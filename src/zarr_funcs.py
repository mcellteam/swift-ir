#!/usr/bin/env python3

import os, sys, time, json, logging, inspect, platform, shutil, psutil
from glob import glob
from pathlib import Path
import multiprocessing as mp
from numcodecs import Blosc
import imageio.v3 as iio
# from PIL import Image
import zarr
import tifffile
import tensorstore as ts
# import imagecodecs
# import dask.array as da
import src.config as cfg
from src.helpers import get_scale_val, time_limit, get_img_filenames, print_exception
from src.image_funcs import ImageSize, ComputeBoundingRect, imageio_read_image

__all__ = ['preallocate_zarr_src', 'preallocate_zarr_aligned', 'tiffs2MultiTiff', 'write_metadata_zarr_multiscale']

logger = logging.getLogger(__name__)

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
    node = platform.node()
    if '.tacc.utexas.edu' in node:
        # Lonestar6: 256 GB (3200 MT/s) DDR4
        # total_bytes_limit = 200_000_000_000
        total_bytes_limit = 200_000_000_000_000
    else:
        total_bytes_limit = 6_000_000_000
    # total_bytes_limit = (6_000_000_000, 200_000_000_000_000)['.tacc.utexas.edu' in platform.node()]
    arr = ts.open({
        'driver': 'zarr',
        'kvstore': { 'driver': 'file', 'path': zarr_path },
        'context': { 'cache_pool': { 'total_bytes_limit': total_bytes_limit} },
        'recheck_cached_data': 'open',
    })
    return arr

def loadTiffsMp(directory:str):
    '''

    :param directory: Directory containing TIF images.
    :type directory: str
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
    logger.critical('Removing Preexisting Zarrs...')
    # path = os.path.join(cfg.data.dest(), 'img_aligned.zarr')
    if os.path.isdir(path):
        logger.critical('Removing Zarr Located at %s...' % path)
        try:
            with time_limit(20):
                logger.info('Removing %s...' % path)
                shutil.rmtree(path, ignore_errors=True)
        except TimeoutError as e:
            logger.warning("Timed out!")
        logger.info('Finished Removing Zarr Files')


def preallocate_zarr_src():
    cfg.main_window.hud.post('Preallocating Scaled Zarr Array...')
    zarr_path = os.path.join(cfg.data.dest(), 'img_src.zarr')
    logger.info('Zarr Root Location: %s' % zarr_path)
    if os.path.exists(zarr_path):
        remove_zarr(zarr_path)

    root = zarr.group(store=zarr_path, overwrite=True)
    # root = zarr.group(store=zarr_path, synchronizer=synchronizer)

    cname = cfg.data.cname()
    clevel = cfg.data.clevel()
    chunkshape = cfg.data.chunkshape()

    for scale in cfg.data.scales():
        dimx, dimy = ImageSize(cfg.data.path_base(s=scale))
        name = 's' + str(get_scale_val(scale))
        shape = (cfg.data.n_imgs(), dimy, dimx)
        logger.info('Preallocating Scale Zarr Array for %s, shape: %s' % (scale, str(shape)))
        compressor = Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None
        # root.zeros(name=name, shape=shape, chunks=chunkshape, dtype='uint8', compressor=compressor, overwrite=True)
        root.zeros(name=name, shape=shape, chunks=chunkshape, compressor=compressor, overwrite=True)

def preallocate_zarr_aligned(scales=None):
    cfg.main_window.hud.post('Preallocating Aligned Zarr Array...')
    if scales == None: scales = [cfg.data.scale()]
    src = os.path.abspath(cfg.data.dest())
    zarr_path = os.path.join(src, 'img_aligned.zarr')
    logger.info('Zarring these scales: %s' % str(scales))
    logger.info('Zarr Root Location: %s' % zarr_path)

    root = zarr.group(store=zarr_path)
    # root = zarr.group(store=zarr_path, synchronizer=synchronizer)
    # root = zarr.group(store=zarr_name, overwrite=True)

    cname = cfg.data.cname()
    clevel = cfg.data.clevel()
    chunkshape = cfg.data.chunkshape()

    for scale in scales:
        out_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(get_scale_val(scale)))
        if os.path.exists(out_path):
            remove_zarr(out_path)

        rect = cfg.data.bounding_rect(s=scale)
        shape = (cfg.data.n_imgs(), rect[2], rect[3])
        logger.info('Preallocating Aligned Zarr Array for %s, shape: %s' % (scale, str(shape)))

        name = 's' + str(get_scale_val(scale))
        compressor = Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None
        root.zeros(name=name, shape=shape, chunks=chunkshape, dtype='uint8', compressor=compressor, overwrite=True)
        # root.zeros(name=name, shape=shape, chunks=chunkshape, compressor=compressor, overwrite=True)
        '''dtype definitely sets the dtype, otherwise goes to float64 on Lonestar6, at least for use with tensorstore'''

    # write_metadata_zarr_multiscale() # write single multiscale zarr for all aligned s

    if cfg.data.scale() == 'scale_1':
        write_metadata_zarr_multiscale(path=os.path.join(cfg.data.dest(), 'img_aligned.zarr'))


def write_metadata_zarr_multiscale(path):
    root = zarr.group(store=path)
    datasets = []
    for scale in cfg.data.aligned_list():
        scale_factor = get_scale_val(scale)
        name = 's' + str(scale_factor)
        metadata = {
            "path": name,
            "coordinateTransformations": [{
                "type": "s",
                "s": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
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
    zarr_path = os.path.join(cfg.data.dest(), name)
    root = zarr.group(store=zarr_path)
    datasets = []
    # scale_factor = scale_val(cfg.data.s())
    scale_factor = cfg.data.scale_val()
    name = 's' + str(scale_factor)
    metadata = {
        "path": name,
        "coordinateTransformations": [{
            "type": "s",
            "s": [float(50.0), 2 * float(scale_factor), 2 * float(scale_factor)]}]
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
#     # write_metadata_zarr_multiscale(path=zarr_path)
#     write_metadata_zarr_aligned(name='img_src.zarr')
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



