#!/usr/bin/env python3

import os
import re
import sys
import copy
import logging
import platform
import datetime
import time
import traceback
import numpy as np
import subprocess as sp
from typing import Dict, Any
import hashlib
import json
import psutil

__all__ = ['run_recipe']

ENABLE_LOGGING = 0


logger = logging.getLogger(__name__)
# MAlogger      = logging.getLogger('MAlogger')
# SWIMlogger    = logging.getLogger('SWIMlogger')
# RMlogger      = logging.getLogger('recipemaker')
# scratchlogger = logging.getLogger('scratch')

def run_recipe(data):
    '''Assemble and execute an alignment recipe
    :param data: data for a single pairwise alignment as Python dictionary.
    '''
    if os.path.basename(data['reference']) != '':
        recipe = align_recipe(
            data=data,)
        recipe.assemble_recipe()
        recipe.execute_recipe()

    return data

class align_recipe:

    # global scratchlogger

    # global SWIMlogger
    # global RMlogger
    # global MAlogger

    def __init__(self, data):
        self.data = data
        self.meta = self.data['alignment']['meta']
        self.configure_logging()
        self.cur_method = self.meta['current_method']
        self.defaults = self.meta['defaults']
        self.destination = self.meta['destination_path']
        self.scale_key = self.meta['scale_key']
        self.siz = self.meta['image_src_size']
        self.dev_mode = self.meta['dev_mode']
        self.scale_dir = os.path.join(self.meta['destination_path'], self.meta['scale_key'])
        self.init_afm = np.array(self.meta['init_afm'])
        self.fn_reference = self.meta['fn_reference']
        self.fn_transforming = self.meta['fn_transforming']
        self.alignment = self.data['alignment']
        self.alignment['method_results'].setdefault('affine_matrix', self.init_afm.tolist())
        self.alignment['method_results'].setdefault('snr', [])
        self.alignment['method_results'].setdefault('snr_report', 'SNR: --')
        self.option = ('init_affine','refine_affine')[self.meta['isRefinement']]
        if self.cur_method == 'grid-default':
            self.wht = self.defaults['signal-whitening']
            self.iters = self.defaults['swim-iterations']
        else:
            self.wht = self.alignment['swim_settings']['signal-whitening']
            self.iters = self.alignment['swim_settings']['iterations']
        if self.meta['isRefinement']:
            self.iters = 3
        self.grid_custom_regions  = self.alignment['swim_settings']['grid-custom-regions']
        self.ingredients = []
        self.initial_rotation = float(self.defaults['initial-rotation'])
        self.afm = np.array([[1., 0., 0.], [0., 1., 0.]])


        # Configure platform-specific path to executables for C SWiFT-IR
        slug = (('linux', 'darwin')[platform.system() == 'Darwin'], 'tacc')['tacc.utexas' in platform.node()]
        self.swim_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/swim'
        self.mir_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/mir'


    def __str__(self):
        s = "align_recipe: \n"
        s += "  dir: " + str(self.scale_dir) + "\n"
        s += "  sta: " + str(self.fn_reference) + "\n"
        s += "  mov: " + str(self.fn_transforming) + "\n"


    def configure_logging(self):
        MAlogger = logging.getLogger('MAlogger')
        SWIMlogger = logging.getLogger('SWIMlogger')
        RMlogger = logging.getLogger('recipemaker')
        logger = logging.getLogger(__name__)
        if self.meta['recipe_logging']:
            MAlogger.addHandler(logging.FileHandler(os.path.join(self.meta['destination_path'], 'logs', 'manual_align.log')))
            SWIMlogger.addHandler(logging.FileHandler(os.path.join(self.meta['destination_path'], 'logs', 'swim.log')))
            RMlogger.addHandler(logging.FileHandler(os.path.join(self.meta['destination_path'], 'logs', 'recipemaker.log')))
            # scratchpath = os.path.join(destination, 'logs', 'scratch.log')
            # try: os.remove(scratchpath)
            # except OSError: pass
            # fh = logging.FileHandler(scratchpath)
            # fh.setLevel(logging.DEBUG)
            # scratchlogger.addHandler(fh)
        else:
            MAlogger.disabled = True
            SWIMlogger.disabled = True
            RMlogger.disabled = True
            logger.disabled = True


    def megabytes(self):
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2

    def gigabytes(self):
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 3


    def assemble_recipe(self):
        # scratchlogger.critical(f'ASSEMBLING RECIPE [{self.cur_method}]...:')

        # Set up 1x1 point and window
        pa = np.zeros((2, 1))  # Point Array for one point
        pa[0, 0] = int(self.siz[0] / 2.0)  # Window Center in x
        pa[1, 0] = int(self.siz[1] / 2.0)  # Window Center in y
        psta_1 = pa

        # Example: psta_2x2 = [[256. 768. 256. 768.] [256. 256. 768. 768.]]

        if self.cur_method == 'grid-default':
            nx, ny = 2, 2
            pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
            sx = int(self.siz[0] / 2.0)  # Initial Size of each window
            sy = int(self.siz[1] / 2.0)  # Initial Size of each window
            for x in range(nx):
                for y in range(ny):
                    pa[0, x + nx * y] = int(0.5 * sx + sx * x)  # Point Array (2x4) points
                    pa[1, x + nx * y] = int(0.5 * sy + sy * y)  # Point Array (2x4) points
            psta_2x2 = pa
            ww_1x1 = self.defaults[self.scale_key]['swim-window-px']
            ww_2x2 = [int(ww_1x1[0]/2), int(ww_1x1[1]/2)]

            if self.meta['isRefinement']:
                '''Perform affine refinement'''
                self.add_ingredients([align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, afm=self.init_afm, ID='Grid2x2', last=True)])
            else:
                '''Perform affine initialization'''
                self.add_ingredients([
                    align_ingredient(mode='SWIM-Grid', ww=ww_1x1, psta=psta_1, ID='Grid1x1'),
                    align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-a'),
                    align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-b', last=True)])
        elif self.cur_method == 'grid-custom':
            ww_1x1 = self.alignment['grid_custom_px_1x1']
            ww_2x2 = self.alignment['grid_custom_px_2x2']
            x1 = ((self.siz[0] - ww_1x1[0]) / 2) + (ww_2x2[0] / 2)
            x2 = self.siz[0] - x1
            y1 = ((self.siz[1] - ww_1x1[1]) / 2) + (ww_2x2[1] / 2)
            y2 = self.siz[1] - y1
            cps = [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]
            nx, ny = 2, 2
            pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
            for i,p in enumerate(cps):
                pa[0,i] = int(p[0])
                pa[1,i] = int(p[1])
            psta_2x2 = pa
            self.add_ingredients([
                align_ingredient(mode='SWIM-Grid', ww=ww_1x1, psta=psta_1, ID='Grid1x1'),
                align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-a'),
                align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-b', last=True),
            ])
        else:
            ww = self.alignment['manual_swim_window_px']
            man_pmov = np.array(self.alignment['manpoints_mir']['base']).transpose()
            man_psta = np.array(self.alignment['manpoints_mir']['ref']).transpose()
            if self.cur_method == 'manual-hint':
                self.add_ingredients([
                    align_ingredient(mode='MIR', ww=ww, psta=man_psta, pmov=man_pmov),
                    align_ingredient(mode='SWIM-Manual', ww=ww, psta=man_psta, pmov=man_pmov, ID='Manual-a'),
                    align_ingredient(mode='SWIM-Manual', ww=ww, psta=man_psta, pmov=man_pmov, ID='Manual-b', last=True)])
            elif self.cur_method == 'manual-strict':
                self.add_ingredients([align_ingredient(mode='MIR', ww=ww, psta=man_psta, pmov=man_pmov, last=True)])


    def execute_recipe(self):

        self.afm = self.init_afm

        if (self.fn_reference == self.fn_transforming) or (self.fn_reference == ''):
            '''handle case where fn_reference is itself'''
            snr = np.array([0.0])
            snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
                snr.mean(), snr.std(), len(snr), snr.min(), snr.max())
            afm = self.init_afm
        else:
            try:
                # Execute each ingredient in recipe
                for i, ingredient in enumerate(self.ingredients):
                    ingredient.afm = self.afm
                    try:
                        self.afm = ingredient.execute_ingredient()
                    except:
                        print_exception(self.destination, extra=f'Error on ingredient {i} of {len(self.ingredients)}')
                snr = self.ingredients[-1].snr
                snr_report = self.ingredients[-1].snr_report
                afm = self.ingredients[-1].afm
            except:
                snr = np.array([0.0])
                snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
                    snr.mean(), snr.std(), len(snr), snr.min(), snr.max())
                afm = self.init_afm

        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            snr_list = snr.tolist()
        except:
            snr_list = list(snr)
        self.data['alignment']['method_results']['snr'] = snr_list
        self.data['alignment']['method_results']['snr_type'] = str(type(snr))
        self.data['alignment']['method_results']['snr_str'] = str(snr)
        self.data['alignment']['method_results']['snr_report'] = str(snr_report)
        self.data['alignment']['method_results']['snr_average'] = sum(snr_list) / len(snr_list)

        self.data['alignment']['method_results']['affine_matrix'] = afm.tolist()
        self.data['alignment']['method_results']['swim_pos'] = self.ingredients[-1].psta.tolist()
        self.data['alignment']['method_results']['datetime'] = time
        self.data['alignment']['method_results']['wht'] = self.wht
        self.data['alignment']['method_results']['swim-iterations'] = self.iters
        self.data['alignment']['method_results']['option'] = self.option
        self.data['alignment']['method_results']['current_method'] = self.cur_method
        self.data['alignment']['method_results']['ingredients'] = {}
        self.data['alignment']['method_results']['fn_reference']= self.fn_reference
        self.data['alignment']['method_results']['fn_transforming']= self.fn_transforming
        self.data['alignment']['method_results']['siz']= self.siz
        try:    self.data['alignment']['method_results']['memory_mb'] = self.megabytes()
        except: print_exception(self.destination)
        try:    self.data['alignment']['method_results']['memory_gb'] = self.gigabytes()
        except: print_exception(self.destination)

        if self.cur_method == 'grid-custom':
            self.data['alignment']['method_results']['grid_custom_regions'] = self.grid_custom_regions

        self.data.setdefault('alignment_history', {})
        self.data['alignment_history'].setdefault(self.cur_method, [])
        self.data['alignment_history'][self.cur_method] = self.data['alignment']['method_results']
        if self.dev_mode:
            self.data['alignment']['swim_args'] = {}
            self.data['alignment']['swim_out'] = {}
            self.data['alignment']['swim_err'] = {}
            self.data['alignment']['mir_toks'] = {}
            self.data['alignment']['mir_script'] = {}
            self.data['alignment']['mir_out'] = {}
            self.data['alignment']['mir_err'] = {}
            # self.data['alignment']['crop_str_mir'] = {}
            for i,ing in enumerate(self.ingredients):
                try: self.data['alignment']['method_results']['ingredient_%d' % i] = {}
                except: self.data['alignment']['method_results']['ingredient_%d' % i] = 'Null'
                try: self.data['alignment']['method_results']['ingredient_%d' % i]['ww'] = ing.ww
                except: self.data['alignment']['method_results']['ingredient_%d' % i]['ww'] = 'Null'
                try: self.data['alignment']['method_results']['ingredient_%d' % i]['psta'] = str(ing.psta)
                except: self.data['alignment']['method_results']['ingredient_%d' % i]['psta'] = 'Null'
                try: self.data['alignment']['method_results']['ingredient_%d' % i]['pmov'] = str(ing.pmov)
                except: self.data['alignment']['method_results']['ingredient_%d' % i]['pmov'] = 'Null'

                if self.cur_method in ('grid-default', 'grid-custom'):
                    try: self.data['alignment']['method_results']['ingredient_%d' % i]['afm'] = str(ing.afm)
                    except: self.data['alignment']['method_results']['ingredient_%d' % i]['afm'] = 'Null'
                    try: self.data['alignment']['method_results']['ingredient_%d' % i]['adjust_x'] = str(ing.adjust_x)
                    except: self.data['alignment']['method_results']['ingredient_%d' % i]['adjust_x'] = 'Null'
                    try: self.data['alignment']['method_results']['ingredient_%d' % i]['adjust_y'] = str(ing.adjust_y)
                    except: self.data['alignment']['method_results']['ingredient_%d' % i]['adjust_y'] = 'Null'

                if self.cur_method in ('grid-default', 'grid-custom', 'manual-hint'):
                    try: self.data['alignment']['mir_err']['ingredient_%d' % i] = ing.ww
                    except: self.data['alignment']['mir_err']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['swim_args']['ingredient_%d' % i] = ing.multi_swim_arg_str()
                    except: self.data['alignment']['swim_args']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['swim_out']['ingredient_%d' % i] = ing.swim_output
                    except: self.data['alignment']['swim_out']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['swim_err']['ingredient_%d' % i] = ing.swim_err_lines
                    except: self.data['alignment']['swim_err']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['mir_toks']['ingredient_%d' % i] = ing.mir_toks
                    except: self.data['alignment']['mir_toks']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['mir_script']['ingredient_%d' % i] = ing.mir_script
                    except: self.data['alignment']['mir_script']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['mir_out']['ingredient_%d' % i] = ing.mir_out_lines
                    except: self.data['alignment']['mir_out']['ingredient_%d' % i] = 'Null'
                    try: self.data['alignment']['mir_err']['ingredient_%d' % i] = ing.mir_err_lines
                    except: self.data['alignment']['mir_err']['ingredient_%d' % i] = 'Null'


        self.data['alignment_hash'] = dict_hash(self.data['alignment_history'][self.cur_method])

        return afm


    def add_ingredients(self, ingredients):
        for ingredient in ingredients:
            ingredient.recipe = self
            ingredient.alignment = self.data['alignment']
            self.ingredients.append(ingredient)


