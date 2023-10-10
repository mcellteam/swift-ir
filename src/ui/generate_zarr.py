#!/usr/bin/env python3

import os
import time
import psutil
import logging
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

from src.funcs_zarr import preallocate_zarr
import src.config as cfg

__all__ = ['ZarrWorker']

logger = logging.getLogger(__name__)


class ZarrWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    def __init__(self, dm, ht):
        super().__init__()
        logger.info('Initializing...')
        self.dm = dm
        self.ht = ht
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

        print(f'\n######## Copy-converting Images to Zarr ########\n')

        dm = self.dm
        scale = dm.scale

        zarr_group = os.path.join(dm.data_location, 'zarr', 's%d' % dm.lvl())
        z = zarr.open(zarr_group)

        # sshash_list = [str(dm.ssSavedHash(s=scale, l=i)) for i in range(len(dm))]
        # cafmhash_list = [str(dm.cafmHash(s=scale, l=i)) for i in range(len(dm))]
        # z.attrs.setdefault('ss_hash', sshash_list)
        # z.attrs.setdefault('cafm_hash', cafmhash_list)
        #
        # z.attrs.setdefault('ss_hash', {})
        # z.attrs.setdefault('cafm_hash', {})
        # z.attrs.setdefault('index', {})

        tasks = []
        for i in range(len(dm)):
            ssHash = str(dm.ssSavedHash(s=scale, l=i))
            cafmHash = str(dm.cafmHash(s=scale, l=i))
            # al_name = dm.path_aligned(s=scale, l=i)
            al_name = dm.path_aligned_saved(s=scale, l=i)
            # save_to = os.path.join(dm.writeDir(s=scale, l=i), cafmHash)
            save_to = os.path.join(dm.writeDirSaved(s=scale, l=i), cafmHash)
            # z.attrs['index'][i] = {'index': i, 'source': al_name, 'copypath': save_to,
            #                             'ss_hash': ssHash, 'cafm_hash': cafmHash}
            # z.attrs['ss_hash'].update({i: ssHash})
            # z.attrs['cafm_hash'].update({i: cafmHash})
            z.attrs[i] = (ssHash, cafmHash)
            task = [i, al_name, zarr_group, save_to]
            tasks.append(task)
        # shuffle(tasks)

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

def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        save_to = task[3]
        store = zarr.open(out)
        # store.attr['test_attribute'] = {'key': 'value'}
        data = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        np.save(save_to, data)
        store[ID, :, :] = data
        return 0
    except Exception as e:
        print(e)
        return 1

