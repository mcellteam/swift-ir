#!/usr/bin/env python3

'''

https://gist.github.com/jbms/1ec1192c34ec816c2c517a3b51a8ed6c

https://programtalk.com/vs4/python/janelia-cosem/fibsem-tools/src/fibsem_tools/io/zarr.py/
'''

import os, re, sys, stat, copy, json, time, signal, logging, inspect
import platform, traceback, shutil, statistics, tracemalloc
from os.path import expanduser
import getpass
from time import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Union, Sequence
from glob import glob
from pathlib import Path
from contextlib import contextmanager
import zarr
import imghdr
import tifffile
import numpy as np
from shutil import rmtree
import psutil
from functools import reduce
import operator
import neuroglancer as ng
import subprocess as sp

from qtpy.QtWidgets import QApplication

try:
    import src.config as cfg
except:
    import config as cfg

try:
    import builtins
except:
    pass

try:
    from src.utils.treeview import Treeview
except:
    from utils.treeview import Treeview

__all__ = ['is_tacc', 'is_linux', 'is_mac', 'create_paged_tiff', 'check_for_binaries', 'delete_recursive',
           'do_scales_exist', 'make_relative', 'make_absolute', 'get_img_filenames', 'print_exception',
           'get_scale_key', 'get_scale_val', 'print_project_tree',
           'verify_image_file', 'exist_aligned_zarr', 'get_scales_with_generated_alignments', 'handleError',
           'count_widgets', 'find_allocated_widgets', 'absFilePaths', 'validate_file', 'hotkey',
           'caller_name','addLoggingLevel', 'sanitizeSavedPaths', 'recursive_key_values'
           ]

logger = logging.getLogger(__name__)

snapshot = None


def hotkey(letter: str):
    return "(" + ('^', '⌘')[is_mac()] + "%s)" % letter

def get_n_tacc_cores(n_tasks):
    return max(min(psutil.cpu_count(logical=False), cfg.TACC_MAX_CPUS, n_tasks),1)



def run_command(cmd, arg_list=None, cmd_input=None):
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    return ({'out': cmd_stdout, 'err': cmd_stderr, 'rc': cmd_proc.returncode})

def update_meta():
    pass



def getOpt(lookup):
    if isinstance(lookup, str):
        lookup = lookup.split(',')
    return reduce(operator.getitem, lookup, cfg.settings)


def setOpt(lookup, val):
    if isinstance(lookup, str):
        lookup = lookup.split(',')
    getOpt(lookup[:-1])[lookup[-1]] = val


def getData(lookup):
    if isinstance(lookup, str):
        lookup = lookup.split(',')
    return reduce(operator.getitem, lookup, cfg.data)


def setData(lookup, val):
    # logger.critical(f'[{caller_name()}] lookup: {lookup}, val: {val}')
    if isinstance(lookup, str):
        lookup = lookup.split(',')
    getData(lookup[:-1])[lookup[-1]] = val


def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def find_allocated_widgets(filter) -> list:
    return [k for k in map(str, QApplication.allWidgets()) if str(filter) in k]


def count_widgets(name_or_type) -> int:
    return sum(name_or_type in s for s in map(str, QApplication.allWidgets()))


def sanitizeSavedPaths():
    # logger.info("Sanitizing paths...")
    # paths = cfg.settings['saved_paths']
    # n_start = len(paths)
    # sanitized = []
    # for path in paths:
    #     if os.path.exists(path) and os.path.isdir(path):
    #         sanitized.append(path)
    # n_end = len(sanitized)
    # if n_start != n_end:
    #     logger.warning(f"{n_start - n_end} saved paths were found to be invalid and will be forgotten")
    # cfg.settings['saved_paths'] = sanitized
    pass

def delete_recursive(dir, keep_core_dirs=False):
    # chunks = glob(dir + '/img_aligned.zarr/**/*', recursive=True) + glob(dir + '/img_src.zarr/**/*', recursive=True)
    to_delete = []
    scales = glob(dir + '/scale_*')
    for s in scales:
        if keep_core_dirs:
            if s == 's1':
                continue
        if os.path.exists(os.path.join(dir, 'history', s)):
            to_delete.append(os.path.join(dir, 'history', s))
        if os.path.exists(os.path.join(dir, 'signals', s)):
            to_delete.append(os.path.join(dir, 'signals', s))
        if os.path.exists(os.path.join(dir, 'matches', s)):
            to_delete.append(os.path.join(dir, 'matches', s))
        if os.path.exists(os.path.join(dir, 'bias_data', s)):
            to_delete.append(os.path.join(dir, 'bias_data', s))
        if os.path.exists(os.path.join(dir, 'tiff', s)):
            to_delete.append(os.path.join(dir, 'tiff', s))
        if os.path.exists(os.path.join(dir, 'thumbnails', s)):
            to_delete.append(os.path.join(dir, 'thumbnails', s))
        # if os.path.exists(os.path.join(dir, level, 'img_src')):
        #     to_delete.append(os.path.join(dir, level, 'img_src'))
    to_delete.extend(glob(dir + '/zarr/level*'))
    # to_delete.extend(glob(dir + '/img_src.zarr/level*'))
    if not keep_core_dirs:
        to_delete.append(dir + '/thumbnails')
        to_delete.append(dir)
        to_delete.append(dir)  # delete twice
    cfg.nProcessDone = 0
    cfg.nProcessSteps = len(to_delete)
    logger.info('# directories to delete: %d' % len(to_delete))
    cfg.main_window.setPbarMax(cfg.nProcessSteps)
    # logger.critical(f'To Delete: {to_delete}')
    for d in to_delete:
        cfg.nProcessDone += 1
        shutil.rmtree(d, ignore_errors=True, onerror=handleError)
        cfg.main_window.updatePbar(cfg.nProcessDone)
        cfg.main_window.update()
        QApplication.processEvents()
    shutil.rmtree(dir, ignore_errors=True, onerror=handleError)

    # cfg.main_window.hidePbar()


