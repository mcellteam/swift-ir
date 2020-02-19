'''AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
'''


import sys
import os
import argparse
import copy
import cv2
import json
import numpy
import scipy
import scipy.ndimage


from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
from PySide2.QtWidgets import QAction, QActionGroup, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox
from PySide2.QtWidgets import QMenu, QColorDialog, QMessageBox
from PySide2.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor
from PySide2.QtCore import Slot, qApp, QRect, QRectF, QSize, Qt, QPoint, QPointF


# Get the path of ../python
alignem_file = os.path.abspath(__file__)                     # path/PySide2/alignem.py
alignem_p    = os.path.dirname( alignem_file )               # path/PySide2
alignem_pp   = os.path.dirname( alignem_p )                  # path
alignem_shared_path = os.path.join ( alignem_pp, 'python' )  # path/python

if len(sys.path) <= 0:
  # Add the path to the currently empty path (this would be an unusual case)
  sys.path.append ( alignem_shared_path )
else:
  # Add the path in the second position (after the default current directory of "")
  sys.path.insert ( 1, alignem_shared_path )

# Import project and alignment support from SWiFT-IR:


import swift_project

project_data = None


new_project_template = \
{
  "version": 0.25,
  "method": "SWiFT-IR",
  "user_settings": {
    "max_image_file_size": 100000000
  },
  "data": {
    "source_path": "",
    "current_layer": 0,
    "current_scale": "scale_1",
    "defaults": {
      "align_to_next_pars": {
        "addx": 800,
        "addy": 800,
        "bias_x_per_image": 0.0,
        "bias_y_per_image": 0.0,
        "output_level": 0,
        "window_size": 1024
      }
    },
    "destination_path": "",
    "pairwise_alignment": True,
    "panel_roles": [
      "ref",
      "base",
      "aligned"
    ],
    "scales": {
      "scale_1": {
        "alignment_stack": []
      }
    }
  }
}

new_layer_template = \
{
  "align_to_ref_method": {
    "method_data": {
      "addx": 256,
      "addy": 256,
      "alignment_option": "Init Affine",
      "alignment_options": [
        "Init Affine",
        "Refine Affine",
        "Apply Affine"
      ],
      "bias_rot_per_image": 0.0,
      "bias_scale_x_per_image": 0.0,
      "bias_scale_y_per_image": 0.0,
      "bias_skew_x_per_image": 0.0,
      "bias_x_per_image": 0.0,
      "bias_y_per_image": 0.0,
      "output_level": 0,
      "window_size": 256
    },
    "method_options": [
      "Auto Swim Align",
      "Match Point Align"
    ],
    "selected_method": "Auto Swim Align",
    "method_results": {
      "affine_matrix": [
        [ 1.0, 0.0, 0.0 ],
        [ 0.0, 1.0, 0.0 ]
      ],
      "cumulative_afm": [
        [ 1.0, 0.0, 0.0 ],
        [ 0.0, 1.0, 0.0 ]
      ],
      "snr": 12.345
    }
  },
  "images": {},
  "skip": None
}


new_image_template = \
{
  "filename": "",
  "metadata": {
    "annotations": [],
    "match_points": []
  }
}


work_from_dict = False

debug_level = 0
def print_debug ( level, str ):
  global debug_level
  if level <= debug_level:
    print ( str )


app = None

preloading_range = 3
max_image_file_size = 1000000000

# The scale_list is a list of dictionaries containing an alignment_layer and scale information
scale_list = [ [] ]
scale_index = 0
current_scale = 'scale_1'

# alignment_layer_list = []
alignment_layer_index = 0

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

class ImageLibrary:
    '''A class containing multiple images keyed by their file name.'''
    def __init__ ( self ):
        self.images = {}

    def get_image_reference ( self, file_path ):
        image_ref = None
        real_norm_path = os.path.realpath(os.path.normpath(file_path))
        if real_norm_path in self.images:
            image_ref = self.images[real_norm_path]
        else:
            print_debug ( 10, "  Loading image: \"" + real_norm_path + "\"" )
            self.images[real_norm_path] = QPixmap(real_norm_path)
            image_ref = self.images[real_norm_path]
        return ( image_ref )

    def remove_image_reference ( self, file_path ):
        image_ref = None
        if not (file_path is None):
            real_norm_path = os.path.realpath(os.path.normpath(file_path))
            if real_norm_path in self.images:
                print_debug ( 10, "Unloading image: \"" + real_norm_path + "\"" )
                image_ref = self.images.pop(real_norm_path)
        return ( image_ref )

    def make_available ( self, requested ):
        already_loaded = set(self.images.keys())
        normalized_requested = set( [os.path.realpath(os.path.normpath(f)) for f in requested] )
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference ( f )
        for f in need_to_load:
            self.get_image_reference ( f )

        print ( "Library has " + str(len(self.images.keys())) + " images" )
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def remove_all_images ( self ):
        keys = self.images.keys()
        for k in keys:
          self.remove_image_reference ( k )
        self.images = {}

image_library = ImageLibrary()



