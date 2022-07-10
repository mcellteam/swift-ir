#!/usr/bin/env python2.7

# This file was previously named 'alignment_process.py'
import numpy as np
# import matplotlib.pyplot as plt
import os
import sys
import platform
import subprocess as sp
from .get_image_size import get_image_size
from .loadImage import loadImage
from .saveImage import saveImage
from .python_swiftir.affineImage import affineImage
from .python_swiftir.swiftir import apodize2
from .python_swiftir.swiftir import mirIterate
from .python_swiftir.swiftir import stationaryToMoving
from .python_swiftir.swiftir import stationaryPatches
from .python_swiftir.swiftir import movingPatches
from .python_swiftir.swiftir import multiSwim

__all__ = ['alignment_process']

'''
alignment_process.py implements a simple generic interface for aligning two images in SWiFT-IR
This version uses py

The interface is composed of two classes:  align_recipe and align_ingredient
The general concept is that the alignment of two images is accomplished by applying a
a series of steps, or "ingredients" to first estimate and then refine the python_swiftir transform
which brings the "moving" image into alignment with the "stationary" image.
Together these ingredients comprise a procedure, or "recipe".
'''

# pyswift_tui calls this -jy

# This is monotonic (0 to 100) with the amount of output:
debug_level = 10  # A larger value prints more stuff
# debug_level = 100  # A larger value prints more stuff

# Using the Python version does not work because the Python 3 code can't
# even be parsed by Python2. It could be dynamically compiled, or use the
# alternate syntax, but that's more work than it's worth for now.
if sys.version_info >= (3, 0):
    pass
    # if debug_level > 10: print ( "Python 3: Supports arbitrary arguments via print")
    # def print_debug ( level, *ds ):
    #  # print_debug ( 1, "This is really important!!" )
    #  # print_debug ( 99, "This isn't very important." )
    #  global debug_level
    #  if level <= debug_level:
    #    print ( *ds )
else:
    if debug_level > 10: print("Python 2: Use default parameters for limited support of arbitrary arguments via print")


# For now, always use the limited argument version
def print_debug(level, p1=None, p2=None, p3=None, p4=None):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
    global debug_level
    if level <= debug_level:
        if p1 == None:
            sys.stderr.write('' + '\n')
        elif p2 == None:
            sys.stderr.write(str(p1) + '\n')
        elif p3 == None:
            sys.stderr.write(str(p1) + str(p2) + '\n')
        elif p4 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + '\n')
        else:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + '\n')


# 0707 changed default to 'c'
global_swiftir_mode = 'c'  # Either 'python' or 'c'
# global_swiftir_mode = 'python'   # Either 'python' or 'c'
global_do_swims = True
global_do_cfms = True
global_gen_imgs = True


def run_command(cmd, arg_list=None, cmd_input=None):
    print_debug(10, "\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    print_debug(10, "  Running command: " + str(cmd_arg_list))
    print_debug(20, "   Passing Data\n==========================\n" + str(cmd_input) + "==========================\n")
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)

    # Note: decode bytes if universal_newlines=False in Popen
    # cmd_stdout = cmd_stdout.decode('utf-8')
    # cmd_stderr = cmd_stderr.decode('utf-8')
    print_debug(20, "Command output: \n\n" + cmd_stdout + "==========================\n")
    print_debug(30, "Command error: \n\n" + cmd_stderr + "==========================\n")

    print_debug(10, "=================================================\n")

    return ({'out': cmd_stdout, 'err': cmd_stderr})


# recipe_dict = {}

# recipe_dict['default'] = [affine_align_recipe(), affine_2x2_recipe, affine_4x4_recipe]
# recipe_dict['match_point'] = [affine_translation_recipe, affine_2x2_recipe, affine_4x4_recipe]

def prefix_lines(i, s):
    return ('\n'.join([i + ss.rstrip() for ss in s.split('\n') if len(ss) > 0]) + "\n")


