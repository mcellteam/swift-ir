#!/usr/bin/env python3
#!/usr/bin/env python2.7
# print(f'pyswift_tui.py.Loading {__name__}')
# import sys
# import os
# import json
# import copy
# import errno
# import inspect
import numpy as np
# import scipy.stats as sps

from utils.helpers import print_debug
from utils.get_image_size import get_image_size


__all__ = ['BiasMat',
           'BiasFuncs',
           'ApplyBiasFuncs',
           'InitCafm',
           'SetSingleCafm',
           'SetStackCafm',
           'BoundingRect']

# try: import swiftir as swiftir
# except: import swiftir
#
# try: from get_image_size import get_image_size
# except: from get_image_size import get_image_size
#
# try: from helpers import print_debug
# except: from helpers import print_debug

debug_level = 70


# Return the bias matrix at position x in the stack as given by the bias_funcs
def BiasMat(x, bias_funcs):
    print('pyswift_tui.BiasMat >>>>>>>>')

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

    bias_mat = swiftir.identityAffine()

    # Compose bias matrix as skew*scale*rot*trans
    bias_mat = swiftir.composeAffine(skew_x_bias_mat, bias_mat)
    bias_mat = swiftir.composeAffine(scale_bias_mat, bias_mat)
    bias_mat = swiftir.composeAffine(rot_bias_mat, bias_mat)
    bias_mat = swiftir.composeAffine(trans_bias_mat, bias_mat)

    print('<<<<<<<< pyswift_tui.BiasMat')

    return bias_mat


