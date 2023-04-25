#!/usr/bin/env python3

import json
import logging
import multiprocessing as mp
import os
import platform
import psutil
import shutil
import inspect
import sys
import time
import numpy as np
from glob import glob
from pathlib import Path

import tensorstore as ts
import tifffile
import zarr
from numcodecs import Blosc
from numcodecs import Zstd
import numcodecs
numcodecs.blosc.use_threads = False
# import imagecodecs
# import dask.array as da
import src.config as cfg
from src.funcs_image import imageio_read_image
from src.helpers import get_scale_val, time_limit, print_exception, get_scales_with_generated_alignments

'''
TensorStore has already been used to solve key engineering challenges in scientific computing (e.g., management and 
processing of large datasets in neuroscience, such as peta-s 3d electron microscopy datamodel and “4d” videos of 
neuronal activity). TensorStore has also been used in the creation of large-s machine learning models such as 
PaLM by addressing the problem of managing previewmodel parameters (checkpoints) during distributed training.
https://www.reddit.com/r/worldTechnology/comments/xuw7kk/tensorstore_for_highperformance_scalable_array/
'''

__all__ = ['preallocate_zarr', 'tiffs2MultiTiff', 'write_metadata_zarr_multiscale']

logger = logging.getLogger(__name__)


def get_zarr_tensor(zarr_path):
    '''
    Returns an asynchronous TensorStore future object which is a webengineview
    into the Zarr image on disk. All TensorStore indexing operations
    produce lazy views.

    Ref: https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

    :param zarr_path:
    :cur_method zarr_path:
    :return: A webengineview into the dataset.
    :rtype: tensorstore.Future
    '''
    logger.info('Getting Zarr tensor at %s' %zarr_path)
    node = platform.node()
    if '.tacc.utexas.edu' in node:
        # Lonestar6: 256 GB (3200 MT/s) DDR4
        # total_bytes_limit = 200_000_000_000
        total_bytes_limit = 250_000_000_000 # just under 256 GB
    else:
        total_bytes_limit = 6_000_000_000
    # total_bytes_limit = (6_000_000_000, 200_000_000_000_000)['.tacc.utexas.edu' in platform.node()]
    arr = ts.open({
        'dtype': 'uint8',
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            # 'driver': 'memory',
            'path': zarr_path
        },
        'context': {
            'cache_pool': {'total_bytes_limit': total_bytes_limit},
            # 'data_copy_concurrency': {'limit': 128},
            # 'file_io_concurrency': {'limit': 128},
        },
        'recheck_cached_data': 'open',
    })
    return arr


def get_zarr_array_layer_view(zarr_path:str, l=None):
    if l == None: l = cfg.data.zpos
    arr = ts.open({
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            'path': zarr_path,
        },
        'path': 'temp.zarr',
        'metadata': {
            'dtype': '<f4',
            'shape': list(cfg.data.resolution()),
            'chunks': list(cfg.data.chunkshape()),
            'order': 'C',
        },
    }, create=True).result()
    # arr[1] = 42  # Overwrites, just like numpy/zarr library
    view = arr[l, :, :]  # Returns a lazy view, no I/O performed
    np.array(view)  # Reads from the view
    # Returns JSON spec that can be passed to `ts.open` to reopen the view.
    view.spec().to_json()
    return view


def get_tensor_from_tiff(dir=None, s=None, l=None):
    if s == None: s = cfg.data.scale
    if l == None: l = cfg.data.zpos
    fn = os.path.basename(cfg.data.base_image_name(s=s, l=l))
    path = os.path.join(cfg.data.dest(), s, 'img_src', fn)
    logger.info('Path: %s' % path)
    arr = ts.open({
        'driver': 'tiff',
        'kvstore': {
            'driver': 'file',
            'path': path,
        },
    }, create=True).result()
    return arr


