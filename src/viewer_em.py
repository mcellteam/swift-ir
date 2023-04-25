#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server'''

import os
import copy
import math
import inspect
import logging
import datetime
import argparse
import abc
# from abc import ABC, abstractmethod
import time
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, QUrl
from qtpy.QtWidgets import QApplication
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, obj_to_string, print_exception
from src.shaders import ann_shader
import src.config as cfg


ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['EMViewer', 'EMViewerStage', 'EMViewerSnr', 'EMViewerMendenhall']

logger = logging.getLogger(__name__)
# handler = logging.StreamHandler(stream=sys.stdout)
# logger.addHandler(handler)

class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal(int)
    stateChangedAny = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()


class AbstractEMViewer(neuroglancer.Viewer):

    @abc.abstractmethod
    def __init__(self, webengine, name=None, **kwargs):
        super().__init__(**kwargs)
        self.signals = WorkerSignals()
        self.webengine = webengine
        self.name = name
        self.cs_scale = None
        self._crossSectionScale = 1
        self.created = datetime.datetime.now()
        # self._layer = None
        self._layer = cfg.data.zpos
        self.scale = cfg.data.scale
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self._blockZoom = False
        self.type = 'AbstractEMViewer'
        # logger.info('viewer constructed!')
        caller = inspect.stack()[1].function
        self._zmag_set = 0


    def __repr__(self):
        # return copy.deepcopy(self.state)
        return self.type

    def __del__(self):
        try:
            logger.warning('__del__ called on %s by %s (created: %s)'% (self.type, inspect.stack()[1].function, self.created))
        except:
            logger.warning('__del__ called on %s (created: %s)' %(self.type, self.created))

    @abc.abstractmethod
    def initViewer(self):
        pass

    def getCoordinateSpace(self):
        return ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale)),
        )

    def getCoordinateSpacePlanar(self):
        return ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale)),
        )


    # @abc.abstractmethod
    # def on_state_changed(self):
    #     pass

    def diableZoom(self):
        self._blockZoom = True
        logger.info('Zoom disabled.')

    def enableZoom(self):
        self._blockZoom = False
        logger.info('Zoom enabled.')


    def on_state_changed_any(self):
        # logger.critical(f'zpos={cfg.data.zpos}')
        # logger.info(f'on_state_changed_any [{self.type}] >>>>')
        # if self._zmag_set < 10:
        #     self._zmag_set += 1
        # logger.critical(f'on_state_changed_any [{self.type}] [i={self._zmag_set}] >>>>')
        self.signals.stateChangedAny.emit()


    def on_state_changed(self):
        if self._blockZoom:
            return

        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        if calname == '<lambda>':
            return
        # logger.info('caller: %s, calname: %s' % (caller, calname))

        if not self.cs_scale:
            if self.state.cross_section_scale:
                if self.state.cross_section_scale > .0001:
                    logger.info('perfect cs_scale captured! - %.3f' % self.state.cross_section_scale)
                    self.cs_scale = self.state.cross_section_scale

        try:
            # print('requested layer: %s' % str(self.state.position[0]))
            # get_loc = floor(self.state.position[0])
            if isinstance(self.state.position, np.ndarray):
                request_layer = int(self.state.position[0])
                if request_layer == self._layer:
                    logger.debug('[%s] State Changed, But Layer Is The Same - '
                                 'Suppressing The stateChanged Callback Signal' %self.type)
                else:
                    self._layer = request_layer
                    logger.info(f'[{self.type}] (!) emitting get_loc: {request_layer} [cur_method={self.type}]')
                    self.signals.stateChanged.emit(request_layer)

            zoom = self.state.cross_section_scale
            if zoom:
                if zoom != self._crossSectionScale:
                    logger.info(f'[{self.type}] (!) emitting zoomChanged (state.cross_section_scale): {zoom:.3f}...')
                    self.signals.zoomChanged.emit(zoom)
                self._crossSectionScale = zoom
        except:
            print_exception()
            logger.error(f'[{self.type}] ERROR on_state_change')


    def url(self):
        return self.get_viewer_url()

    def get_loc(self):
        return math.floor(self.state.position[0])

    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()

    def updateHighContrastMode(self):
        with self.txn() as s:
            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'

    def position(self):
        return copy.deepcopy(self.state.position)
        # return self.state.position

    def set_position(self, val):
        if self.type != 'EMViewerStage':  # Critical!
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


    def zoom(self):
        return copy.deepcopy(self.state.crossSectionScale)
        # return self.state.crossSectionScale

    def set_zoom(self, val):
        if self.type != 'EMViewerStage':  # Critical!
            self._blockZoom = True
            with self.txn() as s:
                s.crossSectionScale = val
            self._blockZoom = False

    def set_layer(self, index):
        if self.type != 'EMViewerStage': #Critical!
            state = copy.deepcopy(self.state)
            state.position[0] = index
            self.set_state(state)

    def set_brightness(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val:
                layer.shaderControls['brightness'] = val
            else:
                layer.shaderControls['brightness'] = cfg.data.brightness
            # layer.volumeRendering = True
        self.set_state(state)

    def set_contrast(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val:
                layer.shaderControls['contrast'] = val
            else:
                layer.shaderControls['contrast'] = cfg.data.contrast
            #layer.volumeRendering = True
        self.set_state(state)

    def _set_zmag(self):
        if self._zmag_set < 8:
            self._zmag_set += 1
            # logger.info(f'zpos={cfg.data.zpos} Setting Z-mag on {self.type}')
            try:
                # logger.critical(f'Setting Z-mag on {self.type}')
                with self.txn() as s:
                    s.relativeDisplayScales = {"z": 10}
            except:
                print_exception()

    def set_zmag(self, val=10):
        # logger.info(f'zpos={cfg.data.zpos} Setting Z-mag on {self.type}')
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            state = copy.deepcopy(self.state)
            state.relativeDisplayScales = {'z': val}
            self.set_state(state)
        except:
            logger.warning('Unable to set Z-mag')
            print_exception()
        else:
            logger.info('Successfully set Z-mag!')


    def updateScaleBar(self):
        with self.txn() as s:
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')

    def updateAxisLines(self):
        with self.txn() as s:
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')


    def updateDefaultAnnotations(self):
        with self.txn() as s:
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')


    def updateUIControls(self):
        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')


    # def set_zmag(self):
    #     if cfg.MP_MODE:
    #         with self.txn() as s:
    #             s.relativeDisplayScales = {"z": 10} # this should work, but does not work. ng bug.

    def clear_layers(self):
        if self.state.layers:
            logger.info('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)

    def initZoom(self, w, h, adjust=1.10):
        # logger.info(f'w={w}, h={h}')
        # self._blockZoom = True

        if self.cs_scale:
            logger.info(f'w={w}, h={h}, cs_scale={self.cs_scale}')
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:
            logger.info(f'w={w}, h={h}')
            cs_scale = self.get_zoom(w=w, h=h)
            # self.cs_scale = cs_scale
            with self.txn() as s:
                s.crossSectionScale = cs_scale * adjust


    def get_zoom(self, w, h):
        _, tensor_y, tensor_x = cfg.tensor.shape
        res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale)  # nm per imagepixel
        scale_h = ((res_y * tensor_y) / h) * 1e-9  # nm/pixel
        scale_w = ((res_x * tensor_x) / w) * 1e-9  # nm/pixel
        cs_scale = max(scale_h, scale_w)
        return cs_scale

        # self._blockZoom = False


    def get_tensors(self):
        del cfg.tensor
        del cfg.unal_tensor
        del cfg.al_tensor
        sf = cfg.data.scale_val(s=cfg.data.scale)
        al_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
        unal_path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        cfg.tensor = cfg.unal_tensor = cfg.al_tensor = None
        try:
            cfg.unal_tensor = get_zarr_tensor(unal_path).result()
            if cfg.data.is_aligned_and_generated():
                cfg.al_tensor = get_zarr_tensor(al_path).result()
            cfg.tensor = (cfg.unal_tensor, cfg.al_tensor)[cfg.data.is_aligned_and_generated()]
        except Exception as e:
            logger.warning('Failed to acquire Tensorstore view')
            raise e

    def post_message(self, msg):
        with self.config_state.txn() as cs:
            cs.status_messages['message'] = msg


# class EMViewer(neuroglancer.Viewer):
class EMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.shared_state.add_changed_callback(self.on_state_changed) #Critical for Corr Sig thumbs to update properly
        # self.shared_state.add_changed_callback(self.on_state_changed_any)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))

        self.type = 'EMViewer'
        self.initViewer()

    def initViewer(self):
        caller = inspect.stack()[1].function
        logger.info(f'\nInitializing [{self.type}] [caller: {caller}]...\n')

        caller = inspect.stack()[1].function
        if getData('state,mode') in ('stack-4panel', 'stack-xy'):
            # cfg.data['ui']['ng_layout'] = '4panel'
            self.initViewerSlim()
        elif cfg.data['state']['mode'] == 'comparison':
            # cfg.data['ui']['ng_layout'] = 'xy'
            self.initViewerSbs()

    def initViewerSbs(self):
        # caller = inspect.stack()[1].function
        # logger.critical(f'Initializing EMViewer (caller: {caller})....')

        requested = getData('state,ng_layout')
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
          'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        nglayout = mapping[requested]

        self.coordinate_space = self.getCoordinateSpace()
        self.get_tensors()

        x_nudge, y_nudge = 0, 0
        if cfg.data.is_aligned_and_generated():
            _, tensor_y, tensor_x = cfg.al_tensor.shape
            x_nudge, y_nudge = (tensor_x - cfg.unal_tensor.shape[2]) / 2, (tensor_y - cfg.unal_tensor.shape[1]) / 2

        cfg.refLV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[0:len(cfg.data) - 1, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[1, y_nudge, x_nudge]
        )
        cfg.baseLV = cfg.LV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, y_nudge, x_nudge],
        )
        if cfg.data.is_aligned_and_generated():
            cfg.alLV = cfg.LV = ng.LocalVolume(
                volume_type='image',
                data=cfg.al_tensor[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, ] * 3,
            )

        is_aligned = cfg.data.is_aligned_and_generated()
        _, tensor_y, tensor_x = cfg.tensor.shape

        # w = cfg.project_tab.webengine.width() / ((2, 3)[cfg.data.is_aligned_and_generated()])
        # h = cfg.project_tab.webengine.height()
        # self.initZoom(w=w, h=h, adjust=1.10)

        sf = cfg.data.scale_val(s=cfg.data.scale)
        self.ref_l, self.base_l, self.aligned_l = 'ref_%d' % sf, 'base_%d' % sf, 'aligned_%d' % sf

        self.grps = []
        self.grps.append(ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout))
        self.grps.append(ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout))
        if is_aligned:
            self.grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout))

        # box = ng.AxisAlignedBoundingBoxAnnotation(
        #     point_a=[5, 50, 50],
        #     point_b=[5, 500, 500],
        #     id="bounding-box",
        # )

        with self.txn() as s:
            '''other settings: 
            s.displayDimensions = ["z", "y", "x"]
            s.perspective_orientation
            s.concurrent_downloads = 512'''
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.layout = ng.row_layout(self.grps)
            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            s.layers[self.ref_l] = ng.ImageLayer(source=cfg.refLV, shader=cfg.data['rendering']['shader'], )
            s.layers[self.base_l] = ng.ImageLayer(source=cfg.baseLV, shader=cfg.data['rendering']['shader'],)
            if is_aligned:
                s.layers[self.aligned_l] = ng.ImageLayer(source=cfg.alLV, shader=cfg.data['rendering']['shader'],)
            # s.showSlices=False
            s.position = [cfg.data.zpos, tensor_y / 2, tensor_x / 2]

            # s.layers["bounding-box"] = ng.AnnotationLayer(annotations=[box], ) #0316

        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.scale_bar_options.scale_factor = 1
            s.show_panel_borders = False

        self._crossSectionScale = self.state.cross_section_scale
        self.initial_cs_scale = self.state.cross_section_scale

        self.set_brightness()
        self.set_contrast()
        # self.set_zmag()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))


        # w = cfg.project_tab.w_ng_display.width() / ((2, 3)[cfg.data.is_aligned_and_generated()])
        #Critical must use main_window width
        w = cfg.main_window.width() / ((2, 3)[cfg.data.is_aligned_and_generated()])
        h = cfg.project_tab.w_ng_display.height()
        self.initZoom(w=w, h=h, adjust=1.10)

        # self.set_zmag()


    def initViewerSlim(self, nglayout=None):
        # t0 = time.time()
        # caller = inspect.stack()[1].function
        # logger.critical(f'Initializing EMViewer Slim (caller: {caller})....')

        if not nglayout:
            requested = getData('state,ng_layout')
            mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
            nglayout = mapping[requested]


        zd = ('img_src.zarr', 'img_aligned.zarr')[cfg.data.is_aligned_and_generated()]
        path = os.path.join(cfg.data.dest(), zd, 's' + str(cfg.data.scale_val()))
        if not os.path.exists(path):
            cfg.main_window.warn('Zarr Not Found: %s' % path)
            return

        self.store = cfg.tensor = get_zarr_tensor(path).result()

        self.coordinate_space = self.getCoordinateSpace()

        self.LV = cfg.LV = cfg.LV = ng.LocalVolume(
            volume_type='image',
            data=self.store[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, ] * 3,
        )

        if getData('state,ng_layout') == 'xy':
            # logger.info('Initializing zoom for xy plane ...')
            w = cfg.main_window.width()
            h = cfg.project_tab.webengine.height()
            self.initZoom(w=w, h=h, adjust=1.10)


        with self.txn() as s:
            s.layout.type = nglayout
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.position=[cfg.data.zpos, self.store.shape[1]/2, self.store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer( source=self.LV, shader=cfg.data['rendering']['shader'], )
            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')


        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = False
            # s.viewer_size = [100,100]

        self._layer = self.get_loc()
        # self.shared_state.add_changed_callback(self.on_state_changed) #0215+ why was this OFF?
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        self.set_brightness()
        self.set_contrast()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))


