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
import shutil
import numcodecs
import numpy as np
numcodecs.blosc.use_threads = False
from libtiff import TIFF


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
    chunkshape   = tuple(map(int,sys.argv[4][1:-1].split(', ')))
    stageit      = bool(int(sys.argv[5]))
    dest         = sys.argv[6]
    '''
    out = os.path.join(od, 's%d' % get_scale_val(scale))
    fn = os.path.join(dest, scale, 'img_src', img)
    '''
    logger = logging.getLogger('job_convert_zarr.log')
    fh = logging.FileHandler(os.path.join(dest, 'logs', 'job_convert_zarr.log'))
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    logger.critical('\nRunning job:\n%s' %str(sys.argv))

    # synchronizer = zarr.ThreadSynchronizer()
    # store = zarr.open(out, synchronizer=synchronizer)\
    store = zarr.open(out, write_empty_chunks=False)
    tif = TIFF.open(fn)
    img = tif.read_image()[:,::-1] # np.array
    # img = TIFFfile(fn)  # pylibtiff -- LIBTIFF (pure Python module)
    # img = tifffile.imread(fn)
    store[ID,:,:] = img # store: <zarr.core.Array (19, 1244, 1130) uint8>
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    # store.attrs['ID'] = ID
    # store.attrs[f'{ID}_stageit'] = stageit
    # store.attrs['fn'] = fn
    # store.attrs['chunkshape'] = chunkshape


    if stageit:
        img_ = np.expand_dims(img, axis=0)
        # img.shape = (1024, 1024)
        # img_.shape = (1, 1024, 1024)

        out_name = 'staged'
        dir_scale = os.path.dirname(os.path.dirname(fn))
        dir_staged = os.path.join(dir_scale, 'zarr_staged')
        dir_staged_img = os.path.join(dir_staged, str(ID))
        path = os.path.join(dir_staged_img, out_name)
        grp = zarr.open(dir_staged_img)
        # arrays = dict(grp.info_items())['Arrays']
        # groups = dict(grp.info_items())['Groups']

        #Temporary!

        if os.path.exists(path):
            try:    shutil.rmtree(path, ignore_errors=True)
            except: pass

        # n_arrays = dict(grp.info_items())['No. arrays']
        # name_ = str(n_arrays) + '__'
        # grp.create_dataset(name=out_name, shape=img.shape, chunks=chunkshape[1:2], dtype='|u1', compressor=None)
        grp.create_dataset(name=out_name, shape=img_.shape, chunks=chunkshape, dtype='|u1', compressor=None)
        # grp[out_name][:,:] = img
        grp[out_name][:,:,:] = img_

        checksum = grp[out_name].digest()



    # del img
    sys.stdout.close()
    sys.stderr.close()



'''
https://zarr.readthedocs.io/en/stable/api/core.html

a.info_items()

Out[24]: 
[('Name', '/'),
 ('Type', 'zarr.hierarchy.Group'),
 ('Read-only', 'False'),
 ('Store cur_method', 'zarr.storage.DirectoryStore'),
 ('No. members', 37),
 ('No. arrays', 37),
 ('No. groups', 0),
 ('Arrays',
  '0, 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 2, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 3, 30, 31, 32, 33, 34, 35, 36, 4, 5, 6, 7, 8, 9')]





NOTE: CREATE versus OPEN

cd ~/scratch/2023-01-01
python3

import os, zarr, numpy as np
from libtiff import TIFF
fn = '/Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_aligned/dummy2.tif'
tif = TIFF.open(fn)
img = tif.read_image()[:,::-1] # np.array
img_ = np.expand_dims(img, axis=0)
dir_staged = '/Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/zarr_staged'
chunkshape = cfg.data.chunkshape()
ID = 7
arr = zarr.open('/Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/zarr_staged/15')




arr = grp.zeros(str(ID), shape=img_.shape, chunks=chunkshape, dtype='i8')

z = zarr.array(img_, chunks=(1, 512,512))
store = zarr.DirectoryStore(dir_staged)


zarr.open_array(dir_staged, shape=img_.shape)
arr = grp.zeros(str(ID), shape=img_.shape, chunks=chunkshape, dtype='i8')


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

