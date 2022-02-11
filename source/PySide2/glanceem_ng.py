#!/usr/bin/env python3
from glanceem_utils import RequestHandler, Server, add_layer, tiffs2zarr, create_scale_pyramid
import neuroglancer as ng
import zarr
import argparse, os, sys, time
import numpy as np
import daisy
import os, sys
import dask
import dask.array as da
import skimage
from PIL import Image
# Documentation on PIL.Image:
# https://pillow.readthedocs.io/en/stable/reference/Image.html
import webbrowser
from glob import glob
from numcodecs import Blosc, Delta, LZMA, Zstd
import json
import multiprocessing
from io import BytesIO



# ^ necessary because pillow is stupid
# see: https://stackoverflow.com/questions/646286/how-to-write-png-image-to-string-with-the-pil

Image.MAX_IMAGE_PIXELS = None
# (prevents the following error for very large images)
# PIL.Image.DecompressionBombError: Image size (603979776 pixels) exceeds limit of 178956970 pixels, could be decompression bomb DOS attack.

# very interesting about REFERENCE FILE SYSTEM:
# https://observablehq.com/@manzt/ome-tiff-as-filesystemreference

# LAPTOP DISPLAY: 2880 × 1800

# affine transforms supported in NG via the nifti format.
# https://github.com/google/neuroglancer/issues/333

# At all blend scales, the needed affine transform is 1e-8 in X & Y

# Look into tradeoffs of rechunking

#
# **** layer_group_viewer.ts ****
#
# SingletonLayerGroupViewer
# SingletonLayerGroupViewer(element, spec, container.viewer)
# ^ layer_groups_viewer.py

# 'focus' layer (object type) needs to be more unlinked
# 'focus' layer also needs scale factor preset

# 'ManagedLayer' class in viewer_state.py.



def unchunk(s):
    print("'u' key press detected. Executing unchunk function...")
    # this is parallel
    path = src
    scale = 0
    n_unchunk = int(s.mouse_voxel_coordinates[2])
    #img_scale = da.from_zarr(path + '/img_aligned_zarr/s' + str(scale))
    img_scale = da.from_zarr(path + '/' + ds_aligned + '/s0')
    curr_img = img_scale[n_unchunk, :, :]
    skimage.io.imsave('image_' + str(n_unchunk) + '_scale' + str(scale) + '.tif', curr_img)

    print("Callback complete.")

# def unchunk_all_scale(s, scale):
#     # this can be parallel

def blend(s):
    print("'b' key press detected. Executing blend function...")
    blend_scale = 0
    n_blend = int(s.mouse_voxel_coordinates[2])
    blend_name = 'blended_' + str(n_blend) + '-' + str(n_blend + 1) + '.tif'

    print("Creating blended TIF of images " + str(n_blend) + " and " + str(n_blend+1) + " using PIL.Image...")

    #img_scale = da.from_zarr(src + '/img_aligned_zarr/s0')
    img_scale = da.from_zarr(src + '/' + ds_aligned + '/s' + str(blend_scale))
    curr_img = img_scale[n_blend, :, :]
    next_img = img_scale[n_blend+1, :, :]
    out1 = 'temp_image_' + str(n_blend) + '.tif'
    out2 = 'temp_image_' + str(n_blend+1) + '.tif'
    skimage.io.imsave(out1, curr_img)
    skimage.io.imsave(out2, next_img)

    img1 = Image.open(out1)
    img2 = Image.open(out2)

    result = Image.blend(img1, img2, 0.5)
    print('Removing temporary TIF files...')
    os.remove(out1)
    os.remove(out2)

    print('Saving image blend as temporary TIF ' + blend_name + '...')
    result.save(blend_name)

    copy_json = json.loads(open(os.path.join(src, ds_aligned, 's0', '.zattrs')).read())

    print('Reading .zarray for ...')

    print('Adding blend to Zarr group ' + ds_blended + '...')
    """ NOTE **kawgs is passed to zarr.creation.create """
    """ https://zarr.readthedocs.io/en/latest/api/creation.html#zarr.creation.create """
    #tiffs2zarr(blend_name, os.path.join(src, ds_blended), tuple(chunks), compressor=Blosc(cname=cname, clevel=clevel), overwrite=True)
    tiffs2zarr(blend_name, os.path.join(src, ds_blended), tuple(chunks), compressor=Blosc(cname='zstd', clevel=1), overwrite=True) #jy
    print('Removing temporary TIF: ' + blend_name + '...')
    os.remove(blend_name)
    print('Copying json for appropriate scale...')
    ds = zarr.open(os.path.join(src,ds_blended), mode='a')
    copy_json = json.loads(open(os.path.join(src, ds_aligned, 's' + str(blend_scale), '.zattrs')).read())
    ds.attrs['offset'] = copy_json['offset']
    #ds.attrs['resolution'] = copy_json['resolution']
    #ds.attrs['resolution'] = [50,.00000001,.00000001]

    copy_json = json.loads(open(os.path.join(src, ds_aligned, 's0', '.zattrs')).read())
    ds.attrs['units'] = copy_json['units']
    ds.attrs['_ARRAY_DIMENSIONS'] = copy_json['_ARRAY_DIMENSIONS']
    # ds.attrs['_ARRAY_DIMENSIONS'] = copy_json['_ARRAY_DIMENSIONS']

    #compressor = {'id': cname, 'level': clevel}
    #create_scale_pyramid(src, ds_blended, scales, chunks, compressor)


    # z = zarr.open(os.path.join(src, ds_blended))
    # print("Creating blend ng.LocalVolume...")
    # try:
    #     blend_vol = ng.LocalVolume(
    #         data=z,
    #         dimensions=dimensions)
    # except:
    #     print("  ERROR creating blend ng.LocalVolume")

    s.layers['focus'].visible = True
    print("Updating viewer.txn()...")
    with viewer.txn() as s:
        try:
            s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr", voxel_size=[i * .00000001 for i in resolution])
        except:
            print("  ERROR updating viewer.txn() with blend_vol ImageLayer")


    print("Callback complete.")


    # im = Image.open(f_result)
    # im.show()

    # POSSIBLE WORKFLOW FOR VIEWING SINGLE BLEND IN NEUROGLANCER VIEWER
    # 1. Create blended image
    # 2. If project.zarr/img_blended_zarr group does not exist, create it
    # 3. Converted blended image to Zarr using tiffs2zarr utility function (from glanceem_utils.py).
    # 4. Blended image array is appended to project.zarr/img_blended_zarr
    # 5. Neuroglancer viewer top panel is updated to display Zarr group img_blended_zarr


