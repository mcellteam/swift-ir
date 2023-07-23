#!/usr/bin/env python3

import os
import sys
import shutil
import psutil
import time
import logging
import src.config as cfg
import multiprocessing as mp
import subprocess as sp
from src.helpers import print_exception, get_scale_val, create_project_structure_directories, \
    get_bindir
# from src.mp_queue import TaskQueue

__all__ = ['GenerateScales']

logger = logging.getLogger(__name__)


def GenerateScales(dm, gui=True):
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(dm) * len(dm.downscales()))
    pbar_text = 'Generating Scale Image Hierarchy (%d Cores)...' % cpus
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
    else:

        n_tasks = len(dm) * (dm.n_scales() - 1)  #0901 #Refactor
        dest = dm['data']['destination_path']
        print(f'\n\n################ Generating Scales ################\n')
        task_name_list = []
        for s in dm.downscales():  # value string '1 2 4'
            scale_val = get_scale_val(s)
            for layer in dm['data']['scales'][s]['stack']:
                task_name_list.append('%s (scaling factor: %d)' %(os.path.basename(layer['filename']), scale_val))

        my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
        create_project_structure_directories(dm.dest(), dm.scales(), gui=gui)
        iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')

        # Create Scale 1 Symlinks
        logger.info('Creating Scale 1 symlinks')
        if gui:
            cfg.main_window.tell('Sym-linking full scale_key images...')
        src_path = dm.source_path()
        for img in dm.basefilenames():
            fn = os.path.join(src_path, img)
            ofn = os.path.join(dm.dest(), 'scale_1', 'img_src', os.path.split(fn)[1])
            # normalize path for different OSs
            if os.path.abspath(os.path.normpath(fn)) != os.path.abspath(os.path.normpath(ofn)):
                try:    os.unlink(ofn)
                except: pass
                try:    os.symlink(fn, ofn)
                except:
                    logger.warning("Unable to link from %s to %s. Copying instead." % (fn, ofn))
                    try:    shutil.copy(fn, ofn)
                    except: logger.warning("Unable to link or copy from " + fn + " to " + ofn)

        tasks = []
        for s in dm.downscales():  # value string '1 2 4'
            scale_val = get_scale_val(s)
            for i, layer in enumerate(dm['data']['scales'][s]['stack']):
                base       = dm.base_image_name(s=s, l=i)
                if_arg     = os.path.join(src_path, base)
                ofn        = os.path.join(dm.dest(), s, 'img_src', os.path.split(if_arg)[1]) # <-- wrong path on second project
                of_arg     = 'of=%s' % ofn
                scale_arg  = '+%d' % scale_val
                tasks.append([iscale2_c, scale_arg, of_arg, if_arg])
                layer['filename'] = ofn #0220+

        logger.info('Beginning downsampling ThreadPool...')
        t0 = time.time()
        ctx = mp.get_context('forkserver')
        # with ctx.Pool(processes=cpus) as pool:
        #     pool.map(run, tasks)
        #     pool.close()
        #     pool.join()
        pool = ctx.Pool(processes=cpus)
        pool.map(run, tasks)
        pool.close()
        pool.join()
        dt = time.time() - t0

        # show_mp_queue_results(task_queue=task_queue, dt=dt)
        dm.t_scaling = dt
        logger.info('Done generating scales.')


def run(task):
    """Call run(), catch exceptions."""
    try:
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))