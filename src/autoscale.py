#!/usr/bin/env python3

import os
import sys
import time
import psutil
import shutil
import logging
import traceback
from datetime import datetime
from os import listdir
from os.path import isfile, join
import multiprocessing as mp
import subprocess as sp
from multiprocessing.pool import ThreadPool
import tqdm

# from thumbnailer import Thumbnailer
from generate_scales_zarr import GenerateScalesZarr
# from background_worker import BackgroundWorker
from data_model import DataModel

import src.config as cfg
# from generate_scales import GenerateScales
# from qtpy.QtCore import QThreadPool


from src.helpers import print_exception, get_scale_val, create_project_structure_directories, \
    get_bindir


__all__ = ['autoscale']

logger = logging.getLogger(__name__)

mp.set_start_method('forkserver', force=True)


def autoscale(dm:DataModel, make_thumbnails=True, gui=True, set_pbar=True):
    logger.critical('>>>> autoscale >>>>')

    # threadpool = QThreadPool.globalInstance()
    # threadpool.setExpiryTimeout(1000)
    #
    # # Todo This should check for existence of original source files before doing anything
    #
    # logger.info('Generating TIFF Scale Image Hierarchy...')
    # if gui:
    #     cfg.mw.tell('Generating TIFF Scale Image Hierarchy...')
    #     if set_pbar:
    #         cfg.mw.showZeroedPbar(set_n_processes=3)
    # try:
    #     worker = BackgroundWorker(fn=GenerateScales(dm=dm, gui=gui))
    #     threadpool.start(worker)
    # except:
    #     print_exception()
    #     logger.warning('Something Unexpected Happened While Generating TIFF Scale Hierarchy')
    #     if gui: cfg.mw.warn('Something Unexpected Happened While Generating TIFF Scale Hierarchy')

    GenerateScales(dm=dm, gui=gui)

    logger.info("\n\nFinished generating downsampled source images. Waiting 1 seconds...\n\n")

    time.sleep(1)


    dm.link_reference_sections(s_list=cfg.data.scales()) #This is necessary
    dm.scale = dm.scales()[-1]


    src_img_size = cfg.data.image_size(s='scale_1')
    for s in cfg.data.scales():
        if s == 'scale_1':
            continue
        sv = cfg.data.scale_val(s)
        siz = (int(src_img_size[0] / sv), int(src_img_size[1] / sv))
        logger.info(f"setting {s} image size to {siz}...")
        cfg.data['data']['scales'][s]['image_src_size'] = siz

    # for s in dm.scales():
    #     dm.set_image_size(s=s)

    logger.info('Copy-converting TIFFs to NGFF-Compliant Zarr...')
    # if gui:
    #     cfg.mw.tell('Copy-converting Downsampled Source Images to Zarr...')
    #     # cfg.mw.showZeroedPbar()
    # try:
    #     worker = BackgroundWorker(fn=GenerateScalesZarr(dm, gui=gui))
    #     threadpool.start(worker)
    # except:
    #     print_exception()
    #     logger.warning('Something Unexpected Happened While Converting The Scale Hierarchy To Zarr')
    #     if gui: cfg.mw.warn('Something Unexpected Happened While Generating Thumbnails')

    logger.info("\n\nGnerating Zarr Scales...\n\n")

    GenerateScalesZarr(dm, gui=gui)

    logger.info("\n\nFinished generating Zarrs of downsampled images. Waiting 1 seconds...\n\n")

    time.sleep(1)



    # if make_thumbnails:
    #     logger.info('Generating Source Thumbnails...')
    #     # if gui:
    #     #     cfg.mw.tell('Generating Source Image Thumbnails...')
    #     #     # cfg.mw.showZeroedPbar()
    #     # try:
    #     #     thumbnailer = Thumbnailer()
    #     #     worker = BackgroundWorker(fn=thumbnailer.reduce_main(dest=dm.dest()))
    #     #     threadpool.start(worker)
    #     # except:
    #     #     print_exception()
    #     #     logger.warning('Something Unexpected Happened While Generating Source Thumbnails')
    #     #     if gui: cfg.mw.warn('Something Unexpected Happened While Generating Source Thumbnails')
    #     thumbnailer = Thumbnailer()
    #     thumbnailer.reduce_main(dest=dm.dest())

    # if gui:
    #     cfg.mw.hidePbar()
    #     # if cfg.mw._isProjectTab():
    #     #     cfg.project_tab.initNeuroglancer()
    #     cfg.mw.tell('**** Autoscaling Complete ****')


    cfg.mw.tell('**** Autoscaling Complete ****')
    logger.info('<<<< autoscale <<<<')



def print_exception(extra=None):
    tstamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}]\nError Type : {exi[0]}\nError Value : {exi[1]}\n{traceback.format_exc()}"
    if extra:
        txt += f'\nExtra: {str(extra)}'
    logger.warning(txt)

    if cfg.data:
        log_path = os.path.join(cfg.data.dest(), 'logs', 'exceptions.log')
        if not os.path.exists(log_path):
            logger.warning('exceptions.log did not exist!')
            open(log_path, 'a').close()
        lf = os.path.join(log_path)
        with open(lf, 'a+') as f:
            f.write('\n' + txt)





def GenerateScales(dm, gui=True):
    cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(dm) * len(dm.downscales()))
    pbar_text = 'Generating Scale Image Hierarchy (%d Cores)...' % cpus
    if cfg.CancelProcesses:
        cfg.main_window.warn('Canceling Tasks: %s' % pbar_text)
    else:

        n_tasks = len(dm) * (dm.n_scales() - 1)  #0901 #Refactor
        dest = dm['data']['destination_path']
        logger.info(f'\n\n################ Generating Scales ################\n')
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

        with ThreadPool(processes=cpus) as pool:
            pool.map(run, tqdm.tqdm(tasks, total=len(tasks)))
            pool.close()
            pool.join()
        # ctx = mp.get_context('forkserver')
        # with ctx.Pool(processes=cpus) as pool:
        #     pool.map(run, tasks)
        #     pool.close()
        #     pool.join()
        # pool = ctx.Pool(processes=cpus)
        # pool.map(run, tqdm.tqdm(tasks, total=len(tasks)))
        # pool.close()
        # pool.join()
        dt = time.time() - t0




        # mypath = os.path.join(cfg.data.dest(), 'scale_2','img_src')
        # onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
        # print(str(onlyfiles))

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