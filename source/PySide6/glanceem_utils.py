#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
import webbrowser
import neuroglancer
import operator
import logging, json
import numpy as np
import zarr
import daisy
import skimage.measure
import tifffile
import imagecodecs
import dask.array as da
import struct
import multiprocessing
import os
import time
import traceback
import copy
import neuroglancer as ng
from glob import glob
from PIL import Image
from source_tracker import get_hash_and_rev # what was Bob using this for?

from PySide6.QtWidgets import QInputDialog, QDialog, QProgressBar, QMessageBox
from PySide6.QtCore import QThread, QThreadPool
try:
    from PySide6.QtCore import Signal, Slot
except ImportError:
    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtCore import pyqtSlot as Slot

from get_image_size import get_image_size

import alignem

center_switch = 0


# IMPORTS FROM alignem_swift.py
# from source_tracker import get_hash_and_rev
# import sys, traceback, os, time, shutil, psutil, copy, argparse, cv2, json, platform, inspect, logging, glob

# from PySide6.QtWidgets import QInputDialog, QDialog, QPushButton, QProgressBar, QMessageBox, QApplication, \
#     QVBoxLayout, QTextEdit, QPlainTextEdit, QWidget
# from PySide6.QtCore import Signal, QObject, QUrl, QThread, QThreadPool
# from PySide6.QtGui import QImageReader
# import pyswift_tui
# import align_swiftir
# import task_queue_mp as task_queue
# import task_wrapper
# import project_runner


logger = logging.getLogger(__name__)

DAISY_VERSION = 1

def areImagesImported() -> bool:
    '''Checks if any images have been imported.'''

    try:
        len(alignem.project_data['data']['scales']['scale_1']['alignment_stack'])
        print('  areImagesImported | Returning True')
        check = True
    except:
        print('  areImagesImported | Returning False')
        check = False

    print('areImagesImported | Returning %s' % check)

    return check


def getNumImportedImages() -> int:
    '''Returns # of imported images.

    CHECK THIS FOR OFF-BY-ONE BUG'''

    try:
        n_imgs = len(alignem.project_data['data']['scales']['scale_1']['alignment_stack'])
        print('getNumImportedImages | Returning %d as int' % n_imgs)
        return n_imgs
    except:
        print('getNumImportedImages | WARNING | No image layers were found')
        return


def getCurScale() -> str:
    '''Returns the current scale, according to alignem.project_data (project dictionary).'''
    print('getCurScale:')

    cur_scale = alignem.project_data['data']['current_scale']
    print('  getCurScale | Returning %s' % cur_scale)
    return cur_scale

def isDestinationSet() -> bool:
    '''Checks if there is a project open'''

    if alignem.project_data['data']['destination_path']:
        check = True
    else:
        check = False
    # print('  isDestinationSet() | Returning %s' % check)
    return check

