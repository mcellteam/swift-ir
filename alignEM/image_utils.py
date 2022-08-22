#!/usr/bin/env python3

import os
import sys
import struct
import logging
import inspect
import numpy as np
import tifffile
try:     from alignEM.swiftir import composeAffine, identityAffine, invertAffine, modelBounds2
except:  from swiftir import composeAffine, identityAffine, invertAffine, modelBounds2

__all__ = [
    'get_image_size',
    'BiasMat',
    'BiasFuncs',
    'ApplyBiasFuncs',
    'InitCafm',
    'SetSingleCafm',
    'SetStackCafm',
    'BoundingRect',
    'invertAffine',
]

debug_level = 0

logger = logging.getLogger(__name__)

def get_image_size(file_path):
    """
    Return (width, height) for a given img file content - no external
    dependencies except the os and struct modules from core
    Name:        get_image_size
    Purpose:     extract image dimensions given a file path using just
                 core modules

    Author:      Paulo Scardine (based on code from Emmanuel VAISSE)
                 Tom Bartol (stripped down to bare bones)

    Created:     26/09/2013
    Copyright:   (c) Paulo Scardine 2013
    Licence:     MIT
    """
    logger.debug('get_image_size:')
    size = os.path.getsize(file_path)

    with open(file_path, 'rb') as input:
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
                        input.read(int(struct.unpack(">H", input.read(2))[0]) - 2)
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
                12: (8, boChar + "d")  # DOUBLE
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
                    if (tag == 256 or tag == 257):
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
                raise UnknownImageFormat(str(e) + msg)
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


# Return the bias matrix at position x in the stack as given by the bias_funcs
def BiasMat(x, bias_funcs):
    logger.debug('BiasMat:')

    #  xdot = np.array([4.0,3.0,2.0,1.0])

    poly_order = len(bias_funcs['x']) - 1
    xdot = np.arange(poly_order, 0, -1, dtype='float64')

    p = bias_funcs['skew_x']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    skew_x_bias = -fdp(x)

    p = bias_funcs['scale_x']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    scale_x_bias = 1 - fdp(x)

    p = bias_funcs['scale_y']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    scale_y_bias = 1 - fdp(x)

    p = bias_funcs['rot']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    rot_bias = -fdp(x)

    p = bias_funcs['x']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    x_bias = -fdp(x)

    p = bias_funcs['y']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    y_bias = -fdp(x)

    # Create skew, scale, rot, and tranlation matrices
    skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0], [0.0, 1.0, 0.0]])
    scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0], [0.0, scale_y_bias, 0.0]])
    rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0], [np.sin(rot_bias), np.cos(rot_bias), 0.0]])
    trans_bias_mat = np.array([[1.0, 0.0, x_bias], [0.0, 1.0, y_bias]])

    bias_mat = identityAffine()

    # Compose bias matrix as skew*scale*rot*trans
    bias_mat = composeAffine(skew_x_bias_mat, bias_mat)
    bias_mat = composeAffine(scale_bias_mat, bias_mat)
    bias_mat = composeAffine(rot_bias_mat, bias_mat)
    bias_mat = composeAffine(trans_bias_mat, bias_mat)

    # logger.info('<<<< BiasMat')

    return bias_mat


