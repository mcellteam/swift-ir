#!/usr/bin/env python3

import os
import sys
import time
import json
import psutil
import logging
import zarr
import numpy as np
import multiprocessing as mp
from multiprocessing.pool import ThreadPool
import zarr
import numcodecs
numcodecs.blosc.use_threads = False
from libtiff import TIFF
import tqdm

import src.config as cfg
from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_val, print_exception, reorder_tasks, renew_directory, file_hash
from src.mp_queue import TaskQueue
from src.funcs_image import SetStackCafm
from src.funcs_zarr import preallocate_zarr
from src.background_worker import BackgroundWorker
from src.job_apply_affine import run_mir


__all__ = ['GenerateAligned']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver')


def GenerateAligned(dm, scale, start=0, end=None, renew_od=False, reallocate_zarr=False, stageit=False, use_gui=True):
    logger.info('>>>> GenerateAligned >>>>')

    scale_val = get_scale_val(scale)

    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Generate Alignment')
    else:
        # if ng.is_server_running():
        #     logger.info('Stopping Neuroglancer...')
        #     ng.server.stop()

        tryRemoveDatFiles(dm, scale,dm.dest())

        Z_STRIDE = 0

        if cfg.USE_PYTHON:
            job_script = 'job_python_apply_affine.py'
        else:
            '''Default'''
            job_script = 'job_apply_affine.py'
        path = os.path.split(os.path.realpath(__file__))[0]
        job_script = os.path.join(path, job_script)

        SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=cfg.data.default_poly_order)

        cfg.data.propagate_swim_1x1_custom_px(start=start, end=end)
        cfg.data.propagate_swim_2x2_custom_px(start=start, end=end)
        cfg.data.propagate_manual_swim_window_px(start=start, end=end)

        od = os.path.join(dm.dest(), scale, 'img_aligned')
        if renew_od:
            logger.info('Renewing Directory %s...' % od)
            renew_directory(directory=od)
        # print_example_cafms(scale_dict)
        bias_path = os.path.join(dm.dest(), scale, 'bias_data')
        # try:
        #     save_bias_analysis(layers=dm.get_iter(s=scale), bias_path=bias_path)
        # except:
        #     print_exception()

        print_example_cafms(dm)

        if end == None:
            end = len(dm)
        n_tasks = len(list(range(start,end)))

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
        # args_list = makeTasksList(dm, iter(stack[start:end]), job_script, scale, rect) #0129-
        if end:
            cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(range(start,end)))
        else:
            cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(range(start, len(dm))))
        pbar_text = 'Generating Scale %d Alignment w/ MIR (%d Cores)...' % (scale_val, cpus)
        dest = dm['data']['destination_path']

        logger.info(f'\n\n################ Generating Aligned Images ################\n')

        tasks = []
        for layer in iter(dm()[start:end]):
            base_name = layer['filename']
            _ , fn = os.path.split(base_name)
            al_name = os.path.join(dest, scale, 'img_aligned', fn)
            cafm = layer['alignment']['method_results']['cumulative_afm']
            # ID = layer['alignment']['meta']['index']
            # args = [sys.executable, job_script, '-gray', '-rect',
            #         str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
            #         str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
            tasks.append([base_name, al_name, rect, cafm, 128])

        t0 = time.time()

        cfg.mw.set_status('Generating aligned images. No progress bar available. Awaiting multiprocessing pool...')
        cfg.mw.setPbarUnavailable(True)
        logger.info("RUNNING MULTIPROCESSING POOL (GENERATE ALIGNED IMAGES)...")
        pbar = tqdm.tqdm(total=len(tasks))
        t0 = time.time()

        def update_tqdm(*a):
            pbar.update()

        mp.set_start_method('forkserver')
        ctx = mp.get_context('forkserver')
        # with ctx.Pool(processes=cpus) as pool:
        with ThreadPool(processes=cpus) as pool:
            results = [pool.apply_async(func=run_mir, args=(task,), callback=update_tqdm) for task in tasks]
            pool.close()
            [p.get() for p in results]
            pool.join()
        logger.critical("----------END----------")
        cfg.mw.setPbarUnavailable(False)
        cfg.mw.set_status('')


        dm.t_generate = time.time() - t0

        dm.set_image_aligned_size()

    '''----TEMP----'''
    # for i, layer in enumerate(cfg.data.get_iter(scale)):
    #     layer['alignment_history'][cfg.data.get_current_method(l=i)]['cumulative_afm'] = \
    #         cfg.data['data']['scales'][scale]['stack'][i]['alignment']['method_results']['cumulative_afm']
    dm.register_cafm_hashes(s=scale, start=start, end=end)

    if cfg.ignore_pbar:
        cfg.nProcessDone += 1
        cfg.main_window.updatePbar()
        cfg.main_window.setPbarText('Copy-converting Alignment to Zarr...')

    pbar_text = 'Copy-converting Scale %d Alignment To Zarr (%d Cores)...' % (scale_val, cpus)
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
    else:
        logger.info('Generating Zarr...')
        if reallocate_zarr:
            logger.info('Preallocating...')
            preallocate_zarr(dm=dm,
                             name='img_aligned.zarr',
                             group='s%d' % scale_val,
                             dimx=rect[2],
                             dimy=rect[3],
                             dimz=len(dm),
                             dtype='|u1',
                             overwrite=True)

        # Create "staged" Zarr hierarchy and its groups
        # dir = os.path.join(dm.dest(), scale)
        # stage_path = os.path.join(dir, 'zarr_staged')
        # store = zarr.DirectoryStore(stage_path)  # Does not create directory
        # root = zarr.group(store=store, overwrite=False)  # <-- creates physical directory.
        # for i in range(len(dm)):
        #     if not os.path.exists(os.path.join(stage_path, str(i))):
        #         logger.info('creating group: %s' %str(i))
        #         root.create_group(str(i))


        if cfg.CancelProcesses:
            cfg.main_window.tell('Canceling Copy-convert Alignment to Zarr Tasks...')
        else:

            logger.info(f'\n\n################ Copy-convert Alignment To Zarr ################\n')

            # cfg.main_window.set_status('Copy-converting TIFFs...')
            chunkshape = dm.chunkshape
            dest = dm['data']['destination_path']


            # if cfg.USE_EXTRA_THREADING and use_gui:
            #     task_queue = TaskQueue(n_tasks=n_tasks, dest=dest, parent=cfg.main_window, pbar_text=pbar_text)
            # else:
            #     task_queue = TaskQueue(n_tasks=n_tasks, dest=dest, use_gui=use_gui)
            # task_queue.taskPrefix = 'Converting TIFF to Zarr for '
            # task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in dm()[start:end]]
            # task_queue.start(cpus)
            # job_script = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_convert_zarr.py')
            # for ID, layer in enumerate(iter(stack[start:snd])):
            # for i in range(start,end):
            #     _ , fn = os.path.split(dm()[i]['filename'])
            #     al_name = os.path.join(dm.dest(), scale, 'img_aligned', fn)
            #     zarr_group = os.path.join(dm.dest(), 'img_aligned.zarr', 's%d' % scale_val)
            #     dest = dm.dest()
            #     args = [sys.executable, job_script, str(i), al_name, zarr_group, str(chunkshape), str(int(stageit)), dest]
            #     task_queue.add_task(args)
            #     logger.info('stageit = %s' % str(int(stageit)))
            #     if cfg.PRINT_EXAMPLE_ARGS:
            #         if i in [0,1,2]:
            #             print('Example Arguments (ID: %d):\n%s' % (i, '\n  '.join(map(str,args))))
            # logger.info('Adding Tasks To Multiprocessing Queue...')
            # try:
            #     dt = task_queue.collect_results()
            #     dm.t_convert_zarr = dt
            # except:
            #     print_exception()
            #     logger.warning('Task Queue encountered a problem')

            tasks = []
            for i in range(start,end):
                _ , fn = os.path.split(dm()[i]['filename'])
                al_name = os.path.join(dm.dest(), scale, 'img_aligned', fn)
                zarr_group = os.path.join(dm.dest(), 'img_aligned.zarr', 's%d' % scale_val)
                task = [i, al_name, zarr_group]
                tasks.append(task)

            cfg.mw.set_status('Generating Zarr. No progress bar available. Awaiting multiprocessing pool...')
            cfg.mw.setPbarUnavailable(True)
            logger.info("RUNNING MULTIPROCESSING POOL (CONVERT ZARR)...")
            pbar = tqdm.tqdm(total=len(tasks))
            t0 = time.time()
            def update_tqdm(*a):
                pbar.update()
            # with ctx.Pool(processes=cpus) as pool:
            with ThreadPool(processes=cpus) as pool:
                results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_tqdm) for task in tasks]
                pool.close()
                [p.get() for p in results]
                pool.join()
            logger.info("----------END----------")
            cfg.mw.setPbarUnavailable(False)
            cfg.mw.set_status('')
            dt = time.time() - t0
            dm.t_convert_zarr = dt



    logger.info('<<<< Generate Aligned <<<<')

# def update_pbar():
#     logger.info('')
#     cfg.mw.pbar.setValue(cfg.mw.pbar.value()+1)


def convert_zarr(task):
    ID = task[0]
    fn = task[1]
    out = task[2]
    store = zarr.open(out, write_empty_chunks=False)
    tif = TIFF.open(fn)
    img = tif.read_image()[:, ::-1]  # np.array
    store[ID, :, :] = img  # store: <zarr.core.Array (19, 1244, 1130) uint8>
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]


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


def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(dm, scale, path):
    # bb_str = str(dm.has_bb())
    # poly_order_str = str(cfg.data.default_poly_order)
    bias_data_path = os.path.join(path, scale, 'bias_data')
    # tryRemoveFile(os.path.join(path, scale,
    #                            'swim_log_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    # tryRemoveFile(os.path.join(path, scale,
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
        # print('-----------------------------------')
        print('First Three CAFMs:')
        print(str(dm.cafm(l=0)))
        print(str(dm.cafm(l=1)))
        print(str(dm.cafm(l=2)))
        # print('-----------------------------------')
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