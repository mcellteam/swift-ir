#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import webbrowser
import neuroglancer
import operator
import logging, json
import numpy as np
import zarr
import daisy
import skimage.measure
import tifffile, imagecodecs
import dask.array as da

import multiprocessing
import os, time
import neuroglancer as ng
from glob import glob
from PIL import Image

logger = logging.getLogger(__name__)


class RequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)


class Server(HTTPServer):
    protocol_version = 'HTTP/1.1'

    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, RequestHandler)


def get_json(path):
    with open(path) as f:
        return json.load(f)
        # example: keys = get_json("project.zarr/img_aligned_zarr/s0/.zarray")

# CREME DE LA CREME - BEAUTIFUL IMPLEMENTATION
# Convert Tiffs to Zarr with implicit dask array
# Ref: https://forum.image.sc/t/store-many-tiffs-into-equal-sized-tiff-stacks-for-hdf5-zarr-chunks-using-ome-tiff-format/61055
def tiffs2zarr(tif_files, zarrurl, chunkshape, overwrite=True, **kwargs):
    def imread(filename):
        with open(filename, 'rb') as fh:
            data = fh.read()
        return imagecodecs.tiff_decode(data) # return first image in TIFF file as numpy array

    with tifffile.FileSequence(imread, tif_files) as tifs:
        with tifs.aszarr() as store:
            array = da.from_zarr(store)
            #array.visualize(filename='_dask_visualize.png') # print dask task graph to file
            # array.shape[1:]= (5332, 5332)
            array.rechunk(chunkshape).to_zarr(zarrurl, overwrite=True, **kwargs)
            # NOTE **kwargs is passed to Passed to the zarr.creation.create() function, e.g., compression options.
            # https://zarr.readthedocs.io/en/latest/api/creation.html#zarr.creation.create

def open_ds(path, ds_name):
    """ wrapper for daisy.open_ds """
    print("Running daisy.open_ds with path:" + path + ", ds_name:" + ds_name)
    try:
        return daisy.open_ds(path, ds_name)
    except KeyError:
        print("\n  ERROR: dataset " + ds_name + " could not be loaded. Must be Daisy-like array.\n")
        return None


def unchunk(s):
    print("'u' key press detected. Executing unchunk function...")
    # this is parallel
    path = src
    scale = 0
    n_unchunk = int(s.mouse_voxel_coordinates[2])
    #img_scale = da.from_zarr(path + '/img_aligned_zarr/s' + str(scale))
    img_scale = da.from_zarr(path + '/' + ds_aligned + '/s0')
    curr_img = img_scale[n_unchunk, :, :]
    skimage.io.imsave('image_' + str(n_unchunk) + '_scale' + str(scale) + '.tif', curr_img)

    print("Callback complete.")

# def unchunk_all_scale(s, scale):
#     # this can be parallel

