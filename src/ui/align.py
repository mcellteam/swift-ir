#!/usr/bin/env python3

import os
import re
import sys
import copy
import json
import glob
import time
import errno
import shutil
import psutil
import logging
import imageio
import imageio.v3 as iio
from pathlib import Path
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
import multiprocessing as mp
import subprocess as sp
import numpy as np
import tqdm
import zarr
import neuroglancer as ng
# import imagecodecs
import numcodecs
numcodecs.blosc.use_threads = False
import libtiff
# libtiff.libtiff_ctypes.suppress_warnings()
# sys.path.insert(1, os.path.dirname(os.path.split(os.path.realpath(__file__))[0]))
# sys.path.insert(1, os.path.split(os.path.realpath(__file__))[0])
from src.data_model import DataModel
from src.funcs_image import SetStackCafm
from src.thumbnailer import Thumbnailer
from src.mp_queue import TaskQueue
from src.ui.timer import Timer
from src.recipe_maker import run_recipe
from src.helpers import print_exception, pretty_elapsed, is_tacc, get_bindir, get_n_tacc_cores
# from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_val, renew_directory, file_hash, pretty_elapsed, is_tacc
from src.funcs_zarr import preallocate_zarr
import src.config as cfg

from qtpy.QtCore import Signal, QObject, QMutex
from qtpy.QtWidgets import QApplication

try:
    from src.swiftir import applyAffine, reptoshape
except Exception as e:
    print(e)
    try:
        from swiftir import applyAffine, reptoshape
    except Exception as e:
        print(e)

__all__ = ['AlignWorker']

logger = logging.getLogger(__name__)




class AlignWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    def __init__(self, scale, path, align_indexes, regen_indexes, align, regenerate, renew_od, reallocate_zarr, dm, ht):
        super().__init__()
        logger.info('Initializing...')
        self.scale = scale
        self.path = path
        self.align_indexes = align_indexes
        self.regen_indexes = regen_indexes
        self._align = align #Temporary
        self._generate = regenerate
        self._renew_od = renew_od
        self._reallocate_zarr = reallocate_zarr
        self.dm = dm
        self.ht = ht
        self.result = None
        self._running = True
        self._mutex = QMutex()
        self.finished.connect(lambda: logger.critical('Finished!'))

        self._tasks = []
        if self._align:
            self._tasks.append(self.align)
        if self._generate:
            self._tasks.append(self.generate)


    def running(self):
        try:
            self._mutex.lock()
            return self._running
        finally:
            self._mutex.unlock()


    def stop(self):
        logger.critical('Stopping!')
        self._mutex.lock()
        self._running = False
        self._mutex.unlock()


    def run(self):
        logger.critical('Running...')
        while self._tasks and self.running():
            self._tasks.pop(0)()
        self.finished.emit() #Important!


    def align(self):
        """Long-running task."""
        logger.critical('\n\nAligning...\n')


        scale = self.scale
        indexes = self.align_indexes
        dm = self.dm

        if 5 in indexes:
            logger.critical(f"\nss hash      : {dm.ssHash(l=5)}\n"
                            f"ss saved hash : {dm.ssSavedHash(l=5)}\n"
                            f"cafm hash    : {dm.cafmHash(l=5)}")

        if scale == dm.coarsest_scale_key():
            logger.info(f'INITIALIZING affine for {len(indexes)} alignment pairs...')
        else:
            logger.info(f'REFINING affine for {len(indexes)} alignment pairs...')

        scratchpath = os.path.join(dm.series_location, 'logs', 'scratch.log')
        if os.path.exists(scratchpath):
            os.remove(scratchpath)

        # checkForTiffs(path)

        first_unskipped = dm.first_unskipped(s=scale)

        tasks = []
        for zpos, sec in [(i, dm()[i]) for i in indexes]:
            zpos = dm().index(sec)
            for key in ['swim_args', 'swim_out', 'swim_err', 'mir_toks', 'mir_script', 'mir_out', 'mir_err']:
                sec['levels'][scale]['results'].pop(key, None)
            # ss = sec['levels'][scale]['swim_settings']
            ss = copy.deepcopy(dm.swim_settings(s=scale, l=zpos))
            ss['path'] = dm.path(s=scale, l=zpos)
            ss['path_reference'] = dm.path_ref(s=scale, l=zpos)
            ss['dir_signals'] = dm.dir_signals(s=scale, l=zpos)
            ss['dir_matches'] = dm.dir_matches(s=scale, l=zpos)
            ss['dir_tmp'] = dm.dir_tmp(s=scale, l=zpos)
            # print(f"path : {ss['path']}")
            # print(f" ref : {ss['path_reference']}")

            wd = dm.ssDir(s=scale, l=zpos)  # write directory
            os.makedirs(wd, exist_ok=True)
            wp = os.path.join(wd, 'swim_settings.json')  # write path
            with open(wp, 'w') as f:
                jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                f.write(jde.encode(dm.swim_settings(s=scale, l=zpos)))

            # if (len(indexes) == len(dm)) or (ss['include'] and (zpos != first_unskipped)):
            if ss['include'] and (zpos != first_unskipped):
                tasks.append(copy.deepcopy(ss))
                # tasks.append(copy.deepcopy(ss))
            else:
                logger.info(f"EXCLUDING section #{zpos}")

        # delete_correlation_signals(dm=dm, scale=scale, indexes=indexes)
        # delete_matches(dm=dm, scale=scale, indexes=indexes)

        dest = dm.data_location

        if is_tacc():
            cpus = get_n_tacc_cores(n_tasks=len(tasks))
            if is_tacc() and (scale == 's1'):
                # cpus = 34
                cpus = cfg.SCALE_1_CORES_LIMIT
        else:
            cpus = psutil.cpu_count(logical=False) - 2

        t0 = time.time()

        # f_recipe_maker = f'{os.path.split(os.path.realpath(__file__))[0]}/src/recipe_maker.py'

        if cfg.USE_POOL_FOR_SWIM:
            ctx = mp.get_context('forkserver')
            desc = f"Computing Affines ({len(tasks)} tasks)"
            self.initPbar.emit((len(tasks), desc))
            all_results = []

            # config = {
            #     'dev_mode': cfg.DEV_MODE,
            #     'verbose_swim': cfg.VERBOSE_SWIM,
            #     'log_recipe_to_file': cfg.LOG_RECIPE_TO_FILE,
            #     'target_thumb_size': cfg.TARGET_THUMBNAIL_SIZE,
            #     'series_location': cfg.data.series_location,
            # }

            # for i in range(len(tasks)):
            #     tasks[i] = (tasks[i], config)

            cfg.CONFIG = {
                'dev_mode': cfg.DEV_MODE,
                'verbose_swim': cfg.VERBOSE_SWIM,
                'log_recipe_to_file': cfg.LOG_RECIPE_TO_FILE,
                'target_thumb_size': cfg.TARGET_THUMBNAIL_SIZE,
                'series_location':dm.series_location,
                'data_location': dm.data_location,
            }

            logger.info(f'max # workers: {cpus}')
            with ThreadPoolExecutor(max_workers=cpus) as pool:
                for i, result in enumerate(tqdm.tqdm(pool.map(run_recipe, tasks),
                                                     total=len(tasks),
                                                     desc=desc, position=0,
                                                     leave=True)):
                    all_results.append(result)
                    self.progress.emit(i)
                    if not self.running():
                        break

            try:
                assert len(all_results) > 0
            except AssertionError:
                logger.error('AssertionError: Alignment failed! No results.')
                self.finished.emit()
                return

            logger.critical(f"# Completed Alignment Tasks: {len(all_results)}")
        else:

            task_queue = TaskQueue(n_tasks=len(tasks), dest=dest)
            task_queue.taskPrefix = 'Computing Alignment for '
            task_queue.taskNameList = [os.path.basename(layer['swim_settings']['path']) for
                                       layer in [dm()[i] for i in indexes]]
            task_queue.start(cpus)
            align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'recipe_maker.py')
            logger.info('adding tasks to the queue...')
            for zpos, sec in [(i, dm()[i]) for i in indexes]:
                if sec['include'] and (zpos != first_unskipped):
                # if zpos != first_unskipped:
                    # encoded_data = json.dumps(copy.deepcopy(sec))
                    encoded_data = json.dumps(sec['levels'][scale])
                    task_args = [sys.executable, align_job, encoded_data]
                    task_queue.add_task(task_args)
            dt = task_queue.collect_results()
            dm.t_align = dt
            tq_results = task_queue.task_dict

            dm.t_align = time.time() - t0

            logger.info('Reading task results and updating data model...')
            # # For use with mp_queue.py ONLY

            all_results = []
            for tnum in range(len(tq_results)):
                # Get the updated datamodel previewmodel from stdout for the task
                parts = tq_results[tnum]['stdout'].split('---JSON-DELIMITER---')
                dm_text = None
                for p in parts:
                    ps = p.strip()
                    if ps.startswith('{') and ps.endswith('}'):
                        all_results.append(json.loads(p))

        logger.critical(f"# results returned: {len(all_results)}")

        ident = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()
        fu = dm.first_unskipped()
        fu_ss = dm.swim_settings(s=scale, l=fu)
        self.ht.put(fu_ss, ident)

        for i,r in enumerate(all_results):
            try:
                assert np.array(r['affine_matrix']).shape == (2, 3)
                # assert np.array(r['affine_matrix']).all() != np.array([[1., 0., 0.], [0., 1., 0.]]).all()
            except:
                siz = len(cfg.pt.ht.data)
                print_exception(extra=f"Alignment failed at index {r['index']}")
                continue
            dm['stack'][r['index']]['levels'][scale]['results'] = r

            ss = dm['stack'][r['index']]['levels'][scale]['swim_settings']
            key = HashableDict(ss)
            # index = r['index']
            # key = dm.swim_settings(s=scale, l=index)

            # value = r
            value = r['affine_matrix']
            if value != ident:
                self.ht.put(key, value)
            wd = dm.ssDir(s=scale, l=i)  # write directory
            wp = os.path.join(wd, 'results.json')  # write path
            os.makedirs(wd, exist_ok=True)
            with open(wp, 'w') as f:
                jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                f.write(jde.encode(r))

        # SetStackCafm(dm, scale=scale, poly_order=dm.poly_order)
        dm.set_stack_cafm()

        if not self.running():
            self.finished.emit()
            return

        t_elapsed = time.time() - t0
        dm.t_align = t_elapsed
        logger.info(f"Elapsed Time, SWIM to compute affines: {t_elapsed:.3g}")


        # Todo make this better
        # for i, layer in enumerate(dm.get_iter(scale)):
        #     layer['alignment_history'][dm.method(z=i)]['method_results']['cafm_hash'] = dm.cafm_current_hash(z=i)

        if 5 in indexes:
            logger.critical(f"\nss hash      : {dm.ssHash(l=5)}\n"
                            f"ss saved hash : {dm.ssSavedHash(l=5)}\n"
                            f"cafm hash    : {dm.cafmHash(l=5)}")
        logger.critical(f"\n\nEND: ALIGN\n")


    def generate(self):
        if 5 in self.regen_indexes:
            logger.critical(f"\nss hash      : {self.dm.ssHash(l=5)}\n"
                            f"ss saved hash : {self.dm.ssSavedHash(l=5)}\n"
                            f"cafm hash    : {self.dm.cafmHash(l=5)}")

        if not self.running():
            logger.warning('Canceling transformation process...')
            self.finished.emit()
            return

        if not self.dm.is_aligned():
            print('\n\n')
            logger.error("Series FAILED to align!")
            print('\n\n')
            self.finished.emit()
            return

        print(f'\n######## Generating Transformed Images ########\n')

        dm = self.dm
        scale = self.scale

        indexes = self.regen_indexes

        logger.critical(f"regen indexes: {self.regen_indexes}")

        scale_val = get_scale_val(scale)

        if not self.running():
            logger.warning('Canceling transformation process...')
            self.finished.emit()
            return

        # tryRemoveDatFiles(dm, scale, dm.data_location)

        # SetStackCafm(dm, scale=scale, poly_order=dm.poly_order)

        #Todo a similar option should be added back in later for forcing regeneration of all output
        # od = os.path.join(dm.series_location, 'tiff', scale)
        # if self._renew_od:
        #     renew_directory(directory=od)
        # print_example_cafms(scale_dict)

        # try:
        #     bias_path = os.path.join(dm.series_location, level, 'bias_data')
        #     save_bias_analysis(layers=dm.get_iter(level=level), bias_path=bias_path)
        # except:
        #     print_exception()

        print_example_cafms(dm)

        if dm.has_bb():
            # Note: now have got new cafm'level -> recalculate bounding box
            rect = dm.set_calculate_bounding_rect(s=scale)  # Only after SetStackCafm
        else:
            w, h = dm.image_size(s=scale)
            rect = [0, 0, w, h]  # might need to swap w/h for Zarr
        logger.info(f'\n'
                    f'Bounding Box       : {dm.has_bb()}\n'
                    f'Polynomial Bias    : {dm.poly_order}\n'
                    f'Aligned Size       : {rect[2]} x {rect[3]}\n'
                    f'Offsets            : {rect[0]}, {rect[1]}')

        dest = dm.data_location
        print(f'\n######## Transforming {len(indexes)} images ########\n')

        tasks = []
        for i, sec in enumerate(dm()):
            if i in indexes:
                ifp = dm.path(s=scale, l=i) # input file path
                ofp = dm.path_aligned(s=scale, l=i)  # output file path
                #Todo add flag to force regenerate
                # if os.path.exists(al_name) or FLAG:
                if not os.path.exists(ofp):
                    os.makedirs(os.path.dirname(ofp), exist_ok=True)
                    cafm = sec['levels'][scale]['cafm']
                    tasks.append([ifp, ofp, rect, cafm, 128])
                else:
                    logger.info(f'Cache hit (transformed image): {ofp}')
                    # if i in [1,2,3]:
                    #     print(f"Example args:\n {[base_name, al_name, rect, cafm, 128]}")


        n_tasks = len(tasks)
        logger.info(f"# of tasks: {n_tasks}")
        if n_tasks == 0:
            logger.info('Nothing new to generate - returning')
            self.finished.emit()
            return

        # pbar = tqdm.tqdm(total=len(tasks), position=0, leave=True, desc="Generating Alignment")

        # def update_pbar(*a):
        #     pbar.update()

        t0 = time.time()
        # ctx = mp.get_context('forkserver')
        # with ctx.Pool(processes=cpus) as pool:
        # with ThreadPool(processes=cpus) as pool:
        #     results = [pool.apply_async(func=run_mir, args=(task,), callback=update_pbar) for task in tasks]
        #     pool.close()
        #     [p.get() for p in results]
        #     pool.join()

        # def run_apply_async_multiprocessing(func, argument_list, num_processes):
        #     pool = mp.Pool(processes=num_processes)
        #     results = [pool.apply_async(func=func, args=(*argument,), callback=update_pbar) if isinstance(argument, tuple) else pool.apply_async(
        #         func=func, args=(argument,), callback=update_pbar) for argument in argument_list]
        #     pool.close()
        #     result_list = [p.get() for p in results]
        #     return result_list
        #
        # run_apply_async_multiprocessing(func=run_mir, argument_list=tasks, num_processes=cpus)
        #
        """Non-blocking"""
        # with ThreadPool(processes=cpus) as pool:
        #     results = [pool.apply_async(func=run_mir, args=(task,), callback=update_pbar) for task in tasks]
        #     pool.close()
        #     [p.get() for p in results]

        """Blocking"""
        ctx = mp.get_context('forkserver')
        #initPbar
        desc = f"Transforming images ({len(tasks)} tasks)"
        self.initPbar.emit((len(tasks), desc))
        # QApplication.processEvents()
        all_results = []
        i = 0
        # cpus = (psutil.cpu_count(logical=False) - 2, 104)[is_tacc()]
        cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks))
        logger.info(f'# Processes: {cpus}')
        with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
            for result in tqdm.tqdm(
                    pool.imap_unordered(run_mir, tasks),
                    total=len(tasks),
                    desc=desc,
                    position=0,
                    leave=True):
                all_results.append(result)
                i += 1
                self.progress.emit(i)
                if not self.running():
                    break

        # with ThreadPoolExecutor(max_workers=cpus) as pool:
        #     # with ProcessPoolExecutor(max_workers=cpus) as pool:
        #     # with ThreadPoolExecutor(max_workers=1) as pool:
        #     #     for i, result in enumerate(tqdm.tqdm(pool.imap_unordered(run, tasks),
        #     #                                          total=len(tasks),
        #     #                                          desc=desc, position=0,
        #     #                                          leave=True)):
        #     for i, result in enumerate(tqdm.tqdm(pool.map(run_mir, tasks),
        #                                          total=len(tasks),
        #                                          desc=desc, position=0,
        #                                          leave=True)):
        #         self.progress.emit(i)
        #         if not self.running():
        #             break


        # with ctx.Pool() as pool:
        #     list(tqdm.tqdm(pool.imap_unordered(run_mir, tasks), total=len(tasks), desc="Generate Alignment", position=0,
        #                    leave=True))
        #     pool.close()


        if not self.running():
            self.finished.emit()
            return

        to_reduce = []
        names = dm.basefilenames()
        for i, name in enumerate([names[i] for i in indexes]):
            ifn = dm.path_aligned(s=scale, l=i)
            ofn = dm.path_thumb(s=scale, l=i)
            if not os.path.exists(ifn):
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), ifn)
                continue
            else:
                if not os.path.exists(ofn):
                    os.makedirs(os.path.dirname(ofn), exist_ok=True)
                    to_reduce.append((ifn, ofn))
                else:
                    logger.info(f'Cache hit (thumbnail): {ofn}')

        if len(to_reduce):
            Thumbnailer().reduce_aligned(dm, indexes, dest=dest, scale=scale)

        print(f'\n######## Generating gifs ########\n')
        t0 = time.time()
        generateAnimations(dm=dm, indexes=indexes, level=scale)
        t1 = time.time()
        dt = t1 - t0
        logger.critical(f"dt (generate gifs): {dt:.3g}s")

        if not self.running():
            self.finished.emit()
            return

        t_elapsed = time.time() - t0
        dm.t_generate = t_elapsed

        # dm.register_cafm_hashes(s=scale, indexes=indexes)
        # dm.set_image_aligned_size() #Todo upgrade

        pbar_text = 'Copy-converting Scale %d Alignment To Zarr (%d Cores)...' % (scale_val, cpus)
        if not self.running():
            logger.warning('Canceling Tasks: %s' % pbar_text)
            self.finished.emit()
            return
        if self._reallocate_zarr:
            tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            preallocate_zarr(dm=dm,
                             name='zarr',
                             group='s%d' % scale_val,
                             shape=(len(dm), rect[3], rect[2]),
                             dtype='|u1',
                             overwrite=True,
                             attr=str(tstamp))



        print(f'\n######## Copy-converting Images to Zarr ########\n')

        #temporary kluge
        if len(indexes) == len(dm):

            zarr_group = os.path.join(dm.data_location, 'zarr', 's%d' % scale_val)
            z = zarr.open(zarr_group)
            # z.attrs['ss_hash'] = [None] * len(dm)
            # z.attrs['cafm_hash'] = [None] * len(dm)

            # sshash_list = [str(dm.ssSavedHash(s=scale, l=i)) for i in range(len(dm))]
            # cafmhash_list = [str(dm.cafmHash(s=scale, l=i)) for i in range(len(dm))]
            # z.attrs.setdefault('ss_hash', sshash_list)
            # z.attrs.setdefault('cafm_hash', cafmhash_list)

            tasks = []
            for i in indexes:
                # ssHash = str(dm.ssHash(s=scale, l=i))
                ssHash = str(dm.ssSavedHash(s=scale, l=i))
                # al_name = dm.path_aligned(s=scale, l=i)
                al_name = dm.path_aligned_saved(s=scale, l=i)
                cafmHash = str(dm.cafmHash(s=scale, l=i))
                # save_to = os.path.join(dm.writeDir(s=scale, l=i), cafmHash)
                save_to = os.path.join(dm.writeDirSaved(s=scale, l=i), cafmHash)
                # z.attrs['index'][i] = {'index': i, 'source': al_name, 'copypath': save_to,
                #                             'ss_hash': ssHash, 'cafm_hash': cafmHash}
                # z.attrs['ss_hash'].update({i: ssHash})
                # z.attrs['cafm_hash'].update({i: cafmHash})
                z.attrs[i] = (ssHash, cafmHash)
                task = [i, al_name, zarr_group, save_to]
                tasks.append(task)
            # shuffle(tasks)

            t0 = time.time()

            if ng.is_server_running():
                logger.info('Stopping Neuroglancer...')
                ng.server.stop()

            # with ctx.Pool(processes=cpus) as pool:
            # with ThreadPool(processes=cpus) as pool:
            #     results = [pool.apply_async(func=convert_zarr, args=(task,), callback=update_pbar) for task in tasks]
            #     pool.close()
            #     [p.get() for p in results]
            #     # pool.join()

            desc = f"Copy-convert to Zarr ({len(tasks)} tasks)"
            # with ThreadPoolExecutor(max_workers=10) as executor:
            #     list(executor.map(convert_zarr,
            #                       tqdm.tqdm(tasks, total=len(tasks), desc=desc, position=0,
            #                                 leave=True)))

            ctx = mp.get_context('forkserver')
            self.initPbar.emit((len(tasks), desc))
            # QApplication.processEvents()
            all_results = []
            # cpus = (psutil.cpu_count(logical=False) - 2, 80)[is_tacc()]
            cpus = min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks))
            logger.info(f"# Processes: {cpus}")
            i = 0
            with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
                for result in tqdm.tqdm(
                        pool.imap_unordered(convert_zarr, tasks),
                        total=len(tasks),
                        desc=desc,
                        position=0,
                        leave=True):
                    all_results.append(result)
                    i += 1
                    self.progress.emit(i)
                    # QApplication.processEvents()
                    if not self.running():
                        break

            t_elapsed = time.time() - t0
            dm.t_convert_zarr = t_elapsed

            logger.info("Zarr conversion complete.")
            logger.info(f"Elapsed Time: {t_elapsed:.3g}s")

            if 5 in self.regen_indexes:
                logger.critical(f"\nss hash      : {dm.ssHash(l=5)}\n"
                                f"ss saved hash : {dm.ssSavedHash(l=5)}\n"
                                f"cafm hash    : {dm.cafmHash(l=5)}")


