#!/usr/bin/env python3

import cv2
import numpy as np
import imageio
import glob
import subprocess as sp
import os


'''
  swim outputs a line of the form

  SNR: target xtgt ytgt source xsrc ysrc φsrc (Δx Δy m0 flags)

  Here:

SNR
  is the signal to noise value of the match.
target
  is the file name of the target image copied from the command line
xtgt ytgt
  are the coordinates of ptgt modified by the -x and -y command line options.
source
  is the file name of the source image copied from the command line
xsrc ysrc
  are the optimized coordinates of psrc that match ptgt.
φsrc
  is the optimized rotation.

Information in parentheses is somewhat redundant. Δx and Δy are the pixel
shifts applied to psrc and m0 := √(Δx2 + Δy2). The flags can indicate bad
matches in x (“dx”), in y (“dy”), in both (“dxy”) if any shift is greater than
a quarter of the window size. It can also indicate that a threshold has been
exceeded (“dreset”)

'''



class align_pair_recipe():

  def __init__(self,im1,im2):
    self.im1 = im1
    self.im2 = im2
    self.af = np.eye(2, 3, dtype=np.float32)
    self.recipe = []


class swim_pair():

  def __init__(self,ww,im_base,im_float,iters='2',whiten='-0.65',addx='0',addy='0,keep=None,tarx=None,tary=None,patx=None,paty=None,rota=None,afm=None):
    self.swim_cmd_list=[]
    self.add_swim_cmd(ww,im_base,im_float,iters=iters,whiten=whiten,addx=addx,addy=addy,keep=keep,tarx=tarx,tary=tary,patx=patx,paty=paty,rota=rota,afm=afm)

  def add_swim_cmd(self,ww,im_base,im_float,iters='2',whiten='-0.65',addx='0',addy='0',keep=None,tarx=None,tary=None,patx=None,paty=None,rota=None,afm=None):
    self.im_base = im_base
    self.im_float = im_float
    self.ww = ww
    self.iters = iters
    self.addx = addx
    self.addy = addy
    self.whiten=whiten

    self.keep=keep
    if self.keep==None:
      keep_arg = ''
    else:
      keep_arg = '-k %s' % (self.keep)

    self.tarx=tarx
    self.tary=tary
    if not self.tarx or not self.tary:
      tar_arg = ''
    else:
      tar_arg = '%s %s' % (self.tarx, self.tary)

    self.patx=patx
    self.paty=paty
    if not self.patx or not self.paty:
      pat_arg = ''
    else:
      pat_arg = '%s %s' % (self.patx, self.paty)

    self.rota=rota
    if not self.rota:
      rota_arg = ''
    else:
      rota_arg = '%s' % (self.rota)

    self.afm = afm
    if not self.afm:
      afm_arg = ''
    else:
      afm_arg = '%s %s %s %s' % (self.afm[0], self.afm[1], self.afm[2], self.afm[3])

    self.swim_cmd_list.append('swim%s -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s %s %s %s' % (self.ww, self.iters, self.whiten, self.addx, self.addy, self.keep, self.im_base, tar_arg, self.im_float, pat_arg, rota_arg, afm_arg))


  def run_swim(self,arg_dict):
    for swim_cmd in self.swim_cmd_list:
      swim_script = '%s\n' % (swim_cmd)
    
    swim_proc = sp.Popen(['swim',self.ww],stdin=sp.PIPE,stdout=sp.PIPE,universal_newlines=True)
    swim_stdout, swim_stderr = swim_proc.communicate(swim_cmd))

    # Note: decode bytes if universal_newlines=False in Popen
    #swim_stdout = swim_stdout.decode('utf-8')
    #swim_stderr = swim_stderr.decode('utf-8')

    toks = swim_stdout.split()
    print('swim output: \n  ' + swim_stdout)
    snr = float(toks[0][0:-1])
    dx = float(toks[8][1:])
    dy = float(toks[9])
    warp_matrix[0,2]=dx
    warp_matrix[1,2]=dy
    print('%s : swim match:  SNR: %g  dX: %g  dY: %g' % (im_fn, snr, dx, dy))
    print(warp_matrix)

  def run_swim(self):
    swim_log = sp.run([swim_cmd],shell=True,stdout=sp.PIPE,stderr=sp.PIPE)
    self.swim_stdout = swim_log.stdout.decode('utf-8')
    self.swim_stderr = swim_log.stdout.decode('utf-8')
    toks = self.swim_stdout.split()
    print('swim output: \n  ' + self.swim_stdout)
    self.snr = float(toks[0][0:-1])
    self.dx = float(toks[8][1:])
    self.dy = float(toks[9])
    self.rot = float(toks[10])
    
    

# get list of jpeg images to be aligned:
im_dir_input = './linear_jpgs/'
im_dir_input = './linear_jpgs/'
jpg_files = sorted(glob.glob(im_dir_input + '*.jpg'))

