#!/usr/bin/env python3

import os
import sys
import time
import copy
import json
import shutil
import psutil
import logging
import src.config as cfg
from .mp_queue import TaskQueue
# from .run_json_project import run_json_project
from .save_bias_analysis import save_bias_analysis
from .helpers import get_scale_val, print_alignment_layer, print_snr_list, \
    remove_aligned, are_aligned_images_generated


__all__ = ['compute_affines','rename_layers','remove_aligned']

logger = logging.getLogger(__name__)

def compute_affines(use_scale, start_layer=0, num_layers=-1):
    '''Compute the python_swiftir transformation matrices for the current scale stack of images according to Recipe1.'''
    logger.critical('>>>>>>>> Compute Affines Start <<<<<<<<')

    rename_switch = False
    alignment_dict = cfg.data['data']['scales'][use_scale]['alignment_stack']
    alignment_option = cfg.data['data']['scales'][use_scale]['method_data']['alignment_option']
    logger.debug('Use Scale: %s\nCode Mode: %s\nUse File IO: %d' % (use_scale, cfg.CODE_MODE, cfg.USE_FILE_IO))
    logger.debug('Start Layer: %d / # Layers: %d' % (start_layer, num_layers))

    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %d...' % get_scale_val(use_scale))
        remove_aligned(use_scale=use_scale, start_layer=start_layer) #0903 Moved into conditional

    cfg.data.clear_method_results(scale_key=use_scale)
    if rename_switch: rename_layers(use_scale=use_scale, al_dict=alignment_dict)

    dm = copy.deepcopy(cfg.data) # Copy the data model for this data to add local fields for SWiFT
    alignment_dict = dm['data']['scales'][use_scale]['alignment_stack']
    n_tasks = 0
    for layer in alignment_dict: # Operating on the Copy!
        layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'
        if not layer['skipped']: n_tasks += 1
    logger.info('# of tasks (after subtracting skips): %d' % n_tasks)

    alstack = copy.deepcopy(cfg.data['data']['scales'][use_scale]['alignment_stack'])
    # Write the entire data as a single JSON file with a unique stable name for this run
    logger.info("Writing Project Dictionary to 'project_runner_job_file.json'")
    run_project_name = os.path.join(cfg.data.dest(), "project_runner_job_file.json")
    with open(run_project_name, 'w') as f:
        # f.write(json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True).encode(cfg.data.to_json()))
        f.write(cfg.data.to_json())

    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window)
    cpus = min(psutil.cpu_count(logical=False), 48) - 1
    task_queue.start(cpus)
    align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_single_alignment.py')

    for i,layer in enumerate(alstack):
        lnum = alstack.index(layer)
        if bool(layer['skipped']):
            logger.info('Not Adding Task for Layer %s' % str(lnum))
        else:
            task_args = [sys.executable,
                         align_job,                          # Python program to run (single_alignment_job)
                         str(run_project_name),              # Project file name
                         str(alignment_option),              # Init, Refine, or Apply
                         str(get_scale_val(use_scale)),      # Scale to use or 0
                         str(cfg.CODE_MODE),                 # Python or C mode
                         str(lnum),                          # First layer number to run from Project file
                         str(1),                             # Number of layers to run
                         str(cfg.USE_FILE_IO)                # Use File IO instead of Pipe
                         ]
            if i == 0:
                example = [str(p) for p in task_args]
                logger.info("Starting mp_queue with args (First Layer Only, Example):\n%s\n" % "\n".join(example))
            task_queue.add_task(task_args)

    # task_queue.work_q.join()
    cfg.main_window.hud.post('Computing Alignment Using %d CPUs...' % cpus)
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    cfg.main_window.hud.done()
    cfg.main_window.hud.post('Alignment Completed in %.2f seconds' % (dt))

    logger.info('Checking Status of Tasks...')
    n_tasks = len(task_queue.task_dict.keys())
    n_success, n_queued, n_failed = 0, 0, 0
    for k in task_queue.task_dict.keys():
        task_item = task_queue.task_dict[k]
        if task_item['statusBar'] == 'completed':  n_success += 1
        elif task_item['statusBar'] == 'queued':  n_queued += 1
        elif task_item['statusBar'] == 'task_error':  n_failed += 1

    cfg.main_window.hud.post('%d Alignment Tasks Completed in %.2f seconds' % (n_tasks, dt))
    cfg.main_window.hud.post('  Num Successful:   %d' % n_success)
    cfg.main_window.hud.post('  Num Still Queued: %d' % n_queued)
    cfg.main_window.hud.post('  Num Failed:       %d' % n_failed)

    # Sort the tasks by layers rather than by process IDs
    task_dict = {}
    for k in task_queue.task_dict.keys():
        t = task_queue.task_dict[k]
        task_dict[int(t['args'][5])] = t

    task_list = [task_dict[k] for k in sorted(task_dict.keys())]

    logger.info("Copying The Project Dictionary")
    updated_model = copy.deepcopy(cfg.data) # Integrate output of each task into a new combined data model

    for tnum in range(len(task_list)):

        if cfg.USE_FILE_IO:
            # Get the updated data model from the file written by single_alignment_job
            output_dir = os.path.join(os.path.split(run_project_name)[0], use_scale)
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
            results_dict = json.loads(dm_text)
            fdm_new = results_dict['data_model']

            # Get the same scale from both the old and new data models
            use_scale_new = fdm_new['data']['scales'][use_scale]
            use_scale_old = updated_model['data']['scales'][use_scale]
            al_stack_old = use_scale_old['alignment_stack']
            al_stack_new = use_scale_new['alignment_stack']

            lnum = int(task_list[tnum]['args'][5])

            al_stack_old[lnum] = al_stack_new[lnum]

            if task_list[tnum]['statusBar'] == 'task_error':
                ref_fn = al_stack_old[lnum]['images']['ref']['filename']
                base_fn = al_stack_old[lnum]['images']['base']['filename']
                cfg.main_window.hud.post('Alignment Task Error at: ' + str(task_list[tnum]['cmd']) + " " + str(task_list[tnum]['args']))
                cfg.main_window.hud.post('Automatically Skipping Layer %d' % (lnum))
                cfg.main_window.hud.post('ref image: %s   base image: %s' % (ref_fn, base_fn))
                al_stack_old[lnum]['skipped'] = True
            need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)

    try: task_queue.end_tasks()
    except: pass
    task_queue.stop()
    del task_queue

    logger.info('\nExample Layer from Alignment Stack:')
    try:
        al_layer = updated_model['data']['scales'][use_scale]['alignment_stack'][-1]
        logger.info(json.dumps(al_layer, indent=2))
    except:
        logger.info('No Alignment Layer Found')

    cfg.data = updated_model #0809-
    bias_data_path = os.path.join(cfg.data['data']['destination_path'], use_scale, 'bias_data')
    save_bias_analysis(cfg.data['data']['scales'][use_scale]['alignment_stack'], bias_data_path) # <-- call to save bias data

    # print_alignment_layer()

    # '''Run the data directly in Serial mode. Does not generate aligned images.'''
    # logger.info('Calling run_json_project (cfg.PARALLEL_MODE was False)...')
    # updated_model, need_to_write_json = run_json_project(
    #         project=copy.deepcopy(cfg.data.to_dict()),
    #         alignment_option=alignment_option,
    #         use_scale=use_scale,
    #         swiftir_code_mode=cfg.CODE_MODE,
    #         start_layer=start_layer,
    #         num_layers=num_layers)
    # logger.info('need_to_write_json = %s' % str(need_to_write_json))
    # if need_to_write_json:
    #     cfg.data = updated_model
    # else:
    #     cfg.data.update_datamodel(updated_model)
    #     # cfg.main_window.refresh_all_images()

    logger.critical('>>>>>>>> Compute Affines End <<<<<<<<')

def rename_layers(use_scale, al_dict):
    source_dir = os.path.join(cfg.data['data']['destination_path'], use_scale, "img_src")
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



'''
SWIM argument string: ww_416 -i 2 -w -0.68 -x -256 -y 256  /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.102.tif 512.000000 512.000000  1.000000 0.000000 -0.000000 1.000000


'''