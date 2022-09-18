#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os, sys, copy, json, inspect, logging, textwrap, operator, threading
from pathlib import Path
import qtpy
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QSpacerItem, QMessageBox, \
    QComboBox, QGroupBox, QSplitter, QTreeView, QHeaderView, QSplashScreen, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsDropShadowEffect
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication, QKeySequence, QColor, QCursor, QMovie, QImageReader
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, QTimer, Slot, Signal, QThread
from qtpy.QtWebEngineWidgets import *
import qtawesome as qta
import pyqtgraph as pg
import numpy as np
from glob import glob
import dask.array as da
import zarr
import time
import asyncio
import neuroglancer.server

import cProfile, pstats, io
from pstats import SortKey

import src.config as cfg
from src.config import ICON_COLOR
from src.helpers import *
from src.data_model import DataModel
from src.image_funcs import get_image_size
from src.compute_affines import compute_affines
from src.generate_aligned import generate_aligned
from src.generate_scales import generate_scales
from src.generate_zarr import generate_zarr
from src.ng_viewer import NgViewer
from src.background_worker import BackgroundWorker
# from src.napari_test import napari_test
from src.image_library import ImageLibrary
from src.ui.head_up_display import HeadUpDisplay
from src.ui.toggle_switch import ToggleSwitch
from src.ui.json_treeview import JsonModel
from src.ui.kimage_window import KImageWindow
from src.ui.snr_plot import SnrPlot
from src.ui.python_console import PythonConsole
from src.ui.PyQtImageStackViewer import QtImageStackViewer
from src.ui.PyQtImageViewer import QtImageViewer
from src.ui.splash import SplashScreen
from src.ui.dialogs import DefaultsForm
from src.zarr_funcs import tiffs2MultiTiff, get_zarr_tensor, generate_zarr_scales

