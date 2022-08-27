'''
This file is for initializing global config and 'project_data' the dictionary project state in memory.
It is imported by other src files and lives outside of the 'src' directory.
'''

__all__ = ['LOG_LEVEL','QT_API','USES_PYSIDE','USES_PYQT','USES_QT5','USES_QT6',
           'project_data','main_window','image_library','USE_FILE_IO',
           'PARALLEL_MODE','CODE_MODE','ICON_COLOR','WIDTH','HEIGHT','DEFAULT_INITIAL_ROTATION',
           'DEFAULT_INITIAL_SCALE', 'DEFAULT_BOUNDING_BOX','DEFAULT_NULL_BIAS',
           'DEFAULT_POLY_ORDER','DEFAULT_WHITENING','DEFAULT_SWIM_WINDOW']

import os
import logging

LOG_LEVEL = None

DEFAULT_SWIM_WINDOW       = float(0.8125)
DEFAULT_WHITENING         = float(-0.6800)
DEFAULT_POLY_ORDER        = int(0)
DEFAULT_NULL_BIAS         = bool(False)
DEFAULT_BOUNDING_BOX      = bool(True)
DEFAULT_INITIAL_ROTATION  = float(0.0000)
DEFAULT_INITIAL_SCALE     = float(1.0000)

QT_API = None
USES_PYSIDE = None
USES_PYQT = None
USES_QT5 = None
USES_QT6 = None

project_data = None
main_window = None
image_library = None
data_model = None
defaults_form = None
panel_list = []

PRELOAD_RANGE = None
USE_FILE_IO = 0
PARALLEL_MODE = True
CODE_MODE = 'c'
HTTP_PORT = 9000
NO_NEUROGLANCER = None
PROJECT_OPEN = False
IMAGES_IMPORTED = False



defaults = ["-0.6800", "0.8125", "0.0000", True]

# cfg.ICON_COLOR = '#d3dae3'
# cfg.ICON_COLOR = '#7c7c7c'
ICON_COLOR = '#455364' # off blue-ish color

WIDTH = 1320
HEIGHT = 850

# class bcolors:
#     HEADER = '\033[95m'
#     OKBLUE = '\033[94m'
#     OKCYAN = '\033[96m'
#     OKGREEN = '\033[92m'
#     WARNING = '\033[93m'
#     FAIL = '\033[91m'
#     ENDC = '\033[0m'
#     BOLD = '\033[1m'
#     UNDERLINE = '\033[4m'


# CSI = "\x1B["
# print(CSI+"31;40m" + u"\u2588"*20 + CSI + "0m")
#
# print('\x1b[6;30;42m' + 'Success!' + '\x1b[0m')



