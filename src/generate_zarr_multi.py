#!/usr/bin/env python3

import os
import sys
import psutil
import logging
import argparse
import src.config as cfg
from src.mp_queue import TaskQueue
from src.helpers import get_scale_val, get_img_filenames, print_exception

__all__ = ['generate_zarr_multi']

logger = logging.getLogger(__name__)

Z_STRIDE = 1

def generate_zarr_multi(src, out):
    logger.critical('>>>> Generate Zarr Multi <<<<')
    logger.info('src : %s\nout: %s' % (src, out))
    # Todo conditional handling of skips
    tasks_ = []
    imgs = sorted(get_img_filenames(os.path.join(src, cfg.data.scale(), 'img_aligned')))
    logger.info('# images: %d' % len(imgs))
    for ID, img in enumerate(imgs):
        for scale in cfg.data.aligned_list():
            scale_val = get_scale_val(scale)
            path_out = os.path.join(out, 's' + str(scale_val))
            tasks_.append([ID, img, src, path_out, scale])
    tasks = [[t for t in tasks_[x::Z_STRIDE]] for x in range(0, Z_STRIDE)]
    logger.info('\n(example task)\n%s' % str(tasks[0]))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=len(tasks), parent=cfg.main_window)
    task_queue.start(cpus)
    for task in tasks:
        script = 'src/job_convert_zarr_scales.py'
        task_args = [sys.executable,
                     script,
                     str(task[0]),          # ID
                     str(task[1]),          # img
                     str(task[2]),          # src
                     str(task[3]),          # out
                     str(task[4]),          # scale str
                     ]
        task_queue.add_task(task_args)
    task_queue.collect_results()
    try: task_queue.end_tasks()
    except: print_exception()
    task_queue.stop()
    del task_queue
    logger.critical('>>>> Generate Zarr End <<<<')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    generate_zarr_multi(src=args.src, out=args.out)
