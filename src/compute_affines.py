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
import shutil
import argparse
import traceback
import inspect
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
from src.background_worker import BackgroundWorker
import src.config as cfg
from src.ui.timer import Timer
from src.recipe_maker import run_recipe
from src.helpers import pretty_elapsed, is_tacc, get_n_tacc_cores


__all__ = ['ComputeAffines']

logger = logging.getLogger(__name__)

def ComputeAffines(scale, path, indexes, renew_od=False, reallocate_zarr=False, swim_only=False, dm=None):
    '''Compute the python_swiftir transformation matrices for the current s stack of images according to Recipe1.'''
    # caller = inspect.stack()[1].function

    # logger.info(f'use_gui = {use_gui}')

    if cfg.DEBUG_MP:
        # if 1:
        logger.info('Multiprocessing Module Debugging is ENABLED')
        mpl = mp.log_to_stderr()
        mpl.setLevel(logging.DEBUG)

    if cfg.CancelProcesses:
        cfg.mw.warn('Canceling Compute Affine Tasks')
    else:
        if scale == dm.coarsest_scale_key():
            print(f'\n\n######## Initializing Alignment for {indexes} ########\n')
        else:
            print(f'\n\n######## Refining Alignment for {indexes} ########\n')

        cfg.mw._autosave()
        # if path:
        use_gui = 1
        if not use_gui:
            with open(path, 'r') as f:
                try:
                    data = json.load(f)
                except Exception as e:
                    logger.warning(e)
                    return
            dm = DataModel(data)
            dm.set_defaults()

        scratchpath = os.path.join(dm.dest(), 'logs', 'scratch.log')
        if os.path.exists(scratchpath):
            os.remove(scratchpath)

        rename_switch = False
        alignment_dict = dm['data']['scales'][scale]['stack']

        # alignment_option = dm['data']['scales'][scale_key]['method_data']['alignment_option']
        logger.critical(f"indexes: {indexes}")

        # checkForTiffs(path)

        signals_dir = os.path.join(dm.dest(), scale, 'signals')
        if not os.path.exists(signals_dir):
            os.mkdir(signals_dir)

        matches_dir = os.path.join(dm.dest(), scale, 'matches_raw')
        if not os.path.exists(matches_dir):
            os.mkdir(matches_dir)

        if rename_switch:
            rename_layers(use_scale=scale, al_dict=alignment_dict)

        # substack = copy.deepcopy(dm()[start:end])
        # substack = dm()[start:end]

        first_unskipped = cfg.data.first_unskipped(s=scale)
        # logger.info('# Sections         : %d' % len(dm))
        # logger.info('First unskipped    : %d' % first_unskipped)

        scale_val = get_scale_val(scale)
        tasks = []
        for zpos, sec in [(i, dm()[i]) for i in indexes]:
            # zpos = sec['alignment']['meta']['index']
            # if not sec['skipped'] and (zpos != first_unskipped):
            if 1:
                # logger.info(f'Adding task for {zpos}')
                # sec['alignment']['meta'] = {}
                zpos = dm().index(sec)

                sec['alignment'].setdefault('method_results', {})
                mr = sec['alignment']['method_results']
                mr.pop('swim_args', None)
                mr.pop('swim_out', None)
                mr.pop('swim_err', None)
                mr.pop('mir_toks', None)
                mr.pop('mir_script', None)
                mr.pop('mir_out', None)
                mr.pop('mir_err', None)

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
                    ss['whiten'] = cfg.data['data']['defaults']['signal-whitening']
                    ss['swim_iters'] = cfg.data['data']['defaults']['swim-iterations']
                else:
                    ss['whiten'] = ss['signal-whitening']
                    ss['swim_iters'] = ss['iterations']

                if dm['data']['scales'][scale]['isRefinement']:
                    scale_prev = dm.scales()[dm.scales().index(scale) + 1]
                    prev_scale_val = int(scale_prev[len('scale_'):])
                    upscale = (float(prev_scale_val) / float(scale_val))
                    prev_method = dm['data']['scales'][scale_prev]['stack'][zpos]['alignment']['swim_settings']['method']
                    init_afm = np.array(copy.deepcopy(dm['data']['scales'][scale_prev]['stack'][zpos][
                                                          'alignment_history'][prev_method]['method_results']['affine_matrix']))
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
                    logger.info(f"EXCLUDING section #{zpos}")
                    cfg.main_window.tell(f"EXCLUDING section #{zpos}")
            # else:
            #     logger.info(f"Dropping task for {zpos}")


        delete_correlation_signals(dm=dm, scale=scale, indexes=indexes)
        delete_matches(dm=dm, scale=scale, indexes=indexes)
        dest = dm['data']['destination_path']

        cpus = get_n_tacc_cores(n_tasks=len(tasks))
        if is_tacc() and (scale == 'scale_1'):
            # cpus = 34
            cpus = cfg.SCALE_1_CORES_LIMIT

        t0 = time.time()

        logger.info(f"# cores: {cpus}")

        # f_recipe_maker = f'{os.path.split(os.path.realpath(__file__))[0]}/src/recipe_maker.py'

        if cfg.USE_POOL_FOR_SWIM:
            ctx = mp.get_context('forkserver')
            with ctx.Pool(processes=cpus) as pool:
                all_results = list(
                    tqdm.tqdm(pool.imap(run_recipe, tasks, chunksize=5),
                              total=len(tasks), desc="Compute Affines",
                              position=0, leave=True))
            # # For use with ThreadPool ONLY
            cfg.all_results = all_results
            for r in all_results:
                index = r['swim_settings']['index']
                method = r['swim_settings']['method']
                dm['data']['scales'][scale]['stack'][index]['alignment'] = r
                dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['method_results'] = \
                    copy.deepcopy(r['method_results'])
                dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['swim_settings'] = \
                    copy.deepcopy(r['swim_settings'])
                try:
                    assert np.array(dm['data']['scales'][scale]['stack'][index]['alignment_history'][method][
                                        'method_results']['affine_matrix']).shape == (2, 3)
                    dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['complete'] = True
                except:
                    logger.warning(f"Task failed at index: {index}")
        else:

            task_queue = TaskQueue(n_tasks=len(tasks), dest=dest, use_gui=use_gui)
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
                    dm['data']['scales'][scale]['stack'][index]['alignment'] = results_dict
                    dm['data']['scales'][scale]['stack'][index]['alignment_history'][method][
                        'method_results'] = copy.deepcopy(results_dict['method_results'])
                    dm['data']['scales'][scale]['stack'][index]['alignment_history'][method][
                        'swim_settings'] = copy.deepcopy(results_dict['swim_settings'])
                    try:
                        assert np.array(dm['data']['scales'][scale]['stack'][index]['alignment_history'][method][
                            'method_results']['affine_matrix']).shape == (2,3)
                        dm['data']['scales'][scale]['stack'][index]['alignment_history'][method]['complete'] = True
                    except:
                        logger.warning(f"Task failed at index: {index}")

        t_elapsed = time.time() - t0
        dm.t_align = t_elapsed
        cfg.main_window.set_elapsed(t_elapsed, f"Compute affines {scale}")

        logger.info(f"Compute Affines Finished for {indexes}")

        SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=cfg.data.default_poly_order)

        #Todo make this better
        for i, layer in enumerate(cfg.data.get_iter(scale)):
            # layer['alignment_history'][cfg.data.method(l=i)]['method_results']['cumulative_afm'] = \
            #     cfg.data['data']['scales'][scale]['stack'][i]['alignment']['method_results']['cumulative_afm']
            layer['alignment_history'][cfg.data.method(l=i)]['method_results']['cafm_hash'] = \
                cfg.data.cafm_current_hash(l=i)

        if cfg.mw._isProjectTab():
            cfg.mw.updateCorrSignalsDrawer()
            cfg.mw.setTargKargPixmaps()


        save2file(dm=dm._data,name=dm.dest())

        # logger.info('Sleeping for 1 seconds...')
        # time.sleep(1)


        if not swim_only:
            if use_gui:
                if cfg.mw._isProjectTab():
                    if not cfg.pt._toggleAutogenerate.isChecked():
                        logger.info('Toggle auto-generate is OFF. Returning...')
                        return
            try:
                if cfg.USE_EXTRA_THREADING and use_gui:
                    cfg.mw.worker = BackgroundWorker(fn=GenerateAligned(
                        dm, scale, indexes, renew_od=renew_od, reallocate_zarr=reallocate_zarr, use_gui=use_gui))
                    cfg.mw.threadpool.start(cfg.mw.worker)
                else:
                    GenerateAligned(dm, scale, indexes, renew_od=renew_od, reallocate_zarr=reallocate_zarr,
                                    use_gui=use_gui)

            except:
                print_exception()
            finally:
                logger.info('Generate Alignment Finished')

            # logger.info('Sleeping for 1 seconds...')
            # time.sleep(1)

            thumbnailer = Thumbnailer()
            try:
                if cfg.USE_EXTRA_THREADING and use_gui:
                    cfg.mw.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(indexes, dest=dest, scale=scale,
                                                                                 use_gui=use_gui))
                    cfg.mw.threadpool.start(cfg.mw.worker)
                else:
                    thumbnailer.reduce_aligned(indexes, dest=dest, scale=scale, use_gui=use_gui)
            except:
                print_exception()
            finally:
                logger.info('Generate Aligned Thumbnails Finished')

            if cfg.ignore_pbar:
                cfg.nProcessDone += 1
                cfg.mw.updatePbar()
                cfg.mw.setPbarText('Aligning')

        return dm

