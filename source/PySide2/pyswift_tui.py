#!/usr/bin/env python2.7

import sys
import os
import errno
import numpy as np
import scipy.stats as sps
import swiftir
import align_swiftir
import json
import copy
import matplotlib.pyplot as plt

# This is monotonic (0 to 100) with the amount of output:
debug_level = 50  # A larger value prints more stuff

# Using the Python version does not work because the Python 3 code can't
# even be parsed by Python2. It could be dynamically compiled, or use the
# alternate syntax, but that's more work than it's worth for now.
if sys.version_info >= (3, 0):
    # print ( "Python 3: Supports arbitrary arguments via print")
    #def print_debug ( level, *ds ):
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
def print_debug ( level, p1=None, p2=None, p3=None, p4=None, p5=None ):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
    global debug_level
    if level <= debug_level:
      if p1 == None:
        print ( "" )
      elif p2 == None:
        print ( str(p1) )
      elif p3 == None:
        print ( str(p1) + str(p2) )
      elif p4 == None:
        print (str (p1) + str (p2) + str (p3))
      elif p5 == None:
        print (str (p1) + str (p2) + str (p3) + str(p4))
      else:
        print ( str(p1) + str(p2) + str(p3) + str(p4) + str(p5) )


# Do Linear Regression of X,Y data
def lin_fit(x,y):

  (m,b,r,p,stderr) = sps.linregress(x,y)
  print_debug(90,'linear regression:')
  print_debug(90,'  slope:',m)
  print_debug(90,'  intercept:',b)
  print_debug(90,'  r:',r)
  print_debug(90,'  p:',p)
  print_debug(90,'  stderr:',stderr)
  print_debug(90,'')

  return(m,b,r,p,stderr)

#align_swiftir.global_swiftir_mode = 'c'
align_swiftir.global_swiftir_mode = 'python'


def BiasFuncs(align_list,bias_funcs=None):
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



def BiasMat(x,bias_funcs):

  xdot = np.array([4.0,3.0,2.0,1.0])

  p = bias_funcs['skew_x']
  dp = p[:-1]*xdot
  fdp = np.poly1d(dp)
  skew_x_bias = -fdp(x)

  p = bias_funcs['scale_x']
  dp = p[:-1]*xdot
  fdp = np.poly1d(dp)
  scale_x_bias = 1-fdp(x)

  p = bias_funcs['scale_y']
  dp = p[:-1]*xdot
  fdp = np.poly1d(dp)
  scale_y_bias = 1-fdp(x)

  p = bias_funcs['rot']
  dp = p[:-1]*xdot
  fdp = np.poly1d(dp)
  rot_bias = -fdp(x)

  p = bias_funcs['x']
  dp = p[:-1]*xdot
  fdp = np.poly1d(dp)
  x_bias = -fdp(x)

  p = bias_funcs['y']
  dp = p[:-1]*xdot
  fdp = np.poly1d(dp)
  y_bias = -fdp(x)

  # Create skew, scale, rot, and tranlation matrices
  skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0],[0.0, 1.0, 0.0]])
  scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0],[0.0, scale_y_bias, 0.0]])
  rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0],[np.sin(rot_bias), np.cos(rot_bias), 0.0]])
  trans_bias_mat = np.array([[1.0, 0.0, x_bias],[0.0, 1.0, y_bias]])

  bias_mat = swiftir.identityAffine()

  # Compose bias matrix as skew*scale*rot*trans
  bias_mat = swiftir.composeAffine(skew_x_bias_mat,bias_mat)
  bias_mat = swiftir.composeAffine(scale_bias_mat,bias_mat)
  bias_mat = swiftir.composeAffine(rot_bias_mat,bias_mat)
  bias_mat = swiftir.composeAffine(trans_bias_mat,bias_mat)

  return bias_mat