def isProjectScaled() -> bool:
    '''Checks if there exists any stacks of scaled images

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''

    if len(alignem.project_data['data']['scales']) < 2:
        isScaled = False
    else:
        isScaled = True

    print('isProjectScaled | checking if %s is less than 2 (proxy for not scaled)' % str(len(alignem.project_data['data']['scales'])))
    print('isProjectScaled | Returning %s' % isScaled)
    return isScaled

def isScaleAligned() -> bool:
    '''Checks if there exists an alignment stack for the current scale

    #fix Note: This will return False if no scales have been generated, but code should be dynamic enough to run alignment
    functions even for a project that does not need scales.'''

    if len(alignem.project_data["data"]["scales"][alignem.get_cur_scale()]["alignment_stack"]) < 1:
        # print('isAlignmentOfCurrentScale() | False')
        isAligned = False
    else:
        # print('isAlignmentOfCurrentScale() | True | # aligned images: ', len(alignem.project_data["data"]["scales"][alignem.get_cur_scale()]["alignment_stack"]))
        isAligned = True

    print('isScaleAligned | Returning %s' % isAligned)

    # print('isScaleAligned() | returning:', isAligned)
    return isAligned

def getNumAligned() -> int:
    '''Returns the count aligned images for the current scale'''

    path = os.path.join(alignem.project_data['data']['destination_path'], alignem.get_cur_scale(), 'img_aligned')
    print('getNumAligned() | path=', path)
    try:
        n_aligned = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
    except:
        print('getNumAligned() | EXCEPTION | Unable to get number of aligned - returning 0')
        return 0
    print('getNumAligned() | returning:', n_aligned)
    return n_aligned

def getSkipsList() -> list[int]:
    '''Returns the list of skipped images at the current scale'''

    skip_list = []
    try:
        for layer_index in range(len(alignem.project_data['data']['scales'][get_cur_scale()]['alignment_stack'])):
            if alignem.project_data['data']['scales'][get_cur_scale()]['alignment_stack'][layer_index]['skip'] == True:
                skip_list.append(layer_index)
            print('getSkipsList() | ', str(skip_list))
    except:
        print('getSkipsList | EXCEPTION | failed to get skips list')

    return skip_list

def isAlignmentOfCurrentScale() -> bool:
    '''Checks if there exists a set of aligned images at the current scale
    DOES *NOT* WORK AS EXPECTED
    ISSUES THAT REGENERATING SCALES MEANS PREVIOUS AALIGNMENTS STILL EXIST AND THUS THIS CAN INCORRECTLY RETURN TRUE
    MIGHT WANT TO HAVE SCALE RE-GENERATION CAUSE PREVIOUSLY ALIGNED IMAGES TO BE REMOVED'''

    path = os.path.join(alignem.project_data['data']['destination_path'], getCurScale(), 'img_aligned')

    try:
        print("alignem.project_data['data']['destination_path'] = ", alignem.project_data['data']['destination_path'])
        files = glob(path + '/*.tif')

    except:
        print('isAlignmentOfCurrentScale | WARNING | Something went wrong. Check project dictionary.')

    if len(files) < 1:
        print('isAlignmentOfCurrentScale | Returning False')
        return False
    else:
        print('isAlignmentOfCurrentScale | Returning True')
        return True

def isAnyScaleAligned() -> bool:
    '''Checks if there exists a set of aligned images at the current scale'''

    try:
        files = glob(alignem.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        files = '' #0520
        print('isAnyScaleAligned | WARNING | Looking for *.tif in project dir but didnt find any')

    if len(files) > 0:
        print('isAnyScaleAligned | Returning True')
        return True
    else:
        print('isAnyScaleAligned | Returning False')
        return False

def returnAlignedImgs() -> list:
    '''Checks if there exists a set of aligned images at the current scale'''

    try:
        files = glob(alignem.project_data['data']['destination_path'] + '/scale_*/img_aligned/*.tif')
    except:
        print('returnAlignedImg | WARNING | Something went wrong. Check project dictionary.')

    print('returnAlignedImg | # aligned images found: ', len(files))
    print('returnAlignedImg | List of aligned imgs: ', files)
    return files

def isAnyAlignmentExported() -> bool:
    '''Checks if there exists an exported alignment'''

    return os.path.isdir(os.path.join(alignem.project_data['data']['destination_path'], 'project.zarr'))

def getNumOfScales() -> int:
    '''Returns the number of scales for the open project'''

    try: n_scales = len(alignem.project_data['data']['scales'])
    except: print('getNumOfScales | WARNING | Something went wrong getting the # of scales. Check project dictionary.')
    print('getNumOfScales() | Returning %d' % n_scales)
    return n_scales

def printCurrentDirectory():
    '''Checks if there exists a set of aligned images at the current scale'''

    print('Current directory is : %s' % os.getcwd())

def requestConfirmation(title, text):
    '''Simple request confirmation dialog.'''

    button = QMessageBox.question(None, title, text)
    print('requestConfirmation | button=',str(button))
    print('requestConfirmation | type(button)=', type(button))
    print("requestConfirmation | Returning " + str(button == QMessageBox.StandardButton.Yes))
    return (button == QMessageBox.StandardButton.Yes)

def print_exception():
    exi = sys.exc_info()
    print("  Exception type = " + str(exi[0]))
    print("  Exception value = " + str(exi[1]))
    print("  Exception trace = " + str(exi[2]))
    print("  Exception traceback:")
    traceback.print_tb(exi[2])


class UnknownImageFormat(Exception):
    pass

#-------------------------------------------------------------------------------
# Name:        get_image_size
# Purpose:     extract image dimensions given a file path using just
#              core modules
#
# Author:      Paulo Scardine (based on code from Emmanuel VAISSE)
#              Tom Bartol (stripped down to bare bones)
#
# Created:     26/09/2013
# Copyright:   (c) Paulo Scardine 2013
# Licence:     MIT
#-------------------------------------------------------------------------------
def get_image_size(file_path):
    """
    Return (width, height) for a given img file content - no external
    dependencies except the os and struct modules from core
    """
    size = os.path.getsize(file_path)

    with open(file_path,'rb') as input:
        height = -1
        width = -1
        data = input.read(25)

        if (size >= 10) and data[:6] in ('GIF87a', 'GIF89a'):
            # GIFs
            w, h = struct.unpack("<HH", data[6:10])
            width = int(w)
            height = int(h)
        elif ((size >= 24) and data.startswith(b'\211PNG\r\n\032\n')
              and (data[12:16] == b'IHDR')):
            # PNGs
            w, h = struct.unpack(">LL", data[16:24])
            width = int(w)
            height = int(h)
        elif (size >= 16) and data.startswith(b'\211PNG\r\n\032\n'):
            # older PNGs?
            w, h = struct.unpack(">LL", data[8:16])
            width = int(w)
            height = int(h)
        elif (size >= 2) and data.startswith(b'\377\330'):
            # JPEG
            msg = " raised while trying to decode as JPEG."
            input.seek(0)
            input.read(2)
            b = input.read(1)
            try:
                while (b and ord(b) != 0xDA):
                    while (ord(b) != 0xFF): b = input.read(1)
                    while (ord(b) == 0xFF): b = input.read(1)
                    if (ord(b) >= 0xC0 and ord(b) <= 0xC3):
                        input.read(3)
                        h, w = struct.unpack(">HH", input.read(4))
                        break
                    else:
                        input.read(int(struct.unpack(">H", input.read(2))[0])-2)
                    b = input.read(1)
                width = int(w)
                height = int(h)
            except struct.error:
                raise UnknownImageFormat("StructError" + msg)
            except ValueError:
                raise UnknownImageFormat("ValueError" + msg)
            except Exception as e:
                raise UnknownImageFormat(e.__class__.__name__ + msg)
        elif (size >= 26) and data.startswith(b'BM'):
            # BMP
            headersize = struct.unpack("<I", data[14:18])[0]
            if headersize == 12:
                w, h = struct.unpack("<HH", data[18:22])
                width = int(w)
                height = int(h)
            elif headersize >= 40:
                w, h = struct.unpack("<ii", data[18:26])
                width = int(w)
                # as h is negative when stored upside down
                height = abs(int(h))
            else:
                raise UnknownImageFormat(
                    "Unkown DIB header size:" +
                    str(headersize))
        elif (size >= 8) and data[:4] in (b'II\052\000', b'MM\000\052'):
            # Standard TIFF, big- or little-endian
            # BigTIFF and other different but TIFF-like formats are not
            # supported currently
            byteOrder = data[:2]
            boChar = '>' if byteOrder == b'MM' else "<"
            # maps TIFF type id to size (in bytes)
            # and python format char for struct
            tiffTypes = {
                1: (1, boChar + "B"),  # BYTE
                2: (1, boChar + "c"),  # ASCII
                3: (2, boChar + "H"),  # SHORT
                4: (4, boChar + "L"),  # LONG
                5: (8, boChar + "LL"),  # RATIONAL
                6: (1, boChar + "b"),  # SBYTE
                7: (1, boChar + "c"),  # UNDEFINED
                8: (2, boChar + "h"),  # SSHORT
                9: (4, boChar + "l"),  # SLONG
                10: (8, boChar + "ll"),  # SRATIONAL
                11: (4, boChar + "f"),  # FLOAT
                12: (8, boChar + "d")   # DOUBLE
            }
            ifdOffset = struct.unpack(boChar + "L", data[4:8])[0]
            try:
                countSize = 2
                input.seek(ifdOffset)
                ec = input.read(countSize)
                ifdEntryCount = struct.unpack(boChar + "H", ec)[0]
                # 2 bytes: TagId + 2 bytes: type + 4 bytes: count of values + 4
                # bytes: value offset
                ifdEntrySize = 12
                for i in range(ifdEntryCount):
                    entryOffset = ifdOffset + countSize + i * ifdEntrySize
                    input.seek(entryOffset)
                    tag = input.read(2)
                    tag = struct.unpack(boChar + "H", tag)[0]
                    if(tag == 256 or tag == 257):
                        # if type indicates that value fits into 4 bytes, value
                        # offset is not an offset but value itself
                        type = input.read(2)
                        type = struct.unpack(boChar + "H", type)[0]
                        if type not in tiffTypes:
                            raise UnknownImageFormat(
                                "Unkown TIFF field type:" +
                                str(type))
                        typeSize = tiffTypes[type][0]
                        typeChar = tiffTypes[type][1]
                        input.seek(entryOffset + 8)
                        value = input.read(typeSize)
                        value = int(struct.unpack(typeChar, value)[0])
                        if tag == 256:
                            width = value
                        else:
                            height = value
                    if width > -1 and height > -1:
                        break
            except Exception as e:
                msg = ' in filename: ' + str(file_path)
                raise UnknownImageFormat(str(e)+msg)
        elif size >= 2:
            # ICO
                # see http://en.wikipedia.org/wiki/ICO_(file_format)
            input.seek(0)
            reserved = input.read(2)
            if 0 != struct.unpack("<H", reserved)[0]:
                raise UnknownImageFormat(
                    "Sorry, don't know how to get size for this file."
                )
            format = input.read(2)
            assert 1 == struct.unpack("<H", format)[0]
            num = input.read(2)
            num = struct.unpack("<H", num)[0]
            if num > 1:
                import warnings
                warnings.warn("ICO File contains more than one image")
            # http://msdn.microsoft.com/en-us/library/ms997538.aspx
            w = input.read(1)
            h = input.read(1)
            width = ord(w)
            height = ord(h)
        else:
            raise UnknownImageFormat(
                "Sorry, don't know how to get information from this file."
            )

    return width, height






class RequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        SimpleHTTPRequestHandler.end_headers(self)


class Server(HTTPServer):
    protocol_version = 'HTTP/1.1'

    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, RequestHandler)

def decode_json(x):
    return json.loads(x, object_pairs_hook=collections.OrderedDict)

def get_json(path):
    with open(path) as f:
        return json.load(f)
        # example: keys = get_json("project.zarr/img_aligned_zarr/s0/.zarray")

# CREME DE LA CREME - BEAUTIFUL IMPLEMENTATION
# Convert Tiffs to Zarr with implicit dask array
# Ref: https://forum.image.sc/t/store-many-tiffs-into-equal-sized-tiff-stacks-for-hdf5-zarr-chunks-using-ome-tiff-format/61055
def tiffs2zarr(tif_files, zarrurl, chunkshape, overwrite=True, **kwargs):
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

def open_ds(path, ds_name):
    """ wrapper for daisy.open_ds """
    print("Running daisy.open_ds with path:" + path + ", ds_name:" + ds_name)
    try:
        return daisy.open_ds(path, ds_name)
    except KeyError:
        print("\n  ERROR: dataset " + ds_name + " could not be loaded. Must be Daisy-like array.\n")
        return None


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




def get_viewer_url(src):
    print("\n\nCalling get_viewer_url(src)...\n\n")

    Image.MAX_IMAGE_PIXELS = None

    bind = '127.0.0.1'
    port = 9000
    view = 'single'

    res_x = 2
    res_y = 2
    res_z = 50

    print("Setting multiprocessing.set_start_method('fork', force=True)...")
    multiprocessing.set_start_method("fork", force=True)

    # LOAD METADATA - .zarray
    print("Loading metadata from .zarray")
    zarray_path = os.path.join(src, "img_aligned_zarr", "s0", ".zarray")
    print("zarray_path : ", zarray_path)
    with open(zarray_path) as f:
        zarray_keys = json.load(f)
    chunks = zarray_keys["chunks"]

    # cname = zarray_keys["compressor"]["cname"] #jy
    # clevel = zarray_keys["compressor"]["clevel"] #jy

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
    print("bind                       :", bind)
    print("port                       :", port)

    # os.chdir(src)
    if 0:
        server = Server((bind, port))
        sa = server.socket.getsockname()
        host = str("http://%s:%d" % (sa[0], sa[1]))
        print("Serving                         :", host)
        viewer_source = str("zarr://" + host)
        print("Viewer source                   :", viewer_source)
        print("Protocol version                :", server.protocol_version)
        print("Server name                     :", server.server_name)
        print("Server type                     :", server.socket_type)
        # print("allow reuse address= ", server.allow_reuse_address)


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
    aligned_scale_paths = glob(os.path.join(src, ds_aligned) + "/s*")
    for s in aligned_scale_paths:
        scale = os.path.join(ds_aligned, os.path.basename(s))
        print("Daisy is opening scale ", s, ". Appending aligned data...")
        data_aligned.append(open_ds(src, scale))

    print("Defining coordinate space...")
    dimensions = ng.CoordinateSpace(
        names=['x', 'y', 'z'],
        units='nm',
        # scales=scales, #jy
        scales=[res_x, res_y, res_z],
    )

    # https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
    print("Updating viewer.txn()...")
    with viewer.txn() as s:

        #s.cross_section_background_color = "#ffffff"
        s.dimensions = dimensions
        # s.perspective_zoom = 300
        # s.position = [0.24, 0.095, 0.14]
        # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

        # temp = np.zeros_like(data_ref)
        # layer = ng.Layer(temp)


        # only for 3 pane view
        if view == 'row':
            add_layer(s, data_ref, 'ref')
            add_layer(s, data_base, 'base')

        add_layer(s, data_aligned, 'aligned')

        ###data_panel_layout_types: frozenset(['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'])

        # s.selectedLayer.visible = False
        # s.layers['focus'].visible = False

        # view = "single"

        if view == "row":
            print("view= row")

            s.layers['focus'].visible = True

            # [
            #     ng.LayerGroupViewer(layers=["focus"], layout='xy'),

            # temp = np.zeros_like(data_ref)
            # #layer = ng.Layer()
            # #layer = ng.ManagedLayer
            # s.layers['focus'] = ng.LocalVolume(temp)

            # s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr",voxel_size=[i * .00000001 for i in resolution])
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
        if view == "single":
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
    webbrowser.open(viewer_url) #jy
    print("Printing viewer state...")
    print(viewer.state)
    # print("\nNeuroglancer view (remote viewer)    :\n", ng.to_url(viewer.state))
    print("\nNeuroglancer view (local viewer)     :\n", viewer, "\n")

    #time.sleep(60)

    return(viewer_url)







# # fsspec integration of tifffile
# with tifffile.imread(tiff_filename, aszarr=True) as store:
#     store.write_fsspec(tiff_filename + '.json', url)

class ScalePyramid(neuroglancer.LocalVolume):
    """A neuroglancer layer that provides volume data on different scales.
    Mimics a LocalVolume.

    Args:

            volume_layers (``list`` of ``LocalVolume``):

                One ``LocalVolume`` per provided resolution.
    """

    def __init__(self, volume_layers):
        volume_layers = volume_layers

        super(neuroglancer.LocalVolume, self).__init__()

        logger.debug("Creating scale pyramid...")

        self.min_voxel_size = min(
            [tuple(layer.dimensions.scales) for layer in volume_layers]
        )
        self.max_voxel_size = max(
            [tuple(layer.dimensions.scales) for layer in volume_layers]
        )

        self.dims = len(volume_layers[0].dimensions.scales)
        self.volume_layers = {
            tuple(
                int(x)
                for x in map(
                    operator.truediv, layer.dimensions.scales, self.min_voxel_size
                )
            ): layer
            for layer in volume_layers
        }

        logger.debug("min_voxel_size: %s", self.min_voxel_size)
        logger.debug("scale keys: %s", self.volume_layers.keys())
        logger.debug(self.info())

    @property
    def volume_type(self):
        return self.volume_layers[(1,) * self.dims].volume_type

    @property
    def token(self):
        return self.volume_layers[(1,) * self.dims].token

    def info(self):

        reference_layer = self.volume_layers[(1,) * self.dims]
        # return reference_layer.info()
        reference_info = reference_layer.info()

        info = {
            "dataType": reference_info["dataType"],
            "encoding": reference_info["encoding"],
            "generation": reference_info["generation"],
            "coordinateSpace": reference_info["coordinateSpace"],
            "shape": reference_info["shape"],
            "volumeType": reference_info["volumeType"],
            "voxelOffset": reference_info["voxelOffset"],
            "chunkLayout": reference_info["chunkLayout"],
            "downsamplingLayout": reference_info["downsamplingLayout"],
            "maxDownsampling": int(
                np.prod(np.array(self.max_voxel_size) // np.array(self.min_voxel_size))
            ),
            "maxDownsampledSize": reference_info["maxDownsampledSize"],
            "maxDownsamplingScales": reference_info["maxDownsamplingScales"],
        }

        return info

    def get_encoded_subvolume(self, data_format, start, end, scale_key=None):
        if scale_key is None:
            scale_key = ",".join(("1",) * self.dims)

        scale = tuple(int(s) for s in scale_key.split(","))

        return self.volume_layers[scale].get_encoded_subvolume(
            data_format, start, end, scale_key=",".join(("1",) * self.dims)
        )

    def get_object_mesh(self, object_id):
        return self.volume_layers[(1,) * self.dims].get_object_mesh(object_id)

    def invalidate(self):
        return self.volume_layers[(1,) * self.dims].invalidate()


def add_layer(
    context,
    array,
    name,
    opacity=None,
    shader=None,
    visible=True,
    reversed_axes=False,
    scale_rgb=False,
    c=[0, 1, 2],
    h=[0.0, 0.0, 1.0],
):

    print('\nadd_layer:')
    print('context:', context)
    print('type(array):', type(array))
    print('name:', name)

    """Add a layer to a neuroglancer context.
    Args:
        context:
            The neuroglancer context to add a layer to, as obtained by
            ``viewer.txn()``.
        array:
            A ``daisy``-like array, containing attributes ``roi``,
            ``voxel_size``, and ``data``. If a list of arrays is given, a
            ``ScalePyramid`` layer is generated.
        name:
            The name of the layer.
        opacity:
            A float to define the layer opacity between 0 and 1
        shader:
            A string to be used as the shader. If set to ``'rgb'``, an RGB
            shader will be used.
        visible:
            A bool which defines layer visibility
        c (channel):
            A list of ints to define which channels to use for an rgb shader
        h (hue):
            A list of floats to define rgb color for an rgba shader
    """
    is_multiscale = type(array) == list

    print("is_multiscale =",is_multiscale)

    if not is_multiscale:

        print("Entering conditional, if not is_multiscale...")

        a = array if not is_multiscale else array[0]

        spatial_dim_names = ["t", "z", "y", "x"]
        channel_dim_names = ["b^", "c^"]


        # NOTE, in alignem.py:
        # dimensions = ng.CoordinateSpace(
        #     names=['x', 'y', 'z'],
        #     units='nm',
        #     # scales=scales, #jy
        #     scales=[res_x, res_y, res_z],
        # )

        dims = len(a.data.shape)


        if DAISY_VERSION == 1:
            spatial_dims = a.roi.dims #daisy1
        else:
            spatial_dims = a.roi.dims() #old
        channel_dims = dims - spatial_dims

        attrs = {
            "names": (channel_dim_names[-channel_dims:] if channel_dims > 0 else [])
            + spatial_dim_names[-spatial_dims:],
            "units": [""] * channel_dims + ["nm"] * spatial_dims,
            "scales": [1] * channel_dims + list(a.voxel_size),
        }
        if reversed_axes:
            attrs = {k: v[::-1] for k, v in attrs.items()}
        dimensions = neuroglancer.CoordinateSpace(**attrs)

        voxel_offset = [0] * channel_dims + list(a.roi.get_offset() / a.voxel_size)
        print("str(voxel_offset) = ", str(voxel_offset))
        #voxel_offset = [0,0,0]
    else:
        dimensions = []
        voxel_offset = None
        for i, a in enumerate(array):
            print("\nenumerating data; i = ",i)

            # spatial_dim_names = ["t", "z", "y", "x"]
            # channel_dim_names = ["b^", "c^"]
            spatial_dim_names = ["z", "y", "x"]

            dims = len(a.data.shape)  # original
            #dims = a.roi.dims

            print("a.roi.dims = ", a.roi.dims)
            print("len(a.data.shape) = ", len(a.data.shape))



            if DAISY_VERSION == 1:
                spatial_dims = a.roi.dims  # daisy1
            else:
                spatial_dims = a.roi.dims()  # old
            channel_dims = dims - spatial_dims
            print("dims = ", str(dims))
            print("channel_dims = ", channel_dims)



            attrs = {
                "names": spatial_dim_names[-spatial_dims:],
                "units": ["nm"] * spatial_dims,
                "scales": list(a.voxel_size),
            }
            print("str(attrs) = ", str(attrs))
            if reversed_axes:
                attrs = {k: v[::-1] for k, v in attrs.items()}
            dimensions.append(neuroglancer.CoordinateSpace(**attrs))

            print("a.roi.get_offset() = ", a.roi.get_offset())
            print("a.voxel_size = ",a.voxel_size)
            if voxel_offset is None:
                voxel_offset = [0] * channel_dims + list(
                    a.roi.get_offset() / a.voxel_size
                )
            print("voxel_offset = ", voxel_offset)

    if reversed_axes:
        voxel_offset = voxel_offset[::-1]

    if shader is None:
        a = array if not is_multiscale else array[0]

        if DAISY_VERSION == 1:
            dims = a.roi.dims #daisy1
        else:
            dims = a.roi.dims() #old

    if is_multiscale:
        print("\nCalling ScalePyramid to create neurolgancer.LocalVolume...")
        print("  voxel_offset             : ", voxel_offset)
        print("  data                     : ", array)
        #print("dimensions               : ", dimensions)
        for i,d in enumerate(dimensions):
            # print("type(d) = ",type(d)) #  <class 'neuroglancer.coordinate_space.CoordinateSpace'>
            print("  dimension[" + str(i) + "] = " + str(dimensions[i]))

        layer = ScalePyramid(
            [
                neuroglancer.LocalVolume(data=a.data, voxel_offset=voxel_offset, dimensions=array_dims)
                for a, array_dims in zip(array, dimensions)
            ]
        )
        print("layer.info() = ", layer.info())

    else:
        print("is_multiscale is False. Creating ng.LocalVolume...")
        layer = neuroglancer.LocalVolume(
            data=array.data,
            voxel_offset=voxel_offset,
            dimensions=dimensions,
        )

    #context.layers.append(name=name, layer=layer, visible=visible, **kwargs) # NameError: name 'kwargs' is not defined
    context.layers.append(name=name, layer=layer, visible=visible)



def downscale_block(in_array, out_array, factor, block):
    dims = len(factor)
    in_data = in_array.to_ndarray(block.read_roi, fill_value=0)

    in_shape = daisy.Coordinate(in_data.shape[-dims:])
    assert in_shape.is_multiple_of(factor)

    n_channels = len(in_data.shape) - dims
    print("downscale_block | dims = len(factor) = ", len(factor))
    print("downscale_block | in_shape = daisy.Coordinate(in_data.shape[-dims:] = ",daisy.Coordinate(in_data.shape[-dims:]))
    print("downscale_block | n_channels = len(in_data.shape) - dims = ", len(in_data.shape) - dims)
    if n_channels >= 1:
        factor = (1,)*n_channels + factor

    if in_data.dtype == np.uint64:
        slices = tuple(slice(k//2, None, k) for k in factor)
        out_data = in_data[slices]
    else:
        out_data = skimage.measure.block_reduce(in_data, factor, np.mean)

    try:
        out_array[block.write_roi] = out_data
    except Exception:
        print("Failed to write to %s" % block.write_roi)
        raise

    return 0



def downscale(in_array, out_array, factor, write_size):

    print("\n  Downsampling by factor " + str(factor) + "...")

    if DAISY_VERSION == 1:
        dims = in_array.roi.dims #daisy1
    else:
        dims = in_array.roi.dims() #old

    block_roi = daisy.Roi((0,)*dims, write_size)


    print("    processing ROI %s with blocks %s" % (out_array.roi, block_roi))
    print("    in_array  : shape = " + str(in_array.shape) + " chunk_shape = " + str(in_array.chunk_shape) + " voxel_size = " + str(in_array.voxel_size))
    print("    out_array : shape = " + str(out_array.shape) + " chunk_shape = " + str(out_array.chunk_shape) + " voxel_size = " + str(out_array.voxel_size))

    # DEBUGGING OUTPUT
    # in_array.shape = (270, 4096, 4096)
    # in_array.chunk_shape = (64, 64, 64)
    # in_array.voxel_size = (50, 2, 2)
    # in_array.n_channel_dims = 0
    # str(in_array.roi) = [0:13500, 0: 8192, 0: 8192] (13500, 8192, 8192)
    #
    # out_array.shape = (1, 270, 2048, 2048)
    # out_array.chunk_shape = (1, 1, 16, 16)
    # out_array.voxel_size = (50, 4, 4)
    # out_array.n_channel_dims = 1
    # str(out_array.roi) = [0:13500, 0: 8192, 0: 8192] (13500, 8192, 8192)


    if DAISY_VERSION == 1:
        downscale_task = daisy.Task(
            'downscale',
            out_array.roi,
            block_roi,
            block_roi,
            process_function=lambda b: downscale_block(
                in_array,
                out_array,
                factor,
                b),
            read_write_conflict=False,
            num_workers=60,
            #num_workers=8,
            # num_workers=4,
            max_retries=0,
            # max_retries=3,
            fit='shrink')

        # foo_task = daisy.Task(
        #     'foo',
        #     total_roi,
        #     block_read_roi,
        #     block_write_roi,
        #     process_function=lambda b: downscale_block(
        #         in_array,
        #         out_array,
        #         factor,
        #         b),
        #     read_write_conflict=False,
        #     # num_workers=60,
        #     # num_workers=8,
        #     num_workers=4,
        #     max_retries=0,
        #     # max_retries=3,
        #     fit='shrink')

        done = daisy.run_blockwise([downscale_task])

        if not done:
            raise RuntimeError("daisy.Task failed for (at least) one block")

    else:
        daisy.run_blockwise(
            out_array.roi,
            block_roi,
            block_roi,
            process_function=lambda b: downscale_block(
                in_array,
                out_array,
                factor,
                b),
            read_write_conflict=False,
            #num_workers=60,
            #num_workers=8,
            num_workers=4,
            max_retries=0,
            #max_retries=3,
            fit='shrink')



#def create_scale_pyramid(in_file, in_ds_name, scales, chunk_shape, cname, clevel):
def create_scale_pyramid(in_file, in_ds_name, scales, chunk_shape, compressor={'id': 'zstd', 'level': 5}):
    """
    # https://zarr.readthedocs.io/en/stable/api/convenience.html#zarr.convenience.open
    # https://zarr.readthedocs.io/en/stable/_modules/zarr/convenience.html
    #ds = zarr.open(in_file)
    # refer to convenience.py zarr source code
    # no mode specified, default is mode='a'

    prepare_ds
    see: https://daisy-docs.readthedocs.io/_/downloads/en/latest/pdf/
    also: https://daisy-docs.readthedocs.io/en/latest/api.html
    """

    print("\nCreating scale pyramid...")
    print("\n  Input arguments:")
    print("    in_file       : ", in_file)
    print("    in_ds_name    : ", in_ds_name)
    print("    scales        : ", str(scales))
    print("    chunk_shape   : ", str(chunk_shape))
    print("    compressor    : ", str(compressor))

    ds = zarr.open(in_file)
    # make sure in_ds_name points to a dataset
    try:
        print("  Opening Zarr dataset as daisy Array...")
        daisy.open_ds(in_file, in_ds_name)
    except Exception:
        raise RuntimeError("%s does not seem to be a dataset" % in_ds_name)

    if not in_ds_name.endswith('/s0'):

        ds_name = in_ds_name + '/s0'

        print("  Moving %s to %s..." % (in_ds_name, ds_name))
        ds.store.rename(in_ds_name, in_ds_name + '__tmp')
        ds.store.rename(in_ds_name + '__tmp', ds_name)
    else:

        ds_name = in_ds_name
        in_ds_name = in_ds_name[:-3]

    print("  Scaling %s by a factor of %s" % (in_file, scales))

    print("\n  Calling daisy.open_ds to create 'prev_array' with arguments:")
    print("    in_file = ", str(in_file))
    print("    ds_name = ", str(ds_name))

    prev_array = daisy.open_ds(in_file, ds_name)

    if chunk_shape is not None:
        chunk_shape = daisy.Coordinate(chunk_shape)
    else:
        chunk_shape = daisy.Coordinate(prev_array.data.chunks)
        print("Reusing chunk shape of %s for new datasets" % (chunk_shape,))

    if prev_array.n_channel_dims == 0:
        # print("Setting num_channels = 1")
        # num_channels = 1
        num_channels = None #!!!!
    elif prev_array.n_channel_dims == 1:
        print("Setting num_channels = prev_array.shape[0] = ", prev_array.shape[0])
        num_channels = prev_array.shape[0]
    else:
        raise RuntimeError(
            "more than one channel not yet implemented, sorry...")

    #num_channels = None #debug

    for scale_num, scale in enumerate(scales):
        print("\n  Working on scale " + str(scale_num) + ":")

        try:
            scale = daisy.Coordinate(scale)
        except Exception:
            scale = daisy.Coordinate((scale,)*chunk_shape.dims())

        next_voxel_size = prev_array.voxel_size*scale
        #next_voxel_size = daisy.Coordinate(prev_array.voxel_size*scale)
        next_total_roi = prev_array.roi.snap_to_grid(next_voxel_size,mode='grow')
        next_write_size = chunk_shape*next_voxel_size
        #next_write_size = daisy.Coordinate(chunk_shape*next_voxel_size)
        next_ds_name = in_ds_name + '/s' + str(scale_num + 1)

        print("    scale                     :", str(scale))
        print("    chunk_shape               :", str(chunk_shape))
        #print("    Next voxel size           :", str(next_voxel_size))
        #print("    Next chunk size           :", str(next_write_size))
        #print("    Next total ROI            :", next_total_roi)
        print("    Preparing dataset " + next_ds_name + "...")
        #print("    prev_array.dtype          :", prev_array.dtype)
        print("    prev_array.n_channel_dims :", prev_array.n_channel_dims)
        print("    num_channels              :", num_channels)
        print("    prev_array.shape[0]       :", prev_array.shape[0])

        curr_ds_path = in_file + '/' + in_ds_name
        # curr_ds = zarr.open(curr_ds_path)


        # ndims = 3
        # #total_roi_size = prev_array.roi
        # print("prev_array.roi = ", prev_array.roi)
        # # define total region of interest (roi)
        # total_roi_start = daisy.Coordinate((0,) * ndims)
        # total_roi_size = daisy.Coordinate(total_roi_size)
        # total_roi = daisy.Roi(total_roi_start, total_roi_size)
        # total_roi = prev_array.roi
        #
        # block_read_size = [64, 64, 64]
        # block_write_size = [64, 64, 64]

        # define block read and write rois
        # block_read_size = daisy.Coordinate(block_read_size)
        # block_write_size = daisy.Coordinate(block_write_size)
        # context = (block_read_size - block_write_size) / 2
        # block_read_roi = daisy.Roi(total_roi_start, block_read_size)
        # block_write_roi = daisy.Roi(context, block_write_size)

        # now use these :
        # total_roi,
        # block_read_roi,
        # block_write_roi,
        # print("total_roi = ", str(total_roi))
        # print("block_read_roi = ", str(block_read_roi))
        # print("block_write_roi = ", str(block_write_roi))

        # next_total_roi = total_roi
        # next_voxel_size = block_read_roi
        # next_write_size = next_write_size


        print("\n  Calling daisy.prepare_ds to create 'next_array' with arguments:")
        print("    " + str(in_file))
        print("    " + str(next_ds_name))
        print("    next_total_roi = ", str(next_total_roi))
        print("    next_voxel_size = ", str(next_voxel_size))
        print("    next_write_size = ", str(next_write_size))
        print("    dtype = ", prev_array.dtype)
        print("    num_channels = ", str(num_channels))
        print("    compressor = ", str(compressor))

        # / Users / joelyancey / glanceEM_SWiFT / test_projects / SYGQK_4096x4096_2022 - 03 - 28 / project.zarr
        # img_aligned_zarr / s1
        # next_total_roi = [0:13500, 0: 8192, 0: 8192] (13500, 8192, 8192)
        # next_voxel_size = (50, 4, 4)
        # next_write_size = (3200, 256, 256)
        # dtype = uint8
        # num_channels = 1
        # compressor = {'id': 'zstd', 'level': 5}


        # in daisy v1.0 the chunk shape for 'next_array' is not chosen correctly
        # daisy.prepare_ds doc:
        # https://github.com/funkelab/daisy/blob/6ef33068affaf78503a7ee73191080a40e35ec74/daisy/datasets.py
            # write_size (:class:`daisy.Coordinate`):
            # The size of anticipated writes to the dataset, in world units. The
            # chunk size of the dataset will be set such that ``write_size`` is a
            # multiple of it. This allows concurrent writes to the dataset if the
            # writes are aligned with ``write_size``.
        next_array = daisy.prepare_ds(
            in_file,
            next_ds_name,
            total_roi=next_total_roi,   #         total_roi (:class:`daisy.Roi`):
            voxel_size=next_voxel_size, #         voxel_size (:class:`daisy.Coordinate`):
            write_size=next_write_size, #         write_size (:class:`daisy.Coordinate`):
            dtype=prev_array.dtype,
            num_channels=num_channels, #!!!! num_channels default value is None, and must be None, not 0 to generate correct chunk_shape
            compressor=compressor
            #compressor={'id': cname, 'level': clevel}
        )

        # print("next_array.chunk_shape = ", next_array.chunk_shape)

        # default: compressor = {'id': 'gzip', 'level': 5}

        # API ref: https://daisy-docs.readthedocs.io/en/latest/api.html
        # source: https://daisy-docs.readthedocs.io/en/latest/_modules/daisy/datasets.html#prepare_ds

        print("\n  Calling downscale with arguments:")
        print("    prev_array (<- in_array) = ", str(prev_array)) # (<- in_array)
        print("    next_array (<- out_array)  = ", str(next_array)) # (<- out_array)
        print("    scale = ", str(scale))
        print("    next_write_size = ", str(next_write_size))

        downscale(prev_array, next_array, scale, next_write_size)

        prev_array = next_array

        print("\nScale complete.\n")


class SwiftirException:
    def __init__(self, project_file, message):
        self.project_file = project_file
        self.message = message
    def __str__(self):
        return self.message


'''
# to override or pass additional arguments...

