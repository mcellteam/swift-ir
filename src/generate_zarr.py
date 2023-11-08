#!/usr/bin/env python3
import copy
import logging
import multiprocessing as mp
import os
import shutil
import subprocess as sp
import time
from datetime import datetime
from pprint import pformat

import imageio.v3 as iio
import neuroglancer as ng
import numpy as np
import tqdm
import zarr

import libtiff
import numcodecs
numcodecs.blosc.use_threads = False

from qtpy.QtCore import Signal, QObject, QMutex

import src.config as cfg
from src.helpers import get_bindir, print_exception, get_core_count
from src.funcs_image import ImageSize
from src.thumbnailer import Thumbnailer
from src.swiftir import applyAffine

__all__ = ['ZarrWorker']

logger = logging.getLogger(__name__)


class ZarrWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    initPbar = Signal(tuple) # (# tasks, description)
    hudMessage = Signal(str)
    hudWarning = Signal(str)

    def __init__(self, dm, renew=False, ignore_cache=False):
        super().__init__()
        logger.info('Initializing...')
        self.dm = dm
        self.renew = renew
        self.ignore_cache = ignore_cache
        self._running = True
        self._mutex = QMutex()

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
        print(f"====> Running Background Thread ====>")
        self.generate()
        print(f"<==== Terminating Background Thread <====")
        self.finished.emit() #Important!

    def generate(self):

        logger.critical(f"\n\nPerforming apply cumulative "
                        f"transformation as Zarr protocol...\n")
        dm = self.dm
        dm.set_stack_cafm()
        grp = os.path.join(dm.data_location, 'zarr', 's%d' % dm.lvl())
        zarrExist = os.path.exists(os.path.join(grp, '.zattrs'))
        z = zarr.open(grp)
        make_all = len(list(dm.zattrs.keys())) == 0

        '''If it is an align all, then we want to set and store bounding box / poly bias'''
        outputHash = hash(HashableDict(dm['level_data'][dm.level]['output_settings']))
        z.attrs['output_settings_hash'] = outputHash
        z.attrs['output_settings'] = copy.deepcopy(dm['level_data'][dm.level]['output_settings'])

        if not zarrExist:
            self.indexes = list(range(len(dm)))
        else:
            self.indexes = []
            for i in range(len(dm)):
                comports = dm.zarrCafmHashComports(l=i)
                if make_all or self.ignore_cache:
                    self.indexes.append(i)
                else:
                    if comports:
                        logger.info(f"Cache hit {dm.cafmHash(l=i)}! "
                                    f"Zarr data correct at index {i}.")
                    else:
                        self.indexes.append(i)


        if not len(self.indexes):
            logger.info("\n\nZarr is in sync.\n")
            self.finished.emit(); return


        if dm.has_bb():
            # Note: now have got new cafm'level -> recalculate bounding box
            rect = dm.set_calculate_bounding_rect()  # Only after SetStackCafm
        else:
            w, h = dm.image_size()
            rect = [0, 0, w, h]  # might need to swap w/h for Zarr
        logger.info(f'Bounding Box : {dm.has_bb()}, Bias: {dm.poly_order}\n')

        tasks = []
        to_reduce = []
        for i in self.indexes:
            ifp = dm.path(l=i)  # input file path
            ofp = dm.path_aligned_cafm(l=i)  # output file path
            to_reduce.append((ofp, dm.path_aligned_cafm_thumb(l=i)))
            if not os.path.exists(ofp):
                os.makedirs(os.path.dirname(ofp), exist_ok=True)
                cafm = dm['stack'][i]['levels'][dm.level]['cafm']
                tasks.append([ifp, ofp, rect, cafm, 128])
            else:
                logger.info(f'Cache hit (transformed image): {ofp}')

        self.cpus = get_core_count(dm, len(tasks))

        desc = f"Generate Cumulative Transformation Images"
        t, *_ = self.run_multiprocessing(run_mir, tasks, desc)

        scale_factor = dm.images['thumbnail_scale_factor'] // dm.lvl()
        Thumbnailer(dm).reduce_tuples(to_reduce, scale_factor=scale_factor)

        if not self.running():
            self.finished.emit(); return

        # path_mini_zarr = os.path.join(dm.data_location, 'zarr_reduced', level)
        # if len(self.indexes) == len(dm):
        #     if os.path.exists(path_mini_zarr):
        #         try:
        #             shutil.rmtree(path_mini_zarr)
        #         except:
        #             print_exception()

        siz = ImageSize(dm.path_aligned_cafm_thumb(l=1)) #Todo #Ugly

        # if not os.path.exists(path_mini_zarr):
        tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        shape = (len(dm), siz[1], siz[0])
        cname, clevel, chunkshape = dm.get_user_zarr_settings()
        chunkshape = (1,32,32)
        preallocate_zarr(dm=dm, name='zarr_reduced', group=dm.level, shape=shape,
                         cname=cname, clevel=clevel, chunkshape=chunkshape,
                         dtype='|u1', overwrite=True, attr=str(tstamp))

        if self.generateAnimations():
            logger.error(f"Something went wrong during generation GIF animations")
            print_exception()

        if not self.running():
            self.finished.emit(); return

        if self.generateMiniZarr():
            logger.error(f"Something went wrong during generation of reduced Zarr")
            print_exception()

        if not self.running():
            self.finished.emit(); return

        if self.renew:
            tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            shape = (len(dm), rect[3], rect[2])
            cname, clevel, chunkshape = dm.get_user_zarr_settings()
            preallocate_zarr(dm=dm, name='zarr', group=dm.level, shape=shape,
                             cname=cname, clevel=clevel, chunkshape=chunkshape,
                             dtype='|u1', overwrite=True, attr=str(tstamp))

        z = dm.get_zarr_transforming()
        tasks = []
        for i in self.indexes:
            src = dm.path_aligned_cafm(l=i)
            if os.path.exists(src):
                z.attrs[i] = (str(dm.ssSavedHash(l=i)), dm.cafmHash(l=i))
                task = [i, src, grp]
                tasks.append(task)
            else:
                logger.warning(f'TIFF Does Not Exist: {src}')

        if tasks:
            if ng.is_server_running():
                logger.info('Stopping Neuroglancer...')
                ng.server.stop()
            desc = f"Copy-convert to Zarr"
            t, *_ = self.run_multiprocessing(convert_zarr, tasks, desc)
            self.dm.t_convert_zarr = t
        else:
            self.dm.t_convert_zarr = 0.

        self.hudMessage.emit(f'<span style="color: #FFFF66;"><b>**** Process Complete ****</b></span>')
        self.finished.emit()


    def generate_single_animation(self, paths, of):
        try:
            ims = list(map(lambda f: iio.imread(f), paths))
            iio.imwrite(of, ims, format='GIF', duration=1, loop=0)
            return 0
        except:
            print_exception()
            logger.error(f'Th e following GIF Frame(s) Could Not Be Read as Image:\n{paths}')
            return 1

    def generateAnimations(self):
        err = 0
        for i in self.indexes:
            # if i == self.dm.first_included(): #1107-
            #     continue
            of = self.dm.path_cafm_gif(l=i)
            # os.makedirs(os.path.dirname(of), exist_ok=True)
            p1 = self.dm.path_aligned_cafm_thumb(l=i)
            p2 = self.dm.path_aligned_cafm_thumb_ref(l=i)
            try:
                o = self.generate_single_animation([p1, p2], of)
            except:
                err += 1
                print_exception(extra=f"# errors: {err}")
        return err > 0


    def generateMiniZarr(self):
        logger.info('')
        z_path = os.path.join(self.dm.data_location, 'zarr_reduced', self.dm.level)
        tasks = []
        for i in self.indexes:
            # if i == self.dm.first_included(): #1107-
            #     continue
            p = self.dm.path_aligned_cafm_thumb_ref(l=i)
            tasks.append([i, p, z_path])
        desc = f"Generate Reduced-Size Zarr"
        t, n, failed, _ = self.run_multiprocessing(convert_zarr, tasks, desc)
        return failed > 0


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
        fail = sum(results)
        succ = len(results) - fail
        dt = time.time() - t0
        self.print_summary(dt, succ, fail, desc)
        print(f"<---- {desc} <----")
        return (dt, succ, fail, results)

    def print_summary(self, dt, succ, fail, desc):

        if fail:
            self.hudWarning(f"\n"
                         f"\n//  Summary  //  {desc}  //"
                         f"\n//  RUNTIME   : {dt:.3g}s"
                         f"\n//  SUCCESS   : {succ}"
                         f"\n//  FAILED    : {fail}"
                         f"\n")
        else:
            self.hudMessage(f"\n"
                        f"\n//  Summary  //  {desc}  //"
                        f"\n//  RUNTIME   : {dt:.3g}s"
                        f"\n//  SUCCESS   : {succ}"
                        f"\n//  FAILED    : {fail}"
                        f"\n")



