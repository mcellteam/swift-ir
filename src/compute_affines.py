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
from src.helpers import pretty_elapsed, is_tacc


__all__ = ['ComputeAffines']

logger = logging.getLogger(__name__)

def ComputeAffines(scale, path, start=0, end=None, use_gui=True, renew_od=False, reallocate_zarr=False, stageit=False, swim_only=False, bounding_box=False, dm=None):
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
            print(f'\n\n######## Initializing Alignment ########\n')
        else:
            print(f'\n\n######## Refining Alignment ########\n')

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
        logger.info('Start Layer: %s /End layer: %s' % (str(start), str(end)))

        # checkForTiffs(path)

        signals_dir = os.path.join(dm.dest(), scale, 'signals')
        if not os.path.exists(signals_dir):
            os.mkdir(signals_dir)

        # dm.clear_method_results(scale=scale, start=start, end=end) #0727-
        if rename_switch:
            rename_layers(use_scale=scale, al_dict=alignment_dict)

        # substack = copy.deepcopy(dm()[start:end])
        # substack = dm()[start:end]

        first_unskipped = cfg.data.first_unskipped(s=scale)
        # logger.info('# Sections         : %d' % len(dm))
        # logger.info('First unskipped    : %d' % first_unskipped)

        scale_val = get_scale_val(scale)
        tasks = []
        for sec in dm()[start:end]:
            # zpos = sec['alignment']['meta']['index']
            zpos = dm().index(sec)

            if not sec['skipped'] and (zpos != first_unskipped):
                # logger.info(f'Adding task for {zpos}')
                sec['alignment']['meta'] = {}
                zpos = dm().index(sec)
                sec['alignment']['method_results'].pop('swim_args', None)
                sec['alignment']['method_results'].pop('swim_out', None)
                sec['alignment']['method_results'].pop('swim_err', None)
                sec['alignment']['method_results'].pop('mir_toks', None)
                sec['alignment']['method_results'].pop('mir_script', None)
                sec['alignment']['method_results'].pop('mir_out', None)
                sec['alignment']['method_results'].pop('mir_err', None)
                sec['alignment']['meta']['index'] = zpos
                sec['alignment']['meta']['scale_val'] = scale_val
                sec['alignment']['meta']['scale_key'] = scale
                sec['alignment']['meta']['isRefinement'] = dm['data']['scales'][scale]['isRefinement']
                sec['alignment']['meta']['isCoarsest'] = dm.coarsest_scale_key() == cfg.data.scale
                sec['alignment']['meta']['destination_path'] = dm['data']['destination_path']
                sec['alignment']['meta']['defaults'] = dm['data']['defaults']
                sec['alignment']['meta']['img_size'] = dm['data']['scales'][scale]['image_src_size']
                sec['alignment']['meta']['skipped'] = sec['skipped']
                sec['alignment']['meta']['dev_mode'] = cfg.DEV_MODE
                sec['alignment']['meta']['recipe_logging'] = cfg.RECIPE_LOGGING
                sec['alignment']['meta']['verbose_swim'] = cfg.VERBOSE_SWIM
                sec['alignment']['meta']['fn_transforming'] = sec['filename']
                sec['alignment']['meta']['fn_reference'] = sec['reference']
                sec['alignment']['meta']['method'] = sec['current_method']


                if sec['current_method'] == 'grid-default':
                    sec['alignment']['meta']['whitening'] = cfg.data['data']['defaults']['signal-whitening']
                    sec['alignment']['meta']['iterations'] = cfg.data['data']['defaults']['swim-iterations']
                else:
                    sec['alignment']['meta']['whitening'] = sec['alignment']['swim_settings']['signal-whitening']
                    sec['alignment']['meta']['iterations'] = sec['alignment']['swim_settings']['iterations']

                if dm['data']['scales'][scale]['isRefinement']:
                    scale_prev = dm.scales()[dm.scales().index(scale) + 1]
                    prev_scale_val = int(scale_prev[len('scale_'):])
                    upscale = (float(prev_scale_val) / float(scale_val))
                    init_afm = np.array(copy.deepcopy(dm['data']['scales'][scale_prev]['stack'][zpos]['alignment']['method_results']['affine_matrix']))
                    # prev_method = scale_prev_dict[zpos]['current_method']
                    # prev_afm = copy.deepcopy(np.array(scale_prev_dict[zpos]['alignment_history'][prev_method]['affine_matrix']))
                    init_afm[0][2] *= upscale
                    init_afm[1][2] *= upscale
                    sec['alignment']['meta']['init_afm'] = init_afm.tolist()
                else:
                    sec['alignment']['meta']['init_afm'] = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()

                tasks.append(copy.deepcopy(sec['alignment']))
            # else:
            #     logger.info(f"Dropping task for {zpos}")


        delete_correlation_signals(dm=dm, scale=scale, start=start, end=end)
        dest = dm['data']['destination_path']

        if cfg.CancelProcesses:
            logger.warning('Canceling Processes!')
            return


        cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks)),1)
        if is_tacc() and (scale == 'scale_1'):
            # cpus = 34
            cpus = cfg.SCALE_1_CORES_LIMIT

        t0 = time.time()



        logger.info(f"# cpus for alignment: {cpus}")

        # f_recipe_maker = f'{os.path.split(os.path.realpath(__file__))[0]}/src/recipe_maker.py'

        # pbar = tqdm.tqdm(total=len(tasks), desc="Compute Affines", position=0, leave=True)
        # def update_pbar(*a):
        #     pbar.update()


        if cfg.USE_MULTIPROCESSING_POOL:
            ctx = mp.get_context('forkserver')
            with ctx.Pool(processes=cpus) as pool:
                all_results = list(
                    tqdm.tqdm(pool.imap(run_recipe, tasks, chunksize=5),
                              total=len(tasks), desc="Compute Affines",
                              position=0, leave=True))

            t_elapsed = time.time() - t0
            dm.t_align = t_elapsed
            cfg.main_window.set_elapsed(t_elapsed, f"Compute affines {scale}")

            # # For use with ThreadPool ONLY
            for r in all_results:
                index = r['meta']['index']
                method = r['meta']['method']
                dm['data']['scales'][scale]['stack'][index]['alignment'] = r
                dm['data']['scales'][scale]['stack'][index][
                    'alignment_history'][method] = r['method_results']
        else:

            task_queue = TaskQueue(n_tasks=len(tasks), dest=dest, use_gui=use_gui)
            task_queue.taskPrefix = 'Computing Alignment for '
            task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in cfg.data()[start:end]]
            task_queue.taskNameList = [os.path.basename(layer['filename']) for layer in dm['data']['scales'][scale]['stack'][start:end]]
            # START TASK QUEUE
            task_queue.start(cpus)
            # align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'job_recipe_alignment.py')
            align_job = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'recipe_maker.py')
            logger.info('adding tasks to the queue...')
            for sec in dm()[start:end]:
                if not sec['skipped']:
                    # encoded_data = json.dumps(copy.deepcopy(sec))
                    encoded_data = json.dumps(sec['alignment'])
                    task_args = [sys.executable, align_job, encoded_data]
                    task_queue.add_task(task_args)
            logger.info('collecting results...')
            dt = task_queue.collect_results()
            dm.t_align = dt
            all_results = task_queue.task_dict

            dm.t_align = time.time() - t0
            task_dict = {}
            index_arg = 3
            for k in task_queue.task_dict.keys():
                t = task_queue.task_dict[k]
                logger.critical(f"\nt = {t}\n\n")
                task_dict[int(t['args'][index_arg])] = t
            task_list = [task_dict[k] for k in sorted(task_dict.keys())]
            updated_model = copy.deepcopy(dm) # Integrate output of each task into a new combined datamodel previewmodel

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
                    layer_index = results_dict['alignment']['meta']['index']
                    dm['data']['scales'][scale]['stack'][layer_index] = results_dict


        logger.info("Compute Affines Finished")

        SetStackCafm(dm.get_iter(scale), scale=scale, poly_order=cfg.data.default_poly_order)

        for i, layer in enumerate(cfg.data.get_iter(scale)):
            layer['alignment_history'][cfg.data.get_current_method(l=i)]['cumulative_afm'] = \
                cfg.data['data']['scales'][scale]['stack'][i]['alignment']['method_results']['cumulative_afm']
            layer['alignment_history'][cfg.data.get_current_method(l=i)]['cafm_hash'] = \
                cfg.data.cafm_current_hash(l=i)

        if cfg.mw._isProjectTab():
            cfg.mw.updateCorrSignalsDrawer()
            cfg.mw.setTargKargPixmaps()


        save2file(dm=dm,name=dm.dest())


        logger.info('Sleeping for 1 seconds...')
        time.sleep(1)

        cpus = max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, len(tasks)), 1)

        if not swim_only:
            if use_gui:
                if cfg.mw._isProjectTab():
                    if not cfg.pt._toggleAutogenerate.isChecked():
                        logger.info('Toggle auto-generate is OFF. Returning...')
                        return
            try:
                if cfg.USE_EXTRA_THREADING and use_gui:
                    cfg.mw.worker = BackgroundWorker(fn=GenerateAligned(
                        dm, scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui))
                    cfg.mw.threadpool.start(cfg.mw.worker)
                else:
                    GenerateAligned(dm, scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui)

            except:
                print_exception()
            finally:
                logger.info('Generate Alignment Finished')

            # logger.info('Sleeping for 1 seconds...')
            # time.sleep(1)

            thumbnailer = Thumbnailer()
            try:
                if cfg.USE_EXTRA_THREADING and use_gui:
                    cfg.mw.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(start=start, end=end, dest=dest, scale=scale, use_gui=use_gui))
                    cfg.mw.threadpool.start(cfg.mw.worker)
                else:
                    thumbnailer.reduce_aligned(start=start, end=end, dest=dest, scale=scale, use_gui=use_gui)
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


def delete_correlation_signals(dm, scale, start, end):
    logger.info('')
    for i in range(start, end):
        sigs = dm.get_signals_filenames(s=scale, l=i)
        # logger.info(f'Deleting:\n{sigs}')
        for f in sigs:
            if os.path.isfile(f):  # this makes the code more robust
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
    data_cp_json = data_cp.to_dict()

    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode(data_cp_json)
    name = dm.dest()
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
    dm = ComputeAffines(scale=scale, path=path, start=start, end=end, use_gui=False, bounding_box=args.bounding_box)
    save2file(dm=dm, name=dm.dest())


