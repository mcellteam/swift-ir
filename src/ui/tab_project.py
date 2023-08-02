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
    QListWidget, QListWidgetItem, QMenu, QMenuBar, QAction, QFormLayout, QGroupBox, QRadioButton, QButtonGroup, QComboBox, \
    QCheckBox, QToolBar, QListView, QDockWidget, QLineEdit, QPlainTextEdit, QDoubleSpinBox, QSpinBox, QButtonGroup, \
    QStackedWidget, QHeaderView, QWidgetAction, QTableWidget, QTableWidgetItem, QAbstractItemView, QSpacerItem, \
    QShortcut, QScrollArea, QMdiSubWindow, QMdiArea, QToolButton
from qtpy.QtCore import Qt, QSize, QRect, QUrl, Signal, Slot, QEvent, QThread, QTimer, QEventLoop, QPoint
from qtpy.QtGui import QPainter, QBrush, QFont, QPixmap, QColor, QCursor, QPalette, QStandardItemModel, \
    QDoubleValidator, QIntValidator, QKeySequence
from qtpy.QtWebEngineWidgets import *
import src.config as cfg
from src.helpers import print_exception, getOpt, setOpt, getData, setData, get_scale_key, natural_sort, hotkey, \
    get_appdir, caller_name, is_tacc, is_joel, make_affine_widget_HTML
from src.viewer_em import EMViewer, EMViewerSnr
from src.viewer_ma import MAViewer
from src.ui.snr_plot import SnrPlot
from src.ui.widget_area import WidgetArea
from src.ui.project_table import ProjectTable
from src.ui.models.json_tree import JsonModel
from src.ui.sliders import DoubleSlider
from src.ui.thumbnail import CorrSignalThumbnail, ThumbnailFast
from src.ui.toggle_switch import ToggleSwitch, AnimatedToggle
from src.ui.process_monitor import HeadupDisplay
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel
from src.ui.joystick import Joystick
from src import DataModel
from collections import OrderedDict

__all__ = ['ProjectTab']

logger = logging.getLogger(__name__)


DEV = is_joel()

