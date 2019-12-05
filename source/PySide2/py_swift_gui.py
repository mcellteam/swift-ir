import sys
import argparse
import cv2

from PySide2.QtWidgets import QApplication, QMainWindow, QLabel, QAction
from PySide2.QtGui import QPixmap
from PySide2.QtCore import Slot, qApp


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

    window = MainWindow(label,fname)
    # window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

    window.show()
    sys.exit(app.exec_())

