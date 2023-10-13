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
from math import floor
import numpy as np
import numcodecs
import zarr
import neuroglancer
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, Slot, QUrl
from qtpy.QtWidgets import QApplication
from qtpy.QtWebEngineWidgets import *
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, getData, setData, print_exception, is_joel, is_tacc, caller_name
import src.config as cfg

ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['MAViewer']

logger = logging.getLogger(__name__)
# logger.propagate = False

# t = Timer()

DEV = is_joel()


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal()
    zVoxelCoordChanged = Signal(int)
    zoomChanged = Signal(float)
    mpUpdate = Signal()
    ptsChanged = Signal()
    swimAction = Signal()
    badStateChange = Signal()



class MAViewer(neuroglancer.Viewer):
    def __init__(self, parent, dm, role='tra', webengine=None):
        super().__init__()
        self.parent = parent
        self.dm = dm
        self.index = None
        self.role = role
        self.webengine = webengine
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        # self._settingZoom = True
        # self._layer = self.dm.zpos
        self.cs_scale = None
        # self.pts = OrderedDict()
        self.pts = {'ref':[None,None,None], 'tra': [None,None,None]}
        self._selected_index = {'ref': 0, 'tra': 0}
        # self._selected_index = 0
        self.colors = cfg.glob_colors
        self._crossSectionScale = 1
        self._mpCount = 0
        self._zmag_set = 0
        # self.shared_state.add_changed_callback(self.on_state_changed)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.type = 'MAViewer'
        self._inSync = 0
        self._blockStateChanged = False
        self.signals.ptsChanged.connect(self.drawSWIMwindow)

        logger.info('viewer constructed!')

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(self.dm.resolution(s=self.dm.level)), )
            # scales=[1,1,1] )

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
            s.show_ui_controls = getData('state,neuroglancer_show_controls')


    def n_annotations(self):
        return len(self.state.layers['ann_points'].annotations)


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
        with self.txn() as s:
            s.crossSectionScale = val
        self._blockStateChanged = False



    # def set_layer(self, index=None):
    def set_layer(self, zpos=None):
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Setting layer (zpos={zpos})...")
        #NotCulpableForFlickerGlitch
        # if self.type != 'EMViewerStage':
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

        with self.txn() as s:
            vc = s.voxel_coordinates
            vc[0] = self.index + 0.5

        # if self.dm.method in ('manual-hint', 'manual-strict'):
        #     self.restoreManAlignPts() #Todo study this. Temp fix. #0805-

        self.drawSWIMwindow()

        self._blockStateChanged = False




    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()


    def post_message(self, msg):
        with self.config_state.txn() as s:
            s.status_messages['message'] = msg


    # async def initViewer(self, obey_zpos=True):
    def initViewer(self):
        t0 = time.time()
        # caller = inspect.stack()[1].function
        self._blockStateChanged = True #Critical #Always
        # if DEV:
        #     logger.critical(f'Initializing [{self.type}] [role: {self.role}] [caller: {caller_name()}]...')

        if self.role == 'ref':
            self.index = self.dm.get_ref_index()
        elif self.role == 'tra':
            self.index = self.dm.zpos #


        self.clear_layers()

        t1 = time.time()

        # self.restoreManAlignPts()

        sf = self.dm.lvl(s=self.dm.level)
        path = os.path.join(self.dm['info']['images_location'], 'zarr', 's' + str(sf))

        if not os.path.exists(path):
            logger.warning('Data Store Not Found: %s' % path); return

        try:
            self.store = self.tensor = get_zarr_tensor(path).result()
            # self.store
            # self.store = await get_zarr_tensor(path)
        except Exception as e:
            logger.error('Unable to Load Data Store at %s' % path)
            raise e

        t2 = time.time()

        # logger.critical('Creating Local Volume for %d' %self.index)

        if is_tacc():
            self.LV = ng.LocalVolume(
                volume_type='image',
                # data=self.store[self.index:self.index + 1, :, :],
                data=self.store[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, 0, 0],
                max_downsampling=cfg.max_downsampling,
                max_downsampled_size = cfg.max_downsampled_size
                # max_downsampling_scales=cfg.max_downsampling_scales  # Goes a LOT slower when set to 1
            )
        else:
            self.LV = ng.LocalVolume(
                volume_type='image',
                # data=self.store[self.index:self.index + 1, :, :],
                data=self.store[:, :, :],
                dimensions=self.coordinate_space,
                voxel_offset=[0, 0, 0],
                # max_downsampling_scales=cfg.max_downsampling_scales  # Goes a LOT slower when set to 1
            )

        t3 = time.time()

        with self.txn() as s:
            s.layout.type = 'yz'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            # level.show_scale_bar = False
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.projectionScale = 1
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=self.dm['rendering']['shader'], )
            _, y, x = self.store.shape
            s.voxel_coordinates = [self.index + .5, y / 2, x / 2]
            s.show_default_annotations = False
            s.projectionScale = 1
            if getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'):
                s.crossSectionBackgroundColor = getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')
            else:
                if getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'):
                    # level.crossSectionBackgroundColor = '#222222'
                    s.crossSectionBackgroundColor = '#000000'
                else:
                    s.crossSectionBackgroundColor = '#808080'

        self.actions.add('add_manpoint', self.add_matchpoint)
        self.actions.add('swim', self.swim)

        t4 = time.time()

        # self.actions.add('swim', self.blinkCallback)

        with self.config_state.txn() as s:
            # s.input_event_bindings.slice_view['dblclick0'] = 'add_manpoint'
            s.input_event_bindings.slice_view['shift+click0'] = 'add_manpoint'
            # s.input_event_bindings.slice_view['mousedown0'] = 'add_manpoint' #this works
            # s.input_event_bindings.slice_view['at:control+mousedown0'] = 'add_manpoint'
            s.input_event_bindings.viewer['keys'] = 'swim'
            s.show_ui_controls = False
            # s.show_ui_controls = True
            s.show_panel_borders = False
            s.show_help_button = True
            s.show_layer_panel = False
            s.scale_bar_options.padding_in_pixels = 0  # default = 8
            s.scale_bar_options.left_pixel_offset = 10  # default = 10
            s.scale_bar_options.bottom_pixel_offset = 10  # default = 10
            s.scale_bar_options.bar_top_margin_in_pixels = 4  # default = 5
            # s.scale_bar_options.font_name = 'monospace'
            # s.scale_bar_options.font_name = 'serif'

        t5 = time.time()
        self.drawSWIMwindow()

        t6 = time.time()

        if self.webengine:
            self.webengine.setUrl(QUrl(self.get_viewer_url()))
            # self.webengine.reload()
            # self.webengine.setFocus() #1011-

        # self.set_brightness()
        # self.set_contrast()
        # QApplication.processEvents()
        self.initZoom()

        self._blockStateChanged = False

        t7 = time.time()

        logger.info(f"\ntimings: {t1-t0:.3g}/{t2 - t0:.3g}/{t3 - t0:.3g}/{t4 - t0:.3g}/{t5 - t0:.3g}/{t6 - t0:.3g}/{t7 - t0:.3g}")



    # def blickCallback(self):
    #     logger.info('')
    #     pass

    def text(self):
        txt = ''

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



    def info(self):
        n_layers = None
        txt = '\n\n'
        try:    txt += f'  caller             = {caller_name()}\n'
        except: txt += f'  caller             =\n'
        txt +=         f'  type/role          = {self.type}/{self.role}\n'
        txt +=         f'  current method     = {self.dm.current_method}\n'
        try:    txt += f'  _blockStateChanged = {self._blockStateChanged}\n'
        except: txt += f'  _blockStateChanged =\n'
        try:    txt += f'  self.dm.zpos      = {self.dm.zpos}\n'
        except: txt += f'  self.dm.zpos      =\n'
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
            n_layers = len(cfg.editorViewer.state.to_json()['layers'])
            txt += f"  {n_layers} Layers\n"
        except:
            txt += f'   0 Layers\n'
        if n_layers:
            for i in range(n_layers):
                txt += f"  Layer {i}:\n"
                name = cfg.editorViewer.state.to_json()['layers'][i]['name']
                txt += f"    Name: {name}\n"
                type = cfg.editorViewer.state.to_json()['layers'][i]['type']
                txt += f"    Type: {type}\n"
                if type == 'annotation':
                    n_ann = len(cfg.editorViewer.state.to_json()['layers'][i]['annotations'])
                    txt += f"    # annotations: {n_ann}\n"
                    ids = [cfg.editorViewer.state.to_json()['layers'][i]['annotations'][x]['id'] for x in range(n_ann)]
                    txt += '    ids : '
                    txt += ', '.join(ids)
                    txt += '\n'
                    try:
                        txt += '    Example: ' + str(cfg.editorViewer.state.to_json()['layers'][i]['annotations'][0]) + '\n'
                    except:
                        print_exception()

        return txt



    @Slot()
    def on_state_changed(self):
        # logger.info(f'[{self.role}]')
        # logger.info(f"[{self.role}], tra_ref_toggle = {self.dm['state']['tra_ref_toggle']}, _blockStateChanged = {self._blockStateChanged}")

        if self._blockStateChanged:
            return

        logger.info('state changed!')

        self._blockStateChanged = True

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
                # self._blockStateChanged = False
                self.signals.zVoxelCoordChanged.emit(self.index)


        # if self.dm.lvl() > 2:
        #     if self.state.relative_display_scales == None:
        #         self.set_zmag()

        self._blockStateChanged = False






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



    # def undrawAnnotations(self):
    #     try:
    #         with self.txn() as s:
    #             s.layers['ann'].annotations = None
    #     except:
    #         logger.warning('Unable to undraw annotations')


    def getNextUnusedColor(self, role):
        # return self.colors[len(self.pts[role])]
        return self.colors[self.getNextPoint(role)]

    def getNextPoint(self, role):
        # return self.colors[len(self.pts[role])]
        return next((i for i, v in enumerate(self.pts[role]) if not v), 0)

    def numPts(self, role):
        n = 0
        for pt in self.pts[role]:
            if pt:
                n += 1
        return n


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
        self.signals.swimAction.emit()



    def add_matchpoint(self, s):
        logger.critical('\n\n--> add_matchpoint -->\n')
        if self.dm.method() != 'manual':
            logger.warning('add_matchpoint: User may not select points while aligning with grid.')
            return

        # if not cfg.project_tab.isManualReady():
        #     return

        # if self.numPts(self.role) >= 3:
        #     cfg.mw.warn('Three points have already been selected for the reference section!')
        #     return

        # logger.info('Adding Manual Points to Buffer...')

        coords = np.array(s.mouse_voxel_coordinates)
        # logger.info('Coordinates: %s' %str(coords))
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless! =%s' % str(coords))
            return
        _, y, x = s.mouse_voxel_coordinates
        # z = 0.1
        # z = 0.5
        pt_index = self._selected_index[self.role]

        # logger.info(f'pt_index = {pt_index}')


        props = [self.colors[pt_index],
                 getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                 getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
        # self.pts[self.getNextUnusedColor()] = ng.PointAnnotation(id=repr((z,y,x)), point=(z,y,x), props=props)
        ann = ng.PointAnnotation(id=repr((self.index + 0.5,y,x)), point=(self.index + 0.5,y,x), props=props)
        # logger.info(ann.to_json())
        self.pts[self.role][pt_index] = ann

        self.setMpData()

        # self._selected_index[self.role] = self.getNextPoint(self.role)
        select_by = self.dm['state']['neuroglancer']['region_selection']['select_by']
        logger.info(f"select by: {select_by}")


        if select_by == 'sticky':
            pass
        elif select_by == 'cycle':
            self._selected_index[self.role] = (self._selected_index[self.role] + 1) % 3
            if self.numPts(self.role) == 3:
                if self.dm['state']['tra_ref_toggle'] == 1:
                    # self._selected_index['ref'] = 0
                    cfg.pt.set_reference()
                else:
                    # self._selected_index['tra'] = 0
                    cfg.pt.set_transforming()

        elif select_by == 'zigzag':
            if self.dm['state']['tra_ref_toggle'] == 1:
                # self._selected_index['ref'] = (self._selected_index[self.role] + 1) % 3
                self._selected_index['ref'] = self._selected_index[self.role]
                cfg.pt.set_reference()
            else:
                self._selected_index['tra'] = (self._selected_index[self.role] + 1) % 3
                cfg.pt.set_transforming()

        self.signals.ptsChanged.emit()
        logger.info('%s Match Point Added: %s' % (self.role, str(coords)))
        # self.drawSWIMwindow()
        # logger.info(f'dict = {self.dm.manpoints_pretty()}')
        logger.critical('\n\n<-- add_matchpoint <--\n')


    def setMpData(self):
        '''Copy local manual points into project dictionary'''
        l = [None,None,None]
        for i,p in enumerate(self.pts[self.role]):
            if p:
                _, x, y = p.point.tolist()
                if not math.isnan(x):
                    print(f"x = {x}, y = {y}")
                    l[i] = (x, y)

        # print(f"Setting point selections: {l}\npts: {self.pts}")
        self.dm.set_manpoints(self.role, l)
        # for p in self.pts['ref']:
        #     _, x, y = p.point.tolist()
        #     pts.append((x, y))
        # self.dm.set_manpoints('ref', pts)



    def draw_point_annotations(self):
        logger.info('Drawing point annotations...')
        try:
            anns = self.pts[self.role]
            if anns:
                with self.txn() as s:
                    s.layers['ann_points'].annotations = anns
        except:
            logger.warning('Unable to draw donut annotations or none to draw')


    def undrawSWIMwindows(self):
        try:
            with self.txn() as s:
                if s.layers['SWIM']:
                    if 'annotations' in s.layers['SWIM'].to_json().keys():
                        s.layers['SWIM'].annotations = None
        except:
            logger.warning('Something went wrong while undrawing SWIM windows')
            print_exception()



    # @functools.cache
    def drawSWIMwindow(self, z=None):
        if z == None:
            z = self.dm.zpos



        if z == self.dm.first_unskipped():
            return

        self._blockStateChanged = True

        # self.setMpData() #0805+

        self.undrawSWIMwindows()

        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Drawing SWIM windows...")


        # marker_size = 1
        marker_size = 0


        # if self.role == 'ref':
        #     self.index = self.dm.get_ref_index()
        # elif self.role == 'tra':
        #     self.index = self.dm.zpos  #

        # if self.dm.current_method == 'manual-hint':
        #     self.draw_point_annotations()
        #     return
        #

        # if self.dm.current_method == 'grid-custom':
        if self.dm.current_method == 'grid':
            logger.info('Method: SWIM Grid Alignment')

            img_siz = self.dm.image_size()
            img_w, img_h = img_siz[0], img_siz[1]
            ww_full = self.dm.swim_1x1_size() # full window width
            ww_2x2 = self.dm.swim_2x2_size() # 2x2 window width

            offset_x1 = ((img_w - ww_full[0]) / 2) + (ww_2x2[0] / 2)
            offset_x2 = img_w - offset_x1
            offset_y1 = ((img_h - ww_full[1]) / 2) + (ww_2x2[1] / 2)
            offset_y2 = img_h - offset_y1

            cps = []
            colors = []
            regions = self.dm.quadrants
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

        elif self.dm.current_method == 'manual':
            logger.info('Method: SWIM Match Region Alignment')
            self.restoreManAlignPts()
            # pts = list(self.pts.items())
            try:
                assert len(self.pts[self.role]) == len(self.dm.manpoints()[self.role])
            except:
                print_exception(extra=f"""len(self.pts[{self.role}]) = {len(self.pts[self.role])}\n
                len(self.dm.manpoints()[{self.role}]) = {len(self.dm.manpoints()[self.role])}""")
            annotations = []
            #Todo make this configurable, and check swim settings for manual 'mode'
            if self.dm.current_method == 'manual_strict':
                ww_x = 16
                ww_y = 16
            else:
                ww_x = ww_y = self.dm.manual_swim_window_px()

            for i, pt in enumerate(self.pts[self.role]):
                if pt:
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

        if self.dm.current_method in ('grid','manual'):
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
        logger.info(">>>> restoreManAlignPts >>>>")
        self.pts[self.role] = [None,None,None]
        pts_data = self.dm.getmpFlat(l=self.dm.zpos)[self.role]
        for i, p in enumerate(pts_data):
            if p:
                props = [self.colors[i], getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'),
                         getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'), ]
                self.pts[self.role][i] = ng.PointAnnotation(id=str(p), point=p, props=props)
        logger.info("<<<< restoreManAlignPts <<<<")


    def set_brightness(self, val=None):
        logger.info('')
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['brightness'] = val
            else:   layer.shaderControls['brightness'] = self.dm.brightness
            # layer.volumeRendering = True
        self.set_state(state)

    def set_contrast(self, val=None):
        logger.info('')
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val: layer.shaderControls['contrast'] = val
            else:   layer.shaderControls['contrast'] = self.dm.contrast
            # layer.volumeRendering = True
        self.set_state(state)

    def set_zmag(self, val=10):
        self._blockStateChanged = True
        try:
            state = copy.deepcopy(self.state)
            state.relativeDisplayScales = {'z': 2}
            self.set_state(state)
        except:
            logger.warning('Unable to set Z-mag')
            print_exception()
        self._blockStateChanged = False


    def _set_zmag(self):
        try:
            with self.txn() as s:
                s.relativeDisplayScales = {"z": 10}
        except:
            print_exception()


    def initZoom(self):
        logger.info(f'[{caller_name()}] [{self.role}] Calling initZoom...')
        adjust = 1.12
        if self.cs_scale:
            logger.info(f'[{self.role}] Initializing crossSectionScale to self.cs_scale ({self.cs_scale})')
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

            res_z, res_y, res_x = self.dm.resolution(s=self.dm.level) # nm per imagepixel
            # tissue_h, tissue_w = res_y*frame[0], res_x*frame[1]  # nm of sample
            scale_h = ((res_y * tensor_y) / widget_h) * 1e-9  # nm/pixel (subtract height of ng toolbar)
            scale_w = ((res_x * tensor_x) / widget_w) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)

            # logger.info(f'Setting crossSectionScale to max of {scale_h} and {scale_w}...')

            # logger.info(f'________{self.role}________')
            # logger.info(f'widget_w       = {widget_w}')
            # logger.info(f'widget_h       = {widget_h}')
            # logger.info(f'tensor_x       = {tensor_x}')
            # logger.info(f'tensor_y       = {tensor_y}')
            # logger.info(f'res_x          = {res_x}')
            # logger.info(f'res_y          = {res_y}')
            # logger.info(f'scale_h        = {scale_h}')
            # logger.info(f'scale_w        = {scale_w}')
            # logger.info(f'self.dm.level_key = {self.dm.level_key}')
            # logger.info(f'cs_scale       = {cs_scale}')

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
    
    
    
    
    
setMpData
    
x = 468.5921936035156, y = 395.48431396484375
p = PointAnnotation({"type": "point", "id": "(17, nan, nan)", "point": [17.0, NaN, NaN], "props": ["#ffe135", 3, 8]})
x = nan, y = nan
p = PointAnnotation({"type": "point", "id": "(17, nan, nan)", "point": [17.0, NaN, NaN], "props": ["#42d4f4", 3, 8]})
x = nan, y = nan


    
    
    
    
    
    
    
    
    '''