#!/usr/bin/env python3
"""
Joel Yancey
2021-11-22 v1
2022-01-18 v2

Notes:
    * script depends on glanceem_utils.py functions for scale pyramid functionality. keep files in the same directory.
        * daisy
            * written by Funke Lab at Janelia
            * source: https://github.com/funkelab/daisy
            * Daisy docs are inordinately hard to track down, so linked here
                * v0.1
                    * https://daisy-python.readthedocs.io/en/latest/appendix.html
                    * https://readthedocs.org/projects/daisy-python/downloads/pdf/latest/
                * v0.2
                    * https://daisy-docs.readthedocs.io/en/latest/api.html
                    * release notes: https://daisy-docs.readthedocs.io/en/latest/release.html
                        * uses tornado instead of dask
                        * Python’s asyncio capability as the sole backend for Tornado
                        * Python 3.5 and lower NOT supported
    * other dependencies:
        * zarr (https://zarr.readthedocs.io/en/stable/)
        * tifffile (https://pypi.org/project/tifffile/)
        * dask (https://docs.dask.org/en/latest/)
            * dask.diagnostics docs: https://docs.dask.org/en/stable/diagnostics-local.html
            * NOTE: when workers and threads per worker are NOT set -> Dask optimizes thread concurrency automatically
        * numcodecs (https://pypi.org/project/numcodecs/)
    *

EXAMPLE USAGE

MINIMAL
./make_zarr.py volume_josef

VERBOSE
./make_zarr.py volume_josef -c '1,5332,5332' -cN 'zstd' -cL 1 -r '50,2,2' -w 8 -t 2

VERY VERBOSE
./make_zarr.py volume_josef --chunks '1,5332,5332' --cname 'zstd' --clevel 1 --resolution '50,2,2' --workers 8 --threads 2


* look into tradeoffs with rechunking
https://zarr.readthedocs.io/en/latest/tutorial.html#changing-chunk-shapes-rechunking

* transition to Mutable Mapping interface or other Zarr storage type
https://zarr.readthedocs.io/en/stable/api/storage.html

Nested Directory Store
Storage class using directories and files on a standard file system, with special handling for chunk keys so that
chunk files for multidimensional arrays are stored in a nested directory tree.
Safe to write in multiple threads or processes.

tifffile new fsspec implementation
https://github.com/cgohlke/tifffile

"""
import logging
logging.basicConfig(filename='make_zarr.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.debug('Logging to make_zarr.log...')

import zarr
from numcodecs import Blosc, Delta, LZMA, Zstd
# blosc.list_compressors() -> ['blosclz', 'lz4', 'lz4hc', 'zlib', 'zstd']
import codecs
import numcodecs
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse, os, sys, time, shutil, re, subprocess, json
from contextlib import redirect_stdout
from glanceem_utils import create_scale_pyramid, tiffs2zarr
from dask.distributed import Client, LocalCluster
#from dask.diagnostics import Profiler, ResourceProfiler, CacheProfiler
#from dask.diagnostics.profile_visualize import visualize
from dask.diagnostics import ProgressBar
import multiprocessing

# register dask progress bar globally
pbar = ProgressBar()
pbar.register()


if __name__ == '__main__':

    # PARSE COMMAND LINE INPUTS
    ap = argparse.ArgumentParser()

    # required arguments
    ap.add_argument('path', type=str, help='Source directory path')

    # optional arguments
    #ap.add_argument('-m', '--make_zarr', action="store_true", help='Make .zarr from source (source is not modifed)')
    #ap.add_argument('-f', '--force', default=True, type=int, help='Force overwrite if zarr exists (default: True)')
    ap.add_argument('-c', '--chunks', default='64,64,64', type=str, help="Chunk shape X,Y,Z (default: '64,64,64')")
    ap.add_argument('-d', '--destination', default='.', type=str, help="Destination dir (default: '.')")
    ap.add_argument('-s', '--scale_ratio', default='1,2,2', type=str, help="Scaling ratio for each axis (default: '1,2,2')")
    ap.add_argument('-nS', '--n_scales', default=4, help='Number of downscaled image arrays. (default: 4)')
    ap.add_argument('-cN', '--cname', default='zstd', type=str, help="Compressor [zstd,zlib,gzip] (default: 'zstd')")
    ap.add_argument('-cL', '--clevel', default=1, type=int, help='Compression level [0:9] (default: 1)')
    ap.add_argument('-r', '--resolution', default='50,2,2', type=str, help="Resolution of x dim (default: '50,2,2')")
    ap.add_argument('-w', '--workers', default=8, type=int, help='Number of workers (default: 8)')
    ap.add_argument('-t', '--threads', default=2, type=int, help='Number of threads per worker (default: 2)')
    ap.add_argument('-nC', '--no_compression', default=0, type=int, help='Do not compress. (default: 0)')
    # COMPRESSORS=blosc,zlib,gzip,lzma,zstd,lz4i
    # BLOSC_COMPRESSORS=blosclz,lz4,lz4hc,snappy,zlib,zstd
    # Compressor is only applied when making zarr.
    args = ap.parse_args()
    print('cli arguments:',args)
    src = Path(args.path)
    destination = args.destination
    chunks = [int(i) for i in args.chunks.split(',')]
    resolution = [int(i) for i in args.resolution.split(',')]
    scale_ratio = [int(i) for i in args.scale_ratio.split(',')]
    timestr = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    print("type(no_compression)",type(args.no_compression))

    no_compression = bool(int(args.no_compression))

    print("type(no_compression)", type(no_compression))

    print("no_compression: ", no_compression)

    print("Setting multiprocessing.set_start_method('fork', force=True)...")
    multiprocessing.set_start_method('fork', force=True)

    #f_out = "project.zarr"  # jy
    f_out = aligned_path_full = os.path.join(args.destination, 'project.zarr')
    store = zarr.NestedDirectoryStore('data/array.zarr')
    print('f_out                           :', f_out)

    if os.path.isdir(f_out):
        print('Deleting existing directory', f_out, '...')
        try:
            shutil.rmtree(f_out)
        except:
            print('Error while deleting directory', f_out)



    # INITIALIZE DASK CLIENT
    ###client = Client(processes=False) # force run as a single thread
    ###client = Client(n_workers=args.workers, threads_per_worker=args.threads, processes=True)
    # client = Client(n_workers=args.workers, threads_per_worker=args.threads, processes=False)
    # client
    #
    # cluster = LocalCluster()
    # cluster


    # CHECK IF DIRECTORIES ALREADY EXIST
    if not src.is_dir():
        print('Exiting: ' + sys.argv[1] + ' is not a directory.')
        sys.exit(2)

    if src.suffix == '.zarr':
        print('Exiting: Source path has .zarr suffix already, cannot make Zarr into Zarr.')
        sys.exit()

    print('Making Zarr from ' +  src.name + '...')
    #blosc.set_nthreads(args.threads)
    cname = str(args.cname)
    clevel = int(args.clevel)
    n_scales = int(args.n_scales)
    r = scale_ratio
    print(type(r))
    #ds_name = "zarr_data"
    ds_name = 'img_aligned_zarr'
    scale_ratio = [scale_ratio]
    [scale_ratio.append(r) for x in range(n_scales-1)]
    ### typical 'scale_ratio'... [[1, 2, 2], [1, 2, 2], [1, 2, 2], [1, 2, 2]]
    ### test case... scale_ratio = [[1,1,1]]

    component = 'zArray'
    print('Source directory                :', src)
    print('Loading file list...')
    filenames = sorted(list(Path(src).glob(r'*.tif')))
    n_imgs = len(filenames)
    if not no_compression:
        config_str = src.as_posix() + "_" + str(n_imgs) + 'imgs_multiscale' + str(n_scales) + \
                     '_chunksize' + str(chunks[0]) + 'x' + str(chunks[1]) + 'x' + str(chunks[2]) + \
                     '_' + cname + '-clevel' + str(clevel)
    if no_compression:
        config_str = src.as_posix() + "_" + str(n_imgs) + 'imgs_multiscale' + str(n_scales) + \
                     '_chunksize' + str(chunks[0]) + 'x' + str(chunks[1]) + 'x' + str(chunks[2]) + \
                     '_uncompressed'

    #f_out = config_str + ".zarr"
    #_out = "project.zarr"
    first_file = str(filenames[0])
    last_file = str(filenames[-1])

    # DUMP RUN INFO TO CONSOLE
    print('# images found                  :', n_imgs)
    print('First file                      :', first_file)
    print('Last file                       :', last_file)
    print('Target (Zarr) directory (f_out) :', f_out)
    print('Number of downscales            :', n_scales)
    print('Downscale ratio by axis         :', scale_ratio)
    print('Chunk shape                     :', chunks)
    print('Compression type                :', cname)
    print('Compression level               :', clevel)

    # CALL 'tiffs2zarr' ON SOURCE DIRECTORY
    print('Making Zarr from TIFs, using dask array intermediary for parallelization...')
    t = time.time()
    #tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), compressor=zarr.get_codec({'id': cname, 'level': clevel}))
    if not no_compression:
        if cname in ('zstd', 'zlib'):
            tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), compressor=Blosc(cname=cname, clevel=clevel), overwrite=True)

        else:
            #compressor = {'id': cname, 'level': clevel}
            # MIGHT NOT PASS IN cname, clevel
            tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), compression=cname, overwrite=True) #jy works by itself
            # tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), compression=compressor,overwrite=True)

            #tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), cname=cname, clevel=clevel, overwrite=True)
            #tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), compressor=compressor, overwrite=True)

    if no_compression:
        # MIGHT PASS IN 'None'
        tiffs2zarr(filenames, f_out + "/" + ds_name, tuple(chunks), compressor=None, overwrite=True)


    # NEUROGLANCER COMPATIBILITY
    ds = zarr.open(f_out + '/' + ds_name, mode='a')
    ds.attrs['offset'] = [0, 0, 0]
    ds.attrs['resolution'] = resolution
    ds.attrs['units'] = ['nm', 'nm', 'nm']
    ds.attrs['scales'] = scale_ratio
    ds.attrs['_ARRAY_DIMENSIONS'] = ['z', 'y', 'x']
    t_to_zarr = time.time() - t
    print('time elapsed: ', t_to_zarr, 'seconds')
    # print('Shutting down dask client...')
    # client.shutdown()

    # COMPUTE SCALE PYRAMID IN PLACE
    print('Generating scale pyramid in place...')
    t = time.time()
    print('scale_ratio=',scale_ratio)

    ###create_scale_pyramid(f_out, ds_name, scale_ratio, chunks, compressor=zarr.get_codec({'id': cname, 'level': clevel}))
    print('chunks=',chunks)
    print('no_compression: ', no_compression)
    if not no_compression:
        print("Using compression...")
        compressor = {'id': cname, 'level': clevel}
        create_scale_pyramid(f_out, ds_name, scale_ratio, chunks, compressor)

    if no_compression:
        print("NOT using compression...")
        compressor = None
        create_scale_pyramid(f_out, ds_name, scale_ratio, chunks, compressor=None)


    t_gen_scales = time.time() - t
    print('t_gen_scales: ',t_gen_scales,'s')
    print('\nMaking the Zarr is completed.\n')

    # CONSOLIDATE META-DATA
    #print("Consolidating meta data...")
    #zarr.consolidate_metadata(f_out)

    # COLLECT RUN DATA AND SAVE TO FILE
    print('Collecting run data...')
    #magic_info = str(magic.from_file(str(filenames[0])))
    data = {
        'time': timestr,
        'path_source': args.path,
        #'magic_info': magic_info,
        'n_imgs': n_imgs,
        'first_image': first_file,
        'last_image': last_file,
        'resolution': resolution,
        'path_zarr_target': f_out,
        'ds_name': ds_name,
        #'overwrite': args.force,
        't_to_zarr': t_to_zarr,
        't_gen_scales': t_gen_scales,
        'n_scales': n_scales,
        'scale_ratio': str(np.concatenate(scale_ratio)),
        'cname': cname,
        'clevel': clevel,
        'chunks': chunks,
    }
    #f_json = config_str + "_dump" +  ".json"
    #print("Dumping run details to ", f_json)
    #with open(f_json, mode='a') as f:
    #    json.dump(data, f, indent=4, skipkeys=True)


    #_txt = config_str + "_dump" + ".txt"
    f_txt = os.path.join(destination, "make_zarr_dump.txt")
    print("Dumping more run details to ", f_txt)
    with open(f_txt, mode='a') as f:
        with redirect_stdout(f):
            print(timestr)
            print("____ RESULTS - MAKE ZARR ____")
            print("source             :", args.path)
            print("output file        :", f_out)
            print("first file         :", first_file)
            print("last file          :", last_file)
            print("# images found     :", n_imgs)
            print("time make .zarr    :", t_to_zarr)
            print("time multiscales   :", t_gen_scales)
            print("n_scales           :", n_scales)
            print("scale_ratio        :", scale_ratio)
            print("chunks             :", chunks)
            print("dataset            :", ds_name)
            print("[cli arguments]")
            print(vars(args))
            print("[ds.info - s0 only]")
            print(ds.info)
            print("Done.\n")



    print("Exiting: Complete.")


