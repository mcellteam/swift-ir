#!/usr/bin/env python3
import copy, time
import os, struct, logging
from dataclasses import dataclass
import numpy as np
import imageio.v3 as iio
try:     from src.helpers import get_img_filenames
except:  from helpers import get_img_filenames
try:     import src.config as cfg
except:  import config as cfg

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

logger = logging.getLogger(__name__)

def imageio_read_image(img_path:str):
    '''
    Load A Single Image Into a Numpy Array
    :param image_path: Path to image on disk.
    :cur_method image_path: str
    :return: The image as a numpy array.
    :rtype: numpy.ndarray
    '''
    return iio.imread(img_path)

def get_size_image_size_imageio(path):
    '''
    Returns the size in pixels of the source images
    :return width: Width of the source images.
    :rtype width: int
    :return height: Height of the source images.
    :rtype height: int
    '''
    width, height = imageio_read_image(path).size
    #Todo finish this function
    return width, height


def ImageSize(file_path):
    '''Extract image dimensions given a file path using just
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

    # Create skew, s, rot, and tranlation matrices
    skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0], [0.0, 1.0, 0.0]])
    scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0], [0.0, scale_y_bias, 0.0]])
    rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0], [np.sin(rot_bias), np.cos(rot_bias), 0.0]])
    trans_bias_mat = np.array([[1.0, 0.0, x_bias], [0.0, 1.0, y_bias]])

    bias_mat = identityAffine()

    # Compose bias matrix as skew*s*rot*trans
    bias_mat = composeAffine(skew_x_bias_mat, bias_mat)
    bias_mat = composeAffine(scale_bias_mat, bias_mat)
    bias_mat = composeAffine(rot_bias_mat, bias_mat)
    bias_mat = composeAffine(trans_bias_mat, bias_mat)

    # logger.info('<<<< BiasMat')

    return bias_mat


# NEW
# Find the bias functions that best fit the trends in cafm across the whole stack
# For now the form of the functions is an Nth-order polynomial
def BiasFuncs(layerator, bias_funcs=None, poly_order=4):
    logger.debug('BiasFuncs:')
    poly_order = int(poly_order)
    n_tasks = sum(1 for _ in copy.deepcopy(layerator))
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

    skew_x_array = np.zeros((n_tasks, 2))
    scale_x_array = np.zeros((n_tasks, 2))
    scale_y_array = np.zeros((n_tasks, 2))
    rot_array = np.zeros((n_tasks, 2))
    x_array = np.zeros((n_tasks, 2))
    y_array = np.zeros((n_tasks, 2))

    # for align_idx in range(len(al_stack)):
    for i, layer in enumerate(layerator):
        c_afm = np.array(layer['alignment']['method_results']['cumulative_afm'])

        rot = np.arctan(c_afm[1, 0] / c_afm[0, 0])
        scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
        scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
        skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
        det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])

        skew_x_array[i]  = [i, skew_x]
        scale_x_array[i] = [i, scale_x]
        scale_y_array[i] = [i, scale_y]
        rot_array[i]     = [i, rot]
        x_array[i]       = [i, c_afm[0, 2]]
        y_array[i]       = [i, c_afm[1, 2]]

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

    logging.debug("init_scalars=%s\nReturning Biases: %s\n" % (str(init_scalars), str(bias_funcs)))

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
    init_skew_x = -bias_funcs['skew_x'][-1]
    init_scale_x = 1.0 / bias_funcs['scale_x'][-1]
    init_scale_y = 1.0 / bias_funcs['scale_y'][-1]
    init_rot = -bias_funcs['rot'][-1]
    init_x = -bias_funcs['x'][-1]
    init_y = -bias_funcs['y'][-1]

    # Create skew, s, rot, and tranlation matrices
    init_skew_x_mat = np.array([[1.0, init_skew_x, 0.0], [0.0, 1.0, 0.0]])
    init_scale_mat = np.array([[init_scale_x, 0.0, 0.0], [0.0, init_scale_y, 0.0]])
    init_rot_mat = np.array([[np.cos(init_rot), -np.sin(init_rot), 0.0], [np.sin(init_rot), np.cos(init_rot), 0.0]])
    init_trans_mat = np.array([[1.0, 0.0, init_x], [0.0, 1.0, init_y]])

    c_afm_init = identityAffine()

    # Compose bias matrix as skew*s*rot*trans
    c_afm_init = composeAffine(init_skew_x_mat, c_afm_init)
    c_afm_init = composeAffine(init_scale_mat, c_afm_init)
    c_afm_init = composeAffine(init_rot_mat, c_afm_init)
    c_afm_init = composeAffine(init_trans_mat, c_afm_init)

    logger.info('Returning: %s' % format_cafm(c_afm_init))

    return c_afm_init


def SetSingleCafm(layer_dict, c_afm, bias_mat=None):
    '''Calculate and set the value of the cafm (with optional bias) for a single layer_dict item'''
    atrm = layer_dict['alignment']
    try:
        afm = np.array(atrm['method_results']['affine_matrix'])
    except:
        logger.warning('SetSingleCafm triggered an exception Empty affine_matrix in base image, skipping: '
                       '%s' % (layer_dict['filename']))
        afm = identityAffine()
        atrm['method_results']['affine_matrix'] = afm.tolist()
    c_afm = np.array(c_afm)
    c_afm = composeAffine(afm, c_afm)
    # Apply bias_mat if given
    if type(bias_mat) != type(None):
        c_afm = composeAffine(bias_mat, c_afm)
    atrm['method_results']['cumulative_afm'] = c_afm.tolist()

    # logger.info('Returning c_afm: %s' % format_cafm(c_afm))

    return c_afm


def SetStackCafm(scale, null_biases=False, poly_order=None):
    '''Calculate cafm across the whole stack with optional bias correction'''
    if null_biases == True:
        # To perform bias correction, first initialize Cafms without bias correction
        SetStackCafm(scale=scale, null_biases=False)
    bias_mat = None
    if null_biases:
        # If null_biases==True, Iteratively determine and null out bias in cafm
        bias_funcs = BiasFuncs(cfg.data.get_iter(scale), poly_order=poly_order)
        c_afm_init = InitCafm(bias_funcs)
    else:
        c_afm_init = identityAffine()
    bias_iters = 2 if null_biases else 1
    for bi in range(bias_iters):
        c_afm = c_afm_init
        for i, layer in enumerate(cfg.data.get_iter(scale)):
            if null_biases:
                bias_mat = BiasMat(i, bias_funcs)
            c_afm = SetSingleCafm(layer, c_afm, bias_mat=bias_mat) # <class 'numpy.ndarray'>
            # if i in [0,1,2,n,n-1]:
            # logger.info('c_afm: %s' % format_cafm(c_afm))
            # cfg.datamodel.set_cafm(c_afm.tolist(), l=align_idx)

        if bi < bias_iters - 1:
            bias_funcs = BiasFuncs(cfg.data.get_iter(scale), bias_funcs=bias_funcs)

    return c_afm_init


def composeAffine(afm, bfm):
    '''COMPOSEAFFINE - Compose two affine transforms
    COMPOSEAFFINE(afm1, afm2) returns the affine transform AFM1 ∘ AFM2
    that applies AFM1 after AFM2.
    Affine matrices must be 2x3 numpy arrays.'''
    afm = np.vstack((afm, [0,0,1]))
    bfm = np.vstack((bfm, [0,0,1]))
    fm = np.matmul(afm, bfm)
    return fm[0:2,:]

def identityAffine():
    '''IDENTITYAFFINE - Return an idempotent affine transform
    afm = IDENTITYAFFINE() returns an affine transform that is
    an identity transform.'''
    return np.array([[1., 0., 0.],
                     [0., 1., 0.]])

def invertAffine(afm):
    '''INVERTAFFINE - Invert affine transform
    INVERTAFFINE(afm), where AFM is a 2x3 affine transformation matrix,
    returns the inverse transform.'''
    afm = np.vstack((afm, [0,0,1]))
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
    transform AFM.'''
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
    '''APPLYAFFINE - Apply affine transform to a point
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

# def ComputeBoundingRect(al_stack, s=None):
def ComputeBoundingRect(al_stack, scale=None):
    '''
    Determines Bounding Rectangle size for alignment stack. Must be preceded by a call to SetStackCafm.

    To get result for current s, in the main process, use:
    from src.image_funcs import ComputeBoundingRect, ImageSize
    ComputeBoundingRect(cfg.datamodel.stack())

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
    if scale == None: scale = cfg.data.scale

    if cfg.SUPPORT_NONSQUARE:
        '''Non-square'''
        # model_bounds = None
        # al_stack = cfg.datamodel.stack()
        model_bounds = [[0,0]] #Todo initialize this better
        siz = cfg.data.image_size(s=scale)
        for item in al_stack:
            c_afm = np.array(item['alignment']['method_results']['cumulative_afm'])
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
        siz = cfg.data.image_size(s=scale)
        for item in al_stack:
            c_afm = np.array(item['alignment']['method_results']['cumulative_afm'])
            if type(model_bounds) == type(None):
                model_bounds = modelBounds2(c_afm, siz)
            else:
                model_bounds = np.append(model_bounds, modelBounds2(c_afm, siz), axis=0)
        border_width = max(0 - model_bounds[:, 0].min(),
                           0 - model_bounds[:, 1].min(),
                           model_bounds[:, 0].max() - siz[0],
                           model_bounds[:, 1].max() - siz[0])
        rect = [int(-border_width), int(-border_width), int(siz[0] + 2 * border_width), int(siz[0] + 2 * border_width)]
        logger.info('ComputeBoundingRectangle Return: %s' % str(rect))

    # logger.critical('<<<< ComputeBoundingRect <<<<')
    return rect


