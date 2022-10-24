#!/usr/bin/env python3

import os
import sys
import time
import json
import psutil
import logging
import importlib
from pathlib import Path
import src.config as cfg
from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_key, get_scale_val, are_aligned_images_generated, \
    makedirs_exist_ok, print_exception, print_snr_list, remove_aligned, reorder_tasks
from src.mp_queue import TaskQueue
from src.image_funcs import SetStackCafm, compute_bounding_rect, ImageSize
from src.zarr_funcs import preallocate_zarr_aligned

'''
64*64*64  = 262,144
1*512*512 = 262,144


Previous functionality was located:
regenerate_aligned()       <- alignem_swift.py
generate_aligned_images()  <- project_runner.py
'''

__all__ = ['generate_aligned']

logger = logging.getLogger(__name__)


def generate_aligned(scale, start_layer=0, num_layers=-1, preallocate=True):
    logger.critical('>>>> Generate Aligned >>>>')

    tryRemoveDatFiles(scale)

    Z_STRIDE = 0

    JOB_FILE = 'job_apply_affine.py'
    # JOB_FILE = 'job_python_apply_affine.py'
    #TODO Add immediate check if alignment data exists and looks correct
    path = os.path.split(os.path.realpath(__file__))[0]
    apply_affine_job = os.path.join(path, JOB_FILE)
    zarr_path = os.path.join(cfg.data.dest(), 'img_aligned.zarr')
    # create_align_directories(scale=scale)
    # print_snr_list()
    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %d' % get_scale_val(scale))
        remove_aligned(use_scale=scale, start_layer=start_layer)

    logger.critical('Calling SetStackCafm (Propogating AFMs to generate CFMs at each layer)...')

    scale_dict = cfg.data['data']['scales'][scale]
    print('================================')
    print(str(scale_dict['alignment_stack'][0]['align_to_ref_method']['method_results']['cumulative_afm']))
    print(str(scale_dict['alignment_stack'][1]['align_to_ref_method']['method_results']['cumulative_afm']))
    print(str(scale_dict['alignment_stack'][2]['align_to_ref_method']['method_results']['cumulative_afm']))
    print('----------------------')
    print(str(cfg.data.cafm(l=0)))
    print(str(cfg.data.cafm(l=1)))
    print(str(cfg.data.cafm(l=2)))
    print('================================')

    SetStackCafm(scale_dict, null_biases=cfg.data.null_cafm())

    print('================================')
    print(str(scale_dict['alignment_stack'][0]['align_to_ref_method']['method_results']['cumulative_afm']))
    print(str(scale_dict['alignment_stack'][1]['align_to_ref_method']['method_results']['cumulative_afm']))
    print(str(scale_dict['alignment_stack'][2]['align_to_ref_method']['method_results']['cumulative_afm']))
    print('----------------------')
    print(str(cfg.data.cafm(l=0)))
    print(str(cfg.data.cafm(l=1)))
    print(str(cfg.data.cafm(l=2)))
    print('================================')

    '''This is where save_bias_analysis should probably be'''

    alstack = cfg.data['data']['scales'][scale]['alignment_stack']

    bias_data_path = os.path.join(cfg.data.dest(), scale, 'bias_data')
    save_bias_analysis(alstack, bias_data_path)

    if cfg.data.has_bb():
        rect = compute_bounding_rect(alstack) # Must come AFTER SetStackCafm
    else:
        width, height = ImageSize(cfg.data.path_base(s=scale,l=0))
        rect = [0, 0, width, height]
    cfg.data.set_bounding_rect(rect)
    logger.info('Bounding Rect is %s' % str(rect))

    if preallocate == True:
        preallocate_zarr_aligned(scales=[scale])

    if num_layers == -1: end_layer = len(alstack)
    else:  end_layer = start_layer + num_layers

    n_tasks = cfg.data.n_imgs()
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Alignment w/ MIR - Scale %d - %d Cores' % (get_scale_val(scale), cpus))
    logger.info('Starting Task Queue...')
    task_queue.start(cpus)
    logger.info('Job Script: %s' % apply_affine_job)

    args_list = []
    for ID, layer in enumerate(alstack[start_layer:end_layer + 1]):
        if ID in [0,1,2]:
            logger.critical('\nafm = %s\n' % ' '.join(map(str, cfg.data.afm(l=ID))))
            logger.critical('\ncafm = %s\n' % ' '.join(map(str, cfg.data.cafm(l=ID))))

        # These IDs are ordered correctly for Zarr indexing
        # logger.critical('generate_aligned Loop. Image: %s' % l['images']['base']['filename'])

        zarr_grp = os.path.join(zarr_path, 's' + str(get_scale_val(scale)))
        zarr_args = [zarr_grp, str(ID)]

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
        # previously had conitional here for 'if use_bounding_rect' then don't pass -rect args...

        if ID in [0,1,2]:
            logger.info('\n(Example Arguments, l=%d):' % ID)
            print(*args, sep="\n")
            ofn = os.path.join(cfg.data['data']['destination_path'], scale, 'bias_data', 'apply_affine.dat')
            with open(ofn, 'a+') as f:
                f.writelines("%s\n" % line for line in args)

        # task_queue.add_task(args)
        args_list.append(args)

    # args_list = reorder_tasks(task_list=args_list, z_stride=Z_STRIDE)
    for task in args_list:
        task_queue.add_task(task)

    print_snr_list()
    logger.info('Running Apply Affine Tasks (task_queue.collect_results())...')
    t0 = time.time()
    try:
        task_queue.collect_results()
        dt = time.time() - t0
        cfg.main_window.hud.post('Completed in %.2f seconds.' % dt)
    except:
        logger.warning('task_queue.collect_results() encountered a problem')
        print_exception()
    finally:
        '''Shoehorn a dictionary key which states if the last images aligned had a bounding box'''
        if (start_layer == 0) & (num_layers == -1):
            for ID, layer in enumerate(alstack[start_layer:end_layer + 1]):
                if cfg.data['data']['scales'][scale]['use_bounding_rect']:
                    cfg.data['data']['scales'][scale]['alignment_stack'][ID]['align_to_ref_method'][
                        'method_options'].update({'has_bounding_rect': True})
                else:
                    cfg.data['data']['scales'][scale]['alignment_stack'][ID]['align_to_ref_method'][
                        'method_options'].update({'has_bounding_rect': False})
    try: task_queue.end_tasks()
    except: pass
    task_queue.stop()
    del task_queue

    logger.critical('<<<< Generate Aligned End <<<<')



def create_align_directories(scale):
    source_dir = os.path.join(cfg.data['data']['destination_path'], scale, "img_src")
    makedirs_exist_ok(source_dir, exist_ok=True)
    target_dir = os.path.join(cfg.data['data']['destination_path'], scale, "img_aligned")
    makedirs_exist_ok(target_dir, exist_ok=True)

def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(scale):
    bias_data_path = os.path.join(cfg.data.dest(), scale, 'bias_data')
    tryRemoveFile(os.path.join(cfg.data.dest(), 'swim_log.dat'))
    tryRemoveFile(os.path.join(cfg.data.dest(), 'mir_commands.dat'))
    tryRemoveFile(os.path.join(cfg.data.dest(), 'fdm_new.txt'))
    tryRemoveFile(os.path.join(bias_data_path, 'snr_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_x_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_y_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_rot_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_scale_x_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_scale_y_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_skew_x_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_det_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'afm_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'c_afm_1.dat'))


# Old Job Script
# Running (Example): python job_python_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name')