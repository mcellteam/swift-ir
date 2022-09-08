#!/usr/bin/env python3

import os
import re
import sys
import copy
import json
import time
import signal
import imghdr
import logging
import inspect
import platform
import traceback
from glob import glob
from pathlib import Path
from contextlib import contextmanager
import zarr
import shutil
# import numcodecs
# numcodecs.blosc.use_threads = False #may need
from numcodecs import Blosc
# blosc.set_nthreads(8)
from PIL import Image

try: import src.config as cfg
except: import config as cfg

try:  import builtins
except:  pass

try: from src.utils.treeview import Treeview
except: from utils.treeview import Treeview

from src.image_utils import BoundingRect

__all__ = ['preallocate_zarr', 'print_zarr_info', 'check_for_binaries', 'remove_aligned', 'is_destination_set',
           'do_scales_exist', 'make_relative', 'make_absolute',
           'is_cur_scale_aligned', 'get_num_aligned', 'are_aligned_images_generated',
           'print_path', 'print_alignment_layer', 'print_dat_files', 'print_sanity_check',
           'copy_skips_to_all_scales', 'are_images_imported', 'is_cur_scale_exported', 'get_images_list_directly',
           'print_exception', 'get_scale_key', 'get_scale_val', 'makedirs_exist_ok', 'print_project_tree',
           'verify_image_file', 'is_arg_scale_aligned',  'print_snr_list', 'is_any_scale_aligned_and_generated',
           'remove_zarr', 'init_zarr'
           ]

logger = logging.getLogger(__name__)

def check_for_binaries():
    logger.info("Checking platform-specific path to SWiFT-IR executables...")
    path = os.path.split(os.path.realpath(__file__))[0]
    if platform.system() == 'Darwin':
        bindir = os.path.join(path, 'lib', 'bin_darwin')
    elif platform.system() == 'Linux':
        bindir = os.path.join(path, 'lib', 'bin_tacc') if '.tacc.utexas.edu' in platform.node() else 'bin_linux'
    else:
        logger.warning("System Could Not Be Resolved. C Binaries Not Found.")
        return
    bin_lst = [os.path.join(bindir, 'iavg'),
               os.path.join(bindir, 'iscale2'),
               os.path.join(bindir, 'mir'),
               os.path.join(bindir, 'remod'),
               os.path.join(bindir, 'swim')
               ]
    for f in bin_lst:
        if os.path.isfile(f):  logger.info('%s FOUND' % f)
        else:  logger.warning('%s NOT FOUND' % f)

def print_zarr_info() -> None:
    dest = cfg.data.destination()
    zarr_path = os.path.join(dest, '3dem.zarr')
    z = zarr.open(zarr_path)
    print('List Dir:\n%s' % str(sorted(os.listdir(zarr_path))))
    print(z.info)
    print(z.tree())


def reorder_tasks(task_list, z_stride) -> list:
    tasks=[]
    for x in range(0, z_stride): #chunk z_dim
        tasks.extend(task_list[x::z_stride])
        # append_list = task_list[x::z_stride]
        # for t in append_list:
        #     tasks.append(t)
    return tasks

# def remove_zarr() -> None:
def remove_zarr(path) -> None:
    # path = os.path.join(cfg.data.destination(), '3dem.zarr')
    if os.path.isdir(path):
        logger.critical('Removing Zarr...')
        try:
            with time_limit(15):
                logger.info('Removing %s...' % path)
                shutil.rmtree(path, ignore_errors=True)
        except TimeoutException as e:
            logger.warning("Timed out!")
        logger.info('Finished Removing Zarr Files')

def init_zarr() -> None:
    logger.critical('Initializing Zarr...')
    path = os.path.join(cfg.data.destination(), '3dem.zarr')
    store = zarr.DirectoryStore(path, dimension_separator='/')  # Create Zarr DirectoryStore
    root = zarr.group(store=store, overwrite=True)  # Create Root Group (?)
    # root = zarr.group(store=store, overwrite=True, synchronizer=zarr.ThreadSynchronizer())  # Create Root Group (?)
    print_zarr_info()

