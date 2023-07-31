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
from src.helpers import get_scale_val, print_exception, reorder_tasks, renew_directory, file_hash, pretty_elapsed
from src.mp_queue import TaskQueue
from src.funcs_image import SetStackCafm
from src.funcs_zarr import preallocate_zarr
from src.background_worker import BackgroundWorker
from src.job_apply_affine import run_mir


__all__ = ['GenerateAligned']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver', force=True)

def GenerateAligned(dm, scale, start=0, end=None, renew_od=False, reallocate_zarr=False, stageit=False, use_gui=True):
    logger.info('>>>> GenerateAligned >>>>')

    scale_val = get_scale_val(scale)

    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Generate Alignment')
        return


    tryRemoveDatFiles(dm, scale,dm.dest())

    SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=cfg.data.default_poly_order)

    cfg.data.propagate_swim_1x1_custom_px(start=start, end=end)
    cfg.data.propagate_swim_2x2_custom_px(start=start, end=end)
    cfg.data.propagate_manual_swim_window_px(start=start, end=end)

    od = os.path.join(dm.dest(), scale, 'img_aligned')
    if renew_od:
        renew_directory(directory=od)
    # print_example_cafms(scale_dict)

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
        logger.info(f'Corrective Polynomial  : {cfg.data.default_poly_order} (Polynomial Order: {cfg.data.default_poly_order})')
    else:
        logger.info(f'Bounding Box      : OFF')
        w, h = dm.image_size(s=scale)
        rect = [0, 0, w, h] # might need to swap w/h for Zarr
    logger.info(f'Aligned Size      : {rect[2:]}')
    logger.info(f'Offsets           : {rect[0]}, {rect[1]}')
    # args_list = makeTasksList(dm, iter(stack[start:end]), job_script, scale_key, rect) #0129-
    if end:
        cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(range(start,end))),1)
    else:
        cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(range(start, len(dm)))),1)
    dest = dm['data']['destination_path']
    print(f'\n\n######## Generating Aligned Images ########\n')

    tasks = []
    for layer in iter(dm()[start:end]):
        base_name = layer['filename']
        _ , fn = os.path.split(base_name)
        al_name = os.path.join(dest, scale, 'img_aligned', fn)
        cafm = layer['alignment']['method_results']['cumulative_afm']
        tasks.append([base_name, al_name, rect, cafm, 128])

    cfg.mw.set_status('Generating aligned images. No progress bar available. Awaiting multiprocessing pool...')
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
    # with ThreadPool(processes=cpus) as pool:

    ctx = mp.get_context('forkserver')
    with ctx.Pool() as pool:
        list(tqdm.tqdm(pool.imap_unordered(run_mir, tasks), total=len(tasks), desc="Generate Alignment", position=0, leave=True))
        pool.close()


    # with ThreadPoolExecutor(max_workers=cpus) as pool:
    #     list(pool.map(run_mir, tqdm.tqdm(tasks, total=len(tasks), desc="Generate Alignment", position=0, leave=True)))
    #


    # _it = 0
    # while (count_aligned_files(dm.dest(), scale) < len(dm)) or _it > 4:
    #     # logger.info('Sleeping for 1 second...')
    #     time.sleep(1)
    #     _it += 1

    logger.info("Generate Alignment Finished")


    t_elapsed = time.time() - t0
    dm.t_generate = t_elapsed
    cfg.main_window.set_elapsed(t_elapsed, f'Generate alignment')

    # time.sleep(1)

    dm.register_cafm_hashes(s=scale, start=start, end=end)
    dm.set_image_aligned_size()

    pbar_text = 'Copy-converting Scale %d Alignment To Zarr (%d Cores)...' % (scale_val, cpus)
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        return
    if reallocate_zarr:
        preallocate_zarr(dm=dm,
                         name='img_aligned.zarr',
                         group='s%d' % scale_val,
                         shape=(len(dm), rect[3], rect[2]),
                         dtype='|u1',
                         overwrite=True)

    # Create "staged" Zarr hierarchy and its groups
    # dir = os.path.join(dm.dest(), scale_key)
    # stage_path = os.path.join(dir, 'zarr_staged')
    # store = zarr.DirectoryStore(stage_path)  # Does not create directory
    # root = zarr.group(store=store, overwrite=False)  # <-- creates physical directory.
    # for i in range(len(dm)):
    #     if not os.path.exists(os.path.join(stage_path, str(i))):
    #         logger.info('creating group: %s' %str(i))
    #         root.create_group(str(i))

    print(f'\n\n######## Copy-convert Alignment To Zarr ########\n')

    tasks = []
    for i in range(start,end):
        _ , fn = os.path.split(dm()[i]['filename'])
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
    """Non-blocking"""
    # with ThreadPool(processes=cpus) as pool:
    #     results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_pbar) for task in tasks]
    #     pool.close()
    #     [p.get() for p in results]
    #     # pool.join()
    """Blocking"""
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(convert_zarr, tqdm.tqdm(tasks, total=len(tasks), desc="Convert Alignment to Zarr", position=0, leave=True)))

    logger.info("Convert Alignment to Zarr Finished")

    t_elapsed = time.time() - t0
    dm.t_convert_zarr = t_elapsed
    cfg.main_window.set_elapsed(t_elapsed, f'Copy-convert alignment to Zarr')
    time.sleep(1)

    cfg.main_window._autosave(silently=True) #0722+


