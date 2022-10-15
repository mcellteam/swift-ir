#!/usr/bin/env python3

import os
import sys
import time
import glob
import json
import psutil
import shutil
import logging
import inspect
import platform
from glob import glob
from pathlib import Path
import multiprocessing as mp
from numcodecs import Blosc
import imageio.v3 as iio
# from PIL import Image
import zarr
import tifffile
import imagecodecs
# import dask.array as da
import src.config as cfg
from src.helpers import get_scale_val, time_limit
from src.image_funcs import BoundingRect, imageio_read_image
from src.helpers import get_img_filenames, print_exception

__all__ = ['preallocate_zarr', 'tiffs2MultiTiff', 'write_zarr_multiscale_metadata']

logger = logging.getLogger(__name__)


def loadTiffsMp(directory:str):
    '''

    :param directory: Directory containing TIF images.
    :type directory: str
    :return: image_arrays
    :rtype: list[numpy.ndarray]
    '''
    tifs = glob.glob(os.path.join(directory, '*.tif'))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    pool = mp.Pool(processes=cpus)
    start = time.time()
    image_arrays = pool.map(imageio_read_image, tifs)
    dt = time.time() - start
    logger.critical('Writing the Multipage Tiff Took %g Seconds' % dt)

    return image_arrays


def get_zarr_tensor_from_path(zarr_path):
    '''
    Returns an asynchronous TensorStore future object which is a view
    into the Zarr image on disk. All TensorStore indexing operations
    produce lazy views.

    Ref: https://stackoverflow.com/questions/64924224/getting-a-view-of-a-zarr-array-slice

    :param zarr_path:
    :type zarr_path:
    :return: A view into the dataset.
    :rtype: tensorstore.Future
    '''
    if cfg.USE_TENSORSTORE:
        import tensorstore as ts

    system = platform.system()
    node = platform.node()

    if '.tacc.utexas.edu' in node:
        # Lonestar6: 256 GB (3200 MT/s) DDR4
        total_bytes_limit = 200_000_000_000
    else:
        total_bytes_limit = 6_000_000_000

    arr = ts.open({
        'driver': 'zarr',
        'kvstore': { 'driver': 'file', 'path': zarr_path },
        'context': { 'cache_pool': { 'total_bytes_limit': total_bytes_limit} },
        'recheck_cached_data': 'open',
    })

    return arr


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
    #
    # imlist[0].save("test.tif", compression="tiff_deflate", save_all=True, append_images=imlist[1:])

# def remove_zarr() -> None:
def remove_zarr(path) -> None:
    # path = os.path.join(cfg.data.dest(), 'img_aligned.zarr')
    if os.path.isdir(path):
        logger.critical('Removing Zarr...')
        try:
            with time_limit(15):
                logger.info('Removing %s...' % path)
                shutil.rmtree(path, ignore_errors=True)
        except TimeoutError as e:
            logger.warning("Timed out!")
        logger.info('Finished Removing Zarr Files')

def init_zarr() -> None:
    logger.critical('Initializing Zarr...')
    path = os.path.join(cfg.data.dest(), 'img_aligned.zarr')
    store = zarr.DirectoryStore(path, dimension_separator='/')  # Create Zarr DirectoryStore
    root = zarr.group(store=store, overwrite=True)  # Create Root Group (?)
    # root = zarr.group(store=store, overwrite=True, synchronizer=zarr.ThreadSynchronizer())  # Create Root Group (?)

