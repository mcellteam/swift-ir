#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import copy
import inspect
import json
import logging
import operator
import os
import platform
import sys
import glob
import textwrap
import time
from pathlib import Path
import zarr
import neuroglancer as ng
import neuroglancer.server
import pyqtgraph as pg
import qtawesome as qta
import qtpy
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QDir
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication, QKeySequence, QCursor, QImageReader, QMovie, QImage
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QSpacerItem, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QDialog, QStyle, QCheckBox, QSpinBox, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView

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
from src.helpers import natural_sort, get_snr_average
from src.http_ng_server import NgHost
# from src.utils.PyQtImageStackViewer import QtImageStackViewer
# from src.utils.PyQtImageViewer import QtImageViewer
from src.ui.dialogs import AskContinueDialog, ConfigDialog, QFileDialogPreview
# from src.napari_test import napari_test
from src.ui.headup_display import HeadupDisplay
from src.ui.kimage_window import KImageWindow
from src.ui.python_console import PythonConsole
from src.ui.snr_plot import SnrPlot
from src.ui.toggle_switch import ToggleSwitch
from src.ui.models.json_tree import JsonModel
from src.ui.models.preview import PreviewModel, PreviewDelegate


# MAIN_PANEL_STARTING_INDEX = 4
MAIN_PANEL_STARTING_INDEX = 0

# from src.zarr_funcs import generate_zarr_scales_da

from collections import namedtuple

