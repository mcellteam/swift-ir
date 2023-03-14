#!/usr/bin/env python3

import os
import logging
import numpy as np
from libtiff import TIFF
import zarr
from qtpy.QtCore import QObject, QFileSystemWatcher
from src.ui.dialogs import mendenhall_dialog
from src.funcs_image import ImageSize
from src.funcs_zarr import preallocate_zarr
from src.helpers import renew_directory
import src.config as cfg

logger = logging.getLogger(__name__)

class Mendenhall(QObject):
    """ Mendenhall Protocol For Aligning Images Before Breakfast"""

    def __init__(self, parent=None, data=None, reopen=False):
        QObject.__init__(self)
        self.parent = parent
        self.data = data
        self._index = 0
        self.dest = cfg.data.dest()
        self.zarr_name = 'mendenhall.zarr'
        self.zarr_group = 'grp'
        self.zarr_path = os.path.join(self.dest, self.zarr_name, self.zarr_group)
        self.sink = None
        self.watchmen = None
        self._files = []
        self._empty = True
        self._first = None
        self.image_size = None
        if reopen:
            self._empty = False
            self.sink = cfg.data.set_source_path()
            self._files = os.listdir(self.sink)
            self._index = len(self._files)


    def set_directory(self):
        self.sink = mendenhall_dialog()
        cfg.data.set_source_path(self.sink)
        cfg.main_window._saveProjectToFile()

    def start_watching(self):
        self.watchmen = QFileSystemWatcher() # files(), directories()
        self.watchmen.addPath(self.sink)
        self.watchmen.directoryChanged.connect(self.watchmen_slot)
        logger.info(f'Watching: {self.sink}')

    def stop_watching(self):
        self.watchmen = None

    def watchmen_slot(self):
        logger.info('watchmen_slot:')
        contents = os.listdir(self.sink)
        print('contents: ' + str(contents))
        print('contents[0]: ' + str(contents[0]))
        if self._empty == True:
            self.first_image(contents[0])
            self._empty = False
        diff = list(set(contents) - set(self._files))
        if len(diff) != 1:
            logger.warning('Watchmen: The difference of set suggests that multiple files have '
                           'have been added or removed simultaneously - Returning')
            return
        img = diff[0]
        logger.info(f'New Image (or possibly removed): {img}')
        self.add_image(os.path.join(self.sink, img))
        self._files = contents

    def n_files(self):
        return len(self._files)

    def first_image(self, img):
        logger.critical('first_image:')
        cfg.main_window.hud.post('The First Microscope Image Has Arrived!')
        self._first = os.path.join(self.sink, img)
        self.image_size = ImageSize(self._first)
        cfg.data.set_image_size_directly(size=self.image_size)
        cfg.main_window.hud.post(f'Expecting Images Of Size: {self.image_size}')
        self.preallocate()
        cfg.project_tab.openViewZarr()

    def add_image(self, img):
        # cfg.main_window.hud.post(f"Adding Image\n'{os.path.basename(img)}'...")
        cfg.data.append_image(img)
        cfg.data.link_reference_sections()
        self.img_to_zarr(ID=self._index, fn=img)
        self._index += 1
        # cfg.main_window.initNgServer()
        # cfg.main_window.ng_workers['scale_1'].invalidateAllLayers()
        cfg.project_tab.openViewZarr()

    def img_to_zarr(self, ID, fn):
        cfg.main_window.hud.post(f"Converting Image ID ({ID}) '{os.path.basename(fn)}' To Zarr...")
        tif = TIFF.open(fn)
        img = tif.read_image()[:, ::-1]  # numpy array
        store = zarr.open(self.zarr_path)
        store[ID, :, :] = img
        store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

    def preallocate(self):
        if self.image_size:
            preallocation_size = 10
            cfg.main_window.hud.post(f'Preallocating Zarr, Preallocation Size: {preallocation_size}')
            preallocate_zarr(name=self.zarr_name,
                             group=self.zarr_group,
                             dimx=self.image_size[0],
                             dimy=self.image_size[1],
                             dimz=10,                # arbitrary z-dim for now
                             dtype='uint8',
                             overwrite=False
                             )
            pass
        else:
            logger.warning('Cannot Preallocate Yet, Image Size Is Still Unknown')