# choose base image for alignment
base_im = 0
im0_fn = jpg_files.pop(base_im)
png_file = './linear_pngs/' + os.path.splitext(os.path.split(im0_fn)[1])[0] + '.png'
im0 = cv2.imread(png_file,cv2.IMREAD_UNCHANGED)

png_file_aligned = './aligned_pngs/' + os.path.splitext(os.path.split(im0_fn)[1])[0] + '.png'
cv2.imwrite(png_file_aligned,im0)

# Find size of image1
sz = im0.shape
print('\naligning to image: ' + im0_fn)
print('image size: ' + str(sz))

swim_cmd_template = 'swim 4000 -i 2 -w -0.61 -k keep.JPG %s %s' 
warp_matrix = np.eye(2, 3, dtype=np.float32)

for im_fn in jpg_files:
  swim_cmd = swim_cmd_template % (im0_fn,im_fn)
  swim_log = sp.run([swim_cmd],shell=True,stdout=sp.PIPE,stderr=sp.PIPE)
  swim_stdout = swim_log.stdout.decode('utf-8')
  swim_stderr = swim_log.stdout.decode('utf-8')
  toks = swim_stdout.split()
  print('swim output: \n  ' + swim_stdout)
  snr = float(toks[0][0:-1])
  dx = float(toks[8][1:])
  dy = float(toks[9])
  warp_matrix[0,2]=dx
  warp_matrix[1,2]=dy
  print('%s : swim match:  SNR: %g  dX: %g  dY: %g' % (im_fn, snr, dx, dy))
  print(warp_matrix)
  png_file = './linear_pngs/' + os.path.splitext(os.path.split(im_fn)[1])[0] + '.png'
  png_file_aligned = './aligned_pngs/' + os.path.splitext(os.path.split(im_fn)[1])[0] + '.png'
  im2 =  cv2.imread(png_file,cv2.IMREAD_UNCHANGED)
  im2_aligned = cv2.warpAffine(im2, warp_matrix, (sz[1],sz[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP);
  print('writing aligned image: %s' % (png_file_aligned))
  cv2.imwrite(png_file_aligned,im2_aligned)

exit(0)


tiff_file = './aligned_tiffs/' + os.path.splitext(os.path.split(im1_fn)[1])[0] + '.tiff'
cv2.imwrite(tiff_file,im1)
 
# Convert 16bit color images to 8bit grayscale
im1_gray = (cv2.cvtColor(im1,cv2.COLOR_BGR2GRAY)/256.).astype('uint8')
 
# Find size of image1
sz = im1.shape
print('aligning to image: ' + tiff_file)
print('image size: ' + str(sz))
 
# Define the motion model
warp_mode = cv2.MOTION_TRANSLATION
 
# Define 2x3 or 3x3 matrices and initialize the matrix to identity
if warp_mode == cv2.MOTION_HOMOGRAPHY :
    warp_matrix = np.eye(3, 3, dtype=np.float32)
else :
    warp_matrix = np.eye(2, 3, dtype=np.float32)
 
# Specify the number of iterations.
number_of_iterations = 10000;
 
# Specify the threshold of the increment
# in the correlation coefficient between two iterations
termination_eps = 1e-10;
 
# Define termination criteria
criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, number_of_iterations,  termination_eps)
 

for im2_fn in tiff_files:
  print('Aligning image: %s' % (im2_fn))
  im2 =  cv2.imread(im2_fn,cv2.IMREAD_UNCHANGED)
  im2_gray = (cv2.cvtColor(im2,cv2.COLOR_BGR2GRAY)/256.).astype('uint8')

  # Run the ECC algorithm. The results are stored in warp_matrix.
  (cc, warp_matrix) = cv2.findTransformECC (im1_gray, im2_gray, warp_matrix, warp_mode, criteria)
 
  if warp_mode == cv2.MOTION_HOMOGRAPHY :
    # Use warpPerspective for Homography 
    im2_aligned = cv2.warpPerspective (im2, warp_matrix, (sz[1],sz[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
  else :
    # Use warpAffine for Translation, Euclidean and Affine
    im2_aligned = cv2.warpAffine(im2, warp_matrix, (sz[1],sz[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP);
 
  # Show final results
  #cv2.namedWindow("Image 1", cv2.WINDOW_NORMAL)
  #cv2.namedWindow("Image 2", cv2.WINDOW_NORMAL)
  #cv2.namedWindow("Aligned Image 2", cv2.WINDOW_NORMAL)
  #cv2.imshow("Image 1", im1)
  #cv2.imshow("Image 2", im2)
  #cv2.imshow("Aligned Image 2", im2_aligned)
  #cv2.waitKey(0)

  tiff_file = './aligned_tiffs/' + os.path.splitext(os.path.split(im2_fn)[1])[0] + '.tiff'

  cv2.imwrite(tiff_file,im2_aligned)

