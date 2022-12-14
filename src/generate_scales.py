#!/usr/bin/env python3

import os
import sys
import shutil
import psutil
import time
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, create_project_structure_directories, \
    get_bindir, show_mp_queue_results, kill_task_queue, create_scale_one_symlinks
from .mp_queue import TaskQueue

__all__ = ['generate_scales']

logger = logging.getLogger(__name__)


def generate_scales():
    logger.info('Generating Scales...')
    n_tasks = cfg.data.n_layers() * (cfg.data.n_scales() - 1)  #0901 #Refactor
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Scale Image Hierarchy - %d Cores' % cpus)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    for s in cfg.data.scales():
        create_project_structure_directories(s)
    iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')
    task_queue.start(cpus)
    src = cfg.data.source_path()
    dest = cfg.data.dest()
    imgs = cfg.data.basefilenames()
    create_scale_one_symlinks(src=src, dest=dest, imgs=imgs)

    for s in cfg.data.downscales():  # value string '1 2 4'
        scale_val = get_scale_val(s)
        logger.info('Scale %d:' % scale_val)
        cfg.main_window.hud.post("Preparing to Downsample Scale %d..." % scale_val)
        for i, layer in enumerate(cfg.data.get_iter(s)):
            base       = cfg.data.base_image_name(s=s, l=i)
            if_arg     = os.path.join(src, base)
            ofn        = os.path.join(cfg.data.dest(), s, 'img_src', os.path.split(if_arg)[1])
            of_arg     = 'of=%s' % ofn
            scale_arg  = '+%d' % scale_val
            task_queue.add_task([iscale2_c, scale_arg, of_arg, if_arg])
            if i == 0:
                logger.info('\nTQ Params (Example):\n  1: %s\n  2: %s\n  3: %s\n  4: %s' % (iscale2_c, scale_arg, of_arg, if_arg))
            # if cfg.CODE_MODE == 'python':
            #     task_queue.add_task(cmd=sys.executable,
            #                         args=['src/job_single_scale.py', str(s), str(fn), str(ofn)], wd='.')
            layer['images']['base']['filename'] = ofn
        cfg.main_window.hud.done()
    cfg.main_window.hud.post('Generating Scale Image Hierarchy...')
    dt = task_queue.collect_results()
    show_mp_queue_results(task_queue=task_queue, dt=dt)
    kill_task_queue(task_queue=task_queue)
    logger.info('<<<< Generate Scales End <<<<')

    '''
    ____task_queue Parameters (Example)____
    (1) : iscale2_c : /Users/joelyancey/glanceem_swift/alignEM/src/src/lib/bin_darwin/iscale2
    (2) : scale_arg : +2
    (3) : of_arg : of=/Users/joelyancey/glanceEM_SWiFT/test_projects/test993/scale_2/img_src/R34CA1-BS12.104.tif
    (4) : if_arg : /Users/joelyancey/glanceEM_SWiFT/test_images/r34_tifs/R34CA1-BS12.104.tif
    '''