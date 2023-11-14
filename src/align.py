#!/usr/bin/env python3

import copy
import glob
import json
import logging
import multiprocessing as mp
import os
import re
import subprocess as sp
import sys
import time

import imageio.v3 as iio
# import imagecodecs
import numcodecs
import numpy as np
import tqdm
import zarr

numcodecs.blosc.use_threads = False
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()
import warnings
warnings.filterwarnings("ignore") #Works for supressing tiffile invalid offset warning
from src.mp_queue import TaskQueue
from src.recipe_maker import run_recipe
from src.helpers import print_exception, get_core_count
import src.config as cfg

from qtpy.QtCore import Signal, QObject, QMutex

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
        self.sl = scale # scale level
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
        print(f"<==== Terminating Background Thread <====")
        self.finished.emit()  # Important!


    def align(self):
        """Long-running task."""
        logger.critical(f'\n\nAligning (ignore cache? {self.ignore_cache})...\n')

        scale = self.scale
        dm = self.dm

        _glob_config = {
            'dev_mode': cfg.DEV_MODE,
            'verbose_swim': cfg.VERBOSE_SWIM,
            'log_recipe_to_file': cfg.LOG_RECIPE_TO_FILE,
            'target_thumb_size': cfg.TARGET_THUMBNAIL_SIZE,
            'images_location': dm.images_location,
            'data_location': dm.data_location,
        }

        firstInd = dm.first_included(s=scale)

        tasks = []
        for i, sec in [(i, dm()[i]) for i in self.indexes]:
            i = dm().index(sec)
            for key in ['swim_args', 'swim_out', 'swim_err', 'mir_toks', 'mir_script', 'mir_out', 'mir_err']:
                sec['levels'][scale]['results'].pop(key, None)
            # ss = sec['levels'][scale]['swim_settings']
            ss = copy.deepcopy(dm.swim_settings(s=scale, l=i))
            ss['first_index'] = firstInd == i
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
            ss['solo'] = len(self.indexes) == 1
            ss['img_size'] = dm.image_size(s=scale)
            ss['is_refinement'] = dm.isRefinement(level=scale)

            wd = dm.ssDir(s=scale, l=i)  # write directory
            os.makedirs(wd, exist_ok=True)
            _write_to = os.path.join(wd, 'swim_settings.json')

            if self.ignore_cache:
                tasks.append(copy.deepcopy(ss))
                self.dict_to_file(i, 'swim_settings.json', ss)
            else:
                if ss['include']:
                    if not self.dm.ht.haskey(self.dm.swim_settings(s=scale, l=i)):
                        tasks.append(copy.deepcopy(ss))
                        self.dict_to_file(i, 'swim_settings.json', ss)
                    else:
                        logger.info(f"[{i}] Cache hit!")

        self.cpus = get_core_count(dm, len(tasks))

        [t.update({'glob_cfg': _glob_config}) for t in tasks]

        self.hudMessage.emit(f'Computing {len(tasks)} tasks, {self.cpus} CPUs')

        if cfg.USE_POOL_FOR_SWIM:
            '''Use Multiprocessing Pool - Default'''
            desc = f"Compute Alignment"
            dt, succ, fail, results = self.run_multiprocessing(run_recipe, tasks, desc)
            self.dm.t_align = dt
            if fail:
                self.hudWarning.emit(f'Something went wrong! # Success: {succ} / # Failed: {fail}')
                # self.finished.emit()
                # return
        else:
            '''Use Tom's multiprocessing Queue'''
            task_queue = TaskQueue(n_tasks=len(tasks), dest=dm.data_location)
            task_queue.taskPrefix = 'Computing Alignment for '
            task_queue.taskNameList = [os.path.basename(layer['swim_settings']['path']) for
                                       layer in [dm()[i] for i in self.indexes]]
            task_queue.start(self.cpus)
            align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'recipe_maker.py')
            logger.info('Adding tasks to the queue...')

            for i, sec in [(i, dm()[i]) for i in self.indexes]:
                if sec ['include']:
                # if i != first_included:
                    # encoded_data = json.dumps(copy.deepcopy(sec))
                    encoded_data = json.dumps(sec['levels'][scale])
                    task_args = [sys.executable, align_job, encoded_data]
                    task_queue.add_task(task_args)
            dm.t_align = task_queue.collect_results()
            tq_results = task_queue.task_dict
            results = []
            for tnum in range(len(tq_results)):
                # Get the updated datamodel previewmodel from stdout for the task
                parts = tq_results[tnum]['stdout'].split('---JSON-DELIMITER---')
                for p in parts:
                    ps = p.strip()
                    if ps.startswith('{') and ps.endswith('}'):
                        results.append(json.loads(p))

        logger.critical(f"# results returned: {len(results)}")

        ident = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()
        # fu = dm.first_included()
        # fu_ss = dm.swim_settings(s=scale, l=fu)
        # if self.dm.ht.haskey(fu_ss):
        #     self.dm.ht.remove(fu_ss) #This depends on whether the section is first unskipped or not
        # self.dm.ht.put(fu_ss, ident)

        first_included = dm.first_included(s=scale)
        for r in results:
            if r['complete']:
                i = r['index']

                # if not dm['stack'][i]['levels'][scale]['initialized']:
                #     p = dm.path_aligned(s=scale, l=i)
                #     if os.path.exists(p):
                #         dm['stack'][i]['levels'][scale]['initialized'] = True
                #     else:
                #         self.hudWarning.emit(f"Failed to generate aligned image at index {i}")
                #         # continue #1111- This does not mean the alignment failed necessarily

                afm = r['affine_matrix']
                try:
                    assert np.array(afm).shape == (2, 3)
                except:
                    self.hudWarning.emit(f'Something went wrong for section # {i}')
                    print_exception(extra=f"Section # {i}")
                    continue

                dm['stack'][i]['levels'][scale]['results'] = r
                ss = dm.swim_settings(s=scale, l=i)
                logger.info(f"[{i}] Success! afm: {afm}")
                self.dm.ht.put(ss, afm)
                self.dict_to_file(i, 'results.json', r)

        # SetStackCafm(dm, scale=scale, poly_order=dm.poly_order)
        # dm.set_stack_cafm()

        if not self.dm['level_data'][self.dm.level]['aligned']:
            self.dm['level_data'][self.dm.level]['initial_snr'] = self.dm.snr_list()
            self.dm['level_data'][self.dm.level]['aligned'] = True

        # self.hudMessage.emit(f'<span style="color: #FFFF66;"><b>**** All Processes Complete ****</b></span>')


    def run_multiprocessing(self, func, tasks, desc):
        # Returns 4 objects dt, succ, fail, results
        print(f"----> {desc} ---->")
        _break = 0
        self.initPbar.emit((len(tasks), desc))
        t0 = time.time()
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
        self.print_summary(dt, succ, fail, desc)
        print(f"<---- {desc} <----")
        return (dt, succ, fail, results)


    def dict_to_file(self, i, name, data):
        directory = self.dm.ssDir(s=self.sl, l=i)
        path = os.path.join(directory, name)
        try:
            with open(path, 'w') as f:
                jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                f.write(jde.encode(data))
        except:
            print_exception()


    # def print_summary(self, dt, succ, fail, desc):
    #
    #     if fail:
    #         self.hudWarning.emit(f"\n"
    #                         f"\n//  Summary  //  {desc}  //"
    #                         f"\n//  RUNTIME   : {dt:.3g}s"
    #                         f"\n//  SUCCESS   : {succ}"
    #                         f"\n//  FAILED    : {fail}"
    #                         f"\n")
    #     else:
    #         self.hudMessage.emit(f"\n"
    #                         f"\n//  Summary  //  {desc}  //"
    #                         f"\n//  RUNTIME   : {dt:.3g}s"
    #                         f"\n//  SUCCESS   : {succ}"
    #                         f"\n//  FAILED    : {fail}"
    #                         f"\n")

    def print_summary(self, dt, succ, fail, desc):
        x = 30
        s0 = desc.ljust(x)[0:x]
        s1 = f"{dt:.3g}s".ljust(x)[0:x]
        s2 = str(succ).ljust(x)[0:x]
        s3 = str(fail).ljust(x)[0:x]

        if fail:
            self.hudWarning.emit(f"\n┌───────────{'─' * x}───┐"
                                 f"\n│  Summary    {s0} │"
                                 f"\n├───────────┬{'─' * x}──┤"
                                 f"\n│  RUNTIME  │ {s1} │"
                                 f"\n│  SUCCESS  │ {s2} │"
                                 f"\n│  FAILED   │ {s3} │"
                                 f"\n└───────────┴{'─' * x}──┘")
        else:
            self.hudMessage.emit(f"\n┌───────────{'─' * x}───┐"
                                 f"\n│  Summary    {s0} │"
                                 f"\n├───────────┬{'─' * x}──┤"
                                 f"\n│  RUNTIME  │ {s1} │"
                                 f"\n│  SUCCESS  │ {s2} │"
                                 f"\n│  FAILED   │ {s3} │"
                                 f"\n└───────────┴{'─' * x}──┘")


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