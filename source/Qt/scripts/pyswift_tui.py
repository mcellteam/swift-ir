#!/usr/bin/env python2.7
# print(f'pyswift_tui.py | Loading {__name__}')
import sys
import os
import json
import copy
import errno
import inspect
import numpy as np
import scipy.stats as sps

'''
print('\npyswift_tui | sys.path:')
print(sys.path)

pyswift_tui | sys.path:
['/Users/joelyancey/glanceem_swift/swift-ir/source/Qt', 
 '/opt/local/Library/Frameworks/Python.framework/Versions/3.9/lib/python39.zip', 
 '/opt/local/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9', 
 '/opt/local/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/lib-dynload', 
 '/Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/lib/python3.9/site-packages']
'''

try:
    import scripts.align_swiftir as align_swiftir
except:
    from scripts import align_swiftir

try:
    import package.swiftir as swiftir
except:
    import swiftir

try:
    from package.get_image_size import get_image_size
except:
    from get_image_size import get_image_size

# import project_runner  # Not really used yet

# This is monotonic (0 to 100) with the amount of output:


debug_level = 100  # A larger value prints more stuff

# Using the Python version does not work because the Python 3 code can't
# even be parsed by Python2. It could be dynamically compiled, or use the
# alternate syntax, but that's more work than it's worth for now.
if sys.version_info >= (3, 0):
    # print ( "Python 3: Supports arbitrary arguments via print")
    # def print_debug ( level, *ds ):
    #  # print_debug ( 1, "This is really important!!" )
    #  # print_debug ( 99, "This isn't very important." )
    #  global debug_level
    #  if level <= debug_level:
    #    print ( *ds )
    pass
else:
    # print ("Python 2: Use default parameters for limited support of arbitrary arguments via print")
    pass


# For now, always use the limited argument version
def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
    global debug_level
    if level <= debug_level:
        if p1 == None:
            sys.stderr.write("" + '\n')
        elif p2 == None:
            sys.stderr.write(str(p1) + '\n')
        elif p3 == None:
            sys.stderr.write(str(p1) + str(p2) + '\n')
        elif p4 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + '\n')
        elif p5 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + '\n')
        else:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + str(p5) + '\n')


def print_debug_enter(level):
    if level <= debug_level:
        call_stack = inspect.stack()
        sys.stderr.write(
            "pyswift_tui | Call Stack: " + str([stack_item.function for stack_item in call_stack][1:]) + '\n')


# Do Linear Regression of X,Y data
def lin_fit(x, y):
    print_debug_enter(90)
    (m, b, r, p, stderr) = sps.linregress(x, y)
    print_debug(90, 'linear regression:')
    print_debug(90, '  slope:', m)
    print_debug(90, '  intercept:', b)
    print_debug(90, '  r:', r)
    print_debug(90, '  p:', p)
    print_debug(90, '  stderr:', stderr)
    print_debug(90, '')

    return (m, b, r, p, stderr)


# align_swiftir.global_swiftir_mode = 'c'
align_swiftir.global_swiftir_mode = 'python'

# print("\npyswift_tui.py | Setting align_swiftir.global_swiftir_mode = 'python'\n")

'''
# Find the bias functions that best fit the trends in c_afm across the whole align_list
# For now the form of the functions is a 4th-order polynomial
def BiasFuncs(align_list, bias_funcs=None):
  print_debug_enter (90)
  print_debug(50,50*'B0')
  if type(bias_funcs) == type(None):
    init_scalars = True
    bias_funcs = {}
    bias_funcs['skew_x'] = np.zeros((5))
    bias_funcs['scale_x'] = np.zeros((5))
    bias_funcs['scale_y'] = np.zeros((5))
    bias_funcs['rot'] = np.zeros((5))
    bias_funcs['x'] = np.zeros((5))
    bias_funcs['y'] = np.zeros((5))
  else:
    init_scalars = False

  skew_x_array = np.zeros((len(align_list),2))
  scale_x_array = np.zeros((len(align_list),2))
  scale_y_array = np.zeros((len(align_list),2))
  rot_array = np.zeros((len(align_list),2))
  x_array = np.zeros((len(align_list),2))
  y_array = np.zeros((len(align_list),2))

  print_debug(50,50*'B1')
  i=0
  for item in align_list:
    align_idx = item['i']
    align_item = item['proc']

    c_afm = align_item.cumulative_afm

    rot = np.arctan(c_afm[1,0]/c_afm[0,0])
    scale_x = np.sqrt(c_afm[0,0]**2 + c_afm[1,0]**2)
    scale_y = (c_afm[1,1]*np.cos(rot))-(c_afm[0,1]*np.sin(rot))
    skew_x = ((c_afm[0,1]*np.cos(rot))+(c_afm[1,1]*np.sin(rot)))/scale_y
    det = (c_afm[0,0]*c_afm[1,1])-(c_afm[0,1]*c_afm[1,0])

    skew_x_array[i] = [align_idx,skew_x]
    scale_x_array[i] = [align_idx,scale_x]
    scale_y_array[i] = [align_idx,scale_y]
    rot_array[i] = [align_idx,rot]
    x_array[i] = [align_idx,c_afm[0,2]]
    y_array[i] = [align_idx,c_afm[1,2]]
    i+=1

  print_debug(50,20*'B2 ')
  p = np.polyfit(skew_x_array[:,0],skew_x_array[:,1],4)
  print_debug(50,10*'B2a ')
  bias_funcs['skew_x'][:-1] += p[:-1]
  print_debug(50,10*'B2b ')
  if init_scalars:
    print_debug(50,10*'B2c ')
    bias_funcs['skew_x'][4] = p[4]
  print_debug(50,50*'B3')

  p = np.polyfit(scale_x_array[:,0],scale_x_array[:,1],4)
  bias_funcs['scale_x'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['scale_x'][4] = p[4]
  print_debug(50,50*'B4')

  p = np.polyfit(scale_y_array[:,0],scale_y_array[:,1],4)
  bias_funcs['scale_y'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['scale_y'][4] = p[4]
  print_debug(50,50*'B5')

  p = np.polyfit(rot_array[:,0],rot_array[:,1],4)
  bias_funcs['rot'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['rot'][4] = p[4]
  print_debug(50,50*'B6')

  p = np.polyfit(x_array[:,0],x_array[:,1],4)
  bias_funcs['x'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['x'][4] = p[4]

  p = np.polyfit(y_array[:,0],y_array[:,1],4)
  bias_funcs['y'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['y'][4] = p[4]

  print_debug(50,"\nBias Funcs: \n%s\n" % (str(bias_funcs)))

  return bias_funcs
'''

