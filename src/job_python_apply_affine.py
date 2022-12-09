#!/usr/bin/env python3
'''
Job script which calls loadImage, saveImage, and affineImage (affineImage originally relied on cv2 for applying
the affine transformation)
'''

import sys
import logging
import argparse
import numpy as np
import traceback
from PIL import Image
import zarr
import numpy as np

try:
    from swiftir import affineImage, saveImage, loadImage
except ImportError:
    from src.swiftir import affineImage, saveImage, loadImage

logger = logging.getLogger(__name__)


def image_apply_affine(in_fn=None, out_fn=None, afm=None, rect=None, grayBorder=False):
    logger.critical("image_apply_affine afm: " + str(afm))
    in_img = loadImage(in_fn)
    logger.critical("Transforming " + str(in_fn))
    logger.critical("    afm = " + str(afm))
    logger.critical("    rect = " + str(rect))
    logger.critical("    grayBorder = " + str(grayBorder))
    out_img = affineImage(afm, in_img, rect=rect, grayBorder=grayBorder)
    logger.critical("  saving transformed image as: " + str(out_fn))
    try:
        saveImage(out_img, out_fn)
    except Exception:
        logger.warning("An Exception Occurred Running 'saveImage'")
        logger.warning(traceback.format_exc())


def print_command_line_syntax(args):
    logger.debug('Usage: %s [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' % (args[0]))
    logger.debug('Description:')
    logger.debug('  Apply 2D affine matrix to input image file')
    logger.debug('  with optional bounding rectangle and gray border.')
    logger.debug('  Result is written to output image file.')
    logger.debug('Options:')
    logger.debug('  -rect 0 0 100 100   : x_min y_min x_max y_max bounding rectangle')
    logger.debug('  -gray               : output with gray border')
    logger.debug('  -debug #            : # = debug level (0-100, larger numbers produce more output)')
    logger.debug('Arguments:')
    logger.debug('  -afm 1 0 0 0 1 0    : the 2D affine matrix')
    logger.debug('  in_file_name        : input image file name (opened for reading only)')
    logger.debug('  out_file_name       : output image file name (opened for writing and overwritten)')


'''
/Users/joelyancey/glanceem_swift/alignEM/src/job_python_apply_affine.py
-gray
-rect
-3
-3
1030
1030
-afm
1.0053000450134277
0.004926680121570826
-2.3439199924468994
-0.005592479836195707
1.0550800561904907
1.5037000179290771

'''


if (__name__ == '__main__'):
    # len(sys.argv) = 16
    if (len(sys.argv) < 4):
        print_command_line_syntax(sys.argv)
        exit(1)
    in_fn = sys.argv[-4]  # Input File Name
    out_fn = sys.argv[-3]  # Output File Name
    zarr_grp = sys.argv[-2]  # Zarr Group
    ID = int(sys.argv[-1])
    rect = None
    grayBorder = False

    # Scan arguments (excluding program name and last 2 file names)
    i = 1
    # while (i < len(sys.argv) - 2):
    while (i < len(sys.argv) - 4):
        logger.info("Processing option " + sys.argv[i])
        if sys.argv[i] == '-afm':
            afm_list = []
            # Extend afm_list using the next 6 args
            for n in range(6):
                i += 1  # Increment to get the argument
                afm_list.extend([float(sys.argv[i])])
            afm = np.array(afm_list, dtype='float64').reshape((-1, 3))
        elif sys.argv[i] == '-rect':
            rect_list = []
            # Extend rect_list using the next 4 args
            for n in range(4):
                i += 1  # Increment to get the argument
                rect_list.extend([int(sys.argv[i])])
            rect = np.array(rect_list, dtype='int')
        elif sys.argv[i] == '-gray':
            grayBorder = True
            # No need to increment i because no additional arguments were taken
        elif sys.argv[i] == '-debug':
            i += 1  # Increment to get the argument
            debug_level = int(sys.argv[i])
        else:
            logger.warning("Improper argument list: %s" % str(sys.argv))
            print_command_line_syntax(sys.argv)
            exit(1)
        i += 1  # Increment to get the next option

    try:
        image_apply_affine(in_fn=in_fn, out_fn=out_fn, afm=afm, rect=rect, grayBorder=grayBorder)
    except Exception:
        logger.warning("An Exception Occurred Running 'image_apply_affine'")
        logger.warning(traceback.format_exc())

    dimx, dimy = rect[2], rect[3]
    # im = tifffile.imread(out_fn)
    Image.MAX_IMAGE_PIXELS = 1_000_000_000_000
    store = zarr.open(zarr_grp)
    # print(store.info)
    store[ID, :, :] = np.flip(Image.open(out_fn), axis=1)
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    sys.stdout.close()
    sys.stderr.close()
