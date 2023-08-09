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
from multiprocessing.pool import ThreadPool
import subprocess as sp
import tqdm
import src.config as cfg
from src.funcs_image import ImageSize, ImageIOSize
from src.helpers import print_exception, get_appdir, get_bindir, natural_sort, absFilePaths, is_tacc

__all__ = ['Thumbnailer']

logger = logging.getLogger(__name__)
tnLogger = logging.getLogger('tnLogger')
tnLogger.propagate = False

mp.set_start_method('forkserver', force=True)

class Thumbnailer:

    def __init__(self):
        self.iscale2_c = os.path.join(get_appdir(), 'lib', get_bindir(), 'iscale2')

    def reduce_main(self, dest, use_gui=True):
        print(f'\n\n######## Reducing: Source Images ########\n')

        pbar_text = 'Generating %s Source Image Thumbnails...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            coarsest_scale = cfg.data.smallest_scale()
            src = os.path.join(cfg.data.dest(), coarsest_scale, 'img_src')
            od = os.path.join(cfg.data.dest(), 'thumbnails')
            dt = self.reduce(
                src=src, od=od, rmdir=True, prefix='', start=0, end=None, pbar_text=pbar_text, dest=dest, use_gui=use_gui)
            return dt


    def reduce_aligned(self, indexes, dest, scale, use_gui=True):
        print(f'\n\n######## Reducing: Aligned Images ########\n')
        src = os.path.join(dest, scale, 'img_aligned')
        od = os.path.join(dest, scale, 'thumbnails_aligned')


        files = []
        baseFileNames = cfg.data.basefilenames()
        for name in [baseFileNames[i] for i in indexes]:
            files.append(os.path.join(src,name))




        pbar_text = 'Generating %s Aligned Image Thumbnails...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:

            dt = self.reduce(
                src=src, od=od, rmdir=False, prefix='', filenames=files, pbar_text=pbar_text, dest=dest,
                use_gui=use_gui)
            try:
                cfg.data.t_thumbs_aligned = dt
            except:
                pass

            # cfg.mw.tell('Generating hashes for aligned image thumbnails...')
            # if end == None:
            #     end = len(cfg.data)
            # cfg.mw.hud.done()

    def reduce_signals(self, indexes, dest, scale, use_gui=True):

        print(f'\n\n######## Reducing: Correlation Signals ########\n')

        pbar_text = 'Generating %s Signal Spot Thumbnails...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            src = os.path.join(dest, scale, 'signals_raw')
            od = os.path.join(dest, scale, 'signals')

            rmdir = False


            if not rmdir:
                #Special handling for corrspot files since they are variable in # and never 1:1 with project files
                for i in indexes:
                    basename = os.path.basename(cfg.data.base_image_name(s=cfg.data.scale_key, l=i))
                    filename, extension = os.path.splitext(basename)
                    method = cfg.data.section(l=i)['alignment']['swim_settings']['method']
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

            files = []
            baseFileNames = cfg.data.basefilenames()
            for name in [baseFileNames[i] for i in indexes]:
                filename, extension = os.path.splitext(name)
                search_path = os.path.join(src, '%s_*%s' % (filename, extension))
                # logger.info(f'Search Path: {search_path}')
                files.extend(glob(search_path))

            # tnLogger.info('Reducing the following corr spot thumbnails:\n%s' %str(filenames))
            tnLogger.info(f'Reducing {len(files)} corr spot thumbnails...')

            if scale == list(cfg.data.scales())[-1]:
                full_size = True
            else:
                full_size = False

            dt = self.reduce(src=src, od=od,
                             rmdir=rmdir, prefix='',
                             pbar_text=pbar_text,
                             filenames=files,
                             dest=dest,
                             use_gui=use_gui,
                             full_size=full_size
                             )
            cfg.data.t_thumbs_spot = dt
            cfg.main_window.hud.done()


    def reduce_matches(self, indexes, dest, scale, use_gui=True):

        print(f'\n\n######## Reducing: Matches ########\n')

        pbar_text = 'Reducing %s Matches...' % cfg.data.scale_pretty()
        if cfg.CancelProcesses:
            cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
        else:
            src = os.path.join(dest, scale, 'matches_raw')
            od = os.path.join(dest, scale, 'matches')

            rmdir = False

            if not rmdir:
                #Special handling for corrspot files since they are variable in # and never 1:1 with project files
                for i in indexes:
                    basename = os.path.basename(cfg.data.base_image_name(s=cfg.data.scale_key, l=i))
                    fn, ext = os.path.splitext(basename)
                    method = cfg.data.section(l=i)['alignment']['swim_settings']['method']
                    pattern = os.path.join(od, '%s_%s_[tk]_%d%s' % (fn, method, i, ext))

                    originals = glob(pattern)
                    # logger.critical(f'\n\n\nFound Files:\n{old_thumbnails}\n\n')
                    # logger.info(f"Removing {len(originals)} stale matches...")
                    for tn in originals:
                        logger.info(f'Removing {tn}...')
                        try:
                            os.remove(tn)
                        except:
                            logger.warning('An exception was triggered during removal of expired thumbnail: %s' % tn)

            files = []
            baseFileNames = cfg.data.basefilenames()
            for name in [baseFileNames[i] for i in indexes]:
                fn, ext = os.path.splitext(name)
                search_path = os.path.join(src, '%s_*%s' % (fn, ext))
                files.extend(glob(search_path))

            # tnLogger.info('Reducing the following corr spot thumbnails:\n%s' %str(filenames))
            tnLogger.info(f'Reducing {len(files)} total match images...')
            logger.info(f'Reducing {len(files)} total match images...')

            dt = self.reduce(src=src, od=od,
                             rmdir=rmdir, prefix='',
                             pbar_text=pbar_text,
                             filenames=files,
                             dest=dest,
                             use_gui=use_gui,
                             full_size=False
                             )
            cfg.data.t_thumbs_matches = dt

            cfg.main_window.tell('Discarding Raw (Full Size) Matches...')
            try:
                shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale_key, 'matches_raw'), ignore_errors=True)
                shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale_key, 'matches_raw'), ignore_errors=True)
            except:
                print_exception()

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

        logpath = os.path.join(dest, 'logs', 'thumbnails.log')
        file = open(logpath, 'a+')
        file.close()
        fh = logging.FileHandler(logpath)
        fh.setLevel(logging.DEBUG)
        tnLogger.handlers.clear()
        tnLogger.addHandler(fh)

        # if cpus == None:
        #     cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2

        if not os.path.isdir(src):
            logger.error(f"The directory '{src}' does not exist, nothing to thumbnail...")
            return


        if os.listdir(src) == []:
            logger.error(f"The directory '{src}' is empty, nothing to thumbnail...")
            return

        try:
            siz_x, siz_y = ImageSize(next(absFilePaths(src)))
            # siz_x, siz_y = ImageIOSize(next(absFilePaths(src)))
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

        if is_tacc():
            cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(filenames)),1)
        else:
            cpus = psutil.cpu_count(logical=False) - 2


        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        tnLogger.info(f'\n==== {timestamp} ====\n'
                      f'Generating Thumbnails...\n'
                      f'src        : {src}\n'
                      f'od         : {od}\n'
                      f'rmdir      : {rmdir}\n'
                      f'prefix     : {prefix}\n'
                      f'pbar       : {pbar_text}\n'
                      f'cpus       : {cpus}\n'
                      f'# files    : {len(filenames)}'
                      )
        tnLogger.info('filenames : \n' + '\n'.join(filenames))
        # logger.info('Removing up to %d files...' %len(filenames))
        tasks = []
        for i, fn in enumerate(filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            try:
                if os.path.exists(ofn):
                    os.remove(ofn)
            except:
                print_exception()

        for i, fn in enumerate(filenames):
            ofn = os.path.join(od, os.path.basename(fn))
            tasks.append([self.iscale2_c, '+%d' % scale_factor, 'of=%s' % ofn, '%s' % fn])

        t0 = time.time()
        with ThreadPool(processes=cpus) as pool:
            pool.map(run_subprocess, tqdm.tqdm(tasks, total=len(tasks), desc="Generating Thumbnails", position=0, leave=True))
            pool.close()
            pool.join()
        # ctx = mp.get_context('forkserver')
        # with ctx.Pool(processes=cpus) as pool:
        #     pool.map(run, tasks)
        #     pool.close()
        #     pool.join()
        # pool = ctx.Pool(processes=cpus)
        # pool.map(run, tqdm.tqdm(tasks, total=len(tasks)))
        # pool.close()
        # pool.join()
        dt = time.time() - t0
        return dt


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))