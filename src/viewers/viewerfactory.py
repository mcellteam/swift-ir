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

https://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object
class Package:
    def __init__(self):
        self.files = []

    def __enter__(self):
        return self

    # ...

    def __exit__(self, exc_type, exc_value, traceback):
        for file in self.files:
            os.unlink(file)

Then, when someone wanted to use your class, they'd do the following:

with Package() as package_obj:
    # use package_obj


'''

import abc
import argparse
import copy
import datetime
import inspect
import logging
import time
import os
import sys
from functools import cache
from math import floor
from pathlib import Path

import numcodecs
import numpy as np
import tensorstore as ts
import zarr
# from neuroglancer import ScreenshotSaver
from qtpy.QtCore import QObject, Signal, QUrl, Slot

import neuroglancer as ng
ng.server.debug = True
import neuroglancer.write_annotations
import neuroglancer.futures
from neuroglancer.json_wrappers import array_wrapper, to_json, JsonObjectWrapper


ng.server.multiprocessing.log_to_stderr()

import src.config as cfg
from src.utils.helpers import getOpt, getData, setData, is_joel, print_exception

context = ts.Context({'cache_pool': {'total_bytes_limit': 1000000000}})


ng.server.debug = cfg.DEBUG_NEUROGLANCER
numcodecs.blosc.use_threads = False

__all__ = ['EMViewer', 'TransformViewer', 'PMViewer', 'MAViewer']

logger = logging.getLogger(__name__)
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
    # positionChanged = Signal()
    zoomChanged = Signal(float)
    mpUpdate = Signal()

    '''MAviewer'''
    zVoxelCoordChanged = Signal(int)
    zChanged = Signal(int)
    ptsChanged = Signal()
    swimAction = Signal()
    badStateChange = Signal()
    toggleView = Signal()
    tellMainwindow = Signal(str)
    warnMainwindow = Signal(str)
    errMainwindow = Signal(str)


class AbstractEMViewer(neuroglancer.Viewer):

    # @abc.abstractmethod
    def __init__(self, parent, webengine, path='', dm=None, res=None, extra_data=None, **kwargs):
        super().__init__(**kwargs)
        clr = inspect.stack()[1].function
        tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        logger.info(f'[{clr}] {tstamp} {path}')
        self.name = 'AbstractEMViewer'
        self.created = datetime.datetime.now()
        self.parent = parent
        self.path = str(path)
        self.dm = dm
        self.res = res
        self.extra_data = extra_data
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

    # def defer_callback(self, callback, *args, **kwargs):
    #     pass

    def __repr__(self):
        return self.get_viewer_url()

    def _repr_html_(self):
        return '<a href="%s" target="_blank">Viewer</a>' % self.get_viewer_url()

    def __del__(self):
        try:
            clr = inspect.stack()[1].function
            logger.warning(f"[{clr}] ({self.created}) {self.name} deleted by {clr}")
        except:
            logger.warning(f"[caller unknown] ({self.created}) {self.name} deleted, caller unknown")


    def __exit__(self, exc_type, exc_value, exc_traceback):
        clr = inspect.stack()[1].function
        logger.warning(f"\n{self.name} exiting | caller: {clr}"
                       f"\nexc_type      : {exc_type}"
                       f"\nexc_value     : {exc_value}"
                       f"\nexc_traceback : {exc_traceback}")

    @abc.abstractmethod
    def initViewer(self):
        raise NotImplementedError

    @abc.abstractmethod
    def on_state_changed(self):
        raise NotImplementedError

    def _keyLeft(self, s):
        logger.info('')
        self.signals.arrowLeft.emit()

    def _keyRight(self, s):
        logger.info('')
        self.signals.arrowRight.emit()

    def _keyUp(self, s):
        logger.info('')
        self.signals.arrowUp.emit()

    def _keyDown(self, s):
        logger.info('')
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
        pos[0] = pos[0] + val
        with self.txn() as s:
            s.position = pos

    def moveRightBy(self, val):
        pos = self.position()
        pos[0] = pos[0] - val
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

    def scroll_dim(self, dim: str, velocity=4, atboundary="loop"):
        with self.txn() as s:
            s.velocity[dim] = {"velocity": velocity, "atBoundary": atboundary, "paused": False}

    def stop_scroll(self):
        with self.txn() as s:
            s.velocity['x']['paused'] = True
            s.velocity['y']['paused'] = True
            s.velocity['z']['paused'] = True

    def getCoordinateSpace(self):
        return ng.CoordinateSpace(
            names=['x', 'y', 'z'],
            units=['nm', 'nm', 'nm'],
            scales=self.res,
        )

    def transform(self, i=None):
        if i == None:
            i = self.dm.zpos
        # try:
        #     val = self.state.to_json()['layers'][index]['source']['transform']['matrix']
        #     return val
        # except Exception as e:
        #     print(e)
        #     logger.warning(f'No transform for layer index {index}')
        with self.txn() as s:
            return s.layers[i].layer.source[0].transform

    def set_transform(self, i, transform):
        self._blockStateChanged = True
        with self.txn() as s:
            pass

        self._blockStateChanged = False

    def get_transform(self, afm=None, i=None):
        if i == None:
            i = self.dm.zpos
        if afm == None:
            afm = [[1., 0., 0.], [0., 1., 0.]]
        afm = to_tuples(afm)
        matrix = conv_mat(m=afm, i=i)
        output_dimensions = {'x': [self.res[0], 'nm'],
                             'y': [self.res[1], 'nm'],
                             'z': [self.res[2], 'nm']}
        return ng.CoordinateSpaceTransform(
            {'matrix': matrix, 'outputDimensions': output_dimensions})

    def set_affine(self, afm=None, i=None):
        self._blockStateChanged = True
        if i == None:
            i = self.dm.zpos
        if afm == None:
            afm = [[1., 0., 0.], [0., 1., 0.]]
        transform = self.get_transform(afm=afm, i=i)
        with self.txn() as s:
            s.layers[i].layer.source[0].transform = transform
        self._blockStateChanged = False

    def set_affines(self, items):
        # for testing...
        # items = zip(range(len(cfg.dm)), [a]*len(cfg.dm))
        self._blockStateChanged = True
        with self.txn() as s:
            for item in items:
                s.layers[item[0]].layer.source[0].transform = self.get_transform(afm=item[1], i=item[0])
        self._blockStateChanged = False

    def set_all_affines(self, vals):
        # for testing...
        # items = zip(range(len(cfg.dm)), [a]*len(cfg.dm))
        self._blockStateChanged = True
        assert len(vals) == len(self.dm)
        with self.txn() as s:
            for i, afm in enumerate(vals):
                s.layers[i].layer.source[0].transform = self.get_transform(afm=afm, i=i)
        self._blockStateChanged = False

    def set_untransformed(self):
        # for testing...
        # items = zip(range(len(cfg.dm)), [a]*len(cfg.dm))
        setData('state,neuroglancer,transformed', False)
        self._blockStateChanged = True
        self._show_transformed = True
        afm = [[1., 0., 0.], [0., 1., 0.]]
        with self.txn() as s:
            for i in range(len(self.dm)):
                s.layers[i].layer.source[0].transform = self.get_transform(afm=afm, i=i)
        self._blockStateChanged = False

    def set_transformed(self):
        # for testing...
        # items = zip(range(len(cfg.dm)), [a]*len(cfg.dm))
        setData('state,neuroglancer,transformed', True)
        self._blockStateChanged = True
        self._show_transformed = True
        afms = [self.dm.alt_cafm(l=i) for i in range(len(self.dm))]
        self.set_all_affines(afms)
        self._blockStateChanged = False


    def add_im_layer(self, name, data, afm=None, i=None):
        if i == None:
            i = 0
        with self.txn() as s:
            self.LV = self.getLocalVolume(data, self.getCoordinateSpace())
            transform = self.get_transform(afm=afm, i=i)
            source = ng.LayerDataSource(url=self.LV, transform=transform,)
            s.layers.append(
                name=name,
                layer=ng.ImageLayer(source=source, shader=self.shader),
                opacity=1,
            )

    # def add_transformed_layers(self):
    #     with self.txn() as s:
    #         # shape = self.tensor.shape
    #         for i in range(len(self.dm)):
    #             name = f"l{i}"
    #             # matrix = conv_mat(to_tuples(self.dm.alt_cafm(l=i)), i=i)
    #             afm = self.dm.alt_cafm(l=i)
    #             data = self.tensor[:, :, i:i + 1]
    #             local_volume = self.getLocalVolume(data, self.getCoordinateSpace())
    #             transform = self.get_transform(afm=afm, i=i)
    #             source = ng.LayerDataSource(
    #                 url=local_volume,
    #                 transform=transform, )
    #             if self.name == 'EMViewer':
    #                 name = self.dm.base_image_name(l=i)
    #             else:
    #                 name = f"layer{i}"
    #             s.layers.append(
    #                 name=name,
    #                 layer=ng.ImageLayer(source=source, shader=self.shader),
    #                 opacity=1, )

    def add_transformation_layers(self, affine=False):
        self._blockStateChanged = True
        self._show_transformed = False
        with self.txn() as s:
            # shape = self.tensor.shape
            _range = self.tensor.shape[2]
            for i in range(_range):
                if affine:
                    afm = self.dm.alt_cafm(l=i)
                    # print(f"[{self.name}] [{i}] afm: {afm}")
                else:
                    afm = [[1., 0., 0.], [0., 1., 0.]]
                # matrix = conv_mat(to_tuples(self.dm.alt_cafm(l=i)), i=i)
                data = self.tensor[:, :, i:i + 1]
                local_volume = self.getLocalVolume(data, self.getCoordinateSpace())
                transform = self.get_transform(afm=afm, i=i)
                source = ng.LayerDataSource(url=local_volume, transform=transform, )
                if self.name == 'EMViewer':
                    name = self.dm.base_image_name(l=i)
                else:
                    name = f"layer{i}"
                s.layers.append(
                    name=name,
                    tab='source',
                    layer=ng.ImageLayer(source=source, shader=self.shader,),
                    opacity=1.0,
                    # blend='additive',
                )
        self._blockStateChanged = False



    @abc.abstractmethod
    def set_layer(self, pos=None):
        raise NotImplementedError
    # def set_layer(self, pos=None):
    #
    #     self._blockStateChanged = True
    #     if not pos:
    #         pos = self.dm.zpos
    #     with self.txn() as s:
    #         s.voxel_coordinates[2] = pos + 0.5
    #     # try:
    #     #     self.LV.invalidate()
    #     # except:
    #     #     print_exception()
    #     self._blockStateChanged = False

    def getLocalVolume(self, data, coordinatespace):
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
        # return ng.LocalVolume(
        #     volume_type='image',
        #     data=data,
        #     voxel_offset=[0, 0, 0],
        #     dimensions=coordinatespace,
        #     downsampling='3d',
        #     max_downsampling=cfg.max_downsampling,
        #     max_downsampled_size=cfg.max_downsampled_size,
        # )
        self.LV = ng.LocalVolume(
            volume_type='image',
            data=data,
            voxel_offset=[0, 0, 0],
            dimensions=coordinatespace,
            downsampling='3d',
            max_downsampling=cfg.max_downsampling,
            max_downsampled_size=cfg.max_downsampled_size,
        )
        return self.LV

    # async def get_zarr_tensor(file_path):
    def getTensor(self, path):
        #Todo can this be made async?
        '''**All TensorStore indexing operations produce lazy views**
        https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

        :param path: Fully qualified Zarr file_path
        :return: A TensorStore future object
        :rtype: tensorstore.Future
        '''
        try:
            assert Path(path).exists()
        except AssertionError:
            logger.info(f"No Data At Path: {path}")
            return
        logger.debug(f'Requested: {path}')
        # total_bytes_limit = 256_000_000_000  # Lonestar6: 256 GB (3200 MT/level) DDR4
        total_bytes_limit = 128_000_000_000
        future = ts.open({
            'dtype': 'uint8',
            'driver': 'zarr',
            'kvstore': {
                'driver': 'file',
                'path': path
            },
            'context': {
                'cache_pool': { 'total_bytes_limit': total_bytes_limit, },
                'file_io_concurrency': {'limit': 2056},
            },
            'data_copy_concurrency': {'limit': 512},
            'recheck_cached_data': 'open',

        })

        # recheck_cache_data is what Janelia opensource dataset uses in TensorStore example
        # may need to be False for total_bytes_limit to take effect
        return future

    def set_zoom(self, val):
        # caller = inspect.stack()[1].function
        logger.info(f'Setting zoom to {val}...')
        self._blockStateChanged = True
        with self.txn() as s:
            s.crossSectionScale = val
        self._blockStateChanged = False

    def set_brightness(self, val=None):

        with self.txn() as s:
            for layer in s.layers:
                if val:
                    layer.shaderControls['brightness'] = val
                else:
                    layer.shaderControls['brightness'] = self.dm.brightness


        # state = copy.deepcopy(self.state)
        # for layer in state.layers:
        #     if val:
        #         layer.shaderControls['brightness'] = val
        #     else:
        #         layer.shaderControls['brightness'] = self.dm.brightness
        # self.set_state(state)

    def set_contrast(self, val=None):

        with self.txn() as s:
            for layer in s.layers:
                if val:
                    layer.shaderControls['contrast'] = val
                else:
                    layer.shaderControls['contrast'] = self.dm.contrast

        # state = copy.deepcopy(self.state)
        # for layer in state.layers:
        #     if val:
        #         layer.shaderControls['contrast'] = val
        #     else:
        #         layer.shaderControls['contrast'] = self.dm.contrast
        # self.set_state(state)

    def updateDisplayExtras(self):
        with self.txn() as s:
            s.show_default_annotations = self.dm['state']['neuroglancer']['show_bounds']
            s.show_axis_lines = self.dm['state']['neuroglancer']['show_axes']
            s.show_scale_bar = self.dm['state']['neuroglancer']['show_scalebar']
        with self.config_state.txn() as s:
            s.show_ui_controls = self.dm['state']['neuroglancer']['show_controls']


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

    def clearAllLayers(self):
        #New method
        with self.txn() as s:
            s.layers.clear()

    # def clear_layers(self):
    #     if self.state.layers:
    #         logger.debug('Clearing viewer layers...')
    #         state = copy.deepcopy(self.state)
    #         state.layers.clear()
    #         self.set_state(state)

    def getFrameScale(self, w, h):
        assert hasattr(self, 'tensor')
        tensor_x, tensor_y, _ = self.tensor.shape
        res_x, res_y, _ = self.res  # nm per imagepixel
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

    def __init__(self, **kwags):
        super().__init__(**kwags)
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        # self.view = view
        self.name = 'EMViewer'
        self.shader = self.dm['rendering']['shader']
        print(self.shader)
        self._mats = [None] * len(self.dm)
        self.created = datetime.datetime.now()
        try:
            # zarr.open(self.path, mode='r')
            self.tensor = self.getTensor(self.path).result()[ts.d[:].label["x", "y", "z"]]
        except AssertionError:
            logger.warning(f"Data not found: {self.path}")
            return
        try:
            self.add_transformation_layers()
        except:
            print_exception()
        self.initViewer()

        self.set_brightness()
        self.set_contrast()
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        # asyncio.ensure_future(self.initViewer())
        # self.post_message(f"Voxel Coordinates: {str(self.state.voxel_coordinates)}")
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))

    def set_selected_layer(self):
        with self.txn() as s:
            s.selected_layer.layer = self.dm.base_image_name()

    @Slot()
    def set_layer(self, pos=None):

        self._blockStateChanged = True
        if not pos:
            pos = self.dm.zpos
        with self.txn() as s:
            # s.voxel_coordinates[2] = pos + 0.5
            s.position[2] = pos + 0.5
        # try:
        #     self.LV.invalidate()
        # except:
        #     print_exception()
        self._blockStateChanged = False

    def on_state_changed(self):

        if 1:
            if not self._blockStateChanged:
                # clr = inspect.stack()[1].function
                # logger.info(f'[{self.created}] [{clr}] [{self.name}]')
                self._blockStateChanged = True

                _css = self.state.cross_section_scale
                if not isinstance(_css, type(None)):
                    val = (_css, _css * 250000000)[_css < .001]
                    if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                        if getData('state,neuroglancer,zoom') != val:
                            logger.info(f'emitting zoomChanged! [{val:.4f}]')
                            setData('state,neuroglancer,zoom', val)
                            self.signals.zoomChanged.emit(val)

                if isinstance(self.state.position, np.ndarray):
                    requested = int(self.state.position[2])
                    if requested != self.dm.zpos:
                        logger.info(f'Changing index to {self.dm.zpos}')
                        # with self.txn() as s:
                        #     s.selected_layer.layer = self.dm.base_image_name()
                        self.dm.zpos = requested

                if self.state.layout.type != getData('state,neuroglancer,layout'):
                    self.signals.layoutChanged.emit()

                self._blockStateChanged = False
            # else:
            #     logger.info('State change signal blocked!')



    # async def initViewer(self, nglayout=None):
    def initViewer(self):
        clr = inspect.stack()[1].function
        logger.critical(f'[{clr}] [{self.name}] Initializing Viewer...')
        self._blockStateChanged = True

        with self.config_state.txn() as s:
            s.show_ui_controls = getData('state,neuroglancer,show_controls')

        _request_transformed = getData('state,neuroglancer,transformed')
        if not self.dm.is_aligned():
            _request_transformed = setData('state,neuroglancer,transformed', False)

        # if self._show_transformed != _request_transformed:
        if _request_transformed:
            self.set_transformed()
        else:
            self.set_untransformed()
        with self.txn() as s:
            s.layout.type = getData('state,neuroglancer,layout')
            s.show_scale_bar = getData('state,neuroglancer,show_scalebar')
            s.show_axis_lines = getData('state,neuroglancer,show_axes')
            s.show_default_annotations = getData('state,neuroglancer,show_bounds')
            s.projection_orientation = [0.6299939155578613, 0.10509441047906876, 0.1297515481710434, 0.75843745470047]
            s.position = [self.tensor.shape[0] / 2, self.tensor.shape[1] / 2, self.dm.zpos + 0.5]
            # s.layout.cross_sections["a"] = ng.CrossSection()
            s.show_slices = True
            # s.layout = ng.row_layout(
            #     [
            #         neuroglancer.LayerGroupViewer(
            #             layout="3d",
            #             layers=[f"f{i}" for i in range(len(self.dm))],
            #
            #         ),
            #     ]
            # )
        self._blockStateChanged = False


class TransformViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.name = 'TransformViewer'
        self.title = ''
        self.path = self.dm.path_zarr_raw()
        self.shader = self.dm['rendering']['shader']
        self.section_number = self.dm.zpos
        self.tensor = self.getTensor(self.path).result()[ts.d[:].label["x", "y", "z"]]
        self.initViewer()
        self.set_brightness()
        self.set_contrast()
        with self.config_state.txn() as s:
            s.show_ui_controls = False
            s.show_layer_panel = False
            # s.scale_bar_options.padding_in_pixels = 2  # default = 8
            s.scale_bar_options.left_pixel_offset = 4  # default = 10
            s.scale_bar_options.bottom_pixel_offset = 4  # default = 10
            # s.scale_bar_options.bar_top_margin_in_pixels = 0  # default = 5
            s.scale_bar_options.max_width_fraction = 0.1
            s.scale_bar_options.text_height_in_pixels = 10  # default = 15
            s.scale_bar_options.bar_height_in_pixels = 4  # default = 8
            # s.scale_bar_options.font_name = 'monospace'
            # s.scale_bar_options.font_name = 'serif'
            s.show_layer_side_panel_button = False
            s.show_layer_list_panel_button = False
            s.show_layer_hover_values = False
            s.viewer_size = [self.webengine.width(), self.webengine.height()]
        self.webengine.setUrl(QUrl(self.get_viewer_url()))

        with self.txn() as s:
            s.layout.type = 'xy'
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.show_default_annotations = True
            s.position = [self.tensor.shape[0] / 2, self.tensor.shape[1] / 2, 1.5]

        self.initZoom(w=self.webengine.width(), h=self.webengine.height(), adjust=1.15)


    def initViewer(self):
        self._blockStateChanged = False
        self.clearAllLayers()
        pos = self.dm.zpos
        ref_pos = self.dm.get_ref_index()
        # afm = self.dm.mir_afm()
        # data = self.tensor[:, :, pos:pos + 1]
        # self.add_im_layer('transforming', data, afm, i=1)
        # if ref_pos is not None:
        #     data = self.tensor[:, :, ref_pos:ref_pos + 1]
        #     self.add_im_layer('reference', data, i=0)
        if hasattr(self,'LV'):
            self.LV.invalidate()
        if hasattr(self, 'LV2'):
            self.LV2.invalidate()
        with self.txn() as s:
            afm = self.dm.mir_afm()
            self.LV = self.getLocalVolume(self.tensor[:, :, pos:pos + 1], self.getCoordinateSpace())
            transform = self.get_transform(afm=afm, i=1)
            source = ng.LayerDataSource(url=self.LV, transform=transform, )
            s.layers.append(
                name='transforming',
                layer=ng.ImageLayer(source=source, shader=self.shader),
                opacity=1,
            )
            if ref_pos is not None:
                self.LV2 = self.getLocalVolume(self.tensor[:, :, ref_pos:ref_pos + 1], self.getCoordinateSpace())
                transform = self.get_transform(afm=None, i=0)
                source = ng.LayerDataSource(url=self.LV2, transform=transform, )
                s.layers.append(
                    name='transforming',
                    layer=ng.ImageLayer(source=source, shader=self.shader),
                    opacity=1,
                )
            s.position = [self.tensor.shape[0] / 2, self.tensor.shape[1] / 2, 1.5]
        self.title = f'[{self.dm.zpos}] SNR: {self.dm.snr():.3g}'
        self.webengine.reload()

    @Slot()
    def toggle(self):
        logger.info('')
        with self.txn() as s:
            curpos = floor(s.position[2])
            if curpos == 0:
                newpos = 1.5
                self.title = f'[{self.dm.zpos}] SNR: {self.dm.snr():.3g}'
            else:
                newpos = 0.5
                self.title = f'[{self.dm.get_ref_index()}] SNR: {self.dm.snr():.3g}'
            s.position[2] = newpos

    @Slot()
    def setReference(self):
        logger.info('')
        with self.txn() as s:
            self.title = f'[{self.dm.get_ref_index()}] SNR: {self.dm.snr():.3g}'
            s.position[2] = 0.5

    @Slot()
    def setTransforming(self):
        logger.info('')
        with self.txn() as s:
            self.title = f'[{self.dm.zpos}] SNR: {self.dm.snr():.3g}'
            s.position[2] = 1.5




'''
            self.viewer = self.parent.viewer = PMViewer(self, extra_data={
                    'webengine0': self.webengine0,
                    'resolution': self._images_info['resolution'][level],
                    'raw_path': Path(self.comboImages.currentText()) / 'zarr' / level,
                    'transformed_path': Path(self.comboTransformed.currentText()) / 'zarr' / level,
                })