class AnnotatedImage:
    '''A class containing an image and other information to be displayed.'''
    def __init__ ( self, role, file_name, load_now=False ):
        self.role = role
        if file_name is None:
          self.image_file_name = None
        else:
          self.image_file_name = os.path.realpath(os.path.normpath(file_name))
        self.image_size = None
        self.pixmap = None
        if load_now:
          self.load()

    def load ( self ):
        global max_image_file_size
        global image_library
        if self.image_file_name != None:
          if len(self.image_file_name) > 0:
            try:
              if self.image_size == None:
                # Get the size if needed
                f = open ( self.image_file_name )
                f.seek (0, 2)  # Seek to the end
                self.image_size = f.tell()
                f.close()
              if self.image_size <= max_image_file_size:
                app.setOverrideCursor(Qt.WaitCursor)
                ##print_debug ( 10, "Loading image: \"" + self.image_file_name + "\"" )
                ##self.pixmap = QPixmap(self.image_file_name)
                self.pixmap = image_library.get_image_reference(self.image_file_name)
                app.restoreOverrideCursor()
              else:
                print_debug ( 10, "Skipping image: \"" + self.image_file_name + "\" (" + str(self.image_size) + " > " + str(max_image_file_size) + ")" )
            except:
                print_debug ( 1, "Error opening image: \"" + str(self.image_file_name) )
                exi = sys.exc_info()
                print ( "  Exception type = " + str(exi[0]) )
                print ( "  Exception value = " + str(exi[1]) )
                print ( "  Exception trace = " + str(exi[2]) )


    def unload ( self ):
        global scale_list
        global scale_index
        global image_library
        alignment_layer_list = scale_list[scale_index]
        self.pixmap = None
        found = False
        for alignment_layer in alignment_layer_list:
          for image in alignment_layer.image_list:
            if image.image_file_name == self.image_file_name:
              if image != self:
                found = True
                break
        if not found:
          image_library.remove_image_reference ( self.image_file_name )


global_panel_roles = []

global_image_scales = [ '1' ]


