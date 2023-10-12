#!/usr/bin/env python3

import os
import shutil
import time
import psutil
import logging
import platform
import imageio
import imageio.v3 as iio
from pathlib import Path
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
import multiprocessing as mp
import subprocess as sp
import numpy as np
import tqdm
import zarr
import neuroglancer as ng
import numcodecs
numcodecs.blosc.use_threads = False
import libtiff

from qtpy.QtCore import Signal, QObject, QMutex
from qtpy.QtWidgets import QApplication

from src.helpers import get_bindir, print_exception
from src.funcs_zarr import preallocate_zarr
from src.thumbnailer import Thumbnailer
import src.config as cfg

try:
    from src.swiftir import applyAffine, reptoshape
except Exception as e:
    print(e)
    try:
        from swiftir import applyAffine, reptoshape
    except Exception as e:
        print(e)

__all__ = ['ZarrWorker']

logger = logging.getLogger(__name__)


class ZarrWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    def __init__(self, dm, renew=False):
        super().__init__()
        logger.info('Initializing...')
        self.dm = dm
        self.renew = renew
        self._running = True
        self._mutex = QMutex()

    def running(self):
        try:
            self._mutex.lock()
            return self._running
        finally:
            self._mutex.unlock()


    def stop(self):
        logger.critical('Stopping!')
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()


    def run(self):
        logger.critical('Running...')
        self.generate()
        self.finished.emit() #Important!

    def generate(self):

        print(f"\n######## Generating/re-sync'ing Zarr ########\n")

        dm = self.dm
        dest = self.dm.data_location
        scale = self.dm.scale

        dm.set_stack_cafm(s=scale)

        # print_example_cafms(dm)

        zarr_group = os.path.join(dm.data_location, 'zarr', 's%d' % self.dm.lvl(s=scale))
        z = zarr.open(zarr_group)

        make_all = len(list(self.dm.zattrs.keys())) == 0

        indexes = []
        for i in range(len(self.dm)):
            # cur_ss_hash = str(self.dm.ssSavedHash(s=scale,l=i))
            cur_cafm_hash = str(self.dm.cafmHash(s=scale,l=i))
            # meta = z.attrs[str(i)]
            # zarr_ss_hash = meta[0]
            # zarr_cafm_hash = meta[1]

            if make_all:
                indexes.append(i)
                continue


            if self.dm.zarrCafmHashComports(s=scale, l=i):
                logger.info(f"Cache hit {cur_cafm_hash}! Zarr is correct at index {i}.")
            else:
                indexes.append(i)

        if not len(indexes):
            logger.info("\n\nZarr is in sync.\n")
            self.finished.emit()
            return


        if dm.has_bb():
            # Note: now have got new cafm'level -> recalculate bounding box
            rect = dm.set_calculate_bounding_rect(s=scale)  # Only after SetStackCafm
        else:
            w, h = dm.image_size(s=scale)
            rect = [0, 0, w, h]  # might need to swap w/h for Zarr
        logger.info(f'\n'
                    f'Bounding Box       : {dm.has_bb()}\n'
                    f'Polynomial Bias    : {dm.poly_order}\n'
                    f'Aligned Size       : {rect[2]} x {rect[3]}\n'
                    f'Offsets            : {rect[0]}, {rect[1]}')

        tasks = []
        # for i, sec in enumerate(dm()):
        to_reduce = []
        for i in indexes:
            ifp = dm.path(s=scale, l=i)  # input file path
            ofp = dm.path_aligned_cafm(s=scale, l=i)  # output file path
            # Todo add flag to force regenerate
            try:
                to_reduce.append((ofp, self.dm.path_aligned_cafm_thumb(s=scale, l=i)))
                print(f"Appending tuple: {(ofp, self.dm.path_aligned_cafm_thumb(s=scale, l=i))}")
            except:
                print_exception()

            if not os.path.exists(ofp):
                os.makedirs(os.path.dirname(ofp), exist_ok=True)
                # cafm = sec['levels'][scale]['cafm']
                # cafm = sec['levels'][scale]['cafm']
                cafm = self.dm['stack'][i]['levels'][scale]['cafm']
                tasks.append([ifp, ofp, rect, cafm, 128])
            else:
                logger.info(f'Cache hit (transformed image): {ofp}')

        n_tasks = len(tasks)
        logger.info(f"# of tasks: {n_tasks}")

        t0 = time.time()

        """Blocking"""
        ctx = mp.get_context('forkserver')
        # initPbar
        desc = f"Transforming images ({len(tasks)} tasks)"
        self.initPbar.emit((len(tasks), desc))
        all_results = []
        i = 0
        # cpus = (psutil.cpu_count(logical=False) - 2, 104)[is_tacc()]
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks))
        logger.info(f'# Processes: {cpus}')
        with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
            for result in tqdm.tqdm(
                    pool.imap_unordered(run_mir, tasks),
                    total=len(tasks),
                    desc=desc,
                    position=0,
                    leave=True):
                all_results.append(result)
                i += 1
                self.progress.emit(i)
                if not self.running():
                    break




        logger.info('\n######## Reducing tuples ########\n')
        Thumbnailer().reduce_tuples(to_reduce, scale_factor=self.dm.series['thumbnail_scale_factor'] // self.dm.lvl(scale))

        if not self.running():
            self.finished.emit()
            return

        print('\n######## Generating gif animations ########\n')
        generateAnimations(dm=self.dm, indexes=indexes, level=scale)

        if not self.running():
            self.finished.emit()
            return


        print(f'\n######## Copy-converting Images to Zarr ########\n')

        dm = self.dm
        scale = dm.scale

        # zarr_group = os.path.join(dm.data_location, 'zarr', 's%d' % dm.lvl())
        # z = zarr.open(zarr_group)

        # sshash_list = [str(dm.ssSavedHash(s=scale, l=i)) for i in range(len(dm))]
        # cafmhash_list = [str(dm.cafmHash(s=scale, l=i)) for i in range(len(dm))]
        # z.attrs.setdefault('ss_hash', sshash_list)
        # z.attrs.setdefault('cafm_hash', cafmhash_list)
        #
        # z.attrs.setdefault('ss_hash', {})
        # z.attrs.setdefault('cafm_hash', {})
        # z.attrs.setdefault('index', {})

        zp = dm.path_zarr_transformed(s=scale)
        # if not os.path.exists(zp):

        if self.renew:
            logger.info(f'Renewing Zarr directory: {zp}...')
            # os.makedirs(zp, exist_ok=True)
            tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            preallocate_zarr(dm=dm,
                             name='zarr',
                             group=scale,
                             shape=(len(dm), rect[3], rect[2]),
                             dtype='|u1',
                             overwrite=True,
                             attr=str(tstamp))

        z = zarr.open(zp)

        fu = dm.first_unskipped()

        tasks = []
        # for i in range(len(dm)):
        for i in indexes:
            ssHash = str(dm.ssSavedHash(s=scale, l=i))
            cafmHash = str(dm.cafmHash(s=scale, l=i))
            # src = dm.path_aligned(s=scale, l=i)
            src = dm.path_aligned_cafm(s=scale, l=i)
            if os.path.exists(src):
                # if not self.renew:
                #     try:
                #         zarrHashes = z.attrs
                #         print(f'--------')
                #         print(f'Zarr SS hash [{i}]      : {zarrHashes[i][0]}')
                #         print(f'Zarr cafm hash [{i}]    : {zarrHashes[i][1]}')
                #         ssHash = dm.ssSavedHash(s=scale,l=i)
                #         ssCafmHash = dm.cafmHash(s=scale,l=i)
                #         print(f'Current SS hash [{i}]   : {ssHash}')
                #         print(f'Current cafm hash [{i}] : {ssCafmHash}')
                #     except:
                #         print_exception()
                # save_to = os.path.join(dm.writeDir(s=scale, l=i), cafmHash)
                save_to = os.path.join(dm.writeDirCafm(s=scale, l=i), cafmHash)
                # z.attrs['index'][i] = {'index': i, 'source': src, 'copypath': save_to,
                #                             'ss_hash': ssHash, 'cafm_hash': cafmHash}
                # z.attrs['ss_hash'].update({i: ssHash})
                # z.attrs['cafm_hash'].update({i: cafmHash})
                z.attrs[i] = (ssHash, cafmHash)
                task = [i, src, zarr_group, save_to]
                tasks.append(task)
            else:
                logger.warning(f'TIFF Not Found: {src}')
        # shuffle(tasks)

        if len(tasks) == 0:
            logger.info('Zarr is already in sync. Complete.')
            self.finished.emit()
            return

        t0 = time.time()

        if ng.is_server_running():
            logger.info('Stopping Neuroglancer...')
            ng.server.stop()

        desc = f"Copy-convert to Zarr ({len(tasks)} tasks)"
        ctx = mp.get_context('forkserver')
        self.initPbar.emit((len(tasks), desc))
        # QApplication.processEvents()
        all_results = []
        # cpus = (psutil.cpu_count(logical=False) - 2, 80)[is_tacc()]
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks))
        logger.info(f"# Processes: {cpus}")
        i = 0
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
                # QApplication.processEvents()
                if not self.running():
                    break

        t_elapsed = time.time() - t0
        dm.t_convert_zarr = t_elapsed

        logger.info("Zarr conversion complete.")
        logger.info(f"Elapsed Time: {t_elapsed:.3g}s")
        self.finished.emit()

