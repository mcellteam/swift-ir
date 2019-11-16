#!/usr/bin/env python2.7

import swiftir
import numpy as np
import matplotlib.pyplot as plt
import os

import subprocess as sp


'''
align_swiftir.py implements a simple generic interface for aligning two images in SWiFT-IR
This version uses swiftir.py

The interface is composed of two classes:  align_recipe and align_ingredient
The general concept is that the alignment of two images is accomplished by applying a
a series of steps, or "ingredients" to first estimate and then refine the affine transform
which brings the "moving" image into alignment with the "stationary" image.
Together these ingredients comprise a procedure, or "recipe". 
'''

debug_level = 0

global_swiftir_mode = 'python'   # Either 'python' or 'c'


def run_command(cmd, arg_list=None, cmd_input=None):

  global debug_level

  cmd_arg_list = [ cmd ]
  if arg_list != None:
    cmd_arg_list = [ a for a in arg_list ]
    cmd_arg_list.insert ( 0, cmd )
  cmd_proc = sp.Popen(cmd_arg_list,stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
  cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)

  # Note: decode bytes if universal_newlines=False in Popen
  #cmd_stdout = cmd_stdout.decode('utf-8')
  #cmd_stderr = cmd_stderr.decode('utf-8')
  if debug_level > 50: print('command output: \n\n' + cmd_stdout + '\n')

  return ( { 'out': cmd_stdout, 'err': cmd_stderr } )



#recipe_dict = {}

#recipe_dict['default'] = [affine_align_recipe(), affine_2x2_recipe, affine_4x4_recipe]
#recipe_dict['match_point'] = [affine_translation_recipe, affine_2x2_recipe, affine_4x4_recipe]

def prefix_lines ( i, s ):
  return ( '\n'.join ( [ i + ss.rstrip() for ss in s.split('\n') if len(ss) > 0 ] ) + "\n" )


class alignment_process:

  def __init__(self, im_sta_fn, im_mov_fn, align_dir, layer_dict=None, init_affine_matrix = None, cumulative_afm=None, x_bias=0.0, y_bias=0.0):
    self.recipe = None
    self.im_sta_fn = im_sta_fn
    self.im_mov_fn = im_mov_fn
    self.align_dir = align_dir
    self.x_bias = x_bias
    self.y_bias = y_bias

    if layer_dict != None:
      self.layer_dict = layer_dict
    else:
      self.layer_dict = {
                          "align_to_ref_method": {
                                                   "selected_method": "Auto Swim Align",
                                                   "method_options": [
                                                                       "Auto Swim Align",
                                                                       "Match Point Align"
                                                                     ],
						   "method_data": {},
						   "method_results": {}
						 }
      }
    if type(init_affine_matrix) == type(None):
      self.init_affine_matrix = swiftir.identityAffine()
    else:
      self.init_affine_matrix = init_affine_matrix
    if type(cumulative_afm) == type(None):
      self.cumulative_afm = swiftir.identityAffine()
    else:
      self.cumulative_afm = cumulative_afm

  def __str__(self):
    s = "alignment_process: \n"
    s += "  dir: " + str(self.align_dir) + "\n"
    s += "  sta: " + str(self.im_sta_fn) + "\n"
    s += "  mov: " + str(self.im_mov_fn) + "\n"
    if self.recipe == None:
      s += "  rec: None\n"
    else:
      s += "  rec:\n" + prefix_lines('    ', str(self.recipe)) + "\n"
    return s

  def align(self):

    atrm = self.layer_dict['align_to_ref_method']
    if atrm['selected_method']=='Auto Swim Align':
      result = self.auto_swim_align()
    elif atrm['selected_method']=='Match Point Align':
      result = self.auto_swim_align()

    return result

  
  def auto_swim_align(self):

    global debug_level
    if debug_level >= 70:
      print ( "*** top of auto_swim_align() ***" )


    im_sta = swiftir.loadImage(self.im_sta_fn)
    im_mov = swiftir.loadImage(self.im_mov_fn)

    # window size scale factor
    wsf = 0.75