def update_pbar(value):
    # logger.info(f"value: {value}")
    cfg.mw.pbar.setValue(cfg.mw.pbar.value()+1)


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        # sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # result = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # cmd_proc = sp.Popen(task, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
        # cmd_stdout, cmd_stderr = cmd_proc.communicate()
        # print(f"cmd_stdout:\n{cmd_stdout}")
        # print(f"cmd_stderr:\n{cmd_stderr}")

        task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # task_proc = sp.Popen(task, shell=False, stdout=sys.stdout, stderr=sys.stderr, bufsize=1)
        result = task_proc.communicate()  # assemble_recipe the task and capture output
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

# def delete_correlation_signals(dm, scale_key, start, end, dest):
#     logger.info('')
#     for i in range(start, end):
#         # sigs = cfg.data.get_signals_filenames(s=scale_key, l=i)
#         sigs = get_signals_filenames(pdscale=scale_key)
#         dir = os.path.join(sest, scale_key, 'signals')
#         basename = os.path.basename(dm.base_image_name(s=s, l=l))
#         filename, extension = os.path.splitext(basename)
#         paths = os.path.join(dir, '%s_%s_*%s' % (filename, self.current_method, extension))
#         names = glob(paths)
#         # logger.info(f'Search Path: {paths}\nReturning: {names}')
#         return natural_sort(names)
#         logger.info(f'Deleting:\n{sigs}')
#         for f in sigs:
#             if os.path.isfile(f):  # this makes the code more robust
#                 logger.info(f"Removing file '%s'" % f)
#                 os.remove(f)



