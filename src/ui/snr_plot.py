#!/usr/bin/env python3

'''
SNR Plot Class. Depends on 'pyqtgraph' Python module.
https://github.com/robertsj/poropy/blob/master/pyqtgraph/graphicsItems/ScatterPlotItem.py
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ScatterPlotItem.html
'''
import os
import sys
from math import ceil
import inspect
import logging
from functools import partial
import numpy as np
import pyqtgraph as pg
from qtpy.QtWidgets import QMainWindow, QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox
from qtpy.QtGui import QFont
from qtpy.QtCore import Qt, QSize
from src.helpers import print_exception, exist_aligned_zarr_cur_scale, exist_aligned_zarr, get_scale_val
import src.config as cfg

logger = logging.getLogger(__name__)


class SnrPlot(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # cfg.data = None

        self.app = pg.mkQApp()
        self.view = pg.GraphicsLayoutWidget()
        # self.view.setBackground('#ffffff')
        drafting_blue = '#004060'
        self.view.setBackground(drafting_blue)
        pg.setConfigOption('foreground', '#f3f6fb')
        self.plot = self.view.addPlot()
        self.vb = CustomViewBox()

        # self.spw = pg.ScatterPlotWidget() #Todo switch to scatter plot widget for greater interactivity

        # pg.setConfigOptions(antialias=True)
        self._plot_colors = ['#FEFE62', '#40B0A6', '#D41159',
                             '#E66100', '#1AFF1A', '#FFC20A',
                             '#66FF00', '#8c001a', '#08E8DE',
                             '#56768e', '#2CBFF7', '#c7b286',
                             '#FF007F', '#376d58', '#f46c60',
                             '#c9cbd0', '#fbd771', '#ff9a00'
                             ]

        self._plot_brushes = [pg.mkBrush(c) for c in self._plot_colors]

        # self.plot.scene().sigMouseClicked.connect(self.mouse_clicked)

        # self.plot.setAspectLocked(True)
        self.plot.showGrid(x=False, y=True, alpha=120)  # alpha: 0-255
        # self.plot.getPlotItem().enableAutoRange()
        self.plot.hoverable = True
        self.plot.hoverSize = 15
        # self.plot.setFocusPolicy(Qt.NoFocus)
        # font = QFont()
        # font.setPixelSize(14)
        # self.plot.getAxis("bottom").tickFont = font
        # self.plot.getAxis("bottom").setStyle(tickFont=font)
        # self.plot.getAxis("left").setStyle(tickFont=font)
        # self.plot.getAxis("bottom").setHeight(12)
        # self.plot.getAxis("left").setWidth(12)
        self.plot.getAxis("left").setStyle(tickTextOffset=4)
        style = {'color': '#f3f6fb;', 'font-size': '14px'}

        self.plot.setCursor(Qt.CrossCursor)
        # self.plot.setAspectLocked()

        self.snr_points = {}
        self.snr_errors = {}
        self.selected_scale = None

        self.checkboxes_widget = QWidget()
        self.checkboxes_hlayout = QHBoxLayout()
        self.checkboxes_hlayout.setContentsMargins(0, 0, 0, 0)
        self.checkboxes_widget.setLayout(self.checkboxes_hlayout)

        # self.layout = QGridLayout()
        # self.layout.addWidget(self.view, 0, 0, 1, 5)
        # self.layout.addWidget(self.checkboxes_widget, 0, 4, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        # # self.layout.setContentsMargins(4, 2, 4, 2)
        # self.layout.setContentsMargins(0, 0, 0, 0)
        # self.setLayout(self.layout)

        self.layout = QGridLayout()
        self.layout.addWidget(self.view, 0, 0, 0, 0)
        self.layout.addWidget(self.checkboxes_widget, 0, 0, 0, 0, alignment=Qt.AlignmentFlag.AlignRight)
        # self.layout.setContentsMargins(4, 2, 4, 2)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.plot.scene().sigMouseClicked.connect(self.mouse_clicked)


    # def setData(self, data):
    #     self.data = data


    def initSnrPlot(self, s=None):
        if not cfg.data:
            logger.warning(f'initSnrPlot was called by {inspect.stack()[1].function} but data does not exist.')
            return
        try:
            self.wipePlot()
            self._snr_checkboxes = dict()
            for i, s in enumerate(cfg.data.scales()):
                self._snr_checkboxes[s] = QCheckBox()
                self._snr_checkboxes[s].setText(cfg.data.scale_pretty(s=s))
                self.checkboxes_hlayout.addWidget(self._snr_checkboxes[s],
                                                  alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                self._snr_checkboxes[s].setChecked(True)
                self._snr_checkboxes[s].clicked.connect(self.plotData)
                self._snr_checkboxes[s].setStatusTip('On/Off SNR Plot Scale %d' % get_scale_val(s))
                color = self._plot_colors[cfg.data.scales()[::-1].index(s)]
                self._snr_checkboxes[s].setStyleSheet(
                    f'background-color: #F3F6FB;'
                    f'border-color: {color}; '
                    f'border-width: 3px; '
                    f'border-style: outset;')
                if s in cfg.data.scalesAligned:
                    self._snr_checkboxes[s].show()
                else:
                    self._snr_checkboxes[s].hide()
            self.checkboxes_hlayout.addStretch()

        except:
            print_exception()
        try:
            self.plotData()
        except:
            print_exception()


    def get_axis_data(self, s=None) -> tuple:
        if s == None: s = cfg.data.curScale
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
        '''Update SNR plot widget based on checked/unchecked state of checkboxes'''
        if cfg.data:
            self.plot.clear()

            for s in cfg.data.scales()[::-1]:
                if exist_aligned_zarr(scale=s):
                    if self._snr_checkboxes[s].isChecked():
                        logger.info(f'{s} is aligned and checkbox is checked. Plotting its SNR data....')
                        self.plotSingleScale(s=s)
            if cfg.data.nScalesAligned:
                if cfg.data.nScalesAligned > 0:
                    max_snr = cfg.data.snr_max_all_scales()
                    assert max_snr is not None
                    assert type(max_snr) is float
                    # self.plot.setLimits(xMin=0, xMax=cfg.datamodel.n_layers(), yMin=0, yMax=ceil(max_snr) + 1)
                    # self.plot.setXRange(0, cfg.datamodel.n_layers(), padding=0)
                    # self.plot.setYRange(0, ceil(max_snr) + 1, padding=0)
                    # self.plot.setRange(xRange=[0, cfg.datamodel.n_layers() + 0.5])
                    # self.plot.setRange(yRange=[0, ceil(max_snr)])
                    xmax = cfg.data.nSections + 1
                    ymax = ceil(max_snr) + 5
                    self.plot.setLimits(
                        minXRange=1,
                        xMin=0,
                        xMax=xmax,
                        maxXRange=xmax,
                        yMin=0,
                        yMax=ymax,
                        minYRange=ymax,
                        maxYRange=ymax,
                    )
                    ax = self.plot.getAxis('bottom')  # This is the trick
                    dx = [(value, str(value)) for value in list((range(0, xmax - 1)))]
                    ax.setTicks([dx, []])

            self.plot.autoRange() # !!!


    def plotSingleScale(self, s=None):
        logger.info(f'plotSingleScale (scale: {s}):')
        if s == None: scale = cfg.data.scale()
        x_axis, y_axis = self.get_axis_data(s=s)
        offset = cfg.data.scales()[::-1].index(s) * (.5/cfg.data.nscales)
        x_axis = [x+offset for x in x_axis]

        brush = self._plot_brushes[cfg.data.scales()[::-1].index(s)]
        self.snr_points[s] = pg.ScatterPlotItem(
            size=11,
            pen=pg.mkPen(None),
            brush=brush,
            hoverable=True,
            # hoverSymbol='s',
            hoverSize=14,
            # hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('#ffffff'),
            # pxMode=False # points transform with zoom
        )
        self.snr_points[s].addPoints(x_axis[1:], y_axis[1:])
        # logger.info('self.snr_points.toolTip() = %s' % self.snr_points.toolTip())
        # value = self.snr_points.setToolTip('Test')
        self.last_snr_click = None
        self.plot.addItem(self.snr_points[s])
        # self.snr_points[s].sigClicked.connect(lambda: self.onSnrClick2(s))
        self.snr_points[s].sigClicked.connect(self.onSnrClick)

        errbars = cfg.data.snr_errorbars(s=s)
        n = cfg.data.nSections - 1
        deltas = np.zeros(n)
        y = np.zeros(n)
        x = np.arange(1, n + 1) + offset

        for i in range(0, n):
            deltas[i] = errbars[i]
            y[i]      = cfg.data.snr(s=s, l=i + 1)

        logger.info('Configuring Error Bars...')
        self.plot.addItem(pg.ErrorBarItem(x=x, y=y,
                                          top=deltas,
                                          bottom=deltas,
                                          beam=0.20,
                                          pen={'color': '#ff0000', 'width': 2}))


    def wipePlot(self):
        try:
            for i in reversed(range(self.checkboxes_hlayout.count())):
                self.checkboxes_hlayout.removeItem(self.checkboxes_hlayout.itemAt(i))
            del self._snr_checkboxes
            self.plot.clear()
            # try:
            #     del self._snr_checkboxes
            # except:
            #     print_exception()
        except:
            logger.warning('Unable To Wipe SNR Plot')


    def mouse_clicked(self, mouseClickEvent):
        if cfg.data:
            try:
                # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
                print('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
                pos_click = int(mouseClickEvent.pos()[0])
                print('Position Clicked: %d' % pos_click)
            except:
                pass

    def onSnrClick2(self, scale):
        logger.info(f'onSnrClick2 ({scale}):')
        self.selected_scale = scale
        cfg.main_window._cmbo_setScale.setCurrentText(scale)


    def onSnrClick(self, plot, points, scale):
        logger.info(f'onSnrClick ({scale}):')
        index = int(points[0].pos()[0])
        snr = float(points[0].pos()[1])
        pt = points[0] # just allow one point clicked
        cfg.main_window.hud.post('Jump to Section #%d (SNR: %.3f)' % (index, snr))
        clickedPen = pg.mkPen({'background-color': "#FF0000", 'width': 1})
        # for p in self.last_snr_click:
        #     p.resetPen()
        #     p.resetBrush()
        # for p in points:
        #     p.setBrush(pg.mkBrush('#ffffff'))
        #     p.setPen(clickedPen)
        if self.last_snr_click:
            self.last_snr_click.resetPen()
            self.last_snr_click.resetBrush()
        pt.setBrush(pg.mkBrush('#ffffff'))
        pt.setPen(clickedPen)
        # self.last_snr_click = points
        self.last_snr_click = pt
        cfg.main_window.jump_to(index)

    def sizeHint(self):
        if cfg.main_window:
            width = int(cfg.main_window.width() / 2)
        else:
            width = int(cfg.WIDTH / 2)
        return QSize(width, 100)


class CustomViewBox(pg.ViewBox):
    def __init__(self, *args, **kwds):
        kwds['enableMenu'] = False
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)

    ## reimplement right-click to zoom out
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self.autoRange()

    ## reimplement mouseDragEvent to disable continuous axis zoom
    def mouseDragEvent(self, ev, axis=None):
        if axis is not None and ev.button() == Qt.MouseButton.RightButton:
            ev.ignore()
        else:
            pg.ViewBox.mouseDragEvent(self, ev, axis=axis)


'''
>>> import pyqtgraph.examples
>>> 
>>> pyqtgraph.examples.run()

app = pg.mkQApp("Crosshair Example")


'''

if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    plot = SnrPlot()
    main_window.setCentralWidget(plot)
    main_window.show()
    sys.exit(app.exec_())