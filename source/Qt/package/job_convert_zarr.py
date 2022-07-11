#!/usr/bin/env python3

import os
import sys
import argparse
import time
import tifffile
import dask.array as da
import imagecodecs
import swiftir

from swiftir import loadImage, scaleImage, saveImage


\def tiffs2zarr(tif_files, zarrurl, chunkshape, overwrite=True, **kwargs):
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

no_compression = 0
filenames = ['filename1', 'filename2', 'filename3']
zarr_ds_path = 'path/path/path'

cname = 'zstd'
clevel=5
chunk_shape_tuple = (64,64,64)
zarr_ds_path = 'path/path/path'
overwrite = True

# CALL 'tiffs2zarr'
print("(script) convert_zarr.py | converting original scale images to Zarr...")
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
    parser.add_argument("path_in", type=str, help="Input directory containing .tif/.tiff images.")
    parser.add_argument("path_out", type=str, help="Output filename for the converted Zarr file")
    parser.add_argument("outfile", help="file name of the scaled image")
    arg_space = parser.parse_args()

    print("SCALE: " + str(arg_space.scale) + " " + arg_space.infile + " " + arg_space.outfile)

    # img = align_swiftir.swiftir.scaleImage(align_swiftir.swiftir.loadImage(arg_space.infile), fac=arg_space.scale)
    # align_swiftir.swiftir.saveImage(img, arg_space.outfile)
    img = swiftir.scaleImage(loadImage(arg_space.infile), fac=arg_space.scale)
    swiftir.saveImage(img, arg_space.outfile)

    sys.stdout.close()
    sys.stderr.close()