class alignment_process:

    def __init__(self, im_sta_fn=None, im_mov_fn=None, align_dir='./', layer_dict=None, init_affine_matrix=None,
                 cumulative_afm=None):
        self.recipe = None
        self.im_sta_fn = im_sta_fn
        self.im_mov_fn = im_mov_fn
        self.align_dir = align_dir

        if layer_dict != None:
            self.layer_dict = layer_dict
            self.im_sta_fn = self.layer_dict['images']['ref']['filename']
            self.im_mov_fn = self.layer_dict['images']['base']['filename']
        else:
            self.layer_dict = {
                "images": {
                    "ref": {"filename": im_sta_fn},
                    "base": {"filename": im_mov_fn}
                },
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
            self.init_affine_matrix = identityAffine()
        else:
            self.init_affine_matrix = init_affine_matrix
        self.cumulative_afm = identityAffine()

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

    #TODO ============================================================
    '''#0707 NOTE: called in run_project_json'''
    def align(self, c_afm, save=True):
        print('align_alignment_process | align >>>>>>>>')

        atrm = self.layer_dict['align_to_ref_method']
        result = None
        if atrm['selected_method'] == 'Auto Swim Align':
            result = self.auto_swim_align(c_afm, save=save)
        elif atrm['selected_method'] == 'Match Point Align':
            result = self.auto_swim_align(c_afm, save=save)

        print('<<<<<<<< align_alignment_process | align')

        return result



    '''' #0707 (!) auto_swim_align function '''

    def auto_swim_align(self, c_afm, save=True):
        print('#0707 align_alignment_process | auto_swim_align >>>>>>>>')

        print_debug(50, "\n\n\n")
        print_debug(20, "********************************")
        print_debug(20, "*** Top of auto_swim_align() ***")
        print_debug(20, "********************************")
        print_debug(50, "\n\n")

        #    im_sta = loadImage(self.im_sta_fn)
        #    im_mov = loadImage(self.im_mov_fn)
        #    siz = (int(im_sta.shape[0]), int(im_sta.shape[1]))

        # Get Image Size
        siz = get_image_size(self.im_sta_fn)

        atrm = self.layer_dict['align_to_ref_method']
        # window size scale factor
        wsf = atrm['method_data']['win_scale_factor']

        #    Previously hard-coded values for wsf chosen by trial-and-error
        #    wsf = 0.80  # Most common good value for wsf
        #    wsf = 0.75  # Also a good value for most projects

        #    wsf = 0.90
        #    wsf = 1.0

        # Set up 1x1 point and window
        pa = np.zeros((2, 1))  # Point Array for one point

        wwx_f = siz[0]  # Window Width in x (Full Size)
        wwy_f = siz[1]  # Window Width in y (Full Size)
        wwx = int(wsf * wwx_f)  # Window Width in x Scaled
        wwy = int(wsf * wwy_f)  # Window Width in y Scaled
        cx = int(wwx_f / 2.0)  # Window Center in x
        cy = int(wwy_f / 2.0)  # Window Center in y
        pa[0, 0] = cx
        pa[1, 0] = cy
        psta_1 = pa

        # Set up 2x2 points and windows
        nx = 2
        ny = 2
        pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
        s = int(wwx_f / 2.0)  # Initial Size of each window
        for x in range(nx):
            for y in range(ny):
                pa[0, x + nx * y] = int(0.5 * s + s * x)  # Point Array (2x4) points
                pa[1, x + nx * y] = int(0.5 * s + s * y)  # Point Array (2x4) points
        s_2x2 = int(wsf * s)
        psta_2x2 = pa

        # Set up 4x4 points and windows
        nx = 4
        ny = 4
        pa = np.zeros((2, nx * ny))
        s = int(wwx_f / 4.0)  # Initial Size of each window
        for x in range(nx):
            for y in range(ny):
                pa[0, x + nx * y] = int(0.5 * s + s * x)
                pa[1, x + nx * y] = int(0.5 * s + s * y)
        s_4x4 = int(wsf * s)
        #    s_4x4 = int(s)
        psta_4x4 = pa

        # Set up a window size for match point alignment (1/32 of x dimension)
        s_mp = int(siz[0] / 32.0)

        print_debug(70, "  psta_1   = " + str(psta_1))
        print_debug(70, "  psta_2x2 = " + str(psta_2x2))
        print_debug(70, "  psta_4x4 = " + str(psta_4x4))

        # im_sta_fn is 'ref', im_mov_fn is 'base'
        #    self.recipe = align_recipe(im_sta, im_mov, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
        self.recipe = align_recipe(im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)  # tag

        wht = atrm['method_data']['whitening_factor']
        if atrm['selected_method'] == 'Auto Swim Align':
            alignment_option = atrm['method_data'].get('alignment_option')
            if alignment_option == 'refine_affine':
                ingredient_4x4 = align_ingredient(ww=int(s_4x4), psta=psta_4x4, afm=self.init_affine_matrix, wht=wht)
                self.recipe.add_ingredient(ingredient_4x4)
            elif alignment_option == 'apply_affine':
                ingredient_apply_affine = align_ingredient(afm=self.init_affine_matrix, align_mode='apply_affine_align')
                self.recipe.add_ingredient(ingredient_apply_affine)
            else:
                # Normal Auto Swim Align - Full Recipe for init_affine
                ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht)  # 1x1 SWIM window
                ingredient_2x2 = align_ingredient(ww=s_2x2, psta=psta_2x2, wht=wht)
                ingredient_4x4 = align_ingredient(ww=s_4x4, psta=psta_4x4, wht=wht)
                self.recipe.add_ingredient(ingredient_1)
                self.recipe.add_ingredient(ingredient_2x2)
                self.recipe.add_ingredient(ingredient_4x4)
        elif atrm['selected_method'] == 'Match Point Align':
            # Get match points from self.layer_dict['images']['base']['metadata']['match_points']
            mp_base = np.array(self.layer_dict['images']['base']['metadata']['match_points']).transpose()
            mp_ref = np.array(self.layer_dict['images']['ref']['metadata']['match_points']).transpose()
            # First ingredient is to calculate the Affine matrix from match points alone
            ingredient_1_mp = align_ingredient(psta=mp_ref, pmov=mp_base, align_mode='match_point_align', wht=wht)
            # Second ingredient is to refine the Affine matrix by swimming at each match point
            ingredient_2_mp = align_ingredient(ww=s_mp, psta=mp_ref, pmov=mp_base, wht=wht)
            self.recipe.add_ingredient(ingredient_1_mp)  # This one will set the Affine matrix
            self.recipe.add_ingredient(ingredient_2_mp)  # This one will use the previous Affine and refine it

        ingredient_check_align = align_ingredient(ww=(wwx_f, wwy_f), psta=psta_1, iters=1, align_mode='check_align', wht=wht)

        # DISABLE CHECK_ALIGN INGREDIENT FOR PERFORMANCE TESTING
        #    self.recipe.add_ingredient(ingredient_check_align)

        self.recipe.execute()  # DOES the alignment -jy

        self.setCafm(c_afm, bias_mat=None)  # returns new current c_afm -jy

        # Retrieve alignment result
        snr = self.recipe.ingredients[-1].snr
        snr_report = self.recipe.ingredients[-1].snr_report
        afm = self.recipe.ingredients[-1].afm
        c_afm = self.cumulative_afm

        # Put alignment results into layer_dict
        atrm['method_results']['snr'] = list(snr)
        atrm['method_results']['snr_report'] = snr_report
        atrm['method_results']['affine_matrix'] = afm.tolist()
        atrm['method_results']['cumulative_afm'] = c_afm.tolist()

        atrm['method_data']['bias_x_per_image'] = 0  # x_bias
        atrm['method_data']['bias_y_per_image'] = 0  # y_bias
        atrm['method_data']['bias_rot_per_image'] = 0  # rot_bias
        atrm['method_data']['bias_scale_x_per_image'] = 0  # scale_x_bias
        atrm['method_data']['bias_scale_y_per_image'] = 0  # scale_y_bias
        atrm['method_data']['bias_skew_x_per_image'] = 0  # skew_x_bias

        if save:
            self.saveAligned()

        return self.cumulative_afm

    def setCafm(self, c_afm, bias_mat=None):
        '''Calculate new cumulative python_swiftir for current stack location'''
        self.cumulative_afm = composeAffine(self.recipe.afm, c_afm)
        # matrix multiplication of current python_swiftir matrix with c_afm (cumulative) -jy
        # current cumulative "at this point in the stack"

        # Apply bias_mat if given
        if type(bias_mat) != type(None):
            self.cumulative_afm = composeAffine(bias_mat, self.cumulative_afm)

        return self.cumulative_afm

    def saveAligned(self, rect=None, apodize=False, grayBorder=False):

        print_debug(12, "\nsaveAligned self.cumulative_afm: " + str(self.cumulative_afm))

        im_mov = loadImage(self.im_mov_fn)
        print_debug(4, "\nTransforming " + str(self.im_mov_fn))
        print_debug(12, " with:")
        print_debug(12, "  self.cumulative_afm = " + str(self.cumulative_afm))
        print_debug(12, "  rect = " + str(rect))
        print_debug(12, "  grayBorder = " + str(grayBorder))
        # print ( 100*'#' )
        # print ( 100*'#' )
        # print ( "  WARNING: Hard-coding rect as test!! ")
        # rect = [-116, -116, 914, 914]
        # print ( 100*'#' )
        # print ( 100*'#' )
        im_aligned = affineImage(self.cumulative_afm, im_mov, rect=rect, grayBorder=grayBorder)
        #      im_aligned = affineImage(self.cumulative_afm, im_mov, rect=rect)
        ofn = os.path.join(self.align_dir, os.path.basename(self.im_mov_fn))
        print('align_swiftir | class=alignment_process | fn saveAligned | ofn =  ', ofn)

        print_debug(4, "  saving as: " + str(ofn))
        if apodize:
            im_apo = apodize2(im_aligned, wfrac=1 / 3.)
            saveImage(im_apo, ofn)
        else:
            saveImage(im_aligned, ofn)

        # del the images to allow for automatic garbage collection
        del im_mov
        del im_aligned


