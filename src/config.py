#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary datamodel state in memory.'''

import platform
# from src import shaders

__all__ = ['data']

LOG_LEVEL = 1

'''Main Objects'''
# datamodel = None
data = None
dataById = {}
main_window = None
mw = None
project_tab = None
zarr_tab = None
thumb = None
emViewer = None
refViewer = None
baseViewer = None
stageViewer = None
snrViewer = None
selected = None
dms = {}
refLV = None
baseLV = None
alLV = None
menLV = None
LV = None
tensor = None
unal_tensor = None
al_tensor = None
men_tensor = None
webdriver = None
py_console = None
is_mendenhall = False

'''Default Window Size'''
# WIDTH, HEIGHT = 1180, 680
# WIDTH, HEIGHT = 1380, 900
WIDTH, HEIGHT = 1180, 720

'''Default Alignment Params'''

DEFAULT_POLY_ORDER           = int(0)
DEFAULT_NULL_BIAS            = bool(False)
DEFAULT_BOUNDING_BOX         = bool(False)
DEFAULT_INITIAL_ROTATION     = float(0.0000)
DEFAULT_INITIAL_SCALE        = float(1.0000)
DEFAULT_DTYPE                = '|u1'
DEFAULT_MANUAL_SWIM_WINDOW   = int(128)
DEFAULT_MANUAL_SWIM_WINDOW_PERC = float(.125)
DEFAULT_AUTO_SWIM_WINDOW_PERC   = float(0.8125)
DEFAULT_MANUAL_WHITENING     = float(-0.6800)
DEFAULT_CLOBBER_PX           = 3
DEFAULT_SWIM_ITERATIONS      = 3 # in pixels

DEFAULT_WHITENING            = float(-0.6800)
DEFAULT_CORRECTIVE_POLYNOMIAL = None

'''Default Image Resolution (Voxel Dimensions)'''
DEFAULT_RESX, DEFAULT_RESY, DEFAULT_RESZ = 2, 2, 50

'''Default Zarr Chunk Shape'''
# CHUNK_X, CHUNK_Y, CHUNK_Z = 128, 128, 1
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
DEFAULT_PLAYBACK_SPEED = 4.0 # playback speed (fps)
TARGET_THUMBNAIL_SIZE = 256
if 'Joels-' in platform.node():
    DEV_MODE = True
else:
    DEV_MODE = False
PROFILING_MODE = False
PRINT_EXAMPLE_ARGS = True
AUTOSAVE = True
DAEMON_THREADS = True
USE_EXTRA_THREADING = True
DEBUG_MP = False
DEBUG_NEUROGLANCER = False
# DEBUG_MP = (False,True)[DEV_MODE]
# DEBUG_NEUROGLANCER = (False,True)[DEV_MODE]
PROFILER = False
DUMMY = False
USE_TENSORSTORE = True
FAULT_HANDLER = False
HEADLESS = False
TACC_MAX_CPUS = 122 # 128 hardware cores/node on Lonestar6
SUPPORT_NONSQUARE = True
USE_PYTHON = False
NO_SPLASH = True
MP_MODE = False
THEME = 0
MP_LINEWEIGHT = 3
MP_SIZE = 6
USE_FILE_IO = 0
CODE_MODE = 'c'
# HTTP_PORT = 9000
ICON_COLOR = '#2774AE'
MV = True

settings = None
selected_file = None
tasks_remaining = None
tasks_total = None

DELAY_BEFORE = 0
DELAY_AFTER = 0
USE_DELAY = False

nTasks = 0
nCompleted = 0
CancelProcesses = False
event = None
ignore_pbar = False

glob_colors = ['#75bbfd', '#e50000', '#fcfc81', '#acc2d9', '#b2996e', '#a8ff04',]

SHADER = shader_default_ = '''#uicontrol vec3 color color(default="white")
#uicontrol float brightness slider(min=-1, max=1, step=0.01)
#uicontrol float contrast slider(min=-1, max=1, step=0.01)
void main() {
  emitRGB(color *
          (toNormalized(getDataValue()) + brightness) *
          exp(contrast));
}
'''