def run_mir(task):
    in_fn = task[0]
    out_fn = task[1]
    rect = task[2]
    cafm = task[3]
    border = task[4]

    # Todo get exact median greyscale value for each image in list, for now just use 128

    app_path = os.path.dirname(os.path.split(os.path.realpath(__file__))[0])
    mir_c = os.path.join(app_path, 'lib', get_bindir(), 'mir')

    bb_x, bb_y = rect[2], rect[3]
    # afm = np.array(cafm)
    # logger.info(f"cafm: {str(cafm)}")
    afm = np.array([cafm[0][0], cafm[0][1], cafm[0][2], cafm[1][0], cafm[1][1], cafm[1][2]], dtype='float64').reshape((
                                                                                                                      -1,
                                                                                                                      3))
    # logger.info(f'afm: {str(afm.tolist())}')
    p1 = applyAffine(afm, (0, 0))  # Transform Origin To Output Space
    p2 = applyAffine(afm, (rect[0], rect[1]))  # Transform BB Lower Left To Output Space
    offset_x, offset_y = p2 - p1  # Offset Is Difference of 'p2' and 'p1'
    a = cafm[0][0]
    c = cafm[0][1]
    e = cafm[0][2] + offset_x
    b = cafm[1][0]
    d = cafm[1][1]
    f = cafm[1][2] + offset_y

    mir_script = \
        'B %d %d 1\n' \
        'Z %g\n' \
        'F %s\n' \
        'A %g %g %g %g %g %g\n' \
        'RW %s\n' \
        'E' % (bb_x, bb_y, border, in_fn, a, c, e, b, d, f, out_fn)
    o = run_command(mir_c, arg_list=[], cmd_input=mir_script)


