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
    renew_directory, reorder_tasks
from src.funcs_zarr import preallocate_zarr

__all__ = ['generate_zarr_scales']

logger = logging.getLogger(__name__)

Z_STRIDE = 1

def generate_zarr_scales():
    logger.info('Generating Scaled Zarr Arrays...')
    # Todo conditional handling of skips

    dest = cfg.data.dest()
    imgs = sorted(get_img_filenames(os.path.join(dest, 'scale_1', 'img_src')))
    od = os.path.abspath(os.path.join(dest, 'img_src.zarr'))
    renew_directory(directory=od)
    for scale in cfg.data.scales():
        x, y = cfg.data.image_size(s=scale)
        group = 's%d' % get_scale_val(scale)
        preallocate_zarr(name='img_src.zarr',
                         group=group,
                         dimx=x,
                         dimy=y,
                         dimz=cfg.data.n_layers(),
                         dtype='uint8',
                         overwrite=True)
    n_tasks = len(cfg.data) * cfg.data.n_scales()
    cfg.main_window.hud('# Tasks: %d' % n_tasks)
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Zarr Scale Arrays (%d Cores)...' % cpus)
    task_queue.start(cpus)
    script = 'src/job_convert_zarr.py'

    # store = zarr.open(out, synchronizer=synchronizer)
    # task_list = []
    for scale in cfg.data.scales():

        for ID, img in enumerate(imgs):

            out = os.path.join(od, 's%d' % get_scale_val(scale))
            # out = os.path.join(od, 's%d' % get_scale_val(scale))
            fn = os.path.join(dest, scale, 'img_src', img)
            # task_list.append([sys.executable, script, str(ID), fn, out ])
            task = [sys.executable, script, str(ID), fn, out ]
            print('\n'.join(task))
            task_queue.add_task(task)
            # task_queue.add_task([sys.executable, script, str(ID), fn, out ])
            # task_queue.add_task([sys.executable, script, str(ID), fn, store ])
    # n_scales = len(cfg.data.scales())
    # chunkshape = cfg.data.chunkshape()
    # z_stride = n_scales * chunkshape[0]
    # task_list = reorder_tasks(task_list, z_stride=z_stride)
    # for task in task_list:
    #     logger.info('Adding Layer %s Task' % task[2])
    #     task_queue.add_task(task)


    dt = task_queue.collect_results()
    show_mp_queue_results(task_queue=task_queue, dt=dt)
    kill_task_queue(task_queue=task_queue)
    logger.info('<<<< Generate Zarr Scales End <<<<')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    generate_zarr_scales(src=args.src, out=args.out)
