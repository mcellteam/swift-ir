#!/usr/bin/env python3

"""WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server"""

'''
old app:
type(match_point_data) = <class 'list'>
match_point_data = [584.021484375, 696.3277343750001]
'''


import argparse
import atexit
import copy
import logging
import os
import shutil
import tempfile
from math import floor
import numpy as np
from collections import deque # double-ended queue is a good data structure for match points

import neuroglancer as ng
from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QRunnable, QObject, Slot, Signal

import src.config as cfg
# from src.funcs_ng import SimpleHTTPServer, launch_server, write_some_annotations
from src.funcs_ng import SimpleHTTPServer, launch_server
from src.funcs_zarr import get_zarr_tensor, get_zarr_tensor_layer, get_tensor_from_tiff
from src.helpers import print_exception, get_scale_val, is_arg_scale_aligned, obj_to_string

if cfg.USE_TENSORSTORE: pass


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

        # self.state_index = None
        self.state_index = 0
        self.cur_message = None
        self.states = []
        self.filename = 'ng_state.json'
        self.annotation_layer_name = 'annotations'
        self.viewport = ng.Viewer()  # (SimpleHTTP)
        # self.ref_pts = deque(maxlen=3)
        # self.base_pts = deque(maxlen=3)
        self.ref_pts = []
        self.base_pts = []
        self.src = src
        self.port = port
        self.viewport = ng.Viewer()
        self.viewer_url = None
        self.scale = scale
        self.coords_3d = [cfg.data.res_z(s=scale), cfg.data.res_y(s=scale), cfg.data.res_x(s=scale)]
        self.coordinate_space_3d = ng.CoordinateSpace(names=['z', 'y', 'x'], units='nm', scales=self.coords_3d, )
        self.coords_2d = [cfg.data.res_y(s=scale), cfg.data.res_x(s=scale)]
        self.coordinate_space_2d = ng.CoordinateSpace(names=['z', 'y'], units='nm', scales=self.coords_2d, )
        self.sf = get_scale_val(scale)  # scale factor
        self.ref_l = 'ref_' + str(self.sf)
        self.base_l = 'base_' + str(self.sf)
        self.aligned_l = 'aligned_' + str(self.sf)
        # self.layout = 'xy'  # Note: Maps To 'xy'
        self.layout = 'yz'  # Note: Maps To 'xy'
        self.al_url = os.path.join('img_aligned.zarr', 's' + str(self.sf))
        self.src_url = os.path.join('img_src.zarr', 's' + str(self.sf))
        self.zarr_addr = "zarr://http://localhost:" + str(self.port)
        self.al_name = os.path.join(src, self.al_url)
        self.unal_name = os.path.join(src, self.src_url)
        self.src_size = cfg.data.image_size(s=self.scale)
        logger.info('zarr_addr: %s' % self.zarr_addr)
        self.http_server = None
        if is_arg_scale_aligned(self.scale):
            self.al_size = cfg.data.al_size(s=self.scale)
        else:
            self.al_size = None

        self.mp_colors = ['#0072b2', '#f0e442', '#FF0000']
        self.mp_ref_count = 0
        self.mp_base_count = 0


    def __del__(self):
        logger.info('__del__ was called on ng_host worker')

    def __str__(self):
        return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.viewport.state)

    @Slot()
    def run(self):
        logger.info('Running Tornado http server...')
        try:
            tempdir = tempfile.mkdtemp()
            atexit.register(shutil.rmtree, tempdir)
            self.server_url = launch_server(bind_address='127.0.0.1', output_dir=tempdir)
        except:
            print_exception()


    def initViewer(self, match_point_mode=False):
        # logger.info('Initializing NG Viewer (called by %s)' % inspect.stack()[1].function)
        logger.info('Creating Neuroglancer Viewer (Scale %d)...' % self.sf)
        cfg.main_window.hud.post('Initializing Neuroglancer Viewer (Scale %d)...' % self.sf)

        self.clear_mp_buffer()
        self.mp_ref_count = self.mp_base_count = 0

        # app_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        # os.chdir(app_dir)  # This sucks but is necessary to reverse simple HTTP server shortcomings

        # self.viewport = ng.UnsynchronizedViewer()
        self.viewport = ng.Viewer() #1108+
        self.viewer_url = str(self.viewport)
        self.mp_marker_size = cfg.data['user_settings']['mp_marker_border_width']
        self.mp_marker_border_width = cfg.data['user_settings']['mp_marker_size']
        is_aligned = is_arg_scale_aligned(self.scale)

        if is_aligned:
            if self.al_size is None:
                # self.al_size = ImageSize(cfg.data.path_aligned(s=self.scale))
                self.al_size = cfg.data.al_size(s=self.scale)
            x_offset = (self.al_size[0] - self.src_size[0]) / 2
            y_offset = (self.al_size[1] - self.src_size[1]) / 2
        else:
            x_offset, y_offset = 0, 0

        cfg.main_window.hud.done()


        with self.viewport.txn() as s:
            s.cross_section_scale = 5e-08
            # s.cross_section_scale = 2e-09

            self.saved_mp_lst_ref = self.get_saved_ref_matchpoints()
            self.saved_mp_lst_base = self.get_saved_base_matchpoints()

            # logger.info('Saved Ref Matchpoints:\n%s' % str(self.saved_mp_lst_ref))
            # logger.info('Saved Base Matchpoints:\n%s' % str(self.saved_mp_lst_base))

            if cfg.USE_TENSORSTORE:

                # Experimental Match Point Mode Code
                # if match_point_mode:
                # self.coordinate_space_3d = ng.CoordinateSpace(names=['height', 'width', 'channel'], units='nm',
                #                                            scales=[2, 2, 1])
                # unal_dataset = get_zarr_tensor(self.unal_name).result()
                # self.layout = 'yx'
                # layer_base = cfg.data.layer()
                # layer_ref = layer_base - 1
                # self.refLV = ng.LocalVolume(
                #     data=get_tensor_from_tiff(s='scale_1', l=layer_ref),
                #     dimensions=self.coordinate_space_3d,
                #     voxel_offset=[0, ] * 3,  # voxel offset of 1
                # )
                # self.baseLV = ng.LocalVolume(
                #     data=get_tensor_from_tiff(s='scale_1', l=layer_base),
                #     dimensions=self.coordinate_space_3d,
                #     voxel_offset=[0, ] * 3,  # voxel offset of 1
                # )
                unal_dataset = get_zarr_tensor(self.unal_name).result()
                self.refLV = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=self.coordinate_space_3d,
                    voxel_offset=[1, x_offset, y_offset],
                )
                self.baseLV = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=self.coordinate_space_3d,
                    voxel_offset=[0, x_offset, y_offset]
                )
                if is_aligned:
                    al_dataset = get_zarr_tensor(self.al_name).result()
                    self.alLV = ng.LocalVolume(
                        data=al_dataset,
                        dimensions=self.coordinate_space_3d,
                        voxel_offset=[0, ] * 3,
                    )

            else:
                # Not using TensorStore, so point Neuroglancer directly to local Zarr on disk.
                self.refLV =    self.baseLV = f'zarr://http://localhost:{self.port}/{self.src_url}'
                if is_aligned:  self.alLV = f'zarr://http://localhost:{self.port}/{self.al_url}'

            s.layers[self.ref_l] = ng.ImageLayer(
                source=self.refLV,
                # shader=src.shaders.colormapJet
                shader=cfg.SHADER
            )
            s.layers[self.base_l] = ng.ImageLayer(
                source=self.baseLV,
                # shader=src.shaders.colormapJet
                shader=cfg.SHADER
            )
            shader = '''void main() { setPointMarkerBorderColor(prop_ptColor()); 
                                      setPointMarkerBorderWidth(prop_ptWidth()); 
                                      setPointMarkerSize(prop_size()); }'''

            logger.critical('saved_mp_lst_ref:\n  %s' % str(self.saved_mp_lst_ref))
            s.layers['matchpoint_ref'] = ng.LocalAnnotationLayer(dimensions=self.coordinate_space_3d,
                                                                 annotations=self.saved_mp_lst_ref,
                                                                 annotation_properties=[
                                                                     ng.AnnotationPropertySpec(
                                                                         id='ptColor',
                                                                         type='rgb',
                                                                         default='white',
                                                                     ),
                                                                     ng.AnnotationPropertySpec(
                                                                         id='ptWidth',
                                                                         type='float32',
                                                                         default=5
                                                                     ),
                                                                     ng.AnnotationPropertySpec(
                                                                         id='size',
                                                                         type='float32',
                                                                         default=8
                                                                     )
                                                                 ],
                                                                 shader=shader,
                                                                 )

            s.layers['matchpoint_base'] = ng.LocalAnnotationLayer(dimensions=self.coordinate_space_3d,
                                                                  annotations=self.saved_mp_lst_base,
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
                                                                  shader=shader,
                                                                  )

            grps = []
            grps.append(ng.LayerGroupViewer(layers=[self.ref_l, 'matchpoint_ref'], layout=self.layout))
            grps.append(ng.LayerGroupViewer(layers=[self.base_l, 'matchpoint_base'], layout=self.layout))

            if is_aligned and not match_point_mode:
                s.layers[self.aligned_l] = ng.ImageLayer(source=self.alLV)
                rect = cfg.data.bounding_rect()
                grps.append(ng.LayerGroupViewer(layers=[self.aligned_l], layout=self.layout))
                s.position = [cfg.data.layer(), rect[3] / 2, rect[2] / 2]
            else:
                s.position = [cfg.data.layer(), self.src_size[1] / 2, self.src_size[0] / 2]

            s.layout = ng.row_layout(grps)
            # self.viewport.shared_state.add_changed_callback(self.on_state_changed)
            self.viewport.shared_state.add_changed_callback(lambda: self.viewport.defer_callback(self.on_state_changed))
            s.crossSectionBackgroundColor = '#004060'
            s.layers['matchpoint_ref'].annotations = self.saved_mp_lst_ref
            s.layers['matchpoint_base'].annotations = self.saved_mp_lst_base

        if match_point_mode:
            self.viewport.actions.add('add_matchpoint_ref', self.add_matchpoint_ref)
            self.viewport.actions.add('add_matchpoint_base', self.add_matchpoint_base)
            self.viewport.actions.add('save_matchpoints', self.save_matchpoints)
            self.viewport.actions.add('clear_matchpoints', self.clear_matchpoints)
        with self.viewport.config_state.txn() as s:
            if match_point_mode:
                s.input_event_bindings.viewer['keym'] = 'add_matchpoint_ref'
                s.input_event_bindings.viewer['keyp'] = 'add_matchpoint_base'
                s.input_event_bindings.viewer['keys'] = 'save_matchpoints'
                s.input_event_bindings.viewer['keyc'] = 'clear_matchpoints'
            s.show_ui_controls = True
            s.show_panel_borders = True
            # s.status_messages['msg'] = str(self.viewport)
            # s.viewer_size = [1000,1000]


    def on_state_changed(self):
        try:

            project_dict_layer = cfg.data.layer()
            request_layer = floor(self.viewport.state.position[0])
            if request_layer == project_dict_layer:
                logger.debug('State Changed, But Layer Is The Same -> Suppressing The Callback Signal')
                return
            self.signals.stateChanged.emit(request_layer)
            self.clear_mp_buffer()
        except:
            print_exception()


    def add_matchpoint_ref(self, s):
        coords = np.array(s.mouse_voxel_coordinates)
        assert coords is not None
        try:
            if (coords[1] < 0) or (coords[2] < 0):
                logger.warning('Invalid match point, outside the image')
                return
        except IndexError:
            logger.warning('NG Viewer is not in focus.')
        if self.mp_ref_count >= 3:
            self.mp_ref_count = 0
            self.clear_mp_buffer()
            with self.viewport.txn() as s:
                s.layers['matchpoint_ref'].annotations = self.saved_mp_lst_ref
            logger.warning('Zeroing matchpoint ticker, ref')
            # return
        color = self.mp_colors[self.mp_ref_count]
        coords[0] = self.request_layer() # cast layer coordinate to integer
        self.ref_pts.append(ng.PointAnnotation(id=repr(coords),
                                               point=coords,
                                               props=[color, self.mp_marker_size, self.mp_marker_border_width]))
        with self.viewport.txn() as s:
            s.layers['matchpoint_ref'].annotations = self.saved_mp_lst_ref + list(self.ref_pts)

            print('type(self.saved_mp_lst_ref) = %s' % type(self.saved_mp_lst_ref))
            print(str(self.saved_mp_lst_ref))
            print('type(list(self.ref_pts)) = %s' % type(self.ref_pts))
            print(str(self.ref_pts))


        logger.info(f'Match Point Added (ref):{str(coords)}')
        self.mp_ref_count += 1
        # self.refLV.invalidate()

    def add_matchpoint_base(self, s):
        coords = np.array(s.mouse_voxel_coordinates)
        assert coords is not None
        logger.info('Adding Base Match Point...')
        try:
            if (coords[1] < 0) or (coords[2] < 0):
                logger.warning('Invalid match point, outside the image')
                return
        except IndexError:
            logger.warning('NG Viewer is not in focus.')
        if self.mp_base_count >= 3:
            self.mp_base_count = 0
            self.clear_mp_buffer()
            with self.viewport.txn() as s:
                s.layers['matchpoint_base'].annotations = self.saved_mp_lst_base
            logger.warning('Zeroing matchpoint ticker, base')
            # return
        color = self.mp_colors[self.mp_base_count]
        coords[0] = self.request_layer() # cast layer coordinate to integer
        self.base_pts.append(ng.PointAnnotation(id=repr(coords),
                                                point=coords,
                                                props=[color, self.mp_marker_size, self.mp_marker_border_width]))
        with self.viewport.txn() as s:
            s.layers['matchpoint_base'].annotations = self.saved_mp_lst_base + list(self.base_pts)
        logger.info(f'Match Point Added (base):{str(coords)}')
        self.mp_base_count += 1
        # self.baseLV.invalidate()


    def save_matchpoints(self, s):
        logger.info('Saving match points...')

        if len(self.ref_pts) < 3:
            cfg.main_window.hud.post('Select 3 match points on the Ref (Left) image', logging.WARNING);
            cfg.data.print_all_match_points()
            logger.error('self.ref_pts = %s' % str(self.ref_pts))
            logger.error('RETURNING')
            return
        cfg.data.print_all_match_points()
        if len(self.base_pts) < 3:
            cfg.main_window.hud.post('Select 3 match points on the Base (Right) image', logging.WARNING); return
            cfg.data.print_all_match_points()
            logger.error('self.base_pts = %s' % str(self.base_pts))
            logger.error('RETURNING')
            return

        logger.info('BEFORE:')
        cfg.data.print_all_match_points()
        logger.info(f'Match Points (base):{str(self.base_pts)}')
        logger.info(f'Match Points (ref):{str(self.ref_pts)}')
        layer = self.request_layer()
        cfg.data.clear_match_points(s=self.scale, l=layer)
        p_r = [ng_point_to_list(p) for p in self.ref_pts]
        p_b = [ng_point_to_list(p) for p in self.base_pts]
        ref_mps = [p_r[0][1::], p_r[1][1::], p_r[2][1::]]
        base_mps = [p_b[0][1::], p_b[1][1::], p_b[2][1::]]
        logger.info('Adding Ref Match Points: %s' % str(ref_mps))
        logger.info('Adding Base Match Points: %s' % str(base_mps))
        cfg.data.set_match_points(role='ref', matchpoints=ref_mps, l=layer)
        cfg.data.set_match_points(role='base', matchpoints=base_mps, l=layer)
        self.clear_mp_buffer()
        # cfg.main_window.save_project()
        cfg.main_window.hud.post('Match Points Saved!')
        self.refLV.invalidate()
        self.baseLV.invalidate()

    def clear_matchpoints(self, s):
        logger.info('Clearing match points...')
        layer = self.request_layer()
        cfg.data.clear_match_points(s=self.scale, l=layer) #Note
        self.clear_mp_buffer() #Note
        cfg.main_window.hud.post('Match Points for Layer %d Erased' % layer)
        self.refLV.invalidate()
        self.baseLV.invalidate()

    def clear_mp_buffer(self):
        logger.warning('Clearing match point buffer')
        self.ref_pts = []
        self.base_pts = []
        # self.ref_pts.clear()
        # self.base_pts.clear()

    def count_saved_points_ref(self):
        layer = self.request_layer()
        points = [ng_point_to_list(p) for p in self.saved_mp_lst_ref]
        count = 0
        for p in points:
            if p[0] == layer: count +=1
        return count

    def count_saved_points_base(self):
        layer = self.request_layer()
        points = [ng_point_to_list(p) for p in self.saved_mp_lst_base]
        count = 0
        for p in points:
            if p[0] == layer: count +=1
        return count


    def get_saved_ref_matchpoints(self):
        lst = cfg.data.all_match_points_ref()
        lst_ng = [list_to_ng_point(p) for p in lst]
        logger.info(str(lst_ng))
        return lst_ng


    def get_saved_base_matchpoints(self):
        lst = cfg.data.all_match_points_base()
        lst_ng = [list_to_ng_point(p) for p in lst]
        logger.info(str(lst_ng))
        return lst_ng


    def invalidateAlignedLayers(self):
        self.alLV.invalidate()


    def invalidateAllLayers(self):
        self.refLV.invalidate()
        self.baseLV.invalidate()
        self.alLV.invalidate()


    def take_screenshot(self, directory=None):
        if directory is None:
            directory = cfg.data.dest()
        ss = ScreenshotSaver(viewer=self.viewport, directory=dir)
        ss.capture()


    def request_layer(self):
        l = floor(self.viewport.state.position[0])
        # logger.info('l = %s' % str(l))
        # assert isinstance(l, int)
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
        return self.viewport.get_viewer_url()


    def show_state(self):
        cfg.main_window.hud.post('Neuroglancer State:\n\n%s' % ng.to_url(self.viewport.state))


    def make_initial_state(self, segment_id, base_state):
        state = copy.deepcopy(base_state)
        state.layers[self.annotation_layer_name] = ng.PointAnnotationLayer()
        return state


    def print_viewer_info(self, s):
        logger.info(f'Selected Values:\n{s.selected_values}')
        logger.info(f'Current Layer:\n{self.viewport.state.position[0]}')
        logger.info(f'Viewer State:\n{self.viewport.state}')


