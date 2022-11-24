#!/usr/bin/env python3

import os
import sys
import copy
import json
import time
import shutil
import psutil
import logging
from datetime import datetime
from pathlib import Path
import src.config as cfg
from src.mp_queue import TaskQueue
from src.helpers import print_exception, rename_layers, remove_aligned, get_scale_val, are_aligned_images_generated, \
    show_mp_queue_results, show_mp_queue_results, kill_task_queue


__all__ = ['compute_affines','rename_layers','remove_aligned']

logger = logging.getLogger(__name__)

def compute_affines(scale, start_layer=0, num_layers=-1):
    '''Compute the python_swiftir transformation matrices for the current s stack of images according to Recipe1.'''
    logger.critical('Computing Affines...')

    rename_switch = False
    alignment_dict = cfg.data['data']['scales'][scale]['alignment_stack']
    scale_val = get_scale_val(scale)
    last_layer = len(alignment_dict) if num_layers == -1 else start_layer + num_layers
    alignment_option = cfg.data['data']['scales'][scale]['method_data']['alignment_option']
    logger.debug('Use Scale: %s\nCode Mode: %s\nUse File IO: %d' % (scale, cfg.CODE_MODE, cfg.USE_FILE_IO))
    logger.debug('Start Layer: %d / # Layers: %d' % (start_layer, num_layers))

    if are_aligned_images_generated():
        cfg.main_window.hud.post(f'Removing Aligned Images for Scale Level {scale_val}')
        remove_aligned(use_scale=scale, start_layer=start_layer) #0903 Moved into conditional
        cfg.main_window.hud.done()

    cfg.data.clear_method_results(scale=scale, start=start_layer, end=last_layer) #1109 Should this be on the copy?
    if rename_switch:
        rename_layers(use_scale=scale, al_dict=alignment_dict)

    dm = copy.deepcopy(cfg.data) # Copy the data previewmodel for this data to add local fields for SWiFT
    alstack = dm['data']['scales'][scale]['alignment_stack']
    substack = alstack[start_layer:last_layer]
    n_tasks = n_skips = 0
    for layer in substack: # Operating on the Copy!
        # layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        # layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'
        if not layer['skipped']: n_tasks +=1
        else:                    n_skips +=1
    logger.info('# Layers (total)           : %d' % cfg.data.n_layers())
    logger.info('# Tasks (excluding skips)  : %d' % n_tasks)
    logger.info('# Skipped Layers           : %d' % n_skips)
    temp_file = os.path.join(cfg.data.dest(), "temp_project_file.json")
    with open(temp_file, 'w') as f:
        f.write(cfg.data.to_json())
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Computing Alignments - Scale %d - %d Cores' % (get_scale_val(scale), cpus))
    task_queue.start(cpus)
    align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_single_alignment.py')
    for layer in substack:
    # for index, layer in enumerate(cfg.data):
        index = alstack.index(layer)
        if layer['skipped']:
            logger.info(f'Layer {index} is skipped')
        else:
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
            task_queue.add_task(task_args)
            if index in range(start_layer, start_layer + 3):
                e = [str(p) for p in task_args] # example
                logger.info("Layer #%d (example):\n%s\n%s\n%s\n%s" % (index, e[0],e[1],e[2]," ".join(e[3::])))

    # task_queue.work_q.join()
    cfg.main_window.hud.post('Computing Alignment Using SWIM...')
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    cfg.main_window.hud.done()
    show_mp_queue_results(task_queue=task_queue, dt=dt)

    # Sort the tasks by layers rather than by process IDs
    task_dict = {}
    for k in task_queue.task_dict.keys():
        t = task_queue.task_dict[k]
        task_dict[int(t['args'][5])] = t

    task_list = [task_dict[k] for k in sorted(task_dict.keys())]
    updated_model = copy.deepcopy(cfg.data) # Integrate output of each task into a new combined data previewmodel

    for tnum in range(len(task_list)):

        if cfg.USE_FILE_IO:
            # Get the updated data previewmodel from the file written by single_alignment_job
            output_dir = os.path.join(os.path.split(temp_file)[0], scale)
            output_file = "single_alignment_out_" + str(tnum) + ".json"
            with open(os.path.join(output_dir, output_file), 'r') as f:
                dm_text = f.read()

        else:
            # Get the updated data previewmodel from stdout for the task
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

            # Get the same s from both the old and new data models
            al_stack_old = updated_model['data']['scales'][scale]['alignment_stack']
            al_stack_new = fdm_new['data']['scales'][scale]['alignment_stack']
            layer_index = int(task_list[tnum]['args'][5]) # may differ from tnum!
            al_stack_old[layer_index] = al_stack_new[layer_index]
            if task_list[tnum]['statusBar'] == 'task_error':
                ref_fn = al_stack_old[layer_index]['images']['ref']['filename']
                base_fn = al_stack_old[layer_index]['images']['base']['filename']
                cfg.main_window.hud.post('Alignment Task Error at: ' +
                                         str(task_list[tnum]['cmd']) + " " +
                                         str(task_list[tnum]['args']))
                cfg.main_window.hud.post('Automatically Skipping Layer %d' % (layer_index), logging.WARNING)
                cfg.main_window.hud.post(f'  ref img: %s\nbase img: %s' % (ref_fn,base_fn))
                al_stack_old[layer_index]['skipped'] = True
            need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)

    kill_task_queue(task_queue=task_queue)
    cfg.data = updated_model #0809-
    write_run_to_file()
    logger.info('<<<< Compute Affines End <<<<')


def write_run_to_file(scale=None):
    if scale == None: scale = cfg.data.scale()
    snr_avg = 'SNR=%.3f' % cfg.data.snr_average(scale=scale)
    timestamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    results = 'results'
    swim_input = 'swim=%.3f' % cfg.main_window.get_swim_input()
    whitening_input = 'whitening=%.3f' % cfg.main_window.get_whitening_input()
    # details = [date, time, s, swim_input, whitening_input, snr_avg]
    scale_str = 's' + str(get_scale_val(scale))
    details = [scale_str, results, timestamp]
    fn = '_'.join(details) + '.json'
    of = Path(os.path.join(cfg.data.dest(), scale, 'history', fn))
    of.parent.mkdir(exist_ok=True, parents=True)
    with open(of, 'w') as f:
        json.dump(cfg.data['data']['scales'][scale], f, indent=4)


'''
SWIM argument string: ww_416 -i 2 -w -0.68 -x -256 -y 256  /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.102.tif 512.000000 512.000000  1.000000 0.000000 -0.000000 1.000000


'''