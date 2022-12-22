#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os
import shutil
import sys
import copy
import json
import threading
import inspect
import logging
import operator
import pprint
import textwrap
import tracemalloc
from pathlib import Path
import zarr
import dis
from collections import namedtuple
import numpy as np
import pyqtgraph.console
import neuroglancer as ng
import pyqtgraph as pg
import qtawesome as qta
import qtpy
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QDir, QFileSystemWatcher
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication, QKeySequence, QCursor, QImageReader, QMovie, QImage
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QSpacerItem, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QDialog, QStyle, QCheckBox, QSpinBox, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView, QTabWidget, QStatusBar, QTextBrowser

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
from src.helpers import natural_sort, get_snr_average, make_affine_widget_HTML, is_tacc, \
    create_project_structure_directories, get_aligned_scales, tracemalloc_start, tracemalloc_stop, \
    tracemalloc_compare, tracemalloc_clear
from src.ng_host import NgHost
from src.ng_host_slim import NgHostSlim
from src.ui.dialogs import AskContinueDialog, ConfigProjectDialog, ConfigAppDialog, QFileDialogPreview, \
    import_images_dialog, new_project_dialog, open_project_dialog, export_affines_dialog, mendenhall_dialog
# from src.napari_test import napari_test
from src.ui.headup_display import HeadupDisplay
from src.ui.kimage_window import KImageWindow
from src.ui.snr_plot import SnrPlot
from src.ui.toggle_switch import ToggleSwitch
from src.ui.models.json_tree import JsonModel
from src.ui.layer_view_widget import LayerViewWidget
from src.ui.ui_custom import VerticalLabel, HorizontalLabel
from src.mendenhall_protocol import Mendenhall
import src.pairwise


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
        self.setWindowIcon(QIcon(QPixmap('src/resources/sims.png')))
        # self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.initThreadpool(timeout=3000)
        self.initImageAllocations()
        self.initOpenGlContext()
        self.initWebEngine()
        self.initPythonConsole()
        self.initStatusBar()
        self.initPbar()
        self.initToolbar()
        self.initUI()
        self.initMenu()
        self.initWidgetSpacing()
        self.initSize(cfg.WIDTH, cfg.HEIGHT)
        self.initPos()
        self.initStyle()
        self.initPrivateMembers()
        self.initShortcuts()
        self.initData()
        self.initView()

        if is_tacc():
            cfg.USE_TORNADO = True

        if not cfg.NO_SPLASH:
            self.show_splash()


    def initSize(self, width, height):
        self.resize(width, height)


    def initPos(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def resizeEvent(self, event):
        self.resized.emit()
        if cfg.data:
            # self.refreshNeuroglancerURL()
            self.initNgViewer()
        return super(MainWindow, self).resizeEvent(event)


    def initData(self):
        logger.info('')
        cfg.data = None
        if cfg.DUMMY:
            with open('tests/example.proj', 'r') as f:
                data = json.load(f)
            project = DataModel(data=data)
            cfg.data = copy.deepcopy(project)
            cfg.data.set_paths_absolute(head='tests/example.proj')  # Todo This may not work
            cfg.data.link_all_stacks()
            self.onStartProject()


    def initThreadpool(self, timeout=3000):
        logger.info('')
        self.threadpool = QThreadPool(self)  # important consideration is this 'self' reference
        self.threadpool.setExpiryTimeout(timeout)  # ms


    def initImageAllocations(self):
        logger.info('')
        if qtpy.PYSIDE6:
            QImageReader.setAllocationLimit(0)  # PySide6 only
        os.environ['QT_IMAGEIO_MAXALLOC'] = "1_000_000_000_000_000"
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 1_000_000_000_000


    def initOpenGlContext(self):
        logger.info('')
        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())


    def initWebEngine(self):
        # Performance with settings: Function 'initWebEngine' executed in 0.1939s
        # Without: Function 'initWebEngine' executed in 0.0001s
        logger.info('')
        self.ng_browser = QWebEngineView()
        # self.browser.setPage(CustomWebEnginePage(self)) # open links in new window
        # if qtpy.PYSIDE6:
        # if is_tacc():
        self.ng_browser.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        self.ng_browser.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.ng_browser.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        self.ng_browser.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.ng_browser.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)


    def initPrivateMembers(self):
        logger.info('')
        self._unsaved_changes = False
        self._working = False
        self._is_mp_mode = False
        self._is_viewer_expanded = False
        self._layout = 1
        # self._up = 0
        self._scales_combobox_switch = 0 #1125
        self._jump_to_worst_ticker = 1  # begin iter at 1 b/c first image has no ref
        self._jump_to_best_ticker = 0
        self._snr_by_scale = dict() #Todo
        # cfg.ng_workers = {}


    def initStyle(self):
        logger.info('')
        self.main_stylesheet = os.path.abspath('styles/default.qss')
        self.apply_default_style()


    def initPythonConsole(self):
        logger.info('')
        ## build an initial namespace for console commands to be executed in (this is optional;
        ## the user can always import these modules manually)
        namespace = {
            'pg': pg,
            'np': np,
            'cfg': src.config,
            'mw': src.config.main_window,
            'viewer': cfg.viewer
        }

        ## initial text to display in the console
        text = """
        Caution - anything executed here is injected into the main event loop of AlignEM-SWiFT!
        """
        self.python_console_ = pyqtgraph.console.ConsoleWidget(namespace=namespace, text=text)
        self.label_python_console = QLabel('Python Console')
        self.label_python_console.setStyleSheet('font-size: 10px;')
        self.python_console = QWidget()
        self.python_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.python_console_lay = QVBoxLayout()
        self.python_console_lay.addWidget(self.label_python_console)
        self.python_console_lay.addWidget(self.python_console_)
        self.python_console.setLayout(self.python_console_lay)
        self.python_console.setObjectName('python_console')
        self.python_console.hide()


    def initView(self):
        logger.info('')
        self.tabs_main.show()
        self.full_window_controls.hide()
        self.main_stack_widget.setCurrentIndex(0)
        self.tabs_main.setCurrentIndex(0)
        self.toolbar_scale_combobox.setEnabled(True)
        self.update_ng_hyperlink()
        cfg.SHADER = None
        self.image_panel_stack_widget.setCurrentIndex(1)

        if cfg.data:
            self._is_mp_mode = False
            # self.image_panel_stack_widget.setCurrentIndex(1)
            if is_cur_scale_aligned():
                self.updateStatusTips()
            self.matchpoint_controls.hide()
            self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))
        else:
            # # self.image_panel_stack_widget.setCurrentIndex(2)
            # self.image_panel_stack_widget.setCurrentIndex(1)
            pass

        if cfg.HEADLESS:
            self.tabs_main.setTabVisible(0, False)
        else:
            self.tabs_main.setTabVisible(0, True)


    def update_ng_hyperlink(self):
        if cfg.data:
            # url = cfg.ng_workers[cfg.data.scale()].viewer.get_viewer_url()
            url = cfg.viewer.url
            self.external_hyperlink.clear()
            self.external_hyperlink.append(f"<a href='{url}'>Open In Browser</a>")


    def show_hide_python_callback(self):
        if self.python_console.isHidden():
            self.python_console.show()
            self.initNgViewer()
            self.show_hide_python_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_python_button.setText('Hide Python')
        else:
            self.python_console.hide()
            self.initNgViewer()
            self.show_hide_python_button.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))
            self.show_hide_python_button.setText(' Python')


    def force_show_controls(self):
        self.dataUpdateWidgets()  # for short-circuiting speed-ups
        self.new_control_panel.show()
        self.splitter_bottom_horizontal.show()
        self.show_hide_controls_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
        self.show_hide_controls_button.setText('Hide Controls')


    def show_hide_controls_callback(self):
        if self.new_control_panel.isHidden():
            self.force_show_controls()
        else:
            self.new_control_panel.hide()
            self.splitter_bottom_horizontal.hide()
            self.show_hide_controls_button.setIcon(qta.icon("ei.adjust-alt", color='#f3f6fb'))
            self.show_hide_controls_button.setText('Controls')


    def autoscale(self, make_thumbnails=True):
        #Todo This should check for existence of original source files before doing anything
        # self.image_panel_stack_widget.setCurrentIndex(2)
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.stopNgServer()
        self.hud.post('Generating TIFF Scale Hierarchy...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_scales())
                self.threadpool.start(self.worker)
            else:
                generate_scales()
        except:
            print_exception()
            self.hud('Something Unexpected Happened While Generating TIFF Scale Hierarchy', logging.WARNING)

        cfg.data.link_all_stacks() #Todo: check if this is necessary
        self.snr_plot.wipePlot() #Todo: Move this it should not be here
        cfg.data.set_scale(cfg.data.scales()[-1])

        for s in cfg.data.scales():
            cfg.data.set_image_size(scale=s)

        self.set_status('Copy-converting TIFFs...')
        self.hud.post('Copy-converting TIFFs to Zarr...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_zarr_scales())
                self.threadpool.start(self.worker)
            else:
                generate_zarr_scales()
        except:
            print_exception()
            self.hud('Something Unexpected Happened While Converting The Scale Hierarchy To Zarr', logging.WARNING)

        if make_thumbnails:
            self.set_status('Generating Thumbnails...')
            self.hud.post('Generating Thumbnails...')
            self.showZeroedPbar()
            try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(fn=generate_thumbnails())
                    self.threadpool.start(self.worker)
                else:
                    generate_thumbnails()

            except:
                print_exception()
                self.hud('Something Unexpected Happened While Generating Thumbnails', logging.WARNING)

            finally:
                # self.initNgServer()
                cfg.data.nscales = len(cfg.data.scales())
                cfg.data.set_scale(cfg.data.scales()[-1])
                self.pbar.hide()
                logger.info('Autoscaling Complete')


    def onAlignmentEnd(self):
        logger.critical('Running post-alignment/regenerate tasks...')
        s = cfg.data.scale()
        cfg.data.scalesAligned = get_aligned_scales()
        cfg.data.nScalesAligned = len(cfg.data.scalesAligned)
        self.updateHistoryListWidget(s=s)
        self.dataUpdateWidgets()
        logger.info(f'aligned scales list: {cfg.data.scalesAligned}')
        self.snr_plot.initSnrPlot()
        self.updateBanner()
        self.updateEnabledButtons()
        self.project_model.load(cfg.data.to_dict())
        self.initNgServer(scales=[cfg.data.scale()]) #1203+
        self.app.processEvents()


    def align_all(self, scale=None) -> None:

        if not cfg.data:
            self.hud.post('No data yet!', logging.WARNING)
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud.post(warning_msg, logging.WARNING)
            return

        self.stopNgServer()

        logger.info('Aligning All...')
        self.showZeroedPbar()
        if scale == None: scale = cfg.data.scale()
        scale_val = get_scale_val(scale)
        self.widgetsUpdateData()
        is_realign = is_cur_scale_aligned()
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
            self.hud.post("Computing Initial Affine Transforms,  Scale %d..." % scale_val)
        else:
            self.hud.post("Computing Refinement of Affine Transforms,  Scale %d..." % scale_val)
        self.set_status('Aligning...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=compute_affines(
                        scale=scale,
                        start_layer=0,
                        num_layers=-1
                    )
                )
                self.threadpool.start(self.worker)
            else:
                compute_affines(
                    scale=scale,
                    start_layer=0,
                    num_layers=-1
                )

        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)
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
            self.hud.post('Re-alignment Results:')
            self.hud.post('  # Better (SNR ↑) : %s' % ' '.join(map(str, pos)))
            self.hud.post('  # Worse  (SNR ↓) : %s' % ' '.join(map(str, neg)))
            self.hud.post('  # Equal  (SNR =) : %s' % ' '.join(map(str, no_chg)))
            if diff_avg > 0:
                self.hud.post('  Δ SNR : +%.3f (BETTER)' % diff_avg)
            else:
                self.hud.post('  Δ SNR : -%.3f (WORSE)' % diff_avg)

            # self.hud.post('Layers whose SNR changed value: %s' % str(diff_indexes))
        self.hud.post('Generating Aligned Images...')
        self.set_status('Generating Alignment...')

        try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(
                        fn=generate_aligned(
                            scale=scale,
                            start_layer=0,
                            num_layers=-1,
                            preallocate=True
                        )
                    )
                    self.threadpool.start(self.worker)
                else:
                    fn = generate_aligned(
                        scale=scale,
                        start_layer=0,
                        num_layers=-1,
                        preallocate=True
                    )

        except:
            print_exception()
            self.hud.post('Alignment Succeeded But Image Generation Failed Unexpectedly. '
                          'Try Re-generating images.', logging.ERROR)
        else:
            self.hud.post('Alignment Complete')
            self.save_project_to_file()
        finally:
            self.onAlignmentEnd()
            self.set_idle()
            self.pbar.hide()
            QApplication.processEvents()


    def align_forward(self, scale=None, num_layers=-1) -> None:

        if not cfg.data:
            self.hud.post('No data yet!', logging.WARNING)
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return

        if not is_cur_scale_aligned():
            self.hud.post('Please align the full series first!', logging.WARNING)
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud.post(warning_msg, logging.WARNING)
            return

        self.stopNgServer()

        logger.info('Aligning Forward...')
        self.showZeroedPbar()
        if scale == None: scale = cfg.data.scale()
        scale_val = get_scale_val(scale)
        self.widgetsUpdateData()
        start_layer = cfg.data.layer()
        self.hud.post('Computing Alignment For Layers %d -> End,  Scale %d...' % (start_layer, scale_val))
        self.set_status('Aligning...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=compute_affines(
                        scale=scale,
                        start_layer=start_layer,
                        num_layers=num_layers
                    )
                )
            else:
                self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)

        self.hud.post('Generating Aligned Images From Layers %d -> End,  Scale  %d...' % (start_layer, scale_val))
        self.set_status('Generating Alignment...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=generate_aligned(scale=scale, start_layer=start_layer, num_layers=num_layers, preallocate=False))
                self.threadpool.start(self.worker)
            else:
                generate_aligned(scale=scale, start_layer=start_layer, num_layers=num_layers, preallocate=False)
        except:
            print_exception()
            self.hud.post('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.', logging.ERROR)

        else:
            self.hud.post('Alignment Complete')
            self.save_project_to_file()
        finally:
            self.onAlignmentEnd()
            self.set_idle()
            self.pbar.hide()
            QApplication.processEvents()


    def align_one(self, scale=None) -> None:

        if cfg.data is None:
            self.hud.post('No data yet!', logging.WARNING)
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return

        if not is_cur_scale_aligned():
            self.hud.post('Please align the full series first!', logging.WARNING)
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud.post(warning_msg, logging.WARNING)
            return

        self.stopNgServer()

        logger.info('SNR Before: %s' % str(cfg.data.snr_report()))
        logger.info('Aligning Single Layer...')
        if scale == None: scale = cfg.data.scale()
        scale_val = get_scale_val(scale)
        self.widgetsUpdateData()
        self.hud.post('Re-aligning The Current Layer,  Scale %d...' % scale_val)
        self.set_status('Aligning...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=compute_affines(
                        scale=scale,
                        start_layer=cfg.data.layer(),
                        num_layers=1
                    )
                )
                self.threadpool.start(self.worker)
            else:
                compute_affines(
                    scale=scale,
                    start_layer=cfg.data.layer(),
                    num_layers=1
                )
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)

        cur_layer = cfg.data.layer()
        self.hud.post('Generating Aligned Image For Layer %d Only...' % cur_layer)
        self.set_status('Generating Alignment...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=generate_aligned(scale=scale, start_layer=cur_layer, num_layers=1, preallocate=False))
                self.threadpool.start(self.worker)
            else:
                generate_aligned(scale=scale, start_layer=cur_layer, num_layers=1, preallocate=False)
        except:
            print_exception()
            self.hud.post('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.', logging.ERROR)
        else:
            self.hud.post('Alignment Complete')
            self.save_project_to_file()
        finally:
            self.onAlignmentEnd()
            self.update_match_point_snr()
            self.set_idle()
            self.pbar.hide()
            QApplication.processEvents()


    def regenerate(self, scale) -> None:

        if cfg.data is None:
            self.hud.post('No data yet!', logging.WARNING)
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return

        if not is_cur_scale_aligned():
            self.hud.post('Please align the full series first!', logging.WARNING)
            return

        if not is_cur_scale_aligned():
            self.hud.post('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING)
            return
        self.widgetsUpdateData()

        self.stopNgServer()

        logger.info('Regenerate Aligned Images...')
        self.showZeroedPbar()
        self.hud.post('Regenerating Aligned Images,  Scale %d...' % get_scale_val(scale))
        try:
            if cfg.USE_EXTRA_THREADING:
                self.set_status('Regenerating Alignment...')
                self.worker = BackgroundWorker(
                    fn=generate_aligned(
                        scale=scale,
                        start_layer=0,
                        num_layers=-1,
                        preallocate=True
                    )
                )
                self.threadpool.start(self.worker)
            else:
                generate_aligned(
                    scale=scale,
                    start_layer=0,
                    num_layers=-1,
                    preallocate=True
                )
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Image Generation.', logging.ERROR)
        else:
            self.dataUpdateWidgets()
            self.save_project_to_file()
        finally:
            self.updateJsonWidget()
            self.initNgViewer()
            if are_aligned_images_generated():
                self.hud.post('Regenerate Succeeded')
            else:
                self.hud.post('Image Generation Failed Unexpectedly. Try Re-aligning.', logging.ERROR)
            self.set_idle()
            self.pbar.hide()
            QApplication.processEvents()


    def generate_multiscale_zarr(self):
        pass


    def export(self):
        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return
        if not are_aligned_images_generated():
            logger.warning('Aligned Images Do Not Exist')
            return
        logger.critical('Exporting To Zarr...')
        self.hud.post('Exporting...')
        self.hud.post('Generating Neuroglancer-Compatible Zarr...')
        src = os.path.abspath(cfg.data['data']['destination_path'])
        out = os.path.abspath(os.path.join(src, 'img_aligned.zarr'))
        self.hud.post('  Compression Level: %s' % cfg.CLEVEL)
        self.hud.post('  Compression Type: %s' % cfg.CNAME)
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
        self.has_unsaved_changes()
        self.hud.post('Process Finished')


    @Slot()
    def clear_skips(self):
        if cfg.data.are_there_any_skips():
            reply = QMessageBox.question(self,
                                         'Verify Reset Skips',
                                         'Clear all skips? This makes all layers unskipped.',
                                         QMessageBox.Cancel | QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                try:
                    self.hud.post('Resetting Skips...')
                    cfg.data.clear_all_skips()
                except:
                    print_exception()
                    self.hud.post('Something Went Wrong', logging.WARNING)
                else:
                    self.hud.done()
        else:
            self.hud.post('There Are No Skips To Clear.', logging.WARNING)
            return


    @Slot()
    def apply_all(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        swim_val = float(self.swim_input.text())
        whitening_val = float(self.whitening_input.text())
        scales_dict = cfg.data['data']['scales']
        self.hud.post('Applying These Settings To All Layers...')
        self.hud.post('  SWIM Window  : %s' % str(swim_val))
        self.hud.post('  Whitening    : %s' % str(whitening_val))
        for scale_key in scales_dict.keys():
            scale = scales_dict[scale_key]
            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                atrm = layer['align_to_ref_method']
                mdata = atrm['method_data']
                mdata['win_scale_factor'] = swim_val
                mdata['whitening_factor'] = whitening_val


    def enableGlobalButtons(self):
        self.apply_all_button.setEnabled(True)
        self.toggle_skip.setEnabled(True)
        self.whitening_input.setEnabled(True)
        self.swim_input.setEnabled(True)
        self.toggle_auto_generate.setEnabled(True)
        self.toggle_bounding_rect.setEnabled(True)
        self.bias_bool_combo.setEnabled(True)
        self.clear_skips_button.setEnabled(True)

    def enableAllButtons(self):
        self.align_all_button.setEnabled(True)
        self.align_one_button.setEnabled(True)
        self.align_forward_button.setEnabled(True)
        self.regenerate_button.setEnabled(True)
        self.prev_scale_button.setEnabled(True)
        self.next_scale_button.setEnabled(True)
        self.apply_all_button.setEnabled(True)
        self.toggle_skip.setEnabled(True)
        self.whitening_input.setEnabled(True)
        self.swim_input.setEnabled(True)
        self.toggle_auto_generate.setEnabled(True)
        self.toggle_bounding_rect.setEnabled(True)
        self.bias_bool_combo.setEnabled(True)
        self.clear_skips_button.setEnabled(True)


    def updateEnabledButtons(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev s buttons depending on current s.
        (2) Set the enabled/disabled state of the align_all-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        self.align_all_button.setText('Align All\n%s' % cfg.data.scale_pretty())
        if is_cur_scale_aligned():
            self.align_all_button.setEnabled(True)
            self.align_one_button.setEnabled(True)
            self.align_forward_button.setEnabled(True)
            self.regenerate_button.setEnabled(True)
        else:
            self.align_one_button.setEnabled(False)
            self.align_forward_button.setEnabled(False)
            self.regenerate_button.setEnabled(False)
        if cfg.data.is_alignable():
            self.align_all_button.setEnabled(True)
        else:
            self.align_all_button.setEnabled(False)
        if cfg.data.nscales == 1:
            self.next_scale_button.setEnabled(False)
            self.prev_scale_button.setEnabled(False)
            self.align_all_button.setEnabled(True)
            self.regenerate_button.setEnabled(True)
        else:
            cur_index = self.toolbar_scale_combobox.currentIndex()
            if cur_index == 0:
                self.prev_scale_button.setEnabled(True)
                self.next_scale_button.setEnabled(False)
            elif cfg.data.n_scales() == cur_index + 1:
                self.prev_scale_button.setEnabled(False)
                self.next_scale_button.setEnabled(True)
            else:
                self.prev_scale_button.setEnabled(True)
                self.next_scale_button.setEnabled(True)


    def updateJsonWidget(self):
        if cfg.data:
            self.project_model.load(cfg.data.to_dict())


    @Slot()
    def updateBanner(self, s=None) -> None:
        '''Update alignment details in the Alignment control panel group box.'''
        # logger.info('updateBanner... called By %s' % inspect.stack()[1].function)
        # self.align_all_button.setText('Align All\n%s' % cfg.data.scale_pretty())
        if s == None: s = cfg.data.scale()

        if is_cur_scale_aligned():
            self.alignment_status_label.setText("Aligned")
            self.alignment_status_label.setStyleSheet('color: #41FF00;')
        else:
            self.alignment_status_label.setText("Not Aligned")
            self.alignment_status_label.setStyleSheet('color: #FF0000;')
        try:
            img_size = cfg.data.image_size(s=s)
            self.align_label_resolution.setText('%sx%spx' % (img_size[0], img_size[1]))
        except:
            self.align_label_resolution.setText('')
            logger.warning('Unable To Determine Image Size.')
        # Todo fix renaming bug where files are not relinked
        # self.align_label_affine.setText(method_str)


    @Slot()
    def get_auto_generate_state(self) -> bool:
        '''Simple get function to get boolean state of auto-generate toggle.'''
        return True if self.toggle_auto_generate.isChecked() else False


    @Slot()
    def toggle_auto_generate_callback(self) -> None:
        '''Update HUD with new toggle state. Not data-driven.'''
        if self.toggle_auto_generate.isChecked():
            self.hud.post('Images will be generated automatically after alignment')
        else:
            self.hud.post('Images will not be generated automatically after alignment')


    @Slot()
    def scale_up(self) -> None:
        '''Callback function for the Next Scale button.'''
        cur_layer = self.request_ng_layer()
        if not self.next_scale_button.isEnabled():
            return
        if self._working:
            self.hud.post('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            self.toolbar_scale_combobox.setCurrentIndex(self.toolbar_scale_combobox.currentIndex() - 1)  # Changes Scale
            cfg.data.set_layer(cur_layer)
            # if not cfg.data.is_alignable():
            #     self.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
        except:
            print_exception()


    @Slot()
    def scale_down(self) -> None:
        '''Callback function for the Previous Scale button.'''
        cur_layer = self.request_ng_layer()
        assert isinstance(cur_layer, int)
        if not self.prev_scale_button.isEnabled():
            return
        if self._working:
            self.hud.post('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            self.toolbar_scale_combobox.setCurrentIndex(self.toolbar_scale_combobox.currentIndex() + 1)  # Changes Scale
            cfg.data.set_layer(cur_layer) # Set layer to layer last visited at previous s
            # if not cfg.data.is_alignable():
            #     self.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
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
        if inspect.stack()[1].function != 'initStyle':
            self.hud.post('Setting Default Theme')
        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        pg.setConfigOption('background', '#1B1E23')
        self.hud.set_theme_default()
        self.toolbar_scale_combobox.setStyleSheet('background-color: #f3f6fb; color: #000000;')
        if cfg.data:
            if inspect.stack()[1].function != 'initStyle':
                self.initNgViewer(scales=[cfg.data.scale()])


    def apply_daylight_style(self):
        cfg.THEME = 1
        if inspect.stack()[1].function != 'initStyle':
            self.hud.post('Setting Daylight Theme')
        self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        pg.setConfigOption('background', 'w')
        self.hud.set_theme_light()
        self.image_panel_landing_page.setStyleSheet('background-color: #fdf3da')
        if cfg.data:
            if inspect.stack()[1].function != 'initStyle':
                self.initNgViewer(scales=[cfg.data.scale()])


    def apply_moonlit_style(self):
        cfg.THEME = 2
        if inspect.stack()[1].function != 'initStyle':
            self.hud.post('Setting Moonlit Theme')
        self.main_stylesheet = os.path.abspath('src/styles/moonlit.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #333333')
        if cfg.data:
            if inspect.stack()[1].function != 'initStyle':
                self.initNgViewer(scales=[cfg.data.scale()])


    def apply_sagittarius_style(self):
        cfg.THEME = 3
        if inspect.stack()[1].function != 'initStyle':
            self.hud.post('Setting Sagittarius Theme')
        self.main_stylesheet = os.path.abspath('src/styles/sagittarius.qss')
        with open(self.main_stylesheet, 'r') as f:
            self.setStyleSheet(f.read())
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #000000')
        if cfg.data:
            if inspect.stack()[1].function != 'initStyle':
                self.initNgViewer(scales=[cfg.data.scale()])


    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')


    def onScaleChange(self):
        s = cfg.data.scale()
        # self.shutdownNeuroglancer() #1203+
        logger.debug('Changing To Scale %s (caller %s)...' % (s, inspect.stack()[1].function))
        # self.initNgServer(scales=[s])
        # self.refreshNeuroglancerURL(s=cfg.data.s())
        if cfg.SIMULTANEOUS_SERVERS:
            self.initNgViewer(scales=[cfg.data.scale()])
        else:
            self.initNgServer()
            # self.initNgViewer()
        self.jump_to(cfg.data.layer())
        self.dataUpdateWidgets()
        self.updateHistoryListWidget(s=s)
        self.project_model.load(cfg.data.to_dict())
        self.updateBanner(s=s)
        self.updateEnabledButtons()
        self.updateStatusTips()
        self.update_ng_hyperlink()
        if self.tabs_main.currentIndex() == 1:
            self.layer_view_widget.set_data()
        self.dataUpdateWidgets()



    @Slot()
    def widgetsUpdateData(self) -> None:
        '''Reads MainWindow to Update Project Data.'''
        #1109 refactor - no longer can be called for every layer change...
        logger.debug('widgetsUpdateData:')
        if self.bias_bool_combo.currentText() == 'None':
            cfg.data.set_use_poly_order(False)
        else:
            cfg.data.set_use_poly_order(True)
            cfg.data.set_poly_order(self.bias_bool_combo.currentText())
        cfg.data.set_use_bounding_rect(self.toggle_bounding_rect.isChecked(), s=cfg.data.scale())
        cfg.data.set_whitening(float(self.whitening_input.text()))
        cfg.data.set_swim_window(float(self.swim_input.text()))

    @Slot()
    def dataUpdateWidgets(self, ng_layer=None) -> None:
        '''Reads Project Data to Update MainWindow.'''

        if not cfg.data:
            logger.warning('No need to update the interface')
            return

        # if cfg.data.is_mendenhall():
        #     self.browser_overlay_widget.hide()
        #     return

        if self._working == True:
            logger.warning("Can't update GUI now - working...")
            self.hud.post("Can't update GUI now - working...", logging.WARNING)
            return
        if isinstance(ng_layer, int):
            try:
                if 0 <= ng_layer < cfg.data.n_layers():
                    cfg.data.set_layer(ng_layer)
                    self.browser_overlay_widget.hide()
                    self.browser_overlay_label.hide()
                    QApplication.processEvents()
                elif ng_layer >= cfg.data.n_layers():
                    self.browser_overlay_widget.setStyleSheet('background-color: rgba(0, 0, 0, 1.0);')
                    self.browser_overlay_label.setText('End Of Image Stack')
                    self.browser_overlay_label.show()
                    self.browser_overlay_widget.show()
                    QApplication.processEvents()
                    self.clearTextWidgetA()
                    self.clearAffineWidget()
                    # logger.info(f'Showing Browser Overlay, Last Layer ({cfg.data.layer()}) - Returning') #Todo
                    return
            except:
                print_exception()


        # else:
            # logger.info('Updating (caller: %s)...' % inspect.stack()[1].function)

        if cfg.data.skipped():
            self.browser_overlay_widget.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
            self.browser_overlay_label.setText('X SKIPPED - %s' % cfg.data.name_base())
            self.browser_overlay_label.show()
            self.browser_overlay_widget.show()
        else:
            self.browser_overlay_widget.hide()
            self.browser_overlay_label.hide()

        self.updateTextWidgetA()

        try:     self.toggle_skip.setChecked(cfg.data.skipped())
        except:  logger.warning('Skip Toggle Widget Failed to Update')
        try:     self.toolbar_jump_input.setText(str(cfg.data.layer()))
        except:  logger.warning('Current Layer Widget Failed to Update')
        try:     self.whitening_input.setText(str(cfg.data.whitening()))
        except:  logger.warning('Whitening Input Widget Failed to Update')
        try:     self.swim_input.setText(str(cfg.data.swim_window()))
        except:  logger.warning('Swim Input Widget Failed to Update')
        try:     self.toggle_bounding_rect.setChecked(cfg.data.has_bb())
        except:  logger.warning('Bounding Rect Widget Failed to Update')
        try:     self.bias_bool_combo.setCurrentText(str(cfg.data.poly_order())) if cfg.data.null_cafm() else 'None'
        except:  logger.warning('Polynomial Order Combobox Widget Failed to Update')



    def updateTextWidgetA(self, s=None, l=None):
        if s == None: s = cfg.data.scale()
        if l == None: l = cfg.data.layer()
        name = "<b style='color: #010048;font-size:14px;'>%s</b><br>" % cfg.data.name_base(s=s, l=l)
        skip = "<b style='color:red;'> SKIP</b><br>" if cfg.data.skipped(s=s, l=l) else ''
        completed = "<b style='color: #212121;font-size:11px;'>Scales Aligned: (%d/%d)</b><br>" % \
                    (cfg.data.nScalesAligned, cfg.data.nscales)
        if is_cur_scale_aligned():
            if cfg.data.has_bb(s=s):
                bb = cfg.data.bounding_rect(s=s)
                dims = [bb[2], bb[3]]
            else:
                dims = cfg.data.image_size(s=s)
            bb_dims = "<b style='color: #212121;font-size:11px;'>Bounds: %dx%dpx</b><br>" % (dims[0], dims[1])
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


    def updateAffineWidget(self, s=None, l=None):
        if s == None: s = cfg.data.scale()
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
        if s == None: s = cfg.data.scale()
        self.history_label = QLabel('<b>Saved Alignments (Scale %d)</b>' % get_scale_val(s))
        self.historyListWidget.clear()
        dir = os.path.join(cfg.data.dest(), s, 'history')
        try:
            self.historyListWidget.addItems(os.listdir(dir))
        except:
            logger.warning(f"History Directory '{dir}' Not Found")


    def view_historical_alignment(self):
        logger.info('Loading History File...')
        name = self.historyListWidget.currentItem().text()
        if name is None: return
        path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'history', name)
        logger.info('Viewing archival alignment %s...' % path)
        with open(path, 'r') as f:
            project = json.load(f)
        logger.info('Creating Project View...')
        self.projecthistory_model.load(project)
        logger.info('Changing Stack Panel Index...')
        self.image_panel_stack_widget.setCurrentIndex(3)


    def rename_historical_alignment(self):
        new_name, ok = QInputDialog.getText(self, 'Rename', 'New Name:')
        if not ok: return
        old_name = self.historyListWidget.currentItem().text()
        dir = os.path.join(cfg.data.dest(), cfg.data.scale(), 'history')
        old_path = os.path.join(dir, old_name)
        new_path = os.path.join(dir, new_name)
        try:
            os.rename(old_path, new_path)
        except:
            logger.warning('There was a problem renaming the file')
        self.updateHistoryListWidget()


    def swap_historical_alignment(self):
        name = self.historyListWidget.currentItem().text()
        if name is None: return
        scale_val = cfg.data.scale_val()
        msg = "Are you sure you want to swap your alignment data for Scale %d with '%s'?\n" \
              "Note: You must realign after swapping it in." % (scale_val, name)
        reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            logger.info("Returning without changing anything.")
            return
        self.hud.post('Loading %s')
        path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'history', name)
        with open(path, 'r') as f:
            scale = json.load(f)
        self.hud.post('Swapping Current Scale %d Dictionary with %s' % (scale_val, name))
        cfg.data.set_al_dict(aldict=scale)
        # self.regenerate() #Todo test this under a range of possible scenarios


    def remove_historical_alignment(self):
        logger.info('Loading History File...')
        name = self.historyListWidget.currentItem().text()
        if name is None: return
        path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'history', name)
        logger.info('Removing archival alignment %s...' % path)
        try:
            os.remove(path)
        except:
            logger.warning('There was an exception while removing the old file')
        finally:
            self.updateHistoryListWidget()


    def historyItemClicked(self, qmodelindex):
        item = self.historyListWidget.currentItem()
        logger.info(f"Selected {item.text()}")
        path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'history', item.text())
        with open(path, 'r') as f:
            scale = json.load(f)
        snr_avg = get_snr_average(scale)
        self.hud.post(f'SNR avg: %.4f' % snr_avg)


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
        # return cfg.ng_workers[cfg.data.scale()].request_layer()
        return cfg.ng_worker.request_layer()


    def updateJumpValidator(self):
        self.jump_validator = QIntValidator(0, cfg.data.n_layers())
        self.toolbar_jump_input.setValidator(self.jump_validator)

    def printActiveThreads(self):
        threads = '\n'.join([thread.name for thread in threading.enumerate()])

        logger.info(f'# Active Threads : {threading.active_count()}')
        logger.info(f'Current Thread   : {threading.current_thread()}')
        logger.info(f'All Threads      : \n{threads}')

        self.hud.post(f'# Active Threads : {threading.active_count()}')
        self.hud.post(f'Current Thread   : {threading.current_thread()}')
        self.hud.post(f'All Threads      : \n{threads}')



    @Slot()
    def jump_to(self, requested) -> None:
        if cfg.data:
            if requested not in range(cfg.data.n_layers()):
                logger.warning('Requested layer is not a valid layer')
                return
            # logger.info('Jumping To Layer %d' % requested)
            # state = copy.deepcopy(cfg.ng_workers[cfg.data.scale()].viewer.state)
            state = copy.deepcopy(cfg.viewer.state)
            state.position[0] = requested
            # cfg.ng_workers[cfg.data.scale()].viewer.set_state(state)
            cfg.viewer.set_state(state)
            self.dataUpdateWidgets()
            self.refreshNeuroglancerURL()


    @Slot()
    def jump_to_layer(self) -> None:
        if cfg.data:
            requested = int(self.toolbar_jump_input.text())
            if requested not in range(cfg.data.n_layers()):
                logger.warning('Requested layer is not a valid layer')
                return
            logger.info('Jumping To Layer %d' % requested)
            # state = copy.deepcopy(cfg.ng_workers[cfg.data.scale()].viewer.state)
            state = copy.deepcopy(cfg.viewer.state)
            state.position[0] = requested
            # cfg.ng_workers[cfg.data.scale()].viewer.set_state(state)
            cfg.viewer.set_state(state)
            self.dataUpdateWidgets()
            self.refreshNeuroglancerURL()


    def jump_to_worst_snr(self) -> None:
        if not are_images_imported():
            self.hud.post("Images Must Be Imported First", logging.WARNING)
            return
        if not are_aligned_images_generated():
            self.hud.post("You Must Align This Scale First!")
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
            self.hud.post("Jumping to Layer %d (Badness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            # cfg.data.set_layer(next_layer)
            self.jump_to(requested=next_layer)
            self.dataUpdateWidgets()
            self._jump_to_worst_ticker += 1
        except:
            self._jump_to_worst_ticker = 1
            print_exception()


    def jump_to_best_snr(self) -> None:
        if not are_images_imported():
            self.hud.post("Images Must Be Imported First", logging.WARNING)
            return
        if not are_aligned_images_generated():
            self.hud.post("You Must Align This Scale First!")
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
            self.hud.post("Jumping to l %d (Goodness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
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
        self.toolbar_scale_combobox.clear()
        self.toolbar_scale_combobox.addItems(cfg.data.scales())
        index = self.toolbar_scale_combobox.findText(cfg.data.scale(), Qt.MatchFixedString)
        if index >= 0:
            self.toolbar_scale_combobox.setCurrentIndex(index)
        self._scales_combobox_switch = 1

    def fn_scales_combobox(self) -> None:

        if self._is_mp_mode == True:
            return
        caller = inspect.stack()[1].function
        # logger.info('caller: %s' % caller)
        if self._scales_combobox_switch == 0:
            if inspect.stack()[1].function != 'reload_scales_combobox':
                logger.info('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return
        if caller == 'onStartProject':
            # logger.warning('Canceling s change...')
            return
        # self.shutdownNeuroglancer()
        # cfg.ng_workers[cfg.data.scale()] = {} #2203 adding this to scale_up/down
        new_scale = self.toolbar_scale_combobox.currentText()
        # logger.info(f'Setting Scale: %s...' % new_scale)
        cfg.data.set_scale(new_scale)
        self.onScaleChange()


    def fn_ng_layout_combobox(self) -> None:
        caller = inspect.stack()[1].function
        if caller == 'onStartProject':
            return
        # logger.info("Setting Neuroglancer Layout [%s]... " % inspect.stack()[1].function)
        if not cfg.data:
            logger.info('Cant change layout, no data is loaded')
            return
        s = cfg.data.scale()
        try:
            if self.toolbar_layout_combobox.currentText() == 'xy':
                cfg.ng_worker.nglayout = 'yz'
                cfg.ng_worker.initViewer()
                self.ngLayout1Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'yz':
                cfg.ng_worker.nglayout = 'xy'
                cfg.ng_worker.initViewer()
                self.ngLayout2Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'xz':
                cfg.ng_worker.nglayout = 'xz'
                cfg.ng_worker.initViewer()
                self.ngLayout3Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'xy-3d':
                cfg.ng_worker.nglayout = 'yz-3d'
                cfg.ng_worker.initViewer()
                self.ngLayout4Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'yz-3d':
                cfg.ng_worker.nglayout = 'xy-3d'
                cfg.ng_worker.initViewer()
                self.ngLayout5Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'xz-3d':
                cfg.ng_worker.nglayout = 'xz-3d'
                cfg.ng_worker.initViewer()
                self.ngLayout6Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == '3d':
                cfg.ng_worker.nglayout = '3d'
                cfg.ng_worker.initViewer()
                self.ngLayout7Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == '4panel':
                cfg.ng_worker.nglayout = '4panel'
                cfg.ng_worker.initViewer()
                self.ngLayout8Action.setChecked(True)
            self.refreshNeuroglancerURL()
        except:
            logger.warning('Cannot Change Neuroglancer Layout At This Time')


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
        self.hud.post('Exported: %s' % file)
        self.hud.post('AFMs exported successfully.')


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

        self.hud.post('Exported: %s' % file)
        self.hud.post('Cumulative AFMs exported successfully.')


    def show_warning(self, title, text):
        QMessageBox.warning(None, title, text)


    def new_project(self, mendenhall=False):
        logger.critical('New Project...')
        if cfg.data:
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
                self.hud.post('New Project Canceled', logging.WARNING)
                return
            if reply == QMessageBox.Cancel:
                logger.info("Response was 'Cancel'")
                self.hud.post('New Project Canceled', logging.WARNING)
                return

        cfg.data = None #+
        self.initView()
        self.hud.clear_display()
        self.clearUIDetails()
        # self.image_panel_stack_widget.setCurrentIndex(2)
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.shutdownNeuroglancer()
        self.snr_plot.wipePlot()
        self.hud.post('Creating A New Project...')
        self.hud.post('Set New Project Path:')
        filename = new_project_dialog()
        logger.info('User Chosen Filename: %s' % filename)
        if filename in ['', None]:
            self.hud.post("New Project Canceled")
            self.set_idle()
            return
        if not filename.endswith('.proj'):
            filename += ".proj"
        if os.path.exists(filename):
            logger.warning("The file '%s' already exists." % filename)
            path_proj = os.path.splitext(filename)[0]
            self.hud.post(f"Removing Extant Project Directory '{path_proj}'...")
            logger.info(f"Removing Extant Project Directory '{path_proj}'...")
            shutil.rmtree(path_proj, ignore_errors=True)
            self.hud.post(f"Removing Extant Project File '{path_proj}'...")
            logger.info(f"Removing Extant Project File '{path_proj}'...")
            os.remove(filename)

        if cfg.data:
            logger.info("Overwriting Project Data In Memory With New Template")

        path, extension = os.path.splitext(filename)
        cfg.data = DataModel(name=path, mendenhall=mendenhall)
        makedirs_exist_ok(cfg.data.dest(), exist_ok=True)

        if not mendenhall:
            try:
                self.import_images()
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
            create_project_structure_directories('scale_1')

        try:
            self.onStartProject()
        except:
            print_exception()
        finally:
            self.save_project_to_file()  # Save for New Project, Not for Open Project


    def open_project(self):
        #Todo check for Zarr files. Generate/Re-generate if necessary
        logger.critical('Opening Project...')
        filename = open_project_dialog()
        logger.info(f'Project File: {filename}')
        if filename == '':
            self.hud.post("No Project File Selected (.proj), dialog returned empty string...", logging.WARNING)
            return
        if filename == None:
            self.hud.post('No Project File Selected (.proj)', logging.WARNING)
            return
        if os.path.isdir(filename):
            self.hud.post("Selected Path Is A Directory.", logging.WARNING)
            return
        # self.image_panel_stack_widget.setCurrentIndex(2)
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.shutdownNeuroglancer()
        self.clearUIDetails()
        try:
            with open(filename, 'r') as f:
                project = DataModel(json.load(f))
        except:
            self.hud.post('No Project Opened', logging.WARNING)
            return

        cfg.data = copy.deepcopy(project)
        cfg.data.set_paths_absolute(filename=filename)
        self.onStartProject()

    #@timer
    def onStartProject(self, launch_servers=True):
        '''Functions that only need to be run once per project
        Do not automatically save, there is nothing to save yet'''
        self.layer_details_widget.show()
        self.afm_widget.show()
        self.history_widget.show()

        if cfg.data.is_mendenhall():
            self.setWindowTitle("Project: %s (Mendenhall Protocol0" % os.path.basename(cfg.data.dest()))
        cfg.data.scalesAligned = get_aligned_scales()
        cfg.data.nScalesAligned = len(cfg.data.scalesAligned)
        cfg.data.nscales = len(cfg.data.scales())
        cfg.data.nlayers = cfg.data.n_layers()
        self._scales_combobox_switch = 0
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.dataUpdateWidgets()
        self.setWindowTitle("Project: %s" % os.path.basename(cfg.data.dest()))
        self.updateStatusTips()
        self.reload_scales_combobox()
        self.updateEnabledButtons()
        self.enableGlobalButtons()
        self.updateJumpValidator()
        self.updateHistoryListWidget()
        self.project_model.load(cfg.data.to_dict())
        self.updateBanner()
        self.snr_plot.wipePlot()
        if cfg.data:
            if is_cur_scale_aligned():
                self.snr_plot.initSnrPlot()
        # cfg.ng_workers = dict.fromkeys(cfg.data.scales()) #1207-
        # self.initNgServer(scales=cfg.data.scales())
        self._scales_combobox_switch = 1
        # self.toolbar_scale_combobox.setCurrentIndex(self.toolbar_scale_combobox.count() - 1)
        self.toolbar_scale_combobox.setCurrentText(cfg.data.scale())
        ng_layouts = ['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d']
        self.toolbar_layout_combobox.clear()
        self.toolbar_layout_combobox.addItems(ng_layouts)
        self.align_all_button.setText('Align All\n%s' % cfg.data.scale_pretty())
        self.tabs_main.setCurrentIndex(0)
        if launch_servers:
            if cfg.SIMULTANEOUS_SERVERS:
                self.initNgViewer(scales=cfg.data.scales())
            else:
                self.initNgServer(scales=[cfg.data.scale()])
        self.update_ng_hyperlink()
        QApplication.processEvents()



    def rescale(self):
        if not cfg.data:
            self.hud.post('No data yet!', logging.WARNING)
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

        self.initView()
        self.shutdownNeuroglancer()
        self.snr_plot.wipePlot()
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

        cfg.main_window.hud.post("Removing Zarr Scale Directories...")
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
            self.save_project_to_file()
            self.hud.post('Rescaling Successful')
        finally:
            self.onStartProject()
            self.set_idle()


    def save_project(self):
        if not cfg.data:
            self.hud.post('Nothing To Save')
            return
        self.set_status('Saving...')
        self.hud.post('Saving Project...')
        try:
            self.save_project_to_file()
            self._unsaved_changes = False
        except:
            self.hud.post('Unable To Save', logging.WARNING)
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
            self.save_project_to_file()


    def save_project_to_file(self, saveas=None):
        if saveas is not None:
            cfg.data.set_destination(saveas)
        data_cp = copy.deepcopy(cfg.data)
        if data_cp.layer() >= data_cp.n_layers():
            real_layer = data_cp.n_layers() - 1
            logger.info(f'Adjusting Save Layer Down to Real Stack Layer ({real_layer}) ')
            data_cp.set_layer(real_layer)
        data_cp.make_paths_relative(start=cfg.data.dest())
        data_cp_json = data_cp.to_dict()
        logger.info('---- SAVING DATA TO PROJECT FILE ----')
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        proj_json = jde.encode(data_cp_json)
        name = cfg.data.dest()
        logger.info('Save Name: %s' % name)
        if not name.endswith('.proj'): name += ".proj"
        with open(name, 'w') as f: f.write(proj_json)
        del data_cp
        self._unsaved_changes = False


    def has_unsaved_changes(self):
        logger.debug("Called by " + inspect.stack()[1].function)
        if inspect.stack()[1].function == 'initUI':
            return
        if inspect.stack()[1].function == 'dataUpdateWidgets':
            return
        self._unsaved_changes = True


    def ng_toggle_show_ui_controls(self):
        if self.ngShowUiControlsAction.isChecked():
            cfg.SHOW_UI_CONTROLS = True
            self.ngShowUiControlsAction.setText('Show UI Controls')
        else:
            cfg.SHOW_UI_CONTROLS = False
            self.ngShowUiControlsAction.setText('Hide UI Controls')
        self.initNgViewer(scales=cfg.data.scales())


    def import_images(self, clear_role=False):
        ''' Import images into data '''
        logger.critical('Importing Images...')
        self.hud.post('Select Images To Import:')
        role = 'base'
        try:
            filenames = natural_sort(import_images_dialog())
        except:
            logger.warning('No Images Selected')
            return
        cfg.data.set_source_path(os.path.dirname(filenames[0])) #Critical!
        if clear_role:
            for layer in cfg.data.alstack():
                if role in layer['images'].keys():  layer['images'].pop(role)

        self.hud.post('Importing Selected Images...')
        logger.debug("Selected Files: " + str(filenames))
        nlayers = 0
        for i, f in enumerate(filenames):
            nlayers += 1
            logger.debug("Role " + str(role) + ", Importing file: " + str(f))
            if f is None:
                cfg.data.append_empty(role)
            else:
                cfg.data.append_image(f, role)

        if are_images_imported():
            self.hud.post('%d Images Imported Successfully' % len(filenames))
            cfg.data.nlayers = nlayers
            img_size = cfg.data.image_size(s='scale_1')
            cfg.data.link_all_stacks()
            self.hud.post(f'Full Scale Image Dimensions: {img_size[0]}x{img_size[1]} pixels')
            '''Todo save the image dimensions in project dictionary for quick lookup later'''
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)
        self.save_project_to_file()
        logger.info('<<<< Import Images <<<<')


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
            self.hud.post('Confirm Exit AlignEM-SWiFT')
            message = "There are unsaved changes.\n\nSave before exiting?"
            msg = QMessageBox(QMessageBox.Warning, "Save Changes", message, parent=self)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            msg.setIcon(QMessageBox.Question)
            reply = msg.exec_()
            if reply == QMessageBox.Cancel:
                logger.info('reply=Cancel. Returning control to the app.')
                self.hud.post('Canceling exit application')
                return
            if reply == QMessageBox.Save:
                logger.info('reply=Save')
                self.save_project()
                self.set_status('Wrapping up...')
                logger.info('Project saved. Exiting')
            if reply == QMessageBox.Discard:
                logger.info('reply=Discard Exiting without saving')
        else:
            logger.info('No Unsaved Changes - Exiting')

        self.shutdownInstructions()


    def shutdownInstructions(self):
        logger.info('Running Shutdown Instructions:')
        # try:
        #     if neuroglancer.server.is_server_running():
        #         logger.info('Stopping Neuroglancer SimpleHTTPServer...')
        #         neuroglancer.server.stop()
        # except:
        #     sys.stdout.flush()
        #     logger.warning('Having trouble shutting down neuroglancer')
        # else:
        #     logger.info('Success')

        if cfg.USE_EXTRA_THREADING:
            try:
                logger.info('Shutting down threadpool...')
                threadpool_result = self.threadpool.waitForDone(msecs=500)
            except:
                logger.warning('Having trouble shutting down threadpool')
            else:
                logger.info('Success')

        if not is_tacc():
            if cfg.PROFILER == True:
                from scalene import scalene_profiler
                scalene_profiler.stop()

        logger.info('Quitting app...')
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
        self.hud.post("Viewing AlignEM_SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def documentation_view_home(self):
        self.hud.post("Viewing AlignEM-SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self.main_stack_widget.setCurrentIndex(1)


    def remote_view(self):
        self.hud.post("Loading A Neuroglancer Instance Running On A Remote Server...")
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.main_stack_widget.setCurrentIndex(3)


    def set_url(self, text: str) -> None:
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
            logger.info('Stopping Neuroglancer...')
            ng.server.stop()


    def invalidate_all(self, s=None):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        if s == None: s = cfg.data.scale()
        if cfg.data.is_mendenhall():
            # cfg.ng_workers['scale_1'].menLV.invalidate()
            cfg.ng_worker.menLV.invalidate()
            return

        refLV = get_refLV()
        baseLV = get_baseLV()
        refLV.invalidate()
        baseLV.invalidate()
        if is_arg_scale_aligned(s):
            alLV = get_alLV()
            alLV.invalidate()


    def refreshNeuroglancerURL(self, s=None):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        if s == None: s = cfg.data.scale()
        if not cfg.HEADLESS:
            self.ng_browser.setUrl(QUrl(cfg.ng_worker.url()))
            self.ng_browser.setFocus()

    def stopNgServer(self):
        if ng.is_server_running():
            self.hud.post('Stopping Neuroglancer...')
            try:
                ng.stop()
            except:
                print_exception()
            else:
                self.hud.done()
        else:
            self.hud.post('Neuroglancer Is Not Running')


    #@timer
    def initNgServer(self, scales=None):
        logger.info(f'caller: {inspect.stack()[1].function}')
        if not cfg.data:
            logger.warning('Nothing To View')
            return

        if not scales:
            # scales = [cfg.data.s()]
            if cfg.SIMULTANEOUS_SERVERS:
                scales = cfg.data.scales()
            else:
                scales = [cfg.data.scale()]

        # asyncio.set_event_loop(asyncio.new_event_loop())

        logger.critical('Initializing Neuroglancer Server(s), %s...' % ', '.join(scales))
        # self.hud.post('Starting Neuroglancer Worker(s)...')
        # self.set_status('Starting Neuroglancer...')
        # cfg.ng_workers = {}

        self.shutdownNeuroglancer() ###########---------
        try:
            for s in scales:
                self.hud.post(f'Initializing Neuroglancer Server, {cfg.data.scale_pretty(s=s)}...')
                try:
                    mp_mode = cfg.ng_worker.mp_mode
                except:
                    mp_mode = False

                # try: ##############------------
                #     logger.info('Deleting Viewer for %s...' % s)
                #     cfg.ng_worker = None
                #
                # except:
                #     print_exception()

                # time.sleep(.5)
                logger.debug('Launching NG Server for %s...' % s)

                # is_aligned = is_arg_scale_aligned(s)

                # logger.info('%s is aligned? %s' % (s, is_aligned))
                # if is_aligned:
                #     self.ng_browser_2.show()
                #     QApplication.processEvents()
                #     cfg.ng_worker = {}
                #     left_w = self.ng_splitter.sizes()[0]
                #     left_h = self.ng_browser.size().height() / 2
                #
                #     right_w = self.ng_splitter.sizes()[1]
                #     right_h = self.ng_browser_2.size().height()
                #
                #     logger.info(f'left_w={left_w}')
                #     logger.info(f'left_h={left_h}')
                #     logger.info(f'right_w={right_w}')
                #     logger.info(f'right_h={right_h}')
                #
                #     cfg.ng_worker['originals'] = NgHost(src=cfg.data.dest(), s=s)
                #     self.threadpool.start(cfg.ng_worker['originals'])
                #     cfg.ng_worker['originals'].initViewer(layout='column', views=['ref','base'], show_ui_controls=False, show_panel_borders=False, w=left_w, h=left_h)
                #
                #     cfg.ng_worker['aligned'] = NgHost(src=cfg.data.dest(), s=s)
                #     self.threadpool.start(cfg.ng_worker['aligned'])
                #     cfg.ng_worker['aligned'].initViewer(layout='column', views=['aligned'], show_ui_controls=True, show_panel_borders=True, w=right_w, h=right_h)
                #
                #     cfg.ng_worker['originals'].signals.stateChanged.connect(lambda l: self.dataUpdateWidgets(ng_layer=l))
                #     cfg.ng_worker['aligned'].signals.stateChanged.connect(lambda l: self.dataUpdateWidgets(ng_layer=l))
                #     cfg.ng_worker['originals'].signals.stateChanged.connect(lambda l: self.update_viewer_aligned(ng_layer=l))
                #     cfg.ng_worker['aligned'].signals.stateChanged.connect(lambda l: self.update_viewer_originals(ng_layer=l))
                #
                #     self.ng_browser_2.setFocus()
                # else:
                #     # self.ng_browser_2.hide()
                #     # QApplication.processEvents()

                # self.threadpool.releaseThread()

                widget_size = self.image_panel_stack_widget.geometry().getRect()

                # self.threadpool.waitForDone(500)
                cfg.ng_worker = NgHost(parent=self, src=cfg.data.dest(), scale=s)
                # self.threadpool.start(cfg.ng_worker)
                cfg.ng_worker.initViewer(widget_size=widget_size, matchpoint=mp_mode)
                cfg.ng_worker.signals.stateChanged.connect(lambda l: self.dataUpdateWidgets(ng_layer=l))

                self.refreshNeuroglancerURL(s=s)  # Important
            # self.refreshNeuroglancerURL() #Important
            self.toolbar_layout_combobox.setCurrentText('xy')
            self.toolbar_layout_combobox.currentTextChanged.connect(self.fn_ng_layout_combobox)
        except:
            print_exception()

        else:
            self.image_panel_stack_widget.setCurrentIndex(1)
            self.hud.done()
            for s in scales:
                self.display_actual_viewer_url(s=s)


    def initShortcuts(self):
        logger.info('')
        events = (
            (QKeySequence.MoveToPreviousChar, self.scale_down),
            (QKeySequence.MoveToNextChar, self.scale_up)
        )
        for event, action in events:
            QShortcut(event, self, action)


    def initNgViewer(self, scales=None, matchpoint=None):
        caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}')
        if cfg.data:
            # if ng.is_server_running():
            if scales == None: scales = [cfg.data.scale()]
            for s in scales:
                if matchpoint != None:
                    cfg.ng_worker.initViewer(matchpoint=matchpoint)
                else:
                    cfg.ng_worker.initViewer()
                self.refreshNeuroglancerURL(s=s)
                if caller != 'resizeEvent':
                    self.display_actual_viewer_url(s=s)
            # else:
            #     logger.warning('Neuroglancer is not running')
        else:
            logger.warning('Cannot initialize viewer. Data model is not initialized')


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
        self.hud.post('Googling...')
        self.browser_docs.setUrl(QUrl('https://www.google.com'))
        self.main_stack_widget.setCurrentIndex(1)

    def gpu_config(self):
        self.browser_docs.setUrl(QUrl('chrome://gpu'))
        self.main_stack_widget.setCurrentIndex(1)

    def chromium_debug(self):
        self.browser_docs.setUrl(QUrl('http://127.0.0.1:9000'))
        self.main_stack_widget.setCurrentIndex(1)

    def display_actual_viewer_url(self, s=None):
        if cfg.data:
            if s == None: s = cfg.data.scale()
            if ng.is_server_running():
                try:
                    url = cfg.viewer.url
                    # self.hud.post(f"\n\nScale {cfg.data.scale_pretty(s=s)} URL:\n<a href='{url}'>{url}</a>\n")
                    self.hud.textedit.appendHtml(f"<span style='color: #F3F6FB'>URL:</span>\n<a href='{url}'>{url}</a>\n")
                    logger.info(f"{cfg.data.scale_pretty(s=s)}\nURL:  {url}\n")
                except:
                    logger.warning('No URL to show')
            else:
                self.hud.post('Neuroglancer is not running.')

    def print_ng_state_url(self):
        if cfg.data:
            if ng.is_server_running():
                # try:     cfg.ng_workers[cfg.data.scale()].show_state()
                try:     cfg.ng_worker.show_state()
                except:  print_exception()
            else:
                self.hud.post('Neuroglancer is not running.')


    def print_ng_state(self):
        if cfg.data:
            if ng.is_server_running():
                # try:     self.hud.post('\nViewer State:\n%s' % str(cfg.ng_workers[cfg.data.scale()].viewer.state))
                try:     self.hud.post('\nViewer State:\n%s' % str(cfg.viewer.state))
                except:  print_exception()
            else:
                self.hud.post('Neuroglancer is not running')


    def print_ng_raw_state(self):
        if cfg.data:
            if ng.is_server_running():
                try:
                    # self.hud.post('\nRaw State:\n%s' % str(cfg.ng_workers[cfg.data.scale()].config_state.raw_state))
                    self.hud.post('\nRaw State:\n%s' % str(cfg.viewer.config_state.raw_state))
                except:
                    print_exception()
            else:
                self.hud.post('Neuroglancer is not running')


    def browser_reload(self):
        try:
            self.ng_browser.reload()
        except:
            print_exception()


    def dump_ng_details(self):
        if cfg.data:
            if not ng.is_server_running():
                logger.warning('Neuroglancer is not running')
                return
            # v = cfg.ng_workers[cfg.data.s()].viewer
            v = cfg.viewer
            self.hud.post("v.position: %s\n" % str(v.state.position))
            self.hud.post("v.config_state: %s\n" % str(v.config_state))


    def blend_ng(self):
        logger.info("blend_ng():")


    def show_splash(self):
        logger.info('Showing Splash...')
        self.temp_img_panel_index = self.image_panel_stack_widget.currentIndex()
        self.splashlabel.show()
        self.image_panel_stack_widget.setCurrentIndex(0)
        self.main_stack_widget.setCurrentIndex(0)
        self.splashmovie.start()


    def runaftersplash(self):
        # self.main_stack_widget.setCurrentIndex(0)
        # self.image_panel_stack_widget.setCurrentIndex(1)
        self.image_panel_stack_widget.setCurrentIndex(self.temp_img_panel_index)
        self.splashlabel.hide()


    def configure_project(self):
        if cfg.data:
            dialog = ConfigProjectDialog(parent=self)
            result = dialog.exec_()
            logger.info(f'ConfigProjectDialog exit code ({result})')
        else:
            self.hud.post('No Project Yet!')

    def configure_application(self):
        dialog = ConfigAppDialog(parent=self)
        result = dialog.exec_()
        logger.info(f'ConfigAppDialog exit code ({result})')


    def view_k_img(self):
        if cfg.data:
            self.w = KImageWindow(parent=self)
            self.w.show()


    def bounding_rect_changed_callback(self, state):
        if cfg.data:
            if inspect.stack()[1].function == 'dataUpdateWidgets': return
            if state:
                self.hud.post('Bounding Box is ON. Warning: Image dimensions may grow large.')
                cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
            else:
                self.hud.post('Bounding Box is OFF. Image dimensions will not change.')
                cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def skip_changed_callback(self, state:int):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        caller = inspect.stack()[1].function
        logger.info(caller)
        if cfg.data:
            # caller is 'main' when user is toggler
            if inspect.stack()[1].function == 'dataUpdateWidgets': return
            skip_state = self.toggle_skip.isChecked()
            for s in cfg.data.scales():
                # layer = self.request_ng_layer()
                layer = cfg.data.layer()
                if layer >= cfg.data.n_layers():
                    logger.warning(f'Request layer is out of range ({layer}) - Returning')
                    return
                cfg.data.set_skip(skip_state, s=s, l=layer)  # for checkbox
            if skip_state:
                self.hud.post("Flagged For Skip: %s" % cfg.data.name_base())
            cfg.data.link_all_stacks()
            self.dataUpdateWidgets()
            if self.tabs_main.currentIndex() == 1:
                self.layer_view_widget.set_data()
            logger.info(f'new skip state: {skip_state}')


    def skip_change_shortcut(self):
        if cfg.data:
            if self.toggle_skip.isChecked():
                self.toggle_skip.setChecked(False)
            else:
                self.toggle_skip.setChecked(True)


    def enterExitMatchPointMode(self):
        if cfg.data:
            if self._is_mp_mode == False:
                logger.info('\nEntering Match Point Mode...')
                self.hud.post('Entering Match Point Mode...')
                self._is_mp_mode = True
                self.toolbar_scale_combobox.setEnabled(False)
                self.extra_header_text_label.setText('Match Point Mode')
                self.new_control_panel.hide()
                self.matchpoint_controls.show()
                self.update_match_point_snr()
                self.mp_marker_size_spinbox.setValue(cfg.data['user_settings']['mp_marker_size'])
                self.mp_marker_lineweight_spinbox.setValue(cfg.data['user_settings']['mp_marker_lineweight'])
                # self.initNgServer(scales=cfg.data.scales())
                self.initNgViewer(matchpoint=True)
            else:
                logger.info('\nExiting Match Point Mode...')
                self.hud.post('Exiting Match Point Mode...')
                self._is_mp_mode = False
                self.toolbar_scale_combobox.setEnabled(True)
                self.extra_header_text_label.setText('')
                # self.updateSkipMatchWidget()
                self.initView()
                self.initNgViewer(matchpoint=False)
                # self.initNgServer()


    def update_match_point_snr(self):
        if cfg.data:
            snr_report = cfg.data.snr_report()
            snr_report.replace('<', '&lt;')
            snr_report.replace('>', '&gt;')
            self.matchpoint_text_snr.setHtml(f'<h4>{snr_report}</h4>')


    def clear_match_points(self):
        if cfg.data:
            logger.info('Clearing Match Points...')
            cfg.data.clear_match_points()
            self.dataUpdateWidgets()


    def print_all_matchpoints(self):
        if cfg.data:
            cfg.data.print_all_matchpoints()


    def show_all_matchpoints(self):
        if cfg.data:
            no_mps = True
            for i, l in enumerate(cfg.data.alstack()):
                r = l['images']['ref']['metadata']['match_points']
                b = l['images']['base']['metadata']['match_points']
                if r != []:
                    no_mps = False
                    self.hud.post(f'Layer: {i}, Ref, Match Points: {str(r)}')
                if b != []:
                    no_mps = False
                    self.hud.post(f'Layer: {i}, Base, Match Points: {str(b)}')
            if no_mps:
                self.hud.post('This project has no match points.')
            self.dataUpdateWidgets()


    def show_run_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.hud.post('\n\nWorking Directory     : %s\n'
                      'Running In (__file__) : %s' % (os.getcwd(), os.path.dirname(os.path.realpath(__file__))))


    def show_module_search_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.hud.post('\n\n' + '\n'.join(sys.path))


    def show_snr_list(self) -> None:
        if cfg.data:
            s = cfg.data.scale_val()
            lst = ' | '.join(map(str, cfg.data.snr_list()))
            self.hud.post('\n\nSNR List for Scale %d:\n%s\n' % (s, lst.split(' | ')))


    def show_zarr_info(self) -> None:
        if cfg.data:
            z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
            self.hud.post('\n' + str(z.tree()) + '\n' + str(z.info))


    def show_zarr_info_aligned(self) -> None:
        if cfg.data:
            z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
            self.hud.post('\n' + str(z.info) + '\n' + str(z.tree()))


    def show_zarr_info_source(self) -> None:
        if cfg.data:
            z = zarr.open(os.path.join(cfg.data.dest(), 'img_src.zarr'))
            self.hud.post('\n' + str(z.info) + '\n' + str(z.tree()))


    def show_memory_statistics(self):
        pass




    def set_mp_marker_lineweight(self):
        cfg.data['user_settings']['mp_marker_lineweight'] = self.mp_marker_lineweight_spinbox.value()
        if inspect.stack()[1].function != 'enterExitMatchPointMode':
            self.initNgViewer(cfg.data.scales())


    def set_mp_marker_size(self):
        cfg.data['user_settings']['mp_marker_size'] = self.mp_marker_size_spinbox.value()
        if inspect.stack()[1].function != 'enterExitMatchPointMode':
            self.initNgViewer(cfg.data.scales())


    def set_opacity(self, obj, val):
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(val)  # 0 to 1 -> fade effect
        obj.setGraphicsEffect(op)
        obj.setAutoFillBackground(True)


    def set_shader_none(self):
        cfg.SHADER = None
        self.initNgViewer(cfg.data.scales())


    def set_shader_colormapJet(self):
        cfg.SHADER = src.shaders.colormapJet
        self.initNgViewer(cfg.data.scales())


    def set_shader_test1(self):
        cfg.SHADER = src.shaders.shader_test1
        self.initNgViewer(cfg.data.scales())


    def set_shader_test2(self):
        cfg.SHADER = src.shaders.shader_test2
        self.initNgViewer(cfg.data.scales())


    def initToolbar(self):
        logger.info('')
        self.toolbar = QToolBar()
        # self.toolbar.setFixedHeight(50)
        self.toolbar.setObjectName('toolbar')
        self.addToolBar(self.toolbar)

        self.action_new_project = QAction('New Project', self)
        self.action_new_project.setStatusTip('New Project')
        self.action_new_project.triggered.connect(self.new_project)
        self.action_new_project.setIcon(qta.icon('fa.plus', color='#1B1E23'))
        self.toolbar.addAction(self.action_new_project)

        self.action_open_project = QAction('Open Project', self)
        self.action_open_project.setStatusTip('Open Project')
        self.action_open_project.triggered.connect(self.open_project)
        self.action_open_project.setIcon(qta.icon('fa.folder-open', color='#1B1E23'))
        self.toolbar.addAction(self.action_open_project)

        self.action_save_project = QAction('Save Project', self)
        self.action_save_project.setStatusTip('Save Project')
        self.action_save_project.triggered.connect(self.save_project)
        self.action_save_project.setIcon(qta.icon('mdi.content-save', color='#1B1E23'))
        self.toolbar.addAction(self.action_save_project)

        self.layoutOneAction = QAction('Column Layout', self)
        self.layoutOneAction.setStatusTip('Column Layout')
        self.layoutOneAction.triggered.connect(self.set_viewer_layout_1)
        self.layoutOneAction.setIcon(qta.icon('mdi.view-column-outline', color='#1B1E23'))
        self.toolbar.addAction(self.layoutOneAction)

        self.layoutTwoAction = QAction('Row Layout', self)
        self.layoutTwoAction.setStatusTip('Row Layout')
        self.layoutTwoAction.triggered.connect(self.set_viewer_layout_2)
        self.layoutTwoAction.setIcon(qta.icon('mdi.view-stream-outline', color='#1B1E23'))
        self.toolbar.addAction(self.layoutTwoAction)

        '''Top Details/Labels Banner'''
        font = QFont()
        font.setBold(True)
        self.align_label_resolution = QLabel('')
        self.align_label_resolution.setObjectName('align_label_resolution')
        self.alignment_status_label = QLabel('')
        self.align_label_resolution.setFont(font)
        self.alignment_status_label.setFont(font)
        self.extra_header_text_label = QLabel('')
        self.extra_header_text_label.setObjectName('extra_header_text_label')
        self.extra_header_text_label.setFont(font)

        self.toolbar_text_widget = QWidget()
        self.toolbar_text_layout = QHBoxLayout()
        self.toolbar_text_layout.addWidget(self.align_label_resolution)
        self.toolbar_text_layout.addWidget(self.alignment_status_label)
        self.toolbar_text_layout.addWidget(self.extra_header_text_label)
        self.toolbar_text_widget.setLayout(self.toolbar_text_layout)
        self.toolbar.addWidget(self.toolbar_text_widget)


        height = int(22) #was 22

        tip = 'Jump To Image #'
        self.toolbar_layer_label = QLabel('Layer #: ')
        self.toolbar_layer_label.setObjectName('toolbar_layer_label')
        self.toolbar_jump_input = QLineEdit(self)
        self.toolbar_jump_input.setFocusPolicy(Qt.ClickFocus)
        self.toolbar_jump_input.setStatusTip(tip)
        self.toolbar_jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.toolbar_jump_input.setFixedSize(QSize(46,height))
        self.toolbar_jump_input.returnPressed.connect(lambda: self.jump_to_layer())
        self.toolbar_layer_hlayout = QHBoxLayout()
        self.toolbar_layer_hlayout.addWidget(self.toolbar_layer_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toolbar_layer_hlayout.addWidget(self.toolbar_jump_input)
        self.toolbar_layer_widget = QWidget()
        self.toolbar_layer_widget.setLayout(self.toolbar_layer_hlayout)
        self.toolbar.addWidget(self.toolbar_layer_widget)

        self.toolbar_layout_label = QLabel('View: ')
        self.toolbar_layout_label.setObjectName('toolbar_layout_label')
        self.toolbar_layout_combobox = QComboBox()
        self.toolbar_layout_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toolbar_layout_combobox.setFixedSize(QSize(68, height))
        self.toolbar_view_hlayout = QHBoxLayout()
        self.toolbar_view_hlayout.addWidget(self.toolbar_layout_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toolbar_view_hlayout.addWidget(self.toolbar_layout_combobox)
        self.toolbar_view_widget = QWidget()
        self.toolbar_view_widget.setLayout(self.toolbar_view_hlayout)
        self.toolbar.addWidget(self.toolbar_view_widget)

        self.toolbar_scale_label = QLabel('Scale: ')
        self.toolbar_scale_label.setObjectName('toolbar_scale_label')
        self.toolbar_scale_combobox = QComboBox(self)
        self.toolbar_scale_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toolbar_scale_combobox.setFixedSize(QSize(82, height))
        self.toolbar_scale_combobox.currentTextChanged.connect(self.fn_scales_combobox)
        self.toolbar_scale_hlayout = QHBoxLayout()
        self.toolbar_scale_hlayout.addWidget(self.toolbar_scale_label)
        self.toolbar_scale_hlayout.addWidget(self.toolbar_scale_combobox, alignment=Qt.AlignmentFlag.AlignRight)
        self.toolbar_scale_widget = QWidget()
        self.toolbar_scale_widget.setLayout(self.toolbar_scale_hlayout)
        self.toolbar.addWidget(self.toolbar_scale_widget)

        tip = 'Show Neuroglancer key bindings'
        self.info_button_buffer_label = QLabel(' ')
        self.info_button = QPushButton()
        self.info_button.setContentsMargins(4, 0, 4, 0)
        self.info_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.info_button.setStatusTip(tip)
        self.info_button.clicked.connect(self.html_keyboard_commands)
        self.info_button.setFixedSize(height, height)
        self.info_button.setIcon(qta.icon("fa.info", color=cfg.ICON_COLOR))

        self.toolbar.addWidget(self.info_button)
        self.toolbar.addWidget(self.info_button_buffer_label)


    def updateStatusTips(self):
        self.regenerate_button.setStatusTip('Generate All Layers,  Scale %d (alters Corrective Bias '
                                            'and Bounding Rectangle)' % get_scale_val(cfg.data.scale()))
        self.align_forward_button.setStatusTip(
            'Align + Generate Layers %d -> End,  Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.scale())))
        self.align_all_button.setStatusTip('Generate + Align All Layers,  Scale %d' % get_scale_val(cfg.data.scale()))
        self.align_one_button.setStatusTip(
            'Align + Generate Layer %d,  Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.scale())))


    def onTabChange(self, index:int):
        if index == 0:
            self.initNgViewer()
        if index == 1:
            if cfg.data:
                self.layer_view_widget.set_data()
        if index == 2:
            # self.projectdata_treeview
            self.updateJsonWidget()
        if index == 3:
            self.snr_plot.initSnrPlot()

        QApplication.processEvents()
        self.repaint()


    def openArbitraryZarr(self):
        # if not ng.is_server_running():
        #     logger.warning('Neuroglancer is not running')
        #     return
        cfg.data = None
        self.browser_overlay_widget.hide()
        try:
            path = QFileDialog.getExistingDirectory(self, 'Select Zarr Directory')
        except:
            print_exception()
            return

        try:
            with open(os.path.join(path, '.zarray')) as j:
                self.zarray = json.load(j)
        except:
            logger.warning("'.zarray' Not Found. Invalid Path.")
            self.hud.post("'.zarray' Not Found. Invalid Path.")
            return
        pprint.pprint(self.zarray)
        shape = self.zarray['shape']
        chunks = self.zarray['chunks']
        logger.info(f'Shape  : {shape}')
        logger.info(f'Chunks : {chunks}')
        cfg.ng_worker = NgHostSlim(parent=self,
                            path=path,
                            shape=shape,
                            )
        cfg.ng_worker.initViewer()
        self.toolbar_layout_combobox.setCurrentText('xy')
        # self.toolbar_layout_combobox.currentTextChanged.connect(self.fn_ng_layout_combobox)
        self.ng_browser.setUrl(QUrl(str(cfg.viewer)))
        self.ng_browser.setFocus()



    def new_mendenhall_protocol(self):
        self.new_project(mendenhall=True)
        cfg.data['data']['cname'] = 'zstd'
        cfg.data['data']['clevel'] = 5
        cfg.data['data']['chunkshape'] = (1, 512, 512)
        cfg.data['data']['scales'][cfg.data.scale()]['resolution_x'] = 2
        cfg.data['data']['scales'][cfg.data.scale()]['resolution_y'] = 2
        cfg.data['data']['scales'][cfg.data.scale()]['resolution_z'] = 50
        self.browser_overlay_widget.hide()

        self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        self.mendenhall.set_directory()
        self.mendenhall.start_watching()
        cfg.data.set_source_path(self.mendenhall.sink)
        self.save_project_to_file()

    def open_mendenhall_protocol(self):
        filename = open_project_dialog()
        with open(filename, 'r') as f:
            project = DataModel(json.load(f), mendenhall=True)
        cfg.data = copy.deepcopy(project)
        cfg.data.set_paths_absolute(filename=filename) #+
        self.browser_overlay_widget.hide()
        self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        self.mendenhall.start_watching()
        self.initNgServer()

    def stop_mendenhall_protocol(self):
        self.mendenhall.stop_watching()

    def aligned_mendenhall_protocol(self):
        cfg.MV = not cfg.MV
        logger.info(f'cfg.MA: {cfg.MV}')
        self.initNgServer()

    def import_mendenhall_protocol(self):
        ''' Import images into data '''
        scale = 'scale_1'
        logger.critical('Importing Images...')
        filenames = natural_sort(os.listdir(cfg.data.source_path()))
        self.hud.post('Importing Images...')
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
        # for i, layer in enumerate(cfg.data.alstack()):
        #     [1]['images']['ref']['filename']
        self.save_project_to_file()


    #@timer
    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

        fileMenu = self.menu.addMenu('File')

        self.newAction = QAction('&New', self)
        self.newAction.triggered.connect(self.new_project)
        self.newAction.setShortcut('Ctrl+N')
        fileMenu.addAction(self.newAction)

        self.openAction = QAction('&Open Project...', self)
        self.openAction.triggered.connect(self.open_project)
        self.openAction.setShortcut('Ctrl+O')
        fileMenu.addAction(self.openAction)

        self.openArbitraryZarrAction = QAction('Open Zarr...', self)
        self.openArbitraryZarrAction.triggered.connect(self.openArbitraryZarr)
        fileMenu.addAction(self.openArbitraryZarrAction)

        self.saveAction = QAction('&Save', self)
        self.saveAction.triggered.connect(self.save_project)
        self.saveAction.setShortcut('Ctrl+S')
        fileMenu.addAction(self.saveAction)

        self.exportAfmAction = QAction('Export Affines', self)
        self.exportAfmAction.triggered.connect(self.export_afms)
        fileMenu.addAction(self.exportAfmAction)

        self.exportCafmAction = QAction('Export Cumulative Affines', self)
        self.exportCafmAction.triggered.connect(self.export_cafms)
        fileMenu.addAction(self.exportCafmAction)

        self.exitAppAction = QAction('Exit', self)
        self.exitAppAction.triggered.connect(self.exit_app)
        self.exitAppAction.setShortcut('Ctrl+Q')
        fileMenu.addAction(self.exitAppAction)

        viewMenu = self.menu.addMenu('View')

        self.normalizeViewAction = QAction('Normal', self)
        self.normalizeViewAction.triggered.connect(self.initView)
        viewMenu.addAction(self.normalizeViewAction)

        expandMenu = viewMenu.addMenu("Enlarge")

        self.expandPythonAction = QAction('Python Console', self)
        self.expandPythonAction.triggered.connect(self.expand_python_size)
        expandMenu.addAction(self.expandPythonAction)

        self.expandPlotAction = QAction('SNR Plot', self)
        self.expandPlotAction.triggered.connect(self.expand_plot_size)
        expandMenu.addAction(self.expandPlotAction)

        # self.expandTreeviewAction = QAction('Project Treeview', self)
        # self.expandTreeviewAction.triggered.connect(self.expand_treeview_size)
        # expandMenu.addAction(self.expandTreeviewAction)

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

        self.splashAction = QAction('Splash', self)
        self.splashAction.triggered.connect(self.show_splash)
        viewMenu.addAction(self.splashAction)

        neuroglancerMenu = self.menu.addMenu('Neuroglancer')

        self.ngRestartAction = QAction('Restart', self)
        self.ngRestartAction.triggered.connect(self.initNgServer)
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
        self.ngLayout1Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('xy'))
        self.ngLayout2Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('xz'))
        self.ngLayout3Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('yz'))
        self.ngLayout4Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('yz-3d'))
        self.ngLayout5Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('xy-3d'))
        self.ngLayout6Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('xz-3d'))
        self.ngLayout6Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('3d'))
        self.ngLayout8Action.triggered.connect(lambda: self.toolbar_layout_combobox.setCurrentText('4panel'))
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

        ngDebugMenu = neuroglancerMenu.addMenu("Debug")

        self.ngInvalidateAction = QAction('Invalidate Local Volumes', self)
        self.ngInvalidateAction.triggered.connect(self.invalidate_all)
        ngDebugMenu.addAction(self.ngInvalidateAction)

        self.ngRefreshViewerAction = QAction('Recreate View', self)
        self.ngRefreshViewerAction.triggered.connect(lambda: self.initNgViewer(scales=cfg.data.scales()))
        ngDebugMenu.addAction(self.ngRefreshViewerAction)

        self.ngRefreshUrlAction = QAction('Refresh URL', self)
        self.ngRefreshUrlAction.triggered.connect(self.refreshNeuroglancerURL)
        ngDebugMenu.addAction(self.ngRefreshUrlAction)

        self.ngRestartClientAction = QAction('Restart Client', self)
        self.ngRestartClientAction.triggered.connect(self.initNgServer)
        ngDebugMenu.addAction(self.ngRestartClientAction)

        self.ngGetUrlAction = QAction('Viewer URL', self)
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

        toolsMenu = self.menu.addMenu('Tools')

        alignMenu = toolsMenu.addMenu('Align')

        self.alignAllAction = QAction('Align All', self)
        self.alignAllAction.triggered.connect(lambda: self.align_all(scale=cfg.data.scale()))
        self.alignAllAction.setShortcut('Ctrl+A')
        alignMenu.addAction(self.alignAllAction)

        self.alignOneAction = QAction('Align One', self)
        self.alignOneAction.triggered.connect(lambda: self.align_one(scale=cfg.data.scale()))
        alignMenu.addAction(self.alignOneAction)

        self.alignForwardAction = QAction('Align Forward', self)
        self.alignForwardAction.triggered.connect(lambda: self.align_forward(scale=cfg.data.scale()))
        alignMenu.addAction(self.alignForwardAction)

        self.alignMatchPointAction = QAction('Match Point Align', self)
        self.alignMatchPointAction.triggered.connect(self.enterExitMatchPointMode)
        self.alignMatchPointAction.setShortcut('Ctrl+M')
        alignMenu.addAction(self.alignMatchPointAction)

        self.rescaleAction = QAction('Rescale', self)
        self.rescaleAction.triggered.connect(self.rescale)
        toolsMenu.addAction(self.rescaleAction)

        self.skipChangeAction = QAction('Toggle Skip', self)
        self.skipChangeAction.triggered.connect(self.skip_change_shortcut)
        self.skipChangeAction.setShortcut('Ctrl+K')
        toolsMenu.addAction(self.skipChangeAction)

        self.jumpWorstSnrAction = QAction('Jump To Next Worst SNR', self)
        self.jumpWorstSnrAction.triggered.connect(self.jump_to_worst_snr)
        toolsMenu.addAction(self.jumpWorstSnrAction)

        self.jumpBestSnrAction = QAction('Jump To Next Best SNR', self)
        self.jumpBestSnrAction.triggered.connect(self.jump_to_best_snr)
        toolsMenu.addAction(self.jumpBestSnrAction)

        self.reinitSnrPlotAction = QAction('Refresh SNR Plot', self)
        self.reinitSnrPlotAction.triggered.connect(self.snr_plot.initSnrPlot)
        toolsMenu.addAction(self.reinitSnrPlotAction)

        configMenu = self.menu.addMenu('Config')

        self.projectConfigAction = QAction('Project', self)
        self.projectConfigAction.triggered.connect(self.configure_project)
        configMenu.addAction(self.projectConfigAction)

        self.appConfigAction = QAction('Application', self)
        self.appConfigAction.triggered.connect(self.configure_application)
        configMenu.addAction(self.appConfigAction)

        mendenhallMenu = toolsMenu.addMenu('Mendenhall Protocol')

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

        detailsMenu = self.menu.addMenu('Details')

        zarrMenu = detailsMenu.addMenu('Zarr Details')

        self.detailsZarrSourceAction = QAction('img_src.zarr', self)
        self.detailsZarrSourceAction.triggered.connect(self.show_zarr_info_source)
        zarrMenu.addAction(self.detailsZarrSourceAction)

        self.detailsZarrAlignedAction = QAction('img_aligned.zarr', self)
        self.detailsZarrAlignedAction.triggered.connect(self.show_zarr_info_aligned)
        zarrMenu.addAction(self.detailsZarrAlignedAction)

        self.moduleSearchPathAction = QAction('Print Module Search Path', self)
        self.moduleSearchPathAction.triggered.connect(self.show_module_search_path)
        detailsMenu.addAction(self.moduleSearchPathAction)

        self.runtimePathAction = QAction('Print Runtime Path', self)
        self.runtimePathAction.triggered.connect(self.show_run_path)
        detailsMenu.addAction(self.runtimePathAction)

        self.showMatchpointsAction = QAction('Print Matchpoints', self)
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

        self.anableAllControlsAction = QAction('Enable All Controls', self)
        self.anableAllControlsAction.triggered.connect(self.enableAllButtons)
        debugMenu.addAction(self.anableAllControlsAction)

        self.printActiveThreadsAction = QAction('Show Active Threads', self)
        self.printActiveThreadsAction.triggered.connect(self.printActiveThreads)
        debugMenu.addAction(self.printActiveThreadsAction)

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

        std_height = int(22)
        std_button_size = QSize(96, std_height)
        normal_button_size = QSize(64, 28)
        slim_button_size = QSize(64, std_height)
        small_button_size = QSize(54, std_height)
        std_combobox_size = QSize(52, 20)

        lower_controls_style = "border-style: solid;" \
                               "border-top-color: qlineargradient(spread:pad, x1:0.5, y1:1, x2:0.5, y2:0, stop:0 rgb(215, 215, 215), stop:1 rgb(222, 222, 222));" \
                               "border-right-color: qlineargradient(spread:pad, x1:0, y1:0.5, x2:1, y2:0.5, stop:0 rgb(217, 217, 217), stop:1 rgb(227, 227, 227));" \
                               "border-left-color: qlineargradient(spread:pad, x1:0, y1:0.5, x2:1, y2:0.5, stop:0 rgb(227, 227, 227), stop:1 rgb(217, 217, 217));" \
                               "border-bottom-color: qlineargradient(spread:pad, x1:0.5, y1:1, x2:0.5, y2:0, stop:0 rgb(215, 215, 215), stop:1 rgb(222, 222, 222));" \
                               "border-width: 1px;" \
                               "border-radius: 3px;" \
                               "background-color: #004060; color: #f3f6fb;" \
                               "font-size: 11px;"

        '''Headup Display'''
        self.hud = HeadupDisplay(self.app)
        self.hud.setObjectName('hud')
        self.hud.post('Welcome To AlignEM-SWiFT.')
        self.hud_widget = QWidget()
        self.label_hud = QLabel('Process Monitor')
        self.label_hud.setStyleSheet('font-size: 10px;')
        self.hud_widget_layout = QVBoxLayout()
        self.hud_widget_layout.addWidget(self.label_hud)
        self.hud_widget_layout.addWidget(self.hud)
        self.hud_widget.setLayout(self.hud_widget_layout)

        tip = 'Use All Images (Reset)'
        self.clear_skips_button = QPushButton('Reset')
        self.clear_skips_button.setEnabled(False)
        self.clear_skips_button.setStyleSheet("font-size: 10px;")
        self.clear_skips_button.setStatusTip(tip)
        self.clear_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_skips_button.clicked.connect(self.clear_skips)
        self.clear_skips_button.setFixedSize(small_button_size)

        tip = 'Set Whether to Use or Reject the Current Layer'
        self.skip_label = QLabel("Toggle Image\nKeep/Reject:")
        self.skip_label.setStyleSheet("font-size: 11px;")
        self.skip_label.setStatusTip(tip)
        self.toggle_skip = QCheckBox()
        self.toggle_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_skip.setObjectName('toggle_skip')
        self.toggle_skip.stateChanged.connect(self.skip_changed_callback)
        self.toggle_skip.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_skip.setStatusTip(tip)
        self.toggle_skip.setEnabled(False)

        self.skip_layout = QHBoxLayout()
        self.skip_layout.addWidget(self.skip_label)
        self.skip_layout.addWidget(self.toggle_skip)
        self.skip_layout.addWidget(self.clear_skips_button)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        self.whitening_label = QLabel("Whitening\nFactor:")
        self.whitening_label.setStyleSheet("font-size: 11px;")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.textEdited.connect(self.has_unsaved_changes)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(66)  # 0829
        self.whitening_input.setFixedHeight(std_height)
        self.whitening_input.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        self.whitening_label.setStatusTip(tip)
        self.whitening_input.setStatusTip(tip)
        self.whitening_grid = QGridLayout()
        self.whitening_grid.addWidget(self.whitening_label, 0, 0)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1)
        self.whitening_input.setEnabled(False)

        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        self.swim_label = QLabel("SWIM Window\n(% size):")
        self.swim_label.setStyleSheet("font-size: 11px;")
        self.swim_input = QLineEdit(self)
        self.swim_input.textEdited.connect(self.has_unsaved_changes)
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(66)
        self.swim_input.setFixedHeight(std_height)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        self.swim_label.setStatusTip(tip)
        self.swim_input.setStatusTip(tip)
        self.swim_grid = QGridLayout()
        self.swim_grid.addWidget(self.swim_label, 0, 0)
        self.swim_grid.addWidget(self.swim_input, 0, 1)
        self.swim_input.setEnabled(False)

        # tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        self.apply_all_button = QPushButton("Apply All")
        self.apply_all_button.setEnabled(False)
        self.apply_all_button.setStatusTip('Apply These Settings To The Entire Project')
        self.apply_all_button.setStyleSheet("font-size: 10px;")
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_button.clicked.connect(self.apply_all)
        self.apply_all_button.setFixedSize(small_button_size)

        tip = 'Go To Next Scale.'
        self.next_scale_button = QPushButton()
        self.next_scale_button.setEnabled(False)
        self.next_scale_button.setStyleSheet("font-size: 11px;")
        self.next_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_scale_button.setStatusTip(tip)
        self.next_scale_button.clicked.connect(self.scale_up)
        self.next_scale_button.setFixedSize(std_height, std_height)
        self.next_scale_button.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        tip = 'Go To Previous Scale.'
        self.prev_scale_button = QPushButton()
        self.prev_scale_button.setEnabled(False)
        self.prev_scale_button.setStyleSheet("font-size: 11px;")
        self.prev_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_scale_button.setStatusTip(tip)
        self.prev_scale_button.clicked.connect(self.scale_down)
        self.prev_scale_button.setFixedSize(std_height, std_height)
        self.prev_scale_button.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        self.scale_ctrl_label = QLabel('Scale:')
        self.scale_ctrl_layout = QHBoxLayout()
        self.scale_ctrl_layout.setAlignment(Qt.AlignLeft)
        self.scale_ctrl_layout.addWidget(self.scale_ctrl_label)
        self.scale_ctrl_layout.addWidget(self.prev_scale_button)
        self.scale_ctrl_layout.addWidget(self.next_scale_button)

        tip = 'Align + Generate All Layers For Current Scale'
        self.align_all_button = QPushButton('Align This\nScale')
        self.align_all_button.setEnabled(False)
        self.align_all_button.setStyleSheet("font-size: 11px;")
        self.align_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_all_button.setStatusTip(tip)
        self.align_all_button.clicked.connect(lambda: self.align_all(scale=cfg.data.scale()))
        self.align_all_button.setFixedSize(normal_button_size)

        tip = 'Align and Generate This Layer'
        self.align_one_button = QPushButton('Align This\nLayer')
        self.align_one_button.setEnabled(False)
        self.align_one_button.setStyleSheet("font-size: 11px;")
        self.align_one_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_one_button.setStatusTip(tip)
        self.align_one_button.clicked.connect(lambda: self.align_one(scale=cfg.data.scale()))
        self.align_one_button.setFixedSize(normal_button_size)

        tip = 'Align and Generate From Layer Current Layer to End'
        self.align_forward_button = QPushButton('Align\nForward')
        self.align_forward_button.setEnabled(False)
        self.align_forward_button.setStyleSheet("font-size: 11px;")
        self.align_forward_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_forward_button.setStatusTip(tip)
        self.align_forward_button.clicked.connect(lambda: self.align_forward(scale=cfg.data.scale()))
        self.align_forward_button.setFixedSize(normal_button_size)

        tip = 'Automatically generate aligned images.'
        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.toggle_auto_generate = ToggleSwitch()
        self.toggle_auto_generate.stateChanged.connect(self.has_unsaved_changes)
        self.auto_generate_label.setStatusTip(tip)
        self.toggle_auto_generate.setStatusTip(tip)
        self.toggle_auto_generate.setChecked(True)
        self.toggle_auto_generate.toggled.connect(self.toggle_auto_generate_callback)
        self.toggle_auto_generate_hlayout = QHBoxLayout()
        self.toggle_auto_generate_hlayout.addWidget(self.auto_generate_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.toggle_auto_generate_hlayout.addWidget(self.toggle_auto_generate, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.toggle_auto_generate.setEnabled(False)

        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension. This' \
              ' option is set at the coarsest s, in order to form a contiguous dataset.'
        self.null_bias_label = QLabel("Corrective\n(Poly) Bias:")
        self.null_bias_label.setStyleSheet("font-size: 11px;")
        self.null_bias_label.setStatusTip(tip)
        self.bias_bool_combo = QComboBox(self)
        self.bias_bool_combo.setStyleSheet("font-size: 11px;")
        self.bias_bool_combo.currentIndexChanged.connect(self.has_unsaved_changes)
        self.bias_bool_combo.setStatusTip(tip)
        self.bias_bool_combo.addItems(['None', '0', '1', '2', '3', '4'])
        self.bias_bool_combo.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self.bias_bool_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bias_bool_combo.setFixedSize(std_combobox_size)
        self.bias_bool_combo.setEnabled(False)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label)
        self.poly_order_hlayout.addWidget(self.bias_bool_combo)

        tip = 'Bounding rectangle (default=ON). Caution: Turning this ON may ' \
              'significantly increase the size of your aligned images.'
        self.bounding_label = QLabel("Bounding\nRectangle:")
        self.bounding_label.setStyleSheet("font-size: 11px;")
        self.bounding_label.setStatusTip(tip)
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setChecked(True)
        self.toggle_bounding_rect.setStatusTip(tip)
        self.toggle_bounding_rect.toggled.connect(self.bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect)
        self.toggle_bounding_rect.setEnabled(False)

        logger.info('2')
        tip = "Recomputes the cumulative affine and generates new aligned images" \
              "based on the current Null Bias and Bounding Rectangle presets."
        self.regenerate_button = QPushButton('Regenerate')
        self.regenerate_button.setEnabled(False)
        self.regenerate_button.setStatusTip(tip)
        self.regenerate_button.clicked.connect(lambda: self.regenerate(scale=cfg.data.scale()))
        self.regenerate_button.setFixedSize(normal_button_size)
        self.regenerate_button.setStyleSheet("font-size: 10px;")

        self.skip_widget = QWidget()
        self.skip_widget.setLayout(self.skip_layout)
        self.swim_widget = QWidget()
        self.swim_widget.setLayout(self.swim_grid)
        self.whitening_widget = QWidget()
        self.whitening_widget.setLayout(self.whitening_grid)
        self.poly_order_widget = QWidget()
        self.poly_order_widget.setLayout(self.poly_order_hlayout)
        self.bounding_widget = QWidget()
        self.bounding_widget.setLayout(self.toggle_bounding_hlayout)
        self.scale_ctrl_widget = QWidget()
        self.scale_ctrl_widget.setLayout(self.scale_ctrl_layout)

        self.align_buttons_widget = QWidget()
        self.align_buttons_hlayout = QHBoxLayout()
        self.align_buttons_hlayout.addWidget(self.regenerate_button)
        self.align_buttons_hlayout.addWidget(self.align_one_button)
        self.align_buttons_hlayout.addWidget(self.align_forward_button)
        self.align_buttons_hlayout.addWidget(self.align_all_button)
        self.align_buttons_widget.setLayout(self.align_buttons_hlayout)

        self.new_control_panel = QWidget()
        self.new_control_panel.setFixedHeight(36)
        self.new_control_panel_layout = QHBoxLayout()
        self.new_control_panel_layout.addStretch(6)
        self.new_control_panel_layout.addWidget(self.skip_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(1)
        self.new_control_panel_layout.addWidget(self.swim_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(1)
        self.new_control_panel_layout.addWidget(self.whitening_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(1)
        self.new_control_panel_layout.addWidget(self.apply_all_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(1)
        self.new_control_panel_layout.addWidget(self.poly_order_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(1)
        self.new_control_panel_layout.addWidget(self.bounding_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(1)
        self.new_control_panel_layout.addWidget(self.align_buttons_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(2)
        self.new_control_panel_layout.addWidget(self.scale_ctrl_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.new_control_panel_layout.addStretch(6)
        self.new_control_panel.setLayout(self.new_control_panel_layout)

        self.label_project_details = QLabel('Details')
        self.label_project_details.setStyleSheet('font-size: 10px;')
        self.layer_details = QTextEdit()
        self.layer_details.setObjectName('layer_details')
        self.layer_details.setReadOnly(True)
        self.layer_details_widget = QWidget()
        self.layer_details_layout = QVBoxLayout()
        self.layer_details_layout.addWidget(self.label_project_details)
        self.layer_details_layout.addWidget(self.layer_details)
        self.layer_details_widget.setLayout(self.layer_details_layout)

        self.history_widget = QWidget()
        self.history_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.history_widget.setObjectName('history_widget')
        self.historyListWidget = QListWidget()
        self.historyListWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.historyListWidget.setObjectName('historyListWidget')
        self.historyListWidget.installEventFilter(self)
        self.historyListWidget.itemClicked.connect(self.historyItemClicked)
        self.label_history = QLabel('History')
        self.label_history.setStyleSheet('font-size: 10px;')
        self.history_layout = QVBoxLayout()
        self.history_layout.addWidget(self.label_history)
        self.history_layout.addWidget(self.historyListWidget)
        self.history_widget.setLayout(self.history_layout)

        self.projecthistory_treeview = QTreeView()
        self.projecthistory_treeview.setStyleSheet('background-color: #ffffff;')
        self.projecthistory_treeview.setObjectName('projectdata_treeview')
        self.projecthistory_model = JsonModel()
        self.projecthistory_treeview.setModel(self.projecthistory_model)
        self.projecthistory_treeview.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.projecthistory_treeview.setAlternatingRowColors(True)
        self.exit_projecthistory_view_button = QPushButton("Back")
        self.exit_projecthistory_view_button.setFixedSize(slim_button_size)
        self.exit_projecthistory_view_button.clicked.connect(self.back_callback)
        self.projectview_history_layout = QGridLayout()
        self.projectview_history_layout.addWidget(self.projecthistory_treeview, 0, 0, 1, 2)
        self.projectview_history_layout.addWidget(self.exit_projecthistory_view_button, 1, 0, 1, 1)
        self.historyview_widget = QWidget()
        self.historyview_widget.setLayout(self.projectview_history_layout)

        '''AFM/CAFM Widget'''
        self.label_afm = QLabel('Transformation')
        self.label_afm.setStyleSheet('font-size: 10px')
        self.label_afm.setObjectName('label_afm')
        self.afm_widget_ = QTextEdit()
        self.afm_widget_.setObjectName('afm_widget')
        self.afm_widget_.setReadOnly(True)
        self.afm_widget = QWidget()
        self.afm_widget_layout = QVBoxLayout()
        self.afm_widget_layout.addWidget(self.label_afm)
        self.afm_widget_layout.addWidget(self.afm_widget_)
        self.afm_widget.setLayout(self.afm_widget_layout)

        '''Neuroglancer Controls'''
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(std_button_size)
        self.reload_ng_button.clicked.connect(self.refreshNeuroglancerURL)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(std_button_size)
        self.print_state_ng_button.clicked.connect(self.print_ng_state_url)

        self.browser = QWebEngineView()
        self.ng_browser_container = QWidget()
        self.ng_browser_container.setObjectName('ng_browser_container')
        self.ng_browser = QWebEngineView()
        self.ng_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ng_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.ng_splitter.addWidget(self.ng_browser)
        self.ng_splitter.splitterMoved.connect(self.initNgViewer)
        self.ng_splitter.setSizes([300, 700])

        self.ng_browser_layout = QGridLayout()
        self.ng_browser_layout.addWidget(self.ng_splitter, 0, 0)
        self.browser_overlay_widget = QWidget()
        self.browser_overlay_widget.setObjectName('browser_overlay_widget')
        self.browser_overlay_widget.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.ng_browser_layout.addWidget(self.browser_overlay_widget, 0, 0)
        self.browser_overlay_label = QLabel()
        self.browser_overlay_label.setObjectName('browser_overlay_label')
        self.ng_browser_layout.addWidget(self.browser_overlay_label, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.ng_browser_container.setLayout(self.ng_browser_layout)

        self.label_ng = VerticalLabel('Neuroglancer 3DEM')
        self.label_ng.setObjectName('label_ng')
        self.ng_browser_container_outer_layout = QHBoxLayout()
        self.ng_browser_container_outer_layout.setContentsMargins(0,0,0,0)
        self.ng_browser_container_outer_layout.addWidget(self.label_ng)
        self.ng_browser_container_outer_layout.addWidget(self.ng_browser_container)
        self.ng_browser_container_outer = QWidget()
        self.ng_browser_container_outer.setObjectName('ng_browser_container_outer')
        self.ng_browser_container_outer.setLayout(self.ng_browser_container_outer_layout)

        self.ng_browser.setFocusPolicy(Qt.StrongFocus)
        self.ng_panel = QWidget()  # goes into the stack widget
        self.ng_panel.setObjectName('ng_panel')  # goes into the stack widget
        self.ng_panel_layout = QVBoxLayout()
        self.ng_panel_controls_widget = QWidget()
        self.ng_panel_controls_widget.hide()
        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_controls_widget.setLayout(self.ng_panel_controls_layout)
        # self.ng_panel_layout.addWidget(self.ng_browser_container)
        self.ng_panel_layout.addWidget(self.ng_browser_container_outer)
        self.ng_panel_layout.addWidget(self.ng_panel_controls_widget)
        self.ng_panel.setLayout(self.ng_panel_layout)

        self.alignem_splash_widget = QWidget()  # Todo refactor this it is not in use
        self.splashmovie = QMovie('src/resources/alignem_animation.gif')
        self.splashlabel = QLabel()
        self.splashlabel.setMovie(self.splashmovie)
        self.splashlabel.setMinimumSize(QSize(100, 100))
        l = QGridLayout()
        l.addWidget(self.splashlabel, 1, 1, 1, 1)
        self.alignem_splash_widget.setLayout(l)
        self.alignem_splash_widget.setGraphicsEffect(QGraphicsOpacityEffect().setOpacity(0.7))
        self.splashmovie.finished.connect(lambda: self.runaftersplash())

        tip = 'Exit Full Window View'
        self.exit_expand_viewer_button = QPushButton('Back')
        self.exit_expand_viewer_button.setObjectName('exit_expand_viewer_button')
        self.exit_expand_viewer_button.setStatusTip(tip)
        self.exit_expand_viewer_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_expand_viewer_button.clicked.connect(self.initView)
        self.exit_expand_viewer_button.setFixedSize(std_button_size)
        self.exit_expand_viewer_button.setIcon(qta.icon('fa.arrow-left', color=cfg.ICON_COLOR))
        self.full_window_controls_hlayout = QHBoxLayout()
        self.full_window_controls_hlayout.addWidget(self.exit_expand_viewer_button)
        self.full_window_controls_hlayout.addStretch()
        self.full_window_controls = QWidget()
        self.full_window_controls.setLayout(self.full_window_controls_hlayout)
        self.full_window_controls.hide()


        '''Image Panel Stack Widget'''
        self.image_panel_stack_widget = QStackedWidget()
        self.image_panel_stack_widget.setObjectName('ImagePanel')
        self.image_panel_landing_page = QWidget()
        self.image_panel_stack_widget.addWidget(self.alignem_splash_widget)
        self.image_panel_stack_widget.addWidget(self.ng_panel)
        self.image_panel_stack_widget.addWidget(self.image_panel_landing_page)
        self.image_panel_stack_widget.addWidget(self.historyview_widget)

        self.external_hyperlink = QTextBrowser()
        self.external_hyperlink.setObjectName('external_hyperlink')
        self.external_hyperlink.setMaximumHeight(24)
        self.external_hyperlink.setAcceptRichText(True)
        self.external_hyperlink.setOpenExternalLinks(True)

        '''Layer View Widget'''
        self.layer_view_widget = LayerViewWidget()
        self.layer_view_widget.setObjectName('layer_view_widget')
        self.layer_view_inner_layout = QVBoxLayout()
        # self.layer_view_inner_layout.addWidget(self.external_hyperlink)
        self.layer_view_inner_layout.addWidget(self.layer_view_widget)
        self.label_overview = VerticalLabel('Project Stackview')
        self.label_overview.setObjectName('label_overview')
        self.layer_view_outter_layout = QHBoxLayout()
        self.layer_view_outter_layout.addWidget(self.label_overview)
        self.layer_view_outter_layout.addLayout(self.layer_view_inner_layout)
        self.layer_view_container = QWidget(parent=self)
        self.layer_view_container.setLayout(self.layer_view_outter_layout)

        self.matchpoint_controls = QWidget()
        self.matchpoint_controls_hlayout = QHBoxLayout()

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
        self.realign_matchpoint_button.clicked.connect(lambda: self.align_one(scale=cfg.data.scale()))
        self.realign_matchpoint_button.setFixedSize(normal_button_size)

        self.matchpoint_controls_hlayout.addWidget(self.exit_matchpoint_button)
        self.matchpoint_controls_hlayout.addWidget(self.realign_matchpoint_button)
        self.matchpoint_controls_hlayout.addWidget(self.mp_marker_size_label)
        self.matchpoint_controls_hlayout.addWidget(self.mp_marker_size_spinbox)
        self.matchpoint_controls_hlayout.addWidget(self.mp_marker_lineweight_label)
        self.matchpoint_controls_hlayout.addWidget(self.mp_marker_lineweight_spinbox)
        self.matchpoint_controls_hlayout.addStretch()

        self.matchpoint_controls_vlayout = QVBoxLayout()
        self.matchpoint_text_snr = QTextEdit()
        self.matchpoint_text_snr.setObjectName('matchpoint_text_snr')

        self.matchpoint_text_prompt = QTextEdit()
        self.matchpoint_text_prompt.setObjectName('matchpoint_text_prompt')
        self.matchpoint_text_prompt.setHtml("Select 3-5 corresponding match points on the reference and base images. Key Bindings:<br>"
                                            "<b>Enter/return</b> - Add match points (Left, Right, Left, Right...)<br>"
                                            "<b>s</b>            - Save match points<br>"
                                            "<b>c</b>            - Clear match points for this layer")

        self.matchpoint_text_prompt.setReadOnly(True)
        self.matchpoint_controls_vlayout.addLayout(self.matchpoint_controls_hlayout)
        self.matchpoint_controls_vlayout.addWidget(self.matchpoint_text_snr)
        self.matchpoint_controls_vlayout.addWidget(self.matchpoint_text_prompt)
        self.matchpoint_controls_vlayout.addStretch()
        self.matchpoint_controls.setLayout(self.matchpoint_controls_vlayout)
        self.matchpoint_controls.hide()

        '''JSON Project View'''
        self.projectdata_treeview = QTreeView()
        self.projectdata_treeview.setStyleSheet('background-color: #ffffff;')
        self.projectdata_treeview.setObjectName('projectdata_treeview')
        self.project_model = JsonModel()
        self.projectdata_treeview.setModel(self.project_model)
        self.projectdata_treeview.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.projectdata_treeview.setAlternatingRowColors(True)
        self.exit_project_view_button = QPushButton('Back')
        self.exit_project_view_button.setFixedSize(slim_button_size)
        self.exit_project_view_button.clicked.connect(self.back_callback)
        self.refresh_project_view_button = QPushButton('Refresh')
        self.refresh_project_view_button.setFixedSize(slim_button_size)
        self.refresh_project_view_button.clicked.connect(self.updateJsonWidget)
        self.projectdata_treeview_widget = QWidget()
        self.projectdata_treeview_layout = QHBoxLayout()
        self.label_treeview = VerticalLabel('Project Data')
        self.label_treeview.setObjectName('label_treeview')
        self.projectdata_treeview_layout.addWidget(self.label_treeview)
        self.projectdata_treeview_layout.addWidget(self.projectdata_treeview)
        self.projectdata_treeview_widget.setLayout(self.projectdata_treeview_layout)

        '''Show/Hide Primary Tools Buttons'''
        show_hide_button_sizes = QSize(98, 18)

        tip = 'Show/Hide Alignment Controls'
        self.show_hide_controls_button = QPushButton('Hide Controls')
        self.show_hide_controls_button.setObjectName('show_hide_controls_button')
        self.show_hide_controls_button.setStyleSheet(lower_controls_style)
        self.show_hide_controls_button.setStatusTip(tip)
        self.show_hide_controls_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_controls_button.clicked.connect(self.show_hide_controls_callback)
        self.show_hide_controls_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_controls_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Python Console'
        self.show_hide_python_button = QPushButton(' Python')
        self.show_hide_python_button.setObjectName('show_hide_python_button')
        self.show_hide_python_button.setStyleSheet(lower_controls_style)
        self.show_hide_python_button.setStatusTip(tip)
        self.show_hide_python_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_python_button.clicked.connect(self.show_hide_python_callback)
        self.show_hide_python_button.setFixedSize(show_hide_button_sizes)
        # self.show_hide_python_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))
        self.show_hide_python_button.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))

        self.show_hide_main_features_widget = QWidget()
        self.show_hide_main_features_widget.setObjectName('show_hide_main_features_widget')
        self.show_hide_main_features_vlayout = QHBoxLayout()
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_controls_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_python_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.show_hide_main_features_vlayout.addStretch()
        self.show_hide_main_features_widget.setLayout(self.show_hide_main_features_vlayout)

        font = QFont()
        font.setBold(True)
        self.snr_plot = SnrPlot()
        self.label_y_axis = VerticalLabel('Signal-to-Noise Ratio')
        # self.label_y_axis.setStyleSheet("font-size: 12px;")
        self.label_y_axis.setFont(font)
        self.label_y_axis.setObjectName('label_y_axis')
        self.snr_plot_and_ylabel = QHBoxLayout()
        self.snr_plot_and_ylabel.addWidget(self.label_y_axis)
        self.snr_plot_and_ylabel.addWidget(self.snr_plot)
        self.snr_plot_layout = QVBoxLayout()
        self.snr_plot_widget = QWidget()
        self.label_x_axis = QLabel('Layer Number')
        self.label_x_axis.setStyleSheet("font-size: 11px;")
        self.label_x_axis.setFont(font)
        self.label_x_axis.setObjectName('label_x_axis')
        self.snr_plot_widget.setLayout(self.snr_plot_layout)
        self.snr_plot_layout.addLayout(self.snr_plot_and_ylabel)
        self.snr_plot_layout.addWidget(self.label_x_axis, alignment=Qt.AlignmentFlag.AlignHCenter)

        '''Tab Widget'''
        self.tabs_main = QTabWidget()
        self.tabs_main.setObjectName('tabs_main')
        self.tabs_main.addTab(self.image_panel_stack_widget, ' 3DEMview ')
        self.tabs_main.addTab(self.layer_view_container, ' Stackview ')
        self.tabs_main.addTab(self.projectdata_treeview_widget, ' Treeview ')
        self.tabs_main.addTab(self.snr_plot_widget, ' SNR Plot ')
        self.tabs_main.currentChanged.connect(self.onTabChange)

        '''Bottom Horizontal Splitter'''
        self.splitter_bottom_horizontal = QSplitter()
        self.splitter_bottom_horizontal.setMaximumHeight(90)
        self.splitter_bottom_horizontal.setHandleWidth(0)
        self.splitter_bottom_horizontal.addWidget(self.hud_widget)
        self.splitter_bottom_horizontal.addWidget(self.layer_details_widget)
        self.splitter_bottom_horizontal.addWidget(self.afm_widget)
        self.splitter_bottom_horizontal.addWidget(self.history_widget)
        self.splitter_bottom_horizontal.setCollapsible(0, True)
        self.splitter_bottom_horizontal.setCollapsible(1, True)
        self.splitter_bottom_horizontal.setCollapsible(2, True)
        self.splitter_bottom_horizontal.setCollapsible(3, True)

        self.layer_details_widget.hide()
        self.afm_widget.hide()
        self.history_widget.hide()

        '''Main Vertical Splitter'''
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(self.tabs_main)
        self.main_splitter.addWidget(self.new_control_panel)
        self.main_splitter.addWidget(self.splitter_bottom_horizontal)
        self.main_splitter.addWidget(self.matchpoint_controls)
        self.main_splitter.addWidget(self.python_console)
        self.main_splitter.setHandleWidth(0)
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)
        self.main_splitter.setCollapsible(2, False)
        self.main_splitter.setCollapsible(3, False)
        self.main_splitter.setCollapsible(4, False)
        self.main_splitter.setStretchFactor(0,5)
        self.main_splitter.setStretchFactor(1,1)
        self.main_splitter.setStretchFactor(2,1)
        self.main_splitter.setStretchFactor(3,1)
        self.main_splitter.setStretchFactor(4,1)

        self.new_main_widget = QWidget()
        self.new_main_widget_vlayout = QVBoxLayout()
        self.new_main_widget_vlayout.addWidget(self.main_splitter)
        self.new_main_widget.setLayout(self.new_main_widget_vlayout)

        '''Documentation Panel'''
        self.browser_docs = QWebEngineView()
        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(std_button_size)
        self.exit_docs_button.clicked.connect(self.exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(std_button_size)
        self.readme_button.clicked.connect(self.documentation_view_home)
        self.docs_panel = QWidget()
        self.docs_panel_layout = QVBoxLayout()
        self.docs_panel_layout.addWidget(self.browser_docs)
        self.docs_panel_controls_layout = QHBoxLayout()
        self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.docs_panel_controls_layout.addWidget(self.readme_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.docs_panel_controls_layout.addSpacerItem(self.spacer_item_docs)
        self.docs_panel_layout.addLayout(self.docs_panel_controls_layout)
        self.docs_panel.setLayout(self.docs_panel_layout)

        '''Remote Neuroglancer Viewer'''
        self.browser_remote = QWebEngineView()
        self.exit_remote_button = QPushButton('Back')
        self.exit_remote_button.setFixedSize(std_button_size)
        self.exit_remote_button.clicked.connect(self.exit_remote)
        self.reload_remote_button = QPushButton('Reload')
        self.reload_remote_button.setFixedSize(std_button_size)
        self.reload_remote_button.clicked.connect(self.reload_remote)
        self.remote_viewer_panel = QWidget()
        self.remote_viewer_panel_layout = QVBoxLayout()
        self.remote_viewer_panel_layout.addWidget(self.browser_remote)
        self.remote_viewer_panel_controls_layout = QHBoxLayout()
        self.remote_viewer_panel_controls_layout.addWidget(self.exit_remote_button,
                                                           alignment=Qt.AlignmentFlag.AlignLeft)
        self.remote_viewer_panel_controls_layout.addWidget(self.reload_remote_button,
                                                           alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_remote_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.remote_viewer_panel_controls_layout.addSpacerItem(self.spacer_item_remote_panel)
        self.remote_viewer_panel_layout.addLayout(self.remote_viewer_panel_controls_layout)
        self.remote_viewer_panel.setLayout(self.remote_viewer_panel_layout)

        '''Demos Panel'''
        self.exit_demos_button = QPushButton('Back')
        self.exit_demos_button.setFixedSize(std_button_size)
        self.exit_demos_button.clicked.connect(self.exit_demos)
        self.demos_panel = QWidget()
        self.demos_panel_layout = QVBoxLayout()
        self.demos_panel_controls_layout = QHBoxLayout()
        self.demos_panel_controls_layout.addWidget(self.exit_demos_button)
        self.demos_panel_layout.addLayout(self.demos_panel_controls_layout)
        self.demos_panel.setLayout(self.demos_panel_layout)

        self.main_panel = QWidget()
        self.main_panel_layout = QVBoxLayout()
        self.main_panel_layout.addWidget(self.new_main_widget)
        self.main_panel_layout.addWidget(self.full_window_controls)
        self.main_panel_layout.addWidget(self.show_hide_main_features_widget, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.main_stack_widget = QStackedWidget(self)
        self.main_stack_widget.addWidget(self.main_panel)           # (0) main_panel
        self.main_stack_widget.addWidget(self.docs_panel)           # (1) docs_panel
        self.main_stack_widget.addWidget(self.demos_panel)          # (2) demos_panel
        self.main_stack_widget.addWidget(self.remote_viewer_panel)  # (3) remote_viewer_panel

        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem('Main')
        self.pageComboBox.addItem('Neuroglancer Local')
        self.pageComboBox.addItem('Documentation')
        self.pageComboBox.addItem('Demos')
        self.pageComboBox.addItem('Remote Viewer')
        self.pageComboBox.addItem('Overview') #1102+
        self.pageComboBox.addItem('Project View')
        self.pageComboBox.activated[int].connect(self.main_stack_widget.setCurrentIndex)

        self.main_panel.setLayout(self.main_panel_layout)
        self.setCentralWidget(self.main_stack_widget)
        self.toolbar.setCursor(QCursor(Qt.PointingHandCursor))
        self.main_stack_widget.setCurrentIndex(0)


    def get_application_root(self):
        return Path(__file__).parents[2]


    def set_viewer_layout_1(self):
        if cfg.data:
            cfg.ng_worker.arrangement = 1
            cfg.ng_worker.initViewer()
            self.refreshNeuroglancerURL()


    def set_viewer_layout_2(self):
        if cfg.data:
            cfg.ng_worker.arrangement = 2
            cfg.ng_worker.initViewer()
            self.refreshNeuroglancerURL()


    def expand_plot_size(self):
        self._is_mp_mode = False
        self.full_window_controls.show()
        self.main_stack_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.hud_widget.hide()
        self.matchpoint_controls.hide()
        self.tabs_main.hide()
        self.snr_plot_widget.show()


    def expand_treeview_size(self):
        self.full_window_controls.show()
        self.extra_header_text_label.setText('')
        self.main_stack_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.hud_widget.hide()
        self.matchpoint_controls.hide()
        self.tabs_main.hide()
        self.projectdata_treeview_widget.show()
        self.projectdata_treeview_widget.show()


    def expand_python_size(self):
        self.full_window_controls.show()
        self.extra_header_text_label.setText('')
        self._is_mp_mode = False
        self.main_stack_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.hud_widget.hide()
        self.matchpoint_controls.hide()
        self.tabs_main.hide()
        self.python_console.show()


    def initWidgetSpacing(self):
        logger.info('')
        self.main_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.new_main_widget_vlayout.setContentsMargins(0, 0, 0, 0)
        self.show_hide_main_features_vlayout.setContentsMargins(0, 0, 0, 0)
        self.ng_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.ng_panel_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.ng_browser_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.setContentsMargins(2, 0, 2, 0)
        self.swim_grid.setContentsMargins(2, 0, 2, 0)
        self.scale_ctrl_layout.setContentsMargins(2, 0, 2, 0)
        self.toggle_bounding_hlayout.setContentsMargins(2, 0, 2, 0)
        self.skip_layout.setContentsMargins(2, 0, 2, 0)
        self.poly_order_hlayout.setContentsMargins(2, 0, 2, 0)
        self.align_buttons_hlayout.setContentsMargins(2, 0, 2, 0)
        self.new_control_panel_layout.setContentsMargins(4, 2, 4, 2)
        self.full_window_controls_hlayout.setContentsMargins(4, 0, 4, 0)
        self.python_console.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layer_hlayout.setContentsMargins(4, 0, 4, 0)
        self.toolbar_scale_hlayout.setContentsMargins(4, 0, 4, 0)
        self.toolbar_view_hlayout.setContentsMargins(4, 0, 4, 0)
        self.toolbar_text_layout.setContentsMargins(0, 0, 0, 0)
        self.external_hyperlink.setContentsMargins(8, 0, 0, 0)
        self.layer_view_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.projectdata_treeview_layout.setContentsMargins(2, 0, 2, 0)
        self.hud.setContentsMargins(2, 0, 2, 0)
        self.layer_view_outter_layout.setContentsMargins(0, 0, 0, 0)
        self.show_hide_main_features_widget.setContentsMargins(2, 0, 2, 0)
        self.snr_plot_layout.setContentsMargins(0, 0, 0, 0)
        self.snr_plot_and_ylabel.setContentsMargins(0, 0, 0, 0)
        self.afm_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.hud_widget_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_details.setContentsMargins(0, 0, 0, 0)
        self.layer_details_layout.setContentsMargins(0, 0, 0, 0)
        self.show_hide_main_features_widget.setMaximumHeight(24)
        self.matchpoint_text_snr.setMaximumHeight(20)
        self.history_widget.setMinimumWidth(148)
        self.afm_widget.setFixedWidth(240)
        self.layer_details.setMinimumWidth(190)


    def initStatusBar(self):
        logger.info('')
        self.statusBar = self.statusBar()
        self.statusBar.setFixedHeight(20)


    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setFont(QFont('Arial', 11))
        self.pbar.setFixedHeight(16)
        self.statusBar.addPermanentWidget(self.pbar)
        self.pbar.hide()


    def pbar_max(self, x):
        self.pbar.setMaximum(x)


    def pbar_update(self, x):
        self.pbar.setValue(x)


    def setPbarText(self, text: str):
        self.pbar.setFormat('(%p%) ' + text)


    def showZeroedPbar(self):
        self.pbar.setValue(0)
        self.setPbarText('Preparing Multiprocessing Tasks...')
        self.pbar.show()


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
        if cfg.data:
            self.image_panel_stack_widget.setCurrentIndex(1)
        # else:
        #     self.image_panel_stack_widget.setCurrentIndex(2)


    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self.historyListWidget:
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


