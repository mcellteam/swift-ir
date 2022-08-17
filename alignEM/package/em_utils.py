#!/usr/bin/env python3

import os
import sys
import copy
import json
import imghdr
import logging
import inspect
import traceback
from glob import glob
from pathlib import Path
try: import package.config as cfg
except: import config as cfg
try:
    import builtins
except:
    pass

try: from package.utils.treeview import Treeview
except: from utils.treeview import Treeview

__all__ = ['remove_aligned', 'get_cur_scale_key', 'get_cur_layer', 'is_destination_set',
           'is_dataset_scaled', 'is_cur_scale_aligned', 'get_num_aligned',
           'get_skips_list', 'are_aligned_images_generated', 'is_any_scale_aligned_and_generated',
           'print_path', 'print_alignment_layer', 'print_dat_files', 'print_sanity_check',
           'copy_skips_to_all_scales', 'get_num_scales',
           'are_images_imported', 'is_cur_scale_exported',
           'get_num_imported_images', 'print_exception', 'get_scale_key', 'get_scale_val',
           'set_scales_from_string', 'makedirs_exist_ok', 'set_default_settings',
           'clear_all_skips', 'verify_image_file', 'print_debug',
           'make_relative', 'make_absolute', 'is_scale_aligned', 'debug_project',
           'is_cur_scale_ready_for_alignment', 'get_aligned_scales_list', 'get_not_aligned_scales_list',
           'get_scales_list', 'get_next_coarsest_scale_key','get_snr_list', 'print_snr_list', 'print_project_tree',
           'get_coarsest_scale_key']

logger = logging.getLogger(__name__)
# logging.basicConfig(
#         level=logger.info,
#         format="%(asctime)s [%(levelname)s] %(message)s",
#         datefmt='%H:%M:%S',
#         handlers=[logging.StreamHandler()]
# )

def remove_aligned(use_scale, start_layer=0):
    '''
    Removes previously generated aligned images for the current scale, starting at layer 'start_layer'.

    :param use_scale: The scale to remove aligned images from.
    :type use_scale: str

    :param project_dict: The project dictionary.
    :type project_dict: dict

    :param image_library: The image library.
    :type image_library: ImageLibrary

    :param start_layer: The starting layer index from which to remove all aligned images, defaults to 0.
    :type start_layer: int
    '''

    logger.info('image_utils.remove_aligned >>>>')
    for layer in cfg.project_data['data']['scales'][use_scale]['alignment_stack'][start_layer:]:
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

    logger.info('<<<< image_utils.remove_aligned')


def get_scales_list() -> list[str]:
    '''Get scales list.
    Faster than O(n*m) performance.
    Preserves order of scales.'''
    return [key for key in cfg.project_data['data']['scales'].keys()]


def get_aligned_scales_list() -> list[str]:
    '''Get aligned scales list.'''
    return [key for key in cfg.project_data['data']['scales'].keys() if is_scale_aligned(key)]


def get_not_aligned_scales_list() -> list[str]:
    '''Get not aligned scales list.'''
    return [key for key in get_scales_list() if key not in set(get_aligned_scales_list())]


def verify_image_file(path: str) -> str:
    '''Tries to determine the filetype of an image using the Python standard library.
    Returns a string.'''''
    imhgr_type = imghdr.what(path)
    logger.info('verify_image_file | imhgr_type = ' % imhgr_type)
    return imhgr_type


def get_project_file_length(path: str) -> int:
    with open(path, 'r') as f:
        text = f.read()
    for count, line in enumerate(text):  pass
    return count + 1


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
    logger.info('create_project_structure_directories:')
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


def is_cur_scale_ready_for_alignment() -> bool:
    if not are_images_imported():
        return False
    # if not is_dataset_scaled(): #0721-
    #     return False
    scales_dict = cfg.project_data['data']['scales']
    cur_scale_key = get_cur_scale_key()
    coarsest_scale = list(scales_dict.keys())[-1]
    if cur_scale_key == coarsest_scale:
        return True
    scales_list = []
    for scale_key in scales_dict.keys():
        scales_list.append(scale_key)
    cur_scale_index = scales_list.index(cur_scale_key)
    next_coarsest_scale_key = scales_list[cur_scale_index + 1]
    if is_scale_aligned(next_coarsest_scale_key):
        return True
    else:
        return False


