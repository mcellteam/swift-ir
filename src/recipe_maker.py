#!/usr/bin/env python3

import os
import re
import sys
import time
import copy
import glob
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
# import shutil
# from src.funcs_image import ImageSize
# import src.config as cfg

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
        # self.ss = self.data['ss']
        self.ss = self.data['swim_settings']
        self.configure_logging()
        self.method = self.ss['method']
        self.index = self.ss['index']
        self.grid_regions  = self.ss['grid']['quadrants']
        self.ingredients = []
        self.initial_rotation = float(self.ss['initial_rotation'])
        # self.afm = np.array([[1., 0., 0.], [0., 1., 0.]])
        # Configure platform-specific path to executables for C SWiFT-IR
        slug = (('linux', 'darwin')[platform.system() == 'Darwin'], 'tacc')[
            'tacc.utexas' in platform.node()]
        p = os.path.split(os.path.realpath(__file__))[0]
        self.swim_c = '%s/lib/bin_%s/swim' % (p, slug)
        self.mir_c = '%s/lib/bin_%s/mir' % (p, slug)
        self.iscale2_c = '%s/lib/bin_%s/iscale2' % (p, slug)
        self.signals_dir = os.path.join(self.ss['location'], 'signals', self.ss['level'])
        self.matches_dir = os.path.join(self.ss['location'], 'matches', self.ss['level'])
        self.tmp_dir = os.path.join(self.ss['location'], 'tmp', self.ss['level'])


    def configure_logging(self):
        logger = logging.getLogger(__name__)
        MAlogger = logging.getLogger('MAlogger')
        RMlogger = logging.getLogger('recipemaker')
        Exceptlogger = logging.getLogger('exceptlogger')
        tnLogger = logging.getLogger('tnLogger')
        tnLogger = logging.getLogger('tnLogger')

        if self.ss['log_recipe_to_file']:
            Exceptlogger.addHandler(logging.FileHandler(os.path.join(self.ss['location'],
                                             'logs', 'exceptions.log')))

            MAlogger.addHandler(logging.FileHandler(os.path.join(
                self.ss['location'], 'logs', 'manual_align.log')))
            RMlogger.addHandler(logging.FileHandler(os.path.join(
                self.ss['location'], 'logs', 'recipemaker.log')))
            tnLogger.addHandler(logging.FileHandler(os.path.join(
                self.ss['location'], 'logs', 'thumbnails.log')))
        else:
            MAlogger.disabled = True
            RMlogger.disabled = True
            logger.disabled = True
            tnLogger.disabled = True


    def megabytes(self):
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2


    def gigabytes(self):
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 3


    def assemble_recipe(self):

        # Set up 1x1 point and window
        pa = np.zeros((2, 1))  # Point Array for one point
        pa[0, 0] = int(self.ss['img_size'][0] / 2.0)  # Window Center x
        pa[1, 0] = int(self.ss['img_size'][1] / 2.0)  # Window Center y
        psta_1 = pa

        # Example: psta_2x2 = [[256. 768. 256. 768.] [256. 256. 768. 768.]]

        # if self.method == 'grid_default':
        # if 'grid' in self.method:
        #     nx, ny = 2, 2
        #     pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
        #     sx = int(self.ss['img_size'][0] / 2.0) #init window size
        #     sy = int(self.ss['img_size'][1] / 2.0)
        #     for x in range(nx):
        #         for y in range(ny):
        #             pa[0, x + nx * y] = int(0.5 * sx + sx * x)  # Pt Array 2x4
        #             pa[1, x + nx * y] = int(0.5 * sy + sy * y)  # Pt Array 2x4
        #     psta_2x2 = pa
        #     ww_1x1 = self.ss['grid']['size_1x1']
        #     # ww_2x2 = [int(ww_1x1[0]/2), int(ww_1x1[1]/2)]
        #     ww_2x2 = self.ss['grid']['size_1x1']
        #
        #     if self.ss['isRefinement']:
        #         '''Perform affine refinement'''
        #         # if self.ss['level'] == 'scale_1':
        #         #     self.add_ingredients([
        #         #         align_ingredient(
        #         #             mode='SWIM-Grid',
        #         #             ww=ww_2x2,
        #         #             psta=psta_2x2,
        #         #             ID='g2x2',
        #         #             last=True)])
        #         # else:
        #         self.add_ingredients([
        #             align_ingredient(
        #                 mode='SWIM-Grid',
        #                 ww=ww_2x2,
        #                 psta=psta_2x2,
        #                 ID='g2x2-a'),
        #             align_ingredient(
        #                 mode='SWIM-Grid',
        #                 ww=ww_2x2,
        #                 psta=psta_2x2,
        #                 ID='g2x2-b',
        #                 last=True)])
        #     else:
        #         '''Perform affine initialization'''
        #         self.add_ingredients([
        #             align_ingredient(
        #                 mode='SWIM-Grid',
        #                 ww=ww_1x1,
        #                 psta=psta_1,
        #                 ID='g1x1'),
        #             align_ingredient(
        #                 mode='SWIM-Grid',
        #                 ww=ww_2x2,
        #                 psta=psta_2x2,
        #                 ID='g2x2-a'),
        #             align_ingredient(
        #                 mode='SWIM-Grid',
        #                 ww=ww_2x2,
        #                 psta=psta_2x2,
        #                 ID='g2x2-c'),
        #             align_ingredient(
        #                 mode='SWIM-Grid',
        #                 ww=ww_2x2,
        #                 psta=psta_2x2,
        #                 ID='g2x2-d',
        #                 last=True)])
        if 'grid' in self.method:
        # elif self.method == 'grid_custom':
            ww_1x1 = self.data['swim_settings']['grid']['size_1x1']
            ww_2x2 = self.data['swim_settings']['grid']['size_2x2']
            x1 = ((self.ss['img_size'][0] - ww_1x1[0]) / 2) + (ww_2x2[0] / 2)
            x2 = self.ss['img_size'][0] - x1
            y1 = ((self.ss['img_size'][1] - ww_1x1[1]) / 2) + (ww_2x2[1] / 2)
            y2 = self.ss['img_size'][1] - y1
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
            ww = self.ss['manual']['size_region']
            #sanitize lists of None elements
            # pts = self.ss['match_points_mir']['base']
            pts = self.ss['manual']['points']['mir_coords']['tra']
            man_pmov = np.array([p for p in pts if p]).transpose()
            pts = self.ss['manual']['points']['mir_coords']['ref']
            man_psta = np.array([p for p in pts if p]).transpose()
            self.clr_indexes = [i for i,p in enumerate(pts) if p]
            if self.method == 'manual_hint':
                self.add_ingredients([
                    align_ingredient(
                        mode='MIR',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov),
                    align_ingredient(
                        mode='SWIM-Manual',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov,
                        ID='Manual-a'),
                    align_ingredient(
                        mode='SWIM-Manual',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov,
                        ID='Manual-b',
                        last=True)])
            elif self.method == 'manual_strict':
                self.add_ingredients([
                    align_ingredient(
                        mode='MIR',
                        ww=[ww,ww],
                        psta=man_psta,
                        pmov=man_pmov,
                        last=True)])


    def execute_recipe(self):

        if not os.path.exists(self.signals_dir):
            os.mkdir(self.signals_dir)
        if not os.path.exists(self.matches_dir):
            os.mkdir(self.matches_dir)
        if not os.path.exists(self.tmp_dir):
            os.mkdir(self.tmp_dir)

        self.afm = np.array(self.ss['init_afm'])

        if (self.ss['reference'] == self.ss['path']) \
                or (self.ss['reference'] == ''):
            print_exception(extra=f'Image #{self.index} Has No Reference!')
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
        try:
            mr['affine_matrix'] = afm.tolist()
        except:
            print_exception(f"\nindex = {self.index}\ntype(afm) = {afm}\nafm={afm}")
        mr['init_afm'] = self.ss['init_afm']
        mr['swim_pos'] = self.ingredients[-1].psta.tolist()
        mr['datetime'] = time
        # mr['whiten'] = self.ss['whiten']
        # mr['swim_iters'] = self.ss['swim_iters']
        mr['method'] = self.method
        mr['memory_mb'] = self.megabytes()
        mr['memory_gb'] = self.gigabytes()

        if self.method == 'grid_custom':
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

        if self.ss['dev_mode']:
            mr['swim_args'] = {}
            mr['swim_out'] = {}
            mr['swim_err'] = {}
            mr['mir_toks'] = {}
            mr['mir_script'] = {}
            mr['mir_out'] = {}
            mr['mir_err'] = {}
            for i,ing in enumerate(self.ingredients):
                try: mr['swim_args']['ing%d' % i] = ing.multi_swim_arg_str()
                except: mr['swim_args']['ing%d' % i] = 'Null'
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
        onto im_mov. Then perform matching to initializeStack or refine the afm.
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
        self.matches_filenames = []


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
        # if self.recipe.method in ('manual','manual_strict'):
        if self.recipe.method == 'manual_hint':
            self.clr_indexes = copy.deepcopy(self.recipe.clr_indexes)
        if self.mode == 'MIR':
            self.afm = self.run_manual_mir()
        else:
            swim_output = self.run_swim()
            if swim_output == ['']:
                # raise ValueError(f"[{self.recipe.index}] SWIM Out is empty "
                #                  f"string! Err:\n{self.swim_err_lines}")
                logger.warning(f"[{self.recipe.index}] SWIM Out is empty "
                                 f"string! Err:\n{self.swim_err_lines}")
                self.snr = np.zeros(len(self.psta[0]))
                self.snr_report = snr_report(self.snr)
                return self.afm

            self.crop_match_signals()
            self.afm = self.ingest_swim_output(swim_output)


        if self.last:
            self.reduce_matches()
        return self.afm


    def get_swim_args(self):
        self.cx = int(self.recipe.ss['img_size'][0] / 2.0)
        self.cy = int(self.recipe.ss['img_size'][1] / 2.0)
        basename = os.path.basename(self.recipe.ss['path'])
        fn, ext = os.path.splitext(basename)
        multi_arg_str = ArgString(sep='\n')
        dir_scale = os.path.join(self.recipe.ss['location'], self.recipe.ss['level'])
        self.ms_paths = []
        m = self.recipe.method
        iters = str(self.recipe.ss['iterations'])
        whiten = str(self.recipe.ss['whitening'])
        use_clobber = self.recipe.ss['clobber_fixed_noise']
        clobber_px = self.recipe.ss['clobber_size']
        afm = '%.6f %.6f %.6f %.6f' % (
                self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1])

        for i in range(len(self.psta[0])):
            if m == 'grid_custom':
                if self.ID != 'g1x1':
                    if not self.recipe.grid_regions[i]:
                        continue
            if m == 'manual_hint':
                ind = self.clr_indexes.pop(0)
            else:
                ind = i
            # correlation signals argument (output path)
            b_arg = os.path.join(self.recipe.signals_dir, '%s_%s_%d%s' % (fn, m, ind, ext))
            self.ms_paths.append(b_arg)
            args = ArgString(sep=' ')
            args.append("%dx%d" % (self.ww[0], self.ww[1]))
            if self.recipe.ss['verbose_swim']:
                args.append("-v")
            if use_clobber:
                args.append('-f%d' % clobber_px)
            args.add_flag(flag='-i', arg=iters)
            args.add_flag(flag='-w', arg=whiten)
            if m in ('grid_default', 'grid_custom'):
                self.offx = int(self.psta[0][i] - self.cx)
                self.offy = int(self.psta[1][i] - self.cy)
                args.add_flag(flag='-x', arg='%d' % self.offx)
                args.add_flag(flag='-y', arg='%d' % self.offy)
            args.add_flag(flag='-b', arg=b_arg)
            if self.last:
                k_arg_name = '%s_%s_k_%d%s' % (fn, m, ind, ext)
                # k_arg_path = os.path.join(dir_scale, 'matches_raw', k_arg_name)
                # k_arg_path = os.path.join(dir_scale, 'matches', k_arg_name)
                k_arg_path = os.path.join(self.recipe.tmp_dir, k_arg_name)
                args.add_flag(flag='-k', arg=k_arg_path)
                self.matches_filenames.append(k_arg_path)
                t_arg_name = '%s_%s_t_%d%s' % (fn, m, ind, ext)
                # t_arg_path = os.path.join(dir_scale, 'matches_raw', t_arg_name)
                # t_arg_path = os.path.join(dir_scale, 'matches', t_arg_name)
                t_arg_path = os.path.join(self.recipe.tmp_dir, t_arg_name)
                args.add_flag(flag='-t', arg=t_arg_path)
                self.matches_filenames.append(t_arg_path)
            # args.append(self.recipe.ss['extra_kwargs'])
            args.append(self.recipe.ss['reference'])
            if m in ('manual_hint'):
                args.append('%s %s' % (self.psta[0][i], self.psta[1][i]))
            else:
                args.append('%s %s' % (self.cx, self.cy))
            args.append(self.recipe.ss['path'])
            if m in ('manual_hint'):
                args.append('%s %s' % (self.pmov[0][i], self.pmov[1][i]))
            else:
                self.adjust_x = '%.6f' % (self.cx + self.afm[0, 2])
                self.adjust_y = '%.6f' % (self.cy + self.afm[1, 2])
                args.append('%s %s' % (self.adjust_x, self.adjust_y))
            r = self.recipe.initial_rotation
            if abs(r) > 0:
                args.append(convert_rotation(r))
            args.append(afm)
            # args.append(self.recipe.ss['extra_args'])
            multi_arg_str.append(args())

        # print(f"{multi_arg_str()}")
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
        w, h = '%d' % self.ww[0], '%d' % self.ww[1]
        x1 = '%d' % int((self.ww[0] - px_keep) / 2.0 + 0.5)
        y1 = '%d' % int((self.ww[1] - px_keep) / 2.0 + 0.5)
        x2 = '%d' % int((self.ww[0] / 2) + (px_keep / 2.0) + 0.5)
        y2 = '%d' % int((self.ww[1] / 2) + (px_keep / 2.0) + 0.5)
        for path in self.ms_paths:
            self.crop_str_args = [
                'B', w, h, '1',
                '\nZ',
                '\nF', path,
                '\n0', '0', x1, y1,
                '\n%s'%w, '0', x2, y1,
                '\n%s'%w, h, x2, y2,
                '\n0', h, x1, y2,
                '\nT',
                '\n0', '1', '2',
                '\n2', '3', '0',
                '\nW', path
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
                        extra=f"#{self.recipe.index}\n"
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
            if self.psta[0][i] and self.psta[1][i]:
                mir_script_mp += f'{self.psta[0][i]} {self.psta[1][i]} ' \
                                 f'{self.pmov[0][i]} {self.pmov[1][i]}\n'
        # print(f"mir_script_mp:\n{mir_script_mp}")
        mir_script_mp += 'R'
        self.mir_script = mir_script_mp
        out, err = run_command(
            self.recipe.mir_c,
            cmd_input=mir_script_mp,
            desc='MIR to compose affine (strict manual)',
        )
        mir_mp_out_lines = out.strip().split('\n')
        mir_mp_err_lines = err.strip().split('\n')
        logging.getLogger('MAlogger').critical(
            f'\n==========\nManual MIR script:\n{mir_script_mp}\n'
            f'stdout >>\n{mir_mp_out_lines}\nstderr >>\n{mir_mp_err_lines}')
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


    def reduce_matches(self):
        tnLogger = logging.getLogger('tnLogger')
        tnLogger.critical("Reducing Matches...")


        src = self.recipe.tmp_dir
        od = self.recipe.matches_dir

        #Special handling since they are variable in # and never 1:1 with project files
        fn, ext = os.path.splitext(self.recipe.ss['path'])
        method = self.recipe.method
        od_pattern = os.path.join(od, '%s_%s_[tk]_%d%s' % (fn, method, self.recipe.index, ext))


        logger.critical(f"src         = {src}")
        logger.critical(f"fn          = {fn}")
        logger.critical(f"od          = {od}")
        logger.critical(f"method      = {od}")
        logger.critical(f"od_pattern  = {od_pattern}")

        for tn in glob.glob(od_pattern):
            logger.info(f'Removing {tn}...')
            try:
                os.remove(tn)
            except:
                logger.warning('An exception was triggered during removal of expired thumbnail: %s' % tn)

        tnLogger.info('Reducing the following thumbnails:\n%s' %str(self.matches_filenames))
        # logger.info(f'Reducing {len(self.matches_filenames)} total match images...')


        try:
            # siz_x, siz_y = ImageSize(next(absFilePaths(src)))
            siz_x, siz_y = self.ww
            scale_factor = int(max(siz_x, siz_y) / self.recipe.ss['target_thumb_size'])
            if scale_factor == 0:
                scale_factor = 1
        except Exception as e:
            print_exception()
            logger.error('Unable to generate thumbnail(level) - Do file(level) exist?')
            raise e

        for i, fn in enumerate(self.matches_filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            args = ['+%d' % scale_factor, 'of=%s' % ofn, '%s' % fn]
            # tnLogger.critical(f"Args:\n{args}")
            run_command(self.recipe.iscale2_c, args, desc="Reduce Matches")
            try:
                if os.path.exists(fn):
                    os.remove(fn)
            except:
                print_exception()


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
        ) as cmd_proc:
        # env=os.environ.copy()) as cmd_proc:
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


def convert_rotation(degrees):
    deg2rad = 2*np.pi/360.
    return np.sin(deg2rad*degrees)


def print_exception(extra='None'):
    tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}] {exi[0]}\nError Value : {exi[1]}\n" \
          f"{traceback.format_exc()}Additional Details: {extra}"
    logging.getLogger('exceptlogger').warning(txt)


def dict_hash(dictionary: Dict[str, Any]) -> str:
    """Returns an MD5 hash of a Python dictionary. source:
    www.doc.ic.ac.uk/~nuric/coding/how-to-hash-a-dictionary-in-python.html"""
    dhash = hashlib.md5()
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.hexdigest()

def absFilePaths(d):
    for dirpath, _, filenames in os.walk(d):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)

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