def blend(s):
    print("'b' key press detected. Executing blend function...")
    blend_scale = 0
    n_blend = int(s.mouse_voxel_coordinates[2])
    blend_name = 'blended_' + str(n_blend) + '-' + str(n_blend + 1) + '.tif'

    print("Creating blended TIF of images " + str(n_blend) + " and " + str(n_blend+1) + " using PIL.Image...")

    #img_scale = da.from_zarr(src + '/img_aligned_zarr/s0')
    img_scale = da.from_zarr(src + '/' + ds_aligned + '/s' + str(blend_scale))
    curr_img = img_scale[n_blend, :, :]
    next_img = img_scale[n_blend+1, :, :]
    out1 = 'temp_image_' + str(n_blend) + '.tif'
    out2 = 'temp_image_' + str(n_blend+1) + '.tif'
    skimage.io.imsave(out1, curr_img)
    skimage.io.imsave(out2, next_img)

    img1 = Image.open(out1)
    img2 = Image.open(out2)

    result = Image.blend(img1, img2, 0.5)
    print('Removing temporary TIF files...')
    os.remove(out1)
    os.remove(out2)

    print('Saving image blend as temporary TIF ' + blend_name + '...')
    result.save(blend_name)

    copy_json = json.loads(open(os.path.join(src, ds_aligned, 's0', '.zattrs')).read())

    print('Reading .zarray for ...')

    print('Adding blend to Zarr group ' + ds_blended + '...')
    """ NOTE **kawgs is passed to zarr.creation.create """
    """ https://zarr.readthedocs.io/en/latest/api/creation.html#zarr.creation.create """
    #tiffs2zarr(blend_name, os.path.join(src, ds_blended), tuple(chunks), compressor=Blosc(cname=cname, clevel=clevel), overwrite=True)
    tiffs2zarr(blend_name, os.path.join(src, ds_blended), tuple(chunks), compressor=Blosc(cname='zstd', clevel=1), overwrite=True) #jy
    print('Removing temporary TIF: ' + blend_name + '...')
    os.remove(blend_name)
    print('Copying json for appropriate scale...')
    ds = zarr.open(os.path.join(src,ds_blended), mode='a')
    copy_json = json.loads(open(os.path.join(src, ds_aligned, 's' + str(blend_scale), '.zattrs')).read())
    ds.attrs['offset'] = copy_json['offset']
    #ds.attrs['resolution'] = copy_json['resolution']
    #ds.attrs['resolution'] = [50,.00000001,.00000001]

    copy_json = json.loads(open(os.path.join(src, ds_aligned, 's0', '.zattrs')).read())
    ds.attrs['units'] = copy_json['units']
    ds.attrs['_ARRAY_DIMENSIONS'] = copy_json['_ARRAY_DIMENSIONS']
    # ds.attrs['_ARRAY_DIMENSIONS'] = copy_json['_ARRAY_DIMENSIONS']

    #compressor = {'id': cname, 'level': clevel}
    #create_scale_pyramid(src, ds_blended, scales, chunks, compressor)


    # z = zarr.open(os.path.join(src, ds_blended))
    # print("Creating blend ng.LocalVolume...")
    # try:
    #     blend_vol = ng.LocalVolume(
    #         data=z,
    #         dimensions=dimensions)
    # except:
    #     print("  ERROR creating blend ng.LocalVolume")

    s.layers['focus'].visible = True
    print("Updating viewer.txn()...")
    with viewer.txn() as s:
        try:
            s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr", voxel_size=[i * .00000001 for i in resolution])
        except:
            print("  ERROR updating viewer.txn() with blend_vol ImageLayer")

    print("Callback complete.")

    # im = Image.open(f_result)
    # im.show()

    # POSSIBLE WORKFLOW FOR VIEWING SINGLE BLEND IN NEUROGLANCER VIEWER
    # 1. Create blended image
    # 2. If project.zarr/img_blended_zarr group does not exist, create it
    # 3. Converted blended image to Zarr using tiffs2zarr utility function (from glanceem_utils.py).
    # 4. Blended image array is appended to project.zarr/img_blended_zarr
    # 5. Neuroglancer viewer top panel is updated to display Zarr group img_blended_zarr


# example keypress callback
def get_mouse_coords(s):
    print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
    print('  Layer selected values: %s' % (s.selected_values,))