def get_next_coarsest_scale_key() -> str:
    if get_num_scales() == 1:
        return get_cur_scale_key()
    scales_dict = cfg.project_data['data']['scales']
    cur_scale_key = get_cur_scale_key()
    coarsest_scale = list(scales_dict.keys())[-1]
    if cur_scale_key == coarsest_scale:
        return cur_scale_key
    scales_list = []
    for scale_key in scales_dict.keys():
        scales_list.append(scale_key)
    cur_scale_index = scales_list.index(cur_scale_key)
    next_coarsest_scale_key = scales_list[cur_scale_index + 1]
    return next_coarsest_scale_key


def set_default_precedure() -> None:
    scales_dict = cfg.project_data['data']['scales']
    coarsest_scale = list(scales_dict.keys())[-1]
    for scale_key in scales_dict.keys():
        scale = scales_dict[scale_key]
        if scale_key == coarsest_scale:
            scale['method_data']['alignment_option'] = 'init_affine'
        else:
            scale['method_data']['alignment_option'] = 'refine_affine'
        for layer_index in range(len(scale['alignment_stack'])):
            layer = scale['alignment_stack'][layer_index]
            if scale_key == coarsest_scale:
                layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
            else:
                layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'


def set_default_settings() -> None:
    '''Force project defaults.'''
    logger.info('set_default_settings:')
    cfg.main_window.hud.post('Applying Project Defaults...')
    scales_dict = cfg.project_data['data']['scales']
    coarsest_scale = list(scales_dict.keys())[-1]
    for scale_key in scales_dict.keys():
        scale = scales_dict[scale_key]
        scale['use_bounding_rect'] = cfg.DEFAULT_BOUNDING_BOX
        scale['null_cafm_trends'] = cfg.DEFAULT_NULL_BIAS
        scale['poly_order'] = cfg.DEFAULT_POLY_ORDER
        if scale_key == coarsest_scale:
            cfg.project_data['data']['scales'][scale_key]['method_data']['alignment_option'] = 'init_affine'
        else:
            cfg.project_data['data']['scales'][scale_key]['method_data']['alignment_option'] = 'refine_affine'
        for layer_index in range(len(scale['alignment_stack'])):
            layer = scale['alignment_stack'][layer_index]
            layer['align_to_ref_method']['method_data']['win_scale_factor'] = cfg.DEFAULT_SWIM_WINDOW
            layer['align_to_ref_method']['method_data']['whitening_factor'] = cfg.DEFAULT_WHITENING
            if scale_key == coarsest_scale:
                layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
            else:
                layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'



def set_scales_from_string(scale_string: str):
    '''This is not pretty. Needs to be refactored ASAP.
    Two callers: 'new_project', 'prepare_generate_scales_worker'
    '''
    cur_scales = [str(v) for v in sorted([get_scale_val(s) for s in cfg.project_data['data']['scales'].keys()])]
    scale_string = scale_string.strip()
    if len(scale_string) > 0:
        input_scales = []
        try:
            input_scales = [str(v) for v in sorted([get_scale_val(s) for s in scale_string.strip().split(' ')])]
        except:
            logger.info("set_scales_from_string | Bad input: (" + str(scale_string) + "), Scales not changed")
            input_scales = []

        if not (input_scales == cur_scales):
            # The scales have changed!!
            # self.define_scales_menu (input_scales)
            cur_scale_keys = [get_scale_key(v) for v in cur_scales]
            input_scale_keys = [get_scale_key(v) for v in input_scales]

            # Remove any scales not in the new list (except always leave 1)
            scales_to_remove = []
            for scale_key in cfg.project_data['data']['scales'].keys():
                if not (scale_key in input_scale_keys):
                    if get_scale_val(scale_key) != 1:
                        scales_to_remove.append(scale_key)
            for scale_key in scales_to_remove:
                cfg.project_data['data']['scales'].pop(scale_key)

            # Add any scales not in the new list
            scales_to_add = []
            for scale_key in input_scale_keys:
                if not (scale_key in cfg.project_data['data']['scales'].keys()):
                    scales_to_add.append(scale_key)
            for scale_key in scales_to_add:
                new_stack = []
                scale_1_stack = cfg.project_data['data']['scales'][get_scale_key(1)]['alignment_stack']
                for l in scale_1_stack:
                    new_layer = copy.deepcopy(l)
                    new_stack.append(new_layer)
                cfg.project_data['data']['scales'][scale_key] = {'alignment_stack': new_stack,
                                                                 'method_data'    : {'alignment_option': 'init_affine'}}
    else:
        logger.info("set_scales_from_string | No input: Scales not changed")


