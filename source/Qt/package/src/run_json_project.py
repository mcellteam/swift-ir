#!/usr/bin/env python3
### #!/usr/bin/env python2.7
# print(f'pyswift_tui.py.Loading {__name__}')

'''This is called by:
single_scale_job.py
    updated_model, need_to_write_json =  run_json_project(
                                         project = project_dict,
                                         alignment_option = alignment_option,
                                         use_scale = use_scale,
                                         code_mode = code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

single_alignment_job.py
   updated_model, need_to_write_json =  run_json_project(
                                         project = project_dict,
                                         alignment_option = alignment_option,
                                         use_scale = use_scale,
                                         code_mode = code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

project_runner.py
            self.updated_model, self.need_to_write_json = run_json_project(
                    project=self.project,
                    alignment_option=self.alignment_option,
                    use_scale=self.use_scale,
                    code_mode=self.code_mode,
                    start_layer=self.start_layer,
                    num_layers=self.num_layers)
            self.project = self.updated_model


'''
import os
import sys
import copy
import errno
import numpy as np

__all__ = ['run_json_project']

# try: import align_as align_swiftir
# except: import align_swiftir
#
# try: import as swiftir
# except: import swiftir
#
# try: import alignem_utils as em
# except: import alignem_utils as em

#----------------------------
# from utils.helpers import print_debug
# from alignem_utils import evaluate_project_status
# from ingredients.alignment_process import alignment_process
# from import *


debug_level=50

# For now, always use the limited argument version
def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
    if level <= debug_level:
        if p1 == None:
            sys.stderr.write("" + '\n')
        elif p2 == None:
            sys.stderr.write(str(p1) + '\n')
        elif p3 == None:
            sys.stderr.write(str(p1) + str(p2) + '\n')
        elif p4 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + '\n')
        elif p5 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + '\n')
        else:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + str(p5) + '\n')