def update_preferences_model():
    # caller = inspect.stack()[1].function
    logger.info(f'Updating user preferences model...')
    if '.tacc.utexas.edu' in platform.node():
        DEFAULT_CONTENT_ROOT = os.path.join(os.getenv('SCRATCH', "SCRATCH not found"), 'alignem_data')
    else:
        DEFAULT_CONTENT_ROOT = os.path.join(os.path.expanduser('~'), 'alignem_data')
    cfg.settings.pop('search_paths', None)
    if 'state' in cfg.settings:
        cfg.settings.pop('state', None)
    if 'ui' in cfg.settings:
        cfg.settings.pop('ui', None)
    cfg.settings.pop('search_paths', None)

    cfg.settings.setdefault('neuroglancer', {})
    cfg.settings['neuroglancer'].setdefault('SHOW_UI_CONTROLS', False)
    cfg.settings['neuroglancer'].setdefault('USE_CUSTOM_BACKGROUND', False)
    cfg.settings['neuroglancer'].setdefault('CUSTOM_BACKGROUND_COLOR', None)
    cfg.settings['neuroglancer'].setdefault('USE_DEFAULT_DARK_BACKGROUND', True)
    cfg.settings['neuroglancer'].setdefault('SHOW_YELLOW_FRAME', False)
    cfg.settings['neuroglancer'].setdefault('SHOW_SCALE_BAR', False)
    cfg.settings['neuroglancer'].setdefault('SHOW_AXIS_LINES', False)
    cfg.settings['neuroglancer'].setdefault('MATCHPOINT_MARKER_SIZE', 8)
    cfg.settings['neuroglancer'].setdefault('MATCHPOINT_MARKER_LINEWEIGHT', 3)
    cfg.settings['neuroglancer'].setdefault('SHOW_SWIM_WINDOW', True)
    cfg.settings['neuroglancer'].setdefault('SHOW_HUD_OVERLAY', True)
    cfg.settings['neuroglancer'].setdefault('NEUTRAL_CONTRAST_MODE', False)

    cfg.settings.setdefault('locations', [])
    cfg.settings.setdefault('alignments', [])

    cfg.settings.setdefault('series_combo_text', None)
    cfg.settings.setdefault('alignment_combo_text', None)
    cfg.settings.setdefault('notes', {})
    cfg.settings['notes'].setdefault('global_notes', '')

    cfg.settings.setdefault('content_root', DEFAULT_CONTENT_ROOT)
    if not os.path.isdir(DEFAULT_CONTENT_ROOT):
        logger.info(f"Making content root directory: {DEFAULT_CONTENT_ROOT}")
        os.makedirs(DEFAULT_CONTENT_ROOT, exist_ok=True)

    p = os.path.join(DEFAULT_CONTENT_ROOT, 'series')
    cfg.settings.setdefault('series_root', p)
    if not os.path.isdir(p):
        logger.info(f"Making default alignments directory: {p}")
        os.makedirs(p, exist_ok=True)

    p = os.path.join(DEFAULT_CONTENT_ROOT, 'alignments')
    cfg.settings.setdefault('alignments_root', p)
    if not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

    cfg.settings.setdefault('series_search_paths', [os.path.join(DEFAULT_CONTENT_ROOT, 'series')])
    cfg.settings.setdefault('alignments_search_paths', [os.path.join(DEFAULT_CONTENT_ROOT, 'alignments')])

    cfg.settings.setdefault('saved_paths', [
        os.path.join(DEFAULT_CONTENT_ROOT, 'series'),
        os.path.join(DEFAULT_CONTENT_ROOT, 'alignments'),
    ])




def initialize_user_preferences():
    userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
    try:
        if os.path.exists(userpreferencespath):
            logger.info(f"Loading user preferences from '{userpreferencespath}'...")
            with open(userpreferencespath, 'r') as f:
                cfg.settings = json.load(f)
        else:
            logger.critical(f'Creating user preferences from defaults...')
            open(userpreferencespath, 'a').close()
            cfg.settings = {}
    except:
        print_exception()

    try:
        update_preferences_model()
    except:
        print_exception()
    '''save user preferences to file'''
    try:
        f = open(userpreferencespath, 'w')
        json.dump(cfg.settings, f, indent=2)
        f.close()
    except:
        print_exception()
        logger.warning(f'Unable to save current user preferences')


def reset_user_preferences():
    userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
    if os.path.exists(userpreferencespath):
        os.remove(userpreferencespath)
    cfg.settings = {}
    update_preferences_model()


def isNeuroglancerRunning():
    return ng.server.is_server_running()


# def validate_project_selection() -> bool:
#     # logger.info('Validating selection %level...' % cfg.selected_file)
#     # called by setSelectionPathText
#     path, extension = os.path.splitext(cfg.selected_file)
#     if extension != '.swiftir':
#         return False
#     else:
#         return True
#
# def validate_zarr_selection() -> bool:
#     logger.info('Validating selection %level...' % cfg.selected_file)
#     # called by setSelectionPathText
#     if os.path.isdir(cfg.selected_file):
#         logger.info('Path IS a directory')
#         if '.zarray' in os.listdir(cfg.selected_file):
#             logger.info('Directory DOES contain .zarray -> Returning True...')
#             return True
#     logger.info('Returning False...')
#     return False


def validate_file(file) -> bool:
    # logger.info('Validating file...\n%level' % file)
    # logger.info('called by %level' % inspect.stack()[1].function)
    is_valid = False
    path, extension = os.path.splitext(file)
    if extension != '.swiftir':
        return False
    else:
        return True


