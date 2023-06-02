#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap
import numpy as np
from functools import cache

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QTableWidget, QTableWidgetItem, QSlider, QSizePolicy
from qtpy.QtCore import Qt, QRect, QRectF, QSize, QPoint, QEvent, QPointF, QSizeF
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
        logger.critical()
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

        self.setWidgetResizable(True)



class ThumbnailFast(QLabel):
    def __init__(self, parent, path=None, extra='', name='', s=None, l=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)
        self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')
        self.path = self.no_image_path
        if path:
            self.path = path
        self.extra = extra
        self.name = name
        self.s = s
        self.l = l

        self.setPixmap(QPixmap(self.path))
        self.border_color = '#000000'
        self.showBorder = False
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._noImage = 0

    def showPixmap(self):
        self._noImage = 0
        self.setPixmap(QPixmap(self.path))

    def selectPixmap(self, path:str):
        if os.path.isdir(path):
            self.set_no_image()
            return
        # logger.critical(f"path = {path}")
        self._noImage = 0
        try:
            self.path = path
            self.setPixmap(QPixmap(self.path))
        except:
            print_exception()
            self.set_no_image()

    def set_no_image(self):
        self._noImage = 1
        self.snr = None
        try:
            self.setPixmap(QPixmap(self.no_image_path))
        except:
            print_exception()
            logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')

    def updateStylesheet(self):
        if self.showBorder:
            self.setStyleSheet(f"border: 3px solid {self.border_color};")
        else:
            self.setStyleSheet("")

    def paintEvent(self, event):
        if self.pixmap():
            try:
                pm = self.pixmap()
                # originalRatio = pm.width() / pm.height()
                # currentRatio = self.width() / self.height()
                # if originalRatio != currentRatio:
                qp = QPainter(self)
                # pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio)

                if self._noImage:
                    # self.set_no_image()
                    self.r = rect = QRect(0, 0, pm.width(), pm.height())
                    self.r.moveCenter(self.rect().center())
                    qp.drawPixmap(self.r, pm)
                    return

                self.r = rect = QRect(0, 0, pm.width(), pm.height())
                # rect.moveBottomLeft(self.rect().bottomLeft())
                qp.drawPixmap(rect, pm)
                img_size = cfg.data.image_size()
                # sf = self.r.getCoords()[2] / img_size[0]  # scale factor
                sf = self.r.getRect()[2] / img_size[0]  # scale factor

                # logger.critical(f"self.r.getCoords() = {self.r.getCoords()}")
                # logger.critical(f"self.r.getRect() = {self.r.getRect()}")
                # logger.critical(f"self.r.width() = {self.r.width()}")
                # logger.critical(f"self.r.height() = {self.r.height()}")

                if self.name in ('reference-table', 'transforming-table'):
                    method = cfg.data.method(s=self.s, l=self.l)
                    s = self.s
                    l = self.l
                else:
                    method = cfg.data.current_method
                    s = cfg.data.scale
                    l = cfg.data.zpos

                if self.name in ('reference', 'transforming', 'reference-table', 'transforming-table'):
                    if method == 'grid-default':
                        cp = QPoint(self.r.center())  # center point
                        ww = tuple(cfg.data['data']['defaults'][cfg.data.scale]['swim-window-px'])
                        for i,r in enumerate(get_default_grid_rects(sf, img_size, ww, cp.x(), cp.y())):
                            qp.setPen(QPen(QColor(cfg.glob_colors[i]), 2, Qt.DotLine))
                            qp.drawRect(r)
                    elif method == 'grid-custom':

                        regions = cfg.data.get_grid_custom_regions(s=s, l=l)
                        ww1x1 = cfg.data.swim_1x1_custom_px(s=s, l=l)
                        ww2x2 = cfg.data.swim_2x2_custom_px(s=s, l=l)

                        # logger.info(f'ww1x1 = {ww1x1}')
                        # logger.info(f'ww2x2 = {ww2x2}')

                        a = [(img_size[0] - ww1x1[0])/2 + ww2x2[0]/2, (img_size[1] - ww1x1[1])/2 + ww2x2[1]/2]
                        b = [img_size[0] - a[0], img_size[1] - a[1]]

                        if regions[0]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[0]), 2, Qt.DotLine))
                            rect = get_rect(sf, a[0], a[1], ww2x2[0])
                            qp.drawRect(rect)
                        if regions[1]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[1]), 2, Qt.DotLine))
                            rect = get_rect(sf, b[0], a[1], ww2x2[0])
                            qp.drawRect(rect)
                        if regions[2]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[2]), 2, Qt.DotLine))
                            rect = get_rect(sf, a[0], b[1], ww2x2[0])
                            qp.drawRect(rect)
                        if regions[3]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[3]), 2, Qt.DotLine))
                            rect = get_rect(sf, b[0], b[1], ww2x2[0])
                            qp.drawRect(rect)
                    elif method == 'manual-hint':
                        pts = []
                        ww = cfg.data.manual_swim_window_px()
                        if self.name in ('reference','reference-table'):
                            if self.name == 'reference-table':
                                pts = cfg.data.manpoints_mir('ref', s=s, l=l)
                            else:
                                pts = cfg.data.manpoints_mir('ref')
                        elif self.name in ('transforming', 'transforming-table'):
                            if self.name == 'transforming-table':
                                pts = cfg.data.manpoints_mir('base', s=s, l=l)
                            else:
                                pts = cfg.data.manpoints_mir('base')
                        for i,pt in enumerate(pts):
                            qp.setPen(QPen(QColor(cfg.glob_colors[i]), 2, Qt.DotLine))
                            x = int(pt[0])
                            y = int(pt[1])
                            r = get_rect(sf, x, y, ww)
                            qp.drawRect(r)



                if self.extra:
                    qp.setPen(QColor('#ede9e8'))
                    loc = QPoint(0, self.rect().height() - 4)
                    if self.extra:
                        qp.drawText(loc, self.extra)
                return



            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                # print_exception()
                self.set_no_image()
                pass
        super().paintEvent(event)


