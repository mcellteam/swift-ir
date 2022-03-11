"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
from glanceem_utils import RequestHandler, Server, get_viewer_url, tiffs2zarr
from caveclient import CAVEclient


import sys, traceback
import os
import copy
import math
import cv2
import json
import numpy
import scipy
import scipy.ndimage
import psutil
import argparse
import pyswift_tui

import concurrent.futures
import threading

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, QStackedWidget, QStackedLayout, QGridLayout
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox, QSpacerItem
#from PySide6.QtWidgets import QOpenGLWidget
from PySide6.QtWidgets import QMenu, QColorDialog, QMessageBox, QComboBox, QRubberBand, QToolButton, QStyle, QDialog, QFrame, QStyleFactory
from PySide6.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat
from PySide6.QtGui import QAction, QActionGroup
#from PySide6.QtGui import QOpenGLContext, QOpenGLVersionProfile
from PySide6.QtCore import Slot, QRect, QRectF, QSize, Qt, QPoint, QPointF, QThreadPool, QUrl, QFile, QTextStream, QCoreApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
#import PySide6.QtOpenGL
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineSettings

import align_swiftir
import task_queue_mp as task_queue

# Get the path of ../python
#alignem_file = os.path.abspath(__file__)                     # path/PySide6/alignem.py
#alignem_p    = os.path.dirname( alignem_file )               # path/PySide6
#alignem_pp   = os.path.dirname( alignem_p )                  # path
#alignem_shared_path = os.path.join ( alignem_pp, 'python' )  # path/python

#if len(sys.path) <= 0:
#  # Add the path to the currently empty path (this would be an unusual case)
#  sys.path.append ( alignem_shared_path )
#else:
#  # Add the path in the second position (after the default current directory of "")
#  sys.path.insert ( 1, alignem_shared_path )

# Import project and alignment support from SWiFT-IR:

from alignem_data_model import new_project_template, new_layer_template, new_image_template, upgrade_data_model
project_data = None


def print_all_skips():
    scale_keys = project_data['data']['scales'].keys()
    for scale_key in sorted(scale_keys):
        print_debug ( 50, " Scale: " + scale_key )
        scale = project_data['data']['scales'][scale_key]
        layers = scale['alignment_stack']
        for layer in layers:
            print_debug ( 50, "  Layer: " + str(layers.index(layer)) + ", skip = " + str(layer['skip']) )
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


# This is monotonic (0 to 100) with the amount of output:
debug_level = 0  # A larger value prints more stuff

# Using the Python version does not work because the Python 3 code can't
# even be parsed by Python2. It could be dynamically compiled, or use the
# alternate syntax, but that's more work than it's worth for now.
if sys.version_info >= (3, 0):
    if debug_level > 10: print ( "Python 3: Supports arbitrary arguments via print")
    #def print_debug ( level, *ds ):
    #  global debug_level
    #  if level <= debug_level:
    #    print ( *ds )
else:
    if debug_level > 10: print ("Python 2: Use default parameters for limited support of arbitrary arguments via print")

# For now, always use the limited argument version
def print_debug ( level, p1=None, p2=None, p3=None, p4=None ):
    global debug_level
    if level <= debug_level:
      if p1 == None:
        print ( "" )
      elif p2 == None:
        print ( str(p1) )
      elif p3 == None:
        print ( str(p1) + str(p2) )
      elif p4 == None:
        print ( str(p1) + str(p2) + str(p3) )
      else:
        print ( str(p1) + str(p2) + str(p3) + str(p4) )


app = None
use_c_version = True
use_file_io = False
show_skipped_images = True

preloading_range = 3
max_image_file_size = 1000000000
crop_window_mode = 'mouse_rectangle' # mouse_rectangle or mouse_square or fixed
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
    global project_data
    return ( project_data['data']['current_scale'] )

main_window = None


def makedirs_exist_ok ( path_to_build, exist_ok=False ):
    # Needed for old python which doesn't have the exist_ok option!!!
    print_debug ( 30, " Make dirs for " + path_to_build )
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
      full = os.path.join(full,p)
      if not os.path.exists(full):
        os.makedirs ( full )
      elif not exist_ok:
        print_debug ( 1, "Warning: Attempt to create existing directory: " + full)


def show_warning ( title, text ):
    QMessageBox.warning ( None, title, text )

def request_confirmation ( title, text ):
    button = QMessageBox.question ( None, title, text )
    print_debug ( 50, "You clicked " + str(button) )
    print_debug ( 50, "Returning " + str(button == QMessageBox.StandardButton.Yes))
    return ( button == QMessageBox.StandardButton.Yes )

def get_scale_val ( scale_of_any_type ):
    # This should return an integer value from any reasonable input (string or int)
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            # It's already an integer, so return it
            return scale
        else: #elif type(scale) in [ str, unicode ]:
            # It's a string, so remove any optional "scale_" prefix(es) and return as int
            while scale.startswith('scale_'):
              scale = scale[len('scale_'):]
            return int(scale)
        #else:
        #    print_debug ( 10, "Error converting " + str(scale_of_any_type) + " of unexpected type (" + str(type(scale)) + ") to a value." )
        #    traceback.print_stack()
    except:
        print_debug ( 1, "Error converting " + str(scale_of_any_type) + " to a value." )
        exi = sys.exc_info()
        print_debug ( 1, "  Exception type = " + str(exi[0]) )
        print_debug ( 1, "  Exception value = " + str(exi[1]) )
        print_debug ( 1, "  Exception traceback:" )
        traceback.print_tb(exi[2])
        return -1

def get_scale_key ( scale_val ):
    # Create a key like "scale_#" from either an integer or a string
    s = str(scale_val)
    while s.startswith ( 'scale_' ):
        s = s[len('scale_'):]
    return 'scale_' + s


def old_load_image_worker ( real_norm_path, image_dict ):
    # Load the image
    print_debug ( 50, "  load_image_worker started with: \"" + str(real_norm_path) + "\"" )
    m = psutil.virtual_memory()
    print_debug ( 50, "    memory available before loading = " + str(m.available) )
    image_dict['image'] = QPixmap(real_norm_path)
    image_dict['loaded'] = True
    print_debug ( 50, "  load_image_worker finished for: \"" + str(real_norm_path) + "\"" )
    print_debug ( 50, "    memory available after loading = " + str(m.available) )