'''
# BACKUP 
# Find the bias functions that best fit the trends in c_afm across the whole stack
# For now the form of the functions is hard-coded as a 4th-order polynomial
def BiasFuncs(al_stack, bias_funcs=None):
  print_debug_enter (90)
  print_debug(50,50*'B0')
  if type(bias_funcs) == type(None):
    init_scalars = True
    bias_funcs = {}
    bias_funcs['skew_x'] = np.zeros((5))
    bias_funcs['scale_x'] = np.zeros((5))
    bias_funcs['scale_y'] = np.zeros((5))
    bias_funcs['rot'] = np.zeros((5))
    bias_funcs['x'] = np.zeros((5))
    bias_funcs['y'] = np.zeros((5))
  else:
    init_scalars = False

  skew_x_array = np.zeros((len(al_stack),2))
  scale_x_array = np.zeros((len(al_stack),2))
  scale_y_array = np.zeros((len(al_stack),2))
  rot_array = np.zeros((len(al_stack),2))
  x_array = np.zeros((len(al_stack),2))
  y_array = np.zeros((len(al_stack),2))

  print_debug(50,50*'B1')
  i=0
  for align_idx in range(len(al_stack)):

    c_afm = np.array(al_stack[align_idx]['align_to_ref_method']['method_results']['cumulative_afm'])

    rot = np.arctan(c_afm[1,0]/c_afm[0,0])
    scale_x = np.sqrt(c_afm[0,0]**2 + c_afm[1,0]**2)
    scale_y = (c_afm[1,1]*np.cos(rot))-(c_afm[0,1]*np.sin(rot))
    skew_x = ((c_afm[0,1]*np.cos(rot))+(c_afm[1,1]*np.sin(rot)))/scale_y
    det = (c_afm[0,0]*c_afm[1,1])-(c_afm[0,1]*c_afm[1,0])

    skew_x_array[i] = [align_idx,skew_x]
    scale_x_array[i] = [align_idx,scale_x]
    scale_y_array[i] = [align_idx,scale_y]
    rot_array[i] = [align_idx,rot]
    x_array[i] = [align_idx,c_afm[0,2]]
    y_array[i] = [align_idx,c_afm[1,2]]
    i+=1

  print_debug(50,20*'B2 ')
  p = np.polyfit(skew_x_array[:,0],skew_x_array[:,1],4)
  print_debug(50,10*'B2a ')
  bias_funcs['skew_x'][:-1] += p[:-1]
  print_debug(50,10*'B2b ')
  if init_scalars:
    print_debug(50,10*'B2c ')
    bias_funcs['skew_x'][4] = p[4]
  print_debug(50,50*'B3')

  p = np.polyfit(scale_x_array[:,0],scale_x_array[:,1],4)
  bias_funcs['scale_x'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['scale_x'][4] = p[4]
  print_debug(50,50*'B4')

  p = np.polyfit(scale_y_array[:,0],scale_y_array[:,1],4)
  bias_funcs['scale_y'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['scale_y'][4] = p[4]
  print_debug(50,50*'B5')

  p = np.polyfit(rot_array[:,0],rot_array[:,1],4)
  bias_funcs['rot'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['rot'][4] = p[4]
  print_debug(50,50*'B6')

  p = np.polyfit(x_array[:,0],x_array[:,1],4)
  bias_funcs['x'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['x'][4] = p[4]

  p = np.polyfit(y_array[:,0],y_array[:,1],4)
  bias_funcs['y'][:-1] += p[:-1]
  if init_scalars:
    bias_funcs['y'][4] = p[4]

  print_debug(50,"\nBias Funcs: \n%s\n" % (str(bias_funcs)))

  return bias_funcs
'''


# NEW
# Find the bias functions that best fit the trends in c_afm across the whole stack
# For now the form of the functions is an Nth-order polynomial
def BiasFuncs(al_stack, bias_funcs=None, poly_order=4):
    print_debug_enter(90)
    print_debug(50, 50 * 'B0')
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

    print_debug(50, "\npyswift_tui | Bias Funcs: \n%s\n" % (str(bias_funcs)))

    return bias_funcs


