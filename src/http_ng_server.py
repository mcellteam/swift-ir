#!/usr/bin/env python3

"""WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server"""

'''
old app:
type(match_point_data) = <class 'list'>
match_point_data = [584.021484375, 696.3277343750001]



cfg.main_window.ng_workers['scale_4'].refLV.info()

'''

import os
import copy
import shutil
import atexit
import inspect
import logging
import datetime
import argparse
import tempfile
from math import floor
import numpy as np

import neuroglancer as ng
from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QRunnable, QObject, Slot, Signal

import src.config as cfg
# from src.funcs_ng import SimpleHTTPServer, launch_server, write_some_annotations
from src.funcs_ng import launch_server
from src.funcs_zarr import get_zarr_tensor, get_zarr_tensor_layer, get_tensor_from_tiff
from src.helpers import print_exception, get_scale_val, is_arg_scale_aligned, obj_to_string
from src.shaders import ann_shader


__all__ = ['NgHost']

logger = logging.getLogger(__name__)

KEEP_RUNNING = True


def keep_running():
    return KEEP_RUNNING


class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal(int)
    mpUpdate = Signal()


class NgHost(QRunnable):
    # stateChanged = Signal(str)

    def __init__(self, src, scale, bind='127.0.0.1', port=9000):
        super(NgHost, self).__init__()

        self.signals = WorkerSignals()
        self.created = datetime.datetime.now()
        # self.viewer = ng.Viewer()
        self.viewer_url = None
        self.ref_pts = []
        self.base_pts = []
        self.src = src
        self.port = port
        self.scale = scale
        scales  = [cfg.data.res_z(s=scale), cfg.data.res_y(s=scale), cfg.data.res_x(s=scale)]
        self.coordinate_space = ng.CoordinateSpace(names=['z', 'y', 'x'], units='nm', scales=scales, )
        self.sf = get_scale_val(scale)  # s factor
        self.ref_l = 'ref_%d' % self.sf
        self.base_l = 'base_%d' % self.sf
        self.aligned_l = 'aligned_%d' % self.sf
        self.layout = 'yz'  # maps to 'xy'
        self.al_url = os.path.join('img_aligned.zarr', 's' + str(self.sf))
        self.src_url = os.path.join('img_src.zarr', 's' + str(self.sf))
        self.zarr_addr = "zarr://http://localhost:" + str(self.port)
        self.al_name = os.path.join(src, self.al_url)
        self.unal_name = os.path.join(src, self.src_url)
        self.src_size = cfg.data.image_size(s=self.scale)
        self.mp_colors = ['#0072b2']*2 + ['#f0e442']*2 + ['#FF0000']*2
        self.mp_count = 0
        self._is_fullscreen = False

    def __del__(self):
        caller = inspect.stack()[1].function
        logger.info('__del__ was called by [%s] on NgHost for s %s created:%s' % (caller, self.sf, self.created))

    def __str__(self):
        return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.viewer.state)


    @Slot()
    def run(self):
        logger.info('Launching Tornado HTTP Server (Scale %d)...' % self.sf)
        try:
            tempdir = tempfile.mkdtemp()
            atexit.register(shutil.rmtree, tempdir)
            self.server_url = launch_server(bind_address='127.0.0.1', output_dir=tempdir)
        except:
            print_exception()


    def initViewer(self, viewers='ref, base, aligned'):
        self.match_point_mode = cfg.main_window._is_mp_mode
        # logger.info('Initializing Viewer (caller: %s):' % inspect.stack()[1].function)
        is_aligned = is_arg_scale_aligned(self.scale)
        # is_aligned = is_arg_scale_aligned(cfg.data.s())
        logger.info('Initializing Viewer, Scale %d, aligned? %s...' % (self.sf, is_aligned))
        cfg.main_window.hud.post('Initializing Neuroglancer Viewer (Scale %d)...' % self.sf)

        if self.match_point_mode:
            self.clear_mp_buffer()

        # self.viewer = ng.UnsynchronizedViewer()
        self.viewer = ng.Viewer() #1108+
        self.viewer_url = str(self.viewer)
        self.mp_marker_size = cfg.data['user_settings']['mp_marker_size']
        self.mp_marker_lineweight = cfg.data['user_settings']['mp_marker_lineweight']
        # logger.info('Match Point Mode  : %s' % str(self.match_point_mode))
        # logger.info('Shader            : %s' % str(cfg.SHADER))
        # logger.info('Is Aligned        : %s' % str(is_aligned))

        if is_aligned:
            self.al_size = cfg.data.aligned_size(s=self.scale)
            # print(f'self.al_size[0] = {self.al_size[0]}')
            # print(f'self.al_size[1] = {self.al_size[1]}')
            # print(f'self.src_size[0] = {self.src_size[0]}')
            # print(f'self.src_size[1] = {self.src_size[1]}')
            x_offset = (self.al_size[0] - self.src_size[0]) / 2
            y_offset = (self.al_size[1] - self.src_size[1]) / 2
            # x_offset = cfg.data.bounding_rect()[0]
            # y_offset = cfg.data.bounding_rect()[1]
            # x_offset, y_offset = 0, 0
        else:
            x_offset, y_offset = 0, 0

        logger.info('Offsets x: %s, y: %s' % (str(x_offset), str(y_offset)))

        with self.viewer.txn() as s:
            # NOTE: image_panel_stack_widget and ng_browser have same geometry (height)

            # 276 pixels of widget
            # 1024 pixel image, 8 nm/pixel
            # --> X nm per pixel (i.e. 20 nm / pixel)
            #trying to represent 1024 * 2 = 8192 nm of tissue
            # 8192/276 = 29.68 nm / pixel

            # img_height = cfg.data.bounding_rect()[3] if is_aligned else cfg.data.image_size()[1]  # pixels
            if is_aligned:
                img_height, img_width = cfg.data.bounding_rect(s=self.scale)[3], cfg.data.bounding_rect(s=self.scale)[2]
            else:
                img_height, img_width = cfg.data.image_size(s=self.scale)[1], cfg.data.image_size(s=self.scale)[0]

            widget_size = cfg.main_window.ng_browser.geometry().getRect()

            tissue_height = cfg.data.res_y(s=self.scale) * img_height  # nm
            widget_height = widget_size[3]  # pixels
            cross_section_height = (tissue_height / widget_height) * 1e-9  # nm/pixel

            tissue_width = cfg.data.res_x(s=self.scale) * img_width  # nm
            if is_aligned:  widget_width = widget_size[2] / 3
            else:           widget_width = widget_size[2] / 2
            cross_section_width = (tissue_width / widget_width) * 1e-9  # nm/pixel

            cross_section_scale = max(cross_section_height, cross_section_width)
            adjustment = 1.02
            s.cross_section_scale = cross_section_scale * adjustment
            # logger.info('Tissue Dimensions: %d | Widget Height: %d | Cross Section Scale: %.10f' % (tissue_height, widget_height, cross_section_scale))

            # adjustment = 1.04

            # s.dimensions = self.coordinate_space # ? causes s to bug out, why?

            if cfg.USE_TENSORSTORE:
                # Experimental Match Point Mode Code
                # if match_point_mode:
                # self.coordinate_space = ng.CoordinateSpace(names=['height', 'width', 'channel'], units='nm',
                #                                            scales=[2, 2, 1])
                # unal_dataset = get_zarr_tensor(self.unal_name).result()
                # self.layout = 'yx'
                # layer_base = cfg.data.layer()
                # layer_ref = layer_base - 1
                # self.refLV = ng.LocalVolume(
                #     data=get_tensor_from_tiff(s='scale_1', l=layer_ref),
                #     dimensions=self.coordinate_space,
                #     voxel_offset=[0, ] * 3,  # voxel offset of 1
                # )
                # self.baseLV = ng.LocalVolume(
                #     data=get_tensor_from_tiff(s='scale_1', l=layer_base),
                #     dimensions=self.coordinate_space,
                #     voxel_offset=[0, ] * 3,  # voxel offset of 1
                # )
                unal_dataset = get_zarr_tensor(self.unal_name).result()
                self.refLV = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=self.coordinate_space,
                    voxel_offset=[1, x_offset, y_offset],
                )
                self.baseLV = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=self.coordinate_space,
                    voxel_offset=[0, x_offset, y_offset]
                )
                if is_aligned:
                    al_dataset = get_zarr_tensor(self.al_name).result()
                    self.alLV = ng.LocalVolume(
                        data=al_dataset,
                        dimensions=self.coordinate_space,
                        voxel_offset=[0, ] * 3,
                    )

            else:
                # Not using TensorStore, so point Neuroglancer directly to local Zarr on disk.
                self.refLV =    self.baseLV = f'zarr://http://localhost:{self.port}/{self.src_url}'
                if is_aligned:  self.alLV = f'zarr://http://localhost:{self.port}/{self.al_url}'

            if cfg.SHADER == None:
                s.layers[self.ref_l] = ng.ImageLayer( source=self.refLV)
                s.layers[self.base_l] = ng.ImageLayer( source=self.baseLV)
                if is_aligned and not self.match_point_mode:
                    s.layers[self.aligned_l] = ng.ImageLayer( source=self.alLV)
            else:
                s.layers[self.ref_l] = ng.ImageLayer(source=self.refLV, shader=cfg.SHADER)
                s.layers[self.base_l] = ng.ImageLayer(source=self.baseLV, shader=cfg.SHADER)
                if is_aligned and not self.match_point_mode:
                    s.layers[self.aligned_l] = ng.ImageLayer(source=self.alLV, shader=cfg.SHADER)

            s.layers['mp_ref'] = ng.LocalAnnotationLayer(dimensions=self.coordinate_space,
                                                         annotations = self.pt2ann(points=cfg.data.get_mps(role='ref')),
                                                         annotation_properties=[
                                                             ng.AnnotationPropertySpec(
                                                                 id='ptColor',
                                                                 type='rgb',
                                                                 default='white',
                                                             ),
                                                             ng.AnnotationPropertySpec(
                                                                 id='ptWidth',
                                                                 type='float32',
                                                                 default=3
                                                             ),
                                                             ng.AnnotationPropertySpec(
                                                                 id='size',
                                                                 type='float32',
                                                                 default=7
                                                             )
                                                         ],
                                                         shader=ann_shader,
                                                         )

            s.layers['mp_base'] = ng.LocalAnnotationLayer(dimensions=self.coordinate_space,
                                                          annotations =self.pt2ann(points=cfg.data.get_mps(role='base')) + self.base_pts,
                                                          annotation_properties=[
                                                              ng.AnnotationPropertySpec(
                                                                  id='ptColor',
                                                                  type='rgb',
                                                                  default='white',
                                                              ),
                                                              ng.AnnotationPropertySpec(
                                                                  id='ptWidth',
                                                                  type='float32',
                                                                  default=3
                                                              ),
                                                              ng.AnnotationPropertySpec(
                                                                  id='size',
                                                                  type='float32',
                                                                  default=7
                                                              )
                                                          ],
                                                          shader=ann_shader,
                                                          )

            grps = []
            grps.append(ng.LayerGroupViewer(layers=[self.ref_l, 'mp_ref'], layout=self.layout))
            grps.append(ng.LayerGroupViewer(layers=[self.base_l, 'mp_base'], layout=self.layout))
            if is_aligned and not self.match_point_mode:
                rect = cfg.data.bounding_rect(s=self.scale)
                grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout=self.layout))
                s.position = [cfg.data.layer(), rect[3] / 2, rect[2] / 2]
            else:
                s.position = [cfg.data.layer(), self.src_size[1] / 2, self.src_size[0] / 2]
            s.layout = ng.row_layout(grps)
            # self.viewer.shared_state.add_changed_callback(self.on_state_changed)
            self.viewer.shared_state.add_changed_callback(lambda: self.viewer.defer_callback(self.on_state_changed))
            # s.layers['mp_ref'].annotations = self.pt2ann(points=cfg.data.get_mps(role='ref'))
            # s.layers['mp_base'].annotations = self.pt2ann(points=cfg.data.get_mps(role='base'))

            if cfg.THEME == 0:    s.crossSectionBackgroundColor = '#1B1E23'
            elif cfg.THEME == 1:  s.crossSectionBackgroundColor = '#FFFFE0'
            elif cfg.THEME == 2:  s.crossSectionBackgroundColor = '#6D7D77'
            elif cfg.THEME == 3:  s.crossSectionBackgroundColor = '#0C0C0C'
            else:                 s.crossSectionBackgroundColor = '#004060'

        mp_key_bindings = [
            ['enter', 'add_matchpoint'],
            ['keys', 'save_matchpoints'],
            ['keyc', 'clear_matchpoints'],
        ]

        if self.match_point_mode:
            self.viewer.actions.add('add_matchpoint', self.add_matchpoint)
            self.viewer.actions.add('save_matchpoints', self.save_matchpoints)
            self.viewer.actions.add('clear_matchpoints', self.clear_matchpoints)
        with self.viewer.config_state.txn() as s:
            if self.match_point_mode:
                for key, command in mp_key_bindings:
                    s.input_event_bindings.viewer[key] = command
            s.show_ui_controls = cfg.SHOW_UI_CONTROLS
            s.show_panel_borders = False
            # s.viewer_size = [1000,1000]
            # s.gpu_memory_limit = 2 * 1024 * 1024 * 1024
        cfg.main_window.hud.done()


    # def _toggle_fullscreen(self, s):
    #     self._is_fullscreen = not self._is_fullscreen
    #     with self.viewer.config_state.txn() as s:
    #         if self._is_fullscreen:
    #             s.show_ui_controls = False
    #             s.show_panel_borders = False
    #             s.viewer_size = [self.fullscreen_width, self.fullscreen_height]
    #             s.scale_bar_options.scale_factor = self.fullscreen_scale_bar_scale
    #         else:
    #             s.show_ui_controls = True
    #             s.show_panel_borders = True
    #             s.viewer_size = None
    #             s.scale_bar_options.scale_factor = 1


    def on_state_changed(self):
        try:
            request_layer = floor(self.viewer.state.position[0])
            project_dict_layer = cfg.data.layer() #1110-
            if request_layer == project_dict_layer: #1110-
                logger.debug('State Changed, But Layer Is The Same -> Suppressing The Callback Signal')
                return
            self.signals.stateChanged.emit(request_layer)
            if self.match_point_mode:
                self.clear_mp_buffer()
        except:
            print_exception()


    def add_matchpoint(self, s):
        logger.info('add_matchpoint:')
        assert self.match_point_mode == True
        coords = np.array(s.mouse_voxel_coordinates)
        if coords.ndim == 0:
            logger.warning('Coordinates are dimensionless!')
            return
        try:
            if (coords[1] < 0) or (coords[2] < 0):
                logger.warning('Invalid match point, outside the image')
                return
        except:
            print_exception()
            # with self.viewer.txn() as s:
            #     s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref'))
            #     s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base'))
            # logger.info('Zeroing matchpoint ticker')
            # return
        props = [self.mp_colors[self.mp_count], self.mp_marker_lineweight, self.mp_marker_size, ]
        with self.viewer.txn() as s:
            if self.mp_count in range(0,100,2):
                self.ref_pts.append(ng.PointAnnotation(id=repr(coords), point=coords, props=props))
                s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref')) + self.ref_pts
                logger.info(f"Ref Match Point Added: {coords}")
            elif self.mp_count in range(1,100,2):
                self.base_pts.append(ng.PointAnnotation(id=repr(coords), point=coords, props=props))
                s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base')) + self.base_pts
                logger.info(f"Base Match Point Added: {coords}")
        self.mp_count += 1


    def save_matchpoints(self, s):
        layer = self.request_layer()
        logger.info('Saving Match Points for Layer %d\nBase Name: %s' % (layer, cfg.data.base_image_name()))
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
        logger.critical('Selected Method (Before Setting): %s' % str(cfg.data.selected_method()))
        cfg.data.set_selected_method(method="Match Point Align", l=layer)
        logger.critical('Selected Method (After Setting): %s' % str(cfg.data.selected_method()))
        self.clear_mp_buffer()
        self.refLV.invalidate()
        self.baseLV.invalidate()
        cfg.data.print_all_match_points()
        cfg.main_window.hud.post('Match Points Saved!')


    def clear_matchpoints(self, s):
        logger.info('Clearing match points in project dict...')
        layer = self.request_layer()
        cfg.data.clear_match_points(s=self.scale, l=layer) #Note
        cfg.data.set_selected_method(method="Auto Swim Align", l=layer)
        self.clear_mp_buffer() #Note
        with self.viewer.txn() as s:
            s.layers['mp_ref'].annotations = self.pt2ann(cfg.data.get_mps(role='ref'))
            s.layers['mp_base'].annotations = self.pt2ann(cfg.data.get_mps(role='base'))
        self.refLV.invalidate()
        self.baseLV.invalidate()
        cfg.main_window.hud.post('Match Points for Layer %d Erased' % layer)


    def clear_mp_buffer(self):
        logger.info('Clearing match point buffer')
        self.mp_count = 0
        self.ref_pts.clear()
        self.base_pts.clear()
        try:
            self.refLV.invalidate()
            self.baseLV.invalidate()
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


    def invalidateAlignedLayers(self):
        self.alLV.invalidate()


    def invalidateAllLayers(self):
        self.refLV.invalidate()
        self.baseLV.invalidate()
        try:
            self.alLV.invalidate()
        except:
            pass


    def take_screenshot(self, directory=None):
        if directory is None:
            directory = cfg.data.dest()
        ss = ScreenshotSaver(viewer=self.viewer, directory=dir)
        ss.capture()


    def request_layer(self):
        l = floor(self.viewer.state.position[0])
        return l


    # Note: odd mapping of axes
    def set_layout_yz(self):
        self.layout = 'xy'; self.initViewer()


    def set_layout_xy(self):
        self.layout = 'yz'; self.initViewer()


    def set_layout_xz(self):
        self.layout = 'xz'; self.initViewer()


    def set_layout_xy_3d(self):
        self.layout = 'yz-3d'; self.initViewer()


    def set_layout_yz_3d(self):
        self.layout = 'xy-3d'; self.initViewer()


    def set_layout_xz_3d(self):
        self.layout = 'xz-3d'; self.initViewer()


    def set_layout_3d(self):
        self.layout = '3d'; self.initViewer()


    def set_layout_4panel(self):
        self.layout = '4panel'; self.initViewer()


    def url(self):
        while True:
            logger.debug('Still looking for an open port...')
            if self.viewer_url is not None:
                logger.debug('An Open Port Was Found')
                return self.viewer_url


    def get_viewer_url(self):
        '''From extend_segments example'''
        return self.viewer.get_viewer_url()


    def show_state(self):
        cfg.main_window.hud.post('Neuroglancer State:\n\n%s' % ng.to_url(self.viewer.state))


    def print_viewer_info(self, s):
        logger.info(f'Selected Values:\n{s.selected_values}')
        logger.info(f'Current Layer:\n{self.viewer.state.position[0]}')
        logger.info(f'Viewer State:\n{self.viewer.state}')



