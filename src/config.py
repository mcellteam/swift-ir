#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary datamodel state in memory.'''

import platform

__all__ = ['data']

LOG_LEVEL = 1

'''Main Objects'''
# datamodel = None
data = None
dataById = {}
main_window = None
project_tab = None
zarr_tab = None
thumb = None
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
is_mendenhall = False

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
# CNAME = 'zstd'
CNAME = 'None'
CLEVEL = 5

'''Other Defaults'''
KEEP_ORIGINAL_SPOTS = False
PROFILING_TIMER_SPEED = 5000
PROFILING_TIMER_AUTOSTART = False
DEFAULT_PLAYBACK_SPEED = 2.5 # playback speed (fps)
TARGET_THUMBNAIL_SIZE = 500
if 'Joels-' in platform.node():
    DEV_MODE = True
else:
    DEV_MODE = False
PRINT_EXAMPLE_ARGS = True
AUTOSAVE = True
DAEMON_THREADS = True
USE_EXTRA_THREADING = False
DEBUG_MP = False
DEBUG_NEUROGLANCER = False
# DEBUG_MP = (False,True)[DEV_MODE]
# DEBUG_NEUROGLANCER = (False,True)[DEV_MODE]
PROFILER = False
DUMMY = False
USE_TENSORSTORE = True
FAULT_HANDLER = False
HEADLESS = False
# TACC_MAX_CPUS = 124  # 128 hardware cores/node on Lonestar6
# TACC_MAX_CPUS = 110  # 128 hardware cores/node on Lonestar6
TACC_MAX_CPUS = 122 # 128 hardware cores/node on Lonestar6
SUPPORT_NONSQUARE = True
USE_PYTHON = False
NO_SPLASH = True
# SHADER = '''
# #define VOLUME_RENDERING true
# void main () {
# emitGrayscale(toNormalized(getDataValue()));
# }'''
SHADER = ''
THEME = 0
MP_LINEWEIGHT = 3
MP_SIZE = 6
USE_FILE_IO = 0
CODE_MODE = 'c'
# HTTP_PORT = 9000
ICON_COLOR = '#2774AE'

MV = True

# SHOW_UI_CONTROLS = False
# SHOW_SCALE_BAR = True
# SHOW_PANEL_BORDERS = True
# SHOW_AXIS_LINES = False

settings = None
projects = None
selected_file = None
tasks_remaining = None
tasks_total = None

MP_MODE = False


DELAY_BEFORE = 0
DELAY_AFTER = 0
USE_DELAY = False

nTasks = 0
nCompleted = 0
CancelProcesses = False
event = None