__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    resized = Signal()
    def __init__(self, title="AlignEM-SWiFT"):

        app = QApplication.instance()
        self.app = QApplication.instance()
        if app is None:
            logger.warning("Creating new QApplication instance.")
            app = QApplication([])

        check_for_binaries()

        logger.info('Initializing Main Window')
        QMainWindow.__init__(self)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(QPixmap('sims.png')))
        self.init_dir = os.getcwd()

        fg = self.frameGeometry()
        fg.moveCenter(QGuiApplication.primaryScreen().availableGeometry().center())
        self.move(fg.topLeft())
        logger.info("Initializing Thread Pool")
        self.threadpool = QThreadPool(self)  # important consideration is this 'self' reference
        self.threadpool.setExpiryTimeout(3000) # ms

        logger.info("Initializing Image Library")
        cfg.image_library = ImageLibrary() # SmartImageLibrary()
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

        if qtpy.QT6:
            QImageReader.setAllocationLimit(4000) #PySide6

        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())

        self.project_progress = 0
        self.project_aligned_scales = []
        # self.scales_combobox_switch = 0
        self.scales_combobox_switch = 1
        self.jump_to_worst_ticker = 1  # begin iter at 1 b/c first image has no ref
        self.jump_to_best_ticker = 0
        
        # PySide6 Only
        logger.info("Initializing Qt WebEngine")
        self.view = QWebEngineView()
        # PySide6-Only Options:
        if qtpy.QT6:
            logger.info('Setting Qt6-specific browser settings')
            self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
            self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        # self.browser.setPage(CustomWebEnginePage(self)) # Open clicked links in new window

        self.aligned_scales = []
        
        self.panel_list = []
        self.match_point_mode = False

        '''Initialize Status Bar'''
        logger.info('Initializing Status Bar')

        self.statusBar = self.statusBar()
        self.statusBar.setMaximumHeight(22)
        self.pbar = QProgressBar(self)
        # self.pbar.setGeometry(30, 40, 200, 25)
        # self.pbar.setStyleSheet("QLineEdit { background-color: yellow }")
        self.statusBar.addPermanentWidget(self.pbar)
        self.pbar.setMaximumWidth(120)
        self.pbar.setMaximumHeight(22)
        self.pbar.hide()

        '''Initialize Jupyter Console'''
        self.initJupyter()

        cfg.defaults_form = DefaultsForm(parent=self)

        logger.info("Initializing Data Model")
        cfg.data = DataModel()

        '''Initialize Menu'''
        logger.info('Initializing Menu')
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setFixedHeight(20)
        self.menu.setCursor(QCursor(Qt.PointingHandCursor))
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

        self._unsaved_changes = False
        self._up = 0

        self._working = False

        self.resized.connect(self.clear_zoom)


        #menu
        #   0:MenuName
        #   1:Shortcut-or-None
        #   2:Action-Function
        #   3:Checkbox (None,False,True)
        #   4:Checkbox-Group-Name (None,string),
        #   5:User-Data
        ml = [
            ['&File',
             [
                 ['&Home', 'Ctrl+H', self.back_callback, None, None, None],
                 ['&New Project', 'Ctrl+N', self.new_project, None, None, None],
                 ['&Open Project', 'Ctrl+O', self.open_project, None, None, None],
                 ['&Save Project', 'Ctrl+S', self.save_project, None, None, None],
                 # ['Rename Project', None, self.rename_project, None, None, None],
                 ['Restart Python Kernel', None, self.restart_python_kernel, None, None, None],
                 ['Exit', 'Ctrl+Q', self.exit_app, None, None, None]
             ]
             ],

            ['&View',
             [
                 ['Set Normal View', 'None', self.set_normal_view, None, None, None],
                 ['Project JSON', 'Ctrl+J', self.project_view_callback, None, None, None],
                 ['Python Console', None, self.show_python_console, None, None, None],
                 ['SNR Plot', None, self.show_snr_plot, None, None, None],
                 ['Splash Screen', None, self.show_splash, None, None, None],
                 ['Theme',
                  [
                      ['Default Theme', None, self.apply_default_style, None, None, None],
                      ['Daylight Theme', None, self.apply_daylight_style, None, None, None],
                      ['Moonlit Theme', None, self.apply_moonlit_style, None, None, None],
                      ['Midnight Theme', None, self.apply_midnight_style, None, None, None],
                  ]
                  ],
             ]
             ],

            ['&Tools',
             [
                 ['Go To Next Worst SNR', None, self.jump_to_worst_snr, None, None, None],
                 ['Go To Next Best SNR', None, self.jump_to_best_snr, None, None, None],
                 ['Apply Project Defaults', None, cfg.data.set_defaults, None, None, None],
                 ['Show &K Image', 'Ctrl+K', self.view_k_img, None, None, None],
                 ['&Write Multipage Tifs', 'None', self.write_paged_tiffs, None, None, None],
                 ['&Match Point Align Mode',
                  [
                      ['Toggle &Match Point Mode', 'Ctrl+M', self.toggle_match_point_align, None, False, True],
                      ['&Remove All Match Points', 'Ctrl+R', self.clear_match_points, None, None, None],
                  ]
                  ],
                 ['&Advanced',
                  [
                      ['Toggle Zarr Controls', None, self.toggle_zarr_controls, None, None, None],
                  ]
                  ],
             ]
             ],


            ['&Run',
             [
                 ['Create Zarr Scales', None, generate_zarr_scales, None, None, None],
                 ['Remote Neuroglancer Server', None, self.remote_view, None, None, None],
                 # ['Napari', None, napari_test, None, None, None],
                 ['Google', None, self.google, None, None, None],

             ]
             ],

            ['&Debug',
             [
                 ['Test WebGL', None, self.webgl2_test, None, None, None],
                 ['Check GPU Configuration', None, self.gpu_config, None, None, None],
                 ['Show SNR List', None, self.show_snr_list, None, None, None],
                 ['Show Zarr Info', None, self.show_zarr_info, None, None, None],
                 ['Show Environment', None, self.show_run_path, None, None, None],
                 ['Show Module Search Path', None, self.show_module_search_path, None, None, None],
                 ['Print Sanity Check', None, print_sanity_check, None, None, None],
                 ['Print Project Tree', None, print_project_tree, None, None, None],
                 ['Print Image Library', None, self.print_image_library, None, None, None],
                 ['Print Single Alignment Layer', None, print_alignment_layer, None, None, None],
                 ['Create Multipage TIF', None, create_paged_tiff, None, None, None],

             ]
             ],

            ['&Help',
             [
                 ['AlignEM-SWiFT Documentation', None, self.documentation_view, None, None, None],
             ]
             ],
        ]
        self.build_menu_from_list(self.menu, ml)


        '''Initialize UI'''
        logger.info('Initializing UI')
        self.initUI()
        self.initShortcuts()

        logger.info('Applying Stylesheet')
        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        # self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())  # must be after QMainWindow.__init__(self)

        # self.img_panels['ref'].scaled.connect(self.img_panels['base'].set_transform)
        # self.img_panels['base'].scaled.connect(self.img_panels['ref'].set_transform)
        # 
        # self.img_panels['ref'].scaled.connect(self.img_panels['base'].set_transform)
        # self.img_panels['base'].scaled.connect(self.img_panels['ref'].set_transform)
        
        # self.img_panels['ref'].viewChanged.connect(self.img_panels['base'].updateViewer())
        # self.img_panels['base'].viewChanged.connect(self.img_panels['ref'].updateViewer())

        # #orig #0912
        # bindScrollBars(self.img_panels['ref'].horizontalScrollBar(), self.img_panels['base'].horizontalScrollBar())
        # bindScrollBars(self.img_panels['ref'].verticalScrollBar(), self.img_panels['base'].verticalScrollBar())

        self.set_idle()
    
    def build_menu_from_list(self, parent, menu_list):
        for item in menu_list:
            if type(item[1]) == type([]):
                sub = parent.addMenu(item[0])
                self.build_menu_from_list(sub, item[1])
            else:
                if item[0] == '-':
                    parent.addSeparator()
                else:
                    # menu item (action) with name | accel | callback
                    action = QAction(item[0], self)
                    if item[1] != None:
                        action.setShortcut(item[1])
                    if item[2] != None:
                        action.triggered.connect(item[2])
                        # if item[2] == self.not_yet:
                        #     action.setDisabled(True)
                    if item[3] != None:
                        action.setCheckable(True)
                        action.setChecked(item[3])
                    if item[4] != None:
                        if not (item[4] in self.action_groups):
                            self.action_groups[item[4]] = QActionGroup(self)
                        self.action_groups[item[4]].addAction(action) # KeyError: False
                    parent.addAction(action)


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


    def update_panels(self):
        '''Repaint the viewing port.'''
        logger.debug("MainWindow.update_panels:")
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()
    
    @Slot()
    def refresh_all_images(self):
        logger.info("MainWindow is refreshing all images (called by " + inspect.stack()[1].function + ")...")
        # self.image_panel.refresh_all_images()
    
    @Slot()
    def project_view_callback(self):
        logger.critical("project_view_callback called by " + inspect.stack()[1].function + "...")
        self.project_model.load(cfg.data.to_dict())
        self.project_view.show()
        self.main_widget.setCurrentIndex(4)

    @Slot()
    def run_scaling(self) -> None:
        logger.info("run_scaling:")
        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            self.set_idle()
            return
        else:
            pass

        self.set_status("Busy...")
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.hud('Requesting scale factors from user')

        if do_scales_exist():
            self.hud('This data was scaled already. Re-scaling now resets alignment progress.',
                          logging.WARNING)
            reply = QMessageBox.question(self, 'Verify Regenerate Scales',
                                         'Regenerating scales now will reset progress.\n\n'
                                         'Continue with rescaling?',
                                         QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                self.hud('Continuing With Rescaling...')
                self.clear_images()
                #
                # # for scale in scales():
                # #     scale_path = os.path.join(proj_path, scale, 'img')
                # #     try:
                # #         shutil.rmtree()
                #
                # self.hud('Removing Previously Generated Images...')
                # proj_path = cfg.data['data']['destination_path']
                # for scale in get_scales_list():
                #     if scale != 'scale_1':
                #         logger.info('Removing directory %s...' % scale)
                #         rm_dir = os.path.join(proj_path, scale)
                #         try:
                #             shutil.rmtree(rm_dir)
                #         except Exception as e:
                #             logger.warning('Failed to delete %s. Reason: %s' % (rm_dir, e))
                #
                #     elif scale == 1:
                #         clear_dir = os.path.join(proj_path, scale, 'img_aligned')
                #         logger.info('Clearing directory %s...' % clear_dir)
                #         for filename in os.listdir(clear_dir):
                #             file_path = os.path.join(clear_dir, filename)
                #             try:
                #                 if os.path.isfile(file_path) or os.path.islink(file_path):
                #                     os.unlink(file_path)
                #                 elif os.path.isdir(file_path):
                #                     shutil.rmtree(file_path)
                #             except Exception as e:
                #                 logger.warning('Failed to delete %s. Reason: %s' % (file_path, e))
                #
                # zarr_path = os.path.join(proj_path, 'alignments.zarr')
                # if os.path.exists(zarr_path):
                #     logger.info('Removing directory %s...' % zarr_path)
                #     try:
                #         shutil.rmtree(zarr_path)
                #     except Exception as e:
                #         logger.warning('Failed to delete %s. Reason: %s' % (zarr_path, e))
                #
                # self.update_panels() #!!
                # self.update_win_self()
                # self.hud('Done')

            else:
                self.hud('Rescaling canceled.')
                self.set_idle()
                return

        if do_scales_exist():
            default_scales = map(str, cfg.data.scale_vals_list())
        else:
            default_scales = ['1']
        input_val, ok = QInputDialog().getText(None, "Define Scales",
                                               "Please enter your scaling factors separated by spaces." \
                                               "\n\nFor example, to generate 1x 2x and 4x scale datasets: 1 2 4\n\n"
                                               "Your current scales: " + str(' '.join(default_scales)),
                                               echo=QLineEdit.Normal,
                                               text=' '.join(default_scales))
        
        if not ok:
            self.hud('Scaling Canceled. Scales Must Be Generated Before Aligning', logging.WARNING)
            self.set_idle()
            return
        
        if input_val == '':
            self.hud('Input Was Empty, Please Provide Scaling Factors', logging.WARNING)
            self.set_idle()
            logger.info('<<<< run_scaling')
            return
        cfg.data.set_scales_from_string(input_val)

        ########
        self.hud('Generating Scale Image Hierarchy For Levels %s...' % input_val)
        self.show_hud()
        self.set_status("Scaling...")
        try:
            self.worker = BackgroundWorker(fn=generate_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud('Generating Scales Triggered an Exception - Returning', logging.ERROR)

        cfg.data.link_all_stacks()
        cfg.data.set_defaults()
        cfg.data['data']['current_scale'] = cfg.data.scales()[-1]
        self.set_status('Creating Zarr Arrays...')
        try:
            generate_zarr_scales()
            # cfg.image_library.set_zarr_refs()
        except:
            logger.warning('An Exception Was Raised While Creating Scaled Zarr Arrays')
            print_exception()

        self.aligned_scales = []
        self.load_unaligned_stacks()
        self.update_unaligned_view()
        self.read_project_data_update_gui()
        self.set_progress_stage_2()
        self.reload_scales_combobox()  # 0529 #0713+
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        self.update_scale_controls()
        self.save_project_to_file()
        self.hud.done()
        self.set_idle()


    def run_scaling_auto(self):
        self.set_status("Scaling...")
        self.show_hud()
        try:
            self.worker = BackgroundWorker(fn=generate_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            logger.warning('Autoscaling Triggered An Exception')
        self.hud('Generating Zarr Scales...')
        cfg.data.link_all_stacks()
        cfg.data.set_defaults()
        cfg.data['data']['current_scale'] = cfg.data.scales()[-1]
        try:
            generate_zarr_scales()
            # cfg.image_library.set_zarr_refs()
        except:
            logger.warning('An Exception Was Raised While Creating Scaled Zarr Arrays')
            print_exception()
        self.aligned_scales = []
        self.load_unaligned_stacks()
        self.update_unaligned_view()
        self.read_project_data_update_gui()
        self.set_progress_stage_2()
        self.reload_scales_combobox()  # 0529 #0713+
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        self.update_scale_controls()
        self.save_project_to_file()
        self.hud.done()
        self.set_idle()

    
    @Slot()
    def run_alignment(self, use_scale) -> None:
        logger.info('run_alignment:')
        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            return
        else:
            pass
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.read_gui_update_project_data()
        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud(warning_msg, logging.WARNING)
            return
        self.img_panels['aligned'].imageViewer.clearImage()
        self.set_status('Aligning Using SWiFT-IR...')
        alignment_option = cfg.data['data']['scales'][use_scale]['method_data']['alignment_option']
        if alignment_option == 'init_affine':
            self.hud.post("Initializing Affine Transforms For Scale Factor %d..." % (get_scale_val(use_scale)))
        else:
            self.hud.post("Refining Affine Transform For Scale Factor d..." % (get_scale_val(use_scale)))
        self.show_hud()
        # self.al_status_checkbox.setChecked(False)
        try:
            self.worker = BackgroundWorker(fn=compute_affines(
                use_scale=use_scale, start_layer=0, num_layers=-1))
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud('An Exception Was Raised During Alignment.', logging.ERROR)
            return

        # if not is_cur_scale_aligned():
        #     self.hud('Current Scale Was Not Aligned.', logging.ERROR)
        #     self.set_idle()
        #     return
        self.update_alignment_details()
        # self.hud('Alignment Succeeded.')
        self.hud.done()
        self.set_status('Generating Alignment...')
        self.hud('Generating Aligned Images...')
        try:
            self.worker = BackgroundWorker(fn=generate_aligned(use_scale=use_scale, start_layer=0, num_layers=-1))
            self.threadpool.start(self.worker)
        except:

            print_exception()
            self.hud('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.',logging.ERROR)
            self.set_idle()
            return

        # if are_aligned_images_generated():
        self.update_aligned_view()
        if self.main_panel_bottom_widget.currentIndex() == 1:
           self.show_snr_plot()

        # self.update_panels()  # 0721+
        self.hud.done()
        self.save_project_to_file() #0908+
        self.set_progress_stage_3()
        if are_aligned_images_generated():
            self.aligned_scales.append(cfg.data.scale())
            self.img_panels['aligned'].show_ng_button()
        else:
            self.img_panels['aligned'].hide_ng_button()
        if self.image_panel_stack_widget.currentIndex() == 1:
            self.reload_ng()
    
    @Slot()
    def run_regenerate_alignment(self, use_scale) -> None:
        logger.info('run_regenerate_alignment:')
        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            self.set_idle()
            return
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.read_gui_update_project_data()
        if not is_cur_scale_aligned():
            self.hud('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING)
            self.set_idle()
            return
        self.img_panels['aligned'].imageViewer.clearImage()
        self.set_busy()
        self.hud('Generating Aligned Images...')
        try:
            self.worker = BackgroundWorker(fn=generate_aligned(use_scale=use_scale, start_layer=0, num_layers=-1))
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud('Something Went Wrong During Image Generation.', logging.ERROR)
            self.set_idle()
            return
        self.hud.done()
        # self.hud('Image Generation Complete')
        if are_aligned_images_generated():
            logger.info('are_aligned_images_generated() returned True. Setting user progress to stage 3...')
            self.set_progress_stage_3()
            self.read_project_data_update_gui()
            self.update_aligned_view()
            if are_aligned_images_generated():
                # self.img_panels['aligned'].imageViewer.show_ng_button()
                self.img_panels['aligned'].show_ng_button()
            else:
                # self.img_panels['aligned'].imageViewer.hide_ng_button()
                self.img_panels['aligned'].hide_ng_button()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
            self.hud("Regenerate Complete")
        else:
            print_exception()
            self.hud('Image Generation Failed Unexpectedly. Try Re-aligning.', logging.ERROR)
            self.set_idle()
            return
        self.update_win_self()
        self.save_project_to_file() #0908+
        # self.has_unsaved_changes() #0908-
    
    def run_export(self):
        logger.info('Exporting to Zarr format...')
        if self._working == True:
           self.hud('Another Process is Already Running', logging.WARNING)
           self.set_idle()
           return

        self.hud('Exporting...')
        if not are_aligned_images_generated():
            self.hud('Current Scale Must be Aligned Before It Can be Exported', logging.WARNING)
            logger.debug('(!) There is no alignment at this scale to export. Returning from export_zarr().')
            self.show_warning('No Alignment', 'Nothing To Export.\n\n'
                                         'This is a Typical Alignment Workflow:\n'
                                         '(1) Open a project or import images and save.\n'
                                         '(2) Generate a set of scaled images and save.\n'
                                         '--> (3) Align each scale starting with the coarsest.'
                                         )
            self.set_idle()
            return
        
        self.set_status('Exporting...')
        self.hud('Generating Neuroglancer-Compatible Zarr...')
        src = os.path.abspath(cfg.data['data']['destination_path'])
        out = os.path.abspath(os.path.join(src, 'alignments.zarr'))
        self.hud('  Compression Level: %s' %  self.clevel_input.text())
        self.hud('  Compression Type: %s' %  self.cname_combobox.currentText())
        try:
            self.worker = BackgroundWorker(fn=generate_zarr(src=src, out=out))
            self.threadpool.start(self.worker)
        except:

            print_exception()
            logger.error('Zarr Export Failed')
            self.set_idle()
            return
        self.has_unsaved_changes()
        self.set_idle()
        self.hud('Process Finished')

    @Slot()
    def clear_all_skips_callback(self):
        if cfg.data.are_there_any_skips():
            reply = QMessageBox.question(self,
                                         'Verify Reset Skips',
                                         'Please verify your action to clear all skips. '
                                         'This makes all images unskipped.',
                                         QMessageBox.Cancel | QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                try:
                    self.hud('Resetting Skips...')
                    cfg.data.clear_all_skips()
                except:
                    print_exception()
                    self.hud('Something Went Wrong', logging.WARNING)
        else:
            self.hud('There Are No Skips To Clear.', logging.WARNING)
            return

    def update_win_self(self):
        self.update()  # repaint
    
    @Slot()
    def apply_all_callback(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        swim_val = self.get_swim_input()
        whitening_val = self.get_whitening_input()
        scales_dict = cfg.data['data']['scales']
        self.hud('Applying these alignment settings to data...')
        self.hud('  SWIM Window  : %s' % str(swim_val))
        self.hud('  Whitening    : %s' % str(whitening_val))
        for scale_key in scales_dict.keys():
            scale = scales_dict[scale_key]
            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                atrm = layer['align_to_ref_method']
                mdata = atrm['method_data']
                mdata['win_scale_factor'] = swim_val
                mdata['whitening_factor'] = whitening_val
    
    @Slot()
    def update_scale_controls(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev scale buttons depending on current scale.
        (2) Set the enabled/disabled state of the align-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        logger.info('Updating Scale Controls (Called by %s)...' % inspect.stack()[1].function)
        if self.project_progress >= 2:
            if cfg.data.n_scales() == 1:
                self.scale_down_button.setEnabled(False)
                self.scale_up_button.setEnabled(False)
                self.align_all_button.setEnabled(True)
            else:
                cur_index = self.scales_combobox.currentIndex()
                if cur_index == 0:
                    self.scale_up_button.setEnabled(False)
                    self.scale_down_button.setEnabled(True)
                elif cfg.data.n_scales() == cur_index + 1:
                    self.scale_up_button.setEnabled(True)
                    self.scale_down_button.setEnabled(False)
                else:
                    self.scale_up_button.setEnabled(True)
                    self.scale_down_button.setEnabled(True)
            if cfg.data.is_alignable():
                self.align_all_button.setEnabled(True)
            else:
                self.align_all_button.setEnabled(False)
            if are_aligned_images_generated():
                # self.img_panels['aligned'].imageViewer.show_ng_button()
                self.img_panels['aligned'].show_ng_button()
            else:
                # self.img_panels['aligned'].imageViewer.hide_ng_button()
                self.img_panels['aligned'].hide_ng_button()

            self.jump_validator = QIntValidator(0, cfg.data.n_imgs())
            self.update_alignment_details() #Shoehorn
    
    @Slot()
    def update_alignment_details(self) -> None:
        '''Piggy-backs its updating with 'update_scale_controls'
        Update alignment details in the Alignment control panel group box.'''
        # logger.info('Updating Alignment Banner Details')
        al_stack = cfg.data['data']['scales'][cfg.data.scale()]['alignment_stack']
        # self.al_status_checkbox.setChecked(is_cur_scale_aligned())
        dict = {'init_affine':'Initialize Affine','refine_affine':'Refine Affine','apply_affine':'Apply Affine'}
        method_str = dict[cfg.data['data']['scales'][cfg.data.scale()]['method_data']['alignment_option']]
        if is_cur_scale_aligned():
            self.alignment_status_label.setText("Is Aligned? Yes")
        else:
            self.alignment_status_label.setText("Is Aligned? No")
        scale_str = str(get_scale_val(cfg.data.scale()))
        try:
            img_size = get_image_size(al_stack[0]['images']['base']['filename'])
            self.align_label_resolution.setText('Scale %s [%sx%spx]' % (scale_str, img_size[0], img_size[1]))
        except:
            logger.warning('Unable To Determine Image Sizes. Project was likely renamed.')
        #Todo fix renaming bug where files are not relinked
        self.align_label_affine.setText(method_str)
        self.align_label_scales_remaining.setText('# Unaligned: %d' %
                                                  len(cfg.data.not_aligned_list()))
        # if not do_scales_exist():
        #     cur_scale_str = 'Scale: n/a'
        #     self.align_label_cur_scale.setText(cur_scale_str)
        # else:
        #     cur_scale_str = 'Scale: ' + str(scale_val(cfg.data.scale()))
        #     self.align_label_cur_scale.setText(cur_scale_str)

    
    @Slot()
    def get_auto_generate_state(self) -> bool:
        '''Simple get function to get boolean state of auto-generate toggle.'''
        return True if self.toggle_auto_generate.isChecked() else False
    
    @Slot()
    def toggle_auto_generate_callback(self) -> None:
        '''Update HUD with new toggle state. Not data-driven.'''
        if self.toggle_auto_generate.isChecked():
            self.hud('Images will be generated automatically after alignment')
        else:
            self.hud('Images will not be generated automatically after alignment')
    
    @Slot()
    def scale_up_button_callback(self) -> None:
        logger.critical('scale_up_button_callback:')
        '''Callback function for the Next Scale button (scales combobox may not be visible but controls the current scale).'''
        if not self.scale_up_button.isEnabled(): return
        if not are_images_imported(): return
        if self._working:
            self.hud('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            self.clear_images()
            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index - 1
            self.scales_combobox.setCurrentIndex(requested_index)  # Changes The Scale
            # if self.image_panel_stack_widget.currentIndex() == 0:
            self.read_project_data_update_gui()

            self.update_aligned_view()

            self.update_scale_controls()
            self.hud('Scale Changed to %d' % get_scale_val(cfg.data.scale()))
            if not cfg.data.is_alignable():
                self.hud('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
            if self.main_panel_bottom_widget.currentIndex() == 1:
                # self.plot_widget.clear() #0824
                self.show_snr_plot()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
        except:
            print_exception()
        # finally:
        #     self.scales_combobox_switch = 0
    
    @Slot()
    def scale_down_button_callback(self) -> None:
        logger.critical('scale_down_button_callback:')
        '''Callback function for the Previous Scale button (scales combobox may not be visible but controls the current scale).'''
        if not self.scale_down_button.isEnabled(): return
        if not are_images_imported(): return
        if self._working:
            self.hud('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            self.clear_images()

            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index + 1
            self.scales_combobox.setCurrentIndex(requested_index)  # changes scale
            if self.image_panel_stack_widget.currentIndex() == 0:
                self.read_project_data_update_gui()

            self.update_aligned_view()

            self.update_scale_controls()
            if not cfg.data.is_alignable():
                self.hud('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
            if self.main_panel_bottom_widget.currentIndex() == 1:
                self.plot_widget.clear()
                self.show_snr_plot()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
            self.hud('Viewing Scale Level %d' % get_scale_val(cfg.data.scale()))
        except:
            print_exception()
        # finally:
        #     self.scales_combobox_switch = 0
    
    @Slot()
    def show_snr_plot(self):
        self.main_widget.setCurrentIndex(0)
        if not are_images_imported():
            self.hud('No SNRs To View.', logging.WARNING)
            self.back_callback()
            return
        if not is_cur_scale_aligned():
            self.hud('No SNRs To View. Current Scale Is Not Aligned Yet.', logging.WARNING)
            self.back_callback()
            return
        self.clear_snr_plot()
        snr_list = cfg.data.snr_list()
        max_snr = max(snr_list)
        x_axis = [x for x in range(0, len(snr_list))]
        pen = pg.mkPen(color=(0, 0, 0), width=5, style=Qt.SolidLine)
        styles = {'color': '#ffffff', 'font-size': '13px'}
        # self.plot_widget.setBackground(QColor(100, 50, 254, 25))
        # self.snr_points = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(30, 255, 35, 255), hoverSize=14)
        self.snr_points = pg.ScatterPlotItem(
            size=9,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(30, 255, 35, 255),
            # hoverable=True,
            # hoverSymbol='s',
            hoverSize=13,
            # hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('g'),
        )
        if self.main_stylesheet == 'src/styles/daylight.qss':
            self.snr_plot.setBackground(None)
        else: self.snr_plot.setBackground('#000000')

        # self.snr_points.setFocusPolicy(Qt.NoFocus)
        self.snr_points.sigClicked.connect(self.onSnrClick)
        self.snr_points.addPoints(x_axis[1:], snr_list[1:])
        self.snr_plot.useOpenGL()
        self.snr_plot.setAntialiasing(True)
        # self.snr_plot.setAspectLocked(True)
        self.last_snr_click = []
        self.snr_plot.addItem(self.snr_points)
        self.snr_plot.showGrid(x=True,y=True, alpha = 200) # alpha: 0-255
        self.snr_plot.getPlotItem().enableAutoRange()
        self.main_panel_bottom_widget.setCurrentIndex(1)

    def clear_snr_plot(self):
        self.snr_plot.getPlotItem().enableAutoRange()
        self.snr_plot.clear()

    def onSnrClick(self, plot, points):
        '''
        type(obj): <class 'pyqtgraph.graphicsItems.ScatterPlotItem.ScatterPlotItem'>
        type(points): <class 'numpy.ndarray'>
        '''
        index = int(points[0].pos()[0])
        snr = float(points[0].pos()[1])
        print('SNR of Selected Layer: %.3f' % snr)
        clickedPen = pg.mkPen('b', width=2)
        for p in self.last_snr_click:
            p.resetPen()
        # print("clicked points", points)
        for p in points:
            p.setPen(clickedPen)
        self.last_snr_click = points
        self.jump_to_layer(index)

    def show_hud(self):
        self.main_panel_bottom_widget.setCurrentIndex(0)

    def initJupyter(self):
        logger.info('Initializing Jupyter Console')
        self.python_console = PythonConsole(customBanner='Caution - anything executed here is injected into the main '
                                                         'event loop of AlignEM-SWiFT - '
                                                         'As they say, with great power...!\n\n')
        # self.main_panel_bottom_widget.setCurrentIndex(1)
        # self.python_console.execute_command('import IPython; IPython.get_ipython().execution_count = 0')
        # self.python_console.execute_command('from src.config import *')
        # self.python_console.execute_command('from src.helpers import *')
        # self.python_console.execute_command('import src.config as cfg')
        # self.python_console.execute_command('import os, sys, zarr, neuroglancer')
        # self.python_console.clear()

    def shutdownJupyter(self):
        logger.info('Shutting Down Jupyter Kernel...')
        try:
            self.python_console.kernel_client.stop_channels()
            self.python_console.kernel_manager.shutdown_kernel()
        except:
            logger.warning('Unable to Shutdown Jupyter Console Kernel')

    def restart_python_kernel(self):
        self.hud('Restarting Python Kernel...')
        self.python_console.request_restart_kernel()
        self.hud.done()

    def show_python_console(self):
        self.main_panel_bottom_widget.setCurrentIndex(2)

    @Slot()
    def back_callback(self):
        logger.info("Returning Home...")
        self.main_widget.setCurrentIndex(0)
        self.image_panel_stack_widget.setCurrentIndex(0)
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.set_idle()

    @Slot()
    def update_skip_toggle(self):
        logger.info('update_skip_toggle:')
        scale = cfg.data['data']['scales'][cfg.data['data']['current_scale']]
        logger.info("scale['alignment_stack'][cfg.data['data']['current_layer']]['skipped'] = ",
                    scale['alignment_stack'][cfg.data['data']['current_layer']]['skipped'])
        self.toggle_skip.setChecked(not scale['alignment_stack'][cfg.data['data']['current_layer']]['skipped'])

    @Slot()
    def set_status(self, msg: str) -> None:
        self.statusBar.showMessage(msg)
    
    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')
    
    def apply_default_style(self):
        self.main_stylesheet = 'src/styles/default.qss'
        self.hud('Switching to Default Theme')
        # self.python_console.set_color_linux()
        self.python_console.set_color_none()
        self.hud.set_theme_default()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_daylight_style(self):
        '''Light stylesheet'''
        self.main_stylesheet = 'src/styles/daylight.qss'
        self.hud('Switching to Daylight Theme')
        self.python_console.set_color_none()
        self.hud.set_theme_light()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_moonlit_style(self):
        '''Grey stylesheet'''
        self.main_stylesheet = 'src/styles/moonlit.qss'
        self.hud('Switching to Moonlit Theme')
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_midnight_style(self):
        self.main_stylesheet = 'src/styles/midnight.qss'
        self.hud('Switching to Midnight Theme')
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')
        self.project_functions_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.images_and_scaling_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.alignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.postalignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.export_and_view_stack.setStyleSheet(open(self.main_stylesheet).read())

    def auto_set_user_progress(self):
        '''Set user progress (0 to 3). This is only called when user opens a data.'''
        logger.debug('auto_set_user_progress:')
        if is_any_scale_aligned_and_generated():  self.set_progress_stage_3()
        elif do_scales_exist():  self.set_progress_stage_2()
        elif is_destination_set():  self.set_progress_stage_1()
        else:  self.set_progress_stage_0()
    
    def set_user_progress(self, gb1: bool, gb2: bool, gb3: bool, gb4: bool) -> None:
        logger.debug('set_user_progress:')
        self.images_and_scaling_stack.setCurrentIndex((0, 1)[gb1])
        self.images_and_scaling_stack.setStyleSheet(
            ("""QGroupBox {border: 1px dotted #171d22;}""",
             open(self.main_stylesheet).read())[gb1])
        self.alignment_stack.setCurrentIndex((0, 1)[gb2])
        self.alignment_stack.setStyleSheet(
            ("""QGroupBox {border: 1px dotted #171d22;}""",
             open(self.main_stylesheet).read())[gb2])
        self.postalignment_stack.setCurrentIndex((0, 1)[gb3])
        self.postalignment_stack.setStyleSheet(
            ("""QGroupBox {border: 1px dotted #171d22;}""",
             open(self.main_stylesheet).read())[gb3])
        self.export_and_view_stack.setCurrentIndex((0, 1)[gb4])
        self.export_and_view_stack.setStyleSheet(
            ("""QGroupBox {border: 1px dotted #171d22;}""",
             open(self.main_stylesheet).read())[gb4])

    def cycle_user_progress(self):
        self._up += 1
        up = self._up % 4
        if up == 0:    self.set_progress_stage_1()
        elif up == 1:  self.set_progress_stage_2()
        elif up == 2:  self.set_progress_stage_3()
        elif up == 3:  self.set_progress_stage_0()
    
    def set_progress_stage_0(self):
        logger.critical(os.getcwd())
        if self.get_user_progress() != 0: self.hud('Reverting user progress to Project')
        self.set_user_progress(False, False, False, False)
        self.project_progress = 0
    
    def set_progress_stage_1(self):
        if self.get_user_progress() > 1:
            self.hud('Reverting user progress to Data Selection & Scaling')
        elif self.get_user_progress() < 1:
            self.hud('Setting user progress to Data Selection & Scaling')
        self.set_user_progress(True, False, False, False)
        self.project_progress = 1
    
    def set_progress_stage_2(self):
        if self.get_user_progress() > 2:
            self.hud('Reverting user progress to Alignment')
        elif self.get_user_progress() < 2:
            self.hud('Setting user progress to Alignment')
        self.set_user_progress(True, True, True, False)
        self.project_progress = 2
    
    def set_progress_stage_3(self):
        if self.get_user_progress() < 2: self.hud('Setting user progress to Export & View')
        self.set_user_progress(True, True, True, True)
        self.project_progress = 3
    
    def get_user_progress(self) -> int:
        '''Get user progress (0 to 3)'''
        if is_any_scale_aligned_and_generated(): return int(3)
        elif do_scales_exist(): return int(2)
        elif is_destination_set(): return int(1)
        else: return int(0)
    
    @Slot()
    def read_gui_update_project_data(self) -> None:
        '''Reads MainWindow to Update Project Data.'''
        logger.debug('read_gui_update_project_data:')

        if not do_scales_exist():
            logger.warning('No Scale To Change To. Import Some Images', logging.WARNING)
            return

        try: cfg.data.set_null_cafm(False) if self.get_null_bias_value() == 'None' else cfg.data.set_null_cafm(True)
        except: logger.warning('Unable to Update Project Dictionary with Null Cafm State')

        try: cfg.data.set_poly_order(self.get_null_bias_value())
        except: logger.warning('Unable to Update Project Dictionary with Polynomial Order')

        try: cfg.data.set_bounding_rect(bool(self.get_bounding_state()))
        except: logger.warning('Unable to Update Project Dictionary with Bounding Rect State')

        try: cfg.data.set_whitening(self.get_whitening_input())
        except: logger.warning('Unable to Update Project Dictionary with Whitening Factor')

        try: cfg.data.set_swim_window(self.get_swim_input())
        except: logger.warning('Unable to Update Project Dictionary with SWIM Window')

    
    @Slot()
    def read_project_data_update_gui(self) -> None:
        '''Reads Project Data to Update MainWindow.'''
        logger.debug('read_project_data_update_gui:')
        if not do_scales_exist():
            logger.warning('No Scaled Images. Nothing To Do (Caller: %s)' % inspect.stack()[1].function)
            return

        try: self.toggle_skip.setChecked(not cfg.data.skipped())
        except: logger.warning('Skip Toggle Widget Failed to Update')

        try: self.jump_input.setText(str(cfg.data.layer()))
        except: logger.warning('Current Layer Widget Failed to Update')

        try: self.whitening_input.setText(str(cfg.data.whitening()))
        except: logger.warning('Whitening Input Widget Failed to Update')

        try: self.swim_input.setText(str(cfg.data.swim_window()))
        except: logger.warning('Swim Input Widget Failed to Update')

        try: self.toggle_bounding_rect.setChecked(cfg.data.bounding_rect())
        except: logger.warning('Bounding Rect Widget Failed to Update')

        if cfg.data.null_cafm() == False:
            self.null_bias_combobox.setCurrentText('None')
        else:
            self.null_bias_combobox.setCurrentText(str(cfg.data.poly_order()))

        if cfg.data.layer() == 0:
            self.layer_down_button.setEnabled(False)
        else:
            self.layer_down_button.setEnabled(True)
        if cfg.data.layer() == cfg.data.n_imgs() - 1:
            self.layer_up_button.setEnabled(False)
        else:
            self.layer_up_button.setEnabled(True)

        #0907-
        # alignment_option = cfg.data['data']['scales'][cfg.data.scale()]['method_data']['alignment_option']
        # if alignment_option == 'refine_affine':
        #     self.null_bias_combobox.setEnabled(False)
        #     self.toggle_bounding_rect.setEnabled(False)
        #     self.null_bias_combobox.hide()
        #     self.null_bias_label.hide()
        #     self.toggle_bounding_rect.hide()
        #     self.bounding_label.hide()
        # if alignment_option == 'init_affine':
        #     self.null_bias_combobox.setEnabled(True)
        #     self.toggle_bounding_rect.setEnabled(True)
        #     self.null_bias_combobox.show()
        #     self.null_bias_label.show()
        #     self.toggle_bounding_rect.show()
        #     self.bounding_label.show()

        # if cfg.data.scale() == 'scale_1':
        #     # self.cname_combobox.show()
        #     # self.cname_label.show()
        #     # self.clevel_input.show()
        #     # self.clevel_label.show()
        #     self.export_zarr_button.show()
        # else:
        #     self.cname_combobox.hide()
        #     self.cname_label.hide()
        #     self.clevel_input.hide()
        #     self.clevel_label.hide()
        #     self.export_zarr_button.hide()


        caller = inspect.stack()[1].function
        if caller != 'change_layer': logger.debug('GUI is in Sync with Project Dictionary')

    @Slot()
    def set_idle(self) -> None:
        self.statusBar.showMessage('Idle')

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
    def get_bounding_state(self):
        return self.toggle_bounding_rect.isChecked()
    
    @Slot()
    def get_null_bias_value(self) -> str:
        return str(self.null_bias_combobox.currentText())

    @Slot()
    def jump_to(self, layer) -> None:
        requested_layer = int(layer)
        self.hud('Jumping To Layer # %d' % requested_layer)
        n_layers = cfg.data.n_imgs()
        if requested_layer >= n_layers:
            requested_layer = n_layers - 1
        elif requested_layer < 0:
            requested_layer = 0
        cfg.data['data']['current_layer'] = int(requested_layer)
        self.read_project_data_update_gui()

    
    @Slot()
    def jump_to_layer(self) -> None:
        self.set_status('Busy...')
        # if self.jump_input.text() == '':
        #     return
        # else:
        try:
            self.read_gui_update_project_data()
            requested_layer = int(self.jump_input.text())
            self.hud("Jumping to Layer " + str(requested_layer))
            n_layers = cfg.data.n_imgs()
            if requested_layer >= n_layers:  # Limit to largest
                requested_layer = n_layers - 1
            elif requested_layer < 0:
                requested_layer = 0
            cfg.data.set_layer(requested_layer)
            self.read_project_data_update_gui()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
        except:
            print_exception()
        self.set_idle()
    
    @Slot()
    def jump_to_worst_snr(self) -> None:
        self.set_status('Busy...')
        if not are_images_imported():
            self.hud("Images Must Be Imported First", logging.WARNING)
            self.set_idle()
            return
        if not are_aligned_images_generated():
            self.hud("Current Scale Must Be Aligned First", logging.WARNING)
            self.set_idle()
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
            self.hud("Jumping to Layer %d (Badness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            cfg.data.set_layer(next_layer)
            self.read_project_data_update_gui()
            # self.image_panel.update_multi_self()
            self.jump_to_worst_ticker += 1
        except:
            self.jump_to_worst_ticker = 1
            print_exception()
        self.set_idle()

    @Slot()
    def jump_to_best_snr(self) -> None:
        self.set_status('Busy...')
        if not are_images_imported():
            self.hud("You Must Import Some Images First!")
            self.set_idle()
            return
        if not are_aligned_images_generated():
            self.hud("You Must Align This Scale First!")
            self.set_idle()
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
            self.hud("Jumping to layer %d (Goodness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            cfg.data.set_layer(next_layer)
            self.read_project_data_update_gui()
            # self.image_panel.update_multi_self()
            self.jump_to_best_ticker += 1
        except:
            self.jump_to_best_ticker = 0
            print_exception()
        self.set_idle()

    @Slot()
    def reload_scales_combobox(self) -> None:
        logger.debug('Caller: %s' % inspect.stack()[1].function)
        prev_state = self.scales_combobox_switch
        # self.scales_combobox_switch = 0
        curr_scale = cfg.data.scale()
        image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.data['data']['scales'].keys())]
        self.scales_combobox.clear()
        for scale in sorted(image_scales_to_run):
            self.scales_combobox.addItems(["scale_" + str(scale)])
        index = self.scales_combobox.findText(curr_scale, Qt.MatchFixedString)
        if index >= 0: self.scales_combobox.setCurrentIndex(index)
        self.scales_combobox_switch = prev_state
    
    @Slot()
    def fn_scales_combobox(self) -> None:
        logger.info('fn_scales_combobox')
        logger.info('self.scales_combobox_switch = %s' % self.scales_combobox_switch)
        if self.scales_combobox_switch == 0:
            # logger.warning('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return None
        cfg.data.set_scale(self.scales_combobox.currentText())
        self.read_project_data_update_gui()
        self.update_scale_controls()
        self.update_all_views()

    @Slot()
    def change_scale(self, scale_key: str):
        try:
            cfg.data['data']['current_scale'] = scale_key
            self.read_project_data_update_gui()
            logger.info('Scale changed to %s' % scale_key)
        except:
            print_exception()
            logger.info('Changing Scales Triggered An Exception')


    @Slot()
    def change_layer_up(self):
        self.change_layer(1)

    @Slot()
    def change_layer_down(self):
        self.change_layer(-1)

    def change_layer(self, layer_delta):
        """This function loads the next or previous layer"""
        self.set_status('Loading...')
        # if neuroglancer.server.is_server_running():
        #     logger.warning('Neuroglancer Server Is Running')
        #     return

        self.jump_to_worst_ticker = 1
        self.jump_to_best_ticker = 1
        self.read_gui_update_project_data() #0908+
        n_imgs = cfg.data.n_imgs()
        requested = cfg.data.layer() + layer_delta
        if requested in range(n_imgs):
            pass
        elif requested < 0:
            logger.warning('Cant layer down any further!')
            self.set_idle()
            return
        elif requested > n_imgs - 1:
            logger.warning('Cant layer up any further!')
            self.set_idle()
            return
        logger.info("Changing to layer %s" % requested)
        cfg.data.set_layer(requested)
        self.update_unaligned_view()
        if are_aligned_images_generated():
            self.img_panels['aligned'].setCurrentIndex(requested)
        if self.image_panel_stack_widget.currentIndex() == 0:
            self.read_project_data_update_gui()
        self.set_idle()

    # def load_unaligned_stacks(self):
    #     try:
    #         self.zarr_scales = {}
    #         for s in cfg.data.scales():
    #             name = os.path.join(cfg.data.dest(), s + '.zarr')
    #             dataset_future = get_zarr_tensor(name)
    #             # self.zarr_scales[s] = dataset_future.result()
    #             # dataset = await dataset_future
    #             import asyncio
    #             self.zarr_scales[s] = await dataset_future
    #     except:
    #         logger.info('No Unaligned Zarr Stacks Were Loaded')


    # def run_zarr_benchmark(self):
    #     zarr_scales = {}
    #     dest = cfg.data.dest()
    #     for s in cfg.data.scales():
    #         name = os.path.join(dest, s + '.zarr')
    #         zarr_scales[s] = da.from_zarr(name)

    def load_unaligned_stacks(self):
        logger.critical('Loading Unaligned Images')
        self.zarr_scales = {}
        try:
            for s in cfg.data.scales():
                # name = os.path.join(cfg.data.dest(), s + '.zarr')
                name = os.path.join(cfg.data.dest(), 'scales.zarr', 's' + str(get_scale_val(s)))
                dataset_future = get_zarr_tensor(name)
                self.zarr_scales[s] = dataset_future.result()
        except:
            logger.warning('No Unaligned Zarr Stacks Were Loaded')
            print_exception()


    @Slot()
    def update_unaligned_view(self):
        '''Called by read_project_data_update_gui '''
        logger.info('update_unaligned_view (called by %s):' % inspect.stack()[1].function)
        # cfg.image_library.preload_images(cfg.data.layer())
        s, l, dest = cfg.data.scale(), cfg.data.layer(), cfg.data.dest()
        logger.info('s,l,dest = %s, %s, %s' % (cfg.data.scale(), str(cfg.data.layer()), cfg.data.dest()))
        image_dict = cfg.data['data']['scales'][s]['alignment_stack'][l]['images']
        is_skipped = cfg.data['data']['scales'][s]['alignment_stack'][l]['skipped']
        try:
            if l != 0:
                x_ref, x_base = self.zarr_scales[s][l-1, :, :], self.zarr_scales[s][l, :, :]
                future_ref, future_base = x_ref.read(), x_base.read()
                logger.info('Setting image ref')
                self.img_panels['ref'].setImage(future_ref.result())
                logger.info('Setting image base')
                self.img_panels['base'].setImage(future_base.result())
            elif l == 0:
                self.img_panels['ref'].clearImage()
                x_base = self.zarr_scales[s][l, :, :]
                future_base = x_base.read()
                logger.info('Setting image base')
                self.img_panels['base'].setImage(future_base.result())

        except:
            print_exception()
            logger.warning('Unable To Render Unaligned Stacks')


    def update_aligned_view(self):
        logger.critical('update_aligned_view:')
        if is_cur_scale_aligned():
            logger.critical('Current scale is aligned')
            dest = cfg.data.dest()
            zarr_path = os.path.join(dest, 'alignments.zarr')
            path = os.path.join(zarr_path, 's' + str(cfg.data.scale_val()))
            logger.critical('path is %s' % path)
            # np_data = zarr.load(path)
            # np_data = np.transpose(np_data, axes=[1, 2, 0])

            # zarr_data = da.from_zarr(path, inline_array=True) # <class 'dask.array.core.Array' #orig
            # zarr_data = np.moveaxis(zarr_data,0,2) # Now has shape (512, 512, 1)
            dataset_future = get_zarr_tensor(path)

            logger.critical('Calling dataset_future.result()')
            t0 = time.time()
            dataset = dataset_future.result()
            dt = time.time() - t0
            logger.info('dataset_future.result() Finished In %g Seconds' % dt)
            logger.info('dataset.domain: %s' % dataset.domain)
            # dataset.domain = { [0, 100*), [0, 1354*), [0, 1354*) }

            # zarr_data = np.asarray(tensor_arr.result())
            # zarr_data = np.moveaxis(zarr_data, 0, 2)  # Now has shape (512, 512, 1)
            # self.img_panels['aligned'].setImage(zarr_data)
            self.img_panels['aligned'].setImage(dataset)
            self.img_panels['aligned'].setCurrentIndex(cfg.data.layer())
        else:
            self.img_panels['aligned'].imageViewer.clearImage()
            logger.warning('No Aligned Stack for Current Scale')

        # th_ref = threading.Thread(target=cfg.image_library.get_image_reference, args=("image_dict['ref']['filename']"))
        # th_base = threading.Thread(target=cfg.image_library.get_image_reference, args=("image_dict['base']['filename']"))

    @Slot()
    def update_all_views(self):
        logger.critical('Called By %s' % inspect.stack()[1].function)
        if are_images_imported():
            logger.critical('Images Are Imported')
            try:     self.update_unaligned_view()
            except:  logger.warning('An exception occurred while attempting to update unaligned image panels')
        if cfg.data.scale() in self.aligned_scales:
            logger.critical('Scale Is Aligned')
            try:     self.update_aligned_view()
            except:  logger.warning('An exception occurred while attempting to update aligned image panel')

    @Slot()
    def clear_images(self):
        self.img_panels['ref'].clearImage()
        self.img_panels['base'].clearImage()
        self.img_panels['aligned'].imageViewer.clearImage()

    
    @Slot()
    def print_image_library(self):
        self.hud(str(cfg.image_library))
    
    def new_project(self):
        logger.debug('new_project:')
        self.set_status("New Project...")
        self.set_normal_view()
        if is_destination_set():
            logger.info('Asking user to confirm new data')
            msg = QMessageBox(QMessageBox.Warning,
                              'Confirm New Project',
                              'Please confirm create new data.',
                              buttons=QMessageBox.Cancel | QMessageBox.Ok)
            msg.setIcon(QMessageBox.Question)
            button_cancel = msg.button(QMessageBox.Cancel)
            button_cancel.setText('Cancel')
            button_ok = msg.button(QMessageBox.Ok)
            button_ok.setText('New Project')
            msg.setDefaultButton(QMessageBox.Cancel)
            reply = msg.exec_()
            if reply == QMessageBox.Ok:
                logger.info("Response was 'OK'")
                pass
            else:
                logger.info("Response was not 'OK' - Returning")
                self.hud('New Project Canceled', logging.WARNING)
                self.set_idle()
                return
            if reply == QMessageBox.Cancel:
                logger.info("Response was 'Cancel'")
                self.hud('New Project Canceled', logging.WARNING)
                self.set_idle()
                return
        self.set_progress_stage_0()
        self.hud('Creating New Project...')
        cfg.image_library.remove_all_images()
        self.img_panels['ref'].clearImage()
        self.img_panels['base'].clearImage()
        self.img_panels['aligned'].imageViewer.clearImage()
        self.aligned_scales = []
        filename = self.new_project_save_as_dialog()
        if filename == '':
            self.hud("Must Provide A Name For The Project.")
            self.set_idle()
            return

        self.clear_images()
        logger.info("Overwriting Project Data In Memory With New Template")
        if not filename.endswith('.json'):
            filename += ".json"
        path, extension = os.path.splitext(filename)
        cfg.data = DataModel(name=path)
        makedirs_exist_ok(cfg.data['data']['destination_path'], exist_ok=True)
        self.hud.done()
        self.setWindowTitle("Project: " + os.path.split(cfg.data.dest())[-1])
        self.save_project()
        self.set_progress_stage_1()
        self.scales_combobox.clear()  # why? #0528
        # self.run_after_import()
        cfg.IMAGES_IMPORTED = False
        self.set_idle()
    
    def import_images_dialog(self):
        '''Dialog for importing images. Returns list of filenames.'''
        caption = "Import Images"
        filter = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)"
        if qtpy.QT5:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getOpenFileNames(
            parent=self,
            caption=caption,
            filter=filter,
            # options=options
        )
        return response[0]
    
    def open_project_dialog(self) -> str:
        '''Dialog for opening a data. Returns 'filename'.'''
        caption = "Open Project (.json)"
        filter = "Projects (*.json);;All Files (*)"
        if qtpy.QT5:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getOpenFileName(
            parent=self,
            caption=caption,
            filter=filter,
            # options=options
        )
        return response[0]
    
    def save_project_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        caption = "Save Project"
        filter = "Projects (*.json);;All Files (*)"
        if qtpy.QT5:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getSaveFileName(
            parent=self,
            caption=caption,
            filter=filter,
            # options=options
        )
        return response[0]
    
    def new_project_save_as_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        caption = "New Project Save As..."
        filter = "Projects (*.json);;All Files (*)"
        if qtpy.QT5:
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getSaveFileName(
            parent=self,
            caption=caption,
            filter=filter,
            # options=options
        )
        return response[0]

    def show_warning(self, title, text):
        QMessageBox.warning(None, title, text)

    def request_confirmation(self, title, text):
        button = QMessageBox.question(None, title, text)
        logger.debug("You clicked " + str(button))
        logger.debug("Returning " + str(button == QMessageBox.StandardButton.Yes))
        return (button == QMessageBox.StandardButton.Yes)
    
    def open_project(self):
        self.main_widget.setCurrentIndex(0)
        self.set_status("Open Project...")
        #Todo need something like this here
        # if self._unsaved_changes:
        #     self.hud('Confirm Exit AlignEM-SWiFT')
        #     message = "There are unsaved changes.\n\nSave before exiting?"
        #     msg = QMessageBox(QMessageBox.Warning, "Save Changes", message, parent=self)
        #     msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        #     msg.setDefaultButton(QMessageBox.Save)
        #     msg.setIcon(QMessageBox.Question)
        #     reply = msg.exec_()
        #     if reply == QMessageBox.Cancel:
        #         logger.info('reply=Cancel. Returning control to the app.')
        #         self.hud('Canceling exit application')
        #         self.set_idle()
        #         return
        #     if reply == QMessageBox.Save:
        #         logger.info('reply=Save')
        #         self.save_project()
        #         self.set_status('Wrapping up...')
        #         logger.info('Project saved. Exiting')
        #     if reply == QMessageBox.Discard:
        #         logger.info('reply=Discard Exiting without saving')
        # else:
        #     logger.critical('No Unsaved Changes - Exiting')
        self.main_panel_bottom_widget.setCurrentIndex(0)
        filename = self.open_project_dialog()
        if filename != '':
            with open(filename, 'r') as f:
                project = DataModel(json.load(f))
            if type(project) == type('abc'):
                self.hud('There Was a Problem Loading the Project File', logging.ERROR)
                logger.warning("Project Type is Abstract Base Class - Unable to Load!")
                self.set_idle()
                return
            self.hud("Loading Project '%s'..." % filename)
            project.set_paths_absolute(head=filename)
            cfg.data = copy.deepcopy(project)  # Replace the current version with the copy
            cfg.data.link_all_stacks()


            if are_images_imported():
                self.load_unaligned_stacks()
                self.update_unaligned_view()
                if are_aligned_images_generated():
                    logger.info('Aligned Images Are Generated. Updating aligned view.')
                    self.update_aligned_view()
                else:
                    logger.info('Aligned Images Are Not Generated. Not updating aligned view.')
            if is_any_scale_aligned_and_generated():
                self.aligned_scales.extend(cfg.data.aligned_list())

            self.read_project_data_update_gui()
            self.auto_set_user_progress()
            self.reload_scales_combobox()
            self.update_scale_controls()
            self.multi_img_viewer.setFocus()


            if are_images_imported():
                cfg.IMAGES_IMPORTED = True
                self.generate_scales_button.setEnabled(True)
            else:
                cfg.IMAGES_IMPORTED = False
                self.generate_scales_button.setEnabled(False)

            if are_aligned_images_generated():
                # self.img_panels['aligned'].imageViewer.show_ng_button()
                self.img_panels['aligned'].show_ng_button()
            else:
                # self.img_panels['aligned'].imageViewer.hide_ng_button()
                self.img_panels['aligned'].hide_ng_button()
            self.setWindowTitle("Project: %s" % os.path.basename(cfg.data.dest()))
            # self.hud("Project '%s'" % cfg.data.dest())
            self.hud.done()
        else:
            self.hud("No Project File (.json) Selected", logging.WARNING)
        self.set_idle()

    def save_project(self):
        self.set_status("Saving...")
        self.hud('Saving Project...')
        self.main_panel_bottom_widget.setCurrentIndex(0)
        try:
            self.save_project_to_file()
            self.hud.done()
            self._unsaved_changes = False
            self.hud("Project File Location: %s" % cfg.data.dest() + ".json")
        except:
            self.hud('Nothing To Save', logging.WARNING)
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





    
    # def save_project_as(self):
    #     self.set_status("Saving As...")

    #     if filename != '':
    #         try:
    #             self.save_project_to_file(saveas=filename)
    #             import shutil
    #             dest = shutil.move(dest_orig, dest_new)
    #             self.hud("Project saved as '%s'" % cfg.data.dest())
    #         except:
    #             print_exception()
    #             self.hud('Save Project Failed', logging.ERROR)
    #         finally:
    #             self.set_idle()

    # def move_project(self):
    #     self.set_status("Moving Project")
    #     dir = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
    #     dest_orig = Path(cfg.data.dest())
    #     filename = self.save_project_dialog()
    #     dest_new = Path(filename).parents[0]
    #     import shutil
    #     dest = shutil.move(dest_orig, dest_new)

    def save_project_to_file(self, saveas=None):
        logger.debug('Saving Project To File')
        if saveas is not None:
            cfg.data.set_destination(saveas)
        if self.get_user_progress() > 1: #0801+
            self.read_gui_update_project_data()
        data_cp = copy.deepcopy(cfg.data.to_dict())
        data_cp['data']['destination_path'] = \
            make_relative(data_cp['data']['destination_path'], cfg.data['data']['destination_path'])
        for s in data_cp['data']['scales'].keys():
            scales = data_cp['data']['scales'][s]
            for l in scales['alignment_stack']:
                for role in l['images'].keys():
                    filename = l['images'][role]['filename']
                    if filename != '':
                        l['images'][role]['filename'] = make_relative(filename, cfg.data.dest())
        logger.info('---- WRITING DATA TO PROJECT FILE ----')
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        proj_json = jde.encode(data_cp)
        name = cfg.data.dest()
        if not name.endswith('.json'): #0818-
            name += ".json"
        with open(name, 'w') as f:
            f.write(proj_json)

    @Slot()
    def has_unsaved_changes(self):
        logger.debug("Called by " + inspect.stack()[1].function)
        if inspect.stack()[1].function == 'initUI':
            return
        if inspect.stack()[1].function == 'read_project_data_update_gui':
            return
        self._unsaved_changes = True
    
    @Slot()
    def actual_size(self):
        logger.info("MainWindow.actual_size:")
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update_zpa_self()

    
    def add_image_to_role(self, image_file_name, role_name):
        logger.debug("Adding Image %s to Role '%s'" % (image_file_name, role_name))
        #### prexisting note: This function is now much closer to empty_into_role and should be merged
        scale = cfg.data.scale()
        if image_file_name != None:
            if len(image_file_name) > 0:
                used_for_this_role = [role_name in l['images'].keys() for l in
                                      cfg.data['data']['scales'][scale]['alignment_stack']]
                layer_index = -1
                if False in used_for_this_role:
                    # There is an unused slot for this role. Find the first:
                    layer_index = used_for_this_role.index(False)
                else:
                    # There are no unused slots for this role. Add a new layer:
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
            # There are no unused slots for this role. Add a new layer
            logger.debug("Adding Empty Layer For Role %s at layer %d" % (role_name, layer_index))
            cfg.data.append_layer(scale_key=local_cur_scale)
            layer_index_for_new_role = len(cfg.data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        cfg.data.add_img(
            scale_key=local_cur_scale,
            layer_index=layer_index,
            role=role_name,
            filename=None
        )
    
    def import_images(self, clear_role=False):
        ''' Import images into data '''
        self.set_status('Import Images...')
        role_to_import = 'base'
        need_to_scale = not are_images_imported()
        filenames = sorted(self.import_images_dialog())
        logger.debug('filenames = %s' % str(filenames))
        if clear_role:
            for layer in cfg.data['data']['scales'][cfg.data.scale()]['alignment_stack']:
                if role_to_import in layer['images'].keys():  layer['images'].pop(role_to_import)
        
        if filenames != None:
            if len(filenames) > 0:
                self.hud('Importing Selected Images...')
                logger.debug("Selected Files: " + str(filenames))
                for i, f in enumerate(filenames):
                    # Find next layer with an empty role matching the requested role_to_import
                    logger.debug("Role " + str(role_to_import) + ", Importing file: " + str(f))
                    if f is None:
                        self.add_empty_to_role(role_to_import)
                    else:
                        self.add_image_to_role(f, role_to_import)
                # Draw the panel's ("windows") #0808- #0816+
                for p in self.panel_list:
                    p.force_center = True
                    p.update_zpa_self()

        self.hud.done()
        if are_images_imported():
            cfg.IMAGES_IMPORTED = True
            self.generate_scales_button.setEnabled(True)
            img_size = get_image_size(
                cfg.data['data']['scales']['scale_1']['alignment_stack'][0]['images'][str(role_to_import)]['filename'])
            cfg.data.link_all_stacks()
            if need_to_scale:
                self.run_after_import()
            self.save_project()
            self.hud('%d Images Imported' % cfg.data.n_imgs())
            self.hud('Image Dimensions: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')
        else:
            self.hud('No Images Were Imported', logging.WARNING)
        self.set_idle()

    @Slot()
    def actual_size_callback(self):
        logger.info('MainWindow.actual_size_callback:')
        # self.image_panel.all_images_actual_size()

    @Slot()
    def clear_zoom(self, all_images_in_stack=True):
        '''
        self.image_panel is a MultiImagePanel object'''
        # logger.info('Called By %s' % inspect.stack()[1].function)
        try:
            if are_images_imported():
                self.img_panels['ref'].clearZoom()
                self.img_panels['base'].clearZoom()
                if is_cur_scale_aligned():
                    self.img_panels['aligned'].imageViewer.clearZoom()
        except:
            logger.warning('Centering All Images Raised An Exception')



    @Slot()
    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent:")
        self.app.quit()
        sys.exit()

    @Slot()
    def exit_app(self):
        logger.info("MainWindow.exit_app:")
        # cfg.pr.disable()
        # s = io.StringIO()
        # sortby = SortKey.CUMULATIVE
        # ps = pstats.Stats(cfg.pr, stream=s).sort_stats(sortby)
        # ps.print_stats()
        # print(s.getvalue())

        self.set_status('Exiting...')
        if self._unsaved_changes:
            self.hud('Confirm Exit AlignEM-SWiFT')
            message = "There are unsaved changes.\n\nSave before exiting?"
            msg = QMessageBox(QMessageBox.Warning, "Save Changes", message, parent=self)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Save)
            msg.setIcon(QMessageBox.Question)
            reply = msg.exec_()
            if reply == QMessageBox.Cancel:
                logger.info('reply=Cancel. Returning control to the app.')
                self.hud('Canceling exit application')
                self.set_idle()
                return
            if reply == QMessageBox.Save:
                logger.info('reply=Save')
                self.save_project()
                self.set_status('Wrapping up...')
                logger.info('Project saved. Exiting')
            if reply == QMessageBox.Discard:
                logger.info('reply=Discard Exiting without saving')
        else:
            logger.critical('No Unsaved Changes - Exiting')
        try:
            self.ng_wrkr.http_server.server_close()
            self.ng_wrkr.http_server.shutdown()
        except:
            pass
        try:
            self.ng_wrkr.http_server.server_close()
            self.ng_wrkr.http_server.shutdown()
        except:
            pass

        if neuroglancer.server.is_server_running():
            logger.info('Stopping Neuroglancer Server')
            neuroglancer.server.stop()

        threadpool_result = self.threadpool.waitForDone(msecs=500)
        if threadpool_result: logger.info('All threads were successfully removed from the threadpool')
        else: logger.warning('Failed to remove all threads from the threadpool')
        # QApplication.quit()
        self.app.quit()
        sys.exit()


    def documentation_view(self):  # documentationview
        self.hud("Switching to AlignEM_SWiFT Documentation")
        # don't force the reload, add home button instead
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
        self.main_widget.setCurrentIndex(1)

    def documentation_view_home(self):
        self.hud("Viewing AlignEM-SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README.md'))

    def remote_view(self):
        self.hud("Switching to Remote Neuroglancer Server")
        # self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        # self.disableShortcuts()
        self.main_widget.setCurrentIndex(3)

    def reload_ng(self):
        logger.info("Reloading Neuroglancer Viewer")
        self.view_neuroglancer()

    def reload_remote(self):
        logger.info("Reloading Remote Neuroglancer Server")
        self.remote_view()

    def exit_ng(self):
        self.hud("Exiting Neuroglancer Viewer")
        self.hud('Stopping Neuroglancer Server')
        # neuroglancer.server.stop()
        self.image_panel_stack_widget.setCurrentIndex(0)  #0906
        new_cur_layer = int(cfg.viewer.state.voxel_coordinates[0])
        cfg.data.set_layer(new_cur_layer)
        self.jump_to(new_cur_layer)
        self.read_project_data_update_gui() #0908+
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def exit_docs(self):
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def exit_remote(self):
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def exit_demos(self):
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def webgl2_test(self):
        '''https://www.khronos.org/files/webgl20-reference-guide.pdf'''
        self.browser_docs.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.main_widget.setCurrentIndex(1)

    def google(self):
        self.hud('Googling...')
        self.browser_docs.setUrl(QUrl('https://www.google.com'))
        self.main_widget.setCurrentIndex(1)

    def gpu_config(self):
        self.browser_docs.setUrl(QUrl('chrome://gpu'))
        self.main_widget.setCurrentIndex(1)


    def print_state_ng(self):
        self.ng_wrkr.show_state()
        # logger.info("Viewer.url : ", self.viewer.get_viewer_url)
        # logger.info("Viewer.screenshot : ", self.viewer.screenshot)
        # logger.info("Viewer.txn : ", self.viewer.txn)
        # logger.info("Viewer.actions : ", self.viewer.actions)


    def print_url_ng(self):
        self.ng_wrkr.show_url()


    def blend_ng(self):
        logger.info("blend_ng():")

    def view_neuroglancer(self):  #view_3dem #ngview #neuroglancer
        '''
        https://github.com/google/neuroglancer/blob/566514a11b2c8477f3c49155531a9664e1d1d37a/src/neuroglancer/ui/default_input_event_bindings.ts
        https://github.com/google/neuroglancer/blob/566514a11b2c8477f3c49155531a9664e1d1d37a/src/neuroglancer/util/event_action_map.ts
        '''
        self.set_status('Busy...')
        logger.info("Switching To Neuroglancer Viewer")
        if not are_images_imported():
            self.hud('Nothing To View')

        dest = os.path.abspath(cfg.data['data']['destination_path'])
        s, l = cfg.data.scale(), cfg.data.layer()
        al_path = os.path.join(dest, 'alignments.zarr')
        self.hud("Loading '%s' in Neuroglancer" % al_path)
        self.ng_wrkr = NgViewer(src=dest, scale=s, viewof='aligned', port=9000)
        self.threadpool.start(self.ng_wrkr)
        self.browser_ng.setUrl(QUrl(self.ng_wrkr.url()))
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.hud('Displaying Alignment In Neuroglancer')
        self.set_idle()


    def set_normal_view(self):
        # neuroglancer.server.stop()
        self.image_panel_widget.show()
        self.lower_panel_groups.show()
        self.multi_img_viewer.show()
        self.image_panel_stack_widget.show()
        self.main_widget.setCurrentIndex(0)
        self.image_panel_stack_widget.setCurrentIndex(0)
        self.main_panel_bottom_widget.setCurrentIndex(0)


    def show_splash(self):

        splash = SplashScreen('src/resources/alignem_animation.gif')
        splash.show()

        def showWindow():
            splash.close()
            # form.show()

        QTimer.singleShot(7500, showWindow)
        # form = MainWindow()


    def run_after_import(self):
        result = cfg.defaults_form.exec_() # result = 0 or 1
        if not result: logger.warning('The Result of cfg.defaults_form.exec_() was 0')
        # self.update_unaligned_view() # Can't show image stacks before creating Zarr scales
        if result:  self.run_scaling_auto()
        else:       logger.critical('Dialog Was Not Accepted - Will Not Scale At This Time')


    def view_k_img(self):
        self.w = KImageWindow(parent=self)
        self.w.show()


    def bounding_rect_changed_callback(self, state):
        if inspect.stack()[1].function == 'read_project_data_update_gui': return
        if state:
            self.hud('Bounding Box is ON. Warning: Dimensions may grow larger than the original images.')
            cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            self.hud('Bounding Box is OFF (faster). Dimensions will equal the original images.')
            cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def skip_changed_callback(self, state):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        self.hud("Keep Image Set To: %s" % str(state))
        if are_images_imported():
            s,l = cfg.data.scale(), cfg.data.layer()
            cfg.data['data']['scales'][s]['alignment_stack'][l]['skipped'] = not state
            copy_skips_to_all_scales()
            cfg.data.link_all_stacks()

    def toggle_zarr_controls(self):
        if self.export_and_view_stack.isHidden():
            self.export_and_view_stack.show()
        else:
            self.export_and_view_stack.hide()


    def toggle_match_point_align(self):
        self.main_widget.setCurrentIndex(0)
        self.match_point_mode = not self.match_point_mode
        if self.match_point_mode:
            self.hud('Match Point Mode is now ON (Ctrl+M or ⌘+M to Toggle Match Point Mode)')
        else:
            self.hud('Match Point Mode is now OFF (Ctrl+M or ⌘+M to Toggle Match Point Mode)')


    def clear_match_points(self):
        logger.info('Clearing Match Points...')
        cfg.data.clear_match_points()
        # self.image_panel.update_multi_self()

    def resizeEvent(self, event):
        self.resized.emit()
        return super(MainWindow, self).resizeEvent(event)

    def pbar_max(self, x):
        self.pbar.setMaximum(x)

    def pbar_update(self, x):
        self.pbar.setValue(x)

    def show_run_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.hud('\n\nWorking Directory     : %s\n'
                      'Running In (__file__) : %s' % (os.getcwd(),os.path.dirname(os.path.realpath(__file__))))

    def show_module_search_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.hud('\n\n' + '\n'.join(sys.path))

    def show_snr_list(self) -> None:
        s = cfg.data.scale_val()
        lst = ' | '.join(map(str, cfg.data.snr_list()))
        self.hud('\n\nSNR List for Scale %d:\n%s' % (s, lst))

    def show_zarr_info(self) -> None:
        import zarr
        z = zarr.open(os.path.join(cfg.data.dest(), 'alignments.zarr'))
        self.hud('\n\n' + str(z.tree()) + '\n' + str(z.info))

    def disableShortcuts(self):
        '''Initialize Global Shortcuts'''
        pass
        logger.info('Disabling Global Shortcuts')
        ## self.shortcut_prev_scale.setEnabled(False)
        ## self.shortcut_next_scale.setEnabled(False)
        self.shortcut_layer_up.setEnabled(False)
        self.shortcut_layer_down.setEnabled(False)

    def initShortcuts(self):
        '''Initialize Global Shortcuts'''

        logger.info('Initializing Global Shortcuts')
        events = (
            # (QKeySequence.Save, self.save_project),
            (QKeySequence.Quit, self.exit_app),
            (QKeySequence.MoveToNextChar, self.change_layer_up),
            (QKeySequence.MoveToPreviousChar, self.change_layer_down),
            (QKeySequence.MoveToNextLine, self.scale_down_button_callback),
            (QKeySequence.MoveToPreviousLine, self.scale_up_button_callback)
        )
        for event, action in events:
            QShortcut(event, self, action)

    def expand_bottom_panel_callback(self):
        if not self.image_panel_widget.isHidden():
            self.image_panel_widget.hide()
            self.lower_panel_groups.hide()
            self.multi_img_viewer.hide()
            self.image_panel_stack_widget.hide()
            self.bottom_display_area_widget.adjustSize()
            self.expand_bottom_panel_button.setIcon(qta.icon("fa.caret-down", color=ICON_COLOR))

        elif self.image_panel_widget.isHidden():
            self.image_panel_widget.show()
            self.lower_panel_groups.show()
            self.multi_img_viewer.show()
            self.image_panel_stack_widget.show()
            self.expand_bottom_panel_button.setIcon(qta.icon("fa.caret-up", color=ICON_COLOR))





    def initUI(self):
        '''Initialize Main UI'''

        gb_margin = (8, 15, 8, 5)
        cpanel_height = 115
        cpanel_1_dims = (260, cpanel_height)
        cpanel_2_dims = (260, cpanel_height)
        cpanel_3_dims = (400, cpanel_height)
        cpanel_4_dims = (120, cpanel_height)
        cpanel_5_dims = (120, cpanel_height)

        std_height = int(22)
        std_width = int(96)
        std_button_size = QSize(std_width, std_height)
        square_button_height = int(30)
        square_button_width = int(72)
        square_button_size = QSize(square_button_width, square_button_height)
        std_input_size = int(56)
        small_input_size = int(36)
        small_button_size = QSize(int(46), std_height)

        '''GroupBox 1 Project'''

        self.hud = HeadUpDisplay(self.app)
        self.hud.setObjectName('hud')
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.hud('You are aligning with AlignEM-SWiFT, please report newlybugs to joel@salk.edu', logging.INFO)

        self.new_project_button = QPushButton(" New")
        self.new_project_button.clicked.connect(self.new_project)
        self.new_project_button.setFixedSize(square_button_size)
        self.new_project_button.setIcon(qta.icon("fa.plus", color=ICON_COLOR))

        self.open_project_button = QPushButton(" Open")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_project_button.setFixedSize(square_button_size)
        self.open_project_button.setIcon(qta.icon("fa.folder-open", color=ICON_COLOR))

        self.save_project_button = QPushButton(" Save")
        self.save_project_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setFixedSize(square_button_size)
        self.save_project_button.setIcon(qta.icon("mdi.content-save", color=ICON_COLOR))

        self.exit_app_button = QPushButton(" Exit")
        self.exit_app_button.clicked.connect(self.exit_app)
        self.exit_app_button.setFixedSize(square_button_size)
        self.exit_app_button.setIcon(qta.icon("fa.close", color=ICON_COLOR))

        self.documentation_button = QPushButton(" Help")
        self.documentation_button.clicked.connect(self.documentation_view)
        self.documentation_button.setFixedSize(square_button_size)
        self.documentation_button.setIcon(qta.icon("mdi.help", color=ICON_COLOR))

        self.remote_viewer_button = QPushButton("Neuroglancer\nServer")
        self.remote_viewer_button.clicked.connect(self.remote_view)
        self.remote_viewer_button.setFixedSize(square_button_size)
        self.remote_viewer_button.setStyleSheet("font-size: 9px;")

        self.project_functions_layout = QGridLayout()
        self.project_functions_layout.setContentsMargins(*gb_margin)
        self.project_functions_layout.addWidget(self.new_project_button, 0, 0)
        self.project_functions_layout.addWidget(self.open_project_button, 0, 1)
        self.project_functions_layout.addWidget(self.save_project_button, 0, 2)
        self.project_functions_layout.addWidget(self.exit_app_button, 1, 0)
        self.project_functions_layout.addWidget(self.documentation_button, 1, 1)
        self.project_functions_layout.addWidget(self.remote_viewer_button, 1, 2)

        '''GroupBox 2 Data Selection & Scaling'''

        self.import_images_button = QPushButton(" Import\n Images")
        self.import_images_button.setToolTip('Import Images.')
        self.import_images_button.clicked.connect(self.import_images)
        self.import_images_button.setFixedSize(square_button_size)
        self.import_images_button.setIcon(qta.icon("fa5s.file-import", color=ICON_COLOR))
        self.import_images_button.setStyleSheet("font-size: 10px;")

        tip = 'Zoom to fit'
        self.clear_zoom_button = QPushButton('Fit Screen')
        self.clear_zoom_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_zoom_button.setToolTip('Zoom to fit')
        self.clear_zoom_button.clicked.connect(self.clear_zoom)
        self.clear_zoom_button.setFixedSize(square_button_width, std_height)
        self.clear_zoom_button.setStyleSheet("font-size: 10px;")

        self.plot_snr_button = QPushButton("Plot SNR")
        self.plot_snr_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_snr_button.clicked.connect(self.show_snr_plot)
        self.plot_snr_button.setFixedSize(square_button_size)

        tip = 'Actual-size all images.'
        self.actual_size_button = QPushButton('Actual Size')
        self.actual_size_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.actual_size_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.actual_size_button.clicked.connect(self.actual_size_callback)
        self.actual_size_button.setFixedSize(square_button_width, std_height)
        self.actual_size_button.setStyleSheet("font-size: 10px;")

        self.size_buttons_vlayout = QVBoxLayout()
        self.size_buttons_vlayout.addWidget(self.clear_zoom_button)
        self.size_buttons_vlayout.addWidget(self.actual_size_button)

        tip = 'Generate scale pyramid with chosen # of levels.'
        self.generate_scales_button = QPushButton('Generate\nScales')
        self.generate_scales_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.generate_scales_button.clicked.connect(self.run_scaling)
        self.generate_scales_button.setFixedSize(square_button_size)
        self.generate_scales_button.setStyleSheet("font-size: 10px;")
        self.generate_scales_button.setIcon(qta.icon("mdi.image-size-select-small", color=ICON_COLOR))
        self.generate_scales_button.setEnabled(False)

        tip = 'Reset skips (keep all)'
        self.clear_all_skips_button = QPushButton('Clear')
        self.clear_all_skips_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clear_all_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_all_skips_button.clicked.connect(self.clear_all_skips_callback)
        self.clear_all_skips_button.setFixedSize(small_button_size)
        # self.clear_all_skips_button.setIcon(qta.icon("mdi.undo", color=ICON_COLOR))

        tip = 'Use or skipped current image?'
        self.toggle_skip = ToggleSwitch()
        self.toggle_skip.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_skip.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_skip.setChecked(True)  # 0816 #observed #sus #0907-
        self.toggle_skip.toggled.connect(self.skip_changed_callback)
        self.skip_label = QLabel("Keep?")
        self.skip_label.setToolTip(tip)
        self.skip_layout = QHBoxLayout()
        self.skip_layout.addWidget(self.skip_label)
        self.skip_layout.addWidget(self.toggle_skip)

        tip = 'Jump to image #'
        self.jump_label = QLabel("Image #:")
        self.jump_label.setToolTip(tip)
        self.jump_input = QLineEdit(self)
        self.jump_input.setFocusPolicy(Qt.ClickFocus)
        self.jump_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.jump_input.setFixedSize(std_input_size, std_height)
        self.jump_validator = QIntValidator()
        self.jump_input.setValidator(self.jump_validator)
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer())

        self.toggle_reset_hlayout = QHBoxLayout()
        self.toggle_reset_hlayout.addWidget(self.clear_all_skips_button)
        self.toggle_reset_hlayout.addLayout(self.skip_layout)
        # self.toggle_reset_hlayout.addWidget(self.jump_label, alignment=Qt.AlignmentFlag.AlignRight)
        # self.toggle_reset_hlayout.addWidget(self.jump_input, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.scale_layout = QGridLayout()
        self.scale_layout.setContentsMargins(*gb_margin)  # tag23
        self.scale_layout.addWidget(self.import_images_button, 0, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addLayout(self.size_buttons_vlayout, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addWidget(self.generate_scales_button, 0, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addLayout(self.toggle_reset_hlayout, 1, 0, 1, 3)

        '''GroupBox 3 Alignment'''

        self.scales_combobox = QComboBox(self)
        # self.scales_combobox.hide()
        self.scales_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scales_combobox.setFixedSize(std_button_size)
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        self.whitening_label = QLabel("Whitening:")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.textEdited.connect(self.has_unsaved_changes)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(std_input_size + 20 ) #0829
        self.whitening_input.setFixedHeight(std_height)
        self.whitening_input.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        self.whitening_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.whitening_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.whitening_grid = QGridLayout()
        self.whitening_grid.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.addWidget(self.whitening_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        self.swim_label = QLabel("SWIM Window:")
        self.swim_input = QLineEdit(self)
        self.swim_input.textEdited.connect(self.has_unsaved_changes)
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(std_input_size  + 20 ) #0829
        self.swim_input.setFixedHeight(std_height)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        self.swim_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.swim_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.swim_grid = QGridLayout()
        self.swim_grid.setContentsMargins(0, 0, 0, 0)
        self.swim_grid.addWidget(self.swim_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        tip = 'Apply these settings to the entire data.'
        self.apply_all_label = QLabel("Apply All:")
        self.apply_all_button = QPushButton()
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.apply_all_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.apply_all_button.clicked.connect(self.apply_all_callback)
        self.apply_all_button.setFixedSize(std_height, std_height)
        self.apply_all_button.setIcon(qta.icon("mdi.transfer", color=ICON_COLOR))

        self.apply_all_layout = QGridLayout()
        self.apply_all_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_all_layout.addWidget(self.apply_all_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.apply_all_layout.addWidget(self.apply_all_button, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        tip = 'Go to next scale.'
        self.scale_up_button = QPushButton()
        self.scale_up_button.setStyleSheet("font-size: 10px;")
        self.scale_up_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scale_up_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.scale_up_button.clicked.connect(self.scale_up_button_callback)
        self.scale_up_button.setFixedSize(std_height, std_height)
        self.scale_up_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.scale_up_button.setIcon(qta.icon("fa.arrow-up", color=ICON_COLOR))

        tip = 'Go to previous scale.'
        self.scale_down_button = QPushButton()
        # self.scale_down_button.setShortcut(QKeySequence=)
        self.scale_down_button.setStyleSheet("font-size: 10px;")
        self.scale_down_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scale_down_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.scale_down_button.clicked.connect(self.scale_down_button_callback)
        self.scale_down_button.setFixedSize(std_height, std_height)
        self.scale_down_button.setIcon(qta.icon("fa.arrow-down", color=ICON_COLOR))

        tip = 'Go to next layer.'
        self.layer_up_button = QPushButton()
        self.layer_up_button.setStyleSheet("font-size: 10px;")
        self.layer_up_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layer_up_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.layer_up_button.clicked.connect(self.change_layer_up)
        self.layer_up_button.setFixedSize(std_height, std_height)
        self.layer_up_button.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        tip = 'Go to previous layer.'
        self.layer_down_button = QPushButton()
        self.layer_down_button.setStyleSheet("font-size: 10px;")
        self.layer_down_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layer_down_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.layer_down_button.clicked.connect(self.change_layer_down)
        self.layer_down_button.setFixedSize(std_height, std_height)
        self.layer_down_button.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        self.scale_selection_label = QLabel()
        self.scale_selection_label.setText("Scale ↕ Layer ↔")
        self.scale_layer_ctrls_layout = QGridLayout()
        self.scale_layer_ctrls_layout.addWidget(self.scale_down_button, 1, 1)
        self.scale_layer_ctrls_layout.addWidget(self.scale_up_button, 0, 1)
        self.scale_layer_ctrls_layout.addWidget(self.layer_up_button, 1, 2)
        self.scale_layer_ctrls_layout.addWidget(self.layer_down_button, 1, 0)

        tip = 'Align This Scale'
        self.align_all_button = QPushButton(' Align')
        self.align_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_all_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.align_all_button.clicked.connect(lambda: self.run_alignment(use_scale=cfg.data.scale()))
        self.align_all_button.setFixedSize(square_button_size)
        self.align_all_button.setIcon(qta.icon("fa.play", color=ICON_COLOR))

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

        self.alignment_layout = QGridLayout()
        self.alignment_layout.setSpacing(8)
        self.alignment_layout.setContentsMargins(*gb_margin)  # tag23
        self.alignment_layout.addLayout(self.swim_grid, 0, 0, 1, 2)
        self.alignment_layout.addLayout(self.whitening_grid, 1, 0, 1, 2)
        self.alignment_layout.addWidget(self.scale_selection_label, 0, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        self.alignment_layout.addLayout(self.scale_layer_ctrls_layout, 1, 3, 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.alignment_layout.addLayout(self.apply_all_layout, 2, 0, 1, 2)
        self.alignment_layout.addWidget(self.align_all_button, 0, 2)

        '''GroupBox 3.5 Post-Alignment'''

        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension. This' \
              ' option is set at the coarsest scale, in order to form a contiguous dataset.'
        self.null_bias_label = QLabel("Bias:")
        self.null_bias_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.null_bias_combobox = QComboBox(self)
        self.null_bias_combobox.currentIndexChanged.connect(self.has_unsaved_changes)
        self.null_bias_combobox.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.null_bias_combobox.addItems(['None', '0', '1', '2', '3', '4'])
        self.null_bias_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.null_bias_combobox.setFixedSize(72, std_height)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.poly_order_hlayout.addWidget(self.null_bias_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that ' \
              'are the same size as the source images but may have missing data, while turning this ON will ' \
              'result in no missing data but may significantly increase the size of the generated images.'
        self.bounding_label = QLabel("Bounding Box:")
        self.bounding_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_bounding_rect.toggled.connect(self.bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignRight)

        tip = "Regenerate aligned images using 'Adjust Output' settings."
        self.regenerate_label = QLabel('Re-generate:')
        self.regenerate_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.regenerate_button = QPushButton()
        self.regenerate_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.regenerate_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.regenerate_button.setIcon(qta.icon("fa.recycle", color=ICON_COLOR))
        self.regenerate_button.clicked.connect(lambda: self.run_regenerate_alignment(use_scale=cfg.data.scale()))
        self.regenerate_button.setFixedSize(std_height, std_height)

        self.regenerate_hlayout = QHBoxLayout()
        self.regenerate_hlayout.addWidget(self.regenerate_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.regenerate_hlayout.addWidget(self.regenerate_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.postalignment_note = QLabel()
        self.postalignment_note.setFont(QFont('Arial', 11, QFont.Light))
        self.postalignment_note.setContentsMargins(0, 0, 0, 0)
        self.postalignment_layout = QGridLayout()
        self.postalignment_layout.setContentsMargins(*gb_margin)

        self.postalignment_layout.addLayout(self.poly_order_hlayout, 0, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addLayout(self.toggle_bounding_hlayout, 1, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addLayout(self.regenerate_hlayout, 2, 0, alignment=Qt.AlignmentFlag.AlignVCenter)

        '''GroupBox 4 Export & View'''

        tip = 'Zarr Compression Level\n(default=5)'
        self.clevel_label = QLabel('clevel (1-9):')
        self.clevel_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clevel_input = QLineEdit(self)
        self.clevel_input.textEdited.connect(self.has_unsaved_changes)
        self.clevel_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clevel_input.setText('5')
        self.clevel_input.setFixedWidth(small_input_size)
        self.clevel_input.setFixedHeight(std_height)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)

        tip = 'Zarr Compression Type\n(default=zstd)'
        self.cname_label = QLabel('cname:')
        self.cname_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setFixedSize(72, std_height)
        self.export_and_view_hbox = QHBoxLayout()
        self.export_zarr_button = QPushButton(" Remake\n Zarr")
        tip = "This function creates a scale pyramid from the full scale aligned images and then converts them " \
              "into the chunked and compressed multiscale Zarr format that can be viewed as a contiguous " \
              "volumetric dataset in Neuroglancer."
        wrapped = '\n'.join(textwrap.wrap(tip, width=35))
        self.export_zarr_button.setToolTip(wrapped)
        self.export_zarr_button.clicked.connect(self.run_export)
        self.export_zarr_button.setFixedSize(square_button_size)
        self.export_zarr_button.setStyleSheet("font-size: 10px;")
        # self.export_zarr_button.setIcon(qta.icon("fa5s.file-export", color=ICON_COLOR))
        self.export_zarr_button.setIcon(qta.icon("fa5s.cubes", color=ICON_COLOR))

        tip = 'View Zarr export in Neuroglancer.'
        self.ng_button = QPushButton("View In\nNeuroglancer")
        self.ng_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.ng_button.clicked.connect(self.view_neuroglancer)
        self.ng_button.setFixedSize(square_button_size)
        # self.ng_button.setIcon(qta.icon("mdi.video-3d", color=ICON_COLOR))
        self.ng_button.setStyleSheet("font-size: 9px;")

        self.export_hlayout = QVBoxLayout()
        self.export_hlayout.addWidget(self.export_zarr_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.export_hlayout.addWidget(self.ng_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clevel_layout = QHBoxLayout()
        self.clevel_layout.setContentsMargins(0, 0, 0, 0)
        self.clevel_layout.addWidget(self.clevel_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignmentFlag.AlignRight)

        self.cname_layout = QHBoxLayout()
        self.cname_layout.addWidget(self.cname_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        self.export_settings_layout = QGridLayout()
        self.export_settings_layout.addLayout(self.clevel_layout, 1, 0)
        self.export_settings_layout.addLayout(self.cname_layout, 0, 0)
        self.export_settings_layout.addLayout(self.export_hlayout, 0, 1, 2, 1)
        self.export_settings_layout.setContentsMargins(*gb_margin)  # tag23


        '''Project GroupBox'''
        self.project_functions_groupbox = QGroupBox("Project")
        self.project_functions_groupbox_ = QGroupBox("Project")
        self.project_functions_groupbox.setLayout(self.project_functions_layout)
        self.project_functions_stack = QStackedWidget()
        self.project_functions_stack.setMinimumSize(*cpanel_1_dims)
        self.project_functions_stack.addWidget(self.project_functions_groupbox_)
        self.project_functions_stack.addWidget(self.project_functions_groupbox)
        self.project_functions_stack.setCurrentIndex(1)

        '''Data Selection & Scaling GroupBox'''
        self.images_and_scaling_groupbox = QGroupBox("Data Selection && Scaling")
        self.images_and_scaling_groupbox_ = QGroupBox("Data Selection && Scaling")
        self.images_and_scaling_groupbox.setLayout(self.scale_layout)
        self.images_and_scaling_stack = QStackedWidget()
        self.images_and_scaling_stack.setMinimumSize(*cpanel_2_dims)
        self.images_and_scaling_stack.addWidget(self.images_and_scaling_groupbox_)
        self.images_and_scaling_stack.addWidget(self.images_and_scaling_groupbox)
        self.images_and_scaling_stack.setCurrentIndex(0)

        '''Alignment GroupBox'''
        self.alignment_groupbox = QGroupBox("Alignment")
        self.alignment_groupbox_ = QGroupBox("Alignment")
        self.alignment_groupbox.setTitle('Alignment')
        self.alignment_groupbox_.setTitle('Alignment')
        self.alignment_groupbox.setLayout(self.alignment_layout)
        self.alignment_stack = QStackedWidget()
        self.alignment_stack.setMinimumSize(*cpanel_3_dims)
        self.alignment_stack.addWidget(self.alignment_groupbox_)
        self.alignment_stack.addWidget(self.alignment_groupbox)
        self.alignment_stack.setCurrentIndex(0)

        '''Post-Alignment GroupBox'''
        self.postalignment_groupbox = QGroupBox("Adjust Output")
        self.postalignment_groupbox_ = QGroupBox("Adjust Output")
        self.postalignment_groupbox.setLayout(self.postalignment_layout)
        self.postalignment_stack = QStackedWidget()
        self.postalignment_stack.setMinimumSize(*cpanel_4_dims)
        self.postalignment_stack.addWidget(self.postalignment_groupbox_)
        self.postalignment_stack.addWidget(self.postalignment_groupbox)
        self.postalignment_stack.setCurrentIndex(0)

        '''Export & View GroupBox'''
        self.export_and_view_groupbox = QGroupBox("Neuroglancer")
        self.export_and_view_groupbox_ = QGroupBox("Neuroglancer")
        self.export_and_view_groupbox.setLayout(self.export_settings_layout)
        self.export_and_view_stack = QStackedWidget()
        self.export_and_view_stack.setMinimumSize(*cpanel_5_dims)
        self.export_and_view_stack.addWidget(self.export_and_view_groupbox_)
        self.export_and_view_stack.addWidget(self.export_and_view_groupbox)
        self.export_and_view_stack.setCurrentIndex(0)

        self.images_and_scaling_stack.setStyleSheet("""QGroupBox {border: 1px dotted #171d22;}""")
        self.alignment_stack.setStyleSheet("""QGroupBox {border: 1px dotted #171d22;}""")
        self.postalignment_stack.setStyleSheet("""QGroupBox {border: 1px dotted #171d22;}""")
        self.export_and_view_stack.setStyleSheet("""QGroupBox {border: 1px dotted #171d22;}""")

        '''Top Details/Labels Banner'''
        self.align_label_resolution = QLabel()
        self.align_label_resolution.setText('Dimensions: n/a')
        self.align_label_affine = QLabel()
        self.align_label_affine.setText('Initialize Affine')
        self.align_label_scales_remaining = QLabel()
        self.align_label_scales_remaining.setText('# Scales Unaligned: n/a')
        self.alignment_status_label = QLabel()
        self.alignment_status_label.setText("Is Scale Aligned: ")
        self.align_label_cur_scale = QLabel()
        self.align_label_cur_scale.setText('')
        # self.al_status_checkbox = QRadioButton()
        # self.al_status_checkbox = QCheckBox()
        # self.al_status_checkbox.setStyleSheet("QCheckBox::indicator {border: 1px solid; border-color: #ffe135;}"
        #                                       "QCheckBox::indicator:checked {background-color: #ffe135;}")
        # self.al_status_checkbox.setEnabled(False)
        # self.al_status_checkbox.setToolTip('Alignment statusBar')
        self.alignment_status_layout = QHBoxLayout()
        self.alignment_status_layout.addWidget(self.alignment_status_label)
        # self.alignment_status_layout.addWidget(self.al_status_checkbox)
        self.details_banner = QWidget()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(6)
        shadow.setOffset(2)
        self.details_banner.setGraphicsEffect(shadow)
        self.details_banner.setContentsMargins(0, 0, 0, 0)
        self.details_banner.setFixedHeight(30)
        # banner_stylesheet = """color: #ffe135; background-color: #000000; font-size: 14px;"""
        banner_stylesheet = """color: #F3F6FB; font-size: 14px;"""
        self.details_banner.setStyleSheet(banner_stylesheet)
        self.details_banner_layout = QHBoxLayout()
        self.details_banner.setLayout(self.details_banner_layout)
        self.details_banner_layout.addWidget(self.align_label_resolution)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.align_label_affine)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addLayout(self.alignment_status_layout)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.align_label_scales_remaining)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.align_label_cur_scale)
        self.details_banner_layout.addStretch(6)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(QLabel('Image #: '))
        self.details_banner_layout.addWidget(self.jump_input)
        self.details_banner_layout.addWidget(QLabel('Scale: '))
        self.details_banner_layout.addWidget(self.scales_combobox)

        self.lwr_groups_layout = QGridLayout()
        self.lwr_groups_layout.setContentsMargins(6,3,6,3) # This is the margin around the group boxes
        self.lwr_groups_layout.addWidget(self.project_functions_stack, 1, 0)
        self.lwr_groups_layout.addWidget(self.images_and_scaling_stack, 1, 1)
        self.lwr_groups_layout.addWidget(self.alignment_stack, 1, 2)
        self.lwr_groups_layout.addWidget(self.postalignment_stack, 1, 3)
        self.lwr_groups_layout.addWidget(self.export_and_view_stack, 1, 4)
        self.export_and_view_stack.hide()
        self.lwr_groups_layout.setHorizontalSpacing(16)
        self.lower_panel_groups = QWidget()
        self.lower_panel_groups.setFixedHeight(cpanel_height + 10)
        self.lower_panel_groups.setLayout(self.lwr_groups_layout)

        # '''Multi Image Panel'''
        # self.image_panel = MultiImagePanel()
        # self.image_panel.setFocusPolicy(Qt.StrongFocus)
        # self.image_panel.setFocus()
        # self.image_panel.draw_annotations = True
        # self.image_panel.setMinimumHeight(image_panel_min_height)
        # self.image_panel_vlayout = QVBoxLayout()
        # self.image_panel_vlayout.setSpacing(0)
        # self.image_panel_vlayout.addWidget(self.details_banner)
        # self.image_panel_vlayout.addWidget(self.image_panel)
        # self.image_panel_widget = QWidget()
        # self.image_panel_widget.setLayout(self.image_panel_vlayout)

        '''Neuroglancer Controls'''
        self.exit_ng_button = QPushButton("Back")
        self.exit_ng_button.setFixedSize(std_button_size)
        self.exit_ng_button.clicked.connect(self.exit_ng)
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(std_button_size)
        self.reload_ng_button.clicked.connect(self.reload_ng)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(std_button_size)
        self.print_state_ng_button.clicked.connect(self.print_state_ng)
        self.print_url_ng_button = QPushButton("Print URL")
        self.print_url_ng_button.setFixedSize(std_button_size)
        self.print_url_ng_button.clicked.connect(self.print_url_ng)
        self.ng_panel = QWidget()

        self.ng_panel_layout = QVBoxLayout()

        self.browser = QWebEngineView()
        # self.browser_al = QWebEngineView()
        # self.browser_unal = QWebEngineView()
        self.browser_ng = QWebEngineView()
        self.ng_multipanel_layout = QHBoxLayout()
        self.ng_multipanel_layout.addWidget(self.browser_ng)

        self.ng_panel_layout.addLayout(self.ng_multipanel_layout)
        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)
        self.ng_panel.setLayout(self.ng_panel_layout)

        '''SNR Plot & Controls'''
        self.snr_plot = SnrPlot()
        self.plot_widget_clear_button = QPushButton('Clear Plot')
        self.plot_widget_clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_widget_clear_button.clicked.connect(self.clear_snr_plot)
        self.plot_widget_clear_button.setFixedSize(square_button_size)
        self.plot_widget_back_button = QPushButton('Back')
        self.plot_widget_back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_widget_back_button.clicked.connect(self.back_callback)
        self.plot_widget_back_button.setFixedSize(square_button_size)
        self.plot_widget_back_button.setAutoDefault(True)
        self.plot_controls_layout = QVBoxLayout()
        self.plot_controls_layout.addWidget(self.plot_widget_clear_button)
        self.plot_controls_layout.addWidget(self.plot_widget_back_button)
        # self.plot_controls_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.plot_widget_layout = QHBoxLayout()
        self.plot_widget_layout.addWidget(self.snr_plot)
        self.plot_widget_layout.addLayout(self.plot_controls_layout)
        self.plot_widget_container = QWidget()
        # self.plot_widget_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) #0917
        self.plot_widget_container.setLayout(self.plot_widget_layout)

        '''Python Console & Controls'''
        self.python_console_back_button = QPushButton('Back')
        self.python_console_back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.python_console_back_button.clicked.connect(self.back_callback)
        self.python_console_back_button.setFixedSize(square_button_size)
        self.python_console_back_button.setAutoDefault(True)
        self.python_console_layout = QHBoxLayout()
        self.python_console_layout.addWidget(self.python_console)
        self.python_console_widget_container = QWidget()
        # self.python_console_widget_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) #0917
        self.python_console_widget_container.setLayout(self.python_console_layout)

        self.main_panel_bottom_widget = QStackedWidget()
        # self.main_panel_bottom_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) #0917
        self.main_panel_bottom_widget.setContentsMargins(0, 0, 0, 0)
        self.main_panel_bottom_widget.addWidget(self.hud)
        self.main_panel_bottom_widget.addWidget(self.plot_widget_container)
        self.main_panel_bottom_widget.addWidget(self.python_console_widget_container)
        self.hud.setContentsMargins(0, 0, 0, 0) #0823
        self.plot_widget_container.setContentsMargins(0, 0, 0, 0) #0823
        self.python_console_widget_container.setContentsMargins(0, 0, 0, 0) #0823
        self.main_panel_bottom_widget.setCurrentIndex(0)

        '''Lower Right Tool Selection Buttons'''
        tip = 'Expand Bottom Panel'
        self.expand_bottom_panel_button = QPushButton()
        self.expand_bottom_panel_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.expand_bottom_panel_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.expand_bottom_panel_button.clicked.connect(self.expand_bottom_panel_callback)
        self.expand_bottom_panel_button.setFixedSize(30,15)
        self.expand_bottom_panel_button.setIcon(qta.icon("fa.caret-up", color=ICON_COLOR))

        self.show_hud_button = QPushButton("Head-up\nDisplay")
        self.show_hud_button.setStyleSheet("font-size: 10px;")
        self.show_hud_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hud_button.clicked.connect(self.show_hud)
        self.show_hud_button.setFixedSize(square_button_size)
        self.show_hud_button.setIcon(qta.icon("mdi.monitor", color=ICON_COLOR))

        self.show_jupyter_console_button = QPushButton("Python\nConsole")
        self.show_jupyter_console_button.setStyleSheet("font-size: 10px;")
        self.show_jupyter_console_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_jupyter_console_button.clicked.connect(self.show_python_console)
        self.show_jupyter_console_button.setFixedSize(square_button_size)
        self.show_jupyter_console_button.setIcon(qta.icon("fa.terminal", color=ICON_COLOR))

        self.show_snr_plot_button = QPushButton(" SNR\n Plot")
        self.show_snr_plot_button.setStyleSheet("font-size: 10px;")
        self.show_snr_plot_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_snr_plot_button.clicked.connect(self.show_snr_plot)
        self.show_snr_plot_button.setFixedSize(square_button_size)
        self.show_snr_plot_button.setIcon(qta.icon("mdi.scatter-plot", color=ICON_COLOR))

        self.project_view_button = QPushButton('View\nJSON')
        self.project_view_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.project_view_button.setToolTip('Inspect the data dictionary in memory.')
        self.project_view_button.clicked.connect(self.project_view_callback)
        self.project_view_button.setFixedSize(square_button_size)
        self.project_view_button.setStyleSheet("font-size: 10px;")
        self.project_view_button.setIcon(qta.icon("mdi.json", color=ICON_COLOR))

        self.main_lwr_vlayout = QVBoxLayout()
        self.main_lwr_vlayout.setContentsMargins(0, 10, 8, 0)
        self.main_lwr_vlayout.addWidget(self.expand_bottom_panel_button)
        self.main_lwr_vlayout.addWidget(self.show_hud_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_lwr_vlayout.addWidget(self.show_jupyter_console_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_lwr_vlayout.addWidget(self.show_snr_plot_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_lwr_vlayout.addWidget(self.project_view_button, alignment=Qt.AlignmentFlag.AlignTop)
        # self.main_lwr_vlayout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.main_lwr_vlayout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.bottom_display_area_hlayout = QHBoxLayout()
        self.bottom_display_area_hlayout.setContentsMargins(0, 0, 0, 0)
        self.bottom_display_area_hlayout.setSpacing(2)
        self.bottom_display_area_hlayout.addWidget(self.main_panel_bottom_widget)
        self.bottom_display_area_hlayout.addLayout(self.main_lwr_vlayout)
        self.bottom_display_area_widget = QWidget()
        self.bottom_display_area_widget.setLayout(self.bottom_display_area_hlayout)
        # self.bottom_display_area_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        '''Image Panels'''
        self.img_panels = {}
        # self.img_panels['ref'] = QtImageStackViewer(role='ref')
        # self.img_panels['base'] = QtImageStackViewer(role='base')
        self.img_panels['aligned'] = QtImageStackViewer(role='aligned', parent=self)
        self.img_panels['ref'] = QtImageViewer(role='ref', parent=self)
        self.img_panels['base'] = QtImageViewer(role='base', parent=self)
        # self.img_panels['aligned'] = QtImageViewer(role='aligned')
        self.image_view_hlayout = QHBoxLayout()
        self.image_view_hlayout.addWidget(self.img_panels['ref'])
        self.image_view_hlayout.addWidget(self.img_panels['base'])
        self.image_view_hlayout.addWidget(self.img_panels['aligned'])
        self.image_view_hlayout.setSpacing(0)
        self.multi_img_viewer = QWidget()
        self.multi_img_viewer.setContentsMargins(0,0,0,0)
        self.multi_img_viewer.setLayout(self.image_view_hlayout)
        # self.splitter.addWidget(self.multi_img_viewer)

        '''Multi-image Panel & Banner Widget'''
        # self.image_panel = MultiImagePanel()
        # self.image_panel.setFocusPolicy(Qt.StrongFocus)
        # self.image_panel.setFocus()
        # self.image_panel.setMinimumHeight(image_panel_min_height)
        self.image_panel_vlayout = QVBoxLayout()
        self.image_panel_vlayout.setSpacing(0)
        self.image_panel_vlayout.addWidget(self.details_banner)
        self.image_panel_vlayout.addWidget(self.multi_img_viewer)
        self.image_panel_widget = QWidget()
        self.image_panel_widget.setLayout(self.image_panel_vlayout)
        self.image_panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        '''Image Panel Stack Widget'''
        self.image_panel_stack_widget = QStackedWidget()
        self.image_panel_stack_widget.addWidget(self.image_panel_widget)
        # self.image_panel_stack_widget.addWidget(self.multi_img_viewer)
        self.image_panel_stack_widget.addWidget(self.ng_panel)

        '''Main Splitter'''
        # main_window.splitter.sizes() # Out[20]: [400, 216, 160]
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.splitterMoved.connect(self.clear_zoom)
        self.splitter.setHandleWidth(4)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        # self.splitter.addWidget(self.image_panel_widget)
        self.splitter.addWidget(self.image_panel_stack_widget)
        self.splitter.addWidget(self.lower_panel_groups)
        self.splitter.addWidget(self.bottom_display_area_widget)
        # self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 2)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.splitter.setCollapsible(2, True)

        '''JSON Project View'''
        self.project_view = QTreeView()
        self.project_model = JsonModel()
        self.project_view.setModel(self.project_model)
        self.project_view.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.project_view.setAlternatingRowColors(True)
        self.exit_project_view_button = QPushButton("Back")
        self.exit_project_view_button.setFixedSize(std_button_size)
        self.exit_project_view_button.clicked.connect(self.back_callback)
        self.refresh_project_view_button = QPushButton("Refresh")
        self.refresh_project_view_button.setFixedSize(std_button_size)
        self.refresh_project_view_button.clicked.connect(self.project_view_callback)
        self.save_project_project_view_button = QPushButton("Save")
        self.save_project_project_view_button.setFixedSize(std_button_size)
        self.save_project_project_view_button.clicked.connect(self.save_project)
        self.project_view_panel = QWidget()
        self.project_view_panel_layout = QVBoxLayout()
        self.project_view_panel_layout.addWidget(self.project_view)
        self.project_view_panel_controls_layout = QHBoxLayout()
        self.project_view_panel_controls_layout.addWidget(self.exit_project_view_button,
                                                          alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_view_panel_controls_layout.addWidget(self.refresh_project_view_button,
                                                          alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_view_panel_controls_layout.addWidget(self.save_project_project_view_button,
                                                          alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_view_panel_controls_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.project_view_panel_layout.addLayout(self.project_view_panel_controls_layout)
        self.project_view_panel.setLayout(self.project_view_panel_layout)

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

        self.exit_remote_button = QPushButton("Back")
        self.exit_remote_button.setFixedSize(std_button_size)
        self.exit_remote_button.clicked.connect(self.exit_remote)
        self.reload_remote_button = QPushButton("Reload")
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
        self.exit_demos_button = QPushButton("Back")
        self.exit_demos_button.setFixedSize(std_button_size)
        self.exit_demos_button.clicked.connect(self.exit_demos)
        self.demos_panel = QWidget()
        self.demos_panel_layout = QVBoxLayout()
        self.demos_panel_controls_layout = QHBoxLayout()
        self.demos_panel_controls_layout.addWidget(self.exit_demos_button)
        self.demos_panel_layout.addLayout(self.demos_panel_controls_layout)
        self.demos_panel.setLayout(self.demos_panel_layout)

        # self.splash() #0816 refactor

        '''Main Window Stacked Widget & Combobox'''
        self.main_panel = QWidget()
        self.main_panel_layout = QGridLayout()
        self.main_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.main_panel_layout.addWidget(self.splitter, 1, 0)

        self.main_widget = QStackedWidget(self)
        self.main_widget.addWidget(self.main_panel)                 # (0) main_panel
        # self.main_widget.addWidget(self.ng_panel)                 # (x) ng_panel
        self.main_widget.addWidget(self.docs_panel)                 # (1) docs_panel
        self.main_widget.addWidget(self.demos_panel)                # (2) demos_panel
        self.main_widget.addWidget(self.remote_viewer_panel)        # (3) remote_viewer_panel
        self.main_widget.addWidget(self.project_view_panel)         # (4) self.project_view
        self.main_widget.setCurrentIndex(0)
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.main_widget)

        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem("Main")
        self.pageComboBox.addItem("Neuroglancer Local")
        self.pageComboBox.addItem("Documentation")
        self.pageComboBox.addItem("Demos")
        self.pageComboBox.addItem("Remote Viewer")
        self.pageComboBox.addItem("Project View")
        self.pageComboBox.addItem("Funky")
        self.pageComboBox.activated[int].connect(self.main_widget.setCurrentIndex)

        self.main_panel.setLayout(self.main_panel_layout)
        self.setCentralWidget(self.main_widget)
        self.set_idle()


        # hbar1 = self.img_panels['ref'].horizontalScrollBar()
        # hbar2 = self.img_panels['base'].horizontalScrollBar()
        #
        # hbar1.valueChanged.connect(lambda _: QTimer.singleShot(0, lambda: hbar2.setValue(hbar1.value())))
        # hbar2.valueChanged.connect(lambda _: QTimer.singleShot(0, lambda: hbar1.setValue(hbar2.value())))
        #
        # vbar1 = self.img_panels['ref'].verticalScrollBar()
        # vbar2 = self.img_panels['base'].verticalScrollBar()
        #
        # vbar1.valueChanged.connect(lambda _: QTimer.singleShot(0, lambda: vbar2.setValue(vbar1.value())))
        # vbar2.valueChanged.connect(lambda _: QTimer.singleShot(0, lambda: vbar1.setValue(vbar2.value())))



def bindScrollBars(scrollBar1, scrollBar2):

    # syncronizing scrollbars syncrnonously somehow breaks zooming and doesn't work
    # scrollBar1.valueChanged.connect(lambda value: scrollBar2.setValue(value))
    # scrollBar2.valueChanged.connect(lambda value: scrollBar1.setValue(value))

    # syncronizing scrollbars asyncronously works ok
    scrollBar1.valueChanged.connect(
        lambda _: QTimer.singleShot(0, lambda: scrollBar2.setValue(scrollBar1.value())))
    scrollBar2.valueChanged.connect(
        lambda _: QTimer.singleShot(0, lambda: scrollBar1.setValue(scrollBar2.value())))