def run_command(cmd, arg_list=None, cmd_input=None):
    # logger.info("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    # logger.info(f"\nSTDOUT:\n{cmd_stdout}\n\nSTDERR:\n{cmd_stderr}\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr, 'rc': cmd_proc.returncode})


def generateAnimations(dm, indexes, level):
    # https://stackoverflow.com/questions/753190/programmatically-generate-video-or-animated-gif-in-python

    # src = os.path.join(dm.series_location, 'thumbnails', dm.scale)
    # out = os.path.join(dm.series_location, 'gif', dm.scale)

    # logger.info(f"Generating {len(indexes)} transformation animations... destination:\n{out}")
    # os.makedirs(out, exist_ok=True)
    first_unskipped = dm.first_unskipped(s=level)
    for i in indexes:
        if i == first_unskipped:
            continue
        ofn = dm.path_gif(s=level, l=i)
        os.makedirs(os.path.dirname(ofn), exist_ok=True)
        im0 = dm.path_thumb(l=i)
        im1 = dm.path_thumb_ref(l=i)
        # if refname == '':
        #     im0 = im1
        if not os.path.exists(im0):
            logger.error(f'Not found: {im0}')
            return
        if not os.path.exists(im1):
            logger.error(f'Not found: {im0}')
            return
        try:
            images = [imageio.imread(im0), imageio.imread(im1)]
            imageio.mimsave(ofn, images)
        except:
            print_exception()
        # iio.imwrite(ofn, images, duration=100, loop=-1)


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        result = task_proc.communicate()
        return result
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))




