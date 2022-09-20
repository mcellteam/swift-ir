#!/usr/bin/env python3

from qtpy.QtWidgets import QSplashScreen
from qtpy.QtGui import QMovie, QPainter, QPixmap
from qtpy.QtCore import Qt


class SplashScreen(QSplashScreen):

    def __init__(self, path):
        self.movie = QMovie(path)
        self.movie.jumpToFrame(0)
        pixmap = QPixmap(self.movie.frameRect().size())
        QSplashScreen.__init__(self, pixmap)
        self.movie.frameChanged.connect(self.repaint)

    def showEvent(self, event):
        self.movie.start()

    def hideEvent(self, event):
        self.movie.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self.movie.currentPixmap()
        self.setMask(pixmap.mask())
        painter.drawPixmap(0, 0, pixmap)


# class SplashScreen(QSplashScreen):
#     def __init__(self, filepath, flags=0):
#         super().__init__(flags=Qt.WindowFlags(flags))
#         self.movie = QMovie(filepath, parent=self)
#         self.movie.frameChanged.connect(self.handleFrameChange)
#         self.movie.start()
#
#     def updateProgress(self, count=0):
#         if count == 0:
#             message = 'Starting...'
#         elif count > 0:
#             message = f'Processing... {count}'
#         else:
#             message = 'Finished!'
#         self.showMessage(
#             message, Qt.AlignHCenter | Qt.AlignBottom, Qt.white)
#
#     def handleFrameChange(self):
#         pixmap = self.movie.currentPixmap()
#         self.setPixmap(pixmap)
#         self.setMask(pixmap.mask())