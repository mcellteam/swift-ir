#!/usr/bin/env python3

import os
import sys
import psutil
import logging
import argparse
# import zarr
# from zarr.util import human_readable_size
# import numpy as np
# from PIL import Image
# from src.image_funcs import ImageSize
from src.mp_queue import TaskQueue
from src.helpers import get_scale_val, get_images_list_directly
import src.config as cfg

__all__ = ['generate_zarr']

logger = logging.getLogger(__name__)


def generate_zarr(src, out, no_scales=False, scale=None):
    logger.critical('>>>>>>>> Generate Zarr Start <<<<<<<<')
    logger.info('Source Image : %s\nOutput Image : %s' % (src, out))
    # Z_STRIDE = 4
    Z_STRIDE = 1
    n_imgs = cfg.data.n_imgs()
    n_scales = cfg.data.n_scales()

    # preallocate_zarr()

    if not no_scales:
        estimated_n_tasks = n_imgs * n_scales  # TODO this should take into account skips
    else:
        estimated_n_tasks = n_imgs

    tasks_ = []
    if not no_scales:
        imgs = sorted(get_images_list_directly(os.path.join(src, cfg.data.scale(), 'img_aligned')))
    else:
        imgs = sorted(get_images_list_directly(os.path.join(src, scale, 'img_src')))

    if not no_scales:
        for ID, img in enumerate(imgs):
            for scale in cfg.data.aligned_list():
                scale_val = get_scale_val(scale)
                path_out = os.path.join(out, 's' + str(scale_val))
                # width, height = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
                # import tifffile
                # width, height = tifffile.imread(os.path.join(src, scale, 'img_aligned', imgs[0])).size
                tasks_.append([ID, img, src, path_out, scale])
    else:
        logger.info('# images: %d' % len(imgs))
        for ID, img in enumerate(imgs):
            # logger.info('ID  = %d' % ID)
            # logger.info('img  = %s' % img)

            scale_val = get_scale_val(scale)
            path_out = os.path.join(out, 's' + str(scale_val))
            # width, height = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
            # import tifffile
            # width, height = tifffile.imread(os.path.join(src, scale, 'img_aligned', imgs[0])).size
            tasks_.append([ID, img, src, path_out, scale])

    logger.info('# tasks: %d' % len(tasks_))

    if not no_scales:
        tasks=[]
        # logger.critical('foo_list:\n%s' % str(foo_list))
        for x in range(0,Z_STRIDE): #chunk z_dim
            append_list = tasks_[x::Z_STRIDE]
            for t in append_list:
                tasks.append(t)
        # logger.critical('foo:\n%s' % str(foo))
    else:
        tasks = tasks_


    logger.info('\nExample Task:\n%s' % str(tasks[0]))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 1
    n_tasks = len(tasks)
    logger.info("Estimated # of tasks: %d" % estimated_n_tasks)
    logger.info('Actual # of tasks: %d' % n_tasks)
    cfg.main_window.pbar_max(n_tasks)
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window)
    task_queue.tqdm_desc = 'Exporting Zarr'
    task_queue.start(cpus)
    for task in tasks:
        if not no_scales:
            script = 'src/job_convert_zarr_scales.py'
        else:
            script = 'src/job_convert_zarr.py'


        task_args = [sys.executable,
                     script,
                     str(task[0]),          # ID
                     str(task[1]),          # img
                     str(task[2]),          # src
                     str(task[3]),          # out
                     str(task[4]),          # scale str
                     ]
        task_queue.add_task(task_args)
    task_queue.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    try: task_queue.end_tasks()
    except: pass
    task_queue.stop()
    del task_queue
    logger.critical('>>>>>>>> Generate Zarr End <<<<<<<<')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    src = args.src
    out = args.out
    generate_zarr(src=src, out=out)