class DisplayLayer:
    '''A class representing the data at one "layer" of an image stack.'''
    def __init__ ( self, role_name, file_name, load_now=False ):
        self.image_list = []
        self.image_list.append ( AnnotatedImage ( str(role_name), file_name, load_now ) )
        self.control_panel_data = None

    def isLoaded ( self ):
        for im in self.image_list:
            if im.pixmap == None:
                return ( False )
        return ( True )

    def load ( self ):
        for im in self.image_list:
            im.load()

    def unload ( self ):
        for im in self.image_list:
            im.unload()

    def to_data ( self ):
        data = {}
        data['control_panel_data'] = self.control_panel_data
        data['image_list'] = []
        for im in self.image_list:
            im_data = {}
            im_data['role'] = im.role
            im_data['image_file_name'] = im.image_file_name
            im_data['image_size'] = im.image_size
            data['image_list'].append ( im_data )
        return data


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
        for key in [ "floatBased", "antialiased", "wheel_index", "scroll_factor", "zoom_scale", "last_button", "mdx", "mdy", "ldx", "ldy", "dx", "dy", "draw_border" ]:
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
        super(ZoomPanWidget, self).update()


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
        ex = event.x()
        ey = event.y()

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


    def wheelEvent(self, event):

        global project_data
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]
        global main_window
        global preloading_range

        kmods = event.modifiers()
        if ( int(kmods) & int(Qt.ShiftModifier) ) == 0:

            # Unshifted Scroll Wheel moves through layers
            layer_delta = int(event.delta()/120)

            if work_from_dict:

              if project_data != None:

                local_scales = project_data['data']['scales']
                local_current_scale = project_data['data']['current_scale']
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
                            if local_current_layer >= len(local_stack):
                                local_current_layer =  len(local_stack)-1
                            elif local_current_layer < 0:
                                local_current_layer = 0
                            # Store the final value
                            project_data['data']['current_layer'] = local_current_layer

                            # Define the images needed
                            needed_images = set()
                            for i in range(len(local_stack)):
                              if abs(i-local_current_layer) < preloading_range:
                                for role,local_image in local_stack[i]['images'].items():
                                  if len(local_image['filename']) > 0:
                                    needed_images.add ( local_image['filename'] )
                            # Ask the library to keep only those images
                            image_library.make_available ( needed_images )

                #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

                # if len(project_data['data']['scales'][local_current_layer]

                self.update_siblings()

            else:

                print_debug ( 50, "Wheel Event: Moving through the stack with alignment_layer_index = " + str(alignment_layer_index) )
                if len(alignment_layer_list) <= 0:
                  alignment_layer_index = 0
                  print_debug ( 60, " Index = " + str(alignment_layer_index) )
                else:
                  main_window.control_panel.distribute_all_layer_data ( [ al.control_panel_data for al in alignment_layer_list ] )
                  alignment_layer_list[alignment_layer_index].control_panel_data = main_window.control_panel.copy_self_to_data()
                  alignment_layer_index += layer_delta
                  if layer_delta > 0:
                    if alignment_layer_index >= len(alignment_layer_list):
                      alignment_layer_index =  len(alignment_layer_list)-1
                  elif layer_delta < 0:
                    if alignment_layer_index < 0:
                      alignment_layer_index = 0

                  if alignment_layer_list[alignment_layer_index].control_panel_data != None:
                    main_window.control_panel.copy_data_to_self(alignment_layer_list[alignment_layer_index].control_panel_data)
                  ##main_window.status.showMessage("File: " + alignment_layer_list[alignment_layer_index].image_file_name)

                  print_debug ( 80, "Images at layer " + str(alignment_layer_index) + " are:" )
                  for im in alignment_layer_list[alignment_layer_index].image_list:
                    print_debug ( 80, "   " + str(im.role) + ":   " + str(im.image_file_name) )

                # Unload images no longer needed
                for i in range(len(alignment_layer_list)):
                  if abs(i-alignment_layer_index) >= preloading_range:
                    alignment_layer_list[i].unload()

                # Load a new image as needed
                if len(alignment_layer_list) > 0:
                  if not alignment_layer_list[alignment_layer_index].isLoaded():
                    alignment_layer_list[alignment_layer_index].load()

                self.update_siblings()

        else:
            # Shifted Scroll Wheel zooms

            self.wheel_index += event.delta()/120
            self.zoom_to_wheel_at(event.x(), event.y())

        self.update_zpa_self()


    def paintEvent(self, event):
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]

        painter = QPainter(self)

        if True:

            if work_from_dict:

                if project_data != None:

                    s = project_data['data']['current_scale']
                    l = project_data['data']['current_layer']

                    if len(project_data['data']['scales']) > 0:
                        if len(project_data['data']['scales'][s]['alignment_stack']) > 0:

                            image_dict = project_data['data']['scales'][s]['alignment_stack'][l]['images']

                            if self.role in image_dict.keys():
                                ann_image = image_dict[self.role]
                                pixmap = image_library.get_image_reference(ann_image['filename'])

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

                # Draw the role
                painter.setPen(QPen(QColor(255,100,100,255), 5))
                painter.drawText(20, 30, self.role)

            else:

                print_debug ( 50, "Painting layer " + str(alignment_layer_index) )
                if len(alignment_layer_list) > 0:
                  if (alignment_layer_index >= 0) and (alignment_layer_index < len(alignment_layer_list)):

                    pixmap = None
                    for layer_image in alignment_layer_list[alignment_layer_index].image_list:
                      if layer_image.role == self.role:
                        pixmap = layer_image.pixmap

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

                # Draw the role
                painter.setPen(QPen(QColor(255,100,100,255), 5))
                painter.drawText(20, 30, self.role)


        else:
            painter.setRenderHint(QPainter.Antialiasing, self.antialiased)
            painter.translate(self.width() / 2, self.height() / 2)
            for diameter in range(0, 256, 9):
                delta = abs((self.wheel_index % 128) - diameter / 2)
                alpha = 255 - (delta * delta) / 4 - diameter
                if alpha > 0:
                    painter.setPen(QPen(QColor(0, diameter / 2, 127, alpha), 3))
                    if self.floatBased:
                        painter.drawEllipse(QRectF(-diameter / 2.0,
                                -diameter / 2.0, diameter, diameter))
                    else:
                        painter.drawEllipse(QRect(-diameter / 2,
                                -diameter / 2, diameter, diameter))



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
        self.bg_color = QColor(40,50,50,255)
        self.border_color = QColor(0,0,0,255)

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
      global global_panel_roles
      if len(roles_list) > 0:
        # Save these roles
        role_settings = {}
        for w in self.actual_children:
          if type(w) == ZoomPanWidget:
            role_settings[w.role] = w.get_settings()

        global_panel_roles = roles_list
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
          self.add_panel ( zpw )

    def remove_all_panels ( self, unused_checked ):
        print_debug ( 30, "In remove_all_panels" )
        while len(self.actual_children) > 0:
            self.hb_layout.removeWidget ( self.actual_children[-1] )
            self.actual_children[-1].deleteLater()
            self.actual_children = self.actual_children[0:-1]
        self.repaint()

    def center_all_images ( self ):
        print_debug ( 30, "In center_all_images" )
        for child in self.actual_children:
            pass # Not sure how to do this yet
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            #self.hb_layout.removeWidget ( self.actual_children[-1] )
            #self.actual_children[-1].deleteLater()
            #self.actual_children = self.actual_children[0:-1]
        self.repaint()


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

        global global_panel_roles
        global app
        if app == None:
                app = QApplication()

        global project_data
        project_data = copy.deepcopy ( new_project_template )

        QMainWindow.__init__(self)
        self.setWindowTitle(title)

        self.current_project_file_name = None
        self.project_open = None
        self.project_save = None
        self.generate_scales = None

        if panel_roles != None:
            global_panel_roles = panel_roles

        self.draw_border = False

        self.panel_list = []
        #if global_panel_roles != None:
        #  self.remove_all_panels(None)

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
        self.image_panel.setStyleSheet("background-color:black;")
        self.image_panel.setAutoFillBackground(True)

        self.main_panel_layout.addWidget ( self.image_panel )
        self.main_panel_layout.addWidget ( self.control_panel )

        self.destination_path = None


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
                  [ 'Set Destination...', None, self.set_destination, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'E&xit', 'Ctrl+Q', self.exit_app, None, None, None ]
                ]
              ],
              [ '&Images',
                [
                  [ 'Define Roles', None, self.define_roles_callback, None, None, None ],
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
                  # [ 'Center', None, self.center_all_images, None, None, None ],
                  [ 'Center', None, self.not_yet, None, None, None ],
                  # [ 'Actual Size', None, self.actual_size, None, None, None ],
                  [ 'Actual Size', None, self.not_yet, None, None, None ],
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
                  [ '&Generate Scales', None, self.generate_scales_callback, None, None, None ],
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
                  [ '-', None, None, None, None, None ],
                  [ 'Show Border', None, self.toggle_border, False, None, None ],
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
                  [ '-', None, None, None, None, None ],
                  [ 'Default Plot Code', None, self.not_yet, None, None, None ],
                  [ 'Custom Plot Code', None, self.not_yet, None, None, None ]
                ]
              ],
              [ '&Show',
                [
                  [ 'Window Centers', None, self.not_yet, False, None, None ],
                  [ 'Affines', None, self.not_yet, False, None, None ],
                  [ 'Skipped Images', None, self.not_yet, True, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Plot', None, self.not_yet, None, None, None ]
                ]
              ],
              [ '&Debug',
                [
                  [ '&Python Console', 'Ctrl+P', self.py_console, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Print Structures', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Print Affine',     None, self.not_yet, None, None, None ],
                  [ 'Print Structures', None, self.not_yet, None, None, None ],
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
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.resize(2000,1000)

        # self.setCentralWidget(self.image_hbox)
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


    def update_win_self ( self ):
        self.update()

    def register_project_open ( self, function ):
        self.project_open = function

    def register_project_save ( self, function ):
        self.project_save = function

    def register_gen_scales ( self, function ):
        self.generate_scales = function


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
        pass

    @Slot()
    def not_yet(self, checked):
        print_debug ( 30, "Function is not implemented yet" )

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
    def open_project(self, checked):
        if self.project_open == None:
            print_debug ( 1, "\n\nOpening Projects is unsupported\n\n" )
        else:
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

                    if work_from_dict:

                        f = open ( file_name, 'r' )
                        text = f.read()
                        f.close()

                        # Read the JSON file from the text
                        global project_data
                        project_data = json.loads ( text )

                        self.image_panel.update_multi_self()

                    else:

                        self.current_project_file_name = file_name

                        # Attempt to hide the file dialog before opening ...
                        for p in self.panel_list:
                            p.update_zpa_self()
                        # self.update_win_self()
                        self.project_open ( file_name )

    @Slot()
    def save_project(self, checked):
        if self.project_save == None:
            print_debug ( 1, "\n\nSaving Projects is unsupported (project_save not registered)\n\n" )
        elif self.current_project_file_name is None:
            self.save_project_as ( None )
        else:
            print_debug ( 1, "\n\n\nSaving Project\n\n\n" )
            self.project_save ( self.current_project_file_name )

    @Slot()
    def save_project_as(self, checked):
        if self.project_save == None:
            print_debug ( 1, "\n\nSaving Projects is unsupported (project_save not registered)\n\n" )
        else:
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
                    self.project_save ( file_name )


    @Slot()
    def actual_size(self, checked):
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
    def opt_n(self, option_name, option_action):
        if 'num' in dir(option_action):
          print_debug ( 50, "Dynamic Option[" + str(option_action.num) + "]: \"" + option_name + "\"" )
        else:
          print_debug ( 50, "Dynamic Option: \"" + option_name + "\"" )
        print_debug ( 50, "  Action: " + str(option_action) )


    def add_image_to_role ( self, image_file_name, role_name ):
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]

        print_debug ( 60, "Trying to place file " + str(image_file_name) + " in role " + str(role_name) )
        if image_file_name != None:
          if len(image_file_name) > 0:
            found_layer = None
            this_layer_index = 0

            if work_from_dict:

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

            else:

              for alignment_layer in alignment_layer_list:
                role_taken = False
                for image in alignment_layer.image_list:
                  print_debug ( 80, "Checking image role of " + image.role + " against role_name of " + str(role_name) )
                  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
                  if image.role == str(role_name):
                    role_taken = True
                    break
                print_debug ( 60, "Searched layer and role_taken = " + str(role_taken) )
                if not role_taken:
                  # Add the image here at this layer
                  found_layer = alignment_layer
                  break
                this_layer_index += 1
              if found_layer != None:
                # Add the image/role to the found layer
                print_debug ( 40, "Adding \"" + str(image_file_name) + "\" to layer " + str(this_layer_index) )
                found_layer.image_list.append ( AnnotatedImage ( str(role_name), image_file_name, load_now=(abs(this_layer_index-alignment_layer_index)<preloading_range) ) )
              else:
                # Add a new layer for the image
                print_debug ( 30, "Creating a new layer at " + str(this_layer_index) )
                alignment_layer_list.append ( DisplayLayer ( role_name, image_file_name, load_now=(abs(this_layer_index-alignment_layer_index)<preloading_range) ) )


    def add_empty_to_role ( self, role_name ):
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]

        # Find next layer with an empty role matching the requested role_name
        print_debug ( 60, "Trying to place file <empty> in role " + str(role_name) )
        found_layer = None
        this_layer_index = 0
        for alignment_layer in alignment_layer_list:
          role_taken = False
          for image in alignment_layer.image_list:
            print_debug ( 80, "Checking image role of " + image.role + " against role_name of " + str(role_name) )
            if image.role == str(role_name):
              role_taken = True
              break
          print_debug ( 60, "Searched layer and role_taken = " + str(role_taken) )
          if not role_taken:
            # Add the image here at this layer
            found_layer = alignment_layer
            break
          this_layer_index += 1
        if found_layer != None:
          # Add the image/role to the found layer
          print_debug ( 40, "Adding <empty> to layer " + str(this_layer_index) )
          found_layer.image_list.append ( AnnotatedImage ( str(role_name), None, load_now=0 ) )
        else:
          # Add a new layer for the image
          print_debug ( 30, "Creating a new layer at " + str(this_layer_index) )
          alignment_layer_list.append ( DisplayLayer ( role_name, None, load_now=0 ) )


    def import_images(self, role_to_import, file_name_list, clear_role=False ):
        global scale_list
        global scale_index
        global alignment_layer_index
        global preloading_range
        alignment_layer_list = scale_list[scale_index]

        print_debug ( 60, "import_images ( " + str(role_to_import) + ", " + str(file_name_list) + ")" )

        print_debug ( 30, "Importing images for role: " + str(role_to_import) )
        for f in file_name_list:
          print_debug ( 30, "   " + str(f) )
        print_debug ( 10, "Importing images for role: " + str(role_to_import) )

        if clear_role:
          for alignment_layer in alignment_layer_list:
            alignment_layer.image_list = [ i for i in alignment_layer.image_list if i.role != role_to_import ]

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

        #if len(alignment_layer_list) > 0:
        #    self.status.showMessage("File: " + alignment_layer_list[alignment_layer_index].image_file_name)


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

        self.destination_path = QFileDialog.getExistingDirectory ( parent=None, caption="Select Destination Directory", dir=self.destination_path, options=options)

        print_debug ( 1, "Destination is: " + str(self.destination_path) )




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

    @Slot()
    def define_roles_callback(self, checked):
        global global_panel_roles
        default_roles = ['ref','src','aligned']
        if len(global_panel_roles) > 0:
          default_roles = global_panel_roles
        input_val, ok = QInputDialog().getText ( None, "Define Roles", "Current: "+str(' '.join(default_roles)), echo=QLineEdit.Normal, text=' '.join(default_roles) )
        if ok:
          input_val = input_val.strip()
          roles_list = global_panel_roles
          if len(input_val) > 0:
            roles_list = [ str(v) for v in input_val.split(' ') if len(v) > 0 ]
          if not (roles_list == global_panel_roles):
            self.define_roles (roles_list)
        else:
          print_debug ( 30, "Cancel: Roles not changed" )


    @Slot()
    def import_into_role(self, checked):
        import_role_name = str ( self.sender().text() )
        self.import_images_dialog ( import_role_name )

    @Slot()
    def empty_into_role(self, checked):
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]

        role_to_import = str ( self.sender().text() )

        print_debug ( 30, "Adding empty for role: " + str(role_to_import) )

        # Find next layer with an empty role matching the requested role_to_import
        print_debug ( 60, "Trying to place file <empty> in role " + str(role_to_import) )
        found_layer = None
        this_layer_index = 0
        for alignment_layer in alignment_layer_list:
          role_taken = False
          for image in alignment_layer.image_list:
            print_debug ( 80, "Checking image role of " + image.role + " against role_to_import of " + str(role_to_import) )
            if image.role == str(role_to_import):
              role_taken = True
              break
          print_debug ( 60, "Searched layer and role_taken = " + str(role_taken) )
          if not role_taken:
            # Add the image here at this layer
            found_layer = alignment_layer
            break
          this_layer_index += 1
        if found_layer:
          # Add the image/role to the found layer
          print_debug ( 40, "Adding <empty> to layer " + str(this_layer_index) )
          found_layer.image_list.append ( AnnotatedImage ( str(role_to_import), None, load_now=0 ) )
        else:
          # Add a new layer for the image
          print_debug ( 30, "Creating a new layer at " + str(this_layer_index) )
          alignment_layer_list.append ( DisplayLayer ( role_to_import, None, load_now=0 ) )

        # Draw the panels ("windows")
        for p in self.panel_list:
            p.force_center = True
            p.update_zpa_self()

        self.update_win_self()



    def define_scales ( self, scales_list ):

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
                for scale in scales_list:
                  item = QAction ( str(scale), self )
                  item.setCheckable(True)
                  item.setChecked(first)
                  self.action_groups['Scales'].addAction(item)
                  item.triggered.connect ( self.set_current_scale )
                  m.addAction(item)
                  first = False


    @Slot()
    def define_scales_callback(self, checked):
        global global_image_scales
        default_scales = ['1']
        if len(global_image_scales) > 0:
          default_scales = global_image_scales
        input_val, ok = QInputDialog().getText ( None, "Define Scales", "Current: "+str(' '.join(default_scales)), echo=QLineEdit.Normal, text=' '.join(default_scales) )
        if ok:
          input_val = input_val.strip()
          scales_list = global_image_scales
          if len(input_val) > 0:
            scales_list = [ str(v) for v in input_val.split(' ') if len(v) > 0 ]
          if not (scales_list == global_image_scales):
            self.define_scales (scales_list)
            global_image_scales = scales_list
        else:
          print_debug ( 30, "Cancel: Scales not changed" )

    @Slot()
    def set_current_scale(self, checked):
        print ( "Set current Scale to " + str(self.sender().text()) )
        global current_scale
        current_scale = str ( self.sender().text() )

    @Slot()
    def generate_scales_callback(self, checked):
        if self.generate_scales != None:
            print ( "Generate the scales now" )
            self.generate_scales()


    @Slot()
    def remove_this_layer(self, checked):
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]
        alignment_layer_list = alignment_layer_list[0:alignment_layer_index] + alignment_layer_list[alignment_layer_index+1:]
        if alignment_layer_index > 0:
          alignment_layer_index += -1
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def remove_all_layers(self, checked):
        global scale_list
        global scale_index
        global alignment_layer_index
        alignment_layer_list = scale_list[scale_index]

        alignment_layer_index = 0
        while len(alignment_layer_list) > 0:
          self.remove_this_layer(checked)
        self.update_win_self()

    @Slot()
    def remove_all_panels(self, checked):
        print_debug ( 30, "Removing all panels" )
        if 'image_panel' in dir(self):
            print_debug ( 30, "image_panel exists" )
            self.image_panel.remove_all_panels(None)
        else:
            print_debug ( 30, "image_panel does not exit!!" )
        self.define_roles ( [] )
        self.update_win_self()


    @Slot()
    def set_max_image_size(self, checked):
        global max_image_file_size
        input_val, ok = QInputDialog().getInt ( None, "Enter Max Image File Size", "Max Image Size:", max_image_file_size )
        if ok:
          max_image_file_size = input_val

    @Slot()
    def set_bg_color(self, checked):
        c = QColorDialog.getColor()
        # print_debug ( 30, " Color = " + str(c) )
        self.image_panel.bg_color = c
        self.image_panel.update_multi_self()
        self.image_panel.repaint()
        alignment_layer_list = scale_list[scale_index]

        for p in self.panel_list:
            p.update_zpa_self()
            p.repaint()

    @Slot()
    def set_border_color(self, checked):
        c = QColorDialog.getColor()
        self.image_panel.border_color = c
        self.image_panel.update_multi_self()
        self.image_panel.repaint()
        for p in self.panel_list:
            p.border_color = c
            p.update_zpa_self()
            p.repaint()

    @Slot()
    def center_all_images(self, checked):
        self.image_panel.center_all_images()


    @Slot()
    def set_preloading_range(self, checked):
        global scale_list
        global scale_index
        global alignment_layer_index
        global preloading_range
        alignment_layer_list = scale_list[scale_index]

        input_val, ok = QInputDialog().getInt ( None, "Enter Number of Images to Preload", "Preloading Count:", preloading_range )
        if ok:
          preloading_range = input_val
          # Unload images to bring total down to preloading value
          for i in range(len(alignment_layer_list)):
            if abs(i-alignment_layer_index) >= preloading_range:
              alignment_layer_list[i].unload()

    @Slot()
    def exit_app(self, checked):
        sys.exit()

    @Slot()
    def py_console(self, checked):
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



