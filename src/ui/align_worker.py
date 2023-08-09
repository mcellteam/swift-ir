

#!/usr/bin/env python3

import os
import re
import sys
import copy
import json
import glob
import platform
from glob import glob
import time
import psutil
import logging
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import concurrent
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
import subprocess as sp
import numpy as np
import tqdm
# sys.path.insert(1, os.path.dirname(os.path.split(os.path.realpath(__file__))[0]))
# sys.path.insert(1, os.path.split(os.path.realpath(__file__))[0])
from src.data_model import DataModel
from src.funcs_image import SetStackCafm
from src.generate_aligned import GenerateAligned
from src.thumbnailer import Thumbnailer
from src.mp_queue import TaskQueue
from src.data_model import DataModel
import src.config as cfg
from src.ui.timer import Timer
from src.recipe_maker import run_recipe
from src.helpers import print_exception, pretty_elapsed, is_tacc, get_n_tacc_cores

from qtpy.QtCore import Signal, QObject

__all__ = ['AlignWorker']

logger = logging.getLogger(__name__)


class AlignWorker(QObject):
    alignmentFinished = Signal()
    progress = Signal(int)
    initPbar = Signal(int)

    def __init__(self, scale, path, indexes, swim_only, renew_od, reallocate_zarr, dm):
        self.scale = scale
        self.path = path
        self.indexes = indexes
        self.swim_only = swim_only
        self.renew_od = renew_od
        self.reallocate_zarr = reallocate_zarr
        self.dm = dm
        self.result = None

        super().__init__()

    def run(self):
        """Long-running task."""


        scale = self.scale
        path = self.path
        indexes = self.indexes
        swim_only = self.swim_only
        renew_od = self.renew_od
        reallocate_zarr = self.reallocate_zarr
        dm = self.dm

        if scale == dm.coarsest_scale_key():
            print(f'\n\nInitializing Alignment for {indexes}\n')
        else:
            print(f'\n\nRefining Alignment for {indexes}\n')

        # cfg.mw._autosave()

        # use_gui = 1
        # if not use_gui:
        #     with open(path, 'r') as f:
        #         try:
        #             data = json.load(f)
        #         except Exception as e:
        #             logger.warning(e)
        #             return
        #     dm = DataModel(data)
        #     dm.set_defaults()

        scratchpath = os.path.join(dm.dest(), 'logs', 'scratch.log')
        if os.path.exists(scratchpath):
            os.remove(scratchpath)

        # checkForTiffs(path)

        signals_dir = os.path.join(dm.dest(), scale, 'signals')
        if not os.path.exists(signals_dir):
            os.mkdir(signals_dir)

        matches_dir = os.path.join(dm.dest(), scale, 'matches_raw')
        if not os.path.exists(matches_dir):
            os.mkdir(matches_dir)

        first_unskipped = dm.first_unskipped(s=scale)

        scale_val = dm.scale_val(scale)
        tasks = []
        for zpos, sec in [(i, dm()[i]) for i in indexes]:
            # zpos = sec['alignment']['meta']['index']
            # if not sec['skipped'] and (zpos != first_unskipped):
            zpos = dm().index(sec)
            sec['alignment'].setdefault('method_results', {})
            sec['alignment']['method_previous'] = copy.deepcopy(sec['alignment']['swim_settings']['method'])
            for key in ['swim_args', 'swim_out', 'swim_err', 'mir_toks', 'mir_script', 'mir_out', 'mir_err']:
                sec['alignment']['method_results'].pop(key, None)
            ss = sec['alignment']['swim_settings']
            ss['index'] = zpos
            # ss['scale_val'] = scale_val
            ss['scale_key'] = scale
            ss['isRefinement'] = dm['data']['scales'][scale]['isRefinement']
            ss['destination_path'] = dm['data']['destination_path']
            ss['defaults'] = dm['data']['defaults']
            ss['img_size'] = dm['data']['scales'][scale]['image_src_size']
            # ss['include'] = not sec['skipped']
            ss['dev_mode'] = cfg.DEV_MODE
            ss['log_recipe_to_file'] = cfg.LOG_RECIPE_TO_FILE
            ss['verbose_swim'] = cfg.VERBOSE_SWIM
            ss['fn_transforming'] = sec['filename']
            ss['fn_reference'] = sec['reference']
            if ss['method'] == 'grid-default':
                ss['whiten'] = dm['data']['defaults']['signal-whitening']
                ss['swim_iters'] = dm['data']['defaults']['swim-iterations']
            else:
                ss['whiten'] = ss['signal-whitening']
                ss['swim_iters'] = ss['iterations']
            if dm['data']['scales'][scale]['isRefinement']:
                scale_prev = dm.scales()[dm.scales().index(scale) + 1]
                prev_scale_val = int(scale_prev[len('scale_'):])
                upscale = (float(prev_scale_val) / float(scale_val))
                prev_method = dm['data']['scales'][scale_prev]['stack'][zpos]['alignment']['swim_settings']['method']
                init_afm = np.array(copy.deepcopy(dm['data']['scales'][scale_prev]['stack'][zpos][
                                                      'alignment_history'][prev_method]['method_results'][
                                                      'affine_matrix']))
                # prev_method = scale_prev_dict[zpos]['current_method']
                # prev_afm = copy.deepcopy(np.array(scale_prev_dict[zpos]['alignment_history'][prev_method]['affine_matrix']))
                init_afm[0][2] *= upscale
                init_afm[1][2] *= upscale
                ss['init_afm'] = init_afm.tolist()
            else:
                ss['init_afm'] = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()

            if ss['include'] and (zpos != first_unskipped):
                tasks.append(copy.deepcopy(sec['alignment']))
            else:
                logger.critical(f"EXCLUDING section #{zpos}")

        delete_correlation_signals(dm=dm, scale=scale, indexes=indexes)
        delete_matches(dm=dm, scale=scale, indexes=indexes)
        dest = dm['data']['destination_path']

        if is_tacc():
            cpus = get_n_tacc_cores(n_tasks=len(tasks))
            if is_tacc() and (scale == 'scale_1'):
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

            self.initPbar.emit(len(tasks))
            all_results = []
            i = 0
            with ctx.Pool(processes=cpus) as pool:
                for result in tqdm.tqdm(
                        pool.imap_unordered(run_recipe, tasks),
                        total=len(tasks),
                        desc="Compute Affines",
                        position=0,
                        leave=True):
                    all_results.append(result)
                    i += 1
                    self.progress.emit(i)

            # # For use with ThreadPool ONLY
            for r in all_results:
                index = r['swim_settings']['index']
                method = r['swim_settings']['method']
                sec = dm['data']['scales'][scale]['stack'][index]
                sec['alignment'] = r
                sec['alignment_history'][method]['method_results'] = copy.deepcopy(r['method_results'])
                sec['alignment_history'][method]['swim_settings'] = copy.deepcopy(r['swim_settings'])
                try:
                    assert np.array(sec['alignment_history'][method]['method_results']['affine_matrix']).shape == (2, 3)
                    # dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['complete'] = True
                except:
                    logger.warning(f"Task failed at index: {index}")
        else:

            task_queue = TaskQueue(n_tasks=len(tasks), dest=dest)
            task_queue.taskPrefix = 'Computing Alignment for '
            task_queue.taskNameList = [os.path.basename(layer['alignment']['swim_settings']['fn_transforming']) for
                                       layer in [dm()[i] for i in indexes]]
            task_queue.start(cpus)
            align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'recipe_maker.py')
            logger.info('adding tasks to the queue...')
            for zpos, sec in [(i, dm()[i]) for i in indexes]:
                if sec['alignment']['swim_settings']['include'] and (zpos != first_unskipped):
                    # encoded_data = json.dumps(copy.deepcopy(sec))
                    encoded_data = json.dumps(sec['alignment'])
                    task_args = [sys.executable, align_job, encoded_data]
                    task_queue.add_task(task_args)
            dt = task_queue.collect_results()
            dm.t_align = dt
            all_results = task_queue.task_dict

            dm.t_align = time.time() - t0

            logger.info('Reading task results and updating data model...')
            # # For use with mp_queue.py ONLY
            for tnum in range(len(all_results)):
                # Get the updated datamodel previewmodel from stdout for the task
                parts = all_results[tnum]['stdout'].split('---JSON-DELIMITER---')
                dm_text = None
                for p in parts:
                    ps = p.strip()
                    if ps.startswith('{') and ps.endswith('}'):
                        dm_text = p
                if dm_text != None:
                    results_dict = json.loads(dm_text)
                    index = results_dict['swim_settings']['index']
                    method = results_dict['swim_settings']['method']
                    sec = dm['data']['scales'][scale]['stack'][index]
                    sec['alignment'] = results_dict
                    sec['alignment_history'][method]['method_results'] = copy.deepcopy(results_dict['method_results'])
                    sec['alignment_history'][method]['swim_settings'] = copy.deepcopy(results_dict['swim_settings'])
                    try:
                        assert np.array(sec['alignment_history'][method]['method_results']['affine_matrix']).shape == (
                        2, 3)
                        dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['complete'] = True
                    except:
                        logger.warning(f"Task failed at index: {index}")

        t_elapsed = time.time() - t0
        dm.t_align = t_elapsed
        logger.info(f"Elapsed Time, SWIM to compute affines: {t_elapsed:.3g}")
        for zpos, sec in [(i, dm()[i]) for i in indexes]:
            method = sec['alignment']['swim_settings']['method']
            sec['alignment_history'][method]['complete'] = True

        logger.info(f"Compute Affines Finished for {indexes}")

        SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=dm.default_poly_order)

        # Todo make this better
        for i, layer in enumerate(dm.get_iter(scale)):
            layer['alignment_history'][dm.method(l=i)]['method_results']['cafm_hash'] = dm.cafm_current_hash(l=i)

        # if cfg.mw._isProjectTab():
        #     cfg.mw.updateCorrSignalsDrawer()
        #     cfg.mw.setTargKargPixmaps()

        save2file(dm=dm._data, name=dm.dest())

        thumbnailer = Thumbnailer()
        thumbnailer.reduce_matches(indexes=indexes, dest=dm['data']['destination_path'], scale=scale)

        if not swim_only:
            if dm['state']['auto_generate']:
                GenerateAligned(dm, scale, indexes, renew_od=renew_od, reallocate_zarr=reallocate_zarr)
                thumbnailer.reduce_aligned(indexes, dest=dest, scale=scale)

        self.result = dm
        self.alignmentFinished.emit() #Important!



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
    name = data_cp['data']['destination_path']
    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp)
    logger.info(f'---- SAVING  ----\n{name}')
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    # logger.info('Save Name: %s' % name)
    with open(name, 'w') as f:
        f.write(proj_json)