class align_ingredient:
    '''
    Universal class for alignment ingredients of recipes

    Ingredients come in 3 main types where the cur_method is determined by value of align_mode
    1)  If ingredient_mode is 'Manual-Hint' or 'Manual-Hint' then this is manual alignment
        We calculate the afm directly using psta and pmov as the matching points
    2)  If ingredient_mode is 'SWIM-Manual', then this is a SWIM to refine the alignment
        of a 'Manual-Hint' using manually specified windows
    3)  If align_mode is 'SWIM' then this is a swim window matching ingredient
        ww and psta specify the size and location of windows in im_sta
        and corresponding windows (pmov) are contructed from psta and projected onto im_mov
        from which image matching is performed to estimate or refine the afm.
        If psta contains only one point then the estimated afm will be a translation matrix
    4) If align_mode is 'check_align' then use swim to check the SNR achieved by the
        supplied afm matrix but do not refine the afm matrix
    '''
    def __init__(self, mode, ww=None, psta=None, pmov=None, afm=None, rota=None, ID='', last=False):
        self.recipe = None
        self.alignment = None
        self.mode = mode
        self.swim_drift = 0.0
        self.afm = afm
        self.ww = ww
        self.psta = psta
        self.pmov = pmov
        self.rota = rota
        # self.snr = 0.0
        self.snr = [0.0]
        self.snr_report = 'SNR: --'
        self.threshold = (3.5, 200, 200)
        self.mir_toks = {}
        self.ID = ID
        self.last = last


    def __str__(self):
        s = "ingredient:\n"
        s += "  mode: " + str(self.mode) + "\n"
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


    def execute_ingredient(self):
        # Returns an affine matrix
        if self.mode == 'MIR':
            self.afm = self.run_manual_mir()
        else:
            swim_output = self.run_swim()
            if swim_output == ['']:
                print(f"[{self.alignment['meta']['index']}] SWIM output is an empty string! - Returning...")
                self.snr = np.zeros(len(self.psta[0]))
                self.snr_report = snr_report(self.snr)
                return self.afm
            self.crop_match_signals()
            self.afm = self.ingest_swim_output(swim_output)
        return self.afm


    def get_swim_args(self):
        self.cx = int(self.recipe.siz[0] / 2.0)
        self.cy = int(self.recipe.siz[1] / 2.0)

        afm_arg = '%.6f %.6f %.6f %.6f' % (self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1])



        basename = os.path.basename(self.recipe.fn_transforming)
        filename, extension = os.path.splitext(basename)

        multi_arg_str = ArgString(sep='\n')

        self.ms_names = []

        for i in range(len(self.psta[0])):

            if self.recipe.cur_method == 'grid-custom':
                if self.ID != 'Grid1x1':
                    if not self.recipe.grid_custom_regions[i]:
                        continue

            # correlation signals argument (output path)
            b_arg = os.path.join( self.recipe.scale_dir, 'signals', '%s_%s_%d%s' %
                                  (filename, self.recipe.cur_method, i, extension))
            self.ms_names.append(b_arg)

            args = ArgString(sep=' ')
            # if type(self.ww) == float or type(self.ww) == int:
            #     args.append("ww_%s" % self.ww)
            # else:
            #     args.append("ww_%dx%d" % (self.ww[0], self.ww[1]))
            if type(self.ww) == float or type(self.ww) == int:
                args.append("%d" % self.ww)
            else:
                args.append("%dx%d" % (self.ww[0], self.ww[1]))
            # args.append("-v")
            # args.append('ww_' + self.swim_ww_arg)
            if self.alignment['swim_settings']['clobber_fixed_noise']:
                args.append('-f%d' % self.alignment['swim_settings']['clobber_fixed_noise_px'])
            # args.add_flag(flag='-i', arg=str(self.rcipe.iters))
            args.add_flag(flag='-i', arg=str(self.recipe.iters))
            args.add_flag(flag='-w', arg=str(self.recipe.wht))
            if self.recipe.cur_method in ('grid-default', 'grid-custom'):
                self.offx = int(self.psta[0][i] - self.cx)
                self.offy = int(self.psta[1][i] - self.cy)
                # self.offx = '%.6f' % (self.psta[0][i] - self.cx)
                # self.offy = '%.6f' % (self.psta[1][i] - self.cy)
                args.add_flag(flag='-x', arg=str(self.offx))
                args.add_flag(flag='-y', arg=str(self.offy))
            args.add_flag(flag='-b', arg=b_arg)
            if self.last:
                if self.alignment['karg']:
                    k_arg_name = '%s_%s_k_%d%s' % (filename, self.recipe.cur_method, i, extension)
                    k_arg_path = os.path.join(self.recipe.scale_dir, 'tmp', k_arg_name)
                    args.add_flag(flag='-k', arg=k_arg_path)
                if self.alignment['targ']:
                    t_arg_name = '%s_%s_t_%d%s' % (filename, self.recipe.cur_method, i, extension)
                    t_arg_path = os.path.join(self.recipe.scale_dir, 'tmp', t_arg_name)
                    args.add_flag(flag='-t', arg=t_arg_path)
            args.append(self.alignment['swim_settings']['extra_kwargs'])
            args.append(self.recipe.fn_reference)
            if self.recipe.cur_method in ('manual-hint'):
                args.append('%s %s' % (self.psta[0][i], self.psta[1][i]))
            else:
                args.append('%s %s' % (self.cx, self.cy))
            args.append(self.recipe.fn_transforming)
            if self.recipe.cur_method in ('manual-hint'):
                args.append('%s %s' % (self.pmov[0][i], self.pmov[1][i]))
            else:
                self.adjust_x = '%.6f' % (self.cx + self.afm[0, 2])
                self.adjust_y = '%.6f' % (self.cy + self.afm[1, 2])
                args.append('%s %s' % (self.adjust_x, self.adjust_y))
            r = self.recipe.initial_rotation
            if abs(r) > 0:
                args.append(convert_rotation(r))
            args.append(afm_arg)
            args.append(self.alignment['swim_settings']['extra_args'])
            multi_arg_str.append(args())

        return multi_arg_str




    def run_swim(self):
        SWIMlogger = logging.getLogger('SWIMlogger')

        self.multi_swim_arg_str = self.get_swim_args()
        SWIMlogger.critical(f'Multi-SWIM Argument String:\n{self.multi_swim_arg_str()}')

        if type(self.ww) == float or type(self.ww) == int:
            # args.append(str(int(self.ww)))
            arg = "%d" % self.ww
        else:
            # args.append(str(int(self.ww[0])) + "x" + str(int(self.ww[1])))
            arg = "%dx%d" % (self.ww[0], self.ww[1])
        # arg = "%sx%s" % tuple(self.ww)

        o = run_command(
            self.recipe.swim_c,
            # arg_list=[self.swim_ww_arg],
            arg_list=[arg],
            cmd_input=self.multi_swim_arg_str(),
            extra=f'Automatic SWIM Alignment ({self.ID})',
            scale=self.alignment['meta']['scale_val']
        )

        self.swim_output = o['out'].strip().split('\n')
        self.swim_err_lines = o['err'].strip().split('\n')

        SWIMlogger.critical(f"\nSWIM Out:\n{str(self.swim_output)}\n\n")
        SWIMlogger.critical(f"\nSWIM Err:\n{str(self.swim_err_lines)}\n\n")


        return self.swim_output


    def get_mir_args(self):
        pass

    def crop_match_signals(self):

        px_keep = 128
        if self.recipe.cur_method in ('grid-default', 'grid-custom'):
            w = str(int(self.ww[0] / 2.0))
            h = str(int(self.ww[1] / 2.0))
            x1 = str(int((self.ww[0] - px_keep) / 2.0))
            y1 = str(int((self.ww[1] - px_keep) / 2.0))
            x2 = str(int((.50 * self.ww[0]) + (px_keep / 2.0)))
            y2 = str(int((.50 * self.ww[1]) + (px_keep / 2.0)))
        else:
            w = h = str(int(self.ww))
            x1 = y1 = str(int((self.ww - px_keep) / 2.0))
            x2 = y2 = str(int((.50 * self.ww) + (px_keep / 2.0)))


        for name in self.ms_names:
            self.crop_str_args = [
                'B', w, h, '1',
                '\nZ',
                '\nF', name,
                '\n0', '0', x1, y1,
                f'\n{w}', '0', x2, y1,
                f'\n{w}', h, x2, y2,
                '\n0', h, x1, y2,
                '\nT',
                '\n0', '1', '2',
                '\n2', '3', '0',
                '\nW', name
            ]
            # self.crop_str_mir = f"""B {w} {h} 1\nZ\nF {name}\n0 0 {x1} {y1}\n{w} 0 {x2} {y1}\n{w} {h} {x2} {y2}\n0 {h} {x1} {y2}\nT\n0 1 2\n2 3 0\nW {name}"""
            self.crop_str_mir = ' '.join(self.crop_str_args)
            logger.critical(f'MIR crop string:\n{self.crop_str_mir}')
            try:
                o = run_command(self.recipe.mir_c,
                                arg_list=[],
                                cmd_input=self.crop_str_mir,
                                extra=f'MIR the Match Signals to crop ({self.ID})',
                                scale=self.alignment['meta']['scale_val'])
            except:
                print_exception()




    def ingest_swim_output(self, swim_output):


        if (len(swim_output) == 1) and (self.recipe.cur_method in ('default-grid', 'custom-grid')):
            toks = swim_output[0].replace('(', ' ').replace(')', ' ').strip().split()
            self.dx = float(toks[8])
            self.dy = float(toks[9])
            aim = copy.deepcopy(self.afm)
            aim[0, 2] += self.dx
            aim[1, 2] += self.dy
            self.afm = aim
            self.snr = np.array([])
            self.snr_report = snr_report(self.snr)
            return self.afm
        else:
            # loop over SWIM output to build the MIR script:
            self.mir_script = ""
            snr_list = []
            for i,l in enumerate(swim_output):
                toks = l.replace('(', ' ').replace(')', ' ').strip().split()
                logger.critical(f"SWIM output tokens, line {i}: {str(toks)}")
                '''
                example:
                toks (i):
                ['28.6102:', '/Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy4.tif', '256', '768', '/Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy5.tif', '246.664', '751.303', '1.00504', '-0.005244', '0.004421', '0.98697', '-0.808517', '-4.85767', '4.92449']
                type: <class 'list'>
                '''

                self.mir_toks[i] = str(toks)
                try:
                    mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                except:
                    print_exception(extra=f"Section #{self.alignment['meta']['index']}\n"
                                          f"mir toks are: {str(toks)}\n"
                                          f"swim_output: {swim_output}")
                self.mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
            self.mir_script += 'R\n'
            logger.critical(f"\n\nmir_toks:\n{mir_toks}\n\n")
            logger.critical(f"\n\nmir_script:\n{self.mir_script}\n\n")
            o = run_command(self.recipe.mir_c,
                            arg_list=[],
                            cmd_input=self.mir_script,
                            extra=f'MIR the SWIM offsets to get affine ({self.ID})',
                            scale=self.alignment['meta']['scale_val']
                            )
            self.mir_out_lines = o['out'].strip().split('\n')
            self.mir_err_lines = o['err'].strip().split('\n')

            aim = np.eye(2, 3, dtype=np.float32)

            for line in self.mir_out_lines:
                toks = line.strip().split()
                if (toks[0] == 'AI'):
                    aim[0, 0] = float(toks[1])
                    aim[0, 1] = float(toks[2])
                    aim[0, 2] = float(toks[3]) + self.swim_drift
                    aim[1, 0] = float(toks[4])
                    aim[1, 1] = float(toks[5])
                    aim[1, 2] = float(toks[6]) + self.swim_drift

            self.afm = aim
            self.snr = np.array(snr_list)
            self.snr_report = snr_report(self.snr)
            return self.afm


    def run_manual_mir(self):
        MAlogger = logging.getLogger('MAlogger')

        mir_script_mp = ''
        for i in range(len(self.psta[0])):
            mir_script_mp += f'{self.psta[0][i]} {self.psta[1][i]} {self.pmov[0][i]} {self.pmov[1][i]}\n'
        mir_script_mp += 'R'
        self.mir_script = mir_script_mp

        o = run_command(
            self.recipe.mir_c,
            arg_list=[],
            cmd_input=mir_script_mp,
            extra='MIR to get affine using manual correspondence points',
            scale=self.alignment['meta']['scale_val']
        )
        mir_mp_out_lines = o['out'].strip().split('\n')
        mir_mp_err_lines = o['err'].strip().split('\n')
        MAlogger.critical(f'\n==========\n'
                          f'MIR script:\n{mir_script_mp}\n'
                          f'manual mir Out:\n{mir_mp_out_lines}\n\n'
                          f'manual mir Err:\n{mir_mp_err_lines}\n'
                          f'==========')
        afm = np.eye(2, 3, dtype=np.float32)
        self.mir_out_lines = mir_mp_out_lines
        for line in mir_mp_out_lines:
            MAlogger.info("Line: " + str(line))
            toks = line.strip().split()
            if (toks[0] == 'AI'):
                afm[0, 0] = float(toks[1])
                afm[0, 1] = float(toks[2])
                afm[0, 2] = float(toks[3])
                afm[1, 0] = float(toks[4])
                afm[1, 1] = float(toks[5])
                afm[1, 2] = float(toks[6])

        self.afm = afm
        self.snr = np.zeros(len(self.psta[0]))
        self.snr_report = snr_report(self.snr)
        return self.afm


