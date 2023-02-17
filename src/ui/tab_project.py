#!/usr/bin/env python3

'''TODO This needs to have columns for indexing and section name (for sorting!)'''

import os, sys, logging, inspect, copy, time, warnings
# from math import log10
from math import log2, sqrt
import neuroglancer as ng
import numpy as np
import qtawesome as qta
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStyleOption, \
    QStyle, QTabBar, QTabWidget, QGridLayout, QTreeView, QSplitter, QTextEdit, QSlider, QPushButton, QSizePolicy, \
    QListWidget, QListWidgetItem, QMenu, QAction, QFormLayout, QGroupBox, QRadioButton, QButtonGroup
from qtpy.QtCore import Qt, QSize, QRect, QUrl, Signal, QEvent
from qtpy.QtGui import QPainter, QFont, QPixmap, QColor
from qtpy.QtWebEngineWidgets import *
import src.config as cfg
from src.helpers import getOpt
from src.viewer_em import EMViewer
from src.viewer_ma import MAViewer
from src.helpers import print_exception
from src.ui.snr_plot import SnrPlot
from src.ui.mini_view import MiniView
from src.ui.widget_area import WidgetArea
from src.ui.project_table import ProjectTable
from src.ui.models.json_tree import JsonModel
from src.ui.sliders import DoubleSlider
from src.ui.thumbnails import Thumbnail, SnrThumbnail
from src.ui.toggle_switch import ToggleSwitch


__all__ = ['ProjectTab']

logger = logging.getLogger(__name__)

