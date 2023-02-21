#!/usr/bin/env python3

'''Job Script for Generating Neuroglancer-Compatible
Zarr from Alignment Output Using Multiple Processors. Tasks
are queued by the script 'generate_scales_zarr.py'. Group level
attributes for multiscale datamodel are stored in the .zattrs file
at the image level. NGFF Spec: https://ngff.openmicroscopy.org/latest/
Joel Yancey 2022-08-15
'''

import sys
import zarr
from tifffile import tifffile
import numcodecs
numcodecs.blosc.use_threads = False
from libtiff import TIFF, TIFFfile, TIFFimage


if __name__ == '__main__':

    job_script   = sys.argv[0] #*
    ID           = int(sys.argv[1]) #*
    fn           = sys.argv[2]
    out          = sys.argv[3] #*

    # synchronizer = zarr.ThreadSynchronizer()
    # store = zarr.open(out, synchronizer=synchronizer)\
    store = zarr.open(out, write_empty_chunks=False)

    tif = TIFF.open(fn)
    img = tif.read_image()[:,::-1] # numpy array

    # LIBTIFF (pure Python module)
    # img = TIFFfile(fn)  # pylibtiff
    # img = tifffile.imread(fn)

    store[ID,:,:] = img # store: <zarr.core.Array (19, 1244, 1130) uint8>
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

    del img #flush datamodel in memory


