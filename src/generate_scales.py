#!/usr/bin/env python3

import os
import sys
import shutil
import platform
import psutil
import time
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, get_scale_key, \
    create_project_structure_directories, get_best_path, do_scales_exist
from .mp_queue import TaskQueue

__all__ = ['generate_scales']

logger = logging.getLogger(__name__)


def generate_scales():
    logger.critical('>>>>>>>> Generate Scales Start <<<<<<<<')
    image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.data['data']['scales'].keys())]
    logger.info("Scale Factors : %s" % str(image_scales_to_run))
    proj_path = cfg.data['data']['destination_path']
    n_tasks = cfg.data.n_imgs() * (cfg.data.n_scales() - 1)  #0901 #Refactor
    # cfg.main_window.pbar_max(n_tasks)
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window)
    task_queue.tqdm_desc = 'Scaling Images'
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 1
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    logger.critical('my_path is %s' % my_path)
    my_system = platform.system()
    my_node = platform.node()
    '''TODO: Check for SWiFT-IR executables at startup'''
    '''TODO: Keep local current scale value as member of MainWindow class, to reduce read ops.'''
    if my_system == 'Darwin':
        bindir = 'bin_darwin'
    elif my_system == 'Linux':
        bindir = 'bin_tacc' if '.tacc.utexas.edu' in my_node else 'bin_linux'
    else:
        logger.error("System Could Not Be Resolved - Exiting")
        return
    iscale2_c = os.path.join(my_path, 'lib', bindir, 'iscale2')
    try:
        os.path.isfile(iscale2_c)
    except:
        print_exception()
        cfg.main_window.hud.post("'iscale2_c' Not Found At Path %s. It Must Be Compiled." % iscale2_c, logging.ERROR)
        return

    cfg.main_window.hud.post("Creating Project Directory Structure...")
    try:
        # for scale in sorted(image_scales_to_run):
        for scale in cfg.data.scales():
            subdir_path = os.path.join(proj_path, scale)
            create_project_structure_directories(subdir_path)
    except:
        print_exception()
        cfg.main_window.hud.post("There Was A Problem Creating Directory Structure", logging.WARNING)
        return
    cfg.main_window.hud.done()

    # #0804+
    # if str(image_scales_to_run) == '[1]':
    #     logger.info('Only one scale is requested, so not calling mp_queue - Returning')
    #     return

    task_queue.start(cpus)

    for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
        logger.debug('Looping, Scale ', scale)
        cfg.main_window.hud.post("Preparing to Downsample Scale %s..." % str(scale))
        scale_key = get_scale_key(scale)
        for i, layer in enumerate(cfg.data['data']['scales'][scale_key]['alignment_stack']):
            fn = os.path.abspath(layer['images']['base']['filename'])
            ofn = os.path.join(proj_path, scale_key, 'img_src', os.path.split(fn)[1])
            layer['align_to_ref_method']['method_options'].update({'initial_scale': cfg.DEFAULT_INITIAL_SCALE})
            layer['align_to_ref_method']['method_options'].update({'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION})

            if scale == 1:

                '''Scale 1 Only'''
                if get_best_path(fn) != get_best_path(ofn):
                    # The paths are different so make the link
                    try:
                        os.unlink(ofn)
                    except:
                        pass

                    try:
                        os.symlink(fn, ofn)
                    except:
                        # Not all operating systems allow linking for all users (Windows 10 requires admin rights)
                        logger.warning("Unable to link from %s to %s. Copying instead." % (fn, ofn))
                        try:
                            shutil.copy(fn, ofn)
                        except:
                            logger.warning("Unable to link or copy from " + fn + " to " + ofn)
            else:
                '''All Scales Other Than 1'''

                try:
                    if os.path.split(os.path.split(os.path.split(fn)[0])[0])[1].startswith('scale_'):
                        '''This may be only run when re-scaling. Needs verification'''
                        # Convert the source from whatever scale is currently processed to scale_1
                        p, f = os.path.split(fn)
                        p, r = os.path.split(p)
                        p, s = os.path.split(p)
                        fn = os.path.join(p, 'scale_1', r, f)
                        if i == 1:
                            pass
                            # logger.info('fn = ', fn)
                            # logger.info('p = ', p)
                            # logger.info('r = ', r)
                            # logger.info('s = ', s)
                            # logger.info(fn)

                    if cfg.CODE_MODE == 'python':
                        task_queue.add_task(cmd=sys.executable,
                                         args=['job_single_scale.py', str(scale), str(fn), str(ofn)], wd='.')
                    else:
                        scale_arg = '+%d' % (scale)
                        outfile_arg = 'of=%s' % (ofn)
                        infile_arg = '%s' % (fn)
                        # task_queue.add_task (cmd=iscale2_c, args=[scale_arg, outfile_arg, infile_arg], wd='.')
                        task_queue.add_task([iscale2_c, scale_arg, outfile_arg, infile_arg])
                        # if i == 1:
                        logger.info('\ntask_queue Parameters (Example):\n1: %s\n2: %s\n3: %s\n4: %s' %
                                     (iscale2_c, scale_arg, outfile_arg, infile_arg))

                except:
                    cfg.main_window.hud.post("Error adding tasks to the task queue - Canceling", logging.ERROR)
                    print_exception()
                    return

            layer['images']['base']['filename'] = ofn  # Update Data Model
        cfg.main_window.hud.done()


    ### Join the queue here to ensure that all have been generated before returning
    # task_queue.work_q.join() # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    cfg.main_window.hud.post('Generating Scale Hierarchy...')
    t0 = time.time()
    task_queue.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    try: task_queue.end_tasks()
    except: pass
    logger.info('Stopping task queue...')
    task_queue.stop()
    logger.info('Deleting task queue...')
    del task_queue
    dt = time.time() - t0
    # cfg.main_window.hud.done()
    cfg.main_window.hud.post("Process generate_scales Completed in %.2f Seconds" % dt)

    logger.critical('>>>>>>>> Generate Scales End <<<<<<<<')

    '''
    ____task_queue Parameters (Example)____
    (1) : iscale2_c : /Users/joelyancey/glanceem_swift/alignEM/src/src/lib/bin_darwin/iscale2
    (2) : scale_arg : +2
    (3) : outfile_arg : of=/Users/joelyancey/glanceEM_SWiFT/test_projects/test993/scale_2/img_src/R34CA1-BS12.104.tif
    (4) : infile_arg : /Users/joelyancey/glanceEM_SWiFT/test_images/r34_tifs/R34CA1-BS12.104.tif
    '''