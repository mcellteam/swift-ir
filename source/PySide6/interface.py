"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.

"""
import sys, os, traceback, copy, math, random, json, psutil, shutil, argparse, inspect, threading, \
    concurrent.futures, platform, collections, time, datetime, multiprocessing, logging, operator, random, \
    multiprocessing, logging, random, textwrap
from http.server import SimpleHTTPRequestHandler, HTTPServer

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QStackedLayout, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox, \
    QSpacerItem, QMenu, QColorDialog, QMessageBox, QComboBox, QRubberBand, QToolButton, QStyle, QDialog, QFrame, \
    QStyleFactory, QGroupBox, QPlainTextEdit, QTabWidget, QScrollArea, QToolButton, QDockWidget, QSplitter
from PySide6.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor, QIntValidator, QDoubleValidator, QIcon, \
    QSurfaceFormat, QAction, QActionGroup, QPaintEvent, QBrush, QFont, QImageReader, QImage
from PySide6.QtCore import Slot, QRect, QRectF, QSize, Qt, QPoint, QPointF, QThreadPool, QUrl, QFile, QTextStream, \
    QCoreApplication, Property, QRunnable, Signal, Slot, QThreadPool, QThread, QObject, QParallelAnimationGroup, \
    QAbstractAnimation, QPropertyAnimation, QParallelAnimationGroup
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings


try:
    from PySide6.QtCore import Signal, Slot
except ImportError:
    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtCore import pyqtSlot as Slot


from pathlib import Path
import daisy
import skimage.measure
import dask.array as da
import neuroglancer as ng
from glob import glob
from PIL import Image
import numpy as np
from tqdm import tqdm

from joel_decs import timeit, profileit, dumpit, traceit, countit
from alignem_data_model import new_project_template, new_layer_template, new_image_template, upgrade_data_model
from glanceem_utils import print_exception, getCurScale, isDestinationSet, isProjectScaled, \
    isScaleAligned, getNumAligned, getNumAligned, getSkipsList, areAlignedImagesGenerated, \
    isAnyScaleAligned, returnAlignedImgs, isAnyAlignmentExported, getNumScales, \
    printCurrentDirectory, link_all_stacks, copy_skips_to_all_scales, print_project_data_stats, getCurSNR, \
    areImagesImported, debug_layer, debug_project, printProjectDetails, getProjectFileLength, isCurScaleExported \
# from glanceem_utils import get_viewer_url
from glanceem_utils import clear_all_skips
from scale_pyramid import add_layer
from align_recipe_1 import align_all_or_some, regenerate_aligned
from get_image_size import get_image_size
import align_swiftir, pyswift_tui
import task_queue_mp as task_queue
import task_wrapper
import pyswift_tui
# from caveclient import CAVEclient

logger = logging.getLogger(__name__)
center_switch = 0

project_data = None #jy turning back on #0404
app = None
use_c_version = True
use_file_io = False
show_skipped_images = True

preloading_range = 3
# max_image_file_size = 1000000000 #original
max_image_file_size = 50000000000
crop_window_mode = 'mouse_rectangle'  # mouse_rectangle or mouse_square or fixed
crop_window_width = 1024
crop_window_height = 1024
# update_linking_callback = None
# update_skips_callback = None
# crop_mode_callback = None
# crop_mode_role = None
# crop_mode_origin = None
# crop_mode_disp_rect = None
# crop_mode_corners = None
# current_scale = 'scale_1'
# alignem_swift.main_win = None #jy 0525

'''global variables'''
project_data = None

def run_app(main_win=None):
    '''Initialize MainWindow object or attach to a MainWindow instance, then show it.'''

    print("run_app | Running app...")
    global app
    global main_window

    if main_win == None:
        print('run_app | WARNING | main_win does not exist. setting main_window = MainWindow() | <conditional>')
        main_window = MainWindow()
    else:
        print('run_app | main_win exists, setting main_window = main_win')
        main_window = main_win

    print('run_app | Showing the application now')
    main_window.show() #windows are hidden by default
    sys.exit(app.exec_())


def open_ds(path, ds_name):
    """ wrapper for daisy.open_ds """
    print("Running daisy.open_ds with path:" + path + ", ds_name:" + ds_name)
    try:
        return daisy.open_ds(path, ds_name)
    except KeyError:
        print("\n  ERROR: dataset " + ds_name + " could not be loaded. Must be Daisy-like array.\n")
        return None



class RequestHandler(SimpleHTTPRequestHandler):
    '''A simple HTTP request handler'''
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)


class Server(HTTPServer):
    '''A simple HTTP server'''
    protocol_version = 'HTTP/1.1'

    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, RequestHandler)

def decode_json(x):
    return json.loads(x, object_pairs_hook=collections.OrderedDict)

def get_json(path):
    with open(path) as f:
        return json.load(f)
        # example: keys = get_json("project.zarr/img_aligned_zarr/s0/.zarray")

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


def clear_crop_settings():
    global crop_mode_role
    global crop_mode_orgin
    global crop_mode_disp_rect
    global crop_mode_corners
    crop_mode_role = None
    crop_mode_orgin = None
    crop_mode_disp_rect = None
    crop_mode_corners = None

def getCurScale():
    global project_data
    return ( project_data['data']['current_scale'] )

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
    # print('create_project_structure_directories:')
    # print('param subdir_path: ', subdir_path)
    try:
        os.mkdir(subdir_path)
    except:
        print('Warning: Exception creating scale path (may already exist).')
        pass
    src_path = os.path.join(subdir_path, 'img_src')
    print('create_project_structure_directories | Creating ' + src_path)
    try:
        os.mkdir(src_path)
    except:
        # NOTE: some commented lines here were discarded
        print('Warning: Exception creating "img_src" path (may already exist).')
        pass
    aligned_path = os.path.join(subdir_path, 'img_aligned')
    print('create_project_structure_directories | Creating ' + aligned_path)
    try:
        os.mkdir(aligned_path)
    except:
        print('Warning: Exception creating "img_aligned" path (may already exist).')
        pass
    bias_data_path = os.path.join(subdir_path, 'bias_data')
    print('create_project_structure_directories | Creating ' + bias_data_path)
    try:
        os.mkdir(bias_data_path)
    except:
        print('Warning: Exception creating "bias_data" path (may already exist).')
        pass


def generate_scales_queue():
    print("Displaying define scales dialog to receive user input...")
    global project_data #0528
    #todo come back to this #0406
    # try:
    #     self.scales_combobox.disconnect()
    # except Exception:
    #     print(
    #         "BenignException: could not disconnect scales_combobox from handlers or nothing to disconnect. Continuing...")

    #0531 TODO: NEED TO HANDLE CHANGING OF NUMBER OF SCALES, ESPECIALLY WHEN DECREASED. MUST REMOVE PRE-EXISTING DATA (bias data, scaled images, and aligned images)

    main_window.scales_combobox_switch = 0

    default_scales = ['1']
    cur_scales = [str(v) for v in sorted([get_scale_val(s) for s in project_data['data']['scales'].keys()])]
    if len(cur_scales) > 0:
        default_scales = cur_scales

    #0406 #todo Greyed out text "No Scales" would be good
    input_val, ok = QInputDialog().getText(None, "Define Scales",
                                           "Please enter your scaling factors separated by spaces." \
                                           "\n\nFor example, to generate 1x 2x and 4x scale datasets: 1 2 4\n\n"
                                           "Your current scales: " + str(' '.join(default_scales)),
                                           echo=QLineEdit.Normal,
                                           text=' '.join(default_scales))
    if ok:
        print("generate_scales_queue | User picked OK - Continuing")
        main_window.set_scales_from_string(input_val)
    else:
        print("generate_scales_queue | User did NOT pick OK - Canceling")
        return


    main_window.status.showMessage("Generating scales...")
    main_window.hud.post('Generating scales...')
    image_scales_to_run = [get_scale_val(s) for s in sorted(project_data['data']['scales'].keys())]

    print("generate_scales_queue | Generating images for these scales: " + str(image_scales_to_run))

    if (project_data['data']['destination_path'] == None) or (
            len(project_data['data']['destination_path']) <= 0):

        show_warning("Note", "Scales cannot be generated without a destination. Please first 'Save Project As...'")

    else:

        print("generate_scales_queue | Counting CPUs and configuring platform-specific path to executables for C SWiFT-IR")

        # Use task_queue_mp
        scaling_queue = task_queue.TaskQueue()
        cpus = psutil.cpu_count(logical=False)

        if cpus > 48:
            cpus = 48

        print('generate_scales_queue | Starting the scaling queue...')
        tqdm(scaling_queue.start(cpus))  # cpus = 8 for my laptop
        print("generate_scales_queue | # cpus        :", cpus)

        # Configure platform-specific path to executables for C SWiFT-IR
        my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        my_system = platform.system()
        my_node = platform.node()
        print("generate_scales_queue | my_path       :", my_path)
        print("generate_scales_queue | my_system     :", my_system)
        print("generate_scales_queue | my_node       :", my_node)

        if my_system == 'Darwin':
            iscale2_c = my_path + '../c/bin_darwin/iscale2'
        elif my_system == 'Linux':
            if '.tacc.utexas.edu' in my_node:
                iscale2_c = my_path + '../c/bin_tacc/iscale2'
            else:
                iscale2_c = my_path + '../c/bin_linux/iscale2'


        for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'

            print("generate_scales_queue | Preparing to generate images for scale " + str(scale))
            main_window.status.showMessage("Preparing to generate images for scale " + str(scale) + " ...")

            scale_key = str(scale)
            if not 'scale_' in scale_key:
                scale_key = 'scale_' + scale_key

            subdir_path = os.path.join(project_data['data']['destination_path'], scale_key)
            # scale_1_path = os.path.join(project_data['data']['destination_path'], 'scale_1')

            create_project_structure_directories(subdir_path)

            for layer in project_data['data']['scales'][scale_key]['alignment_stack']:
                # Remove previously aligned images from panel ??

                # Copy (or link) the source images to the expected scale_key"/img_src" directory
                for role in layer['images'].keys():

                    # Only copy files for roles "ref" and "base"

                    if role in ['ref', 'base']:
                        # print("  Generating images for scale : " + str(scale) + "  layer: "\
                        #       + str(project_data['data']['scales'][scale_key]['alignment_stack'].index(layer))\
                        #       + "  role: " + str(role))
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
                                            # print("generate_scales_queue | UnLinking " + outfile_name)
                                            os.unlink(outfile_name)
                                        except:
                                            pass
                                            # print("generate_scales_queue | Error UnLinking " + outfile_name)
                                        try:
                                            # print("generate_scales_queue | Linking from " + abs_file_name + " to " + outfile_name)
                                            os.symlink(abs_file_name, outfile_name)
                                        except:
                                            print("generate_scales_queue | Unable to link from " + abs_file_name + " to " + outfile_name)
                                            print("generate_scales_queue | Copying file instead")
                                            # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                                            try:
                                                shutil.copy(abs_file_name, outfile_name)
                                            except:
                                                print("generate_scales_queue | Unable to link or copy from " + abs_file_name + " to " + outfile_name)
                                else:
                                    try:
                                        # Do the scaling
                                        # print(
                                        #     "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                        #         scale))

                                        if os.path.split(os.path.split(os.path.split(abs_file_name)[0])[0])[
                                            1].startswith('scale_'):
                                            # Convert the source from whatever scale is currently processed to scale_1
                                            p, f = os.path.split(abs_file_name)
                                            p, r = os.path.split(p)
                                            p, s = os.path.split(p)
                                            abs_file_name = os.path.join(p, 'scale_1', r, f)

                                        code_mode = 'c'  # force c code scaling implementation

                                        if code_mode == 'python':
                                            scaling_queue.add_task(cmd=sys.executable,
                                                                   args=['single_scale_job.py', str(scale),
                                                                         str(abs_file_name), str(outfile_name)], wd='.')
                                        else:
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
                                        print("Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale))
                                        print_exception()

                                # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                                print_debug(40, "generate_scales_queue | Original File Name: " + str(layer['images'][role]['filename']))
                                layer['images'][role]['filename'] = outfile_name
                                print_debug(40, "generate_scales_queue | Updated  File Name: " + str(layer['images'][role]['filename']))

        ### Join the queue here to ensure that all have been generated before returning
        #      scaling_queue.work_q.join() # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
        t0 = time.time()
        scaling_queue.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
        dt = time.time() - t0
        print("generate_scales_queue |  Scales Completed in %.2f seconds" % (dt))
        scaling_queue.stop()
        del scaling_queue

        #0531
        try:
            isProjectScaled()
        except:
            print('generate_scales_queue | Project is not scaled - Returning')
            return None

        main_window.apply_project_defaults()
        main_window.set_progress_stage_2()
        main_window.read_project_data_update_gui()
        main_window.reload_scales_combobox() #0529 moved this from read_project_data_update_gui because it only should be done this one time
        main_window.scales_combobox.setCurrentIndex(main_window.scales_combobox.count() - 1)
        main_window.center_all_images()
        main_window.scales_combobox_switch = 1
        main_window.update_interface_current_scale()
        main_window.update_project_inspector()

        print("\nGenerating scales complete.\n")
        main_window.status.showMessage("Generating scales complete.")

# Load the image
def load_image_worker(real_norm_path, image_dict):
    print_debug(50, "load_image_worker started with:", str(real_norm_path))
    image_dict['image'] = QPixmap(real_norm_path) # no class
    image_dict['loaded'] = True
    image_dict['loading'] = False
    print_debug(50, "load_image_worker finished for:" + str(real_norm_path))
    image_library.print_load_status()


'''
Qt provides four classes for handling image data: QImage, QPixmap, QBitmap and QPicture. QImage is designed and 
optimized for I/O, and for direct pixel access and manipulation, while QPixmap is designed and optimized for showing 
images on screen. QBitmap is only a convenience class that inherits QPixmap, ensuring a depth of 1. The isQBitmap() 
function returns true if a QPixmap object is really a bitmap, otherwise returns false. Finally, the QPicture class is 
a paint device that records and replays QPainter commands.
'''

#imagelibrary
class ImageLibrary:
    """ THIS IS THE CLASS CURRENTLY IN USE, INITIALIZED WITH NAME 'image_library'
    A class containing multiple images keyed by their file name."""

    def __init__(self):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey(self, file_path):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def print_load_status(self):
        if 0:
            print_debug(50, " Library has " + str(len(self._images.keys())) + " images")
            print_debug(50, "  Names:   " + str(sorted([str(s[-7:]) for s in self._images.keys()])))
            print_debug(50, "  Loaded:  " + str(
                sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loaded']])))
            print_debug(50, "  Loading: " + str(
                sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loading']])))
        else:
            return

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

                #0526
                # image = QImage(real_norm_path)
                # self._images[real_norm_path] = {'image': QPixmap.fromImage(image).scaled(200, 200), 'loaded': True, 'loading': False,'task': None}

                self._images[real_norm_path] = {'image': QPixmap(real_norm_path), 'loaded': True, 'loading': False,'task': None} #orig
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
        # print("  ImageLayer is removing image reference (called by " + inspect.stack()[1].function + ")...")
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
        # print('  ImageLibrary.make_available called by ' + inspect.stack()[1].function + '...')
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        print('Making these images available ', str(sorted([str(s[-7:]) for s in requested])))
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
        # print("ImageLibrary is removing all images (called by " + inspect.stack()[1].function + ")...")
        keys = list(self._images.keys())
        for k in keys:
            self.remove_image_reference(k)
        self._images = {}

    def update(self):
        pass

image_library = ImageLibrary() #imagelibrary #0526


def image_completed_loading(par):
    print('\n' + 100 * '$' + '\n' + 100 * '$')
    print("Got: " + str(par))
    print("Image completed loading, check if showing and repaint as needed.")
    ## The following is needed to auto repaint, but it crashes instantly.
    ##alignem_swift.main_win.image_panel.refresh_all_images()
    print('\n' + 100 * '$' + '\n' + 100 * '$')


'''THIS IS CALED ONLY BY SmartImageLibrary, which is not in use'''
def image_loader(real_norm_path, image_dict):
    '''Load images using psutil.virtual_memory()'''
    try:
        # Load the image
        print_debug(5, "  image_loader started with: \"" + str(real_norm_path) + "\"")
        m = psutil.virtual_memory() #0526
        print_debug(5, "    memory available before loading = " + str(m.available))

        image_dict['image'] = QPixmap(real_norm_path) # no class
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
        return self.get_image_reference(file_path)

    def queue_image_read(self, file_path):
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

#zoompanwidget
class ZoomPanWidget(QWidget):
    """A widget to display a single annotated image with zooming and panning."""

    def __init__(self, role, parent=None):
        super(ZoomPanWidget, self).__init__(parent)
        self.role = role #current role

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

        self.need_to_center = 0

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

        #0605 following 6 lines were commented
        # QApplication.instance().focusChanged.connect(self.on_focusChanged)
    #
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
            # self.draw_border = self.parent.draw_border #border #0520
            self.draw_annotations = self.parent.draw_annotations
            self.draw_full_paths = self.parent.draw_full_paths
        super(ZoomPanWidget, self).update()

        #04-04 #maybe better at the end of change_layer?
        if getCurSNR() is None:
            self.setToolTip(self.role + "\n" + str(getCurScale()) + '\n' + "Unaligned")  # tooltip #settooltip
        else:
            self.setToolTip(self.role + "\n" + str(getCurScale()) + '\n' + str(getCurSNR()))  # tooltip #settooltip

    def show_actual_size(self):
        # print("Showing actual size | ZoomPanWidget.show_actual_size...")
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        # self.zoom_to_wheel_at ( 0, 0 ) #pyside2
        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  #pyside6
        clear_crop_settings()

    # ZoomPanWidget.center_image called once for each role/panel
    def center_image(self, all_images_in_stack=True):
        # print("  ZoomPanWidget is centering image for " + str(self.role))

        if project_data != None:
            # s = getCurScale()
            s = project_data['data']['current_scale']
            l = project_data['data']['current_layer']

            if len(project_data['data']['scales']) > 0:
                #print("s = ", s) #0406
                # if len(project_data['data']['scales'][s]['alignment_stack']) > 0: #0509
                if len(project_data['data']['scales'][s]['alignment_stack']):

                    image_dict = project_data['data']['scales'][s]['alignment_stack'][l]['images']

                    if self.role in image_dict.keys():
                        # print("current role: ", self.role)
                        ann_image = image_dict[self.role] # <class 'dict'>
                        # class is ZoomPanWidget
                        pixmap = image_library.get_image_reference(ann_image['filename']) #  <class 'PySide6.QtGui.QPixmap'>

                        if pixmap is None:
                            print("center_image | EXCEPTION | 'pixmap' is set to None")
                        else:
                            pass

                        if (pixmap != None) or all_images_in_stack:
                            img_w = 0
                            img_h = 0
                            if pixmap != None:
                                img_w = pixmap.width()
                                img_h = pixmap.height()
                            win_w = self.width()
                            win_h = self.height()
                            # print("win_w = %d, win_h = %d" % (win_w, win_h))

                            if all_images_in_stack:

                                # Search through all images in this stack to find bounds
                                stack = project_data['data']['scales'][s]['alignment_stack']
                                for layer in stack:
                                    if 'images' in layer.keys():
                                        if self.role in layer['images'].keys():
                                            #0407
                                            other_pixmap = image_library.get_image_reference_if_loaded(
                                                layer['images'][self.role]['filename'])
                                            if other_pixmap != None:
                                                other_w = other_pixmap.width()
                                                other_h = other_pixmap.height()
                                                img_w = max(img_w, other_w)
                                                img_h = max(img_h, other_h)

                            if (img_w <= 0) or (img_h <= 0) or (win_w <= 0) or (win_h <= 0):  # Zero or negative dimensions might lock up?
                                self.need_to_center = 1
                                print("center_image | EXCEPTION | Image or Window dimension is zero. Cannot center image for role \"" + str(self.role) + "\"")

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
                                    print_debug(80, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                    if abs(self.wheel_index) > 100:
                                        print_debug(-1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index))
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
                                    print_debug(80, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                    if abs(self.wheel_index) > 100:
                                        print_debug(-1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index))
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



    '''
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

            # if alignem_swift.main_win.mouse_down_callback != None:
            # if alignem_swift.main_win.mouse_down_callback is not None:
            try:
                # event_handled = alignem_swift.main_win.mouse_down_callback(self.role, (ex, ey),
                #                                                 (self.image_x(ex), self.image_y(ey)),
                #                                                 int(event.button()))
                event_handled = main_window.mouse_down_callback(self.role, (ex, ey),
                                                                           (self.image_x(ex), self.image_y(ey)),
                                                                           int(event.button()))
            except:
                print("ZoomPanWidget.mousePressEvent | WARNING | unable to define event_handled")

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
            # mode = crop_mode_callback()  #bug #0503
            mode = 'View' #hardcoded #0503
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

            # if alignem_swift.main_win.mouse_move_callback != None:
            # if alignem_swift.main_win.mouse_move_callback is not None:
            # if not alignem_swift.main_win.mouse_move_callback:
            try:
                #0503
                # event_handled = alignem_swift.main_win.mouse_move_callback(self.role, (0, 0), (0, 0),
                #                                                 int(event.button()))  # These will be ignored anyway for now
                event_handled = main_window.mouse_move_callback(self.role, (0, 0), (0, 0),
                                                                           int(event.button()))  # These will be ignored anyway for now
            except:
                print("ZoomPanWidget.mouseMoveEvent | WARNING | unable to define event_handled")

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

        #remove #0405 #keep crop_mode false
        #jy if I need to reimplement crop mode, do it differently, not through crop_mode_callback and derived widgets
        # if crop_mode_callback != None:
        #     mode = crop_mode_callback()
        #     if mode == 'Crop':
        #         crop_mode = True

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
    '''

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
        # print('ZoomPanWidget.change_layer')
        global project_data
        global main_window
        global preloading_range

        scale = project_data['data']['scales'][project_data['data']['current_scale']]
        try:
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
        except:
            print('ZoomPanWidget.change_layer | EXCEPTION | no layer loaded - Aborting')
            return

        leaving_layer = project_data['data']['current_layer']
        entering_layer = project_data['data']['current_layer'] + layer_delta
        print("ZoomPanWidget.change_layer | Changing layer from %s to %s" % (leaving_layer, entering_layer))

        if entering_layer < 0:
            entering_layer = 0

        try:
            main_window.read_gui_update_project_data() #0523 swapping my function in for view_change_callback
        except:
            print("ZoomPanWidget.change_layer | EXCEPTION : ", str(sys.exc_info()))

        local_scales = project_data['data']['scales']  # This will be a dictionary keyed with "scale_#" keys
        local_cur_scale = getCurScale()
        if local_cur_scale in local_scales:
            local_scale = local_scales[local_cur_scale]
            if 'alignment_stack' in local_scale:
                local_stack = local_scale['alignment_stack']
                if len(local_stack) <= 0:
                    print('ZoomPanWidget.change_layer | len(local_stack) is <= 0')
                    print("ZoomPanWidget.change_layer | setting: project_data['data']['current_layer'] = 0")
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


                    project_data['data']['current_layer'] = local_current_layer # this seems to be the layer change

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

        image_library.update() #orig
        self.update_zpa_self() #orig
        self.update_siblings() #orig

        try:
            scale = project_data['data']['scales'][project_data['data']['current_scale']]
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
            base_file_name = layer['images']['base']['filename']
            print('ZoomPanWidget.change_layer | New current base layer is ', base_file_name)
        except:
            print('ZoomPanWidget.change_layer | EXCEPTION | Something is wrong. No layer was loaded.')
            return

        main_window.read_project_data_update_gui() #0523

        # hack to fix center bug when proj is closed on layer 1 (ref not loaded) > re-open project > change_layer
        if self.need_to_center == 1:
            main_window.center_all_images()
            self.need_to_center = 0

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
        global main_win #0529
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
            self.wheel_index += event.angleDelta().y() / 120  # pyside62
            # self.zoom_to_wheel_at(event.x(), event.y())
            # AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'x'
            self.zoom_to_wheel_at(event.position())  # return type: PySide6.QtCore.QPointF

    # todo
    # mainWindow.paintEvent is called very frequently. No need to initialize multiple global variables more than once.
    # Get rid of the cruft, try to limit these function calls
    def paintEvent(self, event):
        # global crop_mode_role  #tag why repeatedly define these globals on each paint event?
        # global crop_mode_disp_rect

        if not self.already_painting:
            self.already_painting = True

            # print("standalone function attempting paintEvent...")

            painter = QPainter(self)

            role_text = self.role
            img_text = None

            if project_data != None:

                s = project_data['data']['current_scale']
                l = project_data['data']['current_layer']

                role_text = str(self.role) + " [" + str(s) + "]" + " [" + str(l) + "]"

                if len(project_data['data']['scales']) > 0:
                    # if 1: #monkey patch
                    if len(project_data['data']['scales'][s]['alignment_stack']) > 0: #debug #tag # previously uncommented

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
                                    pass
                                    # Draw an optional border around the image
                                    # painter.setPen(QPen(QColor(255, 255, 255, 255), 4))
                                    # painter.drawRect(
                                    #     QRectF(self.ldx + self.dx, self.ldy + self.dy, pixmap.width(), pixmap.height()))
                                # Draw the pixmap itself on top of the border to ensure every pixel is shown
                                if (not is_skipped) or self.role == 'base':
                                    painter.drawPixmap(QPointF(self.ldx + self.dx, self.ldy + self.dy), pixmap)

                                # Draw any items that should scale with the image

                            # Rescale the painter to draw items at screen resolution
                            painter.scale(1.0 / self.zoom_scale, 1.0 / self.zoom_scale)

                            # Draw the borders of the viewport for each panel to separate panels
                            # painter.setPen(QPen(self.border_color, 4)) #0523
                            painter.drawRect(painter.viewport()) #0523

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
                                self.center_image() #0503 I think this helps
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

            # if self.role == crop_mode_role:
            #     if crop_mode_disp_rect != None:
            #         painter.setPen(QPen(QColor(255, 100, 100, 255), 3))
            #         rect_to_draw = QRectF(self.win_x(crop_mode_disp_rect[0][0]), self.win_y(crop_mode_disp_rect[0][1]),
            #                               self.win_x(crop_mode_disp_rect[1][0] - crop_mode_disp_rect[0][0]),
            #                               self.win_y(crop_mode_disp_rect[1][1] - crop_mode_disp_rect[0][1]))
            #         painter.drawRect(rect_to_draw)

            # Note: It's difficult to use this on a Mac because of the focus policy combined with the shared single menu.
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

            # print("standalone function exiting paintEvent")
            painter.end()
            del painter

            self.already_painting = False

#multiimagepanel
class MultiImagePanel(QWidget):

    def __init__(self):
        super(MultiImagePanel, self).__init__()

        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.black)
        self.setPalette(p)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color:black;")

        # self.current_margin = 0
        self.hb_layout = QHBoxLayout()
        # self.update_spacing()
        self.setLayout(self.hb_layout)
        self.actual_children = []
        self.setContentsMargins(0, 0, 0, 0)
        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False
        # self.bg_color = QColor(40, 50, 50, 255)
        self.bg_color = QColor(0, 0, 0, 255) #0407 #color #background
        self.border_color = QColor(0, 0, 0, 255)

        # QWidgets don't get the keyboard focus by default
        # To have scrolling keys associated with this (multi-panel) widget, set a "StrongFocus"
        self.setFocusPolicy(Qt.StrongFocus)  #tag #add #0526 uncommenting, because not certain it does anything and have zoom issue
        self.arrow_direction = 1

    #keypress
    def keyPressEvent(self, event):

        print("\nKey press event: " + str(event))

        layer_delta = 0
        if event.key() == Qt.Key_Up:
            layer_delta = 1 * self.arrow_direction
        if event.key() == Qt.Key_Down:
            layer_delta = -1 * self.arrow_direction

        if (layer_delta != 0) and (self.actual_children != None):
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in [panels_to_update[0]]:  # Only update the first one which will update the rest
                p.change_layer(layer_delta)
                p.update_zpa_self()
                p.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
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

    def update_multi_self(self, exclude=()):
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget) and (not (w in exclude))]
            for p in panels_to_update:
                p.border_color = self.border_color
                p.update_zpa_self()
                p.repaint()

    def add_panel(self, panel):
        if not panel in self.actual_children:
            self.actual_children.append(panel)
            self.hb_layout.addWidget(panel)
            panel.set_parent(self)
            self.repaint()

    def set_roles(self, roles_list):
        print("MultiImagePanel.set_roles:")
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
                # zpw.draw_border = self.draw_border #border #0520
                zpw.draw_annotations = self.draw_annotations
                zpw.draw_full_paths = self.draw_full_paths
                self.add_panel(zpw)

    def remove_all_panels(self):
        print("MultiImagePanel.remove_all_panels:")
        while len(self.actual_children) > 0:
            self.hb_layout.removeWidget(self.actual_children[-1])
            self.actual_children[-1].deleteLater()
            self.actual_children = self.actual_children[0:-1]
        self.repaint()

    def refresh_all_images(self):
        print('MultiImagePanel.refresh_all_images (caller=%s):' % str(inspect.stack()[1].function))
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.update_zpa_self()
                p.repaint()
        self.repaint()

        # if alignem_swift.main_win.isProjectOpen():
        if getCurSNR() is None:
            self.setToolTip(str(getCurScale()) + '\n' + "Unaligned")  # tooltip #settooltip
        else:
            self.setToolTip(str(getCurScale()) + '\n' + str(getCurSNR()))  # tooltip #settooltip

    def center_all_images(self, all_images_in_stack=True):
        # print('MultiImagePanel.center_all_images (caller=%s):' % str(inspect.stack()[1].function))
        if self.actual_children != None:
            #NOTE THIS CALL CAN BE USED TO OBTAIN HANDLES TO THE THREE ZoomPanWidget OBJECTS
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.center_image(all_images_in_stack=all_images_in_stack)
                p.update_zpa_self()
                p.repaint()
        self.repaint()
        self.refresh_all_images() #jy

    def all_images_actual_size(self):
        print("MultiImagePanel.all_images_actual_size:")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.show_actual_size()
                p.update_zpa_self()
                p.repaint()
        self.repaint()


def null_bias_changed_callback(state):
    print('\nnull_bias_changed_callback(state):' % str(state))
    print('  Null Bias project_file value was:', project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends'])
    if state:
        project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends'] = True
    else:
        project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends'] = False
    print('  Null Bias project_file value saved as: ', project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends'])

def bounding_rect_changed_callback(state):
    print('bounding_rect_changed_callback(state=%s):' % str(state))
    # print('  Bounding Rect project_file value was:', project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'])
    if state:
        project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'] = True
    else:
        project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'] = False
    # print('  Bounding Rect project_file value saved as:',project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'])

def skip_changed_callback(state):  # 'state' is connected to skip toggle
    print("\nskip_changed_callback(state=%s):" % str(state))
    # This function gets called whether it's changed by the user or by another part of the program!!!
    # global ignore_changes #0528
    # called by:  change_layer <-- when ZoomPanWidget.change_layer toggles
    # called by:  run_app <-- when user toggles
    # skip_list = []
    # for layer_index in range(len(project_data['data']['scales'][getCurScale()]['alignment_stack'])):
    #     if project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index]['skip'] == True:
    #         skip_list.append(layer_index)

    if areImagesImported():
        skip_list = getSkipsList()
        if inspect.stack()[1].function == 'run_app':
            toggle_state = state
            new_skip = not state
            print('skip_changed_callback | toggle_state: ' + str(toggle_state) + '  skip_list: ' + str(skip_list) + 'new_skip: ' + str(new_skip))
            scale = project_data['data']['scales'][project_data['data']['current_scale']]
            layer = scale['alignment_stack'][project_data['data']['current_layer']]
            layer['skip'] = new_skip  # skip # this is where skip list is appended to
            # if update_skips_callback != None:
            #     # update_skips_callback(bool(state)) #og
            #     # update_skips_callback(new_skip)  #jy
            copy_skips_to_all_scales()
        else:
            print("skip_changed_callback | EXCEPTION | not called by run_app")

        link_all_stacks() #0525
        main_window.update_panels()
        main_window.refresh_all_images()
        skip_list = getSkipsList()
        # update_linking_callback()

        #0503 possible non-centering bug that occurs when runtime skips change is followed by scale change
        if center_switch:
            main_window.image_panel.center_all_images()


def console():
    print("\nEntering Python console:\n")
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
    ds_aligned = str("aligned_" + getCurScale())
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

# blend
def blend(s):
    print("\n'b' key press detected. Executing blend callback function...\n")
    print("current working dir :", os.getcwd())
    destination_path = os.path.abspath(project_data['data']['destination_path'])
    src = zarr_project_path = os.path.join(destination_path, "project.zarr")
    ds_aligned = str("aligned_" + getCurScale())
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




'''
QRunnable and QThreadPool. The former is the container for the work you want to perform, while the latter is the
method by which you pass that work to alternate threads.

#0526
'''
class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.
    Supported signals are:

    finished - No data
    error - tuple (exctype, value, traceback.format_exc() )
    result - object data returned from processing, anything
    progress - int indicating % progress
    '''
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    '''
    Worker thread
    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    :param callback: The function callback to run on this worker thread. Supplied args and kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


# server #runnable
class RunnableServerThread(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self):
        super(RunnableServerThread, self).__init__()
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

class ToggleSwitch(QCheckBox):
    _transparent_pen = QPen(Qt.transparent)
    _light_grey_pen = QPen(Qt.lightGray)
    _black_pen = QPen(Qt.black)

    def __init__(self,
                 parent=None,
                 bar_color=Qt.gray,
                 # checked_color="#00B0FF",
                 # checked_color="#607cff",
                 # checked_color="#d3dae3",  # monjaromix stylesheet
                 checked_color="#00ff00",

                 handle_color=Qt.white,
                 h_scale=.7,
                 v_scale=.9,
                 fontSize=10):

        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)  # focus don't steal focus from zoompanwidget

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())
        self._handle_brush = QBrush(handle_color)
        # self._handle_checked_brush = QBrush(QColor(checked_color))
        self._handle_checked_brush = QBrush(QColor('#151a1e'))
        # self.light_brush = QBrush(QColor(0, 0, 0))]
        # this setContentMargins can cause issues with painted region, might need to stick to 8,0,8,0
        self.setContentsMargins(0, 0, 2, 0) #left,top,right,bottom
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize

        self.stateChanged.connect(self.handle_state_change)

        self.setFixedWidth(40)

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        # return QSize(76, 30)
        return QSize(80, 35)

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
            p.setPen(self._black_pen)
            p.setBrush(self._handle_checked_brush)
            # p.setFont(QFont('Helvetica', self._fontSize, 75, QFont.Bold)) # for some reason this makes the font italic (?)
            p.setFont(QFont('Helvetica', self._fontSize, 75))
            # p.drawText(xLeft + handleRadius / 2, contRect.center().y() + handleRadius / 2, "KEEP")

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._black_pen)
            p.setBrush(self._handle_brush)
            p.setFont(QFont('Helvetica', self._fontSize, 75))
            # p.drawText(contRect.center().x(), contRect.center().y() + handleRadius / 2, "SKIP")

        p.setPen(self._light_grey_pen)
        p.drawEllipse(QPointF(xPos, barRect.center().y()), handleRadius, handleRadius)
        p.end()

    @Slot(int)
    def handle_state_change(self, value):
        print("ToggleSwitch.handle_state_change:")
        self._handle_position = 1 if value else 0

    @Property(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
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



class ToggleSkipSwitch(QCheckBox):
    _transparent_pen = QPen(Qt.transparent)
    _light_grey_pen = QPen(Qt.lightGray)
    _black_pen = QPen(Qt.black)
    white_pen = QPen(Qt.white)

    def __init__(self,
                 parent=None,
                 bar_color=Qt.gray,
                 checked_color="#00ff00",
                 handle_color=Qt.white,
                 h_scale=1.0,
                 v_scale=0.9,
                 fontSize=8):

        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)  # focus don't steal focus from zoompanwidget

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())
        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor('#151a1e'))
        self.setContentsMargins(0, 0, 8, 0) #left,top,right,bottom
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize

        self.stateChanged.connect(self.handle_state_change)

        self.setFixedWidth(54)

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        # return QSize(76, 30)
        return QSize(80, 35)

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
            p.setPen(self._black_pen)
            # p.setPen(self.white_pen)
            p.setBrush(self._handle_checked_brush)
            # p.setFont(QFont('Helvetica', self._fontSize, 75, QFont.Bold)) # oddly makes the font italic
            p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.drawText(xLeft + handleRadius / 2, contRect.center().y() + handleRadius / 2, "KEEP")

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._black_pen)
            p.setBrush(self._handle_brush)
            # p.setFont(QFont('Helvetica', self._fontSize, 75, QFont.Bold))
            p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.drawText(contRect.center().x(), contRect.center().y() + handleRadius / 2, "SKIP")

        p.setPen(self._light_grey_pen)
        p.drawEllipse(QPointF(xPos, barRect.center().y()), handleRadius, handleRadius)
        p.end()

    @Slot(int)
    def handle_state_change(self, value):
        print("ToggleSkipSwitch.handle_state_change:")
        self._handle_position = 1 if value else 0

    @Property(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
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




'''
https://github.com/fzls/djc_helper/blob/master/qt_collapsible_box.py
'''
class CollapsibleBox(QWidget):
    def __init__(self, title="", title_backgroup_color="", tool_tip="Project Inspector :)", animation_duration_millseconds=250, parent=None):
        super(CollapsibleBox, self).__init__(parent)

        self.title = title
        self.setToolTip(tool_tip)
        self.animation_duration_millseconds = animation_duration_millseconds
        self.collapsed_height = 19
        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(title)

        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.toggle_button.setSizePolicy(sizePolicy)

        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet(f"QToolButton {{ border: none; font-weight: bold; background-color: #7c7c7c; }}")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.toggle_animation = QParallelAnimationGroup(self)

        self.content_area = QScrollArea(self)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_area.setFrameShape(QFrame.NoFrame)

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(QPropertyAnimation(self, b"minimumHeight"))
        self.toggle_animation.addAnimation(QPropertyAnimation(self, b"maximumHeight"))
        self.toggle_animation.addAnimation(QPropertyAnimation(self.content_area, b"maximumHeight"))
    @Slot()
    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.DownArrow if not checked else Qt.RightArrow)
        self.toggle_animation.setDirection(
            QAbstractAnimation.Forward
            if not checked
            else QAbstractAnimation.Backward
        )
        self.toggle_animation.start()

    def setContentLayout(self, layout):
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = (self.sizeHint().height() - self.content_area.maximumHeight())
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            # animation.setDuration(500)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
        # content_animation.setDuration(500)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)


#mainwindow
class MainWindow(QMainWindow):
    def __init__(self, fname=None, panel_roles=None, title="AlignEM-SWiFT"):
        self.pyside_path = os.path.dirname(os.path.realpath(__file__))
        print("MainWindow | pyside_path is ", self.pyside_path)

        print('MainWindow | Setting MESA_GL_VERSION_OVERRIDE')
        os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
        print('MainWindow | MESA_GL_VERSION_OVERRIDE = ', os.environ.get('MESA_GL_VERSION_OVERRIDE'))

        # print('Setting QSurfaceFormat.defaultFormat()...')
        # self.default_format = QSurfaceFormat.defaultFormat()

        print("MainWindow | Setting up thread pool")
        self.threadpool = QThreadPool() #test
        print("MainWindow | Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

        self.init_dir = os.getcwd()

        # # NOTE: You must set the AA_ShareOpenGLContexts flag on QGuiApplication before creating the QGuiApplication
        # # object, otherwise Qt may not create a global shared context.
        # # https://doc.qt.io/qtforpython-5/PySide2/QtGui/QOpenGLContext.html
        # print('Current QOpenGLContext = ', QOpenGLContext.currentContext())

        # QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        # # QtCore.QProcessEnvironment.systemEnvironment() ???
        # print('Current QOpenGLContext = ', QOpenGLContext.currentContext())

        global app
        if app == None:
            print("MainWindow | No pre-existing QApplication instance, defining new global | app = QApplication([])")
            app = QApplication([])
        else:
            print("MainWindow | WARNING | Existing QApplication instance found, continuing...")

        # print("MainWindow | defining global 'project_data'")
        print("MainWindow | copying 'new-project_template' dict to project_data")
        global project_data
        project_data = copy.deepcopy(new_project_template)

        print('MainWindow | initializing QMainWindow.__init__(self)')
        QMainWindow.__init__(self)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(QPixmap('sims.png')))
        self.current_project_file_name = None
        # self.view_change_callback = None
        self.mouse_down_callback = None
        self.mouse_move_callback = None

        '''This will require moving the image_panel = ImageLibrary() to MainWindow constructor where it should be anyway'''
        # self.define_roles(['ref', 'base', 'aligned'])

        '''Fix for error message which results from multiprocessing crashing when using TaskQueue w/ PyCharm debugger.

        objc[53148]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was
        called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint
        on objc_initializeAfterForkError to debug.
        https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr'''
        # print('alignem_swift.py | Setting OBJC_DISABLE_INITIALIZE_FORK_SAFETY=yes')
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "yes"

        # print("alignem_swift.py | QImageReader.allocationLimit() WAS " + str(QImageReader.allocationLimit()) + "MB")
        QImageReader.setAllocationLimit(4000)
        # print("alignem_swift.py | New QImageReader.allocationLimit() NOW IS " + str(QImageReader.allocationLimit()) + "MB")

        self.setMinimumWidth(800)
        self.setMinimumHeight(400)
        self.resize(2000, 1200)

        self.need_to_center=0

        # self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        # self.setWindowFlag(Qt.FramelessWindowHint)

        # stylesheet must be after QMainWindow.__init__(self)
        # self.setStyleSheet(open('stylesheet.qss').read())
        print("MainWindow | applying stylesheet")
        self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet1.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())

        print("MainWindow | Setting multiprocessing.set_start_method('fork', force=True)...")
        multiprocessing.set_start_method('fork', force=True)


        std_height = int(22)
        std_width = int(118)
        std_button_size = QSize(std_width, std_height)
        square_button_height = int(38)
        square_button_width = int(74)
        square_button_size = QSize(square_button_width,square_button_height)
        std_input_size = int(56)
        std_input_size_small = int(36)

        # titlebar resource
        # https://stackoverflow.com/questions/44241612/custom-titlebar-with-frame-in-pyqt5

        # pyside6 port needed to replace deprecated the 'defaultSettings()' attribute of QWebEngineSettings. These two lines were uncommented.
        # self.web_settings = QWebEngineSettings.defaultSettings()
        # self.web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # pyside6
        print("MainWindow | instantiating QWebEngineView()")
        self.view = QWebEngineView()
        # PySide6 available options
        # self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        print("MainWindow | Setting QWebEngineSettings.LocalContentCanAccessRemoteUrls to True\n")
        print('------------------------------------------------------------\n')
        self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        print('------------------------------------------------------------\n')

        def closeEvent(self, event):

            quit_msg = "Are you sure you want to exit the program?"
            reply = QMessageBox.question(self, 'Message',
                                               quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

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

        # create RunnableServerThread class to start background CORS web server
        def start_server():
            print("MainWindow | creating RunnableServerThread() instance and setting up thread pool")
            worker = RunnableServerThread()
            self.threadpool.start(worker)

        # self.browser.setPage(CustomWebEnginePage(self)) # This is necessary. Clicked links will never open new window.
        # self.browser.setPage(CustomWebEnginePage(self))

        # homepage #browserview #webview
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!%7B%22dimensions%22:%7B%22x%22:%5B8e-9%2C%22m%22%5D%2C%22y%22:%5B8e-9%2C%22m%22%5D%2C%22z%22:%5B8e-9%2C%22m%22%5D%7D%2C%22position%22:%5B2914.500732421875%2C3088.243408203125%2C4045%5D%2C%22crossSectionScale%22:3.762185354999915%2C%22projectionOrientation%22:%5B0.31435418128967285%2C0.8142172694206238%2C0.4843378961086273%2C-0.06040274351835251%5D%2C%22projectionScale%22:4593.980956070108%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/image%22%2C%22tab%22:%22source%22%2C%22name%22:%22image%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/ground_truth%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22158571%22%2C%2221894%22%2C%2222060%22%2C%2224436%22%2C%222515%22%5D%2C%22name%22:%22ground-truth%22%7D%5D%2C%22showSlices%22:false%2C%22layout%22:%224panel%22%7D"))
        # self.browser.load(QUrl("https://github.com/google/neuroglancer"))
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!{'layers':{'original-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image'_'visible':false}_'corrected-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image_color_corrected'}_'ground_truth':{'type':'segmentation'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/ground_truth'_'selectedAlpha':0.63_'notSelectedAlpha':0.14_'segments':['3208'_'4901'_'13'_'4965'_'4651'_'2282'_'3189'_'3758'_'15'_'4027'_'3228'_'444'_'3207'_'3224'_'3710']}}_'navigation':{'pose':{'position':{'voxelSize':[6_6_30]_'voxelCoordinates':[5523.99072265625_8538.9384765625_1198.0423583984375]}}_'zoomFactor':22.573112129999547}_'perspectiveOrientation':[-0.004047565162181854_-0.9566211104393005_-0.2268827110528946_-0.1827099621295929]_'perspectiveZoom':340.35867907175077}"))
        # self.browser.setUrl(QUrl()) # empty/blank URL (white screen)
        # self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        # self.browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/user/README.md'))

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
            print(ng.to_url(self.viewer.state))
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



        def ng_view_2():
            print()


        #ngview
        def ng_view():  # ng_view #ngview #neuroglancer
            print("\n>>>>>>>>>>>>>>>> RUNNING ng_view()\n")
            print("ng_view() | # of aligned images                  : ", getNumAligned())
            if not areAlignedImagesGenerated():
                self.hud.post('This scale must be aligned and exported before viewing in Neuroglancer')
                show_warning("No Alignment Found", "This scale must be aligned and exported before viewing in Neuroglancer.\n\n"
                                             "Typical workflow:\n"
                                             "(1) Open a project or import images and save.\n"
                                             "(2) Generate a set of scaled images and save.\n"
                                             "--> (3) Align each scale starting with the coarsest.\n"
                                             "--> (4) Export alignment to Zarr format.\n"
                                             "(5) View data in Neuroglancer client")
                print("ng_view() | EXCEPTION | This scale must be aligned and exported before viewing in Neuroglancer - Aborting")
                return
            else:
                print('ng_view() | Alignment at this scale exists - Continuing')


            if not isCurScaleExported():
                self.hud.post('Alignment must be exported before it can be viewed in Neuroglancer')
                show_warning("No Export Found", "Alignment must be exported before it can be viewed in Neuroglancer.\n\n"
                                             "Typical workflow:\n"
                                             "(1) Open a project or import images and save.\n"
                                             "(2) Generate a set of scaled images and save.\n"
                                             "(3) Align each scale starting with the coarsest.\n"
                                             "--> (4) Export alignment to Zarr format.\n"
                                             "(5) View data in Neuroglancer client")
                print("ng_view() | EXCEPTION | Alignment must be exported before it can be viewed in Neuroglancer - Aborting")
                return
            else:
                print('ng_view() | Exported alignment at this scale exists - Continuing')

            ds_name = "aligned_" + getCurScale()
            destination_path = os.path.abspath(project_data['data']['destination_path'])
            zarr_project_path = os.path.join(destination_path, "project.zarr")
            zarr_ds_path = os.path.join(destination_path, "project.zarr", ds_name)

            print('ng_view() | zarr_project_path                    :', zarr_project_path)
            print('ng_view() | zarr_ds_path                         :', zarr_ds_path)
            print('ng_view() | zarr_ds_path exists?                 :', bool(os.path.isdir(zarr_ds_path)))


            self.hud.post('Loading Neuroglancer viewer...')
            self.hud.post('Zarr source: ' + zarr_project_path)

            if 'server' in locals():
                print('ng_view() | server is already running')
            else:
                # self.browser.setUrl(QUrl()) #empty page
                print('ng_view() | no server found in local namespace -> starting RunnableServerThread() worker')
                worker = RunnableServerThread()
                self.threadpool.start(worker)

            os.chdir(zarr_project_path)  #refactor

            Image.MAX_IMAGE_PIXELS = None
            view = 'single'
            bind = '127.0.0.1'
            port = 9000
            res_x = 2
            res_y = 2
            res_z = 50

            src = zarr_project_path

            # LOAD METADATA - .zarray
            print('ng_view() | loading metadata from .zarray (array details) file')
            zarray_path = os.path.join(src, ds_name, "s0", ".zarray")
            print("zarray_path : ", zarray_path)
            with open(zarray_path) as f:
                zarray_keys = json.load(f)
            chunks = zarray_keys["chunks"]

            # cname = zarray_keys["compressor"]["cname"] #jy
            # clevel = zarray_keys["compressor"]["clevel"] #jy
            shape = zarray_keys["shape"]
            print("shape : ", shape)

            # LOAD META DATA - .zattrs
            print('ng_view() | loading metadata from .zattrs (attributes) file')
            zattrs_path = os.path.join(src, ds_name, "s0", ".zattrs")
            with open(zattrs_path) as f:
                zattrs_keys = json.load(f)
            print("zattrs_path : ", zattrs_path)
            resolution = zattrs_keys["resolution"]
            # scales = zattrs_keys["scales"]  #0405 #0406 #remove
            # print("scales : ", scales)  #0405 #0406 #remove

            ds_ref = "img_ref_zarr"
            ds_base = "img_base_zarr"
            ds_aligned = ds_name
            ds_blended = "img_blended_zarr"

            print('ng_view() | initializing neuroglancer.Viewer()')
            # viewer = ng.Viewer()
            self.viewer = ng.Viewer()

            print('ng_view() | looking for aligned data')
            data_aligned = []
            aligned_scale_paths = glob(os.path.join(src, ds_aligned) + "/s*")
            for s in aligned_scale_paths:
                scale = os.path.join(ds_aligned, os.path.basename(s))
                print("ng_view() | 'daisy' is opening scale '%s' and appending aligned data" % s)
                data_aligned.append(open_ds(src, scale))

            if view == 'row':
                print("Looking for REF scale directories...")
                data_ref = []
                ref_scale_paths = glob(os.path.join(src, ds_ref) + "/s*")
                for s in ref_scale_paths:
                    scale = os.path.join(ds_ref, os.path.basename(s))
                    print("ng_view() | 'daisy' is opening scale '%s' and appending aligned data" % s)
                    data_ref.append(open_ds(src, scale))

                print('Looking for BASE scale directories...')
                data_base = []
                base_scale_paths = glob(os.path.join(src, ds_base) + "/s*")
                for s in base_scale_paths:
                    scale = os.path.join(ds_base, os.path.basename(s))
                    print("ng_view() | 'daisy' is opening scale '%s' and appending aligned data" % s)
                    data_base.append(open_ds(src, scale))

            print('ng_view() | defining Neuroglancer coordinate space')
            dimensions = ng.CoordinateSpace(
                names=['x', 'y', 'z'],
                units='nm',
                #scales=scales, #jy
                scales=[res_x, res_y, res_z],
            )

            # https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
            print('ng_view() | updating viewer.txn()')
            with self.viewer.txn() as s:

                # s.cross_section_background_color = "#ffffff"
                s.cross_section_background_color = "#000000"
                s.dimensions = dimensions
                # s.perspective_zoom = 300
                # s.position = [0.24, 0.095, 0.14]
                # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

                # temp = np.zeros_like(data_ref)
                # layer = ng.Layer(temp)

                # print("type(data_aligned) = ", type(data_aligned))  # <class 'list'>
                # print("type(data_aligned[0]) = ", type(data_aligned[0]))  # <class 'daisy.array.Array'>
                # print("len(data_aligned) = ", len(data_aligned))  # 2

                array = np.asarray(data_aligned)
                # print("type(array) = ", type(array))                       # <class 'numpy.ndarray'>
                # print("array.shape = ", array.shape)                       # (2,)
                # print("array.size = ", array.size)                         # 2
                # print("array.ndim = ", array.ndim)                         # 1

                print('ng_view() | type(np.asarray(data_aligned))       :', type(np.asarray(data_aligned)))
                print('ng_view() | np.asarray(data_aligned).shape       :', np.asarray(data_aligned).shape)
                print('ng_view() | np.asarray(data_aligned).size        :', np.asarray(data_aligned).size)
                print('ng_view() | np.asarray(data_aligned).ndim        :', np.asarray(data_aligned).ndim)

                print("ng_view() | 'view' is set to                     :", view)
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
                    print("ng_view() | view is 'row'")

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
                    s.layout = ng.column_layout(
                        [
                            ng.LayerGroupViewer(
                                layout='xy',
                                layers=["aligned"]),
                        ]
                    )

            print('ng_view() | loading Neuroglancer callbacks       :', self.viewer.config_state)
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

            viewer_url = str(self.viewer)
            # viewer_url = self.viewer
            self.browser.setUrl(QUrl(viewer_url))
            self.stacked_widget.setCurrentIndex(1)

            # To modify the state, use the viewer.txn() function, or viewer.set_state
            print('ng_view() | Viewer.config_state                  :', self.viewer.config_state)
            # print('ng_view() | viewer URL                           :', self.viewer.get_viewer_url())
            # print('Neuroglancer view (remote viewer)                :', ng.to_url(viewer.state))

            try:
                cur_scale = getCurScale()
            except:
                print('ERROR: There was a problem with getCurScale()')
            self.status.showMessage('Viewing aligned images at ' + cur_scale + ' in Neuroglancer.')

            # #self.browser.setUrl(QUrl()) #empty page
            # worker = RunnableServerThread()
            # print("Setting up thread pool...")
            # self.threadpool.start(worker)

            # print('ng_view() | ', neuroglancer.to_url(self.viewer.state))

            print("\n<<<<<<<<<<<<<<<< EXITING ng_view()\n")


        if panel_roles != None:
            project_data['data']['panel_roles'] = panel_roles

        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False

        self.panel_list = []



        def pretty(d, indent=0):
            for key, value in d.items():
                print('\t' * indent + str(key))
                if isinstance(value, dict):
                    pretty(value, indent + 1)
                else:
                    print('\t' * (indent + 1) + str(value))

        def show_memory_usage():
            os.system('python3 memoryusage.py')

        '''------------------------------------------
        PROJECT INSPECTOR #projectinspector
        ------------------------------------------'''

        self.project_inspector = QDockWidget("Project Inspector")
        self.addDockWidget(Qt.RightDockWidgetArea, self.project_inspector)
        scroll = QScrollArea()
        self.project_inspector.setWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        dock_vlayout = QVBoxLayout(content)

        # Skips List
        self.inspector_scales = CollapsibleBox('Skip List')
        dock_vlayout.addWidget(self.inspector_scales)
        lay = QVBoxLayout()
        self.inspector_label_scales = QLabel('')
        self.inspector_label_scales.setStyleSheet(
                "color: #d3dae3;"
                "border-radius: 12px;"
            )
        lay.addWidget(self.inspector_label_scales, alignment=Qt.AlignTop)
        self.inspector_scales.setContentLayout(lay)

        # CPU Specs
        self.inspector_cpu = CollapsibleBox('CPU Specs')
        dock_vlayout.addWidget(self.inspector_cpu)
        lay = QVBoxLayout()
        label = QLabel("CPU #: %s\nSystem : %s" % ( psutil.cpu_count(logical=False), platform.system() ))
        label.setStyleSheet(
                "color: #d3dae3;"
                "border-radius: 12px;"
            )
        lay.addWidget(label, alignment=Qt.AlignTop)
        self.inspector_cpu.setContentLayout(lay)

        dock_vlayout.addStretch()

        '''------------------------------------------
        PANEL 1: PROJECT #projectpanel
        ------------------------------------------'''

        self.documentation_button = QPushButton("Docs")
        self.documentation_button.clicked.connect(documentation_view)
        self.documentation_button.setFixedSize(square_button_size)

        self.remote_viewer_button = QPushButton("Remote\nNeuroglancer\nViewer")
        self.remote_viewer_button.clicked.connect(remote_view)
        self.remote_viewer_button.setFixedSize(square_button_size)
        self.remote_viewer_button.setStyleSheet("font-size: 9px;")

        self.new_project_button = QPushButton("New\nProject")
        self.new_project_button.clicked.connect(self.new_project)
        self.new_project_button.setFixedSize(square_button_size)

        self.open_project_button = QPushButton("Open")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_project_button.setFixedSize(square_button_size)

        self.save_project_button = QPushButton("Save")
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setFixedSize(square_button_size)

        self.exit_app_button = QPushButton("Exit")
        self.exit_app_button.clicked.connect(self.exit_app)
        self.exit_app_button.setFixedSize(square_button_size)

        self.project_functions_layout = QGridLayout()
        self.project_functions_layout.setContentsMargins(10, 25, 10, 5)
        self.project_functions_layout.setSpacing(10)  # ***
        self.project_functions_layout.addWidget(self.new_project_button, 0, 0, alignment=Qt.AlignHCenter)
        self.project_functions_layout.addWidget(self.open_project_button, 0, 1, alignment=Qt.AlignHCenter)
        self.project_functions_layout.addWidget(self.save_project_button, 0, 2, alignment=Qt.AlignHCenter)
        self.project_functions_layout.addWidget(self.exit_app_button, 1, 0, alignment=Qt.AlignHCenter)
        self.project_functions_layout.addWidget(self.documentation_button, 1, 1, alignment=Qt.AlignHCenter)
        self.project_functions_layout.addWidget(self.remote_viewer_button, 1, 2, alignment=Qt.AlignHCenter)

        '''------------------------------------------
        PANEL 2: DATA SELECTION & SCALING
        ------------------------------------------'''
        #datapanel #scalingpanel #importpanel

        self.import_images_button = QPushButton("Import\nImages")
        self.import_images_button.setToolTip('Import TIFF images.')
        self.import_images_button.clicked.connect(self.import_base_images)
        self.import_images_button.setFixedSize(square_button_size)
        # self.import_images_button.setFixedSize(square_button_width, std_height)

        self.center_button = QPushButton('Center')
        self.center_button.setToolTip('Center all images.')
        self.center_button.clicked.connect(self.center_callback)
        self.center_button.setFixedSize(square_button_width, std_height)

        self.actual_size_button = QPushButton('Actual Size')
        self.actual_size_button.setToolTip('Actual-size all images.')
        self.actual_size_button.clicked.connect(self.actual_size_callback)
        self.actual_size_button.setFixedSize(square_button_width, std_height)

        self.size_buttons_vlayout = QVBoxLayout()
        self.size_buttons_vlayout.addWidget(self.center_button)
        self.size_buttons_vlayout.addWidget(self.actual_size_button)

        self.generate_scales_button = QPushButton('Generate\nScales')
        self.generate_scales_button.setToolTip('Generate a scale hierarchy.')
        self.generate_scales_button.clicked.connect(generate_scales_queue)
        self.generate_scales_button.setFixedSize(square_button_size)
        # self.generate_scales_button.setFixedSize(square_button_width, std_height)
        # self.generate_scales_button.setStyleSheet("font-size: 11px;")

        self.clear_all_skips_button = QPushButton('Reset')
        self.clear_all_skips_button.setToolTip('Reset skips (align all)')
        self.clear_all_skips_button.setMaximumHeight(std_height)
        self.clear_all_skips_button.setFocusPolicy(Qt.NoFocus)
        self.clear_all_skips_button.clicked.connect(clear_all_skips)
        self.clear_all_skips_button.setFixedWidth(50)
        self.clear_all_skips_button.setFixedHeight(std_height)

        self.toggle_skip = ToggleSkipSwitch()  #toggleskip
        self.toggle_skip.setToolTip('Skip current image (do not align)')
        self.toggle_skip.setChecked(True)
        self.toggle_skip.setH_scale(.9)
        self.toggle_skip.setV_scale(1.0)
        self.toggle_skip.toggled.connect(skip_changed_callback)

        self.jump_label = QLabel("Jump To:")
        self.jump_label.setToolTip('Jump to image #')
        self.jump_input = QLineEdit(self)
        self.jump_input.setToolTip('Jump to image #')
        self.jump_input.setAlignment(Qt.AlignHCenter)
        # self.jump_input.setText("--")
        self.jump_input.setFixedSize(std_input_size, std_height)
        self.jump_validator = QIntValidator()
        self.jump_input.setValidator(self.jump_validator)
        # self.jump_input.returnPressed.connect(self.jump_to_layer())
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer()) # must be lambda for some reason
        # self.jump_input.editingFinished.connect(self.jump_to_layer())
        # self.jump_hlayout = QHBoxLayout()
        # self.jump_hlayout.addWidget(jump_label, alignment=Qt.AlignLeft)
        # self.jump_hlayout.addWidget(self.jump_input, alignment=Qt.AlignRight)


        self.images_and_scaling_layout = QGridLayout()
        self.images_and_scaling_layout.setContentsMargins(10, 25, 10, 5) #tag23
        self.images_and_scaling_layout.setSpacing(10) # ***
        self.images_and_scaling_layout.addWidget(self.import_images_button, 0, 0, alignment=Qt.AlignHCenter)
        # self.images_and_scaling_layout.addWidget(self.center_button, 0, 1, alignment=Qt.AlignHCenter)
        self.images_and_scaling_layout.addLayout(self.size_buttons_vlayout, 0, 1, alignment=Qt.AlignHCenter)
        self.images_and_scaling_layout.addWidget(self.generate_scales_button, 0, 2, alignment=Qt.AlignHCenter)
        self.toggle_reset_hlayout = QHBoxLayout()
        self.toggle_reset_hlayout.addWidget(self.toggle_skip, alignment=Qt.AlignLeft)
        self.toggle_reset_hlayout.addWidget(self.clear_all_skips_button, alignment=Qt.AlignHCenter)
        self.toggle_reset_hlayout.addWidget(self.jump_label, alignment=Qt.AlignHCenter)
        self.toggle_reset_hlayout.addWidget(self.jump_input, alignment=Qt.AlignHCenter)
        # self.toggle_reset_hlayout.addLayout(self.jump_hlayout, alignment=Qt.AlignHCenter)
        # self.images_and_scaling_layout.addWidget(self.toggle_skip, 1, 0, alignment=Qt.AlignHCenter)
        # self.images_and_scaling_layout.addWidget(self.clear_all_skips_button, 1, 1, alignment=Qt.AlignHCenter)
        self.images_and_scaling_layout.addLayout(self.toggle_reset_hlayout, 1, 0, 1, 3, alignment=Qt.AlignHCenter)
        # self.images_and_scaling_layout.addLayout(self.jump_hlayout, 1, 1, 1, 2, alignment=Qt.AlignRight)

        '''------------------------------------------
        PANEL 3: ALIGNMENT
        ------------------------------------------'''
        #alignmentpanel

        self.scales_combobox = QComboBox(self)
        # self.scales_combobox.addItems([skip_list])
        # self.scales_combobox.addItems(['--'])
        self.scales_combobox.setFocusPolicy(Qt.NoFocus)
        self.scales_combobox.setFixedSize(std_button_size)
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

        self.affine_combobox = QComboBox(self)
        self.affine_combobox.addItems(['Init Affine', 'Refine Affine', 'Apply Affine'])
        self.affine_combobox.setFocusPolicy(Qt.NoFocus)
        self.affine_combobox.setFixedSize(std_button_size)

        # ^^ this should perhaps be connected to a function that updates affine in project file (immediately).. not sure yet
        # on second thought, the selected option here ONLY matters at alignment time
        # in the meantime, best temporary functionality is to just make sure that whatever item is selected when the
        #   alignment button is pressed will always be the affine used for alignment
        # saving affine data to project file might ultimately be needed, but this is good for now.

        # Whitening LineEdit
        self.whitening_label = QLabel("Whitening:")
        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.whitening_label.setToolTip(wrapped)
        self.whitening_input = QLineEdit(self)
        self.whitening_input.setAlignment(Qt.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(std_input_size)
        self.whitening_input.setFixedHeight(std_height)
        self.whitening_input.setValidator(QDoubleValidator(-5.0, 5.0, 2, self))

        # Swim Window LineEdit
        self.swim_label = QLabel("SWIM Window:")
        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.swim_label.setToolTip(wrapped)
        self.swim_input = QLineEdit(self)
        self.swim_input.setAlignment(Qt.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(std_input_size)
        self.swim_input.setFixedHeight(std_height)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))

        self.whitening_grid = QGridLayout()
        self.whitening_grid.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.addWidget(self.whitening_label, 0, 0, alignment=Qt.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignRight)

        self.swim_grid = QGridLayout()
        self.swim_grid.setContentsMargins(0, 0, 0, 0)
        self.swim_grid.addWidget(self.swim_label, 0, 0, alignment=Qt.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignRight)

        # Next Scale Button
        self.next_scale_button = QPushButton('Next Scale  ')
        self.next_scale_button.setToolTip('Go forward to the next scale.')
        self.next_scale_button.clicked.connect(self.next_scale_button_callback)
        # self.next_scale_button.setFixedSize(square_button_width, std_height)
        self.next_scale_button.setFixedSize(std_button_size)
        self.next_scale_button.setLayoutDirection(Qt.RightToLeft)

        pixmap = getattr(QStyle, 'SP_ArrowForward')
        icon = self.style().standardIcon(pixmap)
        self.next_scale_button.setIcon(icon)

        # Previous Scale Button
        self.prev_scale_button = QPushButton('  Prev Scale')
        self.prev_scale_button.setToolTip('Go back to the previous scale.')
        self.prev_scale_button.clicked.connect(self.prev_scale_button_callback)
        self.prev_scale_button.setFixedSize(std_button_size)
        # self.prev_scale_button.setFixedSize(square_button_width, std_height)
        self.prev_scale_button.setFixedSize(std_button_size)

        pixmap = getattr(QStyle, 'SP_ArrowBack')
        icon = self.style().standardIcon(pixmap)
        self.prev_scale_button.setIcon(icon)

        # self.scale_controls_layout = QHBoxLayout()
        # self.scale_controls_layout.addWidget(self.prev_scale_button, alignment=Qt.AlignLeft)
        # self.scale_controls_layout.addWidget(self.next_scale_button, alignment=Qt.AlignRight)

        # Align All Button
        self.align_all_button = QPushButton('Align')
        self.align_all_button.setToolTip('Align This Scale')
        self.align_all_button.clicked.connect(align_all_or_some)
        # self.align_all_button.setFixedSize(square_button_width, std_height)
        self.align_all_button.setFixedSize(std_button_size)

        # pixmap = getattr(QStyle, 'SP_MediaPlay')
        # icon = self.style().standardIcon(pixmap)
        # self.align_all_button.setIcon(icon)
        # self.align_all_button.setLayoutDirection(Qt.RightToLeft)

        # Auto-generate Toggle
        # Current implementation is not data-driven.
        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.auto_generate_label.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate = ToggleSwitch()  #toggleboundingrect
        self.toggle_auto_generate.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate.setChecked(True)
        self.toggle_auto_generate.setV_scale(.6)
        self.toggle_auto_generate.setH_scale(.8)
        self.toggle_auto_generate.toggled.connect(self.toggle_auto_generate_callback)
        self.toggle_auto_generate_hlayout = QHBoxLayout()
        self.toggle_auto_generate_hlayout.addWidget(self.auto_generate_label, alignment=Qt.AlignLeft)
        self.toggle_auto_generate_hlayout.addWidget(self.toggle_auto_generate, alignment=Qt.AlignRight)

        # self.scale_tabs = QTabWidget()
        self.alignment_layout = QGridLayout()
        self.alignment_layout.setContentsMargins(10, 25, 10, 5) #tag23
        self.alignment_layout.addLayout(self.swim_grid, 0, 0)
        self.alignment_layout.addLayout(self.whitening_grid, 1, 0)
        self.alignment_layout.addWidget(self.prev_scale_button, 0, 1)
        self.alignment_layout.addWidget(self.next_scale_button, 1, 1)
        self.alignment_layout.addWidget(self.align_all_button, 2, 1)
        self.alignment_layout.addLayout(self.toggle_auto_generate_hlayout, 2, 0)
        # (2,0,1,2)

        '''------------------------------------------
        PANEL 3.5: Post-alignment
        ------------------------------------------'''
        #postalignmentpanel

        # Null Bias combobox
        self.null_bias_label = QLabel("Bias:")
        tip = 'Polynomial bias (default=None). Note: This affects the alignment and the pixel dimensions of the generated images.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.null_bias_label.setToolTip(wrapped)
        self.null_bias_combobox = QComboBox(self)
        self.null_bias_combobox.setToolTip(wrapped)
        self.null_bias_combobox.setToolTip('Polynomial bias (default=None)')
        self.null_bias_combobox.addItems(['None', '0', '1', '2', '3', '4'])
        self.null_bias_combobox.setFocusPolicy(Qt.NoFocus)
        # self.null_bias_combobox.setFixedSize(std_button_size)
        self.null_bias_combobox.setFixedSize(72, std_height)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignLeft)
        self.poly_order_hlayout.addWidget(self.null_bias_combobox, alignment=Qt.AlignRight)

        # Bounding Box toggle
        self.bounding_label = QLabel("Bounding Box:")
        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that are the same size as the source images but may have missing data, while turning this ON will result in no missing data but may significantly increase the size of the generated images.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.bounding_label.setToolTip(wrapped)
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setToolTip(wrapped)
        # self.toggle_bounding_rect.setChecked(True)
        self.toggle_bounding_rect.setV_scale(.6)
        self.toggle_bounding_rect.setH_scale(.8)
        self.toggle_bounding_rect.toggled.connect(bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignLeft)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignRight)

        # Regenerate Button
        self.regenerate_button = QPushButton('Generate')
        self.regenerate_button.clicked.connect(regenerate_aligned)
        self.regenerate_button.setFixedSize(std_button_size)

        # pixmap = getattr(QStyle, 'SP_BrowserReload')
        # icon = self.style().standardIcon(pixmap)
        # self.regenerate_button.setIcon(icon)
        # # self.regenerate_button.setLayoutDirection(Qt.RightToLeft)

        self.postalignment_layout = QGridLayout()
        self.postalignment_layout.setContentsMargins(10, 25, 10, 5)  # tag23

        self.postalignment_layout.addLayout(self.poly_order_hlayout, 0, 0)
        self.postalignment_layout.addLayout(self.toggle_bounding_hlayout, 1, 0)
        self.postalignment_layout.addWidget(self.regenerate_button, 2, 0, alignment=Qt.AlignCenter)

        '''------------------------------------------
        PANEL 4: EXPORT & VIEW
        ------------------------------------------'''
        #exportpanel

        n_scales_label = QLabel("# of scales:")
        n_scales_label.setToolTip("Number of scale pyramid layers (default=4)")
        self.n_scales_input = QLineEdit(self)
        self.n_scales_input.setAlignment(Qt.AlignCenter)
        self.n_scales_input.setText("4")
        self.n_scales_input.setFixedWidth(std_input_size_small)
        self.n_scales_input.setFixedHeight(std_height)
        self.n_scales_valid = QIntValidator(1, 20, self)
        self.n_scales_input.setValidator(self.n_scales_valid)


        clevel_label = QLabel("clevel (1-9):")
        clevel_label.setToolTip("Zarr Compression Level (default=5)")
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setAlignment(Qt.AlignCenter)
        self.clevel_input.setText("5")
        self.clevel_input.setFixedWidth(std_input_size_small)
        self.clevel_input.setFixedHeight(std_height)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)

        cname_label = QLabel("cname:")
        cname_label.setToolTip("Zarr Compression Type (default=zstd) ")

        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setFixedSize(72, std_height)

        self.export_and_view_hbox = QHBoxLayout()
        self.export_zarr_button = QPushButton("Export To\nZarr")
        tip = "To view data in Neuroglancer, it is necessary to export to a compatible format such as Zarr. This function exports all aligned .TIF images for current scale to the chunked and compressed Zarr (.zarr) format with scale pyramid. Uses parallel processing."
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.export_zarr_button.setToolTip(wrapped)
        self.export_zarr_button.clicked.connect(self.export_zarr)
        self.export_zarr_button.setFixedSize(square_button_size)
        self.export_zarr_button.setStyleSheet("font-size: 11px;")

        self.ng_button = QPushButton("View In\nNeuroglancer")
        self.ng_button.setToolTip('View Zarr export in Neuroglancer.')
        self.ng_button.clicked.connect(ng_view)  # parenthesis were causing the member function to be evaluated early
        self.ng_button.setFixedSize(square_button_size)
        self.ng_button.setStyleSheet("font-size: 9px;")

        self.export_and_view_hlayout = QVBoxLayout()
        self.export_and_view_hlayout.addWidget(self.export_zarr_button, alignment=Qt.AlignCenter)
        self.export_and_view_hlayout.addWidget(self.ng_button, alignment=Qt.AlignCenter)

        self.n_scales_layout = QHBoxLayout()
        self.n_scales_layout.setContentsMargins(0, 0, 0, 0)
        self.n_scales_layout.addWidget(n_scales_label, alignment=Qt.AlignLeft)
        self.n_scales_layout.addWidget(self.n_scales_input, alignment=Qt.AlignRight)

        self.clevel_layout = QHBoxLayout()
        self.clevel_layout.setContentsMargins(0, 0, 0, 0)
        self.clevel_layout.addWidget(clevel_label, alignment=Qt.AlignLeft)
        self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignRight)

        self.cname_layout = QHBoxLayout()
        # self.cname_layout.setContentsMargins(0,0,0,0)
        self.cname_layout.addWidget(cname_label, alignment=Qt.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignRight)

        self.export_settings_grid_layout = QGridLayout()
        self.export_settings_grid_layout.addLayout(self.clevel_layout, 1, 0)
        self.export_settings_grid_layout.addLayout(self.cname_layout, 0, 0)
        self.export_settings_grid_layout.addLayout(self.n_scales_layout, 2, 0)
        self.export_settings_grid_layout.addLayout(self.export_and_view_hlayout, 0, 1, 3, 1)
        # self.export_settings_grid_layout.addWidget(self.export_zarr_button, 1, 1, alignment=Qt.AlignRight)
        # self.export_settings_grid_layout.addWidget(self.ng_button, 2, 1, alignment=Qt.AlignRight)
        self.export_settings_grid_layout.setContentsMargins(10, 25, 10, 5)  # tag23


        '''------------------------------------------
        INTEGRATED CONTROL PANEL
        ------------------------------------------'''
        #controlpanel
        cpanel_height = 145
        cpanel_1_width = 275
        cpanel_2_width = 275
        cpanel_3_width = 370
        cpanel_4_width = 155
        cpanel_5_width = 280

        # PROJECT CONTROLS
        self.project_functions_groupbox = QGroupBox("Project")
        self.project_functions_groupbox_ = QGroupBox("Project")
        self.project_functions_groupbox.setLayout(self.project_functions_layout)
        self.project_functions_stack = QStackedWidget()
        self.project_functions_stack.setFixedSize(cpanel_1_width, cpanel_height)
        self.project_functions_stack.addWidget(self.project_functions_groupbox_)
        self.project_functions_stack.addWidget(self.project_functions_groupbox)
        self.project_functions_stack.setCurrentIndex(1)

        # SCALING & DATA SELECTION CONTROLS
        self.images_and_scaling_groupbox = QGroupBox("Data Selection && Scaling")
        self.images_and_scaling_groupbox_ = QGroupBox("Scaling && Data Selection")
        # self.images_and_scaling_groupbox.setAlignment(Qt.AlignLeft)
        self.images_and_scaling_groupbox.setLayout(self.images_and_scaling_layout)
        self.images_and_scaling_stack = QStackedWidget()
        self.images_and_scaling_stack.setFixedSize(cpanel_2_width, cpanel_height)
        self.images_and_scaling_stack.addWidget(self.images_and_scaling_groupbox_)
        self.images_and_scaling_stack.addWidget(self.images_and_scaling_groupbox)
        self.images_and_scaling_stack.setCurrentIndex(0)

        # ALIGNMENT CONTROLS
        self.alignment_groupbox = QGroupBox("Alignment")
        self.alignment_groupbox_ = QGroupBox("Alignment")
        # self.alignment_groupbox.setAlignment(Qt.AlignLeft)
        self.alignment_groupbox.setLayout(self.alignment_layout)
        self.alignment_stack = QStackedWidget()
        self.alignment_stack.setFixedSize(cpanel_3_width, cpanel_height)
        self.alignment_stack.addWidget(self.alignment_groupbox_)
        self.alignment_stack.addWidget(self.alignment_groupbox)
        self.alignment_stack.setCurrentIndex(0)

        # POST-ALIGNMENT CONTROLS
        self.postalignment_groupbox = QGroupBox("Adjust Output")
        self.postalignment_groupbox_ = QGroupBox("Adjust Output")
        # self.postalignment_groupbox.setAlignment(Qt.AlignLeft)
        self.postalignment_groupbox.setLayout(self.postalignment_layout)
        self.postalignment_stack = QStackedWidget()
        self.postalignment_stack.setFixedSize(cpanel_4_width, cpanel_height)
        self.postalignment_stack.addWidget(self.postalignment_groupbox_)
        self.postalignment_stack.addWidget(self.postalignment_groupbox)
        self.postalignment_stack.setCurrentIndex(0)

        # EXPORT & VIEW CONTROLS
        self.export_and_view_groupbox = QGroupBox("Export && View")
        self.export_and_view_groupbox_ = QGroupBox("Export && View")
        self.export_and_view_groupbox.setLayout(self.export_settings_grid_layout)
        self.export_and_view_stack = QStackedWidget()
        self.export_and_view_stack.setFixedSize(cpanel_5_width, cpanel_height)
        self.export_and_view_stack.addWidget(self.export_and_view_groupbox_)
        self.export_and_view_stack.addWidget(self.export_and_view_groupbox)
        self.export_and_view_stack.setCurrentIndex(0)

        # self.project_functions_stack.setStyleSheet(open(self.main_stylesheet).read()) #might need to apply then remove border to prevent size differences caused by border
        self.images_and_scaling_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")
        self.alignment_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")
        self.postalignment_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")
        self.export_and_view_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")

        self.lower_panel_groups_ = QGridLayout()
        self.lower_panel_groups_.addWidget(self.project_functions_stack, 0, 0, alignment=Qt.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.images_and_scaling_stack, 0, 1, alignment=Qt.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.alignment_stack, 0, 2, alignment=Qt.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.postalignment_stack, 0, 3, alignment=Qt.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.export_and_view_stack, 0, 4, alignment=Qt.AlignHCenter)
        self.lower_panel_groups = QWidget()
        self.lower_panel_groups.setLayout(self.lower_panel_groups_)
        self.lower_panel_groups.setFixedHeight(cpanel_height + 10)

        # self.main_panel_layout.addLayout(self.lower_panel_groups) #**
        # self.main_panel_layout.setAlignment(Qt.AlignHCenter)

        '''------------------------------------------
        MAIN LAYOUT
        ------------------------------------------'''

        self.image_panel = MultiImagePanel()
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.draw_full_paths = self.draw_full_paths
        self.image_panel.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.image_panel.setMinimumHeight(400)

        #logger
        QThread.currentThread().setObjectName('Log')
        logging.getLogger().setLevel(logging.DEBUG)
        self.hud = HeadsUpDisplay(app)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.image_panel)
        self.splitter.addWidget(self.lower_panel_groups)
        self.splitter.addWidget(self.hud)
        # https://stackoverflow.com/questions/14397653/qsplitter-with-one-fixed-size-widget-and-one-variable-size-widget
        self.splitter.setStretchFactor(0,1)
        self.splitter.setStretchFactor(1,0)
        self.splitter.setStretchFactor(2,1)
        self.splitter.setCollapsible(0,False)
        self.splitter.setCollapsible(1,False)
        self.splitter.setCollapsible(2,True)

        self.main_panel = QWidget()
        # self.main_panel_layout = QVBoxLayout()
        self.main_panel_layout = QGridLayout()
        self.main_panel_layout.setSpacing(10) # this will inherit downward

        self.main_panel_layout.addWidget(self.splitter,1,0)
        self.main_panel.setLayout(self.main_panel_layout)


        '''------------------------------------------
        AUXILIARY PANELS
        ------------------------------------------'''

        # DOCUMENTATION PANEL
        self.browser = QWebEngineView()
        self.browser_docs = QWebEngineView()
        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(std_button_size)
        self.exit_docs_button.clicked.connect(exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(std_button_size)
        self.readme_button.clicked.connect(documentation_view_home)
        self.docs_panel = QWidget()
        self.docs_panel_layout = QVBoxLayout()
        self.docs_panel_layout.addWidget(self.browser_docs)
        self.docs_panel_controls_layout = QHBoxLayout()
        self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignLeft)
        self.docs_panel_controls_layout.addWidget(self.readme_button, alignment=Qt.AlignLeft)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.docs_panel_controls_layout.addSpacerItem(self.spacer_item_docs)
        self.docs_panel_layout.addLayout(self.docs_panel_controls_layout)
        self.docs_panel.setLayout(self.docs_panel_layout)

        # REMOTE VIEWER PANEL
        self.browser_remote = QWebEngineView()
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))  # tacctacc
        # self.browser_remote.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.exit_remote_button = QPushButton("Back")
        self.exit_remote_button.setFixedSize(std_button_size)
        self.exit_remote_button.clicked.connect(exit_remote)
        self.reload_remote_button = QPushButton("Reload")
        self.reload_remote_button.setFixedSize(std_button_size)
        self.reload_remote_button.clicked.connect(reload_remote)
        self.remote_viewer_panel = QWidget()
        self.remote_viewer_panel_layout = QVBoxLayout()
        self.remote_viewer_panel_layout.addWidget(self.browser_remote)
        self.remote_viewer_panel_controls_layout = QHBoxLayout()
        self.remote_viewer_panel_controls_layout.addWidget(self.exit_remote_button, alignment=Qt.AlignLeft)
        self.remote_viewer_panel_controls_layout.addWidget(self.reload_remote_button, alignment=Qt.AlignLeft)
        self.spacer_item_remote_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.remote_viewer_panel_controls_layout.addSpacerItem(self.spacer_item_remote_panel)
        self.remote_viewer_panel_layout.addLayout(self.remote_viewer_panel_controls_layout)
        self.remote_viewer_panel.setLayout(self.remote_viewer_panel_layout)

        # DEMOS PANEL
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

        # NEUROGLANCER CONTROLS PANEL
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
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignLeft)
        # self.ng_panel_controls_layout.addWidget(self.screenshot_ng_button, alignment=Qt.AlignLeft)
        # self.ng_panel_controls_layout.addWidget(self.blend_ng_button, alignment=Qt.AlignLeft)
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)  # add horizontal layout
        self.ng_panel.setLayout(self.ng_panel_layout)  # set layout

        # self.spacerItem = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) # not working

        # stack of windows views
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(self.main_panel)  # (0) main_panel
        self.stacked_widget.addWidget(self.ng_panel)  # (1) ng_panel
        self.stacked_widget.addWidget(self.docs_panel)  # (2) docs_panel
        self.stacked_widget.addWidget(self.demos_panel)  # (3) demos_panel
        self.stacked_widget.addWidget(self.remote_viewer_panel)  # (4) docs_panel
        self.stacked_widget.setCurrentIndex(0)

        # This can be invisible, will still use to organize QStackedWidget
        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem("Main")
        self.pageComboBox.addItem("Neuroglancer Local")
        self.pageComboBox.addItem("Documentation")
        self.pageComboBox.addItem("Demos")
        self.pageComboBox.addItem("Remote Viewer")
        self.pageComboBox.activated[int].connect(self.stacked_widget.setCurrentIndex)
        # self.pageComboBox.activated.connect(self.stackedLayout.s_etCurrentIndex)

        self.stacked_layout = QVBoxLayout()
        self.stacked_layout.addWidget(self.stacked_widget)
        self.setCentralWidget(self.stacked_widget)  # setCentralWidget to QStackedWidget

        #menu Menu Bar
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # fix to set non-native menubar in macOS

        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
            ['&File',
             [
                 ['&New Project', 'Ctrl+N', self.new_project, None, None, None],
                 ['&Open Project', 'Ctrl+O', self.open_project, None, None, None],
                 ['&Save Project', 'Ctrl+S', self.save_project, None, None, None],
                 ['Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None],
                 # ['-', None, None, None, None, None],
                 # ['Save &Cropped As...', None, self.save_cropped_as, None, None, None],
                 # ['-', None, None, None, None, None],
                 ['Show Project Inspector', None, self.show_project_inspector, None, None, None],
                 ['Update Project Inspector', None, self.update_project_inspector, None, None, None],
                 ['Exit', 'Ctrl+Q', self.exit_app, None, None, None]
             ]
             ],
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
                 ['Threaded Loading', None, self.toggle_threaded_loading, image_library.threaded_loading_enabled, None, None],
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
                 ['Custom Plot Code', None, self.not_yet, None, None, None],
                 [ '&Stylesheets',
                   [
                     ['Style #1 - Joel Style', None, self.apply_stylesheet_1, None, None, None],
                     # ['Style #2 - Light2', None, self.apply_stylesheet_2, None, None, None],
                     ['Style #3 - Light3', None, self.apply_stylesheet_3, None, None, None],
                     ['Style #4 - Grey', None, self.apply_stylesheet_4, None, None, None],
                     ['Style #11 - Screamin Green', None, self.apply_stylesheet_11, None, None, None],
                     ['Style #12 - Dark12', None, self.apply_stylesheet_12, None, None, None],
                     ['Minimal', None, self.minimal_stylesheet, None, None, None],
                   ]
                 ],
             ]
             ],
            ['&Debug',
             [
                 ['Debug Layer', None, debug_layer, None, None, None],
                 ['Debug Project', None, debug_project, None, None, None],
                 ['Print Structures', None, self.print_structures, None, None, None],
                 ['Print project_data', None, self.print_project_data, None, None, None],
                 ['Print Project Stats', None, self.print_project_data_stats, None, None, None],
                 ['Print Image Library', None, self.print_image_library, None, None, None],
                 ['update_win_self', None, self.update_win_self, None, None, None],
                 ['update_panels', None, self.update_panels, None, None, None],
                 ['refresh_all_images', None, self.refresh_all_images, None, None, None],
                 ['Is Destination Set', None, isDestinationSet, None, None, None],
                 ['Is Project Scaled', None, isProjectScaled, None, None, None],
                 ['Is Any Scale Aligned', None, isAnyScaleAligned, None, None, None],
                 ['Are Aligned Images Generated', None, areAlignedImagesGenerated, None, None, None],
                 ['Return Aligned Imgs', None, returnAlignedImgs, None, None, None],
                 ['Get # Aligned', None, getNumAligned, None, None, None],
                 ['Show Memory Usage', None, show_memory_usage, None, None, None],
                 ['Print Working Directory', None, printCurrentDirectory, None, None, None],
                 ['Read project_data Update GUI', None, self.read_project_data_update_gui, None, None, None],
                 ['Read GUI Update project_data', None, self.read_gui_update_project_data, None, None, None],
                 ['Apply Project Defaults', None, self.apply_project_defaults, None, None, None],

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
                 ['&Python Console', 'Ctrl+P', self.py_console, None, None, None],
                 ['-', None, None, None, None, None],
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
            self.status.showMessage('No project open.')
        else:
            # self.status.showMessage("File: "+fname)
            self.status.showMessage('File: unknown')


    def make_zarr_multithreaded(self, aligned_path, n_scales, cname, clevel, destination_path, ds_name):
        os.system("python3 make_zarr.py %s -c '64,64,64' -nS %s -cN %s -cL %s -d %s -n %s" % (aligned_path, str(n_scales), str(cname), str(clevel), destination_path, ds_name))

    def export_zarr(self):
            print('\nexport_zarr():')

            # if getNumAligned() < 1:
            if isAnyScaleAligned():
                print('  export_zarr() | there is an alignment stack at this scale - continuing.')
                self.status.showMessage('Exporting alignment project to Zarr...')
                pass
            else:
                print('  export_zarr() | (!) There is no alignment at this scale to export. Aborting export_zarr().')
                show_warning('No Alignment', 'There is no alignment to export.\n\n'
                                             'Typical workflow:\n'
                                             '(1) Open a project or import images and save.\n'
                                             '(2) Generate a set of scaled images and save.\n'
                                             '--> (3) Align each scale starting with the coarsest.\n'
                                             '(4) Export alignment to Zarr format.\n'
                                             '(5) View data in Neuroglancer client')

            self.set_status('Exporting scale %s to Neuroglancer-ready Zarr format...' % getCurScale()[-1])
            self.hud.post('Exporting scale %s to Neuroglancer-ready Zarr format...' % getCurScale()[-1])

            # allow any scale export...
            self.aligned_path = os.path.join(project_data['data']['destination_path'], getCurScale(), 'img_aligned')
            self.ds_name = 'aligned_' + getCurScale()
            print('  export_zarr() | aligned_path_cur_scale =', self.aligned_path)

            destination_path = os.path.abspath(project_data['data']['destination_path'])
            print('  export_zarr() | path of aligned images              :', self.aligned_path)
            print('  export_zarr() | path of Zarr export                 :', destination_path)
            print('  export_zarr() | dataset name                        :', self.ds_name)
            os.chdir(self.pyside_path)
            print('  export_zarr() | working directory                   :', os.getcwd())

            self.clevel = str(self.clevel_input.text())
            self.cname = str(self.cname_combobox.currentText())
            self.n_scales = str(self.n_scales_input.text())
            print("  export_zarr() | export options                      : clevel='%s'  cname='%s'  n_scales='%s'".format(
                self.clevel, self.cname, self.n_scales))

            # if self.cname == "none":
            #     os.system(
            #         "python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(
            #             self.n_scales) + " -nC 1 -d " + destination_path)
            # else:
            #     # os.system("./make_zarr.py volume_josef_small --chunks '1,5332,5332' --no_compression True")
            #     os.system(
            #         "python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(self.n_scales) + " -cN " + str(
            #             self.cname) + " -cL " + str(self.clevel) + " -d " + destination_path)

            #zarr
            # https://stackoverflow.com/questions/6783194/background-thread-with-qthread-in-pyqt
            # https://stackoverflow.com/questions/47560399/run-function-in-the-background-and-update-ui
            # https://stackoverflow.com/questions/58327821/how-to-pass-parameters-to-pyqt-qthreadpool-running-function
            self.dest_path = destination_path
            if self.cname == "none":
                # os.system("python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(n_scales) + " -nC 1 -d " + destination_path + " -n " + ds_name)
                os.system("python3 make_zarr.py %s -c '64,64,64' -nS %s -nC 1 -d %s -n %s" % (self.aligned_path, self.n_scales, self.dest_path, self.ds_name))
                self.status.showMessage("Zarr export complete.")
                self.set_status('Export of scale %s to Neuroglancer-ready Zarr format complete!' % str(getCurScale()))
            else:
                # print('\n\n---------ATTEMPTING BACKGROUND ZARR-----------\n\n')
                # worker = Worker(self.make_zarr_multithreaded, self.aligned_path, self.n_scales, self.cname, self.clevel, self.dest_path, self.ds_name) # Any other args, kwargs are passed to the run function
                # self.threadpool.start(worker)

                # worker.signals.result.connect(self.print_output)
                # worker.signals.finished.connect(self.thread_complete)
                # worker.signals.progress.connect(self.progress_fn)

                #make_zarr_multithreaded(aligned_path, n_scales, cname, clevel, destination_path, ds_name) # THIS WORKS

                os.system("python3 make_zarr.py %s -c '64,64,64' -nS %s -cN %s -cL %s -d %s -n %s" % (self.aligned_path, str(self.n_scales), str(self.cname), str(self.clevel), destination_path, self.ds_name))
                #os.system("python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(n_scales) + " -cN " + str(cname) + " -cL " + str(clevel) + " -d " + destination_path + " -n " + ds_name)
                self.status.showMessage("Zarr export complete.")
                self.set_status('Export of scale %s to Neuroglancer-ready Zarr format complete!' % str(getCurScale()))


            # self.ng_button.setStyleSheet("border :2px solid ;"
            #                  "border-top-color : #ffe135; "
            #                  "border-left-color :#ffe135;"
            #                  "border-right-color :#ffe135;"
            #                  "border-bottom-color : #ffe135;")


    def update_win_self(self):
        print("update_win_self (called by %s):" % inspect.stack()[1].function)
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

    #0530
    @Slot()
    def update_interface_current_scale(self) -> None:
        '''Update the visibility of next/prev scale buttons depending on current scale'''

        try:
            n_scales = getNumScales()
            cur_index = self.scales_combobox.currentIndex()
            print('update_interface_current_scale | n_scales=%d, cur_index=%d' % (n_scales, cur_index))
            if cur_index == 0:
                self.next_scale_button.hide()
                self.prev_scale_button.show()
            elif n_scales == cur_index + 1:
                self.prev_scale_button.hide()
                self.next_scale_button.show()
            else:
                self.next_scale_button.show()
                self.prev_scale_button.show()
        except:
            print('update_interface_current_scale | Something went wrong updating button visibility')

        try:
            alignment_method = project_data['data']['scales'][getCurScale()]['method_data']['alignment_option']
            dm_name_to_combo_name = {'init_affine': 'Initialize Affine', 'refine_affine': 'Refine Affine', 'apply_affine': 'Apply Affine'}
            alignment_method_pretty = dm_name_to_combo_name[alignment_method]
            cur_scale = getCurScale()
            img_size = get_image_size(project_data['data']['scales'][getCurScale()]['alignment_stack'][0]['images']['base']['filename'])
            self.alignment_groupbox.setTitle("Align Scale %s of %d | %sx%spx | %s " % (n_scales - cur_index, n_scales,  img_size[0], img_size[1], alignment_method_pretty))
        except:
            print('update_interface_current_scale | Something went wrong updating alignment groupbox title')
            print_exception()

        return None

    @Slot()
    def get_auto_generate_state(self) -> bool:
        '''NOTE: NOT data-driven. Simple get function to get boolean state of auto-generate toggle.'''

        if self.toggle_auto_generate.isChecked():
            return True
        else:
            return False

    @Slot()
    def toggle_auto_generate_callback(self):
        if self.toggle_auto_generate.isChecked():
            self.hud.post('Images will be generated automatically after alignment')
        else:
            self.hud.post('Images will not be generated automatically after alignment')
        pass

    @Slot()
    def next_scale_button_callback(self) -> None:
        '''Callback function for the Next Scale button (scales combobox may not be visible but controls the current scale).'''

        try:
            cur_index = self.scales_combobox.currentIndex()
            print('next_scale_button_callback | current index:',cur_index)
            new_index = cur_index - 1
            new_text = self.scales_combobox.itemText(new_index)
            print('next_scale_button_callbac | Requested scale:',new_text)
            self.scales_combobox.setCurrentIndex(new_index)
        except:
            print('next_scale_button_callback | EXCEPTION | Requested scale not available - Returning')
            return None

        self.read_gui_update_project_data()
        self.read_project_data_update_gui()
        self.update_interface_current_scale()
        self.update_project_inspector()
        return None

    @Slot()
    def prev_scale_button_callback(self) -> None:
        '''Callback function for the Previous Scale button (scales combobox may not be visible but controls the current scale).'''

        try:
            cur_index = self.scales_combobox.currentIndex()
            print('next_scale_button_callback | current index:',cur_index)
            new_index = cur_index + 1
            new_text = self.scales_combobox.itemText(new_index)
            print('next_scale_button_callbac | Requested scale:',new_text)
            self.scales_combobox.setCurrentIndex(new_index)
        except:
            print('prev_scale_button_callback | EXCEPTION | Requested scale not available - Returning')
            return None
        self.read_gui_update_project_data()
        self.read_project_data_update_gui()
        self.update_interface_current_scale()
        self.update_project_inspector()
        return None

    @Slot()
    def show_project_inspector(self):
        self.update_project_inspector()
        self.project_inspector.show()

    @Slot()
    def update_project_inspector(self):
        self.inspector_label_scales.setText(str(getSkipsList()))





    @Slot() #0404
    def set_status(self, message: str):
        self.status.showMessage(message)

    def print_project_data(self):
        # print(project_data)
        print(json.dumps(project_data, indent=2))

    def print_project_data_stats(self):
        # print(project_data)
        print(json.dumps(project_data, indent=2))

    @Slot()  # 0503 #skiptoggle #toggleskip #skipswitch forgot to define this
    def update_skip_toggle(self):
        print('update_skip_toggle:')
        scale = project_data['data']['scales'][project_data['data']['current_scale']]
        print("scale['alignment_stack'][project_data['data']['current_layer']]['skip'] = ",
              scale['alignment_stack'][project_data['data']['current_layer']]['skip'])
        self.toggle_skip.setChecked(not scale['alignment_stack'][project_data['data']['current_layer']]['skip'])

    #stylesheet
    def minimal_stylesheet(self):
        self.setStyleSheet('')
        print('Changing stylesheet to minimal')

    def apply_stylesheet_1(self):
        self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet1.qss')
        print('Changing stylesheet to', self.main_stylesheet)
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    # def apply_stylesheet_2(self):
    #     self.setStyleSheet('')
    #     self.setStyleSheet(open(os.path.join(self.pyside_path, 'styles/stylesheet2.qss')).read())

    def apply_stylesheet_3(self):
        '''Light stylesheet'''
        self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet3.qss')
        print('Changing stylesheet to', self.main_stylesheet)
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def apply_stylesheet_4(self):
        '''Grey stylesheet'''
        self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet4.qss')
        print('Changing stylesheet to', self.main_stylesheet)
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    # def apply_stylesheet_8(self):
    #     self.setStyleSheet('')
    #     self.setStyleSheet(open(os.path.join(self.pyside_path, 'styles/stylesheet8.qss')).read())

    def apply_stylesheet_11(self):
        '''Screamin' Green stylesheet'''
        self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet11.qss')
        print('Changing stylesheet to',self.main_stylesheet)
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def apply_stylesheet_12(self):
        self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet12.qss')
        print('Changing stylesheet to', self.main_stylesheet)
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def reset_groupbox_styles(self):
        print('reset_groupbox_styles | Resetting groupbox styles')
        self.project_functions_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.images_and_scaling_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.alignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.export_and_view_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.set_user_progress()

    def toggle_on_images_and_scaling_groupbox(self):
        self.images_and_scaling_stack.setCurrentIndex(1)
        self.images_and_scaling_stack.setStyleSheet(open(self.main_stylesheet).read())

        """QGroupBox {border: 2px dotted #455364;}"""
    def toggle_off_images_and_scaling_groupbox(self):
        self.images_and_scaling_stack.setCurrentIndex(0)
        self.images_and_scaling_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")


    def toggle_on_alignment_groupbox(self):
        self.alignment_stack.setCurrentIndex(1)
        self.alignment_stack.setStyleSheet(open(self.main_stylesheet).read())

    def toggle_off_alignment_groupbox(self):
        self.alignment_stack.setCurrentIndex(0)
        self.alignment_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")


    def toggle_on_postalignment_groupbox(self):
        self.postalignment_stack.setCurrentIndex(1)
        self.postalignment_stack.setStyleSheet(open(self.main_stylesheet).read())

    def toggle_off_postalignment_groupbox(self):
        self.postalignment_stack.setCurrentIndex(0)
        self.postalignment_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")


    def toggle_on_export_and_view_groupbox(self):
        self.export_and_view_stack.setCurrentIndex(1)
        self.export_and_view_stack.setStyleSheet(open(self.main_stylesheet).read())

    def toggle_off_export_and_view_groupbox(self):
        self.export_and_view_stack.setCurrentIndex(0)
        self.export_and_view_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")

    @Slot()
    def set_progress_stage_0(self):
        self.hud.post('Setting user progress to Project')
        print('Updating user progress to stage 0')
        self.toggle_off_images_and_scaling_groupbox()
        self.toggle_off_alignment_groupbox()
        self.toggle_off_postalignment_groupbox()
        self.toggle_off_export_and_view_groupbox()
        self.scales_combobox_switch = 0

    @Slot()
    def set_progress_stage_1(self):
        self.hud.post('Setting user progress to Data Selection & Scaling')
        print('Updating user progress to stage 1')
        self.toggle_on_images_and_scaling_groupbox()
        self.toggle_off_alignment_groupbox()
        self.toggle_off_postalignment_groupbox()
        self.toggle_off_export_and_view_groupbox()
        self.scales_combobox_switch = 0

    @Slot()
    def set_progress_stage_2(self):
        self.hud.post('Setting user progress to Alignment')
        print('Updating user progress to stage 2')
        self.toggle_on_images_and_scaling_groupbox()
        self.toggle_on_alignment_groupbox()
        self.toggle_on_postalignment_groupbox()
        self.toggle_off_export_and_view_groupbox()
        self.scales_combobox_switch = 1

    @Slot()
    def set_progress_stage_3(self):
        self.hud.post('Setting user progress to Export & View')
        print('Updating user progress to stage 3')
        self.toggle_on_images_and_scaling_groupbox()
        self.toggle_on_alignment_groupbox()
        self.toggle_on_postalignment_groupbox()
        self.toggle_on_export_and_view_groupbox()
        self.scales_combobox_switch = 1

    @Slot()
    def set_user_progress(self):
        '''Set user progress (0 to 3)'''
        if isAnyScaleAligned():
            self.set_progress_stage_3()
            self.update_interface_current_scale()
        elif isProjectScaled():
            self.set_progress_stage_2()
            self.update_interface_current_scale()
        elif isDestinationSet():
            self.set_progress_stage_1()
        else:
            self.set_progress_stage_0()
        self.update_project_inspector()

    @Slot()
    def get_user_progress(self) -> int:
        '''Get user progress (0 to 3)'''
        if isAnyScaleAligned():
            return int(3)
        elif isProjectScaled():
            return int(2)
        elif isDestinationSet():
            return int(1)
        else:
            return int(0)

    @Slot()
    def read_gui_update_project_data(self) -> None:
        '''
        Reads UI data from MainWindow and writes everything to 'project_data'.
        '''
        if self.get_null_bias_value() == 'None':
            project_data['data']['scales'][getCurScale()]['null_cafm_trends'] = False
        else:
            project_data['data']['scales'][getCurScale()]['null_cafm_trends'] = True
            project_data['data']['scales'][getCurScale()]['poly_order'] = int(self.get_null_bias_value())

        project_data['data']['scales'][getCurScale()]['use_bounding_rect'] = self.get_bounding_state()

        scale = project_data['data']['scales'][project_data['data']['current_scale']]
        scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method']['method_data']['whitening_factor'] = self.get_whitening_input()
        scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method']['method_data']['win_scale_factor'] = self.get_swim_input()

        self.update_project_inspector()
        return

    @Slot()
    def read_project_data_update_gui(self) -> None:
        '''
        Reads 'project_data' values and writes everything to MainWindow.
        '''
        scale = project_data['data']['scales'][project_data['data']['current_scale']] # we only want the current scale

        try:
            self.toggle_skip.setChecked(not scale['alignment_stack'][project_data['data']['current_layer']]['skip'])
        except BaseException as error:
            print('read_project_data_update_gui | WARNING | toggle_skip UI element failed to update its state')
            print('read_project_data_update_gui | This was the exception: {}'.format(error))

        combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine','Apply Affine': 'apply_affine'}
        dm_name_to_combo_name = {'init_affine': 'Init Affine', 'refine_affine': 'Refine Affine','apply_affine': 'Apply Affine'}

        try:
            cur_alignment_option = scale['method_data']['alignment_option']
            cur_alignement_option_pretty = dm_name_to_combo_name[cur_alignment_option]
            self.affine_combobox.setCurrentText(str(cur_alignement_option_pretty))
        except:
            print('read_project_data_update_gui | WARNING | Affine Combobox UI element failed to update its state')

        try:
            cur_whitening_factor = scale['alignment_stack'][project_data['data']['current_layer']]['align_to_ref_method']['method_data']['whitening_factor']
            self.whitening_input.setText(str(cur_whitening_factor))
        except:
            print('read_project_data_update_gui | WARNING | Whitening Input UI element failed to update its state')

        try:
            layer = scale['alignment_stack'][project_data['data']['current_layer']] # we only want the current layer
        except:
            print("read_project_data_update_gui | WARNING | unable to define variable 'layer'")

        try:
            cur_swim_window = layer['align_to_ref_method']['method_data']['win_scale_factor']
            self.swim_input.setText(str(cur_swim_window))
        except:
            print('read_project_data_update_gui | WARNING | Swim Input UI element failed to update its state')

        try:
            use_bounding_rect = project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect']
            self.toggle_bounding_rect.setChecked(bool(use_bounding_rect))
        except:
            print('read_project_data_update_gui | WARNING | Bounding Rect UI element failed to update its state')

        # main_window.refresh_all_images() #0528 is something like this needed?
        print('read_project_data_update_gui | GUI is in sync with project_data for current scale + layer.')

        self.update_project_inspector()

    #0519
    @Slot()
    def get_whitening_input(self) -> float:
        return float(self.whitening_input.text())

    @Slot()
    def get_swim_input(self) -> float:
        return float(self.swim_input.text())

    @Slot()
    def get_bounding_state(self):
        '''TODO: WHY WAS THIS RETURNING FLOAT NOT BOOL'''
        return self.toggle_bounding_rect.isChecked()

    #0523
    @Slot()
    def get_null_bias_value(self) -> str:
        return str(self.null_bias_combobox.currentText())

    @Slot()
    def get_affine_combobox(self):
        combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine','Apply Affine': 'apply_affine'}
        return combo_name_to_dm_name[self.affine_combobox.currentText()]

    @Slot()
    def jump_to_layer(self) -> None:
        print('jump_to_layer:')
        if self.jump_input.text() == '':
            pass
        else:
            requested_layer = int(self.jump_input.text())
            print("Jumping to layer " + str(requested_layer))
            num_layers = len(project_data['data']['scales'][getCurScale()]['alignment_stack'])
            if requested_layer >= num_layers:  # Limit to largest
                requested_layer = num_layers - 1

            project_data['data']['current_layer'] = requested_layer
            self.image_panel.update_multi_self()

    @Slot()
    def reload_scales_combobox(self):
        print("reload_scales_combobox:")
        prev_state = self.scales_combobox_switch
        self.scales_combobox_switch = 0
        # if len(project_data['data']['scales']) > 0:

        curr_scale = project_data['data']['current_scale']
        image_scales_to_run = [get_scale_val(s) for s in sorted(project_data['data']['scales'].keys())]
        self.scales_combobox.clear()

        for scale in sorted(image_scales_to_run):
            self.scales_combobox.addItems(["scale_" + str(scale)])

        index = self.scales_combobox.findText(curr_scale, Qt.MatchFixedString)
        if index >= 0:
            self.scales_combobox.setCurrentIndex(index)

        self.scales_combobox_switch = prev_state


    @Slot()  #scales
    def fn_scales_combobox(self) -> None:

        # print('fn_scales_combobox | Switch is live')
        if self.scales_combobox_switch == 0:
            print('fn_scales_combobox | Change scales switch is disabled - Returning')
            return None

        print("fn_scales_combobox | Change scales switch is Enabled, changing to %s"%self.scales_combobox.currentText())
        new_curr_scale = self.scales_combobox.currentText()  #  <class 'str'>
        project_data['data']['current_scale'] = new_curr_scale
        img_size = get_image_size(project_data['data']['scales'][new_curr_scale]['alignment_stack'][0]['images']['base']['filename'])
        self.hud.post('Setting current image scale to %s (%sx%spx)' % (new_curr_scale[-1], img_size[0], img_size[1]))
        
        self.read_project_data_update_gui()
        # self.update_panels()  # 0523 #0528
        main_window.center_all_images() #0528
        return None


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
            print_debug ( 2, "  Scale key: " + str(k) +
                          ", NullBias: " + str(project_data['data']['scales'][k]['null_cafm_trends']) +
                          ", Bounding Rect: " + str(project_data['data']['scales'][k]['use_bounding_rect']) )
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

    '''
    new_project_template = \
        {
            "version": 0.31,
            "method": "None",
            "user_settings": {
                "max_image_file_size": 100000000,
                "use_c_version": True
            },
            "data": {
                "source_path": "",
                "destination_path": "",
                "current_layer": 0,
                "current_scale": "scale_1",
                "panel_roles": [
                    "ref",
                    "base",
                    "aligned"
                ],
                "scales": {
                    "scale_1": {
                        "method_data": {
                            "alignment_option": "init_affine"
                        },
                        "null_cafm_trends": False,
                        "use_bounding_rect": True,
                        "alignment_stack": []
                    }
                }
            }
        }
        '''

    @Slot()
    def apply_project_defaults(self):
        '''The function replaces ensure_proper_data_structure'''

        print('\napply_defaults_to_scales:')
        self.hud.post('Applying project defaults...')
        global project_data
        scales_combobox_switch_ = self.scales_combobox_switch
        self.scales_combobox_switch = 0
        scales_dict = project_data['data']['scales']
        coarsest_scale = list(scales_dict.keys())[-1]

        for scale_key in scales_dict.keys():
            scale = scales_dict[scale_key]
            scale['null_cafm_trends'] = False #refactor
            scale['poly_order'] = int(0) #refactor
            scale['use_bounding_rect'] = True #refactor

            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                if not 'align_to_ref_method' in layer:
                    layer['align_to_ref_method'] = {}
                atrm = layer['align_to_ref_method']
                if not 'method_data' in atrm:
                    atrm['method_data'] = {}
                mdata = atrm['method_data']
                if not 'win_scale_factor' in mdata:
                    mdata['win_scale_factor'] = float(.8125)
                if not 'whitening_factor' in mdata:
                    mdata['whitening_factor'] = float(-.68)
                if scale_key == coarsest_scale:
                    project_data['data']['scales'][scale_key]['method_data']['alignment_option'] = 'init_affine'
                else:
                    project_data['data']['scales'][scale_key]['method_data']['alignment_option'] = 'refine_affine'


        # self.save_project() #0601 - removing
        self.scales_combobox_switch = scales_combobox_switch_

        print("\nExiting apply_project_defaults\n")

    @Slot()
    def new_project(self):
        print('\nnew_project:')

        self.hud.post('Creating a new project...')
        if isDestinationSet():
            print('(!) Warning user about data loss if a new project is started now.')
            msg = QMessageBox(QMessageBox.Warning,
                              'Confirm New Project',
                              'Warning: If a new project is started now, any unsaved progress '
                              'may be unrecoverable, like George Clooney and Sandra Bullock '
                              'drifting through outer space.',
                              buttons=QMessageBox.Cancel | QMessageBox.Ok)
            msg.setIcon(QMessageBox.Question)
            button_cancel = msg.button(QMessageBox.Cancel)
            button_cancel.setText('Cancel')
            # button_cancel.setAlignment(Qt.AlignCenter) #todo
            button_ok = msg.button(QMessageBox.Ok)
            button_ok.setText('New Project')
            # button_ok.setAlignment(Qt.AlignCenter)

            # msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
            msg.setDefaultButton(QMessageBox.Cancel)
            reply = msg.exec_()

            if reply == QMessageBox.Ok:
                print("new_project | reponse was 'Ok' - Continuing")
                pass
            else:
                print('new_project | user did not click Ok - Aborting')
                return

        print('new_project | Using project_data as global (mutable)')
        global project_data

        print('new_project | Setting user progress to stage 0 (why?)')
        self.scales_combobox_switch = 0
        self.set_progress_stage_0()

        # make_new = request_confirmation("Are you sure?",
        #                                 "Are you sure you want to exit the project? " \
        #                                 "Unsaved progress will be unrecoverable like " \
        #                                 "George Clooney and Sandra Bullock drifting " \
        #                                 "through space.")
        # if (make_new):

        print("new_project | copying 'new-project_template' dict to project_data")
        project_data = copy.deepcopy(new_project_template) #<-- NOTE THIS HAPPENS IN MainWindow CONSTRUCTOR ALSO
        project_data['data']['destination_path'] = None # seems redundant
        print('new_project | setting self.current_project_file_name = None')
        self.current_project_file_name = None

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, filter = QFileDialog.getSaveFileName(parent=None,  # None was self
                                                        caption="New Project Save As...",
                                                        filter="Projects (*.json);;All Files (*)",
                                                        selectedFilter="",
                                                        options=options)
        print("new_project | saving as " + str(file_name))

        if file_name != None:
            print('new_project | conditional if file_name != None was entered')
            if len(file_name) > 0:

                self.current_project_file_name = file_name

                # Attempt to hide the file dialog before opening ...
                for p in self.panel_list:
                    p.update_zpa_self()
                # self.update_win_self()

                if self.draw_full_paths:
                    self.setWindowTitle("Project: " + self.current_project_file_name)
                else:
                    self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1])

                self.set_def_proj_dest()
                # self.apply_project_defaults()
                self.save_project_to_current_file()
                self.set_progress_stage_1()
                # self.scales_combobox.clear() #why?? #0528


    @Slot()
    def open_project(self):
        self.hud.post('Opening project...')
        print('\nopen_project:')

        self.scales_combobox_switch = 0

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, filter = QFileDialog.getOpenFileName(parent=None,  # None was self
                                                        caption="Open Project",
                                                        filter="Projects (*.json);;All Files (*)",
                                                        selectedFilter="",
                                                        options=options)
        print("open_project | Opening project", file_name)


        if file_name == '':
            print('open_project | No project was opened')
            self.hud.post('No project was selected', logging.WARNING)
            return

        # ignore_changes = True

        try:
            f = open(file_name, 'r')
            text = f.read()
            f.close()
        except:
            self.hud.post('No project opened.', logging.WARNING)
            print('open_project | EXCEPTION | Something went wrong opening the project file (read-only) - Aborting')
            return

        for count, line in enumerate(text):
            pass

        print('open_project | Using project_data as global (mutable)')
        global project_data

        # Read the JSON file from the text
        proj_copy = json.loads(text)

        # Upgrade the "Data Model"
        proj_copy = upgrade_data_model(proj_copy)

        if proj_copy == None:
            # There was an unknown error loading the data model
            print('open_project | There was an unknown error loading the project')
        elif type(proj_copy) == type('abc'):  # abc = abstract base class
            # There was a known error loading the data model
            print('open_project | EXCEPTION | There was a problem loading the project', proj_copy)
        else:
            # The data model loaded fine, so initialize the application with the data
            # At this point, self.current_project_file_name is None
            self.current_project_file_name = file_name
            self.status.showMessage("Loading Project File " + self.current_project_file_name)

            print('open_project | Modifying the copy to use absolute paths internally')
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

            print('open_project | Replacing the current version with the copy')
            # Replace the current version with the copy
            project_data = copy.deepcopy(proj_copy)

            if self.draw_full_paths:
                self.setWindowTitle('Project: ' + self.current_project_file_name)
            else:
                self.setWindowTitle('Project: ' + os.path.split(self.current_project_file_name)[-1])
            # ignore_changes = False


        self.read_project_data_update_gui()
        self.reload_scales_combobox() #0529 just checking if adding this fixes bug
        self.center_all_images() # #0406 redundancy, discard if possible
        self.set_user_progress()
        self.update_project_inspector()
        print('\nCurrent project: %s\n' % self.current_project_file_name)


    def save_project_to_current_file(self):
        print('save_project_to_current_file:')
        # self.hud.post('Saving project')
        # Save to current file and make known file paths relative to the project file name
        if self.current_project_file_name != None:
            if len(self.current_project_file_name) > 0:
                # Write out the project
                if not self.current_project_file_name.endswith('.json'):
                    self.current_project_file_name = self.current_project_file_name + ".json"
                print("save_project_to_current_file | Saving project_data to file " + str(self.current_project_file_name))
                self.hud.post('Saving project %s' % self.current_project_file_name)
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

                print('------- (!) WRITING TO PROJECT FILE -------')
                try:
                    print('save_project_to_current_file | Opening project file in write mode')
                    f = open(self.current_project_file_name, 'w')
                    print('save_project_to_current_file | Encoding the json')
                    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                    proj_json = jde.encode(proj_copy)
                    f.write(proj_json)
                    f.close()
                except:
                    print('save_project_to_current_file | EXCEPT | Something went wrong writing to the project file - Aborting')
                    return

                if self.draw_full_paths:
                    self.setWindowTitle("Project: " + self.current_project_file_name)
                else:
                    self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1])
                self.status.showMessage("Project File: " + self.current_project_file_name)

        print('save_project_to_current_file | Complete')

    @Slot()
    def save_project(self):
        if self.current_project_file_name is None:
            print("save_project | Project file is not named, presenting user with 'save as' dialog")
            # self.save_project_as()
            self.hud.post('Nothing to save - no project open.', logging.WARNING)
            return
        else:
            print('save_project | saving current project to its project file')
            try:
                self.save_project_to_current_file()
            except:
                print('\nsave_project | EXCEPTION | Something may have gone wrong with saving the project.\n')

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
                    print("save_project_as | WARNING | Project not saved.")
                    return

                try:
                    self.setWindowTitle("Project: " + self.current_project_file_name)
                except:
                    return

                self.set_def_proj_dest()



    @Slot()
    def save_cropped_as(self):
        print('MainWindow.save_cropped_as | saving cropped as...')

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
        print("MainWindow.actual_size:")
        print_debug(90, "Setting images to actual size")
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update_zpa_self()

    @Slot()
    def toggle_arrow_direction(self, checked):
        print('MainWindow.toggle_arrow_direction:')
        self.image_panel.arrow_direction = -self.image_panel.arrow_direction

    @Slot()
    def toggle_threaded_loading(self, checked):
        print('MainWindow.toggle_threaded_loading:')
        image_library.threaded_loading_enabled = checked

    @Slot()
    def toggle_annotations(self, checked):
        print('MainWindow.toggle_annotations:')
        self.draw_annotations = checked
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_annotations = self.draw_annotations
            p.update_zpa_self()

    @Slot()
    def toggle_full_paths(self, checked):
        print('MainWindow.toggle_full_paths:')
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
        print('add_image_to_role:')

        #### NOTE: TODO: This function is now much closer to empty_into_role and should be merged
        local_cur_scale = getCurScale()

        # print("add_image_to_role | Placing file " + str(image_file_name) + " in role " + str(role_name))
        if image_file_name != None:
            if len(image_file_name) > 0:
                used_for_this_role = [role_name in l['images'].keys() for l in
                                      project_data['data']['scales'][local_cur_scale]['alignment_stack']]
                # print("Layers using this role: " + str(used_for_this_role))
                layer_index_for_new_role = -1
                if False in used_for_this_role:
                    # This means that there is an unused slot for this role. Find the first:
                    layer_index_for_new_role = used_for_this_role.index(False)
                    print("add_image_to_role | Inserting file " + str(image_file_name) + " in role " + str(
                        role_name) + " into existing layer " + str(layer_index_for_new_role))
                else:
                    # This means that there are no unused slots for this role. Add a new layer
                    print("add_image_to_role | Making a new layer for file " + str(image_file_name) + " in role " + str(
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
        print('MainWindow.add_empty_to_role:')

        local_cur_scale = getCurScale()
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

        '''
        #0411 need to give user a choice of what to do with imported images. Add to current project, or start a new project.
        '''
        print('MainWindow.import_images:')
        self.hud.post('Importing images...')
        global preloading_range
        local_cur_scale = getCurScale()
        print('Importing images for role: %s' % str(role_to_import))

        if clear_role:
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            for layer in project_data['data']['scales'][local_cur_scale]['alignment_stack']:
                if role_to_import in layer['images'].keys():
                    layer['images'].pop(role_to_import)

        if file_name_list != None:
            if len(file_name_list) > 0:
                print_debug(40, "Selected Files: " + str(file_name_list))
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

        img_size = get_image_size(project_data['data']['scales'][getCurScale()]['alignment_stack'][0]['images']['base']['filename'])
        self.hud.post('Size of images: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')

        # center images after importing
        # if center_switch:
        self.center_all_images()

        # self.set_progress_stage_1() THIS IS NOT NEEDED. USER PROGRESS DOES NOT CHANGE AFTER IMPORT, USER STILL NEEDS TO SCALE.
        # self.apply_project_defaults() #0529 I I THINK THIS IS NECESSARY
        self.update_panels() # NECESSARY. PAINTS THE IMAGES IN VIEWER.
        self.update_project_inspector()
        # THIS SHOULD BE FINE SINCE ORIGINAL IMAGES ARE JUST LINKS. ENSURES PROJECT IS IN A KNOWN STATE.
        # self.save_project()


    def update_panels(self):
        '''NECESSARY. PAINTS THE IMAGES IN VIEWER.'''
        print("MainWindow.update_panels:")
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def import_images_dialog(self, import_role_name):

        print("Importing images dialog for role: " + str(import_role_name))

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
        # self.center_all_images() #0406

    @Slot()
    def set_def_proj_dest(self):
        print("MainWindow is setting default project destination (MainWindow.set_def_proj_dest was called by " +
              inspect.stack()[1].function + ")...")
        print("  Default project destination is set to: ", str(self.current_project_file_name))
        if self.current_project_file_name == None:
            self.status.showMessage("Unable to set a project destination without a project file.\nPlease save the project file first.")
        elif len(self.current_project_file_name) == 0:
            self.status.showMessage("Unable to set a project destination without a project file.\nPlease save the project file first.")
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

                proj_path = self.current_project_file_name
                dest_path = str(project_data['data']['destination_path'])
                self.status.showMessage("Project File: " + proj_path)
                

    #0527
    def load_images_in_role(self, role, file_names):
        print('MainWindow.load_images_in_role:')
        '''Not clear if this has any effect. Needs refactoring.'''
        # print("MainWindow is loading images in role (called by " + inspect.stack()[1].function + ")...")
        print('MainWindow.load_images_in_role(role=%s,file_names=%s):' % (str(role),file_names))
        self.import_images(role, file_names, clear_role=True)
        self.center_all_images()

    def define_roles(self, roles_list):
        print("MainWindow.define_roles:")

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


    @Slot()
    def import_into_role(self, checked):
        print("MainWindow.import_into_role:")

        import_role_name = str(self.sender().text())
        self.import_images_dialog(import_role_name)

    # center try center code from here
    def import_base_images(self):
        print("MainWindow.import_base_images:")

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name_list, filtr = QFileDialog.getOpenFileNames(None,  # None was self
                                                             "Select Images to Import",
                                                             # self.openFileNameLabel.text(),
                                                             "Select Images",
                                                             "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)",
                                                             "", options)

        # Attempt to hide the file dialog before opening ...
        for p in self.panel_list:
            p.update_zpa_self()

        self.import_images('base', file_name_list)

        link_all_stacks()
        self.center_all_images()
        self.update_win_self()


    @Slot()
    def empty_into_role(self, checked):
        print("MainWindow.empty_into_role:")
        print("#### NOTE: TODO: This function is now much closer to add_image_to_role and should be merged")
        local_cur_scale = getCurScale()

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
        print("MainWindow.remove_all_from_role:")
        role_to_remove = str(self.sender().text())
        print_debug(10, "Remove role: " + str(role_to_remove))
        self.remove_from_role(role_to_remove)

    def remove_from_role(self, role, starting_layer=0, prompt=True):
        print("MainWindow.remove_from_role:")
        print_debug(5, "Removing " + role + " from scale " + str(getCurScale()) + " forward from layer " + str(
            starting_layer) + "  (remove_from_role)")
        actually_remove = True
        if prompt:
            actually_remove = request_confirmation("Note", "Do you want to remove all " + role + " images?")
        if actually_remove:
            print_debug(5, "Removing " + role + " images ...")

            delete_list = []

            layer_index = 0
            for layer in project_data['data']['scales'][getCurScale()]['alignment_stack']:
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

            main_window.update_panels()  # 0503
            main_window.refresh_all()  # 0503

    #0527
    def set_scales_from_string(self, scale_string):
        '''This is not pretty. Needs to be refactored ASAP.
        Two callers: 'new_project', 'generate_scales_queue'
        '''

        print("set_scales_from_string | Setting scales, scale_string=%s" % str(scale_string))
        cur_scales = [str(v) for v in sorted([get_scale_val(s) for s in project_data['data']['scales'].keys()])]
        scale_string = scale_string.strip()
        if len(scale_string) > 0:
            input_scales = []
            try:
                input_scales = [str(v) for v in sorted([get_scale_val(s) for s in scale_string.strip().split(' ')])]
            except:
                print("set_scales_from_string | Bad input: (" + str(scale_string) + "), Scales not changed")
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
                    project_data['data']['scales'][scale_key] = {'alignment_stack': new_stack, 'method_data': {'alignment_option': 'init_affine'}}
        else:
            print("set_scales_from_string | No input: Scales not changed")


    @Slot()
    def remove_all_layers(self):
        print("MainWindow.remove_all_layers:")
        global project_data
        local_cur_scale = getCurScale()
        project_data['data']['current_layer'] = 0
        while len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) > 0:
            project_data['data']['scales'][local_cur_scale]['alignment_stack'].pop(0)
        self.update_win_self()

    @Slot()
    def remove_all_panels(self):
        print("MainWindow.remove_all_panels |  Removing all panels")
        print_debug(30, "Removing all panels")
        if 'image_panel' in dir(self):
            print_debug(30, "image_panel exists")
            self.image_panel.remove_all_panels()
        else:
            print_debug(30, "image_panel does not exit!!")
        self.define_roles([]) #0601
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
    def center_callback(self):
        self.hud.post('Centering images...')
        self.center_all_images()

    @Slot()
    def actual_size_callback(self):
        self.hud.post('Actual-sizing images...')
        self.all_images_actual_size()


    # MainWindow.center_all_images -> calls MultiImagePanel.center_all_images
    @Slot()
    def center_all_images(self, all_images_in_stack=True):
        '''NOTE: CALLS COULD BE REDUCED BY CENTERING ALL STACKS OF IMAGES NOT JUST CURRENT SCALE'''
        print("center_all_images | called by " + inspect.stack()[1].function)
        self.image_panel.center_all_images(all_images_in_stack=all_images_in_stack)

    @Slot()
    def refresh_all_images(self):
        # print("  MainWindow is refreshing all images (called by " + inspect.stack()[1].function + ")...")
        self.image_panel.refresh_all_images()

    @Slot()
    def all_images_actual_size(self):
        print("all_images_actual_size | Actual-sizing all images.")
        self.image_panel.all_images_actual_size()
    #inspect.stack()[1].function

    def closeEvent(self, event):
        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


    @Slot()
    def exit_app(self):
        print("MainWindow.exit_app:")
        self.hud.post('Exiting...')
        self.hud.force_quit()

        if areImagesImported():
            message = "<font size = 4 color = gray>Save before exiting?</font>"
            msg = QMessageBox(QMessageBox.Warning, "Save Changes", message, parent=self)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            msg.setIcon(QMessageBox.Question)
            reply = msg.exec_()
            # options = QFileDialog.Options()
            # # options |= QFileDialog.DontUseNativeDialog
            # reply = QMessageBox.question(self, 'Message', "Save before exiting?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                print('exit_app | reply=Save')
                self.save_project()
                print('\nProject saved. Exiting\n')
                sys.exit()
            if reply == QMessageBox.Discard:
                print('exit_app | reply=Discard\n\nExiting without saving\n')
                sys.exit()
            if reply == QMessageBox.Cancel:
                print('exit_app | reply=Cancel\n\nCanceling action - Returning control to app\n')
                return

        else:
            sys.exit()


    @Slot()
    def py_console(self):
        print("@Slot Entering python console, use Control-D or Control-Z when done | MainWindow.py_console...")
        print_debug(1, "\n\n\n")
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



#---------------EMBEDDED LOGGER----------------#

# I think this is a solid implementation of a thread-safe background GUI logger
# https://www.oulub.com/en-US/Python/howto.logging-cookbook-a-qt-gui-for-logging

# Signals need to be contained in a QObject or subclass in order to be correctly initialized.
class Signaller(QObject):
    signal = Signal(str, logging.LogRecord)

class QtHandler(logging.Handler):
    def __init__(self, slotfunc, *args, **kwargs):
        super(QtHandler, self).__init__(*args, **kwargs)
        self.signaller = Signaller()
        self.signaller.signal.connect(slotfunc)

    def emit(self, record):
        s = self.format(record)
        self.signaller.signal.emit(s, record)

def ctname():
    return QThread.currentThread().objectName()

class Worker(QObject):
    @Slot()
    def start(self):
        extra = {'qThreadName': ctname()}
        logger.debug('Started work', extra=extra)
        i = 1
        # Let the thread run until interrupted. This allows reasonably clean
        # thread termination.
        while not QThread.currentThread().isInterruptionRequested():
            delay = 0.5 + random.random() * 2
            time.sleep(delay)
            level = logging.INFO
            logger.log(level, 'Message after delay of %3.1f: %d', delay, i, extra=extra)
            i += 1

class HeadsUpDisplay(QWidget):

    COLORS = {
        logging.DEBUG: 'black',
        logging.INFO: 'blue',
        logging.WARNING: 'orange',
        logging.ERROR: 'red',
        logging.CRITICAL: 'purple',
    }

    def __init__(self, app):
        super(HeadsUpDisplay, self).__init__()
        self.app = app
        self.textedit = te = QPlainTextEdit(self)
        # Set whatever the default monospace font is for the platform
        f = QFont()
        f.setFamily('monospace')

        te.setFont(f)
        te.setReadOnly(True)
        te.setStyleSheet("""
            /*background-color: #d3dae3;*/
            background-color:  #f5ffff;
            /*border-style: solid;*/
            border-style: inset;
            border-color: #455364; /* off-blue-ish color used in qgroupbox border */
            border-width: 2px;
            border-radius: 2px;            
        """)

        PB = QPushButton

        self.handler = h = QtHandler(self.update_status)
        # Remember to use qThreadName rather than threadName in the format string.
        fs = '%(asctime)s %(qThreadName)-12s %(levelname)-8s %(message)s'
        formatter = logging.Formatter(fs)
        h.setFormatter(formatter)
        logger.addHandler(h)
        # Set up to terminate the QThread when we exit
        app.aboutToQuit.connect(self.force_quit)

        layout = QVBoxLayout(self)
        layout.addWidget(te)

        self.start_thread()


    def start_thread(self):
        self.worker = Worker()
        self.worker_thread = QThread()
        self.worker.setObjectName('Worker')
        self.worker_thread.setObjectName('WorkerThread')  # for qThreadName
        self.worker.moveToThread(self.worker_thread)
        # This will start an event loop in the worker thread
        self.worker_thread.start()
        self.post('Starting heads-up display...')

    def kill_thread(self):
        self.worker_thread.requestInterruption()
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        else:
            print('worker has already exited.')

    def force_quit(self):
        if self.worker_thread.isRunning():
            self.kill_thread()

    @Slot(str, logging.LogRecord)
    def update_status(self, status, record):
        color = self.COLORS.get(record.levelno, 'black')
        s = '<pre><font color="%s">%s</font></pre>' % (color, status)
        self.textedit.appendHtml(s)

    @Slot()
    def manual_update(self):
        level = logging.INFO
        extra = {'qThreadName': ctname()}
        logger.log(level, 'Manually logged!', extra=extra)

    @Slot()
    def post(self, message, level=logging.INFO):
        extra = {'qThreadName': ctname()}
        logger.log(level, message, extra=extra)

    @Slot()
    def clear_display(self):
        self.textedit.clear()



if __name__ == "__main__":
    print("Running " + __file__ + ".__main__()")

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

    main_win = MainWindow()
    main_win.resize(2200, 1200)
    main_win.define_roles(['Stack'])
    main_win.show()
    sys.exit(app.exec())



'''
------------------------
 Recipe 1 To-Do list
------------------------
cafm = cumulative affine matrix

To do:
[x] jump to functionality
[x] re-generate aligned
[] project class
[x] upgrade 'daisy' from v0.2 to v1.0
[x] widgets for controls become hidden or visible as user progresses through project
[x] make menu bar attached on macOS
[x] after selecting 'skip', it should not be necessary to re-focus on images widget
[] spawn new thread for making Zarr, to not lock up the GUI
[x] improve affine combo box for intuitive/automatic control flow
[x] automatically focus back on ZoomPanWidget after adjusting control panel
[] when skips are reset, remove red 'x' annotation immediately
[] display current affine more clearly
[x] enable multithreaded export to Zarr
[] run make_zarr.py in a separate thread
[] make_zarr.py 'Cancel' functionality
[] make_zarr.py UI configuration option for when Zarr exists at current scale. whether to (a) cancel (b) overwrite (c) ask
[] BUG: when Keep/Toggle switch is used pre-scaling, red X does not appear immediately
[] improved robustness in error recovery of task_queue
[] generate error report logs, save inside project (talk to James about saving log files to remote database/server)
[] ask to save before exiting
[x] set project destination instantly upon re-opening a project
[] dim out "#scales" and "clevel" when compression combobox option "none" is selected
[] cancel Zarr export
[x] check if aligned images exist before exporting to Zarr. Cancel and display warning otherwise.
[] if-and-only-if quitting without a recent save, have option to save first
[] call 'Apply Affine' something more descriptive, or make its function more clear ('Force Affine'?)
[] add a place to take notes (see: https://pythonbasics.org/pyqt-menubar/)
[x] should be able to export aligned to Zarr at any scale
[] project status indicator
[] there should ALWAYS be a scale 1, not just when scales are generated
[] underlined letters for hotkeys
[] forget/remove all images from project function
[] if scales exist, ask user if they are sure they want to RE-generate alignment (possibly overwriting something they worked hard on)
[] "would you like to create a new project with these images or add them to the current stack?"
[] SNR reported differently between ref, base, and aligned
[] add back make functionality for view mode (View or Crop)  view_match_crop = ComboBoxControl(['View', 'Match', 'Crop'])
[x] add functionality back for alignem.project_data['data']['scales'][prev_scale_key]['null_cafm_trends'] = False
[x] add functionality back for alignem.project_data['data']['scales'][prev_scale_key]['poly_order'] = int(0)
[x] add functionality back for alignem.project_data['data']['scales'][prev_scale_key]['use_bounding_rect'] = False
[x] upgrade PySide2 (Qt5) to PySide6 (Qt6)
[x] upgrade Daisy from v0.2 to v1.0
[x] spawn new thread for emdedded web browser
[x] embed neuroglancer viewer
[x] embed documentation
[x] remake control panel using more conventional and scalable Python/Qt strategies
[x] implement QStackedWidget to allow the application to have paging, replete with back buttons, etc.
[x] apply stylesheet
[x] replace 'skip' checkbox with toggle button
[x] automatically center images after (a) importing images (b) generating scales (c) generating alignments
[x] move align_all_or_some to its own script
[] fix scale combo box text i.e. scale_1 -> Scale 1
[] max bounding box size threshold
[] have a default project name for new projects, i.e. 'my_project.json'
[x] put a stop to the gray rectangle bug
[x] fix bug that requires a project to be saved
[] Tool Tips for all/most buttons/menus
[] auto-generate images button in primary alignment control panel
[] 'apply to all' button for whitening and SWIM window
[] toggle for auto-generate images
[x] function to check if source images have been imported
[x] function to check how many source images have been imported
[x] faster loading of large images
[x] Would you like to save before exiting?
[] Refactor 'set_scales_from_string' functionality (two callers: 'new_project', 'generate_scales_queue')
[] 'areImagesCentered' function
[] apply_project_defaults cannot be a member function of main_window. This is not data driven.
[] Save Automatically toggle switch
[] project has unsaved changes flag (similar to what Tom does)... for asking user whether to save before exit
[] Show which scales have been aligned (possibly with non-selectable radio boxes)
[] SWIM Window <- # of pixels in label
[] show SWIM window as overlay on base & ref
[] for new project, might be probelm with apply_project_defaults() func
[] bug where when project is saved on first base image in the stack (which has no ref) -> reopening the project and changing layer will require a re-center

Things project_data should include:
* is project scaled (bool)
* scales with alignments so-far generated (list of strings, i.e. ['scale_4', 'scale_2'])

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



''''''
------------------------
 Recipe 2 To-Do list
------------------------
[] match-point mode



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



Check if scales have been generated yet:
len(project_data['data']['scales']) = 2
if len(project_data['data']['scales']) > 0:


Print/return the number of aligned images in  <project destination>/<current scale>/img_aligned

dir = os.path.join(project_data['data']['destination_path'], getCurScale(), 'img_aligned')
print(len([name for name in os.listdir(dir) if os.path.isfile(os.path.join(dir, name))]))


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


POSSIBLE WORKFLOW FOR VIEWING SINGLE BLEND IN NEUROGLANCER VIEWER
1. Create blended image
2. If project.zarr/img_blended_zarr group does not exist, create it
3. Converted blended image to Zarr using tiffs2zarr utility function (from glanceem_utils.py).
4. Blended image array is appended to project.zarr/img_blended_zarr
5. Neuroglancer viewer top panel is updated to display Zarr group img_blended_zarr


weird, this randomly appeared:
js: crbug/1173575, non-JS module files deprecated.



At the end of alignment, we have affine and cumulative affine for each image

Matrix decomposition


options for threading:
https://stackoverflow.com/questions/6783194/background-thread-with-qthread-in-pyqt

Using a QRunnable
http://qt-project.org/doc/latest/qthreadpool.html
Note that a QRunnable isn't a subclass of QObject and therefore does
not provide signals and slots.

QWebSocketCorsAuthenticator¶
https://doc.qt.io/qtforpython/PySide6/QtWebSockets/QWebSocketCorsAuthenticator.html?highlight=cors

'''
