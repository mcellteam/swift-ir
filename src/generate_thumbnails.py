#!/usr/bin/env python3

# NOTE: Start with smallest scale already generated for efficiency
# 200px x 200px might be good thumbnail size to start with

import os
import sys
import shutil
import psutil
import time
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, get_scale_key, create_project_structure_directories, \
    get_best_path, is_tacc, is_linux, is_mac, natural_sort, show_mp_queue_results, kill_task_queue
from .mp_queue import TaskQueue

__all__ = ['generate_thumbnails']

logger = logging.getLogger(__name__)


def generate_thumbnails():
    logger.info('>>>> Generate Thumbnails >>>>')
    cfg.main_window.hud.post('Preparing To Generate Thumbnails...')

    # Todo: If the smallest scale happens to be less that thumbnail size, just copy smallest scale for thumbnails

    target_thumbnail_size = 200 # 200x200

    # largest_scale = natural_sort(cfg.data['data']['scales'].keys())[0]
    smallest_scale_key = natural_sort(cfg.data['data']['scales'].keys())[-1]
    scale_val = get_scale_val(smallest_scale_key)

    siz_x, siz_y = cfg.data.image_size(s=smallest_scale_key)
    siz_start = siz_x if siz_x <= siz_y else siz_y

    scale_factor = int(siz_start/target_thumbnail_size)
    logger.info("Thumbnail Scaling Factor : %s" % str(scale_factor))

    n_tasks = cfg.data.n_imgs()
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Thumbnails - %d Cores' % cpus)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'

    od = os.path.join(cfg.data.dest(), 'thumbnails')
    if os.path.exists(od):
        try:
            shutil.rmtree(od)
        except:
            print_exception()
    os.mkdir(od)

    if is_tacc():     bindir = 'bin_tacc'
    elif is_mac():    bindir = 'bin_darwin'
    elif is_linux():  bindir = 'bin_linux'
    else:             logger.error("Operating System Could Not Be Resolved"); return
    iscale2_c = os.path.join(my_path, 'lib', bindir, 'iscale2')
    cfg.main_window.hud.done()
    task_queue.start(cpus)
    for i, layer in enumerate(cfg.data['data']['scales'][smallest_scale_key]['alignment_stack']):
        fn = os.path.abspath(layer['images']['base']['filename'])
        ofn = os.path.join(od, os.path.split(fn)[1])
        scale_arg = '+%d' % scale_val
        of_arg = 'of=%s' % ofn
        if_arg = '%s' % fn
        task_queue.add_task([iscale2_c, scale_arg, of_arg, if_arg])
        if i in [0, 1, 2]:
            logger.info('\nTQ Params:\n1: %s\n2: %s\n3: %s\n4: %s' % (iscale2_c, scale_arg, of_arg, if_arg))

    cfg.main_window.hud.post('Generating Thumbnails...')
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    cfg.main_window.hud.done()
    show_mp_queue_results(task_queue=task_queue, dt=dt)
    kill_task_queue(task_queue=task_queue)

    logger.info('<<<< Generate Thumbnails End <<<<')