test_option = None


def resize_images():

    print_debug ( 0, "Resizing Images with Test Option 1 ..." )

    adjusted_stack = []

    for layer in alignment_layer_list:

        baselist = [ im for im in layer.image_list if im.role == 'Original' ]
        if len(baselist) > 0:
            basename = baselist[0].image_file_name
            basedata = cv2.imread(basename, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)

            if basedata != None:

                scale_value = float(control_model[0][1][0].get_value())
                scaled_image = cv2.resize ( basedata, tuple([ int(x*scale_value) for x in basedata.shape ]), interpolation=cv2.INTER_AREA )

                # Write the adjusted data using to the proper directory
                path_parts = os.path.split(basename)
                if not os.path.exists ( os.path.join ( path_parts[0], 'adjusted' ) ):
                    # Create the scaled base subdirectory
                    os.mkdir ( os.path.join ( path_parts[0], 'adjusted' ) )
                adjusted_name = os.path.join ( path_parts[0], 'adjusted', path_parts[1] )

                print ( "Saving file: " + str(adjusted_name) )
                cv2.imwrite(adjusted_name, scaled_image)

                # Put the new image in the list to go into the aligned role
                adjusted_stack.append ( adjusted_name )

    # Remove the old images from the library
    for name in adjusted_stack:
        image_library.remove_image_reference ( name )

    # Load the updated images into the stack
    main_window.load_images_in_role ( 'Adjusted', adjusted_stack )


