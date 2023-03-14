#!/usr/bin/env python3

'''TODO This needs to have columns for indexing and section name (for sorting!)'''

import os, sys, logging, inspect, copy, time, warnings
from datetime import datetime
# from math import log10
from math import log2, sqrt
import neuroglancer as ng
import numpy as np
import shutil
import qtawesome as qta
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStyleOption, \
    QStyle, QTabBar, QTabWidget, QGridLayout, QTreeView, QSplitter, QTextEdit, QSlider, QPushButton, QSizePolicy, \
    QListWidget, QListWidgetItem, QMenu, QAction, QFormLayout, QGroupBox, QRadioButton, QButtonGroup, QComboBox, \
    QCheckBox
from qtpy.QtCore import Qt, QSize, QRect, QUrl, Signal, QEvent, QThread, QTimer
from qtpy.QtGui import QPainter, QFont, QPixmap, QColor, QCursor
from qtpy.QtWebEngineWidgets import *
import src.config as cfg
from src.helpers import getOpt, setOpt, getData, setData
from src.viewer_em import EMViewer, EMViewerStage, EMViewerSnr
from src.viewer_ma import MAViewer
from src.helpers import print_exception
from src.ui.snr_plot import SnrPlot
from src.ui.widget_area import WidgetArea
from src.ui.project_table import ProjectTable
from src.ui.models.json_tree import JsonModel
from src.ui.sliders import DoubleSlider
from src.ui.thumbnail import CorrSignalThumbnail
from src.ui.toggle_switch import ToggleSwitch
from src.ui.process_monitor import HeadupDisplay
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel
from src.ui.toggle_animated import AnimatedToggle


__all__ = ['ProjectTab']

logger = logging.getLogger(__name__)

