#!/usr/bin/env python3

# import imagecodecs
import numcodecs
numcodecs.blosc.use_threads = False
import libtiff
#!/usr/bin/env python3

import os
import sys
import time
import psutil
import shutil
import logging
from pathlib import Path

from os import kill
from signal import alarm, signal, SIGALRM, SIGKILL
from subprocess import PIPE, Popen
import multiprocessing as mp
import subprocess as sp
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import zarr
import imagecodecs
import libtiff
import tqdm
import numcodecs
from numcodecs import Blosc
numcodecs.blosc.use_threads = False
from src.funcs_image import ImageSize

from src.thumbnailer import Thumbnailer
from src.helpers import print_exception, create_project_directories, get_bindir, get_scale_val, \
    renew_directory, renew_directory, get_img_filenames
# from src.funcs_zarr import preallocate_zarr
from src.funcs_zarr import remove_zarr
import src.config as cfg
from src.ui.align import AlignWorker

from qtpy.QtCore import Signal, QObject, QMutex
from qtpy.QtWidgets import QApplication

__all__ = ['ScaleWorker']

logger = logging.getLogger(__name__)


class ScaleWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    coarsestDone = Signal()
    refresh = Signal()
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str) # (# tasks, description)
    hudWarning = Signal(str) # (# tasks, description)

    def __init__(self, dm, out, scales, imgs, zarr_opts):
        super().__init__()
        # print("Initializing Worker...", flush=True)
        print("Initializing Worker...")
        self.dm = dm
        self.out = out
        self.scales = scales
        self.imgs = imgs
        self.zarr_opts = zarr_opts
        self.result = None
        self._mutex = QMutex()
        self._running = True
        self._timing_results = {'t_scale_generate': {}, 't_scale_convert': {}, 't_thumbs': {}}


    def running(self):
        try:
            self._mutex.lock()
            return self._running
        finally:
            self._mutex.unlock()


    def stop(self):
        print("Stopping Worker...")
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()


    def run(self):

        print(f'\n\n######## Generating Downsampled Images ########\n', flush=True)

        # Todo This should check for source files before doing anything
        if not self.running():
            self.hudWarning.emit('Canceling Tasks: Generate Scale Image Hierarchy')
            self.hudWarning.emit('Canceling Tasks: Copy-convert Scale Images to Zarr')
            return

        cur_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        iscale2_c = os.path.join(Path(cur_path).parent.absolute(), 'lib', get_bindir(), 'iscale2')

        # dm.link_full_resolution()

        logger.info('Creating downsampling tasks...')

        logger.info(f'# images: {len(self.imgs)}')

        ctx = mp.get_context('forkserver')
        # for s in self.dm.downscales()[::-1]:
        # for s in self.dm.scales()[::-1]:
        for s, siz in self.scales:
            sv = get_scale_val(s)
            logger.info(f"s = {s}, siz = {siz}")


            if s != 'scale_1':
                desc = f'Downsampling {s}...'
                logger.info(desc)


                tasks = []
                for i, layer in enumerate(self.dm['data']['scales'][s]['stack']):
                    if_arg     = os.path.join(self.dm['data']['source_path'], self.imgs[i])
                    ofn        = os.path.join(self.out, 'tiff', 's%d' % sv, os.path.split(if_arg)[1])
                    of_arg     = 'of=%s' % ofn
                    scale_arg  = '+%d' % get_scale_val(s)
                    tasks.append([iscale2_c, scale_arg, of_arg, if_arg])
                    # layer['filename'] = ofn #0220+
                    # layer['alignment']['swim_settings']['fn_transforming'] = ofn

                cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks) * len(self.dm.downscales()))

                # cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks) * len(self.dm.downscales()))
                # logger.info(f"cpus: {cpus}")
                self.initPbar.emit((len(tasks), desc))
                t = time.time()

                # with ThreadPoolExecutor(max_workers=10) as pool:
                with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
                # with ctx.Pool(processes=104, maxtasksperchild=1) as pool:
                    for i, result in enumerate(tqdm.tqdm(pool.imap_unordered(run, tasks),
                                                         total=len(tasks),
                                                         desc=desc, position=0,
                                                         leave=True)):
                        self.progress.emit(i)
                        if not self.running():
                            break
                dt = time.time() - t
                self._timing_results['t_scale_generate'][s] = dt

                logger.info(f"Pool Time: {'%.3g' % dt}s")

            if not self.running():
                self.hudWarning.emit('Canceling Tasks:  Convert TIFFs to NGFF Zarr')
                return

            zarr_od = os.path.abspath(os.path.join(self.out, 'zarr'))
            # renew_directory(directory=zarr_od, gui=False)
            desc = f"Converting {s} to Zarr"
            tasks = []
            for ID, img in enumerate(self.imgs):
                fn = os.path.join(self.out, 'tiff', 's%d' % sv, os.path.basename(img))
                out = os.path.join(zarr_od, 's%d' % sv)
                tasks.append([ID, fn, out])
                # logger.critical(f"\n\ntask : {[ID, fn, out]}\n")

            # x, y = ImageSize(tasks[0][1])
            # x, y = self.dm.image_size(s=s)
            x, y = siz[0], siz[1]

            shape = (len(self.imgs), y, x)
            name = 's%d' % get_scale_val(s)
            # preallocate_zarr(out=self.out, name='zarr', group=grp, shape=shape, dtype='|u1', overwrite=True,
            #                  zarr_opts=self.zarr_opts)
            preallocate_zarr(zarr_od=zarr_od, name=name, shape=shape, dtype='|u1', zarr_opts=self.zarr_opts)
            # t = time.time()
            # self.initPbar.emit((len(tasks), desc))
            # with ThreadPoolExecutor(max_workers=110) as executor:
            #     list(tqdm.tqdm(executor.map(convert_zarr, tasks), total=len(tasks), position=0, leave=True, desc=desc))

            t = time.time()
            self.initPbar.emit((len(tasks), desc))
            all_results = []
            cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks) * len(self.dm.downscales()))
            i = 0
            # with ctx.Pool(processes=104, maxtasksperchild=1) as pool:
            with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
                for result in tqdm.tqdm(
                    pool.imap_unordered(convert_zarr, tasks),
                        total=len(tasks),
                        desc=desc,
                        position=0,
                        leave=True):
                    all_results.append(result)
                    i += 1
                    self.progress.emit(i)
                    if not self.running():
                        break

            dt = time.time() - t
            self._timing_results['t_scale_convert'][s] = dt
            logger.info(f"Pool Time: {'%.3g' % dt}s")

            # #Do not modify or remove.
            # self.coarsestDone.emit()
            # if s == dm.coarsest_scale_key():
            #     if dm['data']['autoalign_flag']:
            #         self._alignworker = AlignWorker(scale=s,
            #                   path=None,
            #                   indexes=list(range(0,len(dm))),
            #                   swim_only=False,
            #                   renew_od=False,
            #                   reallocate_zarr=True,
            #                   dm=dm
            #                   )  # Step 3: Create a worker object
            #         self._alignworker.initPbar.connect(lambda t: self.initPbar.emit(t))
            #         self._alignworker.progress.connect(lambda i: self.progress.emit(i))
            #         self._alignworker.run()
            #         # self.coarsestDone.emit()
            #         self.refresh.emit()
            #         QApplication.processEvents()
        self.finished.emit()

        thumbnailer = Thumbnailer()
        self._timing_results['t_thumbs'][s] = thumbnailer.reduce_main(dest=self.out)


        if not self.running():
            self.hudWarning.emit('Canceling Tasks:  Convert TIFFs to NGFF Zarr')
            return

        self.hudMessage.emit('**** Autoscaling Complete ****')
        logger.info('**** Autoscaling Complete ****')
        self.finished.emit()