def run_json_project(project,
                     alignment_option='init_affine',
                     use_scale=0,
                     swiftir_code_mode='python',
                     start_layer=0,
                     num_layers=-1,
                     alone=False):
    '''Align one scale - either the one specified in "use_scale" or the coarsest without an AFM.
    :param project: All project data as a JSON dictionary
    :param alignment_option: This the alignment operation which can be one of three values: 'init_affine' (initializes
    the affine, normally it is run only on the coarsest scale), 'refine_affine' (refines the affine, normally is run on
    all remaining scales), and 'apply_affine' (usually never run, it forces the current affine onto any scale including
    the full scale images), defaults to 'init_affine'
    :param use_scale: The scale value to run the json project at
    :param code_mode: This can be either 'c' or 'python', defaults to python
    :param start_layer: Layer index number to start at, defaults to 0.
    :param num_layers: The number of index layers to operate on, defaults to -1 which equals all of the images.

    '''
    print('run_json_project >>>>>>>>')
    print("run_json_project | alignment_option = ", alignment_option)
    print("run_json_project | use_scale = ", use_scale)
    print("run_json_project | code_mode = ", swiftir_code_mode)
    print("run_json_project | alone = ", str(alone))
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    first_layer_has_ref = False
    if project['data']['scales']['scale_%d' % use_scale]['alignment_stack'][0]['images']['ref']['filename'] != None:
        if len(project['data']['scales']['scale_%d' % use_scale]['alignment_stack'][0]['images']['ref'][
                   'filename']) > 0:
            first_layer_has_ref = True

    print_debug(20, "run_json_project | first_layer_has_ref = " + str(first_layer_has_ref))
    print_debug(20, "run_json_project | ref = \"" + str(project['data']['scales']['scale_%d' % use_scale]['alignment_stack'][0]['images']['ref']['filename']) + "\"")

    print_debug(10, 80 * "!")
    # align_global_mode = code_mode #0707

    # print('run_json_project | align_global_mode = ', align_global_mode)

    destination_path = project['data']['destination_path']

    # Evaluate Status of Project and set appropriate flags here:
    proj_status = evaluate_project_status(project)
    finest_scale_done = proj_status['finest_scale_done']
    # allow_scale_climb defaults to False
    allow_scale_climb = False
    # upscale factor defaults to 1.0
    upscale = 1.0
    next_scale = 0
    if use_scale == 0:
        # Get scale_tbd from proj_status:
        scale_tbd = proj_status['scale_tbd']
        # Compute upscale factor:
        if finest_scale_done != 0:
            upscale = (float(finest_scale_done) / float(scale_tbd))
            next_scale = finest_scale_done
        # Allow scale climbing if there is a finest_scale_done
        allow_scale_climb = (finest_scale_done != 0)
    else:
        # Force scale_tbd to be equal to use_scale
        scale_tbd = use_scale
        # Set allow_scale_climb according to status of next coarser scale
        scale_tbd_idx = proj_status['defined_scales'].index(scale_tbd)
        if scale_tbd_idx < len(proj_status['defined_scales']) - 1:
            next_scale = proj_status['defined_scales'][scale_tbd_idx + 1]
            next_scale_key = 'scale_' + str(next_scale)
            upscale = (float(next_scale) / float(scale_tbd))
            allow_scale_climb = proj_status['scales'][next_scale_key]['all_aligned']

    if ((not allow_scale_climb) & (alignment_option != 'init_affine')):
        print_debug(-1, 'run_json_project | AlignEM SWiFT Error: Cannot perform alignment_option: %s at scale: %d' % (
        alignment_option, scale_tbd))
        print_debug(-1, 'run_json_project |                        Because next coarsest scale is not fully aligned')

        return (project, False)

    if scale_tbd:
        if use_scale:
            print_debug(5,"run_json_project | Performing alignment_option: %s  at user specified scale: %d" % (alignment_option, scale_tbd))
            print_debug(5, "run_json_project | Finest scale completed: ", finest_scale_done)
            print_debug(5, "run_json_project | Next coarsest scale completed: ", next_scale)
            print_debug(5, "run_json_project | Upscale factor: ", upscale)
        else:
            print_debug(5, "run_json_project | Performing alignment_option: %s  at automatically determined scale: %d" % (
            alignment_option, scale_tbd))
            print_debug(5, "run_json_project | Finest scale completed: ", finest_scale_done)
            print_debug(5, "run_json_project | Next coarsest scale completed: ", next_scale)
            print_debug(5, "run_json_project | Upscale factor: ", upscale)

        scale_tbd_dir = os.path.join(destination_path, 'scale_' + str(scale_tbd))

        #    ident = identityAffine().tolist()
        ident = identityAffine()

        s_tbd = project['data']['scales']['scale_' + str(scale_tbd)]['alignment_stack']
        common_length = len(s_tbd)

        # Align Forward Change:
        # Limit the range of the layers based on start_layer and num_layers

        #    if finest_scale_done:
        if next_scale:
            # Copy settings from next coarsest completed scale to tbd:
            #      s_done = project['data']['scales']['scale_'+str(finest_scale_done)]['alignment_stack']
            s_done = project['data']['scales']['scale_' + str(next_scale)]['alignment_stack']
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            common_length = min(len(s_tbd), len(s_done))
            # Copy from coarser to finer
            num_to_copy = num_layers
            if num_layers < 0:
                # Copy to the end
                num_to_copy = common_length - start_layer
            for i in range(num_to_copy):
                s_tbd[start_layer + i]['align_to_ref_method']['method_results'] = copy.deepcopy(
                    s_done[start_layer + i]['align_to_ref_method']['method_results'])

            # project['data']['scales']['scale_'+str(scale_tbd)]['alignment_stack'] = copy.deepcopy(s_done)

        actual_num_layers = num_layers
        if actual_num_layers < 0:
            # Set the actual number of layers to align to the end
            actual_num_layers = common_length - start_layer

        # Align Forward Change:
        range_to_process = list(range(start_layer, start_layer + actual_num_layers))
        print_debug(10, 80 * "@")
        print_debug(10, "run_json_project | Range limited to: " + str(range_to_process))
        print_debug(10, 80 * "@")

        #   Copy skip, swim, and match point settings
        for i in range(len(s_tbd)):
            # fix path for base and ref filenames for scale_tbd
            base_fn = os.path.basename(s_tbd[i]['images']['base']['filename'])
            s_tbd[i]['images']['base']['filename'] = os.path.join(scale_tbd_dir, 'img_src', base_fn)
            if i > 0:
                ref_fn = os.path.basename(s_tbd[i]['images']['ref']['filename'])
                s_tbd[i]['images']['ref']['filename'] = os.path.join(scale_tbd_dir, 'img_src', ref_fn)

            atrm = s_tbd[i]['align_to_ref_method']

            # Initialize method_results for skipped or missing method_results
            if s_tbd[i]['skip'] or atrm['method_results'] == {}:
                atrm['method_results']['affine_matrix'] = ident.tolist()
                atrm['method_results']['cumulative_afm'] = ident.tolist()
                atrm['method_results']['snr'] = [0.0]
                atrm['method_results']['snr_report'] = 'SNR: --'

            # set alignment option
            atrm['method_data']['alignment_option'] = alignment_option
            if not 'seleted_method' in atrm:
                atrm['selected_method'] = "Auto Swim Align"

            # Upscale x & y bias values
            if 'bias_x_per_image' in atrm['method_data']:
                atrm['method_data']['bias_x_per_image'] = upscale * atrm['method_data']['bias_x_per_image']
            else:
                atrm['method_data']['bias_x_per_image'] = 0
            if 'bias_y_per_image' in atrm['method_data']:
                atrm['method_data']['bias_y_per_image'] = upscale * atrm['method_data']['bias_y_per_image']
            else:
                atrm['method_data']['bias_y_per_image'] = 0
            # TODO: handle bias values in a better way than this
            x_bias = atrm['method_data']['bias_x_per_image']
            y_bias = atrm['method_data']['bias_y_per_image']

            # check for affine biases
            # if not present then add identity matrix values to dictionary
            if 'bias_rot_per_image' in atrm['method_data'].keys():
                rot_bias = atrm['method_data']['bias_rot_per_image']
            else:
                rot_bias = 0.0
            if 'bias_scale_x_per_image' in atrm['method_data'].keys():
                scale_x_bias = atrm['method_data']['bias_scale_x_per_image']
            else:
                scale_x_bias = 1.0
            if 'bias_scale_y_per_image' in atrm['method_data'].keys():
                scale_y_bias = atrm['method_data']['bias_scale_y_per_image']
            else:
                scale_y_bias = 1.0
            if 'bias_skew_x_per_image' in atrm['method_data'].keys():
                skew_x_bias = atrm['method_data']['bias_skew_x_per_image']
            else:
                skew_x_bias = 0.0
            atrm['method_data']['bias_rot_per_image'] = rot_bias
            atrm['method_data']['bias_scale_x_per_image'] = scale_x_bias
            atrm['method_data']['bias_scale_y_per_image'] = scale_y_bias
            atrm['method_data']['bias_skew_x_per_image'] = skew_x_bias

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
            print_debug(50, '\nrun_json_project | >>>>>>> Original affine matrices: \n\n')
            print_debug(50, str(afm_tmp))
            afm_scaled = afm_tmp.copy()
            afm_scaled[:, :, 2] = afm_scaled[:, :, 2] * upscale
            print_debug(50, '\nrun_json_project | >>>>>>> Scaled affine matrices: \n\n')
            print_debug(50, str(afm_scaled))
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
            if not s_tbd[i]['skip']:
                #        im_sta_fn = s_tbd[i]['images']['ref']['filename']
                #        im_mov_fn = s_tbd[i]['images']['base']['filename']
                print('run_json_project | Calling align_alignment_process >>>>>>>>')
                from alignment_process import alignment_process
                if (alignment_option == 'refine_affine') or (alignment_option == 'apply_affine'):
                    atrm = s_tbd[i]['align_to_ref_method']

                    print('run_json_project #0707 nuggnikoms | about to enter align_alignment_process...')
                    # Align Forward Change:
                    align_proc = alignment_process(align_dir=align_dir, layer_dict=s_tbd[i],init_affine_matrix=afm_scaled[i])
                #          align_proc = alignment_process(im_sta_fn, im_mov_fn, align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=afm_scaled[i])
                else:
                    # Align Forward Change:
                    align_proc = alignment_process(align_dir=align_dir, layer_dict=s_tbd[i],init_affine_matrix=ident)
                #          align_proc = alignment_process(im_sta_fn, im_mov_fn, align_dir=align_dir, layer_dict=s_tbd[i], init_affine_matrix=ident)
                # Align Forward Change:
                align_list.append({'i': i, 'proc': align_proc, 'do': (i in range_to_process)})

        print_debug(10, 80 * "#")
        print_debug(10, "run_json_project | Before aligning, align_list: " + str(align_list))
        print_debug(10, 80 * "#")

        # Initialize c_afm to identity matrix
        c_afm = identityAffine()

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            print_debug(10, 80 * "@")
            print_debug(10, "run_json_project | Not starting at zero, initialize the c_afm to non-identity from previous aligned image")
            print_debug(10, 80 * "@")
            # Set the c_afm to the afm of the previously aligned image
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            # TODO: Check this for handling skips!!!
            prev_aligned_index = range_to_process[0] - 1
            method_results = s_tbd[prev_aligned_index]['align_to_ref_method']['method_results']
            c_afm = method_results[
                'cumulative_afm']  # Note that this might not be the right type (it's a list not a matrix)

        # Align Forward Change:
        if (range_to_process[0] != 0) and not alone:
            print_debug(10, 80 * "@")
            print_debug(10, "run_json_project | Initialize to non-zero biases")
            print_debug(10, 80 * "@")

        # Calculate AFM for each align_item (i.e for each ref-base pair of images)
        for item in align_list:

            if item['do']:
                align_item = item['proc']
                print_debug(4, '\nrun_json_project | Aligning: %s %s' % (
                os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))
                # align_item.cumulative_afm = c_afm
                c_afm = align_item.align(c_afm, save=False)
            else:
                align_item = item['proc']
                print_debug(50, '\nrun_json_project | Not Aligning: %s %s' % (
                os.path.basename(align_item.im_sta_fn), os.path.basename(align_item.im_mov_fn)))

        '''
        c_afm_init = identityAffine()

        # Compute Cafms across the stack and null trends in c_afm if requested
        # Note: This is necessarily a serial process
        null_biases = project['data']['scales']['scale_'+str(scale_tbd)]['null_cafm_trends']
        c_afm_init = SetStackCafm(s_tbd, null_biases)

        # Save analysis of bias data:
        bias_data_path = os.path.join(destination_path,'scale_'+str(scale_tbd),'bias_data')
        save_bias_analysis(s_tbd, bias_data_path)


        # Save all final aligned images:
        # Note: This should be parallelized via TaskQueue and image_apply_affine.py

        print_debug(50,"\nSaving all aligned images...\n")

        # Save possibly unmodified first image into align_dir
        im_sta_fn = s_tbd[0]['images']['base']['filename']
        base_fn = os.path.basename(im_sta_fn)
        al_fn = os.path.join(align_dir,base_fn)
        print_debug(50,"Saving first image in align dir: ", al_fn)
        im_sta = loadImage(im_sta_fn)

        rect = None
        if project['data']['scales']['scale_'+str(scale_tbd)]['use_bounding_rect']:
          siz = im_sta.shape
    #      rect = BoundingRect(align_list,siz)
          rect = BoundingRect(s_tbd)
        print_debug(10,'Bounding Rectangle: %s' % (str(rect)))

        print_debug(10,"Applying affine: " + str(c_afm_init))
        im_aligned = affineImage(c_afm_init,im_sta,rect=rect,grayBorder=True)
        del im_sta
        print_debug(10,"Saving image: " + al_fn)
        saveImage(im_aligned,al_fn)
        if not 'aligned' in s_tbd[0]['images']:
          s_tbd[0]['images']['aligned'] = {}
        s_tbd[0]['images']['aligned']['filename'] = al_fn

        i = 0
        for item in align_list:
          if item['do']:
            align_idx = item['i']
            align_item = item['proc']
            # Save the image:
            align_item.saveAligned(rect=rect, grayBorder=True)

          # Add aligned image record to layer dictionary for this stack item
            base_fn = os.path.basename(s_tbd[align_idx]['images']['base']['filename'])
            al_fn = os.path.join(align_dir,base_fn)
            s_tbd[align_idx]['images']['aligned'] = {}
            s_tbd[align_idx]['images']['aligned']['filename'] = al_fn
            s_tbd[align_idx]['images']['aligned']['metadata'] = {}
            s_tbd[align_idx]['images']['aligned']['metadata']['match_points'] = []
            s_tbd[align_idx]['images']['aligned']['metadata']['annotations'] = []

          i+=1
        '''

        print_debug(1, 30 * "|=|")
        print_debug(1, "run_json_project | Returning True")
        print_debug(1, 30 * "|=|")

        # The code generally returns "True"
        #jy ^ which makes --> need_to_write_json = True
        print('<<<<<<<< run_json_project')
        return (project, True)

    else:  # if scale_tbd:

        print_debug(1, 30 * "|=|")
        print_debug(1, "run_json_project | Returning False")
        print_debug(1, 30 * "|=|")

        print('<<<<<<<< run_json_project')
        return (project, False)

