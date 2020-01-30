#!/usr/bin/env python3

import sys

import numpy as np
import subprocess as sp
from math import *

'''
  Note:
  swim outputs a line of the form

  SNR: target xtgt ytgt source xsrc ysrc phi_src (dx dy m0 flags)

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
phi_src
  is the optimized rotation.

Information in parentheses is somewhat redundant. dx and dy are the pixel
shifts applied to psrc and m0 := sqrt(dx^2 + dy^2). The flags can indicate bad
matches in x ("dx"), in y ("dy"), in both ("dxy") if any shift is greater than
a quarter of the window size. It can also indicate that a threshold has been
exceeded ("dreset")

'''



class align_image_pair_recipe():

  def __init__(self,im_base,im_adjust):
    self.im_base = im_base
    self.im_adjust= im_adjust
    self.af = np.eye(2, 3, dtype=np.float32)
    self.ai = np.eye(2, 3, dtype=np.float32)
    self.recipe = []

  def mir_get_affine(self,swim_requests):
    mir_script=''
    for req in swim_requests:
      mir_script += '%.15g %.15g %.15g %.15g\n' % (req.base_x, req.base_y, req.adjust_x, req.adjust_y)
    mir_script += 'R\n'
    print('mir_script:\n\n' + mir_script + '\n')

    mir_proc = sp.Popen(['mir'],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    mir_stdout, mir_stderr = mir_proc.communicate(mir_script)
    print('mir stdout: \n\n' + mir_stdout + '\n')
    print('mir stderr: \n\n' + mir_stderr + '\n')
    afm = np.eye(2, 3, dtype=np.float32)
    aim = np.eye(2, 3, dtype=np.float32)
    for line in mir_stdout.splitlines():
      toks = line.strip().split()
      if(toks[0]=='AF'):
        afm[0,0] = float(toks[1])
        afm[0,1] = float(toks[2])
        afm[0,2] = float(toks[3])
        afm[1,0] = float(toks[4])
        afm[1,1] = float(toks[5])
        afm[1,2] = float(toks[6])
      if(toks[0]=='AI'):
        aim[0,0] = float(toks[1])
        aim[0,1] = float(toks[2])
        aim[0,2] = float(toks[3])
        aim[1,0] = float(toks[4])
        aim[1,1] = float(toks[5])
        aim[1,2] = float(toks[6])

    return (afm, aim)



def mir_get_affine(swim_requests):
    mir_script=''
    for req in swim_requests:
      mir_script += '%.15g %.15g %.15g %.15g\n' % (req.base_x, req.base_y, req.adjust_x, req.adjust_y)
    mir_script += 'R\n'
    print('mir_script:\n\n' + mir_script + '\n')

    mir_proc = sp.Popen(['mir'],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    mir_stdout, mir_stderr = mir_proc.communicate(mir_script)
    print('mir stdout: \n\n' + mir_stdout + '\n')
    print('mir stderr: \n\n' + mir_stderr + '\n')
    afm = np.eye(2, 3, dtype=np.float32)
    aim = np.eye(2, 3, dtype=np.float32)
    for line in mir_stdout.splitlines():
      toks = line.strip().split()
      if(toks[0]=='AF'):
        afm[0,0] = float(toks[1])
        afm[0,1] = float(toks[2])
        afm[0,2] = float(toks[3])
        afm[1,0] = float(toks[4])
        afm[1,1] = float(toks[5])
        afm[1,2] = float(toks[6])
      if(toks[0]=='AI'):
        aim[0,0] = float(toks[1])
        aim[0,1] = float(toks[2])
        aim[0,2] = float(toks[3])
        aim[1,0] = float(toks[4])
        aim[1,1] = float(toks[5])
        aim[1,2] = float(toks[6])

    return afm, aim



def mir_calc_affine(pnts):
    mir_script=''
    for pnt in pnts:
      mir_script += '%.15g %.15g %.15g %.15g\n' % (pnt[0],pnt[1],pnt[2],pnt[3])
    mir_script += 'R\n'
    print('mir_script:\n\n' + mir_script + '\n')

    mir_proc = sp.Popen(['mir'],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    mir_stdout, mir_stderr = mir_proc.communicate(mir_script)
    print('mir stdout: \n\n' + mir_stdout + '\n')
    print('mir stderr: \n\n' + mir_stderr + '\n')
    afm = np.eye(2, 3, dtype=np.float32)
    aim = np.eye(2, 3, dtype=np.float32)
    for line in mir_stdout.splitlines():
      toks = line.strip().split()
      if(toks[0]=='AF'):
        afm[0,0] = float(toks[1])
        afm[0,1] = float(toks[2])
        afm[0,2] = float(toks[3])
        afm[1,0] = float(toks[4])
        afm[1,1] = float(toks[5])
        afm[1,2] = float(toks[6])
      if(toks[0]=='AI'):
        aim[0,0] = float(toks[1])
        aim[0,1] = float(toks[2])
        aim[0,2] = float(toks[3])
        aim[1,0] = float(toks[4])
        aim[1,1] = float(toks[5])
        aim[1,2] = float(toks[6])

    return afm, aim


class swim_request:
  def __init__(self,ww,im_base,im_adjust,iters='2',whiten='-0.65',offset_x='0',offset_y='0',keep=None,base_x=None,base_y=None,adjust_x=None,adjust_y=None,rota=None,afm=None):

    self.ww = ww
    self.im_base = im_base
    self.im_adjust = im_adjust
    self.iters = iters
    self.offset_x = offset_x
    self.offset_y = offset_y
    self.whiten=whiten

    self.keep=keep
    self.keep_arg = ''
    if self.keep!=None:
      self.keep_arg = '-k %s' % (self.keep)

    self.base_x=base_x
    self.base_y=base_y
    self.tar_arg = ''
    if self.base_x!=None and self.base_y!=None:
      self.tar_arg = '%s %s' % (self.base_x, self.base_y)

    self.adjust_x=adjust_x
    self.adjust_y=adjust_y
    self.pat_arg = ''
    if self.adjust_x!=None and self.adjust_y!=None:
      self.pat_arg = '%s %s' % (self.adjust_x, self.adjust_y)

    self.rota=rota
    self.rota_arg = ''
    if self.rota!=None:
      self.rota_arg = '%s' % (self.rota)

    self.afm = afm
    self.afm_arg = ''
    if type(self.afm)!=type(None):
      self.afm_arg = '%.6f %.6f %.6f %.6f' % (self.afm[0,0], self.afm[0,1], self.afm[1,0], self.afm[1,1])

    self.swim_stdout = None
    self.swim_stderr = None
    self.swim_results = None
    self.make_swim_request_string()


  def make_swim_request_string(self):
    self.swim_request_string = 'swim_ww_%s -i %s -w %s -x %s -y %s %s %s %s %s %s %s %s' % (self.ww, self.iters, self.whiten, self.offset_x, self.offset_y, self.keep_arg, self.im_base, self.tar_arg, self.im_adjust, self.pat_arg, self.rota_arg, self.afm_arg)


  def run_swim(self):
    if self.swim_request_string == None:
      self.make_swim_request_string()

    swim_script = '%s\n' % (self.swim_request_string)
    print('swim_script:\n\n' + swim_script + '\n')

    swim_proc = sp.Popen(['swim',self.ww],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    swim_stdout, swim_stderr = swim_proc.communicate(swim_script)


    # Note: decode bytes if universal_newlines=False in Popen
    #swim_stdout = swim_stdout.decode('utf-8')
    #swim_stderr = swim_stderr.decode('utf-8')
    print('swim output: \n\n' + swim_stdout + '\n')

    self.set_swim_results(swim_stdout,swim_stderr)


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



class swim_image_pair:

  def __init__(self,ww,im_base,im_adjust,iters='2',whiten='-0.65',offset_x='0',offset_y='0',keep=None,base_x=None,base_y=None,adjust_x=None,adjust_y=None,rota=None,afm=None):
    self.swim_request_list=[]
    self.ww = ww
    self.im_base = im_base
    self.im_adjust = im_adjust
    self.add_swim_request(iters=iters,whiten=whiten,offset_x=offset_x,offset_y=offset_y,keep=keep,base_x=base_x,base_y=base_y,adjust_x=adjust_x,adjust_y=adjust_y,rota=rota,afm=afm)


  def add_swim_request(self,iters='2',whiten='-0.65',offset_x='0',offset_y='0',keep=None,base_x=None,base_y=None,adjust_x=None,adjust_y=None,rota=None,afm=None):

    self.swim_request_list.append(swim_request(self.ww,self.im_base,self.im_adjust,iters=iters,whiten=whiten,offset_x=offset_x,offset_y=offset_y,keep=keep,base_x=base_x,base_y=base_y,adjust_x=adjust_x,adjust_y=adjust_y,rota=rota,afm=afm))
    

  def run_swim(self):
    swim_script = ''
    for swim_request_item in self.swim_request_list:
      swim_script += '%s\n' % (swim_request_item.swim_request_string)
    print('swim_script:\n\n' + swim_script + '\n')

    swim_proc = sp.Popen(['swim',self.ww],stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
    swim_stdout, swim_stderr = swim_proc.communicate(swim_script)

    # Note: decode bytes if universal_newlines=False in Popen
    #swim_stdout = swim_stdout.decode('utf-8')
    #swim_stderr = swim_stderr.decode('utf-8')
    print('swim output: \n\n' + swim_stdout + '\n')

    swim_stdout_lines = swim_stdout.splitlines()
    for i in range(len(self.swim_request_list)):
      swim_request_item = self.swim_request_list[i]
      swim_request_item.set_swim_results(swim_stdout_lines[i],swim_stderr)
    



def run_swim_requests(swim_requests):
  for req in swim_requests:
    req.run_swim()



# The following stub was used to test with concurrent processing in swift_gui.py
def do_alignment ( swim_data_1, swim_data_2 ):
  print ( "running a swim_command" )
  for i in range(100):
    print ( " i = " + str(i) )
    for j in range(10):
      print ( "  j = " + str(j) )
      print ( "    " + str(sqrt(i+10) * cos(j)) )



if __name__ == "__main__":

  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

  args = sys.argv[1:]


  if len(args) <= 0:

    # This is the previous default case

    #swim_test = swim_image_pair('256','test_im_1.jpg','test_im_2.jpg')
    #swim_test.run_swim()

    #swim_requests = []
    #swim_requests.append(swim_request('256','test_im_1.jpg','test_im_2.jpg'))
    #swim_requests.append(swim_request('256','test_im_2.jpg','test_im_1.jpg'))
    #swim_requests.append(swim_request('256','test_im_1.jpg','test_im_1.jpg'))

    im_1 = 'Tile_r1-c1_LM9R5CA1series_244.jpg'
    im_2 = 'Tile_r1-c1_LM9R5CA1series_246.jpg'

    # Start from matching points:
    match_pnts=[]
    match_pnts.append([401,587,483,529])
    match_pnts.append([632,638,686,584])
    match_pnts.append([309,875,408,819])
    match_pnts.append([151,299,231,231])

    center = [512,512,578,453]

    afm, aim = mir_calc_affine(match_pnts)
    print('Match Points AI: \n\n' + str(aim) + '\n')

    swim_req = swim_request('1024',im_1,im_2,iters='2',offset_x='0',offset_y='0',base_x='512',base_y='512',adjust_x='578',adjust_y='453',afm=aim,keep='keep.JPG')
    swim_req.run_swim()

    swim_requests = []
    ww = '512'
    wx = ['-300','0','300']
    wy = ['-300','0','300']
    for x in range(len(wx)):
      for y in range(len(wy)):
        swim_requests.append(swim_request(ww,im_1,im_2,iters='2',offset_x=wx[x],offset_y=wy[y],base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))

    run_swim_requests(swim_requests)

    afm, aim = mir_get_affine(swim_requests)

    print('3x3 recipe 1,  AI: \n\n' + str(aim) + '\n')


    #swim_req = swim_request('1024',im_1,im_2,iters='5',offset_x='0',offset_y='0',base_x='512',base_y='512',adjust_x='578',adjust_y='453',afm=aim,keep='keep.JPG')
    #swim_req.run_swim()

    swim_req = swim_request('1024',im_1,im_2,iters='5',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim,keep='keep.JPG')
    swim_req.run_swim()


    exit()

  if '?' in args:

    print ( "  " + sys.argv[0] + ": Run swim test cases" )
    print ( "    angle_snr" )
    print ( "    angletest" )
    print ( "    multiswim" )

    exit()

  if 'angle_snr' in args:

    # Start: Find initial translation

    swim_req = swim_request('1024', im_1, im_2, iters='5',keep='keep.JPG')
    swim_req.run_swim()


    # Find best translation and rotation

    rad = pi/180.0
    aim = np.eye(2, 3, dtype=np.float32)

    best_snr = 0.0
    best_angle = 0.0
    for ang in np.arange(-4,4.01,0.2):
      print('***** Trying Angle: %g' % (ang))
      aim[0,0]=cos(ang)
      aim[0,1]=sin(ang)
      aim[1,0]=-sin(ang)
      aim[1,1]=cos(ang)
    #  swim_req_2 = swim_request('512',im_1,im_2,iters='5',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim)
      swim_req_2 = swim_request('512',im_1,im_2,iters='5',offset_x='0',offset_y='0',base_x='512',base_y='512',adjust_x='578',adjust_y='453',afm=aim)
      swim_req_2.run_swim()
      if swim_req_2.snr > best_snr:
        best_snr = swim_req_2.snr
        best_angle = ang
        best_swim = swim_req_2

    print('Best SNR: %g at angle %g' % (best_snr,best_angle))

    exit()

  if 'angletest' in args:

    #for ang in np.arange(-5,5.01,0.5):
    #  swim_req_2 = swim_request('512','Tile_r1-c1_LM9R5CA1series_244.jpg', 'Tile_r1-c1_LM9R5CA1series_246.jpg',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=str(ang))
    #  swim_req_2.run_swim()


    ang='2.8'

    swim_req = swim_request('1024','Tile_r1-c1_LM9R5CA1series_244.jpg', 'Tile_r1-c1_LM9R5CA1series_246.jpg',iters=5,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,keep='keep.JPG')
    swim_req.run_swim()

    swim_req = swim_request('1024','Tile_r1-c1_LM9R5CA1series_244.jpg', 'Tile_r1-c1_LM9R5CA1series_246.jpg',iters=5,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,keep='keep.JPG')
    swim_req.run_swim()

    swim_req = swim_request('1024','Tile_r1-c1_LM9R5CA1series_244.jpg', 'Tile_r1-c1_LM9R5CA1series_246.jpg',iters=5,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,keep='keep.JPG')
    swim_req.run_swim()

    swim_req = swim_request('1024','Tile_r1-c1_LM9R5CA1series_244.jpg', 'Tile_r1-c1_LM9R5CA1series_246.jpg',iters=5,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,keep='keep.JPG')
    swim_req.run_swim()

    swim_req = swim_request('1024','Tile_r1-c1_LM9R5CA1series_244.jpg', 'Tile_r1-c1_LM9R5CA1series_246.jpg',iters=5,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,keep='keep.JPG')
    swim_req.run_swim()

    exit()


  if 'multiswim' in args:

    swim_requests = []
    swim_requests.append(swim_request('512',im_1,im_2,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,offset_x='512',offset_y='512',iters=5))
    swim_requests.append(swim_request('512',im_1,im_2,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,offset_x='512',offset_y='-512',iters=5))
    swim_requests.append(swim_request('512',im_1,im_2,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,offset_x='-512',offset_y='512',iters=5))
    swim_requests.append(swim_request('512',im_1,im_2,base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,rota=ang,offset_x='-512',offset_y='-512',iters=5))
    run_swim_requests(swim_requests)

    afm, aim = mir_get_affine(swim_requests)

    print('First AI: \n\n' + str(aim) + '\n')

    '''
    swim_requests = []
    swim_requests.append(swim_request('512',im_1,im_2,iters='3',offset_x='512',offset_y='512',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))
    swim_requests.append(swim_request('512',im_1,im_2,iters='3',offset_x='-512',offset_y='512',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))
    swim_requests.append(swim_request('512',im_1,im_2,iters='3',offset_x='512',offset_y='-512',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))
    swim_requests.append(swim_request('512',im_1,im_2,iters='3',offset_x='-512',offset_y='-512',base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))
    run_swim_requests(swim_requests)

    afm, aim = mir_get_affine(swim_requests)

    print('Second AI: \n\n' + str(aim) + '\n')
    '''

    swim_requests = []
    ww = '512'
    wx = ['-300','300']
    wy = ['-300','300']
    for x in range(len(wx)):
      for y in range(len(wy)):
        swim_requests.append(swim_request(ww,im_1,im_2,iters='5',offset_x=wx[x],offset_y=wy[y],base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))

    run_swim_requests(swim_requests)

    afm, aim = mir_get_affine(swim_requests)

    print('2x2 recipe 1,  AI: \n\n' + str(aim) + '\n')


    swim_requests = []
    ww = '512'
    wx = ['-300','300']
    wy = ['-300','300']
    for x in range(len(wx)):
      for y in range(len(wy)):
        swim_requests.append(swim_request(ww,im_1,im_2,iters='5',offset_x=wx[x],offset_y=wy[y],base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))

    run_swim_requests(swim_requests)

    afm, aim = mir_get_affine(swim_requests)

    print('2x2 recipe 2  AI: \n\n' + str(aim) + '\n')



    '''
    swim_requests = []
    ww = '256'
    wx = ['-300','0','300']
    wy = ['-300','0','300']
    for x in range(len(wx)):
      for y in range(len(wy)):
        swim_requests.append(swim_request(ww,im_1,im_2,iters='5',offset_x=wx[x],offset_y=wy[y],base_x=swim_req.base_x,base_y=swim_req.base_y,adjust_x=swim_req.adjust_x,adjust_y=swim_req.adjust_y,afm=aim))

    run_swim_requests(swim_requests)

    afm, aim = mir_get_affine(swim_requests)

    print('3x3 recipe 1,  AI: \n\n' + str(aim) + '\n')
    '''


    #align_test = align_image_pair_recipe('test_im_1.jpg','test_im_2.jpg')
    #align_test.mir_get_affine(swim_requests)

    exit()

