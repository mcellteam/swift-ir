#!/usr/bin/env python3

import os
import sys
import shutil
import psutil
import time
import logging
import src.config as cfg
from src.helpers import print_exception, get_scale_val, create_project_structure_directories, \
    get_bindir, create_scale_one_symlinks
from .mp_queue import TaskQueue

__all__ = ['generate_scales']

logger = logging.getLogger(__name__)


def generate_scales(dm):
    logger.info('>>>> generate_scales >>>>')

    n_tasks = dm.n_sections() * (dm.n_scales() - 1)  #0901 #Refactor
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS) - 2
    # task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Scale Image Hierarchy (%d Cores)...' % cpus)
    task_queue = TaskQueue(n_tasks=n_tasks, parent=cfg.main_window, pbar_text='Generating Scale Image Hierarchy (%d Cores)...' % cpus)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    create_project_structure_directories(dm.dest(), dm.scales())
    iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')

    src = dm.source_path()
    imgs = dm.basefilenames()
    create_scale_one_symlinks(src=src, dest=dm.dest(), imgs=imgs)

    task_queue.start(cpus)
    assert dm.downscales() != 'scale_None'
    for s in dm.downscales():  # value string '1 2 4'
        scale_val = get_scale_val(s)
        logger.info("Queuing Downsample Tasks For Scale %d..." % scale_val)
        # for i, layer in enumerate(datamodel.get_iter(s)):
        for i, layer in enumerate(dm['data']['scales'][s]['alignment_stack']):
            base       = dm.base_image_name(s=s, l=i)
            if_arg     = os.path.join(src, base)
            ofn        = os.path.join(dm.dest(), s, 'img_src', os.path.split(if_arg)[1]) # <-- wrong path on second project
            of_arg     = 'of=%s' % ofn
            scale_arg  = '+%d' % scale_val
            task_queue.add_task([iscale2_c, scale_arg, of_arg, if_arg])
            if cfg.PRINT_EXAMPLE_ARGS:
                if i in [0, 1, 2]:
                    logger.info('generate_scales/iscale2 TQ Params (Example ID %d):\n%s' % (i, str([iscale2_c, scale_arg, of_arg, if_arg])))
            # if cfg.CODE_MODE == 'python':
            #     task_queue.add_task(cmd=sys.executable,
            #                         args=['src/job_single_scale.py', str(s), str(fn), str(ofn)], wd='.')
            layer['images']['base']['filename'] = ofn
    dt = task_queue.collect_results()
    results = task_queue.get_status_of_tasks()
    # show_mp_queue_results(task_queue=task_queue, dt=dt)
    print(f'results : {results}')
    print(f'dt      : {dt}')
    cfg.results = results
    cfg.dt = dt
    logger.info('<<<< generate_scales <<<<')



    '''
    ____task_queue Parameters (Example)____
    (1) : iscale2_c : /Users/joelyancey/glanceem_swift/alignEM/src/src/lib/bin_darwin/iscale2
    (2) : scale_arg : +2
    (3) : of_arg : of=/Users/joelyancey/glanceEM_SWiFT/test_projects/test993/scale_2/img_src/R34CA1-BS12.104.tif
    (4) : if_arg : /Users/joelyancey/glanceEM_SWiFT/test_images/r34_tifs/R34CA1-BS12.104.tif
    '''