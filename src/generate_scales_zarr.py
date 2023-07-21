#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import argparse
import multiprocessing as mp
from multiprocessing.pool import ThreadPool
import src.config as cfg
# from src.mp_queue import TaskQueue
from src.helpers import get_scale_val, get_img_filenames, print_exception, renew_directory, \
    reorder_tasks
from src.funcs_zarr import preallocate_zarr
import tqdm
import numcodecs
import numpy as np
import zarr
numcodecs.blosc.use_threads = False
from libtiff import TIFF

__all__ = ['GenerateScalesZarr']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver')

Z_STRIDE = 1

def GenerateScalesZarr(dm, gui=True):
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(dm) * len(dm.scales()))

    pbar_text = 'Generating Zarr Scale Arrays (%d Cores)...' % cpus
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
    else:

        logger.info('Generating Scaled Zarr Arrays...')
        # Todo conditional handling of skips

        dest = dm.dest()
        imgs = get_img_filenames(os.path.join(dest, 'scale_1', 'img_src'))
        od = os.path.abspath(os.path.join(dest, 'img_src.zarr'))
        renew_directory(directory=od, gui=gui)
        for scale in dm.scales():
            x, y = dm.image_size(s=scale)
            group = 's%d' % get_scale_val(scale)
            preallocate_zarr(dm=dm,
                             name='img_src.zarr',
                             group=group,
                             dimx=x,
                             dimy=y,
                             dimz=len(dm),
                             dtype='uint8',
                             overwrite=True,
                             gui=gui)
        n_tasks = len(dm) * dm.n_scales()

        cfg.mw.set_status('Copy-converting scales to Zarr. No progress bar available. Awaiting multiprocessing pool...')
        cfg.mw.setPbarUnavailable(True)

        if gui: cfg.main_window.statusBar.showMessage('The next step may take a few minutes...')

        # dest = cfg.data['data']['destination_path']
        logger.info(f'\n\n################ Converting Downscales to Zarr ################\n')

        tasks = []
        for scale in dm.scales():
            for ID, img in enumerate(imgs):
                out = os.path.join(od, 's%d' % get_scale_val(scale))
                fn = os.path.join(dest, scale, 'img_src', img)
                tasks.append([ID, fn, out])

        cfg.mw.set_status('Generating Zarr. No progress bar available. Awaiting multiprocessing pool...')
        cfg.mw.setPbarUnavailable(True)
        logger.info("RUNNING MULTIPROCESSING POOL (CONVERT ZARR)...")
        pbar = tqdm.tqdm(total=len(tasks))
        t0 = time.time()

        def update_tqdm(*a):
            pbar.update()

        mp.set_start_method('forkserver')

        # with ctx.Pool(processes=cpus) as pool:
        with ThreadPool(processes=cpus) as pool:
            results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_tqdm) for task in tasks]
            pool.close()
            [p.get() for p in results]
            pool.join()
        logger.critical("----------END----------")
        cfg.mw.set_status('')
        dm.t_scaling_convert_zarr = time.time() - t0
        logger.info('<<<< Generate Zarr Scales End <<<<')
        cfg.mw.setPbarUnavailable(False)

def convert_zarr(task):
    ID = task[0]
    fn = task[1]
    out = task[2]
    store = zarr.open(out, write_empty_chunks=False)
    tif = TIFF.open(fn)
    img = tif.read_image()[:, ::-1]  # np.array
    store[ID, :, :] = img  # store: <zarr.core.Array (19, 1244, 1130) uint8>
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    GenerateScalesZarr(src=args.src, out=args.out)
