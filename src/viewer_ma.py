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
from neuroglancer.json_wrappers import (JsonObjectWrapper, array_wrapper, optional, text_type, typed_list,
                                        typed_map, typed_set, typed_string_map, wrapped_property,
                                        number_or_string)

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['MAViewer']

logger = logging.getLogger(__name__)
# handler = logging.StreamHandler(stream=sys.stdout)
# logger.addHandler(handler)

class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()
    ptsChanged = Signal()


class MAViewer(neuroglancer.Viewer):
    def __init__(self, index, role=None, webengine=None):
        super().__init__()
        self.index = index
        if role:
            self.role = role
        self.webengine = webengine
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.cs_scale = None
        self.pts = {}
        self.points = {}
        self.mp_colors = ['#f3e375', '#5c4ccc', '#800000',
                          '#aaa672', '#152c74', '#404f74',
                          '#f3e375', '#5c4ccc', '#d6acd6',
                          '#aaa672', '#152c74', '#404f74']
        self._crossSectionScale = 1
        self._mpCount = 0
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        logger.info('viewer constructed!')

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale())), )

        self.restoreManAlignPts()


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


    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()


    def set_zmag(self):
        with self.txn() as s:
            s.relativeDisplayScales = {"z": 10} # this should work, but does not work. ng bug.


    def initViewer(self):
        caller = inspect.stack()[1].function
        logger.critical(f'Initializing EMViewer Slim (caller: {caller})....')
        sf = cfg.data.scale_val(s=cfg.data.scale())

        # self.clear_layers()


        if self.role == 'base':
            self.index = cfg.data.layer()
            path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        elif self.role == 'ref':
            path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))
        elif self.role == 'stage':
            self.index = 0 #placeholder. this will be the index of staging area.
            path = os.path.join(cfg.data.dest(), 'img_stage.zarr', 's' + str(sf))

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

        # self.pts.clear()
        # self.restoreManAlignPts()

        with self.txn() as s:

            s.layout.type = 'yz'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            # s.position=[cfg.data.layer(), store.shape[1]/2, store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV)
            s.crossSectionBackgroundColor = '#808080' # 128 grey
            # s.cross_section_scale = 1
            _, y, x = self.store.shape
            s.position = [0.5, y / 2, x / 2]

            s.layers['ann'].annotations = list(self.pts.values())




        # mp_key_bindings = [
        #     # ['keyx', 'add_matchpoint'],
        #     # ['dblclick0', 'add_matchpoint'],
        #     # ['keys', 'save_matchpoints'],
        #     # ['keyc', 'clear_matchpoints'],
        # ]
        self.actions.add('add_matchpoint', self.add_matchpoint)
        # self.actions.add('save_matchpoints', self.save_matchpoints)
        # self.actions.add('clear_matchpoints', self.clear_matchpoints)


        with self.config_state.txn() as s:
            # for key, command in mp_key_bindings:
            #     s.input_event_bindings.viewer[key] = command
            # s.input_event_bindings.data_view['dblclick0'] = 'add_matchpoint'
            # s.input_event_bindings.data_view['click0'] = 'add_matchpoint'
            s.input_event_bindings.slice_view['shift+click0'] = 'add_matchpoint'
            s.show_ui_controls = False
            s.show_panel_borders = False


        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = getOpt('neuroglancer,SHOW_PANEL_BORDERS')
            # s.viewer_size = [100,100]

        # self.shared_state.add_changed_callback(self.on_state_changed) #0215+ why was this OFF?
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        # if cfg.main_window.detachedNg.isVisible():
        #     logger.critical('detached Neuroglancer is visible! Setting its page...')
        #     cfg.main_window.detachedNg.setUrl(url=self.get_viewer_url())
        # self.set_zmag()

        self.update_annotations()

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))


    def get_layout(self, requested=None):
        if requested == None:
            requested = cfg.data['ui']['ng_layout']
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        return mapping[requested]


    def on_state_changed(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        if calname == '<lambda>':
            return
        # logger.info('caller: %s, calname: %s' % (caller, calname))

        self.signals.stateChanged.emit()

        # if not self.cs_scale:
        #     if self.state.cross_section_scale:
        #         if self.state.cross_section_scale > .0001:
        #             logger.info('perfect cs_scale captured! - %.3f' % self.state.cross_section_scale)
        #             self.cs_scale = self.state.cross_section_scale
        #
        # try:
        zoom = self.state.cross_section_scale
        # logger.info('self.state.cross_section_scale = %s' % str(zoom))
        if zoom:
            if zoom != self._crossSectionScale:
                logger.info(f' (!) emitting zoomChanged (state.cross_section_scale): {zoom}...')
                self.signals.zoomChanged.emit(zoom)
            self._crossSectionScale = zoom
        # except:
        #     print_exception()
        #     logger.error('ERROR on_state_change')


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

    def add_matchpoint(self, s):
        coords = np.array(s.mouse_voxel_coordinates)
        logger.critical('coords: %s' %str(coords))
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless! =%s' % str(coords))
            return

        z, y, x = s.mouse_voxel_coordinates

        props = [self.mp_colors[len(self.pts)], getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'), getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
        self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=repr(coords), point=coords, props=props)
        self.update_annotations()
        self.signals.ptsChanged.emit()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))



    def update_annotations(self):
        anns = list(self.pts.values())
        if anns:
            with self.txn() as s:
                s.layers['ann'].annotations = anns


    def getNextUnusedColor(self):
        for c in self.mp_colors:
            if c in self.pts:
                continue
            else:
                return c


    def getUsedColors(self):
        return set(self.pts.keys())


    def save_matchpoints(self):
        layer = cfg.data.layer()
        logger.info('Saving Match Points for Section #%d: %s' % (layer, cfg.data.base_image_name(l=layer)))
        p_ = [p.point.tolist() for p in self.pts.values()]
        logger.critical('p_: %s' %str(p_))
        mps = [p_[0][1::], p_[1][1::], p_[2][1::]]
        cfg.data.set_match_points(role=self.role, matchpoints=mps, l=layer)
        cfg.data.set_selected_method(method="Match Point Align", l=layer)
        cfg.data.print_all_match_points()
        cfg.main_window._saveProjectToFile(silently=True)
        cfg.main_window.hud.post('Match Points Saved!')


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

    def restoreManAlignPts(self):
        logger.info('')

        for i, p in enumerate(cfg.data.getmpFlat()[self.role]):
            props = [self.mp_colors[i],
                     getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                     getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
            self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=str(p), point=p, props=props)

        with self.txn() as s:
            s.layers['ann'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotations=self.pt2ann(points=cfg.data.getmpFlat()[self.role]),
                # annotations=self.pt2ann(points=[(0,100,100)]),
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='ptColor', type='rgb', default='white', ),
                    ng.AnnotationPropertySpec(id='ptWidth', type='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT')),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'))
                ],
                shader=copy.deepcopy(ann_shader),
            )


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    viewer = MAViewer()
    viewer.initViewer()
