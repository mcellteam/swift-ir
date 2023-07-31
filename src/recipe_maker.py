#!/usr/bin/env python3

import os
import re
import sys
import time
import copy
import logging
import platform
import datetime
import traceback
import numpy as np
import subprocess as sp
from typing import Dict, Any
import hashlib
import json
import psutil

__all__ = ['run_recipe']

logger = logging.getLogger(__name__)

def run_recipe(data):
    '''Assemble and execute an alignment recipe
    :param data: data for one pairwise alignment as Python dictionary.'''
    recipe = align_recipe(data=data,)
    recipe.assemble_recipe()
    recipe.execute_recipe()
    data = recipe.set_results()
    return data

class align_recipe:

    def __init__(self, data):
        self.data = data
        self.meta = self.data['meta']
        self.defaults = self.meta['defaults']
        self.configure_logging()
        self.method = self.meta['method']
        self.index = self.meta['index']
        self.siz = self.meta['image_src_size']
        if self.method == 'grid-default':
            self.wht = self.defaults['signal-whitening']
            self.iters = self.defaults['swim-iterations']
        else:
            self.wht = self.data['swim_settings']['signal-whitening']
            self.iters = self.data['swim_settings']['iterations']
        if self.meta['isRefinement']:
            self.iters = 3
        self.grid_regions  = self.data['swim_settings']['grid-custom-regions']
        self.ingredients = []
        self.initial_rotation = float(self.defaults['initial-rotation'])
        # self.afm = np.array([[1., 0., 0.], [0., 1., 0.]])
        # Configure platform-specific path to executables for C SWiFT-IR
        slug = (('linux', 'darwin')[platform.system() == 'Darwin'], 'tacc')[
            'tacc.utexas' in platform.node()]
        self.swim_c = f'{os.path.split(os.path.realpath(__file__))[0]}' \
                      f'/lib/bin_{slug}/swim'
        self.mir_c = f'{os.path.split(os.path.realpath(__file__))[0]}' \
                     f'/lib/bin_{slug}/mir'


    def configure_logging(self):
        logger = logging.getLogger(__name__)
        MAlogger = logging.getLogger('MAlogger')
        RMlogger = logging.getLogger('recipemaker')
        Exceptlogger = logging.getLogger('exceptlogger')
        Exceptlogger.addHandler(
            logging.FileHandler(os.path.join(self.meta['destination_path'],
                                             'logs', 'exceptions.log')))
        if self.meta['recipe_logging']:
            MAlogger.addHandler(logging.FileHandler(os.path.join(
                self.meta['destination_path'], 'logs', 'manual_align.log')))
            RMlogger.addHandler(logging.FileHandler(os.path.join(
                self.meta['destination_path'], 'logs', 'recipemaker.log')))
        else:
            MAlogger.disabled = True
            RMlogger.disabled = True
            logger.disabled = True


    def megabytes(self):
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2


    def gigabytes(self):
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 3


    def assemble_recipe(self):

        # Set up 1x1 point and window
        pa = np.zeros((2, 1))  # Point Array for one point
        pa[0, 0] = int(self.siz[0] / 2.0)  # Window Center in x
        pa[1, 0] = int(self.siz[1] / 2.0)  # Window Center in y
        psta_1 = pa

        # Example: psta_2x2 = [[256. 768. 256. 768.] [256. 256. 768. 768.]]

        if self.method == 'grid-default':
            nx, ny = 2, 2
            pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
            sx = int(self.siz[0] / 2.0)  # Initial Size of each window
            sy = int(self.siz[1] / 2.0)  # Initial Size of each window
            for x in range(nx):
                for y in range(ny):
                    pa[0, x + nx * y] = int(0.5 * sx + sx * x)  # Pt Array 2x4
                    pa[1, x + nx * y] = int(0.5 * sy + sy * y)  # Pt Array 2x4
            psta_2x2 = pa
            ww_1x1 = self.defaults[self.meta['scale_key']]['swim-window-px']
            ww_2x2 = [int(ww_1x1[0]/2), int(ww_1x1[1]/2)]

            if self.meta['isRefinement']:
                '''Perform affine refinement'''
                # if self.meta['scale_key'] == 'scale_1':
                #     self.add_ingredients([
                #         align_ingredient(
                #             mode='SWIM-Grid',
                #             ww=ww_2x2,
                #             psta=psta_2x2,
                #             ID='g2x2-b',
                #             last=True)])
                # else:
                self.add_ingredients([
                    align_ingredient(
                        mode='SWIM-Grid',
                        ww=ww_2x2,
                        psta=psta_2x2,
                        ID='g2x2-a'),
                    align_ingredient(
                        mode='SWIM-Grid',
                        ww=ww_2x2,
                        psta=psta_2x2,
                        ID='g2x2-b',
                        last=True)])
            else:
                '''Perform affine initialization'''
                self.add_ingredients([
                    align_ingredient(
                        mode='SWIM-Grid',
                        ww=ww_1x1,
                        psta=psta_1,
                        ID='g1x1'),
                    align_ingredient(
                        mode='SWIM-Grid',
                        ww=ww_2x2,
                        psta=psta_2x2,
                        ID='g2x2-a'),
                    align_ingredient(
                        mode='SWIM-Grid',
                        ww=ww_2x2,
                        psta=psta_2x2,
                        ID='g2x2-c'),
                    align_ingredient(
                        mode='SWIM-Grid',
                        ww=ww_2x2,
                        psta=psta_2x2,
                        ID='g2x2-d',
                        last=True)])
        elif self.method == 'grid-custom':
            ww_1x1 = self.data['grid_custom_px_1x1']
            ww_2x2 = self.data['grid_custom_px_2x2']
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
                align_ingredient(
                    mode='SWIM-Grid',
                    ww=ww_1x1,
                    psta=psta_1,
                    ID='g1x1'),
                align_ingredient(
                    mode='SWIM-Grid',
                    ww=ww_2x2,
                    psta=psta_2x2,
                    ID='g2x2-a'),
                align_ingredient(
                    mode='SWIM-Grid',
                    ww=ww_2x2,
                    psta=psta_2x2,
                    ID='g2x2-c'),
                align_ingredient(
                    mode='SWIM-Grid',
                    ww=ww_2x2,
                    psta=psta_2x2,
                    ID='g2x2-d',
                    last=True),
            ])
        else:
            ww = self.data['manual_swim_window_px']
            man_pmov = np.array(self.data['manpoints_mir']['base']).transpose()
            man_psta = np.array(self.data['manpoints_mir']['ref']).transpose()
            if self.method == 'manual-hint':
                self.add_ingredients([
                    align_ingredient(
                        mode='MIR',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov),
                    align_ingredient(
                        mode='SWIM-Manual',
                        ww=[ww,ww], psta=man_psta,
                        pmov=man_pmov,
                        ID='Manual-a'),
                    align_ingredient(
                        mode='SWIM-Manual',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov,
                        ID='Manual-b',
                        last=True)])
            elif self.method == 'manual-strict':
                self.add_ingredients([
                    align_ingredient(
                        mode='MIR',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov,
                        last=True)])


    def execute_recipe(self):

        self.afm = np.array(self.meta['init_afm'])

        if (self.meta['fn_reference'] == self.meta['fn_transforming']) \
                or (self.meta['fn_reference'] == ''):
            print_exception(extra=f'Image Has No Reference!')
            return

        for i, ingredient in enumerate(self.ingredients):
            try:
                ingredient.afm = self.afm
                self.afm = ingredient.execute_ingredient()
            except:
                print_exception(extra=f'ERROR ing{i}/{len(self.ingredients)}')


    def set_results(self):

        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        afm = np.array([[1., 0., 0.], [0., 1., 0.]])
        snr = np.array([0.0])
        snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
            snr.mean(), snr.std(), len(snr), snr.min(), snr.max())

        # afm = self.ingredients[-1].afm
        # snr = self.ingredients[-1].snr
        # snr_report = self.ingredients[-1].snr_report
        # snr_list = snr.tolist()
        try:
            afm = self.ingredients[-1].afm
            snr = self.ingredients[-1].snr
            snr_report = self.ingredients[-1].snr_report
        except:
            print_exception()

        try:
            snr_list = snr.tolist()
        except:
            snr_list = list(snr)
        mr = self.data['method_results']
        mr['snr'] = snr_list
        mr['snr_report'] = str(snr_report)
        mr['snr_average'] = sum(snr_list) / len(snr_list)
        mr['affine_matrix'] = afm.tolist()
        mr['afm'] = afm.tolist()
        mr['init_afm'] = self.meta['init_afm']
        mr['swim_pos'] = self.ingredients[-1].psta.tolist()
        mr['datetime'] = time
        mr['wht'] = self.wht
        mr['swim-iterations'] = self.iters
        mr['method'] = self.method
        mr['siz']= self.siz
        mr['memory_mb'] = self.megabytes()
        mr['memory_gb'] = self.gigabytes()

        if self.method == 'grid-custom':
            mr['grid_regions'] = self.grid_regions

        mr['swim_args'] = {} #Temporary
        for i,ing in enumerate(self.ingredients):
            try: mr['swim_args']['ing%d' % i] = ing.multi_swim_arg_str()
            except: mr['swim_args']['ing%d' % i] = 'Null'

        for i, ing in enumerate(self.ingredients):
            mr['ing%d' % i] = {}
            try: mr['ing%d' % i]['ww'] = ing.ww
            except: mr['ing%d' % i]['ww'] = 'Null'
            try: mr['ing%d' % i]['psta'] = ing.psta.tolist()
            except: mr['ing%d' % i]['psta'] = 'Null'
            try: mr['ing%d' % i]['pmov'] = ing.pmov.tolist()
            except: mr['ing%d' % i]['pmov'] = 'Null'
            try: mr['ing%d' % i]['adjust_x'] = ing.adjust_x
            except: mr['ing%d' % i]['adjust_x'] = 'Null'
            try: mr['ing%d' % i]['adjust_y'] = ing.adjust_y
            except: mr['ing%d' % i]['adjust_y'] = 'Null'
            try: mr['ing%d' % i]['afm'] = ing.afm.tolist()
            except: mr['ing%d' % i]['afm'] = 'Null'
            try: mr['ing%d' % i]['t_swim'] = ing.t_swim
            except: mr['ing%d' % i]['t_swim'] = 'Null'
            try: mr['ing%d' % i]['t_mir'] = ing.t_mir
            except: mr['ing%d' % i]['t_mir'] = 'Null'

        if self.meta['dev_mode']:
            mr['swim_args'] = {}
            mr['swim_out'] = {}
            mr['swim_err'] = {}
            mr['mir_toks'] = {}
            mr['mir_script'] = {}
            mr['mir_out'] = {}
            mr['mir_err'] = {}
            for i,ing in enumerate(self.ingredients):
                # try: mr['swim_args']['ing%d' % i] = ing.multi_swim_arg_str()
                # except: mr['swim_args']['ing%d' % i] = 'Null'
                try: mr['swim_out']['ing%d' % i] = ing.swim_output
                except: mr['swim_out']['ing%d' % i] = 'Null'
                try: mr['swim_err']['ing%d' % i] = ing.swim_err_lines
                except: mr['swim_err']['ing%d' % i] = 'Null'
                try: mr['mir_toks']['ing%d' % i] = ing.mir_toks
                except: mr['mir_toks']['ing%d' % i] = 'Null'
                try: mr['mir_script']['ing%d' % i] = ing.mir_script
                except: mr['mir_script']['ing%d' % i] = 'Null'
                try: mr['mir_out']['ing%d' % i] = ing.mir_out_lines
                except: mr['mir_out']['ing%d' % i] = 'Null'
                try: mr['mir_err']['ing%d' % i] = ing.mir_err_lines
                except: mr['mir_err']['ing%d' % i] = 'Null'

        return self.data

    def add_ingredients(self, ingredients):
        for ingredient in ingredients:
            ingredient.recipe = self
            self.ingredients.append(ingredient)


