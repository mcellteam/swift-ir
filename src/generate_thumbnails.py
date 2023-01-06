#!/usr/bin/env python3

# NOTE: Start with smallest s already generated for efficiency
# 200px x 200px might be good thumbnail size to start with

import os
import sys
import shutil
import psutil
import time
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, get_scale_key, create_project_structure_directories, \
    get_best_path, get_bindir, natural_sort, show_mp_queue_results, kill_task_queue
from .mp_queue import TaskQueue

__all__ = ['generate_thumbnails']

logger = logging.getLogger(__name__)


def generate_thumbnails(dm):
    logger.info('Generating Thumbnails...')
    cfg.main_window.hud.post('Preparing To Generate Thumbnails...')

    # Todo: If the smallest s happens to be less that thumbnail size, just copy smallest s for thumbnails

    target_thumbnail_size = 200 # 200x200
    smallest_scale_key = natural_sort(dm['data']['scales'].keys())[-1]
    scale_val = get_scale_val(smallest_scale_key)
    size = dm.image_size(s=smallest_scale_key)
    siz_x, siz_y = size[0], size[1]
    siz_start = siz_x if siz_x <= siz_y else siz_y
    scale_factor = int(siz_start/target_thumbnail_size)
    logger.info("Thumbnail Scaling Factor : %s" % str(scale_factor))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=dm.n_layers(),
                           parent=cfg.main_window,
                           pbar_text='Generating Thumbnails (%d Cores)...' % cpus)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'

    od = os.path.join(dm.dest(), 'thumbnails')
    if os.path.exists(od):
        try:
            shutil.rmtree(od)
        except:
            print_exception()
    os.mkdir(od)

    iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')
    task_queue.start(cpus)

    it = dm.get_iter(s=smallest_scale_key)
    for i, layer in enumerate(it):
        fn = os.path.abspath(layer['images']['base']['filename'])
        ofn = os.path.join(od, os.path.split(fn)[1])
        dm['data']['thumbnails'].append(ofn)
        scale_arg = '+%d' % scale_val
        of_arg = 'of=%s' % ofn
        if_arg = '%s' % fn
        task = [iscale2_c, scale_arg, of_arg, if_arg]
        task_queue.add_task(task)
        if cfg.PRINT_EXAMPLE_ARGS:
            if i in [0, 1, 2]:
                logger.info('Example Arguments (ID: %d):\n%s' % (i, str(task)))
        # if i in [0, 1]:
        #     logger.info('\nTQ Params:\n  1: %s\n  2: %s\n  3: %s\n  4: %s' % (iscale2_c, scale_arg, of_arg, if_arg))

    dt = task_queue.collect_results()
    show_mp_queue_results(task_queue=task_queue, dt=dt)
    kill_task_queue(task_queue=task_queue)

    logger.info('<<<< Thumbnail Generation Complete <<<<')

