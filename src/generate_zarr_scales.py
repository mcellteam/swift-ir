#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import argparse
import src.config as cfg
from src.mp_queue import TaskQueue
from src.helpers import get_scale_val, get_img_filenames, print_exception, show_mp_queue_results, kill_task_queue, \
    renew_directory
from src.funcs_zarr import preallocate_zarr

__all__ = ['generate_zarr_scales']

logger = logging.getLogger(__name__)

Z_STRIDE = 1

def generate_zarr_scales():
    logger.critical('Generating Scaled Zarr Arrays....')
    # Todo conditional handling of skips

    src = os.path.abspath(cfg.data['data']['destination_path'])
    imgs = sorted(get_img_filenames(os.path.join(src, 'scale_1', 'img_src')))
    od = os.path.abspath(os.path.join(src, 'img_src.zarr'))
    renew_directory(directory=od)
    # preallocate_zarr_src()
    for scale in cfg.data.scales():
        dimx, dimy = cfg.data.image_size(s=scale)
        preallocate_zarr(name='img_src.zarr', scale=scale, dimx=dimx, dimy=dimy, dtype='uint8', overwrite=True)
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    n_tasks = len(cfg.data) * cfg.data.n_scales()
    cfg.main_window.hud('# Tasks: %d' % n_tasks)
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Zarr Scale Arrays - %d Cores' % cpus)
    task_queue.start(cpus)
    for ID, img in enumerate(imgs):
        for scale in cfg.data.scales()[::-1]:
            path_out = os.path.join(od, 's' + str(get_scale_val(scale)))
            script = 'src/job_convert_zarr.py'
            task_args = [sys.executable,
                         script,
                         str(ID),
                         img,
                         src,
                         path_out,
                         scale,
                         ]
            task_queue.add_task(task_args)
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    show_mp_queue_results(task_queue=task_queue, dt=dt)
    kill_task_queue(task_queue=task_queue)
    logger.info('<<<< Generate Zarr End <<<<')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    generate_zarr_scales(src=args.src, out=args.out)
