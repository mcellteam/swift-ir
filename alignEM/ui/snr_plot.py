#!/usr/bin/env python3

'''
https://github.com/robertsj/poropy/blob/master/pyqtgraph/graphicsItems/ScatterPlotItem.py
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ScatterPlotItem.html
'''

import pyqtgraph as pg


class SnrPlot(pg.PlotWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.hoverSize = 10

        # self.scene() is a pyqtgraph.GraphicsScene.GraphicsScene.GraphicsScene
        self.scene().sigMouseClicked.connect(self.mouse_clicked)


    def mouse_clicked(self, mouseClickEvent):
        # mouseClickEvent is a pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent
        # print('clicked plot 0x{:x}, event: {}'.format(id(self), mouseClickEvent))
        # print(mouseClickEvent(0))
        # pos_click = int(mouseClickEvent.pos()[0])
        # print('Position Clicked: %d' % pos_click)
        pass