#!/usr/bin/env python3

'''
https://github.com/robertsj/poropy/blob/master/pyqtgraph/graphicsItems/ScatterPlotItem.py
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ScatterPlotItem.html
'''

import pyqtgraph as pg
from qtpy.QtGui import QFont
from qtpy.QtCore import Qt


class SnrPlot(pg.PlotWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # self.useOpenGL()
        self.setAntialiasing(False)
        self.setAspectLocked(True)
        self.showGrid(x=True, y=True, alpha=220)  # alpha: 0-255
        self.getPlotItem().enableAutoRange()

        self.hoverable = True

        self.hoverSize = 10
        self.setFocusPolicy(Qt.NoFocus)
        font = QFont()
        font.setPixelSize(12)
        self.getAxis("bottom").setStyle(tickFont=font)
        self.getAxis("bottom").setHeight(28)
        self.getAxis("left").setStyle(tickFont=font)
        self.getAxis("left").setWidth(36)
        # pen = pg.mkPen(color=(255, 0, 0), width=5, style=Qt.SolidLine)b
        style = {'color': '#f3f6fb;', 'font-size': '14px'}
        self.setLabel('left', 'SNR', **style)
        self.setLabel('bottom', 'Layer #', **style)

        # self.scene() is a pyqtgraph.GraphicsScene.GraphicsScene.GraphicsScene
        self.scene().sigMouseClicked.connect(self.mouse_clicked)


    def mouse_clicked(self, mouseClickEvent):
        # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
        # print('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
        # print(mouseClickEvent(0))
        # pos_click = int(mouseClickEvent.pos()[0])
        # print('Position Clicked: %d' % pos_click)
        pass