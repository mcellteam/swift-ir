'''AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
'''


import sys, traceback
import os
import argparse
import copy
import cv2
import json
import numpy
import scipy
import scipy.ndimage

import threading

from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
from PySide2.QtWidgets import QAction, QActionGroup, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox
from PySide2.QtWidgets import QMenu, QColorDialog, QMessageBox
from PySide2.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor
from PySide2.QtCore import Slot, qApp, QRect, QRectF, QSize, Qt, QPoint, QPointF


# Get the path of ../python
#alignem_file = os.path.abspath(__file__)                     # path/PySide2/alignem.py
#alignem_p    = os.path.dirname( alignem_file )               # path/PySide2
#alignem_pp   = os.path.dirname( alignem_p )                  # path
#alignem_shared_path = os.path.join ( alignem_pp, 'python' )  # path/python

#if len(sys.path) <= 0:
#  # Add the path to the currently empty path (this would be an unusual case)
#  sys.path.append ( alignem_shared_path )
#else:
#  # Add the path in the second position (after the default current directory of "")
#  sys.path.insert ( 1, alignem_shared_path )

# Import project and alignment support from SWiFT-IR:

from alignem_data_model import new_project_template, new_layer_template, new_image_template

project_data = None


debug_level = 0
def print_debug ( level, str ):
  global debug_level
  if level <= debug_level:
    print ( str )


app = None

preloading_range = 10
max_image_file_size = 1000000000

current_scale = 'scale_1'

main_window = None


def makedirs_exist_ok ( path_to_build, exist_ok=False ):
    # Needed for old python which doesn't have the exist_ok option!!!
    print ( " Make dirs for " + path_to_build )
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


def show_warning ( title, text ):
    wbox = QMessageBox.warning ( None, title, text )


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
        print_debug ( 10, "Error converting " + str(scale_of_any_type) + " to a value." )
        exi = sys.exc_info()
        print ( "  Exception type = " + str(exi[0]) )
        print ( "  Exception value = " + str(exi[1]) )
        print ( "  Exception traceback:" )
        traceback.print_tb(exi[2])
        return ( -1 )

def get_scale_key ( scale_val ):
    # Create a key like "scale_#" from either an integer or a string
    s = str(scale_val)
    while s.startswith ( 'scale_' ):
        s = s[len('scale_'):]
    return ( 'scale_' + s )


def load_image_worker ( real_norm_path, image_dict ):
    # Load the image
    print_debug ( 25, "  load_image_worker started with: \"" + str(real_norm_path) + "\"" )
    image_dict['image'] = QPixmap(real_norm_path)
    image_dict['loaded'] = True
    print_debug ( 25, "  load_image_worker finished for: \"" + str(real_norm_path) + "\"" )


class ImageLibrary:
    '''A class containing multiple images keyed by their file name.'''
    def __init__ ( self ):
        self._images = {}  # { image_key: { "task": task, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey ( self, file_path ):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def get_image_reference ( self, file_path ):
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            load_new = False
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
        return ( image_ref )

    def remove_image_reference ( self, file_path ):
        image_ref = None
        if not (file_path is None):
            real_norm_path = self.pathkey(file_path)
            if real_norm_path in self._images:
                print_debug ( 25, "Unloading image: \"" + real_norm_path + "\"" )
                image_ref = self._images.pop(real_norm_path)['image']
        # This returned value may not be valid when multi-threading is implemented
        return ( image_ref )

    def queue_image_read ( self, file_path ):
        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = { 'image': None, 'loaded': False, 'loading': True, 'task':None }
        t = threading.Thread ( target = load_image_worker, args = (real_norm_path,self._images[real_norm_path]) )
        t.start()
        self._images[real_norm_path]['task'] = t

    def make_available ( self, requested ):
        '''
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        '''

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


image_library = ImageLibrary()



