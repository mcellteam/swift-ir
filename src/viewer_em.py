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
import time
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, Slot, QUrl, QTimer
from qtpy.QtWidgets import QApplication, QSizePolicy
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, obj_to_string, print_exception, is_joel, is_tacc, caller_name, \
    example_zarr
from src.shaders import ann_shader
import src.config as cfg


import argparse
import asyncio
import atexit
import concurrent
import shutil
import tempfile
import threading
import neuroglancer.write_annotations
import numpy as np


ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['EMViewer', 'PMViewer', 'EMViewerMendenhall']

logger = logging.getLogger(__name__)
# handler = logging.StreamHandler(stream=sys.stdout)
# logger.addHandler(handler)

DEV = is_joel()

class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    layoutChanged = Signal()
    # zposChanged = Signal()
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
        self.created = datetime.datetime.now()
        # self._layer = None
        try:
            self._layer = cfg.data.zpos
        except:
            logger.warning("setting layer to 0")
            self._layer = 0
        # self.scale = cfg.data.scale_key
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.type = 'AbstractEMViewer'
        self._zmag_set = 0
        self._blinkState = 0
        self._blockStateChanged = False
        self.rev_mapping = {'yz': 'xy', 'xy': 'yz', 'xz': 'xz', 'yz-3d': 'xy-3d', 'xy-3d': 'yz-3d',
                       'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}


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
            scales=list(cfg.data.resolution(s=cfg.data.scale_key)),
        )

    def getCoordinateSpacePlanar(self):
        return ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale_key)),
        )


    # @abc.abstractmethod
    # def on_state_changed(self):
    #     pass


    @Slot()
    def on_state_changed_any(self):
        # zoom bug factor = 250000000s
        # caller = inspect.stack()[1].function
        # logger.info(f"[{caller}]")

        if self._blockStateChanged:
            return

        # if cfg.data.scale_val() > 2:
        #     if self.state.relative_display_scales == None:
        #         self.set_zmag()

        if self.rev_mapping[self.state.layout.type] != getData('state,ng_layout'):
            self.signals.layoutChanged.emit()
            # logger.info(f'Setting layout to: {self.state.layout.type}')
            # setData('state,ng_layout', self.state.layout.type)

        # if self.state.cross_section_scale == None:
        #     self.signals.zoomChanged.emit(1.0)

        if self.state.cross_section_scale:
            val = (self.state.cross_section_scale, self.state.cross_section_scale * 250000000)[self.state.cross_section_scale < .001]
            if round(val, 3) != round(getData('state,ng_zoom'), 3):
                setData('state,ng_zoom', val)
                self.signals.zoomChanged.emit(val)

        # self.post_message(f"Voxel Coordinates: {str(self.state.voxel_coordinates)}")


    @Slot()
    def on_state_changed(self):
        # caller = inspect.stack()[1].function

        if getData('state,blink'):
            return

        if self._blockStateChanged:
            return

        try:
            if isinstance(self.state.position, np.ndarray):
                request_layer = int(self.state.position[0])
                if request_layer != self._layer:
                    # State Changed, But Layer Is The Same. Supress teh callback
                    cfg.data.zpos = request_layer
                    self._layer = request_layer
        except:
            print_exception()


    def url(self):
        return self.get_viewer_url()


    def blink(self):
        logger.info(f'self._blinkState = {self._blinkState}, self._blockStateChanged={self._blockStateChanged}')
        self._blinkState = 1 - self._blinkState
        if self._blinkState:
            self.set_layer(cfg.data.zpos)
        else:
            self.set_layer(cfg.data.zpos - cfg.data.get_ref_index_offset())


    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()

    def updateHighContrastMode(self):
        with self.txn() as s:
            if getData('state,neutral_contrast'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                # s.crossSectionBackgroundColor = '#222222'
                s.crossSectionBackgroundColor = '#000000'

    def position(self):
        return copy.deepcopy(self.state.position)
        # return self.state.position

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



    def zoom(self):
        return copy.deepcopy(self.state.crossSectionScale)
        # return self.state.crossSectionScale

    def set_zoom(self, val):
        if self.type != 'EMViewerStage':  # Critical!
            self._blockStateChanged = True
            with self.txn() as s:
                s.crossSectionScale = val
            self._blockStateChanged = False

    def set_layer(self, index=None):
        # NotCulpableForFlickerGlitch
        self._blockStateChanged = True
        # if DEV:
        #     logger.critical(f'[{caller_name()}] Setting layer:\n'
        #                     f'index arg={index}\n'
        #                     f'voxel coords before={self.state.voxel_coordinates}\n'
        #                     f'...')
        if index == None:
            index = cfg.data.zpos
        try:
            with self.txn() as s:
                vc = s.voxel_coordinates
                vc[0] = index + 0.5
        except:
            print_exception()
        self._blockStateChanged = False



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
        # self._blockStateChanged = True
        # if self._zmag_set < 8:
        #     self._zmag_set += 1
        try:
            with self.txn() as s:
                s.relativeDisplayScales = {"z": 10}
        except:
            print_exception()
        # self._blockStateChanged = False

    def set_zmag(self):
        # logger.info(f'zpos={cfg.data.zpos} Setting Z-mag on {self.type}')
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        self._blockStateChanged = True
        try:
            res = cfg.data.resolution()
            state = copy.deepcopy(self.state)
            # state.relativeDisplayScales = {'z': res[0] * 1e9, 'y': res[1], 'x': res[2]}
            state.relativeDisplayScales = {'z': 2}
            self.set_state(state)
        except:
            logger.warning('Unable to set Z-mag')
            print_exception()
        else:
            if DEV:
                logger.info(f'[{caller}] Successfully set Z-mag!')
        self._blockStateChanged = False


    def updateScaleBar(self):
        with self.txn() as s:
            s.show_scale_bar = cfg.data['state']['show_scalebar']

    def updateAxisLines(self):
        with self.txn() as s:
            s.show_axis_lines = cfg.data['state']['show_bounds']


    def updateDisplayAccessories(self):
        with self.txn() as s:
            s.show_default_annotations = cfg.data['state']['show_bounds']
            s.show_axis_lines = cfg.data['state']['show_axes']
            s.show_scale_bar = cfg.data['state']['show_scalebar']

        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,show_ng_controls')


    def setBackground(self):
        with self.txn() as s:
            if getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'):
                s.crossSectionBackgroundColor = getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')
            else:
                if getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'):
                    # s.crossSectionBackgroundColor = '#222222'
                    s.crossSectionBackgroundColor = '#000000'
                else:
                    s.crossSectionBackgroundColor = '#808080'

    def updateUIControls(self):
        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,show_ng_controls')


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

    # def initZoom(self, w, h, adjust=1.20):
    def initZoom(self, w, h, adjust=1.10):
        #Todo add check for Zarr existence

        # QApplication.processEvents()
        # logger.info(f'w={w}, h={h}')
        # self._settingZoom = True
        # logger.critical(f'initZoom... w={w}, h={h}')
        # logger.critical(f'initZoom... w_ng_display w={cfg.project_tab.w_ng_display.width()}, w_ng_display h={cfg.project_tab.w_ng_display.height()}')
        if self.tensor:
            if self.cs_scale:
                # logger.info(f'w={w}, h={h}, cs_scale={self.cs_scale}')
                with self.txn() as s:
                    s.cross_section_scale = self.cs_scale
                # logger.critical(f"\n\nself.cs_scale set!! {self.cs_scale}\n\n")
            else:
                # logger.info(f'w={w}, h={h}')
                self.cs_scale = self.get_zoom(w=w, h=h)
                adjusted = self.cs_scale * adjust
                with self.txn() as s:
                    s.cross_section_scale = adjusted
            # logger.critical(f"self.cs_scale = {self.cs_scale}")
            self.signals.zoomChanged.emit(self.cs_scale * 250000000)
        else:
            logger.warning("Cant set zoom now, no tensor object")


    def get_zoom(self, w, h):
        assert hasattr(self, 'tensor')
        try:
            assert self.tensor != None
        except:
            print_exception()
            return
        _, tensor_y, tensor_x = self.tensor.shape
        try:
            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale_key)  # nm per imagepixel
        except:
            res_z, res_y, res_x = [50,2,2]
            logger.warning("Fell back to default resolution settings (cfg.data may not exist)")
        scale_h = ((res_y * tensor_y) / h) * 1e-9  # nm/pixel
        scale_w = ((res_x * tensor_x) / w) * 1e-9  # nm/pixel
        cs_scale = max(scale_h, scale_w)
        # cs_scale = scale_w
        return cs_scale


    def reverse_zoom(self):
        pass

    # 2048 image_pixels x 4 nm/image_pixel = # nanometers
    #


    def get_tensors(self):
        '''TODO study this #0813'''

        # del cfg.tensor
        # del cfg.unal_tensor
        # del cfg.al_tensor
        cfg.mw.tell('Loading Zarr asynchronously using Tensorstore...')
        cfg.tensor = self.tensor = None
        try:
            # cfg.unal_tensor = get_zarr_tensor(unal_path).result()
            sf = cfg.data.scale_val(s=cfg.data.scale_key)
            if cfg.data.is_aligned():
                path = os.path.join(cfg.data.dest(), 'zarr', 's' + str(sf))
                future = get_zarr_tensor(path)
                future.add_done_callback(lambda f: print(f'Callback: {f.result().domain}'))
                self.tensor = cfg.tensor = cfg.al_tensor = future.result()
            else:
                path = os.path.join(cfg.data.dest(), 'zarr', 's' + str(sf))
                future = get_zarr_tensor(path)
                future.add_done_callback(lambda f: print(f'Callback: {f.result().domain}'))
                self.tensor = cfg.tensor = cfg.unal_tensor = future.result()

        except Exception as e:
            logger.warning('Failed to acquire Tensorstore view')
            cfg.mw.warn('Failed to acquire Tensorstore view')
            print_exception()
            ### Add funcitonality to recreate Zarr
            # raise e # raising will ensure crash
        else:
            cfg.mw.hud.done()

    def post_message(self, msg):
        with self.config_state.txn() as cs:
            cs.status_messages['message'] = msg


