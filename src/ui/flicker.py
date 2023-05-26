#!/usr/bin/env python3

import os
import inspect
import logging

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QSizePolicy
from qtpy.QtCore import Qt, QRect, QSize, QPoint, QTimer
from qtpy.QtGui import QPixmap, QPainter, QColor, QBrush, QFont, QPen
import src.config as cfg
from src.helpers import print_exception, get_appdir

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
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.onTimer)
        self.a = None
        self.b = None
        self.series = None
        self.cur = 0
        self._isPlaying = False
        self.setMinimumSize(QSize(128,128))
        # self.resize(QSize(180,180))
        self.setStyleSheet("""background-color: #ffffff;""")

        self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')

        # policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # policy.setHeightForWidth(True)
        # self.setSizePolicy(policy)



    def set(self):
        # logger.critical('Setting pixmap...')
        self.setPixmap(QPixmap(self.series[self.cur]))

    def set_position(self, p:int):
        # logger.critical('Setting flicker position')

        self.position = p

        if (self.position == 0) or (cfg.data.skipped()):
            self.a = self.no_image_path
            self.b = self.no_image_path
            self.series = [self.a, self.b]
            self.set_no_image()
            return

        self.a = cfg.data.thumbnail_aligned(l=p)

        reference = cfg.data['data']['scales'][cfg.data.scale]['stack'][cfg.data.zpos]['reference']
        ind_reference = cfg.data.get_index(reference)

        # self.b = cfg.data.thumbnail_aligned(l=max(0, p - 1))
        self.b = cfg.data.thumbnail_aligned(l=ind_reference)
        # self.a = cfg.data.filename(l=p)
        # self.b = cfg.data.filename(l=max(0,p-1))
        self.series = [self.a, self.b]

    def onTimer(self):
        self.set()
        self.cur = 1 - self.cur
        # logger.info(f'Timer is timing cur = {self.cur}, {self.series[self.cur]} ...')


    def start(self):
        logger.info('start >>>>')
        self.set_position(cfg.data.zpos)
        self.set()
        self.timer.start()
        self._isPlaying = 1

    def stop(self):
        self.timer.stop()
        self._isPlaying = 0
        logger.info('<<<< stop')

    def set_no_image(self):
        self.snr = None
        try:
            self.setPixmap(QPixmap(self.no_image_path))
        except:
            print_exception()
            logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')


    def paintEvent(self, event):
        if self.pixmap():
            try:
                pm = self.pixmap()
                if (pm.width() == 0) or (pm.height() == 0):
                    self.set_no_image()
                    return
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
                logger.warning('ZeroDivisionError')
                print_exception()
        super().paintEvent(event)

    # def resizeEvent(self, e):
    #     self.setMaximumWidth(self.height())

    # def sizeHint(self):
    #     return QSize(100, 100)

    # def sizeHint(self):
    #     try:
    #         pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    #         return QSize(pm.width(), pm.height())
    #         # return QSize(100,100)
    #     except:
    #         pass