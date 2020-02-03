import sys
import os
import argparse
import cv2

from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
from PySide2.QtWidgets import QAction, QActionGroup, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox
from PySide2.QtWidgets import QMenu
from PySide2.QtGui import QPixmap, QColor, QPainter, QPalette, QPen, QCursor
from PySide2.QtCore import Slot, qApp, QRect, QRectF, QSize, Qt, QPoint, QPointF


# Get the path of ../../python
alignem_file = os.path.abspath(__file__)
alignem_p    = os.path.dirname( alignem_file )
alignem_pp   = os.path.dirname( alignem_p )
alignem_shared_path = os.path.join ( alignem_pp, 'python' )

if len(sys.path) <= 0:
  # Add the path to the currently empty path (this would be an unusual case)
  sys.path.append ( swift_shared_path )
else:
  # Add the path in the second position (after the default current directory of "")
  sys.path.insert ( 1, alignem_shared_path )

# Import project and alignment support from SWiFT-IR:

import swift_project


debug_level = 10
def print_debug ( level, str ):
  global debug_level
  if level <= debug_level:
    print ( str )


app = None

preloading_range = 5
max_image_file_size = 1000000000

alignment_layer_list = []
alignment_layer_index = 0

main_window = None

class ImageLibrary:
    def __init__ ( self ):
        self.images = {}

    def get_image_reference ( self, file_path ):
        image_ref = None
        real_norm_path = os.path.realpath(os.path.normpath(file_path))
        if real_norm_path in self.images:
            image_ref = self.images[real_norm_path]
        else:
            print_debug ( 10, "Loading image: \"" + real_norm_path + "\"" )
            self.images[real_norm_path] = QPixmap(real_norm_path)
            image_ref = self.images[real_norm_path]
        return ( image_ref )

    def remove_image_reference ( self, file_path ):
        image_ref = None
        real_norm_path = os.path.realpath(os.path.normpath(file_path))
        if real_norm_path in self.images:
            print_debug ( 10, "Unloading image: \"" + real_norm_path + "\"" )
            image_ref = self.images.pop(real_norm_path)
        return ( image_ref )

image_library = ImageLibrary()

class AnnotatedImage:
    def __init__ ( self, role, file_name, load_now=False ):
        self.role = role
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

    def unload ( self ):
        global alignment_layer_list
        global image_library
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

import_role_name = "src"
global_panel_roles=['ref','src','aligned']

class DisplayLayer:
    def __init__ ( self, file_name, load_now=False ):
        global import_role_name
        self.image_list = []
        self.image_list.append ( AnnotatedImage ( str(import_role_name), file_name, load_now ) )

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


