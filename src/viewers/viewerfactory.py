#!/usr/bin/env python3

'''WARNING: Because this web server permits cross-origin requests, it exposes any
data in the directory that is served to any web page running on a machine that
can connect to the web server

https://github.com/seung-lab/NeuroglancerAnnotationUI/blob/master/examples/statebuilder_examples.ipynb

Position, layout, and zoom options

View options that do not affect individual layers can be set with a dict passed to the view_kws argument in StateBuilder, which are passed to viewer.set_view_options.

    show_slices : Boolean, sets if slices are shown in the 3d view. Defaults to False.
    layout : xy-3d/xz-3d/yz-3d (sections plus 3d pane), xy/yz/xz/3d (only one pane), or 4panel (all panes). Default is xy-3d.
    show_axis_lines : Boolean, determines if the axis lines are shown in the middle of each view.
    show_scale_bar : Boolean, toggles showing the scale bar.
    orthographic : Boolean, toggles orthographic view in the 3d pane.
    position : 3-element vector, determines the centered location.
    zoom_image : Zoom level for the imagery in units of nm per voxel. Defaults to 8.
    zoom_3d : Zoom level for the 3d pane. Defaults to 2000. Smaller numbers are more zoomed in.
    background_color : Sets the background color of the 3d mode. Defaults to black.


https://github.com/google/neuroglancer/issues/365

control+mousedown0
control+mousedown1
control+mousedown2

control+mousedown0 is being treated as control+mousedown1, bringing up the selection pane instead of adding an
annotation. I suspect Firefox is doing some "helpful" remapping of the mouse event when control is held.


Try: control+mousedown1

with viewer.config_state.txn() as s:
    s.input_event_bindings.data_view["shift+mousedown0"] = "start-fill"
    s.input_event_bindings.data_view["keyt"] = "stop-fill"

https://github.com/shwetagopaul92/neuroglancer/tree/master/examples/dependent-project

'''

import abc
import argparse
import copy
import datetime
import inspect
import logging
import os
import sys
from functools import cache
from math import floor
from pathlib import Path

import numcodecs
import numpy as np
import tensorstore as ts
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, QUrl

import neuroglancer as ng
import neuroglancer.write_annotations
from neuroglancer.json_wrappers import array_wrapper, to_json, JsonObjectWrapper

import src.config as cfg
from src.utils.swiftir import invertAffine
from src.utils.helpers import getOpt, getData, setData, is_joel

context = ts.Context({'cache_pool': {'total_bytes_limit': 1000000000}})


ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['EMViewer', 'TransformViewer', 'PMViewer', 'MAViewer']

logger = logging.getLogger(__name__)
if not is_joel():
    logger.propagate = False
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

class WorkerSignals(QObject):
    arrowLeft = Signal()
    arrowRight = Signal()
    arrowUp = Signal()
    arrowDown = Signal()

    result = Signal(str)
    stateChanged = Signal()
    layoutChanged = Signal()
    # zposChanged = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()

    '''MAviewer'''
    zVoxelCoordChanged = Signal(int)
    ptsChanged = Signal()
    swimAction = Signal()
    badStateChange = Signal()
    toggleView = Signal()
    tellMainwindow = Signal(str)
    warnMainwindow = Signal(str)
    errMainwindow = Signal(str)


