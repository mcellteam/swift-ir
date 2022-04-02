"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.

"""
import sys, traceback, os, copy, math, cv2, json, psutil, argparse, inspect, numpy, scipy, scipy.ndimage, threading, \
    concurrent.futures, platform, collections, time, multiprocessing, logging, operator

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QStackedLayout, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox, \
    QSpacerItem, QMenu, QColorDialog, QMessageBox, QComboBox, QRubberBand, QToolButton, QStyle, QDialog, QFrame, \
    QStyleFactory, QGroupBox
from PySide6.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor, QIntValidator, QDoubleValidator, QIcon, \
    QSurfaceFormat, QAction, QActionGroup, QPaintEvent, QBrush, QFont
from PySide6.QtCore import Slot, QRect, QRectF, QSize, Qt, QPoint, QPointF, QThreadPool, QUrl, QFile, QTextStream, \
    QCoreApplication, Property, QRunnable, Signal, Slot, QThreadPool, QThread
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

from http.server import SimpleHTTPRequestHandler, HTTPServer
import zarr, daisy, skimage.measure, tifffile, imagecodecs
import dask.array as da
import neuroglancer as ng
from glob import glob
from PIL import Image
import numpy as np

from joel_decs import timeit, profileit, dumpit, traceit, countit
from glanceem_utils import RequestHandler, Server, get_viewer_url, tiffs2zarr, open_ds, add_layer
from alignem_data_model import new_project_template, new_layer_template, new_image_template, upgrade_data_model
import align_swiftir, pyswift_tui
import task_queue_mp as task_queue
import task_wrapper
import pyswift_tui

# from caveclient import CAVEclient


# project_data = None #jy

# Get the path of ../python
# alignem_file = os.path.abspath(__file__)                     # path/PySide6/py
# alignem_p    = os.path.dirname( alignem_file )               # path/PySide6
# alignem_pp   = os.path.dirname( alignem_p )                  # path
# alignem_shared_path = os.path.join ( alignem_pp, 'python' )  # path/python

# if len(sys.path) <= 0:
#  # Add the path to the currently empty path (this would be an unusual case)
#  sys.path.append ( alignem_shared_path )
# else:
#  # Add the path in the second position (after the default current directory of "")
#  sys.path.insert ( 1, alignem_shared_path )

enable_stats = False


# For now, always use the limited argument version
def print_debug(level, p1=None, p2=None, p3=None, p4=None):
    global DEBUG_LEVEL
    if level <= DEBUG_LEVEL:
        if p1 == None:
            print("")
        elif p2 == None:
            print(str(p1))
        elif p3 == None:
            print(str(p1) + str(p2))
        elif p4 == None:
            print(str(p1) + str(p2) + str(p3))
        else:
            print(str(p1) + str(p2) + str(p3) + str(p4))


app = None
use_c_version = True
use_file_io = False
show_skipped_images = True

preloading_range = 3
max_image_file_size = 1000000000
crop_window_mode = 'mouse_rectangle'  # mouse_rectangle or mouse_square or fixed
crop_window_width = 1024
crop_window_height = 1024

update_linking_callback = None
update_skips_callback = None

crop_mode_callback = None
crop_mode_role = None
crop_mode_origin = None
crop_mode_disp_rect = None
crop_mode_corners = None
# current_scale = 'scale_1'

main_window = None  #tag


def clear_crop_settings():
    global crop_mode_role
    global crop_mode_orgin
    global crop_mode_disp_rect
    global crop_mode_corners
    crop_mode_role = None
    crop_mode_orgin = None
    crop_mode_disp_rect = None
    crop_mode_corners = None


def get_cur_scale():
    global project_data  #debug #tag
    curr_scale = project_data['data']['current_scale']
    # print("get_cur_scale() was called by " + inspect.stack()[1].function + "...")
    # print("  returning the current scale:", curr_scale)
    return curr_scale


def get_cur_snr():
    # print("get_cur_snr() was called by " + inspect.stack()[1].function + "...")
    # print("  current scale,layer according to project_data is " + str(project_data['data']['current_scale']) + ',' + str(project_data['data']['current_layer']))
    s = project_data['data']['current_scale']
    l = project_data['data']['current_layer']

    # print("  len(project_data['data']['scales']) = ", len(project_data['data']['scales']))

    if len(project_data['data']['scales']) > 0:
        scale = project_data['data']['scales'][s]
        if len(scale['alignment_stack']) > 0:
            layer = scale['alignment_stack'][l]
            if 'align_to_ref_method' in layer:
                if 'method_results' in layer['align_to_ref_method']:
                    method_results = layer['align_to_ref_method']['method_results']
                    if 'snr_report' in method_results:
                        if method_results['snr_report'] != None:
                            curr_snr = method_results['snr_report']
                            print("  returning the current snr:", str(curr_snr))
                            return curr_snr


def makedirs_exist_ok(path_to_build, exist_ok=False):
    # Needed for old python which doesn't have the exist_ok option!!!
    print_debug(30, " Make dirs for " + path_to_build)
    parts = path_to_build.split(
        os.sep)  # Variable "parts" should be a list of subpath sections. The first will be empty ('') if it was absolute.
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
            print_debug(1, "Warning: Attempt to create existing directory: " + full)


def show_warning(title, text):
    QMessageBox.warning(None, title, text)


def request_confirmation(title, text):
    button = QMessageBox.question(None, title, text)
    print_debug(50, "You clicked " + str(button))
    print_debug(50, "Returning " + str(button == QMessageBox.StandardButton.Yes))
    return (button == QMessageBox.StandardButton.Yes)


def get_scale_val(scale_of_any_type):
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
        # else:
        #    print_debug ( 10, "Error converting " + str(scale_of_any_type) + " of unexpected type (" + str(type(scale)) + ") to a value." )
        #    traceback.print_stack()
    except:
        print_debug(1, "Error converting " + str(scale_of_any_type) + " to a value.")
        exi = sys.exc_info()
        print_debug(1, "  Exception type = " + str(exi[0]))
        print_debug(1, "  Exception value = " + str(exi[1]))
        print_debug(1, "  Exception traceback:")
        traceback.print_tb(exi[2])
        return -1


def get_scale_key(scale_val):
    # Create a key like "scale_#" from either an integer or a string
    s = str(scale_val)
    while s.startswith('scale_'):
        s = s[len('scale_'):]
    return 'scale_' + s


# NOTE this is REimplimented from alignem_swift, for use in generate_scales_queue
def get_best_path(file_path):
    return os.path.abspath(os.path.normpath(file_path))


# NOTE this is REimplimented from alignem_swift, for use in generate_scales_queue
def create_project_structure_directories(subdir_path):
    print('Creating project structure directories | create_project_structure_directories...')
    print('subdir_path = ', subdir_path)

    print("Creating a subdirectory named " + subdir_path)
    try:
        os.mkdir(subdir_path)
    except:
        print('Warning: Exception creating scale path (may already exist).')
        pass
    src_path = os.path.join(subdir_path, 'img_src')
    print('Creating source subsubdirectory named ' + src_path)
    try:
        os.mkdir(src_path)
    except:
        # NOTE: some lines of commented code here were discarded
        print('Warning: Exception creating "img_src" path (may already exist).')
        pass
    aligned_path = os.path.join(subdir_path, 'img_aligned')
    print('Creating aligned subdirectory named ' + aligned_path)
    try:
        os.mkdir(aligned_path)
    except:
        print('Warning: Exception creating "img_aligned" path (may already exist).')
        pass
    bias_data_path = os.path.join(subdir_path, 'bias_data')
    print('Creating bias subsubdirectory named ' + bias_data_path)
    try:
        os.mkdir(bias_data_path)
    except:
        print('Warning: Exception creating "bias_data" path (may already exist).')
        pass


# @profileit
# @dumpit
# @traceit
# @countit
# @timeit
# @traceit
def generate_scales_queue():
    print("Displaying define scales dialog to receive user input...")
    print("Trying to disconnect scales_combobox from all handlers...")
    try:
        self.scales_combobox.disconnect()
    except Exception:
        print(
            "BenignException: could not disconnect scales_combobox from handlers or nothing to disconnect. Continuing...")

    default_scales = ['1']

    cur_scales = [str(v) for v in sorted([get_scale_val(s) for s in project_data['data']['scales'].keys()])]
    if len(cur_scales) > 0:
        default_scales = cur_scales

    input_val, ok = QInputDialog().getText(None, "Define Scales",
                                           "Please enter your scaling factors separated by spaces." \
                                           "\n\nFor example, to generate 1x 2x and 4x scale datasets:" \
                                           "\n1 2 4\n\nYour current scales:\n" +
                                           str(' '.join(default_scales)),
                                           echo=QLineEdit.Normal,
                                           text=' '.join(default_scales))
    if ok:
        main_window.set_scales_from_string(input_val)

    else:
        print("Aborting. Scales were not generated.")
        return  # Want to exit function if no scales are defined

    print('Generating scales queue...')

    image_scales_to_run = [get_scale_val(s) for s in sorted(project_data['data']['scales'].keys())]

    print("  Generating images for these scales: " + str(image_scales_to_run))

    if (project_data['data']['destination_path'] == None) or (
            len(project_data['data']['destination_path']) <= 0):

        show_warning("Note", "Scales can not be generated without a destination (use File/Set Destination)")

    else:

        ### Create the queue here
        #      task_queue.DEBUG_LEVEL = DEBUG_LEVEL
        #      task_wrapper.DEBUG_LEVEL = DEBUG_LEVEL
        #      scaling_queue = task_queue.TaskQueue (sys.executable)
        #      cpus = psutil.cpu_count (logical=False)
        #      scaling_queue.start (cpus)
        #      scaling_queue.notify = False
        #      scaling_queue.passthrough_stdout = False
        #      scaling_queue.passthrough_stderr = False

        # Use task_queue_mp
        scaling_queue = task_queue.TaskQueue()
        cpus = psutil.cpu_count(logical=False)
        if cpus > 48:
            cpus = 48
        scaling_queue.start(cpus)  # cpus = 8 for my laptop

        for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'

            print("\nGenerating images for scale " + str(scale) + "\n")
            main_window.status.showMessage("Generating Scale " + str(scale) + " ...")

            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key

            subdir_path = os.path.join(project_data['data']['destination_path'], scale_key)
            scale_1_path = os.path.join(project_data['data']['destination_path'], 'scale_1')

            create_project_structure_directories(subdir_path)

            print("Generating images at each layer for key:", str(scale_key))

            for layer in project_data['data']['scales'][scale_key]['alignment_stack']:
                print("  Generating images for layer:",
                      str(project_data['data']['scales'][scale_key]['alignment_stack'].index(layer)))
                # Remove previously aligned images from panel ??

                # Copy (or link) the source images to the expected scale_key"/img_src" directory
                for role in layer['images'].keys():

                    # Only copy files for roles "ref" and "base"

                    if role in ['ref', 'base']:
                        print("  Generating images for role:", role)
                        base_file_name = layer['images'][role]['filename']
                        if base_file_name != None:
                            if len(base_file_name) > 0:
                                abs_file_name = os.path.abspath(base_file_name)
                                bare_file_name = os.path.split(abs_file_name)[1]
                                destination_path = os.path.abspath(project_data['data']['destination_path'])
                                outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                                if scale == 1:
                                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                                        # The paths are different so make the link
                                        try:
                                            print("UnLinking " + outfile_name)
                                            os.unlink(outfile_name)
                                        except:
                                            print("Error UnLinking " + outfile_name)
                                        try:
                                            print("Linking from " + abs_file_name + " to " + outfile_name)
                                            os.symlink(abs_file_name, outfile_name)
                                        except:
                                            print("Unable to link from " + abs_file_name + " to " + outfile_name)
                                            print("Copying file instead")
                                            # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                                            try:
                                                shutil.copy(abs_file_name, outfile_name)
                                            except:
                                                print(
                                                    "Unable to link or copy from " + abs_file_name + " to " + outfile_name)
                                else:
                                    try:
                                        # Do the scaling
                                        print(
                                            "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                                scale))

                                        if os.path.split(os.path.split(os.path.split(abs_file_name)[0])[0])[
                                            1].startswith('scale_'):
                                            # Convert the source from whatever scale is currently processed to scale_1
                                            p, f = os.path.split(abs_file_name)
                                            p, r = os.path.split(p)
                                            p, s = os.path.split(p)
                                            abs_file_name = os.path.join(p, 'scale_1', r, f)

                                        code_mode = 'c'  # force c code scaling implementation

                                        if code_mode == 'python':
                                            print(
                                                "generate_scales_queue > code_mode equals 'python' -> entering conditional...")
                                            scaling_queue.add_task(cmd=sys.executable,
                                                                   args=['single_scale_job.py', str(scale),
                                                                         str(abs_file_name), str(outfile_name)], wd='.')
                                        else:
                                            print(
                                                "generate_scales_queue > configuring platform-specific path to executables for C SWiFT-IR...")
                                            # Configure platform-specific path to executables for C SWiFT-IR
                                            my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
                                            my_system = platform.system()
                                            my_node = platform.node()
                                            print("my_path = ", my_path)
                                            print("my_system = ", my_system)
                                            print("my_node = ", my_node)
                                            if my_system == 'Darwin':
                                                iscale2_c = my_path + '../c/bin_darwin/iscale2'
                                            elif my_system == 'Linux':
                                                if '.tacc.utexas.edu' in my_node:
                                                    iscale2_c = my_path + '../c/bin_tacc/iscale2'
                                                else:
                                                    iscale2_c = my_path + '../c/bin_linux/iscale2'

                                            scale_arg = '+%d' % (scale)
                                            outfile_arg = 'of=%s' % (outfile_name)
                                            infile_arg = '%s' % (abs_file_name)
                                            #                        scaling_queue.add_task (cmd=iscale2_c, args=[scale_arg, outfile_arg, infile_arg], wd='.')
                                            scaling_queue.add_task([iscale2_c, scale_arg, outfile_arg, infile_arg])

                                        # These two lines generate the scales directly rather than through the queue
                                        # img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                                        # align_swiftir.swiftir.saveImage ( img, outfile_name )

                                        # Change the base image for this scale to the new file
                                        layer['images'][role]['filename'] = outfile_name
                                    except:
                                        print_debug(1,
                                                    "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                                        scale))
                                        # print_exception()

                                # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                                print_debug(40, "  Original File Name: " + str(layer['images'][role]['filename']))
                                layer['images'][role]['filename'] = outfile_name
                                print_debug(40, "  Updated  File Name: " + str(layer['images'][role]['filename']))

        ### Join the queue here to ensure that all have been generated before returning
        #      scaling_queue.work_q.join() # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
        t0 = time.time()
        scaling_queue.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
        dt = time.time() - t0
        print("Generate Scales Completed in %.2f seconds" % (dt))

        # Stop the queue
        #      scaling_queue.shutdown()
        scaling_queue.stop()
        del scaling_queue

        #main_window.reload_scales_combobox() #may not need this here
        main_window.center_all_images()

        print("Reloading scales_combobox...")
        main_window.reload_scales_combobox()

        print("Connecting scales_combobox to fn_scales_combobox handler...")
        main_window.scales_combobox.currentTextChanged.connect(main_window.fn_scales_combobox)

        print("Generating scales complete.")
        main_window.status.showMessage("Generating scales complete.")


# Load the image
def load_image_worker(real_norm_path, image_dict):
    print_debug(50, "load_image_worker started with:", str(real_norm_path))
    image_dict['image'] = QPixmap(real_norm_path)
    image_dict['loaded'] = True
    image_dict['loading'] = False
    print_debug(50, "load_image_worker finished for:" + str(real_norm_path))
    image_library.print_load_status()


class ImageLibrary:
    """A class containing multiple images keyed by their file name."""

    def __init__(self):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey(self, file_path):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def print_load_status(self):
        print_debug(50, " Library has " + str(len(self._images.keys())) + " images")
        print_debug(50, "  Names:   " + str(sorted([str(s[-7:]) for s in self._images.keys()])))
        print_debug(50, "  Loaded:  " + str(
            sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loaded']])))
        print_debug(50, "  Loading: " + str(
            sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loading']])))

    def __str__(self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        keys = sorted(self._images.keys())
        for k in keys:
            v = self._images[k]
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"
        # print ( s )
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return (s)

    def get_image_reference(self, file_path):
        # print("Getting image reference | Caller: " + inspect.stack()[1].function + " |  ImageLibrary.get_image_reference")
        print_debug(50, "get_image_reference ( " + str(file_path) + " )")
        self.print_load_status()
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                print_debug(50, "  Image name is in the library")
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    print_debug(50, "  Image was already loaded")
                    image_ref = self._images[real_norm_path]['image']
                elif self._images[real_norm_path]['loading']:
                    # The image is still loading, so wait for it to complete
                    print_debug(4, "  Image still loading ... wait")
                    self._images[real_norm_path]['task'].join()
                    self._images[real_norm_path]['task'] = None
                    self._images[real_norm_path]['loaded'] = True
                    self._images[real_norm_path]['loading'] = False
                    image_ref = self._images[real_norm_path]['image']
                else:
                    print_debug(3, "  Load Warning for: \"" + str(real_norm_path) + "\"")
                    image_ref = self._images[real_norm_path]['image']
            else:
                # The image is not in the library at all, so force a load now (and wait)
                print_debug(4, "  Forced load of image: \"" + str(real_norm_path) + "\"")
                self._images[real_norm_path] = {'image': QPixmap(real_norm_path), 'loaded': True, 'loading': False,
                                                'task': None}
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    # Caller = paintEvent. Loads each image.
    def get_image_reference_if_loaded(self, file_path):
        # print("Getting image reference if loaded | Caller: " + inspect.stack()[1].function + " |  ImageLibrary.get_image_reference_if_loaded")
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    image_ref = self._images[real_norm_path]['image']
                elif self._images[real_norm_path]['loading']:
                    # The image is still loading, so wait for it to complete
                    self._images[real_norm_path]['task'].join()
                    self._images[real_norm_path]['task'] = None
                    self._images[real_norm_path]['loaded'] = True
                    self._images[real_norm_path]['loading'] = False
                    image_ref = self._images[real_norm_path]['image']
                else:
                    print_debug(5, "  Load Warning for: \"" + str(real_norm_path) + "\"")
                    image_ref = self._images[real_norm_path]['image']
        return image_ref

    def remove_image_reference(self, file_path):
        print("  ImageLayer is removing image reference (called by " + inspect.stack()[1].function + ")...")
        image_ref = None
        if not (file_path is None):
            real_norm_path = self.pathkey(file_path)
            if real_norm_path in self._images:
                # print_debug ( 4, "ImageLibrary > remove_image_reference... Unloading image: \"" + real_norm_path + "\"" )
                image_ref = self._images.pop(real_norm_path)['image']
        # This returned value may not be valid when multi-threading is implemented
        return image_ref

    def queue_image_read(self, file_path):
        # print("Queuing image read | Caller: " + inspect.stack()[1].function + " |  ImageLibrary.queue_image_read")
        real_norm_path = self.pathkey(file_path)
        print_debug(30, "  start queue_image_read with: \"" + str(real_norm_path) + "\"")
        self._images[real_norm_path] = {'image': None, 'loaded': False, 'loading': True, 'task': None}
        t = threading.Thread(target=load_image_worker, args=(real_norm_path, self._images[real_norm_path]))
        t.start()
        self._images[real_norm_path]['task'] = t
        print_debug(30, "  finished queue_image_read with: \"" + str(real_norm_path) + "\"")

    def make_available(self, requested):
        print('  ImageLibrary.make_available called by ' + inspect.stack()[1].function + '...')

        #tag #memo
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        print("  making available: " + str(sorted([str(s[-7:]) for s in requested])))
        already_loaded = set(self._images.keys())
        normalized_requested = set([self.pathkey(f) for f in requested])
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference(f)
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read(f)  # Using this will enable threaded reading behavior
            else:
                self.get_image_reference(f)  # Using this will force sequential reading behavior

        self.print_load_status()
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def remove_all_images(self):
        print("ImageLibrary is removing all images (called by " + inspect.stack()[1].function + ")...")
        keys = list(self._images.keys())
        for k in keys:
            self.remove_image_reference(k)
        self._images = {}

    def update(self):
        pass


def image_completed_loading(par):
    print('\n' + 100 * '$' + '\n' + 100 * '$')
    print("Got: " + str(par))
    print("Image completed loading, check if showing and repaint as needed.")
    ## The following is needed to auto repaint, but it crashes instantly.
    ##main_window.image_panel.refresh_all_images()
    print('\n' + 100 * '$' + '\n' + 100 * '$')


def image_loader(real_norm_path, image_dict):
    try:
        # Load the image
        print_debug(5, "  image_loader started with: \"" + str(real_norm_path) + "\"")
        m = psutil.virtual_memory()
        print_debug(5, "    memory available before loading = " + str(m.available))
        image_dict['image'] = QPixmap(real_norm_path)
        image_dict['loaded'] = True
        print_debug(5, "  image_loader finished for: \"" + str(real_norm_path) + "\"")
        print_debug(5, "    memory available after loading = " + str(m.available))
    except:
        print("Got an exception in image_loader")


class SmartImageLibrary:
    """A class containing multiple images keyed by their file name."""

    def __init__(self):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True
        self.initial_memory = psutil.virtual_memory()
        self.prev_scale_val = None
        self.prev_layer_index = None
        self.executors = concurrent.futures.ThreadPoolExecutor(
            max_workers=None)  # Should default to 5 times number of processors

    def pathkey(self, file_path):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def __str__(self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        for k, v in self._images.items():
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"
        print(s)
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return ("ImageLibrary contains ...")

    def remove_image_reference(self, file_path):
        # Do nothing since the smart image library now makes this decision internally
        pass

    def remove_all_images(self):
        # Do nothing since the smart image library now makes this decision internally
        pass

    def get_image_reference(self, file_path):
        print("Getting image reference | Caller: " + inspect.stack()[
            1].function + " |  SmartImageLibrary.get_image_reference")
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    image_ref = self._images[real_norm_path]['image']
                else:
                    # The image is still loading, so return None
                    image_ref = None
            else:
                # The image is not in the library at all, so start loading it now (but don't wait)
                print_debug(5, "  Begin loading image: \"" + str(real_norm_path) + "\"")
                self.queue_image_read(real_norm_path)
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    def get_image_reference_if_loaded(self, file_path):
        print("Getting image reference if loaded | Caller: " + inspect.stack()[
            1].function + " |  SmartImageLibrary.get_image_reference_if_loaded")
        return self.get_image_reference(file_path)

    def queue_image_read(self, file_path):
        print("Queuing image read | Caller: " + inspect.stack()[1].function + " |  SmartImageLibrary.queue_image_read")
        print("top of queue_image_read ( " + file_path + ")")
        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = {'image': None, 'loaded': False, 'loading': True, 'task': None}
        print("submit with (" + real_norm_path + ", " + str(self._images[real_norm_path]) + ")")
        task_future = self.executors.submit(image_loader, real_norm_path, self._images[real_norm_path])
        task_future.add_done_callback(image_completed_loading)
        print("  task_future: " + str(task_future))
        self._images[real_norm_path]['task'] = task_future

    def make_available(self, requested):
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        print_debug(25, "make_available: " + str(sorted([str(s[-7:]) for s in requested])))
        already_loaded = set(self._images.keys())
        normalized_requested = set([self.pathkey(f) for f in requested])
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference(f)
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read(f)  # Using this will enable threaded reading behavior
            else:
                self.get_image_reference(f)  # Using this will force sequential reading behavior

        print_debug(25, "Library has " + str(len(self._images.keys())) + " images")
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def update(self):
        print("SmartImageLibrary is updating | Caller: " + inspect.stack()[
            1].function + " |  SmartImageLibrary.queue_image_read")
        cur_scale_key = project_data['data']['current_scale']
        cur_scale_val = get_scale_val(cur_scale_key)
        cur_layer_index = project_data['data']['current_layer']
        scale_keys = sorted(project_data['data']['scales'].keys())
        scale_vals = sorted(get_scale_val(scale_key) for scale_key in scale_keys)
        cur_stack = project_data['data']['scales'][cur_scale_key]['alignment_stack']
        layer_nums = range(len(cur_stack))
        amem = psutil.virtual_memory().available
        print("Looking at: scale " + str(cur_scale_val) + " in " + str(scale_vals) + ", layer " + str(
            cur_layer_index) + " in " + str(layer_nums) +
              ", Available Memory = " + str(amem) + " out of " + str(self.initial_memory.available))

        try:
            stack = project_data['data']['scales'][project_data['data']['current_scale']]['alignment_stack']
            layer = stack[project_data['data']['current_layer']]
            for k in layer['images'].keys():
                print("Loading role " + k)
                try:
                    fn = layer['images'][k]['filename']
                    if (fn != None) and (len(fn) > 0):
                        print("Loading file " + fn)
                        self.queue_image_read(fn)
                except:
                    pass
        except:
            pass

        self.prev_scale_val = cur_scale_val
        self.prev_layer_index = cur_layer_index


image_library = ImageLibrary()


class ZoomPanWidget(QWidget):
    """A widget to display a single annotated image with zooming and panning."""

    def __init__(self, role, parent=None):
        super(ZoomPanWidget, self).__init__(parent)
        print("ZoomPanWidget constructor called.")
        self.role = role

        self.parent = None
        self.already_painting = False

        self.floatBased = False
        self.antialiased = False  # why
        self.wheel_index = 0
        self.scroll_factor = 1.25
        self.zoom_scale = 1.0
        self.last_button = Qt.MouseButton.NoButton

        self.mdx = 0  # Mouse Down x (screen x of mouse down at start of drag)
        self.mdy = 0  # Mouse Down y (screen y of mouse down at start of drag)
        self.ldx = 0  # Last dx (fixed while dragging)
        self.ldy = 0  # Last dy (fixed while dragging)
        self.dx = 0  # Offset in x of the image
        self.dy = 0  # Offset in y of the image

        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False

        self.setAutoFillBackground(True)
        self.setContentsMargins(0, 0, 0, 0)

        self.setAutoFillBackground(True)
        self.border_color = QColor(100, 100, 100, 255)

        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)

        self.setToolTip('GlanceEM_SWiFT')  # tooltip #settooltip
        # tooltip.setTargetWidget(btn)
        #
        # self.lb = QLabel(self)
        # self.pixmap = QPixmap("{sims.png}")
        # self.height_label = 100
        # self.lb.resize(self.width(), self.height_label)
        # self.lb.setPixmap(self.pixmap.scaled(self.lb.size(), Qt.IgnoreAspectRatio))
        # self.show()

        # focus
        # QApplication.instance().focusChanged.connect(self.on_focusChanged)

    # def on_focusChanged(self):
    #     fwidget = QApplication.focusWidget()
    #     if fwidget is not None:
    #         print("focus widget name = ", fwidget.objectName())

    def get_settings(self):
        settings_dict = {}
        for key in ["floatBased", "antialiased", "wheel_index", "scroll_factor", "zoom_scale", "last_button", "mdx",
                    "mdy", "ldx", "ldy", "dx", "dy", "draw_border", "draw_annotations", "draw_full_paths"]:
            settings_dict[key] = self.__dict__[key]
        return settings_dict

    def set_settings(self, settings_dict):
        for key in settings_dict.keys():
            self.__dict__[key] = settings_dict[key]

    def set_parent(self, parent):
        self.parent = parent

    def update_siblings(self):
        # This will cause the normal "update_self" function to be called on each sibling
        print_debug(30, "Update_siblings called, calling siblings.update_self")
        if type(self.parent) == MultiImagePanel:
            print_debug(60, "Child of MultiImagePanel")
            self.parent.update_multi_self(exclude=[self])

    def update_zpa_self(self):
        # print('Updating zpa self | Caller: ' + inspect.stack()[1].function + ' |  ZoomPanWidget.update_zpa_self...')
        # Call the super "update" function for this panel's QWidget (this "self")
        if self.parent != None:
            self.draw_border = self.parent.draw_border
            self.draw_annotations = self.parent.draw_annotations
            self.draw_full_paths = self.parent.draw_full_paths
        super(ZoomPanWidget, self).update()

        if get_cur_snr() is None:
            self.setToolTip(str(get_cur_scale()) + '\n' + "Unaligned")  # tooltip #settooltip
        else:
            self.setToolTip(str(get_cur_scale()) + '\n' + str(get_cur_snr()))  # tooltip #settooltip

    def show_actual_size(self):
        print("Showing actual size | ZoomPanWidget.show_actual_size...")

        print_debug(30, "Showing actual size image for role " + str(self.role))
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        # self.zoom_to_wheel_at ( 0, 0 ) #pyside2
        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
        clear_crop_settings()

    def center_image(self, all_images_in_stack=True):
        # print("  ZoomPanWidget is centering image for " + str(self.role))

        if project_data != None:
            s = get_cur_scale()
            l = project_data['data']['current_layer']

            if len(project_data['data']['scales']) > 0:
                if len(project_data['data']['scales'][s]['alignment_stack']) > 0:

                    image_dict = project_data['data']['scales'][s]['alignment_stack'][l]['images']

                    if self.role in image_dict.keys():
                        ann_image = image_dict[self.role]
                        pixmap = image_library.get_image_reference(ann_image['filename'])
                        if (pixmap != None) or all_images_in_stack:
                            img_w = 0
                            img_h = 0
                            if pixmap != None:
                                img_w = pixmap.width()
                                img_h = pixmap.height()
                            win_w = self.width()
                            win_h = self.height()
                            if all_images_in_stack:
                                # Search through all images in this stack to find bounds
                                stack = project_data['data']['scales'][s]['alignment_stack']
                                for layer in stack:
                                    if 'images' in layer.keys():
                                        if self.role in layer['images'].keys():
                                            other_pixmap = image_library.get_image_reference_if_loaded(
                                                layer['images'][self.role]['filename'])
                                            if other_pixmap != None:
                                                other_w = other_pixmap.width()
                                                other_h = other_pixmap.height()
                                                img_w = max(img_w, other_w)
                                                img_h = max(img_h, other_h)

                            if (img_w <= 0) or (img_h <= 0) or (win_w <= 0) or (
                                    win_h <= 0):  # Zero or negative dimensions might lock up?
                                print(
                                    "Warning: Image or Window dimension is zero - cannot center image for role \"" + str(
                                        self.role) + "\"")

                            else:
                                # Start with the image at a zoom of 1 (natural size) and with the mouse wheel centered (at 0)
                                self.zoom_scale = 1.0
                                self.ldx = 0
                                self.ldy = 0
                                self.wheel_index = 0
                                # self.zoom_to_wheel_at ( 0, 0 )

                                # Enlarge the image (scaling up) while it is within the size of the window
                                while (self.win_x(img_w) <= win_w) and (self.win_y(img_h) <= win_h):
                                    print_debug(70, "Enlarging image to fit in center.")
                                    # self.zoom_to_wheel_at ( 0, 0 ) #pyside2
                                    self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                    self.wheel_index += 1
                                    print_debug(80, "  Wheel index = " + str(self.wheel_index) + " while enlarging")
                                    print_debug(80,
                                                "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(
                                                    win_w) + "x" + str(win_h))
                                    print_debug(80, "    self.win_x(img_w) = " + str(
                                        self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                    if abs(self.wheel_index) > 100:
                                        print_debug(-1, "Magnitude of Wheel index > 100, wheel_index = " + str(
                                            self.wheel_index))
                                        break

                                # Shrink the image (scaling down) while it is larger than the size of the window
                                while (self.win_x(img_w) > win_w) or (self.win_y(img_h) > win_h):
                                    print_debug(70, "Shrinking image to fit in center.")
                                    # self.zoom_to_wheel_at ( 0, 0 ) #pyside2
                                    self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                    self.wheel_index += -1
                                    print_debug(80, "  Wheel index = " + str(self.wheel_index) + " while shrinking")
                                    print_debug(80,
                                                "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(
                                                    win_w) + "x" + str(win_h))
                                    print_debug(80, "    self.win_x(img_w) = " + str(
                                        self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                    if abs(self.wheel_index) > 100:
                                        print_debug(-1, "Magnitude of Wheel index > 100, wheel_index = " + str(
                                            self.wheel_index))
                                        break

                                # Adjust the offsets to center
                                extra_x = win_w - self.win_x(img_w)
                                extra_y = win_h - self.win_y(img_h)

                                # Bias the y value downward to make room for text at top
                                extra_y = 1.7 * extra_y
                                self.ldx = (extra_x / 2) / self.zoom_scale
                                self.ldy = (extra_y / 2) / self.zoom_scale
        clear_crop_settings()
        # print("  Done centering image for " + str(self.role) )

    def win_x(self, image_x):
        return self.zoom_scale * (image_x + self.ldx + self.dx)

    def win_y(self, image_y):
        return self.zoom_scale * (image_y + self.ldy + self.dy)

    def image_x(self, win_x):
        img_x = (win_x / self.zoom_scale) - self.ldx
        return img_x

    def image_y(self, win_y):
        img_y = (win_y / self.zoom_scale) - self.ldy
        return img_y

    def dump(self):
        print_debug(30, "wheel = " + str(self.wheel_index))
        print_debug(30, "zoom = " + str(self.zoom_scale))
        print_debug(30, "ldx  = " + str(self.ldx))
        print_debug(30, "ldy  = " + str(self.ldy))
        print_debug(30, "mdx  = " + str(self.mdx))
        print_debug(30, "mdy  = " + str(self.mdy))
        print_debug(30, " dx  = " + str(self.dx))
        print_debug(30, " dy  = " + str(self.dy))

    def setFloatBased(self, float_based):
        self.floatBased = float_based
        self.update_zpa_self()

    def setAntialiased(self, antialiased):
        self.antialiased = antialiased
        self.update_zpa_self()

    # minimum #windowsize #qsize
    def minimumSizeHint(self):
        # return QSize(50, 50)
        return QSize(250, 250)

    def sizeHint(self):
        return QSize(180, 180)

    def mousePressEvent(self, event):
        global crop_mode_origin
        global crop_mode_role
        global crop_mode_disp_rect
        global crop_mode_callback
        crop_mode_role = None
        crop_mode_disp_rect = None
        crop_mode = False
        mode = None
        if crop_mode_callback != None:
            mode = crop_mode_callback()
            if mode == 'Crop':
                crop_mode = True
            else:
                # Note: since we don't currently have a callback from a mode change,
                #  remove the crop box upon any mouse click.
                if crop_mode_origin != None:
                    # Remove the box and force a redraw
                    crop_mode_origin = None
                    crop_mode_disp_rect = None
                    crop_mode_role = None
                    self.update_zpa_self()
                    self.update_siblings()

        if crop_mode:
            crop_mode_role = self.role
            ### New Rubber Band Code
            crop_mode_origin = event.pos()
            ex = event.x()
            ey = event.y()
            print_debug(60, "Current Mode = " + str(mode) + ", crop_mode_origin is " + str(
                crop_mode_origin) + ", (x,y) is " + str([ex, ey]) + ", wxy is " + str(
                [self.image_x(ex), self.image_y(ey)]))
            if not self.rubberBand:
                self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
            self.rubberBand.setGeometry(QRect(crop_mode_origin, QSize()))
            self.rubberBand.show()
            self.update_siblings()
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        else:
            event_handled = False

            ex = event.x()
            ey = event.y()

            if main_window.mouse_down_callback != None:
                event_handled = main_window.mouse_down_callback(self.role, (ex, ey),
                                                                (self.image_x(ex), self.image_y(ey)),
                                                                int(event.button()))

            if not event_handled:

                self.last_button = event.button()
                if event.button() == Qt.MouseButton.RightButton:
                    # Resest the pan and zoom
                    self.dx = self.mdx = self.ldx = 0
                    self.dy = self.mdy = self.ldy = 0
                    self.wheel_index = 0
                    self.zoom_scale = 1.0
                elif event.button() == Qt.MouseButton.MiddleButton:
                    self.dump()
                else:
                    # Set the Mouse Down position to be the screen location of the mouse
                    self.mdx = ex
                    self.mdy = ey

            self.update_zpa_self()

    def mouseMoveEvent(self, event):
        global crop_mode_origin
        global crop_mode_role
        global crop_mode_disp_rect
        global crop_mode_callback

        crop_mode = False
        # print("crop_mode = ", crop_mode)
        if crop_mode_callback != None:
            mode = crop_mode_callback()  #bug
            if mode == 'Crop':
                print("    => True")
                crop_mode = True
            else:
                # Note: since we don't currently have a callback from a mode change,
                #  try to remove the crop box upon mouse motion. However, this will
                #  require enabling all mouse motion events (not just with buttons).
                if crop_mode_origin != None:
                    # Remove the box and force a redraw
                    crop_mode_origin = None
                    crop_mode_disp_rect = None
                    crop_mode_role = None
                    self.update_zpa_self()
                    self.update_siblings()

        if crop_mode:
            ### New Rubber Band Code
            print_debug(60, "Move: Current Mode = " + str(mode) + ", crop_mode_origin is " + str(
                crop_mode_origin) + ", mouse is " + str(event.pos()))
            if crop_mode_origin != None:
                self.rubberBand.setGeometry(QRect(crop_mode_origin, event.pos()).normalized())
        else:
            event_handled = False

            if main_window.mouse_move_callback != None:
                event_handled = main_window.mouse_move_callback(self.role, (0, 0), (0, 0),
                                                                int(event.button()))  # These will be ignored anyway for now

            if not event_handled:

                if self.last_button == Qt.MouseButton.LeftButton:
                    self.dx = (event.x() - self.mdx) / self.zoom_scale
                    self.dy = (event.y() - self.mdy) / self.zoom_scale
                    self.update_zpa_self()

    def mouseReleaseEvent(self, event):
        widget = QApplication.focusWidget()
        # print("!!! FOCUS IS ON: ",widget) #focus

        global crop_mode_origin
        global crop_mode_role
        global crop_mode_disp_rect
        global crop_mode_corners
        global crop_mode_callback

        global crop_window_mode  # mouse_rectangle or mouse_square or fixed
        global crop_window_width
        global crop_window_height

        crop_mode = False
        if crop_mode_callback != None:
            mode = crop_mode_callback()
            if mode == 'Crop':
                crop_mode = True
        if crop_mode:
            self.rubberBand.hide()
            if crop_mode_origin != None:

                print_debug(50, "Mouse drawn from (" + str(crop_mode_origin.x()) + "," + str(
                    crop_mode_origin.y()) + ") to (" + str(event.x()) + "," + str(event.y()) + ")")
                print_debug(50, "Cropping with mode: " + str(crop_window_mode))

                if crop_window_mode == 'mouse_rectangle':

                    # Convert to image coordinates
                    img_orig_x = self.image_x(crop_mode_origin.x())
                    img_orig_y = self.image_y(crop_mode_origin.y())
                    img_rel_x = self.image_x(event.x())
                    img_rel_y = self.image_y(event.y())

                    # Save the cropping corners for the actual cropping which is done later
                    crop_mode_corners = [[img_orig_x, img_orig_y], [img_rel_x, img_rel_y]]
                    print_debug(50, "Crop Corners: " + str(crop_mode_corners))  ### These appear to be correct

                    # Convert the crop_mode_corners from image mode back into screen mode for crop_mode_disp_rect
                    crop_w = img_orig_x + self.image_x(event.x() - crop_mode_origin.x())
                    crop_h = img_orig_y + self.image_y(event.y() - crop_mode_origin.y())
                    crop_mode_disp_rect = [[img_orig_x, img_orig_y], [crop_w, crop_h]]

                elif crop_window_mode == 'mouse_square':

                    # Convert to image coordinates:
                    img_orig_x = self.image_x(crop_mode_origin.x())
                    img_orig_y = self.image_y(crop_mode_origin.y())
                    img_rel_x = self.image_x(event.x())
                    img_rel_y = self.image_y(event.y())

                    # Find the center of the selected region in image coordinates (might be a single point)
                    img_ctr_x = (img_orig_x + img_rel_x) / 2.0
                    img_ctr_y = (img_orig_y + img_rel_y) / 2.0

                    # Find the width and height and the square root of the equivalent area
                    img_width = abs(img_rel_x - img_orig_x)
                    img_height = abs(img_rel_y - img_orig_y)
                    area = img_width * img_height
                    img_side = int(round(math.sqrt(area)))
                    print_debug(30, "Cropped image will be " + str(img_side) + "x" + str(img_side))

                    # Compute the upper left and lower right corners in image coordinates
                    img_p0_x = img_ctr_x - (img_side / 2)
                    img_p0_y = img_ctr_y - (img_side / 2)
                    img_p1_x = img_p0_x + img_side
                    img_p1_y = img_p0_y + img_side

                    # Save the cropping corners for the actual cropping which is done later
                    crop_mode_corners = [[img_p0_x, img_p0_y], [img_p1_x, img_p1_y]]
                    print_debug(50, "Crop Corners: " + str(crop_mode_corners))  ### These appear to be correct

                    # Convert the crop_mode_corners from image mode back into screen mode for crop_mode_disp_rect
                    crop_w = img_p0_x + self.image_x(self.win_x(img_p1_x) - self.win_x(img_p0_x))
                    crop_h = img_p0_y + self.image_y(self.win_y(img_p1_y) - self.win_y(img_p0_y))
                    crop_mode_disp_rect = [[img_p0_x, img_p0_y], [crop_w, crop_h]]

                elif crop_window_mode == 'mouse_center_fixed':

                    # Convert to image coordinates:
                    img_orig_x = self.image_x(crop_mode_origin.x())
                    img_orig_y = self.image_y(crop_mode_origin.y())
                    img_rel_x = self.image_x(event.x())
                    img_rel_y = self.image_y(event.y())

                    # Calculate the center of selection in image coordinates
                    img_ctr_x = (img_orig_x + img_rel_x) / 2.0
                    img_ctr_y = (img_orig_y + img_rel_y) / 2.0

                    # Calculate the image width (just the original fixed value)
                    img_width = float(crop_window_width)
                    img_height = float(crop_window_height)

                    # Calculate the corners of the rectangle in image coordinates
                    img_p0_x = img_ctr_x - (img_width / 2)
                    img_p0_y = img_ctr_y - (img_height / 2)
                    img_p1_x = img_p0_x + img_width
                    img_p1_y = img_p0_y + img_height

                    # Save the cropping corners for the actual cropping which is done later
                    crop_mode_corners = [[img_p0_x, img_p0_y], [img_p1_x, img_p1_y]]
                    print_debug(50, "Crop Corners: " + str(crop_mode_corners))  ### These appear to be correct

                    # Convert the crop_mode_corners from image mode back into screen mode for crop_mode_disp_rect
                    crop_w = img_p0_x + self.image_x(self.win_x(img_p1_x) - self.win_x(img_p0_x))
                    crop_h = img_p0_y + self.image_y(self.win_y(img_p1_y) - self.win_y(img_p0_y))
                    crop_mode_disp_rect = [[img_p0_x, img_p0_y], [crop_w, crop_h]]

                self.update_zpa_self()
                self.update_siblings()

        else:

            if event.button() == Qt.MouseButton.LeftButton:
                self.ldx = self.ldx + self.dx
                self.ldy = self.ldy + self.dy
                self.dx = 0
                self.dy = 0
                self.update_zpa_self()

    def mouseDoubleClickEvent(self, event):
        print_debug(50, "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()))
        self.update_zpa_self()

    # def zoom_to_wheel_at ( self, mouse_win_x, mouse_win_y ): #pyside2
    def zoom_to_wheel_at(self, position):  # pyside6, position has type PySide6.QtCore.QPoint
        clear_crop_settings()
        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow(self.scroll_factor, self.wheel_index)

        # self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale) #pyside2
        # self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale) #pyside2

        self.ldx = self.ldx + (position.x() / new_scale) - (position.x() / old_scale)
        self.ldy = self.ldy + (position.y() / new_scale) - (position.y() / old_scale)

    def change_layer(self, layer_delta):
        """This function iterates the current layer"""

        # print("Changing layer (ZoomPanWidget.change_layer)...")
        global project_data
        global main_window
        global preloading_range

        #scale = project_data['data']['scales'][project_data['data']['current_scale']]
        # layer = scale['alignment_stack'][project_data['data']['current_layer']]
        # base_file_name = layer['images']['base']['filename']
        # print('base file name = ', base_file_name)
        # print("current layer =", scale['alignment_stack'][project_data['data']['current_layer']])
        # print("\nsetting toggle to: ", not scale['alignment_stack'][project_data['data']['current_layer']]['skip'])
        #main_window.toggle_skip.setChecked(not scale['alignment_stack'][project_data['data']['current_layer']]['skip'])

        # print("  show_skipped_images = ", show_skipped_images)

        if not show_skipped_images:

            # Try to juggle the layer delta to avoid any skipped images

            scale_key = project_data['data']['current_scale']
            stack = project_data['data']['scales'][scale_key]['alignment_stack']

            layer_index = project_data['data']['current_layer']
            new_layer_index = layer_index + layer_delta
            while (new_layer_index >= 0) and (new_layer_index < len(stack)):
                print_debug(30, "Looking for next non-skipped image")
                if stack[new_layer_index]['skip'] == False:  # skip
                    break
                new_layer_index += layer_delta
            if (new_layer_index >= 0) and (new_layer_index < len(stack)):
                # Found a layer that's not skipped, so set the layer delta for the move
                layer_delta = new_layer_index - layer_index
            else:
                # Could not find a layer that's not skipped in that direction, try going the other way
                layer_index = project_data['data']['current_layer']
                new_layer_index = layer_index
                while (new_layer_index >= 0) and (new_layer_index < len(stack)):
                    print_debug(30, "Looking for next non-skipped image")
                    if stack[new_layer_index]['skip'] == False:  # skip
                        break
                    new_layer_index += -layer_delta
                if (new_layer_index >= 0) and (new_layer_index < len(stack)):
                    # Found a layer that's not skipped, so set the layer delta for the move
                    layer_delta = new_layer_index - layer_index
                else:
                    # Could not find a layer that's not skipped in either direction, stay here
                    layer_delta = 0

        if project_data != None:

            if main_window.view_change_callback != None:

                leaving_layer = project_data['data']['current_layer']
                entering_layer = project_data['data']['current_layer'] + layer_delta

                if entering_layer < 0:
                    entering_layer = 0

                try:
                    leaving_scale = get_cur_scale()
                    entering_scale = get_cur_scale()
                    main_window.view_change_callback(get_scale_key(leaving_scale), get_scale_key(entering_scale),
                                                     leaving_layer, entering_layer)
                except:
                    print_debug(0, "Exception in change_layer: " + str(sys.exc_info()))

            local_scales = project_data['data']['scales']  # This will be a dictionary keyed with "scale_#" keys
            local_cur_scale = get_cur_scale()
            if local_cur_scale in local_scales:
                local_scale = local_scales[local_cur_scale]
                if 'alignment_stack' in local_scale:
                    local_stack = local_scale['alignment_stack']
                    if len(local_stack) <= 0:
                        project_data['data']['current_layer'] = 0
                    else:
                        # Adjust the current layer
                        local_current_layer = project_data['data']['current_layer']
                        local_current_layer += layer_delta
                        # Apply limits (top and bottom of stack)
                        if local_current_layer >= len(local_stack):
                            local_current_layer = len(local_stack) - 1
                        elif local_current_layer < 0:
                            local_current_layer = 0
                        # Store the final value in the shared "JSON"
                        project_data['data']['current_layer'] = local_current_layer

                        # Define the images needed
                        needed_images = set()
                        for i in range(len(local_stack)):
                            if abs(i - local_current_layer) < preloading_range:
                                for role, local_image in local_stack[i]['images'].items():
                                    if local_image['filename'] != None:
                                        if len(local_image['filename']) > 0:
                                            needed_images.add(local_image['filename'])
                        # Ask the library to keep only those images
                        image_library.make_available(needed_images)

            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

            # if len(project_data['data']['scales'][local_current_layer]

            image_library.update()

            self.update_zpa_self()
            self.update_siblings()

            self.center_image()  # centering the image sooner may prevent glitch

            scale = project_data['data']['scales'][project_data['data']['current_scale']]
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
            base_file_name = layer['images']['base']['filename']
            print('  base file name = ', base_file_name)
            # print("\nsetting toggle to: ", not scale['alignment_stack'][project_data['data']['current_layer']]['skip'])
            main_window.toggle_skip.setChecked(
                not scale['alignment_stack'][project_data['data']['current_layer']]['skip'])

            scale = project_data['data']['scales'][
                project_data['data']['current_scale']]  # print(scale) # returns massive wall of text
            layer = scale['alignment_stack'][project_data['data']['current_layer']]

            # fix?
            if get_cur_snr() is not None:
                print("Trying to set whitening_input combobox value...")
                main_window.whitening_input.setText(str(
                    scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method'][
                        'method_data']['whitening_factor']))
                print("Trying to set swim_input combobox value...")
                main_window.swim_input.setText(str(
                    scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method'][
                        'method_data']['win_scale_factor']))

    def wheelEvent(self, event):
        """
        AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'delta'

        PySide6 error with scroll. PySide6 has angleDelta() and pixelDelta() - in place of delta()

        I think delta() is comparable to angleDelta()

        PySide2.QtGui.QWheelEvent.delta() has been deprecated, use pixelDelta() or angleDelta() instead
        PySide2.QtGui.QWheelEvent.delta() returns 'int'

        PySide6.QtGui.QWheelEvent.angleDelta() returns PySide6.QtCore.QPoint
        PySide6.QtGui.QWheelEvent.pixelDelta() returns PySide6.QtCore.QPoint

        PySide6 Ref: https://doc.qt.io/qtforpython/PySide6/QtGui/QWheelEvent.html
        Wheel events are sent to the widget under the mouse cursor, but if that widget does not handle the event they
        are sent to the focus widget. Wheel events are generated for both mouse wheels and trackpad scroll gestures. T
        There are two ways to read the wheel event delta:
          angleDelta() returns the deltas in wheel degrees (wheel rotation angle)
          pixelDelta() returns the deltas in screen pixels, (scrolling distance) and is available on platforms that have high-resolution trackpads, such as macOS
        PySide6.QtCore.QPoint


        other QWheelEvent notes:
          position() and globalPosition() return the mouse cursor’s location at the time of the event
          You should call ignore() if you do not handle the wheel event; this ensures that it will be sent to the parent widget
          The setEnabled() function can be used to enable or disable mouse and keyboard events for a widget.

        # Ref on resolving deprecation issue:
        https://stackoverflow.com/questions/66268136/how-to-replace-the-deprecated-function-qwheeleventdelta-in-the-zoom-in-z
        # zoom: want use angleDelta().y() for vertical scrolling

        """

        global project_data
        global main_window
        global preloading_range

        kmods = event.modifiers()
        if (int(kmods) & int(Qt.ShiftModifier)) == 0:

            # Unshifted Scroll Wheel moves through layers

            # layer_delta = int(event.delta()/120)    #pyside2
            layer_delta = int(event.angleDelta().y() / 120)  # pyside6

            self.change_layer(layer_delta)

            # Ref: https://stackoverflow.com/questions/35508711/how-to-enable-pan-and-zoom-in-a-qgraphicsview
            # _zoom is equivalent to wheel_index
            # if event.angleDelta().y() > 0:
            #     factor = 1.25
            #     self.wheel_index += 1
            # else:
            #     factor = 0.8
            #     self.wheel_index -= 1
            # if self.wheel_index > 0:
            #     self.scale(factor, factor)
            # elif self.wheel_index == 0:
            #     self.fitInView()
            # else:
            #     self.wheel_index = 0

        else:
            # Shifted Scroll Wheel zooms

            # self.wheel_index += event.delta()/120    #pyside2
            self.wheel_index += event.angleDelta().y() / 120  # pyside6
            # self.zoom_to_wheel_at(event.x(), event.y())
            # AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'x'
            self.zoom_to_wheel_at(event.position())  # return type: PySide6.QtCore.QPointF

    # todo
    #mainWindow.paintEvent is called very frequently. No need to initialize multiple global variables more than once.
    # Get rid of the cruft, try to limit these function calls
    def paintEvent(self, event):
        #tag
        # print("Painting | Caller: " + inspect.stack()[1].function + " | ZoomPanWidget.paintEvent...", end='')
        global crop_mode_role  #tag why repeatedly define these globals on each paint event?
        global crop_mode_disp_rect

        if not self.already_painting:
            self.already_painting = True

            painter = QPainter(self)

            role_text = self.role
            img_text = None

            if project_data != None:

                s = project_data['data']['current_scale']
                l = project_data['data']['current_layer']

                role_text = str(self.role) + " [" + str(s) + "]" + " [" + str(l) + "]"

                if len(project_data['data']['scales']) > 0:
                    if len(project_data['data']['scales'][s]['alignment_stack']) > 0:

                        image_dict = project_data['data']['scales'][s]['alignment_stack'][l]['images']
                        is_skipped = project_data['data']['scales'][s]['alignment_stack'][l]['skip']

                        if self.role in image_dict.keys():
                            ann_image = image_dict[self.role]
                            pixmap = image_library.get_image_reference(ann_image['filename'])
                            img_text = ann_image['filename']

                            #scale the painter to draw the image as the background
                            painter.scale(self.zoom_scale, self.zoom_scale)

                            if pixmap != None:
                                if self.draw_border:
                                    # Draw an optional border around the image
                                    painter.setPen(QPen(QColor(255, 255, 255, 255), 4))
                                    painter.drawRect(
                                        QRectF(self.ldx + self.dx, self.ldy + self.dy, pixmap.width(), pixmap.height()))
                                # Draw the pixmap itself on top of the border to ensure every pixel is shown
                                if (not is_skipped) or self.role == 'base':
                                    painter.drawPixmap(QPointF(self.ldx + self.dx, self.ldy + self.dy), pixmap)

                                # Draw any items that should scale with the image

                            # Rescale the painter to draw items at screen resolution
                            painter.scale(1.0 / self.zoom_scale, 1.0 / self.zoom_scale)

                            # Draw the borders of the viewport for each panel to separate panels
                            painter.setPen(QPen(self.border_color, 4))
                            painter.drawRect(painter.viewport())

                            if self.draw_annotations and (pixmap != None):
                                if (pixmap.width() > 0) or (pixmap.height() > 0):
                                    painter.setPen(QPen(QColor(128, 255, 128, 255), 5))
                                    painter.drawText(painter.viewport().width() - 100, 40,
                                                     "%dx%d" % (pixmap.width(), pixmap.height()))

                            if self.draw_annotations and 'metadata' in ann_image:
                                colors = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255],
                                          [0, 255, 255]]
                                if 'colors' in ann_image['metadata']:
                                    colors = ann_image['metadata']['colors']
                                    print_debug(95, "Colors in metadata = " + str(colors))
                                if 'annotations' in ann_image['metadata']:
                                    # Draw the application-specific annotations from the metadata
                                    color_index = 0
                                    ann_list = ann_image['metadata']['annotations']
                                    for ann in ann_list:
                                        print_debug(50, "Drawing " + ann)
                                        cmd = ann[:ann.find('(')].strip().lower()
                                        pars = [float(n.strip()) for n in ann[ann.find('(') + 1: -1].split(',')]
                                        print_debug(50, "Command: " + cmd + " with pars: " + str(pars))
                                        if len(pars) >= 4:
                                            color_index = int(pars[3])
                                        else:
                                            color_index = 0

                                        color_to_use = colors[color_index % len(colors)]
                                        print_debug(50, " Color to use: " + str(color_to_use))
                                        painter.setPen(QPen(QColor(*color_to_use), 5))
                                        x = 0
                                        y = 0
                                        r = 0
                                        if cmd in ['circle', 'square']:
                                            x = self.win_x(pars[0])
                                            y = self.win_y(pars[1])
                                            r = pars[2]
                                        if cmd == 'circle':
                                            painter.drawEllipse(x - r, y - r, r * 2, r * 2)
                                        if cmd == 'square':
                                            painter.drawRect(QRectF(x - r, y - r, r * 2, r * 2))
                                        if cmd == 'skipped':
                                            # color_to_use = colors[color_index+1%len(colors)]
                                            color_to_use = [255, 50, 50]
                                            painter.setPen(QPen(QColor(*color_to_use), 5))
                                            # painter.drawEllipse ( x-(r*2), y-(r*2), r*4, r*4 )
                                            painter.drawLine(0, 0, painter.viewport().width(),
                                                             painter.viewport().height())
                                            painter.drawLine(0, painter.viewport().height(), painter.viewport().width(),
                                                             0)
                                        color_index += 1

                            if is_skipped:  # skip #redx
                                # Draw the red "X" on all images regardless of whether they have the "skipped" annotation
                                self.setWindowOpacity(.5)
                                color_to_use = [255, 50, 50]
                                painter.setPen(QPen(QColor(*color_to_use), 5))
                                painter.drawLine(0, 0, painter.viewport().width(), painter.viewport().height())
                                painter.drawLine(0, painter.viewport().height(), painter.viewport().width(), 0)

                                # painter.fillRect(rect, QBrush(QColor(128, 128, 255, 128)));

            if self.draw_annotations:
                # Draw the role
                painter.setPen(QPen(QColor(255, 100, 100, 255), 5))
                painter.drawText(10, 20, role_text)
                if img_text != None:
                    # Draw the image name
                    painter.setPen(QPen(QColor(100, 100, 255, 255), 5))
                    if self.draw_full_paths:
                        painter.drawText(10, 40, img_text)
                    else:
                        if os.path.sep in img_text:
                            # Only split the path if it's splittable
                            painter.drawText(10, 40, os.path.split(img_text)[-1])
                        else:
                            painter.drawText(10, 40, img_text)

                if len(project_data['data']['scales']) > 0:
                    scale = project_data['data']['scales'][s]
                    if len(scale['alignment_stack']) > 0:
                        layer = scale['alignment_stack'][l]
                        if 'align_to_ref_method' in layer:
                            if 'method_results' in layer['align_to_ref_method']:
                                method_results = layer['align_to_ref_method']['method_results']
                                if 'snr_report' in method_results:
                                    if method_results['snr_report'] != None:
                                        painter.setPen(QPen(QColor(255, 255, 255, 255), 5))
                                        midw = painter.viewport().width() / 3
                                        painter.drawText(midw, 20, method_results['snr_report'])

            if self.role == crop_mode_role:
                if crop_mode_disp_rect != None:
                    painter.setPen(QPen(QColor(255, 100, 100, 255), 3))
                    rect_to_draw = QRectF(self.win_x(crop_mode_disp_rect[0][0]), self.win_y(crop_mode_disp_rect[0][1]),
                                          self.win_x(crop_mode_disp_rect[1][0] - crop_mode_disp_rect[0][0]),
                                          self.win_y(crop_mode_disp_rect[1][1] - crop_mode_disp_rect[0][1]))
                    painter.drawRect(rect_to_draw)

            # Note: It's difficult to use this on a Mac because of the focus policy combined with the shared single menu.
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

            painter.end()
            del painter

            self.already_painting = False


class MultiImagePanel(QWidget):

    def __init__(self):
        print("MultiImagePanel constructor called.")
        super(MultiImagePanel, self).__init__()

        # None of these attempts to auto-fill worked, so a paintEvent handler was added

        # p = self.palette()
        # p.setColor(self.backgroundRole(), Qt.black)
        # self.setPalette(p)
        # self.setAutoFillBackground(True)
        # self.setStyleSheet("background-color:black;")

        self.current_margin = 0
        self.hb_layout = QHBoxLayout()
        self.update_spacing()
        self.setLayout(self.hb_layout)
        self.actual_children = []
        self.setContentsMargins(0, 0, 0, 0)
        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False
        self.bg_color = QColor(40, 50, 50, 255)
        self.border_color = QColor(0, 0, 0, 255)

        # QWidgets don't get the keyboard focus by default
        # To have scrolling keys associated with this (multi-panel) widget, set a "StrongFocus"
        self.setFocusPolicy(Qt.StrongFocus)  #tag #bugaudit
        self.arrow_direction = 1

    # keypress
    def keyPressEvent(self, event):

        print("\n(!) Got a key press event: " + str(event))

        layer_delta = 0
        if event.key() == Qt.Key_Up:
            print_debug(70, "Key Up")
            layer_delta = 1 * self.arrow_direction
        if event.key() == Qt.Key_Down:
            print_debug(70, "Key Down")
            layer_delta = -1 * self.arrow_direction

        if (layer_delta != 0) and (self.actual_children != None):
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in [panels_to_update[0]]:  # Only update the first one which will update the rest
                p.change_layer(layer_delta)
                p.update_zpa_self()
                p.repaint()

        #main_window.update_base_label()

    def paintEvent(self, event):
        painter = QPainter(self)
        # painter.setBackgroundMode(Qt.OpaqueMode)
        # painter.setBackground(QBrush(Qt.black))
        if len(self.actual_children) <= 0:
            # Draw background for no panels
            painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
            painter.setPen(QPen(QColor(200, 200, 200, 255), 5))
            # painter.setPen(QPen(QColor('#000000'), 5)) #jy
            painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
            painter.drawText((self.width() / 2) - 140, self.height() / 2, " No Image Roles Defined ")
        else:
            # Draw background for panels
            painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
        painter.end()

        #main_window.update_base_label()

    def update_spacing(self):
        # print("MultiImagePanel is setting spacing to " + str(self.current_margin))
        # self.hb_layout.setContentsMargin(self.current_margin)    #pyside6 This sets margins around the outer edge of all panels
        # self.hb_layout.setMargin(self.current_margin)    #pyside2 This sets margins around the outer edge of all panels
        self.hb_layout.setSpacing(self.current_margin)  # This sets margins around the outer edge of all panels
        self.repaint()

    def update_multi_self(self, exclude=()):
        print("  MultiImagePanel is updating itself...")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget) and (not (w in exclude))]
            for p in panels_to_update:
                p.border_color = self.border_color
                p.update_zpa_self()
                p.repaint()

        if enable_stats:
            main_window.update_base_label()
            main_window.update_ref_label()

    def add_panel(self, panel):
        # print("MultiImagePanel is adding panel (MultiImagePanel.add_panel)...")
        if not panel in self.actual_children:
            self.actual_children.append(panel)
            self.hb_layout.addWidget(panel)
            panel.set_parent(self)
            self.repaint()

    def set_roles(self, roles_list):
        print("  MultiImagePanel is setting roles...")
        if len(roles_list) > 0:
            # Save these roles
            role_settings = {}
            for w in self.actual_children:
                if type(w) == ZoomPanWidget:
                    role_settings[w.role] = w.get_settings()

            project_data['data']['panel_roles'] = roles_list
            # Remove all the image panels (to be replaced)
            try:
                self.remove_all_panels()
            except:
                pass
            # Create the new panels
            for role in roles_list:
                zpw = ZoomPanWidget(role=role, parent=self)  # focus #zoompanwidget
                # Restore the settings from the previous zpw
                if role in role_settings:
                    zpw.set_settings(role_settings[role])
                zpw.draw_border = self.draw_border
                zpw.draw_annotations = self.draw_annotations
                zpw.draw_full_paths = self.draw_full_paths
                self.add_panel(zpw)

    def remove_all_panels(self):
        print("  MultiImagePanel is removing all panels...")
        while len(self.actual_children) > 0:
            self.hb_layout.removeWidget(self.actual_children[-1])
            self.actual_children[-1].deleteLater()
            self.actual_children = self.actual_children[0:-1]
        self.repaint()

    def refresh_all_images(self):
        print("  MultiImagePanel is refreshing all images...")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.update_zpa_self()
                p.repaint()
        self.repaint()

        if enable_stats:
            main_window.update_base_label()
            main_window.update_ref_label()

    @countit
    def center_all_images(self, all_images_in_stack=True):
        print("  MultiImagePanel is centering all images...")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.center_image(all_images_in_stack=all_images_in_stack)
                p.update_zpa_self()
                p.repaint()
        self.repaint()
        self.refresh_all_images()

    def all_images_actual_size(self):
        print("  MultiImagePanel is actual-sizing all images...")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.show_actual_size()
                p.update_zpa_self()
                p.repaint()
        self.repaint()


ignore_changes = True  # Default for first change which happens on file open?


def bounding_rect_changed_callback(state):
    global ignore_changes
    print_debug(50, 100 * '+')
    print_debug(50, "Bounding Rect changed to " + str(state))
    print_debug(50, "ignore_changes = " + str(ignore_changes))
    print_debug(50, 100 * '+')
    if not ignore_changes:
        if state:
            project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'] = False
        print_debug(50, "bounding_rec_changed_callback (" + str(state) + " saved as " + str(
            project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect']) + ")")


def print_all_skips():
    scale_keys = project_data['data']['scales'].keys()
    for scale_key in sorted(scale_keys):
        print_debug(50, " Scale: " + scale_key)
        scale = project_data['data']['scales'][scale_key]
        layers = scale['alignment_stack']
        for layer in layers:
            print_debug(50, "  Layer: " + str(layers.index(layer)) + ", skip = " + str(layer['skip']))
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def skip_changed_callback(state):  # 'state' is connected to skip toggle
    print("\nskip_changed_callback was called by " + inspect.stack()[1].function + "..")
    # This function gets called whether it's changed by the user or by another part of the program!!!
    global ignore_changes
    # called by:  change_layer <-- when ZoomPanWidget.change_layer toggles
    # called by:  run_app <-- when user toggles
    skip_list = []
    for layer_index in range(len(project_data['data']['scales'][get_cur_scale()]['alignment_stack'])):
        if project_data['data']['scales'][get_cur_scale()]['alignment_stack'][layer_index]['skip'] == True:
            skip_list.append(layer_index)

    if inspect.stack()[1].function == 'run_app':
        toggle_state = state
        new_skip = not state
        print('toggle_state: ' + str(toggle_state) + '  skip_list: ' + str(skip_list) + 'new_skip: ' + str(new_skip))

        print("  !!! Skip changed by user!! New value: " + str(new_skip))
        scale = project_data['data']['scales'][project_data['data']['current_scale']]
        layer = scale['alignment_stack'][project_data['data']['current_layer']]
        layer['skip'] = new_skip  # skip # this is where skip list is appended to
        if update_skips_callback != None:
            # update_skips_callback(bool(state)) #og
            update_skips_callback(new_skip)  #jy
    else:
        print("  Not called by run_app... short-circuiting...")

    if update_linking_callback != None:
        print("  Entering conditional (if update_linking_callback != None)...")
        update_linking_callback()
        main_window.update_win_self()
        main_window.update_panels()
        main_window.refresh_all_images()
        '''
        # This doesn't work to force a redraw of the panels
        if project_data != None:
            if 'data' in project_data:
                if 'current_layer' in project_data['data']:
                    layer_num = project_data['data']['current_layer']
                    ignore_changes = True
                    main_window.view_change_callback ( None, None, layer_num, layer_num )
                    ignore_changes = False
            '''

    skip_list = []
    for layer_index in range(len(project_data['data']['scales'][get_cur_scale()]['alignment_stack'])):
        if project_data['data']['scales'][get_cur_scale()]['alignment_stack'][layer_index]['skip'] == True:
            skip_list.append(layer_index)
    print("  skip_list = ", skip_list)
    # layer_num = project_data['data']['current_layer'] #jy
    #main_window.view_change_callback(None, None, layer_num, layer_num) #jy
    # update_linking_callback()
    #main_window.update_win_self()
    #main_window.update_panels()
    #main_window.refresh_all_images()
    main_window.status_skips_label.setText(str(skip_list))  # settext #status


def align_forward():
    print_debug(30, "Aligning Forward ...")


def console():
    print("\nPython Console:\n")
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


class ScreenshotSaver(object):
    def __init__(self, viewer, directory):
        self.viewer = viewer
        self.directory = directory

        if not os.path.exists(directory):
            os.makedirs(directory)

        self.index = 0

    def get_path(self, index):
        return os.path.join(self.directory, '%07d.png' % index)

    def get_next_path(self, index=None):
        if index is None:
            index = self.index
        return index, self.get_path(index)

    def capture(self, index=None):
        s = self.viewer.screenshot()
        increment_index = index is None
        index, path = self.get_next_path(index)
        with open(path, 'wb') as f:
            f.write(s.screenshot.image)
        if increment_index:
            self.index += 1
        return index, path



# unchunk
def unchunk(s):
    print("\n'u' key press detected. Executing unchunk callback function...\n")
    destination_path = os.path.abspath(project_data['data']['destination_path'])
    path = zarr_project_path = os.path.join(destination_path, "project.zarr")
    ds_aligned = "img_aligned_zarr"
    print("'u' key press detected. Executing unchunk function...")
    # this is parallel
    path = zarr_project_path
    #scale = 0
    scale = 2
    n_unchunk = int(s.mouse_voxel_coordinates[2])
    # img_scale = da.from_zarr(path + '/img_aligned_zarr/s' + str(scale))
    img_scale = da.from_zarr(path + '/' + ds_aligned + '/s0')
    curr_img = img_scale[n_unchunk, :, :]
    skimage.io.imsave('image_' + str(n_unchunk) + '_scale' + str(scale) + '.tif', curr_img)

    img = Image.open(curr_img)
    img.show()

    print("Callback complete.")


# def unchunk_all_scale(s, scale):
#     # this can be parallel


# blend
def blend(s):
    print("\n'b' key press detected. Executing blend callback function...\n")
    print("current working dir :", os.getcwd())
    destination_path = os.path.abspath(project_data['data']['destination_path'])
    src = zarr_project_path = os.path.join(destination_path, "project.zarr")
    ds_aligned = "img_aligned_zarr"
    # blend_scale = 0
    blend_scale = 2
    n_blend = int(s.mouse_voxel_coordinates[2])
    blend_name = 'blended_' + str(n_blend) + '-' + str(n_blend + 1) + '.tif'

    print("Creating blended TIF of images " + str(n_blend) + " and " + str(n_blend + 1) + " using PIL.Image...")

    # img_scale = da.from_zarr(src + '/img_aligned_zarr/s0')
    img_scale = da.from_zarr(src + '/' + ds_aligned + '/s' + str(blend_scale))
    curr_img = img_scale[n_blend, :, :]
    next_img = img_scale[n_blend + 1, :, :]
    out1 = 'temp_image_' + str(n_blend) + '.tif'
    out2 = 'temp_image_' + str(n_blend + 1) + '.tif'
    skimage.io.imsave(out1, curr_img)
    skimage.io.imsave(out2, next_img)

    img1 = Image.open(out1)
    img2 = Image.open(out2)

    result = Image.blend(img1, img2, 0.5)
    print('Removing temporary TIF files...')
    os.remove(out1)
    os.remove(out2)

    print('Saving image blend as temporary TIF ' + blend_name + '...')
    result.save(blend_name)

    result.show()

    print("Callback complete.")

    # im = Image.open(f_result)
    # im.show()


# example keypress callback
def get_mouse_coords(s):
    print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
    print('  Layer selected values: %s' % (s.selected_values,))


# server #runnable
class RunnableServerThread(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self):
        super(RunnableServerThread, self).__init__()
        print("RunnableServerThread constructor called")

        """
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        """

        """
        self.signals = WorkerSignals()
        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress
        """

    @Slot()
    def run(self):
        # time.sleep(1)
        destination_path = os.path.abspath(project_data['data']['destination_path'])
        print("destination_path: ", destination_path)
        zarr_project_path = os.path.join(destination_path, "project.zarr")
        os.chdir(zarr_project_path)

        bind = '127.0.0.1'
        port = 9000

        print("Preparing browser view of " + zarr_project_path + "...")
        print("bind                       :", bind)
        print("port                       :", port)

        server = Server((bind, port))
        # server.allow_reuse_address = True
        sa = server.socket.getsockname()
        host = str("http://%s:%d" % (sa[0], sa[1]))
        viewer_source = str("zarr://" + host)
        print("Serving directory %s at http://%s:%d" % (os.getcwd(), sa[0], sa[1]))
        print("Viewer source                   :", viewer_source)
        print("Protocol version                :", server.protocol_version)
        print("Server name                     :", server.server_name)
        print("Server type                     :", server.socket_type)
        # print("allow reuse address= ", server.allow_reuse_address)

        MAX_RETRIES = 10
        attempt = 0
        for _ in range(MAX_RETRIES):
            attempt = attempt + 1
            print("Trying to serve forever... attempt(" + str(attempt) + ")...")
            try:
                server.serve_forever()
            except:
                print("\nServer connection temporarily lost.\nAttempting to reconnect...\n")
                continue
            else:
                break
        else:
            print("\nMaximum reconnection attempts reached. Disconnecting...\n")
            server.server_close()
            sys.exit(0)


#webpage #browser #embedded
# class CustomWebEnginePage(QWebEnginePage):
#     """ Custom WebEnginePage to customize how we handle link navigation """
#     """ https://www.pythonguis.com/faq/qwebengineview-open-links-new-window/ """
#     """ refer to section: Conditionally popping up a new window """
#     # Store external windows.
#     external_windows = []
#
#     def acceptNavigationRequest(self, url,  _type, isMainFrame):
#         if (_type == QWebEnginePage.NavigationTypeLinkClicked and
#             url.host() != 'www.mfitzp.com'):
#             # Pop up external links into a new window.
#             w = QWebEngineView()
#             w.setUrl(url)
#             w.show()
#
#             # Keep reference to external window, so it isn't cleared up.
#             self.external_windows.append(w)
#             return False
#         return super().acceptNavigationRequest(url,  _type, isMainFrame)
#
#
class CustomWebEnginePage(QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation """
    # Store external windows.
    external_windows = []

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if (_type == QWebEnginePage.NavigationTypeLinkClicked and url.host() != 'github.com'):
            # Pop up external links into a new window.
            w = QWebEngineView()
            w.setUrl(url)
            w.show()

            # Keep reference to external window, so it isn't cleared up.
            self.external_windows.append(w)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)


# https://stackoverflow.com/questions/5671354/how-to-programmatically-make-a-horizontal-line-in-qt
class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


# def render(source_html):
#     """Fully render HTML, JavaScript and all."""
#     from PySide6.QtCore import QEventLoop
#     class Render(QWebEngineView):
#         def __init__(self, html):
#             self.html = None
#             QWebEngineView.__init__(self)
#             self.loadFinished.connect(self._loadFinished)
#             self.setHtml(html)
#             while self.html is None:
#                 self.app.processEvents(QEventLoop.ExcludeUserInputEvents | QEventLoop.ExcludeSocketNotifiers | QEventLoop.WaitForMoreEvents)
#             self.app.quit()
#
#         def _callable(self, data):
#             self.html = data
#
#         def _loadFinished(self, result):
#             self.page().toHtml(self._callable)
#
#     return Render(source_html).html
#
# import requests
# sample_html = requests.get("https://github.com/google/neuroglancer").text
# print(render(sample_html))

# toggle #switch #skip #reset
class ToggleSwitch(QCheckBox):
    _transparent_pen = QPen(Qt.transparent)
    _light_grey_pen = QPen(Qt.lightGray)
    _black_pen = QPen(Qt.black)

    def __init__(self,
                 parent=None,
                 bar_color=Qt.gray,
                 # checked_color="#00B0FF",
                 # checked_color="#ffffff",
                 # checked_color="#607cff",
                 checked_color="#d3dae3",  # for monjaromix stylesheet

                 handle_color=Qt.white,
                 h_scale=1.0,
                 v_scale=0.9,
                 fontSize=9):

        super().__init__(parent)
        print('ToggleSwitch constructor called.')

        self.setFocusPolicy(Qt.NoFocus)  # focus don't steal focus from zoompanwidget

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())

        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor(checked_color))

        # Setup the rest of the widget.

        # (int left, int top, int right, int bottom)
        # self.setContentsMargins(8, 0, 8, 0)
        self.setContentsMargins(8, 0, 8, 0)
        # self._handle_position = 0
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize

        self.stateChanged.connect(self.handle_state_change)

        self.setMaximumWidth(84)

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        return QSize(58, 45)
        # return QSize(86, 45)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect()
        width = contRect.width() * self._h_scale
        height = contRect.height() * self._v_scale
        handleRadius = round(0.24 * height)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(self._transparent_pen)
        barRect = QRectF(0, 0, width - handleRadius, 0.40 * height)
        barRect.moveCenter(contRect.center())
        rounding = barRect.height() / 2

        # the handle will move along this line
        trailLength = contRect.width() * self._h_scale - 2 * handleRadius
        xLeft = contRect.center().x() - (trailLength + handleRadius) / 2
        xPos = xLeft + handleRadius + trailLength * self._handle_position

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setBrush(self._handle_checked_brush)

            p.setPen(self._black_pen)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.drawText(xLeft + handleRadius / 2, contRect.center().y() + handleRadius / 2, "KEEP")

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._black_pen)
            p.setBrush(self._handle_brush)
            p.drawText(contRect.center().x(), contRect.center().y() + handleRadius / 2, "SKIP")

        p.setPen(self._light_grey_pen)
        p.drawEllipse(QPointF(xPos, barRect.center().y()), handleRadius, handleRadius)
        p.end()

    @Slot(int)
    def handle_state_change(self, value):
        print("ToggleSwitch is handling state change (ToggleSwitch.handle_state_change)...")
        self._handle_position = 1 if value else 0

    @Property(float)
    def handle_position(self):
        print("ToggleSwitch is handling position (ToggleSwitch.handle_position, @Property(float) decorator)...")
        print("Note: @Property(float)\n")
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
        print("ToggleSwitch is handling position (ToggleSwitch.handle_position, @handle_position.setter decorator)...")
        """change the property
           we need to trigger QWidget.update() method, either by:
           1- calling it here [ what we're doing ].
           2- connecting the QPropertyAnimation.valueChanged() signal to it.
        """
        self._handle_position = pos
        self.update()

    def setH_scale(self, value):
        self._h_scale = value
        self.update()

    def setV_scale(self, value):
        self._v_scale = value
        self.update()

    def setFontSize(self, value):
        self._fontSize = value
        self.update()


#mainwindow
# from autolog import log_calls
# @log_calls
# from autologging import logged, TRACE, traced
# @logged
# @traced
class MainWindow(QMainWindow):

    def __init__(self, fname=None, panel_roles=None, control_model=None, title="Align EM", simple_mode=True):

        self.pyside_path = os.path.dirname(os.path.realpath(__file__))
        print("pyside_path = ", self.pyside_path)

        print('Setting MESA_GL_VERSION_OVERRIDE=4.5...')
        os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
        print('MESA_GL_VERSION_OVERRIDE = ', os.environ.get('MESA_GL_VERSION_OVERRIDE'))

        print('Setting default_format using QSurfaceFormat...')
        self.default_format = QSurfaceFormat.defaultFormat()

        print("Setting up thread pool...")
        # self.threadpool = QThreadPool() #test
        # print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

        self.init_dir = os.getcwd()

        # # NOTE: You must set the AA_ShareOpenGLContexts flag on QGuiApplication before creating the QGuiApplication
        # # object, otherwise Qt may not create a global shared context.
        # # https://doc.qt.io/qtforpython-5/PySide2/QtGui/QOpenGLContext.html
        # print('Current QOpenGLContext = ', QOpenGLContext.currentContext())
        #
        # print('Setting OpenGL attribute AA_ShareOpenGLContexts...')
        #
        # QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        # # QtCore.QProcessEnvironment.systemEnvironment() ???
        # print('Current QOpenGLContext = ', QOpenGLContext.currentContext())

        global app
        if app == None:
            print("No pre-existing QApplication instance, defining new global | app = QApplication([])")
            app = QApplication([])
        else:
            print("Existing QApplication instance found, continuing...")

        global project_data
        project_data = copy.deepcopy(new_project_template)

        print('\nInitializing QMainWindow...\n')
        QMainWindow.__init__(self)
        self.setWindowTitle(title)
        self.current_project_file_name = None
        self.view_change_callback = None
        self.mouse_down_callback = None
        self.mouse_move_callback = None
        # self.setAttribute(Qt.WA_TranslucentBackground, True) #translucent #dim #opacity #redx
        # self.setFocusPolicy(Qt.StrongFocus)  #jy #focus

        # self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        # self.setWindowFlag(Qt.FramelessWindowHint)

        # stylesheet must be after QMainWindow.__init__(self)
        # self.setStyleSheet(open('stylesheet.qss').read())
        print("Applying stylesheet... ")
        self.setStyleSheet(open(os.path.join(self.pyside_path, 'stylesheet.qss')).read())

        # print("Setting multiprocessing.set_start_method('fork', force=True)...")
        # multiprocessing.set_start_method('fork', force=True)

        std_button_size = QSize(130, 28)

        # titlebar resource
        # https://stackoverflow.com/questions/44241612/custom-titlebar-with-frame-in-pyqt5

        # pyside2... pyside6 deprecated the 'defaultSettings()' attribute of QWebEngineSettings. These two lines were uncommented.
        # self.web_settings = QWebEngineSettings.defaultSettings()
        # self.web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # pyside6
        print("Instantiating QWebEngineView... ")
        self.view = QWebEngineView()
        # PySide6 available options
        # self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        print("Setting QWebEngineSettings.LocalContentCanAccessRemoteUrls to True.")
        self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # !!!
        # def changeEvent(self, event):
        #     if event.type() == event.WindowStateChange:
        #         self.titleBar.windowStateChanged(self.windowState())
        #
        # def resizeEvent(self, event):
        #     self.titleBar.resize(self.width(), self.titleBar.height())

        # # set stylesheet
        # file = QFile(":/dark/stylesheet.qss")
        # file.open(QFile.ReadOnly | QFile.Text)
        # stream = QTextStream(file)
        # app.setStyleSheet(stream.readAll())

        #jy Call the RunnableServerThread class to start background CORS web server
        # def start_server():
        #     print("\nstart_server() was called...\n")
        #     print("Creating RunnableServerThread() worker...")
        #     worker = RunnableServerThread()
        #     print("Setting up thread pool...")
        #     self.threadpool.start(worker)

        # self.browser.setPage(CustomWebEnginePage(self)) # This is necessary. Clicked links will never open new window.
        # self.browser.setPage(CustomWebEnginePage(self))

        # homepage #browserview #webview
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!%7B%22dimensions%22:%7B%22x%22:%5B8e-9%2C%22m%22%5D%2C%22y%22:%5B8e-9%2C%22m%22%5D%2C%22z%22:%5B8e-9%2C%22m%22%5D%7D%2C%22position%22:%5B2914.500732421875%2C3088.243408203125%2C4045%5D%2C%22crossSectionScale%22:3.762185354999915%2C%22projectionOrientation%22:%5B0.31435418128967285%2C0.8142172694206238%2C0.4843378961086273%2C-0.06040274351835251%5D%2C%22projectionScale%22:4593.980956070108%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/image%22%2C%22tab%22:%22source%22%2C%22name%22:%22image%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/ground_truth%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22158571%22%2C%2221894%22%2C%2222060%22%2C%2224436%22%2C%222515%22%5D%2C%22name%22:%22ground-truth%22%7D%5D%2C%22showSlices%22:false%2C%22layout%22:%224panel%22%7D"))
        # self.browser.load(QUrl("https://github.com/google/neuroglancer"))
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!{'layers':{'original-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image'_'visible':false}_'corrected-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image_color_corrected'}_'ground_truth':{'type':'segmentation'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/ground_truth'_'selectedAlpha':0.63_'notSelectedAlpha':0.14_'segments':['3208'_'4901'_'13'_'4965'_'4651'_'2282'_'3189'_'3758'_'15'_'4027'_'3228'_'444'_'3207'_'3224'_'3710']}}_'navigation':{'pose':{'position':{'voxelSize':[6_6_30]_'voxelCoordinates':[5523.99072265625_8538.9384765625_1198.0423583984375]}}_'zoomFactor':22.573112129999547}_'perspectiveOrientation':[-0.004047565162181854_-0.9566211104393005_-0.2268827110528946_-0.1827099621295929]_'perspectiveZoom':340.35867907175077}"))
        # self.browser.setUrl(QUrl()) # empty/blank URL (white screen)
        # self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        # self.browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/user/README.md'))

        # Force the style to be the same on all OSs:
        print("Setting QApplication.setStyle to 'Fusion'...")
        app.setStyle('Fusion')

        # def demos_view(): #documentationview
        #     print("\ndocumentation_view():\n")
        #     self.browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/user/README.md'))
        #     time.sleep(2)
        #     self.stacked_widget.setCurrentIndex(2)

        def documentation_view():  # documentationview
            print("Launching documentation view | MainWindow.documentation_view...")
            # don't force the reload, add home button instead
            self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
            self.stacked_widget.setCurrentIndex(2)
            self.status.showMessage("GlanceEM_SWiFT Documentation")

        def documentation_view_home():
            print("Launching documentation view home | MainWindow.documentation_view_home...")
            self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
            self.status.showMessage("GlanceEM_SWiFT Documentation")

        def remote_view():
            print("Launching remote viewer | MainWindow.remote_view...")
            self.stacked_widget.setCurrentIndex(4)
            self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
            self.status.showMessage("Remote Neuroglancer Viewer (https://neuroglancer-demo.appspot.com/)")

        # webgl2
        def microns_view():
            print("Launching microns viewer | MainWindow.microns_view...")
            self.stacked_widget.setCurrentIndex(5)
            self.browser_microns.setUrl(QUrl(
                'https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v0/son_of_alignment_v15_rechunked%22%2C%22type%22:%22image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22EM%22%7D%2C%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v185/seg%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22:0.51%2C%22segments%22:%5B%22648518346349538235%22%2C%22648518346349539462%22%2C%22648518346349539853%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22cell_segmentation_v185%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-clefts/mip1_d2_1175k%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22synapses%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-mito/seg_191220%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22mitochondria%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-nuclei/seg%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22nuclei%22%7D%5D%2C%22navigation%22:%7B%22pose%22:%7B%22position%22:%7B%22voxelSize%22:%5B4%2C4%2C40%5D%2C%22voxelCoordinates%22:%5B83222.921875%2C52981.34765625%2C834.9962768554688%5D%7D%7D%2C%22zoomFactor%22:383.0066650796121%7D%2C%22perspectiveOrientation%22:%5B-0.00825042650103569%2C0.06130112707614899%2C-0.0012821174459531903%2C0.9980843663215637%5D%2C%22perspectiveZoom%22:3618.7659948513424%2C%22showSlices%22:false%2C%22selectedLayer%22:%7B%22layer%22:%22cell_segmentation_v185%22%7D%2C%22layout%22:%7B%22type%22:%22xy-3d%22%2C%22orthographicProjection%22:true%7D%7D'))
            self.status.showMessage("MICrONS (http://layer23.microns-explorer.org)")
            # self.browser_microns.setUrl(QUrl('https://get.webgl.org/webgl2/'))
            # self.status.showMessage("Checking WebGL2.0 support.")

        def reload_ng():
            print("Reloading Neuroglancer...")
            ng_view()

        def reload_remote():
            print("Reloading remote viewer...")
            remote_view()

        def exit_ng():
            print("Exiting Neuroglancer...")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        def exit_docs():
            print("Exiting docs...")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        def exit_remote():
            print("Exiting remote viewer...")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        def exit_demos():
            print("Exiting demos...")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        # webgl2
        # def exit_microns():
        #     print("\nexit_microns():\n")
        #     self.stacked_widget.setCurrentIndex(0)
        #     self.status.showMessage("")

        def print_state_ng():
            self.status.showMessage("Printing viewer state...")
            # viewer_state = json.loads(str(self.viewer.state))
            print(self.viewer.state)
            print("\n")

            # print("Viewer.url : ", self.viewer.get_viewer_url)
            # print("Viewer.screenshot : ", self.viewer.screenshot)
            # print("Viewer.txn : ", self.viewer.txn)
            # print("Viewer.actions : ", self.viewer.actions)
            # time.sleep(1)
            # self.status.showMessage("Viewing aligned images in Neuroglancer.")

        def print_url_ng():
            self.status.showMessage("Printing viewer URL...")
            print(neuroglancer.to_url(self.viewer.state))
            # print("\nURL : " + self.viewer.get_viewer_url() + "\n")

            # print("Viewer.url : ", self.viewer.get_viewer_url)
            # print("Viewer.screenshot : ", self.viewer.screenshot)
            # print("Viewer.txn : ", self.viewer.txn)
            # print("Viewer.actions : ", self.viewer.actions)
            # time.sleep(1)
            # self.status.showMessage("Viewing aligned images in Neuroglancer.")
            print("\n")

        # def screenshot_ng():
        #     self.status.showMessage("Taking screenshot...")
        #     ScreenshotSaver.capture(self)

        def blend_ng():
            print("blend_ng() : ")
            # self.status.showMessage("Making blended image...")

        # ng_view #ngview
        def ng_view():  # ng_view #ngview #neuroglancer
            print("Creating Neuroglancer viewer...")

            if not self.current_project_file_name:
                print("  (!) There is no open project. Not opening viewer.")
                self.status.showMessage("There is no project open,  nothing to view.")
                return

            destination_path = os.path.abspath(project_data['data']['destination_path'])
            zarr_project_path = os.path.join(destination_path, "project.zarr")

            if not os.path.isdir(zarr_project_path):
                print("  (!) No Zarr project file not found.")
                self.status.showMessage("Project must be exported to Zarr before it can be viewed in Neuroglancer.")
                return

            if 'server' in locals():
                print("Server is already running. Continuing...")
            else:
                # self.browser.setUrl(QUrl()) #empty page
                print("No server found in local namespace. Starting RunnableServerThread() worker...")
                worker = RunnableServerThread()
                self.threadpool.start(worker)

            # time.sleep(1)

            print("destination_path: ", destination_path)
            print("zarr_project_dir: ", zarr_project_path)

            os.chdir(zarr_project_path)  #tag

            Image.MAX_IMAGE_PIXELS = None

            view = 'single'
            # if self.multiview_bool.isChecked():
            #     view = 'row'

            bind = '127.0.0.1'
            port = 9000

            res_x = 2
            res_y = 2
            res_z = 50

            src = zarr_project_path

            # LOAD METADATA - .zarray
            print("Loading metadata from .zarray (array details) file...")
            zarray_path = os.path.join(src, "img_aligned_zarr", "s0", ".zarray")
            print("zarray_path : ", zarray_path)
            with open(zarray_path) as f:
                zarray_keys = json.load(f)
            chunks = zarray_keys["chunks"]

            # cname = zarray_keys["compressor"]["cname"] #jy
            # clevel = zarray_keys["compressor"]["clevel"] #jy

            shape = zarray_keys["shape"]
            print("shape : ", shape)

            # LOAD META DATA - .zattrs
            print("Loading metadata from .zattrs (attributes) file...")
            zattrs_path = os.path.join(src, "img_aligned_zarr", "s0", ".zattrs")
            with open(zattrs_path) as f:
                zattrs_keys = json.load(f)
            print("zattrs_path : ", zattrs_path)
            resolution = zattrs_keys["resolution"]
            scales = zattrs_keys["scales"]
            print("scales : ", scales)

            ds_ref = "img_ref_zarr"
            ds_base = "img_base_zarr"
            ds_aligned = "img_aligned_zarr"
            ds_blended = "img_blended_zarr"

            print("Initializing neuroglancer.Viewer()...")
            # viewer = ng.Viewer()
            self.viewer = ng.Viewer()

            print("Looking for ALIGNED scale directories...")
            data_aligned = []
            aligned_scale_paths = glob(os.path.join(src, ds_aligned) + "/s*")
            for s in aligned_scale_paths:
                scale = os.path.join(ds_aligned, os.path.basename(s))
                print("Daisy is opening scale ", s, ". Appending aligned data...")
                data_aligned.append(open_ds(src, scale))

            if view == 'row':
                print("Looking for REF scale directories...")
                data_ref = []
                ref_scale_paths = glob(os.path.join(src, ds_ref) + "/s*")
                for s in ref_scale_paths:
                    scale = os.path.join(ds_ref, os.path.basename(s))
                    print("Daisy is opening scale ", s, ". Appending ref data...")
                    data_ref.append(open_ds(src, scale))

                print("Looking for BASE scale directories...")
                data_base = []
                base_scale_paths = glob(os.path.join(src, ds_base) + "/s*")
                for s in base_scale_paths:
                    scale = os.path.join(ds_base, os.path.basename(s))
                    print("Daisy is opening scale ", s, ". Appending base data...")
                    data_base.append(open_ds(src, scale))

            print("Defining coordinate space...")
            dimensions = ng.CoordinateSpace(
                names=['x', 'y', 'z'],
                units='nm',
                #scales=scales, #jy
                scales=[res_x, res_y, res_z],
            )

            # https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
            print("Updating viewer.txn()...")
            with self.viewer.txn() as s:

                # s.cross_section_background_color = "#ffffff"
                s.cross_section_background_color = "#000000"
                s.dimensions = dimensions
                # s.perspective_zoom = 300
                # s.position = [0.24, 0.095, 0.14]
                # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

                # temp = np.zeros_like(data_ref)
                # layer = ng.Layer(temp)

                import numpy as np

                print("type(data_aligned) = ", type(data_aligned))  # <class 'list'>
                print("type(data_aligned[0]) = ", type(data_aligned[0]))  # <class 'daisy.array.Array'>
                print("len(data_aligned) = ", len(data_aligned))  # 2

                array = np.asarray(data_aligned)
                # print("type(array) = ", type(array))                       # <class 'numpy.ndarray'>
                # print("array.shape = ", array.shape)                       # (2,)
                # print("array.size = ", array.size)                         # 2
                # print("array.ndim = ", array.ndim)                         # 1

                print("type(np.asarray(data_aligned)) = ", type(np.asarray(data_aligned)))
                print("np.asarray(data_aligned).shape = ", np.asarray(data_aligned).shape)
                print("np.asarray(data_aligned).size = ", np.asarray(data_aligned).size)
                print("np.asarray(data_aligned).ndim = ", np.asarray(data_aligned).ndim)

                # only for 3 pane view
                if view == 'row':
                    add_layer(s, data_ref, 'ref')
                    add_layer(s, data_base, 'base')

                add_layer(s, data_aligned, 'aligned')

                ###data_panel_layout_types: frozenset(['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'])

                # s.selectedLayer.visible = False
                # s.layers['focus'].visible = False

                # view = "single"

                if view == "row":
                    print("view= row")

                    s.layers['focus'].visible = True

                    # [
                    #     ng.LayerGroupViewer(layers=["focus"], layout='xy'),

                    # temp = np.zeros_like(data_ref)
                    # #layer = ng.Layer()
                    # #layer = ng.ManagedLayer
                    # s.layers['focus'] = ng.LocalVolume(temp)

                    # s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr",voxel_size=[i * .00000001 for i in resolution])
                    s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
                    s.layout = ng.column_layout(
                        [
                            ng.row_layout(
                                [
                                    ng.LayerGroupViewer(layers=["focus"], layout='xy'),
                                ]
                            ),

                            ng.row_layout(
                                [
                                    ng.LayerGroupViewer(layers=['ref'], layout='xy'),
                                    ng.LayerGroupViewer(layers=['base'], layout='xy'),
                                    ng.LayerGroupViewer(layers=['aligned'], layout='xy'),
                                ]
                            ),
                        ]
                    )

                    # s.layout = ng.column_layout(
                    #
                    #     [
                    #         ng.LayerGroupViewer(layers=["focus"], layout='xy'),
                    #
                    # s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
                    #
                    # ng.row_layout(
                    #     [
                    #         ng.LayerGroupViewer(layers=["ref"], layout='xy'),
                    #         ng.LayerGroupViewer(layers=["base"], layout='xy'),
                    #         ng.LayerGroupViewer(layers=["aligned"], layout='xy'),
                    #     ]
                    # )
                    #
                    #
                    #
                    #
                    #     ]
                    #
                    # ]
                    # # )

                # single image view
                if view == "single":
                    print('view= single')
                    s.layout = ng.column_layout(
                        [
                            ng.LayerGroupViewer(
                                layout='xy',
                                layers=["aligned"]),
                        ]
                    )

            self.viewer.actions.add('get_mouse_coords_', get_mouse_coords)
            self.viewer.actions.add('unchunk_', unchunk)
            self.viewer.actions.add('blend_', blend)
            with self.viewer.config_state.txn() as s:
                s.input_event_bindings.viewer['keyt'] = 'get_mouse_coords_'
                s.input_event_bindings.viewer['keyu'] = 'unchunk_'
                s.input_event_bindings.viewer['keyb'] = 'blend_'
                # s.status_messages['message'] = 'Welcome to glanceEM_SWiFT!'

                s.show_ui_controls = True
                s.show_panel_borders = True
                s.viewer_size = None

            # To modify the state, use the viewer.txn() function, or viewer.set_state

            print("viewer.get_viewer_url(): ", self.viewer.get_viewer_url())

            print("\nDone making viewer.\n")
            viewer_url = str(self.viewer)
            self.browser.setUrl(QUrl(viewer_url))

            print("Viewer.config_state : ", self.viewer.config_state)
            # print("\nNeuroglancer view (remote viewer)    :\n", ng.to_url(viewer.state))
            print("\nNeuroglancer view (local viewer)     :\n", self.viewer, "\n")

            # #self.browser.setUrl(QUrl()) #empty page
            # worker = RunnableServerThread()
            # print("Setting up thread pool...")
            # self.threadpool.start(worker)

            self.stacked_widget.setCurrentIndex(1)
            self.status.showMessage("Viewing aligned images in Neuroglancer.")

            # client = CAVEclient()
            # #EMsource = client.info.get_datastacks()
            # print("\n\n")
            # #print(str(print(EMsource)))
            # print(client.state)
            # print("\n\n")
            # #print(EMsource)
            # print("\n\n")

            # print(neuroglancer.to_url(self.viewer.state))

        ####

        if panel_roles != None:
            project_data['data']['panel_roles'] = panel_roles

        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False

        self.panel_list = []

        self.simple_mode = simple_mode
        self.main_panel = QWidget()
        self.main_panel_layout = QVBoxLayout()

        self.main_panel_extended_layout = QHBoxLayout()
        self.main_panel_extended_layout.addLayout(self.main_panel_layout)
        self.main_panel.setLayout(self.main_panel_extended_layout)

        self.main_panel.setLayout(self.main_panel_layout)
        # self.main_panel.setAutoFillBackground(False)

        self.image_panel = MultiImagePanel()
        self.image_panel.draw_border = self.draw_border
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.draw_full_paths = self.draw_full_paths
        self.image_panel.setAutoFillBackground(True)

        self.main_panel_layout.addWidget(self.image_panel)  #jy instantiate image panel #mainpanel #mainlayout

        # self.main_panel_layout.addWidget ( self.control_panel ) #controlpanel #controlmodel

        # self.cname_type = ComboBoxControl(['zstd  ', 'zlib  ', 'gzip  ', 'none']) #?? why
        # note - check for string comparison of 'none' later, do not add whitespace fill
        # self.clevel_val = IntField("clevel (1-9):", 5)
        # self.n_scales_val = IntField("scales:", 4)

        # shoehorn extra UI elements
        # self.server_button = QPushButton("Launch Server...")
        # self.server_button.clicked.connect(start_server)
        # self.main_panel_layout.addWidget(self.server_button)

        # self.main_panel_layout.addWidget(self.browser) #tag

        def pretty(d, indent=0):
            for key, value in d.items():
                print('\t' * indent + str(key))
                if isinstance(value, dict):
                    pretty(value, indent + 1)
                else:
                    print('\t' * (indent + 1) + str(value))

        #debug #debuglayer
        def debug_layer():
            print("\n:::DEBUG LAYER:::")
            print("project path = ", project_data['data']['destination_path'])
            print("current scale = ", project_data['data']['current_scale'])
            scale = project_data['data']['scales'][
                project_data['data']['current_scale']]  # print(scale) # returns massive wall of text
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
            base_file_name = layer['images']['base']['filename']
            print("current base image = ", base_file_name)
            print("SNR = ", get_cur_snr())
            print("type(get_cur_snr()) = ", type(get_cur_snr()))
            print("alignment option = ",
                  scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                      'alignment_option'])
            print("whitening factor = ",
                  scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                      'whitening_factor'])
            print("SWIM window = ",
                  scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                      'win_scale_factor'])
            # print("layer = \n", pretty(layer)) # dict_keys(['align_to_ref_method', 'images', 'skip']
            print("layer['skip'] = ", layer['skip'])
            print("scale['alignment_stack'][project_data['data']['current_layer']]['skip'] = ",
                  scale['alignment_stack'][project_data['data']['current_layer']]['skip'])

            skip_list = []
            for layer_index in range(len(project_data['data']['scales'][get_cur_scale()]['alignment_stack'])):
                if project_data['data']['scales'][get_cur_scale()]['alignment_stack'][layer_index]['skip'] == True:
                    skip_list.append(layer_index)
            print("skip_list = ", skip_list)
            print("scale['alignment_stack'][project_data['data']['current_layer']] = \n",
                  scale['alignment_stack'][project_data['data']['current_layer']])

            print("\nproject_data.keys() = ", project_data.keys())
            print("layer.keys() = ", layer.keys())
            print("scale.keys() = ", scale.keys())

        def export_zarr():
            print('Exporting to Zarr...')

            if not self.current_project_file_name:
                print("  (!) There is no project open, nothing to export.")
                self.status.showMessage("There is no project open, nothing to export.")
                return

            destination_path = os.path.abspath(project_data['data']['destination_path'])
            print("  destination_path                    :", destination_path)
            # print("\nproject_data...\n",project_data)
            scale_1_path = os.path.join(project_data['data']['destination_path'], 'scale_1')  #scale_1_path= scale_1
            aligned_path = os.path.join(scale_1_path, 'img_aligned')  # aligned_path= scale_1/img_aligned
            # aligned_path_full = os.path.join(cwd, aligned_path) ???
            # print("aligned_path_full= ", aligned_path_full) ???
            print("  aligned_path                    :", aligned_path)

            self.clevel = self.clevel_input.text()
            self.cname = self.cname_combobox.currentText()
            self.n_scales = self.n_scales_input.text()

            os.chdir(self.pyside_path)
            print("  working directory               :", os.getcwd())

            self.status.showMessage("Exporting project to Zarr...")
            if self.cname == "none":
                os.system(
                    "python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(
                        self.n_scales) + " -nC 1 -d " + destination_path)
            else:
                # os.system("./make_zarr.py volume_josef_small --chunks '1,5332,5332' --no_compression True")
                os.system(
                    "python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(self.n_scales) + " -cN " + str(
                        self.cname) + " -cL " + str(self.clevel) + " -d " + destination_path)

            self.status.showMessage("Export to Zarr complete.")

        # I think this must occur after export_zarr function defintion
        self.export_and_view_hbox = QHBoxLayout()
        self.export_zarr_button = QPushButton("Export to Zarr")
        self.export_zarr_button.clicked.connect(export_zarr)
        self.export_zarr_button.setFixedSize(std_button_size)

        # self.ng_button = QPushButton("Neuroglancer View")
        self.ng_button = QPushButton("Neuroglancer View")
        self.ng_button.clicked.connect(
            ng_view)  # HAH the () parenthesis were causing the member function to be evaluated early
        self.ng_button.setFixedSize(QSize(130, 28))

        n_scales_label = QLabel("#scales:")
        # n_scales_label.setAlignment(Qt.AlignRight)
        self.n_scales_input = QLineEdit(self)
        self.n_scales_input.setText("4")
        self.n_scales_input.setFixedWidth(40)
        self.n_scales_valid = QIntValidator(1, 20, self)
        self.n_scales_input.setValidator(self.n_scales_valid)

        clevel_label = QLabel("clevel (1-9):")
        # clevel_label.setAlignment(Qt.AlignRight)
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setText("5")
        self.clevel_input.setFixedWidth(40)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)

        cname_label = QLabel("compression:")
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setMinimumWidth(60)

        #-------------------------------------
        #           EXTRA FUNCTIONS
        #-------------------------------------

        self.documentation_button = QPushButton("Documentation")
        self.documentation_button.clicked.connect(documentation_view)
        self.documentation_button.setFixedSize(std_button_size)

        self.remote_viewer_button = QPushButton("Remote Viewer")
        self.remote_viewer_button.clicked.connect(remote_view)
        self.remote_viewer_button.setFixedSize(std_button_size)

        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_project_button.setFixedSize(std_button_size)

        self.new_project_button = QPushButton("New Project")
        self.new_project_button.clicked.connect(self.new_project)
        self.new_project_button.setFixedSize(std_button_size)

        self.save_project_button = QPushButton("Save")
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setFixedSize(std_button_size)

        self.save_project_as_button = QPushButton("Save As...")
        self.save_project_as_button.clicked.connect(self.save_project_as)
        self.save_project_as_button.setFixedSize(std_button_size)

        self.quit_app_button = QPushButton("Exit")
        self.quit_app_button.clicked.connect(self.close)
        self.quit_app_button.setFixedSize(std_button_size)

        self.debug_layer_button = QPushButton("Debug Layer")
        self.debug_layer_button.clicked.connect(debug_layer)
        self.debug_layer_button.setFixedSize(std_button_size)

        self.import_images_button = QPushButton("Import Images")
        self.import_images_button.clicked.connect(self.import_base_images)
        self.import_images_button.setFixedSize(std_button_size)

        self.extra_functions_groupbox = QGroupBox("Main")
        self.extra_functions_layout = QGridLayout()
        self.extra_functions_layout.addWidget(self.documentation_button, 0, 0)
        self.extra_functions_layout.addWidget(self.remote_viewer_button, 0, 1)
        # self.extra_functions_layout.addWidget(self.new_project_button, 1, 0)
        # self.extra_functions_layout.addWidget(self.open_project_button, 1, 1)
        # self.extra_functions_layout.addWidget(self.save_project_as_button, 2, 0)
        # self.extra_functions_layout.addWidget(self.save_project_button, 2, 1)
        self.extra_functions_layout.addWidget(self.quit_app_button, 3, 0)
        self.extra_functions_layout.addWidget(self.import_images_button, 3, 1)

        # self.spacerItem = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        # self.extra_functions_layout.addItem(self.spacerItem)
        self.extra_functions_groupbox.setLayout(self.extra_functions_layout)

        splash_button_size = QSize(200, 60)

        self.splash_documentation_button = QPushButton("Documentation")
        self.splash_documentation_button.clicked.connect(documentation_view)
        self.splash_documentation_button.setFixedSize(splash_button_size)

        self.splash_remote_viewer_button = QPushButton("Remote Viewer")
        self.splash_remote_viewer_button.clicked.connect(remote_view)
        self.splash_remote_viewer_button.setFixedSize(splash_button_size)

        self.splash_open_project_button = QPushButton("Open Project")
        self.splash_open_project_button.clicked.connect(self.open_project)
        self.splash_open_project_button.setFixedSize(splash_button_size)

        self.splash_new_project_button = QPushButton("New Project")
        self.splash_new_project_button.clicked.connect(self.new_project)
        self.splash_new_project_button.setFixedSize(splash_button_size)

        self.splash_save_project_button = QPushButton("Save")
        self.splash_save_project_button.clicked.connect(self.save_project)
        self.splash_save_project_button.setFixedSize(splash_button_size)

        self.splash_save_project_as_button = QPushButton("Save As...")
        self.splash_save_project_as_button.clicked.connect(self.save_project_as)
        self.splash_save_project_as_button.setFixedSize(splash_button_size)

        self.splash_quit_app_button = QPushButton("Exit")
        self.splash_quit_app_button.clicked.connect(self.close)
        self.splash_quit_app_button.setFixedSize(splash_button_size)

        self.splash_debug_layer_button = QPushButton("Debug Layer")
        self.splash_debug_layer_button.clicked.connect(debug_layer)
        self.splash_debug_layer_button.setFixedSize(splash_button_size)

        self.splash_import_images_button = QPushButton("Import Images")
        self.splash_import_images_button.clicked.connect(self.import_base_images)
        self.splash_import_images_button.setFixedSize(splash_button_size)

        self.splash_functions_layout = QGridLayout()
        self.splash_functions_layout.addWidget(self.splash_documentation_button, 0, 0)
        self.splash_functions_layout.addWidget(self.splash_remote_viewer_button, 0, 1)
        self.splash_functions_layout.addWidget(self.splash_new_project_button, 1, 0)
        self.splash_functions_layout.addWidget(self.splash_open_project_button, 1, 1)
        self.splash_functions_layout.addWidget(self.splash_save_project_as_button, 2, 0)
        self.splash_functions_layout.addWidget(self.splash_save_project_button, 2, 1)
        self.splash_functions_layout.addWidget(self.splash_quit_app_button, 3, 0)
        self.splash_functions_layout.addWidget(self.splash_import_images_button, 3, 1)
        self.splash_panel = QWidget()
        self.splash_panel.setLayout(self.splash_functions_layout)

        #-------------------------------------
        #           EXPORT AND VIEW
        #-------------------------------------

        self.n_scales_layout = QHBoxLayout()
        self.n_scales_layout.addWidget(n_scales_label, alignment=Qt.AlignLeft)
        self.n_scales_layout.addWidget(self.n_scales_input, alignment=Qt.AlignRight)

        self.clevel_layout = QHBoxLayout()
        self.clevel_layout.addWidget(clevel_label, alignment=Qt.AlignLeft)
        self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignRight)

        self.cname_layout = QHBoxLayout()
        self.cname_layout.addWidget(cname_label, alignment=Qt.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignRight)

        self.export_settings_layout = QVBoxLayout()
        self.export_settings_layout.addLayout(self.n_scales_layout)
        self.export_settings_layout.addLayout(self.clevel_layout)
        self.export_settings_layout.addLayout(self.cname_layout)
        #        , alignment = Qt.AlignRight

        self.export_and_ng_layout = QVBoxLayout()
        self.export_and_ng_layout.addWidget(self.export_zarr_button, alignment=Qt.AlignCenter)
        self.export_and_ng_layout.addWidget(self.ng_button, alignment=Qt.AlignCenter)

        self.export_and_view_layout = QHBoxLayout()
        self.export_and_view_layout.addLayout(self.export_settings_layout)
        self.export_and_view_layout.addLayout(self.export_and_ng_layout)

        self.export_and_view_groupbox = QGroupBox("Export && View")
        # self.export_and_view_layout.setContentsMargins(400, 0, 0, 0)
        self.export_and_view_groupbox.setLayout(self.export_and_view_layout)

        #-------------------------------------
        #           STATUS
        #-------------------------------------
        # QGridLayout params: row, column, rowSpan, columnSpan

        def update_skips_label():
            skip_list = []
            for layer_index in range(len(project_data['data']['scales'][get_cur_scale()]['alignment_stack'])):
                if project_data['data']['scales'][get_cur_scale()]['alignment_stack'][layer_index]['skip'] == True:
                    skip_list.append(layer_index)
            self.status_skips_label.setText(str(skip_list))  # settext #status

        # #@slot()
        # def update_base_label(self):
        #     skip_list = []
        #     scale = project_data['data']['scales'][project_data['data']['current_scale']]  # print(scale) # returns massive wall of text
        #     layer = scale['alignment_stack'][project_data['data']['current_layer']]
        #     base_file_name = layer['images']['base']['filename']
        #     self.status_base_image_label.setText(str(skip_list))  # settext #status

        self.status_vbox = QVBoxLayout()

        self.status_hbox_skips = QHBoxLayout()
        self.status_skips_label = QLabel("[]")
        self.status_skips_label.setObjectName("status_skips_label");
        self.spacer_item_status_skips = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.status_hbox_skips.addWidget(QLabel("Skips:"), alignment=Qt.AlignLeft)
        self.status_hbox_skips.addWidget(self.status_skips_label, alignment=Qt.AlignLeft)
        self.status_hbox_skips.addSpacerItem(self.spacer_item_status_skips)

        self.status_hbox_base_image = QHBoxLayout()
        self.status_base_image_label = QLabel("[]")
        self.status_base_image_label.setObjectName("base_image_label")
        self.spacer_item_status_base_image = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.status_hbox_base_image.addWidget(QLabel("Base Image:"), alignment=Qt.AlignLeft)
        self.status_hbox_base_image.addWidget(self.status_base_image_label, alignment=Qt.AlignLeft)
        self.status_hbox_base_image.addSpacerItem(self.spacer_item_status_base_image)

        self.status_hbox_ref_image = QHBoxLayout()
        self.status_ref_image_label = QLabel("[]")
        self.status_ref_image_label.setObjectName("ref_image_label")
        self.spacer_item_status_ref_image = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.status_hbox_ref_image.addWidget(QLabel("Ref Image:"), alignment=Qt.AlignLeft)
        self.status_hbox_ref_image.addWidget(self.status_ref_image_label, alignment=Qt.AlignLeft)
        self.status_hbox_ref_image.addSpacerItem(self.spacer_item_status_ref_image)

        self.status_vbox.addLayout(self.status_hbox_skips)
        self.status_vbox.addLayout(self.status_hbox_base_image)
        self.status_vbox.addLayout(self.status_hbox_ref_image)
        # self.status_vbox.addWidget(QHLine())

        # DISPLAY EXTRAS #MAINPANELLAYOUT #VERBOSE
        if enable_stats:  # masterswitch
            self.main_panel_extended_layout.addLayout(self.status_vbox)

        #scale = project_data['data']['scales'][
        #     project_data['data']['current_scale']]  # print(scale) # returns massive wall of text
        # layer = scale['alignment_stack'][project_data['data']['current_layer']]
        # base_file_name = layer['images']['base']['filename']
        # print("current base image = ", base_file_name)

        #-------------------------------------
        #           NEW CONTROLS
        #-------------------------------------
        #controls #controlpanel #newcontrols

        self.center_button = QPushButton('Center')  # center
        self.center_button.clicked.connect(self.center_all_images)
        self.center_button.setFixedSize(std_button_size)
        # self.center_button.setFocusPolicy(Qt.NoFocus)

        # self.define_scales_button = QPushButton('Define Scales')
        # self.define_scales_button.clicked.connect(self.define_scales_callback)
        # self.define_scales_button.setFixedSize(std_button_size)

        # from alignem_swift import generate_scales_queue #generate_scales
        self.generate_scales_button = QPushButton('Generate Scales')
        # self.generate_scales_button.clicked.connect(generate_scales_queue)
        self.generate_scales_button.clicked.connect(generate_scales_queue)
        self.generate_scales_button.setFixedSize(std_button_size)

        self.toggle_skip = ToggleSwitch()  # toggleskip
        self.toggle_skip.setChecked(True)
        self.toggle_skip.toggled.connect(skip_changed_callback)

        #scales #scalescombobox #scaleslist #030
        skip_list = []
        for layer_index in range(len(project_data['data']['scales'][get_cur_scale()]['alignment_stack'])):
            if project_data['data']['scales'][get_cur_scale()]['alignment_stack'][layer_index]['skip'] == True:
                skip_list.append(layer_index)
        # print("skip_list = ", skip_list)
        self.scales_combobox = QComboBox(self)  # thing_to_do #init_ref_app #affine
        # self.scales_combobox.addItems([skip_list])
        # self.scales_combobox.addItems(['--'])
        self.scales_combobox.setFocusPolicy(Qt.NoFocus)
        self.scales_combobox.setMaximumWidth(130)
        # self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

        from alignem_swift import clear_all_skips  # clear_all_skips #skip
        # self.clear_all_skips_button = QPushButton('Clear All Skips')
        self.clear_all_skips_button = QPushButton('Reset Skips')

        # self.select_data_layout = QGridLayout()
        # self.select_data_layout.addWidget(self.toggle_skip, 0, 0, Qt.AlignLeft)
        # self.select_data_layout.addWidget(self.clear_all_skips_button, 1, 0, Qt.AlignLeft)

        self.images_and_scaling_groupbox = QGroupBox("Scaling && Data Selection")
        self.images_and_scaling_layout = QGridLayout()
        self.images_and_scaling_layout.addWidget(self.center_button, 0, 0)
        self.images_and_scaling_layout.addWidget(self.scales_combobox, 1, 0)
        # self.images_and_scaling_layout.addWidget(self.define_scales_button, 0, 1)
        self.images_and_scaling_layout.addWidget(self.generate_scales_button, 1, 1)
        self.images_and_scaling_layout.addWidget(self.toggle_skip, 0, 2)  # center
        self.images_and_scaling_layout.addWidget(self.clear_all_skips_button, 1, 2)
        self.images_and_scaling_groupbox.setLayout(self.images_and_scaling_layout)

        self.affine_combobox = QComboBox(self)  # thing_to_do #init_ref_app #affine
        self.affine_combobox.addItems(['Init Affine', 'Refine Affine', 'Apply Affine'])
        self.affine_combobox.setFocusPolicy(Qt.NoFocus)
        self.affine_combobox.setMaximumWidth(130)

        from alignem_swift import align_all_or_some  # align_all_or_some
        self.align_all_button = QPushButton('Align All')
        self.align_all_button.clicked.connect(align_all_or_some)
        self.align_all_button.setFixedSize(std_button_size)

        self.clear_all_skips_button.setFocusPolicy(Qt.NoFocus)
        self.clear_all_skips_button.clicked.connect(clear_all_skips)
        self.clear_all_skips_button.clicked.connect(update_skips_label)  # status
        self.clear_all_skips_button.setFixedSize(std_button_size)
        # from alignem_swift import view_change_callback
        # self.clear_all_skips_button.clicked.connect(self.update_win_self())
        # self.clear_all_skips_button.clicked.connect(self.update_panels())
        # self.clear_all_skips_button.clicked.connect(self.refresh_all_images())
        # self.clear_all_skips_button.clicked.connect(self.view_change_callback)

        # self.select_data_groupbox = QGroupBox("Select Data")
        # self.select_data_groupbox.setLayout(self.select_data_layout)

        # Not necessary for minimal interface. copy_skips_to_all_scales is already run when 'skip' is set.
        # from alignem_swift import copy_skips_to_all_scales #copy_skips_to_all_scales
        # self.copy_skips_to_all_scales_button = QPushButton('Skips -> All Scales')
        # self.copy_skips_to_all_scales_button.clicked.connect(copy_skips_to_all_scales)
        # self.copy_skips_to_all_scales_button.setFixedSize(QSize(130, 28))

        # whitening QLineEdit
        whitening_label = QLabel("Whitening:")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(70)
        # self.whitening_input.setFocusPolicy(Qt.NoFocus) #prevents text entry at runtime
        # self.whitening_valid = QDoubleValidator(-5.0, 5.0, 2, self)
        self.whitening_input.setValidator(QDoubleValidator(-5.0, 5.0, 2, self))

        # swim window QLineEdit
        swim_label = QLabel("SWIM Window:")
        # n_scales_label.setAlignment(Qt.AlignRight)
        self.swim_input = QLineEdit(self)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(70)
        # self.swim_input.setFocusPolicy(Qt.NoFocus) #prevents text entry at runtime
        # self.n_scales_valid = QDoubleValidator(0.0000, 1.0000, 4, self)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))

        self.alignment_groupbox = QGroupBox("Alignment")
        self.images_and_scaling_groupbox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.alignment_layout = QGridLayout()
        self.whitening_grid = QGridLayout()
        self.whitening_grid.addWidget(whitening_label, 0, 0, alignment=Qt.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignRight)
        self.swim_grid = QGridLayout()
        self.swim_grid.addWidget(swim_label, 0, 0, alignment=Qt.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignRight)

        # groups #grouplocation #controlpanel
        self.alignment_layout.addLayout(self.whitening_grid, 0, 0)
        self.alignment_layout.addLayout(self.swim_grid, 1, 0)
        self.alignment_layout.addWidget(self.affine_combobox, 0, 1)
        self.alignment_layout.addWidget(self.align_all_button, 1, 1)  # align_all
        # self.improved_controls_layout.addWidget(self.copy_skips_to_all_scales_button, alignment=Qt.AlignLeft) #not necessary
        # self.spacerItem2 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        # self.improved_controls_layout.addItem(self.spacerItem2)
        self.alignment_groupbox.setLayout(self.alignment_layout)

        # self.divider.addWidget(QHLine(), 0, 0, 1, 2)
        # self.divider.addWidget(QLabel("New Control Panel:"), 1, 0, 1, 1)
        # self.divider.addWidget(QHLine(), 2, 0, 1, 2)

        # ADD TO 'main_panel_layout' #mainpanellayout #maximumsize #groups #groupsize
        self.extra_functions_groupbox.setMaximumWidth(300)
        self.images_and_scaling_groupbox.setMaximumWidth(500)
        # self.select_data_groupbox.setMaximumWidth(350)
        self.alignment_groupbox.setMaximumWidth(400)
        self.export_and_view_groupbox.setMaximumWidth(400)

        self.lower_panel_groups = QGridLayout()
        self.images_and_scaling_groupbox.setAlignment(Qt.AlignLeft)
        self.alignment_groupbox.setAlignment(Qt.AlignLeft)
        self.lower_panel_groups.addWidget(self.extra_functions_groupbox, 0, 0)
        self.lower_panel_groups.addWidget(self.images_and_scaling_groupbox, 0, 1)
        # self.lower_panel_groups.addWidget(self.select_data_groupbox, 0, 2)
        self.lower_panel_groups.addWidget(self.alignment_groupbox, 0, 2)
        self.lower_panel_groups.addWidget(self.export_and_view_groupbox, 0, 3)
        self.main_panel_layout.addLayout(self.lower_panel_groups)  #mainpanellayout

        ##########docs_panel DOCUMENTATION PANEL
        self.browser = QWebEngineView()
        self.browser_docs = QWebEngineView()
        # self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/README.md'))
        # self.browser_docs.setUrl(QUrl('https://github1s.com/mcellteam/swift-ir/blob/development/README.md'))

        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(std_button_size)
        self.exit_docs_button.clicked.connect(exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(std_button_size)
        self.readme_button.clicked.connect(documentation_view_home)
        self.docs_panel = QWidget()  # create QWidget()
        self.docs_panel_layout = QVBoxLayout()  # create QVBoxLayout()
        self.docs_panel_layout.addWidget(self.browser_docs)  # add widgets
        self.docs_panel_controls_layout = QHBoxLayout()
        # self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignLeft | Qt.AlignBottom)   # go back button
        self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignLeft)  # go back button
        self.docs_panel_controls_layout.addWidget(self.readme_button, alignment=Qt.AlignLeft)  # go back button
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.docs_panel_controls_layout.addSpacerItem(self.spacer_item_docs)
        # layout.setContentsMargins(left, top, right, bottom)
        # self.docs_panel_controls_layout.setContentsMargins(0, 0, 1300, 0)
        self.docs_panel_layout.addLayout(self.docs_panel_controls_layout)  # add horizontal layout
        self.docs_panel.setLayout(self.docs_panel_layout)  # set layout

        ##########remote_viewer_panel REMOTE VIEWER PANEL
        self.browser_remote = QWebEngineView()
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))  # tacctacc
        # self.browser_remote.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.exit_remote_button = QPushButton("Back")
        self.exit_remote_button.setFixedSize(std_button_size)
        self.exit_remote_button.clicked.connect(exit_remote)
        self.reload_remote_button = QPushButton("Reload")
        self.reload_remote_button.setFixedSize(std_button_size)
        self.reload_remote_button.clicked.connect(reload_remote)
        self.remote_viewer_panel = QWidget()  # create QWidget()
        self.remote_viewer_panel_layout = QVBoxLayout()  # create QVBoxLayout()
        self.remote_viewer_panel_layout.addWidget(self.browser_remote)  # add widgets
        self.remote_viewer_panel_controls_layout = QHBoxLayout()
        self.remote_viewer_panel_controls_layout.addWidget(self.exit_remote_button,
                                                           alignment=Qt.AlignLeft)  # go back button
        self.remote_viewer_panel_controls_layout.addWidget(self.reload_remote_button, alignment=Qt.AlignLeft)
        self.spacer_item_remote_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.remote_viewer_panel_controls_layout.addSpacerItem(self.spacer_item_remote_panel)
        self.remote_viewer_panel_layout.addLayout(self.remote_viewer_panel_controls_layout)  # add horizontal layout
        self.remote_viewer_panel.setLayout(self.remote_viewer_panel_layout)  # set layout

        # ##########remote_viewer_panel MICRONS DATA SET VIEWER PANEL
        # self.browser_microns = QWebEngineView()
        # self.browser_microns.setUrl(QUrl('https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v0/son_of_alignment_v15_rechunked%22%2C%22type%22:%22image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22EM%22%7D%2C%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v185/seg%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22:0.51%2C%22segments%22:%5B%22648518346349538235%22%2C%22648518346349539462%22%2C%22648518346349539853%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22cell_segmentation_v185%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-clefts/mip1_d2_1175k%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22synapses%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-mito/seg_191220%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22mitochondria%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-nuclei/seg%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22nuclei%22%7D%5D%2C%22navigation%22:%7B%22pose%22:%7B%22position%22:%7B%22voxelSize%22:%5B4%2C4%2C40%5D%2C%22voxelCoordinates%22:%5B83222.921875%2C52981.34765625%2C834.9962768554688%5D%7D%7D%2C%22zoomFactor%22:383.0066650796121%7D%2C%22perspectiveOrientation%22:%5B-0.00825042650103569%2C0.06130112707614899%2C-0.0012821174459531903%2C0.9980843663215637%5D%2C%22perspectiveZoom%22:3618.7659948513424%2C%22showSlices%22:false%2C%22selectedLayer%22:%7B%22layer%22:%22cell_segmentation_v185%22%7D%2C%22layout%22:%7B%22type%22:%22xy-3d%22%2C%22orthographicProjection%22:true%7D%7D'))
        # self.exit_microns_button = QPushButton("Back")
        # self.exit_microns_button.setFixedSize(QSize(100, 28))
        # self.exit_microns_button.clicked.connect(exit_microns)
        # self.microns_panel = QWidget()                                              # create QWidget()
        # self.microns_panel_layout = QVBoxLayout()                                   # create QVBoxLayout()
        # self.microns_panel_layout.addWidget(self.browser_microns)                    # add widgets
        # self.microns_panel_controls_layout = QHBoxLayout()
        # self.microns_panel_controls_layout.addWidget(self.exit_microns_button, alignment=Qt.AlignLeft)   # go back button
        # self.microns_panel_layout.addLayout(self.microns_panel_controls_layout)        # add horizontal layout
        # self.microns_panel.setLayout(self.microns_panel_layout)                      # set layout

        ##########demos_panel DEMOS PANEL
        self.exit_demos_button = QPushButton("Back")
        self.exit_demos_button.setFixedSize(std_button_size)
        self.exit_demos_button.clicked.connect(exit_demos)
        self.demos_panel = QWidget()  # create QWidget()
        self.demos_panel_layout = QVBoxLayout()  # create QVBoxLayout()
        self.demos_panel_controls_layout = QHBoxLayout()
        self.demos_panel_controls_layout.addWidget(self.exit_demos_button)  # go back button
        self.demos_panel_layout.addLayout(self.demos_panel_controls_layout)  # add horizontal layout
        self.demos_panel.setLayout(self.demos_panel_layout)  # set layout
        # self.demos_panel_layout.addWidget(self.browser)            # add widgets

        ##########ngpanel NEUROGLANCER CONTROLS PANEL
        self.exit_ng_button = QPushButton("Back")
        self.exit_ng_button.setFixedSize(std_button_size)
        self.exit_ng_button.clicked.connect(exit_ng)
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(std_button_size)
        self.reload_ng_button.clicked.connect(reload_ng)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(std_button_size)
        self.print_state_ng_button.clicked.connect(print_state_ng)
        self.print_url_ng_button = QPushButton("Print URL")
        self.print_url_ng_button.setFixedSize(std_button_size)
        self.print_url_ng_button.clicked.connect(print_url_ng)
        # self.screenshot_ng_button = QPushButton("Screenshot")
        # self.screenshot_ng_button.setFixedSize(QSize(100, 28))
        # self.screenshot_ng_button.clicked.connect(screenshot_ng)
        # self.blend_ng_button = QPushButton("Blend (b)")
        # self.blend_ng_button.setFixedSize(QSize(100, 28))
        # self.blend_ng_button.clicked.connect(blend_ng)
        self.ng_panel = QWidget()  # create QWidget()
        self.ng_panel_layout = QVBoxLayout()  # create QVBoxLayout()
        self.ng_panel_layout.addWidget(self.browser)  # add widgets
        # layout.setContentsMargins(left, top, right, bottom)
        # self.ng_panel_controls_layout.setContentsMargins(500, 0, 0, 0)
        # self.ng_panel_controls_layout.addWidget(self.spacerItem)
        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignLeft)  # back button
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignLeft)  # reload button
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignLeft)  # reload button
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignLeft)  # reload button
        # self.ng_panel_controls_layout.addWidget(self.screenshot_ng_button, alignment=Qt.AlignLeft)  # reload button
        # self.ng_panel_controls_layout.addWidget(self.blend_ng_button, alignment=Qt.AlignLeft)  # reload button
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)  # add horizontal layout
        self.ng_panel.setLayout(self.ng_panel_layout)  # set layout

        # self.spacerItem = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) # not working

        # stack GUI elements
        # stackedlayout STACKED WIDGET
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(self.main_panel)  # (0) main_panel
        self.stacked_widget.addWidget(self.ng_panel)  # (1) ng_panel
        self.stacked_widget.addWidget(self.docs_panel)  # (2) docs_panel
        self.stacked_widget.addWidget(self.demos_panel)  # (3) demos_panel
        self.stacked_widget.addWidget(self.remote_viewer_panel)  # (4) docs_panel
        self.stacked_widget.addWidget(self.splash_panel)  # (5) splash_panel

        self.stacked_widget.setCurrentIndex(0)

        # This can be invisible, will still use to organize QStackedWidget
        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem("Main")
        self.pageComboBox.addItem("Neuroglancer Local")
        self.pageComboBox.addItem("Documentation")
        self.pageComboBox.addItem("Demos")
        self.pageComboBox.addItem("Remote Viewer")
        self.pageComboBox.addItem("Splash")
        self.pageComboBox.activated[int].connect(self.stacked_widget.setCurrentIndex)
        # self.pageComboBox.activated.connect(self.stackedLayout.setCurrentIndex)

        self.stacked_layout = QVBoxLayout()
        self.stacked_layout.addWidget(self.stacked_widget)
        self.setCentralWidget(self.stacked_widget)  # setCentralWidget to QStackedWidget

        # verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        #menu Menu Bar
        self.action_groups = {}
        self.menu = self.menuBar()
        print("Setting setNativeMenuBar to False for an attached menubar on macOS...")
        self.menu.setNativeMenuBar(False)  # fix to set non-native menubar in macOS

        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
            ['&File',
             [
                 ['&New Project', 'Ctrl+N', self.new_project, None, None, None],
                 ['&Open Project', 'Ctrl+O', self.open_project, None, None, None],
                 ['&Save Project', 'Ctrl+S', self.save_project, None, None, None],
                 ['Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None],
                 ['-', None, None, None, None, None],
                 ['Save &Cropped As...', None, self.save_cropped_as, None, None, None],
                 ['-', None, None, None, None, None],
                 ['Set Project Destination', None, self.set_def_proj_dest, None, None, None],
                 ['-', None, None, None, None, None],
                 ['Set Custom Destination...', None, self.set_destination, None, None, None],
                 ['-', None, None, None, None, None],
                 ['E&xit', 'Ctrl+Q', self.exit_app, None, None, None]
             ]
             ],
            # [ '&Images',
            #   [
            #     [ 'Define Roles', None, self.define_roles_callback, None, None, None ],
            #     [ 'Import &Base Images', None, self.import_base_images, None, None, None ],
            #     [ '-', None, None, None, None, None ],
            #     [ '&Import into',
            #       [
            #         # Empty list to hold the dynamic roles as defined above
            #       ]
            #     ],
            #     [ '&Empty into',
            #       [
            #         # Empty list to hold the dynamic roles as defined above
            #       ]
            #     ],
            #     [ '-', None, None, None, None, None ],
            #     [ 'Center', None, self.center_all_images, None, None, None ],
            #     [ 'Actual Size', None, self.all_images_actual_size, None, None, None ],
            #     [ 'Refresh', None, self.not_yet, None, None, None ],
            #     [ '-', None, None, None, None, None ],
            #     [ 'Clear Role',
            #       [
            #         # Empty list to hold the dynamic roles as defined above
            #       ]
            #     ],
            #     [ 'Remove this Layer', None, self.remove_this_layer, None, None, None ],
            #     [ 'Remove ALL Layers', None, self.remove_all_layers, None, None, None ],
            #     # [ 'Remove ALL Panels', None, self.remove_all_panels, None, None, None ]
            #     [ 'Remove ALL Panels', None, self.not_yet, None, None, None ]
            #   ]
            # ],
            # [ '&Scaling',  # Note that this can NOT contain the string "Scale". "Scaling" is OK.
            #   [
            #     [ '&Define Scales', None, self.define_scales_callback, None, None, None ],
            #     [ '&Generate Scales', None, self.generate_scales_callback, None, None, None ],
            #     [ '&Generate Scales', None, self.not_yet, None, None, None ],
            #     [ '&Import All Scales', None, self.not_yet, None, None, None ],
            #     [ '-', None, None, None, None, None ],
            #     [ '&Generate Tiled', None, self.not_yet, False, None, None ],
            #     [ '&Import Tiled', None, self.not_yet, False, None, None ],
            #     [ '&Show Tiled', None, self.not_yet, False, None, None ]
            #   ]
            # ],
            # [ '&Scale',
            #   [
            #     [ '&Scale 1', None, self.do_nothing, True, "Scales", None ]
            #   ]
            # ],
            # [ '&Points',
            #   [
            #     [ '&Alignment Point Mode', None, self.not_yet, False, None, None ],
            #     [ '&Delete Points', None, self.not_yet, False, None, None ],
            #     [ '&Clear All Alignment Points', None, self.not_yet, None, None, None ],
            #     [ '-', None, None, None, None, None ],
            #     [ '&Point Cursor',
            #       [
            #         [ 'Crosshair', None, self.not_yet, True, "Cursor", None ],
            #         [ 'Target', None, self.not_yet, False, "Cursor", None ]
            #       ]
            #     ]
            #   ]
            # ],
            # [ '&Set',
            ['&Advanced',
             [
                 ['&Max Image Size', 'Ctrl+M', self.set_max_image_size, None, None, None],
                 ['Crop Size',
                  [
                      ['Square', None, self.set_crop_square, False, "CropSize", None],
                      ['Rectangular', None, self.set_crop_rect, True, "CropSize", None],
                      ['Fixed Size', None, self.set_crop_fixed, False, "CropSize", None]
                  ]
                  ],
                 ['-', None, None, None, None, None],
                 ['Num to Preload', None, self.set_preloading_range, None, None, None],
                 ['Threaded Loading', None, self.toggle_threaded_loading, image_library.threaded_loading_enabled, None,
                  None],
                 # [ '-', None, None, None, None, None ],
                 # [ 'Background Color', None, self.set_bg_color, None, None, None ],
                 # [ 'Border Color', None, self.set_border_color, None, None, None ],
                 ['-', None, None, None, None, None],
                 ['Perform Swims', None, self.not_yet, True, None, None],
                 ['Update CFMs', None, self.not_yet, True, None, None],
                 ['Generate Images', None, self.not_yet, True, None, None],
                 ['-', None, None, None, None, None],
                 ['Use C Version', None, self.do_nothing, use_c_version, None, None],
                 ['Use File I/O', None, self.do_nothing, use_file_io, None, None],
                 ['-', None, None, None, None, None],
                 ['Unlimited Zoom', None, self.not_yet, False, None, None],
                 ['Reverse Arrow Keys', None, self.toggle_arrow_direction, False, None, None],
                 ['-', None, None, None, None, None],
                 ['Default Plot Code', None, self.not_yet, None, None, None],
                 ['Custom Plot Code', None, self.not_yet, None, None, None]
             ]
             ],
            # [ '&Show',
            #   [
            #     [ 'Borders', None, self.toggle_border, False, None, None ],
            #     [ 'Window Centers', None, self.not_yet, False, None, None ],
            #     [ 'Affines', None, self.not_yet, False, None, None ],
            #     [ 'Skipped Images', None, self.toggle_show_skipped, show_skipped_images, None, None ],
            #     [ '-', None, None, None, None, None ],
            #     [ 'Plot', None, self.not_yet, None, None, None ],
            #     [ '-', None, None, None, None, None ],
            #     [ 'Annotations', None, self.toggle_annotations, True, None, None ],
            #     [ 'Full Paths', None, self.toggle_full_paths, False, None, None ]
            #   ]
            # ],
            ['&Debug',
             [
                 ['&Python Console', 'Ctrl+P', self.py_console, None, None, None],
                 ['-', None, None, None, None, None],
                 ['Print Structures', None, self.print_structures, None, None, None],
                 ['-', None, None, None, None, None],
                 ['Print Image Library', None, self.print_image_library, None, None, None],
                 ['-', None, None, None, None, None],
                 ['Debug Layer', None, debug_layer, None, None, None],
                 ['-', None, None, None, None, None],
                 ['update_win_self', None, self.update_win_self, None, None, None],
                 ['-', None, None, None, None, None],
                 ['update_panels', None, self.update_panels, None, None, None],
                 ['-', None, None, None, None, None],
                 ['refresh_all_images', None, self.refresh_all_images, None, None, None],
                 ['-', None, None, None, None, None],
                 # ['Define Waves', None, self.not_yet, None, None, None],
                 # ['Make Waves', None, self.not_yet, None, None, None],
                 # ['-', None, None, None, None, None],
                 # ['Define Grid', None, self.not_yet, None, None, None],
                 # ['Grid Align', None, self.not_yet, None, None, None],
                 # ['-', None, None, None, None, None],
                 # ['Show Waves', None, self.not_yet, False, "GridMode", None],
                 # ['Show Grid Align', None, self.not_yet, False, "GridMode", None],
                 # ['Show Aligned', None, self.not_yet, True, "GridMode", None],
                 # ['-', None, None, None, None, None],
                 # ['&Set Debug Level',
                 #  [
                 #      ['Level 0', None, self.set_debug_level, DEBUG_LEVEL == 0, "DebugLevel", 0],
                 #      ['Level 1', None, self.set_debug_level, DEBUG_LEVEL == 1, "DebugLevel", 1],
                 #      ['Level 2', None, self.set_debug_level, DEBUG_LEVEL == 2, "DebugLevel", 2],
                 #      ['Level 3', None, self.set_debug_level, DEBUG_LEVEL == 3, "DebugLevel", 3],
                 #      ['Level 4', None, self.set_debug_level, DEBUG_LEVEL == 4, "DebugLevel", 4],
                 #      ['Level 5', None, self.set_debug_level, DEBUG_LEVEL == 5, "DebugLevel", 5],
                 #      ['Level 6', None, self.set_debug_level, DEBUG_LEVEL == 6, "DebugLevel", 6],
                 #      ['Level 7', None, self.set_debug_level, DEBUG_LEVEL == 7, "DebugLevel", 7],
                 #      ['Level 8', None, self.set_debug_level, DEBUG_LEVEL == 8, "DebugLevel", 8],
                 #      ['Level 9', None, self.set_debug_level, DEBUG_LEVEL == 9, "DebugLevel", 9],
                 #      ['Level 10', None, self.set_debug_level, DEBUG_LEVEL == 10, "DebugLevel", 10],
                 #      ['Level 20', None, self.set_debug_level, DEBUG_LEVEL == 20, "DebugLevel", 20],
                 #      ['Level 30', None, self.set_debug_level, DEBUG_LEVEL == 30, "DebugLevel", 30],
                 #      ['Level 40', None, self.set_debug_level, DEBUG_LEVEL == 40, "DebugLevel", 40],
                 #      ['Level 50', None, self.set_debug_level, DEBUG_LEVEL == 50, "DebugLevel", 50],
                 #      ['Level 60', None, self.set_debug_level, DEBUG_LEVEL == 60, "DebugLevel", 60],
                 #      ['Level 70', None, self.set_debug_level, DEBUG_LEVEL == 70, "DebugLevel", 70],
                 #      ['Level 80', None, self.set_debug_level, DEBUG_LEVEL == 80, "DebugLevel", 80],
                 #      ['Level 90', None, self.set_debug_level, DEBUG_LEVEL == 90, "DebugLevel", 90],
                 #      ['Level 100', None, self.set_debug_level, DEBUG_LEVEL == 100, "DebugLevel", 100]
                 #  ]
                 #  ]
             ]
             ],
            # ['&Help',
            #  [
            #      ['About...', None, self.not_yet, None, None, None],
            #  ]
            #  ]
        ]

        # This could be used to optionally simplify menus:
        '''
        if simple_mode:
            ml[0] = [ '&File',
                [
                  [ '&New Project', 'Ctrl+N', self.new_project, None, None, None ],
                  [ '&Open Project', 'Ctrl+O', self.open_project, None, None, None ],
                  [ '&Save Project', 'Ctrl+S', self.save_project, None, None, None ],
                  [ 'Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Save &Cropped As...', None, self.save_cropped_as, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'E&xit', 'Ctrl+Q', self.exit_app, None, None, None ]
                ]
              ]
              
        '''

        self.build_menu_from_list(self.menu, ml)

        # Status Bar
        self.status = self.statusBar()
        if fname == None:
            self.status.showMessage("No Project Yet ...")
        else:
            # self.status.showMessage("File: "+fname)
            self.status.showMessage("File: unknown")

        # Window dimensions
        # geometry = qApp.desktop().availableGeometry(self)
        # self.setFixedSize(geometry.width() * 0.8, geometry.height() * 0.7)
        # self.setMinimumWidth(600) self.setMinimumHeight(400) self.resize(2000,1000) # original #jy
        # self.setMinimumWidth(600)
        # self.setMinimumHeight(400)
        # self.resize(2000,1000)
        self.setMinimumWidth(800)
        self.setMinimumHeight(400)
        self.resize(2000, 1200)

        # self.setCentralWidget(self.image_hbox)
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    if enable_stats:  # masterswitch
        def update_base_label(self):
            scale = project_data['data']['scales'][
                project_data['data']['current_scale']]
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
            base_file_name = layer['images']['base']['filename']
            self.status_base_image_label.setText(os.path.basename(base_file_name))  # settext #status

        def update_ref_label(self):
            scale = project_data['data']['scales'][
                project_data['data']['current_scale']]
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
            ref_file_name = layer['images']['ref']['filename']
            self.status_ref_image_label.setText(os.path.basename(ref_file_name))  # settext #status

    def update_win_self(self):
        print("  MainWindow is updating itself (called by " + inspect.stack()[1].function + ")...")
        # self.center_all_images()  # uncommenting causes centering issues to re-emerge
        self.update() #repaint

    def build_menu_from_list(self, parent, menu_list):
        # Get the group names first
        for item in menu_list:
            if type(item[1]) == type([]):
                # This is a submenu
                pass
            else:
                # This is a menu item (action) or a separator
                if item[4] != None:
                    # This is a group name so add it as needed
                    if not (item[4] in self.action_groups):
                        # This is a new group:
                        self.action_groups[item[4]] = QActionGroup(self)

        for item in menu_list:
            if type(item[1]) == type([]):
                # This is a submenu
                sub = parent.addMenu(item[0])
                self.build_menu_from_list(sub, item[1])
            else:
                # This is a menu item (action) or a separator
                if item[0] == '-':
                    # This is a separator
                    parent.addSeparator()
                else:
                    # This is a menu item (action) with name, accel, callback
                    action = QAction(item[0], self)
                    if item[1] != None:
                        action.setShortcut(item[1])
                    if item[2] != None:
                        action.triggered.connect(item[2])
                        if item[2] == self.not_yet:
                            action.setDisabled(True)
                    if item[3] != None:
                        action.setCheckable(True)
                        action.setChecked(item[3])
                    if item[4] != None:
                        self.action_groups[item[4]].addAction(action)

                    parent.addAction(action)

    @countit
    @Slot()  #scales #030
    def reload_scales_combobox(self):
        curr_scale = project_data['data']['current_scale']
        image_scales_to_run = [get_scale_val(s) for s in sorted(project_data['data']['scales'].keys())]
        print("reload_scales_combobox was called by " + inspect.stack()[
            1].function + " | curr scale: " + curr_scale + " | scales: " + str(image_scales_to_run))
        self.scales_combobox.clear()

        for scale in sorted(image_scales_to_run):
            self.scales_combobox.addItems(["scale_" + str(scale)])

        index = self.scales_combobox.findText(curr_scale, Qt.MatchFixedString)
        if index >= 0:
            self.scales_combobox.setCurrentIndex(index)

    # method called by combo box
    @Slot()  #scales #030
    def fn_scales_combobox(self):
        print("\n(!) scales_combobox text has changed. Entering fn_scales_combobox scope...")
        print("  self.scales_combobox.currentText() = ", self.scales_combobox.currentText())
        new_curr_scale = self.scales_combobox.currentText()  # ~ set_selected_scale ->  Line 5086 #030
        # print("type(new_curr_scale) = ", type(new_curr_scale)) #  <class 'str'>
        if new_curr_scale is None:
            print("new_curr_scale is None")
        if new_curr_scale == '':
            print("new_curr_scale is empty string")
        project_data['data']['current_scale'] = new_curr_scale
        self.center_all_images()

    @Slot()
    def get_whitening_input(self):
        return self.whitening_input.text()

    @Slot()
    def get_swim_input(self):
        return self.swim_input.text()

    @Slot()
    def do_nothing(self, checked):
        print_debug(90, "Doing Nothing")
        pass

    @Slot()
    def not_yet(self):
        print_debug(30, "Function is not implemented yet")

    @Slot()
    def toggle_annotations(self, checked):
        print_debug(30, "Toggling Annotations")

    @Slot()
    def toggle_full_paths(self, checked):
        print_debug(30, "Toggling Full Paths")

    @Slot()
    def toggle_show_skipped(self, checked):
        print_debug(30, "Toggling Show Skipped with checked = " + str(checked))
        global show_skipped_images
        show_skipped_images = checked

    @Slot()
    def set_debug_level(self, checked):
        global DEBUG_LEVEL
        action_text = self.sender().text()
        try:
            value = int(action_text.split(' ')[1])
            print_debug(5, "Changing Debug Level from " + str(DEBUG_LEVEL) + " to " + str(value))
            DEBUG_LEVEL = value
            try:
                print_debug(5, "Changing TUI Debug Level from " + str(pyswift_tui.DEBUG_LEVEL) + " to " + str(value))
                pyswift_tui.DEBUG_LEVEL = value
                try:
                    print_debug(5, "Changing SWIFT Debug Level from " + str(align_swiftir.DEBUG_LEVEL) + " to " + str(
                        value))
                    align_swiftir.DEBUG_LEVEL = value
                except:
                    print_debug(1, "Unable to change SWIFT Debug Level")
                    pass
            except:
                print_debug(1, "Unable to change TUI Debug Level")
                pass
        except:
            print_debug(1, "Invalid debug value in: \"" + str(action_text))

    @Slot()
    def print_structures(self, checked):
        global DEBUG_LEVEL
        print("\n:::DATA STRUCTURES:::")
        print_debug(2, "  project_data['version'] = " + str(project_data['version']))
        print_debug(2, "  project_data.keys() = " + str(project_data.keys()))
        print_debug(2, "  project_data['data'].keys() = " + str(project_data['data'].keys()))
        print_debug(2, "  project_data['data']['panel_roles'] = " + str(project_data['data']['panel_roles']))
        scale_keys = list(project_data['data']['scales'].keys())
        print_debug(2, "  list(project_data['data']['scales'].keys()) = " + str(scale_keys))
        print_debug(2, "Scales, Layers, and Images:")
        for k in sorted(scale_keys):
            # print_debug ( 2, "  Scale key: " + str(k) +
            #               ", NullBias: " + str(project_data['data']['scales'][k]['null_cafm_trends']) +
            #               ", Bounding Rect: " + str(project_data['data']['scales'][k]['use_bounding_rect']) )
            scale = project_data['data']['scales'][k]
            for layer in scale['alignment_stack']:
                print_debug(2, "    Layer: " + str([k for k in layer['images'].keys()]))
                for role in layer['images'].keys():
                    im = layer['images'][role]
                    print_debug(2, "      " + str(role) + ": " + str(layer['images'][role]['filename']))

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    @Slot()
    def print_image_library(self, checked):
        print("\n:::IMAGE LAYER:::")
        print(str(image_library))

    def make_relative(self, file_path, proj_path):
        print_debug(20, "Proj path: " + str(proj_path))
        print_debug(20, "File path: " + str(file_path))
        rel_path = os.path.relpath(file_path, start=os.path.split(proj_path)[0])
        print_debug(20, "Full path: " + str(file_path))
        print_debug(20, "Relative path: " + str(rel_path))
        print_debug(20, "")
        return rel_path

    def make_absolute(self, file_path, proj_path):
        print_debug(20, "Proj path: " + str(proj_path))
        print_debug(20, "File path: " + str(file_path))
        abs_path = os.path.join(os.path.split(proj_path)[0], file_path)
        print_debug(20, "Full path: " + str(file_path))
        print_debug(20, "Absolute path: " + str(abs_path))
        print_debug(20, "")
        return abs_path

    @Slot()
    def new_project(self):
        print("MainWindow has been asked to make a new project...")
        print("Trying to disconnect scales_combobox from all handlers...")
        try:
            self.scales_combobox.disconnect()
        except Exception:
            print(
                "BenignException: could not disconnect scales_combobox from handlers or nothing to disconnect. Continuing...")

        make_new = request_confirmation("Are you sure?",
                                        "Really quit? Unsaved progress will be unrecoverable like George Clooney and Sandra Bullock drifting through space.")
        if (make_new):
            global project_data
            project_data = copy.deepcopy(new_project_template)
            self.current_project_file_name = None
            project_data['data']['destination_path'] = None

            self.set_scales_from_string("1")
            # self.define_scales_menu ( ["1"] ) #jy-remove

            self.scales_combobox.clear()
            # self.scales_combobox.addItems(['--'])

            self.setWindowTitle("No Project File")
            self.status.showMessage("Project File:       Destination: ")
            self.actual_size()
        print("Connecting scales_combobox to fn_scales_combobox handler...")
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

    @Slot()
    def open_project(self):
        print("\nMainWindow has been asked to open a project. Waiting for user...\n")
        print("Trying to disconnect scales_combobox from all handlers...")
        try:
            self.scales_combobox.disconnect()
        except Exception:
            print(
                "BenignException: could not disconnect scales_combobox from handlers or nothing to disconnect. Continuing...")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, filter = QFileDialog.getOpenFileName(parent=None,  # None was self
                                                        caption="Open Project",
                                                        filter="Projects (*.json);;All Files (*)",
                                                        selectedFilter="",
                                                        options=options)
        print("  Opening project: " + str(file_name) + "...")

        if file_name != None:
            if len(file_name) > 0:

                ignore_changes = True

                f = open(file_name, 'r')
                text = f.read()
                f.close()

                # Read the JSON file from the text
                global project_data
                proj_copy = json.loads(text)

                # Upgrade the "Data Model"
                proj_copy = upgrade_data_model(proj_copy)

                if proj_copy == None:
                    # There was an unknown error loading the data model
                    print("open_project > Unable to load project (loaded as None)")
                elif type(proj_copy) == type('abc'):  # abc = abstract base class
                    # There was a known error loading the data model
                    print("open_project > Error loading project:")
                    print("  " + proj_copy)
                else:
                    # The data model loaded fine, so initialize the application with the data

                    self.current_project_file_name = file_name
                    self.status.showMessage("  Loading Project File " + self.current_project_file_name
                                            + "  Destination: " + str(proj_copy['data']['destination_path']))

                    # Modify the copy to use absolute paths internally
                    if 'destination_path' in proj_copy['data']:
                        if proj_copy['data']['destination_path'] != None:
                            if len(proj_copy['data']['destination_path']) > 0:
                                proj_copy['data']['destination_path'] = self.make_absolute(
                                    proj_copy['data']['destination_path'], self.current_project_file_name)
                    for scale_key in proj_copy['data']['scales'].keys():
                        scale_dict = proj_copy['data']['scales'][scale_key]
                        for layer in scale_dict['alignment_stack']:
                            for role in layer['images'].keys():
                                if layer['images'][role]['filename'] != None:
                                    if len(layer['images'][role]['filename']) > 0:
                                        layer['images'][role]['filename'] = self.make_absolute(
                                            layer['images'][role]['filename'], self.current_project_file_name)

                    # Replace the current version with the copy
                    project_data = copy.deepcopy(proj_copy)

                    # Get the roles from the JSON project:
                    # if project_data != None:
                    #    if 'data' in project_data:
                    #        if 'panel_roles' in project_data['data']:
                    #            if len(project_data['data']['panel_roles']) > 0:
                    #                self.define_roles ( project_data['data']['panel_roles'] )

                    # Force the currently displayed fields to reflect the newly loaded data
                    if self.view_change_callback != None:
                        if project_data != None:
                            if 'data' in project_data:
                                if 'current_layer' in project_data['data']:
                                    layer_num = project_data['data']['current_layer']
                                    scale_key = project_data['data']['current_scale']
                                    print_debug(3,
                                                "Open Project is forcing values into fields by calling view_change_callback...")
                                    self.view_change_callback(scale_key, scale_key, layer_num, layer_num,
                                                              True)  # view_change_callback

                    if self.draw_full_paths:
                        self.setWindowTitle("Project: " + self.current_project_file_name)
                    else:
                        self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1])

                ignore_changes = False

        print_all_skips()

        print("  open_project > updating image library (image_library.update)...")
        image_library.update()
        print("  open_project > setting project destination (set_def_proj_dest)...")
        self.set_def_proj_dest()
        print("  open_project > centering all images...")
        self.center_all_images()

        # Set the currently selected scale from the JSON project data
        print("  setting current scale to " + str(project_data['data']['current_scale']))
        # self.set_selected_scale ( project_data['data']['current_scale'] ) #bob
        self.reload_scales_combobox()  #jy

        # connect
        print("Connecting scales_combobox to fn_scales_combobox handler...")
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

    def save_project_to_current_file(self):
        print(
            "Saving project to current file (MainWindow.save_project_to_current_file was called by " + inspect.stack()[
                1].function + ")...")
        # Save to current file and make known file paths relative to the project file name
        if self.current_project_file_name != None:
            if len(self.current_project_file_name) > 0:
                # Write out the project
                if not self.current_project_file_name.endswith('.json'):
                    self.current_project_file_name = self.current_project_file_name + ".json"
                print_debug(0, "Saving to: \"" + str(self.current_project_file_name) + "\"")
                proj_copy = copy.deepcopy(project_data)
                if project_data['data']['destination_path'] != None:
                    if len(proj_copy['data']['destination_path']) > 0:
                        proj_copy['data']['destination_path'] = self.make_relative(
                            proj_copy['data']['destination_path'], self.current_project_file_name)
                for scale_key in proj_copy['data']['scales'].keys():
                    scale_dict = proj_copy['data']['scales'][scale_key]
                    for layer in scale_dict['alignment_stack']:
                        for role in layer['images'].keys():
                            if layer['images'][role]['filename'] != None:
                                if len(layer['images'][role]['filename']) > 0:
                                    layer['images'][role]['filename'] = self.make_relative(
                                        layer['images'][role]['filename'], self.current_project_file_name)
                f = open(self.current_project_file_name, 'w')
                jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                proj_json = jde.encode(proj_copy)
                f.write(proj_json)
                f.close()

                if self.draw_full_paths:
                    self.setWindowTitle("Project: " + self.current_project_file_name)
                else:
                    self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1])
                self.status.showMessage("Project File: " + self.current_project_file_name
                                        + "   Destination: " + str(proj_copy['data']['destination_path']))

    @Slot()
    def save_project(self):
        if self.current_project_file_name is None:
            print(" (!) Current project does not have a name. Forcing 'save as' dialog...")
            self.save_project_as()
        else:
            print("MainWindow is saving the current project to its project file...")
            try:
                self.save_project_to_current_file()
            except:
                print("\nError: Something may have gone wrong with saving the project.\n")
            else:
                print("Project saved successfully.")

    @Slot()
    def save_project_as(self):
        print("MainWindow is showing the save project as dialog...")

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, filter = QFileDialog.getSaveFileName(parent=None,  # None was self
                                                        caption="Save Project",
                                                        filter="Projects (*.json);;All Files (*)",
                                                        selectedFilter="",
                                                        options=options)
        print_debug(60, "save_project_dialog ( " + str(file_name) + ")")

        if file_name != None:
            if len(file_name) > 0:
                self.current_project_file_name = file_name

                # Attempt to hide the file dialog before opening ...
                for p in self.panel_list:
                    p.update_zpa_self()
                # self.update_win_self()
                try:
                    self.save_project_to_current_file()
                except:
                    print("\nError: Something may have gone wrong with saving the project.\n")
                else:
                    print("Project saved successfully.")

                if self.draw_full_paths:
                    self.setWindowTitle("Project: " + self.current_project_file_name)
                else:
                    self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1])

                self.set_def_proj_dest()

    @Slot()
    def save_cropped_as(self):
        print("MainWindow is saving cropped as...")

        crop_parallel = True

        if crop_mode_role == None:
            show_warning("Warning", "Cannot save cropped images without a cropping region")

        elif project_data['data']['destination_path'] == None:
            show_warning("Warning", "Cannot save cropped images without a destination path")

        elif len(project_data['data']['destination_path']) <= 0:
            show_warning("Warning", "Cannot save cropped images without a valid destination path")
        else:
            options = QFileDialog.Options()
            options |= QFileDialog.Directory
            options |= QFileDialog.DontUseNativeDialog

            cropped_path = QFileDialog.getExistingDirectory(parent=None, caption="Select Directory for Cropped Images",
                                                            dir=project_data['data']['destination_path'],
                                                            options=options)
            print_debug(1, "Cropped Destination is: " + str(cropped_path))

            if cropped_path != None:
                if len(cropped_path) > 0:
                    print("Crop and save images from role " + str(crop_mode_role) + " to " + str(cropped_path))
                    scale_key = project_data['data']['current_scale']
                    cropping_queue = None
                    if crop_parallel:
                        print("Before: cropping_queue = task_queue.TaskQueue ( sys.executable )")
                        # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
                        # cropping_queue = task_queue.TaskQueue ( sys.executable )
                        cropping_queue = task_queue.TaskQueue()
                        cpus = psutil.cpu_count(logical=False)
                        if cpus > 48:
                            cpus = 48
                        cropping_queue.start(cpus)
                        cropping_queue.notify = False
                        cropping_queue.passthrough_stdout = False
                        cropping_queue.passthrough_stderr = False

                    for layer in project_data['data']['scales'][scale_key]['alignment_stack']:
                        infile_name = layer['images'][crop_mode_role]['filename']
                        name_part = os.path.split(infile_name)[1]
                        if '.' in name_part:
                            npp = name_part.rsplit('.')
                            name_part = npp[0] + "_crop." + npp[1]
                        else:
                            name_part = name_part + "_crop"
                        outfile_name = os.path.join(cropped_path, name_part)
                        print("Cropping image " + infile_name)
                        print("Saving cropped " + outfile_name)

                        # Use the "extractStraightWindow" function which takes a center and a rectangle
                        crop_cx = int((crop_mode_corners[0][0] + crop_mode_corners[1][0]) / 2)
                        crop_cy = int((crop_mode_corners[0][1] + crop_mode_corners[1][1]) / 2)
                        crop_w = abs(int(crop_mode_corners[1][0] - crop_mode_corners[0][0]))
                        crop_h = abs(int(crop_mode_corners[1][1] - crop_mode_corners[0][1]))
                        print("x,y = " + str((crop_cx, crop_cy)) + ", w,h = " + str((crop_w, crop_h)))

                        if crop_parallel:
                            my_path = os.path.split(os.path.realpath(__file__))[0]
                            crop_job = os.path.join(my_path, 'single_crop_job.py')
                            print(
                                "cropping_queue.add_task ( [sys.executable, crop_job, str(crop_cx), str(crop_cy), str(crop_w), str(crop_h), infile_name, outfile_name] )")
                            # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
                            cropping_queue.add_task(
                                [sys.executable, crop_job, str(crop_cx), str(crop_cy), str(crop_w), str(crop_h),
                                 infile_name, outfile_name])

                        else:
                            img = align_swiftir.swiftir.extractStraightWindow(
                                align_swiftir.swiftir.loadImage(infile_name), xy=(crop_cx, crop_cy),
                                siz=(crop_w, crop_h))
                            align_swiftir.swiftir.saveImage(img, outfile_name)

                    if crop_parallel:
                        cropping_queue.collect_results()  # It might be good to have an explicit "join" function, but this seems to do so internally.

    @Slot()
    def actual_size(self):
        print("MainWindow.actual_size was called by " + inspect.stack()[1].function + "...")
        print_debug(90, "Setting images to actual size")
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update_zpa_self()

    @Slot()
    def toggle_border(self, checked):
        print_debug(90, "toggle_border called with checked = " + str(checked))
        self.draw_border = checked
        self.image_panel.draw_border = self.draw_border
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_border = self.draw_border
            p.update_zpa_self()

    @Slot()
    def toggle_arrow_direction(self, checked):
        print_debug(90, "toggle_arrow_direction called with checked = " + str(checked))
        self.image_panel.arrow_direction = -self.image_panel.arrow_direction

    @Slot()
    def toggle_threaded_loading(self, checked):
        print_debug(90, "toggle_threaded_loading called with checked = " + str(checked))
        image_library.threaded_loading_enabled = checked

    @Slot()
    def toggle_annotations(self, checked):
        print_debug(90, "toggle_annotations called with checked = " + str(checked))
        self.draw_annotations = checked
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_annotations = self.draw_annotations
            p.update_zpa_self()

    @Slot()
    def toggle_full_paths(self, checked):
        print_debug(90, "toggle_full_paths called with checked = " + str(checked))
        self.draw_full_paths = checked
        self.image_panel.draw_full_paths = self.draw_full_paths
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_full_paths = self.draw_full_paths
            p.update_zpa_self()

        if self.draw_full_paths:
            self.setWindowTitle("Project: " + self.current_project_file_name)
        else:
            self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1])

    @Slot()
    def opt_n(self, option_name, option_action):
        if 'num' in dir(option_action):
            print_debug(50, "Dynamic Option[" + str(option_action.num) + "]: \"" + option_name + "\"")
        else:
            print_debug(50, "Dynamic Option: \"" + option_name + "\"")
        print_debug(50, "  Action: " + str(option_action))

    def add_image_to_role(self, image_file_name, role_name):
        print("MainWindow is adding image to role...")

        #### NOTE: TODO: This function is now much closer to empty_into_role and should be merged
        local_cur_scale = get_cur_scale()

        print("Trying to place file " + str(image_file_name) + " in role " + str(role_name))
        if image_file_name != None:
            if len(image_file_name) > 0:
                used_for_this_role = [role_name in l['images'].keys() for l in
                                      project_data['data']['scales'][local_cur_scale]['alignment_stack']]
                # print("Layers using this role: " + str(used_for_this_role))
                layer_index_for_new_role = -1
                if False in used_for_this_role:
                    # This means that there is an unused slot for this role. Find the first:
                    layer_index_for_new_role = used_for_this_role.index(False)
                    print("Inserting file " + str(image_file_name) + " in role " + str(
                        role_name) + " into existing layer " + str(layer_index_for_new_role))
                else:
                    # This means that there are no unused slots for this role. Add a new layer
                    print("Making a new layer for file " + str(image_file_name) + " in role " + str(
                        role_name) + " at layer " + str(layer_index_for_new_role))
                    project_data['data']['scales'][local_cur_scale]['alignment_stack'].append(
                        copy.deepcopy(new_layer_template))
                    layer_index_for_new_role = len(
                        project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
                image_dict = \
                project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role]['images']
                image_dict[role_name] = copy.deepcopy(new_image_template)
                image_dict[role_name]['filename'] = image_file_name

    def add_empty_to_role(self, role_name):
        print("MainWindow is adding empty to role...")

        local_cur_scale = get_cur_scale()
        # local_cur_scale = 'base' # attempt monkey patch #jy #sus

        used_for_this_role = [role_name in l['images'].keys() for l in
                              project_data['data']['scales'][local_cur_scale]['alignment_stack']]
        print("Layers using this role: " + str(used_for_this_role))
        layer_index_for_new_role = -1
        if False in used_for_this_role:
            # This means that there is an unused slot for this role. Find the first:
            layer_index_for_new_role = used_for_this_role.index(False)
            print("Inserting empty in role " + str(role_name) + " into existing layer " + str(layer_index_for_new_role))
        else:
            # This means that there are no unused slots for this role. Add a new layer
            print(
                "Making a new layer for empty in role " + str(role_name) + " at layer " + str(layer_index_for_new_role))
            project_data['data']['scales'][local_cur_scale]['alignment_stack'].append(copy.deepcopy(new_layer_template))
            layer_index_for_new_role = len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        image_dict = project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role][
            'images']
        image_dict[role_name] = copy.deepcopy(new_image_template)
        image_dict[role_name]['filename'] = None

    def import_images(self, role_to_import, file_name_list, clear_role=False):
        print("MainWindow is importing images...")
        global preloading_range
        local_cur_scale = get_cur_scale()

        print_debug(60, "import_images ( " + str(role_to_import) + ", " + str(file_name_list) + ")")

        print_debug(30, "Importing images for role: " + str(role_to_import))
        for f in file_name_list:
            print_debug(30, "   " + str(f))
        print_debug(10, "Importing images for role: " + str(role_to_import))

        if clear_role:
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            for layer in project_data['data']['scales'][local_cur_scale]['alignment_stack']:
                if role_to_import in layer['images'].keys():
                    layer['images'].pop(role_to_import)

        if file_name_list != None:
            if len(file_name_list) > 0:
                print_debug(40, "Selected Files: " + str(file_name_list))
                print_debug(40, "")
                for f in file_name_list:
                    # Find next layer with an empty role matching the requested role_to_import
                    print_debug(50, "Role " + str(role_to_import) + ", Importing file: " + str(f))
                    if f is None:
                        self.add_empty_to_role(role_to_import)
                    else:
                        self.add_image_to_role(f, role_to_import)
                # Draw the panel's ("windows")
                for p in self.panel_list:
                    p.force_center = True
                    p.update_zpa_self()

        # center images after importing
        self.center_all_images()

        # might need:
        # self.update_panels()

        # instead, try approaching this from the import dialog code block

    def update_panels(self):
        print("  Updating panels (MainWindow.update_panels was called by " + inspect.stack()[1].function + ")...")
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def import_images_dialog(self, import_role_name):

        print_debug(5, "Importing images dialog for role: " + str(import_role_name))

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name_list, filtr = QFileDialog.getOpenFileNames(None,  # None was self
                                                             "Select Images to Import",
                                                             # self.openFileNameLabel.text(),
                                                             "Select Images",
                                                             "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)",
                                                             "", options)

        print_debug(60, "import_images_dialog ( " + str(import_role_name) + ", " + str(file_name_list) + ")")

        # Attempt to hide the file dialog before opening ...
        for p in self.panel_list:
            p.update_zpa_self()

        # self.update_win_self()

        self.import_images(import_role_name, file_name_list)

        self.center_all_images()

    @Slot()
    def set_destination(self):
        print("Calling set_destination(self) was called by " + inspect.stack()[1].function + ")...")
        print_debug(1, "Set Destination")

        options = QFileDialog.Options()
        options |= QFileDialog.Directory
        options |= QFileDialog.DontUseNativeDialog

        project_data['data']['destination_path'] = QFileDialog.getExistingDirectory(parent=None,
                                                                                    caption="Select Destination Directory",
                                                                                    dir=project_data['data'][
                                                                                        'destination_path'],
                                                                                    options=options)
        print_debug(1, "Destination is: " + str(project_data['data']['destination_path']))

        self.status.showMessage("Project File: " + self.current_project_file_name
                                + "   Destination: " + str(project_data['data']['destination_path']))

    @Slot()
    def set_def_proj_dest(self):
        print("MainWindow is setting default project destination (MainWindow.set_def_proj_dest was called by " +
              inspect.stack()[1].function + ")...")
        print("  Default project destination is set to: ", str(self.current_project_file_name))
        if self.current_project_file_name == None:
            show_warning("No Project File",
                         "Unable to set a project destination without a project file.\nPlease save the project file first.")
        elif len(self.current_project_file_name) == 0:
            show_warning("No Legal Project File",
                         "Unable to set a project destination without a project file.\nPlease save the project file first.")
        else:
            p, e = os.path.splitext(self.current_project_file_name)
            if not (e.lower() == '.json'):
                show_warning("Not JSON File Extension",
                             'Project file must be of type "JSON".\nPlease save the project file as ".JSON" first.')
            else:
                project_data['data']['destination_path'] = p
                # os.makedirs(project_data['data']['destination_path'])
                makedirs_exist_ok(project_data['data']['destination_path'], exist_ok=True)
                print("  Destination path is : " + str(project_data['data']['destination_path']))
                self.status.showMessage("Project File: " + self.current_project_file_name
                                        + "   Destination: " + str(project_data['data']['destination_path']))

    def load_images_in_role(self, role, file_names):
        print("MainWindow is loading images in role (called by " + inspect.stack()[1].function + ")...")
        print("load_images_in_role ( " + str(role) + ", " + str(file_names) + ")")
        self.import_images(role, file_names, clear_role=True)

    def define_roles(self, roles_list):
        print("MainWindow is defining roles...")

        # Set the image panels according to the roles
        self.image_panel.set_roles(roles_list)

        # Set the Roles menu from this roles_list
        mb = self.menuBar()
        if not (mb is None):
            for m in mb.children():
                if type(m) == QMenu:
                    text_label = ''.join(m.title().split('&'))
                    if 'Images' in text_label:
                        print_debug(30, "Found Images Menu")
                        for mm in m.children():
                            if type(mm) == QMenu:
                                text_label = ''.join(mm.title().split('&'))
                                if 'Import into' in text_label:
                                    print_debug(30, "Found Import Into Menu")
                                    # Remove all the old actions:
                                    while len(mm.actions()) > 0:
                                        mm.removeAction(mm.actions()[-1])
                                    # Add the new actions
                                    for role in roles_list:
                                        item = QAction(role, self)
                                        item.triggered.connect(self.import_into_role)
                                        mm.addAction(item)
                                if 'Empty into' in text_label:
                                    print_debug(30, "Found Empty Into Menu")
                                    # Remove all the old actions:
                                    while len(mm.actions()) > 0:
                                        mm.removeAction(mm.actions()[-1])
                                    # Add the new actions
                                    for role in roles_list:
                                        item = QAction(role, self)
                                        item.triggered.connect(self.empty_into_role)
                                        mm.addAction(item)
                                if 'Clear Role' in text_label:
                                    print_debug(30, "Found Clear Role Menu")
                                    # Remove all the old actions:
                                    while len(mm.actions()) > 0:
                                        mm.removeAction(mm.actions()[-1])
                                    # Add the new actions
                                    for role in roles_list:
                                        item = QAction(role, self)
                                        item.triggered.connect(self.remove_all_from_role)
                                        mm.addAction(item)

    def register_view_change_callback(self, callback_function):
        self.view_change_callback = callback_function

    def register_mouse_down_callback(self, callback_function):
        self.mouse_down_callback = callback_function

    def register_mouse_move_callback(self, callback_function):
        self.mouse_move_callback = callback_function

    @Slot()
    def define_roles_callback(self):
        print("@Slot Defining roles callback (MainWindow.define_roles_callback was called by " + inspect.stack()[
            1].function + ")...")

        default_roles = ['Stack']
        if len(project_data['data']['panel_roles']) > 0:
            default_roles = project_data['data']['panel_roles']
        input_val, ok = QInputDialog().getText(None, "Define Roles", "Current: " + str(' '.join(default_roles)),
                                               echo=QLineEdit.Normal, text=' '.join(default_roles))
        if ok:
            input_val = input_val.strip()
            roles_list = project_data['data']['panel_roles']
            if len(input_val) > 0:
                roles_list = [str(v) for v in input_val.split(' ') if len(v) > 0]
            # if not (roles_list == project_data['data']['panel_roles']):
            self.define_roles(roles_list)
        else:
            print_debug(30, "Cancel: Roles not changed")

    @Slot()
    def import_into_role(self, checked):
        print("MainWindow is importing into role (called by " + inspect.stack()[1].function + ")...")

        import_role_name = str(self.sender().text())
        self.import_images_dialog(import_role_name)

    # center try center code from here
    def import_base_images(self):
        print("Importing base images...")

        self.import_images_dialog('base')
        if update_linking_callback != None:
            update_linking_callback()
            self.update_win_self()

        self.center_all_images() # patch center all images after importing

    @Slot()
    def empty_into_role(self, checked):
        print("MainWindow is emptying into role (called by " + inspect.stack()[1].function + ")...")
        print("#### NOTE: TODO: This function is now much closer to add_image_to_role and should be merged")
        local_cur_scale = get_cur_scale()

        role_to_import = str(self.sender().text())

        print_debug(30, "Adding empty for role: " + str(role_to_import))

        used_for_this_role = [role_to_import in l['images'].keys() for l in
                              project_data['data']['scales'][local_cur_scale]['alignment_stack']]
        print_debug(60, "Layers using this role: " + str(used_for_this_role))
        layer_index_for_new_role = -1
        if False in used_for_this_role:
            # This means that there is an unused slot for this role. Find the first:
            layer_index_for_new_role = used_for_this_role.index(False)
            print_debug(60, "Inserting <empty> in role " + str(role_to_import) + " into existing layer " + str(
                layer_index_for_new_role))
        else:
            # This means that there are no unused slots for this role. Add a new layer
            print_debug(60, "Making a new layer for <empty> in role " + str(role_to_import) + " at layer " + str(
                layer_index_for_new_role))
            project_data['data']['scales'][local_cur_scale]['alignment_stack'].append(copy.deepcopy(new_layer_template))
            layer_index_for_new_role = len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        image_dict = project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role][
            'images']
        image_dict[role_to_import] = copy.deepcopy(new_image_template)

        # Draw the panels ("windows")
        for p in self.panel_list:
            p.force_center = True
            p.update_zpa_self()

        self.update_win_self()

    @Slot()
    def remove_all_from_role(self, checked):
        print("  MainWindow.remove_all_from_role was called...")
        role_to_remove = str(self.sender().text())
        print_debug(10, "Remove role: " + str(role_to_remove))
        self.remove_from_role(role_to_remove)

    def remove_from_role(self, role, starting_layer=0, prompt=True):
        print("  MainWindow.remove_from_role was called...")
        print_debug(5, "Removing " + role + " from scale " + str(get_cur_scale()) + " forward from layer " + str(
            starting_layer) + "  (remove_from_role)")
        actually_remove = True
        if prompt:
            actually_remove = request_confirmation("Note", "Do you want to remove all " + role + " images?")
        if actually_remove:
            print_debug(5, "Removing " + role + " images ...")

            delete_list = []

            layer_index = 0
            for layer in project_data['data']['scales'][get_cur_scale()]['alignment_stack']:
                if layer_index >= starting_layer:
                    print_debug(5, "Removing " + role + " from Layer " + str(layer_index))
                    if role in layer['images'].keys():
                        delete_list.append(layer['images'][role]['filename'])
                        print_debug(5, "  Removing " + str(layer['images'][role]['filename']))
                        layer['images'].pop(role)
                        # Remove the method results since they are no longer applicable
                        if role == 'aligned':
                            if 'align_to_ref_method' in layer.keys():
                                if 'method_results' in layer['align_to_ref_method']:
                                    # Set the "method_results" to an empty dictionary to signify no results:
                                    layer['align_to_ref_method']['method_results'] = {}
                layer_index += 1

            # image_library.remove_all_images()

            for fname in delete_list:
                if fname != None:
                    if os.path.exists(fname):
                        os.remove(fname)
                        image_library.remove_image_reference(fname)

            main_window.update_panels()
            main_window.refresh_all()

    def set_scales_from_string(self, scale_string):
        print("  MainWindow is setting scales from string (MainWindow.set_scales_from_string)...")
        print("  scale_string = ", scale_string)
        cur_scales = [str(v) for v in sorted([get_scale_val(s) for s in project_data['data']['scales'].keys()])]
        scale_string = scale_string.strip()
        if len(scale_string) > 0:
            input_scales = []
            try:
                input_scales = [str(v) for v in sorted([get_scale_val(s) for s in scale_string.strip().split(' ')])]
            except:
                print("Bad input: (" + str(scale_string) + "), Scales not changed")
                input_scales = []

            if not (input_scales == cur_scales):
                # The scales have changed!!
                # self.define_scales_menu (input_scales)
                cur_scale_keys = [get_scale_key(v) for v in cur_scales]
                input_scale_keys = [get_scale_key(v) for v in input_scales]

                # Remove any scales not in the new list (except always leave 1)
                scales_to_remove = []
                for scale_key in project_data['data']['scales'].keys():
                    if not (scale_key in input_scale_keys):
                        if get_scale_val(scale_key) != 1:
                            scales_to_remove.append(scale_key)
                for scale_key in scales_to_remove:
                    project_data['data']['scales'].pop(scale_key)

                # Add any scales not in the new list
                scales_to_add = []
                for scale_key in input_scale_keys:
                    if not (scale_key in project_data['data']['scales'].keys()):
                        scales_to_add.append(scale_key)
                for scale_key in scales_to_add:
                    new_stack = []
                    scale_1_stack = project_data['data']['scales'][get_scale_key(1)]['alignment_stack']
                    for l in scale_1_stack:
                        new_layer = copy.deepcopy(l)
                        new_stack.append(new_layer)
                    project_data['data']['scales'][scale_key] = {'alignment_stack': new_stack, 'method_data': {
                        'alignment_option': 'init_affine'}}
        else:
            print("No input: Scales not changed")

    @Slot()
    def remove_this_layer(self):
        print("  MainWindow is removing a single layer...")
        local_cur_scale = get_cur_scale()
        local_current_layer = project_data['data']['current_layer']
        project_data['data']['scales'][local_cur_scale]['alignment_stack'].pop(local_current_layer)
        if local_current_layer >= len(project_data['data']['scales'][local_cur_scale]['alignment_stack']):
            local_current_layer = len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        project_data['data']['current_layer'] = local_current_layer

        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def remove_all_layers(self):
        print("  MainWindow is removing all layers...")
        global project_data
        local_cur_scale = get_cur_scale()
        project_data['data']['current_layer'] = 0
        while len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) > 0:
            project_data['data']['scales'][local_cur_scale]['alignment_stack'].pop(0)
        self.update_win_self()

    @Slot()
    def remove_all_panels(self):
        print("  MainWindow is removing all panels...")
        print_debug(30, "Removing all panels")
        if 'image_panel' in dir(self):
            print_debug(30, "image_panel exists")
            self.image_panel.remove_all_panels()
        else:
            print_debug(30, "image_panel does not exit!!")
        self.define_roles([])
        self.update_win_self()

    @Slot()
    def set_max_image_size(self):
        global max_image_file_size
        input_val, ok = QInputDialog().getInt(None, "Enter Max Image File Size", "Max Image Size:", max_image_file_size)
        if ok:
            max_image_file_size = input_val

    @Slot()
    def set_crop_square(self):
        global crop_window_mode
        crop_window_mode = 'mouse_square'
        print_debug(10, "Crop window will be square")

    @Slot()
    def set_crop_rect(self):
        global crop_window_mode
        crop_window_mode = 'mouse_rectangle'
        print_debug(10, "Crop window will be rectangular")

    @Slot()
    def set_crop_fixed(self):
        global crop_window_mode
        global crop_window_width
        global crop_window_height

        crop_window_mode = 'mouse_center_fixed'
        current = str(crop_window_width) + 'x' + str(crop_window_height)
        input_str, ok = QInputDialog().getText(None, "Set Crop Window Size", "Current: " + current,
                                               echo=QLineEdit.Normal, text=current)
        if ok:
            wh = input_str.strip()
            if len(wh) > 0:
                w_h = []
                if 'x' in wh:
                    w_h = [f.strip() for f in wh.split('x')]
                elif ' ' in wh:
                    w_h = [f.strip() for f in wh.split(' ')]
                if len(w_h) > 0:
                    if len(w_h) >= 2:
                        # Set independently
                        crop_window_width = w_h[0]
                        crop_window_height = w_h[1]
                    else:
                        # Set together
                        crop_window_width = w_h[0]
                        crop_window_height = w_h[0]
                    print_debug(10, "Crop Window will be " + str(crop_window_width) + "x" + str(crop_window_height))

    @Slot()
    def center_all_images(self, all_images_in_stack=True):
        print("  MainWindow is centering all images (called by " + inspect.stack()[1].function + ")...")
        self.image_panel.center_all_images(all_images_in_stack=all_images_in_stack)

    @Slot()
    def refresh_all_images(self):
        # print("  MainWindow is refreshing all images (called by " + inspect.stack()[1].function + ")...")
        self.image_panel.refresh_all_images()

    @Slot()
    def all_images_actual_size(self):
        print("  MainWindow is actual-sizing all images (called by " + inspect.stack()[1].function + ")...")
        self.image_panel.all_images_actual_size()

    @Slot()
    def set_preloading_range(self):
        print("  MainWindow is setting preloading range (called by " + inspect.stack()[1].function + ")...")
        global preloading_range

        input_val, ok = QInputDialog().getInt(None, "Enter Number of Images to Preload", "Preloading Count:",
                                              preloading_range)
        if ok:
            preloading_range = input_val

            if project_data != None:

                local_scales = project_data['data']['scales']
                local_cur_scale = get_cur_scale()
                if local_cur_scale in local_scales:
                    local_scale = local_scales[local_cur_scale]
                    if 'alignment_stack' in local_scale:
                        local_stack = local_scale['alignment_stack']
                        if len(local_stack) > 0:
                            local_current_layer = project_data['data']['current_layer']

                            # Define the images needed
                            needed_images = set()
                            for i in range(len(local_stack)):
                                if abs(i - local_current_layer) < preloading_range:
                                    for role, local_image in local_stack[i]['images'].items():
                                        if local_image['filename'] != None:
                                            if len(local_image['filename']) > 0:
                                                needed_images.add(local_image['filename'])
                            # Ask the library to keep only those images
                            image_library.make_available(needed_images)

    @Slot()
    def exit_app(self):
        print("@Slot Exiting app (MainWindow.exit_app was called by " + inspect.stack()[1].function + ")...")
        sys.exit()

    @Slot()
    def py_console(self):
        print("@Slot Entering python console, use Control-D or Control-Z when done | MainWindow.py_console...")
        print_debug(1, "\n\n\n")
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def run_app(main_win=None):
    print("Running app...")
    print("  Defining globals: app, main_window")
    global app
    global main_window

    if main_win == None:
        print('  main_win does not exist... setting main_window = MainWindow()')
        main_window = MainWindow()
    else:
        print('  main_win exists... setting main_window = main_win')
        main_window = main_win

    print('  Showing main window (main_window.show())...')
    #main_window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image
    main_window.show()
    sys.exit(app.exec_())


control_model = None

# This provides default command line parameters if none are given (as with "Idle")
# if len(sys.argv) <= 1:
#    sys.argv = [ __file__, "-f", "vj_097_1k1k_1.jpg" ]

import multiprocessing, logging

logger = multiprocessing.log_to_stderr()
# logger.setLevel(multiprocessing.SUBDEBUG) # very verbose
logger.setLevel(logging.INFO)

#main
if __name__ == "__main__":
    print('\n\n Entering __main__ of py... \n\n')

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False,
                         help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-l", "--preload", type=int, required=False, default=7,
                         help="Preload +/-, total to preload = 2n-1")
    args = options.parse_args()

    DEBUG_LEVEL = int(args.debug)

    if args.preload != None:
        preloading_range = int(args.preload)
        if preloading_range < 1:
            preloading_range = 1

    control_model = [
        # Panes
        [  # Begin first pane
            ["Program: " + __file__],
            ["No Control Panel Data Defined."]
        ]  # End first pane
    ]

    main_window = MainWindow(control_model=control_model)
    main_window.resize(2200, 1200)

    main_window.define_roles(['Stack'])
    main_window.show()
    sys.exit(app.exec_())

"""
To do:
[x] upgrade 'daisy' from v0.2 to v1.0
[x] make menu bar attached on macOS
[x] after selecting 'skip', it should not be necessary to re-focus on images wiget
[] spawn new thread for making Zarr, to not lock up the GUI
[] fix/improve affine combo box
[x] automatically focus back on ZoomPanWidget after adjusting control panel
[] when skips are reset, remove red 'x' annotation immediately
[] display current affine
[] radio buttons for scales (?)
[] BUG: when Keep/Toggle switch is used pre-scaling, red X does not appear immediately
[] improved robustness in error recovery of task_queue
[] generate error report logs, save inside project (talk to James about saving log files to remote database/server)
[] ask to save before exiting
[] dim out "#scales" and "clevel" when compression combobox option "none" is selected
[] cancel Zarr export
[] when quitting without a recent save, have option to save first
[] call 'Apply Affine' something more descriptive, or make its function more clear ('Force Affine'?)
[] add a place to take notes (see: https://pythonbasics.org/pyqt-menubar/)

To do (Zarr/precomputed):
[] look into making pre-computed format multithreaded
[] look into Zarr directory store
[] insert/remove images from Zarr (callback functions)

possible features:
[] dim out skipped images instead of red 'X'
[] magnifying glass
[] use QSplitter for showing additional status info/project details
[] mouseover-specific tooltips or status information
[] view or hide skipped images 

already done:
[x] port Python+Qt to PySide6
[x] enable multithreaded export to Zarr
[x] spawn new thread for emdedded web browser
[x] embed neuroglancer viewer
[x] embed documentation
[x] remake control panel using more conventional and scalable Python/Qt strategies
[x] implement QStackedWidget to allow the application to have paging, replete with back buttons, etc.
[x] apply stylesheet
[x] replace 'skip' checkbox with toggle button
[x] automatically center images



TESTING THE FOLLOWING IN MENU
self.update_win_self()
self.update_panels()
self.refresh_all_images
    * only refresh_all_images updated the display with current scale


inspect module doc:
https://docs.python.org/3/library/inspect.html

print calling function with inspect module:
print(inspect.stack()[1].function)
 "Caller: " + inspect.stack()[1].function
 Caller: ' + inspect.stack()[1].function + ' | 
 
 
 ZoomPanWidget.get_settings
 ZoomPanWidget.update_zpa_self
 


"""

"""
After aligning, images should be centered

"""

"""
Traceback (most recent call last):
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/py", line 4047, in open_project
    self.image_panel.update_multi_self()
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/py", line 1599, in update_multi_self
    main_window.update_ref_label()
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/py", line 3823, in update_ref_label
    ref_file_name = layer['images']['ref']['filename']
KeyError: 'ref'

Occurred pre-scaling, after saving/re-opening. Probably is preventing the image to center. Pressing 'center' successfully centered.


"""

"""
Encountered an endless cycle of scaling

Worker 2:  Task 189 Completed with RC 1
Worker 3:  Task 183 Completed with RC 1
Worker 2:  Stopping
Worker 3:  Stopping

Need to Requeue 194 Failed Tasks...
    Task_IDs: [5, 1, 2, 3, 0, 6, 4, 7, 10, 13, 15, 11, 8, 9, 14, 12, 16, 17, 23, 18, 21, 22, 20, 19, 24, 28, 25, 31, 29, 27, 30, 26, 34, 32, 33, 38, 36, 35, 39, 37, 41, 40, 47, 46, 45, 44, 42, 43, 51, 48, 49, 52, 53, 50, 54, 55, 58, 56, 57, 59, 61, 63, 62, 60, 65, 64, 71, 70, 67, 66, 69, 68, 77, 72, 79, 73, 76, 78, 75, 74, 86, 80, 82, 87, 81, 83, 84, 85, 90, 88, 89, 92, 94, 95, 91, 93, 97, 98, 96, 103, 102, 99, 100, 101, 106, 105, 104, 109, 110, 107, 108, 111, 112, 115, 114, 113, 116, 117, 119, 118, 121, 125, 122, 120, 126, 124, 127, 123, 128, 133, 131, 130, 134, 129, 132, 135, 136, 137, 139, 178, 155, 150, 154, 141, 171, 165, 169, 161, 156, 145, 174, 173, 177, 166, 160, 159, 163, 162, 193, 144, 140, 153, 164, 172, 192, 189, 142, 191, 186, 175, 157, 152, 147, 190, 180, 158, 149, 151, 181, 183, 143, 146, 138, 182, 179, 148, 170, 176, 168, 184, 185, 187, 167, 188]

Restarting Task Queue...
    Restarting Worker 0
    Restarting Worker 1
    Restarting Worker 2
    Restarting Worker 3
    Restarting Worker 4
    Restarting Worker 5
    Restarting Worker 6
    Restarting Worker 7
    Done Restarting Task Queue
Requeuing Failed Task_ID: 5   Retries: 3
  Task: {'cmd': '/Users/joelyancey/anaconda3/envs/ges4_pyside6/bin/python3', 'args': ['/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py', '/Users/joelyancey/glanceEM_SWiFT/test_projects/R34CA1-BS12_2022-03-24/project_runner_job_file.json', 'init_affine', '4', 'c', '5', '1', '0'], 'stdout': '', 'stderr': 'Traceback (most recent call last):\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py", line 50, in <module>\n    updated_model, need_to_write_json = pyswift_tui.run_json_project (\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/pyswift_tui.py", line 686, in run_json_project\n    if project[\'data\'][\'scales\'][\'scale_%d\'%use_scale][\'alignment_stack\'][0][\'images\'][\'ref\'][\'filename\'] != None:\nKeyError: \'ref\'\n', 'rc': 1, 'status': 'task_error', 'retries': 2, 'dt': 1.8007159233093262}


...

  Task: {'cmd': '/Users/joelyancey/anaconda3/envs/ges4_pyside6/bin/python3', 'args': ['/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py', '/Users/joelyancey/glanceEM_SWiFT/test_projects/R34CA1-BS12_2022-03-24/project_runner_job_file.json', 'init_affine', '4', 'c', '188', '1', '0'], 'stdout': '', 'stderr': 'Traceback (most recent call last):\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py", line 50, in <module>\n    updated_model, need_to_write_json = pyswift_tui.run_json_project (\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/pyswift_tui.py", line 686, in run_json_project\n    if project[\'data\'][\'scales\'][\'scale_%d\'%use_scale][\'alignment_stack\'][0][\'images\'][\'ref\'][\'filename\'] != None:\nKeyError: \'ref\'\n', 'rc': 1, 'status': 'task_error', 'retries': 2, 'dt': 2.097774028778076}
Exiting project_runner > do_alignment
Worker 0:  Running Task 5
Exiting project_runner > do_alignment

...


"""

"""
zooming issue...
qt.pointer.dispatch: delivering touch release to same window QWindow(0x0) not QWidgetWindow(0x7f8454c9aef0, name="MainWindowClassWindow")
qt.pointer.dispatch: skipping QEventPoint(id=1 ts=0 pos=0,0 scn=858.668,722.959 gbl=858.668,722.959 Released ellipse=(1x1 ∡ 0) vel=0,0 press=-858.668,-722.959 last=-858.668,-722.959 Δ 858.668,722.959) : no target window
qt.pointer.dispatch: delivering touch release to same window QWindow(0x0) not QWidgetWindow(0x7f8454c9aef0, name="MainWindowClassWindow")
qt.pointer.dispatch: skipping QEventPoint(id=1 ts=0 pos=0,0 scn=1096.8,909.006 gbl=1096.8,909.006 Released ellipse=(1x1 ∡ 0) vel=0,0 press=-1096.8,-909.006 last=-1096.8,-909.006 Δ 1096.8,909.006) : no target window
js: performance warning: READ-usage buffer was written, then fenced, but written again before being read back. This discarded the shadow copy that was created to accelerate readback.
qt.pointer.dispatch: delivering touch release to same window QWindow(0x0) not QWidgetWindow(0x7f8454c9aef0, name="MainWindowClassWindow")
qt.pointer.dispatch: skipping QEventPoint(id=4 ts=0 pos=0,0 scn=1089.21,802.695 gbl=1089.21,802.695 Released ellipse=(1x1 ∡ 0) vel=0,0 press=-1089.21,-802.695 last=-1089.21,-802.695 Δ 1089.21,802.695) : no target window
qt.pointer.dispatch: delivering touch release to same window QWindow(0x0) not QWidgetWindow(0x7f8454c9aef0, name="MainWindowClassWindow")
qt.pointer.dispatch: skipping QEventPoint(id=1 ts=0 pos=0,0 scn=1418.85,903.845 gbl=1418.85,903.845 Released ellipse=(1x1 ∡ 0) vel=0,0 press=-1418.85,-903.845 last=-1418.85,-903.845 Δ 1418.85,903.845) : no target window

This bug could have to do with unused lines of code related to focus, i.e. self.setFocusPolicy(Qt.StrongFocus) #jy #focus

This issue appears to be linked to TensorFlow
https://github.com/tensorflow/tfjs/issues/1145

"""

"""
When aligning full res images with 'Apply Affine'

Finished Collecting Results for 270 Tasks
    Failed Tasks: 19
    Retries: 10

...

270 Alignment Tasks Completed in 138.09 seconds
    Num Successful:   251
    Num Still Queued: 0
    Num Failed:       19



...

Task Error:
   CMD:    /Users/joelyancey/anaconda3/envs/ges4_pyside6/bin/python3
   ARGS:   ['/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py', '/Users/joelyancey/glanceEM_SWiFT/test_projects/SYGQK_4096x4096_2022-03-01/project_runner_job_file.json', 'apply_affine', '1', 'c', '71', '1', '0']
   STDERR: Traceback (most recent call last):
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py", line 50, in <module>
    updated_model, need_to_write_json = pyswift_tui.run_json_project (
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/pyswift_tui.py", line 936, in run_json_project
    c_afm = align_item.align(c_afm,save=False)
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/align_swiftir.py", line 149, in align
    result = self.auto_swim_align(c_afm,save=save)
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/align_swiftir.py", line 188, in auto_swim_align
    wwx = int(wsf*wwx_f)                # Window Width in x Scaled
TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'

...also getting a bunch of this block...

 Task: {'cmd': '/Users/joelyancey/anaconda3/envs/ges4_pyside6/bin/python3', 'args': ['/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py', '/Users/joelyancey/glanceEM_SWiFT/test_projects/SYGQK_4096x4096_2022-03-01/project_runner_job_file.json', 'apply_affine', '1', 'c', '86', '1', '0'], 'stdout': '', 'stderr': 'Traceback (most recent call last):\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/single_alignment_job.py", line 50, in <module>\n    updated_model, need_to_write_json = pyswift_tui.run_json_project (\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/pyswift_tui.py", line 936, in run_json_project\n    c_afm = align_item.align(c_afm,save=False)\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/align_swiftir.py", line 149, in align\n    result = self.auto_swim_align(c_afm,save=save)\n  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/align_swiftir.py", line 188, in auto_swim_align\n    wwx = int(wsf*wwx_f)                # Window Width in x Scaled\nTypeError: unsupported operand type(s) for *: \'NoneType\' and \'int\'\n', 'rc': 1, 'status': 'task_error', 'retries': 9, 'dt': 1.3530302047729492}

...and finally...
Traceback (most recent call last):
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/alignem_swift.py", line 1186, in align_all_or_some
    align_layers(first_layer, num_layers)
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/alignem_swift.py", line 1072, in align_layers
    running_project.do_alignment(alignment_option=this_scale['method_data']['alignment_option'],
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/project_runner.py", line 339, in do_alignment
    self.generate_aligned_images()
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/project_runner.py", line 373, in generate_aligned_images
    pyswift_tui.save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'], bias_data_path)
  File "/Users/joelyancey/glanceem_swift/swift-ir/source/PySide6/pyswift_tui.py", line 583, in save_bias_analysis
    snr = np.array(atrm['method_results']['snr'])
KeyError: 'snr'


"""

"""
    # POSSIBLE WORKFLOW FOR VIEWING SINGLE BLEND IN NEUROGLANCER VIEWER
    # 1. Create blended image
    # 2. If project.zarr/img_blended_zarr group does not exist, create it
    # 3. Converted blended image to Zarr using tiffs2zarr utility function (from glanceem_utils.py).
    # 4. Blended image array is appended to project.zarr/img_blended_zarr
    # 5. Neuroglancer viewer top panel is updated to display Zarr group img_blended_zarr


"""

"""
weird, this randomly appeared:
js: crbug/1173575, non-JS module files deprecated.

"""