def cleanup_project_list(paths: list) -> list:
    # logger.info(f'paths: {paths}')
    paths = list(dict.fromkeys(paths))  # remove duplicates
    paths = [x for x in paths if x != '']
    clean_paths = []
    for path in paths:
        project_dir = os.path.splitext(path)[0]
        if os.path.exists(path):
            if os.path.isdir(project_dir):
                if validate_file(path):
                    clean_paths.append(path)
    diff = list(set(paths) - set(clean_paths))
    if diff:
        txt = f'Some projects were not found and will be removed from the project cache:\n{diff}'
        logger.warning(txt)
    # logger.info(f'clean_paths: {clean_paths}')
    return clean_paths


# def get_project_list():
#     logger.info('>>>> get_project_list >>>>')
#     try:
#         # convert_projects_model()
#         return cfg.settings['projects']
#     except:
#         print_exception()
#     finally:
#         logger.info('<<<< get_project_list <<<<')


# file = os.path.join(os.path.expanduser('~'), '.swift_cache')


def convert_projects_model():
    userprojectspath = os.path.join(os.path.expanduser('~'), '.swift_cache')
    if os.path.exists(userprojectspath):
        with open(userprojectspath, 'r') as f:
            logger.warning('Converting projects model...')
            projectpaths = [line.rstrip() for line in f]

            logger.critical(f"Projects found in old file: {projectpaths}")
            cfg.settings['projects'] = projectpaths
            # cfg.mw.saveUserPreferences()
            try:
                os.remove(userprojectspath)
            except:
                print_exception()


def configure_project_paths():
    # caller = inspect.stack()[1].function
    # logger.info('')
    # userprojectspath = os.path.join(os.path.expanduser('~'), '.swift_cache')
    # if not os.path.exists(userprojectspath):
    #     open(userprojectspath, 'a').close()
    try:
        # with open(userprojectspath, 'r') as f:
        #     lines = f.readlines()
        # paths = [line.rstrip() for line in lines]
        # convert_projects_model()
        paths = cfg.settings['projects']
        logger.critical(f'paths: {paths}')
        cleanpaths = cleanup_project_list(paths)
        logger.critical(f'cleanpaths: {cleanpaths}')
        # with open(userprojectspath, 'w') as f:
        #     for p in cleanpaths:
        #         f.write(f"{p}\n")
        cfg.settings['projects'] = cleanpaths
        if cleanpaths:
            logger.info('AlignEM-SWiFT knows about the following projects:\n\n'
                        '  %s\n' % '\n  '.join(cleanpaths))
    except:
        print_exception()


def check_for_binaries():
    print("Checking for platform-specific SWiFT-IR executables...")
    path = os.path.split(os.path.realpath(__file__))[0]
    if platform.system() == 'Darwin':
        bindir = os.path.join(path, 'lib', 'bin_darwin')
    elif platform.system() == 'Linux':
        bindir = os.path.join(path, 'lib', 'bin_tacc') if '.tacc.utexas.edu' in platform.node() else 'bin_linux'
    else:
        logger.warning("System Could Not Be Resolved. C Binaries Not Found.")
        return
    bin_lst = [os.path.join(bindir, 'iavg'),
               os.path.join(bindir, 'iscale2'),
               os.path.join(bindir, 'mir'),
               os.path.join(bindir, 'remod'),
               os.path.join(bindir, 'swim')
               ]
    for f in bin_lst:
        if os.path.isfile(f):
            print(u'\u2713 FOUND: ' + f)
        else:
            logger.warning('BINARY FILE NOT FOUND, PLEASE COMPILE: ' + f)


def obj_to_string(obj, extra='    '):
    return str(obj.__class__) + '\n' + '\n'.join(
        (extra + (str(item) + ' = ' +
                  (obj_to_string(obj.__dict__[item], extra + '    ') if hasattr(obj.__dict__[item],
                                                                                '__dict__') else str(
                      obj.__dict__[item])))
         for item in sorted(obj.__dict__)))


def is_tacc() -> bool:
    '''Checks if the program is running on a computer at TACC. Returns a boolean.'''
    return '.tacc.utexas.edu' in platform.node()


def is_linux() -> bool:
    '''Checks if the program is running on a Linux OS. Returns a boolean.'''
    return platform.system() == 'Linux'


def is_mac() -> bool:
    '''Checks if the program is running on macOS. Returns a boolean.'''
    return platform.system() == 'Darwin'


def is_joel() -> bool:
    '''Checks if the program is running on macOS. Returns a boolean.'''

    # if 'Joels-' in platform.node():
    #     return True
    # else:
    #     return False

    return getpass.getuser() in ('joelyancey','joely')

def pretty_elapsed(t):
    return f"Elapsed Time: %.3gs / %.3gm" % (t, t/60)

def get_bindir() -> str:
    '''Checks operating system. Returns the operating system-dependent
    path to where SWiFT-IR binaries should exist'''
    bindir = ''
    error = 'Operating System Could Not Be Resolved'
    if is_tacc():
        bindir = 'bin_tacc'
    elif is_mac():
        bindir = 'bin_darwin'
    elif is_linux():
        bindir = 'bin_linux'
    else:
        logger.warning(error)
        cfg.main_window.hud.post(error, logging.ERROR)
    assert len(bindir) > 0
    return bindir


def get_appdir() -> str:
    return os.path.split(os.path.realpath(__file__))[0]


def example_zarr() -> str:
    return os.path.join(get_appdir(), 'resources','example.zarr')


def absFilePaths(d):
    for dirpath, _, filenames in os.walk(d):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def absFilePathsList(d):
    return list(absFilePaths(d))


def handleError(func, path, exc_info):
    logger.warning('Handling Error for file %s' % path)
    logger.warning(exc_info)
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)


def get_paths_absolute(directory):
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def list_paths_absolute(directory):
    return natural_sort(list(get_paths_absolute(directory)))


def tracemalloc_start():
    logger.info('Starting tracemalloc memory allocation analysis...')
    tracemalloc.start()


