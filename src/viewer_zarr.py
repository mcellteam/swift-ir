#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server'''

import os
import copy
import math
import json
import inspect
import logging
import datetime
import argparse
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
from qtpy.QtCore import QObject, Signal
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt
from src.shaders import ann_shader
import src.config as cfg

__all__ = ['ZarrViewer']

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

log = logging.getLogger(__name__)


class WorkerSignals(QObject):
    stateChanged = Signal(int)
    zoomChanged = Signal(float)

class ZarrViewer(neuroglancer.Viewer):

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.bootstrap()

    def __del__(self):
        caller = inspect.stack()[1].function
        log.warning('__del__ called by [%s], created: %s'% (caller, self.created))

    def __repr__(self):
        return copy.deepcopy(self.state)

    def url(self):
        return self.get_viewer_url()

    def tensorstore(self, path):
        return get_zarr_tensor(path).result()

    def zarrstore(self, path):
        return zarr.open(path)

    def validate_zarr(self, path) -> bool:
        if os.path.isdir(path):
            if '.zarray' in os.listdir(path):
                return True
        return False

    def coordinates(self, res=(50,2,2)):
        return neuroglancer.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=res, )

    def local_volume(self, store, coords):
        return neuroglancer.LocalVolume(
            volume_type='image',
            data=store,
            dimensions=coords,
            voxel_offset=[0, 0, 0],
        )

    def get_layout(self):
        sw = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        return sw[cfg.main_window.comboboxNgLayout.currentText()]

    def add_callback(self, fn):
        self.shared_state.add_changed_callback(fn)

    def add_deferred_callback(self, fn):
        self.shared_state.add_changed_callback(lambda: self.defer_callback(fn))

    def add_layer(self):
        pass

    def bootstrap(self):
        log.info('Configuring txn...')

        store = self.tensorstore(self.path)
        coords = self.coordinates(res=(50,2,2))
        LV = self.local_volume(store, coords)
        layout = self.get_layout()
        self.add_callback(self.on_state_changed)

        with self.txn() as s:
            s.layout.type = layout
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.position=[0, store.shape[1]/2, store.shape[2]/2]
            s.layers['layer'] = neuroglancer.ImageLayer(source=LV, shader=cfg.SHADER)
            s.crossSectionBackgroundColor = '#808080' # 128 grey

        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = False
            # s.viewer_size = [100,100]

        self._layer = self.get_loc()
        self.shared_state.add_changed_callback(self.on_state_changed)


    def get_loc(self):
        return math.floor(self.state.position[0])

    def on_state_changed(self):
        pass



if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    zv = ZarrViewer()
    zv.configure_txn()
