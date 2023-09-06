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
from copy import deepcopy
from pathlib import Path

from os import kill
from signal import alarm, signal, SIGALRM, SIGKILL
from subprocess import PIPE, Popen
import multiprocessing as mp
import subprocess as sp
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import numpy as np
import zarr
import imagecodecs
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()
import tqdm
import numcodecs
from numcodecs import Blosc
numcodecs.blosc.use_threads = False
from src.funcs_image import ImageSize

from src.thumbnailer import Thumbnailer
from src.helpers import print_exception, get_bindir, get_scale_val, \
    renew_directory, renew_directory, get_img_filenames
# from src.funcs_zarr import preallocate_zarr
from src.funcs_zarr import remove_zarr
import src.config as cfg

from qtpy.QtCore import Signal, QObject, QMutex

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

    def __init__(self, src, out, scales, opts):
        super().__init__()
        logger.info('')
        self.src = src
        self.out = out
        self.opts = opts
        self.scales = scales
        self.paths = self.opts['paths']
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
        logger.info("Stopping Worker...")
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()


    def run(self):

        print(f'\n######## Reducing Source Images ########\n')
        logger.critical(f"src = {self.src}")

        # Todo This should check for source files before doing anything
        if not self.running():
            self.finished.emit()
            return

        cur_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        iscale2_c = os.path.join(Path(cur_path).parent.absolute(), 'lib', get_bindir(), 'iscale2')

        logger.info(f'Reducing {len(self.paths)} images...')

        ctx = mp.get_context('forkserver')
        for s, siz in deepcopy(self.scales):
            sv = get_scale_val(s)
            if s != 's1':
                desc = f'Reducing {s}...'
                logger.info(desc)
                tasks = []
                for i in range(0, len(self.paths)):
                    if_arg     = os.path.join(self.src, self.paths[i])

                    scale_arg  = '+%d' % get_scale_val(s)
                    ofn = os.path.join(self.out, 'tiff', 's%d' % sv, os.path.split(if_arg)[1])
                    of_arg = 'of=%s' % ofn
                    tasks.append([iscale2_c, scale_arg, of_arg, if_arg])



                self.initPbar.emit((len(tasks), desc))
                t = time.time()

                cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks))
                # cpus = 10
                logger.info(f"CPUs: {cpus}")
                # with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
                # with ctx.Pool(processes=cpus) as pool:
                # with ctx.Pool(processes=cpus) as pool:
                # with ctx.Pool(processes=20) as pool:

                with ThreadPoolExecutor(max_workers=cpus) as pool:
                # with ProcessPoolExecutor(max_workers=cpus) as pool:
                # with ThreadPoolExecutor(max_workers=1) as pool:
                #     for i, result in enumerate(tqdm.tqdm(pool.imap_unordered(run, tasks),
                #                                          total=len(tasks),
                #                                          desc=desc, position=0,
                #                                          leave=True)):
                #     for i, result in enumerate(tqdm.tqdm(pool.map(run, tasks),
                #                                          total=len(tasks),
                #                                          desc=desc, position=0,
                #                                          leave=True)):
                    for i in tqdm.tqdm(pool.map(run, tasks), total=len(tasks),
                                                     desc=desc, position=0,
                                                     leave=True):
                        self.progress.emit(i)
                        if not self.running():
                            break
                # ThreadPoolExecutor.shutdown()

                dt = time.time() - t
                self._timing_results['t_scale_generate'][s] = dt

                logger.info(f"Elapsed Time: {dt:.3g}s")

            if not self.running():
                self.hudWarning.emit('Canceling Tasks:  Convert TIFFs to NGFF Zarr')
                self.finished.emit()
                return

        scales_list = []
        for s, siz in deepcopy(self.scales):
            scales_list.append(s)

        logger.critical(f"self.out = {self.out}\n"
                        f"scales_list = {scales_list}")

        logger.info("Sleeping for 2 seconds...")
        time.sleep(2)

        # count_files(self.out, scales_list)

        out = os.path.join(self.out, 'thumbnails')
        logger.info(f"Creating thumbnails...\n"
                    f"src: {self.src}\n"
                    f"out: {out}")
        thumbnailer = Thumbnailer()
        # self._timing_results['t_thumbs'] = thumbnailer.reduce_main(self.src, out)
        self._timing_results['t_thumbs'] = thumbnailer.reduce_main(self.src, self.paths, out)

        # count_files(self.out, scales_list)


        n_imgs = len(self.paths)

        for s, siz in deepcopy(self.scales):
            logger.critical(f"Looping s={s}, siz={siz}...")
            sv = get_scale_val(s)

            allow_continue = False
            while not allow_continue:
                n_files = count_files(self.out, [s])[0]

                allow_continue = n_files >= n_imgs

                # logger.info(f"Waiting on {n_imgs - n_files} images to generate. Total generated: {n_files}/{n_imgs}")
                print(f"Waiting on: {n_imgs - n_files} {s} image(s), total generated: {n_files}/{n_imgs}", end="\r")



            zarr_od = os.path.abspath(os.path.join(self.out, 'zarr'))
            # renew_directory(directory=zarr_od, gui=False)
            desc = f"Converting {s} to Zarr..."
            logger.info(desc)
            tasks = []
            for ID, img in enumerate(self.paths):
                fn = os.path.join(self.out, 'tiff', 's%d' % sv, os.path.basename(img))
                out = os.path.join(zarr_od, 's%d' % sv)
                tasks.append([ID, fn, out])
                # logger.critical(f"\n\ntask : {[ID, fn, out]}\n")

            x, y = siz[0], siz[1]

            shape = (len(self.paths), y, x)
            name = 's%d' % get_scale_val(s)
            logger.critical(f"preallocating name: {name}, shape: {shape}...")
            preallocate_zarr(zarr_od=zarr_od, name=name, shape=shape, dtype='|u1', opts=self.opts, scale=s)

            t = time.time()
            self.initPbar.emit((len(tasks), desc))
            all_results = []
            i = 0
            cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks))
            # with ctx.Pool(processes=104, maxtasksperchild=1) as pool:
            # logger.info(f"# mp.Pool Processes: {cpus}")
            # with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
            with ThreadPoolExecutor(max_workers=10) as pool:
                for result in tqdm.tqdm(
                    # pool.imap_unordered(convert_zarr, tasks),
                    #     total=len(tasks),
                    #     desc=desc,
                    #     position=0,
                    #     leave=True):
                    pool.map(convert_zarr, tasks),
                        total=len(tasks),
                        desc=desc,
                        position=0,
                        leave=True):

                    all_results.append(result)
                    i += 1
                    self.progress.emit(i)
                    if not self.running():
                        break

            # i = 0
            # # with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
            # with ctx.Pool(processes=1, maxtasksperchild=1) as pool:
            #     for result in tqdm.tqdm(
            #             pool.imap_unordered(convert_zarr, tasks),
            #             total=len(tasks),
            #             desc=desc,
            #             position=0,
            #             leave=True):
            #         all_results.append(result)
            #         i += 1
            #         self.progress.emit(i)
            #         if not self.running():
            #             break

            # with ThreadPool(processes=cpus) as pool:
            #     results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_pbar) for task in tasks]
            #     pool.close()
            #     [p.get() for p in results]
            #     # pool.join()

            dt = time.time() - t
            self._timing_results['t_scale_convert'][s] = dt
            logger.info(f"Elapsed Time: {dt:.3g}s")


        self.finished.emit()


        if not self.running():
            self.hudWarning.emit('Canceling Tasks:  Convert TIFFs to NGFF Zarr')
            self.finished.emit()
            return

        self.hudMessage.emit('**** Autoscaling Complete ****')
        logger.info('**** Autoscaling Complete ****')
        self.finished.emit()