class align_ingredient:
    '''
    Universal class for alignment ingredients of recipes
    1)  If ingredient_mode is 'Manual-' then calculate the afm directly using
        psta and pmov as the matching regions or points.
    2)  If ingredient mode is 'SWIM-Manual', then this is a SWIM to refine the
        alignment of a 'Manual-Hint' using manually specified windows.
    3)  If mode is 'SWIM' then perform a SWIM region matching ingredient using
        ww and psta specify the size and location of windows in im_sta.
        Corresponding windows (pmov) are contructed from psta and projected
        onto im_mov. Then perform matching to initialize or refine the afm.
        If psta contains only one point then return a translation matrix.
    TODO:
    4) If align_mode is 'check_align' then use swim to check the SNR achieved
        by the supplied afm matrix but do not refine the afm matrix
    '''
    def __init__(self, mode, ww=None, psta=None, pmov=None, afm=None, rota=None,
                 ID='', last=False):
        self.recipe = None
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
            self.flags = toks[11:]  # flags will be str or list of strs


    def execute_ingredient(self):
        # Returns an affine matrix
        if self.mode == 'MIR':
            self.afm = self.run_manual_mir()
        else:
            swim_output = self.run_swim()
            if swim_output == ['']:
                print(f"[{self.recipe.index}] SWIM Out is empty string!\n"
                      f"Err:\n{self.swim_err_lines}")
                self.snr = np.zeros(len(self.psta[0]))
                self.snr_report = snr_report(self.snr)
                return self.afm
            self.crop_match_signals()
            self.afm = self.ingest_swim_output(swim_output)
        return self.afm


    def get_swim_args(self):
        self.cx = int(self.recipe.siz[0] / 2.0)
        self.cy = int(self.recipe.siz[1] / 2.0)
        basename = os.path.basename(self.recipe.meta['fn_transforming'])
        fn, extension = os.path.splitext(basename)
        multi_arg_str = ArgString(sep='\n')
        dir_scale = os.path.join(
            self.recipe.meta['destination_path'], self.recipe.meta['scale_key'])
        self.ms_names = []
        for i in range(len(self.psta[0])):
            if self.recipe.method == 'grid-custom':
                if self.ID != 'g1x1':
                    if not self.recipe.grid_regions[i]:
                        continue
            # correlation signals argument (output path)
            b_arg = os.path.join(dir_scale, 'signals', '%s_%s_%d%s' %
                           (fn, self.recipe.method, i, extension))
            self.ms_names.append(b_arg)
            args = ArgString(sep=' ')
            args.append("%dx%d" % (self.ww[0], self.ww[1]))
            if self.recipe.data['meta']['verbose_swim']:
                args.append("-v")
            if self.recipe.data['swim_settings']['clobber_fixed_noise']:
                args.append(
                    '-f%d' % self.recipe.data['swim_settings']
                    ['clobber_fixed_noise_px'])
            args.add_flag(flag='-i', arg=str(self.recipe.iters))
            args.add_flag(flag='-w', arg=str(self.recipe.wht))
            if self.recipe.method in ('grid-default', 'grid-custom'):
                self.offx = int(self.psta[0][i] - self.cx)
                self.offy = int(self.psta[1][i] - self.cy)
                args.add_flag(flag='-x', arg='%d' % self.offx)
                args.add_flag(flag='-y', arg='%d' % self.offy)
            args.add_flag(flag='-b', arg=b_arg)
            if self.last:
                if self.recipe.data['karg']:
                    k_arg_name = '%s_%s_k_%d%s' % (fn, self.recipe.method, i,
                                                   extension)
                    k_arg_path = os.path.join(dir_scale, 'tmp', k_arg_name)
                    args.add_flag(flag='-k', arg=k_arg_path)
                if self.recipe.data['targ']:
                    t_arg_name = '%s_%s_t_%d%s' % (fn, self.recipe.method, i,
                                                   extension)
                    t_arg_path = os.path.join(dir_scale, 'tmp', t_arg_name)
                    args.add_flag(flag='-t', arg=t_arg_path)
            args.append(self.recipe.data['swim_settings']['extra_kwargs'])
            args.append(self.recipe.meta['fn_reference'])
            if self.recipe.method in ('manual-hint'):
                args.append('%s %s' % (self.psta[0][i], self.psta[1][i]))
            else:
                args.append('%s %s' % (self.cx, self.cy))
            args.append(self.recipe.meta['fn_transforming'])
            if self.recipe.method in ('manual-hint'):
                args.append('%s %s' % (self.pmov[0][i], self.pmov[1][i]))
            else:
                self.adjust_x = '%.6f' % (self.cx + self.afm[0, 2])
                self.adjust_y = '%.6f' % (self.cy + self.afm[1, 2])
                args.append('%s %s' % (self.adjust_x, self.adjust_y))
            r = self.recipe.initial_rotation
            if abs(r) > 0:
                args.append(convert_rotation(r))
            args.append('%.6f %.6f %.6f %.6f' % (
                self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1]))
            args.append(self.recipe.data['swim_settings']['extra_args'])
            multi_arg_str.append(args())
        return multi_arg_str


    def run_swim(self):
        self.multi_swim_arg_str = self.get_swim_args()
        logging.getLogger('recipemaker').critical(
            f'Multi-SWIM Argument String:\n{self.multi_swim_arg_str()}')
        arg = "%dx%d" % (self.ww[0], self.ww[1])
        t0 = time.time()
        out, err = run_command(
            self.recipe.swim_c,
            arg_list=[arg],
            cmd_input=self.multi_swim_arg_str(),
            desc=f'SWIM alignment'
        )
        self.t_swim = time.time() - t0
        self.swim_output = out.strip().split('\n')
        self.swim_err_lines = err.strip().split('\n')
        return self.swim_output


    def crop_match_signals(self):

        px_keep = 128
        if self.recipe.method in ('grid-default', 'grid-custom'):
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
                '\n%s'%w, '0', x2, y1,
                '\n%s'%w, h, x2, y2,
                '\n0', h, x1, y2,
                '\nT',
                '\n0', '1', '2',
                '\n2', '3', '0',
                '\nW', name
            ]
            self.crop_str_mir = ' '.join(self.crop_str_args)
            logger.critical(f'MIR crop string:\n{self.crop_str_mir}')
            _, _ = run_command(
                self.recipe.mir_c,
                cmd_input=self.crop_str_mir,
                desc=f'Crop match signals'
            )


    def ingest_swim_output(self, swim_output):

        if (len(swim_output) == 1) and \
                (self.recipe.method in ('default-grid', 'custom-grid')):
            toks = swim_output[0].replace(
                '(', ' ').replace(')', ' ').strip().split()
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
                self.mir_toks[i] = str(toks)
                try:
                    mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                except:
                    print_exception(
                        extra=f"#{self.recipe.data['meta']['index']}\n"
                              f"mir toks are: {str(toks)}\n"
                              f"swim_output: {swim_output}"
                    )
                self.mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
            self.mir_script += 'R\n'
            t0 = time.time()
            out, err = run_command(
                self.recipe.mir_c,
                cmd_input=self.mir_script,
                desc=f'MIR compose affine',
            )
            self.t_mir = time.time() - t0
            self.mir_out_lines = out.strip().split('\n')
            self.mir_err_lines = err.strip().split('\n')
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
        mir_script_mp = ''
        for i in range(len(self.psta[0])):
            mir_script_mp += f'{self.psta[0][i]} {self.psta[1][i]} ' \
                             f'{self.pmov[0][i]} {self.pmov[1][i]}\n'
        mir_script_mp += 'R'
        self.mir_script = mir_script_mp
        out, err = run_command(self.recipe.mir_c, cmd_input=mir_script_mp,
            desc='MIR to compose affine (strict manual)',)
        mir_mp_out_lines = out.strip().split('\n')
        mir_mp_err_lines = err.strip().split('\n')
        logging.getLogger('MAlogger').critical(
            f'\n==========\nMIR script:\n{mir_script_mp}\n'
            f'stdout >>\n{mir_mp_out_lines}\n'
            f'stderr >>\n{mir_mp_err_lines}')
        afm = np.eye(2, 3, dtype=np.float32)
        self.mir_out_lines = mir_mp_out_lines
        for line in mir_mp_out_lines:
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


