"""
Demonstrates GLVolumeItem for displaying volumetric data.
"""
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *

import numpy as np

import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph import functions as fn

import tensorstore as ts

app = pg.mkQApp("pyqtgraph volume viewer")
# app = pg.mkQApp()
# pg.setConfigOptions(antialias=True)

# path = '/Users/joelyancey/glanceem_swift/img_aligned.zarr/s4'
path = '/Users/joelyancey/Downloads/r34_alignment_vijay/r34_alignment/img_aligned.zarr/s4'


def get_zarr_tensor(zarr_path):
    # async def get_zarr_tensor(zarr_path):
    '''
    Returns an asynchronous TensorStore future object which is a webengineview
    into the Zarr image on disk. All TensorStore indexing operations
    produce lazy views.

    Ref: https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

    :param zarr_path:
    :cur_method zarr_path:
    :return: A webengineview into the dataset.
    :rtype: tensorstore.Future
    '''
    # caller = inspect.stack()[1].function
    print(f'Requested: {zarr_path}')
    # node = platform.node()
    # total_bytes_limit = 250_000_000_000  # just under 256 GB
    # if '.tacc.utexas.edu' in node:
    #     # Lonestar6: 256 GB (3200 MT/level) DDR4
    #     # total_bytes_limit = 200_000_000_000
    #     total_bytes_limit = 250_000_000_000 # just under 256 GB
    # else:
    #     total_bytes_limit = 6_000_000_000
    # total_bytes_limit = (20_000_000_000, 200_000_000_000_000)['.tacc.utexas.edu' in platform.node()]
    total_bytes_limit = 1_000_000_000  # 0726+
    future = ts.open({
        'dtype': 'uint8',
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            # 'driver': 'memory',
            'path': zarr_path
        },
        'context': {
            'cache_pool': {'total_bytes_limit': total_bytes_limit},
            'data_copy_concurrency': {'limit': 512},  # 0726+
            'file_io_concurrency': {'limit': 512},  # 0726+
        },
        # 'recheck_cached_data': 'open',
        'recheck_cached_data': True,  # 0726 revert to default (True)
    })
    return future


tensor = get_zarr_tensor(path).result()
shape = tensor.shape
print(f'tensor shape: {tensor.shape}')
data = np.asarray(tensor)
data = np.transpose(data, axes=[2, 1, 0])
# data = np.transpose(data, axes=[2, 0,1])


# win = pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
# win.resize(1000, 600)
# win.setWindowTitle('pyqtgraph example: Plotting')

# view = pg.GraphicsLayoutWidget()
# view.showMaximized()
# layout = pg.GraphicsLayout()
# view.setCentralItem(layout)

w = gl.GLViewWidget()
w.show()
w.setWindowTitle('Demo of PyQtGraph volume viewer')
w.setCameraPosition(distance=200)
# w.setCameraPosition(distance=120, elevation=0, azimuth=0)
# w.pan(0, 0, 10)


# https://gist.github.com/ofgulban/60ba53c46f6870fc30bb1b2117947600
# Prepare data for visualization
d2 = np.zeros(data.shape + (4,))
d2[..., 3] = data**1 * 255  # alpha
d2[..., 0] = d2[..., 3]  # red
d2[..., 1] = d2[..., 3]  # green
d2[..., 2] = d2[..., 3]  # blue



# (optional) RGB orientation lines
# d2[:40, 0, 0] = [255, 0, 0, 255]
# d2[0, :40, 0] = [0, 255, 0, 255]
# d2[0, 0, :40] = [0, 0, 255, 255]
# d2 = d2.astype(np.ubyte)

# levels = (0, 255)
# tex1 = pg.makeRGBA(data[shape[0] // 2], levels=levels)[0]  # yz plane
# tex2 = pg.makeRGBA(data[:, shape[1] // 2], levels=levels)[0]  # xz plane
# tex3 = pg.makeRGBA(data[:, :, shape[2] // 2], levels=levels)[0]  # xy plane
# v1 = gl.GLImageItem(tex1)
# v1.translate(-shape[1] / 2, -shape[2] / 2, 0)
# v1.rotate(90, 0, 0, 1)
# v1.rotate(-90, 0, 1, 0)
# w.addItem(v1)
# v2 = gl.GLImageItem(tex2)
# v2.translate(-shape[0] / 2, -shape[2] / 2, 0)
# v2.rotate(-90, 1, 0, 0)
# w.addItem(v2)
# v3 = gl.GLImageItem(tex3)
# v3.translate(-shape[0] / 2, -shape[1] / 2, 0)
# w.addItem(v3)

# g = gl.GLGridItem()
# g.setSize(x=shape[2], y=shape[1], z=shape[0])
# g.scale(50, 2, 2)
# w.addItem(g)

# v = gl.GLVolumeItem(d2, sliceDensity=1, smooth=True, glOptions='translucent') #defaults
print('Creating volume...')
v = gl.GLVolumeItem(d2, sliceDensity=1, smooth=True, glOptions='translucent') #defaults
# v = gl.GLVolumeItem(d2)
# v.translate(-50,-50,-100)
v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 3)
v.scale(x=2,y=2,z=50)
w.addItem(v)

# widget = QWidget()
# vbl = QVBoxLayout()
# widget.setLayout(vbl)
# vbl.addWidget(w)
#
# widget.show()


# ax = gl.GLAxisItem()
# w.addItem(ax)

if __name__ == '__main__':
    pg.exec()
