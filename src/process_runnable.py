#!/usr/bin/env python3

import logging

from qtpy.QtCore import QRunnable, QThreadPool

# https://stackoverflow.com/questions/47560399/run-function-in-the-background-and-update-ui
# a class that behaves the same as Process:

__all__ = ['ProcessRunnable']


logger = logging.getLogger(__name__)
class ProcessRunnable(QRunnable):
    def __init__(self, target, args):
        QRunnable.__init__(self)
        self.t = target
        self.args = args

    def run(self):
        self.t(*self.args)

    def start(self):
        QThreadPool.globalInstance().start(self)
