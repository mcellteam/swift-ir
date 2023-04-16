#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
import argparse
import src.config as cfg
from src.mp_queue import TaskQueue
from src.helpers import get_scale_val, get_img_filenames, print_exception, get_scales_with_generated_alignments

__all__ = ['generate_multiscale_zarr']

logger = logging.getLogger(__name__)

Z_STRIDE = 1

def generate_multiscale_zarr(src, out):
    logger.critical('Generating Multiscale Zarr...')
    logger.info('src : %s\nout: %s' % (src, out))
    # Todo conditional handling of skips
    tasks_ = []
    imgs = sorted(get_img_filenames(os.path.join(src, cfg.data.scale, 'img_aligned')))
    logger.info('# images: %d' % len(imgs))
    chunkshape = cfg.data.chunkshape()
    for ID, img in enumerate(imgs):
        for scale in get_scales_with_generated_alignments(cfg.data.scales()):
            scale_val = get_scale_val(scale)
            path_out = os.path.join(out, 's' + str(scale_val))
            tasks_.append([ID, img, src, path_out, scale, str(chunkshape)])
    tasks = [[t for t in tasks_[x::Z_STRIDE]] for x in range(0, Z_STRIDE)]
    logger.info('\n(example task)\n%s' % str(tasks[0]))
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    task_queue = TaskQueue(n_tasks=len(tasks), parent=cfg.main_window, pbar_text='Generating Multiscale Zarr (%d Cores)...' % cpus)
    task_queue.start(cpus)
    for task in tasks:
        script = 'src/job_convert_zarr.py'
        task_args = [sys.executable,
                     script,
                     str(task[0]),          # ID
                     str(task[1]),          # img
                     str(task[2]),          # src
                     str(task[3]),          # out
                     str(task[4]),          # s str
                     str(0),
                     ]
        task_queue.add_task(task_args)
    cfg.main_window.tell('Copy-converting TIFFs to NGFF-Compliant Multiscale Zarr...')
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    logger.info('<<<< Generate Zarr End <<<<')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--src', type=str, help='Path containing scaled tiff subdirectories')
    ap.add_argument('-o', '--out', type=str, help='Path for Zarr output')
    args = ap.parse_args()
    generate_multiscale_zarr(src=args.src, out=args.out)