# example keypress callback
def get_mouse_coords(s):
    print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
    print('  Layer selected values: %s' % (s.selected_values,))


def open_ds(path, ds_name):
    """ wrapper for daisy.open_ds """
    print("Running daisy.open_ds with path:" + path + ", ds_name:" + ds_name)
    try:
        return daisy.open_ds(path, ds_name)
    except KeyError:
        print("\n  ERROR: dataset " + ds_name + " could not be loaded. Must be Daisy-like array.\n")
        return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser()

    # required arguments
    ap.add_argument('path', type=str, help='Directory to serve')

    #optional arguments
    ap.add_argument('-p', '--port', type=int, default=9000, help='TCP port to listen on (Default: 9000)')
    ap.add_argument('-a', '--bind', default='127.0.0.1', help='Bind address (Default: 127.0.0.1)')
    ap.add_argument('-v', '--view', default='single', help='View layout. Choose "single" or "row" (Default: "single")')
    args = ap.parse_args()
    src = args.path


    # src = os.path.abspath(args.path) # probably overkill
    # src = "project.zarr" # probably underkill
    view = args.view

    res_x = 2
    res_y = 2
    res_z = 50

    # if view == 'row':
    #     #src = '~/glanceem_feb/glanceem_demo_1/project.zarr' # ?
    #     src = '/Users/joelyancey/glanceem_feb/glanceem_demo_1/project.zarr'

    print("Setting multiprocessing.set_start_method('fork', force=True)...")
    multiprocessing.set_start_method("fork", force=True)

    # LOAD METADATA - .zarray
    print("Loading metadata from .zarray")
    zarray_path = os.path.join(src, "img_aligned_zarr", "s0", ".zarray")
    print("zarray_path : ", zarray_path)
    with open(zarray_path) as f:
        zarray_keys = json.load(f)
    chunks = zarray_keys["chunks"]

    #cname = zarray_keys["compressor"]["cname"] #jy
    #clevel = zarray_keys["compressor"]["clevel"] #jy

    shape = zarray_keys["shape"]


    # LOAD META DATA - .zattrs
    print("Loading metadata from .zattrs")
    zattrs_path = os.path.join(src, "img_aligned_zarr", "s0", ".zattrs")
    with open(zattrs_path) as f:
        zattrs_keys = json.load(f)
    print("zattrs_path : ", zattrs_path)
    resolution = zattrs_keys["resolution"]
    scales = zattrs_keys["scales"]

    print("scales : ", scales)

    ds_ref = "img_ref_zarr"
    ds_base = "img_base_zarr"
    ds_aligned = "img_aligned_zarr"
    ds_blended = "img_blended_zarr"

    print("Preparing browser view of " + src + "...")
    print("args.bind                       :", args.bind)
    print("args.port                       :", args.port)

    print("Connecting to CORS web server...")
    os.chdir(src)
    server = Server((args.bind, args.port))
    sa = server.socket.getsockname()
    host = str("http://%s:%d" % (sa[0], sa[1]))
    print("Serving                         :", host)
    viewer_source = str("zarr://" + host)
    print("Viewer source                   :", viewer_source)
    print("Protocol version                :", server.protocol_version)
    print("Server name                     :", server.server_name)
    print("Server type                     :", server.socket_type)
    #print("allow reuse address= ", server.allow_reuse_address)
    print("Creating neuroglancer.Viewer()...")
    viewer = ng.Viewer()

    print("img_unaligned_zarr exists in source.")
    print("Looking for REF scale directories...")
    data_ref = []
    ref_scale_paths = glob(os.path.join(src, ds_ref) + "/s*")
    for s in ref_scale_paths:
        scale = os.path.join(ds_ref, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending ref data...")
        data_ref.append(open_ds(src, scale))

    print("img_unaligned_zarr exists in source.")
    print("Looking for BASE scale directories...")
    data_base = []
    base_scale_paths = glob(os.path.join(src, ds_base) + "/s*")
    for s in base_scale_paths:
        scale = os.path.join(ds_base, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending base data...")
        data_base.append(open_ds(src, scale))


    print("img_aligned_zarr data set exists in source.")
    print("Looking for ALIGNED scale directories...")
    data_aligned = []
    aligned_scale_paths = glob(os.path.join(src,ds_aligned) + "/s*")
    for s in aligned_scale_paths:
        scale = os.path.join(ds_aligned, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending aligned data...")
        data_aligned.append(open_ds(src, scale))

    print("Defining coordinate space...")
    dimensions = ng.CoordinateSpace(
        names=['x', 'y', 'z'],
        units='nm',
        #scales=scales, #jy
        scales=[res_x, res_y, res_z],
    )


# https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
    print("Updating viewer.txn()...")
    with viewer.txn() as s:

        s.cross_section_background_color = "#ffffff"
        s.dimensions = dimensions
        #s.perspective_zoom = 300
        #s.position = [0.24, 0.095, 0.14]
        #s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

        #temp = np.zeros_like(data_ref)
        # layer = ng.Layer(temp)

        # only for 3 pane view
        if view=='row':
            add_layer(s, data_ref, 'ref')
            add_layer(s, data_base, 'base')

        add_layer(s, data_aligned, 'aligned')

        ###data_panel_layout_types: frozenset(['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'])

        # s.selectedLayer.visible = False
        #s.layers['focus'].visible = False

        #view = "single"

        if view == "row":
            print("view= row")

            s.layers['focus'].visible = True

            # [
            #     ng.LayerGroupViewer(layers=["focus"], layout='xy'),


            # temp = np.zeros_like(data_ref)
            # #layer = ng.Layer()
            # #layer = ng.ManagedLayer
            # s.layers['focus'] = ng.LocalVolume(temp)


            #s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr",voxel_size=[i * .00000001 for i in resolution])
            s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
            s.layout = ng.column_layout(
                [
                    ng.row_layout(
                        [
                                ng.LayerGroupViewer(layers=["focus"], layout='xy'),
                        ]
                    ),

                    ng.row_layout(
                        [
                            ng.LayerGroupViewer(layers=['ref'], layout='xy'),
                            ng.LayerGroupViewer(layers=['base'], layout='xy'),
                            ng.LayerGroupViewer(layers=['aligned'], layout='xy'),
                        ]
                    ),
                ]
            )

            # s.layout = ng.column_layout(
            #
            #     [
            #         ng.LayerGroupViewer(layers=["focus"], layout='xy'),
            #
            # s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
            #
            # ng.row_layout(
            #     [
            #         ng.LayerGroupViewer(layers=["ref"], layout='xy'),
            #         ng.LayerGroupViewer(layers=["base"], layout='xy'),
            #         ng.LayerGroupViewer(layers=["aligned"], layout='xy'),
            #     ]
            # )
            #
            #
            #
            #
            #     ]
            #
            # ]
            # # )


        # single image view
        if view == "single" :
            print('view= single')
            s.layout = ng.column_layout(
                [
                    ng.LayerGroupViewer(
                        layout='xy',
                        layers=["aligned"]),
                ]
        )


    viewer.actions.add('get_mouse_coords_', get_mouse_coords)
    viewer.actions.add('unchunk_', unchunk)
    viewer.actions.add('blend_', blend)
    with viewer.config_state.txn() as s:
        s.input_event_bindings.viewer['keyt'] = 'get_mouse_coords_'
        s.input_event_bindings.viewer['keyu'] = 'unchunk_'
        s.input_event_bindings.viewer['keyb'] = 'blend_'
        s.status_messages['message'] = 'Welcome to glanceEM_SWiFT!'

        s.show_ui_controls = True
        s.show_panel_borders = True
        s.viewer_size = None


    viewer_url = str(viewer)
    webbrowser.open(viewer_url)
    print("Printing viewer state...")
    print(viewer.state)
    #print("\nNeuroglancer view (remote viewer)    :\n", ng.to_url(viewer.state))
    print("\nNeuroglancer view (local viewer)     :\n", viewer, "\n")\

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("An exception occurred related to server.serve_forever()")
        server.server_close()
        sys.exit(0)

    print("Running ng.stop()...")
    ng.stop()
