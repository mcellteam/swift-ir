#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QTableWidget, QTableWidgetItem, QSlider
from qtpy.QtCore import Qt, QRect, QSize
from qtpy.QtGui import QPixmap, QPainter
from src.helpers import absFilePaths
from src.helpers import print_exception
from src.funcs_image import ImageSize

import src.config as cfg

logger = logging.getLogger(__name__)


class SnrThumbnail(QWidget):

    def __init__(self, parent, path='', snr=0.0):
        super().__init__(parent)
        # thumbnail = QLabel(self)
        self.path = path
        self.snr = snr
        self.thumbnail = ScaledPixmapLabel(self)
        self.thumbnail.setScaledContents(True)
        self.label = QLabel('%.3f' % self.snr)
        self.label.setStyleSheet('color: #ff0000')
        layout = QGridLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(self.thumbnail, 0, 0)
        layout.addWidget(self.label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.setLayout(layout)
        if path:
            self.set_data(path=self.path, snr=self.snr)

    def set_data(self, path, snr):
        self.path = path
        self.snr = snr
        try:
            pixmap = QPixmap(self.path)
            self.thumbnail.setPixmap(pixmap)
            self.label.setText('%.3f' % self.snr)
        except:
            print_exception()
            logger.warning(f'WARNING path={self.path}, label={self.snr}')

    def sizeHint(self):
        return QSize(200, 200)


class Thumbnail(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        self.thumbnail = ScaledPixmapLabel(self)
        self.pixmap = QPixmap(path)
        self.thumbnail.setPixmap(self.pixmap)
        self.thumbnail.setScaledContents(True)
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.thumbnail, 0, 0)
        self.setLayout(self.layout)


class ScaledPixmapLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setScaledContents(True)

    def paintEvent(self, event):
        if self.pixmap():
            pm = self.pixmap()
            try:
                originalRatio = pm.width() / pm.height()
                currentRatio = self.width() / self.height()
                if originalRatio != currentRatio:
                    qp = QPainter(self)
                    pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    rect = QRect(0, 0, pm.width(), pm.height())
                    rect.moveCenter(self.rect().center())
                    qp.drawPixmap(rect, pm)
                    return
            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                # print_exception()
                pass
        super().paintEvent(event)