class ZoomPanWidget(QWidget):
    '''A widget to display a single annotated image with zooming and panning.'''
    def __init__(self, role, parent=None, fname=None):
        super(ZoomPanWidget, self).__init__(parent)
        self.role = role

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

        self.setStyleSheet("background-color:black;")
        self.setAutoFillBackground(True)
        self.setContentsMargins(0,0,0,0)

        self.setStyleSheet("background-color:black;")

        self.setPalette(QPalette(QColor(250, 250, 200)))
        self.setAutoFillBackground(True)

        self.border_color = QColor(100,100,100,255)

        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def get_settings ( self ):
        settings_dict = {}
        for key in [ "floatBased", "antialiased", "wheel_index", "scroll_factor", "zoom_scale", "last_button", "mdx", "mdy", "ldx", "ldy", "dx", "dy", "draw_border", "draw_annotations", "draw_full_paths" ]:
            settings_dict[key] = self.__dict__[key]
        return ( settings_dict )

    def set_settings ( self, settings_dict ):
        for key in settings_dict.keys():
            self.__dict__[key] = settings_dict[key]

    def set_parent ( self, parent ):
        self.parent = parent

    def update_siblings ( self ):
        # This will cause the normal "update_self" function to be called on each sibling
        print_debug ( 30, "Update_siblings called, calling siblings.update_self" )
        if type(self.parent) == MultiImagePanel:
            print_debug ( 30, "Child of MultiImagePanel" )
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
        self.zoom_to_wheel_at ( 0, 0 )


    def center_image ( self ):
        print_debug ( 30, "Centering image for " + str(self.role) )

        if project_data != None:

            s = project_data['data']['current_scale']
            l = project_data['data']['current_layer']

            if len(project_data['data']['scales']) > 0:
                if len(project_data['data']['scales'][s]['alignment_stack']) > 0:

                    image_dict = project_data['data']['scales'][s]['alignment_stack'][l]['images']

                    if self.role in image_dict.keys():
                        ann_image = image_dict[self.role]
                        pixmap = image_library.get_image_reference(ann_image['filename'])
                        if pixmap != None:
                            img_w = pixmap.width()
                            img_h = pixmap.height()
                            win_w = self.width()
                            win_h = self.height()

                            if (img_w<=0) or (img_h<=0) or (win_w<=0) or (win_h<=0):  # Zero or negative dimensions might lock up?

                                print_debug ( -1, "Warning: Image or Window dimension is zero - cannot center image for role \"" + str(self.role) + "\"" )

                            else:

                                # Start with the image at a zoom of 1 (natural size) and with the mouse wheel centered (at 0)
                                self.zoom_scale = 1.0
                                self.ldx = 0
                                self.ldy = 0
                                self.wheel_index = 0
                                # self.zoom_to_wheel_at ( 0, 0 )

                                # Enlarge the image (scaling up) while it is within the size of the window
                                while ( self.win_x(img_w) <= win_w ) and ( self.win_y(img_h) <= win_h ):
                                  print_debug ( 40, "Enlarging image to fit in center.")
                                  self.zoom_to_wheel_at ( 0, 0 )
                                  self.wheel_index += 1
                                  print_debug ( 40, "  Wheel index = " + str(self.wheel_index) + " while enlarging" )
                                  print_debug ( 40, "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(win_w) + "x" + str(win_h) )
                                  print_debug ( 40, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)) )
                                  if abs(self.wheel_index) > 100:
                                    print_debug ( -1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index) )
                                    break

                                # Shrink the image (scaling down) while it is larger than the size of the window
                                while ( self.win_x(img_w) > win_w ) or ( self.win_y(img_h) > win_h ):
                                  print_debug ( 40, "Shrinking image to fit in center.")
                                  self.zoom_to_wheel_at ( 0, 0 )
                                  self.wheel_index += -1
                                  print_debug ( 40, "  Wheel index = " + str(self.wheel_index) + " while shrinking" )
                                  print_debug ( 40, "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(win_w) + "x" + str(win_h) )
                                  print_debug ( 40, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)) )
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
        print_debug ( 30, "Done centering image for " + str(self.role) )


    def win_x ( self, image_x ):
        return ( self.zoom_scale * (image_x + self.ldx + self.dx) )

    def win_y ( self, image_y ):
        return ( self.zoom_scale * (image_y + self.ldy + self.dy) )

    def image_x ( self, win_x ):
        img_x = (win_x/self.zoom_scale) - self.ldx
        return ( img_x )

    def image_y ( self, win_y ):
        img_y = (win_y/self.zoom_scale) - self.ldy
        return ( img_y )

    def dump(self):
        print_debug ( 30, "wheel = " + str(self.wheel_index) )
        print_debug ( 30, "zoom = " + str(self.zoom_scale) )
        print_debug ( 30, "ldx  = " + str(self.ldx) )
        print_debug ( 30, "ldy  = " + str(self.ldy) )
        print_debug ( 30, "mdx  = " + str(self.mdx) )
        print_debug ( 30, "mdy  = " + str(self.mdy) )
        print_debug ( 30, " dx  = " + str(self.dx) )
        print_debug ( 30, " dy  = " + str(self.dy) )

    def setFloatBased(self, floatBased):
        self.floatBased = floatBased
        self.update_zpa_self()

    def setAntialiased(self, antialiased):
        self.antialiased = antialiased
        self.update_zpa_self()

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
        return QSize(180, 180)


    def mousePressEvent(self, event):
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
        event_handled = False

        if main_window.mouse_move_callback != None:
            event_handled = main_window.mouse_move_callback ( self.role, (0,0), (0,0), int(event.button()) )  # These will be ignored anyway for now

        if not event_handled:

            if self.last_button == Qt.MouseButton.LeftButton:
                self.dx = (event.x() - self.mdx) / self.zoom_scale
                self.dy = (event.y() - self.mdy) / self.zoom_scale
                self.update_zpa_self()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.ldx = self.ldx + self.dx
            self.ldy = self.ldy + self.dy
            self.dx = 0
            self.dy = 0
            self.update_zpa_self()

    def mouseDoubleClickEvent(self, event):
        print_debug ( 50, "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()) )
        self.update_zpa_self()


    def zoom_to_wheel_at ( self, mouse_win_x, mouse_win_y ):
        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow (self.scroll_factor, self.wheel_index)

        self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale)
        self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale)


    def change_layer ( self, layer_delta ):
        global project_data
        global main_window
        global preloading_range

        if project_data != None:

          if main_window.view_change_callback != None:

            leaving_layer = project_data['data']['current_layer']
            entering_layer = project_data['data']['current_layer'] + layer_delta

            if entering_layer < 0:
                entering_layer = 0

            try:
              leaving_scale = project_data['data']['current_scale']
              entering_scale = project_data['data']['current_scale']
              main_window.view_change_callback ( get_scale_key(leaving_scale), get_scale_key(entering_scale), leaving_layer, entering_layer )
            except:
              print ( "Exception in view_change_callback" )

          local_scales = project_data['data']['scales']   # This will be a dictionary keyed with "scale_#" keys
          local_current_scale = project_data['data']['current_scale']  # Get it from the data model
          if local_current_scale in local_scales:
              local_scale = local_scales[local_current_scale]
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

          self.update_zpa_self()
          self.update_siblings()



    def wheelEvent(self, event):

        global project_data
        global main_window
        global preloading_range

        kmods = event.modifiers()
        if ( int(kmods) & int(Qt.ShiftModifier) ) == 0:

            # Unshifted Scroll Wheel moves through layers

            layer_delta = int(event.delta()/120)

            self.change_layer ( layer_delta )

        else:
            # Shifted Scroll Wheel zooms

            self.wheel_index += event.delta()/120
            self.zoom_to_wheel_at(event.x(), event.y())

        self.update_zpa_self()


    def paintEvent(self, event):
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
                            painter.drawPixmap ( QPointF(self.ldx+self.dx,self.ldy+self.dy), pixmap )

                            # Draw any items that should scale with the image

                        # Rescale the painter to draw items at screen resolution
                        painter.scale ( 1.0/self.zoom_scale, 1.0/self.zoom_scale )

                        # Draw the borders of the viewport for each panel to separate panels
                        painter.setPen(QPen(self.border_color,4))
                        painter.drawRect(painter.viewport())

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
                                    color_index += 1



        if self.draw_annotations:
            # Draw the role
            painter.setPen(QPen(QColor(255,100,100,255), 5))
            painter.drawText(20, 30, role_text)
            if img_text != None:
              painter.setPen(QPen(QColor(100,100,255,255), 5))
              if self.draw_full_paths:
                painter.drawText(20, 60, img_text)
              else:
                if os.path.sep in img_text:
                  # Only split the path if it's splittable
                  painter.drawText(20, 60, os.path.split(img_text)[-1])
                else:
                  painter.drawText(20, 60, img_text)

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        painter.end()
        del painter



