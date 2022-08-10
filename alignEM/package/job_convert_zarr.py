#!/usr/bin/env python3

import os
import sys
import json
import argparse
import time
import logging
import tifffile
import dask.array as da
import imagecodecs
from pathlib import Path
from numcodecs import Blosc
# from image_utils import loadImage, saveImage
from swiftir import loadImage, saveImage
from swiftir import scaleImage

logger = logging.getLogger(__name__)

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


# CALL 'tiffs2zarr'
logger.info("(script) convert_zarr.py | converting original scale images to Zarr...")
t = time.time()
if no_compression:
    tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compressor=None,
               overwrite=overwrite)  # might pass in 'None'
else:
    if cname in ('zstd', 'zlib'):
        tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compressor=Blosc(cname=cname, clevel=clevel),
                   overwrite=overwrite)  # NOTE 'compressor='
        # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), compressor=zarr.get_codec({'id': cname, 'level': clevel}))
    else:
        tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compression=cname,
                   overwrite=overwrite)  # NOTE 'compression='
        # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), compression=compressor,overwrite=True)
        # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), cname=cname, clevel=clevel, overwrite=True)

t_to_zarr = time.time() - t

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("img", required=True, type=str, help="Input image name. Required.")
    parser.add_argument("dir_out", required=True, type=str, help="Output directory name. Required.")
    parser.add_argument("cname", default='zstd', type=str, help="Compression type name. Default: 'zstd'")
    parser.add_argument("clevel", default=5, type=int, help="Compression level, 0-9. Default: 5")
    parser.add_argument("chunkshape", default=(64,64,64), type=tuple, help="Chunk shape. Default: (64,64,64)")
    parser.add_argument("overwrite", default=True, type=bool, help="Overwrite boolean. Default: True")
    args = parser.parse_args()


    Path(args.dir_out).mkdir(parents=True, exist_ok=True)



    tiffs2zarr(args.fin, args.dir_out, args.chunkshape, args.cname, args.overwrite)
    #
    # print('writing .zarray...')
    # zarray = {}
    # zarray['chunks'] = [64,64,64]
    # zarray['compressor'] = {}
    # zarray['compressor']['id'] = 'zstd'
    # zarray['compressor']['level'] = 1
    # zarray['dtype'] = '|u1'
    # zarray['fill_value'] = 0
    # zarray['filters'] = None
    # zarray['order'] = 'C'
    # zarray['zarr_format'] = 2
    # with open(os.path.join(of,'img_aligned_zarr','s0','.zarray'), "w") as f:
    #     zarray['shape'] = [3, 4096, 4096]
    #     json.dump(zarray, f)
    #
    # with open(os.path.join(of,'img_aligned_zarr','s1','.zarray'), "w") as f:
    #     zarray['shape'] = [3, 2048, 2048]
    #     json.dump(zarray, f)
    #
    # with open(os.path.join(of,'img_aligned_zarr','s2','.zarray'), "w") as f:
    #     zarray['shape'] = [3, 1024, 1024]
    #     json.dump(zarray, f)
    # print('writing .zattrs...')
    # zattrs = {}
    # zattrs['offset'] = [0,0,0]
    # zattrs['resolution'] = [50,4,4]
    # with open(os.path.join(of,'img_aligned_zarr','s0','.zattrs'), "w") as f:
    #     json.dump(zattrs, f)
    # with open(os.path.join(of,'img_aligned_zarr','s1','.zattrs'), "w") as f:
    #     json.dump(zattrs, f)
    # with open(os.path.join(of,'img_aligned_zarr','s2','.zattrs'), "w") as f:
    #     json.dump(zattrs, f)


    sys.stdout.close()
    sys.stderr.close()