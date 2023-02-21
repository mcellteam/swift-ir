#!/usr/bin/env python3

import os
import sys
import copy
import json
import glob
import time
import shutil
import psutil
import logging
from datetime import datetime
from pathlib import Path
import neuroglancer as ng
import src.config as cfg
from src.mp_queue import TaskQueue
from src.helpers import print_exception, rename_layers, get_scale_val


__all__ = ['compute_affines']

logger = logging.getLogger(__name__)

def compute_affines(scale, start=0, end=None):
    '''Compute the python_swiftir transformation matrices for the current s stack of images according to Recipe1.'''
    scale_val = get_scale_val(scale)
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    pbar_text = 'Computing Scale %d Transforms w/ SWIM (%d Cores)...' % (scale_val, cpus)
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
    else:
        logger.critical('Computing Affines...')

        dm = cfg.data

        # if ng.is_server_running():
        #     logger.info('Stopping Neuroglancer...')
        #     ng.server.stop()

        rename_switch = False
        alignment_dict = dm['data']['scales'][scale]['alignment_stack']

        alignment_option = dm['data']['scales'][scale]['method_data']['alignment_option']
        logger.info('Start Layer: %s / # Layers: %s' % (str(start), str(end)))

        # path = os.path.join(dm.dest(), scale, 'img_aligned')
        # if checkForTiffs(path):
        #     # al_substack = dm['data']['scales'][scale]['alignment_stack'][start:]
        #     # remove_aligned(al_substack) #0903 Moved into conditional
        #     dm.remove_aligned(scale, start, end)

        corr_spots_dir = os.path.join(dm.dest(), scale, 'corr_spots')
        if not os.path.exists(corr_spots_dir):
            os.mkdir(corr_spots_dir)

        dm.clear_method_results(scale=scale, start=start, end=end) #1109 Should this be on the copy?
        if rename_switch:
            rename_layers(use_scale=scale, al_dict=alignment_dict)

        dm_ = copy.deepcopy(dm) # Copy the datamodel previewmodel for this datamodel to add local fields for SWiFT
        alstack = dm_['data']['scales'][scale]['alignment_stack']
        substack = alstack[start:end]
        n_tasks = n_skips = 0
        for layer in substack: # Operating on the Copy!
            # # layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
            # # layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
            # layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'
            if not layer['skipped']: n_tasks +=1
            else:                    n_skips +=1
        logger.info('# Sections (total)         : %d' % len(dm))
        logger.info('# Tasks (excluding skips)  : %d' % n_tasks)
        logger.info('# Skipped Layers           : %d' % n_skips)
        temp_file = os.path.join(dm.dest(), "temp_project_file.json")
        with open(temp_file, 'w') as f:
            f.write(dm.to_json())

        task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text=pbar_text)

        # START TASK QUEUE
        task_queue.start(cpus)
        align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_single_alignment.py')

        # ADD ALIGNMENT TASKS TO QUEUE
        for layer in substack:
            index = alstack.index(layer)
            if not layer['skipped']:
                task_args = [sys.executable,
                             align_job,            # Python program to run (single_alignment_job)
                             temp_file,            # Temp project file name
                             alignment_option,     # Init, Refine, or Apply
                             str(scale_val),       # Scale to use or 0
                             str(cfg.CODE_MODE),   # Python or C mode
                             str(index),           # First l number to run from Project file #ATTN!
                             str(1),               # Number of layers to run                 #ATTN!
                             str(cfg.USE_FILE_IO)  # Use File IO instead of Pipe
                             ]
                # if index == 5:
                #     task_args[3] = 'bogus_align'
                # if index == 8:
                #     task_args[1] = 'bogus_script.py'
                task_queue.add_task(task_args)
                if cfg.PRINT_EXAMPLE_ARGS:
                    if index in range(start, start + 3):
                        e = [str(p) for p in task_args] # example
                        logger.info("Layer #%d (example):\n%s\n%s\n%s\n%s" % (index, e[0],e[1],e[2]," ".join(e[3::])))

        # task_queue.work_q.join()
        # cfg.main_window.hud.post('Computing Alignment Using SWIM...')
        dt = task_queue.collect_results()
        dm.set_t_align(dt, s=scale)

        if cfg.CancelProcesses:
            return

        # Sort the tasks by layers rather than by process IDs
        task_dict = {}
        for k in task_queue.task_dict.keys():
            t = task_queue.task_dict[k]
            task_dict[int(t['args'][5])] = t

        task_list = [task_dict[k] for k in sorted(task_dict.keys())]
        updated_model = copy.deepcopy(dm) # Integrate output of each task into a new combined datamodel previewmodel

        for tnum in range(len(task_list)):

            if cfg.USE_FILE_IO:
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
                al_stack_old = updated_model['data']['scales'][scale]['alignment_stack']
                al_stack_new = fdm_new['data']['scales'][scale]['alignment_stack']
                layer_index = int(task_list[tnum]['args'][5]) # may differ from tnum!
                al_stack_old[layer_index] = al_stack_new[layer_index]
                if task_list[tnum]['statusBar'] == 'task_error':
                    ref_fn = al_stack_old[layer_index]['reference']
                    base_fn = al_stack_old[layer_index]['filename']
                    cfg.main_window.hud.post('Alignment Task Error at: ' +
                                             str(task_list[tnum]['cmd']) + " " +
                                             str(task_list[tnum]['args']))
                    cfg.main_window.hud.post('Automatically Skipping Layer %d' % (layer_index), logging.WARNING)
                    cfg.main_window.hud.post(f'  ref img: %s\nbase img: %s' % (ref_fn,base_fn))
                    al_stack_old[layer_index]['skipped'] = True
                need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)

        cfg.data = updated_model #0809-
        write_run_to_file(dm)

        # logger.info('Collating Correlation Spot Images...')
        # job_script = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_collate_spots.py')
        # task_queue = TaskQueue(n_tasks=len(substack),
        #                        parent=cfg.main_window,
        #                        pbar_text='Collating Scale %s Correlation Spot Images...' % (scale_val))
        # task_queue.start(cpus)
        #
        # for i, layer in enumerate(substack):
        #     if layer['skipped']:
        #         continue
        #     fn = os.path.basename(layer['images']['base']['filename'])
        #     out = os.path.join(corr_spots_dir, 'collated_' + fn)
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

        logger.info('<<<< Compute Affines End <<<<')


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
    if scale == None: scale = dm.scale()
    # snr_avg = 'SNR=%.3f' % dm.snr_average(scale=scale)
    timestamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    results = 'results'
    # swim_input = 'swim=%.3f' % dm.swim_window()
    # whitening_input = 'whitening=%.3f' % dm.whitening()
    # details = [date, time, s, _swimWindowControl, _whiteningControl, snr_avg]
    scale_str = 's' + str(get_scale_val(scale))
    details = [scale_str, results, timestamp]
    fn = '_'.join(details) + '.json'
    of = Path(os.path.join(dm.dest(), scale, 'history', fn))
    of.parent.mkdir(exist_ok=True, parents=True)
    with open(of, 'w') as f:
        json.dump(dm['data']['scales'][scale], f, indent=4)


'''
SWIM argument string: ww_416 -i 2 -w -0.68 -x -256 -y 256  /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.102.tif 512.000000 512.000000  1.000000 0.000000 -0.000000 1.000000


'''