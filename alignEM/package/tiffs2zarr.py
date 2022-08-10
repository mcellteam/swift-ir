#!/usr/bin/env python3

'''
Takes .tifs and turns them into .zarr (a chunked file format). Uses dask to parallelize reading/writing.
'''
import os
import sys
import json
import shutil
import argparse
from pathlib import Path
import tifffile
import dask.array as da
import imagecodecs


__all__ = ['tiffs2zarr']

# CREME DE LA CREME - BEAUTIFUL IMPLEMENTATION
# Convert Tiffs to Zarr with implicit dask array
# Ref: https://forum.image.sc/t/store-many-tiffs-into-equal-sized-tiff-stacks-for-hdf5-zarr-chunks-using-ome-tiff-format/61055
def tiffs2zarr(tif_files, zarrurl, chunkshape, overwrite=True, **kwargs):
    print('tiffs2zarr:')
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
    files_1024 = sorted(list(Path('./test_data').glob(r'*1024.tif')))
    files_2048 = sorted(list(Path('./test_data').glob(r'*2048.tif')))
    files_4096 = sorted(list(Path('./test_data').glob(r'*4096.tif')))
    # print(filenames)
    print('tiffs2zarr is scaling size 1024...')
    tiffs2zarr(files_1024, os.path.join(of, 'img_aligned_zarr', 's2'), chunk_shape_tuple, compression='zstd',overwrite=True)
    print('tiffs2zarr is scaling size 2048...')
    tiffs2zarr(files_2048, os.path.join(of, 'img_aligned_zarr', 's1'), chunk_shape_tuple, compression='zstd',overwrite=True)
    print('tiffs2zarr is scaling size 4096...')
    tiffs2zarr(files_4096, os.path.join(of,'img_aligned_zarr','s0'), chunk_shape_tuple, compression='zstd', overwrite=True)

    print('writing .zarray...')
    zarray = {}
    zarray['chunks'] = [64,64,64]
    zarray['compressor'] = {}
    zarray['compressor']['id'] = 'zstd'
    zarray['compressor']['level'] = 1
    zarray['dtype'] = '|u1'
    zarray['fill_value'] = 0
    zarray['filters'] = None
    zarray['order'] = 'C'
    zarray['zarr_format'] = 2
    with open(os.path.join(of,'img_aligned_zarr','s0','.zarray'), "w") as f:
        zarray['shape'] = [3, 4096, 4096]
        json.dump(zarray, f)

    with open(os.path.join(of,'img_aligned_zarr','s1','.zarray'), "w") as f:
        zarray['shape'] = [3, 2048, 2048]
        json.dump(zarray, f)

    with open(os.path.join(of,'img_aligned_zarr','s2','.zarray'), "w") as f:
        zarray['shape'] = [3, 1024, 1024]
        json.dump(zarray, f)
    print('writing .zattrs...')
    zattrs = {}
    zattrs['offset'] = [0,0,0]
    zattrs['resolution'] = [50,4,4]
    with open(os.path.join(of,'img_aligned_zarr','s0','.zattrs'), "w") as f:
        json.dump(zattrs, f)
    with open(os.path.join(of,'img_aligned_zarr','s1','.zattrs'), "w") as f:
        json.dump(zattrs, f)
    with open(os.path.join(of,'img_aligned_zarr','s2','.zattrs'), "w") as f:
        json.dump(zattrs, f)


    sys.stdout.close()
    sys.stderr.close()

