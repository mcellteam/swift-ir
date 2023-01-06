#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os
import shutil
import sys
import copy
import json
import time
import threading
import inspect
import logging
import operator
import pprint
import asyncio
import textwrap
import tracemalloc
from pathlib import Path
import zarr
import dis
from collections import namedtuple
import numpy as np
import numpy
import neuroglancer as ng
import pyqtgraph.console
import pyqtgraph as pg
import pyqtgraph
import qtawesome as qta
import qtpy
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QDir, QFileSystemWatcher, QMetaObject, \
    QRect, QCoreApplication
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication, QKeySequence, QCursor, QImageReader, QMovie, QImage, QColor
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QInputDialog, QLineEdit, QPushButton, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QDialog, QStyle, QCheckBox, QSpinBox, QRadioButton, QSlider, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView, QTabWidget, QStatusBar, QTextBrowser, \
    QFormLayout, QGroupBox, QScrollArea, QToolButton

import src.config as cfg
import src.shaders
from src.background_worker import BackgroundWorker
from src.compute_affines import compute_affines
from src.config import ICON_COLOR
from src.data_model import DataModel
from src.funcs_zarr import tiffs2MultiTiff
from src.generate_aligned import generate_aligned
from src.generate_scales import generate_scales
from src.generate_thumbnails import generate_thumbnails
from src.generate_scales_zarr import generate_zarr_scales
from src.helpers import *
from src.helpers import natural_sort, make_affine_widget_HTML, is_tacc, \
    create_project_structure_directories, get_aligned_scales, tracemalloc_start, tracemalloc_stop, \
    tracemalloc_compare, tracemalloc_clear, show_status_report
from src.ng_host import NgHost
from src.ng_host_slim import NgHostSlim
from src.ui.dialogs import AskContinueDialog, ConfigProjectDialog, ConfigAppDialog, QFileDialogPreview, \
    import_images_dialog, new_project_dialog, open_project_dialog, export_affines_dialog, mendenhall_dialog
from src.ui.process_monitor import HeadupDisplay
from src.ui.kimage_window import KImageWindow
from src.ui.snr_plot import SnrPlot
from src.ui.models.json_tree import JsonModel
from src.ui.layer_view_widget import LayerViewWidget
from src.ui.toggle_switch import ToggleSwitch
from src.ui.ui_custom import VerticalLabel, HorizontalLabel
from src.ui.widget_area import WidgetArea
from src.ui.control_panel import ControlPanel
from src.ui.file_browser import FileBrowser
from src.ui.project_tab import ProjectTab
from src.ui.zarr_tab import ZarrTab
from src.mendenhall_protocol import Mendenhall
import src.pairwise
if cfg.DEV_MODE:
    from src.ui.python_console import PythonConsole


