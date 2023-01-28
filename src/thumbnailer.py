#!/usr/bin/env python3

'''Generates thumbnails for use with an AlignEM-SWiFT project.'''

import os
import shutil
import psutil
import inspect
import logging
from math import ceil
from glob import glob

import src.config as cfg
from src.mp_queue import TaskQueue
from src.funcs_image import ImageSize
from src.helpers import print_exception, get_appdir, get_bindir, natural_sort, absFilePaths

__all__ = ['Thumbnailer']

logger = logging.getLogger(__name__)

class Thumbnailer:
    def __init__(self):
        logger.info('')
        self.iscale2_c = os.path.join(get_appdir(), 'lib', get_bindir(), 'iscale2')


    def generate_main(self):
        logger.info('Generating Source Thumbnails...')
        coarsest_scale = cfg.data.smallest_scale()
        src = os.path.join(cfg.data.dest(), coarsest_scale, 'img_src')
        od = os.path.join(cfg.data.dest(), 'thumbnails')
        dt = self.generate_thumbnails(src=src, od=od, rmdir=True)
        cfg.data.set_t_thumbs(dt)


    def generate_aligned(self, start, end):
        src = os.path.join(cfg.data.dest(), cfg.data.scale(), 'img_aligned')
        od = os.path.join(cfg.data.dest(), cfg.data.scale(), 'thumbnails_aligned')
        self.generate_thumbnails(src=src, od=od, rmdir=False, prefix='', start=start, end=end)


    def generate_corr_spot(self, start, end):
        src = os.path.join(cfg.data.dest(), cfg.data.scale(), 'corr_spots')
        od = os.path.join(cfg.data.dest(), cfg.data.scale(), 'thumbnails_corr_spots')
        self.generate_thumbnails(src=src, od=od, rmdir=False, prefix='', start=start, end=end)


    def generate_thumbnails(self, src, od, rmdir=False, prefix='', start=0, end=None):
        caller = inspect.stack()[1].function

        logger.critical('Thumbnail Source Directory: %s' % src)
        # siz_x, siz_y = ImageSize(next(absFilePaths(src)))
        try:
            siz_x, siz_y = ImageSize(next(absFilePaths(src)))
            scale_factor = ceil(max(siz_x, siz_y) / cfg.TARGET_THUMBNAIL_SIZE)
        except:
            print_exception()
            logger.warning('Are there any files in this directory? - Returning')
            return 1

        if rmdir:
            if os.path.exists(od):
                try:    shutil.rmtree(od)
                except: print_exception()
        if not os.path.exists(od):
            os.mkdir(od)

        logger.critical(f'Thumbnail Scaling Factor:{scale_factor}, Target : {cfg.TARGET_THUMBNAIL_SIZE}')

        glob_str = os.path.join(src, '*.tif')
        filenames = natural_sort(glob(glob_str))[start:end]
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
        pbar_text = 'Generating Thumbnails (%d Cores)...' % cpus
        task_queue = TaskQueue(n_tasks=cfg.data.n_sections(), parent=cfg.main_window, pbar_text=pbar_text)
        task_queue.start(cpus)

        for i, fn in enumerate(filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            scale_arg = '+%d' % scale_factor
            of_arg = 'of=%s' % ofn
            if_arg = '%s' % fn
            task = [self.iscale2_c, scale_arg, of_arg, if_arg]
            task_queue.add_task(task)
            if cfg.PRINT_EXAMPLE_ARGS:
                if i in (0, 1, 2):
                    logger.info('\nTQ Params:\n  1: %s\n  2: %s\n  3: %s\n  4: %s'
                                % (self.iscale2_c, scale_arg, of_arg, if_arg))

        dt = task_queue.collect_results()

        logger.info('<<<< Thumbnail Generation Complete <<<<')
        return dt


