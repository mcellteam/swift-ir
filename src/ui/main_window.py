#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os, sys, copy, json, inspect, logging, textwrap, operator, signal, platform
from pathlib import Path
import qtpy
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QSpacerItem, QMessageBox, \
    QComboBox, QGroupBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QScrollBar, QDialog, QStyle
# from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication, QKeySequence, QCursor, QImageReader
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, QTimer, Slot, Signal, QEvent, QSortFilterProxyModel, \
    QModelIndex, QPoint, QDir
from qtpy.QtWebEngineWidgets import *
import qtawesome as qta
import pyqtgraph as pg
import time
import neuroglancer.server

import src.config as cfg
from src.config import ICON_COLOR
from src.helpers import *
from src.helpers import natural_sort
from src.data_model import DataModel
from src.image_funcs import ImageSize
from src.compute_affines import compute_affines
from src.generate_aligned import generate_aligned
from src.generate_scales import generate_scales
from src.generate_zarr import generate_zarr
from src.ng_host import NgHost
from src.background_worker import BackgroundWorker
# from src.napari_test import napari_test
from src.ui.headup_display import HeadupDisplay
from src.ui.toggle_switch import ToggleSwitch
from src.ui.json_treeview import JsonModel
from src.ui.kimage_window import KImageWindow
from src.ui.snr_plot import SnrPlot
from src.ui.python_console import PythonConsole
# from src.utils.PyQtImageStackViewer import QtImageStackViewer
# from src.utils.PyQtImageViewer import QtImageViewer
from src.ui.splash import SplashScreen
from src.ui.dialogs import RecipeMaker
from src.zarr_funcs import tiffs2MultiTiff, get_zarr_tensor, generate_zarr_scales

