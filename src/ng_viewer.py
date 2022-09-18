#!/usr/bin/env python3

"""
Simple web server serving local files that permits cross-origin requests.

This can be used to view local data with Neuroglancer.

WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server.

Neuroglancer demo server
https://neuroglancer-demo.appspot.com

zarr://http://localhost:9000

https://github.com/spatial-image/multiscale-spatial-image

/Users/joelyancey/glanceem_swift/test_zarr/test.zarr/0

zarr://http://127.0.0.1:9000

    map.set('keyl', 'recolor');
    map.set('keyx', 'clear-segments');
    map.set('keys', 'toggle-show-slices');
    map.set('keyb', 'toggle-scale-bar');
    map.set('shift+keyb', 'toggle-default-annotations');
    map.set('keya', 'toggle-axis-lines');
    map.set('keyo', 'toggle-orthographic-projection');

        for (let i = 1; i <= 9; ++i) {
      map.set('digit' + i, 'toggle-layer-' + i);
      map.set('control+digit' + i, 'select-layer-' + i);
      map.set('alt+digit' + i, 'toggle-pick-layer-' + i);
    }

    map.set('keyn', 'add-layer');
    map.set('keyh', 'help');

    map.set('space', 'toggle-layout');
    map.set('shift+space', 'toggle-layout-alternative');
    map.set('backslash', 'toggle-show-statistics');



import copy
new_state = copy.deepcopy(viewer.state)
new_state.layers['segmentation'].segments.add(10625)
viewer.set_state(new_state)

# https://github.com/google/neuroglancer/blob/ba083071586d20af4b6f23b8c5a971cc0eb2715d/python/examples/jupyter-notebook-demo.ipynb



"""
import os
import sys
import http.server
import atexit
import logging
import argparse
from pathlib import Path
from functools import partial
import neuroglancer as ng

from qtpy.QtCore import QRunnable, QUrl
from qtpy.QtCore import Slot
from src.helpers import print_exception, get_scale_val
from src.image_funcs import get_image_size
from neuroglancer import ScreenshotSaver
import src.config as cfg


__all__ = ['NgViewer']

logger = logging.getLogger(__name__)


class CORS_RequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        http.server.SimpleHTTPRequestHandler.end_headers(self)

class Server(http.server.HTTPServer):
    protocol_version = 'HTTP/1.1'
    def __init__(self, server_address):
        http.server.HTTPServer.__init__(self, server_address, CORS_RequestHandler)


KEEP_RUNNING = True

def keep_running():
    return KEEP_RUNNING