def preallocate_zarr(zarr_od, name, shape, dtype, zarr_opts):
    '''zarr.blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']'''
    cname, clevel, chunkshape = zarr_opts
    # src = os.path.abspath(out)
    # path_zarr = os.path.join(out, name)
    # path_out = os.path.join(path_zarr, group)
    logger.critical(f'allocating {zarr_od}/{name}...')

    # if gui:
    #     cfg.main_window.hud(f'Preallocating {os.path.basename(src)}/{group} Zarr...')
    # if os.path.exists(path_out) and (overwrite == False):
    #     logger.warning('Overwrite is False - Returning')
    #     return

    # output_text = f'\n  Zarr root : {os.path.join(os.path.basename(out), name)}' \
    #               f'\n      group :   └ {group}({name}) {dtype} {cname}/{clevel}' \
    #               f'\n      shape : {str(shape)} ' \
    #               f'\n      chunk : {chunkshape}'

    try:
        if os.path.exists(os.path.join(zarr_od, name)):
            remove_zarr(os.path.join(zarr_od, name))
        # synchronizer = zarr.ThreadSynchronizer()
        # arr = zarr.group(store=path_zarr, synchronizer=synchronizer) # overwrite cannot be set to True here, will overwrite entire Zarr
        arr = zarr.group(store=zarr_od, overwrite=False)
        compressor = Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None

        # arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite, synchronizer=synchronizer)
        arr.zeros(name=name, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=True)
        # write_metadata_zarr_multiscale()
    except:
        print_exception()
        logger.warning('Zarr Preallocation Encountered A Problem')
    # else:
        # cfg.main_window.hud.done()
        # logger.info(output_text)