__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    resized = Signal()
    def __init__(self, title="AlignEM-SWiFT"):

        # app = QApplication.instance()
        self.app = QApplication.instance()
        # if app is None:
        #     logger.warning("Creating new QApplication instance.")
        #     self.app = QApplication([])

        check_for_binaries()

        logger.info('Initializing Main Window')
        QMainWindow.__init__(self)


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

        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(QPixmap('sims.png')))
        self.init_dir = os.getcwd()

        fg = self.frameGeometry()
        fg.moveCenter(QGuiApplication.primaryScreen().availableGeometry().center())
        self.move(fg.topLeft())
        logger.info("Initializing Thread Pool")
        self.threadpool = QThreadPool(self)  # important consideration is this 'self' reference
        self.threadpool.setExpiryTimeout(3000) # ms
        self.ng_worker = None

        self._splash = True

        logger.info("Initializing Image Library")
        # cfg.image_library = ImageLibrary() # SmartImageLibrary()
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

        if qtpy.PYSIDE6:
            QImageReader.setAllocationLimit(0) #PySide6
        elif qtpy.PYQT6:
            os.environ['QT_IMAGEIO_MAXALLOC'] = "1000000000000000" #PyQt6

        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())

        # self.project_progress = 0
        self.project_progress = None
        self.project_aligned_scales = []
        # self.scales_combobox_switch = 0
        self.scales_combobox_switch = 1
        self.jump_to_worst_ticker = 1  # begin iter at 1 b/c first image has no ref
        self.jump_to_best_ticker = 0
        
        # PySide6 Only
        logger.info("Initializing Qt WebEngine")
        self.view = QWebEngineView()
        # PySide6-Only Options:
        if qtpy.PYSIDE6:
            logger.info('Setting Qt6-specific browser settings')
            self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
            self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        # self.browser.setPage(CustomWebEnginePage(self)) # Open clicked links in new window

        self.match_point_mode = False

        '''Initialize Status Bar'''
        logger.info('Initializing Status Bar')

        self.statusBar = self.statusBar()
        self.statusBar.setMaximumHeight(24)
        self.pbar = QProgressBar(self)
        # self.pbar.setGeometry(30, 40, 200, 25)
        # self.pbar.setStyleSheet("QLineEdit { background-color: yellow }")
        self.statusBar.addPermanentWidget(self.pbar)
        self.pbar.setMaximumWidth(120)
        self.pbar.setMaximumHeight(22)
        self.pbar.hide()

        '''Initialize Jupyter Console'''
        self.initJupyter()

        logger.info("Initializing Data Model")
        cfg.data = DataModel()

        # self.resized.connect(self.clear_zoom)

        self._unsaved_changes = False
        # self._up = 0
        self._working = False

        self.initMenu()

        '''Initialize UI'''
        logger.info('Initializing UI')
        self.initUI()
        self.initShortcuts()


        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        self.apply_default_style()

        # self.set_idle()

        # self.set_normal_view() #0925
        self.image_panel_stack_widget.setCurrentIndex(2)

        timer = QTimer()
        timer.timeout.connect(self.set_idle)  # execute `display_time`
        timer.setInterval(1000)  # 1000ms = 1s
        timer.start()

        self.set_splash_controls()
        # self.set_project_controls()

    if qtpy.QT5:
        def mousePressEvent(self, event):
            self.oldPos = event.globalPos()

        def mouseMoveEvent(self, event):
            delta = QPoint (event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()
    
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


    @Slot()
    def show_all_controls(self):
        self.control_panel.show()
        self.alignment_widget.show()
        # self.post_alignment_widget.show()
        self.align_all_button.show()

    @Slot()
    def project_view_callback(self):
        logger.critical("project_view_callback called by " + inspect.stack()[1].function + "...")
        self.project_model.load(cfg.data.to_dict())
        self.project_view.show()
        self.main_widget.setCurrentIndex(4)

    @Slot()
    def scale(self) -> None:
        logger.info("scale:")
        # self.scales_combobox_switch = 0
        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            self.set_idle()
            return
        else:
            pass

        self.set_status("Busy...")
        # self.main_panel_bottom_widget.setCurrentIndex(0) #og
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
                # self.clear_images()
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
                # zarr_path = os.path.join(proj_path, 'img_aligned.zarr')
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
            logger.info('<<<< scale')
            return
        cfg.data.set_scales_from_string(input_val)

        ########
        self.hud('Generating Scale Image Hierarchy For Levels %s...' % input_val)
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

        self.load_unaligned_stacks()
        # self.update_unaligned_2D_viewer()
        self.read_project_data_update_gui()
        # self.set_progress_stage_2()
        self.reload_scales_combobox()  # 0529 #0713+
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        self.update_scale_controls()
        self.save_project_to_file()
        self.hud.done()
        # self.set_idle()
        self.pbar.hide()


    def autoscale(self):
        logger.critical('>>>>>>>> Autoscaling Start <<<<<<<<')
        self.set_status("Scaling...")
        # self.scales_combobox_switch = 0
        try:
            self.worker = BackgroundWorker(fn=generate_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            logger.warning('Autoscaling Triggered An Exception')
        self.hud('Generating Zarr Scales...')
        logger.info('linking stacks...')
        cfg.data.link_all_stacks()
        cfg.data.set_defaults()
        logger.info('Determining the coarsest scale...')
        cfg.data['data']['current_scale'] = cfg.data.scales()[-1]
        try:
            logger.info('generating scales...')
            generate_zarr_scales()
            logger.info('exiting _zarr gracefully...')
            # cfg.image_library.set_zarr_refs()
        except:
            logger.warning('An Exception Was Raised While Creating Scaled Zarr Arrays')
            print_exception()
        logger.info('Loading unaligned stacks...')
        self.load_unaligned_stacks()
        # logger.info('Updating unaligned view...')
        # self.update_unaligned_2D_viewer()
        logger.info('Reading project data...')
        self.read_project_data_update_gui()
        # logger.info('Setting user progress...')
        # self.set_progress_stage_2()
        logger.info('Reloading scales combobox...')
        self.reload_scales_combobox()  # 0529 #0713+
        logger.info('Settings combobox index...')
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        logger.info('Updating scale controls...')
        self.update_scale_controls()
        # logger.info('Saving project to file...')
        # self.save_project_to_file() #1002
        # self.hud.done()
        self.set_idle()
        logger.info('Exiting main_window.autoscale')

    
    @Slot()
    def align(self, use_scale=None) -> None:
        logger.critical('>>>>>>>> Align Start <<<<<<<<')

        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            return
        else:
            pass

        if use_scale == None: use_scale = cfg.data.scale()
        # self.main_panel_bottom_widget.setCurrentIndex(0) #og
        self.read_gui_update_project_data()
        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud(warning_msg, logging.WARNING)
            return
        # self.img_panels['aligned'].imageViewer.clearImage()
        img_dims = ImageSize(cfg.data.path_base())
        self.set_status('Aligning Scale %d (%d x %d pixels)...' % (get_scale_val(use_scale), img_dims[0], img_dims[1]))
        alignment_option = cfg.data['data']['scales'][use_scale]['method_data']['alignment_option']
        if alignment_option == 'init_affine':
            self.hud.post("Initializing Affine Transforms For Scale Factor %d..." % (get_scale_val(use_scale)))
        else:
            self.hud.post("Refining Affine Transform For Scale Factor %d..." % (get_scale_val(use_scale)))
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
            # self.set_idle()
            return
        self.hud.done()
        # if are_aligned_images_generated():
        self.update_snr_plot()

        self.save_project_to_file() #0908+
        # self.set_progress_stage_3()

        # if self.is_neuroglancer_viewer():
        self.reload_ng()
        # elif self.is_classic_viewer():
        #     self.update_aligned_2D_viewer()
        self.pbar.hide()



    @Slot()
    def align_forward(self, use_scale=None, num_layers=1) -> None:
        logger.critical('>>>>>>>> Align Forward Start <<<<<<<<')
        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            return
        else:
            pass

        if use_scale == None: use_scale = cfg.data.scale()
        # self.main_panel_bottom_widget.setCurrentIndex(0) #og
        self.read_gui_update_project_data()
        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.hud(warning_msg, logging.WARNING)
            return
        # self.img_panels['aligned'].imageViewer.clearImage()
        img_dims = ImageSize(cfg.data.path_base())
        self.set_status('Aligning Scale %d (%d x %d pixels)...' % (get_scale_val(use_scale), img_dims[0], img_dims[1]))
        alignment_option = cfg.data['data']['scales'][use_scale]['method_data']['alignment_option']
        if alignment_option == 'init_affine':
            self.hud.post("Initializing Affine Transforms For Scale Factor %d..." % (get_scale_val(use_scale)))
        else:
            self.hud.post("Refining Affine Transform For Scale Factor %d..." % (get_scale_val(use_scale)))
        # self.al_status_checkbox.setChecked(False)
        try:
            self.worker = BackgroundWorker(fn=compute_affines(use_scale=use_scale, start_layer=cfg.data.layer(), num_layers=num_layers))
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
            cur_layer = cfg.data.layer()
            self.worker = BackgroundWorker(fn=generate_aligned(use_scale=use_scale, start_layer=cur_layer, num_layers=num_layers))
            self.threadpool.start(self.worker)
        except:

            print_exception()
            self.hud('Alignment Succeeded But Image Generation Failed Unexpectedly.'
                          ' Try Re-generating images.',logging.ERROR)
            # self.set_idle()
            return
        self.hud.done()
        # if are_aligned_images_generated():
        self.update_snr_plot()

        self.save_project_to_file() #0908+
        # self.set_progress_stage_3()

        # if self.is_neuroglancer_viewer():
        self.reload_ng()
        # elif self.is_classic_viewer():
        #     self.update_aligned_2D_viewer()
        self.pbar.hide()
    
    @Slot()
    def regenerate(self, use_scale) -> None:
        logger.info('regenerate:')
        if self._working == True:
            self.hud('Another Process is Already Running', logging.WARNING)
            self.set_idle()
            return
        # self.main_panel_bottom_widget.setCurrentIndex(0) #og
        self.read_gui_update_project_data()
        if not is_cur_scale_aligned():
            self.hud('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING)
            self.set_idle()
            return
        # self.img_panels['aligned'].imageViewer.clearImage()
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
            # self.set_progress_stage_3()
            self.read_project_data_update_gui()
            # if self.is_neuroglancer_viewer():
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
        self.pbar.hide()
    
    def export(self):
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
        out = os.path.abspath(os.path.join(src, 'img_aligned.zarr'))
        self.hud('  Compression Level: %s' %  cfg.CLEVEL)
        self.hud('  Compression Type: %s' %  cfg.CNAME)
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
    def clear_skips(self):
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
    def apply_all(self) -> None:
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
        # if self.project_progress >= 2:
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

        self.jump_validator = QIntValidator(0, cfg.data.n_imgs())
        self.update_alignment_details() #Shoehorn
    
    @Slot()
    def update_alignment_details(self) -> None:
        '''Piggy-backs its updating with 'update_scale_controls'
        Update alignment details in the Alignment control panel group box.'''
        logger.debug("Called by " + inspect.stack()[1].function)   
        # logger.info('Updating Alignment Banner Details')
        al_stack = cfg.data['data']['scales'][cfg.data.scale()]['alignment_stack']
        # self.al_status_checkbox.setChecked(is_cur_scale_aligned())
        dict = {'init_affine':'Initialize Affine','refine_affine':'Refine Affine','apply_affine':'Apply Affine'}
        method_str = dict[cfg.data['data']['scales'][cfg.data.scale()]['method_data']['alignment_option']]
        font = QFont()
        font.setBold(True)
        self.alignment_status_label.setFont(font)
        if is_cur_scale_aligned():
            self.alignment_status_label.setText("Aligned")
            self.alignment_status_label.setStyleSheet('color: #41FF00;')
            self.alignment_snr_label.setText(cfg.data.snr())
        else:
            self.alignment_status_label.setText("Not Aligned")
            self.alignment_status_label.setStyleSheet('color: red;')
            self.alignment_snr_label.setText('')
        scale_str = str(get_scale_val(cfg.data.scale()))
        # if cfg.data.skipped():
        #     self.align_label_is_skipped.setText('Is Skipped? Yes')
        # else:
        #     self.align_label_is_skipped.setText('Is Skipped? No')

        try:
            img_size = ImageSize(al_stack[0]['images']['base']['filename'])
            self.align_label_resolution.setText('%sx%spx' % (img_size[0], img_size[1]))
        except:
            logger.warning('Unable To Determine Image Sizes. Project was likely renamed.')
        #Todo fix renaming bug where files are not relinked
        # self.align_label_affine.setText(method_str)
        num_unaligned = len(cfg.data.not_aligned_list())
        if num_unaligned == 0:
            font = QFont()
            font.setBold(True)
            self.alignment_status_label.setFont(font)
            self.align_label_scales_remaining.setText('All Scales Aligned')
            self.align_label_scales_remaining.setStyleSheet('color: #41FF00;')
        else:
            font = QFont()
            font.setBold(False)
            self.alignment_status_label.setFont(font)
            self.align_label_scales_remaining.setText('# Unaligned: %d' % num_unaligned)
            self.align_label_scales_remaining.setStyleSheet('color: #f3f6fb;')


        # if not do_scales_exist():
        #     cur_scale_str = 'Scale: n/a'
        #     self.align_label_cur_scale.setText(cur_scale_str)
        # else:
        #     cur_scale_str = 'Scale: ' + str(scale_val(cfg.data.scale()))
        #     self.align_label_cur_scale.setText(cur_scale_str)
        logger.info('Exiting update_alignment_details')

    
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
    def scale_up(self) -> None:
        # if self.image_panel_stack_widget.currentIndex() == 1: return

        logger.info('scale_up:')

        '''Callback function for the Next Scale button (scales combobox may not be visible but controls the current scale).'''
        if not self.scale_up_button.isEnabled(): return
        if not are_images_imported(): return
        if self._working:
            self.hud('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            # self.clear_images()
            # self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index - 1
            self.scales_combobox.setCurrentIndex(requested_index)  # Changes The Scale
            self.read_project_data_update_gui()
            self.update_scale_controls()
            self.hud('Scale Changed to %d' % get_scale_val(cfg.data.scale()))
            if not cfg.data.is_alignable():
                self.hud('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)

            # if self.is_neuroglancer_viewer():
            self.reload_ng()
            # elif self.is_classic_viewer():
            #     self.update_2D_viewers()

            self.update_snr_plot()

        except:
            print_exception()

    
    @Slot()
    def scale_down(self) -> None:
        logger.info('scale_down:')
        '''Callback function for the Previous Scale button (scales combobox may not be visible but controls the current scale).'''
        if not self.scale_down_button.isEnabled(): return
        if not are_images_imported(): return
        if self._working:
            self.hud('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            # self.clear_images()

            # self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index + 1
            self.scales_combobox.setCurrentIndex(requested_index)  # changes scale
            self.read_project_data_update_gui()

            # self.update_aligned_2D_viewer()
            self.update_scale_controls()
            self.hud('Scale Changed to %d' % get_scale_val(cfg.data.scale()))
            if not cfg.data.is_alignable():
                self.hud('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)

            # if self.main_panel_bottom_widget.currentIndex() == 1: #og
            # self.plot_widget.clear()
            self.update_snr_plot()

            # if self.is_neuroglancer_viewer():
            self.reload_ng()
            # elif self.is_classic_viewer():
            #     self.update_2D_viewers()

        except:
            print_exception()

    @Slot()
    def update_skip_toggle(self):
        logger.info('update_skip_toggle:')
        scale = cfg.data['data']['scales'][cfg.data['data']['current_scale']]
        logger.info("cfg.data.skipped() = ", cfg.data.skipped())
        self.toggle_skip.setChecked(not cfg.data.skipped())
        # if cfg.data.skipped():
        #     self.align_label_is_skipped.setText('Is Skipped? Yes')
        # else:
        #     self.align_label_is_skipped.setText('Is Skipped? No')


    @Slot()
    def set_status(self, msg: str) -> None:
        self.statusBar.showMessage(msg)
    
    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')
    
    def apply_default_style(self):
        '''
        #colors
        color: #f3f6fb;  /* snow white */
        color: #004060;  /* drafting blue */
        '''


        # self.hud('Applying Default Theme')
        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        # self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        # self.python_console.set_color_linux()
        self.python_console.set_color_none()
        self.hud.set_theme_default()
        self.python_console.setStyleSheet('background-color: #004060; border-width: 0px; color: #f3f6fb;')
        # drafting blue : #004060
        self.scales_combobox.setStyleSheet('background-color: #f3f6fb; color: #000000;')
        # self.image_panel_stack_widget.setStyleSheet('background-color: #f3f6fb;') #bg-color= viewer border
        # self.image_panel_stack_widget.setStyleSheet('background-color: #000000;')
        # self.image_panel_stack_widget.setStyleSheet('background-color: #004060;')
        self.image_panel_landing_page.setStyleSheet('background-color: #004060;')
        # self.details_banner.setStyleSheet("""color: #F3F6FB; font-size: 14px;""")
        # self.details_banner.setStyleSheet("""color: #ffe135; font-size: 14px;""")
        # self.details_banner.setStyleSheet("""color: #FFF9A6; font-size: 14px;""")
        # self.details_banner.setStyleSheet("""background-color: #000000; color: #ffe135; font-size: 14px;""")
        self.details_banner.setStyleSheet("""background-color: #000000; color: #f3f6fb; font-size: 14px;""")
        # self.reset_groupbox_styles()

    def apply_daylight_style(self):
        '''Light stylesheet'''
        # self.hud('Applying Daylight Theme')
        self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_none()
        self.hud.set_theme_light()
        self.image_panel_landing_page.setStyleSheet('background-color: #fdf3da')
        # self.reset_groupbox_styles()
    
    def apply_moonlit_style(self):
        '''Grey stylesheet'''
        # self.hud('Applying Moonlit Theme')
        self.main_stylesheet = os.path.abspath('src/styles/moonlit.qss')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #333333')
        # self.reset_groupbox_styles()
    
    def apply_sagittarius_style(self):
        # self.hud('Applying Sagittarius Theme')
        self.main_stylesheet = os.path.abspath('src/styles/sagittarius.qss')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.python_console.set_color_linux()
        self.hud.set_theme_default()
        self.image_panel_landing_page.setStyleSheet('background-color: #000000')
        # self.reset_groupbox_styles()
    
    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')

        #1001
        # self.alignment_stack.setStyleSheet("""QGroupBox {border: 1px dotted #171d22;}""")
        # self.postalignment_stack.setStyleSheet("""QGroupBox {border: 1px dashed #171d22;}""")
        # self.export_and_view_stack.setStyleSheet("""QGroupBox {border: 1px dashed #171d22;}""")

        # self.project_functions_stack.setStyleSheet(open(self.main_stylesheet).read())
        # self.alignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        # self.postalignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        # self.export_and_view_stack.setStyleSheet(open(self.main_stylesheet).read())

    # def auto_set_user_progress(self):
    #     '''Set user progress (0 to 3). This is only called when user opens a data.'''
    #     logger.debug('auto_set_user_progress:')
    #     if is_any_scale_aligned_and_generated():  self.set_progress_stage_3()
    #     elif do_scales_exist():  self.set_progress_stage_2()
    #     elif is_destination_set():  self.set_progress_stage_1()
    #     else:  self.set_progress_stage_0()
    
    def set_user_progress(self, gb1: bool, gb2: bool, gb3: bool, gb4: bool) -> None:
        logger.debug('set_user_progress:')
        # gb1 = None # Unused due to removal of images and scaling groupbox
        # self.alignment_stack.setCurrentIndex((0, 1)[gb2])
        # self.alignment_stack.setStyleSheet(
        #     ("""QGroupBox {border: 1px dotted #171d22;}""",
        #      open(self.main_stylesheet).read())[gb2])
        # self.postalignment_stack.setCurrentIndex((0, 1)[gb3])
        # self.postalignment_stack.setStyleSheet(
        #     ("""QGroupBox {border: 1px dashed #171d22;}""",
        #      open(self.main_stylesheet).read())[gb3])
        # self.export_and_view_stack.setCurrentIndex((0, 1)[gb4])
        # self.export_and_view_stack.setStyleSheet(
        #     ("""QGroupBox {border: 1px dashed #171d22;}""",
        #      open(self.main_stylesheet).read())[gb4])

    # def cycle_user_progress(self):
    #     self._up += 1
    #     up = self._up % 4
    #     if up == 0:    self.set_progress_stage_1()
    #     elif up == 1:  self.set_progress_stage_2()
    #     elif up == 2:  self.set_progress_stage_3()
    #     elif up == 3:  self.set_progress_stage_0()
    
    def set_progress_stage_0(self):
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


        # cfg.CNAME = self.cname_combobox.currentText()
        # cfg.CLEVEL = int(self.clevel_input.text())

    
    @Slot()
    def read_project_data_update_gui(self) -> None:
        '''Reads Project Data to Update MainWindow.'''
        logger.debug('read_project_data_update_gui:')
        if not do_scales_exist():
            logger.warning('No Scaled Images. Nothing To Do (Caller: %s)' % inspect.stack()[1].function)
            return

        try:  self.toggle_skip.setChecked(not cfg.data.skipped())
        except:  logger.warning('Skip Toggle Widget Failed to Update')

        try:  self.jump_input.setText(str(cfg.data.layer()))
        except:  logger.warning('Current Layer Widget Failed to Update')

        try:  self.whitening_input.setText(str(cfg.data.whitening()))
        except:  logger.warning('Whitening Input Widget Failed to Update')

        try:  self.swim_input.setText(str(cfg.data.swim_window()))
        except:  logger.warning('Swim Input Widget Failed to Update')

        try: self.toggle_bounding_rect.setChecked(cfg.data.bounding_rect())
        except: logger.warning('Bounding Rect Widget Failed to Update')

        if  cfg.data.null_cafm() == False:  self.null_bias_combobox.setCurrentText('None')
        else:  self.null_bias_combobox.setCurrentText(str(cfg.data.poly_order()))

        if  cfg.data.layer() == 0:  self.prev_layer_button.setEnabled(False)
        else:  self.prev_layer_button.setEnabled(True)

        if  cfg.data.layer() == cfg.data.n_imgs() - 1: self.next_layer_button.setEnabled(False)
        else:  self.next_layer_button.setEnabled(True)

        self.update_alignment_details()
        self.jump_input.setText(str(cfg.data.layer()))

        # self.skip_label.setText('Use Image #%d?' % cfg.data.layer())

        self.align_all_button.setText('Align\n%s' % cfg.data.scale_pretty())

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
        if self._working == False:
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
        # if self.image_panel_stack_widget.currentIndex() == 1:
        self.reload_ng()

    
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
            # if self.image_panel_stack_widget.currentIndex() == 1:
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
        logger.info('Reloading Scale Combobox...')
        logger.debug('Caller: %s' % inspect.stack()[1].function)
        self.scales_combobox_switch = 0
        curr_scale = cfg.data.scale()
        image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.data['data']['scales'].keys())]
        self.scales_combobox.clear()
        for scale in sorted(image_scales_to_run):
            self.scales_combobox.addItems(["scale_" + str(scale)])
        index = self.scales_combobox.findText(curr_scale, Qt.MatchFixedString)
        if index >= 0: self.scales_combobox.setCurrentIndex(index)
        self.scales_combobox_switch = 1
    
    @Slot()
    def fn_scales_combobox(self) -> None:
        logger.info('fn_scales_combobox')
        logger.info('self.scales_combobox_switch = %s' % self.scales_combobox_switch)
        if self.scales_combobox_switch == 0:
            logger.warning('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return None
        if self._working:
            logger.warning('fn_scales_combobox was called but _working is True -> ignoring the signal')
            return None
        # if self.image_panel_stack_widget.currentIndex() == 1:


        cfg.data.set_scale(self.scales_combobox.currentText())
        self.read_project_data_update_gui()
        self.update_scale_controls()
        # self.update_2D_viewers()
        self.reload_ng()

    @Slot()
    def fn_ng_layout_combobox(self) -> None:
        try:
            if self.ng_layout_combobox.currentText() == 'xy':
                self.ng_worker.set_layout_xy()
            elif self.ng_layout_combobox.currentText() == 'yz':
                self.ng_worker.set_layout_yz()
            elif self.ng_layout_combobox.currentText() == 'xz':
                self.ng_worker.set_layout_xz()
            elif self.ng_layout_combobox.currentText() == 'xy-3d':
                self.ng_worker.set_layout_xy_3d()
            elif self.ng_layout_combobox.currentText() == 'yz-3d':
                self.ng_worker.set_layout_yz_3d()
            elif self.ng_layout_combobox.currentText() == 'xz-3d':
                self.ng_worker.set_layout_xz_3d()
            elif self.ng_layout_combobox.currentText() == '3d':
                self.ng_worker.set_layout_3d()
            elif self.ng_layout_combobox.currentText() == '4panel':
                self.ng_worker.set_layout_4panel()
            self.reload_ng()
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


    @Slot()
    def change_layer_up(self):
        logger.info('change_layer_up:')
        # if self.image_panel_stack_widget.currentIndex() == 1: return
        self.change_layer(1)

    @Slot()
    def change_layer_down(self):
        logger.info('change_layer_down:')
        # if self.image_panel_stack_widget.currentIndex() == 1: return
        self.change_layer(-1)

    def change_layer(self, layer_delta):
        """This function loads the next or previous layer"""
        # logger.info('change_layer:')
        try:
            self.set_status('Loading...')
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
            self.read_project_data_update_gui()

            # if self.is_neuroglancer_viewer():
            state = copy.deepcopy(cfg.viewer.state)
            state.position[0] = requested
            cfg.viewer.set_state(state)

            # if self.is_classic_viewer():
            #     if are_aligned_images_generated():
            #         self.img_panels['aligned'].setCurrentIndex(requested)
            #     self.update_unaligned_2D_viewer()

        # painter = QPainter(self)
        # s, l = cfg.data.scale(), cfg.data.layer()
        # if cfg.data.skipped():
        #     if self.role == 'base':
        #         red_color = [255, 50, 50]
        #         painter.setPen(QPen(QColor(*red_color), 3))
        #         factor = 6
        #         width = painter.viewport().width() / factor
        #         height = painter.viewport().height() / factor
        #         # x1a, y1a, x2a, y2a = 0, 0, width, height
        #         # x1b, y1b, x2b, y2b = 0, width, height, 0
        #         x1a, y1a, x2a, y2a = 0, painter.viewport().height(), width, painter.viewport().height() - height
        #         x1b, y1b, x2b, y2b = 0, painter.viewport().height() - height, width, painter.viewport().height()
        #         # x1a, y1a, x2a, y2a = 0, 0, width, height
        #         # x1b, y1b, x2b, y2b = 0, width, height, 0
        #         painter.drawLine(x1a, y1a, x2a, y2a)
        #         painter.drawLine(x1b, y1b, x2b, y2b)
        #
        #         # button = QPushButton("Test")
        #
        #         # painter.setOpacity(0.5)
        #         # painter.setOpacity(0)
        #         # painter.setBrush(Qt.black)  # Background
        #         # painter.drawRect(x1a, y1a, x2a, y2a)
        #         # painter.setPen(QPen(Qt.red))  # Border
        #
        #     # if self.role == 'base':
        #     #     width = painter.viewport().width() / factor
        #     #     height = painter.viewport().height() / factor
        #     #     x1b, y1b, x2b, y2b = 0, painter.viewport().height() - height, width, painter.viewport().height()
        #     #     painter.drawText(x1b, y1b, 'SKIP')
        #
        #     painter.setOpacity(0.5)
        #     painter.setBrush(Qt.black)  # Entire MultiImagePanel Background
        #     painter.setPen(QPen(Qt.black))  # Border
        #     # rect = QRect(0, 0, painter.viewport().width(), painter.viewport().height())
        #     painter.drawRect(painter.viewport())
        #
        #     # painter.fillRect(rect, QBrush(QColor(128, 128, 255, 128)))
        except:
            print_exception()
        finally:
            self.set_idle()


    def load_unaligned_stacks(self):
        # logger.critical('Getting Results of Unaligned TensorStore Objects...')
        self.zarr_scales = {}
        try:
            for s in cfg.data.scales():
                # name = os.path.join(cfg.data.dest(), s + '.zarr')
                name = os.path.join(cfg.data.dest(), 'img_src.zarr', 's' + str(get_scale_val(s)))
                dataset_future = get_zarr_tensor(name)
                scale_str = 's' + str(get_scale_val(s))
                self.zarr_scales[scale_str] = dataset_future.result()
        except:
            print_exception()
            logger.warning('Unaligned Zarr Stacks May Not Have Loaded Properly')


    # @Slot()
    # def update_unaligned_2D_viewer(self):
    #     '''Called by read_project_data_update_gui '''
    #     logger.debug('update_unaligned_2D_viewer:')
    #     if self.image_panel_stack_widget.currentIndex() == 0:
    #         # cfg.image_library.preload_images(cfg.data.layer())
    #         s, l, dest = cfg.data.scale(), cfg.data.layer(), cfg.data.dest()
    #         logger.info('s,l,dest = %s, %s, %s' % (cfg.data.scale(), str(cfg.data.layer()), cfg.data.dest()))
    #         image_dict = cfg.data['data']['scales'][s]['alignment_stack'][l]['images']
    #         is_skipped = cfg.data['data']['scales'][s]['alignment_stack'][l]['skipped']
    #         scale_str = 's' + str(get_scale_val(cfg.data.scale()))
    #
    #         try:
    #             if l != 0:
    #                 x_ref, x_base = self.zarr_scales[scale_str][l-1, :, :], self.zarr_scales[scale_str][l, :, :]
    #                 future_ref, future_base = x_ref.read(), x_base.read()
    #                 logger.debug('Setting image ref')
    #                 self.img_panels['ref'].setImage(future_ref.result())
    #                 logger.debug('Setting image base')
    #                 self.img_panels['base'].setImage(future_base.result())
    #             elif l == 0:
    #                 self.img_panels['ref'].clearImage()
    #                 x_base = self.zarr_scales[scale_str][l, :, :]
    #                 future_base = x_base.read()
    #                 logger.debug('Setting image base')
    #                 self.img_panels['base'].setImage(future_base.result())
    #
    #         except:
    #             print_exception()
    #             logger.warning('Unable To Render Unaligned Stacks')
    #     else:
    #         logger.warning("update_unaligned_2D_viewer was called by '%s' but 2D viewer is not being used" % inspect.stack()[1].function)


    # def update_aligned_2D_viewer(self):
    #     logger.critical('update_aligned_2D_viewer:')
    #     if self.image_panel_stack_widget.currentIndex() == 0:
    #         if is_cur_scale_aligned():
    #             dest = cfg.data.dest()
    #             zarr_path = os.path.join(dest, 'img_aligned.zarr')
    #             path = os.path.join(zarr_path, 's' + str(cfg.data.scale_val()))
    #             # np_data = zarr.load(path)
    #             # np_data = np.transpose(np_data, axes=[1, 2, 0])
    #             # zarr_data = da.from_zarr(path, inline_array=True) # <class 'dask.array.core.Array' #orig
    #             # zarr_data = np.moveaxis(zarr_data,0,2) # Now has shape (512, 512, 1)
    #             dataset_future = get_zarr_tensor(path)
    #
    #             logger.info('Calling dataset_future.result()')
    #             t0 = time.time()
    #             dataset = dataset_future.result()
    #             dt = time.time() - t0
    #             logger.info('dataset_future.result() Finished In %g Seconds' % dt)
    #             logger.info('dataset.domain: %s' % dataset.domain)
    #             # dataset.domain = { [0, 100*), [0, 1354*), [0, 1354*) }
    #             # zarr_data = np.asarray(tensor_arr.result())
    #             # zarr_data = np.moveaxis(zarr_data, 0, 2)  # Now has shape (512, 512, 1)
    #             # self.img_panels['aligned'].setImage(zarr_data)
    #             self.img_panels['aligned'].setImage(dataset)
    #             self.img_panels['aligned'].setCurrentIndex(cfg.data.layer())
    #         else:
    #             self.img_panels['aligned'].imageViewer.clearImage()
    #             logger.warning('No Aligned Stack for Current Scale')
    #
    #         # th_ref = threading.Thread(target=cfg.image_library.get_image_reference, args=("image_dict['ref']['filename']"))
    #         # th_base = threading.Thread(target=cfg.image_library.get_image_reference, args=("image_dict['base']['filename']"))
    #     else:
    #         logger.warning("update_aligned_2D_viewer was called by '%s' but 2D viewer is not being used" % inspect.stack()[1].function)

    # @Slot()
    # def update_2D_viewers(self):
    #     logger.critical('Updating 2D viewers... called By %s' % inspect.stack()[1].function)
    #     if self.is_classic_viewer():
    #         if are_images_imported():
    #             logger.critical('Images Are Imported')
    #             try:     self.update_unaligned_2D_viewer()
    #             except:  logger.warning('An exception occurred while attempting to update unaligned image panels')
    #         # if is_cur_scale_aligned():
    #         # if are_aligned_images_generated():
    #         #     logger.critical('Scale Is Aligned')
    #         #     try:     self.update_aligned_2D_viewer()
    #         #     except:  logger.warning('An exception occurred while attempting to update aligned image panel')
    #     else:
    #         logger.warning("update_2D_viewers was called by '%s' but classic viewer is not in use" % inspect.stack()[1].function)


    # @Slot()
    # def clear_images(self):
    #     self.img_panels['ref'].clearImage()
    #     self.img_panels['base'].clearImage()
    #     self.img_panels['aligned'].imageViewer.clearImage()

    
    # @Slot()
    # def print_image_library(self):
    #     self.hud(str(cfg.image_library))
    
    def new_project(self):
        logger.critical('>>>>>>>> New Project Start <<<<<<<<')
        self.set_status("New Project...")
        # cfg.w.ng_browser.back() # create the effect of resetting the browser
        if is_destination_set():
            logger.info('Asking user to confirm new data')
            msg = QMessageBox(QMessageBox.Warning,
                              'Confirm New Project',
                              'Please confirm create new project.',
                              buttons=QMessageBox.Cancel | QMessageBox.Ok)
            msg.setIcon(QMessageBox.Question)
            button_cancel = msg.button(QMessageBox.Cancel)
            button_cancel.setText('Cancel')
            button_ok = msg.button(QMessageBox.Ok)
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
        # self.image_panel_stack_widget.setCurrentIndex(2)
        self.clear_snr_plot()
        # self.set_normal_view()
        # self.set_splash_controls()
        # self.set_progress_stage_0()
        self.reset_details_banner()
        self.hud('Creating A Project...')
        # cfg.image_library.remove_all_images()
        # self.img_panels['ref'].clearImage()
        # self.img_panels['base'].clearImage()
        # self.img_panels['aligned'].imageViewer.clearImage()
        filename = self.new_project_save_as_dialog()
        if filename == '':
            self.hud("Project Canceled.")
            self.set_idle()
            return

        # self.clear_images()
        logger.info("Overwriting Project Data In Memory With New Template")
        if not filename.endswith('.proj'):
            filename += ".proj"
        path, extension = os.path.splitext(filename)
        cfg.data = DataModel(name=path)
        self.image_panel_stack_widget.setCurrentIndex(2)
        makedirs_exist_ok(cfg.data['data']['destination_path'], exist_ok=True)
        self.hud.done()
        self.setWindowTitle("Project: " + os.path.split(cfg.data.dest())[-1])
        self.save_project()
        # self.set_progress_stage_1()
        self.scales_combobox.clear()  # why? #0528
        cfg.IMAGES_IMPORTED = False
        self.import_images()
        self.run_after_import()
        self.save_project_to_file()
        self.use_neuroglancer_viewer()
        self.set_idle()
    
    def import_images_dialog(self):
        '''Dialog for importing images. Returns list of filenames.'''
        # caption = "Import Images"
        # # filter = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)"
        # # filter = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif .bmp)"
        # filter = 'Images (*.tif *.tiff)'
        # # if qtpy.QT5:
        # options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
        # response = QFileDialog.getOpenFileNames(
        #     parent=self,
        #     caption=caption,
        #     filter=filter,
        #     options=options,
        #     # options=options
        # )
        # dlg = QFileDialog()
        # dlg.setFileMode(QFileDialog.AnyFile)
        # dlg.setFilter("Text files (*.txt)")

        dialog = QFileDialog()
        dialog.setOption(QFileDialog.DontUseNativeDialog)
        # dialog.setProxyModel(FileFilterProxyModel())
        dialog.setWindowTitle('Import Images')
        dialog.setNameFilter('Images (*.tif *.tiff)')
        dialog.setFileMode(QFileDialog.ExistingFiles)

        urls = []
        urls.append(QUrl.fromLocalFile(QDir.homePath()))
        if '.tacc.utexas.edu' in platform.node():
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
        dialog.setSidebarUrls(urls)

        # response = dialog.exec()
        logger.info(dialog.selectedFiles())
        logger.info('dialog.Accepted = %s' % dialog.Accepted)
        if dialog.exec_() == QDialog.Accepted:
            self.set_project_controls()
            self.set_normal_view()
            self.show_all_controls()
            return dialog.selectedFiles()
        else:
            if dialog.exec_() == QDialog.Accepted:
                self.set_project_controls()
                self.set_normal_view()
                self.show_all_controls()
                return dialog.selectedFiles()

    
    def open_project_dialog(self) -> str:
        '''Dialog for opening a data. Returns 'filename'.'''
        caption = "Open Project (.proj)"
        filter = "Project (*.proj)"
        # if qtpy.QT5:
        # options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getOpenFileName(
            parent=self,
            caption=caption,
            filter=filter,
            # options=options,
        )
        # dialog = QFileDialog()
        # dialog.setOption(QFileDialog.DontUseNativeDialog)
        # # dialog.setProxyModel(FileFilterProxyModel())
        # dialog.setWindowTitle('Open Project (.json)')
        # dialog.setNameFilter("Text Files (*.json)")
        # dialog.exec()

        return response[0]
        # return dialog.selectedFiles()[0]

    def save_project_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        caption = "Save Project"
        filter = "Project (*.proj)"
        # if qtpy.QT5:
        # options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
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
        filter = "Project (*.proj)"
        # if qtpy.QT5:
        #     options = QFileDialog.Options()
        #     options |= QFileDialog.DontUseNativeDialog
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
        logger.critical('>>>>>>>> Open Project Start <<<<<<<<')
        self.set_status("Open Project...")
        # is_neuroglancer_viewer = True if self.is_neuroglancer_viewer() else False
        self.main_widget.setCurrentIndex(0)
        self.image_panel_stack_widget.setCurrentIndex(2)
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
        # self.main_panel_bottom_widget.setCurrentIndex(0)
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

            self.set_project_controls()
            self.set_normal_view()

            project.set_paths_absolute(head=filename)
            cfg.data = copy.deepcopy(project)  # Replace the current version with the copy
            cfg.data.link_all_stacks()

            self.setWindowTitle("Project: %s" % os.path.basename(cfg.data.dest()))
            if are_images_imported():
                # if is_neuroglancer_viewer:
                self.load_unaligned_stacks()
                self.use_neuroglancer_viewer()  # force neuroglancer viewer (changes stack index)
                # else:
                #     self.update_2D_viewers()
                # self.image_panel_stack_widget.setCurrentIndex(1)

                cfg.IMAGES_IMPORTED = True
            else:
                cfg.IMAGES_IMPORTED = False
            self.read_project_data_update_gui()
            self.clear_snr_plot()
            self.update_snr_plot()
            # self.update_snr_plot()
            # self.auto_set_user_progress()
            # self.set_user_progress(gb1=True, gb3=True,gb4=True) #1001
            self.reload_scales_combobox()
            self.update_scale_controls()
        else:
            self.hud("No Project File (.proj) Selected", logging.WARNING)
        self.set_idle()

    def save_project(self):
        logger.info('Entering save_project...')
        if self._splash:
            logger.info('Nothing To Save')
            return
        logger.info('About to call self.set_status()...')
        self.set_status("Saving...")
        logger.info('About to write to HUD...')
        self.hud.post('Saving Project...')
        # self.main_panel_bottom_widget.setCurrentIndex(0) #og
        logger.info('Trying...')
        try:
            logger.info('About to save_project_to_file...')
            self.save_project_to_file()
            logger.info('About to write done to HUD...')
            # self.hud.done()
            logger.info('Setting self._unsaved_changes = False...')
            self._unsaved_changes = False
            self.hud.post("Project File Location:\n%s" % str(cfg.data.dest() + ".proj"))
        except:
            print_exception()
            self.hud.post('Nothing To Save', logging.WARNING)
        finally:
            logger.info('Doing the finally...')
            self.set_idle()
        logger.info('Exiting save_project')


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
        logger.info("Called by " + inspect.stack()[1].function)
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
        logger.info('---- SAVING DATA TO PROJECT FILE ----')
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        proj_json = jde.encode(data_cp)
        name = cfg.data.dest()
        if not name.endswith('.proj'): #0818-
            name += ".proj"
        with open(name, 'w') as f:
            f.write(proj_json)
        logger.info('Exiting save_project_to_file...')

    @Slot()
    def has_unsaved_changes(self):
        logger.debug("Called by " + inspect.stack()[1].function)
        if inspect.stack()[1].function == 'initUI':
            return
        if inspect.stack()[1].function == 'read_project_data_update_gui':
            return
        self._unsaved_changes = True

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
        logger.critical('>>>>>>>> Import Images Start <<<<<<<<')
        self.set_status('Import Images...')
        role_to_import = 'base'
        # need_to_scale = not are_images_imported()
        # filenames = sorted(self.import_images_dialog())
        try:
            filenames = natural_sort(self.import_images_dialog())
        except:
            logger.warning('No images were selected.')
            self.set_idle()
            return
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

        self.hud.done()
        if are_images_imported():
            cfg.IMAGES_IMPORTED = True
            img_size = ImageSize(
                cfg.data['data']['scales']['scale_1']['alignment_stack'][0]['images'][str(role_to_import)]['filename'])
            cfg.data.link_all_stacks()

            self.save_project_to_file()
            self.hud.post('%d Images Imported' % cfg.data.n_imgs())
            self.hud.post('Image Dimensions: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)
        logger.info('about to call use_neuroglancer_viewer...')
        sys.stdout.flush()
        # self.scales_combobox_switch = 1
        self.set_idle()
        logger.info('Exiting import_images')

    def run_after_import(self):
        logger.info('run_after_import:')
        recipe_maker = RecipeMaker(parent=self)
        result = recipe_maker.exec_()  # result = 0 or 1
        if not result:
            logger.warning('Dialog Did Not Return A Result')
            return
        else:
            # self.update_unaligned_2D_viewer() # Can't show image stacks before creating Zarr scales
            self.autoscale()
        self.pbar.hide()
        logger.info('Exiting autoscale')




    def set_splash_controls(self):
        logger.info('Setting Splash Controls...')
        self._splash = True


        self.title_label.show()
        self.subtitle_label.show()
        # self.bottom_display_area_widget.hide()
        self.hud.hide()
        self.snr_plot.hide()
        # self.bottom_display_area_controls.hide()
        self.bottom_widget.hide()
        self.dual_viewer_w_banner.hide()
        self.menu.hide()

        self.control_panel.setStyleSheet('background-color: #f3f6fb;')
        self.main_splitter.setAutoFillBackground(True)

        # self.bottom_display_area_widget.setMaximumHeight(200)
        # self.bottom_display_area_controls.setMaximumHeight(200)
        self.bottom_widget.setMaximumHeight(200)

        self.resize(100,100)

        self.control_panel.setMaximumHeight(140)

        # self.setWindowFlags(Qt.WindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint))

        button_h, button_w = 100, 40
        self.image_panel_stack_widget.setCurrentIndex(2)
        self.new_project_button.setMinimumSize(button_h, button_w)
        self.open_project_button.setMinimumSize(button_h, button_w)
        self.save_project_button.setMinimumSize(button_h, button_w)
        self.exit_app_button.setMinimumSize(button_h, button_w)
        self.documentation_button.setMinimumSize(button_h, button_w)
        self.remote_viewer_button.setMinimumSize(button_h, button_w)
        # self.import_images_button.setMinimumSize(button_h, button_w)
        try:
            self.alignment_widget.hide()
        except:
            pass
        font_size = 16
        # self.import_images_button.setStyleSheet('font-size: %spx;' % font_size)
        self.new_project_button.setStyleSheet('font-size: %spx;' % font_size)
        self.open_project_button.setStyleSheet('font-size: %spx;' % font_size)
        self.save_project_button.setStyleSheet('font-size: %spx;' % font_size)
        self.remote_viewer_button.setStyleSheet('font-size: %spx;' % font_size)
        self.documentation_button.setStyleSheet('font-size: %spx;' % font_size)
        self.exit_app_button.setStyleSheet('font-size: %spx;' % font_size)

        icon_size = 24
        # self.import_images_button.setIconSize(QSize(icon_size, icon_size))
        self.new_project_button.setIconSize(QSize(icon_size, icon_size))
        self.open_project_button.setIconSize(QSize(icon_size, icon_size))
        self.save_project_button.setIconSize(QSize(icon_size, icon_size))
        self.remote_viewer_button.setIconSize(QSize(icon_size, icon_size))
        self.documentation_button.setIconSize(QSize(icon_size, icon_size))
        self.exit_app_button.setIconSize(QSize(icon_size, icon_size))


    def set_project_controls(self):
        logger.info('Setting Project Controls...')

        self._splash = False

        self.title_label.hide()
        self.subtitle_label.hide()

        self.hud.show()
        self.snr_plot.show()

        # self.bottom_display_area_controls.show() # <- culprit
        self.bottom_widget.show() # <- culprit
        self.dual_viewer_w_banner.show()

        # self.image_panel_stack_widget.setCurrentIndex(1)


        self.alignment_widget.show()
        self.menu.show()
        # self.bottom_display_area_widget.setMaximumHeight(1000)
        # self.bottom_display_area_controls.setMaximumHeight(1000)
        self.bottom_widget.setMaximumHeight(1200)
        self.control_panel.setMinimumHeight(100)

        self.new_project_button.setMinimumSize(1, 1)
        self.open_project_button.setMinimumSize(1, 1)
        self.save_project_button.setMinimumSize(1, 1)
        self.exit_app_button.setMinimumSize(1, 1)
        self.documentation_button.setMinimumSize(1, 1)
        self.remote_viewer_button.setMinimumSize(1, 1)
        # self.import_images_button.setMinimumSize(1, 1)

        font_size = 12
        # self.import_images_button.setStyleSheet('font-size: %spx;' % font_size)
        self.new_project_button.setStyleSheet('font-size: %spx;' % font_size)
        self.open_project_button.setStyleSheet('font-size: %spx;' % font_size)
        self.save_project_button.setStyleSheet('font-size: %spx;' % font_size)
        self.remote_viewer_button.setStyleSheet('font-size: %spx;' % font_size)
        self.documentation_button.setStyleSheet('font-size: %spx;' % font_size)
        self.exit_app_button.setStyleSheet('font-size: %spx;' % font_size)

        icon_size = 12
        # self.import_images_button.setIconSize(QSize(icon_size, icon_size))
        self.new_project_button.setIconSize(QSize(icon_size, icon_size))
        self.open_project_button.setIconSize(QSize(icon_size, icon_size))
        self.save_project_button.setIconSize(QSize(icon_size, icon_size))
        self.remote_viewer_button.setIconSize(QSize(icon_size, icon_size))
        self.documentation_button.setIconSize(QSize(icon_size, icon_size))
        self.exit_app_button.setIconSize(QSize(icon_size, icon_size))

        self.adjustSize()




    # @Slot()
    # def actual_size_callback(self):
    #     logger.info('MainWindow.actual_size_callback:')
    #     # self.image_panel.all_images_actual_size()

    # @Slot()
    # def clear_zoom(self, all_images_in_stack=True):
    #     '''
    #     self.image_panel is a MultiImagePanel object'''
    #     # logger.info('Called By %s' % inspect.stack()[1].function)
    #     try:
    #         if are_images_imported():
    #             self.img_panels['ref'].clearZoom()
    #             self.img_panels['base'].clearZoom()
    #             if is_cur_scale_aligned():
    #                 self.img_panels['aligned'].imageViewer.clearZoom()
    #     except:
    #         logger.warning('Centering All Images Raised An Exception')



    @Slot()
    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent (called by %s):" % inspect.stack()[1].function)
        self.shutdownInstructions()
        logger.info('Running shutdown instructions again...')
        self.shutdownInstructions() # Run Shutdown Instructions 2x

    @Slot()
    def exit_app(self):
        logger.critical("Exiting The Application...")
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

        self.shutdownInstructions()
        logger.info('Running shutdown instructions again...')
        self.shutdownInstructions() # Run Shutdown Instructions 2x


    def shutdownInstructions(self):
        logger.info('Running Shutdown Instructions...')

        try:
            logger.info('Shutting down jupyter...')
            self.shutdownJupyter()
        except:
            sys.stdout.flush()
            logger.info('Having trouble shutting down jupyter')
        else:
            logger.info('done')

        try:
            self.ng_worker.http_server.server_close()
            # self.ng_worker.http_server.shutdown()

            logger.info('Closing http server on port %s...' % str(self.ng_worker.http_server.server_port))
        except:
            sys.stdout.flush()
            logger.info('Having trouble closing http_server')
        else:
            logger.info('done')

        try:
            if neuroglancer.server.is_server_running():
                logger.info('Stopping Neuroglancer Server...')
                neuroglancer.server.stop()
        except:
            sys.stdout.flush()
            logger.warning('Having trouble shutting down neuroglancer')
        else:
            logger.info('done')

        try:
            logger.info('Shutting down threadpool...')
            threadpool_result = self.threadpool.waitForDone(msecs=500)
            logger.info('threadpool_result = %s' % str(threadpool_result))
        except:
            logger.warning('Having trouble shutting down threadpool')
        else:
            logger.info('done')

        logger.info('Quitting app...')
        self.app.quit()
        # logger.info('Calling sys.exit()')
        # logger.info('Calling system exit...')
        # sys.exit() # this may need to be called from main thread


    def documentation_view(self):  # documentationview
        self.hud("Switching to AlignEM_SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
        self.main_widget.setCurrentIndex(1)

    def documentation_view_home(self):
        self.hud("Viewing AlignEM-SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README.md'))

    def remote_view(self):
        self.hud("Switching to Remote Neuroglancer Server")
        # self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.main_widget.setCurrentIndex(3)

    def reload_ng(self):
        logger.info("Reloading Neuroglancer Viewer...")
        # self.use_neuroglancer_viewer()
        self.ng_worker.create_viewer()
        self.ng_browser.setUrl(QUrl(self.ng_worker.url()))
        self.ng_browser.setFocus()
        self.read_project_data_update_gui()


    def use_neuroglancer_viewer(self):  #view_3dem #ngview #neuroglancer
        '''
        https://github.com/google/neuroglancer/blob/566514a11b2c8477f3c49155531a9664e1d1d37a/src/neuroglancer/ui/default_input_event_bindings.ts
        https://github.com/google/neuroglancer/blob/566514a11b2c8477f3c49155531a9664e1d1d37a/src/neuroglancer/util/event_action_map.ts
        '''
        logger.info('Entering use_neuroglancver_viewer()...')
        sys.stdout.flush()
        self.set_status('Loading Neuroglancer...')
        if not are_images_imported():
            self.hud.post('Nothing To View', logging.WARNING)
            return
        logger.info("Switching To Neuroglancer Viewer")
        self.image_panel_stack_widget.setCurrentIndex(1)
        dest = os.path.abspath(cfg.data['data']['destination_path'])
        s, l = cfg.data.scale(), cfg.data.layer()
        self.ng_worker = NgHost(src=dest, scale=s, port=9000)
        self.threadpool.start(self.ng_worker)
        self.ng_browser.setUrl(QUrl(self.ng_worker.url()))
        self.ng_browser.setFocus()
        self.ng_layout_combobox.setCurrentText('xy')
        # self.hud('Displaying Alignment In Neuroglancer')
        self.set_idle()

    def is_neuroglancer_viewer(self) -> bool:
        if self.image_panel_stack_widget.currentIndex() == 1:
            return True
        else:
            return False

    def use_classic_viewer(self):
        self.image_panel_stack_widget.setCurrentIndex(0)
        self.read_project_data_update_gui()

    def is_classic_viewer(self) -> bool:
        if self.image_panel_stack_widget.currentIndex() == 0:  return True
        else:  return False


    def ng_set_layout_yz(self): self.ng_worker.set_layout_yz(); self.reload_ng()
    def ng_set_layout_xy(self): self.ng_worker.set_layout_xy(); self.reload_ng()
    def ng_set_layout_xz(self): self.ng_worker.set_layout_xz(); self.reload_ng()
    def ng_set_layout_xy_3d(self): self.ng_worker.set_layout_xy_3d(); self.reload_ng()
    def ng_set_layout_yz_3d(self): self.ng_worker.set_layout_yz_3d(); self.reload_ng()
    def ng_set_layout_xz_3d(self): self.ng_worker.set_layout_xz_3d(); self.reload_ng()
    def ng_set_layout_4panel(self): self.ng_worker.set_layout_4panel(); self.reload_ng()
    def ng_set_layout_3d(self): self.ng_worker.set_layout_3d(); self.reload_ng()



    def reload_remote(self):
        logger.info("Reloading Remote Neuroglancer Server")
        self.remote_view()

    def exit_ng(self):
        self.hud("Exiting Neuroglancer Viewer")
        # self.image_panel_stack_widget.setCurrentIndex(0)  #0906
        # new_cur_layer = int(cfg.viewer.state.voxel_coordinates[0])
        # cfg.data.set_layer(new_cur_layer)
        # self.jump_to(new_cur_layer)
        # self.read_project_data_update_gui() #0908+
        self.set_normal_view()

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


    def print_ng_state_url(self):
        try:
            self.ng_worker.show_state()
            # logger.info("Viewer.url : ", self.viewer.get_viewer_url)
            # logger.info("Viewer.screenshot : ", self.viewer.screenshot)
            # logger.info("Viewer.txn : ", self.viewer.txn)
            # logger.info("Viewer.actions : ", self.viewer.actions)
        except:
            print_exception()


    def print_ng_state(self):
        try:
            self.hud('\n\n%s' % str(cfg.viewer.state))
        except:
            pass


    def print_url_ng(self):
        try:
            self.ng_worker.show_url()
        except:
            pass


    def print_ng_raw_state(self):
        try:
            self.hud('\n\n%s' % str(cfg.viewer.config_state.raw_state))
        except:
            pass

    def browser_reload(self):
        try:
            self.ng_browser.reload()
        except:
            pass

    def dump_ng_details(self):
        if not are_images_imported():
            return
        v = cfg.viewer
        self.hud("v.position: %s\n" % str(v.state.position))
        self.hud("v.config_state: %s\n" % str(v.config_state))
        self.hud(self.ng_worker)


    def blend_ng(self):
        logger.info("blend_ng():")


    def show_splash(self):

        splash = SplashScreen(path='src/resources/alignem_animation.gif')
        splash.show()

        def showWindow():
            splash.close()
            # form.show()

        QTimer.singleShot(7500, showWindow)
        # form = MainWindow()


    def configure_project(self):
        logger.info('Showing configure project dialog...')
        recipe_maker = RecipeMaker(parent=self)
        result = recipe_maker.exec_()
        if not result:  logger.warning('Dialog Did Not Return A Result')


    def view_k_img(self):
        self.w = KImageWindow(parent=self)
        self.w.show()

    def reset_details_banner(self):
        # self.align_label_resolution.setText('Dimensions: n/a')
        # # self.align_label_affine.setText('Initialize Affine')
        # self.align_label_scales_remaining.setText('# Scales Unaligned: n/a')
        # self.align_label_is_skipped.setText('Is Skipped? n/a')
        # self.alignment_status_label.setText('Is Scale Aligned: n/a')


        # self.align_label_resolution.setText('Dimensions: n/a')
        # # self.align_label_affine.setText('Initialize Affine')
        # self.align_label_scales_remaining.setText('# Scales Unaligned: n/a')
        # self.align_label_is_skipped.setText('Is Skipped? n/a')
        # self.alignment_status_label.setText('Is Scale Aligned: n/a')
        pass

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
        self.hud("Keep Image: %s" % str(state))
        if are_images_imported():
            s,l = cfg.data.scale(), cfg.data.layer()
            cfg.data['data']['scales'][s]['alignment_stack'][l]['skipped'] = not state
            copy_skips_to_all_scales()
            cfg.data.link_all_stacks()
        self.update_alignment_details()

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
        self.hud('\n\nSNR List for Scale %d:\n%s\n' % (s, lst.split(' | ')))

    def show_zarr_info(self) -> None:
        import zarr
        z = zarr.open(os.path.join(cfg.data.dest(), 'img_aligned.zarr'))
        self.hud('\n\n' + str(z.tree()) + '\n' + str(z.info))

    def initShortcuts(self):
        '''Initialize Shortcuts'''
        logger.info('Initializing Shortcuts')
        events = (
            # (QKeySequence.Save, self.save_project),
            (QKeySequence.Quit, self.exit_app),
            (QKeySequence.MoveToNextChar, self.change_layer_up),
            (QKeySequence.MoveToPreviousChar, self.change_layer_down),
            (QKeySequence.MoveToNextLine, self.scale_down),
            (QKeySequence.MoveToPreviousLine, self.scale_up)
        )
        for event, action in events:
            QShortcut(event, self, action)


    def set_normal_view(self):
        # self.image_panel_widget.show()
        self.control_panel.show()
        # self.multi_img_viewer.show()
        self.image_panel_stack_widget.show()
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.main_widget.setCurrentIndex(0)
        self.python_console.show()
        self.snr_plot.show()
        self.clear_snr_plot()
        self.hud.show()
        # self.import_images_button.hide()

        # self.main_panel_bottom_widget.setCurrentIndex(0)
        self.set_idle()

    def expand_bottom_panel_callback(self):
        if not self.image_panel_stack_widget.isHidden():
            # self.multi_img_viewer.hide()
            self.dual_viewer_w_banner.hide()
            self.control_panel.hide()
            self.image_panel_stack_widget.hide()
            # self.bottom_display_area_widget.adjustSize()
            self.bottom_widget.adjustSize()
            self.expand_bottom_panel_button.setIcon(qta.icon("fa.caret-down", color='#f3f6fb'))

        elif self.image_panel_stack_widget.isHidden():
            # self.multi_img_viewer.show()
            self.dual_viewer_w_banner.show()
            self.control_panel.show()
            self.image_panel_stack_widget.show()
            self.expand_bottom_panel_button.setIcon(qta.icon("fa.caret-up", color='#f3f6fb'))

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress:
            print(event.key())
        return super(MainWindow, self).eventFilter(source, event)

    def set_opacity(self, obj, val):
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(val)  # 0 to 1 will cause the fade effect to kick in
        obj.setGraphicsEffect(op)
        obj.setAutoFillBackground(True)

    def initMenu(self):
        '''Initialize Menu'''
        logger.info('Initializing Menu')
        self.action_groups = {}
        self.menu = self.menuBar()
        # self.menu.setFixedHeight(20)
        self.menu.setCursor(QCursor(Qt.PointingHandCursor))
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

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
                 # ['Classic Viewer', 'None', self.use_classic_viewer, None, None, None],
                 # ['Neuroglancer Viewer', 'None', self.use_neuroglancer_viewer, None, None, None],
                 ['Reload Neuroglancer', 'None', self.reload_ng, None, None, None],
                 ['Neuroglancer Layout',
                  [
                      ['xy', None, self.ng_set_layout_xy, None, None, None],
                      ['xz', None, self.ng_set_layout_xz, None, None, None],
                      ['yz', None, self.ng_set_layout_yz, None, None, None],
                      ['yz-3d', None, self.ng_set_layout_yz_3d, None, None, None],
                      ['xy-3d', None, self.ng_set_layout_xy_3d, None, None, None],
                      ['xz-3d', None, self.ng_set_layout_xz_3d, None, None, None],
                      # ['3d', None, self.ng_set_layout_3d, None, None, None],
                      ['4panel', None, self.ng_set_layout_4panel, None, None, None],
                  ]
                  ],
                 # ['Normalize View', 'None', self.set_normal_view, None, None, None],
                 ['Project JSON', 'Ctrl+J', self.project_view_callback, None, None, None],
                 ['Python Console', None, self.show_hide_python, None, None, None],
                 ['SNR Plot', None, self.update_snr_plot, None, None, None],
                 ['Splash Screen', None, self.show_splash, None, None, None],
                 ['Theme',
                  [
                      ['Default Theme', None, self.apply_default_style, None, None, None],
                      ['Daylight Theme', None, self.apply_daylight_style, None, None, None],
                      ['Moonlit Theme', None, self.apply_moonlit_style, None, None, None],
                      ['Sagittarius Theme', None, self.apply_sagittarius_style, None, None, None],
                  ]
                  ],
             ]
             ],

            ['&Tools',
             [
                 ['Project Configuration', None, self.configure_project, None, None, None],
                 ['Regenerate Zarr Scales', None, generate_zarr_scales, None, None, None],
                 ['Go To Next Worst SNR', None, self.jump_to_worst_snr, None, None, None],
                 ['Go To Next Best SNR', None, self.jump_to_best_snr, None, None, None],
                 ['Toggle Autogenerate Callback', None, self.toggle_auto_generate_callback, True, None, None],
                 # ['Apply Project Defaults', None, cfg.data.set_defaults, None, None, None],
                 ['Show &K Image', 'Ctrl+K', self.view_k_img, None, None, None],
                 ['&Write Multipage Tifs', 'None', self.write_paged_tiffs, None, None, None],
                 ['&Match Point Align Mode',
                  [
                      ['Toggle &Match Point Mode', 'Ctrl+M', self.toggle_match_point_align, None, False, True],
                      ['Clear Match Points', 'None', self.clear_match_points, None, None, None],
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
                 # ['&Align', 'Ctrl+A', self.align(lambda : cfg.data.scale()), None, None, None],
                 ['&Regenerate', None, self.regenerate, None, None, None],
                 ['Generate Scales', None, self.scale, None, None, None],
                 # ['Generate Zarr Scales', None, generate_zarr_scales, None, None, None],
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
                 ['Neuroglancer',
                   [
                      ['Reload State', None, self.reload_ng, None, None, None],
                      ['Reload Server', None, self.use_neuroglancer_viewer, None, None, None],
                      ['Show Neuroglancer URL', None, self.print_url_ng, None, None, None],
                      ['Show Neuroglancer State URL', None, self.print_ng_state_url, None, None, None],
                      ['Show Neuroglancer State', None, self.print_ng_state, None, None, None],
                      ['Show Neuroglancer Raw State', None, self.print_ng_raw_state, None, None, None],
                      ['Dump Neuroglancer Details', None, self.dump_ng_details, None, None, None],
                    ]
                  ],
                 ['Browser',
                  [
                      ['Reload', None, self.browser_reload, None, None, None],
                  ]
                  ],
                 ['Show Zarr Info', None, self.show_zarr_info, None, None, None],
                 ['Show Environment', None, self.show_run_path, None, None, None],
                 ['Show Module Search Path', None, self.show_module_search_path, None, None, None],
                 ['Print Sanity Check', None, print_sanity_check, None, None, None],
                 ['Print Project Tree', None, print_project_tree, None, None, None],
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



    def initUI(self):
        '''Initialize Main UI'''

        gb_margin = (8, 14, 8, 6)
        # cpanel_height = 115
        cpanel_height = 100
        cpanel_1_dims = (140, cpanel_height)
        cpanel_2_dims = (260, cpanel_height)
        cpanel_3_dims = (400, cpanel_height)
        cpanel_4_dims = (100, cpanel_height)
        cpanel_5_dims = (120, cpanel_height)

        # std_height = int(22)
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

        std_input_size = int(56)
        small_input_size = int(36)

        std_combobox_size = QSize(58, 20)




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
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.hud('Welcome To AlignEM-SWiFT.', logging.INFO)

        self.new_project_button = QPushButton(" New")
        self.new_project_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.new_project_button.clicked.connect(self.new_project)
        self.new_project_button.setFixedSize(slim_button_size)
        self.new_project_button.setIcon(qta.icon("fa.plus", color=ICON_COLOR))

        self.open_project_button = QPushButton(" Open")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_project_button.setFixedSize(slim_button_size)
        self.open_project_button.setIcon(qta.icon("fa.folder-open", color=ICON_COLOR))

        self.save_project_button = QPushButton(" Save")
        self.save_project_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setFixedSize(slim_button_size)
        self.save_project_button.setIcon(qta.icon("mdi.content-save", color=ICON_COLOR))

        self.exit_app_button = QPushButton(" Exit")
        self.exit_app_button.clicked.connect(self.exit_app)
        self.exit_app_button.setFixedSize(slim_button_size)
        self.exit_app_button.setIcon(qta.icon("fa.close", color=ICON_COLOR))

        self.documentation_button = QPushButton(" Help")
        self.documentation_button.clicked.connect(self.documentation_view)
        self.documentation_button.setFixedSize(slim_button_size)
        self.documentation_button.setIcon(qta.icon("mdi.help", color=ICON_COLOR))

        self.remote_viewer_button = QPushButton("NG Server")
        self.remote_viewer_button.clicked.connect(self.remote_view)
        self.remote_viewer_button.setFixedSize(slim_button_size)
        self.remote_viewer_button.setStyleSheet("font-size: 11px;")

        # self.import_images_button = QPushButton(" Import\n Images")
        # self.import_images_button.setToolTip('Import Images.')
        # self.import_images_button.clicked.connect(self.import_images)
        # self.import_images_button.setFixedSize(normal_button_size)
        # self.import_images_button.setIcon(qta.icon("fa5s.file-import", color=ICON_COLOR))
        # self.import_images_button.setStyleSheet("font-size: 11px;")
        # self.import_images_button.hide()

        # self.project_functions_layout = QGridLayout()
        # self.project_functions_layout.setContentsMargins(*gb_margin)
        # self.project_functions_layout.addWidget(self.new_project_button, 0, 0)
        # self.project_functions_layout.addWidget(self.open_project_button, 0, 1)
        # self.project_functions_layout.addWidget(self.save_project_button, 0, 2)
        # self.project_functions_layout.addWidget(self.exit_app_button, 1, 0)
        # self.project_functions_layout.addWidget(self.documentation_button, 1, 1)
        # self.project_functions_layout.addWidget(self.remote_viewer_button, 1, 2)

        self.project_functions_layout = QHBoxLayout()
        self.project_functions_layout.setContentsMargins(0, 0, 0, 0)
        # self.project_functions_layout.addWidget(self.import_images_button, alignment=Qt.AlignLeft)
        self.project_functions_layout.addWidget(self.new_project_button, alignment=Qt.AlignLeft)
        self.project_functions_layout.addWidget(self.open_project_button, alignment=Qt.AlignLeft)
        self.project_functions_layout.addWidget(self.save_project_button, alignment=Qt.AlignLeft)
        self.project_functions_layout.addWidget(self.remote_viewer_button, alignment=Qt.AlignLeft)
        self.project_functions_layout.addWidget(self.documentation_button, alignment=Qt.AlignLeft)
        self.project_functions_layout.addWidget(self.exit_app_button, alignment=Qt.AlignLeft)

        # self.spacer_item_project_funcs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.project_functions_layout.addStretch()

        '''GroupBox 2 Data Selection & Scaling'''



        # tip = 'Zoom to fit'
        # self.clear_zoom_button = QPushButton('Fit Screen')
        # self.clear_zoom_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.clear_zoom_button.setToolTip('Zoom to fit')
        # self.clear_zoom_button.clicked.connect(self.clear_zoom)
        # self.clear_zoom_button.setFixedSize(normal_button_width, std_height)
        # self.clear_zoom_button.setStyleSheet("font-size: 10px;")

        # tip = 'Actual-size all images.'
        # self.actual_size_button = QPushButton('Actual Size')
        # self.actual_size_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.actual_size_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # self.actual_size_button.clicked.connect(self.actual_size_callback)
        # self.actual_size_button.setFixedSize(normal_button_width, std_height)
        # self.actual_size_button.setStyleSheet("font-size: 10px;")

        # self.size_buttons_vlayout = QVBoxLayout()
        # self.size_buttons_vlayout.addWidget(self.clear_zoom_button)
        # self.size_buttons_vlayout.addWidget(self.actual_size_button)

        tip = 'Generate scale pyramid with chosen # of levels.'
        self.generate_scales_button = QPushButton('Generate\nScales')
        self.generate_scales_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.generate_scales_button.clicked.connect(self.scale)
        self.generate_scales_button.setFixedSize(normal_button_size)
        self.generate_scales_button.setStyleSheet("font-size: 10px;")
        self.generate_scales_button.setIcon(qta.icon("mdi.image-size-select-small", color=ICON_COLOR))

        tip = 'Reset (Use Everything)'
        self.clear_skips_button = QPushButton('Use All')
        self.clear_skips_button.setStyleSheet("font-size: 10px;")
        self.clear_skips_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clear_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_skips_button.clicked.connect(self.clear_skips)
        self.clear_skips_button.setFixedSize(small_button_size)
        # self.clear_skips_button_layout = QHBoxLayout()
        # self.clear_skips_button_layout.addWidget(self.clear_skips_button, alignment=Qt.AlignLeft)

        tip = 'Set Whether to Use or Reject the Current Layer'
        self.skip_label = QLabel("Toggle Image\nKeep/Reject:")
        self.skip_label.setStyleSheet("font-size: 11px;")
        self.skip_label.setToolTip(tip)

        self.toggle_skip = ToggleSwitch()
        self.toggle_skip.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_skip.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_skip.setChecked(True)  # 0816 #observed #sus #0907-
        self.toggle_skip.toggled.connect(self.skip_changed_callback)

        self.skip_layout = QHBoxLayout()
        self.skip_layout.addWidget(self.skip_label, alignment=Qt.AlignRight)
        self.skip_layout.addWidget(self.toggle_skip)
        self.skip_layout.addWidget(self.clear_skips_button)

        self.ng_layout_combobox = QComboBox()
        ng_layouts = ['','xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d']
        self.ng_layout_combobox.addItems(ng_layouts)
        self.ng_layout_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ng_layout_combobox.setFixedSize(QSize(76, std_height))
        self.ng_layout_combobox.currentTextChanged.connect(self.fn_ng_layout_combobox)

        tip = 'Jump to image #'
        self.jump_label = QLabel("Image:")
        self.jump_label.setToolTip(tip)
        self.jump_input = QLineEdit(self)
        self.jump_input.setFocusPolicy(Qt.ClickFocus)
        self.jump_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.jump_input.setFixedSize(std_input_size, std_height)
        self.jump_validator = QIntValidator()
        self.jump_input.setValidator(self.jump_validator)
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer())


        '''GroupBox 3 Alignment'''

        self.scales_combobox = QComboBox(self)
        # self.scales_combobox.hide()
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
        self.swim_label = QLabel("SWIM Window\n(% size):")
        self.swim_label.setStyleSheet("font-size: 11px;")

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

        tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        # self.apply_all_label = QLabel("Apply All:")
        self.apply_all_button = QPushButton("Apply To All")
        self.apply_all_button.setStyleSheet("font-size: 9px;")
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.apply_all_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.apply_all_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.apply_all_button.clicked.connect(self.apply_all)
        # self.apply_all_button.setFixedSize(std_height, std_height)
        self.apply_all_button.setFixedSize(slim_button_size)
        # self.apply_all_button.setIcon(qta.icon("mdi.transfer", color=ICON_COLOR))
        # self.apply_all_button.setIcon(qta.icon("fa.fast-forward", color=ICON_COLOR))

        tip = 'Go to next scale.'
        self.scale_up_button = QPushButton()
        self.scale_up_button.setStyleSheet("font-size: 9px;")
        self.scale_up_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scale_up_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.scale_up_button.clicked.connect(self.scale_up)
        self.scale_up_button.setFixedSize(std_height, std_height)
        self.scale_up_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.scale_up_button.setIcon(qta.icon("fa.arrow-up", color=ICON_COLOR))

        tip = 'Go to previous scale.'
        self.scale_down_button = QPushButton()
        # self.scale_down_button.setShortcut(QKeySequence=)
        self.scale_down_button.setStyleSheet("font-size: 11px;")
        self.scale_down_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scale_down_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.scale_down_button.clicked.connect(self.scale_down)
        self.scale_down_button.setFixedSize(std_height, std_height)
        self.scale_down_button.setIcon(qta.icon("fa.arrow-down", color=ICON_COLOR))

        tip = 'Go to next layer.'
        self.next_layer_button = QPushButton()
        self.next_layer_button.setStyleSheet("font-size: 11px;")
        self.next_layer_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_layer_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.next_layer_button.clicked.connect(self.change_layer_up)
        self.next_layer_button.setFixedSize(std_height, std_height)
        self.next_layer_button.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        tip = 'Go to previous layer.'
        self.prev_layer_button = QPushButton()
        self.prev_layer_button.setStyleSheet("font-size: 11px;")
        self.prev_layer_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_layer_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.prev_layer_button.clicked.connect(self.change_layer_down)
        self.prev_layer_button.setFixedSize(std_height, std_height)
        self.prev_layer_button.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        self.layer_select_label = QLabel('Layer:')
        self.layer_layout = QHBoxLayout()
        self.layer_layout.setAlignment(Qt.AlignLeft)
        self.layer_layout.setContentsMargins(0, 0, 0, 0)
        self.layer_layout.addWidget(self.prev_layer_button)
        self.layer_layout.addWidget(self.next_layer_button)

        self.scale_select_label = QLabel('Scale:')
        self.scale_layout = QVBoxLayout()
        self.scale_layout.setAlignment(Qt.AlignLeft)
        self.scale_layout.setContentsMargins(0, 0, 0, 0)
        self.scale_layout.addWidget(self.scale_up_button)
        self.scale_layout.addWidget(self.scale_down_button)

        # self.scale_selection_label = QLabel()
        # self.scale_selection_label.setText("Scale ↕ Layer ↔")
        # self.scale_layer_ctrls_layout = QGridLayout()
        # self.scale_layer_ctrls_layout.addWidget(self.scale_down_button, 1, 1)
        # self.scale_layer_ctrls_layout.addWidget(self.scale_up_button, 0, 1)
        # self.scale_layer_ctrls_layout.addWidget(self.next_layer_button, 1, 2)
        # self.scale_layer_ctrls_layout.addWidget(self.prev_layer_button, 1, 0)
        #
        # self.scale_layer_ctrls_outer_layout = QHBoxLayout()
        # self.scale_layer_ctrls_outer_layout.addWidget(self.scale_selection_label)
        # self.scale_layer_ctrls_outer_layout.addLayout(self.scale_layer_ctrls_layout)


        tip = 'Align This Scale'
        self.align_all_button = QPushButton('Align This\nScale')
        self.align_all_button.setStyleSheet("font-size: 11px;")
        self.align_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_all_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.align_all_button.clicked.connect(lambda: self.align(use_scale=cfg.data.scale()))
        self.align_all_button.setFixedSize(normal_button_size)
        # self.align_all_button.setIcon(qta.icon("fa.play", color=ICON_COLOR))


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
              ' option is set at the coarsest scale, in order to form a contiguous dataset.'
        self.null_bias_label = QLabel("Corrective\n(Poly) Bias:")
        self.null_bias_label.setStyleSheet("font-size: 11px;")
        self.null_bias_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.null_bias_combobox = QComboBox(self)
        self.null_bias_combobox.setStyleSheet("font-size: 11px;")
        self.null_bias_combobox.currentIndexChanged.connect(self.has_unsaved_changes)
        self.null_bias_combobox.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.null_bias_combobox.addItems(['None', '0', '1', '2', '3', '4'])
        self.null_bias_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.null_bias_combobox.setFixedSize(std_combobox_size)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.poly_order_hlayout.addWidget(self.null_bias_combobox, alignment=Qt.AlignmentFlag.AlignLeft)

        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that ' \
              'are the same size as the source images but may have missing data, while turning this ON will ' \
              'result in no missing data but may significantly increase the size of the generated images.'
        self.bounding_label = QLabel("Bounding\nRectangle:")
        self.bounding_label.setStyleSheet("font-size: 11px;")
        self.bounding_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.toggle_bounding_rect.toggled.connect(self.bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.setContentsMargins(0, 0, 0, 0)
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignLeft)

        tip = "Recomputes the cumulative affine and generates new aligned images" \
              "based on the current Null Bias and Bounding Rectangle presets."
        # self.regenerate_label = QLabel('Re-generate\nAligned Images')
        # self.regenerate_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.regenerate_button = QPushButton('Reapply\nCum. Affine')
        self.regenerate_button.setStyleSheet("font-size: 10px;")
        # self.regenerate_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.regenerate_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # self.regenerate_button.setIcon(qta.icon("fa.recycle", color=ICON_COLOR))
        # self.regenerate_button.setIcon(qta.icon("mdi.image-multiple", color=ICON_COLOR))
        self.regenerate_button.clicked.connect(lambda: self.regenerate(use_scale=cfg.data.scale()))
        # self.regenerate_button.setFixedSize(std_height, std_height)
        self.regenerate_button.setFixedSize(normal_button_size)

        # self.post_alignment_layout = QHBoxLayout()
        # self.post_alignment_layout.setContentsMargins(0, 0, 0, 0)
        # # self.post_alignment_layout.addStretch()
        # self.post_alignment_layout.addLayout(self.poly_order_hlayout)
        # self.post_alignment_layout.addLayout(self.toggle_bounding_hlayout)
        # self.post_alignment_layout.addWidget(self.regenerate_button)
        # self.post_alignment_layout.addLayout(self.regenerate_hlayout)

        # self.post_alignment_widget = QWidget()
        # self.post_alignment_widget.setLayout(self.post_alignment_layout)

        self.alignment_layout = QHBoxLayout()
        # self.alignment_layout.setSpacing(8)
        self.alignment_layout.setContentsMargins(0, 0, 0, 0)
        self.alignment_layout.addLayout(self.skip_layout)
        self.alignment_layout.addLayout(self.swim_grid)
        self.alignment_layout.addLayout(self.whitening_grid)
        self.alignment_layout.addWidget(self.apply_all_button)
        # self.alignment_layout.addWidget(self.scale_selection_label, 0, 5, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.alignment_layout.addLayout(self.scale_layer_ctrls_outer_layout, 1, 5, 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        # self.alignment_layout.addWidget(self.layer_select_label, 1, 5, alignment=Qt.AlignmentFlag.AlignCenter)
        self.alignment_layout.addWidget(self.layer_select_label)
        self.alignment_layout.addLayout(self.layer_layout)
        self.alignment_layout.addWidget(self.scale_select_label)
        self.alignment_layout.addLayout(self.scale_layout)
        # self.alignment_layout.addWidget(self.clear_skips_button, 1, 0)
        # self.alignment_layout.addWidget(self.post_alignment_widget)
        self.alignment_layout.addLayout(self.poly_order_hlayout)
        self.alignment_layout.addLayout(self.toggle_bounding_hlayout)
        self.alignment_layout.addWidget(self.regenerate_button)
        self.alignment_layout.addWidget(self.align_all_button)
        self.alignment_layout.addStretch()

        self.alignment_widget = QWidget()
        self.alignment_widget.setLayout(self.alignment_layout)

        '''GroupBox 4 Export & View'''
        #
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
        # tip = "This function creates a scale pyramid from the full scale aligned images and then converts them " \
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
        # self.ng_button.clicked.connect(self.use_neuroglancer_viewer)
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

        # '''Project GroupBox'''
        # # self.project_functions_groupbox = QGroupBox("Project")
        # self.project_functions_groupbox = QGroupBox()
        # self.project_functions_groupbox_ = QGroupBox("Project")
        # self.project_functions_groupbox.setLayout(self.project_functions_layout)
        # self.project_functions_stack = QStackedWidget()
        # self.project_functions_stack.setObjectName('project_functions_stack')
        # self.project_functions_stack.setMinimumSize(*cpanel_1_dims)
        # self.project_functions_stack.addWidget(self.project_functions_groupbox_)
        # self.project_functions_stack.addWidget(self.project_functions_groupbox)
        # self.project_functions_stack.setCurrentIndex(1)

        # '''Alignment GroupBox'''
        # self.alignment_groupbox = QGroupBox("Alignment")
        # self.alignment_groupbox_ = QGroupBox("Alignment")
        # self.alignment_groupbox.setTitle('Alignment')
        # self.alignment_groupbox_.setTitle('Alignment')
        # self.alignment_groupbox.setLayout(self.alignment_layout)
        # self.alignment_stack = QStackedWidget()
        # self.alignment_stack.setObjectName('alignment_stack')
        # self.alignment_stack.setMinimumSize(*cpanel_3_dims)
        # self.alignment_stack.addWidget(self.alignment_groupbox_)
        # self.alignment_stack.addWidget(self.alignment_groupbox)
        # self.alignment_stack.setCurrentIndex(1)

        # '''Post-Alignment GroupBox'''
        # self.postalignment_groupbox = QGroupBox("Adjust Output")
        # self.postalignment_groupbox_ = QGroupBox("Adjust Output")
        # self.postalignment_groupbox.setLayout(self.post_alignment_layout)
        # self.postalignment_stack = QStackedWidget()
        # self.postalignment_stack.setObjectName('postalignment_stack')
        # self.postalignment_stack.setMinimumSize(*cpanel_4_dims)
        # self.postalignment_stack.addWidget(self.postalignment_groupbox_)
        # self.postalignment_stack.addWidget(self.postalignment_groupbox)
        # self.postalignment_stack.setCurrentIndex(1)

        # '''Export & View GroupBox'''
        # self.export_and_view_groupbox = QGroupBox("Neuroglancer")
        # self.export_and_view_groupbox_ = QGroupBox("Neuroglancer")
        # self.export_and_view_groupbox.setLayout(self.export_settings_layout)
        # self.export_and_view_stack = QStackedWidget()
        # self.export_and_view_stack.setObjectName('export_and_view_stack')
        # self.export_and_view_stack.setMinimumSize(*cpanel_5_dims)
        # self.export_and_view_stack.addWidget(self.export_and_view_groupbox_)
        # self.export_and_view_stack.addWidget(self.export_and_view_groupbox)
        # self.export_and_view_stack.setCurrentIndex(1)

        # self.lwr_groups_layout = QGridLayout()
        # self.lwr_groups_layout.setContentsMargins(6,3,6,3) # This is the margin around the group boxes
        # # self.lwr_groups_layout.addWidget(self.project_functions_stack, 1, 0)
        # self.lwr_groups_layout.addWidget(self.alignment_stack, 1, 1)
        # self.lwr_groups_layout.addWidget(self.postalignment_stack, 1, 2)
        # self.lwr_groups_layout.addWidget(self.export_and_view_stack, 1, 3)
        # self.export_and_view_stack.hide()
        # self.lwr_groups_layout.setHorizontalSpacing(16)

        self.control_panel_inner_layout = QHBoxLayout()
        self.alignment_widget.hide()

        self.control_panel_inner_layout.addWidget(self.alignment_widget)
        # self.control_panel_inner_layout.addWidget(self.post_alignment_widget)
        # self.control_panel_inner_layout.addWidget(self.align_all_button)

        self.control_panel_outter_layout = QVBoxLayout()
        self.control_panel_outter_layout.setContentsMargins(8, 4, 8, 4)
        self.title_label = QLabel('AlignEM-SWiFT')
        self.title_label.setStyleSheet("font-size: 24px; color: #004060;")
        self.subtitle_label = QLabel('for Aligning Electron Micrographs using Signal Whitening Fourier Transforms')
        self.subtitle_label.setStyleSheet("font-size: 14px; color: #004060;")
        self.control_panel_outter_layout.addWidget(self.title_label)
        self.control_panel_outter_layout.addWidget(self.subtitle_label)
        self.control_panel_outter_layout.addLayout(self.project_functions_layout)
        self.control_panel_outter_layout.addLayout(self.control_panel_inner_layout)

        self.control_panel = QWidget()
        self.control_panel.setContentsMargins(4, 0, 4, 12)

        # self.control_panel.setFixedHeight(cpanel_height + 10)
        self.control_panel.setLayout(self.control_panel_outter_layout)

        # self.alignment_stack.setStyleSheet('''border: 1px dotted #171d22;''')
        # self.postalignment_stack.setStyleSheet('''border: 1px dotted #171d22;''')
        # self.export_and_view_stack.setStyleSheet('''border: 1px dotted #171d22;''')

        '''Top Details/Labels Banner'''
        self.align_label_resolution = QLabel('')
        # self.align_label_affine = QLabel('Initialize Affine')
        self.align_label_scales_remaining = QLabel('')
        # self.align_label_is_skipped = QLabel('')
        self.alignment_status_label = QLabel('')
        self.alignment_snr_label = QLabel('')
        self.reset_details_banner()

        tip = 'Show Neuroglancer key bindings.'
        self.info_button = QLabel('')
        self.info_button = QPushButton()
        self.info_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.info_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.info_button.clicked.connect(self.documentation_view)
        self.info_button.setFixedSize(std_height, std_height)
        self.info_button.setIcon(qta.icon("fa.info", color='#f3f6fb'))

        # self.al_status_checkbox = QRadioButton()
        # self.al_status_checkbox = QCheckBox()
        # self.al_status_checkbox.setStyleSheet("QCheckBox::indicator {border: 1px solid; border-color: #ffe135;}"
        #                                       "QCheckBox::indicator:checked {background-color: #ffe135;}")
        # self.al_status_checkbox.setEnabled(False)
        # self.al_status_checkbox.setToolTip('Alignment statusBar')
        self.details_banner = QWidget()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(5)
        shadow.setOffset(2)
        self.details_banner.setGraphicsEffect(shadow)
        self.details_banner.setContentsMargins(0, 0, 0, 0)
        self.details_banner.setFixedHeight(35)
        # banner_stylesheet = """color: #ffe135; background-color: #000000; font-size: 14px;"""
        self.details_banner_layout = QHBoxLayout()
        self.details_banner_layout.addWidget(self.align_label_resolution)
        self.details_banner_layout.addStretch(1)
        # self.details_banner_layout.addWidget(self.align_label_affine)
        self.details_banner_layout.addWidget(self.alignment_status_label)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.align_label_scales_remaining)
        self.details_banner_layout.addStretch(1)
        self.details_banner_layout.addWidget(self.alignment_snr_label)
        # self.details_banner_layout.addWidget(self.align_label_cur_scale)
        # self.details_banner_layout.addWidget(self.align_label_is_skipped)
        self.details_banner_layout.addStretch(7)
        self.details_banner_layout.addWidget(QLabel('View: '), alignment=Qt.AlignVCenter)
        self.details_banner_layout.addWidget(self.ng_layout_combobox)
        self.details_banner_layout.addWidget(QLabel('Image #: '), alignment=Qt.AlignVCenter)
        self.details_banner_layout.addWidget(self.jump_input)
        self.details_banner_layout.addWidget(QLabel('Scale: '), alignment=Qt.AlignVCenter)
        self.details_banner_layout.addWidget(self.scales_combobox)
        self.details_banner_layout.addWidget(self.info_button)
        self.details_banner.setLayout(self.details_banner_layout)

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
        self.print_state_ng_button.clicked.connect(self.print_ng_state_url)
        self.print_url_ng_button = QPushButton("Print URL")
        self.print_url_ng_button.setFixedSize(std_button_size)
        self.print_url_ng_button.clicked.connect(self.print_url_ng)

        self.browser = QWebEngineView()
        # self.browser_al = QWebEngineView()
        # self.browser_unal = QWebEngineView()
        self.ng_browser = QWebEngineView()
        # self.ng_browser.setFocusPolicy(Qt.StrongFocus)

        self.ng_panel = QWidget()
        self.ng_panel_layout = QVBoxLayout()

        self.ng_multipanel_layout = QHBoxLayout()
        self.ng_multipanel_layout.addWidget(self.ng_browser)

        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)

        self.ng_panel_layout.addLayout(self.ng_multipanel_layout)
        # self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)
        self.ng_panel.setLayout(self.ng_panel_layout)

        '''SNR Plot & Controls'''

        self.snr_plot = SnrPlot()
        # self.snr_lineplot = pg.plot()
        l = pg.GraphicsLayout()
        l.layout.setContentsMargins(0, 0, 0, 0)
        # self.snr_plot_container = QWidget()
        # self.snr_plot_layout = QGridLayout()
        # self.snr_plot_layout.addWidget(self.snr_plot, 0, 0)
        # self.snr_plot_label = QLabel('Test Label Test Label')
        # self.snr_plot_label.setParent(self.snr_plot)
        # self.snr_plot_label.setStyleSheet('background-color: #ffffff; color: #ffe135;')
        # self.snr_plot_layout.addWidget(self.snr_plot_label, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)


        # self.snr_plot_h_scroll = QScrollBar(Qt.Horizontal)
        # self.snr_plot_layout.addWidget(self.snr_plot_h_scroll)
        # self.snr_plot_container.setLayout(self.snr_plot_layout)

        self.plot_widget_update_button = QPushButton('Update')
        # self.plot_widget_update_button.setParent(self.snr_plot)
        self.plot_widget_update_button.setStyleSheet("font-size: 8px;")
        self.plot_widget_update_button.setStyleSheet(lower_controls_style)
        self.plot_widget_update_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_widget_update_button.clicked.connect(self.update_snr_plot)
        self.plot_widget_update_button.setFixedSize(QSize(48,18))

        self.plot_widget_clear_button = QPushButton('Clear')
        # self.plot_widget_clear_button.setParent(self.snr_plot)
        self.plot_widget_clear_button.setStyleSheet("font-size: 8px; font-weight: bold;")
        self.plot_widget_clear_button.setStyleSheet(lower_controls_style)
        self.plot_widget_clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_widget_clear_button.clicked.connect(self.clear_snr_plot)
        self.plot_widget_clear_button.setFixedSize(QSize(48,18))

        self.plot_controls_layout = QHBoxLayout()
        self.plot_controls_layout.setAlignment(Qt.AlignBottom)
        self.plot_controls_layout.setContentsMargins(0, 0, 0, 0)
        # self.plot_controls_layout.addWidget(self.plot_widget_update_button, alignment=Qt.AlignLeft)
        # self.plot_controls_layout.addWidget(self.plot_widget_clear_button, alignment=Qt.AlignLeft)
        # self.plot_controls_layout.addWidget(self.plot_widget_update_button, alignment=Qt.AlignBottom)
        # self.plot_controls_layout.addWidget(self.plot_widget_clear_button, alignment=Qt.AlignBottom)
        self.plot_controls_layout.addWidget(self.plot_widget_update_button)
        self.plot_controls_layout.addWidget(self.plot_widget_clear_button)
        self.plot_controls_layout.addStretch()
        # self.plot_controls_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.snr_plot_and_control = QWidget()
        self.snr_plot_and_control_layout = QVBoxLayout()
        self.snr_plot_and_control_layout.addWidget(self.snr_plot)
        self.snr_plot_and_control_layout.addLayout(self.plot_controls_layout)
        self.snr_plot_and_control.setLayout(self.snr_plot_and_control_layout)

        # self.plot_widget_layout = QVBoxLayout()
        # self.plot_widget_layout.setContentsMargins(0, 0, 0, 0)
        # self.plot_widget_layout.addWidget(self.snr_plot)
        # self.plot_widget_layout.addLayout(self.plot_controls_layout)
        # self.snr_plot_widget = QWidget()
        # self.snr_plot_widget.setLayout(self.plot_widget_layout)

        '''Python Console & Controls'''
        # self.python_console_back_button = QPushButton('Back')
        # self.python_console_back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.python_console_back_button.clicked.connect(self.back_callback)
        # self.python_console_back_button.setFixedSize(normal_button_size)
        # self.python_console_back_button.setAutoDefault(True)
        # self.python_console_layout = QHBoxLayout()
        # self.python_console_layout.addWidget(self.python_console)
        # self.python_console_widget_container = QWidget()
        # self.python_console_widget_container.setStyleSheet('background-color: #000000;')

        # self.python_console_widget_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) #0917
        # self.python_console_widget_container.setLayout(self.python_console_layout)

        self.bottom_panel_splitter = QSplitter()
        self.bottom_panel_splitter.setAutoFillBackground(True)

        self.bottom_panel_splitter.setContentsMargins(0, 0, 0, 0)
        self.bottom_panel_splitter.setHandleWidth(8)
        self.bottom_panel_splitter.addWidget(self.hud)
        # self.bottom_panel_splitter.addWidget(self.python_console_widget_container)
        self.bottom_panel_splitter.addWidget(self.python_console)
        # self.bottom_panel_splitter.addWidget(self.snr_plot_widget)
        # self.bottom_panel_splitter.addWidget(self.snr_plot)
        self.bottom_panel_splitter.addWidget(self.snr_plot_and_control)

        self.bottom_panel_splitter.setStretchFactor(0, 4)
        self.bottom_panel_splitter.setStretchFactor(1, 2)
        self.bottom_panel_splitter.setStretchFactor(2, 2)
        self.bottom_panel_splitter.setCollapsible(0, True)
        self.bottom_panel_splitter.setCollapsible(1, True)
        self.bottom_panel_splitter.setCollapsible(2, True)

        # self.main_panel_bottom_widget = QStackedWidget()
        # self.main_panel_bottom_widget.setContentsMargins(0, 0, 0, 0)
        # self.main_panel_bottom_widget.addWidget(self.hud)
        # self.main_panel_bottom_widget.addWidget(self.snr_plot_widget)
        # self.main_panel_bottom_widget.addWidget(self.python_console_widget_container)
        # self.main_panel_bottom_widget.setCurrentIndex(0)

        self.hud.setContentsMargins(0, 0, 0, 0) #0823
        # self.snr_plot_widget.setContentsMargins(0, 0, 0, 0) #0823
        # self.python_console_widget_container.setContentsMargins(0, 0, 0, 0) #0823

        # "color: rgb(0,0,0);" \
            # self.python_console.setStyleSheet('background-color: #35637c; color: #f3f6fb;')
        self.python_console.setStyleSheet('background-color: #004060; border-width: 0px; color: #f3f6fb;')

        # "background-color: rgb(255,255,255);" \
        # "background-color: rgb(255,255,255);" \
        '''Lower Right Tool Selection Buttons'''
        tip = 'Expand Bottom Panel'
        self.expand_bottom_panel_button = QPushButton()
        self.expand_bottom_panel_button.setStyleSheet(lower_controls_style)
        self.expand_bottom_panel_button.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.expand_bottom_panel_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.expand_bottom_panel_button.clicked.connect(self.expand_bottom_panel_callback)
        # self.expand_bottom_panel_button.setFixedSize(30,15)
        self.expand_bottom_panel_button.setFixedSize(normal_button_width,15)
        self.expand_bottom_panel_button.setIcon(qta.icon("fa.caret-up", color='#f3f6fb'))

        self.show_hide_hud_button = QPushButton("Head-up\nDisplay")
        self.show_hide_hud_button.setStyleSheet(lower_controls_style)
        # self.show_hide_hud_button.setStyleSheet("font-size: 10px;")
        self.show_hide_hud_button.setStyleSheet(lower_controls_style)
        self.show_hide_hud_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_hud_button.clicked.connect(self.show_hide_hud)
        self.show_hide_hud_button.setFixedSize(normal_button_size)
        self.show_hide_hud_button.setIcon(qta.icon("mdi.monitor", color='#f3f6fb'))

        self.show_hide_python_button = QPushButton("Python\nConsole")
        self.show_hide_python_button.setStyleSheet(lower_controls_style)
        # self.show_hide_python_button.setStyleSheet("font-size: 10px;")
        self.show_hide_python_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_python_button.clicked.connect(self.show_hide_python)
        self.show_hide_python_button.setFixedSize(normal_button_size)
        self.show_hide_python_button.setIcon(qta.icon("fa.terminal", color='#f3f6fb'))

        self.show_hide_snr = QPushButton(" SNR\n Plot")
        self.show_hide_snr.setStyleSheet(lower_controls_style)
        # self.show_hide_snr.setStyleSheet("font-size: 10px;")
        # self.show_hide_snr.setStyleSheet("color: #f3f6fb; font-size: 10px;")
        self.show_hide_snr.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hide_snr.clicked.connect(self.show_hide_snr_plot)
        self.show_hide_snr.setFixedSize(normal_button_size)
        self.show_hide_snr.setIcon(qta.icon("mdi.scatter-plot", color='#f3f6fb'))

        self.project_view_button = QPushButton('View\nJSON')
        self.project_view_button.setStyleSheet(lower_controls_style)
        self.project_view_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.project_view_button.setToolTip('Inspect the data dictionary in memory.')
        self.project_view_button.clicked.connect(self.project_view_callback)
        # self.project_view_button.clicked.connect(self.show_hide_json)
        self.project_view_button.setFixedSize(normal_button_size)
        # self.project_view_button.setStyleSheet("font-size: 10px;")
        self.project_view_button.setIcon(qta.icon("mdi.json", color='#f3f6fb'))

        self.main_lwr_vlayout = QVBoxLayout()
        self.main_lwr_vlayout.setContentsMargins(2, 2, 2, 0)
        self.main_lwr_vlayout.addWidget(self.expand_bottom_panel_button, alignment=Qt.AlignRight)
        self.main_lwr_vlayout.addWidget(self.show_hide_hud_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_lwr_vlayout.addWidget(self.show_hide_python_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_lwr_vlayout.addWidget(self.show_hide_snr, alignment=Qt.AlignmentFlag.AlignTop)
        # self.main_lwr_vlayout.addWidget(self.plot_widget_clear_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_lwr_vlayout.addWidget(self.project_view_button, alignment=Qt.AlignmentFlag.AlignTop)
        # self.main_lwr_vlayout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.main_lwr_vlayout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))


        self.bottom_display_area_hlayout = QHBoxLayout()
        self.bottom_display_area_hlayout.setContentsMargins(0, 0, 0, 0)
        self.bottom_display_area_hlayout.addWidget(self.bottom_panel_splitter)
        self.bottom_display_area_hlayout.addLayout(self.main_lwr_vlayout)
        self.bottom_display_area_hlayout.setSpacing(2)
        self.bottom_widget = QWidget()
        self.bottom_widget.setLayout(self.bottom_display_area_hlayout)
        # self.bottom_display_area_hlayout.addWidget(self.bottom_display_area_controls)
        # self.bottom_display_area_widget = QWidget()
        # self.bottom_display_area_widget.setLayout(self.bottom_display_area_hlayout)
        # self.bottom_display_area_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        '''Image Panels'''
        # self.img_panels = {}
        # # self.img_panels['ref'] = QtImageStackViewer(role='ref')
        # # self.img_panels['base'] = QtImageStackViewer(role='base')
        # self.img_panels['aligned'] = QtImageStackViewer(role='aligned', parent=self)
        # self.img_panels['ref'] = QtImageViewer(role='ref', parent=self)
        # self.img_panels['base'] = QtImageViewer(role='base', parent=self)
        # self.img_panels['aligned'] = QtImageViewer(role='aligned')
        self.image_view_hlayout = QHBoxLayout()
        # self.image_view_hlayout.addWidget(self.img_panels['ref'])
        # self.image_view_hlayout.addWidget(self.img_panels['base'])
        # self.image_view_hlayout.addWidget(self.img_panels['aligned'])
        self.image_view_hlayout.setSpacing(0)
        self.multi_img_viewer = QWidget()
        self.multi_img_viewer.setMinimumHeight(300)
        self.multi_img_viewer.setContentsMargins(0,0,0,0)
        self.multi_img_viewer.setLayout(self.image_view_hlayout)
        # self.main_splitter.addWidget(self.multi_img_viewer)


        # self.splash_animation = SplashScreen(path='src/resources/alignem_animation.gif')
        # self.splash_animation.show()
        # self.gif_label = QLabel()
        # self.gif_label.setGeometry(QRect(25, 25, 200, 200))
        # self.gif_label.setMinimumSize(QSize(200, 200))
        # self.gif_label.setMaximumSize(QSize(200, 200))
        # self.gif_label.setObjectName("alignem_guy")
        # self.movie = QMovie("src/resource/alignem_animation.gif")
        # self.gif_label.setMovie(self.movie)
        # self.movie.start()


        '''Multi-image Panel & Banner Widget'''
        # self.image_panel = MultiImagePanel()
        # self.image_panel.setFocusPolicy(Qt.StrongFocus)
        # self.image_panel.setFocus()
        # self.image_panel.setMinimumHeight(image_panel_min_height)

        # self.image_panel_vlayout = QVBoxLayout()
        # self.image_panel_vlayout.setSpacing(0)
        # self.image_panel_vlayout.addWidget(self.multi_img_viewer)
        # self.image_panel_widget = QWidget() #This is the cause of glitch
        # self.image_panel_widget.setLayout(self.image_panel_vlayout)
        # self.image_panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        '''Image Panel Stack Widget'''
        self.image_panel_stack_widget = QStackedWidget()
        # self.image_panel_stack_widget.setStyleSheet('background-color: #000000;') #can be used to frame viewer
        self.image_panel_landing_page = QWidget()
        self.image_panel_stack_widget.addWidget(self.multi_img_viewer)
        self.image_panel_stack_widget.addWidget(self.ng_panel)
        self.image_panel_stack_widget.addWidget(self.image_panel_landing_page)

        self.dual_viewer_w_banner = QWidget()
        self.dual_viewer_w_banner_layout = QVBoxLayout()
        self.dual_viewer_w_banner.setLayout(self.dual_viewer_w_banner_layout)
        self.dual_viewer_w_banner_layout.addWidget(self.details_banner)
        self.dual_viewer_w_banner_layout.addWidget(self.image_panel_stack_widget)

        '''Main Splitter'''
        # main_window.main_splitter.sizes() # Out[20]: [400, 216, 160]
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        # self.main_splitter.splitterMoved.connect(self.clear_zoom)
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.setContentsMargins(0, 0, 0, 0)
        self.main_splitter.addWidget(self.dual_viewer_w_banner)
        self.main_splitter.addWidget(self.control_panel)
        # self.main_splitter.addWidget(self.bottom_display_area_widget)
        # self.main_splitter.addWidget(self.bottom_display_area_controls)
        self.main_splitter.addWidget(self.bottom_widget)
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 2)
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, True)
        self.main_splitter.setCollapsible(2, True)

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
        self.treeview_widget = QWidget()
        self.treeview_layout = QVBoxLayout()
        self.treeview_layout.addWidget(self.project_view)
        self.treeview_ctl_layout = QHBoxLayout()
        self.treeview_ctl_layout.addWidget(self.exit_project_view_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.treeview_ctl_layout.addWidget(self.refresh_project_view_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.treeview_ctl_layout.addWidget(self.save_project_project_view_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.treeview_ctl_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.treeview_layout.addLayout(self.treeview_ctl_layout)
        self.treeview_widget.setLayout(self.treeview_layout)

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
        self.main_panel_layout.setSpacing(0) #0918+
        self.main_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.main_panel_layout.addWidget(self.main_splitter, 1, 0)

        self.main_widget = QStackedWidget(self)
        self.main_widget.addWidget(self.main_panel)                 # (0) main_panel
        # self.main_widget.addWidget(self.ng_panel)                 # (x) ng_panel
        self.main_widget.addWidget(self.docs_panel)                 # (1) docs_panel
        self.main_widget.addWidget(self.demos_panel)                # (2) demos_panel
        self.main_widget.addWidget(self.remote_viewer_panel)        # (3) remote_viewer_panel
        self.main_widget.addWidget(self.treeview_widget)         # (4) self.project_view
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

        self.bottom_widget.setAutoFillBackground(True)
        self.bottom_widget.setStyleSheet('''background-color: #000000;''')
        # self.bottom_display_area_controls.setAutoFillBackground(True)
        # self.bottom_display_area_controls.setStyleSheet('''background-color: #000000;''')

        # self.multi_img_viewer.setStyleSheet('''background-color: #000000;''')
        self.multi_img_viewer.setStyleSheet('''background-color: #004060;''')

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

    def paintEvent(self, QPaintEvent):
        pass
        # geom = self.image_panel_stack_widget.geometry()

        # geom = self.main_widget.geometry()
        # painter = QPainter(self)
        # # painter.setPen(QPen(Qt.black, 5, Qt.SolidLine))
        # painter.setPen(QPen(Qt.black, 3, Qt.SolidLine))
        # # painter.setBrush(QBrush(Qt.red, Qt.SolidPattern))
        # # painter.setBrush(QBrush(Qt.black, Qt.DiagCrossPattern))
        # painter.setBrush(QBrush(Qt.black, Qt.Dense2Pattern))
        # painter.setOpacity(.15)
        # painter.drawRect(geom)

        # pixmap = QPixmap(geom)
        # pixmap.fill(Qt.transparent)
        # qp = QPainter(pixmap)
        # pen = QPen(Qt.red, 3)
        # qp.setPen(pen)
        # qp.drawLine(10, 10, 50, 50)
        # qp.end()
        # self.label_top.setPixmap(pixmap)
        # # self.label_bot.setText(textbot)


    # def __exit__(self, type, value, traceback):
    #     if self.killed:
    #         sys.exit(0)
    #     signal.signal(signal.SIGINT, self.old_sigint)
    #     signal.signal(signal.SIGTERM, self.old_sigterm)



    def show_hide_snr_plot(self):
        if self.snr_plot_and_control.isHidden():
            self.snr_plot_and_control.setHidden(False)
        else:
            self.snr_plot_and_control.setHidden(True)

    def show_hide_hud(self):
        if self.hud.isHidden():
            self.hud.setHidden(False)
        else:
            self.hud.setHidden(True)

    def show_hide_python(self):
        if self.python_console.isHidden():
            self.python_console.setHidden(False)
        else:
            self.python_console.setHidden(True)

    # def show_hide_json(self):
    #     if self..isHidden():
    #         self.project_view_button.setHidden(False)
    #     else:
    #         self.python_console.setHidden(True)


    @Slot()
    def update_snr_plot(self):
        self.main_widget.setCurrentIndex(0)
        if not are_images_imported():
            self.hud('No SNRs To View.', logging.WARNING)
            # self.back_callback()
            return
        if not is_cur_scale_aligned():
            self.hud('No SNRs To View. Current Scale Is Not Aligned Yet.', logging.WARNING)
            # self.back_callback()
            return
        # self.clear_snr_plot()
        snr_list = cfg.data.snr_list()
        pg.setConfigOptions(antialias=True)
        max_snr = max(snr_list)
        x_axis = [x for x in range(0, len(snr_list))]
        # pen = pg.mkPen(color=(0, 0, 0), width=5, style=Qt.SolidLine)
        self.snr_points = pg.ScatterPlotItem(
            size=8,
            pen=pg.mkPen(None),
            # brush=pg.mkBrush('#5c4ccc')
            brushes=[pg.mkBrush('#5c4ccc'),
                     pg.mkBrush('#f3e375'),
                     pg.mkBrush('#d6acd6'),
                     pg.mkBrush('#aaa672'),
                     pg.mkBrush('#152c74'),
                     pg.mkBrush('#404f74')],
            hoverable=True,
            # hoverSymbol='s',
            hoverSize=10,
            # hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('#f3f6fb'),
            # pxMode=False #allow spots to transform with the view
        )
        ##41FF00 <- good green color

        if self.main_stylesheet == 'src/styles/daylight.qss':
            self.snr_plot.setBackground(None)
        else: self.snr_plot.setBackground('#000000')

        # self.snr_points.setFocusPolicy(Qt.NoFocus)
        self.snr_points.sigClicked.connect(self.onSnrClick)
        self.snr_points.addPoints(x_axis[1:], snr_list[1:])

        max_y = max(snr_list)
        self.snr_plot.setXRange(0, max_y, padding=0)


        self.snr_plot.autoRange()
        # self.snr_plot.setYRange(0, max_y)

        value = "test"
        # logger.info('self.snr_points.toolTip() = %s' % self.snr_points.toolTip())
        value = self.snr_points.setToolTip('Test')
        self.last_snr_click = []
        self.snr_plot.addItem(self.snr_points)
        # self.main_panel_bottom_widget.setCurrentIndex(1) #og

    def clear_snr_plot(self):
        # self.snr_plot.getPlotItem().enableAutoRange()
        self.snr_plot.clear()

    def onSnrClick(self, plot, points):
        '''
        type(obj): <class 'pyqtgraph.graphicsItems.ScatterPlotItem.ScatterPlotItem'>
        type(points): <class 'numpy.ndarray'>
        '''
        index = int(points[0].pos()[0])
        snr = float(points[0].pos()[1])
        print('SNR of Selected Layer: %.3f' % snr)
        # clickedPen = pg.mkPen('#f3f6fb', width=3)
        clickedPen = pg.mkPen({'color': "#f3f6fb", 'width': 3})
        for p in self.last_snr_click:
            # p.resetPen()
            p.resetBrush()
        # print("clicked points", points)
        for p in points:
            p.setBrush(pg.mkBrush('#f3f6fb'))
            # p.setPen(clickedPen)

        self.last_snr_click = points
        # self.jump_to_layer(index)
        self.jump_to(index)


    def initJupyter(self):
        logger.info('Initializing Jupyter Console')
        self.python_console = PythonConsole(customBanner='Caution - anything executed here is injected into the main '
                                                         'event loop of AlignEM-SWiFT - '
                                                         'As they say, with great power...!\n\n')
        self.python_console.push_vars({'align':self.align})

        # self.main_panel_bottom_widget.setCurrentIndex(1)
        # self.python_console.execute_command('import IPython; IPython.get_ipython().execution_count = 0')
        # self.python_console.execute_command('from src.config import *')
        # self.python_console.execute_command('from src.helpers import *')
        # self.python_console.execute_command('import src.config as cfg')
        # self.python_console.execute_command('import os, sys, zarr, neuroglancer')
        # self.python_console.execute_command('import src.config as cfg')
        # self.python_console.clear()

    def shutdownJupyter(self):
        logger.info('Shutting Down Jupyter Kernel...')
        try:
            # self.python_console.kernel_client.stop_channels()
            self.python_console.kernel_manager.shutdown_kernel()

        except:
            logger.warning('Having trouble shutting down Jupyter Console Kernel')
            self.python_console.request_interrupt_kernel()

    def restart_python_kernel(self):
        self.hud('Restarting Python Kernel...')
        self.python_console.request_restart_kernel()
        self.hud.done()


    @Slot()
    def back_callback(self):
        logger.info("Returning Home...")
        self.main_widget.setCurrentIndex(0)
        self.image_panel_stack_widget.setCurrentIndex(1)
        # self.main_panel_bottom_widget.setCurrentIndex(0) #og
        self.set_idle()



def bindScrollBars(scrollBar1, scrollBar2):

    # syncronizing scrollbars syncrnonously somehow breaks zooming and doesn't work
    # scrollBar1.valueChanged.connect(lambda value: scrollBar2.setValue(value))
    # scrollBar2.valueChanged.connect(lambda value: scrollBar1.setValue(value))

    # syncronizing scrollbars asyncronously works ok
    scrollBar1.valueChanged.connect(
        lambda _: QTimer.singleShot(0, lambda: scrollBar2.setValue(scrollBar1.value())))
    scrollBar2.valueChanged.connect(
        lambda _: QTimer.singleShot(0, lambda: scrollBar1.setValue(scrollBar2.value())))

    scrollBar1.valueChanged.connect(
        lambda _: QTimer.singleShot(0, lambda: scrollBar2.setValue(scrollBar1.value())))
    scrollBar2.valueChanged.connect(
        lambda _: QTimer.singleShot(0, lambda: scrollBar1.setValue(scrollBar2.value())))

