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
project_tab = None
zarr_tab = None
thumb = None
emViewer = None
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
WIDTH, HEIGHT = 1380, 760

'''Default Alignment Params'''
DEFAULT_SWIM_WINDOW       = float(0.8125)
DEFAULT_WHITENING         = float(-0.6800)
DEFAULT_POLY_ORDER        = int(0)
DEFAULT_NULL_BIAS         = bool(False)
DEFAULT_BOUNDING_BOX      = bool(False)
DEFAULT_INITIAL_ROTATION  = float(0.0000)
DEFAULT_INITIAL_SCALE     = float(1.0000)

'''Default Image Resolution (Voxel Dimensions)'''
DEFAULT_RESX, DEFAULT_RESY, DEFAULT_RESZ = 2, 2, 50

'''Default Zarr Chunk Shape'''
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
TARGET_THUMBNAIL_SIZE = 256
if 'Joels-' in platform.node():
    DEV_MODE = True
else:
    DEV_MODE = False
PROFILING_MODE = False
if 'Joels-' in platform.node():
    PROFILING_MODE = True
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
MP_MODE = False
# SHADER =
# SHADER = shaders.shader_default_
# SHADER = '''#uicontrol invlerp normalized
# void main() {
#   emitGrayscale(normalized());
# }'''
# SHADER = '#define VOLUME_RENDERING true'
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

SHADER = shader_default_ = '''#uicontrol vec3 color color(default="white")
#uicontrol float brightness slider(min=-1, max=1, step=0.01)
#uicontrol float contrast slider(min=-1, max=1, step=0.01)
void main() {
  emitRGB(color *
          (toNormalized(getDataValue()) + brightness) *
          exp(contrast));
}
'''

