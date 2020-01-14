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
    print('\nUsage: %s [ -scale n ] [ -alignment_option init_affine|refine_affine|apply_affine ] swiftir_project_input_filename swiftir_project_output_filename \n'%(sys.argv[0]))
    print('         Open swiftir project file and perform alignment operations\n\n')
    print('         Result is written to output project file\n\n')
    exit(1)


  proj_ifn = sys.argv[-2]
  proj_ofn = sys.argv[-1]

  l = len(sys.argv)-3

  use_scale = 0
  alignment_option = 'refine_affine'
  scale_tbd = 0
  scale_done = 0

  # check for an even number of additional args
  if (l > 0) and (int(l/2.) == l/2.):
    i = 1
    while (i < len(sys.argv)-2):
      if sys.argv[i] == '-scale':
        use_scale = int(sys.argv[i+1])
      elif sys.argv[i] == '-alignment_option':
        alignment_option = sys.argv[i+1]
      else:
        print('\nUsage: %s [ -scale n ] [ -alignment_option init_affine|refine_affine|apply_affine ] swiftir_project_input_filename swiftir_project_output_filename \n'%(sys.argv[0]))
        print('         Open swiftir project file and perform alignment operations\n\n')
        print('         Result is written to output project file\n\n')
        exit(1)
      i+=2

  #fp = open('/m2scratch/bartol/swift-ir_tests/LM9R5CA1_project.json','r')
  fp = open(proj_ifn,'r')

  d = json.load(fp)
  scales = sorted([ int(s) for s in d['data']['scales'].keys() ])
  destination_path = d['data']['destination_path']

  if use_scale==0:
    # Iterate over scales from finest to coarsest
    # Identify coarsest scale lacking affine matrices in method_results
    #   and the finest scale which has affine matrices
    for scale in scales:
      sn = d['data']['scales'][str(scale)]['alignment_stack']
      afm = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in sn if 'affine_matrix' in i['align_to_ref_method']['method_results'] ])
      if not len(afm):
        scale_tbd = scale
      elif not scale_done:
        scale_done = scale
  else:
    scale_tbd = use_scale

  if scale_tbd:
    if use_scale:
      upscale = 1.0
      print("Performing alignment_option: %s  at scale: %d" % (alignment_option,scale_tbd))
      print("Operating on images at scale: ",scale_tbd)
      print("Upscale factor: ",upscale)
    else:
      upscale = (float(scale_done)/float(scale_tbd))
      print("Coarsest scale completed: ",scale_done)
      print("Operating on images at scale: ",scale_tbd)
      print("Upscale factor: ",upscale)

    scale_tbd_dir = os.path.join(destination_path,'scale_'+str(scale_tbd))

    ident = swiftir.identityAffine().tolist()

    if scale_done:
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

      # Initialize method_results for skipped or missing method_results
      if s_tbd[i]['skip'] or atrm['method_results'] == {}:
        atrm['method_results']['affine_matrix'] = ident
        atrm['method_results']['cumulative_afm'] = ident
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
      afm_tmp = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in s_tbd ])
      afm_scaled = afm_tmp.copy()
      afm_scaled[:,:,2] = afm_scaled[:,:,2]*upscale
    else:
      afm_scale = None

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
    bias_skew_x_file = open('bias_skew_x_1.dat','w')
    bias_det_file = open('bias_det_1.dat','w')
    afm_file = open('afm_1.dat','w')
    c_afm_file = open('c_afm_1.dat','w')

    if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
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
#      print("Refine affine using bias mat:\n", bias_mat)

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

          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