# Universal class for alignment recipes
class align_recipe:

    #  def __init__(self, im_sta, im_mov, im_sta_fn=None, im_mov_fn=None):
    def __init__(self, im_sta_fn=None, im_mov_fn=None):
        print('align_recipe (constructor) >>>>>>>>')
        self.ingredients = []
        #    self.im_sta = im_sta
        #    self.im_mov = im_mov
        self.im_sta = None
        self.im_mov = None
        self.im_sta_fn = im_sta_fn
        self.im_mov_fn = im_mov_fn
        self.afm = identityAffine()

        global global_swiftir_mode
        self.swiftir_mode = global_swiftir_mode

        # Get Image Size
        self.siz = get_image_size.get_image_size(self.im_sta_fn)

        print('<<<<<<<< align_recipe (constructor)')

    def __str__(self):
        s = "recipe: \n"
        if self.ingredients == None:
            s += "  ing[]: None\n"
        else:
            s += "  ing[]:\n"
            for ing in self.ingredients:
                s += prefix_lines('    ', str(ing))
        return s

    def add_ingredient(self, ingredient):
        ingredient.im_sta = self.im_sta
        ingredient.im_mov = self.im_mov
        ingredient.im_sta_fn = self.im_sta_fn
        ingredient.im_mov_fn = self.im_mov_fn
        ingredient.recipe = self
        self.ingredients.append(ingredient)

    def execute(self):
        print('align_recipe.execute | self.swiftir_mode = ', self.swiftir_mode)

        # Load images now but only in 'python' mode
        #    C SWiFT-IR loads its own images
        if self.swiftir_mode == 'python':
            self.im_sta = loadImage(self.im_sta_fn)
            self.im_mov = loadImage(self.im_mov_fn)

        # Initialize afm to afm of first ingredient in recipe
        if type(self.ingredients[0].afm) != type(None):
            self.afm = self.ingredients[0].afm

        # Execute each ingredient in recipe
        for ingredient in self.ingredients:
            ingredient.afm = self.afm
            self.afm = ingredient.execute()

        # del the images to allow for automatic garbage collection
        del self.im_sta
        del self.im_mov


