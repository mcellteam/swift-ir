#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap
import numpy as np
from math import sqrt
from functools import cache

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QTableWidget, QTableWidgetItem, QSlider, QSizePolicy
from qtpy.QtCore import Qt, QRect, QRectF, QSize, QPoint, QEvent, QPointF, QSizeF, Signal
from qtpy.QtGui import QPixmap, QPainter, QColor, QBrush, QFont, QPen, QMouseEvent, QImage
from src.helpers import absFilePaths
from src.helpers import print_exception, get_appdir
from src.funcs_image import ImageSize, ImageIOSize

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
        self.label = QLabel('%.3g' % self.snr)
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
        finally:
            self.update()

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
    clicked = Signal(QMouseEvent)
    left_click = Signal(float, float)

    def __init__(self, parent, path='', extra='', name='', s=None, l=None):
        super().__init__(parent)
        self.setScaledContents(True)
        self._noImage = 0
        self.path = path
        pixmap = QPixmap(32, 32)
        self.setPixmap(pixmap)

        if self.path:
            image = QImage(path)
            # self.setPixmap(QPixmap.fromImage(image).scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if os.path.exists(path):
                self.setPixmap(QPixmap.fromImage(QImage(path)))
            else:
                self.set_no_image()


            # self.setPixmap(QPixmap(self.path))
        else:
            self.set_no_image()

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

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # policy.setHeightForWidth(True)
        # self.setSizePolicy(policy)


    def mousePressEvent(self, e):
        x, y, = (
            e.x(),
            e.y(),
        )
        print(f"{x} , {y}")
        # if self.pixmap:
        #     r = self.pixmap().rect()
        #     x0, y0 = r.x(), r.y()
            # x1, y1 = x0 + r.width(), y0 + r.height()
            # if x >= x0 and x < x1 and y >= y0 and y < y1:
            #     x_relative = (x - x0) / (x1 - x0)
            #     y_relative = (y - y0) / (y1 - y0)
            #     self.left_click.emit(x_relative, y_relative)
            #     print(f"{x_relative} , {x_relative}")

        super().mousePressEvent(e)

    def showPixmap(self):
        self._noImage = 0
        # self.setPixmap(QPixmap(self.path))
        self.setPixmap(QPixmap.fromImage(QImage(self.path)))
        self.update()

    # def selectPixmap(self, path:str):
    #     if os.path.isdir(path):
    #         self.set_no_image()
    #     else:
    #         self._noImage = 0
    #         try:
    #             self.path = path
    #             self.setPixmap(QPixmap(self.path))
    #         except:
    #             print_exception()
    #             self.set_no_image()
    #         finally:
    #             self.update()

    #From CorrSignalThumbnail
    def set_data(self, path):
        # logger.critical('')
        self._noImage = 0
        self.path = path
        try:
            # self.setPixmap(QPixmap(self.path))
            # self.label.setText('%.3f' % self.snr)

            if os.path.exists(path):
                self.setPixmap(QPixmap.fromImage(QImage(path)))
            else:
                self.set_no_image()

        except:
            print_exception(extra=f'WARNING path={self.path}')
            self.set_no_image()
        finally:
            self.update()

    #Prev
    # def set_no_image(self):
    #     self._noImage = 1
    #     self.snr = None
    #     try:
    #         self.setPixmap(QPixmap(self.no_image_path))
    #     except:
    #         print_exception()
    #         logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')
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

                self.r = QRect(0, 0, pm.width(), pm.height())
                self.r.moveCenter(self.rect().center())
                qp.drawPixmap(self.r, pm)


                coords = self.r.getCoords()
                p1 = QPoint(coords[0], coords[1])
                p2 = QPoint(coords[2], coords[1])
                p3 = QPoint(coords[0], coords[3])
                p4 = QPoint(coords[2], coords[3])


                if self.name in self.map_border_color:
                    qp.setPen(QPen(QColor(self.map_border_color[self.name]), 3, Qt.SolidLine))
                    qp.drawLines(p1, p2, p1, p3, p4, p2, p4, p3)

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

                elif self.name in ('reference', 'transforming', 'reference-table', 'transforming-table'):
                    if self.name in ('reference-table', 'transforming-table'):
                        method = cfg.data.method(s=self.s, l=self.l)
                        s = self.s
                        l = self.l
                    else:
                        method = cfg.data.current_method
                        s = cfg.data.scale_key
                        l = cfg.data.zpos

                    img_size = cfg.data.image_size()
                    # sf = self.r.getCoords()[2] / img_size[0]  # scale_key factor
                    sf = (self.r.getCoords()[2] - self.r.getCoords()[0]) / img_size[0]  # scale_key factor

                    if method == 'grid-default':
                        # cp = QPoint(self.r.center())  # center point
                        # ww = tuple(cfg.data['data']['defaults'][cfg.data.scale_key]['swim-window-px'])
                        # for i,r in enumerate(get_default_grid_rects(sf, img_size, ww, cp.x(), cp.y(), self.r.getCoords())):
                        #     qp.setPen(QPen(QColor(cfg.glob_colors[i]), 2, Qt.DotLine))
                        #     qp.drawRect(r)

                        ww1x1 = cfg.data['data']['defaults'][cfg.data.scale_key]['swim-window-px']
                        ww2x2 = [x / 2 for x in ww1x1]

                        a = [(img_size[0] - ww1x1[0])/2 + ww2x2[0]/2, (img_size[1] - ww1x1[1])/2 + ww2x2[1]/2]
                        b = [img_size[0] - a[0], img_size[1] - a[1]]

                        qp.setPen(QPen(QColor(cfg.glob_colors[0]), 2, Qt.DotLine))
                        qp.drawRect(get_rect(sf, a[0], a[1], ww2x2[0], self.r.getCoords()))
                        qp.setPen(QPen(QColor(cfg.glob_colors[1]), 2, Qt.DotLine))
                        qp.drawRect(get_rect(sf, b[0], a[1], ww2x2[0], self.r.getCoords()))
                        qp.setPen(QPen(QColor(cfg.glob_colors[2]), 2, Qt.DotLine))
                        qp.drawRect(get_rect(sf, a[0], b[1], ww2x2[0], self.r.getCoords()))
                        qp.setPen(QPen(QColor(cfg.glob_colors[3]), 2, Qt.DotLine))
                        qp.drawRect(get_rect(sf, b[0], b[1], ww2x2[0], self.r.getCoords()))

                    elif method == 'grid-custom':
                        regions = cfg.data.get_grid_custom_regions(s=s, l=l)
                        ww1x1 = cfg.data.swim_1x1_custom_px(s=s, l=l)
                        ww2x2 = cfg.data.swim_2x2_custom_px(s=s, l=l)

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

                    elif method == 'manual-hint':
                        pts = []
                        ww = cfg.data.manual_swim_window_px(s=s, l=l)
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



            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                # print_exception()
                self.set_no_image()
        super().paintEvent(event)

    # def sizeHint(self):
    #     return QSize(100,100)

    # def resizeEvent(self, e):
    #     self.setMinimumWidth(self.height())



