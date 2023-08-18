#!/usr/bin/env python3

import os
import sys
import time
import json
import psutil
import logging
import concurrent
import zarr
import numpy as np
from random import shuffle
import multiprocessing as mp
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
import tqdm
import zarr
import neuroglancer as ng
import imagecodecs
import numcodecs
numcodecs.blosc.use_threads = False
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()

import src.config as cfg
from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_val, print_exception, reorder_tasks, renew_directory, file_hash, pretty_elapsed, \
    is_tacc
from src.mp_queue import TaskQueue
from src.funcs_image import SetStackCafm
from src.funcs_zarr import preallocate_zarr
from src.job_apply_affine import run_mir


__all__ = ['GenerateAligned']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver', force=True)

def GenerateAligned(dm, scale, indexes, renew_od=False, reallocate_zarr=False):
    logger.info('>>>> GenerateAligned >>>>')

    scale_val = get_scale_val(scale)

    if cfg.CancelProcesses:
        logger.warning('Canceling Generate Alignment')
        return


    tryRemoveDatFiles(dm, scale,dm.dest())

    SetStackCafm(cfg.data, scale=scale, poly_order=dm.default_poly_order)

    dm.propagate_swim_1x1_custom_px(indexes=indexes)
    dm.propagate_swim_2x2_custom_px(indexes=indexes)
    dm.propagate_manual_swim_window_px(indexes=indexes)

    od = os.path.join(dm.dest(), scale, 'img_aligned')
    if renew_od:
        renew_directory(directory=od)

    # try:
    #     bias_path = os.path.join(dm.dest(), scale_key, 'bias_data')
    #     save_bias_analysis(layers=dm.get_iter(s=scale_key), bias_path=bias_path)
    # except:
    #     print_exception()

    print_example_cafms(dm)

    if dm.has_bb():
        # Note: now have got new cafm's -> recalculate bounding box
        rect = dm.set_calculate_bounding_rect(s=scale) # Only after SetStackCafm
        logger.info(f'Bounding Box           : ON\nNew Bounding Box  : {str(rect)}')
        logger.info(f'Corrective Polynomial  : {dm.default_poly_order} (Polynomial Order: {dm.default_poly_order})')
    else:
        logger.info(f'Bounding Box      : OFF')
        w, h = dm.image_size(s=scale)
        rect = [0, 0, w, h] # might need to swap w/h for Zarr
    logger.info(f'Aligned Size      : {rect[2:]}')
    logger.info(f'Offsets           : {rect[0]}, {rect[1]}')
    if is_tacc():
        cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(indexes)),1)
    else:
        cpus = psutil.cpu_count(logical=False)

    dest = dm['data']['destination_path']
    print(f'\n\nGenerating Aligned Images for {indexes}\n')

    tasks = []
    for sec in [dm()[i] for i in indexes]:
        base_name = sec['alignment']['swim_settings']['fn_transforming']
        _ , fn = os.path.split(base_name)
        al_name = os.path.join(dest, scale, 'img_aligned', fn)
        method = sec['alignment']['swim_settings']['method'] #0802+
        cafm = sec['alignment_history'][method]['method_results']['cumulative_afm']
        tasks.append([base_name, al_name, rect, cafm, 128])

    # pbar = tqdm.tqdm(total=len(tasks), position=0, leave=True, desc="Generating Alignment")

    # def update_pbar(*a):
    #     pbar.update()

    t0 = time.time()
    # ctx = mp.get_context('forkserver')
    # with ctx.Pool(processes=cpus) as pool:
    # with ThreadPool(processes=cpus) as pool:
    #     results = [pool.apply_async(func=run_mir, args=(task,), callback=update_pbar) for task in tasks]
    #     pool.close()
    #     [p.get() for p in results]
    #     pool.join()

    # def run_apply_async_multiprocessing(func, argument_list, num_processes):
    #     pool = mp.Pool(processes=num_processes)
    #     results = [pool.apply_async(func=func, args=(*argument,), callback=update_pbar) if isinstance(argument, tuple) else pool.apply_async(
    #         func=func, args=(argument,), callback=update_pbar) for argument in argument_list]
    #     pool.close()
    #     result_list = [p.get() for p in results]
    #     return result_list
    #
    # run_apply_async_multiprocessing(func=run_mir, argument_list=tasks, num_processes=cpus)
    #
    """Non-blocking"""
    # with ThreadPool(processes=cpus) as pool:
    #     results = [pool.apply_async(func=run_mir, args=(task,), callback=update_pbar) for task in tasks]
    #     pool.close()
    #     [p.get() for p in results]

    """Blocking"""
    ctx = mp.get_context('forkserver')
    with ctx.Pool() as pool:
        list(tqdm.tqdm(pool.imap_unordered(run_mir, tasks), total=len(tasks), desc="Generate Alignment", position=0, leave=True))
        pool.close()

    # with ThreadPoolExecutor(max_workers=cpus) as pool:
    #     list(pool.map(run_mir, tqdm.tqdm(tasks, total=len(tasks), desc="Generate Alignment", position=0, leave=True)))

    # _it = 0
    # while (count_aligned_files(dm.dest(), scale) < len(dm)) or _it > 4:
    #     # logger.info('Sleeping for 1 second...')
    #     time.sleep(1)
    #     _it += 1

    logger.info("Generate Alignment Finished")

    t_elapsed = time.time() - t0
    dm.t_generate = t_elapsed
    # cfg.main_window.set_elapsed(t_elapsed, f'Generate alignment')

    dm.register_cafm_hashes(s=scale, indexes=indexes)
    # dm.set_image_aligned_size() #Todo upgrade

    pbar_text = 'Copy-converting Scale %d Alignment To Zarr (%d Cores)...' % (scale_val, cpus)
    if cfg.CancelProcesses:
        logger.warning('Canceling Tasks: %s' % pbar_text)
        return
    if reallocate_zarr:
        preallocate_zarr(dm=dm,
                         name='img_aligned.zarr',
                         group='s%d' % scale_val,
                         shape=(len(dm), rect[3], rect[2]),
                         dtype='|u1',
                         overwrite=True)

    print(f'\n\nCopy-convert Alignment To Zarr for {indexes}\n')

    tasks = []
    for i in indexes:
        _ , fn = os.path.split(dm()[i]['alignment']['swim_settings']['fn_transforming'])
        al_name = os.path.join(dm.dest(), scale, 'img_aligned', fn)
        zarr_group = os.path.join(dm.dest(), 'img_aligned.zarr', 's%d' % scale_val)
        task = [i, al_name, zarr_group]
        tasks.append(task)
    # shuffle(tasks)

    t0 = time.time()

    if ng.is_server_running():
        logger.info('Stopping Neuroglancer...')
        ng.server.stop()

    # with ctx.Pool(processes=cpus) as pool:
    # with ThreadPool(processes=cpus) as pool:
    #     results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_pbar) for task in tasks]
    #     pool.close()
    #     [p.get() for p in results]
    #     # pool.join()
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(convert_zarr, tqdm.tqdm(tasks, total=len(tasks), desc="Convert Alignment to Zarr", position=0, leave=True)))

    logger.info("Convert Alignment to Zarr Finished")

    t_elapsed = time.time() - t0
    dm.t_convert_zarr = t_elapsed
    # cfg.main_window.set_elapsed(t_elapsed, f'Copy-convert alignment to Zarr')
    # time.sleep(1)

    # cfg.main_window._autosave(silently=True) #0722+