__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    resized = Signal()
    keyPressed = Signal(int)

    def __init__(self, data=None):
        QMainWindow.__init__(self)
        self.app = QApplication.instance()
        self.setObjectName('mainwindow')
        self.setWindowTitle('AlignEM-SWiFT')
        self.setWindowIcon(QIcon(QPixmap('src/resources/em_guy.png')))
        # self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.initPrivateMembers()
        # self.initThreadpool(timeout=3000)
        self.initThreadpool()
        # self.initImageAllocations()
        self.initOpenGlContext()
        self.initNgWebEngine()
        self.initPythonConsole()
        self.initStatusBar()
        self.initPbar()
        self.initToolbar()
        self.initUI()
        self.initMenu()
        self.initWidgetSpacing()
        self.initStyle()
        self.initShortcuts()
        # self.initData()
        # self.initView()

        self.initSizeAndPos(cfg.WIDTH, cfg.HEIGHT)

        self.set_idle()

        # self._forceHideControls()
        # self._tabsGlob.hide()

        if not cfg.NO_SPLASH:
            self.show_splash()


    def _getTabType(self, index=None):
        if index == None:
            index = self._tabsGlob.currentIndex()
        try:
            return self._tabsGlob.currentWidget().__class__.__name__
        except:
            return None


    def initSizeAndPos(self, width, height):
        self.resize(width, height)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def resizeEvent(self, event):
        self.resized.emit()
        if cfg.project_tab:
            cfg.project_tab.updateNeuroglancer()
        return super(MainWindow, self).resizeEvent(event)


    def set_viewer_layout_0(self):
        if cfg.project_tab:
            cfg.project_tab.arrangement = 0
            cfg.project_tab.initNeuroglancer()


    def set_viewer_layout_1(self):
        if cfg.project_tab:
            cfg.project_tab.arrangement = 1
            cfg.project_tab.initNeuroglancer()


    def set_viewer_layout_2(self):
        if cfg.project_tab:
            cfg.project_tab.arrangement = 2
            cfg.project_tab.initNeuroglancer()


    # def initData(self):
    #     logger.info('')
    #     cfg.data = None
    #     if cfg.DUMMY:
    #         with open('tests/example.proj', 'r') as f:
    #             data = json.load(f)
    #         project = DataModel(data=data)
    #         cfg.data = copy.deepcopy(project)
    #         cfg.data.set_paths_absolute(head='tests/example.proj')  # Todo This may not work
    #         cfg.data.link_all_stacks()
    #         self.onStartProject()


    def restartNg(self):
        caller = inspect.stack()[1].function

        if cfg.project_tab:

            # self.tell('Restarting Neuroglancer...')
            logger.info(f'Restarting Neuroglancer Server (caller: {caller})...')
            try:
                # cfg.ng_worker = NgHost(parent=self)
                # cfg.ng_worker.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
                cfg.project_tab.initNeuroglancer()
            except:
                print_exception()
        if cfg.zarr_tab:
            cfg.zarr_tab.openViewZarr()


    def tell(self, message):
        self.hud.post(message, level=logging.INFO)


    def warn(self, message):
        self.hud.post(message, level=logging.WARNING)


    def err(self, message):
        self.hud.post(message, level=logging.ERROR)


    def bug(self, message):
        self.hud.post(message, level=logging.DEBUG)


    def initThreadpool(self, timeout=3000):
        logger.info('')
        self.threadpool = QThreadPool.globalInstance()
        self.threadpool.setExpiryTimeout(timeout)  # ms


    # def initImageAllocations(self):
    #     logger.info('')
    #     if qtpy.PYSIDE6:
    #         QImageReader.setAllocationLimit(0)  # PySide6 only
    #     os.environ['QT_IMAGEIO_MAXALLOC'] = "1_000_000_000_000_000"
    #     from PIL import Image
    #     Image.MAX_IMAGE_PIXELS = 1_000_000_000_000


    def initOpenGlContext(self):
        logger.info('')
        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())


    def initNgWebEngine(self):
        # Performance with settings: Function 'initNgWebEngine' executed in 0.1939s
        # Without: Function 'initNgWebEngine' executed in 0.0001s
        logger.info('')
        self.ng_browser = QWebEngineView()
        # self.browser.setPage(CustomWebEnginePage(self)) # open links in new window
        # if qtpy.PYSIDE6:
        # if is_tacc():

        # self.ng_browser.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # neuroglancer webdriver args
        # --disable-background-networking
        # --disable-default-apps
        # --disable-extensions
        # --disable-gpu
        # --disable-setuid-sandbox
        # --disable-sync
        # --disable-translate
        # --headless
        # --hide-scrollbars
        # --mainFrameClipsContent=false
        # --metrics-recording-only
        # --mute-audio
        # --no-first-run
        # --no-sandbox
        # --safebrowsing-disable-auto-update
        # --window-size=1950,1200

    def initWebEngine(self, webengine):
        logger.info('')
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)


    def initPrivateMembers(self):
        logger.info('')
        self._cur_tab_index = 0
        self._unsaved_changes = False
        self._working = False
        self._is_mp_mode = False
        self._is_viewer_expanded = False
        self._layout = 1
        self._scales_combobox_switch = 0 #1125
        self._jump_to_worst_ticker = 1  # begin iter at 1 b/c first image has no ref
        self._jump_to_best_ticker = 0
        self._snr_by_scale = dict() #Todo

        self._extra_browser_indexes = []

        self._ID = None
        self._key = None
        self._path = None



    def initStyle(self):
        logger.info('')
        self.main_stylesheet = os.path.abspath('styles/default.qss')
        self.apply_default_style()


    def initPythonConsole(self):
        logger.info('')
        namespace = {
            'pg': pyqtgraph,
            'np': numpy,
            'cfg': src.config,
            'mw': src.config.main_window,
            'viewer': cfg.viewer,
        }
        text = """
        Caution - anything executed here is injected into the main event loop of AlignEM-SWiFT!
        """
        cfg.py_console = pyqtgraph.console.ConsoleWidget(namespace=namespace, text=text)
        self._py_console = QWidget()
        # self._py_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        label = QLabel('Python Console')
        label.setStyleSheet('font-size: 10px; font-weight: 500;')
        lay = QVBoxLayout()
        lay.setContentsMargins(0,0,0,0)
        # lay.setSpacing(1)
        lay.addWidget(label, alignment=Qt.AlignmentFlag.AlignBaseline)
        lay.addWidget(cfg.py_console)
        self._py_console.setLayout(lay)
        self._py_console.setObjectName('_py_console')
        self._py_console.hide()


    def initView(self):
        logger.info('')
        # self._tabs.show()
        self._enableAllTabs()
        self.main_stack_widget.setCurrentIndex(0)
        self._cmbo_setScale.setEnabled(True)
        cfg.SHADER = None
        self.viewer_stack_widget.setCurrentIndex(0)
        if cfg.project_tab:
            self._is_mp_mode = False
            if exist_aligned_zarr_cur_scale():
                self.updateStatusTips()
            self._matchpt_ctls.hide()

    def _showToolWidgets(self):
        self._tool_textInfo.show()
        # self._tool_textInfo_NEW.show()
        self._tool_afmCafm.show()
        self._tool_hstry.show()
        self._tool_keyBindings.hide()


    def _callbk_showHidePython(self):
        con = (self._py_console, self._dev_console)[cfg.DEV_MODE]

        if con.isHidden():
            label  = 'Hide Python'
            icon   = 'fa.caret-down'
            color  = '#f3f6fb'
            con.show()
        else:
            label  = ' Python'
            icon   = 'mdi.language-python'
            color  = '#f3f6fb'
            con.hide()

        self._btn_show_hide_console.setIcon(qta.icon(icon, color=color))
        self._btn_show_hide_console.setText(label)
        if cfg.project_tab:
            if cfg.project_tab._tabs.currentIndex() == 0:
                cfg.project_tab.updateNeuroglancer()


    def _forceShowControls(self):
        # self.dataUpdateWidgets()  # for short-circuiting speed-ups
        self.ctl_panel_and_tools.show()
        self._ctl_panel.show()
        self._tools_splitter.show()
        self._btn_show_hide_ctls.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
        self._btn_show_hide_ctls.setText('Hide Controls')


    def _forceHideControls(self):
        self.ctl_panel_and_tools.hide()
        self._ctl_panel.hide()
        self._tools_splitter.hide()
        self._btn_show_hide_ctls.setIcon(qta.icon("ei.adjust-alt", color='#f3f6fb'))
        self._btn_show_hide_ctls.setText('Controls')
        # self._splitter.setSizes([1,0,1,1])


    def _callbk_showHideControls(self):
        if self._ctl_panel.isHidden():
            self._forceShowControls()
        else:
            self._forceHideControls()


    def _forceHidePython(self):
        con = (self._py_console, self._dev_console)[cfg.DEV_MODE]
        label = ' Python'
        icon = 'mdi.language-python'
        color = '#f3f6fb'
        con.hide()
        self._btn_show_hide_console.setIcon(qta.icon(icon, color=color))
        self._btn_show_hide_console.setText(label)


    def autoscale(self, make_thumbnails=True):

        logger.info('>>>> autoscale >>>>')

        #Todo This should check for existence of original source files before doing anything
        self.stopNgServer()
        self.tell('Generating TIFF Scale Image Hierarchy...')
        self.showZeroedPbar()
        self.set_status('Autoscaling...')
        self._disableAllOtherTabs()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_scales(dm=cfg.data))
                self.threadpool.start(self.worker)
            else:
                generate_scales(dm=cfg.data)
        except:
            print_exception()
            self.warn('Something Unexpected Happened While Generating TIFF Scale Hierarchy')
        else:
            self.hud.done()

        show_status_report(results=cfg.results, dt=cfg.dt)

        cfg.data.link_all_stacks() #Todo: check if this is necessary

        cfg.data.set_scale(cfg.data.scales()[-1])

        logger.info('Autoscaler is setting image sizes per scale...')
        for s in cfg.data.scales():
            cfg.data.set_image_size(s=s)

        # self.set_status('Copy-converting TIFFs...')
        self.tell('Copy-converting TIFFs to NGFF-Compliant Zarr...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_zarr_scales(cfg.data))
                self.threadpool.start(self.worker)
            else:
                generate_zarr_scales(cfg.data)
        except:
            print_exception()
            self.warn('Something Unexpected Happened While Converting The Scale Hierarchy To Zarr')

        if make_thumbnails:
            # self.set_status('Generating Thumbnails...')
            self.tell('Generating Thumbnails...')
            self.showZeroedPbar()
            try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(fn=generate_thumbnails(dm=cfg.data))
                    self.threadpool.start(self.worker)
                else:
                    generate_thumbnails(dm=cfg.data)

            except:
                print_exception()
                self.warn('Something Unexpected Happened While Generating Thumbnails')

            finally:
                cfg.data.scalesList = cfg.data.scales()
                cfg.data.nscales = len(cfg.data.scales())
                cfg.data.set_scale(cfg.data.scales()[-1])
                self.pbar_widget.hide()
                logger.info('Autoscaling Complete')
                self.set_idle()

        self._enableAllTabs()
        logger.info('<<<< autoscale <<<<')

    def _runSNRcheck(self, s=None):
        if s == None: s = cfg.data.scale()
        failed = cfg.data.check_snr_status()
        if len(failed) == cfg.data.nSections:
            self.warn(f'No SNR Data Available For This Alignment')
        elif failed:
            indexes, names = zip(*failed)
            self.warn(f'No SNR Data Available For Layers {", ".join(map(str, indexes))}...')
            for name in names:
                self.warn(f'  Section: {name}')


    def onAlignmentEnd(self):
        logger.critical('Running Post- Alignment Tasks...')
        try:
            logger.info('hiding keyboard bindings widget area...')

            self._showToolWidgets()
            cfg.project_tab._onTabChange()
            # cfg.project_tab.snr_plot.initSnrPlot()
            s = cfg.data.curScale
            cfg.data.scalesAligned = get_aligned_scales(cfg.data.scales())
            cfg.data.nScalesAligned = len(cfg.data.scalesAligned)
            self.updateHistoryListWidget(s=s)
            self.dataUpdateWidgets()
            logger.info(f'aligned scales list: {cfg.data.scalesAligned}')
            self.updateEnabledButtons()

            self._runSNRcheck()

            self.app.processEvents()

        except:
            print_exception()
        finally:
            self._enableAllTabs()
            self._autosave()


    def align_all(self, scale=None) -> None:

        if not cfg.data:
            self.warn('No project yet!')
            return

        if self._working == True:
            self.warn('Another Process is Already Running')
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.warn(warning_msg)
            return

        self.stopNgServer()
        self._disableAllOtherTabs()

        logger.info('Aligning All...')
        self.showZeroedPbar()
        if scale == None: scale = cfg.data.curScale
        scale_val = get_scale_val(scale)
        self.widgetsUpdateData()
        is_realign = exist_aligned_zarr_cur_scale()
        if is_realign:
            try:
                # For computing SNR differences later
                snr_before = cfg.data.snr_list()
                snr_avg_before = cfg.data.snr_average()
            except:
                print_exception()
                logger.warning('Unable to get SNR average. Treating project as unaligned...')
                is_realign = False

        if cfg.data.al_option(s=scale) == 'init_affine':
            self.tell("Initializing Affine Transforms (Scale %d)..." % scale_val)
        else:
            self.tell("Refining Affine Transforms (Scale %d)..." % scale_val)
        self.set_status('Aligning...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=compute_affines(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=0,
                        num_layers=-1
                    )
                )
                self.threadpool.start(self.worker)
            else:
                compute_affines(
                    dm=cfg.data,
                    scale=scale,
                    start_layer=0,
                    num_layers=-1
                )

        except:
            print_exception()
            self.err('An Exception Was Raised During Alignment.')
        finally:
            self.set_idle()
            QApplication.processEvents()

        self.showZeroedPbar()
        '''Compute SNR differences'''
        logger.info('Calculating SNR Delta Values...')
        if is_realign:
            snr_after = cfg.data.snr_list()
            snr_avg_after = cfg.data.snr_average()
            diff_avg = snr_avg_after - snr_avg_before
            diff = [a_i - b_i for a_i, b_i in zip(snr_before, snr_after)]
            no_chg = [i for i, x in enumerate(diff) if x == 0]
            pos = [i for i, x in enumerate(diff) if x > 0]
            neg = [i for i, x in enumerate(diff) if x < 0]
            self.tell('Re-alignment Results:')
            self.tell('  # Better (SNR ↑) : %s' % ' '.join(map(str, pos)))
            self.tell('  # Worse  (SNR ↓) : %s' % ' '.join(map(str, neg)))
            self.tell('  # Equal  (SNR =) : %s' % ' '.join(map(str, no_chg)))
            if diff_avg > 0:
                self.tell('  Δ SNR : +%.3f (BETTER)' % diff_avg)
            else:
                self.tell('  Δ SNR : -%.3f (WORSE)' % diff_avg)
            # self.tell('Layers whose SNR changed value: %s' % str(diff_indexes))
        self.tell('Generating Aligned Images...')
        self.set_status('Generating Alignment...')

        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=generate_aligned(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=0,
                        num_layers=-1,
                        preallocate=True
                    )
                )
                self.threadpool.start(self.worker)
            else:
                fn = generate_aligned(
                    dm=cfg.data,
                    scale=scale,
                    start_layer=0,
                    num_layers=-1,
                    preallocate=True
                )

        except:
            print_exception()
            self.err('Alignment Succeeded But Image Generation Failed Unexpectedly. '
                          'Try Re-generating images.')
        else:
            if exist_aligned_zarr_cur_scale():
                self.tell('Alignment Succeeded')
                logger.critical('Alignment seems successful')
        finally:
            self.onAlignmentEnd()
            self.set_idle()
            self.pbar_widget.hide()
            QApplication.processEvents()


    def align_forward(self, scale=None, num_layers=-1) -> None:

        if not cfg.data:
            self.warn('No project yet!')
            return

        if self._working == True:
            self.warn('Another Process is Already Running')
            return

        if not exist_aligned_zarr_cur_scale():
            self.warn('Please align the full series first!')
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.warn(warning_msg)
            return

        self.stopNgServer()

        logger.info('Aligning Forward...')
        self.showZeroedPbar()
        if scale == None: scale = cfg.data.curScale
        scale_val = get_scale_val(scale)
        self.widgetsUpdateData()
        start_layer = cfg.data.layer()
        self.tell('Computing Alignment For Layers %d -> End,  Scale %d...' % (start_layer, scale_val))
        self.set_status('Aligning...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=compute_affines(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=start_layer,
                        num_layers=num_layers
                    )
                )
            else:
                self.threadpool.start(self.worker)
        except:
            print_exception()
            self.err('An Exception Was Raised During Alignment.')

        self.tell('Generating Aligned Images From Layers %d -> End,  Scale  %d...' % (start_layer, scale_val))
        self.set_status('Generating Alignment...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=generate_aligned(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=start_layer,
                        num_layers=num_layers,
                        preallocate=False))
                self.threadpool.start(self.worker)
            else:
                generate_aligned(
                    data=cfg.data,
                    scale=scale,
                    start_layer=start_layer,
                    num_layers=num_layers,
                    preallocate=False)
        except:
            print_exception()
            self.err('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.')

        else:
            self.tell('Alignment Complete')
        finally:
            self.onAlignmentEnd()
            self.set_idle()
            self.pbar_widget.hide()
            QApplication.processEvents()


    def align_one(self, scale=None) -> None:

        if cfg.project_tab is None:
            self.warn('No data yet!')
            return

        if self._working == True:
            self.warn('Another Process is Already Running')
            return

        if not exist_aligned_zarr_cur_scale():
            self.warn('Please align the full series first!')
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.warn(warning_msg)
            return

        self.stopNgServer()
        self._disableAllOtherTabs()

        logger.info('SNR Before: %s' % str(cfg.data.snr_report()))
        logger.info('Aligning Single Layer...')
        if scale == None: scale = cfg.data.curScale
        scale_val = get_scale_val(scale)
        self.widgetsUpdateData()
        self.tell('Re-aligning The Current Layer,  Scale %d...' % scale_val)
        self.set_status('Aligning...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=compute_affines(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=cfg.data.layer(),
                        num_layers=1
                    )
                )
                self.threadpool.start(self.worker)
            else:
                compute_affines(
                    dm=cfg.data,
                    scale=scale,
                    start_layer=cfg.data.layer(),
                    num_layers=1
                )
        except:
            print_exception()
            self.err('An Exception Was Raised During Alignment.')

        cur_layer = cfg.data.layer()
        self.tell('Generating Aligned Image For Layer %d Only...' % cur_layer)
        self.set_status('Generating Alignment...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=generate_aligned(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=cur_layer,
                        num_layers=1,
                        preallocate=False))
                self.threadpool.start(self.worker)
            else:
                generate_aligned(
                    dm=cfg.data,
                    scale=scale,
                    start_layer=cur_layer,
                    num_layers=1,
                    preallocate=False)
        except:
            print_exception()
            self.err('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.')
        else:
            self.tell('Alignment Complete')
        finally:
            self.onAlignmentEnd()
            self.update_match_point_snr()
            self.set_idle()
            self.pbar_widget.hide()
            QApplication.processEvents()


    def regenerate(self, scale) -> None:

        if cfg.project_tab is None:
            self.warn('No data yet!')
            return

        if self._working == True:
            self.warn('Another Process is Already Running')
            return

        if not exist_aligned_zarr_cur_scale():
            self.warn('Scale Must Be Aligned Before Images Can Be Generated.')
            return
        self.widgetsUpdateData()

        self.stopNgServer()
        self._disableAllOtherTabs()

        logger.info('Regenerate Aligned Images...')
        self.showZeroedPbar()
        self.tell('Regenerating Aligned Images,  Scale %d...' % get_scale_val(scale))
        try:
            if cfg.USE_EXTRA_THREADING:
                self.set_status('Regenerating Alignment...')
                self.worker = BackgroundWorker(
                    fn=generate_aligned(
                        dm=cfg.data,
                        scale=scale,
                        start_layer=0,
                        num_layers=-1,
                        preallocate=True
                    )
                )
                self.threadpool.start(self.worker)
            else:
                generate_aligned(
                    dm=cfg.data,
                    scale=scale,
                    start_layer=0,
                    num_layers=-1,
                    preallocate=True
                )
        except:
            print_exception()
            self.err('An Exception Was Raised During Image Generation.')
        else:
            self.dataUpdateWidgets()
            self._autosave()
        finally:
            # self.updateJsonWidget()

            dir = cfg.data.dest()
            scale = cfg.data.scale()
            if are_aligned_images_generated(dir=dir, scale=scale):
                self.tell('Regenerate Succeeded')
            else:
                self.err('Image Generation Failed Unexpectedly. Try Re-aligning.')
            self.set_idle()
            self.pbar_widget.hide()
            QApplication.processEvents()




    def rescale(self):
        if not cfg.data:
            self.warn('No data yet!')
            return
        dlg = AskContinueDialog(title='Confirm Rescale', msg='Warning: Rescaling resets project data.\n'
                                                             'Progress will be lost.  Continue?')
        if not dlg.exec():
            logger.info('Rescale Canceled')
            return
        logger.info('Clobbering project JSON...')
        try:
            os.remove(cfg.data.dest() + '.proj')
        except OSError:
            pass

        self.stopNgServer()
        self._disableAllOtherTabs()

        # self.initView()
        # self.shutdownNeuroglancer()
        self.clearUIDetails()
        path = cfg.data.dest()
        filenames = cfg.data.get_source_img_paths()
        scales = cfg.data.scales()
        self._scales_combobox_switch = 0 #refactor this out
        cfg.main_window.hud.post("Removing Extant Scale Directories...")
        try:
            for scale in scales:
                # if s != 'scale_1':
                p = os.path.join(path, scale)
                if os.path.exists(p):
                    import shutil
                    shutil.rmtree(p)
        except:
            print_exception()
        else:
            self.hud.done()

        self.post = cfg.main_window.hud.post("Removing Zarr Scale Directories...")
        try:
            if os.path.exists(os.path.join(path, 'img_src.zarr')):
                shutil.rmtree(os.path.join(path, 'img_src.zarr'), ignore_errors=True)
            if os.path.exists(os.path.join(path, 'img_aligned.zarr')):
                shutil.rmtree(os.path.join(path, 'img_aligned.zarr'), ignore_errors=True)
        except:
            print_exception()
        else:
            self.hud.done()

        recipe_dialog = ConfigProjectDialog(parent=self)
        if recipe_dialog.exec():
            logger.info('ConfigProjectDialog - Passing...')
            pass
        else:
            logger.info('ConfigProjectDialog - Returning...')
            return
        logger.info('Clobbering The Project Dictionary...')
        makedirs_exist_ok(cfg.data.dest(), exist_ok=True)
        logger.info(str(filenames))
        cfg.main_window.hud.post("Re-scaling...")

        try:
            self.autoscale(make_thumbnails=False)
        except:
            print_exception()
        else:
            self._autosave()
            self.tell('Rescaling Successful')
        finally:
            self._enableAllTabs()
            self.onStartProject()
            self.set_idle()


    def generate_multiscale_zarr(self):
        pass


    def export(self):
        if self._working == True:
            self.warn('Another Process is Already Running')
            return
        logger.critical('Exporting To Zarr...')
        self.tell('Exporting...')
        self.tell('Generating Neuroglancer-Compatible Zarr...')
        src = os.path.abspath(cfg.data['data']['destination_path'])
        out = os.path.abspath(os.path.join(src, 'img_aligned.zarr'))
        self.set_status('Exporting...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_zarr_scales())
                self.threadpool.start(self.worker)
            else:
                generate_zarr_scales()
        except:
            print_exception()
            logger.error('Zarr Export Encountered an Exception')
        finally:
            self.set_idle()
        self._callbk_unsavedChanges()
        self.tell('Process Finished')


    @Slot()
    def clear_skips(self):
        if cfg.project_tab.are_there_any_skips():
            reply = QMessageBox.question(self,
                                         'Verify Reset Skips',
                                         'Clear all skips? This makes all layers unskipped.',
                                         QMessageBox.Cancel | QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                try:
                    self.tell('Resetting Skips...')
                    cfg.data.clear_all_skips()
                except:
                    print_exception()
                    self.warn('Something Went Wrong')
                else:
                    self.hud.done()
        else:
            self.warn('There Are No Skips To Clear.')
            return


    def apply_all(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        swim_val = float(self._swimInput.text())
        whitening_val = float(self._whiteningInput.text())
        scales_dict = cfg.data['data']['scales']
        self.tell('Applying These Settings To All Scales + Layers...')
        self.tell('  SWIM Window  : %s' % str(swim_val))
        self.tell('  Whitening    : %s' % str(whitening_val))
        for key in scales_dict.keys():
            scale = scales_dict[key]
            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                atrm = layer['align_to_ref_method']
                mdata = atrm['method_data']
                mdata['win_scale_factor'] = swim_val
                mdata['whitening_factor'] = whitening_val


    def enableGlobalButtons(self):
        self._ctlpanel_applyAllButton.setEnabled(True)
        self._skipCheckbox.setEnabled(True)
        self._whiteningInput.setEnabled(True)
        self._swimInput.setEnabled(True)
        self.toggle_auto_generate.setEnabled(True)
        self._bbToggle.setEnabled(True)
        self._cmbo_polynomialBias.setEnabled(True)
        self._btn_clear_skips.setEnabled(True)


    def enableAllButtons(self):
        self._btn_alignAll.setEnabled(True)
        self._btn_alignOne.setEnabled(True)
        self._btn_alignForward.setEnabled(True)
        self._btn_regenerate.setEnabled(True)
        self._scaleDownButton.setEnabled(True)
        self._scaleUpButton.setEnabled(True)
        self._ctlpanel_applyAllButton.setEnabled(True)
        self._skipCheckbox.setEnabled(True)
        self._whiteningInput.setEnabled(True)
        self._swimInput.setEnabled(True)
        self.toggle_auto_generate.setEnabled(True)
        self._bbToggle.setEnabled(True)
        self._cmbo_polynomialBias.setEnabled(True)
        self._btn_clear_skips.setEnabled(True)


    def updateEnabledButtons(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev s buttons depending on current s.
        (2) Set the enabled/disabled state of the align_all-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        self._btn_alignAll.setText('Align All\n%s' % cfg.data.scale_pretty())
        if exist_aligned_zarr_cur_scale():
            self._btn_alignAll.setEnabled(True)
            self._btn_alignOne.setEnabled(True)
            self._btn_alignForward.setEnabled(True)
            self._btn_regenerate.setEnabled(True)
        else:
            self._btn_alignOne.setEnabled(False)
            self._btn_alignForward.setEnabled(False)
            self._btn_regenerate.setEnabled(False)
        if cfg.data.is_alignable():
            self._btn_alignAll.setEnabled(True)
        else:
            self._btn_alignAll.setEnabled(False)
        if cfg.data.nscales == 1:
            self._scaleUpButton.setEnabled(False)
            self._scaleDownButton.setEnabled(False)
            self._btn_alignAll.setEnabled(True)
            self._btn_regenerate.setEnabled(True)
        else:
            cur_index = self._cmbo_setScale.currentIndex()
            if cur_index == 0:
                self._scaleDownButton.setEnabled(True)
                self._scaleUpButton.setEnabled(False)
            elif cfg.data.n_scales() == cur_index + 1:
                self._scaleDownButton.setEnabled(False)
                self._scaleUpButton.setEnabled(True)
            else:
                self._scaleDownButton.setEnabled(True)
                self._scaleUpButton.setEnabled(True)


    def updateJsonWidget(self):
        if cfg.project_tab:
            self._treeview_model.load(cfg.data.to_dict())


    @Slot()
    def updateBanner(self, s=None) -> None:
        '''Update alignment details in the Alignment control panel group box.'''
        # logger.info('updateBanner... called By %s' % inspect.stack()[1].function)
        # self._btn_alignAll.setText('Align All\n%s' % cfg.data.scale_pretty())
        if s == None: s = cfg.data.curScale

        # if exist_aligned_zarr_cur_scale():
        #     self.alignment_status_label.setText("Aligned")
        #     self.alignment_status_label.setStyleSheet('color: #41FF00;')
        # else:
        #     self.alignment_status_label.setText("Not Aligned")
        #     self.alignment_status_label.setStyleSheet('color: #FF0000;')
        try:
            img_size = cfg.data.image_size(s=s)
            self.align_label_resolution.setText('%sx%spx' % (img_size[0], img_size[1]))
        except:
            self.align_label_resolution.setText('')
            logger.warning('Unable To Determine Image Size.')
        # Todo fix renaming bug where files are not relinked
        # self.align_label_affine.setText(method_str)


    @Slot()
    def toggle_auto_generate_callback(self) -> None:
        logger.info('toggle_auto_generate_callback:')
        '''Update HUD with new toggle state. Not data-driven.'''
        if self.toggle_auto_generate.isChecked():
            self.tell('Images will be generated automatically after alignment')
        else:
            self.tell('Images will not be generated automatically after alignment')


    def scale_up(self) -> None:
        '''Callback function for the Next Scale button.'''
        if not self._scaleUpButton.isEnabled():
            return
        if self._working:
            self.warn('Changing scales during CPU-bound processes is not currently supported.')
            return
        try:
            self._cmbo_setScale.setCurrentIndex(self._cmbo_setScale.currentIndex() - 1)  # Changes Scale
            if not cfg.data.is_alignable():
                self.warn('Lower scales have not been aligned yet')
        except:
            print_exception()


    def scale_down(self) -> None:
        '''Callback function for the Previous Scale button.'''
        if not self._scaleDownButton.isEnabled():
            return
        if self._working:
            self.warn('Changing scales during CPU-bound processes is not currently supported.')
            return
        try:
            self._cmbo_setScale.setCurrentIndex(self._cmbo_setScale.currentIndex() + 1)  # Changes Scale
            # cfg.data.set_layer(cur_layer) # Set layer to layer last visited at previous s
        except:
            print_exception()


    @Slot()
    def set_status(self, msg: str) -> None:
        self.statusBar.showMessage(msg)
        pass


    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')


    def apply_default_style(self):
        '''#colors
        color: #f3f6fb;  /* snow white */
        color: #004060;  /* drafting blue */
        '''
        cfg.THEME = 0
        # self.tell('Setting Default Theme')
        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        with open(self.main_stylesheet, 'r') as f:
            style = f.read()
        self.setStyleSheet(style)
        self._ctl_panel.setStyleSheet(style)
        self.hud.set_theme_default()
        if inspect.stack()[1].function != 'initStyle':
            ccfg.project_tab.updateNeuroglancer()


    def apply_daylight_style(self):
        cfg.THEME = 1
        # self.tell('Setting Daylight Theme')
        self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        pg.setConfigOption('background', 'w')
        self.hud.set_theme_light()
        if inspect.stack()[1].function != 'initStyle':
            cfg.project_tab.updateNeuroglancer()


    def apply_moonlit_style(self):
        cfg.THEME = 2
        # self.tell('Setting Moonlit Theme')
        self.main_stylesheet = os.path.abspath('src/styles/moonlit.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        self.hud.set_theme_default()
        if inspect.stack()[1].function != 'initStyle':
            cfg.project_tab.updateNeuroglancer()


    def apply_sagittarius_style(self):
        cfg.THEME = 3
        # self.tell('Setting Sagittarius Theme')
        self.main_stylesheet = os.path.abspath('src/styles/sagittarius.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        self.hud.set_theme_default()
        if inspect.stack()[1].function != 'initStyle':
            cfg.project_tab.updateNeuroglancer()


    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')


    def onScaleChange(self):
        s = cfg.data.curScale
        cfg.data.curScale = s
        logger.debug('Changing To Scale %s (caller %s)...' % (s, inspect.stack()[1].function))
        self.jump_to(cfg.data.layer())
        self.dataUpdateWidgets()
        self.updateHistoryListWidget(s=s)
        # self._treeview_model.load(cfg.data.to_dict())
        # self.updateBanner(s=s)
        self.updateEnabledButtons()
        self.updateStatusTips()
        if self._isProjectTab():
            if cfg.project_tab._tabs.currentIndex() == 1:
                cfg.project_tab.layer_view_widget.set_data()
        # self.dataUpdateWidgets()
        if exist_aligned_zarr_cur_scale():
            self.updateStatusTips()
            self._runSNRcheck()
        cfg.project_tab.updateNeuroglancer()


    @Slot()
    def widgetsUpdateData(self) -> None:
        '''Reads MainWindow to Update Project Data.'''
        #1109 refactor - no longer can be called for every layer change...
        logger.debug('widgetsUpdateData:')
        if self._cmbo_polynomialBias.currentText() == 'None':
            cfg.data.set_use_poly_order(False)
        else:
            cfg.data.set_use_poly_order(True)
            cfg.data.set_poly_order(self._cmbo_polynomialBias.currentText())
        cfg.data.set_use_bounding_rect(self._bbToggle.isChecked(), s=cfg.data.curScale)
        cfg.data.set_whitening(float(self._whiteningInput.text()))
        cfg.data.set_swim_window(float(self._swimInput.text()))


    @Slot()
    def dataUpdateWidgets(self, ng_layer=None) -> None:
        '''Reads Project Data to Update MainWindow.'''
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')

        if cfg.zarr_tab:
            self._sectionSlider.setValue(ng_layer)
            self._jumpToLineedit.setText(str(cfg.data.layer()))
            return
        elif not cfg.project_tab:
            return

        if not cfg.data:
            logger.warning('No need to update the interface')
            return

        # if self._tabs.currentIndex() >= self._n_base_tabs:
        #     logger.info('Viewing arbitrary Zarr - Canceling dataUpdateWidgets...')
        #     return

        # if cfg.project_tab.is_mendenhall():
        #     self._overlayRect.hide()
        #     return

        if self._working == True:
            logger.warning("Can't update GUI now - working...")
            self.warn("Can't update GUI now - working...")
            return
        if isinstance(ng_layer, int):
            try:
                if 0 <= ng_layer < cfg.data.n_layers():
                    logger.info(f'Setting Layer: {ng_layer}')
                    cfg.data.set_layer(ng_layer)
                    self._sectionSlider.setValue(ng_layer)
                    cfg.project_tab._overlayRect.hide()
                    cfg.project_tab._overlayLab.hide()
                    QApplication.processEvents()
                else:
                    cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 1.0);')
                    cfg.project_tab._overlayLab.setText('End Of Image Stack')
                    cfg.project_tab._overlayLab.show()
                    cfg.project_tab._overlayRect.show()
                    QApplication.processEvents()
                    self.clearTextWidgetA()
                    self.clearAffineWidget()
                    # logger.info(f'Showing Browser Overlay, Last Layer ({cfg.data.layer()}) - Returning') #Todo
                    return
            except:
                print_exception()



        if cfg.project_tab._tabs.currentIndex() == 0:
            if cfg.data.skipped():
                cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
                cfg.project_tab._overlayLab.setText('X SKIPPED - %s' % cfg.data.name_base())
                cfg.project_tab._overlayLab.show()
                cfg.project_tab._overlayRect.show()
            else:
                cfg.project_tab._overlayRect.hide()
                cfg.project_tab._overlayLab.hide()
            QApplication.processEvents()
            self.app.processEvents()

        try:
            self.updateTextWidgetA()
        except:
            print_exception()
            logger.warning('widget A Buggin out')
        self.updateNewWidget()
        try:     self._jumpToLineedit.setText(str(cfg.data.layer()))
        except:  logger.warning('Current Layer Widget Failed to Update')
        try:     self._skipCheckbox.setChecked(cfg.data.skipped())
        except:  logger.warning('Skip Toggle Widget Failed to Update')
        try:     self._whiteningInput.setText(str(cfg.data.whitening()))
        except:  logger.warning('Whitening Input Widget Failed to Update')
        try:     self._swimInput.setText(str(cfg.data.swim_window()))
        except:  logger.warning('Swim Input Widget Failed to Update')
        try:     self._bbToggle.setChecked(cfg.data.has_bb())
        except:  logger.warning('Bounding Rect Widget Failed to Update')
        try:
            if cfg.data.null_cafm():
                self._cmbo_polynomialBias.setCurrentText(str(cfg.data.poly_order()))
            else:
                'None'
        except:  logger.warning('Polynomial Order Combobox Widget Failed to Update')


    def updateTextWidgetA(self, s=None, l=None):
        if s == None: s = cfg.data.curScale
        if l == None: l = cfg.data.layer()

        name = "<b style='color: #010048;font-size:14px;'>%s</b><br>" % cfg.data.name_base(s=s, l=l)
        skip = "<b style='color:red;'> SKIP</b><br>" if cfg.data.skipped(s=s, l=l) else ''
        completed = "<b style='color: #212121;font-size:11px;'>Scales Aligned: (%d/%d)</b><br>" % \
                    (cfg.data.nScalesAligned, cfg.data.nscales)
        if exist_aligned_zarr_cur_scale():
            if cfg.data.has_bb(s=s):
                bb = cfg.data.bounding_rect(s=s)
                dims = [bb[2], bb[3]]
            else:
                dims = cfg.data.image_size(s=s)
            bb_dims = "<b style='color: #212121;font-size:11px;'>Bounds: %dx%dpx,&nbsp;%s</b><br>" \
                      % (dims[0], dims[1], cfg.data.scale_pretty())
            snr_report = cfg.data.snr_report(s=s, l=l)
            snr_report = snr_report.replace('<', '&lt;')
            snr_report = snr_report.replace('>', '&gt;')
            snr = f"<b style='color:#212121; font-size:11px;'>%s</b><br>" % snr_report

            skips = '\n'.join(map(str, cfg.data.skips_list()))
            matchpoints = '\n'.join(map(str, cfg.data.find_layers_with_matchpoints()))


            self.layer_details.setText(f"{name}{skip}"
                                                 f"{bb_dims}"
                                                 f"{snr}"
                                                 f"{completed}"
                                                 f"<b>Skipped Layers:</b> [{skips}]<br>"
                                                 f"<b>Match Point Layers:</b> [{matchpoints}]"
                                       )
            self.updateAffineWidget()
        else:
            self.layer_details.setText(f"{name}{skip}"
                                                 f"<em style='color: #FF0000;'>Not Aligned</em><br>"
                                                 f"{completed}"
                                                 f"<b>Skipped Layers: []<br>"
                                                 f"<b>Match Point Layers: []</b>"
                                       )
            self.clearAffineWidget()

    def updateNewWidget(self):
        pass


    def updateAffineWidget(self, s=None, l=None):
        if s == None: s = cfg.data.curScale
        if l == None: l = cfg.data.layer()
        afm, cafm = cfg.data.afm(l=l), cfg.data.cafm(l=l)
        self.afm_widget_.setText(make_affine_widget_HTML(afm, cafm))


    def clearUIDetails(self):
        self.clearTextWidgetA()
        self.clearAffineWidget()


    def clearTextWidgetA(self):
        self.layer_details.setText('')
        # self.layer_details.hide()


    def clearAffineWidget(self):
        afm = cafm = [[0] * 3, [0] * 3]
        self.afm_widget_.setText(make_affine_widget_HTML(afm, cafm))


    def updateHistoryListWidget(self, s=None):
        if s == None: s = cfg.data.curScale
        self.history_label = QLabel('<b>Saved Alignments (Scale %d)</b>' % get_scale_val(s))
        self._hstry_listWidget.clear()
        dir = os.path.join(cfg.data.dest(), s, 'history')
        try:
            self._hstry_listWidget.addItems(os.listdir(dir))
        except:
            logger.warning(f"History Directory '{dir}' Not Found")


    def view_historical_alignment(self):
        logger.info('view_historical_alignment:')
        name = self._hstry_listWidget.currentItem().text()
        if cfg.project_tab:
            if name:
                path = os.path.join(cfg.data.dest(), cfg.data.curScale, 'history', name)
                with open(path, 'r') as f:
                    project = json.load(f)
                self.projecthistory_model.load(project)
                self._tabsGlob.addTab(self.historyview_widget, cfg.data.scale_pretty())


    def rename_historical_alignment(self):
        new_name, ok = QInputDialog.getText(self, 'Rename', 'New Name:')
        if not ok: return
        old_name = self._hstry_listWidget.currentItem().text()
        dir = os.path.join(cfg.data.dest(), cfg.data.curScale, 'history')
        old_path = os.path.join(dir, old_name)
        new_path = os.path.join(dir, new_name)
        try:
            os.rename(old_path, new_path)
        except:
            logger.warning('There was a problem renaming the file')
        self.updateHistoryListWidget()


    def swap_historical_alignment(self):
        name = self._hstry_listWidget.currentItem().text()
        if name is None: return
        scale_val = cfg.data.curScale_val()
        msg = "Are you sure you want to swap your alignment data for Scale %d with '%s'?\n" \
              "Note: You must realign after swapping it in." % (scale_val, name)
        reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            logger.info("Returning without changing anything.")
            return
        self.tell('Loading %s')
        path = os.path.join(cfg.data.dest(), cfg.data.curScale, 'history', name)
        with open(path, 'r') as f:
            scale = json.load(f)
        self.tell('Swapping Current Scale %d Dictionary with %s' % (scale_val, name))
        cfg.data.set_al_dict(aldict=scale)
        # self.regenerate() #Todo test this under a range of possible scenarios


    def remove_historical_alignment(self):
        logger.info('Loading History File...')
        name = self._hstry_listWidget.currentItem().text()
        if name is None: return
        path = os.path.join(cfg.data.dest(), cfg.data.curScale, 'history', name)
        logger.info('Removing archival alignment %s...' % path)
        try:
            os.remove(path)
        except:
            logger.warning('There was an exception while removing the old file')
        finally:
            self.updateHistoryListWidget()


    def historyItemClicked(self, qmodelindex):
        item = self._hstry_listWidget.currentItem()
        logger.info(f"Selected {item.text()}")
        path = os.path.join(cfg.data.dest(), cfg.data.curScale, 'history', item.text())
        with open(path, 'r') as f:
            scale = json.load(f)


    def ng_layer(self):
        '''The idea behind this was to cache the current layer. Not Being Used Currently'''
        try:
            index = cfg.ng_worker.cur_index
            assert isinstance(index, int)
            return index
        except:
            print_exception()


    def request_ng_layer(self):
        '''Returns The Currently Shown Layer Index In Neuroglancer'''
        layer = cfg.ng_worker.request_layer()
        logger.info(f'Layer Requested From NG Worker Thread: {layer}')
        return layer


    def _updateJumpToValidator(self):
        logger.info('Setting validators...')
        if self._isProjectTab():
            self._jumpToLineedit.setValidator(QIntValidator(0, cfg.data.nSections - 1))
            self._sectionSlider.setRange(0, cfg.data.nSections - 1)


    def printActiveThreads(self):
        threads = '\n'.join([thread.name for thread in threading.enumerate()])
        logger.info(f'# Active Threads : {threading.active_count()}')
        logger.info(f'Current Thread   : {threading.current_thread()}')
        logger.info(f'All Threads      : \n{threads}')
        self.tell(f'# Active Threads : {threading.active_count()}')
        self.tell(f'Current Thread   : {threading.current_thread()}')
        self.tell(f'All Threads      : \n{threads}')


    @Slot()
    # def jump_to(self, requested) -> None:
    def jump_to(self, requested) -> None:
        logger.info('jumpt_to:')
        if cfg.project_tab:
            if requested not in range(cfg.data.n_layers()):
                logger.warning('Requested layer is not a valid layer')
                return
            cfg.data.set_layer(requested)  # 1231+
            if cfg.project_tab._tabs.currentIndex() == 0:
                # logger.info('Jumping To Layer %d' % requested)
                # state = copy.deepcopy(cfg.ng_workers[cfg.data.curScale].viewer.state)
                state = copy.deepcopy(cfg.viewer.state)
                state.position[0] = requested
                # cfg.ng_workers[cfg.data.curScale].viewer.set_state(state)
                cfg.viewer.set_state(state)
                # self.dataUpdateWidgets() #0106-
            cfg.project_tab.updateNeuroglancer() #0106
            self.dataUpdateWidgets()
            # self.app.processEvents()


    @Slot()
    def jump_to_layer(self) -> None:

        if cfg.project_tab:
            requested = int(self._jumpToLineedit.text())
            if requested not in range(cfg.data.n_layers()):
                logger.warning('Requested layer is not a valid layer')
                return
            if cfg.project_tab._tabs.currentIndex() == 0:
                # logger.info('Jumping To Section #%d' % requested)
                # state = copy.deepcopy(cfg.ng_workers[cfg.data.curScale].viewer.state)
                state = copy.deepcopy(cfg.viewer.state)
                state.position[0] = requested
                # cfg.ng_workers[cfg.data.curScale].viewer.set_state(state)
                cfg.viewer.set_state(state)
                # self.refreshNeuroglancerURL()

            # cfg.project_tab.openViewZarr()
            # self.dataUpdateWidgets() #0106-
            # self.app.processEvents()


    def jump_to_slider(self):
        caller = inspect.stack()[1].function
        if caller == 'dataUpdateWidgets':
            return
        # logger.info(f'caller:{caller}')
        requested = self._sectionSlider.value()
        cfg.ng_worker._layer = requested
        # logger.info(f'slider, requested: {requested}')

        if cfg.project_tab:

            if requested not in range(cfg.data.n_layers()):
                logger.warning('Requested layer is not a valid layer')
                return
            if cfg.project_tab._tabs.currentIndex() == 0:
                logger.info('Jumping To Section #%d' % requested)
                # state = copy.deepcopy(cfg.ng_workers[cfg.data.curScale].viewer.state)
                state = copy.deepcopy(cfg.viewer.state)
                state.position[0] = requested
                # cfg.ng_workers[cfg.data.curScale].viewer.set_state(state)
                cfg.viewer.set_state(state)

        if cfg.zarr_tab:
            state = copy.deepcopy(cfg.viewer.state)
            state.position[0] = requested
            cfg.viewer.set_state(state)

        try:     self._jumpToLineedit.setText(str(requested))
        except:  logger.warning('Current Layer Widget Failed to Update')















    def jump_to_worst_snr(self) -> None:
        scale = cfg.data.scale()
        if not scale in cfg.data.scalesAligned:
            self.tell("You Must Align This Scale First!")
            return
        try:
            # self.widgetsUpdateData()
            snr_list = cfg.data.snr_list()
            enumerate_obj = enumerate(snr_list)
            sorted_pairs = sorted(enumerate_obj, key=operator.itemgetter(1))
            sorted_indices = [index for index, element in sorted_pairs]  # <- rearranged indices
            next_layer = sorted_indices[self._jump_to_worst_ticker]  # int
            snr = sorted_pairs[self._jump_to_worst_ticker]  # tuple
            rank = self._jump_to_worst_ticker  # int
            self.tell("Jump To Section #%d (Badness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            # cfg.data.set_layer(next_layer)
            self.jump_to(requested=next_layer)
            self.dataUpdateWidgets()
            self._jump_to_worst_ticker += 1
        except:
            self._jump_to_worst_ticker = 1
            print_exception()


    def jump_to_best_snr(self) -> None:
        scale = cfg.data.scale()
        if not scale in cfg.data.scalesAligned:
            self.tell("You Must Align This Scale First!")
            return
        try:
            # self.widgetsUpdateData()
            snr_list = cfg.data.snr_list()
            enumerate_obj = enumerate(snr_list)
            sorted_pairs = sorted(enumerate_obj, key=operator.itemgetter(1), reverse=True)
            sorted_indices = [index for index, element in sorted_pairs]  # <- rearranged indices
            # sorted_indices = list(reversed(sorted_indices))
            next_layer = sorted_indices[self._jump_to_best_ticker]
            snr = sorted_pairs[self._jump_to_best_ticker]
            rank = self._jump_to_best_ticker
            self.tell("Jump To Section #%d (Goodness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            # cfg.data.set_layer(next_layer)
            self.jump_to(requested=next_layer)
            self.dataUpdateWidgets()
            self._jump_to_best_ticker += 1
        except:
            self._jump_to_best_ticker = 0
            print_exception()


    @Slot()
    def reload_scales_combobox(self) -> None:
        # logger.info('Reloading Scale Combobox (caller: %s)' % inspect.stack()[1].function)
        self._scales_combobox_switch = 0
        self._cmbo_setScale.clear()
        self._cmbo_setScale.addItems(cfg.data.scales())
        index = self._cmbo_setScale.findText(cfg.data.curScale, Qt.MatchFixedString)
        if index >= 0:
            self._cmbo_setScale.setCurrentIndex(index)
        self._scales_combobox_switch = 1

    def fn_scales_combobox(self) -> None:
        caller = inspect.stack()[1].function
        if caller == 'onStartProject':
            logger.warning('Canceling scale change trigger!')
            return
        if self._is_mp_mode == True:
            return
        # logger.info('caller: %s' % caller)
        if self._scales_combobox_switch == 0:
            if inspect.stack()[1].function != 'reload_scales_combobox':
                logger.info('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return

        new_scale = self._cmbo_setScale.currentText()
        cfg.data.set_scale(new_scale)
        self.onScaleChange()

    # def ng_layout_switch(self, key):
    #     caller = inspect.stack()[1].function
    #     if caller == 'onStartProject':
    #         return
    #     # logger.info("Setting Neuroglancer Layout [%s]... " % inspect.stack()[1].function)
    #     if not cfg.data:
    #         logger.info('Cant change layout, no data is loaded')
    #         return
    #     cur_tab_index = cfg.project_tab._tabs.currentIndex()
    #     if cur_tab_index == 0:
    #         _ng_worker = cfg.ng_worker
    #     elif cfg.project_tab._tabs.currentIndex() in self._extra_browser_indexes:
    #         if cfg.project_tab._tabs.currentIndex() in self._extra_browser_indexes:
    #             _ng_worker = cfg.extra_ng_workers[cfg.project_tab._tabs.currentIndex()]
    #     layout_switcher = {
    #         'xy': self.ngLayout1Action,
    #         'yz': self.ngLayout2Action,
    #         'xz': self.ngLayout3Action,
    #         'xy-3d': self.ngLayout4Action,
    #         'yz-3d': self.ngLayout5Action,
    #         'xz-3d': self.ngLayout6Action,
    #         '3d': self.ngLayout7Action,
    #         '4panel': self.ngLayout8Action
    #     }
    #     func = layout_switcher.get(key, lambda: print_exception)
    #     return func()


    def fn_ng_layout_combobox(self) -> None:
        caller = inspect.stack()[1].function
        if caller == 'onStartProject':
            return
        if not cfg.data:
            logger.info('Cant change layout, no data is loaded')
            return

        if cfg.project_tab._tabs.currentIndex() != 0:
            return

        try:
            choice = self._cmbo_ngLayout.currentText()
            cfg.project_tab.ng_layout = choice
            self.hud("Setting Neuroglancer Layout ['%s']... " % choice)

            layout_actions = {
                'xy': self.ngLayout1Action,
                'yz': self.ngLayout2Action,
                'xz': self.ngLayout3Action,
                'xy-3d': self.ngLayout4Action,
                'yz-3d': self.ngLayout5Action,
                'xz-3d': self.ngLayout6Action,
                '3d': self.ngLayout7Action,
                '4panel': self.ngLayout8Action
            }
            layout_actions[choice].setChecked(True)
            # self.refreshNeuroglancerURL()
            cfg.project_tab.updateNeuroglancer()
        except:
            logger.error('Unable To Change Neuroglancer Layout')



    @Slot()
    def change_scale(self, scale_key: str):
        try:
            cfg.data['data']['current_scale'] = scale_key
            self.dataUpdateWidgets()
            logger.info('Scale changed to %s' % scale_key)
        except:
            print_exception()
            logger.info('Changing Scales Triggered An Exception')


    def export_afms(self):
        if cfg.project_tab:
            if exist_aligned_zarr_cur_scale():
                file = export_affines_dialog()
                if file == None:
                    logger.warning('No Filename - Canceling Export')
                    return
                afm_lst = cfg.data.afm_list()
                with open(file, 'w') as f:
                    for sublist in afm_lst:
                        for item in sublist:
                            f.write(str(item) + ',')
                        f.write('\n')
                self.tell('Exported: %s' % file)
                self.tell('AFMs exported successfully.')
            else:
                self.warn('The current scale is not aligned. Nothing to export.')
        else:
            self.warn('There is no project open. Nothing to export.')


    def export_cafms(self):
        file = export_affines_dialog()
        if file == None:
            logger.warning('No Filename - Canceling Export')
            return
        logger.info('Export Filename: %s' % file)
        cafm_lst =  cfg.data.cafm_list()
        with open(file, 'w') as f:
            for sublist in cafm_lst:
                for item in sublist:
                    f.write(str(item) + ',')
                f.write('\n')

        self.tell('Exported: %s' % file)
        self.tell('Cumulative AFMs exported successfully.')


    def show_warning(self, title, text):
        QMessageBox.warning(None, title, text)


    def new_project(self, mendenhall=False):
        logger.critical('Starting A New Project...')
        if cfg.project_tab:
            logger.info('Data is not None. Asking user to confirm new data...')
            msg = QMessageBox(QMessageBox.Warning,
                              'Confirm New Project',
                              'Please confirm create new project.',
                              buttons=QMessageBox.Cancel | QMessageBox.Ok)
            msg.setIcon(QMessageBox.Question)
            msg.setDefaultButton(QMessageBox.Cancel)
            reply = msg.exec_()
            if reply == QMessageBox.Ok:
                logger.info("Response was 'OK'")
                pass
            else:
                logger.info("Response was not 'OK' - Returning")
                self.warn('New Project Canceled.')
                return
            if reply == QMessageBox.Cancel:
                logger.info("Response was 'Cancel'")
                self.warn('New Project Canceled.')
                return

        # self.initView()
        self.clearUIDetails()
        # self.shutdownNeuroglancer()
        self.tell('New Project Path:')
        filename = new_project_dialog()
        if filename in ['', None]:
            logger.info('New Project Canceled.')
            self.warn("New Project Canceled.")
            self.set_idle()
            return
        if not filename.endswith('.proj'):
            filename += ".proj"
        if os.path.exists(filename):
            logger.warning("The file '%s' already exists." % filename)
            self.warn("The file '%s' already exists." % filename)
            path_proj = os.path.splitext(filename)[0]
            self.tell(f"Removing Extant Project Directory '{path_proj}'...")
            logger.info(f"Removing Extant Project Directory '{path_proj}'...")
            shutil.rmtree(path_proj, ignore_errors=True)
            self.tell(f"Removing Extant Project File '{path_proj}'...")
            logger.info(f"Removing Extant Project File '{path_proj}'...")
            os.remove(filename)

        path, extension = os.path.splitext(filename)
        unique_key = cfg.increasing_tab_counter
        cfg.data = DataModel(name=path, mendenhall=mendenhall)
        cfg.project_tab = ProjectTab(key=unique_key, path=path, datamodel=cfg.data)
        self._tabsGlob.addTab(cfg.project_tab, os.path.basename(path) + '.proj')
        cfg.increasing_tab_counter += 1  # increment after successful tab creation
        self._setLastTab()
        makedirs_exist_ok(path, exist_ok=True)

        if not mendenhall:
            try:
                self.import_multiple_images()
            except:
                print_exception()
                logger.warning('Import Images Dialog Was Canceled - Returning')
                return

            recipe_dialog = ConfigProjectDialog(parent=self)
            if recipe_dialog.exec():
                logger.info('ConfigProjectDialog - Passing...')
                pass
            else:
                logger.info('ConfigProjectDialog - Returning...')
                return

            try:
                self.autoscale()
            except:
                print_exception()
        else:
            create_project_structure_directories(cfg.data.dest(), ['scale_1'])


        self.onStartProject()
        # cfg.project_tab.openViewZarr()

        cfg.project_tab.initNeuroglancer()

        self._autosave()


    def open_zarr(self):
        logger.info('')
        key = cfg.increasing_tab_counter + 1
        cfg.zarr_tab = ZarrTab(key=key)
        self._tabsGlob.addTab(cfg.zarr_tab, 'Open Zarr...')
        cfg.increasing_tab_counter += 1  # increment after successful tab creation
        self.set_status('Select Zarr...')
        self._forceHideControls()
        self._forceHidePython()
        self._setLastTab()


    def open_project(self):
        #Todo check for Zarr. Generate/Re-generate if necessary
        logger.critical('Opening A Project...')
        self.tell('Open Project Path:')
        # self.shutdownNeuroglancer()
        cfg.main_window.set_status('Awaiting User Input...')
        filename = open_project_dialog()
        if filename == None:
            logger.info('Open Project Canceled.')
            self.warn('Open Project Canceled.')
            return
        logger.info(f'filename: {filename}')

        unique_key = cfg.increasing_tab_counter
        try:
            with open(filename, 'r') as f:
                cfg.data = DataModel(data=json.load(f))
        except:
            cfg.main_window.set_idle()
            print_exception()
            return
        else:
            logger.info(f'Project Opened! Unique Key: {unique_key}')

        print(cfg.data.scales())

        cfg.data.set_paths_absolute(filename=filename)
        cfg.project_tab = ProjectTab(
            key=unique_key,
            parent=self,
            path=cfg.data.dest() + '.proj',
            datamodel=cfg.data
        )
        self.onStartProject()

        tab_name = os.path.basename(cfg.data.dest() + '.proj')
        self._tabsGlob.addTab(cfg.project_tab, tab_name)
        cfg.increasing_tab_counter += 1  # increment after successful tab creation
        cfg.project_tab.initNeuroglancer()
        self._setLastTab()
        # self.onStartProject()
        # cfg.project_tab.openViewZarr()
        # cfg.project_tab.snr_plot.initSnrPlot()  # !!!
        # self._forceHideControls()
        # self._forceHidePython()

        if exist_aligned_zarr_cur_scale():
            self.updateStatusTips()
            self._runSNRcheck()


    def onStartProject(self):
        '''Functions that only need to be run once per project
                Do not automatically save, there is nothing to save yet'''
        caller = inspect.stack()[1].function

        cfg.data.update_cache()
        self._sectionSlider.setRange(0, cfg.data.nSections - 1)


        self._scales_combobox_switch = 0
        self.reload_scales_combobox()
        self._cmbo_setScale.setCurrentText(cfg.data.curScale)
        self._cmbo_ngLayout.setCurrentText(cfg.project_tab.ng_layout)
        self._scales_combobox_switch = 1

        self.dataUpdateWidgets()
        self.updateStatusTips()
        self.updateHistoryListWidget()
        self.updateEnabledButtons()
        self.enableGlobalButtons()
        self._updateJumpToValidator()  # future changes to import_multiple_images will require refactoring this
        ng_layouts = ['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d']
        self._cmbo_ngLayout.addItems(ng_layouts) # only doing this here so combo is empty on application open

        self._btn_alignAll.setText('Align All\n%s' % cfg.data.scale_pretty())
        self._showToolWidgets()
        # self.initNgServer() #0103-
        # cfg.project_tab.openViewZarr()
        QApplication.processEvents()
        self.set_idle()
        # self._forceShowControls()
        # self._tabsGlob.show()


    def save(self):
        if not cfg.data:
            self.warn('Nothing To Save')
            return
        self.set_status('Saving...')
        self.tell('Saving Project...')
        try:
            self._proj_saveToFile()
            self._unsaved_changes = False
        except:
            self.warn('Unable To Save')
        else:
            self.hud.done()
        finally:
            self.set_idle()


    def _autosave(self):
        if not cfg.AUTOSAVE:
            logger.info('Autosave is OFF, There May Be Unsaved Changes...')
            return
        if not cfg.data:
            self.warn('Nothing To Save')
            return
        self.set_status('Saving...')
        self.tell('Autosaving...')
        try:
            self._proj_saveToFile()
            self._unsaved_changes = False
        except:
            self.warn('Unable To Autosave')
        else:
            self.hud.done()
        finally:
            self.set_idle()


    def rename_project(self):
        new_name, ok = QInputDialog.getText(self, 'Input Dialog', 'Project Name:')
        if ok:
            dest_orig = Path(cfg.data.dest())
            print(dest_orig)
            parent = dest_orig.parents[0]
            new_dest = os.path.join(parent, new_name)
            new_dest_no_ext = os.path.splitext(new_dest)[0]
            os.rename(dest_orig, new_dest_no_ext)
            cfg.data.set_destination(new_dest)
            # if not new_dest.endswith('.json'):  # 0818-
            #     new_dest += ".json"
            # logger.info('new_dest = %s' % new_dest)
            self._autosave()


    def _proj_saveToFile(self, saveas=None):
        logger.info('Saving...')
        cfg.data.basefilenames()
        if saveas is not None:
            cfg.data.set_destination(saveas)
        data_cp = copy.deepcopy(cfg.data)
        if data_cp.layer() >= data_cp.n_layers():
            real_layer = data_cp.n_layers() - 1
            logger.info(f'Adjusting Save Layer Down to Real Stack Layer ({real_layer}) ')
            data_cp.set_layer(real_layer)
        # data_cp.make_paths_relative(start=cfg.data.dest())
        data_cp_json = data_cp.to_dict()
        logger.info('---- SAVING DATA TO PROJECT FILE ----')
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        proj_json = jde.encode(data_cp_json)
        name = cfg.data.dest()
        if not name.endswith('.proj'): name += ".proj"
        logger.info('Save Name: %s' % name)
        with open(name, 'w') as f: f.write(proj_json)
        del data_cp
        self._unsaved_changes = False
        self._tabsGlob.setTabText(self._tabsGlob.currentIndex(), os.path.basename(name))


    def _callbk_unsavedChanges(self):
        logger.debug("Called by " + inspect.stack()[1].function)
        if inspect.stack()[1].function == 'initUI':
            return
        if inspect.stack()[1].function == 'dataUpdateWidgets':
            return
        self._unsaved_changes = True
        name = os.path.basename(cfg.data.dest())
        self._tabsGlob.setTabText(self._tabsGlob.currentIndex(), name + '.proj' +  '*')


    def ng_toggle_show_ui_controls(self):
        if self.ngShowUiControlsAction.isChecked():
            cfg.SHOW_UI_CONTROLS = True
            self.ngShowUiControlsAction.setText('Show UI Controls')
        else:
            cfg.SHOW_UI_CONTROLS = False
            self.ngShowUiControlsAction.setText('Hide UI Controls')
        cfg.project_tab.updateNeuroglancer()


    def import_multiple_images(self, clear_role=False):
        ''' Import images into data '''
        logger.info('>>>> import_multiple_images >>>>')
        self.tell('Import Images:')
        role = 'base'

        filenames = natural_sort(import_images_dialog())

        cfg.data.set_source_path(os.path.dirname(filenames[0])) #Critical!
        if clear_role:
            for layer in cfg.data.alstack():
                if role in layer['images'].keys():  layer['images'].pop(role)

        self.tell(f'Importing {len(filenames)} Images...')
        logger.info(f'Selected Images: \n{filenames}')

        try:
            nlayers = 0
            for i, f in enumerate(filenames):
                nlayers += 1
                if f is None:
                    cfg.data.append_empty(role)
                else:
                    cfg.data.append_image(f, role)
        except:
            print_exception()
            self.err('There Was A Problem Importing Selected Files')
        else:
            self.hud.done()

        if len(cfg.data) > 0:
            cfg.data.nSections = nlayers
            img_size = cfg.data.image_size(s='scale_1')
            # self.tell(f'{len(filenames)} Images ({img_size[0]}✕{img_size[1]}px) Imported')
            self.tell(f'Dimensions: {img_size[0]}✕{img_size[1]}')
            cfg.data.link_all_stacks()
            # self.tell(f'Dimensions: {img_size[0]}✕{img_size[1]}px')
            '''Todo save the image dimensions in project dictionary for quick lookup later'''
        else:
            self.warn('No Images Were Imported')

        self._proj_saveToFile()
        logger.info('<<<< import_multiple_images <<<<')


    @Slot()
    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent (called by %s):" % inspect.stack()[1].function)
        self.shutdownInstructions()


    def exit_app(self):
        logger.info("Exiting The Application...")

        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            pass
        else:
            return

        self.set_status('Exiting...')
        if self._unsaved_changes:
            self.tell('Exit AlignEM-SWiFT?')
            message = "There are unsaved changes.\n\nSave before exiting?"
            msg = QMessageBox(QMessageBox.Warning, "Save Changes", message, parent=self)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            msg.setIcon(QMessageBox.Question)
            reply = msg.exec_()
            if reply == QMessageBox.Cancel:
                logger.info('reply=Cancel. Returning control to the app.')
                self.tell('Canceling exit application')
                return
            if reply == QMessageBox.Save:
                logger.info('reply=Save')
                self.save()
                self.set_status('Wrapping up...')
                logger.info('Project saved. Exiting')
            if reply == QMessageBox.Discard:
                logger.info('reply=Discard Exiting without saving')
        else:
            logger.info('No Unsaved Changes - Exiting')

        self.shutdownInstructions()


    def shutdownInstructions(self):
        logger.info('Performing Shutdown Instructions...')

        # loop = asyncio.get_event_loop()
        # tasks = [t for t in asyncio.all_tasks() if t is not
        #          asyncio.current_task()]
        #
        # [task.cancel() for task in tasks]
        # asyncio.gather(*tasks)
        # loop.stop()
        # if tasks != []:
        #     logger.warning(f'\nRunning Tasks: {tasks}\n')
        #     time.sleep(.5)

        # tasks = asyncio.all_tasks()
        # if tasks != []:
        #     logger.warning(f'Canceling Tasks: {tasks}...')
        #     self.tell(f'Canceling Tasks: {tasks}...')
        #     for _task in tasks:
        #         _task.cancel()
        #     time.sleep(.3)

        # del cfg.viewer
        # del cfg.ng_worker

        # if ng.server.is_server_running():
        #     try:
        #         logger.info('Stopping Neuroglancer Client...')
        #         self.tell('Stopping Neuroglancer Client...')
        #         self.shutdownNeuroglancer()
        #     except:
        #         sys.stdout.flush()
        #         logger.warning('Having trouble shutting down neuroglancer')
        #         self.warn('Having trouble shutting down neuroglancer')
        #     finally:
        #         time.sleep(.3)

        if cfg.USE_EXTRA_THREADING:
            try:
                self.tell('Waiting For Threadpool...')
                logger.info('Waiting For Threadpool...')
                result = self.threadpool.waitForDone(msecs=500)
            except:
                print_exception()
                self.warn(f'Having trouble shutting down threadpool')
            finally:
                time.sleep(.4)

        if not is_tacc():
            if cfg.PROFILER:
                self.tell('Stopping Profiler...')
                logger.info('Stopping Profiler...')
                try:
                    if cfg.PROFILER == True:
                        from scalene import scalene_profiler
                        scalene_profiler.stop()

                except:
                    print_exception()
                    self.warn('Having trouble stopping profiler')
                finally:
                    time.sleep(.4)

        if cfg.DEV_MODE:
            self.tell('Shutting Down Developer Console Kernel...')
            logger.info('Shutting Down Developer Console Kernel...')
            try:
                self._dev_console.kernel_client.stop_channels()
                self._dev_console.kernel_manager.shutdown_kernel()
            except:
                print_exception()
                self.warn('Having trouble shutting down developer console kernel')
            finally:
                time.sleep(.4)

        self.tell('Graceful, Goodbye!')
        logger.info('Exiting...')
        time.sleep(1)
        QApplication.quit()


    def html_view(self):
        app_root = self.get_application_root()
        html_f = os.path.join(app_root, 'src', 'resources', 'remod.html')
        print(html_f)
        with open(html_f, 'r') as f:
            html = f.read()
        self.browser_docs.setHtml(html)
        self.main_stack_widget.setCurrentIndex(1)


    def html_keyboard_commands(self):
        if self.main_stack_widget.currentIndex() == 1:
            self.main_stack_widget.setCurrentIndex(0)
            return
        app_root = self.get_application_root()
        html_f = os.path.join(app_root, 'src', 'resources', 'KeyboardCommands.html')
        print(html_f)
        with open(html_f, 'r') as f:
            html = f.read()
        self.browser_docs.setHtml(html)
        self.main_stack_widget.setCurrentIndex(1)


    def documentation_view(self):
        self.tell("Viewing AlignEM_SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def documentation_view_home(self):
        self.tell("Viewing AlignEM-SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def remote_view(self):
        self.tell("Loading A Neuroglancer Instance Running On A Remote Server...")
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.main_stack_widget.setCurrentIndex(3)


    def open_url(self, text: str) -> None:
        self.browser_docs.setUrl(QUrl(text))
        self.main_stack_widget.setCurrentIndex(1)


    def view_swiftir_examples(self):
        self.browser_docs.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/examples/README.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def view_swiftir_commands(self):
        self.browser_docs.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/commands/README.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def shutdownNeuroglancer(self):
        if ng.is_server_running():
            logger.info('Deleting Viewer...')
            # self.tell('Deleting Viewer...')
            # del cfg.viewer

            logger.info('Stopping Neuroglancer...')
            self.tell('Stopping Neuroglancer...')
            try:
                ng.server.stop()
            except:
                print_exception()
            finally:
                self.hud.done()


    def invalidate_all(self, s=None):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        if s == None: s = cfg.data.curScale
        if cfg.data.is_mendenhall():
            cfg.ng_worker.menLV.invalidate()
            return
        cfg.refLV.invalidate()
        cfg.baseLV.invalidate()
        if exist_aligned_zarr(s):
            cfg.alLV.invalidate()


    def stopNgServer(self):
        logger.info('Considering stopping Neuroglancer...')
        if ng.is_server_running():
            self.tell('Stopping Neuroglancer...')
            try:
                ng.stop()
            except:
                print_exception()
            else:
                self.hud.done()
        else:
            self.tell('Neuroglancer Is Not Running')

    def initShortcuts(self):
        logger.info('')
        events = (
            (QKeySequence.MoveToPreviousChar, self.scale_down),
            (QKeySequence.MoveToNextChar, self.scale_up)
        )
        for event, action in events:
            QShortcut(event, self, action)


    def reload_remote(self):
        logger.info("Reloading Remote Neuroglancer Client")
        self.remote_view()

    def exit_docs(self):
        self.main_stack_widget.setCurrentIndex(0)

    def exit_remote(self):
        self.main_stack_widget.setCurrentIndex(0)

    def exit_demos(self):
        self.main_stack_widget.setCurrentIndex(0)

    def webgl2_test(self):
        '''https://www.khronos.org/files/webgl20-reference-guide.pdf'''
        self.browser_docs.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.main_stack_widget.setCurrentIndex(1)

    def google(self):
        self.tell('Googling...')
        self.browser_docs.setUrl(QUrl('https://www.google.com'))
        self.main_stack_widget.setCurrentIndex(1)

    def gpu_config(self):
        self.browser_docs.setUrl(QUrl('chrome://gpu'))
        self.main_stack_widget.setCurrentIndex(1)

    def chromium_debug(self):
        self.browser_docs.setUrl(QUrl('http://127.0.0.1:9000'))
        self.main_stack_widget.setCurrentIndex(1)

    def show_webdriver_log(self):
        log = json.dumps(cfg.webdriver.get_log(), indent=2)
        self.hud(f'Webdriver Log:\n{log}')

    def display_actual_viewer_url(self, s=None):
        if cfg.project_tab:
            if s == None: s = cfg.data.curScale
            if ng.is_server_running():
                try:
                    # url = cfg.viewer.url
                    url = str(cfg.viewer)
                    # self.tell(f"\n\nScale {cfg.data.scale_pretty(s=s)} URL:\n<a href='{url}'>{url}</a>\n")
                    # self.hud.textedit.appendHtml(f"<span style='color: #F3F6FB'>URL:</span>\n<a href='{url}'>{url}</a>\n")
                    self.hud.textedit.appendHtml(f"<a href='\n{url}'>{url}</a>\n")
                    logger.info(f"{cfg.data.scale_pretty(s=s)}\nURL:  {url}")
                    # logger.info(f"{cfg.data.scale_pretty(s=s)}\n{url}\n")
                except:
                    logger.warning('No URL to show')
            else:
                self.tell('Neuroglancer is not running.')

    def print_ng_state_url(self):
        if cfg.project_tab:
            if ng.is_server_running():
                try:     cfg.ng_worker.show_state()
                except:  print_exception()
            else:
                self.tell('Neuroglancer is not running.')


    def print_ng_state(self):
        if cfg.project_tab:
            if ng.is_server_running():
                try:     self.tell('\nViewer State:\n%s' % str(cfg.viewer.state))
                except:  print_exception()
            else:
                self.tell('Neuroglancer is not running')


    def print_ng_raw_state(self):
        if cfg.project_tab:
            if ng.is_server_running():
                try:
                    self.tell('\nRaw State:\n%s' % str(cfg.viewer.config_state.raw_state))
                except:
                    print_exception()
            else:
                self.tell('Neuroglancer is not running')


    def browser_reload(self):
        try:
            self.ng_browser.reload()
        except:
            print_exception()


    def dump_ng_details(self):
        if cfg.project_tab:
            if not ng.is_server_running():
                logger.warning('Neuroglancer is not running')
                return
            v = cfg.viewer
            self.tell("v.position: %s\n" % str(v.state.position))
            self.tell("v.config_state: %s\n" % str(v.config_state))


    def blend_ng(self):
        logger.info("blend_ng():")


    def show_splash(self):
        logger.info('Showing Splash...')
        self.temp_img_panel_index = self.viewer_stack_widget.currentIndex()
        self.splashlabel.show()
        self.viewer_stack_widget.setCurrentIndex(1)
        self.main_stack_widget.setCurrentIndex(0)
        self.splashmovie.start()


    def runaftersplash(self):
        self.viewer_stack_widget.setCurrentIndex(self.temp_img_panel_index)
        self.splashlabel.hide()


    def _dlg_cfg_project(self):
        if cfg.project_tab:
            dialog = ConfigProjectDialog(parent=self)
            result = dialog.exec_()
            logger.info(f'ConfigProjectDialog exit code ({result})')
        else:
            self.tell('No Project Yet!')


    def _dlg_cfg_application(self):
        dialog = ConfigAppDialog(parent=self)
        result = dialog.exec_()
        logger.info(f'ConfigAppDialog exit code ({result})')


    def view_k_img(self):
        if cfg.project_tab:
            self.w = KImageWindow(parent=self)
            self.w.show()


    def _callbk_bnding_box(self, state):
        logger.info('_callbk_bnding_box:')
        self._bbToggle.setEnabled(state)
        if cfg.project_tab:
            if inspect.stack()[1].function == 'dataUpdateWidgets': return
            if state:
                self.warn('Bounding Box is now ON. Warning: Output dimensions may grow large.')
                cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
            else:
                self.tell('Bounding Box is now OFF. Output dimensions will match source.')
                cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def _callbk_skipChanged(self, state:int):  # 'state' is connected to skipped toggle
        logger.info(f'_callbk_skipChanged, sig:{state}:')
        '''Callback Function for Skip Image Toggle'''
        caller = inspect.stack()[1].function
        if cfg.project_tab:
            if caller != 'dataUpdateWidgets':
                skip_state = self._skipCheckbox.isChecked()
                for s in cfg.data.scales():
                    # layer = self.request_ng_layer()
                    layer = cfg.data.layer()
                    if layer >= cfg.data.n_layers():
                        logger.warning(f'Request layer is out of range ({layer}) - Returning')
                        return
                    cfg.data.set_skip(skip_state, s=s, l=layer)  # for checkbox
                if skip_state:
                    self.tell("Flagged For Skip: %s" % cfg.data.name_base())
                cfg.data.link_all_stacks()
                self.dataUpdateWidgets()
                if cfg.project_tab._tabs.currentIndex() == 1:
                    cfg.project_tab.layer_view_widget.set_data()


    def skip_change_shortcut(self):
        logger.info('skip_change_shortcut:')
        if cfg.project_tab:
            if self._skipCheckbox.isChecked():
                self._skipCheckbox.setChecked(False)
            else:
                self._skipCheckbox.setChecked(True)


    def enterExitMatchPointMode(self):
        logger.info('enterExitMatchPointMode:')
        if cfg.project_tab:
            if self._is_mp_mode == False:
                logger.info('\nEntering Match Point Mode...')
                self.tell('Entering Match Point Mode...')
                self._is_mp_mode = True
                self._cmbo_setScale.setEnabled(False)
                self.extra_header_text_label.setText('Match Point Mode')
                self._ctl_panel.hide()
                self._matchpt_ctls.show()
                self.update_match_point_snr()
                self.mp_marker_size_spinbox.setValue(cfg.data['user_settings']['mp_marker_size'])
                self.mp_marker_lineweight_spinbox.setValue(cfg.data['user_settings']['mp_marker_lineweight'])

            else:
                logger.info('\nExiting Match Point Mode...')
                self.tell('Exiting Match Point Mode...')
                self._is_mp_mode = False
                self._cmbo_setScale.setEnabled(True)
                self.extra_header_text_label.setText('')
                # self.updateSkipMatchWidget()
                self.initView()
            cfg.project_tab.updateNeuroglancer()


    def update_match_point_snr(self):
        if cfg.project_tab:
            snr_report = cfg.data.snr_report()
            snr_report.replace('<', '&lt;')
            snr_report.replace('>', '&gt;')
            self.matchpoint_text_snr.setHtml(f'<h4>{snr_report}</h4>')

    def _update_lab_keep_reject(self, layer):
        base = 'Keep/Reject:'
        new = base + '\nSection #' + str(layer)
        self._lab_keep_reject.setText()


    def clear_match_points(self):
        if cfg.project_tab:
            logger.info('Clearing Match Points...')
            cfg.data.clear_match_points()
            self.dataUpdateWidgets()


    def print_all_matchpoints(self):
        if cfg.project_tab:
            cfg.data.print_all_matchpoints()


    def show_all_matchpoints(self):
        if cfg.project_tab:
            no_mps = True
            for i, l in enumerate(cfg.data.alstack()):
                r = l['images']['ref']['metadata']['match_points']
                b = l['images']['base']['metadata']['match_points']
                if r != []:
                    no_mps = False
                    self.tell(f'Layer: {i}, Ref, Match Points: {str(r)}')
                if b != []:
                    no_mps = False
                    self.tell(f'Layer: {i}, Base, Match Points: {str(b)}')
            if no_mps:
                self.tell('This project has no match points.')
            self.dataUpdateWidgets()


    def show_run_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.tell('\n\nWorking Directory     : %s\n'
                      'Running In (__file__) : %s' % (os.getcwd(), os.path.dirname(os.path.realpath(__file__))))


    def show_module_search_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.tell('\n\n' + '\n'.join(sys.path))


    def show_snr_list(self) -> None:
        if cfg.project_tab:
            s = cfg.data.curScale_val()
            lst = ' | '.join(map(str, cfg.data.snr_list()))
            self.tell('\n\nSNR List for Scale %d:\n%s\n' % (s, lst.split(' | ')))


    def show_zarr_info(self) -> None:
        if cfg.project_tab:
            z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
            self.tell('\n' + str(z.tree()) + '\n' + str(z.info))


    def show_zarr_info_aligned(self) -> None:
        if cfg.project_tab:
            z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
            self.tell('\n' + str(z.info) + '\n' + str(z.tree()))


    def show_zarr_info_source(self) -> None:
        if cfg.project_tab:
            z = zarr.open(os.path.join(cfg.data.dest(), 'img_src.zarr'))
            self.tell('\n' + str(z.info) + '\n' + str(z.tree()))


    def show_hide_developer_console(self):
        if self._dev_console.isHidden():
            self._dev_console.show()
        else:
            self._dev_console.hide()


    def set_mp_marker_lineweight(self):
        cfg.data['user_settings']['mp_marker_lineweight'] = self.mp_marker_lineweight_spinbox.value()
        if inspect.stack()[1].function != 'enterExitMatchPointMode':
            cfg.project_tab.updateNeuroglancer()


    def set_mp_marker_size(self):
        cfg.data['user_settings']['mp_marker_size'] = self.mp_marker_size_spinbox.value()
        if inspect.stack()[1].function != 'enterExitMatchPointMode':
            cfg.project_tab.updateNeuroglancer()


    def set_opacity(self, obj, val):
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(val)  # 0 to 1 -> fade effect
        obj.setGraphicsEffect(op)
        obj.setAutoFillBackground(True)


    def set_shader_none(self):
        cfg.SHADER = None
        cfg.project_tab.updateNeuroglancer()


    def set_shader_colormapJet(self):
        cfg.SHADER = src.shaders.colormapJet
        cfg.project_tab.updateNeuroglancer()


    def set_shader_test1(self):
        cfg.SHADER = src.shaders.shader_test1
        cfg.project_tab.updateNeuroglancer()


    def set_shader_test2(self):
        cfg.SHADER = src.shaders.shader_test2
        cfg.project_tab.updateNeuroglancer()

    def update(self):
        # get the radio button the send the signal
        rb = self.sender()

        # check if the radio button is checked
        if rb.isChecked():
            self.result_label.setText(f'You selected {rb.text()}')


    def initToolbar(self):
        logger.info('')
        height = int(18)

        self.toolbar = QToolBar()
        self.toolbar.setFixedHeight(34)
        self.toolbar.setObjectName('toolbar')
        self.addToolBar(self.toolbar)

        rb0 = QRadioButton('Stack')
        rb0.setChecked(True)
        rb0.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        rb0.toggled.connect(self.set_viewer_layout_0)

        rb1 = QRadioButton('Ref|Base|Aligned, Column')
        rb1.setChecked(False)
        rb1.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        rb1.toggled.connect(self.set_viewer_layout_1)

        rb2 = QRadioButton('Ref|Base|Aligned, Row')
        rb2.setChecked(False)
        rb2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        rb2.toggled.connect(self.set_viewer_layout_2)

        self._arrangeRadio = QWidget()
        hbl = QHBoxLayout()
        hbl.addWidget(rb0)
        hbl.addWidget(rb1)
        hbl.addWidget(rb2)
        self._arrangeRadio.setLayout(hbl)

        self._sectionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self._sectionSlider.valueChanged.connect(self.jump_to_slider)

        tip = 'Show Neuroglancer key bindings'
        self.info_button_buffer_label = QLabel(' ')
        self.info_button = QPushButton()
        self.info_button.setContentsMargins(2, 0, 2, 0)
        self.info_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.info_button.setStatusTip(tip)
        self.info_button.clicked.connect(self.html_keyboard_commands)
        self.info_button.setFixedSize(16, 16)
        self.info_button.setIcon(qta.icon("fa.info", color=cfg.ICON_COLOR))

        tip = 'Jump To Image #'
        lab = QLabel('Section #: ')
        lab.setObjectName('toolbar_layer_label')

        '''section # / jump-to lineedit'''
        self._jumpToLineedit = QLineEdit(self)
        self._jumpToLineedit.setFocusPolicy(Qt.ClickFocus)
        self._jumpToLineedit.setStatusTip(tip)
        self._jumpToLineedit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._jumpToLineedit.setFixedSize(QSize(46, height))
        self._jumpToLineedit.returnPressed.connect(lambda: self.jump_to_layer())
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._jumpToLineedit)
        self._jumpToSectionWidget = QWidget()
        self._jumpToSectionWidget.setLayout(hbl)
        # self.toolbar.addWidget(self._sectionSlider)

        '''NG arrangement/layout combobox'''
        self._cmbo_ngLayout = QComboBox()
        self._cmbo_ngLayout.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._cmbo_ngLayout.setFixedSize(QSize(64, height))
        self._cmbo_ngLayout.currentTextChanged.connect(self.fn_ng_layout_combobox)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self._cmbo_ngLayout)

        '''scale combobox'''
        self._ngLayoutWidget = QWidget()
        self._ngLayoutWidget.setLayout(hbl)
        self._cmbo_setScale = QComboBox(self)
        self._cmbo_setScale.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._cmbo_setScale.setFixedSize(QSize(90, height))
        self._cmbo_setScale.currentTextChanged.connect(self.fn_scales_combobox)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self._cmbo_setScale, alignment=Qt.AlignmentFlag.AlignRight)
        self._changeScaleCombobox = QWidget()
        self._changeScaleCombobox.setLayout(hbl)

        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # self.toolbar.addWidget(self._btn_view0)
        # self.toolbar.addWidget(self._btn_view1)
        # self.toolbar.addWidget(self._btn_view2)

        self.toolbar.addWidget(self._arrangeRadio)
        # self.toolbar.addWidget(self._sectionSlider)
        self.toolbar.addWidget(w)
        self.toolbar.addWidget(self._jumpToSectionWidget)
        self.toolbar.addWidget(self._sectionSlider)
        self.toolbar.addWidget(self._ngLayoutWidget)
        self.toolbar.addWidget(self._changeScaleCombobox)
        # self.toolbar.addWidget(self.info_button)
        self.toolbar.addWidget(self.info_button_buffer_label)

        # self.toolbar.setCursor(QCursor(Qt.PointingHandCursor))

    def updateStatusTips(self):
        self._btn_regenerate.setStatusTip('Generate All Layers,  Scale %d (affects Corrective Polynomial Bias '
                                            'and Bounding Rectangle)' % get_scale_val(cfg.data.curScale))
        self._btn_alignForward.setStatusTip(
            'Align + Generate Layers %d -> End,  Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.curScale)))
        self._btn_alignAll.setStatusTip('Generate + Align All Layers,  Scale %d' % get_scale_val(cfg.data.curScale))
        self._btn_alignOne.setStatusTip(
            'Align + Generate Layer %d,  Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.curScale)))


    def _disableAllOtherTabs(self):
        indexes = list(range(0, self._tabsGlob.count()))
        indexes.remove(self._tabsGlob.currentIndex())
        for i in indexes:
            self._tabsGlob.setTabEnabled(i, False)


    def _enableAllTabs(self):
        indexes = list(range(0, self._tabsGlob.count()))
        for i in indexes:
            self._tabsGlob.setTabEnabled(i, True)


    def _isProjectTab(self):
        if self._getTabType() == 'ProjectTab':
            return True
        else:
            return False


    def _isZarrTab(self):
        if self._getTabType() == 'ZarrTab':
            return True
        else:
            return False


    def _getTabObject(self):
        return self._tabsGlob.currentWidget()


    def _onGlobTabChange(self):
        caller = inspect.stack()[1].function
        logger.info(f'Tab Changed! (caller: {caller})')
        if self._tabsGlob.count() == 0:
            return
        if caller != 'new_project':
            if caller != 'open_project':
                if self._isProjectTab():
                    logger.info('New Project Tab...')
                    cfg.data = self._tabsGlob.currentWidget().datamodel
                    cfg.project_tab = self._tabsGlob.currentWidget()
                    cfg.zarr_tab = None
                    self._ID = id(cfg.project_tab.datamodel)
                    self._key = cfg.project_tab.key
                    self._path = cfg.project_tab.path
                    cfg.project_tab.initNeuroglancer()
                else:
                    logger.info('New Zarr Tab...')
                    cfg.data = None
                    cfg.project_tab = None
                    cfg.zarr_tab = self._tabsGlob.currentWidget()
                    self._ID = None
                    self._key = None
                    self._path = None
                    cfg.zarr_tab.initNeuroglancer()
                if self._isZarrTab():
                    logger.info(f'Switched to a Zarr tab...')

                self._updateJumpToValidator()
        self.set_idle()
        self._cur_tab_index = self._tabsGlob.currentIndex()


    def _onGlobTabClose(self, index):
        logger.info(f'Closing Tab: {index}')
        self._tabsGlob.removeTab(index)


    def _setLastTab(self):
        self._tabsGlob.setCurrentIndex(self._tabsGlob.count() - 1)


    def new_mendenhall_protocol(self):
        self.new_project(mendenhall=True)
        scale = cfg.data.scale()

        cfg.data['data']['cname'] = 'zstd'
        cfg.data['data']['clevel'] = 5
        cfg.data['data']['chunkshape'] = (1, 512, 512)
        cfg.data['data']['scales'][scale]['resolution_x'] = 2
        cfg.data['data']['scales'][scale]['resolution_y'] = 2
        cfg.data['data']['scales'][scale]['resolution_z'] = 50
        self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        self.mendenhall.set_directory()
        self.mendenhall.start_watching()
        cfg.data.set_source_path(self.mendenhall.sink)
        self._proj_saveToFile()


    def open_mendenhall_protocol(self):
        filename = open_project_dialog()
        with open(filename, 'r') as f:
            project = DataModel(json.load(f), mendenhall=True)
        cfg.data = copy.deepcopy(project)
        cfg.data.set_paths_absolute(filename=filename) #+
        self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        self.mendenhall.start_watching()
        cfg.project_tab.updateNeuroglancer()


    def stop_mendenhall_protocol(self):
        self.mendenhall.stop_watching()


    def aligned_mendenhall_protocol(self):
        cfg.MV = not cfg.MV
        logger.info(f'cfg.MA: {cfg.MV}')
        cfg.project_tab.updateNeuroglancer()


    def import_mendenhall_protocol(self):
        ''' Import images into data '''
        scale = 'scale_1'
        logger.info('Importing Images...')
        filenames = natural_sort(os.listdir(cfg.data.source_path()))
        self.tell('Import Images:')
        logger.info(f'filenames: {filenames}')
        # for i, f in enumerate(filenames):
        #     cfg.data.append_image(f, role_name='base')
        #     cfg.data.add_img(
        #         scale_key=s,
        #         layer_index=layer_index,
        #         role=role_name,
        #         filename=None
        #     )
        cfg.data.link_all_stacks()
        logger.info(f'source path: {cfg.data.source_path()}')
        self._proj_saveToFile()


    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

        fileMenu = self.menu.addMenu('File')

        alignmentMenu = fileMenu.addMenu("Alignment")

        self.newAction = QAction('&New Project...', self)
        self.newAction.triggered.connect(self.new_project)
        self.newAction.setShortcut('Ctrl+N')
        alignmentMenu.addAction(self.newAction)

        self.openAction = QAction('&Open Project...', self)
        self.openAction.triggered.connect(self.open_project)
        self.openAction.setShortcut('Ctrl+O')
        alignmentMenu.addAction(self.openAction)

        self.rescaleAction = QAction('Rescale...', self)
        self.rescaleAction.triggered.connect(self.rescale)
        alignmentMenu.addAction(self.rescaleAction)

        self.exportAfmAction = QAction('Export Affines', self)
        self.exportAfmAction.triggered.connect(self.export_afms)
        alignmentMenu.addAction(self.exportAfmAction)

        self.exportCafmAction = QAction('Export Cumulative Affines', self)
        self.exportCafmAction.triggered.connect(self.export_cafms)
        alignmentMenu.addAction(self.exportCafmAction)

        self.openArbitraryZarrAction = QAction('Open &Zarr...', self)
        self.openArbitraryZarrAction.triggered.connect(self.open_zarr)
        self.openArbitraryZarrAction.setShortcut('Ctrl+Z')
        fileMenu.addAction(self.openArbitraryZarrAction)

        # self.openFileBrowserAction = QAction('File Browser...', self)
        # self.openFileBrowserAction.triggered.connect(self.open_zarr)
        # fileMenu.addAction(self.openFileBrowserAction)

        self.saveAction = QAction('&Save', self)
        self.saveAction.triggered.connect(self.save)
        self.saveAction.setShortcut('Ctrl+S')
        fileMenu.addAction(self.saveAction)

        self.exitAppAction = QAction('&Quit', self)
        self.exitAppAction.triggered.connect(self.exit_app)
        self.exitAppAction.setShortcut('Ctrl+Q')
        fileMenu.addAction(self.exitAppAction)


        viewMenu = self.menu.addMenu('View')

        self.normalizeViewAction = QAction('Normalize', self)
        self.normalizeViewAction.triggered.connect(self.initView)
        viewMenu.addAction(self.normalizeViewAction)

        self.soloViewAction = QAction('Solo View', self)
        self.soloViewAction.triggered.connect(self.set_viewer_layout_0)
        viewMenu.addAction(self.soloViewAction)

        self.colViewAction = QAction('Column View', self)
        self.colViewAction.triggered.connect(self.set_viewer_layout_1)
        viewMenu.addAction(self.colViewAction)

        self.rowViewAction = QAction('Row View', self)
        self.rowViewAction.triggered.connect(self.set_viewer_layout_2)
        viewMenu.addAction(self.rowViewAction)

        self.splashAction = QAction('Splash', self)
        self.splashAction.triggered.connect(self.show_splash)
        viewMenu.addAction(self.splashAction)

        themeMenu = viewMenu.addMenu("Theme")

        self.theme1Action = QAction('Default', self)
        self.theme1Action.triggered.connect(self.apply_default_style)
        themeMenu.addAction(self.theme1Action)

        self.theme2Action = QAction('Morning', self)
        self.theme2Action.triggered.connect(self.apply_daylight_style)
        themeMenu.addAction(self.theme2Action)

        self.theme3Action = QAction('Evening', self)
        self.theme3Action.triggered.connect(self.apply_moonlit_style)
        themeMenu.addAction(self.theme3Action)

        self.theme4Action = QAction('Sagittarius', self)
        self.theme4Action.triggered.connect(self.apply_sagittarius_style)
        themeMenu.addAction(self.theme4Action)

        themeActionGroup = QActionGroup(self)
        themeActionGroup.setExclusive(True)
        themeActionGroup.addAction(self.theme1Action)
        themeActionGroup.addAction(self.theme2Action)
        themeActionGroup.addAction(self.theme3Action)
        themeActionGroup.addAction(self.theme4Action)
        self.theme1Action.setCheckable(True)
        self.theme1Action.setChecked(True)
        self.theme2Action.setCheckable(True)
        self.theme3Action.setCheckable(True)
        self.theme4Action.setCheckable(True)

        configMenu = self.menu.addMenu('Configure')

        self.projectConfigAction = QAction('Project', self)
        self.projectConfigAction.triggered.connect(self._dlg_cfg_project)
        configMenu.addAction(self.projectConfigAction)

        self.appConfigAction = QAction('Application', self)
        self.appConfigAction.triggered.connect(self._dlg_cfg_application)
        configMenu.addAction(self.appConfigAction)

        neuroglancerMenu = self.menu.addMenu('Neuroglancer')

        self.ngRestartAction = QAction('Reload', self)
        self.ngRestartAction.triggered.connect(self.restartNg)
        neuroglancerMenu.addAction(self.ngRestartAction)

        self.ngStopAction = QAction('Stop', self)
        self.ngStopAction.triggered.connect(self.stopNgServer)
        neuroglancerMenu.addAction(self.ngStopAction)

        ngLayoutMenu = neuroglancerMenu.addMenu("Layout")

        self.ngLayout1Action = QAction('xy', self)
        self.ngLayout2Action = QAction('xz', self)
        self.ngLayout3Action = QAction('yz', self)
        self.ngLayout4Action = QAction('yz-3d', self)
        self.ngLayout5Action = QAction('xy-3d', self)
        self.ngLayout6Action = QAction('xz-3d', self)
        self.ngLayout7Action = QAction('3d', self)
        self.ngLayout8Action = QAction('4panel', self)
        ngLayoutMenu.addAction(self.ngLayout1Action)
        ngLayoutMenu.addAction(self.ngLayout2Action)
        ngLayoutMenu.addAction(self.ngLayout3Action)
        ngLayoutMenu.addAction(self.ngLayout4Action)
        ngLayoutMenu.addAction(self.ngLayout5Action)
        ngLayoutMenu.addAction(self.ngLayout6Action)
        ngLayoutMenu.addAction(self.ngLayout7Action)
        ngLayoutMenu.addAction(self.ngLayout8Action)
        self.ngLayout1Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('xy'))
        self.ngLayout2Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('xz'))
        self.ngLayout3Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('yz'))
        self.ngLayout4Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('yz-3d'))
        self.ngLayout5Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('xy-3d'))
        self.ngLayout6Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('xz-3d'))
        self.ngLayout6Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('3d'))
        self.ngLayout8Action.triggered.connect(lambda: self._cmbo_ngLayout.setCurrentText('4panel'))
        ngLayoutActionGroup = QActionGroup(self)
        ngLayoutActionGroup.setExclusive(True)
        ngLayoutActionGroup.addAction(self.ngLayout1Action)
        ngLayoutActionGroup.addAction(self.ngLayout2Action)
        ngLayoutActionGroup.addAction(self.ngLayout3Action)
        ngLayoutActionGroup.addAction(self.ngLayout4Action)
        ngLayoutActionGroup.addAction(self.ngLayout5Action)
        ngLayoutActionGroup.addAction(self.ngLayout6Action)
        ngLayoutActionGroup.addAction(self.ngLayout7Action)
        ngLayoutActionGroup.addAction(self.ngLayout8Action)
        self.ngLayout1Action.setCheckable(True)
        self.ngLayout1Action.setChecked(True)
        self.ngLayout2Action.setCheckable(True)
        self.ngLayout3Action.setCheckable(True)
        self.ngLayout4Action.setCheckable(True)
        self.ngLayout5Action.setCheckable(True)
        self.ngLayout6Action.setCheckable(True)
        self.ngLayout7Action.setCheckable(True)
        self.ngLayout8Action.setCheckable(True)

        ngShaderMenu = neuroglancerMenu.addMenu("Shader")

        self.shader1Action = QAction('None', self)
        self.shader1Action.triggered.connect(self.set_shader_none)
        ngShaderMenu.addAction(self.shader1Action)

        self.shader2Action = QAction('colorMap Jet', self)
        self.shader2Action.triggered.connect(self.set_shader_colormapJet)
        ngShaderMenu.addAction(self.shader2Action)

        self.shader3Action = QAction('shader_test1', self)
        self.shader3Action.triggered.connect(self.set_shader_test1)
        ngShaderMenu.addAction(self.shader3Action)

        self.shader4Action = QAction('shader_test2', self)
        self.shader4Action.triggered.connect(self.set_shader_test2)
        ngShaderMenu.addAction(self.shader4Action)

        shaderActionGroup = QActionGroup(self)
        shaderActionGroup.setExclusive(True)
        shaderActionGroup.addAction(self.shader1Action)
        shaderActionGroup.addAction(self.shader2Action)
        shaderActionGroup.addAction(self.shader3Action)
        shaderActionGroup.addAction(self.shader4Action)
        self.shader1Action.setCheckable(True)
        self.shader1Action.setChecked(True)
        self.shader2Action.setCheckable(True)
        self.shader3Action.setCheckable(True)
        self.shader4Action.setCheckable(True)

        ngStateMenu = neuroglancerMenu.addMenu("Show State")

        self.ngShowStateJsonAction = QAction('JSON', self)
        self.ngShowStateJsonAction.triggered.connect(self.print_ng_state)
        ngStateMenu.addAction(self.ngShowStateJsonAction)

        self.ngShowStateUrlAction = QAction('State URL', self)
        self.ngShowStateUrlAction.triggered.connect(self.print_ng_state_url)
        ngStateMenu.addAction(self.ngShowStateUrlAction)

        self.ngShowRawStateAction = QAction('Raw State', self)
        self.ngShowRawStateAction.triggered.connect(self.print_ng_raw_state)
        ngStateMenu.addAction(self.ngShowRawStateAction)

        self.ngExtractEverythingAction = QAction('Everything', self)
        self.ngExtractEverythingAction.triggered.connect(self.dump_ng_details)
        ngStateMenu.addAction(self.ngExtractEverythingAction)

        self.ngInvalidateAction = QAction('Invalidate Local Volumes', self)
        self.ngInvalidateAction.triggered.connect(self.invalidate_all)
        neuroglancerMenu.addAction(self.ngInvalidateAction)

        # self.ngRefreshViewerAction = QAction('Recreate View', self)
        # self.ngRefreshViewerAction.triggered.connect(cfg.project_tab.openViewZarr)
        # neuroglancerMenu.addAction(self.ngRefreshViewerAction)

        # self.ngRefreshUrlAction = QAction('Refresh URL', self)
        # self.ngRefreshUrlAction.triggered.connect(self.refreshNeuroglancerURL)
        # neuroglancerMenu.addAction(self.ngRefreshUrlAction)

        self.ngGetUrlAction = QAction('Show URL', self)
        self.ngGetUrlAction.triggered.connect(self.display_actual_viewer_url)
        neuroglancerMenu.addAction(self.ngGetUrlAction)

        self.ngShowUiControlsAction = QAction('Show UI Controls', self)
        self.ngShowUiControlsAction.setShortcut('Ctrl+U')
        self.ngShowUiControlsAction.setCheckable(True)
        self.ngShowUiControlsAction.setChecked(cfg.SHOW_UI_CONTROLS)
        self.ngShowUiControlsAction.triggered.connect(self.ng_toggle_show_ui_controls)
        neuroglancerMenu.addAction(self.ngShowUiControlsAction)

        self.ngRemoteAction = QAction('External Client', self)
        self.ngRemoteAction.triggered.connect(self.remote_view)
        neuroglancerMenu.addAction(self.ngRemoteAction)

        # toolsMenu = self.menu.addMenu('Tools')

        alignMenu = self.menu.addMenu('Align')

        self.alignAllAction = QAction('Align All', self)
        self.alignAllAction.triggered.connect(lambda: self.align_all())
        self.alignAllAction.setShortcut('Ctrl+A')
        alignMenu.addAction(self.alignAllAction)

        self.alignOneAction = QAction('Align One', self)
        self.alignOneAction.triggered.connect(lambda: self.align_one())
        alignMenu.addAction(self.alignOneAction)

        self.alignForwardAction = QAction('Align Forward', self)
        self.alignForwardAction.triggered.connect(lambda: self.align_forward())
        alignMenu.addAction(self.alignForwardAction)

        self.alignMatchPointAction = QAction('Match Point Align', self)
        self.alignMatchPointAction.triggered.connect(self.enterExitMatchPointMode)
        self.alignMatchPointAction.setShortcut('Ctrl+M')
        alignMenu.addAction(self.alignMatchPointAction)

        mendenhallMenu = alignMenu.addMenu('Mendenhall Protocol')

        self.newMendenhallAction = QAction('New', self)
        self.newMendenhallAction.triggered.connect(self.new_mendenhall_protocol)
        mendenhallMenu.addAction(self.newMendenhallAction)

        self.openMendenhallAction = QAction('Open', self)
        self.openMendenhallAction.triggered.connect(self.open_mendenhall_protocol)
        mendenhallMenu.addAction(self.openMendenhallAction)

        self.importMendenhallAction = QAction('Import', self)
        self.importMendenhallAction.triggered.connect(self.import_mendenhall_protocol)
        mendenhallMenu.addAction(self.importMendenhallAction)

        self.alignedMendenhallAction = QAction('Sunny Side Up', self)
        self.alignedMendenhallAction.triggered.connect(self.aligned_mendenhall_protocol)
        mendenhallMenu.addAction(self.alignedMendenhallAction)

        self.stopMendenhallAction = QAction('Stop', self)
        self.stopMendenhallAction.triggered.connect(self.stop_mendenhall_protocol)
        mendenhallMenu.addAction(self.stopMendenhallAction)

        # self.skipChangeAction = QAction('Toggle Skip', self)
        # self.skipChangeAction.triggered.connect(self.skip_change_shortcut)
        # self.skipChangeAction.setShortcut('Ctrl+K')
        # toolsMenu.addAction(self.skipChangeAction)

        # self.jumpWorstSnrAction = QAction('Jump To Next Worst SNR', self)
        # self.jumpWorstSnrAction.triggered.connect(self.jump_to_worst_snr)
        # toolsMenu.addAction(self.jumpWorstSnrAction)
        #
        # self.jumpBestSnrAction = QAction('Jump To Next Best SNR', self)
        # self.jumpBestSnrAction.triggered.connect(self.jump_to_best_snr)
        # toolsMenu.addAction(self.jumpBestSnrAction)

        detailsMenu = self.menu.addMenu('Details')

        zarrMenu = detailsMenu.addMenu('Zarr Details')

        self.detailsZarrSourceAction = QAction('img_src.zarr', self)
        self.detailsZarrSourceAction.triggered.connect(self.show_zarr_info_source)
        zarrMenu.addAction(self.detailsZarrSourceAction)

        self.detailsZarrAlignedAction = QAction('img_aligned.zarr', self)
        self.detailsZarrAlignedAction.triggered.connect(self.show_zarr_info_aligned)
        zarrMenu.addAction(self.detailsZarrAlignedAction)

        self.moduleSearchPathAction = QAction('Show Module Search Path', self)
        self.moduleSearchPathAction.triggered.connect(self.show_module_search_path)
        detailsMenu.addAction(self.moduleSearchPathAction)

        self.runtimePathAction = QAction('Show Runtime Path', self)
        self.runtimePathAction.triggered.connect(self.show_run_path)
        detailsMenu.addAction(self.runtimePathAction)

        self.showMatchpointsAction = QAction('Show Matchpoints', self)
        self.showMatchpointsAction.triggered.connect(self.show_all_matchpoints)
        detailsMenu.addAction(self.showMatchpointsAction)

        debugMenu = self.menu.addMenu('Debug')

        tracemallocMenu = debugMenu.addMenu('tracemalloc')

        self.tracemallocStartAction = QAction('Start', self)
        self.tracemallocStartAction.triggered.connect(tracemalloc_start)
        tracemallocMenu.addAction(self.tracemallocStartAction)

        self.tracemallocCompareAction = QAction('Snapshot/Compare', self)
        self.tracemallocCompareAction.triggered.connect(tracemalloc_compare)
        tracemallocMenu.addAction(self.tracemallocCompareAction)

        self.tracemallocStopAction = QAction('Stop', self)
        self.tracemallocStopAction.triggered.connect(tracemalloc_stop)
        tracemallocMenu.addAction(self.tracemallocStopAction)

        self.tracemallocClearAction = QAction('Clear Traces', self)
        self.tracemallocClearAction.triggered.connect(tracemalloc_clear)
        tracemallocMenu.addAction(self.tracemallocClearAction)

        self.detailsWebglAction = QAction('Web GL Test', self)
        self.detailsWebglAction.triggered.connect(self.webgl2_test)
        debugMenu.addAction(self.detailsWebglAction)

        self.detailsGpuAction = QAction('GPU Configuration', self)
        self.detailsGpuAction.triggered.connect(self.gpu_config)
        debugMenu.addAction(self.detailsGpuAction)

        self.chromiumDebugAction = QAction('Chromium Debug', self)
        self.chromiumDebugAction.triggered.connect(self.chromium_debug)
        debugMenu.addAction(self.chromiumDebugAction)

        self.ngWebdriverLogAction = QAction('Show Webdriver Log', self)
        self.ngWebdriverLogAction.triggered.connect(self.show_webdriver_log)
        debugMenu.addAction(self.ngWebdriverLogAction)

        self.anableAllControlsAction = QAction('Enable All Controls', self)
        self.anableAllControlsAction.triggered.connect(self.enableAllButtons)
        debugMenu.addAction(self.anableAllControlsAction)

        self.printActiveThreadsAction = QAction('Show Active Threads', self)
        self.printActiveThreadsAction.triggered.connect(self.printActiveThreads)
        debugMenu.addAction(self.printActiveThreadsAction)

        if cfg.DEV_MODE:
            # developerMenu = debugMenu.addMenu('Developer')
            self.developerConsoleAction = QAction('Developer Console', self)
            self.developerConsoleAction.triggered.connect(self.show_hide_developer_console)
            debugMenu.addAction(self.developerConsoleAction)

        helpMenu = self.menu.addMenu('Help')

        self.documentationAction = QAction('Documentation', self)
        self.documentationAction.triggered.connect(self.documentation_view)
        helpMenu.addAction(self.documentationAction)

        self.keyboardCommandsAction = QAction('Keyboard Commands', self)
        self.keyboardCommandsAction.triggered.connect(self.html_keyboard_commands)
        self.keyboardCommandsAction.setShortcut('Ctrl+H')
        helpMenu.addAction(self.keyboardCommandsAction)

        swiftirMenu = helpMenu.addMenu('SWiFT-IR')

        self.swiftirComponentsAction = QAction('Remod Help', self)
        self.swiftirComponentsAction.triggered.connect(self.html_view)
        swiftirMenu.addAction(self.swiftirComponentsAction)

        self.swiftirCommandsAction = QAction('SWiFT-IR Commands', self)
        self.swiftirCommandsAction.triggered.connect(self.view_swiftir_commands)
        swiftirMenu.addAction(self.swiftirCommandsAction)

        self.swiftirExamplesAction = QAction('SWiFT-IR Examples', self)
        self.swiftirExamplesAction.triggered.connect(self.view_swiftir_examples)
        swiftirMenu.addAction(self.swiftirExamplesAction)

        self.reloadBrowserAction = QAction('Reload QtWebEngine', self)
        self.reloadBrowserAction.triggered.connect(self.browser_reload)
        helpMenu.addAction(self.reloadBrowserAction)

        self.googleAction = QAction('Google', self)
        self.googleAction.triggered.connect(self.google)
        helpMenu.addAction(self.googleAction)


    def initUI(self):
        '''Initialize Main UI'''
        logger.info('')

        std_height = 20
        # square_size = QSize(20, 20)
        std_input_size = QSize(66, std_height)
        std_button_size = QSize(96, std_height)
        normal_button_size = QSize(64, 24)
        slim_button_size = QSize(64, std_height)
        small_button_size = QSize(54, std_height)

        with open('src/styles/controls.qss', 'r') as f:
            lower_controls_style = f.read()

        '''Headup Display'''
        self.hud = HeadupDisplay(self.app)
        self.hud.setObjectName('hud')
        # path = 'src/resources/KeyboardCommands1.html'
        # with open(path) as f:
        #     contents = f.read()
        # self.hud.textedit.appendHtml(contents)
        self.tell('Welcome To AlignEM-SWiFT.')


        '''
        keyboard_commands = [
            QLabel('Keyboard Commands:'),
            QLabel('^N - New Project'),
            QLabel('^O - Open Project'),
            QLabel('^Z - Open Zarr'),
            QLabel('^S - Save'),
            QLabel('^Q - Quit'),
            QLabel('^↕ - Zoom'),
            QLabel(' , - Prev (comma)'),
            QLabel(' . - Next (period)'),
            QLabel(' ← - Scale Down'),
            QLabel(' → - Scale Up'),
            QLabel('^A - Align All'),
            QLabel('^K - Skip')
        ]
        
        '''

        keyboard_commands = [
            # QLabel('Keyboard Commands:'),
            QLabel('^N - New Project  ^O - Open Project  ^Z - Open Zarr'),
            QLabel('^S - Save         ^Q - Quit          ^↕ - Zoom'),
            QLabel(' , - Prev (comma)  . - Next (period) ^K - Skip'),
            QLabel(' ← - Scale Down    → - Scale Up      ^A - Align All'),
        ]
        f = QFont()
        f.setFamily('Courier')
        f.setPointSize(10)
        list(map(lambda x: x.setFont(f), keyboard_commands))
        list(map(lambda x: x.setContentsMargins(0,0,0,0), keyboard_commands))
        list(map(lambda x: x.setMargin(0), keyboard_commands))


        # self._tool_keyBindings = WidgetArea(parent=self, title='Keyboard Commands', labels=keyboard_commands)
        self._tool_keyBindings = WidgetArea(parent=self, labels=keyboard_commands)


        baseline = Qt.AlignmentFlag.AlignBaseline
        vcenter  = Qt.AlignmentFlag.AlignVCenter
        hcenter  = Qt.AlignmentFlag.AlignHCenter
        center   = Qt.AlignmentFlag.AlignCenter
        left     = Qt.AlignmentFlag.AlignLeft
        right    = Qt.AlignmentFlag.AlignRight

        self._tool_processMonitor = QWidget()
        lbl = QLabel('Process Monitor')
        lbl.setStyleSheet('font-size: 10px; font-weight: 500;')
        vbl = QVBoxLayout()
        vbl.setSpacing(1)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lbl, alignment=baseline)
        hbl = QHBoxLayout()
        hbl.addWidget(self.hud)
        hbl.addWidget(self._tool_keyBindings)
        vbl.addLayout(hbl)
        self._tool_processMonitor.setLayout(vbl)

        tip = 'Set Whether to Use or Reject the Current Layer'
        self._lab_keep_reject = QLabel('Keep/Reject:')
        self._lab_keep_reject.setStyleSheet('font-size: 10px; font-weight: 500;')
        self._lab_keep_reject.setStatusTip(tip)
        self._skipCheckbox = QCheckBox()
        self._skipCheckbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._skipCheckbox.setObjectName('_skipCheckbox')
        self._skipCheckbox.stateChanged.connect(self._callbk_skipChanged)
        self._skipCheckbox.stateChanged.connect(self._callbk_unsavedChanges)
        self._skipCheckbox.setStatusTip(tip)
        # self._skipCheckbox.setEnabled(False)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0,0,0,0)
        hbl.addWidget(self._lab_keep_reject, alignment=baseline)
        hbl.addWidget(self._skipCheckbox)
        self._ctlpanel_skip = QWidget()
        self._ctlpanel_skip.setLayout(hbl)

        tip = 'Use All Images (Reset)'
        self._btn_clear_skips = QPushButton('Reset')
        self._btn_clear_skips.setEnabled(False)
        self._btn_clear_skips.setStyleSheet("font-size: 10px;")
        self._btn_clear_skips.setStatusTip(tip)
        self._btn_clear_skips.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_clear_skips.clicked.connect(self.clear_skips)
        self._btn_clear_skips.setFixedSize(small_button_size)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        lab = QLabel("Whitening\nFactor:")
        lab.setAlignment(right | vcenter)
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        self._whiteningInput = QLineEdit(self)
        self._whiteningInput.textEdited.connect(self._callbk_unsavedChanges)
        self._whiteningInput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._whiteningInput.setText(str(cfg.DEFAULT_WHITENING))
        self._whiteningInput.setFixedSize(std_input_size)
        self._whiteningInput.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        lab.setStatusTip(tip)
        self._whiteningInput.setStatusTip(tip)
        gl = QGridLayout()
        gl.addWidget(lab, 0, 0)
        gl.addWidget(self._whiteningInput, 0, 1)
        gl.setContentsMargins(2, 0, 2, 0)
        # self._whiteningInput.setEnabled(False)
        self._ctlpanel_whitening = QWidget()
        self._ctlpanel_whitening.setLayout(gl)

        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        lab = QLabel("SWIM Window\n(%):")
        lab.setAlignment(right | vcenter)
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        self._swimInput = QLineEdit(self)
        self._swimInput.textEdited.connect(self._callbk_unsavedChanges)
        self._swimInput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._swimInput.setText(str(cfg.DEFAULT_SWIM_WINDOW))
        self._swimInput.setFixedSize(std_input_size)
        self._swimInput.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        lab.setStatusTip(tip)
        self._swimInput.setStatusTip(tip)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(lab)
        hbl.addWidget(self._swimInput)
        # self._swimInput.setEnabled(False)
        self._ctlpanel_inp_swimWindow = QWidget()
        self._ctlpanel_inp_swimWindow.setLayout(hbl)

        # tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        self._ctlpanel_applyAllButton = QPushButton("Apply All")
        self._ctlpanel_applyAllButton.setEnabled(False)
        self._ctlpanel_applyAllButton.setStatusTip('Apply These Settings To The Entire Project')
        self._ctlpanel_applyAllButton.setStyleSheet("font-size: 10px;")
        self._ctlpanel_applyAllButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._ctlpanel_applyAllButton.clicked.connect(self.apply_all)
        self._ctlpanel_applyAllButton.setFixedSize(small_button_size)

        self._gb_alignmentSettings = QGroupBox()
        hbl = QHBoxLayout()
        hbl.addWidget(self._ctlpanel_inp_swimWindow)
        hbl.addWidget(self._ctlpanel_whitening)
        hbl.addWidget(self._ctlpanel_applyAllButton)

        tip = 'Go To Next Scale.'
        self._scaleUpButton = QPushButton()
        self._scaleUpButton.setEnabled(False)
        self._scaleUpButton.setStyleSheet("font-size: 11px;")
        self._scaleUpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleUpButton.setStatusTip(tip)
        self._scaleUpButton.clicked.connect(self.scale_up)
        self._scaleUpButton.setFixedSize(QSize(20, 20))
        self._scaleUpButton.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        tip = 'Go To Previous Scale.'
        self._scaleDownButton = QPushButton()
        self._scaleDownButton.setEnabled(False)
        self._scaleDownButton.setStyleSheet("font-size: 11px;")
        self._scaleDownButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleDownButton.setStatusTip(tip)
        self._scaleDownButton.clicked.connect(self.scale_down)
        self._scaleDownButton.setFixedSize(QSize(20, 20))
        self._scaleDownButton.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        self._scaleSetWidget = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 0, 2, 0)
        self._scaleSetWidget.setLayout(hbl)
        hbl.addWidget(self._scaleDownButton, alignment=right)
        hbl.addWidget(self._scaleUpButton, alignment=right)

        lab = QLabel('Scale:')
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        self._ctlpanel_changeScale = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0,0,0,0)
        vbl.setSpacing(0)
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self._scaleSetWidget)
        self._ctlpanel_changeScale.setLayout(vbl)


        tip = 'Align + Generate All Layers For Current Scale'
        self._btn_alignAll = QPushButton('Align This\nScale')
        self._btn_alignAll.setEnabled(False)
        self._btn_alignAll.setStyleSheet("font-size: 9px;")
        self._btn_alignAll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignAll.setStatusTip(tip)
        self._btn_alignAll.clicked.connect(lambda: self.align_all(scale=cfg.data.curScale))
        self._btn_alignAll.setFixedSize(normal_button_size)

        tip = 'Align and Generate This Layer'
        self._btn_alignOne = QPushButton('Align This\nSection')
        self._btn_alignOne.setEnabled(False)
        self._btn_alignOne.setStyleSheet("font-size: 9px;")
        self._btn_alignOne.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignOne.setStatusTip(tip)
        self._btn_alignOne.clicked.connect(lambda: self.align_one(scale=cfg.data.curScale))
        self._btn_alignOne.setFixedSize(normal_button_size)

        tip = 'Align and Generate From Layer Current Layer to End'
        self._btn_alignForward = QPushButton('Align\nForward')
        self._btn_alignForward.setEnabled(False)
        self._btn_alignForward.setStyleSheet("font-size: 9px;")
        self._btn_alignForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignForward.setStatusTip(tip)
        self._btn_alignForward.clicked.connect(lambda: self.align_forward(scale=cfg.data.curScale))
        self._btn_alignForward.setFixedSize(normal_button_size)

        tip = 'Automatically generate aligned images.'
        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.toggle_auto_generate = ToggleSwitch()
        self.toggle_auto_generate.stateChanged.connect(self._callbk_unsavedChanges)
        self.auto_generate_label.setStatusTip(tip)
        self.toggle_auto_generate.setStatusTip(tip)
        self.toggle_auto_generate.setChecked(True)
        # self.toggle_auto_generate.toggled.connect(self.toggle_auto_generate_callback)
        self.toggle_auto_generate.toggled.connect(lambda: self.toggle_auto_generate_callback())
        self.toggle_auto_generate_hlayout = QHBoxLayout()
        self.toggle_auto_generate_hlayout.addWidget(self.auto_generate_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.toggle_auto_generate_hlayout.addWidget(self.toggle_auto_generate, alignment=Qt.AlignmentFlag.AlignVCenter)
        # self.toggle_auto_generate.setEnabled(False)

        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension. This' \
              ' option is set at the coarsest s, in order to form a contiguous dataset.'
        lab = QLabel("Corrective\nPolynomial:")
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        lab.setStatusTip(tip)
        self._cmbo_polynomialBias = QComboBox(self)
        self._cmbo_polynomialBias.setStyleSheet("font-size: 11px;")
        self._cmbo_polynomialBias.currentIndexChanged.connect(self._callbk_unsavedChanges)
        self._cmbo_polynomialBias.setStatusTip(tip)
        self._cmbo_polynomialBias.addItems(['None', '0', '1', '2', '3', '4'])
        self._cmbo_polynomialBias.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self._cmbo_polynomialBias.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._cmbo_polynomialBias.setFixedSize(QSize(60, 20))
        # self._cmbo_polynomialBias.setEnabled(False)
        vbl = QHBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lab)
        vbl.addWidget(self._cmbo_polynomialBias)
        self._ctlpanel_polyOrder = QWidget()
        self._ctlpanel_polyOrder.setLayout(vbl)


        tip = 'Bounding rectangle (default=ON). Caution: Turning this ON may ' \
              'significantly increase the size of your aligned images.'
        lab = QLabel("Bounding\nBox:")
        lab.setAlignment(right | vcenter)
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        lab.setStatusTip(tip)
        self._bbToggle = ToggleSwitch()
        # self._bbToggle.setChecked(True)
        self._bbToggle.setStatusTip(tip)
        self._bbToggle.toggled.connect(self._callbk_bnding_box)
        hbl = QHBoxLayout()
        hbl.setSpacing(1)
        hbl.setContentsMargins(0,0,0,0)
        # hbl.addWidget(lab, alignment=baseline | Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._bbToggle)
        # self._bbToggle.setEnabled(False)
        self._ctlpanel_bb = QWidget()
        self._ctlpanel_bb.setLayout(hbl)

        tip = "Recomputes the cumulative affine and generates new aligned images" \
              "based on the current Null Bias and Bounding Rectangle presets."
        self._btn_regenerate = QPushButton('Regenerate')
        self._btn_regenerate.setEnabled(False)
        self._btn_regenerate.setStatusTip(tip)
        self._btn_regenerate.clicked.connect(lambda: self.regenerate(scale=cfg.data.curScale))
        self._btn_regenerate.setFixedSize(normal_button_size)
        self._btn_regenerate.setStyleSheet("font-size: 9px;")

        self._wdg_alignButtons = QWidget()
        hbl = QHBoxLayout()
        hbl.addWidget(self._btn_regenerate)
        hbl.addWidget(self._btn_alignOne)
        hbl.addWidget(self._btn_alignForward)
        hbl.addWidget(self._btn_alignAll)
        self._wdg_alignButtons.setLayout(hbl)
        hbl.setContentsMargins(2, 0, 2, 0)
        lab = QLabel('One-click Procedures (Highly Parallel)')
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')

        vbl = QVBoxLayout()
        vbl.setSpacing(1)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self._wdg_alignButtons)
        self._ctlpanel_alignRegenButtons = QWidget()
        self._ctlpanel_alignRegenButtons.setLayout(vbl)

        wids = [
            self._ctlpanel_skip,
            self._ctlpanel_inp_swimWindow,
            self._ctlpanel_whitening,
            self._ctlpanel_applyAllButton,
            self._ctlpanel_polyOrder,
            self._ctlpanel_bb,
            self._ctlpanel_alignRegenButtons,
            self._ctlpanel_changeScale,
        ]

        self._ctl_panel = ControlPanel(
            parent=self,
            name='ctl_panel',
            title='Control Panel',
            items=wids,
            bg_color='#f3f6fb'
        )

        '''
                    self.layer_details.setText(f"{name}{skip}"
                                                 f"{bb_dims}"
                                                 f"{snr}"
                                                 f"{completed}"
                                                 f"<b>Skipped Layers:</b> [{skips}]<br>"
                                                 f"<b>Match Point Layers:</b> [{matchpoints}]"
        '''


        self._layer_details = (
            QLabel('Name :'),
            QLabel('Bounds :'),
            QLabel('SNR :'),
            QLabel('Progress :'),
            QLabel('Rejected Layer :'),
            QLabel('Matchpoints :'),
        )
        self._tool_textInfo_NEW = WidgetArea(parent=self, title='Details', labels=self._layer_details)

        lab = QLabel('Details')
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        self.layer_details = QTextEdit()
        self.layer_details.setObjectName('layer_details')
        self.layer_details.setReadOnly(True)
        self._tool_textInfo = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self.layer_details)
        self._tool_textInfo.setLayout(vbl)

        self._tool_hstry = QWidget()
        # self._tool_hstry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tool_hstry.setObjectName('_tool_hstry')
        self._hstry_listWidget = QListWidget()
        # self._hstry_listWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._hstry_listWidget.setObjectName('_hstry_listWidget')
        self._hstry_listWidget.installEventFilter(self)
        self._hstry_listWidget.itemClicked.connect(self.historyItemClicked)
        lab = QLabel('History')
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        vbl = QVBoxLayout()
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self._hstry_listWidget)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        self._tool_hstry.setLayout(vbl)

        self._hstry_treeview = QTreeView()
        self._hstry_treeview.setStyleSheet('background-color: #ffffff;')
        self._hstry_treeview.setObjectName('_treeview')
        self.projecthistory_model = JsonModel()
        self._hstry_treeview.setModel(self.projecthistory_model)
        self._hstry_treeview.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._hstry_treeview.setAlternatingRowColors(True)
        self.exit_projecthistory_view_button = QPushButton("Back")
        self.exit_projecthistory_view_button.setFixedSize(slim_button_size)
        self.exit_projecthistory_view_button.clicked.connect(self.back_callback)
        gl = QGridLayout()
        gl.addWidget(self._hstry_treeview, 0, 0, 1, 2)
        gl.addWidget(self.exit_projecthistory_view_button, 1, 0, 1, 1)
        self.historyview_widget = QWidget()
        self.historyview_widget.setObjectName('historyview_widget')
        self.historyview_widget.setLayout(gl)

        '''AFM/CAFM Widget'''
        lab = QLabel('Transformation')
        lab.setStyleSheet('font-size: 10px; font-weight: 500;')
        lab.setObjectName('label_afm')
        self.afm_widget_ = QTextEdit()
        self.afm_widget_.setObjectName('_tool_afmCafm')
        self.afm_widget_.setReadOnly(True)
        self._tool_afmCafm = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self.afm_widget_)
        self._tool_afmCafm.setLayout(vbl)

        self.ng_widget = QWidget()
        self.ng_widget.setObjectName('ng_widget')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)

        self.splash_widget = QWidget()  # Todo refactor this it is not in use
        self.splash_widget.setObjectName('splash_widget')
        self.splashmovie = QMovie('src/resources/alignem_animation.gif')
        self.splashlabel = QLabel()
        self.splashlabel.setMovie(self.splashmovie)
        self.splashlabel.setMinimumSize(QSize(100, 100))
        gl = QGridLayout()
        gl.addWidget(self.splashlabel, 1, 1, 1, 1)
        self.splash_widget.setLayout(gl)
        self.splash_widget.setGraphicsEffect(QGraphicsOpacityEffect().setOpacity(0.7))
        self.splashmovie.finished.connect(lambda: self.runaftersplash())

        self.permFileBrowser = FileBrowser()

        self.viewer_stack_widget = QStackedWidget()
        self.viewer_stack_widget.setObjectName('viewer_stack_widget')
        self.viewer_stack_widget.addWidget(self.ng_widget)
        self.viewer_stack_widget.addWidget(self.splash_widget)
        self.viewer_stack_widget.addWidget(self.permFileBrowser)
        # self.viewer_stack_widget.addWidget(self.historyview_widget)


        self._matchpt_ctls = QWidget()

        self.mp_marker_size_label = QLabel('Lineweight')
        self.mp_marker_size_spinbox = QSpinBox()
        self.mp_marker_size_spinbox.setMinimum(0)
        self.mp_marker_size_spinbox.setMaximum(32)
        self.mp_marker_size_spinbox.setSuffix('pt')
        self.mp_marker_size_spinbox.valueChanged.connect(self.set_mp_marker_size)

        self.mp_marker_lineweight_label = QLabel('Size')
        self.mp_marker_lineweight_spinbox = QSpinBox()
        self.mp_marker_lineweight_spinbox.setMinimum(0)
        self.mp_marker_lineweight_spinbox.setMaximum(32)
        self.mp_marker_lineweight_spinbox.setSuffix('pt')
        self.mp_marker_lineweight_spinbox.valueChanged.connect(self.set_mp_marker_lineweight)

        self.exit_matchpoint_button = QPushButton('Exit')
        self.exit_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_matchpoint_button.clicked.connect(self.enterExitMatchPointMode)
        self.exit_matchpoint_button.setFixedSize(normal_button_size)

        self.realign_matchpoint_button = QPushButton('Realign\nLayer')
        self.realign_matchpoint_button.setStyleSheet("font-size: 11px;")
        self.realign_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.realign_matchpoint_button.clicked.connect(lambda: self.align_one(scale=cfg.data.curScale))
        self.realign_matchpoint_button.setFixedSize(normal_button_size)

        hbl = QHBoxLayout()
        hbl.addWidget(self.exit_matchpoint_button)
        hbl.addWidget(self.realign_matchpoint_button)
        hbl.addWidget(self.mp_marker_size_label)
        hbl.addWidget(self.mp_marker_size_spinbox)
        hbl.addWidget(self.mp_marker_lineweight_label)
        hbl.addWidget(self.mp_marker_lineweight_spinbox)
        hbl.addStretch()
        vbl = QVBoxLayout()
        self.matchpoint_text_snr = QTextEdit()
        self.matchpoint_text_snr.setObjectName('matchpoint_text_snr')
        self.matchpoint_text_prompt = QTextEdit()
        self.matchpoint_text_prompt.setObjectName('matchpoint_text_prompt')
        self.matchpoint_text_prompt.setHtml("Select 3-5 corresponding match points on the reference and base images. Key Bindings:<br>"
                                            "<b>Enter/return</b> - Add match points (Left, Right, Left, Right...)<br>"
                                            "<b>s</b>            - Save match points<br>"
                                            "<b>c</b>            - Clear match points for this layer")
        self.matchpoint_text_prompt.setReadOnly(True)
        vbl.addLayout(hbl)
        vbl.addWidget(self.matchpoint_text_snr)
        vbl.addWidget(self.matchpoint_text_prompt)
        vbl.addStretch()
        self._matchpt_ctls.setLayout(vbl)
        self._matchpt_ctls.hide()


        '''Show/Hide Primary Tools Buttons'''
        show_hide_button_sizes = QSize(102, 18)

        tip = 'Show/Hide Alignment Controls'
        self._btn_show_hide_ctls = QPushButton('Hide Controls')
        self._btn_show_hide_ctls.setObjectName('_btn_show_hide_ctls')
        self._btn_show_hide_ctls.setStyleSheet(lower_controls_style)
        self._btn_show_hide_ctls.setStatusTip(tip)
        self._btn_show_hide_ctls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_show_hide_ctls.clicked.connect(self._callbk_showHideControls)
        self._btn_show_hide_ctls.setFixedSize(show_hide_button_sizes)
        self._btn_show_hide_ctls.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Python Console'
        self._btn_show_hide_console = QPushButton(' Python')
        self._btn_show_hide_console.setObjectName('_btn_show_hide_console')
        self._btn_show_hide_console.setStyleSheet(lower_controls_style)
        self._btn_show_hide_console.setStatusTip(tip)
        self._btn_show_hide_console.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_show_hide_console.clicked.connect(self._callbk_showHidePython)
        self._btn_show_hide_console.setFixedSize(show_hide_button_sizes)
        self._btn_show_hide_console.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))

        self._showHideFeatures = QWidget()
        self._showHideFeatures.setObjectName('_showHideFeatures')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 4, 4, 4)
        hbl.addWidget(self._btn_show_hide_ctls, alignment=Qt.AlignLeft | Qt.AlignBottom)
        hbl.addWidget(self._btn_show_hide_console, alignment=Qt.AlignLeft | Qt.AlignBottom)
        # hbl.addStretch()
        self._showHideFeatures.setLayout(hbl)
        self._showHideFeatures.setMaximumHeight(26)

        '''Tabs Global Widget'''
        self._tabsGlob = QTabWidget()
        self._tabsGlob.setDocumentMode(True)
        self._tabsGlob.setTabsClosable(True)
        self._tabsGlob.setObjectName('_tabsGlob')
        self._tabsGlob.tabCloseRequested[int].connect(self._onGlobTabClose)
        self._tabsGlob.currentChanged.connect(self._onGlobTabChange)


        '''Bottom Horizontal Splitter'''
        self._tools_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._tools_splitter.setContentsMargins(4, 0, 4, 0)
        # self._tools_splitter.setMaximumHeight(90)
        # self._tools_splitter.setMaximumHeight(110)
        self._tools_splitter.setHandleWidth(1)
        widgets = [
            self._tool_processMonitor,
            self._tool_textInfo,
            # self._tool_textInfo_NEW,
            self._tool_afmCafm,
            self._tool_hstry

        ]
        for i, w in enumerate(widgets):
            self._tools_splitter.addWidget(w)
            self._tools_splitter.setCollapsible(i, True)
            if i != 0:
                w.hide()



        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        # _ctl_panel_layout.addStretch()
        # vbl.addWidget(self._ctl_panel, alignment=Qt.AlignBottom)
        # vbl.addWidget(self._tools_splitter, alignment=Qt.AlignBottom)
        vbl.addWidget(self._ctl_panel)
        vbl.addWidget(self._tools_splitter)
        self.ctl_panel_and_tools = QWidget()
        self.ctl_panel_and_tools.setLayout(vbl)

        '''Main Vertical Splitter'''
        self._splitter = QSplitter(Qt.Orientation.Vertical)    # __SPLITTER INDEX__
        self._splitter.addWidget(self._tabsGlob)               # (0)
        self._splitter.addWidget(self.ctl_panel_and_tools)     # (1)
        self._splitter.addWidget(self._matchpt_ctls)           # (2)
        self._splitter.addWidget(self._py_console)             # (3)
        self._splitter.setSizes([800, 300, 160, 160])

        if cfg.DEV_MODE:
            self._dev_console = PythonConsole()
            self._splitter.addWidget(self._dev_console)           # (5)
            self._dev_console.hide()
        else:
            self._dev_console = None
        self._splitter.addWidget(self._showHideFeatures)  # (6)
        self._splitter.setHandleWidth(1)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, False)
        self._splitter.setCollapsible(3, False)
        self._splitter.setStretchFactor(0, 7)
        self._splitter.setStretchFactor(1, 1)

        '''Documentation Panel'''
        self.browser_docs = QWebEngineView()
        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(std_button_size)
        self.exit_docs_button.clicked.connect(self.exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(std_button_size)
        self.readme_button.clicked.connect(self.documentation_view_home)
        self.docs_panel = QWidget()
        vbl = QVBoxLayout()
        vbl.addWidget(self.browser_docs)
        hbl = QHBoxLayout()
        hbl.addWidget(self.exit_docs_button, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(self.readme_button, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # hbl.addSpacerItem(self.spacer_item_docs)
        vbl.addLayout(hbl)
        self.docs_panel.setLayout(vbl)

        '''Remote Neuroglancer Viewer (_wdg_remote_viewer)'''
        self._wdg_remote_viewer = QWidget()
        self.browser_remote = QWebEngineView()
        self._btn_remote_exit = QPushButton('Back')
        self._btn_remote_exit.setFixedSize(std_button_size)
        self._btn_remote_exit.clicked.connect(self.exit_remote)
        self._btn_remote_reload = QPushButton('Reload')
        self._btn_remote_reload.setFixedSize(std_button_size)
        self._btn_remote_reload.clicked.connect(self.reload_remote)

        vbl = QVBoxLayout()
        vbl.addWidget(self.browser_remote)
        hbl = QHBoxLayout()
        hbl.addWidget(self._btn_remote_exit, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(self._btn_remote_reload, alignment=Qt.AlignmentFlag.AlignLeft)
        # hbl.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        vbl.addLayout(hbl)
        self._wdg_remote_viewer.setLayout(vbl)

        '''Demos Panel (_wdg_demos)'''
        self._wdg_demos = QWidget()
        self._btn_demos_exit = QPushButton('Back')
        self._btn_demos_exit.setFixedSize(std_button_size)
        self._btn_demos_exit.clicked.connect(self.exit_demos)

        vbl = QVBoxLayout()
        hbl = QHBoxLayout()
        hbl.addWidget(self._btn_demos_exit)
        vbl.addLayout(hbl)
        self._wdg_demos.setLayout(vbl)
        self.main_panel = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._splitter)
        vbl.addWidget(self._showHideFeatures, alignment=Qt.AlignmentFlag.AlignLeft)

        #Todo keep this main_stack_widget for now, repurpose later
        self.main_stack_widget = QStackedWidget(self)               #____INDEX____
        self.main_stack_widget.addWidget(self.main_panel)           # (0)
        self.main_stack_widget.addWidget(self.docs_panel)           # (1)
        self.main_stack_widget.addWidget(self._wdg_demos)           # (2)
        self.main_stack_widget.addWidget(self._wdg_remote_viewer)   # (3)
        self.main_panel.setLayout(vbl)
        self.setCentralWidget(self.main_stack_widget)


    def get_application_root(self):
        return Path(__file__).parents[2]


    def initWidgetSpacing(self):
        logger.info('')
        self._py_console.setContentsMargins(0, 0, 0, 0)
        self.hud.setContentsMargins(2, 0, 2, 0)
        self.layer_details.setContentsMargins(0, 0, 0, 0)
        self.matchpoint_text_snr.setMaximumHeight(20)
        self._tool_hstry.setMinimumWidth(248)
        self._tool_afmCafm.setFixedWidth(248)
        self.layer_details.setMinimumWidth(248)


    def initStatusBar(self):
        logger.info('')
        self.statusBar = self.statusBar()
        self.statusBar.setFixedHeight(30)


    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(True)
        self.pbar.setFont(QFont('Arial', 11))
        self.pbar.setFixedHeight(18)
        self.pbar.setFixedWidth(500)
        self.pbar_widget = QWidget(self)
        self.status_bar_layout = QHBoxLayout()
        self.status_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.pbar_widget.setLayout(self.status_bar_layout)
        self.status_bar_layout.addWidget(QLabel('Progress: '), alignment=Qt.AlignmentFlag.AlignRight)
        self.status_bar_layout.addWidget(self.pbar)
        self.statusBar.addPermanentWidget(self.pbar_widget)
        self.pbar_widget.hide()


    def pbar_max(self, x):
        self.pbar.setMaximum(x)


    def pbar_update(self, x):
        self.pbar.setValue(x)


    def setPbarText(self, text: str):
        self.pbar.setFormat('(%p%) ' + text)


    def showZeroedPbar(self):
        self.pbar.setValue(0)
        self.setPbarText('Preparing Multiprocessing Tasks...')
        self.pbar_widget.show()


    @Slot()
    def set_idle(self) -> None:
        if self._working == False:
            self.statusBar.showMessage('Idle')
        pass


    @Slot()
    def set_busy(self) -> None:
        self.statusBar.showMessage('Busy...')


    def back_callback(self):
        logger.info("Returning Home...")
        self.main_stack_widget.setCurrentIndex(0)
        self.viewer_stack_widget.setCurrentIndex(0)


    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self._hstry_listWidget:
            menu = QMenu()
            self.history_view_action = QAction('View')
            self.history_view_action.setStatusTip('View this alignment as a tree view')
            self.history_view_action.triggered.connect(self.view_historical_alignment)
            self.history_swap_action = QAction('Swap')
            self.history_swap_action.setStatusTip('Swap the settings of this historical alignment '
                                                  'with your current s settings')
            self.history_swap_action.triggered.connect(self.swap_historical_alignment)
            self.history_rename_action = QAction('Rename')
            self.history_rename_action.setStatusTip('Rename this file')
            self.history_rename_action.triggered.connect(self.rename_historical_alignment)
            self.history_delete_action = QAction('Delete')
            self.history_delete_action.setStatusTip('Delete this file')
            self.history_delete_action.triggered.connect(self.remove_historical_alignment)
            menu.addAction(self.history_view_action)
            menu.addAction(self.history_rename_action)
            menu.addAction(self.history_swap_action)
            menu.addAction(self.history_delete_action)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
                logger.info(f'Item Text: {item.text()}')
            return True
        return super().eventFilter(source, event)



# NOTES
# jumpt to section 0 from SNR plot