def run_command(cmd, arg_list=None, cmd_input=None, extra='', scale=''):
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    nl = '\n'
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    RMlogger = logging.getLogger('recipemaker')
    RMlogger.critical(f"\n========== Run Command [PID: {cmd_proc.pid}] ==========\n"
                      f"Scale           : {scale}\n"
                      f"Description     : {extra}\n"
                      f"arg_list        : {arg_list}\n"
                      f"Running command :\n{(cmd_arg_list, 'None')[cmd_arg_list == '']}\n"
                      f"Passing data    :\n{(cmd_input, 'None')[cmd_input == '']}\n\n"
                      f">> stdout\n{(cmd_stdout, 'None')[cmd_stdout == '']}\n"
                      f">> stderr\n{(cmd_stderr, 'None')[cmd_stderr == '']}\n"
                      )
    return ({'out': cmd_stdout, 'err': cmd_stderr})


class SWIMparser:
    def __init__(self, sep):
        self.args = []
        self.sep = sep

    def add_flag(self, flag, arg=''):
        self.args.append(' '.join([flag, arg]).strip())

    def append(self, text):
        self.args.append('%s' % str(text))

    def __repr__(self):
        return self.sep.join(self.args).strip()

    def __call__(self):
        return repr(self)



class ArgString:
    def __init__(self, sep):
        self.args = []
        self.sep = sep

    def add_flag(self, flag, arg=''):
        self.args.append(' '.join([flag, arg]).strip())

    def append(self, text):
        self.args.append('%s' % str(text))

    def __repr__(self):
        return self.sep.join(self.args).strip()

    def __call__(self):
        return repr(self)


