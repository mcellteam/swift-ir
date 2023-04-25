#!/usr/bin/env python3

import os, sys, http, logging, inspect, shutil, atexit, tempfile
import concurrent.futures
import threading
import asyncio
import http.server
from pathlib import Path
import neuroglancer as ng
# import neuroglancer.write_annotations
import neuroglancer.random_token
import tornado.web
import tornado.httpserver
import tornado.netutil
import tornado.platform
import tornado.platform.asyncio

__all__ = []

logger = logging.getLogger(__name__)


# def write_some_annotations(self):
#     logger.info('Writing some annotations...')
#     tempdir = tempfile.mkdtemp()
#     atexit.register(shutil.rmtree, tempdir)
#
#     writer = neuroglancer.write_annotations.AnnotationWriter(
#         coordinate_space=self.coordinate_space,
#         annotation_type='point',
#         properties=[
#             ng.AnnotationPropertySpec(id='size', cur_method='float32'),
#             ng.AnnotationPropertySpec(id='cell_type', cur_method='uint16'),
#             ng.AnnotationPropertySpec(id='point_color', cur_method='rgba'),
#         ],
#     )
#     writer.add_point([0, 0, 0], size=10, cell_type=16, point_color=(0, 255, 0, 255))
#     writer.add_point([0, 10, 10], size=30, cell_type=16, point_color=(255, 0, 0, 255))
#     writer.add_point([20, 20, 0], size=30, cell_type=16, point_color=(255, 0, 0, 255))
#     writer.add_point([20, 20, 40], size=100, cell_type=16, point_color=(0, 255, 0, 255))
#     writer.add_point([20, 51, 20], size=300, cell_type=16, point_color=(255, 0, 0, 255))
#     writer.add_point([20, 20, 20], size=80, cell_type=16, point_color=(255, 0, 0, 255))
#     writer.write(tempdir)

# class CORS_RequestHandler(http.server.SimpleHTTPRequestHandler):
#     def end_headers(self):
#         self.send_header('Access-Control-Allow-Origin', '*')
#         http.server.SimpleHTTPRequestHandler.end_headers(self)
#
# class SimpleHTTPServer(http.server.HTTPServer):
#     protocol_version = 'HTTP/1.1'
#     def __init__(self, server_address):
#         http.server.HTTPServer.__init__(self, server_address, CORS_RequestHandler)
#

class CorsStaticFileHandler(tornado.web.StaticFileHandler):

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def options(self, *args):
        self.set_status(204)
        self.finish()


def _start_server(bind_address: str, output_dir: str) -> int:

    token = neuroglancer.random_token.make_random_token()
    handlers = [
        (fr'/{token}/(.*)', CorsStaticFileHandler, {
            'path': output_dir
        }),
    ]
    settings = {}
    app = tornado.web.Application(handlers, settings=settings)

    http_server = tornado.httpserver.HTTPServer(app)
    sockets = tornado.netutil.bind_sockets(port=0, address=bind_address)
    http_server.add_sockets(sockets)
    actual_port = sockets[0].getsockname()[1]
    url = neuroglancer.server._get_server_url(bind_address, actual_port)
    return f'{url}/{token}'

def launch_server(bind_address: str, output_dir: str) -> int:

    server_url_future = concurrent.futures.Future()

    def run_server():
        try:

            ioloop = tornado.platform.asyncio.AsyncIOLoop()
            ioloop.make_current()
            asyncio.set_event_loop(ioloop.asyncio_loop)
            server_url_future.set_result(_start_server(bind_address, output_dir))
        except Exception as e:
            server_url_future.set_exception(e)
            return
        # ioloop.start()
        try:
            ioloop.start()
        except KeyboardInterrupt:
            tornado.ioloop.IOLoop.instance().stop()

        ioloop.close()

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()
    return server_url_future.result()