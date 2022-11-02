#!/usr/bin/env python3

"""WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server"""

import os
import copy
import shutil
import atexit
import inspect
import logging
import asyncio
import datetime
import argparse
import tempfile
import threading
import concurrent
import http.server
from math import floor
import tornado.web
import tornado.netutil
import tornado.httpserver
import neuroglancer as ng
import neuroglancer.server
import neuroglancer.random_token
from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QRunnable, QObject, Slot, Signal
from src.helpers import print_exception, get_scale_val, is_arg_scale_aligned, are_images_imported, obj_to_string
from src.funcs_image import ImageSize, ComputeBoundingRect
from src.funcs_zarr import get_zarr_tensor_from_path
# from src.funcs_ng import SimpleHTTPServer, launch_server, write_some_annotations
from src.funcs_ng import SimpleHTTPServer, launch_server
import src.config as cfg
from neuroglancer.json_utils import decode_json, encode_json
if cfg.USE_TENSORSTORE: import tensorstore as ts

# USE_TORNADO = False
USE_TORNADO = True

__all__ = ['NgHost']

logger = logging.getLogger(__name__)

KEEP_RUNNING = True

def keep_running():
    return KEEP_RUNNING

class WorkerSignals(QObject):
    result = Signal(str)
    stateChanged = Signal(int)

