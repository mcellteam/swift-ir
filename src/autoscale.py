#!/usr/bin/env python3

import os
import sys
import time
import psutil
import shutil
import logging
import traceback
from datetime import datetime
import multiprocessing as mp
import subprocess as sp
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
import tqdm

# from thumbnailer import Thumbnailer
from generate_scales_zarr import GenerateScalesZarr
# from background_worker import BackgroundWorker
from data_model import DataModel

import src.config as cfg
# from qtpy.QtCore import QThreadPool


from src.helpers import print_exception, get_scale_val, create_project_structure_directories, \
    get_bindir, pretty_elapsed


__all__ = ['autoscale']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver', force=True)


def autoscale(dm:DataModel, make_thumbnails=True, gui=True, set_pbar=True):

    print(f'\n\n################ Generating Downsampled Images ################\n')

    # Todo This should check for existence of original source files before doing anything
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: Generate Scale Image Hierarchy')
        cfg.main_window.warn('Canceling Tasks: Copy-convert Scale Images to Zarr')
        return
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(dm) * len(dm.downscales()))
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    create_project_structure_directories(dm.dest(), dm.scales(), gui=gui)
    iscale2_c = os.path.join(my_path, 'lib', get_bindir(), 'iscale2')

    # Create Scale 1 Symlinks
    logger.info('Creating Scale 1 symlinks...')
    if gui:
        cfg.main_window.tell('Sym-linking full scale images...')
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

    logger.info('Creating downsampling tasks...')
    task_groups = {}
    for s in dm.downscales()[::-1]:  # value string '1 2 4'
        task_groups[s] = []
        scale_val = get_scale_val(s)
        for i, layer in enumerate(dm['data']['scales'][s]['stack']):
            base       = dm.base_image_name(s=s, l=i)
            if_arg     = os.path.join(src_path, base)
            ofn        = os.path.join(dm.dest(), s, 'img_src', os.path.split(if_arg)[1]) # <-- wrong path on second project
            of_arg     = 'of=%s' % ofn
            scale_arg  = '+%d' % scale_val
            task_groups[s].append([iscale2_c, scale_arg, of_arg, if_arg])
            layer['filename'] = ofn #0220+



    t0 = time.time()
    # with ThreadPool(processes=cpus) as pool:
    #     pool.map(run, tqdm.tqdm(tasks, total=len(tasks)))
    #     pool.close()
    #     pool.join()
    # for task in tasks:
    #     run2(task)

    # ctx = mp.get_context('forkserver')
    n_imgs = len(dm)
    logger.info(f'# images: {n_imgs}')


    for group in task_groups:
        logger.info(f'Downsampling {group}...')
        t = time.time()
        # with ctx.Pool() as pool:
        #     list(tqdm.tqdm(pool.imap_unordered(run, task_groups[group]), total=len(task_groups[group]), desc=f"Downsampling {group}", position=0, leave=True))
        #     pool.close() #0723+
        #     pool.join()

        # with mp.Pool(processes=cpus) as pool:
        # with mp.Pool(processes=cpus) as pool:
        #     pool.map(run, tqdm.tqdm(task_groups[group], total=len(task_groups[group]), desc=f"Downsampling {group}", position=0, leave=True))
        #     pool.close()
        #     pool.join()

        with ThreadPoolExecutor(max_workers=cpus) as executor:
            list(tqdm.tqdm(executor.map(run, task_groups[group]), total=len(task_groups[group]), position=0, leave=True))


        while any([x < n_imgs for x in count_files(dm.dest(), [group])]):
            # logger.info('Sleeping for 1 second...')
            time.sleep(1)

        logger.info(f"Elapsed Time: {'%.3g' % (time.time() - t)}s")
        cfg.main_window.set_elapsed(time.time() - t, f'Generate {group}')


    # ctx = mp.get_context('forkserver')
    # with ctx.Pool(processes=cpus) as pool:
    #     pool.map(run, tasks)
    #     pool.close()
    #     pool.join()
    # ctx = mp.get_context('forkserver')
    # pool = ctx.Pool(processes=cpus)
    # pool.map(run, tqdm.tqdm(tasks, total=len(tasks), desc="Downsampling", position=0, leave=True))
    # pool.close()
    # pool.join()

    # show_mp_queue_results(task_queue=task_queue, dt=dt)
    dm.t_scaling = time.time() - t0

    dm.link_reference_sections(s_list=dm.scales()) #This is necessary
    dm.scale = dm.scales()[-1]

    src_img_size = dm.image_size(s='scale_1')
    for s in dm.scales()[::-1]:
        if s == 'scale_1':
            continue
        sv = dm.scale_val(s)
        siz = (int(src_img_size[0] / sv), int(src_img_size[1] / sv))
        logger.info(f"setting {s} image size to {siz}...")
        dm['data']['scales'][s]['image_src_size'] = siz

    GenerateScalesZarr(dm, gui=gui)

    cfg.mw.tell('**** Autoscaling Complete ****')
    logger.info('<<<< autoscale <<<<')


def run(task):
    """Call run(), catch exceptions."""
    try:
        # sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))


class Command(object):
    # https://stackoverflow.com/questions/1191374/using-module-subprocess-with-timeout
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    def run(self, timeout):
        def target():
            print('Thread started')
            self.process = sp.Popen(self.cmd, shell=True)
            self.process.communicate()
            print('Thread finished')

        thread = sp.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            print('Terminating process')
            self.process.terminate()
            thread.join()
        print(self.process.returncode)


from os import kill
from signal import alarm, signal, SIGALRM, SIGKILL
from subprocess import PIPE, Popen

def run2(args, cwd = None, shell = False, kill_tree = True, timeout = -1, env = None):
    '''
    Run a command with a timeout after which it will be forcibly
    killed.
    '''
    class Alarm(Exception):
        pass
    def alarm_handler(signum, frame):
        raise Alarm
    p = Popen(args, shell = shell, cwd = cwd, stdout = PIPE, stderr = PIPE, env = env)
    if timeout != -1:
        signal(SIGALRM, alarm_handler)
        alarm(timeout)
    try:
        stdout, stderr = p.communicate()
        if timeout != -1:
            alarm(0)
    except Alarm:
        pids = [p.pid]
        if kill_tree:
            pids.extend(get_process_children(p.pid))
        for pid in pids:
            # process might have died before getting to this line
            # so wrap to avoid OSError: no such process
            try:
                kill(pid, SIGKILL)
            except OSError:
                pass
        return -9, '', ''
    return p.returncode, stdout, stderr

def get_process_children(pid):
    p = Popen('ps --no-headers -o pid --ppid %d' % pid, shell = True,
              stdout = PIPE, stderr = PIPE)
    stdout, stderr = p.communicate()
    return [int(p) for p in stdout.split()]

def count_files(dest, scales):
    result = []
    for s in scales:
        path = os.path.join(dest, s, 'img_src')
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        result.append(len(files))
        # print(f"# {s} Files: {len(files)}")
        print(f"# {s} Files: {len(files)}", end="\r")
    return result

# if any(count_files(dm))