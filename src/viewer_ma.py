#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server

with cfg.refViewer.txn() as s:
    print(s.layers['SWIM'].annotations)
'''

import os
import copy
import math
import inspect
import logging
import datetime
import argparse
import asyncio
import functools
import time
from collections import OrderedDict
from functools import cache
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, Slot, QUrl, QTimer
from qtpy.QtWidgets import QApplication
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, print_exception, is_joel, caller_name
from src.shaders import ann_shader
from src.ui.timer import Timer
import src.config as cfg

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['MAViewer']

logger = logging.getLogger(__name__)

# t = Timer()

DEV = is_joel()


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    zposChanged = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()
    ptsChanged = Signal()
    swimAction = Signal()



class MAViewer(neuroglancer.Viewer):
    def __init__(self, role=None, webengine=None):
        super().__init__()
        self.index = None
        self.role = role
        self.webengine = webengine
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        # self._settingZoom = True
        # self._layer = cfg.data.zpos
        self.cs_scale = None
        # self.pts = OrderedDict()
        self.pts = []
        self.colors = cfg.glob_colors
        self._crossSectionScale = 1
        self._mpCount = 0
        self._zmag_set = 0
        # self.shared_state.add_changed_callback(self.on_state_changed)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        # self.shared_state.add_changed_callback(self.on_state_changed_any)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        # self.signals.ptsChanged.connect(self.drawSWIMwindow)
        self.type = 'MAViewer'
        self._inSync = 0
        self._blockStateChanged = False

        logger.info('viewer constructed!')

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale_key)), )
            # scales=[1,1,1] )

        self._dontDraw = 0

        # QApplication.processEvents()
        self.initViewer()
        # asyncio.ensure_future(self.initViewer())


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

    def z(self):
        # return int(math.floor(self.state.position[0]))
        return int(self.state.voxel_coordinates[0])


    def print_layers(self):
        logger.info(f"# layers: {len(self.state.layers['SWIM'].annotations)}")
        logger.info(f"annotations = {self.state.layers['SWIM'].annotations}")
        # with self.txn() as s:
        #     logger.info(f"# layers: {len(self.state.layers['SWIM'].annotations)}")
        #     logger.info(s.layers['SWIM'].annotations)

    def updateUIControls(self):
        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,show_ng_controls')


    def n_annotations(self):
        return len(self.state.layers['ann_points'].annotations)

    def updateHighContrastMode(self):
        with self.txn() as s:
            if getData('state,neutral_contrast'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'

    def position(self):
        return copy.deepcopy(self.state.position)
        # return self.state.position

    def set_position(self, val):
        # state = copy.deepcopy(self.state)
        # state.position = val
        # self.set_state(state)
        with self.txn() as s:
            s.position = val

    def zoom(self):
        return copy.deepcopy(self.state.crossSectionScale)
        # return self.state.crossSectionScale


    def set_zoom(self, val):



        caller = inspect.stack()[1].function
        logger.info(f'Setting zoom to {caller}')
        self._blockStateChanged = True
        # state = copy.deepcopy(self.state)
        # state.crossSectionScale = val
        # self.set_state(state)
        with self.txn() as s:
            s.crossSectionScale = val

        self._blockStateChanged = False


    # def set_layer(self, index=None):
    def set_layer(self, zpos=None):
        #NotCulpableForFlickerGlitch
        # if self.type != 'EMViewerStage':
        self._blockStateChanged = True
        # if DEV:
        #     logger.critical(f'[{self.role}] [{caller_name()}]\n'
        #                     f'Setting layer:\n'
        #                     f'zpos={zpos},\n'
        #                     f'self.index before={self.index},\n'
        #                     f'voxel coords before={self.state.voxel_coordinates}\n'
        #                     f'...')

        prev_index = self.index

        if self.role == 'ref':
            if zpos:
                self.index=zpos
            else:
                self.index=cfg.data.get_ref_index()
        else:
            if zpos:
                self.index=zpos
            else:
                self.index=cfg.data.zpos




        # if index == None:
        # if self.role == 'ref':
        #     if self.index != cfg.data.get_ref_index():
        #         with self.txn() as s:
        #             vc = s.voxel_coordinates
        #             vc[0] = self.index
        #         self.drawSWIMwindow()

        # if self.index != cfg.data.zpos:
        with self.txn() as s:
            vc = s.voxel_coordinates
            vc[0] = self.index + 0.5

        # if DEV:
        #     logger.info(f'{self.type}:{self.role}  self.index {prev_index} -> {self.index}')

        # state = copy.deepcopy(self.state)
        # state.position[0] = self.index
        # self.set_state(state)
        self.restoreManAlignPts() #Todo study this. Temp fix.

        self.drawSWIMwindow()

        self._blockStateChanged = False

        # else:
        #     self.index = index

        # logger.info('')
        # state = copy.deepcopy(self.state)
        # state.position[0] = index
        # self.set_state(state)



    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()


    def post_message(self, msg):
        with self.config_state.txn() as cs:
            cs.status_messages['message'] = msg


    # async def initViewer(self, obey_zpos=True):
    def initViewer(self, obey_zpos=True):
        # caller = inspect.stack()[1].function
        self._blockStateChanged = False
        if DEV:
            logger.critical(f'Initializing [{self.type}] [role: {self.role}] [caller: {caller_name()}]...')
        # if cfg.data.skipped():
        #     return

        if obey_zpos:
            if self.role == 'ref':
                self.index = cfg.data.get_ref_index()
            elif self.role == 'base':
                self.index = cfg.data.zpos #


        self.clear_layers()
        self.restoreManAlignPts()

        sf = cfg.data.scale_val(s=cfg.data.scale_key)
        path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))

        if not os.path.exists(path):
            cfg.main_window.warn('Data Store Not Found: %s' % path)
            logger.warning('Data Store Not Found: %s' % path); return

        try:
            self.store = get_zarr_tensor(path).result()
            # self.store = await get_zarr_tensor(path)
        except Exception as e:
            cfg.main_window.warn('Unable to Load Data Store at %s' % path)
            raise e

        # logger.critical('Creating Local Volume for %d' %self.index)

        self.LV = ng.LocalVolume(
            volume_type='image',
            # data=self.store[self.index:self.index + 1, :, :],
            data=self.store[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, 0, 0]
        )

        with self.txn() as s:
            s.layout.type = 'yz'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = False
            s.show_axis_lines = False
            s.show_default_annotations = getData('state,show_yellow_frame')
            # s.position=[self.index, self.store.shape[1]/2, self.store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            if getData('state,neutral_contrast'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'
            # s.cross_section_scale = 1 #bug # cant do this
            _, y, x = self.store.shape
            # s.position = [0.5, y / 2, x / 2]
            # s.voxel_coordinates = [self.index, y / 2, x / 2]
            s.voxel_coordinates = [self.index + .5, y / 2, x / 2]
            s.projectionScale = 1

        self.actions.add('add_manpoint', self.add_matchpoint)
        self.actions.add('swim', self.swim)
        # self.actions.add('swim', self.blinkCallback)

        with self.config_state.txn() as s:
            s.input_event_bindings.slice_view['shift+click0'] = 'add_manpoint'
            s.input_event_bindings.viewer['keys'] = 'swim'
            s.show_ui_controls = False
            # s.show_ui_controls = True
            s.show_panel_borders = False


        self.drawSWIMwindow()

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))
            # self.webengine.reload()
            self.webengine.setFocus()

        # self.set_brightness()
        # self.set_contrast()
        # QApplication.processEvents()
        self.drawSWIMwindow()

        self.initZoom()

    # def blickCallback(self):
    #     logger.info('')
    #     pass

    def text(self):
        txt = ''



    def info(self):
        if DEV:
            n_layers = None
            txt = '\n\n'
            try:    txt += f'  caller             = {caller_name()}\n'
            except: txt += f'  caller             =\n'
            txt +=         f'  type/role          = {self.type}/{self.role}\n'
            txt +=         f'  current method     = {cfg.data.current_method}\n'
            try:    txt += f'  _blockStateChanged = {self._blockStateChanged}\n'
            except: txt += f'  _blockStateChanged =\n'
            try:    txt += f'  cfg.data.zpos      = {cfg.data.zpos}\n'
            except: txt += f'  cfg.data.zpos      =\n'
            try:    txt += f'  index              = {self.index}\n'
            except: txt += f'  index              =\n'
            try:    txt += f'  request_layer      = {int(self.state.position[0])}\n'
            except: txt += f'  request_layer      =\n'
            try:    txt += f'  new request_layer  = {int(self.state.voxel_coordinates[0])}\n'
            except: txt += f'  new request_layer  =\n'
            try:    txt += f'  state.voxel_coords = {self.state.voxel_coordinates}\n'
            except: txt += f'  state.voxel_coords =\n'
            try:    txt += f'  state.position     = {self.state.position}\n'
            except: txt += f'  state.position     =\n'
            txt += '\n'
            try:
                n_layers = len(cfg.baseViewer.state.to_json()['layers'])
                txt += f"  {n_layers} Layers\n"
            except:
                txt += f'   0 Layers\n'
            if n_layers:
                for i in range(n_layers):
                    txt += f"  Layer {i}:\n"
                    name = cfg.baseViewer.state.to_json()['layers'][i]['name']
                    txt += f"    Name: {name}\n"
                    type = cfg.baseViewer.state.to_json()['layers'][i]['type']
                    txt += f"    Type: {type}\n"
                    if type == 'annotation':
                        n_ann = len(cfg.baseViewer.state.to_json()['layers'][i]['annotations'])
                        txt += f"    # annotations: {n_ann}\n"
                        ids = [cfg.baseViewer.state.to_json()['layers'][i]['annotations'][x]['id'] for x in range(n_ann)]
                        txt += '    ids : '
                        txt += ', '.join(ids)
                        txt += '\n'
                        try:
                            txt += '    Example: ' + str(cfg.baseViewer.state.to_json()['layers'][i]['annotations'][0]) + '\n'
                        except:
                            pass

        return txt

    @Slot()
    def on_state_changed_any(self):



        # self.post_message(f"Voxel Coordinates: {str(self.state.voxel_coordinates)}")
        if self._blockStateChanged:
            return

        if cfg.data.scale_val() > 2:
            if self.state.relative_display_scales == None:
                self.set_zmag()



        caller = inspect.stack()[1].function
        # logger.info(f'on_state_changed_any [{self.type}] [i={self._zmag_set}] >>>>')
        # logger.info(f'{self.type}:{self.role} self.cs_scale = {self.cs_scale}, self.state.cross_section_scale = {self.state.cross_section_scale}')

        # if not self.cs_scale:
        #     if self.state.cross_section_scale < .001:
        #         self.cs_scale = self.state.cross_section_scale

        # if self.state.relativeDisplayScales == None:
        #     logger.info("setting Zmag!")
        #     self._set_zmag()

        self.signals.stateChanged.emit()


    @Slot()
    def on_state_changed(self):
        # if 1:
        #     return

        if self._blockStateChanged:
            return

        if self.role == 'base':
            if cfg.data['state']['tra_ref_toggle'] != 1:
                return

        elif self.role == 'ref':
            if cfg.data['state']['tra_ref_toggle'] != 0:
                return

        # logger.info('')
        # logger.info(f"[{self.role}], tra_ref_toggle = {cfg.data['state']['tra_ref_toggle']}, _blockStateChanged = {self._blockStateChanged}")

        self._blockStateChanged = True

        # logger.info('>>>> on_state_changed >>>>')

        # self._blockStateChanged = True
        # if not self.cs_scale:
        #     if self.state.cross_section_scale:
        #         if self.state.cross_section_scale > .0001:
        #             logger.info('perfect cs_scale captured! - %.3f' % self.state.cross_section_scale)
        #             self.cs_scale = self.state.cross_section_scale
        #
        # zoom = self.state.cross_section_scale
        # if zoom:
        #     if zoom != self._crossSectionScale:
        #         logger.info(f' (!) emitting zoomChanged (state.cross_section_scale): {zoom:.3f}...')
        #         self.signals.zoomChanged.emit(zoom)
        #     self._crossSectionScale = zoom
        #
        # self._blockStateChanged = False

        # request_layer = int(math.floor(self.state.voxel_coordinates[0]))
        # request_layer = int(self.state.voxel_coordinates[0])

        request_layer = int(self.state.position[0])

        # if DEV:
        #     logger.critical(self.info())


        # if self.role == 'ref':
        #     # if int(math.floor(self.state.voxel_coordinates[0])) != self.index:
        #     if request_layer != self.index:
        #         cfg.pt.setRbTransforming()
        #     return

        if self.role == 'ref':
            if request_layer == self.index:
                self._blockStateChanged = False
                return
            else:
                self.signals.zposChanged.emit()
                self._blockStateChanged = False
                return


        if self.index == request_layer:
            self._blockStateChanged = False
            return

        # request_layer = int(self.state.position[0])
        # request_layer = int(self.state.position[0])

        # logger.critical(f"\n\n\n{self.role}\n  cfg.data.zpos={cfg.data.zpos}\n  request_layer={request_layer}\n  cfg.data.get_ref_index()={cfg.data.get_ref_index()}\n\n")

        # if self.role == 'base':
        #     if request_layer == cfg.data.zpos:
        #         return
        # elif self.role == 'ref':
        #     if request_layer == cfg.data.get_ref_index():
        #         return

        self.index = request_layer

        # if self.role == 'ref':
        #     if request_layer != cfg.data.get_ref_index():
        #         with self.txn() as s:
        #             # logger.info('Sorry!')
        #             vc = s.voxel_coordinates
        #             vc[0] = cfg.data.get_ref_index()
        #     # if not cfg.pt.MA_webengine_ref.isVisible():
        #     #     logger.warning('MA_webengine_ref is NOT visible... canceling state changed callback...')
        #     return
        # if self.role == 'base':
        #     if not cfg.pt.MA_webengine_base.isVisible():
        #         # logger.warning('MA_webengine_base is NOT visible... canceling state changed callback...')
        #         return

        # self.drawSWIMwindow()

        cfg.data.zpos = self.index
        # cfg.mw.setZpos(request_layer)
        logger.info(f'{self.role}: Emitting z-index changed!')
        # self.signals.zposChanged.emit(request_layer)
        self.signals.zposChanged.emit()

        # if isinstance(self.state.position, np.ndarray):
        #     request_layer = int(self.state.position[0])
        #     # ConfirmedOkay
        #     # logger.info(f'  request_layer = {request_layer} // self._layer = {self._layer}')
        #     if request_layer == self._layer:
        #         logger.debug(f'{self.type} state changed, but z-index did not change. '
        #                      f'The callback to update UI was surpressed.')
        #     else:
        #         self._layer = request_layer
        #         cfg.data.zpos = request_layer
        #         # cfg.mw.setZpos(request_layer)
        #         self.signals.stateChanged.emit(request_layer)

        # try:
        #     # print('requested layer: %s' % str(self.state.position[0]))
        #     # get_loc = floor(self.state.position[0])
        #     if isinstance(self.state.position, np.ndarray):
        #         request_layer = int(self.state.position[0])
        #         if cfg.data.zpos != request_layer:
        #             logger.critical(f'  request_layer = {request_layer} // self._layer = {self._layer} // cfg.data.zpos = {cfg.data.zpos}')
        #
        #             # cfg.data.zpos = request_layer
        #             cfg.mw.setZpos(request_layer)
        #             self.signals.stateChanged.emit(request_layer)
        # except:
        #     print_exception()

        # logger.info('  > continuing past <lambda> check...')
        # logger.info(f'self.state.position[0]          = {self.state.position[0]}')
        # logger.info(f'self.state.voxel_coordinates[0] = {self.state.voxel_coordinates[0]}')

        # if isinstance(self.state.position, np.ndarray):
        #     # request_layer = int(self.state.position[0])
        #     request_layer = int(self.state.position[0])
        #     logger.critical(f'request_layer: {request_layer}')
        #     logger.critical(f'self._layer: {self._layer}')
        #     # ConfirmedOkay
        #     # logger.info(f'  request_layer = {request_layer} // self._layer = {self._layer}')
        #     if request_layer == self._layer:
        #         logger.info(f'{self.type}:{self.role} state changed, but z-index did not change. '
        #                     f'The callback to update UI was surpressed.')
        #     else:
        #         self._layer = request_layer
        #         cfg.mw.setZpos(request_layer)
        #         # self._inSync = 1 #Critical!

                # self.signals.stateChanged.emit()

        self._blockStateChanged = False

        logger.info('<<<< on_state_changed <<<<')





    def pt2ann(self, points: list):
        annotations = []
        lineweight = cfg.main_window.mp_marker_lineweight_spinbox.value()
        size = cfg.main_window.mp_marker_size_spinbox.value()
        for i, point in enumerate(points):
            annotations.append(ng.PointAnnotation(id=repr(point),
                                                  point=point,
                                                  props=[self.colors[i % 3],
                                                         size,
                                                         lineweight]))
        self.annotations = annotations
        return annotations



    # def undrawAnnotations(self):
    #     try:
    #         with self.txn() as s:
    #             s.layers['ann'].annotations = None
    #     except:
    #         logger.warning('Unable to undraw annotations')


    def getNextUnusedColor(self):
        return self.colors[len(self.pts)]
        # for c in self.colors:
        #     if c in self.pts:
        #         continue
        #     else:
        #         return c


    def url(self):
        return self.get_viewer_url()


    def clear_layers(self):
        if self.state.layers:
            logger.info('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)

    def swim(self, s):
        logger.info('Running SWIM...')
        # cfg.main_window.alignOne()
        self.signals.swimAction.emit()



    def add_matchpoint(self, s):
        logger.info('')
        if cfg.data.method() not in ('manual-strict', 'manual-hint'):
            logger.warning('add_matchpoint: User may not select points while aligning with grid.')
            return

        # if not cfg.project_tab.isManualReady():
        #     return

        if self.role == 'ref':
            if len(cfg.data.manpoints()['ref']) >= 3:
                cfg.mw.warn('Three points have already been selected for the reference section!')
                return
        elif self.role == 'base':
            if len(cfg.data.manpoints()['base']) >= 3:
                cfg.mw.warn('Three points have already been selected for the transforming section!')
                return


        logger.info('Adding Manual Points to Buffer...')

        coords = np.array(s.mouse_voxel_coordinates)
        logger.info('Coordinates: %s' %str(coords))
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless! =%s' % str(coords))
            return
        _, y, x = s.mouse_voxel_coordinates
        # z = 0.1
        # z = 0.5
        z = self.index

        props = [self.colors[len(self.pts)],
                 getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                 getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
        # self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=repr((z,y,x)), point=(z,y,x), props=props)
        self.pts.append(ng.PointAnnotation(id=repr((z,y,x)), point=(z,y,x), props=props))

        self.applyMps()
        self.signals.ptsChanged.emit()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))
        # self.drawSWIMwindow()
        logger.info(f'dict = {cfg.data.manpoints_pretty()}')




    def applyMps(self):
        '''Copy local manual points into project dictionary'''
        # self._blockStateChanged = True
        logger.info(f'Storing Manual Points for {self.role}...')
        cfg.main_window.statusBar.showMessage('Manual Correspondence Points Stored!', 3000)
        pts = []
        # for key in self.pts.keys():
        #     p = self.pts[key]
        #     _, x, y = p.point.tolist()
        #     pts.append((x, y))
        for p in self.pts:
            _, x, y = p.point.tolist()
            pts.append((x, y))
        cfg.data.set_manpoints(self.role, pts)
        # cfg.data.set_manual_points_color(self.role, pts)
        # cfg.data.print_all_manpoints()
        # self._blockStateChanged = False


    def draw_point_annotations(self):
        logger.info('Drawing point annotations...')
        # logger.info(self.pts.values())
        try:
            # anns = list(self.pts.values())
            anns = self.pts
            if anns:
                with self.txn() as s:
                    s.layers['ann_points'].annotations = anns
        except:
            # print_exception()
            logger.warning('Unable to draw donut annotations or none to draw')
        # pass



    def undrawSWIMwindows(self):
        # caller = inspect.stack()[1].function
        # logger.info(f"[{self.role}] caller: {caller_name()}] Undrawing SWIM windows...")

        # with cfg.refViewer.txn() as s:
        #     print(s.layers['SWIM'].annotations)
        try:
            with self.txn() as s:
                if s.layers['SWIM']:
                    if 'annotations' in s.layers['SWIM'].to_json().keys():
                        s.layers['SWIM'].annotations = None
        except:
            logger.warning('Something went wrong while undrawing SWIM windows')
            print_exception()



    # @functools.cache
    def drawSWIMwindow(self):

        if self._dontDraw:
            logger.info('_dontDraw is blocking drawSWIMwindow')
            return

        # if self.role == 'ref':
        #     if cfg.pt.sw_alignment_editor.currentIndex() != 0:
        #         return
        # if self.role == 'base':
        #     if cfg.pt.sw_alignment_editor.currentIndex() != 1:
        #         return



        self._blockStateChanged = True
        # caller = inspect.stack()[1].function

        # self.undrawSWIMwindows() #todo try without this! #todo try doing this closer to redraw

        if cfg.data.zpos == cfg.data.first_unskipped():
            return



        marker_size = 1

        # if self.role == 'ref':
        #     self.index = cfg.data.get_ref_index()
        # elif self.role == 'base':
        #     self.index = cfg.data.zpos  #

        # if DEV:
        #     logger.critical(f'[{self.role}] caller: {caller_name()} index: {self.index} cfg.data.zpos: {cfg.data.zpos}')

        # if cfg.data.current_method == 'manual-hint':
        #     self.draw_point_annotations()
        #     return
        #


        if cfg.data.current_method == 'grid-custom':
            logger.info('Type: Custom Grid Alignment...')

            img_siz = cfg.data.image_size()
            img_w, img_h = img_siz[0], img_siz[1]
            ww_full = cfg.data.swim_1x1_custom_px() # full window width
            ww_2x2 = cfg.data.swim_2x2_custom_px() # 2x2 window width

            offset_x1 = ((img_w - ww_full[0]) / 2) + (ww_2x2[0] / 2)
            offset_x2 = img_w - offset_x1
            offset_y1 = ((img_h - ww_full[1]) / 2) + (ww_2x2[1] / 2)
            offset_y2 = img_h - offset_y1

            cps = []
            colors = []
            regions = cfg.data.grid_custom_regions
            # logger.info(f'regions: {regions}')
            if regions[0]:
                # quadrant 1
                cps.append((offset_x2, offset_y1))
                colors.append(self.colors[0])
            if regions[1]:
                # quadrant 2
                cps.append((offset_x1, offset_y1))
                colors.append(self.colors[1])
            if regions[2]:
                # quadrant 3
                cps.append((offset_x2, offset_y2))
                colors.append(self.colors[2])
            if regions[3]:
                # quadrant 4
                cps.append((offset_x1, offset_y2))
                colors.append(self.colors[3])

            annotations = []
            for i, pt in enumerate(cps):
                # if regions[i]:
                annotations.extend(
                    self.makeRect(
                        prefix=str(i),
                        z_index=self.index,
                        coords=pt,
                        ww_x=ww_2x2[0] - 4,
                        ww_y=ww_2x2[1] - 4,
                        color=colors[i],
                        marker_size=marker_size
                    )
                )

        elif cfg.data.current_method == 'grid-default':
            # logger.info('Type: Default Grid Alignment...')

            img_siz = cfg.data.image_size()
            img_w, img_h = img_siz[0], img_siz[1]
            # ww_full = cfg.data.stack()[cfg.data.zpos]['alignment']['swim_settings']['default_auto_swim_window_px']
            ww_full = cfg.data['data']['defaults'][cfg.data.scale_key]['swim-window-px']

            offset_x1 = (img_w / 2) - (ww_full[0] * (1 / 4))
            offset_x2 = (img_w / 2) + (ww_full[0] * (1 / 4))
            offset_y1 = (img_h / 2) - (ww_full[1] * (1 / 4))
            offset_y2 = (img_h / 2) + (ww_full[1] * (1 / 4))

            # ww_2x2 = cfg.data.swim_2x2_custom_px() # 2x2 window width
            # offset_x1 = ((img_w - ww_full[0]) / 2) + (ww_2x2[0] / 2)
            # offset_x2 = img_w - offset_x1
            # offset_y1 = ((img_h - ww_full[1]) / 2) + (ww_2x2[1] / 2)
            # offset_y2 = img_h - offset_y1

            cps = []
            colors = []
            regions = [1,1,1,1]
            # logger.info(f'regions: {regions}')
            if regions[0]:
                # quadrant 1
                cps.append((offset_x2, offset_y1))
                colors.append(self.colors[0])
            if regions[1]:
                # quadrant 2
                cps.append((offset_x1, offset_y1))
                colors.append(self.colors[1])
            if regions[2]:
                # quadrant 3
                cps.append((offset_x2, offset_y2))
                colors.append(self.colors[2])
            if regions[3]:
                # quadrant 4
                cps.append((offset_x1, offset_y2))
                colors.append(self.colors[3])

            annotations = []
            for i, pt in enumerate(cps):
                if regions[i]:
                    annotations.extend(
                        self.makeRect(
                            prefix=str(i),
                            z_index=self.index,
                            coords=pt,
                            ww_x=(ww_full[0] / 2) - 4,
                            ww_y=(ww_full[1] / 2) - 4,
                            color=colors[i],
                            marker_size=marker_size
                        )
                    )

        else:
            logger.info('Type: Match Region...')
            # pts = list(self.pts.items())
            try:
                assert len(self.pts) == len(cfg.data.manpoints()[self.role])
            except:
                logger.warning(f'len(self.pts) = {len(self.pts)}, len(cfg.data.manpoints()[self.role]) = {len(cfg.data.manpoints()[self.role])}')
            annotations = []
            if cfg.data.current_method == 'manual-strict':
                ww_x = 16
                ww_y = 16
            else:
                ww_x = ww_y = cfg.data.manual_swim_window_px()

            for i, pt in enumerate(self.pts):
                annotations.extend(
                    self.makeRect(
                        prefix=str(i),
                        z_index=self.index,
                        coords=(pt.point[2], pt.point[1]),
                        ww_x=ww_x,
                        ww_y=ww_y,
                        color=cfg.glob_colors[i],
                        marker_size=marker_size
                    )
                )

        # self.undrawSWIMwindows()
        with self.txn() as s:
            # for i,ann in enumerate(annotations):
            s.layers['SWIM'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='color', type='rgb', default='#ffff66', ),
                    # ng.AnnotationPropertySpec(id='size', cur_method='float32', default=1, )
                    ng.AnnotationPropertySpec(id='size', type='float32', default=5, )
                ],
                annotations=annotations,
                shader='''
                    void main() {
                      setColor(prop_color());
                      setPointMarkerSize(prop_size());
                    }
                ''',
            )
        self._blockStateChanged = False
        # QApplication.processEvents()

    # @cache
    def makeRect(self, prefix, z_index, coords, ww_x, ww_y, color, marker_size):
        segments = []
        x, y = coords[0], coords[1]
        hw = int(ww_x / 2) # Half-width
        hh = int(ww_y / 2) # Half-height
        A = (z_index + 0.5, y + hh, x - hw)
        B = (z_index + 0.5, y + hh, x + hw)
        C = (z_index + 0.5, y - hh, x + hw)
        D = (z_index + 0.5, y - hh, x - hw)

        segments.append(ng.LineAnnotation(id=prefix + '_L1', pointA=A, pointB=B, props=[color, marker_size]))
        segments.append(ng.LineAnnotation(id=prefix + '_L2', pointA=B, pointB=C, props=[color, marker_size]))
        segments.append(ng.LineAnnotation(id=prefix + '_L3', pointA=C, pointB=D, props=[color, marker_size]))
        segments.append(ng.LineAnnotation(id=prefix + '_L4', pointA=D, pointB=A, props=[color, marker_size]))
        return segments


    def restoreManAlignPts(self):

        # self.pts = OrderedDict()
        self.pts = []
        pts_data = cfg.data.getmpFlat(l=cfg.data.zpos)[self.role]
        if pts_data:
            logger.info(f'[{self.role}] Restoring manual point/region selections...')
            for i, p in enumerate(pts_data):
                props = [self.colors[i],
                         getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                         getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
                # self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=str(p), point=p, props=props)
                self.pts.append(ng.PointAnnotation(id=str(p), point=p, props=props))

            # logger.critical(f'pts:\n{self.pts}')
            # json_str = self.state.layers.to_json()
            # logger.critical('--------------')
            # logger.critical(json_str[0]['annotations'])


    def set_brightness(self, val=None):
        logger.info('')
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['brightness'] = val
            else:   layer.shaderControls['brightness'] = cfg.data.brightness
            # layer.volumeRendering = True
        self.set_state(state)

    def set_contrast(self, val=None):
        logger.info('')
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['contrast'] = val
            else:   layer.shaderControls['contrast'] = cfg.data.contrast
            # layer.volumeRendering = True
        self.set_state(state)

    def set_zmag(self, val=10):
        self._blockStateChanged = True
        # logger.info(f'zpos={cfg.data.zpos} Setting Z-mag on {self.type} to {val} [{self.role}]')
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            state = copy.deepcopy(self.state)
            state.relativeDisplayScales = {'z': 2}
            self.set_state(state)
        except:
            logger.warning('Unable to set Z-mag')
            print_exception()
        self._blockStateChanged = False


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

    def initZoom(self):
        logger.info(f'[{caller_name()}] [{self.role}] Calling initZoom...')
        adjust = 1.12
        # logger.critical(f'[{self.role}] self.cs_scale = {self.cs_scale}')
        if self.cs_scale:
            logger.critical(f'[{self.role}] Initializing crossSectionScale to self.cs_scale ({self.cs_scale}) [{self.role}]')
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:
            # QApplication.processEvents()
            # _, tensor_y, tensor_x = cfg.tensor.shape
            _, tensor_y, tensor_x = self.store.shape
            # widget_w = cfg.mw.geometry().width()
            # widget_h = cfg.mw.geometry().height() / 2
            if cfg.project_tab:
                widget_w = cfg.project_tab.ng_widget.width()
                widget_h = cfg.project_tab.ng_widget.height()
            else:
                widget_w = widget_h = cfg.mw.globTabs.height() - 30


            # logger.critical(f'[{self.role}] widget_w = {widget_w}, widget_h = {widget_h}')

            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale_key) # nm per imagepixel
            # tissue_h, tissue_w = res_y*frame[0], res_x*frame[1]  # nm of sample
            scale_h = ((res_y * tensor_y) / widget_h) * 1e-9  # nm/pixel (subtract height of ng toolbar)
            scale_w = ((res_x * tensor_x) / widget_w) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)

            # logger.critical(f'Setting crossSectionScale to max of {scale_h} and {scale_w}...')

            # logger.critical(f'________{self.role}________')
            # logger.critical(f'widget_w       = {widget_w}')
            # logger.critical(f'widget_h       = {widget_h}')
            # logger.critical(f'tensor_x       = {tensor_x}')
            # logger.critical(f'tensor_y       = {tensor_y}')
            # logger.critical(f'res_x          = {res_x}')
            # logger.critical(f'res_y          = {res_y}')
            # logger.critical(f'scale_h        = {scale_h}')
            # logger.critical(f'scale_w        = {scale_w}')
            # logger.critical(f'cfg.data.scale_key = {cfg.data.scale_key}')
            # logger.critical(f'cs_scale       = {cs_scale}')

            # logger.info(f'Initializing crossSectionScale to calculated value times adjust {self.cs_scale} [{self.role}]')
            with self.txn() as s:
                # s.crossSectionScale = cs_scale * 1.20
                s.crossSectionScale = cs_scale * adjust



if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    viewer = MAViewer()
    viewer.initViewer()


    '''
        box = ng.AxisAlignedBoundingBoxAnnotation(
            point_a=[.5, 50, 50],
            point_b=[.5, 500, 500],
            id="bounding-box",
        )
        s.layers['bounding-box'] = ng.LocalAnnotationLayer(
            dimensions=self.coordinate_space,
            annotations=[box])
    
    A____AB_____B
    |           |
    DA   CP    BC
    |           |
    D____CD_____C 
    
    # logger.critical(f'A: {A}')
    # logger.critical(f'B: {B}')
    # logger.critical(f'C: {C}')
    # logger.critical(f'D: {D}')
    #
    # logger.critical(f'AB: {AB}')
    # logger.critical(f'BC: {BC}')
    # logger.critical(f'CD: {CD}')
    # logger.critical(f'DA: {DA}')
    #
    # logger.critical(f'half_w = {half_w}')
    # logger.critical(f'half_h = {half_h}')
    # logger.critical(f'offset_w = {offset_w}')
    # logger.critical(f'offset_h = {offset_h}')
    # logger.critical(f'siz_sw = {siz_sw}')
    # logger.critical(f'siz_sh = {siz_sh}')

    11:46:55 [viewer_ma.drawSWIMwindow:442] A: [0.5, 720.0, 96.0]
    11:46:55 [viewer_ma.drawSWIMwindow:443] B: [0.5, 304.0, 96.0]
    11:46:55 [viewer_ma.drawSWIMwindow:444] C: [0.5, 304.0, 928.0]
    11:46:55 [viewer_ma.drawSWIMwindow:445] D: [0.5, 720.0, 928.0]
    11:46:55 [viewer_ma.drawSWIMwindow:447] AB: [0.5, 256.0, 96.0]
    11:46:55 [viewer_ma.drawSWIMwindow:448] BC: [0.5, 304.0, 512.0]
    11:46:55 [viewer_ma.drawSWIMwindow:449] CD: [0.5, 256.0, 928.0]
    11:46:55 [viewer_ma.drawSWIMwindow:450] DA: [0.5, 720.0, 512.0]
    11:46:55 [viewer_ma.drawSWIMwindow:452] half_w = 512.0
    11:46:55 [viewer_ma.drawSWIMwindow:453] half_h = 256.0
    '''