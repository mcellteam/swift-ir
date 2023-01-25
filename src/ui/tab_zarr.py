#!/usr/bin/env python3

import os, sys, json, logging, inspect, copy
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QSplitter, QVBoxLayout, QStyleOption, QStyle
from qtpy.QtCore import Qt, QSize, QRect, QUrl
from qtpy.QtGui import QPainter, QFont
from qtpy.QtWebEngineWidgets import *
from src.ui.file_browser import FileBrowser
from src.ui.ui_custom import VerticalLabel
import src.config as cfg
from src.ng_host_slim import NgHostSlim
from src.helpers import print_exception

logger = logging.getLogger(__name__)

class ZarrTab(QWidget):

    def __init__(self,
                 parent=None,
                 *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        logger.info('')
        self.parent = parent
        self.path = None
        self.zarray = None
        self.shape = None
        self.nSections = None
        self.chunkshape = None
        self.ng_layout = '4panel'
        cfg.main_window._ng_layout_switch = 0
        cfg.main_window._cmbo_ngLayout.setCurrentText(self.ng_layout)
        cfg.main_window._ng_layout_switch = 1
        self.initUI()


    def initUI(self):
        self._fb = FileBrowser()
        self._webEngine = QWebEngineView()
        self.initSpecialSettings(self._webEngine)
        self._webEngine.hide()
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._webEngine)
        self._splitter.addWidget(self._fb)
        self._splitter.setSizes([1000,100])
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._splitter)
        self.setLayout(vbl)


    def initNeuroglancer(self, layout='4panel'):
        cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
        # cfg.main_window.reload_ng_layout_combobox(initial_layout='4panel')
        logger.info(f'caller: {inspect.stack()[1].function}')
        cfg.ng_worker = NgHostSlim(parent=self, project=False)
        cfg.ng_worker.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
        cfg.main_window.updateMenus()

    def updateNgLayer(self):
        state = copy.deepcopy(cfg.viewer.state)
        state.position[0] = cfg.data.layer()
        cfg.viewer.set_state(state)


    def updateNeuroglancer(self, matchpoint=None):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        cfg.ng_worker.initViewer()
        self._webEngine.setUrl(QUrl(cfg.ng_worker.url()))
        self._webEngine.setFocus()


    def openViewZarr(self):
        logger.info(f'caller: {inspect.stack()[1].function}')
        cfg.main_window.set_status('Opening Zarr...')
        logger.info('(openViewZarr) Going To Open Zarr ...')
        path = self._fb.getSelectionPath()
        logger.info(f'path: {path}')
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
        logger.info(f'array shape: {self.shape}, chunk shape: {self.chunkshape} ')

        cfg.main_window._sectionSlider.setRange(0, self.nSections - 1)
        cfg.ng_worker.path = path
        cfg.ng_worker.initViewer()
        cur_index = cfg.main_window._tabsGlob.currentIndex()
        cfg.main_window._tabsGlob.setTabText(cur_index, 'File: ' + os.path.basename(path))
        cfg.main_window._cmbo_ngLayout.setCurrentText('4panel')
        cfg.main_window._jumpToLineedit.setText('0')
        self._webEngine.setUrl(QUrl(str(cfg.viewer)))
        self._webEngine.show()
        self._webEngine.setFocus()
        # self.fb.hideFb()
        # self._fb.showFbButton()
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