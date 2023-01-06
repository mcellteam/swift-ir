#!/usr/bin/env python3

import os, sys, json, logging, inspect
import neuroglancer as ng
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QSplitter, QVBoxLayout, QHBoxLayout, \
    QSizePolicy, QPushButton, QComboBox, QSpinBox, QStyleOption, QStyle
from qtpy.QtCore import Qt, QSize, QRect, QUrl
from qtpy.QtGui import QPainter, QFont
from qtpy.QtWebEngineWidgets import *

from src.ui.file_browser import FileBrowser
from src.ui.ui_custom import VerticalLabel
import src.config as cfg
from src.ng_host import NgHost
from src.ng_host_slim import NgHostSlim
from src.helpers import print_exception

logger = logging.getLogger(__name__)

class ZarrTab(QWidget):

    def __init__(self,
                 key,
                 parent=None,
                 *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        logger.info('')
        self.key = key
        self.parent = parent
        self.path = None
        self.zarray = None
        self.shape = None
        self.nSections = None
        self.chunkshape = None
        self.ng_layout = 'xy'
        self.initUI()
        self._fb.getOpenButton().clicked.connect(self.openViewZarr)


    def initUI(self):
        self._fb = FileBrowser()
        self._webEngine = QWebEngineView()
        self._webEngine.hide()
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._webEngine)
        self._splitter.addWidget(self._fb)
        self._splitter.setSizes([1000,200])
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._splitter)
        self.setLayout(vbl)


    def initNeuroglancer(self):
        logger.info('')
        logger.info(f'caller: {inspect.stack()[1].function}')
        cfg.ng_worker = NgHostSlim(parent=self, project=False)


    def openViewZarr(self):
        logger.info(f'caller: {inspect.stack()[1].function}')
        cfg.main_window.set_status('Opening Zarr...')
        logger.info('(openViewZarr) Going To Open Zarr...')
        path = self._fb.getSelectionPath()
        logger.info(f'path: {path}')
        cfg.ng_worker.path = path
        try:
            with open(os.path.join(path, '.zarray')) as j:
                self.zarray = json.load(j)
        except:
            logger.warning("'.zarray' Not Found. Invalid Path.")
            cfg.main_window.warn("'.zarray' Not Found. Invalid Path.")
            return
        self.shape = self.zarray['shape']
        self.chunkshape = self.zarray['chunks']
        self.nSections = self.shape[0]
        cfg.main_window._sectionSlider.setRange(0, self.nSection - 1)
        logger.info(f'array shape: {self.shape}, chunk shape: {self.chunkshape} ')
        cfg.ng_worker.initViewer()
        cur_index = cfg.main_window._tabsGlob.currentIndex()
        cfg.main_window._tabsGlob.setTabText(cur_index, 'Zarr: ' + os.path.basename(path))
        cfg.main_window._cmbo_ngLayout.setCurrentText('4panel')
        self._webEngine.setUrl(QUrl(str(cfg.viewer)))
        self._webEngine.show()
        self._webEngine.setFocus()
        # self.fb.hideFb()
        self._fb.showFbButton()
        cfg.main_window.set_idle()


    def initSpecialSettings(self, webengine):
        logger.info('')
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)


    def paintEvent(self, pe):
        '''Enables widget to be style-ized'''
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        s = self.style()
        s.drawPrimitive(QStyle.PE_Widget, opt, p, self)


    def sizeHint(self):
        return QSize(1000,1000)


if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    w = ZarrTab(key=0)
    main_window.setCentralWidget(w)
    main_window.show()
    sys.exit(app.exec_())