class ZoomPanWidget(QWidget):
    def __init__(self, role, parent=None, fname=None):
        super(ZoomPanWidget, self).__init__(parent)
        self.role = role

        # This seems to be ignored here: self.setStyleSheet("background-color:green;")

        global alignment_layer_list
        global alignment_layer_index

        self.parent = parent

        if fname != None:
          alignment_layer_list.append ( DisplayLayer ( fname, load_now=True ) )

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

        # self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update ( self ):
        # The update will be called on a particular ZoomPanWidget (this "self")
        # Call the super "update" function for this panel's QWidget (this "self")
        super(ZoomPanWidget, self).update()
        # Call the super "update" functions for the other panels' QWidgets (their "panel")
        print ( "Update called, calling siblings" )
        if self.parent.panel_list != None:
            print ( "  Hava a parent list" )
            for panel in self.parent.panel_list:
                print ( "    Hava a sibling" )
                if panel != self:
                    super(ZoomPanWidget, panel).update()


    def image_x ( self, win_x ):
        img_x = (win_x/self.zoom_scale) - self.ldx
        return ( img_x )

    def image_y ( self, win_y ):
        img_y = (win_y/self.zoom_scale) - self.ldy
        return ( img_y )

    def dump(self):
        print ( "wheel = " + str(self.wheel_index) )
        print ( "zoom = " + str(self.zoom_scale) )
        print ( "ldx  = " + str(self.ldx) )
        print ( "ldy  = " + str(self.ldy) )
        print ( "mdx  = " + str(self.mdx) )
        print ( "mdy  = " + str(self.mdy) )
        print ( " dx  = " + str(self.dx) )
        print ( " dy  = " + str(self.dy) )

    def setFloatBased(self, floatBased):
        self.floatBased = floatBased
        self.update()

    def setAntialiased(self, antialiased):
        self.antialiased = antialiased
        self.update()

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
        self.update()

    def mouseMoveEvent(self, event):
        if self.last_button == Qt.MouseButton.LeftButton:
            self.dx = (event.x() - self.mdx) / self.zoom_scale
            self.dy = (event.y() - self.mdy) / self.zoom_scale
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.ldx = self.ldx + self.dx
            self.ldy = self.ldy + self.dy
            self.dx = 0
            self.dy = 0
            self.update()

    def mouseDoubleClickEvent(self, event):
        print_debug ( 50, "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()) )
        self.update()

    def wheelEvent(self, event):

        global alignment_layer_list
        global alignment_layer_index
        global main_window
        global preloading_range

        kmods = event.modifiers()
        if ( int(kmods) & int(Qt.ShiftModifier) ) == 0:
            # Unshifted Scroll Wheel moves through layers
            layer_delta = int(event.delta()/120)

            print_debug ( 50, "Wheel Event: Moving through the stack with alignment_layer_index = " + str(alignment_layer_index) )
            if len(alignment_layer_list) <= 0:
              alignment_layer_index = 0
              print_debug ( 60, " Index = " + str(alignment_layer_index) )
            else:
              alignment_layer_index += layer_delta
              if layer_delta > 0:
                if alignment_layer_index >= len(alignment_layer_list):
                  alignment_layer_index =  len(alignment_layer_list)-1
              elif layer_delta < 0:
                if alignment_layer_index < 0:
                  alignment_layer_index = 0
              ##main_window.status.showMessage("File: " + alignment_layer_list[alignment_layer_index].image_file_name)

            # Unload images no longer needed
            for i in range(len(alignment_layer_list)):
              if abs(i-alignment_layer_index) >= preloading_range:
                alignment_layer_list[i].unload()

            # Load a new image as needed
            if len(alignment_layer_list) > 0:
              if not alignment_layer_list[alignment_layer_index].isLoaded():
                alignment_layer_list[alignment_layer_index].load()

            self.update()


        else:
            # Shifted Scroll Wheel zooms
            self.wheel_index += event.delta()/120

            mouse_win_x = event.x()
            mouse_win_y = event.y()

            old_scale = self.zoom_scale
            new_scale = self.zoom_scale = pow (self.scroll_factor, self.wheel_index)

            self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale)
            self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale)

        self.update()


    def paintEvent(self, event):
        global alignment_layer_list
        global alignment_layer_index

        painter = QPainter(self)

        if True:
            print_debug ( 50, "Painting layer " + str(alignment_layer_index) )
            if len(alignment_layer_list) > 0:
              if (alignment_layer_index >= 0) and (alignment_layer_index < len(alignment_layer_list)):

                pixmap = None
                for layer_image in alignment_layer_list[alignment_layer_index].image_list:
                  if layer_image.role == self.role:
                    pixmap = layer_image.pixmap


                # pixmap = alignment_layer_list[alignment_layer_index].pixmap
                if pixmap != None:
                    painter.scale ( self.zoom_scale, self.zoom_scale )
                    if self.draw_border:
                        # Draw an optional border around the image
                        painter.setPen(QPen(QColor(255, 255, 255, 255),4))
                        painter.drawRect ( QRectF ( self.ldx+self.dx, self.ldy+self.dy, pixmap.width(), pixmap.height() ) )
                    painter.drawPixmap ( QPointF(self.ldx+self.dx,self.ldy+self.dy), pixmap )
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