#          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=swiftir.composeAffine(bias_mat,afm_scaled[i]))
        else:
          align_proc = align_swiftir.alignment_process(im_sta_fn, im_mov_fn, align_dir, layer_dict=s_tbd[i], init_affine_matrix=ident)
        align_list.append([i,align_proc])

    # Save unmodified first image into align_dir
    im_sta_fn = s_tbd[0]['images']['base']['filename']  
    base_fn = os.path.basename(im_sta_fn)
    al_fn = os.path.join(align_dir,base_fn)
    print("Saving first image in align dir: ", al_fn)
    im_sta = swiftir.loadImage(im_sta_fn)
    swiftir.saveImage(im_sta,al_fn)
    if not 'aligned' in s_tbd[0]['images']:
      s_tbd[0]['images']['aligned'] = {}
    s_tbd[0]['images']['aligned']['filename'] = al_fn

    c_afm = swiftir.identityAffine()


    # Setup custom bias values for this alignment run
    # SYGQK scale 24 biases
    '''
    rot_bias = -(0.062/270.)
    scale_x_bias = (1/(0.96))**(1/270.)
    scale_y_bias = (1/(0.8))**(1/270.)
    skew_x_bias = -(0.145/270.)
    x_bias = -(-80/270.)
    y_bias = -(80/270.)
    '''

    '''
    # SYGQK scale 6 biases
    rot_bias = -(0.072/270.)
    scale_x_bias = (1/(0.94))**(1/270.)
    scale_y_bias = (1/(0.78**2))**(1/270.)
    skew_x_bias = -(1.1*0.145/270.)
    x_bias = -(-80*2.7/270.)
    y_bias = -(80*5/270.)
    '''

    '''
    # SYGQK scale 6 biases, using apply_affine from scale 24
    rot_bias = -(0.045/270.)
    scale_x_bias = (1/(0.960))**(1/270.)
    scale_y_bias = (1/(0.82))**(1/270.)
    skew_x_bias = -(0.118/270.)
    x_bias = -(-80*4/270.)
    y_bias = -(80*4/270.)
    '''

    # SYGQK scale 6 biases, using apply_affine from scale 24
    '''
    rot_bias = -(0.045/270.)
    scale_x_bias = (1/(0.960))**(1/270.)
    scale_y_bias = (1/(0.82))**(1/270.)
    skew_x_bias = -(0.118/270.)
    x_bias = -(-80*24/270.)
    y_bias = -(80*24/270.)
    '''

    # LM9R5CA1 scale 24 biases
    '''
    rot_bias = -(-0.015/266.)
    scale_x_bias = (1/(1.02))**(1/266.)
    scale_y_bias = (1/(1.03))**(1/266.)
    skew_x_bias = -(-0.02/266.)
    x_bias = -(-145/266.)
    y_bias = -(110/266.)
    '''

    # LM9R5CA1 scale 8 biases, scaled up from scale 24
    rot_bias = -(-0.02/266.)
    scale_x_bias = 1.02**(-1.0/266.)
    scale_y_bias = 1.046**(-1.0/266.)
    skew_x_bias = -(-0.02/266.)
    x_bias = -(-165*3/266.)
    y_bias = -(110*3/266.)


    '''
    rot_bias = 0.0
    scale_x_bias = 1.0
    scale_y_bias = 1.0
    skew_x_bias = 0.0
    x_bias = 0.0
    y_bias = 0.0
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
    
    i = 0
    for item in align_list:

      align_idx = item[0]
      align_item = item[1]
      print('\n\nAligning: %s %s\n' % (align_item.im_sta_fn, align_item.im_mov_fn))

      align_item.cumulative_afm = c_afm
      (c_afm, recipe) = align_item.align()

      c_afm = swiftir.composeAffine(bias_mat,c_afm)

#      c_afm[0,2]-=x_bias
#      c_afm[1,2]-=y_bias
      snr = recipe.ingredients[-1].snr
      afm = recipe.ingredients[-1].afm
    
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

      rot = np.arctan(c_afm[1,0]/c_afm[0,0])
      scale_x = np.sqrt(c_afm[0,0]**2 + c_afm[1,0]**2)
      scale_y = (c_afm[1,1]*np.cos(rot))-(c_afm[0,1]*np.sin(rot))
      skew_x = ((c_afm[0,1]*np.cos(rot))+(c_afm[1,1]*np.sin(rot)))/scale_y
      det = (c_afm[0,0]*c_afm[1,1])-(c_afm[0,1]*c_afm[1,0])

      snr_file.write('%d %.6g\n' % (i, snr))
      bias_x_file.write('%d %.6g\n' % (i, c_afm[0,2]))
      bias_y_file.write('%d %.6g\n' % (i, c_afm[1,2]))
      bias_rot_file.write('%d %.6g\n' % (i, rot))
      bias_scale_x_file.write('%d %.6g\n' % (i, scale_x))
      bias_scale_y_file.write('%d %.6g\n' % (i, scale_y))
      bias_skew_x_file.write('%d %.6g\n' % (i, skew_x))
      bias_det_file.write('%d %.6g\n' % (i, det))

      afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (i, afm[0,0], afm[0,1], afm[0,2], afm[1,0], afm[1,1], afm[1,2]))
      c_afm_file.write('%d %.6g %.6g %.6g %.6g %.6g %.6g\n' % (i, c_afm[0,0], c_afm[0,1], c_afm[0,2], c_afm[1,0], c_afm[1,1], c_afm[1,2]))
      i+=1

    # Write out updated json project file
    print("Writing project to file: ", proj_ofn)
    ofp = open(proj_ofn,'w')
    json.dump(d,ofp, sort_keys=True, indent=2, separators=(',', ': '))

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
  bias_skew_x_file.close()
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