def update_datamodel(updated_model):
    '''This function is called by align_layers and regenerate_aligned. It is called when
    'run_json_project' returns with need_to_write_json=false'''
    logger.info('update_datamodel >>>>>>>>')
    # Load the alignment stack after the alignment has completed
    aln_image_stack = []
    scale_to_run_text = cfg.project_data['data']['current_scale']
    stack_at_this_scale = cfg.project_data['data']['scales'][scale_to_run_text]['alignment_stack']
    for layer in stack_at_this_scale:
        image_name = None
        if 'base' in layer['images'].keys():
            image_name = layer['images']['base']['filename']
        # Convert from the base name to the standard aligned name:
        aligned_name = None
        if image_name != None:
            # The first scale is handled differently now, but it might be better to unify if possible
            if scale_to_run_text == "scale_1":
                aligned_name = os.path.join(os.path.abspath(cfg.project_data['data']['destination_path']),
                                            scale_to_run_text, 'img_aligned', os.path.split(image_name)[-1])
            else:
                name_parts = os.path.split(image_name)
                if len(name_parts) >= 2:
                    aligned_name = os.path.join(os.path.split(name_parts[0])[0],
                                                os.path.join('img_aligned', name_parts[1]))
        aln_image_stack.append(aligned_name)
        # print_debug(30, "Adding aligned image " + aligned_name)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = aligned_name
    try:
        cfg.main_window.load_images_in_role('aligned', aln_image_stack)
    except:
        print_exception()
    cfg.main_window.refresh_all_images()

    # center
    # main_win.center_all_images()
    # main_win.update_win_self()
    # cfg.main_window.center_all_images()
    # cfg.main_window.update_win_self()
    logger.info('<<<<<<<< update_datamodel')


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


def printProjectDetails(project_data: dict) -> None:
    print('In Memory:')
    print("  project_data['data']['destination_path']         :", project_data['data']['destination_path'])
    print("  project_data['data']['source_path']              :", project_data['data']['source_path'])
    print("  project_data['data']['current_scale']            :", project_data['data']['current_scale'])
    print("  project_data['data']['current_layer']            :", project_data['data']['current_layer'])
    print("  project_data['method']                           :", project_data['method'])
    print("  Destination Set Status (is_destination_set)        :", is_destination_set())
    print("  Images Imported Status (are_images_imported)       :", are_images_imported())
    print("  Project Scaled Status (is_dataset_scaled)          :", is_dataset_scaled())
    print("  Any Scale Aligned Status (is_any_scale_aligned_and_generated)     :", is_any_scale_aligned_and_generated())
    print("  Cur Scale Aligned (are_aligned_images_generated)    :", are_aligned_images_generated())
    print("  Any Exported Status (is_any_alignment_exported)     :", is_any_alignment_exported())
    print("  # Imported Images (get_num_imported_images)         :", get_num_imported_images())
    print("  Current Layer SNR (get_cur_snr)                    :", get_cur_snr())

    return None


def debug_project():
    logger.info('-------------- DEBUG PROJECT --------------')
    path = cfg.project_data['data']['destination_path']
    cat_str = 'cat %s.json' % path
    n_init_affine = os.system(cat_str + ' |grep init_affine')
    n_refine_affine = os.system(cat_str + ' |grep refine_affine')
    n_apply_affine = os.system(cat_str + ' |grep apply_affine')
    n_alignment_option = os.system(cat_str + ' |grep alignment_option')
    n_method_options = os.system(cat_str + ' |grep method_options')
    print('Project File:')
    print('  init_affine (project FILE)              :', n_init_affine)
    print('  refine_affine (project FILE)            :', n_refine_affine)
    print('  apply_affine (project FILE)             :', n_apply_affine)
    print('  alignment_option (project_FILE)         :')
    print('cfg.project_data:')
    print('  init_affine (cfg.project_data)    :', str(cfg.project_data).count('init_affine'))
    print('  refine_affine (cfg.project_data)  :', str(cfg.project_data).count('refine_affine'))
    print('  apply_affine (cfg.project_data)   :', str(cfg.project_data).count('apply_affine'))
    print('-------------------------------------------')
    
