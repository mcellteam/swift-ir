#!/usr/bin/env python3

import os
import re
import sys
import copy
import json
import glob
import time
import psutil
import logging
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime
import multiprocessing as mp
import subprocess as sp
import numpy as np
import tqdm
import zarr
# import imagecodecs
import numcodecs
numcodecs.blosc.use_threads = False
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()
import warnings
warnings.filterwarnings("ignore") #Works for supressing tiffile invalid offset warning
from src.mp_queue import TaskQueue
from src.recipe_maker import run_recipe
from src.helpers import print_exception, pretty_elapsed, is_tacc, get_bindir, get_n_tacc_cores
# from src.save_bias_analysis import save_bias_analysis
from src.helpers import get_scale_val, renew_directory, file_hash, pretty_elapsed, is_tacc
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

logging.getLogger('tifffile').propagate = False


class AlignWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    # def __init__(self, scale, path, align_indexes, regen_indexes, align, regenerate, renew_od, reallocate_zarr, dm, ht):
    def __init__(self, dm, path, scale, indexes, ignore_cache=False):
        super().__init__()
        logger.info('Initializing...')
        self.scale = scale
        self.path = path
        self.indexes = indexes
        self.ignore_cache = ignore_cache
        # self.regen_indexes = regen_indexes
        self.dm = dm
        self.result = None
        self._running = True
        self._mutex = QMutex()
        self.finished.connect(lambda: logger.critical('Finished!'))

        self._tasks = []
        self._tasks.append(self.align)
        # if self._align:
        #     self._tasks.append(self.align)
        # if self._generate:
        #     self._tasks.append(self.generate)


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
        self.finished.emit()


    def run(self):
        logger.critical('Running...')
        while self._tasks and self.running():
            self._tasks.pop(0)()
        logger.info(f"\n\n<---- End of Alignment <----\n")
        self.finished.emit() #Important!


    def align(self):
        """Long-running task."""
        logger.critical(f'\n\nAligning (ignore cache? {self.ignore_cache})...\n')

        scale = self.scale
        indexes = self.indexes
        dm = self.dm

        if 5 in indexes:
            logger.info(f"hash ss: {dm.ssHash(l=5)} // ss saved: {dm.ssSavedHash(l=5)} // cafm: {dm.cafmHash(l=5)}")

        scratchpath = os.path.join(dm.images_location, 'logs', 'scratch.log')
        if os.path.exists(scratchpath):
            os.remove(scratchpath)

        # checkForTiffs(path)

        first_unskipped = dm.first_unskipped(s=scale)

        tasks = []
        for i, sec in [(i, dm()[i]) for i in indexes]:
            i = dm().index(sec)
            for key in ['swim_args', 'swim_out', 'swim_err', 'mir_toks', 'mir_script', 'mir_out', 'mir_err']:
                sec['levels'][scale]['results'].pop(key, None)
            # ss = sec['levels'][scale]['swim_settings']
            ss = copy.deepcopy(dm.swim_settings(s=scale, l=i))
            ss['path'] = dm.path(s=scale, l=i)
            ss['path_reference'] = dm.path_ref(s=scale, l=i)
            ss['dir_signals'] = dm.dir_signals(s=scale, l=i)
            ss['dir_matches'] = dm.dir_matches(s=scale, l=i)
            ss['dir_tmp'] = dm.dir_tmp(s=scale, l=i)
            ss['thumbnail_scale_factor'] = dm.images['thumbnail_scale_factor']
            ss['path_thumb_src'] = dm.path_thumb_src(s=scale, l=i)
            ss['path_thumb_transformed'] = dm.path_thumb(s=scale, l=i)
            ss['path_thumb_src_ref'] = dm.path_thumb_src_ref(s=scale, l=i)
            ss['path_gif'] = dm.path_gif(s=scale, l=i)
            ss['wd'] = dm.writeDir(s=scale, l=i)
            ss['solo'] = len(indexes) == 1
            # print(f"path : {ss['path']}")
            # print(f" ref : {ss['path_reference']}")

            wd = dm.ssDir(s=scale, l=i)  # write directory
            os.makedirs(wd, exist_ok=True)

            if self.ignore_cache:
                wp = os.path.join(wd, 'swim_settings.json')  # write path
                with open(wp, 'w') as f:
                    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                    f.write(jde.encode(dm.swim_settings(s=scale, l=i)))
                tasks.append(copy.deepcopy(ss))
            else:
                if ss['include']:
                    if not self.dm.ht.haskey(self.dm.swim_settings(s=scale, l=i)):
                        wp = os.path.join(wd, 'swim_settings.json')  # write path
                        with open(wp, 'w') as f:
                            jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                            f.write(jde.encode(dm.swim_settings(s=scale, l=i)))
                        tasks.append(copy.deepcopy(ss))
                    else:
                        logger.info(f"[{i}] Cache hit!")
        self.hudMessage.emit(f'Batch multiprocessing {len(tasks)} alignment jobs...')

        # delete_correlation_signals(dm=dm, scale=scale, indexes=indexes)
        # delete_matches(dm=dm, scale=scale, indexes=indexes)

        dest = dm.data_location

        if is_tacc():
            cpus = get_n_tacc_cores(n_tasks=len(tasks))
            if is_tacc() and (scale == 's1'):
                # cpus = 34
                cpus = min(cfg.SCALE_1_CORES_LIMIT, cpus)
        else:
            cpus = psutil.cpu_count(logical=False) - 2

        t0 = time.time()

        # f_recipe_maker = f'{os.path.split(os.path.realpath(__file__))[0]}/src/recipe_maker.py'

        if cfg.USE_POOL_FOR_SWIM:
            # ctx = mp.get_context('forkserver')
            ctx = mp.get_context('spawn')
            desc = f"Aligning ({len(tasks)} tasks)"
            self.initPbar.emit((len(tasks), desc))

            cfg.CONFIG = {
                'dev_mode': cfg.DEV_MODE,
                'verbose_swim': cfg.VERBOSE_SWIM,
                'log_recipe_to_file': cfg.LOG_RECIPE_TO_FILE,
                'target_thumb_size': cfg.TARGET_THUMBNAIL_SIZE,
                'images_location':dm.images_location,
                'data_location': dm.data_location,
            }

            for i in range(len(tasks)):
                tasks[i]['config'] = cfg.CONFIG

            logger.info(f'max # workers: {cpus}')

            # with ThreadPoolExecutor(max_workers=cpus) as pool:
            #     for i, result in enumerate(tqdm.tqdm(pool.map(run_recipe, tasks),
            #                                          total=len(tasks),
            #                                          desc=desc, position=0,
            #                                          leave=True)):
            #         all_results.append(result)
            #         self.progress.emit(i)
            #         if not self.running():
            #             break

            all_results = []
            i = 0
            # with ctx.Pool(processes=cpus, maxtasksperchild=1) as pool:
            with ctx.Pool(processes=cpus) as pool:
                for result in tqdm.tqdm(
                        pool.imap_unordered(run_recipe, tasks),
                        total=len(tasks),
                        desc=desc,
                        position=0,
                        leave=True):
                    all_results.append(result)
                    i += 1
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
            for i, sec in [(i, dm()[i]) for i in indexes]:
                if sec['include'] and (i != first_unskipped):
                # if i != first_unskipped:
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
        if self.dm.ht.haskey(fu_ss):
            self.dm.ht.remove(fu_ss) #This depends on whether the section is first unskipped or not
        self.dm.ht.put(fu_ss, ident)

        for i,r in enumerate(all_results):
            index = r['index']
            initialized = dm['stack'][index]['levels'][scale]['initialized']
            if not initialized:
                p = dm.path_aligned(s=scale, l=index)
                if os.path.exists(p):
                    dm['stack'][index]['levels'][scale]['initialized'] = True
                else:
                    logger.warning(f"Failed to generate [{index}] '{p}'")
                    try:
                        logger.warning(f"  afm: {r['affine_matrix']}")
                    except:
                        logger.warning("No Affine")
                    continue
            if r['complete']:
                afm = r['affine_matrix']
                # afm = r['_affine_matrix']
                try:
                    assert np.array(afm).shape == (2, 3)
                    # assert np.array(r['affine_matrix']).all() != np.array([[1., 0., 0.], [0., 1., 0.]]).all()
                except:
                    print_exception(extra=f"Alignment failed at index {index}")
                    continue

                dm['stack'][index]['levels'][scale]['results'] = r

                ss = dm.swim_settings(s=scale, l=index)
                # key = HashableDict(ss)
                # index = r['index']
                # key = dm.swim_settings(s=scale, l=index)
                # value = r
                # value = r['affine_matrix']
                print(f"afm {index}: {afm}")
                if afm != ident:
                    # self.ht.put(key, value)
                    self.dm.ht.put(ss, afm)
                wd = dm.ssDir(s=scale, l=index)  # write directory
                wp = os.path.join(wd, 'results.json')  # write path
                os.makedirs(wd, exist_ok=True)
                with open(wp, 'w') as f:
                    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                    f.write(jde.encode(r))

        # SetStackCafm(dm, scale=scale, poly_order=dm.poly_order)
        # dm.set_stack_cafm()
        t_elapsed = time.time() - t0
        dm.t_align = t_elapsed
        logger.info(f"Elapsed Time, SWIM to compute affines: {t_elapsed:.3g}")
        self.hudMessage.emit(f'<span style="color: #FFFF66;"><b>**** Alignment Complete ****</b></span>')
        self.finished.emit()


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