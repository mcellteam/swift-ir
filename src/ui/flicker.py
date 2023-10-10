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
        self._isPlaying = 0
        self.setMinimumSize(QSize(64,64))
        # self.resize(QSize(180,180))
        self.setStyleSheet("""background-color: #ffffff;""")
        self.extra = "test"

        # policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # policy.setHeightForWidth(True)
        # self.setSizePolicy(policy)


    def set(self):
        # logger.critical('Setting pixmap...')
        self.setPixmap(QPixmap(self.series[self.cur]))
        self.repaint()

    def set_position(self, p:int):
        # logger.critical('Setting flicker position')

        self.position = p

        logger.info(f"self.position                 = {self.position}")
        logger.info(f"cfg.data.first_unskipped()    = {cfg.data.first_unskipped()}")

        if (self.position <= cfg.data.first_unskipped()) or (cfg.data.skipped()):
            self.a = self.no_image_path
            self.b = self.no_image_path
            self.series = [self.a, self.b]
            self.set_no_image()
            self.update()
            return

        self.a = cfg.data.path_aligned(l=p)

        ind_reference = cfg.data['data']['scales'][cfg.data.level]['stack'][cfg.data.zpos]['reference_index']

        # self.b = cfg.data.thumbnail_aligned(z=max(0, p - 1))
        self.b = cfg.data.path_aligned(l=ind_reference)
        # self.a = cfg.data.path(z=p)
        # self.b = cfg.data.path(z=max(0,p-1))
        self.series = [self.a, self.b]

    def onTimer(self):
        self.cur = 1 - self.cur
        self.set()
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
            self.update()
        except:
            print_exception()
            logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')


    def paintEvent(self, event):
        # logger.info('')
        if self.pixmap():
            # logger.info('trying >>>')
            try:
                pm = self.pixmap()
                if (pm.width() == 0) or (pm.height() == 0):
                    self.set_no_image()
                    return
                # originalRatio = pm.width() / pm.height()
                # currentRatio = self.width() / self.height()
                qp = QPainter(self)
                # if originalRatio != currentRatio:
                # qp = QPainter(self)
                pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.r = rect = QRect(0, 0, pm.width(), pm.height())
                # rect.moveBottomLeft(self.rect().bottomLeft())
                # qp.drawPixmap(rect, pm)
                rect.moveCenter(self.rect().center())

                qp.drawPixmap(rect, pm)

                if (not cfg.data.skipped()) and (cfg.data.fn_reference() != ''):
                    font = QFont()
                    font.setBold(True)
                    # size = max(min(int(11 * (max(pm.height(), 1) / 60)), 14), 7)
                    size = 10
                    font.setPointSize(size)
                    qp.setFont(font)
                    # logger.info(f"self.rect().height() = {self.rect().height()}")
                    # qp.setPen(QColor('#FFFF66'))
                    # qp.setPen(QColor(('#FFFF66', '#a30000')[self.cur == 1]))
                    qp.setPen(QColor('#a30000'))
                    # loc = QPoint(0, self.rect().height() - 20)
                    txt = ("Transforming", "Reference")[self.cur == 1]
                    # loc = (QPoint(5, 13), QPoint(5, self.rect().height() - 6))[self.cur == 1]
                    loc = QPoint(5, self.rect().height() - 6)
                    qp.drawText(loc, txt)
                    # return
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