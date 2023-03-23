#!/usr/bin/env python3
'''


afm = affine forward matrix
aim = affine inverse matrix
pa = point array
wwx_f = window width x - full
sx = size x
wwy_f = window width y - full
sy = size y
wsf = window scaling factor (example 0.8125)
psta = stationary points (ref image)
sx_2x2 = size of windows for 2x2

o = run_command(self.swim_c, arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string) #run_command #tag
^ multi_swim_arg_string: an optional


swim_results: stdout/err get appended to this, one line for each SWIM in a multi-SWIM

mir has a -v flag for more output

# default -f is 3x3


'''


import os
import sys
import copy
import json
import errno
import logging
import platform
import datetime
import traceback
import numpy as np
import subprocess as sp

try:     import src.swiftir as swiftir
except:  import swiftir

try:     from src.funcs_image import ImageSize
except:  from funcs_image import ImageSize

__all__ = ['run_json_project', 'alignment_process']

logger = logging.getLogger(__name__)
MAlogger = logging.getLogger('MAlogger')
swimLogger = logging.getLogger('swimLogger')


def run_json_project(project,
                     alignment_option='init_affine',
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


    fh = logging.FileHandler(os.path.join(project['data']['destination_path'], 'logs', 'logger.log'))
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    logger.critical(f'run_json_project option:{alignment_option}, {str(use_scale)}, '
                    f'start: {start_layer}, num layers: {num_layers}>>>>')
    fh = logging.FileHandler(os.path.join(project['data']['destination_path'], 'logs', 'manual_align.log'))
    fh.setLevel(logging.DEBUG)
    MAlogger.addHandler(fh)

    swimLogger = logging.getLogger('swimLogger')
    # if (swimLogger.hasHandlers()):
    #     logger.info('Clearing swimLogger file handlers...')
    #     swimLogger.handlers.clear()
    swimLogger.propagate = False
    fh = logging.FileHandler(os.path.join(project['data']['destination_path'], 'logs', 'swim.log'))
    fh.setLevel(logging.DEBUG)
    swimLogger.addHandler(fh)

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

        scale_tbd_dir = os.path.join(project['data']['destination_path'], 'scale_' + str(scale_tbd)) #directory -> ad variable
        ident = swiftir.identityAffine()
        s_tbd = project['data']['scales']['scale_' + str(scale_tbd)]['stack']
        common_length = len(s_tbd)

        if next_scale:
            # Copy settings from next coarsest completed s to tbd:
            # s_done = datamodel['data']['scales']['scale_'+str(finest_scale_done)]['stack']
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

            atrm = s_tbd[i]['alignment']
            mr = atrm['method_results']
            md = atrm['method_data']

            # Initialize method_results for skipped or missing method_results
            if s_tbd[i]['skipped'] or mr == {}:
                mr['affine_matrix'] = ident.tolist()
                mr['cumulative_afm'] = ident.tolist()
                mr['snr'] = []
                mr['snr_report'] = 'SNR: --'

            md['alignment_option'] = alignment_option

            # atrm['method'] = 'Auto-SWIM' #0205-

            md.setdefault('bias_x_per_image', 0)
            md.setdefault('bias_y_per_image', 0)
            md['bias_x_per_image'] *= upscale
            md['bias_y_per_image'] *= upscale
            md.setdefault('bias_rot_per_image', 0.0)
            md.setdefault('bias_scale_x_per_image', 1.0)
            md.setdefault('bias_scale_y_per_image', 1.0)
            md.setdefault('bias_skew_x_per_image', 0.0)
            s_tbd[i]['alignment'] = atrm # put updated atrm into s_tbd

            # if there are match points, copy and scale them for scale_tbd
            if atrm['method'] in ('Manual-Hint', 'Manual-Strict'):
                mp_ref = (np.array(atrm['manual_points_mir']['ref']) * upscale).tolist()
                mp_base = (np.array(atrm['manual_points_mir']['base']) * upscale).tolist()
                atrm['manual_points_mir']['ref'] = mp_ref
                atrm['manual_points_mir']['base'] = mp_base

        if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
            # Copy the affine_matrices from s_tbd and s the translation part to use as the initial guess for s_tbd
            afm_tmp = np.array([al['alignment']['method_results']['affine_matrix'] for al in s_tbd])
            logger.debug('\n>>>> Original python_swiftir matrices: \n\n')
            logger.debug(str(afm_tmp))
            afm_scaled = afm_tmp.copy()
            afm_scaled[:, :, 2] = afm_scaled[:, :, 2] * upscale
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
                if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
                    '''refine_affine or apply_affine'''
                    logger.info('about to enter align_alignment_process...')
                    align_proc = alignment_process(
                        align_dir=align_dir,
                        layer_dict=s_tbd[i],
                        init_affine_matrix=afm_scaled[i],
                        dest=project['data']['destination_path'],
                    )
                else:
                    '''init_affine'''
                    align_proc = alignment_process(
                        align_dir=align_dir,
                        layer_dict=s_tbd[i],
                        init_affine_matrix=ident,
                        dest=project['data']['destination_path'],
                    )
                align_list.append({'i': i, 'proc': align_proc, 'do': (i in range_to_process)})

        c_afm = swiftir.identityAffine() # Initialize cafm to identity matrix

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            logger.debug(80 * "@")
            logger.debug("Not starting at zero, initialize the cafm to non-identity from previous aligned image")
            logger.debug(80 * "@")
            # Set the cafm to the afm of the previously aligned image
            # TODO: Check this for handling skips!!!
            prev_aligned_index = range_to_process[0] - 1
            method_results = s_tbd[prev_aligned_index]['alignment']['method_results']
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
                # align_item.cumulative_afm = cafm
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
        alstack = project['data']['scales'][scale_key]['stack']
        logger.info('stack: %s' % str(alstack))
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
    logger.info('<<<< Returning Project Status Dict')
    return proj_status

def run_command(cmd, arg_list=None, cmd_input=None):
    logger.debug("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    logger.info("  Running command: " + str(cmd_arg_list))
    logger.info("   Passing Data\n==========================\n" + str(cmd_input) + "==========================\n")
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    logger.info("Command output: \n\n" + cmd_stdout + "==========================\n")
    logger.error("Command error: \n\n" + cmd_stderr + "==========================\n")
    logger.info("=================================================\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr})


def prefix_lines(i, s):
    return ('\n'.join([i + ss.rstrip() for ss in s.split('\n') if len(ss) > 0]) + "\n")


class alignment_process:

    def __init__(self, im_sta_fn=None,
                 im_mov_fn=None,
                 align_dir='./',
                 layer_dict=None,
                 init_affine_matrix=None,
                 cumulative_afm=None,
                 dest=None,
                 ):

        self.recipe = None
        self.im_sta_fn = im_sta_fn
        self.im_mov_fn = im_mov_fn
        self.align_dir = align_dir
        self.dest = dest
        self.mp_ref = None
        self.mp_base = None
        # self.align_mode = 'Auto-SWIM'

        if layer_dict != None:
            self.layer_dict = layer_dict
            self.im_sta_fn = self.layer_dict['reference']
            self.im_mov_fn = self.layer_dict['filename']

            self.align_mode = self.layer_dict['alignment']['method']


        else:
            self.layer_dict = {
                "images": {
                    "ref": {"filename": im_sta_fn},
                    "base": {"filename": im_mov_fn}
                },
                "alignment": {
                    "method": "Auto-SWIM",
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
        atrm = self.layer_dict['alignment']
        result = self.auto_swim_align(c_afm, save=save)
        return result

    def auto_swim_align(self, c_afm, save=True):
        MAlogger.info('Running align_alignment_process.auto_swim_align...')
        siz = ImageSize(self.im_sta_fn)
        atrm = self.layer_dict['alignment'] # (A)lign (T)o (R)ef (M)ethod
        # wsf = atrm['method_data']['win_scale_factor']  #  (W)indow (S)cale (F)actor
        wsf = atrm['method_data']['win_scale_factor']
        wht = atrm['method_data']['whitening_factor']
        # dither_afm = np.array([[1., 0.005, 0.], [-0.005, 1., 0.]])

        # init_rot = self.layer_dict['alignment']['method_options']['initial_rotation']
        # init_scale = self.layer_dict['alignment']['method_options']['initial_scale']
        # deg2rad = 2*np.pi/360.
        # sin_rot = np.sin(deg2rad*init_rot)
        # assert isinstance(init_rot, float)
        # assert isinstance(init_scale, float)

        # dither_afm = np.array([[init_scale, sin_rot, 0.], [-sin_rot, init_scale, 0.]]) #orig
        # dither_afm = np.array([[DITHER_SCALE, DITHER_ROT, 0.], [-DITHER_ROT, DITHER_SCALE, 0.]])
        # sin_rot -> try 0.5, DITHER_SCALE -> try 1.05 #0804

        #    wsf = 0.80  # Most common good value for wsf
        #    wsf = 0.75  # Also a good value for most projects

        # Set up 1x1 point and window
        pa = np.zeros((2, 1))   # Point Array for one point
        wwx_f = siz[0]          # Window Width in x (Full Size)
        wwy_f = siz[1]          # Window Width in y (Full Size)
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

        # Set up 4x4 points and windows
        # nx, ny = 4, 4
        # pa = np.zeros((2, nx * ny))
        # sx = int(wwx_f / 4.0)  # Initial Size of each window
        # sy = int(wwy_f / 4.0)  # Initial Size of each window # THIS WAS MISSING
        # for x in range(nx):
        #     for y in range(ny):
        #         pa[0, x + nx * y] = int(0.5 * sx + sx * x)
        #         pa[1, x + nx * y] = int(0.5 * sx + sx * y)
        # sx_4x4 = int(wsf * sx)
        # sy_4x4 = int(wsf * sy)
        # #    sx_4x4 = int(sx)
        # psta_4x4 = pa

        # Set up a window size for match point alignment (1/32 of x dimension)
        # s_mp = int(siz[0] / 32.0) # size match point #orig
        # s_mp = 128 # size match point
        # s_mp = 128 # size match point
        s_mp = atrm['manual_settings'].get('swim_window_px')

        logger.critical("  psta_1   = " + str(psta_1))
        logger.critical("  psta_2x2 = " + str(psta_2x2))
        logger.critical("  wwx_f = " + str(wwx_f))
        logger.critical("  wwy_f = " + str(wwy_f))
        logger.critical("  wwx = " + str(wwx))
        logger.critical("  wwy = " + str(wwy))

        self.recipe = align_recipe(im_sta_fn=self.im_sta_fn, im_mov_fn=self.im_mov_fn, dest=self.dest) # Call to align_recipe

        # wwx, wwy = window width
        # psta = points stationary array
        #build #recipe #addingredients #ingredients

        fn = os.path.basename(self.layer_dict['filename'])

        # clobber = atrm['manual_settings'].get(['fixed_pattern_clobber'])
        # clobber_arg =

        if atrm['method'] == 'Auto-SWIM':
            alignment_option = atrm['method_data'].get('alignment_option')
            MAlogger.critical('\n%s (Method: Auto-SWIM, Option: %s)...' % (fn, alignment_option))

            if alignment_option == 'refine_affine':
                '''refine_affine'''
                # self.init_affine_matrix - result from previous alignment at coarser scale
                # ingredient_4x4 = align_ingredient(ww=int(sx_4x4), psta=psta_4x4, afm=self.init_affine_matrix, wht=wht, ad=self.align_dir)
                # ingredient_4x4 = align_ingredient(ww=(int(sx_4x4), int(sy_4x4)), psta=psta_4x4, afm=self.init_affine_matrix, wht=wht, ad=self.align_dir)
                # self.recipe.add_ingredient(ingredient_4x4)
                ingredient_2x2 = align_ingredient(mode='SWIM',name=self.im_mov_fn, ww=(int(sx_2x2), int(sy_2x2)), psta=psta_2x2, afm=self.init_affine_matrix, wht=wht, ad=self.align_dir)
                self.recipe.add_ingredient(ingredient_2x2)
            elif alignment_option == 'apply_affine':
                '''apply_affine'''
                ingredient_apply_affine = align_ingredient(name=self.im_mov_fn, afm=self.init_affine_matrix, mode='apply_affine_align', ad=self.align_dir)
                self.recipe.add_ingredient(ingredient_apply_affine)
            else:
                '''init_affine'''
                '''Number of SWIMs is equal to number of points in list of SWIM windows (e.g. psta_1)'''
                '''psta_1 is list of x,y coordinates'''
                # ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht)  # 1x1 SWIM window
                # ingredient_1 = align_ingredient(ww=(wwx, wwy), psta=psta_1, wht=wht, afm=dither_afm, ad=self.align_dir)
                ingredient_1 = align_ingredient(mode='SWIM', name=self.im_mov_fn, ww=(wwx, wwy), psta=psta_1, wht=wht, ad=self.align_dir, dest=self.dest)
                # ingredient_2x2 = align_ingredient(ww=sx_2x2, psta=psta_2x2, wht=wht, ad=self.align_dir)
                ingredient_2x2 = align_ingredient(mode='SWIM', name=self.im_mov_fn, ww=(int(sx_2x2), int(sy_2x2)), psta=psta_2x2, wht=wht, ad=self.align_dir, dest=self.dest)
                ingredient_2x2b = align_ingredient(mode='SWIM', name=self.im_mov_fn, ww=(int(sx_2x2), int(sy_2x2)), psta=psta_2x2, wht=wht, ad=self.align_dir, dest=self.dest)
                # ingredient_4x4 = align_ingredient(ww=(int(sx_4x4), int(sy_4x4)), psta=psta_4x4, wht=wht, ad=self.align_dir)
                self.recipe.add_ingredient(ingredient_1)
                self.recipe.add_ingredient(ingredient_2x2)
                self.recipe.add_ingredient(ingredient_2x2b)
                # self.recipe.add_ingredient(ingredient_4x4)
        elif atrm['method'] == 'Manual-Hint':
            MAlogger.critical('\n%s (Method: Manual-Hint)...' % fn)
            self.mp_base = np.array(self.layer_dict['alignment']['manual_points_mir']['base']).transpose()
            self.mp_ref = np.array(self.layer_dict['alignment']['manual_points_mir']['ref']).transpose()

            # logger.critical('Manual Points (base):\n%s' % str(self.mp_base))
            # logger.critical('Manual Points (ref):\n%s' % str(self.mp_ref))
            # MAlogger.critical('Manual Points (base):\n%s' % str(self.mp_base))
            # MAlogger.critical('Manual Points (ref):\n%s' % str(self.mp_ref))
            # First ingredient is to calculate the Affine matrix from match points alone
            # ingredient_1_mp = align_ingredient(psta=mp_ref, pmov=mp_base, align_mode='manual_align', wht=wht, ad=self.align_dir, dest=self.dest)
            # ingredient_1_mp = align_ingredient(name=self.im_mov_fn, ww=s_mp, psta=self.mp_ref, pmov=self.mp_base, align_mode='manual_align', wht=wht, ad=self.align_dir, dest=self.dest)
            ingredient_1_mp = align_ingredient(mode='Manual-Hint',name=self.im_mov_fn, ww=s_mp, psta=self.mp_ref, pmov=self.mp_base, wht=wht, ad=self.align_dir, dest=self.dest)
            # Second ingredient is to refine the Affine matrix by swimming at each match point
            ingredient_2_mp = align_ingredient(mode='SWIM', name=self.im_mov_fn, ww=s_mp, psta=self.mp_ref, pmov=self.mp_base, wht=wht, ad=self.align_dir, dest=self.dest) # <-- CALL TO SWIM
            ingredient_2_mp_b = align_ingredient(mode='SWIM', name=self.im_mov_fn, ww=s_mp, psta=self.mp_ref, pmov=self.mp_base, wht=wht, ad=self.align_dir, dest=self.dest) #0221+
            self.recipe.add_ingredient(ingredient_1_mp)  # This one will set the Affine matrix
            self.recipe.add_ingredient(ingredient_2_mp)  # This one will use the previous Affine and refine it
            self.recipe.add_ingredient(ingredient_2_mp_b)  # This one will use the previous Affine and refine it #0221+
            # self.recipe.add_ingredient(ingredient_4x4)
        elif atrm['method'] == 'Manual-Strict':
            MAlogger.critical('\n%s (Method: Manual-Strict)...' % fn)
            self.mp_base = np.array(self.layer_dict['alignment']['manual_points_mir']['base']).transpose()
            self.mp_ref = np.array(self.layer_dict['alignment']['manual_points_mir']['ref']).transpose()
            # self.mp_base[1][:] = self.size - self.mp_base[1][:]
            # self.mp_ref[1][:] = self.size - self.mp_ref[1][:]
            # ingredient_1_mp = align_ingredient(name=self.im_mov_fn, psta=self.mp_ref, pmov=self.mp_base, align_mode='manual_align', wht=wht, ad=self.align_dir, dest=self.dest)
            ingredient_1_mp = align_ingredient(mode='Manual-Strict',name=self.im_mov_fn, psta=self.mp_ref, pmov=self.mp_base, wht=wht, ad=self.align_dir, dest=self.dest)
            self.recipe.add_ingredient(ingredient_1_mp)  # This one will set the Affine matrix


        # ingredient_check_align = \
        #     align_ingredient(ww=(wwx_f, wwy_f), psta=psta_1, iters=1, align_mode='check_align', wht=wht)
        # self.recipe.add_ingredient(ingredient_check_align)

        self.recipe.execute()  # DOES the alignment
        self.setCafm(c_afm, bias_mat=None)  # returns new current cafm
        logger.critical('c_afm = %s' % str(c_afm))

        # Retrieve alignment result
        snr = self.recipe.ingredients[-1].snr
        snr_report = self.recipe.ingredients[-1].snr_report
        afm = self.recipe.ingredients[-1].afm
        c_afm = self.cumulative_afm

        # Put alignment results into layer_dict
        atrm['method_results']['snr'] = list(snr)
        atrm['method_results']['snr_report'] = snr_report
        # if self.mp_ref is not None:
        #     atrm['method_results']['mp_ref'] = self.mp_ref.tolist()
        # if self.mp_base is not None:
        #     atrm['method_results']['mp_base'] = self.mp_base.tolist()
        atrm['method_results']['snr_report'] = snr_report
        atrm['method_results']['affine_matrix'] = afm.tolist()
        atrm['method_results']['cumulative_afm'] = c_afm.tolist()
        atrm['method_results']['swim_str'] = self.recipe.ingredients[-1].swim_str
        atrm['method_results']['mir_script'] = self.recipe.ingredients[-1].mir_script
        atrm['method_results']['swim_pos'] = self.recipe.ingredients[-1].psta.tolist()
        if self.recipe.ingredients[0].mir_script_mp:
            atrm['method_results']['mir_script_mp'] = self.recipe.ingredients[0].mir_script_mp
        if self.recipe.ingredients[0].mir_mp_out_lines:
            atrm['method_results']['mir_mp_out_lines'] = self.recipe.ingredients[0].mir_mp_out_lines
        if self.recipe.ingredients[0].mir_mp_err_lines:
            atrm['method_results']['mir_mp_err_lines'] = self.recipe.ingredients[0].mir_mp_err_lines
        atrm['method_results']['swim_out_lines'] = self.recipe.ingredients[-1].swim_out_lines
        atrm['method_results']['swim_err_lines'] = self.recipe.ingredients[-1].swim_err_lines
        atrm['method_data']['bias_x_per_image'] = 0
        atrm['method_data']['bias_y_per_image'] = 0
        atrm['method_data']['bias_rot_per_image'] = 0
        atrm['method_data']['bias_scale_x_per_image'] = 0
        atrm['method_data']['bias_scale_y_per_image'] = 0
        atrm['method_data']['bias_skew_x_per_image'] = 0
        atrm['mir_toks'] = self.recipe.ingredients[-1].mir_toks

        current_time = datetime.datetime.now()
        atrm['method_results']['datetime'] = current_time.strftime('%Y-%m-%d %H:%M:%S')

        if save:
            self.saveAligned()

        return self.cumulative_afm

    def setCafm(self, c_afm, bias_mat=None):
        logger.debug('setCafm >>>>')
        '''Calculate new cumulative python_swiftir for current stack location'''
        self.cumulative_afm = swiftir.composeAffine(self.recipe.afm, c_afm)
        # matrix multiplication of current python_swiftir matrix with cafm (cumulative) -jy
        # current cumulative "at this point in the stack"

        # Apply bias_mat if given
        if type(bias_mat) != type(None):
            self.cumulative_afm = swiftir.composeAffine(bias_mat, self.cumulative_afm)

        return self.cumulative_afm

    def saveAligned(self, rect=None, apodize=False, grayBorder=False):
        im_mov = swiftir.loadImage(self.im_mov_fn)
        im_aligned = swiftir.affineImage(self.cumulative_afm, im_mov, rect=rect, grayBorder=grayBorder)
        #      im_aligned = swiftir.affineImage(self.cumulative_afm, im_mov, rect=rect)
        ofn = os.path.join(self.align_dir, os.path.basename(self.im_mov_fn))
        if apodize:
            im_apo = swiftir.apodize2(im_aligned, wfrac=1 / 3.)
            swiftir.saveImage(im_apo, ofn)
        else:
            swiftir.saveImage(im_aligned, ofn)
        del im_mov
        del im_aligned


# Universal class for alignment recipes
class align_recipe:
    def __init__(self, im_sta_fn=None, im_mov_fn=None, dest=None):
        self.ingredients = []
        self.im_sta = None
        self.im_mov = None
        self.im_sta_fn = im_sta_fn
        self.im_mov_fn = im_mov_fn
        self.afm = swiftir.identityAffine()
        self.swiftir_mode = 'c'
        self.siz = ImageSize(self.im_sta_fn)
        self.dest = dest

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
        # Initialize afm to afm of first ingredient in recipe
        if self.ingredients[0].afm is not None:
            self.afm = self.ingredients[0].afm

        # Execute each ingredient in recipe
        for ingredient in self.ingredients:
            ingredient.afm = self.afm
            self.afm = ingredient.execute()

        del self.im_sta
        del self.im_mov


# Universal class for alignment ingredients of recipes
class align_ingredient:
    '''Initialized with paths to mir/swim'''
    # Constructor for ingredient of a recipe
    # Ingredients come in 3 main types where the type is determined by value of align_mode
    #   1) If align_mode is 'manual-align' then this is a Matching Point ingredient
    #        We calculate the afm directly using psta and pmov as the matching points
    #   2) If align_mode is 'swim_align' then this is a swim window matching ingredient
    #        ww and psta specify the size and location of windows in im_sta
    #        and corresponding windows (pmov) are contructed from psta and projected onto im_mov
    #        from which image matching is performed to estimate or refine the afm.
    #        If psta contains only one point then the estimated afm will be a translation matrix
    #   3) If align_mode is 'check_align' then use swim to check the SNR achieved by the
    #        supplied afm matrix but do not refine the afm matrix
    def __init__(self,
                 mode='SWIM', name=None, ww=None, psta=None, pmov=None, afm=None, wht=-0.68,
                 iters=2, rota=None, ad=None, dest=None, ):
        self.ingredient_mode = mode
        self.name = os.path.basename(name)
        self.swim_drift = 0.0
        self.afm = afm
        self.recipe = None
        self.ww = ww
        self.psta = psta
        self.pmov = pmov
        self.wht = wht
        self.rota = rota
        self.iters = iters
        self.snr = None
        self.snr_report = None
        self.threshold = (3.5, 200, 200)
        self.ad = ad
        self.swim_str = None
        self.mir_script = None
        self.mir_script_mp = None
        self.mir_mp_out_lines = None
        self.mir_mp_err_lines = None
        self.swim_out_lines = None
        self.swim_err_lines = None
        self.dest = dest
        self.mir_toks = {}


        # Configure platform-specific path to executables for C SWiFT-IR
        slug = (('linux', 'darwin')[platform.system() == 'Darwin'], 'tacc')['tacc.utexas' in platform.node()]
        self.swim_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/swim'
        self.mir_c = f'{os.path.split(os.path.realpath(__file__))[0]}/lib/bin_{slug}/mir'

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

    # offx=0, offy=0, keep=None, base_x=None, base_y=None, adjust_x=None, adjust_y=None, rota=None, afm=None):
    def run_swim_c(self):
        ''' Returns the affine matrix '''
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
        rota_arg = ''
        if type(self.ww) == type((1, 2)):
            swim_ww_arg = str(self.ww[0]) + "x" + str(self.ww[1])
        else:
            swim_ww_arg = str(self.ww)
        swim_results = []
        multi_swim_arg_string = ""

        scale_dir = os.path.abspath(os.path.dirname(os.path.dirname(self.ad))) # self.ad = project/scale_X/img_aligned/

        # k_arg = os.path.join(scale_dir, 'keep_' + os.path.basename(self.recipe.im_mov_fn))
        # t_arg = os.path.join(scale_dir, 'target_' + os.path.basename(self.recipe.im_mov_fn))

        #  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty rota # NOT THIS
        #  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty afm0 afm1 afm2 afm3
        #0721 ^initial rotation form of SWIM

        for i in range(len(self.psta[0])):
            b_arg = os.path.join(scale_dir, 'corr_spots', 'corr_spot_%d_' %i + os.path.basename(self.recipe.im_mov_fn))
            offx = int(self.psta[0][i] - (wwx_f / 2.0))
            offy = int(self.psta[1][i] - (wwy_f / 2.0))
            logger.critical("Will run a swim of " + str(self.ww) + " at (" + str(offx) + "," + str(offy) + ")")
            #                   ' -k ' + k_arg + \
            #                   ' -t ' + t_arg + \
            #                   ' ' + karg + \
            swim_arg_string = 'ww_' + swim_ww_arg + \
                              ' -f3 ' + \
                              ' -i ' + str(self.iters) + \
                              ' -w ' + str(self.wht) + \
                              ' -x ' + str(offx) + \
                              ' -y ' + str(offy) + \
                              ' -b ' + b_arg + \
                              ' ' + self.recipe.im_sta_fn + \
                              ' ' + base_x + \
                              ' ' + base_y + \
                              ' ' + self.recipe.im_mov_fn + \
                              ' ' + adjust_x + \
                              ' ' + adjust_y + \
                              ' ' + rota_arg + \
                              ' ' + afm_arg
            # swim_arg_string = 'ww_' + swim_ww_arg + \
            #                   ' -i ' + str(self.iters) + \
            #                   ' -w ' + str(self.wht) + \
            #                   ' -x ' + str(offx) + \
            #                   ' -y ' + str(offy) + \
            #                   ' -b ' + b_arg + \
            #                   ' ' + self.recipe.im_sta_fn + \
            #                   ' ' + base_x + \
            #                   ' ' + base_y + \
            #                   ' ' + self.recipe.im_mov_fn + \
            #                   ' ' + adjust_x + \
            #                   ' ' + adjust_y + \
            #                   ' ' + rota_arg + \
            #                   ' ' + afm_arg

            # default -f is 3x3
            # logger.critical('SWIM argument string: %s' % swim_arg_string)
            multi_swim_arg_string += swim_arg_string + "\n"

        swimLogger.log('multi_swim_arg_string:\n{multi_swim_arg_string}\n\n')

        '''SWIM'''
        self.swim_str = multi_swim_arg_string
        o = run_command(self.swim_c, arg_list=[swim_ww_arg], cmd_input=multi_swim_arg_string)


        MAlogger.critical(f'INGREDIENT MODE : {self.ingredient_mode}')
        if self.ingredient_mode in ('Manual-Hint', 'Manual-Strict'):
            MAlogger.critical('SWIM argument string: %s' % self.swim_str)
            MAlogger.critical('SWIM argument string: %s' % self.swim_str)
            MAlogger.critical('\nSWIM stdout: %s' % str(self.swim_out_lines))
            # MAlogger.info('swim_err_lines\n %s' % str(self.swim_out_lines))

        self.swim_out_lines = swim_out_lines = o['out'].strip().split('\n')
        self.swim_err_lines = swim_err_lines = o['err'].strip().split('\n')
        swim_results.append({'out': swim_out_lines, 'err': swim_err_lines})




        mir_script = ""
        snr_list = []
        dx = dy = 0.0
        # loop over SWIM output to build the MIR script:


        # Example mir_toks
        # "['5.64383:',
        # '/Users/joelyancey/glanceem_swift/test_projects/testProj/scale_4/img_src/R34CA1-BS12.105.tif',
        # '770',
        # '687',
        # '/Users/joelyancey/glanceem_swift/test_projects/testProj/scale_4/img_src/R34CA1-BS12.106.tif',
        # '779.132',
        # '679.697',
        # '0.994905',
        # '0.019098',
        # '-0.003263',
        # '0.99511',
        # '7.37415',
        # '-4.39514',
        # '8.5846']"


        for i,l in enumerate(swim_out_lines):
            MAlogger.critical('SWIM Out Line # %d: '%i + str(l))
            toks = l.replace('(', ' ').replace(')', ' ').strip().split()
            self.mir_toks[i] = str(toks)
            MAlogger.critical('MIR toks:\n %s' %self.mir_toks[i])
            if len(swim_out_lines) == 1:
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

        '''MIR'''
        self.mir_script = mir_script
        o = run_command(self.mir_c, arg_list=[], cmd_input=mir_script)

        mir_out_lines = o['out'].strip().split('\n')
        mir_err_lines = o['err'].strip().split('\n')

        if self.ingredient_mode in ('Manual-Strict', 'Manual-Hint'):
            MAlogger.critical('***MIR script***\n' + str(self.mir_script))
            MAlogger.critical('\nMIR std out: %s\n' % str(mir_out_lines))
            MAlogger.critical('\nMIR std err: %s\n' % str(mir_err_lines))

        # Separate the results into a list of token lists
        afm = np.eye(2, 3, dtype=np.float32)
        aim = np.eye(2, 3, dtype=np.float32)

        if len(swim_out_lines) == 1:
            # simple translation, skip MIR, directly adjust AFM
            aim = copy.deepcopy(self.afm)
            aim[0, 2] += dx # "what swim said, how far to move it"
            aim[1, 2] += dy

            #TODO: may be better to add the offset to the input afm #0810

        else:
            ''' Extract AFM from these lines:
            AF  0.939259 0.0056992 6.42837  -0.0344578 1.00858 36.085
            AI  1.06445 -0.00601489 -6.62562  0.0363665 0.991285 -36.0043 '''
            for line in mir_out_lines:
                logger.info("Line: " + str(line))
                toks = line.strip().split()

                if (toks[0] == 'AF'):
                    afm[0, 0] = float(toks[1])
                    afm[0, 1] = float(toks[2])
                    afm[0, 2] = float(toks[3]) - self.swim_drift
                    afm[1, 0] = float(toks[4])
                    afm[1, 1] = float(toks[5])
                    afm[1, 2] = float(toks[6]) - self.swim_drift
                if (toks[0] == 'AI'):
                    aim[0, 0] = float(toks[1])
                    aim[0, 1] = float(toks[2])
                    aim[0, 2] = float(toks[3]) + self.swim_drift
                    aim[1, 0] = float(toks[4])
                    aim[1, 1] = float(toks[5])
                    aim[1, 2] = float(toks[6]) + self.swim_drift

        logger.debug("\nAIM = " + str(aim))

        if self.ingredient_mode == 'SWIM':
            self.afm = aim

        #    if self.align_mode == 'check_align':
        #      self.snr_report = snr_list
        self.snr = snr_list

        logger.info('<<<< run_swim_c')
        return self.afm

    def execute(self):
        '''RETURN AN AFFINE MATRIX'''

        '''---------------------------------NEW -------------------------------------'''
        #0214
        if self.ingredient_mode in ('Manual-Hint', 'Manual-Strict'):
            mir_script_mp = ''
            for i in range(len(self.psta[0])):
                mir_script_mp += f'{self.psta[0][i]} {self.psta[1][i]} {self.pmov[0][i]} {self.pmov[1][i]}\n'

            mir_script_mp += 'R'
            self.mir_script_mp = mir_script_mp

            MAlogger.critical('\nMIR script:\n' + self.mir_script_mp)
            o = run_command(self.mir_c, arg_list=[], cmd_input=mir_script_mp)
            mir_mp_out_lines = o['out'].strip().split('\n')
            mir_mp_err_lines = o['err'].strip().split('\n')
            self.mir_mp_out_lines = mir_mp_out_lines
            self.mir_mp_err_lines = mir_mp_err_lines
            MAlogger.critical('\n(MANUAL ALIGN: %s) MIR out: %s' % (self.name, str(mir_mp_out_lines)))
            MAlogger.critical('\n(MANUAL ALIGN: %s) MIR err: %s' % (self.name, str(mir_mp_err_lines)))

            afm = np.eye(2, 3, dtype=np.float32)
            self.ww = (0.0, 0.0)

            '''Extract AFM from these lines:
            AF  0.939259 0.0056992 6.42837  -0.0344578 1.00858 36.085
            AI  1.06445 -0.00601489 -6.62562  0.0363665 0.991285 -36.0043'''

            for line in mir_mp_out_lines:
                logger.info("Line: " + str(line))
                toks = line.strip().split()
                # if (toks[0] == 'AF'):
                if (toks[0] == 'AI'):
                    afm[0, 0] = float(toks[1])
                    afm[0, 1] = float(toks[2])
                    afm[0, 2] = float(toks[3])
                    afm[1, 0] = float(toks[4])
                    afm[1, 1] = float(toks[5])
                    afm[1, 2] = float(toks[6])

            self.afm = afm
            self.snr = np.zeros(len(self.psta[0]))
            snr_array = self.snr
            self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
                snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            # logger.critical('AFM:\n' + str(afm))
            # logger.critical('snr_report:\n' + self.snr_report)
            return self.afm
            '''------------------------------ END NEW ----------------------------------'''

        #NOTE made this conditional #2014+
        else:
            #0205-
            # # If ww==None then this is a Matching Point ingredient of a recipe
            # # Calculate afm directly using psta and pmov as the matching points
            # if self.align_mode == 'match_point_align':
            #     logger.info("Alignment Mode is 'Match Point Affine'")
            #     (self.afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
            #     self.ww = (0.0, 0.0)
            #     self.snr = np.zeros(len(self.psta[0]))
            #     snr_array = self.snr
            #     self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
            #         snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            #     return self.afm
            # elif self.align_mode == 'apply_affine_align':
            #     logger.info("Alignment Mode is 'Apply Affine'")
            #     self.snr = np.zeros(1)
            #     snr_array = self.snr
            #     self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
            #         snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            #     return self.afm

            #  Otherwise, this is a swim window match ingredient
            #  Refine the afm via swim and mir
            # afm = self.afm
            # if afm is None:
            #     afm = swiftir.identityAffine()

            afm = self.run_swim_c()

            # if self.recipe.swiftir_mode == 'c':
            #     afm = self.run_swim_c()
            # else:
            #     pass
            #     # 0720
            #     logger.info("Running python version of swim")
            #     self.pmov = swiftir.stationaryToMoving(afm, self.psta)
            #     sta = swiftir.stationaryPatches(self.recipe.im_sta, self.psta, self.ww)
            #     for i in range(self.iters):
            #         logger.debug('psta = ' + str(self.psta))
            #         logger.debug('pmov = ' + str(self.pmov))
            #         mov = swiftir.movingPatches(self.recipe.im_mov, self.pmov, afm, self.ww)
            #         (dp, ss, snr) = swiftir.multiSwim(sta, mov, pp=self.pmov, afm=afm, wht=self.wht)
            #         logger.debug('  dp,ss,snr_report = ' + str(dp) + ', ' + str(ss) + ', ' + str(snr))
            #         self.pmov = self.pmov + dp
            #         (afm, err, n) = swiftir.mirIterate(self.psta, self.pmov)
            #         self.pmov = swiftir.stationaryToMoving(afm, self.psta)
            #         logger.debug('  Affine err:  %g' % (err))
            #         logger.debug('  SNR:  ' + str(snr))
            #     self.snr = snr

            snr_array = np.array(self.snr)
            self.snr = snr_array
            self.snr_report = 'SNR: %.1f (+-%.1f n:%d)  <%.1f  %.1f>' % (
                snr_array.mean(), snr_array.std(), len(snr_array), snr_array.min(), snr_array.max())
            logging.info(self.snr_report)

            if self.ingredient_mode == 'SWIM':
                self.afm = afm

            return self.afm


def align_images(im_sta_fn, im_mov_fn, align_dir, global_afm):
    logger.info('\n%%%% Static Function Call to align_images %%%%\n')
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

    CODE_MODE = 'c'

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

                # Build the l dictionary with the match points
                layer_dict = {
                    "images": {
                        "base": {
                            "metadata": {
                                "manual_points": match_points[0]
                            }
                        },
                        "ref": {
                            "metadata": {
                                "manual_points": match_points[1]
                            }
                        }
                    },
                    "alignment": {
                        "selected_method": "Match Point Align",
                        "method_options": [
                            "Auto-SWIM",
                            "Manual-Hint",
                            "Manual-Strict"
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

    if CODE_MODE == 'c':
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
                                         datamodel = project_dict,
                                         alignment_option = alignment_option,
                                         s = s,
                                         code_mode = code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

single_alignment_job.py
   updated_model, need_to_write_json =  run_json_project(
                                         datamodel = project_dict,
                                         alignment_option = alignment_option,
                                         s = s,
                                         code_mode = code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

project_runner.py
            self.updated_model, self.need_to_write_json = run_json_project(
                    datamodel=self.datamodel,
                    alignment_option=self.alignment_option,
                    s=self.s,
                    code_mode=self.code_mode,
                    start_layer=self.start_layer,
                    num_layers=self.num_layers)
            self.datamodel = self.updated_model


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

wsf = atrm['method_data']['win_scale_factor']  # window size s factor
#    Previously hard-coded values for wsf chosen by trial-and-error
#    wsf = 0.80  # Most common good value for wsf
#    wsf = 0.75  # Also a good value for most projects
#    wsf = 0.90
#    wsf = 1.0


'''