def evaluate_project_status(project):
    print('pyswift_tui.evaluate_project_status.evaluate_project_status >>>>>>>>')
    # Construct a project status dictionary (proj_status above)

    # Get int values for scales in a way compatible with old ('1') and new ('scale_1') style for keys
    scales = sorted([int(s.split('scale_')[-1]) for s in project['data']['scales'].keys()])

    proj_status = {}
    proj_status['defined_scales'] = scales
    proj_status['finest_scale_done'] = 0
    proj_status['scale_tbd'] = 0
    proj_status['scales'] = {}
    for scale in scales:
        scale_key = 'scale_' + str(scale)
        proj_status['scales'][scale_key] = {}

        alstack = project['data']['scales'][scale_key]['alignment_stack']
        # print('\nalstack:')
        # from pprint import pprint
        # pprint(alstack)

        '''
 {'align_to_ref_method': {'method_data': {'whitening_factor': -0.68,
                                          'win_scale_factor': 0.8125},
                          'method_options': ['None'],
                          'method_results': {},
                          'selected_method': 'None'},
  'images': {'base': {'filename': '/Users/joelyancey/glanceem_swift/test_projects/test9999/scale_2/img_src/R34CA1-BS12.107.tif',
                      'metadata': {'annotations': [], 'match_points': []}},
             'ref': {'filename': '/Users/joelyancey/glanceem_swift/test_projects/test9999/scale_2/img_src/R34CA1-BS12.106.tif',
                     'metadata': {'annotations': [], 'match_points': []}}},
  'skip': False},


        '''

        num_alstack = len(alstack)

        #    afm_list = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in alstack if 'affine_matrix' in i['align_to_ref_method']['method_results'] ])

        # Create an array of boolean values representing whether 'affine_matrix' is in the method results for each layer
        proj_status['scales'][scale_key]['aligned_stat'] = np.array(
                ['affine_matrix' in item['align_to_ref_method']['method_results'] for item in alstack])

        num_afm = np.count_nonzero(proj_status['scales'][scale_key]['aligned_stat'] == True)

        if num_afm == num_alstack:
            proj_status['scales'][scale_key]['all_aligned'] = True
            if not proj_status['finest_scale_done']:
                # If not yet set, we've just found the finest scale that is done
                proj_status['finest_scale_done'] = scale
        else:
            proj_status['scales'][scale_key]['all_aligned'] = False
            # Since the outer loop iterates scales from finest to coarsest,
            #   this will always be the coarsest scale not done:
            proj_status['scale_tbd'] = scale

    print('<<<<<<<< pyswift_tui.evaluate_project_status')
    return proj_status

