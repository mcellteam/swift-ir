#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import neuroglancer
import operator
import logging, json
import numpy as np
import zarr
import daisy
import skimage.measure
import tifffile, imagecodecs
import dask.array as da

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



