#!/usr/bin/env python3
'''
By:  Joel Yancey
Date:  2023-01-04
Purpose: This script can be used to open large-volume Zarr image arrays in Neuroglancer. It relies on Neuroglancer
and TensorStore. It only needs to be pointed at a directory containing '.zarray'. Be sure to run Python (3.8+) in
interactive mode by specifying the '-i' cli option. There are two Python modules required:  Neuroglancer, TensorStore

# Install Python modules:
$ pip install neuroglancer
$ pip install tensorstore

# For example, view a local Zarr dataset (perhaps of aligned serial section EM images, or not) in Neuroglancer:
$ python3 -i ng_bootstrap.py -p ./scratch/img_src.zarr/s1 --browser firefox

Neuroglancer:  https://github.com/google/neuroglancer
Tensor:        https://github.com/google/tensorstore
Zarr:          https://zarr.readthedocs.io/en/stable/spec/v2.html
'''

import json
import copy
import math
import inspect
import logging
import datetime
import argparse
import traceback
import tensorstore as ts
import neuroglancer as ng
import neuroglancer.webdriver


log = logging.getLogger(__name__)


class Config():
    def __init__(self, args):
        # HTTP bind address and port, configurable from here
        self.bind = '127.0.0.1'
        self.port = 9000

        # Neuroglancer server settings, configurable from here
        self.gpu_memory_limit = -1
        self.system_memory_limit = -1
        self.concurrent_downloads = 512
        self.neuroglancer_server_debug = True  # verbose neuroglancer

        # TensorStore settings
        self.cache_pool_total_bytes_limit = 250_000_000_000  # Lonestar6: 256 GB (3200 MT/s) DDR4
        self.dtype = 'uint8'
        self.driver = 'zarr'

        # Neuroglancer emViewer options, configurable from here
        self.show_panel_borders = False
        self.show_ui_controls = False
        self.show_scale_bar = True
        self.show_axis_lines = False
        self.background_color = '#808080'  # 128 grey

        # Command line options
        self.PATH = args.path[0]
        self.VOXELSIZE = args.voxelsize
        self.BROWSER = args.browser
        self.HEADLESS = args.headless


def get_zarr_tensor(path, bytes_limit, dtype, driver):
    '''
    Returns an asynchronous TensorStore future object.
    Ref: https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice
    '''
    arr = ts.open({
        'dtype': dtype,
        'driver': driver,
        'kvstore': {
            'driver': 'file',
            'path': path
        },
        'context': {
            'cache_pool': {'total_bytes_limit': bytes_limit},
            'data_copy_concurrency': {'limit': 128},
            'file_io_concurrency': {'limit': 128},
        },
        'recheck_cached_data': 'open',
    })
    return arr


class NgBootstrap():
    def __init__(self, cfg):
        self.created = datetime.datetime.now()
        self.cfg = cfg
        self.LV = None
        self.url = None
        self.webdriver = None

    def __del__(self):
        log.info('__del__ was called by [%s] on EMViewer, created:%s' % (inspect.stack()[1].function, self.created))

    def __repr__(self):
        return copy.deepcopy(self.viewer.state)

    def request_layer(self):
        return math.floor(self.viewer.state.position[0])

    def show_webdriver_log(self):
        if self.webdriver:
            log.info(f'Webdriver Log:\n{json.dumps(self.webdriver.get_log(), indent=2)}')

    def initViewer(self):
        log.info(f'Initializing Neuroglancer Viewer...')
        ng.server.debug = self.cfg.neuroglancer_server_debug
        self.viewer = ng.Viewer()
        ng.set_server_bind_address(bind_address=self.cfg.bind, bind_port=self.cfg.port)

        with self.viewer.txn() as s:
            s.gpu_memory_limit     = self.cfg.gpu_memory_limit
            s.system_memory_limit  = self.cfg.system_memory_limit
            s.concurrent_downloads = self.cfg.concurrent_downloads
            s.show_scale_bar       = self.cfg.show_scale_bar
            s.show_axis_lines      = self.cfg.show_axis_lines
            s.crossSectionBackgroundColor = self.cfg.background_color
            try:
                self.tensor = get_zarr_tensor(
                    path=self.cfg.PATH,
                    dtype=self.cfg.dtype,
                    driver=self.cfg.driver,
                    bytes_limit=self.cfg.cache_pool_total_bytes_limit
                ).result()
                log.info('TensorStore Object Created Successfully!')
            except Exception as e:
                traceback.print_exception(type(e), e, e.__traceback__)
                log.error('Invalid Zarr. Unable To Create Tensor for Zarr Array')

            self.coordinate_space = ng.CoordinateSpace(
                names=['z', 'y', 'x'],
                units=['nm', 'nm', 'nm'],
                scales=self.cfg.VOXELSIZE,
            )

            json.dumps(self.tensor.spec().to_json(), indent=2)
            self.LV = ng.LocalVolume(
                data=self.tensor,
                volume_type='image',
                dimensions=self.coordinate_space,
                voxel_offset=[0, 0, 0],
            )
            s.layers['layer'] = ng.ImageLayer(source=self.LV)

        with self.viewer.config_state.txn() as s:
            s.show_ui_controls = self.cfg.show_ui_controls
            s.show_panel_borders = self.cfg.show_panel_borders

        self.url = str(self.viewer)
        print('\n\nURL: %s\n' % self.url)

        self.webdriver = neuroglancer.webdriver.Webdriver(
            self.viewer,
            headless=self.cfg.HEADLESS,
            browser=self.cfg.BROWSER,
        )


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument(
        '-p',
        '--path',
        nargs='*',  # 0 or more values expected => creates a list
        type=str,
        required=True,
        help='<Required> Path to directory containing .zarray.'
    )
    ap.add_argument(
        '-v',
        '--voxelsize',
        nargs=3,
        type=list,
        default=[50, 2, 2],
        help='Voxel size in Z, Y, and X dimensions (nm).'
    )
    ap.add_argument(
        '--browser',
        choices=['chrome', 'firefox'],
        default='chrome',
        help='Browser preference.'
    )
    ap.add_argument(
        '--headless',
        action='store_true',
        help='Do not launch BROWSER, just show the link.'
    )

    args = ap.parse_args()
    nghost = NgBootstrap(cfg=Config(args))
    nghost.initViewer()
    nghost.show_webdriver_log()