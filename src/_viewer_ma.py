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
import sys
import time
from collections import OrderedDict
from functools import cache
from math import floor
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, Slot, QUrl
from qtpy.QtWidgets import QApplication
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, print_exception, is_joel, is_tacc, caller_name, dt
import src.config as cfg

import tensorstore as ts
context = ts.Context({'cache_pool': {'total_bytes_limit': 1000000000}})

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['MAViewer']

logger = logging.getLogger(__name__)
# logger.propagate = False


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    zVoxelCoordChanged = Signal(int)
    zoomChanged = Signal(float)
    mpUpdate = Signal()
    ptsChanged = Signal()
    swimAction = Signal()
    badStateChange = Signal()
    toggleView = Signal()
    tellMainwindow = Signal(str)
    warnMainwindow = Signal(str)
    errMainwindow = Signal(str)
    arrowLeft = Signal()
    arrowRight = Signal()
    arrowUp = Signal()
    arrowDown = Signal()

class MAViewer(neuroglancer.Viewer):
    # def __init__(self, parent, dm, role='tra', quality=None, webengine0=None):
    def __init__(self, parent, dm, webengine=None):
        super().__init__()
        self.parent = parent
        self.dm = dm
        self.index = None
        self.role = 'tra'
        self.type = 'MAViewer'
        self.created = datetime.datetime.now()
        self.signals = WorkerSignals()
        self.webengine = webengine
        self.webengine.setMouseTracking(True)
        self._blockStateChanged = False
        self.cs_scale = None
        self.colors = cfg.glob_colors
        self._mkr_size = 1
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        self.signals.ptsChanged.connect(self.drawSWIMwindow)

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(self.dm.resolution()), )

        self.initViewer()
        # asyncio.ensure_future(self.initViewer())
        # self.webengine.setFocus()


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


    def updateUIControls(self):
        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,neuroglancer_show_controls')


    def n_annotations(self):
        return len(self.state.layers['ann_points'].annotations)


    def position(self):
        return copy.deepcopy(self.state.position)

    def set_position(self, val):
        with self.txn() as s:
            s.position = val

    def zoom(self):
        return copy.deepcopy(self.state.crossSectionScale)

    def set_zoom(self, val):
        caller = inspect.stack()[1].function
        logger.info(f'Setting zoom to {caller}')
        self._blockStateChanged = True
        with self.txn() as s:
            s.crossSectionScale = val
        self._blockStateChanged = False

    # def set_layer(self, index=None):
    def set_layer(self, zpos=None):
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Setting layer (zpos={zpos})...")
        self._blockStateChanged = True

        if self.role == 'ref':
            if zpos:
                self.index=zpos
            else:
                self.index=self.dm.get_ref_index()
        else:
            if zpos:
                self.index=zpos
            else:
                self.index=self.dm.zpos

        try:
            with self.txn() as s:
                vc = s.voxel_coordinates
                vc[0] = self.index + 0.5
        except:
            print_exception()

        self.drawSWIMwindow()

        self._blockStateChanged = False


    def post_message(self, msg):
        with self.config_state.txn() as s:
            s.status_messages['message'] = msg


    # async def initViewer(self, obey_zpos=True):
    def initViewer(self):
        t0 = time.time()
        # caller = inspect.stack()[1].function
        self._blockStateChanged = True #Critical #Always

        if self.role == 'ref':
            self.index = self.dm.get_ref_index()
        elif self.role == 'tra':
            self.index = self.dm.zpos #

        # self.clear_layers()

        path = os.path.join(self.dm['info']['images_location'], 'zarr', self.dm.level)

        if not os.path.exists(path):
            logger.warning('Data Store Not Found: %s' % path); return

        try:
            self.store = self.tensor = get_zarr_tensor(path).result()
        except Exception as e:
            logger.error('Unable to Load Data Store at %s' % path)
            raise e

        self.LV = ng.LocalVolume(
            volume_type='image',
            data=self.store[:, :, :],
            dimensions=self.coordinate_space,
            voxel_offset=[0, 0, 0],
            downsampling='3d',
            max_downsampling=cfg.max_downsampling,
            max_downsampled_size=cfg.max_downsampled_size
            # max_downsampling_scales=cfg.max_downsampling_scales  # a LOT slower when set to 1
        )

        with self.txn() as s:
            s.layout.type = 'yz'
            # s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            # level.show_scale_bar = False
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.projectionScale = 1
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=self.dm['rendering']['shader'], )
            _, y, x = self.store.shape
            s.voxel_coordinates = [self.index + .5, y / 2, x / 2]
            s.show_default_annotations = False

        # self.actions.add('add_manpoint', self.add_matchpoint)
        self.actions.add('keyLeft', self._onKeyLeft)
        self.actions.add('keyRight', self._onKeyRight)
        self.actions.add('keyUp', self._onKeyUp)
        self.actions.add('keyDown', self._onKeyDown)
        self.actions.add('key1', self._onKey1)
        self.actions.add('key2', self._onKey2)
        self.actions.add('key3', self._onKey3)
        self.actions.add('keySpace', self._onKeySpace)
        self.actions.add('controlClick', self._onControlClick)
        # self.actions.add('swim', self.swim)

        # self.actions.add('swim', self.blinkCallback)

        with self.config_state.txn() as s:
            s.input_event_bindings.slice_view['arrowleft'] = 'keyLeft'
            s.input_event_bindings.slice_view['arrowright'] = 'keyRight'
            s.input_event_bindings.slice_view['arrowup'] = 'keyUp'
            s.input_event_bindings.slice_view['arrowdown'] = 'keyDown'
            # s.input_event_bindings.slice_view['alt+click0'] = 'add_manpoint'
            # s.input_event_bindings.viewer['control+click0'] = 'add_manpoint'
            # s.input_event_bindings.slice_view['keys'] = 'add_manpoint'
            # s.input_event_bindings.slice_view['dblclick0'] = 'add_manpoint'
            s.input_event_bindings.slice_view['digit1'] = 'key1'
            s.input_event_bindings.slice_view['digit2'] = 'key2'
            s.input_event_bindings.slice_view['digit3'] = 'key3'
            s.input_event_bindings.slice_view['space'] = 'keySpace'

            # s.input_event_bindings.viewer['control+mousedown0'] = 'controlClick'
            # s.input_event_bindings.viewer['control+click0'] = 'controlClick'
            # s.input_event_bindings.viewer['at:control+mousedown0'] = 'controlClick'
            s.input_event_bindings.viewer['control+click'] = 'controlClick'
            # s.input_event_bindings.slice_view['shift+click0'] = 'add_manpoint'
            # s.input_event_bindings.slice_view['enter'] = 'add_manpoint'            #this works
            # s.input_event_bindings.slice_view['mousedown0'] = 'add_manpoint'       #this works
            # s.input_event_bindings.slice_view['at:control+mousedown0'] = 'add_manpoint'
            # s.input_event_bindings.viewer['keys'] = 'swim'
            s.show_ui_controls = False
            # s.show_ui_controls = True
            s.show_panel_borders = False
            s.show_help_button = True
            s.show_layer_panel = False
            # s.scale_bar_options.padding_in_pixels = 0  # default = 8
            # s.scale_bar_options.left_pixel_offset = 10  # default = 10
            # s.scale_bar_options.bottom_pixel_offset = 10  # default = 10
            # s.scale_bar_options.bar_top_margin_in_pixels = 4  # default = 5
            # s.scale_bar_options.font_name = 'monospace'
            # s.scale_bar_options.font_name = 'serif'

        self.setBackground()
        self.drawSWIMwindow()


        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))
            self.webengine.setFocus()

        self.initZoom()

        self._blockStateChanged = False

        logger.info(f"\ntimings: {t1-t0:.3g}/{t2 - t0:.3g}/{t3 - t0:.3g}/{t4 - t0:.3g}/{t5 - t0:.3g}/{t6 - t0:.3g}/{t7 - t0:.3g}")

    # def blickCallback(self):
    #     logger.info('')
    #     pass

    def text(self):
        txt = ''


    @Slot()
    def on_state_changed(self):
        # logger.info(f'[{self.role}]')
        # logger.info(f"[{self.role}], tra_ref_toggle = {self.dm['state']['tra_ref_toggle']}, _blockStateChanged = {self._blockStateChanged}")

        if self._blockStateChanged:
            return

        try:
            assert hasattr(self,'index')
        except AssertionError:
            logger.warning('State changed too early! Index not set.')
            return

        # logger.info('state changed!')
        # logger.info('')

        self._blockStateChanged = True

        if self.state.cross_section_scale:
            val = (self.state.cross_section_scale, self.state.cross_section_scale * 250000000)[
                self.state.cross_section_scale < .001]
            if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                if getData('state,neuroglancer,zoom') != val:
                    logger.info(f'emitting zoomChanged! val = {val:.4f}')
                    setData('state,neuroglancer,zoom', val)
                    self.signals.zoomChanged.emit(val)

        try:
            if self.role == 'ref':
                if floor(self.state.position[0]) != self.index:
                    logger.warning(f"[{self.role}] Illegal state change")
                    self.signals.badStateChange.emit() #New
                    return

            elif self.role == 'tra':
                if floor(self.state.position[0]) != self.index:
                    self.index = floor(self.state.position[0])
                    self.drawSWIMwindow(z=self.index) #NeedThis #0803
                    # self.dm.zpos = self.index
                    self.signals.zVoxelCoordChanged.emit(self.index)
        except:
            print_exception()
        self._blockStateChanged = False

    def url(self):
        return self.get_viewer_url()


    def clear_layers(self):
        if self.state.layers:
            logger.info('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)


    def swim(self, s):
        logger.info('[futures] Emitting SWIM signal...')
        self.signals.swimAction.emit()

    def _onKey1(self, s):
        logger.info('')
        self.add_matchpoint(s, id=0, ignore_pointer=True)
        self.webengine.setFocus()


    def _onKey2(self, s):
        logger.info('')
        self.add_matchpoint(s, id=1, ignore_pointer=True)
        self.webengine.setFocus()


    def _onKey3(self, s):
        logger.info('')
        self.add_matchpoint(s, id=2, ignore_pointer=True)
        self.webengine.setFocus()


    def _onKeySpace(self, s):
        logger.info("Native spacebar keybinding intercepted!")
        # if self.dm.method() == 'manual':
        self.signals.toggleView.emit()
        self.webengine.setFocus()

    def _onKeyLeft(self, s):
        logger.warning("Native arrow LEFT keybinding intercepted!")
        self.signals.arrowLeft.emit()
        self.webengine.setFocus()


    def _onKeyRight(self, s):
        logger.warning("Native arrow RIGHT keybinding intercepted!")
        self.signals.arrowRight.emit()
        self.webengine.setFocus()

    def _onKeyUp(self, s):
        logger.warning("Native arrow UP keybinding intercepted!")
        self.signals.arrowUp.emit()
        self.webengine.setFocus()

    def _onKeyDown(self, s):
        logger.warning("Native arrow DOWN keybinding intercepted!")
        self.signals.arrowDown.emit()
        self.webengine.setFocus()

    def _onControlClick(self, s):
        logger.info("Native control+click keybinding intercepted!")
        self.webengine.setFocus()

    def add_matchpoint(self, s, id, ignore_pointer=False):
        if self.dm.method() != 'manual':
            return
        print('\n\n--> add_matchpoint -->\n')
        coords = np.array(s.mouse_voxel_coordinates)
        if coords.ndim == 0:
            logger.warning(f'Null coordinates! ({coords})')
            return
        _, y, x = s.mouse_voxel_coordinates
        frac_y = y / self.store.shape[1]
        frac_x = x / self.store.shape[2]
        logger.critical(f"frac_x = {frac_x}, frac_y = {frac_y}")
        self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][self.role][
            id] = (frac_x, frac_y)
        self.signals.ptsChanged.emit()
        self.drawSWIMwindow()


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


    def undrawSWIMwindows(self):
        try:
            with self.txn() as s:
                if s.layers['SWIM']:
                    if 'annotations' in s.layers['SWIM'].to_json().keys():
                        s.layers['SWIM'].annotations = None
        except:
            print_exception()


    # @functools.cache
    def drawSWIMwindow(self, z=None):
        caller = inspect.stack()[1].function
        logger.critical(f"\n\n[{caller}] Drawing SWIM windows...\n")
        if z == None:
            z = self.dm.zpos
        # if z == self.dm.first_included(): #1025-
        #     return

        self._blockStateChanged = True
        # self.setMpData() #0805+
        # self.undrawSWIMwindows()
        ms = self._mkr_size
        # fac = self.dm.lvl() / self.quality_lvl
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
            z = self.index + 0.5
            for i, pt in enumerate(cps):
                clr = colors[i]
                a, b, c, d = self.getRect2(pt, ww_x, ww_y)
                annotations.extend([
                    ng.LineAnnotation(id=str(i) + '_L1', pointA=(z,) + a, pointB=(z,) + b, props=[clr, ms]),
                    ng.LineAnnotation(id=str(i) + '_L2', pointA=(z,) + b, pointB=(z,) + c, props=[clr, ms]),
                    ng.LineAnnotation(id=str(i) + '_L3', pointA=(z,) + c, pointB=(z,) + d, props=[clr, ms]),
                    ng.LineAnnotation(id=str(i) + '_L4', pointA=(z,) + d, pointB=(z,) + a, props=[clr, ms])
                ])

        elif method == 'manual':
            logger.critical("Restoring...")
            ww_x = ww_y = self.dm.manual_swim_window_px()

            pts = self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][self.role]

            for i, pt in enumerate(pts):
                # 0: (122, None, None)
                logger.critical(f"{i}: {pt}")
                if pt:
                    x = self.store.shape[2] * pt[0]
                    y = self.store.shape[1] * pt[1]
                    a, b, c, d = self.getRect2(coords=(x, y), ww_x=ww_x,ww_y=ww_y,)
                    z = self.index + 0.5
                    clr = self.colors[i]
                    annotations.extend([
                        ng.LineAnnotation(id=str(i) + '_L1', pointA=(z,) + a, pointB=(z,) + b, props=[clr, ms]),
                        ng.LineAnnotation(id=str(i) + '_L2', pointA=(z,) + b, pointB=(z,) + c, props=[clr, ms]),
                        ng.LineAnnotation(id=str(i) + '_L3', pointA=(z,) + c, pointB=(z,) + d, props=[clr, ms]),
                        ng.LineAnnotation(id=str(i) + '_L4', pointA=(z,) + d, pointB=(z,) + a, props=[clr, ms])
                    ])
        # print(f"Adding annotation layers...\n{self.pts}")
        with self.txn() as s:
            s.layers['SWIM'] = ng.LocalAnnotationLayer(
                annotations=annotations,
                dimensions=self.coordinate_space,
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
        self.webengine.setFocus()

    def set_brightness(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['brightness'] = val
            else:   layer.shaderControls['brightness'] = self.dm.brightness
            # layer.volumeRendering = True
        self.set_state(state)


    def set_contrast(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['contrast'] = val
            else:   layer.shaderControls['contrast'] = self.dm.contrast
            # layer.volumeRendering = True
        self.set_state(state)

    def setBackground(self):
        try:
            with self.txn() as s:
                if getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'):
                    s.crossSectionBackgroundColor = getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')
                else:
                    if getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'):
                        # s.crossSectionBackgroundColor = '#222222'
                        s.crossSectionBackgroundColor = '#000000'
                    else:
                        s.crossSectionBackgroundColor = '#808080'
        except:
            print_exception()


    def initZoom(self):
        logger.info(f'[{caller_name()}] [{self.role}] Initializing Zoom...')
        adjust = 1.12
        if self.cs_scale:
            logger.info(f'[{self.role}] Initializing crossSectionScale to self.cs_scale ({self.cs_scale})')
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:
            _, tensor_y, tensor_x = self.store.shape
            w = self.parent.wNg1.width()
            h = self.parent.wNg1.height()
            res_z, res_y, res_x = self.dm.resolution(s=self.dm.level) # nm per imagepixel
            # res_z, res_y, res_x = self.dm.resolution(s=self.quality) # nm per imagepixel
            # tissue_h, tissue_w = res_y*getFrameScale[0], res_x*getFrameScale[1]  # nm of sample
            scale_h = ((res_y * tensor_y) / h) * 1e-9  # nm/pixel (subtract height of ng toolbar)
            scale_w = ((res_x * tensor_x) / w) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)
            # logger.info(f'Initializing crossSectionScale to calculated value times adjust {self._cs_scale} [{self.role}]')
            with self.txn() as s:
                s.crossSectionScale = cs_scale * adjust

    # def pt2ann(self, points: list):
    #     annotations = []
    #     lineweight = cfg.main_window.mp_marker_lineweight_spinbox.value()
    #     size = cfg.main_window.mp_marker_size_spinbox.value()
    #     for i, point in enumerate(points):
    #         annotations.append(ng.PointAnnotation(id=repr(point),
    #                                               point=point,
    #                                               props=[self.colors[i % 3],
    #                                                      size,
    #                                                      lineweight]))
    #     self.annotations = annotations
    #     return annotations

    # def draw_point_annotations(self):
    #     logger.info('Drawing point annotations...')
    #     try:
    #         anns = self.pts[self.role]
    #         if anns:
    #             with self.txn() as s:
    #                 s.layers['ann_points'].annotations = anns
    #     except:
    #         logger.warning('Unable to draw donut annotations or none to draw')

    def info(self):
        n_layers = None
        txt = '\n\n'
        txt += f'  caller             = {caller_name()}\n'
        txt += f'  type/role          = {self.type}/{self.role}\n'
        txt += f'  current method     = {self.dm.current_method}\n'
        txt += f'  _blockStateChanged = {self._blockStateChanged}\n'
        txt += f'  self.dm.zpos       = {self.dm.zpos}\n'
        txt += f'  index              = {self.index}\n'
        try:    txt += f'  state.position     = {self.state.position}\n'
        except: txt += f'  state.position     =\n'
        try:    txt += f'  state.voxel_coordinates  = {self.state.voxel_coordinates}\n'
        except: txt += f'  state.voxel_coordinates  =\n'
        txt += '\n'
        try:
            n_layers = len(self.state.to_json()['layers'])
            txt += f"  {n_layers} Layers\n"
        except:
            txt += f'   0 Layers\n'
        if n_layers:
            for i in range(n_layers):
                txt += f"  Layer {i}:\n"
                name = self.state.to_json()['layers'][i]['name']
                txt += f"    Name: {name}\n"
                type = self.state.to_json()['layers'][i]['type']
                txt += f"    Type: {type}\n"
                if type == 'annotation':
                    n_ann = len(self.state.to_json()['layers'][i]['annotations'])
                    txt += f"    # annotations: {n_ann}\n"
                    ids = [self.state.to_json()['layers'][i]['annotations'][x]['id'] for x in range(n_ann)]
                    txt += '    ids : '
                    txt += ', '.join(ids)
                    txt += '\n'
                    try:
                        txt += '    Example: ' + str(
                            self.state.to_json()['layers'][i]['annotations'][0]) + '\n'
                    except:
                        print_exception()

        return txt


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
    
    
    setMpData
        
    x = 468.5921936035156, y = 395.48431396484375
    p = PointAnnotation({"type": "point", "id": "(17, nan, nan)", "point": [17.0, NaN, NaN], "props": ["#ffe135", 3, 8]})
    x = nan, y = nan
    p = PointAnnotation({"type": "point", "id": "(17, nan, nan)", "point": [17.0, NaN, NaN], "props": ["#42d4f4", 3, 8]})
    x = nan, y = nan
    
    
    '''