class MultiImagePanel(QWidget):

    def __init__(self):
        super(MultiImagePanel, self).__init__()

        # None of these attempts to auto-fill worked, so a paintEvent handler was added
        #self.setStyleSheet("background-color:black;")
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
        self.bg_color = QColor(40,50,50,255)
        self.border_color = QColor(0,0,0,255)
        # QWidgets don't get the keyboard focus by default
        # To have scrolling keys associated with this (multi-panel) widget, set a "StrongFocus"
        self.setFocusPolicy(Qt.StrongFocus)
        self.arrow_direction = 1

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
        self.hb_layout.setMargin(self.current_margin)    # This sets margins around the outer edge of all panels
        self.hb_layout.setSpacing(self.current_margin)    # This sets margins around the outer edge of all panels
        self.repaint()

    def update_multi_self ( self, exclude=[] ):
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
            self.remove_all_panels(None)
        except:
            pass
        # Create the new panels
        for role in roles_list:
          zpw = ZoomPanWidget(role=role, parent=self, fname=None)
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

    def center_all_images ( self ):
        print_debug ( 30, "In MultiImagePanel.center_all_images" )
        if self.actual_children != None:
            panels_to_update = [ w for w in self.actual_children if (type(w) == ZoomPanWidget) ]
            for p in panels_to_update:
                p.center_image()
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

