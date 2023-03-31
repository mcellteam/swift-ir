#!/usr/bin/env python3
'''
afm = affine forward matrix
aim = affine inverse matrix
pa = point array
wwx_f = window width x - full
wwy_f = window width y - full
wsf = window scaling factor (example 0.8125)
psta = stationary points (ref image)
sx_2x2 = size of windows for 2x2

Notes:
- mir has a -v flag for more output
- wsf = 0.80 (Most common good value for wsf) = 0.75  (Also a good value for most projects)
- psta is list of x,y coordinates (points stationary array)
'''


import os
import copy
import time
import logging
import platform
import datetime
import numpy as np
import subprocess as sp

try:
    from src.funcs_image import ImageSize
except ImportError:
    from funcs_image import ImageSize

__all__ = ['run_json_project']

MAlogger      = logging.getLogger('MAlogger')
SWIMlogger    = logging.getLogger('SWIMlogger')
MIRlogger     = logging.getLogger('MIRlogger')
RMlogger      = logging.getLogger('recipemaker.log')
scratchlogger = logging.getLogger('scratch.log')


def run_json_project(project,
                     alignment_option,
                     use_scale=0,
                     start_layer=0,
                     num_layers=-1,
                     alone=False):
    '''Align one s - either the one specified in "s" or the coarsest without an AFM.
    :param project: All datamodel datamodel as a JSON dictionary
    :param alignment_option: This the alignment operation which can be one of three values: 'init_affine' (initializes
    the python_swiftir, normally it is run only on the coarsest s), 'refine_affine' (refines the python_swiftir, normally is run on
    all remaining scales), and 'apply_affine' (usually never run, it forces the current python_swiftir onto any s including
    the full s images), defaults to 'init_affine'
    :param use_scale: The s value to run the json datamodel at
    :param start_layer: Layer index number to start at, defaults to 0.
    :param num_layers: The number of index layers to operate on, defaults to -1 which equals all of the images.
    '''
    pd = project['data']['destination_path']
    MAlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'manual_align.log')))
    SWIMlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'swim.log')))
    MIRlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'mir.log')))
    RMlogger.addHandler(logging.FileHandler(os.path.join(pd, 'logs', 'recipemaker.log')))

    scratchpath = os.path.join(pd, 'logs', 'scratch.log')
    if os.path.exists(scratchpath):
        os.remove(scratchpath)
    fh = logging.FileHandler(scratchpath)
    fh.setLevel(logging.DEBUG)
    scratchlogger.addHandler(fh)

    # Evaluate Status of Project and set appropriate flags here:
    proj_status = evaluate_project_status(project)
    finest_scale_done = proj_status['finest_scale_done']
    allow_scale_climb = False
    upscale = 1.0  # upscale factor defaults to 1.0
    next_scale = 0
    scratchlogger.critical(f'use_scale = {use_scale}')
    scratchlogger.critical(f'proj_status = {proj_status}')
    if use_scale == 0:
        scale_tbd = proj_status['scale_tbd']  # Get scale_tbd from proj_status
        if finest_scale_done != 0:
            upscale = (float(finest_scale_done) / float(scale_tbd))  # Compute upscale factor
            next_scale = finest_scale_done
        allow_scale_climb = (finest_scale_done != 0)  # Allow s climbing if there is a finest_scale_done
    else:
        # Force scale_tbd to be equal to s
        scale_tbd = use_scale
        # Set allow_scale_climb according to statusBar of next coarser s
        scale_tbd_idx = proj_status['defined_scales'].index(scale_tbd)
        if scale_tbd_idx < len(proj_status['defined_scales']) - 1:
            next_scale = proj_status['defined_scales'][scale_tbd_idx + 1]
            next_scale_key = 'scale_' + str(next_scale)
            upscale = (float(next_scale) / float(scale_tbd))
            allow_scale_climb = proj_status['scales'][next_scale_key]['all_aligned']

    if scale_tbd:

        scale_tbd_dir = os.path.join(pd, 'scale_' + str(scale_tbd)) #directory -> ad variable
        ident = np.array([[1., 0., 0.], [0., 1., 0.]])
        s_tbd = project['data']['scales']['scale_' + str(scale_tbd)]['stack']
        common_length = len(s_tbd)

        if next_scale:
            # Copy settings from next coarsest completed s to tbd:
            s_done = project['data']['scales']['scale_' + str(next_scale)]['stack']
            common_length = min(len(s_tbd), len(s_done))
            # Copy from coarser to finer
            num_to_copy = num_layers
            if num_layers < 0:
                num_to_copy = common_length - start_layer  # Copy to the end
            for i in range(num_to_copy):
                s_tbd[start_layer + i]['alignment']['method_results'] = copy.deepcopy(
                    s_done[start_layer + i]['alignment']['method_results'])

            # datamodel['data']['scales']['scale_'+str(scale_tbd)]['stack'] = copy.deepcopy(s_done)

        actual_num_layers = num_layers
        if actual_num_layers < 0:
            # Set the actual number of layers to align_all to the end
            actual_num_layers = common_length - start_layer

        # Align Forward Change:
        range_to_process = list(range(start_layer, start_layer + actual_num_layers))

        #   Copy skipped, swim, and match point settings
        for i in range(len(s_tbd)):
            # fix path for base and ref filenames for scale_tbd
            base_fn = os.path.basename(s_tbd[i]['filename'])
            s_tbd[i]['filename'] = os.path.join(scale_tbd_dir, 'img_src', base_fn)
            if i > 0:
                ref_fn = os.path.basename(s_tbd[i]['reference'])
                s_tbd[i]['reference'] = os.path.join(scale_tbd_dir, 'img_src', ref_fn)

            alData = s_tbd[i]['alignment']
            mr = alData['method_results']
            md = alData['method_data']

            # Initialize method_results for skipped or missing method_results
            if s_tbd[i]['skipped'] or mr == {}:
                mr['affine_matrix'] = ident.tolist()
                mr['cumulative_afm'] = ident.tolist()
                mr['snr'] = []
                mr['snr_report'] = 'SNR: --'

            md['alignment_option'] = alignment_option
            md.setdefault('bias_x_per_image', 0)
            md.setdefault('bias_y_per_image', 0)
            md['bias_x_per_image'] *= upscale
            md['bias_y_per_image'] *= upscale
            md.setdefault('bias_rot_per_image', 0.0)
            md.setdefault('bias_scale_x_per_image', 1.0)
            md.setdefault('bias_scale_y_per_image', 1.0)
            md.setdefault('bias_skew_x_per_image', 0.0)
            s_tbd[i]['alignment'] = alData # put updated alData into s_tbd

            # if there are match points, copy and scale them for scale_tbd
            if alData['method'] in ('Manual-Hint', 'Manual-Strict'):
                mp_ref = (np.array(alData['manual_points']['ref']) * upscale).tolist()
                mp_base = (np.array(alData['manual_points']['base']) * upscale).tolist()
                alData['manual_points']['ref'] = mp_ref
                alData['manual_points']['base'] = mp_base


                mp_ref_mir = (np.array(alData['manual_points_mir']['ref']) * upscale).tolist()
                mp_base_mir = (np.array(alData['manual_points_mir']['base']) * upscale).tolist()
                alData['manual_points_mir']['ref'] = mp_ref_mir
                alData['manual_points_mir']['base'] = mp_base_mir

        if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
            # Copy the affine_matrices from s_tbd and s the translation part to use as the initial guess for s_tbd
            afm_tmp = np.array([al['alignment']['method_results']['affine_matrix'] for al in s_tbd])
            scratchlogger.critical(f'afm_tmp = {afm_tmp}')
            afm_scaled = afm_tmp.copy()
            afm_scaled[:, :, 2] = afm_scaled[:, :, 2] * upscale
        else:
            afm_scaled = None

        # Now setup the alignment for s_tbd
        align_list = []
        align_dir = os.path.join(scale_tbd_dir, 'img_aligned', '')

        # this gets run # times equal to number of images being aligned
        for i in range(1, len(s_tbd)):
            if not s_tbd[i]['skipped']:
                init_afm = afm_scaled[i] if alignment_option in ('refine_affine', 'apply_affine') else ident
                #### CALL TO align_recipe constructor ####
                align_proc = align_recipe(align_dir=align_dir, init_afm=init_afm, layer_dict=s_tbd[i], pd=pd, )
                align_list.append({'i': i, 'proc': align_proc, 'do': (i in range_to_process)})

        c_afm = np.array([[1., 0., 0.], [0., 1., 0.]]) # Initialize cafm to identity matrix

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            # "Not starting at zero, initialize the cafm to non-identity from previous aligned image"
            # Set the cafm to the afm of the previously aligned image
            # TODO: Check this for handling skips!!!
            prev_aligned_index = range_to_process[0] - 1
            method_results = s_tbd[prev_aligned_index]['alignment']['method_results']
            c_afm = method_results['cumulative_afm']  # Note that this might be wrong type (list not a matrix)

        # Calculate AFM for each align_item (i.e for each ref-base pair of images)
        scratchlogger.critical(f'align_list = {align_list}')
        for item in align_list:
            if item['do']:
                '''Only these WILL be aligned'''
                align_item = item['proc']
                # align_item.cumulative_afm = cafm
                c_afm = align_item.auto_swim_align(c_afm)

        scratchlogger.critical(f'\n\n----------\nFinal c_afm: {c_afm}\n----------\n')
        return (project, True)

    else:
        return (project, False)


