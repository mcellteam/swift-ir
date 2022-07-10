#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np

__all__ = ['identityAffine']

def identityAffine():
    '''IDENTITYAFFINE - Return an idempotent python_swiftir transform
    afm = IDENTITYAFFINE() returns an python_swiftir transform that is
    an identity transform.'''
    return np.array([[1., 0., 0.],
                     [0., 1., 0.]])