#!/usr/bin/env python3

from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from qtpy.QtCore import Qt

# Suppressed JS console message substrings (SWR / software renderer noise)
_JS_SUPPRESS = (
    'performance warning: READ-usage buffer',
)

class FilteredWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if any(s in message for s in _JS_SUPPRESS):
            return
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)

class WebEngine(QWebEngineView):

    def __init__(self, ID=None):
        QWebEngineView.__init__(self)
        self.setPage(FilteredWebEnginePage(self))
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)