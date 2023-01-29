#!/usr/bin/env python3
'''
Solid implementation of a thread-safe background GUI logger.

Adapted from:
https://www.oulub.com/en-US/Python/howto.logging-cookbook-a-qt-gui-for-logging
'''
import time
import random
import logging
from qtpy.QtGui import QFont, QTextCursor
from qtpy.QtCore import QObject, QThread, Qt, Signal, Slot, QSize
from qtpy.QtWidgets import QApplication, QWidget, QPlainTextEdit, QVBoxLayout, QSizePolicy


logger = logging.getLogger("hud")
logger.propagate = False # attempt to disable propogation to the root handler

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
        logger.info('Started work', extra=extra)
        i = 1
        # Let the thread run until interrupted. This allows reasonably clean thread termination.
        while not QThread.currentThread().isInterruptionRequested():
            delay = 0.5 + random.random() * 2
            time.sleep(delay)
            level = logging.INFO
            logger.log(level, 'Message after delay of %3.1f: %d', delay, i, extra=extra)
            i += 1

class HeadupDisplay(QWidget):

    COLORS = {
        logging.DEBUG: '#F3F6FB',
        # logging.INFO: '#41FF00',
        # logging.INFO: '#f3f6fb',
        logging.INFO: '#1b1e23',
        logging.WARNING: '#8B4000',
        logging.ERROR: '#FD001B',
        logging.CRITICAL: '#decfbe',
    }

    def __init__(self, app):
        super(HeadupDisplay, self).__init__()
        self.app = app
        self.setFocusPolicy(Qt.NoFocus)
        # self.setMinimumHeight(64)
        self.textedit = te = QPlainTextEdit(self)
        # f = QFont()
        # f.setStyleHint(QFont.Monospace)
        # te.setFont(f)
        te.setReadOnly(True)
        self.handler = h = QtHandler(self.update_status)
        fs = '%(asctime)s [%(levelname)s] %(message)s'
        formatter = logging.Formatter(fs, datefmt='%H:%M:%S')
        h.setFormatter(formatter)
        logger.addHandler(h)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(te)
        self.start_thread()

    def __call__(self, message, level=logging.INFO):
        logger.log(level, message)
        self.textedit.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    def start_thread(self):
        self.hud_worker = HudWorker()
        self.hud_worker_thread = QThread()
        self.hud_worker.setObjectName('HudWorker')
        self.hud_worker_thread.setObjectName('AlignEMLogger')  # for qThreadName
        self.hud_worker.moveToThread(self.hud_worker_thread)
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
        # extra = {'qThreadName': ctname()}
        # logger.log(level, message, extra=extra)
        logger.log(level, message)
        self.textedit.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    @Slot()
    def warn(self, message):
        logger.log(logging.WARNING, message)
        self.textedit.moveCursor(QTextCursor.End)
        QApplication.processEvents()


    def done(self):
        pass


    # def done(self):
    #     txt = self.textedit.toPlainText()
    #     self.textedit.undo()
    #     last_line = txt.split('[INFO]')[-1].lstrip()
    #     if any(x in last_line for x in ['[WARNING]', '[ERROR]']):
    #         return
    #     self.post(last_line + 'done.')
    #     self.textedit.moveCursor(QTextCursor.End)
    #     QApplication.processEvents()


    # def cycle_text(self):
    #     txt = self.textedit.toPlainText()
    #     self.textedit.undo()
    #     last_line = txt.split('[INFO]')[-1].lstrip()
    #     self.post(last_line + 'done.')
    #     self.textedit.moveCursor(QTextCursor.End)
    #     QApplication.processEvents()

    @Slot()
    def clear_display(self):
        self.textedit.clear()

    @Slot()
    def rmline(self):
        self.textedit.undo()

    def set_theme_default(self):

        self.textedit.setStyleSheet("""
            background-color:  #141414;
            border-style: inset;
            border-color: #d3dae3; /* light off-white */
            border-width: 0px;
            border-radius: 2px;
            font-size: 11px;
            margin: 0px 0px 0px 0px;
        """)


    def set_theme_light(self):

        self.textedit.setStyleSheet("""
            color: #ffa213;
            /*background-color:  #8bb8e8;*/
            /*background-color:  #ede9e8;*/
            background-color:  #ffffff;
            /*border-style: solid;*/
            border-style: inset;
            border-color: #1b1e23;
            border-width: 1px;
            border-radius: 4px;  
            font-size: 11px;          
            margin: 0px 0px 0px 0px;
        """)

    def sizeHint(self):
        # if cfg.main_window:
        #     width = int(cfg.main_window.width() / 2)
        # else:
        #     width = int(cfg.WIDTH / 2)
        # width = 300
        return QSize(800, 400)



def ctname():
    '''Return name of the thread'''
    return QThread.currentThread().objectName()