# class EMViewer(neuroglancer.Viewer):
class EMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))

        self.tensor = None

        self.type = 'EMViewer'
        self.initViewer()

        # asyncio.ensure_future(self.initViewer())


    # async def initViewer(self, nglayout=None):
    def initViewer(self, nglayout=None):
        caller = inspect.stack()[1].function
        if DEV:
            logger.info(f'\n\n[DEV] [{caller}] [{self.type}] Initializing Neuroglancer...\n')
        self._blockStateChanged = False

        if not nglayout:
            requested = getData('state,ng_layout')
            mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
            nglayout = mapping[requested]

        # zd = ('img_src.zarr', 'img_aligned.zarr')[cfg.data.is_aligned()] #Todo this is wrong
        if cfg.data.is_aligned():
            path = os.path.join(cfg.data.location,'zarr', cfg.data.scale_key)
        else:
            path = os.path.join(cfg.data.series['zarr_path'], cfg.data.scale_key)
        if not os.path.exists(os.path.join(path,'.zarray')):
            cfg.main_window.warn('Zarr (.zarray) Not Found: %s' % path)
            logger.warning('Zarr (.zarray) Not Found: %s' % path)
            return

        assert os.path.exists(path)
        nfiles = sum(1 for entry in os.listdir(path) if os.path.isfile(os.path.join(path,entry)))
        try:
            assert nfiles > 1
        except:
            print_exception()
            return
        self.tensor = cfg.tensor = get_zarr_tensor(path).result()
        # self.tensor = cfg.tensor = await get_zarr_tensor(path).result()

        self.coordinate_space = self.getCoordinateSpace()

        """ @param max_downsampling: Maximum amount by which on-the-fly downsampling may reduce the
            volume of a chunk.  For example, 4x4x4 downsampling reduces the volume by 64.
            
            
            data – Source data.
            volume_type – either 'image' or 'segmentation'. If not specified, guessed from the data type.
            mesh_options – A dict with the following keys specifying options for mesh simplification for 'segmentation' volumes:
            downsampling – '3d' to use isotropic downsampling, '2d' to downsample separately in XY, XZ, and YZ, None to use no downsampling.
            max_downsampling – Maximum amount by which on-the-fly downsampling may reduce the volume of a chunk. For example, 4x4x4 downsampling reduces the volume by 64"""


        """
        DEFAULT_MAX_DOWNSAMPLING = 64
        DEFAULT_MAX_DOWNSAMPLED_SIZE = 128
        DEFAULT_MAX_DOWNSAMPLING_SCALES = float('inf')        
        """

        if is_tacc():
            cfg.LV = ng.LocalVolume(
                volume_type='image',
                data=self.tensor[:, :, :],
                dimensions=self.coordinate_space,
                # max_voxels_per_chunk_log2=1024
                # downsampling=None, # '3d' to use isotropic downsampling, '2d' to downsample separately in XY, XZ, and YZ,
                # None to use no downsampling.
                max_downsampling=cfg.max_downsampling,
                max_downsampled_size=cfg.max_downsampled_size,
                # max_downsampling_scales=cfg.max_downsampling_scales #Goes a LOT slower when set to 1
            )
        else:
            cfg.LV = ng.LocalVolume(
                volume_type='image',
                data=self.tensor[:, :, :],
                dimensions=self.coordinate_space,
                # max_voxels_per_chunk_log2=1024
                # downsampling=None, # '3d' to use isotropic downsampling, '2d' to downsample separately in XY, XZ, and YZ,
                # None to use no downsampling.
                max_downsampling=cfg.max_downsampling,
                max_downsampled_size=cfg.max_downsampled_size,
                # max_downsampling_scales=cfg.max_downsampling_scales #Goes a LOT slower when set to 1
            )



        with self.txn() as s:
            s.layout.type = nglayout
            # s.gpu_memory_limit = -1
            # s.system_memory_limit = -1
            # s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            # if cfg.data.scale_val() < 6:
            #     s.show_scale_bar = True
            s.show_scale_bar = True
            s.show_axis_lines = getData('state,show_axes')
            s.position=[cfg.data.zpos + 0.5, self.tensor.shape[1]/2, self.tensor.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer( source=cfg.LV, shader=cfg.data['rendering']['shader'], )
            s.show_default_annotations = getData('state,show_bounds')
            s.projectionScale = 1
            if getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'):
                s.crossSectionBackgroundColor = getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')
            else:
                if getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'):
                    # s.crossSectionBackgroundColor = '#222222'
                    s.crossSectionBackgroundColor = '#000000'
                else:
                    s.crossSectionBackgroundColor = '#808080'


        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,show_ng_controls')
            s.show_panel_borders = False
            s.show_layer_panel = False
            # s.viewer_size = [100,100]
            s.show_help_button = True
            s.scale_bar_options.padding_in_pixels = 0 # default = 8
            s.scale_bar_options.left_pixel_offset = 10  # default = 10
            s.scale_bar_options.bottom_pixel_offset = 10  # default = 10
            s.scale_bar_options.bar_top_margin_in_pixels = 4 # default = 5
            # s.scale_bar_options.font_name = 'monospace'
            # s.scale_bar_options.font_name = 'serif'



        self._layer = math.floor(self.state.position[0])

        self.set_brightness()
        self.set_contrast()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))

        if self.state.cross_section_scale:
            val = (self.state.cross_section_scale, self.state.cross_section_scale * 250000000)[self.state.cross_section_scale < .001]
            if round(val, 3) != round(getData('state,ng_zoom'), 3):
                setData('state,ng_zoom', val)
                self.signals.zoomChanged.emit(val)




