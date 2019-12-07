import sys
import argparse
import cv2

from PySide2.QtWidgets import QApplication, QMainWindow, QLabel, QAction
from PySide2.QtGui import QPixmap
from PySide2.QtCore import Slot, qApp

from PySide2.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide2.QtGui import QColor, QPainter, QPalette, QPen
from PySide2.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
        QSizePolicy, QWidget)


class ZoomPanWidget(QWidget):
    def __init__(self, parent=None):
        super(ZoomPanWidget, self).__init__(parent)

        self.floatBased = False
        self.antialiased = False
        self.frameNo = 0

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

    def nextAnimationFrame(self):
        self.frameNo += 1
        self.update()

    def wheelEvent(self, event):
        print ( "Wheel Event with delta() = " + str(event.delta()) )
        self.frameNo += event.delta()/12
        if self.frameNo < 0:
          self.frameNo = 0
        self.update()

        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, self.antialiased)
        painter.translate(self.width() / 2, self.height() / 2)

        for diameter in range(0, 256, 9):
            delta = abs((self.frameNo % 128) - diameter / 2)
            alpha = 255 - (delta * delta) / 4 - diameter
            if alpha > 0:
                painter.setPen(QPen(QColor(0, diameter / 2, 127, alpha), 3))

                if self.floatBased:
                    painter.drawEllipse(QRectF(-diameter / 2.0,
                            -diameter / 2.0, diameter, diameter))
                else:
                    painter.drawEllipse(QRect(-diameter / 2,
                            -diameter / 2, diameter, diameter))


class MainWindow(QMainWindow):
    def __init__(self, widget, fname):
        QMainWindow.__init__(self)
        self.setWindowTitle("PySide2 Image Viewer")

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
        self.setCentralWidget(widget)
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    @Slot()
    def exit_app(self, checked):
        sys.exit()

#__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
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

    # QLabel with an image
    label = QLabel()
    pixmap = QPixmap(fname)
    label.setPixmap(pixmap)

    zpa = ZoomPanWidget()

    window = MainWindow(zpa,fname)
    # window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

    window.show()
    sys.exit(app.exec_())

