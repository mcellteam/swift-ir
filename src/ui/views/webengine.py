#!/usr/bin/env python3

from qtpy.QtWebEngineWidgets import QWebEngineView
from qtpy.QtCore import Qt

class WebEngine(QWebEngineView):

    def __init__(self, ID=None):
        QWebEngineView.__init__(self)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)