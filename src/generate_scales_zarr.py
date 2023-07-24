#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import argparse
from random import shuffle
import multiprocessing as mp
from multiprocessing.pool import ThreadPool
import src.config as cfg
from src.helpers import get_scale_val, get_img_filenames, print_exception, renew_directory, \
    reorder_tasks
from src.funcs_zarr import preallocate_zarr
import tqdm
import numcodecs
import zarr
numcodecs.blosc.use_threads = False

import libtiff
libtiff.libtiff_ctypes.suppress_warnings()

__all__ = ['GenerateScalesZarr']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver', force=True)


Z_STRIDE = 1

def GenerateScalesZarr(dm, gui=True):
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(dm) * len(dm.scales()))

    pbar_text = 'Generating Zarr Scale Arrays (%d Cores)...' % cpus
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
    else:
        print(f'\n\n################ Converting Downscales to Zarr ################\n')
        logger.info('Copy-converting TIFFs to NGFF-Compliant Zarr...')

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

        time.sleep(1)

        task_groups = {}
        for s in dm.scales()[::-1]:
            task_groups[s] = []
            for ID, img in enumerate(imgs):
                out = os.path.join(od, 's%d' % get_scale_val(s))
                fn = os.path.join(dest, s, 'img_src', img)
                task_groups[s].append([ID, fn, out])

        t0 = time.time()
        for group in task_groups:
            t = time.time()
            logger.info(f'Converting {group} to Zarr...')
            pbar = tqdm.tqdm(total=len(task_groups[group]), position=0, leave=True, desc=f"Converting {group} to Zarr")
            def update_pbar(*a):
                pbar.update()

            with ThreadPool(processes=cpus) as pool:
                [pool.apply_async(func=convert_zarr, args=(task,), callback=update_pbar) for task in task_groups[group]]
                pool.close()
                # [p.get() for p in results]
                pool.join()
            logger.info(f"Elapsed Time: {time.time() - t}")



        # pbar = tqdm.tqdm(total=len(tasks), position=0, leave=True)
        # pbar.set_description("Converting Downsampled Images to Zarr")
        # t0 = time.time()





        dm.t_scaling_convert_zarr = time.time() - t0
        # logger.info('<<<< Generate Zarr Scales End <<<<')

def convert_zarr(task):
    ID = task[0]
    fn = task[1]
    out = task[2]
    store = zarr.open(out, write_empty_chunks=False)
    tif = libtiff.TIFF.open(fn)
    img = tif.read_image()[:, ::-1]  # np.array
    store[ID, :, :] = img  # store: <zarr.core.Array (19, 1244, 1130) uint8>
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    GenerateScalesZarr(src=args.src, out=args.out)