# Universal class for alignment ingredients of recipes
class align_ingredient:
    '''Initialized with paths to mir/swim'''

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
    #  def __init__(self, im_sta=None, im_mov=None, ww=None, psta=None, pmov=None, afm=None, wht=-0.68, iters=2, align_mode='swim_align', im_sta_fn=None, im_mov_fn=None):
    def __init__(self, ww=None, psta=None, pmov=None, afm=None, wht=-0.68, iters=2, align_mode='swim_align'):
        print('\n\n\n\n\n')
        print('align_align_ingredient >>>>>>>>')

        self.swim_drift = 0.5

        self.afm = afm
        self.recipe = None
        #    self.im_sta = im_sta
        #    self.im_mov = im_mov
        #    self.im_sta_fn = im_sta_fn
        #    self.im_mov_fn = im_mov_fn
        self.ww = ww
        self.psta = psta
        self.pmov = pmov
        self.wht = wht
        #    self.wht = -0.3
        self.iters = iters
        self.align_mode = align_mode
        self.snr = None
        self.snr_report = None
        self.threshold = (3.5, 200, 200)

        #    global global_swiftir_mode
        #    self.swiftir_mode = global_swiftir_mode

        # Configure platform-specific path to executables for C SWiFT-IR
        my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        self.system = platform.system()
        self.node = platform.node()
        if self.system == 'Darwin':
            # self.swim_c = my_path + 'lib/bin_darwin/swim'
            self.swim_c = my_path + '../lib/bin_darwin/swim'
            # self.mir_c = my_path + 'lib/bin_darwin/mir'
            self.mir_c = my_path + '../lib/bin_darwin/mir'
        elif self.system == 'Linux':
            if '.tacc.utexas.edu' in self.node:
                # self.swim_c = my_path + 'lib/bin_tacc/swim'
                self.swim_c = my_path + '../lib/bin_tacc/swim'
                # self.mir_c = my_path + 'lib/bin_tacc/mir'
                self.mir_c = my_path + '../lib/bin_tacc/mir'
            else:
                # self.swim_c = my_path + 'lib/bin_linux/swim'
                self.swim_c = my_path + '../lib/bin_linux/swim'
                # self.mir_c = my_path + 'lib/bin_linux/mir'
                self.mir_c = my_path + '../lib/bin_linux/mir'

        # if self.swiftir_mode == 'c':
        #  print_debug ( 70, "Actually loading images" )
        #  self.im_sta = loadImage(self.im_sta_fn)
        #  self.im_mov = loadImage(self.im_mov_fn)

    def __str__(self):
        s = "ingredient:\n"
        s += "  mode: " + str(self.align_mode) + "\n"
        s += "  ww: " + str(self.ww) + "\n"
        s += "  psta:\n" + prefix_lines('    ', str(self.psta)) + "\n"
        s += "  pmov:\n" + prefix_lines('    ', str(self.pmov)) + "\n"
        s += "  afm:\n" + prefix_lines('    ', str(self.afm)) + "\n"
        return s

    def set_swim_results(self, swim_stdout, swim_stderr):

        toks = swim_stdout.replace('(', ' ').replace(')', ' ').strip().split()

        self.snr = float(toks[0][0:-1])
        self.base_x = float(toks[2])
        self.base_y = float(toks[3])
        self.adjust_x = float(toks[5])
        self.adjust_y = float(toks[6])
        self.dx = float(toks[8])
        self.dy = float(toks[9])
        self.m0 = float(toks[10])
        self.flags = None
        if len(toks) > 11:
            self.flags = toks[11:]  # Note flags: will be a str or list of strs

        #    warp_matrix[0,2]=dx
        #    warp_matrix[1,2]=dy
        #    print_debug ( 70, '%s %s : swim match:  SNR: %g  dX: %g  dY: %g' % (self.im_base, self.im_adjust, self.snr, self.dx, self.dy))
        pass

    def run_swim_c(self):  # , offx=0, offy=0, keep=None, base_x=None, base_y=None, adjust_x=None, adjust_y=None, rota=None, afm=None ):

        print_debug(50, "--------------------------")

        print_debug(50, "Inside run_swim_c() with self = align_ingredient:")
        print_debug(50, str(self))

        #    wwx_f = int(self.im_sta.shape[0])        # Window Width in x (Full Size)
        #    wwy_f = int(self.im_sta.shape[1])        # Window Width in y (Full Size)
        wwx_f = self.recipe.siz[0]  # Window Width in x (Full Size)
        wwy_f = self.recipe.siz[1]  # Window Width in y (Full Size)
        cx = int(wwx_f / 2.0)
        cy = int(wwy_f / 2.0)

        base_x = str(cx)
        base_y = str(cy)

        adjust_x = '%.6f' % (cx + self.afm[0, 2])
        adjust_y = '%.6f' % (cy + self.afm[1, 2])

        afm_arg = '%.6f %.6f %.6f %.6f' % (self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1])

        karg = ''
        # if keep != None:
        #  karg = '-k %s' % (keep)

        rota_arg = ''
        # if rota!=None:
        #  rota_arg = '%s' % (rota)

        '''
        tar_arg = ''
        if base_x!=None and base_y!=None:
          tar_arg = '%s %s' % (base_x, base_y)
    
        pat_arg = ''
        if adjust_x!=None and adjust_y!=None:
          pat_arg = '%s %s' % (adjust_x, adjust_y)
    
        afm_arg = ''
        if type(afm)!=type(None):
          afm_arg = '%.6f %.6f %.6f %.6f' % (afm[0,0], afm[0,1], afm[1,0], afm[1,1])
        '''

        swim_ww_arg = '1024'
        if type(self.ww) == type((1, 2)):
            swim_ww_arg = str(self.ww[0]) + "x" + str(self.ww[1])
        else:
            swim_ww_arg = str(self.ww)

        print_debug(20, "--------------------------")

        print_debug(50, str(self))

        print_debug(10, "")

        swim_results = []
        # print_debug ( 50, "psta = " + str(self.psta) )
        multi_swim_arg_string = ""
        for i in range(len(self.psta[0])):
            offx = int(self.psta[0][i] - (wwx_f / 2.0))
            offy = int(self.psta[1][i] - (wwy_f / 2.0))
            print_debug(10, "Will run a swim of " + str(self.ww) + " at (" + str(offx) + "," + str(offy) + ")")
            swim_arg_string = 'ww_' + swim_ww_arg + \
                              ' -i ' + str(self.iters) + \
                              ' -w ' + str(self.wht) + \
                              ' -x ' + str(offx) + \
                              ' -y ' + str(offy) + \
                              ' ' + karg + \
                              ' ' + self.recipe.im_sta_fn + \
                              ' ' + base_x + \
                              ' ' + base_y + \
                              ' ' + self.recipe.im_mov_fn + \
                              ' ' + adjust_x + \
                              ' ' + adjust_y + \
                              ' ' + rota_arg + \
                              ' ' + afm_arg
            print_debug(20, "  " + swim_arg_string)
            # print_debug ( 50, "  " + swim_arg_string2 )
            multi_swim_arg_string += swim_arg_string + "\n"

        print_debug(10, "")

        o = run_command(self.swim_c, arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string)

        swim_out_lines = o['out'].strip().split('\n')
        swim_err_lines = o['err'].strip().split('\n')
        swim_results.append({'out': swim_out_lines, 'err': swim_err_lines})

        '''
        swim_log = open('swim_log.txt','a')
        swim_log.write('\n---------------------------------\n')
        swim_log.write('swim_cmd: \n  %s %s %s\n\n' % (self.swim_c, str(swim_ww_arg), str(multi_swim_arg_string)))
        swim_log.write('swim_stdout: \n%s\n\n' % (o['out']))
        swim_log.write('swim_stderr: \n%s\n\n' % (o['err']))
        '''

        mir_script = ""
        snr_list = []
        dx = dy = 0.0
        for l in swim_out_lines:
            if len(swim_out_lines) == 1:
                print_debug(50, "SWIM OUT: " + str(l))
                toks = l.replace('(', ' ').replace(')', ' ').strip().split()
                dx = float(toks[8])
                dy = float(toks[9])
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                print_debug(60, "SNR: " + str(toks[0]))
                snr_list.append(float(toks[0][0:-1]))
            else:
                print_debug(50, "SWIM OUT: " + str(l))
                toks = l.replace('(', ' ').replace(')', ' ').strip().split()
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                print_debug(60, "SNR: " + str(toks[0]))
                snr_list.append(float(toks[0][0:-1]))
        mir_script += 'R\n'

        # print_debug ( 50, "mir_script: " + mir_script )

        o = run_command(self.mir_c, arg_list=[], cmd_input=mir_script)

        mir_out_lines = o['out'].strip().split('\n')
        mir_err_lines = o['err'].strip().split('\n')
        print_debug(60, str(mir_out_lines))
        print_debug(60, str(mir_err_lines))

        '''
        swim_log.write('\n\nmir_cmd: \n  %s %s\n\n' % (self.mir_c, str(mir_script)))
        swim_log.write('mir_stdout: \n%s\n\n' % (o['out']))
        swim_log.write('mir_stderr: \n%s\n\n' % (o['err']))
        swim_log.write('\n---------------------------------\n\n')
        swim_log.close()
        '''

        # Separate the results into a list of token lists

        afm = np.eye(2, 3, dtype=np.float32)
        aim = np.eye(2, 3, dtype=np.float32)

        if len(swim_out_lines) == 1:
            aim[0, 2] = dx + 0.5
            aim[1, 2] = dy + 0.5
        else:
            for line in mir_out_lines:
                print_debug(70, "Line: " + str(line))
                toks = line.strip().split()
                if (toks[0] == 'AF'):
                    afm[0, 0] = float(toks[1])
                    afm[0, 1] = float(toks[2])
                    afm[0, 2] = float(toks[3]) - self.swim_drift  # ???
                    afm[1, 0] = float(toks[4])
                    afm[1, 1] = float(toks[5])
                    afm[1, 2] = float(toks[6]) - self.swim_drift  # ???
                if (toks[0] == 'AI'):
                    aim[0, 0] = float(toks[1])
                    aim[0, 1] = float(toks[2])
                    aim[0, 2] = float(toks[3]) + self.swim_drift
                    aim[1, 0] = float(toks[4])
                    aim[1, 1] = float(toks[5])
                    aim[1, 2] = float(toks[6]) + self.swim_drift

        print_debug(20, "\nAIM = " + str(aim))

        if self.align_mode == 'swim_align':
            self.afm = aim

        #    if self.align_mode == 'check_align':
        #      self.snr = snr_list
        self.snr = snr_list

        return self.afm

    def execute(self):

        global global_do_swims
        global global_do_cfms
        global global_gen_imgs

        if global_do_swims: print_debug(10, "Doing swims")
        if global_do_cfms: print_debug(10, "Doing cfms")
        if global_gen_imgs: print_debug(10, "Generating images")

        # If ww==None then this is a Matching Point ingredient of a recipe
        # Calculate afm directly using psta and pmov as the matching points
        if self.align_mode == 'match_point_align':
            (self.afm, err, n) = mirIterate(self.psta, self.pmov)
            self.ww = (0.0, 0.0)
            self.snr = np.zeros(len(self.psta[0]))
            snr_array = self.snr
            self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
            snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            print_debug(10, self.snr_report)
            return self.afm
        elif self.align_mode == 'apply_affine_align':
            self.snr = np.zeros(1)
            snr_array = self.snr
            self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
            snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            print_debug(10, self.snr_report)
            return self.afm

        #  Otherwise, this is a swim window match ingredient
        #  Refine the afm via swim and mir
        afm = self.afm
        if type(afm) == type(None):
            afm = identityAffine()

        if self.recipe.swiftir_mode == 'c':

            print_debug(50, "Running c version of swim")

            afm = self.run_swim_c()

        else:

            print_debug(50, "Running python version of swim")
            self.pmov = stationaryToMoving(afm, self.psta)
            sta = stationaryPatches(self.recipe.im_sta, self.psta, self.ww)
            for i in range(self.iters):
                print_debug(50, 'psta = ' + str(self.psta))
                print_debug(50, 'pmov = ' + str(self.pmov))
                mov = movingPatches(self.recipe.im_mov, self.pmov, afm, self.ww)
                (dp, ss, snr) = multiSwim(sta, mov, pp=self.pmov, afm=afm, wht=self.wht)
                print_debug(50, '  dp,ss,snr = ' + str(dp) + ', ' + str(ss) + ', ' + str(snr))
                self.pmov = self.pmov + dp
                (afm, err, n) = mirIterate(self.psta, self.pmov)
                self.pmov = stationaryToMoving(afm, self.psta)
                print_debug(50, '  Affine err:  %g' % (err))
                print_debug(50, '  SNR:  ' + str(snr))
            self.snr = snr

        snr_array = np.array(self.snr)
        #    self.snr = [snr_array.mean()]
        self.snr = snr_array
        self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
        snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
        print_debug(10, self.snr_report)

        if self.align_mode == 'swim_align':
            self.afm = afm

        if debug_level >= 101:
            print_debug(50, "Entering the command line debugger:")
            __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        return self.afm


