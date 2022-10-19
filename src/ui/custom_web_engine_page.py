#!/usr/bin/env python3
'''
QtWebEngine Page Class.

'''

from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from qtpy.QtCore import QEventLoop

__all__ = ['CustomWebEnginePage']

class CustomWebEnginePage(QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation
    Depends on QWebEnginePage / QWebEnginePage since Qt5.4"""
    # Store external windows.
    external_windows = []

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if (_type == QWebEnginePage.NavigationTypeLinkClicked and url.host() != 'github.com'):
            # Pop up external links into a new window.
            w = QWebEngineView()
            w.setUrl(url)
            w.show()

            # Keep reference to external window, so it isn't cleared up.
            self.external_windows.append(w)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)

def render(source_html):
    """Fully render HTML, JavaScript and all."""

    class Render(QWebEngineView):
        def __init__(self, html):
            self.html = None
            QWebEngineView.__init__(self)
            self.loadFinished.connect(self._loadFinished)
            self.setHtml(html)
            while self.html is None:
                self.app.processEvents(QEventLoop.ExcludeUserInputEvents | QEventLoop.ExcludeSocketNotifiers | QEventLoop.WaitForMoreEvents)
            self.app.quit()

        def _callable(self, data):
            self.html = data

        def _loadFinished(self, result):
            self.page().toHtml(self._callable)

    return Render(source_html).html

import requests
sample_html = requests.get("https://github.com/google/neuroglancer").text
print(render(sample_html))