def is_not_hidden(path):
    return not path.name.startswith(".")
    
def print_project_tree() -> None:
    '''
    Recursive function that lists project directory contents as a tree.
    
    :return:
    :rtype:
    '''
    
    # paths = Treeview.make_tree(
    #     Path('doc'),
    #     criteria=is_not_hidden
    # )
    # for path in paths:
    #     print(path.displayable())
    
    # # With a criteria (skip hidden files)
    # def is_not_hidden(path):
    #     return not path.name.startswith(".")
    
    paths = Treeview.make_tree(Path(cfg.project_data['data']['destination_path']))
    for path in paths:
        print(path.displayable())

# def list_files(startpath):
#     for root, dirs, files in os.walk(startpath):
#         level = root.replace(startpath, '').count(os.sep)
#         indent = ' ' * 4 * (level)
#         print('{}{}/'.format(indent, os.path.basename(root)))
#         subindent = ' ' * 4 * (level + 1)
#         for f in files:
#             print('{}{}'.format(subindent, f))

def print_path() -> None:
    '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
    print('Current directory is...')
    print('os.getcwd()           : %s' % os.getcwd())
    print('Running In (__file__) : %s' % os.path.dirname(os.path.realpath(__file__)))
    print('sys.path              : %s' % sys.path)


def print_alignment_layer() -> None:
    '''Prints a single alignment layer (the last layer) for the current scale from the project dictionary.'''
    try:
        al_layer = cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][-1]
        print(json.dumps(al_layer, indent=2))
    except:
        print('No Alignment Layers Found for the Current Scale')

# def print_zoom_pan_widget_members() -> None:
#     logger.info(cfg.main_window.)


def print_dat_files() -> None:
    '''Prints the .dat files for the current scale, if they exist .'''
    bias_data_path = os.path.join(cfg.project_data['data']['destination_path'], get_cur_scale_key(), 'bias_data')
    if are_images_imported():
        logger.info('Printing .dat Files')
        try:
            logger.info("_____________________BIAS DATA_____________________")
            logger.info("Scale %s____________________________________________" % get_cur_scale_key()[-1])
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
    # try:
    #     print_project_tree()
    # except:
    #     logger.info('Unable to print project tree at this time')
    
    if cfg.project_data['data']['source_path']:
        print("  Source path                                      :", cfg.project_data['data']['source_path'])
    else:
        print("  Source path                                      : n/a")
    if cfg.project_data['data']['destination_path']:
        print("  Destination path                                 :", cfg.project_data['data']['destination_path'])
    else:
        print("  Destination path                                 : n/a")
    cur_scale = cfg.project_data['data']['current_scale']
    try:
        scale = cfg.project_data['data']['scales'][
            cfg.project_data['data']['current_scale']]  # logger.info(scale) returns massive wall of text
    except:
        pass
    print("  Current scale                                    :", cur_scale)
    print("  Project Method                                   :", cfg.project_data['method'])
    print("  Current layer                                    :", cfg.project_data['data']['current_layer'])
    try:
        print("  Alignment Option                                 :",
              scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                  'alignment_option'])
    except:
        print("  Alignment Option                                 : n/a")
    print("Data Selection & Scaling___________________________")
    print("  Are images imported?                             :", are_images_imported())
    print("  How many images?                                 :", get_num_imported_images())
    if get_skips_list():
        print("  Skip list                                        :", get_skips_list())
    else:
        print("  Skip list                                        : n/a")
    print("  Is dataset scaled?                               :", is_dataset_scaled())
    if is_dataset_scaled():
        print("  How many scales?                                 :", get_num_scales())
    else:
        print("  How many scales?                                 : n/a")
    print("  Which scales?                                    :", get_scales_list())

    print("Alignment__________________________________________")
    print("  Is any scale aligned+generated?                  :", is_any_scale_aligned_and_generated())
    print("  Is this scale aligned?                           :", is_cur_scale_aligned())
    print("  Is this scale ready to be aligned?               :", is_cur_scale_ready_for_alignment())
    try:
        
        print("  How many aligned at this scale?                  :", get_num_aligned())
    except:
        print("  How many aligned at this scale?                  : n/a")
    try:
        if get_aligned_scales_list() == []:
            print("  Which scales are aligned?                        : n/a")
        else:
            print("  Which scales are aligned?                        :", str(get_aligned_scales_list()))
    except:
        print("  Which scales are aligned?                        : n/a")

    print("  alignment_option                                 :",
          cfg.project_data['data']['scales'][get_cur_scale_key()]['method_data']['alignment_option'])
    try:
        print("  whitening factor (current layer)                 :",
              scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                  'whitening_factor'])
    except:
        print("  whitening factor (current layer)                 : n/a")
    try:
        print("  SWIM window (current layer)                      :",
              scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                  'win_scale_factor'])
    except:
        print("  SWIM window (current layer)                      : n/a")
    try:
        print("  SNR (current layer)                              :", get_cur_snr())
    except:
        print("  SNR (current layer)                              : n/a")


    print("Post-alignment_____________________________________")
    # try:
    #     null_cafm_trends = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['null_cafm_trends']
    #     logger.info("  null_cafm_trends                                 :", null_cafm_trends)
    # except:
    #     logger.info("  null_cafm_trends                                 : n/a")
    try:
        poly_order = cfg.project_data['data']['scales'][get_cur_scale_key()]['poly_order']
        print("  poly_order (all layers)                          :", poly_order)
    except:
        print("  poly_order (all layers)                          : n/a")
        pass
    try:
        use_bounding_rect = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']][
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
    '''Checks if there is a project open'''
    if cfg.project_data['data']['destination_path']:
        return True
    else:
        return False