@cache
def get_rect(sf, x, y, ww):
    rect = QRect(QPoint(int(x*sf), int(y*sf)), QSize(int(ww*sf), int(ww*sf)))
    rect.moveCenter(QPoint(int(x*sf), int(y*sf)))
    return rect
    # return QRect(QPointF(x*sf, y*sf), QSizeF(ww*sf, ww*sf))



@cache
def get_default_grid_rects(sf, img_size, ww, cp_x, cp_y):
    # half_ww = [int(ww[0] / 2), int(ww[1] / 2)]

    a = ((img_size[0] - ww[0]) / 2, (img_size[1] - ww[1]) / 2)
    # b = (int((a[0] + ww[0])), int((a[1] + ww[1])))
    # # cp = (int(tn_size[0]/2), int(tn_size[1]/2))
    # rx1 = int(a[0] * sf) # ratio x1 (short)
    # ry1 = int(a[1] * sf) # ratio y1 (short)
    # rx2 = int(b[0] * sf) # ratio x2 (long)
    # ry2 = int(b[1] * sf)  # ratio y3 (long)

    rx1 = int(a[0] * sf)  # ratio x1 (short)
    ry1 = int(a[1] * sf)  # ratio y1 (short)
    rx2 = int((a[0] + ww[0]) * sf)  # ratio x2 (long)
    ry2 = int((a[1] + ww[1]) * sf)  # ratio y3 (long)

    cp = QPoint(cp_x, cp_y)

    # logger.critical('self.r: ' + str(self.r))
    # logger.critical('cp: ' + str(cp))
    # logger.critical('cp.x(): ' + str(cp.x()))
    # logger.critical('cp.y(): ' + str(cp.y()))
    # logger.critical('ww: ' + str(ww))
    # logger.critical('a: ' + str(a))
    # logger.critical('rx1: ' + str(rx1))
    # logger.critical('rx2: ' + str(rx2))
    # logger.critical('ry1: ' + str(ry1))
    # logger.critical('ry2: ' + str(ry2))
    # _p1 =
    # _cp = QPoint(cp.x(), cp.y())

    # p1---p2
    #      |
    # p4---p3
    p1 = QPoint(rx1, ry1)
    p2 = QPoint(rx2, ry1)
    p3 = QPoint(rx2, ry2)
    p4 = QPoint(rx1, ry2)

    # yield QRect(p1, cp)
    # yield QRect(p2, cp)
    # yield QRect(p3, cp)
    # yield QRect(p4, cp)

    return (QRect(p1, cp + QPoint(-1,-1)), QRect(p2, cp + QPoint(1,-1)), QRect(p4, cp + QPoint(-1,1)), QRect(p3, cp + QPoint(1,1)))




    # def resizeEvent(self, e):
    #     self.setMaximumWidth(self.height())



