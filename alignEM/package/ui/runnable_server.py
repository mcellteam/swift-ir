#!/usr/bin/env python3

import os
import sys
from http.server import SimpleHTTPRequestHandler
from http.server import HTTPServer
from qtpy.QtCore import QRunnable
from qtpy.QtCore import Slot
import package.config as cfg

__all__ = ['RunnableServer']

class RunnableServer(QRunnable):
    #    def __init__(self, fn, *args, **kwargs):
    def __init__(self):
        super(RunnableServer, self).__init__()
        """
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        """

        """
        self.signals = WorkerSignals()
        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress
        """

    @Slot()
    def run(self):
        # time.sleep(1)
        destination_path = os.path.abspath(cfg.project_data['data']['destination_path'])
        print("destination_path: ", destination_path)
        zarr_project_path = os.path.join(destination_path, "project.zarr")
        os.chdir(zarr_project_path)

        bind = '127.0.0.1'
        port = 9000

        print("Preparing browser view of " + zarr_project_path + "...")
        print("bind                       :", bind)
        print("port                       :", port)

        server = Server((bind, port))
        # server.allow_reuse_address = True
        sa = server.socket.getsockname()
        host = str("http://%s:%d" % (sa[0], sa[1]))
        viewer_source = str("zarr://" + host)
        print("Serving directory %s at http://%s:%d" % (os.getcwd(), sa[0], sa[1]))
        print("Viewer source                   :", viewer_source)
        print("Protocol version                :", server.protocol_version)
        print("Server name                     :", server.server_name)
        print("Server type                     :", server.socket_type)
        # print("allow reuse address= ", server.allow_reuse_address)

        MAX_RETRIES = 10
        attempt = 0
        for _ in range(MAX_RETRIES):
            attempt = attempt + 1
            print("Trying to serve forever... attempt(" + str(attempt) + ")...")
            try:
                server.serve_forever()
            except:
                print("\nServer connection temporarily lost.\nAttempting to reconnect...\n")
                continue
            else:
                break
        else:
            print("\nMaximum reconnection attempts reached. Disconnecting...\n")
            server.server_close()
            sys.exit(0)


class RequestHandler(SimpleHTTPRequestHandler):
    '''A simple HTTP request handler'''
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)


class Server(HTTPServer):
    '''A simple HTTP server'''
    protocol_version = 'HTTP/1.1'
    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, RequestHandler)