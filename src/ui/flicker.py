#!/usr/bin/env python3

import os
import inspect
import logging

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QSizePolicy
from qtpy.QtCore import Qt, QRect, QSize, QPoint, QTimer
from qtpy.QtGui import QPixmap, QPainter, QColor, QBrush, QFont, QPen
import src.config as cfg

logger = logging.getLogger(__name__)

class Flicker(QLabel):
    def __init__(self, parent, zpos=5, extra=''):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)
        # self.setPixmap(QPixmap(self.path))
        self.extra = extra
        self.border_color = '#000000'
        self.showBorder = False
        # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.onTimer)
        self.a = None
        self.b = None
        self.series = None
        self.cur = 0
        self._isPlaying = False
        self.setMinimumSize(QSize(32,32))

    def set(self):
        self.setPixmap(QPixmap(self.series[self.cur]))

    def set_position(self, p:int):
        self.position = p
        self.a = cfg.data.filename(l=p)
        self.b = cfg.data.filename(l=max(0,p-1))
        self.series = [self.a, self.b]

    def onTimer(self):
        self.set()
        self.cur = 1 - self.cur


    def start(self):
        logger.info('start >>>>')
        self.set()
        self.timer.start()
        self._isPlaying = 1

    def stop(self):
        logger.info('stop >>>>')
        self.timer.stop()
        self._isPlaying = 0

    def paintEvent(self, event):
        if self.pixmap():
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

    def sizeHint(self):
        return QSize(128, 128)