# def showdiff(ima, imb):
#     err = ima.astype('float32') - imb.astype('float32')
#     err = err[100:-100,100:-100]
#     print_debug ( 1, 'rms image error = ', np.sqrt(np.mean(err*err)))
#     blk = ima<imb
#     dif = ima - imb
#     dif[blk] = imb[blk] - ima[blk]
#     plt.clf()
#     plt.imshow(dif, cmap='gray')
#     plt.show()


def align_images(im_sta_fn, im_mov_fn, align_dir, global_afm):
    print_debug(50,
                "\n\n%%%%%%%%%%%%%%%%%%%%%%%%%%% Static Function Call to align_images %%%%%%%%%%%%%%%%%%%%%%%%%%%\n")
    if type(global_afm) == type(None):
        global_afm = identityAffine()

    im_sta = loadImage(im_sta_fn)
    im_mov = loadImage(im_mov_fn)

    pa = np.zeros((2, 1))
    wwx = int(im_sta.shape[0])
    wwy = int(im_sta.shape[1])
    cx = int(wwx / 2)
    cy = int(wwy / 2)
    pa[0, 0] = cx
    pa[1, 0] = cy
    psta_1 = pa

    nx = 2
    ny = 2
    pa = np.zeros((2, nx * ny))
    s = int(im_sta.shape[0] / 2)
    for x in range(nx):
        for y in range(ny):
            pa[0, x + nx * y] = int(0.5 * s + s * x)
            pa[1, x + nx * y] = int(0.5 * s + s * y)
    s_2x2 = s
    psta_2x2 = pa

    nx = 4
    ny = 4
    pa = np.zeros((2, nx * ny))
    s = int(im_sta.shape[0] / 4)
    for x in range(nx):
        for y in range(ny):
            pa[0, x + nx * y] = int(0.5 * s + s * x)
            pa[1, x + nx * y] = int(0.5 * s + s * y)
    s_4x4 = s
    psta_4x4 = pa

    recipe = align_recipe(im_sta, im_mov, im_sta_fn=im_sta_fn, im_mov_fn=im_mov_fn)

    ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1)
    ingredient_2x2 = align_ingredient(ww=s_2x2, psta=psta_2x2)
    ingredient_4x4 = align_ingredient(ww=s_4x4, psta=psta_4x4)
    ingredient_check_align = align_ingredient(ww=(wwx, wwy), psta=psta_1, iters=1, align_mode='check_align')

    recipe.add_ingredient(ingredient_1)
    recipe.add_ingredient(ingredient_2x2)
    recipe.add_ingredient(ingredient_4x4)
    recipe.add_ingredient(ingredient_check_align)

    recipe.execute()

    global_afm = composeAffine(recipe.afm, global_afm)
    im_aligned = affineImage(global_afm, im_mov)
    ofn = os.path.join(align_dir, os.path.basename(im_mov_fn))
    saveImage(im_aligned, ofn)

    return (global_afm, recipe)


