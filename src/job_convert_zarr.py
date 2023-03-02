#!/usr/bin/env python3

'''Job Script for Generating Neuroglancer-Compatible
Zarr from Alignment Output Using Multiple Processors. Tasks
are queued by the script 'generate_scales_zarr.py'. Group level
attributes for multiscale datamodel are stored in the .zattrs file
at the image level. NGFF Spec: https://ngff.openmicroscopy.org/latest/
Joel Yancey 2022-08-15
'''

import os
import sys
import zarr
import logging
import numpy as np
import numcodecs
numcodecs.blosc.use_threads = False
from libtiff import TIFF

try:     import src.config as cfg
except:  import config as cfg

logger = logging.getLogger(__name__)
logpath = '/Users/joelyancey/Logs/temp_zarr.log'



def cat(outfilename, *infilenames):
    with open(outfilename, 'w') as outfile:
        for infilename in infilenames:
            with open(infilename) as infile:
                for line in infile:
                    if line.strip():
                        outfile.write(line)


if __name__ == '__main__':

    job_script   = sys.argv[0] #*
    ID           = int(sys.argv[1]) #*
    fn           = sys.argv[2]
    out          = sys.argv[3] #*

    # synchronizer = zarr.ThreadSynchronizer()
    # store = zarr.open(out, synchronizer=synchronizer)\
    store = zarr.open(out, write_empty_chunks=False)

    tif = TIFF.open(fn)
    img = tif.read_image()[:,::-1] # np.array

    # img = TIFFfile(fn)  # pylibtiff -- LIBTIFF (pure Python module)
    # img = tifffile.imread(fn)

    store[ID,:,:] = img # store: <zarr.core.Array (19, 1244, 1130) uint8>
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

    img_ = np.expand_dims(img, axis=0)
    # img.shape = (1024, 1024)
    # img_.shape = (1, 1024, 1024)
    # copy_store.shape = <zarr.core.Array (1, 1024, 1024) float64>

    # out_stage = '/Users/joelyancey/glanceem_swift/test_projects/testProj2/img_staged/2'
    # if not os.path.isdir(stage):
    #     copy_store = zarr.open_array(stage, shape=img_.shape)
    # else:
    #     copy_store = zarr.open_array(stage, shape=img_.shape)
    #     copy_store.append(img_)

    if '/img_aligned/' in fn:

        grp = zarr.open_group(os.path.join(os.path.dirname(out), 'img_staged'), mode='w')

        p_stg = os.path.join(os.path.dirname(out), 'img_staged', str(ID))


        # open(logpath, 'a+').close()
        with open(logpath, 'a+') as f:
            f.write('\nCopy-writing %s to %s...' % (fn, p_stg))


        # z = zarr.array(img_, shape=img_.shape)
        # z = zarr.open_array(p_stg, shape=img_.shape, mode='w', dtype='uint8', fill_value=0)
        # # z = zarr.open(p_stg, mode='w')
        # z.append(img_, axis=0)

        store = zarr.DirectoryStore(p_stg)

        grp = zarr.open_group('data/example.zarr', mode='w')

        # a = zarr.create(shape=img_.shape, dtype='i4',
        #                 fill_value=42, compressor=None, store=store, overwrite=True)
        a = grp.create_dataset(shape=img_.shape, compressor=None, store=store, overwrite=False)
        a.append(img_)


        # copy_store = zarr.create(shape=img_.shape)
        # copy_store = zarr.open_array(shape=img_.shape)
        # copy_store.append(img_, axis=0)

        # if not os.path.isdir(stage):
        #     with open(logpath, 'a+') as f:
        #         f.write('\nINITopening Zarr...')
        #     # copy_store = zarr.open_array(stage, shape=img_.shape)s
        #     copy_store = zarr.open_array(stage, shape=img_.shape)
        #     # copy_store = zarr.open_array(stage, shape=img_.shape)
        #     # copy_store = zarr.create(shape=img_.shape)
        #     # copy_store[0,:,:] = img_
        #     # with open(logpath, 'a+') as f:
        #     #     f.write('copy_store.shape = %s' %str(copy_store.shape))
        #
        # else:
        #     with open(logpath, 'a+') as f:
        #         f.write('\nREopening Zarr...')
        #     copy_store = zarr.open(stage)
        #     with open(logpath, 'a+') as f:
        #         f.write('copy_store.shape (BEFORE) = %s' % str(copy_store.shape))
        #     copy_store.append(img_, axis=0)
        #     with open(logpath, 'a+') as f:
        #         f.write('copy_store.shape (AFTER) = %s' % str(copy_store.shape))

        # zarr.save_array(copy_store)
        # z_arr = zarr.open(stage, shape=img.shape)
        # x, y = img
        # print('copy_store.shape = %s' %str(store.shape))

    # del img
    sys.stdout.close()
    sys.stderr.close()



'''

NOTE: CREATE versus OPEN

cd ~/scratch/2023-01-01
python3

c
tif = TIFF.open(fn)
img = tif.read_image()[:,::-1] # np.array
img_ = np.expand_dims(img, axis=0)
stage = 'img_staged/foo'
zarr.open_array(stage, shape=img_.shape)


>>> from libtiff import TIFF
>>> import os, zarr, numpy as np
>>> fn = 'funky3.tif'
>>> tif = TIFF.open(fn)
>>> img = tif.read_image()[:,::-1]
>>> stage = 'img_staged/3'
>>> copy_store = zarr.open(stage,)
>>> copy_store
<zarr.hierarchy.Group '/'>
>>> img_ = np.expand_dims(img, axis=0)
>>> copy_store2 = zarr.open_array(stage, shape=img_.shape)
>>> copy_store2
<zarr.core.Array (1, 512, 1024) float64>

'''

