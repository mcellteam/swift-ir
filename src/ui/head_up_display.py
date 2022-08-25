#!/usr/bin/env python3
'''
Solid implementation of a thread-safe background GUI logger.

Adapted from:
https://www.oulub.com/en-US/Python/howto.logging-cookbook-a-qt-gui-for-logging
'''

import time
import random
import logging
from qtpy.QtCore import QObject, Signal, Slot, QThread
from qtpy.QtGui import QFont, QTextCursor
from qtpy.QtWidgets import QApplication, QWidget, QPlainTextEdit, QVBoxLayout
# from src.TqdmToLogger import TqdmToLogger

__all__ = ['HeadUpDisplay', 'HudWorker']

# logger = logging.getLogger(__name__)
logger = logging.getLogger("hud")

class Signaller(QObject):
    signal = Signal(str, logging.LogRecord)

class QtHandler(logging.Handler):
    def __init__(self, slotfunc, *args, **kwargs):
        super(QtHandler, self).__init__(*args, **kwargs)
        self.signaller = Signaller()
        self.signaller.signal.connect(slotfunc)

    def emit(self, record):
        s = self.format(record)
        self.signaller.signal.emit(s, record)

class HudWorker(QObject):
    @Slot()
    def start(self):
        extra = {'qThreadName': ctname()}
        logger.debug('Started work', extra=extra)
        i = 1
        # Let the thread run until interrupted. This allows reasonably clean
        # thread termination.
        while not QThread.currentThread().isInterruptionRequested():
            delay = 0.5 + random.random() * 2
            time.sleep(delay)
            level = logging.INFO
            logger.log(level, 'Message after delay of %3.1f: %d', delay, i, extra=extra)
            i += 1

class HeadUpDisplay(QWidget):

    COLORS = {
        logging.DEBUG: 'black',
        # logging.INFO: 'blue',
        # logging.INFO: '#d3dae3',
        logging.INFO: '#41FF00',
        # logging.WARNING: 'orange',
        logging.WARNING: 'yellow',
        logging.ERROR: '#FD001B',
        # logging.CRITICAL: 'purple',
        # logging.CRITICAL: '#daf0ff',
        logging.CRITICAL: '#decfbe',
    }

    def __init__(self, app):
        super(HeadUpDisplay, self).__init__()
        self.app = app
        self.textedit = te = QPlainTextEdit(self)
        # Set whatever the default monospace font is for the platform
        f = QFont()
        f.setStyleHint(QFont.Monospace)
        te.setFont(f)
        te.setReadOnly(True)
        te.setStyleSheet("""
            /*background-color: #d3dae3;*/
            /*background-color:  #f5ffff;*/
            /*background-color:  #151a1e;*/
            background-color:  #000000;
            /*border-style: solid;*/
            border-style: inset;
            /*border-color: #455364;*/ /* off-blue-ish color used in qgroupbox border */
            border-color: #d3dae3;     /* light off-white */
            border-width: 0px;
            border-radius: 2px;            
        """)
        self.handler = h = QtHandler(self.update_status)
        # fs = '%(asctime)s %(qThreadName)-12s %(levelname)-8s %(message)s'
        # fs = '%(asctime)s %(qThreadName)-15s %(levelname)-8s %(message)s'
        fs = '%(asctime)s [%(levelname)s] %(qThreadName)-10s | %(message)s'
        fs = '%(asctime)s [%(levelname)s] %(message)s'
        # fs = '%(levelname)-8s %(asctime)s %(qThreadname)-15s %(message)s'
        formatter = logging.Formatter(fs, datefmt='%H:%M:%S')
        h.setFormatter(formatter)
        logger.addHandler(h)

        # Set up to terminate the QThread when we exit
        # app.aboutToQuit.connect(self.force_quit) #0816- (!) This caused error after refactor:
        # AttributeError: 'NoneType' object has no attribute 'aboutToQuit'

        layout = QVBoxLayout(self)
        layout.addWidget(te)
        self.start_thread()

    def start_thread(self):
        self.hud_worker = HudWorker()
        self.hud_worker_thread = QThread()
        self.hud_worker.setObjectName('HudWorker')
        self.hud_worker_thread.setObjectName('AlignEMLogger')  # for qThreadName
        self.hud_worker.moveToThread(self.hud_worker_thread)
        # This will start an event loop in the worker thread
        self.hud_worker_thread.start()

    def kill_thread(self):
        self.hud_worker_thread.requestInterruption()
        if self.hud_worker_thread.isRunning():
            self.hud_worker_thread.quit()
            self.hud_worker_thread.wait()
        else:
            print('worker has already exited.')

    def force_quit(self):
        if self.hud_worker_thread.isRunning():
            self.kill_thread()

    @Slot(str, logging.LogRecord)
    def update_status(self, status, record):
        color = self.COLORS.get(record.levelno, 'black')
        s = '<pre><font color="%s">%s</font></pre>' % (color, status)
        self.textedit.appendHtml(s)

    @Slot()
    def manual_update(self):
        level = logging.INFO
        extra = {'qThreadName': ctname()}
        logger.log(level, 'Manually logged!', extra=extra)

    @Slot()
    def post(self, message, level=logging.INFO):
        extra = {'qThreadName': ctname()}
        logger.log(level, message, extra=extra)
        self.textedit.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    @Slot()
    def clear_display(self):
        self.textedit.clear()

def ctname():
    '''Return name of the thread'''
    return QThread.currentThread().objectName()