def InitCafm(bias_funcs):

  init_skew_x = -bias_funcs['skew_x'][4]
  init_scale_x = 1.0/bias_funcs['scale_x'][4]
  init_scale_y = 1.0/bias_funcs['scale_y'][4]
  init_rot = -bias_funcs['rot'][4]
  init_x = -bias_funcs['x'][4]
  init_y = -bias_funcs['y'][4]

  # Create skew, scale, rot, and tranlation matrices
  init_skew_x_mat = np.array([[1.0, init_skew_x, 0.0],[0.0, 1.0, 0.0]])
  init_scale_mat = np.array([[init_scale_x, 0.0, 0.0],[0.0, init_scale_y, 0.0]])
  init_rot_mat = np.array([[np.cos(init_rot), -np.sin(init_rot), 0.0],[np.sin(init_rot), np.cos(init_rot), 0.0]])
  init_trans_mat = np.array([[1.0, 0.0, init_x],[0.0, 1.0, init_y]])

  c_afm_init = swiftir.identityAffine()

  # Compose bias matrix as skew*scale*rot*trans
  c_afm_init = swiftir.composeAffine(init_skew_x_mat,c_afm_init)
  c_afm_init = swiftir.composeAffine(init_scale_mat,c_afm_init)
  c_afm_init = swiftir.composeAffine(init_rot_mat,c_afm_init)
  c_afm_init = swiftir.composeAffine(init_trans_mat,c_afm_init)

  return c_afm_init



def ApplyBiasFuncs(align_list):

  # Iteratively determine and null out bias in c_afm
  print_debug(50,"\nComputing and Nulling Biases...\n")
  bias_funcs = BiasFuncs(align_list)
  c_afm_init = InitCafm(bias_funcs)
  bias_iters = 2
  for bi in range(bias_iters):
    c_afm = c_afm_init
    for item in align_list:
      align_idx = item['i']
      align_item = item['proc']
      bias_mat = BiasMat(align_idx,bias_funcs)
      c_afm = align_item.setCafm(c_afm,bias_mat=bias_mat)
    if bi < bias_iters-1:
      bias_funcs = BiasFuncs(align_list,bias_funcs=bias_funcs)

  return c_afm_init



def BoundingRect(align_list,siz):

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

  # Get int values for scales in a way compatible with old ('1') and new ('scale_1') style for keys
  scales = sorted([ int(s.split('scale_')[-1]) for s in project['data']['scales'].keys() ])
  
  proj_status = {}
  proj_status['defined_scales'] = scales
  proj_status['finest_scale_done'] = 0
  proj_status['scale_tbd'] = 0
  proj_status['scales'] = {}
  for scale in scales:
    scale_key = 'scale_'+str(scale)
    proj_status['scales'][scale_key] = {}

    alstack = project['data']['scales'][scale_key]['alignment_stack']
    num_alstack = len(alstack)
    
#    afm_list = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in alstack if 'affine_matrix' in i['align_to_ref_method']['method_results'] ])

    proj_status['scales'][scale_key]['aligned_stat'] = np.array([ 'affine_matrix' in item['align_to_ref_method']['method_results'] for item in alstack ])
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
  


def run_json_project ( project=None, alignment_option='init_affine', use_scale=0, swiftir_code_mode='python', start_layer=0, num_layers=-1 ):
  '''Align one scale - either the one specified in "use_scale" or the coarsest without an AFM.'''

  print_debug(10,80*"!" )
  print_debug(10,"run_json_project called with: " + str([alignment_option, use_scale, swiftir_code_mode, start_layer, num_layers]) )
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
  if use_scale==0:
    # Get scale_tbd from proj_status:
    scale_tbd = proj_status['scale_tbd']
    # Compute upscale factor:
    if finest_scale_done != 0:
      upscale = (float(finest_scale_done)/float(scale_tbd))
      next_scale = finest_scale_done
    # Allow scale climbing if there is a finest_scale_done
    allow_scale_climb = (finest_scale_done != 0)
  else:
    # Force scale_tbd to be equal to use_scale
    scale_tbd = use_scale
    # Set allow_scale_climb according to status of next coarser scale
    scale_tbd_idx = proj_status['defined_scales'].index(scale_tbd)
    if scale_tbd_idx < len(proj_status['defined_scales'])-1:
      next_scale = proj_status['defined_scales'][scale_tbd_idx+1]
      next_scale_key = 'scale_'+str(next_scale)
      upscale = (float(next_scale)/float(scale_tbd))
      allow_scale_climb = proj_status['scales'][next_scale_key]['all_aligned']

  if ((not allow_scale_climb) & (alignment_option!='init_affine')):
      print('AlignEM SWiFT Error: Cannot perform alignment_option: %s at scale: %d' % (alignment_option,scale_tbd))
      print('                       Because next coarsest scale is not fully aligned')

      return (project,False)
    

  if scale_tbd:
    if use_scale:
      print_debug(50,"Performing alignment_option: %s  at user specified scale: %d" % (alignment_option,scale_tbd))
      print_debug(50,"Finest scale completed: ",finest_scale_done)
      print_debug(50,"Next coarsest scale completed: ",next_scale)
      print_debug(50,"Upscale factor: ",upscale)
    else:
      print_debug(50,"Performing alignment_option: %s  at automatically determined scale: %d" % (alignment_option,scale_tbd))
      print_debug(50,"Finest scale completed: ",finest_scale_done)
      print_debug(50,"Next coarsest scale completed: ",next_scale)
      print_debug(50,"Upscale factor: ",upscale)

    scale_tbd_dir = os.path.join(destination_path,'scale_'+str(scale_tbd))