class ProjectTab(QWidget):
    loadTable = Signal()

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
        self.webengine.setStyleSheet("background-color: #000000;")
        self.webengine.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.webengine.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.webengine.loadFinished.connect(lambda: print('Web engine load finished!'))
        setWebengineProperties(self.webengine)
        # self.webengine.setStyleSheet('background-color: #222222;')
        self.webengine.setMouseTracking(True)
        self.focusedViewer = None
        # self.setAutoFillBackground(True)
        self.indexConfigure = 0
        self.table_container = QWidget()
        self._wdg_treeview = QWidget()
        self.initShader()
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        self.initTabs()
        self._tabs.currentChanged.connect(self._onTabChange)
        self.manAlignBufferRef = []
        self.manAlignBufferBase = []
        self.mp_colors = cfg.glob_colors
        self._allow_zoom_change = True
        # self.Q1.setAutoFillBackground(True)
        # self.Q2.setAutoFillBackground(True)
        # self.Q3.setAutoFillBackground(True)
        # self.Q4.setAutoFillBackground(True)
        self.oldPos = None
        self.blinkTimer = QTimer(self)
        self.blinkTimer.setInterval(300)
        # self.blinkTimer.timeout.connect(self.onBlinkTimer)
        # self.blinkTimer.timeout.connect(cfg.emViewer.blink)
        self.blinkCur = 0
        self.initNeuroglancer(init_all=True)

    # def display_shortcuts(self):
    #     for action in self.findChildren(QAction) :
    #         print(type(action), action.toolTip(), [x.toString() for x in action.shortcuts()])
    #
    # def initShortcuts(self):
    #     logger.info('')
    #     events = (
    #         (QKeySequence.MoveToPreviousChar, cfg.mw.layer_left),
    #         (QKeySequence.MoveToNextChar, cfg.mw.layer_right),
    #         (QKeySequence.MoveToPreviousLine, cfg.mw.incrementZoomIn),
    #         (QKeySequence.MoveToNextLine, cfg.mw.incrementZoomOut),
    #         (QKeySequence("Ctrl+M"), cfg.mw.enterExitManAlignMode),
    #         # (QKeySequence.MoveToPreviousChar, self.scale_down),
    #         # (QKeySequence.MoveToNextChar, self.scale_up),
    #         # (Qt.Key_K, self._callbk_skipChanged),
    #         # (Qt.Key_N, self._callbk_showHideNotes)
    #     )
    #     for event, action in events:
    #         QShortcut(event, self, action)


    def load_data_from_treeview(self):
        self.datamodel = DataModel(self.treeview_model.to_json())
        cfg.data = self.datamodel

    def _onTabChange(self):
        index = self._tabs.currentIndex()
        logger.info(f'Tab changed {index}')
        # QApplication.restoreOverrideCursor()

        cfg.data['state']['current_tab'] = index

        if index == 0:
            # cfg.emViewer.set_layer(cfg.data.zpos)
            # self.initNeuroglancer()
            pass
        elif index == 1:
            # pts_ref = cfg.refViewer.pts
            # pts_base = cfg.baseViewer.pts
            # # self.shutdownNeuroglancer()
            # self.initNeuroglancer()
            # cfg.refViewer.pts = pts_ref
            # cfg.baseViewer.pts = pts_base
            self.initNeuroglancer()
            self.updateLowest8widget()
            self.updateDetailsPanel()
            self.updateTimingsWidget()
            self.update_MA_list_widgets() #0726+

        elif index == 2:
            self.project_table.table.selectRow(cfg.data.zpos)
        elif index == 3:

            self.updateTreeWidget()
            # self.treeview_model.jumpToLayer()
        elif index == 4:
            # self.snr_plot.data = copy.deepcopy(cfg.data)
            self.snr_plot.initSnrPlot()

        cfg.mw.dataUpdateWidgets()

    # def refreshTab(self, index=None):
    def refreshTab(self):
        logger.info('')
        if DEV:
            logger.critical(f'[{caller_name()}]')

        index = self._tabs.currentIndex()

        self.datamodel['state']['blink'] = False
        self.blinkTimer.stop()
        self.tbbBlinkToggle.setIcon(qta.icon('mdi.toggle-switch-off-outline', color='#f3f6fb'))
        self.tbbBlinkToggle.setChecked(False)

        if index == 0:
            # layout = cfg.emViewer.state.layout.type

            self.shutdownNeuroglancer()
            self.initNeuroglancer()

            # if getData('state,ng_layout') == 'xy':
            #     cfg.emViewer.initZoom(self.webengine.width() / 500000000, self.webengine.height() / 500000000)

        elif index == 1:
            # pts_ref = cfg.refViewer.pts
            # pts_base = cfg.baseViewer.pts
            self.shutdownNeuroglancer()
            self.initNeuroglancer()
            # cfg.refViewer.pts = pts_ref
            # cfg.baseViewer.pts = pts_base
            # cfg.mw.setTargKargPixmaps()
            # cfg.mw.updateCorrSignalsDrawer()
        elif index == 2:
            self.project_table.initTableData()
        elif index == 3:
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()
        elif index == 4:
            # self.snr_plot.data = copy.deepcopy(cfg.data)
            self.snr_plot.initSnrPlot()

        if cfg.mw.dw_snr.isVisible():
            self.dSnr_plot.initSnrPlot()

        cfg.mw.dataUpdateWidgets() #Todo might be redundant thumbail redraws
        QApplication.processEvents()


    def shutdownNeuroglancer(self):
        logger.info('')
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if ng.is_server_running():
            ng.server.stop()
            # time.sleep(.5)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)

    def initNeuroglancer(self, init_all=False):
        caller = inspect.stack()[1].function
        if cfg.mw._is_initialized == 0:
            logger.info(f"[{caller}] UNABLE TO INITIALIZE NEUROGLANCER AT THIS TIME")
            return

        if cfg.mw._working:
            logger.info(f"[{caller}] UNABLE TO INITIALIZE NEUROGLANCER AT THIS TIME... BUSY WORKING!")
            return

        # logger.info('')
        # QApplication.processEvents()
        # cfg.mw.tell('Initializing Neuroglancer')
        cfg.mw.set_status('Initializing Neuroglancer...')
        if DEV:
            logger.critical(f"[DEV][{caller_name()}] Initializing Neuroglancer...")
        if cfg.data['state']['current_tab'] == 1 or init_all:
            # self.MA_webengine_ref.setUrl(QUrl("http://localhost:8888/"))
            # self.MA_webengine_base.setUrl(QUrl("http://localhost:8888/"))
            self.refViewer = cfg.refViewer = MAViewer(role='ref', webengine=self.MA_webengine_ref)
            self.baseViewer = cfg.baseViewer = MAViewer(role='base', webengine=self.MA_webengine_base)

            # cfg.main_window.swimWindowChanged.connect(cfg.refViewer.drawSWIMwindow)
            # cfg.main_window.swimWindowChanged.connect(cfg.baseViewer.drawSWIMwindow)

            cfg.baseViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)  # 0314
            cfg.refViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider) #0314

            cfg.refViewer.signals.ptsChanged.connect(self.update_MA_list_widgets)
            cfg.refViewer.signals.ptsChanged.connect(cfg.refViewer.drawSWIMwindow)
            cfg.refViewer.signals.ptsChanged.connect(lambda: print('\n\n Ref Viewer pts changed!\n\n'))

            cfg.baseViewer.signals.ptsChanged.connect(self.update_MA_list_widgets)
            cfg.baseViewer.signals.ptsChanged.connect(cfg.baseViewer.drawSWIMwindow)
            cfg.baseViewer.signals.ptsChanged.connect(lambda: print('\n\n Base Viewer pts changed!\n\n'))
            # cfg.refViewer.signals.stateChangedAny.connect(self.update_MA_base_state)
            # cfg.baseViewer.signals.stateChangedAny.connect(self.update_MA_ref_state)

            # cfg.baseViewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))

            # cfg.refViewer.signals.stateChanged.connect(cfg.baseViewer.set_layer)
            # cfg.baseViewer.signals.stateChanged.connect(cfg.refViewer.set_layer)

            # cfg.refViewer.signals.stateChangedAny.connect(lambda: self.rb_transforming.setChecked(True))

            # cfg.refViewer.signals.stateChanged.connect(cfg.main_window.dataUpdateWidgets)
            cfg.baseViewer.signals.zposChanged.connect(cfg.main_window.dataUpdateWidgets)
            cfg.baseViewer.signals.zposChanged.connect(lambda: cfg.mw.setZpos(on_state_change=True))

            cfg.refViewer.signals.zposChanged.connect(self.set_transforming)

            # cfg.baseViewer.signals.zposChanged.connect(cfg.baseViewer))

            # cfg.mw.zposChanged.connect(cfg.refViewer.set_layer)
            # cfg.mw.zposChanged.connect(cfg.baseViewer.set_layer)

            # cfg.refViewer.signals.stateChanged.connect(lambda: logger.critical(f'Signal Emitted! {self.sender()}'))
            # cfg.baseViewer.signals.stateChanged.connect(lambda: logger.critical(f'Signal Emitted! {self.sender()}'))

            # cfg.baseViewer.shared_state.add_changed_callback(cfg.emViewer.set_zmag)
            # cfg.baseViewer.signals.zoomChanged.connect(self.setZoomSlider) # Not responsible #WasOn
            
            cfg.baseViewer.signals.swimAction.connect(cfg.main_window.alignOne)
            cfg.refViewer.signals.swimAction.connect(cfg.main_window.alignOne)

            self.update_MA_list_widgets()
            self.dataUpdateMA()

            # self.MA_webengine_ref.reload()
            # self.MA_webengine_base.reload()

        if cfg.data['state']['current_tab'] == 0 or init_all:
            self.viewer = cfg.emViewer = EMViewer(webengine=self.webengine)
            self.viewer.initZoom(self.webengine.width(), self.webengine.height())
            cfg.emViewer.signals.zposChanged.connect(cfg.main_window.dataUpdateWidgets)
            cfg.emViewer.signals.layoutChanged.connect(self.slot_layout_changed)
            cfg.emViewer.signals.zoomChanged.connect(self.slot_zoom_changed)
            # cfg.emViewer.signals.zoomChanged.connect(self.setZoomSlider)

            # self.zoomSlider.sliderMoved.connect(self.onZoomSlider)  # Original #0314
            # self.zoomSlider.valueChanged.connect(self.onZoomSlider)
            # self.webengine.reload()
            # QTimer.singleShot(1000, self.webengine.reload)

        cfg.mw.set_status('')
        cfg.mw.hud.done()
        # self.setZmag(10)
        QApplication.processEvents()


    def slot_layout_changed(self):
        rev_mapping = {'yz':'xy', 'xy':'yz', 'xz':'xz', 'yz-3d':'xy-3d','xy-3d':'yz-3d',
                   'xz-3d':'xz-3d', '4panel': '4panel', '3d': '3d'}
        requested = rev_mapping[self.viewer.state.layout.type]
        if DEV:
            logger.critical(f"Layout changed! requested: {requested}")
        setData('state,ng_layout', requested)
        self.comboNgLayout.setCurrentText(requested)
        # if getData('state,ng_layout') == 'xy':
        #     # cfg.emViewer.initZoom(self.webengine.width() / 500000000, self.webengine.height() / 500000000)
        #     cfg.emViewer.initZoom(self.webengine.width(), self.webengine.height())
        cfg.mw.tell(f'Neuroglancer Layout (set from native NG controls): {requested}')

    def slot_zoom_changed(self, val):
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' % caller)
        if val > 1000:
            val *= 250000000
        if DEV:
            logger.info(f"[DEV] Zoom changed! passed value: {val:.3f}")
        setData('state,ng_zoom', val)
        self.le_zoom.setText("%.2f" % val)
        # setData('state,ng_zoom', self.viewer.state.cross_section_scale)
        # self.le_zoom.setText(str(self.viewer.state.cross_section_scale))




    # def delayInitNeuroglancer(self, ms=1000):
    #     QTimer.singleShot(ms, self.initNeuroglancer)

        # self.updateProjectLabels()

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

    # def get_layout(self, requested=None):
    #     if requested == None:
    #         requested = cfg.data['ui']['ng_layout']
    #     mapping = {'xy': 'yz', 'yz': 'xy', 'xz': 'xz', 'xy-3d': 'yz-3d', 'yz-3d': 'xy-3d',
    #                'xz-3d': 'xz-3d', '4panel': '4panel', '3d': '3d'}
    #     return mapping[requested]

    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')

        self._overlayLab = QLabel('<label>')
        # self._overlayLab.setMaximumHeight(20)
        self._overlayLab.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._overlayLab.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayLab.setAlignment(Qt.AlignCenter)
        self._overlayLab.setStyleSheet("""color: #FF0000; font-size: 16px; font-weight: 600; background-color: rgba(0, 0, 0, 0.5); """)
        self._overlayLab.hide()

        # self.hud_overlay = HeadupDisplay(cfg.main_window.app, overlay=True)
        # self.hud_overlay.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        # self.hud_overlay.set_theme_overlay()

        # self.joystick = Joystick()

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

        self.detailsSNR = QLabel()
        self.detailsSNR.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSNR.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSNR.setMaximumHeight(100)
        self.detailsSNR.setWordWrap(True)
        self.detailsSNR.setStyleSheet(style)
        self.detailsSNR.hide()

        self.zoomSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.zoomSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.zoomSlider.setMouseTracking(True)
        # self.zoomSlider.setInvertedAppearance(True)
        self.zoomSlider.setMaximum(4)
        # self.zoomSlider.setMinimum(0.1)
        # self.zoomSlider.setMinimum(0.02)
        # self.zoomSlider.setMinimum(0)
        self.zoomSlider.setMinimum(1)

        # self.zoomSlider.sliderMoved.connect(self.onZoomSlider) #Original #0314
        self.zoomSlider.valueChanged.connect(self.onZoomSlider)
        self.zoomSlider.setValue(4.0)

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
        self.ZdisplaySlider.setValue(1.0)
        self.ZdisplaySlider.valueChanged.connect(self.onSliderZmag)

        self.ZdisplaySliderAndLabel = VWidget()
        self.ZdisplaySliderAndLabel.layout.setSpacing(0)
        self.ZdisplaySliderAndLabel.setFixedWidth(16)
        self.ZdisplaySliderAndLabel.setMaximumHeight(100)
        self.ZdisplaySliderAndLabel.addWidget(self.ZdisplaySlider)
        vlab = VerticalLabel('Z-Mag:')
        vlab.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.ZdisplaySliderAndLabel.addWidget(vlab)

        self.MA_webengine_ref = WebEngine(ID='ref')
        self.MA_webengine_ref.setStyleSheet("background-color: #000000;")
        self.MA_webengine_ref.page().setBackgroundColor(Qt.transparent) #0726+
        self.MA_webengine_ref.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.MA_webengine_base = WebEngine(ID='base')
        self.MA_webengine_base.setStyleSheet("background-color: #000000;")
        self.MA_webengine_base.page().setBackgroundColor(Qt.transparent) #0726+
        self.MA_webengine_base.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        setWebengineProperties(self.MA_webengine_ref)
        setWebengineProperties(self.MA_webengine_base)
        # self.MA_webengine_ref.focusInEvent.connect(self.focusedViewerChanged)
        # self.MA_webengine_base.focusInEvent.connect(self.focusedViewerChanged)
        # self.MA_webengine_ref.setMinimumWidth(100)
        # self.MA_webengine_base.setMinimumWidth(100)
        self.MA_webengine_ref.setMouseTracking(True)
        self.MA_webengine_base.setMouseTracking(True)
        # self.MA_webengine_ref.setFocusPolicy(Qt.FocusPolicy.NoFocus) #0726-
        # self.MA_webengine_base.setFocusPolicy(Qt.FocusPolicy.NoFocus) #0726-
        # self.MA_webengine_ref.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        # self.MA_webengine_base.setFocusPolicy(Qt.FocusPolicy.WheelFocus)


        '''Mouse move events will occur only when a mouse button is pressed down, 
        unless mouse tracking has been enabled with setMouseTracking() .'''

        # NO CHANGE----------------------
        # cfg.refViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)
        # cfg.refViewer.signals.ptsChanged.connect(self.update_MA_list_ref)
        # cfg.baseViewer.signals.ptsChanged.connect(self.update_MA_list_base)
        # cfg.refViewer.shared_state.add_changed_callback(self.update_MA_base_state)
        # cfg.baseViewer.shared_state.add_changed_callback(self.update_MA_ref_state)
        # NO CHANGE----------------------

        # MA Stage Buffer Widget

        self.MA_refViewerTitle = QLabel('Reference Section')
        self.MA_refViewerTitle.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.MA_refViewerTitle.setMaximumHeight(14)

        self.MA_baseViewerTitle = QLabel('Transforming Section')
        self.MA_baseViewerTitle.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.MA_baseViewerTitle.setMaximumHeight(14)

        self.MA_ptsListWidget_ref = QListWidget()
        self.MA_ptsListWidget_ref.setMaximumHeight(64)
        self.MA_ptsListWidget_ref.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.MA_ptsListWidget_ref.setSelectionMode(QListWidget.MultiSelection)
        self.MA_ptsListWidget_ref.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.MA_ptsListWidget_ref.installEventFilter(self)

        self.MA_refNextColorTxt = QLabel('Next Color:   ')
        self.MA_refNextColorTxt.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.MA_refNextColorLab = QLabel()
        self.MA_refNextColorLab.setFixedSize(14, 14)

        self.MA_ptsListWidget_base = QListWidget()
        self.MA_ptsListWidget_base.setMaximumHeight(64)
        # self.MA_ptsListWidget_base.setStyleSheet('background-color: #dadada; font-size: 10px;')
        self.MA_ptsListWidget_base.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.MA_ptsListWidget_base.setSelectionMode(QListWidget.MultiSelection)
        self.MA_ptsListWidget_base.setSelectionMode(QListWidget.ExtendedSelection)
        self.MA_ptsListWidget_base.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.MA_ptsListWidget_base.installEventFilter(self)
        self.MA_baseNextColorTxt = QLabel('Next Color:   ')
        self.MA_baseNextColorTxt.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.MA_baseNextColorLab = QLabel()
        self.MA_baseNextColorLab.setFixedSize(14, 14)

        self.MA_ptsListWidget_ref.itemSelectionChanged.connect(self.MA_ptsListWidget_base.selectionModel().clear)
        self.MA_ptsListWidget_base.itemSelectionChanged.connect(self.MA_ptsListWidget_ref.selectionModel().clear)

        self.btn_undoRefPts = QPushButton()
        self.btn_undoRefPts.setFixedSize(QSize(14, 14))
        self.btn_undoRefPts.setIconSize(QSize(13, 13))
        self.btn_undoRefPts.setToolTip('Undo Last Selection')
        self.btn_undoRefPts.setIcon(qta.icon('fa.undo', color='#161c20'))
        def fn():
            if len(cfg.refViewer.pts):
                cfg.refViewer.pts = cfg.refViewer.pts[:-1]
                cfg.refViewer.applyMps()
                cfg.refViewer.drawSWIMwindow()
                self.update_MA_list_widgets()
                self.updateEnabledButtonsMA()
        self.btn_undoRefPts.clicked.connect(fn)

        self.btn_clrRefPts = QPushButton('Clear')
        self.btn_clrRefPts.setToolTip('Clear All Selections')
        self.btn_clrRefPts.setStyleSheet("""font-size: 9px;""")
        self.btn_clrRefPts.setFixedSize(QSize(36, 14))
        self.btn_clrRefPts.clicked.connect(self.deleteAllMpRef)

        self.btn_undoBasePts = QPushButton()
        self.btn_undoBasePts.setFixedSize(QSize(14, 14))
        self.btn_undoBasePts.setIconSize(QSize(13, 13))
        self.btn_undoBasePts.setToolTip('Undo Last Selection')
        self.btn_undoBasePts.setIcon(qta.icon('fa.undo', color='#161c20'))
        def fn():
            if len(cfg.baseViewer.pts):
                cfg.baseViewer.pts = cfg.baseViewer.pts[:-1]
                cfg.baseViewer.applyMps()
                cfg.baseViewer.drawSWIMwindow()
                self.update_MA_list_widgets()
                self.updateEnabledButtonsMA()
        self.btn_undoBasePts.clicked.connect(fn)

        self.btn_clrBasePts = QPushButton('Clear')
        self.btn_clrBasePts.setToolTip('Clear All Selections')
        self.btn_clrBasePts.setStyleSheet("""font-size: 9px;""")
        self.btn_clrBasePts.setFixedSize(QSize(36, 14))
        self.btn_clrBasePts.clicked.connect(self.deleteAllMpBase)

        self.baseNextColorWidget = HWidget(self.MA_baseNextColorTxt, self.MA_baseNextColorLab,
                                           ExpandingWidget(self), self.btn_undoBasePts, self.btn_clrBasePts)
        self.baseNextColorWidget.setFixedHeight(16)
        self.refNextColorWidget = HWidget(self.MA_refNextColorTxt, self.MA_refNextColorLab,
                                          ExpandingWidget(self), self.btn_undoRefPts, self.btn_clrRefPts)
        self.refNextColorWidget.setFixedHeight(16)

        self.automatic_label = QLabel()
        self.automatic_label.setStyleSheet('color: #06470c; font-size: 11px; font-weight: 600;')

        lab = QLabel('Saved Method:')
        lab.setStyleSheet('font-size: 8px;')
        vw = VWidget(lab, self.automatic_label)
        vw.layout.setSpacing(0)

        def fn():
            cfg.data.set_all_methods_automatic()
            # Todo include all of this functionality somewhere
            # cfg.data.set_auto_swim_windows_to_default()
            cfg.main_window.setControlPanelData()
            cfg.mw.setZpos()
            self.dataUpdateMA()
            #     layer['alignment']['swim_settings'].setdefault('iterations', cfg.DEFAULT_SWIM_ITERATIONS)

        self.btnResetAllMA = QPushButton('Set All To Default Grid')
        self.btnResetAllMA.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnResetAllMA.setFixedSize(QSize(140, 18))
        self.btnResetAllMA.clicked.connect(fn)
        self.btnResetAllMA.setStyleSheet('font-size: 10px;')

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
            cfg.main_window.hud('Defaults restored for section %d' % cfg.data.zpos)
            cfg.data.set_auto_swim_windows_to_default(current_only=True)
            cfg.data.set_manual_swim_windows_to_default(current_only=True)

            self.slider_AS_SWIM_window.setValue(int(cfg.data.swim_1x1_custom_px()[0]))
            self.AS_SWIM_window_le.setText(str(cfg.data.swim_1x1_custom_px()[0]))

            self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_custom_px()[0]))
            self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_custom_px()[0]))

            # No GUI control for this, yet
            # self.slider_MA_SWIM_window.setValue(cfg.DEFAULT_MANUAL_SWIM_WINDOW)
            # self.MA_SWIM_window_le.setText(str(cfg.DEFAULT_MANUAL_SWIM_WINDOW))

            self.spinbox_whitening.setValue(float(cfg.data['data']['defaults']['signal-whitening']))
            self.spinbox_swim_iters.setValue(int(cfg.data['data']['defaults']['swim-iterations']))

            self.updateAnnotations()


        self.MA_settings_defaults_button = QPushButton('Use Defaults')
        self.MA_settings_defaults_button.setStyleSheet("font-size: 10px;")
        # self.MA_settings_defaults_button.setMaximumSize(QSize(100, 18))
        self.MA_settings_defaults_button.setFixedSize(QSize(68, 16))
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

        # sec_label = QLabel('Section:')
        # sec_label.setStyleSheet('font-size: 11px;')
        # w_change_section = HWidget(sec_label, self.btnPrevSection, self.btnNextSection)
        # w_change_section.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # self.fl_actionsMA.addWidget(
        #     HWidget(
        #         ExpandingWidget(self),
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
        self.btnQuickSWIM = QPushButton('Generate Match &Signals')
        self.btnQuickSWIM.setStyleSheet("font-size: 10px; font-weight: 600; color: #161c20; background-color: #9fdf9f;")
        self.btnQuickSWIM.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # self.btnQuickSWIM.setFixedSize(QSize(120, 18))
        self.btnQuickSWIM.setFixedHeight(22)
        self.btnQuickSWIM.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnQuickSWIM.clicked.connect(lambda: cfg.main_window.alignOne(quick_swim=True))
        self.btnQuickSWIM.clicked.connect(lambda: cfg.mw.setdw_matches(True))
        hbl = HBL()
        hbl.setSpacing(0)
        hbl.setContentsMargins(2, 2, 2, 2)
        hbl.addWidget(self.btnQuickSWIM)

        self.MA_controls = QWidget()
        self.MA_controls.setStyleSheet('font-size: 10px;')
        self.MA_controls.setLayout(hbl)

        gb1 = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.MA_baseViewerTitle)
        vbl.addWidget(self.MA_ptsListWidget_base)
        vbl.addWidget(self.baseNextColorWidget)
        gb1.setLayout(vbl)

        gb2 = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.MA_refViewerTitle)
        vbl.addWidget(self.MA_ptsListWidget_ref)
        vbl.addWidget(self.refNextColorWidget)
        gb2.setLayout(vbl)

        self.MA_sbw = HWidget(gb1, gb2)
        self.MA_sbw.layout.setSpacing(0)
        # self.msg_MAinstruct = YellowTextLabel("⇧ + Click - Select 3 corresponding points")
        # self.msg_MAinstruct.setFixedSize(266, 20)

        self.gb_stageInfoText = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(0)
        # vbl.addWidget(self.stageDetails)
        self.gb_stageInfoText.setLayout(vbl)

        self.btnTranslate = QPushButton('Move')
        self.btnTranslate.setStyleSheet("""font-size: 9px;""")
        self.btnTranslate.setFixedSize(QSize(36, 14))
        self.btnTranslate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnTranslate.clicked.connect(self.onTranslate)

        self.le_x_translate = QLineEdit()
        self.le_x_translate.returnPressed.connect(self.onTranslate_x)
        self.le_x_translate.setFixedSize(QSize(36, 16))
        self.le_x_translate.setValidator(QIntValidator())
        # self.le_x_translate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.le_x_translate.setText('0')
        # self.le_x_translate.setMinimum(-99_999)
        # self.le_x_translate.setMaximum(99_999)
        # self.le_x_translate.setSuffix('px')
        self.le_x_translate.setAlignment(Qt.AlignCenter)

        self.le_y_translate = QLineEdit()
        self.le_y_translate.returnPressed.connect(self.onTranslate_y)
        self.le_y_translate.setFixedSize(QSize(36, 16))
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
        self.translatePointsWidget.setStyleSheet("font-size: 10px;")
        self.translatePointsWidget.layout.setAlignment(Qt.AlignRight)

        """  MA Settings Tab  """

        tip = "Window width for manual alignment (px)"

        def fn_slider_MA_SWIM_window():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info('caller: %s' % caller)
                val = int(self.slider_MA_SWIM_window.value())
                if (val % 2) == 1:
                    self.slider_MA_SWIM_window.setValue(val - 1)
                    return

                cfg.data.set_manual_swim_window_px(val)
                self.MA_SWIM_window_le.setText(str(cfg.data.manual_swim_window_px()))
                if cfg.data['state']['tra_ref_toggle'] == 0:
                    cfg.refViewer.drawSWIMwindow()
                else:
                    cfg.baseViewer.drawSWIMwindow()

                if cfg.mw.dw_thumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                cfg.main_window._callbk_unsavedChanges()

        # self.slider_MA_SWIM_window = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.slider_MA_SWIM_window = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_MA_SWIM_window.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_MA_SWIM_window.setMinimum(64)
        self.slider_MA_SWIM_window.setToolTip(tip)
        self.slider_MA_SWIM_window.valueChanged.connect(fn_slider_MA_SWIM_window)
        self.slider_MA_SWIM_window.setFixedWidth(80)
        self.MA_SWIM_window_le = QLineEdit()
        self.MA_SWIM_window_le.setFixedSize(QSize(36, 16))

        def fn_MA_SWIM_window_le():
            caller = inspect.stack()[1].function
            logger.info('caller: %s' % caller)
            # logger.info(f'manua lswim window value {int(self.MA_SWIM_window_le.text())}')

            val = int(self.MA_SWIM_window_le.text())
            if (val % 2) == 1:
                self.slider_MA_SWIM_window.setValue(val - 1)
                return
            #
            cfg.data.set_manual_swim_window_px(val)
            self.dataUpdateMA()
            if cfg.data['state']['tra_ref_toggle'] == 0:
                cfg.refViewer.drawSWIMwindow()
            else:
                cfg.baseViewer.drawSWIMwindow()
            if cfg.mw.dw_thumbs.isVisible():
                self.tn_ref.update()
                self.tn_tra.update()
            self.slider_MA_SWIM_window.setValue(int(self.MA_SWIM_window_le.text()))
        self.MA_SWIM_window_le.returnPressed.connect(fn_MA_SWIM_window_le)

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

        def fn_slider_AS_window():
            logger.info('')
            caller = inspect.stack()[1].function
            if caller == 'main':

                val = int(self.slider_AS_SWIM_window.value())
                if (val % 2) == 1:
                    self.slider_AS_SWIM_window.setValue(val - 1)
                    return
                cfg.data.set_swim_1x1_custom_px(val)
                self.AS_SWIM_window_le.setText(str(cfg.data.swim_1x1_custom_px()[0]))

                self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_custom_px()[0]))

                # self.slider_AS_2x2_SWIM_window.setMaximum(int(val / 2 + 0.5))2
                self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_custom_px()[0]))

                if cfg.data['state']['tra_ref_toggle'] == 0:
                    cfg.refViewer.drawSWIMwindow()
                else:
                    cfg.baseViewer.drawSWIMwindow()

                if cfg.mw.dw_thumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                cfg.main_window._callbk_unsavedChanges()

        self.slider_AS_SWIM_window = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_AS_SWIM_window.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_AS_SWIM_window.setMinimum(64)
        self.slider_AS_SWIM_window.setToolTip(tip)
        self.slider_AS_SWIM_window.valueChanged.connect(fn_slider_AS_window)
        self.slider_AS_SWIM_window.setMaximumWidth(100)

        def fn():
            cfg.data.set_swim_1x1_custom_px(int(self.AS_SWIM_window_le.text()))
            self.dataUpdateMA()
            if cfg.mw.dw_thumbs.isVisible():
                self.tn_ref.update()
                self.tn_tra.update()

        self.AS_SWIM_window_le = QLineEdit()
        self.AS_SWIM_window_le.returnPressed.connect(fn)
        self.AS_SWIM_window_le.setFixedHeight(18)

        tip = "2x2 window width for automatic alignment (px)"

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':

                val = int(self.slider_AS_2x2_SWIM_window.value())
                # logger.critical(f"({val} % 2) = {(val % 2)}")

                #Critical-
                # if (val % 2) == 1:
                #     self.slider_AS_2x2_SWIM_window.setValue(val - 1)
                #     return
                if DEV:
                    logger.critical(f"value: {val}")
                cfg.data.set_swim_2x2_custom_px(val)
                self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_custom_px()[0]))
                self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_custom_px()[0]))
                cfg.main_window._callbk_unsavedChanges()
                self.updateAnnotations()

        self.slider_AS_2x2_SWIM_window = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_AS_2x2_SWIM_window.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_AS_2x2_SWIM_window.setToolTip(tip)
        self.slider_AS_2x2_SWIM_window.valueChanged.connect(fn)
        self.slider_AS_2x2_SWIM_window.setMaximumWidth(100)

        def fn():
            self.slider_AS_2x2_SWIM_window.setValue(int(self.AS_2x2_SWIM_window_le.text()))
            # cfg.data.set_swim_2x2_custom_px(int(self.AS_2x2_SWIM_window_le.text()))
            # self.dataUpdateMA()
            # self.tn_ref.update()
            # self.tn_tra.update()

        self.AS_2x2_SWIM_window_le = QLineEdit()
        self.AS_2x2_SWIM_window_le.returnPressed.connect(fn)
        self.AS_2x2_SWIM_window_le.setFixedHeight(16)

        tip = "SWIM Signal Whitening Factor"

        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info('caller: %s' % caller)
                # cfg.data.set_manual_whitening(float(self.spinbox_whitening.value()))  # Refactor
                cfg.data.set_whitening(float(self.spinbox_whitening.value()))  # Refactor

        self.spinbox_whitening = QDoubleSpinBox(self)
        self.spinbox_whitening.setReadOnly(False)
        self.spinbox_whitening.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.spinbox_whitening.setFixedSize(QSize(60,16))
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
        self.spinbox_swim_iters.setReadOnly(False)
        self.spinbox_swim_iters.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.spinbox_swim_iters.setToolTip('# of SWIM iterations/refinements (default: 3)')
        # self.spinbox_swim_iters.setFixedWidth(80)
        self.spinbox_swim_iters.setFixedSize(QSize(60,18))
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
                if cfg.data['state']['tra_ref_toggle'] == 0:
                    cfg.refViewer.drawSWIMwindow()
                else:
                    cfg.baseViewer.drawSWIMwindow()
                cfg.main_window._callbk_unsavedChanges()
                if cfg.mw.dw_thumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                cfg.mw.updateCorrSignalsDrawer()
                cfg.mw.setTargKargPixmaps()
            cfg.main_window.statusBar.showMessage(f'Manual Alignment Option Set To: {cfg.data.current_method}')

        # self.rb_MA_hint = QRadioButton('Hint')
        # self.rb_MA_strict = QRadioButton('Strict')
        self.rb_MA_hint = QRadioButton('Match Regions (SWIM)')
        self.rb_MA_hint.setStyleSheet("font-size: 9px;")
        self.rb_MA_strict = QRadioButton('Match Points')
        self.rb_MA_strict.setStyleSheet("font-size: 9px;")
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
        # hbl.addWidget(self.btnClearMA)
        w = QWidget()
        w.setLayout(hbl)

        vbl = VBL()
        vbl.addWidget(HWidget(BoldLabel('Method:'), ExpandingWidget(self), self.radioboxes_MA))
        vbl.addWidget(HWidget(BoldLabel('Move Selection:'), ExpandingWidget(self), self.translatePointsWidget))
        vbl.addWidget(w)
        self.gb_MA_manual_controls = QGroupBox()
        self.gb_MA_manual_controls.setObjectName('gb_cpanel')
        self.gb_MA_manual_controls.setLayout(vbl)

        self.AS_swim_window_widget = HWidget(self.slider_AS_SWIM_window, self.AS_SWIM_window_le)
        self.AS_swim_window_widget.setFixedHeight(16)
        self.AS_2x2_swim_window_widget = HWidget(self.slider_AS_2x2_SWIM_window, self.AS_2x2_SWIM_window_le)
        self.AS_2x2_swim_window_widget.setFixedHeight(16)

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

        siz = 20
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

        self.cb_clobber = QCheckBox()
        self.cb_clobber.toggled.connect(lambda: cfg.data.set_clobber(b=self.cb_clobber.isChecked()))
        self.sb_clobber_pixels = QSpinBox()
        self.sb_clobber_pixels.setMaximumWidth(64)
        self.sb_clobber_pixels.setFixedHeight(16)
        self.sb_clobber_pixels.setMinimum(1)
        self.sb_clobber_pixels.setMaximum(16)

        self.btn_settings_apply_everywhere = QPushButton('Apply Clobber to All')

        def fn():
            cfg.data.set_clobber(self.cb_clobber.isChecked(), glob=True)
            cfg.data.set_clobber_px(self.sb_clobber_pixels.value(), glob=True)
            cfg.main_window.tell('Settings Applied!')
            logger.info('Settings applied to entire project.')

        self.btn_settings_apply_everywhere.clicked.connect(fn)
        self.btn_settings_apply_everywhere.setFixedHeight(16)

        self.gb_MA_settings = QGroupBox('These settings apply to the current section only.')
        self.gb_MA_settings.setObjectName('gb_cpanel')
        self.fl_MA_settings = QFormLayout()
        self.fl_MA_settings.setVerticalSpacing(1)
        self.fl_MA_settings.setHorizontalSpacing(2)
        self.fl_MA_settings.setFormAlignment(Qt.AlignCenter)
        self.fl_MA_settings.setContentsMargins(0, 0, 0, 0)
        # self.fl_MA_settings.addRow("Manual Window", self.MA_swim_window_widget)
        self.fl_MA_settings.addRow("SWIM 1x1 Window", self.AS_swim_window_widget)
        self.fl_MA_settings.addRow("SWIM 2x2 Window", self.AS_2x2_swim_window_widget)
        self.fl_MA_settings.addRow("Signal Whitening", self.spinbox_whitening)
        self.fl_MA_settings.addRow("SWIM Iterations", self.spinbox_swim_iters)
        # self.fl_MA_settings.addRow("Select Match Regions\n(minimum=3)", HWidget(self.Q_widget, ExpandingWidget(self)))
        self.fl_MA_settings.addRow("Select Match Regions\n(minimum=3)", self.Q_widget)
        self.fl_MA_settings.addRow('Clobber Fixed Pattern', self.cb_clobber)
        self.fl_MA_settings.addRow('Clobber Amount (px)', self.sb_clobber_pixels)
        # self.fl_MA_settings.addWidget(self.btn_settings_apply_everywhere) #Todo !!!
        # self.fl_MA_settings.addWidget(self.Q_widget)
        self.fl_MA_settings.addWidget(self.MA_settings_defaults_button)
        self.gb_MA_settings.setLayout(self.fl_MA_settings)
        self.gb_MA_settings.setStyleSheet("font-size: 10px;")

        '''
        DEFAULT GRID SWIM SETTINGS
        '''

        ctl_lab_style = 'color: #ede9e8; font-size: 10px;'
        tip = """A SWIM parameter which takes values in the range of -1.00 and 0.00 (default=-0.68)."""
        lab = QLabel("Whitening\nFactor:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(Qt.AlignLeft)
        self.sb_whiteningControl = QDoubleSpinBox(self)
        self.sb_whiteningControl.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.sb_whiteningControl.setFixedSize(QSize(50, 18))
        self.sb_whiteningControl.setDecimals(2)
        self.sb_whiteningControl.setSingleStep(.01)
        self.sb_whiteningControl.setMinimum(-2)
        self.sb_whiteningControl.setMaximum(2)
        self.sb_whiteningControl.valueChanged.connect(cfg.mw._callbk_unsavedChanges)
        self.sb_whiteningControl.valueChanged.connect(cfg.mw._valueChangedWhitening)

        tip = """The number of sequential SWIM refinements to alignment. In general, greater iterations results in a more refined alignment up to some limit, except for in cases of local maxima or complete misalignment (default=3)."""
        self.sb_SWIMiterations = QSpinBox(self)
        self.sb_SWIMiterations.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.sb_SWIMiterations.setFixedSize(QSize(50, 18))
        def fn_swim_iters():
            caller = inspect.stack()[1].function
            if caller == 'main':
                setData('data,defaults,swim-iterations', self.sb_SWIMiterations.value())
                self.updateDetailsPanel()
        self.sb_SWIMiterations.setMinimum(1)
        self.sb_SWIMiterations.setMaximum(9)
        self.sb_SWIMiterations.valueChanged.connect(fn_swim_iters)
        self.sb_SWIMiterations.valueChanged.connect(cfg.mw._callbk_unsavedChanges)

        tip = f"""The full width in pixels of an imaginary, centered grid which SWIM 
        aligns against (default={cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC * 100}% of image width)."""
        lab = QLabel("SWIM\nWindow:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(Qt.AlignLeft)
        # self._swimWindowControl = QSpinBox(self)
        self._swimWindowControl = QLineEdit(self)
        self._swimWindowControl.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._swimWindowControl.setFixedSize(QSize(50, 18))
        self._swimWindowControl.setValidator(QIntValidator())
        def fn():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info(f'caller: {caller}')
                try:
                    val = int(self._swimWindowControl.text())
                except:
                    self._swimWindowControl.setText(str(cfg.data['data']['defaults'][cfg.data.scale_key]['swim-window-px'][0]))
                    return
                logger.info(f"val = {val}")
                if (val % 2) == 1:
                    new_val = val - 1
                    self.tell(f'SWIM requires even values as input. Setting value to {new_val}')
                    self._swimWindowControl.setText(str(new_val))
                    return
                logger.critical(f"val = {val}...........")
                # cfg.data.set_auto_swim_windows_to_default(factor=float(self._swimWindowControl.text()) / cfg.data.image_size()[0])
                cfg.data.set_auto_swim_windows_to_default(factor=val / cfg.data.image_size()[0])
                # self.swimWindowChanged.emit()

                if self._tabs.currentIndex() == 1:
                    cfg.baseViewer.drawSWIMwindow()
                    cfg.refViewer.drawSWIMwindow()
                if cfg.mw.dw_thumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                cfg.mw.tell(f'SWIM Window set to: {str(val)}')
        self._swimWindowControl.selectionChanged.connect(fn)
        self._swimWindowControl.returnPressed.connect(fn)
        self._swimWindowControl.selectionChanged.connect(cfg.mw._callbk_unsavedChanges)
        self._swimWindowControl.returnPressed.connect(cfg.mw._callbk_unsavedChanges)

        self.fl_swimSettings = QFormLayout()
        self.fl_swimSettings.setContentsMargins(2, 2, 2, 2)
        # self.fl_swimSettings.setFormAlignment(Qt.AlignVCenter)
        self.fl_swimSettings.setVerticalSpacing(4)
        self.fl_swimSettings.addRow('Window Width (px):', self._swimWindowControl)
        self.fl_swimSettings.addRow('Signal Whitening:', self.sb_whiteningControl)
        self.fl_swimSettings.addRow('Iterations:', self.sb_SWIMiterations)
        self.fl_swimSettings.addWidget(self.btnResetAllMA)
        # self.fl_swimSettings.setAlignment(Qt.AlignCenter)
        self.fl_swimSettings.setFormAlignment(Qt.AlignVCenter)

        self.gb_defaultGridSwimSettings = QGroupBox("Default SWIM Settings")
        self.gb_defaultGridSwimSettings.setObjectName('gb_cpanel')
        self.gb_defaultGridSwimSettings.setLayout(self.fl_swimSettings)
        # self.gb_defaultGridSwimSettings.setAlignment(Qt.AlignTop)


        '''
        OUTPUT SETTINGS
        '''
        tip = """Whether to auto-generate aligned images following alignment."""
        self._toggleAutogenerate = ToggleSwitch()
        self._toggleAutogenerate.stateChanged.connect(cfg.mw._toggledAutogenerate)
        self._toggleAutogenerate.stateChanged.connect(cfg.mw._callbk_unsavedChanges)
        self._toggleAutogenerate.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._toggleAutogenerate.setChecked(True)

        tip = """Bounding box is only applied upon "Align All" and "Regenerate". Caution: Turning this ON may 
        significantly increase the size of generated images."""
        self._bbToggle = ToggleSwitch()
        self._bbToggle.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._bbToggle.toggled.connect(cfg.mw._callbk_bnding_box)
        self._bbToggle.toggled.connect(cfg.mw._callbk_unsavedChanges)
        self._bbToggle.toggled.connect(self.updateDetailsPanel)

        tip = 'Polynomial bias correction (defaults to None), alters the generated images including their width and height.'
        self._polyBiasCombo = QComboBox(self)
        # self._polyBiasCombo.setStyleSheet("font-size: 10px; padding-left: 6px;")
        self._polyBiasCombo.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._polyBiasCombo.addItems(['None', 'poly 0°', 'poly 1°', 'poly 2°', 'poly 3°', 'poly 4°'])
        # self._polyBiasCombo.setCurrentText(str(cfg.DEFAULT_CORRECTIVE_POLYNOMIAL))
        self._polyBiasCombo.currentIndexChanged.connect(cfg.mw._valueChangedPolyOrder)
        self._polyBiasCombo.currentIndexChanged.connect(cfg.mw._callbk_unsavedChanges)
        self._polyBiasCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._polyBiasCombo.setFixedSize(QSize(70, 16))
        self._polyBiasCombo.lineEdit()

        self.flSettings = QFormLayout()
        self.flSettings.setFormAlignment(Qt.AlignVCenter)
        self.flSettings.setContentsMargins(2, 2, 2, 2)
        self.flSettings.setVerticalSpacing(2)
        self.flSettings.setHorizontalSpacing(0)
        self.flSettings.addRow('Generate TIFFs: ', HWidget(ExpandingWidget(self), self._toggleAutogenerate))
        self.flSettings.addRow('Bounding Box: ', HWidget(ExpandingWidget(self), self._bbToggle))
        self.flSettings.addRow('Corrective Bias: ', HWidget(ExpandingWidget(self), self._polyBiasCombo))

        self.gb_outputSettings = QGroupBox("Output Settings")
        self.gb_outputSettings.setObjectName('gb_cpanel')
        self.gb_outputSettings.setLayout(self.flSettings)

        self.fl_results = QFormLayout()
        self.fl_results.setVerticalSpacing(2)
        self.fl_results.setContentsMargins(0, 0, 0, 0)
        self.results0 = QLabel()  # Image dimensions
        self.results1 = QLabel()  # # of images
        self.results2 = QLabel()  # SNR average
        self.results3 = QWidget()
        self.results3_fl = QFormLayout()
        self.results3_fl.setContentsMargins(0, 0, 0, 0)
        self.results3_fl.setVerticalSpacing(2)
        self.results3.setLayout(self.results3_fl)
        self.fl_results.addRow('Image Dimensions', self.results0)
        self.fl_results.addRow('# Images', self.results1)
        self.fl_results.addRow('SNR (average)', self.results2)
        self.sa_details = QScrollArea()
        self.sa_details.setWidgetResizable(True)
        self.sa_details.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_details.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.secDetails_w = QWidget()
        self.secDetails_w.setStyleSheet("""
            color: #161c20;
            font-size: 9px;
            font-weight: 600;
        """)
        self.secDetails_w.setContentsMargins(0, 0, 0, 0)
        self.secDetails_fl = QFormLayout()
        self.secDetails_fl.setVerticalSpacing(2)
        self.secDetails_fl.setHorizontalSpacing(4)
        self.secDetails_fl.setContentsMargins(0, 0, 0, 0)
        secStyle = """ font-weight: 300; background-color: #dedede; """
        self.secName = QLabel()
        self.secReference = QLabel()
        self.secExcluded = QLabel()
        self.secHasBB = QLabel()
        self.secUseBB = QLabel()
        self.secAlignmentMethod = QLabel()
        self.secSrcImageSize = QLabel()
        self.secAlignedImageSize = QLabel()
        self.secSNR = QLabel()
        self.secDefaults = QLabel()
        self.secName.setStyleSheet(secStyle)
        self.secReference.setStyleSheet(secStyle)
        self.secExcluded.setStyleSheet(secStyle)
        self.secHasBB.setStyleSheet(secStyle)
        self.secUseBB.setStyleSheet(secStyle)
        self.secAlignmentMethod.setStyleSheet(secStyle)
        self.secSrcImageSize.setStyleSheet(secStyle)
        self.secAlignedImageSize.setStyleSheet(secStyle)
        self.secSNR.setStyleSheet(secStyle)
        self.secDefaults.setStyleSheet(secStyle)
        self.secDetails = OrderedDict({
            'Name': self.secName,
            'Reference': self.secReference,
            'SNR': self.secSNR,
            'Alignment Method': self.secAlignmentMethod,
            'Source Image Size': self.secSrcImageSize,
            'Aligned Image Size': self.secAlignedImageSize,
            'Excluded Sections': self.secExcluded,
            'Has Bounding Box': self.secHasBB,
            'Use Bounding Box': self.secUseBB,
            'Defaults': self.secDefaults,
        })
        for i in range(len(self.secDetails)):
            self.secDetails_fl.addRow(list(self.secDetails.items())[i][0], list(self.secDetails.items())[i][1])

        self.secAffine = QLabel()
        self.gb_affine = QGroupBox("Affine")
        self.gb_affine.setLayout(VBL(self.secAffine))

        # self.secDetails_fl.addWidget(self.gb_affine)
        self.secDetails_w.setLayout(self.secDetails_fl)
        self.sa_details.setWidget(VWidget(self.secDetails_w, self.gb_affine))
        self.sa_details.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_details.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.sa_lowest8 = QScrollArea()
        self.sa_lowest8.setWidgetResizable(True)
        self.sa_lowest8.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_lowest8.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.sa_runtimes = QScrollArea()
        self.sa_runtimes.setWidgetResizable(True)
        self.sa_runtimes.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_runtimes.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)


        self.MA_use_global_defaults_lab = QLabel('Global defaults will be used.')
        self.MA_use_global_defaults_lab.setStyleSheet('font-size: 13px; font-weight: 600;')
        self.MA_use_global_defaults_lab.setAlignment(Qt.AlignCenter)

        self.method_rb0 = QRadioButton('Default Grid')
        self.method_rb0.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.method_rb0.setStyleSheet("font-size: 9px; font-weight: 600;")

        tip = """Similar to the Default Grid method, but the user is able to avoid image defects 
        by adjusting the grid shape and location and adding or removing quadrants of the grid. 
        An affine transformation requires at least 3 regions (quadrants)."""
        self.method_rb1 = QRadioButton('Custom Grid')
        self.method_rb1.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.method_rb1.setStyleSheet("font-size: 9px; font-weight: 600;")
        self.method_rb1.setToolTip(tip)


        tip = """User provides an alignment hint for SWIM by selecting 3 matching regions (manual correspondence). 
        Note: An affine transformation requires at least 3 correspondence regions."""
        # self.method_rb2 = QRadioButton('Correspondence Points')
        self.method_rb2 = QRadioButton('Match Regions')
        self.method_rb2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.method_rb2.setStyleSheet("font-size: 9px; font-weight: 600;")
        self.method_rb2.setToolTip(tip)


        self.method_bg = QButtonGroup(self)
        self.method_bg.setExclusive(True)
        self.method_bg.addButton(self.method_rb0)
        self.method_bg.addButton(self.method_rb1)
        self.method_bg.addButton(self.method_rb2)

        def method_bg_fn():
            logger.info('')
            # logger.critical(f'\n\n\n\n\n BEFORE:{cfg.data.current_method} \n\n\n\n\n')
            cur_index = self.MA_stackedWidget.currentIndex()
            if self.method_rb0.isChecked():
                logger.info('radiobox 0 is checked')
                self.MA_stackedWidget.setCurrentIndex(0)
                cfg.data.current_method = 'grid-default'
            elif self.method_rb1.isChecked():
                logger.info('radiobox 1 is checked')
                self.MA_stackedWidget.setCurrentIndex(1)
                cfg.data.current_method = 'grid-custom'
            elif self.method_rb2.isChecked():
                logger.info('radiobox 2 is checked')
                self.MA_stackedWidget.setCurrentIndex(2)
                if cfg.data.current_method == 'manual-strict':
                    self.rb_MA_strict.setChecked(True)
                else:
                    cfg.data.current_method = 'manual-hint'
                    self.rb_MA_hint.setChecked(True)
            cfg.mw.setTargKargPixmaps()
            # elif cur_index == 4:
            #     self.MA_stackedWidget.setCurrentIndex(4)
            cfg.mw.updateCorrSignalsDrawer()
            # QApplication.processEvents()
            # if cfg.data['state']['stackwidget_ng_toggle']:
            #     cfg.baseViewer.drawSWIMwindow()
            # else:
            #     cfg.refViewer.drawSWIMwindow()
            self.updateAnnotations()

            # self.msg_MAinstruct.setVisible(cfg.data.current_method not in ('grid-default', 'grid-custom'))

            # logger.critical(f'\n\n\n\n\n AFTER:{cfg.data.current_method} \n\n\n\n\n')
            # cfg.main_window.dataUpdateWidgets()

        self.method_bg.buttonClicked.connect(method_bg_fn)

        self.radioboxes_method = HWidget(self.method_rb0, self.method_rb1, self.method_rb2)
        self.radioboxes_method.setMaximumHeight(20)

        self.lab_region_selection = QLabel("⇧ + Click - Select 3 corresponding regions\n")
        self.lab_region_selection.setStyleSheet("font-size: 10px; font-weight: 600; color: #161c20; padding: 1px;")

        self.lab_region_selection2 = QLabel("Note: Match signals can be generated from any # of match selections.\n"
                                            "At least three matching regions are necessary to form an alignment affine.")
        self.lab_region_selection2.setStyleSheet("font-size: 9px; color: #161c20; padding: 1px;")
        self.MA_points_tab = VWidget(
            self.MA_sbw,
            self.gb_MA_manual_controls,
            self.lab_region_selection,
            self.lab_region_selection2,
        )
        self.MA_points_tab.layout.setSpacing(1)


        def bottom():
            self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())

        def top():
            self.te_logs.verticalScrollBar().setValue(0)

        self.logs_top_btn = QPushButton('Top')
        self.logs_top_btn.setStyleSheet("font-size: 9px;")
        self.logs_top_btn.setFixedSize(QSize(40, 18))
        self.logs_top_btn.clicked.connect(top)

        self.logs_bottom_btn = QPushButton('Bottom')
        self.logs_bottom_btn.setStyleSheet("font-size: 9px;")
        self.logs_bottom_btn.setFixedSize(QSize(40, 18))
        self.logs_bottom_btn.clicked.connect(bottom)

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

        self.logs_refresh_btn = QPushButton('Refresh')
        self.logs_refresh_btn.setStyleSheet("font-size: 9px;")
        self.logs_refresh_btn.setFixedSize(QSize(64, 18))
        self.logs_refresh_btn.clicked.connect(self.refreshLogs)

        self.logs_delete_all_btn = QPushButton('Delete Logs')
        self.logs_delete_all_btn.setStyleSheet("font-size: 9px;")
        self.logs_delete_all_btn.setFixedSize(QSize(64, 18))
        self.logs_delete_all_btn.clicked.connect(fn)

        self.te_logs = QTextEdit()
        self.te_logs.setReadOnly(True)
        self.te_logs.setText('Logs...')

        self.lab_logs = BoldLabel('Logs:')

        self.rb_logs_swim_args = QRadioButton('SWIM Args')
        self.rb_logs_swim_args.setStyleSheet("font-size: 9px;")
        self.rb_logs_swim_args.setChecked(True)
        self.rb_logs_swim_out = QRadioButton('SWIM Out')
        self.rb_logs_swim_out.setStyleSheet("font-size: 9px;")
        self.rb_logs_mir_args = QRadioButton('MIR')
        self.rb_logs_mir_args.setStyleSheet("font-size: 9px;")
        self.rb_logs = QButtonGroup(self)
        self.rb_logs.setExclusive(True)
        self.rb_logs.addButton(self.rb_logs_swim_args)
        self.rb_logs.addButton(self.rb_logs_swim_out)
        self.rb_logs.addButton(self.rb_logs_mir_args)

        # self.btns_logs = QWidget()

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
            args = '\n'.join(cfg.data['data']['scales'][cfg.data.scale_key]['stack'][cfg.data.zpos]['alignment'][key][
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
            args = '\n'.join(cfg.data['data']['scales'][cfg.data.scale_key]['stack'][cfg.data.zpos]['alignment'][key][
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
            args = '\n'.join(cfg.data['data']['scales'][cfg.data.scale_key]['stack'][cfg.data.zpos]['alignment'][key][
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
            HWidget(ExpandingWidget(self),
                    self.logs_refresh_btn,
                    self.logs_delete_all_btn,
                    self.logs_top_btn,
                    self.logs_bottom_btn
                    ),
        )
        self.logs_widget.setStyleSheet("font-size: 9px;")
        self.logs_widget.layout.setContentsMargins(2,2,2,2)
        self.logs_widget.layout.setSpacing(2)

        # self.sw_logs.addWidget(self.logs_widget)


        # self.fl_settings = QFormLayout()
        # self.fl_settings.setVerticalSpacing(4)
        # self.fl_settings.setHorizontalSpacing(6)
        # self.fl_settings.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        # self.fl_settings.setSpacing(2)
        # self.fl_settings.setContentsMargins(0, 0, 0, 0)
        # # self.fl_settings.addRow('Save Match Regions', self.cb_keep_swim_templates)
        # self.fl_settings.addRow('Clobber Fixed Pattern', self.cb_clobber)
        # self.fl_settings.addRow('Clobber Amount (px)', self.sb_clobber_pixels)
        # # self.fl_settings.addWidget(self.btn_settings_apply_cur_sec)
        # self.fl_settings.addWidget(self.btn_settings_apply_everywhere)

        # self.gb_globSettings = QGroupBox("Other Settings")
        # self.gb_globSettings.setObjectName('gb_cpanel')
        # self.gb_globSettings.setStyleSheet("font-size: 9px;")
        # self.gb_globSettings.setContentsMargins(0, 0, 0, 0)
        # self.gb_globSettings.setLayout(self.fl_settings)

        '''MA STACKED WIDGET'''
        self.MA_stackedWidget = QStackedWidget()
        # self.MA_stackedWidget.addWidget(self.MA_use_global_defaults_lab)
        self.MA_stackedWidget.addWidget(self.gb_defaultGridSwimSettings)
        # self.MA_stackedWidget.addWidget(VWidget(self.gb_MA_settings, self.Q_widget))
        self.MA_stackedWidget.addWidget(self.gb_MA_settings)
        self.MA_stackedWidget.addWidget(self.MA_points_tab)

        # 0617
        self.sw_alignment_editor = QStackedWidget()
        self.sw_alignment_editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sw_alignment_editor.setObjectName('stackwidget-neuroglancer')
        self.sw_alignment_editor.addWidget(self.MA_webengine_ref)
        self.sw_alignment_editor.addWidget(self.MA_webengine_base)
        self.sw_alignment_editor.setCurrentIndex(cfg.data['state']['tra_ref_toggle'])

        self.cl_tra = ClickLabel(' Transforming ')
        self.cl_tra.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cl_tra.setMinimumWidth(128)
        # self.cl_tra.setAlignment(Qt.AlignCenter)
        self.cl_tra.setAlignment(Qt.AlignLeft)
        self.cl_tra.setFixedHeight(16)
        # self.cl_tra.setMinimumWidth(140)
        self.cl_tra.clicked.connect(self.set_transforming)

        self.cl_ref = ClickLabel(' Reference ')
        self.cl_ref.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cl_ref.setMinimumWidth(128)
        # self.cl_ref.setAlignment(Qt.AlignCenter)
        self.cl_ref.setAlignment(Qt.AlignRight)
        self.cl_ref.setFixedHeight(16)
        # self.cl_ref.setMinimumWidth(140)
        self.cl_ref.clicked.connect(self.set_reference)

        self.cl_tra.setStyleSheet('background-color: #339933; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        self.cl_ref.setStyleSheet('background-color: #222222; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')

        self.wSwitchRefTra = QWidget()
        self.wSwitchRefTra.setFixedHeight(16)
        self.wSwitchRefTra.setStyleSheet("background-color: #222222;")
        self.wSwitchRefTra.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.wSwitchRefTra.setContentsMargins(0, 0, 0, 0)
        self.labAlignTo = QLabel(f"Aligns To ➤")
        self.labAlignTo.setToolTip("'/' (slash) key to toggle")
        self.labAlignTo.setFixedWidth(80)
        self.labAlignTo.setAlignment(Qt.AlignHCenter)
        self.labAlignTo.setStyleSheet('background-color: #ede9e8; color: #161c20; font-size: 11px; font-weight: 600; border-radius: 8px; padding-left: 1px; padding-right: 1px;')
        gl = QGridLayout()
        gl.setContentsMargins(0,0,0,0)
        gl.setSpacing(0)
        gl.addWidget(self.cl_tra, 0,0,1,2)
        gl.addWidget(self.cl_ref, 0,2,1,2)
        hw = HWidget()
        hw.layout.addStretch()
        hw.layout.addWidget(self.labAlignTo)
        hw.layout.addStretch()

        gl.addWidget(hw, 0,1,1,2)
        # gl.setAlignment(Qt.AlignCenter)
        self.wSwitchRefTra.setLayout(gl)

        # hbl = HBL(self.cl_tra, self.labAlignTo, self.cl_ref)
        # hbl.setSpacing(0)
        # hbl.setStretch(0,1)
        # hbl.setStretch(1,0)
        # hbl.setStretch(2,1)
        # self.wSwitchRefTra.setLayout(hbl)


        def fn_radiobox():
            newcur = (0, 1)[self.rb_transforming.isChecked()]
            cfg.data['state']['tra_ref_toggle'] = newcur
            active = (cfg.refViewer, cfg.baseViewer)[newcur]
            active._blockStateChanged = True
            inactive = (cfg.refViewer, cfg.baseViewer)[1 - newcur]
            with active.txn() as s:
                s.voxel_coordinates[1] = inactive.state.voxel_coordinates[1]
                s.voxel_coordinates[2] = inactive.state.voxel_coordinates[2]
                try:
                    s.cross_section_scale = inactive.state.cross_section_scale
                except:
                    print_exception()

            if cfg.data['state']['tra_ref_toggle'] == 0:
                # cfg.refViewer.set_layer(cfg.data.get_ref_index())
                cfg.refViewer.set_layer()

            active._blockStateChanged = False
            self.sw_alignment_editor.setCurrentIndex(newcur)
            self.dataUpdateMA()  # 0613+ #attempt fix for 'MA_gl_overlay' not hiding after slash press followed by layer change
            self.updateAnnotations()

        # https://codeloop.org/pyqt5-make-multi-document-interface-mdi-application/


        # '''THIS WORKS'''
        # self.mdi = QMdiArea()
        # self.sub_webengine = QMdiSubWindow()
        # self.sub_webengine.setWidget(self.webengine)
        # self.sub_webengine.showMaximized()
        # self.sub_webengine.setWindowFlags(Qt.FramelessWindowHint)
        # self.mdi.addSubWindow(self.sub_webengine)

        # self.mdi.setBackground(QBrush(Qt.transparent))
        # self.w_mdi = QWidget()
        # self.w_mdi.setLayout(self.mdi)
        # def WindowTrig(p):
        #     print(f"Menu Selection: {p.text()}")
        #     if p.text() == "New":
        #         self.sub = QMdiSubWindow()
        #         te = QTextEdit()
        #         te.setFixedSize(QSize(400,300))
        #         self.sub.setWidget()
        #         self.sub.setWindowTitle("Sub Window")
        #         self.mdi.addSubWindow(self.sub)
        #         self.sub.show()

        # testmenu = QMenu()
        # testmenu.addAction("New")
        # testmenu.addAction("cascade")
        # testmenu.addAction("Tiled")

        # testmenu.triggered[QAction].connect(WindowTrig)
        #
        # self.testButton = QPushButton()
        # self.testButton.setMenu(testmenu)
        # def testFn():
        #     print('Test Function Called...')
        # self.testButton.clicked.connect(testFn)

        self.gl_sw_main = QGridLayout()
        self.gl_sw_main.setSpacing(0)
        self.gl_sw_main.setContentsMargins(0, 0, 0, 0)
        self.gl_sw_main.addWidget(self.sw_alignment_editor, 0, 0, 3, 3)
        self.gl_sw_main.addWidget(self._overlayLab, 0, 0, 3, 3)
        # self.gl_sw_main.addWidget(self.mdi, 0, 0, 3, 3)
        # self.gl_sw_main.addWidget(self.ng_messages, 2, 0, 3, 3)
        # self.gl_sw_main.addWidget(self.msg_MAinstruct, 0, 0, 3, 3)
        # self.msg_MAinstruct.setAlignment(Qt.AlignTop)

        self._ng_widget = QWidget()
        self._ng_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._ng_widget.setLayout(self.gl_sw_main)

        self.ng_widget = QWidget()
        self.ng_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vbl = VBL(self.wSwitchRefTra, self._ng_widget)
        vbl.setSpacing(0)
        self.ng_widget.setLayout(vbl)

        # TOOLBARS

        ngFont = QFont('Tahoma')
        ngFont.setBold(True)
        pal = QPalette()
        pal.setColor(QPalette.Text, QColor("#FFFF66"))

        self.comboNgLayout = QComboBox(self)
        self.comboNgLayout.setStyleSheet("font-size: 9px;")
        self.comboNgLayout.setFixedSize(70, 14)
        self.comboNgLayout.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # items = ['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '3d']
        items = ['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d']
        self.comboNgLayout.addItems(items)
        # self.comboNgLayout.activated.connect(cfg.main_window.fn_ng_layout_combobox)
        self.comboNgLayout.activated.connect(self.onNgLayoutCombobox)
        self.comboNgLayout.setCurrentText(getData('state,ng_layout'))

        # self.ngcl_background = NgClickLabel(self)
        self.ngcl_background = QToolButton()
        self.ngcl_background.setCheckable(True)
        self.ngcl_background.setText('Background')
        self.ngcl_background.setToolTip('Toggle Background')

        # if getData('state,neutral_contrast'):
        #     self.ngcl_background.setStyleSheet("""background: #808080; color: #f3f6fb;
        #                 border-radius: 3px; padding: 2px; margin: 0px; border-color: #339933;""")
        # else:
        #     self.ngcl_background.setStyleSheet("""background: #222222; color: #f3f6fb;
        #                 border-radius: 3px; padding: 2px; margin: 0px; border-color: #339933;""")

        def fn():
            setData('state,neutral_contrast', not getData('state,neutral_contrast'))
            [v.updateHighContrastMode() for v in self.get_viewers()]

            # if getData('state,neutral_contrast'):
            #     self.ngcl_background.setStyleSheet("""background: #808080; color: #f3f6fb;
            #             border-radius: 3px; padding: 2px; margin: 0px; border-color: #339933;""")
            # else:
            #     self.ngcl_background.setStyleSheet("""background: #222222; color: #f3f6fb;
            #             border-radius: 3px; padding: 2px; margin: 0px; border-color: #339933;""")

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
            font-size: 9px;
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

        self.lab_filename = QLabel('Filename')
        self.lab_filename.setStyleSheet("""background-color: #222222; color: #ede9e8; font-weight: 600; font-size: 10px;""")

        self.layout_ng_MA_toolbar = QHBoxLayout()
        self.layout_ng_MA_toolbar.setContentsMargins(0, 0, 0, 0)

        self.layout_ng_MA_toolbar.addWidget(self.lab_filename)

        self.w_section_label_header = QWidget()
        self.w_section_label_header.setStyleSheet("""background-color: #222222; color: #ede9e8; font-weight: 600; font-size: 10px;""")
        self.w_section_label_header.setFixedHeight(16)
        self.w_section_label_header.setLayout(self.layout_ng_MA_toolbar)

        logger.info("Setting NG extended toolbar...")

        self.w_ng_extended_toolbar = QToolBar()
        self.w_ng_extended_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.w_ng_extended_toolbar.setIconSize(QSize(18, 18))
        self.w_ng_extended_toolbar.setFixedHeight(24)
        self.w_ng_extended_toolbar.setStyleSheet(toolbar_style)
        self.w_ng_extended_toolbar.setAutoFillBackground(True)

        # self.labShowHide = QLabel('Display: ')
        # self.labShowHide.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")
        self.labNgLayout = QLabel('Layout: ')
        self.labNgLayout.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")
        # self.labScaleStatus = QLabel('Scale Status: ')
        self.labScaleStatus = QLabel('Status: ')
        self.labScaleStatus.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")

        def fn():
            logger.info('')
            opt = getData('state,show_ng_controls')
            opt = not opt
            setData('state,show_ng_controls', opt)
            self.initNeuroglancer()
            # self.spreadW.setVisible(opt)
            # self.updateUISpacing()
            if cfg.data['state']['current_tab'] == 1:
                cfg.baseViewer.updateUIControls()
                cfg.refViewer.updateUIControls()
            else:
                cfg.emViewer.updateUIControls()
            QApplication.processEvents()
        # self.ngcl_uiControls = NgClickLabel(self)
        self.ngcl_uiControls = QToolButton()
        self.ngcl_uiControls.setCheckable(True)
        self.ngcl_uiControls.setText('NG Controls')
        self.ngcl_uiControls.clicked.connect(fn)


        def fn():
            logger.info('')
            opt = getData('state,show_yellow_frame')
            opt = not opt
            setData('state,show_yellow_frame', opt)
            if cfg.emViewer:
                cfg.emViewer.updateDefaultAnnotations()
            if cfg.emViewer:
                cfg.emViewer.updateUIControls()
        # self.ngcl_bounds = NgClickLabel(self)
        self.ngcl_bounds = QToolButton()
        self.ngcl_bounds.setCheckable(True)
        self.ngcl_bounds.setText('Bounds')
        self.ngcl_bounds.clicked.connect(fn)


        def fn():
            logger.info('')
            opt = getData('state,show_axis_lines')
            opt = not opt
            setData('state,show_axis_lines', opt)
            # self.ngShowAxisLinesAction.setText(('Show Axis Lines', 'Hide Axis Lines')[opt])
            # for v in self.get_viewers():
            #     v.updateAxisLines()
            if cfg.emViewer:
                cfg.emViewer.updateAxisLines()
        # self.ngcl_axes = NgClickLabel(self)
        self.ngcl_axes = QToolButton()
        self.ngcl_axes.setCheckable(True)
        self.ngcl_axes.setText('Axes')
        self.ngcl_axes.clicked.connect(fn)

        def fn():
            logger.info('')
            QApplication.processEvents()
            logger.info(f'isClicked = {self.ngcl_snr.isClicked}')
            if self.ngcl_snr.isClicked:
                self.detailsSNR.show()
            else:
                self.detailsSNR.hide()
            cfg.mw.dataUpdateWidgets()
        self.ngcl_snr = NgClickLabel(self)
        self.ngcl_snr.setText('SNR')
        self.ngcl_snr.clicked.connect(fn)

        def fn():
            if not self.ngcl_shader.isChecked():
                self.shaderToolbar.hide()
                self.ngcl_shader.setToolTip('Show Brightness & Contrast Shaders')
            else:
                self.contrastSlider.setValue(int(cfg.data.contrast))
                self.contrastLE.setText('%.2f' % cfg.data.contrast)
                self.brightnessSlider.setValue(int(cfg.data.brightness))
                self.brightnessLE.setText('%.2f' % cfg.data.brightness)
                self.initNeuroglancer() #Critical #Cringe #guarantees sliders will work
                self.shaderToolbar.show()
                self.ngcl_shader.setToolTip('Hide Brightness & Contrast Shaders')
            QApplication.processEvents()

        # self.ngcl_shader = NgClickLabel(self)
        self.ngcl_shader = QToolButton()
        self.ngcl_shader.setCheckable(True)
        self.ngcl_shader.setText('Shader')
        self.ngcl_shader.clicked.connect(fn)

        self.blinkLab = QLabel(f"  Blink {hotkey('B')}: ")
        self.blinkLab.setStyleSheet("""color: #ede9e8; font-size: 10px; font-weight: 600;""")

        self.tbbBlinkToggle = QPushButton()
        self.tbbBlinkToggle.setIconSize(QSize(24,24))
        self.tbbBlinkToggle.setStyleSheet("font-size: 9px; border: none; background: none; margin: 0px; padding: 0px;")
        self.tbbBlinkToggle.setCheckable(True)

        self.tbbBlinkToggle.setIcon(qta.icon('mdi.toggle-switch-off-outline', color='#f3f6fb'))
        
        def blink_main_fn():
            setData('state,blink', self.tbbBlinkToggle.isChecked())
            logger.info(f"blink toggle: {getData('state,blink')}")
            cfg.mw.tell(f"Blink : {('OFF','ON')[getData('state,blink')]}")
            self.tbbBlinkToggle.setIcon(qta.icon(
                ('mdi.toggle-switch-off-outline', 'mdi.toggle-switch')[getData('state,blink')],
                color='#f3f6fb'))

            if getData('state,blink'):
                self.blinkTimer.timeout.connect(cfg.emViewer.blink)
                cfg.project_tab.blinkTimer.start()
            else:
                self.blinkTimer.stop()
                cfg.emViewer._blinkState = 0

        self.tbbBlinkToggle.clicked.connect(blink_main_fn)

        # ----------------
        # widgets to gain insight into Neuroglancer state

        self.le_zoom = QLineEdit()
        self.le_zoom.setMaximumWidth(64)
        self.le_zoom.setValidator(QDoubleValidator())
        self.le_zoom.returnPressed.connect(lambda: setData('state,ng_zoom', float(self.le_zoom.text())))
        self.le_zoom.returnPressed.connect(lambda: self.viewer.set_zoom(float(self.le_zoom.text())))

        self.zoomLab = QLabel('Zoom:')
        self.zoomLab.setStyleSheet("""color: #ede9e8; font-size: 10px; font-weight: 600;""")

        self.w_zoom = HWidget(self.zoomLab, self.le_zoom)
        self.w_zoom.setMaximumWidth(100)
        self.w_zoom.layout.setAlignment(Qt.AlignLeft)


        self.tbbNgHelp = QToolButton()
        def fn_ng_help():
            logger.info('')
            cfg.emViewer.setHelpMenu(not self.tbbNgHelp.isChecked())
            # if self.tbbNgHelp.isChecked():
            #     self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#161c20'))
            # else:
            #     self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#f3f6fb'))

        self.tbbNgHelp.setToolTip("Neuroglancer Help")
        self.tbbNgHelp.setCheckable(True)
        self.tbbNgHelp.pressed.connect(fn_ng_help)
        self.tbbNgHelp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#f3f6fb'))


        # ----------------


        self.w_ng_extended_toolbar.addWidget(self.labNgLayout)
        self.w_ng_extended_toolbar.addWidget(self.comboNgLayout)
        self.w_ng_extended_toolbar.addWidget(self.blinkLab)
        self.w_ng_extended_toolbar.addWidget(self.tbbBlinkToggle)
        # ----------------
        # Add additional widgets to gain insight into Neuroglancer state

        self.w_ng_extended_toolbar.addWidget(self.w_zoom)
        self.w_ng_extended_toolbar.addWidget(self.tbbNgHelp)

        # ----------------
        self.w_ng_extended_toolbar.addWidget(ExpandingWidget(self))
        self.w_ng_extended_toolbar.addWidget(self.ngcl_uiControls)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_shader)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_bounds)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_axes)
        # self.w_ng_extended_toolbar.addWidget(self.ngcl_snr)
        self.w_ng_extended_toolbar.addWidget(self.ngcl_background)

        self.sideSliders = VWidget(self.ZdisplaySliderAndLabel, self.zoomSliderAndLabel)
        self.sideSliders.setFixedWidth(16)
        self.sideSliders.layout.setSpacing(0)
        self.sideSliders.setStyleSheet("""background-color: #222222; color: #ede9e8;""")

        '''REFERENCE AND TRANSFORMING THUMBNAILS WITH PAINTED SWIM REGION ANNOTATIONS'''
        # self.tn_tra_overlay = QLabel('Excluded')
        self.tn_tra_overlay = QLabel('X')
        self.tn_tra_overlay.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tn_tra_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.tn_tra_overlay.setAlignment(Qt.AlignCenter)
        self.tn_tra_overlay.setStyleSheet("""color: #FF0000; font-size: 20px; font-weight: 600; background-color: rgba(0, 0, 0, 0.5); """)
        self.tn_tra_overlay.hide()

        self.tn_ref = ThumbnailFast(self, name='reference')
        self.tn_tra = ThumbnailFast(self, name='transforming')
        self.tn_ref.setMinimumSize(QSize(64,64))
        self.tn_tra.setMinimumSize(QSize(64,64))

        self.w_tn_tra = QWidget()
        self.gl_tn_tra = QGridLayout()
        self.gl_tn_tra.setContentsMargins(0, 0, 0, 0)
        self.gl_tn_tra.addWidget(self.tn_tra, 0, 0, 1, 1)
        self.gl_tn_tra.addWidget(self.tn_tra_overlay, 0, 0, 1, 1)
        self.w_tn_tra.setLayout(self.gl_tn_tra)

        self.tn_ref_lab = QLabel('Reference Section')
        self.tn_ref_lab.setFixedHeight(26)
        self.tn_ref_lab.setStyleSheet("""font-size: 10px; background-color: #ede9e8; color: #161c20;""")

        self.tn_tra_lab = QLabel('Transforming Section')
        self.tn_tra_lab.setFixedHeight(26)
        self.tn_tra_lab.setStyleSheet("""font-size: 10px; background-color: #ede9e8; color: #161c20;""")

        self.tn_widget = QTableWidget()
        self.tn_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tn_widget.setAutoFillBackground(True)
        # self.tn_widget.setMinimumWidth(160)
        # self.tn_widget.setMinimumWidth(128)
        self.tn_widget.setMinimumWidth(64)
        self.tn_widget.setContentsMargins(0,0,0,0)
        # self.tn_widget.setStyleSheet(
        #     """QLabel{ color: #f3f6fb; background-color: #222222; font-weight: 600; font-size: 9px; }""")
        self.tn_widget.setStyleSheet("""background-color: #222222;""")
        self.tn_widget.horizontalHeader().setHighlightSections(False)
        self.tn_widget.verticalHeader().setHighlightSections(False)
        self.tn_widget.setFocusPolicy(Qt.NoFocus)
        self.tn_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self.tn_widget.setRowCount(2)
        self.tn_widget.setColumnCount(1)
        self.vw1 = VWidget(self.tn_tra_lab, self.w_tn_tra)
        self.vw1.setStyleSheet("background-color: #222222;")
        self.vw2 = VWidget(self.tn_ref_lab, self.tn_ref)
        self.vw2.setStyleSheet("background-color: #222222;")
        self.tn_widget.setCellWidget(0, 0, self.vw1)
        self.tn_widget.setCellWidget(1, 0, self.vw2)
        self.tn_widget.setItem(0, 0, QTableWidgetItem())
        self.tn_widget.setItem(1, 0, QTableWidgetItem())
        self.tn_widget.verticalHeader().setVisible(False)
        self.tn_widget.horizontalHeader().setVisible(False)
        self.tn_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tn_widget.setShowGrid(False)
        v_header = self.tn_widget.verticalHeader()
        h_header = self.tn_widget.horizontalHeader()
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        # h_header.setSectionResizeMode(1, QHeaderView.Stretch)

        # vbl = VBL(self.tn_table, hw)
        # vbl.setSpacing(0)
        # self.tn_widget.setLayout(vbl)

        ####

        # path = os.path.join(get_appdir(), 'resources', 'x_reticle.png')
        #
        # self.tn_reticle1 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle1.setLayout(layout)
        # self.reticle1 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle1.layout().addWidget(self.tn_ms0,0,0)
        # self.tn_reticle1.layout().addWidget(self.reticle1,0,0)
        #
        # self.tn_reticle2 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle2.setLayout(layout)
        # self.reticle2 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle2.layout().addWidget(self.tn_ms1,0,0)
        # self.tn_reticle2.layout().addWidget(self.reticle2,0,0)
        #
        # self.tn_reticle3 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle3.setLayout(layout)
        # self.reticle3 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle3.layout().addWidget(self.tn_ms2,0,0)
        # self.tn_reticle3.layout().addWidget(self.reticle3,0,0)
        #
        # self.tn_reticle4 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle4.setLayout(layout)
        # self.reticle4 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle4.layout().addWidget(self.tn_ms3,0,0)
        # self.tn_reticle4.layout().addWidget(self.reticle4,0,0)

        self.ms_table = QTableWidget()
        self.ms_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.tn_ms0 = CorrSignalThumbnail(self, name='ms0')
        self.tn_ms1 = CorrSignalThumbnail(self, name='ms1')
        self.tn_ms2 = CorrSignalThumbnail(self, name='ms2')
        self.tn_ms3 = CorrSignalThumbnail(self, name='ms3')
        self.msList = [self.tn_ms0, self.tn_ms1, self.tn_ms2, self.tn_ms3]
        self.tn_ms0.set_no_image()
        self.tn_ms1.set_no_image()
        self.tn_ms2.set_no_image()
        self.tn_ms3.set_no_image()

        self.ms_table.setAutoFillBackground(True)
        self.ms_table.setContentsMargins(0,0,0,0)
        self.ms_table.setStyleSheet(
            """QLabel{ color: #ede9e8; background-color: #222222; font-weight: 600; font-size: 9px; } QTableWidget{background-color: #222222;}""")
        self.ms_table.horizontalHeader().setHighlightSections(False)
        self.ms_table.verticalHeader().setHighlightSections(False)
        self.ms_table.setFocusPolicy(Qt.NoFocus)
        self.ms_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.ms_table.setRowCount(4)
        self.ms_table.setColumnCount(1)
        self.ms_table.setCellWidget(0,0, self.tn_ms0)
        self.ms_table.setCellWidget(1,0, self.tn_ms1)
        self.ms_table.setCellWidget(2,0, self.tn_ms2)
        self.ms_table.setCellWidget(3,0, self.tn_ms3)
        self.ms_table.setItem(0, 0, QTableWidgetItem())
        self.ms_table.setItem(1, 0, QTableWidgetItem())
        self.ms_table.setItem(2, 0, QTableWidgetItem())
        self.ms_table.setItem(3, 0, QTableWidgetItem())
        self.ms_table.verticalHeader().setVisible(False)
        self.ms_table.horizontalHeader().setVisible(False)
        self.ms_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ms_table.setShowGrid(True)
        v_header = self.ms_table.verticalHeader()
        h_header = self.ms_table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        v_header.setSectionResizeMode(2, QHeaderView.Stretch)
        v_header.setSectionResizeMode(3, QHeaderView.Stretch)

        self.toggleMatches = QPushButton()
        self.toggleMatches.setIcon(qta.icon('mdi.toggle-switch-off', color=cfg.ICON_COLOR))
        self.toggleMatches.setFixedSize(20, 14)
        self.toggleMatches.setIconSize(QSize(20, 20))

        def fn_stop_playing():
            self.matchPlayTimer.stop()
            self._btn_playMatchTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))

        self.toggleMatches.clicked.connect(fn_stop_playing)
        self.toggleMatches.clicked.connect(self.fn_toggleTargKarg)

        self.matches_tn0 = ThumbnailFast(self, name='match0')
        self.matches_tn1 = ThumbnailFast(self, name='match1')
        self.matches_tn2 = ThumbnailFast(self, name='match2')
        self.matches_tn3 = ThumbnailFast(self, name='match3')
        self.match_thumbnails = [self.matches_tn0, self.matches_tn1, self.matches_tn2, self.matches_tn3]

        self.ktarg_table = QTableWidget()
        self.ktarg_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.ktarg_table.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        # self.ktarg_table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.ktarg_table.setAutoFillBackground(True)
        # self.ktarg_table.setMinimumWidth(64)
        # self.ktarg_table.setMaximumWidth(200)
        self.ktarg_table.setContentsMargins(0,0,0,0)
        self.ktarg_table.setStyleSheet(
            """QLabel{ color: #ede9e8; background-color: #222222; font-weight: 600; font-size: 9px; } QTableWidget{background-color: #222222;}""")
        self.ktarg_table.horizontalHeader().setHighlightSections(False)
        self.ktarg_table.verticalHeader().setHighlightSections(False)
        self.ktarg_table.setFocusPolicy(Qt.NoFocus)
        self.ktarg_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.ktarg_table.setRowCount(4)
        self.ktarg_table.setColumnCount(1)
        # self.ktarg_table.setColumnCount(2)
        self.ktarg_table.setCellWidget(0, 0, self.matches_tn0)
        self.ktarg_table.setCellWidget(1, 0, self.matches_tn1)
        self.ktarg_table.setCellWidget(2, 0, self.matches_tn2)
        self.ktarg_table.setCellWidget(3, 0, self.matches_tn3)
        # self.ktarg_table.setCellWidget(0, 1, self.tn_ms0)
        # self.ktarg_table.setCellWidget(1, 1, self.tn_ms1)
        # self.ktarg_table.setCellWidget(2, 1, self.tn_ms2)
        # self.ktarg_table.setCellWidget(3, 1, self.tn_ms3)
        self.ktarg_table.setItem(0, 0, QTableWidgetItem())
        self.ktarg_table.setItem(1, 0, QTableWidgetItem())
        self.ktarg_table.setItem(2, 0, QTableWidgetItem())
        self.ktarg_table.setItem(3, 0, QTableWidgetItem())
        # self.ktarg_table.setItem(0, 1, QTableWidgetItem())
        # self.ktarg_table.setItem(1, 1, QTableWidgetItem())
        # self.ktarg_table.setItem(2, 1, QTableWidgetItem())
        # self.ktarg_table.setItem(3, 1, QTableWidgetItem())
        self.ktarg_table.verticalHeader().setVisible(False)
        self.ktarg_table.horizontalHeader().setVisible(False)
        self.ktarg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ktarg_table.setShowGrid(True)
        self.ktarg_table.setVisible(getData('state,tool_windows,matches'))
        v_header = self.ktarg_table.verticalHeader()
        h_header = self.ktarg_table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        v_header.setSectionResizeMode(2, QHeaderView.Stretch)
        v_header.setSectionResizeMode(3, QHeaderView.Stretch)

        # Playback Widget

        self._btn_playMatchTimer = QPushButton()
        self._btn_playMatchTimer.setIconSize(QSize(11, 11))
        self._btn_playMatchTimer.setFixedSize(14, 14)
        self._btn_playMatchTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))

        def startStopMatchTimer():
            logger.info('')
            if cfg.mw._isProjectTab():
                cfg.data['state']['blink'] = not cfg.data['state']['blink']
                if cfg.data['state']['blink']:
                    self.matchPlayTimer.start()
                    self._btn_playMatchTimer.setIcon(qta.icon('fa.pause', color=cfg.ICON_COLOR))
                else:
                    self.matchPlayTimer.stop()
                    self._btn_playMatchTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        self._btn_playMatchTimer.clicked.connect(startStopMatchTimer)

        self.matchPlayTimer = QTimer(self)
        self.matchPlayTimer.setInterval(500)
        self.matchPlayTimer.timeout.connect(self.fn_toggleTargKarg)

        self.labMatches = QLabel('Auto-toggle:')
        self.labMatches.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.labMatches.setAlignment(Qt.AlignRight)
        self.labMatches.setFixedHeight(14)
        self.labMatches.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #222222;')

        self.labMatchesTog = QLabel('Toggle:')
        self.labMatchesTog.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.labMatchesTog.setAlignment(Qt.AlignRight)
        self.labMatchesTog.setFixedHeight(14)
        self.labMatchesTog.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #222222;')

        self.mwTitle = HWidget(self.labMatches, self._btn_playMatchTimer, self.labMatchesTog, self.toggleMatches)
        self.mwTitle.layout.setAlignment(Qt.AlignRight)
        self.mwTitle.layout.setSpacing(4)
        self.mwTitle.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #222222;')


        hw = HWidget(self.ktarg_table, self.ms_table)
        hw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.match_widget = VWidget(self.mwTitle, hw)
        self.match_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Warnings

        w = QWidget()
        # vbl = VBL(self.w_ng_extended_toolbar, self.w_section_label_header, self.shaderToolbar, self.ng_widget)
        vbl = VBL(self.w_section_label_header, self.ng_widget)
        vbl.setSpacing(0)
        vbl.setContentsMargins(0,0,0,0)
        w.setLayout(vbl)
        self.ng_widget_container = HWidget(self.ngVertLab, w, self.sideSliders)
        self.ng_widget_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.warning_cafm = WarningNotice(self, 'The cumulative affine for this section no \n'
                                                'longer comports with the displayed alignment.',
                                          fixbutton=True)
        self.warning_cafm.fixbutton.clicked.connect(cfg.mw.fix_cafm)
        self.warning_cafm.hide()


        # self.gb_warnings = QGroupBox('Warnings')
        self.gb_warnings = QGroupBox("Warnings")
        self.gb_warnings.setFixedHeight(44)
        self.gb_warnings.setObjectName('gb_cpanel')
        self.vbl_wanrings = VBL()
        self.vbl_wanrings.addWidget(self.warning_cafm, alignment=Qt.AlignBottom)
        self.gb_warnings.setLayout(self.vbl_wanrings)

        self.gb_method_selection = QGroupBox("Alignment Method")
        self.gb_method_selection.setAlignment(Qt.AlignBottom)
        self.gb_method_selection.setContentsMargins(0,0,0,0)
        self.gb_method_selection.setObjectName('gb_cpanel')
        self.gb_method_selection.setFixedHeight(36)
        self.gb_method_selection.setLayout(VBL(self.radioboxes_method))
        self.gb_method_selection.setStyleSheet('font-size: 11px; padding: 2px;')




        self.le_tacc_num_cores = QLineEdit()
        # self.le_tacc_num_cores.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.le_tacc_num_cores.setFixedHeight(18)
        self.le_tacc_num_cores.setFixedWidth(30)
        self.le_tacc_num_cores.setValidator(QIntValidator(1,128))
        def update_tacc_max_cores():
            logger.info('')
            n = int(self.le_tacc_num_cores.text())
            cfg.TACC_MAX_CPUS = int(n)
            cfg.main_window.tell(f"Maximum # of cores is now set to: {n}")
        self.le_tacc_num_cores.setText(str(cfg.TACC_MAX_CPUS))
        self.le_tacc_num_cores.textEdited.connect(update_tacc_max_cores)
        self.le_tacc_num_cores.returnPressed.connect(update_tacc_max_cores)

        self.le_tacc_num_scale1_cores = QLineEdit()
        # self.le_tacc_num_cores.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.le_tacc_num_scale1_cores.setFixedHeight(18)
        self.le_tacc_num_scale1_cores.setFixedWidth(30)
        self.le_tacc_num_scale1_cores.setValidator(QIntValidator(1,128))
        def update_tacc_max_scale1_cores():
            logger.info('')
            n = int(self.le_tacc_num_scale1_cores.text())
            cfg.SCALE_1_CORES_LIMIT = int(n)
            cfg.main_window.tell(f"Maximum # of cores is now set to: {n}")
        self.le_tacc_num_scale1_cores.setText(str(cfg.SCALE_1_CORES_LIMIT))
        self.le_tacc_num_scale1_cores.textEdited.connect(update_tacc_max_scale1_cores)
        self.le_tacc_num_scale1_cores.returnPressed.connect(update_tacc_max_scale1_cores)

        self.le_qtwebengine_raster_threads = QLineEdit()
        # self.le_qtwebengine_raster_threads.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.le_qtwebengine_raster_threads.setFixedHeight(18)
        self.le_qtwebengine_raster_threads.setFixedWidth(30)
        self.le_qtwebengine_raster_threads.setValidator(QIntValidator())
        def update_raster_threads():
            logger.info('')
            n = int(self.le_qtwebengine_raster_threads.text())
            cfg.QTWEBENGINE_RASTER_THREADS = n
            cfg.main_window.tell(f"# QtWebengine raster threads is now set to: {n}")
        self.le_qtwebengine_raster_threads.setText(str(cfg.QTWEBENGINE_RASTER_THREADS))
        self.le_qtwebengine_raster_threads.textEdited.connect(update_raster_threads)
        self.le_qtwebengine_raster_threads.returnPressed.connect(update_raster_threads)

        self.cb_recipe_logging = QCheckBox()
        self.cb_recipe_logging.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_recipe_logging():
            logger.info('')
            b = self.cb_recipe_logging.isChecked()
            cfg.RECIPE_LOGGING = int(b)
            cfg.main_window.tell(f"Recipe logging is now set to: {b}")
        self.cb_recipe_logging.setChecked(cfg.RECIPE_LOGGING)
        self.cb_recipe_logging.toggled.connect(update_recipe_logging)

        self.cb_dev_mode = QCheckBox()
        self.cb_dev_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_dev_mode():
            logger.info('')
            b = self.cb_dev_mode.isChecked()
            cfg.DEV_MODE = int(b)
            cfg.main_window.tell(f"Dev mode is now set to: {b}")
        self.cb_dev_mode.setChecked(cfg.DEV_MODE)
        self.cb_dev_mode.toggled.connect(update_dev_mode)

        self.cb_use_pool = QCheckBox()
        self.cb_use_pool.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_mp_mode():
            logger.info('')
            b = self.cb_use_pool.isChecked()
            cfg.USE_POOL_FOR_SWIM = int(b)
            cfg.main_window.tell(f"Multiprocessing mode is now set to: "
                                 f"{('task queue', 'pool')[b]}")
        self.cb_use_pool.setChecked(cfg.USE_POOL_FOR_SWIM)
        self.cb_use_pool.toggled.connect(update_mp_mode)

        self.w_tacc = QWidget()
        self.w_tacc.setContentsMargins(2,2,2,2)
        self.fl_tacc = QFormLayout()
        self.w_tacc.setLayout(self.fl_tacc)
        self.fl_tacc.addRow(f"Max # cores (downsampled scales)", self.le_tacc_num_cores)
        self.fl_tacc.addRow(f"Max # cores (scale 1)", self.le_tacc_num_scale1_cores)
        self.fl_tacc.addRow(f"Use mp.Pool (vs task queue)", self.cb_use_pool)
        self.fl_tacc.addRow(f"QtWebengine # raster threads", self.le_qtwebengine_raster_threads)
        self.fl_tacc.addRow(f"RECIPE_LOGGING", self.cb_recipe_logging)
        self.fl_tacc.addRow(f"DEV_MODE", self.cb_dev_mode)

        self.sideTabs = QTabWidget()
        # self.sideTabs.addTab(self.MA_stackedWidget, 'Configure')
        self.sideTabs.addTab(self.sa_lowest8, 'Worst 8 SNR')
        self.sideTabs.addTab(self.sa_details, 'Details')
        self.sideTabs.addTab(self.sa_runtimes, 'Timings')
        self.sideTabs.addTab(self.logs_widget, 'Logs')
        if is_tacc() or is_joel():
            self.sideTabs.addTab(self.w_tacc, 'Other')

        self.sideTabs.currentChanged.connect(self.onSideTabChange)

        self.gb_sideTabs = QGroupBox()
        self.gb_sideTabs.setLayout(VBL(self.sideTabs))

        # self.side_controls = VWidget(self.gb_method_selection, self.MA_stackedWidget, self.MA_controls)
        self.side_controls = VWidget(self.gb_method_selection,
                                     self.MA_stackedWidget,
                                     self.gb_sideTabs,
                                     self.gb_outputSettings,
                                     self.gb_warnings,
                                     self.MA_controls)
        self.side_controls.setMaximumWidth(340)
        self.side_controls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.side_controls.setStyleSheet("""
        QWidget{
            font-size: 10px;
        }
        QTabBar::tab {
            font-size: 9px;
            height: 12px;
            width: 64px;
            min-width: 64px;
            max-width: 64px;
            margin-bottom: 0px;
            padding-bottom: 0px;
        }
        QGroupBox {
            color: #161c20;
            border: 1px solid #161c20;
            font-size: 10px;
            /*font-weight: 600;*/
            border-radius: 2px;
            margin: 2px;
            padding: 2px;
        }
        QGroupBox:title {
            color: #161c20;
            /*font-weight:600;*/
            font-size: 9px;
            subcontrol-origin: margin;
            subcontrol-position: top center;
            margin-bottom: 16px;
        }
        """)

        self.splitterEditAlignment = QSplitter(Qt.Orientation.Horizontal)
        self.splitterEditAlignment.addWidget(self.ng_widget_container)
        self.splitterEditAlignment.addWidget(self.side_controls)

        logger.info("<<<<")


    def set_reference(self):
        if cfg.data.skipped():
            cfg.mw.warning('This section does not have a reference because it is excluded.')
            self.set_transforming()
            return
        logger.info('')
        cfg.data['state']['tra_ref_toggle'] = 0
        self.cl_ref.setChecked(True)
        self.cl_tra.setChecked(False)
        self.cl_ref.setStyleSheet('background-color: #339933; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        self.cl_tra.setStyleSheet('background-color: #222222; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        cfg.refViewer.set_layer(cfg.data.get_ref_index())
        self.sw_alignment_editor.setCurrentIndex(0)
        self.updateAnnotations()


    def set_transforming(self):
        logger.info('')
        cfg.data['state']['tra_ref_toggle'] = 1
        self.cl_tra.setChecked(True)
        self.cl_ref.setChecked(False)
        self.cl_tra.setStyleSheet('background-color: #339933; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        self.cl_ref.setStyleSheet('background-color: #222222; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        cfg.baseViewer.set_layer(cfg.data.zpos)
        self.sw_alignment_editor.setCurrentIndex(1)
        self.updateAnnotations()

    def fn_hwidgetChanged(self):
        # logger.critical('')
        #
        # # self.tn_widget.setFixedWidth(self.tn_tra.height() + 8)
        # max_w = max(self.tn_ms0.height(), self.tn_ms1.height(), self.tn_ms2.height(), self.tn_ms3.height())
        # # logger.info(f'max_w = {max_w}')
        # self.ms_widget.setMaximumWidth(max_w * 2 + 20)
        # logger.info('Resizing things, isProjectTab...')
        # h = self.wEditAlignment.height()
        # # cfg.pt.sideTabs.setFixedWidth(int(.26 * self.width()))
        # ms_w = int(h/4 + 0.5)
        # tn_w = int((h - self.tn_ref_lab.height() - self.tn_ref_lab.height()) / 2 + 0.5)
        # self.ms_widget.setFixedWidth(ms_w)
        # self.match_widget.setFixedWidth(ms_w)
        # self.tn_widget.setFixedWidth(tn_w)
        # # self.initNeuroglancer()
        # # pass
        pass


    def onSideTabChange(self):
        logger.info('')
        if self.te_logs.isVisible():
            self.refreshLogs()
        if self.sa_runtimes.isVisible():
            self.updateTimingsWidget()
        if self.sa_lowest8.isVisible():
            self.updateLowest8widget()



    def fn_toggleTargKarg(self):
        logger.info('')
        setData('state,targ_karg_toggle', 1 - getData('state,targ_karg_toggle'))
        self.toggleMatches.setIcon(qta.icon(
            ('mdi.toggle-switch', 'mdi.toggle-switch-off')[getData('state,targ_karg_toggle')], color=cfg.ICON_COLOR))
        # (self.rb_targ.setChecked, self.rb_karg.setChecked)[getData('state,targ_karg_toggle')](True)
        cfg.mw.setTargKargPixmaps()


    def setRbStackView(self):
        if DEV:
            logger.critical(caller_name())
        self.cl_ref.setChecked(True)
        self.cl_ref.setStyleSheet('background-color: #339933; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        self.cl_tra.setStyleSheet('background-color: #222222; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')


    def setRbRegionsView(self):
        if DEV:
            logger.critical(caller_name())
        self.cl_tra.setChecked(True)
        self.cl_tra.setStyleSheet('background-color: #339933; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')
        self.cl_ref.setStyleSheet('background-color: #222222; color: #ede9e8; font-size: 10px; border: 1px solid #ede9e8; font-weight: 600;')


    # def onBlinkTimer(self):
    #     if getData('state,blink'):
    #         if cfg.emViewer:
    #             cfg.emViewer.blink()

                # self.blinkCur = 1 - self.blinkCur
                # if self.blinkCur:
                #     ref_index = cfg.data.get_index(cfg.data.fn_reference())
                #     logger.info(f'ref_index = {ref_index}')
                #     cfg.emViewer.set_layer(ref_index)
                # else:
                #     cfg.emViewer.set_layer(cfg.data.zpos)

    # def stopBlinkTimer(self):
    #     setData('state,blink', False)
    #     self.blinkTimer.stop()
    #
    #
    # def blinkChanged(self):
    #     setData('state,blink', self.blinkToggle.isChecked())
    #     if getData('state,blink'):
    #         self.blinkTimer.start()
    #     else:
    #         self.blinkTimer.stop()

    # def uiUpdateToggleChanged(self):
    #     setData('state,auto_update_ui', self.uiUpdateToggle.isChecked())



    def refreshLogs(self):
        logger.info('')
        logs_path = os.path.join(cfg.data.dest(), 'logs', 'recipemaker.log')
        if os.path.exists(logs_path):
            with open(logs_path, 'r') as f:
                # lines = f.readlines()
                text = f.read()
        else:
            text = 'No Log To Show.'
        self.te_logs.setText(text)
        self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())

    def updateAutoSwimRegions(self):
        logger.info('')
        if cfg.data.current_method == 'grid-custom':
            cfg.data.grid_custom_regions = [self.Q1.isClicked, self.Q2.isClicked, self.Q3.isClicked, self.Q4.isClicked]
        self.updateAnnotations()

    def updateMethodSelectWidget(self, soft=False):
        caller = inspect.stack()[1].function
        cur_index = self.MA_stackedWidget.currentIndex()
        logger.info(f'caller={caller}, soft={soft}, cur_index={cur_index}')
        # logger.critical(f'cfg.data.current_method = {cfg.data.current_method}')

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


    def updateAnnotations(self):
        if DEV:
            logger.info(f'[{caller_name()}] Updating annotations...')

        if cfg.data['state']['tra_ref_toggle'] == 1:
            cfg.baseViewer.drawSWIMwindow()
        else:
            cfg.refViewer.drawSWIMwindow()
        if cfg.mw.dw_thumbs.isVisible():
            self.tn_ref.update()
            self.tn_tra.update()


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
            logger.info('Setting neuroglancer layout to %s' % choice)
            # setData('ui,ng_layout', choice)
            setData('state,ng_layout', choice)
            cfg.mw.tell(f'Neuroglancer Layout: {choice}')
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
                self.viewer.initViewer()
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

    def updateCursor(self):
        QApplication.restoreOverrideCursor()
        # self.msg_MAinstruct.setText("Toggle 'Mode' to select manual correspondence points")

        if cfg.data['state']['current_tab'] == 1:
            # if self.tgl_alignMethod.isChecked():
            if cfg.data.method() in ('manual-hint', 'manual-strict'):
                pixmap = QPixmap('src/resources/cursor_circle.png')
                cursor = QCursor(pixmap.scaled(QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                QApplication.setOverrideCursor(cursor)

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
    #     path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'img_staged',str(cfg.data.zpos), dt)
    #     if not os.path.isdir(path):
    #         os.mkdir(path)
    #     file = cfg.data.filename()
    #     out = os.path.join(path, os.path.basename(filrestoreManAlignPtse))
    #     logger.critical('Copying FROM %s' % str(file))
    #     logger.critical('Copying TO %s' % str(out))
    #     shutil.copyfile(file, out)


    def validate_MA_points(self):
        # if len(cfg.refViewer.pts.keys()) >= 3:
        if cfg.refViewer.pts.keys() == cfg.baseViewer.pts.keys():
            return True
        return False


    @Slot()
    def dataUpdateMA(self):
        # if DEV:
        #     logger.critical(f"[DEV] called by {caller_name()}")

        #0526 set skipped overlay

        # caller = inspect.stack()[1].function

        # logger.info(f'cfg.data.skipped() = {cfg.data.skipped()} , cfg.data.has_reference() = {cfg.data.has_reference()}')
        # if cfg.data.skipped():
        #     txt = '\n'.join(textwrap.wrap('X EXCLUDED - %s' % cfg.data.name_base(), width=35))
        #     self.MA_gl_overlay._overlayLab.setText(txt)
        #     self.MA_gl_overlay.show()
        # elif not cfg.data.has_reference():
        #     self.MA_gl_overlay.setText('This Section Has No Reference')
        #     self.MA_gl_overlay.show()
        # else:
        #     self.MA_gl_overlay.hide()
        #     self.MA_gl_overlay.setText('')


        # self.msg_MAinstruct.setVisible(cfg.data.current_method not in ('grid-default', 'grid-custom'))

        self.spinbox_whitening.setValue(float(cfg.data.whitening()))

        img_siz = cfg.data.image_size()
        img_w = int(img_siz[0])

        # Update line edit widgets validator
        # Update slider maximum and minimums
        # Update widgets w/ data

        self.AS_SWIM_window_le.setValidator(QIntValidator(64, img_w))
        self.AS_SWIM_window_le.setText(str(cfg.data.swim_1x1_custom_px()[0]))
        self.slider_AS_SWIM_window.setMaximum(img_w)
        self.slider_AS_SWIM_window.setValue(int(cfg.data.swim_1x1_custom_px()[0]))

        self.AS_2x2_SWIM_window_le.setValidator(QIntValidator(64, int(img_w / 2)))
        self.AS_2x2_SWIM_window_le.setText(str(cfg.data.swim_2x2_custom_px()[0]))
        self.slider_AS_2x2_SWIM_window.setMaximum(int(img_w / 2))
        self.slider_AS_2x2_SWIM_window.setValue(int(cfg.data.swim_2x2_custom_px()[0]))

        self.MA_SWIM_window_le.setValidator(QIntValidator(64, img_w))
        self.MA_SWIM_window_le.setText(str(cfg.data.manual_swim_window_px()))
        self.slider_MA_SWIM_window.setMaximum(img_w)
        self.slider_MA_SWIM_window.setValue(int(cfg.data.manual_swim_window_px()))

        self.spinbox_swim_iters.setValue(int(cfg.data.swim_iterations()))

        method = cfg.data.current_method
        if method == 'grid-custom':
            cfg.mw._btn_alignOne.setEnabled(True)
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
        self.update_MA_list_widgets()
        self.cb_clobber.setChecked(cfg.data.clobber())
        self.sb_clobber_pixels.setValue(int(cfg.data.clobber_px()))

        # self.cb_keep_swim_templates.setChecked((cfg.data.targ == True) or (cfg.data.karg == True))
        try:
            self.updateMethodSelectWidget(soft=True)
        except:
            print_exception()


        # if self.match_widget.isVisible():
        if cfg.mw.dw_matches.isVisible():
            cfg.mw.setTargKargPixmaps()
            cfg.mw.updateCorrSignalsDrawer()

        if self.te_logs.isVisible():
            self.refreshLogs()

        if cfg.mw.dw_thumbs.isVisible():
            self.tn_ref.update()
            self.tn_tra.update()


        # logger.critical('<<<< dataUpdateMA <<<<')


    def updateEnabledButtonsMA(self):
        method = cfg.data.current_method
        sec = cfg.data.zpos
        realign_tip = 'SWIM align section #%d and generate an image' % sec
        if method == 'grid-custom':
            cfg.mw._btn_alignOne.setEnabled(True)
            if sum(cfg.data.grid_custom_regions) >= 3:
                cfg.mw._btn_alignOne.setEnabled(True)
                realign_tip = 'SWIM align section #%d using custom grid method' % sec
            else:
                cfg.mw._btn_alignOne.setEnabled(False)
                realign_tip = 'SWIM alignment requires at least three regions to form an affine'
        elif method == 'grid-default':
            cfg.mw._btn_alignOne.setEnabled(True)
            realign_tip = 'SWIM align section #%d using default grid regions'
        elif method in ('manual-hint', 'manual-strict'):
            if (len(cfg.data.manpoints()['ref']) >= 3) and (len(cfg.data.manpoints()['base']) >= 3):
                cfg.mw._btn_alignOne.setEnabled(True)
                realign_tip = 'SWIM align section #%d using manual correspondence regions method ' \
                              'and generate an image' % sec
            else:
                cfg.mw._btn_alignOne.setEnabled(False)
                realign_tip = 'SWIM alignment requires at least three regions to form an affine'

        cfg.mw._btn_alignOne.setToolTip('\n'.join(textwrap.wrap(realign_tip, width=35)))

    def update_MA_list_widgets(self):
        if self._tabs.currentIndex() == 1:
            # if cfg.data.current_method in ('manual-hint', 'manual-strict'):
            if self.method_rb2.isChecked():
                logger.info('')
                # self.setUpdatesEnabled(False)
                self.updateEnabledButtonsMA() #0610+
                self.update_MA_list_base()
                self.update_MA_list_ref()
                self.update_MA_list_count_labels()
                # self.setUpdatesEnabled(True)

    def update_MA_list_ref(self):
        logger.info('')
        # cfg.refViewer.pts = {}
        self.MA_ptsListWidget_ref.clear()
        self.MA_ptsListWidget_ref.update()

        n = 0
        # for i, key in enumerate(cfg.refViewer.pts.keys()):
        for i, p in enumerate(cfg.refViewer.pts):
            _, y, x = p.point.tolist()
            item = QListWidgetItem('%d: x=%.1f, y=%.1f' % (i, x, y))
            # item.setBackground(QColor(self.mp_colors[n]))
            item.setBackground(QColor(cfg.glob_colors[i]))
            item.setForeground(QColor('#141414'))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.MA_ptsListWidget_ref.addItem(item)
            n += 1

    def update_MA_list_base(self):
        logger.info('')
        # cfg.baseViewer.pts = {}
        self.MA_ptsListWidget_base.clear()
        self.MA_ptsListWidget_base.update()
        n = 0
        # for i, key in enumerate(cfg.baseViewer.pts.keys()):
        for i, p in enumerate(cfg.baseViewer.pts):
            _, x, y = p.point.tolist()
            item = QListWidgetItem('%d: x=%.1f, y=%.1f' % (i, x, y))
            # item.setBackground(QColor(self.mp_colors[n]))
            item.setBackground(QColor(cfg.glob_colors[i]))
            item.setForeground(QColor('#141414'))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.MA_ptsListWidget_base.addItem(item)
            n += 1

    def update_MA_list_count_labels(self):
        if len(cfg.data.manpoints()['base']) < 3:
            self.MA_baseNextColorTxt.setText('Next Color:   ')
            self.MA_baseNextColorLab.setStyleSheet(f'''background-color: {cfg.baseViewer.getNextUnusedColor()}''')
            self.MA_baseNextColorLab.show()
        else:
            self.MA_baseNextColorTxt.setText('Complete!')
            self.MA_baseNextColorLab.hide()
        if len(cfg.data.manpoints()['ref']) < 3:
            self.MA_refNextColorTxt.setText('Next Color:   ')
            self.MA_refNextColorLab.setStyleSheet(f'''background-color: {cfg.refViewer.getNextUnusedColor()}''')
            self.MA_refNextColorLab.show()
        else:
            self.MA_refNextColorTxt.setText('Complete!')
            self.MA_refNextColorLab.hide()


    # def update_MA_ref_state(self):
    #     caller = inspect.stack()[1].function
    #     # curframe = inspect.currentframe()
    #     # calframe = inspect.getouterframes(curframe, 2)
    #     # calname = str(calframe[1][3])
    #     # logger.info('Caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
    #     if caller != 'on_state_change':
    #         if self.MA_webengine_ref.isVisible():
    #             if cfg.baseViewer.state.cross_section_scale:
    #                 # if cfg.baseViewer.state.cross_section_scale < 10_000:
    #                 #     if cfg.baseViewer.state.cross_section_scale != 1.0:
    #                 pos = cfg.baseViewer.state.position
    #                 zoom = cfg.baseViewer.state.cross_section_scale
    #                 if isinstance(pos, np.ndarray) or isinstance(zoom, np.ndarray):
    #                     state = copy.deepcopy(cfg.refViewer.state)
    #                     if isinstance(pos, np.ndarray):
    #                         state.position = cfg.baseViewer.state.position
    #                     if isinstance(zoom, float):
    #                         # if cfg.baseViewer.state.cross_section_scale < 10_000:
    #                         if cfg.baseViewer.state.cross_section_scale < 100:
    #                             # if cfg.baseViewer.state.cross_section_scale < cfg.refViewer.cs_scale:
    #                             # if cfg.baseViewer.state.cross_section_scale < 1: # solves runaway zoom effect
    #                             if cfg.baseViewer.state.cross_section_scale != 1.0:
    #                                 logger.info(f'Updating ref viewer state. OLD cs_scale: {state.cross_section_scale}')
    #                                 logger.info(
    #                                     f'Updating ref viewer state. NEW cs_scale: {cfg.baseViewer.state.cross_section_scale}')
    #                                 state.cross_section_scale = cfg.baseViewer.state.cross_section_scale
    #                     cfg.refViewer.set_state(state)

    # def update_MA_base_state(self):
    #     caller = inspect.stack()[1].function
    #     # curframe = inspect.currentframe()
    #     # calframe = inspect.getouterframes(curframe, 2)
    #     # calname = str(calframe[1][3])
    #     # logger.info('Caller: %s, calname: %s, sender: %s' % (caller, calname, self.sender()))
    #     if caller != 'on_state_change':
    #         if self.MA_webengine_base.isVisible():
    #             if cfg.refViewer.state.cross_section_scale:
    #                 # if cfg.refViewer.state.cross_section_scale < 10_000:
    #                 #     if cfg.refViewer.state.cross_section_scale != 1.0:
    #                 pos = cfg.refViewer.state.position
    #                 zoom = cfg.refViewer.state.cross_section_scale
    #
    #                 if isinstance(pos, np.ndarray) or isinstance(zoom, np.ndarray):
    #                     state = copy.deepcopy(cfg.baseViewer.state)
    #                     if isinstance(pos, np.ndarray):
    #                         state.position = cfg.refViewer.state.position
    #                     if isinstance(zoom, float):
    #                         # if cfg.refViewer.state.cross_section_scale < 10_000:
    #                         if cfg.refViewer.state.cross_section_scale < 100:
    #                             # if cfg.refViewer.state.cross_section_scale < cfg.refViewer.cs_scale:
    #                             # if cfg.refViewer.state.cross_section_scale < 1: # solves runaway zoom effect
    #                             if cfg.refViewer.state.cross_section_scale != 1.0:
    #                                 logger.info(
    #                                     f'Updating base viewer state. OLD cs_scale: {state.cross_section_scale}')
    #                                 logger.info(
    #                                     f'Updating base viewer state. NEW cs_scale: {cfg.refViewer.state.cross_section_scale}')
    #                                 state.cross_section_scale = cfg.refViewer.state.cross_section_scale
    #                     cfg.baseViewer.set_state(state)


    def completeDeleteMp(self):
        logger.info('')
        try:
            self.deleteAllMp()
            self.update_MA_list_widgets()
            self.updateAnnotations()
            cfg.mw.setTargKargPixmaps()
            cfg.mw.updateCorrSignalsDrawer()
        except:
            print_exception()


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
        # cfg.refViewer.drawSWIMwindow()
        self.updateAnnotations()
        self.updateEnabledButtonsMA()
        self.update_MA_list_widgets()
        cfg.mw.setTargKargPixmaps()
        cfg.mw.updateCorrSignalsDrawer()

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
        # cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        # cfg.baseViewer.drawSWIMwindow()
        self.updateAnnotations()
        self.updateEnabledButtonsMA()
        self.update_MA_list_widgets()
        cfg.mw.setTargKargPixmaps()
        cfg.mw.updateCorrSignalsDrawer()

    def deleteAllMpRef(self):
        logger.info('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        cfg.refViewer.pts.clear()
        self.MA_ptsListWidget_ref.clear()
        # cfg.refViewer.draw_point_annotations()
        cfg.refViewer.applyMps()
        # cfg.baseViewer.applyMps()
        # cfg.refViewer.drawSWIMwindow()
        self.updateAnnotations()
        self.updateEnabledButtonsMA()
        self.update_MA_list_widgets()
        cfg.mw.setTargKargPixmaps()
        cfg.mw.updateCorrSignalsDrawer()

    def deleteAllMpBase(self):
        logger.info('Deleting All Base Image Manual Correspondence Points from Buffer...')
        cfg.main_window.hud.post('Deleting All Base Image Manual Correspondence Points from Buffer...')
        cfg.baseViewer.pts.clear()
        self.MA_ptsListWidget_base.clear()
        # cfg.refViewer.applyMps()
        cfg.baseViewer.applyMps()
        # cfg.baseViewer.drawSWIMwindow()
        self.updateAnnotations()
        self.updateEnabledButtonsMA()
        self.update_MA_list_widgets()
        cfg.mw.setTargKargPixmaps()
        cfg.mw.updateCorrSignalsDrawer()

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
        # cfg.refViewer.undrawSWIMwindows()
        # cfg.baseViewer.undrawSWIMwindows()
        self.updateAnnotations()
        self.updateEnabledButtonsMA()
        self.update_MA_list_widgets()
        cfg.mw.setTargKargPixmaps()
        cfg.mw.updateCorrSignalsDrawer()

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
            # self.deleteMpRefAction = QAction('Delete')
            # # self.deleteMpRefAction.setStatusTip('Delete this manual correspondence point')
            # self.deleteMpRefAction.triggered.connect(self.deleteMpRef)
            # menu.addAction(self.deleteMpRefAction)
            self.deleteAllMpRefAction = QAction('Clear All Reference Regions')
            # self.deleteAllMpRefAction.setStatusTip('Delete all fn_reference manual correspondence points')
            self.deleteAllMpRefAction.triggered.connect(self.deleteAllMpRef)
            menu.addAction(self.deleteAllMpRefAction)
            self.deleteAllPtsAction0 = QAction('Clear All Regions')
            # self.deleteAllPtsAction0.setStatusTip('Delete all manual correspondence points')
            self.deleteAllPtsAction0.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction0)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        elif event.type() == QEvent.ContextMenu and source is self.MA_ptsListWidget_base:
            menu = QMenu()
            # self.deleteMpBaseAction = QAction('Delete')
            # # self.deleteMpBaseAction.setStatusTip('Delete this manual correspondence point')
            # self.deleteMpBaseAction.triggered.connect(self.deleteMpBase)
            # menu.addAction(self.deleteMpBaseAction)
            self.deleteAllMpBaseAction = QAction('Clear All Transforming Regions')
            # self.deleteAllMpBaseAction.setStatusTip('Delete all base manual correspondence points')
            self.deleteAllMpBaseAction.triggered.connect(self.deleteAllMpBase)
            menu.addAction(self.deleteAllMpBaseAction)
            self.deleteAllPtsAction1 = QAction('Clear All Regions')
            # self.deleteAllPtsAction1.setStatusTip('Delete all manual correspondence points')
            self.deleteAllPtsAction1.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction1)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        return super().eventFilter(source, event)



    # def updateUISpacing(self):
    #     isUiControls = getOpt('neuroglancer,SHOW_UI_CONTROLS')
    #     self.spreadW.setVisible(isUiControls)
    #     if isUiControls:
    #         self.spreadW2.setFixedSize(96, 1)
    #         self.spreadW3.setFixedSize(40, 1)
    #     else:
    #         self.spreadW2.setFixedSize(10, 1)
    #         self.spreadW3.setFixedSize(10, 1)

    def disableZoomSlider(self):
        self._allow_zoom_change = False

    def enableZoomSlider(self):
        self._allow_zoom_change = True

    def setZoomSlider(self):
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        if caller == 'main':
        # logger.critical(f'Setting Zoom to {cfg.emViewer.zoom() / 1}...')
            if self._allow_zoom_change:
                # caller = inspect.stack()[1].function
                if cfg.data['state']['current_tab'] == 1:
                    zoom = cfg.baseViewer.zoom()
                else:
                    zoom = cfg.emViewer.zoom()

                if zoom == 0:
                    return
                # logger.critical('Setting slider value (zoom: %g, caller: %s)' % (zoom, caller))
                # val =
                # if val in range(-2147483648, 2147483647):
                try:
                    self.zoomSlider.setValue(1/zoom)
                except:
                    print_exception()
                    logger.warning(f"zoom = {zoom}")
                # self.zoomSlider.setValue(zoom)
                self._allow_zoom_change = True

    def onZoomSlider(self):
        caller = inspect.stack()[1].function
        if caller not in ('slotUpdateZoomSlider', 'setValue'):  # Original #0314
            val = 1 / self.zoomSlider.value()
            if cfg.data['state']['current_tab'] == 1:
                if abs(cfg.baseViewer.state.cross_section_scale - val) > .0001:
                    cfg.refViewer.set_zoom(val)
                    cfg.baseViewer.set_zoom(val)
            else:
                try:
                    if abs(cfg.emViewer.state.cross_section_scale - val) > .0001:
                        cfg.emViewer.set_zoom(val)
                except:
                    print_exception()


    def slotUpdateZoomSlider(self):
        # Lets only care about REF <--> slider
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if cfg.data['state']['current_tab'] == 1:
                val = cfg.baseViewer.state.cross_section_scale
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

    # def setZmag(self, val):
    #     logger.info(f'zpos={cfg.data.zpos} Setting Z-mag to {val} for all viewers...')
    #     if cfg.mw._isProjectTab():
    #         try:
    #             if cfg.refViewer:
    #                 cfg.refViewer.set_zmag(10)
    #         except:
    #             print_exception()
    #         try:
    #             if cfg.baseViewer:
    #                 cfg.baseViewer.set_zmag(10)
    #         except:
    #             print_exception()
    #         try:
    #             if cfg.emViewer:
    #                 cfg.emViewer.set_zmag(10)
    #         except:
    #             print_exception()

    def onSliderZmag(self):

        caller = inspect.stack()[1].function
        logger.info('caller: %s' % caller)
        try:
            # for viewer in cfg.main_window.get_viewers():
            val = self.ZdisplaySlider.value()
            if cfg.data['state']['current_tab'] == 1:
                state = copy.deepcopy(cfg.refViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.refViewer.set_state(state)
                state = copy.deepcopy(cfg.baseViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.baseViewer.set_state(state)
                # state = copy.deepcopy(cfg.stageViewer.state)
                # state.relative_display_scales = {'z': val}
                # cfg.baseViewer.set_state(state)

            else:
                # logger.info('val = %d' % val)
                state = copy.deepcopy(cfg.emViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.emViewer.set_state(state)
            cfg.main_window.update()
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

    @Slot()
    def async_table_load(self):
        self.loadTable.emit()

    def initUI_table(self):
        '''Layer View Widget'''
        logger.info('')
        self.project_table = ProjectTable(self)
        # self.project_table.setStyleSheet("background-color: #222222; color: #f3f6fb;")
        self.project_table.setStyleSheet("color: #f3f6fb;")
        # self.project_table.setObjectName('project_table')
        vbl = VBL()
        vbl.addWidget(self.project_table)
        self.label_overview = VerticalLabel('Project Data Table View')
        self.label_overview.setStyleSheet("""
        background-color: #161c20;
        color: #ede9e8;""")
        hbl = HBL()
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.table_container.setLayout(hbl)
        self.table_container.setStyleSheet("background-color: #222222; color: #f3f6fb;")
        # self.project_table.initTableData()

        # self.project_table.initTableData()

    def updateTreeWidget(self):
        # cfg.mw.statusBar.showMessage('Loading data into tree view...')
        # time consuming - refactor?
        cfg.mw.tell('Loading data into tree view...')
        self.treeview_model.load(cfg.data.to_dict())
        # self.treeview.setModel(self.treeview_model)
        self.treeview.header().resizeSection(0, 340)
        # self.treeview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.treeview.expandAll()
        # self.treeview.update()

    #0731
    def get_treeview_data(self, index=None):
        # logger.info(f'arg passed {index}')
        if index == None:
            index = self.treeview.selectedIndexes()[0]
        # logger.info(f'index is {index}')
        cur_key = index.data()
        par_key = index.parent().data()
        # print(f"cur_key = {cur_key}")
        # print(f"par_key = {par_key}")
        if par_key == 'stack':
            logger.info(f"setting z-position to {cur_key}")
            cfg.mw.setZpos(int(cur_key))


    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self.treeview = QTreeView()
        self.treeview.expanded.connect(lambda index: self.get_treeview_data(index))


        # self.treeview.setStyleSheet("color: #161c20;")
        self.treeview.setAnimated(True)
        self.treeview.header().resizeSection(0, 340)
        self.treeview.setIndentation(14)
        self.treeview.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.treeview.header().resizeSection(0, 380)
        # self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.treeview_model = JsonModel()
        # self.treeview_model.signals.dataModelChanged.connect(self.load_data_from_treeview) #0716-
        self.treeview.setModel(self.treeview_model)
        self.treeview.setAlternatingRowColors(True)


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

        self.btnCurSection.setToolTip('Jump to the data for current section and scale_key')
        self.btnCurSection.setStyleSheet('font-size: 10px;')
        self.btnCurSection.setFixedSize(80, 18)
        self.btnCurSection.clicked.connect(fn)

        def fn():
            self.updateTreeWidget()
            self.treeview.collapseAll()

        self.btnReloadDataTree = QPushButton('Reload')
        self.btnReloadDataTree.setToolTip('Jump to the data for current section and scale_key')
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
                scale = cfg.data.scale_key
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
                    elif opt == 'Meta':
                        keys.extend(['alignment', 'meta'])
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
        #         requested_scale = cfg.data.scale_key
        #     self.updateTreeWidget()
        #     self.treeview_model.jumpToSection(sec=requested, s=get_scale_key(requested_scale))
        self.le_tree_jumpToSec.returnPressed.connect(goToData)

        self.combo_data_tree = QComboBox()
        self.combo_data_tree.setFixedWidth(120)
        # items = ['--', 'Results', 'SWIM Arguments', 'SWIM Out', 'SWIM Err', 'SWIM Settings', 'MIR Arguments', 'MIR Tokens',
        #          'Alignment History']
        # items = ['--', 'Results', 'Alignment History', 'Method Results', 'SWIM Settings', 'SWIM Out',
        #          'SWIM Err', 'SWIM Arguments', 'MIR Err', 'MIR Out']
        items = ['--', 'Results', 'Alignment History', 'Method Results', 'SWIM Settings', 'Meta']
        self.combo_data_tree.addItems(items)

        self.btn_tree_go = QPushButton('Go')
        self.btn_tree_go.setStyleSheet('font-size: 10px;')
        self.btn_tree_go.clicked.connect(goToData)
        self.btn_tree_go.setFixedSize(28, 18)

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
        btns = QWidget()
        btns.setContentsMargins(2, 2, 2, 2)
        btns.setFixedHeight(24)
        btns.setLayout(hbl)
        btns.setStyleSheet("font-size: 10px;")

        self.treeHbl = HBL()
        self.treeHbl.setSpacing(0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setStyleSheet("""background-color: #161c20; color: #ede9e8;""")
        self.treeHbl.addWidget(lab)
        self.treeHbl.addWidget(VWidget(self.treeview, btns))
        self._wdg_treeview.setLayout(self.treeHbl)

    def initUI_plot(self):
        '''SNR Plot Widget'''
        logger.info('')

        self.snr_plot = SnrPlot()
        lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#ede9e8', font_size=13)
        lab_Xaxis = QLabel('Serial Section #')
        lab_Xaxis.setStyleSheet("font-size: 13px;")
        lab_Xaxis.setAlignment(Qt.AlignHCenter)
        self.w_snr_plot = VWidget(HWidget(lab_yaxis, self.snr_plot), lab_Xaxis)
        self.w_snr_plot.setStyleSheet('background-color: #222222; font-weight: 600; font-size: 14px; color: #ede9e8;')

        self.dSnr_plot = SnrPlot(dock=True)
        # lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#ede9e8', font_size=14)

        # self.w_dSnr_plot = VWidget(HWidget(lab_yaxis, self.dSnr_plot), lab_Xaxis)
        # self.w_dSnr_plot = VWidget(self.dSnr_plot, lab_Xaxis)
        # self.w_dSnr_plot = self.dSnr_plot
        # self.w_dSnr_plot.setStyleSheet('background-color: #222222; font-weight: 600; font-size: 14px; color: #ede9e8;')
        self.dSnr_plot.setStyleSheet('background-color: #222222; font-weight: 600; font-size: 12px; color: #ede9e8;')

        # cfg.mw.dw_snr.setWidget(self.w_dSnr_plot)
        cfg.mw.dw_snr.setWidget(self.dSnr_plot)



    def initTabs(self):
        '''Tab Widget'''
        logger.info('')
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
        QTabBar::tab {
            padding-top: 1px;
            padding-bottom: 1px;
            height: 16px;            
            font-size: 11px;
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
        self._tabs.setDocumentMode(True) #When this property is set the tab widget frame is not rendered.
        self._tabs.setTabPosition(QTabWidget.South)
        # self._tabs.setTabShape(QTabWidget.Triangular)
        self._tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.setTabsClosable(False)
        self._tabs.setObjectName('project_tabs')
        # self._tabs.addTab(self.splitter_ngPlusSideControls, ' 3DEM ')
        # self._tabs.addTab(VWidget(self.w_ng_extended_toolbar, self.shaderToolbar, self.webengine), 'Neuroglancer')
        self._tabs.addTab(VWidget(self.w_ng_extended_toolbar, self.shaderToolbar, self.webengine), 'View Alignment')
        self._tabs.addTab(self.splitterEditAlignment, 'Edit Alignment')

        # self._tabs.addTab(self.wEditAlignment, ' 3DEM ')
        self._tabs.addTab(self.table_container, ' Table ')
        self._tabs.addTab(self._wdg_treeview, ' Raw Data ')
        self._tabs.addTab(self.w_snr_plot, ' SNR Plot ')
        self._tabs.setTabToolTip(0, 'Alignment Visualizer')
        self._tabs.setTabToolTip(1, 'Alignment Editor')
        self._tabs.setTabToolTip(2, 'Project Data Table View')
        self._tabs.setTabToolTip(3, 'Project Data Tree View')
        self._tabs.setTabToolTip(4, 'SNR Plot')

        vbl = VBL()
        vbl.setSpacing(0)
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

        self._btn_resetBrightnessAndContrast = QPushButton('Reset')
        self._btn_resetBrightnessAndContrast.setStyleSheet('font-size: 10px;')
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
        self.brightnessLE.setText('0')
        # self.brightnessLE.setValidator(QDoubleValidator(-1.0, 1.0, 2))
        self.brightnessLE.setValidator(QIntValidator(-100, 100))
        self.brightnessLE.setFixedWidth(50)
        self.brightnessLE.setFixedHeight(16)
        # def fn():
        #     caller = inspect.stack()[1].function
        #     logger.info('caller: %s' %caller)
        #     self.brightnessSlider.setValue(int(self.brightnessLE.text()))

        self.brightnessLE.textChanged.connect(
            lambda: self.brightnessSlider.setValue(int(self.brightnessLE.text())))
        self.brightnessLE.textChanged.connect(self.fn_brightness_control)
        # self.brightnessSlider = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.brightnessSlider = QSlider(Qt.Orientation.Horizontal, self)
        self.brightnessSlider.setFixedWidth(150)
        self.brightnessSlider.setMouseTracking(False)
        self.brightnessSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.brightnessSlider.setMinimum(-1)
        # self.brightnessSlider.setMaximum(1)
        # self.brightnessSlider.setMinimum(-100)
        # self.brightnessSlider.setMaximum(100)
        # self.brightnessSlider.setRange(-1.0, 1.0)
        self.brightnessSlider.setRange(-100, 100)
        self.brightnessSlider.setValue(0)
        self.brightnessSlider.valueChanged.connect(self.fn_brightness_control)
        self.brightnessSlider.valueChanged.connect(cfg.main_window._callbk_unsavedChanges)
        # self.brightnessSlider.valueChanged.connect(
        #     lambda: self.brightnessLE.setText('%.2f' % self.brightnessSlider.value()))
        self.brightnessSlider.valueChanged.connect(
            lambda: self.brightnessLE.setText('%d' % self.brightnessSlider.value()))

        self.brightnessWidget = HWidget(QLabel('Brightness:'), self.brightnessSlider, self.brightnessLE)

        self.contrastLE = QLineEdit()
        self.contrastLE.setStyleSheet("""QLineEdit {
        color: #141414;
        background: #dadada;
        }""")
        self.contrastLE.setText('0')
        # self.contrastLE.setValidator(QDoubleValidator(-1.0, 1.0, 2))
        self.contrastLE.setValidator(QIntValidator(-100, 100))
        self.contrastLE.setFixedWidth(50)
        self.contrastLE.setFixedHeight(16)
        self.contrastLE.textChanged.connect(
            lambda: self.contrastSlider.setValue(int(self.contrastLE.text())))
        self.contrastLE.textChanged.connect(self.fn_contrast_control)
        # self.contrastSlider = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.contrastSlider = QSlider(Qt.Orientation.Horizontal, self)
        self.contrastSlider.setFixedWidth(150)
        self.contrastSlider.setMouseTracking(False)
        self.contrastSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.contrastSlider.setMinimum(-1.0)
        # self.contrastSlider.setMaximum(1.0)
        # self.contrastSlider.setMinimum(-1)
        # self.contrastSlider.setMaximum(1)
        # self.contrastSlider.setMinimum(-100)
        # self.contrastSlider.setMaximum(100)
        # self.contrastSlider.setRange(-1.0, 1.0)
        self.contrastSlider.setRange(-100, 100)
        self.contrastSlider.setValue(0)
        # self.contrastSlider.setSingleStep(.02)
        # self.contrastSlider.setSingleStep(0.01)
        self.contrastSlider.valueChanged.connect(self.fn_contrast_control)
        self.contrastSlider.valueChanged.connect(cfg.main_window._callbk_unsavedChanges)
        # self.contrastSlider.valueChanged.connect(
        #     lambda: self.contrastLE.setText('%.2f' % self.contrastSlider.value()))
        self.contrastSlider.valueChanged.connect(
            lambda: self.contrastLE.setText('%d' % self.contrastSlider.value()))

        self.contrastWidget = HWidget(QLabel('Contrast:'), self.contrastSlider, self.contrastLE)

        self.bcWidget = HWidget(self.brightnessWidget, QLabel('  '), self.contrastWidget)

        self.shaderToolbar = QToolBar()
        self.shaderToolbar.setFixedHeight(24)

        self.shaderToolbar.setStyleSheet("""background-color: #222222; color: #f3f6fb; font-size: 9px;""")
        self.shaderToolbar.addWidget(ExpandingWidget(self))
        self.shaderToolbar.addWidget(self.bcWidget)
        self.shaderToolbar.addWidget(self.shaderSideButtons)
        self.shaderToolbar.addWidget(ExpandingWidget(self))
        self.shaderToolbar.hide()


    def fn_brightness_control(self):
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' %caller)
        if caller == 'main':
            cfg.data.brightness = self.brightnessSlider.value() / 100
            for viewer in self.get_viewers():
                viewer.set_brightness()

    def fn_contrast_control(self):
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' % caller)
        if caller == 'main':
            cfg.data.contrast = self.contrastSlider.value() / 100
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
            logger.critical('ref viewer is now in focus!')
            # pass
        elif self.focusedViewer == 'base':
            logger.critical('base viewer is now in focus!')
            pass

    def get_viewers(self):
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        # viewers = []
        # if cfg.data['state']['current_tab'] == 1:
        #     # viewers.extend([cfg.baseViewer, cfg.refViewer, cfg.stageViewer])
        #     viewers.extend([cfg.baseViewer, cfg.refViewer])
        #     # viewers.extend([cfg.baseViewer, cfg.refViewer])
        #     # return [cfg.project_tab.MA_viewer_base, cfg.project_tab.MA_viewer_ref]
        # tab = self._tabs.currentIndex()
        # if cfg.data['state']['current_tab'] == 1:
        #     viewers.extend([cfg.emViewer])
        # return viewers
        viewers = []
        if cfg.emViewer:
            viewers.append(cfg.emViewer)
        if cfg.baseViewer:
            viewers.append(cfg.baseViewer)
        if cfg.refViewer:
            viewers.append(cfg.refViewer)
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


    def updateTimingsWidget(self):
        logger.info('')
        try:
            fl_l = QFormLayout()
            fl_l.setContentsMargins(0, 0, 0, 0)
            fl_l.setVerticalSpacing(1)
            for t in cfg.data.timings:
                fl_l.addRow(t[0], QLabel(t[1]))
            w = QWidget()
            w.setContentsMargins(0, 0, 0, 0)
            w.setStyleSheet("""QLabel{color: #161c20; font-size: 8px;}""")
            w.setLayout(fl_l)
            cfg.project_tab.sa_runtimes.setWidget(w)

        except:
            print_exception()
            logger.warning('detailsTiming cant update')


    def updateDetailsPanel(self):
        logger.info('')

        if self._tabs.currentIndex() == 1:
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}] Updating details panel...')
            self.secName.setText(cfg.data.filename_basename())
            ref = cfg.data.reference_basename()
            if ref == '':
                ref = 'None'
            self.secReference.setText(ref)

            self.secAlignmentMethod.setText(cfg.data.method_pretty())
            # self.secSNR.setText(cfg.data.snr_report()[5:])
            # self.secSNR.setText('<span style="font-color: red;"><b>%.2f</b></span>' % cfg.data.snr())
            # self.secDetails[2][1].setText(str(cfg.data.skips_list()))
            skips = cfg.data.skips_list()
            if skips == []:
                self.secExcluded.setText('None')
            else:
                self.secExcluded.setText('\n'.join([f'z-index: {a}, name: {b}' for a, b in skips]))
            self.secHasBB.setText(str(cfg.data.has_bb()))
            self.secUseBB.setText(str(cfg.data.use_bb()))
            self.secSrcImageSize.setText('%dx%d pixels' % cfg.data.image_size())
            if cfg.data.is_aligned():
                try:
                    self.secAlignedImageSize.setText('%dx%d pixels' % cfg.data.image_size_aligned())
                except:
                    print_exception()
                if cfg.data.zpos <= cfg.data.first_unskipped():
                    self.secSNR.setText('--')
                else:
                    try:
                        self.secSNR.setText(
                            '<span style="color: #a30000;"><b>%.2f</b></span><span>&nbsp;&nbsp;(%s)</span>' % (
                                cfg.data.snr(), ",  ".join(["%.2f" % x for x in cfg.data.snr_components()])))
                    except:
                        print_exception()
            else:
                self.secAlignedImageSize.setText('--')
                self.secSNR.setText('--')
            self.secDefaults.setText(cfg.data.defaults_pretty)

    def jump_to_manual(self, requested) -> None:
        logger.info(f'requested: {requested}')
        if requested in range(len(cfg.data)):
            cfg.mw.setZpos(requested)
        else:
            logger.warning('Requested layer is not a valid layer')

    def updateLowest8widget(self):

        if cfg.data.is_aligned():
            logger.info('')
            n_lowest = min(8, len(cfg.data) - 1)
            lowest_X_i = [x[0] for x in list(cfg.data.snr_lowest(n_lowest))]
            lowest_X = list(cfg.data.snr_lowest(n_lowest))
            self.lowestX_btns = []
            self.lowestX_txt = []

            for i in range(n_lowest):
                try:
                    # logger.info(f'i = {i}, lowest_X_i[i] = {lowest_X_i[i]}')
                    s1 = ('z-index <u><b>%d</b></u>' % lowest_X[i][0]).ljust(15)
                    s2 = ("<span style='color: #a30000;'>%.2f</span>" % lowest_X[i][1]).ljust(15)
                    combined = s1 + ' ' + s2
                    self.lowestX_txt.append(combined)
                    zpos = copy.deepcopy(lowest_X_i[i])
                    btn = QPushButton(f'Fix Alignment {zpos}')
                    self.lowestX_btns.append(btn)
                    btn.setLayoutDirection(Qt.RightToLeft)
                    btn.setFixedSize(QSize(130, 18))
                    btn.setStyleSheet("font-size: 10px;")
                    btn.setIconSize(QSize(14, 14))
                    btn.setIcon(qta.icon('fa.arrow-right', color='#161c20'))
                    # self.lowestX_btns[i].clicked.connect(funcs[i])
                    btn.clicked.connect(lambda state, x=zpos: self.jump_to_manual(x))
                except:
                    print_exception()

            self.lowX_left_fl = QFormLayout()
            self.lowX_left_fl.setContentsMargins(0, 0, 0, 0)
            self.lowX_left_fl.setVerticalSpacing(1)
            if n_lowest >= 1:
                self.lowX_left_fl.addRow(self.lowestX_txt[0], self.lowestX_btns[0])
            if n_lowest >= 2:
                self.lowX_left_fl.addRow(self.lowestX_txt[1], self.lowestX_btns[1])
            if n_lowest >= 3:
                self.lowX_left_fl.addRow(self.lowestX_txt[2], self.lowestX_btns[2])
            if n_lowest >= 4:
                self.lowX_left_fl.addRow(self.lowestX_txt[3], self.lowestX_btns[3])
            if n_lowest >= 5:
                self.lowX_left_fl.addRow(self.lowestX_txt[4], self.lowestX_btns[4])
            if n_lowest >= 6:
                self.lowX_left_fl.addRow(self.lowestX_txt[5], self.lowestX_btns[5])
            if n_lowest >= 7:
                self.lowX_left_fl.addRow(self.lowestX_txt[6], self.lowestX_btns[6])
            if n_lowest >= 8:
                self.lowX_left_fl.addRow(self.lowestX_txt[7], self.lowestX_btns[7])
            self.lowX_left = QWidget()
            self.lowX_left.setContentsMargins(0, 0, 0, 0)
            self.lowX_left.setLayout(self.lowX_left_fl)
            hbl = QHBoxLayout()
            hbl.addWidget(self.lowX_left)
            w = QWidget()
            w.setLayout(hbl)
            self.sa_lowest8.setWidget(w)

        else:
            label = QLabel('Not Yet Aligned.')
            label.setStyleSheet("font-size: 11px; color: #161c20; font-weight: 600;")
            label.setAlignment(Qt.AlignCenter)
            self.sa_lowest8.setWidget(label)

        QApplication.processEvents()





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

class ExpandingVWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)


class WebEngine(QWebEngineView):

    def __init__(self, ID='webengine'):
        QWebEngineView.__init__(self)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)


        # self.widget_id = id(self.children()[2])
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


class WarningNotice(QWidget):

    def __init__(self, parent, msg, fixbutton=False, **kwargs):
        super().__init__(parent)
        self.msg = msg
        self.label = QLabel(self.msg)
        self.label.setStyleSheet("QLabel {background: none; font-size: 9px; color: #a30000;"
                           "font-weight: 600; border-radius: 4px; font-family: Tahoma, sans-serif; padding: 4px;} ")

        # self.setFixedHeight(16)
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)



        # font = QFont()
        # font.setBold(True)
        # self.setFont(font)

        if fixbutton:
            self.fixbutton = QPushButton('Fix All')
            self.fixbutton.setStyleSheet("font-size: 10px;")
            self.fixbutton.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            # self.fixbutton.setStyleSheet("""
            # QPushButton{
            #     background-color: #ede9e8;
            #     border-style: solid;
            #     border-width: 1px;
            #     border-radius: 4px;
            #     border-color: #f3f6fb;
            #     color: #161c20;
            #     font-size: 9px;
            #     font-weight: 600;
            # }
            # """)
            self.fixbutton.setFixedSize(QSize(40,15))
            # self.fixbutton.setFixedHeight(16)
            self.layout.addWidget(self.fixbutton)

        self.layout.addWidget(self.label)

        # self.setAutoFillBackground(True)
        self.setLayout(self.layout)


class ClickLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent, **kwargs):
        # super().__init__(parent, **kwargs)
        super().__init__(parent)
        self.isChecked = 0

    def mousePressEvent(self, ev):
        self.isChecked = 1 - self.isChecked
        self.clicked.emit()

    def setChecked(self, b):
        self.isClicked = b

    def isChecked(self):
        return self.isChecked


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