def get_zarr_tensor_layer(zarr_path:str, layer:int):
    '''
    Returns an asynchronous TensorStore future object which is a webengineview
    into the Zarr image on disk. All TensorStore indexing operations
    produce lazy views.

    Ref: https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

    :param zarr_path:
    :cur_method zarr_path:
    :return: A webengineview into the dataset.
    :rtype: tensorstore.Future
    '''
    node = platform.node()
    if '.tacc.utexas.edu' in node:
        # Lonestar6: 256 GB (3200 MT/s) DDR4
        # total_bytes_limit = 200_000_000_000
        total_bytes_limit = 200_000_000_000_000
    else:
        total_bytes_limit = 8_000_000_000
    # total_bytes_limit = (6_000_000_000, 200_000_000_000_000)['.tacc.utexas.edu' in platform.node()]
    arr = ts.open({
        'driver': 'zarr',
        'kvstore': { 'driver': 'file', 'path': zarr_path },
        'context': { 'cache_pool': { 'total_bytes_limit': total_bytes_limit} },
        'recheck_cached_data': 'open',
    }, dtype=ts.uint32,)
    slice = np.array(arr[layer,:, :])
    # return arr[layer, :, :]
    return slice


def loadTiffsMp(directory:str):
    '''
    :param directory: Directory containing TIF images.
    :cur_method directory: str
    :return: image_arrays
    :rtype: list[numpy.ndarray]
    '''
    tifs = glob(os.path.join(directory, '*.tif'))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    pool = mp.Pool(processes=cpus)
    start = time.time()
    image_arrays = pool.map(imageio_read_image, tifs)
    dt = time.time() - start
    logger.critical('Writing the Multipage Tiff Took %g Seconds' % dt)

    return image_arrays


# def tiffs2MultiTiff(directory:str, out:str, n_frames:int, width:int, height:int):
def tiffs2MultiTiff(directory:str, out:str):
    # tifs = list(pathlib.Path(directory).glob('*.tif'))
    image_arrays = loadTiffsMp(directory=directory) # image_arrays is a list of numpy arrays
    with tifffile.TiffWriter(out, bigtiff=True) as file:
        file.write(image_arrays)
    # write_multipage(tifs, out)
    # imageio.mimwrite(out, tifs)
    # a = np.ones((n_frames, width, height), dtype=np.uint8)
    # imlist = []
    # for m in a:
    #     imlist.append(Image.fromarray(m))
    # imlist[0].save("test.tif", compression="tiff_deflate", save_all=True, append_images=imlist[1:])


def remove_zarr(path) -> None:
    if os.path.isdir(path):
        logger.info('Removing Extant Zarr Located at %s' % path)
        try:
            with time_limit(20):
                shutil.rmtree(path, ignore_errors=True)
        except TimeoutError as e:
            logger.warning("Timed out!")
        logger.info('Done Removing Zarr')


def preallocate_zarr(name, group, dimx, dimy, dimz, dtype, overwrite):
    '''zarr.blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']'''
    cname, clevel, chunkshape = cfg.data.get_user_zarr_settings()
    src = os.path.abspath(cfg.data.dest())
    path_zarr = os.path.join(src, name)
    path_out = os.path.join(path_zarr, group)
    path_base = os.path.basename(src)
    path_relative = os.path.join(path_base, name)
    logger.critical(f'Preallocating Zarr Array (caller: {inspect.stack()[1].function})...'
                    f' dimx: {dimx}, dimy: {dimy}, dimz: {dimz}')

    cfg.main_window.hud(f'Preallocating {path_base}/{group} Zarr...')
    if os.path.exists(path_out) and (overwrite == False):
        logger.warning('Overwrite is False - Returning')
        return
    shape = (dimz, dimy, dimx)  # Todo check this, inverting x & y

    output_text = f'\n  Zarr root : {path_relative}' \
                  f'\n      group :   └ {group}({name}) {dtype} {cname}/{clevel}' \
                  f'\n      shape : {str(shape)} ' \
                  f'\n      chunk : {chunkshape}'

    try:
        if overwrite and os.path.exists(path_out):
            remove_zarr(path_out)
        # synchronizer = zarr.ThreadSynchronizer()
        # arr = zarr.group(store=path_zarr, synchronizer=synchronizer) # overwrite cannot be set to True here, will overwrite entire Zarr
        arr = zarr.group(store=path_zarr)
        # compressor = Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None
        if cname in ('zstd', 'zlib', 'gzip'):
            compressor = Blosc(cname=cname, clevel=clevel)
        # elif cname == 'zstd':
        #     zarr.storage.default_compressor = Zstd(level=1)
            # compressor = Zstd(level=clevel)
        else:
            compressor = None

        # if cname == 'zstd':
        #     arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, overwrite=overwrite)
        # else:
        # arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite, synchronizer=synchronizer)
        # arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite)
        arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype='|u1', compressor=compressor, overwrite=overwrite)
        '''dtype definitely sets the dtype, otherwise goes to float64 on Lonestar6, at least for use with tensorstore'''
        # write_metadata_zarr_multiscale() # thon3 al   write single multiscale zarr for all aligned s
    except:
        print_exception()
        cfg.main_window.warn('Zarr Preallocation Encountered A Problem')
    else:
        cfg.main_window.hud.done()
        logger.info(output_text)


