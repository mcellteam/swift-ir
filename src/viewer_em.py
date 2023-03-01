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
import time

import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, QUrl
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getpOpt, setpOpt, obj_to_string, print_exception
from src.shaders import ann_shader
import src.config as cfg
from neuroglancer.json_wrappers import (JsonObjectWrapper, array_wrapper, optional, text_type, typed_list,
                                        typed_map, typed_set, typed_string_map, wrapped_property,
                                        number_or_string)

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['EMViewer']

logger = logging.getLogger(__name__)
# handler = logging.StreamHandler(stream=sys.stdout)
# logger.addHandler(handler)

class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal(int)
    zoomChanged = Signal(float)
    mpUpdate = Signal()


class EMViewer(neuroglancer.Viewer):
    def __init__(self, name=None, force_xy=False, webengine=None):
        super().__init__()
        if name:
            self.name=name
        self.webengine = webengine
        self.force_xy = force_xy
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.cs_scale = None
        self._crossSectionScale = 1
        self.orientation = None
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        logger.info('viewer constructed!')


    def __del__(self):
        try:
            caller = inspect.stack()[1].function
            logger.warning('__del__ called by [%s] on EMViewer (created: %s)'
                           % (caller, self.created))
        except Exception as e:
            logger.warning('Lost Track Of Caller')
            raise e
        pass

    # def __str__(self):
    #     return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.state)

    def request_layer(self):
        return math.floor(self.state.position[0])

    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()

    # def set_zmag(self):
    #     if cfg.MP_MODE:
    #         with self.txn() as s:
    #             s.relativeDisplayScales = {"z": 10} # this should work, but does not work. ng bug.


    def set_layer(self, l:int):
        state = copy.deepcopy(self.state)
        state.position[0] = l
        self.set_state(state)

    def initViewerMendenhall(self):
        logger.critical('Initializing Neuroglancer - Mendenhall...')
        path = os.path.join(cfg.data.dest(), 'mendenhall.zarr', 'grp')
        scales = [50, 2, 2]
        coordinate_space = ng.CoordinateSpace(names=['z', 'y', 'x'], units=['nm','nm','nm'], scales=scales, )
        cfg.men_tensor = get_zarr_tensor(path).result()
        self.json_unal_dataset = cfg.men_tensor.spec().to_json()
        logger.debug(self.json_unal_dataset)
        cfg.menLV = ng.LocalVolume(
            data=cfg.men_tensor,
            dimensions=coordinate_space,
            voxel_offset=[0, 0, 0],
        )
        logger.info('Instantiating Viewer...')
        image_size = cfg.data.image_size()
        widget_size = cfg.main_window.globTabs.size()
        logger.critical(f'cfg.main_window.globTabs.size() = {cfg.main_window.globTabs.size()}')
        logger.critical(f'widget_size = {widget_size}')

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

    def initViewer(self):

        if cfg.project_tab._tabs.currentIndex() == 3:
            self.initViewerSbs(requested='xy', orientation='vertical')
        elif getpOpt('state,MANUAL_MODE'):
            self.initViewerSbs(requested='xy')
        else:
            if cfg.main_window.rb0.isChecked():
                cfg.data['ui']['ng_layout'] = '4panel'
                self.initViewerSlim()
            elif cfg.main_window.rb1.isChecked():
                cfg.data['ui']['ng_layout'] = 'xy'
                self.initViewerSbs()


    def initViewerSbs(self, requested=None, orientation='horizontal'):
        caller = inspect.stack()[1].function
        logger.critical(f'Initializing EMViewer (caller: {caller})....')
        self.orientation = orientation

        if requested == None:
            requested = cfg.data['ui']['ng_layout']
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
          'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        nglayout = mapping[requested]

        # logger.critical(f'passed arg: {nglayout}')


        if cfg.data.is_mendenhall(): self.initViewerMendenhall(); return

        self.clear_layers()

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.curScale)),
        )

        if getpOpt('state,MANUAL_MODE'):
            sf = cfg.data.scale_val(s=cfg.data.scale())
            al_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
            self.store = cfg.tensor = cfg.al_tensor =  get_zarr_tensor(al_path).result()
            self.index = cfg.data.layer()
            self.LV = ng.LocalVolume(
                volume_type='image',
                data=self.store[self.index:self.index + 1, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, 0, 0]
            )
        else:
            self.make_local_volumes()


        is_aligned = cfg.data.is_aligned_and_generated()
        if is_aligned:
            tensor_z, tensor_y, tensor_x = cfg.al_tensor.shape
        else:
            tensor_z, tensor_y, tensor_x = cfg.unal_tensor.shape

        self.set_zoom()
        sf = cfg.data.scale_val(s=cfg.data.scale())
        self.ref_l, self.base_l, self.aligned_l = 'ref_%d' % sf, 'base_%d' % sf, 'aligned_%d' % sf


        if getpOpt('state,MANUAL_MODE'):
            self.grps = [ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout)]
        else:
            self.grps = []
            self.grps.append(ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout))
            self.grps.append(ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout))
            if is_aligned:
                self.grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout))

        with self.txn() as s:
            '''other settings: 
            s.displayDimensions = ["z", "y", "x"]
            s.perspective_orientation
            s.concurrent_downloads = 512'''
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            if self.orientation == 'vertical':
                s.show_scale_bar = False
                s.show_default_annotations = False
                s.show_axis_lines = False
            else:
                s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
                s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
                s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            if self.orientation == 'vertical':
                s.crossSectionBackgroundColor = '#1b1e23'
            else:
                s.crossSectionBackgroundColor = '#808080'
            s.layout.type = nglayout
            if getpOpt('state,MANUAL_MODE'):
                s.layers[self.aligned_l] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            else:
                s.layers[self.ref_l] = ng.ImageLayer(source=cfg.refLV, shader=cfg.data['rendering']['shader'], )
                s.layers[self.base_l] = ng.ImageLayer(source=cfg.baseLV, shader=cfg.data['rendering']['shader'],)
                if is_aligned: s.layers[self.aligned_l] = ng.ImageLayer(source=cfg.alLV, shader=cfg.data['rendering']['shader'],)
            s.showSlices=False
            if orientation == 'horizontal':
                s.layout = ng.row_layout(self.grps)
            elif orientation == 'vertical':
                s.layout = ng.column_layout(self.grps)  # col
            else:
                s.layout = ng.row_layout(self.grps)

            # s.layout = ng.row_layout(self.grps)  # col

            if getpOpt('state,MANUAL_MODE'):
                s.position = [0, tensor_y / 2, tensor_x / 2]
            else:
                s.position = [cfg.data.layer(), tensor_y / 2, tensor_x / 2]

        with self.config_state.txn() as s:
            if self.force_xy:
                s.show_ui_controls = False
            else:
                s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = False
            # if orientation == 'vertical':
                # s.viewer_size = (200,600)

        self._layer = math.floor(self.state.position[0])
        self._crossSectionScale = self.state.cross_section_scale

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))
            time.sleep(.25)
            self.webengine.setUrl(QUrl(self.get_viewer_url()))
            time.sleep(.25)
            self.webengine.setUrl(QUrl(self.get_viewer_url()))


    def initViewerSlim(self, nglayout=None):
        caller = inspect.stack()[1].function
        logger.critical(f'Initializing EMViewer Slim (caller: {caller})....')

        if self.force_xy:
            logger.info('Forcing xy...')
            requested = 'xy'
        else:
            requested = cfg.data['ui']['ng_layout']
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
          'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        nglayout = mapping[requested]

        zd = ('img_src.zarr', 'img_aligned.zarr')[cfg.data.is_aligned_and_generated()]
        path = os.path.join(cfg.data.dest(), zd, 's' + str(cfg.data.scale_val()))
        if not os.path.exists(path):
            cfg.main_window.warn('Zarr Not Found: %s' % path)
            return
        try:
            if cfg.USE_TENSORSTORE:
                self.store = cfg.tensor = get_zarr_tensor(path).result()
            else:
                logger.info('Opening Zarr...')
                self.store = zarr.open(path)
        except:
            print_exception()
            cfg.main_window.warn('There was a problem loading tensor at %s' % path)
            cfg.main_window.warn('Trying with regular Zarr datastore...')
            try:
                self.store = zarr.open(path)
            except:
                print_exception()
                cfg.main_window.warn('Unable to load Zarr')
                return
            else:    print('Zarr Loaded Successfully!')
        else:
            print('TensorStore Loaded Successfully!')

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale())), )

        self.LV = cfg.LV = cfg.LV = ng.LocalVolume(
            volume_type='image',
            data=self.store[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, ] * 3,
        )

        with self.txn() as s:
            s.layout.type = nglayout
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.position=[cfg.data.layer(), self.store.shape[1]/2, self.store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer( source=self.LV, shader=cfg.data['rendering']['shader'], )
            s.crossSectionBackgroundColor = '#808080' # 128 grey
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')


        with self.config_state.txn() as s:
            if self.force_xy:
                s.show_ui_controls = False
            else:
                s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = False
            # s.viewer_size = [100,100]

        self._layer = self.request_layer()
        self.shared_state.add_changed_callback(self.on_state_changed) #0215+ why was this OFF?
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))



    def set_zoom(self):
        logger.info('')

        if self.cs_scale:
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:

            area = cfg.main_window.globTabs.geometry().getRect()
            if cfg.data.is_aligned_and_generated():
                tensor_z, tensor_y, tensor_x = cfg.al_tensor.shape
            else:
                tensor_z, tensor_y, tensor_x = cfg.unal_tensor.shape

            is_aligned = cfg.data.is_aligned_and_generated()

            if getpOpt('state,MANUAL_MODE'):
                widget_w = cfg.project_tab.MA_webengine_stage.geometry().width()
                widget_h = cfg.project_tab.MA_webengine_stage.geometry().height()
                logger.info('widget w/h: %d/%d' % (widget_w, widget_h))
            elif self.orientation=='vertical':
                logger.critical('geometry = %s' %str(cfg.project_tab.snrPlotSplitter.geometry()))
                widget_h = cfg.project_tab.snrPlotSplitter.geometry().height()
                widget_w = cfg.project_tab.snrPlotSplitter.sizes()[1]
            else:
                widget_w = area[2]/(2,3)[cfg.main_window.rb1.isChecked() and is_aligned]
                widget_h = area[3]

            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale()) # nm per imagepixel
            # tissue_h, tissue_w = res_y*frame[0], res_x*frame[1]  # nm of sample

            if getpOpt('state,MANUAL_MODE'):
                scale_h = ((res_y * tensor_y) / widget_h) * 1e-9  # nm/pixel (subtract height of ng toolbar)
                scale_w = ((res_x * tensor_x) / widget_w) * 1e-9  # nm/pixel (subtract width of sliders)
            else:
                scale_h = ((res_y*tensor_y) / (widget_h - 74)) * 1e-9  # nm/pixel (subtract height of ng toolbar)
                scale_w = ((res_x*tensor_x) / (widget_w - 20)) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)

            with self.txn() as s:
                if getpOpt('state,MANUAL_MODE'):
                    s.crossSectionScale = cs_scale *1.04
                elif self.orientation == 'vertical':
                    s.crossSectionScale = cs_scale * 1.20
                else:
                    s.crossSectionScale = cs_scale * 1.06


    # def set_rds(self):
    #     with self.txn() as s:
    #         s.relative_display_scales = {'z': 14}


    def get_nudge(self):
        if cfg.data.is_aligned_and_generated():
            _, tensor_y, tensor_x = cfg.al_tensor.shape
            return (tensor_x - cfg.al_tensor.shape[2]) / 2, (tensor_y - cfg.al_tensor.shape[1]) / 2
        else:
            return 0, 0
        return (x_nudge, y_nudge)


    def on_state_changed(self):
        if getpOpt('state,MANUAL_MODE'):
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
            # request_layer = floor(self.state.position[0])
            if isinstance(self.state.position, np.ndarray):
                request_layer = int(self.state.position[0])
                if request_layer == self._layer:
                    logger.debug('State Changed, But Layer Is The Same - Suppressing The stateChanged Callback Signal')
                else:
                    self._layer = request_layer
                    logger.info(f'(!) emitting request_layer: {request_layer}')
                    self.signals.stateChanged.emit(request_layer)

            zoom = self.state.cross_section_scale
            # logger.info('self.state.cross_section_scale = %s' % str(zoom))
            if zoom:
                if zoom != self._crossSectionScale:
                    logger.info(f' (!) emitting zoomChanged (state.cross_section_scale): {zoom}...')
                    self.signals.zoomChanged.emit(zoom)
                self._crossSectionScale = zoom
        except:
            print_exception()
            logger.error('ERROR on_state_change')


    def url(self):
        return self.get_viewer_url()


    def get_layout(self):
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        val = mapping[cfg.main_window.comboboxNgLayout.currentText()]
        return val


    def clear_layers(self):
        if self.state.layers:
            logger.info('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)


    def set_row_layout(self, nglayout):

        with self.txn() as s:
            if cfg.data.is_aligned_and_generated():
                if getpOpt('state,MANUAL_MODE'):
                    s.layout = ng.row_layout([
                        ng.column_layout([
                            ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout),
                        ]),
                    ])
                else:
                    s.layout = ng.row_layout([
                        ng.column_layout([
                            ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout),
                            ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout),
                        ]),
                        ng.column_layout([
                            ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout),
                        ]),
                    ])
            else:
                s.layout = ng.row_layout(self.grps)

    def set_vertical_layout(self, nglayout):
        with self.txn() as s:
            if cfg.data.is_aligned_and_generated():
                if getpOpt('state,MANUAL_MODE'):
                    ng.column_layout([
                        ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout),
                        ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout),
                        ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout),
                    ]),
                else:
                    ng.column_layout([
                        ng.LayerGroupViewer(layers=[self.ref_l], layout=nglayout),
                        ng.LayerGroupViewer(layers=[self.base_l], layout=nglayout),
                    ]),
            else:
                s.layout = ng.row_layout(self.grps)

    def make_local_volumes(self):
        sf = cfg.data.scale_val(s=cfg.data.scale())
        al_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
        unal_path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        cfg.tensor = cfg.unal_tensor = cfg.al_tensor = None
        try:
            cfg.unal_tensor = get_zarr_tensor(unal_path).result()
            if cfg.data.is_aligned_and_generated(): cfg.al_tensor = get_zarr_tensor(al_path).result()
            cfg.tensor = (cfg.unal_tensor, cfg.al_tensor)[cfg.data.is_aligned_and_generated()]
        except Exception as e:
            logger.warning('Failed to acquire Tensorstore view')
            raise e

        x_nudge, y_nudge = self.get_nudge()
        cfg.refLV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[0:len(cfg.data) - 1, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[1, y_nudge, x_nudge]
        )
        cfg.baseLV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, y_nudge, x_nudge],
        )
        if cfg.data.is_aligned_and_generated():
            cfg.alLV = ng.LocalVolume(
                volume_type='image',
                data=cfg.al_tensor[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, ] * 3,
            )
        if cfg.data.is_aligned_and_generated():
            cfg.LV = ng.LocalVolume(
                volume_type='image',
                data=cfg.al_tensor[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, ] * 3,
            )
        else:
            cfg.LV = ng.LocalVolume(
                volume_type='image',
                data=cfg.unal_tensor[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, ] * 3,
            )


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
    EMViewer.initViewerSlim()
