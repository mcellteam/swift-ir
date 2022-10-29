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
from src.image_funcs import SetStackCafm, ComputeBoundingRect, ImageSize
from src.zarr_funcs import preallocate_zarr_aligned



__all__ = ['generate_aligned']

logger = logging.getLogger(__name__)


def generate_aligned(scale, start_layer=0, num_layers=-1, preallocate=True):
    logger.critical('>>>> Generate Aligned >>>>')
    tryRemoveDatFiles(scale)
    Z_STRIDE = 0
    job_script = 'job_apply_affine.py'
    # job_script = 'job_python_apply_affine.py'
    path = os.path.split(os.path.realpath(__file__))[0]
    job_script = os.path.join(path, job_script)
    zarr_group = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's' + str(get_scale_val(scale)))
    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %d' % get_scale_val(scale))
        remove_aligned(use_scale=scale, start_layer=start_layer)
    scale_dict = cfg.data['data']['scales'][scale]
    print_example_cafms(scale_dict)
    SetStackCafm(scale_dict, null_biases=cfg.data.null_cafm()) #***
    print_example_cafms(scale_dict)

    alstack = scale_dict['alignment_stack']
    save_bias_analysis(alstack, os.path.join(cfg.data.dest(), scale, 'bias_data'))
    rect = getSetBoundingRect(scale, alstack)
    if preallocate: preallocate_zarr_aligned(scales=[scale])
    if num_layers == -1: end_layer = len(alstack)
    else: end_layer = start_layer + num_layers
    al_substack = alstack[start_layer:end_layer]
    args_list = makeTasksList(al_substack, job_script, rect, zarr_group)
    # args_list = reorder_tasks(task_list=args_list, z_stride=Z_STRIDE)
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2

    task_queue = TaskQueue(n_tasks=len(args_list),
                           parent=cfg.main_window,
                           pbar_text='Generating Alignment w/ MIR - Scale %d - %d Cores' %
                                     (get_scale_val(scale), cpus))
    task_queue.start(cpus)
    for task in args_list: task_queue.add_task(task)
    try:
        t0 = time.time()
        task_queue.collect_results()
        dt = time.time() - t0
        cfg.main_window.hud.post('Completed in %.2f seconds.' % dt)
    except:
        print_exception()
        logger.warning('task_queue.collect_results() encountered a problem')
    try: task_queue.end_tasks()
    except: print_exception()
    task_queue.stop()
    del task_queue
    logger.critical('<<<< Generate Aligned End <<<<')

def getSetBoundingRect(scale, alstack):
    if cfg.data.has_bb():
        rect = ComputeBoundingRect(alstack) # Must come AFTER SetStackCafm
    else:
        width, height = ImageSize(cfg.data.path_base(s=scale,l=0))
        rect = [0, 0, width, height]
    cfg.data.set_bounding_rect(rect)
    logger.info('Bounding Rect is %s' % str(rect))
    return rect

def makeTasksList(al_substack, job_script, rect, zarr_group):
    args_list = []
    for ID, layer in enumerate(al_substack):
        # if ID in [0,1,2]:
        #     logger.critical('\nafm = %s\n' % ' '.join(map(str, cfg.data.afm(l=ID))))
        #     logger.critical('\ncafm = %s\n' % ' '.join(map(str, cfg.data.cafm(l=ID))))
        base_name = layer['images']['base']['filename']
        al_path, fn = os.path.split(base_name)
        al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = al_name
        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']
        args = [sys.executable, job_script, '-gray', '-rect',
                str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
                str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name,
                zarr_group, str(ID)]
        # NOTE - previously had conditional here for 'if use_bounding_rect' then don't pass -rect args
        args_list.append(args)
    return args_list



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


def print_example_cafms(scale_dict):
    try:
        print('---------- First 3 CAFMs ----------')
        print(str(cfg.data.cafm(l=0)))
        print(str(cfg.data.cafm(l=1)))
        print(str(cfg.data.cafm(l=2)))
        print('-----------------------------------')
    except:
        pass

# def create_align_directories(s):
#     source_dir = os.path.join(cfg.data['data']['destination_path'], s, "img_src")
#     makedirs_exist_ok(source_dir, exist_ok=True)
#     target_dir = os.path.join(cfg.data['data']['destination_path'], s, "img_aligned")
#     makedirs_exist_ok(target_dir, exist_ok=True)


# Old Job Script
# Running (Example): python job_python_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name')


'''
Previous functionality was located:
regenerate_aligned()       <- alignem_swift.py
generate_aligned_images()  <- project_runner.py
'''