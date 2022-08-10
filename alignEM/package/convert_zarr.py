#!/usr/bin/env python3
"""
Author: Joel Yancey
Project: SWiFT-IR

Notes:
    * script depends on em_utils.py functions for scale pyramid functionality. keep files in the same directory.
        * daisy
            * written by Funke Lab at Janelia
            * source: https://github.com/funkelab/daisy
            * Daisy docs are inordinately hard to track down, so linked here
                * v0.1
                    * https://daisy-python.readthedocs.io/en/latest/appendix.html
                    * https://readthedocs.org/projects/daisy-python/downloads/pdf/latest/
                * v0.2
                    * https://daisy-docs.readthedocs.io/en/latest/api.html
                    * release notes: https://daisy-docs.readthedocs.io/en/latest/release.html
                        * uses tornado instead of dask
                        * Python’s asyncio capability as the sole backend for Tornado
                        * Python 3.5 and lower NOT supported
    * other dependencies:
        * zarr (https://zarr.readthedocs.io/en/stable/)
        * tifffile (https://pypi.org/project/tifffile/)
        * dask (https://docs.dask.org/en/latest/)
            * dask.diagnostics docs: https://docs.dask.org/en/stable/diagnostics-local.html
            * NOTE: when workers and threads per worker are NOT set -> Dask optimizes thread concurrency automatically
        * numcodecs (https://pypi.org/project/numcodecs/)
    *

EXAMPLE USAGE

MINIMAL
./convert_zarr.py volume_josef

VERBOSE
./convert_zarr.py volume_josef -c '1,5332,5332' -cN 'zstd' -cL 1 -r '50,2,2' -w 8 -t 2

VERY VERBOSE
./convert_zarr.py volume_josef --chunks '1,5332,5332' --cname 'zstd' --clevel 1 --resolution '50,2,2' --workers 8 --threads 2


* look into tradeoffs with rechunking
https://zarr.readthedocs.io/en/latest/tutorial.html#changing-chunk-shapes-rechunking

* transition to Mutable Mapping interface or other Zarr storage type
https://zarr.readthedocs.io/en/stable/api/storage.html

Nested Directory Store
Storage class using directories and files on a standard file system, with special handling for chunk keys so that
chunk files for multidimensional arrays are stored in a nested directory tree.
Safe to write in multiple threads or processes.

tifffile new fsspec implementation
https://github.com/cgohlke/tifffile

"""
import os
import sys
import time
import shutil
import logging
import argparse
import numpy as np
import multiprocessing
from pathlib import Path
from datetime import datetime
from contextlib import redirect_stdout
import zarr

from numcodecs import Blosc, Delta, LZMA, Zstd # blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']

