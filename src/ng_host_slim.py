#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server'''


import inspect
try:
    caller = inspect.stack()[1].function
except:
    caller = None
    pass
import os
import copy
import pprint
import logging
import datetime
import argparse
import traceback
import platform
from math import floor
import numcodecs
numcodecs.blosc.use_threads = False
import tensorstore as ts
import neuroglancer as ng
import neuroglancer.webdriver
from qtpy.QtCore import QRunnable, QObject, Slot, Signal
if caller != None:
    import src.config as cfg
from src.helpers import exist_aligned_zarr_cur_scale

__all__ = ['NgHostSlim']

logger = logging.getLogger(__name__)


class Config():
    def __init__(self):
        self.viewer = None
        self.LV = None
        self.tensor = None
        self.url = None
        self.DEBUG_NEUROGLANCER = True
        self.HEADLESS = False


def get_zarr_tensor(zarr_path):
    '''
    Returns an asynchronous TensorStore future object which is a webengineview
    into the Zarr image on disk. All TensorStore indexing operations
    produce lazy views.

    Ref: https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

    :param zarr_path:
    :type zarr_path:
    :return: A webengineview into the dataset.
    :rtype: tensorstore.Future
    '''

    node = platform.node()
    if '.tacc.utexas.edu' in node:
        # Lonestar6: 256 GB (3200 MT/s) DDR4
        # total_bytes_limit = 200_000_000_000
        total_bytes_limit = 250_000_000_000 # just under 256 GB
    else:
        total_bytes_limit = 6_000_000_000_000
    # total_bytes_limit = (6_000_000_000, 200_000_000_000_000)['.tacc.utexas.edu' in platform.node()]
    arr = ts.open({
        'dtype': 'uint8',
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            'path': zarr_path
        },
        'context': {
            'cache_pool': {'total_bytes_limit': total_bytes_limit},
            'data_copy_concurrency': {'limit': 128},
            'file_io_concurrency': {'limit': 128},
        },
        'recheck_cached_data': 'open',
    })
    return arr


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal(int)
    mpUpdate = Signal()

# class NgHostSlim(QObject):
# class NgHostSlim(QRunnable):
class NgHostSlim(QRunnable):
    def __init__(self, parent, resolution=None, project=False):
        # QObject.__init__(self)
        QRunnable.__init__(self)
        self.parent = parent
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.bind = '127.0.0.1'
        self.port = 9000
        self.project = project
        # self.shape = shape
        if resolution == None:
            self.resolution = (50, 2, 2)
        self.signals = WorkerSignals()

    def __del__(self):
        try:
            caller = inspect.stack()[1].function
            print('__del__ was called by [%s] on NgHost, created:%s' % (caller, self.created))
        except:
            print('Unable to decipher who caller is')

    def __str__(self):
        return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(cfg.viewer.state)

    # @Slot()
    # def run(self):
    #     try:
    #         cfg.viewer = ng.Viewer()
    #     except:
    #         traceback.print_exc()

    def get_loading_progress(self):
        return neuroglancer.webdriver.driver.execute_script('''
    const userLayer = viewer.layerManager.getLayerByName("segmentation").layer;
    return userLayer.renderLayers.map(x => x.layerChunkProgressInfo)
     ''')

    def request_layer(self):
        return floor(cfg.viewer.state.position[0])

    def initViewer(self,
                   show_ui_controls=True,
                   show_panel_borders=False,
                   show_scale_bar=True,
                   show_axis_lines=True,
                   matchpoint=None):
        print(f'Initializing Neuroglancer Viewer...')
        ng.server.debug = cfg.DEBUG_NEUROGLANCER
        cfg.viewer = ng.Viewer()
        ng.set_server_bind_address(bind_address=self.bind, bind_port=self.port)

        if self.project:
            if exist_aligned_zarr_cur_scale(): zd = 'img_aligned.zarr'
            else:                              zd = 'img_src.zarr'
            self.path = os.path.join(cfg.data.dest(), zd, 's' + str(cfg.data.scale_val()))
            scale = cfg.data.scale()
            coord_space = [cfg.data.res_z(s=scale),
                           cfg.data.res_y(s=scale),
                           cfg.data.res_x(s=scale)]
        else:
            coord_space = self.resolution

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=coord_space, )

        with cfg.viewer.txn() as s:
            adjustment = 1.04
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.concurrent_downloads = 512
            # s.cross_section_scale = cross_section_scale * adjustment
            s.show_scale_bar = show_scale_bar
            s.show_axis_lines = show_axis_lines
            s.crossSectionBackgroundColor = '#808080'  # 128 grey
            try:
                cfg.tensor = get_zarr_tensor(self.path).result()
                print('TensorStore Object Created Successfully!')
            except Exception as e:
                print(e)
                try:
                    logger.error('Invalid Zarr. Unable To Create Tensor for Zarr Array', logging.ERROR)
                    cfg.main_window.hud.post('Invalid Zarr. Unable To Create Tensor for Zarr Array', logging.ERROR)
                except:
                    pass
            # pprint.pprint(cfg.tensor.spec().to_json())
            cfg.LV = ng.LocalVolume(
                data=cfg.tensor,
                volume_type='image',
                dimensions=self.coordinate_space,
                voxel_offset=[0, 0, 0],
                # downsampling=None
            )
            s.layers['layer'] = ng.ImageLayer(source=cfg.LV)

        with cfg.viewer.config_state.txn() as s:
            s.show_ui_controls = show_ui_controls
            s.show_panel_borders = show_panel_borders

        # self._layer = self.request_layer()
        cfg.url = str(cfg.viewer)
        print(f'url: {cfg.url}')

        if cfg.HEADLESS:
            cfg.webdriver = neuroglancer.webdriver.Webdriver(cfg.viewer, headless=False, browser='chrome')

    def url(self):
        return cfg.url

    def on_state_changed(self):
        try:
            request_layer = floor(cfg.viewer.state.position[0])
            if request_layer == self._layer:
                logger.debug('State Changed, But Layer Is The Same - Suppressing The Callback Signal')
                return
            else:
                self._layer = request_layer
            self.signals.stateChanged.emit(request_layer)
        except:
            # print_exception()
            logger.error('ERROR')


def obj_to_string(obj, extra='    '):
    return str(obj.__class__) + '\n' + '\n'.join(
        (extra + (str(item) + ' = ' +
                  (obj_to_string(obj.__dict__[item], extra + '    ') if hasattr(obj.__dict__[item],
                                                                                '__dict__') else str(
                      obj.__dict__[item])))
         for item in sorted(obj.__dict__)))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--path', type=str, default='.', help='Path To Zarr')
    args = ap.parse_args()

    cfg = Config()
    # nghost = NgHostSlim(parent=None, path=args.path, size=args.size)
    nghost = NgHostSlim(parent=None, project=False)
    nghost.path = args.path
    nghost.initViewer()

