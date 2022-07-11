'''
Takes .tifs and turns them into .zarr (a chunked file format). Uses dask to parallelize reading/writing.
'''

import tifffile
import dask.array as da
import imagecodecs

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