class EMViewerStage(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.type = 'EMViewerStage'
        # self.shared_state.add_changed_callback(self.on_state_changed_any)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        self.initViewer()


    def initViewer(self):
        caller = inspect.stack()[1].function
        logger.info(f'\n\nInitializing [{self.type}] [caller: {caller}]...\n')

        self.coordinate_space = self.getCoordinateSpace()

        self.index = cfg.data.zpos
        dir_staged = os.path.join(cfg.data.dest(), self.scale, 'zarr_staged', str(self.index), 'staged')
        # self.store = cfg.tensor = cfg.al_tensor = get_zarr_tensor(dir_staged).result()
        self.store = cfg.stageViewer = get_zarr_tensor(dir_staged).result()
        self.LV = ng.LocalVolume(
            volume_type='image',
            data=self.store,
            # data=self.store[self.index:self.index+1, :, :],
            # dimensions=self.coordinate_space,
            # dimensions=[1,1,1],
            dimensions=self.getCoordinateSpacePlanar(),
            voxel_offset=[0, 0, 0]
        )
        # _, tensor_y, tensor_x = cfg.tensor.shape
        _, tensor_y, tensor_x = self.store.shape

        logger.info(f'Tensor Shape: {self.store.shape}')

        sf = cfg.data.scale_val(s=cfg.data.scale)
        self.ref_l, self.base_l, self.aligned_l = 'ref_%d' % sf, 'base_%d' % sf, 'aligned_%d' % sf
        with self.txn() as s:
            '''other settings: 
            s.displayDimensions = ["z", "y", "x"]
            s.perspective_orientation
            s.concurrent_downloads = 512'''
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.layout = ng.row_layout([ng.LayerGroupViewer(layers=[self.aligned_l], layout='yz')])
            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'
            # s.show_scale_bar = True
            s.show_scale_bar = False
            s.show_axis_lines = False
            s.show_default_annotations = getData('state,stage_viewer,show_yellow_frame')
            s.layers[self.aligned_l] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            # s.showSlices=False
            s.position = [0, tensor_y / 2, tensor_x / 2]
            # s.relativeDisplayScales = {"z": 50, "y": 2, "x": 2}

        with self.config_state.txn() as s:
            s.show_ui_controls = False
            s.show_panel_borders = False

        self._crossSectionScale = self.state.cross_section_scale
        self.initial_cs_scale = self.state.cross_section_scale

        self.set_brightness()
        self.set_contrast()
        # self.set_zmag()
        # self.set_zmag()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        w = cfg.project_tab.MA_webengine_stage.geometry().width()
        h = cfg.project_tab.MA_webengine_stage.geometry().height()
        self.initZoom(w=w, h=h, adjust=1.02)

        # logger.info('\n\n' + self.url() + '\n')





class EMViewerSnr(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        # self.shared_state.add_changed_callback(self.on_state_changed)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        self.type = 'EMViewerSnr'
        self.initViewer()


    def initViewer(self):
        caller = inspect.stack()[1].function
        logger.info(f'Initializing [{self.type}] [caller: {caller}]...')

        self.coordinate_space = self.getCoordinateSpace()
        self.get_tensors()

        cfg.refLV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[0:len(cfg.data) - 1, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[1, 0, 0]
        )
        cfg.baseLV = cfg.LV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, 0, 0],
        )
        if cfg.data.is_aligned_and_generated():
            cfg.alLV = cfg.LV = ng.LocalVolume(
                volume_type='image',
                data=cfg.al_tensor[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, ] * 3,
            )

        _, tensor_y, tensor_x = cfg.tensor.shape
        # h = cfg.project_tab.snrPlotSplitter.geometry().height() / 3
        # w = cfg.project_tab.snrPlotSplitter.sizes()[1]
        # self.initZoom(h=h, w=w, adjust=1.20)
        sf = cfg.data.scale_val(s=cfg.data.scale)
        self.ref_l, self.base_l, self.aligned_l = 'ref_%d' % sf, 'base_%d' % sf, 'aligned_%d' % sf

        with self.txn() as s:
            '''other settings: 
            s.displayDimensions = ["z", "y", "x"]
            s.perspective_orientation
            s.concurrent_downloads = 512'''
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            # s.displayDimensions = ["z", "y"]

            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'
            s.show_scale_bar = False
            s.show_default_annotations = True
            s.show_axis_lines = True

            self.grps = []
            self.grps.append(ng.LayerGroupViewer(layers=[self.ref_l], layout='yz'))
            self.grps.append(ng.LayerGroupViewer(layers=[self.base_l], layout='yz'))
            s.layers[self.ref_l] = ng.ImageLayer(source=cfg.refLV, shader=cfg.data['rendering']['shader'], )
            s.layers[self.base_l] = ng.ImageLayer(source=cfg.baseLV, shader=cfg.data['rendering']['shader'], )
            if cfg.data.is_aligned_and_generated():
                self.grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout='yz'))
                s.layers[self.aligned_l] = ng.ImageLayer(source=cfg.alLV, shader=cfg.data['rendering']['shader'], )

            s.layout = ng.column_layout(self.grps)  # col
            # s.showSlices = False
            s.position = [cfg.data.zpos, tensor_y / 2, tensor_x / 2]

            # s.relativeDisplayScales = {"z": 10}

        with self.config_state.txn() as s:
            s.show_ui_controls = False
            # s.show_panel_borders = False
            s.show_panel_borders = False

        self._layer = math.floor(self.state.position[0])
        self._crossSectionScale = self.state.cross_section_scale
        self.initial_cs_scale = self.state.cross_section_scale

        self.set_brightness()
        self.set_contrast()
        # self.set_zmag()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))

        h = cfg.project_tab.snrPlotSplitter.geometry().height() / 3
        w = cfg.project_tab.snrPlotSplitter.sizes()[1]
        self.initZoom(h=h, w=w, adjust=1.20)

        # self.set_zmag()