# def get_signals_filenames(destination, scale_key):
#     dir = os.path.join(self.dest(), s, 'signals')
#     basename = os.path.basename(dm.base_image_name(s=s, l=l))
#     filename, extension = os.path.splitext(basename)
#     paths = os.path.join(dir, '%s_%s_*%s' % (filename, self.current_method, extension))
#     names = glob(paths)
#     # logger.info(f'Search Path: {paths}\nReturning: {names}')
#     return natural_sort(names)

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

def write_run_to_file(dm, scale=None):
    logger.critical('Writing run to file...')
    if scale == None: scale = dm.scale_key
    # snr_avg = 'SNR=%.3f' % dm.snr_average(scale_key=scale_key)
    timestamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    results = 'results'
    # swim_input = 'swim=%.3f' % dm.swim_window()
    # whitening_input = 'whitening=%.3f' % dm.whitening()
    # details = [date, time, s, _swimWindowControl, sb_whiteningControl, snr_avg]
    scale_str = 's' + str(get_scale_val(scale))
    details = [scale_str, results, timestamp]
    fn = '_'.join(details) + '.json'
    of = Path(os.path.join(dm.dest(), scale, 'history', fn))
    of.parent.mkdir(exist_ok=True, parents=True)
    with open(of, 'w') as f:
        json.dump(dm['data']['scales'][scale], f, indent=4)


