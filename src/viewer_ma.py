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
from qtpy.QtCore import QObject, Signal, QUrl
from qtpy.QtWidgets import QApplication
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, print_exception
from src.shaders import ann_shader
from src.ui.timer import Timer
import src.config as cfg

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['MAViewer']

logger = logging.getLogger(__name__)

# t = Timer()


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    stateChangedAny = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()
    ptsChanged = Signal()
    swimAction = Signal()


class MAViewer(neuroglancer.Viewer):
    def __init__(self, role=None, webengine=None):
        super().__init__()
        self.index = None
        if role:
            self.role = role
        self.webengine = webengine
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._settingZoom = True
        self._layer = cfg.data.zpos
        self.cs_scale = None
        self.pts = OrderedDict()
        self.colors = cfg.glob_colors
        self._crossSectionScale = 1
        self._mpCount = 0
        self._zmag_set = 0
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(self.on_state_changed_any)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        # self.signals.ptsChanged.connect(self.drawSWIMwindow)
        self.type = 'MAViewer'

        logger.info('viewer constructed!')

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.scale)), )

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
        return len(self.state.layers['ann_points'].annotations)

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
        logger.critical(f'Setting zoom to {caller}')
        self._settingZoom = True
        # state = copy.deepcopy(self.state)
        # state.crossSectionScale = val
        # self.set_state(state)
        with self.txn() as s:
            s.crossSectionScale = val

        self._settingZoom = False


    def set_layer(self, index):
        state = copy.deepcopy(self.state)
        state.position[0] = index
        self.set_state(state)


    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()


    def initViewer(self):
        caller = inspect.stack()[1].function
        logger.critical(f'Initializing [{self.type}] [role: {self.role}] [caller: {caller}]...')

        if self.role == 'ref':
            self.index = max(cfg.data.zpos - 1, 0)
        elif self.role == 'base':
            self.index = cfg.data.zpos #

        # self.clear_layers()
        self.restoreManAlignPts()

        sf = cfg.data.scale_val(s=cfg.data.scale)
        path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))

        if not os.path.exists(path):
            cfg.main_window.warn('Data Store Not Found: %s' % path)
            logger.warning('Data Store Not Found: %s' % path); return

        try:
            self.store = get_zarr_tensor(path).result()
        except Exception as e:
            cfg.main_window.warn('Unable to Load Data Store at %s' % path)
            raise e

        # logger.critical('Creating Local Volume for %d' %self.index)
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
            s.show_scale_bar = False
            s.show_axis_lines = False
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            # s.position=[cfg.data.zpos, store.shape[1]/2, store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                s.crossSectionBackgroundColor = '#808080'
            else:
                s.crossSectionBackgroundColor = '#222222'
            # s.cross_section_scale = 1 #bug # cant do this
            _, y, x = self.store.shape
            s.position = [0.5, y / 2, x / 2]
            # s.position = [0.1, y / 2, x / 2]
            # s.layers['ann'].annotations = list(self.pts.values())

        self.actions.add('add_manpoint', self.add_matchpoint)


        self.actions.add('swim', self.swim)

        with self.config_state.txn() as s:
            s.input_event_bindings.slice_view['shift+click0'] = 'add_manpoint'
            s.input_event_bindings.viewer['keys'] = 'swim'
            s.show_ui_controls = False
            s.show_panel_borders = False

        self.drawSWIMwindow()

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))
            self.webengine.setFocus()

        self.set_brightness()
        self.set_contrast()
        # self.set_zmag()
        QApplication.processEvents()
        self.initZoom()
        # self._set_zmag()

    def on_state_changed_any(self):
        caller = inspect.stack()[1].function

        # if not self.cs_scale:
        #     if self.state.crossSectionScale < .001:
        #         self.cs_scale = self.state.crossSectionScale

        # if self._zmag_set < 10:
        #     self._zmag_set += 1
        # logger.critical(f'on_state_changed_any [{self.type}] [i={self._zmag_set}] >>>>')

        # logger.info(f'on_state_changed_any zpos={cfg.data.zpos} [{self.type} {self.role}] [{caller}] >>>>')
        self.signals.stateChangedAny.emit()


    def on_state_changed(self):
        if self._settingZoom:
            return
        # caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        # if calname == '<lambda>':
        #     return


        # self.signals.stateChanged.emit()
        #
        # zoom = self.state.cross_section_scale
        # if zoom:
        #     # if zoom != self._crossSectionScale:
        #     #     logger.info(f' (!) emitting zoomChanged (state.cross_section_scale): {zoom:.3f}...')
        #     #     self.signals.zoomChanged.emit(zoom)
        #     self._crossSectionScale = zoom


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


    def addMp(self):

        pass


    # def undrawAnnotations(self):
    #     try:
    #         with self.txn() as s:
    #             s.layers['ann'].annotations = None
    #     except:
    #         logger.warning('Unable to undraw annotations')


    def getNextUnusedColor(self):
        for c in self.colors:
            if c in self.pts:
                continue
            else:
                return c


    def getUsedColors(self):
        return set(self.pts.keys())


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
        if cfg.data.method() not in ('manual-strict', 'manual-hint'):
            logger.warning('add_matchpoint: User may not select point when using the Auto-SWIM alignment method.')
            return

        logger.info('Adding Manual Points to Buffer...')
        # if not cfg.project_tab.isManualReady():
        #     return

        coords = np.array(s.mouse_voxel_coordinates)
        logger.info('Coordinates: %s' %str(coords))
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless! =%s' % str(coords))
            return
        _, y, x = s.mouse_voxel_coordinates
        z = 0.5
        # z = 0.1
        props = [self.colors[len(self.pts)],
                 getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                 getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
        self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=repr((z,y,x)), point=(z,y,x), props=props)

        self.applyMps()
        self.signals.ptsChanged.emit()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))
        self.drawSWIMwindow()
        logger.info(f'dict = {cfg.data.manpoints_pretty()}')




    def applyMps(self):
        logger.info(f'Setting Manual Correspondence Points for {self.role} viewer...')
        cfg.main_window.statusBar.showMessage('Manual Points Saved!', 3000)
        pts = []
        for key in self.pts.keys():
            p = self.pts[key]
            _, x, y = p.point.tolist()
            pts.append((x, y))
        cfg.data.set_manpoints(self.role, pts)
        # cfg.data.set_manual_points_color(self.role, pts)
        cfg.data.print_all_manpoints()


    def draw_point_annotations(self):
        logger.info('Drawing point annotations...')
        try:
            anns = list(self.pts.values())
            if anns:
                with self.txn() as s:
                    s.layers['ann_points'].annotations = anns
        except:
            # print_exception()
            logger.warning('Unable to draw donut annotations or none to draw')
        # pass



    def undrawSWIMwindows(self):
        caller = inspect.stack()[1].function
        try:
            with self.txn() as s:
                if s.layers['SWIM']:
                    if 'annotations' in s.layers['SWIM'].to_json().keys():
                        logger.info(f'Undrawing SWIM windows...')
                        s.layers['SWIM'].annotations = None
        except:
            logger.warning('Something went wrong while undrawing SWIM windows')
            print_exception()
        pass


    # @functools.cache
    def drawSWIMwindow(self):
        caller = inspect.stack()[1].function

        self.undrawSWIMwindows()
        marker_size = 1

        if cfg.data.current_method == 'grid-custom':
            logger.info('Drawing SWIM Window Annotations for Auto-SWIM Alignment...')

            img_siz = cfg.data.image_size()
            img_w, img_h = img_siz[0], img_siz[1]
            ww_full = cfg.data.swim_window_px() # full window width
            ww_2x2 = cfg.data.swim_2x2_px() # 2x2 window width

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
                        coords=pt,
                        ww_x=ww_2x2[0] - 4,
                        ww_y=ww_2x2[1] - 4,
                        color=colors[i],
                        marker_size=marker_size
                    )
                )

        elif cfg.data.current_method == 'grid-default':
            logger.info('Drawing SWIM Window Annotations for Auto-SWIM Alignment...')

            img_siz = cfg.data.image_size()
            img_w, img_h = img_siz[0], img_siz[1]
            ww_full = cfg.data.stack()[cfg.data.zpos]['alignment']['swim_settings']['default_auto_swim_window_px']

            offset_x1 = (img_w / 2) - (ww_full[0] * (1 / 4))
            offset_x2 = (img_w / 2) + (ww_full[0] * (1 / 4))
            offset_y1 = (img_h / 2) - (ww_full[1] * (1 / 4))
            offset_y2 = (img_h / 2) + (ww_full[1] * (1 / 4))

            # ww_2x2 = cfg.data.swim_2x2_px() # 2x2 window width
            # offset_x1 = ((img_w - ww_full[0]) / 2) + (ww_2x2[0] / 2)
            # offset_x2 = img_w - offset_x1
            # offset_y1 = ((img_h - ww_full[1]) / 2) + (ww_2x2[1] / 2)
            # offset_y2 = img_h - offset_y1

            cps = []
            colors = []
            regions = cfg.data.grid_default_regions
            logger.info(f'regions: {regions}')
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
                            coords=pt,
                            # ww_x=ww_2x2[0],
                            # ww_y=ww_2x2[1],
                            ww_x=(ww_full[0] / 2) - 4,
                            ww_y=(ww_full[1] / 2) - 4,
                            color=colors[i],
                            marker_size=marker_size
                        )
                    )

        else:
            logger.info('Drawing SWIM Window Annotations for Manual Alignment...')
            pts = list(self.pts.items())
            try:
                assert len(pts) == len(cfg.data.manpoints()[self.role])
            except:
                logger.warning(f'len(pts) = {len(pts)}, len(cfg.data.manpoints()[self.role]) = {len(cfg.data.manpoints()[self.role])}')
            annotations = []
            ww = cfg.data.manual_swim_window_px()
            for i, pt in enumerate(pts):
                coords = pt[1].point
                color = pt[0]
                annotations.extend(
                    self.makeRect(
                        prefix=str(i),
                        coords=(coords[2], coords[1]),
                        ww_x=ww,
                        ww_y=ww,
                        color=color,
                        marker_size=marker_size
                    )
                )


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


    @cache
    def makeRect(self, prefix, coords, ww_x, ww_y, color, marker_size):
        segments = []
        x = coords[0]
        y = coords[1]
        hw = int(ww_x / 2) # Half-width
        hh = int(ww_y / 2) # Half-height
        A = (.5, y + hh, x - hw)
        B = (.5, y + hh, x + hw)
        C = (.5, y - hh, x + hw)
        D = (.5, y - hh, x - hw)
        segments.append(ng.LineAnnotation(id=prefix + '_L1', pointA=A, pointB=B, props=[color, marker_size]))
        segments.append(ng.LineAnnotation(id=prefix + '_L2', pointA=B, pointB=C, props=[color, marker_size]))
        segments.append(ng.LineAnnotation(id=prefix + '_L3', pointA=C, pointB=D, props=[color, marker_size]))
        segments.append(ng.LineAnnotation(id=prefix + '_L4', pointA=D, pointB=A, props=[color, marker_size]))
        return segments




    def restoreManAlignPts(self):
        logger.info('Restoring manual alignment points for role: %s' %self.role)
        # self.pts = {}
        self.pts = OrderedDict()
        pts_data = cfg.data.getmpFlat(l=cfg.data.zpos)[self.role]
        for i, p in enumerate(pts_data):
            props = [self.colors[i],
                     getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                     getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
            self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=str(p), point=p, props=props)

        # with self.txn() as s:
        #     s.layers['ann'] = ng.LocalAnnotationLayer(
        #         dimensions=self.coordinate_space,
        #         annotations=self.pt2ann(points=pts_data),
        #         annotation_properties=[
        #             ng.AnnotationPropertySpec(id='ptColor', cur_method='rgb', default='white', ),
        #             ng.AnnotationPropertySpec(id='ptWidth', cur_method='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT')),
        #             ng.AnnotationPropertySpec(id='size', cur_method='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'))
        #         ],
        #         shader=copy.deepcopy(ann_shader),
        #     )


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
        logger.info(f'zpos={cfg.data.zpos} Setting Z-mag on {self.type} to {val} [{self.role}]')
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


    def _set_zmag(self):

        if self._zmag_set < 8:
            # logger.info(f'zpos={cfg.data.zpos} Setting Z-mag on {self.type} [{self.role}]')
            self._zmag_set += 1
            try:
                with self.txn() as s:
                    s.relativeDisplayScales = {"z": 10}
            except:
                print_exception()

    def initZoom(self):
        adjust = 1.08
        if self.cs_scale:
            logger.critical(f'Initializing crossSectionScale to self.cs_scale ({self.cs_scale}) [{self.role}]')
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:
            _, tensor_y, tensor_x = cfg.tensor.shape
            widget_w = cfg.project_tab.MA_webengine_ref.geometry().width()
            widget_h = cfg.project_tab.MA_webengine_ref.geometry().height()
            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale) # nm per imagepixel
            # tissue_h, tissue_w = res_y*frame[0], res_x*frame[1]  # nm of sample
            scale_h = ((res_y * tensor_y) / widget_h) * 1e-9  # nm/pixel (subtract height of ng toolbar)
            scale_w = ((res_x * tensor_x) / widget_w) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)
            logger.info(f'Initializing crossSectionScale to calculated value times adjust {self.cs_scale} [{self.role}]')
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