'''

class PMViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        # self.name = 'PMViewer'
        print(kwags)
        self.name = self.extra_data['name']
        self.shader = '''
                    #uicontrol vec3 color color(default="white")
                    #uicontrol float brightness slider(min=-1, max=1, step=0.01)
                    #uicontrol float contrast slider(min=-1, max=1, step=0.01)
                    void main() { emitRGB(color * (toNormalized(getDataValue()) + brightness) * exp(contrast));}
                    '''

    def initViewer(self):
        path = self.path
        # logger.critical(f"INITIALIZING [{self.name}]\nLoading: {path}")

        if not Path(path).exists():
            logger.warning(f"[{self.name}] not found: {path}")
            self.webengine.setnull()
            return

        if self.name == 'viewer1':
            self.dm = self.parent.dm
            assert hasattr(self.dm, '_data')
            #Todo
            # if not self.dm.is_aligned(s=self.parent.):
            #     self.webengine.setnull()
            #     return


        try:
            # zarr.open(self.raw_path, mode='r')
            self.tensor = self.getTensor(str(path)).result()
            self.vol_source = self.getLocalVolume(self.tensor[:, :, :], self.getCoordinateSpace())
        except:
            logger.warning(f"[{self.name}] Could not open Zarr: {path}")
            print_exception()
            return

        if self.name == 'viewer1':
            if self.dm is not None:
                #Todo fix
                # if self.dm.is_aligned():
                # self.add_transformation_layers(affine=True)
                self.add_transformation_layers(affine=False)
            else:
                # self.webengine.setnull()
                return
        else:
            # self.add_transformation_layers(affine=False)
            self.add_im_layer('layer', self.tensor[:,:,:])

        with self.txn() as s:
            s.layout.type = 'xy'
            s.show_default_annotations = True
            s.show_axis_lines = True
            s.show_scale_bar = False
            if self.name == 'viewer0':
                s.layers['source'] = ng.ImageLayer(source=self.vol_source)
            # _layer_groups = [ng.LayerGroupViewer(layout='xy', layers=['source'])]
            # s.layout = ng.row_layout(_layer_groups)
        with self.config_state.txn() as s:
            s.show_ui_controls = False
        self.webengine.setUrl(QUrl(self.get_viewer_url()))

    def on_state_changed(self):
        pass


class MAViewer(AbstractEMViewer):

    def __init__(self, **kwags):
        super().__init__(**kwags)
        self.name = 'MAViewer'
        # self.role = 'tra'
        self.cs_scale = None
        self.marker_size = 1
        self.shader = self.dm['rendering']['shader']
        self.level_val = self.dm.lvl()
        # self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        # self.signals.ptsChanged.connect(self.drawSWIMwindow)
        try:
            assert Path(self.path).exists()
        except AssertionError:
            logger.warning(f"Data not found: {self.path}")
            return
        self.tensor = self.getTensor(self.path).result()

        self.coordinate_space = self.getCoordinateSpace()
        with self.txn() as s:
            s.layout.type = 'xy'
            s.show_scale_bar = True
            s.show_axis_lines = False
            s.show_default_annotations = False
            x, y, _ = self.tensor.shape
            s.voxel_coordinates = [x / 2, y / 2, 0.5]
        self.initViewer()
        self.shared_state.add_changed_callback(lambda: self.defer_callback(self.on_state_changed))
        # self.shared_state.add_changed_callback(self.on_state_changed)
        self.signals.ptsChanged.connect(self.drawSWIMwindow)
        self.initZoom(w=self.webengine.width(), h=self.webengine.height())
        self.webengine.setUrl(QUrl(self.get_viewer_url()))
        self.webengine.setFocus()


    def set_layer(self):
        self._blockStateChanged = True
        logger.info(f"----> set_layer ---->")
        with self.txn() as s:
            if self.dm['state']['tra_ref_toggle'] == 'ref':
                s.position[2] = 1.5
            else:
                s.position[2] = 0.5

        # neuroglancer.futures.run_on_new_thread(self.drawSWIMwindow)
        self.drawSWIMwindow()
        logger.info(f"<---- set_layer <----")
        self._blockStateChanged = False

    def applyTransformation(self):
        afm = self.dm.mir_afm()
        self.set_affine(afm=afm, i=0)

    def initViewer(self):
        logger.debug('')
        self._blockStateChanged = True
        self.clearAllLayers()
        pos = self.dm.zpos
        ref_pos = self.dm.get_ref_index()
        # afm = self.dm.mir_afm()
        if hasattr(self, 'LV'):
            self.LV.invalidate()
        if hasattr(self, 'LV2'):
            self.LV2.invalidate()
        with self.txn() as s:
            self.LV = self.getLocalVolume(self.tensor[:, :, pos:pos + 1], self.getCoordinateSpace())
            transform = self.get_transform(afm=None, i=1)
            source = ng.LayerDataSource(url=self.LV, transform=transform, )
            s.layers.append(
                name='transforming',
                layer=ng.ImageLayer(source=source, shader=self.shader),
                opacity=1,
            )
            if ref_pos is not None:
                self.LV2 = self.getLocalVolume(self.tensor[:, :, ref_pos:ref_pos + 1], self.getCoordinateSpace())
                transform = self.get_transform(afm=None, i=0)
                source = ng.LayerDataSource(url=self.LV2, transform=transform, )
                s.layers.append(
                    name='transforming',
                    layer=ng.ImageLayer(source=source, shader=self.shader),
                    opacity=1,
                )

        # self.defer_callback(self.drawSWIMwindow)
        self.drawSWIMwindow()
        self._blockStateChanged = False

    def on_state_changed(self):
        logger.info('----> STATE CHANGE ---->')
        if 1:
            if not self._blockStateChanged:
                logger.info(f'')

                self._blockStateChanged = True

                if self.state.cross_section_scale:
                    val = (self.state.cross_section_scale, self.state.cross_section_scale * 250000000)[
                        self.state.cross_section_scale < .001]
                    if round(val, 2) != round(getData('state,neuroglancer,zoom'), 2):
                        if getData('state,neuroglancer,zoom') != val:
                            logger.debug(f'emitting zoomChanged! val = {val:.4f}')
                            setData('state,neuroglancer,zoom', val)
                            self.signals.zoomChanged.emit(val)
                if 1:
                    requested = floor(self.state.position[2])
                    _role = self.dm['state']['tra_ref_toggle']
                    if floor(requested) < 1:
                        _newrole = 'tra'
                    else:
                        _newrole = 'ref'
                    if _role != _newrole:
                        self.dm['state']['tra_ref_toggle'] = _newrole
                        self.drawSWIMwindow()

                self._blockStateChanged = False

        logger.info('<---- STATE CHANGE <----')

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
            x, y, _ = s.mouse_voxel_coordinates
            frac_x = x / self.tensor.shape[0]
            frac_y = y / self.tensor.shape[1]
            logger.debug(f"decimal x = {frac_x}, decimal y = {frac_y}")
            role = self.dm['state']['tra_ref_toggle']
            self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][
                role][id] = (frac_x, frac_y)
            self.signals.ptsChanged.emit()
            neuroglancer.futures.run_on_new_thread(self.drawSWIMwindow)

    def drawSWIMwindow(self):
        # caller = inspect.stack()[1].function
        # logger.info(f"----> [{caller}][{self.index}] drawSWIMwindow ---->")
        # z = self.dm.zpos + 0.5
        self._blockStateChanged = True
        if self.dm['state']['tra_ref_toggle'] == 'ref':
            z = 1.5
        else:
            z = 0.5

        m = self.marker_size
        method = self.dm.current_method
        annotations = []
        if method == 'grid':
            ww1x1 = tuple(self.dm.size1x1())  # full window width
            ww2x2 = tuple(self.dm.size2x2())  # 2x2 window width
            w, h = self.dm.image_size(s=self.dm.level)
            p = getCenterpoints(w, h, ww1x1, ww2x2)
            colors = self.colors[0:sum(self.dm.quadrants)]
            cps = [x for i, x in enumerate(p) if self.dm.quadrants[i]]
            ww_x = ww2x2[0] - (24 // self.level_val)
            ww_y = ww2x2[1] - (24 // self.level_val)
            for i, pt in enumerate(cps):
                c = colors[i]
                d1, d2, d3, d4 = getRect(pt, ww_x, ww_y)
                id = 'roi%d' % i
                annotations.extend([
                    ng.LineAnnotation(id=id + '_0', pointA=d1 + (z,), pointB=d2 + (z,), props=[c, m]),
                    ng.LineAnnotation(id=id + '_1', pointA=d2 + (z,), pointB=d3 + (z,), props=[c, m]),
                    ng.LineAnnotation(id=id + '_2', pointA=d3 + (z,), pointB=d4 + (z,), props=[c, m]),
                    ng.LineAnnotation(id=id + '_3', pointA=d4 + (z,), pointB=d1 + (z,), props=[c, m])])
            # cfg.mw.setFocus()

        elif method == 'manual':
            ww_x = ww_y = self.dm.manual_swim_window_px()
            role = self.dm['state']['tra_ref_toggle']
            pts = self.dm.swim_settings()['method_opts']['points']['coords'][role]
            # z = 1.5
            for i, pt in enumerate(pts):
                if pt:
                    x = self.tensor.shape[0] * pt[0]
                    y = self.tensor.shape[1] * pt[1]
                    d1, d2, d3, d4 = getRect(coords=(x, y), ww_x=ww_x, ww_y=ww_y, )
                    c = self.colors[i]
                    id = 'roi%d' % i
                    annotations.extend([
                        ng.LineAnnotation(id=id + '%d0', pointA=d1 + (z,), pointB=d2 + (z,), props=[c, m]),
                        ng.LineAnnotation(id=id + '%d1', pointA=d2 + (z,), pointB=d3 + (z,), props=[c, m]),
                        ng.LineAnnotation(id=id + '%d2', pointA=d3 + (z,), pointB=d4 + (z,), props=[c, m]),
                        ng.LineAnnotation(id=id + '%d3', pointA=d4 + (z,), pointB=d1 + (z,), props=[c, m])])

            self.webengine.setFocus()

        self.new_annotations = ng.LocalAnnotationLayer(
            annotations=annotations,
            dimensions=self.coordinate_space,
            annotationColor='blue',
            annotation_properties=[
                ng.AnnotationPropertySpec(id='color', type='rgb', default='#ffff66', ),
                ng.AnnotationPropertySpec(id='size', type='float32', default=1, )
            ],
            shader='''void main() {setColor(prop_color()); setPointMarkerSize(prop_size());}''',
        )

        with self.txn() as s:
            if s.layers['SWIM']:
                try:
                    s.layers['SWIM'].annotations = None
                except AttributeError:
                    pass
            s.layers['SWIM'] = self.new_annotations
        self._blockStateChanged = False
        # self.webengine0.reload()
        logger.info(f"<---- drawSWIMwindow <----")
        # print("<< drawSWIMwindow", flush=True)

    # def undrawSWIMwindows(self):
    #     #Fast, ~0.002
    #     with self.txn() as s:
    #         if s.layers['SWIM']:
    #             try:
    #                 s.layers['SWIM'].annotations = None
    #             except AttributeError:
    #                 pass




@cache
def getCenterpoints(w, h, ww1x1, ww2x2):
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
def getRect(coords, ww_x, ww_y):
    x, y = coords[0], coords[1]
    hw = int(ww_x / 2)  # Half-width
    hh = int(ww_y / 2)  # Half-height
    A = (x + hh, y - hw)
    B = (x + hh, y + hw)
    C = (x - hh, y + hw)
    D = (x - hh, y - hw)
    return A, B, C, D


@cache
def conv_mat(m=None, i=0):
    if m == None:
        m = [[1., 0., 0.], [0., 1., 0.]]
    o = [[.999, 0., 0., 0.],
         [0., 1., 0., 0.],
         [0., 0., 1., i]]
    o[0][0] = m[0][0]
    o[0][1] = m[0][1]
    o[0][3] = m[0][2]
    o[1][0] = m[1][0]
    o[1][1] = m[1][1]
    o[1][3] = m[1][2]
    return o


def to_tuples(arg):
    return tuple(tuple(x) for x in arg)


def transpose(m):
    return np.array([[m[1][1], m[1][0], m[1][2]],
            [m[0][1], m[0][0], m[0][2]]])




"""

# Code for not using TensorStore, point Neuroglancer directly at local Zarr
# cfg.refLV = cfg.baseLV = f'zarr://http://localhost:{self.port}/{unal_path}'
# if is_aligned_and_generated:  cfg.alLV = f'zarr://http://localhost:{self.port}/{al_path}'

total_bytes_limit : integer[0, +∞) = 0¶
Soft limit on the total number of bytes in the cache. The least-recently used data 
that is not in use is evicted from the cache when this limit is reached.

Context.data_copy_concurrency : object¶
Specifies a limit on the number of CPU cores used concurrently for data copying/encoding/decoding.

Optional members¶
limit : integer[1, +∞) | "shared" = "shared"¶
    The maximum number of CPU cores that may be used. If the special value of "shared" is specified, a shared global limit equal to the number of CPU cores/threads available applies.


"""

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source', type=str, required=True, default='.', help='Directory to serve')
    ap.add_argument('-b', '--bind', type=str, default='127.0.0.1', help='Bind address')
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on')
    args = ap.parse_args()

    EMViewer()
    EMViewer.initViewer()