def preallocate_zarr(use_scale=None, bounding_rect=True, z_stride=16, chunks=(16,64,64)):

    cfg.main_window.hud.post('Preallocating Zarr Array...')
    cur_scale = cfg.data.get_scale()
    cur_scale_val = get_scale_val(cfg.data.get_scale())
    src = os.path.abspath(cfg.data.destination())
    n_imgs = cfg.data.get_n_images()
    # n_scales = cfg.data.get_n_scales()
    aligned_scales_lst = cfg.data.get_aligned_scales_list()

    zarr_path = os.path.join(cfg.data.destination(), '3dem.zarr')
    caller = inspect.stack()[1].function
    # if (use_scale == cfg.data.get_coarsest_scale_key()) or caller == 'generate_zarr':
    #     # remove_zarr()
    #     init_zarr()

    out_path = os.path.join(src, '3dem.zarr', 's' + str(cur_scale_val))

    if cfg.data.get_scale() != 'scale_1':
        if os.path.exists(out_path):
            remove_zarr(out_path)

    # name = 's' + str(get_scale_val(use_scale))
    # zarr_name = os.path.join(zarr_path,name)
    # synchronizer = zarr.ProcessSynchronizer(zarr_path)
    # root = zarr.group(store=zarr_path, synchronizer=synchronizer)  # Create Root Group
    root = zarr.group(store=zarr_path)  # Create Root Group
    # root = zarr.group(store=zarr_name, overwrite=True)  # Create Root Group
    # root = zarr.open(store=zarr_path)  # Create Root Group
    # root = zarr.open(zarr_path, mode='w')

    opt_cname = cfg.main_window.cname_combobox.currentText()
    opt_clevel = int(cfg.main_window.clevel_input.text())

    if use_scale is None:
        zarr_these_scales = aligned_scales_lst
    else:
        zarr_these_scales = [use_scale]

    logger.critical('Preallocating Zarr for Scales: %s' % str(zarr_these_scales))

    datasets = []
    for scale in zarr_these_scales:
        logger.info('Preallocating Zarr for Scale: %s' % str(scale))

        if bounding_rect is True:
            rect = BoundingRect(cfg.data['data']['scales'][scale]['alignment_stack'])
            dimx = rect[2]
            dimy = rect[3]
        else:
            imgs = sorted(get_images_list_directly(os.path.join(src, scale, 'img_src')))
            dimx, dimy = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size


        scale_val = get_scale_val(scale)
        name = 's' + str(scale_val)

        shape = (n_imgs, dimy, dimx)
        # chunks = (z_stride, 64, 64)
        dtype = 'uint8'
        compressor = Blosc(cname=opt_cname, clevel=opt_clevel) if opt_cname in ('zstd', 'zlib', 'gzip') else None
        # compressor = Blosc(cname='zstd', clevel=5)

        # synchronizer = zarr.ProcessSynchronizer('example.zarr')
        logger.critical('Zarr Array will have shape: %s' % str(shape))
        array = root.zeros(name=name, shape=shape, chunks=chunks, dtype=dtype, compressor=compressor, overwrite=True)  # Preallocate



        # datasets.append(
        #     {
        #         "path": name,
        #         "coordinateTransformations": [{
        #             "type": "scale",
        #             "scale": [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]}]
        #     }
        # )

        # metadata = {
        #     "path": name,
        #     "coordinateTransformations": [{
        #         "type": "scale",
        #         "scale": [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]}]
        # }
        # root.attrs["multiscales"][0]["datasets"].append(metadata)

    # write_zarr_metadata() # write single multiscale zarr for all aligned scale

    if cfg.data.get_scale() == 'scale_1':
        write_zarr_metadata()
    else:
        write_zarr_metadata_cur_scale() # write multiscale zarr for current scale

    # time.sleep(500)