# def update_pbar():
#     logger.info('')
#     cfg.mw.pbar.setValue(cfg.mw.pbar.value()+1)

def imread(filename):
    # return first image in TIFF file as numpy array
    with open(filename, 'rb') as fh:
        data = fh.read()
    return imagecodecs.tiff_decode(data)


def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        store = zarr.open(out)
        # tif = libtiff.TIFF.open(fn)
        # img = tif.read_image()[:, ::-1]  # np.array
        # img = imread(fn)[:, ::-1]
        # store[ID, :, :] = img  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        store[ID, :, :] = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        # store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

        return 0
    except Exception as e:
        print(e)
        return 1

def makeTasksList(dm, iter, job_script, scale, rect, zarr_group):
    logger.info('Making Generate Alignment Tasks List...')
    args_list = []
    dest = dm.dest()
    for ID, layer in enumerate(iter):
        # if ID in [0,1,2]:
        #     logger.info('afm = %s\n' % ' '.join(map(str, datamodel.afm(l=ID))))
        #     logger.info('cafm = %s\n' % ' '.join(map(str, datamodel.cafm(l=ID))))
        base_name = layer['filename']
        _ , fn = os.path.split(base_name)
        al_name = os.path.join(dest, scale, 'img_aligned', fn)
        # layer['images']['aligned'] = {}
        # layer['images']['aligned']['filename'] = al_name
        cafm = layer['alignment']['method_results']['cumulative_afm']
        args = [sys.executable, job_script, '-gray', '-rect',
                str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
                str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name,
                zarr_group, str(ID)]
        if cfg.PRINT_EXAMPLE_ARGS:
            if ID in [0,1,2]:
                logger.info('Example Arguments (ID: %d):\n%s' % (ID, '    '.join(map(str,args))))
            # if ID is 7:
            #     args[2] = '-bogus_option'
            # if ID is 11:
            #     args[15] = 'bogus_file'

        # NOTE - previously had conditional here for 'if use_bounding_rect' then don't pass -rect args
        args_list.append(args)
    return args_list



def count_aligned_files(dest, s):
    path = os.path.join(dest, s, 'img_aligned')
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

# def create_align_directories(s):
#     source_dir = os.path.join(datamodel['data']['destination_path'], s, "img_src")
#     makedirs_exist_ok(source_dir, exist_ok=True)
#     target_dir = os.path.join(datamodel['data']['destination_path'], s, "img_aligned")
#     makedirs_exist_ok(target_dir, exist_ok=True)


# Old Job Script
# Running (Example): python job_python_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name')


'''
Previous functionality was located:
regenerate_aligned()       <- alignem_swift.py
generate_aligned_images()  <- project_runner.py
'''