class ProjectTab(QWidget):

    def __init__(self,
                 parent,
                 path=None,
                 datamodel=None):
        super().__init__(parent)
        logger.info(f'Initializing Project Tab...\nID(datamodel): {id(datamodel)}, Path: {path}')
        self.parent = parent
        self.path = path
        self.viewer = None
        self.datamodel = datamodel
        self.setUpdatesEnabled(True)
        self.webengine = QWebEngineView()
        # self.webengine.setMouseTracking(True)
        # self.webengine.setFocusPolicy(Qt.StrongFocus)
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        self.initUI_tab_widget()
        self._tabs.currentChanged.connect(self._onTabChange)
        self.manAlignBufferRef = []
        self.manAlignBufferBase = []
        self.mp_colors = ['#f3e375', '#5c4ccc', '#800000',
                          '#aaa672', '#152c74', '#404f74',
                          '#f3e375', '#5c4ccc', '#d6acd6',
                          '#aaa672', '#152c74', '#404f74']

        self.bookmark_tab = 0
        self.MA_ref_cscale = None
        self.MA_ref_zoom = None
        self.MA_base_cscale = None
        self.MA_base_zoom = None

    def _onTabChange(self, index=None):
        if index == None:
            index = self._tabs.currentIndex()
        # if index == 0:
        #     self.updateNeuroglancer() # Don't update neuroglancer -> maintain emViewer state
        if index == 1:
            # self.project_table.setScaleData()
            # self.project_table.setScaleData() #not sure why this is needed twice
            pass
        if index == 2:
            # self.updateJsonWidget()
            self.treeview_model.jumpToLayer()
        if index == 3:
            self.snr_plot.data = cfg.data
            self.snr_plot.initSnrPlot()
            self.updatePlotThumbnail()
        # QApplication.processEvents()
        # self.repaint()


    def shutdownNeuroglancer(self):
        logger.critical('')
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if ng.is_server_running():
            ng.server.stop()
            # time.sleep(.5)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)


    def initNeuroglancer(self):
        caller = inspect.stack()[1].function
        if cfg.MP_MODE:
            # cfg.main_window.comboboxNgLayout.setCurrentText('xy')
            self.MA_viewer_ref = MAViewer(role='ref', webengine=self.MA_webengine_base)
            self.MA_viewer_base = MAViewer(role='base', webengine=self.MA_webengine_ref)
            self.MA_viewer_stage = EMViewer(force_xy=True, webengine=self.MA_webengine_Stage)
            self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
            self.MA_viewer_ref.signals.ptsChanged.connect(self.updateMAlistRef)
            self.MA_viewer_base.signals.ptsChanged.connect(self.updateMAlistBase)
            self.MA_viewer_ref.shared_state.add_changed_callback(self.updateMA_base_state)
            self.MA_viewer_base.shared_state.add_changed_callback(self.updateMA_ref_state)

            #Critical Only connect to one of the two interconnected widgets. Do not connect stage.
            self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
            # self.MA_viewer_base.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
            self.MA_viewer_stage.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
            self.MA_viewer_ref.signals.ptsChanged.connect(self.updateMAlistRef)
            self.MA_viewer_base.signals.ptsChanged.connect(self.updateMAlistBase)
            self.MA_viewer_ref.signals.stateChanged.connect(self.updateMA_base_state)
            self.MA_viewer_base.signals.stateChanged.connect(self.updateMA_ref_state)
            self.MA_viewer_base.initViewer()
            self.MA_viewer_ref.initViewer()
            self.MA_viewer_stage.initViewer()
            #----
            # self.MA_webengine_base.setUrl(QUrl(self.MA_viewer_base.url()))
            # self.MA_webengine_ref.setUrl(QUrl(self.MA_viewer_ref.url()))
            # self.MA_webengine_Stage.setUrl(QUrl(cfg.emViewer.url()))
            return
        # logger.critical(f'caller: {caller}\n\n\n')
        # self.shutdownNeuroglancer()
        if cfg.data.is_aligned_and_generated():
            cfg.main_window.corr_spot_thumbs.setVisible(getOpt('ui,SHOW_CORR_SPOTS'))
        else:
            cfg.main_window.corr_spot_thumbs.hide()

        if caller != '_onGlobTabChange':
            logger.critical(f'\n\nInitializing Neuroglancer (caller: {inspect.stack()[1].function})...\n')
            cfg.emViewer = self.viewer = EMViewer(webengine=self.webengine)
            self.updateNeuroglancer()
            cfg.emViewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
            cfg.emViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
            # cfg.emViewer.signals.mpUpdate.connect(cfg.main_window.dataUpdateWidgets)
            # self.webengine.setUrl(QUrl(cfg.emViewer.get_viewer_url())) #----
            cfg.main_window.dataUpdateWidgets() #0204+


    def updateNeuroglancer(self):
        caller = inspect.stack()[1].function
        logger.info(f'Updating Neuroglancer Viewer (caller: {caller})')
        if cfg.MP_MODE:
            # cfg.main_window.comboboxNgLayout.setCurrentText('xy')
            # self.MA_viewer_ref = MAViewer(role='ref')
            # self.MA_viewer_base = MAViewer(role='base')
            # self.MA_viewer_stage = MAViewer(role='base')
            self.MA_viewer_base.initViewer()
            self.MA_viewer_ref.initViewer()
            self.MA_viewer_stage.initViewer()
            #----
            # self.MA_webengine_base.setUrl(QUrl(self.MA_viewer_base.url()))
            # self.MA_webengine_ref.setUrl(QUrl(self.MA_viewer_ref.url()))
            # self.MA_webengine_Stage.setUrl(QUrl(cfg.emViewer.url()))
            return
            # self.setZmag(val=15)
        else:
            cfg.emViewer.initViewer()


        # if not cfg.MP_MODE:
        #     show = getOpt('neuroglancer,SHOW_ALIGNMENT_DETAILS')
        #     self._widgetArea_details.setVisible(show)
        #     if show:
        #         self._transformationWidget.setVisible(cfg.data.is_aligned_and_generated())

        # self.slotUpdate
        # Slider()

        state = copy.deepcopy(cfg.emViewer.state)
        for layer in state.layers:
            # layer.shaderControls['normalized'] = {
            #     'range': np.array(cfg.main_window.norFsource thumbsmalizedSlider.getRange())
            # }
            layer.shaderControls['normalized'] = {'range': np.array(cfg.data.normalize())}
            layer.shaderControls['brightness'] = cfg.data.brightness()
            layer.shaderControls['contrast'] = cfg.data.contrast()
            # layer.volumeRendering = True

        cfg.emViewer.set_state(state)
        url = cfg.emViewer.get_viewer_url()
        logger.info('setting URL...\n%s' % url)
        self.webengine.setUrl(QUrl(url))



    def get_layout(self, requested=None):
        if requested == None:
            requested = cfg.data['ui']['ng_layout']
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        return mapping[requested]

    # def addToState(self):
    #     state = copy.deepcopy(cfg.emViewer.state)
    #     state.relative_display_scales = {"z": 10}
    #     cfg.emViewer.set_state(state)
    #     cfg.LV.invalidate()

    def setNeuroglancerUrl(self):
        self.webengine.setUrl(QUrl(cfg.emViewer.get_viewer_url()))


    def updateNgLayer(self):
        state = copy.deepcopy(cfg.emViewer.state)
        state.position[0] = cfg.data.layer()
        cfg.emViewer.set_state(state)


    def getBrowserSize(self):
        return self.webengine.geometry().getRect()



    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')

        self.webengine.loadFinished.connect(lambda: print('QWebengineView Load Finished!'))
        # this fixes detailsSection not displaying immediately on start project
        self.webengine.loadFinished.connect(cfg.main_window.dataUpdateWidgets)



        # self.webengine.loadFinished.connect(self.resetSliderZmag)
        # self.webengine.loadFinished.connect(self.slotUpdateZoomSlider)
        # self.webengine.loadFinished.connect(lambda val=21: self.setZmag(val=val))


        # self.webengine.loadProgress.connect(lambda progress: print(f'QWebengineView Load Progress: {progress}'))
        # self.webengine.urlChanged.connect(lambda terminationStatus:
        #                              print(f'QWebengineView Render Process Terminated!'
        #                                    f' terminationStatus:{terminationStatus}'))

        # self.webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        # self.webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        self.ng_browser_container = QWidget()
        self.ng_browser_container.setObjectName('ng_browser_container')
        self.ng_gl = QGridLayout()
        self.ng_gl.addWidget(self.webengine, 0, 0, 4, 5)
        self._overlayRect = QWidget()
        self._overlayRect.setObjectName('_overlayRect')
        self._overlayRect.setStyleSheet("""background-color: rgba(0, 0, 0, 0.5);""")
        self._overlayRect.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayRect.hide()
        self.ng_gl.addWidget(self._overlayRect, 0, 0, 4, 5)
        self._overlayLab = QLabel()
        self._overlayLab.setStyleSheet("""color: #FF0000; font-size: 28px;""")
        self._overlayLab.hide()


        '''AFM/CAFM Widget'''
        self.afm_widget_ = QTextEdit()
        self.afm_widget_.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.afm_widget_.setObjectName('_tool_afmCafm')
        self.afm_widget_.setReadOnly(True)
        self._transformationWidget = QWidget()
        # self._transformationWidget.setFixedSize(180,80)
        self._transformationWidget.setFixedWidth(170)
        self._transformationWidget.setMaximumHeight(70)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        # vbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignBaseline)
        vbl.addWidget(self.afm_widget_)
        self._transformationWidget.setLayout(vbl)


        self._overlayBottomLeft = QLabel()
        self._overlayBottomLeft.setObjectName('_overlayBottomLeft')
        self._overlayBottomLeft.hide()
        self.ng_gl.addWidget(self._overlayLab, 0, 0, 4, 5,alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.ng_gl.addWidget(self._overlayBottomLeft, 0, 0, 4, 5, alignment=Qt.AlignLeft | Qt.AlignBottom)
        # self.ng_gl.addWidget(cfg.main_window._tool_afmCafm, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.ng_gl.setContentsMargins(0, 0, 0, 0)
        self.ngVertLab = VerticalLabel('Neuroglancer 3DEM View')
        self.ngVertLab.setObjectName('label_ng')

        dSize = 120

        self.DetailsContainer = QWidget()
        # self.DetailsContainer.setWindowFlags(Qt.FramelessWindowHint)
        # self.DetailsContainer.setAttribute(Qt.WA_TransparentForMouseEvents)
        # self.DetailsContainer.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.DetailsContainer.setAutoFillBackground(False)
        self.DetailsContainer.setAttribute(Qt.WA_TranslucentBackground, True)
        self.DetailsContainer.setStyleSheet("""background-color: rgba(255, 255, 255, 0);""")

        self.detailsCorrSpots = QWidget()
        # self.detailsCorrSpots.setWindowFlags(Qt.FramelessWindowHint)
        # self.detailsCorrSpots.setAttribute(Qt.WA_TransparentForMouseEvents)
        # self.detailsCorrSpots.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.corrSpotClabel = ClickLabel("<b>Corr.&nbsp;Spot</b>")
        self.corrSpotClabel.setStyleSheet("background-color: rgba(255, 255, 255, 0);color: #f3f6fb;")
        self.corrSpotClabel.setAutoFillBackground(False)
        self.corrSpotClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        def fn():
            self.detailsCorrSpots.setVisible(self.detailsCorrSpots.isHidden())
            self.corrSpotClabel.setText(
                ("<b><span style='color: #ffe135;'>Corr.&nbsp;Spot</span></b>",
                 "<b>Corr.&nbsp;Spot</b>")[self.detailsCorrSpots.isHidden()])
            # if not cfg.data.is_aligned_and_generated():
            #     self.detailsCorrSpots.hide()
            #     self.corrSpotClabel.hide()
        self.corrSpotClabel.clicked.connect(fn)
        self.corrSpotClabel.clicked.connect(cfg.main_window.dataUpdateWidgets)

        self.cs0 = SnrThumbnail(parent=self)
        self.cs1 = SnrThumbnail(parent=self)
        self.cs2 = SnrThumbnail(parent=self)
        self.cs3 = SnrThumbnail(parent=self)

        gl = QGridLayout()
        gl.setSpacing(0)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.addWidget(self.cs0, 0, 0)
        gl.addWidget(self.cs1, 0, 1)
        gl.addWidget(self.cs2, 1, 0)
        gl.addWidget(self.cs3, 1, 1)
        self.csALL = QWidget()
        self.csALL.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.csALL.setLayout(gl)

        self.cspotSlider = QSlider(Qt.Orientation.Vertical)
        self.cspotSlider.setRange(36,256)
        start_size = 120
        self.cspotSlider.setValue(start_size)
        self.cspotSlider.setFixedSize(QSize(16,56))
        self.csALL.setFixedSize(start_size, start_size)

        self.cspotSlider.sliderReleased.connect(lambda: self.csALL.setFixedSize(
            QSize(self.cspotSlider.value(), self.cspotSlider.value())))
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.csALL, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.cspotSlider, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.detailsCorrSpots.setLayout(hbl)
        self.detailsCorrSpots.hide()

        self.detailsSection = QLabel()
        self.detailsSection.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSection.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSection.setMaximumHeight(100)
        self.detailsSection.setMinimumWidth(210)
        # self.detailsSection.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsClabel = ClickLabel("<b><span style='color: #ffe135;'>Section</span></b>")
        self.detailsClabel.setStyleSheet("color: #f3f6fb;")
        self.detailsClabel.setAutoFillBackground(False)
        self.detailsClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.detailsClabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        def fn():
            self.detailsSection.setVisible(self.detailsSection.isHidden())
            self.detailsClabel.setText(
                ("<b><span style='color: #ffe135;'>Section</span></b>",
                 "<b>Section</b>")[self.detailsSection.isHidden()])
            cfg.main_window.dataUpdateWidgets()
        self.detailsClabel.clicked.connect(fn)
        self.detailsSection.setWordWrap(True)
        self.detailsSection.setStyleSheet("""
            font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;
            font-size: 10px;
            background-color: rgba(0,0,0,.24);
            color: #f3f6fb;
            padding: 3px;
            """)
        # self.detailsSection.hide()


        self.detailsAFM = QLabel()
        self.detailsAFM.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsAFM.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsAFM.setMaximumHeight(100)
        # self.detailsAFM.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.afmClabel = ClickLabel('<b>Affine</b>')
        self.afmClabel.setStyleSheet("background-color: rgba(255, 255, 255, 0); color: #f3f6fb;")
        self.afmClabel.setAutoFillBackground(False)
        self.afmClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.afmClabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        def fn():
            self.detailsAFM.setVisible(self.detailsAFM.isHidden())
            self.afmClabel.setText(
                ("<b><span style='color: #ffe135;'>Affine</span></b>",
                 "<b>Affine</b>")[self.detailsAFM.isHidden()])
            cfg.main_window.dataUpdateWidgets()
        self.afmClabel.clicked.connect(fn)
        self.detailsAFM.setWordWrap(True)
        self.detailsAFM.setStyleSheet("""
            font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;
            font-size: 10px;
            background-color: rgba(0,0,0,.24);
            color: #f3f6fb;
            padding: 3px;
            """)
        self.detailsAFM.hide()


        self.detailsSNR = QLabel()
        self.detailsSNR.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSNR.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSNR.setMaximumHeight(100)
        self.snrClabel = ClickLabel('<b>SNR</b>')
        self.snrClabel.setStyleSheet("background-color: rgba(255, 255, 255, 0); color: #f3f6fb;")
        self.snrClabel.setAutoFillBackground(False)
        self.snrClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.snrClabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        def fn():
            self.detailsSNR.setVisible(not self.detailsSNR.isVisible())
            self.snrClabel.setText(
                ("<b><span style='color: #ffe135;'>SNR</span></b>",
                 "<b>SNR</b>")[self.detailsSNR.isHidden()])
            cfg.main_window.dataUpdateWidgets()
        self.snrClabel.clicked.connect(fn)
        self.detailsSNR.setWordWrap(True)
        self.detailsSNR.setStyleSheet("""
            font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;
            font-size: 10px;
            background-color: rgba(0,0,0,.24);
            color: #f3f6fb;
            padding: 3px;
            """)
        # self.detailsSNR.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.detailsSNR.hide()

        vbl = QVBoxLayout()
        vbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(0)

        self.labelsWidget = QWidget()
        self.labelsWidget.setFixedHeight(20)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(8, 0, 8, 0)
        hbl.addWidget(self.detailsClabel)
        hbl.addWidget(QLabel("<span style='font-size: 15px; color: #f3f6fb; "
                             "font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;'>&#183;</span>"))
        hbl.addWidget(self.afmClabel)
        hbl.addWidget(QLabel("<span style='font-size: 15px; color: #f3f6fb; "
                             "font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;'>&#183;</span>"))
        hbl.addWidget(self.snrClabel)
        hbl.addWidget(QLabel("<span style='font-size: 15px; color: #f3f6fb; "
                             "font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;'>&#183;</span>"))
        hbl.addWidget(self.corrSpotClabel)
        self.labelsWidget.setLayout(hbl)


        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # spreadW.setLayout(vbl)

        self.detailsDetailsWidget = QWidget()
        self.detailsDetailsWidget.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsDetailsWidget.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsDetailsWidget.show()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0,0,0,0)
        hbl.addWidget(self.detailsSection, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsAFM, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsSNR, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsCorrSpots, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.detailsDetailsWidget.setLayout(hbl)


        # vbl.addWidget(self.spreadW, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        vbl.addWidget(self.labelsWidget, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        # vbl.addWidget(self.detailsDetailsWidget, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.DetailsContainer.setLayout(vbl)

        self.spreadW = QWidget()
        self.spreadW.setWindowFlags(Qt.FramelessWindowHint)
        self.spreadW.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.spreadW.setFixedSize(1,12)
        self.spreadW.setVisible(getOpt('neuroglancer,SHOW_UI_CONTROLS'))

        self.spreadW2 = QWidget()
        self.spreadW2.setWindowFlags(Qt.FramelessWindowHint)
        self.spreadW2.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.spreadW2.setFixedSize(96,1)

        self.spreadW3 = QWidget()
        self.spreadW3.setWindowFlags(Qt.FramelessWindowHint)
        self.spreadW3.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.spreadW3.setFixedSize(40,1)

        self.ng_gl.addWidget(self.labelsWidget, 0, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.spreadW3, 0, 4, 1, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.spreadW2, 1, 3, 2, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.spreadW, 1, 4, 1, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.detailsDetailsWidget, 2, 0, 1, 4, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.setRowStretch(0, 0)
        self.ng_gl.setRowStretch(1, 0)
        self.ng_gl.setRowStretch(2, 100)
        self.ng_gl.setColumnStretch(0, 24)
        self.ng_gl.setColumnStretch(1, 0)
        self.ng_gl.setColumnStretch(2, 5)
        self.ng_gl.setColumnStretch(3, 1)
        self.updateUISpacing()
        self.ng_browser_container.setLayout(self.ng_gl)

        self.zoomSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.zoomSlider.setMaximum(4)
        self.zoomSlider.setMinimum(0.1)
        # self.zoomSlider.valueChanged.connect(self.onZoomSlider)
        self.zoomSlider.sliderMoved.connect(self.onZoomSlider)
        self.zoomSlider.setValue(4.0)

        # self.crossSectionOrientationSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        # # self.zoomSlider.setMaximum(8.0)
        # # self.zoomSlider.setMaximum(100)
        # self.crossSectionOrientationSlider.setMaximum(5.0)
        # self.crossSectionOrientationSlider.setMinimum(-5.0)
        # self.crossSectionOrientationSlider.valueChanged.connect(self.onSliderCrossSectionOrientation)

        # self.crossSectionOrientationSliderAndLabel = QWidget()
        # self.crossSectionOrientationSliderAndLabel.setFixedWidth(24)
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # vbl.addWidget(self.crossSectionOrientationSlider)
        # vbl.addWidget(VerticalLabel('Rotation:'))
        # self.crossSectionOrientationSliderAndLabel.setLayout(vbl)

        self.zoomSliderAndLabel = QWidget()
        self.zoomSliderAndLabel.setFixedWidth(16)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.zoomSlider)
        vbl.addWidget(VerticalLabel('Zoom:'))
        self.zoomSliderAndLabel.setLayout(vbl)

        self.ZdisplaySlider = QSlider(Qt.Orientation.Vertical, self)
        self.ZdisplaySlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.ZdisplaySlider.setMaximum(20)
        self.ZdisplaySlider.setMinimum(1)
        self.ZdisplaySlider.valueChanged.connect(self.onSliderZmag)
        self.ZdisplaySlider.setValue(1.0)

        self.ZdisplaySliderAndLabel = QWidget()
        self.ZdisplaySliderAndLabel.setFixedWidth(16)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.ZdisplaySlider)
        vbl.addWidget(VerticalLabel('Z-Mag:'))
        self.ZdisplaySliderAndLabel.setLayout(vbl)

        self.MA_webengine_ref = QWebEngineView()
        self.MA_webengine_base = QWebEngineView()
        self.MA_webengine_Stage = QWebEngineView()
        # self.MA_viewer_ref = MAViewer(role='ref', webengine=self.MA_webengine_base)
        # self.MA_viewer_base = MAViewer(role='base', webengine=self.MA_webengine_ref)
        # self.MA_viewer_stage = EMViewer(force_xy=True, webengine=self.MA_webengine_Stage)
        self.MA_webengine_ref.setMinimumWidth(200)
        self.MA_webengine_base.setMinimumWidth(200)
        self.MA_webengine_Stage.setMinimumWidth(128)
        self.MA_webengine_Stage.setMinimumHeight(128)
        # self.MA_webengine_ref.setMouseTracking(True)
        # self.MA_webengine_base.setMouseTracking(True)
        # self.MA_webengine_Stage.setMouseTracking(True)
        # self.MA_webengine_ref.setMinimumSize(QSize(300,300))
        # self.MA_webengine_base.setMinimumSize(QSize(300,300))
        # self.MA_webengine_Stage.setMinimumSize(QSize(300,300))

        # self.MA_webengine_ref.setFocusPolicy(Qt.StrongFocus)
        # self.MA_webengine_base.setFocusPolicy(Qt.StrongFocus)
        # self.MA_webengine_Stage.setFocusPolicy(Qt.StrongFocus)

        # DONT CHANGE----------------------
        # self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
        # self.MA_viewer_ref.signals.ptsChanged.connect(self.updateMAlistRef)
        # self.MA_viewer_base.signals.ptsChanged.connect(self.updateMAlistBase)
        # self.MA_viewer_ref.shared_state.add_changed_callback(self.updateMA_base_state)
        # self.MA_viewer_base.shared_state.add_changed_callback(self.updateMA_ref_state)
        # DONT CHANGE----------------------


        # MA Stage Buffer Widget
        self.MA_stageBufferRef = QLabel('Reference')
        self.MA_stageBufferRef.setStyleSheet('color: #1b1e23; font-weight: 600;font-size:18px;')
        self.MA_stageBufferBase = QLabel('Base')
        self.MA_stageBufferBase.setStyleSheet('color: #1b1e23; font-weight: 600;font-size:18px;')

        self.MA_ptsListWidget_ref = QListWidget()
        self.MA_ptsListWidget_ref.installEventFilter(self)
        self.MA_ptsListWidget_ref.itemClicked.connect(self.refListItemClicked)

        self.MA_ptsListWidget_base = QListWidget()
        self.MA_ptsListWidget_base.installEventFilter(self)
        self.MA_ptsListWidget_base.itemClicked.connect(self.baseListItemClicked)



        self.gb_actionsMA = QGroupBox('Actions')
        fl_actionsMA = QFormLayout()

        self.gb_actionsMA.setLayout(fl_actionsMA)


        lab = QLabel('Method: ')
        tip = 'Automatic Alignment using SWIM'
        self.rbAuto = QRadioButton('Automatic')
        # self.rb0.setStyleSheet('font-size: 11px')
        self.rbAuto.setStatusTip(tip)
        self.rbAuto.setChecked(True)
        self.rbAuto.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def fn():
            if self.rbAuto.isChecked():
                cfg.data.set_selected_method('Auto SWIM Align')
            else:
                cfg.data.set_selected_method('Match Point Align')
        self.rbAuto.clicked.connect(fn)

        tip = 'Align by Manual Point Selection'
        # self.rb1 = QRadioButton('Ref | Curr')
        # self.rb1 = QRadioButton('Compare')
        # self.rb1 = QRadioButton('Ref|Base|Aligned, Column')
        self.rbMan = QRadioButton('Manual')
        # self.rb1.setStyleSheet('font-size: 11px')
        self.rbMan.setStatusTip(tip)
        self.rbMan.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def fn():
            if self.rbMan.isChecked():
                cfg.data.set_selected_method('Match Point Align')
            else:
                cfg.data.set_selected_method('Auto SWIM Align')
        self.rbMan.clicked.connect(fn)

        self.rbMethodGroup = QButtonGroup()
        self.rbMethodGroup.addButton(self.rbAuto)
        self.rbMethodGroup.addButton(self.rbMan)
        self.rbMethodGroup.setExclusive(True)

        #tag
        '''
        Alignment Method (displayed):
        Alignment Method (next run): '''

        w = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(lab)
        hbl.addWidget(self.rbAuto)
        hbl.addWidget(self.rbMan)
        w.setLayout(hbl)
        fl_actionsMA.addWidget(w)




        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        w = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.MA_stageBufferRef)
        vbl.addWidget(self.MA_ptsListWidget_ref)
        w.setLayout(vbl)
        hbl.addWidget(w)
        w = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.MA_stageBufferBase)
        vbl.addWidget(self.MA_ptsListWidget_base)
        w.setLayout(vbl)
        hbl.addWidget(w)

        self.MA_sbw = QWidget() # make the widget
        self.MA_sbw.setLayout(hbl)


        '''MA Stage area widgets'''
        # MA Stage Widget
        self.MA_stage = QWidget()
        self.MA_stage.setMinimumWidth(32)
        # self.MA_stage.setMaximumWidth(500)
        # self.MA_stage.setMaximumWidth(200)

        txt = '⇧ + Click - Select at least 3 and up to 7 corresponding points'
        self.msg_MAinstruct = QLabel()
        self.msg_MAinstruct.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.msg_MAinstruct.setAlignment(Qt.AlignCenter)
        # self.msg_MAinstruct.setStyleSheet('color: #1b1e23; font-weight: 400;font-size:12px;')
        self.msg_MAinstruct.setStyleSheet(
            """
            color: #ffe135; 
            background-color: rgba(0,0,0,.24); 
            font-weight: 600;
            text-align: center;
            padding: 3px;
            """)
        # self.afmClabel.setAutoFillBackground(False)
        # self.afmClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.msg_MAinstruct.setText(txt)
        self.msg_MAinstruct.setFixedHeight(30)
        self.msg_MAinstruct.setFixedWidth(430)

        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.MA_webengine_Stage)
        # vbl.addWidget(self.MA_sbw, alignment=Qt.AlignmentFlag.AlignBottom)
        vbl.addWidget(self.MA_sbw)
        #tag


        self.MA_stage.setLayout(vbl)


        self.MA_gl = QGridLayout()
        self.MA_gl.setContentsMargins(0,0,0,0)

        w = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.MA_webengine_ref)
        w.setLayout(vbl)
        self.MA_gl.addWidget(w, 0, 0, 4, 2)

        w = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.MA_webengine_base)
        w.setLayout(vbl)
        self.MA_gl.addWidget(w, 0, 2, 4, 2)

        self.MA_gl.addWidget(self.msg_MAinstruct, 2, 1, 1, 2)

        # self.MA_gl.addWidget(self.MA_stage, alignment=Qt.AlignmentFlag.AlignBottom)

        self.MA_widget = QWidget()
        self.MA_widget.setLayout(self.MA_gl)
        # self.MA_widget.hide()

        self.MA_splitter = QSplitter()
        self.MA_splitter.setHandleWidth(2)
        self.MA_splitter.addWidget(self.MA_widget)
        self.MA_splitter.addWidget(self.MA_stage)
        self.MA_splitter.setCollapsible(0, False)
        self.MA_splitter.setCollapsible(1, False)
        self.MA_splitter.setSizes([.75*cfg.WIDTH, .25*cfg.WIDTH])
        self.MA_splitter.hide()

        self.weSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.weSplitter.addWidget(self.ng_browser_container)
        self.weSplitter.addWidget(self.MA_splitter)
        self.weSplitter.setCollapsible(0, False)
        self.weSplitter.setCollapsible(1, False)

        hbl = QHBoxLayout()
        hbl.setSpacing(1)
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.ngVertLab)
        hbl.addWidget(self.weSplitter)
        # hbl.addWidget(self.zoomSlider)
        # hbl.addWidget(self.crossSectionOrientationSliderAndLabel)
        hbl.addWidget(self.ZdisplaySliderAndLabel)
        hbl.addWidget(self.zoomSliderAndLabel)
        self.ng_browser_container_outer = QWidget()
        self.ng_browser_container_outer.setObjectName('ng_browser_container_outer')
        self.ng_browser_container_outer.setLayout(hbl)

    def refListItemClicked(self, qmodelindex):
        item = self.MA_ptsListWidget_ref.currentItem()
        logger.info(f"Selected {item.text()}")

    def baseListItemClicked(self, qmodelindex):
        item = self.MA_ptsListWidget_base.currentItem()
        logger.info(f"Selected {item.text()}")


    def updateMAlistRef(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        logger.info('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))

        # mps = [(p[1], p[2]) for p in [p.point.tolist() for p in self.MA_viewer_ref.pts.values()]]
        self.MA_ptsListWidget_ref.clear()
        for key in self.MA_viewer_ref.pts.keys():
            p = self.MA_viewer_ref.pts[key]
            _, x, y = p.point.tolist()
            # item = QListWidgetItem('%.1f, %.1f' %(x,y))
            item = QListWidgetItem('%.1f, %.1f' %(x,y))
            item.setBackground(QColor(key))
            self.MA_ptsListWidget_ref.addItem(item)

    def updateMAlistBase(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        logger.info('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))

        # mps = [(p[1], p[2]) for p in [p.point.tolist() for p in self.MA_viewer_base.pts.values()]]
        self.MA_ptsListWidget_base.clear()
        for key in self.MA_viewer_base.pts.keys():
            p = self.MA_viewer_base.pts[key]
            _, x, y = p.point.tolist()
            item = QListWidgetItem('%.1f, %.1f' % (x, y))
            item.setBackground(QColor(key))
            self.MA_ptsListWidget_base.addItem(item)


    def updateMA_ref_state(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        logger.info('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))

        if caller != 'on_state_change':
            if self.MA_webengine_ref.isVisible():
                if self.MA_viewer_base.state.cross_section_scale:
                    if self.MA_viewer_base.state.cross_section_scale < 10_000:
                        pos = self.MA_viewer_base.state.position
                        zoom = self.MA_viewer_base.state.cross_section_scale
                        if isinstance(pos,np.ndarray) or isinstance(zoom,np.ndarray):
                            state = copy.deepcopy(self.MA_viewer_ref.state)
                            if isinstance(pos, np.ndarray):
                                state.position = self.MA_viewer_base.state.position
                            if isinstance(zoom, float):
                                state.cross_section_scale = self.MA_viewer_base.state.cross_section_scale
                            self.MA_viewer_ref.set_state(state)


    def updateMA_base_state(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        logger.info('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))

        if caller != 'on_state_change':
            if self.MA_webengine_base.isVisible():
                if self.MA_viewer_ref.state.cross_section_scale:
                    if self.MA_viewer_ref.state.cross_section_scale < 10_000:
                        pos = self.MA_viewer_ref.state.position
                        zoom = self.MA_viewer_ref.state.cross_section_scale
                        if isinstance(pos, np.ndarray) or isinstance(zoom, np.ndarray):
                            state = copy.deepcopy(self.MA_viewer_base.state)
                            if isinstance(pos, np.ndarray):
                                state.position = self.MA_viewer_ref.state.position
                            if isinstance(zoom, float):
                                state.cross_section_scale = self.MA_viewer_ref.state.cross_section_scale
                            self.MA_viewer_base.set_state(state)


    def deleteMpRef(self):
        logger.info('Deleting A Reference Image Manual Correspondence Point from Buffer...')
        cfg.main_window.hud.post('Deleting A Reference Image Manual Correspondence Point from Buffer...')
        for item in self.MA_ptsListWidget_ref.selectedItems():
            self.MA_ptsListWidget_ref.takeItem(self.MA_ptsListWidget_ref.row(item))
        if self.MA_ptsListWidget_ref.currentItem():
            del_key = self.MA_ptsListWidget_ref.currentItem().background().color().name()
            logger.info('del_key is %s' % del_key)
            self.MA_viewer_ref.pts.pop(del_key)
            self.MA_viewer_ref.update_annotations()

    def deleteMpBase(self):
        logger.info('Deleting A Base Image Manual Correspondence Point from Buffer...')
        cfg.main_window.hud.post('Deleting A Base Image Manual Correspondence Point from Buffer...')
        for item in self.MA_ptsListWidget_base.selectedItems():
            self.MA_ptsListWidget_base.takeItem(self.MA_ptsListWidget_base.row(item))
        if self.MA_ptsListWidget_base.currentItem():
            del_key = self.MA_ptsListWidget_base.currentItem().background().color().name()
            logger.info('del_key is %s' % del_key)
            self.MA_viewer_base.pts.pop(del_key)
            self.MA_viewer_base.update_annotations()

    def deleteAllMpRef(self):
        logger.info('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        self.MA_viewer_ref.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        self.MA_viewer_ref.update_annotations()

    def deleteAllMpBase(self):
        logger.info('Deleting All Base Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base Image Manual Correspondence Points from Buffer...')
        self.MA_viewer_base.pts.clear()
        self.MA_ptsListWidget_base.clear()
        self.MA_viewer_base.update_annotations()

    def deleteAllMp(self):
        logger.info('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        self.MA_viewer_ref.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        self.MA_viewer_base.pts.clear()
        self.MA_ptsListWidget_base.clear()
        self.MA_viewer_ref.update_annotations()
        self.MA_viewer_base.update_annotations()





    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self.MA_ptsListWidget_ref:
            menu = QMenu()
            self.deleteMpRefAction = QAction('Delete')
            self.deleteMpRefAction.setStatusTip('Delete this manual correspondence point')
            self.deleteMpRefAction.triggered.connect(self.deleteMpRef)
            menu.addAction(self.deleteMpRefAction)
            self.deleteAllMpRefAction = QAction('Delete All Ref Pts')
            self.deleteAllMpRefAction.setStatusTip('Delete all reference manual correspondence points')
            self.deleteAllMpRefAction.triggered.connect(self.deleteAllMpRef)
            menu.addAction(self.deleteAllMpRefAction)
            self.deleteAllPtsAction0 = QAction('Delete All Pts')
            self.deleteAllPtsAction0.setStatusTip('Delete all manual correspondence points')
            self.deleteAllPtsAction0.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction0)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        elif event.type() == QEvent.ContextMenu and source is self.MA_ptsListWidget_base:
            menu = QMenu()
            self.deleteMpBaseAction = QAction('Delete')
            self.deleteMpBaseAction.setStatusTip('Delete this manual correspondence point')
            self.deleteMpBaseAction.triggered.connect(self.deleteMpBase)
            menu.addAction(self.deleteMpBaseAction)
            self.deleteAllMpBaseAction = QAction('Delete All Base Pts')
            self.deleteAllMpBaseAction.setStatusTip('Delete all base manual correspondence points')
            self.deleteAllMpBaseAction.triggered.connect(self.deleteAllMpBase)
            menu.addAction(self.deleteAllMpBaseAction)
            self.deleteAllPtsAction1 = QAction('Delete All Pts')
            self.deleteAllPtsAction1.setStatusTip('Delete all manual correspondence points')
            self.deleteAllPtsAction1.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction1)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        return super().eventFilter(source, event)

    def onEnterManualMode(self):
        logger.critical('')
        self.bookmark_tab = self._tabs.currentIndex()
        self._tabs.setCurrentIndex(0)
        self.ng_browser_container.hide()
        self.MA_splitter.show()

        #Todo update listwidgets before entering manual alignment mode
        self.MA_viewer_ref = MAViewer(role='ref', webengine=self.MA_webengine_base)
        self.MA_viewer_base = MAViewer(role='base', webengine=self.MA_webengine_ref)
        self.MA_viewer_stage = EMViewer(force_xy=True, webengine=self.MA_webengine_Stage)
        self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
        self.MA_viewer_ref.signals.ptsChanged.connect(self.updateMAlistRef)
        self.MA_viewer_base.signals.ptsChanged.connect(self.updateMAlistBase)
        self.MA_viewer_ref.shared_state.add_changed_callback(self.updateMA_base_state)
        self.MA_viewer_base.shared_state.add_changed_callback(self.updateMA_ref_state)
        self.MA_viewer_ref.initViewer()
        self.MA_viewer_base.initViewer()
        self.MA_viewer_stage.initViewer()

        # self.updateMAviewers() #----
        # self.MA_webengine_ref.setUrl(QUrl(self.MA_viewer_ref.url()))
        # self.MA_webengine_base.setUrl(QUrl(self.MA_viewer_base.url()))
        # self.MA_webengine_Stage.setUrl(QUrl(cfg.emViewer.url()))
        # self.MA_viewer_stage.initViewer(role='stage')
        self.ngVertLab.setText('Manual Alignment Mode')
        self.ngVertLab.setStyleSheet("""background-color: #1b1e23; color: #f3f6fb;""")

    def updateMAviewers(self):
        self.MA_webengine_ref.setUrl(QUrl(self.MA_viewer_ref.url()))
        self.MA_webengine_base.setUrl(QUrl(self.MA_viewer_base.url()))
        self.MA_webengine_Stage.setUrl(QUrl(cfg.emViewer.url()))


    def onExitManualMode(self):
        logger.critical('')
        self.deleteAllMp()
        self._tabs.setCurrentIndex(self.bookmark_tab)
        self.ng_browser_container.show()
        # self.MA_widget.hide()
        self.MA_splitter.hide()
        self.ngVertLab.setStyleSheet('')
        self.ngVertLab.setText('Neuroglancer 3DEM View')
        self.initNeuroglancer()


    def updateUISpacing(self):
        isUiControls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
        self.spreadW.setVisible(isUiControls)
        if isUiControls:
            self.spreadW2.setFixedSize(96, 1)
            self.spreadW3.setFixedSize(40, 1)
        else:
            self.spreadW2.setFixedSize(10, 1)
            self.spreadW3.setFixedSize(10, 1)

    def slotUpdateZoomSlider(self):
        # Lets only care about REF <--> slider
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        try:
            if cfg.MP_MODE:
                val = self.MA_viewer_ref.state.cross_section_scale
                if val:
                    if val != 0:
                        new_val = float(sqrt(val))
                        # logger.info(f'val = {val}, new_val = {new_val}')
                        self.zoomSlider.setValue(new_val)
            else:
                val = cfg.emViewer.state.cross_section_scale
                if val:
                    if val != 0:
                        new_val = float(sqrt(val))
                        # logger.info(f'val = {val}, new_val = {new_val}')
                        self.zoomSlider.setValue(new_val)
        except:
            print_exception()


    def onZoomSlider(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])

        logger.critical('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))

        if caller not in  ('slotUpdateZoomSlider', 'setValue'):
            if cfg.MP_MODE:
                val = self.zoomSlider.value()
                state = copy.deepcopy(self.MA_viewer_ref.state)
                state.cross_section_scale = val * val
                self.MA_viewer_ref.set_state(state)
            else:
                try:
                    val = self.zoomSlider.value()
                    state = copy.deepcopy(cfg.emViewer.state)
                    state.cross_section_scale = val * val
                    cfg.emViewer.set_state(state)
                except:
                    print_exception()


    def setZmag(self, val):
        logger.critical(f'Setting Z-mag to {val}...')
        try:
            state = copy.deepcopy(cfg.emViewer.state)
            state.relative_display_scales = {'z': val}
            cfg.emViewer.set_state(state)
            cfg.main_window.update()
        except:
            print_exception()


    def onSliderZmag(self):
        caller = inspect.stack()[1].function
        logger.critical('caller: %s' % caller)
        try:
            val = self.ZdisplaySlider.value()
            logger.critical('val = %d' % val)
            state = copy.deepcopy(cfg.emViewer.state)
            state.relative_display_scales = {'z': val}
            cfg.emViewer.set_state(state)
            cfg.main_window.update()
        except:
            print_exception()


    def resetSliderZmag(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        try:
            if cfg.main_window.rb1.isChecked():
                self.ZdisplaySlider.setValue(10)
            else:
                self.ZdisplaySlider.setValue(1)

        except:
            print_exception()

    # def onSliderCrossSectionOrientation(self):
    #     caller = inspect.stack()[1].function
    #     # if caller not in ('slotUpdateZoomSlider', 'setValue'):
    #     #     # logger.info(f'caller: {caller}')
    #     if cfg.emViewer.state.cross_section_scale:
    #         state = copy.deepcopy(cfg.emViewer.state)
    #         val = self.crossSectionOrientationSlider.value()
    #         logger.info(f'val={val}')
    #         # cur_val = state.cross_section_orientation
    #         state.cross_section_orientation = [0,0,0,val]
    #         cfg.emViewer.set_state(state)
    #     else:
    #         logger.warning('cfg.emViewer.state.cross_section_scale does not exist!')


    def initUI_table(self):
        '''Layer View Widget'''
        logger.info('')
        self.project_table = ProjectTable(self)
        self.project_table.setObjectName('project_table')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.project_table)
        self.label_overview = VerticalLabel('Project Data Table View')
        self.label_overview.setObjectName('label_overview')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.table_container = QWidget()
        self.table_container.setObjectName('table_container')
        self.table_container.setLayout(hbl)


    def updateJsonWidget(self):
        logger.info('')
        self.treeview_model.load(cfg.data.to_dict())
        self.treeview.header().resizeSection(0, 300)
        self.treeview.expandAll()


    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self.treeview = QTreeView()
        self.treeview.setAnimated(True)
        self.treeview.setIndentation(20)
        self.treeview.header().resizeSection(0, 300)
        self.treeview_model = JsonModel()
        self.treeview.setModel(self.treeview_model)
        self.treeview.setAlternatingRowColors(True)
        self._wdg_treeview = QWidget()
        self._wdg_treeview.setObjectName('_wdg_treeview')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 0, 2, 0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setObjectName('label_treeview')
        hbl.addWidget(lab)
        hbl.addWidget(self.treeview)
        self._wdg_treeview.setLayout(hbl)


    def updatePlotThumbnail(self):
        pixmap = QPixmap(cfg.data.thumbnail())
        pixmap = pixmap.scaledToHeight(160)
        self._thumbnail_src.setPixmap(pixmap)
        self.source_thumb_and_label.show()
        if cfg.data.is_aligned_and_generated():
            pixmap = QPixmap(cfg.data.thumbnail_aligned())
            pixmap = pixmap.scaledToHeight(160)
            self._thumbnail_aligned.setPixmap(pixmap)
            self.aligned_thumb_and_label.show()
        else:
            self.aligned_thumb_and_label.hide()


    def initUI_plot(self):
        '''SNR Plot Widget'''
        logger.info('')
        font = QFont()
        font.setBold(True)
        self.snr_plot = SnrPlot()
        lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#f3f6fb', font_size=14)
        lab_yaxis.setFixedWidth(18)
        hbl = QHBoxLayout()
        hbl.addWidget(lab_yaxis)
        self._plot_Yaxis = QWidget()
        self._plot_Yaxis.setLayout(hbl)
        self._plot_Yaxis.setContentsMargins(0, 0, 0, 0)
        self._plot_Yaxis.setFixedWidth(26)
        lab_yaxis.setFont(font)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self._plot_Yaxis)
        hbl.addWidget(self.snr_plot)
        # self.snr_plot_widget = QWidget()
        # self.snr_plot_widget.setObjectName('snr_plot_widget')
        self._plot_Xaxis = QLabel('Serial Section #')
        self._plot_Xaxis.setStyleSheet('color: #f3f6fb; font-size: 14px;')
        self._plot_Xaxis.setContentsMargins(0, 0, 0, 8)
        self._plot_Xaxis.setFont(font)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addLayout(hbl)
        vbl.addWidget(self._plot_Xaxis, alignment=Qt.AlignmentFlag.AlignHCenter)

        w1 = QWidget()
        w1.setLayout(vbl)

        self._thumbnail_src = QLabel()
        self._thumbnail_aligned = QLabel()

        style = '''font-size: 14px; color: #f3f6fb; font-weight: 500;'''

        self._lab_source_thumb = QLabel('Source:')
        self._lab_source_thumb.setFixedHeight(16)
        self._lab_source_thumb.setStyleSheet(style)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._lab_source_thumb)
        vbl.addWidget(self._thumbnail_src, alignment=Qt.AlignmentFlag.AlignTop)
        self.source_thumb_and_label = QWidget()
        self.source_thumb_and_label.setLayout(vbl)

        self._lab_aligned_thumb = QLabel('Aligned:')
        self._lab_aligned_thumb.setFixedHeight(16)
        self._lab_aligned_thumb.setStyleSheet(style)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._lab_aligned_thumb)
        vbl.addWidget(self._thumbnail_aligned, alignment=Qt.AlignmentFlag.AlignTop)
        self.aligned_thumb_and_label = QWidget()
        self.aligned_thumb_and_label.setLayout(vbl)

        self.source_thumb_and_label.hide()
        self.aligned_thumb_and_label.hide()

        gl = QGridLayout()
        gl.setContentsMargins(4, 4, 4, 4)
        gl.setRowStretch(0, 1)
        gl.setRowStretch(1, 1)
        gl.setColumnStretch(0, 1)
        gl.addWidget(self.source_thumb_and_label, 0, 0)
        gl.addWidget(self.aligned_thumb_and_label, 1, 0)
        w2 = QWidget()
        w2.setLayout(gl)
        self.snr_plot_widget = QSplitter(Qt.Orientation.Horizontal)
        self.snr_plot_widget.setObjectName('snr_plot_widget')


        # self.snr_plot_browser = QWebEngineView()
        # w3 = QWidget()
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # vbl.addWidget(self.snr_plot_browser)
        # w3.setLayout(vbl)


        self.snr_plot_widget.addWidget(w1)
        self.snr_plot_widget.addWidget(w2)
        # self.snr_plot_widget.addWidget(w3)


    # def upateSnrPlotBrowser(self):
    #     cfg.emViewer = EMViewer(parent=self)
    #     cfg.emViewer.initViewerSlim()
    #     url = cfg.emViewer.get_viewer_url()
    #     self.snr_plot_browser.setUrl(QUrl(url))




    def initUI_mini_view(self):
        self._mv = MiniView()


    def initUI_tab_widget(self):
        '''Tab Widget'''
        logger.info('')
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet('QTabBar::tab { height: 22px; width: 84px; }')
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setObjectName('project_tabs')
        self._tabs.addTab(self.ng_browser_container_outer, ' 3DEM ')
        self._tabs.addTab(self.table_container, ' Table ')
        self._tabs.setTabToolTip(1, os.path.basename(cfg.data.dest()))
        # self._tabs.addTab(self._wdg_treeview, ' Tree ')
        self._tabs.addTab(self._wdg_treeview, ' Data ')
        self._tabs.addTab(self.snr_plot_widget, ' SNR Plot ')
        # self._addTab(widget=self._mv, name=' Miniview ')
        self._tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(1, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(2, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(3, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(0, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(1, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(2, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(3, QTabBar.LeftSide, None)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._tabs)
        self.setLayout(vbl)


    def paintEvent(self, pe):
        '''Enables widget to be style-ized'''
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        s = self.style()
        s.drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def sizeHint(self):
        return QSize(1000,1000)


class Thumbnail(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        thumbnail = ScaledPixmapLabel(self)
        pixmap = QPixmap(path)
        thumbnail.setPixmap(pixmap)
        thumbnail.setScaledContents(True)
        layout = QGridLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(thumbnail, 0, 0)
        self.setLayout(layout)


class ScaledPixmapLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setScaledContents(True)

    def paintEvent(self, event):
        if self.pixmap():
            pm = self.pixmap()
            try:
                originalRatio = pm.width() / pm.height()
                currentRatio = self.width() / self.height()
                if originalRatio != currentRatio:
                    qp = QPainter(self)
                    pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    rect = QRect(0, 0, pm.width(), pm.height())
                    rect.moveCenter(self.rect().center())
                    qp.drawPixmap(rect, pm)
                    return
            except ZeroDivisionError:
                pass
                # logger.warning('Cannot divide by zero')
                # print_exception()
        super().paintEvent(event)



class VerticalLabel(QLabel):

    def __init__(self, text, bg_color=None, font_color=None, font_size=None, *args):
        QLabel.__init__(self, text, *args)

        self.text = text
        self.setStyleSheet("font-size: 12px;")
        font = QFont()
        font.setBold(True)
        self.setFont(font)
        style = ''
        if bg_color:
            style += f'background-color: {bg_color};'
        if font_color:
            style += f'color: {font_color};'
        if font_size:
            style += f'font-size: {str(font_size)};'
        if style != '':
            self.setStyleSheet(style)

    def setText(self, p_str):
        self.text = p_str

    def paintEvent(self, event):
        p = QPainter(self)
        p.rotate(-90)
        rgn = QRect(-self.height(), 0, self.height(), self.width())
        align  = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter
        # align  = Qt.AlignmentFlag.AlignCenter
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.hint = p.drawText(rgn, align, self.text)
        p.end()
        self.setMaximumWidth(self.hint.height())
        self.setMinimumHeight(self.hint.width())


    def sizeHint(self):
        if hasattr(self, 'hint'):
            return QSize(self.hint.height(), self.hint.width() + 10)
        else:
            return QSize(10, 48)


    def minimumSizeHint(self):
        size = QLabel.minimumSizeHint(self)
        return QSize(size.height(), size.width())


class ClickLabel(QLabel):
    clicked=Signal()

    def mousePressEvent(self, ev):
        self.clicked.emit()

if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    pt = ProjectTab()
    main_window.setCentralWidget(pt)
    main_window.show()
    sys.exit(app.exec_())