def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        store = zarr.open(out)
        # img = imread(fn)[:, ::-1]
        store[ID, :, :] = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        # store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
        return 0
    except:
        print_exception()
        return 1


def imread(filename):
    # return first image in TIFF file as numpy array
    with open(filename, 'rb') as fh:
        data = fh.read()
    return imagecodecs.tiff_decode(data)


def run(task):
    """Call run(), catch exceptions."""
    try:
        # sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))


class Command(object):
    # https://stackoverflow.com/questions/1191374/using-module-subprocess-with-timeout
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        def target():
            print('Thread started')
            self.process = sp.Popen(self.cmd, shell=True)
            self.process.communicate()
            print('Thread finished')

        thread = sp.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            print('Terminating process')
            self.process.terminate()
            thread.join()
        print(self.process.returncode)




def run2(args, cwd = None, shell = False, kill_tree = True, timeout = -1, env = None):
    '''
    Run a command with a timeout after which it will be forcibly
    killed.
    '''
    class Alarm(Exception):
        pass
    def alarm_handler(signum, frame):
        raise Alarm
    p = Popen(args, shell = shell, cwd = cwd, stdout = PIPE, stderr = PIPE, env = env)
    if timeout != -1:
        signal(SIGALRM, alarm_handler)
        alarm(timeout)
    try:
        stdout, stderr = p.communicate()
        if timeout != -1:
            alarm(0)
    except Alarm:
        pids = [p.pid]
        if kill_tree:
            pids.extend(get_process_children(p.pid))
        for pid in pids:
            # process might have died before getting to this line
            # so wrap to avoid OSError: no such process
            try:
                kill(pid, SIGKILL)
            except OSError:
                pass
        return -9, '', ''
    return p.returncode, stdout, stderr

def get_process_children(pid):
    p = Popen('ps --no-headers -o pid --ppid %d' % pid, shell = True,
              stdout = PIPE, stderr = PIPE)
    stdout, stderr = p.communicate()
    return [int(p) for p in stdout.split()]


def count_files(dest, scales):
    result = []
    for s in scales:
        path = os.path.join(dest, s, 'img_src')
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        result.append(len(files))
        # print(f"# {s} Files: {len(files)}")
        print(f"# {s} Files: {len(files)}", end="\r")
    return result


#/Users/joelyancey/.alignem_data/series/0816_DW02_3imgs/scale_24/img_src/SYGQK_003.tif
