#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server

https://github.com/seung-lab/NeuroglancerAnnotationUI/blob/master/examples/statebuilder_examples.ipynb

Position, layout, and zoom options

View options that do not affect individual layers can be set with a dict passed to the view_kws argument in StateBuilder, which are passed to viewer.set_view_options.

    show_slices : Boolean, sets if slices are shown in the 3d view. Defaults to False.
    layout : xy-3d/xz-3d/yz-3d (sections plus 3d pane), xy/yz/xz/3d (only one pane), or 4panel (all panes). Default is xy-3d.
    show_axis_lines : Boolean, determines if the axis lines are shown in the middle of each view.
    show_scale_bar : Boolean, toggles showing the scale bar.
    orthographic : Boolean, toggles orthographic view in the 3d pane.
    position : 3-element vector, determines the centered location.
    zoom_image : Zoom level for the imagery in units of nm per voxel. Defaults to 8.
    zoom_3d : Zoom level for the 3d pane. Defaults to 2000. Smaller numbers are more zoomed in.
    background_color : Sets the background color of the 3d mode. Defaults to black.


https://github.com/google/neuroglancer/issues/365

control+mousedown0
control+mousedown1
control+mousedown2

control+mousedown0 is being treated as control+mousedown1, bringing up the selection pane instead of adding an
annotation. I suspect Firefox is doing some "helpful" remapping of the mouse event when control is held.


Try: control+mousedown1

with viewer.config_state.txn() as s:
    s.input_event_bindings.data_view["shift+mousedown0"] = "start-fill"
    s.input_event_bindings.data_view["keyt"] = "stop-fill"

https://github.com/shwetagopaul92/neuroglancer/tree/master/examples/dependent-project

