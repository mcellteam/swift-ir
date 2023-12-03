#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary datamodel state in memory.'''

__all__ = ['dm']

VERSION = '0.5.51'

LOOP = None

CONFIG = None

'''Default Window Size'''
WIDTH, HEIGHT = 1200, 760

# max_downsampling=1024  # default=64
# max_downsampled_size=2056  # default=128
# # max_downsampling_scales=1

max_downsampling = 512  # default=64
max_downsampled_size = 1024  # default=128
# max_downsampling_scales=1

KEEP_SIGNALS = True
KEEP_MATCHES = True
GENERATE_THUMBNAILS = True

DEV_MODE = 1
LOG_RECIPE_TO_FILE = 1
DEBUG_MP = 0
DEBUG_NEUROGLANCER = 0
VERBOSE_SWIM = 0
# TACC_MAX_CPUS = 58 # x3 is > 304
# TACC_MAX_CPUS = 90 # x3 is > 304
# QTWEBENGINE_RASTER_THREADS = 1024
# QTWEBENGINE_RASTER_THREADS = 128
QTWEBENGINE_RASTER_THREADS = 512
TARGET_THUMBNAIL_SIZE = 256
USE_POOL_FOR_SWIM = True
# USE_EXTRA_THREADING = True
# UI_UPDATE_TIMEOUT = 300 #ms
# UI_UPDATE_TIMEOUT = 350  # ms
TACC_MAX_CPUS = 100  # x3 is > 304
SCALE_2_CORES_LIMIT = 70
SCALE_1_CORES_LIMIT = 30


'''Default SWIM parameters'''
# DEFAULT_POLY_ORDER             = int(0)
DEFAULT_USE_BOUNDING_BOX = bool(False)
DEFAULT_INITIAL_ROTATION = float(0.0000)
DEFAULT_INITIAL_SCALE = float(1.0000)
DEFAULT_DTYPE = '|u1'
DEFAULT_MANUAL_SWIM_WINDOW_PERC = float(.125)
DEFAULT_AUTO_SWIM_WINDOW_PERC = float(0.8125)
DEFAULT_WHITENING = float(-0.6800)
DEFAULT_CLOBBER_PX = 3
DEFAULT_USE_CLOBBER = False
DEFAULT_SWIM_ITERATIONS = 3  # in pixels
DEFAULT_CORRECTIVE_POLYNOMIAL = None
'''Default Image Resolution (Voxel Dimensions)'''
DEFAULT_RESX, DEFAULT_RESY, DEFAULT_RESZ = 2, 2, 50
'''Default Zarr Chunk Shape'''
CHUNK_X, CHUNK_Y, CHUNK_Z = 1024, 1024, 1
CHUNK_FACTOR = 16
BLOCKSIZE = 4
'''Default Compression Parameters'''
# CNAME = 'zstd'
CNAME = 'none'
CLEVEL = 5

preferences = None
dm = None
# dataById = {}
tabsById = {}
main_window = None
mw = None
project_tab = None
pt = None
pm = None
zarr_tab = None
thumb = None
viewer0 = None
editorViewer = None
selected = None
dms = {}
alLV = None
LV = None
tensor = None
unal_tensor = None
al_tensor = None
men_tensor = None
webdriver = None
py_console = None
is_mendenhall = False

'''Other Defaults'''
DEFAULT_PLAYBACK_SPEED = 4.0 # playback speed (fps)
PROFILING_MODE = False
PRINT_EXAMPLE_ARGS = True
DAEMON_THREADS = True
PROFILER = False
FAULT_HANDLER = False
HEADLESS = False
SUPPORT_NONSQUARE = True
DELAY_BEFORE = 0
DELAY_AFTER = 0
USE_DELAY = False

nProcessSteps = 0
nProcessDone = 0
CancelProcesses = False
event = None
ignore_pbar = False

# glob_colors = ['#75bbfd', '#e50000', '#fcfc81', '#acc2d9', '#b2996e', '#a8ff04',]
# glob_colors = ['#ffffe4', '#be013c', '#42d4f4', '#FFFF66', '#b2996e', '#a8ff04',]
glob_colors = ['#ffffe4', '#ffe135', '#42d4f4', '#b2996e', '#FFFF66', '#a8ff04',]

SHADER = shader_default_ = '''#uicontrol vec3 color color(default="white")
#uicontrol float brightness wSlider(min=-1, max=1, step=0.01)
#uicontrol float contrast wSlider(min=-1, max=1, step=0.01)
void main() {
  emitRGB(color *
          (brightness) *
          exp(contrast));
}
'''

vw = None
temp = None