def tracemalloc_compare():
    if tracemalloc.is_tracing():
        global snapshot
        snapshot2 = tracemalloc.take_snapshot()
        snapshot2 = snapshot2.filter_traces((
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
            tracemalloc.Filter(False, tracemalloc.__file__)
        ))

        if snapshot is not None:
            print("================================== Begin Trace:")
            top_stats = snapshot2.compare_to(snapshot, 'lineno', cumulative=True)
            for stat in top_stats[:10]:
                print(stat)
        snapshot = snapshot2
    else:
        logger.warning('tracemalloc is not currently tracing')


def tracemalloc_stop():
    if tracemalloc.is_tracing():
        logger.info('Stopping tracemalloc memory allocation analysis...')
        tracemalloc.stop()
    else:
        logger.warning('tracemalloc is not currently tracing')


def tracemalloc_clear():
    if tracemalloc.is_tracing():
        logger.info('Clearing tracemalloc traces...')
        tracemalloc.clear_traces()
    else:
        logger.warning('tracemalloc is not currently tracing')


def timer(func):
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        # print(f'Function {func.__name__!r} executed in {(t2-t1):.4f}level')
        function = f'Function {func.__name__!r}'.ljust(35, ' ')
        result = f'executed in {(t2 - t1):.4f}level'
        print(function + result)
        return result

    return wrap_func


