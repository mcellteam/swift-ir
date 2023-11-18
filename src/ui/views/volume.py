"""
Demonstrates GLVolumeItem for displaying volumetric data.

Source code for pyqtgraph.opengl.GLViewWidget:
https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/opengl/GLViewWidget.html#GLViewWidget

PyQtGraph Global Configuration Options:
https://pyqtgraph.readthedocs.io/en/latest/api_reference/config_options.html

However, it is possible to generate an image from a GLViewWidget by using QGLWidget.grabFrameBuffer or QGLWidget.renderPixmap:
glview.grabFrameBuffer().save('fileName.png')



"""
import sys

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from qtpy.QtCore import *
from qtpy.QtWidgets import *

# from pyqtgraph.Qt.QtCore import *
# from pyqtgraph.Qt.QtGui import *
# from pyqtgraph.Qt import QtGui
# QtGui.QApplication.setGraphicsSystem("raster") # raster/native/opengl

# Performance issues:
# https://stackoverflow.com/questions/63855707/realtime-visualisation-bottleneck-with-pyqtgraph-plotcurveitem

try:
    import OpenGL
    pg.setConfigOption('useOpenGL', True)
    pg.setConfigOption('enableExperimental', True)
except Exception as e:
    print(f"Enabling OpenGL failed with {e}. Will result in slow rendering. Try installing PyOpenGL.")


from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager

import tensorstore as ts

app = pg.mkQApp("pyqtgraph volume viewer")
# app = pg.mkQApp()
# pg.setConfigOptions(antialias=True)

# file_path = '/Users/joelyancey/glanceem_swift/img_aligned.zarr/s4'
path = '/Users/joelyancey/alignem_data/alignments/test3.alignment/zarr_reduced/s4'