class EMViewerMendenhall(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        # self.shared_state.add_changed_callback(self.on_state_changed)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        self.type = 'EMViewerMendenhall'

    def initViewer(self):
        logger.critical('Initializing Neuroglancer - Mendenhall...')
        path = os.path.join(cfg.data.dest(), 'mendenhall.zarr', 'grp')
        scales = [50, 2, 2]
        coordinate_space = ng.CoordinateSpace(names=['z', 'y', 'x'], units=['nm', 'nm', 'nm'], scales=scales, )
        cfg.men_tensor = get_zarr_tensor(path).result()
        self.json_unal_dataset = cfg.men_tensor.spec().to_json()
        logger.debug(self.json_unal_dataset)
        logger.info('Instantiating Viewer...')
        image_size = cfg.data.image_size()
        widget_size = cfg.main_window.globTabs.size()

        widget_height = widget_size[3]
        tissue_h = 2 * image_size[1]  # nm
        scale_h = (tissue_h / widget_height) * 1e-9  # nm/pixel
        tissue_w = 2 * image_size[0]  # nm
        scale_w = (tissue_w / image_size[0]) * 1e-9  # nm/pixel
        cross_section_scale = max(scale_h, scale_w)

        with self.txn() as s:
            s.layers['layer'] = ng.ImageLayer(source=cfg.menLV)
            s.crossSectionBackgroundColor = '#808080'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1

        self.webengine.setUrl(QUrl(self.get_viewer_url()))





        # dt = time.time() - t0
        # # logger.critical('Loading Time: %.4f' %dt)


    # def set_rds(self):
    #     with self.txn() as s:
    #         s.relative_display_scales = {'z': 14}





    # def set_row_layout(self, nglayout):
    #
    #     with self.txn() as s:
    #         if cfg.data.is_aligned_and_generated():
    #             if getData('state,MANUAL_MODE'):
    #                 s.layout = ng.row_layout([
    #                     ng.column_layout([
    #                         ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout),
    #                     ]),
    #                 ])
    #             else:
    #                 s.layout = ng.row_layout([
    #                     ng.column_layout([
    #                         ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout),
    #                         ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout),
    #                     ]),
    #                     ng.column_layout([
    #                         ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout),
    #                     ]),
    #                 ])
    #         else:
    #             s.layout = ng.row_layout(self.grps)

    # def set_vertical_layout(self, nglayout):
    #     with self.txn() as s:
    #         if cfg.data.is_aligned_and_generated():
    #             if getData('state,MANUAL_MODE'):
    #                 ng.column_layout([
    #                     ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout),
    #                     ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout),
    #                     ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout),
    #                 ]),
    #             else:
    #                 ng.column_layout([
    #                     ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout),
    #                     ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout),
    #                 ]),
    #         else:
    #             s.layout = ng.row_layout(self.grps)




    # def _set_zmag(self):
    #     with self.txn() as s:
    #         s.relativeDisplayScales = {"z": 10}


# # Not using TensorStore, so point Neuroglancer directly to local Zarr on disk.
# cfg.refLV = cfg.baseLV = f'zarr://http://localhost:{self.port}/{unal_path}'
# if is_aligned_and_generated:  cfg.alLV = f'zarr://http://localhost:{self.port}/{al_path}'


'''
ViewerState({
    "dimensions": {
        "z": [5e-08, "m"],
        "y": [8e-09, "m"],
        "x": [8e-09, "m"]
    },
    "position": [0.5167545080184937, 264, 679.9994506835938],
    "crossSectionScale": 1,
    "projectionScale": 1024,
    "layers": [{
        "cur_method": "annotation",
        "source": {
            "url": "local://annotations",
            "transform": {
                "outputDimensions": {
                    "z": [5e-08, "m"],
                    "y": [8e-09, "m"],
                    "x": [8e-09, "m"]
                }
            }
        },
        "tab": "source",
        "annotations": [{
            "point": [0.5, 369, 597.4999389648438],
            "cur_method": "point",
            "id": "(0.5, 369.0, 597.49994)",
            "props": ["#f3e375", 3, 8]
        }, {
            "point": [0.5, 449, 379.4999694824219],
            "cur_method": "point",
            "id": "(0.5, 449.0, 379.49997)",
            "props": ["#5c4ccc", 3, 8]
        }],
        "annotationProperties": [{
            "id": "ptColor",
            "cur_method": "rgb",
            "default": "#ffffff"
        }, {
            "id": "ptWidth",
            "cur_method": "float32",
            "default": 3
        }, {
            "id": "size",
            "cur_method": "float32",
            "default": 8
        }],
        "shader": "void main() { setPointMarkerBorderColor(prop_ptColor()); \nsetPointMarkerBorderWidth(prop_ptWidth()); \nsetPointMarkerSize(prop_size());}\n",
        "name": "ann"
    }, {
        "cur_method": "image",
        "source": "python://volume/cef5a1ec1ac2735310e4b0eac0f6c086399351cf.bc644314f0d66472a635e053ba4a78252a6a4262",
        "tab": "source",
        "shader": "\n        #uicontrol vec3 color color(default=\"white\")\n        #uicontrol float brightness slider(min=-1, max=1, step=0.01)\n        #uicontrol float contrast slider(min=-1, max=1, step=0.01)\n        void main() { emitRGB(color * (toNormalized(getDataValue()) + brightness) * exp(contrast));}\n        ",
        "name": "layer"
    }],
    "crossSectionBackgroundColor": "#808080",
    "layout": "yz"
})

'''

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    EMViewer()
    EMViewer.initViewerSlim()