# Return the bias matrix at position x in the stack as given by the bias_funcs
def BiasMat(x, bias_funcs):
    print_debug_enter(90)

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

    return bias_mat


# Get the initial c_afm from the constant terms of the bias_funcs
def InitCafm(bias_funcs):
    print_debug_enter(70)

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

    return c_afm_init


# Calculate and set the value of the c_afm (with optional bias) for a single layer_dict item
def SetSingleCafm(layer_dict, c_afm, bias_mat=None):
    atrm = layer_dict['align_to_ref_method']
    print("pyswift_tui | atrm = layer_dict['align_to_ref_method'] = ", str(atrm))
    try:
        afm = np.array(atrm['method_results']['affine_matrix'])
    except:
        '''
        THIS EXCEPT IS BEING TRIGGERED #0619
        '''

        print_debug(-1, 'pyswift_tui | SetSingleCafm error: empty affine_matrix in base image: %s' % (
                layer_dict['images']['base']['filename']))
        print_debug(-1,
                    'pyswift_tui | Automatically skipping base image: %s' % (layer_dict['images']['base']['filename']))
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

    return c_afm


def ApplyBiasFuncs(align_list):
    print_debug_enter(70)

    # Iteratively determine and null out bias in c_afm
    print_debug(50, "\npyswift_tui | Computing and Nulling Biases...\n")
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


# Calculate c_afm across the whole stack with optional bias correction
# @countit #sus #crash #bug #0405
def SetStackCafm(scale_dict, null_biases=False):
    print_debug_enter(70)

    print_debug(50, "\npyswift_tui | Computing Cafm and Nulling Biases...\n")

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

    return c_afm_init


'''
def BoundingRect(align_list,siz):
  print_debug_enter (70)

  model_bounds = None

  for item in align_list:
    align_item = item['proc']

    if type(model_bounds) == type(None):
      model_bounds = swiftir.modelBounds2(align_item.cumulative_afm, siz)
    else:
      model_bounds = np.append(model_bounds, swiftir.modelBounds2(align_item.cumulative_afm, siz), axis=0)

  border_width = max(0 - model_bounds[:,0].min(), 0 - model_bounds[:,1].min(), model_bounds[:,0].max() - siz[0], model_bounds[:,1].max() - siz[0])

  rect = [-border_width, -border_width, siz[0]+2*border_width, siz[0]+2*border_width]

  return rect
'''


# Determine Bounding Rectangle for a stack of images
def BoundingRect(al_stack):
    print_debug_enter(70)

    model_bounds = None

    siz = get_image_size(al_stack[0]['images']['base']['filename'])

    for item in al_stack:
        c_afm = np.array(item['align_to_ref_method']['method_results']['cumulative_afm'])

        if type(model_bounds) == type(None):
            model_bounds = swiftir.modelBounds2(c_afm, siz)
        else:
            model_bounds = np.append(model_bounds, swiftir.modelBounds2(c_afm, siz), axis=0)

    border_width = max(0 - model_bounds[:, 0].min(), 0 - model_bounds[:, 1].min(), model_bounds[:, 0].max() - siz[0],
                       model_bounds[:, 1].max() - siz[0])

    rect = [-border_width, -border_width, siz[0] + 2 * border_width, siz[0] + 2 * border_width]

    return rect


def save_bias_analysis(al_stack, bias_data_path):
    print('(tag) save_bias_analysis | bias_data_path=', bias_data_path)

    snr_file = open(os.path.join(bias_data_path, 'snr_1.dat'), 'w')
    bias_x_file = open(os.path.join(bias_data_path, 'bias_x_1.dat'), 'w')
    bias_y_file = open(os.path.join(bias_data_path, 'bias_y_1.dat'), 'w')
    bias_rot_file = open(os.path.join(bias_data_path, 'bias_rot_1.dat'), 'w')
    bias_scale_x_file = open(os.path.join(bias_data_path, 'bias_scale_x_1.dat'), 'w')
    bias_scale_y_file = open(os.path.join(bias_data_path, 'bias_scale_y_1.dat'), 'w')
    bias_skew_x_file = open(os.path.join(bias_data_path, 'bias_skew_x_1.dat'), 'w')
    bias_det_file = open(os.path.join(bias_data_path, 'bias_det_1.dat'), 'w')
    afm_file = open(os.path.join(bias_data_path, 'afm_1.dat'), 'w')
    c_afm_file = open(os.path.join(bias_data_path, 'c_afm_1.dat'), 'w')

    for i in range(len(al_stack)):

        if True or not al_stack[i]['skip']:
            try:
                atrm = al_stack[i]['align_to_ref_method']
                afm = np.array(atrm['method_results']['affine_matrix'])
                c_afm = np.array(atrm['method_results']['cumulative_afm'])
                snr = np.array(atrm['method_results']['snr'])
            except:
                print('pyswift_tui.save_bias_analysis | EXCEPTION | There was a problem reading the project file')

            # Compute and save final biases in analysis data files
            rot = np.arctan(c_afm[1, 0] / c_afm[0, 0])
            scale_x = np.sqrt(c_afm[0, 0] ** 2 + c_afm[1, 0] ** 2)
            scale_y = (c_afm[1, 1] * np.cos(rot)) - (c_afm[0, 1] * np.sin(rot))
            skew_x = ((c_afm[0, 1] * np.cos(rot)) + (c_afm[1, 1] * np.sin(rot))) / scale_y
            det = (c_afm[0, 0] * c_afm[1, 1]) - (c_afm[0, 1] * c_afm[1, 0])

            snr_file.write('%d %.6g\n' % (i, snr.mean()))
            bias_x_file.write('%d %.6g\n' % (i, c_afm[0, 2]))
            bias_y_file.write('%d %.6g\n' % (i, c_afm[1, 2]))
            bias_rot_file.write('%d %.6g\n' % (i, rot))
            bias_scale_x_file.write('%d %.6g\n' % (i, scale_x))
            bias_scale_y_file.write('%d %.6g\n' % (i, scale_y))
            bias_skew_x_file.write('%d %.6g\n' % (i, skew_x))
            bias_det_file.write('%d %.6g\n' % (i, det))

            afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
                    i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
            c_afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (
                    i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

            print_debug(50, 'pyswift_tui | AFM:  %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
                    i, afm[0, 0], afm[0, 1], afm[0, 2], afm[1, 0], afm[1, 1], afm[1, 2]))
            print_debug(50, 'pyswift_tui | CAFM: %d %.6g %.6g %.6g %.6g %.6g %.6g' % (
                    i, c_afm[0, 0], c_afm[0, 1], c_afm[0, 2], c_afm[1, 0], c_afm[1, 1], c_afm[1, 2]))

    snr_file.close()
    bias_x_file.close()
    bias_y_file.close()
    bias_rot_file.close()
    bias_scale_x_file.close()
    bias_scale_y_file.close()
    bias_skew_x_file.close()
    bias_det_file.close()
    afm_file.close()
    c_afm_file.close()