#    ident = swiftir.identityAffine().tolist()
    ident = swiftir.identityAffine()

#    if finest_scale_done:
    if next_scale:
      # Copy settings from next coarsest completed scale to tbd:
#      s_done = project['data']['scales']['scale_'+str(finest_scale_done)]['alignment_stack']
      s_done = project['data']['scales']['scale_'+str(next_scale)]['alignment_stack']
      project['data']['scales']['scale_'+str(scale_tbd)]['alignment_stack'] = copy.deepcopy(s_done)

    s_tbd = project['data']['scales']['scale_' + str(scale_tbd)]['alignment_stack']

    # Align Forward Change:
    # Limit the range of the layers based on start_layer and num_layers
    actual_num_layers = num_layers
    if actual_num_layers < 0:
      # Set the actual number of layers to align to the end
      actual_num_layers = len(s_tbd) - start_layer
    #if actual_num_layers < 2:  # For some reason the TUI won't align just one layer from the start
    #  actual_num_layers = 2    # For some reason the TUI won't align just one layer from the start
    # Align Forward Change:
    range_to_process = list(range(start_layer, start_layer+actual_num_layers))
    print_debug(10,80 * "@")
    print_debug(10,"Range limited to: " + str(range_to_process) + ", but seems to align 1 more ...")
    print_debug(10,80 * "@")

    #   Copy skip, swim, and match point settings
    for i in range(len(s_tbd)):
      # fix path for base and ref filenames for scale_tbd
      base_fn = os.path.basename(s_tbd[i]['images']['base']['filename'])
      s_tbd[i]['images']['base']['filename'] = os.path.join(scale_tbd_dir,'img_src',base_fn)
      if i>0:
        ref_fn = os.path.basename(s_tbd[i]['images']['ref']['filename'])
        s_tbd[i]['images']['ref']['filename'] = os.path.join(scale_tbd_dir,'img_src',ref_fn)

      atrm = s_tbd[i]['align_to_ref_method']

      # Initialize method_results for skipped or missing method_results
      if s_tbd[i]['skip'] or atrm['method_results'] == {}:
        atrm['method_results']['affine_matrix'] = ident.tolist()
        atrm['method_results']['cumulative_afm'] = ident.tolist()
        atrm['method_results']['snr'] = 0.0

      # set alignment option
      atrm['method_data']['alignment_option'] = alignment_option

      # Upscale x & y bias values
      atrm['method_data']['bias_x_per_image'] = upscale*atrm['method_data']['bias_x_per_image']
      atrm['method_data']['bias_y_per_image'] = upscale*atrm['method_data']['bias_y_per_image']
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
        mp_ref = (np.array(s_tbd[i]['images']['ref']['metadata']['match_points'])*upscale).tolist()
        mp_base = (np.array(s_tbd[i]['images']['base']['metadata']['match_points'])*upscale).tolist()
        s_tbd[i]['images']['ref']['metadata']['match_points'] = mp_ref
        s_tbd[i]['images']['base']['metadata']['match_points'] = mp_base


    if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
      # Copy the affine_matrices from s_tbd and scale the translation part to use as the initial guess for s_tbd
      afm_tmp = np.array([ al['align_to_ref_method']['method_results']['affine_matrix'] for al in s_tbd ])
      print('\n>>>>>>> Original affine matrices: \n\n')
      print(str(afm_tmp))
      afm_scaled = afm_tmp.copy()
      afm_scaled[:,:,2] = afm_scaled[:,:,2]*upscale
      print('\n>>>>>>> Scaled affine matrices: \n\n')
      print(str(afm_scaled))