def write_metadata_zarr_multiscale(path):
    root = zarr.group(store=path)
    datasets = []
    for scale in get_scales_with_generated_alignments(cfg.data.scales()):
        scale_factor = get_scale_val(scale)
        name = 's' + str(scale_factor)
        metadata = {
            "path": name,
            "coordinateTransformations": [{
                "cur_method": "s",
                "s": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
        }
        datasets.append(metadata)
    axes = [
        {"name": "z", "cur_method": "space", "unit": "nanometer"},
        {"name": "y", "cur_method": "space", "unit": "nanometer"},
        {"name": "x", "cur_method": "space", "unit": "nanometer"}
    ]
    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
            "version": "0.4",
            "name": "my_data",
            "axes": axes,
            "datasets": datasets,
            "cur_method": "gaussian",
        }
    ]


def write_metadata_zarr_aligned(name='img_aligned.zarr'):
    zarr_path = os.path.join(cfg.data.dest(), name)
    root = zarr.group(store=zarr_path)
    datasets = []
    # scale_factor = scale_val(cfg.datamodel.s())
    scale_factor = cfg.data.scale_val()
    name = 's' + str(scale_factor)
    metadata = {
        "path": name,
        "coordinateTransformations": [{
            "cur_method": "s",
            "s": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
    }
    datasets.append(metadata)

    axes = [
        {"name": "z", "cur_method": "space", "unit": "nanometer"},
        {"name": "y", "cur_method": "space", "unit": "nanometer"},
        {"name": "x", "cur_method": "space", "unit": "nanometer"}
    ]

    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
            "version": "0.4",
            "name": "my_data",
            "axes": axes,
            "datasets": datasets,
            "cur_method": "gaussian",
        }
    ]

