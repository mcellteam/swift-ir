#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QTableWidget, QTableWidgetItem, QSlider, QSizePolicy
from qtpy.QtCore import Qt, QRect, QSize, QPoint, QEvent
from qtpy.QtGui import QPixmap, QPainter, QColor, QBrush, QFont, QPen
from src.helpers import absFilePaths
from src.helpers import print_exception, get_appdir
from src.funcs_image import ImageSize

import src.config as cfg

logger = logging.getLogger(__name__)


class SnrThumbnail(QWidget):

    def __init__(self, parent=None, path='', snr=0.0):
        super().__init__(parent)
        # thumbnail = QLabel(self)
        self.path = path
        self.snr = snr
        self.thumbnail = CorrSignalThumbnail(self)
        self.thumbnail.setScaledContents(True)
        self.label = QLabel('%.3f' % self.snr)
        self.label.setStyleSheet('color: #ff0000')
        self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')
        # layout = QGridLayout()
        # layout.setContentsMargins(1, 1, 1, 1)
        # layout.addWidget(self.thumbnail, 0, 0)
        # layout.addWidget(self.label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        # self.setLayout(layout)

        if path:
            self.set_data(path=self.path, snr=self.snr)

    def set_data(self, path, snr):
        self.path = path
        self.snr = snr
        self.thumbnail.snr = snr
        try:
            self.thumbnail.setPixmap(QPixmap(self.path))
            # self.label.setText('%.3f' % self.snr)
        except:
            print_exception()
            logger.warning(f'WARNING path={self.path}, label={self.snr}')

    def set_no_image(self):
        try:
            self.thumbnail.setPixmap(QPixmap(self.no_image_path))
            self.label.setText('')
        except:
            print_exception()
            logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')

    # def sizeHint(self):
    #     return QSize(200, 200)


class Thumbnail(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        self.thumbnail = CorrSignalThumbnail(self)
        self.pixmap = QPixmap(path)
        self.thumbnail.setPixmap(self.pixmap)
        self.thumbnail.setScaledContents(True)
        self.layout = QGridLayout()
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.addWidget(self.thumbnail, 0, 0)
        self.setLayout(self.layout)



class ThumbnailFast(QLabel):
    def __init__(self, parent, path=None, extra=''):
        super().__init__(parent)
        self.setScaledContents(True)
        if path:
            self.path = path
            self.setPixmap(QPixmap(self.path))
        self.extra = extra
        # self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image_.png')
        # self.repaint()
        self.border_color = '#000000'
        self.showBorder = False
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)



    def showPixmap(self):
        self.setPixmap(QPixmap(self.path))

    def updateStylesheet(self):
        if self.showBorder:
            self.setStyleSheet(f"border: 3px solid {self.border_color};")
        else:
            self.setStyleSheet("")


    def paintEvent(self, event):
        if self.pixmap():
            # if self.showBorder:
            #     self.setStyleSheet(f"border: 3px solid {self.border_color};")
            # else:
            #     self.setStyleSheet("")
            try:
                pm = self.pixmap()
                originalRatio = pm.width() / pm.height()
                currentRatio = self.width() / self.height()
                if originalRatio != currentRatio:
                    qp = QPainter(self)
                    pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.r = rect = QRect(0, 0, pm.width(), pm.height())
                    rect.moveBottomLeft(self.rect().bottomLeft())
                    qp.drawPixmap(rect, pm)

                    if self.extra:
                        qp.setPen(QColor('#ede9e8'))
                        loc = QPoint(0, self.rect().height() - 4)
                        if self.extra:
                            qp.drawText(loc, self.extra)
                    return
            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                # print_exception()
                pass
        super().paintEvent(event)

    def resizeEvent(self, e):
        self.setMaximumWidth(self.height())




class CorrSignalThumbnail(QLabel):
    def __init__(self, parent, path='', snr='', extra=''):
        super().__init__(parent)
        self.setScaledContents(True)
        self.path = path
        if self.path:
            self.setPixmap(QPixmap(self.path))
        self.snr = snr
        self.extra = extra
        self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')
        # self.setStyleSheet("""border: 3px solid #ffe135;""")


    def paintEvent(self, event):
        if self.pixmap():
            try:
                # originalRatio = pm.width() / pm.height()
                # currentRatio = self.width() / self.height()
                # if originalRatio != currentRatio:
                qp = QPainter(self)

                pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # pm.fill()
                self.r = rect = QRect(0, 0, pm.width(), pm.height())
                # rect.moveBottomLeft(self.rect().bottomLeft())
                # rect.moveBottomLeft(self.rect().bottomLeft())
                rect.moveCenter(self.rect().center())
                qp.drawPixmap(rect, pm)
                # pen = QPen()
                # brush = QBrush()
                # brush.setColor(QColor("#141414"))
                # pen.setBrush(brush)
                # pen.setColor(QColor('#ffe135'))
                # qp.setPen(pen)


                font = QFont()
                font.setBold(True)
                font.setPointSize(13)
                qp.setFont(font)
                # qp.setPen(QColor('#ff0000'))
                qp.setPen(QColor('#a30000'))

                if self.snr:
                    # loc = QPoint(0, self.rect().height() - 4)
                    loc = QPoint(4, self.rect().height() - 8)
                    if self.extra:
                        qp.drawText(loc, '%.3f' %self.snr + '\n' + self.extra)
                    else:
                        qp.drawText(loc, '%.3f' %self.snr)
                return
            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                # print_exception()
                pass
        super().paintEvent(event)


    def set_data(self, path, snr):
        self.path = path
        self.snr = snr
        try:
            self.setPixmap(QPixmap(self.path))
            # self.label.setText('%.3f' % self.snr)
        except:
            print_exception()
            logger.warning(f'WARNING path={self.path}, label={self.snr}')

    def set_no_image(self):
        self.snr = None
        try:
            self.setPixmap(QPixmap(self.no_image_path))
        except:
            print_exception()
            logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')