def modelBounds2(afm, siz):
    '''MODELBOUNDS - Returns a bounding rectangle in model space
    (x0, y0, w, h) = MODELBOUNDS(afm, siz) returns the bounding rectangle
    of an input rectangle (siz) in model space if pixel lookup is through affine
    transform AFM.'''
    inv = invertAffine(afm)
    w, h = si_unpackSize(siz)
    c = [applyAffine(inv, [0, 0])]
    c = np.append(c,[applyAffine(inv, [w, 0])],axis=0)
    c = np.append(c,[applyAffine(inv, [0, h])],axis=0)
    c = np.append(c,[applyAffine(inv, [w, h])],axis=0)
    c_min = [np.floor(c[:,0].min()).astype('int32'), np.floor(c[:,1].min()).astype('int32')]
    c_max = [np.ceil(c[:,0].max()).astype('int32'), np.ceil(c[:,1].max()).astype('int32')]
    return np.array([c_min, c_max])

def identityAffine():
    '''IDENTITYAFFINE - Return an idempotent affine transform
    afm = IDENTITYAFFINE() returns an affine transform that is
    an identity transform.'''
    return np.array([[1., 0., 0.],
                     [0., 1., 0.]])

def applyAffine(afm, xy):
    '''APPLYAFFINE - Apply affine transform to a point
    xy_ = APPLYAFFINE(afm, xy) applies the affine matrix AFM to the point XY
    Affine matrix must be a 2x3 numpy array. XY may be a list or an array.'''
    if not type(xy)==np.ndarray:
        xy = np.array([xy[0], xy[1]])
    return np.matmul(afm[0:2,0:2], xy) + reptoshape(afm[0:2,2], xy)