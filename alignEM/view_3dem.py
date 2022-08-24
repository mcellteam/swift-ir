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
"""
import os
import sys
import logging
import argparse
import functools
import neuroglancer as ng
from http.server import HTTPServer, SimpleHTTPRequestHandler
from qtpy.QtCore import Slot, QRunnable, QUrl
from alignEM.em_utils import print_exception
import alignEM.config as cfg

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

# import http.server
# import socketserver
#
# PORT = 8000
# DIRECTORY = "web"
#
#
# class Handler(http.server.SimpleHTTPRequestHandler):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, directory=DIRECTORY, **kwargs)
#
#
# with socketserver.TCPServer(("", PORT), Handler) as httpd:
#     print("serving at port", PORT)
#     httpd.serve_forever()



class View3DEM(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self, source=None, bind='127.0.0.1', port=9000):
        super(View3DEM, self).__init__()
        self.source = source
        self.bind = bind
        self.port = port
        self.viewer_url = None
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

                # dir = cfg.project_data.
                Handler = functools.partial(
                    http.server.SimpleHTTPRequestHandler,
                    directory='/my/dir/goes/here'
                )
            except OSError:
                logger.warning('Port %d already in use. Trying Another port...' % self.port)
                self.port += 1
            except:
                print_exception()

        # if not __name__ == '__main__': cfg.HTTP_PORT = self.port
        if not __name__ == '__main__':
            self.create_viewer()

        sa = self.ng_server.socket.getsockname()
        logger.info("Serving Data at http://%s:%d" % (sa[0], sa[1]))
        logger.info("Neuroglancer Address: zarr://http://%s:%d" % (sa[0], sa[1]))
        # server.allow_reuse_address = True
        logger.info("Protocol version                :%s" % str(self.ng_server.protocol_version))
        logger.info("Server name                     :%s" % str(self.ng_server.server_name))
        logger.info("Server type                     :%s" % str(self.ng_server.socket_type))
        # print("allow reuse address= ", server.allow_reuse_address)

        MAX_RETRIES = 10
        attempt = 0
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
        else:
            logger.error("\nMaximum reconnection attempts reached. Disconnecting...\n")
            self.ng_server.server_close()
            sys.exit(0)

    def create_viewer(self):

        # Image.MAX_IMAGE_PIXELS = None #0820-
        res_x, res_y, res_z = 2, 2, 50
        self.ng_viewer = ng.Viewer()
        logger.info('Adding Zarr Image to Viewer...')
        with self.ng_viewer.txn() as s:
            # s.layers['multiscale_img'] = ng.ImageLayer(source="zarr://http://localhost:" + str(cfg.HTTP_PORT))
            s.layers['multiscale_img'] = ng.ImageLayer(source="zarr://http://localhost:" + str(self.port))
            s.cross_section_background_color = "#ffffff"
            # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]
            # s.perspective_zoom = 300
            # s.position = [0, 0, 0]
            s.dimensions = ng.CoordinateSpace(
                names=["z", "y", "x"],
                units=["nm", "nm", "nm"],
                scales=[res_z, res_y, res_x]
            )
            # layouts: 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'
            s.layout = ng.column_layout(
                [ng.LayerGroupViewer(
                    layout='4panel',
                    layers=['multiscale_img'])]
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
                logger.info('Viewer Url: %s' % str(self.viewer_url))
                return self.viewer_url


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    View3DEM(args.source, args.bind, args.port)