class NgViewer(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self, src=None, viewof=None, scale=None, bind='127.0.0.1', port=9000):
        super(NgViewer, self).__init__()
        self.src = src
        self.viewof = viewof
        self.bind = bind
        self.port = port
        cfg.viewer_url = None
        self.scale = scale
        if viewof == 'ref' or 'base':
            self.path = os.path.join(src, scale + '.zarr')
        if viewof == 'aligned':
            self.path = os.path.join(src, 'img_aligned.zarr')

    @Slot()
    def run(self):
        # time.sleep(1)
        logger.info('Starting HTTP Server...')

        os.chdir(self.src) # <-- this sucks, refactor
        # os.chdir(self.path) # <-- this sucks, refactor

        self.http_server = None
        while self.http_server is None:
            try:
                self.http_server = Server((self.bind, self.port))
            except OSError:
                logger.warning('Port %d already in use. Trying Another port...' % self.port)
                self.port += 1
                logger.info('port now is %d' % self.port)
            except:
                print_exception()

        try:
            self.create_viewer()
        except:
            print_exception()
            logger.error('Failed NgViewer Failed to Create The Viewer')

        sa = self.http_server.socket.getsockname()
        # self.http_server.allow_reuse_address = True
        logger.info("Serving Data at http  : //%s:%d" % (sa[0], sa[1]))
        logger.info("Neuroglancer Address  : zarr://http://%s:%d" % (sa[0], sa[1]))
        logger.info("Protocol Version      : %s" % str(self.http_server.protocol_version))
        logger.info("Server Name           : %s" % str(self.http_server.server_name))
        logger.info("Server Port           : %s" % str(self.http_server.server_port))
        logger.info("Server Type           : %s" % str(self.http_server.socket_type))
        logger.info("Server Address        : %s" % str(self.http_server.server_address))
        logger.info("Server Socket         : %s" % str(self.http_server.socket))

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
            ng.server.stop()
            self.http_server.server_close()
            self.http_server.shutdown()
            # sys.exit(0)
        # else:
        #     logger.error("\nMaximum reconnection attempts reached. Disconnecting...\n")
        #     self.http_server.server_close()
        #     self.http_server.shutdown()
        #     sys.exit(0)

    def take_screenshot(self):
        dir = cfg.data.dest()
        ss = ScreenshotSaver(viewer=cfg.viewer, directory=dir)
        ss.capture()

    # def my_action(s):
    #     print('Got my-action')
    #     print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
    #     print('  Layer selected values: %s' % (s.selected_values,))

    def create_viewer(self):

        res_x, res_y, res_z = 2, 2, 50
        scale_val = get_scale_val(cfg.data.scale())
        scales = [float(res_z), res_x * float(scale_val), res_y * float(scale_val)]

        l = cfg.data.layer()

        if self.viewof == 'aligned':
            img_dim = get_image_size(cfg.data.path_al())
        else:
            img_dim = get_image_size(cfg.data.path_base())

        logger.info('Adding Image Layer to Viewer...')
        addr = "zarr://http://localhost:" + str(self.port)
        scale_str = 's' + str(get_scale_val(cfg.data.scale()))
        al_path = os.path.join(addr, 'img_aligned.zarr', scale_str)
        unal_path = os.path.join(addr, 'img_src.zarr', scale_str)
        # addr = "zarr://http://localhost:9000"
        logger.info('Layer Address: %s' % addr)
        cfg.viewer = ng.Viewer()
        cfg.viewer_url = str(cfg.viewer)

        with cfg.viewer.txn() as s:
            s.layers['unal_layer'] = ng.ImageLayer(source=unal_path)
            s.layers['al_layer'] = ng.ImageLayer(source=al_path)

            if cfg.main_window.main_stylesheet == os.path.abspath('src/styles/daylight.qss'):
                s.cross_section_background_color = "#ffffff"
            else:
                s.cross_section_background_color = "#000000"
            # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]
            # s.perspective_zoom = 300
            # s.position = [l, 0, 0]
            s.position = [l, img_dim[0] / 2, img_dim[1] / 2]
            # s.dimensions = ng.CoordinateSpace(
            #     names=["z", "y", "x"],
            #     # units=["nm", "nm", "nm"],
            #     units="nm",
            #     # scales=[res_z, res_y, res_x]
            #     scales=scales
            # )


            # panels=[
            #     ng.LayerSidePanelState(
            #         side='left',
            #         col = 0,
            #         row = 0,
            #         tab='render',
            #         tabs=['source', 'rendering'],
            #     ),
            #     ng.LayerSidePanelState(
            #         side='left',
            #         col = 0,
            #         row=1,
            #         tab='render',
            #         tabs=['annotations'],
            #     )
            # ]


            s.layout = ng.row_layout(
                [
                    ng.LayerGroupViewer(layers=["unal_layer"], layout='xy'),
                    ng.LayerGroupViewer(layers=["unal_layer"], layout='xy'),
                    ng.LayerGroupViewer(layers=["al_layer"], layout='xy'),
                ]
            )



            # # layouts: 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'
            # s.layout = ng.column_layout(
            #     [ng.LayerGroupViewer(
            #         # layout='4panel',
            #         layout='yz',
            #         layers=['al_layer'])]
            # )

        # logger.info('Loading Neuroglancer Callbacks...')
        # # cfg.viewer.actions.add('unchunk_', unchunk)
        # # cfg.viewer.actions.add('blend_', blend)
        # # cfg.viewer.actions.add('blend_', blend)
        cfg.viewer.actions.add('screenshot', self.take_screenshot)
        with cfg.viewer.config_state.txn() as s:
            # s.input_event_bindings.viewer['keyu'] = 'unchunk_'
            # s.input_event_bindings.viewer['keyb'] = 'blend_'
            s.input_event_bindings.viewer['keyb'] = 'screenshot'
            # s.status_messages['message'] = 'Welcome to AlignEM_SWiFT'
            s.show_ui_controls = True
            s.show_panel_borders = True
            s.viewer_size = None

            s.input_event_bindings.viewer['keyt'] = 'my-action'
            s.status_messages['hello'] = "Viewing: %s" % self.src


        if cfg.viewer is not None:
            logger.info('Viewer URL: %s' % cfg.viewer.get_viewer_url())
            logger.info('Viewer State URL: %s' % ng.to_url(cfg.viewer.state))
            logger.info('Viewer Configuration: %s' % str(cfg.viewer.config_state))


    def url(self):
        while True:
            logger.debug('Still looking for an open port...')
            if cfg.viewer_url is not None:
                logger.debug('An Open Port Was Found')
                return cfg.viewer_url


    def show_url(self):
        cfg.main_window.hud.post('Viewer Url:\n\n%s' % str(cfg.viewer_url))


    def show_state(self):
        cfg.main_window.hud.post('Neuroglancer State:\n\n%s' % ng.to_url(cfg.viewer.state))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    NgViewer(args.source, args.bind, args.port)


