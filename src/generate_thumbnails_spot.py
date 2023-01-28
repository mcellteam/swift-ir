#!/usr/bin/env python3

# NOTE: Start with smallest s already generated for efficiency
# 200px x 200px might be good thumbnail size to start with

import os
import sys
import shutil
import psutil
import time
from glob import glob
from math import ceil
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, get_scale_key, create_project_structure_directories, \
    get_best_path, get_bindir, natural_sort, handleError
from .mp_queue import TaskQueue

__all__ = ['generate_thumbnails_aligned']

logger = logging.getLogger(__name__)


def generate_thumbnails_spot(dm, scale=None, layers=None):
    logger.info('>>>> Spot Thumbnail Generation Complete >>>>')
    if scale == None:  scale = dm.scale()
    if layers == None: layers = range(0, dm.n_sections())
    logger.info('Preparing To Generate Corr Spot Thumbnails...')

    target_thumbnail_size = cfg.TARGET_THUMBNAIL_SIZE
    scale_val = get_scale_val(scale)

    if dm.has_bb():
        size = dm.bounding_rect()[2:4]
    else:
        size = dm.image_size(s=scale)
    siz_x, siz_y = size[0], size[1]
    siz_start = siz_x if siz_x <= siz_y else siz_y
    scale_factor = ceil(siz_start/target_thumbnail_size)
    logger.critical(f'size: {size}, siz_start: {siz_start}, scale_factor_:{scale_factor}, '
                    f'target_thumbnail_size: {target_thumbnail_size}')
    logger.critical("Thumbnail Scaling Factor : %s" % str(scale_factor))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=dm.n_sections(), parent=cfg.main_window,
                           pbar_text='Generating Corr. Spot Thumbnails (%d Cores)...' % cpus)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'

    od = os.path.join(dm.dest(), dm.scale(), 'thumbnails_corr_spots')
    if not os.path.exists(od):
        os.makedirs(od)

    iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')
    task_queue.start(cpus)

    glob_str = os.path.join(cfg.data.dest(), cfg.data.scale(), 'corr_spots', '*.tif')
    filenames = natural_sort(glob(glob_str))

    if len(filenames) < 7:
        if filenames:
            name = os.path.basename(filenames[0])[12:]
            cfg.main_window.tell('Generating Correlation Spot Thumbnail for %s' % name)

    # Create Thumbs for Every File in the Folder
    # for i, file in enumerate(filenames):
    for i,fn in enumerate(filenames):
        # fn = os.path.abspath(layer['images']['aligned']['filename'])
        ofn = os.path.join(od, os.path.split(fn)[1])
        # dm['data']['thumbnails'].append(ofn)
        scale_arg = '+%d' % scale_val
        of_arg = 'of=%s' % ofn
        if_arg = '%s' % fn
        task = [iscale2_c, scale_arg, of_arg, if_arg]
        task_queue.add_task(task)
        if cfg.PRINT_EXAMPLE_ARGS:
            if i in [0, 1, 2]:
                logger.info('\nTQ Params:\n  1: %s\n  2: %s\n  3: %s\n  4: %s'
                            % (iscale2_c, scale_arg, of_arg, if_arg))

    dt = task_queue.collect_results()

    cfg.data.set_t_thumbs_spot(dt,s=scale)

    if cfg.KEEP_ORIGINAL_SPOTS:
        remove_path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'corr_spots')
        logger.info(f'Deleting Corr Spot Directory {remove_path}...')
        try:
            shutil.rmtree(remove_path, ignore_errors=True, onerror=handleError)
            shutil.rmtree(remove_path, ignore_errors=True, onerror=handleError)
        except:
            cfg.main_window.warn('An Error Was Encountered During Deletion of the Project Directory')
            print_exception()
        else:
            cfg.main_window.hud.done()

    logger.info('<<<< Spot Thumbnail Generation Complete <<<<')

