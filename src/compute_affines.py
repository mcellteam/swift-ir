#!/usr/bin/env python3

import os
import re
import sys
import copy
import json
import glob
from glob import glob
import time
import shutil
import argparse
import traceback
import inspect
import psutil
import logging
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import multiprocessing as mp
import subprocess as sp
import numpy as np
import tqdm

sys.path.insert(1, os.path.dirname(os.path.split(os.path.realpath(__file__))[0]))
sys.path.insert(1, os.path.split(os.path.realpath(__file__))[0])
from src.data_model import DataModel
from src.funcs_image import SetStackCafm
from src.generate_aligned import GenerateAligned
from src.thumbnailer import Thumbnailer
from src.mp_queue import TaskQueue
from src.data_model import DataModel
from src.background_worker import BackgroundWorker
import src.config as cfg
from src.ui.timer import Timer
from src.recipe_maker import run_recipe


__all__ = ['ComputeAffines']

logger = logging.getLogger(__name__)

def ComputeAffines(scale, path, start=0, end=None, use_gui=True, renew_od=False, reallocate_zarr=False, stageit=False, swim_only=False, bounding_box=False, dm=None):
    '''Compute the python_swiftir transformation matrices for the current s stack of images according to Recipe1.'''
    # caller = inspect.stack()[1].function

    # logger.info(f'use_gui = {use_gui}')

    if cfg.CancelProcesses:
        cfg.mw.warn('Canceling Compute Affine Tasks')
    else:
        logger.info(f'\n\nPreparing Alignment Tasks...\n')
        logger.info(f'path: {path}')

        # if path:
        if not use_gui:
            with open(path, 'r') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    logger.warning(e)
                    return
            USE_FILE_IO = 0
            DEV_MODE = False
            TACC_MAX_CPUS = 122
            dm = DataModel(data)
            logger.info(f'dm.dest(): {dm.dest()}')
            dm.set_defaults()
        else:
            logger.critical('using GUI...')
            USE_FILE_IO = cfg.USE_FILE_IO
            DEV_MODE = cfg.DEV_MODE
            TACC_MAX_CPUS = cfg.TACC_MAX_CPUS
            # dm = cfg.data

        if end == None:
            end = dm.count

        scratchpath = os.path.join(dm.dest(), 'logs', 'scratch.log')
        if os.path.exists(scratchpath):
            os.remove(scratchpath)

        rename_switch = False
        alignment_dict = dm['data']['scales'][scale]['stack']

        # alignment_option = dm['data']['scales'][scale_key]['method_data']['alignment_option']
        logger.info('Start Layer: %s /End layer: %s' % (str(start), str(end)))

        # path = os.path.join(dm.dest(), scale_key, 'img_aligned')
        # if checkForTiffs(path):
        #     # al_substack = dm['data']['scales'][scale_key]['stack'][start:]
        #     # remove_aligned(al_substack) #0903 Moved into conditional
        #     dm.remove_aligned(scale_key, start, end)

        signals_dir = os.path.join(dm.dest(), scale, 'signals')
        if not os.path.exists(signals_dir):
            os.mkdir(signals_dir)


        dm.clear_method_results(scale=scale, start=start, end=end) #1109 Should this be on the copy?
        if rename_switch:
            rename_layers(use_scale=scale, al_dict=alignment_dict)

        dm_ = copy.deepcopy(dm) # Copy the datamodel previewmodel for this datamodel to add local fields for SWiFT
        substack = dm_()[start:end]
        # substack = dm()[start:end]
        n_tasks = n_skips = 0
        for layer in substack: # Operating on the Copy!
            if not layer['skipped']: n_tasks +=1
            else:                    n_skips +=1
        logger.info('# Sections (total)         : %d' % len(dm))
        logger.info('# Tasks (excluding skips)  : %d' % n_tasks)
        logger.info('# Skipped Layers           : %d' % n_skips)

        scale_val = get_scale_val(scale)
        for sec in substack:
            zpos = dm().index(sec)

            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta'] = {}
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['index'] = zpos
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['scale_val'] = scale_val
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['scale_key'] = scale
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['isRefinement'] = dm['data']['scales'][scale]['isRefinement']
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['destination_path'] = dm['data']['destination_path']
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['defaults'] = dm['data']['defaults']
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['image_src_size'] = dm['data']['scales'][scale]['image_src_size']
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['skipped'] = dm['data']['scales'][scale]['stack'][zpos]['skipped']
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['dev_mode'] = cfg.DEV_MODE
            dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['recipe_logging'] = cfg.RECIPE_LOGGING

            if dm['data']['scales'][scale]['isRefinement']:
                scale_prev = dm.scales()[dm.scales().index(scale) + 1]
                prev_scale_val = int(scale_prev[len('scale_'):])
                upscale = (float(prev_scale_val) / float(scale_val))
                init_afm = np.array(copy.deepcopy(dm['data']['scales'][scale_prev]['stack'][zpos]['alignment']['method_results']['affine_matrix']))
                # prev_method = scale_prev_dict[zpos]['current_method']
                # prev_afm = copy.deepcopy(np.array(scale_prev_dict[zpos]['alignment_history'][prev_method]['affine_matrix']))
                init_afm[0][2] *= upscale
                init_afm[1][2] *= upscale
                dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['init_afm'] = init_afm.tolist()
            else:
                dm['data']['scales'][scale]['stack'][zpos]['alignment']['meta']['init_afm'] = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()


        delete_correlation_signals(dm=dm, scale=scale, start=start, end=end)

        dest = dm['data']['destination_path']

        cpus = min(psutil.cpu_count(logical=False), TACC_MAX_CPUS, n_tasks)
        print(f'\n\n################ Computing Alignment ################\n')
        if end == None:
            end = len(dm)
        task_queue = TaskQueue(n_tasks=n_tasks, dest=dest, use_gui=use_gui)
        task_queue.taskPrefix = 'Computing Alignment for '
        task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in cfg.data()[start:end]]
        task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in dm['data']['scales'][scale]['stack'][start:end]]
        # START TASK QUEUE
        task_queue.start(cpus)
        # align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_recipe_alignment.py')
        align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'recipe_maker.py')
        # ADD ALIGNMENT TASKS TO QUEUE
        for sec in substack:
            zpos = dm_().index(sec)
            if not sec['skipped']:
                encoded_data = json.dumps(copy.deepcopy(dm['data']['scales'][scale]['stack'][zpos]))
                task_args = [sys.executable, align_job, encoded_data]
                task_queue.add_task(task_args)

        # task_queue.work_q.join()
        # cfg.mw.hud.post('Computing Alignment Using SWIM...')
        dt = task_queue.collect_results()
        dm.t_align = dt
        all_results = task_queue.task_dict


        # tasks = []
        # for sec in substack:
        #     zpos = dm_().index(sec)
        #     if not sec['skipped']:
        #         tasks.append(copy.deepcopy(dm['data']['scales'][scale]['stack'][zpos]))


        '''
        # ctx = mp.get_context('forkserver')
        # pbar = tqdm.tqdm(total=len(tasks), position=0, leave=True)
        # pbar.set_description("Computing Affines")
        # def update_tqdm(*a):
        #     pbar.update()
        # t0 = time.time()
        # # with ctx.Pool(processes=cpus) as pool:
        # with ThreadPool(processes=cpus) as pool:
        #     results = [pool.apply_async(func=run_recipe, args=(task,), callback=update_tqdm) for task in tasks]
        #     pool.close()
        #     all_results = [p.get() for p in results]
        #     pool.join()



        # t0 = time.time()
        # ctx = mp.get_context('forkserver')
        # all_results = []
        # with ctx.Pool(processes=cpus) as pool:
        #
        #     # all_results = pool.map(run_recipe, tasks)
        #     for result in tqdm.tqdm(pool.map(run_recipe, tasks)):
        #         all_results.append(result)


        # dm.t_align = time.time() - t0


        '''






        # def run_apply_async_multiprocessing(func, argument_list, num_processes):
        #
        #     pool = Pool(processes=num_processes)
        #
        #     results = [pool.apply_async(func=func, args=(*argument,), callback=update_pbar) if isinstance(argument, tuple) else pool.apply_async(
        #         func=func, args=(argument,), callback=update_pbar) for argument in argument_list]
        #     pool.close()
        #     result_list = [p.get() for p in results]
        #
        #     return result_list
        #
        # all_results = run_apply_async_multiprocessing(func=run_recipe, argument_list=tasks,
        #                                               num_processes=cpus)



        if cfg.CancelProcesses:
            logger.warning('Canceling Processes!')
            return

        # task_dict = {}
        # index_arg = 3
        # for k in task_queue.task_dict.keys():
        #     t = task_queue.task_dict[k]
        #     logger.critical(f"\nt = {t}\n\n")
        #     task_dict[int(t['args'][index_arg])] = t
        # task_list = [task_dict[k] for k in sorted(task_dict.keys())]
        # updated_model = copy.deepcopy(dm) # Integrate output of each task into a new combined datamodel previewmodel

        logger.info('Reading task results and updating data model...')

        al_stack_old = dm['data']['scales'][scale]['stack']

        # for tnum in range(len(task_list)):
        for tnum in range(len(all_results)):
        # for r in all_results:
            logger.info(f'Reading task results for {tnum}...')
            # Get the updated datamodel previewmodel from stdout for the task
            parts = all_results[tnum]['stdout'].split('---JSON-DELIMITER---')
            dm_text = None
            for p in parts:
                ps = p.strip()
                if ps.startswith('{') and ps.endswith('}'):
                    dm_text = p
            if dm_text != None:
                results_dict = json.loads(dm_text)
                layer_index = results_dict['alignment']['meta']['index']
                al_stack_old[layer_index] = results_dict


            # # For use with ThreadPool ONLY
            # layer_index = r['alignment']['meta']['index']
            # al_stack_old[r['alignment']['meta']['index']] = r



        #     if all_results[tnum]['statusBar'] == 'task_error':
        #         ref_fn = al_stack_old[layer_index]['fn_reference']
        #         base_fn = al_stack_old[layer_index]['filename']
        #         if use_gui:
        #             cfg.mw.hud.post('Alignment Task Error at: ' +
        #                                      str(all_results[tnum]['cmd']) + " " +
        #                                      str(all_results[tnum]['args']))
        #             cfg.mw.hud.post('Automatically Skipping Layer %d' % (layer_index), logging.WARNING)
        #             cfg.mw.hud.post(f'  ref img: %s\nbase img: %s' % (ref_fn,base_fn))
        #         else:
        #             logger.warning(('Alignment Task Error at: ' +
        #                                      str(all_results[tnum]['cmd']) + " " +
        #                                      str(all_results[tnum]['args'])))
        #             logger.warning('Automatically Skipping Layer %d' % (layer_index), logging.WARNING)
        #             logger.warning(f'  ref img: %s\nbase img: %s' % (ref_fn, base_fn))
        #         al_stack_old[layer_index]['skipped'] = True
        #     # need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)
        #
        # for i, layer in enumerate(cfg.data.get_iter(scale)):
        #     layer['alignment_history'][cfg.data.get_current_method(l=i)]['cumulative_afm'] = \
        #         cfg.data['data']['scales'][scale]['stack'][i]['alignment']['method_results']['cumulative_afm']

        SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=cfg.data.default_poly_order)



        for i, layer in enumerate(cfg.data.get_iter(scale)):
            layer['alignment_history'][cfg.data.get_current_method(l=i)]['cumulative_afm'] = \
                cfg.data['data']['scales'][scale]['stack'][i]['alignment']['method_results']['cumulative_afm']
            layer['alignment_history'][cfg.data.get_current_method(l=i)]['cafm_hash'] = \
                cfg.data.cafm_current_hash(l=i)

        if cfg.mw._isProjectTab():
            cfg.mw.updateCorrSignalsDrawer()
            cfg.mw.setTargKargPixmaps()


        save2file(dm=dm,name=dm.dest())

        if not swim_only:
            if use_gui:
                if cfg.mw._isProjectTab():
                    if not cfg.pt._toggleAutogenerate.isChecked():
                        logger.info('Toggle auto-generate is OFF. Returning...')
                        return
                if cfg.ignore_pbar:
                    cfg.nProcessDone += 1
                    cfg.mw.updatePbar()
                    cfg.mw.setPbarText('Generating Alignment...')

            try:
                # if cfg.USE_EXTRA_THREADING and use_gui:
                #     cfg.mw.worker = BackgroundWorker(fn=GenerateAligned(
                #         dm, scale_key, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui))
                #     cfg.mw.threadpool.start(cfg.mw.worker)
                # else:
                GenerateAligned(dm, scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui)

            except:
                print_exception()
            finally:
                logger.info('Generate Alignment Finished')

            if cfg.ignore_pbar and use_gui:
                cfg.nProcessDone += 1
                cfg.mw.updatePbar()
                cfg.mw.setPbarText('Generating Aligned Thumbnail...')

            thumbnailer = Thumbnailer()
            try:
                # if cfg.USE_EXTRA_THREADING and use_gui:
                #     cfg.mw.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(start=start, end=end, dest=dest, scale_key=scale_key, use_gui=use_gui))
                #     cfg.mw.threadpool.start(cfg.mw.worker)
                # else:
                thumbnailer.reduce_aligned(start=start, end=end, dest=dest, scale=scale, use_gui=use_gui)
            except:
                print_exception()
            finally:
                logger.info('Generate Aligned Thumbnails Finished')

            if cfg.ignore_pbar:
                cfg.nProcessDone += 1
                cfg.mw.updatePbar()
                cfg.mw.setPbarText('Aligning')

        return dm