def run_command(cmd, arg_list=(), cmd_input=None, desc=''):
    cmd_arg_list = [cmd]
    cmd_arg_list.extend(arg_list)
    # Note: decode bytes if universal_newlines False
    with sp.Popen(
        cmd_arg_list,
        stdin=sp.PIPE,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        universal_newlines=True,
        env=os.environ.copy()) as cmd_proc:
        cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    logging.getLogger('recipemaker').critical(
        f"\n======== Run Command [PID: {cmd_proc.pid}] ========\n"
        f"Description     : {desc}\n"
        f"Running command : {cmd_arg_list}\n"
        f"Passing data    : {cmd_input}\n\n"
        f">> stdout\n{cmd_stdout}\n>> stderr\n{cmd_stderr}\n"
    )
    # time.sleep(.01)
    return cmd_stdout, cmd_stderr


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
    return ('\n'.join([i + ss.rstrip() for ss
                       in s.split('\n') if len(ss) > 0]) + "\n")


def snr_report(arr) -> str:
    return 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
        arr.mean(), arr.std(), len(arr), arr.min(), arr.max())


def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def convert_rotation(degrees):
    deg2rad = 2*np.pi/360.
    return np.sin(deg2rad*degrees)


def print_exception(extra='None'):
    tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}] {exi[0]}\nError Value : {exi[1]}\n" \
          f"{traceback.format_exc()}\nAdditional Details: {extra}"
    logging.getLogger('exceptlogger').warning(txt)


def dict_hash(dictionary: Dict[str, Any]) -> str:
    """Returns an MD5 hash of a Python dictionary. source:
    www.doc.ic.ac.uk/~nuric/coding/how-to-hash-a-dictionary-in-python.html"""
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
    print(json.JSONEncoder(indent=1, separators=(",", ": "),
                           sort_keys=True).encode(result))
    print("---JSON-DELIMITER---")
    sys.stdout.close()
    sys.stderr.close()