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
from qtpy.QtWidgets import QMainWindow, QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel
from qtpy.QtGui import QFont
from qtpy.QtCore import Qt, QSize
from src.helpers import print_exception
import src.config as cfg

logger = logging.getLogger(__name__)


class SnrPlot(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.app = pg.mkQApp()
        self.view = pg.GraphicsLayoutWidget()
        # self.view.setBackground('#1b1e23')
        self.view.setBackground('#222222')
        # drafting_blue = '#004060'
        # self.view.setBackground(drafting_blue)
        pg.setConfigOption('foreground', '#f3f6fb')
        pg.setConfigOptions(antialias=True)
        self.plot = self.view.addPlot()
        # self.label_value = pg.InfLineLabel('test', **{'color': '#FFF'})
        self._curLayerLine = pg.InfiniteLine(
            # pen='w',
            pen=pg.mkPen('w', width=3),
            movable=False,
            angle=90,
            label='Section #{value:.0f}',
            # snr=self.label_value,
            labelOpts={'position': .1, 'color': (200, 200, 100), 'fill': (200, 200, 200, 50), 'movable': True})
        # self._snr_label = pg.InfLineLabel(self._curLayerLine, '', position=0.95, rotateAxis=(1, 0),
        #                                  anchor=(1, 1))
        self._snr_label = pg.InfLineLabel(self._curLayerLine, '', position=0.92, anchor=(1, 1), color='#f3f6fb')
        f = QFont('Tahoma')
        f.setBold(True)
        f.setPointSize(12)
        self._snr_label.setFont(f)
        self.plot.addItem(self._curLayerLine)
        self._mp_lines = []
        self._mp_labels = []
        self._skip_lines = []
        self._skip_labels = []
        self._error_bars = {}

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
        # style = {'color': '#f3f6fb;', 'font-size': '14px'}

        self.plot.setCursor(Qt.CrossCursor)
        # self.plot.setAspectLocked()

        self.snr_points = {}
        self.snr_errors = {}
        self.selected_scale = None

        self.checkboxes_widget = QWidget()
        self.checkboxes_widget.setMaximumHeight(24)
        self.checkboxes_hlayout = QHBoxLayout()
        self.checkboxes_hlayout.setContentsMargins(0, 0, 0, 0)
        self.checkboxes_widget.setLayout(self.checkboxes_hlayout)

        self.layout = QGridLayout()
        self.layout.addWidget(self.view, 0, 0, 2, 2)
        self.layout.addWidget(self.checkboxes_widget, 0, 1, 1, 1,
                              alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.layout.setRowStretch(0,0)
        self.layout.setRowStretch(1,1)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # self.plot.scene().sigMouseClicked.connect(self.mouse_clicked)



    def updateLayerLinePos(self):
        caller = inspect.stack()[1].function
        # logger.info(f'caller={caller}')
        if cfg.data:
            offset = self._getScaleOffset(s=cfg.data.scale)
            pos = [cfg.data.zpos + offset, 1]
            # logger.info(f'pos = {pos}')
            self._curLayerLine.setPos(pos)
            # snr = pg.InfLineLabel(self._curLayerLine, "region 1", position=0.95, rotateAxis=(1, 0), anchor=(1, 1))
            lab = 'SNR: %.2f\n%s' % (cfg.data.snr(), cfg.data.scale_pretty())
            # logger.info(f'lab = {lab}')
            self._snr_label.setText(lab)
            styles = {'color': '#ede9e8', 'font-size': '14px', 'font-weight': 'bold'}
            self.plot.setLabel('top', cfg.data.base_image_name(), **styles)
        else:
            logger.warning(f'Cant update layer line caller={caller}')



    def updateSpecialLayerLines(self):
        logger.debug('')
        offset = self._getScaleOffset(s=cfg.data.scale)
        layers_mp = cfg.data.find_layers_with_manpoints()
        for line in self._mp_lines:   self.plot.removeItem(line)
        for label in self._mp_labels: self.plot.removeItem(label)
        self._mp_lines = []
        self._mp_labels = []
        for layer in layers_mp:
            line = pg.InfiniteLine(
                movable=False,
                angle=90,
                pen='#32CD32',
                # snr='Match Point #{value:.0f}',
                # # snr=self.label_value,
                labelOpts={'position': .1, 'color': (255, 225, 53), 'fill': (200, 200, 200, 50), 'movable': True}
            )
            self._mp_lines.append(line)
            label = pg.InfLineLabel(line, f'Manual Align', position=0.32, color='#32CD32',rotateAxis=(1, 0), anchor=(.8, 1))
            self._mp_labels.append(label)
            line.setPos([layer[0] + offset, 1])
            self.plot.addItem(line)

        for line in self._skip_lines:   self.plot.removeItem(line)
        for label in self._skip_labels: self.plot.removeItem(label)

        self._skip_lines = []
        self._skip_labels = []

        for layer in cfg.data.skips_list():
            line = pg.InfiniteLine(
                movable=False,
                angle=90,
                pen='#ff0000',
                # snr='Skip #{value:.0f}',
                # # snr=self.label_value,
                labelOpts={'position': .1, 'color': (255,250,250), 'fill': (255, 0, 0, 75), 'movable': True}
            )
            self._skip_lines.append(line)
            label = pg.InfLineLabel(line, f'Skip', position=0.08, color='#ff0000', rotateAxis=(1, 0), anchor=(1, 1))
            self._skip_labels.append(label)
            line.setPos([layer[0] + offset, 1])
            self.plot.addItem(line)


    def callableFunction(x, y):
        return str(cfg.data.snr())
        # logger.info()
        # return f"Square Values: ({x ** 2:.4f}, {y ** 2:.4f})"


    def initSnrPlot(self, s=None):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        if not cfg.data:
            logger.warning(f'initSnrPlot was called by {inspect.stack()[1].function} but data does not exist.')
            return
        try:
            if caller != 'initUI_plot':
                self.wipePlot()

            n_aligned = 0
            for s in cfg.data.scales():
                if cfg.data.is_aligned(s=s):
                    n_aligned += 1
            if n_aligned == 0:
                logger.info('0 scales are aligned, Nothing to Plot - Returning')
                return

            self._snr_checkboxes = dict()

            for i in reversed(range(self.checkboxes_hlayout.count())):
                self.checkboxes_hlayout.itemAt(i).widget().setParent(None)

            for i, s in enumerate(cfg.data.scales()):
                if cfg.data.is_aligned(s=s):
                    self._snr_checkboxes[s] = QCheckBox()
                    self._snr_checkboxes[s].setText(cfg.data.scale_pretty(s=s))
                    self.checkboxes_hlayout.addWidget(self._snr_checkboxes[s],
                                                      alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                    self._snr_checkboxes[s].setChecked(True)
                    self._snr_checkboxes[s].clicked.connect(self.plotData)
                    self._snr_checkboxes[s].setStatusTip('On/Off SNR Plot %s' % cfg.data.scale_pretty(s=s))
                    color = self._plot_colors[cfg.data.scales()[::-1].index(s)]
                    self._snr_checkboxes[s].setStyleSheet(
                        f'background-color: #F3F6FB;'
                        f'border-color: {color}; '
                        f'border-width: 3px; '
                        f'border-style: outset;')
                # if cfg.data.is_aligned(s=s):
                #     self._snr_checkboxes[s].show()
                # else:
                #     self._snr_checkboxes[s].hide()

            # self.checkboxes_hlayout.addStretch()

            self.updateLayerLinePos()
            # styles = {'color': '#f3f6fb', 'font-size': '14px', 'font-weight': 'bold'}
            styles = {'color': '#ede9e8', 'font-size': '14px', 'font-weight': 'bold'}
            self.plot.setLabel('top', cfg.data.base_image_name(), **styles)
        except:
            print_exception()
        try:
            self.plotData()
        except:
            print_exception()


    def get_axis_data(self, s=None) -> tuple:
        if s == None: s = cfg.data.scale
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
        caller = inspect.stack()[1].function
        logger.debug(f'caller: {caller}')
        if cfg.data:
            self.plot.clear()
            self.plot.addItem(self._curLayerLine)
            for s in cfg.data.scales()[::-1]:
                if cfg.data.is_aligned(s=s):
                    if self._snr_checkboxes[s].isChecked():
                        self.plotSingleScale(s=s)
            max_snr = cfg.data.snr_max_all_scales()
            if not max_snr:
                logger.warning('No max SNR, Nothing to plot - Returning')
                return
            xmax = len(cfg.data) + 1
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
            # ax = self.plot.getAxis('bottom')  # This is the trick
            # dx = [(value, str(value)) for value in list((range(0, xmax - 1)))]
            # ax.setTicks([dx, []])
            #
            # xticks = np.arange(0, cfg.data.count, 10)
            # ax = self.plot.getAxis("bottom")
            # ax.setTicks([[(v, str(v)) for v in xticks ]])

            # ticks = np.arange(0, cfg.data.count)
            # ax = self.plot.getAxis("bottom")
            # ax.setTicks([[(v, str(v)) for v in ticks ]])

            self.updateSpecialLayerLines()
            self.plot.autoRange() # !!!

    def _getScaleOffset(self, s):
        return cfg.data.scales()[::-1].index(s) * (.5/len(cfg.data.scales()))


    def plotSingleScale(self, s=None):
        logger.info(f'plotSingleScale (scale: {s}):')
        if s == None: scale = cfg.data.scale
        x_axis, y_axis = self.get_axis_data(s=s)
        offset = self._getScaleOffset(s=s)
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
        self.updateErrBars(s=s)


    def updateErrBars(self, s):
        # logger.info('')
        offset = self._getScaleOffset(s=s)
        errbars = cfg.data.snr_errorbars(s=s)
        n = len(cfg.data)
        deltas = np.zeros(n)
        y = np.zeros(n)
        x = np.arange(0, n ) + offset

        if s in self._error_bars:
            self.plot.removeItem(self._error_bars[s])
            self._error_bars[s] = None

        try:
            skip_list = list(zip(*cfg.data.skips_list()))[0]
        except:
            skip_list = [-1]

        for i, err in enumerate(errbars):
            if i not in skip_list:
                deltas[i] = err
                y[i]      = cfg.data.snr(s=s, l=i)
            else:
                logger.debug(f'skipping errbars for layer {i}')

        err_bar = pg.ErrorBarItem(x=x, y=y,
                                  top=deltas,
                                  bottom=deltas,
                                  beam=0.20,
                                  pen={'color': '#ff0000', 'width': 2})
        self._error_bars[s] = err_bar
        self.plot.addItem(err_bar)


    def wipePlot(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        try:
            for i in reversed(range(self.checkboxes_hlayout.count())):
                self.checkboxes_hlayout.removeItem(self.checkboxes_hlayout.itemAt(i))
            # try:
            #     del self._snr_checkboxes
            # except:
            #     pass
            #0123 !!!!!!!
            self.plot.clear()
            self.plot.addItem(self._curLayerLine)
            for eb in self._error_bars:
                self.plot.removeItem(eb)
            # self.updateSpecialLayerLines()
            # try:
            #     del self._snr_checkboxes
            # except:
            #     print_exception()
        except:
            print_exception()
            logger.warning('Unable To Wipe SNR Plot')


    def mouse_clicked(self, mouseClickEvent):
        if cfg.data:
            try:
                # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
                print('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
                pos_click = int(mouseClickEvent.pos()[0])
                print('Position Clicked: %d' % pos_click)
                cfg.data.zpos = pos_click
                self.updateLayerLinePos()
                cfg.main_window.dataUpdateWidgets()
            except:
                pass

    def onSnrClick2(self, scale):
        logger.info(f'onSnrClick2 ({scale}):')
        self.selected_scale = scale
        cfg.main_window._changeScaleCombo.setCurrentText(scale)


    # def onSnrClick(self, plot, points, scale):
    def onSnrClick(self, plot, points):
        # logger.info(f'onSnrClick ({scale}):')

        index = int(points[0].pos()[0])
        if index in range(len(cfg.data)):
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
            # cfg.main_window.jump_to(index)
            cfg.data.zpos = index
            # cfg.set_layer(cfg.data.zpos)
            cfg.main_window.dataUpdateWidgets()
            self.updateLayerLinePos()

        else:
            logger.warning('Invalid Index: %d' %index)


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