"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""

import sys, traceback
import os
import argparse
import copy

import threading

from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
from PySide2.QtWidgets import QAction, QActionGroup, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox
from PySide2.QtWidgets import QMenu, QColorDialog, QMessageBox, QComboBox
from PySide2.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor
from PySide2.QtCore import Slot, QRect, QRectF, QSize, Qt, QPoint, QPointF

current_image_info_list = []
current_image_index = 0

# This is monotonic (0 to 100) with the amount of output:
debug_level = 0  # A larger value prints more stuff

# Use the limited argument version to be compatible with Python 2
def print_debug ( level, p1=None, p2=None, p3=None, p4=None ):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
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

preloading_range = 3
max_image_file_size = 1000000000

main_window = None


def show_warning ( title, text ):
    QMessageBox.warning ( None, title, text )

def request_confirmation ( title, text ):
    button = QMessageBox.question ( None, title, text )
    print ( "You clicked " + str(button) )
    print ( "Returning " + str(button == QMessageBox.StandardButton.Yes))
    return ( button == QMessageBox.StandardButton.Yes )



def load_image_worker ( real_norm_path, image_dict ):
    # Load the image
    print ( "load_image_worker started with: \"" + str(real_norm_path) + "\"" )
    image_dict['image'] = QPixmap(real_norm_path)
    image_dict['loaded'] = True
    image_dict['loading'] = False
    print ( "load_image_worker finished for: \"" + str(real_norm_path) + "\"" )
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
        print_debug ( 4, " Library has " + str(len(self._images.keys())) + " images" )
        print_debug ( 30, "  Names:   " + str(sorted([str(s[-7:]) for s in self._images.keys()])) )
        print_debug ( 6, "  Loaded:  " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loaded']])) )
        print_debug ( 6, "  Loading: " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loading']])) )

    def __str__ (self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        for k,v in self._images.items():
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"
        print ( s )
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return ( s )

    def get_image_reference ( self, file_path ):
        print_debug ( 4, "get_image_reference ( " + str(file_path) + " )" )
        self.print_load_status()
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                print_debug ( 4, "  Image name is in the library" )
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    print_debug ( 4, "  Image was already loaded" )
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
        print_debug ( 4, "  start queue_image_read with: \"" + str(real_norm_path) + "\"" )
        self._images[real_norm_path] = { 'image': None, 'loaded': False, 'loading': True, 'task':None }
        t = threading.Thread ( target = load_image_worker, args = (real_norm_path,self._images[real_norm_path]) )
        t.start()
        self._images[real_norm_path]['task'] = t
        print_debug ( 4, "  finished queue_image_read with: \"" + str(real_norm_path) + "\"" )

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

        print_debug ( 4, "make_available: " + str(sorted([str(s[-7:]) for s in requested])) )
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

image_library = ImageLibrary()


class ZoomPanWidget(QWidget):
    """A widget to display a single annotated image with zooming and panning."""
    def __init__(self, role, parent=None):
        super(ZoomPanWidget, self).__init__(parent)
        self.role = role
        self.parent = None

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
        print_debug ( 30, "Showing actual size image" )
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        self.zoom_to_wheel_at ( 0, 0 )


    def center_image ( self ):
        print_debug ( 30, "Centering images" )

        if len(current_image_info_list) > 0:

            pixmap = image_library.get_image_reference(current_image_info_list[current_image_index]['file_name'])
            if pixmap != None:
                img_w = pixmap.width()
                img_h = pixmap.height()
                win_w = self.width()
                win_h = self.height()

                if (img_w<=0) or (img_h<=0) or (win_w<=0) or (win_h<=0):  # Zero or negative dimensions might lock up?

                    print_debug ( 11, "Warning: Image or Window dimension is zero - cannot center image" )

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

        print_debug ( 30, "Done centering image" )


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
        global main_window
        global preloading_range
        global current_image_info_list
        global current_image_index

        if len(current_image_info_list) <= 0:
          current_image_index = 0
        else:
          # Adjust the current layer
          new_current_layer = current_image_index + layer_delta
          # Apply limits (top and bottom of stack)
          if new_current_layer >= len(current_image_info_list):
              new_current_layer =  len(current_image_info_list)-1
          elif new_current_layer < 0:
              new_current_layer = 0
          # Only set the global value after the limits have been applied
          current_image_index = new_current_layer

          # Define the images needed
          needed_images = set()
          for i in range(len(current_image_info_list)):
            print_debug ( 60, "Check if " + str(i) + " is in the preloading range of " + str(preloading_range) )
            if abs(i-current_image_index) < preloading_range:
                image_name_to_add = current_image_info_list[i]['file_name']
                needed_images.add ( image_name_to_add )
          # Ask the library to keep only those images
          image_library.make_available ( needed_images )
          self.update_zpa_self()
          self.update_siblings()



    def wheelEvent(self, event):

        global main_window

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

        img_text = None

        print_debug ( 15, "\nCurrent image index = " + str(current_image_index) )
        for f in current_image_info_list:
            print_debug ( 60, "  Image: " + str(f) )

        if len(current_image_info_list) > 0:

            pixmap = image_library.get_image_reference(current_image_info_list[current_image_index]['file_name'])
            # img_text = ann_image['filename']
            img_text = current_image_info_list[current_image_index]['file_name']

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

            if self.draw_annotations:
                painter.setPen (QPen (QColor (128, 255, 128, 255), 5))
                painter.drawText (painter.viewport().width()-100, 20, "%dx%d" % (pixmap.width (), pixmap.height ()))

        if self.draw_annotations:
            if img_text != None:
                # Draw the image name
                painter.setPen(QPen(QColor(100,100,255,255), 5))
                if self.draw_full_paths:
                    painter.drawText(10, 40, img_text)
                else:
                    if os.path.sep in img_text:
                        # Only split the path if it's splittable
                        painter.drawText(10, 20, os.path.split(img_text)[-1])
                    else:
                        painter.drawText(10, 20, img_text)

        painter.end()
        del painter



class MultiImagePanel(QWidget):

    def __init__(self):
        super(MultiImagePanel, self).__init__()

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
            painter.drawText((self.width()/2)-140, self.height()/2, " No Images")
        else:
            # Draw background for panels
            painter.fillRect(0,0,self.width(),self.height(),self.bg_color)
        painter.end()

    def update_spacing ( self ):
        print_debug ( 30, "Setting Spacing to " + str(self.current_margin) )
        self.hb_layout.setMargin(self.current_margin)    # This sets margins around the outer edge of all panels
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



def console():
    print_debug ( 0, "\n\n\nPython Console:\n" )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



# MainWindow contains the Menu Bar and the Status Bar
class MainWindow(QMainWindow):

    def __init__(self, fname=None, panel_roles=None, title="Align EM"):

        global app
        global debug_level
        if app == None:
                app = QApplication([])

        QMainWindow.__init__(self)
        self.setWindowTitle(title)

        self.current_project_file_name = None

        self.mouse_down_callback = None
        self.mouse_move_callback = None

        self.draw_border = False
        self.draw_annotations = True
        self.draw_full_paths = False

        self.panel_list = []

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

        self.setCentralWidget(self.main_panel)


        # Menu Bar
        self.action_groups = {}
        self.menu = self.menuBar()
        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
              [ '&Images',
                [
                  [ 'Import &Images', None, self.import_base_images, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Center', None, self.center_all_images, None, None, None ],
                  [ 'Actual Size', None, self.all_images_actual_size, None, None, None ],
                  [ 'Refresh', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Remove this Layer', None, self.remove_this_layer, None, None, None ],
                  [ 'Remove ALL Layers', None, self.remove_all_layers, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'E&xit', 'Ctrl+Q', self.exit_app, None, None, None ]
                ]
              ],
              [ '&Set',
                [
                  [ '&Max Image Size', 'Ctrl+M', self.set_max_image_size, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Num to Preload', None, self.set_preloading_range, None, None, None ],
                  [ 'Threaded Loading', None, self.toggle_threaded_loading, image_library.threaded_loading_enabled, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Background Color', None, self.set_bg_color, None, None, None ],
                  [ 'Border Color', None, self.set_border_color, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Unlimited Zoom', None, self.not_yet, False, None, None ],
                  [ 'Reverse Arrow Keys', None, self.toggle_arrow_direction, False, None, None ],
                  [ '-', None, None, None, None, None ]
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
                      [ 'Level 10',  None, self.set_debug_level, debug_level==10,  "DebugLevel", 10 ],
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
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.resize(800,600)

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
            print_debug ( 5, "Changing Debug Level from " + str(debug_level) + " to " + str(value) )
            debug_level = value
        except:
            print_debug ( 1, "Invalid debug value in: \"" + str(action_text) )

    @Slot()
    def print_structures(self, checked):
        global debug_level
        global current_image_info_list
        global current_image_index
        print ( "\n\nInternal Structures:")
        for f in current_image_info_list:
            print ( "  Image List contains: " + str(f) )
        print ( str(image_library) )
        print ( "  Current image index = " + str(current_image_index) )

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

    def update_panels(self):
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()


    @Slot()
    def import_images_dialog(self):

        global current_image_info_list
        global current_image_index

        print_debug ( 5, "Import images dialog" )

        view_at_0 = False
        if len(current_image_info_list) == 0:
            view_at_0 = True

        options = QFileDialog.Options()

        file_name_list, filtr = QFileDialog.getOpenFileNames ( None,  # None was self
                                                               "Select Images to Import",
                                                               #self.openFileNameLabel.text(),
                                                               "Select Images",
                                                               "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)", "", options)

        print_debug ( 60, "import_images_dialog ( " + str(file_name_list) + ")" )

        if current_image_index >= len(current_image_info_list):
            current_image_index = len(current_image_info_list) - 1

        for f in file_name_list:
            current_image_info_list.insert ( current_image_index+1, {'file_name':f, 'loaded':False, 'image':None} )
            current_image_index += 1

        if view_at_0:
            current_image_index = 0

        for p in self.panel_list:
          p.force_center = True
          p.update_zpa_self()

        self.update_win_self()



    def import_base_images ( self ):
        self.import_images_dialog()


    @Slot()
    def remove_this_layer(self):
        global current_image_info_list
        global current_image_index
        current_image_info_list.pop ( current_image_index )
        if current_image_index >= len(current_image_info_list):
            current_image_index = len(current_image_info_list) - 1

        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def remove_all_layers(self):
        global current_image_info_list
        global current_image_index
        current_image_index = 0
        current_image_info_list = []
        self.update_win_self()

    @Slot()
    def remove_all_panels(self):
        print_debug ( 30, "Removing all panels" )
        if 'image_panel' in dir(self):
            print_debug ( 30, "image_panel exists" )
            self.image_panel.remove_all_panels()
        else:
            print_debug ( 30, "image_panel does not exit!!" )
        self.image_panel.set_roles ( [] )

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
          image_library.update()


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


if __name__ == "__main__":

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, default=10, help="Print more information with larger DEBUG (0 to 100)")
    # options.add_argument("-t", "--test", type=int, required=False, help="Run test case: TEST")
    args = options.parse_args()
    try:
        debug_level = int(args.debug)
    except:
        pass

    main_window = MainWindow()
    main_window.resize(800,600)

    main_window.image_panel.set_roles ( ['Stack'] )

    main_window.show()
    sys.exit(app.exec_())