def update_pbar(value):
    # logger.info(f"value: {value}")
    cfg.mw.pbar.setValue(cfg.mw.pbar.value()+1)


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        # sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))


def delete_correlation_signals(dm, scale, start, end):
    logger.info('')
    for i in range(start, end):
        sigs = dm.get_signals_filenames(s=scale, l=i)
        # logger.info(f'Deleting:\n{sigs}')
        for f in sigs:
            if os.path.isfile(f):  # this makes the code more robust
                os.remove(f)

# def delete_correlation_signals(dm, scale_key, start, end, dest):
#     logger.info('')
#     for i in range(start, end):
#         # sigs = cfg.data.get_signals_filenames(s=scale_key, l=i)
#         sigs = get_signals_filenames(pdscale=scale_key)
#         dir = os.path.join(sest, scale_key, 'signals')
#         basename = os.path.basename(dm.base_image_name(s=s, l=l))
#         filename, extension = os.path.splitext(basename)
#         paths = os.path.join(dir, '%s_%s_*%s' % (filename, self.current_method, extension))
#         names = glob(paths)
#         # logger.info(f'Search Path: {paths}\nReturning: {names}')
#         return natural_sort(names)
#         logger.info(f'Deleting:\n{sigs}')
#         for f in sigs:
#             if os.path.isfile(f):  # this makes the code more robust
#                 logger.info(f"Removing file '%s'" % f)
#                 os.remove(f)