#
# class CorrSignalThumbnail(QLabel):
#     def __init__(self, parent, path='', snr='', extra=''):
#         super().__init__(parent)
#         self.setScaledContents(True)
#         # self.setMinimumSize(QSize(QSize(64,64)))
#         # self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
#         # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred) #Original!
#         self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
#         # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
#         self.path = path
#         if self.path:
#             self.setPixmap(QPixmap(self.path))
#         self.snr = snr
#         self.extra = extra
#         self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')
#         # self.setStyleSheet("""border: 3px solid #ffe135;""")
#         self.setAlignment(Qt.AlignCenter)
#         self.setStyleSheet("""background-color: #ffffff;""")
#         self.setMinimumSize(QSize(90, 90))
#         self.setAutoFillBackground(True)
#
#
#
#         # policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
#         # policy.setHeightForWidth(True)
#         # self.setSizePolicy(policy)
#
#     # def heightForWidth(self, width):
#     #     return width
#
#     def resizeEvent(self, e):
#         self.setMaximumWidth(self.height())
#
#
#     def paintEvent(self, event):
#         if self.pixmap():
#             try:
#                 # originalRatio = pm.width() / pm.height()
#                 # currentRatio = self.width() / self.height()
#                 # if originalRatio != currentRatio:
#                 qp = QPainter(self)
#
#                 pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
#                 if (pm.width() == 0) or (pm.height() == 0):
#                     self.set_no_image()
#                     return
#
#                 # pm.fill()
#                 self.r = rect = QRect(0, 0, pm.width(), pm.height())
#                 # rect.moveBottomLeft(self.rect().bottomLeft())
#                 # rect.moveBottomLeft(self.rect().bottomLeft())
#                 rect.moveCenter(self.rect().center())
#                 qp.drawPixmap(rect, pm)
#                 font = QFont()
#                 # font.setFamily('Courier')
#                 font.setBold(True)
#                 size = max(min(int(11 * (max(pm.height(),1) / 60)), 16), 8)
#                 font.setPointSize(size)
#                 # logger.critical(f'font size: {size}')
#                 qp.setFont(font)
#                 qp.setPen(QColor('#a30000'))
#                 # qp.setBrush(QColor('#ff0000'))
#
#                 if self.snr:
#                     # loc = QPoint(0, self.rect().height() - 4)
#                     loc = QPoint(4, self.rect().height() - 6)
#                     if self.extra:
#                         qp.drawText(loc, '%.1f' %self.snr + '\n' + self.extra)
#                     else:
#                         qp.drawText(loc, '%.1f' %self.snr)
#                 return
#             except ZeroDivisionError:
#                 # logger.warning('Cannot divide by zero')
#                 print_exception()
#                 pass
#         super().paintEvent(event)
#
#
#     def set_data(self, path, snr):
#         self.path = path
#         self.snr = snr
#         try:
#             self.setPixmap(QPixmap(self.path))
#             # self.label.setText('%.3f' % self.snr)
#         except:
#             print_exception()
#             logger.warning(f'WARNING path={self.path}, label={self.snr}')
#
#     def set_no_image(self):
#         self.snr = None
#         try:
#             self.setPixmap(QPixmap(self.no_image_path))
#         except:
#             print_exception()
#             logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')
#
#     # def heightForWidth(self, w):
#     #     if self.pixmap():
#     #         return int(w * (self.pixmap().height() / self.pixmap().width()))
#


