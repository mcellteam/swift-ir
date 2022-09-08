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
import logging
import argparse
from pathlib import Path
from functools import partial
import neuroglancer as ng
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PyQt5.QtCore import QRunnable, QUrl
from PyQt5.QtCore import pyqtSlot as Slot
from src.helpers import print_exception, get_scale_val
from src.image_utils import get_image_size
import src.config as cfg


# https://github.com/google/neuroglancer/blob/566514a11b2c8477f3c49155531a9664e1d1d37a/src/neuroglancer/ui/default_input_event_bindings.ts
# https://github.com/google/neuroglancer/blob/566514a11b2c8477f3c49155531a9664e1d1d37a/src/neuroglancer/util/event_action_map.ts

__all__ = ['View3DEM']

logger = logging.getLogger(__name__)

class RequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)

class Server(HTTPServer):
    protocol_version = 'HTTP/1.1'
    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, RequestHandler)

import http.server
import socketserver

PORT = 8000
DIRECTORY = "web"
# #
# #
# class Handler(http.server.SimpleHTTPRequestHandler):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, directory=DIRECTORY, **kwargs)
#
#
# with socketserver.TCPServer(("", PORT), Handler) as httpd:
#     print("serving at port", PORT)
#     httpd.serve_forever()

def handler_from(directory):
    def _init(self, *args, **kwargs):
        return http.server.SimpleHTTPRequestHandler.__init__(self, *args, directory=self.directory, **kwargs)
    return type(f'HandlerFrom<{directory}>',
                (http.server.SimpleHTTPRequestHandler,),
                {'__init__': _init, 'directory': directory})





# def start_httpd(directory: Path, port: int = 8000):
#     print(f"serving from {directory}...")
#     handler = partial(SimpleHTTPRequestHandler, directory=directory)
#     httpd = HTTPServer(('localhost', port), handler)
#     httpd.serve_forever()