def format_cafm(cafm):
    if isinstance(cafm, (np.ndarray, np.generic) ):
        cafm = cafm.tolist()
    cafm[0] = ['%.3f' % x for x in cafm[0]]
    cafm[1] = ['%.3f' % x for x in cafm[1]]
    return str(cafm)



'''
dataset = ts.open(
    spec,
    read=True,
    # context=context,
    dtype=ts.uint8,
    # shape=[5],
    open=True
).result()

dataset
Out[21]: 
TensorStore({
  'context': {
    'cache_pool': {},
    'data_copy_concurrency': {},
    'file_io_concurrency': {},
  },
  'driver': 'zarr',
  'dtype': 'uint8',
  'kvstore': {
    'driver': 'file',
    'path': '/Users/joelyancey/glanceem_swift/test_projects/test2_10imgs/scale_4.zarr/',
  },
  'metadata': {
    'chunks': [1, 512, 512],
    'compressor': {
      'blocksize': 0,
      'clevel': 5,
      'cname': 'lz4',
      'id': 'blosc',
      'shuffle': 1,
    },
    'dimension_separator': '.',
    'dtype': '|u1',
    'fill_value': 0,
    'filters': None,
    'order': 'C',
    'shape': [10, 1024, 1024],
    'zarr_format': 2,
  },
  'transform': {
    'input_exclusive_max': [[10], [1024], [1024]],
    'input_inclusive_min': [0, 0, 0],
  },
})



'''

