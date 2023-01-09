#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server'''

import os
import copy
import json
import pprint
import inspect
import logging
import datetime
import argparse
import traceback
from decimal import Decimal
from math import floor
import numpy as np
import numcodecs
numcodecs.blosc.use_threads = False
import zarr
import neuroglancer as ng
import neuroglancer.webdriver
from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QRunnable, QObject, Slot, Signal
import src.config as cfg
from src.funcs_zarr import get_zarr_tensor, get_zarr_tensor_layer, get_tensor_from_tiff
from src.helpers import print_exception, get_scale_val, exist_aligned_zarr, obj_to_string
from src.shaders import ann_shader

__all__ = ['NgHost']

import sys
import logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal(int)
    mpUpdate = Signal()

# class NgHost(QObject):
class NgHost(QRunnable):
# class NgHost:
    # def __init__(self, parent, src, scale, src, scale, bind='127.0.0.1', port=9000):
    def __init__(self, parent, bind='127.0.0.1', port=9000):
        QRunnable.__init__(self)
        self.parent = parent
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.url_viewer = None
        self.ref_pts = []
        self.base_pts = []
        self.bind = bind
        self.port = port
        self.scale = None
        self.zarr_addr = "zarr://http://localhost:" + str(self.port)
        self.mp_colors = ['#f3e375', '#5c4ccc', '#d6acd6',
                          '#aaa672', '#152c74', '#404f74',
                          '#f3e375', '#5c4ccc', '#d6acd6',
                          '#aaa672', '#152c74', '#404f74']
        self.mp_count = 0
        self._is_fullscreen = False
        self.arrangement = 1
        self.mp_mode = False

    def __del__(self):
        try:
            caller = inspect.stack()[1].function
            logger.warning('__del__ was called by [%s] on NgHost for s %s created:%s' % (caller, self.scale, self.created))
        except:
            logger.warning('Lost Track Of Caller')


    def __str__(self):
        return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(cfg.viewer.state)

    # @Slot()
    async def run(self):
        print('\nrun:\n')
        try:
            cfg.viewer = ng.Viewer()
        except:
            # traceback.print_exc()
            logger.error('ERROR')

    def get_loading_progress(self):
        return neuroglancer.webdriver.driver.execute_script('''
    const userLayer = viewer.layerManager.getLayerByName("segmentation").layer;
    return userLayer.renderLayers.map(x => x.layerChunkProgressInfo)
     ''')

    def request_layer(self):
        return floor(cfg.viewer.state.position[0])

    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()

    def invalidateAllLayers(self):
        if cfg.data.is_mendenhall():
            cfg.menLV.invalidate()
            return

        cfg.refLV.invalidate()
        cfg.baseLV.invalidate()
        try:
            cfg.alLV.invalidate()
        except:
            pass

    def initViewerMendenhall(self):
        logger.critical('Initializing Neuroglancer viewer (Mendenhall)...')
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
        print('Instantiating Viewer...')
        cfg.viewer = ng.Viewer()
        self.url_viewer = str(cfg.viewer)
        image_size = cfg.data.image_size()
        widget_size = cfg.project_tab.getBrowserSize()
        print(f'\nwidget_size = {widget_size}\n')

        widget_height = widget_size[3]
        tissue_height = 2 * image_size[1]  # nm
        cross_section_height = (tissue_height / widget_height) * 1e-9  # nm/pixel
        tissue_width = 2 * image_size[0]  # nm
        cross_section_width = (tissue_width / image_size[0]) * 1e-9  # nm/pixel
        cross_section_scale = max(cross_section_height, cross_section_width)
        css = '%.2E' % Decimal(cross_section_scale)
        # logger.info(f'cross_section_scale: {css}')

        with cfg.viewer.txn() as s:
            s.layers['layer'] = ng.ImageLayer(source=cfg.menLV)
            s.crossSectionBackgroundColor = '#808080'
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1

        # self.webdriver = neuroglancer.webdriver.Webdriver(cfg.viewer, headless=True)

    def initViewer(self,
                   matchpoint=None,
                   widget_size=None,
                   show_ui_controls=True,
                   show_panel_borders=False,
                   show_scale_bar=False,
                   show_axis_lines=False
                   ):
        caller = inspect.stack()[1].function
        if matchpoint: self.mp_mode = matchpoint
        ng.server.debug = cfg.DEBUG_NEUROGLANCER
        self.scale = cfg.data.scale()
        print(f'Initializing Neuroglancer Viewer ({cfg.data.scale_pretty(s=self.scale)})...')
        is_aligned = exist_aligned_zarr(self.scale)
        sf = get_scale_val(self.scale)
        self.ref_l, self.base_l, self.aligned_l  = 'ref_%d'%sf, 'base_%d'%sf, 'aligned_%d'%sf

        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        self.nglayout = mapping[cfg.main_window._cmbo_ngLayout.currentText()]
        self.al_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(sf))
        self.unal_path = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(sf))

        try:    cfg.unal_tensor = cfg.tensor = get_zarr_tensor(self.unal_path).result()
        except: cfg.main_window.err(f'Invalid Zarr For Tensor, Unaligned, Scale {sf}'); print_exception()
        cfg.main_window.updateToolbar()
        if is_aligned:
            try:    cfg.al_tensor = cfg.tensor = get_zarr_tensor(self.al_path).result()
            except: cfg.main_window.err(f'Invalid Zarr For Tensor, Aligned, Scale {sf}'); print_exception()

        if cfg.data.is_mendenhall():
            self.unal_path = os.path.join(cfg.data.dest(), 'mendenhall.zarr', 'grp')
            is_aligned = True  # Force, was below the conditional
            if cfg.MV:
                logger.warning('Transferring control to initViewerMendenhall...')
                self.initViewerMendenhall()
                return

        coord_space = [cfg.data.res_z(s=self.scale), cfg.data.res_y(s=self.scale), cfg.data.res_x(s=self.scale)]
        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm','nm','nm'],
            scales=coord_space,
        )

        # cfg.viewer = ng.UnsynchronizedViewer()
        cfg.viewer = ng.Viewer()
        self.url_viewer = str(cfg.viewer)
        self.mp_marker_size = cfg.data['user_settings']['mp_marker_size']
        self.mp_marker_lineweight = cfg.data['user_settings']['mp_marker_lineweight']

        if is_aligned:
            frame = cfg.al_tensor.shape[1:] # [height, width]
            x_nudge = (frame[1] - cfg.unal_tensor.shape[2]) / 2
            y_nudge = (frame[0] - cfg.unal_tensor.shape[1]) / 2
        else:
            frame = cfg.unal_tensor.shape[1:]
            x_nudge, y_nudge = 0, 0

        if widget_size is None:
            widget_size = cfg.project_tab.geometry().getRect()
        # widget_height = widget_size[3] - 36 # subtract pixel height of Neuroglancer toolbar
        widget_height = widget_size[3] - 40 # subtract pixel height of Neuroglancer toolbar

        if self.arrangement == 1:
            if is_aligned: widget_width = widget_size[2] / 3
            else:          widget_width = widget_size[2] / 2
        else:
            widget_width = widget_size[2] / 2

        tissue_height = cfg.data.res_y(s=self.scale) * frame[0]  # nm
        cross_section_height = (tissue_height / widget_height) * 1e-9  # nm/pixel
        tissue_width = cfg.data.res_x(s=self.scale) * frame[1]  # nm
        cross_section_width = (tissue_width / widget_width) * 1e-9  # nm/pixel
        cross_section_scale = max(cross_section_height, cross_section_width)

        # print('frame[0], frame[1]           =%d,%d' % (frame[0], frame[1]))
        # print('widget size                  =%s' % str(widget_size))
        # print('arrangement                  =%d' % self.arrangement)
        # print('is aligned                   =%s' % is_aligned)
        # print('has bounding box             =%s' % cfg.data.has_bb(s=self.scale))
        # print('nudge_x,nudge_y              =%d,%d' % (x_nudge, y_nudge))
        # print('frame width,height           =%d,%d' % (frame[1], frame[0]))
        # print('x_nudge,y_nudge              =%d,%d' % (x_nudge, y_nudge))
        # print('widget width,height          =%d,%d' % (widget_width, widget_height))
        # print('tissue width,height          =%d,%d' % (tissue_width, tissue_height))
        # print('cross_section width,height   =%.10f,%.10f' % (cross_section_width, cross_section_height))
        # print('cross_section_scale          =%.10f' % cross_section_scale)

        with cfg.viewer.txn() as s:
            adjustment = 1.06
            # s.gpu_memory_limit = -1
            # s.system_memory_limit = -1
            # s.concurrent_downloads = 512
            s.cross_section_scale = cross_section_scale * adjustment
            s.show_scale_bar = show_scale_bar
            s.show_axis_lines = show_axis_lines
            # s.perspective_orientation
            # s.relative_display_scales = [32, 1, 1] #Todo inspect this

            cfg.refLV = ng.LocalVolume(
                data=cfg.unal_tensor,
                volume_type='image',
                dimensions=self.coordinate_space,
                voxel_offset=[1, y_nudge, x_nudge],
            )
            cfg.baseLV = ng.LocalVolume(
                data=cfg.unal_tensor,
                volume_type='image',
                dimensions=self.coordinate_space,
                voxel_offset=[0, y_nudge, x_nudge],
            )
            if is_aligned:
                cfg.alLV = ng.LocalVolume(
                    data=cfg.al_tensor,
                    volume_type='image',
                    dimensions=self.coordinate_space,
                    voxel_offset=[0, ] * 3,
                )

            # # Not using TensorStore, so point Neuroglancer directly to local Zarr on disk.
            # cfg.refLV = cfg.baseLV = f'zarr://http://localhost:{self.port}/{self.unal_path}'
            # if is_aligned:  cfg.alLV = f'zarr://http://localhost:{self.port}/{self.al_path}'

            s.layers[self.ref_l] = ng.ImageLayer(source=cfg.refLV, shader=cfg.SHADER)
            s.layers[self.base_l] = ng.ImageLayer(source=cfg.baseLV, shader=cfg.SHADER)
            if is_aligned: s.layers[self.aligned_l] = ng.ImageLayer(source=cfg.alLV, shader=cfg.SHADER)

            s.layers['mp_ref'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotations=self.pt2ann(points=cfg.data.get_mps(role='ref')),
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='ptColor', type='rgb', default='white',),
                    ng.AnnotationPropertySpec(id='ptWidth', type='float32', default=3),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=7)
                ],
                shader=ann_shader,
            )

            s.layers['mp_base'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotations=self.pt2ann(
                    points=cfg.data.get_mps(role='base')) + self.base_pts,
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='ptColor', type='rgb', default='white', ),
                    ng.AnnotationPropertySpec(id='ptWidth', type='float32', default=3),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=7)
                ],
                shader=ann_shader,
            )

            grps = []
            grps.append(ng.LayerGroupViewer(layers=[self.ref_l, 'mp_ref'], layout=self.nglayout))
            grps.append(ng.LayerGroupViewer(layers=[self.base_l, 'mp_base'], layout=self.nglayout))
            if is_aligned:
                grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout=self.nglayout))

            s.position = [cfg.data.layer(), frame[0]/2, frame[1]/2]

            if self.arrangement == 1:
                s.layout = ng.row_layout(grps)

            if self.arrangement == 2:
                if is_aligned:
                    s.layout = ng.row_layout([
                        ng.column_layout([
                            ng.LayerGroupViewer(layers=[self.ref_l, 'mp_ref'], layout=self.nglayout),
                            ng.LayerGroupViewer(layers=[self.base_l, 'mp_base'], layout=self.nglayout),
                        ]),
                        ng.column_layout([
                            ng.LayerGroupViewer(layers=[self.aligned_l], layout=self.nglayout),
                        ]),
                    ])
                else:
                    s.layout = ng.row_layout(grps)

            # cfg.viewer.shared_state.add_changed_callback(self.on_state_changed)
            cfg.viewer.shared_state.add_changed_callback(lambda: cfg.viewer.defer_callback(self.on_state_changed))

            # s.layers['mp_ref'].annotations = self.pt2ann(points=cfg.datamodel.get_mps(role='ref'))
            # s.layers['mp_base'].annotations = self.pt2ann(points=cfg.datamodel.get_mps(role='base'))

            if cfg.THEME == 0:    s.crossSectionBackgroundColor = '#808080'
            elif cfg.THEME == 1:  s.crossSectionBackgroundColor = '#FFFFE0'
            elif cfg.THEME == 2:  s.crossSectionBackgroundColor = '#808080'  # 128 grey
            elif cfg.THEME == 3:  s.crossSectionBackgroundColor = '#0C0C0C'
            else:                 s.crossSectionBackgroundColor = '#004060'

        if self.mp_mode:
            mp_key_bindings = [
                ['enter', 'add_matchpoint'],
                ['keys', 'save_matchpoints'],
                ['keyc', 'clear_matchpoints'],
            ]
            cfg.viewer.actions.add('add_matchpoint', self.add_matchpoint)
            cfg.viewer.actions.add('save_matchpoints', self.save_matchpoints)
            cfg.viewer.actions.add('clear_matchpoints', self.clear_matchpoints)
        else:
            mp_key_bindings = []

        with cfg.viewer.config_state.txn() as s:
            for key, command in mp_key_bindings:
                s.input_event_bindings.viewer[key] = command
            s.show_ui_controls = show_ui_controls
            s.show_panel_borders = show_panel_borders

        self._layer = self.request_layer()
        self.clear_mp_buffer()
        cfg.url = str(cfg.viewer)
        if cfg.HEADLESS:
            cfg.webdriver = neuroglancer.webdriver.Webdriver(cfg.viewer, headless=False, browser='chrome')


    def on_state_changed(self):
        try:
            request_layer = floor(cfg.viewer.state.position[0])
            if request_layer == self._layer:
                logger.debug('State Changed, But Layer Is The Same - Suppressing The Callback Signal')
                return
            else:
                self._layer = request_layer
            self.signals.stateChanged.emit(request_layer)
            if self.mp_mode:
                self.clear_mp_buffer()
        except:
            # print_exception()
            logger.error('ERROR')


    def add_matchpoint(self, s):
        logger.info('add_matchpoint:')
        assert self.mp_mode == True
        coords = np.array(s.mouse_voxel_coordinates)
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless!')
            return
        try:
            bounds = cfg.unal_tensor.shape[1:]
            if (coords[1] < 0) or (coords[2] < 0):
                logger.warning('Invalid match point (%.3fx%.3f), outside the image bounds(%dx%d)'
                               % (coords[1], coords[2], bounds[0], bounds[1]))
                return
            if (coords[1] > bounds[0]) or (coords[2] > bounds[1]):
                logger.warning('Invalid match point (%.3fx%.3f), outside the image bounds(%dx%d)'
                               % (coords[1], coords[2], bounds[0], bounds[1]))
        except:
            # print_exception()
            logger.error('ERROR')

        n_mp_pairs = floor(self.mp_count / 2)
        props = [self.mp_colors[n_mp_pairs], self.mp_marker_lineweight, self.mp_marker_size, ]
        with cfg.viewer.txn() as s:
            if self.mp_count in range(0, 100, 2):
                self.ref_pts.append(ng.PointAnnotation(id=repr(coords), point=coords, props=props))
                s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref')) + self.ref_pts
                logger.info(f"Ref Match Point Added: {coords}")
            elif self.mp_count in range(1, 100, 2):
                self.base_pts.append(ng.PointAnnotation(id=repr(coords), point=coords, props=props))
                s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base')) + self.base_pts
                logger.info(f"Base Match Point Added: {coords}")
        self.mp_count += 1


    def save_matchpoints(self, s):
        layer = self.request_layer()
        logger.info('Saving Match Points for Layer %d\nBase Name: %s' % (layer, cfg.data.base_image_name(l=layer)))
        n_ref, n_base = len(self.ref_pts), len(self.base_pts)
        if n_ref != n_base:
            cfg.main_window.hud.post(f'Each image must have the same # points\n'
                                     f'Left img has: {len(self.ref_pts)}\n'
                                     f'Right img has: {len(self.base_pts)}', logging.WARNING)
            return

        cfg.data.clear_match_points(s=self.scale, l=layer)
        p_r = [p.point.tolist() for p in self.ref_pts]
        p_b = [p.point.tolist() for p in self.base_pts]
        ref_mps = [p_r[0][1::], p_r[1][1::], p_r[2][1::]]
        base_mps = [p_b[0][1::], p_b[1][1::], p_b[2][1::]]
        cfg.data.set_match_points(role='ref', matchpoints=ref_mps, l=layer)
        cfg.data.set_match_points(role='base', matchpoints=base_mps, l=layer)
        cfg.data.set_selected_method(method="Match Point Align", l=layer)
        self.clear_mp_buffer()
        cfg.refLV.invalidate()
        cfg.baseLV.invalidate()
        cfg.data.print_all_match_points()
        cfg.main_window.hud.post('Match Points Saved!')


    def clear_matchpoints(self, s):
        logger.info('Clearing Match Points...')
        layer = self.request_layer()
        cfg.data.clear_match_points(s=self.scale, l=layer)  # Note
        cfg.data.set_selected_method(method="Auto Swim Align", l=layer)
        self.clear_mp_buffer()  # Note
        with cfg.viewer.txn() as s:
            s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref'))
            s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base'))
        cfg.refLV.invalidate()
        cfg.baseLV.invalidate()
        cfg.main_window.hud.post('Match Points for Layer %d Erased' % layer)


    def clear_mp_buffer(self):
        if self.mp_mode:
            # logger.info('Clearing match point buffer...')
            self.mp_count = 0
            self.ref_pts.clear()
            self.base_pts.clear()
            try:
                cfg.refLV.invalidate()
                cfg.baseLV.invalidate()
            except:
                pass


    def count_saved_points_ref(self):
        layer = self.request_layer()
        points = self.pt2ann(points=cfg.data.get_mps(role='ref'))
        points_ = [p.point.tolist() for p in points]
        count = 0
        for p in points_:
            if p[0] == layer:
                count += 1
        return count


    def count_saved_points_base(self):
        layer = self.request_layer()
        points = self.pt2ann(points=cfg.data.get_mps(role='base'))
        points_ = [p.point.tolist() for p in points]
        count = 0
        for p in points_:
            if p[0] == layer:
                count += 1
        return count

    def pt2ann(self, points: list):
        annotations = []
        for i, point in enumerate(points):
            annotations.append(ng.PointAnnotation(id=repr(point),
                                                  point=point,
                                                  props=[self.mp_colors[i % 3],
                                                         self.mp_marker_size,
                                                         self.mp_marker_lineweight]))
        return annotations


    def take_screenshot(self, directory=None):
        if directory is None:
            directory = cfg.data.dest()
        ss = ScreenshotSaver(viewer=cfg.viewer, directory=dir)
        ss.capture()


    def url(self):
        # str(cfg.viewer)
        return cfg.url


    def show_state(self):
        cfg.main_window.hud.post('Neuroglancer State:\n\n%s' % ng.to_url(cfg.viewer.state))


    def print_viewer_info(self, s):
        logger.info(f'Selected Values:\n{s.selected_values}')
        logger.info(f'Current Layer:\n{cfg.viewer.state.position[0]}')
        logger.info(f'Viewer State:\n{cfg.viewer.state}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    NgHost(args.source, args.bind, args.port)