def write_zarr_metadata():
    zarr_path = os.path.join(cfg.data.destination(), '3dem.zarr')
    root = zarr.group(store=zarr_path)
    datasets = []
    for scale in cfg.data.get_aligned_scales_list():
        scale_val = get_scale_val(scale)
        name = 's' + str(scale_val)
        metadata = {
            "path": name,
            "coordinateTransformations": [{
                "type": "scale",
                "scale": [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]}]
        }
        datasets.append(metadata)

    axes = [
        {"name": "z", "type": "space", "unit": "nanometer"},
        {"name": "y", "type": "space", "unit": "nanometer"},
        {"name": "x", "type": "space", "unit": "nanometer"}
    ]

    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
            "version": "0.4",
            "name": "my_data",
            "axes": axes,
            "datasets": datasets,
            "type": "gaussian",
        }
    ]

def write_zarr_metadata_cur_scale():
    zarr_path = os.path.join(cfg.data.destination(), '3dem.zarr')
    root = zarr.group(store=zarr_path)
    datasets = []
    scale_val = get_scale_val(cfg.data.get_scale())
    name = 's' + str(scale_val)
    metadata = {
        "path": name,
        "coordinateTransformations": [{
            "type": "scale",
            "scale": [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]}]
    }
    datasets.append(metadata)

    axes = [
        {"name": "z", "type": "space", "unit": "nanometer"},
        {"name": "y", "type": "space", "unit": "nanometer"},
        {"name": "x", "type": "space", "unit": "nanometer"}
    ]

    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
            "version": "0.4",
            "name": "my_data",
            "axes": axes,
            "datasets": datasets,
            "type": "gaussian",
        }
    ]


class TimeoutException(Exception): pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


def print_exception():
    exi = sys.exc_info()
    logger.warning("  Exception type = " + str(exi[0]))
    logger.warning("  Exception value = " + str(exi[1]))
    logger.warning("  Exception trace = " + str(exi[2]))
    logger.warning("  Exception traceback:")
    logger.warning(traceback.format_exc())
    '''Pipe these into a logs directory - but where?'''


def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def get_images_list_directly(path) -> list[str]:
    logger.debug('get_images_list_directly:')
    logger.debug('Searching in Path: %s ' % path)
    imgs = [x for x in os.listdir(path) if os.path.splitext(x)[1] in (
        '.tif',
        '.tiff',
        '.bmp',
        '.jpg',
        '.jpeg',
        '.png',
        '.eps'
    )]
    logger.debug('Returning: %s' % str(imgs))
    return imgs


def remove_aligned(use_scale, start_layer=0):
    '''
    Removes previously generated aligned images for the current scale, starting at layer 'start_layer'.

    :param use_scale: The scale to remove aligned images from.
    :type use_scale: str

    :param project_dict: The data dictionary.
    :type project_dict: dict

    :param image_library: The image library.
    :type image_library: ImageLibrary

    :param start_layer: The starting layer index from which to remove all aligned images, defaults to 0.
    :type start_layer: int
    '''

    logger.info('image_utils.remove_aligned:')
    for layer in cfg.data['data']['scales'][use_scale]['alignment_stack'][start_layer:]:
        ifn = layer['images'].get('filename', None)
        layer['images'].pop('aligned', None)
        if ifn != None:
            try:
                os.remove(ifn)
            except:
                print_exception()
                logger.warning("os.remove(%s) Triggered An Exception" % ifn)

            try:
                cfg.image_library.remove_image_reference(ifn)
            except:
                print_exception()
                logger.warning("image_library.remove_image_reference(%s) Triggered An Exception" % ifn)



def verify_image_file(path: str) -> str:
    '''Tries to determine the filetype of an image using the Python standard library.
    Returns a string.'''''
    imhgr_type = imghdr.what(path)
    logger.info('verify_image_file | imhgr_type = ' % imhgr_type)
    return imhgr_type


def percentage(part, whole) -> str:
    percentage = 100 * float(part) / float(whole)
    return str(round(percentage, 2)) + "%"


def get_best_path(file_path):
    '''Normalize path for different OS'''
    return os.path.abspath(os.path.normpath(file_path))


def make_relative(file_path, proj_path):
    rel_path = os.path.relpath(file_path, start=os.path.split(proj_path)[0])
    return rel_path


