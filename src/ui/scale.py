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
numcodecs.blosc.use_threads = False

from src.thumbnailer import Thumbnailer
from src.helpers import print_exception, create_project_structure_directories, get_bindir, get_scale_val, \
    renew_directory, renew_directory, get_img_filenames
from src.funcs_zarr import preallocate_zarr
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
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str) # (# tasks, description)
    hudWarning = Signal(str) # (# tasks, description)

    def __init__(self, dm):
        super().__init__()
        # print("Initializing Worker...", flush=True)
        print("Initializing Worker...")
        self.dm = dm
        self.result = None
        self._mutex = QMutex()
        self._running = True


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
        dm = self.dm

        print(f'\n\n######## Generating Downsampled Images ########\n', flush=True)

        # Todo This should check for source files before doing anything
        if not self.running():
            self.hudWarning.emit('Canceling Tasks: Generate Scale Image Hierarchy')
            self.hudWarning.emit('Canceling Tasks: Copy-convert Scale Images to Zarr')
            return
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(self.dm) * len(self.dm.downscales()))
        cur_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        create_project_structure_directories(self.dm.dest(), self.dm.scales(), gui=False)
        iscale2_c = os.path.join(Path(cur_path).parent.absolute(), 'lib', get_bindir(), 'iscale2')

        dm.link_full_resolution()

        logger.info('Creating downsampling tasks...')

        # self.dm.link_reference_sections(s_list=self.dm.scales()) #This is necessary
        # for s in self.dm.scales()[::-1]:
        #     if s != 'scale_1':
        #         siz = (np.array(self.dm.image_size(s='scale_1')) / self.dm.scale_val(s)).astype(int).tolist()
        #         self.dm['data']['scales'][s]['image_src_size'] = siz

        t0 = time.time()

        imgs = get_img_filenames(os.path.join(self.dm.location, 'scale_1', 'img_src'))
        zarr_od = os.path.abspath(os.path.join(self.dm.location, 'img_src.zarr'))
        renew_directory(directory=zarr_od, gui=False)
        logger.info(f'# images: {len(imgs)}')
        logger.info(f"cpus: {cpus}")
        ctx = mp.get_context('forkserver')
        for s in self.dm.downscales()[::-1]:
            desc = f'Downsampling {self.dm.scale_pretty(s)}...'
            logger.info(desc)

            tasks = []
            for i, layer in enumerate(self.dm['data']['scales'][s]['stack']):
                if_arg     = os.path.join(self.dm['data']['source_path'], self.dm.base_image_name(s=s, l=i))
                ofn        = os.path.join(self.dm.dest(), s, 'img_src', os.path.split(if_arg)[1])
                of_arg     = 'of=%s' % ofn
                scale_arg  = '+%d' % self.dm.scale_val(s)
                tasks.append([iscale2_c, scale_arg, of_arg, if_arg])
                layer['filename'] = ofn #0220+
                layer['alignment']['swim_settings']['fn_transforming'] = ofn

            self.initPbar.emit((len(tasks), desc))
            t = time.time()
            with ctx.Pool(processes=104, maxtasksperchild=1) as pool:
            # with ThreadPoolExecutor(max_workers=10) as pool:
                for i, result in enumerate(tqdm.tqdm(pool.imap_unordered(run, tasks),
                                                     total=len(tasks),
                                                     desc=desc, position=0,
                                                     leave=True)):
                    self.progress.emit(i)
                    if not self.running():
                        break
            dt = time.time() - t
            self.dm['data']['benchmarks']['scales'][s]['t_scale_generate'] = dt
            logger.info(f"Elapsed Time: {'%.3g' % dt}s")

            self.dm.link_reference_sections(s_list=[s]) #This is necessary
            # if s != 'scale_1':
            #     siz = (np.array(self.dm.image_size(s='scale_1')) / self.dm.scale_val(s)).astype(int).tolist()
            #     logger.info(f"Setting size for {s} to {siz}...")
            #     self.dm['data']['scales'][s]['image_src_size'] = siz



            if not self.running():
                self.hudWarning.emit('Canceling Tasks:  Convert TIFFs to NGFF Zarr')
                return

            desc = f"Converting {s} to Zarr"
            tasks = []
            for ID, img in enumerate(imgs):
                out = os.path.join(zarr_od, 's%d' % get_scale_val(s))
                fn = os.path.join(self.dm.location, s, 'img_src', img)
                tasks.append([ID, fn, out])

            x, y = self.dm.image_size(s=s)
            shape = (len(self.dm), y, x)
            grp = 's%d' % self.dm.scale_val(s=s)
            preallocate_zarr(dm=self.dm, name=zarr_od, group=grp, shape=shape, dtype='|u1', overwrite=True, gui=False)
            # t = time.time()
            # self.initPbar.emit((len(tasks), desc))
            # with ThreadPoolExecutor(max_workers=110) as executor:
            #     list(tqdm.tqdm(executor.map(convert_zarr, tasks), total=len(tasks), position=0, leave=True, desc=desc))

            t = time.time()
            self.initPbar.emit((len(tasks), desc))
            all_results = []
            i = 0
            # with ctx.Pool(processes=110, maxtasksperchild=1) as pool:
            with ctx.Pool(processes=104, maxtasksperchild=1) as pool:
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
            self.dm['data']['benchmarks']['scales'][s]['t_scale_convert'] = dt
            logger.info(f"ThreadPoolExecutor Time: {'%.3g' % dt}s")


            if s == dm.coarsest_scale_key():
                if dm['data']['autoalign_flag']:
                    self._alignworker = AlignWorker(scale=s,
                              path=None,
                              indexes=list(range(0,len(dm))),
                              swim_only=False,
                              renew_od=False,
                              reallocate_zarr=True,
                              dm=dm
                              )  # Step 3: Create a worker object

                    self._alignworker.run()
                    self.coarsestDone.emit()
                    QApplication.processEvents()





        # self.dm.t_scaling = time.time() - t0



        thumbnailer = Thumbnailer()
        self.dm.t_thumbs = thumbnailer.reduce_main(dest=self.dm.dest())

        # self.dm.scale = self.dm.scales()[-1]



        if not self.running():
            self.hudWarning.emit('Canceling Tasks:  Convert TIFFs to NGFF Zarr')
            return

        # print(f'\n\n######## Copy-converting TIFFs to NGFF Zarr ########\n')


        #
        # t0 = time.time()
        # # for group in task_groups:
        #
        # for s in self.dm.scales()[::-1]: # do coarsest scale first for quicker viewing
        #     desc = f"Converting {s} to Zarr"
        #     tasks = []
        #     for ID, img in enumerate(imgs):
        #         out = os.path.join(zarr_od, 's%d' % get_scale_val(s))
        #         fn = os.path.join(self.dm.location, s, 'img_src', img)
        #         tasks.append([ID, fn, out])
        #
        #     x, y = self.dm.image_size(s=s)
        #     shape = (len(self.dm), y, x)
        #     grp = 's%d' % self.dm.scale_val(s=s)
        #     preallocate_zarr(dm=self.dm, name=zarr_od, group=grp, shape=shape, dtype='|u1', overwrite=True, gui=False)
        #     # t = time.time()
        #     # self.initPbar.emit((len(tasks), desc))
        #     # with ThreadPoolExecutor(max_workers=110) as executor:
        #     #     list(tqdm.tqdm(executor.map(convert_zarr, tasks), total=len(tasks), position=0, leave=True, desc=desc))
        #
        #     t = time.time()
        #     self.initPbar.emit((len(tasks), desc))
        #     all_results = []
        #     i = 0
        #     # with ctx.Pool(processes=110, maxtasksperchild=1) as pool:
        #     with ctx.Pool(processes=104, maxtasksperchild=1) as pool:
        #         for result in tqdm.tqdm(
        #             pool.imap_unordered(convert_zarr, tasks),
        #                 total=len(tasks),
        #                 desc=desc,
        #                 position=0,
        #                 leave=True):
        #             all_results.append(result)
        #             i += 1
        #             self.progress.emit(i)
        #             if not self.running():
        #                 break
        #
        #     dt = time.time() - t
        #     self.dm['data']['benchmarks']['scales'][s]['t_scale_convert'] = dt
        #     logger.info(f"ThreadPoolExecutor Time: {'%.3g' % dt}s")
        #     if s == dm.coarsest_scale_key():
        #         self.coarsestDone.emit()
        #         QApplication.processEvents()



        # t_elapsed = time.time() - t0
        # self.dm.t_scaling_convert_zarr = t_elapsed



        self.hudMessage.emit('**** Autoscaling Complete ****')
        logger.info('**** Autoscaling Complete ****')
        self.finished.emit()



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