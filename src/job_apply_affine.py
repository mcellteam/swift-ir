#!/usr/bin/env python3
'''
Job script which calls loadImage, saveImage, and affineImage (affineImage originally relied on cv2 for applying
the affine transformation)
'''

import sys
import logging
import numpy as np
import traceback
import cv2
# from swiftir import affineImage, saveImage, loadImage
from swiftir import saveImage, loadImage

def shiftAffine(afm, dx):
    return afm + np.array([[0,0,dx[0]],[0,0,dx[1]]])

def affineImage(afm, img, rect=None, grayBorder=False ):
    '''AFFINEIMAGE - Apply an affine transformation to an image
    res = AFFINEIMAGE(afm, img) returns an image the same size of IMGimage_funcs
    looking up pixels in the original using affine transformation.
    res = AFFINEIMAGE(afm, img, rect), where rect is an (x0,y0,w,h)-tuple
    as from MODELBOUNDS, returns the given rectangle of model space.
    If grayBorder is True, set the image border color to the mean image value'''
    if grayBorder:
      border = img.mean()
    else:
      border = 0
    if rect is None:
        return cv2.warpAffine(img, afm, (img.shape[1],img.shape[0]),
                              flags=cv2.WARP_INVERSE_MAP + cv2.INTER_LINEAR,
                              borderValue=border)
    else:
        p1 = applyAffine(afm, (0,0))
        p2 = applyAffine(afm, (rect[0], rect[1]))
        return cv2.warpAffine(img, shiftAffine(afm, p2-p1), (rect[2], rect[3]),
                              flags=cv2.WARP_INVERSE_MAP + cv2.INTER_LINEAR,
                              borderValue=border)

logger = logging.getLogger(__name__)

def image_apply_affine(in_fn=None, out_fn=None, afm=None, rect=None, grayBorder=False):
    logger.info("image_apply_affine afm: " + str(afm))
    in_img = loadImage(in_fn)
    logger.debug("Transforming " + str(in_fn))
    logger.debug("    afm = " + str(afm))
    logger.debug("    rect = " + str(rect))
    logger.debug("    grayBorder = " + str(grayBorder))
    out_img = affineImage(afm, in_img, rect=rect, grayBorder=grayBorder)
    logger.debug("  saving transformed image as: " + str(out_fn))
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


if (__name__ == '__main__'):
    # len(sys.argv) = 16
    if (len(sys.argv) < 4):
        print_command_line_syntax(sys.argv)
        exit(1)
    in_fn = sys.argv[-2]
    out_fn = sys.argv[-1]
    rect = None
    grayBorder = False

    # Scan arguments (excluding program name and last 2 file names)
    i = 1
    while (i < len(sys.argv) - 2):
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
    
    sys.stdout.close()
    sys.stderr.close()
