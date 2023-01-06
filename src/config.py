#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary datamodel state in memory.'''

import platform

__all__ = ['data']

LOG_LEVEL = 1

'''Main Objects'''
# datamodel = None
data = None
increasing_tab_counter = 0
main_window = None
project_tab = None
zarr_tab = None
opengllogger = None
selected = None
ng_worker = None
dms = {}
viewer = None
refLV = None
baseLV = None
alLV = None
menLV = None
LV = None
tensor = None
unal_tensor = None
al_tensor = None
men_tensor = None
url = None
webdriver = None
results = None
dt = None
py_console = None

'''Default Window Size'''
# WIDTH, HEIGHT = 1160, 680
WIDTH, HEIGHT = 1180, 680

'''Default Alignment Params'''
DEFAULT_SWIM_WINDOW       = float(0.8125)
DEFAULT_WHITENING         = float(-0.6800)
DEFAULT_POLY_ORDER        = int(0)
DEFAULT_NULL_BIAS         = bool(True)
DEFAULT_BOUNDING_BOX      = bool(False)
DEFAULT_INITIAL_ROTATION  = float(0.0000)
DEFAULT_INITIAL_SCALE     = float(1.0000)

'''Default Image Resolution (Voxel Dimensions)'''
DEFAULT_RESX, DEFAULT_RESY, DEFAULT_RESZ = 2, 2, 50

'''Default Zarr Chunk Shape'''
# CHUNK_X, CHUNK_Y, CHUNK_Z = 512, 512, 3
CHUNK_X, CHUNK_Y, CHUNK_Z = 512, 512, 1
# CHUNK_X, CHUNK_Y, CHUNK_Z = 64, 64, 64

'''Default Compression Parameters'''
CNAME = 'zstd'
CLEVEL = 5

'''Other Defaults'''


if 'Joels-' in platform.node():
    DEV_MODE = True
else:
    DEV_MODE = False
# DEV_MODE = False
PRINT_EXAMPLE_ARGS = True
AUTOSAVE = True
DAEMON_THREADS = False
USE_EXTRA_THREADING = False
DEBUG_MP = False
DEBUG_NEUROGLANCER = False
PROFILER = False
DUMMY = False
USE_TENSORSTORE = True
FAULT_HANDLER = False
HEADLESS = False
# TACC_MAX_CPUS = 124  # 128 hardware cores/node on Lonestar6
# TACC_MAX_CPUS = 110  # 128 hardware cores/node on Lonestar6
TACC_MAX_CPUS = 116 # 128 hardware cores/node on Lonestar6
SUPPORT_NONSQUARE = True
USE_PYTHON = False
NO_SPLASH = True
SHADER = None
THEME = 0
SHOW_UI_CONTROLS = True
MP_LINEWEIGHT = 3
MP_SIZE = 6
USE_FILE_IO = 0
CODE_MODE = 'c'
# HTTP_PORT = 9000
ICON_COLOR = '#2774AE'

MV = True