class NgHost(QRunnable):
    # stateChanged = Signal(str)

    def __init__(self, src, scale, bind='127.0.0.1', port=9000):
        super(NgHost, self).__init__()

        # self.stateChanged

        self.signals = WorkerSignals()

        # self.state_index = None
        self.state_index = 0
        self.cur_message = None
        self.states = []
        self.filename = 'ng_state.json'
        self.annotation_layer_name = 'annotations'
        self.viewport = ng.Viewer() #(SimpleHTTP)

        # self.cur_index = None
        # self.cur_index = cfg.data.layer()
        self.cur_index = 0

        self.src = src
        self.bind = bind
        self.port = port
        self.viewport = ng.Viewer()
        self.viewer_url = None
        self.scale = scale
        self.scales = [cfg.data.res_z(s=scale), cfg.data.res_y(s=scale), cfg.data.res_x(s=scale)]
        self.sf = get_scale_val(scale)  # s factor
        self.ref_l = 'ref_' + str(self.sf)
        self.base_l = 'base_' + str(self.sf)
        self.aligned_l = 'aligned_' + str(self.sf)
        self.layout = 'yz'  # Note: Maps To 'xy'
        self.aligned_url = os.path.join('img_aligned.zarr', 's' + str(self.sf))
        self.src_url = os.path.join('img_src.zarr', 's' + str(self.sf))
        self.al_name = os.path.join(src, self.aligned_url)
        self.unal_name = os.path.join(src, self.src_url)
        self.base_img_siz = ImageSize(cfg.data.path_base(s=scale))
        self.zarr_addr = "zarr://http://localhost:" + str(self.port)
        logger.info('zarr_addr: %s' % self.zarr_addr)
        self.http_server = None
        if is_arg_scale_aligned(self.scale):
            # path = os.path.join(cfg.data.path_aligned(s=self.s), cfg.data.name_base())
            br = cfg.data.bounding_rect()
            self.al_img_siz = [br[2], br[3]]
        else:
            self.al_img_siz = None

        self.num_actions = 0 # for 'nglogger' method


    def __del__(self):
        logger.warning('__del__ was called on ng_host worker')
        # logger.warning('Garbage Collecting An NgHost object...')
        # ng.server.stop()
        # if not USE_TORNADO:
        #     logger.warning('Shutting Down HTTP SimpleHTTPServer...')
        #     self.http_server.shutdown()
        #     self.http_server.server_close()

    def __str__(self):
        return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.viewport.state)

    @Slot()
    def run(self):

        if USE_TORNADO:
            logger.info('Using Tornado for http server...')
            '''tornado'''
            try:
                # self.http_server = SimpleHTTPServer((self.bind, self.port))
                tempdir = tempfile.mkdtemp()
                atexit.register(shutil.rmtree, tempdir)
                self.server_url = launch_server(bind_address='127.0.0.1', output_dir=tempdir)
            except:
                print_exception()
        else:
            logger.info('Using Simple HTTP Server (std library)...')
            '''simple HTTP server'''
            logger.info('Starting HTTP SimpleHTTPServer (Scale %d)...' % self.sf)
            os.chdir(self.src)  # <-- this sucks, refactor
            self.http_server = None
            # del self.http_server

            while self.http_server is None:
                '''Find An Available Port'''
                try:
                    self.http_server = SimpleHTTPServer((self.bind, self.port))
                except OSError:
                    logger.info('Port %d already in use. Trying Another port...' % self.port)
                    self.port += 1
                    logger.info('port now is %d' % self.port)
                except:
                    print_exception()

            sa = self.http_server.socket.getsockname()
            # self.http_server.allow_reuse_address = True
            logger.info("Serving Data At       : //%s:%d" % (sa[0], sa[1]))
            self.http_address = "zarr://http://%s:%s" % (str(sa[0]), str(sa[1]))

            try:
                while keep_running():
                    self.http_server.handle_request()
                # self.http_server.serve_forever()
            except KeyboardInterrupt:
                logger.warning("\nSimpleHTTPServer connection temporarily lost due to keyboard interruption.")
            except:
                logger.warning("\nSimpleHTTPServer connection temporarily lost for unknown reason.")
            finally:
                logger.info('Stopping Neuroglancer at address %s...' % str(self.http_server.server_address))
                ng.server.stop()
                logger.info('Shutting Down HTTP SimpleHTTPServer on port %s...' % str(self.http_server.server_port))
                # self.http_server.server_close()
                self.http_server.shutdown()
            logger.info(f"_________________SimpleHTTPServer:_________________\n"
                        f"Protocol={self.http_server.protocol_version}, Socket={self.http_server.socket}, "
                        f"Port={self.http_server.server_port}, Socket={self.http_server.socket}, "
                        f"Type={self.http_server.socket_type}, Address={self.http_server.server_address}")


    def initViewer(self, l=None):
        # logger.info('Initializing NG Viewer (called by %s)' % inspect.stack()[1].function)
        logger.info('Initializing Thread For NG Client (Scale %d)...' % self.sf)

        app_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        os.chdir(app_dir) # This sucks but is necessary to reverse simple HTTP server shortcomings

        # self.viewport = ng.Viewer()
        # self.viewport = ng.UnsynchronizedViewer()
        self.viewer_url = str(self.viewport)
        assert self.viewport is not None
        assert self.viewer_url is not None

        is_aligned = is_arg_scale_aligned(self.scale)

        if is_aligned:
            if self.al_img_siz == None:
                self.al_img_siz = ImageSize(cfg.data.path_aligned(s=self.scale))
            x_offset = (self.al_img_siz[0] - self.base_img_siz[0]) / 2
            y_offset = (self.al_img_siz[1] - self.base_img_siz[1]) / 2
        else:
            x_offset, y_offset = 0, 0

        self.num_actions = 0

        with self.viewport.txn() as s:

            '''call .info on layer for tensor information'''
            self.coordinate_space = ng.CoordinateSpace(names=['z', 'y', 'x'], units='nm', scales=self.scales, )

            # s.layers['points'] = ng.LocalAnnotationLayer(dimensions=self.coordinate_space)
            # logger.critical(type(s.layers['points'])) #  <class 'neuroglancer.viewer_state.ManagedLayer'>

            if cfg.USE_TENSORSTORE:
                ''' USE_TENSORSTORE is ON, so point Neuroglancer to TensorStore Object. '''

                if cfg.MULTIVIEW:
                    unal_dataset = get_zarr_tensor_from_path(self.unal_name).result()

                    self.refLV = ng.LocalVolume(
                        data=unal_dataset,
                        dimensions=self.coordinate_space,
                        voxel_offset=[1, x_offset, y_offset], # voxel offset of 1
                    )
                    self.baseLV = ng.LocalVolume(
                        data=unal_dataset,
                        dimensions=self.coordinate_space,
                        voxel_offset=[0, x_offset, y_offset]
                    )
                    if is_aligned:
                        al_dataset = get_zarr_tensor_from_path(self.al_name).result()
                        self.alLV = ng.LocalVolume(
                            data=al_dataset,
                            dimensions=self.coordinate_space,
                            voxel_offset=[0, ] * 3,
                        )
                else:
                    use = self.al_name if is_aligned else self.unal_name
                    data = get_zarr_tensor_from_path(use).result()
                    layer = ng.LocalVolume(
                        data=data,
                        dimensions=self.coordinate_space,
                        voxel_offset=[0, ] * 3,
                    )

            else:
                ''' USE_TENSORSTORE is OFF, so point Neuroglancer to local Zarr directly. '''
                if cfg.MULTIVIEW:
                    self.refLV = 'zarr://http://localhost:' + str(self.port) + '/' + self.src_url
                    self.baseLV = 'zarr://http://localhost:' + str(self.port) + '/' + self.src_url
                    if is_aligned:  self.alLV = 'zarr://http://localhost:' + str(self.port) + '/' + self.aligned_url
                else:
                    layer = 'zarr://http://localhost:%d/' % self.port + (self.src_url, self.aligned_url)[is_aligned]

            if cfg.MULTIVIEW:
                s.layers[self.ref_l] = ng.ImageLayer(source=self.refLV)
                s.layers[self.base_l] = ng.ImageLayer(source=self.baseLV)
                s.layers['points'] = ng.LocalAnnotationLayer(dimensions=self.coordinate_space)
                if is_aligned: s.layers[self.aligned_l] = ng.ImageLayer(source=self.alLV)

                if is_aligned:
                    rect = cfg.data.bounding_rect()
                    s.position = [cfg.data.layer(), rect[3] / 2, rect[2] / 2]
                    s.layout = ng.row_layout([ng.LayerGroupViewer(layers=[self.ref_l], layout=self.layout),
                                              ng.LayerGroupViewer(layers=[self.base_l, 'points'], layout=self.layout),
                                              ng.LayerGroupViewer(layers=[self.aligned_l], layout=self.layout)])
                else:
                    # s.position = [cfg.data.layer(), img_dim[0] / 2, img_dim[1] / 2]
                    s.position = [cfg.data.layer(), self.base_img_siz[1] / 2, self.base_img_siz[0] / 2]
                    s.layout = ng.row_layout([ng.LayerGroupViewer(layers=[self.ref_l], layout=self.layout),
                                              ng.LayerGroupViewer(layers=[self.base_l, 'points'], layout=self.layout)])
            else:
                s.layers['l'] = ng.ImageLayer(source=layer)
                s.layout = ng.row_layout([ng.LayerGroupViewer(layers=['l'], layout=self.layout)])

            if cfg.main_window.main_stylesheet == os.path.abspath('styles/daylight.qss'):
                s.cross_section_background_color = "#ffffff"
            else:
                s.cross_section_background_color = "#004060"

            if cfg.USE_TENSORSTORE:
                s.cross_section_scale = (1e-8)*2

            # s.layers['annotation'] = neuroglancer.AnnotationLayer()
            # annotations = s.layers['annotation'].annotations
            # annotations.append(ng.PointAnnotation(point=[0,0,0], id='point1'))
            # annotations.append(ng.PointAnnotation(point=[1,1,1], id='point2'))
            # s.selected_layer.layer = 'annotations'
            s.selected_layer.visible = True

        def layer_left(s):
            print('Layering left...')
            print('s.position = %s' % str(s.position))
            print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
            print('  Layer selected values: %s' % (s.selected_values,))
            # s.position[0] -= 1

        def layer_right(s):
            print('Layering right...')
            print('Layering right...%s' % str(s.position))
            print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
            print('  Layer selected values: %s' % (s.selected_values,))
            # s.position[0] += 1

        # self.viewport.shared_state.add_changed_callback(self.on_state_changed)
        self.viewport.shared_state.add_changed_callback(lambda: self.viewport.defer_callback(self.on_state_changed))

        # self.viewport.actions.add('anno-save', lambda s: self.save())
        # self.viewport.actions.add('screenshot', self.take_screenshot)
        self.viewport.actions.add('l-right', layer_right)
        self.viewport.actions.add('l-left', layer_left)
        self.viewport.actions.add('nglogger', self.nglogger)
        with self.viewport.config_state.txn() as s:
            # s.status_messages['hello'] = 'Add a prompt for neuroglancer'
            # s.input_event_bindings.viewer['control+keys'] = 'anno-save'
            # s.input_event_bindings.viewer['shift+mousedown0']
            # s.input_event_bindings.viewer['keyb'] = 'screenshot'
            s.input_event_bindings.viewer['keyl'] = 'l-left'
            s.input_event_bindings.viewer['keyr'] = 'l-right'
            s.input_event_bindings.viewer['keyl'] = 'nglogger'
            s.show_ui_controls = True
            s.show_panel_borders = False
            # s.viewer_size = None
            # s.status_messages['hello'] = "AlignEM-SWiFT: Scale: %d Viewer URL: %s  Protocol: %s" % \
            #                              (cfg.data.scale_val(), self.viewport.get_viewer_url(),
            #                              self.http_server.protocol_version)


        # if USE_TORNADO:
        #     logger.info('Stored Viewer URL ( self.server_url ): %s' % self.server_url)
        # logger.info('Real Viewer URL ( self.viewport.get_viewer_url()) ): %s' % self.viewport.get_viewer_url()) #orig
        # logger.info('Viewer Configuration: %s' % str(self.viewport.config_state))

    def invalidateAlignedLayers(self):
        self.alLV.invalidate()

    def request_layer(self):
        l = floor(self.viewport.state.position[0])
        # logger.info('l = %s' % str(l))
        assert isinstance(l, int)
        return l

    def on_state_changed(self):
        try:
            # self.cur_index = floor(self.viewport.state.position[0])
            self.cur_index = self.request_layer()
            project_dict_layer = cfg.data.layer()
            if project_dict_layer == self.cur_index:
                logger.info('State Changed, But Layer Is The Same -> Surpressing The Callback Signal')
                return
            self.signals.stateChanged.emit(self.cur_index)
        except:
            print_exception()

    '''Note: weird mapping of axes'''
    def set_layout_yz(self):      self.layout = 'xy'; self.initViewer()
    def set_layout_xy(self):      self.layout = 'yz'; self.initViewer()
    def set_layout_xz(self):      self.layout = 'xz'; self.initViewer()
    def set_layout_xy_3d(self):   self.layout = 'yz-3d'; self.initViewer()
    def set_layout_yz_3d(self):   self.layout = 'xy-3d'; self.initViewer()
    def set_layout_xz_3d(self):   self.layout = 'xz-3d'; self.initViewer()
    def set_layout_3d(self):      self.layout = '3d'; self.initViewer()
    def set_layout_4panel(self):  self.layout = '4panel'; self.initViewer()

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
        # state.layers[self.point_annotation_layer_name] = ng.PointAnnotationLayer()
        state.layers[self.annotation_layer_name] = ng.PointAnnotationLayer()
        return state

    def remove_zero_segments(self):
        for state in self.states:
            segment_ids = self.get_state_segment_ids(state)
            if 0 in segment_ids:
                segment_ids.remove(0)

    def nglogger(self, s):
        import numpy as np
        # global num_actions
        self.num_actions += 1
        # with self.viewport.config_state.txn() as st:
        #     st.status_messages['hello'] = ('Got action %d: mouse position = %r' %
        #                                    (self.num_actions, s.mouse_voxel_coordinates))
        coords = np.array(s.mouse_voxel_coordinates)
        cfg.main_window.hud.post('Matchpoint Added: %s' % str(coords))

        logger.info('Matchpoint At: ', coords)

        # print('Layer selected values:', (np.array(list(self.viewport.state.layers['segmentation'].segments))))

        try:
            with self.viewport.txn() as s:
                point = coords
                point_anno = ng.PointAnnotation(
                    id=repr(point),
                    point=point)
                # logger.critical(type(s.layers['points'])) <class 'neuroglancer.viewer_state.ManagedLayer'>
                s.layers['points'].annotations = [point_anno]
        except:
            print_exception()
        finally:
            self.baseLV.invalidate()


    def take_screenshot(self, dir=None):
        if dir == None: dir = cfg.data.dest()
        ss = ScreenshotSaver(viewer=self.viewport, directory=dir)
        ss.capture()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    NgHost(args.source, args.bind, args.port)



'''
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
