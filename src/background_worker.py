#!/usr/bin/env python3

import sys
import logging
import traceback
from qtpy.QtCore import Slot
from qtpy.QtCore import Signal
from qtpy.QtCore import QObject
from qtpy.QtCore import QRunnable
import src.config as cfg
from src.helpers import print_exception

__all__ = ['BackgroundWorker']

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.
    Supported signals are:

    finished - No data
    error - tuple (exctype, value, traceback.format_exc() )
    result - object data returned from processing, anything
    progress - int indicating % progress
    '''

    # https://stackoverflow.com/questions/29007619/python-typeerror-pickling-an-authenticationstring-object-is-disallowed-for-sec
    def __getstate__(self):
        """called when pickling - this hack allows subprocesses to
           be spawned without the AuthenticationString raising an error"""
        state = self.__dict__.copy()
        conf = state['_config']
        if 'authkey' in conf:
            del conf['authkey']
            conf['authkey'] = bytes(conf['authkey'])
        return state

    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int, name='progressSignal')


class BackgroundWorker(QRunnable, status=None):
    '''
    BackgroundWorker thread
    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    :param callback: The function callback to run on this worker thread. Supplied args and kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    Doc:
    QThreadPool manages and recyles individual QThread objects to help reduce thread creation costs in
    programs that use threads. Each src application has one global QThreadPool object, which can be
    accessed by calling globalInstance() .

    To use one of the QThreadPool threads, subclass QRunnable and implement the run() virtual function.
    Then create an object of that class and pass it to start() .

    QThreadPool deletes the QRunnable automatically by default.

    QThreadPool supports executing the same QRunnable more than once by calling tryStart (this) from within run()

    Note that QThreadPool is a low-level class for managing threads, see the src Concurrent module
    for higher level alternatives.

    '''

    def __init__(self, fn, *args, **kwargs):
        super(BackgroundWorker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.signals.progress.__hash__()
        self.signals.progress.__str__()

        # Add the callback to our kwargs
        '''If 'progress_callback' is provided as a parameter of the function passed into BackgroundWorker, it will be assigned
        the value -> self.signals.progress'''
        self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        '''
        Initialise the runner functiosn with passed args, kwargs.
        '''
        logger.info("Running Background Worker...")

        if self.status != None:
            cfg.main_window.set_status(self.status)

        cfg.main_window._working = True
        cfg.main_window.pbar.show()
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            # print('BackgroundWorker.run traceback:')
            print_exception()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()
            cfg.main_window._working = False
            cfg.main_window.pbar.hide()
            cfg.main_window.set_idle()