# def get_signals_filenames(destination, scale_key):
#     dir = os.path.join(self.dest(), s, 'signals')
#     basename = os.path.basename(dm.base_image_name(s=s, l=l))
#     filename, extension = os.path.splitext(basename)
#     paths = os.path.join(dir, '%s_%s_*%s' % (filename, self.current_method, extension))
#     names = glob(paths)
#     # logger.info(f'Search Path: {paths}\nReturning: {names}')
#     return natural_sort(names)

def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)

def checkForTiffs(path) -> bool:
    '''Returns True or False dependent on whether aligned images have been generated for the current s.'''
    files = glob.glob(path + '/*.tif')
    if len(files) < 1:
        logger.debug('Zero aligned TIFs were found at this s - Returning False')
        return False
    else:
        logger.debug('One or more aligned TIFs were found at this s - Returning True')
        return True

def write_run_to_file(dm, scale=None):
    logger.critical('Writing run to file...')
    if scale == None: scale = dm.scale_key
    # snr_avg = 'SNR=%.3f' % dm.snr_average(scale_key=scale_key)
    timestamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    results = 'results'
    # swim_input = 'swim=%.3f' % dm.swim_window()
    # whitening_input = 'whitening=%.3f' % dm.whitening()
    # details = [date, time, s, _swimWindowControl, sb_whiteningControl, snr_avg]
    scale_str = 's' + str(get_scale_val(scale))
    details = [scale_str, results, timestamp]
    fn = '_'.join(details) + '.json'
    of = Path(os.path.join(dm.dest(), scale, 'history', fn))
    of.parent.mkdir(exist_ok=True, parents=True)
    with open(of, 'w') as f:
        json.dump(dm['data']['scales'][scale], f, indent=4)


