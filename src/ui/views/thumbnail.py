#!/usr/bin/env python3

import os
import logging
import numpy as np
from math import sqrt
from functools import cache

from qtpy.QtWidgets import QLabel
from qtpy.QtCore import Qt, QRect, QRectF, QSize, QPoint, QPointF, Signal
from qtpy.QtGui import QPixmap, QPainter, QColor, QBrush, QFont, QPen, QMouseEvent, QImage
from src.utils.helpers import print_exception
from src.utils.funcs_image import ImageSize

import src.config as cfg

logger = logging.getLogger(__name__)


class ThumbnailFast(QLabel):
    clicked = Signal(QMouseEvent)
    left_click = Signal(float, float)

    def __init__(self, parent, path='', extra='', name='', s=None, l=None):
        super().__init__(parent)
        self.setScaledContents(True)
        self._noImage = 0
        self.path = path
        self.setPixmap(QPixmap(32, 32))
        if self.path:
            try:
                # self.setPixmap(QPixmap.fromImage(QImage(file_path)))
                self.setPixmap(QPixmap(path))
            except:
                logger.warning(f"Failed to load: {path}")
                self.set_no_image()
        else:
            pixmap = QPixmap(32, 32)
            self.setPixmap(pixmap)

        self.extra = extra
        self.name = name
        self.s = s
        self.l = l

        self.map_border_color = {
            'match0': cfg.glob_colors[0],
             'match1': cfg.glob_colors[1],
             'match2': cfg.glob_colors[2],
             'match3': cfg.glob_colors[3]
        }
        # self.setStyleSheet("background-color: #dadada;")

    # def mousePressEvent(self, e):
    #     x, y, = (
    #         e.x(),
    #         e.y(),
    #     )
    #     print(f"{x} , {y}")
    #     # if self.pixmap:
    #     #     r = self.pixmap().rect()
    #     #     x0, y0 = r.x(), r.y()
    #         # x1, y1 = x0 + r.width(), y0 + r.height()
    #         # if x >= x0 and x < x1 and y >= y0 and y < y1:
    #         #     x_relative = (x - x0) / (x1 - x0)
    #         #     y_relative = (y - y0) / (y1 - y0)
    #         #     self.left_click.emit(x_relative, y_relative)
    #         #     print(f"{x_relative} , {x_relative}")
    #
    #     super().mousePressEvent(e)

    def showPixmap(self):
        self._noImage = 0
        # self.setPixmap(QPixmap(self.file_path))
        self.setPixmap(QPixmap.fromImage(QImage(self.path)))
        # self.update()

    def set_data(self, path):
        # logger.critical('')
        self._noImage = 0
        self.path = path
        try:
            self.setPixmap(QPixmap.fromImage(QImage(path)))
        except:
            print_exception(extra=f'WARNING path={self.path}')
            self.set_no_image()
        # finally:
        #     self.update()

    #Prev
    # def set_no_image(self):
    #     self._noImage = 1
    #     self.snr = None
    #     try:
    #         self.setPixmap(QPixmap(self.no_image_path))
    #     except:
    #         print_exception()
    #         logger.warning(f'WARNING file_path={self.no_image_path}, label={self.snr}')
    #     finally:
    #         self.update()

    # def set_no_image(self):
    #     # logger.critical('')
    #     self._noImage = 1
    #     try:
    #         # pass
    #         # self.pixmap().fill(QColor('#161c20'))
    #         # self.pixmap().fill(QColor('#ffe135'))
    #         # # self.pixmap().fill()
    #         # pixmap = QPixmap(16, 16)
    #         # # pixmap = QPixmap()
    #         # pixmap.fill(QColor('#f3f6fb'))  # fill the map with black
    #         # self.setPixmap(pixmap)
    #         pixmap = QPixmap(32, 32)
    #         pixmap.fill(QColor('#161c20'))  # fill the map with black
    #         self.setPixmap(pixmap)
    #     except:
    #         print_exception()
    #         logger.warning('Unable to set no image...')
    #     finally:
    #         self.update()

    def set_no_image(self):
        self._noImage = 1
        # try:
        #     self.pixmap().fill(QColor('#141414'))
        # except:
        #     # print_exception()
        #     logger.warning('Unable to set no image...')
        # finally:
        #     self.update()
        self.pixmap().fill(QColor('#dadada'))
        self.update()


    def paintEvent(self, event):
        if self.pixmap():
            try:

                qp = QPainter(self)

                # pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # if (pm.width() == 0) or (pm.height() == 0):
                #     return

                self.r = QRect(0, 0, pm.width(), pm.height())
                self.r.moveCenter(self.rect().center())
                qp.drawPixmap(self.r, pm)

                coords = self.r.getCoords()
                p1 = QPoint(coords[0], coords[1])
                p2 = QPoint(coords[2], coords[1])
                p3 = QPoint(coords[0], coords[3])
                p4 = QPoint(coords[2], coords[3])

                if self.name in self.map_border_color:
                    if cfg.mw.dm['state']['annotate_match_signals']:
                        qp.setPen(QPen(QColor(self.map_border_color[self.name]), 0, Qt.SolidLine))
                        qp.setBrush(QBrush(QColor(self.map_border_color[self.name])))
                        # qp.drawLines(p1,p2 , p1,p3,  p4,p2 , p4,p3)
                        qp.drawRect(0,0,20,20)

                if self._noImage:
                    try:
                        self.pixmap().fill(QColor('#dadada'))
                        font = QFont()
                        size = max(min(int(11 * (max(pm.height(), 1) / 80)), 14), 5)
                        font.setPointSize(size)
                        # font.setBold(True)
                        qp.setFont(font)
                        qp.setPen(QColor('#161c20'))
                        qp.drawText(QRectF(p1, p4), Qt.AlignCenter, "No Image")
                    except:
                        print_exception()

                elif self.name in ('reference', 'transforming', 'reference-data', 'transforming-data'):
                    if self.name in ('reference-data', 'transforming-data'):
                        s = self.s
                        l = self.l
                    else:
                        s = cfg.mw.dm.level
                        l = cfg.mw.dm.zpos

                    method = cfg.mw.dm.method(s=s, l=l)

                    img_size = cfg.mw.dm.image_size()
                    # sf = self.r.getCoords()[2] / img_size[0]  # level_key factor
                    sf = (self.r.getCoords()[2] - self.r.getCoords()[0]) / img_size[0]  # level_key factor

                    if 'grid' in method:
                        regions = cfg.mw.dm.get_grid_custom_regions(s=s, l=l)
                        ww1x1 = cfg.mw.dm.size1x1(s=s, l=l)
                        ww2x2 = cfg.mw.dm.size2x2(s=s, l=l)

                        a = [(img_size[0] - ww1x1[0])/2 + ww2x2[0]/2, (img_size[1] - ww1x1[1])/2 + ww2x2[1]/2]
                        b = [img_size[0] - a[0], img_size[1] - a[1]]

                        if regions[0]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[0]), 2, Qt.DotLine))
                            rect = get_rect(sf, a[0], a[1], ww2x2[0], self.r.getCoords())
                            qp.drawRect(rect)
                        if regions[1]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[1]), 2, Qt.DotLine))
                            rect = get_rect(sf, b[0], a[1], ww2x2[0], self.r.getCoords())
                            qp.drawRect(rect)
                        if regions[2]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[2]), 2, Qt.DotLine))
                            rect = get_rect(sf, a[0], b[1], ww2x2[0], self.r.getCoords())
                            qp.drawRect(rect)
                        if regions[3]:
                            qp.setPen(QPen(QColor(cfg.glob_colors[3]), 2, Qt.DotLine))
                            rect = get_rect(sf, b[0], b[1], ww2x2[0], self.r.getCoords())
                            qp.drawRect(rect)

                    elif method == 'manual':

                        #Todo... cant use manpoints_mir...

                        pts = []
                        # ww = cfg.mw.dm.manual_swim_window_px(s=s, l=l)
                        ww = cfg.mw.dm.manual_swim_window_px(s=s, l=l)
                        if self.name in ('reference','reference-data'):
                            if self.name == 'reference-data':
                                pts = cfg.mw.dm.manpoints_mir('ref', s=s, l=l)
                            else:
                                pts = cfg.mw.dm.manpoints_mir('ref')
                        elif self.name in ('transforming', 'transforming-data'):
                            if self.name == 'transforming-data':
                                pts = cfg.mw.dm.manpoints_mir('base', s=s, l=l)
                            else:
                                pts = cfg.mw.dm.manpoints_mir('base')
                        for i,pt in enumerate(pts):
                            if pt:
                                qp.setPen(QPen(QColor(cfg.glob_colors[i]), 2, Qt.DotLine))
                                x = int(pt[0])
                                y = int(pt[1])
                                r = get_rect(sf, x, y, ww, self.r.getCoords())
                                qp.drawRect(r)


                if self.extra:
                    qp.setPen(QColor('#ede9e8'))
                    loc = QPoint(0, self.rect().height() - 4)
                    if self.extra:
                        qp.drawText(loc, self.extra)
                return

            except:
                # logger.warning('Cannot divide by zero')
                print_exception()
                self.set_no_image()
        super().paintEvent(event)

    # def sizeHint(self):
    #     return QSize(100,100)

    # def resizeEvent(self, e):
    #     self.setMinimumWidth(self.height())