def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        save_to = task[3]
        store = zarr.open(out)
        # store.attr['test_attribute'] = {'key': 'value'}
        data = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>

        # os.remove(fn)
        shutil.rmtree(os.path.dirname(fn), ignore_errors=True)

        # np.save(save_to, data)
        store[ID, :, :] = data
        return 0
    except Exception as e:
        print(e)
        return 1


def print_example_cafms(dm):
    try:
        print('First Three CAFMs:')
        print(str(dm.cafm(l=0)))
        if len(dm) > 1:
            print(str(dm.cafm(l=1)))
        if len(dm) > 2:
            print(str(dm.cafm(l=2)))
    except:
        pass


def run_mir(task):
    in_fn = task[0]
    out_fn = task[1]
    rect = task[2]
    cafm = task[3]
    border = task[4]

    # Todo get exact median greyscale value for each image in list, for now just use 128

    app_path = os.path.split(os.path.realpath(__file__))[0]
    mir_c = os.path.join(app_path, 'lib', get_bindir(), 'mir')

    bb_x, bb_y = rect[2], rect[3]
    # afm = np.array(cafm)
    # logger.info(f"cafm: {str(cafm)}")
    afm = np.array([cafm[0][0], cafm[0][1], cafm[0][2], cafm[1][0], cafm[1][1], cafm[1][2]], dtype='float64').reshape((
        -1,
        3))
    # logger.info(f'afm: {str(afm.tolist())}')
    p1 = applyAffine(afm, (0, 0))  # Transform Origin To Output Space
    p2 = applyAffine(afm, (rect[0], rect[1]))  # Transform BB Lower Left To Output Space
    offset_x, offset_y = p2 - p1  # Offset Is Difference of 'p2' and 'p1'
    a = cafm[0][0]
    c = cafm[0][1]
    e = cafm[0][2] + offset_x
    b = cafm[1][0]
    d = cafm[1][1]
    f = cafm[1][2] + offset_y

    mir_script = \
        'B %d %d 1\n' \
        'Z %g\n' \
        'F %s\n' \
        'A %g %g %g %g %g %g\n' \
        'RW %s\n' \
        'E' % (bb_x, bb_y, border, in_fn, a, c, e, b, d, f, out_fn)
    o = run_command(mir_c, arg_list=[], cmd_input=mir_script)



def generateAnimations(dm, indexes, level):
    # https://stackoverflow.com/questions/753190/programmatically-generate-video-or-animated-gif-in-python

    first_unskipped = dm.first_unskipped(s=level)
    for i in indexes:
        if i == first_unskipped:
            continue
        ofn = dm.path_cafm_gif(s=level, l=i)
        os.makedirs(os.path.dirname(ofn), exist_ok=True)
        im0 = dm.path_aligned_cafm_thumb(s=level, l=i)
        im1 = dm.path_aligned_cafm_thumb_ref(s=level, l=i)
        if not os.path.exists(im0):
            logger.error(f'Not found: {im0}')
            return
        if not os.path.exists(im1):
            logger.error(f'Not found: {im0}')
            return
        try:
            images = [imageio.imread(im0), imageio.imread(im1)]
            imageio.mimsave(ofn, images, format='GIF', duration=1, loop=0)
        except:
            print_exception()


def run_command(cmd, arg_list=None, cmd_input=None):
    # logger.info("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    # logger.info(f"\nSTDOUT:\n{cmd_stdout}\n\nSTDERR:\n{cmd_stderr}\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr, 'rc': cmd_proc.returncode})