def make_absolute(file_path, proj_path):
    abs_path = os.path.join(os.path.split(proj_path)[0], file_path)
    return abs_path


def create_project_structure_directories(subdir_path) -> None:
    src_path = os.path.join(subdir_path, 'img_src')
    aligned_path = os.path.join(subdir_path, 'img_aligned')
    bias_data_path = os.path.join(subdir_path, 'bias_data')
    try:
        os.mkdir(subdir_path)
        os.mkdir(src_path)
        os.mkdir(aligned_path)
        os.mkdir(bias_data_path)
    except:
        pass


def printProjectDetails(project_data: dict) -> None:
    logger.info('In Memory:')
    logger.info("  data['data']['destination_path']         :", project_data['data']['destination_path'])
    logger.info("  data['data']['source_path']              :", project_data['data']['source_path'])
    logger.info("  data['data']['current_scale']            :", project_data['data']['current_scale'])
    logger.info("  data['data']['current_layer']            :", project_data['data']['current_layer'])
    logger.info("  data['method']                           :", project_data['method'])
    logger.info("  Destination Set Status    :", is_destination_set())
    logger.info("  Images Imported Status    :", are_images_imported())
    logger.info("  Project Scaled Status     :", do_scales_exist())
    logger.info("  Any Scale Aligned Status  :", is_any_scale_aligned_and_generated())
    logger.info("  Cur Scale Aligned         :", are_aligned_images_generated())
    logger.info("  Any Exported Status       :", is_any_alignment_exported())
    logger.info("  # Imported Images         :", cfg.data.get_n_images())
    logger.info("  Current Layer SNR         :", cfg.data.get_snr())


def is_not_hidden(path):
    return not path.name.startswith(".")


def print_project_tree() -> None:
    '''Recursive function that lists data directory contents as a tree.'''
    paths = Treeview.make_tree(Path(cfg.data['data']['destination_path']))
    for path in paths:
        print(path.displayable())


def print_path() -> None:
    '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
    print('Current directory is...')
    print('os.getcwd()           : %s' % os.getcwd())
    print('Running In (__file__) : %s' % os.path.dirname(os.path.realpath(__file__)))
    print('sys.path              : %s' % sys.path)


def print_alignment_layer() -> None:
    '''Prints a single alignment layer (the last layer) for the current scale from the data dictionary.'''
    try:
        al_layer = cfg.data['data']['scales'][cfg.data.get_scale()]['alignment_stack'][-1]
        print(json.dumps(al_layer, indent=2))
    except:
        print('No Alignment Layers Found for the Current Scale')


def print_dat_files() -> None:
    '''Prints the .dat files for the current scale, if they exist .'''
    bias_data_path = os.path.join(cfg.data['data']['destination_path'], cfg.data.get_scale(), 'bias_data')
    if are_images_imported():
        logger.info('Printing .dat Files')
        try:
            logger.info("_____________________BIAS DATA_____________________")
            logger.info("Scale %d____________________________________________" % get_scale_val(cfg.data.get_scale()))
            with open(os.path.join(bias_data_path, 'snr_1.dat'), 'r') as f:
                snr_1 = f.read()
                logger.info('snr_1               : %s' % snr_1)
            with open(os.path.join(bias_data_path, 'bias_x_1.dat'), 'r') as f:
                bias_x_1 = f.read()
                logger.info('bias_x_1            : %s' % bias_x_1)
            with open(os.path.join(bias_data_path, 'bias_y_1.dat'), 'r') as f:
                bias_y_1 = f.read()
                logger.info('bias_y_1            : %s' % bias_y_1)
            with open(os.path.join(bias_data_path, 'bias_rot_1.dat'), 'r') as f:
                bias_rot_1 = f.read()
                logger.info('bias_rot_1          : %s' % bias_rot_1)
            with open(os.path.join(bias_data_path, 'bias_scale_x_1.dat'), 'r') as f:
                bias_scale_x_1 = f.read()
                logger.info('bias_scale_x_1      : %s' % bias_scale_x_1)
            with open(os.path.join(bias_data_path, 'bias_scale_y_1.dat'), 'r') as f:
                bias_scale_y_1 = f.read()
                logger.info('bias_scale_y_1      : %s' % bias_scale_y_1)
            with open(os.path.join(bias_data_path, 'bias_skew_x_1.dat'), 'r') as f:
                bias_skew_x_1 = f.read()
                logger.info('bias_skew_x_1       : %s' % bias_skew_x_1)
            with open(os.path.join(bias_data_path, 'bias_det_1.dat'), 'r') as f:
                bias_det_1 = f.read()
                logger.info('bias_det_1          : %s' % bias_det_1)
            with open(os.path.join(bias_data_path, 'afm_1.dat'), 'r') as f:
                afm_1 = f.read()
                logger.info('afm_1               : %s' % afm_1)
            with open(os.path.join(bias_data_path, 'c_afm_1.dat'), 'r') as f:
                c_afm_1 = f.read()
                logger.info('c_afm_1             : %s' % c_afm_1)
        except:
            logger.info('Is this scale aligned? No .dat files were found at this scale.')
            pass


