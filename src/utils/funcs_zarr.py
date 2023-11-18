#!/usr/bin/env python3

import json
import logging
import os
import platform
import shutil
import sys
from pathlib import Path

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


def get_zarr_array_layer_view(dm, zarr_path:str, l=None):
    if l == None: l = dm.zpos
    arr = ts.open({
        'driver': 'zarr',
        'kvstore': {
            'driver': 'file',
            'file_path': zarr_path,
        },
        'file_path': 'temp.zarr',
        'metadata': {
            'dtype': '<f4',
            'shape': list(dm.resolution()),
            'chunks': list(dm.chunkshape()),
            'order': 'C',
        },
    }, create=True).result()
    # arr[1] = 42  # Overwrites, just like numpy/zarr library
    view = arr[l, :, :]  # Returns a lazy view, no I/O performed
    np.array(view)  # Reads from the view
    # Returns JSON spec that can be passed to `ts.open` to reopen the view.
    view.spec().to_json()
    return view


def get_tensor_from_tiff(dm, dir=None, s=None, l=None):
    if s == None: s = dm.level
    if l == None: l = dm.zpos
    fn = os.path.basename(dm.base_image_name(s=s, l=l))
    path = os.path.join(dm.dest(), s, 'img_src', fn)
    logger.info('Path: %s' % path)
    arr = ts.open({
        'driver': 'tiff',
        'kvstore': {
            'driver': 'file',
            'file_path': path,
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


# def loadTiffsMp(directory:str):
#     '''
#     :param directory: Directory containing TIF images.
#     :cur_method directory: str
#     :return: image_arrays
#     :rtype: list[numpy.ndarray]
#     '''
#     tifs = glob(os.file_path.join(directory, '*.tif'))
#     cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2,1)
#     pool = mp.Pool(processes=cpus)
#     start = time.time()
#     image_arrays = pool.map(imageio_read_image, tifs)
#     dt = time.time() - start
#     logger.critical('Writing the Multipage Tiff Took %g Seconds' % dt)
#
#     return image_arrays




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


def write_metadata_zarr_aligned(name='img_aligned.zarr'):
    zarr_path = os.path.join(cfg.mw.dm.dest(), name)
    root = zarr.group(store=zarr_path)
    datasets = []
    scale_factor = cfg.mw.dm.lvl()
    name = 'level' + str(scale_factor)
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

# def generate_zarr_scales_da(dm):
#     logger.info('generate_zarr_scales_da:')
#     dest = dm.dest()
#     logger.info('scales = %level' % str(dm.scales))
#
#     for level in dm.scales:
#         logger.info('Working On %level' % level)
#         tif_files = sorted(glob(os.file_path.join(dest, level, 'img_src', '*.tif')))
#         # zarrurl = os.file_path.join(dest, level + '.zarr')
#         zarrurl = os.file_path.join(dest, 'img_src.zarr', 'level' + str(get_scale_val(level)))
#         tiffs2zarr(tif_files=tif_files, zarrurl=zarrurl, chunkshape=(1, 512, 512))
#         z = zarr.open(zarrurl)
#         z.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
#         # z.attrs['offset'] = ["0", "0", "0"]
#
#     # zarr_path = os.file_path.join(dest, 'img_src.zarr')
#     # write_metadata_zarr_multiscale(file_path=zarr_path)
#     write_metadata_zarr_aligned(name='img_src.zarr')
#
#     # scale_factor = dm.lvl()
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
    #     def imread(file_path):
    #         with open(file_path, 'rb') as fh:
    #             datamodel = fh.read()
    #         return imagecodecs.tiff_decode(datamodel) # return first image in TIFF file as numpy array
    #     try:
    #         with tifffile.FileSequence(imread, tif_files) as tifs:
    #             with tifs.aszarr() as store:
    #                 array = da.from_zarr(store)
    #                 #array.visualize(file_path='_dask_visualize.png') # print dask task graph to file
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
        # tiffs2zarr(files_1024, os.file_path.join(of, 'img_aligned_zarr', 's2'), chunk_shape_tuple, compression='zstd',
        #            overwrite=True)
        # print('tiffs2zarr is scaling size 2048...')
        # tiffs2zarr(files_2048, os.file_path.join(of, 'img_aligned_zarr', 's1'), chunk_shape_tuple, compression='zstd',
        #            overwrite=True)
        # print('tiffs2zarr is scaling size 4096...')
        # tiffs2zarr(files_4096, os.file_path.join(of, 'img_aligned_zarr', 's0'), chunk_shape_tuple, compression='zstd',
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



