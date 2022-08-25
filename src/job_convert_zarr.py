#!/usr/bin/env python3
'''
Each image is a Zarr group
Group level attributes for multiscale data are stored in the .zattrs file at the image level. NGFF Spec:
https://ngff.openmicroscopy.org/latest/
'''

import os
import sys
import zarr
import tifffile

if __name__ == '__main__':

    job_script   = sys.argv[0]
    ID           = int(sys.argv[1])
    img          = sys.argv[2]
    src          = sys.argv[3]
    out          = sys.argv[4]
    scale_str    = sys.argv[5]
    chunks       = sys.argv[6]
    n_imgs       = int(sys.argv[7])
    width        = int(sys.argv[8])
    height       = int(sys.argv[9])
    scale_val    = int(sys.argv[10])

    # chunks_zyx = chunks.split(',')

    scale_img = os.path.join(src, scale_str, 'img_aligned', img)
    im = tifffile.imread(scale_img) # im.dtype =  uint8
    # im = np.atleast_3d(im)
    # im = np.expand_dims(im, axis=0)
    #PROBABLY WANT TO SET DATA TYPE ON ARRAY CREATION
    store = zarr.open(out)
    store[ID,:,:] = im
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

    # array.attrs['axes'] = {
    #     "labels": ["z", "y", "x"],
    #     "types": ["space", "space", "space"],
    #     "units": ["nm", "nm", "nm"]
    # }
    # array.attrs['resolution'] = [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]
    # array.attrs['offset'] = [float(0), float(0), float(0)]

    # array.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    # array.attrs['resolution'] = [float(50.0), 2 * float(scale_val), 2 * float(scale_val)]
    # # array.attrs['offset']      = [0, 0, 0]
    # array.attrs['offset'] = [float(0), float(0), float(0)]


    # AXES_TYPE_DICT = {
    #     "x": "space",
    #     "y": "space",
    #     "z": "space",
    # }

    # array.attrs['axes'] = {
    #     "labels": ["z", "y", "x"],
    #     "types": ["space", "space", "space"],
    #     "units": ["nm", "nm", "nm"]
    # }
    # array.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    # print('i = ', i)
    # array.attrs['resolution']  = [float(50.0), 2*float(scale_val), 2*float(scale_val)]
    # # array.attrs['offset']      = [0, 0, 0]
    # array.attrs['offset']      = [float(ID*50), float(0), float(0)]

    # datasets = []
    # datasets.append(
    #     {"path": slug,
    #      "coordinateTransformations": [{
    #          "type": "scale",
    #          "scale": [float(50.0),2*float(scale), 2*float(scale)]
    #      }]}
    # )
    #
    # axes = [
    #             {"name": "z", "type": "space", "unit": "nanometer"},
    #             {"name": "y", "type": "space", "unit": "nanometer"},
    #             {"name": "x", "type": "space", "unit": "nanometer"}
    #         ]
    #
    # grp.attrs['multiscales'] = [
    #     {
    #     "version": "0.4",
    #     "name": "my_data",
    #     "axes": axes,
    #     "datasets": datasets,
    #     "type": "gaussian",
    #     "coordinateTransformations": [{
    #         "type": "translation",
    #         "translation": [float(ID*50), float(0), float(0)]
    #     }]
    #     }
    # ]

    sys.stdout.close()
    sys.stderr.close()