def print_sanity_check():
    # logging.debug('print_sanity_check | logger is logging')
    logger.info("___________________SANITY CHECK____________________")
    logger.info("Project____________________________________________")
    if cfg.data['data']['source_path']:
        print("  Source path                                      :", cfg.data['data']['source_path'])
    else:
        print("  Source path                                      : n/a")
    if cfg.data['data']['destination_path']:
        print("  Destination path                                 :", cfg.data['data']['destination_path'])
    else:
        print("  Destination path                                 : n/a")
    cur_scale = cfg.data['data']['current_scale']
    try:
        scale = cfg.data.get_scale()  # logger.info(scale) returns massive wall of text
    except:
        pass
    print("  Current scale                                    :", cur_scale)
    print("  Project Method                                   :", cfg.data['method'])
    print("  Current layer                                    :", cfg.data['data']['current_layer'])
    try:
        print("  Alignment Option                                 :",
              scale['alignment_stack'][cfg.data['data']['current_layer']]['align_to_ref_method']['method_data'][
                  'alignment_option'])
    except:
        print("  Alignment Option                                 : n/a")
    print("Data Selection & Scaling___________________________")
    print("  Are images imported?                             :", are_images_imported())
    print("  How many images?                                 :", cfg.data.get_n_images())
    skips = cfg.data.get_skips()
    if skips != []:
        print("  Skip list                                        :", skips)
    else:
        print("  Skip list                                        : n/a")
    print("  Is dataset scaled?                               :", do_scales_exist())
    if do_scales_exist():
        print("  How many scales?                                 :", cfg.data.get_n_scales())
    else:
        print("  How many scales?                                 : n/a")
    print("  Which scales?                                    :", cfg.data.get_scales())

    print("Alignment__________________________________________")
    print("  Is any scale aligned+generated?                  :", is_any_scale_aligned_and_generated())
    print("  Is this scale aligned?                           :", is_cur_scale_aligned())
    print("  Is this scale ready to be aligned?               :", cfg.data.is_alignable())
    try:
        
        print("  How many aligned at this scale?                  :", get_num_aligned())
    except:
        print("  How many aligned at this scale?                  : n/a")
    try:
        al_scales = cfg.data.get_aligned_scales_list()
        if al_scales == []:
            print("  Which scales are aligned?                        : n/a")
        else:
            print("  Which scales are aligned?                        :", str(al_scales))
    except:
        print("  Which scales are aligned?                        : n/a")

    print("  alignment_option                                 :",
          cfg.data['data']['scales'][cfg.data.get_scale()]['method_data']['alignment_option'])
    try:
        print("  whitening factor (current layer)                 :",
              scale['alignment_stack'][cfg.data['data']['current_layer']]['align_to_ref_method']['method_data'][
                  'whitening_factor'])
    except:
        print("  whitening factor (current layer)                 : n/a")
    try:
        print("  SWIM window (current layer)                      :",
              scale['alignment_stack'][cfg.data['data']['current_layer']]['align_to_ref_method']['method_data'][
                  'win_scale_factor'])
    except:
        print("  SWIM window (current layer)                      : n/a")
    try:
        print("  SNR (current layer)                              :", cfg.data.get_snr())
    except:
        print("  SNR (current layer)                              : n/a")


    print("Post-alignment_____________________________________")
    try:
        poly_order = cfg.data['data']['scales'][cfg.data.get_scale()]['poly_order']
        print("  poly_order (all layers)                          :", poly_order)
    except:
        print("  poly_order (all layers)                          : n/a")
        pass
    try:
        use_bounding_rect = cfg.data['data']['scales'][cfg.data['data']['current_scale']][
            'use_bounding_rect']
        print("  use_bounding_rect (all layers)                   :", use_bounding_rect)
    except:
        print("  use_bounding_rect (all layers)                   : n/a")

    print("Export & View______________________________________")
    print("  Is any alignment exported?                       :", is_any_alignment_exported())
    print("  Is current scale exported?                       :", is_cur_scale_exported())