'''

import os
import sys
import abc
import copy
import math
import inspect
import logging
import datetime
import argparse
import time
from math import floor
import numpy as np
import numcodecs
import zarr
import neuroglancer as ng
from functools import cache
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, Slot, QUrl, QTimer
from src.helpers import getOpt, getData, setData, print_exception, is_joel
import src.config as cfg


import argparse
import asyncio
import atexit
import concurrent
import shutil
import tempfile
import threading
import neuroglancer.write_annotations

import tensorstore as ts
context = ts.Context({'cache_pool': {'total_bytes_limit': 1000000000}})


ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['EMViewer', 'PMViewer', 'MAViewer']

logger = logging.getLogger(__name__)
if not is_joel():
    logger.propagate = False
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

class WorkerSignals(QObject):
    arrowLeft = Signal()
    arrowRight = Signal()
    arrowUp = Signal()
    arrowDown = Signal()

    result = Signal(str)
    stateChanged = Signal()
    layoutChanged = Signal()
    # zposChanged = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()

    '''MAviewer'''
    zVoxelCoordChanged = Signal(int)
    ptsChanged = Signal()
    swimAction = Signal()
    badStateChange = Signal()
    toggleView = Signal()
    tellMainwindow = Signal(str)
    warnMainwindow = Signal(str)
    errMainwindow = Signal(str)


class AbstractEMViewer(neuroglancer.Viewer):

    # @abc.abstractmethod
    def __init__(self, parent, webengine, path, dm, res, **kwargs):
        super().__init__(**kwargs)
        logger.critical(f"\nCalling AbstractEMViewer __init__ ...\n")
        self.type = 'AbstractEMViewer'
        self.created = datetime.datetime.now()
        self.parent = parent
        self.path = path
        self.dm = dm
        self.res = res
        self.tensor = None
        self.webengine = webengine
        self.webengine.setMouseTracking(True)
        self.signals = WorkerSignals()
        self._cs_scale = None
        self.colors = cfg.glob_colors
        self._blockStateChanged = False
        actions = [('keyLeft', self._keyLeft),
                   ('keyRight', self._keyRight),
                   ('keyUp', self._keyUp),
                   ('keyDown', self._keyDown),
                   ('key1', self._key1),  #abstract
                   ('key2', self._key2),  #abstract
                   ('key3', self._key3),  #abstract
                   ('keySpace', self._keySpace),
                   ('ctlMousedown', self._ctlMousedown)
                   ]
        for a in actions:
            self.actions.add(*a)

        with self.config_state.txn() as s:
            '''DO work: enter, mousedown0, keys, digit1'''
            '''do NOT work: control+mousedown0, control+click0, at:control+mousedown0'''
            s.input_event_bindings.viewer['arrowleft'] = 'keyLeft'
            s.input_event_bindings.viewer['arrowright'] = 'keyRight'
            s.input_event_bindings.viewer['arrowup'] = 'keyUp'
            s.input_event_bindings.viewer['arrowdown'] = 'keyDown'
            s.input_event_bindings.viewer['digit1'] = 'key1'
            s.input_event_bindings.viewer['digit2'] = 'key2'
            s.input_event_bindings.viewer['digit3'] = 'key3'
            s.input_event_bindings.viewer['space'] = 'keySpace'
            s.input_event_bindings.viewer['space'] = 'ctlMousedown'
            # s.input_event_bindings.slice_view['space'] = 'keySpace'
            s.show_ui_controls = False
            s.show_ui_controls = False
            s.show_panel_borders = False
            s.show_layer_panel = False
            s.show_help_button = True

        with self.txn() as s:
            # s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.concurrent_downloads = 1024 ** 2

        self.setBackground()
        self.webengine.setFocus()


    def __del__(self):
        try:
            clr = inspect.stack()[1].function
            logger.warning(f'{self.type} deleted by {clr} ({self.created})')
        except:
            logger.warning(f"{self.type} deleted, caller unknown ({self.created})")

    @staticmethod
    @cache
    def _convert_layout(type):
        d = {
            'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d',
            'yz-3d': 'xy-3d', 'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'
        }
        return d[type]


    @abc.abstractmethod
    def initViewer(self):
        raise NotImplementedError

    @abc.abstractmethod
    def set_layer(self, z=None):
        self._blockStateChanged = True
        if z == None:
            z = self.dm.zpos
        with self.txn() as s:
            vc = s.voxel_coordinates
            try:
                vc[0] = z + 0.5
            except TypeError:
                pass
        self._blockStateChanged = False

    @abc.abstractmethod
    def on_state_changed(self):
        raise NotImplementedError

    def _keyLeft(self, s):
        self.signals.arrowLeft.emit()

    def _keyRight(self, s):
        self.signals.arrowRight.emit()

    def _keyUp(self, s):
        self.signals.arrowUp.emit()

    def _keyDown(self, s):
        self.signals.arrowDown.emit()

    @abc.abstractmethod
    def _key1(self, s):
        raise NotImplementedError

    @abc.abstractmethod
    def _key2(self, s):
        raise NotImplementedError

    @abc.abstractmethod
    def _key3(self, s):
        raise NotImplementedError


    def getCoordinateSpace(self):
        return ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=self.res,
        )

    def getLocalVolume(self, data, coordinatespace):
        """
            data – Source data.
            volume_type – 'image'/'segmentation', or, guessed from data type.
            mesh_options – A dict with the following keys specifying options
                for mesh simplification for 'segmentation' volumes:
            downsampling – '3d' to use isotropic downsampling, '2d' to
                downsample separately in XY, XZ, and YZ; or, None.
            max_downsampling (default=64) – Maximum amount by which on-the-fly
                downsampling may reduce the volume of a chunk. Ex. 4x4x4
                downsampling reduces the volume by 64
            max_downsampled_size (default=128)
        """
        lv = ng.LocalVolume(
            volume_type='image',
            data=data,
            voxel_offset=[0, 0, 0],
            dimensions=coordinatespace,
            downsampling='3d',
            max_downsampling=cfg.max_downsampling,
            max_downsampled_size=cfg.max_downsampled_size,
        )

        return lv

    # async def get_zarr_tensor(path):
    def getTensor(self, path):
        #Todo can this be made async?
        '''**All TensorStore indexing operations produce lazy views**
        https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

        :param path: Fully qualified Zarr path
        :return: A TensorStore future object
        :rtype: tensorstore.Future
        '''
        if not os.path.exists(path):
            logger.warning(f"Path Not Found: {path}")
            return None
        logger.info(f'Requested: {path}')
        total_bytes_limit = 256_000_000_000  # Lonestar6: 256 GB (3200 MT/level) DDR4
        future = ts.open({
            'dtype': 'uint8',
            'driver': 'zarr',
            'kvstore': {
                'driver': 'file',
                'path': path
            },
            'context': {
                'cache_pool': {'total_bytes_limit': total_bytes_limit},
                'file_io_concurrency': {'limit': 1024},  # 1027+
                # 'data_copy_concurrency': {'limit': 512},
            },
            # 'recheck_cached_data': 'open',
            'recheck_cached_data': True,  # default=True
        })
        return future

    def url(self):
        return self.get_viewer_url()

    def position(self):
        return copy.deepcopy(self.state.position)

    def set_position(self, val):
        with self.txn() as s:
            s.position = val

    def moveUpBy(self, val):
        pos = self.position()
        pos[1] = pos[1] - val
        with self.txn() as s:
            s.position = pos

    def moveDownBy(self, val):
        pos = self.position()
        pos[1] = pos[1] + val
        with self.txn() as s:
            s.position = pos

    def moveLeftBy(self, val):
        pos = self.position()
        pos[2] = pos[2] + val
        with self.txn() as s:
            s.position = pos

    def moveRightBy(self, val):
        pos = self.position()
        pos[2] = pos[2] - val
        with self.txn() as s:
            s.position = pos

    def setHelpMenu(self, b):
        logger.info(f"b = {b}")
        state = copy.deepcopy(self.state)
        state.help_panel.visible = bool(b)
        self.set_state(state)

    def _keySpace(self, s):
        logger.info("Native spacebar keybinding intercepted!")
        # if self.dm.method() == 'manual':
        self.signals.toggleView.emit()
        self.webengine.setFocus()

    def _ctlMousedown(self, s):
        logger.info("Native control+mousedown keybinding intercepted!")
        # if self.dm.method() == 'manual':
        self.webengine.setFocus()

    def _ctlClick(self, s):
        logger.info("Native control+click keybinding intercepted!")
        self.webengine.setFocus()

    def zoom(self):
        return copy.deepcopy(self.state.crossSectionScale)

    def set_zoom(self, val):
        caller = inspect.stack()[1].function
        logger.info(f'Setting zoom to {caller}')
        self._blockStateChanged = True
        with self.txn() as s:
            s.crossSectionScale = val
        self._blockStateChanged = False

    def set_brightness(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val:
                layer.shaderControls['brightness'] = val
            else:
                layer.shaderControls['brightness'] = self.dm.brightness
        self.set_state(state)

    def set_contrast(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val:
                layer.shaderControls['contrast'] = val
            else:
                layer.shaderControls['contrast'] = self.dm.contrast
        self.set_state(state)

    def updateDisplayExtras(self):
        with self.txn() as s:
            s.show_default_annotations = self.dm['state']['neuroglancer']['show_bounds']
            s.show_axis_lines = self.dm['state']['neuroglancer']['show_axes']
            s.show_scale_bar = self.dm['state']['neuroglancer']['show_scalebar']

        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,neuroglancer,show_controls')


    def setBackground(self):
        with self.txn() as s:
            if getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'):
                s.crossSectionBackgroundColor = getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')
            else:
                if getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'):
                    s.crossSectionBackgroundColor = '#000000'
                else:
                    s.crossSectionBackgroundColor = '#808080'

    def setUrl(self):
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        self.webengine.setFocus()


    def clear_layers(self):
        if self.state.layers:
            logger.debug('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)

    def getFrameScale(self, w, h):
        assert hasattr(self, 'tensor')
        _, tensor_y, tensor_x = self.tensor.shape
        _, res_y, res_x = self.res  # nm per imagepixel
        scale_h = ((res_y * tensor_y) / h) * 1e-9  # nm/pixel
        scale_w = ((res_x * tensor_x) / w) * 1e-9  # nm/pixel
        cs_scale = max(scale_h, scale_w)
        return cs_scale


    def initZoom(self, w, h, adjust=1.10):
        logger.info('')
        if self.tensor:
            if self._cs_scale:
                logger.info(f'w={w}, h={h}, cs_scale={self._cs_scale}')
                with self.txn() as s:
                    s.cross_section_scale = self._cs_scale
            else:
                self._cs_scale = self.getFrameScale(w=w, h=h)
                adjusted = self._cs_scale * adjust
                with self.txn() as s:
                    s.cross_section_scale = adjusted
            self.signals.zoomChanged.emit(self._cs_scale * 250000000)
        else:
            logger.warning("Cant set zoom now, no tensor store")


    def post_message(self, msg):
        with self.config_state.txn() as cs:
            cs.status_messages['message'] = msg


class EMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        logger.info(f"\nCalling EMViewer __init__ ...\n")
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.type = 'EMViewer'
        self.initViewer()
        # asyncio.ensure_future(self.initViewer())
        # self.post_message(f"Voxel Coordinates: {str(self.state.voxel_coordinates)}")

    def on_state_changed(self):

        if not self._blockStateChanged:

            _css = self.state.cross_section_scale
            if not isinstance(_css, type(None)):
                val = (_css, _css * 250000000)[_css < .001]
                if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                    if getData('state,neuroglancer,zoom') != val:
                        logger.info(f'emitting zoomChanged! [{val:.4f}]')
                        setData('state,neuroglancer,zoom', val)
                        self.signals.zoomChanged.emit(val)

            if isinstance(self.state.position, np.ndarray):
                requested = int(self.state.position[0])
                if requested != self.dm.zpos:
                    self.dm.zpos = requested

            if self.state.layout.type != self._convert_layout(getData('state,neuroglancer,layout')):
                self.signals.layoutChanged.emit()

    # async def initViewer(self, nglayout=None):
    def initViewer(self):
        caller = inspect.stack()[1].function
        self._blockStateChanged = False

        if not os.path.exists(os.path.join(self.path,'.zarray')):
            cfg.main_window.warn('Zarr (.zarray) Not Found: %s' % self.path)
            return

        if os.path.exists(os.path.join(self.path, '.zarray')):
            self.tensor = cfg.tensor = self.getTensor(self.path).result()
            cfg.LV = self.getLocalVolume(self.tensor[:,:,:], self.getCoordinateSpace())

        with self.txn() as s:
            s.layout.type = self._convert_layout(getData('state,neuroglancer,layout'))
            s.show_scale_bar = getData('state,neuroglancer,show_scalebar')
            s.show_axis_lines = getData('state,neuroglancer,show_axes')
            s.show_default_annotations = getData('state,neuroglancer,show_bounds')
            s.position=[self.dm.zpos + 0.5, self.tensor.shape[1]/2, self.tensor.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer( source=cfg.LV, shader=self.dm['rendering']['shader'], )

        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,neuroglancer,show_controls')

        self.set_brightness()
        self.set_contrast()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))


class PMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        logger.info(f"\nCalling PMViewer __init__ ...\n")
        self.type = 'PMViewer'
        self.coordspace = ng.CoordinateSpace(
            names=['z', 'y', 'x'], units=['nm', 'nm', 'nm'], scales=[50, 2,2])  # DoThisRight TEMPORARY <---------
        self.initViewer()


    def initViewer(self):

        if os.path.exists(os.path.join(self.path[0], '.zarray')):
            self.tensor = self.getTensor(self.path[0]).result()
            self.LV_l = self.getLocalVolume(self.tensor[:, :, :], self.getCoordinateSpace())

        if os.path.exists(os.path.join(self.path[1],'.zarray')):
            self.tensor_r = self.getTensor(self.path[1]).result()
            self.LV_r = self.getLocalVolume(self.tensor_r[:, :, :], self.getCoordinateSpace())

        with self.txn() as s:
            s.layout.type = 'yz'
            s.show_default_annotations = True
            s.show_axis_lines = True
            s.show_scale_bar = False

            if hasattr(self, 'LV_l'):
                s.layers['source'] = ng.ImageLayer(source=self.LV_l)
            else:
                s.layers['source'] = ng.ImageLayer()

            if hasattr(self,'LV_r'):
                s.layers['transformed'] = ng.ImageLayer(source=self.LV_r)
                s.layout = ng.row_layout([
                    ng.LayerGroupViewer(layout='yz', layers=['source']),
                    ng.LayerGroupViewer(layout='yz', layers=['transformed'],),
                ])
            else:
                s.layout = ng.row_layout([
                    ng.LayerGroupViewer(layout='yz', layers=['source']),
                ])

        with self.config_state.txn() as s:
            s.show_ui_controls = False

        self.webengine.setUrl(QUrl(self.get_viewer_url()))

    def _left(self, s):
        logger.info('')
        with self.txn() as s:
            vc = s.voxel_coordinates
            vc[0] = max(vc[0] - 1, 0)

    def _right(self, s):
        logger.info('')
        with self.txn() as s:
            vc = s.voxel_coordinates
            vc[0] = min(vc[0] + 1, self.tensor.shape[0])

    def on_state_changed(self):
        pass


class MAViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        logger.info(f"\nCalling MAViewer __init__ ...\n")
        self.type = 'MAViewer'
        self.role = 'tra'
        self.index = 0 #None -1026
        self.cs_scale = None
        self.marker_size = 1
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.signals.ptsChanged.connect(self.drawSWIMwindow)
        self.initViewer()

    def z(self):
        return int(self.state.voxel_coordinates[0]) # self.state.position[0]

    def set_layer(self):
        caller = inspect.stack()[1].function
        self._blockStateChanged = True

        if self.role == 'ref':
            self.index = self.dm.get_ref_index()
        else:
            self.index = self.dm.zpos
        logger.info(f"[{caller}] Setting Z-position [{self.index}]")
        with self.txn() as s:
            vc = s.voxel_coordinates
            try:
                vc[0] = self.index + 0.5
            except TypeError:
                pass

        self.drawSWIMwindow() #1111+
        print(f"<< set_layer")
        # self.signals.zVoxelCoordChanged.emit(self.index)
        self._blockStateChanged = False




    def initViewer(self):
        logger.info('')
        self._blockStateChanged = True
        ref = self.dm.get_ref_index()
        self.index = ref if self.role == 'ref' else self.dm.zpos

        try:
            self.store = self.tensor = self.getTensor(self.path).result()
        except Exception as e:
            logger.error('Unable to Load Data Store at %s' % self.path)
            raise e

        self.LV = self.getLocalVolume(self.tensor[:, :, :], self.getCoordinateSpace())

        with self.txn() as s:
            s.layout.type = 'yz'
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.show_default_annotations = False
            _, y, x = self.tensor.shape
            s.voxel_coordinates = [self.index + .5, y / 2, x / 2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=self.dm['rendering']['shader'], )

        w = self.parent.wNg1.width()
        h = self.parent.wNg1.height()
        self.initZoom(w=w, h=h)
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        self.drawSWIMwindow()
        self.webengine.setFocus()
        self._blockStateChanged = False

    def on_state_changed(self):
        print(f'[{self.role}]')
        logger.info(f'[{self.role}]')

        if not self._blockStateChanged:
            logger.info('proceeding...')

            self._blockStateChanged = True

            if self.state.cross_section_scale:
                val = (self.state.cross_section_scale, self.state.cross_section_scale * 250000000)[
                    self.state.cross_section_scale < .001]
                if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                    if getData('state,neuroglancer,zoom') != val:
                        logger.debug(f'emitting zoomChanged! val = {val:.4f}')
                        setData('state,neuroglancer,zoom', val)
                        self.signals.zoomChanged.emit(val)

            if self.role == 'ref':
                if floor(self.state.position[0]) != self.index:
                    logger.warning(f"[{self.role}] Illegal state change")
                    self.signals.badStateChange.emit()  # New
                    return

            elif self.role == 'tra':
                logger.info(f"checking {floor(self.state.position[0])} == {self.index}...")
                if floor(self.state.position[0]) != self.index:
                    logger.info(f"Calling Back...")
                    self.index = floor(self.state.position[0])
                    self.drawSWIMwindow(z=self.index)  # NeedThis #0803
                    # self.dm.zpos = self.index
                    self.signals.zVoxelCoordChanged.emit(self.index)

            self._blockStateChanged = False


    def _key1(self, s):
        logger.info('')
        self.add_matchpoint(s, id=0, ignore_pointer=True)
        self.webengine.setFocus()


    def _key2(self, s):
        logger.info('')
        self.add_matchpoint(s, id=1, ignore_pointer=True)
        self.webengine.setFocus()


    def _key3(self, s):
        logger.info('')
        self.add_matchpoint(s, id=2, ignore_pointer=True)
        self.webengine.setFocus()


    def swim(self, s):
        logger.info('[futures] Emitting SWIM signal...')
        self.signals.swimAction.emit()


    def add_matchpoint(self, s, id, ignore_pointer=False):
        if self.dm.method() == 'manual':
            print('\n\n--> adding region selection -->\n')
            coords = np.array(s.mouse_voxel_coordinates)
            if coords.ndim == 0:
                logger.warning(f'Null coordinates! ({coords})')
                return
            _, y, x = s.mouse_voxel_coordinates
            frac_y = y / self.store.shape[1]
            frac_x = x / self.store.shape[2]
            logger.critical(f"decimal x = {frac_x}, decimal y = {frac_y}")
            self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][
                self.role][id] = (frac_x, frac_y)
            self.signals.ptsChanged.emit()
            self.drawSWIMwindow()


    def drawSWIMwindow(self, z=None):
        caller = inspect.stack()[1].function
        logger.critical(f"\n\n[{caller}] XXX Drawing SWIM windows [{self.index}]...\n")
        if z == None:
            z = self.dm.zpos
        z += 0.5
        # if z == self.dm.first_included(): #1025-
        #     return
        self._blockStateChanged = True
        self.undrawSWIMwindows()
        m = self.marker_size
        level_val = self.dm.lvl()
        method = self.dm.current_method
        annotations = []

        if method == 'grid':
            ww1x1 = tuple(self.dm.size1x1())  # full window width
            ww2x2 = tuple(self.dm.size2x2())  # 2x2 window width
            w, h = self.dm.image_size(s=self.dm.level)
            p = self.getCenterpoints(w, h, ww1x1, ww2x2)
            colors = self.colors[0:sum(self.dm.quadrants)]
            cps = [x for i, x in enumerate(p) if self.dm.quadrants[i]]
            ww_x = ww2x2[0] - (24 // level_val)
            ww_y = ww2x2[1] - (24 // level_val)
            for i, pt in enumerate(cps):
                c = colors[i]
                d1, d2, d3, d4 = self.getRect2(pt, ww_x, ww_y)
                id = 'roi%d' % i
                annotations.extend([
                    ng.LineAnnotation(id=id + '%d0', pointA=(z,) + d1, pointB=(z,) + d2, props=[c, m]),
                    ng.LineAnnotation(id=id + '%d1', pointA=(z,) + d2, pointB=(z,) + d3, props=[c, m]),
                    ng.LineAnnotation(id=id + '%d2', pointA=(z,) + d3, pointB=(z,) + d4, props=[c, m]),
                    ng.LineAnnotation(id=id + '%d3', pointA=(z,) + d4, pointB=(z,) + d1, props=[c, m])])

            cfg.mw.setFocus()

        elif method == 'manual':
            ww_x = ww_y = self.dm.manual_swim_window_px()
            pts = self.dm.ss['method_opts']['points']['coords'][self.role]
            for i, pt in enumerate(pts):
                if pt:
                    x = self.store.shape[2] * pt[0]
                    y = self.store.shape[1] * pt[1]
                    d1, d2, d3, d4 = self.getRect2(coords=(x, y), ww_x=ww_x, ww_y=ww_y, )
                    c = self.colors[i]
                    id = 'roi%d' % i
                    annotations.extend([
                        ng.LineAnnotation(id=id + '%d0', pointA=(z,) + d1, pointB=(z,) + d2, props=[c, m]),
                        ng.LineAnnotation(id=id + '%d1', pointA=(z,) + d2, pointB=(z,) + d3, props=[c, m]),
                        ng.LineAnnotation(id=id + '%d2', pointA=(z,) + d3, pointB=(z,) + d4, props=[c, m]),
                        ng.LineAnnotation(id=id + '%d3', pointA=(z,) + d4, pointB=(z,) + d1, props=[c, m])
                    ])
            self.webengine.setFocus()

        with self.txn() as s:
            s.layers['SWIM'] = ng.LocalAnnotationLayer(
                annotations=annotations,
                dimensions=self.getCoordinateSpace(),
                annotationColor='blue',
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='color', type='rgb', default='#ffff66', ),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=1, )
                ],
                shader='''
                    void main() {
                      setColor(prop_color());
                      setPointMarkerSize(prop_size());
                    }
                ''',
            )

        self._blockStateChanged = False
        self.webengine.setFocus() #1111-
        # cfg.mw.setFocus()
        print('<< drawSWIMwindows')

    def undrawSWIMwindows(self):
        with self.txn() as s:
            if s.layers['SWIM']:
                if 'annotations' in s.layers['SWIM'].to_json().keys():
                    s.layers['SWIM'].annotations = None

    @cache
    def getCenterpoints(self, w, h, ww1x1, ww2x2):
        d_x1 = ((w - ww1x1[0]) / 2) + (ww2x2[0] / 2)
        d_x2 = w - d_x1
        d_y1 = ((h - ww1x1[1]) / 2) + (ww2x2[1] / 2)
        d_y2 = h - d_y1
        p1 = (d_x2, d_y1)
        p2 = (d_x1, d_y1)
        p3 = (d_x2, d_y2)
        p4 = (d_x1, d_y2)
        return p1, p2, p3, p4

    @cache
    def getRect2(self, coords, ww_x, ww_y):
        x, y = coords[0], coords[1]
        hw = int(ww_x / 2)  # Half-width
        hh = int(ww_y / 2)  # Half-height
        A = (y + hh, x - hw)
        B = (y + hh, x + hw)
        C = (y - hh, x + hw)
        D = (y - hh, x - hw)
        return A, B, C, D


# # Not using TensorStore, so point Neuroglancer directly to local Zarr on disk.
# cfg.refLV = cfg.baseLV = f'zarr://http://localhost:{self.port}/{unal_path}'
# if is_aligned_and_generated:  cfg.alLV = f'zarr://http://localhost:{self.port}/{al_path}'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    EMViewer()
    EMViewer.initViewer()