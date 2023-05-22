#!/usr/bin/env python3

import os
import sys
import logging
import traceback
from datetime import datetime
from generate_scales import generate_scales
from generate_scales_zarr import generate_scales_zarr
from background_worker import BackgroundWorker
from data_model import DataModel
from thumbnailer import Thumbnailer
import src.config as cfg
from qtpy.QtCore import QThreadPool

__all__ = ['autoscale']

logger = logging.getLogger(__name__)


def autoscale(dm:DataModel, make_thumbnails=True, gui=True):
    logger.critical('>>>> autoscale >>>>')

    threadpool = QThreadPool.globalInstance()
    threadpool.setExpiryTimeout(1000)

    # Todo This should check for existence of original source files before doing anything

    logger.info('Generating TIFF Scale Image Hierarchy...')
    if gui:
        cfg.mw.tell('Generating TIFF Scale Image Hierarchy...')
        cfg.mw.showZeroedPbar(reset_n_tasks=3, cancel_processes=False)
    try:
        worker = BackgroundWorker(fn=generate_scales(dm=dm, gui=gui))
        threadpool.start(worker)
    except:
        print_exception()
        logger.warning('Something Unexpected Happened While Generating TIFF Scale Hierarchy')
        if gui: cfg.mw.warn('Something Unexpected Happened While Generating TIFF Scale Hierarchy')


    dm.link_reference_sections() #This is necessary
    dm.scale = dm.scales()[-1]

    for s in dm.scales():
        dm.set_image_size(s=s)

    logger.info('Copy-converting TIFFs to NGFF-Compliant Zarr...')
    if gui:
        cfg.mw.tell('Copy-converting TIFFs to NGFF-Compliant Zarr...')
        cfg.mw.showZeroedPbar()
    try:
        worker = BackgroundWorker(fn=generate_scales_zarr(dm, gui=gui))
        threadpool.start(worker)
    except:
        print_exception()
        logger.warning('Something Unexpected Happened While Converting The Scale Hierarchy To Zarr')
        if gui: cfg.mw.warn('Something Unexpected Happened While Generating Thumbnails')

    if make_thumbnails:
        logger.info('Generating Source Thumbnails...')
        if gui:
            cfg.mw.tell('Generating Source Thumbnails...')
            cfg.mw.showZeroedPbar()
        try:
            thumbnailer = Thumbnailer()
            worker = BackgroundWorker(fn=thumbnailer.reduce_main(dest=dm.dest()))
            threadpool.start(worker)
        except:
            print_exception()
            logger.warning('Something Unexpected Happened While Generating Source Thumbnails')
            if gui: cfg.mw.warn('Something Unexpected Happened While Generating Source Thumbnails')

    if gui:
        cfg.mw.hidePbar()
        # if cfg.mw._isProjectTab():
        #     cfg.project_tab.initNeuroglancer()
        cfg.mw.tell('**** Autoscaling Complete ****')
    logger.info('<<<< autoscale <<<<')



def print_exception():
    tstamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f"  [{tstamp}]\nError Type : {exi[0]}\nError Value : {exi[1]}\n{traceback.format_exc()}"
    logger.warning(txt)

    if cfg.data:
        lf = os.path.join(cfg.data.dest(), 'logs', 'exceptions.log')
        with open(lf, 'a+') as f:
            f.write('\n' + txt)