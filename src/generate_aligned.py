#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import src.config as cfg
from src.helpers import get_scale_key, get_scale_val, are_aligned_images_generated, \
    makedirs_exist_ok, print_exception, print_snr_list, remove_aligned, reorder_tasks
from src.mp_queue import TaskQueue
from src.image_funcs import SetStackCafm, BoundingRect, ImageSize
from src.zarr_funcs import preallocate_zarr

'''
64*64*64  = 262,144
1*512*512 = 262,144


Previous functionality was located:
regenerate_aligned()       <- alignem_swift.py
generate_aligned_images()  <- project_runner.py
'''

__all__ = ['generate_aligned']

logger = logging.getLogger(__name__)


def generate_aligned(use_scale, start_layer=0, num_layers=-1):
    '''
    This function is currently called by two MainWindow methods:
    - app.align
    - app.regenerate
    For now, start_layer is always passed the value 0, and
    num_layers is always passed the value -1.
    '''

    logger.critical('>>>>>>>> Generate Aligned Start <<<<<<<<')

    Z_STRIDE = 1
    chunks   = (cfg.CHUNK_Z, cfg.CHUNK_Y, cfg.CHUNK_X)

    JOB_FILE = 'job_apply_affine.py'
    # JOB_FILE = 'job_python_apply_affine.py'

    #TODO Add immediate check if alignment data exists and looks correct

    # image_scales_to_run = [scale_val(s) for s in sorted(cfg.data['data']['scales'].keys())]
    # proj_path = cfg.data['data']['destination_path']
    # for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #     print('Loop: scale = ', scale)
    #     scale_key = get_scale_key(scale)
    #     for i, layer in enumerate(cfg.data['data']['scales'][scale_key]['alignment_stack']):
    #         fn = os.path.abspath(layer['images']['base']['filename'])
    #         ofn = os.path.join(proj_path, scale_key, 'img_src', os.path.split(fn)[1])
    #
    #         layer['align_to_ref_method']['method_options'] = {
    #             'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION,
    #             'initial_scale': cfg.DEFAULT_INITIAL_SCALE
    #         }
    # logger.critical('cfg.DEFAULT_INITIAL_SCALE = %f' % cfg.DEFAULT_INITIAL_SCALE)
    # logger.critical('cfg.DEFAULT_INITIAL_ROTATION = %f' % cfg.DEFAULT_INITIAL_ROTATION)
    #
    # cfg.data.update_init_rot()
    # cfg.data.update_init_scale()

    path = os.path.split(os.path.realpath(__file__))[0]
    apply_affine_job = os.path.join(path, JOB_FILE)
    scale_key = get_scale_key(use_scale)
    # create_align_directories(use_scale=scale_key)
    print_snr_list()
    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %d' % get_scale_val(scale_key))
        remove_aligned(use_scale=scale_key, start_layer=start_layer)
    logger.info('Propogating AFMs to generate CFMs at each layer')
    scale_dict = cfg.data['data']['scales'][scale_key]
    null_bias = cfg.data['data']['scales'][use_scale]['null_cafm_trends']
    SetStackCafm(scale_dict=scale_dict, null_biases=null_bias)

    zarr_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr')
    bounding_rect = cfg.data.bounding_rect()
    cfg.main_window.hud.done()
    # preallocate_zarr(use_scale=use_scale, bounding_rect=bounding_rect, z_stride=16, chunks=(16,64,64))
    logger.critical('use_bounding_rect = %s' % str(bounding_rect))
    preallocate_zarr(use_scale=use_scale, bounding_rect=bounding_rect, z_stride=Z_STRIDE, chunks=chunks)

    ofn = os.path.join(cfg.data['data']['destination_path'], scale_key, 'bias_data', 'bounding_rect.dat')
    use_bounding_rect = bool(cfg.data['data']['scales'][scale_key]['use_bounding_rect'])
    logger.info('Writing Bounding Rectangle Dimensions to bounding_rect.dat...')
    with open(ofn, 'w') as f:
        if use_bounding_rect:
            logger.critical('Using bounding rect...')
            rect = BoundingRect(cfg.data['data']['scales'][scale_key]['alignment_stack'])
            f.write("%d %d %d %d\n" % (rect[0], rect[1], rect[2], rect[3]))
            # Example: rect = [-346, -346, 1716, 1716]  <class 'list'>
        else:
            logger.critical('Not using bounding rect...')
            width, height = ImageSize(cfg.data['data']['scales'][scale_key]['alignment_stack'][0]['images']['base']['filename'])
            rect = [0, 0, width, height]
            f.write("None\n")
    n_tasks = cfg.data.n_imgs()
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window)
    task_queue.tqdm_desc = 'Generating Images'
    cpus = min(psutil.cpu_count(logical=False), 48) - 1
    logger.info('Starting Task Queue...')
    task_queue.start(cpus)
    logger.info('Job Script: %s' % apply_affine_job)
    alstack = cfg.data['data']['scales'][scale_key]['alignment_stack']
    if num_layers == -1:
        end_layer = len(alstack)
    else:
        end_layer = start_layer + num_layers
    logger.info(
        '\nRunning (Example): python job_python_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name')

    args_list = []
    for ID, layer in enumerate(alstack[start_layer:end_layer + 1]):
        # These IDs are ordered correctly for Zarr indexing
        # logger.critical('generate_aligned Loop. Image: %s' % layer['images']['base']['filename'])

        zarr_grp = os.path.join(zarr_path, 's' + str(get_scale_val(use_scale)))
        zarr_args = [zarr_grp, str(ID)]

        # ID = int(sys.argv[1])    <- i
        # img = sys.argv[2]        <- NOT NEEDED (al_name)
        # src = sys.argv[3]        <- NOT NEEDED (al_name)
        # out = sys.argv[4]        <- zarr_group
        # scale_str = sys.argv[5]  <- NOT NEEDED (al_name)

        base_name = layer['images']['base']['filename']
        ref_name = layer['images']['ref']['filename']
        al_path, fn = os.path.split(base_name)
        if ID == 1:
            logger.info('\nSecond Layer (Example Paths):\nbasename = %s\nref_name = %s\nal_path = %s\nfn=%s'
                        % (base_name, ref_name, al_path, fn))
        al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = al_name
        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']

        '''New Arguments For Slotting Zarr: ID, zarr_group'''
        args = [sys.executable, apply_affine_job, '-gray', '-rect',
                str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
                str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        args.extend(zarr_args)
        # if use_bounding_rect:
        #     args = [sys.executable, apply_affine_job, '-gray', '-rect',
        #             str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
        #             str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        #     args.extend(zarr_args)
        # else:
        #     args = [sys.executable, apply_affine_job, '-gray', '-afm', str(cafm[0][0]), str(cafm[0][1]),
        #             str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        #     args.extend(zarr_args)
        if ID == 1:
            logger.info('\nSecond Layer (Example Arguments):')
            print(*args, sep="\n")
            ofn = os.path.join(cfg.data['data']['destination_path'], scale_key, 'bias_data', 'apply_affine.dat')
            logger.info('Writing Example Arguments to apply_affine.dat...')
            
            with open(ofn, 'w') as f:
                f.writelines("%s\n" % line for line in args)

        # task_queue.add_task(args)

        args_list.append(args)

    args_list = reorder_tasks(task_list=args_list, z_stride=Z_STRIDE)
    for task in args_list:
        task_queue.add_task(task)

    print_snr_list()
    logger.info('Running Apply Affine Tasks (task_queue.collect_results())...')
    t0 = time.time()
    try:
        task_queue.collect_results()
        dt = time.time() - t0
        cfg.main_window.hud.post('Image Generation Completed in %.2f seconds. Wrapping up...' % dt)
        cfg.main_window.clear_zoom()
    except:
        logger.warning('task_queue.collect_results() encountered a problem')
        print_exception()
    try: task_queue.end_tasks()
    except: pass
    task_queue.stop()
    del task_queue

    logger.critical('>>>>>>>> Generate Aligned End <<<<<<<<')


def create_align_directories(scale_key):
    source_dir = os.path.join(cfg.data['data']['destination_path'], scale_key, "img_src")
    makedirs_exist_ok(source_dir, exist_ok=True)
    target_dir = os.path.join(cfg.data['data']['destination_path'], scale_key, "img_aligned")
    makedirs_exist_ok(target_dir, exist_ok=True)