def are_images_imported() -> bool:
    '''Checks if any images have been imported.'''
    n_imgs = len(cfg.project_data['data']['scales']['scale_1']['alignment_stack'])
    if n_imgs > 0:
        return True
    else:
        return False


def get_num_imported_images() -> int:
    '''Returns # of imported images.
    CHECK THIS FOR OFF-BY-ONE BUG'''
    try:
        n_imgs = len(cfg.project_data['data']['scales']['scale_1']['alignment_stack'])
    except:
        logger.info('get_num_imported_images | No image layers were found');  return 0  # 0711
    else:
        return n_imgs


def get_skips_list() -> list[int]:
    '''Returns the list of skipped images at the current scale'''
    # logger.info('get_skips_list | called by ',inspect.stack()[1].function)
    skip_list = []
    try:
        for layer_index in range(len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])):
            if cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][layer_index]['skip'] == True:
                skip_list.append(layer_index)
            # logger.info('get_skips_list() | Skips List: %s' % str(skip_list))
    except:
        logger.warning('Unable to get skips list!');  return []  # 0711
    else:
        return skip_list


########################################################################################################################

def get_scale_key(scale_val):
    # Create a key like "scale_#" from either an integer or a string
    s = str(scale_val)
    while s.startswith('scale_'):
        s = s[len('scale_'):]
    return 'scale_' + s


def get_cur_scale_key() -> str:
    '''Returns the current scale, according to cfg.project_data (project dictionary).'''
    return cfg.project_data['data']['current_scale']


def get_scale_val(scale_of_any_type):
    '''Converts scale key to integer (i.e. 'scale_1' as string -> 1 as int)
    TODO: move this to glanceem_utils'''

    # This should return an integer value from any reasonable input (string or int)
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            # It's already an integer, so return it
            return scale
        else:  # elif type(scale) in [ str, unicode ]:
            # It's a string, so remove any optional "scale_" prefix(es) and return as int
            while scale.startswith('scale_'):
                scale = scale[len('scale_'):]
            return int(scale)
    except:
        print_exception()
        # else:
        #    print_debug ( 10, "Error converting " + str(scale_of_any_type) + " of unexpected type (" + str(type(scale)) + ") to a value." )
        #    traceback.print_stack()
    # except:
    #     logger.warning("Error converting " + str(scale_of_any_type) + " to a value.")
    #     exi = sys.exc_info()
    #     logger.warning("  Exception type = " + str(exi[0]))
    #     logger.warning("  Exception value = " + str(exi[1]))
    #     logger.warning("  Exception traceback:")
    #     traceback.print_tb(exi[2])
    #     return -1