#    wsf = 1.0

    # Set up 1x1 point and window
    pa = np.zeros((2,1))                # Point Array for one point
    wwx_f = int(im_sta.shape[0])        # Window Width in x (Full Size)
    wwy_f = int(im_sta.shape[1])        # Window Width in y (Full Size)
    wwx = int(wsf*im_sta.shape[0])      # Window Width in x Scaled
    wwy = int(wsf*im_sta.shape[1])      # Window Width in y Scaled
    cx = int(im_sta.shape[0]/2)         # Window Center in x
    cy = int(im_sta.shape[1]/2)         # Window Center in y
    pa[0,0] = cx
    pa[1,0] = cy
    psta_1 = pa


    # Set up 2x2 points and windows
    nx = 2
    ny = 2
    pa = np.zeros((2,nx*ny))                # Point Array (2x4) points
    s = int(im_sta.shape[0]/2)              # Initial Size of each window
    for x in range(nx):
      for y in range(ny):
        pa[0, x + nx*y] = int(0.5*s + s*x)  # Point Array (2x4) points
        pa[1, x + nx*y] = int(0.5*s + s*y)  # Point Array (2x4) points
    s_2x2 = int(wsf*s)
    psta_2x2 = pa


    # Set up 4x4 points and windows
    nx = 4
    ny = 4
    pa = np.zeros((2,nx*ny))
    s = int(im_sta.shape[0]/4)
    for x in range(nx):
      for y in range(ny):
        pa[0, x + nx*y] = int(0.5*s + s*x)
        pa[1, x + nx*y] = int(0.5*s + s*y)
