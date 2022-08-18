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
from http.server import HTTPServer, SimpleHTTPRequestHandler
from qtpy.QtCore import Slot, QRunnable

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


class View3DEM(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self, source=None, bind='127.0.0.1', port=9000):
        super(View3DEM, self).__init__()
        self.source = source
        self.bind = bind
        self.port = port
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
        logger.info('Entering view_3dem.run...')
        logger.info('self.source  : %s' % self.source)
        logger.info('bind         : %s' % self.bind)
        logger.info('port         : %d' % self.port)
        logger.info('Starting HTTP Server...')

        import neuroglancer as ng
        viewer = ng.Viewer()
        with viewer.txn() as s:
            # s.cross_section_background_color = "#ffffff"
            s.cross_section_background_color = "#000000"

        os.chdir(self.source) # <-- this sucks, refactor

        try:
            self.ng_server = Server((self.bind, self.port))
        except:
            logger.warning('Unable to create new HTTP server process - Continuing Anyway...')

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


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    View3DEM(args.source, args.bind, args.port)