def get_num_scales() -> int:
    '''Returns the number of scales in scale pyramid'''
    try:
        n_scales = len(cfg.project_data['data']['scales'].keys())
        return n_scales
    except:
        print_exception()
        logger.warning('Unable to return the # of scales.')


def getScaleKeys() -> list[str]:
    '''Returns the sorted dictionary keys for the scales in the current project'''
    try:
        scale_keys = sorted(cfg.project_data['data']['scales'].keys())
        return scale_keys
    except:
        print_exception()
        logger.warning('Unable to return dictionary keys for scales')

def get_coarsest_scale_key() -> None:
    return list(cfg.project_data['data']['scales'].keys())[-1]

def is_dataset_scaled() -> bool:
    '''Checks if there exists any stacks of scaled images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''
    # if len(cfg.project_data['data']['scales']) < 2:
    #     isScaled = False
    # else:
    #     isScaled = True

    #0804
    try:
        if any(d.startswith('scale_') for d in os.listdir(cfg.project_data['data']['destination_path'])):
            return True
        else:
            return False
    except:
        pass




def get_cur_layer() -> int:
    '''Returns the current layer, according to cfg.project_data (project dictionary).'''
    return cfg.project_data['data']['current_layer']


########################################################################################################################
def is_cur_scale_aligned() -> bool:
    '''Checks if there exists an alignment stack for the current scale

    #0615 Bug fixed - look for populated bias_data folder, not presence of aligned images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''
    try:
        project_dir = cfg.project_data['data']['destination_path']
        bias_dir = os.path.join(project_dir, get_cur_scale_key(), 'bias_data')
        afm_1_file = os.path.join(bias_dir, 'afm_1.dat')
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


def get_num_aligned() -> int:
    '''Returns the count aligned and generated images for the current scale.'''

    path = os.path.join(cfg.project_data['data']['destination_path'], get_cur_scale_key(), 'img_aligned')
    # logger.info('get_num_aligned | path=', path)
    try:
        n_aligned = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
    except:
        return 0
    # logger.info('get_num_aligned() | returning:', n_aligned)
    return n_aligned