def module_debug() -> None:
    '''Simple helper function to debug available modules.'''
    import sys, os
    modulenames = set(sys.modules) & set(globals())
    allmodules = [sys.modules[name] for name in modulenames]
    logger.info('========================================================' +
          '_____________________MODULE DEBUG_______________________' +
          'script       : ' + str(logger.info(sys.argv[0])) + 'running in   :' +
          str(os.path.dirname(os.path.realpath(__file__))) + 'sys.pathc    : ' + str(sys.path) +
          'module names : ' + str(modulenames) + 'allmodules   : ' + str(allmodules) +
          'In module products sys.path[0] = ' + str(sys.path[0]) + '__package__ = ' +
          str(__package__) + '========================================================')

    # Courtesy of https://github.com/wimglenn
    import sys
    try:
        old_import = builtins.__import__

        def my_import(name, *args, **kwargs):
            if name not in sys.modules:  logger.info('importing --> {}'.format(name))
            return old_import(name, *args, **kwargs)

        builtins.__import__ = my_import
    except:
        pass


def is_destination_set() -> bool:
    '''Checks if there is a data open'''
    if cfg.data['data']['destination_path']:
        return True
    else:
        return False


def are_images_imported() -> bool:
    '''Checks if any images have been imported.'''
    n_imgs = len(cfg.data['data']['scales']['scale_1']['alignment_stack'])
    if n_imgs > 0:
        cfg.IMAGES_IMPORTED = True
        return True
    else:
        cfg.IMAGES_IMPORTED = False
        return False


def get_scale_key(scale_val):
    '''Create a key like "scale_#" from either an integer or a string'''
    s = str(scale_val)
    while s.startswith('scale_'):
        s = s[len('scale_'):]
    return 'scale_' + s


def get_scale_val(scale_of_any_type) -> int:
    '''Converts scale key to integer (i.e. 'scale_1' as string -> 1 as int)
    TODO: move this to glanceem_utils'''
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            return scale
        else:
            while scale.startswith('scale_'):
                scale = scale[len('scale_'):]
            return int(scale)
    except:
        print_exception()


def do_scales_exist() -> bool:
    '''Checks whether any stacks of scaled images exist'''
    try:
        if any(d.startswith('scale_') for d in os.listdir(cfg.data['data']['destination_path'])):
            return True
        else:
            return False
    except:
        pass

def is_cur_scale_aligned() -> bool:
    '''Checks if there exists an alignment stack for the current scale

    #0615 Bug fixed - look for populated bias_data folder, not presence of aligned images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a data that does not need scales.'''
    try:
        afm_1_file = os.path.join(cfg.data['data']['destination_path'],
                                  cfg.data.get_scale(),
                                  'bias_data',
                                  'afm_1.dat')
        # logger.info('afm_1_file = ', afm_1_file)
        # logger.info('os.path.exists(afm_1_file) = ', os.path.exists(afm_1_file))
        if os.path.exists(afm_1_file):
            logger.debug('is_cur_scale_aligned | Returning True')
            return True
        else:
            logger.debug('is_cur_scale_aligned | Returning False')
            return False
    except:
        logger.warning('Unexpected function behavior - Returning False')
        return False