class View3DEM(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self, source=None, scale=None, bind='127.0.0.1', port=9000):
        super(View3DEM, self).__init__()
        self.source = source
        self.bind = bind
        self.port = port
        self.viewer_url = None
        self.scale = scale
        """
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

        self.signals = WorkerSignals()
        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress
        """

    @Slot()
    def run(self):
        # time.sleep(1)
        logger.info('Starting HTTP Server...')

        viewer = ng.Viewer()
        with viewer.txn() as s:
            # s.cross_section_background_color = "#ffffff"
            s.cross_section_background_color = "#000000"

        os.chdir(self.source) # <-- this sucks, refactor

        self.ng_server = None
        while self.ng_server is None:
            try:
                self.ng_server = Server((self.bind, self.port))

                # path = Path(self.source)
                # # self.ng_server = start_httpd(path, port=self.port)
                # handler = partial(SimpleHTTPRequestHandler, directory=self.source)
                # self.ng_server = HTTPServer(('localhost', self.port), handler)
                # self.ng_server.serve_forever()

                # dir = cfg.data.
                # Handler = functools.partial(
                #     http.server.SimpleHTTPRequestHandler,
                #     directory='/my/dir/goes/here'
                # )
            except OSError:
                logger.warning('Port %d already in use. Trying Another port...' % self.port)
                self.port += 1
            except:
                print_exception()

            # finally:
            #     path = os.path.split(os.path.realpath(__file__))[0]
            #     os.chdir(path)

        # if not __name__ == '__main__': cfg.HTTP_PORT = self.port
        # if not __name__ == '__main__':
        #     self.create_viewer()
        self.create_viewer()

        sa = self.ng_server.socket.getsockname()
        logger.info("Serving Data at http://%s:%d" % (sa[0], sa[1]))
        logger.info("Neuroglancer Address: zarr://http://%s:%d" % (sa[0], sa[1]))
        # server.allow_reuse_address = True
        logger.info("Protocol version                :%s" % str(self.ng_server.protocol_version))
        logger.info("Server name                     :%s" % str(self.ng_server.server_name))
        logger.info("Server type                     :%s" % str(self.ng_server.socket_type))
        # print("allow reuse address= ", server.allow_reuse_address)

        # MAX_RETRIES = 10
        MAX_RETRIES = 3
        attempt = 0
        cfg.main_window.disableShortcuts()
        for _ in range(MAX_RETRIES):
            attempt += 1
            logger.info("Trying to serve forever... attempt(" + str(attempt) + ")...")
            try:
                self.ng_server.serve_forever()
            except:
                logger.warning("\nServer connection temporarily lost.\nAttempting to reconnect...\n")
                continue
            else:
                break
            finally:
                cfg.main_window.initShortcuts()

                path = os.path.split(os.path.realpath(__file__))[0]
                os.chdir(path) #0908+
        else:
            logger.error("\nMaximum reconnection attempts reached. Disconnecting...\n")
            cfg.main_window.initShortcuts()
            self.ng_server.server_close()
            sys.exit(0)



    def my_action(s):
        print('Got my-action')
        print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
        print('  Layer selected values: %s' % (s.selected_values,))

    def create_viewer(self):

        # Image.MAX_IMAGE_PIXELS = None #0820-
        res_x, res_y, res_z = 2, 2, 50
        scale_val = get_scale_val(cfg.data.get_scale())
        scales = [float(res_z), res_x * float(scale_val), res_y * float(scale_val)]

        cur_layer = cfg.data.get_layer()


        al_size = get_image_size(cfg.data.get_al_img_path())

        self.ng_viewer = ng.Viewer()
        logger.info('Adding Zarr Image to Viewer...')
        with self.ng_viewer.txn() as s:
            # s.layers['layer'] = ng.ImageLayer(source="zarr://http://localhost:" + str(cfg.HTTP_PORT))
            s.layers['layer'] = ng.ImageLayer(source="zarr://http://localhost:" + str(self.port))
            # s.cross_section_background_color = "#ffffff"
            s.cross_section_background_color = "#000000"
            # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]
            # s.perspective_zoom = 300
            # s.position = [cur_layer, 0, 0]
            s.position = [cur_layer, al_size[0] / 2, al_size[1] / 2]
            # s.dimensions = ng.CoordinateSpace(
            #     names=["z", "y", "x"],
            #     # units=["nm", "nm", "nm"],
            #     units="nm",
            #     # scales=[res_z, res_y, res_x]
            #     scales=scales
            # )


            # layouts: 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'
            s.layout = ng.column_layout(
                [ng.LayerGroupViewer(
                    layout='4panel',
                    layers=['layer'])]
            )

        # logger.info('Loading Neuroglancer Callbacks...')
        # # self.ng_viewer.actions.add('unchunk_', unchunk)
        # # self.ng_viewer.actions.add('blend_', blend)
        with self.ng_viewer.config_state.txn() as s:
            # s.input_event_bindings.viewer['keyu'] = 'unchunk_'
            # s.input_event_bindings.viewer['keyb'] = 'blend_'
            # s.status_messages['message'] = 'Welcome to AlignEM_SWiFT'
            s.show_ui_controls = True
            s.show_panel_borders = True
            s.viewer_size = None

            s.input_event_bindings.viewer['keyt'] = 'my-action'
            s.status_messages['hello'] = "Viewing: %s" % self.source



        self.viewer_url = str(self.ng_viewer)
        # logger.info('viewer_url: %s' % viewer_url)
        # cfg.main_window.browser.setUrl(QUrl(self.viewer_url))
        # cfg.main_window.main_widget.setCurrentIndex(1)
        # logger.info('Viewer.config_state                  : %s' % str(self.ng_viewer.config_state))
        # # logger.info('viewer URL                           :', self.ng_viewer.get_viewer_url())
        # # logger.info('Neuroglancer view (remote viewer)                :', ng.to_url(viewer.state))
        # cfg.main_window.hud.post('Viewing Aligned Images In Neuroglancer')
        # logger.info("<<<< view_neuroglancer")

        logger.info('Viewer URL: %s' % self.ng_viewer.get_viewer_url())
        logger.debug('Viewer State URL: %s' % ng.to_url(self.ng_viewer.state))
        logger.debug('Viewer Configuration: %s' % str(self.ng_viewer.config_state))

    def url(self):
        while True:
            logger.debug('Still looking for an open port...')
            if self.viewer_url is not None:
                logger.debug('An Open Port Was Found')
                return self.viewer_url

    def show_url(self):
        cfg.main_window.hud.post('Viewer Url:\n\n%s' % str(self.viewer_url))

    def show_state(self):
        cfg.main_window.hud.post('Neuroglancer State:\n\n%s' % ng.to_url(self.ng_viewer.state))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    View3DEM(args.source, args.bind, args.port)