'''
# Schema of project status dictionary:
# Should we merge this with the project datamodel?
proj_status { 
  'defined_scales': [ 1, 4 ]
  'finest_scale_done': 4
  'scale_tbd': 1
  'scales': {
    'scale_1': {
      'all_aligned': False
      'aligned_stat': np.array([ True, True, True, False, False ])
    }
    'scale_4': {
      'all_aligned': True
      'aligned_stat': np.array([ True, True, True, True, True ])
    }
  }
}
'''


def evaluate_project_status(project):
    # Construct a project status dictionary (proj_status above)
    print_debug_enter(40)

    # Get int values for scales in a way compatible with old ('1') and new ('scale_1') style for keys
    scales = sorted([int(s.split('scale_')[-1]) for s in project['data']['scales'].keys()])

    proj_status = {}
    proj_status['defined_scales'] = scales
    proj_status['finest_scale_done'] = 0
    proj_status['scale_tbd'] = 0
    proj_status['scales'] = {}
    for scale in scales:
        scale_key = 'scale_' + str(scale)
        proj_status['scales'][scale_key] = {}

        alstack = project['data']['scales'][scale_key]['alignment_stack']
        # print('\nalstack:')
        # from pprint import pprint
        # pprint(alstack)

        '''
 {'align_to_ref_method': {'method_data': {'whitening_factor': -0.68,
                                          'win_scale_factor': 0.8125},
                          'method_options': ['None'],
                          'method_results': {},
                          'selected_method': 'None'},
  'images': {'base': {'filename': '/Users/joelyancey/glanceem_swift/test_projects/test9999/scale_2/img_src/R34CA1-BS12.107.tif',
                      'metadata': {'annotations': [], 'match_points': []}},
             'ref': {'filename': '/Users/joelyancey/glanceem_swift/test_projects/test9999/scale_2/img_src/R34CA1-BS12.106.tif',
                     'metadata': {'annotations': [], 'match_points': []}}},
  'skip': False},


        '''

        num_alstack = len(alstack)

        #    afm_list = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in alstack if 'affine_matrix' in i['align_to_ref_method']['method_results'] ])

        # Create an array of boolean values representing whether 'affine_matrix' is in the method results for each layer
        proj_status['scales'][scale_key]['aligned_stat'] = np.array(
                ['affine_matrix' in item['align_to_ref_method']['method_results'] for item in alstack])

        num_afm = np.count_nonzero(proj_status['scales'][scale_key]['aligned_stat'] == True)

        if num_afm == num_alstack:
            proj_status['scales'][scale_key]['all_aligned'] = True
            if not proj_status['finest_scale_done']:
                # If not yet set, we've just found the finest scale that is done
                proj_status['finest_scale_done'] = scale
        else:
            proj_status['scales'][scale_key]['all_aligned'] = False
            # Since the outer loop iterates scales from finest to coarsest,
            #   this will always be the coarsest scale not done:
            proj_status['scale_tbd'] = scale

    return proj_status


