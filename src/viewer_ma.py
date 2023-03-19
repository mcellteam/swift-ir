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
from collections import OrderedDict
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, QUrl
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, print_exception
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
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

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
        return len(self.state.layers['ann'].annotations)


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
        # caller = inspect.stack()[1].function
        # logger.critical('caller: %s' %str(caller))
        logger.critical(f'Initializing Viewer (Role: %s)....' %self.role)

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
            # s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.show_axis_lines = False
            s.show_default_annotations = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            # s.position=[cfg.data.zpos, store.shape[1]/2, store.shape[2]/2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=cfg.data['rendering']['shader'], )
            s.crossSectionBackgroundColor = '#808080' # 128 grey
            # s.cross_section_scale = 1 #bug # cant do this
            _, y, x = self.store.shape
            s.position = [0.5, y / 2, x / 2]
            # s.position = [0.1, y / 2, x / 2]
            # s.layers['ann'].annotations = list(self.pts.values())

        self.actions.add('add_manpoint', self.add_matchpoint)

        with self.config_state.txn() as s:
            s.input_event_bindings.slice_view['shift+click0'] = 'add_manpoint'
            s.show_ui_controls = False
            s.show_panel_borders = False

        # if cfg.data.method() != 'Auto-SWIM':
        #     self.draw_point_annotations()

        # if getOpt('neuroglancer,SHOW_SWIM_WINDOW'):
        self.drawSWIMwindow()

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))

        self.set_brightness()
        self.set_contrast()
        # self.set_zmag()
        # self.initZoom()
        # self._set_zmag()


    def on_state_changed(self):
        if self._settingZoom:
            return
        # caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        if calname == '<lambda>':
            return


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


    def add_matchpoint(self, s):
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


        self.draw_point_annotations()
        self.drawSWIMwindow()

        self.signals.ptsChanged.emit()

        self._set_zmag()





        # self._set_zmag()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))




    def draw_point_annotations(self):
        # logger.critical('Drawing point annotations...')
        # try:
        #     anns = list(self.pts.values())
        #     if anns:
        #         with self.txn() as s:
        #             s.layers['ann'].annotations = anns
        # except:
        #     # print_exception()
        #     logger.warning('Unable to draw donut annotations or none to draw')
        pass


    def undraw_point_annotations(self):
        # logger.critical('Undrawing point annotations...')
        # try:
        #     with self.txn() as s:
        #         s.layers['ann'].annotations = None
        # except:
        #     # print_exception()
        #     logger.warning('No donut annotations to delete')
        pass


    def undrawSWIMwindow(self):
        logger.critical('Undrawing SWIM Window')
        try:
            with self.txn() as s:
                s.layers['SWIM Window'].annotations = None
        except:
            logger.warning('No annotations to clear')
            # print_exception()


    def drawSWIMwindow(self):
        logger.critical('Drawing SWIM window...')
        self.undrawSWIMwindow()

        marker_size = 1

        if cfg.data.method() == 'Auto-SWIM':
        # if not cfg.project_tab.tgl_alignMethod.isChecked():
            logger.critical('Drawing SWIM Window for automatic SWIM alignment...')
            self.undraw_point_annotations()

            sw = cfg.data.swim_window() # SWIM Window
            image_w = cfg.data.image_size()[0]
            image_h = cfg.data.image_size()[1]
            siz_sw = sw * image_w
            offset = (image_w - siz_sw) /2
            half_w = image_w / 2
            half_h = image_h / 2

            # pointA=[.5, 10, 10], pointB=[.5, 1000, 1000] <- diagonal from upper right to bottom left
            # square corners, counter-clockwise from upper-left:
            A = [.5, offset + siz_sw, offset]
            B = [.5, offset, offset]
            C = [.5, offset, offset + siz_sw]
            D = [.5, offset + siz_sw, offset + siz_sw]

            AB = [.5, half_w, offset]
            BC = [.5, offset, half_h]
            CD = [.5, half_w, offset + siz_sw]
            DA = [.5, offset + siz_sw, half_h]

            '''
            A____AB_____B
            |           |
            DA          BC
            |           |
            D____CD_____C 
            '''


            annotations = [
                ng.LineAnnotation(id='L1', pointA=A, pointB=B, props=['#FFFF00', marker_size]),
                ng.LineAnnotation(id='L2', pointA=B, pointB=C, props=['#FFFF00', marker_size]),
                ng.LineAnnotation(id='L3', pointA=C, pointB=D, props=['#FFFF00', marker_size]),
                ng.LineAnnotation(id='L4', pointA=D, pointB=A, props=['#FFFF00', marker_size]),
                ng.LineAnnotation(id='L5', pointA=AB, pointB=CD, props=['#FFFF00', marker_size]),
                ng.LineAnnotation(id='L6', pointA=DA, pointB=BC, props=['#FFFF00', marker_size]),
            ]

        else:
            logger.critical('Drawing SWIM Windows for manual alignment...')
            manual_sw = 128
            points = cfg.data.manual_points()[self.role]
            annotations = []

            if len(cfg.data.manual_points()[self.role]) > 0:
                for i in range(len(points)):
                    pt = points[i]
                    x = pt[0]
                    y = pt[1]
                    A = [.5, x-64, y+64]
                    B = [.5, x+64, y+64]
                    C = [.5, x+64, y-64]
                    D = [.5, x-64, y-64]

                    X_A = [.5, x - 25, y + 25]
                    X_B = [.5, x + 25, y + 25]
                    X_C = [.5, x + 25, y - 25]
                    X_D = [.5, x - 25, y - 25]

                    color = self.mp_colors[i]

                    annotations.append(ng.LineAnnotation(id='%d_L1'%i, pointA=A, pointB=B, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L2'%i, pointA=B, pointB=C, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L3'%i, pointA=C, pointB=D, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L4'%i, pointA=D, pointB=A, props=[color, marker_size]))

                    annotations.append(ng.LineAnnotation(id='%d_L5'%i, pointA=X_A, pointB=X_C, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L6'%i, pointA=X_B, pointB=X_D, props=[color, marker_size]))
            else:
                pts_list = list(self.pts.items())

                for i in range(len(pts_list)):
                    pt = pts_list[i]
                    color = pt[0]
                    coords = pt[1].point

                    x = coords[1]
                    y = coords[2]
                    A = [.5, x-64, y+64]
                    B = [.5, x+64, y+64]
                    C = [.5, x+64, y-64]
                    D = [.5, x-64, y-64]

                    X_A = [.5, x - 25, y + 25]
                    X_B = [.5, x + 25, y + 25]
                    X_C = [.5, x + 25, y - 25]
                    X_D = [.5, x - 25, y - 25]

                    annotations.append(ng.LineAnnotation(id='%d_L1'%i, pointA=A, pointB=B, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L2'%i, pointA=B, pointB=C, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L3'%i, pointA=C, pointB=D, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L4'%i, pointA=D, pointB=A, props=[color, marker_size]))

                    annotations.append(ng.LineAnnotation(id='%d_L5'%i, pointA=X_A, pointB=X_C, props=[color, marker_size]))
                    annotations.append(ng.LineAnnotation(id='%d_L6'%i, pointA=X_B, pointB=X_D, props=[color, marker_size]))

        box = ng.AxisAlignedBoundingBoxAnnotation(
            point_a=[5, 50, 50],
            point_b=[5, 500, 500],
            id="bounding-box",
        )


        with self.txn() as s:
            s.layers["bounding-box"] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotations=[box])
            s.layers['SWIM Window'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='color', type='rgb', default='#ffff66', ),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=1, )
                ],
                annotations=annotations,
                shader='''
                    void main() {
                      setColor(prop_color());
                      setPointMarkerSize(prop_size());
                    }
                ''',

            )

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
            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale) # nm per imagepixel
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
    sf = cfg.data.scale_val(s=cfg.data.scale)
    path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