class ProjectTab(QWidget):

    def __init__(self,
                 parent,
                 path=None,
                 datamodel=None):
        super().__init__(parent)
        logger.info('')
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

        h = self.MA_webengine_ref.geometry().height()
        self.MA_stageSplitter.setSizes([int(.7*h), int(.3*h)])

    def _onTabChange(self):
        logger.info('')
        index = self._tabs.currentIndex()
        # if index == 0:
        #     if cfg.data['ui']['arrangement'] == 'stack':
        #         cfg.main_window.combo_mode.setCurrentIndex(0)
        #     elif cfg.data['ui']['arrangement'] == 'stack':
        #         cfg.main_window.combo_mode.setCurrentIndex(0)
        #     self.initNeuroglancer()
        #     # pass
        QApplication.restoreOverrideCursor()
        self.refreshTab(index=index)

    def refreshTab(self, index=None):
        logger.info('\n\n\n')
        if index == None:
            index = self._tabs.currentIndex()

        if getData('state,manual_mode'):
            pts_ref = self.MA_viewer_ref.pts
            pts_base = self.MA_viewer_base.pts
            self.initNeuroglancer()
            self.MA_viewer_ref.pts = pts_ref
            self.MA_viewer_base.pts = pts_base
            # self.updateNeuroglancer()

        if index == 0:
            # self.updateNeuroglancer()
            self.initNeuroglancer()
            # pass
        elif index == 1:
            pass
        elif index == 2:
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()
        elif index == 3:
            self.snr_plot.data = cfg.data
            self.snr_plot.initSnrPlot()
            self.initSnrViewer()


        # QApplication.processEvents()
        # self.repaint()

    def initSnrViewer(self):

        self.snrViewer = self.viewer =  cfg.emViewer = EMViewerSnr(webengine=self.snrWebengine)
        # self.snrViewer.initViewerSbs(orientation='vertical')
        self.snrWebengine.setUrl(QUrl(self.snrViewer.url()))
        self.snrViewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
        self.updateNeuroglancer()


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
        logger.info(f'Initializing Neuroglancer (caller: {inspect.stack()[1].function})...')

        caller = inspect.stack()[1].function
        if getData('state,manual_mode'):
            # cfg.main_window.comboboxNgLayout.setCurrentText('xy')
            self.MA_viewer_ref = MAViewer(role='ref', webengine=self.MA_webengine_ref)
            self.MA_viewer_base = MAViewer(role='base', webengine=self.MA_webengine_base)
            self.MA_viewer_stage = EMViewerStage(webengine=self.MA_webengine_stage)
            self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
            self.MA_viewer_ref.signals.ptsChanged.connect(self.update_MA_widgets)
            self.MA_viewer_base.signals.ptsChanged.connect(self.update_MA_widgets)
            self.MA_viewer_ref.shared_state.add_changed_callback(self.update_MA_base_state)
            self.MA_viewer_base.shared_state.add_changed_callback(self.update_MA_ref_state)
            self.update_MA_widgets()
        else:
            if caller != '_onGlobTabChange':
                self.viewer = cfg.emViewer = EMViewer(webengine=self.webengine)
                self.updateNeuroglancer()
                cfg.main_window.dataUpdateWidgets()  # 0204+
                self.viewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
                self.viewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)


    def updateNeuroglancer(self):
        caller = inspect.stack()[1].function
        logger.info(f'Updating Neuroglancer Viewer (caller: {caller})')
        for viewer in cfg.main_window.get_viewers():
            viewer.initViewer()
        # if getData('state,MANUAL_MODE'):
        #     self.MA_viewer_base.initViewer()
        #     self.MA_viewer_ref.initViewer()
        #     self.MA_viewer_stage.initViewer()
        #     self.update_MA_widgets() # <-- !!!
        # else:
        #     self.viewer.initViewer()

        # self.setViewerModifications()


    # def setViewerModifications(self):
    #     logger.info('')
    #     if getData('state,MANUAL_MODE'):
    #         self.MA_viewer_base.set_brightness()
    #         self.MA_viewer_ref.set_brightness()
    #         self.MA_viewer_stage.set_brightness()
    #
    #         self.MA_viewer_base.set_contrast()
    #         self.MA_viewer_ref.set_contrast()
    #         self.MA_viewer_stage.set_contrast()
    #     else:
    #         self.viewer.set_brightness()
    #         self.viewer.set_contrast()




    def get_layout(self, requested=None):
        if requested == None:
            requested = cfg.data['ui']['ng_layout']
        mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
              'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
        return mapping[requested]


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
        self.ng_gl.addWidget(self.webengine, 0, 0, 5, 5)
        self._overlayRect = QWidget()
        self._overlayRect.setObjectName('_overlayRect')
        self._overlayRect.setStyleSheet("""background-color: rgba(0, 0, 0, 0.5);""")
        self._overlayRect.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayRect.hide()
        self.ng_gl.addWidget(self._overlayRect, 0, 0, 5, 5)
        self._overlayLab = QLabel()
        self._overlayLab.setStyleSheet("""color: #FF0000; font-size: 28px;""")
        self._overlayLab.hide()

        self.hud_overlay = HeadupDisplay(cfg.main_window.app, overlay=True)
        self.hud_overlay.setFixedWidth(220)
        self.hud_overlay.setFixedHeight(60)
        self.hud_overlay.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.hud_overlay.setStyleSheet("""
                    font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
                    font-size: 7px;
                    background-color: rgba(0,0,0,0);
                    color: #ffe135;
                    padding: 1px;
                    """)

        w = QWidget()
        w.setWindowFlags(Qt.FramelessWindowHint)
        w.setAttribute(Qt.WA_TransparentForMouseEvents)
        vbl = QVBoxLayout()
        vbl.addWidget(self.hud_overlay)
        w.setLayout(vbl)

        # self.ng_gl.addWidget(self.hud_overlay, 4, 0, 1, 1, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        self.ng_gl.addWidget(w, 4, 2, 1, 3, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        '''AFM/CAFM Widget'''
        self.afm_widget_ = QTextEdit()
        self.afm_widget_.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.afm_widget_.setObjectName('_tool_afmCafm')
        self.afm_widget_.setReadOnly(True)
        self._transformationWidget = QWidget()
        self._transformationWidget.setFixedWidth(170)
        self._transformationWidget.setMaximumHeight(70)
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.afm_widget_)
        self._transformationWidget.setLayout(vbl)

        self.ng_gl.addWidget(self._overlayLab, 0, 0, 5, 5,alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.ng_gl.setContentsMargins(0, 0, 0, 0)
        self.ngVertLab = VerticalLabel('Neuroglancer 3DEM View')
        self.ngVertLab.setObjectName('label_ng')

        self.DetailsContainer = QWidget()
        self.DetailsContainer.setAutoFillBackground(False)
        self.DetailsContainer.setAttribute(Qt.WA_TranslucentBackground, True)
        self.DetailsContainer.setStyleSheet("""background-color: rgba(255, 255, 255, 0);""")

        self.detailsCorrSpots = QWidget()
        self.corrSpotClabel = ClickLabel("<b>Signal</b>")
        self.corrSpotClabel.setStyleSheet("background-color: rgba(255, 255, 255, 0);color: #f3f6fb;")
        self.corrSpotClabel.setAutoFillBackground(False)
        self.corrSpotClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        def fn():
            self.detailsCorrSpots.setVisible(self.detailsCorrSpots.isHidden())
            self.corrSpotClabel.setText(
                ("<b><span style='color: #ffe135;'>Signal</span></b>",
                 "<b>Signal</b>")[self.detailsCorrSpots.isHidden()])
        self.corrSpotClabel.clicked.connect(fn)
        self.corrSpotClabel.clicked.connect(cfg.main_window.dataUpdateWidgets)

        self.cs0 = CorrSignalThumbnail(parent=self)
        self.cs1 = CorrSignalThumbnail(parent=self)
        self.cs2 = CorrSignalThumbnail(parent=self)
        self.cs3 = CorrSignalThumbnail(parent=self)
        self.cs0.setFixedSize(90,90)
        self.cs1.setFixedSize(90,90)
        self.cs2.setFixedSize(90,90)
        self.cs3.setFixedSize(90,90)

        gl = QGridLayout()
        gl.setSpacing(0)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.addWidget(self.cs0, 0, 0)
        gl.addWidget(self.cs1, 0, 1)
        gl.addWidget(self.cs2, 1, 0)
        gl.addWidget(self.cs3, 1, 1)
        self.csALL = QWidget()
        self.csALL.setLayout(gl)

        style = """font-family: 'Andale Mono', 'Ubuntu Mono', monospace; font-size: 10px; 
        background-color: rgba(0,0,0,.24); color: #f3f6fb; padding: 3px;"""

        # self.cspotSlider = QSlider(Qt.Orientation.Vertical)
        # self.cspotSlider.setRange(36,256)
        # start_size = 120
        # self.cspotSlider.setValue(start_size)
        # self.cspotSlider.setFixedSize(QSize(16,56))
        # self.csALL.setFixedSize(start_size, start_size)
        #
        # self.cspotSlider.sliderReleased.connect(lambda: self.csALL.setFixedSize(
        #     QSize(self.cspotSlider.value(), self.cspotSlider.value())))
        hbl = HBL()
        hbl.addWidget(self.csALL, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        # hbl.addWidget(self.cspotSlider, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.detailsCorrSpots.setLayout(hbl)
        self.detailsCorrSpots.hide()

        self.detailsSection = QLabel()
        self.detailsSection.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSection.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSection.setMaximumHeight(100)
        self.detailsSection.setMinimumWidth(230)
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
        self.detailsSection.setStyleSheet(style)
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
        self.detailsAFM.setStyleSheet(style)
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
        self.detailsSNR.setStyleSheet(style)
        self.detailsSNR.hide()

        self.detailsRuntime = QLabel()
        self.detailsRuntime.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsRuntime.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.runtimeClabel = ClickLabel('<b>dt</b>')
        self.runtimeClabel.setStyleSheet("background-color: rgba(255, 255, 255, 0); color: #f3f6fb;")
        self.runtimeClabel.setAutoFillBackground(False)
        self.runtimeClabel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.runtimeClabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        def fn():
            self.detailsRuntime.setVisible(not self.detailsRuntime.isVisible())
            self.runtimeClabel.setText(
                ("<b><span style='color: #ffe135;'>dt</span></b>",
                 "<b>dt</b>")[self.detailsRuntime.isHidden()])
        self.runtimeClabel.clicked.connect(fn)
        self.detailsRuntime.setWordWrap(True)
        self.detailsRuntime.setStyleSheet(style)
        self.detailsRuntime.hide()

        sep = "<span style='font-size: 15px; color: #f3f6fb; " \
                    "font-family: sans-serif;'>&nbsp;&#183;&nbsp;</span>"
        sep0, sep1, sep2, sep3 = QLabel(sep), QLabel(sep), QLabel(sep), QLabel(sep)
        self.labelsWidget = HWidget(self.detailsClabel, sep0, self.afmClabel, sep1,
                                    self.snrClabel, sep2, self.runtimeClabel, sep3,
                                    self.corrSpotClabel)
        self.labelsWidget.setContentsMargins(8, 0, 8, 0)
        self.labelsWidget.setFixedHeight(20)

        self.detailsDetailsWidget = QWidget()
        self.detailsDetailsWidget.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsDetailsWidget.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsDetailsWidget.show()
        hbl = HBL()
        hbl.addWidget(self.detailsSection, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsAFM, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsSNR, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsRuntime, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsCorrSpots, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.detailsDetailsWidget.setLayout(hbl)

        vbl = VBL()
        vbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        vbl.setSpacing(0)
        vbl.addWidget(self.labelsWidget, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
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
        self.ng_gl.setRowStretch(0, 1)
        self.ng_gl.setRowStretch(1, 1)
        self.ng_gl.setRowStretch(2, 100)
        self.ng_gl.setRowStretch(3, 25)
        self.ng_gl.setRowStretch(4, 0)
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

        self.zoomSliderAndLabel = VWidget()
        self.zoomSliderAndLabel.setFixedWidth(16)
        self.zoomSliderAndLabel.addWidget(self.zoomSlider)
        vlab = VerticalLabel('Zoom:')
        vlab.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.zoomSliderAndLabel.addWidget(vlab)

        self.ZdisplaySlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.ZdisplaySlider.setMaximum(20)
        self.ZdisplaySlider.setMinimum(1)
        self.ZdisplaySlider.valueChanged.connect(self.onSliderZmag)
        self.ZdisplaySlider.setValue(1.0)

        self.ZdisplaySliderAndLabel = VWidget()
        self.ZdisplaySliderAndLabel.setFixedWidth(16)
        self.ZdisplaySliderAndLabel.setMaximumHeight(100)
        self.ZdisplaySliderAndLabel.addWidget(self.ZdisplaySlider)
        vlab = VerticalLabel('Z-Mag:')
        vlab.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.ZdisplaySliderAndLabel.addWidget(vlab)

        self.MA_webengine_ref = QWebEngineView()
        self.MA_webengine_base = QWebEngineView()
        self.MA_webengine_stage = QWebEngineView()
        self.MA_webengine_ref.setMinimumWidth(200)
        self.MA_webengine_base.setMinimumWidth(200)
        # self.MA_webengine_ref.setMouseTracking(True)
        # self.MA_webengine_base.setMouseTracking(True)
        # self.MA_webengine_stage.setMouseTracking(True)
        '''Mouse move events will occur only when a mouse button is pressed down, 
        unless mouse tracking has been enabled with setMouseTracking() .'''
        self.MA_webengine_ref.setFocusPolicy(Qt.StrongFocus)
        self.MA_webengine_base.setFocusPolicy(Qt.StrongFocus)

        self.MA_webengine_stage.setMinimumWidth(240)
        self.MA_webengine_stage.setMinimumHeight(128)
        self.MA_webengine_stage.setFocusPolicy(Qt.StrongFocus)

        # NO CHANGE----------------------
        # self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
        # self.MA_viewer_ref.signals.ptsChanged.connect(self.update_MA_list_ref)
        # self.MA_viewer_base.signals.ptsChanged.connect(self.update_MA_list_base)
        # self.MA_viewer_ref.shared_state.add_changed_callback(self.update_MA_base_state)
        # self.MA_viewer_base.shared_state.add_changed_callback(self.update_MA_ref_state)
        # NO CHANGE----------------------

        # MA Stage Buffer Widget

        # self.MA_refViewerTitle = YellowTextLabel('Reference')
        # self.MA_baseViewerTitle = YellowTextLabel('Working')
        self.MA_refViewerTitle = QLabel('Left Image Points')
        self.MA_refViewerTitle.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif; font-weight: 600px;')
        self.MA_refViewerTitle.setMaximumHeight(14)

        self.MA_baseViewerTitle = QLabel('Right Image Points')
        self.MA_baseViewerTitle.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif; font-weight: 600px;')
        self.MA_baseViewerTitle.setMaximumHeight(14)

        self.MA_ptsListWidget_ref = QListWidget()
        self.MA_ptsListWidget_ref.setMaximumHeight(64)
        self.MA_ptsListWidget_ref.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.MA_ptsListWidget_ref.installEventFilter(self)
        self.MA_ptsListWidget_ref.itemClicked.connect(self.refListItemClicked)
        self.MA_ptsListWidget_ref.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')

        self.MA_refNextColorTxt = QLabel('Next Color: ')
        self.MA_refNextColorTxt.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.MA_refNextColorLab = QLabel()
        # self.MA_refNextColorLab.setMaximumHeight(12)
        self.MA_refNextColorLab.setFixedSize(60, 18)

        self.MA_ptsListWidget_base = QListWidget()
        self.MA_ptsListWidget_base.setMaximumHeight(64)
        self.MA_ptsListWidget_base.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.MA_ptsListWidget_base.installEventFilter(self)
        self.MA_ptsListWidget_base.itemClicked.connect(self.baseListItemClicked)
        self.MA_ptsListWidget_base.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')
        self.MA_baseNextColorTxt = QLabel('Next Color: ')
        self.MA_baseNextColorTxt.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.MA_baseNextColorLab = QLabel()
        # self.MA_baseNextColorLab.setMaximumHeight(12)
        self.MA_baseNextColorLab.setFixedSize(60, 18)

        self.baseNextColorWidget = HWidget(self.MA_baseNextColorTxt, self.MA_baseNextColorLab)
        self.baseNextColorWidget.setMaximumHeight(14)
        self.refNextColorWidget = HWidget(self.MA_refNextColorTxt, self.MA_refNextColorLab)
        self.refNextColorWidget.setMaximumHeight(14)

        self.gb_actionsMA = QGroupBox()
        self.fl_actionsMA = QFormLayout()
        self.fl_actionsMA.setSpacing(2)
        self.fl_actionsMA.setContentsMargins(0, 0, 0, 0)
        self.gb_actionsMA.setLayout(self.fl_actionsMA)

        self.automatic_label = QLabel()
        self.automatic_label.setStyleSheet('color: #06470c; font-size: 11px; font-weight: 600;')
        # font = QFont()
        # font.setFamily("Tahoma")
        # self.automatic_label.setFont(font)


        def fn():
            caller = inspect.stack()[1].function
            logger.critical('caller: %s' % caller)
            if self.tgl_alignMethod.isChecked():
                self.combo_MA_manual_mode.setEnabled(True)
                self.update_MA_widgets()
            else:
                self.combo_MA_manual_mode.setEnabled(False)
                cfg.data.set_selected_method('Auto-SWIM') #Critical always set project dict back to Auto-align
                self.set_method_label_text()
            self.updateCursor()
        self.tgl_alignMethod = AnimatedToggle(
            checked_color='#FFB000',
            pulse_checked_color='#44FFB000')
        self.tgl_alignMethod.toggled.connect(fn)
        self.tgl_alignMethod.toggled.connect(cfg.main_window._callbk_unsavedChanges)
        self.tgl_alignMethod.setFixedSize(44,26)

        def fn():
            caller = inspect.stack()[1].function
            logger.critical('caller: %s' % caller)
            # request = self.combo_MA_manual_mode.currentText()
            # cfg.data.set_selected_method(request)
            if cfg.data.selected_method() != 'Auto-SWIM':
                self.set_method_label_text()
        self.combo_MA_manual_mode = QComboBox(self)
        self.combo_MA_manual_mode.setFixedHeight(18)
        self.combo_MA_manual_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        items = ['Manual-Hint', 'Manual-Strict']
        self.combo_MA_manual_mode.addItems(items)
        self.combo_MA_manual_mode.currentTextChanged.connect(fn)
        self.combo_MA_manual_mode.currentTextChanged.connect(cfg.main_window._callbk_unsavedChanges)
        self.combo_MA_manual_mode.setEnabled(False)
        self.combo_MA_manual_mode.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')


        # mainToggle = AnimatedToggle()
        # secondaryToggle = AnimatedToggle(
        #     checked_color="#FFB000",
        #     pulse_checked_color="#44FFB000"
        # )
        # mainToggle.setFixedSize(mainToggle.sizeHint())
        # secondaryToggle.setFixedSize(mainToggle.sizeHint())
        # window.setLayout(QVBoxLayout())
        # window.layout().addWidget(QLabel("Main Toggle"))
        # window.layout().addWidget(mainToggle)
        # window.layout().addWidget(QLabel("Secondary Toggle"))
        # window.layout().addWidget(secondaryToggle)
        # mainToggle.stateChanged.connect(secondaryToggle.setChecked)

        lab = QLabel('Saved Method:')
        lab.setStyleSheet('font-size: 8px; font-family: Tahoma, sans-serif;')
        vw = VWidget(lab, self.automatic_label)
        vw.layout.setSpacing(0)

        # lab2 = QLabel('Mode:')
        # lab2.setStyleSheet('font-size: 8px; font-family: Tahoma, sans-serif;')
        # vw2 = VWidget(lab2, self.tgl_alignMethod)
        # vw2.layout.setSpacing(0)

        self.fl_actionsMA.addWidget(HWidget(vw, self.tgl_alignMethod, self.combo_MA_manual_mode))

        def fn():
            try:
                self.deleteAllMp()
                cfg.data.set_selected_method('Auto-SWIM')
                self.update_MA_widgets()
                self.set_method_label_text()
                self.tgl_alignMethod.setChecked(False)
            except:
                print_exception()
            else:
                self.btnClearMA.setEnabled(False)
        self.btnClearMA = QPushButton('Clear')
        self.btnClearMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnClearMA.setMaximumHeight(20)
        self.btnClearMA.setMaximumWidth(60)
        self.btnClearMA.clicked.connect(fn)
        self.btnClearMA.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')

        # self.btnClearMA.clicked.connect(self.initNeuroglancer)

        # your logic here

        def fn():
            pos = cfg.project_tab.MA_viewer_base.position()
            zoom = cfg.project_tab.MA_viewer_base.zoom()
            cfg.main_window.layer_left()
            # self.MA_viewer_ref.clear_layers()
            # self.MA_viewer_base.clear_layers()
            # self.initNeuroglancer()
            self.updateNeuroglancer()
            self.MA_viewer_base.set_position(pos)
            # self.MA_viewer_stage.initViewer()
            self.MA_viewer_stage = EMViewerStage(webengine=self.MA_webengine_stage)
            self.update_MA_widgets()
        tip = 'Go To Previous Section.'
        self.btnPrevSection = QPushButton()
        self.btnPrevSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnPrevSection.setStatusTip(tip)
        self.btnPrevSection.clicked.connect(fn)
        self.btnPrevSection.setFixedSize(QSize(18, 18))
        self.btnPrevSection.setIcon(qta.icon("fa.arrow-left", color=cfg.ICON_COLOR))
        self.btnPrevSection.setEnabled(False)


        def fn():
            pos = cfg.project_tab.MA_viewer_base.position()
            zoom = cfg.project_tab.MA_viewer_base.zoom()
            cfg.main_window.layer_right()
            # self.MA_viewer_ref.clear_layers()
            # self.MA_viewer_base.clear_layers()
            # self.initNeuroglancer()
            self.updateNeuroglancer()
            self.MA_viewer_base.set_position(pos)
            # self.MA_viewer_stage.initViewer()
            self.MA_viewer_stage = EMViewerStage(webengine=self.MA_webengine_stage)
            self.update_MA_widgets()
        tip = 'Go To Next Section.'
        self.btnNextSection = QPushButton()
        self.btnNextSection.clicked.connect(fn)
        self.btnNextSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnNextSection.setStatusTip(tip)
        self.btnNextSection.setFixedSize(QSize(18, 18))
        self.btnNextSection.setIcon(qta.icon("fa.arrow-right", color=cfg.ICON_COLOR))
        self.btnNextSection.setEnabled(False)


        def fn():
            cfg.data.set_all_methods_automatic()
            cfg.main_window.hud.done()
        self.btnResetAllMA = QPushButton('Set All Automatic')
        self.btnResetAllMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnResetAllMA.setFixedHeight(20)
        self.btnResetAllMA.setFixedWidth(102)
        self.btnResetAllMA.clicked.connect(fn)
        self.btnResetAllMA.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')

        def fn():
            cfg.main_window.hud.post('Aligning...')
            cfg.main_window.alignOneMp()
            # cfg.main_window.regenerateOne()
            cfg.main_window.hud.done()
        self.btnRealignMA = QPushButton('Align && Regenerate')
        # self.btnRealignMA.setStyleSheet()
        self.btnRealignMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnRealignMA.setFixedHeight(20)
        self.btnRealignMA.setFixedWidth(102)
        self.btnRealignMA.clicked.connect(fn)
        self.btnRealignMA.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')

        def fn():
            cfg.main_window.hud.post('Applying Manual Points...')
            if self.validate_MA_points():
                self.applyMps()
                cfg.data.set_selected_method(self.combo_MA_manual_mode.currentText())
                self.update_MA_widgets()
                self.set_method_label_text()
                cfg.main_window.hud.done()
            else:
                logger.warning('(!) validate points is misconfigured')
        self.btnApplyMA = QPushButton('Apply')
        self.btnApplyMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnApplyMA.setFixedHeight(20)
        self.btnApplyMA.setFixedWidth(60)
        self.btnApplyMA.clicked.connect(fn)
        self.btnApplyMA.setEnabled(False)
        self.btnApplyMA.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')

        self.btnExitMA = QPushButton('Exit')
        self.btnExitMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnExitMA.setFixedHeight(20)
        self.btnExitMA.setFixedWidth(60)
        self.btnExitMA.clicked.connect(cfg.main_window.exit_man_mode)
        self.btnExitMA.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')

        def fn():
            pass
        self.combo_MA_actions = QComboBox(self)
        self.combo_MA_actions.setStyleSheet('font-size: 11px')
        self.combo_MA_actions.setFixedHeight(20)
        self.combo_MA_actions.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        items = ['Set All Auto-SWIM']
        self.combo_MA_actions.addItems(items)
        self.combo_MA_actions.currentTextChanged.connect(fn)
        self.combo_MA_actions.currentTextChanged.connect(fn)
        btn_go = QPushButton()
        btn_go.clicked.connect(self.onMAaction)

        self.MA_actions = HWidget(self.combo_MA_actions, btn_go)

        sec_label = QLabel('Section:')
        sec_label.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        w_change_section = HWidget(sec_label, self.btnPrevSection, self.btnNextSection)
        w_change_section.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.fl_actionsMA.addWidget(
            HWidget(
                w_change_section,
                self.btnClearMA,
                self.btnApplyMA,
            )
        )
        self.fl_actionsMA.addWidget(
            HWidget(
                w,
                self.btnRealignMA,
                self.btnResetAllMA,
                self.btnExitMA
            )
        )

        gb1 = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.MA_refViewerTitle)
        vbl.addWidget(self.MA_ptsListWidget_ref)
        vbl.addWidget(self.refNextColorWidget)
        gb1.setLayout(vbl)

        gb2 = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.MA_baseViewerTitle)
        vbl.addWidget(self.MA_ptsListWidget_base)
        vbl.addWidget(self.baseNextColorWidget)
        gb2.setLayout(vbl)

        self.MA_sbw = HWidget(gb1, gb2)
        self.MA_sbw.layout.setSpacing(0)
        self.msg_MAinstruct = YellowTextLabel("⇧ + Click - Select at least 3 corresponding points")
        self.msg_MAinstruct.setFixedSize(290, 22)
        self.msg_MAinstruct.hide()

        def fn():
            # self.MA_viewer_stage = EMViewerStage(webengine=self.MA_webengine_stage)
            EMViewerStage(webengine=self.MA_webengine_stage)
        self.cb_showYellowFrame = QCheckBox('Show Frame')
        self.cb_showYellowFrame.setChecked(getData('ui,stage_viewer,show_yellow_frame'))
        self.cb_showYellowFrame.toggled.connect(lambda val: setData('ui,stage_viewer,show_yellow_frame', val))
        # self.cb_showYellowFrame.toggled.connect(self.initNeuroglancer)
        self.cb_showYellowFrame.toggled.connect(fn)

        self.labNoArrays = QLabel('')

        self.stageDetails = VWidget()
        lab = QLabel('No. Generated Arrays:')
        lab.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.stageDetails.addWidget(HWidget(lab, self.labNoArrays))
        #Todo self.labNoArrays

        self.gb_stageInfoText = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(0)
        vbl.addWidget(self.stageDetails)
        self.gb_stageInfoText.setLayout(vbl)


        self.MA_webengine_widget = VWidget()
        self.MA_webengine_widget.addWidget(self.MA_webengine_stage)
        self.MA_webengine_widget.addWidget(self.cb_showYellowFrame)


        self.MA_stageSplitter = QSplitter(Qt.Orientation.Vertical)
        # self.MA_stageSplitter.addWidget(self.MA_webengine_stage)
        self.MA_stageSplitter.addWidget(self.MA_webengine_widget)
        self.MA_stageSplitter.addWidget(VWidget(self.gb_stageInfoText, self.MA_sbw, self.gb_actionsMA))
        self.MA_stageSplitter.setCollapsible(0, False)
        self.MA_stageSplitter.setCollapsible(1, False)

        self.MA_ng_widget = QWidget()
        self.MA_gl = GL()
        # self.MA_gl.addWidget(self.MA_refViewerTitle, 3, 0, 1, 1)
        # self.MA_gl.addWidget(self.MA_baseViewerTitle, 3, 2, 1, 1)

        #Note, may be able to tailor this to webengine if wrapped in QWidget
        # self.MA_webengine_ref.setCursor(QCursor(QPixmap('src/resources/cursor_circle.png')))
        # self.MA_webengine_base.setCursor(QCursor(QPixmap('src/resources/cursor_circle.png')))


        self.MA_gl.addWidget(self.MA_webengine_ref, 0, 0, 4, 2)
        self.MA_gl.addWidget(self.MA_webengine_base, 0, 2, 4, 2)
        self.MA_gl.addWidget(self.msg_MAinstruct, 2, 0, 1, 4, alignment=Qt.AlignCenter)
        # self.MA_ng_widget.setCursor(QCursor(QPixmap('src/resources/cursor_circle.png')))
        self.MA_ng_widget.setLayout(self.MA_gl)

        self.MA_splitter = HSplitter(self.MA_ng_widget, self.MA_stageSplitter)
        self.MA_splitter.setSizes([.80 * cfg.WIDTH, .20 * cfg.WIDTH])
        self.MA_splitter.setCollapsible(0, False)
        self.MA_splitter.setCollapsible(1, False)
        self.MA_splitter.hide()

        self.weSplitter = HSplitter(self.ng_browser_container, self.MA_splitter)
        self.weSplitter.setCollapsible(0, False)
        self.weSplitter.setCollapsible(1, False)

        self.sideSliders = VWidget(self.ZdisplaySliderAndLabel, self.zoomSliderAndLabel)

        self.ng_browser_container_outer = HWidget(
            self.ngVertLab,
            self.weSplitter,
            self.sideSliders,
        )
        self.ng_browser_container_outer.layout.setSpacing(1)


    def updateCursor(self):
        QApplication.restoreOverrideCursor()
        self.msg_MAinstruct.hide()
        # self.msg_MAinstruct.setText("Toggle 'Mode' to select manual correspondence points")

        if getData('state,manual_mode'):
            if self.tgl_alignMethod.isChecked():
                pixmap = QPixmap('src/resources/cursor_circle.png')
                cursor = QCursor(pixmap.scaled(QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                QApplication.setOverrideCursor(cursor)
                self.msg_MAinstruct.show()




    def isManualReady(self):
        return self.tgl_alignMethod.isChecked()

    # def fade(self):
    #     self.MA_ng_widget.setWindowOpacity(0.5)
    #     QTimer.singleShot(1000, self.unfade)
    #
    #
    # def unfade(self):
    #     self.setWindowOpacity(1)


    def onMAaction(self):
        if self.combo_MA_actions.currentIndex() == 0:
            cfg.data.set_all_methods_automatic()



    def refListItemClicked(self, qmodelindex):
        item = self.MA_ptsListWidget_ref.currentItem()
        logger.info(f"Selected {item.text()}")


    def baseListItemClicked(self, qmodelindex):
        item = self.MA_ptsListWidget_base.currentItem()
        logger.info(f"Selected {item.text()}")


    # def copySaveAlignment(self):
    #     logger.critical('')
    #     dt = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    #     path = os.path.join(cfg.data.dest(), cfg.data.scale, 'img_staged',str(cfg.data.zpos), dt)
    #     if not os.path.isdir(path):
    #         os.mkdir(path)
    #     file = cfg.data.filename()
    #     out = os.path.join(path, os.path.basename(file))
    #     logger.critical('Copying FROM %s' % str(file))
    #     logger.critical('Copying TO %s' % str(out))
    #     shutil.copyfile(file, out)


    def set_method_label_text(self):
        method = cfg.data.selected_method()
        if method == 'Auto-SWIM':
            self.automatic_label.setText('<i>Auto SWIM Alignment</i>')
            self.automatic_label.setStyleSheet(
                'color: #06470c; font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')
        elif method == 'Manual-Hint':
            self.automatic_label.setText('<i>Manual Alignment (Hint)</i>')
            self.automatic_label.setStyleSheet(
                'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')
        elif method == 'Manual-Strict':
            self.automatic_label.setText('<i>Manual Alignment (Strict)</i>')
            self.automatic_label.setStyleSheet(
                'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')


    def validate_MA_points(self):
        # if cfg.data.selected_method() != 'Auto-SWIM':
        if len(self.MA_viewer_ref.pts.keys()) >= 3:
            if self.MA_viewer_ref.pts.keys() == self.MA_viewer_base.pts.keys():
                return True
        return False


    def update_MA_widgets(self):
        caller = inspect.stack()[1].function
        logger.info('caller: %s' %caller)
        if getData('state,manual_mode'):
            self.update_MA_list_base()
            self.update_MA_list_ref()
        self.dataUpdateMA()


    def dataUpdateMA(self):
        caller = inspect.stack()[1].function
        logger.info('caller: %s' % caller)
        # self.tgl_alignMethod.setChecked(is_manual)
        if cfg.data.selected_method() != 'Auto-SWIM':
            self.combo_MA_manual_mode.setCurrentText(cfg.data.selected_method())
        # if self.validate_MA_points() and method != 'Auto-SWIM':
        self.btnApplyMA.setEnabled(self.validate_MA_points() and self.tgl_alignMethod.isChecked())
        # self.combo_MA_manual_mode.setEnabled(self.validate_MA_points() and self.tgl_alignMethod.isChecked())
        self.combo_MA_manual_mode.setEnabled(self.tgl_alignMethod.isChecked())
        self.btnClearMA.setEnabled(bool(len(self.MA_viewer_ref.pts) + len(self.MA_viewer_base.pts)))
        self.btnPrevSection.setEnabled(cfg.data.zpos > 0)
        self.btnNextSection.setEnabled(cfg.data.zpos < len(cfg.data) - 1)


    def update_MA_list_ref(self):
        logger.info('')
        # self.MA_viewer_ref.pts = {}
        self.MA_ptsListWidget_ref.clear()
        self.MA_ptsListWidget_ref.update()
        n = 0
        for key in self.MA_viewer_ref.pts.keys():
            p = self.MA_viewer_ref.pts[key]
            _, x, y = p.point.tolist()
            item = QListWidgetItem('(%.1f,  %.1f)' % (x, y))
            item.setBackground(QColor(self.mp_colors[n]))
            self.MA_ptsListWidget_ref.addItem(item)
            n += 1
        self.MA_refNextColorLab.setStyleSheet(
            f'''background-color: {self.MA_viewer_ref.getNextUnusedColor()}''')


    def update_MA_list_base(self):
        logger.info('')
        # self.MA_viewer_base.pts = {}
        self.MA_ptsListWidget_base.clear()
        self.MA_ptsListWidget_base.update()
        n = 0
        for key in self.MA_viewer_base.pts.keys():
            p = self.MA_viewer_base.pts[key]
            _, x, y = p.point.tolist()
            item = QListWidgetItem('(%.1f,  %.1f)' % (x, y))
            item.setBackground(QColor(self.mp_colors[n]))
            self.MA_ptsListWidget_base.addItem(item)
            n += 1
        self.MA_baseNextColorLab.setStyleSheet(
            f'''background-color: {self.MA_viewer_base.getNextUnusedColor()}''')


    def update_MA_ref_state(self):
        caller = inspect.stack()[1].function
        # curframe = inspect.currentframe()
        # calframe = inspect.getouterframes(curframe, 2)
        # calname = str(calframe[1][3])
        # logger.info('Caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
        if caller != 'on_state_change':
            if self.MA_webengine_ref.isVisible():
                if self.MA_viewer_base.state.cross_section_scale:
                    # if self.MA_viewer_base.state.cross_section_scale < 10_000:
                    #     if self.MA_viewer_base.state.cross_section_scale != 1.0:
                    pos = self.MA_viewer_base.state.position
                    zoom = self.MA_viewer_base.state.cross_section_scale
                    if isinstance(pos,np.ndarray) or isinstance(zoom,np.ndarray):
                        state = copy.deepcopy(self.MA_viewer_ref.state)
                        if isinstance(pos, np.ndarray):
                            state.position = self.MA_viewer_base.state.position
                        if isinstance(zoom, float):
                            if self.MA_viewer_base.state.cross_section_scale < 10_000:
                                if self.MA_viewer_base.state.cross_section_scale != 1.0:
                                    state.cross_section_scale = self.MA_viewer_base.state.cross_section_scale
                        self.MA_viewer_ref.set_state(state)


    def update_MA_base_state(self):
        caller = inspect.stack()[1].function
        # curframe = inspect.currentframe()
        # calframe = inspect.getouterframes(curframe, 2)
        # calname = str(calframe[1][3])
        # logger.info('Caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
        if caller != 'on_state_change':
            if self.MA_webengine_base.isVisible():
                if self.MA_viewer_ref.state.cross_section_scale:
                    # if self.MA_viewer_ref.state.cross_section_scale < 10_000:
                    #     if self.MA_viewer_ref.state.cross_section_scale != 1.0:
                    pos = self.MA_viewer_ref.state.position
                    zoom = self.MA_viewer_ref.state.cross_section_scale
                    if isinstance(pos, np.ndarray) or isinstance(zoom, np.ndarray):
                        state = copy.deepcopy(self.MA_viewer_base.state)
                        if isinstance(pos, np.ndarray):
                            state.position = self.MA_viewer_ref.state.position
                        if isinstance(zoom, float):
                            if self.MA_viewer_ref.state.cross_section_scale < 10_000:
                                if self.MA_viewer_ref.state.cross_section_scale != 1.0:
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
        self.update_MA_widgets()
        self.updateNeuroglancer()


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
        self.update_MA_widgets()
        self.updateNeuroglancer()


    def deleteAllMpRef(self):
        logger.info('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        self.MA_viewer_ref.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        self.MA_viewer_ref.update_annotations()
        self.update_MA_widgets()
        self.updateNeuroglancer()


    def deleteAllMpBase(self):
        logger.info('Deleting All Base Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base Image Manual Correspondence Points from Buffer...')
        self.MA_viewer_base.pts.clear()
        self.MA_ptsListWidget_base.clear()
        self.MA_viewer_base.update_annotations()
        self.update_MA_widgets()
        self.updateNeuroglancer()


    def deleteAllMp(self):
        logger.info('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        cfg.data.clearMps()
        self.MA_viewer_ref.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        self.MA_viewer_base.pts.clear()
        self.MA_ptsListWidget_base.clear()
        self.MA_viewer_ref.update_annotations()
        self.MA_viewer_base.update_annotations()
        self.update_MA_widgets()
        self.applyMps()

        self.MA_viewer_ref.undrawAnnotations()
        self.MA_viewer_base.undrawAnnotations()

        # self.MA_viewer_ref.clear_layers()
        # self.MA_viewer_base.clear_layers()

        # pos = self.MA_viewer_ref.position()
        # zoom = self.MA_viewer_ref.zoom()
        # # pos_staged = self.MA_viewer_stage.position()
        # # zoom_staged = self.MA_viewer_stage.zoom()
        # self.updateNeuroglancer()
        # # self.initNeuroglancer()
        # self.MA_viewer_ref.set_position(pos)
        # self.MA_viewer_ref.set_zoom(zoom)
        # # self.MA_viewer_stage.set_position(pos_staged)
        # # self.MA_viewer_stage.set_zoom(zoom_staged)
        # self.MA_viewer_stage.set_zoom(self.MA_viewer_stage.initial_cs_scale)
        # # self.MA_viewer_stage.initViewer()

    def applyMps(self):
        cfg.main_window.hud.post('Saving Manual Correspondence Points...')
        logger.info('Saving Manual Correspondence Points...')
        if self.validate_MA_points():
            ref_pts, base_pts = [], []
            for key in self.MA_viewer_ref.pts.keys():
                p = self.MA_viewer_ref.pts[key]
                _, x, y = p.point.tolist()
                ref_pts.append((x, y))
            for key in self.MA_viewer_base.pts.keys():
                p = self.MA_viewer_base.pts[key]
                _, x, y = p.point.tolist()
                base_pts.append((x, y))
            logger.info('Setting+Saving Reference manual points: %s' % str(ref_pts))
            logger.info('Setting+Saving Working manual points: %s' % str(base_pts))
            cfg.data.set_manual_points('ref', ref_pts)
            cfg.data.set_manual_points('base', base_pts)

            # if self.rbAuto.isChecked():
            #     cfg.data.set_selected_method('Auto-SWIM')
            # if self.rbManHint.isChecked():
            #     cfg.data.set_selected_method('Manual-Hint')
            # elif self.rbManStrict.isChecked():
            #     cfg.data.set_selected_method('Manual-Strict')
            # else:
            #     cfg.data.set_selected_method('Auto-SWIM')

            cfg.data.print_all_match_points()
            cfg.main_window._saveProjectToFile(silently=True)
            cfg.main_window.hud.post('Match Points Saved!')


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
        self.bookmark_tab = self._tabs.currentIndex()
        self._tabs.setCurrentIndex(0)
        self.ng_browser_container.hide()
        self.MA_splitter.show()
        method = cfg.data.selected_method()
        self.set_method_label_text()
        self.tgl_alignMethod.setChecked(method == 'Auto-SWIM')
        self.MA_viewer_ref = MAViewer(role='ref', webengine=self.MA_webengine_ref)
        self.MA_viewer_base = MAViewer(role='base', webengine=self.MA_webengine_base)
        self.MA_viewer_stage = EMViewerStage(webengine=self.MA_webengine_stage)
        self.MA_viewer_ref.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
        self.MA_viewer_ref.signals.ptsChanged.connect(self.update_MA_widgets)
        self.MA_viewer_base.signals.ptsChanged.connect(self.update_MA_widgets)
        self.MA_viewer_ref.shared_state.add_changed_callback(self.update_MA_base_state)
        self.MA_viewer_base.shared_state.add_changed_callback(self.update_MA_ref_state)
        self.ngVertLab.setText('Manual Alignment Mode')
        self.ngVertLab.setStyleSheet("""background-color: #1b1e23; color: #f3f6fb;""")
        self.update_MA_widgets()
        self.tgl_alignMethod.setChecked(method != 'Auto-SWIM')
        cfg.main_window.dataUpdateWidgets()


    # def onExitManualMode(self):
    #     self.MA_ptsListWidget_ref.clear()
    #     self.MA_ptsListWidget_base.clear()
    #     self._tabs.setCurrentIndex(self.bookmark_tab)
    #     self.MA_splitter.hide()
    #     self.ng_browser_container.show()
    #     self.ngVertLab.setStyleSheet('')
    #     self.ngVertLab.setText('Neuroglancer 3DEM View')
    #     self.initNeuroglancer()


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
            if getData('state,manual_mode'):
                val = self.MA_viewer_ref.state.cross_section_scale
            else:
                val = self.viewer.state.cross_section_scale
            if val:
                if val != 0:
                    new_val = float(sqrt(val))
                    self.zoomSlider.setValue(new_val)
        except:
            print_exception()


    def onZoomSlider(self):
        caller = inspect.stack()[1].function
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        calname = str(calframe[1][3])
        # logger.critical('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))

        if caller not in  ('slotUpdateZoomSlider', 'setValue'):
            if getData('state,manual_mode'):
                val = self.zoomSlider.value()
                state = copy.deepcopy(self.MA_viewer_ref.state)
                state.cross_section_scale = val * val
                self.MA_viewer_ref.set_state(state)
            else:
                try:
                    val = self.zoomSlider.value()
                    state = copy.deepcopy(self.viewer.state)
                    state.cross_section_scale = val * val
                    self.viewer.set_state(state)
                except:
                    print_exception()


    def setZmag(self, val):
        logger.info(f'Setting Z-mag to {val}...')
        try:
            state = copy.deepcopy(self.viewer.state)
            state.relative_display_scales = {'z': val}
            self.viewer.set_state(state)
            cfg.main_window.update()
        except:
            print_exception()


    def onSliderZmag(self):
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' % caller)
        try:
            # for viewer in cfg.main_window.get_viewers():

            if getData('state,manual_mode'):
                val = self.ZdisplaySlider.value()
                state = copy.deepcopy(self.MA_viewer_ref.state)
                state.relative_display_scales = {'z': val}
                self.MA_viewer_ref.set_state(state)
                state = copy.deepcopy(self.MA_viewer_base.state)
                state.relative_display_scales = {'z': val}
                self.MA_viewer_base.set_state(state)
            else:
                val = self.ZdisplaySlider.value()
                # logger.info('val = %d' % val)
                state = copy.deepcopy(self.viewer.state)
                state.relative_display_scales = {'z': val}
                self.viewer.set_state(state)
            cfg.main_window.update()
        except:
            print_exception()


    def resetSliderZmag(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        try:
            if cfg.data['ui']['arrangement'] == 'comparison':
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
        vbl = VBL()
        vbl.addWidget(self.project_table)
        self.label_overview = VerticalLabel('Project Data Table View')
        self.label_overview.setObjectName('label_overview')
        hbl = HBL()
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.table_container = QWidget()
        self.table_container.setObjectName('table_container')
        self.table_container.setLayout(hbl)


    def updateTreeWidget(self):
        logger.info('Updating Project Tree...')
        self.treeview_model.load(cfg.data.to_dict())
        self.treeview.setModel(self.treeview_model)
        self.treeview.header().resizeSection(0, 300)
        self.treeview.expandAll()
        self.treeview.update()
        self.repaint()


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
        self.btnCollapseAll = QPushButton('Collapse All')
        self.btnCollapseAll.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.btnCollapseAll.setFixedSize(70,18)
        self.btnCollapseAll.clicked.connect(self.treeview.collapseAll)
        self.btnExpandAll = QPushButton('Expand All')
        self.btnExpandAll.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.btnExpandAll.setFixedSize(70,18)
        self.btnExpandAll.clicked.connect(self.treeview.expandAll)

        self.treeHbl = QHBoxLayout()
        self.treeHbl.setContentsMargins(2, 0, 2, 0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setObjectName('label_treeview')
        self.treeHbl.addWidget(lab)

        spcr = QWidget()
        spcr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        hbl = HBL()
        hbl.addWidget(self.btnCollapseAll)
        hbl.addWidget(self.btnExpandAll)
        hbl.addWidget(spcr)
        btns = QWidget()
        btns.setMaximumHeight(22)
        btns.setLayout(hbl)

        w = QWidget()
        vbl = VBL()
        vbl.addWidget(self.treeview)
        vbl.addWidget(btns)

        w.setLayout(vbl)
        self.treeHbl.addWidget(w)
        self._wdg_treeview.setLayout(self.treeHbl)


    def initUI_plot(self):
        '''SNR Plot Widget'''
        logger.info('')
        font = QFont()
        font.setBold(True)
        self.snr_plot = SnrPlot()
        self.lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#ede9e8', font_size=14)
        self.lab_yaxis.setMaximumWidth(20)
        hbl = HBL()
        hbl.addWidget(self.lab_yaxis)
        hbl.addWidget(self.snr_plot)
        self._plot_Xaxis = QLabel('Serial Section #')
        self._plot_Xaxis.setMaximumHeight(20)
        self._plot_Xaxis.setStyleSheet('color: #ede9e8; font-size: 14px;')
        self._plot_Xaxis.setContentsMargins(0, 0, 0, 8)
        self._plot_Xaxis.setFont(font)
        vbl = VBL()
        vbl.addLayout(hbl)
        vbl.addWidget(self._plot_Xaxis, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.snr_plt_wid = QWidget()
        self.snr_plt_wid.setLayout(vbl)
        self.snr_plt_wid.setStyleSheet('background-color: #1b1e23; font-weight: 550;')
        self._thumbnail_src = QLabel()
        self._thumbnail_aligned = QLabel()
        self.snrWebengine = QWebEngineView()
        self.snrWebengine.setMinimumWidth(256)
        self.snrPlotSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.snrPlotSplitter.setStyleSheet('background-color: #1b1e23;')
        self.snrPlotSplitter.addWidget(self.snr_plt_wid)
        self.snrPlotSplitter.addWidget(self.snrWebengine)



    def initUI_tab_widget(self):
        '''Tab Widget'''
        logger.info('')
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet('QTabBar::tab { height: 20px; width: 84px; }')
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setObjectName('project_tabs')
        self._tabs.addTab(self.ng_browser_container_outer, ' 3DEM ')
        self._tabs.addTab(self.table_container, ' Table ')
        self._tabs.setTabToolTip(1, os.path.basename(cfg.data.dest()))
        self._tabs.addTab(self._wdg_treeview, ' Data ')
        self._tabs.addTab(self.snrPlotSplitter, ' SNR Plot ')
        self._tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(1, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(2, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(3, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(0, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(1, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(2, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(3, QTabBar.LeftSide, None)
        vbl = VBL()
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