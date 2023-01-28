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
import textwrap
import tracemalloc
import timeit
import getpass
from pathlib import Path
import zarr
import dis
import stat
import psutil
import resource
from collections import namedtuple
import numpy as np
# from guppy import hpy; h=hpy()
import neuroglancer as ng
import pyqtgraph.console
import pyqtgraph as pg
import qtawesome as qta
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QTimer
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QKeySequence, QMovie
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QInputDialog, QLineEdit, QPushButton, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QCheckBox, QSpinBox, QDoubleSpinBox, QRadioButton, QSlider, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView, QTabWidget, QStatusBar, QTextBrowser, \
    QFormLayout, QGroupBox, QScrollArea, QToolButton, QWidgetAction, QSpacerItem

import src.config as cfg
import src.shaders
from src.background_worker import BackgroundWorker
from src.compute_affines import compute_affines
from src.config import ICON_COLOR
from src.data_model import DataModel
from src.funcs_zarr import tiffs2MultiTiff
from src.generate_aligned import generate_aligned
from src.generate_scales import generate_scales
from src.thumbnailer import Thumbnailer
from src.generate_scales_zarr import generate_zarr_scales
from src.helpers import setOpt, getOpt, print_exception, get_scale_val, natural_sort, make_affine_widget_HTML, \
    is_tacc, create_project_structure_directories, get_scales_with_generated_alignments, tracemalloc_start, \
    tracemalloc_stop, tracemalloc_compare, tracemalloc_clear, show_status_report, exist_aligned_zarr_cur_scale, \
    makedirs_exist_ok, are_aligned_images_generated, exist_aligned_zarr, validate_selection, \
    configure_project_paths, handleError, append_project_path, isNeuroglancerRunning, count_widgets, \
    find_allocated_widgets, cleanup_project_list
from src.ui.dialogs import AskContinueDialog, ConfigProjectDialog, ConfigAppDialog, QFileDialogPreview, \
    import_images_dialog, new_project_dialog, open_project_dialog, export_affines_dialog, mendenhall_dialog