def delete_correlation_signals(dm, scale, indexes):
    logger.info('')
    for i in indexes:
        files = dm.get_signals_filenames(s=scale, l=i)
        # logger.info(f'Deleting:\n{sigs}')
        for f in files:
            if os.path.isfile(f):  # this makes the code more robust
                os.remove(f)
    logger.info('done')


def delete_matches(dm, scale, indexes):
    logger.info('')
    for i in indexes:
        files = dm.get_matches_filenames(s=scale, l=i)
        # logger.info(f'Deleting:\n{sigs}')
        for f in files:
            if os.path.isfile(f):  # this makes the code more robust
                # logger.info(f"Removing {f}...")
                os.remove(f)
    logger.info('done')


def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def checkForTiffs(path) -> bool:
    '''Returns True or False dependent on whether aligned images have been generated for the current level.'''
    files = glob.glob(path + '/*.tif')
    if len(files) < 1:
        logger.debug('Zero aligned TIFs were found at this level - Returning False')
        return False
    else:
        logger.debug('One or more aligned TIFs were found at this level - Returning True')
        return True


def save2file(dm, name):
    data_cp = copy.deepcopy(dm)
    name = data_cp['data_location']
    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp)
    logger.info(f'---- SAVING  ----\n{name}')
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    # logger.info('Save Name: %level' % name)
    with open(name, 'w') as f:
        f.write(proj_json)



