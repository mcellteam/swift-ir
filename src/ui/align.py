#!/usr/bin/env python3

import os
import re
import sys
import copy
import json
import glob
import time
import shutil
import psutil
import logging
from pathlib import Path
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
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
from src.helpers import print_exception, pretty_elapsed, is_tacc, get_n_tacc_cores
from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_val, renew_directory, file_hash, pretty_elapsed, is_tacc
from src.funcs_zarr import preallocate_zarr
from src.job_apply_affine import run_mir
import src.config as cfg

from qtpy.QtCore import Signal, QObject, QMutex
from qtpy.QtWidgets import QApplication

__all__ = ['AlignWorker']

logger = logging.getLogger(__name__)


class AlignWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    def __init__(self, scale, path, align_indexes, regen_indexes, align, regenerate, renew_od, reallocate_zarr, dm):
        super().__init__()
        logger.info('')
        self.scale = scale
        self.path = path
        self.align_indexes = align_indexes
        self.regen_indexes = regen_indexes
        self._align = align #Temporary
        self._generate = regenerate
        self._renew_od = renew_od
        self._reallocate_zarr = reallocate_zarr
        self.dm = dm
        self.result = None
        self._mutex = QMutex()
        self._running = True

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
        logger.info('')
        while self._tasks and self.running():
            self._tasks.pop(0)()
        self.finished.emit() #Important!


    def align(self):
        """Long-running task."""

        scale = self.scale
        indexes = self.align_indexes
        dm = self.dm

        if scale == dm.coarsest_scale_key():
            print(f'\n\nInitializing Alignment for {indexes}\n')
        else:
            print(f'\n\nRefining Alignment for {indexes}\n')

        # cfg.mw._autosave()

        scratchpath = os.path.join(dm.dest(), 'logs', 'scratch.log')
        if os.path.exists(scratchpath):
            os.remove(scratchpath)

        # checkForTiffs(path)

        first_unskipped = dm.first_unskipped(s=scale)

        scale_val = dm.scale_val(scale)
        tasks = []
        for zpos, sec in [(i, dm()[i]) for i in indexes]:
            # zpos = sec['alignment']['meta']['index']
            # if not sec['skipped'] and (zpos != first_unskipped):
            zpos = dm().index(sec)
            sec['levels'][scale].setdefault('method_results', {})
            sec['levels'][scale]['method_previous'] = copy.deepcopy(sec['levels'][scale]['swim_settings']['method'])
            for key in ['swim_args', 'swim_out', 'swim_err', 'mir_toks', 'mir_script', 'mir_out', 'mir_err']:
                sec['levels'][scale]['method_results'].pop(key, None)
            ss = sec['levels'][scale]['swim_settings']
            mr = sec['levels'][scale]['method_results']
            ss['index'] = zpos
            # ss['scale_val'] = scale_val
            ss['scale_key'] = scale
            ss['isRefinement'] = dm.isRefinement()
            ss['location'] = dm.location
            ss['defaults'] = dm['defaults']
            ss['img_size'] = dm.series['levels'][scale]['size_xy']
            # ss['include'] = not sec['skipped']
            ss['dev_mode'] = cfg.DEV_MODE
            ss['log_recipe_to_file'] = cfg.LOG_RECIPE_TO_FILE
            ss['target_thumb_size'] = cfg.TARGET_THUMBNAIL_SIZE
            ss['verbose_swim'] = cfg.VERBOSE_SWIM
            # ss['filename'] = ss['filename']
            # ss['fn_reference'] = ss['reference']
            if ss['method'] == 'grid-default':
                ss['whiten'] = dm['defaults']['signal-whitening']
                ss['swim_iters'] = dm['defaults']['swim-iterations']
            else:
                ss['whiten'] = ss['signal-whitening']
                ss['swim_iters'] = ss['iterations']
            if dm.isRefinement():
                scale_prev = dm.scales[dm.scales.index(scale) + 1]
                prev_scale_val = int(scale_prev[len('scale_'):])
                upscale = (float(prev_scale_val) / float(scale_val))
                prev_method = dm['stack'][zpos]['levels'][scale_prev]['swim_settings']['method']
                init_afm = np.array(copy.deepcopy(dm['stack'][zpos]['levels'][scale_prev]['alignment_history'][
                                                      prev_method]['method_results']['affine_matrix']))
                # prev_method = scale_prev_dict[zpos]['current_method']
                # prev_afm = copy.deepcopy(np.array(scale_prev_dict[zpos]['alignment_history'][prev_method]['affine_matrix']))
                init_afm[0][2] *= upscale
                init_afm[1][2] *= upscale
                ss['init_afm'] = init_afm.tolist()
            else:
                ss['init_afm'] = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()

            if ss['include'] and (zpos != first_unskipped):
                # tasks.append(copy.deepcopy(sec['alignment']))
                tasks.append(copy.deepcopy({'swim_settings': ss, 'method_results': mr}))
            else:
                logger.critical(f"EXCLUDING section #{zpos}")

        delete_correlation_signals(dm=dm, scale=scale, indexes=indexes)
        delete_matches(dm=dm, scale=scale, indexes=indexes)
        dest = dm.location

        if is_tacc():
            cpus = get_n_tacc_cores(n_tasks=len(tasks))
            if is_tacc() and (scale == 's1'):
                # cpus = 34
                cpus = cfg.SCALE_1_CORES_LIMIT
        else:
            cpus = psutil.cpu_count(logical=False) - 2

        t0 = time.time()

        logger.info(f"# cores: {cpus}")

        # f_recipe_maker = f'{os.path.split(os.path.realpath(__file__))[0]}/src/recipe_maker.py'

        if cfg.USE_POOL_FOR_SWIM:
            ctx = mp.get_context('forkserver')
            # with ctx.Pool(processes=cpus) as pool:
            #     all_results = list(
            #         tqdm.tqdm(pool.imap(run_recipe, tasks, chunksize=5),
            #                   total=len(tasks), desc="Compute Affines",
            #                   position=0, leave=True))

            #initPbar
            desc = f"Computing Affines ({len(tasks)} tasks)"
            self.initPbar.emit((len(tasks), desc))
            QApplication.processEvents()
            all_results = []
            with ctx.Pool(processes=cpus) as pool:
                for i, result in enumerate(tqdm.tqdm(pool.imap_unordered(run_recipe, tasks),
                                        total=len(tasks), desc=desc, position=0, leave=True)):
                    all_results.append(result)
                    self.progress.emit(i)
                    QApplication.processEvents()
                    # logger.info(f'running? {self.running()}')
                    if not self.running():
                        break

            logger.critical(f"# Completed Alignment Tasks: {len(all_results)}")

            # # # For use with ThreadPool ONLY
            # for r in all_results:
            #     index = r['swim_settings']['index']
            #     method = r['swim_settings']['method']
            #     sec = dm['data']['scales'][scale]['stack'][index]
            #     sec['alignment'] = r
            #     sec['alignment_history'][method]['method_results'] = copy.deepcopy(r['method_results'])
            #     sec['alignment_history'][method]['swim_settings'] = copy.deepcopy(r['swim_settings'])
            #     sec['alignment_history'][method]['complete'] = True
            #     try:
            #         assert np.array(sec['alignment_history'][method]['method_results']['affine_matrix']).shape == (2, 3)
            #         # dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['complete'] = True
            #     except:
            #         logger.warning(f"Task failed at index: {index}")
        else:

            task_queue = TaskQueue(n_tasks=len(tasks), dest=dest)
            task_queue.taskPrefix = 'Computing Alignment for '
            task_queue.taskNameList = [os.path.basename(layer['swim_settings']['filename']) for
                                       layer in [dm()[i] for i in indexes]]
            task_queue.start(cpus)
            align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'recipe_maker.py')
            logger.info('adding tasks to the queue...')
            for zpos, sec in [(i, dm()[i]) for i in indexes]:
                if sec['swim_settings']['include'] and (zpos != first_unskipped):
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
                # logger.critical(f"------------------------------------------------------")
                # Get the updated datamodel previewmodel from stdout for the task
                parts = tq_results[tnum]['stdout'].split('---JSON-DELIMITER---')
                dm_text = None
                for p in parts:
                    # logger.critical(f"\n\n\np = {p}\n\n")
                    ps = p.strip()
                    if ps.startswith('{') and ps.endswith('}'):
                        all_results.append(json.loads(p))


        for r in all_results:
            index = r['swim_settings']['index']
            method = r['swim_settings']['method']
            sec = dm['stack'][index]['levels'][scale]
            sec['method_results'] = r['method_results']
            sec['alignment_history'][method]['method_results'] = copy.deepcopy(r['method_results'])
            sec['alignment_history'][method]['swim_settings'] = copy.deepcopy(r['swim_settings'])
            sec['alignment_history'][method]['complete'] = True
            try:
                assert np.array(sec['alignment_history'][method]['method_results']['affine_matrix']).shape == (2, 3)
                # dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['complete'] = True
            except:
                logger.warning(f"Task failed at index: {index}")


        SetStackCafm(cfg.data, scale=scale, poly_order=dm.default_poly_order)

        #Todo
        # try:
        #     shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale_key, 'matches_raw'), ignore_errors=True)
        #     shutil.rmtree(os.path.join(cfg.data.dest(), cfg.data.scale_key, 'matches_raw'), ignore_errors=True)
        # except:
        #     print_exception()

        if not self.running():
            return

        t_elapsed = time.time() - t0
        dm.t_align = t_elapsed
        logger.info(f"Elapsed Time, SWIM to compute affines: {t_elapsed:.3g}")


        # Todo make this better
        # for i, layer in enumerate(dm.get_iter(scale)):
        #     layer['alignment_history'][dm.method(l=i)]['method_results']['cafm_hash'] = dm.cafm_current_hash(l=i)

        # if cfg.mw._isProjectTab():
        #     cfg.mw.updateCorrSignalsDrawer()
        #     cfg.mw.setTargKargPixmaps()

        save2file(dm=dm._data, name=dm.dest())

        # initPbar
        # thumbnailer = Thumbnailer()
        # thumbnailer.reduce_matches(indexes=indexes, dest=dm['data']['series_path'], scale=scale)



    def generate(self):
        logger.info('\n\nGenerating Aligned Images...\n')

        dm = self.dm
        scale = self.scale
        indexes = self.regen_indexes

        scale_val = get_scale_val(scale)

        if not self.running():
            logger.warning('Canceling Generate Alignment')
            return

        tryRemoveDatFiles(dm, scale, dm.dest())

        SetStackCafm(cfg.data, scale=scale, poly_order=dm.default_poly_order)

        dm.propagate_swim_1x1_custom_px(indexes=indexes)
        dm.propagate_swim_2x2_custom_px(indexes=indexes)
        dm.propagate_manual_swim_window_px(indexes=indexes)

        od = os.path.join(dm.dest(), 'tiff', scale)
        if self._renew_od:
            renew_directory(directory=od)
        # print_example_cafms(scale_dict)

        # try:
        #     bias_path = os.path.join(dm.dest(), scale_key, 'bias_data')
        #     save_bias_analysis(layers=dm.get_iter(s=scale_key), bias_path=bias_path)
        # except:
        #     print_exception()

        print_example_cafms(dm)

        if dm.has_bb():
            # Note: now have got new cafm's -> recalculate bounding box
            rect = dm.set_calculate_bounding_rect(s=scale)  # Only after SetStackCafm
            logger.info(f'Bounding Box           : ON\nNew Bounding Box  : {str(rect)}')
            logger.info(f'Corrective Polynomial  : {dm.default_poly_order} (Polynomial Order: {dm.default_poly_order})')
        else:
            logger.info(f'Bounding Box           : OFF')
            logger.info(f'Corrective Polynomial  : {str(dm.default_poly_order)}')
            w, h = dm.image_size(s=scale)
            rect = [0, 0, w, h]  # might need to swap w/h for Zarr
        logger.info(f'Aligned Size      : {rect[2:]}')
        logger.info(f'Offsets           : {rect[0]}, {rect[1]}')
        if is_tacc():
            cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(indexes)), 1)
        else:
            cpus = psutil.cpu_count(logical=False)

        dest = dm.location
        logger.info(f'\n\nGenerating Aligned Images for {indexes}\n')

        tasks = []
        for i, sec in enumerate(dm()):
            if i in indexes:
                base_name = sec['levels'][scale]['swim_settings']['filename']
                _, fn = os.path.split(base_name)
                al_name = os.path.join(dest, 'tiff', scale, fn)
                method = sec['levels'][scale]['swim_settings']['method']  # 0802+
                cafm = sec['levels'][scale]['alignment_history'][method]['method_results']['cumulative_afm']
                tasks.append([base_name, al_name, rect, cafm, 128])
                if i in [1,2,3]:
                    print(f"Example args:\n {[base_name, al_name, rect, cafm, 128]}")
                if cfg.DEV_MODE:
                    sec['levels'][scale]['method_results']['generate_args'] = [base_name, al_name, rect, cafm, 128]

        logger.info(f"# of tasks: {len(tasks)}")

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
        desc = f"Generating Alignment ({len(tasks)} tasks)"
        self.initPbar.emit((len(tasks), desc))
        QApplication.processEvents()
        all_results = []
        i = 0
        cpus = (psutil.cpu_count(logical=False) - 2, 104)[is_tacc()]
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
                QApplication.processEvents()
                if not self.running():
                    break


        # with ctx.Pool() as pool:
        #     list(tqdm.tqdm(pool.imap_unordered(run_mir, tasks), total=len(tasks), desc="Generate Alignment", position=0,
        #                    leave=True))
        #     pool.close()

        logger.info("Generate Alignment Finished")


        nFilesFound = len(os.listdir(os.path.join(dest, 'tiff', scale)))
        logger.critical(f"# Files Found: {nFilesFound}")
        if nFilesFound == 0:
            logger.warning(f"No Files Found. Nothing to convert.")
            return

        if not self.running():
            return

        #initPbar
        thumbnailer = Thumbnailer()
        thumbnailer.reduce_aligned(indexes, dest=dest, scale=scale)

        if not self.running():
            return

        t_elapsed = time.time() - t0
        dm.t_generate = t_elapsed

        dm.register_cafm_hashes(s=scale, indexes=indexes)
        # dm.set_image_aligned_size() #Todo upgrade

        pbar_text = 'Copy-converting Scale %d Alignment To Zarr (%d Cores)...' % (scale_val, cpus)
        if not self.running():
            logger.warning('Canceling Tasks: %s' % pbar_text)
            return
        if self._reallocate_zarr:
            preallocate_zarr(dm=dm,
                             name='zarr',
                             group='s%d' % scale_val,
                             shape=(len(dm), rect[3], rect[2]),
                             dtype='|u1',
                             overwrite=True)

        print(f'\n\nCopy-convert Alignment To Zarr for {indexes}\n')

        tasks = []
        for i in indexes:
            _, fn = os.path.split(dm()[i]['levels'][scale]['swim_settings']['filename'])
            al_name = os.path.join(dm.dest(), 'tiff', scale, fn)
            zarr_group = os.path.join(dm.dest(), 'zarr', 's%d' % scale_val)
            task = [i, al_name, zarr_group]
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

        desc = f"Convert Alignment to Zarr ({len(tasks)} tasks)"
        # with ThreadPoolExecutor(max_workers=10) as executor:
        #     list(executor.map(convert_zarr,
        #                       tqdm.tqdm(tasks, total=len(tasks), desc=desc, position=0,
        #                                 leave=True)))

        ctx = mp.get_context('forkserver')
        self.initPbar.emit((len(tasks), desc))
        QApplication.processEvents()
        all_results = []
        i = 0
        cpus = (psutil.cpu_count(logical=False) - 2, 104)[is_tacc()]
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
                QApplication.processEvents()
                if not self.running():
                    break


        logger.info("Convert Alignment to Zarr Finished")

        t_elapsed = time.time() - t0
        dm.t_convert_zarr = t_elapsed



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


