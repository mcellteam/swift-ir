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
from src.funcs_zarr import get_zarr_tensor
from src.helpers import getOpt, obj_to_string, print_exception
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
    def __init__(self, name=''):
        super().__init__()
        logger.info('')
        self.name=name
        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        self._layer = None
        self.cs_scale = None
        self.ref_pts = []
        self.base_pts = []
        self.mp_colors = ['#f3e375', '#5c4ccc', '#800000',
                          '#aaa672', '#152c74', '#404f74',
                          '#f3e375', '#5c4ccc', '#d6acd6',
                          '#aaa672', '#152c74', '#404f74']
        self._crossSectionScale = 1
        self._mpCount = 0
        self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        logger.info('viewer constructed!')


    def __del__(self):
        try:
            caller = inspect.stack()[1].function
            logger.warning('__del__ called by [%s] on EMViewer (created: %s)'
                           % (caller, self.created))
        except:
            logger.warning('Lost Track Of Caller')

    # def __str__(self):
    #     return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.state)

    def request_layer(self):
        return math.floor(self.state.position[0])

    def invalidateAlignedLayers(self):
        cfg.alLV.invalidate()

    def set_zmag(self):
        if cfg.MP_MODE:
            with self.txn() as s:
                s.relativeDisplayScales = {"z": 10} # this should work, but does not work. ng bug.


    def set_layer(self, l:int):
        state = copy.deepcopy(self.state)
        state.position[0] = l
        self.set_state(state)

    def initViewerMendenhall(self):
        logger.critical('Initializing Neuroglancer EMViewer (Mendenhall)...')
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

    def initViewer(self, matchpoint=False):

        if cfg.main_window.rb0.isChecked():
            self.initViewerSlim(nglayout='4panel')
        elif cfg.main_window.rb1.isChecked():
            self.initViewerSbs(nglayout='xy', matchpoint=matchpoint)


    def initViewerSbs(self, nglayout=None, matchpoint=False):

        # logger.critical(f'passed arg: {nglayout}')
        if nglayout == None:
            nglayout = cfg.data['ui']['ng_layout']

        # logger.critical(f'passed arg: {nglayout}')

        caller = inspect.stack()[1].function
        logger.critical(f'Initializing EMViewer (caller: {caller})....')
        if cfg.data.is_mendenhall(): self.initViewerMendenhall(); return

        self.clear_layers()
        self.make_local_volumes()

        is_aligned = cfg.data.is_aligned_and_generated()
        if is_aligned:
            tensor_z, tensor_y, tensor_x = cfg.al_tensor.shape
        else:
            tensor_z, tensor_y, tensor_x = cfg.unal_tensor.shape

        self.set_pos_and_zoom()
        sf = cfg.data.scale_val(s=cfg.data.scale())
        self.ref_l, self.base_l, self.aligned_l = 'ref_%d' % sf, 'base_%d' % sf, 'aligned_%d' % sf

        self.grps = []
        if matchpoint:
            self.grps.append(ng.LayerGroupViewer(layers=[self.ref_l, 'mp_ref'], layout=nglayout))
            self.grps.append(ng.LayerGroupViewer(layers=[self.base_l, 'mp_base'], layout=nglayout))
            if is_aligned:
                self.grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout=nglayout))
        else:
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
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            if cfg.MP_MODE:
                s.relativeDisplayScales = {"z": 10} # this should work, but does not work. ng bug.
            s.crossSectionBackgroundColor = '#808080'
            s.layout.type = nglayout
            s.layers[self.ref_l] = ng.ImageLayer(source=cfg.refLV, shader=cfg.SHADER,)
            s.layers[self.base_l] = ng.ImageLayer(source=cfg.baseLV, shader=cfg.SHADER,)
            if is_aligned: s.layers[self.aligned_l] = ng.ImageLayer(source=cfg.alLV, shader=cfg.SHADER,)
            # if matchpoint:
            s.showSlices=False


            # if cfg.main_window.rb2.isChecked():
            #     self.set_row_layout(nglayout=nglayout) # row
            # else:
            s.layout = ng.row_layout(self.grps)  # col
            s.position = [cfg.data.layer(), tensor_y / 2, tensor_x / 2]
            # if matchpoint:
            # s.layers['mp_ref'].annotations = self.pt2ann(points=cfg.data.get_mps(role='ref'))
            # s.layers['mp_base'].annotations = self.pt2ann(points=cfg.data.get_mps(role='base'))  # ???

        mp_key_bindings = []

        # if cfg.MP_MODE:
        self.add_matchpoint_layers()

        if matchpoint:
            mp_key_bindings = [
                ['enter', 'add_matchpoint'],
                ['keys', 'save_matchpoints'],
                ['keyc', 'clear_matchpoints'],
            ]
            self.actions.add('add_matchpoint', self.add_matchpoint)
            self.actions.add('save_matchpoints', self.save_matchpoints)
            self.actions.add('clear_matchpoints', self.clear_matchpoints)


        with self.config_state.txn() as s:
            for key, command in mp_key_bindings:
                s.input_event_bindings.viewer[key] = command
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = getOpt('neuroglancer,SHOW_PANEL_BORDERS')

        self._layer = math.floor(self.state.position[0])


        if matchpoint:
            self.clear_mp_buffer()

        if cfg.main_window.detachedNg.view.isVisible():
            cfg.main_window.detachedNg.open(url=self.get_viewer_url())


        self._crossSectionScale = self.state.cross_section_scale

        cfg.main_window.updateToolbar()


    def initViewerSlim(self, nglayout=None):
        caller = inspect.stack()[1].function
        logger.critical(f'Initializing EMViewer Slim (caller: {caller})....')
        if nglayout == None:
            nglayout = cfg.data['ui']['ng_layout']

        self.clear_layers()
        self.make_local_volumes()

        zd = ('img_src.zarr', 'img_aligned.zarr')[cfg.data.is_aligned_and_generated()]
        path = os.path.join(cfg.data.dest(), zd, 's' + str(cfg.data.scale_val()))
        if not os.path.exists(path):
            cfg.main_window.warn('Zarr Not Found: %s' % path)
            return
        try:
            if cfg.USE_TENSORSTORE:
                cfg.tensor = store = get_zarr_tensor(path).result()
            else:
                logger.info('Opening Zarr...')
                store = zarr.open(path)
        except:
            print_exception()
            cfg.main_window.warn('There was a problem loading tensor at %s' % path)
            cfg.main_window.warn('Trying with regular Zarr datastore...')
            try:
                store = zarr.open(path)
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

        with self.txn() as s:

            s.layout.type = nglayout
            s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.show_scale_bar = getOpt('neuroglancer,SHOW_SCALE_BAR')
            s.show_axis_lines = getOpt('neuroglancer,SHOW_AXIS_LINES')
            s.position=[cfg.data.layer(), store.shape[1]/2, store.shape[2]/2]
            if cfg.data.is_aligned_and_generated():
                s.layers['layer'] = ng.ImageLayer(
                    source=cfg.alLV,
                    shader=cfg.SHADER,
                    # tool_bindings={
                    #     'A': neuroglancer.ShaderControlTool(control='normalized'),
                    #     'B': neuroglancer.OpacityTool(),
                    # },
                )
            else:
                s.layers['layer'] = ng.ImageLayer(
                    source=cfg.baseLV,
                    shader=cfg.SHADER,
                    # shaderControls=typed_string_map({"normalized": typed_string_map({"range": [31, 255]})})
                    # shaderControls = typed_string_map({"normalized": {"range": [31, 255]}})
                )
            s.crossSectionBackgroundColor = '#808080' # 128 grey
            # s.layout = {
            #     "type": "4panel",
            #     "crossSections": {
            #       "a": {
            #         "width": store.shape[1],
            #         "height": store.shape[2]
            #       }
            #     }
            #   }

        with self.config_state.txn() as s:
            s.show_ui_controls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            s.show_panel_borders = getOpt('neuroglancer,SHOW_PANEL_BORDERS')
            # s.viewer_size = [100,100]

        self._layer = self.request_layer()
        # self.shared_state.add_changed_callback(self.on_state_changed)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

        # if cfg.main_window.detachedNg.view.isVisible():
        #     cfg.main_window.detachedNg.open(url=self.get_viewer_url())

        cfg.main_window.updateToolbar()


    def set_pos_and_zoom(self):

        if self.cs_scale:
            with self.txn() as s:
                s.crossSectionScale = self.cs_scale
        else:

            area = cfg.main_window.globTabs.geometry().getRect()
            if cfg.data.is_aligned_and_generated():
                tensor_z, tensor_y, tensor_x = cfg.al_tensor.shape
            else:
                tensor_z, tensor_y, tensor_x = cfg.unal_tensor.shape

            if cfg.main_window.rb1.isChecked():
                widget_w = (area[2] / 2, area[2] / 3)[cfg.data.is_aligned_and_generated()]
            else:
                widget_w = area[2] / 2
            widget_h = area[3]
            res_z, res_y, res_x = cfg.data.resolution(s=cfg.data.scale()) # nm per imagepixel
            # tissue_h, tissue_w = res_y*frame[0], res_x*frame[1]  # nm of sample
            scale_h = ((res_y*tensor_y) / (widget_h - 34)) * 1e-9  # nm/pixel (subtract height of ng toolbar)
            scale_w = ((res_x*tensor_x) / (widget_w - 20)) * 1e-9  # nm/pixel (subtract width of sliders)
            cs_scale = max(scale_h, scale_w)

            # logger.info('res_y    = %s' % str(res_y))
            # logger.info('area[3]  = %s' % (str(area[3])))
            # logger.info('nm/pixel (height)    : %.11f' % scale_h)
            # logger.info('nm/pixel (width)     : %.11f' % scale_w)
            # logger.info('zoom factor          : %.11f' % cs_scale)

            with self.txn() as s:
                s.crossSectionScale = cs_scale * 1.06
    #
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
        # caller = inspect.stack()[1].function
        # logger.info('caller: %s' % caller)

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
                    if cfg.MP_MODE:
                        self.clear_mp_buffer()

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


    def add_matchpoint(self, s):
        if cfg.MP_MODE:
            logger.critical(str(s))
            logger.info('add_matchpoint:')
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
                    return
            except:
                print_exception()

            n_mp_pairs = math.floor(self._mpCount / 2)

            props = [self.mp_colors[n_mp_pairs],
                     cfg.main_window.mp_marker_lineweight_spinbox.value(),
                     cfg.main_window.mp_marker_size_spinbox.value(), ]
            with self.txn() as s:
                s.relativeDisplayScales = {"z": 10}  # this should work, but does not work. ng bug.

                if self._mpCount in range(0, 100, 2):
                    self.ref_pts.append(ng.PointAnnotation(id=repr(coords), point=coords, props=props))
                    s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref')) + self.ref_pts
                    logger.info(f"Ref Match Point Added: {coords}")
                elif self._mpCount in range(1, 100, 2):
                    self.base_pts.append(ng.PointAnnotation(id=repr(coords), point=coords, props=props))
                    s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base')) + self.base_pts
                    logger.info(f"Base Match Point Added: {coords}")
            self._mpCount += 1


    def save_matchpoints(self, s):
        if cfg.MP_MODE:
            layer = self.request_layer()
            logger.info('Saving Match Points for Layer %d\nBase Name: %s' % (layer, cfg.data.base_image_name(l=layer)))
            n_ref, n_base = len(self.ref_pts), len(self.base_pts)
            if n_ref == n_base:
                cfg.data.clear_match_points(s=cfg.data.scale(), l=layer)
                p_r = [p.point.tolist() for p in self.ref_pts]
                p_b = [p.point.tolist() for p in self.base_pts]
                logger.critical('p_r: %s' %str(p_r))
                logger.critical('p_b: %s' %str(p_b))
                ref_mps = [p_r[0][1::], p_r[1][1::], p_r[2][1::]]
                base_mps = [p_b[0][1::], p_b[1][1::], p_b[2][1::]]
                cfg.data.set_match_points(role='ref', matchpoints=ref_mps, l=layer)
                cfg.data.set_match_points(role='base', matchpoints=base_mps, l=layer)
                cfg.data.set_selected_method(method="Match Point Align", l=layer)
                self.clear_mp_buffer()
                # cfg.refLV.invalidate()
                # cfg.baseLV.invalidate()
                cfg.data.print_all_match_points()
                self.signals.mpUpdate.emit()
                cfg.main_window._saveProjectToFile(silently=True)
                cfg.main_window.hud.post('Match Points Saved!')
            else:
                cfg.main_window.hud.post(f'Each image must have the same # points\n'
                                         f'Left img has: {len(self.ref_pts)}\n'
                                         f'Right img has: {len(self.base_pts)}', logging.WARNING)

    def clear_matchpoints(self, s):
        if cfg.MP_MODE:
            layer = self.request_layer()
            logger.info('Clearing %d match points for section #%d...' %(self._mpCount,layer))
            cfg.main_window.hud.post('Clearing %d match points for section #%d...' %(self._mpCount,layer))
            cfg.data.clear_match_points(s=cfg.data.scale(), l=layer)  # Note
            cfg.data.set_selected_method(method="Auto Swim Align", l=layer)
            self.clear_mp_buffer()  # Note
            with self.txn() as s:
                s.relativeDisplayScales = {"z": 10}  # this should work, but does not work. ng bug.
                s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref'))
                s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base'))
            # cfg.refLV.invalidate()
            # cfg.baseLV.invalidate()
            cfg.main_window.hud.post('Match Points for Layer %d Erased' % layer)
            cfg.main_window.updateDetailsWidget()


    def clear_mp_buffer(self):
        if cfg.MP_MODE:
            logger.info('Clearing match point buffer of %d match points...' % self._mpCount)
            self._mpCount = 0
            self.ref_pts.clear()
            self.base_pts.clear()
            # try:
            #     cfg.refLV.invalidate()
            #     cfg.baseLV.invalidate()
            # except:
            #     pass


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


    # def take_screenshot(self, directory=None):
    #     if directory is None:
    #         directory = cfg.data.dest()
    #     ss = ScreenshotSaver(viewer=self, directory=directory)
    #     ss.capture()


    def url(self):
        return self.get_viewer_url()

    def get_layout(self):

        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        val = mapping[cfg.main_window.comboboxNgLayout.currentText()]
        # logger.critical('RETURNING: %s' % val)
        return val


    def clear_layers(self):
        if self.state.layers:
            logger.info('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)

    def add_matchpoint_layers(self):
        logger.info('')

        with self.txn() as s:
            s.layers['mp_ref'] = ng.LocalAnnotationLayer(
                dimensions=self.coordinate_space,
                annotations=self.pt2ann(points=cfg.data.get_mps(role='ref')),
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='ptColor', type='rgb', default='white', ),
                    ng.AnnotationPropertySpec(id='ptWidth', type='float32', default=3),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=7)
                ],
                shader=copy.deepcopy(ann_shader),
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
                shader=copy.deepcopy(ann_shader),
            )

    def set_row_layout(self, nglayout):

        with self.txn() as s:
            if cfg.data.is_aligned_and_generated():
                if cfg.MP_MODE:
                    s.layout = ng.row_layout([
                        ng.column_layout([
                            ng.LayerGroupViewer(layers=[self.ref_l, 'mp_ref'], layout=nglayout),
                            ng.LayerGroupViewer(layers=[self.base_l, 'mp_base'], layout=nglayout),
                        ]),
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

        self.coordinate_space = ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=list(cfg.data.resolution(s=cfg.data.curScale)),
        )

        x_nudge, y_nudge = self.get_nudge()
        cfg.refLV = ng.LocalVolume(
            volume_type='image',
            data=cfg.unal_tensor[0:cfg.data.nSections - 1, :, :],
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
