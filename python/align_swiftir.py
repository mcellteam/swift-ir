#!/usr/bin/env python2.7

import swiftir
import numpy as np
import matplotlib.pyplot as plt

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



# Universal class for alignment recipes
class align_recipe:

  def __init__(self, im_sta, im_mov):
    self.recipe = []
    self.im_sta = im_sta
    self.im_mov = im_mov
    self.afm = swiftir.identityAffine()

  def add_ingredient(self, ingredient):
    ingredient.im_sta = self.im_sta
    ingredient.im_mov = self.im_mov
    self.recipe.append(ingredient)

  def execute(self):
    for ingredient in self.recipe:
      ingredient.afm = self.afm
      self.afm = ingredient.execute()



# Universal class for alignment ingredients of recipes
class align_ingredient:
 
  # Constructor for ingredient of a recipe
  # Ingredients come in 2 main types where the type is determined whether ww is None
  #   1) If ww==None then this is a Matching Point ingredient
  #        We calculate the afm directly using psta and pmov as the matching points
  #   2) If ww!=None then this is swim window matching ingredient
  #        ww and psta specify the size and location of windows in im_sta
  #        and corresponding windows (pmov) are contructed from psta and projected onto im_mov
  #        from which image matching is performed to estimate or refine the afm.
  #        If psta contains only one point then the estimated afm will be a translation matrix
  def __init__(self, im_sta=None, im_mov=None, ww=None, psta=None, pmov=None, afm=None, wht=-0.65, iters=2):

    self.afm = afm
    self.im_sta = im_sta
    self.im_mov = im_mov
    self.ww = ww
    self.psta = psta
    self.pmov = pmov
    self.wht = wht
    self.iters = iters


  def execute(self):

    # If ww==None then this is a Matching Point ingredient of a recipe
    # Calculate afm directly using psta and pmov as the matching points
    if type(self.ww) == type(None):
      (self.afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
      return(self.afm)

    #  Otherwise, this is a swim window match ingredient
    if type(self.afm)==type(None):
      self.afm = swiftir.identityAffine()

    self.pmov = swiftir.stationaryToMoving(self.afm, self.psta)
    sta = swiftir.stationaryPatches(self.im_sta, self.psta, self.ww)
    for i in range(self.iters):
      mov = swiftir.movingPatches(self.im_mov, self.pmov, self.afm, self.ww)
      (dp, ss, snr) = swiftir.multiSwim(sta, mov, pp=self.pmov, afm=self.afm, wht=self.wht)
      self.pmov = self.pmov + dp
      (self.afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
      self.pmov = swiftir.stationaryToMoving(self.afm, self.psta)
      print('  Affine err:  %g' % (err))
      print('  SNR:  ', snr)

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



if __name__=='__main__':

  image_dir = './'
  im_sta = swiftir.loadImage(image_dir + 'Tile_r1-c1_LM9R5CA1series_247.jpg')
  im_mov = swiftir.loadImage(image_dir + 'Tile_r1-c1_LM9R5CA1series_248.jpg')


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

  recipe.add_ingredient(ingredient_1)
  recipe.add_ingredient(ingredient_2x2)
  recipe.add_ingredient(ingredient_4x4)

  recipe.execute()

  exit()

  afm = affine_translation_recipe(im_sta, im_mov)


  # 2x2 recipe to refine estimate full affine transform
  print('2x2 recipe to refine estimate full affine transform')

  afm = affine_2x2_recipe(im_sta, im_mov, afm)


  # 3x3 recipe to finalize estimate full affine transform
  #print('3x3 recipe to finalize estimate full affine transform')

  #afm = affine_3x3_recipe(im_sta, im_mov, afm)


  # 4x4 recipe to finalize estimate full affine transform
  print('4x4 recipe to finalize estimate full affine transform')

  afm = affine_4x4_recipe(im_sta, im_mov, afm)

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