def set_zarr_attribute(z, key, value):
    z.attrs[key] = value



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
    # exit_code = cmd_proc.wait() #1031+
    # type(cmd_proc.returncode) = int
    # type(cmd_proc.wait()) = int
    return ({'out': cmd_stdout, 'err': cmd_stderr, 'rc': cmd_proc.returncode})


def run_mir(task):
    in_fn = task[0]
    out_fn = task[1]
    rect = task[2]
    cafm = task[3] # type <class 'list'>
    border = task[4]

    # Todo get exact median greyscale value for each image in list, for now just use 128

    app_path = os.path.split(os.path.realpath(__file__))[0]
    mir_c = os.path.join(app_path, 'lib', get_bindir(), 'mir')

    bb_x, bb_y = rect[2], rect[3]
    afm = np.array([cafm[0][0], cafm[0][1], cafm[0][2], cafm[1][0], cafm[1][1], cafm[1][2]],
                   dtype='float64').reshape((-1, 3))
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
    rc = o['rc']
    # logger.critical(pformat(o))
    # return 0
    return rc


def convert_zarr(task):
    '''
    @param 1: ID int
    @param 2: file path str
    @param 3: zarr path str
    '''
    try:
        _id = task[0]
        _f = task[1]
        _path = task[2]
        store = zarr.open(_path)
        # data = libtiff.TIFF.open(_f).read_image()[:, ::-1]  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        data = iio.imread(_f)  # store: <zarr.core.Array (19, 1244, 1130) uint8>
        # os.remove(_f)
        # shutil.rmtree(os.path.dirname(_f), ignore_errors=True) #1102-
        store[_id, :, :] = data
        return 0
    except Exception as e:
        print(e)
        return 1