def bool_changed_callback ( state ):
    print_debug ( 50, 100*'+' )
    print_debug ( 50, "Bool changed to " + str(state) )
    print_debug ( 50, 100*'+' )
    global ignore_changes
    if not ignore_changes:
        if main_window != None:
            if main_window.view_change_callback != None:
                layer_num = 0
                if project_data != None:
                    if 'data' in project_data:
                        if 'current_layer' in project_data['data']:
                            layer_num = project_data['data']['current_layer']
                ignore_changes = True
                main_window.view_change_callback ( -1, -1, layer_num, layer_num )
                ignore_changes = False


class ControlPanelWidget(QWidget):
    '''A widget to hold all of the application data for an alignment method.'''
    def __init__(self, control_model=None):
        super(ControlPanelWidget, self).__init__()
        self.cm = control_model
        #self.control_panel = QWidget()
        self.control_panel_layout = QVBoxLayout()
        self.setLayout(self.control_panel_layout)
        self.control_panel_layout.setMargin(0)
        self.control_panel_layout.setSpacing(0)

        if self.cm != None:
            # Only show the first pane for now
            rows = control_model[0]
            print_debug ( 30, "Pane contains " + str(len(rows)) + " rows" )

            for row in rows:
              row_box = QWidget()
              row_box_layout = QHBoxLayout()
              row_box_layout.setMargin(2)
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
                      val_widget.stateChanged.connect ( bool_changed_callback )
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
                  else:
                      item_widget = QLineEdit ( str(item) )
                      item_widget.setAlignment(Qt.AlignHCenter)
                      row_box_layout.addWidget ( item_widget )
              self.control_panel_layout.addWidget ( row_box )

    def dump ( self ):
        print ( "Control Panel:" )
        for p in self.cm:
          print ( "  Panel:" )
          for r in p:
            print ( "    Row:" )
            for i in r:
              print ( "      Item: " + str(i) )
              print ( "          Subclass of GenericWidget: " + str(isinstance(i,GenericWidget)) )

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
        return ( data )

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
    '''
    def __init__ ( self, text, value, all_layers=0, callback=None ):
        self.text = text  # Should be handled by super, but fails in Python2
        self.widget = None
        self.value = value
        self.all_layers = all_layers
        self.callback = callback
        print ( "BoolField created with callback = " + str(self.callback) )
    """
    def __init__ ( self, text, value, all_layers=0, callback=None ):
        super(BoolField,self).__init__( text, value, all_layers )
        self.callback = callback
    """
    '''

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

def align_forward():
    print_debug ( 30, "Aligning Forward ..." )

def console():
    print_debug ( 0, "\n\n\nPython Console:\n" )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



