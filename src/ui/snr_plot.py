#!/usr/bin/env python3

'''
SNR Plot Class. Depends on 'pyqtgraph' Python module.
https://github.com/robertsj/poropy/blob/master/pyqtgraph/graphicsItems/ScatterPlotItem.py
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ScatterPlotItem.html
'''
import os
import sys
from math import ceil
import logging

import pyqtgraph as pg
from qtpy.QtWidgets import QMainWindow, QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox
from qtpy.QtGui import QFont
from qtpy.QtCore import Qt, QSize

from src.helpers import print_exception, is_arg_scale_aligned, get_scale_val

import src.config as cfg

logger = logging.getLogger(__name__)


class SnrPlot(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.app = pg.mkQApp()
        self.view = pg.GraphicsLayoutWidget()
        self.plot = self.view.addPlot()

        self.spw = pg.ScatterPlotWidget()
        # self.spw.

        # self.plot = pg.PlotWidget()
        # self.plot.setAntialiasing(False)
        # pg.setConfigOptions(antialias=True)
        self._plot_colors = ['#FF007F', '#66FF00', '#08E8DE',
                             '#8c001a', '#2CBFF7', '#c7b286',
                             '#56768e', '#376d58', '#f46c60',
                             '#c9cbd0', '#fbd771', '#ff9a00'
                             ]

        self._plot_brushes = [pg.mkBrush(c) for c in self._plot_colors]

        self.plot.scene().sigMouseClicked.connect(self.mouse_clicked)

        # self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True, alpha=220)  # alpha: 0-255
        # self.plot.getPlotItem().enableAutoRange()
        self.plot.hoverable = True
        self.plot.hoverSize = 11
        # self.plot.setFocusPolicy(Qt.NoFocus)
        font = QFont()
        font.setPixelSize(14)
        self.plot.getAxis("bottom").tickFont = font
        self.plot.getAxis("bottom").setStyle(tickFont=font)
        self.plot.getAxis("bottom").setHeight(24)
        self.plot.getAxis("left").setStyle(tickFont=font)
        self.plot.getAxis("left").setWidth(28)
        self.plot.getAxis("left").setStyle(tickTextOffset=2)
        style = {'color': '#f3f6fb;', 'font-size': '14px'}
        self.plot.setLabel('left', 'SNR', **style)
        self.plot.setLabel('bottom', 'Layer #', **style)

        self.plot.setCursor(Qt.CrossCursor)

        self.snr_points = {}

        self.checkboxes_widget = QWidget()
        self.checkboxes_hlayout = QHBoxLayout()
        self.checkboxes_hlayout.setContentsMargins(0, 0, 0, 0)
        self.checkboxes_widget.setLayout(self.checkboxes_hlayout)

        self.layout = QGridLayout()
        # self.layout.addWidget(self.plot, 0, 0, 1, 5)
        self.layout.addWidget(self.view, 0, 0, 1, 5)
        self.layout.addWidget(self.checkboxes_widget, 0, 4, 1, 1)
        self.layout.setContentsMargins(4, 2, 4, 2)
        self.setLayout(self.layout)
        self.setAutoFillBackground(False)



    def initSnrPlot(self, s=None):
        try:
            self.wipePlot()
            self._snr_checkboxes = dict()
            for i, s in enumerate(cfg.data.scales()[::-1]):
                self._snr_checkboxes[s] = QCheckBox()
                self._snr_checkboxes[s].setText('s' + str(get_scale_val(s)))
                self.checkboxes_hlayout.addWidget(self._snr_checkboxes[s],
                                                  alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                self._snr_checkboxes[s].setChecked(True)
                self._snr_checkboxes[s].clicked.connect(self.plotData)
                self._snr_checkboxes[s].setStatusTip('On/Off SNR Plot Scale %d' % get_scale_val(s))
                color = self._plot_colors[cfg.data.scales().index(s)]
                self._snr_checkboxes[s].setStyleSheet('background-color: #F3F6FB;'
                                                      'border-color: %s; '
                                                      'border-width: 2px; '
                                                      'border-style: outset;' % color)
                if is_arg_scale_aligned(scale=s):
                    self._snr_checkboxes[s].show()
                else:
                    self._snr_checkboxes[s].hide()
            self.checkboxes_hlayout.addStretch()
            self.plotData()
        except:
            print_exception()


    def get_axis_data(self, s=None) -> tuple:
        if s == None: s = cfg.data.scale()
        x_axis, y_axis = [], []
        for layer, snr in enumerate(cfg.data.snr_list(s=s)):
            if cfg.data.skipped(s=s, l=layer):
                x_axis.append(layer)
                y_axis.append(0)
            else:
                x_axis.append(layer)
                y_axis.append(snr)
        return x_axis, y_axis


    def plotData(self):
        logger.info('plotData:')
        '''Update SNR plot widget based on checked/unchecked state of checkboxes'''
        logger.info('plotData:')
        if cfg.data:
            self.plot.clear()
            for i, scale in enumerate(cfg.data.scales()[::-1]):
                if is_arg_scale_aligned(scale=scale):
                    if self._snr_checkboxes[scale].isChecked():
                        self.plotSingleScale(scale=scale)
            max_snr = cfg.data.snr_max_all_scales()
            logger.info(f'max_snr: {max_snr}')
            self.plot.setLimits(xMin=0, xMax=cfg.data.n_layers(), yMin=0, yMax=ceil(max_snr) + 1)
            # self.plot.autoRange()


    def plotSingleScale(self, scale=None):
        logger.info(f'plotSingleScale (scale: {scale}):')
        if scale == None: scale = cfg.data.scale()
        x_axis, y_axis = self.get_axis_data(s=scale)
        brush = self._plot_brushes[cfg.data.scales().index(scale)]
        self.snr_points[scale] = pg.ScatterPlotItem(
            size=7,
            pen=pg.mkPen(None),
            brush=brush,
            hoverable=True,
            # hoverSymbol='s',
            hoverSize=11,
            # hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('#ffffff'),
            # pxMode=False # points transform with zoom
        )
        self.snr_points[scale].addPoints(x_axis[1:], y_axis[1:])
        # logger.info('self.snr_points.toolTip() = %s' % self.snr_points.toolTip())
        # value = self.snr_points.setToolTip('Test')
        self.last_snr_click = []
        self.plot.addItem(self.snr_points[scale])
        self.snr_points[scale].sigClicked.connect(self.onSnrClick)


    def wipePlot(self):
        try:
            for i in reversed(range(self.checkboxes_hlayout.count())):
                self.checkboxes_hlayout.removeItem(self.checkboxes_hlayout.itemAt(i))
            self.plot.clear()
            # try:
            #     del self._snr_checkboxes
            # except:
            #     print_exception()
        except:
            logger.warning('Unable To Wipe SNR Plot')


    def mouse_clicked(self, mouseClickEvent):
        # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
        print('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
        pos_click = int(mouseClickEvent.pos()[0])
        print('Position Clicked: %d' % pos_click)


    def onSnrClick(self, plot, points):
        logger.info('onSnrClick:')
        index = int(points[0].pos()[0])
        snr = float(points[0].pos()[1])
        cfg.main_window.hud.post(f'Layer: {index}, SNR: {snr}')
        clickedPen = pg.mkPen({'color': "#FF0000", 'width': 1})
        for p in self.last_snr_click:
            p.resetPen()
            p.resetBrush()
        for p in points:
            p.setBrush(pg.mkBrush('#ffffff'))
            p.setPen(clickedPen)
        self.last_snr_click = points
        cfg.main_window.jump_to(index)

    def sizeHint(self):
        if cfg.main_window:
            width = int(cfg.main_window.width() / 2)
        else:
            width = int(cfg.WIDTH / 2)
        return QSize(width, 100)


'''
>>> import pyqtgraph.examples
>>> 
>>> pyqtgraph.examples.run()

'''

if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    plot = SnrPlot()
    main_window.setCentralWidget(plot)
    main_window.show()
    sys.exit(app.exec_())