# import argparse
import sys

if __name__ == '__main__':
    print("Running " + __file__ + ".__main__()")

    # "Tile_r1-c1_LM9R5CA1series_247.jpg",
    # "Tile_r1-c1_LM9R5CA1series_248.jpg",

    # These are the defaults
    f1 = "vj_097_shift_rot_skew_crop_1.jpg"
    f2 = "vj_097_shift_rot_skew_crop_2.jpg"
    out = os.path.join("../../../../../../..", "aligned")

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
        print_debug(50, "Current args: " + str(args))
        if args[0] == '-c':
            print_debug(50, "Running in 'c' mode")
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
            cafm = [float(v) for v in args[0].split(' ')[1].split(',')]
            if len(cafm) == 6:
                cumulative_afm = [cafm[0:3], cafm[3:6]]
            args = args[1:]
        elif args[0] == '-match':
            # This will be -match 0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2
            #   representing [ [ [0.1,0.2], [0.3,0.4], [0.5,0.6] ], [ [0.7,0.8], [0.9,1.0], [1.1,1.2] ] ]
            # Note that the first sub-array are all the match points from the first image,
            #   and the second sub-array are corresponding match points from second image
            # Example for tests/vj_097_shift_rot_skew_crop_1.jpg and tests/vj_097_shift_rot_skew_crop_2.jpg:
            #   327.8,332.0,539.4,208.8,703.3,364.3,266.2,659.9,402.1,249.4,605.2,120.5,776.2,269.0,353.0,580.0

            args = args[1:]
            match = [float(v) for v in args[0].split(',')]
            args = args[1:]
            # Force the number of points to be a multiple of 4 (2 per point by 2 per pair)
            npts = (len(match) / 2) / 2
            if npts > 0:
                match_points = [[], []]
                # Split the original one dimensional array into 2 parts (one for each image)
                m = [match[0:npts * 2], match[npts * 2:]]
                # Group the floats for each image into pairs representing points
                match_points[0] = [[m[0][2 * i], m[0][(2 * i) + 1]] for i in range(len(m[0]) / 2)]
                match_points[1] = [[m[1][2 * i], m[1][(2 * i) + 1]] for i in range(len(m[1]) / 2)]

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

    print_debug(50, "Creating the alignment process")
    align_proc = alignment_process(f1,
                                   f2,
                                   out,
                                   layer_dict=layer_dict,
                                   cumulative_afm=cumulative_afm)

    if global_swiftir_mode == 'c':
        print_debug(50, "Loading the images")
        if not (align_proc.recipe is None):
            if not (align_proc.recipe.ingredients is None):
                im_sta = loadImage(f1)
                im_mov = loadImage(f2)
                for ing in align_proc.recipe.ingredients:
                    ing.im_sta = im_sta
                    ing.im_mov = im_mov

    print_debug(50, "Performing the alignment")
    align_proc.align()

    """
    image_dir = './'
    align_dir = './aligned/'
    im_sta_fn = image_dir + 'Tile_r1-c1_LM9R5CA1series_247.jpg'
    im_mov_fn = image_dir + 'Tile_r1-c1_LM9R5CA1series_248.jpg'
  
  
    global_afm = identityAffine()
  
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
  
    pmov = stationaryToMoving(afm, psta)
    sta = stationaryPatches(im_sta, psta, ww)
    mov = movingPatches(im_mov, pmov, afm, ww)
    (dp, ss, snr) = multiSwim(sta, mov, pp=pmov, afm=afm, wht=-.65)
    print_debug ( 50, snr)
    print_debug ( 50, afm)
  
    #best = alignmentImage(sta[0], mov[0])
    #plt.imshow(best,cmap='gray')
    #plt.show()
  
    '''

def composeAffine(afm, bfm):
    '''COMPOSEAFFINE - Compose two python_swiftir transforms
    COMPOSEAFFINE(afm1, afm2) returns the python_swiftir transform AFM1 ∘ AFM2
    that applies AFM1 after AFM2.
    Affine matrices must be 2x3 numpy arrays.'''
    afm = np.vstack((afm, [0,0,1]))
    bfm = np.vstack((bfm, [0,0,1]))
    fm = np.matmul(afm, bfm)
    return fm[0:2,:]

def applyAffine(afm, xy):
    '''APPLYAFFINE - Apply python_swiftir transform to a point
    xy_ = APPLYAFFINE(afm, xy) applies the python_swiftir matrix AFM to the point XY
    Affine matrix must be a 2x3 numpy array. XY may be a list or an array.'''
    if not type(xy)==np.ndarray:
        xy = np.array([xy[0], xy[1]])
    return np.matmul(afm[0:2,0:2], xy) + reptoshape(afm[0:2,2], xy)

def identityAffine():
    '''IDENTITYAFFINE - Return an idempotent python_swiftir transform
    afm = IDENTITYAFFINE() returns an python_swiftir transform that is
    an identity transform.'''
    return np.array([[1., 0., 0.],
                     [0., 1., 0.]])

def reptoshape(mat, pattern):
    '''REPTOSHAPE - Repeat a matrix to match shape of other matrix
    REPTOSHAPE(mat, pattern) returns a copy of the matrix MAT replicated
    to match the shape of PATTERNS. For instance, if MAT is an N-vector
    or an Nx1 matrix, and PATTERN is NxK, the output will be an NxK matrix
    of which each the columns is filled with the contents of MAT.
    Higher dimensional cases are handled as well, but non-singleton dimensions
    of MAT must always match the corresponding dimension of PATTERN.'''
    ps = [x for x in pattern.shape]
    ms = [x for x in mat.shape]
    while len(ms)<len(ps):
        ms.append(1)
    mat = np.reshape(mat, ms)
    for d in range(len(ps)):
        if ms[d]==1:
            mat = np.repeat(mat, ps[d], d)
        elif ms[d] != ps[d]:
            raise ValueError('Cannot broadcast'  + str(mat.shape) + ' to '
                             + str(pattern.shape))
    return mat