#
# class CorrSignalThumbnail(QLabel):
#     def __init__(self, parent, path='', snr='', extra=''):
#         super().__init__(parent)
#         self.setScaledContents(True)
#         self.setMinimumSize(QSize(90,90))
#         # self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
#         # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
#         self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
#         # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
#         self.path = path
#         if self.path:
#             self.setPixmap(QPixmap(self.path))
#         self.snr = snr
#         self.extra = extra
#         self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')
#         # self.setStyleSheet("""border: 3px solid #ffe135;""")
#
#     def resizeEvent(self, e):
#         self.setMaximumWidth(self.height())
#
#     def paintEvent(self, event):
#         if self.pixmap():
#             try:
#                 # originalRatio = pm.width() / pm.height()
#                 # currentRatio = self.width() / self.height()
#                 # if originalRatio != currentRatio:
#                 qp = QPainter(self)
#
#                 pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
#
#                 # pm.fill()
#                 self.r = rect = QRect(0, 0, pm.width(), pm.height())
#                 # rect.moveBottomLeft(self.rect().bottomLeft())
#                 # rect.moveBottomLeft(self.rect().bottomLeft())
#                 rect.moveCenter(self.rect().center())
#                 qp.drawPixmap(rect, pm)
#                 font = QFont()
#                 # font.setFamily('Courier')
#                 font.setBold(True)
#                 size = max(min(int(11 * (max(pm.height(),1) / 60)), 16), 8)
#                 font.setPointSize(size)
#                 # logger.critical(f'font size: {size}')
#                 qp.setFont(font)
#                 qp.setPen(QColor('#a30000'))
#                 # qp.setBrush(QColor('#ff0000'))
#
#                 if self.snr:
#                     # loc = QPoint(0, self.rect().height() - 4)
#                     loc = QPoint(4, self.rect().height() - 6)
#                     if self.extra:
#                         qp.drawText(loc, '%.1f' %self.snr + '\n' + self.extra)
#                     else:
#                         qp.drawText(loc, '%.1f' %self.snr)
#                 return
#             except ZeroDivisionError:
#                 # logger.warning('Cannot divide by zero')
#                 print_exception()
#                 pass
#         super().paintEvent(event)
#
#
#     def set_data(self, path, snr):
#         self.path = path
#         self.snr = snr
#         try:
#             self.setPixmap(QPixmap(self.path))
#             # self.label.setText('%.3f' % self.snr)
#         except:
#             print_exception()
#             logger.warning(f'WARNING path={self.path}, label={self.snr}')
#
#     def set_no_image(self):
#         self.snr = None
#         try:
#             self.setPixmap(QPixmap(self.no_image_path))
#         except:
#             print_exception()
#             logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')
#
#
#     def sizeHint(self):
#         # pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
#         # return QSize(pm.width(), pm.height())
#         return QSize(100,100)


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
        self.setStyleSheet("""border: 0px solid #ffe135;""")
        self.setContentsMargins(0,0,0,0)
        self._noImage = 0


    def paintEvent(self, event):
        # if self._noImage:
        #     return

        if self.pixmap():
            try:
                # originalRatio = pm.width() / pm.height()
                # currentRatio = self.width() / self.height()s
                # if originalRatio != currentRatio:

                qp = QPainter(self)

                pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)

                # logger.info(f'pm.width() = {pm.width()}, pm.height() = {pm.height()}')

                # if self._noImage:
                #     return
                if self._noImage:
                    # self.set_no_image()
                    self.r = rect = QRect(0, 0, pm.width(), pm.height())
                    self.r.moveCenter(self.rect().center())
                    qp.drawPixmap(self.r, pm)
                    return

                # if (pm.width() == 0) or (pm.height() == 0):
                # pm.fill()
                self.r = rect = QRect(0, 0, pm.width(), pm.height())
                # rect.moveBottomLeft(self.rect().bottomLeft())
                self.r.moveCenter(self.rect().center())

                qp.drawPixmap(self.r, pm)
                # coords = self.r.getCoords()
                coords = self.r.getRect()
                cp = QPointF(self.r.center())  # center point

                siz = pm.width() / 4
                # logger.info(f'siz = {siz}')

                # qp.setPen(QPen(Qt.red, 1, Qt.DashLine))
                qp.setPen(QPen(QColor('#a30000'), 1, Qt.SolidLine))

                val = float(convert_rotation(45) * siz/2)
                qp.drawLine(QPointF(coords[0], coords[1]), cp + QPointF(float(-val), float(-val)))
                qp.drawLine(QPointF(coords[2], coords[1]), cp + QPointF(float(val), float(-val)))
                qp.drawLine(QPointF(coords[0], coords[3]), cp + QPointF(float(-val), float(val)))
                qp.drawLine(QPointF(coords[2], coords[3]), cp + QPointF(float(val), float(val)))


                arcRect = QRectF(cp + QPointF(float(-siz/2), float(-siz/2)), cp + QPointF(float(siz/2), float(siz/2)))
                # qp.drawArc(arcRect, 0, 90*16)
                # The startAngle and spanAngle must be specified in 1/16th of a degree, i.e.
                # a full circle equals 5760 (16 * 360). Positive values for the angles mean
                # counter-clockwise while negative values mean the clockwise direction. Zero
                # degrees is at the 3 o'clock position.
                spanAngle = 30
                qp.drawArc(arcRect, 30*16, spanAngle*16)
                qp.drawArc(arcRect, 30*16 + 180*16, spanAngle*16)
                qp.drawArc(arcRect, 30*16 + 90*16, spanAngle*16)
                qp.drawArc(arcRect, 30*16 + 270*16, spanAngle*16)

                font = QFont()
                font.setBold(True)
                size = max(min(int(11 * (max(pm.height(), 1) / 60)), 16), 8)
                font.setPointSize(size)
                # font.setPointSize(14)
                qp.setFont(font)
                # qp.setPen(QColor('#ff0000'))
                qp.setPen(QColor('#a30000'))

                if self.snr:
                    # loc = QPoint(0, self.rect().height() - 4)
                    # loc = QPoint(16, self.rect().height() - 6)
                    loc = QPointF(coords[0] + pm.width()/2 - size, coords[3])
                    if self.extra:
                        qp.drawText(loc, '%.1f' %self.snr + '\n' + self.extra)
                    else:
                        qp.drawText(loc, '%.1f' %self.snr)
                return
            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                print_exception()
                pass
        super().paintEvent(event)


    def set_data(self, path, snr):
        # logger.critical('')
        self._noImage = 0
        self.path = path
        self.snr = snr
        try:
            self.setPixmap(QPixmap(self.path))
            # self.label.setText('%.3f' % self.snr)

        except:
            print_exception()
            logger.warning(f'WARNING path={self.path}, label={self.snr}')

    def set_no_image(self):
        # logger.critical('')
        self.snr = None
        self._noImage = 1
        try:
            self.setPixmap(QPixmap(self.no_image_path))
            self.update()
        except:
            print_exception()
            logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')


def convert_rotation(degrees):
    deg2rad = 2*np.pi/360.
    return np.sin(deg2rad*degrees)