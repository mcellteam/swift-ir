#!/usr/bin/env python3

import os
import sys
import time
import json
import psutil
import logging
import neuroglancer as ng
import src.config as cfg
from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_key, get_scale_val, are_aligned_images_generated, \
    makedirs_exist_ok, print_exception, print_snr_list, remove_aligned, reorder_tasks, show_mp_queue_results, \
    kill_task_queue, renew_directory
from src.mp_queue import TaskQueue
from src.funcs_image import SetStackCafm, ComputeBoundingRect
from src.funcs_zarr import preallocate_zarr


__all__ = ['generate_aligned']

logger = logging.getLogger(__name__)


def generate_aligned(scale, start_layer=0, num_layers=-1, preallocate=True):
    logger.info('Generating Aligned Images...')

    if ng.is_server_running():
        logger.info('Stopping Neuroglancer...')
        ng.server.stop()

    tryRemoveDatFiles(scale)
    Z_STRIDE = 0

    if cfg.USE_PYTHON:
        job_script = 'job_python_apply_affine.py'
    else:
        '''Default'''
        job_script = 'job_apply_affine.py'
    path = os.path.split(os.path.realpath(__file__))[0]
    job_script = os.path.join(path, job_script)
    scale_val = get_scale_val(scale)
    dest = cfg.data.dest()
    zarr_group = os.path.join(dest, 'img_aligned.zarr', 's%d' % scale_val)
    od = os.path.join(dest, scale, 'img_aligned')
    renew_directory(directory=od)
    alstack = cfg.data.alstack(s=scale)
    print_example_cafms()
    # layerator = cfg.data.get_iter(s=s)
    logger.critical('Setting Stack CAFM...')
    SetStackCafm(scale=scale, null_biases=cfg.data.null_cafm(s=scale), poly_order=cfg.data.poly_order(s=scale))
    # print_example_cafms(scale_dict)
    bias_path = os.path.join(dest, scale, 'bias_data')
    iterator = cfg.data.get_iter(s=scale)
    save_bias_analysis(layers=iterator, bias_path=bias_path)
    if cfg.data.has_bb():
        # Note: now have got new cafm's -> recalculate bounding box
        rect = cfg.data.set_calculate_bounding_rect(s=scale) # Only after SetStackCafm
        logger.info(f'Bounding Box              : ON\nNew Bounding Box          : {str(rect)}')
        logger.info(f'Null Bias                 : {cfg.data.null_cafm()} (Polynomial Order: {cfg.data.poly_order()})')
    else:
        logger.info(f'Bounding Box              : OFF')
        w, h = cfg.data.image_size(s=scale)
        rect = [0, 0, w, h] # might need to swap w/h for Zarr
    logger.info(f'Aligned Size              : {rect[2:]}')
    logger.info(f'Offsets                   : {rect[0]}, {rect[1]}')
    group = 's%d' % scale_val
    if preallocate:
        preallocate_zarr(name='img_aligned.zarr',
                         group=group,
                         dimx=rect[2],
                         dimy=rect[3],
                         dimz=cfg.data.n_layers(),
                         dtype='uint8',
                         overwrite=True)

    if num_layers == -1:
        end_layer = len(alstack)
    else:
        end_layer = start_layer + num_layers
    iterator = iter(alstack[start_layer:end_layer])
    args_list = makeTasksList(iterator, job_script, scale, rect, zarr_group)
    # args_list = reorder_tasks(task_list=args_list, z_stride=Z_STRIDE)
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=len(args_list),
                           parent=cfg.main_window,
                           pbar_text='Generating Scale %d Alignment w/ MIR...' % (scale_val))
    task_queue.start(cpus)
    for task in args_list:
        task_queue.add_task(task)
    try:
        dt = task_queue.collect_results()
        show_mp_queue_results(task_queue=task_queue, dt=dt)
    except:
        print_exception()
        logger.warning('Task Queue encountered a problem')
    finally:
        kill_task_queue(task_queue=task_queue)

    #### RUN ZARR TASKS

    logger.info('Making Zarr Copy-convert Alignment Tasks List...')
    # cfg.main_window.set_status('Copy-converting TIFFs...')
    task_queue = TaskQueue(n_tasks=len(args_list),
                           parent=cfg.main_window,
                           pbar_text='Copy-converting Scale %d Alignment To Zarr...' % (
                           scale_val))
    task_queue.start(cpus)
    job_script = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_convert_zarr.py')
    task_list = []
    for ID, layer in enumerate(iter(alstack[start_layer:end_layer])):
        _ , fn = os.path.split(layer['images']['base']['filename'])
        al_name = os.path.join(dest, scale, 'img_aligned', fn)
        zarr_group = os.path.join(dest, 'img_aligned.zarr', 's%d' % scale_val)
        args = [sys.executable, job_script, str(ID), al_name, zarr_group]
        task_list.append(args)
        if cfg.PRINT_EXAMPLE_ARGS:
            if ID in [0,1,2]:
                logger.info('generate_aligned/job_convert_zarr Example Arguments (ID: %d):\n%s' % (ID, str(args)))
        # task_queue.add_task(args)
    chunkshape = cfg.data.chunkshape()
    # task_list = reorder_tasks(task_list, chunkshape[0])
    logger.info('Adding Tasks To Multiprocessing Queue...')
    for task in task_list:
        # logger.info('Adding Layer %s Task' % task[2])
        task_queue.add_task(task)

    try:
        dt = task_queue.collect_results()
        show_mp_queue_results(task_queue=task_queue, dt=dt)
    except:
        print_exception()
        logger.warning('Task Queue encountered a problem')
    finally:
        kill_task_queue(task_queue=task_queue)
        cfg.main_window.set_idle()

    logger.info('<<<< Generate Aligned End <<<<')


