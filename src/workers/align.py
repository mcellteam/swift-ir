#!/usr/bin/env python3

import sys
import copy
import glob
import json
import logging
import multiprocessing as mp
import os
import re
import subprocess as sp
import time
import statistics
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")  # Works for supressing tiffile invalid offset warning

import imageio.v3 as iio
# import imagecodecs
import numcodecs
import numpy as np
import tqdm
import zarr
numcodecs.blosc.use_threads = False
# import libtiff
# libtiff.libtiff_ctypes.suppress_warnings()

# from src.mp_queue import TaskQueue
from src.utils.readers import read
from src.utils.writers import write
from src.core.recipemaker import run_recipe
from src.utils.helpers import print_exception, get_core_count
import src.config as cfg

from qtpy.QtCore import Signal, QObject, QMutex
from qtpy.QtWidgets import QApplication

__all__ = ['AlignWorker']

logger = logging.getLogger(__name__)

logging.getLogger('tifffile').propagate = False


class AlignWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    # def __init__(self, scale, file_path, align_indexes, regen_indexes, align, regenerate, renew_od, reallocate_zarr, dm, ht):
    def __init__(self, dm, path, scale, indexes, prev_snr, ignore_cache=False):
        super().__init__()
        logger.info('Initializing...')
        self.scale = scale
        self.sl = scale # scale level
        self.path = path
        self.indexes = indexes
        self.prev_snr = prev_snr
        self.ignore_cache = ignore_cache
        # self.regen_indexes = regen_indexes
        self.dm = dm
        self.result = None
        self._running = True
        self._mutex = QMutex()
        self._tasks = []
        self._tasks.append(self.align)


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
        print(f"====> Running Background Thread ====>")
        self.align()
        self.finished.emit()
        print(f"<==== Terminating Background Thread <====")


    def align(self):
        """Long-running task."""
        logger.critical(f'\n\nAligning (ignore cache? {self.ignore_cache})...\n')

        scale = self.scale
        dm = self.dm

        siz = dm.image_size(scale)
        are_large = siz[0] > 16000 or siz[1] > 16000


        _glob_config = {
            'dev_mode': cfg.DEV_MODE,
            'verbose_swim': cfg.VERBOSE_SWIM,
            'log_recipe_to_file': cfg.LOG_RECIPE_TO_FILE,
            'target_thumb_size': cfg.TARGET_THUMBNAIL_SIZE,
            'images_path': dm.images_path,
            'file_path': dm.data_file_path,
            # 'keep_signals': cfg.KEEP_SIGNALS,
            # 'keep_matches': cfg.KEEP_MATCHES,
            # 'generate_thumbnails': cfg.GENERATE_THUMBNAILS,
            'keep_signals': not are_large,
            'keep_matches': not are_large,
            'generate_thumbnails': not are_large,
        }

        firstInd = dm.first_included(s=scale)

        print(self.dm.swim_settings(s=scale, l=5))

        tasks = []
        _actual_indexes = []
        for i, sec in [(i, dm()[i]) for i in self.indexes]:
            i = dm().index(sec)
            ss = copy.deepcopy(dm.swim_settings(s=scale, l=i))
            ss['first_index'] = firstInd == i
            ss['file_path'] = dm.path(s=scale, l=i)
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
            ss['solo'] = len(self.indexes) == 1
            ss['img_size'] = dm.image_size(s=scale)
            ss['is_refinement'] = dm.isRefinement(level=scale)
            ss['glob_cfg'] = _glob_config
            wd = dm.ssDir(s=scale, l=i)  # write directory
            os.makedirs(wd, exist_ok=True)

            if self.ignore_cache:
                _actual_indexes.append(i)
                tasks.append(ss)
            else:
                if ss['include']:
                    result_cached = self.dm.ht.haskey(self.dm.swim_settings(s=scale, l=i))
                    thumbs_exist = Path(ss['path_thumb_transformed']).exists() and Path(ss['path_gif']).exists()
                    must_generate = _glob_config['generate_thumbnails'] and not thumbs_exist
                    if must_generate or not result_cached:
                        _actual_indexes.append(i)
                        tasks.append(ss)
                    else:
                        result = self.dm.ht.get(self.dm.swim_settings(s=scale, l=i))
                        try:
                            dm['stack'][i]['levels'][scale]['results'] = result
                            dm['stack'][i]['levels'][scale].update({'affine_matrix': result['affine_matrix']})
                            dm['stack'][i]['levels'][scale].update({'mir_afm': result['mir_afm']})
                            dm['stack'][i]['levels'][scale].update({'mir_aim': result['mir_aim']})
                            dm['stack'][i]['levels'][scale].update({'snr': result['snr']})
                        except:
                            print_exception()
                            self.hudWarning.emit(f'[{i}] Cached data exists, but certain keys are missing. This '
                                                 f'is non-fatal and the cache will be re-built.')
                            _actual_indexes.append(i)
                            tasks.append(ss)
                            continue
                        logger.info(f"[{i}] Cache hit")

        # _prev_snr = dm.indexes_to_snr_list(_actual_indexes)
        _prev_snr = dm.indexes_to_snr_list(range(len(dm)))


        self.cpus = get_core_count(dm, len(tasks))

        self.hudMessage.emit(f'Computing {len(tasks)} tasks, {self.cpus} CPUs')

        desc = f"Compute Alignment"
        dt, succ, fail, results = self.run_multiprocessing(run_recipe, tasks, desc)
        self.dm.t_align = dt
        if fail:
            self.hudWarning.emit(f"Something went wrong! # Success: {succ} / # Failed: {fail}")

        for r in results:
            if r['complete']:
                layer = int(r['index'])
                try:
                    assert np.array(r['affine_matrix']).shape == (2, 3)
                except:
                    self.hudWarning.emit(f'[{i}] No affine was returned for this layer. This may indicate a failed alignment.')
                    continue
                ss = dm.swim_settings(s=scale, l=layer)
                self.dm.ht.put(ss, r)
                dm['stack'][layer]['levels'][scale].update({'results': r})
                dm['stack'][layer]['levels'][scale].update({'mir_afm': r['mir_afm']})
                dm['stack'][layer]['levels'][scale].update({'mir_aim': r['mir_aim']})
                dm['stack'][layer]['levels'][scale].update({'affine_matrix': r['affine_matrix']})
                dm['stack'][layer]['levels'][scale].update({'snr': r['snr']})
                # self.dict_to_file(i, 'results.json', r)
            else:
                logger.warning(f"Recipe Maker reports incomplete alignment, index={r['index']}")

        if not self.dm['level_data'][scale]['aligned']:
            self.dm['level_data'][scale]['initial_snr'] = self.dm.snr_list()
            self.dm['level_data'][scale]['aligned'] = True

        dm.ht.pickle()

        try:
            dm.set_stack_cafm()
        except:
            print_exception()
        dm.save(silently=True)

        try:
            self.present_snr_results(dt, succ, fail, desc, dm, _actual_indexes, _prev_snr)
        except:
            print_exception()





    def run_multiprocessing(self, func, tasks, desc):
        # Returns 4 objects dt, succ, fail, results
        print(f"----> {desc} ---->")
        _break = 0
        self.initPbar.emit((len(tasks), desc))
        t0 = time.time()
        if sys.platform == 'win32':
            ctx = mp.get_context('spawn')
        else:
            ctx = mp.get_context('forkserver')
        n = len(tasks)
        i, results = 0, []
        # with ctx.Pool(processes=self.cpus, maxtasksperchild=1) as pool:
        with ctx.Pool(processes=self.cpus) as pool:
            for result in tqdm.tqdm(
                    pool.imap_unordered(func, tasks),
                    total=n,
                    desc=desc,
                    position=0,
                    leave=True):
                results.append(result)
                i += 1
                self.progress.emit(i)
                if not self.running():
                    _break = 1
                    print(f"<==== BREAKING ABRUPTLY <====")
                    break
        fail = len(tasks) - len(results)
        succ = len(results) - fail
        dt = time.time() - t0
        # self.print_summary(dt, succ, fail, desc)
        print(f"<---- {desc} <----")
        return (dt, succ, fail, results)


    def dict_to_file(self, i, name, data):
        directory = self.dm.ssDir(s=self.sl, l=i)
        path = os.path.join(directory, name)
        try:
            write('json')(path, data)
        except:
            print_exception()


    def print_summary(self, dt, succ, fail, desc):
        x = 30
        s0 = desc.ljust(x)[0:x]
        s1 = f"{dt:.3g}s".ljust(x)[0:x]
        s2 = str(succ).ljust(x)[0:x]
        s3 = str(fail).ljust(x)[0:x]
        if fail: messagewith = self.hudWarning
        else: messagewith = self.hudMessage
        messagewith.emit(f"\n┌───────────{'─' * x}───┐"
                         f"\n│  Summary    {s0} │"
                         f"\n├───────────┬{'─' * x}──┤"
                         f"\n│  RUNTIME  │ {s1} │"
                         f"\n│  SUCCESS  │ {s2} │"
                         f"\n│  FAILED   │ {s3} │"
                         f"\n└───────────┴{'─' * x}──┘")

    def present_snr_results(self, dt, succ, fail, desc, dm, indexes, _prev_snr):

        x = len(desc)
        # s0 = f"<span style='color: #999999;'><b>{desc}</b></span>".ljust(x)[0:x]
        s0 = f"{desc}".ljust(x)[0:x]
        s1 = f"{dt:.3g}s".rjust(x)[0:x]
        s2 = str(succ).rjust(x)[0:x]
        s3 = str(fail).rjust(x)[0:x]
        if fail:
            messagewith = self.hudWarning
        else:
            messagewith = self.hudMessage

        # indexes = list(range(len(dm)))
        # if dm.first_included() in indexes:
        #     indexes.remove(dm.first_included())

        # logger.info(f"indexes  : {indexes}")


        # logger.critical(f"[{len(snr_before)}] snr_before = {snr_before}")
        # logger.critical(f"[{len(snr_after)}] snr_after  = {snr_after}")

        if len(indexes) > 0:
            prev_snr = [_prev_snr[i] for i in indexes]
            snr_after = [dm.snr(l=i) for i in indexes]
            # logger.info(f"snr  prev: {prev_snr}")
            # logger.info(f"snr after: {snr_after}")
            mean_before = statistics.fmean(prev_snr)
            mean_after = statistics.fmean(snr_after)
            diff_avg = mean_after - mean_before
            delta_list = dm.delta_snr_list(snr_after, prev_snr)
            # delta_snr_list = dm.delta_snr_list(snr_after, prev_snr)
            # logger.info(f"delta_snr_list: {delta_snr_list}")
            # delta_list = [delta_snr_list[i] for i in indexes]
            pos = [i for i, x in enumerate(delta_list) if x > 0]
            neg = [i for i, x in enumerate(delta_list) if x < 0]
            no_chg = [i for i, x in enumerate(delta_list) if x == 0]
            fi = dm.first_included()
            if fi in no_chg:
                no_chg.remove(fi)
            n1 = len(no_chg)
            n2 = len(pos)
            n3 = len(neg)
        else:
            n1, n2, n3 = 0, 0, 0
            diff_avg = 0.

        # i1 = (' '.join(map(str, no_chg))).ljust(4) if n1 < 11 \
        #     else (' '.join(map(str, no_chg[:5])) + ' ... ' + ' '.join(map(str, no_chg[n1 - 5:]))).ljust(x)
        # i2 = (' '.join(map(str, pos))).ljust(4) if n2 < 11 \
        #     else (' '.join(map(str, pos[:5])) + ' ... ' + ' '.join(map(str, pos[n2 - 5:]))).ljust(x)
        # i3 = (' '.join(map(str, neg))).ljust(4) if n3 < 11 \
        #     else (' '.join(map(str, neg[:5])) + ' ... ' + ' '.join(map(str, neg[n3 - 5:]))).ljust(x)

        if abs(diff_avg) < .01:
            _s4 = f"    {(f'{0:4.2f}')}".rjust(x)
            # s4 = f"<span style=''><b>{_s4}</b></span>"
            s4 = _s4
        elif diff_avg < 0:
            _s4 = f'(-) {abs(diff_avg):4.2f}'.rjust(x)
            s4 = f"<span style='color: #f1807e;'><b>{_s4}</b></span>"
        else:
            _s4 = f'(+) {diff_avg:4.2f}'.rjust(x)
            s4 = f"<span style='color: #66FF00;'><b>{_s4}</b></span>"



        # _s5 = f"{f'{n2:4g}'}{('', ' |  i = ')[n2 > 0]}{i2}".ljust(x2)
        _s5 = f"{n2}".rjust(x)
        s5 = f"<span style='color: #66FF00;'><b>{_s5}</b></span>"

        # _s6 = f"{f'{n3:4g}'}{('', ' |  i = ')[n3 > 0]}{i3}".ljust(x2)
        _s6 = f"{n3}".rjust(x)
        s6 = f"<span style='color: #f1807e;'>{_s6}</b></span>"

        # s7 = f"{f'{n1:4g}'}{('', ' |  i = ')[n1 > 0]}{i1}".ljust(x2)
        s7 = f"{n1}".rjust(x)


        lA =                                  f"Δ Avg SNR "
        lB = f"<span style='color: #66FF00;'><b>    SNR ↑ </b></span>"

        lC = f"<span style='color: #f1807e;'><b>    SNR ↓ </b></span>"

        lD =                                  f"No Change "

        # self.hudMessage.emit(f"Alignment Results:\n" + '\n'.join(lines))

        messagewith.emit(f"\n┌─────────────{'─' * x}───┐"
                         f"\n│    Summary   {s0}  │"
                         f"\n├─────────────┬{'─' * x}──┤"
                         f"\n│    RUNTIME  │ {s1} │"
                         f"\n│    SUCCESS  │ {s2} │"
                         f"\n│     FAILED  │ {s3} │"
                         f"\n│  {   lA   } │ {s4} │"
                         f"\n│  {   lD   } │ {s7} │"
                         f"\n│  {   lC   } │ {s6} │"
                         f"\n│  {   lB   } │ {s5} │"
                         f"\n└─────────────┴{'─' * x}──┘")



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
    name = data_cp['file_path']
    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp)
    logger.info(f'---- SAVING  ----\n{name}')
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    # logger.info('Save Name: %level' % name)
    with open(name, 'w') as f:
        f.write(proj_json)


def convert_zarr(task):
    try:
        ID = task[0]
        fn = task[1]
        out = task[2]
        save_to = task[3]
        store = zarr.open(out)
        # store.attr['test_attribute'] = {'key': 'value'}
        # data = libtiff.TIFF.open(fn).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        data = iio.imread(fn)  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        np.save(save_to, data)
        store[ID, :, :] = data
        return 0
    except Exception as e:
        print(e)
        return 1


def tryRemoveFile(directory):
    try:
        os.remove(directory)
    except:
        pass

def tryRemoveDatFiles(path, scale):
    bias_data_path = os.path.join(path, scale, 'bias_data')
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