def get_bytes(start_path='.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                # skip symbolic links
                total_size += os.path.getsize(fp)

    return total_size


def make_affine_widget_HTML(afm, cafm, fs1=9, fs2=8):
    # 'cellspacing' affects project_table width and 'cellpadding' affects project_table height
    # text = f"<project_table project_table-layout='fixed' style='border-collapse: collapse;' cellspacing='3' cellpadding='2' border='0'>"\
    # text = f"<project_table project_table-layout='fixed' style='border-collapse: collapse;' cellspacing='10' cellpadding='4' border='0'>"\
    text = f"<table table-layout='fixed' style='border-bottom: 1pt solid #161c20;' cellspacing='2' cellpadding='1'>" \
           f"  <tr>" \
           f"    <td rowspan=2 style='font-size: {fs1}px;'>{'Affine'.rjust(9)}</td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(afm[0][0], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(afm[0][1], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(afm[0][2], 3)).center(8)}</pre></center></td>" \
           f"  </tr>" \
           f"  <tr>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(afm[1][0], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(afm[1][1], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(afm[1][2], 3)).center(8)}</pre></center></td>" \
           f"  </tr>" \
           f"  <tr>" \
           f"    <td rowspan=2 style='font-size: {fs1}px;'>{'Cumulative Affine'.rjust(9)}</td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(cafm[0][0], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(cafm[0][1], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(cafm[0][2], 3)).center(8)}</pre></center></td>" \
           f"  </tr>" \
           f"  <tr>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(cafm[1][0], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(cafm[1][1], 3)).center(8)}</pre></center></td>" \
           f"    <td style='color: #161c20; width:30px; font-size: {fs2}px;'><center><pre>{str(round(cafm[1][2], 3)).center(8)}</pre></center></td>" \
           f"  </tr>" \
           f"</table>"
    return text


def elapsed_since(start):
    return time.strftime("%H:%M:%S", time.gmtime(time.time() - start))


def get_process_memory():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss


def track(func):
    def wrapper(*args, **kwargs):
        mem_before = get_process_memory()
        start = time.time()
        result = func(*args, **kwargs)
        elapsed_time = elapsed_since(start)
        mem_after = get_process_memory()
        logger.critical("{}: memory before: {:,}, after: {:,}, consumed: {:,}; exec time: {}".format(
            func.__name__,
            mem_before, mem_after, mem_after - mem_before,
            elapsed_time))
        return result

    return wrapper


def renew_directory(directory: str, gui=True) -> None:
    logger.info(f'Renewing directory {directory}...')
    '''Remove and re-create a directory, if it exists.'''
    if os.path.exists(directory):
        d = os.path.basename(directory)
        if gui:
            cfg.main_window.hud.post("Overwriting Directory '%s'..." % directory)
        try:
            shutil.rmtree(directory, ignore_errors=True)
        except:
            print_exception()
        try:
            os.makedirs(directory, exist_ok=True)
        except:
            print_exception()
        if gui:
            cfg.main_window.hud.done()


# def kill_task_queue(task_queue):
#     '''End task queue multiprocessing tasks and delete a task queue object'''
#     try: task_queue.end_tasks()
#     except: print_exception()
#     task_queue.stop()
#     del task_queue

def show_status_report(results, dt):
    if results[2] > 0:
        cfg.main_window.hud(f'  Succeeded    = {results[0]}')
        if results[1] > 0:
            cfg.main_window.warning(f'  Queued       = {results[1]}')
        else:
            cfg.main_window.hud(f'  Queued       = {results[1]}')
        cfg.main_window.err(f'  Failed       = {results[2]}')
        cfg.main_window.hud(f'  Time Elapsed = {dt:.4g}level')
    else:
        cfg.main_window.hud(f'  Succeeded    = {results[0]}')
        cfg.main_window.hud(f'  Queued       = {results[1]}')
        cfg.main_window.hud(f'  Failed       = {results[2]}')
        cfg.main_window.hud(f'  Time Elapsed = {dt:.4g}level')


def get_scale_key(scale_val) -> str:
    '''Create a key like "scale_#" from either an integer or a string'''
    s = str(scale_val)
    while s.startswith('scale_'):
        s = s[len('scale_'):]
    # return 'scale_' + level
    return 'level' + s


def get_scale_val(s) -> int:
    try:
        if type(s) == type(1):
            return s
        else:
            return int(s[1:])
    except:
        logger.warning('Unable to return level value')


def do_scales_exist() -> bool:
    '''Checks whether any stacks of scaled images exist'''
    try:
        if any(d.startswith('scale_') for d in os.listdir(cfg.data['data']['series_path'])):
            return True
        else:
            return False
    except:
        pass


def get_scales_with_generated_alignments(scales) -> list:
    # logger.info('called by %level' % inspect.stack()[1].function)
    l = []
    for s in scales:
        if exist_aligned_zarr(s):
            l.append(s)
    return l


def exist_aligned_zarr(scale: str) -> bool:
    '''Returns boolean based on whether arg level is aligned '''
    caller = inspect.stack()[1].function
    logger.info('called by %s' % inspect.stack()[1].function)
    if cfg.data:
        zarr_path = os.path.join(cfg.data.dest(), 'zarr', 'level' + str(get_scale_val(scale)))
        if not os.path.isdir(zarr_path):
            # logger.critical(f"Path Not Found: {zarr_path}")
            result = False
        elif not os.path.exists(os.path.join(zarr_path, '.zattrs')):
            # logger.critical(f"Path Not Found: {os.path.join(zarr_path, '.zattrs')}")
            result = False
        elif not os.path.exists(os.path.join(zarr_path, '.zarray')):
            # logger.critical(f"Path Not Found: {os.path.join(zarr_path, '.zarray')}")
            result = False
        elif not os.path.exists(os.path.join(zarr_path, '0.0.0')):
            # logger.critical(f"Path Not Found: {os.path.join(zarr_path, '0.0.0')}")
            result = False
        else:
            result = True
        logger.critical('Returning Result %r for level %s' % (result, scale))
        return result
    else:
        logger.warning(f'called by {caller} but there is no cfg.data!')



def reorder_tasks(task_list, z_stride) -> list:
    tasks = []
    for x in range(0, z_stride):  # chunk z_dim
        tasks.extend(task_list[x::z_stride])
        # append_list = task_list[x::z_stride]
        # for t in append_list:
        #     tasks.append(t)
    return tasks


def imgToNumpy(img):
    '''Proper way to convert between images and numpy arrays as of PIL 1.1.6'''
    return np.array(img)


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


class TimeoutException(Exception): pass


def register_login():

    if is_tacc():
        tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        node = platform.node()
        user = getpass.getuser()

        login_txt = f"-----------------login------------------\n" \
                    f"Time        : {tstamp}\n" \
                    f"Node        : {platform.node()}\n" \
                    f"User        : {user}\n\n" \

        fn = f"{node}_{user}.log"
        location = "/work/08507/joely/ls6/log_db"
        of = os.path.join(location, fn)
        # sp.call(['chmod', '0666', of])
        with open(of, 'a+') as f:
            f.write(login_txt)
        os.chmod(of, 0o666)



def addLoggingLevel(levelName, levelNum, methodName=None):
    """
    https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility/35804945#35804945

    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
       raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
       raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
       raise AttributeError('{} already defined in logger class'.format(methodName))

    # This method is based on answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)
    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


def print_exception(extra=''):
    tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    exi = sys.exc_info()

    if 'MemoryError' in str(exi[0]):
        logger.critical('Memory Error!!')
        # cfg.main_window.memory()
        # try:
        #     cfg.main_window.mem()
        # except:
        #     print_exception()

    txt = f"[{inspect.stack()[1].function}] [{tstamp}]\nError Type/Value : {exi[0]} {exi[1]}\n{traceback.format_exc()}{extra}"
    logger.warning(txt)

    # if cfg.data:
    #     lf = os.path.join(cfg.data.dest(), 'logs', 'exceptions.log')
    #     file = Path(lf)
    #     file.touch(exist_ok=True)
    #     with open(lf, 'a+') as f:
    #         f.write('\n' + txt)

    if is_tacc():
        node = platform.node()
        user = getpass.getuser()
        fn = f"{node}_{user}.log"
        log_to_db = f"----------------------------------------\n" \
                    f"Time        : {tstamp}\n" \
                    f"Node        : {platform.node()}\n" \
                    f"User        : {user}\n" \
                    f"Exception   : \n" \
                    f"{txt}\n"
        fn = f"{node}_{user}.log"
        location = "/work/08507/joely/ls6/log_db"
        of = os.path.join(location, fn)
        with open(of, 'a+') as f:
            f.write(log_to_db)
        os.chmod(of, 0o666)


def get_img_filenames(path) -> list[str]:
    logger.debug('get_img_filenames:')
    logger.debug('Searching in Path: %s ' % path)
    imgs = [x for x in os.listdir(path) if os.path.splitext(x)[1] in (
        '.tif',
        '.tiff',
        '.bmp',
        '.jpg',
        '.jpeg',
        '.png',
        '.eps'
    )]
    logger.debug('Returning: %s' % str(imgs))
    return natural_sort(imgs)


def rename_layers(use_scale, al_dict):
    logger.info('rename_layers:')
    source_dir = os.path.join(cfg.data.dest(), use_scale, "img_src")
    for layer in al_dict:
        image_name = None
        if 'base' in layer['images'].keys():
            image = layer['images']['base']
            try:
                image_name = os.path.basename(image['path'])
                destination_image_name = os.path.join(source_dir, image_name)
                shutil.copyfile(image.image_file_name, destination_image_name)
            except:
                logger.warning('Something went wrong with renaming the alignment layers')
                pass



def verify_image_file(path: str) -> str:
    '''Tries to determine the filetype of an image using the Python standard library.
    Returns a string.'''''
    imhgr_type = imghdr.what(path)
    logger.info('verify_image_file | imhgr_type = ' % imhgr_type)
    return imhgr_type


def percentage(part, whole) -> str:
    percentage = 100 * float(part) / float(whole)
    return str(round(percentage, 2)) + "%"


def make_relative(file_path, proj_path):
    rel_path = os.path.relpath(file_path, start=os.path.split(proj_path)[0])
    return rel_path


def make_absolute(file_path, proj_path):
    abs_path = os.path.join(os.path.split(proj_path)[0], file_path)
    return abs_path


def initLogFiles(location):
    try:
        logpath = os.path.join(location, 'logs')
        os.makedirs(logpath, exist_ok=True)
        open(os.path.join(logpath, 'exceptions.log'), 'a').close()
        open(os.path.join(logpath, 'thumbnails.log'), 'a').close()
        open(os.path.join(logpath, 'recipemaker.log'), 'a').close()
        open(os.path.join(logpath, 'swim.log'), 'a').close()
        open(os.path.join(logpath, 'multiprocessing.log'), 'a').close()
    except:
        exi = sys.exc_info()
        logger.warning(f"[{exi[0]} / {exi[1]}] Initializing log files triggered an exception")


def create_project_directories(destination, scales, gui=True) -> None:
    caller = inspect.stack()[1].function
    logger.info(f'Creating Project Structure Directories for destination {destination}, scales: {scales}...')

    for scale in scales:
        if gui:
            cfg.mw.tell('Creating directories for %s...' % scale)
        subdir_path = os.path.join(destination, scale)
        src_path = os.path.join(subdir_path, 'img_src')
        aligned_path = os.path.join(subdir_path, 'img_aligned')
        bias_data_path = os.path.join(subdir_path, 'bias_data')
        history_path = os.path.join(subdir_path, 'history')
        tmp_path = os.path.join(subdir_path, 'tmp')
        signals_path = os.path.join(subdir_path, 'signals')
        matches_path = os.path.join(subdir_path, 'matches')

        try:
            os.makedirs(subdir_path, exist_ok=True)
            os.makedirs(src_path, exist_ok=True)
            os.makedirs(aligned_path, exist_ok=True)
            os.makedirs(bias_data_path, exist_ok=True)
            os.makedirs(history_path, exist_ok=True)
            os.makedirs(tmp_path, exist_ok=True)
            os.makedirs(signals_path, exist_ok=True)
            os.makedirs(matches_path, exist_ok=True)
        except:
            print_exception()
            logger.warning('Exception Raised While Creating Directory Structure')




def is_not_hidden(path):
    return not path.name.startswith(".")


def print_project_tree() -> None:
    '''Recursive function that lists datamodel directory contents as a tree.'''
    paths = Treeview.make_tree(Path(cfg.data.location))
    for path in paths:
        print(path.displayable())


def module_debug() -> None:
    '''Simple helper function to debug available modules.'''
    import sys, os
    modulenames = set(sys.modules) & set(globals())
    allmodules = [sys.modules[name] for name in modulenames]
    logger.info('========================================================' +
                '_____________________MODULE DEBUG_______________________' +
                'script       : ' + str(logger.info(sys.argv[0])) + 'running in   :' +
                str(os.path.dirname(os.path.realpath(__file__))) + 'sys.pathc    : ' + str(sys.path) +
                'module names : ' + str(modulenames) + 'allmodules   : ' + str(allmodules) +
                'In module products sys.path[0] = ' + str(sys.path[0]) + '__package__ = ' +
                str(__package__) + '========================================================')

    # Courtesy of https://github.com/wimglenn
    import sys
    try:
        old_import = builtins.__import__

        def my_import(name, *args, **kwargs):
            if name not in sys.modules:  logger.info('importing --> {}'.format(name))
            return old_import(name, *args, **kwargs)

        builtins.__import__ = my_import
    except:
        pass


def print_scratch(msg):
    with open('~/Logs/scratchlog', "w") as f:
        f.write(str(msg))




def update_skip_annotations():
    logger.info('update_skip_annotations:')
    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    remove_list = []
    add_list = []
    for sk, scale in cfg.data['data']['scales'].items():
        for layer in scale['stack']:
            layer_num = scale['stack'].index(layer)
            for ik, im in layer['images'].items():
                if not 'metadata' in im:
                    im['metadata'] = {}
                if not 'annotations' in im['metadata']:
                    im['metadata']['annotations'] = []
                ann = im['metadata']['annotations']
                if layer['skipped']:
                    # Check and set as needed
                    already_skipped = False
                    for a in ann:
                        if a.startswith('skipped'):
                            already_skipped = True
                            break
                    if not already_skipped:
                        add_list.append((sk, layer_num, ik))
                        ann.append('skipped(1)')
                else:
                    # Remove all "skipped"
                    for a in ann:
                        if a.startswith('skipped'):
                            remove_list.append((sk, layer_num, ik))
                            ann.remove(a)
    # for item in remove_list:
    #     interface.print_debug(80, "Removed skipped from " + str(item))
    # for item in add_list:
    #     interface.print_debug(80, "Added skipped to " + str(item))


class SwiftirException:
    def __init__(self, project_file, message):
        self.project_file = project_file
        self.message = message

    def __str__(self):
        return self.message


ZARR_AXES_3D = ["z", "y", "x"]
DEFAULT_ZARR_STORE = zarr.NestedDirectoryStore


def create_paged_tiff():
    dest = cfg.data.dest()
    for scale in cfg.data.scales:
        path = os.path.join(dest, scale, 'img_src')
        of = os.path.join(dest, scale + '_img_src.tif')
        files = glob(path + '/*.tif')
        image_sequence = tifffile.imread(files)
    '''
    image_sequence.shape
    Out[29]: (34, 4096, 4096)
    '''


def caller_name(skip=2):
    """Get a name of a caller in the format module.class.method

       `skip` specifies how many levels of stack to skip while getting caller
       name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

       An empty string is returned if skipped levels exceed stack height

       source: https://stackoverflow.com/questions/2654113/how-to-get-the-callers-method-name-in-the-called-method
    """
    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return ''
    parentframe = stack[start][0]

    name = []
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    # TODO(techtonik): consider using __main__
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append(codename)  # function or a method

    ## Avoid circular refs and frame leaks
    #  https://docs.python.org/2.7/library/inspect.html#the-interpreter-stack
    del parentframe, stack

    return ".".join(name)


def recursive_key_values(dictionary):
    """recursive_key_values.
        Print all keys and values anywhere in a dictionary
    Args:
        dictionary: any dictionary
    Returns:
        tuple:
    """
    for key, value in dictionary.items():
        i = 0
        if type(value) is str:
            yield (key, value)
        elif type(value) is dict:
            yield from recursive_key_values(value)
        elif type(value) in (list, tuple, set):
            for seq_item in value:
                yield from recursive_key_values({f"{key}_{str(i)}": seq_item})
                i = i + 1
        else:
            yield (key, str(value))


def dict_from_two_lists(keys: list, values: list) -> dict:
    if not len(keys) == len(values):
        raise ValueError("List of keys must have the same length as the list of values!")

    return dict(zip(keys, values))



from typing import Dict, Any
import hashlib
import json

def dict_hash(dictionary: Dict[str, Any]) -> str:
    """
    MD5 hash of a dictionary.
    source: https://www.doc.ic.ac.uk/~nuric/coding/how-to-hash-a-dictionary-in-python.html
    """
    dhash = hashlib.md5()
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.hexdigest()


# General-purpose solution that can process large files
def file_hash(file_path):
    # https://stackoverflow.com/questions/64994057/python-image-hashing
    # https://stackoverflow.com/questions/22058048/hashing-a-file-in-python

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            data = f.read(65536) # arbitrary number to reduce RAM usage
            if not data:
                break
            sha256.update(data)

    return sha256.hexdigest()

# def show_mp_queue_results(task_queue, dt):
#
#     logger.info('Checking Status of Tasks...')
#     n_tasks = len(task_queue.task_dict.keys())
#     n_success, n_queued, n_failed = 0, 0, 0
#     for k in task_queue.task_dict.keys():
#         task_item = task_queue.task_dict[k]
#         if task_item['statusBar'] == 'completed':
#             logger.debug('\nProcessDone:')
#             logger.debug('   CMD:    %level' % (str(task_item['cmd'])))
#             logger.debug('   ARGS:   %level' % (str(task_item['args'])))
#             logger.debug('   STDERR: %level\n' % (str(task_item['stderr'])))
#             n_success += 1
#         elif task_item['statusBar'] == 'queued':
#             logger.warning('\nQueued:')
#             logger.warning('   CMD:    %level' % (str(task_item['cmd'])))
#             logger.warning('   ARGS:   %level' % (str(task_item['args'])))
#             logger.warning('   STDERR: %level\n' % (str(task_item['stderr'])))
#             n_queued += 1
#         elif task_item['statusBar'] == 'task_error':
#             logger.warning('\nTask Error:')
#             logger.warning('   CMD:    %level' % (str(task_item['cmd'])))
#             logger.warning('   ARGS:   %level' % (str(task_item['args'])))
#             logger.warning('   STDERR: %level\n' % (str(task_item['stderr'])))
#             n_failed += 1
#
#     # cfg.main_window.hud.post('  Time Elapsed    : %.2f seconds' % dt)
#
#     if n_failed > 0:
#         # cfg.main_window.hud.post('  Tasks Completed : %d' % n_success, logging.WARNING)
#         # cfg.main_window.hud.post('  Tasks Queued    : %d' % n_queued, logging.WARNING)
#         # cfg.main_window.hud.post('  Tasks Failed    : %d' % n_failed, logging.WARNING)
#         # cfg.main_window.warn('Succeeded/Queued/Failed : %d/%d/%d %.2fs' % (n_success, n_queued, n_failed, dt))
#         # cfg.main_window.warn(f'Succeeded={n_success} Queued={n_queued} Failed={n_failed} {dt:.2f}level')
#         cfg.main_window.hud(f'  Succeeded    = {n_success}')
#         if n_queued > 0:
#             cfg.main_window.warning(f'  Queued       = {n_queued}')
#         else:
#             cfg.main_window.hud(f'  Queued       = {n_queued}')
#         cfg.main_window.err(f'  Failed       = {n_failed}')
#         cfg.main_window.hud(f'  Time Elapsed = {dt:.2f}level')
#     else:
#         # cfg.main_window.hud.post('  Tasks Completed : %d' % n_success, logging.INFO)
#         # cfg.main_window.hud.post('  Tasks Queued    : %d' % n_queued, logging.INFO)
#         # cfg.main_window.hud.post('  Tasks Failed    : %d' % n_failed, logging.INFO)
#         # cfg.main_window.hud('Succeeded/Queued/Failed : %d/%d/%d %.2fs' % (n_success,n_queued,n_failed, dt))
#         # cfg.main_window.hud(f'  Succeeded={n_success} Queued={n_queued} Failed={n_failed} {dt:.2f}level')
#         cfg.main_window.hud(f'  Succeeded    = {n_success}')
#         cfg.main_window.hud(f'  Queued       = {n_queued}')
#         cfg.main_window.hud(f'  Failed       = {n_failed}')
#         cfg.main_window.hud(f'  Time Elapsed = {dt:.2f}level')

# def load():
#     try:
#         with open('datamodel.json', 'r') as f:
#             self.previewmodel.todos = json.load(f)
#     except Exception:
#         pass


#
# # @delayed
# def _rmtree_after_delete_files(path: str, dependency: Any):
#     rmtree(path)
#
#
# def rmtree_parallel(
#     path: Union[str, Path], branch_depth: int = 1, compute: bool = True
# ):
#     branches = glob(os.path.join(path, *("*",) * branch_depth))
#     deleter = os.remove
#     files = list_files_parallel(branches)
#     deleted_files = bag.from_sequence(files).map(deleter)
#     result = _rmtree_after_delete_files(path, dependency=deleted_files)
#
#     if compute:
#         return result.compute(scheduler="threads")
#     else:
#         return result
#
# def list_files_parallel(
#     paths: Union[Sequence[Union[str, Path]], str, Path],
#     followlinks=False,
#     compute: bool = True,
# ):
#     result = []
#     delf = delayed(lambda p: list_files(p, followlinks=followlinks))
#
#     if isinstance(paths, str) or isinstance(paths, Path):
#         result = bag.from_delayed([delf(paths)])
#     elif isinstance(paths, Sequence):
#         result = bag.from_delayed([delf(p) for p in paths])
#     else:
#         raise TypeError(f"Input must be a string or a sequence, not {cur_method(paths)}")
#
#     if compute:
#         return result.compute(scheduler="threads")
#     else:
#         return result
#
#
# def list_files(
#     paths: Union[Sequence[Union[str, Path]], str, Path], followlinks: bool = False):
#     if isinstance(paths, str) or isinstance(paths, Path):
#         if os.path.isdir(paths):
#             return list(
#                 tz.concat(
#                     (os.path.join(dp, f) for f in fn)
#                     for dp, dn, fn in os.walk(paths, followlinks=followlinks)
#                 )
#             )
#         elif os.path.isfile(paths):
#             return [paths]
#         else:
#             raise ValueError(f"Input argument {paths} is not a path or a directory")
#
#     elif isinstance(paths, Sequence):
#         sortd = sorted(paths, key=os.path.isdir)
#         files, dirs = tuple(tz.partitionby(os.path.isdir, sortd))
#         return list(tz.concatv(files, *tz.map(list_files, dirs)))


# NOTE: this is called right after importing base images
# def update_linking_callback():
#     logger.info('Updating linking callback | update_linking_callback...')
#     link_reference_sections()
#     logger.info('Exiting update_linking_callback()')
#
#
# def update_skips_callback(new_state):
#     logger.info('Updating skips callback | update_skips_callback...')
#
#     # Update all of the annotations based on the skipped values
#     copy_skips_to_all_scales()
#     # update_skip_annotations()  # This could be done via annotations, but it'level easier for now to hard-code into main_window.py
#     logger.info("Exiting update_skips_callback(new_state)")


# def mouse_down_callback(role, screen_coords, image_coords, bBlink):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     # logger.info("mouse_down_callback was called but there is nothing to do.")
#     return  # monkeypatch
#
#
# def mouse_move_callback(role, screen_coords, image_coords, bBlink):
#     # global match_pt_mode
#     # if match_pt_mode.get_value():
#     return #monkeypatch #jy
#
#     # # logger.info("view_match_crop.get_value() = ", view_match_crop.get_value())
#     # if view_match_crop.get_value() == 'Match':
#     #     return (True)  # Lets the framework know that the move has been handled
#     # else:
#     #     return (False)  # Lets the framework know that the move has not been handled

# def notyet():
#     logger.info('notyet() was called')
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + str(skipped.value)) #skipped
#     # interface.print_debug(0, "Function not implemented yet. Skip = " + main_window.cbSkip.isChecked())

# def crop_mode_callback():
#     return
#     # return view_match_crop.get_value()


# def print_dat_files() -> None:
#     '''Prints the .dat files for the current level, if they exist .'''
#     bias_data_path = os.path.join(cfg.datamodel['data']['destination_path'], cfg.datamodel.level, 'bias_data')
#     if are_images_imported():
#         logger.info('Printing .dat Files')
#         try:
#             logger.info("_____________________BIAS DATA_____________________")
#             logger.info("Scale %d____________________________________________" % get_scale_val(cfg.datamodel.level))
#             with open(os.path.join(bias_data_path, 'snr_1.dat'), 'r') as f:
#                 snr_1 = f.read()
#                 logger.info('snr_1               : %level' % snr_1)
#             with open(os.path.join(bias_data_path, 'bias_x_1.dat'), 'r') as f:
#                 bias_x_1 = f.read()
#                 logger.info('bias_x_1            : %level' % bias_x_1)
#             with open(os.path.join(bias_data_path, 'bias_y_1.dat'), 'r') as f:
#                 bias_y_1 = f.read()
#                 logger.info('bias_y_1            : %level' % bias_y_1)
#             with open(os.path.join(bias_data_path, 'bias_rot_1.dat'), 'r') as f:
#                 bias_rot_1 = f.read()
#                 logger.info('bias_rot_1          : %level' % bias_rot_1)
#             with open(os.path.join(bias_data_path, 'bias_scale_x_1.dat'), 'r') as f:
#                 bias_scale_x_1 = f.read()
#                 logger.info('bias_scale_x_1      : %level' % bias_scale_x_1)
#             with open(os.path.join(bias_data_path, 'bias_scale_y_1.dat'), 'r') as f:
#                 bias_scale_y_1 = f.read()
#                 logger.info('bias_scale_y_1      : %level' % bias_scale_y_1)
#             with open(os.path.join(bias_data_path, 'bias_skew_x_1.dat'), 'r') as f:
#                 bias_skew_x_1 = f.read()
#                 logger.info('bias_skew_x_1       : %level' % bias_skew_x_1)
#             with open(os.path.join(bias_data_path, 'bias_det_1.dat'), 'r') as f:
#                 bias_det_1 = f.read()
#                 logger.info('bias_det_1          : %level' % bias_det_1)
#             with open(os.path.join(bias_data_path, 'afm_1.dat'), 'r') as f:
#                 afm_1 = f.read()
#                 logger.info('afm_1               : %level' % afm_1)
#             with open(os.path.join(bias_data_path, 'c_afm_1.dat'), 'r') as f:
#                 c_afm_1 = f.read()
#                 logger.info('c_afm_1             : %level' % c_afm_1)
#         except:
#             logger.info('Is this level aligned? No .dat files were found at this level.')
#             pass