def ng_point_to_list(ng_point):
    return ng_point.point.tolist()


def list_to_ng_point(coords):
    # return ng.PointAnnotation(id=repr(coords),point=coords)
    print(str(coords))
    return ng.PointAnnotation(id='color',point=coords)


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


s.layers.append(
            name="synapse",
            layer=neuroglancer.LocalAnnotationLayer(
                dimensions=s.dimensions,
                annotation_relationships=['synapse'],
                linked_segmentation_layer={'synapse': 'skeletons'},
                filter_by_segmentation=['synapse'],
                ignore_null_segment_filter=False,
                annotation_properties=[
                    neuroglancer.AnnotationPropertySpec(
                        id='color',
                        type='rgb',
                        default='red',
                    )
                ],
                annotations=[
                    neuroglancer.PointAnnotation(
                        id='1',
                        point=[0, 0, 0],
                        segments=[[40637]],
                        props=['#0f0'],
                    )







{'crossSectionBackgroundColor': '#004060',
 'crossSectionScale': 2.4999999999999996,
 'dimensions': {'x': [8e-09, 'm'], 'y': [8e-09, 'm'], 'z': [5e-08, 'm']},
 'layers': [{'name': 'ref_4',
             'source': 'python://volume/35191a77e78799ae7f7cd6476ef9c7e1fd336cb7.38acc78d4eba0e47cab02434280d213fd13f08ba',
             'tab': 'source',
             'type': 'image'},
            {'name': 'base_4',
             'source': 'python://volume/35191a77e78799ae7f7cd6476ef9c7e1fd336cb7.6751114dfc2e0f85e66f969df6bb402b1961a1ff',
             'tab': 'source',
             'type': 'image'},
            {'annotations': [],
             'name': 'matchpoint_ref',
             'source': {'transform': {...}, 'url': 'local://annotations'},
             'tab': 'source',
             'type': 'annotation'},
            {'annotations': [],
             'name': 'matchpoint_base',
             'source': {'transform': {...}, 'url': 'local://annotations'},
             'tab': 'source',
             'type': 'annotation'},
            {'name': 'aligned_4',
             'source': 'python://volume/35191a77e78799ae7f7cd6476ef9c7e1fd336cb7.c3478cf03ef1bc7957a86c0ae0aa5a30842e1096',
             'tab': 'source',
             'type': 'image'}],
 'layout': {'children': [{'layers': [...], 'layout': 'yz', 'type': 'viewer'},
                         {'layers': [...], 'layout': 'yz', 'type': 'viewer'},
                         {'layers': [...], 'layout': 'yz', 'type': 'viewer'}],
            'type': 'row'},
 'position': [28.5, 880, 880.5],
 'projectionScale': 1024}



NOTES: 

Note tensorstore appears not to support multiscale metadata yet: However, we do have to deal with 
issues of rounding. I have been looking into supporting this in tensorstore, but it is not yet ready.
https://github.com/google/neuroglancer/issues/333


        # state = copy.deepcopy(self.viewport.state)
        # state.position[0] = requested
        # self.viewport.set_state(state)

        # with self.viewport.state as s:
        #     # state = copy.deepcopy(self.viewport.state)
        #     # state = self.viewport.state
        #     # state.position[0] += layer_delta
        #
        #     s.crossSectionScale = 15
        #     # self.viewport.set_state(state)

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
        # self.viewport.shared_state.add_changed_callback(
        #     lambda: self.viewport.defer_callback(self.on_state_changed))
        
        
'''
