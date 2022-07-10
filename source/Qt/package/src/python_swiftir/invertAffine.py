#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np

__all__ = ['invertAffine']

def invertAffine(afm):
    '''INVERTAFFINE - Invert affine transform
    INVERTAFFINE(afm), where AFM is a 2x3 affine transformation matrix,
    returns the inverse transform.'''
    afm = np.vstack((afm, [0,0,1]))
    ifm = np.linalg.inv(afm)
    return ifm[0:2,:]