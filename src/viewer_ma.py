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
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, QUrl
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, obj_to_string, print_exception
from src.shaders import ann_shader
import src.config as cfg

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['MAViewer']

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()
    ptsChanged = Signal()


class MAViewer(neuroglancer.Viewer):
    def __init__(self, role=None, webengine=None):
        super().__init__()
        self.index = None
        if role:
            self.role = role
        self.webengine = webengine
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.cs_scale = None
        self.pts = {}
        self.points = {}
        self.mp_colors = ['#f3e375', '#5c4ccc', '#800000', '#aaa672',
                          '#152c74', '#404f74', '#f3e375', '#5c4ccc',
                          '#d6acd6', '#aaa672', '#152c74', '#404f74'
                          ]
        self._crossSectionScale = 1
        self._mpCount = 0
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        logger.info('viewer constructed!')

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale())), )

        # self.restoreManAlignPts()

        self.initViewer()


    def __del__(self):
        try:
            caller = inspect.stack()[1].function
            logger.warning('__del__ called by [%s] on EMViewer (created: %s)'
                           % (caller, self.created))
        except Exception as e:
            logger.warning('Lost Track Of Caller')

    # def __str__(self):
    #     return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.state)

    def n_annotations(self):
        return len(self.state.layers['ann'].annotations)


    def position(self):
        return self.state.position

    def set_position(self, val):
        # state = copy.deepcopy(self.state)
        # state.position = val
        # self.set_state(state)
        with self.txn() as s:
            s.position = val

    def zoom(self):
        return self.state.crossSectionScale

    def set_zoom(self, val):
        # state = copy.deepcopy(self.state)
        # state.crossSectionScale = val
        # self.set_state(state)
        with self.txn() as s:
            s.crossSectionScale = val

    def undrawAnnotations(self):
        with self.txn() as s:
            s.layers['ann'].annotations = None

    def set_layer(self, index):
        state = copy.deepcopy(self.state)
        state.position[0] = index
        self.set_state(state)

    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()


    def initViewer(self):
        # caller = inspect.stack()[1].function
        # logger.critical('caller: %s' %str(caller))
        logger.info(f'Initializing Viewer (Role: %s)....' %self.role)

        if self.role == 'ref':
            self.index = max(cfg.data.loc - 1, 0)
        elif self.role == 'base':
            self.index = cfg.data.loc #

        self.clear_layers()
        self.restoreManAlignPts()

        sf = cfg.data.scale_val(s=cfg.data.scale())
        path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        # if self.role == 'base':
        #     path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        # elif self.role == 'ref':
        #     path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        # elif self.role == 'stage':
        #     self.index = 0 #placeholder. this will be the index of staging area.
        #     path = os.path.join(cfg.data.dest(), 'img_stage.zarr', 's' + str(sf))


        if not os.path.exists(path):
            cfg.main_window.warn('Data Store Not Found: %s' % path)
            logger.warning('Data Store Not Found: %s' % path); return

        try:
            self.store = get_zarr_tensor(path).result()
        except Exception as e:
            cfg.main_window.warn('Unable to Load Data Store at %s' % path)
            raise e

        self.LV = ng.LocalVolume(
            volume_type='image',
            data=self.store[self.index:self.index+1, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, 0, 0]
        )


        with self.txn() as s:

            s.layout.type = 'yz'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            # s.position=[cfg.data.loc, store.shape[1]/2, store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            s.crossSectionBackgroundColor = '#808080' # 128 grey
            # s.cross_section_scale = 1 #bug # cant do this
            _, y, x = self.store.shape
            s.position = [0.5, y / 2, x / 2]
            # s.position = [0.1, y / 2, x / 2]
            s.layers['ann'].annotations = list(self.pts.values())

        self.actions.add('add_manpoint', self.add_matchpoint)

        with self.config_state.txn() as s:
            s.input_event_bindings.slice_view['shift+click0'] = 'add_manpoint'
            s.show_ui_controls = False
            s.show_panel_borders = False

        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = False

        self.update_annotations()

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))

        self.set_brightness()
        self.set_contrast()
        # self.set_zmag()
        # self.initZoom()
        # self._set_zmag()


    def get_layout(self, requested=None):
        if requested == None:
            requested = cfg.data['ui']['ng_layout']
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        return mapping[requested]


    def on_state_changed(self):
        # caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        if calname == '<lambda>':
            return

        self.signals.stateChanged.emit()
        zoom = self.state.cross_section_scale
        if zoom:
            if zoom != self._crossSectionScale:
                logger.info(f' (!) emitting zoomChanged (state.cross_section_scale): {zoom}...')
                self.signals.zoomChanged.emit(zoom)
            self._crossSectionScale = zoom


    def pt2ann(self, points: list):
        annotations = []
        lineweight = cfg.main_window.mp_marker_lineweight_spinbox.value()
        size = cfg.main_window.mp_marker_size_spinbox.value()
        for i, point in enumerate(points):
            annotations.append(ng.PointAnnotation(id=repr(point),
                                                  point=point,
                                                  props=[self.mp_colors[i % 3],
                                                         size,
                                                         lineweight]))
        self.annotations = annotations
        return annotations


    def addMp(self):

        pass


    def update_annotations(self):
        anns = list(self.pts.values())
        if anns:
            with self.txn() as s:
                s.layers['ann'].annotations = anns

    def remove_annotations(self):
        with self.txn() as s:
            s.layers['ann'].annotations = None


    def getNextUnusedColor(self):
        for c in self.mp_colors:
            if c in self.pts:
                continue
            else:
                return c


    def getUsedColors(self):
        return set(self.pts.keys())


    # def save_matchpoints(self):
    #     logger.info('Saving Match Points for Section #%d: %s' % (layer, cfg.data.base_image_name(l=layer)))
    #     p_ = [p.point.tolist() for p in self.pts.values()]
    #     logger.critical('p_: %s' %str(p_))
    #     mps = [p_[0][1::], p_[1][1::], p_[2][1::]]
    #     cfg.data.set_manual_points(role=self.role, matchpoints=mps, l=self.index)
    #     cfg.data.set_selected_method(method="Match Point Align", l=self.index)
    #     cfg.data.print_all_match_points()
    #     cfg.main_window._saveProjectToFile(silently=True)
    #     cfg.main_window.hud.post('Match Points Saved!')


    # def clear_matchpoints(self, s):
    #     cfg.main_window.hud.post('Clearing manual correspondence point buffer of %d match points...' % self._mpCount)
    #     logger.warning('Clearing manual correspondence point buffer of %d match points...' % self._mpCount)
    #     self.pts.clear()
    #     with self.txn() as s:
    #         s.layers['ann'].annotations = self.pt2ann(cfg.data.getmpFlat()[self.role])


    def url(self):
        return self.get_viewer_url()


    def clear_layers(self):
        if self.state.layers:
            logger.info('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)



    def add_matchpoint(self, s):
        coords = np.array(s.mouse_voxel_coordinates)
        logger.info('Coordinates: %s' %str(coords))
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless! =%s' % str(coords))
            return
        _, y, x = s.mouse_voxel_coordinates
        z = 0.5
        # z = 0.1
        props = [self.mp_colors[len(self.pts)],
                 getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                 getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
        self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=repr((z,y,x)), point=(z,y,x), props=props)
        self.update_annotations()
        self.signals.ptsChanged.emit()
        self._set_zmag()

        # self._set_zmag()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))


    def restoreManAlignPts(self):
        logger.info('Restoring manual alignment points for role: %s' %self.role)
        self.pts = {}
        pts_data = cfg.data.getmpFlat(l=cfg.data.loc)[self.role]
        for i, p in enumerate(pts_data):
            props = [self.mp_colors[i],
                     getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                     getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
            self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=str(p), point=p, props=props)

        with self.txn() as s:
            s.layers['ann'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotations=self.pt2ann(points=pts_data),
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='ptColor', type='rgb', default='white', ),
                    ng.AnnotationPropertySpec(id='ptWidth', type='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT')),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'))
                ],
                shader=copy.deepcopy(ann_shader),
            )

        # json_str = self.state.layers.to_json()
        # logger.critical('--------------')
        # logger.critical(json_str[0]['annotations'])


    def set_brightness(self, val=None):
        logger.info('')
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['brightness'] = val
            # else:   layer.shaderControls['brightness'] = cfg.data.brightness()
            else:   layer.shaderControls['brightness'] = cfg.data.brightness
            # layer.volumeRendering = True
        self.set_state(state)

    def set_contrast(self, val=None):
        logger.info('')
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['contrast'] = val
            # else:   layer.shaderControls['contrast'] = cfg.data.contrast()
            else:   layer.shaderControls['contrast'] = cfg.data.contrast
            # layer.volumeRendering = True
        self.set_state(state)

    def set_zmag(self, val=10):
        logger.info('')
        try:
            state = copy.deepcopy(self.state)
            state.relativeDisplayScales = val
            self.set_state(state)
        except:
            logger.warning('Unable to set Z-mag')
        else:
            logger.info('Successfully set Z-mag!')

    def _set_zmag(self):
        with self.txn() as s:
            s.relativeDisplayScales = {"z": 10}

    def initZoom(self):
        logger.info('')

        if self.cs_scale:
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:
            _, tensor_y, tensor_x = cfg.tensor.shape
            widget_w = cfg.project_tab.MA_webengine_ref.geometry().width()
            widget_h = cfg.project_tab.MA_webengine_ref.geometry().height()
            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale()) # nm per imagepixel
            # tissue_h, tissue_w = res_y*frame[0], res_x*frame[1]  # nm of sample
            scale_h = ((res_y * tensor_y) / widget_h) * 1e-9  # nm/pixel (subtract height of ng toolbar)
            scale_w = ((res_x * tensor_x) / widget_w) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)

            with self.txn() as s:
                # s.crossSectionScale = cs_scale * 1.20
                s.crossSectionScale = cs_scale



if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    viewer = MAViewer()
    viewer.initViewer()




    from src.funcs_zarr import get_zarr_tensor
    sf = cfg.data.scale_val(s=cfg.data.scale())
    path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