def is_arg_scale_aligned(scale: str) -> bool:
    '''Returns boolean based on whether arg scale is aligned '''
    # logger.info('called by ', inspect.stack()[1].function)
    try:
        afm_1_file = os.path.join(cfg.data['data']['destination_path'], scale, 'bias_data', 'afm_1.dat')
        if os.path.exists(afm_1_file):
            if os.path.getsize(afm_1_file) > 1:
                # check if file is large than 1 byte
                # logger.info('is_scale_aligned | Returning True')
                return True
            else:
                return False
                # logger.info('is_scale_aligned | Returning False (afm_1.dat exists but contains no data)')
        else:
            # logger.info('is_scale_aligned | Returning False (afm_1.dat does not exist)')
            return False
    except:
        logger.warning('Unexpected function behavior - Returning False')
        return False

def get_num_aligned() -> int:
    '''Returns the count aligned and generated images for the current scale.'''

    path = os.path.join(cfg.data['data']['destination_path'], cfg.data.get_scale(), 'img_aligned')
    # logger.info('get_num_aligned | path=', path)
    try:
        n_aligned = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
    except:
        return 0
    # logger.info('get_num_aligned() | returning:', n_aligned)
    return n_aligned

def is_any_scale_aligned_and_generated() -> bool:
    '''Checks if there exists a set of aligned images at the current scale
    Todo: Sometimes aligned images are generated but do get rendered'''
    files = glob(cfg.data['data']['destination_path'] + '/scale_*/img_aligned/*.tif*')
    if len(files) > 0:
        return True
    else:
        return False


def are_aligned_images_generated():
    '''Returns True or False dependent on whether aligned images have been generated for the current scale.'''
    path = os.path.join(cfg.data['data']['destination_path'], cfg.data.get_scale(), 'img_aligned')
    files = glob(path + '/*.tif')
    if len(files) < 1:
        logger.debug('Zero aligned TIFs were found at this scale - Returning False')
        return False
    else:
        logger.debug('One or more aligned TIFs were found at this scale - Returning True')
        return True


