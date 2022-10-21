#!/usr/bin/env python3

import os, struct, logging
from dataclasses import dataclass
import imageio.v3 as iio
import numpy as np
# from PIL import Image
# import tifffile
try:     from src.helpers import get_img_filenames
except:  from helpers import get_img_filenames
try:     from src.swiftir import composeAffine, identityAffine, invertAffine, modelBounds2
except:  from swiftir import composeAffine, identityAffine, invertAffine, modelBounds2
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
    'BoundingRect',
    'invertAffine',
]

debug_level = 0

logger = logging.getLogger(__name__)

def imageio_read_image(img_path:str):
    '''
    Load A Single Image Into a Numpy Array
    :param image_path: Path to image on disk.
    :type image_path: str
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
    :type file_path: str.
    :returns:  (width, height) for a given img file content
    :rtype: (int, int)
    '''
    logger.debug('ImageSize:')
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
    logger.critical('Setting Stack CAFM...')
    # To perform bias correction, first initialize Cafms without bias correction
    if null_biases == True:
        SetStackCafm(scale_dict, null_biases=False)
    al_stack = scale_dict['alignment_stack']
    # If null_biases==True, Iteratively determine and null out bias in c_afm
    bias_mat = None
    if null_biases:
        # bias_funcs = BiasFuncs(al_stack, poly_order=scale_dict['poly_order'])  # <-- #1020-
        bias_funcs = BiasFuncs(al_stack, poly_order=int(scale_dict['poly_order']))
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
    '''
    Determines Bounding Rectangle size for alignment stack. Must be preceded by a call to SetStackCafm.

    To get result for current scale, in the main process, use:
    from src.image_funcs import BoundingRect, ImageSize
    BoundingRect(cfg.data.aligned_dict())

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
    if cfg.SUPPORT_NONSQUARE:
        # model_bounds = None
        # al_stack = cfg.data.aligned_dict()
        model_bounds = [[0,0]] #Todo initialize this better
        siz = ImageSize(al_stack[0]['images']['base']['filename'])
        for item in al_stack:
            c_afm = np.array(item['align_to_ref_method']['method_results']['cumulative_afm'])
            model_bounds = np.append(model_bounds, modelBounds2(c_afm, siz), axis=0)
        border_width_x = max(0 - model_bounds[:, 0].min(), model_bounds[:, 0].max() - siz[0])
        border_width_y = max(0 - model_bounds[:, 1].min(), model_bounds[:, 1].max() - siz[1])
        rect = [-border_width_x, -border_width_y, siz[0] + 2 * border_width_x, siz[1] + 2 * border_width_y]
        logger.info('Bounding Rectangle Dims: %s' % str(rect))
        # AlignEM[2]: [-14, -14, 1052, 540]
        # AlignEM[2]: [-14, -76, 1052, 664]
        return rect
    else:
        logger.debug('BoundingRect:')
        model_bounds = None
        siz = ImageSize(al_stack[0]['images']['base']['filename'])
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
#     arrays to a multipage greyscale, RGB, or RGBA image, with file type
#     deduced from the filename.
#     The `flags` parameter should be one or more values from the IO_FLAGS
#     class defined in this module, or-ed together with | as appropriate.
#     (See the source-code comments for more details.)
#     """
#
#     filename = asbytes(filename)
#     ftype = _FI.FreeImage_GetFIFFromFilename(filename)
#     if ftype == -1:
#         raise ValueError('Cannot determine type of file %s' % filename)
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
#         raise ValueError('Cannot write arrays of given type and shape.')
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
#                dtype.type == np.uint8:
#             wrapped_array[0] = n(array[:, :, 2])
#             wrapped_array[1] = n(array[:, :, 1])
#             wrapped_array[2] = n(array[:, :, 0])
#             if shape[2] == 4:
#                 wrapped_array[3] = n(array[:, :, 3])
#         else:
#             wrapped_array[:] = n(array)
#         if len(shape) == 2 and dtype.type == np.uint8:
#             palette = _FI.FreeImage_GetPalette(bitmap)
#             palette = ctypes.c_void_p(palette)
#             if not palette:
#                 raise RuntimeError('Could not get image palette')
#             ctypes.memmove(palette, _GREY_PALETTE.ctypes.data, 1024)
#         return bitmap, fi_type
#     except:
#         _FI.FreeImage_Unload(bitmap)
#         raise
#
# def _wrap_bitmap_bits_in_array(bitmap, shape, dtype):
#     """Return an ndarray view on the data in a FreeImage bitmap. Only
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
#             raise ValueError('Unknown image pixel type')
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
#     # sharding = {'@type': 'neuroglancer_uint64_sharded_v1',
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
#                 "type": "image",
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

