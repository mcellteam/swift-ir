#!/usr/bin/env python3

import os
import re
import sys
import copy
import logging
import platform
import datetime
import traceback
import numpy as np
import subprocess as sp

__all__ = ['run_recipe']

MAlogger      = logging.getLogger('MAlogger')
SWIMlogger    = logging.getLogger('SWIMlogger')
MIRlogger     = logging.getLogger('MIRlogger')
RMlogger      = logging.getLogger('recipemaker')
scratchlogger = logging.getLogger('scratch')


def run_recipe(project, scale_val, zpos=0, dev_mode=False):
    '''Assemble and execute an alignment recipe
    :param project: project data dictionary expressed as JSON-formatted string.
    :param scale_val: scale to run the alignment recipe on.
    :param zpos: z-index of current section within the stack.
    '''
    pd = project['data']['destination_path']
    scale_key = 'scale_' + str(scale_val)
    od = os.path.join(pd, scale_key, 'img_aligned')

    MAlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'manual_align.log')))
    SWIMlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'swim.log')))
    MIRlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'mir.log')))
    RMlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'recipemaker.log')))
    scratchpath = os.path.join(pd, 'logs', 'scratch.log')
    try:
        os.remove(scratchpath)
    except OSError:
        pass
    fh = logging.FileHandler(scratchpath)
    fh.setLevel(logging.DEBUG)
    scratchlogger.addHandler(fh)

    s_tbd = project['data']['scales'][scale_key]['stack']
    img_size = project['data']['scales'][scale_key]['image_src_size']
    # option = s_tbd[zpos]['alignment']['method_data']['alignment_option']
    if project['data']['scales'][scale_key]['isRefinement']:
        option = 'refine_affine'
    else:
        option = 'init_affine'
    # option = s_tbd[zpos]['alignment']['method_data']['alignment_option'] #Refactor
    init_afm = np.array([[1., 0., 0.], [0., 1., 0.]])

    if option in ('refine_affine', 'apply_affine'):
        scales = natural_sort(list(project['data']['scales'].keys()))
        scale_prev = scales[scales.index(scale_key) + 1]
        prev_scale_val = int(scale_prev[len('scale_'):])
        upscale = (float(prev_scale_val) / float(scale_val))
        scale_prev_dict = project['data']['scales'][scale_prev]['stack']
        # prev_afm = np.array(scale_prev_dict[zpos]['alignment']['method_results']['affine_matrix']).copy()
        prev_method = scale_prev_dict[zpos]['current_method']
        prev_afm = np.array(scale_prev_dict[zpos]['alignment_history'][prev_method]['affine_matrix']).copy()
        prev_afm[0][2] *= upscale
        prev_afm[1][2] *= upscale
        init_afm = prev_afm

    s_tbd[zpos]['alignment']['method_results'].setdefault('affine_matrix', init_afm.tolist())
    s_tbd[zpos]['alignment']['method_results'].setdefault('snr', [])
    s_tbd[zpos]['alignment']['method_results'].setdefault('snr_report', 'SNR: --')

    initial_rotation = float(project['data']['defaults']['initial-rotation'])
    isRefinement = project['data']['scales'][scale_key]['isRefinement']


    if not s_tbd[zpos]['skipped']:
        if os.path.basename(s_tbd[zpos]['reference']) != '':
            recipe = align_recipe(
                pd=pd,
                od=od,
                init_afm=init_afm,
                img_size=img_size,
                layer_dict=s_tbd[zpos],
                scale=scale_key,
                defaults=project['data']['defaults'],
                initial_rotation=initial_rotation,
                isRefinement=isRefinement,
                dev_mode=dev_mode
            )
            recipe.assemble_recipe()
            recipe.execute_recipe()

    return (project, True)