class ControlPanelWidget(QWidget):

    def __init__(self, control_model=None):
        super(ControlPanelWidget, self).__init__()
        self.cm = control_model
        #self.control_panel = QWidget()
        self.control_panel_layout = QVBoxLayout()
        self.setLayout(self.control_panel_layout)

        if self.cm != None:
            # Only show the first pane for now
            rows = control_model[0]
            print ( "Pane contains " + str(len(rows)) + " rows" )

            for row in rows:
              row_box = QWidget()
              row_box_layout = QHBoxLayout()
              row_box.setLayout ( row_box_layout )
              print ( "Row contains " + str(len(row)) + " items" )
              for item in row:
                  print ( "  Item is " + str(item) )
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
                  elif isinstance(item, IntField):
                      if item.text != None:
                          row_box_layout.addWidget ( QLabel ( str(item.text) ) )
                      val_widget = ( QLineEdit ( str(item.value) ) )
                      val_widget.setAlignment(Qt.AlignHCenter)
                      row_box_layout.addWidget ( val_widget )
                  elif isinstance(item, FloatField):
                      if item.text != None:
                          row_box_layout.addWidget ( QLabel ( str(item.text) ) )
                      val_widget = ( QLineEdit ( str(item.value) ) )
                      val_widget.setAlignment(Qt.AlignHCenter)
                      row_box_layout.addWidget ( val_widget )
                  elif isinstance(item, CallbackButton):
                      item_widget = QPushButton ( str(item.text) )
                      item_widget.clicked.connect ( item.callback )
                      row_box_layout.addWidget ( item_widget )
                  else:
                      item_widget = QLineEdit ( str(item) )
                      item_widget.setAlignment(Qt.AlignHCenter)
                      row_box_layout.addWidget ( item_widget )
              self.control_panel_layout.addWidget ( row_box )

        #self.control_panel_layout.addWidget ( QLabel ( "Control Panel Line 1" ) )
        #self.control_panel_layout.addWidget ( QLabel ( "Control Panel Line 2" ) )

class GenericWidget:
    def __init__ ( self, text ):
        self.text = text

class GenericField(GenericWidget):
    def __init__ ( self, text, value ):
        #super(None,self).__init__(text)
        #super(GenericField,self).__init__(text)
        self.text = text  # Should be handled by super, but fails in Python2
        self.value = value

class TextField(GenericField):
    pass

class BoolField(GenericField):
    pass

class IntField(GenericField):
    pass

class FloatField(GenericField):
    pass

class CallbackButton(GenericWidget):
    def __init__ ( self, text, callback ):
        #super(CallbackButton,self).__init__(text)
        self.text = text  # Should be handled by super, but fails in Python2
        self.callback = callback

def align_forward():
    print ( "Aligning Forward ..." )