#      exit(0)
    else:
      afm_scaled = None

    # Now setup the alignment for s_tbd
    align_list = []
    align_dir = os.path.join(scale_tbd_dir,'img_aligned','')
    # make dir path for align_dir and ignore error if it already exists
    try:
        os.makedirs(align_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    bias_data_path = os.path.join(destination_path,'scale_'+str(scale_tbd),'bias_data')
    snr_file = open(os.path.join(bias_data_path,'snr_1.dat'),'w')
    bias_x_file = open(os.path.join(bias_data_path,'bias_x_1.dat'),'w')
    bias_y_file = open(os.path.join(bias_data_path,'bias_y_1.dat'),'w')
    bias_rot_file = open(os.path.join(bias_data_path,'bias_rot_1.dat'),'w')
    bias_scale_x_file = open(os.path.join(bias_data_path,'bias_scale_x_1.dat'),'w')
    bias_scale_y_file = open(os.path.join(bias_data_path,'bias_scale_y_1.dat'),'w')
    bias_skew_x_file = open(os.path.join(bias_data_path,'bias_skew_x_1.dat'),'w')
    bias_det_file = open(os.path.join(bias_data_path,'bias_det_1.dat'),'w')
    afm_file = open(os.path.join(bias_data_path,'afm_1.dat'),'w')
    c_afm_file = open(os.path.join(bias_data_path,'c_afm_1.dat'),'w')

    if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
      # Create skew, scale, rot, and translation matrices
      skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0],[0.0, 1.0, 0.0]])
      scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0],[0.0, scale_y_bias, 0.0]])
      rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0],[np.sin(rot_bias), np.cos(rot_bias), 0.0]])
      trans_bias_mat = np.array([[1.0, 0.0, x_bias],[0.0, 1.0, y_bias]])

      # Compose bias matrix as skew*scale*rot*trans
      bias_mat = swiftir.identityAffine()
      bias_mat = swiftir.composeAffine(skew_x_bias_mat,bias_mat)
      bias_mat = swiftir.composeAffine(scale_bias_mat,bias_mat)
      bias_mat = swiftir.composeAffine(rot_bias_mat,bias_mat)
      bias_mat = swiftir.composeAffine(trans_bias_mat,bias_mat)
      print_debug(90,"Refine affine using bias mat:\n", bias_mat)

    for i in range(1,len(s_tbd)):
      if not s_tbd[i]['skip']:
        im_sta_fn = s_tbd[i]['images']['ref']['filename']
        im_mov_fn = s_tbd[i]['images']['base']['filename']
        if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
          atrm = s_tbd[i]['align_to_ref_method']
          x_bias = atrm['method_data']['bias_x_per_image']
          y_bias = atrm['method_data']['bias_y_per_image']
          rot_bias = atrm['method_data']['bias_rot_per_image']
          scale_x_bias = atrm['method_data']['bias_scale_x_per_image']
          scale_y_bias = atrm['method_data']['bias_scale_y_per_image']
          skew_x_bias = atrm['method_data']['bias_skew_x_per_image']
          # Create skew, scale, rot, and tranlation matrices
          skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0],[0.0, 1.0, 0.0]])
          scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0],[0.0, scale_y_bias, 0.0]])
          rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0],[np.sin(rot_bias), np.cos(rot_bias), 0.0]])
          trans_bias_mat = np.array([[1.0, 0.0, x_bias],[0.0, 1.0, y_bias]])

          # Compose bias matrix as skew*scale*rot*trans
          bias_mat = swiftir.identityAffine()
          bias_mat = swiftir.composeAffine(skew_x_bias_mat,bias_mat)
          bias_mat = swiftir.composeAffine(scale_bias_mat,bias_mat)
          bias_mat = swiftir.composeAffine(rot_bias_mat,bias_mat)
          bias_mat = swiftir.composeAffine(trans_bias_mat,bias_mat)

          # Align Forward Change:
          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
          # align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=swiftir.composeAffine(bias_mat,afm_scaled[i]))
        else:
          # Align Forward Change:
          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=ident)
        # Align Forward Change:
        align_list.append({'i':i, 'proc':align_proc, 'do':(i in range_to_process)})

    # Initialize c_afm to identity matrix
    c_afm = swiftir.identityAffine()

    # Align Forward Change:
    if range_to_process[0] != 0:
      print_debug(10,80 * "@")
      print_debug(10,"Not starting at zero, initialize the c_afm to non-identity from previous aligned image")
      print_debug(10,80 * "@")
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
      c_afm = method_results['cumulative_afm']  # Note that this might not be the right type (it's a list not a matrix)

    # Setup for no bias
    rot_bias = 0.0
    scale_x_bias = 1.0
    scale_y_bias = 1.0
    skew_x_bias = 0.0
    x_bias = 0.0
    y_bias = 0.0

    # Align Forward Change:
    if range_to_process[0] != 0:
      print_debug(10,80 * "@")
      print_debug(10,"Initialize to non-zero biases")
      print_debug(10,80 * "@")
      # Set the biases from the previously aligned image
      prev_aligned_index = range_to_process[0] - 1
      method_data = s_tbd[prev_aligned_index]['align_to_ref_method']['method_data']
      x_bias = method_data['bias_x_per_image']
      y_bias = method_data['bias_y_per_image']
      rot_bias = method_data['bias_rot_per_image']
      scale_x_bias = method_data['bias_scale_x_per_image']
      scale_y_bias = method_data['bias_scale_y_per_image']
      skew_x_bias = method_data['bias_skew_x_per_image']

    '''
    rot_bias_mat = np.array([[np.cos(rot_bias), -np.sin(rot_bias), 0.0],[np.sin(rot_bias), np.cos(rot_bias), 0.0]])
    scale_bias_mat = np.array([[scale_x_bias, 0.0, 0.0],[0.0, scale_y_bias, 0.0]])
    skew_x_bias_mat = np.array([[1.0, skew_x_bias, 0.0],[0.0, 1.0, 0.0]])
    trans_bias_mat = np.array([[1.0, 0.0, x_bias],[0.0, 1.0, y_bias]])

    bias_mat = swiftir.identityAffine()

    bias_mat = swiftir.composeAffine(skew_x_bias_mat,bias_mat)
    bias_mat = swiftir.composeAffine(scale_bias_mat,bias_mat)
    bias_mat = swiftir.composeAffine(rot_bias_mat,bias_mat)
    bias_mat = swiftir.composeAffine(trans_bias_mat,bias_mat)
    '''

    # Align the images
    for item in align_list:

      if item['do']:
        align_item = item ['proc']
        print_debug(20,'\n\nAligning: %s %s\n' % (os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))
        # align_item.cumulative_afm = c_afm
        c_afm = align_item.align(c_afm,save=False)
      else:
        align_item = item ['proc']
        print_debug(20,'\n\nNot Aligning: %s %s\n' % (os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))


    c_afm_init = swiftir.identityAffine()

    # Null Trends in c_afm if requested
    if project['data']['scales']['scale_'+str(scale_tbd)]['null_cafm_trends']:
      c_afm_init = ApplyBiasFuncs(align_list)


    # Save all final aligned images:
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
      rect = BoundingRect(align_list,siz)
    print_debug(10,'Bounding Rectangle: %s' % (str(rect)))

    print_debug(10,"Applying affine: " + str(c_afm_init))
    im_aligned = swiftir.affineImage(c_afm_init,im_sta,rect=rect,grayBorder=True)
    print_debug(10,"Saving image: " + al_fn)
    swiftir.saveImage(im_aligned,al_fn)
    if not 'aligned' in s_tbd[0]['images']:
      s_tbd[0]['images']['aligned'] = {}
    s_tbd[0]['images']['aligned']['filename'] = al_fn

    skew_x_array = np.zeros((len(align_list),2))
    scale_x_array = np.zeros((len(align_list),2))
    scale_y_array = np.zeros((len(align_list),2))
    rot_array = np.zeros((len(align_list),2))
    x_array = np.zeros((len(align_list),2))
    y_array = np.zeros((len(align_list),2))

    i = 0
    for item in align_list:
      if item['do']:
        align_idx = item['i']
        align_item = item['proc']
        # Save the image:
        align_item.saveAligned(rect=rect, grayBorder=True)

      # Retrieve alignment result
        recipe = align_item.recipe
        snr = recipe.ingredients[-1].snr
        afm = recipe.ingredients[-1].afm
        c_afm = align_item.cumulative_afm

      # Store custom bias values in the dictionary for this stack item
        atrm = s_tbd[align_idx]['align_to_ref_method']
        atrm['method_data']['bias_x_per_image'] = x_bias
        atrm['method_data']['bias_y_per_image'] = y_bias
        atrm['method_data']['bias_rot_per_image'] = rot_bias
        atrm['method_data']['bias_scale_x_per_image'] = scale_x_bias
        atrm['method_data']['bias_scale_y_per_image'] = scale_y_bias
        atrm['method_data']['bias_skew_x_per_image'] = skew_x_bias

      # Add results to layer dictionary for this stack item
        base_fn = os.path.basename(s_tbd[align_idx]['images']['base']['filename'])
        al_fn = os.path.join(align_dir,base_fn)
        s_tbd[align_idx]['images']['aligned'] = {}
        s_tbd[align_idx]['images']['aligned']['filename'] = al_fn
        s_tbd[align_idx]['images']['aligned']['metadata'] = {}
        s_tbd[align_idx]['images']['aligned']['metadata']['match_points'] = []
        s_tbd[align_idx]['images']['aligned']['metadata']['annotations'] = []
        method_results = s_tbd[align_idx]['align_to_ref_method']['method_results']
        method_results['snr'] = snr[0]
        method_results['affine_matrix'] = afm.tolist()
        method_results['cumulative_afm'] = c_afm.tolist()

        # Compute and save final biases
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

        snr_file.write('%d %.6g\n' % (i, snr[0]))
        bias_x_file.write('%d %.6g\n' % (i, c_afm[0,2]))
        bias_y_file.write('%d %.6g\n' % (i, c_afm[1,2]))
        bias_rot_file.write('%d %.6g\n' % (i, rot))
        bias_scale_x_file.write('%d %.6g\n' % (i, scale_x))
        bias_scale_y_file.write('%d %.6g\n' % (i, scale_y))
        bias_skew_x_file.write('%d %.6g\n' % (i, skew_x))
        bias_det_file.write('%d %.6g\n' % (i, det))

        afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (i, afm[0,0], afm[0,1], afm[0,2], afm[1,0], afm[1,1], afm[1,2]))
        c_afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (i, c_afm[0,0], c_afm[0,1], c_afm[0,2], c_afm[1,0], c_afm[1,1], c_afm[1,2]))

        print_debug(2, 'AFM:  %d %.6g %.6g %.6g %.6g %.6g %.6g' % (i, afm[0,0], afm[0,1], afm[0,2], afm[1,0], afm[1,1], afm[1,2]))
        print_debug(2, 'CAFM: %d %.6g %.6g %.6g %.6g %.6g %.6g' % (i, c_afm[0,0], c_afm[0,1], c_afm[0,2], c_afm[1,0], c_afm[1,1], c_afm[1,2]))

      i+=1

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

    print_debug(1, 30 * "|=|")
    print_debug(1, "Returning True")
    print_debug(1, 30 * "|=|")

    # The code generally returns "True"
    return (project,True)

  else:  # if scale_tbd:

    print_debug(1, 30 * "|=|")
    print_debug(1, "Returning False")
    print_debug(1, 30 * "|=|")

    return (project,False)

