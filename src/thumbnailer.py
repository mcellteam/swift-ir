#!/usr/bin/env python3

'''Generates thumbnails for use with an AlignEM-SWiFT project.'''

import os
import time
import shutil
import psutil
import inspect
import logging
import datetime
from math import floor, ceil
from glob import glob
import multiprocessing as mp
import subprocess as sp

import src.config as cfg
from src.funcs_image import ImageSize
from src.helpers import print_exception, get_appdir, get_bindir, natural_sort, absFilePaths

__all__ = ['Thumbnailer']

logger = logging.getLogger(__name__)
tnLogger = logging.getLogger('tnLogger')
tnLogger.propagate = False



class Thumbnailer:

    def __init__(self):
        logger.info('')
        self.iscale2_c = os.path.join(get_appdir(), 'lib', get_bindir(), 'iscale2')

    def reduce_main(self, dest, use_gui=True):
        logger.info(f'\n\n################ Reducing: Source Images ################\n')

        pbar_text = 'Generating %s Source Image Thumbnails...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            coarsest_scale = cfg.data.smallest_scale()
            src = os.path.join(cfg.data.dest(), coarsest_scale, 'img_src')
            od = os.path.join(cfg.data.dest(), 'thumbnails')
            dt = self.reduce(
                src=src, od=od, rmdir=True, prefix='', start=0, end=None, pbar_text=pbar_text, dest=dest, use_gui=use_gui)
            cfg.data.t_thumbs = dt


    def reduce_aligned(self, start, end, dest, scale, use_gui=True):
        logger.info(f'\n\n################ Reducing: Aligned Images ################\n')

        pbar_text = 'Generating %s Aligned Image Thumbnails...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            src = os.path.join(dest, scale, 'img_aligned')
            od = os.path.join(dest, scale, 'thumbnails_aligned')
            dt = self.reduce(
                src=src, od=od, rmdir=False, prefix='', start=start, end=end, pbar_text=pbar_text, dest=dest, use_gui=use_gui)
            try:
                cfg.data.t_thumbs_aligned = dt
            except:
                pass

            # cfg.mw.tell('Generating hashes for aligned image thumbnails...')
            # if end == None:
            #     end = len(cfg.data)
            # cfg.mw.hud.done()

    def reduce_signals(self, start, end, dest, scale, use_gui=True):

        logger.info(f'\n\n################ Reducing: Correlation Signals ################\n')

        pbar_text = 'Generating %s Signal Spot Thumbnails...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            src = os.path.join(dest, scale, 'signals_raw')
            od = os.path.join(dest, scale, 'signals')

            rmdir = False
            if end == None:
                end = cfg.data.count

            baseFileNames = cfg.data.basefilenames()
            if not rmdir:
                logger.info(f'start: {start}, end: {end}')
                #Special handling for corrspot files since they are variable in # and never 1:1 with project files
                for i in range(start,end):
                    basename = os.path.basename(cfg.data.base_image_name(s=cfg.data.scale, l=i))
                    filename, extension = os.path.splitext(basename)
                    method = cfg.data.section(l=i)['current_method']
                    # old_thumbnails = glob(os.path.join(od, '*' + '_' + method + '_' + baseFileNames[i]))
                    search_path = os.path.join(od, '%s_%s_*%s' % (filename, method, extension))
                    # logger.critical(f'\n\n\nSearch Path (Pre-Removal):\n{search_path}\n\n')
                    old_thumbnails = glob(search_path)
                    # logger.critical(f'\n\n\nFound Files:\n{old_thumbnails}\n\n')
                    for tn in old_thumbnails:
                        logger.info(f'Removing {tn}...')
                        try:
                            os.remove(tn)
                        except:
                            logger.warning('An exception was triggered during removal of expired thumbnail: %s' % tn)

            filenames = []
            for name in baseFileNames[start:end]:
                filename, extension = os.path.splitext(name)
                search_path = os.path.join(src, '%s_*%s' % (filename, extension))
                # logger.info(f'Search Path: {search_path}')
                filenames.extend(glob(search_path))

            # tnLogger.info('Reducing the following corr spot thumbnails:\n%s' %str(filenames))
            tnLogger.info(f'Reducing {len(filenames)} corr spot thumbnails...')

            if scale == list(cfg.data.scales())[-1]:
                full_size = True
            else:
                full_size = False

            dt = self.reduce(src=src, od=od,
                             rmdir=rmdir, prefix='',
                             start=start, end=end,
                             pbar_text=pbar_text,
                             filenames=filenames,
                             dest=dest,
                             use_gui=use_gui,
                             full_size=full_size
                             )
            cfg.data.t_thumbs_spot = dt
            cfg.main_window.tell('Discarding Raw (Full Size) Correlation Signals...')
            try:
                shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale, 'signals_raw'), ignore_errors=True)
                shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale, 'signals_raw'), ignore_errors=True)
            except:
                print_exception()
            else:
                cfg.main_window.hud.done()


    def reduce(self,
               src,
               od,
               rmdir=False,
               prefix='',
               start=0,
               end=None,
               pbar_text='',
               filenames=None,
               target_size=cfg.TARGET_THUMBNAIL_SIZE,
               full_size=False,
               dest='',
               use_gui=True,
               ):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')


        logpath = os.path.join(dest, 'logs', 'thumbnails.log')
        file = open(logpath, 'w+')
        file.close()
        fh = logging.FileHandler(logpath)
        fh.setLevel(logging.DEBUG)
        tnLogger.handlers.clear()
        tnLogger.addHandler(fh)

        # if cpus == None:
        #     cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2

        logger.info('Thumbnail Source Directory: %s' % src)

        if os.listdir(src) == []:
            logger.error(f"The directory '{src}' is empty, nothing to thumbnail...")
            if use_gui:
                logger.error(f"Something went wrong. The directory '{src}' is empty, nothing to thumbnail...")
            return

        try:
            siz_x, siz_y = ImageSize(next(absFilePaths(src)))
            scale_factor = int(max(siz_x, siz_y) / target_size)
            if full_size:
                scale_factor = 1
            if scale_factor == 0:
                scale_factor = 1
        except Exception as e:
            # print_exception()
            logger.warning('Do file(s) exist? - Returning')
            if use_gui:
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

        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(filenames))

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


        logger.info('Removing up to %d files...' %len(filenames))
        tasks = []
        for i, fn in enumerate(filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            try:
                if os.path.exists(ofn):
                    os.remove(ofn)
            except:
                print_exception()

        logger.info('Making thumbnailer tasks...')
        for i, fn in enumerate(filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            tasks.append([self.iscale2_c, '+%d' % scale_factor, 'of=%s' % ofn, '%s' % fn])

        logger.info('Beginning thumbnailer ThreadPool...')
        t0 = time.time()
        ctx = mp.get_context('forkserver')
        # with ctx.Pool(processes=cpus) as pool:
        #     pool.map(run, tasks)
        #     pool.close()
        #     pool.join()
        pool = ctx.Pool(processes=cpus)
        pool.map(run, tasks)
        pool.close()
        pool.join()
        logger.info('<<<< Thumbnail Generation Complete <<<<')
        dt = time.time() - t0
        return dt


def run(task):
    """Call run(), catch exceptions."""
    try:
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))