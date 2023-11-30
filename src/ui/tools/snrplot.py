#!/usr/bin/env python3

'''
SNR Plot Class. Depends on 'pyqtgraph' Python module.
https://github.com/robertsj/poropy/blob/master/pyqtgraph/graphicsItems/ScatterPlotItem.py
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ScatterPlotItem.html


15:19:13 [data_model.needsGenerateIndexes:1883] needsGenerateIndexes dt = 0.0665
15:19:13 [data_model.data_dn_comport_indexes:1857] data_dn_comport_indexes dt = 0.18
15:19:13 [data_model.all_comports_indexes:1865] all_comports_indexes dt = 0.247
15:19:13 [data_model.needsGenerateIndexes:1883] needsGenerateIndexes dt = 0.0611
15:19:13 [data_model.data_dn_comport_indexes:1857] data_dn_comport_indexes dt = 0.175

15:19:13 [snr_plot.get_everything_comport_axis_data:338] get_everything_comport_axis_data dt=0.248
15:19:13 [snr_plot.get_cafm_no_comport_axis_data:356] get_cafm_no_comport_axis_data dt=0.0622
15:19:13 [snr_plot.get_data_no_comport_axis_data:374] get_data_no_comport_axis_data dt=0.175
15:19:13 [snr_plot.plotData:414] plotData dt=0.502
15:19:13 [snr_plot.initSnrPlot:303] initSnrPlot dt=0.511

'''
import inspect
import logging
import sys
from math import ceil
from time import time

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QMainWindow, QApplication, QWidget, QHBoxLayout, QGridLayout, QCheckBox

import src.config as cfg
from src.utils.helpers import print_exception

logger = logging.getLogger(__name__)
# logger.propagate = False

