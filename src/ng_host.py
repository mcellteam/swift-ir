#!/usr/bin/env python3

"""WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server"""

import os
import copy
import inspect
import http.server
import logging
import argparse
import neuroglancer as ng
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QRunnable, Slot
from src.helpers import print_exception, get_scale_val, is_cur_scale_aligned, is_arg_scale_aligned, are_images_imported
from src.image_funcs import ImageSize, ComputeBoundingRect
from src.zarr_funcs import get_zarr_tensor_from_path
import src.config as cfg
if cfg.USE_TENSORSTORE: import tensorstore as ts

__all__ = ['NgHost']

logger = logging.getLogger(__name__)

KEEP_RUNNING = True

def keep_running():
    return KEEP_RUNNING

class NgHost(QRunnable):
    def __init__(self, src, scale, bind='127.0.0.1', port=9000):
        super(NgHost, self).__init__()
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
        self.http_server = None
        if is_arg_scale_aligned(scale):
            self.al_img_siz = ImageSize(cfg.data.path_aligned(s=scale))
        else:
            self.al_img_siz = None
        self.viewport = ng.Viewer()


    def __del__(self):
        logger.warning('Garbage Collecting An NgHost object...')
        logger.info('Finally: Stopping Neuroglancer...')
        ng.server.stop()
        logger.info('Finally: Shutting Down HTTP Server...')
        self.http_server.shutdown()
        logger.info('Finally: Closing HTTP Server on port %s...' % str(self.http_server.server_port))
        self.http_server.server_close()

    def __str__(self):
        return obj_to_string(self)

    def __repr__(self):
        return copy.deepcopy(self.viewport.state)


    @Slot()
    def run(self):
        # time.sleep(1)
        logger.info('Starting HTTP Server (Scale %d)...' % self.sf)

        os.chdir(self.src) # <-- this sucks, refactor
        self.http_server = None
        # del self.http_server
        '''Find An Available Port'''
        while self.http_server is None:
            try:
                self.http_server = Server((self.bind, self.port))
            except OSError:
                logger.info('Port %d already in use. Trying Another port...' % self.port)
                self.port += 1
                logger.info('port now is %d' % self.port)
            except:
                print_exception()

        # try:
        #     self.initViewer()
        #     # self.initViewer()
        # except:
        #     print_exception()
        #     logger.error('Failed NgHost Failed to Create The Viewer')

        sa = self.http_server.socket.getsockname()
        # self.http_server.allow_reuse_address = True
        logger.info("Serving Data At       : //%s:%d" % (sa[0], sa[1]))
        # self.http_address = "zarr://http://%s:%s" % (str(sa[0]), str(sa[1]))
        # logger.info("Protocol Version      : %s" % str(self.http_server.protocol_version))
        # logger.info("Server Name           : %s" % str(self.http_server.server_name))
        # logger.info("Server Port           : %s" % str(self.http_server.server_port))
        # logger.info("Server Type           : %s" % str(self.http_server.socket_type))
        # logger.info("Server Address        : %s" % str(self.http_server.server_address))
        # logger.info("Server Socket         : %s" % str(self.http_server.socket))


        try:
            while keep_running():
                self.http_server.handle_request()
            # self.http_server.serve_forever()
        except KeyboardInterrupt:
            logger.warning("\nServer connection temporarily lost due to keyboard interruption.")
        except:
            logger.warning("\nServer connection temporarily lost for unknown reason.")
        finally:
            # os.chdir(os.path.split(os.path.realpath(__file__))[0]) #0908+
            logger.info('Finally: Stopping Neuroglancer...')
            ng.server.stop()
            # logger.info('Finally: Closing HTTP Server on port %s...' % str(self.http_server.server_port))
            # self.http_server.server_close()
            logger.info('Finally: Shutting Down HTTP Server...')
            self.http_server.shutdown()
            logger.info('Finally: Exiting System...')
            # sys.exit(0)
        # else:
        #     logger.error("\nMaximum reconnection attempts reached. Disconnecting...\n")
        #     self.http_server.server_close()
        #     self.http_server.shutdown()
        #     sys.exit(0)

    # def take_screenshot(self):
    #     dir = cfg.data.dest()
    #     ss = ScreenshotSaver(viewports=self.viewport, directory=dir)
    #     ss.capture()



    def initViewer(self, l=None):
        logger.info('Creating NG Viewer (called by %s)...' % inspect.stack()[1].function)

        if not are_images_imported():
            logger.warning('Nothing To View in Neuroglancer - Returning')
            return

        # self.viewport = ng.Viewer()

        is_aligned = is_arg_scale_aligned(self.scale)
        if l == None: l = cfg.data.layer()

        # self.viewport = ng.UnsynchronizedViewer()
        self.viewer_url = str(self.viewport)

        x_offset, y_offset = self.get_offsets()

        with self.viewport.txn() as s:
            '''call .info on layer for tensor information'''

            if cfg.USE_TENSORSTORE:
                ''' USE_TENSORSTORE is ON, so point Neuroglancer to TensorStore Object. '''

                if cfg.MULTIVIEW:
                    unal_dataset = get_zarr_tensor_from_path(self.unal_name).result()
                    self.refLV = ng.LocalVolume(
                        data=unal_dataset,
                        dimensions=ng.CoordinateSpace(names=['z','y','x'], units='nm', scales=self.scales,),
                        voxel_offset=[1, x_offset, y_offset], # voxel offset of 1
                    )
                    self.baseLV = ng.LocalVolume(
                        data=unal_dataset,
                        dimensions=ng.CoordinateSpace(names=['z', 'y', 'x'], units='nm', scales=self.scales, ),
                        voxel_offset=[0, x_offset, y_offset]
                    )
                    if is_aligned:
                        al_dataset = get_zarr_tensor_from_path(self.al_name).result()
                        self.alLV = ng.LocalVolume(
                            data=al_dataset,
                            dimensions=ng.CoordinateSpace(names=['z','y','x'], units='nm', scales=self.scales, ),
                            voxel_offset=[0, ] * 3,
                        )
                else:
                    use = self.al_name if is_aligned else self.unal_name
                    data = get_zarr_tensor_from_path(use).result()
                    layer = ng.LocalVolume(
                        data=data,
                        dimensions=ng.CoordinateSpace(names=['z','y','x'], units='nm', scales=self.scales, ),
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
                if is_aligned: s.layers[self.aligned_l] = ng.ImageLayer(source=self.alLV)

                if is_aligned:
                    rect = cfg.data.bounding_rect()
                    s.position = [l, rect[3] / 2, rect[2] / 2]
                    s.layout = ng.row_layout([ng.LayerGroupViewer(layers=[self.ref_l], layout=self.layout),
                                              ng.LayerGroupViewer(layers=[self.base_l], layout=self.layout),
                                              ng.LayerGroupViewer(layers=[self.aligned_l], layout=self.layout)])
                else:
                    # s.position = [l, img_dim[0] / 2, img_dim[1] / 2]
                    s.position = [l, self.base_img_siz[1] / 2, self.base_img_siz[0] / 2]
                    s.layout = ng.row_layout([ng.LayerGroupViewer(layers=[self.ref_l], layout=self.layout),
                                              ng.LayerGroupViewer(layers=[self.base_l], layout=self.layout)])
            else:
                s.layers['l'] = ng.ImageLayer(source=layer)
                s.layout = ng.row_layout([ng.LayerGroupViewer(layers=['l'], layout=self.layout)])


            if cfg.main_window.main_stylesheet == os.path.abspath('src/styles/daylight.qss'):
                s.cross_section_background_color = "#ffffff"
            else:
                s.cross_section_background_color = "#004060"

            if cfg.USE_TENSORSTORE:
                s.cross_section_scale = (1e-8)*2
                # 1e-7 = .0000001
                # .001 = 1e-3       = mm
                # .000001 = 1e-6    = micrometer
                # .000000001 = 1e-9 = nanometer

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

        def layer_left(s):
            # print('Layering left...')
            # print('s.position = %s' % str(s.position))
            # print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
            # print('  Layer selected values: %s' % (s.selected_values,))
            # s.position[0] -= 1
            pass

        def layer_right(s):
            # print('Layering right...')
            # print('Layering right...%s' % str(s.position))
            # print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
            # print('  Layer selected values: %s' % (s.selected_values,))
            # s.position[0] += 1
            pass

        # self.viewport.actions.add('screenshot', self.take_screenshot)
        self.viewport.actions.add('l-right', layer_right)
        self.viewport.actions.add('l-left', layer_left)
        with self.viewport.config_state.txn() as s:
            # s.input_event_bindings.viewports['keyb'] = 'screenshot'
            s.input_event_bindings.viewer['keyl'] = 'l-left'
            s.input_event_bindings.viewer['keyr'] = 'l-right'
            # s.show_ui_controls = True
            s.show_ui_controls = True
            # s.show_panel_borders = True
            s.show_panel_borders = False
            # s.viewer_size = None
            # s.input_event_bindings.viewer['keyt'] = 'my-action'
            # s.status_messages['hello'] = "AlignEM-SWiFT: Scale: %d Viewer URL: %s  Protocol: %s" % \
            #                              (cfg.data.scale_val(), self.viewport.get_viewer_url(),
            #                              self.http_server.protocol_version)
            # s.status_messages['hello'] = 'AlignEM-SWiFT Volumetric Viewer (Powered By Neuroglancer)'
            s.status_messages['hello'] = ''

        if self.viewport is not None:
            logger.info('Viewer URL: %s' % self.viewport.get_viewer_url())
            # logger.info('Viewer Configuration: %s' % str(self.viewport.config_state))

    def invalidateAlignedLayers(self):
        self.alLV.invalidate()

    def get_offsets(self):
        if is_arg_scale_aligned(self.scale):
            if self.al_img_siz == None:
                self.al_img_siz = ImageSize(cfg.data.path_aligned(s=self.scale))
            x_offset = (self.al_img_siz[0] - self.base_img_siz[0]) / 2
            y_offset = (self.al_img_siz[1] - self.base_img_siz[1]) / 2
        else:
            x_offset, y_offset = 0, 0
        return (x_offset, y_offset)

    def set_msg(self, msg:str) -> None:
        with self.viewport.config_state.txn() as s:
            s.status_messages['hello'] = msg

    # # layouts: 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'
    def set_layout_yz(self):
        self.layout = 'xy'
        self.initViewer()

    def set_layout_xy(self):
        self.layout = 'yz'
        self.initViewer()

    def set_layout_xz(self):
        self.layout = 'xz'
        self.initViewer()

    def set_layout_xy_3d(self):
        self.layout = 'yz-3d'
        self.initViewer()

    def set_layout_yz_3d(self):
        self.layout = 'xy-3d'
        self.initViewer()

    def set_layout_xz_3d(self):
        self.layout = 'xz-3d'
        self.initViewer()

    def set_layout_3d(self):
        self.layout = '3d'
        self.initViewer()

    def set_layout_4panel(self):
        self.layout = '4panel'
        self.initViewer()

    def url(self):
        while True:
            logger.debug('Still looking for an open port...')
            if self.viewer_url is not None:
                logger.debug('An Open Port Was Found')
                return self.viewer_url

    def show_url(self):
        cfg.main_window.hud.post('Viewer Url:\n%s' % str(self.viewer_url))

    def show_state(self):
        cfg.main_window.hud.post('Neuroglancer State:\n\n%s' % ng.to_url(self.viewport.state))


class CORS_RequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        http.server.SimpleHTTPRequestHandler.end_headers(self)


class Server(http.server.HTTPServer):
    protocol_version = 'HTTP/1.1'
    def __init__(self, server_address):
        http.server.HTTPServer.__init__(self, server_address, CORS_RequestHandler)


def obj_to_string(obj, extra='    '):
    return str(obj.__class__) + '\n' + '\n'.join(
        (extra + (str(item) + ' = ' +
                  (obj_to_string(obj.__dict__[item], extra + '    ') if hasattr(obj.__dict__[item], '__dict__') else str(
                      obj.__dict__[item])))
         for item in sorted(obj.__dict__)))


'''
Note tensorstore appears not to support multiscale metadata yet:
However, we do have to deal with issues of rounding. I have been looking into supporting this in tensorstore, 
but it is not yet ready.
https://github.com/google/neuroglancer/issues/333
'''



if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    NgHost(args.source, args.bind, args.port)


