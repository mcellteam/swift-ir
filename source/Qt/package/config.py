'''
This file is for initializing global config and 'project_data' the dictionary project state in memory.
It is imported by other project files.
'''

import logging

__all__ = ['QT_API','USES_PYSIDE','USES_PYQT','USES_QT5','USES_QT6',
           'project_data','main_window','image_library','USE_FILE_IO',
           'PARALLEL_MODE','CODE_MODE','ICON_COLOR','WIDTH','HEIGHT']

QT_API = None
USES_PYSIDE = None
USES_PYQT = None
USES_QT5 = None
USES_QT6 = None

project_data = None
main_window = None
image_library = None

USE_FILE_IO = 0
PARALLEL_MODE = True
CODE_MODE = 'c'
# CODE_MODE = 'python'

# cfg.ICON_COLOR = "#d3dae3" #orig
# cfg.ICON_COLOR = '#7c7c7c'
ICON_COLOR = '#455364' # off blue-ish color

WIDTH = 1320
HEIGHT = 780

