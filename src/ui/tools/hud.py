#!/usr/bin/env python3

'''
Solid implementation of a thread-safe background GUI logger.

Adapted from:
https://www.oulub.com/en-US/Python/howto.logging-cookbook-a-qt-gui-for-logging

self.textedit

a = cfg.mw.hud.te.toPlainText()
'''
import inspect
import logging
import random
import time

from qtpy.QtCore import QObject, QThread, Qt, Signal, Slot, QSize
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout

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
            # level = logging.INFO
            level = logging.INFO
            logger.log(level, 'Message after delay of %3.1f: %d', delay, i, extra=extra)
            i += 1

class HeadupDisplay(QWidget):

    COLORS = {
        logging.DEBUG: '#F3F6FB',
        logging.INFO: '#1b1e23',
        logging.WARNING: '#8B4000',
        logging.ERROR: '#FD001B',
        logging.CRITICAL: '#decfbe',
    }

    COLORS_OVERLAY = {
        logging.DEBUG: '#F3F6FB',
        logging.INFO: '#141414',
        logging.WARNING: '#8B4000',
        logging.ERROR: '#FD001B',
        logging.CRITICAL: '#decfbe',
    }

    COLORS_DARK = {
        logging.DEBUG: '#F3F6FB',
        logging.INFO: '#F3F6FB',
        # logging.INFO: '#141414',
        logging.WARNING: '#ffa756',
        logging.ERROR: '#FD001B',
        logging.CRITICAL: '#decfbe',
    }

    def __init__(self, app, overlay=False):
        super(HeadupDisplay, self).__init__()

        self.app = app
        self._overlay = overlay
        self.setFocusPolicy(Qt.NoFocus)
        # self.setMinimumHeight(64)
        self.te = te = QPlainTextEdit(self)
        self.te.setReadOnly(False)
        self.te.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        # f = QFont()
        # f.setStyleHint(QFont.Monospace)
        # te.setFont(f)
        if overlay:
            self.te.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.te.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.handler = h = QtHandler(self.update_status)
        fs = '%(asctime)s [%(levelname)s] %(message)s'
        formatter = logging.Formatter(fs, datefmt='%H:%M:%S')
        h.setFormatter(formatter)
        logger.addHandler(h)
        layout = QVBoxLayout(self)
        # layout.setContentsMargins(2,2,2,2)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(te)
        self.start_thread()
        self.theme = None
        # self.layout().setAlignment(Qt.AlignBottom)
        # self.setStyleSheet("""
        # padding: 0px;
        # margin: 0px;
        # border-width: 0px;
        # """)
        self.messages = []

        self.resize(self.sizeHint())

    def __call__(self, message, level=logging.INFO):
        logger.log(level, message)
        self.te.moveCursor(QTextCursor.End)

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
        if self.theme == 'overlay':
            color = self.COLORS_OVERLAY.get(record.levelno, 'black')
        elif self.theme == 'dark':
            color = self.COLORS_DARK.get(record.levelno, 'black')
        else:
            color = self.COLORS.get(record.levelno, 'black')
        s = '<pre><font color="%s">%s</font></pre>' % (color, status)
        self.te.appendHtml(s)
        self.te.moveCursor(QTextCursor.End)
        self.update()

    @Slot()
    def manual_update(self):
        level = logging.INFO
        extra = {'qThreadName': ctname()}
        logger.log(level, 'Manually logged!', extra=extra)
        self.te.moveCursor(QTextCursor.End)
        self.update()

    @Slot()
    def post(self, message, level=logging.INFO):
        # extra = {'qThreadName': ctname()}
        # logger.log(level, message, extra=extra)
        logger.log(level, message)
        self.te.moveCursor(QTextCursor.End)
        self.update()

    @Slot()
    def warn(self, message):
        logger.log(logging.WARNING, message)
        self.te.moveCursor(QTextCursor.End)
        self.update()


    # def done(self):
    #     pass


    def done(self):
        caller = inspect.stack()[1].function
        txt = self.te.toPlainText()
        last_line = txt.split('[INFO]')[-1].lstrip()
        # print(f"\nlast_line: {last_line}\nany? {any(x in last_line for x in ['[WARNING]', '[ERROR]'])}\nlast 3: {last_line[-3:]}\n")


        if any(x in last_line for x in ['[WARNING]', '[ERROR]']):
            return
        if last_line[-3:] != '...':
            return

        # if cfg.project_tab:
        #     cfg.project_tab.hud_overlay.textedit.undo()
        #     cfg.project_tab.hud_overlay.post(last_line + 'done.')
        #     cfg.project_tab.hud_overlay.textedit.moveCursor(QTextCursor.End)

        self.te.undo()
        self.post(last_line + f'done ({caller})')
        # self.post(last_line + 'done(%level).' % caller)
        self.te.moveCursor(QTextCursor.End)
        self.update()
        # pass


    # def cycle_text(self):
    #     txt = self.te.toPlainText()
    #     self.te.undo()
    #     last_line = txt.split('[INFO]')[-1].lstrip()
    #     self.post(last_line + 'done.')
    #     self.te.moveCursor(QTextCursor.End)
    #     QApplication.processEvents()

    @Slot()
    def clear_display(self):
        self.te.clear()

    @Slot()
    def rmline(self):
        self.te.undo()

    def set_theme_default(self):
        self.theme = 'default'

        self.te.setStyleSheet("""
            background-color:  #141414;
            border-style: inset;
            border-color: #d3dae3; /* light off-white */
            border-width: 0px;
            border-radius: 2px;
            font-size: 9px;
            font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
            margin: 0px 0px 0px 0px;
        """)

    def set_theme_dark(self):
        self.theme = 'dark'
        self.te.setStyleSheet("""
            background-color:  #141414;
            color: #f3f6fb;
            /*border-style: inset;*/
            /*border-color: #d3dae3;  light off-white */
            border-width: 0px;
            border-radius: 2px;
            font-size: 9px;
            font-family: 'Andale Mono','Ubuntu Mono',  monospace;
            margin: 0px 0px 0px 0px;
        """)


    def set_theme_overlay(self):
        self.theme = 'overlay'

        self.te.setStyleSheet("""
            color: #ffa213;
            background-color: rgba(255,255,255,0.65);
            /*border-style: solid;*/
            border-style: inset;
            border-color: #1b1e23;
            border-width: 1px;
            border-bottom-left-radius: 4px;
            border-bottom-right-radius: 4px;
            font-size: 7px;
            font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
            margin: 0px 0px 0px 0px;
        """)

    #
    def sizeHint(self):
        # width = int(cfg.main_window.width() / 2) - 10
        # return QSize(width, 120)
        return QSize(800, 100)





def ctname():
    '''Return name of the thread'''
    return QThread.currentThread().objectName()