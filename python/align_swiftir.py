#!/usr/bin/env python2.7

import swiftir
import numpy as np
import matplotlib.pyplot as plt
import os

'''
align_swiftir.py implements a simple generic interface for aligning two images in SWiFT-IR
This version uses swiftir.py

The interface is composed of two classes:  align_recipe and align_ingredient
The general concept is that the alignment of two images is accomplished by applying a
a series of steps, or "ingredients" to first estimate and then refine the affine transform
which brings the "moving" image into alignment with the "stationary" image.
Together these ingredients comprise a procedure, or "recipe". 
'''



#recipe_dict = {}

#recipe_dict['default'] = [affine_align_recipe(), affine_2x2_recipe, affine_4x4_recipe]
#recipe_dict['match_point'] = [affine_translation_recipe, affine_2x2_recipe, affine_4x4_recipe]

class alignment_process:

  def __init__(self, im_sta_fn, im_mov_fn, align_dir, layer_dict=None, cumulative_afm=None, x_bias=0.0, y_bias=0.0):
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
    if type(cumulative_afm) == type(None):
      self.cumulative_afm = swiftir.identityAffine()
    else:
      self.cumulative_afm = cumulative_afm


  def align(self):

    if self.layer_dict['align_to_ref_method']['selected_method']=='Auto Swim Align':
      result = self.auto_swim_align()
    elif self.layer_dict['align_to_ref_method']['selected_method']=='Match Point Align':
      result = self.auto_swim_align()

    return result

  
  def auto_swim_align(self):

    im_sta = swiftir.loadImage(self.im_sta_fn)
    im_mov = swiftir.loadImage(self.im_mov_fn)

    # window size scale factor
    wsf = 0.75

    pa = np.zeros((2,1))
    wwx = int(wsf*im_sta.shape[0])
    wwy = int(wsf*im_sta.shape[1])
    cx = int(im_sta.shape[0]/2)
    cy = int(im_sta.shape[1]/2)
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
    s_2x2 = int(wsf*s)
    psta_2x2 = pa

    nx = 4
    ny = 4
    pa = np.zeros((2,nx*ny))
    s = int(im_sta.shape[0]/4)
    for x in range(nx):
      for y in range(ny):
        pa[0, x + nx*y] = int(0.5*s + s*x)
        pa[1, x + nx*y] = int(0.5*s + s*y)
    s_4x4 = int(wsf*s)
    psta_4x4 = pa

    s_mp = int(im_sta.shape[0]/32)


    self.recipe = align_recipe(im_sta, im_mov)

    if self.layer_dict['align_to_ref_method']['selected_method']=='Auto Swim Align':
      ingredient_1 = align_ingredient(ww=(wwx,wwy), psta=psta_1)
      ingredient_2x2 = align_ingredient(ww=s_2x2, psta=psta_2x2)
      ingredient_4x4 = align_ingredient(ww=s_4x4, psta=psta_4x4)
      self.recipe.add_ingredient(ingredient_1)
      self.recipe.add_ingredient(ingredient_2x2)
      self.recipe.add_ingredient(ingredient_4x4)
    elif self.layer_dict['align_to_ref_method']['selected_method']=='Match Point Align':
      # Get match points from self.layer_dict['images']['base']['metadata']['match_points']
      mp_base = np.array(self.layer_dict['images']['base']['metadata']['match_points']).transpose()
      mp_ref = np.array(self.layer_dict['images']['ref']['metadata']['match_points']).transpose()
      ingredient_1_mp = align_ingredient(psta=mp_ref, pmov=mp_base, align_mode='match_point_align')
      ingredient_2_mp = align_ingredient(ww=s_mp, psta=mp_ref, pmov=mp_base)
      self.recipe.add_ingredient(ingredient_1_mp)
      self.recipe.add_ingredient(ingredient_2_mp)

    ingredient_check_align = align_ingredient(ww=(wwx,wwy), psta=psta_1, iters=1, align_mode='check_align')

    self.recipe.add_ingredient(ingredient_check_align)

    self.recipe.execute()

    self.cumulative_afm = swiftir.composeAffine(self.cumulative_afm,self.recipe.afm)
    self.cumlative_afm[0,2] -= self.x_bias
    self.cumlative_afm[1,2] -= self.y_bias
    im_aligned = swiftir.affineImage(self.cumulative_afm,im_mov)
    ofn = os.path.join ( self.align_dir, os.path.basename(self.im_mov_fn) )
    swiftir.saveImage(im_aligned,ofn)

    return (self.cumulative_afm, self.recipe)



# Universal class for alignment recipes
class align_recipe:

  def __init__(self, im_sta, im_mov):
    self.ingredients_list = []
    self.im_sta = im_sta
    self.im_mov = im_mov
    self.afm = swiftir.identityAffine()

  def add_ingredient(self, ingredient):
    ingredient.im_sta = self.im_sta
    ingredient.im_mov = self.im_mov
    self.ingredients_list.append(ingredient)

  def execute(self):
    for ingredient in self.ingredients_list:
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
  def __init__(self, im_sta=None, im_mov=None, ww=None, psta=None, pmov=None, afm=None, wht=-0.65, iters=2, align_mode='swim_align'):

    self.afm = afm
    self.im_sta = im_sta
    self.im_mov = im_mov
    self.ww = ww
    self.psta = psta
    self.pmov = pmov
    self.wht = wht
    self.iters = iters
    self.align_mode = align_mode
    self.snr = None


  def execute(self):

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

    self.pmov = swiftir.stationaryToMoving(afm, self.psta)
    sta = swiftir.stationaryPatches(self.im_sta, self.psta, self.ww)
    for i in range(self.iters):
      mov = swiftir.movingPatches(self.im_mov, self.pmov, afm, self.ww)
      (dp, ss, snr) = swiftir.multiSwim(sta, mov, pp=self.pmov, afm=afm, wht=self.wht)
      self.pmov = self.pmov + dp
      (afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
      self.pmov = swiftir.stationaryToMoving(afm, self.psta)
      print('  Affine err:  %g' % (err))
      print('  SNR:  ', snr)
    self.snr = snr

    if self.align_mode == 'swim_align':
      self.afm = afm

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

  recipe = align_recipe(im_sta, im_mov)

  ingredient_1 = align_ingredient(ww=(wwx,wwy), psta=psta_1)
  ingredient_2x2 = align_ingredient(ww=s_2x2, psta=psta_2x2)
  ingredient_4x4 = align_ingredient(ww=s_4x4, psta=psta_4x4)
  ingredient_check_align = align_ingredient(ww=(wwx,wwy), psta=psta_1, iters=1, align_mode='check_align')

  recipe.add_ingredient(ingredient_1)
  recipe.add_ingredient(ingredient_2x2)
  recipe.add_ingredient(ingredient_4x4)
  recipe.add_ingredient(ingredient_check_align)

  recipe.execute()

  global_afm = swiftir.composeAffine(global_afm,recipe.afm)
  im_aligned = swiftir.affineImage(global_afm,im_mov)
  ofn = os.path.join ( align_dir, os.path.basename(im_mov_fn) )
  swiftir.saveImage(im_aligned,ofn)

  return (global_afm, recipe)


if __name__=='__main__':

  image_dir = './'
  align_dir = './aligned/'
  im_sta_fn = image_dir + 'Tile_r1-c1_LM9R5CA1series_247.jpg'
  im_mov_fn = image_dir + 'Tile_r1-c1_LM9R5CA1series_248.jpg'

  global_afm = swiftir.identityAffine()

  align_images(im_sta_fn, im_mov_fn, align_dir, global_afm)


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