def adjust_brightness():

    print_debug ( 0, "Adjusting brightness with Test Option 2 ..." )

    adjusted_stack = []

    for layer in alignment_layer_list:

        baselist = [ im for im in layer.image_list if im.role == 'Original' ]
        if len(baselist) > 0:
            basename = baselist[0].image_file_name
            basedata = cv2.imread(basename, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)

            if basedata != None:

                scale_value = float(control_model[0][1][0].get_value())
                offset_value = float(control_model[0][1][2].get_value())

                f = numpy.array ( basedata, dtype=float )

                f = (scale_value * f) + offset_value

                # Write the adjusted data using to the proper directory
                path_parts = os.path.split(basename)
                if not os.path.exists ( os.path.join ( path_parts[0], 'adjusted' ) ):
                    # Create the scaled base subdirectory
                    os.mkdir ( os.path.join ( path_parts[0], 'adjusted' ) )
                adjusted_name = os.path.join ( path_parts[0], 'adjusted', path_parts[1] )

                print ( "Saving file: " + str(adjusted_name) )
                cv2.imwrite ( adjusted_name, numpy.array(f, dtype='uint8') )

                # Put the new image in the list to go into the aligned role
                adjusted_stack.append ( adjusted_name )

    # Remove the old images from the library
    for name in adjusted_stack:
        image_library.remove_image_reference ( name )

    # Load the updated images into the stack
    main_window.load_images_in_role ( 'Adjusted', adjusted_stack )