def get_viewer_url(src):
    print("\n\nCalling get_viewer_url(src)...\n\n")

    Image.MAX_IMAGE_PIXELS = None

    bind = '127.0.0.1'
    port = 9000
    view = 'single'

    res_x = 2
    res_y = 2
    res_z = 50

    print("Setting multiprocessing.set_start_method('fork', force=True)...")
    multiprocessing.set_start_method("fork", force=True)

    # LOAD METADATA - .zarray
    print("Loading metadata from .zarray")
    zarray_path = os.path.join(src, "img_aligned_zarr", "s0", ".zarray")
    print("zarray_path : ", zarray_path)
    with open(zarray_path) as f:
        zarray_keys = json.load(f)
    chunks = zarray_keys["chunks"]

    # cname = zarray_keys["compressor"]["cname"] #jy
    # clevel = zarray_keys["compressor"]["clevel"] #jy

    shape = zarray_keys["shape"]

    # LOAD META DATA - .zattrs
    print("Loading metadata from .zattrs")
    zattrs_path = os.path.join(src, "img_aligned_zarr", "s0", ".zattrs")
    with open(zattrs_path) as f:
        zattrs_keys = json.load(f)
    print("zattrs_path : ", zattrs_path)
    resolution = zattrs_keys["resolution"]
    scales = zattrs_keys["scales"]

    print("scales : ", scales)

    ds_ref = "img_ref_zarr"
    ds_base = "img_base_zarr"
    ds_aligned = "img_aligned_zarr"
    ds_blended = "img_blended_zarr"

    print("Preparing browser view of " + src + "...")
    print("bind                       :", bind)
    print("port                       :", port)

    # os.chdir(src)
    if 0:
        server = Server((bind, port))
        sa = server.socket.getsockname()
        host = str("http://%s:%d" % (sa[0], sa[1]))
        print("Serving                         :", host)
        viewer_source = str("zarr://" + host)
        print("Viewer source                   :", viewer_source)
        print("Protocol version                :", server.protocol_version)
        print("Server name                     :", server.server_name)
        print("Server type                     :", server.socket_type)
        # print("allow reuse address= ", server.allow_reuse_address)


    print("Creating neuroglancer.Viewer()...")
    viewer = ng.Viewer()

    print("img_unaligned_zarr exists in source.")
    print("Looking for REF scale directories...")
    data_ref = []
    ref_scale_paths = glob(os.path.join(src, ds_ref) + "/s*")
    for s in ref_scale_paths:
        scale = os.path.join(ds_ref, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending ref data...")
        data_ref.append(open_ds(src, scale))

    print("img_unaligned_zarr exists in source.")
    print("Looking for BASE scale directories...")
    data_base = []
    base_scale_paths = glob(os.path.join(src, ds_base) + "/s*")
    for s in base_scale_paths:
        scale = os.path.join(ds_base, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending base data...")
        data_base.append(open_ds(src, scale))

    print("img_aligned_zarr data set exists in source.")
    print("Looking for ALIGNED scale directories...")
    data_aligned = []
    aligned_scale_paths = glob(os.path.join(src, ds_aligned) + "/s*")
    for s in aligned_scale_paths:
        scale = os.path.join(ds_aligned, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending aligned data...")
        data_aligned.append(open_ds(src, scale))

    print("Defining coordinate space...")
    dimensions = ng.CoordinateSpace(
        names=['x', 'y', 'z'],
        units='nm',
        # scales=scales, #jy
        scales=[res_x, res_y, res_z],
    )

    # https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
    print("Updating viewer.txn()...")
    with viewer.txn() as s:

        s.cross_section_background_color = "#ffffff"
        s.dimensions = dimensions
        # s.perspective_zoom = 300
        # s.position = [0.24, 0.095, 0.14]
        # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

        # temp = np.zeros_like(data_ref)
        # layer = ng.Layer(temp)

        # only for 3 pane view
        if view == 'row':
            add_layer(s, data_ref, 'ref')
            add_layer(s, data_base, 'base')

        add_layer(s, data_aligned, 'aligned')

        ###data_panel_layout_types: frozenset(['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'])

        # s.selectedLayer.visible = False
        # s.layers['focus'].visible = False

        # view = "single"

        if view == "row":
            print("view= row")

            s.layers['focus'].visible = True

            # [
            #     ng.LayerGroupViewer(layers=["focus"], layout='xy'),

            # temp = np.zeros_like(data_ref)
            # #layer = ng.Layer()
            # #layer = ng.ManagedLayer
            # s.layers['focus'] = ng.LocalVolume(temp)

            # s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr",voxel_size=[i * .00000001 for i in resolution])
            s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
            s.layout = ng.column_layout(
                [
                    ng.row_layout(
                        [
                            ng.LayerGroupViewer(layers=["focus"], layout='xy'),
                        ]
                    ),

                    ng.row_layout(
                        [
                            ng.LayerGroupViewer(layers=['ref'], layout='xy'),
                            ng.LayerGroupViewer(layers=['base'], layout='xy'),
                            ng.LayerGroupViewer(layers=['aligned'], layout='xy'),
                        ]
                    ),
                ]
            )

            # s.layout = ng.column_layout(
            #
            #     [
            #         ng.LayerGroupViewer(layers=["focus"], layout='xy'),
            #
            # s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
            #
            # ng.row_layout(
            #     [
            #         ng.LayerGroupViewer(layers=["ref"], layout='xy'),
            #         ng.LayerGroupViewer(layers=["base"], layout='xy'),
            #         ng.LayerGroupViewer(layers=["aligned"], layout='xy'),
            #     ]
            # )
            #
            #
            #
            #
            #     ]
            #
            # ]
            # # )

        # single image view
        if view == "single":
            print('view= single')
            s.layout = ng.column_layout(
                [
                    ng.LayerGroupViewer(
                        layout='xy',
                        layers=["aligned"]),
                ]
            )

    viewer.actions.add('get_mouse_coords_', get_mouse_coords)
    viewer.actions.add('unchunk_', unchunk)
    viewer.actions.add('blend_', blend)
    with viewer.config_state.txn() as s:
        s.input_event_bindings.viewer['keyt'] = 'get_mouse_coords_'
        s.input_event_bindings.viewer['keyu'] = 'unchunk_'
        s.input_event_bindings.viewer['keyb'] = 'blend_'
        s.status_messages['message'] = 'Welcome to glanceEM_SWiFT!'

        s.show_ui_controls = True
        s.show_panel_borders = True
        s.viewer_size = None

    viewer_url = str(viewer)
    webbrowser.open(viewer_url) #jy
    print("Printing viewer state...")
    print(viewer.state)
    # print("\nNeuroglancer view (remote viewer)    :\n", ng.to_url(viewer.state))
    print("\nNeuroglancer view (local viewer)     :\n", viewer, "\n")

    #time.sleep(60)

    return(viewer_url)







# # fsspec integration of tifffile
# with tifffile.imread(tiff_filename, aszarr=True) as store:
#     store.write_fsspec(tiff_filename + '.json', url)

class ScalePyramid(neuroglancer.LocalVolume):
    """A neuroglancer layer that provides volume data on different scales.
    Mimics a LocalVolume.

    Args:

            volume_layers (``list`` of ``LocalVolume``):

                One ``LocalVolume`` per provided resolution.
    """

    def __init__(self, volume_layers):
        volume_layers = volume_layers

        super(neuroglancer.LocalVolume, self).__init__()

        logger.debug("Creating scale pyramid...")

        self.min_voxel_size = min(
            [tuple(layer.dimensions.scales) for layer in volume_layers]
        )
        self.max_voxel_size = max(
            [tuple(layer.dimensions.scales) for layer in volume_layers]
        )

        self.dims = len(volume_layers[0].dimensions.scales)
        self.volume_layers = {
            tuple(
                int(x)
                for x in map(
                    operator.truediv, layer.dimensions.scales, self.min_voxel_size
                )
            ): layer
            for layer in volume_layers
        }

        logger.debug("min_voxel_size: %s", self.min_voxel_size)
        logger.debug("scale keys: %s", self.volume_layers.keys())
        logger.debug(self.info())

    @property
    def volume_type(self):
        return self.volume_layers[(1,) * self.dims].volume_type

    @property
    def token(self):
        return self.volume_layers[(1,) * self.dims].token

    def info(self):

        reference_layer = self.volume_layers[(1,) * self.dims]
        # return reference_layer.info()

        reference_info = reference_layer.info()

        info = {
            "dataType": reference_info["dataType"],
            "encoding": reference_info["encoding"],
            "generation": reference_info["generation"],
            "coordinateSpace": reference_info["coordinateSpace"],
            "shape": reference_info["shape"],
            "volumeType": reference_info["volumeType"],
            "voxelOffset": reference_info["voxelOffset"],
            "chunkLayout": reference_info["chunkLayout"],
            "downsamplingLayout": reference_info["downsamplingLayout"],
            "maxDownsampling": int(
                np.prod(np.array(self.max_voxel_size) // np.array(self.min_voxel_size))
            ),
            "maxDownsampledSize": reference_info["maxDownsampledSize"],
            "maxDownsamplingScales": reference_info["maxDownsamplingScales"],
        }

        return info

    def get_encoded_subvolume(self, data_format, start, end, scale_key=None):
        if scale_key is None:
            scale_key = ",".join(("1",) * self.dims)

        scale = tuple(int(s) for s in scale_key.split(","))

        return self.volume_layers[scale].get_encoded_subvolume(
            data_format, start, end, scale_key=",".join(("1",) * self.dims)
        )

    def get_object_mesh(self, object_id):
        return self.volume_layers[(1,) * self.dims].get_object_mesh(object_id)

    def invalidate(self):
        return self.volume_layers[(1,) * self.dims].invalidate()


def add_layer(
    context,
    array,
    name,
    opacity=None,
    shader=None,
    visible=True,
    reversed_axes=False,
    scale_rgb=False,
    c=[0, 1, 2],
    h=[0.0, 0.0, 1.0],
):

    """Add a layer to a neuroglancer context.

    Args:

        context:

            The neuroglancer context to add a layer to, as obtained by
            ``viewer.txn()``.

        array:

            A ``daisy``-like array, containing attributes ``roi``,
            ``voxel_size``, and ``data``. If a list of arrays is given, a
            ``ScalePyramid`` layer is generated.

        name:

            The name of the layer.

        opacity:

            A float to define the layer opacity between 0 and 1

        shader:

            A string to be used as the shader. If set to ``'rgb'``, an RGB
            shader will be used.

        visible:

            A bool which defines layer visibility

        c (channel):

            A list of ints to define which channels to use for an rgb shader

        h (hue):

            A list of floats to define rgb color for an rgba shader
    """

    is_multiscale = type(array) == list

    print("is_multiscale=",is_multiscale)

    if not is_multiscale:

        a = array if not is_multiscale else array[0]

        spatial_dim_names = ["t", "z", "y", "x"]
        channel_dim_names = ["b^", "c^"]

        dims = len(a.data.shape)
        spatial_dims = a.roi.dims()
        channel_dims = dims - spatial_dims

        attrs = {
            "names": (channel_dim_names[-channel_dims:] if channel_dims > 0 else [])
            + spatial_dim_names[-spatial_dims:],
            "units": [""] * channel_dims + ["nm"] * spatial_dims,
            "scales": [1] * channel_dims + list(a.voxel_size),
        }
        if reversed_axes:
            attrs = {k: v[::-1] for k, v in attrs.items()}
        dimensions = neuroglancer.CoordinateSpace(**attrs)

        voxel_offset = [0] * channel_dims + list(a.roi.get_offset() / a.voxel_size)

    else:
        dimensions = []
        voxel_offset = None
        for i, a in enumerate(array):

            spatial_dim_names = ["t", "z", "y", "x"]
            channel_dim_names = ["b^", "c^"]

            dims = len(a.data.shape)
            spatial_dims = a.roi.dims()
            channel_dims = dims - spatial_dims

            attrs = {
                "names": (channel_dim_names[-channel_dims:] if channel_dims > 0 else [])
                + spatial_dim_names[-spatial_dims:]
                if spatial_dims > 0
                else [],
                "units": [""] * channel_dims + ["nm"] * spatial_dims,
                "scales": [1] * channel_dims + list(a.voxel_size),
            }
            if reversed_axes:
                attrs = {k: v[::-1] for k, v in attrs.items()}
            dimensions.append(neuroglancer.CoordinateSpace(**attrs))

            if voxel_offset is None:
                voxel_offset = [0] * channel_dims + list(
                    a.roi.get_offset() / a.voxel_size
                )

    if reversed_axes:
        voxel_offset = voxel_offset[::-1]

    if shader is None:
        a = array if not is_multiscale else array[0]
        dims = a.roi.dims()
        if dims < len(a.data.shape):
            channels = a.data.shape[0]
            if channels > 1:
                shader = "rgb"

    if shader == "rgb":
        if scale_rgb:
            shader = """
void main() {
    emitRGB(
        255.0*vec3(
            toNormalized(getDataValue(%i)),
            toNormalized(getDataValue(%i)),
            toNormalized(getDataValue(%i)))
        );
}""" % (
                c[0],
                c[1],
                c[2],
            )

        else:
            shader = """
void main() {
    emitRGB(
        vec3(
            toNormalized(getDataValue(%i)),
            toNormalized(getDataValue(%i)),
            toNormalized(getDataValue(%i)))
        );
}""" % (
                c[0],
                c[1],
                c[2],
            )

    elif shader == "rgba":
        shader = """
void main() {
    emitRGBA(
        vec4(
        %f, %f, %f,
        toNormalized(getDataValue()))
        );
}""" % (
            h[0],
            h[1],
            h[2],
        )

    elif shader == "mask":
        shader = """
void main() {
  emitGrayscale(255.0*toNormalized(getDataValue()));
}"""

    elif shader == "heatmap":
        shader = """
void main() {
    float v = toNormalized(getDataValue(0));
    vec4 rgba = vec4(0,0,0,0);
    if (v != 0.0) {
        rgba = vec4(colormapJet(v), 1.0);
    }
    emitRGBA(rgba);
}"""

    kwargs = {}

    if shader is not None:
        kwargs["shader"] = shader
    if opacity is not None:
        kwargs["opacity"] = opacity

    if is_multiscale:
        print("is_multiscale is True. Running layer = ScalePyramid, creating ng.LocalVolume...")
        print("voxel_offset             : ", voxel_offset)
        print("data                     : ", array)
        print("dimensions               : ", dimensions)


        layer = ScalePyramid(
            [
                neuroglancer.LocalVolume(
                    data=a.data, voxel_offset=voxel_offset, dimensions=array_dims
                )
                for a, array_dims in zip(array, dimensions)
            ]
        )

    else:
        print("is_multiscale is False. Creating ng.LocalVolume...")
        layer = neuroglancer.LocalVolume(
            data=array.data,
            voxel_offset=voxel_offset,
            dimensions=dimensions,
        )

    context.layers.append(name=name, layer=layer, visible=visible, **kwargs)


def downscale_block(in_array, out_array, factor, block):

    dims = len(factor)
    in_data = in_array.to_ndarray(block.read_roi, fill_value=0)

    in_shape = daisy.Coordinate(in_data.shape[-dims:])
    assert in_shape.is_multiple_of(factor)

    n_channels = len(in_data.shape) - dims
    if n_channels >= 1:
        factor = (1,)*n_channels + factor

    if in_data.dtype == np.uint64:
        slices = tuple(slice(k//2, None, k) for k in factor)
        out_data = in_data[slices]
    else:
        out_data = skimage.measure.block_reduce(in_data, factor, np.mean)

    try:
        out_array[block.write_roi] = out_data
    except Exception:
        print("Failed to write to %s" % block.write_roi)
        raise

    return 0



def downscale(in_array, out_array, factor, write_size):

    print("Downsampling by factor %s" % (factor,))

    dims = in_array.roi.dims()
    block_roi = daisy.Roi((0,)*dims, write_size)

    print("Processing ROI %s with blocks %s" % (out_array.roi, block_roi))

    daisy.run_blockwise(
        out_array.roi,
        block_roi,
        block_roi,
        process_function=lambda b: downscale_block(
            in_array,
            out_array,
            factor,
            b),
        read_write_conflict=False,
        #num_workers=60, #jy
        #num_workers=8,
        num_workers=4,
        max_retries=0,
        #max_retries=3,
        fit='shrink')


#def create_scale_pyramid(in_file, in_ds_name, scales, chunk_shape, cname, clevel):
def create_scale_pyramid(in_file, in_ds_name, scales, chunk_shape, compressor):
    """
    # https://zarr.readthedocs.io/en/stable/api/convenience.html#zarr.convenience.open
    # https://zarr.readthedocs.io/en/stable/_modules/zarr/convenience.html
    #ds = zarr.open(in_file)
    # refer to convenience.py zarr source code
    # no mode specified, default is mode='a'

    prepare_ds
    see: https://daisy-docs.readthedocs.io/_/downloads/en/latest/pdf/
    also: https://daisy-docs.readthedocs.io/en/latest/api.html
    """



    ds = zarr.open(in_file)

    # make sure in_ds_name points to a dataset
    try:
        daisy.open_ds(in_file, in_ds_name)
    except Exception:
        raise RuntimeError("%s does not seem to be a dataset" % in_ds_name)

    if not in_ds_name.endswith('/s0'):

        ds_name = in_ds_name + '/s0'

        print("Moving %s to %s" % (in_ds_name, ds_name))
        ds.store.rename(in_ds_name, in_ds_name + '__tmp')
        ds.store.rename(in_ds_name + '__tmp', ds_name)

    else:

        ds_name = in_ds_name
        in_ds_name = in_ds_name[:-3]

    print("Scaling %s by a factor of %s" % (in_file, scales))

    prev_array = daisy.open_ds(in_file, ds_name)

    if chunk_shape is not None:
        chunk_shape = daisy.Coordinate(chunk_shape)
    else:
        chunk_shape = daisy.Coordinate(prev_array.data.chunks)
        print("Reusing chunk shape of %s for new datasets" % (chunk_shape,))

    if prev_array.n_channel_dims == 0:
        num_channels = 1
    elif prev_array.n_channel_dims == 1:
        num_channels = prev_array.shape[0]
    else:
        raise RuntimeError(
            "more than one channel not yet implemented, sorry...")

    for scale_num, scale in enumerate(scales):

        try:
            scale = daisy.Coordinate(scale)
        except Exception:
            scale = daisy.Coordinate((scale,)*chunk_shape.dims())

        next_voxel_size = prev_array.voxel_size*scale
        next_total_roi = prev_array.roi.snap_to_grid(
            next_voxel_size,
            mode='grow')
        next_write_size = chunk_shape*next_voxel_size

        print("Next voxel size: %s" % (next_voxel_size,))
        print("Next total ROI: %s" % next_total_roi)
        print("Next chunk size: %s" % (next_write_size,))

        next_ds_name = in_ds_name + '/s' + str(scale_num + 1)
        print("Preparing %s" % (next_ds_name,))

        print("compressor=",compressor)

        if isinstance(compressor, dict):
            print("compressor is a dict...")
            # cname = compressor['cname']
            # clevel = compressor['clevel']
            next_array = daisy.prepare_ds(
                in_file,
                next_ds_name,
                total_roi=next_total_roi,
                voxel_size=next_voxel_size,
                write_size=next_write_size,
                dtype=prev_array.dtype,
                num_channels=num_channels,
                compressor=compressor
                #compressor={'id': cname, 'level': clevel}
            )
        elif isinstance(compressor, str):
            print("compressor is a string...")
            next_array = daisy.prepare_ds(
                in_file,
                next_ds_name,
                total_roi=next_total_roi,
                voxel_size=next_voxel_size,
                write_size=next_write_size,
                dtype=prev_array.dtype,
                num_channels=num_channels,
                compressor=compressor
                #compressor={'id': cname, 'level': clevel}
            )

        # elif compressor=='none':
        #     next_array = daisy.prepare_ds(
        #         in_file,
        #         next_ds_name,
        #         total_roi=next_total_roi,
        #         voxel_size=next_voxel_size,
        #         write_size=next_write_size,
        #         dtype=prev_array.dtype,
        #         num_channels=num_channels,
        #         compressor=None  # added for passing in compressor from **kwargs
        #     )

        else:
            print("compressor is neither a dict nor a string...")
            next_array = daisy.prepare_ds(
                in_file,
                next_ds_name,
                total_roi=next_total_roi,
                voxel_size=next_voxel_size,
                write_size=next_write_size,
                dtype=prev_array.dtype,
                num_channels=num_channels,
                compressor=compressor  # added for passing in compressor from **kwargs
                # note - must support case where compressor is a bool (None)
            )



        """
        # I dont believe I need this case
        if compressor is None:
            next_array = daisy.prepare_ds(
            in_file,
            next_ds_name,
            total_roi=next_total_roi,
            voxel_size=next_voxel_size,
            write_size=next_write_size,
            dtype=prev_array.dtype,
            num_channels=num_channels,
            compressor=None
            )


        """
            # default: compressor = {'id': 'gzip', 'level': 5}

            # API ref: https://daisy-docs.readthedocs.io/en/latest/api.html
            # source: https://daisy-docs.readthedocs.io/en/latest/_modules/daisy/datasets.html#prepare_ds


        downscale(prev_array, next_array, scale, next_write_size)

        prev_array = next_array



