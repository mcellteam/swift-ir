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
from src.helpers import print_exception, rename_layers, remove_aligned, get_scale_val, are_aligned_images_generated


__all__ = ['compute_affines','rename_layers','remove_aligned']

logger = logging.getLogger(__name__)

def compute_affines(scale, start_layer=0, num_layers=-1):
    '''Compute the python_swiftir transformation matrices for the current s stack of images according to Recipe1.'''
    logger.critical('>>>> Compute Affines >>>>')

    rename_switch = False
    alignment_dict = cfg.data['data']['scales'][scale]['alignment_stack']
    alignment_option = cfg.data['data']['scales'][scale]['method_data']['alignment_option']
    logger.debug('Use Scale: %s\nCode Mode: %s\nUse File IO: %d' % (scale, cfg.CODE_MODE, cfg.USE_FILE_IO))
    logger.debug('Start Layer: %d / # Layers: %d' % (start_layer, num_layers))

    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %d...' % get_scale_val(scale))
        remove_aligned(use_scale=scale, start_layer=start_layer) #0903 Moved into conditional
        cfg.main_window.hud.done()

    cfg.data.clear_method_results(scale_key=scale)
    if rename_switch: rename_layers(use_scale=scale, al_dict=alignment_dict)

    dm = copy.deepcopy(cfg.data) # Copy the data model for this data to add local fields for SWiFT
    alignment_dict = dm['data']['scales'][scale]['alignment_stack']
    n_tasks = 0
    for layer in alignment_dict: # Operating on the Copy!
        layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'
        if not layer['skipped']: n_tasks += 1
    logger.info('# of tasks (after subtracting skips): %d' % n_tasks)

    alstack = copy.deepcopy(cfg.data['data']['scales'][scale]['alignment_stack'])
    # Write the entire data as a single JSON file with a unique stable name for this run
    logger.info("Writing Project Dictionary to 'project_runner_job_file.json'")
    run_project_name = os.path.join(cfg.data.dest(), "project_runner_job_file.json")
    with open(run_project_name, 'w') as f:
        # f.write(json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True).encode(cfg.data.to_json()))
        f.write(cfg.data.to_json())


    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Computing Alignments - Scale %d - %d Cores' % (get_scale_val(scale), cpus))
    task_queue.start(cpus)
    align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_single_alignment.py')

    for i,layer in enumerate(alstack):
        lnum = alstack.index(layer)

        if bool(layer['skipped']):
            logger.info('Skipping Layer %s' % str(lnum))
        else:
            task_args = [sys.executable,
                         align_job,  # Python program to run (single_alignment_job)
                         str(run_project_name),  # Project file name
                         str(alignment_option),  # Init, Refine, or Apply
                         str(get_scale_val(scale)),  # Scale to use or 0
                         str(cfg.CODE_MODE),  # Python or C mode
                         str(lnum),  # First l number to run from Project file
                         str(1),  # Number of layers to run
                         str(cfg.USE_FILE_IO)  # Use File IO instead of Pipe
                         ]
            if i in [0,1,2]:
                example = [str(p) for p in task_args]
                logger.info("Example Tasks (First 3 Tasks):\n%s\n" % "\n".join(example))

            task_queue.add_task(task_args)
            # logger.critical(str(task_args))

    # task_queue.work_q.join()
    cfg.main_window.hud.post('Computing Alignment w/ SWIM...')
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    cfg.main_window.hud.done()
    cfg.main_window.hud.post('Completed in %.2f seconds' % (dt))

    logger.info('Checking Status of Tasks...')
    n_tasks = len(task_queue.task_dict.keys())
    n_success, n_queued, n_failed = 0, 0, 0
    for k in task_queue.task_dict.keys():
        task_item = task_queue.task_dict[k]
        if task_item['statusBar'] == 'completed':
            # logger.info('\nCompleted:')
            # logger.info('   CMD:    %s' % (str(task_item['cmd'])))
            # logger.info('   ARGS:   %s' % (str(task_item['args'])))
            # logger.info('   STDERR: %s\n' % (str(task_item['stderr'])))
            n_success += 1
        elif task_item['statusBar'] == 'queued':
            # logger.warning('\nQueued:')
            # logger.warning('   CMD:    %s' % (str(task_item['cmd'])))
            # logger.info('   ARGS:   %s' % (str(task_item['args'])))
            # logger.warning('   STDERR: %s\n' % (str(task_item['stderr'])))
            n_queued += 1
        elif task_item['statusBar'] == 'task_error':
            logger.critical('\nTask Error:')
            logger.critical('   CMD:    %s' % (str(task_item['cmd'])))
            logger.critical('   ARGS:   %s' % (str(task_item['args'])))
            logger.critical('   STDERR: %s\n' % (str(task_item['stderr'])))
            n_failed += 1

    cfg.main_window.hud.post('%d Alignment Tasks Completed in %.2f seconds' % (n_tasks, dt))
    cfg.main_window.hud.post('  Num Successful:   %d' % n_success)
    cfg.main_window.hud.post('  Num Still Queued: %d' % n_queued)
    cfg.main_window.hud.post('  Num Failed:       %d' % n_failed)

    # Sort the tasks by layers rather than by process IDs
    task_dict = {}
    for k in task_queue.task_dict.keys():
        t = task_queue.task_dict[k]
        task_dict[int(t['args'][5])] = t

    # task_list = [task_dict[k] for k in sorted(task_dict.keys())]
    task_list = [task_dict[k] for k in sorted(task_dict.keys())]

    logger.info("Copying The Project Dictionary")
    updated_model = copy.deepcopy(cfg.data) # Integrate output of each task into a new combined data model

    for tnum in range(len(task_list)):


        if cfg.USE_FILE_IO:
            # Get the updated data model from the file written by single_alignment_job
            output_dir = os.path.join(os.path.split(run_project_name)[0], scale)
            output_file = "single_alignment_out_" + str(tnum) + ".json"
            with open(os.path.join(output_dir, output_file), 'r') as f:
                dm_text = f.read()

        else:
            # Get the updated data model from stdout for the task
            parts = task_list[tnum]['stdout'].split('---JSON-DELIMITER---')
            dm_text = None
            for p in parts:
                ps = p.strip()
                if ps.startswith('{') and ps.endswith('}'):
                    dm_text = p

        if dm_text != None:
            '''This gets run normally'''
            '''Bug is before this'''
            results_dict = json.loads(dm_text)
            fdm_new = results_dict['data_model']

            # Get the same s from both the old and new data models
            use_scale_new = fdm_new['data']['scales'][scale]
            use_scale_old = updated_model['data']['scales'][scale]
            al_stack_old = use_scale_old['alignment_stack']
            al_stack_new = use_scale_new['alignment_stack']

            lnum = int(task_list[tnum]['args'][5]) # may differ from tnum
            al_stack_old[lnum] = al_stack_new[lnum] ###

            if task_list[tnum]['statusBar'] == 'task_error':
                ref_fn = al_stack_old[lnum]['images']['ref']['filename']
                base_fn = al_stack_old[lnum]['images']['base']['filename']
                cfg.main_window.hud.post('Alignment Task Error at: ' + str(task_list[tnum]['cmd']) + " " + str(task_list[tnum]['args']))
                cfg.main_window.hud.post('Automatically Skipping Layer %d' % (lnum))
                cfg.main_window.hud.post('ref image: %s   base image: %s' % (ref_fn, base_fn))
                al_stack_old[lnum]['skipped'] = True
            need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)


    try: task_queue.end_tasks()
    except: print_exception()
    task_queue.stop()
    del task_queue

    # '''BUG OCCURS BEFORE THIS POINT'''
    # logger.info('\nExample Layer from Alignment Stack:')
    # try:
    #     al_layer = updated_model['data']['scales'][scale]['alignment_stack'][-1]
    #     logger.info(json.dumps(al_layer, indent=2))
    # except:
    #     logger.info('No Alignment Layer Found')


    cfg.data = updated_model #0809-
    # cfg.data['data']['scales'][scale]['alignment_stack']


    write_run_to_file()

    # print_alignment_layer()

    # '''Run the data directly in Serial mode. Does not generate aligned images.'''
    # updated_model, need_to_write_json = run_json_project(
    #         project=copy.deepcopy(cfg.data.to_dict()),
    #         alignment_option=alignment_option,
    #         scale=scale,
    #         swiftir_code_mode=cfg.CODE_MODE,
    #         start_layer=start_layer,
    #         num_layers=num_layers)
    # logger.info('need_to_write_json = %s' % str(need_to_write_json))
    # if need_to_write_json:
    #     cfg.data = updated_model
    # else:
    #     cfg.data.update_datamodel(updated_model)
    #     # cfg.main_window.refresh_all_images()

    logger.critical('<<<< Compute Affines End <<<<')

def write_run_to_file(scale=None):
    if scale == None: scale = cfg.data.scale()
    snr_avg = 'SNR=%.3f' % cfg.data.snr_average(scale=scale)
    date = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H%M%S")
    swim_input = 'swim=%.3f' % cfg.main_window.get_swim_input()
    whitening_input = 'whitening=%.3f' % cfg.main_window.get_whitening_input()
    details = [scale, date, time, swim_input, whitening_input, snr_avg]
    fn = '_'.join(details) + '.txt'
    of = Path(os.path.join(cfg.data.dest(), scale, 'history', fn))
    of.parent.mkdir(exist_ok=True, parents=True)
    with open(of, 'w') as f:
        json.dump(cfg.data['data']['scales'][scale], f, indent=4)


'''
SWIM argument string: ww_416 -i 2 -w -0.68 -x -256 -y 256  /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.102.tif 512.000000 512.000000  1.000000 0.000000 -0.000000 1.000000


'''