def is_any_scale_aligned_and_generated() -> bool:
    '''Checks if there exists a set of aligned images at the current scale'''
    files = glob(cfg.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif*')
    if len(files) > 0:
        return True
    else:
        return False


def is_scale_aligned(scale: str) -> bool:
    '''Returns boolean based on whether arg scale is aligned '''
    # logger.info('called by ', inspect.stack()[1].function)
    try:
        afm_1_file = os.path.join(cfg.project_data['data']['destination_path'], scale, 'bias_data', 'afm_1.dat')
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


# def isAlignmentOfCurrentScale() -> bool:
#     '''Checks if there exists a set of aligned images at the current scale
#
#     DOES *NOT* FUNCTION PROPERLY
#
#     NEEDS TO PROBE 'bias_data' DIRECTORIES
#
#     ISSUES THAT REGENERATING SCALES MEANS PREVIOUS AALIGNMENTS STILL EXIST AND THUS THIS CAN INCORRECTLY RETURN TRUE
#     MIGHT WANT TO HAVE SCALE RE-GENERATION CAUSE PREVIOUSLY ALIGNED IMAGES TO BE REMOVED'''
#
#     try:
#         destination_path = os.path.join(cfg.project_data['data']['destination_path'])
#     except:
#         logger.info('isAlignmentOfCurrentScale | WARNING | There is no project open - Returning False')
#         return False
#
#     try:
#         is_dataset_scaled()
#     except:
#         logger.info('isAlignmentOfCurrentScale | WARNING | This project has not been scaled yet - returning False')
#         return False
#
#     try:
#         bias_path = destination_path + '/' + get_cur_scale_key() + '/bias_data'
#         logger.info('isAlignmentOfCurrentScale | bias path =', bias_path)
#         bias_dir_byte_size=0
#         for path, dirs, files in os.walk(bias_path):
#             for f in files:
#                 fp = os.path.join(path, f)
#                 bias_dir_byte_size += os.path.getsize(fp)
#     except:
#         logger.info('isAlignmentOfCurrentScale | WARNING | Unable to get size of the bias directory - Returning False')
#
#
#     logger.info('isAlignmentOfCurrentScale | size of bias dir=', bias_dir_byte_size)
#
#     if bias_dir_byte_size < 20:
#         logger.info('isAlignmentOfCurrentScale | Returning False')
#         return False
#     else:
#         logger.info('isAlignmentOfCurrentScale | Returning True')
#         return True

def are_aligned_images_generated():
    '''Returns True or False dependent on whether aligned images have been generated for the current scale.'''
    path = os.path.join(cfg.project_data['data']['destination_path'], get_cur_scale_key(), 'img_aligned')
    # logger.info("cfg.project_data['data']['destination_path'] = %s" % cfg.project_data['data']['destination_path'])
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
        files = glob(cfg.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        logger.warning('Something went wrong. Check project dictionary - Returning None')
        return []

    logger.debug('# aligned images found: %d' % len(files))
    logger.debug('List of aligned imgs: %s' % str(files))
    return files


def is_any_alignment_exported() -> bool:
    '''Checks if there exists an exported alignment'''

    return os.path.isdir(os.path.join(cfg.project_data['data']['destination_path'], 'project.zarr'))


def is_cur_scale_exported() -> bool:
    '''Checks if there exists an exported alignment'''
    path = os.path.join(cfg.project_data['data']['destination_path'], '3dem.zarr')
    answer = os.path.isdir(path)
    logger.debug("path: %s" % path)
    logger.debug("response: %s" % str(answer))
    return answer


def get_cur_snr() -> str:
    if not cfg.project_data['data']['current_scale']:
        logger.info("Canceling get_cur_snr() because no current scale is set...")
        return ''  # 0711
    try:
        s = cfg.project_data['data']['current_scale']
        l = cfg.project_data['data']['current_layer']
        if len(cfg.project_data['data']['scales']) > 0:
            scale = cfg.project_data['data']['scales'][s]
            if len(scale['alignment_stack']) > 0:
                layer = scale['alignment_stack'][l]
                if 'align_to_ref_method' in layer:
                    if 'method_results' in layer['align_to_ref_method']:
                        method_results = layer['align_to_ref_method']['method_results']
                        if 'snr_report' in method_results:
                            if method_results['snr_report'] != None:
                                curr_snr = method_results['snr_report']
                                logger.debug("  returning the current snr: %s" % str(curr_snr))
                                return str(curr_snr)
    except:
        logger.warning('An Exception Was Raised Trying To Get SNR of The Current Layer')


def get_snr_list():
    snr_list = []
    # logger.info('len(layer list) = %d' % len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack']))
    for layer in cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack']:
        try:
            snr_vals = layer['align_to_ref_method']['method_results']['snr']
            mean_snr = sum(snr_vals) / len(snr_vals)
            snr_list.append(mean_snr)
        except:
            pass
    return snr_list

def print_snr_list() -> None:
    try:
        snr_list = cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][get_cur_layer()][
            'align_to_ref_method']['method_results']['snr']
        logger.debug('snr_list:  %s' % str(snr_list))
        mean_snr = sum(snr_list) / len(snr_list)
        logger.debug('mean(snr_list):  %s' % mean_snr)
        snr_report = cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][get_cur_layer()][
            'align_to_ref_method']['method_results']['snr_report']
        logger.info('snr_report:  %s' % str(snr_report))
        logger.debug('All Mean SNRs for current scale:  %s' % str(get_snr_list()))
    except:
        logger.info('An Exception Was Raised trying to Print the SNR List')




# def requestConfirmation(title, text):
#     '''Simple request confirmation dialog.'''
#
#     button = QMessageBox.question(None, title, text)
#     logger.info('requestConfirmation | button=',str(button))
#     logger.info('requestConfirmation | type(button)=', type(button))
#     logger.info("requestConfirmation | Returning " + str(button == QMessageBox.StandardButton.Yes))
#     return (button == QMessageBox.StandardButton.Yes)