def makeTasksList(iter, job_script, scale, rect, zarr_group):
    logger.info('Making Generate Alignment Tasks List...')
    args_list = []
    dest = cfg.data.dest()
    for ID, layer in enumerate(iter):
        # if ID in [0,1,2]:
        #     logger.info('afm = %s\n' % ' '.join(map(str, cfg.data.afm(l=ID))))
        #     logger.info('cafm = %s\n' % ' '.join(map(str, cfg.data.cafm(l=ID))))
        base_name = layer['images']['base']['filename']
        _ , fn = os.path.split(base_name)
        al_name = os.path.join(dest, scale, 'img_aligned', fn)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = al_name
        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']
        args = [sys.executable, job_script, '-gray', '-rect',
                str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
                str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name,
                zarr_group, str(ID)]
        if cfg.PRINT_EXAMPLE_ARGS:
            if ID in [0,1,2]:
                logger.info('Example Arguments (ID: %d):\n%s' % (ID, str(args)))
        # NOTE - previously had conditional here for 'if use_bounding_rect' then don't pass -rect args
        args_list.append(args)
    return args_list


def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(scale):
    bb_str = str(cfg.data.has_bb())
    poly_order_str = str(cfg.data.poly_order())
    null_cafm_str = str(cfg.data.null_cafm())
    bias_data_path = os.path.join(cfg.data.dest(), scale, 'bias_data')
    tryRemoveFile(os.path.join(cfg.data.dest(), scale, 'swim_log_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    tryRemoveFile(os.path.join(cfg.data.dest(), scale, 'mir_commands_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    tryRemoveFile(os.path.join(cfg.data.dest(), scale, 'swim_log.dat'))
    tryRemoveFile(os.path.join(cfg.data.dest(), scale, 'mir_commands.dat'))
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


def print_example_cafms():
    try:
        # print('-----------------------------------')
        print('First Three CAFMs:')
        print(str(cfg.data.cafm(l=0)))
        print(str(cfg.data.cafm(l=1)))
        print(str(cfg.data.cafm(l=2)))
        # print('-----------------------------------')
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