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
from qtpy.QtCore import QObject, Slot, Signal
if caller != None:
    import src.config as cfg

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

class NgHostSlim(QObject):
    def __init__(self, parent, path, shape, resolution=None):
        QObject.__init__(self)
        self.parent = parent
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.bind = '127.0.0.1'
        self.port = 9000
        self.path = path
        self.shape = shape
        if resolution == None:
            self.resolution = (50, 2, 2)
        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm','nm','nm'],
            scales=self.resolution,
        )

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

    @Slot()
    def run(self):
        try:
            cfg.viewer = ng.Viewer()
        except:
            traceback.print_exc()

    def request_layer(self):
        return floor(cfg.viewer.state.position[0])

    def initViewer(self,
                   show_ui_controls=True,
                   show_panel_borders=False,
                   show_scale_bar=True,
                   show_axis_lines=True):
        print(f'Initializing Neuroglancer Viewer...')
        ng.server.debug = cfg.DEBUG_NEUROGLANCER
        cfg.viewer = ng.Viewer()
        ng.set_server_bind_address(bind_address=self.bind)
        # src_width, src_height = self.size[0], self.size[1]
        # max_width, max_height = src_width, src_height
        # widget_size = cfg.main_window.ng_browser.geometry().getRect()
        # widget_height = widget_size[3] - 36 # subtract pixel height of Neuroglancer toolbar
        # widget_width = widget_size[2]
        # tissue_height = self.resolution[1] * max_height  # nm
        # cross_section_height = (tissue_height / widget_height) * 1e-9  # nm/pixel
        # tissue_width = self.resolution[2] * max_width  # nm
        # cross_section_width = (tissue_width / widget_width) * 1e-9  # nm/pixel
        # cross_section_scale = max(cross_section_height, cross_section_width)

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
                print('Unable To Get Zarr Tensor')
            # pprint.pprint(cfg.tensor.spec().to_json())
            cfg.LV = ng.LocalVolume(
                data=cfg.tensor,
                volume_type='image',
                dimensions=self.coordinate_space,
                voxel_offset=[0, 0, 0],
                downsampling=None
            )
            s.layers['layer'] = ng.ImageLayer(source=cfg.LV)
            # pos_x, pos_y = self.shape[2] / 2, self.size[1] / 2
            # s.position = [0, pos_x, pos_y]

        with cfg.viewer.config_state.txn() as s:
            s.show_ui_controls = show_ui_controls
            s.show_panel_borders = show_panel_borders

        # self._layer = self.request_layer()
        cfg.url = str(cfg.viewer)
        print(f'url: {cfg.url}')

        if cfg.HEADLESS:
            cfg.webdriver = neuroglancer.webdriver.Webdriver(cfg.viewer, headless=False, browser='chrome')


def obj_to_string(obj, extra='    '):
    return str(obj.__class__) + '\n' + '\n'.join(
        (extra + (str(item) + ' = ' +
                  (obj_to_string(obj.__dict__[item], extra + '    ') if hasattr(obj.__dict__[item],
                                                                                '__dict__') else str(
                      obj.__dict__[item])))
         for item in sorted(obj.__dict__)))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--path', type=str, default='.', help='Path to data')
    ap.add_argument('-s', '--size', type=tuple, default=(4096,4096), help='Size of images in 2D')
    args = ap.parse_args()

    cfg = Config()
    # nghost = NgHostSlim(parent=None, path=args.path, size=args.size)
    nghost = NgHostSlim(parent=None,
                        path='.',
                        shape=(4096,4096)
                        )
    nghost.initViewer()

