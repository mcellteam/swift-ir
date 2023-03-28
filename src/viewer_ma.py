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
        self._layer = None
        self.cs_scale = None
        # self.pts = {}
        self.pts = OrderedDict()
        self.mp_colors = ['#f3e375', '#5c4ccc', '#800000', '#aaa672',
                          '#152c74', '#404f74', '#f3e375', '#5c4ccc',
                          '#d6acd6', '#aaa672', '#152c74', '#404f74'
                          ]
        self._crossSectionScale = 1
        self._mpCount = 0
        self._zmag_set = 0
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(self.on_state_changed_any)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed_any))
        self.signals.ptsChanged.connect(self.drawSWIMwindow)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
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
            # s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.show_axis_lines = False
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            # s.position=[cfg.data.zpos, store.shape[1]/2, store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            # s.crossSectionBackgroundColor = '#808080' # 128 grey
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

        # if cfg.data.method() != 'Auto-SWIM':
        #     self.draw_point_annotations()

        # if getOpt('neuroglancer,SHOW_SWIM_WINDOW'):
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
        # if self._zmag_set < 10:
        #     self._zmag_set += 1
        # logger.critical(f'on_state_changed_any [{self.type}] [i={self._zmag_set}] >>>>')

        logger.info(f'on_state_changed_any {self.type} [{self.role}] [{caller}] >>>>')
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


        self.signals.stateChanged.emit()

        # zoom = self.state.cross_section_scale
        # if zoom:
        #     if zoom != self._crossSectionScale:
        #         logger.info(f' (!) emitting zoomChanged (state.cross_section_scale): {zoom:.3f}...')
        #         self.signals.zoomChanged.emit(zoom)
        #     self._crossSectionScale = zoom


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


    # def undrawAnnotations(self):
    #     try:
    #         with self.txn() as s:
    #             s.layers['ann'].annotations = None
    #     except:
    #         logger.warning('Unable to undraw annotations')


    def getNextUnusedColor(self):
        for c in self.mp_colors:
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
        logger.critical('Running SWIM...')
        # cfg.main_window.alignOne()
        self.signals.swimAction.emit()



    def add_matchpoint(self, s):
        if cfg.data.method() not in ('Manual-Strict', 'Manual-Hint'):
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
        props = [self.mp_colors[len(self.pts)],
                 getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                 getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
        self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=repr((z,y,x)), point=(z,y,x), props=props)

        self.applyMps()
        self.signals.ptsChanged.emit()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))
        # try:
        #     self.set_zmag()
        # except:
        #     print_exception()
        self.drawSWIMwindow()
        if cfg.data.method() == 'Manual-Strict':
            self.draw_point_annotations()
        logger.critical(f'pts = {self.pts}')
        logger.critical(f'dict = {cfg.data.manpoints_pretty()}')




    def applyMps(self):
        logger.info(f'Setting Manual Correspondence Points for {self.role} viewer...')
        cfg.main_window.statusBar.showMessage('Manual Points Saved!', 3000)
        pts = []
        for key in self.pts.keys():
            p = self.pts[key]
            _, x, y = p.point.tolist()
            pts.append((x, y))
        cfg.data.set_manual_points(self.role, pts)
        # cfg.data.set_manual_points_color(self.role, pts)
        cfg.data.print_all_match_points()


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


    def undraw_point_annotations(self):
        # logger.info('Undrawing point annotations...')
        try:
            with self.txn() as s:
                s.layers['ann_swim'].annotations = None
        except:
            # print_exception()
            logger.warning('No donut annotations to delete')
        # pass


    def undrawSWIMwindow(self):
        # logger.info('Undrawing SWIM Window')
        try:
            with self.txn() as s:
                s.layers['ann_auto'].annotations = None
        except:
            logger.warning('No annotations to clear')
            # print_exception()


    # @functools.cache
    def drawSWIMwindow(self):
        logger.info('')
        # t.start()

        self.undraw_point_annotations()
        self.undrawSWIMwindow()

        marker_size = 1

        if cfg.data.method() == 'Auto-SWIM':
            '''SWIM Annotations for Automated SWIM Alignments'''

            # if not cfg.project_tab.tgl_alignMethod.isChecked():
            logger.info('Drawing SWIM Window Layer for Auto-SWIM Alignment...')

            sw = cfg.data.swim_window()  # SWIM Window
            image_w = cfg.data.image_size()[0]
            image_h = cfg.data.image_size()[1]
            siz_sw = sw * image_w
            siz_sh = sw * image_h
            offset_w = (image_w - siz_sw) / 2
            offset_h = (image_h - siz_sh) / 2
            half_w = image_w / 2
            half_h = image_h / 2

            # pointA=[.5, 10, 10], pointB=[.5, 1000, 1000] <- diagonal from upper right to bottom left
            # square corners, counter-clockwise from upper-left:
            A = [.5, offset_h + siz_sh, offset_w]
            B = [.5, offset_h, offset_w]
            C = [.5, offset_h, offset_w + siz_sw]
            D = [.5, offset_h + siz_sh, offset_w + siz_sw]

            AB = [.5, half_h, offset_w]
            BC = [.5, offset_h, half_w]
            CD = [.5, half_h, offset_w + siz_sw]
            DA = [.5, offset_h + siz_sh, half_w]

            CP = [.5, half_h, half_w]

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
            '''
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


            '''
            A____AB_____B
            |           |
            DA   CP    BC
            |           |
            D____CD_____C 
            '''

            color0 = self.mp_colors[3]
            color1 = self.mp_colors[2]
            color2 = self.mp_colors[1]
            color3 = self.mp_colors[0]


            # annotations = [
            #     ng.LineAnnotation(id='L1', pointA=A, pointB=B, props=['#FFFF00', marker_size]),
            #     ng.LineAnnotation(id='L2', pointA=B, pointB=C, props=['#FFFF00', marker_size]),
            #     ng.LineAnnotation(id='L3', pointA=C, pointB=D, props=['#FFFF00', marker_size]),
            #     ng.LineAnnotation(id='L4', pointA=D, pointB=A, props=['#FFFF00', marker_size]),
            #     ng.LineAnnotation(id='L5', pointA=AB, pointB=CD, props=['#FFFF00', marker_size]),
            #     ng.LineAnnotation(id='L6', pointA=DA, pointB=BC, props=['#FFFF00', marker_size]),
            # ]

            annotations = [
                ng.LineAnnotation(id='L01', pointA=A, pointB=AB, props=[color0, marker_size]),
                ng.LineAnnotation(id='L02', pointA=AB, pointB=CP, props=[color0, marker_size]),
                ng.LineAnnotation(id='L03', pointA=CP, pointB=DA, props=[color0, marker_size]),
                ng.LineAnnotation(id='L04', pointA=DA, pointB=A, props=[color0, marker_size]),

                ng.LineAnnotation(id='L05', pointA=AB, pointB=B, props=[color1, marker_size]),
                ng.LineAnnotation(id='L06', pointA=B, pointB=BC, props=[color1, marker_size]),
                ng.LineAnnotation(id='L07', pointA=BC, pointB=CP, props=[color1, marker_size]),
                ng.LineAnnotation(id='L08', pointA=CP, pointB=AB, props=[color1, marker_size]),

                ng.LineAnnotation(id='L09', pointA=DA, pointB=CP, props=[color2, marker_size]),
                ng.LineAnnotation(id='L10', pointA=CP, pointB=CD, props=[color2, marker_size]),
                ng.LineAnnotation(id='L11', pointA=CD, pointB=D, props=[color2, marker_size]),
                ng.LineAnnotation(id='L12', pointA=D, pointB=DA, props=[color2, marker_size]),

                ng.LineAnnotation(id='L13', pointA=CP, pointB=BC, props=[color3, marker_size]),
                ng.LineAnnotation(id='L14', pointA=BC, pointB=C, props=[color3, marker_size]),
                ng.LineAnnotation(id='L15', pointA=C, pointB=CD, props=[color3, marker_size]),
                ng.LineAnnotation(id='L16', pointA=CD, pointB=CP, props=[color3, marker_size]),

            ]

        else:
            '''SWIM Annotations for Manual Alignments'''

            logger.info('Drawing SWIM Windows Layer for Manual Alignment...')
            points = cfg.data.manual_points()[self.role]
            annotations = []
            half_win = int(cfg.data.manual_swim_window() / 2)

            # if len(cfg.data.manual_points()[self.role]) > 0:
            #     for i in range(len(points)):
            #         pt = points[i]
            #         x = pt[0]
            #         y = pt[1]
            #
            #
            #         A = [.5, y-half_win, x+half_win]
            #         B = [.5, y+half_win, x+half_win]
            #         C = [.5, y+half_win, x-half_win]
            #         D = [.5, y-half_win, x-half_win]
            #
            #         # X_A = [.5, x - 25, y + 25]
            #         # X_B = [.5, x + 25, y + 25]
            #         # X_C = [.5, x + 25, y - 25]
            #         # X_D = [.5, x - 25, y - 25]
            #
            #         color = self.mp_colors[i]
            #
            #         annotations.append(ng.LineAnnotation(id='%d_L1'%i, pointA=A, pointB=B, props=[color, marker_size]))
            #         annotations.append(ng.LineAnnotation(id='%d_L2'%i, pointA=B, pointB=C, props=[color, marker_size]))
            #         annotations.append(ng.LineAnnotation(id='%d_L3'%i, pointA=C, pointB=D, props=[color, marker_size]))
            #         annotations.append(ng.LineAnnotation(id='%d_L4'%i, pointA=D, pointB=A, props=[color, marker_size]))
            #
            #         # annotations.append(ng.LineAnnotation(id='%d_L5'%i, pointA=X_A, pointB=X_C, props=[color, marker_size]))
            #         # annotations.append(ng.LineAnnotation(id='%d_L6'%i, pointA=X_B, pointB=X_D, props=[color, marker_size]))
            # else:
            pts_list = list(self.pts.items())

            for i in range(len(pts_list)):
                pt = pts_list[i]
                color = pt[0]
                coords = pt[1].point

                x = coords[1]
                y = coords[2]
                A = [.5, x-half_win, y+half_win]
                B = [.5, x+half_win, y+half_win]
                C = [.5, x+half_win, y-half_win]
                D = [.5, x-half_win, y-half_win]

                X_A = [.5, x - 25, y + 25]
                X_B = [.5, x + 25, y + 25]
                X_C = [.5, x + 25, y - 25]
                X_D = [.5, x - 25, y - 25]

                annotations.append(ng.LineAnnotation(id='%d_L1'%i, pointA=A, pointB=B, props=[color, marker_size]))
                annotations.append(ng.LineAnnotation(id='%d_L2'%i, pointA=B, pointB=C, props=[color, marker_size]))
                annotations.append(ng.LineAnnotation(id='%d_L3'%i, pointA=C, pointB=D, props=[color, marker_size]))
                annotations.append(ng.LineAnnotation(id='%d_L4'%i, pointA=D, pointB=A, props=[color, marker_size]))

                # annotations.append(ng.LineAnnotation(id='%d_L5'%i, pointA=X_A, pointB=X_C, props=[color, marker_size]))
                # annotations.append(ng.LineAnnotation(id='%d_L6'%i, pointA=X_B, pointB=X_D, props=[color, marker_size]))

        # box = ng.AxisAlignedBoundingBoxAnnotation(
        #     point_a=[.5, 50, 50],
        #     point_b=[.5, 500, 500],
        #     id="bounding-box",
        # )


        with self.txn() as s:
            # s.layers['bounding-box'] = ng.LocalAnnotationLayer(
            #     dimensions=self.coordinate_space,
            #     annotations=[box])
            s.layers['ann_swim'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='color', type='rgb', default='#ffff66', ),
                    # ng.AnnotationPropertySpec(id='size', type='float32', default=1, )
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

        # t.stop()


    def makeSquare(self, size):
        pass




    def restoreManAlignPts(self):
        logger.info('Restoring manual alignment points for role: %s' %self.role)
        # self.pts = {}
        self.pts = OrderedDict()
        pts_data = cfg.data.getmpFlat(l=cfg.data.zpos)[self.role]
        for i, p in enumerate(pts_data):
            props = [self.mp_colors[i],
                     getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                     getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
            self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=str(p), point=p, props=props)

        # with self.txn() as s:
        #     s.layers['ann'] = ng.LocalAnnotationLayer(
        #         dimensions=self.coordinate_space,
        #         annotations=self.pt2ann(points=pts_data),
        #         annotation_properties=[
        #             ng.AnnotationPropertySpec(id='ptColor', type='rgb', default='white', ),
        #             ng.AnnotationPropertySpec(id='ptWidth', type='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT')),
        #             ng.AnnotationPropertySpec(id='size', type='float32', default=getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'))
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
        logger.info(f'Setting Z-mag on {self.type} to {val} [{self.role}]')
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
            logger.info(f'Setting Z-mag on {self.type} [{self.role}]')
            self._zmag_set += 1
            try:
                with self.txn() as s:
                    s.relativeDisplayScales = {"z": 10}
            except:
                print_exception()

    def initZoom(self):


        logger.critical(f'Initializing Zoom [{self.role}]')
        adjust = 1.08

        if self.cs_scale:
            logger.critical(f'Setting zoom to self.cs_scale, {self.cs_scale} [{self.role}]')
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
            logger.critical(f'Setting zoom to calculated value times adjust ({adjust}), {self.cs_scale} [{self.role}]')
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




    from src.funcs_zarr import get_zarr_tensor
    sf = cfg.data.scale_val(s=cfg.data.scale)
    path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