def preallocate_zarr(dm, name, group, shape, cname, clevel, chunkshape, dtype, overwrite, attr=None):
    '''zarr.blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']'''
    logger.info("\n\n--> preallocate -->\n")
    cname, clevel, chunkshape = dm.get_user_zarr_settings()
    src = os.path.abspath(dm.data_location)
    path_zarr = os.path.join(src, name)
    path_out = os.path.join(path_zarr, group)
    logger.info(f'allocating {name}/{group}...')

    if os.path.exists(path_out) and (overwrite == False):
        logger.warning('Overwrite is False - Returning')
        return
    output_text = f'\n  Zarr root : {os.path.join(os.path.basename(src), name)}' \
                  f'\n      group :   └ {group}({name}) {dtype} {cname}/{clevel}' \
                  f'\n      shape : {str(shape)} ' \
                  f'\n      chunk : {chunkshape}'

    try:
        if overwrite and os.path.exists(path_out):
            logger.info(f'Removing {path_out}...')
            shutil.rmtree(path_out, ignore_errors=True)
        # synchronizer = zarr.ThreadSynchronizer()
        # arr = zarr.group(store=path_zarr_transformed, synchronizer=synchronizer) # overwrite cannot be set to True here, will overwrite entire Zarr
        arr = zarr.group(store=path_zarr)
        compressor = numcodecs.Blosc(cname=cname, clevel=clevel) if cname in ('zstd', 'zlib', 'gzip') else None

        logger.info(f"\n"
                    f"  group      : {group}\n"
                    f"  shape      : {shape}\n"
                    f"  chunkshape : {chunkshape}\n"
                    f"  dtype      : {dtype}\n"
                    f"  compressor : {compressor}\n"
                    f"  overwrite  : {overwrite}")

        # arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite, synchronizer=synchronizer)
        arr.zeros(name=group, shape=shape, chunks=chunkshape, dtype=dtype, compressor=compressor, overwrite=overwrite)
        # write_metadata_zarr_multiscale()
        if attr:
            arr.attrs['attribute'] = attr
    except:
        print_exception()
        logger.warning('Zarr Preallocation Encountered A Problem')
    else:
        # cfg.main_window.hud.done()
        logger.info(output_text)
    logger.info(f"\n\n<-- preallocate <--\n")


class HashableDict(dict):
    def __hash__(self):
        # return abs(hash(str(sorted(self.items()))))
        return abs(hash(str(sorted(self.items()))))