def preallocate_zarr(zarr_od, name, shape, dtype, opts, scale):
    '''zarr.blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']'''
    cname, clevel, chunkshape = opts['cname'], opts['clevel'], opts['chunkshape'][scale]
    output_text = f'\n  Zarr root : {zarr_od}' \
                  f'\n      group :   └ {name} {dtype}/{cname}/{clevel}' \
                  f'\n      shape : {str(shape)} ' \
                  f'\n      chunk : {chunkshape}'
    logger.info(output_text)
    try:
        if os.path.exists(os.path.join(zarr_od, name)):
            remove_zarr(os.path.join(zarr_od, name))
        arr = zarr.group(store=zarr_od, overwrite=False)
        compressor = Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None
        arr.zeros(name=name, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=True)
    except:
        print_exception()
        logger.warning('Zarr Preallocation Encountered A Problem')


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


def run(task):
    """Call run(), catch exceptions."""
    try:
        #Critical bufsize=-1... allows blocking for reduction tasks
        process = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        process.wait()

        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))



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
    # logger.info('')
    result = []
    for s in scales:
        path = os.path.join(dest, 'tiff', s)
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        result.append(len(files))
        # print(f"# {level} Files: {len(files)}")
        # logger.info(f"# {s} files: {len(files)}")
    # logger.info('<<')
    return result


#/Users/joelyancey/.alignem_data/series/0816_DW02_3imgs/scale_24/img_src/SYGQK_003.tif


"""

23:25:33 [scale.preallocate_zarr:231] zarr_od=/Users/joelyancey/alignem_data/series/seriesU/zarr
23:25:33 [scale.preallocate_zarr:232] name=s1
23:25:33 [scale.preallocate_zarr:233] shape=(5, 4096, 4096)
23:25:33 [scale.preallocate_zarr:234] dtype=|u1
23:25:33 [scale.preallocate_zarr:235] 

opts={
'created': '2023-08-14_23-25-22', 
'count': 5, 
'paths': ['/Users/joelyancey/glanceem_swift/test_images/dummy1.tif', 
    ...'/Users/joelyancey/glanceem_swift/test_images/dummy5.tif'], 
'tiff_path': '/Users/joelyancey/alignem_data/series/seriesU/tiff', 
'zarr_path': '/Users/joelyancey/alignem_data/series/seriesU/zarr', 
'lvls': [24, 6, 2, 1], 
'scale_keys': ['s24', 's6', 's2', 's1'], 
'levels': 
    {'s24': {'size_zyx': [5, 170, 170], 'size_xy': [170, 170]}, 
    's6': {'size_zyx': [5, 682, 682], 'size_xy': [682, 682]}, 
    's2': {'size_zyx': [5, 2048, 2048], 'size_xy': [2048, 2048]}, 
    's1': {'size_zyx': [5, 4096, 4096], 'size_xy': [4096, 4096]}}, 
'settings': 
    {'scale_factors': [24, 6, 2, 1], 
    'clevel': 5, 
    'cname': 'none', 
    'chunkshape': (1, 1024, 1024), 
    'scales': 
        {24: {'resolution': [48, 48, 50]}, 
        6: {'resolution': [12, 12, 50]}, 
        2: {'resolution': [4, 4, 50]}, 
        1: {'resolution': [2, 2, 50]}}}}



"""