# nicer_array = NicerTensorStore(spec=spec, open_kwargs={"write": True})
# store_arrays.append(nicer_array)

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



#
# def _generate_candidate_libs():
#     # look for likely library files in the following dirs:
#     lib_dirs = [os.path.dirname(__file__),
#                 '/lib',
#                 '/usr/lib',
#                 '/usr/local/lib',
#                 '/opt/local/lib',
#                 os.path.join(sys.prefix, 'lib'),
#                 os.path.join(sys.prefix, 'DLLs')
#                 ]
#     if 'HOME' in os.environ:
#         lib_dirs.append(os.path.join(os.environ['HOME'], 'lib'))
#     lib_dirs = [ld for ld in lib_dirs if os.path.exists(ld)]
#
#     lib_names = ['libfreeimage', 'freeimage']  # should be lower-case!
#     # Now attempt to find libraries of that name in the given directory
#     # (case-insensitive and without regard for extension)
#     lib_paths = []
#     for lib_dir in lib_dirs:
#         for lib_name in lib_names:
#             files = os.listdir(lib_dir)
#             lib_paths += [os.path.join(lib_dir, lib) for lib in files
#                            if lib.lower().startswith(lib_name) and not
#                            os.path.splitext(lib)[1] in ('.py', '.pyc', '.ini')]
#     lib_paths = [lp for lp in lib_paths if os.path.exists(lp)]
#
#     return lib_dirs, lib_paths
#
# def load_freeimage():
#     if sys.platform == 'win32':
#         loader = ctypes.windll
#         functype = ctypes.WINFUNCTYPE
#     else:
#         loader = ctypes.cdll
#         functype = ctypes.CFUNCTYPE
#
#     freeimage = None
#     errors = []
#     # First try a few bare library names that ctypes might be able to find
#     # in the default locations for each platform. Win DLL names don't need the
#     # extension, but other platforms do.
#     bare_libs = ['FreeImage', 'libfreeimage.dylib', 'libfreeimage.so',
#                 'libfreeimage.so.3']
#     lib_dirs, lib_paths = _generate_candidate_libs()
#     lib_paths = bare_libs + lib_paths
#     for lib in lib_paths:
#         try:
#             freeimage = loader.LoadLibrary(lib)
#             break
#         except Exception:
#             if lib not in bare_libs:
#                 # Don't record errors when it couldn't load the library from
#                 # a bare name -- this fails often, and doesn't provide any
#                 # useful debugging information anyway, beyond "couldn't find
#                 # library..."
#                 # Get exception instance in Python 2.x/3.x compatible manner
#                 e_type, e_value, e_tb = sys.exc_info()
#                 del e_tb
#                 errors.append((lib, e_value))
#
#     if freeimage is None:
#         if errors:
#             # No freeimage library loaded, and load-errors reported for some
#             # candidate libs
#             err_txt = ['%s:\n%s' % (l, str(e.message)) for l, e in errors]
#             raise RuntimeError('One or more FreeImage libraries were found, but '
#                                'could not be loaded due to the following errors:\n'
#                                '\n\n'.join(err_txt))
#         else:
#             # No errors, because no potential libraries found at all!
#             raise RuntimeError('Could not find a FreeImage library in any of:\n' +
#                                '\n'.join(lib_dirs))
#
#     # FreeImage found
#     @functype(None, ctypes.c_int, ctypes.c_char_p)
#     def error_handler(fif, message):
#         raise RuntimeError('FreeImage error: %s' % message)
#
#     freeimage.FreeImage_SetOutputMessage(error_handler)
#     return freeimage
#
# _FI = load_freeimage()
#
# def write_multipage(arrays, filename, flags=0):
#     """Write a list of (height, width) or (height, width, nchannels)
#     arrays to a multipage greyscale, RGB, or RGBA image, with file cur_method
#     deduced from the filename.
#     The `flags` parameter should be one or more values from the IO_FLAGS
#     class defined in this module, or-ed together with | as appropriate.
#     (See the source-code comments for more details.)
#     """
#
#     filename = asbytes(filename)
#     ftype = _FI.FreeImage_GetFIFFromFilename(filename)
#     if ftype == -1:
#         raise ValueError('Cannot determine cur_method of file %s' % filename)
#     create_new = True
#     read_only = False
#     keep_cache_in_memory = True
#     multibitmap = _FI.FreeImage_OpenMultiBitmap(ftype, filename,
#                                                 create_new, read_only,
#                                                 keep_cache_in_memory, 0)
#     if not multibitmap:
#         raise ValueError('Could not open %s for writing multi-page image.' %
#                          filename)
#     try:
#         for array in arrays:
#             array = np.asarray(array)
#             bitmap, fi_type = _array_to_bitmap(array)
#             _FI.FreeImage_AppendPage(multibitmap, bitmap)
#     finally:
#         _FI.FreeImage_CloseMultiBitmap(multibitmap, flags)
#
# # 4-byte quads of 0,v,v,v from 0,0,0,0 to 0,255,255,255
# _GREY_PALETTE = np.arange(0, 0x01000000, 0x00010101, dtype=np.uint32)
#
#
# def _array_to_bitmap(array):
#     """Allocate a FreeImage bitmap and copy a numpy array into it.
#     """
#     shape = array.shape
#     dtype = array.dtype
#     r, c = shape[:2]
#     if len(shape) == 2:
#         n_channels = 1
#         w_shape = (c, r)
#     elif len(shape) == 3:
#         n_channels = shape[2]
#         w_shape = (n_channels, c, r)
#     else:
#         n_channels = shape[0]
#     try:
#         fi_type = FI_TYPES.fi_types[(dtype, n_channels)]
#     except KeyError:
#         raise ValueError('Cannot write arrays of given cur_method and shape.')
#
#     itemsize = array.dtype.itemsize
#     bpp = 8 * itemsize * n_channels
#     bitmap = _FI.FreeImage_AllocateT(fi_type, c, r, bpp, 0, 0, 0)
#     bitmap = ctypes.c_void_p(bitmap)
#     if not bitmap:
#         raise RuntimeError('Could not allocate image for storage')
#     try:
#         def n(arr):  # normalise to freeimage's in-memory format
#             return arr.T[:, ::-1]
#         wrapped_array = _wrap_bitmap_bits_in_array(bitmap, w_shape, dtype)
#         # swizzle the color components and flip the scanlines to go to
#         # FreeImage's BGR[A] and upside-down internal memory format
#         if len(shape) == 3 and _FI.FreeImage_IsLittleEndian() and \
#                dtype.cur_method == np.uint8:
#             wrapped_array[0] = n(array[:, :, 2])
#             wrapped_array[1] = n(array[:, :, 1])
#             wrapped_array[2] = n(array[:, :, 0])
#             if shape[2] == 4:
#                 wrapped_array[3] = n(array[:, :, 3])
#         else:
#             wrapped_array[:] = n(array)
#         if len(shape) == 2 and dtype.cur_method == np.uint8:
#             palette = _FI.FreeImage_GetPalette(bitmap)
#             palette = ctypes.c_void_p(palette)
#             if not palette:
#                 raise RuntimeError('Could not get image palette')
#             ctypes.memmove(palette, _GREY_PALETTE.ctypes.datamodel, 1024)
#         return bitmap, fi_type
#     except:
#         _FI.FreeImage_Unload(bitmap)
#         raise
#
# def _wrap_bitmap_bits_in_array(bitmap, shape, dtype):
#     """Return an ndarray webengineview on the datamodel in a FreeImage bitmap. Only
#     valid for as long as the bitmap is loaded (if single page) / locked
#     in memory (if multipage).
#     """
#     pitch = _FI.FreeImage_GetPitch(bitmap)
#     height = shape[-1]
#     byte_size = height * pitch
#     itemsize = dtype.itemsize
#
#     if len(shape) == 3:
#         strides = (itemsize, shape[0] * itemsize, pitch)
#     else:
#         strides = (itemsize, pitch)
#     bits = _FI.FreeImage_GetBits(bitmap)
#     array = np.ndarray(shape, dtype=dtype,
#                           buffer=(ctypes.c_char * byte_size).from_address(bits),
#                           strides=strides)
#     return array
#
#
# class FI_TYPES(object):
#     FIT_UNKNOWN = 0
#     FIT_BITMAP = 1
#     FIT_UINT16 = 2
#     FIT_INT16 = 3
#     FIT_UINT32 = 4
#     FIT_INT32 = 5
#     FIT_FLOAT = 6
#     FIT_DOUBLE = 7
#     FIT_COMPLEX = 8
#     FIT_RGB16 = 9
#     FIT_RGBA16 = 10
#     FIT_RGBF = 11
#     FIT_RGBAF = 12
#
#     dtypes = {
#         FIT_BITMAP: np.uint8,
#         FIT_UINT16: np.uint16,
#         FIT_INT16: np.int16,
#         FIT_UINT32: np.uint32,
#         FIT_INT32: np.int32,
#         FIT_FLOAT: np.float32,
#         FIT_DOUBLE: np.float64,
#         FIT_COMPLEX: np.complex128,
#         FIT_RGB16: np.uint16,
#         FIT_RGBA16: np.uint16,
#         FIT_RGBF: np.float32,
#         FIT_RGBAF: np.float32
#         }
#
#     fi_types = {
#         (np.dtype('uint8'), 1): FIT_BITMAP,
#         (np.dtype('uint8'), 3): FIT_BITMAP,
#         (np.dtype('uint8'), 4): FIT_BITMAP,
#         (np.dtype('uint16'), 1): FIT_UINT16,
#         (np.dtype('int16'), 1): FIT_INT16,
#         (np.dtype('uint32'), 1): FIT_UINT32,
#         (np.dtype('int32'), 1): FIT_INT32,
#         (np.dtype('float32'), 1): FIT_FLOAT,
#         (np.dtype('float64'), 1): FIT_DOUBLE,
#         (np.dtype('complex128'), 1): FIT_COMPLEX,
#         (np.dtype('uint16'), 3): FIT_RGB16,
#         (np.dtype('uint16'), 4): FIT_RGBA16,
#         (np.dtype('float32'), 3): FIT_RGBF,
#         (np.dtype('float32'), 4): FIT_RGBAF
#         }
#
#     extra_dims = {
#         FIT_UINT16: [],
#         FIT_INT16: [],
#         FIT_UINT32: [],
#         FIT_INT32: [],
#         FIT_FLOAT: [],
#         FIT_DOUBLE: [],
#         FIT_COMPLEX: [],
#         FIT_RGB16: [3],
#         FIT_RGBA16: [4],
#         FIT_RGBF: [3],
#         FIT_RGBAF: [4]
#         }
#
#     @classmethod
#     def get_type_and_shape(cls, bitmap):
#         w = _FI.FreeImage_GetWidth(bitmap)
#         h = _FI.FreeImage_GetHeight(bitmap)
#         fi_type = _FI.FreeImage_GetImageType(bitmap)
#         if not fi_type:
#             raise ValueError('Unknown image pixel cur_method')
#         dtype = cls.dtypes[fi_type]
#         if fi_type == cls.FIT_BITMAP:
#             bpp = _FI.FreeImage_GetBPP(bitmap)
#             if bpp == 8:
#                 extra_dims = []
#             elif bpp == 24:
#                 extra_dims = [3]
#             elif bpp == 32:
#                 extra_dims = [4]
#             else:
#                 raise ValueError('Cannot convert %d BPP bitmap' % bpp)
#         else:
#             extra_dims = cls.extra_dims[fi_type]
#         return np.dtype(dtype), extra_dims + [w, h]
#