def print_command_line_syntax ( args ):
  print_debug ( -1, "" )
  print_debug ( -1, 'Usage: %s [ options ] inproject.json outproject.json' % (args[0]) )
  print_debug ( -1, 'Description:' )
  print_debug ( -1, '  Open swiftir project file and perform alignment operations.' )
  print_debug ( -1, '  Result is written to output project file.' )
  print_debug ( -1, 'Options:' )
  print_debug ( -1, '  -code m             : m = c | python' )
  print_debug ( -1, '  -start s            : s = first layer number (starting at 0), defaults to 0' )
  print_debug ( -1, '  -count n            : n = number of layers (-1 for all remaining), defaults to -1' )
  print_debug ( -1, '  -debug d            : d = debug level (0-100, larger numbers produce more output)' )
  print_debug ( -1, '  -alignment_option o : o = init_affine | refine_affine | apply_affine' )
  print_debug ( -1, 'Arguments:' )
  print_debug ( -1, '  inproject.json      : input project file name (opened for reading only)' )
  print_debug ( -1, '  outproject.json     : output project file name (opened for writing and overwritten)' )
  print_debug ( -1, "" )


if (__name__ == '__main__'):

  if (len(sys.argv)<3):
    print_command_line_syntax (sys.argv)
    exit(1)

  proj_ifn = sys.argv[-2]
  proj_ofn = sys.argv[-1]

  l = len(sys.argv)-3

  use_scale = 0
  alignment_option = 'refine_affine'
  scale_tbd = 0
  finest_scale_done = 0
  swiftir_code_mode = 'python'
  start_layer = 0
  num_layers = -1

  # check for an even number of additional args
  if (l > 0) and (int(l/2.) == l/2.):
    i = 1
    while (i < len(sys.argv)-2):
      if sys.argv[i] == '-scale':
        use_scale = int(sys.argv[i+1])
      elif sys.argv[i] == '-code':
        # align_swiftir.global_swiftir_mode = str(sys.argv[i+1])
        swiftir_code_mode = str(sys.argv[i+1])
      elif sys.argv [i] == '-alignment_option':
        alignment_option = sys.argv [i + 1]
      elif sys.argv [i] == '-start':
        start_layer = int(sys.argv [i + 1])
      elif sys.argv [i] == '-count':
        num_layers = int (sys.argv [i + 1])
      elif sys.argv [i] == '-debug':
        debug_level = int (sys.argv [i + 1])
      else:
        print_command_line_syntax ( sys.argv )
        exit(1)
      i+=2

  #fp = open('/m2scratch/bartol/swift-ir_tests/LM9R5CA1_project.json','r')
  fp = open(proj_ifn,'r')

  d = json.load(fp)

  align_swiftir.debug_level = debug_level

  d, need_to_write_json = run_json_project ( project=d,
                                             alignment_option=alignment_option,
                                             use_scale=use_scale,
                                             swiftir_code_mode=swiftir_code_mode,
                                             start_layer=start_layer,
                                             num_layers=num_layers )

  if need_to_write_json:

    # Write out updated json project file
    print_debug(50,"Writing project to file: ", proj_ofn)
    ofp = open(proj_ofn,'w')
    json.dump(d,ofp, sort_keys=True, indent=2, separators=(',', ': '))

    '''
    p = np.polyfit(skew_x_array[:,0],skew_x_array[:,1],4)
    print_debug(50,"\n4th degree of Skew_X bias: \n", p)

    p = np.polyfit(scale_x_array[:,0],scale_x_array[:,1],4)
    print_debug(50,"\n4th degree of Scale_X bias: \n", p)

    p = np.polyfit(scale_y_array[:,0],scale_y_array[:,1],4)
    print_debug(50,"\n4th degree of Scale_Y bias: \n", p)

    p = np.polyfit(rot_array[:,0],rot_array[:,1],4)
    print_debug(50,"\n4th degree of Rot bias: \n", p)

    p = np.polyfit(x_array[:,0],x_array[:,1],4)
    print_debug(50,"\n4th degree of X bias: \n", p)

    p = np.polyfit(y_array[:,0],y_array[:,1],4)
    print_debug(50,"\n4th degree of Y bias: \n", p)
    '''



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