def run_json_project(project=None, alignment_option='init_affine', use_scale=0, swiftir_code_mode='python',
                     start_layer=0, num_layers=-1, alone=False):
    '''Align one scale - either the one specified in "use_scale" or the coarsest without an AFM.'''
    print("\npyswift_tui | run_json_project | alignment_option = \n", alignment_option)
    print_debug_enter(40)
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    first_layer_has_ref = False
    if project['data']['scales']['scale_%d' % use_scale]['alignment_stack'][0]['images']['ref']['filename'] != None:
        if len(project['data']['scales']['scale_%d' % use_scale]['alignment_stack'][0]['images']['ref'][
                   'filename']) > 0:
            first_layer_has_ref = True

    print_debug(20, "pyswift_tui | first_layer_has_ref = " + str(first_layer_has_ref))
    print_debug(20, "pyswift_tui |   ref = \"" + str(
            project['data']['scales']['scale_%d' % use_scale]['alignment_stack'][0]['images']['ref'][
                'filename']) + "\"")

    print_debug(10, 80 * "!")
    print("pyswift_tui | run_json_project called with: " + str(
            [alignment_option, use_scale, swiftir_code_mode, start_layer, num_layers, alone]))
    print(
        "\npyswift_tui | run_json_project | Setting align_swiftir.global_swiftir_mode to %s\n" % str(swiftir_code_mode))
    align_swiftir.global_swiftir_mode = swiftir_code_mode

    destination_path = project['data']['destination_path']

    # Evaluate Status of Project and set appropriate flags here:
    proj_status = evaluate_project_status(project)
    finest_scale_done = proj_status['finest_scale_done']
    # allow_scale_climb defaults to False
    allow_scale_climb = False
    # upscale factor defaults to 1.0
    upscale = 1.0
    next_scale = 0
    if use_scale == 0:
        # Get scale_tbd from proj_status:
        scale_tbd = proj_status['scale_tbd']
        # Compute upscale factor:
        if finest_scale_done != 0:
            upscale = (float(finest_scale_done) / float(scale_tbd))
            next_scale = finest_scale_done
        # Allow scale climbing if there is a finest_scale_done
        allow_scale_climb = (finest_scale_done != 0)
    else:
        # Force scale_tbd to be equal to use_scale
        scale_tbd = use_scale
        # Set allow_scale_climb according to status of next coarser scale
        scale_tbd_idx = proj_status['defined_scales'].index(scale_tbd)
        if scale_tbd_idx < len(proj_status['defined_scales']) - 1:
            next_scale = proj_status['defined_scales'][scale_tbd_idx + 1]
            next_scale_key = 'scale_' + str(next_scale)
            upscale = (float(next_scale) / float(scale_tbd))
            allow_scale_climb = proj_status['scales'][next_scale_key]['all_aligned']

    if ((not allow_scale_climb) & (alignment_option != 'init_affine')):
        print_debug(-1, 'pyswift_tui | AlignEM SWiFT Error: Cannot perform alignment_option: %s at scale: %d' % (
                alignment_option, scale_tbd))
        print_debug(-1, 'pyswift_tui |                        Because next coarsest scale is not fully aligned')

        return (project, False)

    if scale_tbd:
        if use_scale:
            print_debug(5,
                        "pyswift_tui | Performing alignment_option: %s  at user specified scale: %d" % (
                        alignment_option, scale_tbd))
            print_debug(5, "pyswift_tui | Finest scale completed: ", finest_scale_done)
            print_debug(5, "pyswift_tui | Next coarsest scale completed: ", next_scale)
            print_debug(5, "pyswift_tui | Upscale factor: ", upscale)
        else:
            print_debug(5, "pyswift_tui | Performing alignment_option: %s  at automatically determined scale: %d" % (
                    alignment_option, scale_tbd))
            print_debug(5, "pyswift_tui | Finest scale completed: ", finest_scale_done)
            print_debug(5, "pyswift_tui | Next coarsest scale completed: ", next_scale)
            print_debug(5, "pyswift_tui | Upscale factor: ", upscale)

        scale_tbd_dir = os.path.join(destination_path, 'scale_' + str(scale_tbd))

        #    ident = swiftir.identityAffine().tolist()
        ident = swiftir.identityAffine()

        s_tbd = project['data']['scales']['scale_' + str(scale_tbd)]['alignment_stack']
        common_length = len(s_tbd)

        # Align Forward Change:
        # Limit the range of the layers based on start_layer and num_layers

        #    if finest_scale_done:
        if next_scale:
            # Copy settings from next coarsest completed scale to tbd:
            #      s_done = project['data']['scales']['scale_'+str(finest_scale_done)]['alignment_stack']
            s_done = project['data']['scales']['scale_' + str(next_scale)]['alignment_stack']
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            common_length = min(len(s_tbd), len(s_done))
            # Copy from coarser to finer
            num_to_copy = num_layers
            if num_layers < 0:
                # Copy to the end
                num_to_copy = common_length - start_layer
            for i in range(num_to_copy):
                s_tbd[start_layer + i]['align_to_ref_method']['method_results'] = copy.deepcopy(
                        s_done[start_layer + i]['align_to_ref_method']['method_results'])

            # project['data']['scales']['scale_'+str(scale_tbd)]['alignment_stack'] = copy.deepcopy(s_done)

        actual_num_layers = num_layers
        if actual_num_layers < 0:
            # Set the actual number of layers to align to the end
            actual_num_layers = common_length - start_layer

        # Align Forward Change:
        range_to_process = list(range(start_layer, start_layer + actual_num_layers))
        print_debug(10, 80 * "@")
        print_debug(10, "pyswift_tui | Range limited to: " + str(range_to_process))
        print_debug(10, 80 * "@")

        #   Copy skip, swim, and match point settings
        for i in range(len(s_tbd)):
            # fix path for base and ref filenames for scale_tbd
            base_fn = os.path.basename(s_tbd[i]['images']['base']['filename'])
            s_tbd[i]['images']['base']['filename'] = os.path.join(scale_tbd_dir, 'img_src', base_fn)
            if i > 0:
                ref_fn = os.path.basename(s_tbd[i]['images']['ref']['filename'])
                s_tbd[i]['images']['ref']['filename'] = os.path.join(scale_tbd_dir, 'img_src', ref_fn)

            atrm = s_tbd[i]['align_to_ref_method']

            # Initialize method_results for skipped or missing method_results
            if s_tbd[i]['skip'] or atrm['method_results'] == {}:
                atrm['method_results']['affine_matrix'] = ident.tolist()
                atrm['method_results']['cumulative_afm'] = ident.tolist()
                atrm['method_results']['snr'] = [0.0]
                atrm['method_results']['snr_report'] = 'SNR: --'

            # set alignment option
            atrm['method_data']['alignment_option'] = alignment_option
            if not 'seleted_method' in atrm:
                atrm['selected_method'] = "Auto Swim Align"

            # Upscale x & y bias values
            if 'bias_x_per_image' in atrm['method_data']:
                atrm['method_data']['bias_x_per_image'] = upscale * atrm['method_data']['bias_x_per_image']
            else:
                atrm['method_data']['bias_x_per_image'] = 0
            if 'bias_y_per_image' in atrm['method_data']:
                atrm['method_data']['bias_y_per_image'] = upscale * atrm['method_data']['bias_y_per_image']
            else:
                atrm['method_data']['bias_y_per_image'] = 0
            # TODO: handle bias values in a better way than this
            x_bias = atrm['method_data']['bias_x_per_image']
            y_bias = atrm['method_data']['bias_y_per_image']

            # check for affine biases
            # if not present then add identity matrix values to dictionary
            if 'bias_rot_per_image' in atrm['method_data'].keys():
                rot_bias = atrm['method_data']['bias_rot_per_image']
            else:
                rot_bias = 0.0
            if 'bias_scale_x_per_image' in atrm['method_data'].keys():
                scale_x_bias = atrm['method_data']['bias_scale_x_per_image']
            else:
                scale_x_bias = 1.0
            if 'bias_scale_y_per_image' in atrm['method_data'].keys():
                scale_y_bias = atrm['method_data']['bias_scale_y_per_image']
            else:
                scale_y_bias = 1.0
            if 'bias_skew_x_per_image' in atrm['method_data'].keys():
                skew_x_bias = atrm['method_data']['bias_skew_x_per_image']
            else:
                skew_x_bias = 0.0
            atrm['method_data']['bias_rot_per_image'] = rot_bias
            atrm['method_data']['bias_scale_x_per_image'] = scale_x_bias
            atrm['method_data']['bias_scale_y_per_image'] = scale_y_bias
            atrm['method_data']['bias_skew_x_per_image'] = skew_x_bias

            # put updated atrm into s_tbd
            s_tbd[i]['align_to_ref_method'] = atrm

            # if there are match points, copy and scale them for scale_tbd
            if atrm['selected_method'] == 'Match Point Align':
                mp_ref = (np.array(s_tbd[i]['images']['ref']['metadata']['match_points']) * upscale).tolist()
                mp_base = (np.array(s_tbd[i]['images']['base']['metadata']['match_points']) * upscale).tolist()
                s_tbd[i]['images']['ref']['metadata']['match_points'] = mp_ref
                s_tbd[i]['images']['base']['metadata']['match_points'] = mp_base

        if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
            # Copy the affine_matrices from s_tbd and scale the translation part to use as the initial guess for s_tbd
            afm_tmp = np.array([al['align_to_ref_method']['method_results']['affine_matrix'] for al in s_tbd])
            print_debug(50, '\npyswift_tui | >>>>>>> Original affine matrices: \n\n')
            print_debug(50, str(afm_tmp))
            afm_scaled = afm_tmp.copy()
            afm_scaled[:, :, 2] = afm_scaled[:, :, 2] * upscale
            print_debug(50, '\npyswift_tui | >>>>>>> Scaled affine matrices: \n\n')
            print_debug(50, str(afm_scaled))
        #      exit(0)
        else:
            afm_scaled = None

        # Now setup the alignment for s_tbd
        align_list = []
        align_dir = os.path.join(scale_tbd_dir, 'img_aligned', '')
        # make dir path for align_dir and ignore error if it already exists
        try:
            os.makedirs(align_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        for i in range(1, len(s_tbd)):
            if not s_tbd[i]['skip']:
                #        im_sta_fn = s_tbd[i]['images']['ref']['filename']
                #        im_mov_fn = s_tbd[i]['images']['base']['filename']
                if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
                    atrm = s_tbd[i]['align_to_ref_method']

                    # Align Forward Change:
                    align_proc = align_swiftir.alignment_process(align_dir=align_dir, layer_dict=s_tbd[i],
                                                                 init_affine_matrix=afm_scaled[i])
                #          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
                else:
                    # Align Forward Change:
                    align_proc = align_swiftir.alignment_process(align_dir=align_dir, layer_dict=s_tbd[i],
                                                                 init_affine_matrix=ident)
                #          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=ident)
                # Align Forward Change:
                align_list.append({'i': i, 'proc': align_proc, 'do': (i in range_to_process)})

        print_debug(10, 80 * "#")
        print_debug(10, "pyswift_tui | Before aligning, align_list: " + str(align_list))
        print_debug(10, 80 * "#")

        # Initialize c_afm to identity matrix
        c_afm = swiftir.identityAffine()

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            print_debug(10, 80 * "@")
            print_debug(10,
                        "pyswift_tui | Not starting at zero, initialize the c_afm to non-identity from previous aligned image")
            print_debug(10, 80 * "@")
            # Set the c_afm to the afm of the previously aligned image
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            prev_aligned_index = range_to_process[0] - 1
            method_results = s_tbd[prev_aligned_index]['align_to_ref_method']['method_results']
            c_afm = method_results[
                'cumulative_afm']  # Note that this might not be the right type (it's a list not a matrix)

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            print_debug(10, 80 * "@")
            print_debug(10, "pyswift_tui | Initialize to non-zero biases")
            print_debug(10, 80 * "@")

        # Calculate AFM for each align_item (i.e for each ref-base pair of images)
        for item in align_list:

            if item['do']:
                align_item = item['proc']
                print_debug(4, '\npyswift_tui | Aligning: %s %s' % (
                        os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))
                # align_item.cumulative_afm = c_afm
                c_afm = align_item.align(c_afm, save=False)
            else:
                align_item = item['proc']
                print_debug(50, '\npyswift_tui | Not Aligning: %s %s' % (
                        os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))

        '''
        c_afm_init = swiftir.identityAffine()

        # Compute Cafms across the stack and null trends in c_afm if requested
        # Note: This is necessarily a serial process
        null_biases = project['data']['scales']['scale_'+str(scale_tbd)]['null_cafm_trends']
        c_afm_init = SetStackCafm(s_tbd, null_biases)

        # Save analysis of bias data:
        bias_data_path = os.path.join(destination_path,'scale_'+str(scale_tbd),'bias_data')
        save_bias_analysis(s_tbd, bias_data_path)


        # Save all final aligned images:
        # Note: This should be parallelized via TaskQueue and job_apply_affine.py

        print_debug(50,"\nSaving all aligned images...\n")

        # Save possibly unmodified first image into align_dir
        im_sta_fn = s_tbd[0]['images']['base']['filename']
        base_fn = os.path.basename(im_sta_fn)
        al_fn = os.path.join(align_dir,base_fn)
        print_debug(50,"Saving first image in align dir: ", al_fn)
        im_sta = swiftir.loadImage(im_sta_fn)

        rect = None
        if project['data']['scales']['scale_'+str(scale_tbd)]['use_bounding_rect']:
          siz = im_sta.shape
    #      rect = BoundingRect(align_list,siz)
          rect = BoundingRect(s_tbd)
        print_debug(10,'Bounding Rectangle: %s' % (str(rect)))

        print_debug(10,"Applying affine: " + str(c_afm_init))
        im_aligned = swiftir.affineImage(c_afm_init,im_sta,rect=rect,grayBorder=True)
        del im_sta
        print_debug(10,"Saving image: " + al_fn)
        swiftir.saveImage(im_aligned,al_fn)
        if not 'aligned' in s_tbd[0]['images']:
          s_tbd[0]['images']['aligned'] = {}
        s_tbd[0]['images']['aligned']['filename'] = al_fn

        i = 0
        for item in align_list:
          if item['do']:
            align_idx = item['i']
            align_item = item['proc']
            # Save the image:
            align_item.saveAligned(rect=rect, grayBorder=True)

          # Add aligned image record to layer dictionary for this stack item
            base_fn = os.path.basename(s_tbd[align_idx]['images']['base']['filename'])
            al_fn = os.path.join(align_dir,base_fn)
            s_tbd[align_idx]['images']['aligned'] = {}
            s_tbd[align_idx]['images']['aligned']['filename'] = al_fn
            s_tbd[align_idx]['images']['aligned']['metadata'] = {}
            s_tbd[align_idx]['images']['aligned']['metadata']['match_points'] = []
            s_tbd[align_idx]['images']['aligned']['metadata']['annotations'] = []

          i+=1
        '''

        print_debug(1, 30 * "|=|")
        print_debug(1, "pyswift_tui | Returning True")
        print_debug(1, 30 * "|=|")

        # The code generally returns "True"
        return (project, True)

    else:  # if scale_tbd:

        print_debug(1, 30 * "|=|")
        print_debug(1, "pyswift_tui | Returning False")
        print_debug(1, 30 * "|=|")

        return (project, False)


def print_command_line_syntax(args):
    print_debug(-1, "")
    print_debug(-1, 'Usage: %s [ options ] inproject.json outproject.json' % (args[0]))
    print_debug(-1, 'Description:')
    print_debug(-1, '  Open swiftir project file and perform alignment operations.')
    print_debug(-1, '  Result is written to output project file.')
    print_debug(-1, 'Options:')
    print_debug(-1, '  -code m             : m = c | python')
    print_debug(-1, '  -scale #            : # = first layer number (starting at 0), defaults to 0')
    print_debug(-1, '  -start #            : # = first layer number (starting at 0), defaults to 0')
    print_debug(-1, '  -count #            : # = number of layers (-1 for all remaining), defaults to -1')
    print_debug(-1, '  -debug #            : # = debug level (0-100, larger numbers produce more output)')
    print_debug(-1, '  -alignment_option o : o = init_affine | refine_affine | apply_affine')
    print_debug(-1, '  -master             : Run as master process .. generate sub-data-models and delegate')
    print_debug(-1, '  -worker             : Run as worker process .. work only on this particular data model')
    print_debug(-1, 'Arguments:')
    print_debug(-1, '  inproject.json      : input project file name (opened for reading only)')
    print_debug(-1, '  outproject.json     : output project file name (opened for writing and overwritten)')
    print_debug(-1, "")


if (__name__ == '__main__'):
    print("Running " + __file__ + ".__main__()")

    if (len(sys.argv) < 3):
        print_command_line_syntax(sys.argv)
        exit(1)

    proj_ifn = sys.argv[-2]
    proj_ofn = sys.argv[-1]

    use_scale = 0
    alignment_option = 'refine_affine'
    scale_tbd = 0
    finest_scale_done = 0
    swiftir_code_mode = 'python'
    start_layer = 0
    num_layers = -1
    run_as_master = False
    run_as_worker = False
    alone = False

    # Scan arguments (excluding program name and last 2 file names)
    i = 1
    while i < len(sys.argv) - 2:
        print("Processing option " + sys.argv[i])
        if sys.argv[i] == '-master':
            run_as_master = True
            # No need to increment i because no additional arguments were taken
        elif sys.argv[i] == '-worker':
            run_as_worker = True
            alone = True
            # No need to increment i because no additional arguments were taken
        elif sys.argv[i] == '-scale':
            i += 1  # Increment to get the argument
            use_scale = int(sys.argv[i])
        elif sys.argv[i] == '-code':
            i += 1  # Increment to get the argument
            # align_swiftir.global_swiftir_mode = str(sys.argv[i+1])
            swiftir_code_mode = str(sys.argv[i])
        elif sys.argv[i] == '-alignment_option':
            i += 1  # Increment to get the argument
            alignment_option = sys.argv[i]
        elif sys.argv[i] == '-start':
            i += 1  # Increment to get the argument
            start_layer = int(sys.argv[i])
        elif sys.argv[i] == '-count':
            i += 1  # Increment to get the argument
            num_layers = int(sys.argv[i])
        elif sys.argv[i] == '-debug':
            i += 1  # Increment to get the argument
            debug_level = int(sys.argv[i])
        else:
            print("\nImproper argument list: " + str(argv) + "\n")
            print_command_line_syntax(sys.argv)
            exit(1)
        i += 1  # Increment to get the next option

    # Load the JSON project regardless of the mode
    fp = open(proj_ifn, 'r')
    d = json.load(fp)
    need_to_write_json = False

    if run_as_worker:

        # This task was called to just process one layer
        print_debug(1, "pyswift_tui | Running as a worker for just one layer with PID=" + str(os.getpid()))
        # Chop up the JSON project so that the only layer is the one requested
        for scale_key in d['data']['scales'].keys():
            scale = d['data']['scales'][scale_key]
            # Set the entire stack equal to the single layer that needs to be aligned (including both ref and base)
            scale['alignment_stack'] = [scale['alignment_stack'][start_layer]]

        # Call run_json_project with the partial data model and the "alone" flag set to True
        d, need_to_write_json = run_json_project(project=d,
                                                 alignment_option=alignment_option,
                                                 use_scale=use_scale,
                                                 swiftir_code_mode=swiftir_code_mode,
                                                 start_layer=start_layer,
                                                 num_layers=num_layers,
                                                 alone=True)

        # When run as a worker, always return the data model to the master on stdout
        print("pyswift_tui | NEED TO RETURN DATA MODEL TO MASTER from PID=" + str(os.getpid()))

    elif run_as_master:

        # This task was called to process the entire stack in parallel mode
        # This will create a task manager instance and have it run the jobs

        print_debug(-1, "pyswift_tui | Warning: The \"run_as_master\" flag isn't supported yet.")
        exit(99)

    else:

        # This task was called to process the entire stack in serial mode
        print_debug(1, "pyswift_tui | Running in serial mode with PID=" + str(os.getpid()))

        align_swiftir.debug_level = debug_level
        print_debug(20, "pyswift_tui | Before RJP: " + str(
                [d['data']['current_scale'], alignment_option, use_scale, swiftir_code_mode, start_layer, num_layers,
                 alone]))

        d, need_to_write_json = run_json_project(project=d,
                                                 alignment_option=alignment_option,
                                                 use_scale=use_scale,
                                                 swiftir_code_mode=swiftir_code_mode,
                                                 start_layer=start_layer,
                                                 num_layers=num_layers,
                                                 alone=False)
        if need_to_write_json:
            # Write out updated json project file
            print_debug(50, "pyswift_tui | Writing project to file: ", proj_ofn)
            ofp = open(proj_ofn, 'w')
            json.dump(d, ofp, sort_keys=True, indent=2, separators=(',', ': '))

    '''
    cafm = np.array([ i['align_to_ref_method']['method_results']['cumulative_afm'] for i in sn if i['align_to_ref_method']['method_results'].get('cumulative_afm') ])

    cx = cafm[:,:,2][:,0]
    cy = cafm[:,:,2][:,1]

    (mx,bx,r,p,stderr) = lin_fit(np.arange(len(cx)),cx)
    (my,by,r,p,stderr) = lin_fit(np.arange(len(cy)),cy)
    xl = mx*np.arange(len(cx))+bx
    yl = my*np.arange(len(cy))+by

    print_debug(50,"(mx,bx): ",mx,bx)
    print_debug(50,"(my,by): ",my,by)


    # plot data
    p = plt.scatter(np.arange(len(cx)),cx)
    p = plt.scatter(np.arange(len(cy)),cy)
    p = plt.scatter(np.arange(len(cx)),xl)
    p = plt.scatter(np.arange(len(cy)),yl)
    plt.show()
    '''