class PythonConsole(RichJupyterWidget):

    def __init__(self, customBanner=None, *args, **kwargs):
        super(PythonConsole, self).__init__(*args, **kwargs)
        # self.set_default_style(colors='nocolor')
        self.prompt_to_top()

        if customBanner is not None:
            self.banner = customBanner

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel(show_banner=False)
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = self._kernel_manager.client()
        self.kernel_client.start_channels()
        self.setFocusPolicy(Qt.NoFocus)

        self.execute_command('import variables')
        self.execute_command('import os, sys, copy, json, stat, time, glob')
        self.execute_command('import zarr')
        self.execute_command('import neuroglancer as ng')
        self.execute_command('from qtpy import QtCore, QtGui, QtWidgets')
        self.execute_command('from qtpy.QtWidgets import *')
        self.execute_command('from qtpy.QtCore import *')
        self.execute_command('from qtpy.QtGui import *')
        self.execute('clear')
        # self.out_prompt = 'AlignEM [<span class="out-prompt-number">%i</span>]: '

        import IPython;
        IPython.get_ipython().execution_count = 0
        self.print_text('AlignEM [<span class="out-prompt-number">%i</span>]: ')

        def stop():
            self.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            # guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)

    def push_vars(self, variableDict):
        """Push dictionary variables to the Jupyter console widget"""
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """Clears the terminal"""
        self._control.clear()
        # self.kernel_manager

    def print_text(self, text):
        """Print to the console"""
        self._append_plain_text(text)

    def execute_command(self, command):
        """Execute a command in the getFrameScale of the console widget"""
        self._execute(command, False)

    def set_color_none(self):
        """Set no color scheme"""
        self.set_default_style(colors='nocolor')

    def set_color_linux(self):
        """Set linux color scheme"""
        self.set_default_style(colors='linux')


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
    total_bytes_limit = 1_000_000_000  # 0726+
    future = ts.open({
        'dtype': 'uint8',
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            # 'driver': 'memory',
            'file_path': zarr_path
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


class VolumeWidget(QWidget):

    def __init__(self):
        super(VolumeWidget, self).__init__()
        print(f"----> get_volume_widget ---->")

        # data = get_zarr_tensor(file_path).result()
        self.data = data = get_zarr_tensor(path).result()
        # shape = tensor.shape
        # print(f'tensor shape: {tensor.shape}')
        # data = np.asarray(tensor)
        # data = tensor
        data = np.transpose(data, axes=[2, 1, 0])
        # data = np.transpose(data, axes=[2, 0,1])
        self.setMouseTracking(True)

        # win = pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
        # win.resize(1000, 600)
        # win.setWindowTitle('pyqtgraph example: Plotting')

        # view = pg.GraphicsLayoutWidget()
        # view.showMaximized()
        # layout = pg.GraphicsLayout()
        # view.setCentralItem(layout)

        self.glvolume = gl.GLViewWidget()
        # self.glvolume.show()
        self.glvolume.setWindowTitle('Demo of PyQtGraph volume viewer')
        # self.glvolume.setCameraPosition(distance=200)
        # self.glvolume.setCameraPosition(distance=120, elevation=0, azimuth=0)
        # self.glvolume.pan(0, 0, 10)

        # 2023-10-30
        # https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243

        # https://gist.github.com/ofgulban/60ba53c46f6870fc30bb1b2117947600
        # Prepare data for visualization
        d2 = np.zeros(data.shape + (4,))
        # d2[..., 3] = data**1 * 255  # alpha
        # d2[..., 3] = data**1 * 255  # alpha
        # d2[..., 0] = d2[..., 3]  # red
        # d2[..., 1] = d2[..., 3]  # green
        # d2[..., 2] = d2[..., 3]  # blue

        # https://gist.github.com/ofgulban/a5c23bbcb843d690fa07038e5b7a4801 *note: different link from above
        # DO NOT MODIFY - ORIGINAL
        # d2[..., 0] = data * (255. / (data.max() / 1))
        # d2[..., 1] = d2[..., 0]
        # d2[..., 2] = d2[..., 0]
        # d2[..., 3] = d2[..., 0]
        # d2[..., 3] = (d2[..., 3].astype(float) / 255.) ** 2 * 255

        # OKAY TO MODIFY
        alpha = 200.
        d2[..., 0] = data * (alpha / (data.max() / 1))
        d2[..., 1] = d2[..., 0]
        d2[..., 2] = d2[..., 0]
        d2[..., 3] = d2[..., 0]
        d2[..., 3] = (d2[..., 3].astype(float) / 255.) ** 2 * 255

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
        # self.glvolume.addItem(v1)
        # v2 = gl.GLImageItem(tex2)
        # v2.translate(-shape[0] / 2, -shape[2] / 2, 0)
        # v2.rotate(-90, 1, 0, 0)
        # self.glvolume.addItem(v2)
        # v3 = gl.GLImageItem(tex3)
        # v3.translate(-shape[0] / 2, -shape[1] / 2, 0)
        # self.glvolume.addItem(v3)

        # g = gl.GLGridItem()
        # g.setSize(x=shape[2], y=shape[1], z=shape[0])
        # g.scale(50, 2, 2)
        # self.glvolume.addItem(g)

        # v = gl.GLVolumeItem(d2, sliceDensity=1, smooth=True, glOptions='translucent') #defaults
        print('Creating volume...')
        v = gl.GLVolumeItem(d2, # Volume data to be rendered. Must be 4D numpy array (x, y, z, RGBA) with dtype=ubyte.
                            sliceDensity=1, # Density of slices to render through the volume. A value of 1 means one slice per voxel.
                            smooth=False, # (bool) If True, the volume slices are rendered with linear interpolation
                            glOptions='opaque')  # defaults

        # opaque        Enables depth testing and disables blending
        # translucent   Enables depth testing and blending
        #               Elements must be drawn sorted back-to-front for
        #               translucency to work correctly.
        # additive      Disables depth testing, enables blending.
        #               Colors are added together, so sorting is not required.
        # v = gl.GLVolumeItem(d2)
        # v.translate(-50,-50,-100)

        print(f"d2.shape   : {d2.shape}")
        print(f"data.shape : {data.shape}")

        # v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 3)
        # v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 2)
        v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 2)
        # v.scale(x=2,y=2,z=2)
        v.scale(x=1, y=1, z=1)
        self.glvolume.addItem(v)

        vbl = QVBoxLayout()
        vbl.setContentsMargins(0,0,0,0)
        vbl.addWidget(self.glvolume)
        self.setLayout(vbl)

        self.glvolume.show()

        # ax = gl.GLAxisItem()
        # self.glvolume.addItem(ax)
        print(f"<----  <----")


def get_GLViewWidget():
    print(f"----> get_volume_widget ---->")

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

    glvw = gl.GLViewWidget()
    # glvw.show()
    glvw.setWindowTitle('Demo of PyQtGraph volume viewer')
    # glvw.setCameraPosition(distance=200)
    # glvw.setCameraPosition(distance=120, elevation=0, azimuth=0)
    # glvw.pan(0, 0, 10)

    # 2023-10-30
    # https://gist.github.com/markjay4k/da2f55e28514be7160a7c5fbf95bd243


    # https://gist.github.com/ofgulban/60ba53c46f6870fc30bb1b2117947600
    # Prepare data for visualization
    d2 = np.zeros(data.shape + (4,))
    # d2[..., 3] = data**1 * 255  # alpha
    # d2[..., 3] = data**1 * 255  # alpha
    # d2[..., 0] = d2[..., 3]  # red
    # d2[..., 1] = d2[..., 3]  # green
    # d2[..., 2] = d2[..., 3]  # blue


    # https://gist.github.com/ofgulban/a5c23bbcb843d690fa07038e5b7a4801 *note: different link from above
    #DO NOT MODIFY - ORIGINAL
    # d2[..., 0] = data * (255. / (data.max() / 1))
    # d2[..., 1] = d2[..., 0]
    # d2[..., 2] = d2[..., 0]
    # d2[..., 3] = d2[..., 0]
    # d2[..., 3] = (d2[..., 3].astype(float) / 255.) ** 2 * 255



    # OKAY TO MODIFY
    alpha = 128.
    d2[..., 0] = data * (alpha / (data.max() / 1))
    d2[..., 1] = d2[..., 0]
    d2[..., 2] = d2[..., 0]
    d2[..., 3] = d2[..., 0]
    d2[..., 3] = (d2[..., 3].astype(float) / 255.) ** 2 * 255



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
    # glvw.addItem(v1)
    # v2 = gl.GLImageItem(tex2)
    # v2.translate(-shape[0] / 2, -shape[2] / 2, 0)
    # v2.rotate(-90, 1, 0, 0)
    # glvw.addItem(v2)
    # v3 = gl.GLImageItem(tex3)
    # v3.translate(-shape[0] / 2, -shape[1] / 2, 0)
    # glvw.addItem(v3)

    # g = gl.GLGridItem()
    # g.setSize(x=shape[2], y=shape[1], z=shape[0])
    # g.scale(50, 2, 2)
    # glvw.addItem(g)

    # v = gl.GLVolumeItem(d2, sliceDensity=1, smooth=True, glOptions='translucent') #defaults
    print('Creating volume...')
    v = gl.GLVolumeItem(d2, sliceDensity=1, smooth=False, glOptions='translucent') #defaults
    # v = gl.GLVolumeItem(d2)
    # v.translate(-50,-50,-100)

    print(f"d2.shape   : {d2.shape}")
    print(f"data.shape : {data.shape}")

    # v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 3)
    # v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 2)
    v.translate(dx=-d2.shape[0] / 2, dy=-d2.shape[1] / 2, dz=-d2.shape[2] / 2)
    # v.scale(x=2,y=2,z=2)
    v.scale(x=1,y=1,z=1)
    glvw.addItem(v)

    # ax = gl.GLAxisItem()
    # glvw.addItem(ax)
    print(f"<---- Returning {type(glvw)} <----")
    return glvw

if __name__ == '__main__':
    print('Running ' + __file__ + '.__main__()')
    pg.setConfigOption('crashWarning', True)
    pg.setConfigOption('useCupy', True)
    print(f"____PyQtGraph Global Config____")
    print(f"Use OpenGL? {pg.getConfigOption('useOpenGL')}") #Enable OpenGL in GraphicsView.
    print(f"Use CuPy? {pg.getConfigOption('useCupy')}") #Use cupy to perform calculations on the GPU. Only currently applies to ImageItem and its associated functions.
    print(f"Use Numba? {pg.getConfigOption('useNumba')}") #Use numba acceleration where implemented.
    print(f"Enable experimental? {pg.getConfigOption('enableExperimental')}")
    print(f"Crash warning? {pg.getConfigOption('crashWarning')}")
    print(f"Antialias? {pg.getConfigOption('antialias')}")
    print(f"Exit cleanup? {pg.getConfigOption('exitCleanup')}") # Attempt to work around some exit crash bugs in PyQt and PySide.
    app = QApplication([])

    mw = QMainWindow()

    # glvw = get_GLViewWidget()
    variables.vw = VolumeWidget()
    variables.vw.glvolume.opts['azimuth'] = 0

    # glvw.opts = {
    #     'center': Vector(0, 0, 0),  ## will always appear at the center of the widget
    #     'rotation': QQuaternion(1, 0, 0, 0),  ## camera rotation (quaternion:wxyz)
    #     'distance': 10.0,  ## distance of camera from center
    #     'fov': 60,  ## horizontal field of view in degrees
    #     'elevation': 30,  ## camera's angle of elevation in degrees
    #     'azimuth': 45,  ## camera's azimuthal angle in degrees
    #     ## (rotation around z-axis 0 points along x-axis)
    #     'viewport': None,  ## glViewport params; None == whole widget
    #     ## note that 'viewport' is in device pixels
    #     'rotationMethod': 'euler' #  (*) mechanism to drive the rotation method,‘euler’ | ‘quaternion’ (default=‘euler’)
    # }

    pc = PythonConsole()
    # pc = pyqtgraph.console.ConsoleWidget()
    pc.setFixedHeight(300)



    w = QWidget()
    vbl = QVBoxLayout()
    vbl.setContentsMargins(0,0,0,0)
    vbl.addWidget(variables.vw)
    vbl.addWidget(pc)
    w.setLayout(vbl)

    variables.vw.show()


    mw.setCentralWidget(w)



    mw.setFixedSize(600,600)
    mw.show()



    sys.exit(app.exec())

