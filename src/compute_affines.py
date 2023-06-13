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
import numpy as np

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


__all__ = ['ComputeAffines']

logger = logging.getLogger(__name__)

def ComputeAffines(scale, path, start=0, end=None, use_gui=True, renew_od=False, reallocate_zarr=False, stageit=False, swim_only=False, bounding_box=False, dm=None):
    '''Compute the python_swiftir transformation matrices for the current s stack of images according to Recipe1.'''
    caller = inspect.stack()[1].function
    scale_val = get_scale_val(scale)
    # logger.info(f'use_gui = {use_gui}')

    logger.info(f'>>>> ComputeAffines [{caller}] >>>>')

    if cfg.CancelProcesses:
        cfg.mw.warn('Canceling Compute Affine Tasks')
    else:
        logger.info(f'\n\n################ Computing Affines ################\n')
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

        # alignment_option = dm['data']['scales'][scale]['method_data']['alignment_option']
        logger.info('Start Layer: %s /End layer: %s' % (str(start), str(end)))

        # path = os.path.join(dm.dest(), scale, 'img_aligned')
        # if checkForTiffs(path):
        #     # al_substack = dm['data']['scales'][scale]['stack'][start:]
        #     # remove_aligned(al_substack) #0903 Moved into conditional
        #     dm.remove_aligned(scale, start, end)

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
        temp_file = os.path.join(dm.dest(), "temp_project_file.json")
        with open(temp_file, 'w') as f:
            f.write(dm.to_json())


        delete_correlation_signals(dm=dm, scale=scale, start=start, end=end)

        dest = dm['data']['destination_path']

        cpus = min(psutil.cpu_count(logical=False), TACC_MAX_CPUS, n_tasks)
        pbar_text = 'Computing Scale %d Transforms w/ SWIM (%d Cores)...' % (scale_val, cpus)
        logger.info(f'\n\n################ Computing Alignment ################\n')

        if use_gui:
            task_queue = TaskQueue(n_tasks=n_tasks, dest=dest, parent=cfg.mw, pbar_text=pbar_text)
        else:
            task_queue = TaskQueue(n_tasks=n_tasks, dest=dest, use_gui=use_gui)
        task_queue.taskPrefix = 'Computing Alignment for '
        # task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in cfg.data()[start:end]]
        # if end == None:
        #     end = len(dm)
        task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in dm['data']['scales'][scale]['stack'][start:end]]

        # START TASK QUEUE
        task_queue.start(cpus)
        align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_recipe_alignment.py')

        # ADD ALIGNMENT TASKS TO QUEUE
        for sec in substack:
            zpos = dm_().index(sec)
            # zpos = dm().index(sec)

            if not sec['skipped']:
                task_args = [sys.executable,
                             align_job,             # Python program to run (single_alignment_job)
                             temp_file,             # Temp project file name
                             str(scale_val),        # Scale to use or 0
                             str(zpos),             # Section index to run recipe alignment
                             str(USE_FILE_IO),      # Use File IO instead of Pipe
                             str(DEV_MODE),         # Use development mode
                             ]
                task_queue.add_task(task_args)
                if use_gui:
                    if cfg.PRINT_EXAMPLE_ARGS:
                        if zpos in range(start, start + 3):
                            logger.info("Section #%d (example):\n%s" % (zpos, " ".join(task_args)))

        # task_queue.work_q.join()
        # cfg.mw.hud.post('Computing Alignment Using SWIM...')
        dt = task_queue.collect_results()
        dm.t_align = dt

        t0 = time.time()
        if use_gui:
            if cfg.CancelProcesses:
                return

        # Sort the tasks by layers rather than by process IDs
        task_dict = {}
        index_arg = 3
        for k in task_queue.task_dict.keys():
            t = task_queue.task_dict[k]
            task_dict[int(t['args'][index_arg])] = t

        task_list = [task_dict[k] for k in sorted(task_dict.keys())]
        # updated_model = copy.deepcopy(dm) # Integrate output of each task into a new combined datamodel previewmodel

        logger.info('Reading task results and updating data model...')

        for tnum in range(len(task_list)):

            if USE_FILE_IO:
                # Get the updated datamodel previewmodel from the file written by single_alignment_job
                output_dir = os.path.join(os.path.split(temp_file)[0], scale)
                output_file = "single_alignment_out_" + str(tnum) + ".json"
                with open(os.path.join(output_dir, output_file), 'r') as f:
                    dm_text = f.read()

            else:
                # Get the updated datamodel previewmodel from stdout for the task
                parts = task_list[tnum]['stdout'].split('---JSON-DELIMITER---')
                dm_text = None
                for p in parts:
                    ps = p.strip()
                    if ps.startswith('{') and ps.endswith('}'):
                        dm_text = p

            if dm_text != None:
                # This gets run normally...

                results_dict = json.loads(dm_text)
                fdm_new = results_dict['data_model']

                # Get the same s from both the old and new datamodel models
                # al_stack_old = updated_model['data']['scales'][scale]['stack']
                al_stack_old = dm['data']['scales'][scale]['stack']
                al_stack_new = fdm_new['data']['scales'][scale]['stack']
                layer_index = int(task_list[tnum]['args'][index_arg]) # may differ from tnum!
                al_stack_old[layer_index] = al_stack_new[layer_index]
                if task_list[tnum]['statusBar'] == 'task_error':
                    ref_fn = al_stack_old[layer_index]['reference']
                    base_fn = al_stack_old[layer_index]['filename']
                    if use_gui:
                        cfg.mw.hud.post('Alignment Task Error at: ' +
                                                 str(task_list[tnum]['cmd']) + " " +
                                                 str(task_list[tnum]['args']))
                        cfg.mw.hud.post('Automatically Skipping Layer %d' % (layer_index), logging.WARNING)
                        cfg.mw.hud.post(f'  ref img: %s\nbase img: %s' % (ref_fn,base_fn))
                    else:
                        logger.warning(('Alignment Task Error at: ' +
                                                 str(task_list[tnum]['cmd']) + " " +
                                                 str(task_list[tnum]['args'])))
                        logger.warning('Automatically Skipping Layer %d' % (layer_index), logging.WARNING)
                        logger.warning(f'  ref img: %s\nbase img: %s' % (ref_fn, base_fn))
                    al_stack_old[layer_index]['skipped'] = True
                need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)


        SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=cfg.data.default_poly_order)

        save2file(dm=dm,name=dm.dest())

        try:
            os.remove(temp_file)
        except:
            print_exception()

        write_run_to_file(dm)


        # if cfg.ignore_pbar:
        #     cfg.nProcessDone +=1
        #     cfg.mw.updatePbar()
        #     cfg.mw.setPbarText('Scaling Correlation Signal Thumbnails...')
        # try:
        #     # if cfg.USE_EXTRA_THREADING and use_gui:
        #     #     cfg.mw.worker = BackgroundWorker(fn=cfg.thumb.reduce_signals(start=start, end=end))
        #     #     cfg.mw.threadpool.start(cfg.mw.worker)
        #     # else:
        #     cfg.thumb.reduce_signals(start=start, end=end, dest=dest, scale=scale, use_gui=use_gui)
        # except:
        #     print_exception()
        #     cfg.mw.warn('There Was a Problem Generating Corr Spot Thumbnails')



        # logger.info('Collating Correlation Signal Images...')
        # job_script = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_collate_spots.py')
        # task_queue = TaskQueue(n_tasks=len(substack),
        #                        parent=cfg.mw,
        #                        pbar_text='Collating Scale %s Correlation Signal Images...' % (scale_val))
        # task_queue.start(cpus)
        #
        # for i, layer in enumerate(substack):
        #     if layer['skipped']:
        #         continue
        #     fn = os.path.basename(layer['images']['base']['filename'])
        #     out = os.path.join(signals_raw_dir, 'collated_' + fn)
        #     # out = os.path.join(dm.dest(), 'collated_' + fn)
        #     task_args = [sys.executable,
        #                  job_script,            # Python program to run (single_alignment_job)
        #                  fn,
        #                  out
        #                  ]
        #     task_queue.add_task(task_args)
        #     if cfg.PRINT_EXAMPLE_ARGS:
        #         if i in range(0,3):
        #             logger.info("Layer #%d (example):\n%s" % (i, "\n".join(task_args)))
        #
        # try:
        #     dt = task_queue.collect_results()
        # except:
        #     print_exception()
        #     logger.warning('Task Queue encountered a problem')

        if not swim_only:
            if use_gui:
                if not cfg.mw._toggleAutogenerate.isChecked():
                    logger.info('Toggle auto-generate is OFF. Returning...')
                    return
                if cfg.ignore_pbar:
                    cfg.nProcessDone += 1
                    cfg.mw.updatePbar()
                    cfg.mw.setPbarText('Generating Alignment...')

            try:
                # if cfg.USE_EXTRA_THREADING and use_gui:
                #     cfg.mw.worker = BackgroundWorker(fn=GenerateAligned(
                #         dm, scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui))
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
                #     cfg.mw.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(start=start, end=end, dest=dest, scale=scale, use_gui=use_gui))
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