def align_all_2():

    print_debug ( 0, "Aligning All with AlignEM..." )
    print_debug ( 70, "Control Model = " + str(control_model) )

    scaled_base_stack = []
    scaled_ref_stack = []
    scaled_corr_stack = []
    aln_image_stack = []

    for layer in alignment_layer_list:
        basename = None
        baseimage = None
        basedata = None

        refname = None
        refimage = None
        refdata = None

        baselist = [ im for im in layer.image_list if im.role == 'base' ]
        if len(baselist) > 0:
            basename = baselist[0].image_file_name
            baseimage = baselist[0].pixmap # Not used yet
            basedata = cv2.imread(basename, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)

        reflist = [ im for im in layer.image_list if im.role == 'ref' ]
        if len(reflist) > 0:
            refname = reflist[0].image_file_name
            refimage = reflist[0].pixmap # Not used yet
            refdata = cv2.imread(refname, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)

        sbasedata = None
        srefdata = None

        if basedata != None:
            # There is an image to be aligned

            sbasedata = cv2.resize ( basedata, tuple([ x/int(scale_down_factor.get_value()) for x in basedata.shape ]), interpolation=cv2.INTER_AREA )

            if refdata == None:
                # Put an empty image on the stack
                scaled_ref_stack.append ( None )
                scaled_corr_stack.append ( None )
            else:
                # There is a reference, so align the base to the ref
                print ( "Aligning " + basename )
                print ( "    with " + refname )

                # Resize to show that it's actually working. Eventually use cv2.matchTemplate ?


                srefdata = cv2.resize ( refdata, tuple([ x/int(scale_down_factor.get_value()) for x in refdata.shape ]), interpolation=cv2.INTER_AREA )

                # Write out the aligned data using to the proper directory
                path_parts = os.path.split(refname)
                if not os.path.exists ( os.path.join ( path_parts[0], 'scaled_ref' ) ):
                    # Create the scaled base subdirectory
                    os.mkdir ( os.path.join ( path_parts[0], 'scaled_ref' ) )
                aligned_name = os.path.join ( path_parts[0], 'scaled_ref', path_parts[1] )

                print ( "Saving file: " + str(aligned_name) )
                cv2.imwrite(aligned_name, srefdata)

                # Put the new image in the list to go into the aligned role
                scaled_ref_stack.append ( aligned_name )

                #scorrdata = scipy.ndimage.correlate(srefdata, sbasedata)
                #scorrdata = scipy.ndimage.convolve(srefdata, sbasedata)
                # scorrdata = 255 + (sbasedata - srefdata)

                D = search_radius.get_value()
                results = []
                rows,cols = sbasedata.shape

                for drow in range(-D,D+1):
                    ref_start_row = 0
                    ref_end_row = rows
                    src_start_row = 0
                    src_end_row = rows
                    if drow > 0:
                        ref_start_row = drow
                        src_end_row = rows-drow
                    if drow < 0:
                        ref_end_row = rows+drow
                        src_start_row = -drow

                    row_res = []

                    for dcol in range(-D,D+1):
                        ref_start_col = 0
                        ref_end_col = cols
                        src_start_col = 0
                        src_end_col = cols
                        if dcol > 0:
                            ref_start_col = dcol
                            src_end_col = cols-dcol
                        if dcol < 0:
                            ref_end_col = cols+dcol
                            src_start_col = -dcol
                        subref = srefdata [ref_start_row:ref_end_row, ref_start_col:ref_end_col]
                        subsrc = sbasedata[src_start_row:src_end_row, src_start_col:src_end_col]

                        scorrdata = abs(((1.0*subref) - subsrc)/2) + 128

                        row_res.append ( int ( 1000 * scorrdata.min() / ( (ref_end_row-ref_start_row) * (ref_end_col-ref_start_col) ) ) )

                        #print ( "drow = " + str(drow) + "   dcol = " + str(dcol) )
                        #print ( "  Ref rows: " + str(ref_start_row) + " to " + str(ref_end_row) + "     Ref cols: " + str(ref_start_col) + " to " + str(ref_end_col) )
                        #print ( "  Src rows: " + str(src_start_row) + " to " + str(src_end_row) + "     Src cols: " + str(src_start_col) + " to " + str(src_end_col) )

                    results.append ( row_res )

                print ( 100*'*' )
                for r in results:
                  print ( "  " + str(r) )
                print ( 100*'*' )

                #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

                # Write out the aligned data using to the proper directory
                path_parts = os.path.split(refname)
                if not os.path.exists ( os.path.join ( path_parts[0], 'scaled_corr' ) ):
                    # Create the scaled base subdirectory
                    os.mkdir ( os.path.join ( path_parts[0], 'scaled_corr' ) )
                aligned_name = os.path.join ( path_parts[0], 'scaled_corr', path_parts[1] )

                print ( "Saving file: " + str(aligned_name) )
                cv2.imwrite(aligned_name, scorrdata)

                # Put the new image in the list to go into the aligned role
                scaled_corr_stack.append ( aligned_name )


            # Write out the aligned data using to the proper directory
            path_parts = os.path.split(basename)
            if not os.path.exists ( os.path.join ( path_parts[0], 'scaled_base' ) ):
                # Create the scaled base subdirectory
                os.mkdir ( os.path.join ( path_parts[0], 'scaled_base' ) )
            aligned_name = os.path.join ( path_parts[0], 'scaled_base', path_parts[1] )

            print ( "Saving file: " + str(aligned_name) )
            cv2.imwrite(aligned_name, sbasedata)


            # Put the new image in the list to go into the aligned role
            scaled_base_stack.append ( aligned_name )

    # Purge the old images from the library
    for name in aln_image_stack:
        image_library.remove_image_reference ( name )
    for name in scaled_base_stack:
        image_library.remove_image_reference ( name )
    for name in scaled_ref_stack:
        image_library.remove_image_reference ( name )
    for name in scaled_corr_stack:
        image_library.remove_image_reference ( name )

    # Load the updated images into the stack
    main_window.load_images_in_role ( 'sref', scaled_ref_stack )
    main_window.load_images_in_role ( 'sbase', scaled_base_stack )
    main_window.load_images_in_role ( 'scorr', scaled_corr_stack )