def evaluate_project_status(project):
    global RMlogger

    # Get int values for scales in a way compatible with old ('1') and new ('scale_1') style for keys
    scales = sorted([int(s.split('scale_')[-1]) for s in project['data']['scales'].keys()])
    proj_status = {'defined_scales': scales,
                   'finest_scale_done': 0,
                   'scale_tbd': 0,
                   'scales': {}
                   }
    for scale in scales:
        scale_key = 'scale_' + str(scale)
        proj_status['scales'][scale_key] = {}
        alstack = project['data']['scales'][scale_key]['stack']
        # Create an array of boolean values representing whether 'affine_matrix' is in the method results for each l
        proj_status['scales'][scale_key]['aligned_stat'] = np.array(
            ['affine_matrix' in item['alignment']['method_results'] for item in alstack])
        num_afm = np.count_nonzero(proj_status['scales'][scale_key]['aligned_stat'] == True)
        if num_afm == len(alstack):
            proj_status['scales'][scale_key]['all_aligned'] = True
            if not proj_status['finest_scale_done']:
                proj_status['finest_scale_done'] = scale  # If not yet set, we found the finest s done
        else:
            proj_status['scales'][scale_key]['all_aligned'] = False
            proj_status['scale_tbd'] = scale  # this will always be the coarsest s not done

    RMlogger.critical(f'Project Status\n{proj_status}')
    return proj_status