def rename_layers(use_scale, al_dict):
    logger.info('rename_layers:')
    source_dir = os.path.join(cfg.data.dest(), use_scale, "img_src")
    for layer in al_dict:
        image_name = None
        if 'base' in layer['images'].keys():
            image = layer['images']['base']
            try:
                image_name = os.path.basename(image['filename'])
                destination_image_name = os.path.join(source_dir, image_name)
                shutil.copyfile(image.image_file_name, destination_image_name)
            except:
                logger.warning('Something went wrong with renaming the alignment layers')
                pass


def get_scale_val(scale_of_any_type) -> int:
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            return scale
        else:
            while scale.startswith('scale_'):
                scale = scale[len('scale_'):]
            return int(scale)
    except:
        logger.warning('Unable to return s value')


def print_exception():
    tstamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}]\nError Type : {exi[0]}\nError Value : {exi[1]}\n{traceback.format_exc()}"
    logger.warning(txt)

    if cfg.data:
        lf = os.path.join(cfg.data.dest(), 'logs', 'exceptions.log')
        with open(lf, 'a+') as f:
            f.write('\n' + txt)

'''
SWIM argument string: ww_416 -i 2 -w -0.68 -x -256 -y 256  /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.102.tif 512.000000 512.000000  1.000000 0.000000 -0.000000 1.000000


'''