class align_recipe:

    global scratchlogger
    global MIRlogger
    global SWIMlogger
    global RMlogger
    global MAlogger

    def __init__(self, pd, od, init_afm, img_size, layer_dict, scale, defaults, initial_rotation, isRefinement, dev_mode):
        self.pd = pd
        self.od = od
        self.scale_dir = os.path.abspath(os.path.dirname(self.od))
        self.init_afm = init_afm
        self.siz = img_size
        self.layer_dict = layer_dict
        self.im_sta_fn = layer_dict['reference']
        self.im_mov_fn = layer_dict['filename']
        self.alData = layer_dict['alignment']
        self.scale = scale
        self.defaults = defaults
        self.cur_method = layer_dict['current_method']
        if isRefinement:
            self.option = 'refine_affine'
        else:
            self.option = 'init_affine'
        # self.option = self.alData['method_data']['alignment_option']
        if self.cur_method == 'grid-default':
            self.wht = self.defaults['signal-whitening']
            self.iters = self.defaults['swim-iterations']
        else:
            # self.wht = self.alData['method_data']['whitening_factor']
            self.wht = self.alData['swim_settings']['signal-whitening']
            self.iters = self.alData['swim_settings']['iterations']
        self.grid_custom_regions  = self.alData['swim_settings']['grid-custom-regions']
        self.ingredients = []
        self.initial_rotation = float(self.defaults['initial-rotation'])
        self.afm = np.array([[1., 0., 0.], [0., 1., 0.]])
        self.dev_mode = dev_mode

        # Configure platform-specific path to executables for C SWiFT-IR
        slug = (('linux', 'darwin')[platform.system() == 'Darwin'], 'tacc')['tacc.utexas' in platform.node()]
        self.swim_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/swim'
        self.mir_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/mir'


    def __str__(self):
        s = "align_recipe: \n"
        s += "  dir: " + str(self.scale_dir) + "\n"
        s += "  sta: " + str(self.im_sta_fn) + "\n"
        s += "  mov: " + str(self.im_mov_fn) + "\n"


    def assemble_recipe(self):
        scratchlogger.critical(f'ASSEMBLING RECIPE [{self.cur_method}]...:')

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
            ww_1x1 = self.defaults[self.scale]['swim-window-px']
            ww_2x2 = [int(ww_1x1[0]/2), int(ww_1x1[1]/2)]
            if self.option == 'init_affine':
                self.add_ingredients([
                    align_ingredient(mode='SWIM-Grid', ww=ww_1x1, psta=psta_1, ID='Grid1x1'),
                    align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-a'),
                    align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-b', last=True)])
            elif self.option == 'refine_affine':
                self.add_ingredients([align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, afm=self.init_afm, ID='Grid2x2', last=True)])
        elif self.cur_method == 'grid-custom':
            ww_1x1 = self.alData['swim_settings']['grid-custom-px']
            ww_2x2 = self.alData['swim_settings']['grid-custom-2x2-px']
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
            ww_1x1 = self.defaults[self.scale]['swim-window-px']
            ww_2x2 = self.alData['swim_settings']['grid-custom-2x2-px']
            self.add_ingredients([
                align_ingredient(mode='SWIM-Grid', ww=ww_1x1, psta=psta_1, ID='Grid1x1'),
                align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-a'),
                align_ingredient(mode='SWIM-Grid', ww=ww_2x2, psta=psta_2x2, ID='Grid2x2-b', last=True),
            ])
        else:
            ww = self.alData['manual_settings']['manual_swim_window_px']
            man_pmov = np.array(self.alData['manpoints_mir']['base']).transpose()
            man_psta = np.array(self.alData['manpoints_mir']['ref']).transpose()
            if self.cur_method == 'manual-hint':
                self.add_ingredients([
                    align_ingredient(mode='MIR', ww=ww, psta=man_psta, pmov=man_pmov),
                    align_ingredient(mode='SWIM-Manual', ww=ww, psta=man_psta, pmov=man_pmov, ID='Manual-a'),
                    align_ingredient(mode='SWIM-Manual', ww=ww, psta=man_psta, pmov=man_pmov, ID='Manual-b', last=True)])
            elif self.cur_method == 'manual-strict':
                self.add_ingredients([align_ingredient(mode='MIR', ww=ww, psta=man_psta, pmov=man_pmov, last=True)])

        scratchlogger.critical(f'\n\n# ingredients = {len(self.ingredients)}\n')


    def execute_recipe(self):
        scratchlogger.critical('execute_recipe >>>>')

        # Initialize afm to afm of first ingredient in recipe
        # if self.ingredients[0].afm is not None:
        # if self.ingredients[0].afm:
        #     self.afm = self.ingredients[0].afm
        self.afm = self.init_afm

        # Execute each ingredient in recipe
        for i, ingredient in enumerate(self.ingredients):
            scratchlogger.critical(f'----------------\n'
                                   f'Ingredient #: {i} of {len(self.ingredients)}\n'
                                   f'  AFM (before): {self.afm}\n'
                                   f'----------------')
            ingredient.afm = self.afm
            try:
                self.afm = ingredient.execute_ingredient()
            except:
                print_exception(self.pd)

        scratchlogger.critical(f'Final AFM = {self.afm}')

        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        snr = self.ingredients[-1].snr
        snr_report = self.ingredients[-1].snr_report
        afm = self.ingredients[-1].afm

        scratchlogger.critical(f'<<<< 1 >>>>')

        # Retrieve alignment result
        self.layer_dict.setdefault('alignment_history', {})
        self.layer_dict['alignment_history'].setdefault(self.cur_method, [])
        # if type(snr) == float:
        #     self.layer_dict['alignment']['method_results']['snr'] = [snr]
        # else:
        # self.layer_dict['alignment']['method_results']['snr'] = list(snr)


        if self.im_sta_fn == self.im_mov_fn:
            self.layer_dict['alignment']['method_results']['snr'] = [0.0]
            self.layer_dict['alignment']['method_results']['snr_str'] = str([0.0])
            self.layer_dict['alignment']['method_results']['snr_report'] = 'SNR: --'
            self.layer_dict['alignment']['method_results']['snr_average'] = 0.0
        else:
            snr_list = snr.tolist()
            self.layer_dict['alignment']['method_results']['snr'] = snr_list
            self.layer_dict['alignment']['method_results']['snr_type'] = str(type(snr))
            self.layer_dict['alignment']['method_results']['snr_str'] = str(snr)
            self.layer_dict['alignment']['method_results']['snr_report'] = str(snr_report)
            self.layer_dict['alignment']['method_results']['snr_average'] = sum(snr_list) / len(snr_list)


        #
        self.layer_dict['alignment']['method_results']['affine_matrix'] = afm.tolist()
        self.layer_dict['alignment']['method_results']['swim_pos'] = self.ingredients[-1].psta.tolist()
        self.layer_dict['alignment']['method_results']['datetime'] = time
        self.layer_dict['alignment']['method_results']['wht'] = self.wht
        self.layer_dict['alignment']['method_results']['swim-iterations'] = self.iters
        self.layer_dict['alignment']['method_results']['option'] = self.option
        self.layer_dict['alignment']['method_results']['current_method'] = self.cur_method
        self.layer_dict['alignment']['method_results']['ingredients'] = {}
        self.layer_dict['alignment']['method_results']['im_sta_fn']= self.im_sta_fn
        self.layer_dict['alignment']['method_results']['im_mov_fn']= self.im_mov_fn
        self.layer_dict['alignment']['method_results']['siz']= self.siz
        if self.cur_method == 'grid-custom':
            self.layer_dict['alignment']['method_results']['grid_custom_regions'] = self.grid_custom_regions
        # self.layer_dict['alignment_history'][self.cur_method].append(self.layer_dict['alignment']['method_results'])
        self.layer_dict['alignment_history'][self.cur_method] = self.layer_dict['alignment']['method_results']


        if self.dev_mode:
            self.layer_dict['alignment']['swim_args'] = {}
            self.layer_dict['alignment']['swim_out'] = {}
            self.layer_dict['alignment']['swim_err'] = {}
            self.layer_dict['alignment']['mir_toks'] = {}
            self.layer_dict['alignment']['mir_script'] = {}
            self.layer_dict['alignment']['mir_out'] = {}
            self.layer_dict['alignment']['mir_err'] = {}
            self.layer_dict['alignment']['swim_ww_arg'] = {}
            self.layer_dict['alignment']['crop_str_mir'] = {}
            for i,ing in enumerate(self.ingredients):
                try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i] = {}
                except: print_exception(self.pd)
                try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['ww'] = ing.ww
                except: print_exception(self.pd)
                # if self.cur_method == 'manual-hint':
                try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['psta'] = str(ing.psta)
                except: print_exception(self.pd)
                try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['pmov'] = str(ing.pmov)
                except: print_exception(self.pd)
                if self.cur_method in ('grid-default', 'grid-custom'):
                    # try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['cx'] = str(ing.cx)
                    # except: print_exception(self.pd)
                    # try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['cy'] = str(ing.cy)
                    # except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['adjust_x'] = str(ing.adjust_x)
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['adjust_y'] = str(ing.adjust_y)
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['afm'] = str(ing.afm)
                    except: print_exception(self.pd)
                if self.cur_method in ('grid-default', 'grid-custom', 'manual-hint'):
                    try: self.layer_dict['alignment']['swim_args']['ingredient_%d' % i] = ing.multi_arg_str
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['swim_out']['ingredient_%d' % i] = ing.swim_output
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['swim_err']['ingredient_%d' % i] = ing.swim_err_lines
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['mir_toks']['ingredient_%d' % i] = ing.mir_toks
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['mir_script']['ingredient_%d' % i] = ing.mir_script
                    except: print_exception(self.pd)
                    # try: self.layer_dict['alignment']['dx']['ingredient_%d' % i] = ing.dx
                    # except: print_exception(self.pd)
                    # try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i] = ing.dy
                    # except: print_exception(self.pd)
                    # try: self.layer_dict['alignment']['method_results']['ingredient_%d' % i]['swim_drift'] = ing.swim_drift
                    # except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['mir_out']['ingredient_%d' % i] = ing.mir_out_lines
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['mir_err']['ingredient_%d' % i] = ing.mir_err_lines
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['swim_ww_arg']['ingredient_%d' % i] = ing.swim_ww_arg
                    except: print_exception(self.pd)
                    try: self.layer_dict['alignment']['crop_str_mir']['ingredient_%d' % i] = ing.crop_str_mir
                    except: print_exception(self.pd)


        # cfg.data.stack()[5]['alignment']['method_results']['ingredient_0']['swim_out']
        # ['28.6787: /Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/img_src/R34CA1-BS12.105.tif 512 512 /Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/img_src/R34CA1-BS12.106.tif 518.514 506.982  1 0 0 1 (6.5141 -5.01831 8.22295)']
        # ['28.6787: /Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/img_src/R34CA1-BS12.105.tif 512 512 /Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/img_src/R34CA1-BS12.106.tif 518.514 506.982  1 0 0 1 (6.5141 -5.01831 8.22295)']
        # a = cfg.data.stack()[5]['alignment']['method_results']['ingredient_0']['swim_out'][0]
        # a.replace('(', ' ').replace(')', ' ').strip().split()
        # ['28.6787:',
        #  '/Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/img_src/R34CA1-BS12.105.tif',
        #  '512',
        #  '512',
        #  '/Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/img_src/R34CA1-BS12.106.tif',
        #5  '518.514',
        #6  '506.982',
        #  '1',
        #8  '0',
        #9  '0',
        #  '1',
        #  '6.5141',
        #  '-5.01831',
        #  '8.22295']
        #

        # self.layer_dict['alignment']['method_results']['auto_ww'] = self.auto_ww
        # self.layer_dict['alignment']['method_results']['pts_base'] = self.man_pmov.tolist()
        # self.layer_dict['alignment']['method_results']['pts_ref'] = self.man_psta.tolist()



        # self.layer_dict['alignment']['method_data']['bias_x_per_image'] = 0
        # self.layer_dict['alignment']['method_data']['bias_y_per_image'] = 0
        # self.layer_dict['alignment']['method_data']['bias_rot_per_image'] = 0
        # self.layer_dict['alignment']['method_data']['bias_scale_x_per_image'] = 1
        # self.layer_dict['alignment']['method_data']['bias_scale_y_per_image'] = 1
        # self.layer_dict['alignment']['method_data']['bias_skew_x_per_image'] = 0

        # self.layer_dict['alignment']['mir_toks'] = self.ingredients[-1].mir_toks
        # self.layer_dict['alignment']['mir_args'] = self.ingredients[-1].mir_script
        # self.layer_dict['alignment'].setdefault('swim_args', {})
        # self.layer_dict['alignment'].setdefault('swim_out', {})
        # self.layer_dict['alignment'].setdefault('swim_err', {})

        # self.layer_dict['alignment']['ingredient0_dx'] = self.ingredients[0].dx
        # self.layer_dict['alignment']['ingredient0_dy'] = self.ingredients[0].dy

        # self.layer_dict['alignment']['swim_args'] = {}
        # self.layer_dict['alignment']['swim_out'] = {}
        # self.layer_dict['alignment']['swim_err'] = {}
        # if self.cur_method in ('grid-default', 'grid-custom', 'manual-hint'):
        #     for i,ing in enumerate(self.ingredients):
        #         try:    self.layer_dict['alignment']['swim_args']['ingredient_%d' % i] = ing.multi_arg_str
        #         except: print_exception(self.pd)
        #         try:    self.layer_dict['alignment']['swim_out']['ingredient_%d' % i] = ing.swim_output
        #         except: print_exception(self.pd)
        #         try:    self.layer_dict['alignment']['swim_err']['ingredient_%d' % i] = ing.swim_err_lines
        #         except: print_exception(self.pd)

        scratchlogger.critical('<<<<  execute_recipe')
        return afm


    def add_ingredients(self, ingredients):
        for ingredient in ingredients:
            ingredient.recipe = self
            ingredient.alData = self.layer_dict['alignment']
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
        self.alData = None
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
            self.afm = self.ingest_swim_output(swim_output)
        return self.afm


    def run_swim(self):
        scratchlogger.critical(f'run_swim [{self.ID}] >>>>')

        # cx = int(self.recipe.siz[0] / 2.0)
        # cy = int(self.recipe.siz[1] / 2.0)
        # adjust_x = '%.6f' % (cx + self.afm[0, 2])
        # adjust_y = '%.6f' % (cy + self.afm[1, 2])

        self.cx = int(self.recipe.siz[0] / 2.0)
        self.cy = int(self.recipe.siz[1] / 2.0)

        afm_arg = '%.6f %.6f %.6f %.6f' % (self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1])

        if isinstance(self.ww, float):
            self.swim_ww_arg = str(int(self.ww))
        else:
            self.swim_ww_arg = str(int(self.ww[0])) + "x" + str(int(self.ww[1])) #<--

        basename = os.path.basename(self.recipe.im_mov_fn)
        filename, extension = os.path.splitext(basename)

        multi_arg_str = ArgString(sep='\n')

        ms_names = []

        for i in range(len(self.psta[0])):
            scratchlogger.critical(f'Constructing {self.recipe.cur_method} [i={i}]...')

            if self.recipe.cur_method == 'grid-custom':
                if self.ID != 'Grid1x1':
                    if not self.recipe.grid_custom_regions[i]:
                        scratchlogger.critical(f'Continuing (!) [i={i}]...')
                        continue

            # correlation signals argument (output path)
            b_arg = os.path.join( self.recipe.scale_dir, 'signals', '%s_%s_%d%s' %
                                  (filename, self.recipe.cur_method, i, extension))
            ms_names.append(b_arg)

            args = ArgString(sep=' ')
            args.append('ww_' + self.swim_ww_arg)
            if self.alData['swim_settings']['clobber_fixed_noise']:
                args.append('-f%d' % self.alData['swim_settings']['clobber_fixed_noise_px'])
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
                if self.alData['swim_settings']['karg']:
                    k_arg_name = '%s_%s_k_%d%s' % (filename, self.recipe.cur_method, i, extension)
                    k_arg_path = os.path.join(self.alData['swim_settings']['karg_path'], k_arg_name)
                    args.add_flag(flag='-k', arg=k_arg_path)
                if self.alData['swim_settings']['targ']:
                    t_arg_name = '%s_%s_t_%d%s' % (filename, self.recipe.cur_method, i, extension)
                    t_arg_path = os.path.join(self.alData['swim_settings']['targ_path'], t_arg_name)
                    args.add_flag(flag='-t', arg=t_arg_path)
            args.append(self.alData['swim_settings']['extra_kwargs'])
            args.append(self.recipe.im_sta_fn)
            if self.recipe.cur_method in ('manual-hint'):
                args.append('%s %s' % (self.psta[0][i], self.psta[1][i]))
            else:
                args.append('%s %s' % (self.cx, self.cy))
            args.append(self.recipe.im_mov_fn)
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
            args.append(self.alData['swim_settings']['extra_args'])
            multi_arg_str.append(args())


        scratchlogger.critical('Running command >>>>')

        self.multi_arg_str = multi_arg_str()

        SWIMlogger.critical(f'Multi-SWIM Argument String:\n{multi_arg_str()}')
        o = run_command(
            self.recipe.swim_c,
            arg_list=[self.swim_ww_arg],
            cmd_input=multi_arg_str(),
            extra=f'Automatic SWIM Alignment ({self.ID})',
        )

        self.swim_output = o['out'].strip().split('\n')
        self.swim_err_lines = o['err'].strip().split('\n')

        scratchlogger.critical('Cropping Match Signals...')
        keep = .30
        px_keep = 128
        if self.recipe.cur_method in ('grid-default', 'grid-custom'):
            w = str(int(self.ww[0] / 2.0))
            h = str(int(self.ww[1] / 2.0))
            # x1 = str(int(self.ww[0] * ((1.0 - keep) / 2.0)))  # short
            # x2 = str(int(self.ww[0] * (.50 + (keep / 2.0))))  # long
            # y1 = str(int(self.ww[1] * ((1.0 - keep) / 2.0)))  # short
            # y2 = str(int(self.ww[1] * (.50 + (keep / 2.0))))  # long
            x1 = str(int((self.ww[0] - px_keep) / 2.0))
            y1 = str(int((self.ww[1] - px_keep) / 2.0))
            x2 = str(int((.50 * self.ww[0]) + (px_keep / 2.0)))
            y2 = str(int((.50 * self.ww[1]) + (px_keep / 2.0)))
        else:
            w = h = str(int(self.ww))
            # x1 = y1 = str(int(self.ww * ((1.0 - keep) / 2.0)))
            # x2 = y2 = str(int(self.ww * (.50 + (keep / 2.0))))
            x1 = y1 = str(int((self.ww - px_keep) / 2.0))
            x2 = y2 = str(int((.50 * self.ww) + (px_keep / 2.0)))

        for name in ms_names:
            self.crop_str_mir = f"""B {w} {h} 1\nZ\nF {name}\n0 0 {x1} {y1}\n{w} 0 {x2} {y1}\n{w} {h} {x2} {y2}\n0 {h} {x1} {y2}\nT\n0 1 2\n2 3 0\nW {name}"""

            # self.crop_str_mir = f"B {w} {h} 1\n"\
            #                     f"Z\n"\
            #                     f"F {name}\n"\
            #                     f"0 0 {x1} {y1}\n"\
            #                     f"{w} 0 {x2} {y1}\n"\
            #                     f"{w} {h} {x2} {y2}\n"\
            #                     f"0 {h} {x1} {y2}\n"\
            #                     f"T\n"\
            #                     f"0 1 2\n"\
            #                     f"2 3 0\n"\
            #                     f"W {name}"

            o = run_command(self.recipe.mir_c, arg_list=[], cmd_input=self.crop_str_mir,
                        extra=f'MIR the Match Signals to crop ({self.ID})', )

        if self.mode == 'SWIM-Manual':
            MAlogger.critical(f'\nSWIM OUT:\n{self.swim_output}\nSWIM ERR:\n{self.swim_err_lines}')
        scratchlogger.critical(f'<<<< run_swim [{self.ID}]')

        return self.swim_output


    def ingest_swim_output(self, swim_output):

        if swim_output == '':
            self.snr = np.zeros(len(self.psta[0]))
            self.snr_report = snr_report(self.snr)
            return self.afm

        self.mir_script = ""
        snr_list = []
        dx = dy = 0.0
        # loop over SWIM output to build the MIR script:

        if (len(swim_output) == 1) and (self.recipe.cur_method in ('default-grid', 'custom-grid')):
            toks = swim_output[0].replace('(', ' ').replace(')', ' ').strip().split()
            self.dx = float(toks[8])
            self.dy = float(toks[9])
            aim = np.eye(2, 3, dtype=np.float32)
            aim = copy.deepcopy(self.afm)
            aim[0, 2] += self.dx
            aim[1, 2] += self.dy
            self.afm = aim
            self.snr = np.array(snr_list)
            self.snr_report = snr_report(self.snr)
            return self.afm
        else:
            for i,l in enumerate(swim_output):
                toks = l.replace('(', ' ').replace(')', ' ').strip().split()
                self.mir_toks[i] = str(toks)
                MIRlogger.critical('MIR toks:\n %s' %self.mir_toks[i])
                # if len(swim_output) == 1:
                #     dx = float(toks[8])
                #     dy = float(toks[9])
                #     self.dx = float(toks[8])
                #     self.dy = float(toks[9])
                # else:
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                self.mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
            self.mir_script += 'R\n'
            o = run_command(self.recipe.mir_c, arg_list=[], cmd_input=self.mir_script, extra=f'MIR the SWIM offsets to get affine ({self.ID})', )
            self.mir_out_lines = o['out'].strip().split('\n')
            self.mir_err_lines = o['err'].strip().split('\n')

            MIRlogger.critical(f'***MIR script***\n{str(self.mir_script)}\n'
                               f'MIR std out:\n{str(self.mir_out_lines)}\n'
                               f'MIR std err:\n{str(self.mir_err_lines)}')

            aim = np.eye(2, 3, dtype=np.float32)

            # if len(swim_output) == 1:
            #     # 1x1 offset can be plugged directly into the affine's translation components
            #     aim = copy.deepcopy(self.afm)
            #     aim[0, 2] += self.dx
            #     aim[1, 2] += self.dy
            # else:
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
            mir_script_mp += f'{self.psta[0][i]} {self.psta[1][i]} {self.pmov[0][i]} {self.pmov[1][i]}\n'
        mir_script_mp += 'R'
        self.mir_script = mir_script_mp

        o = run_command(
            self.recipe.mir_c,
            arg_list=[],
            cmd_input=mir_script_mp,
            extra='MIR to get affine using manual correspondence points',
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


def run_command(cmd, arg_list=None, cmd_input=None, extra=''):
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    nl = '\n'
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    RMlogger.critical(f"\n========== Run Command ==========\n"
                      f"Description     : {extra}\n"
                      f"Running command :\n{(nl.join(cmd_arg_list), 'None')[cmd_arg_list == '']}\n"
                      f"Passing data    :\n{(cmd_input, 'None')[cmd_input == '']}\n\n"
                      f">> stdout\n{(cmd_stdout, 'None')[cmd_stdout == '']}\n"
                      f">> stderr\n{(cmd_stderr, 'None')[cmd_stderr == '']}\n"
                      )
    return ({'out': cmd_stdout, 'err': cmd_stderr})


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

def print_exception(dest):
    tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}]\nError Type : {exi[0]}\nError Value : {exi[1]}\n{traceback.format_exc()}"
    print(txt)

    lf = os.path.join(dest, 'logs', 'exceptions.log')
    with open(lf, 'w+') as f:
        f.write('\n' + txt)


if __name__ == '__main__':
    RMlogger.info("Running " + __file__ + ".__main__()")


'''
Notes:
  - mir has a -v flag for more output
  - wsf = 0.80 (Most common good value for wsf) = 0.75  (Also a good value for most projects)

'''