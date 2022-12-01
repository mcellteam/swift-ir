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
import tornado.platform.asyncio
import tornado.netutil
import tornado.httpserver
# import tornado.platform
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
#             ng.AnnotationPropertySpec(id='size', type='float32'),
#             ng.AnnotationPropertySpec(id='cell_type', type='uint16'),
#             ng.AnnotationPropertySpec(id='point_color', type='rgba'),
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






