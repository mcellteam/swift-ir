#!/usr/bin/env python3

'''TODO This needs to have columns for indexing and section name (for sorting!)'''
import glob
import os, sys, logging, inspect, copy, time, warnings
from datetime import datetime
import textwrap
# from math import log10
from math import log2, sqrt
import neuroglancer as ng
import numpy as np
import shutil
import qtawesome as qta
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStyleOption, \
    QStyle, QTabBar, QTabWidget, QGridLayout, QTreeView, QSplitter, QTextEdit, QSlider, QPushButton, QSizePolicy, \
    QListWidget, QListWidgetItem, QMenu, QAction, QFormLayout, QGroupBox, QRadioButton, QButtonGroup, QComboBox, \
    QCheckBox, QToolBar, QListView, QDockWidget, QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QButtonGroup, \
    QStackedWidget, QHeaderView, QWidgetAction
from qtpy.QtCore import Qt, QSize, QRect, QUrl, Signal, QEvent, QThread, QTimer, QEventLoop, QPoint
from qtpy.QtGui import QPainter, QBrush, QFont, QPixmap, QColor, QCursor, QPalette, QStandardItemModel, \
    QDoubleValidator, QIntValidator
from qtpy.QtWebEngineWidgets import *
import src.config as cfg
from src.helpers import print_exception, getOpt, setOpt, getData, setData, get_scale_key, natural_sort
from src.viewer_em import EMViewer, EMViewerStage, EMViewerSnr
from src.viewer_ma import MAViewer
from src.ui.snr_plot import SnrPlot
from src.ui.widget_area import WidgetArea
from src.ui.project_table import ProjectTable
from src.ui.models.json_tree import JsonModel
from src.ui.sliders import DoubleSlider
from src.ui.thumbnail import CorrSignalThumbnail, ThumbnailFast
from src.ui.toggle_switch import ToggleSwitch
from src.ui.process_monitor import HeadupDisplay
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel
from src.ui.joystick import Joystick
from src import DataModel

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
        # self.webengine = QWebEngineView()
        self.webengine = WebEngine(ID='emViewer')
        self.webengine.loadFinished.connect(lambda: logger.info('Web engine load finished!'))
        setWebengineProperties(self.webengine)
        self.webengine.setStyleSheet('background-color: #222222;')

        self.focusedViewer = None

        self.setAutoFillBackground(True)
        # self.webengine.setMouseTracking(True)
        # self.webengine.setFocusPolicy(Qt.StrongFocus)
        self.initShader()
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        self.initUI_tab_widget()
        self._tabs.currentChanged.connect(self._onTabChange)
        self.manAlignBufferRef = []
        self.manAlignBufferBase = []
        self.mp_colors = cfg.glob_colors

        self.bookmark_tab = 0
        self.MA_ref_cscale = None
        self.MA_ref_zoom = None
        self.MA_base_cscale = None
        self.MA_base_zoom = None
        self._allow_zoom_change = True

        self.update_MA_widgets_calls = 0
        self.dataUpdateMA_calls = 0

        h = self.MA_webengine_ref.geometry().height()
        self.MA_stageSplitter.setSizes([int(.7 * h), int(.3 * h)])

        self.Q1.setAutoFillBackground(True)
        self.Q2.setAutoFillBackground(True)
        self.Q3.setAutoFillBackground(True)
        self.Q4.setAutoFillBackground(True)

        # with open('src/style/buttonstyle.qss', 'r') as f:
        #     self.buttonstyle = f.read()

        self.oldPos = None

    # def mousePressEvent(self, event):
    #     if event.button() == Qt.MouseButton.LeftButton:
    #         self.oldPos = event.globalPos()
    #
    # def mouseMoveEvent(self, event):
    #     if self.oldPos is not None:
    #         delta = event.globalPos() - self.oldPos
    #         self.move(self.pos() + delta)
    #         self.oldPos = event.globalPos()
    #
    # def mouseReleaseEvent(self, event):
    #     self.oldPos = None

    def load_data_from_treeview(self):
        self.datamodel = DataModel(self.treeview_model.to_json())
        cfg.data = self.datamodel

    def _onTabChange(self):
        logger.info('>>>> _onTabChange >>>>')
        index = self._tabs.currentIndex()
        QApplication.restoreOverrideCursor()
        index = self._tabs.currentIndex()

        # if getData('state,manual_mode'):
        #     pts_ref = cfg.refViewer.pts
        #     pts_base = cfg.baseViewer.pts
        #     self.initNeuroglancer()
        #     cfg.refViewer.pts = pts_ref
        #     cfg.baseViewer.pts = pts_base

        if index == 0:
            # self.updateNeuroglancer()
            # self.initNeuroglancer()
            cfg.emViewer.set_layer(cfg.data.zpos)
        elif index == 1:
            pass
        elif index == 2:
            self.updateTreeWidget()
            # self.treeview_model.jumpToLayer()
        elif index == 3:
            self.snr_plot.data = cfg.data
            self.snr_plot.initSnrPlot()
            self.initSnrViewer()
        logger.info('<<<< _onTabChange <<<<')

    # def refreshTab(self, index=None):
    def refreshTab(self):
        logger.info('Refreshing Tab...')

        index = self._tabs.currentIndex()
        man_mode = getData('state,manual_mode')

        if man_mode:
            pts_ref = cfg.refViewer.pts
            pts_base = cfg.baseViewer.pts

        if index == 0:
            self.initNeuroglancer()
            if man_mode:
                cfg.refViewer.pts = pts_ref
                cfg.baseViewer.pts = pts_base
        elif index == 1:
            self.project_table.setScaleData()
        elif index == 2:
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()
        elif index == 3:
            self.snr_plot.data = cfg.data
            self.snr_plot.initSnrPlot()
            self.initSnrViewer()

        logger.info('<<<< Refreshing')

    def initSnrViewer(self):

        # cfg.snrViewer = self.viewer =  cfg.emViewer = EMViewerSnr(webengine=self.snrWebengine)
        # cfg.snrViewer = cfg.emViewer = EMViewerSnr(webengine=self.snrWebengine)
        cfg.snrViewer = EMViewerSnr(webengine=self.snrWebengine)
        # cfg.snrViewer.initViewerSbs(orientation='vertical')
        # self.snrWebengine.setUrl(QUrl(cfg.snrViewer.url()))
        # cfg.snrViewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
        cfg.snrViewer.signals.stateChanged.connect(cfg.main_window.dataUpdateWidgets)
        cfg.snrViewer.signals.stateChangedAny.connect(cfg.snrViewer._set_zmag)
        # self.updateNeuroglancer()

    def shutdownNeuroglancer(self):
        logger.info('')
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if ng.is_server_running():
            ng.server.stop()
            # time.sleep(.5)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)

    def initNeuroglancer(self):
        QApplication.processEvents()
        logger.info(f'\n\n  Initializing Neuroglancer [{inspect.stack()[1].function}]...\n')
        caller = inspect.stack()[1].function
        if getData('state,manual_mode'):
            # cfg.main_window.comboboxNgLayout.setCurrentText('xy')
            # self.shutdownNeuroglancer()

            cfg.refViewer = MAViewer(role='ref', webengine=self.MA_webengine_ref)
            cfg.baseViewer = MAViewer(role='base', webengine=self.MA_webengine_base)
            cfg.stageViewer = EMViewerStage(webengine=self.MA_webengine_stage)

            cfg.main_window.swimWindowChanged.connect(cfg.refViewer.drawSWIMwindow)
            cfg.main_window.swimWindowChanged.connect(cfg.baseViewer.drawSWIMwindow)

            cfg.refViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)  # 0314
            # cfg.baseViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider) #0314

            cfg.refViewer.signals.ptsChanged.connect(self.update_MA_list_widgets)
            cfg.refViewer.signals.ptsChanged.connect(lambda: print('\n\n Ref Viewer pts changed!\n\n'))
            cfg.baseViewer.signals.ptsChanged.connect(self.update_MA_list_widgets)
            cfg.baseViewer.signals.ptsChanged.connect(lambda: print('\n\n Base Viewer pts changed!\n\n'))
            # cfg.refViewer.signals.stateChangedAny.connect(self.update_MA_base_state)
            # cfg.baseViewer.signals.stateChangedAny.connect(self.update_MA_ref_state)

            # cfg.baseViewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
            # cfg.baseViewer.signals.stateChanged.connect(cfg.main_window.dataUpdateWidgets) #WatchThis #WasOn

            # cfg.baseViewer.shared_state.add_changed_callback(cfg.emViewer.set_zmag)
            # cfg.baseViewer.signals.zoomChanged.connect(self.setZoomSlider) # Not responsible #WasOn

            cfg.baseViewer.signals.stateChangedAny.connect(cfg.baseViewer._set_zmag)  # Not responsible
            cfg.refViewer.signals.stateChangedAny.connect(cfg.refViewer._set_zmag)  # Not responsible
            cfg.stageViewer.signals.stateChangedAny.connect(cfg.stageViewer._set_zmag)  # Not responsible

            cfg.baseViewer.signals.swimAction.connect(cfg.main_window.alignOne)
            cfg.refViewer.signals.swimAction.connect(cfg.main_window.alignOne)

            self.update_MA_list_widgets()
            self.dataUpdateMA()
        else:
            # if caller != '_onGlobTabChange':
            logger.info('Initializing...')
            self.viewer = cfg.emViewer = EMViewer(webengine=self.webengine)
            cfg.emViewer.signals.stateChanged.connect(cfg.main_window.dataUpdateWidgets)  # 0424-
            cfg.emViewer.signals.stateChangedAny.connect(cfg.emViewer._set_zmag)
            # cfg.emViewer.shared_state.add_changed_callback(cfg.emViewer._set_zmag) #0424(?)
            cfg.emViewer.signals.zoomChanged.connect(self.setZoomSlider)
            # self.zoomSlider.sliderMoved.connect(self.onZoomSlider)  # Original #0314
            # self.zoomSlider.valueChanged.connect(self.onZoomSlider)

        # self.updateProjectLabels()

    def updateNeuroglancer(self):
        caller = inspect.stack()[1].function
        logger.info(f'Updating Neuroglancer Viewer (caller: {caller})')
        for viewer in self.get_viewers():
            viewer.initViewer()
        # if getData('state,MANUAL_MODE'):
        #     cfg.baseViewer.initViewer()
        #     cfg.refViewer.initViewer()
        #     cfg.stageViewer.initViewer()
        #     self.update_MA_list_widgets() # <-- !!!
        # else:
        #     self.viewer.initViewer()

        # self.setViewerModifications()

    # def setViewerModifications(self):
    #     logger.info('')
    #     if getData('state,MANUAL_MODE'):
    #         cfg.baseViewer.set_brightness()
    #         cfg.refViewer.set_brightness()
    #         cfg.stageViewer.set_brightness()
    #
    #         cfg.baseViewer.set_contrast()
    #         cfg.refViewer.set_contrast()
    #         cfg.stageViewer.set_contrast()
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
        # self.webengine.loadFinished.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))

        self.w_ng_display = QWidget()
        # self.w_ng_display.setStyleSheet('background-color: #222222;')
        self.w_ng_display.setAutoFillBackground(True)
        self.w_ng_display.setObjectName('w_ng_display')
        self.ng_gl = QGridLayout()
        self.ng_gl.addWidget(self.webengine, 0, 0, 5, 5)
        self._overlayRect = QWidget()
        self._overlayRect.setObjectName('_overlayRect')
        self._overlayRect.setStyleSheet("""background-color: rgba(0, 0, 0, 0.5);""")
        self._overlayRect.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayRect.hide()
        self.ng_gl.addWidget(self._overlayRect, 0, 0, 5, 5)
        self._overlayLab = QLabel('Test Label')
        self._overlayLab.setStyleSheet("""color: #FF0000; font-size: 28px;""")
        self._overlayLab.hide()

        self.hud_overlay = HeadupDisplay(cfg.main_window.app, overlay=True)
        self.hud_overlay.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.hud_overlay.set_theme_overlay()

        # self.joystick = Joystick()

        self.ng_gl.addWidget(self._overlayLab, 0, 0, 5, 5, alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.ng_gl.setContentsMargins(0, 0, 0, 0)
        self.ngVertLab = VerticalLabel('Neuroglancer 3DEM View')
        self.ngVertLab.setStyleSheet("""background-color: #222222; color: #ede9e8;""")

        style = """
        font-family: 'Andale Mono', 'Ubuntu Mono', monospace; 
        font-size: 9px; 
        background-color: rgba(0,0,0,.50); 
        color: #f3f6fb; 
        margin: 5px;
        padding: 5px;
        border-radius: 2px;
        """

        # self.detailsSection = QLabel()
        # self.detailsSection.setWindowFlags(Qt.FramelessWindowHint)
        # self.detailsSection.setAttribute(Qt.WA_TransparentForMouseEvents)
        # self.detailsSection.setWordWrap(True)
        # self.detailsSection.setStyleSheet(style)
        # self.detailsSection.hide()

        # self.detailsAFM = QLabel()
        # self.detailsAFM.setWindowFlags(Qt.FramelessWindowHint)
        # self.detailsAFM.setAttribute(Qt.WA_TransparentForMouseEvents)
        # self.detailsAFM.setMaximumHeight(100)
        # self.detailsAFM.setWordWrap(True)
        # self.detailsAFM.setStyleSheet(style)
        # self.detailsAFM.hide()

        self.detailsSNR = QLabel()
        self.detailsSNR.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSNR.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSNR.setMaximumHeight(100)
        self.detailsSNR.setWordWrap(True)
        self.detailsSNR.setStyleSheet(style)
        self.detailsSNR.hide()

        self.detailsDetailsWidget = QWidget()
        self.detailsDetailsWidget.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsDetailsWidget.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsDetailsWidget.show()
        hbl = HBL()
        # hbl.addWidget(self.detailsAFM, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self.detailsSNR, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.detailsDetailsWidget.setLayout(hbl)

        self.spreadW = QWidget()
        self.spreadW.setWindowFlags(Qt.FramelessWindowHint)
        self.spreadW.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.spreadW.setFixedSize(1, 12)
        self.spreadW.setVisible(getOpt('neuroglancer,SHOW_UI_CONTROLS'))

        self.spreadW2 = QWidget()
        self.spreadW2.setWindowFlags(Qt.FramelessWindowHint)
        self.spreadW2.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.spreadW2.setFixedSize(96, 1)

        self.spreadW3 = QWidget()
        self.spreadW3.setWindowFlags(Qt.FramelessWindowHint)
        self.spreadW3.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.spreadW3.setFixedSize(40, 1)

        # self.ng_gl.addWidget(self.joystick, 0, 0, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # self.ng_gl.addWidget(self.labelsWidget, 0, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.spreadW3, 0, 4, 1, 1,
                             alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.spreadW2, 1, 3, 2, 1,
                             alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.spreadW, 1, 4, 1, 1,
                             alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.ng_gl.addWidget(self.detailsDetailsWidget, 2, 0, 1, 4,
                             alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
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
        self.w_ng_display.setLayout(self.ng_gl)

        self.zoomSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.zoomSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.zoomSlider.setMouseTracking(True)
        # self.zoomSlider.setInvertedAppearance(True)
        self.zoomSlider.setMaximum(4)
        # self.zoomSlider.setMinimum(0.1)
        self.zoomSlider.setMinimum(0.02)

        # self.zoomSlider.sliderMoved.connect(self.onZoomSlider) #Original #0314
        self.zoomSlider.valueChanged.connect(self.onZoomSlider)
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
        self.zoomSliderAndLabel.layout.setSpacing(0)
        self.zoomSliderAndLabel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.zoomSliderAndLabel.setFixedWidth(16)
        self.zoomSliderAndLabel.addWidget(self.zoomSlider)
        vlab = VerticalLabel('Zoom:')
        # vlab.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.zoomSliderAndLabel.addWidget(vlab)

        self.ZdisplaySlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.ZdisplaySlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ZdisplaySlider.setMaximum(20)
        self.ZdisplaySlider.setMinimum(1)
        self.ZdisplaySlider.valueChanged.connect(self.onSliderZmag)
        self.ZdisplaySlider.setValue(1.0)

        self.ZdisplaySliderAndLabel = VWidget()
        self.ZdisplaySliderAndLabel.layout.setSpacing(0)
        self.ZdisplaySliderAndLabel.setFixedWidth(16)
        self.ZdisplaySliderAndLabel.setMaximumHeight(100)
        self.ZdisplaySliderAndLabel.addWidget(self.ZdisplaySlider)
        vlab = VerticalLabel('Z-Mag:')
        # vlab.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.ZdisplaySliderAndLabel.addWidget(vlab)

        self.MA_webengine_ref = WebEngine(ID='ref')
        self.MA_webengine_base = WebEngine(ID='base')
        self.MA_webengine_stage = WebEngine(ID='stage')
        self.MA_webengine_stage.setMinimumHeight(64)
        # setWebengineProperties(self.MA_webengine_ref)
        # setWebengineProperties(self.MA_webengine_base)
        # setWebengineProperties(self.MA_webengine_stage)
        # self.MA_webengine_ref.inFocus.triggered.connect(self.focusedViewerChanged)
        # self.MA_webengine_base.inFocus.triggered.connect(self.focusedViewerChanged)
        self.MA_webengine_ref.setMinimumWidth(100)
        self.MA_webengine_base.setMinimumWidth(100)
        # self.MA_webengine_ref.setMouseTracking(True)
        # self.MA_webengine_base.setMouseTracking(True)
        # self.MA_webengine_stage.setMouseTracking(True)
        '''Mouse move events will occur only when a mouse button is pressed down, 
        unless mouse tracking has been enabled with setMouseTracking() .'''

        self.MA_webengine_base.setFocus()

        # NO CHANGE----------------------
        # cfg.refViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
        # cfg.refViewer.signals.ptsChanged.connect(self.update_MA_list_ref)
        # cfg.baseViewer.signals.ptsChanged.connect(self.update_MA_list_base)
        # cfg.refViewer.shared_state.add_changed_callback(self.update_MA_base_state)
        # cfg.baseViewer.shared_state.add_changed_callback(self.update_MA_ref_state)
        # NO CHANGE----------------------

        # MA Stage Buffer Widget

        self.MA_refViewerTitle = QLabel('Reference Image (Left)')
        self.MA_refViewerTitle.setStyleSheet('font-size: 9px; font-family: Tahoma, sans-serif; font-weight: 600px;')
        self.MA_refViewerTitle.setMaximumHeight(14)

        self.MA_baseViewerTitle = QLabel('Transforming Image (Right)')
        self.MA_baseViewerTitle.setStyleSheet('font-size: 9px; font-family: Tahoma, sans-serif; font-weight: 600px;')
        self.MA_baseViewerTitle.setMaximumHeight(14)

        self.MA_ptsListWidget_ref = QListWidget()
        self.MA_ptsListWidget_ref.setMaximumHeight(54)
        self.MA_ptsListWidget_ref.setSelectionMode(QListWidget.MultiSelection)
        self.MA_ptsListWidget_ref.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.MA_ptsListWidget_ref.installEventFilter(self)
        self.MA_ptsListWidget_ref.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif; ')

        self.MA_refNextColorTxt = QLabel('Next Color: ')
        self.MA_refNextColorTxt.setStyleSheet('font-size: 9px; font-family: Tahoma, sans-serif; font-weight: 600px;')
        self.MA_refNextColorLab = QLabel()
        self.MA_refNextColorLab.setFixedSize(16, 16)

        self.MA_ptsListWidget_base = QListWidget()
        self.MA_ptsListWidget_base.setMaximumHeight(54)
        self.MA_ptsListWidget_base.setSelectionMode(QListWidget.MultiSelection)
        self.MA_ptsListWidget_base.setSelectionMode(QListWidget.ExtendedSelection)
        self.MA_ptsListWidget_base.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.MA_ptsListWidget_base.installEventFilter(self)
        self.MA_ptsListWidget_base.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.MA_baseNextColorTxt = QLabel('Next Color: ')
        self.MA_baseNextColorTxt.setStyleSheet('font-size: 9px; font-family: Tahoma, sans-serif; font-weight: 600px;')
        self.MA_baseNextColorLab = QLabel()
        self.MA_baseNextColorLab.setFixedSize(16, 16)

        self.MA_ptsListWidget_ref.itemSelectionChanged.connect(self.MA_ptsListWidget_base.selectionModel().clear)
        self.MA_ptsListWidget_base.itemSelectionChanged.connect(self.MA_ptsListWidget_ref.selectionModel().clear)

        self.baseNextColorWidget = HWidget(self.MA_baseNextColorTxt, self.MA_baseNextColorLab)
        self.baseNextColorWidget.setFixedHeight(12)
        self.refNextColorWidget = HWidget(self.MA_refNextColorTxt, self.MA_refNextColorLab)
        self.refNextColorWidget.setFixedHeight(12)

        self.automatic_label = QLabel()
        self.automatic_label.setStyleSheet('color: #06470c; font-size: 11px; font-weight: 600;')
        # font = QFont()
        # font.setFamily("Tahoma")
        # self.automatic_label.setFont(font)

        # def fn():
        #     caller = inspect.stack()[1].function
        #     logger.info('caller: %s' % caller)
        #     if caller == 'main':
        #         if self.tgl_alignMethod.isChecked():
        #             self.update_MA_list_widgets()
        #         else:
        #             cfg.data.set_method('Auto-SWIM') #Critical always set project dict back to Auto-align
        #             self.set_method_label_text()
        #         # cfg.project_tab.MA_viewer_ref.undrawSWIMwindow()
        #         # cfg.project_tab.MA_viewer_base.undrawSWIMwindow()
        #         if getOpt('neuroglancer,SHOW_SWIM_WINDOW'):
        #             cfg.project_tab.MA_viewer_ref.drawSWIMwindow()
        #             cfg.project_tab.MA_viewer_base.drawSWIMwindow()
        #         self.updateCursor()
        # self.tgl_alignMethod = AnimatedToggle(
        #     checked_color='#FFB000',
        #     pulse_checked_color='#44FFB000')
        # self.tgl_alignMethod.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.tgl_alignMethod.toggled.connect(fn)
        # self.tgl_alignMethod.toggled.connect(cfg.main_window._callbk_unsavedChanges)
        # self.tgl_alignMethod.setFixedSize(44,26)

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

        def fn():
            logger.info('')
            self.MA_stackedWidget.setCurrentIndex(5)

        self.btnMAsettings = QPushButton('Settings')
        self.btnMAsettings.setFixedSize(QSize(54, 18))
        self.btnMAsettings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnMAsettings.clicked.connect(fn)

        def fn():
            logger.info('')
            try:
                self.deleteAllMp()
                # cfg.data.set_method('Auto-SWIM')
                self.update_MA_list_widgets()
                # self.set_method_label_text()
                # self.tgl_alignMethod.setChecked(False)
                cfg.refViewer.undrawSWIMwindows()
                cfg.baseViewer.undrawSWIMwindows()
            except:
                print_exception()

        self.btnClearMA = QPushButton('Reset')
        self.btnClearMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnClearMA.setFixedSize(QSize(40, 18))
        self.btnClearMA.clicked.connect(fn)
        self.btnClearMA.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')

        # self.btnResetMA.clicked.connect(self.initNeuroglancer)

        # your logic here

        tip = 'Go To Previous Section.'
        self.btnPrevSection = QPushButton()
        self.btnPrevSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnPrevSection.setToolTip(tip)
        self.btnPrevSection.clicked.connect(self.MA_layer_left)
        self.btnPrevSection.setFixedSize(QSize(18, 18))
        self.btnPrevSection.setIcon(qta.icon("fa.arrow-left", color=cfg.ICON_COLOR))
        self.btnPrevSection.setEnabled(False)

        tip = 'Go To Next Section.'
        self.btnNextSection = QPushButton()
        self.btnNextSection.clicked.connect(self.MA_layer_right)
        self.btnNextSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnNextSection.setToolTip(tip)
        self.btnNextSection.setFixedSize(QSize(18, 18))
        self.btnNextSection.setIcon(qta.icon("fa.arrow-right", color=cfg.ICON_COLOR))
        self.btnNextSection.setEnabled(False)

        def fn():
            cfg.data.set_all_methods_automatic()
            # Todo include all of this functionality somewhere
            # cfg.data.set_auto_swim_windows_to_default()
            cfg.main_window.setControlPanelData()
            # cfg.data['data']['defaults']['whitening-factor'] = cfg.DEFAULT_WHITENING
            # cfg.data['data']['defaults']['initial-rotation'] = cfg.DEFAULT_INITIAL_ROTATION
            cfg.refViewer.drawSWIMwindow()
            cfg.baseViewer.drawSWIMwindow()
            self.dataUpdateMA()
            #     layer['alignment']['swim_settings'].setdefault('iterations', cfg.DEFAULT_SWIM_ITERATIONS)

        self.btnResetAllMA = QPushButton('Set All To Default Grid')
        self.btnResetAllMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnResetAllMA.setFixedSize(QSize(113, 18))
        self.btnResetAllMA.clicked.connect(fn)
        self.btnResetAllMA.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')

        def fn():
            cfg.main_window.hud.post('Aligning...')
            # self.applyMps()

            # Issue #CriticaL #Why does this erase part of the series?!?!
            # cfg.main_window.alignOne()
            # cfg.main_window.regenerate(cfg.data.scale, start=cfg.data.zpos, end=None)

            cfg.main_window.alignGenerateOne()

        self.btnRealignMA = QPushButton('Align && Regenerate')
        self.btnRealignMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnRealignMA.setFixedSize(QSize(107, 18))
        self.btnRealignMA.clicked.connect(fn)
        self.btnRealignMA.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')

        self.btnExitMA = QPushButton('Exit')
        self.btnExitMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnExitMA.setFixedSize(QSize(54, 18))
        self.btnExitMA.clicked.connect(cfg.main_window.exit_man_mode)
        self.btnExitMA.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')

        def fn():
            pass

        self.combo_MA_actions = QComboBox(self)
        self.combo_MA_actions.setStyleSheet('font-size: 11px')
        self.combo_MA_actions.setFixedHeight(20)
        self.combo_MA_actions.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        items = ['Set All Auto-SWIM']
        self.combo_MA_actions.addItems(items)
        self.combo_MA_actions.currentTextChanged.connect(fn)
        btn_go = QPushButton()
        btn_go.clicked.connect(self.onMAaction)

        self.MA_actions = HWidget(self.combo_MA_actions, btn_go)

        def fn():
            cfg.main_window.hud('Defaults Manual Alignment Settings Restored for Section %d' % cfg.data.zpos)
            cfg.data.set_whitening(cfg.DEFAULT_WHITENING)
            cfg.data.set_auto_swim_windows_to_default(current_only=True)
            cfg.data.set_manual_swim_windows_to_default(current_only=True)
            cfg.data.set_swim_iterations_glob(val=cfg.DEFAULT_SWIM_ITERATIONS)
            setData('state,stage_viewer,show_overlay_message', True)

            self.slider_AS_SWIM_window.setValue(int(cfg.data.swim_window_px()[0]))
            self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_px()[0]))
            self.AS_SWIM_window_le.setText(str(cfg.data.swim_window_px()[0]))

            self.slider_MA_SWIM_window.setValue(int(cfg.data.manual_swim_window_px()))
            self.MA_SWIM_window_le.setText(str(cfg.data.manual_swim_window_px()))

            self.spinbox_whitening.setValue(float(cfg.data.whitening()))

            self.spinbox_swim_iters.setValue(int(cfg.data.swim_iterations()))

            cfg.data.current_method = 'grid-default'
            self.method_rb0.setChecked(True)
            self.MA_stackedWidget.setCurrentIndex(0)

            cfg.refViewer.drawSWIMwindow()
            cfg.baseViewer.drawSWIMwindow()
            self.update()
            # self.initNeuroglancer()

        self.MA_settings_defaults_button = QPushButton('Use Default')
        # self.MA_settings_defaults_button.setMaximumSize(QSize(100, 18))
        self.MA_settings_defaults_button.setFixedSize(QSize(80, 18))
        self.MA_settings_defaults_button.clicked.connect(fn)

        def fn():
            # logs_path = os.path.join(cfg.data.dest(), 'logs', 'recipemaker.log')
            # with open(logs_path, 'r') as f:
            #     # lines = f.readlines()
            #     text = f.read()
            # self.te_logs.setText(text)
            # self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())
            self.refreshLogs()
            self.MA_stackedWidget.setCurrentIndex(4)

        self.btn_view_logs = QPushButton('Logs')
        self.btn_view_logs.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.btn_view_logs.setFixedSize(QSize(28, 18))
        self.btn_view_logs.clicked.connect(fn)

        self.btn_view_targ_karg = QPushButton('View Match Regions')

        def btn_view_targ_karg_fn():
            if self.MA_stackedWidget.currentIndex() == 3:
                self.updateMethodSelectWidget(soft=False)
                self.btn_view_targ_karg.setText('View Match Regions')
            else:
                self.setTargKargPixmaps()
                self.MA_stackedWidget.setCurrentIndex(3)
                self.btn_view_targ_karg.setText('Hide Match Regions')

        self.btn_view_targ_karg.clicked.connect(btn_view_targ_karg_fn)
        self.btn_view_targ_karg.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.btn_view_targ_karg.setFixedSize(QSize(110, 18))

        # sec_label = QLabel('Section:')
        # sec_label.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        # w_change_section = HWidget(sec_label, self.btnPrevSection, self.btnNextSection)
        # w_change_section.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # self.fl_actionsMA.addWidget(
        #     HWidget(
        #         ExpandingWidget(self),
        #         self.btn_view_logs,
        #         self.btn_view_targ_karg,
        #         self.MA_settings_defaults_button,
        #         # self.btnRunSwimMA,
        #         self.btnMAsettings,
        #         # self.btnClearMA,
        #         ))
        #
        # self.fl_actionsMA.addWidget(
        #     HWidget(
        #         ExpandingWidget(self),
        #         self.btnRealignMA,
        #         self.btnResetAllMA,
        #         self.btnExitMA))

        tip = "Perform a quick SWIM alignment to show match signals and SNR values, " \
              "but do not generate any new images"
        self.btnQuickSWIM = QPushButton('Quick\n&SWIM')
        self.btnQuickSWIM.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.btnQuickSWIM.setFixedSize(QSize(44, 38))
        self.btnQuickSWIM.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnQuickSWIM.clicked.connect(cfg.main_window.alignOne)
        hbl = HBL()
        hbl.setSpacing(0)
        hbl.setContentsMargins(2, 2, 2, 2)
        hbl.addWidget(self.btnQuickSWIM, alignment=Qt.AlignRight)
        hbl.addWidget(
            VWidget(
                HWidget(
                    ExpandingWidget(self),
                    self.btn_view_logs,
                    self.btn_view_targ_karg,
                    self.MA_settings_defaults_button,
                    # self.btnRunSwimMA,
                    self.btnMAsettings,
                    # self.btnClearMA,
                    ExpandingWidget(self)
                ),
                HWidget(
                    ExpandingWidget(self),
                    self.btnRealignMA,
                    self.btnResetAllMA,
                    self.btnExitMA,
                    ExpandingWidget(self))
            ), alignment=Qt.AlignCenter)
        self.MA_controls = QWidget()
        self.MA_controls.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.MA_controls.setLayout(hbl)
        # self.MA_controls.setStyleSheet("""
        # QPushButton {
        #     font-size: 12px;
        #     font-family: Tahoma, sans-serif;
        #     color: #f3f6fb;
        #     background-color: #1b1e23;
        #     border-width: 1px;
        #     border-color: #dadada;
        #     border-style: solid;
        #     padding: 1px;
        #     border-radius: 4px;
        #     outline: none;
        # }
        #
        # QPushButton:disabled {
        #     border-width: 1px;
        #     border-color: #dadada;
        #     border-style: solid;
        #     background-color: #dadada;
        #     padding: 1px;
        #     border-radius: 4px;
        #     color: #ede9e8;
        # }
        # """)

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
        self.msg_MAinstruct = YellowTextLabel("⇧ + Click - Select 3 corresponding points")
        self.msg_MAinstruct.setFixedSize(300, 24)

        self.gb_stageInfoText = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(0)
        # vbl.addWidget(self.stageDetails)
        self.gb_stageInfoText.setLayout(vbl)

        # self.MA_webengine_widget = VWidget()
        # self.MA_webengine_widget.addWidget(self.MA_webengine_stage)
        # self.MA_webengine_widget.addWidget(self.cb_showYellowFrame)

        self.btnTranslate = QPushButton('Move')
        self.btnTranslate.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.btnTranslate.setFixedSize(QSize(40, 18))
        self.btnTranslate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnTranslate.clicked.connect(self.onTranslate)

        self.le_x_translate = QLineEdit()
        self.le_x_translate.returnPressed.connect(self.onTranslate_x)
        self.le_x_translate.setFixedSize(QSize(48, 18))
        self.le_x_translate.setValidator(QIntValidator())
        # self.le_x_translate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.le_x_translate.setText('0')
        # self.le_x_translate.setMinimum(-99_999)
        # self.le_x_translate.setMaximum(99_999)
        # self.le_x_translate.setSuffix('px')
        self.le_x_translate.setAlignment(Qt.AlignCenter)

        self.le_y_translate = QLineEdit()
        self.le_y_translate.returnPressed.connect(self.onTranslate_y)
        self.le_y_translate.setFixedSize(QSize(48, 18))
        self.le_y_translate.setValidator(QIntValidator())
        # self.le_y_translate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.le_y_translate.setText('0')
        # self.le_y_translate.setMinimum(-99_999)
        # self.le_y_translate.setMaximum(99_999)
        # self.le_y_translate.setSuffix('px')
        self.le_y_translate.setAlignment(Qt.AlignCenter)

        self.translatePointsWidget = HWidget(
            # QLabel('Translation:'),
            ExpandingWidget(self),
            QLabel('up:'),
            self.le_y_translate,
            ExpandingWidget(self),
            QLabel('right:'),
            self.le_x_translate,
            self.btnTranslate
        )
        self.translatePointsWidget.layout.setAlignment(Qt.AlignRight)

        """  MA Settings Tab  """

        tip = "Window width for manual alignment (px)"

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info('caller: %s' % caller)
                cfg.data.set_manual_swim_window_px(int(self.slider_MA_SWIM_window.value()))
                self.MA_SWIM_window_le.setText(str(cfg.data.manual_swim_window_px()))
                cfg.refViewer.drawSWIMwindow()
                cfg.baseViewer.drawSWIMwindow()
                cfg.main_window._callbk_unsavedChanges()

        # self.slider_MA_SWIM_window = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.slider_MA_SWIM_window = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_MA_SWIM_window.setToolTip(tip)
        self.slider_MA_SWIM_window.valueChanged.connect(fn)
        self.slider_MA_SWIM_window.setFixedWidth(80)
        self.MA_SWIM_window_le = QLineEdit()
        self.MA_SWIM_window_le.setFixedWidth(48)

        def fn():
            caller = inspect.stack()[1].function
            logger.info('caller: %s' % caller)
            cfg.data.set_manual_swim_window_px(int(self.MA_SWIM_window_le.text()))
            self.dataUpdateMA()

        self.MA_SWIM_window_le.returnPressed.connect(fn)
        self.MA_SWIM_window_le.setFixedHeight(18)

        # self.spinbox_MA_swim_window = QSpinBox()
        # def fn():
        #     caller = inspect.stack()[1].function
        #     if caller == 'main':
        #         val = float(self.spinbox_MA_swim_window.value())
        #         cfg.data.set_manual_swim_window_px(val)
        #         self.slider_MA_SWIM_window.setValue(cfg.data.manual_swim_window_px())
        #         self.MA_SWIM_window_le.setText(str(cfg.data.manual_swim_window_px()))
        #         cfg.refViewer.drawSWIMwindow()
        #         cfg.baseViewer.drawSWIMwindow()
        # self.spinbox_MA_swim_window.valueChanged.connect(fn)
        # self.spinbox_MA_swim_window.setSuffix('px')
        # self.spinbox_MA_swim_window.setRange(8, 512)
        # self.spinbox_MA_swim_window.setSingleStep(2)

        tip = "Full window width for automatic alignment (px)"

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                cfg.data.set_swim_window_px(int(self.slider_AS_SWIM_window.value()))
                self.AS_SWIM_window_le.setText(str(cfg.data.swim_window_px()[0]))

                self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_px()[0]))
                self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_px()[0]))

                cfg.refViewer.drawSWIMwindow()
                cfg.baseViewer.drawSWIMwindow()
                cfg.main_window._callbk_unsavedChanges()

        self.slider_AS_SWIM_window = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_AS_SWIM_window.setToolTip(tip)
        self.slider_AS_SWIM_window.valueChanged.connect(fn)
        self.slider_AS_SWIM_window.setMaximumWidth(100)

        def fn():
            cfg.data.set_swim_window_px(int(self.AS_SWIM_window_le.text()))
            self.dataUpdateMA()

        self.AS_SWIM_window_le = QLineEdit()
        self.AS_SWIM_window_le.returnPressed.connect(fn)
        self.AS_SWIM_window_le.setFixedHeight(18)

        tip = "2x2 window width for automatic alignment (px)"

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                cfg.data.set_swim_2x2_px(int(self.slider_AS_2x2_SWIM_window.value()))
                self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_px()[0]))
                self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_px()[0]))
                cfg.refViewer.drawSWIMwindow()
                cfg.baseViewer.drawSWIMwindow()
                cfg.main_window._callbk_unsavedChanges()

        self.slider_AS_2x2_SWIM_window = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_AS_2x2_SWIM_window.setToolTip(tip)
        self.slider_AS_2x2_SWIM_window.valueChanged.connect(fn)
        self.slider_AS_2x2_SWIM_window.setMaximumWidth(100)

        def fn():
            cfg.data.set_swim_2x2_px(int(self.AS_2x2_SWIM_window_le.text()))
            self.dataUpdateMA()

        self.AS_2x2_SWIM_window_le = QLineEdit()
        self.AS_2x2_SWIM_window_le.returnPressed.connect(fn)
        self.AS_2x2_SWIM_window_le.setFixedHeight(18)

        tip = "SWIM Signal Whitening Factor"

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info('caller: %s' % caller)
                cfg.data.set_manual_whitening(float(self.spinbox_whitening.value()))  # Refactor
                cfg.data.set_whitening(float(self.spinbox_whitening.value()))  # Refactor

        self.spinbox_whitening = QDoubleSpinBox(self)
        self.spinbox_whitening.setFixedWidth(80)
        self.spinbox_whitening.setToolTip(tip)
        # self.spinbox_whitening.setFixedHeight(26)
        # self.sb_whiteningControl.setValue(cfg.DEFAULT_WHITENING)
        self.spinbox_whitening.valueChanged.connect(fn)
        self.spinbox_whitening.valueChanged.connect(cfg.main_window._callbk_unsavedChanges)
        # self.spinbox_whitening.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinbox_whitening.setDecimals(2)
        self.spinbox_whitening.setSingleStep(.01)
        self.spinbox_whitening.setMinimum(-1.0)
        self.spinbox_whitening.setMaximum(0.0)

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                val = self.spinbox_swim_iters.value()
                cfg.data.set_swim_iterations(val=val)
                logger.info(f'SWIM iterations for section #{cfg.data.zpos} is set to {val}')

        self.spinbox_swim_iters = QSpinBox(self)
        self.spinbox_swim_iters.setToolTip('# of SWIM iterations/refinements (default: 3)')
        self.spinbox_swim_iters.setFixedWidth(80)
        self.spinbox_swim_iters.valueChanged.connect(fn)
        self.spinbox_swim_iters.valueChanged.connect(cfg.main_window._callbk_unsavedChanges)
        # self.spinbox_swim_iters.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinbox_swim_iters.setMinimum(1)
        self.spinbox_swim_iters.setMaximum(9)

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                if self.rb_MA_hint.isChecked():
                    cfg.data.current_method = 'manual-hint'
                elif self.rb_MA_strict.isChecked():
                    cfg.data.current_method = 'manual-strict'

            cfg.main_window.statusBar.showMessage(f'Manual Alignment Option Set To: {cfg.data.current_method}')

        # self.rb_MA_hint = QRadioButton('Hint')
        # self.rb_MA_strict = QRadioButton('Strict')
        self.rb_MA_hint = QRadioButton('Match Regions (SWIM)')
        self.rb_MA_strict = QRadioButton('Match Points')
        self.MA_bg = QButtonGroup(self)
        self.MA_bg.setExclusive(True)
        self.MA_bg.addButton(self.rb_MA_hint)
        self.MA_bg.addButton(self.rb_MA_strict)
        self.MA_bg.buttonClicked.connect(fn)
        self.radioboxes_MA = HWidget(self.rb_MA_hint, self.rb_MA_strict)

        # self.MA_swim_window_widget = HWidget(self.radioboxes_MA, self.slider_MA_SWIM_window, self.MA_SWIM_window_le, self.btnClearMA)
        hbl = HBL()
        # hbl.addWidget(self.radioboxes_MA)
        # lab = QLabel('Window Width:')
        # lab.setStyleSheet('font-weight: 600;')
        hbl.addWidget(BoldLabel('Window Width:'))
        hbl.addWidget(ExpandingWidget(self))
        hbl.addWidget(self.slider_MA_SWIM_window)
        hbl.addWidget(self.MA_SWIM_window_le)
        hbl.addWidget(QLabel('px'))
        hbl.addWidget(self.btnClearMA)
        w = QWidget()
        w.setLayout(hbl)

        vbl = VBL()
        vbl.addWidget(HWidget(BoldLabel('Method:'), ExpandingWidget(self), self.radioboxes_MA))
        vbl.addWidget(HWidget(BoldLabel('Move Selection:'), ExpandingWidget(self), self.translatePointsWidget))
        vbl.addWidget(w)
        self.gb_MA_manual_controls = QGroupBox()
        self.gb_MA_manual_controls.setLayout(vbl)

        self.AS_swim_window_widget = HWidget(self.slider_AS_SWIM_window, self.AS_SWIM_window_le)
        self.AS_2x2_swim_window_widget = HWidget(self.slider_AS_2x2_SWIM_window, self.AS_2x2_SWIM_window_le)

        # colors = ['#75bbfd', '#e50000', '#137e6d', '#efb435']
        clr = {'ul': '#e50000', 'ur': '#efb435', 'll': '#137e6d', 'lr': '#acc2d9'}
        # self.Q1 = Rect(ID='Q1')
        # self.Q2 = Rect(ID='Q2')
        # self.Q3 = Rect(ID='Q3')
        # self.Q4 = Rect(ID='Q4')
        self.Q1 = ClickRegion(self, color=cfg.glob_colors[0], name='Q1')
        # self.Q1.clicked.connect()
        self.Q2 = ClickRegion(self, color=cfg.glob_colors[1], name='Q2')
        self.Q3 = ClickRegion(self, color=cfg.glob_colors[2], name='Q3')  # correct
        self.Q4 = ClickRegion(self, color=cfg.glob_colors[3], name='Q4')  # correct

        self.Q1.clicked.connect(self.updateAutoSwimRegions)
        self.Q2.clicked.connect(self.updateAutoSwimRegions)
        self.Q3.clicked.connect(self.updateAutoSwimRegions)
        self.Q4.clicked.connect(self.updateAutoSwimRegions)

        self.Q1.setAutoFillBackground(True)
        self.Q2.setAutoFillBackground(True)
        self.Q3.setAutoFillBackground(True)
        self.Q4.setAutoFillBackground(True)

        siz = 22
        self.Q1.setFixedSize(siz, siz)
        self.Q2.setFixedSize(siz, siz)
        self.Q3.setFixedSize(siz, siz)
        self.Q4.setFixedSize(siz, siz)

        self.Q_widget = QWidget()
        # self.Q_widget.setAutoFillBackground(True)
        self.gl_Q = QGridLayout()
        self.gl_Q.setSpacing(1)
        self.gl_Q.addWidget(self.Q1, 0, 0, 1, 1, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.gl_Q.addWidget(self.Q2, 0, 1, 1, 1, alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.gl_Q.addWidget(self.Q3, 1, 0, 1, 1, alignment=Qt.AlignRight | Qt.AlignTop)
        self.gl_Q.addWidget(self.Q4, 1, 1, 1, 1, alignment=Qt.AlignLeft | Qt.AlignTop)
        self.Q_widget.setLayout(self.gl_Q)

        self.gb_MA_settings = QGroupBox()
        # self.gb_MA_settings.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.fl_MA_settings = QFormLayout()
        self.fl_MA_settings.setVerticalSpacing(4)
        self.fl_MA_settings.setHorizontalSpacing(6)
        self.fl_MA_settings.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        self.fl_MA_settings.setSpacing(2)
        self.fl_MA_settings.setContentsMargins(0, 0, 0, 0)
        # self.fl_MA_settings.addRow("Manual Window", self.MA_swim_window_widget)
        self.fl_MA_settings.addRow("SWIM Full Window", self.AS_swim_window_widget)
        self.fl_MA_settings.addRow("SWIM 2x2 Window", self.AS_2x2_swim_window_widget)
        self.fl_MA_settings.addRow("Signal Whitening", self.spinbox_whitening)
        self.fl_MA_settings.addRow("SWIM Iterations", self.spinbox_swim_iters)
        # self.fl_MA_settings.addRow("Keep SWIM Cutouts", HWidget(self.cb_keep_swim_templates, self.btn_view_targ_karg))
        # self.fl_MA_settings.addRow("Keep SWIM Cutouts", self.cb_keep_swim_templates)
        self.fl_MA_settings.addRow("Select SWIM Regions\n(at least 3 required)", HWidget(self.Q_widget, ExpandingWidget(self)))
        # self.fl_MA_settings.addWidget(self.Q_widget)
        # self.fl_MA_settings.addWidget(self.MA_settings_defaults_button)
        self.gb_MA_settings.setLayout(self.fl_MA_settings)

        # self.MA_settings = QWidget()

        self.MA_tabs = QTabWidget()
        self.MA_tabs.setStyleSheet("""
        QTabBar::tab {
            height: 16px;
            font-size: 9px;
            margin: 0px;
            padding: 0px;
        }
        """)

        self.MA_use_global_defaults_lab = QLabel('Global default settings will be used.')
        self.MA_use_global_defaults_lab.setStyleSheet('font-size: 13px; font-weight: 600;')
        self.MA_use_global_defaults_lab.setAlignment(Qt.AlignCenter)




        self.method_rb0 = QRadioButton('Default Grid')

        tip = """Similar to the Default Grid method, but the user is able to avoid image defects 
        by adjusting the grid shape and location and adding or removing quadrants of the grid. 
        An affine transformation requires at least 3 regions (quadrants)."""
        self.method_rb1 = QRadioButton('Custom Grid')
        self.method_rb1.setStyleSheet("font-size: 10px;")
        self.method_rb1.setToolTip(tip)


        tip = """User provides an alignment hint for SWIM by selecting 3 matching regions (manual correspondence). 
        Note: An affine transformation requires at least 3 correspondence regions."""
        # self.method_rb2 = QRadioButton('Correspondence Points')
        self.method_rb2 = QRadioButton('Match Regions')
        self.method_rb2.setStyleSheet("font-size: 10px;")
        self.method_rb2.setToolTip(tip)


        self.method_bg = QButtonGroup(self)
        self.method_bg.setExclusive(True)
        self.method_bg.addButton(self.method_rb0)
        self.method_bg.addButton(self.method_rb1)
        self.method_bg.addButton(self.method_rb2)

        def method_bg_fn():
            logger.info('')
            cur_index = self.MA_stackedWidget.currentIndex()
            if self.method_rb0.isChecked():
                self.MA_stackedWidget.setCurrentIndex(0)
                cfg.data.current_method = 'grid-default'
            elif self.method_rb1.isChecked():
                self.MA_stackedWidget.setCurrentIndex(1)
                cfg.data.current_method = 'grid-custom'
            elif self.method_rb2.isChecked():
                self.MA_stackedWidget.setCurrentIndex(2)
                if cfg.data.current_method == 'manual-strict':
                    self.rb_MA_strict.setChecked(True)
                else:
                    cfg.data.current_method = 'manual-hint'
                    self.rb_MA_hint.setChecked(True)
            if cur_index == 3:
                self.MA_stackedWidget.setCurrentIndex(3)
                self.setTargKargPixmaps()
            elif cur_index == 4:
                self.MA_stackedWidget.setCurrentIndex(4)

            cfg.refViewer.drawSWIMwindow()
            cfg.baseViewer.drawSWIMwindow()
            self.msg_MAinstruct.setVisible(cfg.data.current_method not in ('grid-default', 'grid-custom'))
            # cfg.main_window.dataUpdateWidgets()
            if cfg.main_window.dw_signals.isVisible():
                cfg.main_window.updateCorrSignalsDrawer()

        self.method_bg.buttonClicked.connect(method_bg_fn)

        self.radioboxes_method = HWidget(self.method_rb0, self.method_rb1, self.method_rb2)

        self.method_lab = QLabel('Alignment Method:')
        self.method_lab.setStyleSheet('font-size: 11px; font-weight: 600;')
        self.gb_method_selection = QGroupBox()
        vbl = VBL()
        vbl.addWidget(self.method_lab)
        vbl.addWidget(self.radioboxes_method)
        # vbl.setSpacing(0)
        # vbl.addWidget(self.stageDetails)
        self.gb_method_selection.setLayout(vbl)
        self.gb_method_selection.setStyleSheet('font-size: 11px;')

        self.MA_points_tab = VWidget(
            # self.MA_swim_window_widget,
            self.MA_sbw,
            # self.translatePointsWidget,
            self.gb_MA_manual_controls, )

        self.rb_targ = QRadioButton('Reference')
        self.rb_targ.setChecked(True)
        self.rb_karg = QRadioButton('Moving')
        self.rb_bg_MA_targ_karg = QButtonGroup(self)
        self.rb_bg_MA_targ_karg.setExclusive(True)
        self.rb_bg_MA_targ_karg.addButton(self.rb_targ)
        self.rb_bg_MA_targ_karg.addButton(self.rb_karg)

        self.toggleTargKarg = QPushButton('Toggle')
        self.toggleTargKarg.setStyleSheet("font-size: 9px;")
        self.toggleTargKarg.setFixedSize(60,16)
        def fn_toggleTargKarg():
            if self.rb_targ.isChecked():
                self.rb_karg.setChecked(True)
            elif self.rb_karg.isChecked():
                self.rb_targ.setChecked(True)
            self.setTargKargPixmaps()

        self.toggleTargKarg.clicked.connect(fn_toggleTargKarg)



        def setTargKargPixmaps_fn():
            caller = inspect.stack()[1].function
            # if caller in ('main', 'fn_toggleTargKarg'):
            self.setTargKargPixmaps()

        self.rb_bg_MA_targ_karg.buttonClicked.connect(setTargKargPixmaps_fn)
        self.radioboxes_targ_karg = HWidget(self.rb_targ, self.rb_karg)

        self.targ_karg_back_btn = QPushButton('Back')
        self.targ_karg_back_btn.setFixedSize(QSize(40, 18))
        # def fn():
        #     self.MA_stackedWidget

        # self.targ_karg_back_btn.clicked.connect(lambda: self.MA_stackedWidget.setCurrentIndex(1))
        self.targ_karg_back_btn.clicked.connect(self.updateMethodSelectWidget)

        # clr = ['#efb435', '#e50000', '#137e6d', '#75bbfd']
        clr = cfg.glob_colors

        self.matches_tn0 = ThumbnailFast(self)
        self.matches_tn1 = ThumbnailFast(self)
        self.matches_tn2 = ThumbnailFast(self)
        self.matches_tn3 = ThumbnailFast(self)
        self.matches_tn0.border_color = clr[0]
        self.matches_tn1.border_color = clr[1]
        self.matches_tn2.border_color = clr[2]
        self.matches_tn3.border_color = clr[3]
        self.matches_tn0.updateStylesheet()
        self.matches_tn1.updateStylesheet()
        self.matches_tn2.updateStylesheet()
        self.matches_tn3.updateStylesheet()
        # self.matches_tn0.setStyleSheet(f"border: 2px solid #{clr['ul']};")
        # self.matches_tn1.setStyleSheet(f"border: 2px solid #{clr['ur']};")
        # self.matches_tn2.setStyleSheet(f"border: 2px solid #{clr['ll']};")
        # self.matches_tn3.setStyleSheet(f"border: 2px solid #{clr['lr']};")
        self.cutout_thumbnails = [self.matches_tn0, self.matches_tn1, self.matches_tn2, self.matches_tn3]

        max_siz = 80
        self.matches_tn0.setMaximumHeight(max_siz)
        self.matches_tn1.setMaximumHeight(max_siz)
        self.matches_tn2.setMaximumHeight(max_siz)
        self.matches_tn3.setMaximumHeight(max_siz)

        self.matches_tn0.setMaximumWidth(max_siz)
        self.matches_tn1.setMaximumWidth(max_siz)
        self.matches_tn2.setMaximumWidth(max_siz)
        self.matches_tn3.setMaximumWidth(max_siz)

        self.gl_targ_karg = QGridLayout()
        self.gl_targ_karg.setContentsMargins(2, 2, 2, 2)
        self.gl_targ_karg.setSpacing(2)
        self.gl_targ_karg.setAlignment(Qt.AlignCenter)
        self.gl_targ_karg.addWidget(self.matches_tn0, 0, 0)
        self.gl_targ_karg.addWidget(self.matches_tn1, 0, 1)
        self.gl_targ_karg.addWidget(self.matches_tn2, 1, 0)
        self.gl_targ_karg.addWidget(self.matches_tn3, 1, 1)
        # self.gl_targ_karg.addWidget(self.targ_karg_back_btn, 2, 0, 1, 2)
        self.targ_karg_widget = QWidget()
        self.targ_karg_widget.setLayout(self.gl_targ_karg)

        hbl = HBL()
        hbl.addWidget(self.targ_karg_back_btn, alignment=Qt.AlignRight)
        hbl.addWidget(self.radioboxes_targ_karg, alignment=Qt.AlignLeft)
        hbl.addWidget(self.toggleTargKarg, alignment=Qt.AlignLeft)
        hbl.addWidget(ExpandingWidget(self))

        w = QWidget()
        w.setLayout(hbl)

        self.swim_cutout_panel = QWidget()
        vbl = VBL()
        vbl.setSpacing(0)
        vbl.setContentsMargins(2, 2, 2, 2)
        self.lab_swim_matches = BoldLabel('Match Regions:')
        vbl.addWidget(self.lab_swim_matches, alignment=Qt.AlignLeft | Qt.AlignTop)
        vbl.addWidget(self.targ_karg_widget)
        vbl.addWidget(w, alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.swim_cutout_panel.setLayout(vbl)

        def bottom():
            self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())

        def top():
            self.te_logs.verticalScrollBar().setValue(0)

        self.logs_top_btn = QPushButton('Top')
        self.logs_top_btn.setFixedSize(QSize(40, 18))
        self.logs_top_btn.clicked.connect(top)

        self.logs_bottom_btn = QPushButton('Bottom')
        self.logs_bottom_btn.setFixedSize(QSize(40, 18))
        self.logs_bottom_btn.clicked.connect(bottom)

        self.logs_refresh_btn = QPushButton('Refresh')
        self.logs_refresh_btn.setFixedSize(QSize(40, 18))
        self.logs_refresh_btn.clicked.connect(self.refreshLogs)

        self.logs_back_btn = QPushButton('Back')
        self.logs_back_btn.setFixedSize(QSize(40, 18))
        self.logs_back_btn.clicked.connect(self.updateMethodSelectWidget)

        def fn():
            logger.info('')
            logs_path = os.path.join(cfg.data.dest(), 'logs')
            for filename in os.listdir(logs_path):
                file_path = os.path.join(logs_path, filename)
                logger.info(f'Removing: {file_path}...')
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))

            self.te_logs.setText('No Log To Show.')

        self.logs_delete_all_btn = QPushButton('Delete Logs')
        self.logs_delete_all_btn.setFixedSize(QSize(80, 18))
        self.logs_delete_all_btn.clicked.connect(fn)

        self.te_logs = QTextEdit()
        self.te_logs.setReadOnly(True)
        self.te_logs.setText('Logs...')

        self.lab_logs = BoldLabel('Logs:')

        self.rb_logs_swim_args = QRadioButton('SWIM Args')
        self.rb_logs_swim_args.setChecked(True)
        self.rb_logs_swim_out = QRadioButton('SWIM Out')
        self.rb_logs_mir_args = QRadioButton('MIR')
        self.rb_logs = QButtonGroup(self)
        self.rb_logs.setExclusive(True)
        self.rb_logs.addButton(self.rb_logs_swim_args)
        self.rb_logs.addButton(self.rb_logs_swim_out)
        self.rb_logs.addButton(self.rb_logs_mir_args)

        # self.btns_logs = QWidget()

        self.sw_logs = QStackedWidget()
        self.lab_ing = QLabel('Ingredients:')

        self.btn_ing0 = QPushButton('1')

        def fn():
            key = 'swim_args'
            if self.rb_logs_swim_args.isChecked():
                key = 'swim_args'
            elif self.rb_logs_swim_out.isChecked():
                key = 'swim_out'
            elif self.rb_logs_mir_args.isChecked():
                key = 'mir_args'
            args = '\n'.join(cfg.data['data']['scales'][cfg.data.scale]['stack'][cfg.data.zpos]['alignment'][key][
                                 'ingredient_0']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.te_logs.setText(' '.join(args))

        self.btn_ing0.clicked.connect(fn)

        self.btn_ing1 = QPushButton('2')

        def fn():
            key = 'swim_args'
            if self.rb_logs_swim_args.isChecked():
                key = 'swim_args'
            elif self.rb_logs_swim_out.isChecked():
                key = 'swim_out'
            elif self.rb_logs_mir_args.isChecked():
                key = 'mir_args'
            args = '\n'.join(cfg.data['data']['scales'][cfg.data.scale]['stack'][cfg.data.zpos]['alignment'][key][
                                 'ingredient_1']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.te_logs.setText(' '.join(args))

        self.btn_ing1.clicked.connect(fn)

        self.btn_ing2 = QPushButton('3')

        def fn():
            key = 'swim_args'
            if self.rb_logs_swim_args.isChecked():
                key = 'swim_args'
            elif self.rb_logs_swim_out.isChecked():
                key = 'swim_out'
            elif self.rb_logs_mir_args.isChecked():
                key = 'mir_args'
            args = '\n'.join(cfg.data['data']['scales'][cfg.data.scale]['stack'][cfg.data.zpos]['alignment'][key][
                                 'ingredient_2']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.te_logs.setText(' '.join(args))

        self.btn_ing2.clicked.connect(fn)
        self.btn_ing0.setFixedSize(QSize(40, 18))
        self.btn_ing1.setFixedSize(QSize(40, 18))
        self.btn_ing2.setFixedSize(QSize(40, 18))
        self.w_ingredients = HWidget(self.lab_ing, ExpandingWidget(self), self.btn_ing0, self.btn_ing1, self.btn_ing2)

        self.logs_widget = VWidget(
            HWidget(self.lab_logs, ExpandingWidget(self), self.rb_logs_swim_args, self.rb_logs_swim_out),
            self.te_logs,
            self.w_ingredients,
            HWidget(self.logs_back_btn,
                    ExpandingWidget(self),
                    self.logs_delete_all_btn,
                    self.logs_top_btn,
                    self.logs_bottom_btn,
                    self.logs_refresh_btn
                    ),
        )
        self.logs_widget.layout.setContentsMargins(4, 4, 4, 4)
        self.logs_widget.layout.setSpacing(4)

        self.sw_logs.addWidget(self.logs_widget)

        self.cb_clobber = QCheckBox()
        self.sb_clobber_pixels = QSpinBox()
        self.sb_clobber_pixels.setFixedSize(QSize(38, 18))
        self.sb_clobber_pixels.setMinimum(1)
        self.sb_clobber_pixels.setMaximum(16)

        self.cb_keep_swim_templates = QCheckBox()

        def fn():
            if self.cb_keep_swim_templates.isChecked():
                cfg.data.targ = True
                cfg.data.karg = True
            else:
                cfg.data.targ = False
                cfg.data.karg = False

        self.cb_keep_swim_templates.toggled.connect(fn)

        self.btn_settings_apply_cur_sec = QPushButton('Apply To Current Section')

        def fn():
            cfg.data.set_clobber(self.cb_clobber.isChecked(), glob=False)
            cfg.data.set_clobber_px(self.sb_clobber_pixels.value(), glob=False)
            cfg.main_window.tell('Settings Applied!')
            logger.info('Settings applied to current section.')

        self.btn_settings_apply_cur_sec.clicked.connect(fn)
        self.btn_settings_apply_cur_sec.setFixedSize(QSize(140, 18))

        self.btn_settings_apply_everywhere = QPushButton('Apply Everywhere')

        def fn():
            cfg.data.set_clobber(self.cb_clobber.isChecked(), glob=True)
            cfg.data.set_clobber_px(self.sb_clobber_pixels.value(), glob=True)
            cfg.main_window.tell('Settings Applied!')
            logger.info('Settings applied to entire project.')

        self.btn_settings_apply_everywhere.clicked.connect(fn)
        self.btn_settings_apply_everywhere.setFixedSize(QSize(140, 18))

        self.fl_settings = QFormLayout()
        self.fl_settings.setVerticalSpacing(4)
        self.fl_settings.setHorizontalSpacing(6)
        self.fl_settings.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        self.fl_settings.setSpacing(2)
        self.fl_settings.setContentsMargins(0, 0, 0, 0)
        self.fl_settings.addRow('Save Match Regions', self.cb_keep_swim_templates)
        self.fl_settings.addRow('Clobber Fixed Pattern', self.cb_clobber)
        self.fl_settings.addRow('Clobber Amount (px)', self.sb_clobber_pixels)
        self.fl_settings.addWidget(self.btn_settings_apply_cur_sec)
        self.fl_settings.addWidget(self.btn_settings_apply_everywhere)

        self.settings_widget = QWidget()
        self.settings_widget.setLayout(self.fl_settings)

        '''MA STACKED WIDGET'''
        self.MA_stackedWidget = QStackedWidget()
        self.MA_stackedWidget.addWidget(self.MA_use_global_defaults_lab)
        # self.MA_stackedWidget.addWidget(VWidget(self.gb_MA_settings, self.Q_widget))
        self.MA_stackedWidget.addWidget(self.gb_MA_settings)
        self.MA_stackedWidget.addWidget(self.MA_points_tab)
        self.MA_stackedWidget.addWidget(self.swim_cutout_panel)
        # self.MA_stackedWidget.addWidget(self.logs_widget)
        self.MA_stackedWidget.addWidget(self.sw_logs)
        self.MA_stackedWidget.addWidget(self.settings_widget)

        # self.MA_stackedWidget_gb = QGroupBox()
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # vbl.setSpacing(0)
        # vbl.addWidget(self.MA_stackedWidget)
        # self.MA_stackedWidget_gb.setLayout(vbl)

        self.MA_stageSplitter = QSplitter(Qt.Orientation.Vertical)
        # self.MA_stageSplitter.addWidget(self.MA_webengine_stage)
        self.MA_stageSplitter.addWidget(self.MA_webengine_stage)
        # self.MA_stageSplitter.addWidget(VWidget(self.radioboxes_method, self.MA_tabs, self.gb_actionsMA))
        # self.MA_stageSplitter.addWidget(VWidget(self.gb_method_selection, self.MA_stackedWidget, self.gb_actionsMA))
        # self.MA_stageSplitter.addWidget(VWidget(self.gb_method_selection, self.MA_stackedWidget_gb, self.MA_controls))
        self.MA_stageSplitter.addWidget(VWidget(self.gb_method_selection, self.MA_stackedWidget, self.MA_controls))
        self.MA_stageSplitter.setCollapsible(0, False)
        self.MA_stageSplitter.setCollapsible(1, False)

        self.MA_ng_widget = QWidget()
        self.MA_gl = GL()
        self.MA_gl.setSpacing(1)
        self.MA_gl.addWidget(self.MA_webengine_ref, 0, 0, 4, 2)
        self.MA_gl.addWidget(self.MA_webengine_base, 0, 2, 4, 2)
        self.MA_gl.addWidget(self.msg_MAinstruct, 3, 0, 1, 4, alignment=Qt.AlignCenter | Qt.AlignBottom)
        # self.MA_gl.addWidget(self.msg_MAinstruct, 3, 0, 1, 4, alignment=Qt.AlignCenter)
        # self.MA_ng_widget.setCursor(QCursor(QPixmap('src/resources/cursor_circle.png')))
        self.MA_ng_widget.setLayout(self.MA_gl)

        self.MA_splitter = HSplitter(self.MA_ng_widget, self.MA_stageSplitter)
        # self.MA_splitter.setSizes([int(.80 * cfg.WIDTH), int(.20 * cfg.WIDTH)])
        self.MA_splitter.setSizes([int(.80 * cfg.WIDTH), int(.20 * cfg.WIDTH)])
        self.MA_splitter.setCollapsible(0, False)
        self.MA_splitter.setCollapsible(1, False)
        # self.MA_splitter.setStyleSheet('background-color: #222222; color: #ede9e8;')
        self.MA_splitter.hide()

        # TOOLBARS

        ngFont = QFont('Tahoma')
        ngFont.setBold(True)
        pal = QPalette()
        pal.setColor(QPalette.Text, QColor("#FFFF66"))

        self.comboNgLayout = QComboBox(self)
        self.comboNgLayout.setFixedSize(100, 16)
        self.comboNgLayout.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # items = ['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '3d']
        items = ['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d']
        self.comboNgLayout.addItems(items)
        # self.comboNgLayout.activated.connect(cfg.main_window.fn_ng_layout_combobox)
        self.comboNgLayout.activated.connect(self.onNgLayoutCombobox)
        self.comboNgLayout.setCurrentText(getData('state,ng_layout'))

        # self.aligned_label = QLabel(' Aligned ')
        # self.aligned_label.setObjectName('green_toolbar_label')
        # self.aligned_label.setFixedHeight(16)
        # self.aligned_label.hide()
        # self.unaligned_label = QLabel(' Not Aligned ')
        # self.unaligned_label.setObjectName('red_toolbar_label')
        # self.unaligned_label.setFixedHeight(16)
        # self.unaligned_label.hide()
        # self.generated_label = QLabel(' Generated ')
        # self.generated_label.setObjectName('green_toolbar_label')
        # self.generated_label.setFixedHeight(16)
        # self.generated_label.hide()

        self.ngcl_background = NgClickLabel(self)
        self.ngcl_background.setText('Background')
        self.ngcl_background.setToolTip('Toggle Background')

        if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
            self.ngcl_background.setStyleSheet("""background: #808080; color: #f3f6fb; 
                        border-radius: 0px; padding: 2px; margin: 0px; font-weight: 600;  border-color: #339933;""")
        else:
            self.ngcl_background.setStyleSheet("""background: #222222; color: #f3f6fb; 
                        border-radius: 0px; padding: 2px; margin: 0px; font-weight: 600;  border-color: #339933;""")

        def fn():
            # logger.info(f"getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE') = {getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE')}")
            setOpt('neuroglancer,NEUTRAL_CONTRAST_MODE', not getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'))
            [v.updateHighContrastMode() for v in self.get_viewers()]

            if getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'):
                self.ngcl_background.setStyleSheet("""background: #808080; color: #f3f6fb; 
                        border-radius: 0px; padding: 2px; margin: 0px; font-weight: 600;  border-color: #339933;""")
            else:
                self.ngcl_background.setStyleSheet("""background: #222222; color: #f3f6fb; 
                        border-radius: 0px; padding: 2px; margin: 0px; font-weight: 600;  border-color: #339933;""")

        self.ngcl_background.clicked.connect(fn)
        self.ngcl_background.setToolTip('Neuroglancer background setting')

        # self.toolbarLabelsWidget = HWidget()
        # self.toolbarLabelsWidget.layout.setSpacing(2)
        # self.toolbarLabelsWidget.addWidget(self.aligned_label)
        # self.toolbarLabelsWidget.addWidget(self.unaligned_label)
        # self.toolbarLabelsWidget.addWidget(self.generated_label)

        toolbar_style = """
        QToolBar {
            background-color: #222222;
            color: #f3f6fb;
            font-size: 10px;
        }
        QToolButton {
            background-color: #1b1e23;
            color: #f3f6fb;
            border-radius: 3px;
            padding: 0px;
            border: 1px solid #808080;
            margin: 1px;
            height: 9px;
        }
        QToolButton::checked {
            background: #339933;
            color: #f3f6fb;
            border-radius: 3px;
            padding: 0px;
            margin: 1px;
        }
        QToolButton:hover {
            border: 1px solid #339933;
            color: #f3f6fb;

        }
        
        
        
        """
        self.lab_reference = QLabel('Reference Section')
        self.lab_reference.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")
        self.lab_transforming = QLabel('Transforming Section')
        self.lab_transforming.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")
        self.lab_output = QLabel('Aligned Output')
        self.lab_output.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")

        self.w_ng_MA_toolbar = QToolBar()
        self.w_ng_MA_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.w_ng_MA_toolbar.setIconSize(QSize(18, 18))
        self.w_ng_MA_toolbar.setFixedHeight(20)
        self.w_ng_MA_toolbar.setStyleSheet(toolbar_style)
        self.w_ng_MA_toolbar.setAutoFillBackground(True)

        self.layout_ng_MA_toolbar = QHBoxLayout()
        self.layout_ng_MA_toolbar.setContentsMargins(0, 0, 0, 0)
        self.w_ng_MA_toolbar.setLayout(self.layout_ng_MA_toolbar)

        # self.w_ng_MA_toolbar.addWidget(ExpandingWidget(self))
        # self.layout_ng_MA_toolbar.addStretch()
        self.w_ng_MA_toolbar.addWidget(self.lab_reference)
        self.w_ng_MA_toolbar.addWidget(ExpandingWidget(self))
        self.w_ng_MA_toolbar.addWidget(ExpandingWidget(self))
        # self.layout_ng_MA_toolbar.addStretch()
        self.w_ng_MA_toolbar.addWidget(self.lab_transforming)
        # self.layout_ng_MA_toolbar.addStretch()
        self.w_ng_MA_toolbar.addWidget(ExpandingWidget(self))
        self.w_ng_MA_toolbar.addWidget(ExpandingWidget(self))
        self.w_ng_MA_toolbar.addWidget(self.lab_output)
        # self.layout_ng_MA_toolbar.addStretch()
        # self.w_ng_MA_toolbar.addWidget(ExpandingWidget(self))
        self.w_ng_MA_toolbar.hide()



        self.w_ng_extended_toolbar = QToolBar()
        self.w_ng_extended_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.w_ng_extended_toolbar.setIconSize(QSize(18, 18))
        self.w_ng_extended_toolbar.setFixedHeight(20)
        self.w_ng_extended_toolbar.setStyleSheet(toolbar_style)
        self.w_ng_extended_toolbar.setAutoFillBackground(True)


        self.labShowHide = QLabel('Display: ')
        self.labShowHide.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")
        self.labNgLayout = QLabel('Layout: ')
        self.labNgLayout.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")
        # self.labScaleStatus = QLabel('Scale Status: ')
        self.labScaleStatus = QLabel('Status: ')
        self.labScaleStatus.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")

        def fn():
            logger.info('')
            opt = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            setOpt('neuroglancer,SHOW_UI_CONTROLS', not opt)
            opt = getOpt('neuroglancer,SHOW_UI_CONTROLS')
            self.spreadW.setVisible(opt)
            self.updateUISpacing()
            if cfg.emViewer:
                cfg.emViewer.updateUIControls()
            if opt:
                self.ngcl_uiControls.setStyleSheet("""background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600; border-color: #339933;""")
            else:
                self.ngcl_uiControls.setStyleSheet("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""")
        self.ngcl_uiControls = NgClickLabel(self)
        self.ngcl_uiControls.setText('NG Controls')
        self.ngcl_uiControls.clicked.connect(fn)
        self.ngcl_uiControls.setStyleSheet(("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""",
                                            """background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600; border-color: #339933;""")
                                           [getOpt('neuroglancer,SHOW_UI_CONTROLS')])


        def fn():
            logger.info('')
            opt = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            setOpt('neuroglancer,SHOW_YELLOW_FRAME', not opt)
            opt = getOpt('neuroglancer,SHOW_YELLOW_FRAME')
            # self.ngShowYellowFrameAction.setText(('Show Boundary', 'Hide Boundary')[opt])
            if cfg.emViewer:
                cfg.emViewer.updateDefaultAnnotations()
            if cfg.emViewer:
                cfg.emViewer.updateUIControls()
            if opt:
                self.ngcl_bounds.setStyleSheet("""background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600; border-color: #339933;""")
            else:
                self.ngcl_bounds.setStyleSheet("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""")
        self.ngcl_bounds = NgClickLabel(self)
        self.ngcl_bounds.setText('Bounds')
        self.ngcl_bounds.clicked.connect(fn)
        self.ngcl_bounds.setStyleSheet(("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""",
                                            """background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600;  border-color: #339933;""")
                                           [getOpt('neuroglancer,SHOW_YELLOW_FRAME')])


        def fn():
            logger.info('')
            opt = getOpt('neuroglancer,SHOW_AXIS_LINES')
            setOpt('neuroglancer,SHOW_AXIS_LINES', not opt)
            opt = getOpt('neuroglancer,SHOW_AXIS_LINES')
            # self.ngShowAxisLinesAction.setText(('Show Axis Lines', 'Hide Axis Lines')[opt])
            # for v in self.get_viewers():
            #     v.updateAxisLines()
            if cfg.emViewer:
                cfg.emViewer.updateAxisLines()
            if opt:
                self.ngcl_axes.setStyleSheet("""background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600;  border-color: #339933;""")
            else:
                self.ngcl_axes.setStyleSheet("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""")
        self.ngcl_axes = NgClickLabel(self)
        self.ngcl_axes.setText('Axes')
        self.ngcl_axes.clicked.connect(fn)
        self.ngcl_axes.setStyleSheet(("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""",
                                            """background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600; border-color: #339933;""")
                                           [getOpt('neuroglancer,SHOW_AXIS_LINES')])

        def fn():
            logger.info('')
            QApplication.processEvents()
            logger.info(f'isClicked = {self.ngcl_snr.isClicked}')
            if self.ngcl_snr.isClicked:
                self.ngcl_snr.setStyleSheet("""background: #339933; color: #f3f6fb; 
                    border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600; border-color: #339933;""")
                self.detailsSNR.show()
            else:
                self.ngcl_snr.setStyleSheet("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""")
                self.detailsSNR.hide()
            cfg.mw.dataUpdateWidgets()
        self.ngcl_snr = NgClickLabel(self)
        self.ngcl_snr.setText('SNR')
        self.ngcl_snr.clicked.connect(fn)
        self.ngcl_snr.setStyleSheet("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""")

        def fn():
            if not self.ngcl_shader.isClicked:
                self.shaderToolbar.hide()
                self.ngcl_shader.setToolTip('Show Brightness & Contrast Shaders')
            else:
                self.contrastSlider.setValue(int(cfg.data.contrast))
                self.contrastLE.setText('%.2f' % cfg.data.contrast)
                self.brightnessSlider.setValue(int(cfg.data.brightness))
                self.brightnessLE.setText('%.2f' % cfg.data.brightness)
                self.shaderToolbar.show()
                self.ngcl_shader.setToolTip('Hide Brightness & Contrast Shaders')
            self.ngcl_shader.setStyleSheet(("""background: #222222; color: #f3f6fb;
                        border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""",
                                          """background: #339933; color: #f3f6fb; 
                  border-radius: 3px; padding: 0px; margin: 1px; font-weight: 600; border-color: #339933;""")
                                         [self.ngcl_shader.isClicked])

        self.ngcl_shader = NgClickLabel(self)
        self.ngcl_shader.setText('Shader')
        self.ngcl_shader.clicked.connect(fn)
        self.ngcl_shader.setStyleSheet("""background: #222222; color: #f3f6fb;
                    border-radius: 3px; padding: 0px; margin: 1px; border-color: #339933;""")

        self.w_ng_extended_toolbar.addWidget(self.labNgLayout)
        self.w_ng_extended_toolbar.addWidget(self.comboNgLayout)
        self.w_ng_extended_toolbar.addWidget(ExpandingWidget(self))
        self.w_ng_extended_toolbar.addWidget(self.labShowHide)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_uiControls)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_shader)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_bounds)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_axes)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_snr)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_background)

        self.ngCombinedHwidget = HWidget(self.w_ng_display, self.MA_splitter)
        self.ngCombinedOutterVwidget = VWidget(self.w_ng_extended_toolbar, self.w_ng_MA_toolbar, self.shaderToolbar, self.ngCombinedHwidget)

        self.sideSliders = VWidget(self.ZdisplaySliderAndLabel, self.zoomSliderAndLabel)
        self.sideSliders.layout.setSpacing(0)
        self.sideSliders.setStyleSheet("""background-color: #222222; color: #ede9e8;""")

        self.ng_browser_container_outer = HWidget(
            self.ngVertLab,
            self.ngCombinedOutterVwidget,
            self.sideSliders,
        )
        self.ng_browser_container_outer.layout.setSpacing(0)

    def refreshLogs(self):
        logs_path = os.path.join(cfg.data.dest(), 'logs', 'recipemaker.log')
        if os.path.exists(logs_path):
            with open(logs_path, 'r') as f:
                # lines = f.readlines()
                text = f.read()
        else:
            text = 'No Log To Show.'
        self.te_logs.setText(text)
        self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())

    def setTargKargPixmaps(self):
        caller = inspect.stack()[1].function
        logger.critical(f'setTargKargPixmaps [{caller}] >>>>')

        # self.lab_swim_matches.setText(f'Match Regions ({cfg.data.current_method_pretty}):')
        self.lab_swim_matches.setText(f'Match Regions')
        basename = cfg.data.filename_basename()
        filename, extension = os.path.splitext(basename)
        if self.rb_targ.isChecked():
            tkarg = 't'
        else:
            tkarg = 'k'
        files = []
        for i in range(0, 4):
            name = '%s_%s_%s_%d%s' % (filename, cfg.data.current_method, tkarg, i, extension)
            files.append(os.path.join(cfg.data.dest(), cfg.data.scale, 'tmp', name))

        # if self.rb_targ.isChecked():
        #     files = natural_sort(glob.glob(os.path.join(cfg.data.dest(), cfg.data.scale, 'tmp',  f_targ)))
        # else:
        #     files = natural_sort(glob.glob(os.path.join(cfg.data.dest(), cfg.data.scale, 'tmp',  f_karg)))
        method = cfg.data.current_method
        # if method == 'grid-default':
        #     n_cutouts = sum(cfg.data.grid_default_regions)
        # elif method == 'grid-custom':
        #     n_cutouts = sum(cfg.data.grid_custom_regions)
        # elif method in ('manual-hint', 'manual-strict'):
        #     n_cutouts = len(cfg.data.manpoints()['base'])

        self.cutout_thumbnails[0].showBorder = False
        self.cutout_thumbnails[1].showBorder = False
        self.cutout_thumbnails[2].showBorder = False
        self.cutout_thumbnails[3].showBorder = False

        self.cutout_thumbnails[0].setPixmap(QPixmap())
        self.cutout_thumbnails[1].setPixmap(QPixmap())
        self.cutout_thumbnails[2].setPixmap(QPixmap())
        self.cutout_thumbnails[3].setPixmap(QPixmap())

        arg = 't' if self.rb_targ.isChecked() else 'k'
        logger.info(f'Files:\n{files}')

        if cfg.data.current_method in ('grid-custom', 'grid-default'):
            # for i in range(n_cutouts):
            for i in range(0, 4):
                use = True
                if method == 'grid-custom':
                    use = cfg.data.grid_custom_regions[i]
                elif method == 'grid-default':
                    use = cfg.data.grid_default_regions[i]

                logger.info(f'file  : {files[i]}  exists? : {os.path.exists(files[i])}  use? : {use}')
                if use:
                    if use and os.path.exists(files[i]):
                        tn = self.cutout_thumbnails[i]
                        tn.showBorder = True
                        path = os.path.join(cfg.data.dest(), cfg.data.scale, 'tmp', files[i])
                        tn.path = path
                        tn.showPixmap()

        if cfg.data.current_method == 'manual-hint':
            n_cutouts = len(cfg.data.manpoints()['base'])
            for i in range(0, 4):
                # 0, 1, 2, 3
                if i < n_cutouts:
                    if os.path.exists(files[i]):
                        tn = self.cutout_thumbnails[i]
                        tn.showBorder = True
                        path = os.path.join(cfg.data.dest(), cfg.data.scale, 'tmp', files[i])
                        tn.path = path
                        tn.showPixmap()

        self.cutout_thumbnails[0].updateStylesheet()
        self.cutout_thumbnails[1].updateStylesheet()
        self.cutout_thumbnails[2].updateStylesheet()
        self.cutout_thumbnails[3].updateStylesheet()

        QApplication.processEvents()
        self.update()
        logger.info('<<<< setTargKargPixmaps')

    def updateAutoSwimRegions(self):
        logger.info('')
        if cfg.data.current_method == 'grid-custom':
            cfg.data.grid_custom_regions = [self.Q1.isClicked, self.Q2.isClicked, self.Q3.isClicked, self.Q4.isClicked]
        elif cfg.data.current_method == 'grid-default':
            cfg.data.grid_default_regions = [self.Q1.isClicked, self.Q2.isClicked, self.Q3.isClicked, self.Q4.isClicked]
        cfg.refViewer.drawSWIMwindow()
        cfg.baseViewer.drawSWIMwindow()

    # def updateMethodSelectWidget(self):
    #     caller = inspect.stack()[1].function
    #     logger.info(f'caller: {caller}')
    #
    #     cur_index = self.MA_stackedWidget.currentIndex()
    #
    #     if cfg.data.current_method == 'grid-default':
    #         self.method_rb0.setChecked(True)
    #         self.MA_stackedWidget.setCurrentIndex(0)
    #     elif cfg.data.current_method == 'grid-custom':
    #         self.method_rb1.setChecked(True)
    #         self.MA_stackedWidget.setCurrentIndex(1)
    #     elif cfg.data.current_method in ('manual-hint', 'manual-strict'):
    #         self.method_rb2.setChecked(True)
    #         self.MA_stackedWidget.setCurrentIndex(2)
    #         if cfg.data.hint_or_strict == 'strict':
    #             self.rb_MA_strict.setChecked(True)
    #         else:
    #             self.rb_MA_hint.setChecked(True)
    #
    #     if cur_index in (3,4):
    #         self.MA_stackedWidget.setCurrentIndex(cur_index)

    def updateMethodSelectWidget(self, soft=False):
        caller = inspect.stack()[1].function
        cur_index = self.MA_stackedWidget.currentIndex()
        logger.critical(f'caller={caller}, soft={soft}, cur_index={cur_index}')

        if cfg.data.current_method == 'grid-default':
            self.method_rb0.setChecked(True)
            self.MA_stackedWidget.setCurrentIndex(0)
        elif cfg.data.current_method == 'grid-custom':
            self.method_rb1.setChecked(True)
            self.MA_stackedWidget.setCurrentIndex(1)
        elif cfg.data.current_method in ('manual-hint', 'manual-strict'):
            self.method_rb2.setChecked(True)
            self.MA_stackedWidget.setCurrentIndex(2)
            if cfg.data.current_method == 'manual-strict':
                self.rb_MA_strict.setChecked(True)
            else:
                self.rb_MA_hint.setChecked(True)

        if soft and (cur_index in (3, 4)):
            self.MA_stackedWidget.setCurrentIndex(cur_index)

        if self.MA_stackedWidget.currentIndex() == 3:
            self.btn_view_targ_karg.setText('Hide SWIM Matches')
        else:
            self.btn_view_targ_karg.setText('View SWIM Matches')

    def hideSecondaryNgTools(self):
        # for i in range(0, 14):
        #     self.w_ng_extended_toolbar.actions()[i].setVisible(False)
        for i in range(0, 10):
            self.w_ng_extended_toolbar.actions()[i].setVisible(False)

    def showSecondaryNgTools(self):
        # for i in range(0, 13):
        for i in range(0, 10):
            self.w_ng_extended_toolbar.actions()[i].setVisible(True)

    def onTranslate(self):
        if (self.MA_ptsListWidget_base.selectedIndexes() == []) and (self.MA_ptsListWidget_ref.selectedIndexes() == []):
            cfg.main_window.warn('No points are selected in the list')
            return

        selections = []
        if len(self.MA_ptsListWidget_ref.selectedIndexes()) > 0:
            role = 'ref'
            for sel in self.MA_ptsListWidget_ref.selectedIndexes():
                selections.append(int(sel.data()[0]))
        else:
            role = 'base'
            for sel in self.MA_ptsListWidget_base.selectedIndexes():
                selections.append(int(sel.data()[0]))

        pts_old = cfg.data.manpoints()[role]
        pts_new = pts_old

        d = {'ref': cfg.refViewer, 'base': cfg.baseViewer}
        viewer = d[role]

        for sel in selections:
            new_x = pts_old[sel][1] - int(self.le_x_translate.text())
            new_y = pts_old[sel][0] - int(self.le_y_translate.text())
            pts_new[sel] = (new_y, new_x)

        cfg.data.set_manpoints(role=role, matchpoints=pts_new)
        viewer.restoreManAlignPts()
        viewer.drawSWIMwindow()
        # if role == 'ref':
        #     self.update_MA_list_ref()
        # elif role == 'base':
        #     self.update_MA_list_base()

        cfg.main_window._callbk_unsavedChanges()

    def onTranslate_x(self):
        if (self.MA_ptsListWidget_base.selectedIndexes() == []) and (self.MA_ptsListWidget_ref.selectedIndexes() == []):
            cfg.main_window.warn('No points are selected in the list')
            return

        selections = []
        if len(self.MA_ptsListWidget_ref.selectedIndexes()) > 0:
            role = 'ref'
            for sel in self.MA_ptsListWidget_ref.selectedIndexes():
                selections.append(int(sel.data()[0]))
        else:
            role = 'base'
            for sel in self.MA_ptsListWidget_base.selectedIndexes():
                selections.append(int(sel.data()[0]))

        pts_old = cfg.data.manpoints()[role]
        pts_new = pts_old

        d = {'ref': cfg.refViewer, 'base': cfg.baseViewer}
        viewer = d[role]

        for sel in selections:
            new_x = pts_old[sel][1] - int(self.le_x_translate.text())
            new_y = pts_old[sel][0]
            pts_new[sel] = (new_y, new_x)

        cfg.data.set_manpoints(role=role, matchpoints=pts_new)
        viewer.restoreManAlignPts()
        viewer.drawSWIMwindow()
        # if role == 'ref':
        #     self.update_MA_list_ref()
        # elif role == 'base':
        #     self.update_MA_list_base()

        cfg.main_window._callbk_unsavedChanges()

    def onTranslate_y(self):
        if (self.MA_ptsListWidget_base.selectedIndexes() == []) and (self.MA_ptsListWidget_ref.selectedIndexes() == []):
            cfg.main_window.warn('No points are selected in the list')
            return

        selections = []
        if len(self.MA_ptsListWidget_ref.selectedIndexes()) > 0:
            role = 'ref'
            for sel in self.MA_ptsListWidget_ref.selectedIndexes():
                selections.append(int(sel.data()[0]))
        else:
            role = 'base'
            for sel in self.MA_ptsListWidget_base.selectedIndexes():
                selections.append(int(sel.data()[0]))

        pts_old = cfg.data.manpoints()[role]
        pts_new = pts_old

        d = {'ref': cfg.refViewer, 'base': cfg.baseViewer}
        viewer = d[role]

        for sel in selections:
            new_x = pts_old[sel][1]
            new_y = pts_old[sel][0] - int(self.le_y_translate.text())
            pts_new[sel] = (new_y, new_x)

        cfg.data.set_manpoints(role=role, matchpoints=pts_new)
        viewer.restoreManAlignPts()
        viewer.drawSWIMwindow()
        # if role == 'ref':
        #     self.update_MA_list_ref()
        # elif role == 'base':
        #     self.update_MA_list_base()

        cfg.main_window._callbk_unsavedChanges()

    def onNgLayoutCombobox(self) -> None:
        caller = inspect.stack()[1].function
        if caller in ('main', '<lambda>'):
            choice = self.comboNgLayout.currentText()
            logger.info('Setting ui,ng_layout to %s' % str(choice))
            # setData('ui,ng_layout', choice)
            setData('state,ng_layout', choice)
            try:
                cfg.main_window.hud("Setting Neuroglancer Layout to '%s'... " % choice)
                layout_actions = {
                    'xy': cfg.main_window.ngLayout1Action,
                    'yz': cfg.main_window.ngLayout2Action,
                    'xz': cfg.main_window.ngLayout3Action,
                    'xy-3d': cfg.main_window.ngLayout4Action,
                    'yz-3d': cfg.main_window.ngLayout5Action,
                    'xz-3d': cfg.main_window.ngLayout6Action,
                    # '3d': cfg.main_window.ngLayout7Action,
                    '4panel': cfg.main_window.ngLayout8Action
                }
                layout_actions[choice].setChecked(True)
                self.updateNeuroglancer()
            except:
                print_exception()
                logger.error('Unable To Change Neuroglancer Layout')

    # def updateProjectLabels(self):
    #     caller = inspect.stack()[1].function
    #     # logger.info(f'caller: {caller}')
    #     self.aligned_label.hide()
    #     self.unaligned_label.hide()
    #     self.generated_label.hide()
    #
    #     # if cfg.data['state']['mode'] == 'stack':
    #     #     setData('state,ng_layout', '4panel')
    #     #     cfg.main_window.combo_mode.setCurrentIndex(0)
    #     # elif cfg.data['state']['mode'] == 'comparison':
    #     #     setData('state,ng_layout', 'xy')
    #     #     cfg.main_window.combo_mode.setCurrentIndex(1)
    #
    #     # self.comboboxNgLayout.setCurrentText(cfg.data['ui']['ng_layout'])
    #     if cfg.data.is_aligned_and_generated():
    #         self.aligned_label.show()
    #         self.generated_label.show()
    #     elif cfg.data.is_aligned():
    #         self.aligned_label.show()
    #     else:
    #         self.unaligned_label.show()

    def MA_layer_left(self):
        if self.btnPrevSection.isEnabled():
            # pos = cfg.project_tab.MA_viewer_base.position()
            # zoom = cfg.project_tab.MA_viewer_base.zoom()
            # self.initNeuroglancer()
            cfg.main_window.layer_left()
            # self.updateNeuroglancer()
            # cfg.refViewer = MAViewer(role='ref', webengine=self.MA_webengine_ref)
            # cfg.baseViewer = MAViewer(role='base', webengine=self.MA_webengine_base)
            # cfg.stageViewer = EMViewerStage(webengine=self.MA_webengine_stage)

            # cfg.baseViewer.set_position(pos)
            # cfg.baseViewer.set_zoom(zoom)

            # cfg.stageViewer.initViewer()
            # self.update_MA_list_widgets()

        else:
            cfg.main_window.warn('The current section is the first section')

    def MA_layer_right(self):
        if self.btnNextSection.isEnabled():
            # pos = cfg.project_tab.MA_viewer_base.position()
            # zoom = cfg.project_tab.MA_viewer_base.zoom()
            # self.initNeuroglancer()
            cfg.main_window.layer_right()
            # self.updateNeuroglancer()

            # cfg.refViewer = MAViewer(role='ref', webengine=self.MA_webengine_ref)
            # cfg.baseViewer = MAViewer(role='base', webengine=self.MA_webengine_base)
            # cfg.stageViewer = EMViewerStage(webengine=self.MA_webengine_stage)

            # cfg.baseViewer.set_position(pos)
            # cfg.baseViewer.set_zoom(zoom)

            # cfg.stageViewer.initViewer()
            # self.update_MA_list_widgets()

        else:
            cfg.main_window.warn('The current section is the last section')

    def updateCursor(self):
        QApplication.restoreOverrideCursor()
        self.msg_MAinstruct.hide()
        # self.msg_MAinstruct.setText("Toggle 'Mode' to select manual correspondence points")

        if getData('state,manual_mode'):
            # if self.tgl_alignMethod.isChecked():
            if cfg.data.method() in ('manual-hint', 'manual-strict'):
                pixmap = QPixmap('src/resources/cursor_circle.png')
                cursor = QCursor(pixmap.scaled(QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                QApplication.setOverrideCursor(cursor)
                self.msg_MAinstruct.show()

    # def isManualReady(self):
    #     return self.tgl_alignMethod.isChecked()

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

    # def refListItemClicked(self, qmodelindex):
    #     item = self.MA_ptsListWidget_ref.currentItem()
    #     logger.info(f"Selected {item.text()}")
    #
    #
    # def baseListItemClicked(self, qmodelindex):
    #     item = self.MA_ptsListWidget_base.currentItem()
    #     logger.info(f"Selected {item.text()}")

    # def copySaveAlignment(self):
    #     logger.critical('')
    #     dt = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    #     path = os.path.join(cfg.data.dest(), cfg.data.scale, 'img_staged',str(cfg.data.zpos), dt)
    #     if not os.path.isdir(path):
    #         os.mkdir(path)
    #     file = cfg.data.filename()
    #     out = os.path.join(path, os.path.basename(filrestoreManAlignPtse))
    #     logger.critical('Copying FROM %s' % str(file))
    #     logger.critical('Copying TO %s' % str(out))
    #     shutil.copyfile(file, out)

    # def set_method_label_text(self):
    #     method = cfg.data.method()
    #     if method == 'Auto-SWIM':
    #         self.automatic_label.setText('<i>Auto SWIM Alignment</i>')
    #         self.automatic_label.setStyleSheet(
    #             'color: #06470c; font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')
    #     elif method == 'Manual-Hint':
    #         self.automatic_label.setText('<i>Manual Alignment (Hint)</i>')
    #         self.automatic_label.setStyleSheet(
    #             'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')
    #     elif method == 'Manual-Strict':
    #         self.automatic_label.setText('<i>Manual Alignment (Strict)</i>')
    #         self.automatic_label.setStyleSheet(
    #             'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif; font-weight: 600;')

    def validate_MA_points(self):
        # if len(cfg.refViewer.pts.keys()) >= 3:
        if cfg.refViewer.pts.keys() == cfg.baseViewer.pts.keys():
            return True
        return False

    def dataUpdateMA(self):
        self.dataUpdateMA_calls += 1

        caller = inspect.stack()[1].function
        logger.critical(f'>>>> dataUpdateMA caller: {caller} ; call #{self.dataUpdateMA_calls} ; cfg.data.current_method={cfg.data.current_method} >>>>')
        if getData('state,manual_mode'):

            # self.btnResetMA.setEnabled(bool(len(cfg.refViewer.pts) + len(cfg.baseViewer.pts)))
            self.btnPrevSection.setEnabled(cfg.data.zpos > 0)
            self.btnNextSection.setEnabled(cfg.data.zpos < len(cfg.data) - 1)
            self.msg_MAinstruct.setVisible(cfg.data.current_method not in ('grid-default', 'grid-custom'))
            # self.spinbox_whitening.setValue(float(cfg.data.manual_whitening()))
            self.spinbox_whitening.setValue(float(cfg.data.whitening()))
            # self.updateProjectLabels()  # 0424+

            img_siz = cfg.data.image_size()
            img_w = int(img_siz[0])

            # Update line edit widgets validator
            # Update slider maximum and minimums
            # Update widgets w/ data

            self.AS_SWIM_window_le.setValidator(QIntValidator(64, img_w))
            self.AS_SWIM_window_le.setText(str(cfg.data.swim_window_px()[0]))
            self.slider_AS_SWIM_window.setMaximum(img_w)
            self.slider_AS_SWIM_window.setValue(int(cfg.data.swim_window_px()[0]))

            self.AS_2x2_SWIM_window_le.setValidator(QIntValidator(64, int(img_w / 2)))
            self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_px()[0]))
            self.slider_AS_2x2_SWIM_window.setMaximum(int(img_w / 2))
            self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_px()[0]))

            self.MA_SWIM_window_le.setValidator(QIntValidator(64, img_w))
            self.MA_SWIM_window_le.setText(str(cfg.data.manual_swim_window_px()))
            self.slider_MA_SWIM_window.setMaximum(img_w)
            self.slider_MA_SWIM_window.setValue(int(cfg.data.manual_swim_window_px()))

            self.spinbox_swim_iters.setValue(int(cfg.data.swim_iterations()))

            method = cfg.data.current_method
            if method == 'grid-custom':
                self.btnRealignMA.setEnabled(True)
                grid = cfg.data.grid_custom_regions
                self.Q1.setActivated(grid[0])
                self.Q2.setActivated(grid[1])
                self.Q3.setActivated(grid[2])
                self.Q4.setActivated(grid[3])
            elif method == 'grid-default':
                grid = cfg.data.grid_default_regions
                self.Q1.setActivated(grid[0])
                self.Q2.setActivated(grid[1])
                self.Q3.setActivated(grid[2])
                self.Q4.setActivated(grid[3])

            self.updateEnabledButtonsMA()
            self.cb_clobber.setChecked(cfg.data.clobber())
            self.sb_clobber_pixels.setValue(int(cfg.data.clobber_px()))

            self.cb_keep_swim_templates.setChecked((cfg.data.targ == True) or (cfg.data.karg == True))
            try:
                self.updateMethodSelectWidget(soft=True)
            except:
                print_exception()
            if self.MA_stackedWidget.currentIndex() == 3:
                self.setTargKargPixmaps()

            if self.MA_stackedWidget.currentIndex() == 4:
                self.refreshLogs()

        logger.critical('<<<< dataUpdateMA <<<<')


    def updateEnabledButtonsMA(self):
        method = cfg.data.current_method
        sec = cfg.data.zpos
        realign_tip = 'SWIM align section #%d and generate an image' % sec
        if method == 'grid-custom':
            self.btnRealignMA.setEnabled(True)
            if sum(cfg.data.grid_custom_regions) >= 3:
                self.btnRealignMA.setEnabled(True)
                realign_tip = 'SWIM align section #%d using custom grid method' % sec
            else:
                self.btnRealignMA.setEnabled(False)
                realign_tip = 'SWIM alignment requires at least three regions to form an affine'
        elif method == 'grid-default':
            self.btnRealignMA.setEnabled(True)
            realign_tip = 'SWIM align section #%d using default grid regions'
        elif method in ('manual-hint', 'manual-strict'):
            if (len(cfg.data.manpoints()['ref']) >= 3) and (len(cfg.data.manpoints()['base']) >= 3):
                self.btnRealignMA.setEnabled(True)
                realign_tip = 'SWIM align section #%d using manual correspondence regions method ' \
                              'and generate an image' % sec
            else:
                self.btnRealignMA.setEnabled(False)
                realign_tip = 'SWIM alignment requires at least three regions to form an affine'

        self.btnRealignMA.setToolTip('\n'.join(textwrap.wrap(realign_tip, width=35)))

    def update_MA_list_widgets(self):
        self.update_MA_widgets_calls += 1
        self.setUpdatesEnabled(False)
        self.update_MA_list_base()
        self.update_MA_list_ref()
        self.setUpdatesEnabled(True)

    def update_MA_list_ref(self):
        logger.info('')
        # cfg.refViewer.pts = {}
        self.MA_ptsListWidget_ref.clear()
        self.MA_ptsListWidget_ref.update()
        n = 0
        for i, key in enumerate(cfg.refViewer.pts.keys()):
            p = cfg.refViewer.pts[key]
            _, y, x = p.point.tolist()
            item = QListWidgetItem('%d: x=%.1f, y=%.1f' % (i, x, y))
            # item.setBackground(QColor(self.mp_colors[n]))
            # item.setBackground(QColor(list(cfg.refViewer.pts)[i]))
            item.setForeground(QColor(list(cfg.refViewer.pts)[i]))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.MA_ptsListWidget_ref.addItem(item)
            n += 1
        self.MA_refNextColorLab.setStyleSheet(
            f'''background-color: {cfg.refViewer.getNextUnusedColor()}''')

    def update_MA_list_base(self):
        logger.info('')
        # cfg.baseViewer.pts = {}
        self.MA_ptsListWidget_base.clear()
        self.MA_ptsListWidget_base.update()
        n = 0
        for i, key in enumerate(cfg.baseViewer.pts.keys()):
            p = cfg.baseViewer.pts[key]
            _, x, y = p.point.tolist()
            item = QListWidgetItem('%d: x=%.1f, y=%.1f' % (i, x, y))
            # item.setBackground(QColor(self.mp_colors[n]))
            # item.setBackground(QColor(list(cfg.baseViewer.pts)[i]))
            item.setForeground(QColor(list(cfg.baseViewer.pts)[i]))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.MA_ptsListWidget_base.addItem(item)
            n += 1
        self.MA_baseNextColorLab.setStyleSheet(
            f'''background-color: {cfg.baseViewer.getNextUnusedColor()}''')

    def update_MA_ref_state(self):
        caller = inspect.stack()[1].function
        # curframe = inspect.currentframe()
        # calframe = inspect.getouterframes(curframe, 2)
        # calname = str(calframe[1][3])
        # logger.info('Caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
        if caller != 'on_state_change':
            if self.MA_webengine_ref.isVisible():
                if cfg.baseViewer.state.cross_section_scale:
                    # if cfg.baseViewer.state.cross_section_scale < 10_000:
                    #     if cfg.baseViewer.state.cross_section_scale != 1.0:
                    pos = cfg.baseViewer.state.position
                    zoom = cfg.baseViewer.state.cross_section_scale
                    if isinstance(pos, np.ndarray) or isinstance(zoom, np.ndarray):
                        state = copy.deepcopy(cfg.refViewer.state)
                        if isinstance(pos, np.ndarray):
                            state.position = cfg.baseViewer.state.position
                        if isinstance(zoom, float):
                            # if cfg.baseViewer.state.cross_section_scale < 10_000:
                            if cfg.baseViewer.state.cross_section_scale < 100:
                                # if cfg.baseViewer.state.cross_section_scale < cfg.refViewer.cs_scale:
                                # if cfg.baseViewer.state.cross_section_scale < 1: # solves runaway zoom effect
                                if cfg.baseViewer.state.cross_section_scale != 1.0:
                                    logger.info(f'Updating ref viewer state. OLD cs_scale: {state.cross_section_scale}')
                                    logger.info(
                                        f'Updating ref viewer state. NEW cs_scale: {cfg.baseViewer.state.cross_section_scale}')
                                    state.cross_section_scale = cfg.baseViewer.state.cross_section_scale
                        cfg.refViewer.set_state(state)

    def update_MA_base_state(self):
        caller = inspect.stack()[1].function
        # curframe = inspect.currentframe()
        # calframe = inspect.getouterframes(curframe, 2)
        # calname = str(calframe[1][3])
        # logger.info('Caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
        if caller != 'on_state_change':
            if self.MA_webengine_base.isVisible():
                if cfg.refViewer.state.cross_section_scale:
                    # if cfg.refViewer.state.cross_section_scale < 10_000:
                    #     if cfg.refViewer.state.cross_section_scale != 1.0:
                    pos = cfg.refViewer.state.position
                    zoom = cfg.refViewer.state.cross_section_scale

                    if isinstance(pos, np.ndarray) or isinstance(zoom, np.ndarray):
                        state = copy.deepcopy(cfg.baseViewer.state)
                        if isinstance(pos, np.ndarray):
                            state.position = cfg.refViewer.state.position
                        if isinstance(zoom, float):
                            # if cfg.refViewer.state.cross_section_scale < 10_000:
                            if cfg.refViewer.state.cross_section_scale < 100:
                                # if cfg.refViewer.state.cross_section_scale < cfg.refViewer.cs_scale:
                                # if cfg.refViewer.state.cross_section_scale < 1: # solves runaway zoom effect
                                if cfg.refViewer.state.cross_section_scale != 1.0:
                                    logger.info(
                                        f'Updating base viewer state. OLD cs_scale: {state.cross_section_scale}')
                                    logger.info(
                                        f'Updating base viewer state. NEW cs_scale: {cfg.refViewer.state.cross_section_scale}')
                                    state.cross_section_scale = cfg.refViewer.state.cross_section_scale
                        cfg.baseViewer.set_state(state)

    def deleteMpRef(self):
        # todo .currentItem().background().color().name() is no longer viable

        logger.info('Deleting A Reference Image Manual Correspondence Point from Buffer...')
        cfg.main_window.hud.post('Deleting A Reference Image Manual Correspondence Point from Buffer...')
        # for item in self.MA_ptsListWidget_ref.selectedItems():
        #     logger.critical(f'item:\n{item}')
        #     logger.critical(f'item.text():\n{item.text()}')
        #     self.MA_ptsListWidget_ref.takeItem(self.MA_ptsListWidget_ref.row(item))
        if self.MA_ptsListWidget_ref.currentItem():
            # del_key = self.MA_ptsListWidget_ref.currentItem().background().color().name()
            del_key = self.MA_ptsListWidget_ref.currentItem().foreground().color().name()
            logger.critical('del_key is %s' % del_key)
            cfg.refViewer.pts.pop(del_key)
            # if del_key in cfg.baseViewer.pts.keys():
            #     cfg.baseViewer.pts.pop(del_key)
        cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        cfg.refViewer.drawSWIMwindow()
        cfg.baseViewer.drawSWIMwindow()
        self.update_MA_list_widgets()
        self.updateEnabledButtonsMA()
        # self.updateNeuroglancer()

    def deleteMpBase(self):
        # todo .currentItem().background().color().name() is no longer viable

        logger.info('Deleting A Base Image Manual Correspondence Point from Buffer...')
        cfg.main_window.hud.post('Deleting A Base Image Manual Correspondence Point from Buffer...')
        # for item in self.MA_ptsListWidget_base.selectedItems():
        #     self.MA_ptsListWidget_base.takeItem(self.MA_ptsListWidget_base.row(item))
        if self.MA_ptsListWidget_base.currentItem():
            # del_key = self.MA_ptsListWidget_base.currentItem().background().color().name()
            del_key = self.MA_ptsListWidget_base.currentItem().foreground().color().name()
            logger.critical('del_key is %s' % del_key)
            cfg.baseViewer.pts.pop(del_key)
            # if del_key in cfg.refViewer.pts.keys():
            #     cfg.refViewer.pts.pop(del_key)
        cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        cfg.refViewer.drawSWIMwindow()
        cfg.baseViewer.drawSWIMwindow()
        self.update_MA_list_widgets()
        self.updateEnabledButtonsMA()
        # self.initNeuroglancer()

    def deleteAllMpRef(self):
        logger.info('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        cfg.refViewer.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        self.update_MA_list_widgets()
        # cfg.refViewer.draw_point_annotations()
        cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        cfg.refViewer.drawSWIMwindow()
        cfg.baseViewer.drawSWIMwindow()
        self.updateEnabledButtonsMA()

    def deleteAllMpBase(self):
        logger.info('Deleting All Base Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base Image Manual Correspondence Points from Buffer...')
        cfg.baseViewer.pts.clear()
        self.MA_ptsListWidget_base.clear()
        self.update_MA_list_widgets()
        cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        cfg.refViewer.drawSWIMwindow()
        cfg.baseViewer.drawSWIMwindow()
        self.updateEnabledButtonsMA()

    def deleteAllMp(self):
        logger.info('deleteAllMp >>>>')
        logger.info('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        cfg.data.clearMps()
        cfg.refViewer.pts.clear()
        cfg.baseViewer.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        self.MA_ptsListWidget_base.clear()
        cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        cfg.refViewer.undrawSWIMwindows()
        cfg.baseViewer.undrawSWIMwindows()
        self.updateEnabledButtonsMA()

        logger.info('<<<< deleteAllMp')

    # def applyMps(self):
    #
    #     if self.validate_MA_points():
    #         cfg.main_window.hud.post('Saving Manual Correspondence Points...')
    #         logger.info('Saving Manual Correspondence Points...')
    #         cfg.main_window.statusBar.showMessage('Manual Points Saved!', 3000)
    #         ref_pts, base_pts = [], []
    #         for key in cfg.refViewer.pts.keys():
    #             p = cfg.refViewer.pts[key]
    #             _, x, y = p.point.tolist()
    #             ref_pts.append((x, y))
    #         for key in cfg.baseViewer.pts.keys():
    #             p = cfg.baseViewer.pts[key]
    #             _, x, y = p.point.tolist()
    #             base_pts.append((x, y))
    #         logger.info('Setting+Saving Reference manual points: %s' % str(ref_pts))
    #         logger.info('Setting+Saving Working manual points: %s' % str(base_pts))
    #         cfg.data.set_manpoints('ref', ref_pts)
    #         cfg.data.set_manpoints('base', base_pts)
    #         cfg.data.print_all_match_points()
    #         # cfg.main_window._saveProjectToFile(silently=True)
    #         # cfg.main_window.hud.post('Match Points Saved!')

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
        self.ngVertLab.setText('Manual Alignment Mode')
        # self.ngVertLab.setStyleSheet("""background-color: #222222 ; color: #ffe135;""")
        self.bookmark_tab = self._tabs.currentIndex()
        self._tabs.setCurrentIndex(0)
        self.hideSecondaryNgTools()
        self.w_ng_display.hide()  # change layout before initializing viewer
        self.MA_splitter.show()  # change layout before initializing viewer
        self.update()
        self.initNeuroglancer()

    # def onExitManualMode(self):
    #     self.MA_ptsListWidget_ref.clear()
    #     self.MA_ptsListWidget_base.clear()
    #     self._tabs.setCurrentIndex(self.bookmark_tab)
    #     self.MA_splitter.hide()
    #     self.w_ng_display.show()
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

    def disableZoomSlider(self):
        self._allow_zoom_change = False

    def enableZoomSlider(self):
        self._allow_zoom_change = True

    def setZoomSlider(self):
        logger.info('')
        # logger.critical(f'Setting Zoom to {cfg.emViewer.zoom() / 1}...')
        if self._allow_zoom_change:
            # caller = inspect.stack()[1].function
            zoom = cfg.emViewer.zoom()
            # logger.critical('Setting slider value (zoom: %g, caller: %s)' % (zoom, caller))
            self.zoomSlider.setValue(1 / zoom)
            self._allow_zoom_change = True

    def onZoomSlider(self):
        caller = inspect.stack()[1].function
        # curframe = inspect.currentframe()
        # calframe = inspect.getouterframes(curframe, 2)
        # calname = str(calframe[1][3])
        # logger.critical('caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
        # logger.critical('caller: %s, self._allow_zoom_change = %r' %(caller, self._allow_zoom_change))

        # if self._allow_zoom_change:
        #     self._allow_zoom_change = False

        if caller not in ('slotUpdateZoomSlider', 'setValue'):  # Original #0314
            # logger.critical('caller: %s' % caller)

            if getData('state,manual_mode'):
                val = 1 / self.zoomSlider.value()
                # state = copy.deepcopy(cfg.refViewer.state)
                # state.cross_section_scale = 1 / val
                # state.cross_section_scale = val * val
                # state.cross_section_scale = 1 / (val * val)
                # cfg.refViewer.set_state(state)
                if abs(cfg.emViewer.state.cross_section_scale - val) > .0001:
                    # logger.info('Setting Neuroglancer Zoom to %g...' %val)
                    cfg.refViewer.set_zoom(val)
                    cfg.baseViewer.set_zoom(val)

                # cfg.stageViewer._set_zmag()
                # cfg.refViewer._set_zmag()
                # cfg.baseViewer._set_zmag()
            else:
                try:
                    val = 1 / self.zoomSlider.value()
                    # logger.critical('cfg.emViewer.state.cross_section_scale - val = %s' %str(diff))
                    # state = copy.deepcopy(cfg.emViewer.state)
                    # state.cross_section_scale = 1 / val
                    # state.cross_section_scale = val * val
                    # state.cross_section_scale = 1 / (val * val)
                    # cfg.emViewer.set_state(state)
                    if abs(cfg.emViewer.state.cross_section_scale - val) > .0001:
                        # logger.info('Setting Neuroglancer Zoom to %g...' % val)
                        cfg.emViewer.set_zoom(val)
                except:
                    print_exception()
            # logger.critical('val = %s' %str(val))
            # logger.critical('1 / (val * val) = %s' %str(1 / (val * val)))
            # self._allow_zoom_change = True

    def slotUpdateZoomSlider(self):
        # Lets only care about REF <--> slider
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if getData('state,manual_mode'):
                val = cfg.refViewer.state.cross_section_scale
            else:
                val = cfg.emViewer.state.cross_section_scale
            if val:
                if val != 0:
                    # new_val = float(sqrt(val))
                    new_val = float(val * val)
                    logger.info('new_val = %s' % str(new_val))
                    self.zoomSlider.setValue(new_val)
        except:
            print_exception()

    def setZmag(self, val):
        logger.info(f'zpos={cfg.data.zpos} Setting Z-mag to {val}...')
        try:
            state = copy.deepcopy(cfg.emViewer.state)
            state.relative_display_scales = {'z': val}
            cfg.emViewer.set_state(state)
            cfg.main_window.update()
        except:
            print_exception()

    def onSliderZmag(self):
        caller = inspect.stack()[1].function
        logger.info('caller: %s' % caller)
        try:
            # for viewer in cfg.main_window.get_viewers():
            val = self.ZdisplaySlider.value()
            if getData('state,manual_mode'):
                state = copy.deepcopy(cfg.refViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.refViewer.set_state(state)
                state = copy.deepcopy(cfg.baseViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.baseViewer.set_state(state)
                state = copy.deepcopy(cfg.stageViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.baseViewer.set_state(state)

            else:
                # logger.info('val = %d' % val)
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
            if cfg.data['state']['mode'] == 'comparison':
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
        self.label_overview.setStyleSheet("""
        background-color: #161c20;
        color: #ede9e8;""")
        hbl = HBL()
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.table_container = QWidget()
        self.table_container.setObjectName('table_container')
        self.table_container.setLayout(hbl)

    def updateTreeWidget(self):
        # time consuming - refactor?
        logger.info('Updating project raw data tree...')
        self.treeview_model.load(cfg.data.to_dict())
        self.treeview.setModel(self.treeview_model)
        self.treeview.header().resizeSection(0, 380)
        # self.treeview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.treeview.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.treeview.expandAll()
        self.treeview.update()
        self.repaint()

    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self.treeview = QTreeView()
        self.treeview.setAnimated(True)
        self.treeview.setIndentation(20)
        # self.treeview.header().resizeSection(0, 380)
        # self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.treeview_model = JsonModel()
        self.treeview_model.signals.dataModelChanged.connect(self.load_data_from_treeview)
        self.treeview.setModel(self.treeview_model)
        self.treeview.setAlternatingRowColors(True)
        self._wdg_treeview = QWidget()
        self._wdg_treeview.setContentsMargins(0, 0, 0, 0)
        # self._wdg_treeview.setObjectName('_wdg_treeview')
        self.btnCollapseAll = QPushButton('Collapse All')
        self.btnCollapseAll.setToolTip('Collapse all tree nodes')
        self.btnCollapseAll.setStyleSheet('font-size: 10px;')
        self.btnCollapseAll.setFixedSize(80, 18)
        self.btnCollapseAll.clicked.connect(self.treeview.collapseAll)
        self.btnExpandAll = QPushButton('Expand All')
        self.btnExpandAll.setToolTip('Expand all tree nodes')
        self.btnExpandAll.setStyleSheet('font-size: 10px;')
        self.btnExpandAll.setFixedSize(80, 18)
        self.btnExpandAll.clicked.connect(self.treeview.expandAll)
        self.btnCurSection = QPushButton('Current Section')

        def fn():
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()

        self.btnCurSection.setToolTip('Jump to the data for current section and scale')
        self.btnCurSection.setStyleSheet('font-size: 10px;')
        self.btnCurSection.setFixedSize(80, 18)
        self.btnCurSection.clicked.connect(fn)

        def fn():
            self.updateTreeWidget()
            self.treeview.collapseAll()

        self.btnReloadDataTree = QPushButton('Reload')
        self.btnReloadDataTree.setToolTip('Jump to the data for current section and scale')
        self.btnReloadDataTree.setStyleSheet('font-size: 10px;')
        self.btnReloadDataTree.setFixedSize(80, 18)
        self.btnReloadDataTree.clicked.connect(fn)

        def goToData():
            logger.info('')
            if self.le_tree_jumpToSec.text():
                section = int(self.le_tree_jumpToSec.text())
            else:
                section = cfg.data.zpos
            if (len(self.le_tree_jumpToScale.text()) > 0) and \
                    (int(self.le_tree_jumpToScale.text()) in cfg.data.scale_vals()):
                scale = get_scale_key(int(self.le_tree_jumpToScale.text()))
            else:
                scale = cfg.data.scale
            self.updateTreeWidget()

            keys = ['data', 'scales', scale, 'stack', section]

            opt = self.combo_data_tree.currentText()
            logger.info(f'opt = {opt}')
            if opt:
                try:
                    if opt == 'Section':
                        pass
                    elif opt == 'Results':
                        keys.extend(['alignment', 'method_results'])
                    elif opt == 'Alignment History':
                        keys.extend(['alignment_history'])
                    elif opt == 'Method Results':
                        keys.extend(['alignment', 'method_results'])
                    # elif opt == 'Ingredient 0':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_0'])
                    # elif opt == 'Ingredient 1':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_1'])
                    # elif opt == 'Ingredient 2':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_2'])
                    elif opt == 'SWIM Settings':
                        keys.extend(['alignment', 'swim_settings'])
                    # elif opt == 'SWIM Out':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_2', 'swim_out'])
                    # elif opt == 'SWIM Err':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_2', 'swim_err'])
                    # elif opt == 'SWIM Arguments':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_2', 'swim_args'])
                    # elif opt == 'MIR Err':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_2', 'mir_err_lines'])
                    # elif opt == 'MIR Out':
                    #     keys.extend(['alignment', 'method_results', 'ingredient_2', 'mir_out_lines'])

                    logger.info(f'keys = {keys}')
                except:
                    print_exception()
                else:
                    self.treeview_model.jumpToKey(keys=keys)

        self.le_tree_jumpToScale = QLineEdit()
        self.le_tree_jumpToScale.setFixedHeight(18)
        self.le_tree_jumpToScale.setFixedWidth(30)
        # def fn():
        #     requested = int(self.le_tree_jumpToScale.text())
        #     if requested in cfg.data.scale_vals():
        #         self.updateTreeWidget()
        #         self.treeview_model.jumpToScale(s=get_scale_key(requested))
        self.le_tree_jumpToScale.returnPressed.connect(goToData)

        self.le_tree_jumpToSec = QLineEdit()
        self.le_tree_jumpToSec.setFixedHeight(18)
        self.le_tree_jumpToSec.setFixedWidth(30)
        # def fn():
        #     logger.info('')
        #     requested = int(self.le_tree_jumpToSec.text())
        #     if (len(self.le_tree_jumpToScale.text()) > 0) and \
        #             (int(self.le_tree_jumpToScale.text()) in cfg.data.scale_vals()):
        #         requested_scale = int(self.le_tree_jumpToScale.text())
        #     else:
        #         requested_scale = cfg.data.scale
        #     self.updateTreeWidget()
        #     self.treeview_model.jumpToSection(sec=requested, s=get_scale_key(requested_scale))
        self.le_tree_jumpToSec.returnPressed.connect(goToData)

        self.combo_data_tree = QComboBox()
        self.combo_data_tree.setFixedWidth(120)
        # items = ['--', 'Results', 'SWIM Arguments', 'SWIM Out', 'SWIM Err', 'SWIM Settings', 'MIR Arguments', 'MIR Tokens',
        #          'Alignment History']
        # items = ['--', 'Results', 'Alignment History', 'Method Results', 'SWIM Settings', 'SWIM Out',
        #          'SWIM Err', 'SWIM Arguments', 'MIR Err', 'MIR Out']
        items = ['--', 'Results', 'Alignment History', 'Method Results', 'SWIM Settings']
        self.combo_data_tree.addItems(items)

        self.btn_tree_go = QPushButton('Go')
        self.btn_tree_go.clicked.connect(goToData)
        self.btn_tree_go.setFixedSize(28, 18)

        self.treeHbl = QHBoxLayout()
        self.treeHbl.setContentsMargins(0, 0, 0, 0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setStyleSheet("""
        background-color: #161c20;
        color: #ede9e8;""")
        self.treeHbl.addWidget(lab)

        spcr = QWidget()
        spcr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.jumpToTreeLab = QLabel('Jump To: ')
        self.jumpToTreeLab.setAlignment(Qt.AlignRight)
        self.jumpToTreeLab.setFixedHeight(18)
        # self.jumpToTreeLab.setStyleSheet('color: #141414; font-weight: 600; border: 1px solid #dadada;')
        self.jumpToTreeLab.setStyleSheet('color: #141414; font-weight: 600; font-size: 10px;')

        hbl = HBL()
        hbl.setSpacing(4)
        hbl.addWidget(self.btnReloadDataTree)
        hbl.addWidget(self.btnCollapseAll)
        hbl.addWidget(self.btnExpandAll)
        hbl.addWidget(ExpandingWidget(self))
        hbl.addWidget(self.jumpToTreeLab)
        hbl.addWidget(QLabel(' Scale:'))
        hbl.addWidget(self.le_tree_jumpToScale)
        hbl.addWidget(QLabel(' Section:'))
        hbl.addWidget(self.le_tree_jumpToSec)
        hbl.addWidget(self.combo_data_tree)
        hbl.addWidget(self.btn_tree_go)
        hbl.addWidget(self.btnCurSection)
        # hbl.addWidget(spcr)
        btns = QWidget()
        btns.setContentsMargins(2, 2, 2, 2)
        btns.setFixedHeight(24)
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
        # self.lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#ede9e8', font_size=14)
        self.lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#ede9e8', font_size=14)
        self.lab_yaxis.setMaximumWidth(20)
        hbl = HBL()
        hbl.addWidget(self.lab_yaxis)
        hbl.addWidget(self.snr_plot)
        self._plot_Xaxis = QLabel('Serial Section #')
        self._plot_Xaxis.setMaximumHeight(20)
        # self._plot_Xaxis.setStyleSheet('color: #ede9e8; font-size: 14px;')
        self._plot_Xaxis.setStyleSheet('color: #ede9e8; font-size: 14px;')
        self._plot_Xaxis.setContentsMargins(0, 0, 0, 8)
        self._plot_Xaxis.setFont(font)
        vbl = VBL()
        vbl.addLayout(hbl)
        vbl.addWidget(self._plot_Xaxis, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.snr_plt_wid = QWidget()
        self.snr_plt_wid.setLayout(vbl)
        self.snr_plt_wid.setStyleSheet('background-color: #222222; font-weight: 550;')
        self._thumbnail_src = QLabel()
        self._thumbnail_aligned = QLabel()
        self.snrWebengine = WebEngine(ID='snr')
        setWebengineProperties(self.snrWebengine)
        # self.snrWebengine.setMinimumWidth(140)
        self.snrWebengine.setMinimumWidth(140)
        self.snrPlotSplitter = QSplitter(Qt.Orientation.Horizontal)
        self.snrPlotSplitter.setStyleSheet('background-color: #222222;')
        self.snrPlotSplitter.addWidget(self.snr_plt_wid)
        self.snrPlotSplitter.addWidget(self.snrWebengine)

    def initUI_tab_widget(self):
        '''Tab Widget'''
        logger.info('')
        self._tabs = QTabWidget()
        self._tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tabs.setStyleSheet("""
        QTabBar::tab {
            height: 12px;
            width: 100px;
            font-size: 9px;
            font-weight: 600;

            border: 1px solid #ede9e8;
            background-color: #dadada;

        }
        QTabBar::tab:selected
        {
            font-weight: 600;
            color: #f3f6fb;
            background-color: #222222;
        }
        """)
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setObjectName('project_tabs')
        self._tabs.addTab(self.ng_browser_container_outer, ' 3DEM ')
        self._tabs.addTab(self.table_container, ' Table ')
        self._tabs.addTab(self._wdg_treeview, ' Raw Data ')
        self._tabs.addTab(self.snrPlotSplitter, ' SNR Plot ')
        self._tabs.setTabToolTip(0, '3D Data Visualization')
        self._tabs.setTabToolTip(1, 'Project Data Table View')
        self._tabs.setTabToolTip(2, 'Project Data Tree View')
        self._tabs.setTabToolTip(3, 'SNR Plot')

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

    def initShader(self):

        # def fn():
        #     logger.info('')
        #     cfg.data.brightness = float(self.brightnessLE.text())
        #     cfg.data.contrast = float(self.contrastLE.text())
        #     cfg.project_tab.initNeuroglancer()
        #     cfg.main_window._callbk_unsavedChanges()
        # self._btn_applyShader = QPushButton('Apply')
        # self._btn_applyShader.setFixedSize(QSize(64,20))
        # self._btn_applyShader.clicked.connect(fn)

        def resetBrightessAndContrast():
            reset_val = 0.0
            cfg.data.brightness = reset_val
            cfg.data.contrast = reset_val
            self.brightnessSlider.setValue(int(cfg.data.brightness))
            self.contrastSlider.setValue(int(cfg.data.contrast))
            for viewer in self.get_viewers():
                viewer.set_brightness()
                viewer.set_contrast()

            # cfg.project_tab.initNeuroglancer()

        self._btn_resetBrightnessAndContrast = QPushButton('Reset')
        self._btn_resetBrightnessAndContrast.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self._btn_resetBrightnessAndContrast.setFixedSize(QSize(40, 18))
        self._btn_resetBrightnessAndContrast.clicked.connect(resetBrightessAndContrast)

        # self._btn_volumeRendering = QPushButton('Volume')
        # self._btn_volumeRendering.setFixedSize(QSize(58,20))
        # self._btn_volumeRendering.clicked.connect(self.fn_volume_rendering)
        # self.shaderSideButtons = HWidget(self._btn_resetBrightnessAndContrast, self._btn_volumeRendering)
        self.shaderSideButtons = HWidget(self._btn_resetBrightnessAndContrast)
        self.shaderWidget = QWidget()

        self.brightnessLE = QLineEdit()
        self.brightnessLE.setStyleSheet("""QLineEdit {
        color: #141414;
        background: #dadada;
        }""")
        self.brightnessLE.setText('0.00')
        self.brightnessLE.setValidator(QDoubleValidator(-1, 1, 2))
        self.brightnessLE.setFixedWidth(50)
        self.brightnessLE.setFixedHeight(16)
        self.brightnessLE.textChanged.connect(
            lambda: self.brightnessSlider.setValue(float(self.brightnessLE.text())))
        self.brightnessLE.textChanged.connect(self.fn_brightness_control)
        self.brightnessSlider = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.brightnessSlider.setFixedWidth(200)
        self.brightnessSlider.setMouseTracking(False)
        self.brightnessSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.brightnessSlider.setMinimum(-1.0)
        self.brightnessSlider.setMaximum(1.0)
        self.brightnessSlider.setValue(0)
        self.brightnessSlider.valueChanged.connect(self.fn_brightness_control)
        self.brightnessSlider.valueChanged.connect(cfg.main_window._callbk_unsavedChanges)
        self.brightnessSlider.valueChanged.connect(
            lambda: self.brightnessLE.setText('%.2f' % self.brightnessSlider.value()))

        self.brightnessWidget = HWidget(QLabel('Brightness:'), self.brightnessSlider, self.brightnessLE)

        self.contrastLE = QLineEdit()
        self.contrastLE.setStyleSheet("""QLineEdit {
        color: #141414;
        background: #dadada;
        }""")
        self.contrastLE.setText('0.00')
        self.contrastLE.setValidator(QDoubleValidator(-1, 1, 2))
        self.contrastLE.setFixedWidth(50)
        self.contrastLE.setFixedHeight(16)
        self.contrastLE.textChanged.connect(
            lambda: self.contrastSlider.setValue(float(self.contrastLE.text())))
        self.contrastLE.textChanged.connect(self.fn_contrast_control)
        self.contrastSlider = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.contrastSlider.setFixedWidth(200)
        self.contrastSlider.setMouseTracking(False)
        self.contrastSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.contrastSlider.setMinimum(-1.0)
        self.contrastSlider.setMaximum(1.0)
        self.contrastSlider.setValue(0)
        # self.contrastSlider.setSingleStep(.02)
        # self.contrastSlider.setSingleStep(0.01)
        self.contrastSlider.valueChanged.connect(self.fn_contrast_control)
        self.contrastSlider.valueChanged.connect(cfg.main_window._callbk_unsavedChanges)
        self.contrastSlider.valueChanged.connect(
            lambda: self.contrastLE.setText('%.2f' % self.contrastSlider.value()))

        self.contrastWidget = HWidget(QLabel('Contrast:'), self.contrastSlider, self.contrastLE)

        self.bcWidget = HWidget(self.brightnessWidget, ExpandingWidget(self), self.contrastWidget)

        self.shaderToolbar = QToolBar()
        self.shaderToolbar.setFixedHeight(20)
        # self.shaderToolbar.setStyleSheet("""
        # QToolBar {
        # background-color: #222222;
        # color: #f3f6fb;
        # border-top-width: 1px;
        # border-bottom-width: 1px;
        # border-color: #339933;
        # border-style: solid;
        # }
        # QLabel { color: #f3f6fb; }
        # """)
        self.shaderToolbar.setStyleSheet("""background-color: #222222; color: #f3f6fb;""")
        self.shaderToolbar.addWidget(QLabel('<b>Shader:&nbsp;&nbsp;&nbsp;&nbsp;</b>'))
        self.shaderToolbar.addWidget(self.bcWidget)
        self.shaderToolbar.addWidget(self.shaderSideButtons)
        self.shaderToolbar.addWidget(ExpandingWidget(self))
        self.shaderToolbar.hide()

        # self.shaderWidget = HWidget(self.bcWidget, self.shaderSideButtons)
        # self.shaderWidget.hide()

    def fn_brightness_control(self):
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' %caller)
        if caller == 'main':
            cfg.data.brightness = self.brightnessSlider.value()
            for viewer in self.get_viewers():
                viewer.set_brightness()

    def fn_contrast_control(self):
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' % caller)
        if caller == 'main':
            cfg.data.contrast = self.contrastSlider.value()
            for viewer in self.get_viewers():
                viewer.set_contrast()

    # def fn_shader_control(self):
    #     logger.info('')
    #     logger.info(f'range: {self.normalizedSlider.getRange()}')
    #     cfg.data.set_normalize(self.normalizedSlider.getRange())
    #     state = copy.deepcopy(cfg.emViewer.state)
    #     for layer in state.layers:
    #         layer.shaderControls['normalized'].range = np.array(cfg.data.normalize())
    #     # state.layers[0].shader_controls['normalized'] = {'range': np.array([20,50])}
    #     cfg.emViewer.set_state(state)

    def fn_volume_rendering(self):
        logger.info('')
        state = copy.deepcopy(cfg.emViewer.state)
        state.showSlices = False
        cfg.emViewer.set_state(state)

    def focusedViewerChanged(self, focused: str):
        logger.critical(f'focused: {focused}')

        if self.focusedViewer == 'ref':
            pass
        elif self.focusedViewer == 'base':
            pass

    def get_viewers(self):
        caller = inspect.stack()[1].function
        # logger.info(f'get_viewers [caller: {caller}] >>>>')
        viewers = []
        if getData('state,manual_mode'):
            viewers.extend([cfg.baseViewer, cfg.refViewer, cfg.stageViewer])
            # viewers.extend([cfg.baseViewer, cfg.refViewer])
            # return [cfg.project_tab.MA_viewer_base, cfg.project_tab.MA_viewer_ref]
        tab = self._tabs.currentIndex()
        if tab == 0:
            if not getData('state,manual_mode'):
                viewers.extend([cfg.emViewer])
        elif tab == 3:
            viewers.extend([cfg.snrViewer])

        # logger.info(f'<<<< get_viewers')
        return viewers

    def paintEvent(self, pe):
        '''Enables widget to be style-ized'''
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        s = self.style()
        s.drawPrimitive(QStyle.PE_Widget, opt, p, self)

    # def sizeHint(self):
    #     return QSize(1000,1000)


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
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter
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


class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


class WebEngine(QWebEngineView):

    def __init__(self, ID='webengine'):
        QWebEngineView.__init__(self)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)
        # self.inFocus = Signal(str)
        # self.installEventFilter(self)

    # def eventFilter(self, object, event):
    #     if event.type() == QEvent.Enter:
    #         # self.inFocus.emit(self.ID)
    #         logger.info(f"Entering Focus of ({self.ID})")
    #         # self.stop = True
    #         # print('program stop is', self.stop)
    #         # return True
    #     elif event.type() == QEvent.Leave:
    #         logger.info(f"Leaving Focus of ({self.ID})")
    #         # self.stop = False
    #         # print('program stop is', self.stop)
    #     return True


class Rect(QWidget):
    clicked = Signal()

    def __init__(self, ID):
        super().__init__()
        self.ID = ID
        # self.setGeometry(30,30,600,400)
        self.begin = QPoint()
        self.end = QPoint()
        self.show()

    def paintEvent(self, event):
        qp = QPainter(self)
        br = QBrush(QColor(100, 10, 10, 40))
        qp.setBrush(br)
        qp.drawRect(QRect(self.begin, self.end))

    def mousePressEvent(self, event):
        self.clicked.emit()
        logger.critical(f'Rect {self.ID} clicked!')
        self.begin = event.pos()
        self.end = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.begin = event.pos()
        self.end = event.pos()
        self.update()


class ClickRegion(QLabel):
    clicked = Signal()

    def __init__(self, parent, color, name, **kwargs):
        # super().__init__(parent, **kwargs)
        super().__init__(parent)
        self.name = name
        self.color = color
        if name:
            self.setObjectName(name)
        # self.setStyleSheet('color: #f3f6fb;')
        self.setStyleSheet(f'background-color: {self.color}; border: 2px solid #f3f6fb;')
        self.isClicked = 1

    def mousePressEvent(self, ev):
        self.isClicked = 1 - self.isClicked
        if self.isClicked:
            self.activate()
        else:
            self.inactivate()
        self.clicked.emit()

    def activate(self):
        self.isClicked = 1
        self.setStyleSheet(f'background-color: {self.color}; border: 2px solid #f3f6fb;')

    def inactivate(self):
        self.isClicked = 0
        self.setStyleSheet(f'background-color: #dadada; border: 2px dotted #141414;')

    def setActivated(self, val):
        if val:
            self.activate()
        else:
            self.inactivate()

    # def onClick(self):
    #     logger.info(f'{self.name} was clicked!')
    #     if self.isClicked:
    #         self.setStyleSheet(f'background-color: {self.color};')
    #     else:
    #         self.setStyleSheet(f'background-color: #dadada;')


class ClickLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent, **kwargs):
        # super().__init__(parent, **kwargs)
        super().__init__(parent)
        self.setStyleSheet('color: #f3f6fb;')

    def mousePressEvent(self, ev):
        self.clicked.emit()


class NgClickLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # super().__init__(parent)
        self.setStyleSheet('color: #f3f6fb;')
        # self.isClicked = False
        self.isClicked = False

    def mousePressEvent(self, ev):
        self.isClicked = not self.isClicked
        self.clicked.emit()


class BoldLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet('font-weight: 600;')


def setWebengineProperties(webengine):
    webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)


if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    pt = ProjectTab()
    main_window.setCentralWidget(pt)
    main_window.show()
    sys.exit(app.exec_())