class SnrPlot(QWidget):

    def __init__(self, dm, dock=False, **kwargs):
        super().__init__(**kwargs)

        self.dm = dm

        self.app = pg.mkQApp()
        self.dock = dock
        self.view = pg.GraphicsLayoutWidget()
        if self.dock:
            self.view.ci.layout.setContentsMargins(0, 0, 0, 0)
            self.view.ci.layout.setSpacing(0)  # might not be necessary for you
        # self.view.setBackground('#1b1e23')
        self.view.setBackground('#222222')
        # drafting_blue = '#004060'
        # self.view.setBackground(drafting_blue)
        pg.setConfigOption('foreground', '#f3f6fb')
        pg.setConfigOptions(antialias=True)

        self.plot = self.view.addPlot()

        # ax0.setStyle(showValues=False)


        if self.dock:
            self.plot.getAxis('bottom').setHeight(16)
            # self.plot.getAxis('bottom').setStyle(tickTextOffset=2)
        # self.label_value = pg.InfLineLabel('test', **{'color': '#FFF'})


        if self.dock:
            self._curLayerLine = pg.InfiniteLine(
                # pen='w',
                pen=pg.mkPen('#0096ff', width=1),
                movable=False,
                angle=90,
                labelOpts={'position': .2, 'color': '#f3f6fb', 'fill': '#141414', 'movable': True})
        else:
            self._curLayerLine = pg.InfiniteLine(
                # pen='w',
                pen=pg.mkPen('#0096ff', width=2),
                movable=False,
                angle=90,
                label='Section #{value:.0f}',
                # snr=self.label_value,
                labelOpts={'position': .8, 'color': '#f3f6fb', 'fill': '#141414', 'movable': True})
        # self._snr_label = pg.InfLineLabel(self._curLayerLine, '', position=0.95, rotateAxis=(1, 0),
        #                                  anchor=(1, 1))
        self._curLayerLine.addMarker('v', position=1, size=(9,12)[self.dock])
        self._curLayerLine.addMarker('^', position=0, size=(9,12)[self.dock])
        self._curLayerLine.setZValue(0)

        if self.dock:
            self._snr_label = pg.InfLineLabel(self._curLayerLine, '', position=0.2, anchor=(0, 1), color='#f3f6fb')
        else:
            self._snr_label = pg.InfLineLabel(self._curLayerLine, '', position=0.1, anchor=(1, 1), color='#f3f6fb')

        # f = QFont('Consolas')
        f = QFont('Tahoma')
        f.setBold(True)
        # f.setPointSize(12)
        f.setPointSize((12,10)[self.dock])
        self._snr_label.setFont(f)
        self.plot.addItem(self._curLayerLine)
        self._mp_lines = []
        self._mp_labels = []
        self._skip_lines = []
        self._skip_labels = []
        self._text_labels = []
        self._fill_rois = []
        self._error_bars = {}
        # self.pt_selected = None

        # self.spw = pg.ScatterPlotWidget() #Todo switch to scatter plot widget for greater interactivity

        self._plot_colors = ['#2CBFF7', '#FEFE62', '#c9cbd0',
                             '#ff9a00', '#fbd771', '#1AFF1A',
                             '#56768e', '#8c001a', '#08E8DE',
                             '#FF007F', '#376d58', '#f46c60',
                             '#D41159', '#66FF00', '#E66100'
                             ]

        self._plot_brushes = [pg.mkBrush(c) for c in self._plot_colors]

        # self.plot.scene().sigMouseClicked.connect(self.mouse_clicked)


        # self.plot.setAspectLocked(True)
        self.plot.showGrid(x=False, y=True, alpha=(160,220)[dock])  # alpha: 0-255
        self.plot.hoverable = True
        self.plot.hoverSize = (13,12)[self.dock]
        if self.dock:
            font = QFont()
            font.setPixelSize(8)
            self.plot.getAxis("left").tickFont = font
            # self.plot.getAxis("bottom").tickFont = font
            self.plot.getAxis("left").setStyle(tickFont=font) # PyQtgraph 0.11+ syntax
            self.plot.getAxis("bottom").setStyle(tickFont=font) # PyQtgraph 0.11+ syntax
            self.plot.getAxis("bottom").setStyle(tickTextOffset=1)
            self.plot.getAxis("left").setStyle(tickTextOffset=1)
        else:
            font = QFont()
            font.setPixelSize(10)
            self.plot.getAxis("left").setStyle(tickFont=font)  # PyQtgraph 0.11+ syntax
            self.plot.getAxis("bottom").setStyle(tickFont=font)  # PyQtgraph 0.11+ syntax
            self.plot.getAxis("bottom").setStyle(tickTextOffset=4)
            self.plot.getAxis("left").setStyle(tickTextOffset=4)


        # self.plot.getAxis("bottom").setStyle(tickFont=font)
        # self.plot.getAxis("left").setStyle(tickFont=font)
        # self.plot.getAxis("bottom").setHeight(12)
        # self.plot.getAxis("left").setWidth(12)

        # style = {'color': '#f3f6fb;', 'font-size': '14px'}

        self.plot.setCursor(Qt.CrossCursor)
        # self.plot.setAspectLocked()

        self.snr_points = {}
        self.ghost_points = {}
        self.no_comport_cafm_points = {}
        self.no_comport_data_points = {}
        self.snr_errors = {}
        self.selected_scale = None

        self.checkboxes_widget = QWidget()
        # self.checkboxes_widget.setStyleSheet("background-color: #222222;")
        self.checkboxes_widget.setMaximumHeight((24,20)[self.dock])
        self.checkboxes_hlayout = QHBoxLayout()
        self.checkboxes_hlayout.setContentsMargins(0, 0, 0, 0)
        self.checkboxes_widget.setLayout(self.checkboxes_hlayout)

        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.view, 0, 0, 2, 2)
        self.layout.addWidget(self.checkboxes_widget, 0, 1, 1, 1,
                              alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.layout.setRowStretch(0,0)
        self.layout.setRowStretch(1,1)
        self.setLayout(self.layout)


        self.points = []
        self.ev = []

        # self._memHover0 = None
        # self._memHover1 = None
        self._memHover0 = np.array(0)
        self._memHover1 = np.array(0)



    def updateLayerLinePos(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller={caller}')
        offset = self._getScaleOffset(s=self.dm.level)
        pos = [self.dm.zpos + offset, 1]
        # logger.info(f'pos = {pos}')
        self._curLayerLine.setPos(pos)
        # snr = pg.InfLineLabel(self._curLayerLine, "region 1", position=0.95, rotateAxis=(1, 0), anchor=(1, 1))
        if not self.dm.skipped():
            if self.dock:
                lab = 'SNR: %.2g' % self.dm.snr()
            else:
                lab = 'SNR: %.3g\n%s' % (self.dm.snr(), self.dm.level_pretty())
            self._snr_label.setText(lab)

        if not self.dock:
            styles = {'color': '#f3f6fb', 'font-size': '14px', 'font-weight': 'bold'}
            self.plot.setLabel('top', self.dm.base_image_name(), **styles)
        self.update()



    def updateSpecialLayerLines(self):
        # logger.info('')
        offset = self._getScaleOffset(s=self.dm.level)

        # layers_mp = self.dm.find_layers_with_manpoints()
        # for line in self._mp_lines:   self.plot.removeItem(line)
        # for label in self._mp_labels: self.plot.removeItem(label)
        # self._mp_lines = []
        # self._mp_labels = []
        # for layer in layers_mp:
        #     line = pg.InfiniteLine(
        #         movable=False,
        #         angle=90,
        #         pen='#32CD32',
        #         # snr='Match Point #{value:.0f}',
        #         # # snr=self.label_value,
        #         labelOpts={'position': .1, 'color': (255, 225, 53), 'fill': (200, 200, 200, 50), 'movable': True}
        #     )
        #     self._mp_lines.append(line)
        #     label = pg.InfLineLabel(line, f'Manual', position=0.32, color='#32CD32',rotateAxis=(1, 0),
        #                             anchor=(.8, 1))
        #     self._mp_labels.append(label)
        #     line.setPos([layer[0] + offset, 1])
        #     self.plot.addItem(line)

        for line in self._skip_lines:   self.plot.removeItem(line)
        for label in self._skip_labels: self.plot.removeItem(label)

        self._skip_lines = []
        self._skip_labels = []
        self._fill_rois = []
        self._text_labels = []

        for i, name in self.dm.skips_list():

            
            lr = pg.LinearRegionItem([i, i+1], movable=False, pen=(238, 75, 43, 256), brush=(238, 75, 43, 80))
            self.plot.addItem(lr)
            self._fill_rois.append(lr)

            # Create line
            # line = pg.InfiniteLine(
            #     movable=False,
            #     angle=90,
            #     pen='#ede9e8',
            #     # snr='Skip #{value:.0f}',
            #     # # snr=self.label_value,
            #     labelOpts={'position': -1, 'color': '#666666', 'fill': '#fffff', 'movable': True, 'size': '8pt'}
            # )
            # self._skip_lines.append(line)
            if not self.dock:
                # Create label

                text = pg.TextItem(html='<span style="color: rgb(238, 75, 43); font-size: 9pt;">Exclude</span>', anchor=(.5,.5), angle=90)
                self.plot.addItem(text)
                text.setPos(i+1, 1)
                self._text_labels.append(text)


                # label = pg.InfLineLabel(line, f"<span style='font-size: 8px;'>Exclude</span>",
                #                         position=0.12,
                #                         # color='#ff0000',
                #                         color='#ede9e8',
                #                         # rotateAxis=(1, 0),
                #                         angle=90,
                #                         anchor=(1, 0),
                #                         )
                # ^^ position is vertical position of 'skip' label
                # self._skip_labels.append(label)
            # line.setPos([i[0] + offset, 1])
            # line.setPos([i, 1])
            # self.plot.addItem(line)


    def initSnrPlot(self, s=None):

        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Initializing Plot...")

        if cfg.mw.dwSnr.isHidden():
            # logger.warning("Dock widget SNR is hidden!")
            return

        t0 = time()
        try:
            if caller != 'initUI_plot':
                self.wipePlot()

            if not self.dock:
                n_aligned = 0
                for s in self.dm.levels:
                    if self.dm.is_aligned(s=s):
                        n_aligned += 1
                if n_aligned == 0:
                    return

                self._snr_checkboxes = dict()
                for i in reversed(range(self.checkboxes_hlayout.count())):
                    self.checkboxes_hlayout.itemAt(i).widget().setParent(None)

                for i, s in enumerate(self.dm.levels):
                    if self.dm.is_aligned(s=s):
                        color = self._plot_colors[self.dm.levels[::-1].index(s)]
                        self._snr_checkboxes[s] = QCheckBox()
                        self._snr_checkboxes[s].setText(self.dm.level_pretty(s=s))
                        self.checkboxes_hlayout.addWidget(self._snr_checkboxes[s],
                                                          alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                        self._snr_checkboxes[s].setChecked(True)
                        self._snr_checkboxes[s].clicked.connect(lambda: print('cb clicked!'))
                        self._snr_checkboxes[s].clicked.connect(self.plotData)
                        self._snr_checkboxes[s].setStatusTip('On/Off SNR Plot %s' % self.dm.level_pretty(s=s))
                        self._snr_checkboxes[s].setStyleSheet(
                            f'color: #f3f6fb;'
                            f'background-color: #161c20;'
                            f'border-color: {color};'
                            f'border-width: 3px;'
                            # f'border-style: outset;'
                            f'border-radius: 4px;')
                    # if self.dm.is_aligned(level=level):
                    #     self._snr_checkboxes[level].show()
                    # else:
                    #     self._snr_checkboxes[level].hide()
        except:
            print_exception()

        if self.dock:
            if self.dm.is_aligned():
                try:
                    self.plotGhostScaleData()
                except:
                    print_exception()
        self.plotData()
        # self.updateLayerLinePos()
        logger.info(f"Time Elapsed: {time() - t0:.3g}")
        # logger.info('<<')



    def get_axis_data(self, s=None) -> tuple:
        if s == None: s = self.dm.scale
        x_axis, y_axis = [], []
        # for layer, snr in enumerate(self.dm.snr_list(level=level)):
        # for layer, snr in enumerate(self.dm.snr_list(level=level)[1:]): #0601+ #Todo
        firstInd = self.dm.first_included(s=s)
        for i, snr in enumerate(self.dm.snr_list(s=s)): #0601+
            if i != firstInd:
                if self.dm.include(s=s, l=i):
                    x_axis.append(i)
                    y_axis.append(snr)

        # logger.info(f"\nx-axis: {x_axis}\ny-axis: {y_axis}")
        return x_axis, y_axis

    def get_everything_comport_axis_data(self, s=None) -> tuple:
        if s == None: s = self.dm.scale
        t0 = time()
        x_axis, y_axis = [], []
        # for layer, snr in enumerate(self.dm.snr_list(level=level)):
        # for layer, snr in enumerate(self.dm.snr_list(level=level)[1:]): #0601+ #Todo
        firstInd = self.dm.first_included(s=s)
        for i in self.dm.all_comports_indexes(s=s): #0601+
            if i != firstInd:
                if self.dm.skipped(s=s, l=i):
                    x_axis.append(i)
                    y_axis.append(0)
                else:
                    x_axis.append(i)
                    y_axis.append(self.dm.snr(s=s, l=i))
        logger.info(f"get_everything_comport_axis_data dt={time() - t0:.3g}")
        # logger.info(f"\nx-axis: {x_axis}\ny-axis: {y_axis}")
        self._pts_all_comport = (x_axis, y_axis)
        return x_axis, y_axis

    def get_cafm_no_comport_axis_data(self, s=None) -> tuple:
        if s == None: s = self.dm.scale
        t0 = time()
        x_axis, y_axis = [], []
        # for layer, snr in enumerate(self.dm.snr_list(level=level)):
        # for layer, snr in enumerate(self.dm.snr_list(level=level)[1:]): #0601+ #Todo
        firstInd = self.dm.first_included(s=s)
        for i in self.dm.needsGenerateIndexes(s=s): #0601+
            if i != firstInd:
                if self.dm.skipped(s=s, l=i):
                    x_axis.append(i)
                    y_axis.append(0)
                else:
                    x_axis.append(i)
                    y_axis.append(self.dm.snr(s=s, l=i))
        logger.info(f"get_cafm_no_comport_axis_data dt={time() - t0:.3g}")
        # logger.info(f"\nx-axis: {x_axis}\ny-axis: {y_axis}")
        self._pts_cafm_nocomport = (x_axis, y_axis)
        return x_axis, y_axis

    def get_data_no_comport_axis_data(self, s=None) -> tuple:
        t0 = time()
        if s == None: s = self.dm.scale
        x_axis, y_axis = [], []
        # for layer, snr in enumerate(self.dm.snr_list(level=level)):
        # for layer, snr in enumerate(self.dm.snr_list(level=level)[1:]): #0601+ #Todo
        firstInd = self.dm.first_included(s=s)
        # for i in self.dm.data_dn_comport_indexes(s=s): #0601+
        for i in self.dm.needsAlignIndexes(s=s): #0601+
            if i != firstInd:
                if self.dm.skipped(s=s, l=i):
                    x_axis.append(i)
                    y_axis.append(0)
                else:
                    x_axis.append(i)
                    y_axis.append(self.dm.snr(s=s, l=i))
        logger.info(f"get_data_no_comport_axis_data dt={time()-t0:.3g}")
        # logger.info(f"\nx-axis: {x_axis}\ny-axis: {y_axis}")
        self._pts_data_nocomport = (x_axis, y_axis)
        return x_axis, y_axis


    def plotData(self):
        '''Update SNR plot widget based on checked/unchecked state of checkboxes'''
        print('\nPlotting data...')
        logger.info(f"")
        self.wipePlot(checkboxes=False)
        # caller = inspect.stack()[1].function
        t0 = time()
        # if self.dm:
            # self.plot.clear() #0808-
            # self.plot.addItem(self._curLayerLine) #0808-
        # logger.critical('Plotting data...')
        if self.dock:
            # self.plotGhostScaleData()
            self.plotSingleScale()
            self.plot.setLimits(xMin=0, xMax=len(self.dm) + 1, yMin=0, yMax=max(self.dm.snr_list()) + 1)
            self.plot.enableAutoRange()  #Fixed

        else:
            for s in self.dm.levels[::-1]:
                if self.dm.is_aligned(s=s):
                    if self._snr_checkboxes[s].isChecked():
                        self.plotSingleScale(s=s)
            self.updateSpecialLayerLines()
            xMax = len(self.dm) + 1
            yMax = ceil(self.dm.snr_max_all_scales()) + 5
            self.plot.setLimits(
                minXRange=1,
                xMin=0,
                xMax=xMax,
                maxXRange=xMax,
                yMin=0,
                yMax=yMax,
                minYRange=20,
                maxYRange=yMax,
            )

        ax0 = self.plot.getAxis('bottom')  # get handle to x-axis 0
        n = len(self.dm)
        if n < 21:     ax0.setTickSpacing(1, 1)
        elif n < 151:  ax0.setTickSpacing(5, 1)
        elif n < 301:  ax0.setTickSpacing(10, 1)
        elif n < 451:  ax0.setTickSpacing(15, 1)
        elif n < 601:  ax0.setTickSpacing(20, 1)
        elif n < 751:  ax0.setTickSpacing(25, 1)
        else:          ax0.setTickSpacing(30, 1)

        self.updateLayerLinePos()



        # logger.info(f"plotData dt={time() - t0:.3g}")


    def _getScaleOffset(self, s):
        if self.dock:
            return 0
        else:
            # return self.dm.levels()[::-1].index(level) * (.5/len(self.dm.levels()))
            return self.dm.levels.index(s) * (.5/len(self.dm.levels))


    def plotGhostScaleData(self, s=None):
        logger.info('Plotting ghost data...')
        if s == None: s = self.dm.scale
        x_axis, y_axis = [], []
        # for layer, snr in enumerate(self.dm.snr_list(level=level)):
        # for layer, snr in enumerate(self.dm.snr_list(level=level)[1:]): #0601+ #Todo
        firstInd = self.dm.first_included(s=s)
        data = self.dm['level_data'][s]['initial_snr']
        for i in range(0, len(self.dm)): #0601+
            if i != firstInd:
                x_axis.append(i)
                y_axis.append(data[i])

        self.ghost_points[s] = pg.ScatterPlotItem(
            size=(11,8)[self.dock],
            # pen=pg.mkPen(None),
            symbol='o',
            pen=pg.mkPen('#666666', width=1),
            brush=pg.mkBrush('#444444'),
            hoverable=True,
            tip='Initial results:\nSection #: {x:.3g}\nSNR: {y:.3g}'.format,
            hoverSymbol='o',
            hoverSize=(13,10)[self.dock],
            # hoverPen=pg.mkPen('#f3f6fb', width=1),
            # hoverBrush=None,
            # pxMode=False # points generate_thumbnail with zoom
        )
        self.ghost_points[s].addPoints(x_axis, y_axis)
        self.ghost_points[s].setZValue(0)

        self._pts_ghost = (x_axis, y_axis)
        self.plot.addItem(self.ghost_points[s])


    def plotSingleScale(self, s=None):
        if s == None: s = self.dm.scale
        print(f'Plotting {s}...')
        # logger.info(f'[{self.dock}] plotSingleScale (level_key: {level}):')
        # x_axis, y_axis = self.get_axis_data(level=level)
        # x_axis, y_axis = self.get_everything_comport_axis_data(s=s)
        x_axis, y_axis = self.get_axis_data(s=s)
        if not self.dock:
            x_axis = [x+self._getScaleOffset(s=s) for x in x_axis]
        brush = self._plot_brushes[self.dm.levels[::-1].index(s)]

        self.snr_points[s] = pg.ScatterPlotItem(
            size=(11,8)[self.dock],
            # pen=pg.mkPen(None),
            symbol='o',
            pen=pg.mkPen('#f3f6fb', width=2),
            brush=(brush, pg.mkBrush('#AAFF00'))[self.dock],
            hoverable=True,
            tip='Bla bla bla\nSection #: {x:.3g}\nSNR: {y:.3g}'.format,
            hoverSymbol='o',
            hoverSize=(13,10)[self.dock],
            # hoverPen=pg.mkPen('#f3f6fb', width=1),
            # hoverBrush=None,
            # pxMode=False # points generate_thumbnail with zoom
        )
        #         *tip*                  A string-valued function of a spot'level (x, y, data) values. Set to None to prevent a tool tip
        #                                from being shown.

        # def hoverSlot(points, ev):
        #
        #     print(f"points: {points}")
        #     print(f"ev: {ev}")
        #     self.points = points
        #     if len(ev):
        #         print(f"hovered: {int(cfg.pt.dSnr_plot.ev.item().pos()[0])}")
        #         self.ev = ev
        #
        # self.snr_points[level].sigHovered.connect(hoverSlot)

        # self.snr_points[level].addPoints(x_axis[1:], y_axis[1:]) #Todo
        self.snr_points[s].addPoints(x_axis, y_axis)
        self.snr_points[s].setZValue(1)

        # def hoverEvent(event):
        #     """Show the position, pixel, and value under the mouse cursor.
        #     """
        #     data = np.array(cfg.pt.dSnr_plot.get_everything_comport_axis_data())
        #     pos = event.pos()
        #     i, j = pos.y(), pos.x()
        #     i = int(np.clip(i, 0, data.shape[0] - 1))
        #     j = int(np.clip(j, 0, data.shape[1] - 1))
        #     val = data[i, j]
        #     ppos = self.mapToParent(pos)
        #     x, y = ppos.x(), ppos.y()
        #     self.plot.setTitle("pos: (%0.1f, %0.1f)" % (i,j))
        #
        # self.snr_points[level].hoverEvent.connect(hoverEvent)

        # logger.info('self.snr_points.toolTip() = %level' % self.snr_points.toolTip())
        # value = self.snr_points.setToolTip('Test')
        self.plot.addItem(self.snr_points[s])
        # self.snr_points[level].sigClicked.connect(lambda: self.onSnrClick2(level))
        self.snr_points[s].sigClicked.connect(self.onSnrClick)

        # if self.dock:
        if 0:

            # logger.critical("Plotting cafm no comports data points...")
            self.no_comport_cafm_points[s] = pg.ScatterPlotItem(
                size=8,
                # pen=pg.mkPen(None),
                symbol='x',
                # pen=pg.mkPen('#f3f6fb', width=1),
                pen=pg.mkPen('#f3f6fb', width=0),
                brush=pg.mkBrush('#f3f6fb'),
                # brush=None,
                hoverable=True,
                tip='Section #: {x:.3g}\nSNR: {y:.3g}'.format,
                # tip='cafm_no_comport\nx: {x:.3g}\ny: {y:.3g}\nWarnings:\n{self.dm.is_zarr_generated(x)}'.format,
                hoverSize=10,
                # hoverPen=pg.mkPen('#ff0000', width=3),
                # hoverBrush=None,
                # pxMode=False # points generate_thumbnail with zoom
            )
            x_axis, y_axis = self.get_cafm_no_comport_axis_data(s=s)
            self.no_comport_cafm_points[s].addPoints(x_axis, y_axis)
            self.plot.addItem(self.no_comport_cafm_points[s])
            self.no_comport_cafm_points[s].sigClicked.connect(self.onSnrClick)

            # def hoverSlot0(points, ev):
            #     if len(ev) == 1:
            #         if self._memHover0.any():
            #             if self._memHover0 != ev:
            #                 hoverIndex = int(ev.item().pos()[0])
            #                 print(f"hovered index: {hoverIndex}")
            #                 comport_data = self.dm.is_zarr_generated(z=hoverIndex)
            #                 if comport_data:
            #                     logger.info(f'CAFM does not comport for section #{hoverIndex}')
            #         self._memHover0 = ev
            #
            # self.no_comport_cafm_points[level].sigHovered.connect(hoverSlot0)

            self.no_comport_data_points[s] = pg.ScatterPlotItem(
                size=9,
                # pen=pg.mkPen(None),
                symbol='o',
                pen=pg.mkPen('#f3f6fb', width=2),
                brush=None,
                hoverable=True,
                tip='Section #_: {x:.3g}\nSNR: {y:.3g}'.format,
                # data=[self.dm.data_comports(level=self.dm.scale, z=z) for z in self.get_data_no_comport_axis_data()[0]],
                # tip='data_no_comport\nx: {x:.3g}\ny: {y:.3g}\nWarnings:\n{self.dm.data_comports(x)}'.format,
                hoverSize=11,
                # hoverPen=pg.mkPen('#ff0000', width=3),
                # hoverBrush=None,
                # pxMode=False # points generate_thumbnail with zoom
            )
            x_axis, y_axis = self.get_data_no_comport_axis_data(s=s)
            self.no_comport_data_points[s].addPoints(x_axis, y_axis)
            self.plot.addItem(self.no_comport_data_points[s])
            self.no_comport_data_points[s].sigClicked.connect(self.onSnrClick)

            # def hoverSlot1(points, ev):
            #     if len(ev):
            #         logger.info(f"type(self._memHover1) = {type(self._memHover1)}")
            #         logger.info(f"type(ev) = {type(ev)}")
            #         logger.info(f"len(ev) = {len(ev)}")
            #         if self._memHover1.any():
            #             if self._memHover1 != ev:
            #                 hoverIndex = int(ev.item().pos()[0])
            #                 print(f"hovered index: {hoverIndex}")
            #                 comport_data = self.dm.data_comports(z=hoverIndex)
            #                 if comport_data[0]:
            #                     logger.info(comport_data)
            #         self._memHover1 = ev
            #
            # self.no_comport_data_points[level].sigHovered.connect(hoverSlot1)

        # if not self.dock:
        self.updateErrBars(s=s)
        sys.stdout.flush()
        self.update()
        # logger.info('<<')


    def updateErrBars(self, s):
        offset = self._getScaleOffset(s=s)
        errbars = self.dm.snr_errorbars(s=s)
        n = len(self.dm)
        # n = len(self.dm) - 1 #Todo
        deltas = np.zeros(n)
        y = np.zeros(n)
        x = np.arange(0, n ) + offset

        if s in self._error_bars:
            self.plot.removeItem(self._error_bars[s])
            self._error_bars[s] = None

        try:
            skip_list = list(zip(*self.dm.skips_list()))
            if skip_list:
                skip_list = skip_list[0]
        except:
            # skip_list = [-1]
            skip_list = []
            print_exception()

        for i, err in enumerate(errbars):
            if i not in skip_list:
                deltas[i] = err
                y[i]      = self.dm.snr(s=s, l=i)
            else:
                logger.debug(f'skipping errbars for layer {i}')

        err_bar = pg.ErrorBarItem(x=x, y=y,
                                  top=deltas,
                                  bottom=deltas,
                                  beam=0.15,
                                  pen={'color': '#ff0000', 'width': 2})
        self._error_bars[s] = err_bar
        self.plot.addItem(err_bar)
        # logger.info('<<')


    def wipePlot(self, checkboxes=True):
        # logger.info('')
        try:
            if checkboxes:
                for i in reversed(range(self.checkboxes_hlayout.count())):
                    self.checkboxes_hlayout.removeItem(self.checkboxes_hlayout.itemAt(i))
            self.plot.clear()
            self.plot.addItem(self._curLayerLine)
            for eb in self._error_bars:
                self.plot.removeItem(eb)
            for item in self._text_labels:
                self.plot.removeItem(item)
            for item in self._fill_rois:
                self.plot.removeItem(item)
        except:
            print_exception()
            logger.warning('Unable To Wipe SNR Plot')

    def wipeScale(self, s):
        # logger.info('')
        #Not Tested
        try:
            self.snr_points[s].clear()
            self.plot.clear()
            self.plot.addItem(self._curLayerLine)
            self.plot.removeItem(self._error_bars[s])
        except:
            print_exception()
            logger.warning('Unable To Wipe SNR Plot')


    def mouse_clicked(self, mouseClickEvent):
        logger.info('')
        try:
            # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
            # logger.info('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
            pos_click = int(mouseClickEvent.pos()[0])
            logger.info('Position Clicked: %d' % pos_click)
            self.dm.zpos = int(pos_click)
            # self.updateLayerLinePos()
        except:
            print_exception()


    def onSnrClick(self, _, points):
        logger.info('')
        self.dm.zpos = int(points[0].pos()[0])


    def onSnrClick2(self, scale):
        logger.info('')
        # logger.info(f'onSnrClick2 ({level_key}):')
        self.selected_scale = scale
        cfg.main_window.boxScale.setCurrentText(scale)


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


class FmtAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [f'{v:.4f}' for v in values]

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