# def update_pbar():
#     logger.info('')
#     cfg.mw.pbar.setValue(cfg.mw.pbar.value()+1)

def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        save_to = task[3]
        store = zarr.open(out)
        # store.attr['test_attribute'] = {'key': 'value'}
        data = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        np.save(save_to, data)
        store[ID, :, :] = data
        return 0
    except Exception as e:
        print(e)
        return 1


def count_aligned_files(dest, s):
    path = os.path.join(dest, 'tiff', s)
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    # print(f"# {level} Files: {len(files)}")
    print(f"# complete: {len(files)}", end="\r")
    return len(files)

def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(dm, scale, path):
    # bb_str = str(dm.has_bb())
    bias_data_path = os.path.join(path, scale, 'bias_data')
    # tryRemoveFile(os.path.join(path, level,
    #                            'swim_log_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    # tryRemoveFile(os.path.join(path, level,
    #                            'mir_commands_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    tryRemoveFile(os.path.join(path, scale, 'swim_log.dat'))
    tryRemoveFile(os.path.join(path, scale, 'mir_commands.dat'))
    tryRemoveFile(os.path.join(path, 'fdm_new.txt'))
    tryRemoveFile(os.path.join(bias_data_path, 'snr_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_x_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_y_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_rot_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_scale_x_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_scale_y_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_skew_x_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'bias_det_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'afm_1.dat'))
    tryRemoveFile(os.path.join(bias_data_path, 'c_afm_1.dat'))


def print_example_cafms(dm):
    try:
        print('First Three CAFMs:')
        print(str(dm.cafm(l=0)))
        if len(dm) > 1:
            print(str(dm.cafm(l=1)))
        if len(dm) > 2:
            print(str(dm.cafm(l=2)))
    except:
        pass


class HashableDict(dict):
    def __hash__(self):
        # return hash(tuple(str(sorted(self.items()))))
        return abs(hash(str(sorted(self.items()))))