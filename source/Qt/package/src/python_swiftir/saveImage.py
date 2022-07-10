#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import cv2
__all__ = ['saveImage']

def saveImage(img, ofn, qual=None, comp=1):
    '''SAVEIMAGE - Save an image
    SAVEIMAGE(img, ofn) saves the image IMG to the file named OFN.
    Optional third argument specifies jpeg quality as a number between
    0 and 100, and must only be given if OFN ends in ".jpg". Default
    is 95.'''
    if qual is None:
        ext = os.path.splitext(ofn)[-1]
        if (ext == '.tif') or (ext == '.tiff') or (ext == '.TIF') or (ext == '.TIFF'):
            if comp != None:
                # code 1 means uncompressed tif
                # code 5 means LZW compressed tif
                cv2.imwrite(ofn, img, (cv2.IMWRITE_TIFF_COMPRESSION, comp))
            else:
                # Use default
                cv2.imwrite(ofn, img)
        else:
            cv2.imwrite(ofn, img)
    else:
        cv2.imwrite(ofn, img, (cv2.IMWRITE_JPEG_QUALITY, qual))