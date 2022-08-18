#!/usr/bin/env python3
'''
Each image is a Zarr group
Group level attributes for multiscale data are stored in the .zattrs file at the image level. NGFF Spec:
https://ngff.openmicroscopy.org/latest/
'''

import os
import sys

import numpy as np
import zarr
import tifffile

if __name__ == '__main__':

    job_script   = sys.argv[0]
    ID           = int(sys.argv[1])
    img          = sys.argv[2]
    src          = sys.argv[3]
    out          = sys.argv[4]
    scales       = sys.argv[5].split(",")
    chunks       = (1, int(sys.argv[6]), int(sys.argv[6]))
    n_imgs       = int(sys.argv[7])
    # dim_x       = int(sys.argv[8])
    # dim_y       = int(sys.argv[9])
    dim_x_lst    = sys.argv[8].split(",")
    dim_y_lst    = sys.argv[9].split(",")
    scale_vals   = sys.argv[10].split(",")

    # sandbox_dir = '/Users/joelyancey/glanceem_swift/sandbox'
    # if ID == 1:
    #     with open(os.path.join(sandbox_dir, 'parameters.txt'), 'w') as f:
    #         f.write('----\n')
    #         f.write('job_script: %s\n' % job_script)
    #         f.write('ID: %d\n' % ID)
    #         f.write('img: %s\n' % img)
    #         f.write('src: %s\n' % src)
    #         f.write('out: %s\n' % out)
    #         f.write('scales: %s\n' % str(scales))
    #         f.write('chunks: %s\n' % str(chunks))
    #         f.write('n_imgs: %d\n' % n_imgs)
    #         f.write('dim_x_lst: %s\n' % str(dim_x_lst))
    #         f.write('dim_y_lst: %s\n' % str(dim_y_lst))
    #         f.write('scale_vals: %s\n' % str(scale_vals))
    #         f.write('----')

    ### TESTING ONLY
    # ID = 0
    # img = 'R34CA1-BS12.101.tif'
    # src = '/Users/joelyancey/glanceem_swift/test_projects/small_proj_3'
    # out = '/Users/joelyancey/glanceem_swift/sandbox'
    # scales = ['scale_1', 'scale_2', 'scale_4']
    # chunks = (1,4096,4096)
    # n_imgs = 15
    # dim_x_lst = '4300,2148,1070,'.split(",")
    # dim_y_lst = '4300,2148,1070'.split(",")
    # scale_vals = [1,2,4]

    AXES_TYPE_DICT = {
        "x": "space",
        "y": "space",
        "z": "space",
    }

    grp = zarr.group(out, overwrite=True)

    '''Loop Over Scales'''
    datasets = []
    # for i, scale in enumerate(scales):
    for i, scale in enumerate(scales):
        print('Scale %s...' % scale)
        slug = 'base' if scale == 'scale_1' else scale
        '''convert tiff -> numpy array -> zarr group'''

        scale_img = os.path.join(src, scale, 'img_aligned', img)
        im = tifffile.imread(scale_img) # im.dtype =  uint8
        print('shape(im) = %s' % str(np.shape(im)))
        # im = np.atleast_3d(im)
        im = np.expand_dims(im, axis=0)
        '''PROBABLY WANT TO SET DATA TYPE ON ARRAY CREATION'''

        grp.create_dataset(slug, data=im)

        array = zarr.open(os.path.join(out,slug))
        array.attrs['axes'] = {
            "labels": ["z", "y", "x"],
            "types": ["space", "space", "space"],
            "units": ["nm", "nm", "nm"]
        }
        array.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
        print('i = ', i)
        print('scale_vals[i] = ', scale_vals[i])
        print('2*scale_vals[i] = ', 2*scale_vals[i])
        array.attrs['resolution']  = [float(50.0), 2*float(scale_vals[i]), 2*float(scale_vals[i])]
        # array.attrs['offset']      = [0, 0, 0]
        array.attrs['offset']      = [float(ID*50), float(0), float(0)]

        datasets.append(
            {"path": slug,
             "coordinateTransformations": [{
                 "type": "scale",
                 "scale": [float(50.0),2*float(scale_vals[i]), 2*float(scale_vals[i])]
             }]}
        )

    axes = [
                {"name": "z", "type": "space", "unit": "nanometer"},
                {"name": "y", "type": "space", "unit": "nanometer"},
                {"name": "x", "type": "space", "unit": "nanometer"}
            ]

    grp.attrs['multiscales'] = [
        {
        "version": "0.4",
        "name": "my_data",
        "axes": axes,
        "datasets": datasets,
        "type": "gaussian",
        "coordinateTransformations": [{
            "type": "translation",
            "translation": [float(ID*50), float(0), float(0)]
        }]
        }
    ]

    sys.stdout.close()
    sys.stderr.close()