# MainWindow contains the Menu Bar and the Status Bar
class MainWindow(QMainWindow):

    def __init__(self, fname=None, panel_roles=None, control_model=None, title="Align EM"):

        global app
        if app == None:
                app = QApplication([])

        global project_data
        project_data = copy.deepcopy ( new_project_template )

        QMainWindow.__init__(self)
        self.setWindowTitle(title)

        self.current_project_file_name = None

        self.view_change_callback = None
        self.scale_change_callback = None
        self.mouse_down_callback = None
        self.mouse_move_callback = None

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

        self.control_panel = ControlPanelWidget(self.control_model)

        self.main_panel = QWidget()

        self.main_panel_layout = QVBoxLayout()
        self.main_panel.setLayout ( self.main_panel_layout )
        self.main_panel.setAutoFillBackground(False)

        self.image_panel = MultiImagePanel()
        self.image_panel.draw_border = self.draw_border
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.draw_full_paths = self.draw_full_paths
        self.image_panel.setStyleSheet("background-color:black;")
        self.image_panel.setAutoFillBackground(True)

        self.main_panel_layout.addWidget ( self.image_panel )
        self.main_panel_layout.addWidget ( self.control_panel )

        self.setCentralWidget(self.main_panel)


        # Menu Bar
        self.action_groups = {}
        self.menu = self.menuBar()
        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
              [ '&File',
                [
                  #[ '&New Project', 'Ctrl+N', self.not_yet, None, None, None ],
                  [ '&Open Project', 'Ctrl+O', self.open_project, None, None, None ],
                  #[ '&Save Project', 'Ctrl+S', self.save_project, None, None, None ],
                  [ '&Save Project', 'Ctrl+S', self.save_project, None, None, None ],
                  [ 'Save Project &As', 'Ctrl+A', self.save_project_as, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Set Project Destination', None, self.set_def_proj_dest, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Set Other Destination...', None, self.set_destination, None, None, None ],
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
                  [ '-', None, None, None, None, None ],
                  [ 'Num to Preload', None, self.set_preloading_range, None, None, None ],
                  [ 'Threaded Loading', None, self.toggle_threaded_loading, False, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Background Color', None, self.set_bg_color, None, None, None ],
                  [ 'Border Color', None, self.set_border_color, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Perform Swims', None, self.not_yet, True, None, None ],
                  [ 'Update CFMs', None, self.not_yet, True, None, None ],
                  [ 'Generate Images', None, self.not_yet, True, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Use C Version', None, self.do_nothing, False, None, None ],
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
                  [ 'Skipped Images', None, self.not_yet, True, None, None ],
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
                      [ 'Level 0',   None, self.set_debug_level, False, "DebugLevel", 0 ],
                      [ 'Level 10',  None, self.set_debug_level, True,  "DebugLevel", 10 ],
                      [ 'Level 20',  None, self.set_debug_level, False, "DebugLevel", 20 ],
                      [ 'Level 30',  None, self.set_debug_level, False, "DebugLevel", 30 ],
                      [ 'Level 40',  None, self.set_debug_level, False, "DebugLevel", 40 ],
                      [ 'Level 50',  None, self.set_debug_level, False, "DebugLevel", 50 ],
                      [ 'Level 60',  None, self.set_debug_level, False, "DebugLevel", 60 ],
                      [ 'Level 70',  None, self.set_debug_level, False, "DebugLevel", 70 ],
                      [ 'Level 80',  None, self.set_debug_level, False, "DebugLevel", 80 ],
                      [ 'Level 90',  None, self.set_debug_level, False, "DebugLevel", 90 ],
                      [ 'Level 100', None, self.set_debug_level, False, "DebugLevel", 100 ]
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
        self.build_menu_from_list ( self.menu, ml )

        # Status Bar
        self.status = self.statusBar()
        if fname == None:
          self.status.showMessage("No Status Yet ...")
        else:
          # self.status.showMessage("File: "+fname)
          self.status.showMessage("File: unknown")

        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)
        # self.setFixedSize(geometry.width() * 0.8, geometry.height() * 0.7)
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
    def set_debug_level(self, checked):
        global debug_level
        action_text = self.sender().text()
        try:
            value = int(action_text.split(' ')[1])
            print_debug ( 30, "Changing Debug Level from " + str(debug_level) + " to " + str(value) )
            debug_level = value
        except:
            print_debug ( 30, "Invalid debug value in: \"" + str(action_text) )

    @Slot()
    def print_structures(self, checked):
        global debug_level
        print_debug ( 30, "Data Structures:" )
        print_debug ( 30, "  project_data['version'] = " + str(project_data['version']) )
        print_debug ( 30, "  project_data.keys() = " + str(project_data.keys()) )
        print_debug ( 30, "  project_data['data'].keys() = " + str(project_data['data'].keys()) )
        print_debug ( 30, "  project_data['data']['panel_roles'] = " + str(project_data['data']['panel_roles']) )
        scale_keys = list(project_data['data']['scales'].keys())
        print_debug ( 30, "  list(project_data['data']['scales'].keys()) = " + str(scale_keys) )
        print ( "Scales, Layers, and Images:" )
        for k in sorted(scale_keys):
          print ( "  Scale key: " + str(k) )
          scale = project_data['data']['scales'][k]
          for layer in scale['alignment_stack']:
            print ( "    Layer: " + str([ k for k in layer['images'].keys()]) )
            for role in layer['images'].keys():
              im = layer['images'][role]
              print ( "      " + str(role) + ": " + str(layer['images'][role]['filename']) )

        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def make_relative ( self, file_path, proj_path ):
        print ( "Proj path: " + str(proj_path) )
        print ( "File path: " + str(file_path) )
        rel_path = os.path.relpath(file_path,start=os.path.split(proj_path)[0])
        print ( "Full path: " + str(file_path) )
        print ( "Relative path: " + str(rel_path) )
        print ( "" )
        return rel_path

    def make_absolute ( self, file_path, proj_path ):
        print ( "Proj path: " + str(proj_path) )
        print ( "File path: " + str(file_path) )
        abs_path = os.path.join ( os.path.split(proj_path)[0], file_path )
        print ( "Full path: " + str(file_path) )
        print ( "Absolute path: " + str(abs_path) )
        print ( "" )
        return abs_path


    @Slot()
    def open_project(self):
        print_debug ( 1, "\n\nOpening Project\n\n" )

        options = QFileDialog.Options()
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

                self.current_project_file_name = file_name

                # Modifiy the copy to use absolute paths internally
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
                                self.view_change_callback ( scale_key, scale_key, layer_num, layer_num, True )

                if self.draw_full_paths:
                  self.setWindowTitle("Project: " + self.current_project_file_name )
                else:
                  self.setWindowTitle("Project: " + os.path.split(self.current_project_file_name)[-1] )

                self.center_all_images()

                ignore_changes = False


    def save_project_to_current_file(self):
        # Save to current file and make known file paths relative to the project file name
        if self.current_project_file_name != None:
          if len(self.current_project_file_name) > 0:
              # Write out the project
              print_debug ( 0, "Saving to: \"" + str(self.current_project_file_name) + "\"" )
              proj_copy = copy.deepcopy ( project_data )
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

    @Slot()
    def save_project(self):
        if self.current_project_file_name is None:
            # Force the choosing of a name
            self.save_project_as()
        else:
            print_debug ( 1, "\n\n\nSaving Project\n\n\n" )
            self.save_project_to_current_file()

    @Slot()
    def save_project_as(self):
        print_debug ( 1, "\n\nSaving Project\n\n" )

        options = QFileDialog.Options()
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
        print_debug ( 90, "toggle_border called with checked = " + str(checked) )
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

        print_debug ( 60, "Trying to place file " + str(image_file_name) + " in role " + str(role_name) )
        if image_file_name != None:
          if len(image_file_name) > 0:
            found_layer = None
            this_layer_index = 0

            used_for_this_role = [ role_name in l['images'].keys() for l in project_data['data']['scales'][current_scale]['alignment_stack'] ]
            print_debug ( 60, "Layers using this role: " + str(used_for_this_role) )
            layer_index_for_new_role = -1
            if False in used_for_this_role:
              # This means that there is an unused slot for this role. Find the first:
              layer_index_for_new_role = used_for_this_role.index(False)
              print_debug ( 60, "Inserting file " + str(image_file_name) + " in role " + str(role_name) + " into existing layer " + str(layer_index_for_new_role) )
            else:
              # This means that there are no unused slots for this role. Add a new layer
              print_debug ( 60, "Making a new layer for file " + str(image_file_name) + " in role " + str(role_name) + " at layer " + str(layer_index_for_new_role) )
              project_data['data']['scales'][current_scale]['alignment_stack'].append ( copy.deepcopy(new_layer_template) )
              layer_index_for_new_role = len(project_data['data']['scales'][current_scale]['alignment_stack']) - 1
            image_dict = project_data['data']['scales'][current_scale]['alignment_stack'][layer_index_for_new_role]['images']
            image_dict[role_name] = copy.deepcopy(new_image_template)
            image_dict[role_name]['filename'] = image_file_name


    def add_empty_to_role ( self, role_name ):

        used_for_this_role = [ role_name in l['images'].keys() for l in project_data['data']['scales'][current_scale]['alignment_stack'] ]
        print_debug ( 60, "Layers using this role: " + str(used_for_this_role) )
        layer_index_for_new_role = -1
        if False in used_for_this_role:
          # This means that there is an unused slot for this role. Find the first:
          layer_index_for_new_role = used_for_this_role.index(False)
          print_debug ( 60, "Inserting empty in role " + str(role_name) + " into existing layer " + str(layer_index_for_new_role) )
        else:
          # This means that there are no unused slots for this role. Add a new layer
          print_debug ( 60, "Making a new layer for empty in role " + str(role_name) + " at layer " + str(layer_index_for_new_role) )
          project_data['data']['scales'][current_scale]['alignment_stack'].append ( copy.deepcopy(new_layer_template) )
          layer_index_for_new_role = len(project_data['data']['scales'][current_scale]['alignment_stack']) - 1
        image_dict = project_data['data']['scales'][current_scale]['alignment_stack'][layer_index_for_new_role]['images']
        image_dict[role_name] = copy.deepcopy(new_image_template)
        image_dict[role_name]['filename'] = None


    def import_images(self, role_to_import, file_name_list, clear_role=False ):
        global preloading_range

        print_debug ( 60, "import_images ( " + str(role_to_import) + ", " + str(file_name_list) + ")" )

        print_debug ( 30, "Importing images for role: " + str(role_to_import) )
        for f in file_name_list:
          print_debug ( 30, "   " + str(f) )
        print_debug ( 10, "Importing images for role: " + str(role_to_import) )

        if clear_role:
          # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
          for layer in project_data['data']['scales'][current_scale]['alignment_stack']:
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

        self.update_win_self()


    def update_panels(self):
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()


    @Slot()
    def import_images_dialog(self, import_role_name):

        print_debug ( 5, "Importing images dialog for role: " + str(import_role_name) )

        options = QFileDialog.Options()
        if False:  # self.native.isChecked():
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


    @Slot()
    def set_destination ( self ):
        print_debug ( 1, "Set Destination" )

        options = QFileDialog.Options()
        options |= QFileDialog.Directory
        if False:  # self.native.isChecked():
            options |= QFileDialog.DontUseNativeDialog

        project_data['data']['destination_path'] = QFileDialog.getExistingDirectory ( parent=None, caption="Select Destination Directory", dir=project_data['data']['destination_path'], options=options)
        print_debug ( 1, "Destination is: " + str(project_data['data']['destination_path']) )

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
            print ( "Destination path is : " + str(project_data['data']['destination_path']) )


    def load_images_in_role ( self, role, file_names ):
        print_debug ( 60, "load_images_in_role ( " + str(role) + ", " + str(file_names) + ")" )
        self.import_images ( role, file_names, clear_role=True )


    def define_roles ( self, roles_list ):

        # Set the image panels according to the roles
        self.image_panel.set_roles ( roles_list )

        # Set the Roles menu from this roles_list
        roles_menu = None
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
                      first = True
                      for role in roles_list:
                        item = QAction ( role, self )
                        #item.setCheckable(True)
                        #item.setChecked(first)
                        item.triggered.connect ( self.import_into_role )
                        mm.addAction(item)
                        first = False
                    if 'Empty into' in text_label:
                      print_debug ( 30, "Found Empty Into Menu" )
                      # Remove all the old actions:
                      while len(mm.actions()) > 0:
                        mm.removeAction(mm.actions()[-1])
                      # Add the new actions
                      first = True
                      for role in roles_list:
                        item = QAction ( role, self )
                        #item.setCheckable(True)
                        #item.setChecked(first)
                        item.triggered.connect ( self.empty_into_role )
                        mm.addAction(item)
                        first = False

    def register_view_change_callback ( self, callback_function ):
        self.view_change_callback = callback_function

    def register_scale_change_callback ( self, callback_function ):
        self.scale_change_callback = callback_function

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
          if not (roles_list == project_data['data']['panel_roles']):
            self.define_roles (roles_list)
        else:
          print_debug ( 30, "Cancel: Roles not changed" )


    @Slot()
    def import_into_role(self, checked):
        import_role_name = str ( self.sender().text() )
        self.import_images_dialog ( import_role_name )

    def import_base_images ( self ):
        self.import_images_dialog ( 'base' )

    @Slot()
    def empty_into_role(self, checked):
        #### NOTE: TODO: This function is now much closer to add_image_to_role and should be merged

        role_to_import = str ( self.sender().text() )

        print_debug ( 30, "Adding empty for role: " + str(role_to_import) )

        used_for_this_role = [ role_to_import in l['images'].keys() for l in project_data['data']['scales'][current_scale]['alignment_stack'] ]
        print_debug ( 60, "Layers using this role: " + str(used_for_this_role) )
        layer_index_for_new_role = -1
        if False in used_for_this_role:
          # This means that there is an unused slot for this role. Find the first:
          layer_index_for_new_role = used_for_this_role.index(False)
          print_debug ( 60, "Inserting <empty> in role " + str(role_to_import) + " into existing layer " + str(layer_index_for_new_role) )
        else:
          # This means that there are no unused slots for this role. Add a new layer
          print_debug ( 60, "Making a new layer for <empty> in role " + str(role_to_import) + " at layer " + str(layer_index_for_new_role) )
          project_data['data']['scales'][current_scale]['alignment_stack'].append ( copy.deepcopy(new_layer_template) )
          layer_index_for_new_role = len(project_data['data']['scales'][current_scale]['alignment_stack']) - 1
        image_dict = project_data['data']['scales'][current_scale]['alignment_stack'][layer_index_for_new_role]['images']
        image_dict[role_to_import] = copy.deepcopy(new_image_template)

        # Draw the panels ("windows")
        for p in self.panel_list:
            p.force_center = True
            p.update_zpa_self()

        self.update_win_self()


    def define_scales_menu ( self, scales_list ):
        # Set the Scales menu from this scales_list
        scales_menu = None
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
        scales_menu = None
        mb = self.menuBar()
        if not (mb is None):
          for m in mb.children():
            if type(m) == QMenu:
              text_label = ''.join(m.title().split('&'))
              if 'Scale' in text_label:
                print_debug ( 30, "Found Scale Menu" )
                global current_scale
                scale_to_match = int(str(project_data['data']['current_scale'].split('_')[1]))
                for a in m.actions():
                  if int(a.text()) == scale_to_match:
                    a.setChecked ( True )
                    project_data['data']['current_scale'] = 'scale_' + str(scale_to_match)
                    current_scale = project_data['data']['current_scale']
                  else:
                    a.setChecked ( False )


    @Slot()
    def define_scales_callback(self):
        default_scales = ['1']

        cur_scales = [ str(v) for v in sorted ( [ get_scale_val(s) for s in project_data['data']['scales'].keys() ] ) ]
        if len(cur_scales) > 0:
            default_scales = cur_scales

        input_val, ok = QInputDialog().getText ( None, "Define Scales", "Current: "+str(' '.join(default_scales)), echo=QLineEdit.Normal, text=' '.join(default_scales) )
        if ok:
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
                      project_data['data']['scales'][scale_key] = { 'alignment_stack': new_stack }
            else:
                print_debug ( 30, "No input: Scales not changed" )
        else:
            print_debug ( 30, "Cancel: Scales not changed" )

    @Slot()
    def set_current_scale(self, checked):
        global current_scale
        print_debug ( 30, "Set current Scale to " + str(self.sender().text()) )
        old_scale = current_scale
        new_scale = get_scale_key ( str ( self.sender().text() ) )
        if self.scale_change_callback != None:
            self.scale_change_callback ( old_scale, new_scale )
        current_scale = new_scale
        project_data['data']['current_scale'] = current_scale
        print_debug ( 30, "Set current_scale key to " + str(project_data['data']['current_scale']) )

        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()


    @Slot()
    def generate_scales_callback(self):
        print ( "Generating scales is now handled via control panel buttons in subclass alignem_swift." )


    @Slot()
    def remove_this_layer(self):
        local_current_layer = project_data['data']['current_layer']
        project_data['data']['scales'][current_scale]['alignment_stack'].pop(local_current_layer)
        if local_current_layer >= len(project_data['data']['scales'][current_scale]['alignment_stack']):
          local_current_layer = len(project_data['data']['scales'][current_scale]['alignment_stack']) - 1
        project_data['data']['current_layer'] = local_current_layer

        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def remove_all_layers(self):
        global project_data
        project_data['data']['current_layer'] = 0
        while len ( project_data['data']['scales'][current_scale]['alignment_stack'] ) > 0:
          project_data['data']['scales'][current_scale]['alignment_stack'].pop(0)
        self.update_win_self()

    @Slot()
    def remove_all_panels(self):
        print_debug ( 30, "Removing all panels" )
        if 'image_panel' in dir(self):
            print_debug ( 30, "image_panel exists" )
            self.image_panel.remove_all_panels(None)
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
    def center_all_images(self):
        self.image_panel.center_all_images()

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
            local_current_scale = project_data['data']['current_scale']
            if local_current_scale in local_scales:
                local_scale = local_scales[local_current_scale]
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

if __name__ == "__main__":

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, help="Print more information with larger DEBUG (0 to 100)")
    # options.add_argument("-t", "--test", type=int, required=False, help="Run test case: TEST")
    args = options.parse_args()
    try:
        debug_level = int(args.debug)
    except:
        pass

    control_model = [
      # Panes
      [ # Begin first pane
        [ "Program: " + __file__ ],
        [ "No Control Panel Data Defined." ]
      ] # End first pane
    ]

    main_window = MainWindow ( control_model=control_model )
    main_window.resize(2400,1000)

    main_window.define_roles ( ['Stack'] )

    main_window.show()
    sys.exit(app.exec_())

