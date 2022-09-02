#!/usr/bin/env python3

'''Job Script for Generating Neuroglancer-Compatible Zarr from Alignment Output Using Multiple Processors. Tasks are
queued by the script 'generate_zarr.py'. Group level attributes for multiscale data are stored in the .zattrs
file at the image level. NGFF Spec:
https://ngff.openmicroscopy.org/latest/

Joel Yancey 2022-08-15
'''

import os
import sys
import zarr
# import tifffile
from PIL import Image


if __name__ == '__main__':

    job_script   = sys.argv[0] #*
    ID           = int(sys.argv[1]) #*
    img          = sys.argv[2] #*
    src          = sys.argv[3] #*
    out          = sys.argv[4] #*
    scale_str    = sys.argv[5] #*

    scale_img = os.path.join(src, scale_str, 'img_aligned', img)
    # im = tifffile.imread(scale_img) # im.dtype =  uint8
    im = Image.open(scale_img)
    # im = np.atleast_3d(im)
    # im = np.expand_dims(im, axis=0)
    '''Probably want to set data type on array creation'''
    store = zarr.open(out)
    store[ID,:,:] = im
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

    sys.stdout.close()
    sys.stderr.close()