# class EMViewerStage(AbstractEMViewer):
#
#     def __init__(self, **kwags):
#         super().__init__(**kwags)
#         self.type = 'EMViewerStage'
#         # self.shared_state.add_changed_callback(self.on_state_changed_any)
#         self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
#         self.initViewer()
#
#
#     def initViewer(self):
#         caller = inspect.stack()[1].function
#         logger.info(f'\n\nInitializing {self.type} [{caller}]...\n')
#
#         self.coordinate_space = self.getCoordinateSpace()
#
#         self.get_tensors()
#         sf = cfg.data.scale_val(s=cfg.data.scale_key)
#         path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
#
#         self.index = cfg.data.zpos
#         # dir_staged = os.path.join(cfg.data.dest(), self.scale_key, 'zarr_staged', str(self.index), 'staged')
#         # self.tensor = cfg.stageViewer = get_zarr_tensor(dir_staged).result()
#
#         tensor = get_zarr_tensor(path).result()
#         self.LV = ng.LocalVolume(
#             volume_type='image',
#             # data=self.tensor,
#             data=tensor[:,:,:],
#             # data=self.tensor[self.index:self.index+1, :, :],
#             # dimensions=self.coordinate_space,
#             # dimensions=[1,1,1],
#             # dimensions=self.getCoordinateSpacePlanar(),
#             dimensions=self.coordinate_space,
#             voxel_offset=[0, 0, 0]
#         )
#         # _, tensor_y, tensor_x = cfg.tensor.shape
#         _, tensor_y, tensor_x = tensor.shape
#
#         logger.info(f'Tensor Shape: {tensor.shape}')
#
#         sf = cfg.data.scale_val(s=cfg.data.scale_key)
#         self.ref_l, self.base_l, self.aligned_l = 'ref_%d' % sf, 'base_%d' % sf, 'aligned_%d' % sf
#         with self.txn() as s:
#             '''other settings:
#             s.displayDimensions = ["z", "y", "x"]
#             s.perspective_orientation
#             s.concurrent_downloads = 512'''
#             s.gpu_memory_limit = -1
#             s.system_memory_limit = -1
#             s.layout = ng.row_layout([ng.LayerGroupViewer(layers=[self.aligned_l], layout='yz')])
#             if getData('state,neutral_contrast'):
#                 s.crossSectionBackgroundColor = '#808080'
#             else:
#                 s.crossSectionBackgroundColor = '#222222'
#             # s.show_scale_bar = True
#             s.show_scale_bar = False
#             s.show_axis_lines = False
#             s.show_default_annotations = getData('state,show_yellow_frame')
#             s.layers[self.aligned_l] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
#             # s.showSlices=False
#             # s.position = [0, tensor_y / 2, tensor_x / 2]
#             # s.position = [0.5, tensor_y / 2, tensor_x / 2]
#             # s.voxel_coordinates = [0, tensor_y / 2, tensor_x / 2] #Prev
#             # s.relativeDisplayScales = {"z": 50, "y": 2, "x": 2}
#
#         with self.config_state.txn() as s:
#             s.show_ui_controls = False
#             # s.show_ui_controls = True
#             s.show_panel_borders = False
#
#         self._crossSectionScale = self.state.cross_section_scale
#         self.initial_cs_scale = self.state.cross_section_scale
#
#         self.set_brightness()
#         self.set_contrast()
#         # self.set_zmag()
#         # self.set_zmag()
#         self.webengine.setUrl(QUrl(self.get_viewer_url()))
#         w = cfg.project_tab.MA_webengine_stage.geometry().width()
#         h = cfg.project_tab.MA_webengine_stage.geometry().height()
#         self.initZoom(w=w, h=h, adjust=1.02)
#
#         # logger.info('\n\n' + self.url() + '\n')
#
#

class PMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        # self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        self.type = 'PMViewer'
        self._example_path = example_zarr()

    def initExample(self):
        logger.info('')
        self.initViewer(path=self._example_path)
        # self.post_message("No series have been imported yet. This is just an example.")
        with self.config_state.txn() as cs:
            cs.status_messages['message'] = "No series have been imported yet. This is just an example."


    def initViewer(self, path_l=None, path_r=None):
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] [{self.type}]\n"
                        f"path_l: {path_l}\n"
                        f"path_r: {path_r}")
        # if path_l:
        self.path_l = path_l
        self.path_r = path_r
        self.tensor, self.tensor_r = None, None
        self.LV_l, self.LV_r = None, None
        # else:
        #     self.path_l = self._example_path
        # coordinate_space = ng.CoordinateSpace(names=['z', 'y', 'x'], units=['nm', 'nm', 'nm'], scales=scales, )
        coordinate_space = ng.CoordinateSpace(names=['z', 'y', 'x'], units=['nm', 'nm', 'nm'], scales=[50,2,2])
        # try:
        #     self.tensor = get_zarr_tensor(path_l).result()
        # except:
        #     self.tensor = get_zarr_tensor(self._example_path).result()
        #     with self.config_state.txn() as cs:
        #         cs.status_messages['message'] = "No series have been imported yet. This is just an example."
        #     print_exception()

        if self.path_l:
            try:
                self.tensor = get_zarr_tensor(path_l).result()
                self.LV_l = ng.LocalVolume(
                    volume_type='image',
                    data=self.tensor[:, :, :],
                    dimensions=coordinate_space,
                    # max_voxels_per_chunk_log2=1024
                    # downsampling=None, # '3d' to use isotropic downsampling, '2d' to downsample separately in XY, XZ, and YZ,
                    # None to use no downsampling.
                    max_downsampling=cfg.max_downsampling,
                    max_downsampled_size=cfg.max_downsampled_size,
                    # max_downsampling_scales=cfg.max_downsampling_scales #Goes a LOT slower when set to 1
                )
            except:
                print_exception()

        if self.path_r:
            try:
                self.tensor_r = get_zarr_tensor(path_r).result()
                self.LV_r = ng.LocalVolume(
                    volume_type='image',
                    data=self.tensor_r[:, :, :],
                    dimensions=coordinate_space,
                    # max_voxels_per_chunk_log2=1024
                    # downsampling=None, # '3d' to use isotropic downsampling, '2d' to downsample separately in XY, XZ, and YZ,
                    # None to use no downsampling.
                    max_downsampling=cfg.max_downsampling,
                    max_downsampled_size=cfg.max_downsampled_size,
                    # max_downsampling_scales=cfg.max_downsampling_scales #Goes a LOT slower when set to 1
                )
            except:
                print_exception()

        with self.txn() as s:
            s.layout.type = 'yz'
            if self.LV_l:
                s.layers['layer0'] = ng.ImageLayer(source=self.LV_l)
            else:
                s.layers['layer0'] = ng.ImageLayer()
            if self.LV_r:
                s.layers['layer1'] = ng.ImageLayer(source=self.LV_r)
            else:
                s.layers['layer1'] = ng.ImageLayer()
            s.crossSectionBackgroundColor = '#222222'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_default_annotations = True
            s.show_axis_lines = True
            s.show_scale_bar = False
            s.layout = ng.row_layout([
                ng.LayerGroupViewer(layout='yz', layers=['layer0']),
                ng.LayerGroupViewer(layout='yz', layers=['layer1'],),
            ])


        with self.config_state.txn() as s:
            s.show_ui_controls = False
            s.status_messages = None
            s.show_panel_borders = False
            s.show_layer_panel = False


        self.webengine.setUrl(QUrl(self.get_viewer_url()))




class EMViewerMendenhall(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        # self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        self.type = 'EMViewerMendenhall'

    def initViewer(self):
        logger.info('Initializing Neuroglancer - Mendenhall...')
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
    EMViewer.initViewer()