def return_aligned_imgs() -> list:
    '''Returns the list of paths for aligned images at the current scale, if any exist.'''

    try:
        files = glob(cfg.data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        logger.warning('Something went wrong. Check data dictionary - Returning None')
        return []

    logger.debug('# aligned images found: %d' % len(files))
    logger.debug('List of aligned imgs: %s' % str(files))
    return files


def is_any_alignment_exported() -> bool:
    '''Checks if there exists an exported alignment'''
    return os.path.isdir(os.path.join(cfg.data['data']['destination_path'], '3dem.zarr'))


def is_cur_scale_exported() -> bool:
    '''Checks if there exists an exported alignment'''
    path = os.path.join(cfg.data['data']['destination_path'], '3dem.zarr')
    answer = os.path.isdir(path)
    logger.debug("path: %s" % path)
    logger.debug("response: %s" % str(answer))
    return answer


def print_snr_list() -> None:
    try:
        snr_list = cfg.data['data']['scales'][cfg.data.get_scale()]['alignment_stack'][cfg.data.get_layer()][
            'align_to_ref_method']['method_results']['snr']
        logger.debug('snr_list:  %s' % str(snr_list))
        mean_snr = sum(snr_list) / len(snr_list)
        logger.debug('mean(snr_list):  %s' % mean_snr)
        snr_report = cfg.data['data']['scales'][cfg.data.get_scale()]['alignment_stack'][cfg.data.get_layer()][
            'align_to_ref_method']['method_results']['snr_report']
        logger.info('snr_report:  %s' % str(snr_report))
        logger.debug('All Mean SNRs for current scale:  %s' % str(cfg.data.snr_list()))
    except:
        logger.info('An Exception Was Raised trying to Print the SNR List')

def print_scratch(msg):
    with open('~/Logs/scratchlog', "w") as f:
        f.write(str(msg))

def makedirs_exist_ok(path_to_build, exist_ok=False):
    # Needed for old python which doesn't have the exist_ok option!!!
    logger.debug("Making directories for path %s" % path_to_build)
    parts = path_to_build.split(os.sep)  # Variable "parts" should be a list of subpath sections. The first will be empty ('') if it was absolute.
    full = ""
    if len(parts[0]) == 0:
        # This happens with an absolute PosixPath
        full = os.sep
    else:
        # This may be a Windows drive or the start of a non-absolute path
        if ":" in parts[0]:
            # Assume a Windows drive
            full = parts[0] + os.sep
        else:
            # This is a non-absolute path which will be handled naturally with full=""
            pass
    for p in parts:
        full = os.path.join(full, p)
        if not os.path.exists(full):
            os.makedirs(full)
        elif not exist_ok:
            pass
            # logger.info("Warning: Attempt to create existing directory: " + full)


def copy_skips_to_all_scales():
    logger.info('Copying skips to all scales...')
    source_scale_key = cfg.data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = cfg.data['data']['scales']
    image_scale_keys = [s for s in sorted(scales.keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        if not 'scale_' in str(scale_key):
            scale_key = 'scale_' + str(scale_key)
        if scale_key != source_scale_key:
            for l in range(len(scales[source_scale_key]['alignment_stack'])):
                if l < len(scales[scale_key]['alignment_stack']):
                    scales[scale_key]['alignment_stack'][l]['skip'] = \
                        scales[source_scale_key]['alignment_stack'][l]['skip']  # <----


def update_skip_annotations():
    logger.info('update_skip_annotations:')
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in cfg.data['data']['scales'].items():
        for layer in scale['alignment_stack']:
            layer_num = scale['alignment_stack'].index(layer)
            for ik, im in layer['images'].items():
                if not 'metadata' in im:
                    im['metadata'] = {}
                if not 'annotations' in im['metadata']:
                    im['metadata']['annotations'] = []
                ann = im['metadata']['annotations']
                if layer['skip']:
                    # Check and set as needed
                    already_skipped = False
                    for a in ann:
                        if a.startswith('skipped'):
                            already_skipped = True
                            break
                    if not already_skipped:
                        add_list.append((sk, layer_num, ik))
                        ann.append('skipped(1)')
                else:
                    # Remove all "skipped"
                    for a in ann:
                        if a.startswith('skipped'):
                            remove_list.append((sk, layer_num, ik))
                            ann.remove(a)
    # for item in remove_list:
    #     interface.print_debug(80, "Removed skip from " + str(item))
    # for item in add_list:
    #     interface.print_debug(80, "Added skip to " + str(item))

class SwiftirException:
    def __init__(self, project_file, message):
        self.project_file = project_file
        self.message = message

    def __str__(self):
        return self.message


# NOTE: this is called right after importing base images
# def update_linking_callback():
#     logger.info('Updating linking callback | update_linking_callback...')
#     link_all_stacks()
#     logger.info('Exiting update_linking_callback()')
#
#
# def update_skips_callback(new_state):
#     logger.info('Updating skips callback | update_skips_callback...')
#
#     # Update all of the annotations based on the skip values
#     copy_skips_to_all_scales()
#     # update_skip_annotations()  # This could be done via annotations, but it's easier for now to hard-code into main_window.py
#     logger.info("Exiting update_skips_callback(new_state)")


# def mouse_down_callback(role, screen_coords, image_coords, button):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     # logger.info("mouse_down_callback was called but there is nothing to do.")
#     return  # monkeypatch
#
#
# def mouse_move_callback(role, screen_coords, image_coords, button):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     return #monkeypatch #jy
#
#     # # logger.info("view_match_crop.get_value() = ", view_match_crop.get_value())
#     # if view_match_crop.get_value() == 'Match':
#     #     return (True)  # Lets the framework know that the move has been handled
#     # else:
#     #     return (False)  # Lets the framework know that the move has not been handled

# def notyet():
#     logger.info('notyet() was called')
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + str(skip.value)) #skip
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + main_window.toggle_skip.isChecked())

# def crop_mode_callback():
#     return
#     # return view_match_crop.get_value()
