#!/usr/bin/env python3

import os
import sys
import signal
import shutil
import psutil
import logging
import argparse
import zarr
from zarr.util import human_readable_size
import numpy as np
from PIL import Image
from package.image_utils import get_image_size
from package.mp_queue import TaskQueue
from package.em_utils import get_scale_key, get_scale_val, get_scales_list, get_num_scales, get_aligned_scales_list
import package.config as cfg
from contextlib import contextmanager
# import numcodecs
# numcodecs.blosc.use_threads = False #may need
from numcodecs import Blosc
# blosc.set_nthreads(8)



class TimeoutException(Exception): pass

@contextmanager
def time_limit(seconds):
    def signal_handler(signum, frame):
        raise TimeoutException("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)



__all__ = ['generate_zarr_contig']

logger = logging.getLogger(__name__)

def generate_zarr_contig(src, out):
    scales_list = get_scales_list()
    scales_str = ",".join([str(s) for s in scales_list])
    chunks = '64'
    scale_1 = os.path.join(src, 'scale_1', 'img_aligned')
    imgs = sorted(os.listdir(scale_1))
    n_imgs = len(imgs)
    n_scales = get_num_scales()
    n_tasks = n_imgs * n_scales
    print('out: %s' % out)
    if os.path.isdir(out):

        try:
            with time_limit(15):
                logger.info('Removing %s...' % out)
                shutil.rmtree(out, ignore_errors=True)
        except TimeoutException as e:
            print("Timed out!")

        logger.info('Finished Removing Files')
    # store = zarr.NestedDirectoryStore(out, dimension_separator='/')
    store = zarr.DirectoryStore(out, dimension_separator='/')
    root = zarr.group(store=store, overwrite=True)
    logger.info('\n%s' % root.info)
    datasets = []
    al_scales_list = get_aligned_scales_list()

    for scale in al_scales_list:
        width, height = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
        scale_val = get_scale_val(scale)
        name = 's' + str(scale_val)
        logger.info('Creating a Zarr dataset named %s' % name)
        # from Docs:
        # z = zarr.zeros(1000000, compressor=Blosc(cname='zstd', clevel=1, shuffle=Blosc.SHUFFLE))

        opt_cname = cfg.main_window.cname_combobox.currentText()
        opt_clevel = int(cfg.main_window.clevel_input.text())


        '''
                tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compressor=None, overwrite=overwrite) # might pass in 'None'
    else:
        if cname in ('zstd', 'zlib'):
            tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compressor=Blosc(cname=cname, clevel=clevel), overwrite=overwrite)  # NOTE 'compressor='
            # tiffs2zarr(filenames, zarr_path + "/" + ds_name, tuple(chunks), compressor=zarr.get_codec({'id': cname, 'level': clevel}))
        else:
            tiffs2zarr(filenames, zarr_ds_path, chunk_shape_tuple, compression=cname, overwrite=overwrite)  # NOTE 'compression='
        
        '''
        if opt_cname in ('zstd', 'zlib', 'gzip'):
            root.zeros(name, shape=(n_imgs, height, width), chunks=(1, 64, 64), dtype='uint8',
                       compressor=Blosc(cname=opt_cname, clevel=opt_clevel))
        # elif opt_cname in ('gzip'):
        #     root.zeros(name, shape=(n_imgs, height, width), chunks=(1, 64, 64), dtype='uint8',
        #                compressor=opt_cname, synchronizer=zarr.ThreadSynchronizer())
        else:
            root.zeros(name, shape=(n_imgs, height, width), chunks=(1, 64, 64), dtype='uint8',
                       compressor=None)


        #, synchronizer=zarr.ThreadSynchronizer()

        datasets.append(
            {
                "path": name,
                "coordinateTransformations": [
                    {
                        "type": "scale",
                        "scale": [float(50.0),2*float(scale_val), 2*float(scale_val)]
                    }
                ]
            }
        )

    axes = [
                {"name": "z", "type": "space", "unit": "nanometer"},
                {"name": "y", "type": "space", "unit": "nanometer"},
                {"name": "x", "type": "space", "unit": "nanometer"}
            ]

    root.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    root.attrs['multiscales'] = [
        {
        "version": "0.4",
        "name": "my_data",
        # "_ARRAY_DIMENSIONS": ["z", "y", "x"],
        "axes": axes,
        "datasets": datasets,
        "type": "gaussian",
        }
    ]

    tasks = []
    for ID, img in enumerate(imgs):
        for scale in scales_list:
            scale_val = get_scale_val(scale)
            path_out = os.path.join(out, 's' + str(scale_val))
            width, height = Image.open(os.path.join(src, scale, 'img_aligned', imgs[0])).size
            tasks.append([ID, img, src, path_out, scale, chunks, n_tasks, width, height, scale_val])
    logger.info('\nExample Task:\n%s' % str(tasks[0]))
    cpus = min(psutil.cpu_count(logical=False), 48)
    scale_q = TaskQueue(n_tasks=len(tasks))
    scale_q.start(cpus)
    for task in tasks:
        task_args = [sys.executable,
                     'package/job_convert_zarr_contig.py',
                     str(task[0]),          # ID
                     str(task[1]),          # img
                     str(task[2]),          # src
                     str(task[3]),          # out
                     str(task[4]),          # scale str
                     str(task[5]),          # chunks
                     str(task[6]),          # # of tasks
                     str(task[7]),          # width
                     str(task[8]),          # height
                     str(task[9]),          # scale val
                     ]
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
    generate_zarr_contig(src=src, out=out)