@cache
def get_rect(sf, x, y, ww, coords):
    rect = QRect(QPoint(int(x*sf), int(y*sf)), QSize(int(ww*sf), int(ww*sf)))
    rect.moveCenter(QPoint(int(x*sf), int(y*sf)) + QPoint(coords[0], coords[1]))
    #0716 + QPoint(coords[0], coords[1]) provides translation correction
    return rect



@cache
def get_default_grid_rects(sf, img_size, ww, cp_x, cp_y, coords):
    # half_ww = [int(ww[0] / 2), int(ww[1] / 2)]
    logger.warning(f'coords = {coords}')
    logger.warning(f'x = {coords[0]}')
    logger.warning(f'y = {coords[1]}')
    logger.warning(f'type = {type(coords)}')

    a = ((img_size[0] - ww[0]) / 2, (img_size[1] - ww[1]) / 2)
    # b = (int((a[0] + ww[0])), int((a[1] + ww[1])))
    # # cp = (int(tn_size[0]/2), int(tn_size[1]/2))
    # rx1 = int(a[0] * sf) # ratio x1 (short)
    # ry1 = int(a[1] * sf) # ratio y1 (short)
    # rx2 = int(b[0] * sf) # ratio x2 (long)
    # ry2 = int(b[1] * sf)  # ratio y3 (long)

    rx1 = int(a[0] * sf)           # ratio x1 (short)
    ry1 = int(a[1] * sf)                        # ratio y1 (short)
    rx2 = int((a[0] + ww[0]) * sf)              # ratio x2 (long)
    ry2 = int((a[1] + ww[1]) * sf)            # ratio y3 (long)

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
    # logger.critical(f"rx1={rx1}, ry1={ry1}, rx2={rx2}, ry2={ry2}")
    # logger.critical(f"a={a}, cp={cp}")
    # logger.critical(f"p1={p1}, p2={p2}, p3={p3}, p4={p4}")
    # yield QRect(p1, cp)
    # yield QRect(p2, cp)
    # yield QRect(p3, cp)
    # yield QRect(p4, cp)
    return (QRect(p1, cp + QPoint(-1,-1)), QRect(p2, cp + QPoint(1,-1)), QRect(p4, cp + QPoint(-1,1)), QRect(p3, cp + QPoint(1,1)))



