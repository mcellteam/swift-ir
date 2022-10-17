#!/usr/bin/env python3

import os
import sys
import shutil
import psutil
import time
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, get_scale_key, create_project_structure_directories, \
    get_best_path, is_tacc, is_linux, is_mac
from .mp_queue import TaskQueue

__all__ = ['generate_scales']

logger = logging.getLogger(__name__)


def generate_scales():
    logger.critical('>>>> Generate Scales <<<<')
    image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.data['data']['scales'].keys())]
    logger.info("Scale Factors : %s" % str(image_scales_to_run))
    n_tasks = cfg.data.n_imgs() * (cfg.data.n_scales() - 1)  #0901 #Refactor
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window)
    task_queue.tqdm_desc = 'Scaling Images'
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    for s in cfg.data.scales():
        create_project_structure_directories(s)

    if is_tacc():     bindir = 'bin_tacc'
    elif is_mac():    bindir = 'bin_darwin'
    elif is_linux():  bindir = 'bin_linux'
    else:             logger.error("Operating System Could Not Be Resolved"); return

    iscale2_c = os.path.join(my_path, 'lib', bindir, 'iscale2')
    task_queue.start(cpus)
    for scale in sorted(image_scales_to_run):  # value string '1 2 4'
        cfg.main_window.hud.post("Preparing to Downsample Scale %s..." % str(scale))
        scale_key = get_scale_key(scale)
        for i, layer in enumerate(cfg.data['data']['scales'][scale_key]['alignment_stack']):
            fn = os.path.abspath(layer['images']['base']['filename'])
            ofn = os.path.join(cfg.data.dest(), scale_key, 'img_src', os.path.split(fn)[1])
            layer['align_to_ref_method']['method_options'].update({'initial_scale': cfg.DEFAULT_INITIAL_SCALE})
            layer['align_to_ref_method']['method_options'].update({'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION})

            if scale == 1:
                '''Scale 1 Only'''
                if get_best_path(fn) != get_best_path(ofn):
                    try:    os.unlink(ofn)
                    except: pass
                    try:
                        os.symlink(fn, ofn)
                    except:
                        logger.warning("Unable to link from %s to %s. Copying instead." % (fn, ofn))
                        try:     shutil.copy(fn, ofn)
                        except:  logger.warning("Unable to link or copy from " + fn + " to " + ofn)
            else:
                '''All Other Scales'''
                # if os.path.split(os.path.split(os.path.split(fn)[0])[0])[1].startswith('scale_'):
                #     '''This may be only run when re-scaling. Needs verification'''
                #     # Convert the source from whatever scale is currently processed to scale_1
                #     p, f = os.path.split(fn)
                #     p, r = os.path.split(p)
                #     p, s = os.path.split(p)
                #     fn = os.path.join(p, 'scale_1', r, f)
                if cfg.CODE_MODE == 'python':
                    task_queue.add_task(cmd=sys.executable,
                                        args=['job_single_scale.py', str(scale), str(fn), str(ofn)], wd='.')
                else:
                    scale_arg = '+%d' % scale
                    of_arg = 'of=%s' % ofn
                    if_arg = '%s' % fn
                    task_queue.add_task([iscale2_c, scale_arg, of_arg, if_arg])
                    logger.info('\nTQ Params:\n1: %s\n2: %s\n3: %s\n4: %s' % (iscale2_c, scale_arg, of_arg, if_arg))

            layer['images']['base']['filename'] = ofn
        cfg.main_window.hud.done()
    cfg.main_window.hud.post('Generating Scale Hierarchy...')
    t0 = time.time()
    task_queue.collect_results()
    try: task_queue.end_tasks()
    except: print_exception()
    task_queue.stop()
    del task_queue
    dt = time.time() - t0
    cfg.main_window.hud.post("Process generate_scales Completed in %.2f Seconds" % dt)

    '''Set more lenient permissions on Tifs'''
    for scale in cfg.data.scales():
        logger.info('Setting permissions on generated images for scale %s...' % scale)
        path = os.path.join(cfg.data.dest(), scale, 'img_src')
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                os.chmod(path, 0o766)

    logger.critical('>>>> Generate Scales End <<<<')

    '''
    ____task_queue Parameters (Example)____
    (1) : iscale2_c : /Users/joelyancey/glanceem_swift/alignEM/src/src/lib/bin_darwin/iscale2
    (2) : scale_arg : +2
    (3) : of_arg : of=/Users/joelyancey/glanceEM_SWiFT/test_projects/test993/scale_2/img_src/R34CA1-BS12.104.tif
    (4) : if_arg : /Users/joelyancey/glanceEM_SWiFT/test_images/r34_tifs/R34CA1-BS12.104.tif
    '''