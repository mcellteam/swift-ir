#!/usr/bin/env python3

"""WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server"""

import os
import copy
import http.server
import logging
import argparse
import neuroglancer as ng
from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QRunnable, Slot
from src.helpers import print_exception, get_scale_val, is_cur_scale_aligned, are_images_imported
from src.image_funcs import get_image_size
from src.zarr_funcs import get_zarr_tensor
import src.config as cfg

__all__ = ['NgHost']

logger = logging.getLogger(__name__)

KEEP_RUNNING = True

def keep_running():
    return KEEP_RUNNING

class NgHost(QRunnable):
    def __init__(self, src=None, scale=None, bind='127.0.0.1', port=9000):
        super(NgHost, self).__init__()
        self.src = src
        self.bind = bind
        self.port = port
        cfg.viewer_url = None
        self.scale = scale
        self.layout = 'yz'
        # self.layout = 'xy'

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
        return copy.deepcopy(cfg.viewer.state)


    @Slot()
    def run(self):
        # time.sleep(1)
        logger.info('Starting HTTP Server...')

        os.chdir(self.src) # <-- this sucks, refactor
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
            logger.error('Failed NgHost Failed to Create The Viewer')

        sa = self.http_server.socket.getsockname()
        # self.http_server.allow_reuse_address = True
        logger.info("Serving Data at http  : //%s:%d" % (sa[0], sa[1]))
        # self.http_address = "zarr://http://%s:%s" % (str(sa[0]), str(sa[1]))
        logger.info("Neuroglancer Address  : ")
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
            logger.info('Finally: Stopping Neuroglancer...')
            ng.server.stop()
            logger.info('Finally: Closing HTTP Server on port %s...' % str(self.http_server.server_port))
            self.http_server.server_close()
            logger.info('Finally: Shutting Down HTTP Server...')
            self.http_server.shutdown()
            logger.info('Finally: Exiting System...')
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


    def create_viewer(self):
        logger.info('Creating Neuroglancer Viewer...')
        '''
        Note tensorstore appears not to support multiscale metadata yet:
        However, we do have to deal with issues of rounding. I have been looking into supporting this in tensorstore, 
        but it is not yet ready.
        https://github.com/google/neuroglancer/issues/333
        '''
        is_aligned = is_cur_scale_aligned()
        logger.info('is_aligned: %s' % str(is_aligned))
        if is_aligned:  logger.info('is_aligned=True')
        else:           logger.info('is_aligned=False')
        scale_val = get_scale_val(cfg.data.scale())
        l = cfg.data.layer()
        if not are_images_imported():
            logger.warning('Nothing To View, Cant Use Neuroglancer - Returning')
            return

        #Todo set different coordinates for the two different datasets. For now use larger dim.
        img_dim = get_image_size(cfg.data.path_base())

        logger.info('Creating the Neuroglancer Viewer...')
        addr = "zarr://http://localhost:" + str(self.port)
        # addr = "http://localhost:" + str(self.port) # probably want this addr
        # for TensorStore. 'zarr://' protocol only known to Neuroglancer

        logger.info('Layer Address: %s' % addr)
        del cfg.viewer
        cfg.viewer = ng.Viewer()
        # cfg.viewer = ng.UnsynchronizedViewer()
        cfg.viewer_url = str(cfg.viewer)
        scale_factor = cfg.data.scale_val()

        # This did the trick. Open tensorstore using filesystem path, not http.
        al_name = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(scale_factor))
        unal_name = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(scale_factor))

        slug = '_scale' + str(scale_factor)

        with cfg.viewer.txn() as s:

            if is_aligned: al_dataset = get_zarr_tensor(al_name).result()
            unal_dataset = get_zarr_tensor(unal_name).result()

            if is_aligned: logger.info(al_dataset)
            logger.info(unal_dataset)
            if not is_aligned:
                logger.info('Creating Local Volumes...')
                scales = [float(cfg.RES_Z), cfg.RES_Y * float(scale_val), cfg.RES_X * float(scale_val)]
                ref_layer = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=ng.CoordinateSpace(
                        names=['z','y','x'],
                        units='nm',
                        scales=scales,
                    ),
                    voxel_offset=[1, 0, 0], # voxel offset of 1
                )
                logger.info('\nref_layer:\n%s\n' % ref_layer.info())
                s.layers['ref' + slug] = ng.ImageLayer(source=ref_layer)

                base_layer = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=ng.CoordinateSpace(
                        names=['z','y','x'],
                        units='nm',
                        scales=scales,
                    ),
                    voxel_offset=[0, ] * 3,

                )
                logger.info('\nbase_layer:\n%s\n' % base_layer.info())
                s.layers['base' + slug] = ng.ImageLayer(source=base_layer)

                s.position = [l, img_dim[0] / 2, img_dim[1] / 2]


            else:
                al_img_dim = get_image_size(cfg.data.path_al())

                x_offset = (al_img_dim[0] - img_dim[0])/2
                y_offset = (al_img_dim[1] - img_dim[1])/2

                scales = [float(cfg.RES_Z), cfg.RES_Y * float(scale_val), cfg.RES_X * float(scale_val)]
                ref_layer = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=ng.CoordinateSpace(
                        names=['z', 'y', 'x'],
                        units='nm',
                        scales=scales,
                    ),
                    # voxel_offset=[1, 0, 0], # voxel offset of 1
                    voxel_offset=[1, x_offset, y_offset],  # voxel offset of 1
                )
                logger.info('\nref_layer:\n%s\n' % ref_layer.info())
                s.layers['ref' + slug] = ng.ImageLayer(source=ref_layer)

                base_layer = ng.LocalVolume(
                    data=unal_dataset,
                    dimensions=ng.CoordinateSpace(
                        names=['z', 'y', 'x'],
                        units='nm',
                        scales=scales,
                    ),
                    # voxel_offset=[0, ] * 3,
                    voxel_offset=[0, x_offset, y_offset],  # voxel offset of 1

                )
                logger.info('\nbase_layer:\n%s\n' % base_layer.info())
                s.layers['base' + slug] = ng.ImageLayer(source=base_layer)

                if is_aligned:
                    al_layer = ng.LocalVolume(
                        data=al_dataset,
                        dimensions=ng.CoordinateSpace(
                            names=['z', 'y', 'x'],
                            units='nm',
                            scales=scales,
                        ),
                        voxel_offset=[0, ] * 3,
                    )
                    logger.info('\nal_layer:\n%s\n' % al_layer.info())
                    s.layers['aligned' + slug] = ng.ImageLayer(source=al_layer)

                if cfg.main_window.main_stylesheet == os.path.abspath('src/styles/daylight.qss'):
                    s.cross_section_background_color = "#ffffff"
                else:
                    s.cross_section_background_color = "#000000"

                s.position = [l, img_dim[0] / 2, img_dim[1] / 2]



            logger.info('Setting Layouts...')
            if is_aligned:
                s.layout = ng.row_layout([ng.LayerGroupViewer(layers=["ref" + slug], layout=self.layout),
                                          ng.LayerGroupViewer(layers=["base" + slug], layout=self.layout),
                                          ng.LayerGroupViewer(layers=["aligned" + slug], layout=self.layout)])
            else:
                s.layout = ng.row_layout([ng.LayerGroupViewer(layers=["ref" + slug], layout=self.layout),
                                          ng.LayerGroupViewer(layers=["base" + slug], layout=self.layout)])


        # with cfg.viewer.state as s:
        #     # state = copy.deepcopy(cfg.viewer.state)
        #     # state = cfg.viewer.state
        #     # state.position[0] += layer_delta
        #
        #     s.crossSectionScale = 15
        #     # cfg.viewer.set_state(state)

        logger.info('Configuring State Attributes...')
        # logger.info('Loading Neuroglancer Callbacks...')
        # # cfg.viewer.actions.add('unchunk_', unchunk)
        # # cfg.viewer.actions.add('blend_', blend)
        def layer_left(s):
            print('Layering left...')
            print('s.position = %s' % str(s.position))
            print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
            print('  Layer selected values: %s' % (s.selected_values,))
            s.position[0] -= 1

        def layer_right(s):
            print('Layering right...')
            print('Layering right...%s' % str(s.position))
            print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
            print('  Layer selected values: %s' % (s.selected_values,))
            s.position[0] += 1

        cfg.viewer.actions.add('screenshot', self.take_screenshot)
        cfg.viewer.actions.add('layer-right', layer_right)
        cfg.viewer.actions.add('layer-left', layer_left)
        with cfg.viewer.config_state.txn() as s:
            s.input_event_bindings.viewer['keyb'] = 'screenshot'
            s.input_event_bindings.viewer['keyl'] = 'layer-left'
            s.input_event_bindings.viewer['keyr'] = 'layer-right'
            s.show_ui_controls = True
            s.show_panel_borders = True
            s.viewer_size = None
            s.input_event_bindings.viewer['keyt'] = 'my-action'
            # s.status_messages['hello'] = "AlignEM-SWiFT: Scale: %d Viewer URL: %s  Protocol: %s" % \
            #                              (cfg.data.scale_val(), cfg.viewer.get_viewer_url(), self.http_server.protocol_version)
            s.status_messages['hello'] = "AlignEM-SWiFT Volumetric Viewer (Powered By Neuroglancer)"

        if cfg.viewer is not None:
            logger.info('Viewer URL: %s' % cfg.viewer.get_viewer_url())
            logger.info('Viewer Configuration: %s' % str(cfg.viewer.config_state))

    # # layouts: 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'
    def set_layout_yz(self):  self.layout = 'xy'

    def set_layout_xy(self):  self.layout = 'yz'

    def set_layout_xz(self):  self.layout = 'xz'

    def set_layout_xy_3d(self):  self.layout = 'yz-3d'

    def set_layout_yz_3d(self):  self.layout = 'xy-3d'

    def set_layout_xz_3d(self):  self.layout = 'xz-3d'

    def set_layout_3d(self):  self.layout = '3d'

    def set_layout_4panel(self):  self.layout = '4panel'

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

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    NgHost(args.source, args.bind, args.port)