def preallocate_zarr(use_scale=None, bounding_rect=True, name='out.zarr', z_stride=16, chunks=(1, 512, 512), is_alignment=True):

    cfg.main_window.hud.post('Preallocating Zarr Array...')

    cur_scale = cfg.data.scale()
    cur_scale_val = get_scale_val(cfg.data.scale())
    src = os.path.abspath(cfg.data.dest())
    n_imgs = cfg.data.n_imgs()
    # n_scales = cfg.data.n_scales()
    aligned_scales_lst = cfg.data.aligned_list()

    zarr_path = os.path.join(cfg.data.dest(), name)
    # if (use_scale == cfg.data.coarsest_scale_key()) or caller == 'generate_zarr_flat':
    #     # remove_zarr()
    #     init_zarr()

    out_path = os.path.join(src, name, 's' + str(cur_scale_val))
    if cfg.data.scale() != 'scale_1':
        if os.path.exists(out_path):
            remove_zarr(out_path)

    # name = 's' + str(scale_val(use_scale))
    # zarr_name = os.path.join(zarr_path,name)
    # root = zarr.group(store=zarr_path, synchronizer=synchronizer)  # Create Root Group
    root = zarr.group(store=zarr_path)  # Create Root Group
    # root = zarr.group(store=zarr_name, overwrite=True)  # Create Root Group

    # opt_cname = cfg.main_window.cname_combobox.currentText()
    # opt_clevel = int(cfg.main_window.clevel_input.text())

    if use_scale is None:
        zarr_these_scales = aligned_scales_lst
    else:
        zarr_these_scales = [use_scale]

    datasets = []
    for scale in zarr_these_scales:
        logger.info('Preallocating Zarr for Scale: %s' % str(scale))
        logger.info('bounding_rect = %s' % str(bounding_rect))
        if bounding_rect is True:
            rect = BoundingRect(cfg.data['data']['scales'][scale]['alignment_stack'])
            dimx, dimy = rect[2], rect[3]
            logger.info('dim_x=%d, dim_y=%d' % (dimx, dimy))

        else:
            imgs = sorted(get_img_filenames(os.path.join(src, scale, 'img_src')))
            # dimx, dimy = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
            if is_alignment:
                dimx, dimy = tifffile.imread(os.path.join(src, scale, 'img_aligned', imgs[0])).size
            else:
                from src.image_funcs import ImageSize
                path = os.path.join(src, scale, 'img_src', imgs[0])
                logger.info('path = %s' % path)
                dimx, dimy = ImageSize(path)



        scale_val = get_scale_val(scale)
        name = 's' + str(scale_val)

        shape = (n_imgs, dimy, dimx)
        # chunks = (z_stride, 64, 64)
        chunks = (cfg.CHUNK_Z, cfg.CHUNK_Y, cfg.CHUNK_X)
        dtype = 'uint8'
        compressor = Blosc(cname=cfg.CNAME, clevel=cfg.CLEVEL) if cfg.CNAME in ('zstd', 'zlib', 'gzip') else None
        # compressor = Blosc(cname='zstd', clevel=5)

        logger.info('Zarr Array will have shape: %s' % str(shape))
        array = root.zeros(name=name, shape=shape, chunks=chunks, dtype=dtype, compressor=compressor, overwrite=True)

        # datasets.append(
        #     {
        #         "path": name,
        #         "coordinateTransformations": [{
        #             "type": "scale",
        #             "scale": [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]}]
        #     }
        # )

        # metadata = {
        #     "path": name,
        #     "coordinateTransformations": [{
        #         "type": "scale",
        #         "scale": [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]}]
        # }
        # root.attrs["multiscales"][0]["datasets"].append(metadata)


    # write_zarr_multiscale_metadata() # write single multiscale zarr for all aligned scale

    if cfg.data.scale() == 'scale_1':
        zarr_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr')
        write_zarr_multiscale_metadata(path=zarr_path)
    else:
        write_zarr_metadata_cur_scale()  # write multiscale zarr for current scale
    cfg.main_window.hud.done()

    # time.sleep(500)

def write_zarr_multiscale_metadata(path):

    root = zarr.group(store=path)
    datasets = []
    for scale in cfg.data.aligned_list():
        scale_factor = get_scale_val(scale)
        name = 's' + str(scale_factor)
        metadata = {
            "path": name,
            "coordinateTransformations": [{
                "type": "scale",
                "scale": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
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

def write_zarr_metadata_cur_scale(name='img_aligned.zarr'):
    zarr_path = os.path.join(cfg.data.dest(), name)
    root = zarr.group(store=zarr_path)
    datasets = []
    # scale_factor = scale_val(cfg.data.scale())
    scale_factor = cfg.data.scale_val()
    name = 's' + str(scale_factor)
    metadata = {
        "path": name,
        "coordinateTransformations": [{
            "type": "scale",
            "scale": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
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

# def generate_zarr_scales_da():
#     logger.info('generate_zarr_scales_da:')
#     dest = cfg.data.dest()
#     logger.info('scales() = %s' % str(cfg.data.scales()))
#
#     for s in cfg.data.scales():
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
#     # write_zarr_multiscale_metadata(path=zarr_path)
#     write_zarr_metadata_cur_scale(name='img_src.zarr')
#
#     # scale_factor = cfg.data.scale_val()
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
    #             data = fh.read()
    #         return imagecodecs.tiff_decode(data) # return first image in TIFF file as numpy array
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
        # parser.add_argument("img", type=str, help="Input image")
        # parser.add_argument("dir_out", type=str, help="Output directory")
        # parser.add_argument("cname", type=str, help="Compression type name")
        # parser.add_argument("clevel", type=int, help="Compression level (0-9)")
        # args = parser.parse_args()
        #
        #
        #
        # # os.makedirs(os.path.dirname('out.zarr'), exist_ok=True)
        # # os.makedirs(os.path.dirname('img_aligned_zarr'), exist_ok=True)
        # Path(args.dir_out).mkdir(parents=True, exist_ok=True)

        of = 'out.zarr'
        shutil.rmtree(of)

        chunk_shape_tuple = tuple([64, 64, 64])
        files_1024 = sorted(list(Path('test_data').glob(r'*1024.tif')))
        files_2048 = sorted(list(Path('test_data').glob(r'*2048.tif')))
        files_4096 = sorted(list(Path('test_data').glob(r'*4096.tif')))
        # print(filenames)
        print('tiffs2zarr is scaling size 1024...')
        tiffs2zarr(files_1024, os.path.join(of, 'img_aligned_zarr', 's2'), chunk_shape_tuple, compression='zstd',
                   overwrite=True)
        print('tiffs2zarr is scaling size 2048...')
        tiffs2zarr(files_2048, os.path.join(of, 'img_aligned_zarr', 's1'), chunk_shape_tuple, compression='zstd',
                   overwrite=True)
        print('tiffs2zarr is scaling size 4096...')
        tiffs2zarr(files_4096, os.path.join(of, 'img_aligned_zarr', 's0'), chunk_shape_tuple, compression='zstd',
                   overwrite=True)

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



