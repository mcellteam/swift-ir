#!/usr/bin/env python3
'''


afm = affine forward matrix
aim = affine inverse matrix

o = run_command(self.swim_c, arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string) #run_command #tag
^ multi_swim_arg_string: an optional


swim_results: stdout/err get appended to this, one line for each SWIM in a multi-SWIM


'''


import os
import sys
import copy
import json
import errno
import logging
import platform
import traceback
import numpy as np
import subprocess as sp

try:     import src.config as cfg
except:  import config as cfg

try:     import src.swiftir as swiftir
except:  import swiftir

try:     from src.image_funcs import ImageSize
except:  from image_funcs import ImageSize

__all__ = ['run_json_project', 'alignment_process']

logger = logging.getLogger(__name__)

def run_json_project(project,
                     alignment_option='init_affine',
                     use_scale=0,
                     swiftir_code_mode='python',
                     start_layer=0,
                     num_layers=-1,
                     alone=False):
    '''Align one scale - either the one specified in "use_scale" or the coarsest without an AFM.
    :param project: All data data as a JSON dictionary
    :param alignment_option: This the alignment operation which can be one of three values: 'init_affine' (initializes
    the python_swiftir, normally it is run only on the coarsest scale), 'refine_affine' (refines the python_swiftir, normally is run on
    all remaining scales), and 'apply_affine' (usually never run, it forces the current python_swiftir onto any scale including
    the full scale images), defaults to 'init_affine'
    :param use_scale: The scale value to run the json data at
    :param swiftir_code_mode: This can be either 'c' or 'python', defaults to python
    :param start_layer: Layer index number to start at, defaults to 0.
    :param num_layers: The number of index layers to operate on, defaults to -1 which equals all of the images.
  
    '''
    logger.info('\n\nrun_json_project >>>>\n\n')
    logger.info("alignment_option = %s" % str(alignment_option))
    logger.info("use_scale = %s" % str(use_scale))
    logger.info("code_mode = %s" % str(swiftir_code_mode))
    logger.info("alone = %s" % str(alone))
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    # Evaluate Status of Project and set appropriate flags here:
    proj_status = evaluate_project_status(project)
    finest_scale_done = proj_status['finest_scale_done']
    allow_scale_climb = False
    upscale = 1.0  # upscale factor defaults to 1.0
    next_scale = 0
    if use_scale == 0:
        scale_tbd = proj_status['scale_tbd']  # Get scale_tbd from proj_status
        if finest_scale_done != 0:
            upscale = (float(finest_scale_done) / float(scale_tbd))  # Compute upscale factor
            next_scale = finest_scale_done
        allow_scale_climb = (finest_scale_done != 0)  # Allow scale climbing if there is a finest_scale_done
    else:
        # Force scale_tbd to be equal to use_scale
        scale_tbd = use_scale
        # Set allow_scale_climb according to statusBar of next coarser scale
        scale_tbd_idx = proj_status['defined_scales'].index(scale_tbd)
        if scale_tbd_idx < len(proj_status['defined_scales']) - 1:
            next_scale = proj_status['defined_scales'][scale_tbd_idx + 1]
            next_scale_key = 'scale_' + str(next_scale)
            upscale = (float(next_scale) / float(scale_tbd))
            allow_scale_climb = proj_status['scales'][next_scale_key]['all_aligned']

    if ((not allow_scale_climb) & (alignment_option != 'init_affine')):
        logger.warning('AlignEM SWiFT Error: Cannot perform alignment_option: %s at scale: %d' % (
            alignment_option, scale_tbd))
        logger.warning('                       Because next coarsest scale is not fully aligned')

        return (project, False)

    if scale_tbd:
        if use_scale:
            logger.info("Performing %s at predetermined scale: %d" % (alignment_option, scale_tbd))
            logger.info("Finest scale completed: %s" % str(finest_scale_done))
            logger.info("Next coarsest scale completed: %s" % str(next_scale))
            logger.info("Upscale factor: %s" % str(upscale))
        else:
            logger.info("Performing %s at automatically determined scale: %d" % (alignment_option, scale_tbd))
            logger.info("Finest scale completed: %s" % str(finest_scale_done))
            logger.info("Next coarsest scale completed: %s" % str(next_scale))
            logger.info("Upscale factor: %s" % str(upscale))

        scale_tbd_dir = os.path.join(project['data']['destination_path'], 'scale_' + str(scale_tbd))
        ident = swiftir.identityAffine()
        s_tbd = project['data']['scales']['scale_' + str(scale_tbd)]['alignment_stack']
        common_length = len(s_tbd)

        if next_scale:
            # Copy settings from next coarsest completed scale to tbd:
            #      s_done = data['data']['scales']['scale_'+str(finest_scale_done)]['alignment_stack']
            s_done = project['data']['scales']['scale_' + str(next_scale)]['alignment_stack']
            common_length = min(len(s_tbd), len(s_done))
            # Copy from coarser to finer
            num_to_copy = num_layers
            if num_layers < 0:
                num_to_copy = common_length - start_layer  # Copy to the end
            for i in range(num_to_copy):
                s_tbd[start_layer + i]['align_to_ref_method']['method_results'] = copy.deepcopy(
                    s_done[start_layer + i]['align_to_ref_method']['method_results'])

            # data['data']['scales']['scale_'+str(scale_tbd)]['alignment_stack'] = copy.deepcopy(s_done)

        actual_num_layers = num_layers
        if actual_num_layers < 0:
            # Set the actual number of layers to align_all to the end
            actual_num_layers = common_length - start_layer

        # Align Forward Change:
        range_to_process = list(range(start_layer, start_layer + actual_num_layers))
        logger.info(80 * "@")
        logger.info("Range limited to: " + str(range_to_process))
        logger.info(80 * "@")

        #   Copy skipped, swim, and match point settings
        for i in range(len(s_tbd)):
            # fix path for base and ref filenames for scale_tbd
            base_fn = os.path.basename(s_tbd[i]['images']['base']['filename'])
            s_tbd[i]['images']['base']['filename'] = os.path.join(scale_tbd_dir, 'img_src', base_fn)
            if i > 0:
                ref_fn = os.path.basename(s_tbd[i]['images']['ref']['filename'])
                s_tbd[i]['images']['ref']['filename'] = os.path.join(scale_tbd_dir, 'img_src', ref_fn)

            atrm = s_tbd[i]['align_to_ref_method']
            mr = atrm['method_results']
            md = atrm['method_data']

            # Initialize method_results for skipped or missing method_results
            logger.info("s_tbd[i]['skipped'] = %s" % str(s_tbd[i]['skipped']))
            logger.info("atrm['method_results'] == {} = %s" % str(mr == {}))
            if s_tbd[i]['skipped'] or mr == {}:
                mr['affine_matrix'] = ident.tolist()
                mr['cumulative_afm'] = ident.tolist()
                mr['snr'] = [0.0]
                mr['snr_report'] = 'SNR: --'

            # set alignment option
            md['alignment_option'] = alignment_option
            atrm['selected_method'] = 'Auto Swim Align'  # seleted_method typo

            md.setdefault('bias_x_per_image', 0)
            md.setdefault('bias_y_per_image', 0)
            md['bias_x_per_image'] *= upscale
            md['bias_y_per_image'] *= upscale
            md.setdefault('bias_rot_per_image', 0.0)
            md.setdefault('bias_scale_x_per_image', 1.0)
            md.setdefault('bias_scale_y_per_image', 1.0)
            md.setdefault('bias_skew_x_per_image', 0.0)

            logger.info('method_data\n%s' % json.dumps(atrm['method_data'], indent=2))

            # put updated atrm into s_tbd
            s_tbd[i]['align_to_ref_method'] = atrm

            # if there are match points, copy and scale them for scale_tbd
            if atrm['selected_method'] == 'Match Point Align':
                mp_ref = (np.array(s_tbd[i]['images']['ref']['metadata']['match_points']) * upscale).tolist()
                mp_base = (np.array(s_tbd[i]['images']['base']['metadata']['match_points']) * upscale).tolist()
                s_tbd[i]['images']['ref']['metadata']['match_points'] = mp_ref
                s_tbd[i]['images']['base']['metadata']['match_points'] = mp_base

        if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
            # Copy the affine_matrices from s_tbd and scale the translation part to use as the initial guess for s_tbd
            afm_tmp = np.array([al['align_to_ref_method']['method_results']['affine_matrix'] for al in s_tbd])
            logger.debug('\n>>>> Original python_swiftir matrices: \n\n')
            logger.debug(str(afm_tmp))
            afm_scaled = afm_tmp.copy()
            afm_scaled[:, :, 2] = afm_scaled[:, :, 2] * upscale
            logger.debug('\n>>> Scaled python_swiftir matrices: \n\n')
            logger.debug(str(afm_scaled))
        #      exit(0)
        else:
            afm_scaled = None

        # Now setup the alignment for s_tbd
        align_list = []
        align_dir = os.path.join(scale_tbd_dir, 'img_aligned', '')
        # make dir path for align_dir and ignore error if it already exists
        try:
            os.makedirs(align_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        for i in range(1, len(s_tbd)):
            if not s_tbd[i]['skipped']:
                #        im_sta_fn = s_tbd[i]['images']['ref']['filename']
                #        im_mov_fn = s_tbd[i]['images']['base']['filename']
                logger.info('Calling align_alignment_process >>>>')
                # from alignment_process import alignment_process
                '''refine_affine or apply_affine'''
                if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
                    atrm = s_tbd[i]['align_to_ref_method']

                    logger.info('about to enter align_alignment_process...')
                    # Align Forward Change:
                    align_proc = alignment_process(align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
                #          align_proc = alignment_process(im_sta_fn, im_mov_fn, align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
                else:
                    '''init_affine'''
                    # Align Forward Change:
                    align_proc = alignment_process(align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=ident)
                #          align_proc = alignment_process(im_sta_fn, im_mov_fn, align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=ident)
                # Align Forward Change:
                align_list.append({'i': i, 'proc': align_proc, 'do': (i in range_to_process)})

        c_afm = swiftir.identityAffine() # Initialize c_afm to identity matrix

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            logger.debug(80 * "@")
            logger.debug("Not starting at zero, initialize the c_afm to non-identity from previous aligned image")
            logger.debug(80 * "@")
            # Set the c_afm to the afm of the previously aligned image
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            prev_aligned_index = range_to_process[0] - 1
            method_results = s_tbd[prev_aligned_index]['align_to_ref_method']['method_results']
            c_afm = method_results['cumulative_afm']  # Note that this might be wrong type (list not a matrix)

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            logger.debug(80 * "@")
            logger.debug("Initialize to non-zero biases")
            logger.debug(80 * "@")

        # Calculate AFM for each align_item (i.e for each ref-base pair of images)
        for item in align_list:
            logger.info('item = %s' % str(item))

            if item['do']:
                align_item = item['proc']
                logger.debug('\nAligning: %s %s' % (
                    os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))
                # align_item.cumulative_afm = c_afm
                c_afm = align_item.align(c_afm, save=False)
            else:
                align_item = item['proc']
                logger.debug('\nNot Aligning: %s %s' % (
                    os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))

        # The code generally returns "True"
        # jy ^ which makes --> need_to_write_json = True
        logger.info('\n\n<<<< run_json_project\n\n')
        return (project, True)

    else:  # if scale_tbd:

        logger.info(30 * "|=|")
        logger.info("Returning False")
        logger.info(30 * "|=|")

        logger.info('\n\n<<<< run_json_project\n\n')
        return (project, False)


def evaluate_project_status(project):
    logger.info('Evaluating Project Status >>>>')
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
        alstack = project['data']['scales'][scale_key]['alignment_stack']
        logger.info('alstack: %s' % str(alstack))
        # Create an array of boolean values representing whether 'affine_matrix' is in the method results for each layer
        proj_status['scales'][scale_key]['aligned_stat'] = np.array(
            ['affine_matrix' in item['align_to_ref_method']['method_results'] for item in alstack])
        num_afm = np.count_nonzero(proj_status['scales'][scale_key]['aligned_stat'] == True)
        if num_afm == len(alstack):
            proj_status['scales'][scale_key]['all_aligned'] = True
            if not proj_status['finest_scale_done']:
                proj_status['finest_scale_done'] = scale  # If not yet set, we found the finest scale done
        else:
            proj_status['scales'][scale_key]['all_aligned'] = False
            proj_status['scale_tbd'] = scale  # this will always be the coarsest scale not done
    logger.info('<<<< Returning Project Status Dict')
    return proj_status

def run_command(cmd, arg_list=None, cmd_input=None):
    logger.debug("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    logger.debug("  Running command: " + str(cmd_arg_list))
    logger.debug("   Passing Data\n==========================\n" + str(cmd_input) + "==========================\n")
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    logger.debug("Command output: \n\n" + cmd_stdout + "==========================\n")
    logger.error("Command error: \n\n" + cmd_stderr + "==========================\n")
    logger.debug("=================================================\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr})


def prefix_lines(i, s):
    return ('\n'.join([i + ss.rstrip() for ss in s.split('\n') if len(ss) > 0]) + "\n")


class alignment_process:

    def __init__(self, im_sta_fn=None, im_mov_fn=None, align_dir='./', layer_dict=None, init_affine_matrix=None, cumulative_afm=None):
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
                    # "method_options": [
                    #     "Auto Swim Align",
                    #     "Match Point Align"
                    # ],
                    "method_options": {},
                    "method_data": {},
                    "method_results": {}
                }
            }
        if type(init_affine_matrix) == type(None):
            self.init_affine_matrix = swiftir.identityAffine()
        else:
            self.init_affine_matrix = init_affine_matrix
        self.cumulative_afm = swiftir.identityAffine()

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

    # TODO ============================================================
    '''#0707 NOTE: called in run_project_json'''

    def align(self, c_afm, save=True):
        logger.info('Running align_alignment_process.align_all...')
        atrm = self.layer_dict['align_to_ref_method']
        result = self.auto_swim_align(c_afm, save=save)
        return result

    def auto_swim_align(self, c_afm, save=True):
        logger.info('Running align_alignment_process.auto_swim_align...')
        siz = ImageSize(self.im_sta_fn)
        atrm = self.layer_dict['align_to_ref_method'] # (A)lign (T)o (R)ef (M)ethod
        wsf = atrm['method_data']['win_scale_factor']  #  (W)indow (S)cale (F)actor
        # dither_afm = np.array([[1., 0.005, 0.], [-0.005, 1., 0.]])

        # [
        # init_rot = self.layer_dict['align_to_ref_method']['method_options']['initial_rotation']
        # init_scale = self.layer_dict['align_to_ref_method']['method_options']['initial_scale']
        # deg2rad = 2*np.pi/360.
        # sin_rot = np.sin(deg2rad*init_rot)
        # assert isinstance(init_rot, float)
        # assert isinstance(init_scale, float)

        # dither_afm = np.array([[init_scale, sin_rot, 0.], [-sin_rot, init_scale, 0.]]) #orig
        # ]

        # dither_afm = np.array([[DITHER_SCALE, DITHER_ROT, 0.], [-DITHER_ROT, DITHER_SCALE, 0.]])
        # sin_rot -> try 0.5, DITHER_SCALE -> try 1.05 #0804

        # logger.critical('init_rot = %f' % init_rot)
        # logger.critical('init_scale = %f' % init_scale)
        # logger.critical('dither_afm: %sx' % str(dither_afm))

        # init_rot
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



        # pa = point array
        # wwx_f = window width x - full
        # sx = size x
        # wwy_f = window width y - full
        # sy = size y
        # wsf = window scaling factor (example 0.8125)
        # psta = stationary points (ref image)
        # sx_2x2 = size of windows for 2x2

        # Set up 2x2 points and windows
        nx = 2
        ny = 2
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

        # Set up 4x4 points and windows
        nx = 4
        ny = 4
        pa = np.zeros((2, nx * ny))
        sx = int(wwx_f / 4.0)  # Initial Size of each window
        sy = int(wwy_f / 4.0)  # Initial Size of each window # THIS WAS MISSING
        for x in range(nx):
            for y in range(ny):
                pa[0, x + nx * y] = int(0.5 * sx + sx * x)
                pa[1, x + nx * y] = int(0.5 * sx + sx * y)
        sx_4x4 = int(wsf * sx)
        sy_4x4 = int(wsf * sy)
        #    sx_4x4 = int(sx)
        psta_4x4 = pa

        # Set up a window size for match point alignment (1/32 of x dimension)
        s_mp = int(siz[0] / 32.0)

        logger.info("  psta_1   = " + str(psta_1))
        logger.info("  psta_2x2 = " + str(psta_2x2))
        logger.info("  psta_4x4 = " + str(psta_4x4))

        # im_sta_fn is 'ref', im_mov_fn is 'base'
        #    self.recipe = align_recipe(im_sta, im_mov, im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)
        self.recipe = align_recipe(im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn)  # tag

        wht = atrm['method_data']['whitening_factor']

        # wwx, wwy = window width
        # psta = points stationary array
        if atrm['selected_method'] == 'Auto Swim Align':
            alignment_option = atrm['method_data'].get('alignment_option')
            if alignment_option == 'refine_affine':
                '''refine_affine'''
                # ingredient_4x4 = align_ingredient(ww=int(sx_4x4), psta=psta_4x4, afm=self.init_affine_matrix, wht=wht, ad=self.align_dir)
                ingredient_4x4 = align_ingredient(ww=(int(sx_4x4), int(sy_4x4)), psta=psta_4x4, afm=self.init_affine_matrix, wht=wht, ad=self.align_dir)
                self.recipe.add_ingredient(ingredient_4x4)
                # ingredient_2x2 = align_ingredient(ww=(int(sx_2x2), int(sy_2x2)), psta=psta_2x2, afm=self.init_affine_matrix, wht=wht, ad=self.align_dir)
                # self.recipe.add_ingredient(ingredient_2x2)
            elif alignment_option == 'apply_affine':
                '''apply_affine'''
                ingredient_apply_affine = align_ingredient(afm=self.init_affine_matrix, align_mode='apply_affine_align', ad=self.align_dir)
                self.recipe.add_ingredient(ingredient_apply_affine)
            else:
                '''init_affine'''
                # ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht)  # 1x1 SWIM window
                # ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht, afm=None)  # 0721

                # ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht, afm=dither_afm, ad=self.align_dir)  # 0721 only this one has dither (1x1)
                ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht, ad=self.align_dir )  # 0721 only this one has dither (1x1)
                # ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht, ad=self.align_dir)  # 0721-
                # ingredient_2x2 = align_ingredient(ww=sx_2x2, psta=psta_2x2, wht=wht, ad=self.align_dir)
                ingredient_2x2 = align_ingredient(ww=(int(sx_2x2), int(sy_2x2)), psta=psta_2x2, wht=wht, ad=self.align_dir)
                # ingredient_4x4 = align_ingredient(ww=sx_4x4, psta=psta_4x4, wht=wht, ad=self.align_dir)
                ingredient_4x4 = align_ingredient(ww=(int(sx_4x4), int(sy_4x4)), psta=psta_4x4, wht=wht, ad=self.align_dir)
                self.recipe.add_ingredient(ingredient_1)
                self.recipe.add_ingredient(ingredient_2x2)
                self.recipe.add_ingredient(ingredient_4x4)
        elif atrm['selected_method'] == 'Match Point Align':
            # Get match points from self.layer_dict['images']['base']['metadata']['match_points']
            mp_base = np.array(self.layer_dict['images']['base']['metadata']['match_points']).transpose()
            mp_ref = np.array(self.layer_dict['images']['ref']['metadata']['match_points']).transpose()
            # First ingredient is to calculate the Affine matrix from match points alone
            ingredient_1_mp = align_ingredient(psta=mp_ref, pmov=mp_base, align_mode='match_point_align', wht=wht, ad=self.align_dir)
            # Second ingredient is to refine the Affine matrix by swimming at each match point
            ingredient_2_mp = align_ingredient(ww=s_mp, psta=mp_ref, pmov=mp_base, wht=wht, ad=self.align_dir)
            self.recipe.add_ingredient(ingredient_1_mp)  # This one will set the Affine matrix
            self.recipe.add_ingredient(ingredient_2_mp)  # This one will use the previous Affine and refine it

        ingredient_check_align = align_ingredient(ww=(wwx_f, wwy_f), psta=psta_1, iters=1, align_mode='check_align',
                                                  wht=wht)

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
        logger.debug('setCafm >>>>')
        '''Calculate new cumulative python_swiftir for current stack location'''
        self.cumulative_afm = swiftir.composeAffine(self.recipe.afm, c_afm)
        # matrix multiplication of current python_swiftir matrix with c_afm (cumulative) -jy
        # current cumulative "at this point in the stack"

        # Apply bias_mat if given
        if type(bias_mat) != type(None):
            self.cumulative_afm = swiftir.composeAffine(bias_mat, self.cumulative_afm)

        logger.debug('<<<< setCafm')
        return self.cumulative_afm

    def saveAligned(self, rect=None, apodize=False, grayBorder=False):

        logger.debug("\nsaveAligned self.cumulative_afm: " + str(self.cumulative_afm))
        im_mov = swiftir.loadImage(self.im_mov_fn)
        logger.debug("\nTransforming " + str(self.im_mov_fn))
        logger.debug(" with:")
        logger.debug("  self.cumulative_afm = " + str(self.cumulative_afm))
        logger.debug("  rect = " + str(rect))
        logger.debug("  grayBorder = " + str(grayBorder))
        im_aligned = swiftir.affineImage(self.cumulative_afm, im_mov, rect=rect, grayBorder=grayBorder)
        #      im_aligned = swiftir.affineImage(self.cumulative_afm, im_mov, rect=rect)
        ofn = os.path.join(self.align_dir, os.path.basename(self.im_mov_fn))
        logger.debug('align_swiftir | class=alignment_process | fn saveAligned | ofn =  ', ofn)

        logger.debug("  saving as: " + str(ofn))
        if apodize:
            im_apo = swiftir.apodize2(im_aligned, wfrac=1 / 3.)
            swiftir.saveImage(im_apo, ofn)
        else:
            swiftir.saveImage(im_aligned, ofn)

        # del the images to allow for automatic garbage collection
        del im_mov
        del im_aligned


# Universal class for alignment recipes
class align_recipe:
    def __init__(self, im_sta_fn=None, im_mov_fn=None):
        logger.info('align_recipe (constructor) >>>>')
        self.ingredients = []
        self.im_sta = None
        self.im_mov = None
        self.im_sta_fn = im_sta_fn
        self.im_mov_fn = im_mov_fn
        self.afm = swiftir.identityAffine()
        self.swiftir_mode = cfg.CODE_MODE
        self.siz = ImageSize(self.im_sta_fn)

        logger.info('<<<< align_recipe (constructor)')

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
        logger.info('self.swiftir_mode = ', self.swiftir_mode)

        # Load images now but only in 'python' mode. C SWiFT-IR loads its own images.
        if self.swiftir_mode == 'python':
            self.im_sta = swiftir.loadImage(self.im_sta_fn)
            self.im_mov = swiftir.loadImage(self.im_mov_fn)

        # Initialize afm to afm of first ingredient in recipe
        if self.ingredients[0].afm is not None:
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
    # def __init__(self, ww=None, psta=None, pmov=None, afm=None, wht=-0.68, iters=2, align_mode='swim_align', rota=None):
    def __init__(self, ww=None, psta=None, pmov=None, afm=None, wht=-0.68, iters=2, align_mode='swim_align', rota=None, ad=None):
        logger.info('\nalign_align_ingredient >>>>\n')

        self.swim_drift = 0.5
        self.afm = afm
        self.recipe = None
        self.ww = ww
        self.psta = psta
        self.pmov = pmov
        self.wht = wht
        self.rota = rota
        self.iters = iters
        self.align_mode = align_mode
        self.snr = None
        self.snr_report = None
        self.threshold = (3.5, 200, 200)
        self.ad=ad

        # Configure platform-specific path to executables for C SWiFT-IR
        my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        logger.info('my_path = %s' % my_path)
        self.system = platform.system()
        self.node = platform.node()
        if self.system == 'Darwin':
            self.swim_c = my_path + 'lib/bin_darwin/swim'
            self.mir_c = my_path + 'lib/bin_darwin/mir'
        elif self.system == 'Linux':
            if '.tacc.utexas.edu' in self.node:
                self.swim_c = my_path + 'lib/bin_tacc/swim'
                self.mir_c = my_path + 'lib/bin_tacc/mir'
            else:
                self.swim_c = my_path + 'lib/bin_linux/swim'
                self.mir_c = my_path + 'lib/bin_linux/mir'

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
        logger.debug(
            '%s %s : swim match:  SNR: %g  dX: %g  dY: %g' % (self.im_base, self.im_adjust, self.snr, self.dx, self.dy))

    # offx=0, offy=0, keep=None, base_x=None, base_y=None, adjust_x=None, adjust_y=None, rota=None, afm=None):
    def run_swim_c(self):
        logger.info('run_swim_c >>>>')

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
        logger.critical('afm_arg =  %s' % afm_arg)

        karg = ''
        # if keep != None:
        #  karg = '-k %s' % (keep)

        rota_arg = ''
        # if rota!=None:
        #  rota_arg = '%s' % (rota)

        swim_ww_arg = '1024'
        if type(self.ww) == type((1, 2)):
            swim_ww_arg = str(self.ww[0]) + "x" + str(self.ww[1])
        else:
            swim_ww_arg = str(self.ww)

        logger.debug("--------------------------")
        logger.debug(str(self))

        swim_results = []
        logger.debug("psta = " + str(self.psta))
        multi_swim_arg_string = ""
        #  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty rota # NOT THIS
        #  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty afm0 afm1 afm2 afm3
        # 0721 ^^ use this form to add initial rotation
        # https://github.com/mcellteam/swift-ir/blob/dd62684dd682087af5f1df15ec8ea398aa6a281e/docs/user/command_line/commands/README.md

        # kip = os.path.join(os.path.dirname(os.path.dirname(self.ad)), 'k_img.JPG')
        dir = os.path.join(os.path.dirname(os.path.dirname(self.ad))) #dir is the data directory (I think)
        kip = 'keep.JPG'
        # ' -k  ' + kip + \
        # logger.critical('kip = ' + kip)

        #                              ' -f ' +  \

        # ' -k ' + kip + \
        # ' -d ' + dir + \

        # ' -f3' + \
        for i in range(len(self.psta[0])):
            offx = int(self.psta[0][i] - (wwx_f / 2.0))
            offy = int(self.psta[1][i] - (wwy_f / 2.0))
            logger.debug("Will run a swim of " + str(self.ww) + " at (" + str(offx) + "," + str(offy) + ")")
            # swim_arg_string = 'ww_' + swim_ww_arg + \
            #                   ' -i ' + str(self.iters) + \
            #                   ' -w ' + str(self.wht) + \
            #                   ' -x ' + str(offx) + \
            #                   ' -y ' + str(offy) + \
            #                   ' ' + karg + \
            #                   ' ' + self.recipe.im_sta_fn + \
            #                   ' ' + base_x + \
            #                   ' ' + base_y + \
            #                   ' ' + self.recipe.im_mov_fn + \
            #                   ' ' + adjust_x + \
            #                   ' ' + adjust_y + \
            #                   ' ' + rota_arg + \
            #                   ' ' + afm_arg
            swim_arg_string = 'ww_' + swim_ww_arg + \
                              ' -f3 ' + \
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

            # default -f is 3x3

            logger.debug('SWIM argument string: %s' % swim_arg_string)
            multi_swim_arg_string += swim_arg_string + "\n"
            # print('\nSWIM argument string: %s\n' % multi_swim_arg_string)



        '''SWIM'''
        o = run_command(self.swim_c, arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string) #run_command #tag




        swim_out_lines = o['out'].strip().split('\n')
        swim_err_lines = o['err'].strip().split('\n')
        swim_results.append({'out': swim_out_lines, 'err': swim_err_lines})

        path = os.path.join(os.path.dirname(os.path.dirname(self.recipe.im_sta_fn)), 'swim_log.dat')
        with open(path, 'a+') as f:
            f.write('%s %s\n' % (str(swim_ww_arg), str(multi_swim_arg_string)))
            f.write('swim_stdout: \n%s\n\n' % (o['out']))
            f.write('swim_stderr: \n%s\n\n' % (o['err']))

        mir_script = ""
        snr_list = []
        dx = dy = 0.0
        # loop over SWIM output to build the MIR script:
        for l in swim_out_lines:
            if len(swim_out_lines) == 1:
                logger.info("SWIM OUT: " + str(l))
                toks = l.replace('(', ' ').replace(')', ' ').strip().split()
                dx = float(toks[8])
                dy = float(toks[9])
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                logger.info("SNR: " + str(toks[0]))
                snr_list.append(float(toks[0][0:-1]))
            else:
                logger.info("SWIM OUT: " + str(l))
                toks = l.replace('(', ' ').replace(')', ' ').strip().split()
                mir_toks = [toks[k] for k in [2, 3, 5, 6]]
                mir_script += ' '.join(mir_toks) + '\n'
                logger.info("SNR: " + str(toks[0]))
                snr_list.append(float(toks[0][0:-1]))
        mir_script += 'R\n'

        '''MIR'''
        o = run_command(self.mir_c, arg_list=[], cmd_input=mir_script)




        mir_out_lines = o['out'].strip().split('\n')
        mir_err_lines = o['err'].strip().split('\n')
        logger.info(str(mir_out_lines))
        logger.info(str(mir_err_lines))

        # Separate the results into a list of token lists
        afm = np.eye(2, 3, dtype=np.float32)
        aim = np.eye(2, 3, dtype=np.float32)

        if len(swim_out_lines) == 1:
            # aim[0, 2] = dx + 0.5 #0809
            # aim[1, 2] = dy + 0.5
            aim = copy.deepcopy(self.afm)
            aim[0, 2] += dx # "what swim said how far we're going to move it"
            aim[1, 2] += dy

            '''#TODO: may be better to add the offset to the input afm #0810'''

        else:
            for line in mir_out_lines:
                logger.info("Line: " + str(line))
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

        logger.debug("\nAIM = " + str(aim))

        if self.align_mode == 'swim_align':
            self.afm = aim

        #    if self.align_mode == 'check_align':
        #      self.snr = snr_list
        self.snr = snr_list

        logger.info('<<<< run_swim_c')
        return self.afm

    def execute(self):
        logger.info('align_ingredient.execute >>>>')

        # If ww==None then this is a Matching Point ingredient of a recipe
        # Calculate afm directly using psta and pmov as the matching points
        if self.align_mode == 'match_point_align':
            logger.info("Alignment Mode is 'Match Point Affine'")
            (self.afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
            self.ww = (0.0, 0.0)
            self.snr = np.zeros(len(self.psta[0]))
            snr_array = self.snr
            self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
                snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            return self.afm
        elif self.align_mode == 'apply_affine_align':
            logger.info("Alignment Mode is 'Apply Affine'")
            self.snr = np.zeros(1)
            snr_array = self.snr
            self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
                snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            return self.afm

        #  Otherwise, this is a swim window match ingredient
        #  Refine the afm via swim and mir
        afm = self.afm
        if afm is None:
            afm = swiftir.identityAffine()

        if self.recipe.swiftir_mode == 'c':
            afm = self.run_swim_c()
        else:
            pass
            # 0720
            logger.info("Running python version of swim")
            self.pmov = swiftir.stationaryToMoving(afm, self.psta)
            sta = swiftir.stationaryPatches(self.recipe.im_sta, self.psta, self.ww)
            for i in range(self.iters):
                logger.debug('psta = ' + str(self.psta))
                logger.debug('pmov = ' + str(self.pmov))
                mov = swiftir.movingPatches(self.recipe.im_mov, self.pmov, afm, self.ww)
                (dp, ss, snr) = swiftir.multiSwim(sta, mov, pp=self.pmov, afm=afm, wht=self.wht)
                logger.debug('  dp,ss,snr = ' + str(dp) + ', ' + str(ss) + ', ' + str(snr))
                self.pmov = self.pmov + dp
                (afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
                self.pmov = swiftir.stationaryToMoving(afm, self.psta)
                logger.debug('  Affine err:  %g' % (err))
                logger.debug('  SNR:  ' + str(snr))
            self.snr = snr

        snr_array = np.array(self.snr)
        self.snr = snr_array
        self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
            snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
        logging.info(self.snr_report)

        if self.align_mode == 'swim_align':
            self.afm = afm

        return self.afm


def align_images(im_sta_fn, im_mov_fn, align_dir, global_afm):
    logger.info('\n%%%%%%%%%%%%%%%%%%%%%%%%%%% Static Function Call to align_images %%%%%%%%%%%%%%%%%%%%%%%%%%%\n')
    if global_afm is None:
        global_afm = swiftir.identityAffine()

    im_sta = swiftir.loadImage(im_sta_fn)
    im_mov = swiftir.loadImage(im_mov_fn)

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

    global_afm = swiftir.composeAffine(recipe.afm, global_afm)
    im_aligned = swiftir.affineImage(global_afm, im_mov)
    ofn = os.path.join(align_dir, os.path.basename(im_mov_fn))
    try:
        swiftir.saveImage(im_aligned, ofn)
    except Exception:
        logger.warning(traceback.format_exc())

    return global_afm, recipe


if __name__ == '__main__':
    logger.info("Running " + __file__ + ".__main__()")

    # "Tile_r1-c1_LM9R5CA1series_247.jpg",
    # "Tile_r1-c1_LM9R5CA1series_248.jpg",

    # These are the defaults
    f1 = "vj_097_shift_rot_skew_crop_1.jpg"
    f2 = "vj_097_shift_rot_skew_crop_2.jpg"
    out = os.path.join("../../../../..", "aligned")

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
                args = args[1:]  # Shift out the dest argument

    # Now all of the remaining arguments should be optional
    xbias = 0
    ybias = 0
    match_points = None
    layer_dict = None
    cumulative_afm = None

    while len(args) > 0:
        logger.info("Current args: " + str(args))
        if args[0] == '-c':
            logger.info("Running in 'c' mode")
            global_swiftir_mode = cfg.CODE_MODE
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

    logger.debug("Creating the alignment process")
    align_proc = alignment_process(f1,
                                   f2,
                                   out,
                                   layer_dict=layer_dict,
                                   cumulative_afm=cumulative_afm)

    if cfg.CODE_MODE == 'c':
        logger.debug("Loading the images")
        if not (align_proc.recipe is None):
            if not (align_proc.recipe.ingredients is None):
                im_sta = swiftir.loadImage(f1)
                im_mov = swiftir.loadImage(f2)
                for ing in align_proc.recipe.ingredients:
                    ing.im_sta = im_sta
                    ing.im_mov = im_mov

    logger.debug("Performing the alignment")
    align_proc.align()



'''run_json_project is called by:
single_scale_job.py
    updated_model, need_to_write_json =  run_json_project(
                                         data = project_dict,
                                         alignment_option = alignment_option,
                                         use_scale = use_scale,
                                         code_mode = code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

single_alignment_job.py
   updated_model, need_to_write_json =  run_json_project(
                                         data = project_dict,
                                         alignment_option = alignment_option,
                                         use_scale = use_scale,
                                         code_mode = code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

project_runner.py
            self.updated_model, self.need_to_write_json = run_json_project(
                    data=self.data,
                    alignment_option=self.alignment_option,
                    use_scale=self.use_scale,
                    code_mode=self.code_mode,
                    start_layer=self.start_layer,
                    num_layers=self.num_layers)
            self.data = self.updated_model


swiftir.py functions:
loadImage
saveImage
affineImage # USES cv2
apodize2
mirIterate # USES cv2 (mirAffine)!
stationaryToMoving
stationaryPatches  # USES cv2 (fft)!
movingPatches  # USES cv2 (fft)!
multiSwim  #no cv2
composeAffine  #no cv2

wsf = atrm['method_data']['win_scale_factor']  # window size scale factor
#    Previously hard-coded values for wsf chosen by trial-and-error
#    wsf = 0.80  # Most common good value for wsf
#    wsf = 0.75  # Also a good value for most projects
#    wsf = 0.90
#    wsf = 1.0


'''