class ValidationError(Exception):
    def __init__(self, message, errors):            
        # Call the base class constructor with the parameters it needs
        super().__init__(message)

        # Now for your custom code...
        self.errors = errors
        
        
        
Rules of global Keyword

The basic rules for global keyword in Python are:

    When we create a variable inside a function, it is local by default.
    When we define a variable outside of a function, it is global by default. You don't have to use global keyword.
    We use global keyword to read and write a global variable inside a function.
    Use of global keyword outside a function has no effect.

        
        
'''


########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################


def link_stack():
    print('Linking stack | link_stack...')

    skip_list = []
    for layer_index in range(len(alignem.project_data['data']['scales'][getCurScale()]['alignment_stack'])):
        if alignem.project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index][
            'skip'] == True:
            skip_list.append(layer_index)

    print('\nlink_stack(): Skip List = \n' + str(skip_list) + '\n')

    for layer_index in range(len(alignem.project_data['data']['scales'][getCurScale()]['alignment_stack'])):
        base_layer = alignem.project_data['data']['scales'][getCurScale()]['alignment_stack'][layer_index]

        if layer_index == 0:
            # No ref for layer 0
            if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
            base_layer['images']['ref']['filename'] = ''
        elif layer_index in skip_list:
            # No ref for skipped layer
            if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
            base_layer['images']['ref']['filename'] = ''
        else:
            # Find nearest previous non-skipped layer
            j = layer_index - 1
            while (j in skip_list) and (j >= 0):
                j -= 1

            # Use the nearest previous non-skipped layer as ref for this layer
            if (j not in skip_list) and (j >= 0):
                ref_layer = alignem.project_data['data']['scales'][getCurScale()]['alignment_stack'][j]
                ref_fn = ''
                if 'base' in ref_layer['images'].keys():
                    ref_fn = ref_layer['images']['base']['filename']
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
                base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print('\nskip_list =\n', str(skip_list))
    print('Exiting link_stack()')


'''
# ONLY CALLED WHEN LINKING LAYERS (i.e. when importing images)

