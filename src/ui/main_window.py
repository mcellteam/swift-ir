#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os, sys, copy, json, inspect, logging, textwrap, psutil, operator, platform, shutil

# import qtpy
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QSpacerItem, QMenu, QMessageBox, \
    QComboBox, QGroupBox, QScrollArea, QToolButton, QSplitter, QRadioButton, QFrame, QTreeView, QHeaderView, \
    QDockWidget, QSplashScreen, QAction, QActionGroup, QProgressBar, QCheckBox, QShortcut
from PyQt5.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication, QKeySequence
from PyQt5.QtCore import Qt, QSize, QUrl, QThreadPool, QRect
from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtCore import pyqtSignal as Signal
import qtawesome as qta
import pyqtgraph as pg
import neuroglancer as ng
import src.config as cfg
if not cfg.NO_NEUROGLANCER:
    from PyQt5.QtWebEngineWidgets import *
    from PyQt5.QtWebEngineCore import *
from src.config import ICON_COLOR
from src.helpers import *
from src.data_model import DataModel
from src.image_utils import get_image_size
from src.compute_affines import compute_affines
from src.generate_aligned import generate_aligned
from src.generate_scales import generate_scales
from src.generate_zarr import generate_zarr
from src.view_3dem import View3DEM
from src.background_worker import BackgroundWorker
from .head_up_display import HeadUpDisplay
from .image_library import ImageLibrary, SmartImageLibrary
from .multi_image_panel import MultiImagePanel
from .toggle_switch import ToggleSwitch
from .json_treeview import JsonModel
from .defaults_form import DefaultsForm
from .kimage_window import KImageWindow
from .snr_plot import SnrPlot
from .jupyter_console import JupyterConsole

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

        logger.info("Initializing Image Library")
        cfg.image_library = ImageLibrary() # SmartImageLibrary()
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

        # if cfg.QT_API == 'pyside6':
        #     logger.info("QImageReader.allocationLimit() WAS " + str(QImageReader.allocationLimit()) + "MB")
        #     QImageReader.setAllocationLimit(4000) #pyside6 #0610setAllocationLimit
        #     logger.info("New QImageReader.allocationLimit() NOW IS " + str(QImageReader.allocationLimit()) + "MB")


        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())

        self.project_progress = 0
        self.project_aligned_scales = []
        self.scales_combobox_switch = 0
        self.jump_to_worst_ticker = 1  # begin iter at 1 b/c first image has no ref
        self.jump_to_best_ticker = 0
        
        # pyside6 only
        logger.info("Initializing Qt WebEngine")
        self.view = QWebEngineView()
        # PySide6-Only Options
        # self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        # if qtpy.PYQT6:
        #     self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        # self.browser.setPage(CustomWebEnginePage(self)) # Open clicked links in new window
        
        self.panel_list = []
        self.match_point_mode = False

        '''Initialize Status Bar'''
        logger.info('Initializing Status Bar')
        self.status = self.statusBar()
        self.pbar = QProgressBar(self)
        self.pbar.setGeometry(30, 40, 200, 25)
        self.pbar.setStyleSheet("QLineEdit { background-color: yellow }")
        self.status.addPermanentWidget(self.pbar)
        self.pbar.setMaximumWidth(400)
        self.pbar.hide()

        '''Initialize Jupyter Console'''
        logger.info('Initializing Jupyter Console')
        self.jupyter_console = JupyterConsole()
        cfg.defaults_form = DefaultsForm(parent=self)
        app.aboutToQuit.connect(self.shutdown_jupyter_kernel)

        logger.info("Initializing Data Model")
        cfg.data = DataModel()

        '''Initialize Menu'''
        logger.info('Initializing Menu')
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # Fix for non-native menubar on macOS

        self._unsaved_changes = False
        self._up = 0

        self._working = False

        self.resized.connect(self.center_all_images)

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
                 ['&New Project', 'Ctrl+N', self.new_project, None, None, None],
                 ['&Open Project', 'Ctrl+O', self.open_project, None, None, None],
                 ['&Save Project', 'Ctrl+S', self.save_project, None, None, None],
                 ['&Configure Project Options', 'Ctrl+C', self.run_after_import, None, None, None],
                 ['Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None],
                 # ['Show/Hide Project Inspector', None, self.show_hide_project_inspector, None, None, None],

                 ['&Help', None, self.documentation_view, None, None, None],

                 ['Go Back', None, self.back_callback, None, None, None],
                 ['Exit', 'Ctrl+Q', self.exit_app, None, None, None]
             ]
             ],
            ['&Tools',
             [
                 ['&Match Point Align Mode',
                  [
                      ['Toggle &Match Point Mode', 'Ctrl+M', self.toggle_match_point_align, None, False, True],
                      ['&Remove All Match Points', 'Ctrl+R', self.clear_match_points, None, None, None],
                  ]
                  ],
                 ['Go To Next Worst SNR', None, self.jump_to_worst_snr, None, None, None],
                 ['Go To Next Best SNR', None, self.jump_to_best_snr, None, None, None],
                 ['Apply Project Defaults', None, cfg.data.set_defaults, None, None, None],
                 ['&Set User Progress',
                  [
                      ['0', None, self.set_progress_stage_0, None, None, None],
                      ['1', None, self.set_progress_stage_1, None, None, None],
                      ['2', None, self.set_progress_stage_2, None, None, None],
                      ['3', None, self.set_progress_stage_3, None, None, None],
                      ['++1', 'Ctrl+]', self.cycle_user_progress, None, None, None],
                  ]
                  ],
                 ['View &K Image', 'Ctrl+K', self.view_k_img, None, None, None],
                 ['&Python Console', 'Ctrl+P', self.show_jupyter_console, None, None, None],

             ]
             ],
            ['&View',
             [
                 ['Show Project JSON', 'Ctrl+J', self.project_view_callback, None, None, None],
                 ['Show Python Console', None, self.show_jupyter_console, None, None, None],
                 ['Show SNR Plot', None, self.show_snr_plot, None, None, None],
                 ['Show Remote Neuroglancer', None, self.remote_view, None, None, None],
                 ['Toggle Zarr Controls', None, self.toggle_zarr_controls, None, None, None],
                 ['Show Splash', None, self.show_splash, None, None, None],
                 ['Theme',
                  [
                      ['Default Theme', None, self.apply_default_style, None, None, None],
                      # ['Style #2 - Light2', None, self.apply_stylesheet_2, None, None, None],
                      ['Daylight Theme', None, self.apply_daylight_style, None, None, None],
                      ['Moonlit Theme', None, self.apply_moonlit_style, None, None, None],
                      # ['Style #11 - Screamin Green', None, self.apply_stylesheet_11, None, None, None],
                      ['Midnight Theme', None, self.apply_midnight_style, None, None, None],
                      # ['Minimal', None, self.minimal_stylesheet, None, None, None],

                  ]
                  ],

             ]
             ],
            ['&Debug',
             [
                 # ['Launch Debugger', None, self.launch_debugger, None, None, None],
                 ['Auto Set User Progress', None, self.auto_set_user_progress, None, None, None],
                 ['Refresh All Images (Repaint+Update Panels)', None, self.refresh_all_images, None, None, None],
                 # ['Read data Update GUI', None, self.read_project_data_update_gui, None, None, None],
                 # ['Read GUI Update data', None, self.read_gui_update_project_data, None, None, None],
                 ['Link Images Stacks', None, cfg.data.link_all_stacks, None, None, None],
                 ['Reload Scales Combobox', None, self.reload_scales_combobox, None, None, None],
                 # ['Update Project Inspector', None, self.update_project_inspector, None, None, None],
                 ['Update Alignment Details', None, self.update_alignment_details, None, None, None],
                 ['Update Scale Controls', None, self.update_scale_controls, None, None, None],
                 ['Print Sanity Check', None, print_sanity_check, None, None, None],
                 ['Print Project Tree', None, print_project_tree, None, None, None],
                 ['Print Image Library', None, self.print_image_library, None, None, None],
                 ['Print Aligned Scales List', None, cfg.data.get_aligned_scales_list, None, None, None],
                 ['Print Single Alignment Layer', None, print_alignment_layer, None, None, None],
                 ['Print SNR List', None, print_snr_list, None, None, None],
                 # ['Print .dat Files', None, print_dat_files, None, None, None],
                 ['Print Working Directory', None, print_path, None, None, None],
                 ['Print Zarr Details', None, print_zarr_info, None, None, None],
                 ['Google', None, self.google, None, None, None],
                 # ['chrome://gpu', None, self.gpu_config, None, None, None],
                 ['Test WebGL', None, self.webgl2_test, None, None, None],
             ]
             ],
        ]
        self.build_menu_from_list(self.menu, ml)

        self.initShortcuts()

        '''Initialize UI'''
        logger.info('Initializing UI')
        self.initUI()

        logger.info('Applying Stylesheet')
        self.main_stylesheet = os.path.abspath('src/styles/default.qss')
        # self.main_stylesheet = os.path.abspath('src/styles/daylight.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())  # must be after QMainWindow.__init__(self)

        check_for_binaries()

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

    def update_panels(self):
        '''Repaint the viewing port.'''
        logger.debug("MainWindow.update_panels:")
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()
    
    @Slot()
    def refresh_all_images(self):
        logger.info("MainWindow is refreshing all images (called by " + inspect.stack()[1].function + ")...")
        self.image_panel.refresh_all_images()
    
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
            self.hud.post('Another Process is Already Running', logging.WARNING)
            self.set_idle()
            return
        else:
            pass

        self.set_status("Busy...")
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.hud.post('Requesting scale factors from user')

        if do_scales_exist():
            self.hud.post('This data was scaled already. Re-scaling now resets alignment progress.',
                          logging.WARNING)
            reply = QMessageBox.question(self, 'Verify Regenerate Scales',
                                         'Regenerating scales now will reset progress.\n\n'
                                         'Continue with rescaling?',
                                         QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                self.hud.post('Continuing With Rescaling...')
                #
                # # for scale in get_scales():
                # #     scale_path = os.path.join(proj_path, scale, 'img')
                # #     try:
                # #         shutil.rmtree()
                #
                # self.hud.post('Removing Previously Generated Images...')
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
                # zarr_path = os.path.join(proj_path, '3dem.zarr')
                # if os.path.exists(zarr_path):
                #     logger.info('Removing directory %s...' % zarr_path)
                #     try:
                #         shutil.rmtree(zarr_path)
                #     except Exception as e:
                #         logger.warning('Failed to delete %s. Reason: %s' % (zarr_path, e))
                #
                # self.update_panels() #!!
                # self.update_win_self()
                # self.hud.post('Done')

            else:
                self.hud.post('Rescaling canceled.')
                self.set_idle()
                return

        if do_scales_exist():
            default_scales = map(str, cfg.data.get_scale_vals())
        else:
            default_scales = ['1']
        input_val, ok = QInputDialog().getText(None, "Define Scales",
                                               "Please enter your scaling factors separated by spaces." \
                                               "\n\nFor example, to generate 1x 2x and 4x scale datasets: 1 2 4\n\n"
                                               "Your current scales: " + str(' '.join(default_scales)),
                                               echo=QLineEdit.Normal,
                                               text=' '.join(default_scales))
        
        if not ok:
            self.hud.post('Canceling Scaling Process')
            self.set_idle()
            return
        
        if input_val == '':
            self.hud.post('Input Was Empty, Please Provide Scaling Factors', logging.WARNING)
            self.set_idle()
            logger.info('<<<< run_scaling')
            return
        cfg.data.set_scales_from_string(input_val)

        ########
        self.hud.post('Generating Scale Image Hierarchy (Selected Levels: %s)...' % input_val)
        # self.pbar.show()
        self.show_hud()
        self.set_status("Scaling...")
        try:
            self.worker = BackgroundWorker(fn=generate_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('Generating Scales Triggered an Exception - Returning', logging.ERROR)

        cfg.data.link_all_stacks()
        cfg.data.set_defaults()
        cfg.data['data']['current_scale'] = cfg.data.get_scales()[-1]
        self.read_project_data_update_gui()
        self.set_progress_stage_2()
        self.reload_scales_combobox()  # 0529 #0713+
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        self.update_scale_controls()
        self.center_all_images()
        self.update_win_self()
        self.shake()
        self.save_project_to_file()
        self.hud.post('Scaling Complete.')


    def run_scaling_auto(self):
        self.hud.post('Generating Scale Image Hierarchy...')
        # self.pbar.show()
        self.show_hud()
        self.set_status("Scaling...")
        try:
            self.worker = BackgroundWorker(fn=generate_scales())
            self.threadpool.start(self.worker)
        except:
            print_exception()
            logger.warning('Generating Scales Triggered an Exception')

        cfg.data.link_all_stacks()
        cfg.data.set_defaults()
        cfg.data['data']['current_scale'] = cfg.data.get_scales()[-1]
        self.read_project_data_update_gui()
        self.set_progress_stage_2()
        self.reload_scales_combobox()  # 0529 #0713+
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        self.update_scale_controls()
        self.center_all_images()
        self.update_win_self()
        self.shake()
        self.save_project_to_file()
        self.hud.post('Scaling Complete.')

    
    @Slot()
    def run_alignment(self, use_scale) -> None:
        logger.info('run_alignment:')
        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            return
        else:
            pass
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.read_gui_update_project_data()
        if not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.get_next_coarsest_scale_key())
            self.hud.post(warning_msg, logging.WARNING)
            return
        self.set_status('Aligning...')
        alignment_option = cfg.data['data']['scales'][use_scale]['method_data']['alignment_option']
        if alignment_option == 'init_affine':
            cfg.main_window.hud.post("Initializing Affine Transformations at Scale: %d..." % (get_scale_val(use_scale)))
        else:
            cfg.main_window.hud.post("Refining Affine Transfors at Scale: %d..." % (get_scale_val(use_scale)))
        self.show_hud()
        self.al_status_checkbox.setChecked(False)
        try:
            self.worker = BackgroundWorker(fn=compute_affines(
                use_scale=use_scale, start_layer=0, num_layers=-1))
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)

        # if not is_cur_scale_aligned():
        #     self.hud.post('Current Scale Was Not Aligned.', logging.ERROR)
        #     self.set_idle()
        #     return
        self.update_alignment_details()
        self.hud.post('Alignment Succeeded.')

        # self.pbar.show()
        self.set_status('Generating Images...')
        self.hud.post('Generating Aligned Images...')
        try:
            self.worker = BackgroundWorker(fn=generate_aligned(use_scale=use_scale, start_layer=0, num_layers=-1))
            self.threadpool.start(self.worker)
        except:

            print_exception()
            self.hud.post('Alignment Succeeded but Applying the Affine Failed.'
                          ' Try Re-generating images.',logging.ERROR)
            self.set_idle()
            return

        # if are_aligned_images_generated():

        if self.main_panel_bottom_widget.currentIndex() == 1:
           self.show_snr_plot()

        self.refresh_all_images()
        self.has_unsaved_changes()
        self.read_project_data_update_gui()
        self.center_all_images()
        self.update_panels()  # 0721+
        self.hud.post('Image Generation Complete')
        self.update_win_self()
        # self.image_panel.all_images_actual_size()
        # self.center_all_images()
        # self.image_panel.zpw[2].setFocus()
        # self.image_panel.need_to_center = 1
        self.shake()
        self.set_progress_stage_3()
        self.image_panel.zpw[2].center_image() #***
        if are_aligned_images_generated():
            self.image_panel.zpw[2].show_ng_button()
        else:
            self.image_panel.zpw[2].hide_ng_button()
        if self.image_panel_stack_widget.currentIndex() == 1:
            self.reload_ng()
    
    @Slot()
    def run_regenerate_alignment(self, use_scale) -> None:
        logger.info('run_regenerate_alignment:')
        if self._working == True:
            self.hud.post('Another Process is Already Running', logging.WARNING)
            self.set_idle()
            return

        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.read_gui_update_project_data()
        if not is_cur_scale_aligned():
            self.hud.post('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING)
            self.set_idle()
            return

        try:
            self.worker = BackgroundWorker(fn=generate_aligned(use_scale=use_scale, start_layer=0, num_layers=-1))
            self.threadpool.start(self.worker)
        except:
            print_exception()
            self.hud.post('Something Went Wrong During ImageGeneration.', logging.ERROR)
            self.set_idle()
            return
        self.hud.post('Image Generation Complete')

        # self.pbar.show()
        self.set_busy()
        self.hud.post('Generating Aligned Images...')
        if are_aligned_images_generated():
            logger.info('are_aligned_images_generated() returned True. Setting user progress to stage 3...')
            self.set_progress_stage_3()
            self.image_panel.zpw[2].setFocus()
            self.image_panel.center_all_images()
            # self.next_scale_button_callback()
            # self.prev_scale_button_callback()
            # get_layer = get_cur_layer()
            # self.jump_to_layer(-1)
            # self.jump_to_layer(get_layer)
            # self.center_all_images()
            # self.read_project_data_update_gui()
            # self.update_win_self()
            self.image_panel.all_images_actual_size()
            self.center_all_images()
            self.image_panel.update_multi_self()
            # self.image_panel.need_to_center = 1
            self.image_panel.zpw[2].center_image()  # ***
            if are_aligned_images_generated():
                self.image_panel.zpw[2].show_ng_button()
            else:
                self.image_panel.zpw[2].hide_ng_button()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
            self.hud.post("Regenerate Complete")
            logger.info('\n\nRegenerate Complete\n')
        else:

            print_exception()
            self.hud.post('Image Generation Failed Unexpectedly. Try Re-aligning First.', logging.ERROR)
            self.set_idle()
            return
        self.update_win_self()
        self.shake()
        self.has_unsaved_changes()


    
    def run_export(self):
        logger.info('Exporting to Zarr format...')
        if self._working == True:
           self.hud.post('Another Process is Already Running', logging.WARNING)
           self.set_idle()
           return

        self.hud.post('Exporting...')
        if not are_aligned_images_generated():
            self.hud.post('Current Scale Must be Aligned Before It Can be Exported', logging.WARNING)
            logger.debug('(!) There is no alignment at this scale to export. Returning from export_zarr().')
            self.show_warning('No Alignment', 'There is no alignment to export.\n\n'
                                         'Typical workflow:\n'
                                         '(1) Open a data or import images and save.\n'
                                         '(2) Generate a set of scaled images and save.\n'
                                         '--> (3) Align each scale starting with the coarsest.\n'
                                         '(4) Export alignment to Zarr format.\n'
                                         '(5) View data in Neuroglancer client')
            self.set_idle()
            return
        
        self.set_status('Exporting...')
        self.hud.post('Generating Neuroglancer-Compatible Zarr...')
        src = os.path.abspath(cfg.data['data']['destination_path'])
        out = os.path.abspath(os.path.join(src, '3dem.zarr'))
        self.hud.post('  Compression Level: %s' %  self.clevel_input.text())
        self.hud.post('  Compression Type: %s' %  self.cname_combobox.currentText())
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
        self.hud.post('Process Finished')

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
                    self.hud.post('Resetting Skips...')
                    cfg.data.clear_all_skips()
                except:
                    print_exception()
                    self.hud.post('Something Went Wrong', logging.WARNING)
        else:
            self.hud.post('There Are No Skips To Clear.', logging.WARNING)
            return

    def update_win_self(self):
        logger.debug("update_win_self (called by %s):" % inspect.stack()[1].function)
        # self.center_all_images()  # uncommenting causes centering issues to re-emerge
        self.update()  # repaint
    
    @Slot()
    def apply_all_callback(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        swim_val = self.get_swim_input()
        whitening_val = self.get_whitening_input()
        scales_dict = cfg.data['data']['scales']
        self.hud.post('Applying these alignment settings to data...')
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
    def update_scale_controls(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev scale buttons depending on current scale.
        (2) Set the enabled/disabled state of the align-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        logger.info('Updating Scale Controls (Called by %s)...' % inspect.stack()[1].function)
        if self.project_progress >= 2:
            if cfg.data.get_n_scales() == 1:
                self.prev_scale_button.setEnabled(False)
                self.next_scale_button.setEnabled(False)
                self.align_all_button.setEnabled(True)
            else:
                cur_index = self.scales_combobox.currentIndex()
                if cur_index == 0:
                    self.next_scale_button.setEnabled(False)
                    self.prev_scale_button.setEnabled(True)
                elif cfg.data.get_n_scales() == cur_index + 1:
                    self.next_scale_button.setEnabled(True)
                    self.prev_scale_button.setEnabled(False)
                else:
                    self.next_scale_button.setEnabled(True)
                    self.prev_scale_button.setEnabled(True)
            if cfg.data.is_alignable():
                self.align_all_button.setEnabled(True)
            else:
                self.align_all_button.setEnabled(False)
            if are_aligned_images_generated():
                self.image_panel.zpw[2].show_ng_button()
            else:
                self.image_panel.zpw[2].hide_ng_button()

            self.jump_validator = QIntValidator(0, cfg.data.get_n_images())
            self.update_alignment_details() #Shoehorn
    
    @Slot()
    def update_alignment_details(self) -> None:
        '''Update alignment details in the Alignment control panel group box.'''
        # logger.info('Updating Alignment Banner Details')
        al_stack = cfg.data['data']['scales'][cfg.data.get_scale()]['alignment_stack']
        self.al_status_checkbox.setChecked(is_cur_scale_aligned())
        dict = {'init_affine':'Initialize Affine','refine_affine':'Refine Affine','apply_affine':'Apply Affine'}
        img_size = get_image_size(al_stack[0]['images']['base']['filename'])
        method_str = dict[cfg.data['data']['scales'][cfg.data.get_scale()]['method_data']['alignment_option']]
        self.alignment_status_label.setText("Is Aligned? ")
        self.align_label_resolution.setText('%sx%spx' % (img_size[0], img_size[1]))
        self.align_label_affine.setText(method_str)
        self.align_label_scales_remaining.setText('# Scales Unaligned: %d' %
                                                  len(cfg.data.get_not_aligned_scales_list()))
        if not do_scales_exist():
            cur_scale_str = 'Scale: n/a'
            self.align_label_cur_scale.setText(cur_scale_str)
        else:
            cur_scale_str = 'Scale: ' + str(get_scale_val(cfg.data.get_scale()))
            self.align_label_cur_scale.setText(cur_scale_str)

    
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
    def next_scale_button_callback(self) -> None:
        logger.info('next_scale_button_callback:')
        '''Callback function for the Next Scale button (scales combobox may not be visible but controls the current scale).'''
        if not self.next_scale_button.isEnabled(): return
        if not are_images_imported(): return
        if self._working:
            self.hud.post('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index - 1
            self.scales_combobox.setCurrentIndex(requested_index)  # changes scale
            self.read_project_data_update_gui()
            self.update_scale_controls()
            self.hud.post('Scale Changed to %d' % get_scale_val(cfg.data.get_scale()))
            if not cfg.data.is_alignable():
                self.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
            if self.main_panel_bottom_widget.currentIndex() == 1:
                # self.plot_widget.clear() #0824
                self.show_snr_plot()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
        except:
            print_exception()
        finally:
            self.scales_combobox_switch = 0
    
    @Slot()
    def prev_scale_button_callback(self) -> None:
        logger.info('prev_scale_button_callback:')
        '''Callback function for the Previous Scale button (scales combobox may not be visible but controls the current scale).'''
        if not self.prev_scale_button.isEnabled(): return
        if not are_images_imported(): return
        if self._working:
            self.hud.post('Changing scales during CPU-bound processes is not currently supported.', logging.WARNING)
            return
        try:
            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index + 1
            self.scales_combobox.setCurrentIndex(requested_index)  # changes scale
            self.read_project_data_update_gui()
            self.update_scale_controls()
            if not cfg.data.is_alignable():
                self.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
            if self.main_panel_bottom_widget.currentIndex() == 1:
                self.plot_widget.clear()
                self.show_snr_plot()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
            self.hud.post('Viewing Scale Level %d' % get_scale_val(cfg.data.get_scale()))
        except:
            print_exception()
        finally:
            self.scales_combobox_switch = 0
    
    @Slot()
    def show_snr_plot(self):
        if not are_images_imported():
            self.hud.post('No SNRs To View.', logging.WARNING)
            self.back_callback()
            return
        if not is_cur_scale_aligned():
            self.hud.post('No SNRs To View. Current Scale Is Not Aligned Yet.', logging.WARNING)
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
        # self.snr_points.setFocusPolicy(Qt.NoFocus)
        self.snr_points.sigClicked.connect(self.onSnrClick)
        self.snr_points.addPoints(x_axis[1:], snr_list[1:])
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
        self.jump_to(index)

    def show_hud(self):
        self.main_panel_bottom_widget.setCurrentIndex(0)

    def shutdown_jupyter_kernel(self):
        logger.info('Shutting Down Jupyter Kernel...')
        try:
            self.jupyter_widget.kernel_client.stop_channels()
            self.jupyter_widget.kernel_manager.shutdown_kernel()
        except:
            logger.warning('Unable to Shutdown Jupyter Console Kernel')

    def show_jupyter_console(self):
        # self.jupyter_console.execute_command('import IPython; IPython.get_ipython().execution_count = 0')
        self.jupyter_console.execute_command('from IPython.display import Image, display')
        self.jupyter_console.execute_command('from src.config import *')
        self.jupyter_console.execute_command('import src.config as cfg')
        self.jupyter_console.execute_command('from src.helpers import *')
        self.jupyter_console.execute_command('import os, sys')
        self.jupyter_console.execute_command('import zarr')
        self.jupyter_console.execute_command("z = zarr.open(os.path.join(cfg.data.destination(), '3dem.zarr'))")
        self.jupyter_console.execute_command('clear')
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
        logger.info("scale['alignment_stack'][cfg.data['data']['current_layer']]['skip'] = ",
                    scale['alignment_stack'][cfg.data['data']['current_layer']]['skip'])
        self.toggle_skip.setChecked(not scale['alignment_stack'][cfg.data['data']['current_layer']]['skip'])

    @Slot()
    def set_status(self, msg: str) -> None:
        self.status.showMessage(msg)
    
    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')
    
    def apply_default_style(self):
        self.main_stylesheet = 'src/styles/default.qss'
        self.hud.post('Switching to Default Theme')
        self.jupyter_console.set_color_linux()
        self.hud.set_theme_default()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_daylight_style(self):
        '''Light stylesheet'''
        self.main_stylesheet = 'src/styles/daylight.qss'
        self.hud.post('Switching to Daylight Theme')
        self.jupyter_console.set_color_none()
        self.hud.set_theme_light()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_moonlit_style(self):
        '''Grey stylesheet'''
        self.main_stylesheet = 'src/styles/moonlit.qss'
        self.hud.post('Switching to Moonlit Theme')
        self.jupyter_console.set_color_linux()
        self.hud.set_theme_default()
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_midnight_style(self):
        self.main_stylesheet = 'src/styles/midnight.qss'
        self.hud.post('Switching to Midnight Theme')
        self.jupyter_console.set_color_linux()
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
        if self.get_user_progress() != 0: self.hud.post('Reverting user progress to Project')
        self.set_user_progress(False, False, False, False)
        self.project_progress = 0
    
    def set_progress_stage_1(self):
        if self.get_user_progress() > 1:
            self.hud.post('Reverting user progress to Data Selection & Scaling')
        elif self.get_user_progress() < 1:
            self.hud.post('Setting user progress to Data Selection & Scaling')
        self.set_user_progress(True, False, False, False)
        self.project_progress = 1
    
    def set_progress_stage_2(self):
        if self.get_user_progress() > 2:
            self.hud.post('Reverting user progress to Alignment')
        elif self.get_user_progress() < 2:
            self.hud.post('Setting user progress to Alignment')
        self.set_user_progress(True, True, True, False)
        self.project_progress = 2
    
    def set_progress_stage_3(self):
        if self.get_user_progress() < 2: self.hud.post('Setting user progress to Export & View')
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
            logger.warning('No Scales Yet, Nothing To Do (caller: %s) - Returning' % inspect.stack()[1].function)
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
            logger.warning('No Scales Yet, Nothing To Do (Caller: %s)' % inspect.stack()[1].function)
            return

        try: self.toggle_skip.setChecked(not cfg.data.get_skip())
        except: logger.warning('Skip Toggle Widget Failed to Update')

        try: self.jump_input.setText(str(cfg.data.get_layer()))
        except: logger.warning('Current Layer Widget Failed to Update')

        try: self.whitening_input.setText(str(cfg.data.get_whitening()))
        except: logger.warning('Whitening Input Widget Failed to Update')

        try: self.swim_input.setText(str(cfg.data.get_swim_window()))
        except: logger.warning('Swim Input Widget Failed to Update')

        try: self.toggle_bounding_rect.setChecked(cfg.data.get_bounding_rect())
        except: logger.warning('Bounding Rect Widget Failed to Update')

        if cfg.data.get_null_cafm() == False:
            self.null_bias_combobox.setCurrentText('None')
        else:
            self.null_bias_combobox.setCurrentText(str(cfg.data.get_poly_order()))

        if cfg.data.get_layer() == 0:
            self.layer_down_button.setEnabled(False)
        else:
            self.layer_down_button.setEnabled(True)
        if cfg.data.get_layer() == cfg.data.get_n_images() - 1:
            self.layer_up_button.setEnabled(False)
        else:
            self.layer_up_button.setEnabled(True)


        #0907-
        # alignment_option = cfg.data['data']['scales'][cfg.data.get_scale()]['method_data']['alignment_option']
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

        # if cfg.data.get_scale() == 'scale_1':
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

    def toggle_zarr_controls(self):
        self.export_and_view_stack.show()
        # if self.cname_combobox.isHidden():
        #     self.cname_combobox.show()
        #     self.cname_label.show()
        #     self.clevel_input.show()
        #     self.clevel_label.show()
        # else:
        #     self.cname_combobox.hide()
        #     self.cname_label.hide()
        #     self.clevel_input.hide()
        #     self.clevel_label.hide()


    # self.cname_combobox.show()
    # self.cname_label.show()
    # self.clevel_input.show()
    # self.clevel_label.show()

    
    @Slot()
    def set_idle(self) -> None:
        self.status.showMessage('Idle')

    @Slot()
    def set_busy(self) -> None:
        self.status.showMessage('Busy...')
    
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
        cfg.data['data']['current_layer'] = int(layer)
        self.read_project_data_update_gui()
        self.image_panel.update_multi_self()
    
    @Slot()
    def jump_to_layer(self) -> None:
        self.set_status('Busy...')
        # if self.jump_input.text() == '':
        #     return
        # else:
        try:
            self.read_gui_update_project_data()
            requested_layer = int(self.jump_input.text())
            self.hud.post("Jumping to Layer " + str(requested_layer))
            n_layers = len(cfg.data['data']['scales'][cfg.data.get_scale()]['alignment_stack'])
            if requested_layer >= n_layers:  # Limit to largest
                requested_layer = n_layers - 1
            cfg.data.set_layer(requested_layer)
            self.read_project_data_update_gui()
            self.image_panel.update_multi_self()
            if self.image_panel_stack_widget.currentIndex() == 1:
                self.reload_ng()
        except:
            print_exception()
        self.set_idle()
    
    @Slot()
    def jump_to_worst_snr(self) -> None:
        self.set_status('Busy...')
        if not are_images_imported():
            self.hud.post("You Must Import Some Images First!")
            self.set_idle()
            return
        if not are_aligned_images_generated():
            self.hud.post("You Must Align This Scale First!")
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
            self.hud.post("Jumping to Layer %d (Badness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            cfg.data.set_layer(next_layer)
            self.read_project_data_update_gui()
            self.image_panel.update_multi_self()
            self.jump_to_worst_ticker += 1
        except:
            self.jump_to_worst_ticker = 1
            print_exception()
        self.set_idle()

    @Slot()
    def jump_to_best_snr(self) -> None:
        self.set_status('Busy...')
        if not are_images_imported():
            self.hud.post("You Must Import Some Images First!")
            self.set_idle()
            return
        if not are_aligned_images_generated():
            self.hud.post("You Must Align This Scale First!")
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
            self.hud.post("Jumping to layer %d (Goodness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            cfg.data.set_layer(next_layer)
            self.read_project_data_update_gui()
            self.image_panel.update_multi_self()
            self.jump_to_best_ticker += 1
        except:
            self.jump_to_best_ticker = 0
            print_exception()
        self.set_idle()

    @Slot()
    def reload_scales_combobox(self) -> None:
        logger.debug('Caller: %s' % inspect.stack()[1].function)
        prev_state = self.scales_combobox_switch
        self.scales_combobox_switch = 0
        curr_scale = cfg.data.get_scale()
        image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.data['data']['scales'].keys())]
        self.scales_combobox.clear()
        for scale in sorted(image_scales_to_run):
            self.scales_combobox.addItems(["scale_" + str(scale)])
        index = self.scales_combobox.findText(curr_scale, Qt.MatchFixedString)
        if index >= 0: self.scales_combobox.setCurrentIndex(index)
        self.scales_combobox_switch = prev_state
    
    @Slot()
    def fn_scales_combobox(self) -> None:
        if self.scales_combobox_switch == 0:
            # logger.warning('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return None
        cfg.data.set_scale(self.scales_combobox.currentText())
        self.read_project_data_update_gui()
        self.center_all_images() #0903+

    @Slot()
    def change_scale(self, scale_key: str):
        try:
            cfg.data['data']['current_scale'] = scale_key
            self.read_project_data_update_gui()
            self.center_all_images()
            logger.info('Scale changed to %s' % scale_key)
        except:
            print_exception()
            logger.info('Changing Scales Triggered An Exception')

    @Slot()
    def change_layer_up(self):
        self.image_panel.zpw[0].change_layer(1)
        # if self.image_panel_stack_widget.currentIndex() == 1:
        #     self.reload_ng()

    @Slot()
    def change_layer_down(self):
        self.image_panel.zpw[0].change_layer(-1)
        # if self.image_panel_stack_widget.currentIndex() == 1:
        #     self.reload_ng()
    
    @Slot()
    def print_image_library(self):
        logger.info(str(cfg.image_library))
    
    def new_project(self):
        logger.debug('new_project:')
        self.hud.post('Creating New Project...')
        self.set_status("Project...")
        self.main_panel_bottom_widget.setCurrentIndex(0)
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
                self.hud.post('New Project Canceled')
                self.set_idle()
                return
            if reply == QMessageBox.Cancel:
                logger.info("Response was 'Cancel'")
                self.hud.post('New Project Canceled')
                self.set_idle()
                return
        self.set_progress_stage_0()
        filename = self.new_project_save_as_dialog()
        if filename == '':
            self.hud.post("You did not enter a valid name for the data file.")
            self.set_idle()
            return

        logger.info("Overwriting data data in memory with data template")
        '''Create new DataModel object'''

        if not filename.endswith('.json'):
            filename += ".json"
        logger.info("Creating new data %s" % filename)
        path, extension = os.path.splitext(filename)
        cfg.data = DataModel(name=path)
        makedirs_exist_ok(cfg.data['data']['destination_path'], exist_ok=True)
        self.setWindowTitle("Project: " + os.path.split(cfg.data.destination())[-1])
        self.save_project()
        self.set_progress_stage_1()
        self.scales_combobox.clear()  # why? #0528
        # self.run_after_import()
        # preallocate_zarr()
        cfg.IMAGES_IMPORTED = False
        self.image_panel.update_multi_self()
        self.set_idle()
    
    def import_images_dialog(self):
        '''Dialog for importing images. Returns list of filenames.'''
        caption = "Import Images"
        filter = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.gif);;All Files (*)"
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getOpenFileNames(
            parent=self,
            caption=caption,
            filter=filter,
            options=options
        )
        return response[0]
    
    def open_project_dialog(self) -> str:
        '''Dialog for opening a data. Returns 'filename'.'''
        caption = "Open Project (.json)"
        filter = "Projects (*.json);;All Files (*)"
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getOpenFileName(
            parent=self,
            caption=caption,
            filter=filter,
            options=options
        )
        return response[0]
    
    def save_project_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        caption = "Save Project"
        filter = "Projects (*.json);;All Files (*)"
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getSaveFileName(
            parent=self,
            caption=caption,
            filter=filter,
            options=options
        )
        return response[0]
    
    def new_project_save_as_dialog(self) -> str:
        '''Dialog for saving a data. Returns 'filename'.'''
        caption = "New Project Save As..."
        filter = "Projects (*.json);;All Files (*)"
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        response = QFileDialog.getSaveFileName(
            parent=self,
            caption=caption,
            filter=filter,
            options=options
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
        logger.info('Opening Project...')
        self.set_status("Project...")


        # Going to need something like this here
        # if self._unsaved_changes:
        #     self.hud.post('Confirm Exit AlignEM-SWiFT')
        #     message = "There are unsaved changes.\n\nSave before exiting?"
        #     msg = QMessageBox(QMessageBox.Warning, "Save Changes", message, parent=self)
        #     msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        #     msg.setDefaultButton(QMessageBox.Save)
        #     msg.setIcon(QMessageBox.Question)
        #     reply = msg.exec_()
        #     if reply == QMessageBox.Cancel:
        #         logger.info('reply=Cancel. Returning control to the app.')
        #         self.hud.post('Canceling exit application')
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
                proj_copy = json.load(f)
            proj_copy = DataModel(proj_copy)
            if type(proj_copy) == type('abc'):
                self.hud.post('There Was a Problem Loading the Project File', logging.ERROR)
                logger.warning("Project Type is Abstract Base Class - Unable to Load!")
                self.set_idle()
                return
            self.hud.post("Loading data '%s'" % filename)
            logger.info("proj_copy['data']['destination_path'] was: %s" % proj_copy['data']['destination_path'])
            proj_copy['data']['destination_path'] = make_absolute(proj_copy['data']['destination_path'], filename)
            logger.info('make_absolute is returning: %s' % proj_copy['data']['destination_path'])

            for scale_key in proj_copy['data']['scales'].keys():
                scale_dict = proj_copy['data']['scales'][scale_key]
                for layer in scale_dict['alignment_stack']:
                    for role in layer['images'].keys():
                        layer['images'][role]['filename'] = make_absolute(layer['images'][role]['filename'], filename)

            cfg.data = copy.deepcopy(proj_copy)  # Replace the current version with the copy
            cfg.data.ensure_proper_data_structure()
            cfg.data.link_all_stacks()
            self.read_project_data_update_gui()
            self.reload_scales_combobox()
            self.auto_set_user_progress()
            self.update_scale_controls()
            self.image_panel.setFocus()
            if are_images_imported():
                cfg.IMAGES_IMPORTED = True
                self.generate_scales_button.setEnabled(True)
            else:
                cfg.IMAGES_IMPORTED = False
                self.generate_scales_button.setEnabled(False)

            if are_aligned_images_generated():
                self.image_panel.zpw[2].show_ng_button()
            else:
                self.image_panel.zpw[2].hide_ng_button()
            self.center_all_images()
            self.setWindowTitle("Project: %s" % os.path.basename(cfg.data.destination()))
            self.hud.post("Project '%s'" % cfg.data.destination())
        else:
            self.hud.post("No data file (.json) was selected")
        self.set_idle()

    def save_project(self):
        logger.debug('save_project:')
        self.set_status("Saving...")
        try:
            self.save_project_to_file()
            self._unsaved_changes = False
            self.hud.post("Project saved as '%s'" % cfg.data.destination())
        except:
            self.hud.post('Nothing To Save', logging.WARNING)
        self.set_idle()
    
    def save_project_as(self):
        logger.debug("save_project_as:")
        self.set_status("Saving...")
        filename = self.save_project_dialog()
        if filename != '':
            try:
                self.save_project_to_file()
                self.hud.post("Project saved as '%s'" % cfg.data.destination())
            except:
                print_exception()
                self.hud.post('Save Project Failed', logging.ERROR)
        self.set_idle()
    
    def save_project_to_file(self):
        logger.debug('Saving data...')
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
                        l['images'][role]['filename'] = make_relative(filename, cfg.data.destination())
        logger.info('---- WRITING DATA TO PROJECT FILE ----')
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        proj_json = jde.encode(data_cp)
        name = cfg.data.destination()
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
        scale = cfg.data.get_scale()
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
        local_cur_scale = cfg.data.get_scale()
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
        logger.info('Importing images...')
        self.set_status('Importing...')
        role_to_import = 'base'
        file_name_list = sorted(self.import_images_dialog())
        local_cur_scale = cfg.data.get_scale()
        if clear_role:
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            for layer in cfg.data['data']['scales'][local_cur_scale]['alignment_stack']:
                if role_to_import in layer['images'].keys():
                    layer['images'].pop(role_to_import)
        
        if file_name_list != None:
            if len(file_name_list) > 0:
                logger.debug("Selected Files: " + str(file_name_list))
                for i, f in enumerate(file_name_list):
                    if i == 0:
                        self.center_all_images()
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

        if are_images_imported():
            cfg.IMAGES_IMPORTED = True
            self.generate_scales_button.setEnabled(True)
            img_size = get_image_size(
                cfg.data['data']['scales']['scale_1']['alignment_stack'][0]['images'][str(role_to_import)]['filename'])
            n_images = cfg.data.get_n_images()
            self.hud.post('%d Images Were Imported' % n_images)
            self.hud.post('Image dimensions: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')
            cfg.data.link_all_stacks()
            self.center_all_images()
            self.image_panel.update_multi_self()
            self.run_after_import()
            self.save_project()
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)
        
        self.set_idle()

    # 0527
    def load_images_in_role(self, role, file_names):
        logger.info('load_images_in_role:')
        '''Not clear if this has any effect. Needs refactoring.'''
        self.import_images(role, file_names, clear_role=True)
        self.center_all_images()
    
    @Slot()
    def remove_all_layers(self):
        logger.info("MainWindow.remove_all_layers:")
        local_cur_scale = cfg.data.get_scale()
        cfg.data['data']['current_layer'] = 0
        while len(cfg.data['data']['scales'][local_cur_scale]['alignment_stack']) > 0:
            cfg.data['data']['scales'][local_cur_scale]['alignment_stack'].pop(0)
        self.update_win_self()
    
    @Slot()
    def remove_all_panels(self):
        if 'image_panel' in dir(self):
            logger.info("Removing All Panels")
            self.image_panel.remove_all_panels()
        else:
            logger.warning("Image Panel Does Not Exist")
        self.update_win_self()
    
    @Slot()
    def actual_size_callback(self):
        logger.info('MainWindow.actual_size_callback:')
        self.all_images_actual_size()
    
    @Slot()
    def center_all_images(self, all_images_in_stack=True):
        '''NOTE: CALLS COULD BE REDUCED BY CENTERING ALL STACKS OF IMAGES NOT JUST CURRENT SCALE
        self.image_panel is a MultiImagePanel object'''
        calledby = inspect.stack()[1].function
        if calledby != 'resizeEvent':
            if calledby != 'main':
                logger.info("Called by " + calledby)
        self.image_panel.center_all_images(all_images_in_stack=all_images_in_stack)
        self.image_panel.update_multi_self()
    
    @Slot()
    def all_images_actual_size(self):
        logger.info("Actual-sizing all images.")
        self.image_panel.all_images_actual_size()

    @Slot()
    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent:")
        self.exit_app()

    @Slot()
    def exit_app(self):
        logger.info("MainWindow.exit_app:")
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

        self.threadpool.waitForDone(msecs=200)
        QApplication.quit()
        sys.exit()

    def documentation_view(self):  # documentationview
        self.hud.post("Switching to AlignEM_SWiFT Documentation")
        # don't force the reload, add home button instead
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
        self.main_widget.setCurrentIndex(1)

    def documentation_view_home(self):
        self.hud.post("Viewing AlignEM-SWiFT Documentation")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README.md'))

    def remote_view(self):
        self.hud.post("Switching to Remote Neuroglancer Server")
        self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.disableShortcuts()
        self.main_widget.setCurrentIndex(3)

    def reload_ng(self):
        logger.info("Reloading Neuroglancer Viewer")
        self.view_neuroglancer()

    def reload_remote(self):
        logger.info("Reloading Remote Neuroglancer Server")
        self.remote_view()

    def exit_ng(self):
        self.hud.post("Exiting Neuroglancer Viewer")
        self.image_panel_stack_widget.setCurrentIndex(0)  #0906
        new_layer = int(self.ng_worker.ng_viewer.state.voxel_coordinates[0])
        self.jump_to(new_layer)
        self.read_project_data_update_gui() #0908+
        self.center_all_images() #0908+
        self.main_widget.setCurrentIndex(0)
        self.initShortcuts()
        self.set_idle()

    def exit_docs(self):
        self.hud.post("Exiting Documentation")
        self.main_widget.setCurrentIndex(0)
        self.initShortcuts()
        self.set_idle()

    def exit_remote(self):
        self.hud.post("Exiting Remote Neuroglancer Server")
        self.main_widget.setCurrentIndex(0)
        self.initShortcuts()
        self.set_idle()

    def exit_demos(self):
        logger.info("Exiting demos...")
        self.main_widget.setCurrentIndex(0)
        self.initShortcuts()
        self.set_idle()

    def webgl2_test(self):
        '''https://www.khronos.org/files/webgl20-reference-guide.pdf'''
        logger.info("Running WebGL 2.0 Test In Web Browser...")
        self.browser_docs.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.main_widget.setCurrentIndex(2)

    def google(self):
        if not cfg.NO_NEUROGLANCER:
            logger.info("Running Google in Web Browser...")
            self.browser_docs.setUrl(QUrl('https://www.google.com'))
            self.main_widget.setCurrentIndex(2)

    def gpu_config(self):
        if not cfg.NO_NEUROGLANCER:
            logger.info("Running chrome://gpu in Web Browser...")
            self.browser_docs.setUrl(QUrl('chrome://gpu'))
            self.main_widget.setCurrentIndex(2)


    def print_state_ng(self):
        self.ng_worker.show_state()
        # logger.info("Viewer.url : ", self.ng_viewer.get_viewer_url)
        # logger.info("Viewer.screenshot : ", self.ng_viewer.screenshot)
        # logger.info("Viewer.txn : ", self.ng_viewer.txn)
        # logger.info("Viewer.actions : ", self.ng_viewer.actions)

    def print_url_ng(self):
        # print(ng.to_url(self.ng_viewer.state))
        self.ng_worker.show_url()
        # logger.info("\nURL : " + self.ng_viewer.get_viewer_url() + "\n")
        # logger.info("Viewer.url : ", self.ng_viewer.get_viewer_url)
        # logger.info("Viewer.screenshot : ", self.ng_viewer.screenshot)
        # logger.info("Viewer.txn : ", self.ng_viewer.txn)
        # logger.info("Viewer.actions : ", self.ng_viewer.actions)

    def blend_ng(self):
        logger.info("blend_ng():")

    def view_neuroglancer(self):  #view_3dem #ngview #neuroglancer
        if cfg.NO_NEUROGLANCER:
            self.hud.post('Neuroglancer Is Disabled', logging.WARNING)
            return
        self.set_status('Busy...')
        logger.info("view_neuroglancer >>>>")
        logger.info("# of aligned images                  : %d" % get_num_aligned())
        if not are_aligned_images_generated():
            self.hud.post('This scale must be aligned and exported before viewing in Neuroglancer')

            self.show_warning("No Alignment Found",
                         "This scale must be aligned and exported before viewing in Neuroglancer.\n\n"
                         "Typical workflow:\n"
                         "(1) Open a data or import images and save.\n"
                         "(2) Generate a set of scaled images and save.\n"
                         "--> (3) Align each scale starting with the coarsest."
                         )
            logger.info(
                "Warning | This scale must be aligned and exported before viewing in Neuroglancer - Returning")
            self.set_idle()
            return
        else:
            logger.info('Alignment at this scale exists - Continuing')

        # if not is_cur_scale_exported():
        #     self.hud.post('Alignment must be exported before it can be viewed in Neuroglancer')
        #
        #     self.show_warning("No Export Found",
        #                  "Alignment must be exported before it can be viewed in Neuroglancer.\n\n"
        #                  "Typical workflow:\n"
        #                  "(1) Open a data or import images and save.\n"
        #                  "(2) Generate a set of scaled images and save.\n"
        #                  "(3) Align each scale starting with the coarsest.\n"
        #                  "--> (4) Export alignment to Zarr format.\n"
        #                  "(5) View data in Neuroglancer client")
        #     logger.info(
        #         "WARNING | Alignment must be exported before it can be viewed in Neuroglancer - Returning")
        #     self.set_idle()
        #     return
        # else:
        #     logger.info('Exported alignment at this scale exists - Continuing')

        self.disableShortcuts()
        proj_path = os.path.abspath(cfg.data['data']['destination_path'])

        # if cfg.data.get_scale() != 'scale_1':
        #     s = 's' + str(get_scale_val(cfg.data.get_scale()))
        #     zarr_path = os.path.join(proj_path, '3dem.zarr', s) # view multiscale
        # else:
        #     zarr_path = os.path.join(proj_path, '3dem.zarr')  # view multiscale
        zarr_path = os.path.join(proj_path, '3dem.zarr')  # view multiscale

        self.hud.post("Loading Neuroglancer Viewer with '%s'" % zarr_path)
        self.ng_worker = View3DEM(source=zarr_path, scale=cfg.data.get_scale())
        self.threadpool.start(self.ng_worker)
        logger.info('viewer_url: %s' % self.ng_worker.url())
        self.browser.setUrl(QUrl(self.ng_worker.url()))
        self.image_panel_stack_widget.setCurrentIndex(1)
        self.hud.post('Displaying Alignment In Neuroglancer')
        self.set_idle()

    def set_main_view(self):
        self.initShortcuts()
        self.main_widget.setCurrentIndex(0)
        self.image_panel_stack_widget.setCurrentIndex(0)

    def show_splash(self):
        print('Initializing funky UI...')
        splash_pix = QPixmap('resources/em_guy.png')
        splash = QSplashScreen(self, splash_pix, Qt.WindowStaysOnTopHint)
        splash.setMask(splash_pix.mask())
        splash.show()

    def splash(self):
        self.funky_panel = QWidget()
        self.funky_layout = QVBoxLayout()
        pixmap = QPixmap('src/resources/fusiform-alignem-guy.png')
        label = QLabel(self)
        label.setPixmap(pixmap)
        # self.resize(pixmap.width(), pixmap.height())
        self.funky_layout.addWidget(label)
        self.funky_panel.setLayout(self.funky_layout)

    def run_after_import(self):
        # cfg.defaults_form.show()
        result = cfg.defaults_form.exec_() # result = 0 or 1
        if result:
            self.run_scaling_auto()
        else:
            logger.critical('Dialog Was Not Accepted - Will Not Scale At This Time')

    def view_k_img(self):
        logger.info('view_k_img:')
        self.w = KImageWindow(parent=self)
        self.w.show()

    def bounding_rect_changed_callback(self, state):
        if inspect.stack()[1].function == 'read_project_data_update_gui':
            return
        if state:
            self.hud.post('Bounding Box is ON. Warning: Dimensions may grow larger than the original images.')
            cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            self.hud.post('Bounding Box is OFF (faster). Dimensions will equal the original images.')
            cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def skip_changed_callback(self, state):  # 'state' is connected to skip toggle
        '''Callback Function for Skip Image Toggle'''
        self.hud.post("Keep Image Set To: %s" % str(state))
        if are_images_imported():
            s,l = cfg.data.get_scale(), cfg.data.get_layer()
            cfg.data['data']['scales'][s]['alignment_stack'][l]['skip'] = not state
            copy_skips_to_all_scales()
            cfg.data.link_all_stacks()
            self.center_all_images()


    def toggle_match_point_align(self):
        self.match_point_mode = not self.match_point_mode
        if self.match_point_mode:
            self.hud.post('Match Point Mode is now ON (Ctrl+M or ⌘+M to Toggle Match Point Mode)')
        else:
            self.hud.post('Match Point Mode is now OFF (Ctrl+M or ⌘+M to Toggle Match Point Mode)')

    def clear_match_points(self):
        logger.info('Clearing Match Points...')
        cfg.data.clear_match_points()
        self.image_panel.update_multi_self()

    def resizeEvent(self, event):
        self.resized.emit()
        return super(MainWindow, self).resizeEvent(event)

    @Slot()
    def pbar_set(self, x):
        self.pbar.setValue(int(x))
        if self.pbar.value() >= 99:
            self.pbar.setValue(0)

    def pbar_max(self, x):
        self.pbar.setMaximum(x)

    def pbar_update(self, x):
        self.pbar.setValue(x)

    def shake(self):
        try:
            start_layer = int(cfg.data['data']['current_layer'])
            for _ in range(6): self.change_layer_up()
            for _ in range(6): self.change_layer_down()
            cfg.data['data']['current_layer'] = start_layer
            self.read_project_data_update_gui()
            self.image_panel.update_multi_self()
        except:
            pass


    def disableShortcuts(self):
        '''Initialize Global Shortcuts'''
        pass
        logger.info('Disabling Global Shortcuts')
        # self.shortcut_prev_scale.setEnabled(False)
        # self.shortcut_next_scale.setEnabled(False)
        self.shortcut_layer_up.setEnabled(False)
        self.shortcut_layer_down.setEnabled(False)

    def initShortcuts(self):
        '''Initialize Global Shortcuts'''
        logger.info('Initializing Global Shortcuts')
        self.shortcut_prev_scale = QShortcut(QKeySequence(Qt.Key_Down), self)
        self.shortcut_next_scale = QShortcut(QKeySequence(Qt.Key_Up), self)
        self.shortcut_layer_up = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_layer_down = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_prev_scale.setEnabled(True)
        self.shortcut_next_scale.setEnabled(True)
        self.shortcut_layer_up.setEnabled(True)
        self.shortcut_layer_down.setEnabled(True)
        self.shortcut_prev_scale.activated.connect(self.prev_scale_button_callback)
        self.shortcut_next_scale.activated.connect(self.next_scale_button_callback)
        self.shortcut_layer_up.activated.connect(self.change_layer_up)
        self.shortcut_layer_down.activated.connect(self.change_layer_down)

    def initUI(self):

        gb_margin = (8, 20, 8, 5)
        cpanel_height = 120
        # cpanel_height = 230
        cpanel_1_dims = (260, cpanel_height)
        cpanel_2_dims = (260, cpanel_height)
        # cpanel_3_dims = (300, cpanel_height)
        cpanel_3_dims = (400, cpanel_height)
        cpanel_4_dims = (120, cpanel_height)
        # cpanel_5_dims = (240, cpanel_height)
        cpanel_5_dims = (90, cpanel_height)


        image_panel_min_height = 200

        std_height = int(22)
        std_width = int(96)
        std_button_size = QSize(std_width, std_height)
        square_button_height = int(30)
        square_button_width = int(72)
        square_button_size = QSize(square_button_width, square_button_height)
        std_input_size = int(56)
        small_input_size = int(36)
        small_button_size = QSize(int(46), std_height)


        '''-------- PANEL 1: PROJECT --------'''

        self.hud = HeadUpDisplay(self.app)
        self.hud.setObjectName('hud')
        self.hud.setContentsMargins(0, 0, 0, 0)
        # self.hud.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hud.post('You are aligning with AlignEM-SWiFT, please report newlybugs to joel@salk.edu',
                      logging.INFO)

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
        self.project_functions_layout.addWidget(self.new_project_button, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.open_project_button, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.save_project_button, 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.exit_app_button, 1, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.documentation_button, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.remote_viewer_button, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        '''-------- PANEL 2: data SELECTION & SCALING --------'''

        self.import_images_button = QPushButton(" Import\n Images")
        self.import_images_button.setToolTip('Import Images.')
        self.import_images_button.clicked.connect(self.import_images)
        self.import_images_button.setFixedSize(square_button_size)
        self.import_images_button.setIcon(qta.icon("fa5s.file-import", color=ICON_COLOR))
        self.import_images_button.setStyleSheet("font-size: 10px;")

        self.center_button = QPushButton('Center')
        self.center_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.center_button.setToolTip('Center all images.')
        self.center_button.clicked.connect(self.center_all_images)
        self.center_button.setFixedSize(square_button_width, std_height)
        self.center_button.setStyleSheet("font-size: 10px;")

        self.plot_snr_button = QPushButton("Plot SNR")
        self.plot_snr_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_snr_button.clicked.connect(self.show_snr_plot)
        self.plot_snr_button.setFixedSize(square_button_size)

        # self.set_defaults_button = QPushButton("Options")
        # self.set_defaults_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.set_defaults_button.clicked.connect(cfg.data.set_defaults)
        # self.set_defaults_button.setFixedSize(square_button_size)
        # self.set_defaults_button.setStyleSheet("font-size: 10px;")

        tip = 'Actual-size all images.'
        self.actual_size_button = QPushButton('Actual Size')
        self.actual_size_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.actual_size_button.setToolTip(tip)
        self.actual_size_button.clicked.connect(self.actual_size_callback)
        self.actual_size_button.setFixedSize(square_button_width, std_height)
        self.actual_size_button.setStyleSheet("font-size: 10px;")

        self.size_buttons_vlayout = QVBoxLayout()
        self.size_buttons_vlayout.addWidget(self.center_button)
        self.size_buttons_vlayout.addWidget(self.actual_size_button)

        self.generate_scales_button = QPushButton('Generate\nScales')
        self.generate_scales_button.setToolTip('Generate scale pyramid with chosen # of levels.')
        self.generate_scales_button.clicked.connect(self.run_scaling)
        self.generate_scales_button.setFixedSize(square_button_size)
        self.generate_scales_button.setStyleSheet("font-size: 10px;")
        self.generate_scales_button.setIcon(qta.icon("mdi.image-size-select-small", color=ICON_COLOR))
        self.generate_scales_button.setEnabled(False)

        self.clear_all_skips_button = QPushButton('Clear')
        self.clear_all_skips_button.setToolTip('Reset skips (keep all)')
        self.clear_all_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_all_skips_button.clicked.connect(self.clear_all_skips_callback)
        self.clear_all_skips_button.setFixedSize(small_button_size)
        # self.clear_all_skips_button.setIcon(qta.icon("mdi.undo", color=ICON_COLOR))

        tip = 'Use or skip current image?'
        self.toggle_skip = ToggleSwitch()
        self.toggle_skip.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_skip.setToolTip(tip)
        # self.toggle_skip.setChecked(True)  # 0816 #observed #sus #0907-
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
        self.jump_input.setToolTip(tip)
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.jump_input.setFixedSize(std_input_size, std_height)
        self.jump_validator = QIntValidator()
        self.jump_input.setValidator(self.jump_validator)
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer())

        self.toggle_reset_hlayout = QHBoxLayout()
        self.toggle_reset_hlayout.addWidget(self.clear_all_skips_button)
        self.toggle_reset_hlayout.addLayout(self.skip_layout)
        self.toggle_reset_hlayout.addWidget(self.jump_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toggle_reset_hlayout.addWidget(self.jump_input, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.scale_layout = QGridLayout()
        self.scale_layout.setContentsMargins(*gb_margin)  # tag23
        self.scale_layout.addWidget(self.import_images_button, 0, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addLayout(self.size_buttons_vlayout, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addWidget(self.generate_scales_button, 0, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addLayout(self.toggle_reset_hlayout, 1, 0, 1, 3)
        # self.scale_layout.addWidget(self.set_defaults_button, 2, 0)

        '''-------- PANEL 3: ALIGNMENT --------'''

        self.scales_combobox = QComboBox(self)
        self.scales_combobox.hide()
        # self.scales_combobox.addItems([skip_list])
        # self.scales_combobox.addItems(['--'])
        self.scales_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scales_combobox.setFixedSize(std_button_size)
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

        self.whitening_label = QLabel("Whitening:")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.textEdited.connect(self.has_unsaved_changes)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(std_input_size + 20 ) #0829
        self.whitening_input.setFixedHeight(std_height)
        self.whitening_input.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        self.whitening_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.whitening_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.whitening_grid = QGridLayout()
        self.whitening_grid.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.addWidget(self.whitening_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.swim_label = QLabel("SWIM Window:")
        self.swim_input = QLineEdit(self)
        self.swim_input.textEdited.connect(self.has_unsaved_changes)
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(std_input_size  + 20 ) #0829
        self.swim_input.setFixedHeight(std_height)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        self.swim_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.swim_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.swim_grid = QGridLayout()
        self.swim_grid.setContentsMargins(0, 0, 0, 0)
        self.swim_grid.addWidget(self.swim_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.apply_all_label = QLabel("Apply All:")
        self.apply_all_button = QPushButton()
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_label.setToolTip('Apply these settings to the entire data.')
        self.apply_all_button.setToolTip('Apply these settings to the entire data.')
        self.apply_all_button.clicked.connect(self.apply_all_callback)
        self.apply_all_button.setFixedSize(std_height, std_height)
        self.apply_all_button.setIcon(qta.icon("mdi.transfer", color=ICON_COLOR))

        self.apply_all_layout = QGridLayout()
        self.apply_all_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_all_layout.addWidget(self.apply_all_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.apply_all_layout.addWidget(self.apply_all_button, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.next_scale_button = QPushButton()
        self.next_scale_button.setStyleSheet("font-size: 10px;")
        self.next_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_scale_button.setToolTip('Go to the next scale.')
        self.next_scale_button.clicked.connect(self.next_scale_button_callback)
        self.next_scale_button.setFixedSize(std_height, std_height)
        self.next_scale_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.next_scale_button.setIcon(qta.icon("fa.arrow-up", color=ICON_COLOR))

        self.prev_scale_button = QPushButton()
        self.prev_scale_button.setStyleSheet("font-size: 10px;")
        self.prev_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_scale_button.setToolTip('Go to the previous scale.')
        self.prev_scale_button.clicked.connect(self.prev_scale_button_callback)
        self.prev_scale_button.setFixedSize(std_height, std_height)
        self.prev_scale_button.setIcon(qta.icon("fa.arrow-down", color=ICON_COLOR))

        self.layer_up_button = QPushButton()
        self.layer_up_button.setStyleSheet("font-size: 10px;")
        self.layer_up_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layer_up_button.setToolTip('Go to the next layer.')
        self.layer_up_button.clicked.connect(self.change_layer_up)
        self.layer_up_button.setFixedSize(std_height, std_height)
        self.layer_up_button.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        self.layer_down_button = QPushButton()
        self.layer_down_button.setStyleSheet("font-size: 10px;")
        self.layer_down_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layer_down_button.setToolTip('Go to the previous layer.')
        self.layer_down_button.clicked.connect(self.change_layer_down)
        self.layer_down_button.setFixedSize(std_height, std_height)
        self.layer_down_button.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        self.scale_selection_label = QLabel()
        self.scale_selection_label.setText("Scale ↕ Layer ↔")
        self.scale_layer_ctrls_layout = QGridLayout()
        self.scale_layer_ctrls_layout.addWidget(self.prev_scale_button, 1, 1)
        self.scale_layer_ctrls_layout.addWidget(self.next_scale_button, 0, 1)
        self.scale_layer_ctrls_layout.addWidget(self.layer_up_button, 1, 2)
        self.scale_layer_ctrls_layout.addWidget(self.layer_down_button, 1, 0)

        self.align_all_button = QPushButton(' Align')
        self.align_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_all_button.setToolTip('Align This Scale')
        self.align_all_button.clicked.connect(lambda: self.run_alignment(use_scale=cfg.data.get_scale()))
        self.align_all_button.setFixedSize(square_button_size)
        # self.align_all_button.setIcon(qta.icon("mdi.transfer", color=ICON_COLOR))
        # self.align_all_button.setIcon(qta.icon("ei.indent-left", color=ICON_COLOR))
        # self.align_all_button.setIcon(qta.icon("fa.navicon", color=ICON_COLOR))
        self.align_all_button.setIcon(qta.icon("fa.play", color=ICON_COLOR))

        # self.align_txt_layout = QGridLayout()
        # self.align_txt_layout.addWidget(self.align_label_resolution, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.align_txt_layout.addWidget(self.align_label_affine, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.align_txt_layout.addLayout(self.alignment_status_layout, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.align_txt_layout.addWidget(self.align_label_scales_remaining, 1, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.align_txt_layout.setContentsMargins(5, 5, 15, 5)

        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.auto_generate_label.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate = ToggleSwitch()  # toggleboundingrect
        self.toggle_auto_generate.stateChanged.connect(self.has_unsaved_changes)
        self.toggle_auto_generate.setToolTip('Automatically generate aligned images.')
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

        # self.align_txt_layout_tweak = QVBoxLayout()
        # self.align_txt_layout_tweak.setAlignment(Qt.AlignCenter)
        # self.align_line = QFrame()
        # self.align_line.setGeometry(QRect(60, 110, 751, 20))
        # self.align_line.setFrameShape(QFrame.HLine)
        # self.align_line.setFrameShadow(QFrame.Sunken)
        # self.align_line.setStyleSheet("""background-color: #455364;""")
        #
        # self.align_txt_layout_tweak.addWidget(self.align_line)
        # self.align_txt_layout_tweak.addLayout(self.align_txt_layout)
        # self.align_txt_layout_tweak.setContentsMargins(0, 10, 0, 0)
        # self.alignment_layout.addLayout(self.align_txt_layout_tweak, 3, 0, 1, 3)

        '''-------- PANEL 3.5: Post-alignment --------'''

        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension. This' \
              ' option is set at the coarsest scale, in order to form a contiguous dataset.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.null_bias_label = QLabel("Bias:")
        self.null_bias_label.setToolTip(wrapped)
        self.null_bias_combobox = QComboBox(self)
        self.null_bias_combobox.currentIndexChanged.connect(self.has_unsaved_changes)
        self.null_bias_combobox.setToolTip(wrapped)
        self.null_bias_combobox.setToolTip(wrapped)
        self.null_bias_combobox.addItems(['None', '0', '1', '2', '3', '4'])
        self.null_bias_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.null_bias_combobox.setFixedSize(72, std_height)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.poly_order_hlayout.addWidget(self.null_bias_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that ' \
              'are the same size as the source images but may have missing data, while turning this ON will ' \
              'result in no missing data but may significantly increase the size of the generated images.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.bounding_label = QLabel("Bounding Box:")
        self.bounding_label.setToolTip(wrapped)
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setToolTip(wrapped)
        self.toggle_bounding_rect.toggled.connect(self.bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignRight)

        tip = "Regenerate aligned with adjusted settings."
        self.regenerate_label = QLabel('Re-generate:')
        self.regenerate_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.regenerate_label.setToolTip(tip)
        self.regenerate_button = QPushButton()
        self.regenerate_button.setToolTip(tip)
        self.regenerate_button.setIcon(qta.icon("fa.recycle", color=ICON_COLOR))
        # self.regenerate_button.clicked.connect(self.run_regenerate_alignment)
        self.regenerate_button.clicked.connect(lambda: self.run_regenerate_alignment(use_scale=cfg.data.get_scale()))
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
        # self.postalignment_layout.addWidget(self.postalignment_note, 3, 0, alignment=Qt.AlignmentFlag.AlignBottom)

        # self.label_icon_navigation = QLabel(self)
        # self.navigation_pixmap = QPixmap('src/resources/icon_navigation3.png')
        # self.navigation_pixmap = self.navigation_pixmap.scaledToWidth(80, Qt.SmoothTransformation)
        # self.navigation_pixmap = self.navigation_pixmap.scaledToHeight(80, Qt.SmoothTransformation)
        # self.label_icon_navigation.setPixmap(self.navigation_pixmap)
        # self.resize(self.navigation_pixmap.width(), self.navigation_pixmap.height())
        # self.alignment_layout.addWidget(self.label_icon_navigation, 0, 3, 3, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        '''-------- PANEL 4: EXPORT & VIEW --------'''

        self.clevel_label = QLabel("clevel (1-9):")
        self.clevel_label.setToolTip("Zarr Compression Level\n(default=5)")
        self.clevel_input = QLineEdit(self)
        self.clevel_input.textEdited.connect(self.has_unsaved_changes)
        self.clevel_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clevel_input.setText("5")
        self.clevel_input.setFixedWidth(small_input_size)
        self.clevel_input.setFixedHeight(std_height)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)
        self.cname_label = QLabel("cname:")
        self.cname_label.setToolTip("Zarr Compression Type\n(default=zstd) ")
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setFixedSize(72, std_height)
        self.export_and_view_hbox = QHBoxLayout()
        self.export_zarr_button = QPushButton(" Remake\n Zarr")
        tip = "This function creates a scale pyramid from the full scale aligned images and then converts them " \
              "into the chunked and compressed multiscale Zarr format that can be viewed as a contiguous " \
              "volumetric dataset in Neuroglancer."
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.export_zarr_button.setToolTip(wrapped)
        self.export_zarr_button.clicked.connect(self.run_export)
        self.export_zarr_button.setFixedSize(square_button_size)
        self.export_zarr_button.setStyleSheet("font-size: 10px;")
        # self.export_zarr_button.setIcon(qta.icon("fa5s.file-export", color=ICON_COLOR))
        self.export_zarr_button.setIcon(qta.icon("fa5s.cubes", color=ICON_COLOR))

        self.ng_button = QPushButton("View In\nNeuroglancer")
        self.ng_button.setToolTip('View Zarr export in Neuroglancer.')
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

        '''-------- INTEGRATED CONTROL PANEL --------'''

        # PROJECT CONTROLS
        self.project_functions_groupbox = QGroupBox("Project")
        self.project_functions_groupbox_ = QGroupBox("Project")
        self.project_functions_groupbox.setLayout(self.project_functions_layout)
        self.project_functions_stack = QStackedWidget()
        self.project_functions_stack.setMinimumSize(*cpanel_1_dims)
        self.project_functions_stack.addWidget(self.project_functions_groupbox_)
        self.project_functions_stack.addWidget(self.project_functions_groupbox)
        self.project_functions_stack.setCurrentIndex(1)

        # SCALING & data SELECTION CONTROLS
        self.images_and_scaling_groupbox = QGroupBox("Data Selection && Scaling")
        self.images_and_scaling_groupbox_ = QGroupBox("Data Selection && Scaling")
        self.images_and_scaling_groupbox.setLayout(self.scale_layout)
        self.images_and_scaling_stack = QStackedWidget()
        self.images_and_scaling_stack.setMinimumSize(*cpanel_2_dims)
        self.images_and_scaling_stack.addWidget(self.images_and_scaling_groupbox_)
        self.images_and_scaling_stack.addWidget(self.images_and_scaling_groupbox)
        self.images_and_scaling_stack.setCurrentIndex(0)

        # ALIGNMENT CONTROLS
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

        # POST-ALIGNMENT CONTROLS
        self.postalignment_groupbox = QGroupBox("Adjust Output")
        self.postalignment_groupbox_ = QGroupBox("Adjust Output")
        self.postalignment_groupbox.setLayout(self.postalignment_layout)
        self.postalignment_stack = QStackedWidget()
        self.postalignment_stack.setMinimumSize(*cpanel_4_dims)
        self.postalignment_stack.addWidget(self.postalignment_groupbox_)
        self.postalignment_stack.addWidget(self.postalignment_groupbox)
        self.postalignment_stack.setCurrentIndex(0)

        # EXPORT & VIEW CONTROLS
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

        #details
        banner_stylesheet = """color: #ffe135; background-color: #000000; font-size: 14px;"""

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

        self.alignment_status_label.setToolTip('Alignment status')
        # self.al_status_checkbox = QRadioButton()
        self.al_status_checkbox = QCheckBox()
        self.al_status_checkbox.setStyleSheet("QCheckBox::indicator {border: 1px solid; border-color: #ffe135;}"
                                              "QCheckBox::indicator:checked {background-color: #ffe135;}")

        self.al_status_checkbox.setEnabled(False)
        self.al_status_checkbox.setToolTip('Alignment status')

        self.alignment_status_layout = QHBoxLayout()
        self.alignment_status_layout.addWidget(self.alignment_status_label)
        self.alignment_status_layout.addWidget(self.al_status_checkbox)

        self.details_banner = QWidget()
        self.details_banner.setContentsMargins(0, 0, 0, 0)
        self.details_banner.setFixedHeight(40)
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

        '''-------- MAIN LAYOUT --------'''

        self.image_panel = MultiImagePanel()
        self.image_panel.setFocusPolicy(Qt.StrongFocus)
        self.image_panel.setFocus()
        self.image_panel.draw_annotations = True
        # self.image_panel.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding) #0610
        # self.image_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_panel.setMinimumHeight(image_panel_min_height)

        self.image_panel_vlayout = QVBoxLayout()
        self.image_panel_vlayout.setSpacing(0)

        self.image_panel_vlayout.addWidget(self.details_banner)
        self.image_panel_vlayout.addWidget(self.image_panel)

        self.image_panel_widget = QWidget()
        self.image_panel_widget.setLayout(self.image_panel_vlayout)

        self.image_panel_stack_widget = QStackedWidget()
        self.image_panel_stack_widget.addWidget(self.image_panel_widget)

        # self.image_panel.zpw[2].ng_callback_button.clicked.connect(self.view_neuroglancer)

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
        self.plot_controls_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.plot_widget_layout = QHBoxLayout()
        self.plot_widget_layout.addWidget(self.snr_plot)
        self.plot_widget_layout.addLayout(self.plot_controls_layout)
        self.plot_widget_container = QWidget()
        self.plot_widget_container.setLayout(self.plot_widget_layout)

        self.python_console_back_button = QPushButton('Back')
        self.python_console_back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.python_console_back_button.clicked.connect(self.back_callback)
        self.python_console_back_button.setFixedSize(square_button_size)
        self.python_console_back_button.setAutoDefault(True)

        self.python_console_layout = QHBoxLayout()
        self.python_console_layout.addWidget(self.jupyter_console)
        self.python_console_widget_container = QWidget()
        self.python_console_widget_container.setLayout(self.python_console_layout)

        self.main_panel_bottom_widget = QStackedWidget()
        self.main_panel_bottom_widget.setContentsMargins(0, 0, 0, 0)
        self.main_panel_bottom_widget.addWidget(self.hud)
        self.main_panel_bottom_widget.addWidget(self.plot_widget_container)
        self.main_panel_bottom_widget.addWidget(self.python_console_widget_container)
        self.hud.setContentsMargins(0, 0, 0, 0) #0823
        self.plot_widget_container.setContentsMargins(0, 0, 0, 0) #0823
        self.python_console_widget_container.setContentsMargins(0, 0, 0, 0) #0823
        self.main_panel_bottom_widget.setCurrentIndex(0)

        '''MAIN SECONDARY CONTROL PANEL'''
        self.show_hud_button = QPushButton("Head-up\nDisplay")
        self.show_hud_button.setStyleSheet("font-size: 10px;")
        self.show_hud_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hud_button.clicked.connect(self.show_hud)
        self.show_hud_button.setFixedSize(square_button_size)
        self.show_hud_button.setIcon(qta.icon("mdi.monitor", color=ICON_COLOR))

        self.show_jupyter_console_button = QPushButton("Python\nConsole")
        self.show_jupyter_console_button.setStyleSheet("font-size: 10px;")
        self.show_jupyter_console_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_jupyter_console_button.clicked.connect(self.show_jupyter_console)
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

        # main_window.splitter.sizes() # Out[20]: [400, 216, 160]
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.splitterMoved.connect(self.center_all_images)
        self.splitter.setHandleWidth(4)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        # self.splitter.addWidget(self.image_panel_widget)
        self.splitter.addWidget(self.image_panel_stack_widget)
        self.splitter.addWidget(self.lower_panel_groups)
        self.splitter.addWidget(self.bottom_display_area_widget)

        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 2)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.splitter.setCollapsible(2, True)

        self.main_panel = QWidget()
        self.main_panel_layout = QGridLayout()
        self.main_panel_layout.setContentsMargins(0,0,0,0)
        # self.main_panel_layout.setSpacing(2) # inherits downward
        self.main_panel_layout.addWidget(self.splitter, 1, 0)

        '''-------- AUXILIARY PANELS --------'''

        # PROJECT VIEW PANEL
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

        # DOCUMENTATION PANEL
        if not cfg.NO_NEUROGLANCER:
            self.browser = QWebEngineView()
            self.browser_docs = QWebEngineView()
        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(std_button_size)
        self.exit_docs_button.clicked.connect(self.exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(std_button_size)
        self.readme_button.clicked.connect(self.documentation_view_home)
        self.docs_panel = QWidget()
        self.docs_panel_layout = QVBoxLayout()
        if not cfg.NO_NEUROGLANCER:
            self.docs_panel_layout.addWidget(self.browser_docs)
        self.docs_panel_controls_layout = QHBoxLayout()
        self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.docs_panel_controls_layout.addWidget(self.readme_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.docs_panel_controls_layout.addSpacerItem(self.spacer_item_docs)
        self.docs_panel_layout.addLayout(self.docs_panel_controls_layout)
        self.docs_panel.setLayout(self.docs_panel_layout)

        # REMOTE VIEWER PANEL
        if not cfg.NO_NEUROGLANCER:
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
        if not cfg.NO_NEUROGLANCER:
            self.remote_viewer_panel_layout.addWidget(self.browser_remote)
        self.remote_viewer_panel_controls_layout = QHBoxLayout()
        self.remote_viewer_panel_controls_layout.addWidget(self.exit_remote_button,
                                                           alignment=Qt.AlignmentFlag.AlignLeft)
        self.remote_viewer_panel_controls_layout.addWidget(self.reload_remote_button,
                                                           alignment=Qt.AlignmentFlag.AlignLeft)
        # self.spacer_item_remote_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) #0610
        self.spacer_item_remote_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.remote_viewer_panel_controls_layout.addSpacerItem(self.spacer_item_remote_panel)
        self.remote_viewer_panel_layout.addLayout(self.remote_viewer_panel_controls_layout)
        self.remote_viewer_panel.setLayout(self.remote_viewer_panel_layout)

        # DEMOS PANEL
        self.exit_demos_button = QPushButton("Back")
        self.exit_demos_button.setFixedSize(std_button_size)
        self.exit_demos_button.clicked.connect(self.exit_demos)
        self.demos_panel = QWidget()  # create QWidget()
        self.demos_panel_layout = QVBoxLayout()  # create QVBoxLayout()
        self.demos_panel_controls_layout = QHBoxLayout()
        self.demos_panel_controls_layout.addWidget(self.exit_demos_button)  # go back button
        self.demos_panel_layout.addLayout(self.demos_panel_controls_layout)  # add horizontal layout
        self.demos_panel.setLayout(self.demos_panel_layout)  # set layout
        # self.demos_panel_layout.addWidget(self.browser)            # add widgets

        # NEUROGLANCER CONTROLS PANEL
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
        self.ng_panel_layout.addWidget(self.browser)
        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)
        self.ng_panel.setLayout(self.ng_panel_layout)

        self.image_panel_stack_widget.addWidget(self.ng_panel)  #0906

        self.splash() #0816 refactor

        self.main_widget = QStackedWidget(self)
        self.main_widget.addWidget(self.main_panel)                 # (0) main_panel
        # self.main_widget.addWidget(self.ng_panel)                   # (1) ng_panel
        self.main_widget.addWidget(self.docs_panel)                 # (2) docs_panel
        self.main_widget.addWidget(self.demos_panel)                # (3) demos_panel
        self.main_widget.addWidget(self.remote_viewer_panel)        # (4) remote_viewer_panel
        self.main_widget.addWidget(self.project_view_panel)         # (5) self.project_view
        self.main_widget.addWidget(self.funky_panel)                # (6) self.funky_panel
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






