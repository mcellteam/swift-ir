#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os
import shutil
import sys
import copy
import time
import glob
import json
import inspect
import logging
import operator
import platform
import textwrap
from pathlib import Path
import psutil
import zarr
import dis
from collections import namedtuple

from neuroglancer.viewer_config_state import AggregateChunkSourceStatistics
from neuroglancer.viewer_config_state import ChunkSourceStatistics

import neuroglancer as ng
import neuroglancer.server
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
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView, QTabWidget, QStatusBar

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
from src.generate_zarr_scales import generate_zarr_scales
from src.helpers import *
from src.helpers import natural_sort, get_snr_average, make_affine_widget_HTML, is_tacc, \
    create_project_structure_directories, get_aligned_scales
from src.ng_host import NgHost
from src.ui.dialogs import AskContinueDialog, ConfigDialog, QFileDialogPreview, \
    import_images_dialog, new_project_dialog, open_project_dialog, export_affines_dialog, mendenhall_dialog
# from src.napari_test import napari_test
from src.ui.headup_display import HeadupDisplay
from src.ui.kimage_window import KImageWindow
from src.ui.python_console import PythonConsole
from src.ui.snr_plot import SnrPlot
from src.ui.toggle_switch import ToggleSwitch
from src.ui.models.json_tree import JsonModel
from src.ui.models.preview import PreviewModel, PreviewDelegate
from src.ui.layer_view_widget import LayerViewWidget
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
        self.initJupyter()
        self.initMenu()
        self.initToolbar()
        self.initPbar()
        self.initUI()
        self.initWidgetSpacing()
        self.initSize(cfg.WIDTH, cfg.HEIGHT)
        self.initPos()
        self.initStyle()
        self.initPlotColors()
        self.initView()
        self.initPrivateMembers()
        self.initShortcuts()
        self.initData()

        if is_tacc():
            cfg.USE_TORNADO = True
            cfg.USE_NG_WEBDRIVER = False

        if not cfg.NO_SPLASH:
            self.show_splash()


    def initSize(self, width, height):
        self.resize(width, height)


    def initPos(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def initData(self):
        # logger.info('')
        cfg.data = None
        if cfg.DUMMY:
            with open('tests/example.proj', 'r') as f:
                data = json.load(f)
            project = DataModel(data=data)
            cfg.data = copy.deepcopy(project)
            cfg.data.set_paths_absolute(head='tests/example.proj')  # Todo This may not work
            cfg.data.link_all_stacks()
            self.onStartProject()


    def resizeEvent(self, event):
        self.resized.emit()
        if cfg.data:
            self.refreshNeuroglancerURL()
        return super(MainWindow, self).resizeEvent(event)


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
        self.webengineview = QWebEngineView()
        # self.browser.setPage(CustomWebEnginePage(self)) # open links in new window
        # if qtpy.PYSIDE6:
        # self.webengineview.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.webengineview.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.webengineview.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.webengineview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        # self.webengineview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)


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
        self.ng_workers = {}


    def initStyle(self):
        logger.info('')
        self.main_stylesheet = os.path.abspath('styles/default.qss')
        self.apply_default_style()


    def initPlotColors(self):
        logger.info('')
        self._plot_colors = ['#aaa672', '#152c74', '#404f74',
                             '#ffe135', '#5c4ccc', '#d6acd6',
                             '#aaa672', '#152c74', '#404f74',
                             '#f3e375', '#5c4ccc', '#d6acd6',
                             ]
        self._plot_brushes = [pg.mkBrush(c) for c in self._plot_colors]


    def initJupyter(self):
        logger.info('')
        self.python_console = PythonConsole(customBanner='Caution - anything executed here is injected into the main '
                                                         'event loop of AlignEM-SWiFT - '
                                                         'As they say, with great power...!\n\n')
        self.python_console.setObjectName('python_console')
        # self.python_console.push_vars({'align_all':self.align_all})


    def shutdownJupyter(self):
        try:
            # self.python_console._kernel_client.stop_channels()
            self.python_console._kernel_manager.shutdown_kernel()
        except:
            logger.info('Having trouble shutting down Jupyter Console Kernel')
            self.python_console.request_interrupt_kernel()


    def restart_python_kernel(self):
        self.hud.post('Restarting Python Kernel...')
        self.python_console.request_restart_kernel()


    def initView(self):
        logger.info('')
        self.main_tab_widget.show()
        self.full_window_controls.hide()
        self.main_stack_widget.setCurrentIndex(0)
        self.main_tab_widget.setCurrentIndex(0)
        self.force_hide_expandable_widgets()
        self.low_low_widget.show()
        self.hud.show()
        self.new_control_panel.show()
        self.toolbar_scale_combobox.setEnabled(True)
        cfg.SHADER = None

        if cfg.data:
            self._is_mp_mode = False
            self.image_panel_stack_widget.setCurrentIndex(1)
            if is_cur_scale_aligned():
                self.updateStatusTips()
                self.showScoreboardWidegts()
            else:
                self.hideScoreboardWidgets()
            self.matchpoint_controls.hide()
            self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))
        else:
            self.image_panel_stack_widget.setCurrentIndex(2)


    def showScoreboardWidegts(self):
        self.main_details_subwidgetA.show()
        self.main_details_subwidgetB.show()
        self.afm_widget.show()
        self.history_widget.show()


    def hideScoreboardWidgets(self):
        self.main_details_subwidgetA.hide()
        self.main_details_subwidgetB.hide()
        self.afm_widget.hide()
        self.history_widget.hide()


    def force_hide_python_console(self):
        self.python_console.hide()
        self.show_hide_python_button.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))
        self.show_hide_python_button.setText(' Python')


    def force_hide_snr_plot(self):
        self.snr_plot_and_control.hide()
        self.show_hide_snr_plot_button.setIcon(qta.icon("mdi.scatter-plot", color='#f3f6fb'))
        self.show_hide_snr_plot_button.setText('SNR Plot')


    def force_hide_project_treeview(self):
        self.projectdata_treeview.hide()
        self.projectdata_treeview_widget.hide()
        self.show_hide_project_tree_button.setIcon(qta.icon("mdi.json", color='#f3f6fb'))
        self.show_hide_project_tree_button.setText('Tree View')


    def force_hide_expandable_widgets(self):
        self.force_hide_python_console()
        self.force_hide_snr_plot()
        self.force_hide_project_treeview()


    def show_hide_project_tree_callback(self):

        if self.projectdata_treeview.isHidden():
            self.read_project_data_update_gui()
            self.projectdata_treeview.show()
            self.projectdata_treeview_widget.show()
            self.show_hide_project_tree_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_project_tree_button.setText('Hide Tree View')
        else:
            self.projectdata_treeview.hide()
            self.projectdata_treeview_widget.hide()
            self.show_hide_project_tree_button.setIcon(qta.icon("mdi.json", color='#f3f6fb'))
            self.show_hide_project_tree_button.setText('Tree View')


    def show_hide_snr_plot_callback(self):
        if self.snr_plot_and_control.isHidden():
            self.snr_plot_and_control.show()
            self.show_hide_snr_plot_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_snr_plot_button.setText('Hide SNR Plot')
        else:
            self.snr_plot_and_control.hide()
            self.show_hide_snr_plot_button.setIcon(qta.icon("mdi.scatter-plot", color='#f3f6fb'))
            self.show_hide_snr_plot_button.setText('SNR Plot')


    def show_hide_python_callback(self):
        if self.python_console.isHidden():
            self.python_console.show()
            self.show_hide_python_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_python_button.setText('Hide Python')
        else:
            self.python_console.hide()
            self.show_hide_python_button.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))
            self.show_hide_python_button.setText(' Python')


    def show_hide_controls_callback(self):
        if self.new_control_panel.isHidden():
            self.read_project_data_update_gui()  # for short-circuiting speed-ups
            self.new_control_panel.show()
            self.hud.show()
            self.show_hide_controls_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_controls_button.setText('Hide Controls')
        else:
            self.new_control_panel.hide()
            self.hud.hide()
            self.show_hide_controls_button.setIcon(qta.icon("ei.adjust-alt", color='#f3f6fb'))
            self.show_hide_controls_button.setText('Controls')


    def show_hide_hud_callback(self):
        if self.hud.isHidden():
            self.hud.show()
            self.show_hide_hud_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_hud_button.setText('Hide HUD')
        else:
            self.hud.hide()
            self.show_hide_hud_button.setIcon(qta.icon("fa.dashboard", color='#f3f6fb'))
            self.show_hide_hud_button.setText('HUD')


    def go_to_overview_callback(self):
        self.main_stack_widget.setCurrentIndex(4)
        self.layer_view_widget.set_data()


    # def write_paged_tiffs(self):
    #     t0 = time.time()
    #     dest = cfg.data.dest()
    #     for s in cfg.data.aligned_list():
    #         logger.info('Exporting Alignment for Scale %d to Multipage Tif...' % get_scale_val(s))
    #         directory = os.path.join(dest, s, 'img_aligned')
    #         out = os.path.join(dest, s + '_multi.tif')
    #         tiffs2MultiTiff(directory=directory, out=out)
    #     dt = time.time() - t0
    #     logger.info('Exporting Tifs Took %g Seconds' % dt)


    def autoscale(self, make_thumbnails=True):
        #Todo This should check for existence of original source files before doing anything
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.hud.post('Generating TIFF Scale Hierarchy...')
        self.set_status('Scaling...')
        try:
            self.worker = BackgroundWorker(fn=generate_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud('Something Unexpected Happened While Generating TIFF Scale Hierarchy', logging.WARNING)

        cfg.data.link_all_stacks() #Todo: check if this is necessary
        self.wipe_snr_plot() #Todo: Move this it should not be here
        cfg.data.set_scale(cfg.data.scales()[-1])

        for s in cfg.data.scales():
            cfg.data.set_image_size(scale=s)

        self.set_status('Copy-converting TIFFs...')
        self.hud.post('Copy-converting TIFFs to Zarr...')
        try:
            self.worker = BackgroundWorker(fn=generate_zarr_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud('Something Unexpected Happened While Converting The Scale Hierarchy To Zarr', logging.WARNING)

        if make_thumbnails:
            self.set_status('Generating Thumbnails...')
            self.hud.post('Generating Thumbnails...')
            try:
                self.worker = BackgroundWorker(fn=generate_thumbnails())
                self.threadpool.start(self.worker)
            except:
                print_exception()
                self.hud('Something Unexpected Happened While Generating Thumbnails', logging.WARNING)

            finally:
                # self.initNgServer()
                logger.info('<<<< Autoscale <<<<')

        cfg.data.nscales = len(cfg.data.scales())
        cfg.data.set_scale(cfg.data.scales()[-1])


    def onAlignmentEnd(self):
        s = cfg.data.scale()
        # self.initNgServer(scales=[s])
        cfg.data.list_aligned = get_aligned_scales()
        cfg.data.naligned = len(cfg.data.list_aligned)
        self.initNgViewer()
        self.updateHistoryListWidget(s=s)
        self.initSnrPlot()
        self.read_project_data_update_gui()
        self.updateBanner()
        self.updateEnabledButtons()
        self.showScoreboardWidegts()
        self.project_model.load(cfg.data.to_dict())



    def align_all(self, scale=None) -> None:

        if not cfg.data:
            self.hud.post('No data yet!', logging.WARNING);
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING);
            return

        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud.post(warning_msg, logging.WARNING)
            return

        logger.critical('Aligning All...')
        if scale == None: scale = cfg.data.scale()
        scale_val = get_scale_val(scale)
        self.read_gui_update_project_data()
        is_realign = is_cur_scale_aligned()
        if is_realign:
            # For computing SNR differences later
            snr_before = cfg.data.snr_list()
            snr_avg_before = cfg.data.snr_average()

        if cfg.data.al_option(s=scale) == 'init_affine':
            self.hud.post("Computing Initial Affine Transforms,  Scale %d..." % scale_val)
        else:
            self.hud.post("Computing Refinement of Affine Transforms,  Scale %d..." % scale_val)
        self.set_status('Aligning...')
        try:
            self.worker = BackgroundWorker(
                fn=compute_affines(
                    scale=scale,
                    start_layer=0,
                    num_layers=-1
                )
            )
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)
        finally:
            self.set_idle()

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
            self.worker = BackgroundWorker(
                fn=generate_aligned(
                    scale=scale,
                    start_layer=0,
                    num_layers=-1,
                    preallocate=True
                )
            )
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('Alignment Succeeded But Image Generation Failed Unexpectedly. '
                          'Try Re-generating images.', logging.ERROR)
        else:
            self.hud.post('Alignment Succeeded')
            self.initSnrPlot()
            self.read_project_data_update_gui()
            self.save_project_to_file()
        finally:
            self.onAlignmentEnd()
            self.set_idle()
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

        logger.critical('Aligning Forward...')
        if scale == None: scale = cfg.data.scale()
        scale_val = get_scale_val(scale)
        self.read_gui_update_project_data()
        start_layer = cfg.data.layer()
        self.hud.post('Computing Alignment For Layers %d -> End,  Scale %d...' % (start_layer, scale_val))
        self.set_status('Aligning...')
        try:
            self.worker = BackgroundWorker(
                fn=compute_affines(
                    scale=scale,
                    start_layer=start_layer,
                    num_layers=num_layers
                )
            )
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)

        self.hud.post('Generating Aligned Images From Layers %d -> End,  Scale  %d...' % (start_layer, scale_val))
        self.set_status('Generating Alignment...')
        try:
            self.worker = BackgroundWorker(
                fn=generate_aligned(scale=scale, start_layer=start_layer, num_layers=num_layers, preallocate=False))
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.', logging.ERROR)

        else:
            self.hud.post('Alignment Succeeded')
            self.initSnrPlot()
            self.read_project_data_update_gui()
            self.save_project_to_file()
        finally:
            self.onAlignmentEnd()
            self.set_idle()
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

        logger.info('SNR Before: %s' % str(cfg.data.snr()))
        logger.critical('Aligning Single Layer...')
        if scale == None: scale = cfg.data.scale()
        scale_val = get_scale_val(scale)
        self.read_gui_update_project_data()
        self.hud.post('Re-aligning The Current Layer,  Scale %d...' % scale_val)
        self.set_status('Aligning...')
        try:
            self.worker = BackgroundWorker(
                fn=compute_affines(
                    scale=scale,
                    start_layer=cfg.data.layer(),
                    num_layers=1
                )
            )
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)

        cur_layer = cfg.data.layer()
        self.hud.post('Generating Aligned Image For Layer %d Only...' % cur_layer)
        self.set_status('Generating Alignment...')
        try:

            self.worker = BackgroundWorker(
                fn=generate_aligned(scale=scale, start_layer=cur_layer, num_layers=1, preallocate=False))
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.', logging.ERROR)
        else:
            self.hud.post('Alignment Succeeded')
            self.initSnrPlot()
            self.read_project_data_update_gui()
            self.save_project_to_file()
        finally:
            self.onAlignmentEnd()
            self.matchpoint_text_snr.setHtml(f'<p><b>{cfg.data.snr()}</b></p>')
            self.set_idle()
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
            self.hud.post('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING); return
        self.read_gui_update_project_data()
        logger.info('Regenerate Aligned Images...')
        self.hud.post('Regenerating Aligned Images,  Scale %d...' % get_scale_val(scale))
        try:
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
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Image Generation.', logging.ERROR)
        else:
            self.read_project_data_update_gui()
            self.save_project_to_file()
        finally:
            self.updateJsonWidget()
            # self.initNgServer(scales=[cfg.data.scale()])
            self.initNgViewer()
            if are_aligned_images_generated():
                self.hud.post('Regenerate Succeeded')
            else:
                self.hud.post('Image Generation Failed Unexpectedly. Try Re-aligning.', logging.ERROR)
            self.set_idle()
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
        try:
            self.set_status('Exporting...')
            self.worker = BackgroundWorker(fn=generate_zarr_scales(src=src, out=out))
            self.threadpool.start(self.worker)
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
                                         'Please verify your action to clear all skips. '
                                         'This makes all images unskipped.',
                                         QMessageBox.Cancel | QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                try:
                    self.hud.post('Resetting Skips...')
                    cfg.data.clear_all_skips()
                except:
                    print_exception()
                    self.hud.post('Something Went Wrong', logging.WARNING)
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
        self.setStyleSheet(open(self.main_stylesheet).read())
        pg.setConfigOption('background', '#1B1E23')
        # self.python_console.set_color_none()
        self.hud.set_theme_default()
        # self.python_console.setStyleSheet('background-color: #004060; border-width: 0px; color: #f3f6fb;')
        self.python_console.setStyleSheet('background-color: #004060; border-width: 0px; color: #f3f6fb;')
        self.toolbar_scale_combobox.setStyleSheet('background-color: #f3f6fb; color: #000000;')
        if cfg.data:
            if inspect.stack()[1].function != 'initStyle':
                self.initNgViewer(scales=[cfg.data.scale()])


    def apply_daylight_style(self):
        cfg.THEME = 1
        if inspect.stack()[1].function != 'initStyle':
            self.hud.post('Setting Daylight Theme')
        self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())
        pg.setConfigOption('background', 'w')
        # self.python_console.set_color_none()
        self.python_console.set_color_linux()
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
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_linux()
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
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #000000')
        if cfg.data:
            if inspect.stack()[1].function != 'initStyle':
                self.initNgViewer(scales=[cfg.data.scale()])


    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')


    def onScaleChange(self):
        s = cfg.data.scale()
        logger.debug('Changing To Scale %s (caller %s)...' % (s, inspect.stack()[1].function))
        # self.initNgServer(scales=[s])
        # self.refreshNeuroglancerURL(s=cfg.data.scale())
        if cfg.SIMULTANEOUS_SERVERS:
            self.initNgViewer(scales=[cfg.data.scale()])
        else:
            self.initNgServer(scales=[cfg.data.scale()])
        self.jump_to(cfg.data.layer())
        self.read_project_data_update_gui()
        self.updateHistoryListWidget(s=s)
        self.project_model.load(cfg.data.to_dict())
        self.updateLowLowWidgetB()
        self.updateBanner(s=s)
        self.updateEnabledButtons()
        self.updateStatusTips()
        if self.main_tab_widget.currentIndex() == 1:
            self.layer_view_widget.set_data()
        self.read_project_data_update_gui()


    @Slot()
    def read_gui_update_project_data(self) -> None:
        '''Reads MainWindow to Update Project Data.'''
        #1109 refactor - no longer can be called for every layer change...
        logger.debug('read_gui_update_project_data:')
        if self.bias_bool_combo.currentText() == 'None':
            cfg.data.set_use_poly_order(False)
        else:
            cfg.data.set_use_poly_order(True)
            cfg.data.set_poly_order(self.bias_bool_combo.currentText())
        cfg.data.set_use_bounding_rect(self.toggle_bounding_rect.isChecked(), s=cfg.data.scale())
        cfg.data.set_whitening(float(self.whitening_input.text()))
        cfg.data.set_swim_window(float(self.swim_input.text()))

    @Slot()
    def read_project_data_update_gui(self, ng_layer=None) -> None:
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
                if -1 < ng_layer < cfg.data.n_layers():
                    cfg.data.set_layer(ng_layer)
                # else:
                #     logger.critical('Bad Layer Requested (%d)' % ng_layer)
            except:
                print_exception()
            if ng_layer == cfg.data.n_layers():
                self.browser_overlay_widget.setStyleSheet('background-color: rgba(0, 0, 0, 1.0);')
                self.browser_overlay_label.setText('End Of Image Stack')
                self.browser_overlay_label.show()
                self.browser_overlay_widget.show()
                self.clearTextWidgetA()
                self.clearAffineWidget()
                # logger.info(f'Showing Browser Overlay, Last Layer ({cfg.data.layer()}) - Returning') #Todo
                return
            else:
                self.browser_overlay_widget.hide()
                self.browser_overlay_label.hide()
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
        if is_cur_scale_aligned():
            self.updateAffineWidget()

        # logger.info(f'Updating, Current Layer {cfg.data.layer()}...')
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

        if self.main_tab_widget.currentIndex() == 1:
            self.layer_view_widget.set_data()


    def updateTextWidgetA(self, s=None, l=None):
        if s == None: s = cfg.data.scale()
        if l == None: l = cfg.data.layer()
        name = "<b style='color: #010048;font-size:14px;'>%s</b><br>" % cfg.data.name_base(s=s, l=l)
        skip = "<b style='color:red;'> SKIP</b><br>" if cfg.data.skipped(s=s, l=l) else ''
        completed = "<b style='color: #212121;font-size:12px;'>Scales Aligned: (%d/%d)</b><br>" % \
                    (cfg.data.naligned, cfg.data.nscales)
        if is_cur_scale_aligned():
            if cfg.data.has_bb(s=s):
                bb = cfg.data.bounding_rect(s=s)
                dims = [bb[2], bb[3]]
            else:
                dims = cfg.data.image_size(s=s)
            bb_dims = "<b style='color: #212121;font-size:12px;'>Bounds: %dx%dpx</b><br>" % (dims[0], dims[1])
            snr = "<b style='color:#212121; font-size=10px;'>%s</b><br>" % cfg.data.snr(s=s, l=l)
            self.main_details_subwidgetA.setText(f"{name}{skip}"
                                                 f"{bb_dims}"
                                                 f"{snr}"
                                                 f"{completed}")
        else:
            self.main_details_subwidgetA.setText(f"{name}{skip}"
                                                 f"<em style='color: #FF0000;'>Not Aligned</em><br>"
                                                 f"{completed}")


    def clearTextWidgetA(self):
        self.main_details_subwidgetA.setText('')


    def updateLowLowWidgetB(self):
        skips = '\n'.join(map(str,cfg.data.skips_list()))
        matchpoints = '\n'.join(map(str,cfg.data.find_layers_with_matchpoints()))
        self.main_details_subwidgetB.setText(f"<b>Skipped Layers:</b><br>"
                                             f"{skips}<br>"
                                             f"<b>Match Point Layers:</b><br>"
                                             f"{matchpoints}<br>")


    def clearLowLowWidgetB(self):
        self.main_details_subwidgetB.setText(f'<b>Skipped Layers:<br><b>Match Point Layers:</b>')


    def updateAffineWidget(self, s=None, l=None):
        if s == None: s = cfg.data.scale()
        if l == None: l = cfg.data.layer()
        if is_cur_scale_aligned():
            afm, cafm = cfg.data.afm(l=l), cfg.data.cafm(l=l)
            self.afm_widget.setText(make_affine_widget_HTML(afm, cafm))


    def clearAffineWidget(self):
        afm = cafm = [[0] * 3, [0] * 3]
        self.afm_widget.setText(make_affine_widget_HTML(afm, cafm))


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
            index = self.ng_workers[cfg.data.scale()].cur_index
            assert isinstance(index, int)
            return index
        except:
            print_exception()


    def request_ng_layer(self):
        '''Returns The Currently Shown Layer Index In Neuroglancer'''
        return self.ng_workers[cfg.data.scale()].request_layer()


    def updateJumpValidator(self):
        self.jump_validator = QIntValidator(0, cfg.data.n_layers())
        self.toolbar_jump_input.setValidator(self.jump_validator)


    @Slot()
    def jump_to(self, requested) -> None:
        if requested not in range(cfg.data.n_layers()):
            logger.warning('Requested layer is not a valid layer')
            return
        # logger.info('Jumping To Layer %d' % requested)
        state = copy.deepcopy(self.ng_workers[cfg.data.scale()].viewer.state)
        state.position[0] = requested
        self.ng_workers[cfg.data.scale()].viewer.set_state(state)
        self.read_project_data_update_gui()
        self.refreshNeuroglancerURL()


    @Slot()
    def jump_to_layer(self) -> None:
        requested = int(self.toolbar_jump_input.text())
        if requested not in range(cfg.data.n_layers()):
            logger.warning('Requested layer is not a valid layer')
            return
        logger.info('Jumping To Layer %d' % requested)
        state = copy.deepcopy(self.ng_workers[cfg.data.scale()].viewer.state)
        state.position[0] = requested
        self.ng_workers[cfg.data.scale()].viewer.set_state(state)
        self.read_project_data_update_gui()
        self.refreshNeuroglancerURL()


    def jump_to_worst_snr(self) -> None:
        if not are_images_imported():
            self.hud.post("Images Must Be Imported First", logging.WARNING)
            return
        if not are_aligned_images_generated():
            self.hud.post("You Must Align This Scale First!")
            return
        try:
            # self.read_gui_update_project_data()
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
            self.read_project_data_update_gui()
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
            # self.read_gui_update_project_data()
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
            self.read_project_data_update_gui()
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
            # logger.warning('Canceling scale change...')
            return
        self.ng_workers[cfg.data.scale()] = {}
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
                self.ng_workers[s].nglayout = 'yz'
                self.ng_workers[s].initViewer()
                self.ngLayout1Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'yz':
                self.ng_workers[s].nglayout = 'xy'
                self.ng_workers[s].initViewer()
                self.ngLayout2Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'xz':
                self.ng_workers[s].nglayout = 'xz'
                self.ng_workers[s].initViewer()
                self.ngLayout3Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'xy-3d':
                self.ng_workers[s].nglayout = 'yz-3d'
                self.ng_workers[s].initViewer()
                self.ngLayout4Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'yz-3d':
                self.ng_workers[s].nglayout = 'xy-3d'
                self.ng_workers[s].initViewer()
                self.ngLayout5Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == 'xz-3d':
                self.ng_workers[s].nglayout = 'xz-3d'
                self.ng_workers[s].initViewer()
                self.ngLayout6Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == '3d':
                self.ng_workers[s].nglayout = '3d'
                self.ng_workers[s].initViewer()
                self.ngLayout7Action.setChecked(True)
            elif self.toolbar_layout_combobox.currentText() == '4panel':
                self.ng_workers[s].nglayout = '4panel'
                self.ng_workers[s].initViewer()
                self.ngLayout8Action.setChecked(True)
            self.refreshNeuroglancerURL()
        except:
            logger.warning('Cannot Change Neuroglancer Layout At This Time')


    @Slot()
    def change_scale(self, scale_key: str):
        try:
            cfg.data['data']['current_scale'] = scale_key
            self.read_project_data_update_gui()
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


    # def rename_file_dialog(self):
    #     self.setMinimumSize(QSize(320, 140))
    #     self.setWindowTitle("PyQt Line Edit example (textfield) - pythonprogramminglanguage.com")
    #
    #     self.nameLabel = QLabel(self)
    #     self.nameLabel.setText('Name:')
    #     self.line = QLineEdit(self)
    #
    #     self.line.move(80, 20)
    #     self.line.resize(200, 32)
    #     self.nameLabel.move(20, 20)
    #
    #     pybutton = QPushButton('OK', self)
    #     pybutton.clicked.connect(self.clickMethod)
    #     pybutton.resize(200, 32)
    #     pybutton.move(80, 60)


    def show_warning(self, title, text):
        QMessageBox.warning(None, title, text)


    def new_project(self, mendenhall=False):
        logger.critical('Starting A New Project...')
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
        self.clearTextWidgetA()
        self.clearLowLowWidgetB()
        self.clearAffineWidget()
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.shutdownNeuroglancer()
        self.wipe_snr_plot()
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
            logger.info(f"Removing Extant Project Directory '{path_proj}'...")
            shutil.rmtree(path_proj)
            logger.info(f"Removing Extant Project File '{path_proj}'...")
            shutil.rmtree(filename)

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

            recipe_dialog = ConfigDialog(parent=self)
            recipe_dialog.exec()
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
            logger.info('<<<< New Project <<<<')


    def open_project(self):
        logger.critical('Opening Project...')
        filename = open_project_dialog()
        logger.info('filename: %s' % filename)
        if filename == '':
            self.hud.post("No Project File Selected (.proj), dialog returned empty string...", logging.WARNING); return
        if filename == None:
            self.hud.post('No Project File Selected (.proj)', logging.WARNING); return
        if os.path.isdir(filename):
            self.hud.post("Selected Path Is A Directory.", logging.WARNING); return
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.shutdownNeuroglancer()
        self.clearLowLowWidgetB()
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
        if cfg.data.is_mendenhall():
            self.setWindowTitle("Project: %s (Mendenhall Protocol0" % os.path.basename(cfg.data.dest()))
            # self.expand_viewer_size()
            # return
        cfg.data.list_aligned = get_aligned_scales()
        cfg.data.naligned = len(cfg.data.list_aligned)
        cfg.data.nscales = len(cfg.data.scales())
        self._scales_combobox_switch = 0
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.read_project_data_update_gui()
        self.setWindowTitle("Project: %s" % os.path.basename(cfg.data.dest()))
        self.updateStatusTips()
        self.reload_scales_combobox()
        self.updateEnabledButtons()
        self.enableGlobalButtons()
        self.updateJumpValidator()
        self.updateHistoryListWidget()
        self.project_model.load(cfg.data.to_dict())
        self.updateBanner()
        self.initSnrPlot()
        self.showScoreboardWidegts()
        self.updateLowLowWidgetB()
        self.initOverviewPanel()
        self.ng_workers = dict.fromkeys(cfg.data.scales())
        # self.initNgServer(scales=cfg.data.scales())
        self._scales_combobox_switch = 1
        # self.toolbar_scale_combobox.setCurrentIndex(self.toolbar_scale_combobox.count() - 1)
        self.toolbar_scale_combobox.setCurrentText(cfg.data.scale())
        ng_layouts = ['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d']
        self.toolbar_layout_combobox.clear()
        self.toolbar_layout_combobox.addItems(ng_layouts)
        self.align_all_button.setText('Align All\n%s' % cfg.data.scale_pretty())
        if launch_servers:
            if cfg.SIMULTANEOUS_SERVERS:
                self.initNgViewer(scales=cfg.data.scales())
            else:
                self.initNgServer(scales=[cfg.data.scale()])
        QApplication.processEvents()



    def rescale(self):
        if not cfg.data:
            self.hud.post('No data yet!', logging.WARNING);
            return
        dlg = AskContinueDialog(title='Confirm Rescale', msg='Warning: Rescaling resets project data.\n'
                                                             'Progress will be lost.  Continue?')
        if not dlg.exec(): logger.info('Rescale Canceled'); return
        logger.info('Clobbering project JSON file...')
        try:
            os.remove(cfg.data.dest() + '.proj')
        except OSError:
            pass

        self.initView()
        self.shutdownNeuroglancer()
        self.wipe_snr_plot()
        self.clearLowLowWidgetB()
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

        recipe_dialog = ConfigDialog(parent=self)
        recipe_dialog.exec()
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

    # def move_project(self):
    #     self.set_status("Moving Project")
    #     dir = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
    #     dest_orig = Path(cfg.data.dest())
    #     filename = self.save_project_dialog()
    #     dest_new = Path(filename).parents[0]
    #     import shutil
    #     dest = shutil.move(dest_orig, dest_new)

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
        if inspect.stack()[1].function == 'read_project_data_update_gui':
            return
        self._unsaved_changes = True


    def ng_toggle_show_ui_controls(self):
        if self.ngShowUiControlsAction.isChecked():
            cfg.SHOW_UI_CONTROLS = True
            self.ngShowUiControlsAction.setText('Show UI Controls')
        else:
            cfg.SHOW_UI_CONTROLS = False
            self.ngShowUiControlsAction.setText('Hide UI Controls')
        # self.initNgServer(scales=[cfg.data.scale()])
        self.initNgViewer(scales=cfg.data.scales())


    def import_images(self, clear_role=False):
        ''' Import images into data '''
        logger.critical('Importing Images...')
        self.hud.post('Select Images To Import:')
        role = 'base'
        try:
            filenames = natural_sort(import_images_dialog())
        except:
            logger.warning('No images were selected.')
            return

        cfg.data.set_source_path(os.path.dirname(filenames[0])) #Critical!
        logger.debug('filenames = %s' % str(filenames))
        if clear_role:
            for layer in cfg.data.alstack():
                if role in layer['images'].keys():  layer['images'].pop(role)

        if filenames != None:
            if len(filenames) > 0:
                self.hud.post('Importing Selected Images...')
                logger.debug("Selected Files: " + str(filenames))
                for i, f in enumerate(filenames):
                    logger.debug("Role " + str(role) + ", Importing file: " + str(f))
                    if f is None:
                        cfg.data.append_empty(role)
                    else:
                        cfg.data.append_image(f, role)


        if are_images_imported():
            self.hud.post('%d Images Imported Successfully' % len(filenames))
            img_size = cfg.data.image_size(s='scale_1')
            cfg.data.link_all_stacks()
            self.hud.post(f'Full Scale Image Dimensions: {img_size[0]}x{img_size[1]} pixels')
            '''Todo save the image dimensions in project dictionary for quick lookup later'''
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)
        self.save_project_to_file() #1123+
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

        try:
            logger.info('Shutting down jupyter...')
            self.shutdownJupyter()
        except:
            sys.stdout.flush()
            logger.info('Having trouble shutting down jupyter')
        else:
            logger.info('Success')

        # try:
        #     if neuroglancer.server.is_server_running():
        #         logger.info('Stopping Neuroglancer SimpleHTTPServer...')
        #         neuroglancer.server.stop()
        # except:
        #     sys.stdout.flush()
        #     logger.warning('Having trouble shutting down neuroglancer')
        # else:
        #     logger.info('Success')

        try:
            logger.info('Shutting down threadpool...')
            threadpool_result = self.threadpool.waitForDone(msecs=500)
        except:
            logger.warning('Having trouble shutting down threadpool')
        else:
            logger.info('Success')

        logger.info('Quitting app...')
        self.app.quit()


    def html_view(self):
        app_root = self.get_application_root()
        html_f = os.path.join(app_root, 'src', 'resources', 'someHTML.html')
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
        self.ng_browser.setUrl(QUrl(text))


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
            logger.warning('Stopping Neuroglancer')
            ng.server.stop()


    def invalidate_all(self, s=None):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        if s == None: s = cfg.data.scale()
        if cfg.data.is_mendenhall():
            self.ng_workers['scale_1'].menLV.invalidate()
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
        if not cfg.NO_EMBED_NG:
            self.ng_browser.setUrl(QUrl(self.ng_workers[s].url()))
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
            try:
                logger.info('Garbage collecting Ng viewers...')
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
            logger.warning('Nothing To View'); return

        if not scales:
            # scales = [cfg.data.scale()]
            if cfg.SIMULTANEOUS_SERVERS:
                scales = cfg.data.scales()
            else:
                scales = [cfg.data.scale()]
        logger.debug('Initializing Neuroglancer Servers For %s...' % ', '.join(scales))
        self.hud.post('Starting Neuroglancer Worker(s)...')
        self.set_status('Starting Neuroglancer...')
        # self.ng_workers = {}
        try:
            for s in scales:
                try:
                    mp_mode = self.ng_workers[s].mp_mode
                except:
                    mp_mode = False
                # logger.info('Deleting Viewer for %s...' % s)
                try:
                    del self.ng_workers[s]
                except:
                    pass
                logger.debug('Launching NG Server for %s...' % s)

                # is_aligned = is_arg_scale_aligned(s)

                # logger.info('%s is aligned? %s' % (s, is_aligned))
                # if is_aligned:
                #     self.ng_browser_2.show()
                #     QApplication.processEvents()
                #     self.ng_workers[s] = {}
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
                #     self.ng_workers[s]['originals'] = NgHost(src=cfg.data.dest(), scale=s)
                #     self.threadpool.start(self.ng_workers[s]['originals'])
                #     self.ng_workers[s]['originals'].initViewer(layout='column', views=['ref','base'], show_ui_controls=False, show_panel_borders=False, w=left_w, h=left_h)
                #
                #     self.ng_workers[s]['aligned'] = NgHost(src=cfg.data.dest(), scale=s)
                #     self.threadpool.start(self.ng_workers[s]['aligned'])
                #     self.ng_workers[s]['aligned'].initViewer(layout='column', views=['aligned'], show_ui_controls=True, show_panel_borders=True, w=right_w, h=right_h)
                #
                #     self.ng_workers[s]['originals'].signals.stateChanged.connect(lambda l: self.read_project_data_update_gui(ng_layer=l))
                #     self.ng_workers[s]['aligned'].signals.stateChanged.connect(lambda l: self.read_project_data_update_gui(ng_layer=l))
                #     self.ng_workers[s]['originals'].signals.stateChanged.connect(lambda l: self.update_viewer_aligned(ng_layer=l))
                #     self.ng_workers[s]['aligned'].signals.stateChanged.connect(lambda l: self.update_viewer_originals(ng_layer=l))
                #
                #     self.ng_browser_2.setFocus()
                # else:
                #     # self.ng_browser_2.hide()
                #     # QApplication.processEvents()

                # self.ng_workers[s] = None

                widget_size = self.image_panel_stack_widget.geometry().getRect()
                self.ng_workers[s] = NgHost(src=cfg.data.dest(), scale=s)
                self.threadpool.start(self.ng_workers[s])
                self.ng_workers[s].initViewer(widget_size=widget_size, matchpoint=mp_mode)
                self.ng_workers[s].signals.stateChanged.connect(lambda l: self.read_project_data_update_gui(ng_layer=l))
                self.refreshNeuroglancerURL(s=s)  # Important
            # self.refreshNeuroglancerURL() #Important
            self.toolbar_layout_combobox.setCurrentText('xy')
            self.toolbar_layout_combobox.currentTextChanged.connect(self.fn_ng_layout_combobox)
        except:
            print_exception()
        finally:
            self.hud.done()
            self.image_panel_stack_widget.setCurrentIndex(1)
            self.set_idle()


    def initShortcuts(self):
        logger.info('')
        '''Initialize Shortcuts'''
        # logger.info('')
        events = (
            (QKeySequence.MoveToPreviousChar, self.scale_down),
            (QKeySequence.MoveToNextChar, self.scale_up)
        )
        for event, action in events:
            QShortcut(event, self, action)


    def initNgViewer(self, scales=None, matchpoint=None):
        # logger.critical(f'caller: {inspect.stack()[1].function}')
        if cfg.data:
            if ng.is_server_running():
                if scales == None: scales = [cfg.data.scale()]
                for s in scales:
                    if matchpoint != None:
                        self.ng_workers[s].initViewer(matchpoint=matchpoint)
                    else:
                        self.ng_workers[s].initViewer()
                    self.refreshNeuroglancerURL(s=s)
            else:
                logger.warning('Neuroglancer is not running')
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

    def print_ng_state_url(self):
        if cfg.data:
            if ng.is_server_running():
                try:     self.ng_workers[cfg.data.scale()].show_state()
                except:  print_exception()
            else:
                self.hud.post('Neuroglancer is not running.')


    def print_ng_state(self):
        if cfg.data:
            if ng.is_server_running():
                try:     self.hud.post('\nViewer State:\n%s' % str(self.ng_workers[cfg.data.scale()].viewer.state))
                except:  print_exception()
            else:
                self.hud.post('Neuroglancer is not running')


    def print_ng_raw_state(self):
        if cfg.data:
            if ng.is_server_running():
                try:
                    self.hud.post('\nRaw State:\n%s' % str(self.ng_workers[cfg.data.scale()].config_state.raw_state))
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
            v = self.ng_workers[cfg.data.s()].viewer
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
            logger.info('Showing configure project dialog...')
            recipe_dialog = ConfigDialog(parent=self)
            result = recipe_dialog.exec_()
            if not result:  logger.warning('Dialog Did Not Return A Result')


    def view_k_img(self):
        if cfg.data:
            self.w = KImageWindow(parent=self)
            self.w.show()


    def bounding_rect_changed_callback(self, state):
        if cfg.data:
            if inspect.stack()[1].function == 'read_project_data_update_gui': return
            if state:
                self.hud.post('Bounding Box is ON. Warning: Dimensions may grow larger than the original images.')
                cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
            else:
                self.hud.post('Bounding Box is OFF (faster). Dimensions will equal the original images.')
                cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def skip_changed_callback(self, state:int):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        caller = inspect.stack()[1].function
        logger.info(caller)
        if cfg.data:
            # caller is 'main' when user is toggler
            if inspect.stack()[1].function == 'read_project_data_update_gui': return
            skip_state = self.toggle_skip.isChecked()
            logger.info(f'skip state: {skip_state}')
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
            self.read_project_data_update_gui()
            self.updateLowLowWidgetB()
            logger.info(f'skip state: {skip_state}')

    def updateOverview(self):
        selected_indexes = self.layer_view_widget.table_widget.selectedIndexes()
        # self.layer_view_widget.table_widget.set



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
                self.force_hide_expandable_widgets()
                # self.low_low_widget.hide()
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

                self.updateLowLowWidgetB()
                self.initView()
                self.initNgViewer(matchpoint=False)
                # self.initNgServer()


    def update_match_point_snr(self):
        self.matchpoint_text_snr.setHtml(f'<h4>{cfg.data.snr()}</h4>')


    def clear_match_points(self):
        logger.info('Clearing Match Points...')
        cfg.data.clear_match_points()
        self.updateLowLowWidgetB()
        # self.image_panel.update_multi_self()


    def print_all_matchpoints(self):
        cfg.data.print_all_matchpoints()


    def show_all_matchpoints(self):
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
        self.updateLowLowWidgetB()


    def show_run_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.hud.post('\n\nWorking Directory     : %s\n'
                      'Running In (__file__) : %s' % (os.getcwd(), os.path.dirname(os.path.realpath(__file__))))


    def show_module_search_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.hud.post('\n\n' + '\n'.join(sys.path))


    def show_snr_list(self) -> None:
        s = cfg.data.scale_val()
        lst = ' | '.join(map(str, cfg.data.snr_list()))
        self.hud.post('\n\nSNR List for Scale %d:\n%s\n' % (s, lst.split(' | ')))


    def show_zarr_info(self) -> None:
        z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
        self.hud.post('\n' + str(z.tree()) + '\n' + str(z.info))


    def show_zarr_info_aligned(self) -> None:
        z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
        self.hud.post('\n' + str(z.info) + '\n' + str(z.tree()))


    def show_zarr_info_source(self) -> None:
        z = zarr.open(os.path.join(cfg.data.dest(), 'img_src.zarr'))
        self.hud.post('\n' + str(z.info) + '\n' + str(z.tree()))


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
        op.setOpacity(val)  # 0 to 1 will cause the fade effect to kick in
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
        self.toolbar.setObjectName('toolbar')
        self.addToolBar(self.toolbar)

        self.action_new_project = QAction('New Project', self)
        self.action_new_project.setStatusTip('New Project')
        self.action_new_project.triggered.connect(self.new_project)
        self.action_new_project.setIcon(qta.icon('fa.plus', color=ICON_COLOR))
        self.toolbar.addAction(self.action_new_project)

        self.action_open_project = QAction('Open Project', self)
        self.action_open_project.setStatusTip('Open Project')
        self.action_open_project.triggered.connect(self.open_project)
        self.action_open_project.setIcon(qta.icon('fa.folder-open', color=ICON_COLOR))
        self.toolbar.addAction(self.action_open_project)

        self.action_save_project = QAction('Save Project', self)
        self.action_save_project.setStatusTip('Save Project')
        self.action_save_project.triggered.connect(self.save_project)
        self.action_save_project.setIcon(qta.icon('mdi.content-save', color=ICON_COLOR))
        self.toolbar.addAction(self.action_save_project)

        self.layoutOneAction = QAction('Column Layout', self)
        self.layoutOneAction.setStatusTip('Column Layout')
        self.layoutOneAction.triggered.connect(self.set_viewer_layout_1)
        self.layoutOneAction.setIcon(qta.icon('mdi.view-column-outline', color=ICON_COLOR))
        self.toolbar.addAction(self.layoutOneAction)

        self.layoutTwoAction = QAction('Row Layout', self)
        self.layoutTwoAction.setStatusTip('Row Layout')
        self.layoutTwoAction.triggered.connect(self.set_viewer_layout_2)
        self.layoutTwoAction.setIcon(qta.icon('mdi.view-stream-outline', color=ICON_COLOR))
        self.toolbar.addAction(self.layoutTwoAction)

        self.expandViewAction = QAction('Expand Neuroglancer to Full Window', self)
        self.expandViewAction.setStatusTip('Expand')
        self.expandViewAction.triggered.connect(self.expand_viewer_size)
        self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))
        self.toolbar.addAction(self.expandViewAction)

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

        std_height = int(22)
        std_width = int(96)
        std_button_size = QSize(std_width, std_height)
        std_input_size = int(46)

        tip = 'Jump To Image #'
        self.toolbar_layer_label = QLabel('Layer #: ')
        self.toolbar_layer_label.setObjectName('toolbar_layer_label')
        self.toolbar_jump_input = QLineEdit(self)
        self.toolbar_jump_input.setFocusPolicy(Qt.ClickFocus)
        self.toolbar_jump_input.setStatusTip(tip)
        self.toolbar_jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.toolbar_jump_input.setFixedSize(std_input_size, std_height)
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
        self.toolbar_layout_combobox.setFixedSize(QSize(76, std_height))
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
        self.toolbar_scale_combobox.setFixedSize(std_button_size)
        self.toolbar_scale_combobox.currentTextChanged.connect(self.fn_scales_combobox)
        self.toolbar_scale_hlayout = QHBoxLayout()
        self.toolbar_scale_hlayout.addWidget(self.toolbar_scale_label)
        self.toolbar_scale_hlayout.addWidget(self.toolbar_scale_combobox, alignment=Qt.AlignmentFlag.AlignRight)
        self.toolbar_scale_widget = QWidget()
        self.toolbar_scale_widget.setLayout(self.toolbar_scale_hlayout)
        self.toolbar.addWidget(self.toolbar_scale_widget)

        tip = 'Show Neuroglancer key bindings'
        self.info_button = QLabel('')
        self.info_button = QPushButton()
        self.info_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.info_button.setStatusTip(tip)
        self.info_button.clicked.connect(self.html_keyboard_commands)
        self.info_button.setFixedSize(std_height, std_height)
        self.info_button.setIcon(qta.icon("fa.info", color=cfg.ICON_COLOR))

        self.toolbar.addWidget(self.info_button)


    def updateStatusTips(self):
        self.regenerate_button.setStatusTip('Generate All Layers,  Scale %d (alters Corrective Bias '
                                            'and Bounding Rectangle)' % get_scale_val(cfg.data.scale()))
        self.align_forward_button.setStatusTip(
            'Align + Generate Layers %d -> End,  Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.scale())))
        self.align_all_button.setStatusTip('Generate + Align All Layers,  Scale %d' % get_scale_val(cfg.data.scale()))
        self.align_one_button.setStatusTip(
            'Align + Generate Layer %d,  Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.scale())))


    def main_tab_changed(self, index:int):
        if index == 0:
            self.initNgViewer()
        if index == 1:
            if cfg.data:
                self.layer_view_widget.set_data()

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
        #         scale_key=scale,
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
        logger.info('')
        '''Initialize Menu'''
        # logger.info('')
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

        fileMenu = self.menu.addMenu('File')

        self.newAction = QAction('&New', self)
        self.newAction.triggered.connect(self.new_project)
        self.newAction.setShortcut('Ctrl+N')
        fileMenu.addAction(self.newAction)

        self.openAction = QAction('&Open...', self)
        self.openAction.triggered.connect(self.open_project)
        self.openAction.setShortcut('Ctrl+O')
        fileMenu.addAction(self.openAction)

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

        self.expandViewerAction = QAction('Neuroglancer', self)
        self.expandViewerAction.triggered.connect(self.expand_viewer_size)
        expandMenu.addAction(self.expandViewerAction)

        self.expandPythonAction = QAction('Python Console', self)
        self.expandPythonAction.triggered.connect(self.expand_python_size)
        expandMenu.addAction(self.expandPythonAction)

        self.expandPlotAction = QAction('SNR Plot', self)
        self.expandPlotAction.triggered.connect(self.expand_plot_size)
        expandMenu.addAction(self.expandPlotAction)

        self.expandTreeviewAction = QAction('Project Treeview', self)
        self.expandTreeviewAction.triggered.connect(self.expand_treeview_size)
        expandMenu.addAction(self.expandTreeviewAction)

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

        self.ngShowStateUrlAction = QAction('URL', self)
        self.ngShowStateUrlAction.triggered.connect(self.print_ng_state_url)
        ngStateMenu.addAction(self.ngShowStateUrlAction)

        self.ngShowRawStateAction = QAction('URL', self)
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

        self.projectConfigAction = QAction('Project Configuration', self)
        self.projectConfigAction.triggered.connect(self.configure_project)
        toolsMenu.addAction(self.projectConfigAction)

        self.jumpWorstSnrAction = QAction('Jump To Next Worst SNR', self)
        self.jumpWorstSnrAction.triggered.connect(self.jump_to_worst_snr)
        toolsMenu.addAction(self.jumpWorstSnrAction)

        self.jumpBestSnrAction = QAction('Jump To Next Best SNR', self)
        self.jumpBestSnrAction.triggered.connect(self.jump_to_best_snr)
        toolsMenu.addAction(self.jumpBestSnrAction)

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

        self.detailsWebglAction = QAction('Web GL Configuration', self)
        self.detailsWebglAction.triggered.connect(self.webgl2_test)
        detailsMenu.addAction(self.detailsWebglAction)

        self.detailsGpuAction = QAction('GPU Configuration', self)
        self.detailsGpuAction.triggered.connect(self.gpu_config)
        detailsMenu.addAction(self.detailsGpuAction)

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


        helpMenu = self.menu.addMenu('Help')

        self.documentationAction = QAction('Documentation', self)
        self.documentationAction.triggered.connect(self.documentation_view)
        helpMenu.addAction(self.documentationAction)

        self.keyboardCommandsAction = QAction('Keyboard Commands', self)
        self.keyboardCommandsAction.triggered.connect(self.html_keyboard_commands)
        self.keyboardCommandsAction.setShortcut('Ctrl+H')
        helpMenu.addAction(self.keyboardCommandsAction)

        swiftirMenu = helpMenu.addMenu('SWiFT-IR')

        self.swiftirComponentsAction = QAction('SWiFT-IR Components', self)
        self.swiftirComponentsAction.triggered.connect(self.html_view)
        swiftirMenu.addAction(self.swiftirComponentsAction)

        self.swiftirCommandsAction = QAction('SWiFT-IR Commands', self)
        self.swiftirCommandsAction.triggered.connect(self.view_swiftir_commands)
        swiftirMenu.addAction(self.swiftirCommandsAction)

        self.swiftirExamplesAction = QAction('SWiFT-IR Examples', self)
        self.swiftirExamplesAction.triggered.connect(self.view_swiftir_examples)
        swiftirMenu.addAction(self.swiftirExamplesAction)

        self.restartPythonKernelAction = QAction('Restart Python Kernel', self)
        self.restartPythonKernelAction.triggered.connect(self.restart_python_kernel)
        helpMenu.addAction(self.restartPythonKernelAction)

        self.reloadBrowserAction = QAction('Reload QtWebEngine', self)
        self.reloadBrowserAction.triggered.connect(self.browser_reload)
        helpMenu.addAction(self.reloadBrowserAction)


    #@timer
    def initUI(self):
        logger.info('')
        '''Initialize Main UI'''
        # logger.info('')
        std_height = int(22)
        std_width = int(96)
        std_button_size = QSize(std_width, std_height)
        normal_button_width = int(68)
        normal_button_height = int(30)
        normal_button_size = QSize(normal_button_width, normal_button_height)
        slim_button_height = int(22)
        slim_button_size = QSize(normal_button_width, slim_button_height)
        small_button_width = int(48)
        small_button_size = QSize(small_button_width, slim_button_height)
        std_input_size = int(46)
        small_input_size = int(36)
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

        '''GroupBox 1 Project'''

        self.hud = HeadupDisplay(self.app)
        self.hud.setObjectName('hud')
        self.hud.post('Welcome To AlignEM-SWiFT.')

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
        # self.toggle_skip = ToggleSwitch()
        self.toggle_skip = QCheckBox()
        self.toggle_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_skip.setObjectName('toggle_skip')
        self.toggle_skip.stateChanged.connect(self.skip_changed_callback)
        self.toggle_skip.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_skip.setStatusTip(tip)
        self.toggle_skip.setEnabled(False)

        self.skip_layout = QHBoxLayout()
        self.skip_layout.addWidget(self.skip_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.skip_layout.addWidget(self.toggle_skip, alignment=Qt.AlignmentFlag.AlignLeft)
        self.skip_layout.addWidget(self.clear_skips_button)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        self.whitening_label = QLabel("Whitening\nFactor:")
        self.whitening_label.setStyleSheet("font-size: 11px;")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.textEdited.connect(self.has_unsaved_changes)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(std_input_size + 20)  # 0829
        self.whitening_input.setFixedHeight(std_height)
        self.whitening_input.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        self.whitening_label.setStatusTip(tip)
        self.whitening_input.setStatusTip(tip)
        self.whitening_grid = QGridLayout()
        self.whitening_grid.addWidget(self.whitening_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.whitening_input.setEnabled(False)

        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        self.swim_label = QLabel("SWIM Window\n(% size):")
        self.swim_label.setStyleSheet("font-size: 11px;")
        self.swim_input = QLineEdit(self)
        self.swim_input.textEdited.connect(self.has_unsaved_changes)
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(std_input_size + 20)
        self.swim_input.setFixedHeight(std_height)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        self.swim_label.setStatusTip(tip)
        self.swim_input.setStatusTip(tip)
        self.swim_grid = QGridLayout()
        self.swim_grid.addWidget(self.swim_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.swim_input.setEnabled(False)

        # tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        self.apply_all_button = QPushButton("Apply All")
        self.apply_all_button.setEnabled(False)
        self.apply_all_button.setStatusTip('Apply These Settings To The Entire Project')
        self.apply_all_button.setStyleSheet("font-size: 10px;")
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_button.clicked.connect(self.apply_all)
        self.apply_all_button.setFixedSize(slim_button_size)

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
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.poly_order_hlayout.addWidget(self.bias_bool_combo, alignment=Qt.AlignmentFlag.AlignLeft)

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
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_bounding_rect.setEnabled(False)

        tip = "Recomputes the cumulative affine and generates new aligned images" \
              "based on the current Null Bias and Bounding Rectangle presets."
        self.regenerate_button = QPushButton('Regenerate')
        self.regenerate_button.setEnabled(False)
        self.regenerate_button.setStatusTip(tip)
        self.regenerate_button.clicked.connect(lambda: self.regenerate(scale=cfg.data.scale()))
        self.regenerate_button.setFixedSize(normal_button_size)
        self.regenerate_button.setStyleSheet("font-size: 10px;")

        self.new_control_panel = QWidget()
        self.new_control_panel.setFixedHeight(40)
        self.new_control_panel_layout = QHBoxLayout()
        self.new_control_panel_layout.addStretch()
        self.new_control_panel_layout.addLayout(self.skip_layout)
        self.new_control_panel_layout.addLayout(self.swim_grid)
        self.new_control_panel_layout.addLayout(self.whitening_grid)
        self.new_control_panel_layout.addWidget(self.apply_all_button)
        self.new_control_panel_layout.addWidget(self.scale_ctrl_label)
        self.new_control_panel_layout.addLayout(self.scale_ctrl_layout)
        self.new_control_panel_layout.addLayout(self.poly_order_hlayout)
        self.new_control_panel_layout.addLayout(self.toggle_bounding_hlayout)
        self.new_control_panel_layout.addWidget(self.regenerate_button)
        self.new_control_panel_layout.addWidget(self.align_one_button)
        self.new_control_panel_layout.addWidget(self.align_forward_button)
        self.new_control_panel_layout.addWidget(self.align_all_button)
        self.new_control_panel_layout.addStretch()
        self.new_control_panel.setLayout(self.new_control_panel_layout)

        self.main_details_subwidgetA = QTextEdit()
        self.main_details_subwidgetB = QTextEdit()
        self.main_details_subwidgetA.setReadOnly(True)
        self.main_details_subwidgetB.setReadOnly(True)
        self.main_details_subwidgetA.setObjectName('main_details_subwidgetA')
        self.main_details_subwidgetB.setObjectName('main_details_subwidgetB')

        self.history_widget = QWidget()
        self.history_widget.setObjectName('history_widget')
        self.historyListWidget = QListWidget()
        self.historyListWidget.setObjectName('historyListWidget')
        self.historyListWidget.installEventFilter(self)
        self.historyListWidget.itemClicked.connect(self.historyItemClicked)
        self.history_layout = QVBoxLayout()
        self.history_label = QLabel('<b>Saved Alignments</b>')
        self.history_label.setStyleSheet("font-size: 10px;")
        self.history_layout.addWidget(self.history_label)
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

        self.afm_widget = QTextEdit()
        self.afm_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.afm_widget.setObjectName('afm_widget')
        self.afm_widget.setReadOnly(True)

        '''SNR Plot & Controls'''
        self.snr_plot_and_control = QWidget()
        self.snr_plot = SnrPlot()
        self.snr_plot_controls_hlayout = QHBoxLayout()
        self.snr_plot_and_control_layout = QVBoxLayout()
        self.snr_plot_and_control_layout.addLayout(self.snr_plot_controls_hlayout)
        self.snr_plot_and_control_layout.addWidget(self.snr_plot)
        self.snr_plot_and_control_layout.setContentsMargins(8, 4, 8, 4)
        self.snr_plot_and_control.setLayout(self.snr_plot_and_control_layout)
        self.snr_plot_and_control.setAutoFillBackground(False)

        '''Neuroglancer Controls'''
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(std_button_size)
        self.reload_ng_button.clicked.connect(self.refreshNeuroglancerURL)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(std_button_size)
        self.print_state_ng_button.clicked.connect(self.print_ng_state_url)

        self.browser = QWebEngineView()
        self.ng_browser_container = QWidget()
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
        # self.ng_browser_layout.addWidget(self.browser_overlay_label, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.ng_browser_layout.addWidget(self.browser_overlay_label, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.ng_browser_container.setLayout(self.ng_browser_layout)
        self.ng_browser.setFocusPolicy(Qt.StrongFocus)
        # self.ng_browser.installEventFilter(self)

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
        self.ng_panel_layout.addWidget(self.ng_browser_container)
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

        self.layer_view_widget = LayerViewWidget()
        self.layer_view_widget.setObjectName('layer_view_widget')

        self.main_tab_widget = QTabWidget()
        self.main_tab_widget.setObjectName('main_tab_widget')
        self.main_tab_widget.addTab(self.image_panel_stack_widget, 'Neuroglancer')
        self.main_tab_widget.addTab(self.layer_view_widget, 'Overview')
        self.main_tab_widget.currentChanged.connect(self.main_tab_changed)

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
        self.projectdata_treeview_widget.setLayout(self.projectdata_treeview_layout)
        self.projectdata_treeview_layout.addWidget(self.projectdata_treeview)

        '''Show/Hide Primary Tools Buttons'''
        show_hide_button_sizes = QSize(normal_button_width + 32, 18)

        tip = 'Show/Hide Alignment Controls'
        self.show_hide_controls_button = QPushButton('Hide Controls')
        self.show_hide_controls_button.setObjectName('show_hide_controls_button')
        self.show_hide_controls_button.setStyleSheet(lower_controls_style)
        self.show_hide_controls_button.setStatusTip(tip)
        self.show_hide_controls_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_controls_button.clicked.connect(self.show_hide_controls_callback)
        self.show_hide_controls_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_controls_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide SNR Plot'
        self.show_hide_snr_plot_button = QPushButton('Hide SNR Plot')
        self.show_hide_snr_plot_button.setObjectName('show_hide_snr_plot_button')
        self.show_hide_snr_plot_button.setStyleSheet(lower_controls_style)
        self.show_hide_snr_plot_button.setStatusTip(tip)
        self.show_hide_snr_plot_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_snr_plot_button.clicked.connect(self.show_hide_snr_plot_callback)
        self.show_hide_snr_plot_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_snr_plot_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Head-Up Display (HUD)'
        self.show_hide_hud_button = QPushButton()
        self.show_hide_hud_button.setObjectName('show_hide_hud_button')
        self.show_hide_hud_button.setStyleSheet(lower_controls_style)
        self.show_hide_hud_button.setStatusTip(tip)
        self.show_hide_hud_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_hud_button.clicked.connect(self.show_hide_hud_callback)
        self.show_hide_hud_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_hud_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Python Console'
        self.show_hide_python_button = QPushButton()
        self.show_hide_python_button.setObjectName('show_hide_python_button')
        self.show_hide_python_button.setStyleSheet(lower_controls_style)
        self.show_hide_python_button.setStatusTip(tip)
        self.show_hide_python_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_python_button.clicked.connect(self.show_hide_python_callback)
        self.show_hide_python_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_python_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        # tip = 'Go To Project Overview'
        # self.show_hide_overview_button = QPushButton('Overview')
        # self.show_hide_overview_button.setObjectName('show_hide_overview_button')
        # self.show_hide_overview_button.setStyleSheet(lower_controls_style)
        # self.show_hide_overview_button.setStatusTip(tip)
        # self.show_hide_overview_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.show_hide_overview_button.clicked.connect(self.go_to_overview_callback)
        # self.show_hide_overview_button.setFixedSize(show_hide_button_sizes)
        # # self.show_hide_overview_button.setIcon(qta.icon('fa.table', color='#f3f6fb'))

        tip = 'Show/Hide Project Treeview'
        self.show_hide_project_tree_button = QPushButton('Hide Tools')
        self.show_hide_project_tree_button.setObjectName('show_hide_project_tree_button')
        self.show_hide_project_tree_button.setStyleSheet(lower_controls_style)
        self.show_hide_project_tree_button.setStatusTip(tip)
        self.show_hide_project_tree_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_project_tree_button.clicked.connect(self.show_hide_project_tree_callback)
        self.show_hide_project_tree_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_project_tree_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))


        '''Main Splitter'''
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(self.main_tab_widget)
        self.main_splitter.addWidget(self.new_control_panel)
        self.main_splitter.addWidget(self.hud)
        self.main_splitter.addWidget(self.snr_plot_and_control)
        self.main_splitter.addWidget(self.matchpoint_controls)
        self.main_splitter.addWidget(self.projectdata_treeview_widget)
        self.main_splitter.addWidget(self.python_console)
        self.main_splitter.setHandleWidth(0)
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)
        self.main_splitter.setCollapsible(2, False)
        self.main_splitter.setCollapsible(3, False)
        self.main_splitter.setCollapsible(4, False)
        self.main_splitter.setCollapsible(5, False)
        self.main_splitter.setCollapsible(6, False)
        self.main_splitter.setStretchFactor(0,5)
        self.main_splitter.setStretchFactor(1,1)
        self.main_splitter.setStretchFactor(2,1)
        self.main_splitter.setStretchFactor(3,1)
        self.main_splitter.setStretchFactor(4,1)
        self.main_splitter.setStretchFactor(5,1)
        self.main_splitter.setStretchFactor(6,1)

        self.show_hide_main_features_widget = QWidget()
        self.show_hide_main_features_widget.setObjectName('show_hide_main_features_widget')
        self.show_hide_main_features_vlayout = QVBoxLayout()
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_controls_button, alignment=Qt.AlignHCenter)
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_snr_plot_button, alignment=Qt.AlignHCenter)
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_project_tree_button, alignment=Qt.AlignHCenter)
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_python_button, alignment=Qt.AlignHCenter)
        # self.show_hide_main_features_vlayout.addWidget(self.show_hide_overview_button, alignment=Qt.AlignHCenter)
        self.show_hide_main_features_widget.setLayout(self.show_hide_main_features_vlayout)

        self.low_low_widget = QWidget()
        self.low_low_gridlayout = QGridLayout()
        self.low_low_widget.setLayout(self.low_low_gridlayout)
        self.low_low_gridlayout.addWidget(self.main_details_subwidgetA,0,0, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.main_details_subwidgetB,0,1, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.show_hide_main_features_widget,0,2, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.afm_widget,0,3, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.history_widget,0,4, alignment=Qt.AlignCenter)
        self.main_details_subwidgetA.hide()
        self.main_details_subwidgetB.hide()
        self.afm_widget.hide()
        self.history_widget.hide()

        self.new_main_widget = QWidget()
        self.new_main_widget_vlayout = QVBoxLayout()
        self.new_main_widget_vlayout.addWidget(self.main_splitter)
        self.new_main_widget_vlayout.addWidget(self.low_low_widget)
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
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))

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

        self.pbar_container = QWidget()
        self.pbar_layout = QVBoxLayout()
        self.pbar_layout.addWidget(self.pbar)
        self.pbar_container.setLayout(self.pbar_layout)

        self.main_panel = QWidget()
        self.main_panel_layout = QGridLayout()
        self.main_panel_layout.addWidget(self.new_main_widget, 1, 0, 1, 5)
        self.main_panel_layout.addWidget(self.full_window_controls, 2, 0, 1, 5)
        self.main_panel_layout.addWidget(self.pbar_container, 3, 0, 1, 5)

        self.thumbnail_table = QTableView()
        self.thumbnail_table.horizontalHeader().hide()
        self.thumbnail_table.verticalHeader().hide()
        self.thumbnail_table.setGridStyle(Qt.NoPen)

        self.overview_panel = QWidget()
        self.overview_layout = QGridLayout()
        self.overview_layout.addWidget(self.thumbnail_table, 1, 0, 1, 3)

        self.overview_tab_widget = QTabWidget()
        self.overview_tab_widget.addTab(self.overview_panel, 'Overview')

        self.overview_panel.setLayout(self.overview_layout)
        self.overview_panel_title = QLabel('<h1>Project Overview [ Under Construction :) ]</h1>')
        self.overview_back_button = QPushButton("Back")
        self.overview_back_button.setFixedSize(slim_button_size)
        self.overview_back_button.clicked.connect(self.back_callback)
        self.overview_layout.addWidget(self.overview_panel_title, 0, 0, 1, 3)
        self.overview_layout.addWidget(self.overview_back_button, 3, 0, 1, 1)

        self.main_stack_widget = QStackedWidget(self)
        self.main_stack_widget.addWidget(self.main_panel)           # (0) main_panel
        self.main_stack_widget.addWidget(self.docs_panel)           # (1) docs_panel
        self.main_stack_widget.addWidget(self.demos_panel)          # (2) demos_panel
        self.main_stack_widget.addWidget(self.remote_viewer_panel)  # (3) remote_viewer_panel
        self.main_stack_widget.addWidget(self.overview_tab_widget)       # (4) overview_panel

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

    def show_hide_snr_plot(self):
        if self.snr_plot_and_control.isHidden():
            self.snr_plot_and_control.setHidden(False)
        else:
            self.snr_plot_and_control.setHidden(True)
        self.read_project_data_update_gui()

    def show_hide_hud(self):
        if self.hud.isHidden():
            self.hud.setHidden(False)
        else:
            self.hud.setHidden(True)
        self.read_project_data_update_gui()

    def show_hide_python(self):
        if self.python_console.isHidden():
            self.python_console.setHidden(False)
        else:
            self.python_console.setHidden(True)
        self.read_project_data_update_gui()


    def expand_viewer_size(self):
        if self._is_viewer_expanded:
            logger.info('Collapsing Viewer')
            self._is_viewer_expanded = False
            self.initView()
            self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))
            self.expandViewAction.setStatusTip('Set Expanded Viewer Size')

        else:
            logger.info('Expanding Viewer')
            self._is_viewer_expanded = True
            # self.full_window_controls.show()
            self.new_control_panel.hide()
            self.low_low_widget.hide()
            self.hud.hide()
            self.matchpoint_controls.hide()
            self.main_tab_widget.show()
            self.main_tab_widget.setCurrentIndex(0)
            self.image_panel_stack_widget.setCurrentIndex(1)
            self.main_stack_widget.setCurrentIndex(0)
            self.force_hide_expandable_widgets()
            self.expandViewAction.setIcon(qta.icon('mdi.arrow-collapse-all', color=ICON_COLOR))
            self.expandViewAction.setStatusTip('Set Normal Viewer Size')

        if cfg.data:
            self.initNgViewer()

        logger.info('is viewer expanded? %s' % self._is_viewer_expanded)


    def set_viewer_layout_1(self):
        if cfg.data:
            # self._layout = 1
            self.ng_workers[cfg.data.scale()].arrangement = 1
            self.ng_workers[cfg.data.scale()].initViewer()
            self.refreshNeuroglancerURL()
            # self.refreshNeuroglancerURL()
            # self.initNgServer()


    def set_viewer_layout_2(self):
        if cfg.data:
            # self._layout = 2
            self.ng_workers[cfg.data.scale()].arrangement = 2
            self.ng_workers[cfg.data.scale()].initViewer()
            self.refreshNeuroglancerURL()
            # self.refreshNeuroglancerURL()
            # self.initNgServer()


    def expand_plot_size(self):
        self._is_mp_mode = False
        self.full_window_controls.show()
        self.main_stack_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.low_low_widget.hide()
        self.hud.hide()
        self.matchpoint_controls.hide()
        self.main_tab_widget.hide()
        self.force_hide_expandable_widgets()
        self.snr_plot_and_control.show()


    def expand_treeview_size(self):
        self.full_window_controls.show()
        self.extra_header_text_label.setText('')
        self.main_stack_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.low_low_widget.hide()
        self.hud.hide()
        self.matchpoint_controls.hide()
        self.main_tab_widget.hide()
        self.force_hide_expandable_widgets()
        self.projectdata_treeview.show()
        self.projectdata_treeview_widget.show()


    def expand_python_size(self):
        self.full_window_controls.show()
        self.extra_header_text_label.setText('')
        self._is_mp_mode = False
        self.main_stack_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.low_low_widget.hide()
        self.hud.hide()
        self.matchpoint_controls.hide()
        self.main_tab_widget.hide()
        self.force_hide_expandable_widgets()
        self.python_console.show()


    def get_thumbnail_list(self):
        pass


    def initOverviewPanel(self):
        logger.info('')
        preview = namedtuple("preview", "id title image")

        self.previewmodel = PreviewModel()

        self.thumbnails = {}
        self.thumbnail_items = {}
        for n, fn in enumerate(cfg.data.thumbnail_names()):
            thumbnail = QImage(fn)
            self.thumbnails[fn] = QImage(fn)
            # self.thumbnails[n].setText('filename', fn) # key, value
            # self.thumbnails[n].save()
            # item = preview(n, fn, self.thumbnails[fn])
            # item = preview(n, fn, thumbnail)
            self.thumbnail_items[n] = preview(n, fn, thumbnail)
            self.previewmodel.previews.append(self.thumbnail_items[n])
        self.previewmodel.layoutChanged.emit()

        delegate = PreviewDelegate()
        self.thumbnail_table.setItemDelegate(delegate)
        # self.thumbnail_table.setItemDelegateForColumn(1, ThumbnailDelegate())

        # import pandas as pd
        # # df = pd.DataFrame(zip(cfg.data.snr_list(), self.thumbnail_items))
        # df = pd.DataFrame(zip(self.thumbnails, cfg.data.snr_list()))
        # self.pandasmodel = PandasModel(dataframe=df)

        # self.thumbnail_table.setModel(self.pandasmodel)
        self.thumbnail_table.setModel(self.previewmodel)
        # self.generaltabelmodel = GeneralTableModel(self.thumbnail_items)
        # self.thumbnail_table.setModel(self.generaltabelmodel)

        self.thumbnail_table.resizeRowsToContents()
        self.thumbnail_table.resizeColumnsToContents()
        QApplication.processEvents()


    def initWidgetSpacing(self):
        logger.info('')
        self.main_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.main_details_subwidgetA.setContentsMargins(0, 0, 0, 0)
        self.main_details_subwidgetB.setContentsMargins(0, 0, 0, 0)
        self.new_main_widget_vlayout.setContentsMargins(0, 0, 0, 0)
        self.show_hide_main_features_vlayout.setContentsMargins(4, 4, 4, 10)
        self.ng_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.ng_panel_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.ng_browser_layout.setContentsMargins(0, 0, 0, 0)
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.setContentsMargins(0, 0, 0, 0)
        self.swim_grid.setContentsMargins(0, 0, 0, 0)
        self.scale_ctrl_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.toggle_bounding_hlayout.setContentsMargins(0, 0, 0, 0)
        self.new_control_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.full_window_controls_hlayout.setContentsMargins(8, 0, 8, 0)
        self.new_control_panel.setContentsMargins(8, 4, 8, 4)
        self.projectdata_treeview.setContentsMargins(8, 4, 8, 4)
        self.python_console.setContentsMargins(8, 4, 8, 4)
        self.low_low_gridlayout.setContentsMargins(8, 4, 8, 4)
        self.pbar_layout.setContentsMargins(0, 0, 0, 0)

        self.pbar.setFixedHeight(18)
        self.show_hide_main_features_vlayout.setSpacing(4)
        self.show_hide_main_features_widget.setMaximumHeight(80)
        self.low_low_widget.setMaximumHeight(100)
        self.matchpoint_text_snr.setMaximumHeight(20)
        self.main_details_subwidgetA.setMinimumWidth(128)
        self.main_details_subwidgetB.setMinimumWidth(128)
        self.afm_widget.setMinimumWidth(128)
        self.history_widget.setMinimumWidth(128)


    def wipe_snr_plot(self):
        try:
            self.snr_plot.clear()
            self.remove_snr_plot_checkboxes()
        except:
            logger.warning('Cannot clear SNR plot. Does it exist yet?')


    def remove_snr_plot_checkboxes(self):
        for i in reversed(range(self.snr_plot_controls_hlayout.count())):
            self.snr_plot_controls_hlayout.removeItem(self.snr_plot_controls_hlayout.itemAt(i))


    def initSnrPlot(self, s=None):
        logger.info('')
        '''
        cfg.main_window.snr_points.data - numpy.ndarray (snr data points)
        AlignEM [11]: numpy.ndarray
        cfg.main_window.snr_points.data[0]
        AlignEM [13]: (1., 14.73061687, -1., None, None, None, None, None,
          PyQt5.QtCore.QRectF(0.0, 0.0, 8.0, 8.0),
          PyQt5.QtCore.QRectF(57.99999999999997, 60.602795211005855, 8.0, 8.0), 4.)
        '''
        try:
            self.remove_snr_plot_checkboxes()
            self._snr_checkboxes = dict()

            # self._snr_checkboxes = dict()
            for i, s in enumerate(cfg.data.scales()[::-1]):
                self._snr_checkboxes[s] = QCheckBox()
                self._snr_checkboxes[s].setText('s' + str(get_scale_val(s)))
                self.snr_plot_controls_hlayout.addWidget(self._snr_checkboxes[s], alignment=Qt.AlignLeft)
                self._snr_checkboxes[s].setChecked(True)
                # self._snr_checkboxes[s].setStyleSheet('background-color: %s' % self._plot_colors[i]) #-
                self._snr_checkboxes[s].clicked.connect(self.updateSnrPlot)
                self._snr_checkboxes[s].setStatusTip('On/Off SNR Plot Scale %d' % get_scale_val(s))
                if is_arg_scale_aligned(scale=s):
                    self._snr_checkboxes[s].show()
                else:
                    self._snr_checkboxes[s].hide()
            self.snr_plot_controls_hlayout.addStretch()
            self.updateSnrPlot()
        except:
            print_exception()


    def updateSnrPlot(self):
        '''Update SNR plot widget based on checked/unchecked state of checkboxes'''
        # logger.info('Updating SNR Plot...')
        self.snr_plot.clear()
        for i, scale in enumerate(cfg.data.scales()[::-1]):
            if self._snr_checkboxes[scale].isChecked():
                if is_arg_scale_aligned(scale=scale):
                    self.show_snr(scale=scale)
            cfg.data.scales().index(scale)
            color = self._plot_colors[cfg.data.scales().index(scale)]
            self._snr_checkboxes[scale].setStyleSheet('background-color: #F3F6FB;'
                                                      'border-color: %s; '
                                                      'border-width: 2px; '
                                                      'border-style: outset;' % color)
        # max_snr = cfg.data.snr_max_all_scales()
        # if is_any_scale_aligned_and_generated():
        #     try:
        #         if max_snr != None:  self.snr_plot.setLimits(xMin=0, xMax=cfg.data.n_layers(), yMin=0, yMax=max_snr + 1)
        #     except:
        #         logger.warning('updateSnrPlot encountered a problem setting plot limits')


    def show_snr(self, scale=None):
        #Todo This is being called too many times!
        # logger.info('called by %s' % inspect.stack()[1].function)
        if scale == None: scale = cfg.data.scale()
        # logger.info('show_snr (s: %s):' % str(s))
        snr_list = cfg.data.snr_list(scale=scale)
        pg.setConfigOptions(antialias=True)
        x_axis = []
        y_axis = []
        for layer, snr in enumerate(snr_list):
            if not cfg.data.skipped(s=scale, l=layer):
                x_axis.append(layer)
                y_axis.append(snr)
        # x_axis = [x for x in range(0, len(snr_list))]
        brush = self._plot_brushes[cfg.data.scales().index(scale)]
        # color = self._plot_colors[cfg.data.scales().index(s)]
        # self._snr_checkboxes[s].setStyleSheet('border-color: %s' % color)
        self.snr_points = pg.ScatterPlotItem(
            size=7,
            pen=pg.mkPen(None),
            brush=brush,
            hoverable=True,
            # hoverSymbol='s',
            hoverSize=11,
            # hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('#41FF00'),
            # pxMode=False #allow spots to transform with the
        )
        ##41FF00 <- good green color
        self.snr_points.sigClicked.connect(self.onSnrClick)
        self.snr_points.addPoints(x_axis[1:], y_axis[1:])
        # logger.info('self.snr_points.toolTip() = %s' % self.snr_points.toolTip())
        # value = self.snr_points.setToolTip('Test')
        self.last_snr_click = []
        self.snr_plot.addItem(self.snr_points)
        # self.snr_plot.autoRange()

        max_snr = cfg.data.snr_max_all_scales()
        if is_any_scale_aligned_and_generated():
            if max_snr != None:
                self.snr_plot.setLimits(xMin=0, xMax=cfg.data.n_layers(), yMin=0, yMax=max_snr + 1)


    def onSnrClick(self, plot, points):
        '''
        type(obj): <class 'pyqtgraph.graphicsItems.ScatterPlotItem.ScatterPlotItem'>
        type(points): <class 'numpy.ndarray'>
        '''
        index = int(points[0].pos()[0])
        snr = float(points[0].pos()[1])
        self.hud.post(f'Layer: {index}, SNR: {snr}')
        # clickedPen = pg.mkPen({'color': "#f3f6fb", 'width': 3})
        clickedPen = pg.mkPen({'color': "#ffe135", 'width': 3})
        for p in self.last_snr_click:
            # p.resetPen()
            p.resetBrush()
        for p in points:
            p.setBrush(pg.mkBrush('#FF0000'))
            # p.setPen(clickedPen)
        self.last_snr_click = points
        self.jump_to(index)


    #@timer
    def initPbar(self):
        logger.info('')
        # logger.info('')
        self.statusBar = self.statusBar()
        self.statusBar.setFixedHeight(18)
        # self.statusBar = QStatusBar()
        # self.pbar = QProgressBar(self)
        self.pbar = QProgressBar()
        # self.statusBar.addPermanentWidget(self.pbar)
        # self.statusBar.addWidget(self.pbar)
        self.pbar.setAlignment(Qt.AlignCenter)
        # self.pbar.setGeometry(0, 0, 250, 50)
        self.pbar.hide()

    def pbar_max(self, x):
        self.pbar.setMaximum(x)

    def pbar_update(self, x):
        self.pbar.setValue(x)

    def setPbarText(self, text: str):
        self.pbar.setFormat('(%p%) ' + text)


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
        else:
            self.image_panel_stack_widget.setCurrentIndex(2)


    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self.historyListWidget:
            menu = QMenu()
            self.history_view_action = QAction('View')
            self.history_view_action.setStatusTip('View this alignment as a tree view')
            self.history_view_action.triggered.connect(self.view_historical_alignment)
            self.history_swap_action = QAction('Swap')
            self.history_swap_action.setStatusTip('Swap the settings of this historical alignment '
                                                  'with your current scale settings')
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


