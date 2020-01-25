import sys
import argparse
import cv2

from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QAction, QSizePolicy
from PySide2.QtGui import QPixmap, QColor, QPainter, QPalette, QPen
from PySide2.QtCore import Slot, qApp, QRect, QRectF, QSize, Qt, QPoint, QPointF


class ZoomPanWidget(QWidget):
    def __init__(self, parent=None, fname=None):
        super(ZoomPanWidget, self).__init__(parent)

        self.fname = fname
        self.pixmap = None

        if self.fname != None:
          if len(self.fname) > 0:
            self.pixmap = QPixmap(fname)

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

        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
        print ( "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()) )
        self.update()

    def wheelEvent(self, event):
        self.wheel_index += event.delta()/120

        mouse_win_x = event.x()
        mouse_win_y = event.y()

        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow (self.scroll_factor, self.wheel_index)

        self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale)
        self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        if True:
            if self.pixmap != None:
                painter.scale ( self.zoom_scale, self.zoom_scale )
                painter.drawPixmap ( QPointF(self.ldx+self.dx,self.ldy+self.dy), self.pixmap )
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


# MainWindow contains the Menu Bar and the Status Bar
class MainWindow(QMainWindow):

    def __init__(self, fname):

        QMainWindow.__init__(self)
        self.setWindowTitle("PySide2 Image Viewer")

        self.zpa = ZoomPanWidget(fname=fname)

        # Menu Bar
        self.menu = self.menuBar()
        ml = [
              [ '&File',
                [
                  [ '&New Project', 'Ctrl+N', self.not_yet ],
                  [ '&Open Project', 'Ctrl+O', self.not_yet ],
                  [ '&Save Project', 'Ctrl+S', self.not_yet ],
                  [ 'Save Project &As', 'Ctrl+A', self.not_yet ],
                  [ '-', None, None ],
                  [ 'Set Destination...', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'E&xit', 'Ctrl+Q', self.exit_app ]
                ]
              ],
              [ '&Images',
                [
                  [ '&Import...', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Center', None, self.not_yet ],
                  [ 'Actual Size', None, self.not_yet ],
                  [ 'Refresh', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Clear Out Images', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Clear All Layers', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Clear Everything', None, self.not_yet ]
                ]
              ],
              [ '&Scaling',
                [
                  [ '&Define Scales', None, self.not_yet ],
                  [ '&Generate All Scales', None, self.not_yet ],
                  [ '&Import All Scales', None, self.not_yet ],
                  [ '-', None, None ],
                  [ '&Generate Tiled', None, self.not_yet ],
                  [ '&Import Tiled', None, self.not_yet ],
                  [ '&Show Tiled', None, self.not_yet ]
                ]
              ],
              [ '&Scales',
                [
                  [ '&Scale 1', None, self.not_yet ]
                ]
              ],
              [ '&Points',
                [
                  [ '&Alignment Point Mode', None, self.not_yet ],
                  [ '&Delete Points', None, self.not_yet ],
                  [ '&Clear All Alignment Points', None, self.not_yet ],
                  [ '-', None, None ],
                  [ '&Point Cursor',
                    [
                      [ 'Crosshair', None, self.not_yet ],
                      [ 'Target', None, self.not_yet ]
                    ]
                  ]
                ]
              ],
              [ '&Set',
                [
                  [ '&Max Image Size', 'Ctrl+M', self.not_yet ],
                  [ '-', None, None ],
                  [ 'Perform Swims', None, self.not_yet ],
                  [ 'Update CFMs', None, self.not_yet ],
                  [ 'Generate Images', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Use C Version', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Unlimited Zoom', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Default Plot Code', None, self.not_yet ],
                  [ 'Custom Plot Code', None, self.not_yet ],
                ]
              ],
              [ '&Show',
                [
                  [ 'Window Centers', None, self.not_yet ],
                  [ 'Affines', None, self.not_yet ],
                  [ 'Skipped Images', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Plot', None, self.not_yet ],
                ]
              ],
              [ '&Debug',
                [
                  [ '&Python Console', 'Ctrl+P', self.py_console ],
                  [ '-', None, None ],
                  [ 'Print Affine', None, self.not_yet ],
                  [ 'Print Structures', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Define Waves', None, self.not_yet ],
                  [ 'Make Waves', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Define Grid', None, self.not_yet ],
                  [ 'Grid Align', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Show Waves', None, self.not_yet ],
                  [ 'Show Grid Align', None, self.not_yet ],
                  [ 'Show Aligned', None, self.not_yet ],
                  [ '-', None, None ],
                  [ '&Set Debug Level',
                    [
                      [ 'Level 0', None, self.not_yet ],
                      [ 'Level 10', None, self.not_yet ],
                      [ 'Level 20', None, self.not_yet ],
                      [ 'Level 30', None, self.not_yet ],
                      [ 'Level 40', None, self.not_yet ],
                      [ 'Level 50', None, self.not_yet ],
                      [ 'Level 60', None, self.not_yet ],
                      [ 'Level 70', None, self.not_yet ],
                      [ 'Level 80', None, self.not_yet ],
                      [ 'Level 90', None, self.not_yet ],
                      [ 'Level 100', None, self.not_yet ]
                    ]
                  ]
                ]
              ],
              [ '&Help',
                [
                  [ 'Manual...', None, self.not_yet ],
                  [ 'Key Commands...', None, self.not_yet ],
                  [ 'Mouse Clicks...', None, self.not_yet ],
                  [ '-', None, None ],
                  [ 'Skipped Images', None, self.not_yet ],
                  [ 'License...', None, self.not_yet ],
                  [ 'Version...', None, self.not_yet ]
                ]
              ]
            ]
        self.build_menu_from_list ( self.menu, ml )

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage("File: "+fname)

        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)
        # self.setFixedSize(geometry.width() * 0.8, geometry.height() * 0.7)
        self.setMinimumWidth(1400)
        self.setMinimumHeight(1024)

        self.setCentralWidget(self.zpa)
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def build_menu_from_list (self, parent, menu_list):
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
              parent.addAction ( action )


    @Slot()
    def not_yet(self, checked):
        print ( "Function is not implemented yet" )

    @Slot()
    def exit_app(self, checked):
        sys.exit()

    @Slot()
    def py_console(self, checked):
        print ( "\n\nEntering python console, use Control-D or Control-Z when done.\n" )
        __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


# This provides default command line parameters if none are given (as with "Idle")
if len(sys.argv) <= 1:
    sys.argv = [ __file__, "-f", "vj_097_1k1k_1.jpg" ]

if __name__ == "__main__":
    options = argparse.ArgumentParser()
    options.add_argument("-f", "--file", type=str, required=True)
    args = options.parse_args()
    fname = args.file

    # Qt Application
    app = QApplication(sys.argv)

    window = MainWindow(fname)
    # window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

    window.show()
    sys.exit(app.exec_())