# NEW
# Find the bias functions that best fit the trends in c_afm across the whole stack
# For now the form of the functions is an Nth-order polynomial
def BiasFuncs(al_stack, bias_funcs=None, poly_order=4):
    print('pyswift_tui.BiasFuncs >>>>>>>>')
    print_debug(50, 50 * 'B0')
    poly_order=int(poly_order)
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

    print_debug(50, 50 * 'B1')
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

    print_debug(50, 20 * 'B2 ')
    p = np.polyfit(skew_x_array[:, 0], skew_x_array[:, 1], poly_order)
    print_debug(50, 10 * 'B2a ')
    bias_funcs['skew_x'][:-1] += p[:-1]
    print_debug(50, 10 * 'B2b ')
    if init_scalars:
        print_debug(50, 10 * 'B2c ')
        bias_funcs['skew_x'][poly_order] = p[poly_order]
    print_debug(50, 50 * 'B3')

    p = np.polyfit(scale_x_array[:, 0], scale_x_array[:, 1], poly_order)
    bias_funcs['scale_x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['scale_x'][poly_order] = p[poly_order]
    print_debug(50, 50 * 'B4')

    p = np.polyfit(scale_y_array[:, 0], scale_y_array[:, 1], poly_order)
    bias_funcs['scale_y'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['scale_y'][poly_order] = p[poly_order]
    print_debug(50, 50 * 'B5')

    p = np.polyfit(rot_array[:, 0], rot_array[:, 1], poly_order)
    bias_funcs['rot'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['rot'][poly_order] = p[poly_order]
    print_debug(50, 50 * 'B6')

    p = np.polyfit(x_array[:, 0], x_array[:, 1], poly_order)
    bias_funcs['x'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['x'][poly_order] = p[poly_order]

    p = np.polyfit(y_array[:, 0], y_array[:, 1], poly_order)
    bias_funcs['y'][:-1] += p[:-1]
    if init_scalars:
        bias_funcs['y'][poly_order] = p[poly_order]

    print_debug(50, "\npyswift_tui.BiasFuncs | Bias Funcs: \n%s\n" % (str(bias_funcs)))

    print('<<<<<<<< pyswift_tui.BiasFuncs')


    return bias_funcs


def ApplyBiasFuncs(align_list):
    print('pyswift_tui.ApplyBiasFuncs >>>>>>>>')

    # Iteratively determine and null out bias in c_afm
    print_debug(50, "\npyswift_tui.ApplyBiasFuncs | Computing and Nulling Biases...\n")
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

    print('<<<<<<<< pyswift_tui.ApplyBiasFuncs')
    return c_afm_init


# Get the initial c_afm from the constant terms of the bias_funcs
def InitCafm(bias_funcs):
    print('pyswift_tui.InitCafm >>>>>>>>')

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

    c_afm_init = swiftir.identityAffine()

    # Compose bias matrix as skew*scale*rot*trans
    c_afm_init = swiftir.composeAffine(init_skew_x_mat, c_afm_init)
    c_afm_init = swiftir.composeAffine(init_scale_mat, c_afm_init)
    c_afm_init = swiftir.composeAffine(init_rot_mat, c_afm_init)
    c_afm_init = swiftir.composeAffine(init_trans_mat, c_afm_init)

    print('<<<<<<<< pyswift_tui.InitCafm')

    return c_afm_init


# Calculate and set the value of the c_afm (with optional bias) for a single layer_dict item
def SetSingleCafm(layer_dict, c_afm, bias_mat=None):
    # print('pyswift_tui.SetSingleCafm >>>>>>>>')

    atrm = layer_dict['align_to_ref_method']
    # print("pyswift_tui.atrm = layer_dict['align_to_ref_method'] = ", str(atrm) )
    try:
        afm = np.array(atrm['method_results']['affine_matrix'])
    except:
        '''
        THIS EXCEPT IS BEING TRIGGERED #0619
        '''

        print_debug(-1, 'pyswift_tui.SetSingleCafm | ERROR | empty affine_matrix in base image: %s' % (
        layer_dict['images']['base']['filename']))
        print_debug(-1, 'pyswift_tui.SetSingleCafm | Automatically skipping base image: %s' % (layer_dict['images']['base']['filename']))
        layer_dict['skip'] = True
        afm = swiftir.identityAffine()
        atrm['method_results']['affine_matrix'] = afm.tolist()
        # atrm['method_results']['snr'] = [0.0]
        # atrm['method_results']['snr_report'] = 'SNR: --'

    c_afm = np.array(c_afm)
    c_afm = swiftir.composeAffine(afm, c_afm)

    # Apply bias_mat if given
    if type(bias_mat) != type(None):
        c_afm = swiftir.composeAffine(bias_mat, c_afm)

    atrm['method_results']['cumulative_afm'] = c_afm.tolist()

    # print('<<<<<<<< pyswift_tui.SetSingleCafm')

    return c_afm


# Calculate c_afm across the whole stack with optional bias correction
# @countit #sus #crash #bug #0405
def SetStackCafm(scale_dict, null_biases=False):
    print('pyswift_tui.SetStackCafm >>>>>>>>')

    print_debug(50, "\npyswift_tui.SetStackCafm | Computing Cafm and Nulling Biases...\n")

    # To perform bias correction, first initialize Cafms without bias correction
    if null_biases == True:
        SetStackCafm(scale_dict, null_biases=False)

    al_stack = scale_dict['alignment_stack']

    # If null_biases==True, Iteratively determine and null out bias in c_afm
    bias_mat = None
    if null_biases:
        bias_funcs = BiasFuncs(al_stack, poly_order=scale_dict['poly_order'])
        c_afm_init = InitCafm(bias_funcs)
    else:
        c_afm_init = swiftir.identityAffine()
    if null_biases:
        bias_iters = 2
    else:
        bias_iters = 1
    for bi in range(bias_iters):
        c_afm = c_afm_init
        for align_idx in range(len(al_stack)):
            if null_biases:
                bias_mat = BiasMat(align_idx, bias_funcs)
            c_afm = SetSingleCafm(al_stack[align_idx], c_afm, bias_mat=bias_mat)
        if bi < bias_iters - 1:
            bias_funcs = BiasFuncs(al_stack, bias_funcs=bias_funcs)

    print('<<<<<<<< pyswift_tui.SetStackCafm')
    return c_afm_init




# Determine Bounding Rectangle for a stack of images
def BoundingRect(al_stack):
    print('pyswift_tui.BoundingRect >>>>>>>>')

    model_bounds = None

    siz = get_image_size(al_stack[0]['images']['base']['filename'])

    # print()

    for item in al_stack:
        c_afm = np.array(item['align_to_ref_method']['method_results']['cumulative_afm'])

        if type(model_bounds) == type(None):
            model_bounds = swiftir.modelBounds2(c_afm, siz)
        else:
            model_bounds = np.append(model_bounds, swiftir.modelBounds2(c_afm, siz), axis=0)

    border_width = max(0 - model_bounds[:, 0].min(), 0 - model_bounds[:, 1].min(), model_bounds[:, 0].max() - siz[0], model_bounds[:, 1].max() - siz[0])

    rect = [-border_width, -border_width, siz[0] + 2 * border_width, siz[0] + 2 * border_width]

    print('<<<<<<<< pyswift_tui.BoundingRect')
    return rect


def composeAffine(afm, bfm):
    '''COMPOSEAFFINE - Compose two affine transforms
    COMPOSEAFFINE(afm1, afm2) returns the affine transform AFM1 ∘ AFM2
    that applies AFM1 after AFM2.
    Affine matrices must be 2x3 numpy arrays.'''
    afm = np.vstack((afm, [0,0,1]))
    bfm = np.vstack((bfm, [0,0,1]))
    fm = np.matmul(afm, bfm)
    return fm[0:2,:]

def applyAffine(afm, xy):
    '''APPLYAFFINE - Apply affine transform to a point
    xy_ = APPLYAFFINE(afm, xy) applies the affine matrix AFM to the point XY
    Affine matrix must be a 2x3 numpy array. XY may be a list or an array.'''
    if not type(xy)==np.ndarray:
        xy = np.array([xy[0], xy[1]])
    return np.matmul(afm[0:2,0:2], xy) + reptoshape(afm[0:2,2], xy)

def identityAffine():
    '''IDENTITYAFFINE - Return an idempotent affine transform
    afm = IDENTITYAFFINE() returns an affine transform that is
    an identity transform.'''
    return np.array([[1., 0., 0.],
                     [0., 1., 0.]])

def modelBounds2(afm, siz):
    '''MODELBOUNDS - Returns a bounding rectangle in model space
    (x0, y0, w, h) = MODELBOUNDS(afm, siz) returns the bounding rectangle
    of an input rectangle (siz) in model space if pixel lookup is through affine
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