def print_exception():
    exi = sys.exc_info()
    logger.error("  Exception type = " + str(exi[0]))
    logger.error("  Exception value = " + str(exi[1]))
    logger.error("  Exception trace = " + str(exi[2]))
    logger.error("  Exception traceback:")
    logger.error(traceback.format_exc())
    
    # exc_type, exc_value, exc_tb = sys.exc_info()
    # tb = traceback.TracebackException(exc_type, exc_value, exc_tb)
    # logger.error(''.join(tb.format_exception_only()))
    
    # logger.error('pdb.post_mortem() = ')
    # logger.error(pdb.post_mortem())
    
    # logger.error(traceback.print_tb(exi[2]))
    # now = datetime.now()
    # current_time = now.strftime("%H:%M:%S")
    # with open('~/Logs/traceback.log', "a") as f:
    #     logger.info('--------------------------------Current Time = %s' % current_time, file=f)
    #     frame, filename, line_number, function_name, lines, index = inspect.stack()[1]
    #     logger.info(frame, filename, line_number, function_name, lines, index, file=f)
    #     f.write(traceback.format_exc())


def print_scratch(msg):
    with open('~/Logs/scratchlog', "w") as f:
        f.write(str(msg))


class SwiftirException:
    def __init__(self, project_file, message):
        self.project_file = project_file
        self.message = message

    def __str__(self):
        return self.message


'''
# to override or pass additional arguments...

class ValidationError(Exception):
    def __init__(self, message, errors):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)

        # Now for your custom code...
        self.errors = errors



Rules of global Keyword

The basic rules for global keyword in Python are:

    When we create a variable inside a function, it is local by default.
    When we define a variable outside of a function, it is global by default. You don't have to use global keyword.
    We use global keyword to read and write a global variable inside a function.
    Use of global keyword outside a function has no effect.



'''


########################################################################################################################

def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
    debug_level = 50
    if level <= debug_level:
        if p1 == None:
            sys.stderr.write("" + '')
        elif p2 == None:
            sys.stderr.write(str(p1) + '')
        elif p3 == None:
            sys.stderr.write(str(p1) + str(p2) + '')
        elif p4 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + '')
        elif p5 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + '')
        else:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + str(p5) + '')
        
        try:  # find code_context
            # First try to use currentframe() (maybe not available in all implementations)
            frame = inspect.currentframe()
            if frame:
                # Found a frame, so get the info, and strip space from the code_context
                code_context = inspect.getframeinfo(frame.f_back).code_context[0].strip()
            else:
        
                # No frame, so use stack one level above us, and strip space around
                # the 4th element, code_context
                code_context = inspect.stack()[1][4][0].strip()

        finally:
            # Deterministic free references to the frame, to be on the safe side
            del frame
        print('Code context : {}'.format(code_context))
        # print('Value of args: {}\n'.format(args))


def clear_all_skips():
    logger.info('Clearing all skips | clear_all_skips...')
    image_scale_keys = [s for s in sorted(cfg.project_data['data']['scales'].keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        for layer in cfg.project_data['data']['scales'][scale_key]['alignment_stack']:
            layer['skip'] = False

    # main_win.status_skips_label.setText(str(skip_list))  # settext #status
    # skip.set_value(False) #skip


def copy_skips_to_all_scales():
    logger.info('Copying skips to all scales | copy_skips_to_all_scales...')
    source_scale_key = cfg.project_data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = cfg.project_data['data']['scales']
    image_scale_keys = [s for s in sorted(scales.keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        if not 'scale_' in str(scale_key):
            scale_key = 'scale_' + str(scale_key)
        if scale_key != source_scale_key:
            for l in range(len(scales[source_scale_key]['alignment_stack'])):
                if l < len(scales[scale_key]['alignment_stack']):
                    scales[scale_key]['alignment_stack'][l]['skip'] = scales[source_scale_key]['alignment_stack'][l][
                        'skip']  # <----
    # Not needed: skip.set_value(scales[source_scale_key]['alignment_stack'][cfg.project_data['data']['current_layer']]['skip']


# skip
def update_skip_annotations():
    logger.info('update_skip_annotations:')
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in cfg.project_data['data']['scales'].items():
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