class align_recipe:

    def __init__(self, align_dir, init_afm, layer_dict, pd, ):

        self.recipe = None
        self.ad = align_dir
        self.dest = pd
        self.init_afm = init_afm
        self.layer_dict = layer_dict
        self.im_sta_fn = self.layer_dict['reference']
        self.im_mov_fn = self.layer_dict['filename']
        self.align_mode = self.layer_dict['alignment']['method']
        self.cumulative_afm = np.array([[1., 0., 0.], [0., 1., 0.]])

        # Configure platform-specific path to executables for C SWiFT-IR
        slug = (('linux', 'darwin')[platform.system() == 'Darwin'], 'tacc')['tacc.utexas' in platform.node()]
        self.swim_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/swim'
        self.mir_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/mir'

    def __str__(self):
        s = "align_recipe: \n"
        s += "  dir: " + str(self.ad) + "\n"
        s += "  sta: " + str(self.im_sta_fn) + "\n"
        s += "  mov: " + str(self.im_mov_fn) + "\n"

    def auto_swim_align(self, c_afm):
        '''
        :param c_afm: The previous cumulative affine.
        :returns self.cumulative_affine: The new cumulative affine.
        '''

        global scratchlogger
        global MIRlogger
        global SWIMlogger
        global RMlogger
        SWIMlogger.critical(f'\n\n----------\nEntering auto_swim_align: {c_afm}\n----------\n')

        self.siz = ImageSize(self.im_sta_fn)
        alData = self.layer_dict['alignment']            # (A)lign (T)o (R)ef (M)ethod
        wsf = alData['method_data']['win_scale_factor']  # (W)indow (S)cale (F)actor
        wht = alData['method_data']['whitening_factor']

        # init_rot = self.layer_dict['alignment']['method_options']['initial_rotation']
        # init_scale = self.layer_dict['alignment']['method_options']['initial_scale']
        # deg2rad = 2*np.pi/360.
        # sin_rot = np.sin(deg2rad*init_rot)

        # Set up 1x1 point and window
        pa = np.zeros((2, 1))   # Point Array for one point
        wwx_f = self.siz[0]          # Window Width in x (Full Size)
        wwy_f = self.siz[1]          # Window Width in y (Full Size)
        wwx = int(wsf * wwx_f)  # Window Width in x Scaled
        wwy = int(wsf * wwy_f)  # Window Width in y Scaled
        cx = int(wwx_f / 2.0)   # Window Center in x
        cy = int(wwy_f / 2.0)   # Window Center in y
        pa[0, 0] = cx
        pa[1, 0] = cy
        psta_1 = pa

        # Set up 2x2 points and windows
        nx, ny = 2, 2
        pa = np.zeros((2, nx * ny))  # Point Array (2x4) points
        sx = int(wwx_f / 2.0)  # Initial Size of each window
        sy = int(wwy_f / 2.0)  # Initial Size of each window
        for x in range(nx):
            for y in range(ny):
                pa[0, x + nx * y] = int(0.5 * sx + sx * x)  # Point Array (2x4) points
                pa[1, x + nx * y] = int(0.5 * sy + sy * y)  # Point Array (2x4) points
        sx_2x2 = int(wsf * sx)
        sy_2x2 = int(wsf * sy)
        psta_2x2 = pa

        self.ingredients = []
        self.afm = np.array([[1., 0., 0.], [0., 1., 0.]])

        option = alData['method_data'].get('alignment_option')

        if option == 'init_affine':
            if alData['method'] == 'Auto-SWIM':
                '''Number of SWIMs is equal to number of points in list of SWIM windows (e.g. psta_1)'''
                ingredient_1    = align_ingredient(mode='SWIM', iters=3, ww=(wwx, wwy), psta=psta_1, wht=wht, ID='ingr1_1x1_')
                ingredient_2x2  = align_ingredient(mode='SWIM', iters=3, ww=(sx_2x2, sy_2x2), psta=psta_2x2, wht=wht, ID='ingr2_2x2_')
                ingredient_2x2b = align_ingredient(mode='SWIM', iters=3, ww=(sx_2x2, sy_2x2), psta=psta_2x2, wht=wht, ID='ingr3_2x2_')
                self.add_ingredients([ingredient_1, ingredient_2x2, ingredient_2x2b])
            elif alData['method'] == 'Manual-Hint':
                pmov = np.array(alData['manual_points_mir']['base']).transpose()
                psta = np.array(alData['manual_points_mir']['ref']).transpose()
                s_mp = alData['manual_settings'].get('swim_window_px')  # size match point
                ingredient_1_mp   = align_ingredient(mode='Manual-Hint', ww=s_mp, psta=psta, pmov=pmov, wht=wht, ID='ingr1_hint_')
                ingredient_2_mp   = align_ingredient(mode='SWIM-Manual', iters=3, ww=s_mp, psta=psta, pmov=pmov, wht=wht, ID='ingr2_SWIM_')
                ingredient_2_mp_b = align_ingredient(mode='SWIM-Manual', iters=3, ww=s_mp, psta=psta, pmov=pmov, wht=wht, ID='ingr3_SWIM_')
                self.add_ingredients([ingredient_1_mp, ingredient_2_mp, ingredient_2_mp_b])  # further refinement
            elif alData['method'] == 'Manual-Strict':
                pmov = np.array(alData['manual_points_mir']['base']).transpose()
                psta = np.array(alData['manual_points_mir']['ref']).transpose()
                ingredient_1_mp = align_ingredient(mode='Manual-Strict', psta=psta, pmov=pmov, wht=wht )
                self.add_ingredients([ingredient_1_mp])
        elif option == 'refine_affine':
            if alData['method'] == 'Auto-SWIM':
                # self.init_afm - result from previous alignment at coarser scale
                ingredient_2x2 = align_ingredient(mode='SWIM', ww=(sx_2x2, sy_2x2), psta=psta_2x2, afm=self.init_afm, wht=wht, ID='_2x2')
                self.add_ingredients([ingredient_2x2])
            elif alData['method'] == 'Manual-Hint':
                pmov = np.array(alData['manual_points_mir']['base']).transpose()
                psta = np.array(alData['manual_points_mir']['ref']).transpose()
                s_mp = alData['manual_settings'].get('swim_window_px')  # size match point
                ingredient_1_mp   = align_ingredient(mode='Manual-Hint', ww=s_mp, psta=psta, pmov=pmov, wht=wht, ID='ingr1_hint_r_')
                ingredient_2_mp   = align_ingredient(mode='SWIM', iters=3, ww=s_mp, psta=psta, pmov=pmov, wht=wht, ID='ingr2_SWIM_r_')
                ingredient_2_mp_b = align_ingredient(mode='SWIM', iters=3, ww=s_mp, psta=psta, pmov=pmov, wht=wht, ID='ingr3_SWIM_r_')
                self.add_ingredients([ingredient_1_mp, ingredient_2_mp, ingredient_2_mp_b])
            elif alData['method'] == 'Manual-Strict':
                pmov            = np.array(alData['manual_points_mir']['base']).transpose()
                psta            = np.array(alData['manual_points_mir']['ref']).transpose()
                ingredient_1_mp = align_ingredient(mode='Manual-Strict', psta=psta, pmov=pmov, wht=wht)
                self.add_ingredients([ingredient_1_mp])  # This one will set the Affine matrix

        self.execute()
        # Retrieve alignment result
        snr = self.ingredients[-1].snr
        snr_report = self.ingredients[-1].snr_report
        afm = self.ingredients[-1].afm
        c_afm = self.cumulative_afm

        SWIMlogger.critical('Loading results into project dictionary...')
        alData['method_results']['snr'] = list(snr)
        alData['method_results']['snr_report'] = snr_report
        alData['method_results']['affine_matrix'] = afm.tolist()
        alData['method_results']['cumulative_afm'] = c_afm.tolist()
        alData['method_results']['swim_pos'] = self.ingredients[-1].psta.tolist()
        alData['method_data']['bias_x_per_image'] = 0
        alData['method_data']['bias_y_per_image'] = 0
        alData['method_data']['bias_rot_per_image'] = 0
        alData['method_data']['bias_scale_x_per_image'] = 1
        alData['method_data']['bias_scale_y_per_image'] = 1
        alData['method_data']['bias_skew_x_per_image'] = 0
        alData['mir_toks'] = self.ingredients[-1].mir_toks
        alData['method_results']['datetime'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        SWIMlogger.critical('\n\n----------\nExiting auto_swim_align: {c_afm}\n----------\n')
        return self.cumulative_afm


    def add_ingredients(self, ingredients):
        for ingredient in ingredients:
            self.add_ingredient(ingredient)

    def add_ingredient(self, ingredient):
        SWIMlogger.critical('Adding Ingredient...')
        ingredient.recipe = self
        ingredient.alData = self.layer_dict['alignment']
        self.ingredients.append(ingredient)

    def execute(self):
        SWIMlogger.critical('Executing Recipe...')
        # Initialize afm to afm of first ingredient in recipe
        if self.ingredients[0].afm is not None:
            self.afm = self.ingredients[0].afm
        # Execute each ingredient in recipe
        for ingredient in self.ingredients:
            ingredient.afm = self.afm
            self.afm = ingredient.execute()



class align_ingredient:
    '''
    Universal class for alignment ingredients of recipes

    Ingredients come in 3 main types where the type is determined by value of align_mode
    1)  If align_mode is 'manual-align' then this is a Matching Point ingredient
        We calculate the afm directly using psta and pmov as the matching points
    2)  If align_mode is 'swim_align' then this is a swim window matching ingredient
        ww and psta specify the size and location of windows in im_sta
        and corresponding windows (pmov) are contructed from psta and projected onto im_mov
        from which image matching is performed to estimate or refine the afm.
        If psta contains only one point then the estimated afm will be a translation matrix
    3) If align_mode is 'check_align' then use swim to check the SNR achieved by the
        supplied afm matrix but do not refine the afm matrix
    '''
    def __init__(self, mode, ww=None, psta=None, pmov=None, afm=None, wht=-0.68, iters=3, rota=None, ID=''):
        self.recipe = None
        self.alData = None
        self.ingredient_mode = mode
        self.swim_drift = 0.0
        self.afm = afm
        self.ww = ww
        self.psta = psta
        self.pmov = pmov
        self.wht = wht
        self.rota = rota
        self.iters = iters # Only used by SWIM
        self.snr = None
        self.snr_report = None
        self.threshold = (3.5, 200, 200)
        self.mir_toks = {}
        self.ID=ID

    def __str__(self):
        s = "ingredient:\n"
        s += "  mode: " + str(self.ingredient_mode) + "\n"
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


    def execute(self):
        # Returns an affine matrix
        if self.ingredient_mode == 'Manual-Hint':
            self.afm = self.run_manual_mir()
        elif self.ingredient_mode == 'Manual-Strict':
            self.afm = self.run_manual_mir()
        else:
            swim_output = self.run_swim()
            self.afm = self.ingest_swim_output(swim_output)
        return self.afm


    def run_swim(self):
        scratchlogger.critical('Running Swim........')
        wwx_f = self.recipe.siz[0]  # Window Width in x (Full Size)
        wwy_f = self.recipe.siz[1]  # Window Width in y (Full Size)
        cx, cy = int(wwx_f / 2.0), int(wwy_f / 2.0)
        adjust_x = '%.6f' % (cx + self.afm[0, 2])
        adjust_y = '%.6f' % (cy + self.afm[1, 2])
        afm_arg = '%.6f %.6f %.6f %.6f' % (self.afm[0, 0], self.afm[0, 1], self.afm[1, 0], self.afm[1, 1])
        rota_arg = ''
        if type(self.ww) == type((1, 2)):
            swim_ww_arg = str(int(self.ww[0])) + "x" + str(int(self.ww[1]))
        else:
            swim_ww_arg = str(int(self.ww))
        swim_results = []
        multi_swim_arg_string = ""
        scale_dir = os.path.abspath(os.path.dirname(os.path.dirname(self.recipe.ad)))
        SWIMlogger.critical('Constructing SWIM string........')
        for i in range(len(self.psta[0])):
            b_arg = os.path.join(scale_dir, 'corr_spots', 'corr_spot_%d_' %i + os.path.basename(self.recipe.im_mov_fn))
            offx = int(self.psta[0][i] - (wwx_f / 2.0))
            offy = int(self.psta[1][i] - (wwy_f / 2.0))
            swim_arg_string  = 'ww_' + swim_ww_arg
            if self.alData['swim_settings']['clobber_fixed_noise']:
                swim_arg_string += ' -f%d ' % self.alData['swim_settings']['clobber_fixed_noise_px']
            swim_arg_string += ' -i ' + str(self.iters)
            swim_arg_string += ' -w ' + str(self.wht)
            if self.ingredient_mode != 'SWIM-Manual':
                swim_arg_string += ' -x ' + str(offx)
                swim_arg_string += ' -y ' + str(offy)
            swim_arg_string += ' -b ' + b_arg
            if self.alData['swim_settings']['karg']:
                k_arg_name = 'pt%d_' %i + self.ID + self.alData['swim_settings']['karg_name'] + '.tif'
                k_arg_path = os.path.join(self.alData['swim_settings']['karg_path'], k_arg_name)
                swim_arg_string += f" -k {k_arg_path}"
            if self.alData['swim_settings']['targ']:
                t_arg_name = 'pt%d_' %i + self.ID +  self.alData['swim_settings']['targ_name'] + '.tif'
                t_arg_path = os.path.join(self.alData['swim_settings']['targ_path'], t_arg_name)
                swim_arg_string += f" -t {t_arg_path}"
            swim_arg_string += self.alData['swim_settings']['extra_kwargs']
            swim_arg_string += ' ' + self.recipe.im_sta_fn
            if self.ingredient_mode == 'SWIM-Manual':
                swim_arg_string += ' ' + str(self.psta[0][i])
                swim_arg_string += ' ' + str(self.psta[1][i])
            else:
                swim_arg_string += ' ' + str(cx)
                swim_arg_string += ' ' + str(cy)
            swim_arg_string += ' ' + self.recipe.im_mov_fn
            if self.ingredient_mode == 'SWIM-Manual':
                swim_arg_string += ' ' + str(self.pmov[0][i])
                swim_arg_string += ' ' + str(self.pmov[1][i])
            else:
                swim_arg_string += ' ' + adjust_x
                swim_arg_string += ' ' + adjust_y
            swim_arg_string += ' ' + rota_arg
            swim_arg_string += ' ' + afm_arg
            swim_arg_string += self.alData['swim_settings']['extra_args']

            multi_swim_arg_string += swim_arg_string + "\n"
        SWIMlogger.critical(f'multi_swim_arg_string:\n{multi_swim_arg_string}')
        o = run_command(self.recipe.swim_c, arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string)

        swim_output = o['out'].strip().split('\n')
        swim_err_lines = o['err'].strip().split('\n')
        swim_results.append({'out': swim_output, 'err': swim_err_lines})

        if self.ingredient_mode in ('Manual-Hint', 'Manual-Strict'):
            MAlogger.critical(f'SWIM OUT:\n{swim_output}\n'
                              f'SWIM ERR:\n{swim_err_lines}')

        RMlogger.critical('<<<< Returning SWIM Output')
        return swim_output


    def ingest_swim_output(self, swim_output):
        scratchlogger.critical(f'\nIngesting SWIM output:\n{swim_output}\n')

        mir_script = ""
        snr_list = []
        dx = dy = 0.0
        # loop over SWIM output to build the MIR script:
        for i,l in enumerate(swim_output):
            MIRlogger.critical('SWIM Out Line # %d: '%i + str(l))
            toks = l.replace('(', ' ').replace(')', ' ').strip().split()
            self.mir_toks[i] = str(toks)
            MIRlogger.critical('MIR toks:\n %s' %self.mir_toks[i])
            if len(swim_output) == 1:
                dx = float(toks[8])
                dy = float(toks[9])
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
            else:
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                snr_list.append(float(toks[0][0:-1]))
        mir_script += 'R\n'

        o = run_command(self.recipe.mir_c, arg_list=[], cmd_input=mir_script)

        mir_out_lines = o['out'].strip().split('\n')
        mir_err_lines = o['err'].strip().split('\n')

        MIRlogger.critical(f'***MIR script***\n{str(mir_script)}\n'
                           f'MIR std out:\n{str(mir_out_lines)}\n'
                           f'MIR std err:\n{str(mir_err_lines)}')

        if self.ingredient_mode in ('Manual-Hint', 'Manual-Strict'):
            MAlogger.critical(f'***MIR script***\n{str(mir_script)}\n'
                              f'MIR std out:\n{str(mir_out_lines)}\n'
                              f'MIR std err:\n{str(mir_err_lines)}')

        # Separate the results into a list of token lists
        aim = np.eye(2, 3, dtype=np.float32)

        if len(swim_output) == 1:
            # simple translation, skip MIR, directly adjust AFM
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

        o = run_command(self.recipe.mir_c, arg_list=[], cmd_input=mir_script_mp)
        mir_mp_out_lines = o['out'].strip().split('\n')
        mir_mp_err_lines = o['err'].strip().split('\n')
        MAlogger.critical(f'\n============================================================\n'
                          f'MIR script:\n{mir_script_mp}\n'
                          f'manual mir Out:\n{mir_mp_out_lines}\n\n'
                          f'manual mir Err:\n{mir_mp_err_lines}\n'
                          f'============================================================')

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

        self.snr = np.zeros(len(self.psta[0]))
        self.snr_report = snr_report(self.snr)
        return afm



def run_command(cmd, arg_list=None, cmd_input=None):
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    nl = '\n'
    RMlogger.critical(f"\n================== Run Command ==================\n"
                      f"Running command :\n{nl.join(cmd_arg_list)}\n"
                      f"Passing data    :\n{cmd_input}"
                      f"=================================================\n")
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    RMlogger.critical(f"\n===================== Output ====================\n"
                      f"Command output  : {cmd_stdout}\n"
                      f"Command error   : {cmd_stderr}\n"
                      f"=================================================\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr})


def prefix_lines(i, s):
    return ('\n'.join([i + ss.rstrip() for ss in s.split('\n') if len(ss) > 0]) + "\n")

def snr_report(arr) -> str:
    return 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (arr.mean(), arr.std(), len(arr), arr.min(), arr.max())


if __name__ == '__main__':
    RMlogger.info("Running " + __file__ + ".__main__()")