def local_debug():
  print ( "In alignem" )
  __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


scale_down_factor = IntField ( "Scale Down Factor:", 16, all_layers=1 )
search_radius = IntField ( "Search Radius (in pixels):", 20, all_layers=1 )

control_model = None

# This provides default command line parameters if none are given (as with "Idle")
#if len(sys.argv) <= 1:
#    sys.argv = [ __file__, "-f", "vj_097_1k1k_1.jpg" ]

if __name__ == "__main__":

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-t", "--test", type=int, required=False, help="Run test case: TEST (currently 1 or 2)")
    args = options.parse_args()
    try:
        debug_level = int(args.debug)
    except:
        pass
    try:
        test_option = int(args.test)
    except:
        pass

    if test_option is None:

        control_model = [
          # Panes
          [ # Begin first pane
            [ "Program: " + __file__ ],
            [ "No Control Panel Data Defined." ]
          ] # End first pane
        ]

        main_window = MainWindow ( control_model=control_model )
        main_window.resize(2400,1000)

        main_window.define_roles ( ['Image Stack'] )


    elif test_option in [1, 2]:

        # All of these test options share the same original image files

        ref_image_stack = [ None,
                            "vj_097_shift_rot_skew_crop_1k1k_1.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_2.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_3.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_4.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_5.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_6.jpg" ]

        src_image_stack = [ "vj_097_shift_rot_skew_crop_1k1k_1.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_2.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_3.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_4.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_5.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_6.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_7.jpg" ]

        if test_option == 1:

            control_model = [
              # Panes
              [ # Begin first pane
                [ "Program \"" + __file__ + "\":   Scaling" ],
                [ FloatField("Scale Image Size by: ", 1.0, all_layers=1), "  ", CallbackButton('Apply', resize_images) ]
              ] # End first pane
            ]

            main_window = MainWindow ( control_model=control_model )
            main_window.resize(2400,1000)

            main_window.define_roles ( ['Original','Adjusted'] )

            main_window.load_images_in_role ( 'Original', src_image_stack )

        if test_option == 2:

            control_model = [
              # Panes
              [ # Begin first pane
                [ "Program \"" + __file__ + "\":   Brightness" ],
                [ FloatField("Scale Brightness: ", 1.0, all_layers=1), 10*" ", FloatField("Offset Brightness: ", 0.0, all_layers=1), "  ", CallbackButton('Apply', adjust_brightness) ]
              ] # End first pane
            ]

            main_window = MainWindow ( control_model=control_model )
            main_window.resize(2400,1000)

            main_window.define_roles ( ['Original','Adjusted'] )

            main_window.load_images_in_role ( 'Original', src_image_stack )

        elif test_option == 3:

            control_model = [
              # Panes
              [ # Begin first pane
                [ "Program:", 6*" ", __file__ ],
                [ scale_down_factor, 6*" " ], #, FloatField("Floating Point:",2.3), 6*" ", BoolField("Boolean",False) ],
                [ search_radius, 6*" " ], #, FloatField("Floating Point:",2.3), 6*" ", BoolField("Boolean",False) ],
                [ TextField("String:","Default text"), 20*" ", CallbackButton('Align All', align_all_2), CallbackButton('Debug', local_debug) ]
              ] # End first pane
            ]

            main_window = MainWindow ( control_model=control_model )
            main_window.resize(2400,1000)

            main_window.define_roles ( ['ref','base','align'] )

            main_window.define_roles ( ['ref','base','sref', 'sbase', 'scorr'] )

            main_window.load_images_in_role ( 'ref', ref_image_stack )
            main_window.load_images_in_role ( 'base', src_image_stack )


    else:

      print ( "Undefined test option: " + str(test_option) + ", try --help option." )
      exit(99)


    main_window.show()
    sys.exit(app.exec_())

