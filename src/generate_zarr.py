#!/usr/bin/env python3

import os
import sys
import signal
import shutil
import psutil
import logging
import argparse
import zarr
from zarr.util import human_readable_size
import numpy as np
from PIL import Image
from src.image_utils import get_image_size
from src.mp_queue import TaskQueue
from src.em_utils import get_cur_scale_key, get_scale_key, get_scale_val, get_scales_list, get_num_scales, \
    get_aligned_scales_list, get_images_list_directly, get_num_imported_images
import src.config as cfg
from contextlib import contextmanager
# import numcodecs
# numcodecs.blosc.use_threads = False #may need
from numcodecs import Blosc
# blosc.set_nthreads(8)

__all__ = ['generate_zarr']

logger = logging.getLogger(__name__)

class TimeoutException(Exception): pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

def generate_zarr(src, out):
    logger.critical('>>>>>>>> Generate Zarr Start <<<<<<<<')
    logger.info('Input 1: src = %s' % src)
    logger.info('Input 2: out = %s' % out)

    scales_list = get_scales_list()
    chunks = '4,64,64'
    Z_STRIDE = 4

    if os.path.isdir(out):
        try:
            with time_limit(15):
                logger.info('Removing %s...' % out)
                shutil.rmtree(out, ignore_errors=True)
        except TimeoutException as e:
            print("Timed out!")
        logger.info('Finished Removing Files')
    store = zarr.DirectoryStore(out, dimension_separator='/')
    root = zarr.group(store=store, overwrite=True)

    # n_imgs = len(get_images_list_directly(os.path.join(src, get_cur_scale_key()))) # bug
    n_imgs = get_num_imported_images()
    al_scales_list = get_aligned_scales_list()
    print(al_scales_list)
    n_scales = len(al_scales_list)
    print('n_scales = %d' % n_scales)
    print('n_imgs = %d' % n_imgs)
    estimated_n_tasks = n_imgs * n_scales #TECHNICALLY THIS SHOULD TAKE INTO ACCOUNT SKIPS
    datasets = []
    for scale in al_scales_list:
        imgs = sorted(get_images_list_directly(os.path.join(src, scale, 'img_aligned')))
        n_imgs = len(imgs)
        width, height = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
        cfg.main_window.hud.post('Image dimensions at Scale %s: %dpx x %dpx' % (scale[-1], width, height))
        scale_val = get_scale_val(scale)
        name = 's' + str(scale_val)
        cfg.main_window.hud.post('Creating a Zarr dataset named %s' % name)
        opt_cname = cfg.main_window.cname_combobox.currentText()
        opt_clevel = int(cfg.main_window.clevel_input.text())
        if opt_cname in ('zstd', 'zlib', 'gzip'):
            root.zeros(name, shape=(n_imgs, height, width), chunks=(Z_STRIDE, 64, 64), dtype='uint8',
                       compressor=Blosc(cname=opt_cname, clevel=opt_clevel))
        # elif opt_cname in ('gzip'):
        #     root.zeros(name, shape=(n_imgs, height, width), chunks=(1, 64, 64), dtype='uint8',
        #                compressor=opt_cname, synchronizer=zarr.ThreadSynchronizer())
        else:
            root.zeros(name, shape=(n_imgs, height, width), chunks=(Z_STRIDE, 64, 64), dtype='uint8',
                       compressor=None)
        #, synchronizer=zarr.ThreadSynchronizer()
        datasets.append(
            {
                "path": name,
                "coordinateTransformations": [
                    {
                        "type": "scale",
                        "scale": [float(50.0),2*float(scale_val), 2*float(scale_val)]
                    }
                ]
            }
        )

    axes = [
                {"name": "z", "type": "space", "unit": "nanometer"},
                {"name": "y", "type": "space", "unit": "nanometer"},
                {"name": "x", "type": "space", "unit": "nanometer"}
            ]

    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
        "version": "0.4",
        "name": "my_data",
        # "_ARRAY_DIMENSIONS": ["z", "y", "x"],
        "axes": axes,
        "datasets": datasets,
        "type": "gaussian",
        }
    ]

    tasks_ = []
    for ID, img in enumerate(imgs):
        for scale in al_scales_list:
            scale_val = get_scale_val(scale)
            path_out = os.path.join(out, 's' + str(scale_val))
            width, height = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
            tasks_.append([ID, img, src, path_out, scale, chunks, estimated_n_tasks, width, height, scale_val])
    logger.critical("Estimated # of tasks: %d" % estimated_n_tasks)
    logger.critical('# of tasks: %d' % len(tasks_))
    tasks=[]
    for x in range(0,Z_STRIDE): #chunk z_dim
        append_list = tasks_[x::Z_STRIDE]
        for t in append_list:
            tasks.append(t)

    logger.critical('# of shuffled tasks: %d' % len(tasks))

    n_tasks = len(tasks)
    logger.info('\nExample Task:\n%s' % str(tasks[0]))
    cpus = min(psutil.cpu_count(logical=False), 48)
    scale_q = TaskQueue(n_tasks=n_tasks)
    scale_q.tqdm_desc = 'Exporting Zarr'
    scale_q.start(cpus)
    for task in tasks:
        task_args = [sys.executable,
                     'src/job_convert_zarr.py',
                     str(task[0]),          # ID
                     str(task[1]),          # img
                     str(task[2]),          # src
                     str(task[3]),          # out
                     str(task[4]),          # scale str
                     str(task[5]),          # chunks
                     str(task[6]),          # # of tasks
                     str(task[7]),          # width
                     str(task[8]),          # height
                     str(task[9]),          # scale val
                     ]
        scale_q.add_task(task_args)
    scale_q.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    scale_q.stop()
    del scale_q
    logger.critical('>>>>>>>> Generate Zarr End <<<<<<<<')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    src = args.src
    out = args.out
    generate_zarr(src=src, out=out)