# def update_pbar():
#     logger.info('')
#     cfg.mw.pbar.setValue(cfg.mw.pbar.value()+1)

def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        store = zarr.open(out)
        store[ID, :, :] = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        return 0
    except Exception as e:
        print(e)
        return 1


def count_aligned_files(dest, s):
    path = os.path.join(dest, 'tiff', s)
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    # print(f"# {s} Files: {len(files)}")
    print(f"# complete: {len(files)}", end="\r")
    return len(files)

def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(dm, scale, path):
    # bb_str = str(dm.has_bb())
    # poly_order_str = str(cfg.data.default_poly_order)
    bias_data_path = os.path.join(path, scale, 'bias_data')
    # tryRemoveFile(os.path.join(path, scale_key,
    #                            'swim_log_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    # tryRemoveFile(os.path.join(path, scale_key,
    #                            'mir_commands_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    tryRemoveFile(os.path.join(path, scale, 'swim_log.dat'))
    tryRemoveFile(os.path.join(path, scale, 'mir_commands.dat'))
    tryRemoveFile(os.path.join(path, 'fdm_new.txt'))
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


def print_example_cafms(dm):
    try:
        print('First Three CAFMs:')
        print(str(dm.cafm(l=0)))
        if len(dm) > 1:
            print(str(dm.cafm(l=1)))
        if len(dm) > 2:
            print(str(dm.cafm(l=2)))
    except:
        pass


# Old Job Script
# Running (Example): python job_python_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name')

