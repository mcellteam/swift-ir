'''
This file is for initializing global config and 'project_data' the dictionary project state in memory.
It is imported by other project files.
'''
import copy
from package.alignem_data_model import new_project_template

# print('\n Initializing globals \n')

QT_API = None
USES_PYSIDE = None
USES_PYQT = None
USES_QT5 = None
USES_QT6 = None

# global project_data

project_data = None
# project_data = copy.deepcopy(new_project_template)