@cache
def get_rect(sf, x, y, ww, coords):
    # rect = QRect(QPoint(int(x*sf), int(y*sf)), QSize(int(ww*sf), int(ww*sf)))
    # rect.moveCenter(QPoint(int(x*sf), int(y*sf)))
    rect = QRect(QPoint(int(x*sf), int(y*sf)), QSize(int(ww*sf), int(ww*sf)))
    rect.moveCenter(QPoint(int(x*sf), int(y*sf)) + QPoint(coords[0], coords[1])) #0716 + QPoint(coords[0], coords[1]) provides translation correction
    return rect


    # return QRect(QPointF(x*sf, y*sf), QSizeF(ww*sf, ww*sf))



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


    #orig
    # rx1 = int(a[0] * sf)  # ratio x1 (short)
    # ry1 = int(a[1] * sf)  # ratio y1 (short)
    # rx2 = int((a[0] + ww[0]) * sf)  # ratio x2 (long)
    # ry2 = int((a[1] + ww[1]) * sf)  # ratio y3 (long)

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
    # def __init__(self, parent, path='', snr='', extra='', name=''):
    def __init__(self, parent, path='', snr='', extra='', name=''):
        super().__init__(parent)
        self.setScaledContents(True)
        self._noImage = 0
        self.path = path
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor('#dadada'))  # fill the map with black
        self.setPixmap(pixmap)
        if self.path:
            # image = QImage(path)
            # self.setPixmap(QPixmap.fromImage(image).scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if os.path.exists(path):
                self.setPixmap(QPixmap.fromImage(QImage(path)))
            else:
                self.set_no_image()

            # self.setPixmap(QPixmap(self.path))
        else:
            # pixmap = QPixmap(16, 16)
            # pixmap.fill(QColor('#141414'))  # fill the map with black
            # self.setPixmap(pixmap)
            self.set_no_image()

        # self.snr = snr
        self.snr = 0.0
        self.extra = extra
        self.name = name
        self.no_image_path = os.path.join(get_appdir(), 'resources', 'no-image.png')
        # self.setStyleSheet("""border: 0px solid #ffe135;""")
        self.setContentsMargins(0,0,0,0)

        self.map_border_color = {
            'ms0': cfg.glob_colors[0],
             'ms1': cfg.glob_colors[1],
             'ms2': cfg.glob_colors[2],
             'ms3': cfg.glob_colors[3]
        }

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


    def paintEvent(self, event):

        if self.pixmap():
            try:
                # originalRatio = pm.width() / pm.height()
                # currentRatio = self.width() / self.height()s
                # if originalRatio != currentRatio:

                qp = QPainter(self)
                # pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pm = self.pixmap().scaled(self.size() - QSize(4, 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)

                self.r = QRect(0, 0, pm.width(), pm.height())
                self.r.moveCenter(self.rect().center())
                qp.drawPixmap(self.r, pm)
                # if (pm.width() == 0) or (pm.height() == 0):

                coords = self.r.getCoords()

                p1 = QPoint(coords[0], coords[1])
                p2 = QPoint(coords[2], coords[1])
                p3 = QPoint(coords[0], coords[3])
                p4 = QPoint(coords[2], coords[3])

                if self.name in self.map_border_color:
                    qp.setPen(QPen(QColor(self.map_border_color[self.name]), 3, Qt.SolidLine))
                    qp.drawLines(p1,p2 , p1,p3,  p4,p2 , p4,p3)

                if self._noImage or self.extra == 'reticle':
                    self.pixmap().fill(QColor('#dadada'))
                    font = QFont()
                    size = max(min(int(11 * (max(pm.height(), 1) / 80)), 14), 5)
                    font.setPointSize(size)
                    # font.setBold(True)
                    qp.setFont(font)
                    qp.setPen(QColor('#161c20'))
                    # qp.drawText(QRectF(0, 0, pm.width(), pm.height()), Qt.AlignCenter, "No Signal")
                    qp.drawText(QRectF(p1, p4), Qt.AlignCenter, "No Signal")
                else:

                    cp = QPointF(self.r.center())  # center point

                    # qp.setPen(QPen(Qt.red, 1, Qt.DashLine))
                    qp.setPen(QPen(QColor('#339933'), 1, Qt.DashLine))

                    # x = 12
                    x = int((pm.width() / 10) + .5)

                    qp.drawLines(p1, cp + QPoint(-x, -x),
                                 p2, cp + QPoint(x, -x),
                                 p3, cp + QPoint(-x, x),
                                 p4, cp + QPoint(x, x))

                    qp.setPen(QPen(QColor('#339933'), 1, Qt.SolidLine))

                    d = float(sqrt(x ** 2 + x ** 2)) * 2

                    # arcRect = QRectF(cp + QPoint(int(-siz/2 + .5), int(-siz/2 + .5)), cp + QPointF(int(siz/2 + .5), int(siz/2 + .5)))
                    arcRect = QRectF(cp + QPointF(-d, -d), cp + QPointF(d, d))
                    spanAngle = 30
                    qp.drawArc(arcRect, 30*16, spanAngle*16)
                    qp.drawArc(arcRect, 30*16 + 180*16, spanAngle*16)
                    qp.drawArc(arcRect, 30*16 + 90*16, spanAngle*16)
                    qp.drawArc(arcRect, 30*16 + 270*16, spanAngle*16)

                    font = QFont()
                    size = max(min(int(11 * (max(pm.height(), 1) / 60)), 14), 5)
                    font.setPointSize(size)
                    font.setBold(True)
                    qp.setFont(font)
                    qp.setPen(QColor('#141414'))

                    if self.snr:
                        # loc = QPoint(0, self.rect().height() - 4)
                        # loc = QPoint(16, self.rect().height() - 6)
                        loc = QPointF(coords[0] + pm.width()/2 - size, coords[3] - 2)
                        try:
                            if self.extra:
                                qp.drawText(loc, '%.3g' %float(self.snr) + '\n' + self.extra)
                            else:
                                qp.drawText(loc, '%.3g' %float(self.snr))
                        except:
                            print_exception()
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
            # self.setPixmap(QPixmap(self.path))
            # self.setPixmap(QPixmap(self.path))
            # self.label.setText('%.3f' % self.snr)
            if os.path.exists(path):
                self.setPixmap(QPixmap.fromImage(QImage(path)))
            else:
                self.set_no_image()

        except:
            print_exception()
            self.set_no_image()
            logger.warning(f'WARNING path={self.path}, label={self.snr}')
        finally:
            self.update()

    def set_no_image(self):
        self.snr = None
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

        # try:
        #     # self.setPixmap(QPixmap(self.no_image_path))
        #     # self.update()
        # except:
        #     print_exception()
        #     logger.warning(f'WARNING path={self.no_image_path}, label={self.snr}')


def convert_rotation(degrees):
    deg2rad = 2*np.pi/360.
    return np.sin(deg2rad*degrees)