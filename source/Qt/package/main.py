#!/usr/bin/env python3
print(f'Loading {__name__} at top of script')
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to [http://unlicense.org]

QtPy provides cross-compatibility for PySide2, PySide6, PyQt5, PyQt6

Environment variable QT_API can take the following values:
    pyqt5 (to use PyQt5).
    pyside2 (to use PySide2).
    pyqt6 (to use PyQt6).
    pyside6 (to use PySide6).

To output a string of Mypy CLI args that will reflect the currently selected Qt API:
$ qtpy mypy-args

"""

import os
import sys
import argparse
import subprocess
import logging
import signal
import time
from pathlib import Path
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt, QCoreApplication

from interface import MainWindow
import config as cfg

# logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")

# logging.getLogger().addHandler(logging.StreamHandler())
# fs = '%(asctime)s %(qThreadName)-15s %(levelname)-8s %(message)s'
# formatter = logging.Formatter(fs)
#
# LogWithLevelName = logging.getLogger('AlignEMlogger')
# level = logging.getLevelName('INFO')
# LogWithLevelName.setLevel(level)

reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
installed_packages = [r.decode().split('==')[0] for r in reqs.split()]
if 'QtAwesome' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','QtAwesome'])
if 'QtPy' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','QtPy'])
if 'imagecodecs' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','imagecodecs'])
if 'zarr' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','zarr'])
if 'tifffile' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','tifffile'])
if 'tqdm' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','tqdm'])


# main_win = None # previously outside __main__ scope
logging.root.handlers = []
if __name__ == "__main__":
    print(f'Loading {__name__} in __main__')
    logger = logging.getLogger(__name__)
    # logger = logging.getLogger('AlignEMLogger')
    logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt='%Y-%m-%d,%H:%M:%S',
            handlers=[ logging.StreamHandler() ]
    )
    # sys.stdout.write("\nWelcome to AlignEM-SWiFT (Development Branch). Please report bugs to joel@salk.edu.\n")
    sys.stdout.write('\n===================================================================================\n')
    sys.stdout.write('Welcome to AlignEM-SWiFT (Development Branch). Please report bugs to joel@salk.edu.\n')
    sys.stdout.write('===================================================================================\n\n')
    sys.stdout.flush()
    logging.info("main | Running " + __file__ + ".__main__()")
    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, default=10,help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-p", "--parallel", type=int, required=False, default=1, help="Run in parallel")
    options.add_argument("-l", "--preload", type=int, required=False, default=3,help="Preload +/-, total to preload = 2n-1")
    options.add_argument("-c", "--use_c_version", type=int, required=False, default=1,help="Run the C versions of SWiFT tools")
    options.add_argument("-f", "--use_file_io", type=int, required=False, default=0,help="Use files to gather output from tasks")
    options.add_argument("-a", "--api", type=str, required=False, default='pyqt6',help="Select Python API from: pyqt6, pyqt5, pyside6, pyside2")
    options.add_argument("-i", "--interactive", required=False, default=False, action='store_true', help="Run with interactive python console in separate window")
    args = options.parse_args()
    logging.info('main | cli args: %s' % str(args)[10:-1])
    # logging.info('main | %s' % str(args)[10:-1])

    cfg.global_parallel_mode = args.parallel
    cfg.global_use_file_io = args.use_file_io
    cfg.QT_API = args.api

    Path(__file__).resolve().parent.parent

    if cfg.QT_API in ('pyside2', 'pyside6'):
        cfg.USES_PYSIDE, cfg.USES_PYQT = True, False
    elif cfg.QT_API in ('pyqt5', 'pyqt6'):
        cfg.USES_PYQT, cfg.USES_PYSIDE = True, False
    if cfg.QT_API in ('pyside2', 'pyqt5'):
        cfg.USES_QT5, cfg.USES_QT6 = True, False
    elif cfg.QT_API in ('pyside6', 'pyqt6'):
        cfg.USES_QT6, cfg.USES_QT5 = True, False

    # os.environ["FORCE_QT_API"] = 'True'
    os.environ['QT_API'] = cfg.QT_API
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    logging.info('main | QT_API                              : %s' % os.environ.get('QT_API'))
    logging.info('main | OBJC_DISABLE_INITIALIZE_FORK_SAFETY : %s' % os.environ.get('OBJC_DISABLE_INITIALIZE_FORK_SAFETY'))
    logging.info('main | MESA_GL_VERSION_OVERRIDE            : %s' % os.environ.get('MESA_GL_VERSION_OVERRIDE'))
    # Attribute Qt::AA_ShareOpenGLContexts must be set before QCoreApplication is created.
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    logging.info('main | Attribute Qt::AA_ShareOpenGLContext set')
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # graceful exit on ctrl+c
    app = QApplication(sys.argv)
    logging.info('main | QApplication() created')
    logging.info('main | app.__str__() = %s' % app.__str__())
    app.setStyle('Fusion')
    logging.info('main | App style set to Fusion')
    logging.info('main | Instantiating MainWindow...')
    cfg.main_window = MainWindow(title="AlignEM-SWiFT") # no more control_model
    cfg.main_window.resize(cfg.WIDTH, cfg.HEIGHT)
    cfg.main_window.define_roles(['ref', 'base', 'aligned'])
    logging.info('main | Window Size is %dx%d pixels' % (cfg.WIDTH, cfg.HEIGHT))
    logging.info('main | Showing AlignEM-SWiFT')
    cfg.main_window.show() #windows are hidden by default
    # if cfg.USES_PYSIDE:
    #     app.quit()
    #     sys.exit(app.exec_())
    # else:
    #     app.quit()
    #     sys.exit(app.exec())

    app.quit()
    sys.exit(app.exec())