class OldImageLibrary:
    """A class containing multiple images keyed by their file name."""
    def __init__ ( self ):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey ( self, file_path ):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def __str__ (self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        for k,v in self._images.items():
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"

        print_debug(4, s)
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return ( "ImageLibrary contains ...")

    def get_image_reference ( self, file_path ):
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
                    print_debug ( 5, "  Load Warning for: \"" + str(real_norm_path) + "\"" )
                    image_ref = self._images[real_norm_path]['image']
            else:
                # The image is not in the library at all, so force a load now (and wait)
                print_debug ( 25, "  Forced load of image: \"" + str(real_norm_path) + "\"" )
                self._images[real_norm_path] = { 'image': QPixmap(real_norm_path), 'loaded': True, 'loading': False, 'task':None }
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    def get_image_reference_if_loaded ( self, file_path ):
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
                    print_debug ( 5, "  Load Warning for: \"" + str(real_norm_path) + "\"" )
                    image_ref = self._images[real_norm_path]['image']
        return image_ref


    def remove_image_reference ( self, file_path ):
        image_ref = None
        if not (file_path is None):
            real_norm_path = self.pathkey(file_path)
            if real_norm_path in self._images:
                print_debug ( 50, "Unloading image: \"" + real_norm_path + "\"" )
                image_ref = self._images.pop(real_norm_path)['image']
        # This returned value may not be valid when multi-threading is implemented
        return image_ref

    def queue_image_read ( self, file_path ):
        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = { 'image': None, 'loaded': False, 'loading': True, 'task':None }
        t = threading.Thread ( target = load_image_worker, args = (real_norm_path,self._images[real_norm_path]) )
        t.start()
        self._images[real_norm_path]['task'] = t

    def make_available ( self, requested ):
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        print_debug ( 25, "make_available: " + str(sorted([str(s[-7:]) for s in requested])) )
        already_loaded = set(self._images.keys())
        normalized_requested = set ( [self.pathkey(f) for f in requested] )
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference ( f )
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read ( f )   # Using this will enable threaded reading behavior
            else:
                self.get_image_reference ( f )   # Using this will force sequential reading behavior

        print_debug ( 25, "Library has " + str(len(self._images.keys())) + " images" )
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def remove_all_images ( self ):
        keys = list(self._images.keys())
        for k in keys:
          self.remove_image_reference ( k )
        self._images = {}
    def update ( self ):
        # Do nothing - needed to be plug replacable with SmartImageLibrary
        pass



# Load the image
def load_image_worker ( real_norm_path, image_dict ):
    print_debug(50, "load_image_worker started with:", str(real_norm_path))
    image_dict['image'] = QPixmap(real_norm_path)
    image_dict['loaded'] = True
    image_dict['loading'] = False
    print_debug(50, "load_image_worker finished for:" + str(real_norm_path))
    image_library.print_load_status()


class ImageLibrary:
    """A class containing multiple images keyed by their file name."""
    def __init__ ( self ):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey ( self, file_path ):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def print_load_status ( self ):
        print_debug ( 50, " Library has " + str(len(self._images.keys())) + " images" )
        print_debug ( 50, "  Names:   " + str(sorted([str(s[-7:]) for s in self._images.keys()])) )
        print_debug ( 50, "  Loaded:  " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loaded']])) )
        print_debug ( 50, "  Loading: " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loading']])) )

    def __str__ (self):
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
        return ( s )

    def get_image_reference ( self, file_path ):
        print_debug ( 50, "get_image_reference ( " + str(file_path) + " )" )
        self.print_load_status()
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                print_debug ( 50, "  Image name is in the library" )
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    print_debug ( 50, "  Image was already loaded" )
                    image_ref = self._images[real_norm_path]['image']
                elif self._images[real_norm_path]['loading']:
                    # The image is still loading, so wait for it to complete
                    print_debug ( 4, "  Image still loading ... wait" )
                    self._images[real_norm_path]['task'].join()
                    self._images[real_norm_path]['task'] = None
                    self._images[real_norm_path]['loaded'] = True
                    self._images[real_norm_path]['loading'] = False
                    image_ref = self._images[real_norm_path]['image']
                else:
                    print_debug ( 3, "  Load Warning for: \"" + str(real_norm_path) + "\"" )
                    image_ref = self._images[real_norm_path]['image']
            else:
                # The image is not in the library at all, so force a load now (and wait)
                print_debug ( 4, "  Forced load of image: \"" + str(real_norm_path) + "\"" )
                self._images[real_norm_path] = { 'image': QPixmap(real_norm_path), 'loaded': True, 'loading': False, 'task':None }
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    def get_image_reference_if_loaded ( self, file_path ):
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
                    print_debug ( 5, "  Load Warning for: \"" + str(real_norm_path) + "\"" )
                    image_ref = self._images[real_norm_path]['image']
        return image_ref

    def remove_image_reference ( self, file_path ):
        image_ref = None
        if not (file_path is None):
            real_norm_path = self.pathkey(file_path)
            if real_norm_path in self._images:
                print_debug ( 4, "Unloading image: \"" + real_norm_path + "\"" )
                image_ref = self._images.pop(real_norm_path)['image']
        # This returned value may not be valid when multi-threading is implemented
        return image_ref

    def queue_image_read ( self, file_path ):
        real_norm_path = self.pathkey(file_path)
        print_debug ( 30, "  start queue_image_read with: \"" + str(real_norm_path) + "\"" )
        self._images[real_norm_path] = { 'image': None, 'loaded': False, 'loading': True, 'task':None }
        t = threading.Thread ( target = load_image_worker, args = (real_norm_path,self._images[real_norm_path]) )
        t.start()
        self._images[real_norm_path]['task'] = t
        print_debug ( 30, "  finished queue_image_read with: \"" + str(real_norm_path) + "\"" )

    def make_available ( self, requested ):
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        print_debug ( 50, "make_available: " + str(sorted([str(s[-7:]) for s in requested])) )
        already_loaded = set(self._images.keys())
        normalized_requested = set ( [self.pathkey(f) for f in requested] )
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference ( f )
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read ( f )   # Using this will enable threaded reading behavior
            else:
                self.get_image_reference ( f )   # Using this will force sequential reading behavior

        self.print_load_status()
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def remove_all_images ( self ):
        keys = list(self._images.keys())
        for k in keys:
          self.remove_image_reference ( k )
        self._images = {}

    def update ( self ):
        pass



def image_completed_loading(par):
    print ( '\n' + 100*'$' + '\n' + 100*'$' )
    print ( "Got: " + str(par) )
    print ( "Image completed loading, check if showing and repaint as needed." )
    ## The following is needed to auto repaint, but it crashes instantly.
    ## main_window.image_panel.refresh_all_images()
    print ( '\n' + 100*'$' + '\n' + 100*'$' )

def image_loader ( real_norm_path, image_dict ):
    try:
        # Load the image
        print_debug ( 5, "  image_loader started with: \"" + str(real_norm_path) + "\"" )
        m = psutil.virtual_memory()
        print_debug ( 5, "    memory available before loading = " + str(m.available) )
        image_dict['image'] = QPixmap(real_norm_path)
        image_dict['loaded'] = True
        print_debug ( 5, "  image_loader finished for: \"" + str(real_norm_path) + "\"" )
        print_debug ( 5, "    memory available after loading = " + str(m.available) )
    except:
        print ( "Got an exception in image_loader")

class SmartImageLibrary:
    """A class containing multiple images keyed by their file name."""
    def __init__ ( self ):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True
        self.initial_memory = psutil.virtual_memory()
        self.prev_scale_val = None
        self.prev_layer_index = None
        self.executors = concurrent.futures.ThreadPoolExecutor(max_workers=None) # Should default to 5 times number of processors

    def pathkey ( self, file_path ):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def __str__ (self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        for k,v in self._images.items():
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"
        print ( s )
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return ( "ImageLibrary contains ...")

    def remove_image_reference ( self, file_path ):
        # Do nothing since the smart image library now makes this decision internally
        pass

    def remove_all_images ( self ):
        # Do nothing since the smart image library now makes this decision internally
        pass

    def get_image_reference ( self, file_path ):
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
                print_debug ( 5, "  Begin loading image: \"" + str(real_norm_path) + "\"" )
                self.queue_image_read(real_norm_path)
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    def get_image_reference_if_loaded ( self, file_path ):
        return self.get_image_reference ( file_path )

    def queue_image_read ( self, file_path ):
        print ( "top of queue_image_read ( " + file_path + ")" )
        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = { 'image': None, 'loaded': False, 'loading': True, 'task':None }
        print ( "submit with (" + real_norm_path + ", " + str(self._images[real_norm_path]) + ")" )
        task_future = self.executors.submit ( image_loader, real_norm_path, self._images[real_norm_path] )
        task_future.add_done_callback ( image_completed_loading )
        print ( "  task_future: " + str(task_future) )
        self._images[real_norm_path]['task'] = task_future

    def make_available ( self, requested ):
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        print_debug ( 25, "make_available: " + str(sorted([str(s[-7:]) for s in requested])) )
        already_loaded = set(self._images.keys())
        normalized_requested = set ( [self.pathkey(f) for f in requested] )
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference ( f )
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read ( f )   # Using this will enable threaded reading behavior
            else:
                self.get_image_reference ( f )   # Using this will force sequential reading behavior

        print_debug ( 25, "Library has " + str(len(self._images.keys())) + " images" )
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


    def update ( self ):
        cur_scale_key = project_data['data']['current_scale']
        cur_scale_val = get_scale_val(cur_scale_key)
        cur_layer_index = project_data['data']['current_layer']
        scale_keys = sorted ( project_data['data']['scales'].keys() )
        scale_vals = sorted ( get_scale_val(scale_key) for scale_key in scale_keys )
        cur_stack = project_data['data']['scales'][cur_scale_key]['alignment_stack']
        layer_nums = range ( len(cur_stack) )
        amem = psutil.virtual_memory().available
        print ( "Looking at: scale " + str(cur_scale_val) + " in " + str(scale_vals) + ", layer " + str(cur_layer_index) + " in " + str(layer_nums) +
                ", Available Memory = " + str(amem) + " out of " + str(self.initial_memory.available) )

        try:
            stack = project_data['data']['scales'][project_data['data']['current_scale']]['alignment_stack']
            layer = stack[project_data['data']['current_layer']]
            for k in layer['images'].keys():
                print ( "Loading role " + k )
                try:
                    fn = layer['images'][k]['filename']
                    if (fn != None) and (len(fn) > 0):
                        print ( "Loading file " + fn )
                        self.queue_image_read ( fn )
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
        self.role = role
        self.parent = None
        self.already_painting = False

        self.floatBased = False
        self.antialiased = False
        self.wheel_index = 0
        self.scroll_factor = 1.25
        self.zoom_scale = 1.0
        self.last_button = Qt.MouseButton.NoButton

        self.mdx = 0  # Mouse Down x (screen x of mouse down at start of drag)
        self.mdy = 0  # Mouse Down y (screen y of mouse down at start of drag)
        self.ldx = 0  # Last dx (fixed while dragging)
        self.ldy = 0  # Last dy (fixed while dragging)
        self.dx = 0   # Offset in x of the image
        self.dy = 0   # Offset in y of the image

        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False

        self.setAutoFillBackground(True)
        self.setContentsMargins(0,0,0,0)

        self.setPalette(QPalette(QColor(250, 250, 200)))
        self.setAutoFillBackground(True)

        self.border_color = QColor(100,100,100,255)

        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)


    def get_settings ( self ):
        settings_dict = {}
        for key in [ "floatBased", "antialiased", "wheel_index", "scroll_factor", "zoom_scale", "last_button", "mdx", "mdy", "ldx", "ldy", "dx", "dy", "draw_border", "draw_annotations", "draw_full_paths" ]:
            settings_dict[key] = self.__dict__[key]
        return settings_dict

    def set_settings ( self, settings_dict ):
        for key in settings_dict.keys():
            self.__dict__[key] = settings_dict[key]

    def set_parent ( self, parent ):
        self.parent = parent

    def update_siblings ( self ):
        # This will cause the normal "update_self" function to be called on each sibling
        print_debug ( 30, "Update_siblings called, calling siblings.update_self" )
        if type(self.parent) == MultiImagePanel:
            print_debug ( 60, "Child of MultiImagePanel" )
            self.parent.update_multi_self(exclude=[self])

    def update_zpa_self ( self ):
        # Call the super "update" function for this panel's QWidget (this "self")
        if self.parent != None:
            self.draw_border = self.parent.draw_border
            self.draw_annotations = self.parent.draw_annotations
            self.draw_full_paths = self.parent.draw_full_paths
        super(ZoomPanWidget, self).update()


    def show_actual_size ( self ):
        print_debug ( 30, "Showing actual size image for role " + str(self.role) )
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        #self.zoom_to_wheel_at ( 0, 0 ) #pyside2
        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
        clear_crop_settings()

    def center_image ( self, all_images_in_stack = True ):
        print_debug ( 30, "Centering image for " + str(self.role) )

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
                                            other_pixmap = image_library.get_image_reference_if_loaded(layer['images'][self.role]['filename'])
                                            if other_pixmap != None:
                                                other_w = other_pixmap.width()
                                                other_h = other_pixmap.height()
                                                img_w = max(img_w, other_w)
                                                img_h = max(img_h, other_h)

                            if (img_w<=0) or (img_h<=0) or (win_w<=0) or (win_h<=0):  # Zero or negative dimensions might lock up?

                                print_debug ( 11, "Warning: Image or Window dimension is zero - cannot center image for role \"" + str(self.role) + "\"" )

                            else:

                                # Start with the image at a zoom of 1 (natural size) and with the mouse wheel centered (at 0)
                                self.zoom_scale = 1.0
                                self.ldx = 0
                                self.ldy = 0
                                self.wheel_index = 0
                                # self.zoom_to_wheel_at ( 0, 0 )

                                # Enlarge the image (scaling up) while it is within the size of the window
                                while ( self.win_x(img_w) <= win_w ) and ( self.win_y(img_h) <= win_h ):
                                  print_debug ( 70, "Enlarging image to fit in center.")
                                  #self.zoom_to_wheel_at ( 0, 0 ) #pyside2
                                  self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                  self.wheel_index += 1
                                  print_debug ( 80, "  Wheel index = " + str(self.wheel_index) + " while enlarging" )
                                  print_debug ( 80, "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(win_w) + "x" + str(win_h) )
                                  print_debug ( 80, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)) )
                                  if abs(self.wheel_index) > 100:
                                    print_debug ( -1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index) )
                                    break

                                # Shrink the image (scaling down) while it is larger than the size of the window
                                while ( self.win_x(img_w) > win_w ) or ( self.win_y(img_h) > win_h ):
                                  print_debug ( 70, "Shrinking image to fit in center.")
                                  #self.zoom_to_wheel_at ( 0, 0 ) #pyside2
                                  self.zoom_to_wheel_at(QPointF(0.0,0.0))  # pyside6
                                  self.wheel_index += -1
                                  print_debug ( 80, "  Wheel index = " + str(self.wheel_index) + " while shrinking" )
                                  print_debug ( 80, "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(win_w) + "x" + str(win_h) )
                                  print_debug ( 80, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)) )
                                  if abs(self.wheel_index) > 100:
                                    print_debug ( -1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index) )
                                    break

                                # Adjust the offsets to center
                                extra_x = win_w - self.win_x(img_w)
                                extra_y = win_h - self.win_y(img_h)

                                # Bias the y value downward to make room for text at top
                                extra_y = 1.7 * extra_y
                                self.ldx = (extra_x / 2) / self.zoom_scale
                                self.ldy = (extra_y / 2) / self.zoom_scale
        clear_crop_settings()
        print_debug ( 30, "Done centering image for " + str(self.role) )


    def win_x ( self, image_x ):
        return self.zoom_scale * (image_x + self.ldx + self.dx)

    def win_y ( self, image_y ):
        return self.zoom_scale * (image_y + self.ldy + self.dy)

    def image_x ( self, win_x ):
        img_x = (win_x/self.zoom_scale) - self.ldx
        return img_x

    def image_y ( self, win_y ):
        img_y = (win_y/self.zoom_scale) - self.ldy
        return img_y

    def dump(self):
        print_debug ( 30, "wheel = " + str(self.wheel_index) )
        print_debug ( 30, "zoom = " + str(self.zoom_scale) )
        print_debug ( 30, "ldx  = " + str(self.ldx) )
        print_debug ( 30, "ldy  = " + str(self.ldy) )
        print_debug ( 30, "mdx  = " + str(self.mdx) )
        print_debug ( 30, "mdy  = " + str(self.mdy) )
        print_debug ( 30, " dx  = " + str(self.dx) )
        print_debug ( 30, " dy  = " + str(self.dy) )

    def setFloatBased(self, float_based):
        self.floatBased = float_based
        self.update_zpa_self()

    def setAntialiased(self, antialiased):
        self.antialiased = antialiased
        self.update_zpa_self()

    #minimum #windowsize #qsize
    def minimumSizeHint(self):
        #return QSize(50, 50)
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
            print_debug ( 60, "Current Mode = " + str(mode) + ", crop_mode_origin is " + str(crop_mode_origin) + ", (x,y) is " + str([ex, ey]) + ", wxy is " + str([self.image_x(ex), self.image_y(ey)]) )
            if not self.rubberBand:
                self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
            self.rubberBand.setGeometry(QRect(crop_mode_origin,QSize()))
            self.rubberBand.show()
            self.update_siblings()
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        else:
            event_handled = False

            ex = event.x()
            ey = event.y()

            if main_window.mouse_down_callback != None:
                event_handled = main_window.mouse_down_callback ( self.role, (ex,ey), (self.image_x(ex),self.image_y(ey)), int(event.button()) )

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
        if crop_mode_callback != None:
            mode = crop_mode_callback()
            if mode == 'Crop':
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
            print_debug ( 60, "Move: Current Mode = " + str(mode) + ", crop_mode_origin is " + str(crop_mode_origin) + ", mouse is " + str(event.pos()) )
            if crop_mode_origin != None:
                self.rubberBand.setGeometry(QRect(crop_mode_origin,event.pos()).normalized())
        else:
            event_handled = False

            if main_window.mouse_move_callback != None:
                event_handled = main_window.mouse_move_callback ( self.role, (0,0), (0,0), int(event.button()) )  # These will be ignored anyway for now

            if not event_handled:

                if self.last_button == Qt.MouseButton.LeftButton:
                    self.dx = (event.x() - self.mdx) / self.zoom_scale
                    self.dy = (event.y() - self.mdy) / self.zoom_scale
                    self.update_zpa_self()

    def mouseReleaseEvent(self, event):
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

                print_debug ( 50, "Mouse drawn from (" + str(crop_mode_origin.x()) + "," + str(crop_mode_origin.y()) + ") to (" + str(event.x()) + "," + str(event.y()) + ")")
                print_debug ( 50, "Cropping with mode: " + str(crop_window_mode) )

                if crop_window_mode == 'mouse_rectangle':

                    # Convert to image coordinates
                    img_orig_x = self.image_x(crop_mode_origin.x())
                    img_orig_y = self.image_y(crop_mode_origin.y())
                    img_rel_x = self.image_x(event.x())
                    img_rel_y = self.image_y(event.y())

                    # Save the cropping corners for the actual cropping which is done later
                    crop_mode_corners = [ [ img_orig_x, img_orig_y ], [ img_rel_x, img_rel_y ] ]
                    print_debug ( 50, "Crop Corners: " + str(crop_mode_corners) ) ### These appear to be correct

                    # Convert the crop_mode_corners from image mode back into screen mode for crop_mode_disp_rect
                    crop_w = img_orig_x + self.image_x(event.x() - crop_mode_origin.x())
                    crop_h = img_orig_y + self.image_y(event.y() - crop_mode_origin.y())
                    crop_mode_disp_rect = [ [ img_orig_x, img_orig_y ], [ crop_w, crop_h ] ]

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
                    img_side = int ( round(math.sqrt ( area )) )
                    print_debug ( 30, "Cropped image will be " + str(img_side) + "x" + str(img_side) )

                    # Compute the upper left and lower right corners in image coordinates
                    img_p0_x = img_ctr_x - (img_side/2)
                    img_p0_y = img_ctr_y - (img_side/2)
                    img_p1_x = img_p0_x + img_side
                    img_p1_y = img_p0_y + img_side

                    # Save the cropping corners for the actual cropping which is done later
                    crop_mode_corners = [ [ img_p0_x, img_p0_y ], [ img_p1_x, img_p1_y ] ]
                    print_debug ( 50, "Crop Corners: " + str(crop_mode_corners) ) ### These appear to be correct

                    # Convert the crop_mode_corners from image mode back into screen mode for crop_mode_disp_rect
                    crop_w = img_p0_x + self.image_x(self.win_x(img_p1_x) - self.win_x(img_p0_x))
                    crop_h = img_p0_y + self.image_y(self.win_y(img_p1_y) - self.win_y(img_p0_y))
                    crop_mode_disp_rect = [ [ img_p0_x, img_p0_y ], [ crop_w, crop_h ] ]

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
                    img_p0_x = img_ctr_x - (img_width/2)
                    img_p0_y = img_ctr_y - (img_height/2)
                    img_p1_x = img_p0_x + img_width
                    img_p1_y = img_p0_y + img_height

                    # Save the cropping corners for the actual cropping which is done later
                    crop_mode_corners = [ [ img_p0_x, img_p0_y ], [ img_p1_x, img_p1_y ] ]
                    print_debug ( 50, "Crop Corners: " + str(crop_mode_corners) ) ### These appear to be correct

                    # Convert the crop_mode_corners from image mode back into screen mode for crop_mode_disp_rect
                    crop_w = img_p0_x + self.image_x(self.win_x(img_p1_x) - self.win_x(img_p0_x))
                    crop_h = img_p0_y + self.image_y(self.win_y(img_p1_y) - self.win_y(img_p0_y))
                    crop_mode_disp_rect = [ [ img_p0_x, img_p0_y ], [ crop_w, crop_h ] ]

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
        print_debug ( 50, "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()) )
        self.update_zpa_self()


    #def zoom_to_wheel_at ( self, mouse_win_x, mouse_win_y ): #pyside2
    def zoom_to_wheel_at(self, position):  #pyside6, position has type PySide6.QtCore.QPoint
        clear_crop_settings()
        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow (self.scroll_factor, self.wheel_index)

        # self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale) #pyside2
        # self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale) #pyside2

        self.ldx = self.ldx + (position.x() / new_scale) - (position.x() / old_scale)
        self.ldy = self.ldy + (position.y() / new_scale) - (position.y() / old_scale)


    def change_layer ( self, layer_delta ):
        global project_data
        global main_window
        global preloading_range

        if not show_skipped_images:

            # Try to juggle the layer delta to avoid any skipped images

            scale_key = project_data['data']['current_scale']
            stack = project_data['data']['scales'][scale_key]['alignment_stack']

            layer_index = project_data['data']['current_layer']
            new_layer_index = layer_index + layer_delta
            while (new_layer_index >= 0) and (new_layer_index < len(stack)):
                print_debug ( 30, "Looking for next non-skipped image")
                if stack[new_layer_index]['skip'] == False:
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
                    print_debug ( 30, "Looking for next non-skipped image")
                    if stack[new_layer_index]['skip'] == False:
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
              main_window.view_change_callback ( get_scale_key(leaving_scale), get_scale_key(entering_scale), leaving_layer, entering_layer )
            except:
              print_debug ( 0, "Exception in change_layer: " + str (sys.exc_info ()) )

          local_scales = project_data['data']['scales']   # This will be a dictionary keyed with "scale_#" keys
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
                          local_current_layer =  len(local_stack)-1
                      elif local_current_layer < 0:
                          local_current_layer = 0
                      # Store the final value in the shared "JSON"
                      project_data['data']['current_layer'] = local_current_layer

                      # Define the images needed
                      needed_images = set()
                      for i in range(len(local_stack)):
                        if abs(i-local_current_layer) < preloading_range:
                          for role,local_image in local_stack[i]['images'].items():
                            if local_image['filename'] != None:
                              if len(local_image['filename']) > 0:
                                needed_images.add ( local_image['filename'] )
                      # Ask the library to keep only those images
                      image_library.make_available ( needed_images )

          #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

          # if len(project_data['data']['scales'][local_current_layer]

          image_library.update()

          self.update_zpa_self()
          self.update_siblings()



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
        if ( int(kmods) & int(Qt.ShiftModifier) ) == 0:

            # Unshifted Scroll Wheel moves through layers

            #layer_delta = int(event.delta()/120)    #pyside2
            layer_delta = int(event.angleDelta().y() / 120)    #pyside6

            self.change_layer ( layer_delta )

            #Ref: https://stackoverflow.com/questions/35508711/how-to-enable-pan-and-zoom-in-a-qgraphicsview
            #_zoom is equivalent to wheel_index
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

            #self.wheel_index += event.delta()/120    #pyside2
            self.wheel_index += event.angleDelta().y() / 120    #pyside6
            #self.zoom_to_wheel_at(event.x(), event.y())
            #AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'x'
            self.zoom_to_wheel_at(event.position()) # return type: PySide6.QtCore.QPointF

        self.update_zpa_self()


    def paintEvent(self, event):
        global crop_mode_role
        global crop_mode_disp_rect

        print_debug(50, "Bob: Top of paintEvent")

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

                            # Scale the painter to draw the image as the background
                            painter.scale ( self.zoom_scale, self.zoom_scale )

                            if pixmap != None:
                                if self.draw_border:
                                    # Draw an optional border around the image
                                    painter.setPen(QPen(QColor(255, 255, 255, 255),4))
                                    painter.drawRect ( QRectF ( self.ldx+self.dx, self.ldy+self.dy, pixmap.width(), pixmap.height() ) )
                                # Draw the pixmap itself on top of the border to ensure every pixel is shown
                                if (not is_skipped) or self.role == 'base':
                                    painter.drawPixmap ( QPointF(self.ldx+self.dx,self.ldy+self.dy), pixmap )

                                # Draw any items that should scale with the image

                            # Rescale the painter to draw items at screen resolution
                            painter.scale ( 1.0/self.zoom_scale, 1.0/self.zoom_scale )

                            # Draw the borders of the viewport for each panel to separate panels
                            painter.setPen(QPen(self.border_color,4))
                            painter.drawRect(painter.viewport())

                            if self.draw_annotations and (pixmap != None):
                                if (pixmap.width() > 0) or (pixmap.height() > 0):
                                    painter.setPen (QPen (QColor (128, 255, 128, 255), 5))
                                    painter.drawText (painter.viewport().width()-100, 40, "%dx%d" % (pixmap.width(), pixmap.height()))


                            if self.draw_annotations and 'metadata' in ann_image:
                                colors = [ [ 255, 0, 0 ], [ 0, 255, 0 ], [ 0, 0, 255 ], [ 255, 255, 0 ], [ 255, 0, 255 ], [ 0, 255, 255 ] ]
                                if 'colors' in ann_image['metadata']:
                                    colors = ann_image['metadata']['colors']
                                    print_debug ( 95, "Colors in metadata = " + str(colors) )
                                if 'annotations' in ann_image['metadata']:
                                    # Draw the application-specific annotations from the metadata
                                    color_index = 0
                                    ann_list = ann_image['metadata']['annotations']
                                    for ann in ann_list:
                                        print_debug ( 50, "Drawing " + ann )
                                        cmd = ann[:ann.find('(')].strip().lower()
                                        pars = [ float(n.strip()) for n in ann [ ann.find('(')+1: -1 ].split(',') ]
                                        print_debug ( 50, "Command: " + cmd + " with pars: " + str(pars) )
                                        if len(pars) >= 4:
                                            color_index = int(pars[3])
                                        else:
                                            color_index = 0

                                        color_to_use = colors[color_index%len(colors)]
                                        print_debug ( 50, " Color to use: " + str(color_to_use) )
                                        painter.setPen(QPen(QColor(*color_to_use),5))
                                        x = 0
                                        y = 0
                                        r = 0
                                        if cmd in ['circle', 'square']:
                                            x = self.win_x(pars[0])
                                            y = self.win_y(pars[1])
                                            r = pars[2]
                                        if cmd == 'circle':
                                            painter.drawEllipse ( x-r, y-r, r*2, r*2 )
                                        if cmd == 'square':
                                            painter.drawRect ( QRectF ( x-r, y-r, r*2, r*2 ) )
                                        if cmd == 'skipped':
                                            # color_to_use = colors[color_index+1%len(colors)]
                                            color_to_use = [255,50,50]
                                            painter.setPen(QPen(QColor(*color_to_use),5))
                                            # painter.drawEllipse ( x-(r*2), y-(r*2), r*4, r*4 )
                                            painter.drawLine ( 0, 0, painter.viewport().width(), painter.viewport().height() )
                                            painter.drawLine ( 0, painter.viewport().height(), painter.viewport().width(), 0 )
                                        color_index += 1

                            if is_skipped:
                                # Draw the red "X" on all images regardless of whether they have the "skipped" annotation
                                color_to_use = [255,50,50]
                                painter.setPen(QPen(QColor(*color_to_use),5))
                                painter.drawLine ( 0, 0, painter.viewport().width(), painter.viewport().height() )
                                painter.drawLine ( 0, painter.viewport().height(), painter.viewport().width(), 0 )


            if self.draw_annotations:
                # Draw the role
                painter.setPen(QPen(QColor(255,100,100,255), 5))
                painter.drawText(10, 20, role_text)
                if img_text != None:
                    # Draw the image name
                    painter.setPen(QPen(QColor(100,100,255,255), 5))
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
                        layer =  scale['alignment_stack'][l]
                        if 'align_to_ref_method' in layer:
                            if 'method_results' in layer['align_to_ref_method']:
                                method_results = layer['align_to_ref_method']['method_results']
                                if 'snr_report' in method_results:
                                    if method_results['snr_report'] != None:
                                        painter.setPen (QPen (QColor (255, 255, 255, 255), 5))
                                        midw = painter.viewport().width() / 3
                                        painter.drawText(midw,20,method_results['snr_report'])

            if self.role == crop_mode_role:
                if crop_mode_disp_rect != None:
                    painter.setPen(QPen(QColor(255,100,100,255), 3))
                    rect_to_draw = QRectF ( self.win_x(crop_mode_disp_rect[0][0]), self.win_y(crop_mode_disp_rect[0][1]), self.win_x(crop_mode_disp_rect[1][0]-crop_mode_disp_rect[0][0]), self.win_y(crop_mode_disp_rect[1][1]-crop_mode_disp_rect[0][1]) )
                    painter.drawRect ( rect_to_draw )


            # Note: It's difficult to use this on a Mac because of the focus policy combined with the shared single menu.
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

            painter.end()
            del painter

            self.already_painting = False

        print_debug(50, "Bob: Bottom of paintEvent")



class MultiImagePanel(QWidget):

    def __init__(self):
        super(MultiImagePanel, self).__init__()

        # None of these attempts to auto-fill worked, so a paintEvent handler was added
        self.setStyleSheet("background-color:black;")
        #p = self.palette()
        #p.setColor(self.backgroundRole(), Qt.black)
        #self.setPalette(p)
        #self.setAutoFillBackground(True)

        self.current_margin = 0

        self.hb_layout = QHBoxLayout()
        self.update_spacing()
        self.setLayout(self.hb_layout)
        self.actual_children = []
        self.setContentsMargins(0,0,0,0)
        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False
        self.bg_color = QColor(40,50,50,255) #tag

        self.border_color = QColor(0,0,0,255)
        # QWidgets don't get the keyboard focus by default
        # To have scrolling keys associated with this (multi-panel) widget, set a "StrongFocus"
        self.setFocusPolicy(Qt.StrongFocus)
        self.arrow_direction = 1

    #keypress
    def keyPressEvent(self, event):

        print_debug ( 80, "Got a key press event: " + str(event) )

        layer_delta = 0
        if event.key() == Qt.Key_Up:
          print_debug ( 70, "Key Up" )
          layer_delta = 1 * self.arrow_direction
        if event.key() == Qt.Key_Down:
          print_debug ( 70, "Key Down" )
          layer_delta = -1 * self.arrow_direction

        if (layer_delta != 0) and (self.actual_children != None):
            panels_to_update = [ w for w in self.actual_children if (type(w) == ZoomPanWidget) ]
            for p in [ panels_to_update[0] ]:  # Only update the first one which will update the rest
                p.change_layer ( layer_delta )
                p.update_zpa_self()
                p.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        #painter.setBackgroundMode(Qt.OpaqueMode)
        #painter.setBackground(QBrush(Qt.black))
        if len(self.actual_children) <= 0:
            # Draw background for no panels
            painter.fillRect(0,0,self.width(),self.height(),self.bg_color)
            painter.setPen(QPen(QColor(200,200,200,255), 5))
            painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
            painter.drawText((self.width()/2)-140, self.height()/2, " No Image Roles Defined ")
        else:
            # Draw background for panels
            painter.fillRect(0,0,self.width(),self.height(),self.bg_color)
        painter.end()

    def update_spacing ( self ):
        print_debug ( 30, "Setting Spacing to " + str(self.current_margin) )
        #self.hb_layout.setContentsMargin(self.current_margin)    #pyside6 This sets margins around the outer edge of all panels
        #self.hb_layout.setMargin(self.current_margin)    #pyside2 This sets margins around the outer edge of all panels
        self.hb_layout.setSpacing(self.current_margin)    # This sets margins around the outer edge of all panels
        self.repaint()

    def update_multi_self ( self, exclude=() ):
        if self.actual_children != None:
            panels_to_update = [ w for w in self.actual_children if (type(w) == ZoomPanWidget) and (not (w in exclude)) ]
            for p in panels_to_update:
                p.border_color = self.border_color
                p.update_zpa_self()
                p.repaint()

    def add_panel ( self, panel ):
        if not panel in self.actual_children:
            self.actual_children.append ( panel )
            self.hb_layout.addWidget ( panel )
            panel.set_parent ( self )
            self.repaint()

    def set_roles (self, roles_list):
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
          zpw = ZoomPanWidget(role=role, parent=self)
          # Restore the settings from the previous zpw
          if role in role_settings:
            zpw.set_settings ( role_settings[role] )
          zpw.draw_border = self.draw_border
          zpw.draw_annotations = self.draw_annotations
          zpw.draw_full_paths = self.draw_full_paths
          self.add_panel ( zpw )

    def remove_all_panels ( self ):
        print_debug ( 30, "In remove_all_panels" )
        while len(self.actual_children) > 0:
            self.hb_layout.removeWidget ( self.actual_children[-1] )
            self.actual_children[-1].deleteLater()
            self.actual_children = self.actual_children[0:-1]
        self.repaint()

    def refresh_all_images ( self ):
        print_debug ( 30, "In MultiImagePanel.refresh_all_images" )
        if self.actual_children != None:
            panels_to_update = [ w for w in self.actual_children if (type(w) == ZoomPanWidget) ]
            for p in panels_to_update:
                p.update_zpa_self()
                p.repaint()
        self.repaint()

    def center_all_images ( self, all_images_in_stack=True ):
        print_debug ( 30, "In MultiImagePanel.center_all_images" )
        if self.actual_children != None:
            panels_to_update = [ w for w in self.actual_children if (type(w) == ZoomPanWidget) ]
            for p in panels_to_update:
                p.center_image(all_images_in_stack=all_images_in_stack)
                p.update_zpa_self()
                p.repaint()
        self.repaint()

    def all_images_actual_size ( self ):
        print_debug ( 30, "In MultiImagePanel.all_images_actual_size" )
        if self.actual_children != None:
            panels_to_update = [ w for w in self.actual_children if (type(w) == ZoomPanWidget) ]
            for p in panels_to_update:
                p.show_actual_size()
                p.update_zpa_self()
                p.repaint()
        self.repaint()



ignore_changes = True  # Default for first change which happens on file open?

def null_bias_changed_callback ( state ):
    global ignore_changes
    print_debug ( 50, 100*'+' )
    print_debug ( 50, "Null Bias changed to " + str(state) )
    print_debug ( 50, "ignore_changes = " + str(ignore_changes))
    print_debug ( 50, 100*'+' )
    if not ignore_changes:
        if state:
            project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends'] = True
        else:
            project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends'] = False
        print_debug ( 50, "null_bias_changed_callback (" + str(state) + " saved as " + str(project_data['data']['scales'][project_data['data']['current_scale']]['null_cafm_trends']) + ")")

def bounding_rect_changed_callback ( state ):
    global ignore_changes
    print_debug ( 50, 100*'+' )
    print_debug ( 50, "Bounding Rect changed to " + str(state) )
    print_debug ( 50, "ignore_changes = " + str(ignore_changes))
    print_debug ( 50, 100*'+' )
    if not ignore_changes:
        if state:
            project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect'] = False
        print_debug ( 50, "bounding_rec_changed_callback (" + str(state) + " saved as " + str(project_data['data']['scales'][project_data['data']['current_scale']]['use_bounding_rect']) + ")")

def skip_changed_callback ( state ):
    # This function gets called whether it's changed by the user or by another part of the program!!!
    global ignore_changes
    new_skip = bool(state)
    print_debug ( 3, "Skip changed!! New value: " + str(new_skip) )
    scale = project_data['data']['scales'][project_data['data']['current_scale']]
    layer = scale['alignment_stack'][project_data['data']['current_layer']]
    layer['skip'] = new_skip
    if update_skips_callback != None:
        update_skips_callback(bool(state))

    if update_linking_callback != None:
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

def bool_changed_callback ( state ):
    global ignore_changes
    print_debug ( 50, 100*'+' )
    print_debug ( 2, "Bool changed to " + str(state) )
    print_debug ( 2, "ignore_changes = " + str(ignore_changes))
    print_debug ( 50, 100*'+' )
    if not ignore_changes:
        if main_window != None:
            if main_window.view_change_callback != None:
                layer_num = 0
                if project_data != None:
                    if 'data' in project_data:
                        if 'current_layer' in project_data['data']:
                            layer_num = project_data['data']['current_layer']
                ignore_changes = True
                main_window.view_change_callback ( None, None, layer_num, layer_num )
                ignore_changes = False


class ControlPanelWidget(QWidget):
    """A widget to hold all of the application data for an alignment method."""
    def __init__(self, control_model=None):
        super(ControlPanelWidget, self).__init__()
        self.cm = control_model
        #self.control_panel = QWidget()
        self.control_panel_layout = QVBoxLayout()
        self.setLayout(self.control_panel_layout)
        #self.control_panel_layout.setContentsMargin(0) #pyside6
        #self.control_panel_layout.setMargin(0) #pyside2
        self.control_panel_layout.setSpacing(0)

        if self.cm != None:
            # Only show the first pane for now
            rows = control_model[0]
            print_debug ( 30, "Pane contains " + str(len(rows)) + " rows" )

            for row in rows:
              row_box = QWidget()
              row_box_layout = QHBoxLayout()
              #row_box_layout.setContentsMargin(2) #pyside6
              #row_box_layout.setMargin(2) #pyside2
              row_box_layout.setSpacing(2)
              row_box.setLayout ( row_box_layout )
              print_debug ( 30, "Row contains " + str(len(row)) + " items" )
              for item in row:
                  print_debug ( 30, "  Item is " + str(item) )
                  if type(item) == type('a'):
                      item_widget = QLabel ( str(item) )
                      item_widget.setAlignment(Qt.AlignHCenter)
                      row_box_layout.addWidget ( item_widget )
                  elif type(item) == type([]):
                      item_widget = QPushButton ( str(item[0]) )
                      row_box_layout.addWidget ( item_widget )
                  elif isinstance(item, BoolField):
                      val_widget = ( QCheckBox ( str(item.text) ) )
                      row_box_layout.addWidget ( val_widget )
                      # Hard code a few special callbacks ...
                      if item.text == "Null Bias":
                          #val_widget.stateChanged.connect(null_bias_changed_callback)
                          val_widget.clicked.connect(null_bias_changed_callback)
                      elif item.text == "Bounding Rect":
                          #val_widget.stateChanged.connect(bounding_rect_changed_callback)
                          val_widget.clicked.connect(bounding_rect_changed_callback)
                      elif item.text == "Skip":
                          #val_widget.stateChanged.connect(skip_changed_callback)
                          val_widget.clicked.connect(skip_changed_callback)
                      else:
                          #val_widget.stateChanged.connect(bool_changed_callback)
                          val_widget.clicked.connect(bool_changed_callback)
                      item.widget = val_widget
                  elif isinstance(item, TextField):
                      if item.text != None:
                          row_box_layout.addWidget ( QLabel ( str(item.text) ) )
                      val_widget = ( QLineEdit ( str(item.value) ) )
                      val_widget.setAlignment(Qt.AlignHCenter)
                      item.widget = val_widget
                      row_box_layout.addWidget ( val_widget )
                  elif isinstance(item, IntField):
                      if item.text != None:
                          row_box_layout.addWidget ( QLabel ( str(item.text) ) )
                      val_widget = ( QLineEdit ( str(item.value) ) )
                      val_widget.setAlignment(Qt.AlignHCenter)
                      item.widget = val_widget
                      row_box_layout.addWidget ( val_widget )
                  elif isinstance(item, FloatField):
                      if item.text != None:
                          row_box_layout.addWidget ( QLabel ( str(item.text) ) )
                      val_widget = ( QLineEdit ( str(item.value) ) )
                      val_widget.setAlignment(Qt.AlignHCenter)
                      item.widget = val_widget
                      row_box_layout.addWidget ( val_widget )
                  elif isinstance(item, CallbackButton):
                      item_widget = QPushButton ( str(item.text) )
                      item_widget.clicked.connect ( item.callback )
                      item.widget = item_widget
                      row_box_layout.addWidget ( item_widget )
                  elif isinstance (item, ComboBoxControl):
                      item_widget = QComboBox()
                      item_widget.addItems (item.choices)
                      #item_widget.clicked.connect ( item.callback )
                      item.widget = item_widget
                      row_box_layout.addWidget ( item_widget )
                  else:
                      item_widget = QLineEdit ( str(item) )
                      item_widget.setAlignment(Qt.AlignHCenter)
                      row_box_layout.addWidget ( item_widget )
              self.control_panel_layout.addWidget ( row_box )

    def dump ( self ):
        print_debug ( 1, "Control Panel:" )
        for p in self.cm:
          print_debug ( 1, "  Panel:" )
          for r in p:
            print_debug ( 1, "    Row:" )
            for i in r:
              print_debug ( 1, "      Item: " + str(i) )
              print_debug ( 1, "          Subclass of GenericWidget: " + str(isinstance(i,GenericWidget)) )

    def copy_self_to_data ( self ):
        data = []
        for p in self.cm:
          new_panel = []
          for r in p:
            new_row = []
            for i in r:
              if isinstance(i,GenericWidget):
                # Store as a list to identify as a widget
                new_row.append ( [ i.get_value() ] )
              else:
                # Store as static raw data
                # new_row.append ( i )  # This data is useless since it's set by the application
                new_row.append ( '' )   # Save an empty string as a place holder for static data
            new_panel.append ( new_row )
          data.append ( new_panel )
        return data

    def copy_data_to_self ( self, data ):
        ip = 0
        for p in self.cm:
          panel = data[ip]
          ip += 1
          ir = 0
          for r in p:
            row = panel[ir]
            ir += 1
            ii = 0
            for i in r:
              item = row[ii]
              ii += 1
              if type(item) == type([]):
                # This was a widget
                i.set_value ( item[0] )
              else:
                # Ignore static raw data
                pass

    def distribute_all_layer_data ( self, control_panel_layer_list ):
        # First make a copy of this widget's data
        this_layers_data = self.copy_self_to_data()

        # Search the widgets for those that should be identical across all layers
        page_index = 0
        for p in self.cm:
          row_index = 0
          for r in p:
            item_index = 0
            for i in r:
              if isinstance(i,GenericWidget):
                if 'all_layers' in dir(i):
                  if i.all_layers:
                    # Store this value in all layers
                    for l in control_panel_layer_list:
                      if l is None:
                        # There is no data stored for this layer yet.
                        # Maybe copy the entire nested list to a new layer?
                        # But the Widget fields might take care of this anyway.
                        # Pass for now.
                        pass
                      else:
                        # Just set the values that should be identical
                        l[page_index][row_index][item_index] = this_layers_data[page_index][row_index][item_index]
              else:
                pass
              item_index += 1
            row_index += 1
          page_index += 1


class GenericWidget:
    def __init__ ( self, text ):
        self.text = text
        self.widget = None
    def get_value ( self ):
        return None
    def set_value ( self, value ):
        pass

class GenericField(GenericWidget):
    def __init__ ( self, text, value, all_layers=0 ):
        #super(None,self).__init__(text)
        #super(GenericField,self).__init__(text)
        self.text = text  # Should be handled by super, but fails in Python2
        self.widget = None
        self.value = value
        self.all_layers = all_layers
    def get_value ( self ):
        return None
    def set_value ( self, value ):
        pass

class TextField(GenericField):
    def get_value ( self ):
      if 'widget' in dir(self):
        try:
          return str(self.widget.text())
        except:
          return None
      else:
        return None
    def set_value ( self, value ):
      if 'widget' in dir(self):
        try:
          self.widget.setText(str(value))
        except:
          pass

class BoolField(GenericField):
    """
    def __init__ ( self, text, value, all_layers=0, callback=None ):
        self.text = text  # Should be handled by super, but fails in Python2
        self.widget = None
        self.value = value
        self.all_layers = all_layers
        self.callback = callback
        print_debug ( 20, "BoolField created with callback = " + str(self.callback) )
    '''
    def __init__ ( self, text, value, all_layers=0, callback=None ):
        super(BoolField,self).__init__( text, value, all_layers )
        self.callback = callback
    '''
    """
    def __init__ ( self, text, value, all_layers=0, callback=None ):
        self.text = text  # Should be handled by super, but fails in Python2
        self.widget = None
        self.value = value
        self.all_layers = all_layers
        self.callback = callback
        print_debug ( 20, "BoolField created with callback = " + str(self.callback) )

    def get_value ( self ):
      if 'widget' in dir(self):
        try:
          return bool(self.widget.isChecked())
        except:
          return None
      else:
        return None
    def set_value ( self, value ):
      if 'widget' in dir(self):
        try:
          self.widget.setChecked(value)
        except:
          pass

class IntField(GenericField):
    def get_value ( self ):
      if 'widget' in dir(self):
        try:
          return int(self.widget.text())
        except:
          return None
      else:
        return None
    def set_value ( self, value ):
      if 'widget' in dir(self):
        try:
          self.widget.setText(str(value))
        except:
          pass

class FloatField(GenericField):
    def get_value ( self ):
      if 'widget' in dir(self):
        try:
          return float(self.widget.text())
        except:
          return None
      else:
        return None
    def set_value ( self, value ):
      if 'widget' in dir(self):
        try:
          self.widget.setText(str(value))
        except:
          pass

class CallbackButton(GenericWidget):
    def __init__ ( self, text, callback ):
        #super(CallbackButton,self).__init__(text)
        self.text = text  # Should be handled by super, but fails in Python2
        self.callback = callback
    def get_value ( self ):
        return None
    def set_value ( self, value ):
        pass

class ComboBoxControl(GenericWidget):
    def __init__ ( self, choices ):
        #super(CallbackButton,self).__init__(text)
        self.choices = choices
    def get_value ( self ):
        return self.widget.currentText()
    def set_value ( self, value ):
        print_debug ( 50, "ComboBoxControl.set_value ( " + str(value) + ")")
        self.widget.setCurrentText(value)
        #print ( "Setting value")
        #__import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
        pass


def align_forward():
    print_debug ( 30, "Aligning Forward ..." )

def console():
    print_debug ( 0, "\n\n\nPython Console:\n" )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



import collections
#### Neuroglancer Python Utils ####
# JSON Utils - https://github.com/google/neuroglancer/blob/a2c98640f8adb2e024acaf4e3dcbfb341b9ca42f/python/neuroglancer/json_utils.py#L53
def decode_json(x):

    return json.loads(x, object_pairs_hook=collections.OrderedDict)


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


#utils
from PySide6.QtCore import QRunnable, Signal, Slot, QThreadPool, QThread
from glanceem_utils import open_ds, add_layer
from http.server import SimpleHTTPRequestHandler, HTTPServer
import webbrowser
import neuroglancer
import operator
import logging, json
import numpy as np
import zarr
import daisy
import skimage.measure
import tifffile, imagecodecs
import dask.array as da

import multiprocessing
import os, time
import neuroglancer as ng
from glob import glob
from PIL import Image

#unchunk
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
    #img_scale = da.from_zarr(path + '/img_aligned_zarr/s' + str(scale))
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
    #blend_scale = 0
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

    # POSSIBLE WORKFLOW FOR VIEWING SINGLE BLEND IN NEUROGLANCER VIEWER
    # 1. Create blended image
    # 2. If project.zarr/img_blended_zarr group does not exist, create it
    # 3. Converted blended image to Zarr using tiffs2zarr utility function (from glanceem_utils.py).
    # 4. Blended image array is appended to project.zarr/img_blended_zarr
    # 5. Neuroglancer viewer top panel is updated to display Zarr group img_blended_zarr


# example keypress callback
def get_mouse_coords(s):
    print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
    print('  Layer selected values: %s' % (s.selected_values,))


#server #runnable
class RunnableServerThread(QRunnable):
#    def __init__(self, fn, *args, **kwargs):
    def __init__(self):
        super(RunnableServerThread, self).__init__()
        print("\nRunnableServerThread(QRunnable):\n")

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
        #time.sleep(1)
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
        print("\nServing directory %s at http://%s:%d" % (os.getcwd(), sa[0], sa[1]))
        print("\nViewer source                   :", viewer_source)
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


#webpage
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

    def acceptNavigationRequest(self, url,  _type, isMainFrame):
        if (_type == QWebEnginePage.NavigationTypeLinkClicked and url.host() != 'github.com'):
            # Pop up external links into a new window.
            w = QWebEngineView()
            w.setUrl(url)
            w.show()

            # Keep reference to external window, so it isn't cleared up.
            self.external_windows.append(w)
            return False
        return super().acceptNavigationRequest(url,  _type, isMainFrame)

# https://stackoverflow.com/questions/5671354/how-to-programmatically-make-a-horizontal-line-in-qt
class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


# def closeEvent(self, event):
#
#     quit_msg = "Are you sure you want to exit the program?"
#     reply = QMessageBox.question(self, 'Message',
#                      quit_msg, QMessageBox.Yes, QMessageBox.No)
#
#     if reply == QMessageBox.Yes:
#         event.accept()
#     else:
#         event.ignore()


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



#mainwindow contains the Menu Bar and the Status Bar
class MainWindow(QMainWindow): #jy note call to QMainWindow (allows status bar, etc.)

    def __init__(self, fname=None, panel_roles=None, control_model=None, title="Align EM", simple_mode=True):

        print('Setting MESA_GL_VERSION_OVERRIDE=4.5...')
        os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
        print('MESA_GL_VERSION_OVERRIDE = ', os.environ.get('MESA_GL_VERSION_OVERRIDE'))

        print('Setting default_format using QSurfaceFormat...')
        self.default_format = QSurfaceFormat.defaultFormat()

        print("Setting up thread pool...")
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

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
            app = QApplication([]) #jy note call to QApplication


        global project_data
        project_data = copy.deepcopy ( new_project_template )

        QMainWindow.__init__(self)
        self.setWindowTitle(title)
        self.current_project_file_name = None
        self.view_change_callback = None
        self.mouse_down_callback = None
        self.mouse_move_callback = None

        #self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        #self.setWindowFlag(Qt.FramelessWindowHint)


        # stylesheet must be after QMainWindow.__init__(self)
        self.setStyleSheet(open('stylesheet.qss').read())

        #titlebar resource
        # https://stackoverflow.com/questions/44241612/custom-titlebar-with-frame-in-pyqt5

        #pyside2... pyside6 deprecated the 'defaultSettings()' attribute of QWebEngineSettings. These two lines were uncommented.
        #self.web_settings = QWebEngineSettings.defaultSettings()
        #self.web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        #pyside6
        self.view = QWebEngineView()
        # PySide6 available options
        # self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        #!!!
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

        # jy Call the RunnableServerThread class to start background CORS web server
        # def start_server():
        #     print("\nstart_server() was called...\n")
        #     print("Creating RunnableServerThread() worker...")
        #     worker = RunnableServerThread()
        #     print("Setting up thread pool...")
        #     self.threadpool.start(worker)

        #self.browser.setPage(CustomWebEnginePage(self)) # This is necessary. Clicked links will never open new window.
        #self.browser.setPage(CustomWebEnginePage(self))

        #homepage #browserview #webview
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!%7B%22dimensions%22:%7B%22x%22:%5B8e-9%2C%22m%22%5D%2C%22y%22:%5B8e-9%2C%22m%22%5D%2C%22z%22:%5B8e-9%2C%22m%22%5D%7D%2C%22position%22:%5B2914.500732421875%2C3088.243408203125%2C4045%5D%2C%22crossSectionScale%22:3.762185354999915%2C%22projectionOrientation%22:%5B0.31435418128967285%2C0.8142172694206238%2C0.4843378961086273%2C-0.06040274351835251%5D%2C%22projectionScale%22:4593.980956070108%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/image%22%2C%22tab%22:%22source%22%2C%22name%22:%22image%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/ground_truth%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22158571%22%2C%2221894%22%2C%2222060%22%2C%2224436%22%2C%222515%22%5D%2C%22name%22:%22ground-truth%22%7D%5D%2C%22showSlices%22:false%2C%22layout%22:%224panel%22%7D"))
        #self.browser.load(QUrl("https://github.com/google/neuroglancer"))
        #self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!{'layers':{'original-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image'_'visible':false}_'corrected-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image_color_corrected'}_'ground_truth':{'type':'segmentation'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/ground_truth'_'selectedAlpha':0.63_'notSelectedAlpha':0.14_'segments':['3208'_'4901'_'13'_'4965'_'4651'_'2282'_'3189'_'3758'_'15'_'4027'_'3228'_'444'_'3207'_'3224'_'3710']}}_'navigation':{'pose':{'position':{'voxelSize':[6_6_30]_'voxelCoordinates':[5523.99072265625_8538.9384765625_1198.0423583984375]}}_'zoomFactor':22.573112129999547}_'perspectiveOrientation':[-0.004047565162181854_-0.9566211104393005_-0.2268827110528946_-0.1827099621295929]_'perspectiveZoom':340.35867907175077}"))
        #self.browser.setUrl(QUrl()) # empty/blank URL (white screen)
        #self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        #self.browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/user/README.md'))

        # Force the style to be the same on all OSs:
        app.setStyle("Fusion")

        # def demos_view(): #documentationview
        #     print("\ndocumentation_view():\n")
        #     self.browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/user/README.md'))
        #     time.sleep(2)
        #     self.stacked_widget.setCurrentIndex(2)


        def documentation_view(): #documentationview
            print("\ndocumentation_view():\n")
            # don't force the reload, add home button instead
            self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
            self.stacked_widget.setCurrentIndex(2)
            self.status.showMessage("GlanceEM_SWiFT Documentation")

        def documentation_view_home():
            self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
            self.status.showMessage("GlanceEM_SWiFT Documentation")


        def remote_view():
            print("\nremote_view():\n")
            self.stacked_widget.setCurrentIndex(4)
            self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
            self.status.showMessage("Remote Neuroglancer Viewer (https://neuroglancer-demo.appspot.com/)")

        #webgl2
        def microns_view():
            print("\nmicrons_view():\n")
            self.stacked_widget.setCurrentIndex(5)
            self.browser_microns.setUrl(QUrl('https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v0/son_of_alignment_v15_rechunked%22%2C%22type%22:%22image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22EM%22%7D%2C%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v185/seg%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22:0.51%2C%22segments%22:%5B%22648518346349538235%22%2C%22648518346349539462%22%2C%22648518346349539853%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22cell_segmentation_v185%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-clefts/mip1_d2_1175k%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22synapses%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-mito/seg_191220%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22mitochondria%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-nuclei/seg%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22nuclei%22%7D%5D%2C%22navigation%22:%7B%22pose%22:%7B%22position%22:%7B%22voxelSize%22:%5B4%2C4%2C40%5D%2C%22voxelCoordinates%22:%5B83222.921875%2C52981.34765625%2C834.9962768554688%5D%7D%7D%2C%22zoomFactor%22:383.0066650796121%7D%2C%22perspectiveOrientation%22:%5B-0.00825042650103569%2C0.06130112707614899%2C-0.0012821174459531903%2C0.9980843663215637%5D%2C%22perspectiveZoom%22:3618.7659948513424%2C%22showSlices%22:false%2C%22selectedLayer%22:%7B%22layer%22:%22cell_segmentation_v185%22%7D%2C%22layout%22:%7B%22type%22:%22xy-3d%22%2C%22orthographicProjection%22:true%7D%7D'))
            self.status.showMessage("MICrONS (http://layer23.microns-explorer.org)")
            #self.browser_microns.setUrl(QUrl('https://get.webgl.org/webgl2/'))
            #self.status.showMessage("Checking WebGL2.0 support.")

        def reload_ng():
            print("\nreload_ng():\n")
            ng_view()

        def exit_ng():
            print("\nexit_ng():\n")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")


        def exit_docs():
            print("\nexit_docs():\n")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        def exit_remote():
            print("\nexit_remote():\n")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        def exit_demos():
            print("\nexit_demos():\n")
            self.stacked_widget.setCurrentIndex(0)
            self.status.showMessage("")

        #webgl2
        # def exit_microns():
        #     print("\nexit_microns():\n")
        #     self.stacked_widget.setCurrentIndex(0)
        #     self.status.showMessage("")

        def print_state_ng():
            self.status.showMessage("Printing viewer state...")
            #viewer_state = json.loads(str(self.viewer.state))
            print("\n")
            print(self.viewer.state)
            print("\n")

            # print("Viewer.url : ", self.viewer.get_viewer_url)
            # print("Viewer.screenshot : ", self.viewer.screenshot)
            # print("Viewer.txn : ", self.viewer.txn)
            # print("Viewer.actions : ", self.viewer.actions)
            #time.sleep(1)
            #self.status.showMessage("Viewing aligned images in Neuroglancer.")

        def print_url_ng():
            self.status.showMessage("Printing viewer URL...")
            print(neuroglancer.to_url(self.viewer.state))
            #print("\nURL : " + self.viewer.get_viewer_url() + "\n")

            # print("Viewer.url : ", self.viewer.get_viewer_url)
            # print("Viewer.screenshot : ", self.viewer.screenshot)
            # print("Viewer.txn : ", self.viewer.txn)
            # print("Viewer.actions : ", self.viewer.actions)
            #time.sleep(1)
            #self.status.showMessage("Viewing aligned images in Neuroglancer.")


        # def screenshot_ng():
        #     self.status.showMessage("Taking screenshot...")
        #     ScreenshotSaver.capture(self)

        def blend_ng():
            print("blend_ng() : ")
            #self.status.showMessage("Making blended image...")



        #ng_view #ngview
        def ng_view(): # ng_view #ngview #neuroglancer
            print("\nng_view():\n")

            if not self.current_project_file_name:
                print("There is no open project. Not opening viewer.")
                self.status.showMessage("There is no project open,  nothing to view.")
                return

            destination_path = os.path.abspath(project_data['data']['destination_path'])
            zarr_project_path = os.path.join(destination_path, "project.zarr")

            if not os.path.isdir(zarr_project_path):
                print("No Zarr project file not found.")
                self.status.showMessage("Project must be exported to Zarr before it can be viewed in Neuroglancer.")
                return

            if 'server' in locals():
                print("\nServer is already running. Continuing...\n")
            else:
                #self.browser.setUrl(QUrl()) #empty page
                print("\nNo server found in local namespace. Starting RunnableServerThread() worker...\n")
                worker = RunnableServerThread()
                self.threadpool.start(worker)

            #time.sleep(1)

            print("destination_path: ", destination_path)
            print("zarr_project_dir: ", zarr_project_path)

            os.chdir(zarr_project_path) #tag

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

            print("\nInitializing neuroglancer.Viewer()...\n")
            #viewer = ng.Viewer()
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
                # scales=scales, #jy
                scales=[res_x, res_y, res_z],
            )

            # https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
            print("Updating viewer.txn()...")
            with self.viewer.txn() as s:

                #s.cross_section_background_color = "#ffffff"
                s.cross_section_background_color = "#000000"
                s.dimensions = dimensions
                # s.perspective_zoom = 300
                # s.position = [0.24, 0.095, 0.14]
                # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

                # temp = np.zeros_like(data_ref)
                # layer = ng.Layer(temp)

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
                #s.status_messages['message'] = 'Welcome to glanceEM_SWiFT!'

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

            #print(neuroglancer.to_url(self.viewer.state))




        ####

        if panel_roles != None:
            project_data['data']['panel_roles'] = panel_roles

        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False

        self.panel_list = []

        self.control_model = control_model

        if self.control_model == None:
          # Use the default control model
          self.control_model = [
            # Panes
            [ # Begin first pane
              [ "Program:", 6*" ", __file__ ],
              [ IntField("Integer:",55), 6*" ", FloatField("Floating Point:",2.3), 6*" ", BoolField("Boolean",False) ],
              [ TextField("String:","Default text"), 20*" ", CallbackButton('Align Forward', align_forward), 5*" ", "# Forward", 1, 20*" ", CallbackButton('Console', console) ]
            ] # End first pane
          ]

        #buttons


        self.control_panel = ControlPanelWidget(self.control_model)
        self.simple_mode = simple_mode
        self.main_panel = QWidget()
        self.main_panel_layout = QVBoxLayout()
        self.main_panel.setLayout ( self.main_panel_layout )
        # self.main_panel.setAutoFillBackground(False)

        self.image_panel = MultiImagePanel()
        self.image_panel.draw_border = self.draw_border
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.draw_full_paths = self.draw_full_paths
        self.image_panel.setAutoFillBackground(True)

        self.main_panel_layout.addWidget ( self.image_panel ) #jy instantiate image panel
        self.main_panel_layout.addWidget ( self.control_panel )

        self.cname_type = ComboBoxControl(['zstd  ', 'zlib  ', 'gzip  ', 'none'])
        # note - check for string comparison of 'none' later, do not add whitespace fill
        self.clevel_val = IntField("clevel (1-9):", 5)
        self.n_scales_val = IntField("scales:", 4)

        # shoehorn extra UI elements
        # self.server_button = QPushButton("Launch Server...")
        # self.server_button.clicked.connect(start_server)
        # self.main_panel_layout.addWidget(self.server_button)

        #self.main_panel_layout.addWidget(self.browser) #tag

        # Bottom configuration panel
        self.documentation_button = QPushButton("Documentation")
        self.documentation_button.clicked.connect(documentation_view)
        self.documentation_button.setFixedSize(QSize(130, 32))
        # self.microns_button = QPushButton("MICrONS")
        # self.microns_button.clicked.connect(microns_view)
        # self.microns_button.setFixedSize(QSize(130, 32))
        self.remote_viewer_button = QPushButton("Remote Viewer")
        self.remote_viewer_button.clicked.connect(remote_view)
        self.remote_viewer_button.setFixedSize(QSize(130, 32))
        self.ng_button = QPushButton("Neuroglancer View")
        self.ng_button.clicked.connect(ng_view) # HAH the () parenthesis were causing the member function to be evaluated early
        self.ng_button.setFixedSize(QSize(130, 32))

        n_scales_label = QLabel("# scales:")
        #n_scales_label.setAlignment(Qt.AlignRight)
        self.n_scales_input = QLineEdit(self)
        self.n_scales_input.setText("4")
        self.n_scales_input.setFixedWidth(40)
        self.n_scales_valid = QIntValidator(1, 20, self)
        self.n_scales_input.setValidator(self.n_scales_valid)

        clevel_label = QLabel("clevel (1-9):")
        #clevel_label.setAlignment(Qt.AlignRight)
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setText("5")
        self.clevel_input.setFixedWidth(40)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)

        cname_label = QLabel("compression:")
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])

        # self.multiview_bool = QCheckBox("Multiview Demo")
        # self.multiview_bool.setChecked(False)

        def export_zarr():

            if not self.current_project_file_name:
                print("There is no project open. Canceling export....")
                self.status.showMessage("There is no project open,  nothing to export.")
                return


            self.status.showMessage("Exporting project to Zarr...")
            destination_path = os.path.abspath(project_data['data']['destination_path'])
            print("destination_path= ", destination_path)
            # print("\nproject_data...\n",alignem.project_data)
            scale_1_path = os.path.join(project_data['data']['destination_path'], 'scale_1')  # scale_1_path= scale_1
            aligned_path = os.path.join(scale_1_path, 'img_aligned')  # aligned_path= scale_1/img_aligned
            # aligned_path_full = os.path.join(cwd, aligned_path) ???
            # print("aligned_path_full= ", aligned_path_full) ???
            print("aligned_path= ", aligned_path)

            self.clevel = self.clevel_input.text()
            self.cname = self.cname_combobox.currentText()
            self.n_scales = self.n_scales_input.text()

            # I don't like this workaround
            print("\ncwd=", os.getcwd())
            os.chdir(self.init_dir)
            print("Resetting working dir...")
            print("\ncwd=", os.getcwd())

            # why was this using aligned_path_full... odd
            if self.cname == "none":
                print("cname is none.")
                os.system(
                    "python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(
                        self.n_scales) + " -nC 1 -d " + destination_path)
            else:
                # os.system("./make_zarr.py volume_josef_small --chunks '1,5332,5332' --no_compression True")
                os.system(
                    "python3 make_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(self.n_scales) + " -cN " + str(
                        self.cname) + " -cL " + str(self.clevel) + " -d " + destination_path)

            self.status.showMessage("Export complete.")


        # def close_all(self):
        #     # if 'server' in locals():
        #     #     print("\server appears alive. Killing it...\n")
        #     #     server.server_close()
        #     print("\nQuitting application...\n")
        #     QApplication.quit()


        ############main window lower controls panel
        self.export_zarr_button = QPushButton("Export to Zarr")
        self.export_zarr_button.clicked.connect(export_zarr)
        self.export_zarr_button.setFixedSize(QSize(130, 32))
        self.h_layout = QHBoxLayout()
        self.quit_app_button = QPushButton("Exit")                                          #quit/exit app button
        #self.quit_app_button.clicked.connect(close_all)
        self.quit_app_button.clicked.connect(self.close)
        self.quit_app_button.setFixedSize(QSize(130, 32))
        #self.quit_app_button.resize(50,50) #not working could be .css
        #self.quit_app_button.setGeometry(100, 100, 600, 400) #not working could be .css
        #setfixedsize is necessary to force pushbutton size
        #self.quit_app_button.setFixedSize(QSize(100,32))
        self.h_layout.addWidget(self.quit_app_button, alignment=Qt.AlignLeft)
        self.h_layout.addWidget(self.documentation_button, alignment=Qt.AlignLeft)
        # self.h_layout.addWidget(self.microns_button, alignment=Qt.AlignLeft)
        self.spacerItem = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.h_layout.addItem(self.spacerItem)
        self.h_layout.addWidget(n_scales_label, alignment=Qt.AlignRight)
        self.h_layout.addWidget(self.n_scales_input, alignment=Qt.AlignRight)
        self.h_layout.addWidget(clevel_label, alignment=Qt.AlignRight)
        self.h_layout.addWidget(self.clevel_input, alignment=Qt.AlignRight)
        self.h_layout.addWidget(cname_label, alignment=Qt.AlignRight)
        self.h_layout.addWidget(self.cname_combobox, alignment=Qt.AlignRight)
        self.h_layout.addWidget(self.export_zarr_button, alignment=Qt.AlignRight)
        self.h_layout.addWidget(self.remote_viewer_button, alignment=Qt.AlignRight)
        self.h_layout.addWidget(self.ng_button, alignment=Qt.AlignRight)
        # self.h_layout.addWidget(self.multiview_bool, alignment=Qt.AlignRight)
        #self.h_layout.setContentsMargins(400, 0, 0, 0)

        self.layout = QGridLayout()
        self.layout.addWidget(QHLine(), 0, 0, 1, 2)
        self.layout.addWidget(QLabel("New features:"), 1, 0, 1, 1)
        self.layout.addWidget(QHLine(), 2, 0, 1, 2)
        self.main_panel_layout.addLayout(self.layout)


        self.main_panel_layout.addLayout(self.h_layout)
        # self.setCentralWidget(self.main_panel) #!!!


        ##########docs_panel DOCUMENTATION PANEL
        self.browser = QWebEngineView()
        self.browser_docs = QWebEngineView()
        #self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/README.md'))
        #self.browser_docs.setUrl(QUrl('https://github1s.com/mcellteam/swift-ir/blob/development/README.md'))

        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(QSize(100, 32))
        self.exit_docs_button.clicked.connect(exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(QSize(100, 32))
        self.readme_button.clicked.connect(documentation_view_home)
        self.docs_panel = QWidget()                                            # create QWidget()
        self.docs_panel_layout = QVBoxLayout()                                 # create QVBoxLayout()
        self.docs_panel_layout.addWidget(self.browser_docs)                    # add widgets
        self.docs_panel_controls_layout = QHBoxLayout()
        #self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignLeft | Qt.AlignBottom)   # go back button
        self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignLeft)   # go back button
        self.docs_panel_controls_layout.addWidget(self.readme_button, alignment=Qt.AlignLeft)  # go back button
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.docs_panel_controls_layout.addSpacerItem(self.spacer_item_docs)
        # layout.setContentsMargins(left, top, right, bottom)
        #self.docs_panel_controls_layout.setContentsMargins(0, 0, 1300, 0)
        self.docs_panel_layout.addLayout(self.docs_panel_controls_layout)      # add horizontal layout
        self.docs_panel.setLayout(self.docs_panel_layout)                      # set layout


        ##########remote_viewer_panel REMOTE VIEWER PANEL
        self.browser_remote = QWebEngineView()
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/')) #tacctacc
        #self.browser_remote.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.exit_remote_button = QPushButton("Back")
        self.exit_remote_button.setFixedSize(QSize(100, 32))
        self.exit_remote_button.clicked.connect(exit_remote)
        self.remote_viewer_panel = QWidget()                                              # create QWidget()
        self.remote_viewer_panel_layout = QVBoxLayout()                                   # create QVBoxLayout()
        self.remote_viewer_panel_layout.addWidget(self.browser_remote)                    # add widgets
        self.remote_viewer_panel_controls_layout = QHBoxLayout()
        self.remote_viewer_panel_controls_layout.addWidget(self.exit_remote_button, alignment=Qt.AlignLeft)   # go back button
        self.remote_viewer_panel_layout.addLayout(self.remote_viewer_panel_controls_layout)        # add horizontal layout
        self.remote_viewer_panel.setLayout(self.remote_viewer_panel_layout)                      # set layout


        # ##########remote_viewer_panel MICRONS DATA SET VIEWER PANEL
        # self.browser_microns = QWebEngineView()
        # self.browser_microns.setUrl(QUrl('https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v0/son_of_alignment_v15_rechunked%22%2C%22type%22:%22image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22EM%22%7D%2C%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v185/seg%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22:0.51%2C%22segments%22:%5B%22648518346349538235%22%2C%22648518346349539462%22%2C%22648518346349539853%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22cell_segmentation_v185%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-clefts/mip1_d2_1175k%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22synapses%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-mito/seg_191220%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22mitochondria%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-nuclei/seg%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22nuclei%22%7D%5D%2C%22navigation%22:%7B%22pose%22:%7B%22position%22:%7B%22voxelSize%22:%5B4%2C4%2C40%5D%2C%22voxelCoordinates%22:%5B83222.921875%2C52981.34765625%2C834.9962768554688%5D%7D%7D%2C%22zoomFactor%22:383.0066650796121%7D%2C%22perspectiveOrientation%22:%5B-0.00825042650103569%2C0.06130112707614899%2C-0.0012821174459531903%2C0.9980843663215637%5D%2C%22perspectiveZoom%22:3618.7659948513424%2C%22showSlices%22:false%2C%22selectedLayer%22:%7B%22layer%22:%22cell_segmentation_v185%22%7D%2C%22layout%22:%7B%22type%22:%22xy-3d%22%2C%22orthographicProjection%22:true%7D%7D'))
        # self.exit_microns_button = QPushButton("Back")
        # self.exit_microns_button.setFixedSize(QSize(100, 32))
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
        self.exit_demos_button.setFixedSize(QSize(100, 32))
        self.exit_demos_button.clicked.connect(exit_demos)
        self.demos_panel = QWidget()                                          # create QWidget()
        self.demos_panel_layout = QVBoxLayout()                               # create QVBoxLayout()
        self.demos_panel_controls_layout = QHBoxLayout()
        self.demos_panel_controls_layout.addWidget(self.exit_demos_button)    # go back button
        self.demos_panel_layout.addLayout(self.demos_panel_controls_layout)   # add horizontal layout
        self.demos_panel.setLayout(self.demos_panel_layout)                   # set layout
        #self.demos_panel_layout.addWidget(self.browser)            # add widgets


        ##########ngpanel NEUROGLANCER CONTROLS PANEL
        self.exit_ng_button = QPushButton("Back")
        self.exit_ng_button.setFixedSize(QSize(100, 32))
        self.exit_ng_button.clicked.connect(exit_ng)
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(QSize(100, 32))
        self.reload_ng_button.clicked.connect(reload_ng)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(QSize(100, 32))
        self.print_state_ng_button.clicked.connect(print_state_ng)
        self.print_url_ng_button = QPushButton("Print URL")
        self.print_url_ng_button.setFixedSize(QSize(100, 32))
        self.print_url_ng_button.clicked.connect(print_url_ng)
        # self.screenshot_ng_button = QPushButton("Screenshot")
        # self.screenshot_ng_button.setFixedSize(QSize(100, 32))
        # self.screenshot_ng_button.clicked.connect(screenshot_ng)
        # self.blend_ng_button = QPushButton("Blend (b)")
        # self.blend_ng_button.setFixedSize(QSize(100, 32))
        # self.blend_ng_button.clicked.connect(blend_ng)
        self.ng_panel = QWidget()                                      # create QWidget()
        self.ng_panel_layout = QVBoxLayout()                           # create QVBoxLayout()
        self.ng_panel_layout.addWidget(self.browser)                   # add widgets
        # layout.setContentsMargins(left, top, right, bottom)
        #self.ng_panel_controls_layout.setContentsMargins(500, 0, 0, 0)
        #self.ng_panel_controls_layout.addWidget(self.spacerItem)
        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignLeft)      # back button
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignLeft)    # reload button
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignLeft)  # reload button
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignLeft)  # reload button
        # self.ng_panel_controls_layout.addWidget(self.screenshot_ng_button, alignment=Qt.AlignLeft)  # reload button
        #self.ng_panel_controls_layout.addWidget(self.blend_ng_button, alignment=Qt.AlignLeft)  # reload button
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)     # add horizontal layout
        self.ng_panel.setLayout(self.ng_panel_layout)                     # set layout

        #self.spacerItem = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) # not working

        #stack GUI elements
        #stackedlayout STACKED WIDGET
        self.stacked_widget = QStackedWidget(self)                    # create QStackedWidget
        self.stacked_widget.addWidget(self.main_panel)                # add main_panel (0)
        self.stacked_widget.addWidget(self.ng_panel)                  # add ng_panel (1)
        self.stacked_widget.addWidget(self.docs_panel)                # add docs_panel (2)
        self.stacked_widget.addWidget(self.demos_panel)               # add demos_panel (3)
        self.stacked_widget.addWidget(self.remote_viewer_panel)       # add docs_panel (4)

        #This can be invisible, will still use to organize QStackedWidget
        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem("Main")
        self.pageComboBox.addItem("Neuroglancer Local")
        self.pageComboBox.addItem("Documentation")
        self.pageComboBox.addItem("Demos")
        self.pageComboBox.addItem("Remote Viewer")
        self.pageComboBox.activated[int].connect(self.stacked_widget.setCurrentIndex)
        #self.pageComboBox.activated.connect(self.stackedLayout.setCurrentIndex)

        self.stacked_layout = QVBoxLayout()
        self.stacked_layout.addWidget(self.stacked_widget)
        self.setCentralWidget(self.stacked_widget)               # setCentralWidget to QStackedWidget


        #verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)



        # Menu Bar
        self.action_groups = {}
        self.menu = self.menuBar()
        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
              [ '&File',
                [
                  [ '&New Project', 'Ctrl+N', self.new_project, None, None, None ],
                  [ '&Open Project', 'Ctrl+O', self.open_project, None, None, None ],
                  [ '&Save Project', 'Ctrl+S', self.save_project, None, None, None ],
                  [ 'Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Save &Cropped As...', None, self.save_cropped_as, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Set Project Destination', None, self.set_def_proj_dest, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Set Custom Destination...', None, self.set_destination, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'E&xit', 'Ctrl+Q', self.exit_app, None, None, None ]
                ]
              ],
              [ '&Images',
                [
                  [ 'Define Roles', None, self.define_roles_callback, None, None, None ],
                  [ 'Import &Base Images', None, self.import_base_images, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ '&Import into',
                    [
                      # Empty list to hold the dynamic roles as defined above
                    ]
                  ],
                  [ '&Empty into',
                    [
                      # Empty list to hold the dynamic roles as defined above
                    ]
                  ],
                  [ '-', None, None, None, None, None ],
                  [ 'Center', None, self.center_all_images, None, None, None ],
                  [ 'Actual Size', None, self.all_images_actual_size, None, None, None ],
                  [ 'Refresh', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Clear Role',
                    [
                      # Empty list to hold the dynamic roles as defined above
                    ]
                  ],
                  [ 'Remove this Layer', None, self.remove_this_layer, None, None, None ],
                  [ 'Remove ALL Layers', None, self.remove_all_layers, None, None, None ],
                  # [ 'Remove ALL Panels', None, self.remove_all_panels, None, None, None ]
                  [ 'Remove ALL Panels', None, self.not_yet, None, None, None ]
                ]
              ],
              [ '&Scaling',  # Note that this can NOT contain the string "Scale". "Scaling" is OK.
                [
                  [ '&Define Scales', None, self.define_scales_callback, None, None, None ],
                  # [ '&Generate Scales', None, self.generate_scales_callback, None, None, None ],
                  [ '&Generate Scales', None, self.not_yet, None, None, None ],
                  [ '&Import All Scales', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ '&Generate Tiled', None, self.not_yet, False, None, None ],
                  [ '&Import Tiled', None, self.not_yet, False, None, None ],
                  [ '&Show Tiled', None, self.not_yet, False, None, None ]
                ]
              ],
              [ '&Scale',
                [
                  [ '&Scale 1', None, self.do_nothing, True, "Scales", None ]
                ]
              ],
              [ '&Points',
                [
                  [ '&Alignment Point Mode', None, self.not_yet, False, None, None ],
                  [ '&Delete Points', None, self.not_yet, False, None, None ],
                  [ '&Clear All Alignment Points', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ '&Point Cursor',
                    [
                      [ 'Crosshair', None, self.not_yet, True, "Cursor", None ],
                      [ 'Target', None, self.not_yet, False, "Cursor", None ]
                    ]
                  ]
                ]
              ],
              [ '&Set',
                [
                  [ '&Max Image Size', 'Ctrl+M', self.set_max_image_size, None, None, None ],
                  [ 'Crop Size',
                    [
                      [ 'Square', None, self.set_crop_square, False, "CropSize", None ],
                      [ 'Rectangular', None, self.set_crop_rect, True, "CropSize", None ],
                      [ 'Fixed Size', None, self.set_crop_fixed, False, "CropSize", None ]
                    ]
                  ],
                  [ '-', None, None, None, None, None ],
                  [ 'Num to Preload', None, self.set_preloading_range, None, None, None ],
                  [ 'Threaded Loading', None, self.toggle_threaded_loading, image_library.threaded_loading_enabled, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Background Color', None, self.set_bg_color, None, None, None ],
                  [ 'Border Color', None, self.set_border_color, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Perform Swims', None, self.not_yet, True, None, None ],
                  [ 'Update CFMs', None, self.not_yet, True, None, None ],
                  [ 'Generate Images', None, self.not_yet, True, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Use C Version', None, self.do_nothing, use_c_version, None, None ],
                  [ 'Use File I/O', None, self.do_nothing, use_file_io, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Unlimited Zoom', None, self.not_yet, False, None, None ],
                  [ 'Reverse Arrow Keys', None, self.toggle_arrow_direction, False, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Default Plot Code', None, self.not_yet, None, None, None ],
                  [ 'Custom Plot Code', None, self.not_yet, None, None, None ]
                ]
              ],
              [ '&Show',
                [
                  [ 'Borders', None, self.toggle_border, False, None, None ],
                  [ 'Window Centers', None, self.not_yet, False, None, None ],
                  [ 'Affines', None, self.not_yet, False, None, None ],
                  [ 'Skipped Images', None, self.toggle_show_skipped, show_skipped_images, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Plot', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Annotations', None, self.toggle_annotations, True, None, None ],
                  [ 'Full Paths', None, self.toggle_full_paths, False, None, None ]
                ]
              ],
              [ '&Debug',
                [
                  [ '&Python Console', 'Ctrl+P', self.py_console, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Print Structures', None, self.print_structures, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Print Image Library', None, self.print_image_library, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Print Affine',     None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Define Waves', None, self.not_yet, None, None, None ],
                  [ 'Make Waves',   None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Define Grid', None, self.not_yet, None, None, None ],
                  [ 'Grid Align',  None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Show Waves',      None, self.not_yet, False, "GridMode", None ],
                  [ 'Show Grid Align', None, self.not_yet, False, "GridMode", None ],
                  [ 'Show Aligned',    None, self.not_yet, True,  "GridMode", None ],
                  [ '-', None, None, None, None, None ],
                  [ '&Set Debug Level',
                    [
                      [ 'Level 0',  None, self.set_debug_level, debug_level==0, "DebugLevel",  0 ],
                      [ 'Level 1',  None, self.set_debug_level, debug_level==1, "DebugLevel",  1 ],
                      [ 'Level 2',  None, self.set_debug_level, debug_level==2, "DebugLevel",  2 ],
                      [ 'Level 3',  None, self.set_debug_level, debug_level==3, "DebugLevel",  3 ],
                      [ 'Level 4',  None, self.set_debug_level, debug_level==4, "DebugLevel",  4 ],
                      [ 'Level 5',  None, self.set_debug_level, debug_level==5, "DebugLevel",  5 ],
                      [ 'Level 6',  None, self.set_debug_level, debug_level==6, "DebugLevel",  6 ],
                      [ 'Level 7',  None, self.set_debug_level, debug_level==7, "DebugLevel",  7 ],
                      [ 'Level 8',  None, self.set_debug_level, debug_level==8, "DebugLevel",  8 ],
                      [ 'Level 9',  None, self.set_debug_level, debug_level==9, "DebugLevel",  9 ],
                      [ 'Level 10',  None, self.set_debug_level, debug_level==10, "DebugLevel", 10 ],
                      [ 'Level 20',  None, self.set_debug_level, debug_level==20, "DebugLevel", 20 ],
                      [ 'Level 30',  None, self.set_debug_level, debug_level==30, "DebugLevel", 30 ],
                      [ 'Level 40',  None, self.set_debug_level, debug_level==40, "DebugLevel", 40 ],
                      [ 'Level 50',  None, self.set_debug_level, debug_level==50, "DebugLevel", 50 ],
                      [ 'Level 60',  None, self.set_debug_level, debug_level==60, "DebugLevel", 60 ],
                      [ 'Level 70',  None, self.set_debug_level, debug_level==70, "DebugLevel", 70 ],
                      [ 'Level 80',  None, self.set_debug_level, debug_level==80, "DebugLevel", 80 ],
                      [ 'Level 90',  None, self.set_debug_level, debug_level==90, "DebugLevel", 90 ],
                      [ 'Level 100', None, self.set_debug_level, debug_level==100, "DebugLevel", 100 ]
                    ]
                  ]
                ]
              ],
              [ '&Help',
                [
                  [ 'About...', None, self.not_yet, None, None, None ],
                ]
              ]
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


        self.build_menu_from_list ( self.menu, ml )

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
        # self.setMinimumWidth(600) # original #jy
        # self.setMinimumHeight(400) # original #jy
        # self.resize(2000,1000) # original #jy
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.resize(2000,1000)

        # self.setCentralWidget(self.image_hbox)
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



    def update_win_self ( self ):
        self.update()


    def build_menu_from_list (self, parent, menu_list):
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
                self.action_groups[item[4]] = QActionGroup ( self )

        for item in menu_list:
          if type(item[1]) == type([]):
            # This is a submenu
            sub = parent.addMenu(item[0])
            self.build_menu_from_list ( sub, item[1] )
          else:
            # This is a menu item (action) or a separator
            if item[0] == '-':
              # This is a separator
              parent.addSeparator()
            else:
              # This is a menu item (action) with name, accel, callback
              action = QAction ( item[0], self)
              if item[1] != None:
                action.setShortcut ( item[1] )
              if item[2] != None:
                action.triggered.connect ( item[2] )
                if item[2] == self.not_yet:
                  action.setDisabled(True)
              if item[3] != None:
                action.setCheckable(True)
                action.setChecked(item[3])
              if item[4] != None:
                self.action_groups[item[4]].addAction(action)

              parent.addAction ( action )



    @Slot()
    def do_nothing(self, checked):
        print_debug ( 90, "Doing Nothing" )
        pass

    @Slot()
    def not_yet(self):
        print_debug ( 30, "Function is not implemented yet" )

    @Slot()
    def toggle_annotations(self, checked):
        print_debug ( 30, "Toggling Annotations" )

    @Slot()
    def toggle_full_paths(self, checked):
        print_debug ( 30, "Toggling Full Paths" )

    @Slot()
    def toggle_show_skipped(self, checked):
        print_debug ( 30, "Toggling Show Skipped with checked = " + str(checked) )
        global show_skipped_images
        show_skipped_images = checked


    @Slot()
    def set_debug_level(self, checked):
        global debug_level
        action_text = self.sender().text()
        try:
            value = int(action_text.split(' ')[1])
            print_debug ( 5, "Changing Debug Level from " + str(debug_level) + " to " + str(value) )
            debug_level = value
            try:
                print_debug (5, "Changing TUI Debug Level from " + str (pyswift_tui.debug_level) + " to " + str (value))
                pyswift_tui.debug_level = value
                try:
                    print_debug (5, "Changing SWIFT Debug Level from " + str (align_swiftir.debug_level) + " to " + str (value))
                    align_swiftir.debug_level = value
                except:
                    print_debug (1, "Unable to change SWIFT Debug Level")
                    pass
            except:
                print_debug (1, "Unable to change TUI Debug Level" )
                pass
        except:
            print_debug ( 1, "Invalid debug value in: \"" + str(action_text) )

    @Slot()
    def print_structures(self, checked):
        global debug_level
        print_debug ( 2, "Data Structures:" )
        print_debug ( 2, "  project_data['version'] = " + str(project_data['version']) )
        print_debug ( 2, "  project_data.keys() = " + str(project_data.keys()) )
        print_debug ( 2, "  project_data['data'].keys() = " + str(project_data['data'].keys()) )
        print_debug ( 2, "  project_data['data']['panel_roles'] = " + str(project_data['data']['panel_roles']) )
        scale_keys = list(project_data['data']['scales'].keys())
        print_debug ( 2, "  list(project_data['data']['scales'].keys()) = " + str(scale_keys) )
        print_debug ( 2, "Scales, Layers, and Images:" )
        for k in sorted(scale_keys):
          print_debug ( 2, "  Scale key: " + str(k) +
                        ", NullBias: " + str(project_data['data']['scales'][k]['null_cafm_trends']) +
                        ", Bounding Rect: " + str(project_data['data']['scales'][k]['use_bounding_rect']) )
          scale = project_data['data']['scales'][k]
          for layer in scale['alignment_stack']:
            print_debug ( 2, "    Layer: " + str([ k for k in layer['images'].keys()]) )
            for role in layer['images'].keys():
              im = layer['images'][role]
              print_debug ( 2, "      " + str(role) + ": " + str(layer['images'][role]['filename']) )

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    @Slot()
    def print_image_library(self, checked):
        print ( str(image_library))

    def make_relative ( self, file_path, proj_path ):
        print_debug ( 20, "Proj path: " + str(proj_path) )
        print_debug ( 20, "File path: " + str(file_path) )
        rel_path = os.path.relpath(file_path,start=os.path.split(proj_path)[0])
        print_debug ( 20, "Full path: " + str(file_path) )
        print_debug ( 20, "Relative path: " + str(rel_path) )
        print_debug ( 20, "" )
        return rel_path

    def make_absolute ( self, file_path, proj_path ):
        print_debug ( 20, "Proj path: " + str(proj_path) )
        print_debug ( 20, "File path: " + str(file_path) )
        abs_path = os.path.join ( os.path.split(proj_path)[0], file_path )
        print_debug ( 20, "Full path: " + str(file_path) )
        print_debug ( 20, "Absolute path: " + str(abs_path) )
        print_debug ( 20, "" )
        return abs_path


    @Slot()
    def new_project(self):
        make_new = request_confirmation ( "Are you sure?", "Are you sure you've saved everything you want to save?" )
        if (make_new):
            print ( "Creating new project ...")
            global project_data
            project_data = copy.deepcopy ( new_project_template )
            self.current_project_file_name = None
            project_data['data']['destination_path'] = None

            self.set_scales_from_string ( "1" )
            self.define_scales_menu ( ["1"] )

            self.setWindowTitle ("No Project File")
            self.status.showMessage ( "Project File:       Destination: " )

            self.actual_size ()

    @Slot()
    def open_project(self):
        print_debug ( 20, "\n\nOpening Project\n\n" )

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, filter = QFileDialog.getOpenFileName ( parent=None,  # None was self
                                                          caption="Open Project",
                                                          filter="Projects (*.json);;All Files (*)",
                                                          selectedFilter="",
                                                          options=options)
        print_debug ( 60, "open_project ( " + str(file_name) + ")" )

        if file_name != None:
            if len(file_name) > 0:

                ignore_changes = True

                f = open ( file_name, 'r' )
                text = f.read()
                f.close()

                # Read the JSON file from the text
                global project_data
                proj_copy = json.loads ( text )

                # Upgrade the "Data Model"
                proj_copy = upgrade_data_model(proj_copy)

                if proj_copy == None:
                    # There was an unknown error loading the data model
                    print ( "Unable to load project (loaded as None)" )
                elif type(proj_copy) == type('abc'):
                    # There was a known error loading the data model
                    print ( "Error loading project:" )
                    print ( "  " + proj_copy )
                else:
                    # The data model loaded fine, so initialize the application with the data

                    self.current_project_file_name = file_name
                    self.status.showMessage ("Project File: " + self.current_project_file_name
                                             + "   Destination: " + str(proj_copy ['data'] ['destination_path']))

                    # Modify the copy to use absolute paths internally
                    if 'destination_path' in proj_copy['data']:
                      if proj_copy['data']['destination_path'] != None:
                        if len(proj_copy['data']['destination_path']) > 0:
                          proj_copy['data']['destination_path'] = self.make_absolute ( proj_copy['data']['destination_path'], self.current_project_file_name )
                    for scale_key in proj_copy['data']['scales'].keys():
                      scale_dict = proj_copy['data']['scales'][scale_key]
                      for layer in scale_dict['alignment_stack']:
                        for role in layer['images'].keys():
                          if layer['images'][role]['filename'] != None:
                            if len(layer['images'][role]['filename']) > 0:
                              layer['images'][role]['filename'] = self.make_absolute ( layer['images'][role]['filename'], self.current_project_file_name )

                    # Replace the current version with the copy
                    project_data = copy.deepcopy ( proj_copy )

                    # Get the roles from the JSON project:
                    #if project_data != None:
                    #    if 'data' in project_data:
                    #        if 'panel_roles' in project_data['data']:
                    #            if len(project_data['data']['panel_roles']) > 0:
                    #                self.define_roles ( project_data['data']['panel_roles'] )

                    # Update the scales menu
                    self.define_scales_menu ( sorted(project_data['data']['scales'].keys()) )
                    self.image_panel.update_multi_self()

                    # Set the currently selected scale from the JSON project data
                    print_debug ( 30, "Set current Scale to " + str(project_data['data']['current_scale']) )
                    self.set_selected_scale ( project_data['data']['current_scale'] )

                    # Force the currently displayed fields to reflect the newly loaded data
                    if self.view_change_callback != None:
                        if project_data != None:
                            if 'data' in project_data:
                                if 'current_layer' in project_data['data']:
                                    layer_num = project_data['data']['current_layer']
                                    scale_key = project_data['data']['current_scale']
                                    print_debug(3, "Open Project forcing values into fields with view_change_callback()")
                                    self.view_change_callback ( scale_key, scale_key, layer_num, layer_num, True )

                    if self.draw_full_paths:
                      self.setWindowTitle("Project: " + self.current_project_file_name )
                    else:
                      self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1] )

                    self.center_all_images()

                ignore_changes = False

        image_library.update()

        print_all_skips()


    def save_project_to_current_file(self):
        # Save to current file and make known file paths relative to the project file name
        if self.current_project_file_name != None:
          if len(self.current_project_file_name) > 0:
              # Write out the project
              if not self.current_project_file_name.endswith('.json'):
                  self.current_project_file_name = self.current_project_file_name + ".json"
              print_debug ( 0, "Saving to: \"" + str(self.current_project_file_name) + "\"" )
              proj_copy = copy.deepcopy ( project_data )
              if project_data ['data'] ['destination_path'] != None:
                if len(proj_copy['data']['destination_path']) > 0:
                  proj_copy['data']['destination_path'] = self.make_relative ( proj_copy['data']['destination_path'], self.current_project_file_name )
              for scale_key in proj_copy['data']['scales'].keys():
                scale_dict = proj_copy['data']['scales'][scale_key]
                for layer in scale_dict['alignment_stack']:
                  for role in layer['images'].keys():
                    if layer['images'][role]['filename'] != None:
                      if len(layer['images'][role]['filename']) > 0:
                        layer['images'][role]['filename'] = self.make_relative ( layer['images'][role]['filename'], self.current_project_file_name )
              f = open ( self.current_project_file_name, 'w' )
              jde = json.JSONEncoder ( indent=2, separators=(",",": "), sort_keys=True )
              proj_json = jde.encode ( proj_copy )
              f.write ( proj_json )
              f.close()

              if self.draw_full_paths:
                self.setWindowTitle("Project: " + self.current_project_file_name )
              else:
                self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1] )
              self.status.showMessage ("Project File: " + self.current_project_file_name
                                       + "   Destination: " + str(proj_copy['data']['destination_path']))

    @Slot()
    def save_project(self):
        if self.current_project_file_name is None:
            # Force the choosing of a name
            self.save_project_as()
        else:
            print_debug ( 1, "Saving Project..." )
            self.save_project_to_current_file()

    @Slot()
    def save_project_as(self):
        print_debug ( 1, "Saving Project..." )

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, filter = QFileDialog.getSaveFileName ( parent=None,  # None was self
                                                          caption="Save Project",
                                                          filter="Projects (*.json);;All Files (*)",
                                                          selectedFilter="",
                                                          options=options)
        print_debug ( 60, "save_project_dialog ( " + str(file_name) + ")" )

        if file_name != None:
            if len(file_name) > 0:
                self.current_project_file_name = file_name

                # Attempt to hide the file dialog before opening ...
                for p in self.panel_list:
                    p.update_zpa_self()
                # self.update_win_self()
                self.save_project_to_current_file()

                if self.draw_full_paths:
                  self.setWindowTitle("Project: " + self.current_project_file_name )
                else:
                  self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1] )

                self.set_def_proj_dest()


    @Slot()
    def save_cropped_as(self):
        print("Saving Cropped Images...")

        crop_parallel = True

        if crop_mode_role == None:
            show_warning ( "Warning", "Cannot save cropped images without a cropping region" )

        elif project_data['data']['destination_path'] == None:
            show_warning ( "Warning", "Cannot save cropped images without a destination path" )

        elif len(project_data['data']['destination_path']) <= 0:
            show_warning ( "Warning", "Cannot save cropped images without a valid destination path" )

        else:

            options = QFileDialog.Options()
            options |= QFileDialog.Directory
            options |= QFileDialog.DontUseNativeDialog

            cropped_path = QFileDialog.getExistingDirectory ( parent=None, caption="Select Directory for Cropped Images", dir=project_data['data']['destination_path'], options=options)
            print_debug ( 1, "Cropped Destination is: " + str(cropped_path) )

            if cropped_path != None:
                if len(cropped_path) > 0:
                    print ( "Crop and save images from role " + str(crop_mode_role) + " to " + str(cropped_path) )
                    scale_key = project_data['data']['current_scale']
                    cropping_queue = None
                    if crop_parallel:
                        print ( "Before: cropping_queue = task_queue.TaskQueue ( sys.executable )" )
                        # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
                        #cropping_queue = task_queue.TaskQueue ( sys.executable )
                        cropping_queue = task_queue.TaskQueue()
                        cpus = psutil.cpu_count (logical=False)
                        if cpus > 48:
                            cpus = 48
                        cropping_queue.start (cpus)
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
                        print ( "Cropping image " + infile_name )
                        print ( "Saving cropped " + outfile_name )

                        # Use the "extractStraightWindow" function which takes a center and a rectangle
                        crop_cx = int((crop_mode_corners[0][0] + crop_mode_corners[1][0]) / 2)
                        crop_cy = int((crop_mode_corners[0][1] + crop_mode_corners[1][1]) / 2)
                        crop_w = abs(int(crop_mode_corners[1][0] - crop_mode_corners[0][0]))
                        crop_h = abs(int(crop_mode_corners[1][1] - crop_mode_corners[0][1]))
                        print ( "x,y = " + str((crop_cx,crop_cy)) + ", w,h = " + str((crop_w,crop_h)) )

                        if crop_parallel:
                            my_path = os.path.split(os.path.realpath(__file__))[0]
                            crop_job = os.path.join(my_path,'single_crop_job.py')
                            print ( "cropping_queue.add_task ( [sys.executable, crop_job, str(crop_cx), str(crop_cy), str(crop_w), str(crop_h), infile_name, outfile_name] )" )
                            # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
                            cropping_queue.add_task ( [sys.executable, crop_job, str(crop_cx), str(crop_cy), str(crop_w), str(crop_h), infile_name, outfile_name] )

                        else:
                            img = align_swiftir.swiftir.extractStraightWindow ( align_swiftir.swiftir.loadImage(infile_name), xy=(crop_cx,crop_cy), siz=(crop_w,crop_h) )
                            align_swiftir.swiftir.saveImage ( img, outfile_name )


                    if crop_parallel:
                        cropping_queue.collect_results() # It might be good to have an explicit "join" function, but this seems to do so internally.



    @Slot()
    def actual_size(self):
        print_debug ( 90, "Setting images to actual size" )
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update_zpa_self()


    @Slot()
    def toggle_border(self, checked):
        print_debug ( 90, "toggle_border called with checked = " + str(checked) )
        self.draw_border = checked
        self.image_panel.draw_border = self.draw_border
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_border = self.draw_border
            p.update_zpa_self()

    @Slot()
    def toggle_arrow_direction(self, checked):
        print_debug ( 90, "toggle_arrow_direction called with checked = " + str(checked) )
        self.image_panel.arrow_direction = -self.image_panel.arrow_direction

    @Slot()
    def toggle_threaded_loading(self, checked):
        print_debug ( 90, "toggle_threaded_loading called with checked = " + str(checked) )
        image_library.threaded_loading_enabled = checked

    @Slot()
    def toggle_annotations(self, checked):
        print_debug ( 90, "toggle_annotations called with checked = " + str(checked) )
        self.draw_annotations = checked
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_annotations = self.draw_annotations
            p.update_zpa_self()

    @Slot()
    def toggle_full_paths(self, checked):
        print_debug ( 90, "toggle_full_paths called with checked = " + str(checked) )
        self.draw_full_paths = checked
        self.image_panel.draw_full_paths = self.draw_full_paths
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_full_paths = self.draw_full_paths
            p.update_zpa_self()

        if self.draw_full_paths:
            self.setWindowTitle("Project: " + self.current_project_file_name )
        else:
            self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1] )

    @Slot()
    def opt_n(self, option_name, option_action):
        if 'num' in dir(option_action):
          print_debug ( 50, "Dynamic Option[" + str(option_action.num) + "]: \"" + option_name + "\"" )
        else:
          print_debug ( 50, "Dynamic Option: \"" + option_name + "\"" )
        print_debug ( 50, "  Action: " + str(option_action) )


    def add_image_to_role ( self, image_file_name, role_name ):
        #### NOTE: TODO: This function is now much closer to empty_into_role and should be merged
        local_cur_scale = get_cur_scale()

        print_debug ( 60, "Trying to place file " + str(image_file_name) + " in role " + str(role_name) )
        if image_file_name != None:
          if len(image_file_name) > 0:
            used_for_this_role = [ role_name in l['images'].keys() for l in project_data['data']['scales'][local_cur_scale]['alignment_stack'] ]
            print_debug ( 60, "Layers using this role: " + str(used_for_this_role) )
            layer_index_for_new_role = -1
            if False in used_for_this_role:
              # This means that there is an unused slot for this role. Find the first:
              layer_index_for_new_role = used_for_this_role.index(False)
              print_debug ( 60, "Inserting file " + str(image_file_name) + " in role " + str(role_name) + " into existing layer " + str(layer_index_for_new_role) )
            else:
              # This means that there are no unused slots for this role. Add a new layer
              print_debug ( 60, "Making a new layer for file " + str(image_file_name) + " in role " + str(role_name) + " at layer " + str(layer_index_for_new_role) )
              project_data['data']['scales'][local_cur_scale]['alignment_stack'].append ( copy.deepcopy(new_layer_template) )
              layer_index_for_new_role = len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
            image_dict = project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role]['images']
            image_dict[role_name] = copy.deepcopy(new_image_template)
            image_dict[role_name]['filename'] = image_file_name


    def add_empty_to_role ( self, role_name ):
        local_cur_scale = get_cur_scale()

        used_for_this_role = [ role_name in l['images'].keys() for l in project_data['data']['scales'][local_cur_scale]['alignment_stack'] ]
        print_debug ( 60, "Layers using this role: " + str(used_for_this_role) )
        layer_index_for_new_role = -1
        if False in used_for_this_role:
          # This means that there is an unused slot for this role. Find the first:
          layer_index_for_new_role = used_for_this_role.index(False)
          print_debug ( 60, "Inserting empty in role " + str(role_name) + " into existing layer " + str(layer_index_for_new_role) )
        else:
          # This means that there are no unused slots for this role. Add a new layer
          print_debug ( 60, "Making a new layer for empty in role " + str(role_name) + " at layer " + str(layer_index_for_new_role) )
          project_data['data']['scales'][local_cur_scale]['alignment_stack'].append ( copy.deepcopy(new_layer_template) )
          layer_index_for_new_role = len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        image_dict = project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role]['images']
        image_dict[role_name] = copy.deepcopy(new_image_template)
        image_dict[role_name]['filename'] = None


    def import_images(self, role_to_import, file_name_list, clear_role=False ):
        global preloading_range
        local_cur_scale = get_cur_scale()

        print_debug ( 60, "import_images ( " + str(role_to_import) + ", " + str(file_name_list) + ")" )

        print_debug ( 30, "Importing images for role: " + str(role_to_import) )
        for f in file_name_list:
          print_debug ( 30, "   " + str(f) )
        print_debug ( 10, "Importing images for role: " + str(role_to_import) )

        if clear_role:
          # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
          for layer in project_data['data']['scales'][local_cur_scale]['alignment_stack']:
            if role_to_import in layer['images'].keys():
              layer['images'].pop(role_to_import)

        if file_name_list != None:
          if len(file_name_list) > 0:
            print_debug ( 40, "Selected Files: " + str(file_name_list) )
            print_debug ( 40, "" )
            for f in file_name_list:
              # Find next layer with an empty role matching the requested role_to_import
              print_debug ( 50, "Role " + str(role_to_import) + ", Importing file: " + str(f) )
              if f is None:
                self.add_empty_to_role ( role_to_import )
              else:
                self.add_image_to_role ( f, role_to_import )
            # Draw the panel's ("windows")
            for p in self.panel_list:
              p.force_center = True
              p.update_zpa_self()

        #center images after importing #jy
        self.center_all_images()
        #self.refresh_all_images()
        #might need:
        #self.update_panels()

        # instead, try approaching this from the import dialog code block

        self.update_win_self()



    def update_panels(self):
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()


    @Slot()
    def import_images_dialog(self, import_role_name):

        print_debug ( 5, "Importing images dialog for role: " + str(import_role_name) )

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name_list, filtr = QFileDialog.getOpenFileNames ( None,  # None was self
                                                               "Select Images to Import",
                                                               #self.openFileNameLabel.text(),
                                                               "Select Images",
                                                               "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)", "", options)

        print_debug ( 60, "import_images_dialog ( " + str(import_role_name) + ", " + str(file_name_list) + ")" )

        # Attempt to hide the file dialog before opening ...
        for p in self.panel_list:
            p.update_zpa_self()

        # self.update_win_self()

        self.import_images( import_role_name, file_name_list )

        # self.center_all_images() #center does not work
        # self.update_win_self()


    @Slot()
    def set_destination ( self ):
        print_debug ( 1, "Set Destination" )

        options = QFileDialog.Options()
        options |= QFileDialog.Directory
        options |= QFileDialog.DontUseNativeDialog

        project_data['data']['destination_path'] = QFileDialog.getExistingDirectory ( parent=None, caption="Select Destination Directory", dir=project_data['data']['destination_path'], options=options)
        print_debug ( 1, "Destination is: " + str(project_data['data']['destination_path']) )

        self.status.showMessage ("Project File: " + self.current_project_file_name
                             + "   Destination: " + str (project_data['data']['destination_path']))

    @Slot()
    def set_def_proj_dest ( self ):
        print_debug ( 1, "Set Default Project Destination to " + str(self.current_project_file_name) )
        if self.current_project_file_name == None:
          show_warning ( "No Project File", "Unable to set a project destination without a project file.\nPlease save the project file first." )
        elif len(self.current_project_file_name) == 0:
          show_warning ( "No Legal Project File", "Unable to set a project destination without a project file.\nPlease save the project file first." )
        else:
          p,e = os.path.splitext(self.current_project_file_name)
          if not (e.lower() == '.json'):
            show_warning ( "Not JSON File Extension", 'Project file must be of type "JSON".\nPlease save the project file as ".JSON" first.' )
          else:
            project_data['data']['destination_path'] = p
            #os.makedirs(project_data['data']['destination_path'])
            makedirs_exist_ok ( project_data['data']['destination_path'], exist_ok=True )
            print_debug ( 5, "Destination path is : " + str(project_data['data']['destination_path']) )
            self.status.showMessage ("Project File: " + self.current_project_file_name
                                 + "   Destination: " + str (project_data['data']['destination_path']))


    def load_images_in_role ( self, role, file_names ):
        print_debug ( 60, "load_images_in_role ( " + str(role) + ", " + str(file_names) + ")" )
        self.import_images ( role, file_names, clear_role=True )


    def define_roles ( self, roles_list ):

        # Set the image panels according to the roles
        self.image_panel.set_roles ( roles_list )

        # Set the Roles menu from this roles_list
        mb = self.menuBar()
        if not (mb is None):
          for m in mb.children():
            if type(m) == QMenu:
              text_label = ''.join(m.title().split('&'))
              if 'Images' in text_label:
                print_debug ( 30, "Found Images Menu" )
                for mm in m.children():
                  if type(mm) == QMenu:
                    text_label = ''.join(mm.title().split('&'))
                    if 'Import into' in text_label:
                      print_debug ( 30, "Found Import Into Menu" )
                      # Remove all the old actions:
                      while len(mm.actions()) > 0:
                        mm.removeAction(mm.actions()[-1])
                      # Add the new actions
                      for role in roles_list:
                        item = QAction ( role, self )
                        item.triggered.connect ( self.import_into_role )
                        mm.addAction(item)
                    if 'Empty into' in text_label:
                      print_debug ( 30, "Found Empty Into Menu" )
                      # Remove all the old actions:
                      while len(mm.actions()) > 0:
                        mm.removeAction(mm.actions()[-1])
                      # Add the new actions
                      for role in roles_list:
                        item = QAction ( role, self )
                        item.triggered.connect ( self.empty_into_role )
                        mm.addAction(item)
                    if 'Clear Role' in text_label:
                      print_debug ( 30, "Found Clear Role Menu" )
                      # Remove all the old actions:
                      while len(mm.actions()) > 0:
                        mm.removeAction(mm.actions()[-1])
                      # Add the new actions
                      for role in roles_list:
                        item = QAction ( role, self )
                        item.triggered.connect ( self.remove_all_from_role )
                        mm.addAction(item)

    def register_view_change_callback ( self, callback_function ):
        self.view_change_callback = callback_function

    def register_mouse_down_callback ( self, callback_function ):
        self.mouse_down_callback = callback_function

    def register_mouse_move_callback ( self, callback_function ):
        self.mouse_move_callback = callback_function

    @Slot()
    def define_roles_callback(self):
        default_roles = ['Stack']
        if len(project_data['data']['panel_roles']) > 0:
          default_roles = project_data['data']['panel_roles']
        input_val, ok = QInputDialog().getText ( None, "Define Roles", "Current: "+str(' '.join(default_roles)), echo=QLineEdit.Normal, text=' '.join(default_roles) )
        if ok:
          input_val = input_val.strip()
          roles_list = project_data['data']['panel_roles']
          if len(input_val) > 0:
            roles_list = [ str(v) for v in input_val.split(' ') if len(v) > 0 ]
          #if not (roles_list == project_data['data']['panel_roles']):
          self.define_roles (roles_list)
        else:
          print_debug ( 30, "Cancel: Roles not changed" )


    @Slot()
    def import_into_role(self, checked):
        import_role_name = str ( self.sender().text() )
        self.import_images_dialog ( import_role_name )

    #center try center code from here
    def import_base_images ( self ):
        self.import_images_dialog ( 'base' )
        if update_linking_callback != None:
            update_linking_callback()
            self.update_win_self():

        #patch center all images after importing
        self.center_all_images()
        self.update_win_self()

    @Slot()
    def empty_into_role(self, checked):
        #### NOTE: TODO: This function is now much closer to add_image_to_role and should be merged
        local_cur_scale = get_cur_scale()

        role_to_import = str ( self.sender().text() )

        print_debug ( 30, "Adding empty for role: " + str(role_to_import) )

        used_for_this_role = [ role_to_import in l['images'].keys() for l in project_data['data']['scales'][local_cur_scale]['alignment_stack'] ]
        print_debug ( 60, "Layers using this role: " + str(used_for_this_role) )
        layer_index_for_new_role = -1
        if False in used_for_this_role:
          # This means that there is an unused slot for this role. Find the first:
          layer_index_for_new_role = used_for_this_role.index(False)
          print_debug ( 60, "Inserting <empty> in role " + str(role_to_import) + " into existing layer " + str(layer_index_for_new_role) )
        else:
          # This means that there are no unused slots for this role. Add a new layer
          print_debug ( 60, "Making a new layer for <empty> in role " + str(role_to_import) + " at layer " + str(layer_index_for_new_role) )
          project_data['data']['scales'][local_cur_scale]['alignment_stack'].append ( copy.deepcopy(new_layer_template) )
          layer_index_for_new_role = len(project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        image_dict = project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role]['images']
        image_dict[role_to_import] = copy.deepcopy(new_image_template)

        # Draw the panels ("windows")
        for p in self.panel_list:
            p.force_center = True
            p.update_zpa_self()

        self.update_win_self()

    @Slot()
    def remove_all_from_role(self, checked):
        role_to_remove = str ( self.sender().text() )
        print_debug ( 10, "Remove role: " + str(role_to_remove) )
        self.remove_from_role ( role_to_remove )

    @Slot()
    def empty_into_role(self, checked):
        #### NOTE: TODO: This function is now much closer to add_image_to_role and should be merged
        pass


    def remove_from_role ( self, role, starting_layer=0, prompt=True):
        print_debug ( 5, "Removing " + role + " from scale " + str(get_cur_scale()) + " forward from layer " + str(starting_layer) + "  (remove_from_role)" )
        actually_remove = True
        if prompt:
            actually_remove = request_confirmation ("Note", "Do you want to remove all " + role + " images?")
        if actually_remove:
            print_debug ( 5, "Removing " + role + " images ..." )

            delete_list = []

            layer_index = 0
            for layer in project_data['data']['scales'][get_cur_scale()]['alignment_stack']:
              if layer_index >= starting_layer:
                print_debug ( 5, "Removing " + role + " from Layer " + str(layer_index) )
                if role in layer['images'].keys():
                  delete_list.append ( layer['images'][role]['filename'] )
                  print_debug (5, "  Removing " + str (layer['images'][role]['filename']))
                  layer['images'].pop(role)
                  # Remove the method results since they are no longer applicable
                  if role == 'aligned':
                    if 'align_to_ref_method' in layer.keys():
                      if 'method_results' in layer['align_to_ref_method']:
                        # Set the "method_results" to an empty dictionary to signify no results:
                        layer['align_to_ref_method']['method_results'] = {}
              layer_index += 1

            #image_library.remove_all_images()

            for fname in delete_list:
              if fname != None:
                if os.path.exists(fname):
                  os.remove(fname)
                  image_library.remove_image_reference ( fname )

            main_window.update_panels()
            main_window.refresh_all()

    def define_scales_menu ( self, scales_list ):
        # Set the Scales menu from this scales_list
        mb = self.menuBar()
        if not (mb is None):
          for m in mb.children():
            if type(m) == QMenu:
              text_label = ''.join(m.title().split('&'))
              if 'Scale' in text_label:
                print_debug ( 30, "Found Scale Menu" )
                # Remove all the old actions:
                while len(m.actions()) > 0:
                  m.removeAction(m.actions()[-1])
                # Add the new actions
                first = True
                for scale in sorted([ get_scale_val(s) for s in scales_list ]):
                  item = QAction ( str(scale), self )
                  item.setCheckable(True)
                  item.setChecked(first)
                  self.action_groups['Scales'].addAction(item)
                  item.triggered.connect ( self.set_current_scale )
                  m.addAction(item)
                  first = False

    def set_selected_scale ( self, scale_str ):
        # Set the Scales menu from this scales_list
        mb = self.menuBar()
        if not (mb is None):
          for m in mb.children():
            if type(m) == QMenu:
              text_label = ''.join(m.title().split('&'))
              if 'Scale' in text_label:
                print_debug ( 30, "Found Scale Menu" )
                scale_to_match = int(str(project_data['data']['current_scale'].split('_')[1]))
                for a in m.actions():
                  if int(a.text()) == scale_to_match:
                    a.setChecked ( True )
                    project_data['data']['current_scale'] = 'scale_' + str(scale_to_match)
                  else:
                    a.setChecked ( False )

    def set_scales_from_string(self, scale_string):
        cur_scales = [ str(v) for v in sorted ( [ get_scale_val(s) for s in project_data['data']['scales'].keys() ] ) ]
        scale_string = scale_string.strip ()
        if len (scale_string) > 0:
            input_scales = []
            try:
                input_scales = [str (v) for v in sorted ([get_scale_val (s) for s in scale_string.strip ().split (' ')])]
            except:
                print_debug (1, "Bad input: (" + str (scale_string) + "), Scales not changed")
                input_scales = []

            if not (input_scales == cur_scales):
                # The scales have changed!!
                self.define_scales_menu (input_scales)
                cur_scale_keys = [get_scale_key (v) for v in cur_scales]
                input_scale_keys = [get_scale_key (v) for v in input_scales]

                # Remove any scales not in the new list (except always leave 1)
                scales_to_remove = []
                for scale_key in project_data ['data'] ['scales'].keys ():
                    if not (scale_key in input_scale_keys):
                        if get_scale_val (scale_key) != 1:
                            scales_to_remove.append (scale_key)
                for scale_key in scales_to_remove:
                    project_data ['data'] ['scales'].pop (scale_key)

                # Add any scales not in the new list
                scales_to_add = []
                for scale_key in input_scale_keys:
                    if not (scale_key in project_data ['data'] ['scales'].keys ()):
                        scales_to_add.append (scale_key)
                for scale_key in scales_to_add:
                    new_stack = []
                    scale_1_stack = project_data ['data'] ['scales'] [get_scale_key (1)] ['alignment_stack']
                    for l in scale_1_stack:
                        new_layer = copy.deepcopy (l)
                        new_stack.append (new_layer)
                    project_data ['data'] ['scales'] [scale_key] = { 'alignment_stack': new_stack, 'method_data': {
                        'alignment_option': 'init_affine' } }
        else:
            print_debug (30, "No input: Scales not changed")


    @Slot()
    def define_scales_callback(self):
        default_scales = ['1']

        cur_scales = [ str(v) for v in sorted ( [ get_scale_val(s) for s in project_data['data']['scales'].keys() ] ) ]
        if len(cur_scales) > 0:
            default_scales = cur_scales

        input_val, ok = QInputDialog().getText ( None, "Define Scales", "Current: "+str(' '.join(default_scales)), echo=QLineEdit.Normal, text=' '.join(default_scales) )
        if ok:
            self.set_scales_from_string ( input_val )
            '''
            input_val = input_val.strip()
            if len(input_val) > 0:
                input_scales = []
                try:
                    input_scales = [ str(v) for v in sorted ( [ get_scale_val(s) for s in input_val.strip().split(' ') ] ) ]
                except:
                    print_debug ( 1, "Bad input: (" + str(input_val) + "), Scales not changed" )
                    input_scales = []

                if not (input_scales == cur_scales):
                    # The scales have changed!!
                    self.define_scales_menu (input_scales)
                    cur_scale_keys = [ get_scale_key(v) for v in cur_scales ]
                    input_scale_keys = [ get_scale_key(v) for v in input_scales ]

                    # Remove any scales not in the new list (except always leave 1)
                    scales_to_remove = []
                    for scale_key in project_data['data']['scales'].keys():
                      if not (scale_key in input_scale_keys):
                        if get_scale_val(scale_key) != 1:
                          scales_to_remove.append ( scale_key )
                    for scale_key in scales_to_remove:
                      project_data['data']['scales'].pop ( scale_key )

                    # Add any scales not in the new list
                    scales_to_add = []
                    for scale_key in input_scale_keys:
                      if not (scale_key in project_data['data']['scales'].keys()):
                        scales_to_add.append ( scale_key )
                    for scale_key in scales_to_add:
                      new_stack = []
                      scale_1_stack = project_data['data']['scales'][get_scale_key(1)]['alignment_stack']
                      for l in scale_1_stack:
                        new_layer = copy.deepcopy ( l )
                        new_stack.append ( new_layer )
                      project_data['data']['scales'][scale_key] = { 'alignment_stack': new_stack, 'method_data': {'alignment_option': 'init_affine'} }
            else:
                print_debug ( 30, "No input: Scales not changed" )
            '''
        else:
            print_debug ( 30, "Cancel: Scales not changed" )

    @Slot()
    def set_current_scale(self, checked):
        local_cur_scale = get_cur_scale()
        print_debug ( 30, "Set current Scale to " + str(self.sender().text()) )
        old_scale = local_cur_scale
        new_scale = get_scale_key ( str ( self.sender().text() ) )
        if self.view_change_callback != None:
          leaving_layer = project_data['data']['current_layer']
          entering_layer = project_data['data']['current_layer']
          try:
            # This guards against errors in "user code"
            main_window.view_change_callback ( old_scale, new_scale, leaving_layer, entering_layer )
          except:
            print_debug ( 0, "Exception in set_current_scale: " + str(sys.exc_info()) )
        local_cur_scale = new_scale
        project_data['data']['current_scale'] = local_cur_scale
        print_debug ( 30, "Set current_scale key to " + str(project_data['data']['current_scale']) )

        image_library.update()

        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()


    @Slot()
    def generate_scales_callback(self):
        print_debug ( 5, "Generating scales is now handled via control panel buttons in subclass alignem_swift." )


    @Slot()
    def remove_this_layer(self):
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
        global project_data
        local_cur_scale = get_cur_scale()
        project_data['data']['current_layer'] = 0
        while len ( project_data['data']['scales'][local_cur_scale]['alignment_stack'] ) > 0:
          project_data['data']['scales'][local_cur_scale]['alignment_stack'].pop(0)
        self.update_win_self()

    @Slot()
    def remove_all_panels(self):
        print_debug ( 30, "Removing all panels" )
        if 'image_panel' in dir(self):
            print_debug ( 30, "image_panel exists" )
            self.image_panel.remove_all_panels()
        else:
            print_debug ( 30, "image_panel does not exit!!" )
        self.define_roles ( [] )
        self.update_win_self()


    @Slot()
    def set_max_image_size(self):
        global max_image_file_size
        input_val, ok = QInputDialog().getInt ( None, "Enter Max Image File Size", "Max Image Size:", max_image_file_size )
        if ok:
          max_image_file_size = input_val

    @Slot()
    def set_crop_square(self):
        global crop_window_mode
        crop_window_mode = 'mouse_square'
        print_debug ( 10, "Crop window will be square" )

    @Slot()
    def set_crop_rect(self):
        global crop_window_mode
        crop_window_mode = 'mouse_rectangle'
        print_debug ( 10, "Crop window will be rectangular" )

    @Slot()
    def set_crop_fixed(self):
        global crop_window_mode
        global crop_window_width
        global crop_window_height

        crop_window_mode = 'mouse_center_fixed'
        current = str(crop_window_width)+'x'+str(crop_window_height)
        input_str, ok = QInputDialog().getText ( None, "Set Crop Window Size", "Current: "+current, echo=QLineEdit.Normal, text=current )
        if ok:
            wh = input_str.strip()
            if len(wh) > 0:
                w_h = []
                if 'x' in wh:
                    w_h = [ f.strip() for f in wh.split('x') ]
                elif ' ' in wh:
                    w_h = [ f.strip() for f in wh.split(' ') ]
                if len(w_h) > 0:
                    if len(w_h) >= 2:
                        # Set independently
                        crop_window_width = w_h[0]
                        crop_window_height = w_h[1]
                    else:
                        # Set together
                        crop_window_width = w_h[0]
                        crop_window_height = w_h[0]
                    print_debug ( 10, "Crop Window will be " + str(crop_window_width) + "x" + str(crop_window_height) )

    @Slot()
    def set_bg_color(self):
        c = QColorDialog.getColor()
        # print_debug ( 30, " Color = " + str(c) )
        self.image_panel.bg_color = c
        self.image_panel.update_multi_self()
        self.image_panel.repaint()

        for p in self.panel_list:
            p.update_zpa_self()
            p.repaint()

    @Slot()
    def set_border_color(self):
        c = QColorDialog.getColor()
        self.image_panel.border_color = c
        self.image_panel.update_multi_self()
        self.image_panel.repaint()
        for p in self.panel_list:
            p.border_color = c
            p.update_zpa_self()
            p.repaint()

    @Slot()
    def center_all_images(self,all_images_in_stack=True):
        self.image_panel.center_all_images(all_images_in_stack=all_images_in_stack)

    @Slot()
    def refresh_all_images(self):
        self.image_panel.refresh_all_images()

    @Slot()
    def all_images_actual_size(self):
        self.image_panel.all_images_actual_size()

    @Slot()
    def set_preloading_range(self):
        global preloading_range

        input_val, ok = QInputDialog().getInt ( None, "Enter Number of Images to Preload", "Preloading Count:", preloading_range )
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
                          if abs(i-local_current_layer) < preloading_range:
                            for role,local_image in local_stack[i]['images'].items():
                              if local_image['filename'] != None:
                                if len(local_image['filename']) > 0:
                                  needed_images.add ( local_image['filename'] )
                        # Ask the library to keep only those images
                        image_library.make_available ( needed_images )


    @Slot()
    def exit_app(self):
        sys.exit()

    @Slot()
    def py_console(self):
        print_debug ( 1, "\n\nEntering python console, use Control-D or Control-Z when done.\n" )
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



def run_app(main_win=None):
    global app
    global main_window

    if main_win == None:
        main_window = MainWindow()
    else:
        main_window = main_win

    # main_window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

    main_window.show()
    sys.exit(app.exec_())


control_model = None

# This provides default command line parameters if none are given (as with "Idle")
#if len(sys.argv) <= 1:
#    sys.argv = [ __file__, "-f", "vj_097_1k1k_1.jpg" ]

#main
if __name__ == "__main__":

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-l", "--preload", type=int, required=False, default=7, help="Preload +/-, total to preload = 2n-1")
    # options.add_argument("-t", "--test", type=int, required=False, help="Run test case: TEST")
    args = options.parse_args()
    try:
        debug_level = int(args.debug)
    except:
        pass

    if args.preload != None:
      preloading_range = int(args.preload)
      if preloading_range < 1:
        preloading_range = 1

    control_model = [
      # Panes
      [ # Begin first pane
        [ "Program: " + __file__ ],
        [ "No Control Panel Data Defined." ]
      ] # End first pane
    ]

    main_window = MainWindow ( control_model=control_model )
    main_window.resize(2200,1000)

    main_window.define_roles ( ['Stack'] )

    main_window.show()
    sys.exit(app.exec_())

