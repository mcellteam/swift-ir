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

        self.mdx = 0
        self.mdy = 0
        self.ldx = 0
        self.ldy = 0
        self.dx = 0
        self.dy = 0

        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
        print ( "mousePressEvent at " + str(event.x()) + ", " + str(event.y()) )
        if event.button() == Qt.MouseButton.RightButton:
            self.dx = self.mdx = self.ldx = 0
            self.dy = self.mdy = self.ldy = 0
            self.zoom_scale = 1.0
        else:
            self.mdx = event.x()
            self.mdy = event.y()
        self.update()

    def mouseMoveEvent(self, event):
        # print ( "mouseMoveEvent at " + str(event.x()) + ", " + str(event.y()) )
        self.dx = (event.x() - self.mdx) / self.zoom_scale
        self.dy = (event.y() - self.mdy) / self.zoom_scale
        self.update()

    def mouseReleaseEvent(self, event):
        print ( "mouseReleaseEvent at " + str(event.x()) + ", " + str(event.y()) )
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
        self.zoom_scale = pow (self.scroll_factor, self.wheel_index)
        print ( "Wheel index = " + str(self.wheel_index) + ", Scale = " + str(self.zoom_scale) )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        if True:
            if self.pixmap != None:
                painter.scale ( self.zoom_scale, self.zoom_scale )
                painter.drawPixmap ( QPoint(self.ldx+self.dx,self.ldy+self.dy), self.pixmap )
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

        # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("&File")

        # Exit QAction
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.exit_app)

        self.file_menu.addAction(exit_action)

        # Status Bar
        self.status = self.statusBar()
        self.status.showMessage("File: "+fname)

        # Window dimensions
        geometry = qApp.desktop().availableGeometry(self)
        # self.setFixedSize(geometry.width() * 0.8, geometry.height() * 0.7)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)

        self.setCentralWidget(self.zpa)
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    @Slot()
    def exit_app(self, checked):
        sys.exit()

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