def prefix_lines(i, s):
    return ('\n'.join([i + ss.rstrip() for ss in s.split('\n') if len(ss) > 0]) + "\n")

def snr_report(arr) -> str:
    return 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (arr.mean(), arr.std(), len(arr), arr.min(), arr.max())

def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)

def convert_rotation(degrees):
    deg2rad = 2*np.pi/360.
    return np.sin(deg2rad*degrees)

def print_exception(dest=None, extra='None'):
    tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}]\nError Type : {exi[0]}\nError Value : {exi[1]}\n{traceback.format_exc()}\nAdditional Details: {extra}"
    print(txt)
    lf = os.path.join(dest, 'logs', 'exceptions.log')
    with open(lf, 'a+') as f:
        f.write('\n' + txt)

def dict_hash(dictionary: Dict[str, Any]) -> str:
    """
    MD5 hash of a dictionary.
    source: https://www.doc.ic.ac.uk/~nuric/coding/how-to-hash-a-dictionary-in-python.html
    """
    dhash = hashlib.md5()
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.hexdigest()


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.info("Running " + __file__ + ".__main__()")

    f_self = sys.argv[0]
    data = json.loads(sys.argv[1])
    result = run_recipe(data=data)
    print("---JSON-DELIMITER---")
    print(json.JSONEncoder(indent=1, separators=(",", ": "), sort_keys=True).encode(result))
    print("---JSON-DELIMITER---")
    sys.stdout.close()
    sys.stderr.close()


'''
SWIM output (example)

>> stdout
12.4662: /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy2.tif 256 256 /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy3.tif 261.361 241.863  1 0 0 1 (5.36096 -14.1372 15.1195)
10.1774: /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy2.tif 768 256 /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy3.tif 782.292 235.2  1 0 0 1 (14.2921 -20.8 25.2369)
16.512: /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy2.tif 256 768 /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy3.tif 255.506 767.735  1 0 0 1 (-0.493896 -0.264648 0.560333)
12.5832: /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy2.tif 768 768 /Users/joelyancey/glanceem_swift/test_projects/test5/scale_4/img_src/dummy3.tif 773.354 780.944  1 0 0 1 (5.35358 12.9438 14.0073)

>> stderr
None



'''