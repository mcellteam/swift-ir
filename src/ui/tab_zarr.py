#!/usr/bin/env python3

import os
import json
import logging
from qtpy.QtWidgets import QWidget, QVBoxLayout
from qtpy.QtCore import QUrl
from qtpy.QtWebEngineWidgets import *
from src.viewer_zarr import ZarrViewer
import src.config as cfg

__all__ = ['ZarrTab']

log = logging.getLogger(__name__)

class ZarrTab(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        log.info('')
        self.parent = parent
        self.path = path
        self.viewer = cfg.emViewer = ZarrViewer(path=path)
        self.webengine = QWebEngineView()
        self.load()


        with open(os.path.join(path, '.zarray')) as j:
            self.zarray = json.load(j)
        self.shape      = self.zarray['shape']
        self.chunkshape = self.zarray['chunks']
        self.zdim       = self.shape[0]

        cfg.main_window._sectionSlider.setRange(0, self.zdim - 1)
        cfg.main_window._jumpToLineedit.setText('0')
        # cfg.main_window.comboboxNgLayout.setCurrentText('4panel')

        self.initUI()

    def load(self):
        self.webengine.setUrl(QUrl(self.viewer.url()))

    def initUI(self):
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.webengine)
        self.setLayout(vbl)



