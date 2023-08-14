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

To output a string of Mypy CLI args that will reflect the currently selected src API:
$ qtpy mypy-args

~ ❯ pip show alignem
Name: alignEM
Version: 0.0.1
Summary: AlignEM-SWIFT is a graphical tool for aligning serial section electron micrographs using SWiFT-IR.
Home-page: https://github.com/mcellteam/swift-ir/tree/development_ng
Author: Joel Yancey,
Author-email: Joel Yancey <joelgyancey@ucla.edu>, Tom Bartol <bartol@salk.edu>, Arthur Wetzel <awetzel@psc.edu>
License: Mozilla Public License Version 2.0
Location: /Users/joelyancey/miniconda3/envs/test_alignem/lib/python3.9/site-packages
Requires: imagecodecs, neuroglancer, numpy, opencv-python-headless, pillow, psutil, PyQt5, pyqtgraph,
pyqtwebengine, qtawesome, qtconsole, qtpy, tifffile, tqdm, zarr
Required-by:


NOTES
https://github.com/nexpy/nexpy/issues/398

"""
print('(Hang tight. The application will launch shortly...)')
import os
import subprocess as sp
import qtpy
# os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'
# os.environ["BLOSC_NTHREADS"] = "1"
import sys, signal, logging, argparse
import faulthandler
from concurrent.futures import ThreadPoolExecutor

from qtpy.QtWebEngineWidgets import *
from qtpy import QtCore
from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.helpers import check_for_binaries, configure_project_paths, initialize_user_preferences, \
    is_tacc, print_exception, register_login, convert_projects_model
import src.config as cfg
from qtconsole import __version__ as qcv

print("Imports complete.", flush=True)




# WHITE_LIST = {'src'}      # Look for these words in the file path.
# EXCLUSIONS = {'<'}          # Ignore <listcomp>, etc. in the function name.

# def tracefunc(frame, event, arg):
#     # https://stackoverflow.com/questions/8315389/how-do-i-print-functions-as-they-are-called
#     if event == "call":
#         tracefunc.stack_level += 1
#
#         unique_id = frame.f_code.co_filename + str(frame.f_lineno)
#         if unique_id in tracefunc.memorized:
#             return
#
#         # Part of filename MUST be in white list.
#         if any(x in frame.f_code.co_filename for x in WHITE_LIST) \
#                 and \
#                 not any(x in frame.f_code.co_name for x in EXCLUSIONS):
#
#             if 'self' in frame.f_locals:
#                 class_name = frame.f_locals['self'].__class__.__name__
#                 func_name = class_name + '.' + frame.f_code.co_name
#             else:
#                 func_name = frame.f_code.co_name
#
#             func_name = '{name:->{indent}s}()'.format(indent=tracefunc.stack_level * 2, name=func_name)
#             txt = '{: <40} # {}, {}'.format(
#                 func_name, frame.f_code.co_filename, frame.f_lineno)
#             print(txt)
#
#             tracefunc.memorized.add(unique_id)
#
#     elif event == "return":
#         tracefunc.stack_level -= 1
#
#
# tracefunc.memorized = set()
# tracefunc.stack_level = 0

def addLoggingLevel(levelName, levelNum, methodName=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
       raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
       raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
       raise AttributeError('{} already defined in logger class'.format(methodName))

    # This method is based on answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)
    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)

class CustomFormatter(logging.Formatter):
    # ANSI color codess
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[1;34m"
    reset = "\x1b[0m"
    format = '%(asctime)s %(levelname)s [%(module)s.%(funcName)s:%(lineno)d] %(message)s'
    format2 = '%(asctime)s [%(module)s.%(funcName)s:%(lineno)d] %(message)s'
    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        # logging.CRITICAL: bold_red + format2 + reset,
        logging.CRITICAL: blue + format2 + reset,
    }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)


def main():
    logger = logging.getLogger()
    # logger = logging.getLogger(__name__)
    # logging.propagate = False  # stops message propogation to the root handler
    # fh = logging.FileHandler('messages.log')
    # logger.addHandler(fh)
    # logger.info('Running ' + __file__ + '.__main__()')
    # logger.critical('start cwd: %s' % os.getcwd())
    # logger.critical('directory of this script: %s' % os.path.dirname(__file__))
    # # os.chdir(os.path.dirname(__file__))
    # logger.critical('new cwd: %s' % os.getcwd())

    logger.info('Setting Qt.AA_ShareOpenGLContexts')
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts) # must be set before QCoreApplication is created. #2230-
    QCoreApplication.setAttribute(Qt.AA_UseOpenGLES)

    QCoreApplication.setApplicationName("ALIGNEM-SWIFT")

    addLoggingLevel('VERSIONCHECK', logging.DEBUG + 5)
    logging.getLogger('init').setLevel("VERSIONCHECK")
    logging.getLogger('init').versioncheck('alignEM-SWiFT         : %s' % cfg.VERSION)
    logging.getLogger('init').versioncheck('environment           : %s' % sys.version)
    logging.getLogger('init').versioncheck('QtCore.__version__    : %s' % QtCore.__version__)
    logging.getLogger('init').versioncheck('qtpy.PYQT_VERSION     : %s' % qtpy.PYQT_VERSION)
    logging.getLogger('init').versioncheck('qtpy.PYSIDE_VERSION   : %s' % qtpy.PYSIDE_VERSION)
    logging.getLogger('init').versioncheck('Jupyter QtConsole     : %s' % qcv)

    check_for_binaries()

    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='pyqt5', help='Python-Qt API (pyqt6|pyqt5|pyside6|pyside2)')
    parser.add_argument('--debug', action='store_true', help='Debug Mode')
    parser.add_argument('--debug_mp', action='store_true', help='Set python multiprocessing debug level to DEBUG')
    parser.add_argument('--loglevel', type=int, default=cfg.LOG_LEVEL, help='Logging Level (0-4)')
    # parser.add_argument('--no_tensorstore', action='store_true', help='Does not use Tensorstore if True')
    parser.add_argument('--headless', action='store_true', help='Do not embed the neuroglancer browser if True')
    parser.add_argument('--no_splash', action='store_true', help='Do not start up with a splash screen')
    parser.add_argument('--dummy', action='store_true', help='Start the application using a dummy project')
    parser.add_argument('--profile', action='store_true', help='Profile performance of memory and multiprocessing')
    args = parser.parse_args()
    os.environ['QT_API'] = args.api  # This env setting is ingested by qtpy
    # os.environ['PYQTGRAPH_QT_LIB'] = args.api #do not set!

    os.environ['PYQTGRAPH_QT_LIB'] = 'PyQt5'
    os.environ["BLOSC_NTHREADS"] = "1"

    if logger.hasHandlers():  logger.handlers.clear() #orig
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    LOGLEVELS = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(LOGLEVELS[args.loglevel])
    if args.debug_mp:
        cfg.DEBUG_MP = 1
    # if args.no_tensorstore: cfg.USE_TENSORSTORE = False
    if args.headless:  cfg.HEADLESS = True
    if args.no_splash: cfg.NO_SPLASH = True
    if args.dummy: cfg.DUMMY = True
    if args.profile:
        cfg.PROFILING_MODE = True


    if is_tacc():
        try:
            register_login()
        except:
            print_exception()
        try:
            bashrc = os.path.join(os.getenv('HOME'), '.bashrc')

            try:
                appendme = """\nalias alignem='source $WORK/swift-ir/tacc_bootstrap'"""
                check_str = """alias alignem="""
                with open(bashrc, "r") as f:
                    found = any(check_str in x for x in f)
                logger.info(f"Quick launch alias 'alignem' found? {found}")
                if not found:
                    logger.critical("Adding quick launch alias 'alignem'...")
                    with open(bashrc, "a+") as f:
                        f.write(appendme)
                    logger.info("Sourcing bashrc...")
                    sp.call(['source', '$HOME/.bashrc'])
            except:
                print_exception()

            try:
                appendme = """\nalias alignemdev='source $WORK/swift-ir/tacc_develop'"""
                check_str = """alias alignemdev="""
                with open(bashrc, "r") as f:
                    found = any(check_str in x for x in f)
                logger.info(f"Quick launch alias 'alignemdev' found? {found}")
                if not found:
                    logger.critical("Adding quick launch alias 'alignemdev'...")
                    with open(bashrc, "a+") as f:
                        f.write(appendme)
                    logger.info("Sourcing bashrc...")
                    sp.call(['source', '$HOME/.bashrc'])
            except:
                print_exception()
        except:
            print_exception()


    # https://doc.qt.io/qtforpython-5/PySide2/QtCore/Qt.html
    # Forces the usage of OpenGL ES 2.0 or higher on platforms that
    # use dynamic loading of the OpenGL implementation.

    if cfg.FAULT_HANDLER:
        faulthandler.enable(file=sys.stderr, all_threads=True)

    # if cfg.PROFILING_MODE:
    #     sys.setprofile(tracefunc)

    os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    # logger.info('Setting OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES')
    # logger.info('Setting QTWEBENGINE_CHROMIUM_FLAGS')
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    # os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-web-security'

    # ***************
    # os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox -disable-web-security --enable-logging'
    # ***************

    # os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--enable-logging --log-level=3' # suppress JS warnings
    # os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-web-security --enable-logging --log-level=0'
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-web-security --no-sandbox --num-raster-threads=%s' % cfg.QTWEBENGINE_RASTER_THREADS
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    # os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9000'
    os.environ['LIBTIFF_STRILE_ARRAY_MAX_RESIZE_COUNT'] = '1000000000'

    # PYTHONHASHSEED must be "random" or an integer in range [0; 4294967295]
    # os.environ['PYTHONHASHSEED'] = '98247985'
    # os.environ['PYTHONHASHSEED'] = '0'


    if qtpy.QT5:
        logger.info('Setting Qt.AA_EnableHighDpiScaling')
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        logger.info('Setting Qt.AA_UseHighDpiPixmaps')
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


    # QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL) #0226-

    # report the number of worker threads chosen by default
    logger.info(f"ThreadPoolExecutor _max_workers: {ThreadPoolExecutor()._max_workers}")

    initialize_user_preferences()
    convert_projects_model()
    # configure_project_paths()

    # app = QApplication([])
    app = QApplication(sys.argv)

    app.setStyle('Fusion')
    # app.setStyle('Breeze')
    # app.setStyle('Oxygen')
    # app.setStyle('Windows')
    cfg.main_window = cfg.mw = MainWindow()

    logger.info('Showing AlignEM-SWiFT...')
    cfg.main_window.show()

    sys.exit(app.exec())

    # stats = pstats.Stats(profiler).sort_stats('ncalls')
    # stats.print_stats()

    # sys.exit(app.exec())


if __name__ == "__main__":

    main()



