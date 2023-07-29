#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary datamodel state in memory.'''

import platform
import getpass
# from src import shaders

__all__ = ['data']

VERSION = '0.5.49'

LOOP = None

LOG_LEVEL = 1
DEBUG_MP = 0
# DEBUG_MP = (False,True)[DEV_MODE]
DEBUG_NEUROGLANCER = 0
# DEBUG_NEUROGLANCER = (False,True)[DEV_MODE]
# RECIPE_LOGGING = int(getpass.getuser() in ('joelyancey','joely'))
RECIPE_LOGGING = 0
DEV_MODE = 1
# TACC_MAX_CPUS = 122 # 128 hardware cores/node on Lonestar6
# TACC_MAX_CPUS = 80 # 128 hardware cores/node on Lonestar6
VERBOSE_SWIM = 0
TACC_MAX_CPUS = 104 # x3 is > 304
# QTWEBENGINE_RASTER_THREADS = 1024
QTWEBENGINE_RASTER_THREADS = 128
TARGET_THUMBNAIL_SIZE = 256
USE_EXTRA_THREADING = True
UI_UPDATE_DELAY = 250 #ms

'''Main Objects'''
# datamodel = None
data = None
dataById = {}
tabsById = {}
main_window = None
mw = None
project_tab = None
pt = None
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
# WIDTH, HEIGHT = 1180, 720
# WIDTH, HEIGHT = 1320, 740
WIDTH, HEIGHT = 1400, 800

'''Default Alignment Params'''

# DEFAULT_POLY_ORDER            = int(0)
DEFAULT_NULL_BIAS             = bool(False)
DEFAULT_BOUNDING_BOX          = bool(False)
DEFAULT_INITIAL_ROTATION      = float(0.0000)
DEFAULT_INITIAL_SCALE         = float(1.0000)
DEFAULT_DTYPE                 = '|u1'
# DEFAULT_MANUAL_SWIM_WINDOW    = int(128)
DEFAULT_MANUAL_SWIM_WINDOW    = int(256)
DEFAULT_MANUAL_SWIM_WINDOW_PERC = float(.125)
DEFAULT_AUTO_SWIM_WINDOW_PERC   = float(0.8125)
# DEFAULT_AUTO_SWIM_WINDOW_PERC   = float(0.9000) #new default
# DEFAULT_MANUAL_WHITENING      = float(-0.6800)
DEFAULT_CLOBBER_PX            = 3
DEFAULT_SWIM_ITERATIONS       = 3 # in pixels

DEFAULT_WHITENING             = float(-0.6800)
# DEFAULT_WHITENING             = float(-0.6500)
DEFAULT_CORRECTIVE_POLYNOMIAL = None

'''Default Image Resolution (Voxel Dimensions)'''
DEFAULT_RESX, DEFAULT_RESY, DEFAULT_RESZ = 2, 2, 50

'''Default Zarr Chunk Shape'''
# CHUNK_X, CHUNK_Y, CHUNK_Z = 128, 128, 1
CHUNK_X, CHUNK_Y, CHUNK_Z = 1024, 1024, 1
# CHUNK_X, CHUNK_Y, CHUNK_Z = 64, 64, 64

'''Default Compression Parameters'''
# CNAME = 'zstd'
CNAME = 'None'
CLEVEL = 5

'''Other Defaults'''
DEFAULT_PLAYBACK_SPEED = 4.0 # playback speed (fps)
PROFILING_MODE = False
PRINT_EXAMPLE_ARGS = True
AUTOSAVE = True
DAEMON_THREADS = True
PROFILER = False
DUMMY = False
USE_TENSORSTORE = True
FAULT_HANDLER = False
HEADLESS = False
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

nProcessSteps = 0
nProcessDone = 0
CancelProcesses = False
event = None
ignore_pbar = False

# glob_colors = ['#75bbfd', '#e50000', '#fcfc81', '#acc2d9', '#b2996e', '#a8ff04',]
glob_colors = ['#ffffe4', '#be013c', '#42d4f4', '#FFFF66', '#b2996e', '#a8ff04',]

SHADER = shader_default_ = '''#uicontrol vec3 color color(default="white")
#uicontrol float brightness slider(min=-1, max=1, step=0.01)
#uicontrol float contrast slider(min=-1, max=1, step=0.01)
void main() {
  emitRGB(color *
          (toNormalized(getDataValue()) + brightness) *
          exp(contrast));
}
'''