DEPRECATE THIS
'''
def ensure_proper_data_structure():
    print('\n(!) ensure_proper_data_structure:\n')
    ''' Try to ensure that the data model is usable. '''
    scales_dict = alignem.project_data['data']['scales']
    for scale_key in scales_dict.keys():
        scale = scales_dict[scale_key]
        '''
        if not 'null_cafm_trends' in scale:
          scale ['null_cafm_trends'] = null_cafm_trends.get_value()
        if not 'use_bounding_rect' in scale:
          scale ['use_bounding_rect'] = make_bool ( use_bounding_rect.get_value() )
        if not 'poly_order' in scale:
          scale ['poly_order'] = poly_order.get_value()
        '''
        # 0405 #hardcode whatever values
        if not 'null_cafm_trends' in scale:
            scale['null_cafm_trends'] = False  # 0523 need to hardcode this since cannot any longer read the value from toggle
        if not 'use_bounding_rect' in scale:
            scale['use_bounding_rect'] = True  # 0523 need to hardcode this as well for similar reason
        if not 'poly_order' in scale:
            scale['poly_order'] = int(0)  # 0523 need to hardcode this as well for similar reason

        for layer_index in range(len(scale['alignment_stack'])):
            layer = scale['alignment_stack'][layer_index]
            if not 'align_to_ref_method' in layer:
                layer['align_to_ref_method'] = {}
            atrm = layer['align_to_ref_method']
            if not 'method_data' in atrm:
                atrm['method_data'] = {}
            mdata = atrm['method_data']
            if not 'win_scale_factor' in mdata:
                print("  Warning: if NOT 'win_scale_factor' in mdata was run")
                mdata['win_scale_factor'] = float(alignem.main_window.get_swim_input())

            # print("Evaluating: if not 'whitening_factor' in mdata")
            if not 'whitening_factor' in mdata:
                print("  Warning: if NOT 'whitening_factor' in mdata was run")
                mdata['whitening_factor'] = float(alignem.main_window.get_whitening_input())

    print("ensure_proper_data_structure | Exiting...")


# NOTE: this is called right after importing base images (through update_linking_callback)
def link_all_stacks():
    print('\nlink_all_stacks:')
    print('link_all_stacks | Linking all stacks for each scale')
    ensure_proper_data_structure()

    for scale_key in alignem.project_data['data']['scales'].keys():
        skip_list = []
        for layer_index in range(len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])):
            if alignem.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip'] == True:
                print('  appending layer ' + str(layer_index) + ' to skip_list')
                skip_list.append(layer_index)  # skip


        for layer_index in range(len(alignem.project_data['data']['scales'][scale_key]['alignment_stack'])):
            base_layer = alignem.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]

            if layer_index == 0:
                # No ref for layer 0 # <-- ******
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
                base_layer['images']['ref']['filename'] = ''
            elif layer_index in skip_list:
                # No ref for skipped layer
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
                base_layer['images']['ref']['filename'] = ''
            else:
                # Find nearest previous non-skipped layer
                j = layer_index - 1
                while (j in skip_list) and (j >= 0):
                    j -= 1

                # Use the nearest previous non-skipped layer as ref for this layer
                if (j not in skip_list) and (j >= 0):
                    ref_layer = alignem.project_data['data']['scales'][scale_key]['alignment_stack'][j]
                    ref_fn = ''
                    if 'base' in ref_layer['images'].keys():
                        ref_fn = ref_layer['images']['base']['filename']
                    if 'ref' not in base_layer['images'].keys():
                        base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
                    base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()

    if center_switch:
        alignem.main_window.center_all_images()


    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print("link_all_stacks | Exiting link_all_stacks()")


class RunProgressDialog(QDialog):
    """
    Simple dialog that consists of a Progress Bar and a Button.
    Clicking on the button results in the start of a timer and
    updates the progress bar.
    """

    def __init__(self):
        super().__init__()
        print("RunProgressDialog constructor called")
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Progress Bar')
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)
        self.progress.setMaximum(100)
        # self.button = QPushButton('Start', self)
        # self.button.move(0, 30)
        self.setModal(True)
        self.show()
        self.onButtonClick()

        # self.button.clicked.connect(self.onButtonClick)

    def onButtonClick(self):
        self.calc = RunnableThread()
        self.calc.countChanged.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)


class RunnableThread(QThread):
    """
    Runs a counter thread.
    """
    countChanged = Signal(int)

    def run(self):
        count = 0
        while count < COUNT_LIMIT:
            count += 1
            time.sleep(0.02)
            self.countChanged.emit(count)


def run_progress():
    print('run_progress: Initializing a RunProgressDialog()')
    global window
    window = RunProgressDialog()


# Call this function when run_json_project returns with need_to_write_json=false
def update_datamodel(updated_model):
    print('\nUpdating data model | update_datamodel...\n')
    # alignem.print_debug(1, 100 * "+")
    # alignem.print_debug(1, "run_json_project returned with need_to_write_json=false")
    # alignem.print_debug(1, 100 * "+")
    # Load the alignment stack after the alignment has completed
    aln_image_stack = []
    scale_to_run_text = alignem.project_data['data']['current_scale']
    stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']

    for layer in stack_at_this_scale:

        image_name = None
        if 'base' in layer['images'].keys():
            image_name = layer['images']['base']['filename']

        # Convert from the base name to the standard aligned name:
        aligned_name = None
        if image_name != None:
            # The first scale is handled differently now, but it might be better to unify if possible
            if scale_to_run_text == "scale_1":
                aligned_name = os.path.join(os.path.abspath(alignem.project_data['data']['destination_path']),
                                            scale_to_run_text, 'img_aligned', os.path.split(image_name)[-1])
            else:
                name_parts = os.path.split(image_name)
                if len(name_parts) >= 2:
                    aligned_name = os.path.join(os.path.split(name_parts[0])[0],
                                                os.path.join('img_aligned', name_parts[1]))
        aln_image_stack.append(aligned_name)
        # alignem.print_debug(30, "Adding aligned image " + aligned_name)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = aligned_name
    try:
        print('update_datamodel | trying to load_images_into_role')
        alignem.main_window.load_images_in_role('aligned', aln_image_stack)
    except:
        print('Error from main_win.load_images_in_role.')
        print_exception()
        pass
    alignem.main_window.refresh_all_images()

    # center
    # main_win.center_all_images()
    # main_win.update_win_self()
    if center_switch:
        alignem.main_window.center_all_images()
    alignem.main_window.update_win_self()


combo_name_to_dm_name = {'Init Affine': 'init_affine', 'Refine Affine': 'refine_affine', 'Apply Affine': 'apply_affine'}
dm_name_to_combo_name = {'init_affine': 'Init Affine', 'refine_affine': 'Refine Affine', 'apply_affine': 'Apply Affine'}

def clear_match_points():
    print('\nCalling clear_match_points() in alignem_swift.py:\n')

    # global match_pt_mode
    # if not match_pt_mode.get_value():
    if view_match_crop.get_value() != 'Match':
        print('"\nMust be in \"Match\" mode to delete all match points."')
    else:
        print('Deleting all match points for this layer')
        scale_key = alignem.project_data['data']['current_scale']
        layer_num = alignem.project_data['data']['current_layer']
        stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]

        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['match_points'] = []
                layer['images'][role]['metadata']['annotations'] = []
        main_win.update_panels()
        alignem.main_window.refresh_all_images()


def clear_all_skips():
    print('Clearing all skips | clear_all_skips...')
    image_scale_keys = [s for s in sorted(alignem.project_data['data']['scales'].keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
            layer['skip'] = False

    # main_win.status_skips_label.setText(str(skip_list))  # settext #status
    # skip.set_value(False) #skip


def copy_skips_to_all_scales():
    print('Copying skips to all scales | copy_skips_to_all_scales...')
    source_scale_key = alignem.project_data['data']['current_scale']
    if not 'scale_' in str(source_scale_key):
        source_scale_key = 'scale_' + str(source_scale_key)
    scales = alignem.project_data['data']['scales']
    image_scale_keys = [s for s in sorted(scales.keys())]
    for scale in image_scale_keys:
        scale_key = str(scale)
        if not 'scale_' in str(scale_key):
            scale_key = 'scale_' + str(scale_key)
        if scale_key != source_scale_key:
            for l in range(len(scales[source_scale_key]['alignment_stack'])):
                if l < len(scales[scale_key]['alignment_stack']):
                    scales[scale_key]['alignment_stack'][l]['skip'] = scales[source_scale_key]['alignment_stack'][l][
                        'skip']  # <----
    # Not needed: skip.set_value(scales[source_scale_key]['alignment_stack'][alignem.project_data['data']['current_layer']]['skip']


# skip
def update_skip_annotations():
    print('\nupdate_skip_annotations:\n')
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in alignem.project_data['data']['scales'].items():
        for layer in scale['alignment_stack']:
            layer_num = scale['alignment_stack'].index(layer)
            for ik, im in layer['images'].items():
                if not 'metadata' in im:
                    im['metadata'] = {}
                if not 'annotations' in im['metadata']:
                    im['metadata']['annotations'] = []
                ann = im['metadata']['annotations']
                if layer['skip']:
                    # Check and set as needed
                    already_skipped = False
                    for a in ann:
                        if a.startswith('skipped'):
                            already_skipped = True
                            break
                    if not already_skipped:
                        add_list.append((sk, layer_num, ik))
                        ann.append('skipped(1)')
                else:
                    # Remove all "skipped"
                    for a in ann:
                        if a.startswith('skipped'):
                            remove_list.append((sk, layer_num, ik))
                            ann.remove(a)
    # for item in remove_list:
    #     alignem.print_debug(80, "Removed skip from " + str(item))
    # for item in add_list:
    #     alignem.print_debug(80, "Added skip to " + str(item))


# NOTE: this is called right after importing base images
# def update_linking_callback():
#     print('Updating linking callback | update_linking_callback...')
#     link_all_stacks()
#     print('Exiting update_linking_callback()')
#
#
# def update_skips_callback(new_state):
#     print('Updating skips callback | update_skips_callback...')
#
#     # Update all of the annotations based on the skip values
#     copy_skips_to_all_scales()
#     # update_skip_annotations()  # This could be done via annotations, but it's easier for now to hard-code into alignem.py
#     print("Exiting update_skips_callback(new_state)")


# def mouse_down_callback(role, screen_coords, image_coords, button):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     # print("mouse_down_callback was called but there is nothing to do.")
#     return  # monkeypatch
#
#
# def mouse_move_callback(role, screen_coords, image_coords, button):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     return #monkeypatch #jy
#
#     # # print("view_match_crop.get_value() = ", view_match_crop.get_value())
#     # if view_match_crop.get_value() == 'Match':
#     #     return (True)  # Lets the framework know that the move has been handled
#     # else:
#     #     return (False)  # Lets the framework know that the move has not been handled

# def notyet():
#     print('notyet() was called')
#     # alignem.print_debug(0, "Function not implemented yet. Skip = " + str(skip.value)) #skip
#     # alignem.print_debug(0, "Function not implemented yet. Skip = " + alignem.main_window.toggle_skip.isChecked())

# def crop_mode_callback():
#     return
#     # return view_match_crop.get_value()



