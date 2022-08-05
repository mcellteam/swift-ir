'''
This file is for initializing global config and 'project_data' the dictionary project state in memory.
It is imported by other package files and lives outside of the 'package' directory.
'''

__all__ = ['LOG_LEVEL','QT_API','USES_PYSIDE','USES_PYQT','USES_QT5','USES_QT6',
           'project_data','main_window','image_library','USE_FILE_IO',
           'PARALLEL_MODE','CODE_MODE','ICON_COLOR','WIDTH','HEIGHT']

import logging

LOG_LEVEL = logging.INFO

DEFAULT_SWIM_WINDOW       = float(0.8125)
DEFAULT_WHITENING         = float(-0.6800)
DEFAULT_POLY_ORDER        = int(0)
DEFAULT_NULL_BIAS         = bool(False)
DEFAULT_BOUNDING_BOX      = bool(True)
DEFAULT_INITIAL_ROTATION  = 0.0000
DEFAULT_INITIAL_SCALE  = 0.0000

QT_API = None
USES_PYSIDE = None
USES_PYQT = None
USES_QT5 = None
USES_QT6 = None

project_data = None
main_window = None
image_library = None

data_model = None

PRELOAD_RANGE = 3

USE_FILE_IO = 0
PARALLEL_MODE = True
CODE_MODE = 'c'
# CODE_MODE = 'python'


# defaults = {}
# defaults['whitening_factor']     = float(-0.6800)
# defaults['swim_window']          = float(0.8125)
# defaults['initial_rotation']     = float(0.0000)
# defaults['bounding_rectangle']   = bool(True)
# defaults['poly_order']           = int(0)
# defaults['null_bias']            = bool(False)
defaults = ["-0.6800", "0.8125", "0.0000", True]

# cfg.ICON_COLOR = "#d3dae3" #orig
# cfg.ICON_COLOR = '#7c7c7c'
ICON_COLOR = '#455364' # off blue-ish color

WIDTH = 1320
HEIGHT = 850

