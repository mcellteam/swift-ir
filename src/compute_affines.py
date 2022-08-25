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
from .run_json_project import run_json_project
from .save_bias_analysis import save_bias_analysis
from .em_utils import are_images_imported, get_cur_scale_key, get_scale_val, print_alignment_layer, print_snr_list, \
    remove_aligned, update_datamodel, are_aligned_images_generated


__all__ = ['compute_affines','rename_layers','remove_aligned']

logger = logging.getLogger(__name__)

# def compute_affines():
def compute_affines(use_scale, start_layer=0, num_layers=-1):
    '''Compute the python_swiftir transformation matrices for the current scale stack of images according to Recipe1.'''
    logger.critical('>>>>>>>> Compute Affines Start <<<<<<<<')

    if are_images_imported():
        pass
    else:
        cfg.main_window.hud.post("Images must be imported prior to alignment.", logger.WARNING)
        return

    rename_switch = False
    # Create links or copy files in the expected directory structure
    # os.symlink(src, dst, target_is_directory=False, *, dir_fd=None)
    scale_dict = cfg.project_data['data']['scales'][use_scale]
    alignment_dict = cfg.project_data['data']['scales'][use_scale]['alignment_stack']
    alignment_option = scale_dict['method_data']['alignment_option']
    logger.debug('Use Scale: %s\nCode Mode: %s\nUse File IO: %d' % (use_scale, cfg.CODE_MODE, cfg.USE_FILE_IO))
    logger.debug('Start Layer: %d / # Layers: %d' % (start_layer, num_layers))

    cfg.main_window.alignment_status_checkbox.setChecked(False)
    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing Aligned Images for Scale Level %s...' % use_scale[-1])
    remove_aligned(use_scale=use_scale, start_layer=start_layer)
    logger.info('Clearing method_results data...')
    cfg.project_data.clear_method_results(scale_key=use_scale)
    cfg.main_window.hud.post("Using SWiFT-IR to Compute Affine Transformations (Affine: %s, Scale: %s)..."
                             % (alignment_option, use_scale[-1]))

    print_snr_list()
    # ensure_proper_data_structure() #0709

    if rename_switch:
        rename_layers(use_scale=use_scale, alignment_dict=alignment_dict)

    # Copy the data model for this project to add local fields for SWiFT
    # dm = copy.deepcopy(cfg.project_data)
    # dm = copy.deepcopy(cfg.project_data.to_dict())
    dm = copy.deepcopy(cfg.project_data)
    alignment_dict = dm['data']['scales'][use_scale]['alignment_stack']
    for layer in alignment_dict: # Operating on the Copy!
        layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'

    # project = copy.deepcopy(cfg.project_data)
    # alstack = project['data']['scales'][use_scale]['alignment_stack']
    alstack = copy.deepcopy(cfg.project_data['data']['scales'][use_scale]['alignment_stack'])

    if cfg.PARALLEL_MODE:
        logger.debug('cfg.PARALLEL_MODE was True...')
        '''Run the project as a series of jobs'''
        # Write the entire project as a single JSON file with a unique stable name for this run
        logger.info("Copying project file to 'project_runner_job_file.json'")

        run_project_name = os.path.join(cfg.project_data.name(), "project_runner_job_file.json")
        with open(run_project_name, 'w') as f:
            # f.write(json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True).encode(cfg.project_data.to_json()))
            f.write(cfg.project_data.to_json())

        # foo = os.path.join(cfg.project_data.name(), str(time.time()) + '.json')
        # with open(foo, 'w') as f:
        #     # f.write(json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True).encode(cfg.project_data.to_json()))
        #     f.write(cfg.project_data.to_json())

        # task_queue = TaskQueue(n_tasks=len(alstack))
        task_queue = TaskQueue(n_tasks=len(alstack))
        task_queue.tqdm_desc = 'Computing Affines'
        cpus = min(psutil.cpu_count(logical=False), 48)
        cfg.main_window.hud.post("Task Queue is using %d CPUs" % cpus)
        task_queue.start(cpus)
        align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_single_alignment.py')

        for i,layer in enumerate(alstack):
            lnum = alstack.index(layer)
            skip = False
            try:
                skip = layer['skip']
            except:
                logger.warning('skip could not be read in project_data')
            if skip is True:
                logger.debug('Skipping layer %s' % str(lnum))
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
                    # logger.info("Starting mp_queue with args (First Layer Only, Example):\n\n%s\n" % "\n".join(example))
                    logger.info("Starting mp_queue with args (First Layer Only, Example):\n%s\n" % "\n".join(example))


                task_queue.add_task(task_args)

        # task_queue.work_q.join()
        t0 = time.time()
        cfg.main_window.hud.post('Waiting for Alignment Tasks to Complete...')
        # **********************************
        task_queue.collect_results()
        # **********************************
        dt = time.time() - t0
        cfg.main_window.hud.post('Alignment Completed in %.2f seconds' % (dt))

        # Check status of all tasks and report final tally
        n_tasks = len(task_queue.task_dict.keys())
        n_success = 0
        n_queued = 0
        n_failed = 0
        for k in task_queue.task_dict.keys():
            task_item = task_queue.task_dict[k]
            status = task_item['status']
            if status == 'completed':  n_success += 1
            elif status == 'queued':  n_queued += 1
            elif status == 'task_error':
                cfg.main_window.hud.post('\nTask Error:')
                cfg.main_window.hud.post('   CMD:    %s' % (str(task_item['cmd'])))
                cfg.main_window.hud.post('   ARGS:   %s' % (str(task_item['args'])))
                cfg.main_window.hud.post('   STDERR: %s\n' % (str(task_item['stderr'])))
                n_failed += 1
            pass

        cfg.main_window.hud.post('%d Alignment Tasks Completed in %.2f seconds' % (n_tasks, dt))
        cfg.main_window.hud.post('  Num Successful:   %d' % (n_success))
        cfg.main_window.hud.post('  Num Still Queued: %d' % (n_queued))
        cfg.main_window.hud.post('  Num Failed:       %d' % (n_failed))

        # Sort the tasks by layers rather than by process IDs
        task_dict = {}
        for k in task_queue.task_dict.keys():
            t = task_queue.task_dict[k]
            task_dict[int(t['args'][5])] = t

        task_list = [task_dict[k] for k in sorted(task_dict.keys())]

        logger.info("Copying 'cfg.project_data'...")
        # updated_model = copy.deepcopy(cfg.project_data) # Integrate output of each task into a new combined data model
        updated_model = copy.deepcopy(cfg.project_data) # Integrate output of each task into a new combined data model

        use_scale_new_key = updated_model['data']['current_scale']
        # if use_scale > 0:
        # use_scale_new_key = get_scale_key(use_scale)
    
        for tnum in range(len(task_list)):

            if cfg.USE_FILE_IO:
                # Get the updated data model from the file written by single_alignment_job
                output_dir = os.path.join(os.path.split(run_project_name)[0], get_cur_scale_key())
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

            # logger.debug('\ndm_text:')
            # logger.debug(dm_text)
            if dm_text != None:
                results_dict = json.loads(dm_text)
                fdm_new = results_dict['data_model']

                # Get the same scale from both the old and new data models
                use_scale_new = fdm_new['data']['scales'][use_scale_new_key]
                use_scale_old = updated_model['data']['scales'][use_scale_new_key]
                al_stack_old = use_scale_old['alignment_stack']
                al_stack_new = use_scale_new['alignment_stack']

                lnum = int(task_list[tnum]['args'][5])

                al_stack_old[lnum] = al_stack_new[lnum]

                if task_list[tnum]['status'] == 'task_error':
                    ref_fn = al_stack_old[lnum]['images']['ref']['filename']
                    base_fn = al_stack_old[lnum]['images']['base']['filename']
                    cfg.main_window.hud.post('Alignment Task Error at: ' + str(task_list[tnum]['cmd']) + " " + str(task_list[tnum]['args']))
                    cfg.main_window.hud.post('Automatically Skipping Layer %d' % (lnum))
                    cfg.main_window.hud.post('ref image: %s   base image: %s' % (ref_fn, base_fn))
                    al_stack_old[lnum]['skip'] = True
                need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)
        
        task_queue.stop()
        del task_queue
        
        logger.info('\nExample Layer from Alignment Stack:')
        try:
            al_layer = updated_model['data']['scales'][use_scale]['alignment_stack'][-1]
            logger.info(json.dumps(al_layer, indent=2))
        except:
            logger.info('No Alignment Layer Found')

        cfg.project_data = updated_model #0809-
        bias_data_path = os.path.join(cfg.project_data['data']['destination_path'], use_scale, 'bias_data')
        save_bias_analysis(cfg.project_data['data']['scales'][use_scale]['alignment_stack'], bias_data_path) # <-- call to save bias data
        
        print_alignment_layer()

    else:
        '''Run the project directly in Serial mode. Does not generate aligned images.'''
        logger.info('Calling run_json_project (cfg.PARALLEL_MODE was False)...')
        updated_model, need_to_write_json = run_json_project(
                project=copy.deepcopy(cfg.project_data.to_dict()),
                alignment_option=alignment_option,
                use_scale=use_scale,
                swiftir_code_mode=cfg.CODE_MODE,
                start_layer=start_layer,
                num_layers=num_layers)
        logger.info('need_to_write_json = %s' % str(need_to_write_json))
        if need_to_write_json:
            cfg.project_data = updated_model
        else:
            update_datamodel(updated_model)


    logger.critical('>>>>>>>> Compute Affines End <<<<<<<<')

def rename_layers(use_scale, alignment_dict):
    source_dir = os.path.join(cfg.project_data['data']['destination_path'], use_scale, "img_src")
    for layer in alignment_dict:
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