# def generate_zarr_scales_da():
#     logger.info('generate_zarr_scales_da:')
#     dest = cfg.datamodel.dest()
#     logger.info('scales() = %s' % str(cfg.datamodel.scales()))
#
#     for s in cfg.datamodel.scales():
#         logger.info('Working On %s' % s)
#         tif_files = sorted(glob(os.path.join(dest, s, 'img_src', '*.tif')))
#         # zarrurl = os.path.join(dest, s + '.zarr')
#         zarrurl = os.path.join(dest, 'img_src.zarr', 's' + str(get_scale_val(s)))
#         tiffs2zarr(tif_files=tif_files, zarrurl=zarrurl, chunkshape=(1, 512, 512))
#         z = zarr.open(zarrurl)
#         z.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
#         # z.attrs['offset'] = ["0", "0", "0"]
#
#     # zarr_path = os.path.join(dest, 'img_src.zarr')
#     # write_metadata_zarr_multiscale(path=zarr_path)
#     write_metadata_zarr_aligned(name='img_src.zarr')
#
#     # scale_factor = cfg.datamodel.scale_val()
#
#     # z.attrs['_ARRAY_DIMENSIONS'] = [ "z", "y", "x" ]
#     # z.attrs['offset'] = [ "0", "0", "0" ]
#     # z.attrs['resolution'] = [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]
#
#     # tiffs2zarr(tif_files=tif_files, zarrurl=zarrurl, chunkshape=(1, 512, 512),synchronizer=zarr.ThreadSynchronizer())
#
#     logger.info('Exiting generate_zarr_scales_da')



    # def tiffs2zarr(tif_files, zarrurl, chunkshape, overwrite=True, **kwargs):
    #     '''Convert Tiffs to Zarr with implicit dask array
    #     Ref: https://forum.image.sc/t/store-many-tiffs-into-equal-sized-tiff-stacks-for-hdf5-zarr-chunks-using-ome-tiff-format/61055
    #     '''
    #     logger.info('Converting Tiff To Zarr...')
    #     logger.info(str(tif_files))
    #
    #     def imread(filename):
    #         with open(filename, 'rb') as fh:
    #             datamodel = fh.read()
    #         return imagecodecs.tiff_decode(datamodel) # return first image in TIFF file as numpy array
    #     try:
    #         with tifffile.FileSequence(imread, tif_files) as tifs:
    #             with tifs.aszarr() as store:
    #                 array = da.from_zarr(store)
    #                 #array.visualize(filename='_dask_visualize.png') # print dask task graph to file
    #                 array.rechunk(chunkshape).to_zarr(zarrurl, overwrite=True, **kwargs)
    #                 # NOTE **kwargs is passed to Passed to the zarr.creation.create() function, e.g., compression options.
    #                 # https://zarr.readthedocs.io/en/latest/api/creation.html#zarr.creation.create
    #     except:
    #         print_exception()


    if __name__ == '__main__':
        # parser = argparse.ArgumentParser()
        # parser.add_argument("img", cur_method=str, help="Input image")
        # parser.add_argument("dir_out", cur_method=str, help="Output directory")
        # parser.add_argument("cname", cur_method=str, help="Compression cur_method name")
        # parser.add_argument("clevel", cur_method=int, help="Compression level (0-9)")
        # args = parser.parse_args()

        of = 'out.zarr'
        shutil.rmtree(of)

        chunk_shape_tuple = tuple([1,512,512])
        files_1024 = sorted(list(Path('test_data').glob(r'*1024.tif')))
        files_2048 = sorted(list(Path('test_data').glob(r'*2048.tif')))
        files_4096 = sorted(list(Path('test_data').glob(r'*4096.tif')))
        # print(filenames)
        # print('tiffs2zarr is scaling size 1024...')
        # tiffs2zarr(files_1024, os.path.join(of, 'img_aligned_zarr', 's2'), chunk_shape_tuple, compression='zstd',
        #            overwrite=True)
        # print('tiffs2zarr is scaling size 2048...')
        # tiffs2zarr(files_2048, os.path.join(of, 'img_aligned_zarr', 's1'), chunk_shape_tuple, compression='zstd',
        #            overwrite=True)
        # print('tiffs2zarr is scaling size 4096...')
        # tiffs2zarr(files_4096, os.path.join(of, 'img_aligned_zarr', 's0'), chunk_shape_tuple, compression='zstd',
        #            overwrite=True)

        print('writing .zarray...')
        zarray = {}
        zarray['chunks'] = [64, 64, 64]
        zarray['compressor'] = {}
        zarray['compressor']['id'] = 'zstd'
        zarray['compressor']['level'] = 1
        zarray['dtype'] = '|u1'
        zarray['fill_value'] = 0
        zarray['filters'] = None
        zarray['order'] = 'C'
        zarray['zarr_format'] = 2
        with open(os.path.join(of, 'img_aligned_zarr', 's0', '.zarray'), "w") as f:
            zarray['shape'] = [3, 4096, 4096]
            json.dump(zarray, f)

        with open(os.path.join(of, 'img_aligned_zarr', 's1', '.zarray'), "w") as f:
            zarray['shape'] = [3, 2048, 2048]
            json.dump(zarray, f)

        with open(os.path.join(of, 'img_aligned_zarr', 's2', '.zarray'), "w") as f:
            zarray['shape'] = [3, 1024, 1024]
            json.dump(zarray, f)
        print('writing .zattrs...')
        zattrs = {}
        zattrs['offset'] = [0, 0, 0]
        zattrs['resolution'] = [50, 4, 4]
        with open(os.path.join(of, 'img_aligned_zarr', 's0', '.zattrs'), "w") as f:
            json.dump(zattrs, f)
        with open(os.path.join(of, 'img_aligned_zarr', 's1', '.zattrs'), "w") as f:
            json.dump(zattrs, f)
        with open(os.path.join(of, 'img_aligned_zarr', 's2', '.zattrs'), "w") as f:
            json.dump(zattrs, f)

        sys.stdout.close()
        sys.stderr.close()