def rename_layers(use_scale, al_dict):
    logger.info('rename_layers:')
    source_dir = os.path.join(cfg.data.dest(), use_scale, "img_src")
    for layer in al_dict:
        image_name = None
        if 'base' in layer['images'].keys():
            image = layer['images']['base']
            try:
                image_name = os.path.basename(image['filename'])
                destination_image_name = os.path.join(source_dir, image_name)
                shutil.copyfile(image.image_file_name, destination_image_name)
            except:
                logger.warning('Something went wrong with renaming the alignment layers')
                pass


def get_scale_val(scale_of_any_type) -> int:
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            return scale
        else:
            while scale.startswith('scale_'):
                scale = scale[len('scale_'):]
            return int(scale)
    except:
        logger.warning('Unable to return s value')


def print_exception():
    tstamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
    exi = sys.exc_info()
    txt = f" [{tstamp}]\nError Type/Value : {exi[0]} / {exi[1]}\n{traceback.format_exc()}"
    logger.warning(txt)

    if cfg.data:
        lf = os.path.join(cfg.data.dest(), 'logs', 'exceptions.log')
        with open(lf, 'a+') as f:
            f.write('\n' + txt)

'''
SWIM argument string: ww_416 -i 2 -w -0.68 -x -256 -y 256  /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/test98/scale_4/img_src/R34CA1-BS12.102.tif 512.000000 512.000000  1.000000 0.000000 -0.000000 1.000000


'''

def save2file(dm, name):
    data_cp = copy.deepcopy(dm)
    # data_cp.make_paths_relative(start=cfg.data.dest())
    # data_cp_json = data_cp.to_dict()
    name = data_cp['data']['destination_path']

    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp)
    logger.info(f'---- SAVING  ----\n{name}')
    if not name.endswith('.swiftir'):
        name += ".swiftir"
    # logger.info('Save Name: %s' % name)
    with open(name, 'w') as f:
        f.write(proj_json)


if __name__ == '__main__':
    logger.info('Running ' + __file__ + '.__main__()')
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', help='Path to project file')
    parser.add_argument('--scale_key', help='Scale to use')
    parser.add_argument('--start', default=0, help='Section index to start at')
    parser.add_argument('--end', default=None, help='Section index to end at')
    parser.add_argument('--bounding_box', default=False, help='Bounding Box On/Off')
    args = parser.parse_args()
    logger.info(f'args : {args}')
    # os.environ['QT_API'] = args.api
    if args.path:
        path = args.path
    else:
        path = '/Users/joelyancey/glanceem_swift/test_projects/test4.swiftir'

    with open(path, 'r') as f:
        data = json.load(f)

    if args.scale:
        scale = args.scale
    else:
        # scale_key = data['data']['current_scale']
        scale = 'scale_4'
    start = args.start
    end = args.end
    dm = ComputeAffines(scale=scale, path=path, indexes=list(range(start,end)))
    save2file(dm=dm, name=dm.dest())