#    s_4x4 = int(wsf*s)
    s_4x4 = int(s)
    psta_4x4 = pa

    # Set up a window size for match point alignment (1/32 of x dimension)
    s_mp = int(im_sta.shape[0]/32)

    if debug_level >= 70:
      print ( "  psta_1   = " + str(psta_1) )
      print ( "  psta_2x2 = " + str(psta_2x2) )
      print ( "  psta_4x4 = " + str(psta_4x4) )

    self.recipe = align_recipe(im_sta, im_mov, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)

    atrm = self.layer_dict['align_to_ref_method']
    if atrm['selected_method']=='Auto Swim Align':
      alignment_option = atrm['method_data'].get('alignment_option')
      if alignment_option == 'refine_affine':
        ingredient_4x4 = align_ingredient(ww=int(s_4x4), psta=psta_4x4, afm=self.init_affine_matrix, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
        self.recipe.add_ingredient(ingredient_4x4)
      elif alignment_option == 'apply_affine':
        self.recipe.afm = self.init_affine_matrix
      else:
        # Normal Auto Swim Align - Full Recipe
        ingredient_1 = align_ingredient(ww=(wwx,wwy), psta=psta_1, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
        ingredient_2x2 = align_ingredient(ww=s_2x2, psta=psta_2x2, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
        ingredient_4x4 = align_ingredient(ww=s_4x4, psta=psta_4x4, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
        self.recipe.add_ingredient(ingredient_1)
        self.recipe.add_ingredient(ingredient_2x2)
        self.recipe.add_ingredient(ingredient_4x4)
    elif atrm['selected_method']=='Match Point Align':
      # Get match points from self.layer_dict['images']['base']['metadata']['match_points']
      mp_base = np.array(self.layer_dict['images']['base']['metadata']['match_points']).transpose()
      mp_ref = np.array(self.layer_dict['images']['ref']['metadata']['match_points']).transpose()
      # First ingredient is to calculate the Affine matrix from match points alone
      ingredient_1_mp = align_ingredient(psta=mp_ref, pmov=mp_base, align_mode='match_point_align', im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
      # Second ingredient is to refine the Affine matrix by swimming at each match point
      ingredient_2_mp = align_ingredient(ww=s_mp, psta=mp_ref, pmov=mp_base, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
      self.recipe.add_ingredient(ingredient_1_mp)  # This one will set the Affine matrix
      self.recipe.add_ingredient(ingredient_2_mp)  # This one will use the previous Affine and refine it

    ingredient_check_align = align_ingredient(ww=(wwx_f,wwy_f), psta=psta_1, iters=1, align_mode='check_align', im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)

    self.recipe.add_ingredient(ingredient_check_align)

    self.recipe.execute()

    self.cumulative_afm = swiftir.composeAffine(self.recipe.afm,self.cumulative_afm)
    self.cumulative_afm[0,2] -= self.x_bias
    self.cumulative_afm[1,2] -= self.y_bias
    im_aligned = swiftir.affineImage(self.cumulative_afm,im_mov)
    ofn = os.path.join ( self.align_dir, os.path.basename(self.im_mov_fn) )
    swiftir.saveImage(im_aligned,ofn)

    return (self.cumulative_afm, self.recipe)



# Universal class for alignment recipes
class align_recipe:

  def __init__(self, im_sta, im_mov, im_sta_fn=None, im_mov_fn=None):
    self.ingredients = []
    self.im_sta = im_sta
    self.im_mov = im_mov
    self.im_sta_fn = im_sta_fn
    self.im_mov_fn = im_mov_fn
    self.afm = swiftir.identityAffine()

  def __str__(self):
    s = "recipe: \n"
    if self.ingredients == None:
      s += "  ing[]: None\n"
    else:
      s += "  ing[]:\n"
      for ing in self.ingredients:
        s += prefix_lines ( '    ', str(ing) )
    return s

  def add_ingredient(self, ingredient):
    ingredient.im_sta = self.im_sta
    ingredient.im_mov = self.im_mov
    ingredient.im_sta_fn = self.im_sta_fn
    ingredient.im_mov_fn = self.im_mov_fn
    self.ingredients.append(ingredient)

  def execute(self):
    for ingredient in self.ingredients:
      ingredient.afm = self.afm
      self.afm = ingredient.execute()



# Universal class for alignment ingredients of recipes
class align_ingredient:
 
  # Constructor for ingredient of a recipe
  # Ingredients come in 3 main types where the type is determined by value of align_mode
  #   1) If align_mode is 'match_point_align' then this is a Matching Point ingredient
  #        We calculate the afm directly using psta and pmov as the matching points
  #   2) If align_mode is 'swim_align' then this is a swim window matching ingredient
  #        ww and psta specify the size and location of windows in im_sta
  #        and corresponding windows (pmov) are contructed from psta and projected onto im_mov
  #        from which image matching is performed to estimate or refine the afm.
  #        If psta contains only one point then the estimated afm will be a translation matrix
  #   3) If align_mode is 'check_align' then use swim to check the SNR achieved by the 
  #        supplied afm matrix but do not refine the afm matrix
  def __init__(self, im_sta=None, im_mov=None, ww=None, psta=None, pmov=None, afm=None, wht=-0.68, iters=2, align_mode='swim_align', im_sta_fn=None, im_mov_fn=None):

    self.afm = afm
    self.im_sta = im_sta
    self.im_mov = im_mov
    self.im_sta_fn = im_sta_fn
    self.im_mov_fn = im_mov_fn
    self.ww = ww
    self.psta = psta
    self.pmov = pmov
    self.wht = wht
    self.iters = iters
    self.align_mode = align_mode
    self.snr = None

    global global_swiftir_mode
    self.swiftir_mode = global_swiftir_mode

    if self.swiftir_mode == 'c':
      print ( "Actually loading images" )
      self.im_sta = swiftir.loadImage(self.im_sta_fn)
      self.im_mov = swiftir.loadImage(self.im_mov_fn)

  def __str__(self):
    s =  "ingredient:\n"
    s += "  mode: " + str(self.align_mode) + "\n"
    s += "  ww: " + str(self.ww) + "\n"
    s += "  psta:\n" + prefix_lines('    ', str(self.psta)) + "\n"
    s += "  pmov:\n" + prefix_lines('    ', str(self.pmov)) + "\n"
    s += "  afm:\n"  + prefix_lines('    ', str(self.afm)) + "\n"
    return s

  def set_swim_results(self,swim_stdout,swim_stderr):

    toks = swim_stdout.replace('(',' ').replace(')',' ').strip().split()

    self.snr = float(toks[0][0:-1])
    self.base_x = float(toks[2])
    self.base_y = float(toks[3])
    self.adjust_x = float(toks[5])
    self.adjust_y = float(toks[6])
    self.dx = float(toks[8])
    self.dy = float(toks[9])
    self.m0 = float(toks[10])
    self.flags = None
    if len(toks)>11:
      self.flags = toks[11:]  # Note flags: will be a str or list of strs

#    warp_matrix[0,2]=dx
#    warp_matrix[1,2]=dy
#    print('%s %s : swim match:  SNR: %g  dX: %g  dY: %g' % (self.im_base, self.im_adjust, self.snr, self.dx, self.dy))
    pass



  def run_swim_c ( self, im_base_fn, im_adj_fn, offx=0, offy=0, keep=None, base_x=None, base_y=None, adjust_x=None, adjust_y=None, rota=None, afm=None ):

    global debug_level

    if debug_level >= 10:
      print ( str(self) )

    karg = ''
    if keep != None:
      karg = '-k %s' % (keep)

    tar_arg = ''
    if base_x!=None and base_y!=None:
      tar_arg = '%s %s' % (base_x, base_y)

    pat_arg = ''
    if adjust_x!=None and adjust_y!=None:
      pat_arg = '%s %s' % (adjust_x, adjust_y)

    rota_arg = ''
    if rota!=None:
      rota_arg = '%s' % (rota)

    afm_arg = ''
    if type(afm)!=type(None):
      afm_arg = '%.6f %.6f %.6f %.6f' % (afm[0,0], afm[0,1], afm[1,0], afm[1,1])

    swim_ww_arg = '1024'
    if type(self.ww) == type((1,2)):
      swim_ww_arg = str(self.ww[0]) + "x" + str(self.ww[1])
    else:
      swim_ww_arg = str(self.ww)

    print ( "--------------------------" )

    print ( str(self) )

    swim_results = []
    # print ( "psta = " + str(self.psta) )
    multi_swim_arg_string = ""
    for i in range(len(self.psta[0])):
      offx = self.psta[0][i]
      offy = self.psta[1][i]
      print ( "Will run a swim of " + str(self.ww) + " at (" + str(self.psta[0][i]) + "," + str(self.psta[1][i]) + ")" )
      # swim_arg_string = 'ww_%s -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s' % (swim_ww_arg, self.iters, self.wht, offx, offy, karg, im_base_fn, tar_arg, im_adj_fn, pat_arg, rota_arg, afm_arg)
      swim_arg_string = 'ww_' + swim_ww_arg + ' -i ' + str(self.iters) + ' -w ' + str(self.wht) + ' -x ' + str(offx) + ' -y ' + str(offy) + ' ' + karg + ' ' + im_base_fn + ' ' + tar_arg + ' ' + im_adj_fn + ' ' + pat_arg + ' ' + rota_arg + ' ' + afm_arg
      print ( "  " + swim_arg_string )
      #print ( "  " + swim_arg_string2 )
      multi_swim_arg_string += swim_arg_string + "\n"

    print ( "" )

    o = run_command ( "swim", arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string )

    swim_out_lines = o['out'].strip().split('\n')
    swim_err_lines = o['err'].strip().split('\n')
    swim_results.append ( { 'out':swim_out_lines, 'err':swim_err_lines } )

    for l in swim_out_lines:
      print ( "SWIM OUT: " + str(l) )

    # Separate the results into a list of token lists
    toks = [ swim_results[i]['out'][0].replace('(',' ').replace(')',' ').strip().split() for i in range(len(swim_results)) ]


    print ( "--------------------------" )
    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    #swim_request_string = 'swim_ww_%d -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s' % (swim_ww_arg, self.iters, self.wht, offx, offy, karg, im_base_fn, tar_arg, im_adj_fn, pat_arg, rota_arg, afm_arg)
    #swim_request_string = 'swim_ww_%d -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s' % (swim_ww_arg, self.iters, self.wht, offx, offy, karg, im_base_fn, tar_arg, im_adj_fn, pat_arg, rota_arg, afm_arg)
    #swim_script = '%s\n' % (swim_request_string)
    #print('swim_script:\n\n' + swim_script + '\n')

    #swim_proc = sp.Popen(['swim',str(swim_ww_arg)],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    #swim_stdout, swim_stderr = swim_proc.communicate(swim_script)


    # Note: decode bytes if universal_newlines=False in Popen
    #swim_stdout = swim_stdout.decode('utf-8')
    #swim_stderr = swim_stderr.decode('utf-8')
    #print('swim output: \n\n' + swim_stdout + '\n')

    #self.set_swim_results(swim_stdout,swim_stderr)

    '''
    swim_cmd_string = 'swim %s -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s' % (swim_ww_arg, self.iters, self.wht, offx, offy, karg, im_base_fn, tar_arg, im_adj_fn, pat_arg, rota_arg, afm_arg)
    print('swim_str:\n\n' + swim_cmd_string + '\n')

    swim_proc = sp.Popen([s for s in swim_cmd_string.split()],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    swim_stdout, swim_stderr = swim_proc.communicate()

    print('swim output: \n\n' + swim_stdout + '\n')

    print ( "####################################" )
    '''

    swim_arg_string = 'ww_%s -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s' % (swim_ww_arg, self.iters, self.wht, offx, offy, karg, im_base_fn, tar_arg, im_adj_fn, pat_arg, rota_arg, afm_arg)
    print('swim_cmd_str: swim ' + str(swim_ww_arg) + '\n')
    print('swim_arg_str: ' + swim_arg_string + '\n')

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    o = run_command ( "swim", arg_list=[swim_ww_arg], cmd_input=swim_arg_string )

    swim_out_lines = o['out'].strip().split('\n')
    swim_err_lines = o['err'].strip().split('\n')
    swim_results = { 'out':swim_out_lines, 'err':swim_err_lines }

    if debug_level >= 95:
      print ( "Entering the command line debugger:" )
      __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    return swim_results


  def execute(self):

    global debug_level

    # If ww==None then this is a Matching Point ingredient of a recipe
    # Calculate afm directly using psta and pmov as the matching points
    if self.align_mode == 'match_point_align':
      (self.afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
      self.ww = (0.0, 0.0)
      self.snr = np.zeros(len(self.psta[0]))
      return(self.afm)

    #  Otherwise, this is a swim window match ingredient
    #  Refine the afm via swim and mir
    afm = self.afm
    if type(afm)==type(None):
      afm = swiftir.identityAffine()

    if self.swiftir_mode == 'c':

      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      if debug_level >= 50: print ( "Running c version of swim" )
      #self.pmov = swiftir.stationaryToMoving(afm, self.psta)

      res = self.run_swim_c ( self.im_sta_fn, self.im_mov_fn )

      # This puts all SNRs into a list (as it should)
      self.snr = [ float(res['out'][n].split(':')[0]) for n in range(len(res['out'])) ]

      # This just uses the first offset only
      x0 = float(res['out'][0].split()[2])
      y0 = float(res['out'][0].split()[3])
      x1 = float(res['out'][0].split()[5])
      y1 = float(res['out'][0].split()[6])

      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      self.afm = np.array ( [ [ 1.0, 0.0, x1-x0 ], [ 0.0, 1.0, y1-y0 ] ] )  # Offset matrix

      # Temporary: return an identity matrix and other "dummy" settings
      #self.afm = np.array ( [ [ 1.0, 0.0, 0.0 ], [ 0.0, 1.0, 0.0 ] ] )  # Identity matrix
      #theta = np.pi / 50
      #self.afm = np.array ( [ [ np.cos(theta), -np.sin(theta), 0.0 ], [ np.sin(theta), np.cos(theta), 0.0 ] ] )  # Identity matrix

      #self.pmov = swiftir.stationaryToMoving(afm, self.psta)
      #self.snr = np.ones ( len(self.psta[0]) ) * 999.0

    else:

      if debug_level >= 50: print ( "Running python version of swim" )
      self.pmov = swiftir.stationaryToMoving(afm, self.psta)
      sta = swiftir.stationaryPatches(self.im_sta, self.psta, self.ww)
      for i in range(self.iters):
        print ( 'psta = ' + str(self.psta) )
        print ( 'pmov = ' + str(self.pmov) )
        mov = swiftir.movingPatches(self.im_mov, self.pmov, afm, self.ww)
        (dp, ss, snr) = swiftir.multiSwim(sta, mov, pp=self.pmov, afm=afm, wht=self.wht)
        if debug_level >= 0: print ( '  dp,ss,snr = ' + str(dp) + ', ' + str(ss) + ', ' + str(snr) )
        self.pmov = self.pmov + dp
        (afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
        self.pmov = swiftir.stationaryToMoving(afm, self.psta)
        if debug_level >= 0: print('  Affine err:  %g' % (err))
        if debug_level >= 0: print('  SNR:  ', snr)
      self.snr = snr

    if self.align_mode == 'swim_align':
      self.afm = afm

    if debug_level >= 90:
      print ( "Entering the command line debugger:" )
      __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    return(self.afm)



def showdiff(ima, imb):
    err = ima.astype('float32') - imb.astype('float32')
    err = err[100:-100,100:-100]
    print('rms image error = ', np.sqrt(np.mean(err*err)))
    blk = ima<imb
    dif = ima - imb
    dif[blk] = imb[blk] - ima[blk]
    plt.clf()
    plt.imshow(dif, cmap='gray')
    plt.show()


def align_images(im_sta_fn, im_mov_fn, align_dir, global_afm):

  print ( "\n\n%%%%%%%%%%%%%%%%%%%%%%%%%%% Static Function Call to align_images %%%%%%%%%%%%%%%%%%%%%%%%%%%\n" )
  if type(global_afm) == type(None):
    global_afm = swiftir.identityAffine()

  im_sta = swiftir.loadImage(im_sta_fn)
  im_mov = swiftir.loadImage(im_mov_fn)

  pa = np.zeros((2,1))
  wwx = int(im_sta.shape[0])
  wwy = int(im_sta.shape[1])
  cx = int(wwx/2)
  cy = int(wwy/2)
  pa[0,0] = cx
  pa[1,0] = cy
  psta_1 = pa

  nx = 2
  ny = 2
  pa = np.zeros((2,nx*ny))
  s = int(im_sta.shape[0]/2)
  for x in range(nx):
    for y in range(ny):
      pa[0, x + nx*y] = int(0.5*s + s*x)
      pa[1, x + nx*y] = int(0.5*s + s*y)
  s_2x2 = s
  psta_2x2 = pa

  nx = 4
  ny = 4
  pa = np.zeros((2,nx*ny))
  s = int(im_sta.shape[0]/4)
  for x in range(nx):
    for y in range(ny):
      pa[0, x + nx*y] = int(0.5*s + s*x)
      pa[1, x + nx*y] = int(0.5*s + s*y)
  s_4x4 = s
  psta_4x4 = pa

  recipe = align_recipe(im_sta, im_mov, im_sta_fn=im_sta_fn, im_mov_fn=im_mov_fn)

  ingredient_1 = align_ingredient(ww=(wwx,wwy), psta=psta_1)
  ingredient_2x2 = align_ingredient(ww=s_2x2, psta=psta_2x2)
  ingredient_4x4 = align_ingredient(ww=s_4x4, psta=psta_4x4)
  ingredient_check_align = align_ingredient(ww=(wwx,wwy), psta=psta_1, iters=1, align_mode='check_align')

  recipe.add_ingredient(ingredient_1)
  recipe.add_ingredient(ingredient_2x2)
  recipe.add_ingredient(ingredient_4x4)
  recipe.add_ingredient(ingredient_check_align)

  recipe.execute()

  global_afm = swiftir.composeAffine(recipe.afm,global_afm)
  im_aligned = swiftir.affineImage(global_afm,im_mov)
  ofn = os.path.join ( align_dir, os.path.basename(im_mov_fn) )
  swiftir.saveImage(im_aligned,ofn)

  return (global_afm, recipe)



#import argparse
import sys


if __name__=='__main__':
  print ( "Running " + __file__ + ".__main__()" )

  # "Tile_r1-c1_LM9R5CA1series_247.jpg",
  # "Tile_r1-c1_LM9R5CA1series_248.jpg",

  # These are the defaults
  f1 = "vj_097_shift_rot_skew_crop_1.jpg"
  f2 = "vj_097_shift_rot_skew_crop_2.jpg"
  out = "./aligned"

  # Process and remove the fixed positional arguments
  args = sys.argv
  args = args[1:]  # Shift out this file name (argv[0])
  if (len(args) > 0) and (not args[0].startswith('-')):
    f1 = args[0]
    f2 = args[0]
    args = args[1:]  # Shift out the first file name argument
    if (len(args) > 0) and (not args[0].startswith('-')):
      f2 = args[0]
      args = args[1:]  # Shift out the second file name argument
      if (len(args) > 0) and (not args[0].startswith('-')):
        out = args[0]
        args = args[1:]  # Shift out the destination argument

  # Now all of the remaining arguments should be optional
  xbias = 0
  ybias = 0
  match_points = None
  layer_dict = None
  cumulative_afm = None

  while len(args) > 0:
    print ( "Current args: " + str(args) )
    if args[0] == '-c':
      print ( "Running in 'c' mode" )
      global_swiftir_mode = 'c'
      args = args[1:]
    elif args[0] == '-xb':
      args = args[1:]
      xbias = float(args[0])
      args = args[1:]
    elif args[0] == '-yb':
      args = args[1:]
      ybias = float(args[0])
      args = args[1:]
    elif args[0] == '-cafm':
      # This will be -cafm 0.1,0.2,0.3,0.4,0.5,0.6
      #   representing [ [0.1,0.2,0.3], [0.4,0.5,0.6] ]
      args = args[1:]
      cafm = [ float(v) for v in args[0].split(' ')[1].split(',') ]
      if len(cafm) == 6:
        cumulative_afm = [ cafm[0:3], cafm[3:6] ]
      args = args[1:]
    elif args[0] == '-match':
      # This will be -match 0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2
      #   representing [ [ [0.1,0.2], [0.3,0.4], [0.5,0.6] ], [ [0.7,0.8], [0.9,1.0], [1.1,1.2] ] ]
      # Note that the first sub-array are all the match points from the first image,
      #   and the second sub-array are corresponding match points from second image
      # Example for tests/vj_097_shift_rot_skew_crop_1.jpg and tests/vj_097_shift_rot_skew_crop_2.jpg:
      #   327.8,332.0,539.4,208.8,703.3,364.3,266.2,659.9,402.1,249.4,605.2,120.5,776.2,269.0,353.0,580.0

      args = args[1:]
      match = [ float(v) for v in args[0].split(',') ]
      args = args[1:]
      # Force the number of points to be a multiple of 4 (2 per point by 2 per pair)
      npts = (len(match) / 2) / 2
      if npts > 0:
        match_points = [ [], [] ]
        # Split the original one dimensional array into 2 parts (one for each image)
        m = [match[0:npts*2], match[npts*2:]]
        # Group the floats for each image into pairs representing points
        match_points[0] = [ [m[0][2*i],m[0][(2*i)+1]] for i in range(len(m[0])/2) ]
        match_points[1] = [ [m[1][2*i],m[1][(2*i)+1]] for i in range(len(m[1])/2) ]

        # Build the layer dictionary with the match points
        layer_dict = {
          "images": {
            "base": {
              "metadata": {
                "match_points": match_points[0]
              }
            },
            "ref": {
              "metadata": {
                "match_points": match_points[1]
              }
            }
          },
          "align_to_ref_method": {
            "selected_method": "Match Point Align",
            "method_options": [
              "Auto Swim Align",
              "Match Point Align"
            ],
            "method_data": {},
            "method_results": {}
          }
        }


  print ( "Creating the alignment process" )
  align_proc = alignment_process ( f1,
                                   f2,
                                   out,
                                   layer_dict=layer_dict,
                                   x_bias=xbias,
                                   y_bias=ybias,
                                   cumulative_afm=cumulative_afm )

  if global_swiftir_mode == 'c':
    print ( "Loading the images" )
    if not (align_proc.recipe is None):
      if not (align_proc.recipe.ingredients is None):
        im_sta = swiftir.loadImage(f1)
        im_mov = swiftir.loadImage(f2)
        for ing in align_proc.recipe.ingredients:
          ing.im_sta = im_sta
          ing.im_mov = im_mov

  print ( "Performing the alignment" )
  align_proc.align()

  """
  image_dir = './'
  align_dir = './aligned/'
  im_sta_fn = image_dir + 'Tile_r1-c1_LM9R5CA1series_247.jpg'
  im_mov_fn = image_dir + 'Tile_r1-c1_LM9R5CA1series_248.jpg'


  global_afm = swiftir.identityAffine()

  align_images(im_sta_fn, im_mov_fn, align_dir, global_afm)
  """


  '''
  psta = np.zeros((2,1))
  wwx = int(im_sta.shape[0])
  wwy = int(im_sta.shape[1])
  cx = int(wwx/2)
  cy = int(wwy/2)
  psta[0,0] = cx
  psta[1,0] = cy

  pmov = swiftir.stationaryToMoving(afm, psta)
  sta = swiftir.stationaryPatches(im_sta, psta, ww)
  mov = swiftir.movingPatches(im_mov, pmov, afm, ww)
  (dp, ss, snr) = swiftir.multiSwim(sta, mov, pp=pmov, afm=afm, wht=-.65)
  print(snr)
  print(afm)

  #best = swiftir.alignmentImage(sta[0], mov[0])
  #plt.imshow(best,cmap='gray')
  #plt.show()

  '''

