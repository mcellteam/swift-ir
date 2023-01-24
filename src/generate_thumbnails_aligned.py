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
    get_best_path, get_bindir, natural_sort
from .mp_queue import TaskQueue

__all__ = ['generate_thumbnails_aligned']

logger = logging.getLogger(__name__)


def generate_thumbnails_aligned(dm, layers=None):
    if layers == None:
        layers = range(0, dm.n_sections())
    logger.info('Generating Thumbnails...')
    cfg.main_window.hud.post('Preparing To Generate Thumbnails...')

    # Todo: If the smallest s happens to be less that thumbnail size, just copy smallest s for thumbnails

    target_thumbnail_size = cfg.TARGET_THUMBNAIL_SIZE
    smallest_scale_key = natural_sort(dm['data']['scales'].keys())[-1]
    scale_val = get_scale_val(smallest_scale_key)

    if dm.has_bb():
        size = dm.bounding_rect()[2:4]
    else:
        size = dm.image_size(s=smallest_scale_key)
    siz_x, siz_y = size[0], size[1]
    siz_start = siz_x if siz_x <= siz_y else siz_y
    scale_factor = int(siz_start/target_thumbnail_size)
    logger.info("Thumbnail Scaling Factor : %s" % str(scale_factor))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=dm.n_sections(),
                           parent=cfg.main_window,
                           pbar_text='Generating Thumbnails (%d Cores)...' % cpus)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'


    od = os.path.join(dm.dest(), dm.scale(), 'thumbnails')
    if not os.path.exists(od):
        os.makedirs(od)


    iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')
    task_queue.start(cpus)

    # it = dm.get_iter(s=smallest_scale_key)
    # for i, layer in enumerate(it):
    for layer in layers:

        # fn = os.path.abspath(layer['images']['aligned']['filename'])
        fn = os.path.abspath(dm['data']['scales'][dm.scale()]['alignment_stack'][layer]['images']['aligned']['filename'])
        ofn = os.path.join(od, os.path.split(fn)[1])
        # dm['data']['thumbnails'].append(ofn)
        scale_arg = '+%d' % scale_val
        of_arg = 'of=%s' % ofn
        if_arg = '%s' % fn
        task = [iscale2_c, scale_arg, of_arg, if_arg]
        task_queue.add_task(task)
        if cfg.PRINT_EXAMPLE_ARGS:
            if layer in [0, 1, 2]:
                logger.info('Example Arguments (ID: %d):\n%s' % (layer, str(task)))
        # if i in [0, 1]:
        #     logger.info('\nTQ Params:\n  1: %s\n  2: %s\n  3: %s\n  4: %s' % (iscale2_c, scale_arg, of_arg, if_arg))

    dt = task_queue.collect_results()

    logger.info('<<<< Thumbnail Generation Complete <<<<')