def save2file(dm, name):
    data_cp = copy.deepcopy(dm)
    # data_cp.make_paths_relative(start=cfg.data.dest())
    data_cp_json = data_cp.to_dict()

    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp_json)
    name = dm.dest()
    logger.info(f'---- SAVING  ----\n{name}')
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    # logger.info('Save Name: %s' % name)
    with open(name, 'w') as f:
        f.write(proj_json)


if __name__ == '__main__':
    logger.info('Running ' + __file__ + '.__main__()')
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', help='Path to project file')
    parser.add_argument('--scale_key', help='Scale to use')
    parser.add_argument('--start', default=0, help='Section index to start at')
    parser.add_argument('--end', default=None, help='Section index to end at')
    parser.add_argument('--bounding_box', default=False, help='Bounding Box On/Off')
    args = parser.parse_args()
    logger.info(f'args : {args}')
    # os.environ['QT_API'] = args.api
    if args.path:
        path = args.path
    else:
        path = '/Users/joelyancey/glanceem_swift/test_projects/test4.swiftir'

    with open(path, 'r') as f:
        data = json.load(f)

    if args.scale:
        scale = args.scale
    else:
        # scale_key = data['data']['current_scale']
        scale = 'scale_4'
    start = args.start
    end = args.end
    dm = ComputeAffines(scale=scale, path=path, start=start, end=end, use_gui=False, bounding_box=args.bounding_box)
    save2file(dm=dm, name=dm.dest())


