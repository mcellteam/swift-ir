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

"""
import os, sys, signal, logging, argparse



# os.environ['QT_API'] = 'pyqt6'
# os.environ['QT_API'] = 'PySide6'
# os.environ['QT_DRIVER'] = 'PySide6' # necessary for qimage2ndarray


# import cProfile, pstats, io
# from pstats import SortKey
# cfg.pr = cProfile.Profile()
# cfg.pr.enable()

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


def main():
    logger.info('Running ' + __file__ + '.__main__()')
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='pyqt5', help='Python-Qt API (pyqt6|pyqt5|pyside6|pyside2)')
    parser.add_argument('--debug', action='store_true', help='Debug Mode')
    parser.add_argument('--loglevel', type=int, default=1, help='Logging Level (1-5, default: 2)')
    # parser.add_argument('-n', '--no_neuroglancer', action='store_true', default=False, help='Debug Mode')
    args = parser.parse_args()
    import qtpy
    os.environ['QT_API'] = args.api  # This env setting is ingested by qtpy
    # os.environ['PYQTGRAPH_QT_LIB'] = args.api #do not set!

    from PIL import Image
    import neuroglancer
    from qtpy.QtWidgets import QApplication
    from qtpy.QtCore import Qt, QCoreApplication, QTimer
    from src.helpers import print_exception, check_for_binaries
    from src.ui.main_window import MainWindow
    import src.config as cfg

    LOGLEVELS = [ logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL ]
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(LOGLEVELS[args.loglevel])
    cfg.LOG_LEVEL = logger.level
    cfg.QT_API = args.api

    # os.environ['MESA_GL_VERSION_OVERRIDE'] = '4.5'
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-web-security'
    # os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9000'

    # Qt5 Only
    if qtpy.QT5:
        logger.info('Setting Qt.AA_EnableHighDpiScaling and Qt.AA_UseHighDpiPixmaps attributes')
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    logger.info('Setting PIL limit on MAX_IMAGE_PIXELS to None')
    Image.MAX_IMAGE_PIXELS = None

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts) # must be set before QCoreApplication is created.
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # graceful exit on ctrl+c

    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
    except:
        print_exception()
        logger.error('Unable to Instantiate QApplication')

    try:
        logger.info('Initializing MainWindow')
        cfg.main_window = cfg.w = MainWindow(title="AlignEM-SWiFT")
        cfg.main_window.setGeometry(100,100, cfg.WIDTH, cfg.HEIGHT)
        app.aboutToQuit.connect(cfg.main_window.shutdownJupyter) #0921+
        app.aboutToQuit.connect(neuroglancer.server.stop) #0921+
        cfg.main_window.show()
        logger.info('Showing AlignEM-SWiFT')
    except:
        print_exception()
        logger.error('Unable to Instantiate MainWindow')

    try:
        logger.info('Trying sys.exit(app.exec())...')
        sys.exit(app.exec())
        # sys.exit(app.exec_())
    except:
        logger.info('Trying sys.exit(app.exec_())...')
        sys.exit(app.exec_())
        # sys.exit(app.exec())


if __name__ == "__main__":
    main()