#!/usr/bin/env python3
import inspect
import logging
import os
import struct
from dataclasses import dataclass

import imagecodecs
import numpy as np

from src.utils.helpers import print_exception

try:
    import src.config as cfg
except:
    import config as cfg

__all__ = [
    'ImageSize',
    'BiasMat',
    'BiasFuncs',
    'ApplyBiasFuncs',
    'InitCafm',
    'SetSingleCafm',
    'SetStackCafm',
    'ComputeBoundingRect',
    'invertAffine',
]

debug_level = 0
_set_stack_calls = 0

logger = logging.getLogger(__name__)

def imread(filename):
    # return first image in TIFF file as numpy array
    with open(filename, 'rb') as fh:
        data = fh.read()
    return imagecodecs.tiff_decode(data)




def ImageSize(file_path):
    '''Extract image dimensions given a file file_path using just
    core modules os and struct

    moduleauthor:: Tom Bartol - stripped down to bare bones
    moduleauthor:: Paulo Scardine - based on code by Emmanuel Vaisse
    :param file_path: The image to get size of.
    :cur_method file_path: str.
    :returns:  (width, height) for a given img file content
    :rtype: (int, int)
    '''
    size = os.path.getsize(file_path)

    with open(file_path, 'rb') as input:
        '''Determine the image type of fhandle and return its size.'''
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
            # maps TIFF cur_method id to size (in bytes)
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
                9: (4, boChar + "z"),  # SLONG
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
                # 2 bytes: TagId + 2 bytes: cur_method + 4 bytes: count of values + 4
                # bytes: value offset
                ifdEntrySize = 12
                for i in range(ifdEntryCount):
                    entryOffset = ifdOffset + countSize + i * ifdEntrySize
                    input.seek(entryOffset)
                    tag = input.read(2)
                    tag = struct.unpack(boChar + "H", tag)[0]
                    if (tag == 256 or tag == 257):
                        # if cur_method indicates that value fits into 4 bytes, value
                        # offset is not an offset but value itself
                        type = input.read(2)
                        type = struct.unpack(boChar + "H", type)[0]
                        if type not in tiffTypes:
                            raise UnknownImageFormat(
                                "Unkown TIFF field cur_method:" +
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
                msg = ' in file_path: ' + str(file_path)
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
    try:
        logger.debug('Returning: %d x %d' % (width,height))
    except:
        logger.warning('Returning: ? - ImageSize has a problem')
    return width, height

class UnknownImageFormat(Exception):
  pass

# Return the bias matrix at position x in the stack as given by the bias_funcs
def BiasMat(x, bias_funcs):
    logger.debug('BiasMat:')

    #  xdot = np.array([4.0,3.0,2.0,1.0])

    poly_order = len(bias_funcs['x']) - 1
    xdot = np.arange(poly_order, 0, -1, dtype='float64')

    p = bias_funcs['scale_x']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    scale_x_bias = 1 - fdp(x)  # scale_x is multiplicative

    p = bias_funcs['scale_y']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    scale_y_bias = 1 - fdp(x)  # scale_y is multiplicative

    p = bias_funcs['skew_x']
    dp = p[:-1] * xdot
    fdp = np.poly1d(dp)
    skew_x_bias = -fdp(x)
   
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

    # Create scale, skew, rot, and translation matrices
    scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0], [0.0, scale_y_bias, 0.0]])
    skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0], [0.0, 1.0, 0.0]])
    rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0], [np.sin(rot_bias), np.cos(rot_bias), 0.0]])
    trans_bias_mat = np.array([[1.0, 0.0, x_bias], [0.0, 1.0, y_bias]])

    bias_mat = identityAffine()

    # Compose bias matrix as trans*rot*skew*scale with pre-multiplication (i.e. left action)
    bias_mat = composeAffine(scale_bias_mat, bias_mat)
    bias_mat = composeAffine(skew_x_bias_mat, bias_mat)
    bias_mat = composeAffine(rot_bias_mat, bias_mat)
    bias_mat = composeAffine(trans_bias_mat, bias_mat)

    # logger.info('<<<< BiasMat')

    return bias_mat



