#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary data state in memory.'''

import platform

__all__ = []

LOG_LEVEL = 1

'''Main Objects'''
data = None
main_window = None
opengllogger = None
selected = None
ng_worker = None
extra_ng_workers = {}
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

'''Default Window Size'''
# WIDTH, HEIGHT = 1160, 680
WIDTH, HEIGHT = 1200, 680

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
IS_TACC = None
if 'Joels-' in platform.node():
    DEVELOPER_MODE = True
else:
    DEVELOPER_MODE = False
AUTOSAVE = True
DAEMON_THREADS = False
USE_EXTRA_THREADING = False
DEBUG_MP = False
DEBUG_NEUROGLANCER = False
PROFILER = False
DUMMY = False
USE_TENSORSTORE = True
USE_SIMPLEHTTPSERVER = True
USE_TORNADO = True
FAULT_HANDLER = False
HEADLESS = False
# TACC_MAX_CPUS = 124  # 128 hardware cores/node on Lonestar6
# TACC_MAX_CPUS = 110  # 128 hardware cores/node on Lonestar6
TACC_MAX_CPUS = 116 # 128 hardware cores/node on Lonestar6
SUPPORT_NONSQUARE = True
USE_PYTHON = False
NO_SPLASH = True
SIMULTANEOUS_SERVERS = False
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