from tiffs2zarr import tiffs2zarr
from scale_pyramid import create_scale_pyramid

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logger.info('convert_zarr.py >>>>')

    # logfile = 'make_zarr.log'
    # logging.basicConfig(filename=logfile, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    # PARSE COMMAND LINE INPUTS
    ap = argparse.ArgumentParser()

    # required arguments
    ap.add_argument('path', type=str, help='Source directory path')

    # optional arguments
    ap.add_argument('-c', '--chunks', default='64,64,64', type=str, help="Chunk shape X,Y,Z (default: '64,64,64')")
    ap.add_argument('-d', '--destination', default='.', type=str, help="Destination dir (default: '.')")
    ap.add_argument('-n', '--dataset_name', default='img_aligned_zarr', type=str, help="Destination dir (default: 'img_aligned_zarr')")
    ap.add_argument('-s', '--scale_ratio', default='1,2,2', type=str, help="Scaling ratio for each axis (default: '1,2,2')")
    ap.add_argument('-nS', '--n_scales', default=4, type=int, help='Number of downscaled image arrays. (default: 4)')
    ap.add_argument('-cN', '--cname', default='zstd', type=str, help="Compressor [zstd,zlib,gzip] (default: 'zstd')")
    ap.add_argument('-cL', '--clevel', default=1, type=int, help='Compression level [0:9] (default: 1)')
    ap.add_argument('-r', '--resolution', default='50,2,2', type=str, help="Resolution of x dim (default: '50,2,2')")
    ap.add_argument('-w', '--workers', default=8, type=int, help='Number of workers (default: 8)')
    ap.add_argument('-t', '--threads', default=2, type=int, help='Number of threads per worker (default: 2)')
    ap.add_argument('-nC', '--no_compression', default=0, type=int, help='Do not compress. (default: 0)')
    ap.add_argument('-o', '--overwrite', default=1, type=int, help='Overwrite target if already exists (default: 1)')
    # ap.add_argument('-m', '--make_zarr', action="store_true", help='Make .zarr from source (source is not modifed)')
    # ap.add_argument('-f', '--force', default=True, type=int, help='Force overwrite if zarr exists (default: True)')
    # COMPRESSORS=blosc,zlib,gzip,lzma,zstd,lz4i / BLOSC_COMPRESSORS=blosclz,lz4,lz4hc,snappy,zlib,zstd
    args = ap.parse_args()
    cname = args.cname
    clevel = args.clevel
    n_scales = args.n_scales
    no_compression = bool(args.no_compression)
    overwrite = bool(args.overwrite)
    workers = args.workers
    destination = args.destination
    ds_name = args.dataset_name
    zarr_path = os.path.join(args.destination, 'project.zarr')
    zarr_ds_path = os.path.join(zarr_path, ds_name)
    src = Path(args.path)
    filenames = sorted(list(Path(src).glob(r'*.tif')))
    n_imgs = len(filenames)
    chunks = [int(i) for i in args.chunks.split(',')]
    chunk_shape_tuple = tuple(chunks)
    resolution = [int(i) for i in args.resolution.split(',')]
    scale_ratio = [int(i) for i in args.scale_ratio.split(',')]
    r = scale_ratio
    scale_ratio = [scale_ratio]
    [scale_ratio.append(r) for x in range(n_scales - 1)]
    timestr = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    component = 'zArray'
    # blosc.set_nthreads(args.threads)
    # store = zarr.NestedDirectoryStore('data/array.zarr')
    # more intuitive scale_ratio for Zarr metadata...
    scales_list = [r]
    next = np.array(r)
    for s in range(1, n_scales):
        next = next * np.array(r)
        scales_list.append(next.tolist())

    # CHECK IF SOURCE MAKES SENSE
    if not src.is_dir():
        logger.warning("Source '%s' is not a directory - Aborting" % str(src))
        logger.warning("<<<< convert_zarr.py")
        sys.exit()

    if src.suffix == '.zarr':
        logger.warning("Source has '.zarr' suffix, cannot export Zarr to Zarr - Aborting")
        logger.warning("<<<< convert_zarr.py")
        sys.exit()

    # SET PYTHON 'multiprocessing' TO USE 'fork'
    logger.info("setting multiprocessing start method to 'fork'...")
    try:
        multiprocessing.set_start_method('fork', force=True)
    except:
        logger.warning('Something went wrong while setting multiprocessing start method')
        pass

    # CHECK IF TARGET DIRECTORY EXISTS; OVERWRITE?
    logger.info('checking if export path already exists...')
    if os.path.isdir(zarr_ds_path):
        if overwrite is False:
            logger.info('EXCEPTION | target already exists & overwrite is disabled - Aborting')
            logger.info("<<<<<<<<<<<<<<<< EXITING convert_zarr.py")
            sys.exit()
        logger.info("target '%s' already exists, overwrite=%s" %  (zarr_ds_path, overwrite))
        logger.info("removing '%s'..." % zarr_ds_path)
        try:
            shutil.rmtree(zarr_ds_path)
        except:
            logger.warning("Unable to remove '%s'" % zarr_ds_path)
            pass


    logger.info('loading file list...')

    if not no_compression:
        config_str = src.as_posix() + "_" + str(n_imgs) + 'imgs_multiscale' + str(n_scales) + \
                     '_chunksize' + str(chunks[0]) + 'x' + str(chunks[1]) + 'x' + str(chunks[2]) + \
                     '_' + cname + '-clevel' + str(clevel)
    if no_compression:
        config_str = src.as_posix() + "_" + str(n_imgs) + 'imgs_multiscale' + str(n_scales) + \
                     '_chunksize' + str(chunks[0]) + 'x' + str(chunks[1]) + 'x' + str(chunks[2]) + \
                     '_uncompressed'
    first_file = str(filenames[0])
    last_file = str(filenames[-1])

    # CONSOLE DUMP

    logger.info('export path (Zarr)       :', zarr_path)
    logger.info('zarr url                 :', zarr_ds_path)
    logger.info('overwrite                :', str(overwrite))
    logger.info('source                   :', src)
    logger.info('src.name                 :', src.name)
    logger.info('# of images found        :', n_imgs)
    logger.info('first image              :', first_file)
    logger.info('last image               :', last_file)
    logger.info('# of scales              :', n_scales)
    logger.info('scales                   :', scales_list)
    logger.info('chunk shape              :', str(chunk_shape_tuple))
    logger.info('compression type         :', cname)
    logger.info('compression level        :', clevel)
    logger.info('compression type         :', cname)
    logger.info('no_compression           :', no_compression)
    try:
        logger.info('compressor               :', str(Blosc(cname=cname, clevel=clevel)))
    except:
        logger.warning("Could not evaluate 'str(Blosc(cname=cname, clevel=clevel))'")

    # CALL 'tiffs2zarr'
    logger.info("converting original scale images to Zarr...")
    t = time.time()
    if no_compression:
        tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compressor=None, overwrite=overwrite) # might pass in 'None'
    else:
        if cname in ('zstd', 'zlib'):
            tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compressor=Blosc(cname=cname, clevel=clevel), overwrite=overwrite)  # NOTE 'compressor='
            # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), compressor=zarr.get_codec({'id': cname, 'level': clevel}))
        else:
            tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compression=cname, overwrite=overwrite)  # NOTE 'compression='
            # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), compression=compressor,overwrite=True)
            # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), cname=cname, clevel=clevel, overwrite=True)

    t_to_zarr = time.time() - t

    # WRITE NEUROGLANCER & OME-NGFF-COMPATIBLE METADATA
    logger.info('setting Neuroglancer & OME-NGFF compatible meta-data...')
    ds = zarr.open(zarr_path + '/' + ds_name, mode='a')
    ds.attrs['n_images'] = n_imgs
    ds.attrs['offset'] = [0, 0, 0]
    ds.attrs['resolution'] = resolution
    ds.attrs['units'] = ['nm', 'nm', 'nm']
    #ds.attrs['scales'] = scale_ratio
    ds.attrs['scale_factors'] = scales_list
    ds.attrs['_ARRAY_DIMENSIONS'] = ['z', 'y', 'x']

    logger.info("--------original scale Zarr info (pre-scaling)--------")
    logger.debug(ds.info)

    # COMPUTE SCALE PYRAMID
    logger.info('Generating scales...')
    t = time.time()
    if no_compression:
        compressor = None
        create_scale_pyramid(zarr_path, ds_name, scale_ratio, chunks, compressor=None)
    else:
        compressor = {'id': cname, 'level': clevel}
        create_scale_pyramid(zarr_path, ds_name, scale_ratio, chunks, compressor)
        # create_scale_pyramid(zarr_path, ds_name, scale_ratio, chunks) # testing ONLY
        # create_scale_pyramid(zarr_path, ds_name, scale_ratio, chunks, compressor=zarr.get_codec({'id': cname, 'level': clevel})) # testing ONLY

    t_gen_scales = time.time() - t
    t_total = t_to_zarr + t_gen_scales

    # CONSOLIDATE META-DATA
    logger.info("consolidating Zarr metadata")
    zarr.consolidate_metadata(zarr_path)

    # COLLECT RUN DATA AND SAVE TO FILE
    f_txt = os.path.join(destination, "make_zarr_dump.txt")
    logger.info("dumping run details to '%s'" % f_txt)
    with open(f_txt, mode='a') as f:
        with redirect_stdout(f):
            logger.info(timestr)
            logger.info("____ RESULTS - MAKE ZARR ____")
            logger.info("source             :", args.path)
            logger.info("output file        :", zarr_path)
            logger.info("first file         :", os.path.basename(first_file))
            logger.info("last file          :", os.path.basename(last_file))
            logger.info("# images found     :", n_imgs)
            logger.info("time make .zarr    :", t_to_zarr)
            logger.info("time multiscales   :", t_gen_scales)
            logger.info("n_scales           :", n_scales)
            logger.info("scale_ratio        :", scale_ratio)
            logger.info("chunks             :", chunks)
            logger.info("dataset            :", ds_name)
            logger.info("[cli arguments]")
            logger.info(vars(args))
            logger.info("[ds.info - s0 only]")
            logger.info(ds.info)
            logger.info("Done.")



    logger.info("printing result as tree...")
    ds = zarr.open(zarr_path)
    logger.info(ds.tree())

    logger.info('---------------------------------------------------------------------')
    logger.info('Time Elapsed (copy data to Zarr)                 : {:.2f} seconds'.format(t_to_zarr))
    logger.info('Time Elapsed (generate scales)                   : {:.2f} seconds'.format(t_gen_scales))
    logger.info('Total Time Elapsed                               : {:.2f} seconds'.format(t_total))
    logger.info('---------------------------------------------------------------------')
    logger.info("<<<< Exiting convert_zarr.py")