class CorrSignalThumbnail(QLabel):
    # def __init__(self, parent, file_path='', snr='', extra='', name=''):
    def __init__(self, parent, path='', snr='', extra='', name='', annotations=True):
        super().__init__(parent)
        self.setScaledContents(True)
        self._noImage = 0
        self.path = path
        self.annotations = annotations
        self.setPixmap(QPixmap(32, 32))
        self.siz = None
        # self.snr = snr
        self.snr = 0.0
        self.extra = extra
        self.name = name
        if self.path:
            # logger.info(f'name = {name} / file_path = {self.file_path}')
            try:
                # self.setPixmap(QPixmap(file_path))
                self.setPixmap(QPixmap.fromImage(QImage(path)))
                self.siz = ImageSize(path)
            except:
                logger.warning(f"Failed to load: {path}")
                self.set_no_image()
        else:
            pixmap = QPixmap(32, 32)
            self.setPixmap(pixmap)

        self.setContentsMargins(0,0,0,0)

        self.map_border_color = {
            'ms0': cfg.glob_colors[0],
             'ms1': cfg.glob_colors[1],
             'ms2': cfg.glob_colors[2],
             'ms3': cfg.glob_colors[3]
        }
        # self.setStyleSheet("background-color: #f3e9df; font-size: 10px; font-family: 'Consolas';") #1030-

        self.setAutoFillBackground(True)


    def paintEvent(self, event):
        # logger.info(f"[{caller_name()}]")

        if self.pixmap():
            try:
                # originalRatio = pm.width() / pm.height()
                # currentRatio = self.width() / self.height()level
                # if originalRatio != currentRatio:
                qp = QPainter(self)
                # pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.r = QRect(0, 0, pm.width(), pm.height())
                self.r.moveCenter(self.rect().center())
                qp.drawPixmap(self.r, pm)
                # if (pm.width() == 0) or (pm.height() == 0):
                #     return
                if not self.annotations:
                    return
                if not cfg.mw.dm['state']['annotate_match_signals']:
                    return

                coords = self.r.getCoords()

                p1 = QPoint(coords[0], coords[1])
                p2 = QPoint(coords[2], coords[1])
                p3 = QPoint(coords[0], coords[3])
                p4 = QPoint(coords[2], coords[3])

                if self.name in self.map_border_color:
                    qp.setPen(QPen(QColor(self.map_border_color[self.name]), 0, Qt.SolidLine))
                    qp.setBrush(QBrush(QColor(self.map_border_color[self.name])))
                    # qp.drawLines(p1,p2 , p1,p3,  p4,p2 , p4,p3)
                    qp.drawRect(0,0,20,20)

                if self._noImage or self.extra == 'reticle':
                    self.pixmap().fill(QColor('#dadada'))
                    font = QFont()
                    size = max(min(int(11 * (max(pm.height(), 1) / 120)), 13), 5)
                    font.setPointSize(size)
                    # font.setBold(True)
                    qp.setFont(font)
                    qp.setPen(QColor('#161c20'))
                    # qp.drawText(QRectF(0, 0, pm.width(), pm.height()), Qt.AlignCenter, "No Signal")
                    qp.drawText(QRectF(p1, p4), Qt.AlignCenter, "No Signal")
                else:

                    cp = QPointF(self.r.center())  # center point

                    # qp.setPen(QPen(Qt.red, 1, Qt.DashLine))
                    qp.setPen(QPen(QColor('#fd411e'), 1, Qt.DashLine))

                    # x = 12
                    x = int((pm.width() / 10) + .5)

                    qp.drawLines(p1, cp + QPoint(-x, -x),
                                 p2, cp + QPoint(x, -x),
                                 p3, cp + QPoint(-x, x),
                                 p4, cp + QPoint(x, x))

                    qp.setPen(QPen(QColor('#fd411e'), 1, Qt.SolidLine))

                    d = float(sqrt(x ** 2 + x ** 2)) * 2

                    # arcRect = QRectF(cp + QPoint(int(-siz/2 + .5), int(-siz/2 + .5)), cp + QPointF(int(siz/2 + .5), int(siz/2 + .5)))
                    arcRect = QRectF(cp + QPointF(-d, -d), cp + QPointF(d, d))
                    spanAngle = 30
                    qp.drawArc(arcRect, 30*16, spanAngle*16)
                    qp.drawArc(arcRect, 30*16 + 180*16, spanAngle*16)
                    qp.drawArc(arcRect, 30*16 + 90*16, spanAngle*16)
                    qp.drawArc(arcRect, 30*16 + 270*16, spanAngle*16)

                    font = QFont()
                    font.setFamily('Tahoma')
                    fsize = max(int(pm.height() / 10 + 0.5), 5)
                    font.setPointSize(fsize)
                    font.setWeight(10)
                    qp.setFont(font)
                    # qp.setPen(QColor('#d0342c'))
                    qp.setPen(QColor('#fd411e'))
                    # qp.setBrush(QColor('#2774ae'))

                    # coords: x, y, w, h
                    # lower left
                    p0_x = coords[0] + 10
                    p0_y = coords[3]
                    # upper right
                    p1_x = int(pm.width()/2 + 0.5)
                    p1_y = coords[1] + fsize

                    textFill = QColor('#ffffff')
                    textFill.setAlpha(128)
                    qp.fillRect(QRect(QPoint(p0_x-2,p0_y-fsize), QSize(int(fsize*5),fsize)), QBrush(textFill))
                    qp.fillRect(QRect(QPoint(p1_x-2,p1_y-fsize), QSize(int(fsize*6),int(fsize*1.2))), QBrush(textFill))

                    if self.siz:
                        self.extra = f"{self.siz[0]}x{self.siz[1]}px"

                    if self.snr:
                        # qp.drawRect(p0_x-2,p0_y-12,60,16)
                        qp.drawText(QPointF(p0_x, p0_y), 'SNR: %.3g' %float(self.snr))
                        if self.extra:
                            qp.drawText(QPointF(p1_x, p1_y), self.extra)
                return
            # except ZeroDivisionError:
            except:
                # logger.warning('Cannot divide by zero')
                print_exception()
        super().paintEvent(event)


    def set_data(self, path, snr):
        # logger.critical('')
        self._noImage = 0
        self.path = path
        self.snr = snr
        try:
            # self.setPixmap(QPixmap(self.file_path))
            # self.setPixmap(QPixmap(self.file_path))
            # self.label.setText('%.3f' % self.snr)
            if os.path.exists(path):
                self.setPixmap(QPixmap.fromImage(QImage(path)))
                self.siz = ImageSize(self.path)
            else:
                self.set_no_image()

        except:
            print_exception()
            self.set_no_image()
            logger.warning(f'WARNING path={self.path}, label={self.snr}')
        # finally:
        #     self.update()

    def set_no_image(self):
        # self.snr = None #0826-
        self.snr = 0.0
        self._noImage = 1
        self.pixmap().fill(QColor('#dadada'))
        self.update()


def convert_rotation(degrees):
    deg2rad = 2*np.pi/360.
    return np.sin(deg2rad*degrees)