from src.ui.process_monitor import HeadupDisplay
from src.ui.kimage_window import KImageWindow
from src.ui.models.json_tree import JsonModel
from src.ui.toggle_switch import ToggleSwitch
from src.ui.widget_area import WidgetArea
from src.ui.control_panel import ControlPanel
from src.ui.file_browser import FileBrowser
from src.ui.tab_project import ProjectTab
from src.ui.tab_zarr import ZarrTab
from src.ui.webpage import WebPage
from src.ui.tab_browser import WebBrowser
from src.ng_host import NgHost
from src.ng_host_slim import NgHostSlim
from src.ui.tab_open_project import OpenProject
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
        self._mainVSplitterSizes = [800, 160, 160, 160]
        cfg.thumb = Thumbnailer()
        # self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.initImageAllocations()
        self.initPrivateMembers()
        # self.initThreadpool(timeout=3000)
        self.initThreadpool()
        self.initOpenGlContext()
        self.initPythonConsole()
        self.initStatusBar()
        self.initPbar()
        self.initToolbar()
        self.initControlPanel()
        self.initUI()
        self.initMenu()
        self.initWidgetSpacing()
        self.initStyle()
        self.initShortcuts()
        # self.initData()
        # self.initView()
        self.initSizeAndPos(cfg.WIDTH, cfg.HEIGHT)
        self.set_idle()

        self.initLaunchTab()

        if not cfg.NO_SPLASH:
            self.show_splash()

        # if cfg.DEV_MODE:
        #     self.profilingTimerButton.click()


    def initSizeAndPos(self, width, height):
        self.resize(width, height)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def resizeEvent(self, event):
        if not self._working:
            self.resized.emit()
            if cfg.project_tab:
                cfg.project_tab.initNeuroglancer()
            return super(MainWindow, self).resizeEvent(event)


    def setAppropriateNgLayout(self):
        current_text = self._cmbo_ngLayout.currentText()
        if self.rb0.isChecked():
            if current_text != '4panel':
                logger.warning('Snapping current combobox text to 4panel')
                self._cmbo_ngLayout.setCurrentText('4panel')
        elif self.rb1.isChecked():
            if current_text != 'xy':
                logger.warning('Snapping current combobox text to xy')
                self._cmbo_ngLayout.setCurrentText('xy')


    def neuroglancer_configuration_0(self):
        logger.info('')
        if cfg.data:
            if cfg.project_tab:
                cfg.project_tab._overlayBottomLeft.hide()
                cfg.project_tab._overlayLab.hide()
                cfg.project_tab._overlayRect.hide()
                self._jumpToLineedit.setText(str(cfg.data.layer()))
                self._cmbo_ngLayout.setCurrentText('4panel')
                # cfg.project_tab._overlayNotification.show()
                cfg.project_tab._widgetArea_details.show()
                cfg.project_tab.initNeuroglancer()


    def neuroglancer_configuration_1(self):
        logger.info('')
        if cfg.data:
            if cfg.project_tab:
                self._cmbo_ngLayout.setCurrentText('xy')
                cfg.project_tab._widgetArea_details.show()
                try:
                    cfg.project_tab.initNeuroglancer()
                except:
                    print_exception()
                    self.warn('There was a problem loading Side-by-side layout')
                    self.rb0.setChecked(True)
                    self.setAppropriateNgLayout()
                    cfg.project_tab.initNeuroglancer()



    def neuroglancer_configuration_2(self):
        logger.info('')
        if cfg.data:
            if cfg.project_tab:
                self._cmbo_ngLayout.setCurrentText('xy')
                cfg.project_tab._widgetArea_details.show()
                # cfg.project_tab._tabs.setCurrentIndex(0) #0124-
                # cfg.project_tab.updateNeuroglancer()
                cfg.project_tab.initNeuroglancer()


    # def hardRestartNg(self):
    #     self.refreshTab(hard_restart=True)


    def refreshTab(self):
        if cfg.zarr_tab:
            cfg.zarr_tab.initNeuroglancer()
        if cfg.data:
            if cfg.project_tab:
                if not self._working:
                    if cfg.project_tab._tabs.currentIndex() == 0:
                        logger.critical('Refreshing Neuroglancer...')
                        self.tell('Refreshing SNR Plot...')
                        cfg.project_tab.initNeuroglancer()
                    if cfg.project_tab._tabs.currentIndex() == 1:
                        logger.critical('Refreshing Table...')
                        self.tell('Refreshing SNR Plot...')
                        cfg.project_tab.project_table.set_data()
                    elif cfg.project_tab._tabs.currentIndex() == 3:
                        logger.critical('Refreshing SNR Plot...')
                        self.tell('Refreshing SNR Plot...')
                        cfg.project_tab.snr_plot.wipeData()
                        cfg.project_tab.snr_plot.initSnrPlot()
                    else:
                        self.warn('The application is busy')
                        logger.warn('The application is busy')


    def shutdownNeuroglancer(self):
        if ng.is_server_running():
            logger.critical('Stopping Neuroglancer...')
            # self.tell('Stopping Neuroglancer...')
            ng.server.stop()
            logger.info('Is server running? %r ' % ng.is_server_running())
            time.sleep(1)
            self.hud.done()


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


    def initImageAllocations(self):
        logger.info('')
        # if qtpy.PYSIDE6:
        #     QImageReader.setAllocationLimit(0)  # PySide6 only
        os.environ['QT_IMAGEIO_MAXALLOC'] = "1_000_000_000_000_000_000"
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 1_000_000_000_000



    def initOpenGlContext(self):
        logger.info('')
        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())


    def initPrivateMembers(self):
        logger.info('')
        self._unsaved_changes = False
        self._working = False
        self._is_mp_mode = False
        self._scales_combobox_switch = 0 #1125
        self._ng_layout_switch = 1 #1125
        self._section_slider_switch = 1
        self._isPlayingBack = 0
        self._isProfiling = 0
        self.detachedNg = WebPage(self)


    def initStyle(self):
        logger.info('')
        self.main_stylesheet = os.path.abspath('styles/default.qss')
        self.apply_default_style()


    def initPythonConsole(self):
        logger.info('')
        namespace = {
            'pg': pg,
            'np': np,
            'cfg': src.config,
            'mw': src.config.main_window,
            'viewer': cfg.viewer,
        }
        text = """
        Caution - anything executed here is injected into the main event loop of AlignEM-SWiFT!
        """
        cfg.py_console = pyqtgraph.console.ConsoleWidget(namespace=namespace, text=text)
        self._py_console = QWidget()
        label = QLabel('Python Console')
        label.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        lay = QVBoxLayout()
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(label, alignment=Qt.AlignmentFlag.AlignBaseline)
        lay.addWidget(cfg.py_console)
        self._py_console.setLayout(lay)
        self._py_console.setObjectName('_py_console')
        self._py_console.hide()


    def initView(self):
        logger.info('Making things look normal...')
        # self._tabs.show()
        self._enableAllTabs()
        self.main_stack_widget.setCurrentIndex(0)
        self._changeScaleCombo.setEnabled(True)
        cfg.SHADER = ''
        try:
            cfg.project_tab._overlayRect.hide()
            cfg.project_tab._overlayLab.hide()
        except:
            pass
        self.viewer_stack_widget.setCurrentIndex(0)
        if cfg.project_tab:
            self._is_mp_mode = False
            self._matchpt_ctls.hide()


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
        self._controlPanelAndHud.show()
        self._btn_show_hide_ctls.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
        self._btn_show_hide_ctls.setText('Hide Controls')


    def _forceHideControls(self):
        self._controlPanelAndHud.hide()
        self._btn_show_hide_ctls.setIcon(qta.icon("ei.adjust-alt", color='#f3f6fb'))
        self._btn_show_hide_ctls.setText('Controls')


    def _callbk_showHideControls(self):
        if self._controlPanelAndHud.isHidden():
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

        cfg.data.link_reference_sections() #Todo: check if this is necessary

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
            self.tell('Generating Thumbnails...')
            self.showZeroedPbar()
            try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(fn=cfg.thumb.generate_main())
                    self.threadpool.start(self.worker)
                else:
                    cfg.thumb.generate_main()

            except:
                print_exception()
                self.warn('Something Unexpected Happened While Generating Thumbnails')

            finally:
                cfg.data.scalesList = cfg.data.scales()
                cfg.data.nscales = len(cfg.data.scales())
                cfg.data.set_scale(cfg.data.scales()[-1])
                self.pbar_widget.hide()
                logger.info('Thumbnail Generation Complete')
                self.set_idle()

        self._enableAllTabs()
        # cfg.project_tab.initNeuroglancer()
        logger.info('<<<< autoscale <<<<')


    def _showSNRcheck(self, s=None):
        caller = inspect.stack()[1].function
        if s == None: s = cfg.data.scale()
        if cfg.data.is_aligned():
            logger.info(f'Checking SNR data for {s}...')
            failed = cfg.data.check_snr_status()
            if len(failed) == cfg.data.nSections:
                self.warn(f'No SNR Data Available for %s' % cfg.data.scale_pretty(s=s))
            elif failed:
                indexes, names = zip(*failed)
                lst_names = ''
                for name in names:
                    lst_names += f'\n  Section: {name}'
                self.warn(f'No SNR Data For Layers {", ".join(map(str, indexes))}...')


    def regenerate(self, scale) -> None:

        if cfg.project_tab is None:
            self.warn('No data yet!')
            return

        if self._working == True:
            self.warn('Another Process is Already Running')
            return

        # if not exist_aligned_zarr_cur_scale():
        #     self.warn('Scale Must Be Aligned Before Images Can Be Generated.')
        #     return
        if not cfg.data.is_aligned(s=scale):
            self.warn('Scale Must Be Aligned Before Images Can Be Generated.')
            return

        self.onAlignmentStart()

        logger.info('Regenerate Aligned Images...')
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
                        preallocate=True,
                        renew_dir=True
                    )
                )
                self.threadpool.start(self.worker)
            else:
                generate_aligned(
                    dm=cfg.data,
                    scale=scale,
                    start_layer=0,
                    num_layers=-1,
                    preallocate=True,
                    renew_dir=True
                )

            # self.set_status('Generating Thumbnails...')
            self.tell('Generating Aligned Thumbnails...')
            self.showZeroedPbar()
            try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(fn=cfg.thumb.generate_aligned(start=0, end=None))
                    self.threadpool.start(self.worker)
                else:
                    cfg.thumb.generate_aligned(start=0, end=None)

            except:
                print_exception()
                self.warn('Something Unexpected Happened While Generating Thumbnails')

            finally:
                cfg.data.scalesList = cfg.data.scales()
                cfg.data.nscales = len(cfg.data.scales())
                cfg.data.set_scale(cfg.data.scales()[-1])
                self.pbar_widget.hide()
                logger.info('Thumbnail Generation Complete')

        except:
            print_exception()
            self.err('An Exception Was Raised During Image Generation.')
        else:
            self.dataUpdateWidgets()
            self._autosave()

        finally:

            dir = cfg.data.dest()
            scale = cfg.data.scale()
            cfg.project_tab._onTabChange()
            if are_aligned_images_generated(dir=dir, scale=scale):
                self.tell('Regenerate Succeeded')
            else:
                self.err('Image Generation Failed Unexpectedly. Try Re-aligning.')
            self.set_idle()
            self.pbar_widget.hide()
            cfg.project_tab.initNeuroglancer()
            time.sleep(1)
            cfg.project_tab.initNeuroglancer()
            QApplication.processEvents()


    def verify_alignment_readiness(self) -> bool:

        if not cfg.data:
            self.warn('No project yet!')
            return False
        elif self._working == True:
            self.warn('Another Process is Running')
            return False
        elif not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.warn(warning_msg)
            return False
        else:
            return True


    def onAlignmentEnd(self):
        logger.info('')
        logger.critical('Running Post- Alignment Tasks...')
        try:
            self.pbar_widget.hide()
            cfg.project_tab._onTabChange()
            s = cfg.data.curScale
            cfg.data.scalesAlignedAndGenerated = get_scales_with_generated_alignments(cfg.data.scales())
            cfg.data.nScalesAlignedAndGenerated = len(cfg.data.scalesAlignedAndGenerated)
            # self.updateHistoryListWidget(s=s)
            cfg.data.update_cache()
            self.dataUpdateWidgets()
            logger.info('Aligned Scales:\n%s' % cfg.data.scalesAlignedAndGenerated)
            self.updateEnabledButtons()
            self.updateToolbar()
            if self._isOpenProjTab():
                try:    cfg.project_tab.project_table.set_data()
                except: logger.warning('No data to set!')
            self._showSNRcheck()
            cfg.project_tab.project_table.updateSliderMaxVal()
            cfg.project_tab.initNeuroglancer()
            if cfg.project_tab._tabs.currentIndex() == 1:
                cfg.project_tab.project_table.setScaleData()
            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.snr_plot.initSnrPlot()


            self.updateMenus()
        except:
            print_exception()
        finally:
            self._enableAllTabs()
            self._autosave()
            QApplication.processEvents()


    def onAlignmentStart(self):
        logger.info('')
        self.stopPlaybackTimer()
        self.stopNgServer()
        self._disableAllOtherTabs()
        self.showZeroedPbar()
        cfg.data.set_use_bounding_rect(self._bbToggle.isChecked(), s=cfg.data.curScale)
        cfg.data.set_prev_snr()


    def alignAll(self):
        self.align(scale=cfg.data.curScale, start=0, end=None)
        if exist_aligned_zarr_cur_scale():
            self.tell('Aligned Images Generated Successfully')
            logger.info('Alignment seems successful')


    def alignForward(self):
        self.align(scale=cfg.data.curScale, start=cfg.data.layer(), end=None)


    def alignOne(self):
        self.align(scale=cfg.data.curScale, start=cfg.data.layer(), end=cfg.data.layer())


    def align(self, scale, start, end):
        logger.info('')
        if not self.verify_alignment_readiness(): return
        self.onAlignmentStart()
        is_realign = cfg.data.is_aligned(s=scale)
        m = {'init_affine': 'Initializing', 'refine_affine': 'Refining'}
        self.tell("%s Affines (%s)..." %(m[cfg.data.al_option(s=scale)], cfg.data.scale_pretty(s=scale)))
        # self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=compute_affines(scale, start, end))
                self.threadpool.start(self.worker)
            else: compute_affines(scale, start, end)
        except:   print_exception(); self.err('An Exception Was Raised During Alignment.')
        else:     logger.info('Affine Computation Succeeded')

        self.tell('Generating Correlation Spot Thumbnails...')
        # self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=cfg.thumb.generate_corr_spot(start=0, end=None))
                self.threadpool.start(self.worker)
            else: cfg.thumb.generate_corr_spot(start=0, end=None)
        except: print_exception(); self.warn('There Was a Problem Generating Corr Spot Thumbnails')
        else:   logger.info('Correlation Spot Thumbnail Generation Succeeded')

        logger.info('Calculating SNR Delta Values...')
        if is_realign:
            diff_avg = cfg.data.snr_average() - cfg.data.snr_prev_average()
            diff = [a_i - b_i for a_i, b_i in zip(cfg.data.snr_prev_list(), cfg.data.snr_list())]
            no_chg = [i for i, x in enumerate(diff) if x == 0]
            pos = [i for i, x in enumerate(diff) if x > 0]
            neg = [i for i, x in enumerate(diff) if x < 0]
            self.tell('Re-alignment Results:')
            self.tell('  # Better (SNR ↑) : %s' % ' '.join(map(str, pos)))
            self.tell('  # Worse  (SNR ↓) : %s' % ' '.join(map(str, neg)))
            self.tell('  # Equal  (SNR =) : %s' % ' '.join(map(str, no_chg)))
            if abs(diff_avg) < .001: self.tell('  Δ AVG. SNR : 0.000 (NO CHANGE)')
            elif diff_avg > 0:       self.tell('  Δ AVG. SNR : +%.3f (BETTER)' % diff_avg)
            else:                    self.tell('  Δ AVG. SNR : -%.3f (WORSE)' % diff_avg)

        if not self._toggleAutogenerate.isChecked():
            self.onAlignmentEnd()
            self.tell('Affine Computation Complete!')
            return

        self.tell('Generating Aligned Images...')
        # self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_aligned(scale, start, end, preallocate=True))
                self.threadpool.start(self.worker)
            else: generate_aligned(scale, start, end, preallocate=True)

            self.tell('Generating Aligned Thumbnails...')
            # self.showZeroedPbar()
            try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(fn=cfg.thumb.generate_aligned(start=0, end=None))
                    self.threadpool.start(self.worker)
                else: cfg.thumb.generate_aligned(start=0, end=None)
            except:  print_exception(); self.warn('Something Unexpected Happened While Generating Thumbnails')
            finally: logger.info('Thumbnail Generation Complete')
        except:  print_exception(); self.err('Alignment Succeeded But Image Generation Failed Unexpectedly.')
        finally: self.onAlignmentEnd()


    def rescale(self):

        #Todo clear SNR data!

        if not cfg.data:
            self.warn('No data yet!')
            return
        msg ='Warning: Rescaling resets project data.\nAll progress will be lost. Continue?'
        dlg = AskContinueDialog(title='Confirm Rescale', msg=msg)
        if not dlg.exec():
            logger.info('Rescale Canceled')
            return

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
                    logger.info(f'removing path {p}...')
                    shutil.rmtree(p)
        except:
            print_exception()
        else:
            self.hud.done()

        self.post = cfg.main_window.hud.post("Removing Zarr Scale Directories...")
        try:
            p = os.path.join(path, 'img_src.zarr')
            if os.path.exists(p):
                logger.info(f'removing path {p}...')
                shutil.rmtree(p, ignore_errors=True)
            p = os.path.join(path, 'img_aligned.zarr')
            if os.path.exists(p):
                logger.info(f'removing path {p}...')
                shutil.rmtree(p, ignore_errors=True)
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
            self.pbar_widget.hide()
            self._enableAllTabs()
            self.onStartProject()
            self.onAlignmentEnd()
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
            msg = 'Verify reset the reject list.'
            reply = QMessageBox.question(self, 'Verify Reset Reject List', msg, QMessageBox.Cancel | QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                cfg.data.clear_all_skips()
        else:
            self.warn('No Skips To Clear.')


    def apply_all(self, s) -> None:
        if s == None: s = cfg.data.curScale
        '''Apply alignment settings to all images for all scales'''
        if cfg.data:
            swim_val = self._swimWindowControl.value() * 100.
            whitening_val = self._whiteningControl.value()
            self.tell('Applying These Settings To All Scales + Layers...')
            self.tell('  SWIM Window  : %s' % str(swim_val))
            self.tell('  Whitening    : %s' % str(whitening_val))
            for layer in cfg.data.alstack(s=s):
                layer['align_to_ref_method']['method_data']['win_scale_factor'] = swim_val
                layer['align_to_ref_method']['method_data']['whitening_factor'] = whitening_val


    def enableAllButtons(self):
        self._btn_alignAll.setEnabled(True)
        self._btn_alignOne.setEnabled(True)
        self._btn_alignForward.setEnabled(True)
        self._btn_regenerate.setEnabled(True)
        self._scaleDownButton.setEnabled(True)
        self._scaleUpButton.setEnabled(True)
        self._ctlpanel_applyAllButton.setEnabled(True)
        self._skipCheckbox.setEnabled(True)
        self._whiteningControl.setEnabled(True)
        self._swimWindowControl.setEnabled(True)
        self._toggleAutogenerate.setEnabled(True)
        self._bbToggle.setEnabled(True)
        self._polyBiasCombo.setEnabled(True)
        self._btn_clear_skips.setEnabled(True)
        self._toggleAutogenerate.setEnabled(True)


    def updateEnabledButtons(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev s buttons depending on current s.
        (2) Set the enabled/disabled state of the align_all-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        logger.info('')
        if cfg.data:
            self._btn_alignAll.setText('Align All\n%s' % cfg.data.scale_pretty())
            self._ctlpanel_applyAllButton.setEnabled(True)
            self._skipCheckbox.setEnabled(True)
            self._toggleAutogenerate.setEnabled(True)
            self._bbToggle.setEnabled(True)
            self._polyBiasCombo.setEnabled(True)
            self._btn_clear_skips.setEnabled(True)
            self._swimWindowControl.setEnabled(True)
            self._whiteningControl.setEnabled(True)
        else:
            self._ctlpanel_applyAllButton.setEnabled(False)
            self._skipCheckbox.setEnabled(False)
            self._whiteningControl.setEnabled(False)
            self._swimWindowControl.setEnabled(False)
            self._toggleAutogenerate.setEnabled(False)
            self._bbToggle.setEnabled(False)
            self._polyBiasCombo.setEnabled(False)
            self._btn_clear_skips.setEnabled(False)

        if cfg.data:
            if cfg.data.is_aligned_and_generated():
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(True)
                self._btn_alignForward.setEnabled(True)
                self._btn_regenerate.setEnabled(True)
            else:
                self._btn_alignOne.setEnabled(False)
                self._btn_alignForward.setEnabled(False)
                if cfg.data.is_aligned():
                    self._btn_regenerate.setEnabled(True)
                else:
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
                cur_index = self._changeScaleCombo.currentIndex()
                if cur_index == 0:
                    self._scaleDownButton.setEnabled(True)
                    self._scaleUpButton.setEnabled(False)
                elif cfg.data.n_scales() == cur_index + 1:
                    self._scaleDownButton.setEnabled(False)
                    self._scaleUpButton.setEnabled(True)
                else:
                    self._scaleDownButton.setEnabled(True)
                    self._scaleUpButton.setEnabled(True)
        else:
            self._scaleUpButton.setEnabled(False)
            self._scaleDownButton.setEnabled(False)
            self._btn_alignAll.setEnabled(False)
            self._btn_alignOne.setEnabled(False)
            self._btn_alignForward.setEnabled(False)
            self._btn_regenerate.setEnabled(False)
        if cfg.data:
            self._btn_regenerate.setStatusTip('Re-generate Images, But Do Not Compute Alignment,  %s' %
                                              cfg.data.scale_pretty())
            self._btn_alignForward.setStatusTip('Align and Generate %d -> End,  %s' %
                                                (cfg.data.layer(), cfg.data.scale_pretty()))
            self._btn_alignAll.setStatusTip('Align and Generate All,  %s' %
                                            cfg.data.scale_pretty())
            self._btn_alignOne.setStatusTip('Align and Generate the Current One Only %d,  Scale %d' %
                                            (cfg.data.layer(), cfg.data.scale_val()))



    def scale_up(self) -> None:
        '''Callback function for the Next Scale button.'''
        logger.info('')
        if not self._scaleUpButton.isEnabled():
            return
        if self._working:
            self.warn('Changing scales during CPU-bound processes is not currently supported.')
            return
        try:
            self._changeScaleCombo.setCurrentIndex(self._changeScaleCombo.currentIndex() - 1)  # Changes Scale
            if not cfg.data.is_alignable():
                self.warn('Lower scales have not been aligned yet')
        except:
            print_exception()


    def scale_down(self) -> None:
        '''Callback function for the Previous Scale button.'''
        logger.info('')
        if not self._scaleDownButton.isEnabled():
            return
        if self._working:
            self.warn('Changing scales during CPU-bound processes is not currently supported.')
            return
        try:
            self._changeScaleCombo.setCurrentIndex(self._changeScaleCombo.currentIndex() + 1)  # Changes Scale
            # cfg.data.set_layer(cur_layer) # Set layer to layer last visited at previous s
        except:
            print_exception()


    @Slot()
    def set_status(self, msg: str) -> None:
        # self.statusBar.showMessage(msg)
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
        self._cpanel.setStyleSheet(style)
        # self.hud.set_theme_default()
        self.hud.set_theme_light()
        if inspect.stack()[1].function != 'initStyle':
            if cfg.project_tab:
                cfg.project_tab.updateNeuroglancer()
            elif cfg.zarr_tab:
                cfg.zarr_tab.updateNeuroglancer()


    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')


    def onScaleChange(self):
        caller = inspect.stack()[1].function
        logger.critical(f'Changing Scales...')
        if caller != 'OnStartProject':
            # self.jump_to(cfg.data.layer())
            self.dataUpdateWidgets()
            self.updateEnabledButtons()
            if cfg.project_tab._tabs.currentIndex() == 1:
                cfg.project_tab.project_table.set_data()
            self.updateToolbar()
            self._showSNRcheck()
            try:
                self._bbToggle.setChecked(cfg.data.has_bb())
            except:
                logger.warning('Bounding Rect Widget Failed to Update')
            cfg.project_tab.initNeuroglancer()


    def updateToolbar(self):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        if self._tabsGlob.currentWidget().__class__.__name__ == 'ProjectTab':
            if cfg.data.is_aligned_and_generated():
                self.aligned_label.show()
                self.generated_label.show()
                self.unaligned_label.hide()
            elif cfg.data.is_aligned():
                self.aligned_label.show()
                self.generated_label.hide()
                self.unaligned_label.hide()
            else:
                self.aligned_label.hide()
                self.generated_label.hide()
                self.unaligned_label.show()
                self._isZarrTab()
        if self._tabsGlob.currentWidget().__class__.__name__ in ('ProjectTab', 'ZarrTab'):
            if cfg.tensor:
                self.label_toolbar_resolution.setText(f'{cfg.tensor.shape}')
                self.label_toolbar_resolution.show()
        else:
            self.aligned_label.hide()
            self.unaligned_label.hide()
            self.generated_label.hide()
            self.label_toolbar_resolution.hide()

    @Slot()
    def dataUpdateWidgets(self, ng_layer=None) -> None:
        '''Reads Project Data to Update MainWindow.'''
        caller = inspect.stack()[1].function
        logger.info(f'Updating widgets (caller: {caller})...')
        # logger.info(f'caller: {caller}')
        if cfg.zarr_tab:
            if ng_layer:
                self._sectionSlider.setValue(ng_layer)
                self._jumpToLineedit.setText(str(ng_layer))
            else:
                self._sectionSlider.setValue(cfg.ng_worker._layer)
                self._jumpToLineedit.setText(str(cfg.ng_worker._layer))
            return
        if cfg.project_tab:
            if cfg.data:
                if self._working == True:
                    logger.warning(f"Can't update GUI now - working (caller: {caller})...")
                    self.warn("Can't update GUI now - working...")
                    return

                if isinstance(ng_layer, int):
                    try:
                        if 0 <= ng_layer < cfg.data.n_sections():
                            logger.debug(f'Setting Layer: {ng_layer}')
                            cfg.data.set_layer(ng_layer)
                            # self._sectionSlider.setValue(ng_layer)
                    except:
                        print_exception()
                    if cfg.project_tab._tabs.currentIndex() == 0:
                        if self.rb1.isChecked():
                            cfg.project_tab._overlayRect.hide()
                            cfg.project_tab._overlayLab.hide()
                            if ng_layer == cfg.data.n_sections():
                                cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 1.0);')
                                cfg.project_tab._overlayLab.setText('End Of Image Stack')
                                cfg.project_tab._overlayLab.show()
                                cfg.project_tab._overlayRect.show()
                                self.layer_details.setText('')
                                self.clearAffineWidget()
                                cfg.project_tab._widgetArea_details.hide()
                                self._sectionSlider.setValue(cfg.main_window._sectionSlider.maximum()) #0119+
                                self._jumpToLineedit.setText('-1')
                                QApplication.processEvents()
                                return
                            elif cfg.data.skipped():
                                cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
                                cfg.project_tab._overlayLab.setText('X REJECTED - %s' % cfg.data.name_base())
                                cfg.project_tab._overlayLab.show()
                                cfg.project_tab._overlayRect.show()
                            elif ng_layer == 0:
                                cfg.project_tab._overlayLab.setText('No Reference')
                                cfg.project_tab._overlayLab.show()
                            # else:
                            #     cfg.project_tab._overlayRect.hide()
                            #     cfg.project_tab._overlayLab.hide()
                                # QApplication.processEvents()
                            cfg.project_tab._widgetArea_details.show()
                            QApplication.processEvents()


                if cfg.project_tab._tabs.currentIndex() == 3:
                    cfg.project_tab.snr_plot.updateLayerLinePos()
                    cfg.project_tab.updatePlotThumbnail()

                    styles = {'color': '#f3f6fb', 'font-size': '14px', 'font-weight': 'bold'}
                    # cfg.project_tab.snr_plot.plot.setTitle(cfg.data.base_image_name())
                    cfg.project_tab.snr_plot.plot.setLabel('top', cfg.data.base_image_name(), **styles)

                self._sectionSlider.setValue(cfg.data.layer())

                # try:
                #     if self.detachedNg.view.isVisible():
                #         if cfg.project_tab:
                #             cfg.project_tab.updateNgLayer()
                #         if cfg.zarr_tab:
                #             cfg.zarr_tab.updateNgLayer()
                # except:
                #     print_exception()

                try:
                    self.updateLayerDetails()

                    try:     self._jumpToLineedit.setText(str(cfg.data.layer()))
                    except:  logger.warning('Current Layer Widget Failed to Update')
                    try:     self._skipCheckbox.setChecked(cfg.data.skipped())
                    except:  logger.warning('Skip Toggle Widget Failed to Update')
                    try:     self._whiteningControl.setValue(cfg.data.whitening())
                    except:  logger.warning('Whitening Input Widget Failed to Update')
                    try:     self._swimWindowControl.setValue(cfg.data.swim_window() * 100.)
                    except:  logger.warning('Swim Input Widget Failed to Update')
                    try:
                        if cfg.data.null_cafm():
                            self._polyBiasCombo.setCurrentText(str(cfg.data.poly_order()))
                        else:
                            self._polyBiasCombo.setCurrentText('None')
                    except:  logger.warning('Polynomial Order Combobox Widget Failed to Update')

                except:
                    print_exception()
                    logger.warning('dataUpdateWidgets bugging out')


    def updateLayerDetails(self, s=None, l=None):
        if s == None: s = cfg.data.curScale
        if l == None: l = cfg.data.layer()
        name = "%s" % cfg.data.name_base(s=s, l=l)
        snr_report = cfg.data.snr_report(s=s, l=l)
        snr = f"%s" % snr_report
        skips = ' '.join(map(str, cfg.data.skips_list()))
        matchpoints = ' '.join(map(str, cfg.data.find_layers_with_matchpoints()))
        text0 = f"{name}"
        text1 = f"{snr}"
        text2 = f"Skipped Layers: [{skips}]"
        text3 = f"Match Point Layers: [{matchpoints}]"
        cfg.project_tab._layer_details[0].setText(text0)
        cfg.project_tab._layer_details[1].setText(text1)
        cfg.project_tab._layer_details[2].setText(text2)
        cfg.project_tab._layer_details[3].setText(text3)
        if cfg.data.is_aligned_and_generated():
            afm, cafm = cfg.data.afm(l=l), cfg.data.cafm(l=l)
            cfg.project_tab.afm_widget_.setText(make_affine_widget_HTML(afm, cafm))
        else:
            self.clearAffineWidget()


    def clearUIDetails(self):
        self.layer_details.setText('')
        self.clearAffineWidget()



    def clearAffineWidget(self):
        afm = cafm = [[0] * 3, [0] * 3]
        cfg.project_tab.afm_widget_.setText(make_affine_widget_HTML(afm, cafm))


    def setPlaybackSpeed(self):
        dlg = QInputDialog(self)
        dlg.setInputMode(QInputDialog.IntInput)
        dlg.setTextValue(str(cfg.DEFAULT_PLAYBACK_SPEED))
        dlg.setLabelText('Set Playback Speed\n(frames per second)...')
        dlg.resize(200, 120)
        ok = dlg.exec_()
        if ok:
            new_speed = float(dlg.textValue())
            cfg.DEFAULT_PLAYBACK_SPEED = new_speed
            logger.info(f'Automatic playback speed set to {new_speed}fps')
            self.tell(f'Automatic playback speed set to {new_speed}fps')


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
        self._setLastTab()


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
        # self.updateHistoryListWidget()


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
        # finally:
        #     self.updateHistoryListWidget()


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


    def _resetSliderAndJumpInput(self):
        if cfg.data:
            if self._isProjectTab() or self._isZarrTab():
                logger.info('Setting section slider and jump input validators...')
                self._section_slider_switch = 0
                if cfg.project_tab:
                    self._jumpToLineedit.setValidator(QIntValidator(0, cfg.data.n_sections() - 1))
                    self._sectionSlider.setRange(0, cfg.data.n_sections() - 1)
                    self._sectionSlider.setValue(cfg.data.layer())
                if cfg.zarr_tab:
                    if not cfg.tensor:
                        logger.warning('No tensor!')
                        return
                    self._jumpToLineedit.setValidator(QIntValidator(0, cfg.tensor.shape[0] - 1))
                    self._jumpToLineedit.setText(str(0))
                    self._sectionSlider.setRange(0, cfg.tensor.shape[0] - 1)
                    self._sectionSlider.setValue(0)
                self._section_slider_switch = 1


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
        logger.info('')
        if cfg.project_tab:
            if requested not in range(cfg.data.n_sections()):
                logger.warning('Requested layer is not a valid layer')
                return
            cfg.data.set_layer(requested)  # 1231+
            # if cfg.project_tab._tabs.currentIndex() == 0:
            #     # logger.info('Jumping To Layer %d' % requested)
            #     # state = copy.deepcopy(cfg.ng_workers[cfg.data.curScale].viewer.state)
            #     state = copy.deepcopy(cfg.viewer.state)
            #     state.position[0] = requested
            #     # cfg.ng_workers[cfg.data.curScale].viewer.set_state(state)
            #     cfg.viewer.set_state(state)
            #     # self.dataUpdateWidgets() #0106-
            # # cfg.project_tab.updateNeuroglancer()
            # cfg.project_tab.updateNgLayer()
            self.dataUpdateWidgets()


    @Slot()
    def jump_to_layer(self) -> None:
        logger.info('')
        if cfg.project_tab:
            requested = int(self._jumpToLineedit.text())
            if requested not in range(cfg.data.n_sections()):
                logger.warning('Requested layer is not a valid layer')
                return
            cfg.data.set_layer(requested)
            if cfg.project_tab._tabs.currentIndex() == 1:
                cfg.project_tab.project_table.table.selectRow(requested)
            self._sectionSlider.setValue(requested)



    def jump_to_slider(self):
        # if cfg.data:
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        if caller == 'dataUpdateWidgets':
            return
        if not cfg.project_tab:
            if not cfg.zarr_tab:
                return
        # logger.info(f'caller: {caller}')
        if self._section_slider_switch:


            # logger.info(f'caller: {caller}')
            requested = self._sectionSlider.value()
            if cfg.project_tab:
                cfg.data.set_layer(requested)
            cfg.ng_worker._layer = requested
            # logger.info(f'slider, requested: {requested}')

            if cfg.project_tab:
                if requested in range(cfg.data.n_sections()):
                    if cfg.project_tab._tabs.currentIndex() == 0:
                        logger.info('Jumping To Section #%d' % requested)
                        state = copy.deepcopy(cfg.viewer.state)
                        state.position[0] = requested
                        cfg.viewer.set_state(state)

                    if cfg.project_tab._tabs.currentIndex() == 1:
                        cfg.project_tab.project_table.table.selectRow(requested)
                    # elif self.detachedNg:
                    #     if self.detachedNg.view.isVisible():
                    #         state = copy.deepcopy(cfg.viewer.state)
                    #         state.position[0] = requested
                    #         cfg.viewer.set_state(state)

                self.dataUpdateWidgets()
                    # if cfg.project_tab._tabs.currentIndex() == 3:

            elif cfg.zarr_tab:
                logger.info('Jumping To Section #%d' % requested)
                state = copy.deepcopy(cfg.viewer.state)
                state.position[0] = requested
                cfg.viewer.set_state(state)

            try:     self._jumpToLineedit.setText(str(requested))
            except:  logger.warning('Current Layer Widget Failed to Update')


    @Slot()
    def reload_scales_combobox(self) -> None:
        # logger.info('Reloading Scale Combobox (caller: %s)' % inspect.stack()[1].function)
        self._scales_combobox_switch = 0
        self._changeScaleCombo.clear()
        self._changeScaleCombo.addItems(cfg.data.scales())
        index = self._changeScaleCombo.findText(cfg.data.curScale, Qt.MatchFixedString)
        if index >= 0:
            self._changeScaleCombo.setCurrentIndex(index)
        self._scales_combobox_switch = 1


    def fn_scales_combobox(self) -> None:
        if cfg.project_tab:
            if self._scales_combobox_switch == 1:
                caller = inspect.stack()[1].function
                if caller != 'onStartProject':
                    if self._is_mp_mode != True:
                        cfg.data.set_scale(self._changeScaleCombo.currentText())
                        self.onScaleChange()


    def fn_ng_layout_combobox(self) -> None:

        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')

        if self._ng_layout_switch == 0:
            return
        if caller == 'main':

            if caller == 'onStartProject':
                return
            if not cfg.data:
                if not cfg.project_tab:
                    if not cfg.zarr_tab:
                        logger.info('Cant change layout, no data is loaded')
                        return

            choice = self._cmbo_ngLayout.currentText()

            if cfg.project_tab:
                cfg.project_tab.ng_layout = choice

            if cfg.zarr_tab:
                cfg.zarr_tab.ng_layout = choice

            try:
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

                if cfg.project_tab:
                    # cfg.project_tab.initNeuroglancer()
                    cfg.project_tab.updateNeuroglancer()
                elif cfg.zarr_tab:
                    # cfg.ng_worker.initViewer()
                    cfg.zarr_tab.updateNeuroglancer()

                # if cfg.project_tab:
                #     cfg.project_tab.updateNeuroglancer()
                    # cfg.project_tab.refreshNeuroglancerURL()
            except:
                print_exception()
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
            if cfg.data.is_aligned_and_generated():
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
        self.tell('Starting A New Project...')
        self.stopPlaybackTimer()
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
            else:
                logger.info("Response was not 'OK' - Returning")
                self.warn('New Project Canceled.')
                return

        # self.initView()
        # self.clearUIDetails()

        self.tell('New Project Path:')
        filename = new_project_dialog()
        if filename in ['', None]:
            logger.info('New Project Canceled.')
            self.warn("New Project Canceled.")
            self.set_idle()
            return
        if not filename.endswith('.swiftir'):
            filename += ".swiftir"
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

        # path, extension = os.path.splitext(filename)
        # makedirs_exist_ok(path, exist_ok=True)
        # cfg.data = DataModel(name=path, mendenhall=mendenhall)
        # cfg.project_tab = ProjectTab(path=path, datamodel=cfg.data)

        path, extension = os.path.splitext(filename)
        cfg.data = DataModel(name=path, mendenhall=mendenhall)
        cfg.project_tab = ProjectTab(self, path=path, datamodel=cfg.data)
        self._tabsGlob.addTab(cfg.project_tab, os.path.basename(path) + '.swiftir')
        self._setLastTab()
        makedirs_exist_ok(path, exist_ok=True)


        if not mendenhall:
            try:
                self.import_multiple_images()
            except:
                logger.warning('Import Images Dialog Was Canceled - Returning')
                self.warn('Canceling New Project')
                print_exception()
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

            # cfg.data.set_defaults()
            # self._tabsGlob.addTab(cfg.project_tab, os.path.basename(path) + '.swiftir')
            # self._setLastTab()

            self.onStartProject()
        else:
            create_project_structure_directories(cfg.data.dest(), ['scale_1'])
            # self.onStartProject(mendenhall=True)
            # turn OFF onStartProject for Mendenhall

        logger.critical(f'Appending {filename} to .swift_cache...')
        userprojectspath = os.path.join(os.path.expanduser('~'), '.swift_cache')
        with open(userprojectspath, 'a') as f:
            f.write(filename + '\n')

        # cfg.project_tab.initNeuroglancer()
        self._autosave()

    def delete_project(self):
        logger.critical('')
        project_file = cfg.selected_file
        project = os.path.splitext(project_file)[0]

        if not validate_selection():
            logger.warning('Invalid Project For Deletion (!)\n%s' % project)
            return
        txt = "Are you sure you want to PERMANENTLY DELETE " \
              "the following project?\n\n" \
              "Project: %s" % project

        msgbox = QMessageBox(QMessageBox.Warning, 'Confirm Delete Project', txt,
                          buttons=QMessageBox.Abort | QMessageBox.Yes)
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setMaximumWidth(350)
        msgbox.setDefaultButton(QMessageBox.Cancel)
        reply = msgbox.exec_()
        if reply == QMessageBox.Abort:
            self.tell('Aborting Delete Project Permanently Instruction...')
            logger.warning('Aborting Delete Project Permanently Instruction...')
            return
        if reply == QMessageBox.Ok:
            logger.info('Deleting Project File %s...' % project_file)
            self.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)
            logger.warning('Executing Delete Project Permanently Instruction...')

        try:
            logger.critical(f'Deleting Project File: {project_file}')
            shutil.rmtree(project_file, ignore_errors=True, onerror=handleError)
            shutil.rmtree(project_file, ignore_errors=True, onerror=handleError)
        except:
            self.warn('An Error Was Encountered During Deletion of the Project File')
            print_exception()
        else:
            self.hud.done()


        try:
            logger.info('Deleting Project Directory %s...' % project)
            self.tell('Deleting Project Directory %s...' % project)
            shutil.rmtree(project, ignore_errors=True, onerror=handleError)
            shutil.rmtree(project, ignore_errors=True, onerror=handleError)
        except:
            self.warn('An Error Was Encountered During Deletion of the Project Directory')
            print_exception()
        else:
            self.hud.done()

        self.tell('Wrapping up...')
        configure_project_paths()
        if self._tabsGlob.currentWidget().__class__.__name__ == 'OpenProject':
            logger.critical('Refreshing data...')
            try:
                self._tabsGlob.currentWidget().user_projects.set_data()
                QApplication.processEvents()
            except:
                logger.warning('There was a problem updating the project list')
                print_exception()



        self.tell('Deletion Complete')
        logger.info('Deletion Complete')


    def open_project(self):
        #Todo check for Zarr. Generate/Re-generate if necessary
        logger.critical('Opening A Project...')
        self.tell('Opening A Project...')
        self.stopPlaybackTimer()
        cfg.main_window.set_status('Awaiting User Input...')
        filename = open_project_dialog()
        if filename == None:
            logger.info('Canceling Open Project.')
            self.warn('Canceling Open Project.')
            return
        logger.info(f'filename: {filename}')

        try:
            with open(filename, 'r') as f:
                cfg.data = DataModel(data=json.load(f))
        except:
            self.warn(f'No Such File Found: {filename}')
            logger.warning(f'No Such File Found: {filename}')
            cfg.main_window.set_idle()
            return
        else:
            logger.info(f'Project Opened!')

        print(cfg.data.scales())

        cfg.data.set_paths_absolute(filename=filename)
        cfg.project_tab = ProjectTab(
            self,
            path=cfg.data.dest() + '.swiftir',
            datamodel=cfg.data
        )

        # tab_name = os.path.basename(cfg.data.dest() + '.swiftir')
        tab_name = os.path.basename(cfg.data.dest())
        self._tabsGlob.addTab(cfg.project_tab, tab_name)
        self._setLastTab()
        # self.rb0.setChecked(True)
        self._jumpToLineedit.setText(str(cfg.data.layer()))

        if cfg.data.is_aligned():
            self._showSNRcheck()

        self.onStartProject()
        self.hud.done()

    def open_project_new(self):
        self._tabsGlob.addTab(OpenProject(), 'Open...')
        self._setLastTab()

    def open_project_selected(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        logger.info('')

        if self._getTabType() == 'ZarrTab':
            self.open_zarr()
            return

        if not validate_selection():
            self.warn("Invalid Path, extension must be '.swiftir'")
            logger.warning('Invalid Path...')
            return

        filename = cfg.selected_file
        logger.critical(f'Opening Project {filename}...')
        self.tell('Opening A Project...')
        self.stopPlaybackTimer()

        try:
            with open(filename, 'r') as f:
                cfg.data = DataModel(data=json.load(f))
            self._autosave()
        except:
            self.warn(f'No Such File Found: {filename}')
            logger.warning(f'No Such File Found: {filename}')
            cfg.main_window.set_idle()
            print_exception()
            return
        else:
            logger.info(f'Project Opened!')

        append_project_path(filename)

        print(cfg.data.scales())

        cfg.data.set_paths_absolute(filename=filename)

        cfg.project_tab = ProjectTab(
            self,
            path=cfg.data.dest() + '.swiftir',
            datamodel=cfg.data
        )

        self.onStartProject()

        tab_name = os.path.basename(cfg.data.dest() + '.swiftir')
        self._tabsGlob.addTab(cfg.project_tab, tab_name)
        self._setLastTab()

        # self.rb0.setChecked(True)
        # self._jumpToLineedit.setText(str(cfg.data.layer())) #0123-

        if cfg.data.is_aligned():
            self._showSNRcheck()

        # self.onStartProject()
        self.hud.done()


    def open_zarr(self):
        caller = inspect.stack()[1].function
        logger.critical('caller: %s' % caller)
        self.label_toolbar_resolution.setText('[dims]')
        cfg.zarr_tab = ZarrTab()
        cfg.zarr_tab.initNeuroglancer()
        self._tabsGlob.addTab(cfg.zarr_tab, 'Open Zarr ...')
        self.set_status('Select Zarr...')
        self._setLastTab()

    def openDetatchedZarr(self):
        if cfg.project_tab or cfg.zarr_tab:
            # self.detachedNg = WebPage()
            self.detachedNg.open(url=str(cfg.viewer))
            self.detachedNg.show()
        else:
            if not ng.server.is_server_running():
                self.warn('Neuroglancer is not running.')

    def set_nglayout_combo_text(self, layout:str):
        cfg.main_window._ng_layout_switch = 0
        cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
        cfg.main_window._ng_layout_switch = 1


    def onStartProject(self, mendenhall=False):
        '''Functions that only need to be run once per project
                Do not automatically save, there is nothing to save yet'''
        caller = inspect.stack()[1].function
        # logger.critical('caller: %s' % caller)
        logger.critical('Loading project...')

        cfg.data.update_cache()
        self._changeScaleCombo.show()
        self._scales_combobox_switch = 0
        self.reload_scales_combobox()
        self._changeScaleCombo.setCurrentText(cfg.data.curScale)
        self._scales_combobox_switch = 1
        self._fps_spinbox.setValue(cfg.DEFAULT_PLAYBACK_SPEED)
        # self.set_nglayout_combo_text(layout=cfg.project_tab.ng_layout)
        cfg.data.set_defaults() # BEFORE dataUpdateWidgets
        cfg.project_tab.initNeuroglancer()
        self.dataUpdateWidgets()
        try:    self._bbToggle.setChecked(cfg.data.has_bb())
        except: logger.warning('Bounding Rect Widget Failed to Update')
        self.updateEnabledButtons()
        self.updateMenus()
        self.updateToolbar()
        self._resetSliderAndJumpInput()  # future changes to import_multiple_images will require refactoring this
        cfg.main_window._sectionSlider.setValue(int(cfg.data.n_sections() / 2))
        self._btn_alignAll.setText('Align All\n%s' % cfg.data.scale_pretty())
        cfg.project_tab._widgetArea_details.show()
        QApplication.processEvents()
        self.set_idle()

    # def initNeuroglancer(self, layout=None, matchpoint=None):
    #     caller = inspect.stack()[1].function
    #     logger.info(f'caller: {caller}')
    #     if cfg.data:
    #         if layout:
    #             cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
    #         # cfg.main_window.reload_ng_layout_combobox(initial_layout=self.ng_layout)
    #         if cfg.main_window.rb0.isChecked():
    #             cfg.main_window._cmbo_ngLayout.setCurrentText('4panel')
    #             cfg.ng_worker = NgHostSlim(parent=self, project=True)
    #         elif cfg.main_window.rb1.isChecked():
    #             cfg.main_window._cmbo_ngLayout.setCurrentText('xy')
    #             cfg.ng_worker = NgHost(parent=self)
    #         cfg.ng_worker.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
    #         self.updateNeuroglancer(matchpoint=matchpoint)
    #
    # def updateNeuroglancer(self, matchpoint=None, layout=None):
    #     # caller = inspect.stack()[1].function
    #     # logger.info(f'caller: {caller}')
    #     if layout:
    #         cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
    #     if matchpoint != None:
    #         cfg.ng_worker.initViewer(matchpoint=matchpoint)
    #     else:
    #         cfg.ng_worker.initViewer()
    #     self.ng_browser.setUrl(QUrl(cfg.ng_worker.url()))
    #     self.ng_browser.setFocus()
    #
    #     if cfg.data.is_aligned_and_generated():
    #         self._transformationWidget.show()
    #     else:
    #         self._transformationWidget.hide()


    def saveApplicationSettings(self):
        logger.info('')
        usersettingspath = os.path.join(os.path.expanduser('~'), '.swiftrc')
        try:
            f = open(usersettingspath, 'w')
            json.dump(cfg.settings, f, indent=2)
            f.close()
        except:
            logger.warning(f'Unable to save current user settings. Using defaults...')
            self.warn(f'Unable to save current user settings. Using defaults...')
            f = open('defaults.json', 'r')
            cfg.settings = json.load(f)
        else:
            self.tell(f'Application Settings Saved!')


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


    def save(self):
        if cfg.data:
            self.set_status('Saving...')
            self.tell('Saving Project...')
            try:
                self._saveProjectToFile()
                self._unsaved_changes = False
            except:
                self.warn('Unable To Save')
            else:
                self.hud.done()
            finally:
                self.set_idle()

    def _autosave(self):
        if cfg.data:
            if cfg.AUTOSAVE:
                logger.info('Autosaving...')
                try:
                    self._saveProjectToFile()
                except:
                    self._unsaved_changes = True
                    print_exception()


    def _saveProjectToFile(self, saveas=None):
        if cfg.data:
            if self._isProjectTab():
                try:
                    cfg.data.basefilenames()
                    if saveas is not None:
                        cfg.data.set_destination(saveas)
                    data_cp = copy.deepcopy(cfg.data)
                    # data_cp.make_paths_relative(start=cfg.data.dest())
                    data_cp_json = data_cp.to_dict()
                    logger.info('---- SAVING DATA TO PROJECT FILE ----')
                    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                    proj_json = jde.encode(data_cp_json)
                    name = cfg.data.dest()
                    if not name.endswith('.swiftir'):
                        name += ".swiftir"
                    logger.info('Save Name: %s' % name)
                    with open(name, 'w') as f: f.write(proj_json)
                    del data_cp
                    self._tabsGlob.setTabText(self._tabsGlob.currentIndex(), os.path.basename(name))
                except:
                    print_exception()
                else:
                    self._unsaved_changes = False


    def _callbk_unsavedChanges(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            # self.tell('You have unsaved changes.')
            # logger.info("Called by " + inspect.stack()[1].function)
            self._unsaved_changes = True
            name = os.path.basename(cfg.data.dest())
            self._tabsGlob.setTabText(self._tabsGlob.currentIndex(), name + '.swiftir' + '*')
        # else:
        #     logger.warning('Caller was not main! (%s)' % caller)

    def update_ng(self):
        if cfg.project_tab:  cfg.project_tab.updateNeuroglancer()
        if cfg.zarr_tab:     cfg.zarr_tab.updateNeuroglancer()

    def import_multiple_images(self):
        ''' Import images into data '''
        logger.info('>>>> import_multiple_images >>>>')
        self.tell('Import Images:')
        filenames = natural_sort(import_images_dialog())

        if not filenames:
            logger.warning('No Images Were Selected')
            self.warn('No Images Were Selected')
            return 1

        cfg.data.set_source_path(os.path.dirname(filenames[0])) #Critical!
        self.tell(f'Importing {len(filenames)} Images...')
        logger.info(f'Selected Images: \n{filenames}')

        try:
            for f in filenames:
                if f:
                    cfg.data.append_image(f)
                else:
                    cfg.data.append_empty()
        except:
            print_exception()
            self.err('There Was A Problem Importing Selected Files')
        else:
            self.hud.done()

        if len(cfg.data) > 0:
            cfg.data.nSections = len(filenames)
            img_size = cfg.data.image_size(s='scale_1')
            self.tell(f'Dimensions: {img_size[0]}✕{img_size[1]}')
            cfg.data.link_reference_sections()
        else:
            self.warn('No Images Were Imported')

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
        self.browser_web.setHtml(html)
        self.main_stack_widget.setCurrentIndex(1)



    def documentation_view(self):
        self.tell('Opening Documentation...')
        browser = WebBrowser()
        browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self._tabsGlob.addTab(browser, 'Documentation')
        self._setLastTab()
        self._forceHideControls()


    def remote_view(self):
        self.tell('Opening Neuroglancer Remote Viewer...')
        browser = WebBrowser()
        browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self._tabsGlob.addTab(browser, 'Neuroglancer')
        self._setLastTab()
        self._forceHideControls()


    def open_url(self, text: str) -> None:
        self.browser_web.setUrl(QUrl(text))
        self.main_stack_widget.setCurrentIndex(1)


    def view_swiftir_examples(self):
        self.browser_web.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/examples/README.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def view_swiftir_commands(self):
        self.browser_web.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/commands/README.md'))
        self.main_stack_widget.setCurrentIndex(1)

    def browser_3dem_community(self):
        self.browser_web.setUrl(QUrl(
            'https://3dem.org/workbench/data/tapis/community/data-3dem-community/'))



    def invalidate_all(self, s=None):
        if ng.is_server_running():
            if s == None: s = cfg.data.curScale
            if cfg.data.is_mendenhall():
                cfg.ng_worker.menLV.invalidate()
            else:
                cfg.refLV.invalidate()
                cfg.baseLV.invalidate()
                if exist_aligned_zarr(s):
                    cfg.alLV.invalidate()


    def stopNgServer(self):
        logger.info('Considering stopping Neuroglancer...')
        if ng.is_server_running():
            self.tell('Stopping Neuroglancer...')
            try:    ng.stop()
            except: print_exception()
            else:   self.hud.done()
        else:
            self.tell('Neuroglancer Is Not Running')

    def startStopProfiler(self):
        logger.info('')
        if self._isProfiling:
            self.profilingTimer.stop()
        else:
            self.profilingTimer.setInterval(cfg.PROFILING_TIMER_SPEED)
            self.profilingTimer.start()
        self._isProfiling = not self._isProfiling

    def startStopTimer(self):
        logger.info('')
        if self._isPlayingBack:
            self.automaticPlayTimer.stop()
            self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        elif cfg.project_tab or cfg.zarr_tab:
            # self.automaticPlayTimer.setInterval(1000 / cfg.DEFAULT_PLAYBACK_SPEED)
            self.automaticPlayTimer.start()
            self._btn_automaticPlayTimer.setIcon(qta.icon('fa.pause', color=cfg.ICON_COLOR))
        self._isPlayingBack = not self._isPlayingBack


    def stopPlaybackTimer(self):
        self.automaticPlayTimer.stop()
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        self._isPlayingBack = 0

    # def _setPlaybackFps(self):
    #     cfg.DEFAULT_PLAYBACK_SPEED = float(self._fps_spinbox.value())


    def initShortcuts(self):
        logger.info('')
        events = (
            (QKeySequence.MoveToPreviousChar, self.scale_down),
            (QKeySequence.MoveToNextChar, self.scale_up),
            (Qt.Key_K, self._callbk_skipChanged),
            (Qt.Key_P, self.startStopTimer)
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

    def detachNeuroglancer(self):
        if cfg.project_tab or cfg.zarr_tab:
            # self.detachedNg = WebPage()
            self.detachedNg.open(url=str(cfg.viewer))

        else:
            if not ng.server.is_server_running():
                self.warn('Neuroglancer is not running.')

    def webgl2_test(self):
        '''https://www.khronos.org/files/webgl20-reference-guide.pdf'''
        self.browser_web.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.main_stack_widget.setCurrentIndex(1)

    def google(self):
        self.tell('Opening Google Tab...')
        self.browser = WebBrowser(self)
        self.browser.setObjectName('web_browser')
        self.browser.setUrl(QUrl('https://www.google.com'))
        self._tabsGlob.addTab(self.browser, 'Web Browser')
        self._setLastTab()
        # self._getTabObject()
        self._forceHideControls()

    def gpu_config(self):
        self.tell('Opening GPU Config...')
        browser = WebBrowser()
        browser.setUrl(QUrl('chrome://gpu'))
        self._tabsGlob.addTab(browser, 'GPU Configuration')
        self._setLastTab()
        self._forceHideControls()

    def chromium_debug(self):
        self.tell('Opening Chromium Debugger...')
        browser = WebBrowser()
        browser.setUrl(QUrl('http://127.0.0.1:9000'))
        self._tabsGlob.addTab(browser, 'Debug Chromium')
        self._setLastTab()
        self._forceHideControls()

    def get_ng_state(self):
        if cfg.project_tab:
            try:
                if ng.is_server_running():
                    txt = json.dumps(cfg.viewer.state.to_json(), indent=2)
                    return f"Viewer State:\n{txt}"
                else:
                    return f"Neuroglancer Is Not Running."
            except:
                return f"N/A"
                print_exception()


    def get_ng_state_raw(self):
        if cfg.project_tab:
            try:
                if ng.is_server_running():
                    return f"Raw Viewer State:\n{cfg.viewer.config_state.raw_state}"
                else:
                    return f"Neuroglancer Is Not Running."
            except:
                return f"N/A"
                print_exception()


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

        # self.splash_widget = QWidget()  # Todo refactor this it is not in use
        # self.splash_widget.setObjectName('splash_widget')
        # self.splashmovie = QMovie('src/resources/alignem_animation.gif')
        # self.splashlabel = QLabel()
        # self.splashlabel.setMovie(self.splashmovie)
        # self.splashlabel.setMinimumSize(QSize(100, 100))
        # gl = QGridLayout()
        # gl.addWidget(self.splashlabel, 1, 1, 1, 1)
        # self.splash_widget.setLayout(gl)
        # self.splash_widget.setGraphicsEffect(QGraphicsOpacityEffect().setOpacity(0.7))
        # self.splashmovie.finished.connect(lambda: self.runaftersplash())


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
        caller = inspect.stack()[1].function
        logger.info(f'Bounding Box Toggle Callback (caller: {caller})')
        if caller != 'dataUpdateWidgets':
            # self._bbToggle.setEnabled(state)
            if cfg.project_tab:
                if state:
                    self.warn('Bounding Box is now ON. Warning: Output dimensions may grow large.')
                    cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
                else:
                    self.tell('Bounding Box is now OFF. Output dimensions will match source.')
                    cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def _callbk_skipChanged(self, state:int):  # 'state' is connected to skipped toggle
        logger.debug(f'_callbk_skipChanged, sig:{state}:')
        '''Callback Function for Skip Image Toggle'''
        caller = inspect.stack()[1].function
        if cfg.project_tab:
            if caller != 'dataUpdateWidgets':
                skip_state = self._skipCheckbox.isChecked()
                for s in cfg.data.scales():
                    # layer = self.request_ng_layer()
                    layer = cfg.data.layer()
                    if layer >= cfg.data.n_sections():
                        logger.warning(f'Request layer is out of range ({layer}) - Returning')
                        return
                    cfg.data.set_skip(skip_state, s=s, l=layer)  # for checkbox
                if skip_state:
                    self.tell("Flagged For Skip: %s" % cfg.data.name_base())
                cfg.data.link_reference_sections()
                self.dataUpdateWidgets()
                if cfg.project_tab._tabs.currentIndex() == 1:
                    cfg.project_tab.project_table.set_data()
            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.snr_plot.initSnrPlot()
                QApplication.processEvents()


    def skip_change_shortcut(self):
        logger.info('')
        if cfg.data:
            if cfg.project_tab:
                if self._skipCheckbox.isChecked(): self._skipCheckbox.setChecked(False)
                else:                              self._skipCheckbox.setChecked(True)


    def enterExitMatchPointMode(self):
        #Todo REFACTOR
        logger.info('')
        if cfg.data:
            if not cfg.data.is_aligned_and_generated():
                logger.warning('Cannot enter match point mode until the series is aligned.')
                self.warn('Cannot enter match point mode until the series is aligned.')
                return

            if cfg.project_tab:
                if self._is_mp_mode == False:
                    logger.info('\nEntering Match Point Mode...')
                    self.tell('Entering Match Point Mode...')
                    self._is_mp_mode = True
                    self._changeScaleCombo.setEnabled(False)
                    self.extra_header_text_label.setText('Match Point Mode')
                    self._forceHideControls()
                    self._matchpt_ctls.show()
                    if cfg.data.is_aligned_and_generated():
                        self.update_match_point_snr()
                    self.extra_header_text_label.show()
                    self.mp_marker_size_spinbox.setValue(cfg.data['user_settings']['mp_marker_size'])
                    self.mp_marker_lineweight_spinbox.setValue(cfg.data['user_settings']['mp_marker_lineweight'])
                    self.rb0.setEnabled(False)
                    self.rb1.setChecked(True)
                    self.extra_header_text_label.show()
                    # cfg.project_tab.ng_layout = 'xy'
                    cfg.project_tab.updateNeuroglancer(matchpoint=True, layout='xy')
                    # self.neuroglancer_configuration_1()
                else:
                    logger.info('\nExiting Match Point Mode...')
                    self.tell('Exiting Match Point Mode...')
                    self._is_mp_mode = False
                    self._changeScaleCombo.setEnabled(True)
                    # self.extra_header_text_label.setText('')
                    self.extra_header_text_label.hide()
                    self._forceShowControls()
                    # self.updateSkipMatchWidget()s
                    self.initView()
                    cfg.project_tab.ng_layout = '4panel'
                    self.rb0.setEnabled(True)
                    self.rb0.setChecked(True)
                    # cfg.project_tab.updateNeuroglancer(matchpoint=False, layout='4panel')
                    cfg.project_tab.initNeuroglancer(layout='4panel', matchpoint=False)
                    # self.neuroglancer_configuration_0()
                    if cfg.project_tab._tabs.currentIndex() == 3:
                        cfg.project_tab.snr_plot.updateSpecialLayerLines()


                self.updateToolbar()
                # cfg.project_tab.updateNeuroglancer()


    def update_match_point_snr(self):
        if cfg.project_tab:
            snr_report = cfg.data.snr_report()
            self.matchpoint_text_snr.setHtml(f'<h4>{snr_report}</h4>')


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
        cfg.SHADER = '''void main () {
          emitGrayscale(toNormalized(getDataValue()));
        }'''
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

    # def update(self):
    #     # get the radio button the send the signal
    #     rb = self.sender()
    #
    #     # check if the radio button is checked
    #     if rb.isChecked():
    #         self.result_label.setText(f'You selected {rb.text()}')

    def onProfilingTimer(self):
        cpu_percent = psutil.cpu_percent()
        psutil.virtual_memory()
        percent_ram = psutil.virtual_memory().percent
        num_widgets = len(QApplication.allWidgets())

        # memory_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2
        # memory_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        print('CPU Usage: %.3f%% | RAM Usage: %.3f%%' % (cpu_percent, percent_ram))
        print('Neuoglancer Running? %r' % isNeuroglancerRunning())
        print('# Allocated Widgets: %d' % num_widgets)

        # print(f'CPU Usage    : {cpu_percent:.3f}%')
        # print(f'RAM Usage    : {percent_ram:.3f}%')
        # print(f'Memory Used  : {memory_mb:.3f}MB')
        # print(f'Memory Peak  : {memory_peak/2072576:.3f}MB')
        # print(f'# of widgets : {num_widgets}')
        # print(h.heap())


    def initToolbar(self):
        logger.info('')
        height = int(18)

        self._btn_refreshNg = QPushButton('Refresh')
        self._btn_refreshNg.setIcon(qta.icon('ei.refresh', color=cfg.ICON_COLOR))
        # self._btn_refreshNg.setFixedSize(QSize(22,22))
        self._btn_refreshNg.clicked.connect(self.refreshTab)
        self._btn_refreshNg.setStatusTip('Refresh Neuroglancer')

        self.toolbar = QToolBar()
        self.toolbar.setFixedHeight(34)
        # self.toolbar.setFixedHeight(64)
        self.toolbar.setObjectName('toolbar')
        self.addToolBar(self.toolbar)

        # self.rb0 = QRadioButton('Stack')
        # self.rb0 = QRadioButton('Contiguous')
        # self.rb0 = QRadioButton('Default')
        self.rb0 = QRadioButton('Normal')
        self.rb0.setChecked(True)
        self.rb0.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rb0.toggled.connect(self.neuroglancer_configuration_0)
        self.rb0.toggled.connect(self.updateMenus)

        # self.rb1 = QRadioButton('Ref | Curr')
        self.rb1 = QRadioButton('Side-by-side')
        # self.rb1 = QRadioButton('Comparison')
        # self.rb1 = QRadioButton('Compare')
        # self.rb1 = QRadioButton('Ref|Base|Aligned, Column')
        self.rb1.setChecked(False)
        self.rb1.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rb1.toggled.connect(self.neuroglancer_configuration_1)
        self.rb1.toggled.connect(self.updateMenus)

        # self.rb2 = QRadioButton('Ref|Base|Aligned, Row')
        # self.rb2.setChecked(False)
        # self.rb2.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.rb2.toggled.connect(self.neuroglancer_configuration_2)

        self._arrangeRadio = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(8, 0, 8, 0)
        hbl.addWidget(self.rb0)
        hbl.addWidget(self.rb1)
        # hbl.addWidget(icon_sbs)
        # hbl.addWidget(self.rb2)
        self._arrangeRadio.setLayout(hbl)

        self._sectionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self._sectionSlider.setFixedWidth(192)
        self._sectionSlider.valueChanged.connect(self.jump_to_slider)

        tip = 'Show Neuroglancer key bindings'
        self.info_button_buffer_label = QLabel(' ')

        self.profilingTimerButton = QPushButton('P')
        self.profilingTimerButton.setFixedSize(20,20)
        self.profilingTimerButton.clicked.connect(self.startStopProfiler)
        self.profilingTimer = QTimer(self)
        self.profilingTimer.timeout.connect(self.onProfilingTimer)
        if cfg.PROFILING_TIMER_AUTOSTART:
            self.profilingTimerButton.click()


        tip = 'Jump To Image #'
        lab = QLabel('Section #: ')
        lab.setObjectName('toolbar_layer_label')

        '''section # / jump-to lineedit'''
        self._jumpToLineedit = QLineEdit(self)
        self._jumpToLineedit.setFocusPolicy(Qt.ClickFocus)
        self._jumpToLineedit.setStatusTip(tip)
        self._jumpToLineedit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._jumpToLineedit.setFixedSize(QSize(46, height))
        self._jumpToLineedit.returnPressed.connect(self.jump_to_layer)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._jumpToLineedit)
        self._jumpToSectionWidget = QWidget()
        self._jumpToSectionWidget.setLayout(hbl)
        # self.toolbar.addWidget(self._sectionSlider)

        self._btn_automaticPlayTimer = QPushButton()
        self._btn_automaticPlayTimer.setFixedSize(20,20)
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        self.automaticPlayTimer = QTimer(self)
        # self._btn_automaticPlayTimer.clicked.connect(self.automaticPlayTimer.start)

        self._btn_automaticPlayTimer.clicked.connect(self.startStopTimer)

        def onTimer():
            logger.info('')
            # self.automaticPlayTimer.set #comeback
            # self.automaticPlayTimer.setInterval(1000 / cfg.DEFAULT_PLAYBACK_SPEED)
            self.automaticPlayTimer.setInterval(1000 / self._fps_spinbox.value())
            if cfg.data:
                if cfg.project_tab:
                    if self._sectionSlider.value() < cfg.data.nSections - 1:
                        self._sectionSlider.setValue(self._sectionSlider.value() + 1)
                        QApplication.processEvents()
                    else:
                        self._sectionSlider.setValue(0)
                        self.automaticPlayTimer.stop()
                        self._isPlayingBack = 0
                        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
                        # self._sectionSlider.setValue(0)
                        # self._sectionSlider.setValue(1)

        self.automaticPlayTimer.timeout.connect(onTimer)
        self._sectionSliderWidget = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4,0,4,0)
        hbl.addWidget(self._btn_automaticPlayTimer, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._sectionSlider, alignment=Qt.AlignmentFlag.AlignLeft)
        self._sectionSliderWidget.setLayout(hbl)

        lab = QLabel('Speed:')
        self._fps_spinbox = QDoubleSpinBox()
        self._fps_spinbox.setFixedHeight(22)
        self._fps_spinbox.setMinimum(.5)
        self._fps_spinbox.setMaximum(10)
        self._fps_spinbox.setSingleStep(.2)
        self._fps_spinbox.setDecimals(1)
        self._fps_spinbox.setSuffix('fps')
        self._fps_spinbox.setStatusTip('Playback Speed (frames/second)')
        # self._fps_spinbox.valueChanged.connect(self._setPlaybackFps)
        self._fps_spinbox.clear()

        '''NG arrangement/layout combobox'''
        self._cmbo_ngLayout = QComboBox()
        self._cmbo_ngLayout.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._cmbo_ngLayout.setFixedSize(QSize(76, 20))
        self._cmbo_ngLayout.addItems(['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '3d'])
        self._cmbo_ngLayout.currentTextChanged.connect(self.fn_ng_layout_combobox)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self._cmbo_ngLayout)

        '''scale combobox'''
        self._ngLayoutWidget = QWidget()
        self._ngLayoutWidget.setLayout(hbl)
        self._changeScaleCombo = QComboBox(self)
        self._changeScaleCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._changeScaleCombo.setFixedSize(QSize(90, 20))
        self._changeScaleCombo.currentTextChanged.connect(self.fn_scales_combobox)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self._changeScaleCombo, alignment=Qt.AlignmentFlag.AlignRight)
        self._changeScaleWidget = QWidget()
        self._changeScaleWidget.setLayout(hbl)

        self.label_toolbar_resolution = QLabel('[dims]')
        self.label_toolbar_resolution.setObjectName('label_toolbar_resolution')
        self.label_toolbar_resolution.setFixedHeight(20)
        self.label_toolbar_resolution.hide()
        self.aligned_label = QLabel(' Aligned ')
        self.aligned_label.setObjectName('green_toolbar_label')
        self.aligned_label.setFixedHeight(20)
        self.aligned_label.hide()
        self.unaligned_label = QLabel(' Not Aligned ')
        self.unaligned_label.setObjectName('red_toolbar_label')
        self.unaligned_label.setFixedHeight(20)
        self.unaligned_label.hide()
        self.generated_label = QLabel(' Generated ')
        self.generated_label.setObjectName('green_toolbar_label')
        self.generated_label.setFixedHeight(20)
        self.generated_label.hide()
        self.extra_header_text_label = QLabel('Match Point Mode')
        self.extra_header_text_label.setObjectName('extra_header_text_label')
        self.extra_header_text_label.setFixedHeight(20)
        self.extra_header_text_label.hide()

        self._al_unal_label_widget = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.label_toolbar_resolution)
        hbl.addWidget(self.aligned_label)
        hbl.addWidget(self.unaligned_label)
        hbl.addWidget(self.generated_label)
        hbl.addWidget(self.extra_header_text_label)
        self._al_unal_label_widget.setLayout(hbl)

        self._detachNgButton = QPushButton()
        self._detachNgButton.setIcon(qta.icon("fa.external-link-square", color=ICON_COLOR))
        self._detachNgButton.clicked.connect(self.detachNeuroglancer)
        self._detachNgButton.setStatusTip('Detach Neuroglancer (open in a separate window)')

        self.toolbar.addWidget(self._btn_refreshNg)
        self.toolbar.addWidget(self._arrangeRadio)
        self.toolbar.addWidget(self._al_unal_label_widget)
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(w)
        self.toolbar.addWidget(self._jumpToSectionWidget)
        self.toolbar.addWidget(self._sectionSliderWidget)
        self.toolbar.addWidget(self._fps_spinbox)
        self.toolbar.addWidget(self._ngLayoutWidget)
        self.toolbar.addWidget(self._changeScaleWidget)
        if cfg.DEV_MODE:
            self.toolbar.addWidget(self.profilingTimerButton)
        self.toolbar.addWidget(self._detachNgButton)
        self.toolbar.addWidget(self.info_button_buffer_label)


    def _disableAllOtherTabs(self):
        indexes = list(range(0, self._tabsGlob.count()))
        indexes.remove(self._tabsGlob.currentIndex())
        for i in indexes:
            self._tabsGlob.setTabEnabled(i, False)
        # self._btn_refreshNg.setEnabled(False)


    def _enableAllTabs(self):
        indexes = list(range(0, self._tabsGlob.count()))
        for i in indexes:
            self._tabsGlob.setTabEnabled(i, True)
        # self._btn_refreshNg.setEnabled(True)


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


    def _isOpenProjTab(self):
        if self._getTabType() == 'OpenProject':
            return True
        else:
            return False


    def _getTabType(self, index=None):
        try:
            return self._tabsGlob.currentWidget().__class__.__name__
        except:
            return None


    def getCurrentTabWidget(self):
        return self._tabsGlob.currentWidget()


    def _getTabObject(self):
        return self._tabsGlob.currentWidget()


    def _onGlobTabChange(self):
        logger.info('')
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')

        if self._tabsGlob.count() == 0:
            return
        if caller == 'onStartProject':
            return

        cfg.selected_file = None
        self._tabsGlob.show()
        self.stopPlaybackTimer()
        tabtype = self._getTabType()


        if caller == 'initLaunchTab':
            return

        if tabtype == 'OpenProject':
            self._actions_widget.show()
            self.clearSelectionPathText()
            configure_project_paths()
        else:
            self._actions_widget.hide()

        # #0124- !!!!
        # if (caller == 'main') or (caller == '_onGlobTabClose') or (caller == '_setLastTab'):
        #     self.shutdownNeuroglancer()

        # if caller != 'new_project':
        if self._isProjectTab():
            # logger.info('Loading Project Tab...')
            cfg.data = self._tabsGlob.currentWidget().datamodel
            cfg.project_tab = self._tabsGlob.currentWidget()
            cfg.zarr_tab = None
            self._changeScaleCombo.show()
            self.reload_scales_combobox()
            self.rb0.show()
            self.rb1.show()
            # self.rb2.show()
            self.label_toolbar_resolution.show()
            self.dataUpdateWidgets()

            # self.set_nglayout_combo_text(layout=cfg.project_tab.ng_layout)  # must be before initNeuroglancer
            if self.rb0.isChecked():
                self.set_nglayout_combo_text(layout='4panel')  # must be before initNeuroglancer
            elif self.rb1.isChecked():
                self.set_nglayout_combo_text(layout='xy')  # must be before initNeuroglancer

            cfg.project_tab.initNeuroglancer() #!!!!

        else:
            cfg.data = None
            cfg.project_tab = None
            self._changeScaleCombo.clear()
            self.extra_header_text_label.hide()

        if self._isZarrTab():
            logger.info('Loading Zarr Tab...')
            cfg.zarr_tab = self._tabsGlob.currentWidget()
            self.set_nglayout_combo_text(layout=cfg.zarr_tab.ng_layout)  # must be before initNeuroglancer
            cfg.zarr_tab.initNeuroglancer() #!!!!!!!!!!
            self.label_toolbar_resolution.show()

        if self._isOpenProjTab():
            try:
                self.getCurrentTabWidget().user_projects.set_data()
            except:
                logger.warning('No data to set!')

        if self._isProjectTab() or self._isZarrTab():
            self.updateMenus()
        else:
            self.tensorMenu.clear()
            self.clearNgStateMenus()

        self.updateToolbar()
        self._resetSliderAndJumpInput()
        self.updateEnabledButtons() #0124+
        self.set_idle()

    def _onGlobTabClose(self, index):
        if not self._working:
            logger.info(f'Closing Tab: {index}')
            self._tabsGlob.removeTab(index)


    def _setLastTab(self):
        self._tabsGlob.setCurrentIndex(self._tabsGlob.count() - 1)


    def new_mendenhall_protocol(self):
        self.new_project(mendenhall=True)
        scale = cfg.data.scale()

        cfg.data['data']['cname'] = 'none'
        cfg.data['data']['clevel'] = 5
        cfg.data['data']['chunkshape'] = (1, 512, 512)
        cfg.data['data']['scales'][scale]['resolution_x'] = 2
        cfg.data['data']['scales'][scale]['resolution_y'] = 2
        cfg.data['data']['scales'][scale]['resolution_z'] = 50
        self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        self.mendenhall.set_directory()
        self.mendenhall.start_watching()
        cfg.data.set_source_path(self.mendenhall.sink)
        self._saveProjectToFile()


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
        cfg.data.link_reference_sections()
        logger.info(f'source path: {cfg.data.source_path()}')
        self._saveProjectToFile()

    def showActiveThreads(self, action):
        logger.info('')
        threads = '\n'.join([thread.name for thread in threading.enumerate()])
        text = f'# Active Threads : {threading.active_count()}' \
               f'Current Thread   : {threading.current_thread()}' \
               f'All Threads      : \n{threads}'
        self.menuTextActiveThreads.setText(text)
        QApplication.processEvents()


    def updateMenus(self):
        '''NOTE: This should always be run AFTER initializing Neuroglancer!'''
        caller = inspect.stack()[1].function
        logger.info('')
        if (not self._isProjectTab()) and (not self._isZarrTab()):
            return
        # logger.info('Clearing menus...')
        self.tensorMenu.clear()

        def addTensorMenuInfo(label, body):
            menu = self.tensorMenu.addMenu(label)
            textedit = QTextEdit(self)
            textedit.setFixedSize(QSize(600,600))
            textedit.setReadOnly(True)
            textedit.setText(body)
            action = QWidgetAction(self)
            action.setDefaultWidget(textedit)
            menu.addAction(action)

        if cfg.project_tab:
            if cfg.unal_tensor:
                # logger.info('Adding Raw Series tensor to menu...')
                txt = json.dumps(cfg.unal_tensor.spec().to_json(), indent=2)
                addTensorMenuInfo(label='Raw Series', body=txt)
            if cfg.data.is_aligned():
                if cfg.al_tensor:
                    # logger.info('Adding Aligned Series tensor to menu...')
                    txt = json.dumps(cfg.al_tensor.spec().to_json(), indent=2)
                    addTensorMenuInfo(label='Aligned Series', body=txt)

        elif cfg.zarr_tab:
            if cfg.tensor:
                txt = json.dumps(cfg.tensor.spec().to_json(), indent=2)
                addTensorMenuInfo(label='Zarr Series', body=txt)

        self.updateNgMenuStateWidgets()

    def clearTensorMenu(self):
        self.tensorMenu.clear()
        textedit = QTextEdit(self)
        textedit.setFixedSize(QSize(50,28))
        textedit.setReadOnly(True)
        textedit.setText('N/A')
        action = QWidgetAction(self)
        action.setDefaultWidget(textedit)
        self.tensorMenu.addAction(action)


    def updateNgMenuStateWidgets(self):
        # logger.info('')
        if not cfg.data:
            self.clearNgStateMenus()
            return
        textedit = QTextEdit(self)
        textedit.setFixedSize(QSize(600, 600))
        textedit.setReadOnly(True)
        textedit.setText(self.get_ng_state())
        action = QWidgetAction(self)
        action.setDefaultWidget(textedit)
        self.ngStateMenu.clear()
        self.ngStateMenu.addAction(action)

        # textedit = QTextEdit(self)
        # textedit.setFixedSize(QSize(600, 600))
        # textedit.setReadOnly(True)
        # textedit.setText(self.get_ng_state_raw())
        # action = QWidgetAction(self)
        # action.setDefaultWidget(textedit)
        # self.ngRawStateMenu.clear()
        # self.ngRawStateMenu.addAction(action)


    def clearNgStateMenus(self):
        self.clearMenu(menu=self.ngStateMenu)
        # self.clearMenu(menu=self.ngRawStateMenu)

        # self.ngStateMenu.clear()
        # textedit = QTextEdit(self)
        # textedit.setFixedSize(QSize(50, 28))
        # textedit.setReadOnly(True)
        # textedit.setText('N/A')
        # action = QWidgetAction(self)
        # action.setDefaultWidget(textedit)
        # selpf.ngStateMenu.addAction(action)
        #
        # self.ngRawStateMenu.clear()
        # textedit = QTextEdit(self)
        # textedit.setFixedSize(QSize(50, 28))
        # textedit.setReadOnly(True)
        # textedit.setText('N/A')
        # action = QWidgetAction(self)
        # action.setDefaultWidget(textedit)
        # self.ngRawStateMenu.addAction(action)

    def clearMenu(self, menu):
        menu.clear()
        textedit = QTextEdit(self)
        textedit.setFixedSize(QSize(50, 28))
        textedit.setReadOnly(True)
        textedit.setText('N/A')
        action = QWidgetAction(self)
        action.setDefaultWidget(textedit)
        menu.addAction(action)

    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

        fileMenu = self.menu.addMenu('File')

        self.newAction = QAction('&New Project...', self)
        self.newAction.triggered.connect(self.new_project)
        self.newAction.setShortcut('Ctrl+N')
        fileMenu.addAction(self.newAction)

        self.openAction = QAction('&Open Project...', self)
        # self.openAction.triggered.connect(self.open_project)
        self.openAction.triggered.connect(self.open_project_new)
        self.openAction.setShortcut('Ctrl+O')
        fileMenu.addAction(self.openAction)

        self.openArbitraryZarrAction = QAction('Open &Zarr...', self)
        self.openArbitraryZarrAction.triggered.connect(self.open_zarr)
        self.openArbitraryZarrAction.setShortcut('Ctrl+Z')
        fileMenu.addAction(self.openArbitraryZarrAction)

        exportMenu = fileMenu.addMenu('Export')

        self.exportAfmAction = QAction('Affines...', self)
        self.exportAfmAction.triggered.connect(self.export_afms)
        exportMenu.addAction(self.exportAfmAction)

        self.exportCafmAction = QAction('Cumulative Affines...', self)
        self.exportCafmAction.triggered.connect(self.export_cafms)
        exportMenu.addAction(self.exportCafmAction)

        self.ngRemoteAction = QAction('Remote Neuroglancer', self)
        self.ngRemoteAction.triggered.connect(self.remote_view)
        fileMenu.addAction(self.ngRemoteAction)

        self.saveAction = QAction('&Save Project', self)
        self.saveAction.triggered.connect(self.save)
        self.saveAction.setShortcut('Ctrl+S')
        fileMenu.addAction(self.saveAction)

        self.saveAppSettingsAction = QAction('Save User Preferences', self)
        self.saveAppSettingsAction.triggered.connect(self.saveApplicationSettings)
        fileMenu.addAction(self.saveAppSettingsAction)

        self.exitAppAction = QAction('&Quit', self)
        self.exitAppAction.triggered.connect(self.exit_app)
        self.exitAppAction.setShortcut('Ctrl+Q')
        fileMenu.addAction(self.exitAppAction)


        alignMenu = self.menu.addMenu('Align')

        menu = alignMenu.addMenu('History')
        action = QWidgetAction(self)
        action.setDefaultWidget(self._tool_hstry)
        menu.addAction(action)

        self.alignAllAction = QAction('Align All', self)
        self.alignAllAction.triggered.connect(self.alignAll)
        self.alignAllAction.setShortcut('Ctrl+A')
        alignMenu.addAction(self.alignAllAction)

        self.alignOneAction = QAction('Align One', self)
        self.alignOneAction.triggered.connect(self.alignOne)
        alignMenu.addAction(self.alignOneAction)

        self.alignForwardAction = QAction('Align Forward', self)
        self.alignForwardAction.triggered.connect(self.alignForward)
        alignMenu.addAction(self.alignForwardAction)

        self.alignMatchPointAction = QAction('Match Point Align', self)
        self.alignMatchPointAction.triggered.connect(self.enterExitMatchPointMode)
        self.alignMatchPointAction.setShortcut('Ctrl+M')
        alignMenu.addAction(self.alignMatchPointAction)

        self.skipChangeAction = QAction('Toggle Skip', self)
        self.skipChangeAction.triggered.connect(self.skip_change_shortcut)
        self.skipChangeAction.setShortcut('Ctrl+K')
        alignMenu.addAction(self.skipChangeAction)

        self.showMatchpointsAction = QAction('Show Matchpoints', self)
        self.showMatchpointsAction.triggered.connect(self.show_all_matchpoints)
        alignMenu.addAction(self.showMatchpointsAction)

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


        ngMenu = self.menu.addMenu("Neuroglancer")

        self.ngStateMenu = ngMenu.addMenu('JSON State') #get_ng_state
        self.ngStateMenuText = QTextEdit(self)
        self.ngStateMenuText.setReadOnly(False)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.ngStateMenuText)
        # self.ngStateMenu.hovered.connect(self.updateNgMenuStateWidgets)
        ngMenu.hovered.connect(self.updateNgMenuStateWidgets)
        self.ngStateMenu.addAction(action)

        self.clearNgStateMenus()

        ngPerspectiveMenu = ngMenu.addMenu("Perspective")

        self.ngLayout1Action = QAction('xy', self)
        self.ngLayout2Action = QAction('xz', self)
        self.ngLayout3Action = QAction('yz', self)
        self.ngLayout4Action = QAction('yz-3d', self)
        self.ngLayout5Action = QAction('xy-3d', self)
        self.ngLayout6Action = QAction('xz-3d', self)
        self.ngLayout7Action = QAction('3d', self)
        self.ngLayout8Action = QAction('4panel', self)
        ngPerspectiveMenu.addAction(self.ngLayout1Action)
        ngPerspectiveMenu.addAction(self.ngLayout2Action)
        ngPerspectiveMenu.addAction(self.ngLayout3Action)
        ngPerspectiveMenu.addAction(self.ngLayout4Action)
        ngPerspectiveMenu.addAction(self.ngLayout5Action)
        ngPerspectiveMenu.addAction(self.ngLayout6Action)
        ngPerspectiveMenu.addAction(self.ngLayout7Action)
        ngPerspectiveMenu.addAction(self.ngLayout8Action)
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

        ngArrangementMenu = ngMenu.addMenu("Arrangement")

        self.soloViewAction = QAction('Stack', self)
        self.soloViewAction.triggered.connect(self.neuroglancer_configuration_0)
        self.soloViewAction.triggered.connect(self.updateMenus)
        ngArrangementMenu.addAction(self.soloViewAction)

        self.colViewAction = QAction('Column', self)
        self.colViewAction.triggered.connect(self.neuroglancer_configuration_1)
        self.colViewAction.triggered.connect(self.updateMenus)

        ngArrangementMenu.addAction(self.colViewAction)

        self.rowViewAction = QAction('Row', self)
        self.rowViewAction.triggered.connect(self.neuroglancer_configuration_2)
        self.rowViewAction.triggered.connect(self.updateMenus)
        ngArrangementMenu.addAction(self.rowViewAction)

        ngShaderMenu = ngMenu.addMenu("Experimental Shaders")

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

        self.ngShowUiControlsAction = QAction('Show Ng UI Controls', self)
        self.ngShowUiControlsAction.setCheckable(True)
        self.ngShowUiControlsAction.setChecked(getOpt('neuroglancer,SHOW_UI_CONTROLS'))
        # self.ngShowUiControlsAction.triggered.connect(self.ng_toggle_show_ui_controls)
        self.ngShowUiControlsAction.triggered.connect(lambda val: setOpt('neuroglancer,SHOW_UI_CONTROLS', val))
        self.ngShowUiControlsAction.triggered.connect(self.update_ng)
        ngMenu.addAction(self.ngShowUiControlsAction)

        self.ngShowScaleBarAction = QAction('Show Ng Scale Bar', self)
        self.ngShowScaleBarAction.setCheckable(True)
        self.ngShowScaleBarAction.setChecked(getOpt('neuroglancer,SHOW_SCALE_BAR'))
        self.ngShowScaleBarAction.triggered.connect(lambda val: setOpt('neuroglancer,SHOW_SCALE_BAR', val))
        self.ngShowScaleBarAction.triggered.connect(self.update_ng)
        ngMenu.addAction(self.ngShowScaleBarAction)

        self.ngShowPanelBordersAction = QAction('Show Ng Panel Borders', self)
        self.ngShowPanelBordersAction.setCheckable(True)
        self.ngShowPanelBordersAction.setChecked(getOpt('neuroglancer,SHOW_PANEL_BORDERS'))
        self.ngShowPanelBordersAction.triggered.connect(lambda val: setOpt('neuroglancer,SHOW_PANEL_BORDERS', val))
        self.ngShowPanelBordersAction.triggered.connect(self.update_ng)
        ngMenu.addAction(self.ngShowPanelBordersAction)

        self.ngShowAxisLinesAction = QAction('Show Ng Axis Lines', self)
        self.ngShowAxisLinesAction.setCheckable(True)
        self.ngShowAxisLinesAction.setChecked(getOpt('neuroglancer,SHOW_AXIS_LINES'))
        self.ngShowAxisLinesAction.triggered.connect(lambda val: setOpt('neuroglancer,SHOW_AXIS_LINES', val))
        self.ngShowAxisLinesAction.triggered.connect(self.update_ng)
        ngMenu.addAction(self.ngShowAxisLinesAction)

        self.detachNgAction = QAction('Detach Neuroglancer...', self)
        self.detachNgAction.triggered.connect(self.detachNeuroglancer)
        ngMenu.addAction(self.detachNgAction)

        # self.hardRestartNgAction = QAction('Hard Restart Neuroglancer', self)
        # self.hardRestartNgAction.triggered.connect(self.hardRestartNg)
        # ngMenu.addAction(self.hardRestartNgAction)



        # ngStateMenu = ngMenu.addMenu("State")
        #
        # self.ngShowStateJsonAction = QAction('JSON', self)
        # self.ngShowStateJsonAction.triggered.connect(self.print_ng_state)
        # ngStateMenu.addAction(self.ngShowStateJsonAction)

        # self.ngShowStateUrlAction = QAction('State URL', self)
        # self.ngShowStateUrlAction.triggered.connect(self.print_ng_state_url)
        # ngStateMenu.addAction(self.ngShowStateUrlAction)

        # self.ngShowRawStateAction = QAction('Raw State', self)
        # self.ngShowRawStateAction.triggered.connect(self.print_ng_raw_state)
        # ngStateMenu.addAction(self.ngShowRawStateAction)
        #
        # self.ngExtractEverythingAction = QAction('Everything', self)
        # self.ngExtractEverythingAction.triggered.connect(self.dump_ng_details)
        # ngStateMenu.addAction(self.ngExtractEverythingAction)

        # viewMenu = self.menu.addMenu('View')
        #
        # self.splashAction = QAction('Splash', self)
        # self.splashAction.triggered.connect(self.show_splash)
        # viewMenu.addAction(self.splashAction)

        # toolsMenu = self.menu.addMenu('Tools')

        self.tensorMenu = self.menu.addMenu('Tensors')
        self.clearTensorMenu()


        configMenu = self.menu.addMenu('Configure')

        self.rescaleAction = QAction('Project...', self)
        self.rescaleAction.triggered.connect(self.rescale)
        configMenu.addAction(self.rescaleAction)

        # self.projectConfigAction = QAction('Project...', self)
        # self.projectConfigAction.triggered.connect(self._dlg_cfg_project)
        # configMenu.addAction(self.projectConfigAction)

        self.appConfigAction = QAction('Application...', self)
        self.appConfigAction.triggered.connect(self._dlg_cfg_application)
        configMenu.addAction(self.appConfigAction)

        self.setPlaybackSpeedAction = QAction('Playback...', self)
        self.setPlaybackSpeedAction.triggered.connect(self.setPlaybackSpeed)
        configMenu.addAction(self.setPlaybackSpeedAction)

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

        self.debugWebglAction = QAction('Web GL Test', self)
        self.debugWebglAction.triggered.connect(self.webgl2_test)
        debugMenu.addAction(self.debugWebglAction)

        self.debugGpuAction = QAction('GPU Configuration', self)
        self.debugGpuAction.triggered.connect(self.gpu_config)
        debugMenu.addAction(self.debugGpuAction)

        self.chromiumDebugAction = QAction('Troubleshoot Chromium', self)
        self.chromiumDebugAction.triggered.connect(self.chromium_debug)
        debugMenu.addAction(self.chromiumDebugAction)

        def fn():
            try:
                log = json.dumps(cfg.webdriver.get_log(), indent=2)
            except:
                log = 'Webdriver is offline.'
            self.menuTextWebdriverLog.setText(log)

        menu = debugMenu.addMenu('Webdriver Log')
        self.menuTextWebdriverLog = QTextEdit(self)
        self.menuTextWebdriverLog.setReadOnly(True)
        self.menuTextWebdriverLog.setText('Webdriver is offline.')
        action = QWidgetAction(self)
        action.setDefaultWidget(self.menuTextWebdriverLog)
        menu.hovered.connect(fn)
        debugMenu.hovered.connect(fn)
        menu.addAction(action)


        def fn():
            threads = '\n'.join([thread.name for thread in threading.enumerate()])
            html = \
            f"""<html><body>
            <h4><b>Active Threads :</b></h4>
            <p>{threading.active_count()}</p>
            <h4><b>Current Thread :</b></h4>
            <p>{threading.current_thread()}</p>
            <h4><b>Active Threads :</b></h4>
            <p>{threads}</p>
            </body></html>"""
            self.menuTextActiveThreads.setText(html)

        menu = debugMenu.addMenu('Active Threads')
        self.menuTextActiveThreads = QTextEdit(self)
        self.menuTextActiveThreads.setReadOnly(True)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.menuTextActiveThreads)
        menu.hovered.connect(fn)
        debugMenu.hovered.connect(fn)
        menu.addAction(action)

        self.moduleSearchPathAction = QAction('Module Search Path', self)
        self.moduleSearchPathAction.triggered.connect(self.show_module_search_path)
        debugMenu.addAction(self.moduleSearchPathAction)

        self.runtimePathAction = QAction('Runtime Path', self)
        self.runtimePathAction.triggered.connect(self.show_run_path)
        debugMenu.addAction(self.runtimePathAction)

        overrideMenu = debugMenu.addMenu('Override')

        self.anableAllControlsAction = QAction('Enable All Controls', self)
        self.anableAllControlsAction.triggered.connect(self.enableAllButtons)
        overrideMenu.addAction(self.anableAllControlsAction)

        if cfg.DEV_MODE:
            # developerMenu = debugMenu.addMenu('Developer')
            self.developerConsoleAction = QAction('Developer Console', self)
            self.developerConsoleAction.triggered.connect(self.show_hide_developer_console)
            debugMenu.addAction(self.developerConsoleAction)

        from src.ui.snr_plot import SnrPlot
        tw = SnrPlot()

        testMenu = debugMenu.addMenu('Test Menu Widgets')
        action = QWidgetAction(self)
        action.setDefaultWidget(tw)
        testMenu.addAction(action)

        helpMenu = self.menu.addMenu('Help')

        menu = helpMenu.addMenu('Keyboard Bindings')
        textbrowser = QTextBrowser(self)
        textbrowser.setSource(QUrl('src/resources/KeyboardCommands.html'))
        action = QWidgetAction(self)
        action.setDefaultWidget(textbrowser)
        menu.addAction(action)

        menu = helpMenu.addMenu('SWiFT-IR Components')
        textbrowser = QTextBrowser(self)
        textbrowser.setSource(QUrl('src/resources/swiftir_components.html'))
        action = QWidgetAction(self)
        action.setDefaultWidget(textbrowser)
        menu.addAction(action)


        action = QAction('SWiFT-IR Examples', self)
        action.triggered.connect(self.view_swiftir_examples)
        helpMenu.addAction(action)

        # self.reloadBrowserAction = QAction('Reload QtWebEngine', self)
        # self.reloadBrowserAction.triggered.connect(self.browser_reload)
        # helpMenu.addAction(self.reloadBrowserAction)

        action = QAction('Remod Help', self)
        action.triggered.connect(self.html_view)
        helpMenu.addAction(action)

        self.documentationAction = QAction('Documentation', self)
        self.documentationAction.triggered.connect(self.documentation_view)
        helpMenu.addAction(self.documentationAction)

        self.googleAction = QAction('Google', self)
        self.googleAction.triggered.connect(self.google)
        helpMenu.addAction(self.googleAction)


    # @Slot()
    # def widgetsUpdateData(self) -> None:
    #     '''Reads MainWindow to Update Project Data.'''
    #     logger.debug('widgetsUpdateData:')


    def _valueChangedSwimWindow(self):
        # logger.info('')
        caller = inspect.stack()[1].function
        # if caller == 'initControlPanel': return
        if caller == 'main':
            logger.info(f'caller: {caller}')
            cfg.data.set_swim_window(float(self._swimWindowControl.value()) / 100.)

    def _valueChangedWhitening(self):
        # logger.info('')
        caller = inspect.stack()[1].function
        # if caller != 'initControlPanel':
        if caller == 'main':
            logger.info(f'caller: {caller}')
            cfg.data.set_whitening(float(self._whiteningControl.value()))

    def _valueChangedPolyOrder(self):
        # logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'initControlPanel': return
        logger.info(f'caller: {caller}')
        if self._polyBiasCombo.currentText() == 'None':
            cfg.data.set_use_poly_order(False)
        else:
            cfg.data.set_use_poly_order(True)
            cfg.data.set_poly_order(self._polyBiasCombo.currentText())


    def _toggledAutogenerate(self) -> None:
        # logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'initControlPanel': return
        logger.info(f'caller: {caller}')

        if self._toggleAutogenerate.isChecked():
            self.tell('Images will be generated automatically after alignment')
        else:
            self.tell('Images will not be generated automatically after alignment')

    # def _valueChangedBoundingRect(self):
    #     pass


    def initControlPanel(self):

        button_size = QSize(54, 20)
        std_input_size = QSize(74, 20)
        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)
        baseline = Qt.AlignmentFlag.AlignBaseline
        vcenter  = Qt.AlignmentFlag.AlignVCenter
        hcenter  = Qt.AlignmentFlag.AlignHCenter
        center   = Qt.AlignmentFlag.AlignCenter
        left     = Qt.AlignmentFlag.AlignLeft
        right    = Qt.AlignmentFlag.AlignRight

        tip = 'Set Whether to Use or Reject the Current Layer'
        self._lab_keep_reject = QLabel('Reject:')
        self._lab_keep_reject.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414; color: #141414')
        self._lab_keep_reject.setStatusTip(tip)
        self._skipCheckbox = QCheckBox()
        self._skipCheckbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._skipCheckbox.setObjectName('_skipCheckbox')
        self._skipCheckbox.stateChanged.connect(self._callbk_skipChanged)
        self._skipCheckbox.stateChanged.connect(self._callbk_unsavedChanges)
        self._skipCheckbox.setStatusTip(tip)
        self._skipCheckbox.setEnabled(False)
        lay = QHBoxLayout()
        # lay.setSpacing(0)
        # lay.setContentsMargins(2, 0, 2, 0)
        lay.addWidget(self._lab_keep_reject, alignment=right)
        lay.addWidget(self._skipCheckbox, alignment=left)
        self._ctlpanel_skip = QWidget()
        self._ctlpanel_skip.setLayout(lay)

        tip = 'Use All Images (Reset)'
        self._btn_clear_skips = QPushButton('Reset')
        self._btn_clear_skips.setEnabled(False)
        self._btn_clear_skips.setStyleSheet("font-size: 10px;")
        self._btn_clear_skips.setStatusTip(tip)
        self._btn_clear_skips.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_clear_skips.clicked.connect(self.clear_skips)
        self._btn_clear_skips.setFixedSize(button_size)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        lab = QLabel("Whitening\nFactor:")
        lab.setAlignment(right)
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        self._whiteningControl = QDoubleSpinBox(self)
        self._whiteningControl.setFixedHeight(22)
        self._whiteningControl.valueChanged.connect(self._callbk_unsavedChanges)
        self._whiteningControl.valueChanged.connect(self._valueChangedWhitening)
        self._whiteningControl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self._whiteningControl.setValue(cfg.DEFAULT_WHITENING)
        self._whiteningControl.setFixedSize(std_input_size)
        self._whiteningControl.setDecimals(2)
        self._whiteningControl.setMinimum(-0.99)
        self._whiteningControl.setMaximum(0.99)
        self._whiteningControl.setEnabled(False)

        lab.setStatusTip(tip)
        self._whiteningControl.setStatusTip(tip)
        lay = QHBoxLayout()
        # lay.setSpacing(0)
        lay.addWidget(lab, alignment=right)
        lay.addWidget(self._whiteningControl, alignment=left)
        lay.setContentsMargins(0, 0, 0, 0)
        self._ctlpanel_whitening = QWidget()
        self._ctlpanel_whitening.setLayout(lay)

        tip = "The region size SWIM uses for computing alignment, specified as percentage of image" \
              "width. (default=81.25%)"
        lab = QLabel("SWIM\nWindow:")
        lab.setAlignment(right)
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        self._swimWindowControl = QDoubleSpinBox(self)
        self._swimWindowControl.setSuffix('%')
        self._swimWindowControl.setFixedHeight(22)
        self._swimWindowControl.valueChanged.connect(self._callbk_unsavedChanges)
        self._swimWindowControl.valueChanged.connect(self._valueChangedSwimWindow)
        self._swimWindowControl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self._swimWindowControl.setValue(cfg.DEFAULT_SWIM_WINDOW)
        self._swimWindowControl.setFixedSize(std_input_size)
        self._swimWindowControl.setDecimals(2)
        self._swimWindowControl.setEnabled(False)
        lab.setStatusTip(tip)
        self._swimWindowControl.setStatusTip(tip)
        lay = QHBoxLayout()
        # lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lab, alignment=right)
        lay.addWidget(self._swimWindowControl, alignment=left)
        self._ctlpanel_inp_swimWindow = QWidget()
        self._ctlpanel_inp_swimWindow.setLayout(lay)

        # tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        self._ctlpanel_applyAllButton = QPushButton("Apply To All\nSections")
        self._ctlpanel_applyAllButton.setEnabled(False)
        self._ctlpanel_applyAllButton.setStatusTip('Apply These Settings To The Entire Image Stack')
        self._ctlpanel_applyAllButton.setStyleSheet("font-size: 9px;")
        self._ctlpanel_applyAllButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._ctlpanel_applyAllButton.clicked.connect(self.apply_all)
        # self._ctlpanel_applyAllButton.setFixedSize(QSize(54, 20))
        self._ctlpanel_applyAllButton.setFixedSize(normal_button_size)

        self._gb_alignmentSettings = QGroupBox()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self._ctlpanel_inp_swimWindow)
        hbl.addWidget(self._ctlpanel_whitening)
        hbl.addWidget(self._ctlpanel_applyAllButton)
        # hbl.setAlignment()

        tip = 'Go To Next Scale.'
        self._scaleUpButton = QPushButton()
        self._scaleUpButton.setEnabled(False)
        self._scaleUpButton.setStyleSheet("font-size: 11px;")
        self._scaleUpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleUpButton.setStatusTip(tip)
        self._scaleUpButton.clicked.connect(self.scale_up)
        self._scaleUpButton.setFixedSize(QSize(18, 18))
        self._scaleUpButton.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        tip = 'Go To Previous Scale.'
        self._scaleDownButton = QPushButton()
        self._scaleDownButton.setEnabled(False)
        self._scaleDownButton.setStyleSheet("font-size: 11px;")
        self._scaleDownButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleDownButton.setStatusTip(tip)
        self._scaleDownButton.clicked.connect(self.scale_down)
        self._scaleDownButton.setFixedSize(QSize(18, 18))
        self._scaleDownButton.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        self._scaleSetWidget = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        self._scaleSetWidget.setLayout(hbl)
        hbl.addWidget(self._scaleDownButton, alignment=right)
        hbl.addWidget(self._scaleUpButton, alignment=left)

        lab = QLabel('Scale:')
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        self._ctlpanel_changeScale = QWidget()
        lay = QHBoxLayout()
        # hbl.setContentsMargins(0,0,0,0)
        # hbl.setSpacing(0)
        lay.addWidget(lab, alignment=right)
        lay.addWidget(self._scaleSetWidget, alignment=left)
        self._ctlpanel_changeScale.setLayout(lay)

        tip = 'Align + Generate All Layers For Current Scale'
        self._btn_alignAll = QPushButton('Align This\nScale')
        self._btn_alignAll.setEnabled(False)
        self._btn_alignAll.setStyleSheet("font-size: 9px;")
        self._btn_alignAll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignAll.setStatusTip(tip)
        self._btn_alignAll.clicked.connect(self.alignAll)
        self._btn_alignAll.setFixedSize(normal_button_size)

        tip = 'Align and Generate This Layer'
        self._btn_alignOne = QPushButton('Align This\nSection')
        self._btn_alignOne.setEnabled(False)
        self._btn_alignOne.setStyleSheet("font-size: 9px;")
        self._btn_alignOne.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignOne.setStatusTip(tip)
        self._btn_alignOne.clicked.connect(self.alignOne)
        self._btn_alignOne.setFixedSize(normal_button_size)

        tip = 'Align and Generate From Layer Current Layer to End'
        self._btn_alignForward = QPushButton('Align\nForward')
        self._btn_alignForward.setEnabled(False)
        self._btn_alignForward.setStyleSheet("font-size: 9px;")
        self._btn_alignForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignForward.setStatusTip(tip)
        self._btn_alignForward.clicked.connect(self.alignForward)
        self._btn_alignForward.setFixedSize(normal_button_size)

        tip = 'Automatically generate aligned images.'
        lab = QLabel("Auto-generate:")
        lab.setAlignment(right)
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        lab.setStatusTip(tip)
        self._toggleAutogenerate = ToggleSwitch()
        self._toggleAutogenerate.stateChanged.connect(self._toggledAutogenerate)
        self._toggleAutogenerate.stateChanged.connect(self._callbk_unsavedChanges)
        self._toggleAutogenerate.setStatusTip(tip)
        self._toggleAutogenerate.setChecked(True)
        self._toggleAutogenerate.setEnabled(False)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(lab, alignment=right | vcenter)
        hbl.addWidget(self._toggleAutogenerate, alignment=right | vcenter)
        self._ctlpanel_toggleAutogenerate = QWidget()
        self._ctlpanel_toggleAutogenerate.setLayout(hbl)

        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension. This' \
              ' option is set at the coarsest s, in order to form a contiguous dataset.'
        lab = QLabel("Corrective\nPolynomial:")
        lab.setAlignment(right)
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        lab.setStatusTip(tip)
        self._polyBiasCombo = QComboBox(self)
        self._polyBiasCombo.setStyleSheet("font-size: 11px;")
        self._polyBiasCombo.currentIndexChanged.connect(self._valueChangedPolyOrder)
        self._polyBiasCombo.currentIndexChanged.connect(self._callbk_unsavedChanges)
        self._polyBiasCombo.setStatusTip(tip)
        self._polyBiasCombo.addItems(['None', '0', '1', '2', '3', '4'])
        self._polyBiasCombo.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self._polyBiasCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._polyBiasCombo.setFixedSize(QSize(60, 18))
        self._polyBiasCombo.setEnabled(False)
        lay = QHBoxLayout()
        # lay.setSpacing(0)
        lay.setContentsMargins(2,2,2,2)
        lay.addWidget(lab, alignment=right)
        lay.addWidget(self._polyBiasCombo, alignment=left)
        self._ctlpanel_polyOrder = QWidget()
        self._ctlpanel_polyOrder.setLayout(lay)


        tip = 'Bounding rectangle (default=ON). Caution: Turning this ON may ' \
              'significantly increase the size of your aligned images.'
        lab = QLabel("Bounding Box:")
        # lab.setAlignment(right | vcenter)
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        lab.setStatusTip(tip)
        self._bbToggle = ToggleSwitch()
        # self._bbToggle.setChecked(True)
        self._bbToggle.setStatusTip(tip)
        self._bbToggle.toggled.connect(self._callbk_bnding_box)
        self._bbToggle.setEnabled(False)
        lay = QHBoxLayout()
        # hbl.setSpacing(1)
        # hbl.setContentsMargins(0,0,0,0)
        # hbl.addWidget(lab, alignment=baseline | Qt.AlignmentFlag.AlignRight)
        lay.addWidget(lab, alignment=right | vcenter)
        lay.addWidget(self._bbToggle, alignment=left | vcenter)
        self._ctlpanel_bb = QWidget()
        self._ctlpanel_bb.setLayout(lay)

        tip = "Recomputes the cumulative affine and generates new aligned images" \
              "based on the current Null Bias and Bounding Rectangle presets."
        self._btn_regenerate = QPushButton('Generate')
        self._btn_regenerate.setEnabled(False)
        self._btn_regenerate.setStatusTip(tip)
        self._btn_regenerate.clicked.connect(lambda: self.regenerate(scale=cfg.data.curScale))
        self._btn_regenerate.setFixedSize(normal_button_size)
        self._btn_regenerate.setStyleSheet("font-size: 10px;")

        self._wdg_alignButtons = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2,2,2,2)
        hbl.addWidget(self._btn_regenerate, alignment=right)
        hbl.addWidget(self._btn_alignOne, alignment=right)
        hbl.addWidget(self._btn_alignForward, alignment=right)
        hbl.addWidget(self._btn_alignAll, alignment=right)
        self._wdg_alignButtons.setLayout(hbl)
        lay.setContentsMargins(2,2,2,2)
        lab = QLabel('Actions\n(Highly Parallel):')
        lab.setAlignment(right | vcenter)
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        lay = QHBoxLayout()
        # vbl.setSpacing(1)
        lay.setContentsMargins(2,2,2,2)
        lay.addWidget(lab, alignment=right)
        lay.addWidget(self._wdg_alignButtons, alignment=left)
        self._ctlpanel_alignRegenButtons = QWidget()
        self._ctlpanel_alignRegenButtons.setLayout(lay)

        # wids = [
        #     self._ctlpanel_skip,
        #     self._ctlpanel_inp_swimWindow,
        #     self._ctlpanel_whitening,
        #     self._ctlpanel_applyAllButton,
        #     self._ctlpanel_polyOrder,
        #     self._ctlpanel_bb,
        #     self._ctlpanel_alignRegenButtons,
        #     self._ctlpanel_changeScale,
        # ]

        self._cpanelVLayout = QVBoxLayout()
        self._cpanelVLayout.setSpacing(1)
        hbl0 = QHBoxLayout()
        hbl1 = QHBoxLayout()
        hbl2 = QHBoxLayout()
        hbl0.setContentsMargins(0, 0, 0, 0)
        hbl1.setContentsMargins(0, 0, 0, 0)
        hbl2.setContentsMargins(0, 0, 0, 0)
        self._cpanelVLayout.addLayout(hbl0)
        self._cpanelVLayout.addLayout(hbl1)
        self._cpanelVLayout.addLayout(hbl2)

        hbl0.addWidget(self._ctlpanel_skip)
        hbl0.addWidget(self._ctlpanel_bb)
        hbl0.addWidget(self._ctlpanel_toggleAutogenerate)
        hbl0.addWidget(self._ctlpanel_changeScale)

        hbl1.addStretch()
        hbl1.addWidget(self._ctlpanel_polyOrder)
        hbl1.addStretch()
        hbl1.addWidget(self._ctlpanel_inp_swimWindow)
        hbl1.addStretch()
        hbl1.addWidget(self._ctlpanel_whitening)
        hbl1.addStretch()
        hbl1.addWidget(self._ctlpanel_applyAllButton)
        hbl1.addStretch()

        hbl2.addWidget(self._ctlpanel_alignRegenButtons)

        self._cpanel = ControlPanel(
            parent=self,
            name='ctl_panel',
            title='Control Panel',
            # items=wids,
            bg_color='#f3f6fb'
        )
        self._cpanel.setCustomLayout(self._cpanelVLayout)
        self._cpanel.setFixedWidth(520)
        self._cpanel.setMaximumHeight(120)


    def initUI(self):
        '''Initialize Main UI'''
        logger.info('')

        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)

        with open('src/styles/controls.qss', 'r') as f:
            lower_controls_style = f.read()

        '''Headup Display'''
        self.hud = HeadupDisplay(self.app)
        self.hud.setObjectName('hud')
        # path = 'src/resources/KeyboardCommands1.html'
        # with open(path) as f:
        #     contents = f.read()
        # self.hud.textedit.appendHtml(contents)
        self.user = getpass.getuser()
        self.tell(f'Hello {self.user}, We Hope You Enjoy AlignEM-SWiFT :).')


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

        # keyboard_commands = [
        #     QLabel('^N - New Project   ^O - Open Project   ^Z - Open Zarr'),
        #     QLabel('^S - Save          ^Q - Quit           ^↕ - Zoom'),
        #     QLabel(' , - Prev (comma)   . - Next (period)  ^K - Skip'),
        #     QLabel(' ← - Scale Down     → - Scale Up       ^A - Align All')
        # ]
        # f = QFont()
        # f.setFamily('Courier')
        # list(map(lambda x: x.setFont(f), keyboard_commands))
        # list(map(lambda x: x.setContentsMargins(0,0,0,0), keyboard_commands))
        # list(map(lambda x: x.setMargin(0), keyboard_commands))

        # self._tool_keyBindings = WidgetArea(parent=self, title='Keyboard Bindings', labels=keyboard_commands)
        # self._tool_keyBindings.setObjectName('_tool_keyBindings')
        # self._tool_keyBindings.setStyleSheet('font-size: 10px; '
        #                                       'font-weight: 500; color: #141414;')

        baseline = Qt.AlignmentFlag.AlignBaseline
        vcenter  = Qt.AlignmentFlag.AlignVCenter
        hcenter  = Qt.AlignmentFlag.AlignHCenter
        center   = Qt.AlignmentFlag.AlignCenter
        left     = Qt.AlignmentFlag.AlignLeft
        right    = Qt.AlignmentFlag.AlignRight

        self._processMonitorWidget = QWidget()
        lab = QLabel('Process Monitor')
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        vbl = QVBoxLayout()
        vbl.setSpacing(1)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self.hud)
        self._processMonitorWidget.setLayout(vbl)

        # self._btn_refresh = QPushButton('Refresh')
        # self._btn_refresh.clicked.connect(cfg.ng_worker.ini)


        # self.initControlPanel()

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
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        self.layer_details = QTextEdit()
        self.layer_details.setObjectName('layer_details')
        self.layer_details.setReadOnly(True)
        self._tool_textInfo = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        # vbl.addWidget(lab, alignment=baseline)
        # vbl.addWidget(self.layer_details)
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
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        vbl = QVBoxLayout()
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self._hstry_listWidget)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        self._tool_hstry.setLayout(vbl)

        self._hstry_treeview = QTreeView()
        self._hstry_treeview.setStyleSheet('background-color: #ffffff;')
        self._hstry_treeview.setObjectName('treeview')
        self.projecthistory_model = JsonModel()
        self._hstry_treeview.setModel(self.projecthistory_model)
        self._hstry_treeview.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._hstry_treeview.setAlternatingRowColors(True)
        self.exit_projecthistory_view_button = QPushButton("Back")
        self.exit_projecthistory_view_button.setFixedSize(normal_button_size)
        self.exit_projecthistory_view_button.clicked.connect(self.back_callback)
        gl = QGridLayout()
        gl.addWidget(self._hstry_treeview, 0, 0, 1, 2)
        gl.addWidget(self.exit_projecthistory_view_button, 1, 0, 1, 1)
        self.historyview_widget = QWidget()
        self.historyview_widget.setObjectName('historyview_widget')
        self.historyview_widget.setLayout(gl)

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
        self.splashmovie.finished.connect(self.runaftersplash)

        self.permFileBrowser = FileBrowser()

        self.viewer_stack_widget = QStackedWidget()
        self.viewer_stack_widget.setObjectName('viewer_stack_widget')
        self.viewer_stack_widget.addWidget(self.ng_widget)
        self.viewer_stack_widget.addWidget(self.splash_widget)
        self.viewer_stack_widget.addWidget(self.permFileBrowser)

        self._matchpt_ctls = QWidget()

        self.mp_marker_size_label = QLabel('Lineweight')
        self.mp_marker_size_spinbox = QSpinBox()
        self.mp_marker_size_spinbox.setMinimum(0)
        self.mp_marker_size_spinbox.setMaximum(32)
        self.mp_marker_size_spinbox.setSuffix('pt')
        self.mp_marker_size_spinbox.valueChanged.connect(self.set_mp_marker_lineweight)

        self.mp_marker_lineweight_label = QLabel('Size')
        self.mp_marker_lineweight_spinbox = QSpinBox()
        self.mp_marker_lineweight_spinbox.setMinimum(0)
        self.mp_marker_lineweight_spinbox.setMaximum(32)
        self.mp_marker_lineweight_spinbox.setSuffix('pt')
        self.mp_marker_lineweight_spinbox.valueChanged.connect(self.set_mp_marker_size)

        self.exit_matchpoint_button = QPushButton('Exit')
        self.exit_matchpoint_button.setStatusTip('Exit Match Point Mode')
        self.exit_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_matchpoint_button.clicked.connect(self.enterExitMatchPointMode)
        self.exit_matchpoint_button.setFixedSize(normal_button_size)

        self.realign_matchpoint_button = QPushButton('Realign\nSection')
        self.realign_matchpoint_button.setStatusTip('Realign The Current Layer')
        self.realign_matchpoint_button.setStyleSheet("font-size: 9px;")
        self.realign_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.realign_matchpoint_button.clicked.connect(self.alignOne)
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
        vbl.setContentsMargins(0,0,0,0)
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
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addStretch()
        hbl.addWidget(self._btn_show_hide_ctls, alignment=Qt.AlignCenter | Qt.AlignBottom)
        hbl.addWidget(self._btn_show_hide_console, alignment=Qt.AlignCenter| Qt.AlignBottom)
        hbl.addStretch()
        # hbl.addStretch()
        self._showHideFeatures.setLayout(hbl)
        self._showHideFeatures.setMaximumHeight(26)

        '''Tabs Global Widget'''
        self._tabsGlob = QTabWidget()
        # self._tabsGlob.setTabBarAutoHide(True)
        self._tabsGlob.setElideMode(Qt.ElideMiddle)
        self._tabsGlob.setMovable(True)
        self._tabsGlob.hide()
        # mic_icon = qta.icon('ph.microphone-fill')
        # self._tabsGlob.setStyleSheet('''QTabBar::close-button {
        #      image: %s
        #  }''' % mic_icon)
        # self._tabsGlob.setTabIcon(mic_icon)
        # self._tabsGlob.setCornerWidget(QLabel('test'))

        self._tabsGlob.setDocumentMode(True)
        self._tabsGlob.setTabsClosable(True)
        self._tabsGlob.setObjectName('_tabsGlob')
        self._tabsGlob.tabCloseRequested[int].connect(self._onGlobTabClose)
        self._tabsGlob.currentChanged.connect(self._onGlobTabChange)

        # with open('src/styles/controls.qss', 'r') as f:
        #     style = f.read()
        self._buttonOpen = QPushButton('Open')
        self._buttonOpen.clicked.connect(self.open_project_selected)
        self._buttonOpen.setFixedSize(64, 20)
        # self._buttonOpen.setStyleSheet(style)

        self._buttonDelete = QPushButton('Delete')
        self._buttonDelete.clicked.connect(self.delete_project)
        self._buttonDelete.setFixedSize(64, 20)
        # self._buttonDelete.setStyleSheet(style)

        self._buttonNew = QPushButton('New')
        self._buttonNew.clicked.connect(self.new_project)
        self._buttonNew.setFixedSize(64, 20)
        # self._buttonNew.setStyleSheet(style)

        # self._buttonNew = QPushButton('Remember')
        # self._buttonNew.setStyleSheet("font-size: 9px;")
        # self._buttonNew.clicked.connect(self.new_project)
        # self._buttonNew.setFixedSize(64, 20)
        # # self._buttonNew.setStyleSheet(style)

        # self.selectionReadout = QLabel('<h4>Selection:</h4>')
        # self.selectionReadout = QLabel()
        self.selectionReadout = QLineEdit()
        self.selectionReadout.returnPressed.connect(self.open_project_selected)
        # self.selectionReadout.textChanged.connect(lambda: print('Text Changed!'))
        # self.selectionReadout.textEdited.connect(lambda: print('Text Edited!'))
        self.selectionReadout.textEdited.connect(self.validateUserEnteredPath)
        self.selectionReadout.setFixedHeight(22)
        # self.selectionReadout.setFixedWidth(600)
        # self.selectionReadout.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.selectionReadout.setMinimumWidth(700)
        # self.selectionReadout.setReadOnly(True)

        self.validity_label = QLabel('Invalid')
        self.validity_label.setObjectName('validity_label')
        self.validity_label.setFixedHeight(20)
        self.validity_label.hide()

        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)

        # hbl.addWidget(self.selectionReadout)
        # hbl.addWidget(self._buttonOpen, alignment=Qt.AlignmentFlag.AlignLeft)
        # hbl.addWidget(self._buttonDelete, alignment=Qt.AlignmentFlag.AlignLeft)
        # hbl.addWidget(self._buttonNew, alignment=Qt.AlignmentFlag.AlignLeft)

        hbl.addWidget(self._buttonNew)
        hbl.addWidget(self.selectionReadout)
        hbl.addWidget(self.validity_label)
        hbl.addWidget(self._buttonOpen)
        hbl.addWidget(self._buttonDelete)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hbl.addSpacerItem(self.spacer_item_docs)

        self._buttonOpen.setEnabled(False)
        self._buttonDelete.setEnabled(False)


        self._actions_widget = QWidget()
        self._actions_widget.setFixedHeight(30)
        self._actions_widget.setLayout(hbl)

        self._controlPanelAndHud = QWidget()
        hbl = QHBoxLayout()
        # hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self._processMonitorWidget)
        hbl.addWidget(self._cpanel)
        vbl = QVBoxLayout()
        # vbl.setContentsMargins(6, 0, 6, 0)
        vbl.addWidget(self._actions_widget)
        vbl.addLayout(hbl)
        self._controlPanelAndHud.setLayout(vbl)
        self._controlPanelAndHud.resize(QSize(1000, 10))

        '''Main Vertical Splitter'''
        self._splitter = QSplitter(Qt.Orientation.Vertical)    # __SPLITTER INDEX__
        self._splitter.addWidget(self._tabsGlob)               # (0)
        self._splitter.addWidget(self._controlPanelAndHud)     # (1)
        self._splitter.addWidget(self._matchpt_ctls)           # (2)
        self._splitter.addWidget(self._py_console)             # (3)
        self._splitter.setSizes(self._mainVSplitterSizes)

        if cfg.DEV_MODE:
            self._dev_console = PythonConsole()
            self._splitter.addWidget(self._dev_console)           # (5)
            self._dev_console.hide()
        else:
            self._dev_console = None
        self._splitter.addWidget(self._showHideFeatures)  # (6)
        self._splitter.setHandleWidth(2)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, False)
        self._splitter.setCollapsible(3, False)
        self._splitter.setCollapsible(4, False)
        self._splitter.setStretchFactor(0, 7)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 1)
        self._splitter.setStretchFactor(3, 1)
        self._splitter.setStretchFactor(4, 1)

        '''Documentation Panel'''
        self.browser_web = QWebEngineView()
        # self.browser = WebPage(self)
        self._buttonExitBrowserWeb = QPushButton("Exit")
        self._buttonExitBrowserWeb.setFixedSize(64, 20)
        self._buttonExitBrowserWeb.setFixedSize(std_button_size)
        self._buttonExitBrowserWeb.clicked.connect(self.exit_docs)
        self._readmeButton = QPushButton("README.md")
        self._readmeButton.setFixedSize(std_button_size)
        self._readmeButton.clicked.connect(self.documentation_view)
        self.browser_widget = QWidget()
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        def browser_backward():
            self.browser_web.page().triggerAction(QWebEnginePage.Back)

        def browser_forward():
            self.browser_web.page().triggerAction(QWebEnginePage.Forward)

        def browser_reload():
            self.browser_web.page().triggerAction(QWebEnginePage.Reload)

        def browser_view_source():
            self.browser_web.page().triggerAction(QWebEnginePage.ViewSource)

        def browser_copy():
            self.browser_web.page().triggerAction(QWebEnginePage.Copy)

        def browser_paste():
            self.browser_web.page().triggerAction(QWebEnginePage.Paste)

        buttonBrowserBack = QPushButton()
        buttonBrowserBack.setStatusTip('Go Back')
        buttonBrowserBack.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserBack.clicked.connect(browser_backward)
        buttonBrowserBack.setFixedSize(QSize(20, 20))
        buttonBrowserBack.setIcon(qta.icon('fa.arrow-left', color=ICON_COLOR))

        buttonBrowserForward = QPushButton()
        buttonBrowserForward.setStatusTip('Go Forward')
        buttonBrowserForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserForward.clicked.connect(browser_forward)
        buttonBrowserForward.setFixedSize(QSize(20, 20))
        buttonBrowserForward.setIcon(qta.icon('fa.arrow-right', color=ICON_COLOR))

        buttonBrowserRefresh = QPushButton()
        buttonBrowserRefresh.setStatusTip('Refresh')
        buttonBrowserRefresh.setIcon(qta.icon("ei.refresh", color=cfg.ICON_COLOR))
        buttonBrowserRefresh.setFixedSize(QSize(22,22))
        buttonBrowserRefresh.clicked.connect(browser_reload)

        # buttonBrowserViewSource = QPushButton()
        # buttonBrowserViewSource.setStatusTip('View Source')
        # buttonBrowserViewSource.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # buttonBrowserViewSource.clicked.connect(browser_view_source)
        # buttonBrowserViewSource.setFixedSize(QSize(20, 20))
        # buttonBrowserViewSource.setIcon(qta.icon('ri.code-view', color=ICON_COLOR))

        buttonBrowserCopy = QPushButton('Copy')
        buttonBrowserCopy.setStatusTip('Copy Text')
        buttonBrowserCopy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserCopy.clicked.connect(browser_copy)
        buttonBrowserCopy.setFixedSize(QSize(50, 20))

        buttonBrowserPaste = QPushButton('Paste')
        buttonBrowserPaste.setStatusTip('Paste Text')
        buttonBrowserPaste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserPaste.clicked.connect(browser_paste)
        buttonBrowserPaste.setFixedSize(QSize(50, 20))

        button3demCommunity = QPushButton('3DEM Community Data')
        button3demCommunity.setStyleSheet('font-size: 10px;')
        button3demCommunity.setStatusTip('Vist the 3DEM Community Workbench')
        button3demCommunity.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button3demCommunity.clicked.connect(self.browser_3dem_community)
        button3demCommunity.setFixedSize(QSize(120, 20))

        #webpage
        browser_controls_widget = QWidget()
        browser_controls_widget.setFixedHeight(24)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserBack, alignment=right)
        hbl.addWidget(buttonBrowserForward, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserRefresh, alignment=left)
        # hbl.addWidget(QLabel(' '))
        # hbl.addWidget(buttonBrowserViewSource, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserCopy, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserPaste, alignment=left)
        hbl.addWidget(QLabel('   |   '))
        hbl.addWidget(button3demCommunity, alignment=left)
        browser_controls_widget.setLayout(hbl)

        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(browser_controls_widget, alignment=Qt.AlignmentFlag.AlignLeft)
        vbl.addWidget(self.browser_web)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self._buttonExitBrowserWeb, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(self._readmeButton, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(w)
        browser_bottom_controls = QWidget()
        browser_bottom_controls.setFixedHeight(24)
        browser_bottom_controls.setLayout(hbl)
        # self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # hbl.addSpacerItem(self.spacer_item_docs)
        vbl.addWidget(browser_bottom_controls)
        self.browser_widget.setLayout(vbl)

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
        self.main_stack_widget.addWidget(self.browser_widget)           # (1)
        self.main_stack_widget.addWidget(self._wdg_demos)           # (2)
        self.main_stack_widget.addWidget(self._wdg_remote_viewer)   # (3)
        self.main_panel.setLayout(vbl)
        self.setWindowIcon(QIcon(QPixmap('src/resources/em_guy_icon.png')))
        self.setCentralWidget(self.main_stack_widget)


    def validateUserEnteredPath(self):
        cfg.selected_file = self.selectionReadout.text()
        if validate_selection():
            self.validity_label.hide()
            self._buttonOpen.setEnabled(True)
            self._buttonDelete.setEnabled(True)
        else:
            self.validity_label.show()
            self._buttonOpen.setEnabled(False)
            self._buttonDelete.setEnabled(False)

    def setSelectionPathText(self, path):
        self.selectionReadout.setText(path)
        if validate_selection():
            self.validity_label.hide()
            self._buttonOpen.setEnabled(True)
            self._buttonDelete.setEnabled(True)
        else:
            self.validity_label.show()
            self._buttonOpen.setEnabled(False)
            self._buttonDelete.setEnabled(False)

    def clearSelectionPathText(self):
        self.selectionReadout.setText('')

    def initLaunchTab(self):
        self._launchScreen = OpenProject()
        self._tabsGlob.addTab(self._launchScreen, 'Welcome')



    def get_application_root(self):
        return Path(__file__).parents[2]


    def initWidgetSpacing(self):
        logger.info('')
        self._py_console.setContentsMargins(0, 0, 0, 0)
        self.hud.setContentsMargins(2, 0, 2, 0)
        self.layer_details.setContentsMargins(0, 0, 0, 0)
        self.matchpoint_text_snr.setMaximumHeight(20)
        self._tool_hstry.setMinimumWidth(248)
        # cfg.project_tab._transformationWidget.setFixedWidth(248)
        # cfg.project_tab._transformationWidget.setFixedSize(248,100)
        self.layer_details.setMinimumWidth(248)


    def initStatusBar(self):
        logger.info('')
        self.statusBar = self.statusBar()
        # self.statusBar.setFixedHeight(30)
        self.statusBar.setFixedHeight(26)


    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(True)
        font = QFont('Arial', 12)
        font.setBold(True)
        self.pbar.setFont(font)
        # self.pbar.setFixedHeight(18)
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
        # if self._working == False:
        #     self.statusBar.showMessage('Idle')
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


    def store_var(self, name, var):
        setattr(cfg, name, var)

