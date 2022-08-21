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

reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
installed_packages = [r.decode().split('==')[0] for r in reqs.split()]
if 'QtPy' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','qtpy'])
if 'QtAwesome' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','qtawesome'])
if 'pyqtgraph' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','pyqtgraph'])
if 'tqdm' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','tqdm'])
if 'tqdm' not in installed_packages:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install','imagecodecs'])

from alignEM.em_utils import print_exception
from alignEM.ui.main_window import MainWindow
import alignEM.config as cfg

class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    # blue = "\x1b[1;34m"
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

logger = logging.getLogger()
if logger.hasHandlers():  logger.handlers.clear()
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)


if __name__ == "__main__":

    logger.info('Running ' + __file__ + '.__main__()')
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--api', default='pyqt5', help='Python-Qt API (pyqt6|pyqt5|pyside6|pyside2)')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug Mode')
    parser.add_argument('-l', '--loglevel', type=int, default=1, help='Logging Level (1-5, default: 2)')
    parser.add_argument('-p', '--preload', type=int, default=3, help='# Images +/- to Preload')
    args = parser.parse_args()
    LOGLEVELS = [ logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL ]
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(LOGLEVELS[args.loglevel])
    cfg.LOG_LEVEL = logger.level
    cfg.QT_API = args.api
    cfg.PRELOAD_RANGE = args.preload
    # print('\x1b[6;30;42m' + '--' * 43 + '\x1b[0m')
    logger.critical('You are aligning with AlignEM-SWiFT, please report any newlybugs to joel@salk.edu.')
    # print('\x1b[6;30;42m' + '--' * 43 + '\x1b[0m')
    sys.stdout.flush()
    os.environ['QT_API'] = cfg.QT_API
    # os.environ["FORCE_QT_API"] = 'True'
    os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-web-security --ignore-gpu-blacklist'
    os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9000'
    logger.info('QT_API: %s' % os.environ.get('QT_API'))

    if cfg.QT_API in ('pyside2', 'pyside6'): cfg.USES_PYSIDE, cfg.USES_PYQT = True, False
    if cfg.QT_API in ('pyqt5', 'pyqt6'):     cfg.USES_PYQT, cfg.USES_PYSIDE = True, False
    if cfg.QT_API in ('pyside2', 'pyqt5'):   cfg.USES_QT5, cfg.USES_QT6 = True, False
    if cfg.QT_API in ('pyside6', 'pyqt6'):   cfg.USES_QT6, cfg.USES_QT5 = True, False

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts) # must be set before QCoreApplication is created.
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # graceful exit on ctrl+c

    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        logger.info('QApplication Instance Created')
    except:
        logger.error('Unable to Instantiate QApplication')
        print_exception()

    try:
        cfg.main_window = MainWindow(title="AlignEM-SWiFT")
        cfg.main_window.setGeometry(100,100, cfg.WIDTH, cfg.HEIGHT)
        # cfg.main_window.define_roles(['ref', 'base', 'aligned'])
        app.aboutToQuit.connect(cfg.main_window.shutdown_jupyter_kernel)
        cfg.main_window.show()
        logger.info('Showing AlignEM-SWiFT')
    except:
        logger.error('Unable to Instantiate MainWindow')
        print_exception()

    try:
        sys.exit(app.exec())
    except:
        sys.exit(app.exec_())