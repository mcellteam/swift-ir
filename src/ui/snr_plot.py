#!/usr/bin/env python3

'''
https://github.com/robertsj/poropy/blob/master/pyqtgraph/graphicsItems/ScatterPlotItem.py
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ScatterPlotItem.html
'''

import pyqtgraph as pg
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class SnrPlot(pg.PlotWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.hoverSize = 12
        self.setFocusPolicy(Qt.NoFocus)
        font = QFont()
        font.setPixelSize(12)
        self.getAxis("bottom").setStyle(tickFont=font)
        self.getAxis("bottom").setHeight(30)
        self.getAxis("left").setStyle(tickFont=font)
        self.getAxis("left").setWidth(38)
        # pen = pg.mkPen(color=(255, 0, 0), width=5, style=Qt.SolidLine)
        style = {'color': '#ffffff', 'font-size': '14px'}
        self.setLabel('left', 'SNR', **style)
        self.setLabel('bottom', 'Layer', **style)

        # self.scene() is a pyqtgraph.GraphicsScene.GraphicsScene.GraphicsScene
        self.scene().sigMouseClicked.connect(self.mouse_clicked)


    def mouse_clicked(self, mouseClickEvent):
        # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
        # print('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
        # print(mouseClickEvent(0))
        # pos_click = int(mouseClickEvent.pos()[0])
        # print('Position Clicked: %d' % pos_click)
        pass