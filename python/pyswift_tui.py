#!/usr/bin/env python3

import sys
import os
import errno
import numpy as np
import math
import scipy.stats as sps
import swiftir
import align_swiftir
import json
import copy
import matplotlib.pyplot as plt


# Do Linear Regression of X,Y data
def lin_fit(x,y):

  (m,b,r,p,stderr) = sps.linregress(x,y)
#  print('linear regression:')
#  print('  slope:',m)
#  print('  intercept:',b)
#  print('  r:',r)
#  print('  p:',p)
#  print('  stderr:',stderr)
#  print('')

  return(m,b,r,p,stderr)

if (__name__ == '__main__'):

  if (len(sys.argv)<3):
    print('\nUsage: %s swiftir_project_input_filename swiftir_project_output_filename \n'%(sys.argv[0]))
    print('         Open swiftir project file and perform alignment operations\n\n')
    print('         Result is written to output project file\n\n')
    exit(1)


  proj_ifn = sys.argv[1]
  proj_ofn = sys.argv[2]
  #fp = open('/m2scratch/bartol/swift-ir_tests/LM9R5CA1_project.json','r')
  fp = open(proj_ifn,'r')

  d = json.load(fp)
  scales = sorted([ int(s) for s in d['data']['scales'].keys() ])
  destination_path = d['data']['destination_path']

  # Iterate over scales from finest to coarsest
  # Identify coarsest scale lacking affine matrices in method_results
  #   and the finest scale which has affine matrices
  scale_tbd = 0
  scale_done = 0
  for scale in scales:
    sn = d['data']['scales'][str(scale)]['alignment_stack']
    afm = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in sn if 'affine_matrix' in i['align_to_ref_method']['method_results'] ])
    if not len(afm):
      scale_tbd = scale
    elif not scale_done:
      scale_done = scale

  if scale_tbd:
    upscale = (float(scale_done)/float(scale_tbd))
    print("Coarsest scale completed: ",scale_done)
    print("Operating on images at scale: ",scale_tbd)
    print("Upscale factor: ",upscale)
    scale_tbd_dir = os.path.join(destination_path,'scale_'+str(scale_tbd))

    ident = swiftir.identityAffine().tolist()

    # Copy settings from finest completed scale to tbd:
    s_done = d['data']['scales'][str(scale_done)]['alignment_stack']
    d['data']['scales'][str(scale_tbd)]['alignment_stack'] = copy.deepcopy(s_done)
    s_tbd = d['data']['scales'][str(scale_tbd)]['alignment_stack']
    #   Copy skip, swim, and match point settings
    for i in range(len(s_tbd)):
      # fix path for base and ref filenames for scale_tbd
      base_fn = os.path.basename(s_tbd[i]['images']['base']['filename'])
      s_tbd[i]['images']['base']['filename'] = os.path.join(scale_tbd_dir,'img_src',base_fn)
      if i>0:
        ref_fn = os.path.basename(s_tbd[i]['images']['ref']['filename'])
        s_tbd[i]['images']['ref']['filename'] = os.path.join(scale_tbd_dir,'img_src',ref_fn)

      
      atrm = s_tbd[i]['align_to_ref_method']

      if s_tbd[i]['skip']:
        atrm['method_results']['affine_matrix'] = ident
        atrm['method_results']['cumulative_afm'] = ident
        atrm['method_results']['snr'] = 0.0

      # set alignment option to 'refine_affine'
      atrm['method_data']['alignment_option'] = 'refine_affine'

      # Upscale bias values
      atrm['method_data']['bias_x_per_image'] = upscale*atrm['method_data']['bias_x_per_image']
      atrm['method_data']['bias_y_per_image'] = upscale*atrm['method_data']['bias_y_per_image']
      # TODO: handle bias values in a better way than this
      x_bias = atrm['method_data']['bias_x_per_image']
      y_bias = atrm['method_data']['bias_y_per_image']

      # put updated atrm into s_tbd
      s_tbd[i]['align_to_ref_method'] = atrm

      # if there are match points, copy and scale them for scale_tbd
      if atrm['selected_method'] == 'Match Point Align':
        mp_ref = (np.array(s_tbd[i]['images']['ref']['metadata']['match_points'])*upscale).tolist()
        mp_base = (np.array(s_tbd[i]['images']['base']['metadata']['match_points'])*upscale).tolist()
        s_tbd[i]['images']['ref']['metadata']['match_points'] = mp_ref
        s_tbd[i]['images']['base']['metadata']['match_points'] = mp_base


    # Copy the affine_matrices from s_tbd and scale the translation part to use as the initial guess for s_tbd
    afm_tmp = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in s_tbd ])
    afm_scaled = afm_tmp.copy()
    afm_scaled[:,:,2] = afm_scaled[:,:,2]*upscale


    # Now setup the alignment for s_tbd
    align_list = []
    align_dir = os.path.join(scale_tbd_dir,'img_aligned','')
    # make dir path for align_dir and ignore error if it already exists
    try:
        os.makedirs(align_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    snr_file = open('snr_1.dat','w')
    bias_x_file = open('bias_x_1.dat','w')
    bias_y_file = open('bias_y_1.dat','w')
    bias_rot_file = open('bias_rot_1.dat','w')
    bias_scale_x_file = open('bias_scale_x_1.dat','w')
    bias_scale_y_file = open('bias_scale_y_1.dat','w')
    bias_skew_file = open('bias_skew_1.dat','w')
    bias_det_file = open('bias_det_1.dat','w')
    afm_file = open('afm_1.dat','w')
    c_afm_file = open('c_afm_1.dat','w')


    for i in range(1,len(s_tbd)):
      if not s_tbd[i]['skip']:
        im_sta_fn = s_tbd[i]['images']['ref']['filename']  
        im_mov_fn = s_tbd[i]['images']['base']['filename']  
        align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
        align_list.append([i,align_proc])

    # Save unmodified first image into align_dir
    im_sta_fn = s_tbd[0]['images']['base']['filename']  
    base_fn = os.path.basename(im_sta_fn)
    al_fn = os.path.join(align_dir,base_fn)
    print("Saving first image in align dir: ", al_fn)
    im_sta = swiftir.loadImage(im_sta_fn)
    swiftir.saveImage(im_sta,al_fn)
    s_tbd[0]['images']['aligned']['filename'] = al_fn

    c_afm = swiftir.identityAffine()
    
    i = 0
    for item in align_list:

      align_idx = item[0]
      align_item = item[1]
      print('\n\nAligning: %s %s\n' % (align_item.im_sta_fn, align_item.im_mov_fn))

      align_item.cumulative_afm = c_afm
      (c_afm, recipe) = align_item.align()

      c_afm[0,2]-=x_bias
      c_afm[1,2]-=y_bias
      snr = recipe.ingredients[-1].snr
      afm = recipe.ingredients[-1].afm
    
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

      rot = math.atan(afm[1,0]/afm[0,0])
      scale_x = math.sqrt(afm[0,0]**2 + afm[1,0]**2)
      scale_y = (afm[1,1]*math.cos(rot))-(afm[0,1]*math.sin(rot))
      skew = ((afm[0,1]*math.cos(rot))+(afm[1,1]*math.sin(rot)))/scale_y
      det = (afm[0,0]*afm[1,1])-(afm[0,1]*afm[1,0])

      snr_file.write('%d %.6g\n' % (i, snr))
      bias_x_file.write('%d %.6g\n' % (i, afm[0,2]))
      bias_y_file.write('%d %.6g\n' % (i, afm[1,2]))
      bias_rot_file.write('%d %.6g\n' % (i, rot))
      bias_scale_x_file.write('%d %.6g\n' % (i, scale_x))
      bias_scale_y_file.write('%d %.6g\n' % (i, scale_y))
      bias_skew_file.write('%d %.6g\n' % (i, skew))
      bias_det_file.write('%d %.6g\n' % (i, det))

      afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (i, afm[0,0], afm[0,1], afm[0,2], afm[1,0], afm[1,1], afm[1,2]))
      c_afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (i, c_afm[0,0], c_afm[0,1], c_afm[0,2], c_afm[1,0], c_afm[1,1], c_afm[1,2]))
      i+=1

    # Write out updated json project file
    print("Writing project to file: ", proj_ofn)
    ofp = open(proj_ofn,'w')
    json.dump(d,ofp)

    '''
    for align_item in align_list:
      align_item.saveAligned(rect=rect, grayBorder=True)
    '''


  snr_file.close()
  bias_x_file.close()
  bias_y_file.close()
  bias_rot_file.close()
  bias_scale_x_file.close()
  bias_scale_y_file.close()
  bias_skew_file.close()
  bias_det_file.close()
  afm_file.close()
  c_afm_file.close()


  exit(0)


  cafm = np.array([ i['align_to_ref_method']['method_results']['cumulative_afm'] for i in sn if i['align_to_ref_method']['method_results'].get('cumulative_afm') ])

  cx = cafm[:,:,2][:,0]
  cy = cafm[:,:,2][:,1]

  (mx,bx,r,p,stderr) = lin_fit(np.arange(len(cx)),cx)
  (my,by,r,p,stderr) = lin_fit(np.arange(len(cy)),cy)
  xl = mx*np.arange(len(cx))+bx
  yl = my*np.arange(len(cy))+by

  print("(mx,bx): ",mx,bx)
  print("(my,by): ",my,by)


  # plot data
  p = plt.scatter(np.arange(len(cx)),cx)
  p = plt.scatter(np.arange(len(cy)),cy)
  p = plt.scatter(np.arange(len(cx)),xl)
  p = plt.scatter(np.arange(len(cy)),yl)
  plt.show()


