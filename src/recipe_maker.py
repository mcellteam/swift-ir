#!/usr/bin/env python3

import os
import re
import copy
import logging
import platform
import datetime
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
    option = s_tbd[zpos]['alignment']['method_data']['alignment_option']
    init_afm = np.array([[1., 0., 0.], [0., 1., 0.]])

    if option in ('refine_affine', 'apply_affine'):
        scales = natural_sort(list(project['data']['scales'].keys()))
        scale_prev = scales[scales.index(scale_key) + 1]
        prev_scale_val = int(scale_prev[len('scale_'):])
        upscale = (float(prev_scale_val) / float(scale_val))
        scale_prev_dict = project['data']['scales'][scale_prev]['stack']
        prev_afm = np.array(scale_prev_dict[zpos]['alignment']['method_results']['affine_matrix']).copy()
        prev_afm[0][2] *= upscale
        prev_afm[1][2] *= upscale
        init_afm = prev_afm

    s_tbd[zpos]['alignment']['method_results'].setdefault('affine_matrix', init_afm.tolist())
    s_tbd[zpos]['alignment']['method_results'].setdefault('snr', [])
    s_tbd[zpos]['alignment']['method_results'].setdefault('snr_report', 'SNR: --')

    initial_rotation = float(project['data']['initial_rotation'])

    if not s_tbd[zpos]['skipped']:
        if os.path.basename(s_tbd[zpos]['reference']) != '':
            recipe = align_recipe(
                od=od,
                init_afm=init_afm,
                img_size=img_size,
                layer_dict=s_tbd[zpos],
                scale=scale_key,
                defaults=project['data']['defaults'],
                initial_rotation=initial_rotation,
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

    def __init__(self, od, init_afm, img_size, layer_dict, scale, defaults, initial_rotation):
        self.od = od
        self.scale_dir = os.path.abspath(os.path.dirname(self.od))
        self.init_afm = init_afm
        self.siz = img_size
        self.layer_dict = layer_dict
        self.im_sta_fn = layer_dict['reference']
        self.im_mov_fn = layer_dict['filename']
        self.alData = layer_dict['alignment']
        # self.cur_method = layer_dict['alignment']['current_method']
        self.cur_method = layer_dict['current_method']
        self.scale=scale
        self.defaults = defaults

        #New
        if self.cur_method == 'grid-default':
            self.grid_ww = self.defaults[scale]['swim-window-px']
            self.grid_ww_2x2 = [self.grid_ww[0] / 2,  self.grid_ww[1] / 2]
        else:
            self.grid_ww = self.alData['swim_settings']['grid-custom-px']
            self.grid_ww_2x2 = self.alData['swim_settings']['grid-custom-2x2-px']

        self.option = self.alData['method_data']['alignment_option']
        self.wsf    = self.alData['method_data']['win_scale_factor']
        self.auto_ww    = self.alData['swim_settings']['grid-custom-px']
        self.grid_default_ww    = self.alData['swim_settings']['default_auto_swim_window_px']
        self.grid_custom_ww    = self.alData['swim_settings']['grid-custom-px']
        self.ww_2x2    = self.alData['swim_settings']['grid-custom-2x2-px']
        self.wht    = self.alData['method_data']['whitening_factor']
        self.man_ww = self.alData['manual_settings'].get('manual_swim_window_px')
        self.hint_or_strict = self.alData['manual_settings'].get('hint-or-strict')
        self.grid_custom_regions  = self.alData['swim_settings']['grid-custom-regions']
        self.man_pmov = np.array(self.alData['manpoints_mir'].get('base')).transpose()
        self.man_psta = np.array(self.alData['manpoints_mir'].get('ref')).transpose()
        self.ingredients = []
        self.initial_rotation = initial_rotation
        # self.iters = 3
        self.afm = np.array([[1., 0., 0.], [0., 1., 0.]])

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
        pa = np.zeros((2, 1))   # Point Array for one point
        wwx = int(self.grid_default_ww[0])  # Window Width in x Scaled
        wwy = int(self.grid_default_ww[1])  # Window Width in y Scaled
        cx = int(self.siz[0] / 2.0)   # Window Center in x
        cy = int(self.siz[1] / 2.0)   # Window Center in y
        pa[0, 0] = cx
        pa[1, 0] = cy
        psta_1 = pa

        # Set up 2x2 points and windows
        nx, ny = 2, 2
        pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
        sx = int(self.siz[0] / 2.0)  # Initial Size of each window
        sy = int(self.siz[1] / 2.0)  # Initial Size of each window
        for x in range(nx):
            for y in range(ny):
                pa[0, x + nx * y] = int(0.5 * sx + sx * x)  # Point Array (2x4) points
                pa[1, x + nx * y] = int(0.5 * sy + sy * y)  # Point Array (2x4) points
        sx_2x2 = int(self.auto_ww[0] / 2)
        sy_2x2 = int(self.auto_ww[1] / 2)
        psta_2x2 = pa

        scratchlogger.critical(f'\nsx,sy                  = {sx},{sy}\n'
                               f'wwx,wwy                = {wwx},{wwy}\n'
                               f'sx_2x2,sy_2x2          = {sx_2x2},{sy_2x2}\n'
                               f'**default** psta_2x2   = {psta_2x2}\n'
                               f'len(psta_2x2[0])       = {len(psta_2x2[0])}\n'
                               f'current method         = {self.cur_method}\n'
                               f'========================')


        if self.cur_method == 'grid-custom':
            scratchlogger.critical(f'grid-custom >>>>')
            img_w = self.siz[0]
            img_h = self.siz[1]
            # ww_full = self.auto_ww # full window width
            ww_full = self.grid_custom_ww # full window width
            ww_2x2 =self.ww_2x2 # 2x2 window width

            offset_x1 = ((img_w - ww_full[0]) / 2) + (ww_2x2[0] / 2)
            offset_x2 = img_w - offset_x1
            offset_y1 = ((img_h - ww_full[1]) / 2) + (ww_2x2[1] / 2)
            offset_y2 = img_h - offset_y1

            cps = [(offset_x1, offset_y1),
                   (offset_x2, offset_y1),
                   (offset_x1, offset_y2),
                   (offset_x2, offset_y2)]

            pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
            for i,p in enumerate(cps):
                pa[0,i] = int(p[0])
                pa[1,i] = int(p[1])
            psta_2x2 = pa


        if self.cur_method in ('manual-hint', 'manual-strict'):
            MAlogger.critical(f'{self.im_mov_fn}\n'
                              f'Type         : {self.cur_method}\n'
                              f'Window width : {self.man_ww}')

        # Example: psta_2x2 = [[256. 768. 256. 768.] [256. 256. 768. 768.]]

        ww2x2 = (self.ww_2x2[0], self.ww_2x2[1])


        if self.cur_method == 'grid-default':
            if self.option == 'init_affine':
                self.add_ingredients([
                    align_ingredient(mode='SWIM-Grid', ww=self.grid_default_ww[0], psta=psta_1, ID='Grid1x1'),
                    align_ingredient(mode='SWIM-Grid', ww=(sx_2x2, sy_2x2), psta=psta_2x2, ID='Grid2x2-a'),
                    align_ingredient(mode='SWIM-Grid', ww=(sx_2x2, sy_2x2), psta=psta_2x2, ID='Grid2x2-b', last=True)])
            elif self.option == 'refine_affine':
                self.add_ingredients([align_ingredient(mode='SWIM-Grid', ww=(sx_2x2, sy_2x2), psta=psta_2x2, afm=self.init_afm, ID='Grid2x2', last=True)])
        elif self.cur_method == 'grid-custom':
            self.add_ingredients([
                align_ingredient(mode='SWIM-Grid', ww=self.grid_custom_ww[0], psta=psta_1, ID='Grid1x1'),
                align_ingredient(mode='SWIM-Grid', ww=ww2x2, psta=psta_2x2, ID='Grid2x2-a'),
                align_ingredient(mode='SWIM-Grid', ww=ww2x2, psta=psta_2x2, ID='Grid2x2-b', last=True),
            ])
        elif self.cur_method == 'manual-hint':
            self.add_ingredients([
                align_ingredient(mode='MIR', ww=self.man_ww, psta=self.man_psta, pmov=self.man_pmov),
                align_ingredient(mode='SWIM-Manual', ww=self.man_ww, psta=self.man_psta, pmov=self.man_pmov, ID='Manual-a'),
                align_ingredient(mode='SWIM-Manual', ww=self.man_ww, psta=self.man_psta, pmov=self.man_pmov, ID='Manual-b', last=True)])
        elif self.cur_method == 'manual-strict':
            self.add_ingredients([align_ingredient(mode='MIR', ww=self.man_ww, psta=self.man_psta, pmov=self.man_pmov, last=True)])

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
            self.afm = ingredient.execute_ingredient()

        scratchlogger.critical(f'Final AFM = {self.afm}')

        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        snr = self.ingredients[-1].snr
        snr_report = self.ingredients[-1].snr_report
        afm = self.ingredients[-1].afm

        scratchlogger.critical(f'<<<< 1 >>>>')

        # Retrieve alignment result
        self.layer_dict.setdefault('alignment_history', {})
        self.layer_dict['alignment_history'].setdefault(self.cur_method, [])
        self.layer_dict['alignment']['method_results']['snr'] = list(snr)
        self.layer_dict['alignment']['method_results']['snr_report'] = str(snr_report)
        self.layer_dict['alignment']['method_results']['affine_matrix'] = afm.tolist()
        self.layer_dict['alignment']['method_results']['swim_pos'] = self.ingredients[-1].psta.tolist()
        self.layer_dict['alignment']['method_results']['datetime'] = time
        self.layer_dict['alignment']['method_results']['wht'] = self.wht
        self.layer_dict['alignment']['method_results']['auto_ww'] = self.auto_ww
        self.layer_dict['alignment']['method_results']['ww_2x2'] = self.ww_2x2
        self.layer_dict['alignment']['method_results']['pts_base'] = self.man_pmov.tolist()
        self.layer_dict['alignment']['method_results']['pts_ref'] = self.man_psta.tolist()
        self.layer_dict['alignment']['method_results']['manual_mode'] = self.hint_or_strict
        if self.cur_method == 'grid-custom':
            self.layer_dict['alignment']['method_results']['grid_custom_regions'] = self.grid_custom_regions

        scratchlogger.critical(f'<<<< 2 >>>>')

        self.layer_dict['alignment']['method_data']['bias_x_per_image'] = 0
        self.layer_dict['alignment']['method_data']['bias_y_per_image'] = 0
        self.layer_dict['alignment']['method_data']['bias_rot_per_image'] = 0
        self.layer_dict['alignment']['method_data']['bias_scale_x_per_image'] = 1
        self.layer_dict['alignment']['method_data']['bias_scale_y_per_image'] = 1
        self.layer_dict['alignment']['method_data']['bias_skew_x_per_image'] = 0
        self.layer_dict['alignment']['mir_toks'] = self.ingredients[-1].mir_toks
        self.layer_dict['alignment']['mir_args'] = self.ingredients[-1].mir_script
        self.layer_dict['alignment'].setdefault('swim_args', {})
        self.layer_dict['alignment'].setdefault('swim_out', {})
        self.layer_dict['alignment'].setdefault('swim_err', {})

        scratchlogger.critical(f'<<<< 3 >>>>')

        # self.layer_dict['alignment']['ingredient0_dx'] = self.ingredients[0].dx
        # self.layer_dict['alignment']['ingredient0_dy'] = self.ingredients[0].dy

        self.layer_dict['alignment']['swim_args'] = {}
        self.layer_dict['alignment']['swim_out'] = {}
        self.layer_dict['alignment']['swim_err'] = {}
        if self.cur_method in ('grid-default', 'grid-custom', 'manual-hint'):
            for i,ingredient in enumerate(range(len(self.ingredients))):
                try:    self.layer_dict['alignment']['swim_args']['ingredient_' + str(i)] = self.ingredients[i].multi_arg_str
                except: pass
                try:    self.layer_dict['alignment']['swim_out']['ingredient_' + str(i)] = self.ingredients[i].swim_output
                except: pass
                try:    self.layer_dict['alignment']['swim_err']['ingredient_' + str(i)] = self.ingredients[i].swim_err_lines
                except: pass

        scratchlogger.critical(f'<<<< 4 >>>>')

        self.layer_dict['alignment_history'][self.cur_method].append(self.layer_dict['alignment']['method_results'])

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
        self.snr = 0.0
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

        cx = int(self.recipe.siz[0] / 2.0)
        cy = int(self.recipe.siz[1] / 2.0)
        adjust_x = '%.6f' % (cx + self.afm[0, 2])
        adjust_y = '%.6f' % (cy + self.afm[1, 2])
        afm_arg = '%.6f %.6f %.6f %.6f' % (self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1])
        rota_arg = ''

        if type(self.ww) == type((1, 2)):
            # swim_ww_arg = str(int(self.ww[0])) + "x" + str(int(self.ww[1])) #<--
            swim_ww_arg = str(int(self.ww[0])) + "x" + str(int(self.ww[1])) #<--
        else:
            swim_ww_arg = str(int(self.ww))


        iters = self.alData['swim_settings']['iterations']
        use_targ = self.alData['swim_settings']['targ']
        use_karg = self.alData['swim_settings']['karg']
        basename = os.path.basename(self.recipe.im_mov_fn)
        filename, extension = os.path.splitext(basename)

        multi_arg_str = ArgString(sep='\n')

        for i in range(len(self.psta[0])):
            scratchlogger.critical(f'Constructing {self.recipe.cur_method} [i={i}]...')

            if self.recipe.cur_method == 'grid-custom':
                if self.ID != 'Grid1x1':
                    if not self.recipe.grid_custom_regions[i]:
                        scratchlogger.critical(f'Continuing (!) [i={i}]...')
                        continue

            b_arg = os.path.join(
                self.recipe.scale_dir,
                'signals_raw',
                '%s_%s_%d%s' % (filename, self.recipe.cur_method, i, extension))
            offx = int(self.psta[0][i] - cx)
            offy = int(self.psta[1][i] - cy)
            args = ArgString(sep=' ')
            args.append('ww_' + swim_ww_arg)
            if self.alData['swim_settings']['clobber_fixed_noise']:
                args.append('-f%d' % self.alData['swim_settings']['clobber_fixed_noise_px'])
            # args.add_flag(flag='-i', arg=str(self.rcipe.iters))
            args.add_flag(flag='-i', arg=str(iters))
            args.add_flag(flag='-w', arg=str(self.recipe.wht))
            if self.recipe.cur_method not in ('manual-hint'):
                args.add_flag(flag='-x', arg=str(offx))
                args.add_flag(flag='-y', arg=str(offy))
            args.add_flag(flag='-b', arg=b_arg)
            if use_karg:
                if self.last:
                    k_arg_name = '%s_%s_k_%d%s' % (filename, self.recipe.cur_method, i, extension)
                    k_arg_path = os.path.join(self.alData['swim_settings']['karg_path'], k_arg_name)
                    args.add_flag(flag='-k', arg=k_arg_path)
            if use_targ:
                if self.last:
                    t_arg_name = '%s_%s_t_%d%s' % (filename, self.recipe.cur_method, i, extension)
                    t_arg_path = os.path.join(self.alData['swim_settings']['targ_path'], t_arg_name)
                    args.add_flag(flag='-t', arg=t_arg_path)
            args.append(self.alData['swim_settings']['extra_kwargs'])
            args.append(self.recipe.im_sta_fn)
            if self.recipe.cur_method in ('manual-hint'):
                args.append('%s %s' % (self.psta[0][i], self.psta[1][i]))
            else:
                args.append('%s %s' % (cx, cy))
            args.append(self.recipe.im_mov_fn)
            if self.recipe.cur_method in ('manual-hint'):
                args.append('%s %s' % (self.pmov[0][i], self.pmov[1][i]))
            else:
                args.append('%s %s' % (adjust_x, adjust_y))
            if abs(self.recipe.initial_rotation) > 0:
                args.append(convert_rotation(self.recipe.initial_rotation))
            args.append(afm_arg)
            args.append(self.alData['swim_settings']['extra_args'])

            multi_arg_str.append(args())

        scratchlogger.critical('Running command >>>>')

        self.multi_arg_str = multi_arg_str()

        SWIMlogger.critical(f'Multi-SWIM Argument String:\n{multi_arg_str()}')
        o = run_command(
            self.recipe.swim_c,
            arg_list=[swim_ww_arg],
            cmd_input=multi_arg_str(),
            extra=f'Automatic SWIM Alignment ({self.ID})',
        )
        scratchlogger.critical('<<<< Running command')

        self.swim_output = o['out'].strip().split('\n')
        self.swim_err_lines = o['err'].strip().split('\n')

        if self.mode == 'SWIM-Manual':
            MAlogger.critical(f'\nSWIM OUT:\n{self.swim_output}\nSWIM ERR:\n{self.swim_err_lines}')

        scratchlogger.critical(f'<<<< run_swim [{self.ID}]')

        return self.swim_output


    def ingest_swim_output(self, swim_output):

        if swim_output == '':
            self.snr = np.zeros(len(self.psta[0]))
            self.snr_report = snr_report(self.snr)
            return self.afm

        mir_script = ""
        snr_list = []
        dx = dy = 0.0
        # loop over SWIM output to build the MIR script:
        for i,l in enumerate(swim_output):
            toks = l.replace('(', ' ').replace(')', ' ').strip().split()
            self.mir_toks[i] = str(toks)
            MIRlogger.critical('MIR toks:\n %s' %self.mir_toks[i])
            if len(swim_output) == 1:
                dx = float(toks[8])
                dy = float(toks[9])
                self.dx = float(toks[8])
                self.dy = float(toks[9])
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
            else:
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
        mir_script += 'R\n'
        self.mir_script = mir_script

        o = run_command(
            self.recipe.mir_c,
            arg_list=[],
            cmd_input=mir_script,
            extra=f'MIR to get affine using SWIM output ({self.ID})',
        )

        mir_out_lines = o['out'].strip().split('\n')
        mir_err_lines = o['err'].strip().split('\n')

        MIRlogger.critical(f'***MIR script***\n{str(mir_script)}\n'
                           f'MIR std out:\n{str(mir_out_lines)}\n'
                           f'MIR std err:\n{str(mir_err_lines)}')

        if self.mode == 'SWIM-Manual':
            MAlogger.critical(f'***MIR script***\n{str(mir_script)}\n'
                              f'MIR std out:\n{str(mir_out_lines)}\n'
                              f'MIR std err:\n{str(mir_err_lines)}')

        aim = np.eye(2, 3, dtype=np.float32)

        if len(swim_output) == 1:
            aim = copy.deepcopy(self.afm)
            aim[0, 2] += dx # "what swim said, how far to move it"
            aim[1, 2] += dy
        else:
            for line in mir_out_lines:
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


if __name__ == '__main__':
    RMlogger.info("Running " + __file__ + ".__main__()")


'''
Notes:
  - mir has a -v flag for more output
  - wsf = 0.80 (Most common good value for wsf) = 0.75  (Also a good value for most projects)

'''