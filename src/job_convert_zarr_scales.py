#!/usr/bin/env python3

'''Job Script for Generating Neuroglancer-Compatible MULTISCALE
Zarr from Alignment Output Using Multiple Processors. Tasks
are queued by the script 'generate_zarr_scales.py'. Group level
attributes for multiscale data are stored in the .zattrs file
at the image level. NGFF Spec: https://ngff.openmicroscopy.org/latest/
Joel Yancey 2022-08-15
'''

import os
import sys
import zarr
from PIL import Image
# import tifffile

if __name__ == '__main__':

    job_script   = sys.argv[0] #*
    ID           = int(sys.argv[1]) #*
    img          = sys.argv[2] #*
    src          = sys.argv[3] #*
    out          = sys.argv[4] #*
    scale_str    = sys.argv[5] #*

    Image.MAX_IMAGE_PIXELS = 1_000_000_000_000

    scale_img = os.path.join(src, scale_str, 'img_aligned', img)
    # im = tifffile.imread(scale_img)
    im = Image.open(scale_img)
    store = zarr.open(out)
    store[ID,:,:] = im
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    sys.stdout.close()
    sys.stderr.close()