__all__ = ['MainWindow']

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    resized = Signal()
    keyPressed = Signal(int)

    def __init__(self, data=None):
        QMainWindow.__init__(self)
        logger.info('Initializing Main Window')
        self.app = QApplication.instance()

        # self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)

        window = self.window()
        window.setGeometry(
            QStyle.alignedRect(
                Qt.LeftToRight,
                Qt.AlignCenter,
                window.size(),
                QGuiApplication.primaryScreen().availableGeometry(),
            ),
        )
        self.oldPos = self.pos()
        self.setWindowTitle('AlignEM-SWiFT')
        self.setWindowIcon(QIcon(QPixmap('sims.png')))
        self.init_dir = os.getcwd()
        fg = self.frameGeometry()
        fg.moveCenter(QGuiApplication.primaryScreen().availableGeometry().center())
        self.move(fg.topLeft())
        logger.info("Initializing Thread Pool")
        self.threadpool = QThreadPool(self)  # important consideration is this 'self' reference
        self.threadpool.setExpiryTimeout(3000)  # ms
        # self.ng_workers = None
        # self.ng_workers = {}

        self._snr_by_scale = dict()

        if qtpy.PYSIDE6:
            QImageReader.setAllocationLimit(0)  # PySide6
        elif qtpy.PYQT6:
            os.environ['QT_IMAGEIO_MAXALLOC'] = "1000000000000000"  # PyQt6

        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())

        self.project_progress = None
        self.project_aligned_scales = []
        self.scales_combobox_switch = 1
        self.jump_to_worst_ticker = 1  # begin iter at 1 b/c first image has no ref
        self.jump_to_best_ticker = 0

        logger.info("Initializing Qt WebEngine")
        self.webengineview = QWebEngineView()

        # if qtpy.PYSIDE6:
        #     logger.info('Setting Qt6-specific browser settings')
        #     self.webengineview.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        #     self.webengineview.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        #     self.webengineview.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        #     self.webengineview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        #     self.webengineview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        # self.browser.setPage(CustomWebEnginePage(self)) # Open clicked links in new window

        self.webengineview.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        self.webengineview.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.webengineview.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        self.webengineview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.webengineview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        self._unsaved_changes = False
        self._working = False
        self._is_mp_mode = False
        self._is_viewer_expanded = False
        self._layout = 2
        # self._up = 0

        self.initPbar()
        self.initJupyter()
        self.initMenu()
        self.initToolbar()
        self.initUI()
        self.initShortcuts()

        self.setWidgetSpacing()

        self.main_stylesheet = os.path.abspath('styles/default.qss')
        self.apply_default_style()

        # self.show_hide_controls_callback()
        # self.show_hide_hud_callback()


        # self.show_hide_python_callback()
        # self.show_hide_snr_plot_callback()
        # self.show_hide_project_tree_callback()
        self.normal_view()

        self._snr_plot_colors = ['#f3e375', '#5c4ccc', '#d6acd6', '#aaa672', '#152c74', '#404f74',
                                 '#f3e375', '#5c4ccc', '#d6acd6', '#aaa672', '#152c74', '#404f74']

        self._snr_plot_brushes = [pg.mkBrush(self._snr_plot_colors[0]),
                                  pg.mkBrush(self._snr_plot_colors[1]),
                                  pg.mkBrush(self._snr_plot_colors[2]),
                                  pg.mkBrush(self._snr_plot_colors[3]),
                                  pg.mkBrush(self._snr_plot_colors[4]),
                                  pg.mkBrush(self._snr_plot_colors[5]),
                                  pg.mkBrush(self._snr_plot_colors[6]),
                                  pg.mkBrush(self._snr_plot_colors[7]),
                                  pg.mkBrush(self._snr_plot_colors[8]),
                                  pg.mkBrush(self._snr_plot_colors[9]),
                                  pg.mkBrush(self._snr_plot_colors[10]),
                                  pg.mkBrush(self._snr_plot_colors[11])
                                  ]

        # self.set_idle()
        # self.image_panel_stack_widget.setCurrentIndex(4)
        self.image_panel_stack_widget.setCurrentIndex(2)
        if not cfg.NO_SPLASH:
            self.show_splash()
        self.resize(cfg.WIDTH, cfg.HEIGHT)
        self.moveCenter()
        # self.adjustSize()

        if cfg.DUMMY:
            with open('tests/example.proj', 'r') as f:
                data = json.load(f)
            project = DataModel(data=data)
            cfg.data = copy.deepcopy(project)
            cfg.data.set_paths_absolute(head='tests/example.proj')  # Todo This may not work
            cfg.data.link_all_stacks()
            self.onStartProject()
        else:
            # cfg.data = DataModel()
            cfg.data = None

    def show_hide_project_tree_callback(self, force_hide=False, force_show=False):

        if force_show:
            self.read_project_data_update_gui()
            self.projectdata_treeview.show()
            self.projectdata_treeview_widget.show()
            self.show_hide_project_tree_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_project_tree_button.setText('Hide Tree View')
            return

        if force_hide:
            self.projectdata_treeview.hide()
            self.projectdata_treeview_widget.hide()
            self.show_hide_project_tree_button.setIcon(qta.icon("mdi.json", color='#f3f6fb'))
            self.show_hide_project_tree_button.setText('Tree View')
            return

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

    def show_hide_snr_plot_callback(self, force_hide=False, force_show=False):
        if force_show:
            self.snr_plot_and_control.show()
            self.show_hide_snr_plot_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_snr_plot_button.setText('Hide SNR Plot')
            return
        if force_hide:
            self.snr_plot_and_control.hide()
            self.show_hide_snr_plot_button.setIcon(qta.icon("mdi.scatter-plot", color='#f3f6fb'))
            self.show_hide_snr_plot_button.setText('SNR Plot')
            return
        if self.snr_plot_and_control.isHidden():
            self.snr_plot_and_control.show()
            self.show_hide_snr_plot_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_snr_plot_button.setText('Hide SNR Plot')
        else:
            self.snr_plot_and_control.hide()
            self.show_hide_snr_plot_button.setIcon(qta.icon("mdi.scatter-plot", color='#f3f6fb'))
            self.show_hide_snr_plot_button.setText('SNR Plot')

    def show_hide_python_callback(self, force_hide=False, force_show=False):

        if force_show:
            self.python_console.show()
            self.show_hide_python_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))
            self.show_hide_python_button.setText('Hide Python')
            return

        if force_hide:
            self.python_console.hide()
            self.show_hide_python_button.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))
            self.show_hide_python_button.setText(' Python')
            return

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
        self.main_widget.setCurrentIndex(4)

    def write_paged_tiffs(self):
        t0 = time.time()
        dest = cfg.data.dest()
        for s in cfg.data.aligned_list():
            logger.info('Exporting Alignment for Scale %d to Multipage Tif...' % get_scale_val(s))
            directory = os.path.join(dest, s, 'img_aligned')
            out = os.path.join(dest, s + '_multi.tif')
            tiffs2MultiTiff(directory=directory, out=out)
        dt = time.time() - t0
        logger.info('Exporting Tifs Took %g Seconds' % dt)

    def updateJsonWidget(self):
        self.project_model.load(cfg.data.to_dict())

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
        self.clear_snr_plot() #Todo: Move this it should not be here
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

    def onAlignmentEnd(self):
        s = cfg.data.scale()
        self.initNgServer(scales=[s])
        self.updateHistoryListWidget(s=s)
        self.initSnrPlot()
        self.read_project_data_update_gui()
        self.updateBanner()
        self.updateEnabledButtons()
        self.show_hide_low_low_side_widgets()
        self.project_model.load(cfg.data.to_dict())


    def isProjectOpen(self):
        if cfg.data.dest() in ('', None):
            return False
        else:
            return True

    def align_matchpoint(self):

        pass


    def align_all(self, scale=None) -> None:

        if cfg.data is None:
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
            self.hud.post("Computing Initial Affine Transforms - Scale %d..." % scale_val)
        else:
            self.hud.post("Computing Refinement of Affine Transforms - Scale %d..." % scale_val)
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


    def align_forward(self, scale=None, num_layers=1) -> None:

        if cfg.data is None:
            self.hud.post('No data yet!', logging.WARNING);
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
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
        self.hud.post('Computing Alignment For Layers %d -> End - Scale %d...' % (start_layer, scale_val))
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

        self.hud.post('Generating Aligned Images From Layers %d -> End - Scale  %d...' % (start_layer, scale_val))
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
            self.hud.post('No data yet!', logging.WARNING);
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
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
        self.hud.post('Re-aligning The Current Layer - Scale %d...' % scale_val)
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
            self.hud.post('No data yet!', logging.WARNING);
            return

        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING); return

        if not is_cur_scale_aligned():
            self.hud.post('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING); return
        self.read_gui_update_project_data()
        logger.info('Regenerate Aligned Images...')
        self.hud.post('Regenerating Aligned Images - Scale %d...' % get_scale_val(scale))
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
            self.updateTextWidgetA()
            self.updateAffineWidgets()
            self.updateJsonWidget()
            self.initNgServer(scales=[cfg.data.scale()])
            if are_aligned_images_generated():
                self.hud.post('Regenerate Succeeded')
            else:
                self.hud.post('Image Generation Failed Unexpectedly. Try Re-aligning.', logging.ERROR)
            self.set_idle()
            QApplication.processEvents()


    def generate_multiscale_zarr(self):
        pass

    def export(self):
        logger.critical('Exporting To Zarr...')
        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return

        self.hud.post('Exporting...')
        if not are_aligned_images_generated():
            self.hud.post('Current Scale Must be Aligned Before It Can be Exported', logging.WARNING)
            logger.debug('(!) There is no alignment at this s to export. Returning from export_zarr().')
            self.show_warning('No Alignment', 'Nothing To Export.\n\n'
                                              'This is a Typical Alignment Workflow:\n'
                                              '(1) Open a project or import images and save.\n'
                                              '(2) Generate a set of scaled images and save.\n'
                                              '--> (3) Align each s starting with the coarsest.'
                              )
            return
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

    def update_win_self(self):
        self.update()  # repaint

    @Slot()
    def apply_all(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        swim_val = self.get_swim_input()
        whitening_val = self.get_whitening_input()
        scales_dict = cfg.data['data']['scales']
        self.hud.post('Applying These Settings To All Data...')
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

    @Slot()
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
        if cfg.data.n_scales() == 1:
            self.next_scale_button.setEnabled(False)
            self.prev_scale_button.setEnabled(False)
            self.align_all_button.setEnabled(True)
            self.regenerate_button.setEnabled(True)
        else:
            cur_index = self.scales_combobox.currentIndex()
            if cur_index == 0:
                self.prev_scale_button.setEnabled(True)
                self.next_scale_button.setEnabled(False)
            elif cfg.data.n_scales() == cur_index + 1:
                self.prev_scale_button.setEnabled(False)
                self.next_scale_button.setEnabled(True)
            else:
                self.prev_scale_button.setEnabled(True)
                self.next_scale_button.setEnabled(True)


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
            self.scales_combobox.setCurrentIndex(self.scales_combobox.currentIndex() - 1)  # Changes Scale
            cfg.data.set_layer(cur_layer)
            # self.read_project_data_update_gui()
            self.onScaleChange()
            # self.hud.post('Viewing Scale %d' % get_scale_val(cfg.data.scale()))
            if not cfg.data.is_alignable():
                self.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
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
            self.scales_combobox.setCurrentIndex(self.scales_combobox.currentIndex() + 1)  # Changes Scale
            cfg.data.set_layer(cur_layer) # Set layer to layer last visited at previous s
            self.onScaleChange()
            # self.hud.post('Viewing Scale %d' % get_scale_val(cfg.data.scale()))
            if not cfg.data.is_alignable():
                self.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
        except:
            print_exception()

    @Slot()
    def set_status(self, msg: str) -> None:
        self.statusBar.showMessage(msg)

    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')

    def apply_default_style(self):
        '''#colors
        color: #f3f6fb;  /* snow white */
        color: #004060;  /* drafting blue */
        '''
        cfg.THEME = 0
        if inspect.stack()[1].function != '__init__':
            self.hud.post('Setting Default Theme')
        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())
        pg.setConfigOption('background', '#1B1E23')
        # self.python_console.set_color_none()
        self.hud.set_theme_default()
        # self.python_console.setStyleSheet('background-color: #004060; border-width: 0px; color: #f3f6fb;')
        self.python_console.setStyleSheet('background-color: #004060; border-width: 0px; color: #f3f6fb;')
        self.scales_combobox.setStyleSheet('background-color: #f3f6fb; color: #000000;')
        # self.reset_groupbox_styles()
        if inspect.stack()[1].function != '__init__':
            self.initNgServer(scales=[cfg.data.scale()])

    def apply_daylight_style(self):
        cfg.THEME = 1
        if inspect.stack()[1].function != '__init__':
            self.hud.post('Setting Daylight Theme')
        self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())
        pg.setConfigOption('background', 'w')
        # self.python_console.set_color_none()
        self.python_console.set_color_linux()
        self.hud.set_theme_light()
        self.image_panel_landing_page.setStyleSheet('background-color: #fdf3da')
        if inspect.stack()[1].function != '__init__':
            self.initNgServer(scales=[cfg.data.scale()])

    def apply_moonlit_style(self):
        cfg.THEME = 2
        if inspect.stack()[1].function != '__init__':
            self.hud.post('Setting Moonlit Theme')
        self.main_stylesheet = os.path.abspath('src/styles/moonlit.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #333333')
        if inspect.stack()[1].function != '__init__':
            self.initNgServer(scales=[cfg.data.scale()])

    def apply_sagittarius_style(self):
        cfg.THEME = 3
        if inspect.stack()[1].function != '__init__':
            self.hud.post('Setting Sagittarius Theme')
        self.main_stylesheet = os.path.abspath('src/styles/sagittarius.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #000000')
        if inspect.stack()[1].function != '__init__':
            self.initNgServer(scales=[cfg.data.scale()])

    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')

    def onScaleChange(self):
        s = cfg.data.scale()
        self.refreshNeuroglancerURL()
        self.read_project_data_update_gui()
        self.updateHistoryListWidget(s=s)
        self.project_model.load(cfg.data.to_dict())
        self.updateLowLowWidgetB()
        self.updateBanner(s=s)
        self.updateEnabledButtons()
        self.updateStatusTips()

    @Slot()
    def read_gui_update_project_data(self) -> None:
        '''Reads MainWindow to Update Project Data.'''
        #1109 Rethink this. No longer can be called for every layer change... removing from s change mechanics
        logger.debug('read_gui_update_project_data:')


        if self.get_null_bias_value() == 'None':
            try:
                cfg.data.set_use_poly_order(False)
            except:
                logger.warning('Unable to Update Project Dictionary with Null CAFM')
        else:
            try:
                cfg.data.set_use_poly_order(True)
            except:
                logger.warning('Unable to Update Project Dictionary with Null CAFM')
            try:
                cfg.data.set_poly_order(int(self.get_null_bias_value()))
                logger.info(f'Poly Order Set In Data To {int(self.get_null_bias_value())}')
            except:
                logger.warning('Unable to Update Project Dictionary with Polynomial Order')

        try:
            cfg.data.set_use_bounding_rect(self.get_bounding_state(), s=cfg.data.scale())
        except:
            logger.warning('Unable to Update Project Dictionary with Bounding Rect State')

        try:
            cfg.data.set_whitening(self.get_whitening_input())
            logger.info(f'Whitening Set In Data To {self.get_whitening_input()}')
        except:
            logger.warning('Unable to Update Project Dictionary with Whitening Factor')

        try:
            cfg.data.set_swim_window(self.get_swim_input())
            logger.info(f'SWIM Window Set In Data To {self.get_swim_input()}')
        except:
            logger.warning('Unable to Update Project Dictionary with SWIM Window')

    @Slot()
    def read_project_data_update_gui(self, ng_layer=None) -> None:
        '''Reads Project Data to Update MainWindow.'''
        if self._working == True:
            logger.warning("Can't update GUI now - working...")
            self.hud.post("Can't update GUI now - working...", logging.WARNING)
            return
        if cfg.data is None:
            logger.warning('No need to update the interface')
            return
        if isinstance(ng_layer, int):
            try:
                # logger.info('Updating, Layer %d...' % ng_layer)
                # if -1 < ng_layer < cfg.data.n_layers():
                #     logger.info(f'Updating layer from {cfg.data.layer()} to {ng_layer}')
                cfg.data.set_layer(ng_layer)
            except:
                print_exception()
            '''This Condition Is True At The End Of The Image Stack'''
            if ng_layer == cfg.data.n_layers():
                self.browser_overlay_widget.setStyleSheet('background-color: rgba(0, 0, 0, 1.0);')
                self.browser_overlay_label.setText('End Of Image Stack')
                self.browser_overlay_label.show()
                self.browser_overlay_widget.show()
                self.clearTextWidgetA()
                self.updateAffineWidgets(show=False)
                logger.info(f'Showing Browser Overlay, layer({cfg.data.layer()}) - Returning')
                return
            else:
                self.browser_overlay_widget.hide()
                self.browser_overlay_label.hide()
        # else:
            # logger.info('Updating (caller: %s)...' % inspect.stack()[1].function)
        logger.info(f'Updating, Current Layer {cfg.data.layer()}...')
        self.updateTextWidgetA()
        self.updateAffineWidgets(show=True)
        if cfg.data.skipped():
            self.browser_overlay_widget.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
            self.browser_overlay_label.setText('X SKIPPED - %s' % cfg.data.name_base())
            self.browser_overlay_label.show()
            self.browser_overlay_widget.show()
        else:
            self.browser_overlay_widget.hide()
            self.browser_overlay_label.hide()
        try:     self.toggle_skip.setChecked(cfg.data.skipped())
        except:  logger.warning('Skip Toggle Widget Failed to Update')
        try:     self.jump_input.setText(str(cfg.data.layer()))
        except:  logger.warning('Current Layer Widget Failed to Update')
        try:     self.whitening_input.setText(str(cfg.data.whitening()))
        except:  logger.warning('Whitening Input Widget Failed to Update')
        try:     self.swim_input.setText(str(cfg.data.swim_window()))
        except:  logger.warning('Swim Input Widget Failed to Update')
        try:     self.toggle_bounding_rect.setChecked(cfg.data.has_bb())
        except:  logger.warning('Bounding Rect Widget Failed to Update')
        try:     self.bias_bool_combo.setCurrentText(str(cfg.data.poly_order())) if cfg.data.null_cafm() else 'None'
        except:  logger.warning('Polynomial Order Combobox Widget Failed to Update')


    def updateTextWidgetA(self):
        name = "<b style='color: #010048;font-size:14px;'>%s</b><br>" % cfg.data.name_base()
        skip = "<b style='color:red;'> SKIP</b><br>" if cfg.data.skipped() else ''
        completed = "Scales Aligned: <b style='color: #212121;font-size:12px;'>(%d/%d)</b><br>" % \
                      (len(cfg.data.aligned_list()), cfg.data.n_scales())
        if is_cur_scale_aligned():
            if cfg.data.has_bb():
                bb = cfg.data.bounding_rect()
                dims = [bb[2], bb[3]]
            else:
                dims = cfg.data.image_size()
            bb_dims = "Bounds: <b style='color: #212121;font-size:12px;'>%dx%dpx</b><br>" % (dims[0], dims[1])
            snr = "<font color='#212121';size='12'>%s</font><br>" % cfg.data.snr()
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
        self.main_details_subwidgetB.setText(f"<b>Skipped Layers:</b><br>"
                                             f"{', '.join(map(str, cfg.data.skips_list()))}<br>"
                                             f"<b>Match Point Layers:</b><br>"
                                             f"{', '.join(map(str, cfg.data.find_layers_with_matchpoints()))}<br>")

    def clearLowLowWidgetB(self):
        self.main_details_subwidgetB.setText(f'<b>Skipped Layers:<br><b>Match Point Layers:</b>')


    def updateHistoryListWidget(self, s=None):
        if s == None: s = cfg.data.scale()
        self.history_label = QLabel('<b>Saved Alignments (Scale %d)</b>' % get_scale_val(s))
        self.historyListWidget.clear()
        # for i, f in enumerate(os.listdir(dir)):
        #     self.historyListWidget.insertItem(i, f)
        dir = os.path.join(cfg.data.dest(), s, 'history')
        self.historyListWidget.addItems(os.listdir(dir))

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
              "Note: You must 'regenerate' after swapping it in." % (scale_val, name)
        reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            pass
        else:
            logger.info("Returning without changing anything.")
            return
        self.hud.post('Loading %s')
        path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'history', name)
        with open(path, 'r') as f:
            scale = json.load(f)
        self.hud.post('Swapping Current Scale %d Dictionary with %s' % (scale_val, name))
        cfg.data.set_al_dict(aldict=scale)
        self.regenerate() #Todo test this under a range of possible scenarios

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
        # self.hud.post(f"Selected '%s' - SNR avg: %.4f" % (item.text(), snr_avg))
        self.hud.post(f'SNR avg: %.4f' % snr_avg)


    def updateAffineWidgets(self, show=True):

        if is_cur_scale_aligned() and show:
            afm, cafm = cfg.data.afm(), cfg.data.cafm()
        else:
            afm = cafm = [[0]*3,[0]*3]

        # 'cellspacing' affects table width and 'cellpadding' affects table height
        self.afm_widget.setText(
            f"<table table-layout='fixed' style='border-collapse: collapse;' cellspacing='3' cellpadding='3' border='0'>"
            f"  <tr>"
            f"    <td rowspan=2 style='background-color: #dcdcdc; width: 20px'><b>AFM</b></td>"
            f"    <td style='background-color: #f5f5f5; width:34px;'><center><pre>{str(round(afm[0][0], 3)).center(8)}</pre></center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px;'><center><pre>{str(round(afm[0][1], 3)).center(8)}</pre></center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px;'><center><pre>{str(round(afm[0][2], 3)).center(8)}</pre></center></td>"
            f"  </tr>"
            f"  <tr>"
            f"    <td style='background-color: #f5f5f5; width:34px'><center><pre>{str(round(afm[1][0], 3)).center(8)}</pre></center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px'><center><pre>{str(round(afm[1][1], 3)).center(8)}</pre></center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px'><center><pre>{str(round(afm[1][2], 3)).center(8)}</pre></center></td>"
            f"  </tr>"
            f"  <tr>"
            f"    <td rowspan=2 style='background-color: #dcdcdc; width: 10%'><b>CAFM</b></td>"
            f"    <td style='background-color: #f5f5f5; width:34px;'><center><pre>{str(round(cafm[0][0], 3)).center(8)}</pre></center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px;'><center><pre>{str(round(cafm[0][1], 3)).center(8)}</pre></center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px;'><center><pre>{str(round(cafm[0][2], 3)).center(8)}</pre></center></td>"
            f"  </tr>"
            f"  <tr>"
            f"    <td style='background-color: #f5f5f5; width:34px'><center><pre>{str(round(cafm[1][0], 3)).center(8)}</center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px'><center>{str(round(cafm[1][1], 3)).center(8)}</center></td>"
            f"    <td style='background-color: #f5f5f5; width:34px'><center>{str(round(cafm[1][2], 3)).center(8)}</pre></center></td>"
            f"  </tr>"
            f"</table>")


    @Slot()
    def set_idle(self) -> None:
        if self._working == False:
            self.statusBar.showMessage('Idle')
        # pass

    @Slot()
    def set_busy(self) -> None:
        self.statusBar.showMessage('Busy...')

    @Slot()
    def get_whitening_input(self) -> float:
        return float(self.whitening_input.text())

    @Slot()
    def get_swim_input(self) -> float:
        return float(self.swim_input.text())

    @Slot()
    def get_bounding_state(self) -> bool:
        return self.toggle_bounding_rect.isChecked()

    @Slot()
    def get_null_bias_value(self) -> str:
        return str(self.bias_bool_combo.currentText())

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
        # leader_panel = self.get_panels()[-1]
        # return leader_panel.request_layer()
        return self.ng_workers[cfg.data.scale()].request_layer()

    def updateJumpValidator(self):
        self.jump_validator = QIntValidator(0, cfg.data.n_layers())
        self.jump_input.setValidator(self.jump_validator)

    #Todo Fix These
    @Slot()
    def jump_to(self, requested) -> None:
        if requested not in range(cfg.data.n_layers()):
            logger.warning('Requested layer is not a valid layer')
            return
        self.hud.post('Jumping To Layer %d' % requested)
        state = copy.deepcopy(self.ng_workers[cfg.data.scale()].viewer.state)
        state.position[0] = requested
        self.ng_workers[cfg.data.scale()].viewer.set_state(state)
        self.read_project_data_update_gui()
        self.refreshNeuroglancerURL()

    @Slot()
    def jump_to_layer(self) -> None:
        requested = int(self.jump_input.text())
        if requested not in range(cfg.data.n_layers()):
            logger.warning('Requested layer is not a valid layer')
            return
        self.hud.post('Jumping To Layer %d' % requested)
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
            self.hud.post("Current Scale Must Be Aligned First", logging.WARNING)
            return
        try:
            self.read_gui_update_project_data()
            snr_list = cfg.data.snr_list()
            enumerate_obj = enumerate(snr_list)
            sorted_pairs = sorted(enumerate_obj, key=operator.itemgetter(1))
            sorted_indices = [index for index, element in sorted_pairs]  # <- rearranged indices
            next_layer = sorted_indices[self.jump_to_worst_ticker]  # int
            snr = sorted_pairs[self.jump_to_worst_ticker]  # tuple
            rank = self.jump_to_worst_ticker  # int
            self.hud.post("Jumping to Layer %d (Badness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            # cfg.data.set_layer(next_layer)
            self.jump_to(requested=next_layer)
            self.read_project_data_update_gui()
            self.jump_to_worst_ticker += 1
        except:
            self.jump_to_worst_ticker = 1
            print_exception()

    def jump_to_best_snr(self) -> None:
        if not are_images_imported():
            self.hud.post("Images Must Be Imported First", logging.WARNING)
            return
        if not are_aligned_images_generated():
            self.hud.post("You Must Align This Scale First!")
            return
        try:
            self.read_gui_update_project_data()
            snr_list = cfg.data.snr_list()
            enumerate_obj = enumerate(snr_list)
            sorted_pairs = sorted(enumerate_obj, key=operator.itemgetter(1), reverse=True)
            sorted_indices = [index for index, element in sorted_pairs]  # <- rearranged indices
            # sorted_indices = list(reversed(sorted_indices))
            next_layer = sorted_indices[self.jump_to_best_ticker]
            snr = sorted_pairs[self.jump_to_best_ticker]
            rank = self.jump_to_best_ticker
            self.hud.post("Jumping to l %d (Goodness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            # cfg.data.set_layer(next_layer)
            self.jump_to(requested=next_layer)
            self.read_project_data_update_gui()
            self.jump_to_best_ticker += 1
        except:
            self.jump_to_best_ticker = 0
            print_exception()

    @Slot()
    def reload_scales_combobox(self) -> None:
        # logger.info('Reloading Scale Combobox (caller: %s)' % inspect.stack()[1].function)
        self.scales_combobox_switch = 0
        self.scales_combobox.clear()
        self.scales_combobox.addItems(cfg.data.scales())
        index = self.scales_combobox.findText(cfg.data.scale(), Qt.MatchFixedString)
        if index >= 0:
            self.scales_combobox.setCurrentIndex(index)
        self.scales_combobox_switch = 1

    @Slot()
    def fn_scales_combobox(self) -> None:
        caller = inspect.stack()[1].function
        logger.info('caller: %s' % caller)
        # logger.info('self.scales_combobox_switch = %s' % self.scales_combobox_switch)
        if self.scales_combobox_switch == 0:
            if inspect.stack()[1].function != 'reload_scales_combobox':
                logger.info('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return None
        if self._working:
            logger.warning('fn_scales_combobox was called but _working is True -> ignoring the signal')
            return None
        new_scale = self.scales_combobox.currentText()
        logger.info(f'Updating, %s...' % new_scale)
        cfg.data.set_scale(new_scale)
        # if is_arg_scale_aligned(new_scale):
        #     self.ng_browser_2.show()
        #     self.ng_browser_2.setFocus()
        # else:
        #     self.hide_browser_2()

        # self.read_project_data_update_gui()
        self.onScaleChange()
        # self.refreshNeuroglancerURL()

    def get_panels(self, s=None):
        if s == None: s = cfg.data.scale()
        # if is_arg_scale_aligned(s):
        #     panels = [self.ng_workers[s]['originals'], self.ng_workers[s]['aligned']]
        # else:
        #     panels = [self.ng_workers[s]]
        # return panels
        return [self.ng_workers[s]]




    def fn_ng_layout_combobox(self) -> None:
        logger.critical("fn_ng_layout_combobox (called by: %s)" % inspect.stack()[1].function)
        s = cfg.data.scale()
        try:
            # for panel in self.get_panels(s=s):
            if self.ng_layout_combobox.currentText() == 'xy':
                self.ng_workers[s].set_layout_xy()
                self.ngLayout1Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == 'yz':
                self.ng_workers[s].set_layout_yz()
                self.ngLayout2Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == 'xz':
                self.ng_workers[s].set_layout_xz()
                self.ngLayout3Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == 'xy-3d':
                self.ng_workers[s].set_layout_xy_3d()
                self.ngLayout4Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == 'yz-3d':
                self.ng_workers[s].set_layout_yz_3d()
                self.ngLayout5Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == 'xz-3d':
                self.ng_workers[s].set_layout_xz_3d()
                self.ngLayout6Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == '3d':
                self.ng_workers[s].set_layout_3d()
                self.ngLayout7Action.setChecked(True)
            elif self.ng_layout_combobox.currentText() == '4panel':
                self.ng_workers[s].set_layout_4panel()
                self.ngLayout8Action.setChecked(True)
            self.refreshNeuroglancerURL()
            # self.initNgServer()
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

    def get_this_scripts_path(self):
        return os.path.realpath(__file__)

    def import_images_dialog(self):
        '''Dialog for importing images. Returns list of filenames.'''
        dialog = QFileDialogPreview()
        dialog.setOption(QFileDialog.DontUseNativeDialog)
        dialog.setWindowTitle('Import Images - %s' % cfg.data.name())
        dialog.setNameFilter('Images (*.tif *.tiff)')
        dialog.setFileMode(QFileDialog.ExistingFiles)
        urls = dialog.sidebarUrls()
        urls.append(QUrl.fromLocalFile(QDir.homePath()))
        if '.tacc.utexas.edu' in platform.node():
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabData'))
        dialog.setSidebarUrls(urls)
        logger.debug('Selected Files:\n%s' % str(dialog.selectedFiles()))
        logger.info('Dialog return value: %s' % dialog.Accepted)
        if dialog.exec_() == QDialog.Accepted:
            # self.set_mainwindow_project_view()
            return dialog.selectedFiles()
        else:
            logger.warning('Import Images dialog did not return an image list')
            return

    def new_project_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        dialog = QFileDialog()
        dialog.setOption(QFileDialog.DontUseNativeDialog)
        dialog.setWindowTitle('* New Project *')
        dialog.setNameFilter("Text Files (*.proj *.json)")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        urls = dialog.sidebarUrls()
        if '.tacc.utexas.edu' in platform.node():
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
        dialog.setSidebarUrls(urls)
        if dialog.exec() == QFileDialog.Accepted:
            logger.info('Save File Path: %s' % dialog.selectedFiles()[0])
            return dialog.selectedFiles()[0]

    def export_afms(self):
        file = self.export_affines_dialog()
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
        file = self.export_affines_dialog()
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

    def export_affines_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        dialog = QFileDialog()
        dialog.setOption(QFileDialog.DontUseNativeDialog)
        dialog.setWindowTitle('Export Affine Data as .csv')
        dialog.setNameFilter("Text Files (*.csv)")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        if dialog.exec() == QFileDialog.Accepted:
            self.hud.post('Exported: %s' % dialog.selectedFiles()[0])
            return dialog.selectedFiles()[0]

    def open_project_dialog(self) -> str:
        '''Dialog for opening a data. Returns 'filename'.'''
        dialog = QFileDialog()
        dialog.setOption(QFileDialog.DontUseNativeDialog)
        dialog.setWindowTitle('* Open Project *')
        dialog.setNameFilter("Text Files (*.proj *.json)")
        dialog.setViewMode(QFileDialog.Detail)
        urls = dialog.sidebarUrls()
        if '.tacc.utexas.edu' in platform.node():
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
        dialog.setSidebarUrls(urls)

        if dialog.exec() == QFileDialog.Accepted:
            logger.info('Save File Name: %s' % dialog.selectedFiles()[0])
            # self.hud.post("Loading Project '%s'" % os.path.basename(dialog.selectedFiles()[0]))
            return dialog.selectedFiles()[0]

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

    def new_project(self):
        logger.critical('Starting A New Project...')
        self.hud.post('Set New Project Save Path...')
        # app_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        # os.chdir(app_dir)
        # if is_destination_set():
        logger.info('Asking user to confirm new data')
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
            self.set_idle()
            return
        if reply == QMessageBox.Cancel:
            logger.info("Response was 'Cancel'")
            self.hud.post('New Project Canceled', logging.WARNING)
            self.set_idle()
            return

        self.normal_view()
        self.hud.clear_display()
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.shutdownNeuroglancer()
        self.clear_snr_plot()
        self.hud.post('Creating A New Project...')
        filename = self.new_project_dialog()
        if filename in ['', None]:
            self.hud.post("New Project Canceled.")
            self.set_idle()
            return 0
        logger.info("Overwriting Project Data In Memory With New Template")
        if not filename.endswith('.proj'):
            filename += ".proj"
        path, extension = os.path.splitext(filename)
        cfg.data = None
        cfg.data = DataModel(name=path)
        makedirs_exist_ok(cfg.data.dest(), exist_ok=True)
        # self.import_images()
        try:
            self.import_images()
        except:
            print_exception()
            logger.warning('Import Images Dialog Was Canceled')
            return
        try:
            recipe_dialog = ConfigDialog(parent=self)
            if recipe_dialog.exec() != QFileDialog.Accepted:
                logger.warning('Configuration Dialog Did Not Return A Result - Canceling...')
                return
        except:
            logger.warning('Project Configuation Dialog Exited Abruptly')
            return

        self.scales_combobox_switch = 1
        try:
            self.autoscale()
        except:
            print_exception()
        try:
            self.onStartProject()
        except:
            print_exception()
        finally:
            self.save_project_to_file()  # Save for New Project, Not for Open Project
            logger.info('<<<< New Project <<<<')


    def rescale(self):
        dlg = AskContinueDialog(title='Confirm Rescale', msg='Warning: Rescaling resets project data.\n'
                                                             'Progress will be lost.  Continue?')
        if dlg.exec():
            pass
        else:
            logger.info('Rescale Canceled')
            return

        logger.info('Clobbering project JSON file...')

        try:
            os.remove(cfg.data.dest() + '.proj')
        except OSError:
            pass


        self.normal_view()
        self.shutdownNeuroglancer()
        self.clear_snr_plot()
        self.clearLowLowWidgetB()

        path = cfg.data.dest()
        filenames = cfg.data.get_source_img_paths()
        scales = cfg.data.scales()

        self.scales_combobox_switch = 0 #refactor this out
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

        try:
            recipe_dialog = ConfigDialog(parent=self)
            if recipe_dialog.exec() != QFileDialog.Accepted:
                logger.warning('Configuration Dialog Did Not Return A Result - Canceling...')
                return
        except:
            logger.warning('Project Configuation Dialog Exited Abruptly')
            return

        logger.info('Clobbering The Project Dictionary...')
        # cfg.data = DataModel(name=path)
        makedirs_exist_ok(cfg.data.dest(), exist_ok=True)
        logger.info(str(filenames))
        # self.import_images_silent(filenames, clear_role=True)
        # self.import_images_silent(filenames)
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




    def open_project(self):
        logger.critical('Opening Project...')
        filename = self.open_project_dialog()
        logger.info('filename: %s' % filename)
        if filename == '':
            self.hud.post("No Project File (.proj) Selected (='')", logging.WARNING)
            return
        if filename == None:
            self.hud.post('No Project File (.proj) Selected', logging.WARNING)
            return
        if os.path.isdir(filename):
            self.hud.post("Selected Path Is A Directory. "
                          "Please open a project file with extension .proj or .json.", logging.WARNING)
            return

        self.image_panel_stack_widget.setCurrentIndex(2)
        self.shutdownNeuroglancer()
        self.clearLowLowWidgetB()
        try:
            with open(filename, 'r') as f:
                project = DataModel(json.load(f)) #1123-
                # cfg.data = DataModel(json.load(f)) #1123+

        except:
            self.hud.post('No Project Opened', logging.WARNING)
            return
        cfg.data = copy.deepcopy(project) #1123-
        cfg.data.set_paths_absolute(filename=filename)

        # cfg.data.set_destination_absolute(head=filename)
        # cfg.data.link_all_stacks()
        self.onStartProject()

    def onStartProject(self):
        '''Functions that only need to be run once per project
        Do not automatically save, there is nothing to save yet'''
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.read_project_data_update_gui()
        self.setWindowTitle("Project: %s" % os.path.basename(cfg.data.dest()))
        self.updateStatusTips()
        self.reload_scales_combobox()  # 0529 #0713+
        self.updateEnabledButtons()
        self.updateJumpValidator()
        self.updateHistoryListWidget()
        self.project_model.load(cfg.data.to_dict())
        self.updateBanner()
        self.initSnrPlot()  # 1101
        # self.read_project_data_update_gui()  # ***
        self.show_hide_low_low_side_widgets()
        self.updateLowLowWidgetB()
        self.initOverviewPanel()
        self.scales_combobox_switch = 1
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        ng_layouts = ['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d']
        self.ng_layout_combobox.clear()
        self.ng_layout_combobox.addItems(ng_layouts)
        self.align_all_button.setText('Align All\n%s' % cfg.data.scale_pretty())
        self.create_ng_worker_dicts()
        self.initNgServer(scales=cfg.data.scales()) # must come AFTER scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        self.set_idle()
        QApplication.processEvents()


    def save_project(self):
        if cfg.data.dest() == '':
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
        # logger.info("Called by " + inspect.stack()[1].function)
        if saveas is not None:
            cfg.data.set_destination(saveas)
        self.read_gui_update_project_data()
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
        self.initNgServer(scales=[cfg.data.scale()])

    def import_images(self, clear_role=False):
        ''' Import images into data '''
        logger.critical('Importing Images...')
        self.hud.post('Select Images To Import...')
        role_to_import = 'base'
        try:
            filenames = natural_sort(self.import_images_dialog())
        except:
            logger.warning('No images were selected.')
            return 1

        cfg.data.set_source_path(os.path.dirname(filenames[0]))
        logger.debug('filenames = %s' % str(filenames))
        if clear_role:
            for layer in cfg.data.alstack():
                if role_to_import in layer['images'].keys():  layer['images'].pop(role_to_import)

        if filenames != None:
            if len(filenames) > 0:
                self.hud.post('Importing Selected Images...')
                logger.debug("Selected Files: " + str(filenames))
                for i, f in enumerate(filenames):
                    # Find next l with an empty role matching the requested role_to_import
                    logger.debug("Role " + str(role_to_import) + ", Importing file: " + str(f))
                    if f is None:
                        self.add_empty_to_role(role_to_import)
                    else:
                        self.add_image_to_role(f, role_to_import)

        if are_images_imported():
            self.hud.post('%d Images Imported Successfully' % len(filenames))
            cfg.IMAGES_IMPORTED = True
            img_size = cfg.data.image_size(s='scale_1')
            cfg.data.link_all_stacks()
            self.hud.post('%d Images Imported Successfully.' % cfg.data.n_layers())
            self.hud.post(f'Image Dimensions: {img_size[0]}x{img_size[1]} pixels')
            '''Todo save the image dimensions in project dictionary for quick lookup later'''
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)
        self.save_project_to_file() #1123+
        logger.info('<<<< Import Images <<<<')

    def import_images_silent(self, filenames, clear_role=False):
        logger.info(f'Filenames For Silent Import:\n{filenames}')
        ''' Import images into data '''
        logger.critical('Importing Images Silently...')
        role_to_import = 'base'

        cfg.data.set_source_path(os.path.dirname(filenames[0]))
        logger.debug('filenames = %s' % str(filenames))
        if clear_role:
            for layer in cfg.data.alstack():
                if role_to_import in layer['images'].keys():  layer['images'].pop(role_to_import)

        if filenames != None:
            if len(filenames) > 0:
                for i, f in enumerate(filenames):
                    # Find next l with an empty role matching the requested role_to_import
                    logger.info("Role " + str(role_to_import) + ", Importing file: " + str(f))
                    if f is None:
                        logger.info(f'Adding Empty To ({role_to_import})')
                        self.add_empty_to_role(role_to_import)
                    else:
                        logger.info(f'Adding Image To ({role_to_import}): {f}')
                        self.add_image_to_role(f, role_to_import)

        cfg.IMAGES_IMPORTED = True
        img_size = cfg.data.image_size(s='scale_1')
        cfg.data.link_all_stacks()
        self.hud.post('%d Images Imported Successfully.' % cfg.data.n_layers())
        self.hud.post('Image Dimensions: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')
        '''Todo save the image dimensions in project dictionary for quick lookup later'''

        logger.info('<<<< Import Images Silent <<<<')


    # def add_image_to_role(self, image_file_name, role_name, s=None):
    def add_image_to_role(self, image_file_name, role_name):
        logger.debug("Adding Image %s to Role '%s'" % (image_file_name, role_name))
        #### prexisting note: This function is now much closer to empty_into_role and should be merged

        #1118
        # if s == None:
        #     s = cfg.data.s()
        scale = 'scale_1'

        if image_file_name != None:
            if len(image_file_name) > 0:
                used_for_this_role = [role_name in l['images'].keys() for l in
                                      cfg.data['data']['scales'][scale]['alignment_stack']]
                layer_index = -1
                if False in used_for_this_role:
                    # There is an unused slot for this role. Find the first:
                    layer_index = used_for_this_role.index(False)
                else:
                    # There are no unused slots for this role. Add a new l:
                    cfg.data.append_layer(scale_key=scale)
                    layer_index = len(cfg.data['data']['scales'][scale]['alignment_stack']) - 1
                cfg.data.add_img(
                    scale_key=scale,
                    layer_index=layer_index,
                    role=role_name,
                    filename=image_file_name
                )

    def add_empty_to_role(self, role_name):
        logger.debug('MainWindow.add_empty_to_role:')
        local_cur_scale = cfg.data.scale()
        used_for_this_role = [role_name in l['images'].keys() for l in
                              cfg.data['data']['scales'][local_cur_scale]['alignment_stack']]
        layer_index = -1
        if False in used_for_this_role:
            # There is an unused slot for this role. Find the first.
            layer_index = used_for_this_role.index(False)
        else:
            # There are no unused slots for this role. Add a new l
            logger.debug("Adding Empty Layer For Role %s at l %d" % (role_name, layer_index))
            cfg.data.append_layer(scale_key=local_cur_scale)
            layer_index_for_new_role = len(cfg.data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        cfg.data.add_img(
            scale_key=local_cur_scale,
            layer_index=layer_index,
            role=role_name,
            filename=None
        )

    def moveCenter(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

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
        self.main_widget.setCurrentIndex(1)

    def html_keyboard_commands(self):
        app_root = self.get_application_root()
        html_f = os.path.join(app_root, 'src', 'resources', 'KeyboardCommands.html')
        print(html_f)
        with open(html_f, 'r') as f:
            html = f.read()
        self.browser_docs.setHtml(html)
        self.main_widget.setCurrentIndex(1)

    def documentation_view(self):
        self.hud.post("Viewing AlignEM_SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self.main_widget.setCurrentIndex(1)

    def documentation_view_home(self):
        self.hud.post("Viewing AlignEM-SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))
        self.main_widget.setCurrentIndex(1)

    def remote_view(self):
        self.hud.post("Loading A Neuroglancer Instance Running On A Remote Server...")
        # self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.main_widget.setCurrentIndex(3)

    def set_url(self, text: str) -> None:
        self.ng_browser.setUrl(QUrl(text))

    def view_swiftir_examples(self):
        self.browser_docs.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/examples/README.md'))
        self.main_widget.setCurrentIndex(1)

    def view_swiftir_commands(self):
        self.browser_docs.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/commands/README.md'))
        self.main_widget.setCurrentIndex(1)

    def shutdownNeuroglancer(self):
        if ng.is_server_running():
            logger.warning('Stopping Neuroglancer')
            ng.server.stop()

    def invalidate_all(self, s=None):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        if s == None: s = cfg.data.scale()
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


    def initNgServer(self, scales=None):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        if cfg.data is None:
            logger.warning('Nothing To View')
            return

        if not self.is_project_open():
            logger.warning('Nothing to view in Neuroglancer')
            return
        if scales in (None, False):
            scales = cfg.data.scales()
        logger.critical('Initializing NG Workers For Scales %s' % ', '.join(scales))
        self.hud.post('Starting Neuroglancer Workers...')
        self.set_status('Starting Neuroglancer...')
        # self.ng_workers = {}  # Todo not good but for now just initialize everything together
        try:

            for s in scales:
                logger.info('Deleting Viewer for %s...' % s)
                del self.ng_workers[s]

                is_aligned = is_arg_scale_aligned(s)
                logger.info('%s is aligned? %s' % (s, is_aligned))
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
                h = self.ng_browser.size().height()
                w = self.ng_browser.size().width()
                self.ng_workers[s] = NgHost(src=cfg.data.dest(), scale=s)
                self.threadpool.start(self.ng_workers[s])
                self.ng_workers[s].initViewer(layout=self._layout, w=w, h=h)
                self.ng_workers[s].signals.stateChanged.connect(lambda l: self.read_project_data_update_gui(ng_layer=l))
                self.refreshNeuroglancerURL(s=s)  # Important
            # self.refreshNeuroglancerURL() #Important
            self.ng_layout_combobox.setCurrentText('xy')
            self.ng_layout_combobox.currentTextChanged.connect(self.fn_ng_layout_combobox)
        except:
            print_exception()
        finally:
            self.image_panel_stack_widget.setCurrentIndex(1)
            self.set_idle()


    # def hide_browser_2(self):
    #     caller = inspect.stack()[1].function
    #     logger.warning(f'hiding browser 2 (caller:{caller})')
    #     self.ng_browser_2.hide()

    # does not work (?)
    def initNgViewer(self, s=None):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        if s == None: s = cfg.data.scale()
        logger.info('Initializing Viewer (%s)...' % s)
        self.ng_workers[s].initViewer()
        # for panel in self.get_panels():
        #     panel.initViewer()

    # def fitNgImagesToWindow(self):
    #     pass

    def create_ng_worker_dicts(self):
        logger.info('Creating NgWorker dictionaries...')
        self.ng_workers = dict.fromkeys(cfg.data.scales())

    def reload_remote(self):
        logger.info("Reloading Remote Neuroglancer Client")
        self.remote_view()

    def exit_docs(self):
        self.main_widget.setCurrentIndex(0)

    def exit_remote(self):
        self.main_widget.setCurrentIndex(0)

    def exit_demos(self):
        self.main_widget.setCurrentIndex(0)

    def webgl2_test(self):
        '''https://www.khronos.org/files/webgl20-reference-guide.pdf'''
        self.browser_docs.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.main_widget.setCurrentIndex(1)

    def google(self):
        self.hud.post('Googling...')
        self.browser_docs.setUrl(QUrl('https://www.google.com'))
        self.main_widget.setCurrentIndex(1)

    def gpu_config(self):
        self.browser_docs.setUrl(QUrl('chrome://gpu'))
        self.main_widget.setCurrentIndex(1)

    def print_ng_state_url(self):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running.')
            return
        try:
            self.ng_workers[cfg.data.scale()].show_state()
        except:
            print_exception()

    def print_ng_state(self):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        try:
            self.hud.post('\n\n%s' % str(self.ng_workers[cfg.data.scale()].viewer.state))
        except:
            pass

    def print_ng_raw_state(self):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        try:
            self.hud.post('\n\n%s' % str(self.ng_workers[cfg.data.scale()].config_state.raw_state))
        except:
            pass

    def browser_reload(self):
        try:
            self.ng_browser.reload()
        except:
            print_exception()

    def dump_ng_details(self):
        if not ng.is_server_running():
            logger.warning('Neuroglancer is not running')
            return
        v = self.ng_workers[cfg.data.s()].viewer
        self.hud.post("v.position: %s\n" % str(v.state.position))
        self.hud.post("v.config_state: %s\n" % str(v.config_state))
        # for panel in self.get_panels():
        #     self.hud.post(panel)

    def blend_ng(self):
        logger.info("blend_ng():")

    def show_splash(self):
        logger.info('Showing Splash...')
        self.temp_img_panel_index = self.image_panel_stack_widget.currentIndex()
        self.splashlabel.show()
        self.image_panel_stack_widget.setCurrentIndex(0)
        self.main_widget.setCurrentIndex(0)
        self.splashmovie.start()

    def runaftersplash(self):
        # self.main_widget.setCurrentIndex(0)
        # self.image_panel_stack_widget.setCurrentIndex(1)
        self.image_panel_stack_widget.setCurrentIndex(self.temp_img_panel_index)
        self.splashlabel.hide()

    def configure_project(self):
        logger.info('Showing configure project dialog...')
        recipe_dialog = ConfigDialog(parent=self)
        result = recipe_dialog.exec_()
        if not result:  logger.warning('Dialog Did Not Return A Result')

    def view_k_img(self):
        self.w = KImageWindow(parent=self)
        self.w.show()

    def bounding_rect_changed_callback(self, state):
        if inspect.stack()[1].function == 'read_project_data_update_gui': return
        if state:
            self.hud.post('Bounding Box is ON. Warning: Dimensions may grow larger than the original images.')
            cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            self.hud.post('Bounding Box is OFF (faster). Dimensions will equal the original images.')
            cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False

    def skip_changed_callback(self, state):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        # caller is 'main' when user is toggler
        if inspect.stack()[1].function == 'read_project_data_update_gui': return
        skip_state = self.toggle_skip.isChecked()
        for s in cfg.data.scales():
            layer = self.request_ng_layer()
            logger.info(f'request_ng_layer: {layer}, cfg.data.layer(): {cfg.data.layer()}, cfg.data.n_layers(): {cfg.data.n_layers()}')
            if layer >= cfg.data.n_layers():
                logger.warning(f'Request layer is out of range ({layer}) - Returning')
                return
            cfg.data.set_skip(skip_state, s=s, l=layer)  # for checkbox
        if skip_state: self.hud.post("Flagged For Skip: %s" % cfg.data.name_base())
        else:          self.hud.post("No Skip: %s" % cfg.data.name_base())
        cfg.data.link_all_stacks()
        self.read_project_data_update_gui()
        self.updateLowLowWidgetB()

    def skip_change_shortcut(self):
        if self.toggle_skip.isChecked():
            self.toggle_skip.setChecked(False)
        else:
            self.toggle_skip.setChecked(True)


    # def toggle_zarr_controls(self):
    #     if self.export_and_view_stack.isHidden():
    #         self.export_and_view_stack.show()
    #     else:
    #         self.export_and_view_stack.hide()

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

    def resizeEvent(self, event):
        self.resized.emit()
        # self.initNgServer()
        return super(MainWindow, self).resizeEvent(event)

    def pbar_max(self, x):
        self.pbar.setMaximum(x)

    def pbar_update(self, x):
        self.pbar.setValue(x)

    def setPbarText(self, text: str):
        self.pbar.setFormat('(%p%) ' + text)

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
        # self.initNgViewer()
        # self.initNgServer()
        self.initNgServer(scales=[cfg.data.scale()])

    def set_mp_marker_size(self):
        cfg.data['user_settings']['mp_marker_size'] = self.mp_marker_size_spinbox.value()
        # self.initNgViewer()
        # self.initNgServer()
        self.initNgServer(scales=[cfg.data.scale()])


    def initShortcuts(self):
        '''Initialize Shortcuts'''
        logger.info('Initializing Shortcuts')
        events = (
            (QKeySequence.MoveToPreviousChar, self.scale_down),
            (QKeySequence.MoveToNextChar, self.scale_up)
        )
        for event, action in events:
            QShortcut(event, self, action)

    def set_opacity(self, obj, val):
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(val)  # 0 to 1 will cause the fade effect to kick in
        obj.setGraphicsEffect(op)
        obj.setAutoFillBackground(True)

    def set_shader_none(self):
        cfg.SHADER = None
        self.initNgServer(scales=[cfg.data.scale()])
        # self.initNgViewer() # Note: must restart NG

    def set_shader_colormapJet(self):
        cfg.SHADER = src.shaders.colormapJet
        self.initNgServer(scales=[cfg.data.scale()])
        # self.initNgViewer()

    def set_shader_test1(self):
        cfg.SHADER = src.shaders.shader_test1
        self.initNgServer(scales=[cfg.data.scale()])
        # self.initNgViewer()

    def set_shader_test2(self):
        cfg.SHADER = src.shaders.shader_test2
        self.initNgServer(scales=[cfg.data.scale()])
        # self.initNgViewer()

    def initToolbar(self):
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)

        # self.action_exit_app = QAction('Exit App', self)
        # self.action_exit_app.setStatusTip('Exit App')
        # self.action_exit_app.triggered.connect(self.exit_app)
        # self.action_exit_app.setIcon(qta.icon('fa.close', color=ICON_COLOR))
        # self.toolbar.addAction(self.action_exit_app)

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

        self.expandViewAction = QAction('Expand Neuroglancer to Full Window', self)
        self.expandViewAction.setStatusTip('Expand')
        self.expandViewAction.triggered.connect(self.expand_viewer_size)
        # self.expandViewAction.setIcon(qta.icon("ei.resize-full", color=ICON_COLOR))
        self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))
        self.expandViewAction.setToolTip('Set Expanded Viewer Size')
        self.toolbar.addAction(self.expandViewAction)

        self.layoutOneAction = QAction('Column Layout', self)
        self.layoutOneAction.setStatusTip('Column Layout')
        self.layoutOneAction.setToolTip('Column Layout')
        self.layoutOneAction.triggered.connect(self.set_viewer_layout_1)
        # self.layoutOneAction.setIcon(qta.icon('mdi.view-column', color=ICON_COLOR))
        # self.layoutOneAction.setIcon(qta.icon('mdi.view-column-outline', color=ICON_COLOR))
        # self.layoutOneAction.setIcon(qta.icon('fa.columns', color=ICON_COLOR))
        # self.layoutOneAction.setIcon(qta.icon('mdi.view-column', color=ICON_COLOR))
        # self.layoutOneAction.setIcon(qta.icon('mdi.view-parallel', color=ICON_COLOR))
        self.layoutOneAction.setIcon(qta.icon('mdi.view-column-outline', color=ICON_COLOR))
        self.toolbar.addAction(self.layoutOneAction)

        self.layoutTwoAction = QAction('Row Layout', self)
        self.layoutTwoAction.setStatusTip('Row Layout')
        self.layoutTwoAction.setToolTip('Row Layout')
        self.layoutTwoAction.triggered.connect(self.set_viewer_layout_2)
        # self.layoutTwoAction.setIcon(qta.icon('mdi.view-agenda', color=ICON_COLOR))
        # self.layoutTwoAction.setIcon(qta.icon('ph.rows-fill', color=ICON_COLOR))
        # self.layoutTwoAction.setIcon(qta.icon('ri.layout-4-line', color=ICON_COLOR))
        # self.layoutTwoAction.setIcon(qta.icon('ri.layout-row-line', color=ICON_COLOR))
        # self.layoutTwoAction.setIcon(qta.icon('mdi.view-sequential', color=ICON_COLOR))
        self.layoutTwoAction.setIcon(qta.icon('mdi.view-stream-outline', color=ICON_COLOR))
        self.toolbar.addAction(self.layoutTwoAction)

    def updateStatusTips(self):
        logger.info('Updating Status Tips...')
        self.regenerate_button.setStatusTip('Generate All Layers - Scale %d (alters Corrective Bias '
                                            'and Bounding Rectangle)' % get_scale_val(cfg.data.scale()))
        self.align_forward_button.setStatusTip(
            'Align + Generate Layers %d -> End - Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.scale())))
        self.align_all_button.setStatusTip('Generate + Align All Layers - Scale %d' % get_scale_val(cfg.data.scale()))
        self.align_one_button.setStatusTip(
            'Align + Generate Layer %d - Scale %d' % (cfg.data.layer(), get_scale_val(cfg.data.scale())))



    def initMenu(self):
        '''Initialize Menu'''
        logger.info('Initializing Menu')
        self.action_groups = {}
        self.menu = self.menuBar()
        # self.menu.setFixedHeight(20)
        # self.menu.setCursor(QCursor(Qt.PointingHandCursor))
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

        self.normalizeViewAction = QAction('Normalize', self)
        self.normalizeViewAction.triggered.connect(self.normal_view)
        viewMenu.addAction(self.normalizeViewAction)

        expandMenu = viewMenu.addMenu("Expand")

        self.expandViewerAction = QAction('Viewer', self)
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

        ngLayoutMenu = viewMenu.addMenu("Layout")

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
        self.ngLayout1Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('xy'))
        self.ngLayout2Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('xz'))
        self.ngLayout3Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('yz'))
        self.ngLayout4Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('yz-3d'))
        self.ngLayout5Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('xy-3d'))
        self.ngLayout6Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('xz-3d'))
        self.ngLayout6Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('3d'))
        self.ngLayout8Action.triggered.connect(lambda: self.ng_layout_combobox.setCurrentText('4panel'))
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

        shaderMenu = viewMenu.addMenu("Shader")

        self.shader1Action = QAction('None', self)
        self.shader1Action.triggered.connect(self.set_shader_none)
        shaderMenu.addAction(self.shader1Action)

        self.shader2Action = QAction('colorMap Jet', self)
        self.shader2Action.triggered.connect(self.set_shader_colormapJet)
        shaderMenu.addAction(self.shader2Action)

        self.shader3Action = QAction('shader_test1', self)
        self.shader3Action.triggered.connect(self.set_shader_test1)
        shaderMenu.addAction(self.shader3Action)

        self.shader4Action = QAction('shader_test2', self)
        self.shader4Action.triggered.connect(self.set_shader_test2)
        shaderMenu.addAction(self.shader4Action)

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

        self.splashAction = QAction('Show Splash', self)
        self.splashAction.triggered.connect(self.show_splash)
        viewMenu.addAction(self.splashAction)

        neuroglancerMenu = self.menu.addMenu('Neuroglancer')

        self.ngRestartAction = QAction('Restart', self)
        self.ngRestartAction.triggered.connect(self.initNgServer)
        neuroglancerMenu.addAction(self.ngRestartAction)

        ngStateMenu = neuroglancerMenu.addMenu("Show State")

        self.ngShowStateJsonAction = QAction('JSON', self)
        self.ngShowStateJsonAction.triggered.connect(self.print_ng_state)
        ngStateMenu.addAction(self.ngShowStateJsonAction)

        self.ngShowStateUrlAction = QAction('URL', self)
        self.ngShowStateUrlAction.triggered.connect(self.print_ng_state_url)
        ngStateMenu.addAction(self.ngShowStateUrlAction)

        self.ngExtractEverythingAction = QAction('Everything', self)
        self.ngExtractEverythingAction.triggered.connect(self.dump_ng_details)
        ngStateMenu.addAction(self.ngExtractEverythingAction)

        ngDebugMenu = neuroglancerMenu.addMenu("Debug")

        self.ngInvalidateAction = QAction('Invalidate Local Volumes', self)
        self.ngInvalidateAction.triggered.connect(self.invalidate_all)
        ngDebugMenu.addAction(self.ngInvalidateAction)

        self.ngRefreshViewerAction = QAction('Recreate View', self)
        self.ngRefreshViewerAction.triggered.connect(lambda: self.initNgViewer(s=cfg.data.scale()))
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
        self.alignAllAction.triggered.connect(self.align_all)
        self.alignAllAction.setShortcut('Ctrl+A')
        alignMenu.addAction(self.alignAllAction)

        self.alignOneAction = QAction('Align One', self)
        self.alignOneAction.triggered.connect(self.align_one)
        alignMenu.addAction(self.alignOneAction)

        self.alignForwardAction = QAction('Align Forward', self)
        self.alignForwardAction.triggered.connect(self.align_forward)
        alignMenu.addAction(self.alignForwardAction)

        self.alignMatchPointAction = QAction('Match Point Align', self)
        self.alignMatchPointAction.triggered.connect(self.enter_exit_match_point_mode)
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

        # show_zarr_info_aligned

        detailsMenu = self.menu.addMenu('Details')

        self.detailsWebglAction = QAction('Web GL Configuration', self)
        self.detailsWebglAction.triggered.connect(self.webgl2_test)
        detailsMenu.addAction(self.detailsWebglAction)

        self.detailsGpuAction = QAction('GPU Configuration', self)
        self.detailsGpuAction.triggered.connect(self.gpu_config)
        detailsMenu.addAction(self.detailsGpuAction)

        zarrMenu = detailsMenu.addMenu('Zarr')

        self.detailsZarrSourceAction = QAction('img_src.zarr', self)
        self.detailsZarrSourceAction.triggered.connect(self.show_zarr_info_source)
        zarrMenu.addAction(self.detailsZarrSourceAction)

        self.detailsZarrAlignedAction = QAction('img_aligned.zarr', self)
        self.detailsZarrAlignedAction.triggered.connect(self.show_zarr_info_aligned)
        zarrMenu.addAction(self.detailsZarrAlignedAction)

        # pythonMenu = detailsMenu.addMenu('Python/Jupyter')

        self.moduleSearchPathAction = QAction('Show Module Search Path', self)
        self.moduleSearchPathAction.triggered.connect(self.show_module_search_path)
        detailsMenu.addAction(self.moduleSearchPathAction)

        self.runtimePathAction = QAction('Show Runtime Path', self)
        self.runtimePathAction.triggered.connect(self.show_run_path)
        detailsMenu.addAction(self.runtimePathAction)


        projectMenu = self.menu.addMenu('Project')

        self.showMatchpointsAction = QAction('Show Matchpoints', self)
        self.showMatchpointsAction.triggered.connect(self.show_all_matchpoints)
        projectMenu.addAction(self.showMatchpointsAction)


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

    def initUI(self):
        '''Initialize Main UI'''
        logger.info('Initializing UI')

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

        # self.new_project_button = QPushButton(" New")
        # self.new_project_button.clicked.connect(self.new_project)
        # self.new_project_button.setIcon(qta.icon("fa.plus", color=ICON_COLOR))
        #
        # self.open_project_button = QPushButton(" Open")
        # self.open_project_button.clicked.connect(self.open_project)
        # self.open_project_button.setIcon(qta.icon("fa.folder-open", color=ICON_COLOR))
        #
        # self.save_project_button = QPushButton(" Save")
        # self.save_project_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.save_project_button.clicked.connect(self.save_project)
        # self.save_project_button.setIcon(qta.icon("mdi.content-save", color=ICON_COLOR))
        #
        # self.exit_app_button = QPushButton(" Exit")
        # self.exit_app_button.clicked.connect(self.exit_app)
        # self.exit_app_button.setIcon(qta.icon("fa.close", color=ICON_COLOR))
        #
        # self.documentation_button = QPushButton(" Help")
        # self.documentation_button.clicked.connect(self.documentation_view)
        # self.documentation_button.setIcon(qta.icon("mdi.help", color=ICON_COLOR))
        #
        # self.remote_viewer_button = QPushButton("NG SimpleHTTPServer")
        # self.remote_viewer_button.clicked.connect(self.remote_view)
        # self.remote_viewer_button.setStyleSheet("font-size: 11px;")
        #
        # self.refresh_button = QPushButton("Refresh")
        # self.refresh_button.clicked.connect(self.read_project_data_update_gui)
        # self.refresh_button.setStyleSheet("font-size: 11px;")
        # self.refresh_button.setIcon(qta.icon("fa.refresh", color=ICON_COLOR))
        #
        # # self.import_images_button = QPushButton(" Import\n Images")
        # # self.import_images_button.setToolTip('Import Images.')
        # # self.import_images_button.clicked.connect(self.import_images)
        # # self.import_images_button.setFixedSize(normal_button_size)
        # # self.import_images_button.setIcon(qta.icon("fa5s.file-import", color=ICON_COLOR))
        # # self.import_images_button.setStyleSheet("font-size: 11px;")
        # # self.import_images_button.hide()
        #
        # # self.main_navigation_layout = QGridLayout()
        # # self.main_navigation_layout.addWidget(self.new_project_button, 0, 0)
        # # self.main_navigation_layout.addWidget(self.open_project_button, 0, 1)
        # # self.main_navigation_layout.addWidget(self.save_project_button, 0, 2)
        # # self.main_navigation_layout.addWidget(self.exit_app_button, 1, 0)
        # # self.main_navigation_layout.addWidget(self.documentation_button, 1, 1)
        # # self.main_navigation_layout.addWidget(self.remote_viewer_button, 1, 2)
        #
        # self.main_navigation_layout = QHBoxLayout()
        # # self.main_navigation_layout.addWidget(self.import_images_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.new_project_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.open_project_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.save_project_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.remote_viewer_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.documentation_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.exit_app_button, alignment=Qt.AlignLeft)
        # # self.main_navigation_layout.addWidget(self.refresh_button, alignment=Qt.AlignLeft)
        # self.main_navigation_layout.addWidget(self.new_project_button)
        # self.main_navigation_layout.addWidget(self.open_project_button)
        # # self.main_navigation_layout.addWidget(self.save_project_button)
        # # self.main_navigation_layout.addWidget(self.remote_viewer_button)
        # # self.main_navigation_layout.addWidget(self.documentation_button)
        # self.main_navigation_layout.addWidget(self.exit_app_button)
        # self.main_navigation_layout.addWidget(self.refresh_button)
        # self.main_navigation_layout.addStretch()
        # self.main_navigation_widget = QWidget()
        # self.main_navigation_widget.setLayout(self.main_navigation_layout)

        tip = 'Reset (Use Everything)'
        self.clear_skips_button = QPushButton('Use All')
        self.clear_skips_button.setEnabled(False)
        self.clear_skips_button.setStatusTip('Use All The Images')
        self.clear_skips_button.setStyleSheet("font-size: 10px;")
        self.clear_skips_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clear_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_skips_button.clicked.connect(self.clear_skips)
        self.clear_skips_button.setFixedSize(small_button_size)

        tip = 'Set Whether to Use or Reject the Current Layer'
        self.skip_label = QLabel("Toggle Image\nKeep/Reject:")
        self.skip_label.setStyleSheet("font-size: 11px;")
        self.skip_label.setToolTip(tip)

        # self.toggle_skip = ToggleSwitch()
        self.toggle_skip = QCheckBox()
        self.toggle_skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle_skip.setObjectName('toggle_skip')
        self.toggle_skip.stateChanged.connect(self.skip_changed_callback)
        self.toggle_skip.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_skip.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))

        self.skip_layout = QHBoxLayout()
        self.skip_layout.addWidget(self.skip_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.skip_layout.addWidget(self.toggle_skip, alignment=Qt.AlignmentFlag.AlignLeft)
        self.skip_layout.addWidget(self.clear_skips_button)

        self.ng_layout_combobox = QComboBox()
        self.ng_layout_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ng_layout_combobox.setFixedSize(QSize(76, std_height))

        tip = 'Jump to image #'
        self.jump_label = QLabel("Image:")
        self.jump_label.setToolTip(tip)
        self.jump_input = QLineEdit(self)
        self.jump_input.setFocusPolicy(Qt.ClickFocus)
        self.jump_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.jump_input.setFixedSize(std_input_size, std_height)
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer())

        '''GroupBox 3 Alignment'''
        self.scales_combobox = QComboBox(self)
        self.scales_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scales_combobox.setFixedSize(std_button_size)
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

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
        self.whitening_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.whitening_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.whitening_grid = QGridLayout()
        self.whitening_grid.addWidget(self.whitening_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

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
        self.swim_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.swim_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.swim_grid = QGridLayout()
        self.swim_grid.addWidget(self.swim_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        self.apply_all_button = QPushButton("Apply To All")
        self.apply_all_button.setEnabled(False)
        self.apply_all_button.setStatusTip('Apply These Settings To All The Data')
        self.apply_all_button.setStyleSheet("font-size: 9px;")
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.apply_all_button.clicked.connect(self.apply_all)
        self.apply_all_button.setFixedSize(slim_button_size)

        tip = 'Go to next l.'
        self.next_scale_button = QPushButton()
        self.next_scale_button.setEnabled(False)
        self.next_scale_button.setStyleSheet("font-size: 11px;")
        self.next_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_scale_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.next_scale_button.clicked.connect(self.scale_up)
        self.next_scale_button.setFixedSize(std_height, std_height)
        self.next_scale_button.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        tip = 'Go to previous l.'
        self.prev_scale_button = QPushButton()
        self.prev_scale_button.setEnabled(False)
        self.prev_scale_button.setStyleSheet("font-size: 11px;")
        self.prev_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_scale_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
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
        self.align_all_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.align_all_button.clicked.connect(lambda: self.align_all(scale=cfg.data.scale()))
        self.align_all_button.setFixedSize(normal_button_size)

        tip = 'Align and Generate This Layer'
        self.align_one_button = QPushButton('Align This\nLayer')
        self.align_one_button.setEnabled(False)
        self.align_one_button.setStyleSheet("font-size: 11px;")
        self.align_one_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_one_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.align_one_button.clicked.connect(lambda: self.align_one(scale=cfg.data.scale()))
        self.align_one_button.setFixedSize(normal_button_size)

        tip = 'Align and Generate From Layer Current Layer to End'
        self.align_forward_button = QPushButton('Align\nForward')
        self.align_forward_button.setEnabled(False)
        self.align_forward_button.setStyleSheet("font-size: 11px;")
        self.align_forward_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_forward_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.align_forward_button.clicked.connect(lambda: self.align_forward(scale=cfg.data.scale()))
        self.align_forward_button.setFixedSize(normal_button_size)

        tip = 'Automatically generate aligned images.'
        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.toggle_auto_generate = ToggleSwitch()  # toggleboundingrect
        self.toggle_auto_generate.stateChanged.connect(self.has_unsaved_changes)
        self.auto_generate_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_auto_generate.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_auto_generate.setChecked(True)
        self.toggle_auto_generate.toggled.connect(self.toggle_auto_generate_callback)
        self.toggle_auto_generate_hlayout = QHBoxLayout()
        self.toggle_auto_generate_hlayout.addWidget(self.auto_generate_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.toggle_auto_generate_hlayout.addWidget(self.toggle_auto_generate, alignment=Qt.AlignmentFlag.AlignVCenter)

        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension. This' \
              ' option is set at the coarsest s, in order to form a contiguous dataset.'
        self.null_bias_label = QLabel("Corrective\n(Poly) Bias:")
        self.null_bias_label.setStyleSheet("font-size: 11px;")
        self.null_bias_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.bias_bool_combo = QComboBox(self)
        self.bias_bool_combo.setStyleSheet("font-size: 11px;")
        self.bias_bool_combo.currentIndexChanged.connect(self.has_unsaved_changes)
        self.bias_bool_combo.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.bias_bool_combo.addItems(['None', '0', '1', '2', '3', '4'])
        self.bias_bool_combo.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self.bias_bool_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bias_bool_combo.setFixedSize(std_combobox_size)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.poly_order_hlayout.addWidget(self.bias_bool_combo, alignment=Qt.AlignmentFlag.AlignLeft)

        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that ' \
              'are the same size as the source images but may have missing data, while turning this ON will ' \
              'result in no missing data but may significantly increase the size of the generated images.'
        self.bounding_label = QLabel("Bounding\nRectangle:")
        self.bounding_label.setStyleSheet("font-size: 11px;")
        self.bounding_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setChecked(True)
        self.toggle_bounding_rect.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_bounding_rect.toggled.connect(self.bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignLeft)

        tip = "Recomputes the cumulative affine and generates new aligned images" \
              "based on the current Null Bias and Bounding Rectangle presets."
        self.regenerate_button = QPushButton('Regenerate')
        self.regenerate_button.setEnabled(False)
        self.regenerate_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
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

        '''GroupBox 4 Export & View'''
        # tip = 'Zarr Compression Level\n(default=5)'
        # self.clevel_label = QLabel('clevel (1-9):')
        # self.clevel_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # self.clevel_input = QLineEdit(self)
        # self.clevel_input.textEdited.connect(self.has_unsaved_changes)
        # self.clevel_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.clevel_input.setText(str(cfg.CLEVEL))
        # self.clevel_input.setFixedWidth(small_input_size)
        # self.clevel_input.setFixedHeight(std_height)
        # self.clevel_valid = QIntValidator(1, 9, self)
        # self.clevel_input.setValidator(self.clevel_valid)
        #
        # tip = 'Zarr Compression Type\n(default=zstd)'
        # self.cname_label = QLabel('cname:')
        # self.cname_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # self.cname_combobox = QComboBox(self)
        # self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        # self.cname_combobox.setFixedSize(72, std_height)
        # self.export_and_view_hbox = QHBoxLayout()
        # self.export_zarr_button = QPushButton(" Remake\n Zarr")
        # tip = "This function creates a s pyramid from the full s aligned images and then converts them " \
        #       "into the chunked and compressed multiscale Zarr format that can be viewed as a contiguous " \
        #       "volumetric dataset in Neuroglancer."
        # wrapped = '\n'.join(textwrap.wrap(tip, width=35))
        # self.export_zarr_button.setToolTip(wrapped)
        # self.export_zarr_button.clicked.connect(self.export)
        # self.export_zarr_button.setFixedSize(normal_button_size)
        # self.export_zarr_button.setStyleSheet("font-size: 11px;")
        # # self.export_zarr_button.setIcon(qta.icon("fa5s.file-export", color=ICON_COLOR))
        # self.export_zarr_button.setIcon(qta.icon("fa5s.cubes", color=ICON_COLOR))
        #
        # tip = 'View Zarr export in Neuroglancer.'
        # self.ng_button = QPushButton("View In\nNeuroglancer")
        # self.ng_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # self.ng_button.clicked.connect(self.initNgServer)
        # self.ng_button.setFixedSize(normal_button_size)
        # # self.ng_button.setIcon(qta.icon("mdi.video-3d", color=ICON_COLOR))
        # self.ng_button.setStyleSheet("font-size: 9px;")
        #
        # self.export_hlayout = QVBoxLayout()
        # self.export_hlayout.addWidget(self.export_zarr_button, alignment=Qt.AlignmentFlag.AlignCenter)
        # self.export_hlayout.addWidget(self.ng_button, alignment=Qt.AlignmentFlag.AlignCenter)
        #
        # self.clevel_layout = QHBoxLayout()
        # self.clevel_layout.setContentsMargins(0, 0, 0, 0)
        # self.clevel_layout.addWidget(self.clevel_label, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignmentFlag.AlignRight)
        #
        # self.cname_layout = QHBoxLayout()
        # self.cname_layout.addWidget(self.cname_label, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignmentFlag.AlignRight)
        #
        # self.export_settings_layout = QHBoxLayout()
        # self.export_settings_layout.addLayout(self.clevel_layout)
        # self.export_settings_layout.addLayout(self.cname_layout)
        # self.export_settings_layout.addLayout(self.export_hlayout)

        self.main_details_subwidgetA = QTextEdit()
        self.main_details_subwidgetB = QTextEdit()
        self.main_details_subwidgetA.setReadOnly(True)
        self.main_details_subwidgetB.setReadOnly(True)
        self.main_details_subwidgetA.setObjectName('main_details_subwidgetA')
        self.main_details_subwidgetB.setObjectName('main_details_subwidgetB')
        self.main_details_subwidgetA.setStyleSheet('background-color: #e2e5e7;')
        self.main_details_subwidgetB.setStyleSheet('background-color: #e2e5e7;')

        '''Historical/Archived Alignments Functionality'''
        self.history_widget = QWidget()
        self.historyListWidget = QListWidget()
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

        self.matrix_container = QWidget()
        self.matrix_container_vlayout = QVBoxLayout()
        self.matrix_container_vlayout.addWidget(self.afm_widget)
        self.matrix_container.setLayout(self.matrix_container_vlayout)

        '''SNR Plot & Controls'''
        self.snr_plot_and_control = QWidget()
        self.snr_plot = SnrPlot()
        self.snr_plot_controls_hlayout = QHBoxLayout()
        # self.snr_plot_and_control_layout.setAlignment(Qt.AlignBottom)
        self.snr_plot_and_control_layout = QVBoxLayout()
        self.snr_plot_and_control_layout.addLayout(self.snr_plot_controls_hlayout)
        self.snr_plot_and_control_layout.addWidget(self.snr_plot)
        self.snr_plot_and_control_layout.setContentsMargins(8, 4, 8, 4)
        self.snr_plot_and_control.setLayout(self.snr_plot_and_control_layout)
        self.snr_plot_and_control.setAutoFillBackground(False)

        # self.title_label = QLabel('AlignEM-SWiFT')
        # self.title_label.setStyleSheet("font-size: 24px; color: #004060;")
        # self.subtitle_label = QLabel('for Aligning Electron Micrographs using SWiFT')
        # self.subtitle_label.setStyleSheet("font-size: 14px; color: #004060;")

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

        # tip = 'Show Neuroglancer key bindings.'
        tip = ''
        self.info_button = QLabel('')
        self.info_button = QPushButton()
        self.info_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.info_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.info_button.clicked.connect(self.html_keyboard_commands)
        self.info_button.setFixedSize(std_height, std_height)
        self.info_button.setIcon(qta.icon("fa.info", color=cfg.ICON_COLOR))

        self.details_banner = QWidget()
        self.details_banner.setObjectName('details_banner')
        self.details_banner.setFixedHeight(35)
        self.details_banner_layout = QHBoxLayout()
        self.details_banner_layout.addWidget(self.align_label_resolution)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.alignment_status_label)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.extra_header_text_label)
        self.details_banner_layout.addStretch(7)
        self.banner_layer_label = QLabel('Layer #: ')
        self.banner_layer_label.setObjectName('banner_layer_label')
        self.details_banner_layout.addWidget(self.banner_layer_label, alignment=Qt.AlignVCenter)
        self.details_banner_layout.addWidget(self.jump_input)
        self.banner_view_label = QLabel('View: ')
        self.banner_view_label.setObjectName('banner_view_label')
        self.details_banner_layout.addWidget(self.banner_view_label, alignment=Qt.AlignVCenter)
        self.details_banner_layout.addWidget(self.ng_layout_combobox)
        self.banner_scale_label = QLabel('Scale: ')
        self.banner_scale_label.setObjectName('banner_scale_label')
        self.details_banner_layout.addWidget(self.banner_scale_label, alignment=Qt.AlignVCenter)
        self.details_banner_layout.addWidget(self.scales_combobox)
        self.details_banner_layout.addWidget(self.info_button)
        self.details_banner.setLayout(self.details_banner_layout)

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
        # self.ng_browser_2 = QWebEngineView()
        # self.ng_browser_2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.ng_splitter.addWidget(self.ng_browser_2)
        self.ng_splitter.splitterMoved.connect(self.initNgServer)
        self.ng_splitter.setSizes([300, 700])

        self.ng_browser_layout = QGridLayout()
        # self.ng_browser_layout.addWidget(self.ng_browser, 0, 0)
        # # self.ng_browser_layout.addWidget(self.ng_browser_2, 0, 1, 1, 3)
        # self.ng_browser_layout.addWidget(self.ng_browser_2, 0, 1)
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
        # opacity = QGraphicsOpacityEffect()
        # opacity.setOpacity(0.7)
        self.alignem_splash_widget.setGraphicsEffect(QGraphicsOpacityEffect().setOpacity(0.7))
        self.splashmovie.finished.connect(lambda: self.runaftersplash())

        tip = 'Exit Full Window View'
        self.exit_expand_viewer_button = QPushButton('Back')
        self.exit_expand_viewer_button.setObjectName('exit_expand_viewer_button')
        self.exit_expand_viewer_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.exit_expand_viewer_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_expand_viewer_button.clicked.connect(self.normal_view)
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

        self.viewer_and_banner_widget = QWidget()
        self.viewer_and_banner_layout = QVBoxLayout()
        self.viewer_and_banner_layout.addWidget(self.details_banner)
        self.viewer_and_banner_layout.addWidget(self.image_panel_stack_widget)
        # self.viewer_and_banner_layout.addWidget(self.full_window_controls)
        self.viewer_and_banner_widget.setLayout(self.viewer_and_banner_layout)

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

        self.exit_matchpoint_button = QPushButton('Back')
        self.exit_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_matchpoint_button.clicked.connect(self.normal_view)
        self.exit_matchpoint_button.setFixedSize(normal_button_size)

        self.realign_matchpoint_button = QPushButton('Realign\nLayer')
        self.realign_matchpoint_button.setStyleSheet("font-size: 11px;")
        self.realign_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.realign_matchpoint_button.clicked.connect(self.align_one)
        self.realign_matchpoint_button.clicked.connect(lambda: self.align_one(use_scale=cfg.data.scale()))
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
        # self.matchpoint_text_snr.setAttribute(Qt.WA_TranslucentBackground)

        self.matchpoint_text_prompt = QTextEdit()
        self.matchpoint_text_prompt.setObjectName('matchpoint_text_prompt')
        # self.matchpoint_text_prompt.setAttribute(Qt.WA_TranslucentBackground)
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
        self.show_hide_controls_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.show_hide_controls_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_controls_button.clicked.connect(self.show_hide_controls_callback)
        self.show_hide_controls_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_controls_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Results'
        self.show_hide_snr_plot_button = QPushButton('Hide SNR Plot')
        self.show_hide_snr_plot_button.setObjectName('show_hide_snr_plot_button')
        self.show_hide_snr_plot_button.setStyleSheet(lower_controls_style)
        self.show_hide_snr_plot_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.show_hide_snr_plot_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_snr_plot_button.clicked.connect(self.show_hide_snr_plot_callback)
        self.show_hide_snr_plot_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_snr_plot_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Head-Up Display (HUD)'
        self.show_hide_hud_button = QPushButton()
        self.show_hide_hud_button.setObjectName('show_hide_hud_button')
        self.show_hide_hud_button.setStyleSheet(lower_controls_style)
        self.show_hide_hud_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.show_hide_hud_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_hud_button.clicked.connect(self.show_hide_hud_callback)
        self.show_hide_hud_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_hud_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Show/Hide Python'
        self.show_hide_python_button = QPushButton()
        self.show_hide_python_button.setObjectName('show_hide_python_button')
        self.show_hide_python_button.setStyleSheet(lower_controls_style)
        self.show_hide_python_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.show_hide_python_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_python_button.clicked.connect(self.show_hide_python_callback)
        self.show_hide_python_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_python_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))

        tip = 'Go To Project Overview'
        self.show_hide_overview_button = QPushButton('Overview')
        self.show_hide_overview_button.setObjectName('show_hide_overview_button')
        self.show_hide_overview_button.setStyleSheet(lower_controls_style)
        self.show_hide_overview_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.show_hide_overview_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_overview_button.clicked.connect(self.go_to_overview_callback)
        self.show_hide_overview_button.setFixedSize(show_hide_button_sizes)
        # self.show_hide_overview_button.setIcon(qta.icon('fa.table', color='#f3f6fb'))

        tip = 'Show/Hide Tools'
        self.show_hide_project_tree_button = QPushButton('Hide Tools')
        self.show_hide_project_tree_button.setObjectName('show_hide_project_tree_button')
        self.show_hide_project_tree_button.setStyleSheet(lower_controls_style)
        self.show_hide_project_tree_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.show_hide_project_tree_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_project_tree_button.clicked.connect(self.show_hide_project_tree_callback)
        self.show_hide_project_tree_button.setFixedSize(show_hide_button_sizes)
        self.show_hide_project_tree_button.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))


        '''Main Splitter'''
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(self.viewer_and_banner_widget)
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
        self.show_hide_main_features_vlayout.addWidget(self.show_hide_overview_button, alignment=Qt.AlignHCenter)
        self.show_hide_main_features_widget.setLayout(self.show_hide_main_features_vlayout)

        self.low_low_widget = QWidget()
        self.low_low_gridlayout = QGridLayout()
        self.low_low_widget.setLayout(self.low_low_gridlayout)
        self.low_low_gridlayout.addWidget(self.main_details_subwidgetA,0,0, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.main_details_subwidgetB,0,1, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.show_hide_main_features_widget,0,2, alignment=Qt.AlignCenter)
        # self.low_low_gridlayout.addWidget(self.afm_widget, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.matrix_container,0,3, alignment=Qt.AlignCenter)
        self.low_low_gridlayout.addWidget(self.history_widget,0,4, alignment=Qt.AlignCenter)
        self.main_details_subwidgetA.hide()
        self.main_details_subwidgetB.hide()
        self.matrix_container.hide()
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

        self.overview_panel.setLayout(self.overview_layout)
        self.overview_panel_title = QLabel('<h1>Project Overview [ Under Construction :) ]</h1>')
        self.overview_back_button = QPushButton("Back")
        self.overview_back_button.setFixedSize(slim_button_size)
        self.overview_back_button.clicked.connect(self.back_callback)
        self.overview_layout.addWidget(self.overview_panel_title, 0, 0, 1, 3)
        self.overview_layout.addWidget(self.overview_back_button, 3, 0, 1, 1)

        self.main_widget = QStackedWidget(self)
        self.main_widget.addWidget(self.main_panel)           # (0) main_panel
        self.main_widget.addWidget(self.docs_panel)           # (1) docs_panel
        self.main_widget.addWidget(self.demos_panel)          # (2) demos_panel
        self.main_widget.addWidget(self.remote_viewer_panel)  # (3) remote_viewer_panel
        self.main_widget.addWidget(self.overview_panel)       # (4) overview_panel

        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem('Main')
        self.pageComboBox.addItem('Neuroglancer Local')
        self.pageComboBox.addItem('Documentation')
        self.pageComboBox.addItem('Demos')
        self.pageComboBox.addItem('Remote Viewer')
        self.pageComboBox.addItem('Overview') #1102+
        self.pageComboBox.addItem('Project View')
        self.pageComboBox.activated[int].connect(self.main_widget.setCurrentIndex)

        self.main_panel.setLayout(self.main_panel_layout)
        self.setCentralWidget(self.main_widget)
        self.toolbar.setCursor(QCursor(Qt.PointingHandCursor))
        self.main_widget.setCurrentIndex(MAIN_PANEL_STARTING_INDEX)

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

    def show_hide_low_low_side_widgets(self):
        '''Called onStartProject and onAlignmentEnd'''

        if is_cur_scale_aligned():
            self.main_details_subwidgetA.show()
            self.main_details_subwidgetB.show()
            self.matrix_container.show()
            self.history_widget.show()
        else:
            self.main_details_subwidgetA.hide()
            self.main_details_subwidgetB.hide()
            self.matrix_container.hide()
            self.history_widget.hide()

    def is_project_open(self):
        try:
            if cfg.data.dest() == '':
                return False
            else:
                return True
        except:
            logger.warning('No data model yet')

    def enter_exit_match_point_mode(self):
        if self._is_mp_mode == False:

            self.extra_header_text_label.setText('Match Point Mode')
            self._is_mp_mode = True
            self.hud.post('Entering Match Point Mode.')
            self.new_control_panel.hide()
            # self.details_banner.hide()
            self.show_hide_python_callback(force_hide=True)
            self.show_hide_snr_plot_callback(force_hide=True)
            self.show_hide_project_tree_callback(force_hide=True)
            # self.low_low_widget.hide()
            self.matchpoint_controls.show()
            self.update_match_point_snr()
            self.mp_marker_size_spinbox.setValue(cfg.data['user_settings']['mp_marker_size'])
            self.mp_marker_lineweight_spinbox.setValue(cfg.data['user_settings']['mp_marker_lineweight'])
            self.initNgServer(scales=cfg.data.scales())

        else:
            self._is_mp_mode = False
            self.extra_header_text_label.setText('')
            self.hud.post('Exiting Match Point Mode.')
            self.updateLowLowWidgetB()
            self.normal_view()


    def update_match_point_snr(self):
        self.matchpoint_text_snr.setHtml(f'<h4>{cfg.data.snr()}</h4>')


    def normal_view(self):

        if cfg.data is None:
            self.image_panel_stack_widget.setCurrentIndex(2)
        else:
            self.image_panel_stack_widget.setCurrentIndex(1)

        self.new_control_panel.show()
        self.viewer_and_banner_widget.show()
        self.full_window_controls.hide()
        self.extra_header_text_label.setText('')
        # self.main_widget.setCurrentIndex(0)
        # self.image_panel_stack_widget.setCurrentIndex(1)

        self.details_banner.show()
        self.low_low_widget.show()

        if is_cur_scale_aligned():
            self.updateStatusTips()
            self.main_details_subwidgetA.show()
            self.main_details_subwidgetB.show()
            self.matrix_container.show()
            self.history_widget.show()
        else:
            self.main_details_subwidgetA.hide()
            self.main_details_subwidgetB.hide()
            self.matrix_container.hide()
            self.history_widget.hide()

        self._is_mp_mode = False
        self.matchpoint_controls.hide()
        self.hud.show()

        self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))

        self.show_hide_project_tree_callback(force_hide=True)
        self.show_hide_snr_plot_callback(force_hide=True)
        self.show_hide_python_callback(force_hide=True)
        # self.ng_workers[cfg.data.s()].match_point_mode = False
        # self.initNgServer(scales=[cfg.data.s()]) #1122-


    def expand_viewer_size(self):

        if self._is_viewer_expanded:
            self.hud.post('Collapsing Viewer')
            self._is_viewer_expanded = False
            self.normal_view()
            self.expandViewAction.setIcon(qta.icon('mdi.arrow-expand-all', color=ICON_COLOR))
            self.expandViewAction.setToolTip('Set Expanded Viewer Size')

        else:
            self.hud.post('Expanding Viewer')
            self._is_viewer_expanded = True
            # self.full_window_controls.show()
            self.main_widget.setCurrentIndex(0)
            # self.image_panel_stack_widget.setCurrentIndex(1)
            self.new_control_panel.hide()
            self.details_banner.hide()
            self.low_low_widget.hide()
            self.hud.hide()
            self.matchpoint_controls.hide()
            self.viewer_and_banner_widget.show()
            self.show_hide_project_tree_callback(force_hide=True)
            self.show_hide_snr_plot_callback(force_hide=True)
            self.show_hide_python_callback(force_hide=True)
            self.expandViewAction.setIcon(qta.icon('mdi.arrow-collapse-all', color=ICON_COLOR))
            self.expandViewAction.setToolTip('Set Normal Viewer Size')

        self.initNgServer()


    def set_viewer_layout_1(self):
        self._layout = 1
        self.initNgServer()


    def set_viewer_layout_2(self):
        self._layout = 2
        self.initNgServer()


    def expand_plot_size(self):
        self._is_mp_mode = False
        self.full_window_controls.show()
        self.main_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.details_banner.hide()
        self.low_low_widget.hide()
        self.hud.hide()
        self.matchpoint_controls.hide()
        self.viewer_and_banner_widget.hide()
        self.show_hide_project_tree_callback(force_hide=True)
        self.show_hide_python_callback(force_hide=True)
        self.show_hide_snr_plot_callback(force_show=True)
        # self.initNgServer()

    def expand_treeview_size(self):
        self.full_window_controls.show()
        self.extra_header_text_label.setText('')
        self.main_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.details_banner.hide()
        self.low_low_widget.hide()
        self.hud.hide()
        self.matchpoint_controls.hide()
        self.viewer_and_banner_widget.hide()
        self.show_hide_snr_plot_callback(force_hide=True)
        self.show_hide_python_callback(force_hide=True)
        self.show_hide_project_tree_callback(force_show=True)

        # self.initNgServer()

    def expand_python_size(self):

        self.full_window_controls.show()
        self.extra_header_text_label.setText('')
        self._is_mp_mode = False
        self.main_widget.setCurrentIndex(0)
        self.new_control_panel.hide()
        self.details_banner.hide()
        self.low_low_widget.hide()
        self.hud.hide()
        self.matchpoint_controls.hide()

        self.viewer_and_banner_widget.hide()
        self.show_hide_project_tree_callback(force_hide=True)
        self.show_hide_snr_plot_callback(force_hide=True)
        self.show_hide_python_callback(force_show=True)

        # self.initNgServer()


    #1103
    def initOverviewPanel(self, destination=None):
        if destination == None:
            destination = os.path.join(cfg.data.dest(), 'thumbnails')

        logger.info('Initializing Overview Panel...')
        logger.info('thumbnails directory: %s' % str(destination))

        preview = namedtuple("preview", "id title image")

        self.previewmodel = PreviewModel()

        self.thumbnails = {}
        self.thumbnail_items = {}
        for n, fn in enumerate(glob.glob(os.path.join(destination, '*.tif'))):
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
        # self.thumbnail_table.setItemDelegateForColumn(1, PreviewDelegate())

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

    #spacing #contentsmargin
    def setWidgetSpacing(self):
        # self.main_navigation_layout.setContentsMargins(0, 0, 0, 0)
        self.main_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.main_details_subwidgetA.setContentsMargins(0, 0, 0, 0)
        self.main_details_subwidgetB.setContentsMargins(0, 0, 0, 0)
        self.new_main_widget_vlayout.setContentsMargins(0, 0, 0, 0)
        self.show_hide_main_features_vlayout.setContentsMargins(4, 4, 4, 10)
        self.ng_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.ng_panel_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.ng_browser_layout.setContentsMargins(0, 0, 0, 0)
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.details_banner.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.setContentsMargins(0, 0, 0, 0)
        self.swim_grid.setContentsMargins(0, 0, 0, 0)
        self.scale_ctrl_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.toggle_bounding_hlayout.setContentsMargins(0, 0, 0, 0)
        self.new_control_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.matrix_container_vlayout.setContentsMargins(0, 0, 0, 0)
        self.full_window_controls_hlayout.setContentsMargins(8, 0, 8, 0)
        # self.snr_plot_and_control_layout.setContentsMargins(8, 4, 8, 4)
        self.details_banner_layout.setContentsMargins(8, 0, 8, 0)
        self.new_control_panel.setContentsMargins(8, 4, 8, 4)
        self.projectdata_treeview.setContentsMargins(8, 4, 8, 4)
        self.python_console.setContentsMargins(8, 4, 8, 4)
        self.low_low_gridlayout.setContentsMargins(8, 4, 8, 4)

        # self.show_hide_main_features_vlayout.setSpacing(2)

        # self.image_panel_stack_widget.resize(cfg.WIDTH, 1000)

        self.pbar_layout.setContentsMargins(0, 0, 0, 0)
        # self.pbar_container.setFixedHeight(26)
        self.pbar.setFixedHeight(18)

        # self.python_console.resize(cfg.WIDTH, 120)
        # self.projectdata_treeview_widget.resize(cfg.WIDTH, 120)
        # self.hud.setFixedHeight(140)

        # self.new_main_widget_vlayout.setSpacing(2) #1110+
        self.show_hide_main_features_vlayout.setSpacing(4)
        self.show_hide_main_features_widget.setMaximumHeight(90) # was 120
        self.low_low_widget.setMaximumHeight(100) # was 120

        # self.snr_plot.setMinimumHeight(78) #1109-
        # self.matchpoint_controls.setMaximumHeight(170) #1110-
        self.matchpoint_text_snr.setMaximumHeight(20)

        self.main_details_subwidgetA.setMinimumWidth(128)
        self.main_details_subwidgetB.setMinimumWidth(128)
        self.matrix_container.setMinimumWidth(128)
        self.history_widget.setMinimumWidth(128)


    def clear_snr_plot(self):
        try:
            self.snr_plot.clear()
            self.clear_snr_plot_checkboxes()
        except:
            logger.warning('Cannot clear SNR plot. Does it exist yet?')

    def clear_snr_plot_checkboxes(self):
        for i in reversed(range(self.snr_plot_controls_hlayout.count())):
            self.snr_plot_controls_hlayout.removeItem(self.snr_plot_controls_hlayout.itemAt(i))


    def initSnrPlot(self, s=None):
        '''
        cfg.main_window.snr_points.data <- numpy.ndarray of snr data points
        type(cfg.main_window.snr_points.data)
        AlignEM [11]: numpy.ndarray
        cfg.main_window.snr_points.data[0]
        AlignEM [13]: (1., 14.73061687, -1., None, None, None, None, None,
          PyQt5.QtCore.QRectF(0.0, 0.0, 8.0, 8.0),
          PyQt5.QtCore.QRectF(57.99999999999997, 60.602795211005855, 8.0, 8.0), 4.)
        '''
        self.clear_snr_plot_checkboxes()

        self._snr_checkboxes = dict()

        # self._snr_checkboxes = dict()
        for i, s in enumerate(cfg.data.scales()[::-1]):
            self._snr_checkboxes[s] = QCheckBox()
            self._snr_checkboxes[s].setText('s' + str(get_scale_val(s)))
            self.snr_plot_controls_hlayout.addWidget(self._snr_checkboxes[s], alignment=Qt.AlignLeft)
            self._snr_checkboxes[s].setChecked(True)
            self._snr_checkboxes[s].setStyleSheet('border-color: %s' % self._snr_plot_colors[i])
            self._snr_checkboxes[s].clicked.connect(self.updateSnrPlot)
            self._snr_checkboxes[s].setToolTip('On/Off SNR Plot Scale %d' % get_scale_val(s))
            if is_arg_scale_aligned(scale=s):
                self._snr_checkboxes[s].show()
            else:
                self._snr_checkboxes[s].hide()
        self.snr_plot_controls_hlayout.addStretch()
        self.updateSnrPlot()

    def updateSnrPlot(self):
        '''Update SNR plot widget based on checked/unchecked state of checkboxes'''
        # logger.info('Updating SNR Plot...')
        self.snr_plot.clear()
        for i, scale in enumerate(cfg.data.scales()[::-1]):
            if self._snr_checkboxes[scale].isChecked():
                if is_arg_scale_aligned(scale=scale):
                    self.show_snr(scale=scale)
            cfg.data.scales().index(scale)
            color = self._snr_plot_colors[cfg.data.scales().index(scale)]
            self._snr_checkboxes[scale].setStyleSheet('border-color: %s; border-width: 3; border-style: solid;' % color)
            # self._snr_checkboxes[s].setStyleSheet('background-color: %s' % color)
        max_snr = cfg.data.snr_max_all_scales()
        if is_any_scale_aligned_and_generated():
            try:
                if max_snr != None:  self.snr_plot.setLimits(xMin=0, xMax=cfg.data.n_layers(), yMin=0, yMax=max_snr + 1)
            except:
                logger.warning('updateSnrPlot encountered a problem setting plot limits')

    def show_snr(self, scale=None):
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
        brush = self._snr_plot_brushes[cfg.data.scales().index(scale)]
        # color = self._snr_plot_colors[cfg.data.scales().index(s)]
        # self._snr_checkboxes[s].setStyleSheet('border-color: %s' % color)
        self.snr_points = pg.ScatterPlotItem(
            size=7,
            pen=pg.mkPen(None),
            brush=brush,
            hoverable=True,
            # hoverSymbol='s',
            hoverSize=10,
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

    def onSnrClick(self, plot, points):
        '''
        type(obj): <class 'pyqtgraph.graphicsItems.ScatterPlotItem.ScatterPlotItem'>
        type(points): <class 'numpy.ndarray'>
        '''
        index = int(points[0].pos()[0])
        snr = float(points[0].pos()[1])
        clickedPen = pg.mkPen({'color': "#f3f6fb", 'width': 3})
        for p in self.last_snr_click:
            # p.resetPen()
            p.resetBrush()
        for p in points:
            p.setBrush(pg.mkBrush('#FF0000'))
            # p.setPen(clickedPen)
        self.last_snr_click = points
        self.jump_to(index)

    def initPbar(self):
        logger.info('Initializing progress bar')
        self.statusBar = self.statusBar()
        self.pbar = QProgressBar(self)
        # self.statusBar.addPermanentWidget(self.pbar)
        # self.statusBar.addWidget(self.pbar)
        self.pbar.setAlignment(Qt.AlignCenter)
        # self.pbar.setGeometry(0, 0, 250, 50)
        self.pbar.hide()

    def initJupyter(self):
        logger.info('Initializing Jupyter Console')
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

    def back_callback(self):
        logger.info("Returning Home...")
        self.main_widget.setCurrentIndex(0)
        if cfg.data is None:
            self.image_panel_stack_widget.setCurrentIndex(2)
        else:
            self.image_panel_stack_widget.setCurrentIndex(1)

    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self.historyListWidget:
            menu = QMenu()
            self.history_view_action = QAction('View')
            self.history_view_action.triggered.connect(self.view_historical_alignment)
            self.history_swap_action = QAction('Set')
            self.history_swap_action.triggered.connect(self.swap_historical_alignment)
            self.history_rename_action = QAction('Rename')
            self.history_rename_action.triggered.connect(self.rename_historical_alignment)
            self.history_delete_action = QAction('Delete')
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