def delete_correlation_signals(dm, scale, start, end):
    logger.info('')
    for i in range(start, end):
        sigs = dm.get_signals_filenames(s=scale, l=i)
        # logger.info(f'Deleting:\n{sigs}')
        for f in sigs:
            if os.path.isfile(f):  # this makes the code more robust
                os.remove(f)

# def delete_correlation_signals(dm, scale, start, end, dest):
#     logger.info('')
#     for i in range(start, end):
#         # sigs = cfg.data.get_signals_filenames(s=scale, l=i)
#         sigs = get_signals_filenames(pdscale=scale)
#         dir = os.path.join(sest, scale, 'signals')
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



# def get_signals_filenames(pd, scale):
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
    if scale == None: scale = dm.scale
    # snr_avg = 'SNR=%.3f' % dm.snr_average(scale=scale)
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
    logger.info('---- SAVING DATA TO PROJECT FILE ----')
    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp_json)
    name = dm.dest()
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    logger.info('Save Name: %s' % name)
    with open(name, 'w') as f:
        f.write(proj_json)


if __name__ == '__main__':
    logger.info('Running ' + __file__ + '.__main__()')
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', help='Path to project file')
    parser.add_argument('--scale', help='Scale to use')
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
        # scale = data['data']['current_scale']
        scale = 'scale_4'
    start = args.start
    end = args.end
    dm = ComputeAffines(scale=scale, path=path, start=start, end=end, use_gui=False, bounding_box=args.bounding_box)
    save2file(dm=dm, name=dm.dest())


