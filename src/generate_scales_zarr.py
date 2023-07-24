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
from concurrent.futures import ThreadPoolExecutor

import src.config as cfg
from src.helpers import get_scale_val, get_img_filenames, print_exception, renew_directory, \
    reorder_tasks, pretty_elapsed
from src.funcs_zarr import preallocate_zarr
import tqdm
import imagecodecs
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
            # logger.info(f'Converting {group} to Zarr...')
            pbar = tqdm.tqdm(total=len(task_groups[group]), position=0, leave=True, desc=f"Converting {group} to Zarr")
            def update_pbar(*a):
                pbar.update()

            # with ThreadPool(processes=cpus) as pool:
            #     results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_pbar) for task in task_groups[group]]
            #     pool.close()
            #     [p.get() for p in results]

            with ThreadPoolExecutor(max_workers=cpus) as executor:
                list(tqdm.tqdm(executor.map(convert_zarr, task_groups[group]), total=len(task_groups[group])))


            logger.info(f"Elapsed Time: {'%.3g' % (time.time() - t)}s")
            time.sleep(1)



        # pbar = tqdm.tqdm(total=len(tasks), position=0, leave=True)
        # pbar.set_description("Converting Downsampled Images to Zarr")
        # t0 = time.time()




        t_elapsed = time.time() - t0
        dm.t_scaling_convert_zarr = t_elapsed
        cfg.main_window.set_elapsed(t_elapsed, "Copy-convert scales to Zarr")
        # logger.info('<<<< Generate Zarr Scales End <<<<')

def imread(filename):
    # return first image in TIFF file as numpy array
    with open(filename, 'rb') as fh:
        data = fh.read()
    return imagecodecs.tiff_decode(data)

def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        store = zarr.open(out, write_empty_chunks=False)
        tif = libtiff.TIFF.open(fn)
        img = tif.read_image()[:, ::-1]  # np.array
        # img = imread(fn)[:, ::-1]
        store[ID, :, :] = img  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        # store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
        return 0
    except:
        print_exception()
        return 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    GenerateScalesZarr(src=args.src, out=args.out)
