#!/usr/bin/env python3

'''Generates thumbnails for use with an alignEM project.'''

import datetime
import logging
import multiprocessing as mp
import os
import shutil
import subprocess as sp
import sys
import time
from glob import glob
from multiprocessing.pool import ThreadPool
import imagecodecs
import imageio.v3 as iio
import psutil
import tqdm

import src.config as cfg
from src.utils.funcs_image import ImageSize
from src.utils.helpers import print_exception, get_appdir, get_bindir, natural_sort, is_tacc

__all__ = ['Thumbnailer']

logger = logging.getLogger(__name__)
tnLogger = logging.getLogger('tnLogger')
tnLogger.propagate = False

if sys.platform != 'win32':
    mp.set_start_method('forkserver', force=True)

class Thumbnailer:

    def __init__(self, dm=None):
        self.dm = dm
        self.iscale2_c = os.path.join(get_appdir(), '../lib', get_bindir(), 'iscale2')


    def reduce_main(self, src, filenames, od):
        print(f'\n######## Reducing Thumbnails: Source Images ########\n')
        # coarsest_scale = self.dm.smallest_scale()

        d = os.path.dirname(od) #Needed for logging
        dt = -1
        try:
            # dt = self.reduce(src=src, od=od, dest=d, rmdir=True, prefix='', start=0, end=None)
            dt = self.reduce(src=src, filenames=filenames, od=od, dest=d, rmdir=True, prefix='', start=0, end=None)
        except:
            print_exception()
        return dt


    # def reduce_aligned(self, dm, indexes, dest, scale):
    #     print(f'\n######## Reducing Thumbnails: Aligned Images ########\n')
    #     to_reduce = []
    #     baseFileNames = self.dm.basefilenames()
    #     for i, name in enumerate([baseFileNames[i] for i in indexes]):
    #         ifn = dm.path_aligned(s=scale, l=i)
    #         ofn = dm.path_thumb(s=scale, l=i)
    #         if os.file_path.exists(ifn):
    #             if not os.file_path.exists(ofn):
    #                 os.makedirs(os.file_path.dirname(ofn), exist_ok=True)
    #                 to_reduce.append((ifn,ofn))
    #         else:
    #             raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), ifn)
    #
    #     if len(to_reduce):
    #         pbar_text = f'Reducing {self.dm.level_pretty()} aligned images (count={len(to_reduce)})...'
    #         if cfg.CancelProcesses:
    #             cfg.mw.warn('Canceling Tasks: %s' % pbar_text)
    #         else:
    #             # dt = self.reduce(src=src, od=od, rmdir=False, prefix='', filenames=files, pbar_text=pbar_text, dest=dest)
    #             dt = self.reduce_tuples(to_reduce=to_reduce)
    #             try:
    #                 self.dm.t_thumbs_aligned = dt
    #             except:
    #                 pass


    def reduce_signals(self, indexes, dest, scale):

        print(f'\n######## Reducing Thumbnails: Correlation Signals ########\n')

        pbar_text = 'Generating %s Signal Spot Thumbnails...' % self.dm.level_pretty()
        if cfg.CancelProcesses:
            cfg.mw.warn('Canceling Tasks: %s' % pbar_text)
        else:
            # src = os.file_path.join(dest, scale, 'signals_raw')
            src = os.path.join(dest, 'signals', scale)
            od = os.path.join(dest, 'signals', scale)

            rmdir = False


            if not rmdir:
                #Special handling for corrspot files since they are variable in # and never 1:1 with project files
                for i in indexes:
                    basename = os.path.basename(self.dm.base_image_name(s=self.dm.scale, l=i))
                    filename, extension = os.path.splitext(basename)
                    method = self.dm.section(s=self.dm.scale, l=i)['swim_settings']['method_opts']['method']
                    # old_thumbnails = glob(os.file_path.join(od, '*' + '_' + method + '_' + baseFileNames[i]))
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
            baseFileNames = self.dm.basefilenames()
            for name in [baseFileNames[i] for i in indexes]:
                filename, extension = os.path.splitext(name)
                search_path = os.path.join(src, '%s_*%s' % (filename, extension))
                # logger.info(f'Search Path: {search_path}')
                files.extend(glob(search_path))

            # tnLogger.info('Reducing the following corr spot thumbnails:\n%level' %str(filenames))
            tnLogger.info(f'Reducing {len(files)} corr spot thumbnails...')

            if scale == list(self.dm.scales)[-1]:
                full_size = True
            else:
                full_size = False

            dt = self.reduce(src=src, od=od,
                             rmdir=rmdir, prefix='',
                             pbar_text=pbar_text,
                             filenames=files,
                             dest=dest,
                             full_size=full_size
                             )
            self.dm.t_thumbs_spot = dt
            cfg.mw.hud.done()


    def reduce_matches(self, indexes, dest, scale):

        print(f'\n######## Reducing Thumbnails: Matches ########\n')

        pbar_text = 'Reducing %s Matches...' % self.dm.level_pretty()
        if cfg.CancelProcesses:
            cfg.mw.warn('Canceling Tasks: %s' % pbar_text)
        else:
            # src = os.file_path.join(dest, scale, 'matches_raw')
            src = os.path.join(dest, 'matches', scale)
            od = os.path.join(dest, 'matches', scale)

            rmdir = False

            if not rmdir:
                #Special handling for corrspot files since they are variable in # and never 1:1 with project files
                for i in indexes:
                    basename = os.path.basename(self.dm.base_image_name(s=self.dm.scale, l=i))
                    fn, ext = os.path.splitext(basename)
                    method = self.dm.section(s=self.dm.scale, l=i)['swim_settings']['method_opts']['method']
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
            baseFileNames = self.dm.basefilenames()
            for name in [baseFileNames[i] for i in indexes]:
                fn, ext = os.path.splitext(name)
                search_path = os.path.join(src, '%s_*%s' % (fn, ext))
                files.extend(glob(search_path))

            # tnLogger.info('Reducing the following corr spot thumbnails:\n%level' %str(filenames))
            tnLogger.info(f'Reducing {len(files)} total match images...')
            logger.info(f'Reducing {len(files)} total match images...')

            dt = self.reduce(src=src, od=od,
                             rmdir=rmdir, prefix='',
                             pbar_text=pbar_text,
                             filenames=files,
                             dest=dest,
                             full_size=False
                             )
            self.dm.t_thumbs_matches = dt

            cfg.mw.tell('Discarding Raw (Full Size) Matches...')
            try:
                shutil.rmtree(os.path.join(self.dm.dest(), self.dm.level, 'matches_raw'), ignore_errors=True)
                shutil.rmtree(os.path.join(self.dm.dest(), self.dm.level, 'matches_raw'), ignore_errors=True)
            except:
                print_exception()

            cfg.mw.hud.done()


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
               ):

        # if dest:
        #     logpath = os.file_path.join(dest, 'logs', 'thumbnails.log')
        #     file = open(logpath, 'a+')
        #     file.close()
        #     fh = logging.FileHandler(logpath)
        #     fh.setLevel(logging.DEBUG)
        #     tnLogger.handlers.clear()
        #     tnLogger.addHandler(fh)

        # if cpus == None:
        #     cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2

        if not os.path.isdir(src):
            logger.error(f"Directory '{src}' not found, nothing to thumbnail...")
            return


        if os.listdir(src) == []:
            logger.error(f"Directory '{src}' is empty, nothing to thumbnail...")
            return

        if rmdir:
            if os.path.exists(od):
                try:    shutil.rmtree(od)
                except: print_exception()
        if not os.path.exists(od):
            os.makedirs(od, exist_ok=True)


        if filenames == None:
            filenames = natural_sort(glob(os.path.join(src, '*.tif')))[start:end]

        try:
            logger.critical(f"sample 0 : {filenames[0]}")
            logger.critical(f"sample 1 : {filenames[1]}")
            siz_x, siz_y = ImageSize(filenames[1])
            # siz_x, siz_y = ImageIOSize(next(absFilePaths(src)))
            scale_factor = int(max(siz_x, siz_y) / target_size)
            if full_size:
                scale_factor = 1
            if scale_factor == 0:
                scale_factor = 1
        except Exception as e:
            print_exception()
            logger.error('Unable to generate thumbnail(level) - Do file(level) exist?')
            raise e


        if is_tacc():
            cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(filenames)),1)
        else:
            cpus = psutil.cpu_count(logical=False) - 2


        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        logger.info(f'\n==== {timestamp} ====\n'
                      f'Generating Thumbnails...\n'
                      f'src             : {src}\n'
                      f'od              :  └ {os.path.basename(od)} ({len(filenames)} files)\n'
                      f'overwrite dir?  : {rmdir}\n'
                      )
        # tnLogger.info('filenames : \n' + '\n'.join(filenames))
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
        logger.info(f"# Processes: {cpus}")
        with ThreadPool(processes=cpus) as pool:
            pool.map(run_subprocess, tqdm.tqdm(tasks, total=len(tasks), desc="Generating Thumbnails", position=0, leave=True))
            pool.close()
            pool.join()

        time.sleep(.1)
        logger.critical("(monkey patch) Rewriting images to correct metadata...")
        _t0 = time.time()
        for f in filenames:
            ofn = os.path.join(od, os.path.basename(f))
            # im = iio.imread(ofn)
            try:
                im = imread(ofn)
                iio.imwrite(ofn, im)
            except:
                print_exception()

        _dt = time.time() - _t0
        logger.critical(f"Rewriting images took {_dt:.3g}s")

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
        logger.info('\n\n<<<< Thumbnailing Complete <<<<\n')
        return dt


    def reduce_tuples(self, to_reduce, target_size=cfg.TARGET_THUMBNAIL_SIZE, scale_factor=None):
        logger.info(f"-------REDUCING TUPLES--------")
        # logger.info(f"-------REDUCING TUPLES--------\n{pprint(to_reduce)}")

        try:
            assert len(to_reduce) > 0
        except AssertionError:
            logger.warning('Argument has no images to reduce.')
            return

        if scale_factor == None:
            try:
                sample = to_reduce[0][0]
                logger.info(f"sample: {sample}")
                siz_x, siz_y = ImageSize(sample)
                # siz_x, siz_y = ImageIOSize(next(absFilePaths(src)))
                scale_factor = int(max(siz_x, siz_y) / target_size)
            except Exception as e:
                print_exception()
                logger.error('Unable to generate thumbnail(level) - Do file(level) exist?')
                raise e

        logger.info(f'Downsampling factor for thumbnails: {scale_factor}')

        if is_tacc():
            # cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(to_reduce)), 1)
            cpus = 16
        else:
            cpus = psutil.cpu_count(logical=False) - 2

        tasks = []

        for item in to_reduce:
            fn = item[0]
            ofn = item[1]
            tasks.append([self.iscale2_c, '+%d' % scale_factor, 'of=%s' % ofn, '%s' % fn])

        t0 = time.time()
        logger.info(f"# Processes: {cpus}")
        with ThreadPool(processes=cpus) as pool:
            pool.map(run_subprocess, tqdm.tqdm(tasks, total=len(tasks), desc="Generating Thumbnails", position=0, leave=True))
            pool.close()
            pool.join()

        if 0:
            logger.critical("(monkey patch) Rewriting images to correct metadata...")
            _t0 = time.time()
            for item in to_reduce:
                ofn = item[1]
                # im = iio.imread(ofn)
                im = imread(ofn)
                iio.imwrite(ofn, im)
            _dt = time.time() - _t0
            logger.critical(f"\n\n// Rewriting of images took {_dt:.3g}s //")

        dt = time.time() - t0
        logger.info(f'Thumbnailing complete. Time elapsed: {dt:.3f}')
        return dt


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))


def imread(filename):
    # return first image in TIFF file as numpy array
    with open(filename, 'rb') as fh:
        data = fh.read()
    return imagecodecs.tiff_decode(data)