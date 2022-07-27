#!/usr/bin/env python3
"""
AlignEM-SWiFT - A software tool for image alignment that is under active development.

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

To output a string of Mypy CLI args that will reflect the currently selected alignEM API:
$ qtpy mypy-args

"""

import os
import sys
import signal
import logging
import argparse
import subprocess
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt, QCoreApplication
# from ui.interface import MainWindow
from package.ui.app import MainWindow
import package.config as cfg


class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = '%(asctime)s %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] %(message)s'

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)

logger = logging.getLogger() # <-- use this logger initialization in main, to apply formatting to root logger
if (logger.hasHandlers()):
    logger.handlers.clear()

logger.setLevel(cfg.LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

# fileConfig('logger.ini')

# logging.basicConfig(
#         level=logging.DEBUG,
#         format='%(asctime)s %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] | %(message)s',
#         datefmt='%H:%M:%S',
#         handlers=[ logging.StreamHandler() ]
# )

# create logger with 'spam_application'

# logger.setLevel(logging.DEBUG)
# ch = logging.StreamHandler()
# ch.setLevel(logging.DEBUG)
# formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] | %(message)s')
# ch.setFormatter(formatter)
# logger.addHandler(ch)

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


# logger = logging.getLogger('AlignEMLogger')
# logger.setLevel(logging.DEBUG)  # <- critical instruction else logger will break.
# logging.basicConfig(
#         format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
#         datefmt='%H:%M:%S',
#         handlers=[logger.StreamHandler()]
# )
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(process)d - %(threadName)s - %(levelname)s - %(message)s')
# formatter = logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s")
# formatter = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
# handler.setFormatter(formatter)
# logger.addHandler(handler)



if __name__ == "__main__":

    # logger.debug("debug message")
    # logger.info("info message")
    # logger.warning("warning message")
    # logger.error("error message")
    # logger.critical("critical message")

    sys.stdout.write('\n===================================================================================\n')
    sys.stdout.write('Welcome to AlignEM-SWiFT (Development Branch). Please report bugs to joel@salk.edu.\n')
    sys.stdout.write('===================================================================================\n\n')
    sys.stdout.flush()
    logger.info("Running " + __file__ + ".__main__()")
    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, default=10,help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-p", "--parallel", type=int, required=False, default=1, help="Run in parallel")
    options.add_argument("-l", "--preload", type=int, required=False, default=3,help="Preload +/-, total to preload = 2n-1")
    options.add_argument("-c", "--use_c_version", type=int, required=False, default=1,help="Run the C versions of SWiFT tools")
    options.add_argument("-f", "--use_file_io", type=int, required=False, default=0,help="Use files to gather output from tasks")
    options.add_argument("-a", "--api", type=str, required=False, default='pyqt6',help="Select Python API from: pyqt6, pyqt5, pyside6, pyside2")
    options.add_argument("-i", "--interactive", required=False, default=False, action='store_true', help="Run with interactive python console in separate window")
    args = options.parse_args()
    cfg.PARALLEL_MODE = args.parallel
    cfg.USE_FILE_IO = args.use_file_io
    cfg.QT_API = args.api

    if cfg.QT_API in ('pyside2', 'pyside6'): cfg.USES_PYSIDE, cfg.USES_PYQT = True, False
    if cfg.QT_API in ('pyqt5', 'pyqt6'):     cfg.USES_PYQT, cfg.USES_PYSIDE = True, False
    if cfg.QT_API in ('pyside2', 'pyqt5'):   cfg.USES_QT5, cfg.USES_QT6 = True, False
    if cfg.QT_API in ('pyside6', 'pyqt6'):   cfg.USES_QT6, cfg.USES_QT5 = True, False

    # os.environ["FORCE_QT_API"] = 'True'
    os.environ['QT_API'] = cfg.QT_API
    os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    logger.info('QT_API=%s' % os.environ.get('QT_API'))
    logger.info('MESA_GL_VERSION_OVERRID=%s' % os.environ.get('MESA_GL_VERSION_OVERRIDE'))
    logger.info('OBJC_DISABLE_INITIALIZE_FORK_SAFETY=%s' % os.environ.get('OBJC_DISABLE_INITIALIZE_FORK_SAFETY'))
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts) # must be set before QCoreApplication is created.
    logger.info('Attribute alignEM::AA_ShareOpenGLContext set')
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # graceful exit on ctrl+c
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    logger.info('QApplication() created')
    logger.info('app.__str__() = %s' % app.__str__())
    logger.info('Instantiating MainWindow...')
    cfg.main_window = MainWindow(title="AlignEM-SWiFT")
    cfg.main_window.resize(cfg.WIDTH, cfg.HEIGHT)
    cfg.main_window.define_roles(['ref', 'base', 'aligned'])
    logger.info('Window Size is %dx%d pixels' % (cfg.WIDTH, cfg.HEIGHT))
    logger.info('Showing AlignEM-SWiFT')
    cfg.main_window.show()
    try:
        sys.exit(app.exec())
    except:
        sys.exit(app.exec_())


