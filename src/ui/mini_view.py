#!/usr/bin/env python3


import logging

from qtpy.QtWidgets import QMainWindow, QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel

import numpy as np
import pyqtgraph as pg
# import pyqtgraph.opengl as gl

from src.funcs_zarr import get_zarr_tensor

logger = logging.getLogger(__name__)


class MiniView(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # cfg.data = None

        self.app = pg.mkQApp()
        self.view = pg.GraphicsLayoutWidget()
        # self.view.setBackground('#ffffff')
        drafting_blue = '#004060'
        self.view.setBackground(drafting_blue)
        pg.setConfigOption('foreground', '#f3f6fb')
        pg.setConfigOptions(antialias=True)
        self.plot = self.view.addPlot()

        path = '/Users/joelyancey/glanceem_swift/test_projects/r34_50imgs_2x2/img_src.zarr/s1'
        # z = zarr.open()
        tensor = get_zarr_tensor(path).result()
        print(type(np.asarray(tensor)))
        shape = tensor.shape
        print(f'tensor shape: {tensor.shape}')
        data = np.asarray(tensor)

        app = pg.mkQApp("GLImageItem Example")
        w = gl.GLViewWidget()
        # w.show()
        w.setWindowTitle('pyqtgraph example: GLImageItem')
        w.setCameraPosition(distance=2000)

        ## create volume data set to slice three images from
        # shape = (100,100,70)
        # data = pg.gaussianFilter(np.random.normal(size=shape), (4,4,4))
        # data += pg.gaussianFilter(np.random.normal(size=shape), (15,15,15))*15

        ## slice out three planes, convert to RGBA for OpenGL texture
        # levels = (-0.08, 0.08)
        levels = (0, 255)
        tex1 = pg.makeRGBA(data[shape[0] // 2], levels=levels)[0]  # yz plane
        tex2 = pg.makeRGBA(data[:, shape[1] // 2], levels=levels)[0]  # xz plane
        tex3 = pg.makeRGBA(data[:, :, shape[2] // 2], levels=levels)[0]  # xy plane
        # tex1[:,:,3] = 128
        # tex2[:,:,3] = 128
        # tex3[:,:,3] = 128

        ## Create three image items from textures, add to view
        v1 = gl.GLImageItem(tex1)
        v1.translate(-shape[1] / 2, -shape[2] / 2, 0)
        v1.rotate(90, 0, 0, 1)
        v1.rotate(-90, 0, 1, 0)
        w.addItem(v1)
        v2 = gl.GLImageItem(tex2)
        v2.translate(-shape[0] / 2, -shape[2] / 2, 0)
        v2.rotate(-90, 1, 0, 0)
        w.addItem(v2)
        v3 = gl.GLImageItem(tex3)
        v3.translate(-shape[0] / 2, -shape[1] / 2, 0)
        w.addItem(v3)

        ax = gl.GLAxisItem()
        w.addItem(ax)

        self.layout = QGridLayout()
        self.layout.addWidget(w, 0, 0, 0, 0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        pg.exec()

