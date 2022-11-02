#!/usr/bin/env python3

'''This file is for initializing global config and 'data' the dictionary data state in memory.'''

# __all__ = ['data', 'main_window']
__all__ = []

LOG_LEVEL = 1

'''Main Objects'''
data = None
main_window = None
# viewports = None
opengllogger = None

'''Default Window Size'''
WIDTH, HEIGHT = 1180, 800
# WIDTH, HEIGHT = 1500, 1200

'''Default Alignment Params'''
DEFAULT_SWIM_WINDOW       = float(0.8125)
DEFAULT_WHITENING         = float(-0.6800)
DEFAULT_POLY_ORDER        = int(0)
DEFAULT_NULL_BIAS         = bool(True)
DEFAULT_BOUNDING_BOX      = bool(True)
DEFAULT_INITIAL_ROTATION  = float(0.0000)
DEFAULT_INITIAL_SCALE     = float(1.0000)

'''Default Image Resolution (Voxel Dimensions)'''
RES_X, RES_Y, RES_Z = 2, 2, 50

'''Default Zarr Chunk Shape'''
CHUNK_X, CHUNK_Y, CHUNK_Z = 512, 512, 1

'''Default Compression Parameters'''
CNAME = 'zstd'
CLEVEL = 5

'''Other Defaults'''
USE_TENSORSTORE = True
# USE_TENSORSTORE = False
NO_EMBED_NG = False
# TACC_MAX_CPUS = 128  # 128 hardware cores/node on Lonestar6
TACC_MAX_CPUS = 124  # 128 hardware cores/node on Lonestar6
# REFRESH_RATE = 300 # GUI refresh/synchronization rate (ms). None = OFF.
# REFRESH_RATE = None

MULTIVIEW = True

SUPPORT_NONSQUARE = False
DEBUG_MP = False
# NO_SPLASH = False
NO_SPLASH = True
USE_OPENCV = False
# USE_OPENCV = True

USE_FILE_IO = 0
CODE_MODE = 'c'
HTTP_PORT = 9000

PROJECT_OPEN = False

# cfg.ICON_COLOR = '#d3dae3'
# cfg.ICON_COLOR = '#7c7c7c'
ICON_COLOR = '#455364' # off blue-ish color
# ICON_COLOR = '#F3F6FB' # snow white