# def prepare_tensorstore_from_pyramid(
#     pyr: Sequence[DataArray],
#     level_names: Sequence[str],
#     jpeg_quality: int,
#     output_chunks: Sequence[int],
#     root_container_path: Path,
# ):
#     store_arrays = []
#     # sharding = {'@cur_method': 'neuroglancer_uint64_sharded_v1',
#     #       'preshift_bits': 9,
#     #        'hash': 'identity',
#     #        'minishard_index_encoding': 'gzip',
#     #       'minishard_bits': 6,
#     #       'shard_bits': 15}
#
#     for p, ln in zip(pyr, level_names):
#         res = [abs(float(p.coords[k][1] - p.coords[k][0])) for k in p.dims]
#         spec: Dict[str, Any] = {
#             "driver": "neuroglancer_precomputed",
#             "kvstore": {
#                 "driver": "file",
#                 "path": str(Path(root_container_path).parent),
#             },
#             "path": root_container_path.parts[-1],
#             "scale_metadata": {
#                 "size": p.shape,
#                 "resolution": res,
#                 "encoding": "jpeg",
#                 "jpeg_quality": jpeg_quality,
#                 #'sharding': sharding,
#                 "chunk_size": output_chunks,
#                 "key": ln,
#                 "voxel_offset": (0, 0, 0),
#             },
#             "multiscale_metadata": {
#                 "data_type": p.dtype.name,
#                 "num_channels": 1,
#                 "cur_method": "image",
#             },
#         }
#         try:
#             ts.open(spec=spec, open=True).result()
#         except ValueError:
#             try:
#                 ts.open(spec=spec, create=True).result()
#             except ValueError:
#                 ts.open(spec=spec, create=True, delete_existing=True).result()
#
#         nicer_array = NicerTensorStore(spec=spec, open_kwargs={"write": True})
#         store_arrays.append(nicer_array)
#     return store_arrays


# @dataclass
# class NicerTensorStore:
#     spec: Dict[str, Any]
#     open_kwargs: Dict[str, Any]
#
#     def __getitem__(self, slices):
#         return ts.open(spec=self.spec, **self.open_kwargs).result()[slices]
#
#     def __setitem__(self, slices, values):
#         ts.open(spec=self.spec, **self.open_kwargs).result()[ts.d["channel"][0]][
#             slices
#         ] = values
#         return None

'''
https://programtalk.com/vs4/python/janelia-cosem/fibsem-tools/src/fibsem_tools/io/tensorstore.py/
'''