# NEW
# Find the bias functions that best fit the trends in cafm across the whole stack
# For now the form of the functions is an Nth-order polynomial
# def BiasFuncs(layerator, bias_funcs=None, poly_order=4):
def BiasFuncs(dm, scale, poly_order=0, bias_funcs=None):
    poly_order = int(poly_order)
    # n_tasks = sum(1 for _ in copy.deepcopy(layerator))
    n_tasks = len(dm)
    if type(bias_funcs) == type(None):
        init_scalars = True
        bias_funcs = {}
        bias_funcs['scale_x'] = np.zeros((poly_order + 1))
        bias_funcs['scale_y'] = np.zeros((poly_order + 1))
        bias_funcs['skew_x'] = np.zeros((poly_order + 1))
        bias_funcs['rot'] = np.zeros((poly_order + 1))
        bias_funcs['x'] = np.zeros((poly_order + 1))
        bias_funcs['y'] = np.zeros((poly_order + 1))
    else:
        init_scalars = False
        poly_order = len(bias_funcs['x']) - 1

    scale_x_array = np.zeros((n_tasks, 2))
    scale_y_array = np.zeros((n_tasks, 2))
    skew_x_array = np.zeros((n_tasks, 2))
    rot_array = np.zeros((n_tasks, 2))
    x_array = np.zeros((n_tasks, 2))
    y_array = np.zeros((n_tasks, 2))

    # for align_idx in range(len(al_stack)):
    for i, layer in enumerate(dm()):
        c_afm = np.array(layer['levels'][scale]['alt_cafm'])

        # Decompose the affine matrix into scale, skew, rotation, and translation
        rot = np.arctan2(c_afm[1, 0], c_afm[0, 0])
        # scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
        # scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
        # skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
        # calculations that avoid using sin and cos:
        scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
        scale_y = ((c_afm[1, 1] * c_afm[0,0]) - (c_afm[0, 1] * c_afm[1, 0])) / scale_x
        skew_x = ((c_afm[0, 0] * c_afm[0, 1]) + (c_afm[1, 0] * c_afm[1, 1])) / (scale_x * scale_y)
        det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])

        scale_x_array[i] = [i, scale_x]
        scale_y_array[i] = [i, scale_y]
        skew_x_array[i]  = [i, skew_x]
        rot_array[i]     = [i, rot]
        x_array[i]       = [i, c_afm[0, 2]]
        y_array[i]       = [i, c_afm[1, 2]]

    p = np.polyfit(scale_x_array[:, 0], scale_x_array[:, 1], poly_order)
    bias_funcs['scale_x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['scale_x'][poly_order] = p[poly_order]

    p = np.polyfit(scale_y_array[:, 0], scale_y_array[:, 1], poly_order)
    bias_funcs['scale_y'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['scale_y'][poly_order] = p[poly_order]

    p = np.polyfit(skew_x_array[:, 0], skew_x_array[:, 1], poly_order)
    bias_funcs['skew_x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['skew_x'][poly_order] = p[poly_order]

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

    logging.info("init_scalars=%s\nReturning Biases: %s\n" % (str(init_scalars), str(bias_funcs)))

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
            logger.info('\ncafm = %s' % format_cafm(c_afm))
        if bi < bias_iters - 1:
            bias_funcs = BiasFuncs(align_list, bias_funcs=bias_funcs)
    return c_afm_init


def InitCafm(bias_funcs):
    '''Get the initial cafm from the constant terms of the bias_funcs'''
    init_scale_x = 1.0 / bias_funcs['scale_x'][-1]
    init_scale_y = 1.0 / bias_funcs['scale_y'][-1]
    init_skew_x = -bias_funcs['skew_x'][-1]
    init_rot = -bias_funcs['rot'][-1]
    init_x = -bias_funcs['x'][-1]
    init_y = -bias_funcs['y'][-1]

    # Create scale, skew, rot, and translation matrices
    init_scale_mat = np.array([[init_scale_x, 0.0, 0.0], [0.0, init_scale_y, 0.0]])
    init_skew_x_mat = np.array([[1.0, init_skew_x, 0.0], [0.0, 1.0, 0.0]])
    init_rot_mat = np.array([[np.cos(init_rot), -np.sin(init_rot), 0.0], [np.sin(init_rot), np.cos(init_rot), 0.0]])
    init_trans_mat = np.array([[1.0, 0.0, init_x], [0.0, 1.0, init_y]])

    c_afm_init = identityAffine()

    # Compose bias matrix as trans*rot*scale*skew with pre-multiplication (i.e. left action)
    c_afm_init = composeAffine(init_scale_mat, c_afm_init)
    c_afm_init = composeAffine(init_skew_x_mat, c_afm_init)
    c_afm_init = composeAffine(init_rot_mat, c_afm_init)
    c_afm_init = composeAffine(init_trans_mat, c_afm_init)

    logger.info('Returning: %s' % format_cafm(c_afm_init))

    return c_afm_init




# def SetSingleCafm(d, scale, c_afm, bias_mat=None, method='grid'):
def SetSingleCafm(dm, scale, index, c_afm, include, bias_mat=None, method='grid'):
    '''Calculate and set the value of the cafm (with optional bias) for a single section data dict'''
    # atrm = layer_dict['alignment']
    try:
        if include:
            # afm = np.array(d['levels'][scale]['results']['affine_matrix'])
            afm = np.array(dm.afm(s=scale, l=index))
        else:

            afm = identityAffine()
    except:
        logger.warning(f"afm not found for index: {index}")
        afm = identityAffine()
    c_afm = np.array(c_afm)
    try:
        c_afm = composeAffine(afm, c_afm)
    except Exception as e:
        logger.warning(f'[{index}] Failed to compose affine, setting to identity matrix. Reason: {e.__class__.__name__}')
        c_afm = identityAffine()
    # Apply bias_mat if given
    if type(bias_mat) != type(None):
        c_afm = composeAffine(bias_mat, c_afm)
    dm['stack'][index]['levels'][scale]['cafm'] = c_afm.tolist()
    # dm['stack'][index]['levels'][scale]['afm'] = afm.tolist()
    # logger.info('Returning c_afm: %level' % format_cafm(c_afm))
    return c_afm




# def SetStackCafm(iterator, level, poly_order=None):
def SetStackCafm(dm, scale, poly_order=None):
    '''Calculate cafm across the whole stack with optional bias correction'''
    caller = inspect.stack()[1].function
    global _set_stack_calls
    _set_stack_calls +=1
    logger.critical(f'[{caller}] Setting Stack CAFM (call # {_set_stack_calls})...')

    # logger.info(f'Setting Stack CAFM (iterator={str(iterator)}, level={level}, poly_order={poly_order})...')
    # cfg.mw.tell('<span style="color: #FFFF66;"><b>Setting Stack CAFM...</b></span>')
    # cfg.mw.tell('Setting Stack CAFM...')
    use_poly = (poly_order != None)
    if use_poly:
        SetStackCafm(dm, scale=scale, poly_order=None) # first initializeStack Cafms without bias correction
    bias_mat = None
    if use_poly:
        # If null_biases==True, Iteratively determine and null out bias in cafm
        bias_funcs = BiasFuncs(dm, scale, poly_order=poly_order)
        c_afm_init = InitCafm(bias_funcs)
    else:
        c_afm_init = identityAffine()

    bias_iters = (1,2)[use_poly]
    for bi in range(bias_iters):
        # logger.critical(f'\n\nbi = {bi}\n')
        c_afm = c_afm_init
        for i, d in enumerate(dm()):
            # try:
            #     # assert 'affine_matrix' in d['levels'][scale]['results']
            #     cfg.pt.ht.haskey()
            # except AssertionError as e:
            #     logger.error(f"AssertionError, section #{i}: {str(e)}")
            #     break
            if use_poly:
                bias_mat = BiasMat(i, bias_funcs)
            # method = d['levels'][scale]['swim_settings']['method_opts']['method']
            method = d['levels'][scale]['swim_settings']['method_opts']['method']
            include = dm['stack'][i]['levels'][scale]['swim_settings']['include']
            # include = dm['stack'][i]['levels'][scale]['swim_settings']['include'] #1129
            c_afm = SetSingleCafm(dm, scale, i, c_afm, include, bias_mat=bias_mat, method=method) # <class
            # 'numpy.ndarray'>

        if bi < bias_iters - 1:
            bias_funcs = BiasFuncs(dm, scale, bias_funcs=bias_funcs, poly_order=poly_order)

    cfg.mw.hud.done()
    return c_afm_init,




def hashstring(text:str):
    hash=0
    for ch in text:
        hash = ( hash*281  ^ ord(ch)*997) & 0xFFFFFFFF
    return hash

def composeAffine(afm, bfm):
    '''COMPOSEAFFINE - Compose two affine transforms
    COMPOSEAFFINE(afm1, afm2) returns the affine generate_thumbnail AFM1 ∘ AFM2
    that applies AFM1 after AFM2.
    Affine matrices must be 2x3 numpy arrays.'''
    afm = np.vstack((afm, [0., 0., 1.]))
    bfm = np.vstack((bfm, [0., 0., 1.]))
    fm = np.matmul(afm, bfm)
    # fm = np.matmul(bfm, afm)
    return fm[0:2,:]



def identityAffine():
    '''IDENTITYAFFINE - Return an idempotent affine generate_thumbnail
    afm = IDENTITYAFFINE() returns an affine generate_thumbnail that is
    an identity generate_thumbnail.'''
    return np.array([[1., 0., 0.],
                     [0., 1., 0.]])

def invertAffine(afm):
    '''INVERTAFFINE - Invert affine generate_thumbnail
    INVERTAFFINE(afm), where AFM is a 2x3 affine transformation matrix,
    returns the inverse generate_thumbnail.'''
    afm = np.vstack((afm, [0., 0., 1.]))
    ifm = np.linalg.inv(afm)
    return ifm[0:2,:]

def si_unpackSize(siz):
    '''SI_UNPACKSIZE - Interprets size arguments
    Sizes are rounded up to next even number. Size may be given as one
    or two numbers. Unpacks to tuple.'''
    if type(siz)==np.ndarray or type(siz)==list or type(siz)==tuple:
        w = siz[0]
        h = siz[-1]
    else:
        w = h = siz
    if w % 2:
        w += 1
    if h % 2:
        h += 1
    return (w, h)

def modelBounds2(afm, siz):
    '''MODELBOUNDS - Returns a bounding rectangle in previewmodel space
    (x0, y0, w, h) = MODELBOUNDS(afm, siz) returns the bounding rectangle
    of an input rectangle (siz) in previewmodel space if pixel lookup is through affine
    generate_thumbnail AFM.'''
    inv = invertAffine(afm)
    w, h = si_unpackSize(siz)
    c = [applyAffine(inv, [0, 0])]
    c = np.append(c,[applyAffine(inv, [w, 0])],axis=0)
    c = np.append(c,[applyAffine(inv, [0, h])],axis=0)
    c = np.append(c,[applyAffine(inv, [w, h])],axis=0)
    c_min = [np.floor(c[:,0].min()).astype('int32'), np.floor(c[:,1].min()).astype('int32')]
    c_max = [np.ceil(c[:,0].max()).astype('int32'), np.ceil(c[:,1].max()).astype('int32')]
    return np.array([c_min, c_max])

def applyAffine(afm, xy):
    '''APPLYAFFINE - Apply affine generate_thumbnail to a point
    xy_ = APPLYAFFINE(afm, xy) applies the affine matrix AFM to the point XY
    Affine matrix must be a 2x3 numpy array. XY may be a list or an array.'''
    if not type(xy)==np.ndarray:
        xy = np.array([xy[0], xy[1]])
    return np.matmul(afm[0:2,0:2], xy) + reptoshape(afm[0:2,2], xy)

def reptoshape(mat, pattern):
    '''REPTOSHAPE - Repeat a matrix to match shape of other matrix
    REPTOSHAPE(mat, pattern) returns a copy of the matrix MAT replicated
    to match the shape of PATTERNS. For instance, if MAT is an N-vector
    or an Nx1 matrix, and PATTERN is NxK, the output will be an NxK matrix
    of which each the columns is filled with the contents of MAT.
    Higher dimensional cases are handled as well, but non-singleton dimensions
    of MAT must always match the corresponding dimension of PATTERN.'''
    ps = [x for x in pattern.shape]
    ms = [x for x in mat.shape]
    while len(ms)<len(ps):
        ms.append(1)
    mat = np.reshape(mat, ms)
    for d in range(len(ps)):
        if ms[d]==1:
            mat = np.repeat(mat, ps[d], d)
        elif ms[d] != ps[d]:
            raise ValueError('Cannot broadcast'  + str(mat.shape) + ' to '
                             + str(pattern.shape))
    return mat

# def ComputeBoundingRect(al_stack, level=None):
def ComputeBoundingRect(dm, scale=None):
    '''
    Determines Bounding Rectangle size for alignment stack. Must be preceded by a call to SetStackCafm.

    To get result for current level, in the main process, use:
    from src.image_funcs import ComputeBoundingRect, ImageSize
    ComputeBoundingRect(dm.stack())

    model_bounds example:
AlignEM [29]:
array([[   0,    0],
       [1024,  512],
       [  -5,   -5],
       [1026,  495],
       [  -9,   14],
       [1008,  508],
       [ -14,   29],
       [1006,  523],
       [  -6,   35],
       [1012,  532],
       [  -7,   37],
        ...
       [1022,  569],
       [   1,   76],
       [1014,  565],
       [  -2,   77],
       [1011,  565],
       [   9,   85],
       [1011,  570],
       [   6,   76],
       [1003,  561],
       [   6,   79],
       [ 994,  576],
       [   9,   80],
       [ 997,  580]], dtype=int32)
    '''
    logger.info('Computing Bounding Rect...')
    if scale == None: scale = dm.level

    if cfg.SUPPORT_NONSQUARE:
        '''Non-square'''
        # model_bounds = None
        model_bounds = [[0,0]] #Todo initializeStack this better
        siz = dm.image_size(s=scale)
        for item in dm():
            # method = item['levels'][scale]['swim_settings']['method_opts']['method']
            c_afm = np.array(item['levels'][scale]['cafm'])
            model_bounds = np.append(model_bounds, modelBounds2(c_afm, siz), axis=0)
        border_width_x = max(0 - model_bounds[:, 0].min(), model_bounds[:, 0].max() - siz[0])
        border_width_y = max(0 - model_bounds[:, 1].min(), model_bounds[:, 1].max() - siz[1])
        rect = [int(-border_width_x),
                int(-border_width_y),
                int(siz[0] + 2 * border_width_x),
                int(siz[1] + 2 * border_width_y)]
        logger.debug('Returning: %s' % str(rect))
    else:
        '''Old code/square only'''
        model_bounds = None
        siz = dm.image_size(s=scale)
        for item in dm():
            c_afm = np.array(item['levels'][scale]['cafm'])
            if type(model_bounds) == type(None):
                model_bounds = modelBounds2(c_afm, siz)
            else:
                model_bounds = np.append(model_bounds, modelBounds2(c_afm, siz), axis=0)
        border_width = max(0 - model_bounds[:, 0].min(),
                           0 - model_bounds[:, 1].min(),
                           model_bounds[:, 0].max() - siz[0],
                           model_bounds[:, 1].max() - siz[0])
        rect = (int(-border_width), int(-border_width), int(siz[0] + 2 * border_width), int(siz[0] + 2 * border_width))
        logger.critical('ComputeBoundingRectangle Return: %s' % str(rect))

    # logger.critical('<<<< ComputeBoundingRect <<<<')
    return rect


def format_cafm(cafm):
    if isinstance(cafm, (np.ndarray, np.generic) ):
        cafm = cafm.tolist()
    cafm[0] = ['%.3f' % x for x in cafm[0]]
    cafm[1] = ['%.3f' % x for x in cafm[1]]
    return str(cafm)






@dataclass
class StripNullFields:
    def asdict(self):
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                if hasattr(v, "asdict"):
                    result[k] = v.asdict()
                elif isinstance(v, list):
                    result[k] = []
                    for element in v:
                        if hasattr(element, "asdict"):
                            result[k].append(element.asdict())
                        else:
                            result[k].append(element)
                else:
                    result[k] = v
        return result