def delete_matches(dm, scale, indexes):
    logger.info('')
    for i in indexes:
        files = dm.get_matches_filenames(s=scale, l=i)
        # logger.info(f'Deleting:\n{sigs}')
        for f in files:
            if os.path.isfile(f):  # this makes the code more robust
                # logger.info(f"Removing {f}...")
                os.remove(f)


def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def checkForTiffs(path) -> bool:
    '''Returns True or False dependent on whether aligned images have been generated for the current s.'''
    files = glob.glob(path + '/*.tif')
    if len(files) < 1:
        logger.debug('Zero aligned TIFs were found at this s - Returning False')
        return False
    else:
        logger.debug('One or more aligned TIFs were found at this s - Returning True')
        return True


def save2file(dm, name):
    data_cp = copy.deepcopy(dm)
    name = data_cp['location']
    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp)
    logger.info(f'---- SAVING  ----\n{name}')
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    # logger.info('Save Name: %s' % name)
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
        store = zarr.open(out)
        store[ID, :, :] = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        return 0
    except Exception as e:
        print(e)
        return 1


def count_aligned_files(dest, s):
    path = os.path.join(dest, 'tiff', s)
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    # print(f"# {s} Files: {len(files)}")
    print(f"# complete: {len(files)}", end="\r")
    return len(files)

def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(dm, scale, path):
    # bb_str = str(dm.has_bb())
    # poly_order_str = str(cfg.data.default_poly_order)
    bias_data_path = os.path.join(path, scale, 'bias_data')
    # tryRemoveFile(os.path.join(path, scale_key,
    #                            'swim_log_' + bb_str + '_' + null_cafm_str + '_' + poly_order_str + '.dat'))
    # tryRemoveFile(os.path.join(path, scale_key,
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