#!/usr/bin/env python3

import os
import sys
import psutil
import logging
import argparse
import zarr
import numpy as np
from PIL import Image
from alignEM.image_utils import get_image_size
from alignEM.mp_queue import TaskQueue
from alignEM.em_utils import get_scale_key, get_scale_val, get_scales_list

__all__ = ['generate_zarr']

logger = logging.getLogger(__name__)

def generate_zarr(src, out):
    scales_list = get_scales_list()
    scales_str = ",".join([str(s) for s in scales_list])
    chunks = '64'
    scale_1 = os.path.join(src, 'scale_1', 'img_aligned')
    imgs = sorted(os.listdir(scale_1))
    n_imgs = len(imgs)
    dim_x, dim_y = [], []
    for scale in scales_list:
        single_img = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0]))
        width, height = single_img.size
        dim_x.append(width)
        dim_y.append(height)

    scale_vals = []
    for scale in scales_list:
        val = get_scale_val(scale)
        scale_vals.append(val)
    scale_vals_str = ",".join([str(s) for s in scale_vals])

    dim_x_str = ",".join([str(x) for x in dim_x])
    dim_y_str = ",".join([str(y) for y in dim_y])

    tasks = []
    for ID, img in enumerate(imgs):
        path_out = os.path.join(out, str(ID))
        tasks.append([ID, img, src, path_out, scales_str, chunks, n_imgs, dim_x_str, dim_y_str, scale_vals_str])
    zarr.DirectoryStore(src)
    logger.info('\nEXAMPLE TASK\n%s' % str(tasks[0]))
    cpus = min(psutil.cpu_count(logical=False), 48)
    scale_q = TaskQueue(n_tasks=len(tasks))
    scale_q.start(cpus)

    for task in tasks:
        task_args = [sys.executable,
                     os.path.abspath('job_convert_zarr.py'),
                     str(task[0]),          # ID
                     str(task[1]),          # img
                     str(task[2]),          # src
                     str(task[3]),          # out
                     str(task[4]),          # scales_list
                     str(task[5]),          # chunks
                     str(task[6]),          # # of images
                     str(task[7]),          # dim_x_str
                     str(task[8]),          # dim_y_str
                     str(task[9]),          # scale_vals_str

                     ]

        logger.info('-------------')
        logger.info("\n".join(task_args))
        scale_q.add_task(task_args)
    scale_q.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    scale_q.stop()
    del scale_q


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    src = args.src
    out = args.out
    generate_zarr(src=src, out=out)