if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    NgHost(args.source, args.bind, args.port)

'''
cfg.main_window.ng_workers['scale_4'].saved_mp_lst_ref[0].point.tolist()
AlignEM [12]: [3.999997138977051, 157.12501525878906, 1012.6249389648438]

cfg.main_window.ng_workers['scale_4'].saved_mp_lst_ref[0]
AlignEM [8]: PointAnnotation({
  "type": "point", 
  "id": "array([   3.9999971,  157.12502  , 1012.62494  ], dtype=float32)", 
  "point": [3.999997138977051, 157.12501525878906, 1012.6249389648438]})


https://github.com/google/neuroglancer/issues/333
Note tensorstore appears not to support multiscale metadata yet: However, we do have to deal with 
issues of rounding. I have been looking into supporting this in tensorstore, but it is not yet ready.

        # state = copy.deepcopy(self.viewer.state)
        # state.position[0] = requested
        # self.viewer.set_state(state)

        # with self.viewer.state as s:
        #     # state = copy.deepcopy(self.viewer.state)
        #     # state = self.viewer.state
        #     # state.position[0] += layer_delta
        #
        #     s.crossSectionScale = 15
        #     # self.viewer.set_state(state)

        # If changes are made to a neuroglancer l through custom actions, the
        # l needs to be re-rendered for the changes to be visible in the
        # viewports. To re-render a l simply call the invalidate() function on a
        # LocalVolume object
        #
        # # assume a viewports with is already created
        # mesh_volume = neuroglancer.LocalVolume(
        #         data=data, dimensions=res)
        # with viewports.txn() as s:
        #     s.layers['mesh'] = neuroglancer.SegmentationLayer(
        #     source=mesh_volume)
        #
        # # do something ...
        #
        # # re-renders the 'mesh' l in viewports
        # mesh_volume.invalidate()
        # https://connectomics.readthedocs.io/en/latest/external/neuroglancer.html

        # Ref, Text annotations:
        # https://github.com/google/neuroglancer/issues/199

        # https://github.com/google/neuroglancer/blob/master/python/neuroglancer/local_volume.py

        # cfg.main_window.ng_workers[cfg.data.s()].baseLV.invalidate()
        # cfg.main_window.ng_workers[cfg.data.s()].baseLV.info()
        # self.viewer.shared_state.add_changed_callback(
        #     lambda: self.viewer.defer_callback(self.on_state_changed))
        
        
'''