"""
dask.config.config

# https://docs.dask.org/en/stable/configuration.html

Out[15]: 
{'temporary-directory': None,
 'tokenize': {'ensure-deterministic': False},
 'dataframe': {'shuffle-compression': None,
  'parquet': {'metadata-task-size-local': 512,
   'metadata-task-size-remote': 16}},
 'array': {'svg': {'size': 120},
  'slicing': {'split-large-chunks': None},
  'chunk-size': '128MiB',
  'rechunk-threshold': 4},
 'optimization': {'fuse': {'active': None,
   'ave-width': 1,
   'max-width': None,
   'max-height': inf,
   'max-depth-new-edges': None,
   'subgraphs': None,
   'rename-keys': True}},
 'distributed': {'version': 2,
  'scheduler': {'allowed-failures': 3,
   'bandwidth': 100000000,
   'blocked-handlers': [],
   'default-data-size': '1kiB',
   'events-cleanup-delay': '1h',
   'idle-timeout': None,
   'transition-log-length': 100000,
   'events-log-length': 100000,
   'work-stealing': True,
   'work-stealing-interval': '100ms',
   'worker-ttl': None,
   'pickle': True,
   'preload': [],
   'preload-argv': [],
   'unknown-task-duration': '500ms',
   'default-task-durations': {'rechunk-split': '1us', 'split-shuffle': '1us'},
   'validate': False,
   'dashboard': {'status': {'task-stream-length': 1000},
    'tasks': {'task-stream-length': 100000},
    'tls': {'ca-file': None, 'key': None, 'cert': None},
    'bokeh-application': {'allow_websocket_origin': ['*'],
     'keep_alive_milliseconds': 500,
     'check_unused_sessions_milliseconds': 500}},
   'locks': {'lease-validation-interval': '10s', 'lease-timeout': '30s'},
   'http': {'routes': ['distributed.http.scheduler.prometheus',
     'distributed.http.scheduler.info',
     'distributed.http.scheduler.json',
     'distributed.http.health',
     'distributed.http.proxy',
     'distributed.http.statics']},
   'allowed-imports': ['dask', 'distributed'],
   'active-memory-manager': {'start': False,
    'interval': '2s',
    'policies': [{'class': 'distributed.active_memory_manager.ReduceReplicas'}]}},
  'worker': {'blocked-handlers': [],
   'multiprocessing-method': 'spawn',
   'use-file-locking': True,
   'connections': {'outgoing': 50, 'incoming': 10},
   'preload': [],
   'preload-argv': [],
   'daemon': True,
   'validate': False,
   'resources': {},
   'lifetime': {'duration': None, 'stagger': '0 seconds', 'restart': False},
   'profile': {'interval': '10ms', 'cycle': '1000ms', 'low-level': False},
   'memory': {'recent-to-old-time': '30s',
    'rebalance': {'measure': 'optimistic',
     'sender-min': 0.3,
     'recipient-max': 0.6,
     'sender-recipient-gap': 0.1},
    'target': 0.6,
    'spill': 0.7,
    'pause': 0.8,
    'terminate': 0.95},
   'http': {'routes': ['distributed.http.worker.prometheus',
     'distributed.http.health',
     'distributed.http.statics']}},
  'nanny': {'preload': [],
   'preload-argv': [],
   'environ': {'MALLOC_TRIM_THRESHOLD_': 65536,
    'OMP_NUM_THREADS': 1,
    'MKL_NUM_THREADS': 1}},
  'client': {'heartbeat': '5s', 'scheduler-info-interval': '2s'},
  'deploy': {'lost-worker-timeout': '15s', 'cluster-repr-interval': '500ms'},
  'adaptive': {'interval': '1s',
   'target-duration': '5s',
   'minimum': 0,
   'maximum': inf,
   'wait-count': 3},
  'comm': {'retry': {'count': 0, 'delay': {'min': '1s', 'max': '20s'}},
   'compression': 'auto',
   'shard': '64MiB',
   'offload': '10MiB',
   'default-scheme': 'tcp',
   'socket-backlog': 2048,
   'recent-messages-log-length': 0,
   'ucx': {'cuda-copy': None,
    'tcp': None,
    'nvlink': None,
    'infiniband': None,
    'rdmacm': None,
    'net-devices': None,
    'reuse-endpoints': None,
    'create-cuda-context': None},
   'zstd': {'level': 3, 'threads': 0},
   'timeouts': {'connect': '30s', 'tcp': '30s'},
   'require-encryption': None,
   'tls': {'ciphers': None,
    'ca-file': None,
    'scheduler': {'cert': None, 'key': None},
    'worker': {'key': None, 'cert': None},
    'client': {'key': None, 'cert': None}},
   'websockets': {'shard': '8MiB'}},
  'diagnostics': {'nvml': True,
   'computations': {'max-history': 100,
    'ignore-modules': ['distributed',
     'dask',
     'xarray',
     'cudf',
     'cuml',
     'prefect',
     'xgboost']}},
  'dashboard': {'link': '{scheme}://{host}:{port}/status',
   'export-tool': False,
   'graph-max-items': 5000,
   'prometheus': {'namespace': 'dask'}},
  'admin': {'tick': {'interval': '20ms', 'limit': '3s'},
   'max-error-length': 10000,
   'log-length': 10000,
   'log-format': '%(name)s - %(levelname)s - %(message)s',
   'pdb-on-err': False,
   'system-monitor': {'interval': '500ms'},
   'event-loop': 'tornado'},
  'rmm': {'pool-size': None}}}


"""
