#!/usr/bin/env python3

'''Job Script for Generating Neuroglancer-Compatible
Zarr from Alignment Output Using Multiple Processors. Tasks
are queued by the script 'generate_scales_zarr.py'. Group level
attributes for multiscale data are stored in the .zattrs file
at the image level. NGFF Spec: https://ngff.openmicroscopy.org/latest/
Joel Yancey 2022-08-15
'''

import os
import sys
import zarr
from PIL import Image
import numpy as np
import numcodecs
numcodecs.blosc.use_threads = False

Image.MAX_IMAGE_PIXELS = 1_000_000_000_000

if __name__ == '__main__':

    job_script   = sys.argv[0] #*
    ID           = int(sys.argv[1]) #*
    fn           = sys.argv[2]
    out          = sys.argv[3] #*
    # store          = sys.argv[3] #*

    synchronizer = zarr.ThreadSynchronizer()
    store = zarr.open(out, synchronizer=synchronizer)
    store[ID,:,:] = np.flip(Image.open(fn), axis=1)
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    sys.stdout.close()
    sys.stderr.close()
