#!/usr/bin/env python3

'''Generates thumbnails for use with an AlignEM-SWiFT project.'''

import os
import shutil
import psutil
import inspect
import logging
import datetime
from math import floor, ceil
from glob import glob

import src.config as cfg
from src.mp_queue import TaskQueue
from src.funcs_image import ImageSize
from src.helpers import print_exception, get_appdir, get_bindir, natural_sort, absFilePaths

__all__ = ['Thumbnailer']

logger = logging.getLogger(__name__)
tnLogger = logging.getLogger('tnLogger')



class Thumbnailer:

    def __init__(self):
        logger.info('')
        self.iscale2_c = os.path.join(get_appdir(), 'lib', get_bindir(), 'iscale2')



    def generate_main(self):
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
        pbar_text = 'Generating Source Image Thumbnails (%d Cores)...' % cpus
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            logger.info('Generating Source Thumbnails...')
            coarsest_scale = cfg.data.smallest_scale()
            src = os.path.join(cfg.data.dest(), coarsest_scale, 'img_src')
            od = os.path.join(cfg.data.dest(), 'thumbnails')
            dt = self.generate_thumbnails(
                src=src, od=od, rmdir=True, prefix='', start=0, end=None, pbar_text=pbar_text, cpus=cpus)
            cfg.data.set_t_thumbs(dt)


    def generate_aligned(self, start, end):
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
        pbar_text = 'Generating Aligned Image Thumbnails (%d Cores)...' % cpus
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            src = os.path.join(cfg.data.dest(), cfg.data.scale(), 'img_aligned')
            od = os.path.join(cfg.data.dest(), cfg.data.scale(), 'thumbnails_aligned')
            dt = self.generate_thumbnails(
                src=src, od=od, rmdir=False, prefix='', start=start, end=end, pbar_text=pbar_text, cpus=cpus)
            cfg.data.set_t_thumbs_aligned(dt)


    def generate_corr_spot(self, start, end):
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2

        pbar_text = 'Generating Correlation Spot Thumbnails (%d Cores)...' % cpus
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            src = os.path.join(cfg.data.dest(), cfg.data.scale(), 'corr_spots')
            od = os.path.join(cfg.data.dest(), cfg.data.scale(), 'thumbnails_corr_spots')
            rmdir = True if (start == 0) and (end == None) else False

            baseFileNames = cfg.data.basefilenames()
            if not rmdir:
                #Special handling for corrspot files since they are variable in # and never 1:1 with project files
                for i in range(start,end):
                    old_thumbnails = glob(os.path.join(od, '*' + baseFileNames[i]))
                    for tn in old_thumbnails:
                        try:
                            os.remove(tn)
                        except:
                            logger.warning('Error removing expired thumbnail: %s' % tn)

            filenames = []
            for name in baseFileNames[start:end]:
                filenames.extend(glob(os.path.join(src, '*' + name)))

            tnLogger.info('Generating the following corr spot thumbnails:\n%s' %str(filenames))

            dt = self.generate_thumbnails(src=src, od=od,
                                          rmdir=rmdir, prefix='',
                                          start=start, end=end,
                                          pbar_text=pbar_text, cpus=cpus,
                                          filenames=filenames
                                          )
            cfg.data.set_t_thumbs_spot(dt)
            cfg.main_window.tell('Discarding Full Size Correlation Spots...')
            try:
                shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale(), 'corr_spots'), ignore_errors=True)
                shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale(), 'corr_spots'), ignore_errors=True)
            except:
                print_exception()
            else:
                cfg.main_window.hud.done()



    def generate_thumbnails(self,
                            src,
                            od,
                            rmdir=False,
                            prefix='',
                            start=0,
                            end=None,
                            pbar_text='',
                            cpus=None,
                            filenames=None,
                            target_size=cfg.TARGET_THUMBNAIL_SIZE
                            ):
        caller = inspect.stack()[1].function

        fh = logging.FileHandler(os.path.join(cfg.data.dest(), 'logs', 'thumbnails.log'))
        fh.setLevel(logging.DEBUG)
        tnLogger.handlers.clear()
        tnLogger.addHandler(fh)

        # if cpus == None:
        #     cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2

        logger.info('Thumbnail Source Directory: %s' % src)

        try:
            siz_x, siz_y = ImageSize(next(absFilePaths(src)))
            scale_factor = int(max(siz_x, siz_y) / cfg.TARGET_THUMBNAIL_SIZE)
            if scale_factor == 0:
                scale_factor = 1
        except Exception as e:
            # print_exception()
            logger.warning('Do file(s) exist? - Returning')
            cfg.main_window.err('Unable to generate thumbnail(s)')
            raise e

        if rmdir:
            if os.path.exists(od):
                try:    shutil.rmtree(od)
                except: print_exception()
        if not os.path.exists(od):
            os.mkdir(od)

        if filenames == None:
            filenames = natural_sort(glob(os.path.join(src, '*.tif')))[start:end]

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        tnLogger.info(f'\n==== {timestamp} ====\n'
                      f'Generating Thumbnails...\n'
                      f'caller    : {caller}\n'
                      f'src       : {src}\n'
                      f'od        : {od}\n'
                      f'rmdir     : {rmdir}\n'
                      f'prefix    : {prefix}\n'
                      f'start     : {start}\n'
                      f'end       : {end}\n'
                      f'pbar      : {pbar_text}\n'
                      f'cpus      : {cpus}\n'
                      f'# files   : {len(filenames)}'
                      )
        tnLogger.info('filenames : \n' + '\n'.join(filenames))

        # logger.info(f'Generating thumbnails for:\n{str(filenames)}')
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
        task_queue = TaskQueue(n_tasks=len(cfg.data), parent=cfg.main_window, pbar_text=pbar_text)
        task_queue.start(cpus)

        logger.info('Removing up to %d files...' %len(filenames))
        for i, fn in enumerate(filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            if os.path.exists(ofn):
                os.remove(ofn)
            task = (self.iscale2_c, '+%d' % scale_factor, 'of=%s' % ofn, '%s' % fn)
            task_queue.add_task(task)
            if cfg.PRINT_EXAMPLE_ARGS and (i in (0, 1, 2)):
                logger.info('\nTQ Params:\n  (1) %s\n  (2) %s\n  (3) %s\n  (4) %s' % task)

        dt = task_queue.collect_results()

        logger.info('<<<< Thumbnail Generation Complete <<<<')
        return dt


