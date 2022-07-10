#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
from .applyAffine import applyAffine

__all__ = ['affineImage','shiftAffine']


def affineImage(afm, img, rect=None, grayBorder=False ):
    '''AFFINEIMAGE - Apply an python_swiftir transformation to an image
    res = AFFINEIMAGE(afm, img) returns an image the same size of IMG
    looking up pixels in the original using python_swiftir transformation.
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

def shiftAffine(afm, dx):
    return afm + np.array([[0, 0, dx[0]], [0, 0, dx[1]]])