# MainWindow contains the Menu Bar and the Status Bar
class MainWindow(QMainWindow):

    def __init__(self, fname=None, panel_roles=None, control_model=None):

        global global_panel_roles
        global app
        if app == None:
                app = QApplication()

        QMainWindow.__init__(self)
        self.setWindowTitle("Align EM")

        if panel_roles != None:
            global_panel_roles = panel_roles

        self.draw_border = False

        self.init_panels(cm=control_model)

        # Menu Bar
        self.action_groups = {}
        self.menu = self.menuBar()
        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
              [ '&File',
                [
                  [ '&New Project', 'Ctrl+N', self.not_yet, None, None, None ],
                  [ '&Open Project', 'Ctrl+O', self.not_yet, None, None, None ],
                  [ '&Save Project', 'Ctrl+S', self.not_yet, None, None, None ],
                  [ 'Save Project &As', 'Ctrl+A', self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Set Destination...', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'E&xit', 'Ctrl+Q', self.exit_app, None, None, None ]
                ]
              ],
              [ '&Images',
                [
                  #[ '&Import...', None, self.import_images, None, None, None ],
                  [ 'Define Roles', None, self.define_roles, None, None, None ],
                  [ '&Import into',
                    [
                      [ 'New Role',  None, self.import_images_new_role, None, None, None ],
                      [ 'Selected Role',  None, self.import_images_selected_role, None, None, None ]
                    ]
                  ],
                  [ '-', None, None, None, None, None ],
                  [ 'Center', None, self.not_yet, None, None, None ],
                  [ 'Actual Size', None, self.actual_size, None, None, None ],
                  [ 'Refresh', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Remove this Layer', None, self.remove_this_layer, None, None, None ],
                  # [ 'Remove ALL Layers', None, self.remove_all_layers, None, None, None ],
                  [ 'Remove ALL Panels', None, self.remove_all_panels, None, None, None ]
                ]
              ],
              [ '&Scaling',
                [
                  [ '&Define Scales', None, self.not_yet, None, None, None ],
                  [ '&Generate All Scales', None, self.not_yet, None, None, None ],
                  [ '&Import All Scales', None, self.not_yet, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ '&Generate Tiled', None, self.not_yet, False, None, None ],
                  [ '&Import Tiled', None, self.not_yet, False, None, None ],
                  [ '&Show Tiled', None, self.not_yet, False, None, None ]
                ]
              ],
              [ '&Scales',
                [
                  [ '&Scale 1', None, self.not_yet, True, "Scales", None ]
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
                  #[ 'Unlimited Zoom', None, self.not_yet, None, None, None ],
                  #[ '-', None, None, None, None, None ],
                  [ 'Num to Preload', None, self.set_preloading_range, None, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Show Border', None, self.toggle_border, False, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Perform Swims', None, self.not_yet, True, None, None ],
                  [ 'Update CFMs', None, self.not_yet, True, None, None ],
                  [ 'Generate Images', None, self.not_yet, True, None, None ],
                  [ '-', None, None, None, None, None ],
                  [ 'Use C Version', None, self.not_yet, False, None, None ],
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
        self.setMinimumWidth(1400)
        self.setMinimumHeight(1024)

        # self.setCentralWidget(self.image_hbox)
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})




    def init_panels (self, cm=None, fname=None):
        self.panel_list = []
        global global_panel_roles
        if global_panel_roles != None:
          self.remove_all_panels(None)
          for r in global_panel_roles:
            zpw = ZoomPanWidget(role=r, parent=self, fname=fname)
            zpw.draw_border = self.draw_border
            self.panel_list.append ( zpw )

        self.control_model = cm

        if self.control_model == None:
          # Use the default control model
          self.control_model = [
            # Panes
            [ # Begin first pane
              # Rows
              [ # Begin first row
                # Items
                "File Name: junk.txt",  # A string by itself is just a label
                "Layer: 5"  # A string by itself is just a label
              ], # End first row
              [ # Begin second row
                # Items
                "X:",  1.1,
                "      ",
                "Y: ", 2.2,
                "      ",
                "Z: ", 3.3
              ], # End second row
              [ # Begin third row
                # Items
                "a: ", 1010,
                "      ",
                "b: ", 1011,
                "      ",
                "c: ", 1100,
                "      ",
                "d: ", 1101,
                "      ",
                "e: ", 1110,
                "      ",
                "f: ", 1111
              ], # End third row
              [ # Begin fourth row
                # Items
                ['Align All'],
                "      ",
                CallbackButton('Align Forward', align_forward),
                "      ",
                "# Forward", 1
              ] # End fourth row
            ] # End first pane
          ]

        self.control_panel = ControlPanelWidget(self.control_model)

        self.image_hbox = QWidget()
        self.image_hbox.setStyleSheet("background-color:black;")
        self.image_hbox_layout = QHBoxLayout()
        for p in self.panel_list:
            self.image_hbox_layout.addWidget ( p )
        self.image_hbox.setLayout(self.image_hbox_layout)

        self.main_panel = QWidget()
        self.main_panel_layout = QVBoxLayout()
        self.main_panel.setLayout ( self.main_panel_layout )

        self.main_panel_layout.addWidget ( self.image_hbox )
        self.main_panel_layout.addWidget ( self.control_panel )


        self.setCentralWidget(self.main_panel)



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
              if item[3] != None:
                action.setCheckable(True)
                action.setChecked(item[3])
              if item[4] != None:
                self.action_groups[item[4]].addAction(action)

              parent.addAction ( action )

    @Slot()
    def not_yet(self, checked):
        print ( "Function is not implemented yet" )

    @Slot()
    def set_debug_level(self, checked):
        global debug_level
        action_text = self.sender().text()
        try:
            value = int(action_text.split(' ')[1])
            print ( "Changing Debug Level from " + str(debug_level) + " to " + str(value) )
            debug_level = value
        except:
            print ( "Invalid debug value in: \"" + str(action_text) )


    @Slot()
    def actual_size(self, checked):
        print_debug ( 90, "Setting images to actual size" )
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update()


    @Slot()
    def toggle_border(self, checked):
        print_debug ( 90, "toggle_border called with checked = " + str(checked) )
        self.draw_border = checked
        for p in self.panel_list:
            p.draw_border = self.draw_border
            p.update()


    @Slot()
    def opt_n(self, option_name, option_action):
        if 'num' in dir(option_action):
          print_debug ( 50, "Dynamic Option[" + str(option_action.num) + "]: \"" + option_name + "\"" )
        else:
          print_debug ( 50, "Dynamic Option: \"" + option_name + "\"" )
        print_debug ( 50, "  Action: " + str(option_action) )



    @Slot()
    def import_images(self, checked):
        global alignment_layer_list
        global alignment_layer_index
        global preloading_range

        global import_role_name

        print_debug ( 5, "  Importing images for role: " + str(import_role_name) )

        options = QFileDialog.Options()
        if False:  # self.native.isChecked():
            options |= QFileDialog.DontUseNativeDialog

        file_name_list, filtr = QFileDialog.getOpenFileNames ( None,  # None was self
                                                               "Select Images to Import",
                                                               #self.openFileNameLabel.text(),
                                                               "Select Images",
                                                               "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)", "", options)
        if file_name_list != None:
          if len(file_name_list) > 0:

            # Attempt to hide the file dialog before opening ...
            for p in self.panel_list:
                p.update()

            print_debug ( 20, "Selected Files: " + str(file_name_list) )
            print_debug ( 20, "" )
            for f in file_name_list:
              # Find next layer with an empty role matching the requested import_role_name
              print_debug ( 10, "Trying to place file " + str(f) + " in role " + str(import_role_name) )
              found_layer = None
              this_layer_index = 0
              for alignment_layer in alignment_layer_list:
                role_taken = False
                for image in alignment_layer.image_list:
                  print_debug ( 10, "Checking image role of " + image.role + " against import_role_name of " + str(import_role_name) )
                  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
                  if image.role == str(import_role_name):
                    role_taken = True
                    break
                print_debug ( 10, "Searched layer and role_taken = " + str(role_taken) )
                if not role_taken:
                  # Add the image here at this layer
                  found_layer = alignment_layer
                  break
                this_layer_index += 1
              if found_layer:
                # Add the image/role to the found layer
                print_debug ( 10, "Adding to layer " + str(this_layer_index) )
                found_layer.image_list.append ( AnnotatedImage ( str(import_role_name), f, load_now=(abs(this_layer_index-alignment_layer_index)<preloading_range) ) )
              else:
                # Add a new layer for the image
                print_debug ( 10, "Creating a new layer at " + str(this_layer_index) )
                alignment_layer_list.append ( DisplayLayer ( f, load_now=(abs(this_layer_index-alignment_layer_index)<preloading_range) ) )

            # Draw the panels ("windows")
            for p in self.panel_list:
                p.force_center = True
                p.update()

        self.update()

        #if len(alignment_layer_list) > 0:
        #    self.status.showMessage("File: " + alignment_layer_list[alignment_layer_index].image_file_name)


    def set_roles (self, roles_list):
      global global_panel_roles
      if len(roles_list) > 0:
        # Save these roles
        global_panel_roles = roles_list
        # Remove all the image panels (to be replaced)
        self.remove_all_panels(None)
        # Create the new panels
        for role in roles_list:
          zpw = ZoomPanWidget(role=role, parent=self, fname=None)
          zpw.draw_border = self.draw_border
          self.panel_list.append ( zpw )
          self.image_hbox_layout.addWidget ( self.panel_list[-1] )
        # Set the Roles menu with these newly defined roles
        roles_menu = None
        mb = self.menuBar()
        if not (mb is None):
          for m in mb.children():
            if type(m) == QMenu:
              text_label = ''.join(m.title().split('&'))
              if 'Images' in text_label:
                print ( "Found Images Menu" )
                for mm in m.children():
                  if type(mm) == QMenu:
                    text_label = ''.join(mm.title().split('&'))
                    if 'Import into' in text_label:
                      print ( "Found Import Into Menu" )
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

    @Slot()
    def define_roles(self, checked):
        global global_panel_roles
        input_val, ok = QInputDialog().getText ( None, "Define Roles", "Current: "+str(global_panel_roles), echo=QLineEdit.Normal, text="" )
        if ok:
          input_val = input_val.strip()
          if len(input_val) > 0:
            roles_list = [ str(v) for v in input_val.split(' ') if len(v) > 0 ]
            self.set_roles ( roles_list )
          else:
            self.set_roles ( global_panel_roles )
        else:
          print ( "Cancel: Roles not changed" )


    @Slot()
    def import_into_role(self, checked):
        global import_role_name
        import_role_name = str ( self.sender().text() )
        self.import_images ( checked )

    @Slot()
    def import_images_new_role(self, checked):
        print ( "Roles must be defined first" )

    '''
        global import_role_name
        import_role_name += 1
        self.import_images ( checked )
        zpw = ZoomPanWidget(role=str(import_role_name), parent=self, fname=fname)
        zpw.draw_border = self.draw_border
        self.panel_list.append ( zpw )
        self.image_hbox_layout.addWidget ( self.panel_list[-1] )

    @Slot()
    def import_images_new_role(self, checked):
        global import_role_name
        import_role_name += 1
        self.import_images ( checked )
        zpw = ZoomPanWidget(role=str(import_role_name), parent=self, fname=fname)
        zpw.draw_border = self.draw_border
        self.panel_list.append ( zpw )
        self.image_hbox_layout.addWidget ( self.panel_list[-1] )
    '''

    @Slot()
    def import_images_selected_role(self, checked):
        global import_role_name
        input_val, ok = QInputDialog().getText ( None, "Select Role", "Choose: "+str(global_panel_roles), echo=QLineEdit.Normal, text="" )
        if ok:
          import_role_name = input_val
          self.import_images ( checked )

    @Slot()
    def remove_this_layer(self, checked):
        global alignment_layer_list
        global alignment_layer_index
        alignment_layer_list = alignment_layer_list[0:alignment_layer_index] + alignment_layer_list[alignment_layer_index+1:]
        if alignment_layer_index > 0:
          alignment_layer_index += -1
        for p in self.panel_list:
            p.update()

    @Slot()
    def remove_all_layers(self, checked):
        global alignment_layer_list
        global alignment_layer_index
        global main_window
        global import_role_name
        alignment_layer_index = 0
        alignment_layer_list = []
        for w in main_window.panel_list:
            main_window.image_hbox_layout.removeWidget(w)
            w.destroy()
        main_window.panel_list = []
        import_role_name = 1
        self.update()

    @Slot()
    def remove_all_panels(self, checked):
        global alignment_layer_list
        global alignment_layer_index
        global main_window
        global import_role_name
        alignment_layer_index = 0
        alignment_layer_list = []
        if main_window != None:
          for w in main_window.panel_list:
              main_window.image_hbox_layout.removeWidget(w)
              w.destroy()
          main_window.panel_list = []
        import_role_name = 1
        #self.init_panels()
        self.update()


    @Slot()
    def set_max_image_size(self, checked):
        global max_image_file_size
        input_val, ok = QInputDialog().getInt ( None, "Enter Max Image File Size", "Max Image Size:", max_image_file_size )
        if ok:
          max_image_file_size = input_val

    @Slot()
    def set_preloading_range(self, checked):
        global alignment_layer_list
        global alignment_layer_index
        global preloading_range
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
        print ( "\n\nEntering python console, use Control-D or Control-Z when done.\n" )
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def run_app(main_win=None, file_name=None):
    global app
    global fname
    global main_window

    fname = file_name

    # Qt Application
    # app = QApplication(sys.argv)

    if main_win == None:
        main_window = MainWindow(fname)
    else:
        main_window = main_win

    # main_window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

    main_window.show()
    sys.exit(app.exec_())


# This provides default command line parameters if none are given (as with "Idle")
#if len(sys.argv) <= 1:
#    sys.argv = [ __file__, "-f", "vj_097_1k1k_1.jpg" ]

if __name__ == "__main__":
    # global app  # global isn't needed here ... because the "if" doesn't create a new scope (unlike many other languages)

    options = argparse.ArgumentParser()
    options.add_argument("-f", "--file", type=str, required=False)
    args = options.parse_args()
    fname = args.file

    # Qt Application
    app = QApplication(sys.argv)

    main_window = MainWindow(fname)
    # main_window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

    main_window.show()
    sys.exit(app.exec_())

