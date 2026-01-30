#!/usr/bin/env python3

import logging
import os
import platform
import shutil

import numcodecs
import numpy as np
import tensorstore as ts
import zarr
from numcodecs import Blosc

numcodecs.blosc.use_threads = False
import src.config as cfg
from src.utils.helpers import get_scale_val, print_exception

'''
TensorStore has already been used to solve key engineering challenges in scientific computing (e.g., management and 
processing of large datasets in neuroscience, such as peta-level 3d electron microscopy datamodel and “4d” videos of 
neuronal activity). TensorStore has also been used in the creation of large-level machine learning models such as 
PaLM by addressing the problem of managing previewmodel parameters (checkpoints) during distributed training.
https://www.reddit.com/r/worldTechnology/comments/xuw7kk/tensorstore_for_highperformance_scalable_array/
'''

__all__ = ['preallocate_zarr', 'write_metadata_zarr_multiscale', 'write_zarr_multiscale_metadata']

logger = logging.getLogger(__name__)


def get_zarr_tensor(path):
# async def get_zarr_tensor(file_path):
    '''
    Returns an asynchronous TensorStore future object which is a view
    into the Zarr on disk. **All TensorStore indexing operations
    produce lazy views**

    https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

    :param path: Fully qualified Zarr file_path
    :return: A TensorStore future object
    :rtype: tensorstore.Future
    '''
    logger.info(f'Requested: {path}')
    total_bytes_limit = 256_000_000_000 # Lonestar6: 256 GB (3200 MT/level) DDR4
    future = ts.open({
        'dtype': 'uint8',
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            'file_path': path
        },
        'context': {
            'cache_pool': {'total_bytes_limit': total_bytes_limit},
            'file_io_concurrency': {'limit': 1024}, #1027+
            # 'data_copy_concurrency': {'limit': 512},
        },
        # 'recheck_cached_data': 'open',
        'recheck_cached_data': True, # default=True
    })
    return future




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
        # Lonestar6: 256 GB (3200 MT/level) DDR4
        # total_bytes_limit = 200_000_000_000
        total_bytes_limit = 200_000_000_000_000
    else:
        total_bytes_limit = 8_000_000_000
    # total_bytes_limit = (6_000_000_000, 200_000_000_000_000)['.tacc.utexas.edu' in platform.node()]
    arr = ts.open({
        'driver': 'zarr',
        'kvstore': { 'driver': 'file', 'file_path': zarr_path },
        'context': { 'cache_pool': { 'total_bytes_limit': total_bytes_limit} },
        'recheck_cached_data': 'open',
    }, dtype=ts.uint32,)
    slice = np.array(arr[layer,:, :])
    # return arr[layer, :, :]
    return slice






def remove_zarr(path) -> None:
    if os.path.isdir(path):
        logger.info('Removing extant Zarr at %s...' % path)
        # try:
        #     with time_limit(20):
        #         shutil.rmtree(file_path, ignore_errors=True)
        # except TimeoutError as e:
        #     logger.warning("Timed out!")
        try:
            shutil.rmtree(path, ignore_errors=True)
        except:
            print_exception()
        finally:
            logger.info('Done')


def preallocate_zarr(dm, name, group, shape, dtype, overwrite, gui=True, attr=None):
    '''zarr.blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']'''
    logger.info("\n\n--> preallocate -->\n")
    cname, clevel, chunkshape = dm.get_images_zarr_settings()
    src = os.path.abspath(dm.data_dir_path)
    path_zarr = os.path.join(src, name)
    path_out = os.path.join(path_zarr, group)
    logger.info(f'allocating {name}/{group}...')

    if gui:
        cfg.main_window.hud(f'Preallocating {os.path.basename(src)}/{group} Zarr...')
    if os.path.exists(path_out) and (overwrite == False):
        logger.warning('Overwrite is False - Returning')
        return
    output_text = f'\n  Zarr root : {os.path.join(os.path.basename(src), name)}' \
                  f'\n      group :   └ {group}({name}) {dtype} {cname}/{clevel}' \
                  f'\n      shape : {str(shape)} ' \
                  f'\n      chunk : {chunkshape}'

    try:
        if overwrite and os.path.exists(path_out):
            logger.info(f"Removing '{path_out}'")
            shutil.rmtree(path_out, ignore_errors=True)
        # synchronizer = zarr.ThreadSynchronizer()
        # arr = zarr.group(store=path_zarr_transformed, synchronizer=synchronizer) # overwrite cannot be set to True here, will overwrite entire Zarr
        arr = zarr.group(store=path_zarr)
        compressor = Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None

        logger.info(f"\n"
                    f"  group      : {group}\n"
                    f"  shape      : {shape}\n"
                    f"  chunkshape : {chunkshape}\n"
                    f"  dtype      : {dtype}\n"
                    f"  compressor : {compressor}\n"
                    f"  overwrite  : {overwrite}")

        # arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite, synchronizer=synchronizer)
        arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite)
        # write_metadata_zarr_multiscale()
        if attr:
            arr.attrs['attribute'] = attr
    except:
        print_exception()
        logger.warning('Zarr Preallocation Encountered A Problem')
    else:
        # cfg.main_window.hud.done()
        logger.info(output_text)
    logger.info(f"\n\n<-- preallocate <--\n")


def write_metadata_zarr_multiscale(path):
    root = zarr.group(store=path)
    datasets = []
    scales = [1,2,4]
    for scale in scales:
        scale_factor = get_scale_val(scale)
        name = 's' + str(scale_factor)
        metadata = {
            "file_path": name,
            "coordinateTransformations": [{
                "cur_method": "level",
                "level": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
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


def write_zarr_multiscale_metadata(path, scales, resolution):
    root = zarr.group(store=path)
    datasets = []
    for scale in scales:
        scale_factor = get_scale_val(scale)
        name = 'level' + str(scale_factor)
        metadata = {
            "file_path": name,
            "coordinateTransformations": [{
                "type": "level",
                "level": [float(resolution[0]), scale_factor * float(resolution[1]), scale_factor * float(resolution[2])]}]
        }
        datasets.append(metadata)
    axes = [
        {"name": "z", "type": "space", "unit": "nanometer"},
        {"name": "y", "type": "space", "unit": "nanometer"},
        {"name": "x", "type": "space", "unit": "nanometer"}
    ]
    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
            "version": "0.4",
            "name": "my_data",
            "axes": axes,
            "datasets": datasets,
            "type": "gaussian",
        }
    ]






