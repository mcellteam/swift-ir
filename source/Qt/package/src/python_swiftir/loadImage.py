#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import cv2

def loadImage(ifn, stretch=False):
    '''LOADIMAGE - Load an image for alignment work
    img = LOADIMAGE(ifn) loads the named image, which can then serve as
    either the “stationary” or the “moving” image.
    Images are always converted to 8 bits. Optional second argument STRETCH
    enables contrast stretching. STRETCH may be given as a percentage,
    or simply as True, which implies 0.1%.
    The current implementation can only read from the local file system.
    Backends for http, DVID, etc., would be a useful extension.'''
    if type(stretch)==bool and stretch:
        stretch = 0.1
    img = cv2.imread(ifn, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)
    if stretch:
        N = img.size
        ilo = int(.01*stretch*N)
        ihi = int((1-.01*stretch)*N)
        vlo = np.partition(img.reshape(N,), ilo)[ilo]
        vhi = np.partition(img.reshape(N,), ihi)[ihi]
        nrm = np.array([255.999/(vhi-vlo)], dtype='float32')
        img[img<vlo] = vlo
        img = ((img-vlo) * nrm).astype('uint8')
    return img