# NEW
# Find the bias functions that best fit the trends in c_afm across the whole stack
# For now the form of the functions is an Nth-order polynomial
def BiasFuncs(al_stack, bias_funcs=None, poly_order=4):
    logger.debug('BiasFuncs:')
    poly_order = int(poly_order)
    if type(bias_funcs) == type(None):
        init_scalars = True
        bias_funcs = {}
        bias_funcs['skew_x'] = np.zeros((poly_order + 1))
        bias_funcs['scale_x'] = np.zeros((poly_order + 1))
        bias_funcs['scale_y'] = np.zeros((poly_order + 1))
        bias_funcs['rot'] = np.zeros((poly_order + 1))
        bias_funcs['x'] = np.zeros((poly_order + 1))
        bias_funcs['y'] = np.zeros((poly_order + 1))
    else:
        init_scalars = False
        poly_order = len(bias_funcs['x']) - 1

    skew_x_array = np.zeros((len(al_stack), 2))
    scale_x_array = np.zeros((len(al_stack), 2))
    scale_y_array = np.zeros((len(al_stack), 2))
    rot_array = np.zeros((len(al_stack), 2))
    x_array = np.zeros((len(al_stack), 2))
    y_array = np.zeros((len(al_stack), 2))

    i = 0
    for align_idx in range(len(al_stack)):
        c_afm = np.array(al_stack[align_idx]['align_to_ref_method']['method_results']['cumulative_afm'])

        rot = np.arctan(c_afm[1, 0] / c_afm[0, 0])
        scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
        scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
        skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
        det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])

        skew_x_array[i] = [align_idx, skew_x]
        scale_x_array[i] = [align_idx, scale_x]
        scale_y_array[i] = [align_idx, scale_y]
        rot_array[i] = [align_idx, rot]
        x_array[i] = [align_idx, c_afm[0, 2]]
        y_array[i] = [align_idx, c_afm[1, 2]]
        i += 1

    p = np.polyfit(skew_x_array[:, 0], skew_x_array[:, 1], poly_order)
    bias_funcs['skew_x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['skew_x'][poly_order] = p[poly_order]

    p = np.polyfit(scale_x_array[:, 0], scale_x_array[:, 1], poly_order)
    bias_funcs['scale_x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['scale_x'][poly_order] = p[poly_order]

    p = np.polyfit(scale_y_array[:, 0], scale_y_array[:, 1], poly_order)
    bias_funcs['scale_y'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['scale_y'][poly_order] = p[poly_order]

    p = np.polyfit(rot_array[:, 0], rot_array[:, 1], poly_order)
    bias_funcs['rot'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['rot'][poly_order] = p[poly_order]

    p = np.polyfit(x_array[:, 0], x_array[:, 1], poly_order)
    bias_funcs['x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['x'][poly_order] = p[poly_order]

    p = np.polyfit(y_array[:, 0], y_array[:, 1], poly_order)
    bias_funcs['y'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['y'][poly_order] = p[poly_order]

    logging.info("Bias Funcs: \n%s\n" % (str(bias_funcs)))

    logger.info('<<<< BiasFuncs')
    return bias_funcs


def ApplyBiasFuncs(align_list):
    logger.debug('ApplyBiasFuncs:')
    bias_funcs = BiasFuncs(align_list)
    c_afm_init = InitCafm(bias_funcs)
    bias_iters = 2
    for bi in range(bias_iters):
        c_afm = c_afm_init
        for item in align_list:
            align_idx = item['i']
            align_item = item['proc']
            bias_mat = BiasMat(align_idx, bias_funcs)
            c_afm = align_item.setCafm(c_afm, bias_mat=bias_mat)
        if bi < bias_iters - 1:
            bias_funcs = BiasFuncs(align_list, bias_funcs=bias_funcs)
    return c_afm_init



def InitCafm(bias_funcs):
    '''Get the initial c_afm from the constant terms of the bias_funcs'''
    logger.debug('InitCafm:')
    init_skew_x = -bias_funcs['skew_x'][-1]
    init_scale_x = 1.0 / bias_funcs['scale_x'][-1]
    init_scale_y = 1.0 / bias_funcs['scale_y'][-1]
    init_rot = -bias_funcs['rot'][-1]
    init_x = -bias_funcs['x'][-1]
    init_y = -bias_funcs['y'][-1]

    # Create skew, scale, rot, and tranlation matrices
    init_skew_x_mat = np.array([[1.0, init_skew_x, 0.0], [0.0, 1.0, 0.0]])
    init_scale_mat = np.array([[init_scale_x, 0.0, 0.0], [0.0, init_scale_y, 0.0]])
    init_rot_mat = np.array([[np.cos(init_rot), -np.sin(init_rot), 0.0], [np.sin(init_rot), np.cos(init_rot), 0.0]])
    init_trans_mat = np.array([[1.0, 0.0, init_x], [0.0, 1.0, init_y]])

    c_afm_init = identityAffine()

    # Compose bias matrix as skew*scale*rot*trans
    c_afm_init = composeAffine(init_skew_x_mat, c_afm_init)
    c_afm_init = composeAffine(init_scale_mat, c_afm_init)
    c_afm_init = composeAffine(init_rot_mat, c_afm_init)
    c_afm_init = composeAffine(init_trans_mat, c_afm_init)

    logger.info('<<<< InitCafm')
    return c_afm_init


def SetSingleCafm(layer_dict, c_afm, bias_mat=None):
    '''Calculate and set the value of the c_afm (with optional bias) for a single layer_dict item'''
    logger.debug('SetSingleCafm:')
    atrm = layer_dict['align_to_ref_method']
    try:
        afm = np.array(atrm['method_results']['affine_matrix'])
    except:
        # This was being triggered #0619
        logger.warning('SetSingleCafm triggered an exception Empty affine_matrix in base image, skipping: '
                       '%s' % (layer_dict['images']['base']['filename']))
        afm = identityAffine()
        atrm['method_results']['affine_matrix'] = afm.tolist()
    c_afm = np.array(c_afm)
    c_afm = composeAffine(afm, c_afm)
    # Apply bias_mat if given
    if type(bias_mat) != type(None):
        c_afm = composeAffine(bias_mat, c_afm)
    atrm['method_results']['cumulative_afm'] = c_afm.tolist()
    return c_afm


def SetStackCafm(scale_dict, null_biases=False):
    '''Calculate c_afm across the whole stack with optional bias correction'''
    logger.debug('SetStackCafm:')
    # To perform bias correction, first initialize Cafms without bias correction
    if null_biases == True:
        SetStackCafm(scale_dict, null_biases=False)
    al_stack = scale_dict['alignment_stack']
    # If null_biases==True, Iteratively determine and null out bias in c_afm
    bias_mat = None
    if null_biases:
        bias_funcs = BiasFuncs(al_stack, poly_order=scale_dict['poly_order'])
        c_afm_init = InitCafm(bias_funcs)
    else:
        c_afm_init = identityAffine()
    bias_iters = 2 if null_biases else 1
    for bi in range(bias_iters):
        c_afm = c_afm_init
        for align_idx in range(len(al_stack)):
            if null_biases:
                bias_mat = BiasMat(align_idx, bias_funcs)
            c_afm = SetSingleCafm(al_stack[align_idx], c_afm, bias_mat=bias_mat)
        if bi < bias_iters - 1:
            bias_funcs = BiasFuncs(al_stack, bias_funcs=bias_funcs)
    return c_afm_init


def BoundingRect(al_stack):
    '''Determine Bounding Rectangle for a stack of images'''
    logger.debug('BoundingRect:')
    model_bounds = None
    siz = get_image_size(al_stack[0]['images']['base']['filename'])
    for item in al_stack:
        c_afm = np.array(item['align_to_ref_method']['method_results']['cumulative_afm'])
        if type(model_bounds) == type(None):
            model_bounds = modelBounds2(c_afm, siz)
        else:
            model_bounds = np.append(model_bounds, modelBounds2(c_afm, siz), axis=0)
    border_width = max(0 - model_bounds[:, 0].min(),
                       0 - model_bounds[:, 1].min(),
                       model_bounds[:, 0].max() - siz[0],
                       model_bounds[:, 1].max() - siz[0])
    rect = [-border_width, -border_width, siz[0] + 2 * border_width, siz[0] + 2 * border_width]
    logger.info('Returning: %s' % str(rect))
    return rect


class UnknownImageFormat(Exception):
  pass


# def loadImage(ifn, stretch=False):
#   '''LOADIMAGE - Load an image for alignment work
#   img = LOADIMAGE(ifn) loads the named image, which can then serve as
#   either the “stationary” or the “moving” image.
#   Images are always converted to 8 bits. Optional second argument STRETCH
#   enables contrast stretching. STRETCH may be given as a percentage,
#   or simply as True, which implies 0.1%.
#   The current implementation can only read from the local file system.
#   Backends for http, DVID, etc., would be a useful extension.'''
#   logger.info('image_utils.loadImage >>>>')
#   if type(stretch) == bool and stretch:
#     stretch = 0.1
#   # img = cv2.imread(ifn, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)
#   img = tifffile.imread(ifn)  # 0720+
#   if stretch:
#     N = img.size
#     ilo = int(.01 * stretch * N)
#     ihi = int((1 - .01 * stretch) * N)
#     vlo = np.partition(img.reshape(N, ), ilo)[ilo]
#     vhi = np.partition(img.reshape(N, ), ihi)[ihi]
#     nrm = np.array([255.999 / (vhi - vlo)], dtype='float32')
#     img[img < vlo] = vlo
#     img = ((img - vlo) * nrm).astype('uint8')
#   logger.info('<<<< image_utils.loadImage')
#   return img
#
#
#
#
# def saveImage(img, ofn, qual=None, comp=1):
#   '''SAVEIMAGE - Save an image
#   SAVEIMAGE(img, ofn) saves the image IMG to the file named OFN.
#   Optional third argument specifies jpeg quality as a number between
#   0 and 100, and must only be given if OFN ends in ".jpg". Default
#   is 95.'''
#   logger.info('image_utils.saveImage >>>>')
#   if qual is None:
#     ext = os.path.splitext(ofn)[-1]
#     if (ext == '.tif') or (ext == '.tiff') or (ext == '.TIF') or (ext == '.TIFF'):
#       if comp != None:
#         # code 1 means uncompressed tif
#         # code 5 means LZW compressed tif
#         # cv2.imwrite(ofn, img, (cv2.IMWRITE_TIFF_COMPRESSION, comp))
#         tifffile.imwrite(ofn, img, bigtiff=True, dtype='uint8')
#       else:
#         # Use default
#         # cv2.imwrite(ofn, img)
#         tifffile.imwrite(ofn, img, bigtiff=True, dtype='uint8')
#     else:
#       # cv2.imwrite(ofn, img)
#       tifffile.imwrite(ofn, img, bigtiff=True, dtype='uint8')
#   else:
#     # cv2.imwrite(ofn, img, (cv2.IMWRITE_JPEG_QUALITY, qual))
#     tifffile.imwrite(ofn, img, bigtiff=True, dtype='uint8')
#   logger.info('<<<< image_utils.saveImage')
#
#
# class UnknownImageFormat(Exception):
#   pass