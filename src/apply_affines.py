#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import src.config as cfg

from .em_utils import get_scale_key, get_scale_val, get_cur_scale_key, are_aligned_images_generated, \
    makedirs_exist_ok, print_exception, get_num_imported_images, print_snr_list, remove_aligned
from .mp_queue import TaskQueue
from .image_utils import SetStackCafm, BoundingRect
from .save_bias_analysis import save_bias_analysis

'''
Previous functionality was located:
regenerate_aligned()       <- alignem_swift.py
generate_aligned_images()  <- project_runner.py

'''

__all__ = ['generate_aligned']

logger = logging.getLogger(__name__)


def generate_aligned(use_scale, start_layer=0, num_layers=-1):
    '''
    This function is currently called by two MainWindow methods:
    - app.run_alignment
    - app.run_regenerate_alignment
    For now, start_layer is always passed the value 0, and
    num_layers is always passed the value -1.
    '''
    logger.critical('>>>>>>>> Generate Aligned Start <<<<<<<<')
    
    '''NEED AN IMMEDIATE CHECK RIGHT HERE TO SEE IF ALIGNMENT DATA EVEN EXISTS AND LOOKS CORRECT'''

    # image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.project_data['data']['scales'].keys())]
    # proj_path = cfg.project_data['data']['destination_path']
    # for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #     print('Loop: scale = ', scale)
    #     scale_key = get_scale_key(scale)
    #     for i, layer in enumerate(cfg.project_data['data']['scales'][scale_key]['alignment_stack']):
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
    # cfg.project_data.update_init_rot()
    # cfg.project_data.update_init_scale()

    logger.info('Generating Aligned Images...')
    scale_key = get_scale_key(use_scale)
    # create_align_directories(use_scale=scale_key)
    print_snr_list()
    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %s' % scale_key[-1])
        remove_aligned(use_scale=scale_key, start_layer=start_layer)
    logger.info('Propogating AFMs to generate CFMs at each layer')
    scale_dict = cfg.project_data['data']['scales'][scale_key]
    null_bias = cfg.project_data['data']['scales'][get_cur_scale_key()]['null_cafm_trends']
    SetStackCafm(scale_dict=scale_dict, null_biases=null_bias)
    ofn = os.path.join(cfg.project_data['data']['destination_path'], scale_key, 'bias_data', 'bounding_rect.dat')
    use_bounding_rect = bool(cfg.project_data['data']['scales'][scale_key]['use_bounding_rect'])
    logger.info('Writing Bounding Rectangle Dimensions to bounding_rect.dat...')
    with open(ofn, 'w') as f:
        if use_bounding_rect:
            rect = BoundingRect(cfg.project_data['data']['scales'][scale_key]['alignment_stack'])
            f.write("%d %d %d %d\n" % (rect[0], rect[1], rect[2], rect[3]))
        else:
            f.write("None\n")
    logger.info('Constructing TaskQueue...')
    n_tasks = get_num_imported_images()
    cfg.main_window.pbar_max(n_tasks)
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window)
    task_queue.tqdm_desc = 'Generating Images'
    cpus = min(psutil.cpu_count(logical=False), 48)
    logger.info('Starting TaskQueue...')
    task_queue.start(cpus)
    path = os.path.split(os.path.realpath(__file__))[0]
    apply_affine_job = os.path.join(path, 'job_apply_affine.py')
    logger.info('Job Script: %s' % apply_affine_job)
    alstack = cfg.project_data['data']['scales'][scale_key]['alignment_stack']
    if num_layers == -1:
        end_layer = len(alstack)
    else:
        end_layer = start_layer + num_layers
    logger.info(
        '\nRunning (Example): python job_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name')
    for i, layer in enumerate(alstack[start_layer:end_layer + 1]):
        base_name = layer['images']['base']['filename']
        ref_name = layer['images']['ref']['filename']
        al_path, fn = os.path.split(base_name)
        if i == 1 or i == 5:
            logger.info('\nSecond Layer (Example Paths):\nbasename = %s\nref_name = %s\nal_path = %s\nfn=%s'
                        % (base_name, ref_name, al_path, fn))
        al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = al_name
        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']
        if use_bounding_rect:
            args = [sys.executable, apply_affine_job, '-gray', '-rect',
                    str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
                    str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        else:
            args = [sys.executable, apply_affine_job, '-gray', '-afm', str(cafm[0][0]), str(cafm[0][1]),
                    str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        if i == 1:
            logger.info('\nSecond Layer (Example Arguments):')
            print(*args, sep="\n")
            
            ofn = os.path.join(cfg.project_data['data']['destination_path'], scale_key, 'bias_data', 'apply_affine.dat')
            use_bounding_rect = bool(cfg.project_data['data']['scales'][scale_key]['use_bounding_rect'])
            logger.info('Writing Example Arguments to apply_affine.dat...')
            
            with open(ofn, 'w') as f:
                f.writelines("%s\n" % line for line in args)
        task_queue.add_task(args)

    print_snr_list()
    logger.info('Running Apply Affine Tasks (task_queue.collect_results())...')
    cfg.main_window.hud.post('Generating Images...')
    t0 = time.time()
    try:
        task_queue.collect_results()
        dt = time.time() - t0
        cfg.main_window.hud.post('Image Generation Completed in %.2f seconds. Wrapping up...' % dt)
        cfg.main_window.center_all_images()
    except:
        logger.warning('task_queue.collect_results() encountered a problem')
        print_exception()
    logger.info('Stopping TaskQueue...')
    task_queue.stop()
    del task_queue

    logger.critical('>>>>>>>> Generate Aligned End <<<<<<<<')


def create_align_directories(scale_key):
    source_dir = os.path.join(cfg.project_data['data']['destination_path'], scale_key, "img_src")
    makedirs_exist_ok(source_dir, exist_ok=True)
    target_dir = os.path.join(cfg.project_data['data']['destination_path'], scale_key, "img_aligned")
    makedirs_exist_ok(target_dir, exist_ok=True)