class AbstractEMViewer(neuroglancer.Viewer):

    # @abc.abstractmethod
    def __init__(self, parent, webengine, path, dm, res, **kwargs):
        super().__init__(**kwargs)
        clr = inspect.stack()[1].function
        tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        logger.critical(f'[{clr}] {tstamp}')
        self.type = 'AbstractEMViewer'
        self.created = datetime.datetime.now()
        self.parent = parent
        self.path = path
        self.dm = dm
        self.res = res
        # self.res *= self.res / self.dm.lvl()  # monkey patch #Todo fix this
        self.tensor = None
        self.webengine = webengine
        self.webengine.setMouseTracking(True)
        self.signals = WorkerSignals()
        self._cs_scale = None
        self.colors = cfg.glob_colors
        self._blockStateChanged = False
        actions = [('keyLeft', self._keyLeft),
                   ('keyRight', self._keyRight),
                   ('keyUp', self._keyUp),
                   ('keyDown', self._keyDown),
                   ('key1', self._key1),  #abstract
                   ('key2', self._key2),  #abstract
                   ('key3', self._key3),  #abstract
                   ('keySpace', self._keySpace),
                   ('ctlMousedown', self._ctlMousedown)
                   ]
        for a in actions:
            self.actions.add(*a)

        with self.config_state.txn() as s:
            '''DO work: enter, mousedown0, keys, digit1'''
            '''do NOT work: control+mousedown0, control+click0, at:control+mousedown0'''
            s.input_event_bindings.viewer['arrowleft'] = 'keyLeft'
            s.input_event_bindings.viewer['arrowright'] = 'keyRight'
            s.input_event_bindings.viewer['arrowup'] = 'keyUp'
            s.input_event_bindings.viewer['arrowdown'] = 'keyDown'
            s.input_event_bindings.viewer['digit1'] = 'key1'
            s.input_event_bindings.viewer['digit2'] = 'key2'
            s.input_event_bindings.viewer['digit3'] = 'key3'
            s.input_event_bindings.viewer['space'] = 'keySpace'
            s.input_event_bindings.viewer['control+mousedown1'] = 'ctlMousedown'
            # s.input_event_bindings.slice_view['space'] = 'keySpace'
            s.show_ui_controls = False
            s.show_panel_borders = False
            s.show_layer_panel = False
            s.show_help_button = True

        with self.txn() as s:
            # s.gpu_memory_limit = -1
            s.system_memory_limit = -1
            s.concurrent_downloads = 1024 ** 2

        self.setBackground()
        self.webengine.setFocus()

    def defer_callback(self, callback, *args, **kwargs):
        pass

    def __repr__(self):
        return self.get_viewer_url()

    def _repr_html_(self):
        return '<a href="%s" target="_blank">Viewer</a>' % self.get_viewer_url()

    def __del__(self):
        print('\n')
        try:
            clr = inspect.stack()[1].function
            logger.critical(f"{self.type} deleted by {clr} ({self.created})")
            print(f"{self.type} deleted by {clr} ({self.created})", flush=True)
        except:

            logger.critical(f"{self.type} deleted, caller unknown ({self.created})")
            print(f"{self.type} deleted, caller unknown ({self.created})", flush=True)
        print('\n')

    def __exit__(self, exc_type, exc_value, exc_traceback):
        clr = inspect.stack()[1].function
        logger.warning(f"\n{self.type} exiting | caller: {clr}"
                       f"\nexc_type      : {exc_type}"
                       f"\nexc_value     : {exc_value}"
                       f"\nexc_traceback : {exc_traceback}")

    @staticmethod
    @cache
    def _convert_layout(type):
        d = {
            'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d',
            'yz-3d': 'xy-3d', 'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'
        }
        return d[type]

    def transform(self, index=None):
        logger.info('')
        if not index:
            index = 0
        try:
            val = self.state.to_json()['layers'][index]['source']['transform']['matrix']
            print(f"transform: {val}")
            return val
        except Exception as e:
            print(e)
            logger.warning(f'No transform for layer index {index}')

    def set_transform(self, index=0, matrix=None):
        logger.info('')
        if not matrix:
            matrix = [[.999, 0, 0, 0],
                      [0, 1, 0, 0],
                      [0, 0, 1, 0]]

        # self.state.layers[index].layer.source[0].transform.matrix = matrix
        state = copy.deepcopy(self.state)
        try:
            # state.layers[index].layer['source']['transform']['matrix'] = matrix
            state.layers[index].layer.source[0].transform.matrix = matrix
            self.set_state(state)
        except Exception as e:
            logger.info(e)

    # def set_afm(self, index=0, mat=None):
    #     logger.info('')
    #     if not mat:
    #         mat = self.dm.afm_cur()
    #     print(f"afm: {mat}")
    #     # cfg.dm.afm()
    #     # Out[3]: [[1.0, 0.0, 0.0],
    #     #          [0.0, 1.0, 0.0]]
    #
    #     ngmat = conv_mat(mat)
    #
    #     # self.state.layers[index].layer.source[0].transform.matrix = matrix
    #     state = copy.deepcopy(self.state)
    #     try:
    #         # state.layers[index].layer['source']['transform']['matrix'] = matrix
    #         state.layers[index].layer.source[0].transform.matrix = ngmat
    #         self.set_state(state)
    #     except Exception as e:
    #         logger.info(e)

    def set_null_afm(self, index=0, mat=None):
        logger.info('')
        # cfg.dm.afm()
        # Out[3]: [[1.0, 0.0, 0.0],
        #          [0.0, 1.0, 0.0]]

        mat = [[.999, 0, 0, 0],
               [0, 1, 0, 0],
               [0, 0, 1, 0]]

        # self.state.layers[index].layer.source[0].transform.matrix = matrix
        state = copy.deepcopy(self.state)
        try:
            # state.layers[index].layer['source']['transform']['matrix'] = matrix
            state.layers[index].layer.source[0].transform.matrix = mat
            self.set_state(state)
        except Exception as e:
            logger.info(e)



    @abc.abstractmethod
    def initViewer(self):
        raise NotImplementedError

    @abc.abstractmethod
    def set_layer(self):
        self._blockStateChanged = True
        with self.txn() as s:
            vc = s.voxel_coordinates
            try:
                vc[0] = self.dm.zpos + 0.5
            except TypeError:
                logger.warning("TypeError")
                pass
        self._blockStateChanged = False

    @abc.abstractmethod
    def on_state_changed(self):
        raise NotImplementedError

    def _keyLeft(self, s):
        self.signals.arrowLeft.emit()

    def _keyRight(self, s):
        self.signals.arrowRight.emit()

    def _keyUp(self, s):
        self.signals.arrowUp.emit()

    def _keyDown(self, s):
        self.signals.arrowDown.emit()

    @abc.abstractmethod
    def _key1(self, s):
        raise NotImplementedError

    @abc.abstractmethod
    def _key2(self, s):
        raise NotImplementedError

    @abc.abstractmethod
    def _key3(self, s):
        raise NotImplementedError


    def getCoordinateSpace(self):
        return ng.CoordinateSpace(
            names=['z', 'y', 'x'],
            units=['nm', 'nm', 'nm'],
            scales=self.res,
        )
        # return ng.CoordinateSpaceTransform(
        #     ng.CoordinateSpace(
        #         names=['z', 'y', 'x'],
        #         units=['nm', 'nm', 'nm'],
        #         scales=self.res,
        #     )
        # )

    def getLocalVolume(self, data, coordinatespace, z_offset=0):
        """
            data – Source data.
            volume_type – 'image'/'segmentation', or, guessed from data type.
            mesh_options – A dict with the following keys specifying options
                for mesh simplification for 'segmentation' volumes:
            downsampling – '3d' to use isotropic downsampling, '2d' to
                downsample separately in XY, XZ, and YZ; or, None.
            max_downsampling (default=64) – Maximum amount by which on-the-fly
                downsampling may reduce the volume of a chunk. Ex. 4x4x4
                downsampling reduces the volume by 64
            max_downsampled_size (default=128)
        """
        return ng.LocalVolume(
            volume_type='image',
            data=data,
            voxel_offset=[z_offset, 0, 0],
            dimensions=coordinatespace,
            downsampling='3d',
            max_downsampling=cfg.max_downsampling,
            max_downsampled_size=cfg.max_downsampled_size,
        )


    # async def get_zarr_tensor(file_path):
    def getTensor(self, path):
        #Todo can this be made async?
        '''**All TensorStore indexing operations produce lazy views**
        https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

        :param path: Fully qualified Zarr file_path
        :return: A TensorStore future object
        :rtype: tensorstore.Future
        '''
        if not os.path.exists(path):
            logger.warning(f"Path Not Found: {path}")
            return None
        logger.debug(f'Requested: {path}')
        total_bytes_limit = 256_000_000_000  # Lonestar6: 256 GB (3200 MT/level) DDR4
        future = ts.open({
            'dtype': 'uint8',
            'driver': 'zarr',
            'kvstore': {
                'driver': 'file',
                'path': path
            },
            'context': {
                'cache_pool': {'total_bytes_limit': total_bytes_limit},
                'file_io_concurrency': {'limit': 1024},  # 1027+
                # 'data_copy_concurrency': {'limit': 512},
            },
            'recheck_cached_data': 'open',
            # 'recheck_cached_data': True,  # default=True
        })
        return future

    def url(self):
        return self.get_viewer_url()

    def position(self):
        return copy.deepcopy(self.state.position)

    def set_position(self, val):
        with self.txn() as s:
            s.position = val

    def moveUpBy(self, val):
        pos = self.position()
        pos[1] = pos[1] - val
        with self.txn() as s:
            s.position = pos

    def moveDownBy(self, val):
        pos = self.position()
        pos[1] = pos[1] + val
        with self.txn() as s:
            s.position = pos

    def moveLeftBy(self, val):
        pos = self.position()
        pos[2] = pos[2] + val
        with self.txn() as s:
            s.position = pos

    def moveRightBy(self, val):
        pos = self.position()
        pos[2] = pos[2] - val
        with self.txn() as s:
            s.position = pos

    def setHelpMenu(self, b):
        logger.debug(f"b = {b}")
        state = copy.deepcopy(self.state)
        state.help_panel.visible = bool(b)
        self.set_state(state)

    def _keySpace(self, s):
        logger.debug("Native spacebar keybinding intercepted!")
        # if self.dm.method() == 'manual':
        self.signals.toggleView.emit()
        self.webengine.setFocus()

    def _ctlMousedown(self, s):
        logger.debug("Native control+mousedown keybinding intercepted!")
        # if self.dm.method() == 'manual':
        self.webengine.setFocus()

    def _ctlClick(self, s):
        logger.debug("Native control+click keybinding intercepted!")
        self.webengine.setFocus()

    def zoom(self):
        return copy.deepcopy(self.state.crossSectionScale)

    def set_zoom(self, val):
        caller = inspect.stack()[1].function
        logger.debug(f'Setting zoom to {caller}')
        self._blockStateChanged = True
        with self.txn() as s:
            s.crossSectionScale = val
        self._blockStateChanged = False

    def set_brightness(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val:
                layer.shaderControls['brightness'] = val
            else:
                layer.shaderControls['brightness'] = self.dm.brightness
        self.set_state(state)

    def set_contrast(self, val=None):
        state = copy.deepcopy(self.state)
        for layer in state.layers:
            if val:
                layer.shaderControls['contrast'] = val
            else:
                layer.shaderControls['contrast'] = self.dm.contrast
        self.set_state(state)

    def updateDisplayExtras(self):
        with self.txn() as s:
            s.show_default_annotations = self.dm['state']['neuroglancer']['show_bounds']
            s.show_axis_lines = self.dm['state']['neuroglancer']['show_axes']
            s.show_scale_bar = self.dm['state']['neuroglancer']['show_scalebar']

        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,neuroglancer,show_controls')


    def setBackground(self):
        with self.txn() as s:
            if getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'):
                s.crossSectionBackgroundColor = getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')
            else:
                if getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'):
                    s.crossSectionBackgroundColor = '#000000'
                else:
                    s.crossSectionBackgroundColor = '#808080'

    def setUrl(self):
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        self.webengine.setFocus()


    def clear_layers(self):
        if self.state.layers:
            logger.debug('Clearing viewer layers...')
            state = copy.deepcopy(self.state)
            state.layers.clear()
            self.set_state(state)

    def getFrameScale(self, w, h):
        assert hasattr(self, 'tensor')
        _, tensor_y, tensor_x = self.tensor.shape
        _, res_y, res_x = self.res  # nm per imagepixel
        scale_h = ((res_y * tensor_y) / h) * 1e-9  # nm/pixel
        scale_w = ((res_x * tensor_x) / w) * 1e-9  # nm/pixel
        cs_scale = max(scale_h, scale_w)
        return cs_scale


    def initZoom(self, w, h, adjust=1.10):
        logger.debug('')
        if self.tensor:
            if self._cs_scale:
                logger.debug(f'w={w}, h={h}, cs_scale={self._cs_scale}')
                with self.txn() as s:
                    s.cross_section_scale = self._cs_scale
            else:
                self._cs_scale = self.getFrameScale(w=w, h=h)
                adjusted = self._cs_scale * adjust
                with self.txn() as s:
                    s.cross_section_scale = adjusted
            self.signals.zoomChanged.emit(self._cs_scale * 250000000)
        else:
            logger.warning("Cant set zoom now, no tensor store")


    def post_message(self, msg):
        with self.config_state.txn() as cs:
            cs.status_messages['message'] = msg


class EMViewer(AbstractEMViewer):

    def __init__(self, view='raw', **kwags):
        super().__init__(**kwags)
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.view = view
        self.type = 'EMViewer'
        self.shader = self.dm['rendering']['shader']
        self._mats = [None] * len(self.dm)
        self.initViewer()
        # asyncio.ensure_future(self.initViewer())
        # self.post_message(f"Voxel Coordinates: {str(self.state.voxel_coordinates)}")

    def on_state_changed(self):

        if not self._blockStateChanged:
            logger.info('')

            _css = self.state.cross_section_scale
            if not isinstance(_css, type(None)):
                val = (_css, _css * 250000000)[_css < .001]
                if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                    if getData('state,neuroglancer,zoom') != val:
                        logger.debug(f'emitting zoomChanged! [{val:.4f}]')
                        setData('state,neuroglancer,zoom', val)
                        self.signals.zoomChanged.emit(val)

            if isinstance(self.state.position, np.ndarray):
                requested = int(self.state.position[0])
                if requested != self.dm.zpos:
                    logger.info(f'Chaning index to {self.dm.zpos}')
                    self.dm.zpos = requested

            if self.state.layout.type != self._convert_layout(getData('state,neuroglancer,layout')):
                self.signals.layoutChanged.emit()

    # async def initViewer(self, nglayout=None):
    def initViewer(self):
        self._blockStateChanged = False

        siz = self.dm.image_size()

        # if not os.path.exists(os.path.join(self.path,'.zarray')):
        #     cfg.main_window.warn('Zarr (.zarray) Not Found: %s' % self.path)
        #     return

        # if os.path.exists(os.path.join(self.path, '.zarray')):
        #     self.tensor = cfg.tensor = self.getTensor(str(self.path)).result()
        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,neuroglancer,show_controls')

        with self.txn() as s:
            s.layout.type = self._convert_layout(getData('state,neuroglancer,layout'))
            s.show_scale_bar = getData('state,neuroglancer,show_scalebar')
            s.show_axis_lines = getData('state,neuroglancer,show_axes')
            s.show_default_annotations = getData('state,neuroglancer,show_bounds')

            if self.view == 'experimental':
                # self.root = Path(self.dm.images_path) / 'zarr_slices'
                self.path = Path(self.dm.images_path) / 'zarr' / self.dm.level
                tensor = self.getTensor(str(self.path)).result()
                s.position = [self.dm.zpos + 0.5, tensor.shape[1] / 2, tensor.shape[2] / 2]
                for i in range(len(self.dm)):
                    # p = self.root / str(i)
                    # if p.exists():

                    # inv_cafm = invertAffine(self.dm.cafm(l=i))
                    # matrix = conv_mat(inv_cafm, i=i)

                    matrix = conv_mat(self.dm.cafm(l=i), i=i)
                    self._mats[i] = matrix

                    output_dims = {'z': [self.res[0], 'nm'],
                                   'y': [self.res[1], 'nm'],
                                   'x': [self.res[2], 'nm']}

                    transform = {
                        'matrix': matrix,
                        'outputDimensions': output_dims
                    }
                    # tensor = self.getTensor(str(p)).result()

                    LV = self.getLocalVolume(tensor[i:i+1, :, :], self.getCoordinateSpace())
                    # LV = self.getLocalVolume(tensor[:, :, :], self.getCoordinateSpace(), z_offset=i)
                    source = ng.LayerDataSource(
                        url=LV,
                        transform=ng.CoordinateSpaceTransform(transform)
                    )
                    # s.layers[f'{i}'] = ng.ImageLayer(source=source, shader=copy.deepcopy(self.shader,))
                    s.layers.append(
                        name=f"layer-{i}",
                        # layer=ng.ImageLayer(source=source, shader=copy.deepcopy(self.shader,))
                        layer=ng.ImageLayer(source=source, shader=copy.deepcopy(self.shader, )),
                        opacity=1, #Critical
                    )
            else:

                tensor = self.getTensor(str(self.path)).result()
                s.position = [self.dm.zpos + 0.5, tensor.shape[1] / 2, tensor.shape[2] / 2]
                LV = self.getLocalVolume(tensor[:, :, :], self.getCoordinateSpace())
                # LV = self.getLocalVolume(tensor[:, :, :], self.getCoordinateSpace(), z_offset=i)
                source = ng.LayerDataSource(url=LV,)
                s.layers[f'layer'] = ng.ImageLayer(source=source, shader=copy.deepcopy(self.shader, ))



         # https://github.com/google/neuroglancer/blob/ada384e9b27a64ceb704f565fa0989a1262fc903/python/tests/fill_value_test.py#L37

        self.set_brightness()
        self.set_contrast()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))


class TransformViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.type = 'EMViewer'
        self.shader = self.dm['rendering']['shader']
        self.path = Path(self.dm.path_zarr_raw())
        self.section_number = self.dm.zpos
        self.initViewer()

    def initViewer(self):
        self._blockStateChanged = False

        if not self.path.exists():
            logger.warning(f"Path not found: {self.path}")
            return

        self._tensor = self.getTensor(str(self.path)).result()

        self.tensor_ref = self.getTensor(str(self.path)).result()
        ref_pos = self.dm.get_ref_index()
        if ref_pos:
            try:
                self.LV0 = self.getLocalVolume(self.tensor_ref[ref_pos:ref_pos+1, :, :], self.getCoordinateSpace())
            except Exception as e:
                print(e)


        self.tensor = self.getTensor(str(self.path)).result()
        self.LV1 = self.getLocalVolume(self._tensor[self.dm.zpos:self.dm.zpos+1, :, :], self.getCoordinateSpace())

        ident = np.array([[1., 0., 0.], [0., 1., 0.]])
        output_dims = {'z': [self.res[0], 'nm'],
                       'y': [self.res[1], 'nm'],
                       'x': [self.res[2], 'nm']}

        # transform0 = {'matrix': conv_mat(ident, i=1),
        #     'outputDimensions': output_dims}
        #
        # transform1 = {'matrix': conv_mat(self.dm.afm_cur(), i=2),
        #     'outputDimensions': output_dims}

        with self.txn() as s:
            s.layout.type = self._convert_layout('xy')
            # s.layout.type = self._convert_layout('4panel')
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.show_default_annotations = True
            # s.position = [0.5, self.tensor.shape[1] / 2, self.tensor.shape[2] / 2]
            s.position = [1.5, self.tensor.shape[1] / 2, self.tensor.shape[2] / 2]
            transform0 = {'matrix': conv_mat(ident, i=0), 'outputDimensions': output_dims}
            if hasattr(self, 'LV0'):
                source0 = ng.LayerDataSource(
                    url=self.LV0,
                    transform=ng.CoordinateSpaceTransform(transform0),)
                s.layers.append(
                    name='layer0',
                    layer=ng.ImageLayer(source=source0, shader=copy.deepcopy(self.shader, )),
                    opacity=1,)

                if self.dm.is_aligned():
                    mat = conv_mat(self.dm.afm_cur(), i=1)
                    # mat = conv_mat(self.dm.real_afm(), i=1)
                    # mat = conv_mat(self.dm.applied_afm(), i=1)
                else:
                    mat = conv_mat(ident, i=1)
                transform1 = {'matrix': mat, 'outputDimensions': output_dims}
                source1 = ng.LayerDataSource(
                    url=self.LV1,
                    transform=ng.CoordinateSpaceTransform(transform1), )
                s.layers.append(
                    name='layer1',
                    layer=ng.ImageLayer(source=source1, shader=copy.deepcopy(self.shader, )),
                    opacity=1,)

        with self.config_state.txn() as s:
            s.show_ui_controls = False
            s.show_layer_panel = False
            # s.scale_bar_options.padding_in_pixels = 2  # default = 8
            s.scale_bar_options.left_pixel_offset = 4  # default = 10
            s.scale_bar_options.bottom_pixel_offset = 4  # default = 10
            # s.scale_bar_options.bar_top_margin_in_pixels = 0  # default = 5
            s.scale_bar_options.max_width_fraction = 0.1
            s.scale_bar_options.text_height_in_pixels = 10 # default = 15
            s.scale_bar_options.bar_height_in_pixels = 4  # default = 8
            # s.scale_bar_options.font_name = 'monospace'
            # s.scale_bar_options.font_name = 'serif'

        # w = self.webengine.width()
        # h = self.webengine.height()
        # self.initZoom(w=w, h=h)

        self.set_brightness()
        self.set_contrast()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))


class PMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.type = 'PMViewer'
        self.coordspace = ng.CoordinateSpace(
            names=['z', 'y', 'x'], units=['nm', 'nm', 'nm'], scales=[50, 2,2])  # DoThisRight TEMPORARY <---------
        self.initViewer()


    def initViewer(self):
        if not len(self.path):
            logger.info('No paths passed to viewer.')
            return
        p = Path(self.path[0])
        if (p / '.zarray').exists():
            self.tensor = self.getTensor(str(p)).result()
            self.LV_l = self.getLocalVolume(self.tensor[:, :, :], self.getCoordinateSpace())
        if len(self.path) == 2:
            p = Path(self.path[1])
            if (p / '.zarray').exists():
                self.tensor_r = self.getTensor(str(p)).result()
                self.LV_r = self.getLocalVolume(self.tensor_r[:, :, :], self.getCoordinateSpace())

        with self.txn() as s:
            s.layout.type = 'yz'
            s.show_default_annotations = True
            s.show_axis_lines = True
            s.show_scale_bar = False

            if hasattr(self, 'LV_l'):
                s.layers['source'] = ng.ImageLayer(source=self.LV_l)
            else:
                s.layers['source'] = ng.ImageLayer()

            if hasattr(self,'LV_r'):
                s.layers['transformed'] = ng.ImageLayer(source=self.LV_r)
                s.layout = ng.row_layout([
                    ng.LayerGroupViewer(layout='yz', layers=['source']),
                    ng.LayerGroupViewer(layout='yz', layers=['transformed'],),
                ])
            else:
                s.layout = ng.row_layout([
                    ng.LayerGroupViewer(layout='yz', layers=['source']),
                ])

        with self.config_state.txn() as s:
            s.show_ui_controls = False

        self.webengine.setUrl(QUrl(self.get_viewer_url()))

    def _left(self, s):
        logger.debug('')
        with self.txn() as s:
            vc = s.voxel_coordinates
            vc[0] = max(vc[0] - 1, 0)

    def _right(self, s):
        logger.debug('')
        with self.txn() as s:
            vc = s.voxel_coordinates
            vc[0] = min(vc[0] + 1, self.tensor.shape[0])

    def on_state_changed(self):
        pass


class MAViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.type = 'MAViewer'
        self.role = 'tra'
        self.index = 0 #None -1026
        self.cs_scale = None
        self.marker_size = 1
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        self.signals.ptsChanged.connect(self.drawSWIMwindow)
        self.initViewer()

    def z(self):
        return int(self.state.voxel_coordinates[0]) # self.state.position[0]

    def set_layer(self):
        caller = inspect.stack()[1].function
        self._blockStateChanged = True

        if self.role == 'ref':
            self.index = self.dm.get_ref_index()
        else:
            self.index = self.dm.zpos
        logger.debug(f"[{caller}] Setting Z-position [{self.index}]")
        with self.txn() as s:
            vc = s.voxel_coordinates
            try:
                vc[0] = self.index + 0.5
            except TypeError:
                logger.warning('TypeError')
                pass

        self.drawSWIMwindow() #1111+
        try:
            print(f"<< set_layer [{self.index}] [{self.state.voxel_coordinates}]")
        except Exception as e:
            print(e)
        # self.signals.zVoxelCoordChanged.emit(self.index)
        self._blockStateChanged = False

    def initViewer(self):
        logger.debug('')
        self._blockStateChanged = True
        ref = self.dm.get_ref_index()
        self.index = ref if self.role == 'ref' else self.dm.zpos

        try:
            self.store = self.tensor = self.getTensor(self.path).result()
        except Exception as e:
            logger.error('Unable to Load Data Store at %s' % self.path)
            raise e

        self.LV = self.getLocalVolume(self.tensor[:, :, :], self.getCoordinateSpace())

        with self.txn() as s:
            s.layout.type = 'yz'
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.show_default_annotations = False
            _, y, x = self.tensor.shape
            s.voxel_coordinates = [self.index + .5, y / 2, x / 2]
            s.layers['layer'] = ng.ImageLayer(source=self.LV, shader=self.dm['rendering']['shader'], )

        w = self.parent.wNg1.width()
        h = self.parent.wNg1.height()
        self.initZoom(w=w, h=h)
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        self.drawSWIMwindow()
        self.webengine.setFocus()
        self._blockStateChanged = False

    def on_state_changed(self):
        if not self._blockStateChanged:
            # logger.debug(f'[{self.role}]')
            self._blockStateChanged = True

            if self.state.cross_section_scale:
                val = (self.state.cross_section_scale, self.state.cross_section_scale * 250000000)[
                    self.state.cross_section_scale < .001]
                if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                    if getData('state,neuroglancer,zoom') != val:
                        logger.debug(f'emitting zoomChanged! val = {val:.4f}')
                        setData('state,neuroglancer,zoom', val)
                        self.signals.zoomChanged.emit(val)

            if self.role == 'ref':
                if floor(self.state.position[0]) != self.index:
                    logger.warning(f"[{self.role}] Illegal state change")
                    self.signals.badStateChange.emit()  # New
                    return

            elif self.role == 'tra':
                if floor(self.state.position[0]) != self.index:
                    logger.debug(f"Signaling Z-position change...")
                    self.index = floor(self.state.position[0])
                    self.dm.zpos = self.index
                    self.drawSWIMwindow()  # NeedThis #0803
                    # self.dm.zpos = self.index
                    # self.signals.zVoxelCoordChanged.emit(self.index)

            self._blockStateChanged = False
            # logger.debug('<< on_state_changed')


    def _key1(self, s):
        logger.debug('')
        self.add_matchpoint(s, id=0, ignore_pointer=True)
        self.webengine.setFocus()


    def _key2(self, s):
        logger.debug('')
        self.add_matchpoint(s, id=1, ignore_pointer=True)
        self.webengine.setFocus()


    def _key3(self, s):
        logger.debug('')
        self.add_matchpoint(s, id=2, ignore_pointer=True)
        self.webengine.setFocus()


    def swim(self, s):
        logger.debug('[futures] Emitting SWIM signal...')
        self.signals.swimAction.emit()


    def add_matchpoint(self, s, id, ignore_pointer=False):
        if self.dm.method() == 'manual':
            logger.debug('')
            # print('\n\n--> adding region selection -->\n')
            coords = np.array(s.mouse_voxel_coordinates)
            if coords.ndim == 0:
                logger.warning(f'Null coordinates! ({coords})')
                return
            _, y, x = s.mouse_voxel_coordinates
            frac_y = y / self.store.shape[1]
            frac_x = x / self.store.shape[2]
            logger.debug(f"decimal x = {frac_x}, decimal y = {frac_y}")
            self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][
                self.role][id] = (frac_x, frac_y)
            self.signals.ptsChanged.emit()
            self.drawSWIMwindow()


    def drawSWIMwindow(self):
        caller = inspect.stack()[1].function
        logger.debug(f"[{caller}][{self.index}] Drawing SWIM windows...")
        z = self.dm.zpos + 0.5
        self._blockStateChanged = True
        self.undrawSWIMwindows()
        m = self.marker_size
        level_val = self.dm.lvl()
        method = self.dm.current_method
        annotations = []

        if method == 'grid':
            ww1x1 = tuple(self.dm.size1x1())  # full window width
            ww2x2 = tuple(self.dm.size2x2())  # 2x2 window width
            w, h = self.dm.image_size(s=self.dm.level)
            p = self.getCenterpoints(w, h, ww1x1, ww2x2)
            colors = self.colors[0:sum(self.dm.quadrants)]
            cps = [x for i, x in enumerate(p) if self.dm.quadrants[i]]
            ww_x = ww2x2[0] - (24 // level_val)
            ww_y = ww2x2[1] - (24 // level_val)
            for i, pt in enumerate(cps):
                c = colors[i]
                d1, d2, d3, d4 = self.getRect2(pt, ww_x, ww_y)
                id = 'roi%d' % i
                annotations.extend([
                    ng.LineAnnotation(id=id + '%d0', pointA=(z,) + d1, pointB=(z,) + d2, props=[c, m]),
                    ng.LineAnnotation(id=id + '%d1', pointA=(z,) + d2, pointB=(z,) + d3, props=[c, m]),
                    ng.LineAnnotation(id=id + '%d2', pointA=(z,) + d3, pointB=(z,) + d4, props=[c, m]),
                    ng.LineAnnotation(id=id + '%d3', pointA=(z,) + d4, pointB=(z,) + d1, props=[c, m])])
            cfg.mw.setFocus()

        elif method == 'manual':
            ww_x = ww_y = self.dm.manual_swim_window_px()
            pts = self.dm.ss['method_opts']['points']['coords'][self.role]
            for i, pt in enumerate(pts):
                if pt:
                    x = self.store.shape[2] * pt[0]
                    y = self.store.shape[1] * pt[1]
                    d1, d2, d3, d4 = self.getRect2(coords=(x, y), ww_x=ww_x, ww_y=ww_y, )
                    c = self.colors[i]
                    id = 'roi%d' % i
                    annotations.extend([
                        ng.LineAnnotation(id=id + '%d0', pointA=(z,) + d1, pointB=(z,) + d2, props=[c, m]),
                        ng.LineAnnotation(id=id + '%d1', pointA=(z,) + d2, pointB=(z,) + d3, props=[c, m]),
                        ng.LineAnnotation(id=id + '%d2', pointA=(z,) + d3, pointB=(z,) + d4, props=[c, m]),
                        ng.LineAnnotation(id=id + '%d3', pointA=(z,) + d4, pointB=(z,) + d1, props=[c, m])
                    ])
            self.webengine.setFocus()

        with self.txn() as s:
            s.layers['SWIM'] = ng.LocalAnnotationLayer(
                annotations=annotations,
                dimensions=self.getCoordinateSpace(),
                annotationColor='blue',
                annotation_properties=[
                    ng.AnnotationPropertySpec(id='color', type='rgb', default='#ffff66', ),
                    ng.AnnotationPropertySpec(id='size', type='float32', default=1, )
                ],
                shader='''
                    void main() {
                      setColor(prop_color());
                      setPointMarkerSize(prop_size());
                    }
                ''',
            )
        self._blockStateChanged = False
        print("<< drawSWIMwindow", flush=True)

    def undrawSWIMwindows(self):
        with self.txn() as s:
            if s.layers['SWIM']:
                if 'annotations' in s.layers['SWIM'].to_json().keys():
                    s.layers['SWIM'].annotations = None

    @cache
    def getCenterpoints(self, w, h, ww1x1, ww2x2):
        d_x1 = ((w - ww1x1[0]) / 2) + (ww2x2[0] / 2)
        d_x2 = w - d_x1
        d_y1 = ((h - ww1x1[1]) / 2) + (ww2x2[1] / 2)
        d_y2 = h - d_y1
        p1 = (d_x2, d_y1)
        p2 = (d_x1, d_y1)
        p3 = (d_x2, d_y2)
        p4 = (d_x1, d_y2)
        return p1, p2, p3, p4

    @cache
    def getRect2(self, coords, ww_x, ww_y):
        x, y = coords[0], coords[1]
        hw = int(ww_x / 2)  # Half-width
        hh = int(ww_y / 2)  # Half-height
        A = (y + hh, x - hw)
        B = (y + hh, x + hw)
        C = (y - hh, x + hw)
        D = (y - hh, x - hw)
        return A, B, C, D

# @cache # Unhashable type: List
def conv_mat(mat, i=0):
    ngmat = [[.999, 0, 0, i],
             [0, 1, 0, 0],
             [0, 0, 1, 0]]
    ngmat[2][2] = mat[0][0]
    ngmat[2][1] = mat[0][1]
    ngmat[2][3] = mat[0][2]  # translation
    ngmat[1][2] = mat[1][0]
    ngmat[1][1] = mat[1][1]
    ngmat[1][3] = mat[1][2] #translation

    # ngmat[2][2] = mat[0][0]
    # ngmat[2][1] = mat[0][1]
    # ngmat[2][3] = mat[0][2]
    # ngmat[1][2] = mat[1][0]
    # ngmat[1][1] = mat[1][1]
    # ngmat[1][3] = mat[1][2]

    # ngmat[2][2] = mat[0][0]
    # ngmat[2][1] = mat[0][1]
    # ngmat[2][0] = mat[0][2]
    # ngmat[1][2] = mat[1][0]
    # ngmat[1][1] = mat[1][1]
    # ngmat[1][0] = mat[1][2]

    # ngmat[2][0] = mat[0][0]
    # ngmat[2][1] = mat[0][1]
    # ngmat[2][2] = mat[0][2]
    # ngmat[1][0] = mat[1][0]
    # ngmat[1][1] = mat[1][1]
    # ngmat[1][2] = mat[1][2]

    return ngmat


# # Not using TensorStore, so point Neuroglancer directly to local Zarr on disk.
# cfg.refLV = cfg.baseLV = f'zarr://http://localhost:{self.port}/{unal_path}'
# if is_aligned_and_generated:  cfg.alLV = f'zarr://http://localhost:{self.port}/{al_path}'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    EMViewer()
    EMViewer.initViewer()
