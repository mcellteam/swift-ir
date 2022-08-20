#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os, sys, copy, json, inspect, multiprocessing, logging, textwrap, psutil, operator, platform
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QSpacerItem, QMenu, QMessageBox, \
    QComboBox, QGroupBox, QScrollArea, QToolButton, QSplitter, QRadioButton, QFrame, QTreeView, QHeaderView, \
    QDockWidget, QSplashScreen
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QGuiApplication
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, QRect
from qtpy.QtWidgets import QAction, QActionGroup
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWebEngineCore import *
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
# from qtconsole.rich_jupyter_widget import RichJupyterWidget
# from qtconsole.inprocess import QtInProcessKernelManager
# from qtconsole.manager import QtKernelManager
import qtawesome as qta
import pyqtgraph as pg
import neuroglancer as ng
from PIL import Image
import alignEM.config as cfg
from alignEM.em_utils import *
from alignEM.data_model import DataModel
from alignEM.image_utils import get_image_size
from alignEM.compute_affines import compute_affines
from alignEM.apply_affines import generate_aligned
from alignEM.generate_scales import generate_scales
from alignEM.generate_zarr import generate_zarr
from alignEM.view_3dem import View3DEM
from .head_up_display import HeadUpDisplay
from .image_library import ImageLibrary, SmartImageLibrary
from .multi_image_panel import MultiImagePanel
from .toggle_switch import ToggleSwitch
from .json_treeview import JsonModel
from .defaults_form import DefaultsForm
from .collapsible_box import CollapsibleBox
from .screenshot_saver import ScreenshotSaver
from .kimage_window import KImageWindow
from .snr_plot import SnrPlot
from .jupyter_console import JupyterConsole

__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

# app = None #0816-


class MainWindow(QMainWindow):
    def __init__(self, title="AlignEM-SWiFT"):

        app = QApplication.instance()
        self.app = QApplication.instance()
        if app is None:
            logger.info("Warning | 'app' was None. Creating new instance.")
            app = QApplication([])

        logger.info('initializing QMainWindow.__init__(self)')
        QMainWindow.__init__(self)
        cfg.defaults_form = DefaultsForm(parent=self)
        self.jupyter_console = JupyterConsole()
        app.aboutToQuit.connect(self.shutdown_jupyter_kernel)

        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(QPixmap('sims.png')))
        self.init_dir = os.getcwd()
        fg = self.frameGeometry()
        cp = QGuiApplication.primaryScreen().availableGeometry().center()
        fg.moveCenter(cp)
        self.move(fg.topLeft())
        logger.info('Center Point of primary monitor: %s' % str(cp))
        logger.info('Frame Geometry: %s' % str(fg))
        logger.info("Initializing Thread Pool..")
        self.threadpool = QThreadPool(self)  # important consideration is this 'self' reference
        cfg.project_data = DataModel()
        cfg.image_library = ImageLibrary()
        # cfg.image_library = SmartImageLibrary()
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

        
        # if cfg.QT_API == 'pyside6':
        #     logger.info("QImageReader.allocationLimit() WAS " + str(QImageReader.allocationLimit()) + "MB")
        #     QImageReader.setAllocationLimit(4000) #pyside6 #0610setAllocationLimit
        #     logger.info("New QImageReader.allocationLimit() NOW IS " + str(QImageReader.allocationLimit()) + "MB")

        print(os.getcwd())
        self.main_stylesheet = 'alignEM/styles/stylesheet1.qss'
        self.setStyleSheet(open(self.main_stylesheet).read()) # must be after QMainWindow.__init__(self)
        
        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())
        multiprocessing.set_start_method('fork', force=True)
        
        self.project_progress = 0
        self.project_aligned_scales = []
        self.scales_combobox_switch = 0
        self.jump_to_worst_ticker = 1  # begin iter at 1 to skip first image (has no ref)
        self.jump_to_best_ticker = 0
        self.always_generate_images = True
        
        # self.std_height = int(22)
        self.std_height = int(24)
        self.std_width = int(96)
        self.std_button_size = QSize(self.std_width, self.std_height)
        self.square_button_height = int(30)
        self.square_button_width = int(72)
        self.square_button_size = QSize(self.square_button_width, self.square_button_height)
        self.std_input_size = int(56)
        self.std_input_size_small = int(36)
        
        # titlebar resource
        # https://stackoverflow.com/questions/44241612/custom-titlebar-with-frame-in-pyqt5
        
        # pyside6 port needed to replace deprecated the 'defaultSettings()' attribute of QWebEngineSettings
        # self.web_settings = QWebEngineSettings.defaultSettings()
        # self.web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        
        # pyside6 ONLY
        logger.info("instantiating QWebEngineView()")
        if cfg.USES_PYSIDE:
            self.view = QWebEngineView()
        if cfg.QT_API == 'pyqt6':
            self.view = QWebEngineView()
        # PySide6 available options
        # self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        logger.info("Setting QWebEngineSettings.LocalContentCanAccessRemoteUrls to True")
        if cfg.USES_QT6:
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        self.up = 0

        # def changeEvent(self, event):
        #     if event.type() == event.WindowStateChange:
        #         self.titleBar.windowStateChanged(self.windowState())
        # def resizeEvent(self, event):
        #     self.titleBar.resize(self.width(), self.titleBar.height())

        # self.browser.setPage(CustomWebEnginePage(self)) # Or else clicked links will never open new window.
        
        self.draw_border = False
        self.draw_annotations = True

        self.panel_list = []

        self.inspector_label_skips = QLabel()
        
        self.project_inspector = QDockWidget("Project Inspector")
        self.project_inspector.setMinimumWidth(160)
        self.project_inspector.hide()
        self.addDockWidget(Qt.RightDockWidgetArea, self.project_inspector)
        # if cfg.QT_API == 'pyside':
        #     self.addDockWidget(alignEM.RightDockWidgetArea, self.project_inspector)
        # # elif cfg.QT_API == 'pyqt':
        # #     # self.project_inspector.setAllowedAreas() # ? there is no reference on how to do this
        
        scroll = QScrollArea()
        self.project_inspector.setWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        dock_vlayout = QVBoxLayout(content)
        self.inspector_scales = CollapsibleBox('Skip List')
        dock_vlayout.addWidget(self.inspector_scales)
        lay = QVBoxLayout()
        self.inspector_label_skips.setStyleSheet("color: #d3dae3; border-radius: 12px;")
        lay.addWidget(self.inspector_label_skips, alignment=Qt.AlignTop)
        self.inspector_scales.setContentLayout(lay)
        self.inspector_cpu = CollapsibleBox('CPU Specs')
        dock_vlayout.addWidget(self.inspector_cpu)
        lay = QVBoxLayout()
        label = QLabel("CPU #: %s\nSystem : %s" % (psutil.cpu_count(logical=False), platform.system()))
        label.setStyleSheet("color: #d3dae3; border-radius: 12px;")
        lay.addWidget(label, alignment=Qt.AlignTop)
        self.inspector_cpu.setContentLayout(lay)
        dock_vlayout.addStretch()

        self.match_point_mode = False

        '''Initialize UI'''
        self.initUI()

        '''Initialize Status Bar'''
        self.status = self.statusBar()
        self.set_idle()
        
        '''Initialize Menu'''
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # fix to set non-native menubar in macOS



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
                 ['&Configure Project Options', 'Ctrl+C', self.settings, None, None, None],
                 ['Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None],
                 ['View Project JSON', 'Ctrl+J', self.project_view_callback, None, None, None],
                 ['Show/Hide Project Inspector', None, self.show_hide_project_inspector, None, None, None],
                 ['Show Console', None, self.show_jupyter_console, None, None, None],
                 ['Remote Neuroglancer Server', None, self.remote_view, None, None, None],
                 ['initUI', None, self.initUI, None, None, None],
                 ['Show Splash', None, self.show_splash, None, None, None],
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
                      ['Clear Match Points', None, self.clear_match_points, None, None, None],

                  ]
                  ],
                 ['Plot SNRs', None, self.show_snr_plot, None, None, None],
                 ['Go To Next Worst SNR', None, self.jump_to_worst_snr, None, None, None],
                 ['Go To Next Best SNR', None, self.jump_to_best_snr, None, None, None],
                 ['Apply Project Defaults', None, set_default_settings, None, None, None],
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
                 ['Stylesheets',
                  [
                      ['Style #1 - Joel Style', None, self.apply_stylesheet_1, None, None, None],
                      # ['Style #2 - Light2', None, self.apply_stylesheet_2, None, None, None],
                      ['Style #3 - Light3', None, self.apply_stylesheet_3, None, None, None],
                      ['Style #4 - Grey', None, self.apply_stylesheet_4, None, None, None],
                      ['Style #11 - Screamin Green', None, self.apply_stylesheet_11, None, None, None],
                      ['Style #12 - Dark12', None, self.apply_stylesheet_12, None, None, None],
                      ['Minimal', None, self.minimal_stylesheet, None, None, None],

                  ]
                ],
                 ['&Python Console', 'Ctrl+P', self.show_jupyter_console, None, None, None],

             ]
             ],
            ['&Debug',
             [
                 # ['Launch Debugger', None, self.launch_debugger, None, None, None],
                 ['Auto Set User Progress', None, self.auto_set_user_progress, None, None, None],
                 ['Update Win Self (Update MainWindow)', None, self.update_win_self, None, None, None],
                 ['Refresh All Images (Repaint+Update Panels)', None, self.refresh_all_images, None, None, None],
                 ['Read project_data Update GUI', None, self.read_project_data_update_gui, None, None, None],
                 ['Read GUI Update project_data', None, self.read_gui_update_project_data, None, None, None],
                 ['Link Images Stacks', None, cfg.project_data.link_all_stacks, None, None, None],
                 ['Reload Scales Combobox', None, self.reload_scales_combobox, None, None, None],
                 ['Update Project Inspector', None, self.update_project_inspector, None, None, None],
                 ['Update Alignment Details', None, self.update_alignment_details, None, None, None],
                 ['Update Scale Controls', None, self.update_scale_controls, None, None, None],
                 ['Print Sanity Check', None, print_sanity_check, None, None, None],
                 ['Print Project Tree', None, print_project_tree, None, None, None],
                 ['Print Image Library', None, self.print_image_library, None, None, None],
                 ['Print Aligned Scales List', None, get_aligned_scales_list, None, None, None],
                 ['Print Single Alignment Layer', None, print_alignment_layer, None, None, None],
                 ['Print SNR List', None, print_snr_list, None, None, None],
                 ['Print .dat Files', None, print_dat_files, None, None, None],
                 ['Print Working Directory', None, print_path, None, None, None],
                 ['Google', None, self.google, None, None, None],
                 ['about:config', None, self.about_config, None, None, None],
                 ['chrome://gpu', None, self.gpu_config, None, None, None],
                 ['Test Web GL2.0', None, self.webgl2_test, None, None, None],
             ]
             ],
        ]
        self.build_menu_from_list(self.menu, ml)
    
    def build_menu_from_list(self, parent, menu_list):
        # Get the group names first
        for item in menu_list:
            if type(item[1]) == type([]):
                # This is a submenu
                pass
            else:
                # This is a menu item (action) or a separator
                if item[4] != None:
                    # This is a group name so add it as needed
                    if not (item[4] in self.action_groups):
                        # This is a new group:
                        self.action_groups[item[4]] = QActionGroup(self)
        
        for item in menu_list:
            if type(item[1]) == type([]):
                '''This is a sub-menu'''
                sub = parent.addMenu(item[0])
                self.build_menu_from_list(sub, item[1])
            else:
                '''This is a menu item (action) or a separator'''
                if item[0] == '-':
                    parent.addSeparator() # This is a separator
                else:
                    # This is a menu item (action) with name, accel, callback
                    action = QAction(item[0], self)
                    if item[1] != None:
                        action.setShortcut(item[1])
                    if item[2] != None:
                        action.triggered.connect(item[2])
                        if item[2] == self.not_yet:
                            action.setDisabled(True)
                    if item[3] != None:
                        action.setCheckable(True)
                        action.setChecked(item[3])
                    if item[4] != None:
                        self.action_groups[item[4]].addAction(action)
                    
                    parent.addAction(action)


    # def make_jupyter_widget_with_kernel(self):
    #     """Start a kernel, connect to it, and create a RichJupyterWidget to use it. Doc:
    #     https://qtconsole.readthedocs.io/en/stable/
    #     """
    #     # Create an in-process kernel
    #     # self.kernel_manager = QtInProcessKernelManager()
    #     # self.kernel_manager.start_kernel(show_banner=False)
    #     # self.kernel = self.kernel_manager.kernel
    #     # self.kernel.gui = 'qt'
    #     # kernel.shell.push({'x': 0, 'y': 1, 'z': 2})
    #     # project_data = cfg.project_data #notr sure why this dictionary does not push
    #     # self.kernel.shell.push(project_data)
    #     # self.kernel.shell.
    #     # self.kernel_client = self.kernel_manager.client()
    #     # self.kernel_client.start_channels()
    #     # self.jupyter_widget = RichJupyterWidget()
    #
    #     # self.jupyter_widget.execute_command('ls')
    #     # self.jupyter_widget.banner = ''
    #     # self.jupyter_widget.set_default_style(colors='linux')
    #     # self.jupyter_widget.prompt_to_top()
    #     # self.jupyter_widget.kernel_manager = self.kernel_manager
    #     # self.jupyter_widget.kernel_client = self.kernel_client
    #     return self.jupyter_widget

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
        self.project_model.load(cfg.project_data.to_dict())
        self.project_view.show()
        self.main_widget.setCurrentIndex(5)
        # 0718
    
    @Slot()
    def run_scaling(self) -> None:
        logger.info("run_scaling:")
        self.set_status("Scaling...")
        self.hud.post('Requesting scale factors from user')


        self.save_project() #0804+

        default_scales = []
        if is_dataset_scaled():
            default_scales = [str(v) for v in
                              sorted([get_scale_val(s) for s in cfg.project_data['data']['scales'].keys()])]
        else:
            default_scales = ['1']
        input_val, ok = QInputDialog().getText(None, "Define Scales",
                                               "Please enter your scaling factors separated by spaces." \
                                               "\n\nFor example, to generate 1x 2x and 4x scale datasets: 1 2 4\n\n"
                                               "Your current scales: " + str(' '.join(default_scales)),
                                               echo=QLineEdit.Normal,
                                               text=' '.join(default_scales))
        
        if not ok:
            logger.info("User did not select OK - Canceling")
            self.hud.post('User did not select OK - Canceling')
            self.set_idle()
            logger.info('<<<< run_scaling')
            return
        
        if input_val == '':
            self.hud.post('Input was empty, please provide scaling factors')
            self.set_idle()
            logger.info('<<<< run_scaling')
            return
        cfg.main_window.hud.post('Generating Scale Image Hierarchy...')
        set_scales_from_string(input_val)
        self.hud.post('Scale image hierarchy will have these scale levels: %s' % input_val)
        self.show_hud()
        try:
            generate_scales()  # <-- CALL TO generate_scales
        except:
            print_exception()
            self.hud.post('Generating Scales Triggered an Exception - Returning', logging.ERROR)

        cfg.project_data.link_all_stacks()
        set_default_settings()
        cfg.project_data['data']['current_scale'] = get_scales_list()[-1]
        self.read_project_data_update_gui()
        self.set_progress_stage_2()
        self.reload_scales_combobox()  # 0529 #0713+

        # TODO: Get rid of this as soon as possible !
        logger.info("Current scales combobox index: %s" % str(cfg.main_window.scales_combobox.currentIndex()))
        self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
        logger.info("New current scales combobox index: %s" % str(cfg.main_window.scales_combobox.currentIndex()))
        # AllItems = [self.scales_combobox.itemText(i) for i in range(self.scales_combobox.count())]
        
        self.update_scale_controls()
        self.center_all_images()
        self.update_win_self()
        self.save_project()
        print('Project Structure:')
        print_project_tree()
        self.hud.post('Scaling Complete.')
        self.set_idle()
        logger.info('\nScaling Complete.\n')
    
    @Slot()
    def run_alignment(self) -> None:
        logger.info('run_alignment:')
        self.read_gui_update_project_data()
        if not is_cur_scale_ready_for_alignment():
            error_msg = "Scale %s must be aligned first!" % get_next_coarsest_scale_key()[-1]
            cfg.main_window.hud.post(error_msg, logging.WARNING)
            return
        self.status.showMessage('Aligning...')
        self.show_hud()
        try:
            compute_affines(use_scale=get_cur_scale_key(), start_layer=0, num_layers=-1)
        except:
            print_exception()
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)
        
        if not is_cur_scale_aligned():
            self.hud.post('Current Scale Was Not Aligned.', logging.ERROR)
            self.set_idle()
            return
        self.update_alignment_details()
        self.hud.post('Alignment Complete.')
        
        if self.always_generate_images:
            self.set_busy()
            try:
                generate_aligned(
                    use_scale=get_cur_scale_key(),
                    start_layer=0,
                    num_layers=-1
                )
            except:
                print_exception()
                self.hud.post('Something Went Wrong During Image Generation.', logging.ERROR)
                self.set_idle()
                return
            
            if are_aligned_images_generated():
                self.set_progress_stage_3()
                self.center_all_images()

                if self.main_panel_bottom_widget.currentIndex() == 1:
                   self.show_snr_plot()
                
                self.hud.post('Image Generation Complete')
                logger.info('\n\nImage Generation Complete\n')
            else:
                self.hud.post('Alignment Succeeded, but Image Generation Failed. Try Re-generating the Images.',
                              logging.ERROR)
            self.update_win_self()
            self.refresh_all_images()
            self.update_panels()  # 0721+
            self.set_idle()
    
    @Slot()
    def run_regenerate_alignment(self) -> None:
        logger.info('run_regenerate_alignment:')
        self.read_gui_update_project_data()
        if not is_cur_scale_aligned():
            self.hud.post('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING)
            self.set_idle()
            return
        self.status.showMessage('Busy...')
        try:
            generate_aligned(
                use_scale=get_cur_scale_key(),
                start_layer=0,
                num_layers=-1
            )
        except:
            print_exception()
            self.hud.post('Something Went Wrong During ImageGeneration.', logging.ERROR)
            self.set_idle()
            return
        
        if are_aligned_images_generated():
            logger.info('are_aligned_images_generated() returned True. Setting user progress to stage 3...')
            self.set_progress_stage_3()
            cfg.main_window.image_panel.zpw[2].setFocus()
            self.image_panel.center_all_images()
            # self.next_scale_button_callback()
            # self.prev_scale_button_callback()
            # cur_layer = get_cur_layer()
            # self.jump_to_layer(-1)
            # self.jump_to_layer(cur_layer)
            # self.center_all_images()
            # self.read_project_data_update_gui()
            # self.update_win_self()
            self.image_panel.all_images_actual_size()
            self.image_panel.center_all_images()
            self.update_panels()  # 0721+
            self.center_all_images()
            self.hud.post("Regenerate Complete")
            logger.info('\n\nRegenerate Complete\n')
        else:
            self.hud.post('Image Generation Failed Unexpectedly. Try Re-aligning First.', logging.ERROR)
        self.update_win_self()
        self.set_idle()

    
    def export_zarr(self):
        logger.info('Exporting to Zarr format...')
        if not are_aligned_images_generated():
            self.hud.post('Current Scale Must be Aligned Before It Can be Exported', logging.WARNING)
            logger.debug(
                '  export_zarr() | (!) There is no alignment at this scale to export. Returning from export_zarr().')
            self.show_warning('No Alignment', 'There is no alignment to export.\n\n'
                                         'Typical workflow:\n'
                                         '(1) Open a project or import images and save.\n'
                                         '(2) Generate a set of scaled images and save.\n'
                                         '--> (3) Align each scale starting with the coarsest.\n'
                                         '(4) Export alignment to Zarr format.\n'
                                         '(5) View data in Neuroglancer client')
            self.set_idle()
            return
        
        self.set_status('Exporting...')
        src = os.path.abspath(cfg.project_data['data']['destination_path'])
        out = os.path.abspath(os.path.join(src, '3dem.zarr'))
        # generate_zarr(src=src, out=out)
        generate_zarr(src=src, out=out)

        self.clevel = str(self.clevel_input.text())
        self.cname = str(self.cname_combobox.currentText())
        self.n_scales = str(self.n_scales_input.text())
        logger.info("clevel='%s'  cname='%s'  n_scales='%s'" % (self.clevel, self.cname, self.n_scales))

        self.set_idle()
        self.hud.post('Zarr Export Complete')

    @Slot()
    def clear_all_skips_callback(self):
        self.set_busy()
        reply = QMessageBox.question(self,
                                     'Verify Reset Skips',
                                     'Verify reset skips? This will make all images unskipped.',
                                     QMessageBox.Cancel | QMessageBox.Ok)
        if reply == QMessageBox.Ok:
            try:
                self.hud.post('Resetting Skips...')
                clear_all_skips()
            except:
                print_exception()
                self.hud.post('Something Went Wrong', logging.WARNING)
        self.hud.post('Done')
        self.set_idle()
    
    def update_win_self(self):
        logger.debug("update_win_self (called by %s):" % inspect.stack()[1].function)
        # self.center_all_images()  # uncommenting causes centering issues to re-emerge
        self.update()  # repaint
    
    @Slot()
    def apply_all_callback(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        swim_val = self.get_swim_input()
        whitening_val = self.get_whitening_input()
        scales_dict = cfg.project_data['data']['scales']
        self.hud.post('Applying these alignment settings to project...')
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
        if self.project_progress >= 2:
            
            if get_num_scales() == 1:
                self.next_scale_button.hide()
                self.prev_scale_button.hide()
                self.align_all_button.setEnabled(True)
                try:
                    self.update_alignment_details()
                except:
                    logger.warning('Calling update_alignment_details() triggered an exception')

            else:
                try:
                    n_scales = get_num_scales()
                    cur_index = self.scales_combobox.currentIndex()
                    if cur_index == 0:
                        self.next_scale_button.hide()
                        self.prev_scale_button.show()
                    elif n_scales == cur_index + 1:
                        self.next_scale_button.show()
                        self.prev_scale_button.hide()
                    else:
                        self.next_scale_button.show()
                        self.prev_scale_button.show()
                except:
                    print_exception()
                    logger.warning('Something went wrong updating visibility state of controls')
                
                try:
                    self.align_all_button.setEnabled(is_cur_scale_ready_for_alignment())
                except:
                    logger.warning('Something went wrong enabling/disabling align all button')
                
                
                
            try:
                self.jump_validator = QIntValidator(0, get_num_imported_images())
            except:
                logger.warning('Something went wrong setting validator on jump_input')
            try:
                self.update_alignment_details()
            except:
                logger.warning('Calling update_alignment_details() triggered an exception')
    
    @Slot()
    def update_alignment_details(self) -> None:
        '''Update alignment details in the Alignment control panel group box.'''
        logger.debug('update_alignment_details >>>>')
        al_stack = cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack']
        self.alignment_status_checkbox.setChecked(is_cur_scale_aligned())
        # if is_cur_scale_aligned():
        self.alignment_status_checkbox.show()
        self.alignment_status_label.show()
        self.align_label_resolution.show()
        self.align_label_affine.show()
        self.align_label_scales_remaining.show()
        dm_name_to_combo_name = {'init_affine'  : 'Initialize Affine',
                                 'refine_affine': 'Refine Affine',
                                 'apply_affine' : 'Apply Affine'}
        img_size = get_image_size(al_stack[0]['images']['base']['filename'])
        alignment_method_string = dm_name_to_combo_name[cfg.project_data['data']['scales'][get_cur_scale_key()][
            'method_data']['alignment_option']]
        
        self.alignment_status_label.setText("Is Aligned: ")
        self.align_label_resolution.setText('%sx%spx' % (img_size[0], img_size[1]))
        self.align_label_affine.setText(alignment_method_string)
        self.align_label_scales_remaining.setText('# Scales Unaligned: %d' % len(get_not_aligned_scales_list()))
        # else:
        #     # self.alignment_status_label.hide()
        #     # self.align_label_resolution.hide()
        #     # self.align_label_affine.hide()
        #     # self.align_label_scales_remaining.hide()
        #     logger.info('update_alignment_details | WARNING | Function was called but current scale is not aligned')
    
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
        '''Callback function for the Next Scale button (scales combobox may not be visible but controls the current scale).'''
        try:
            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index - 1
            self.scales_combobox.setCurrentIndex(requested_index)
            self.read_project_data_update_gui()
            self.update_scale_controls()
            if not is_cur_scale_ready_for_alignment():
                cfg.main_window.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
            if self.main_panel_bottom_widget.currentIndex() == 1:
                self.plot_widget.clear()
                self.show_snr_plot()
        except:
            print_exception()
        finally:
            self.scales_combobox_switch = 0
    
    @Slot()
    def prev_scale_button_callback(self) -> None:
        '''Callback function for the Previous Scale button (scales combobox may not be visible but controls the current scale).'''
        try:
            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index + 1
            self.scales_combobox.setCurrentIndex(requested_index)  # commence the scale change
            self.read_project_data_update_gui()
            self.update_scale_controls()
            if not is_cur_scale_ready_for_alignment():
                cfg.main_window.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
            if self.main_panel_bottom_widget.currentIndex() == 1:
                self.plot_widget.clear()
                self.show_snr_plot()
        except:
            print_exception()
        finally:
            self.scales_combobox_switch = 0
    
    @Slot()
    def show_snr_plot(self):
        if not are_images_imported():
            self.hud.post('No SNRs To View. Images Have Not Even Been Imported Yet.', logging.WARNING)
            self.back_callback()
            return
        if not is_cur_scale_aligned():
            self.hud.post('No SNRs To View. Current Scale Is Not Aligned Yet.', logging.WARNING)
            self.back_callback()
            return
        snr_list = get_snr_list()
        max_snr = max(snr_list)
        x_axis = [x for x in range(0, len(snr_list))]

        # pen = pg.mkPen(color=(255, 0, 0), width=5, style=Qt.SolidLine)
        pen = pg.mkPen(color=(0, 0, 0), width=5, style=Qt.SolidLine)
        styles = {'color': '#ffffff', 'font-size': '13px'}
        # self.plot_widget.setXRange(0, get_num_imported_images())
        # self.plot_widget.setBackground(QColor(100, 50, 254, 25))
        # self.snr_points = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(30, 255, 35, 255), hoverSize=14)
        self.snr_points = pg.ScatterPlotItem(
            size=9,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(30, 255, 35, 255),
            # hoverable=True,
            # hoverSymbol='s',
            hoverSize=12,
            # hoverPen=pg.mkPen('r', width=2),
            hoverBrush=pg.mkBrush('g'),
        )
        self.snr_points.sigClicked.connect(self.onSnrClick)
        self.snr_points.addPoints(x_axis[1:], snr_list[1:])

        self.last_snr_click = []

        font = QFont()
        font.setPixelSize(12)
        self.snr_plot.getAxis("bottom").setStyle(tickFont=font)
        self.snr_plot.getAxis("bottom").setHeight(26)
        self.snr_plot.getAxis("left").setStyle(tickFont=font)
        self.snr_plot.getAxis("left").setWidth(34)

        # self.scatter_widget.setData(x_axis, snr_list)
        self.snr_plot.addItem(self.snr_points)
        # self.plot_widget.plot(x_axis, snr_list, name="SNR", pen=pen, symbol='+')
        self.snr_plot.showGrid(x=True,y=True, alpha = 200) # alpha: 0-255
        # styles = {'color': 'r', 'font-size': '16px'}
        style = {'color': '#ffffff', 'font-size': '14px'}
        self.snr_plot.setLabel('left', 'SNR', **style)
        self.snr_plot.setLabel('bottom', 'Layer', **style)
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
        self.jupyter_console.execute_command('from alignEM.config import *')
        self.jupyter_console.execute_command('from alignEM.em_utils import *')
        self.jupyter_console.execute_command('clear')
        self.main_panel_bottom_widget.setCurrentIndex(2)

    def show_img(self, path):
        self.jupyter_console.execute_command(display(Image(filename=path)))
        self.main_panel_bottom_widget.setCurrentIndex(2)



    def show_hud(self):
        self.main_panel_bottom_widget.setCurrentIndex(0)


    @Slot()
    def back_callback(self):
        logger.info("Returning Home...")
        self.main_widget.setCurrentIndex(0)
        self.main_panel_bottom_widget.setCurrentIndex(0)
        self.set_idle()
    
    @Slot()
    def show_hide_project_inspector(self):
        logger.info('show_hide_project_inspector:')
        if self.project_inspector.isHidden():
            self.update_project_inspector()
            self.project_inspector.show()
        elif self.project_inspector.isVisible():
            self.project_inspector.hide()
    
    @Slot()
    def update_project_inspector(self):
        try:
            skips_list = str(get_skips_list())
            skips_list_wrapped = "\n".join(textwrap.wrap(skips_list, width=10))
            self.inspector_label_skips.setText(skips_list_wrapped)
        except:
            print_exception()
            logger.warning('Failed to update skips list')

    @Slot()  # 0503 #skiptoggle #toggleskip #skipswitch forgot to define this
    def update_skip_toggle(self):
        logger.info('update_skip_toggle:')
        scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]
        logger.info("scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'] = ",
                    scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'])
        self.toggle_skip.setChecked(not scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'])

    @Slot()
    def set_status(self, msg: str) -> None:
        self.status.showMessage(msg)
    
    # stylesheet
    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')
    
    def apply_stylesheet_1(self):
        self.main_stylesheet = 'alignEM/styles/stylesheet1.qss'
        self.hud.post('Applying stylesheet 1')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_stylesheet_3(self):
        '''Light stylesheet'''
        self.main_stylesheet = 'alignEM/styles/stylesheet3.qss'
        self.hud.post('Applying stylesheet 3')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_stylesheet_4(self):
        '''Grey stylesheet'''
        self.main_stylesheet = 'alignEM/styles/stylesheet4.qss'
        self.hud.post('Applying stylesheet 4')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_stylesheet_11(self):
        '''Screamin' Green stylesheet'''
        self.main_stylesheet = 'alignEM/styles/stylesheet11.qss'
        self.hud.post('Applying stylesheet 11')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()
    
    def apply_stylesheet_12(self):
        self.main_stylesheet = 'alignEM/styles/stylesheet12.qss'
        self.hud.post('Applying stylesheet 12')
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
        '''Set user progress (0 to 3). This is only called when user opens a project.'''
        logger.info('auto_set_user_progress:')
        if is_any_scale_aligned_and_generated():
            self.set_progress_stage_3()
        elif is_dataset_scaled():
            self.set_progress_stage_2()
        elif is_destination_set():
            self.set_progress_stage_1()
        else:
            self.set_progress_stage_0()
    
    def set_user_progress(self, gb1: bool, gb2: bool, gb3: bool, gb4: bool) -> None:
        logger.info('set_user_progress:')
        self.images_and_scaling_stack.setCurrentIndex((0, 1)[gb1])
        self.images_and_scaling_stack.setStyleSheet(
            ("""QGroupBox {border: 2px dotted #455364;}""", open(self.main_stylesheet).read())[gb1])
        self.alignment_stack.setCurrentIndex((0, 1)[gb2])
        self.alignment_stack.setStyleSheet(
            ("""QGroupBox {border: 2px dotted #455364;}""", open(self.main_stylesheet).read())[gb2])
        self.postalignment_stack.setCurrentIndex((0, 1)[gb3])
        self.postalignment_stack.setStyleSheet(
            ("""QGroupBox {border: 2px dotted #455364;}""", open(self.main_stylesheet).read())[gb3])
        self.export_and_view_stack.setCurrentIndex((0, 1)[gb4])
        self.export_and_view_stack.setStyleSheet(
            ("""QGroupBox {border: 2px dotted #455364;}""", open(self.main_stylesheet).read())[gb4])
    
    @Slot()
    def set_progress_stage_0(self):
        if self.get_user_progress() != 0: self.hud.post('Reverting user progress to Project')
        self.set_user_progress(False, False, False, False)
        self.project_progress = 0
    
    @Slot()
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
        if is_any_scale_aligned_and_generated():
            return int(3)
        elif is_dataset_scaled():
            return int(2)
        elif is_destination_set():
            return int(1)
        else:
            return int(0)
    
    @Slot()
    def read_gui_update_project_data(self) -> None:
        '''
        Reads UI data from MainWindow and writes everything to 'cfg.project_data'.
        '''
        # logger.info('read_gui_update_project_data:')
        if not is_dataset_scaled():
            logger.warning('read_gui_update_project_data was called without purpose by %s - Returning'
                           % inspect.stack()[1].function)
            return
        try:
            if self.get_null_bias_value() == 'None':
                cfg.project_data['data']['scales'][get_cur_scale_key()]['null_cafm_trends'] = False
            else:
                cfg.project_data['data']['scales'][get_cur_scale_key()]['null_cafm_trends'] = True
                cfg.project_data['data']['scales'][get_cur_scale_key()]['poly_order'] = int(self.get_null_bias_value())
            cfg.project_data['data']['scales'][get_cur_scale_key()]['use_bounding_rect'] = self.get_bounding_state()
            scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]
            scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                'whitening_factor'] = self.get_whitening_input()
            scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                'win_scale_factor'] = self.get_swim_input()
        except:
            print_exception()
            logger.error('There was a exception while updating project_data')
        return
    
    @Slot()
    def read_project_data_update_gui(self) -> None:
        '''Reads 'cfg.project_data' values and writes everything to MainWindow.'''
        
        if not is_dataset_scaled():
            logger.warning('read_gui_update_project_data was called without purpose by %s - Returning'
                           % inspect.stack()[1].function)
            return
        
        # Parts of the GUI that should be updated at any stage of progress
        if are_images_imported():
            try:
                scale = cfg.project_data['data']['scales'][
                    cfg.project_data['data']['current_scale']]  # we only want the current scale
            except:
                logger.error('Failed to get current scale')
            try:
                self.toggle_skip.setChecked(not scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'])
            except:
                logger.error('toggle_skip UI element failed to update its state')
            
            try:
                self.jump_input.setText(str(get_cur_layer()))
            except:
                pass
            
            # Parts of the GUI that should be updated only if the project is scaled
            # if is_dataset_scaled():  #0721-
            try:
                cur_whitening_factor = \
                    scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method'][
                        'method_data'][
                        'whitening_factor']
                self.whitening_input.setText(str(cur_whitening_factor))
            except:
                logger.error('Whitening Input UI element failed to update its state')
            
            try:
                layer = scale['alignment_stack'][
                    cfg.project_data['data']['current_layer']]  # we only want the current layer
                cur_swim_window = layer['align_to_ref_method']['method_data']['win_scale_factor']
                self.swim_input.setText(str(cur_swim_window))
            except:
                logger.error('Swim Input UI element failed to update its state')
            
            try:
                use_bounding_rect = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']][
                    'use_bounding_rect']
                self.toggle_bounding_rect.setChecked(bool(use_bounding_rect))

            except:
                logger.error('Bounding Rect UI element failed to update its state')
            
            # self.reload_scales_combobox() #0713-
            # self.update_scale_controls() #<-- this does not need to be called on every change of layer
            # if cfg.main_window.get_user_progress() >= 2:
            #     try:
            #         self.update_alignment_details()
            #     except:
            #         logger.error('Unable to update alignment status indicator')
            #         print_exception()
            
            caller = inspect.stack()[1].function
            if caller != 'change_layer': logger.info('GUI is in sync with cfg.project_data for current scale + layer.')
    
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
        cfg.project_data['data']['current_layer'] = int(layer)
        self.read_project_data_update_gui()
        self.image_panel.update_multi_self()
    
    @Slot()
    def jump_to_layer(self) -> None:
        if self.jump_input.text() == '':
            pass
        else:
            try:
                self.read_gui_update_project_data()
                requested_layer = int(self.jump_input.text())
                logger.info("Jumping to layer " + str(requested_layer))
                self.hud.post("Jumping to Layer " + str(requested_layer))
                n_layers = len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])
                if requested_layer >= n_layers:  # Limit to largest
                    requested_layer = n_layers - 1
                
                cfg.project_data['data']['current_layer'] = requested_layer
                self.read_project_data_update_gui()
                self.image_panel.update_multi_self()
            except:
                print_exception()
    
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
            snr_list = get_snr_list()
            enumerate_obj = enumerate(snr_list)
            sorted_pairs = sorted(enumerate_obj, key=operator.itemgetter(1))
            sorted_indices = [index for index, element in sorted_pairs]  # <- rearranged indices
            
            next_layer = sorted_indices[self.jump_to_worst_ticker]  # int
            snr = sorted_pairs[self.jump_to_worst_ticker]  # tuple
            rank = self.jump_to_worst_ticker  # int
            self.hud.post("Jumping to Layer %d (Badness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            
            cfg.project_data['data']['current_layer'] = next_layer
            self.read_project_data_update_gui()
            self.image_panel.update_multi_self()
            
            self.jump_to_worst_ticker += 1
        
        except:
            self.jump_to_worst_ticker = 1
            print_exception()
        
        self.image_panel.update_multi_self()
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
            snr_list = get_snr_list()
            enumerate_obj = enumerate(snr_list)
            sorted_pairs = sorted(enumerate_obj, key=operator.itemgetter(1), reverse=True)
            sorted_indices = [index for index, element in sorted_pairs]  # <- rearranged indices
            # sorted_indices = list(reversed(sorted_indices))
            next_layer = sorted_indices[self.jump_to_best_ticker]
            snr = sorted_pairs[self.jump_to_best_ticker]
            rank = self.jump_to_best_ticker
            self.hud.post("Jumping to layer %d (Goodness Rank = %d, SNR = %.2f)" % (next_layer, rank, snr[1]))
            cfg.project_data['data']['current_layer'] = next_layer
            self.read_project_data_update_gui()
            self.image_panel.update_multi_self()
            self.jump_to_best_ticker += 1
        
        except:
            self.jump_to_best_ticker = 0
            print_exception()
        
        self.image_panel.update_multi_self()
        self.set_idle()
    
    @Slot()
    def reload_scales_combobox(self) -> None:
        # logger.info("reload_scales_combobox:")
        prev_state = self.scales_combobox_switch
        self.scales_combobox_switch = 0
        curr_scale = cfg.project_data['data']['current_scale']
        image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.project_data['data']['scales'].keys())]
        self.scales_combobox.clear()
        for scale in sorted(image_scales_to_run):
            self.scales_combobox.addItems(["scale_" + str(scale)])
        index = self.scales_combobox.findText(curr_scale, Qt.MatchFixedString)
        if index >= 0: self.scales_combobox.setCurrentIndex(index)
        self.scales_combobox_switch = prev_state
    
    @Slot()  # scales
    def fn_scales_combobox(self) -> None:
        logger.debug('fn_scales_combobox >>>>')
        logger.debug('Called by %s' % inspect.stack()[1].function)
        if self.scales_combobox_switch == 0:
            logger.warning('Unnecessary Function Call Switch Disabled: %s' % inspect.stack()[1].function)
            return None
        logger.debug('Switch is live...')
        logger.debug('self.scales_combobox.currentText() = %s' % self.scales_combobox.currentText())
        new_curr_scale = self.scales_combobox.currentText()
        cfg.project_data['data']['current_scale'] = new_curr_scale
        self.read_project_data_update_gui()
        # self.update_panels()  # 0523 #0528
        self.center_all_images()  # 0528
        logger.debug('<<<< fn_scales_combobox')
        return None
    
    @Slot()
    def change_scale(self, scale_key: str):
        try:
            cfg.project_data['data']['current_scale'] = scale_key
            self.read_project_data_update_gui()
            self.center_all_images()
            logger.info('Scale changed to %s' % scale_key)
        except:
            print_exception()
            logger.info('Changing Scales Triggered An Exception')
    
    @Slot()
    def not_yet(self):
        logger.debug("Function is not implemented yet")
    
    @Slot()
    def print_image_library(self):
        logger.info(str(cfg.image_library))
    
    def new_project(self):
        logger.debug('new_project:')
        self.hud.post('Creating new project...')
        self.set_status("Project...")
        if is_destination_set():
            logger.info('Asking user to confirm new project')
            msg = QMessageBox(QMessageBox.Warning,
                              'Confirm New Project',
                              'Please confirm create new project.',
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
                self.hud.post('New project was canceled')
                self.set_idle()
                return
            if reply == QMessageBox.Cancel:
                logger.info("Response was 'Cancel'")
                self.hud.post('New project was canceled')
                self.set_idle()
                return
        self.set_progress_stage_0()
        filename = self.new_project_save_as_dialog()
        if filename == '':
            self.hud.post("You did not enter a valid name for the project file.")
            self.set_idle()
            return

        logger.info("Overwriting project data in memory with project template")
        '''Create new DataModel object'''


        if not filename.endswith('.json'):
            filename += ".json"
        logger.info("Creating new project %s" % filename)
        path, extension = os.path.splitext(filename)
        cfg.project_data = DataModel(name=path)
        makedirs_exist_ok(cfg.project_data['data']['destination_path'], exist_ok=True)
        self.setWindowTitle("Project: " + os.path.split(cfg.project_data.name())[-1])
        self.save_project()
        self.set_progress_stage_1()
        self.scales_combobox.clear()  # why? #0528
        cfg.project_data.settings()
        self.set_idle()

    def import_into_role(self):
        logger.debug("import_into_role:")
        import_role_name = str(self.sender().text())
        self.import_images_dialog(import_role_name)
    
    def import_base_images(self):
        '''Import images callback function.'''
        self.set_status('Importing...')
        self.hud.post('Importing images...')
        base_images = sorted(self.import_images_dialog())
        try:
            self.import_images('base', base_images)
        except:
            logger.warning('Something went wrong during import')
        if are_images_imported():
            self.update_scale_controls()
            self.center_all_images()
            self.refresh_all_images()
            self.save_project()  # good to have known fallback state
    
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
        '''Dialog for opening a project. Returns 'filename'.'''
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
        '''Dialog for saving a project. Returns 'filename'.'''
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
        '''Dialog for saving a project. Returns 'filename'.'''
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
        filename = self.open_project_dialog()
        if filename != '':
            with open(filename, 'r') as f:
                proj_copy = json.load(f)
            # proj_copy = upgrade_data_model(proj_copy)  # Upgrade the "Data Model"
            proj_copy = DataModel(proj_copy)  # Upgrade the "Data Model"
            if type(proj_copy) == type('abc'):
                self.hud.post('There Was a Problem Loading the Project File', logging.ERROR)
                logger.warning("Project Type is Abstract Base Class - Unable to Load!")
                self.set_idle()
                return
            self.hud.post("Loading project '%s'" % filename)
            # Modify the copy to use absolute paths internally
            # make_absolute(file_path, proj_path)
            logger.info("proj_copy['data']['destination_path'] was: %s" % proj_copy['data']['destination_path'])
            proj_copy['data']['destination_path'] = make_absolute(proj_copy['data']['destination_path'], filename)
            logger.info('make_absolute is returning: %s' % proj_copy['data']['destination_path'])

            for scale_key in proj_copy['data']['scales'].keys():
                scale_dict = proj_copy['data']['scales'][scale_key]
                for layer in scale_dict['alignment_stack']:
                    for role in layer['images'].keys():
                        layer['images'][role]['filename'] = make_absolute(layer['images'][role]['filename'], filename)
            
            cfg.project_data = copy.deepcopy(proj_copy)  # Replace the current version with the copy
            logger.info('Ensuring proper data structure...')
            cfg.project_data.ensure_proper_data_structure()
            cfg.project_data.link_all_stacks()
            self.read_project_data_update_gui()
            self.reload_scales_combobox()
            self.auto_set_user_progress()
            self.update_scale_controls()
            self.image_panel.setFocus()
            if are_images_imported():
                self.generate_scales_button.setEnabled(True)
            self.center_all_images()
            self.setWindowTitle("Project: %s" % os.path.basename(cfg.project_data.name()))
            self.hud.post("Project '%s'" % cfg.project_data.name())
        else:
            self.hud.post("No project file (.json) was selected")
        self.set_idle()
        logger.debug('<<<< open_project')
    
    def save_project(self):
        logger.info('save_project:')
        self.set_status("Saving...")
        try:
            self.save_project_to_file()
            self.hud.post("Project saved as '%s'" % cfg.project_data.name())
        except:
            print_exception()
            self.hud.post('Save Project Failed', logging.ERROR)
            self.set_idle()
        self.set_idle()
    
    def save_project_as(self):
        logger.info("save_project_as:")
        self.set_status("Saving...")
        filename = self.save_project_dialog()
        if filename != '':
            try:
                self.save_project_to_file()
                self.hud.post("Project saved as '%s'" % cfg.project_data.name())
            except:
                print_exception()
                self.hud.post('Save Project Failed', logging.ERROR)
                self.set_idle()
        self.set_idle()
    
    def save_project_to_file(self):
        logger.debug('Saving project...')
        if self.get_user_progress() > 1: #0801+
            self.read_gui_update_project_data()
        # if not cfg.project_data['data']['destination_path'].endswith('.json'): #0818-
        #     cfg.project_data['data']['destination_path'] += ".json"
        proj_copy = copy.deepcopy(cfg.project_data.to_dict())
        if cfg.project_data['data']['destination_path'] != None:
            if len(proj_copy['data']['destination_path']) > 0:
                proj_copy['data']['destination_path'] = make_relative(
                    proj_copy['data']['destination_path'], cfg.project_data['data']['destination_path'])
        for scale_key in proj_copy['data']['scales'].keys():
            scale_dict = proj_copy['data']['scales'][scale_key]
            for layer in scale_dict['alignment_stack']:
                for role in layer['images'].keys():
                    if layer['images'][role]['filename'] != None:
                        if len(layer['images'][role]['filename']) > 0:
                            layer['images'][role]['filename'] = make_relative(layer['images'][role]['filename'], cfg.project_data.name())
        logger.info("Writing data to '%s'" % cfg.project_data.name())
        logger.info('---- WRITING DATA TO PROJECT FILE ----')
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        proj_json = jde.encode(proj_copy)

        name = cfg.project_data.name()
        if not name.endswith('.json'): #0818-
            name += ".json"
        with open(name, 'w') as f:
            f.write(proj_json)
    
    @Slot()
    def actual_size(self):
        logger.info("MainWindow.actual_size:")
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update_zpa_self()
    
    @Slot()
    def toggle_threaded_loading(self, checked):
        logger.info('MainWindow.toggle_threaded_loading:')
        cfg.image_library.threaded_loading_enabled = checked
    
    @Slot()
    def toggle_annotations(self, checked):
        logger.info('MainWindow.toggle_annotations:')
        self.draw_annotations = checked
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_annotations = self.draw_annotations
            p.update_zpa_self()
    
    @Slot()
    def opt_n(self, option_name, option_action):
        if 'num' in dir(option_action):
            logger.debug("Dynamic Option[" + str(option_action.num) + "]: \"" + option_name + "\"")
        else:
            logger.debug("Dynamic Option: \"" + option_name + "\"")
        logger.debug("  Action: " + str(option_action))
    
    def add_image_to_role(self, image_file_name, role_name):
        logger.debug("Adding Image %s to Role '%s'" % (image_file_name, role_name))
        #### prexisting note: This function is now much closer to empty_into_role and should be merged
        scale = get_cur_scale_key()
        if image_file_name != None:
            if len(image_file_name) > 0:
                used_for_this_role = [role_name in l['images'].keys() for l in
                                      cfg.project_data['data']['scales'][scale]['alignment_stack']]
                layer_index = -1
                if False in used_for_this_role:
                    # There is an unused slot for this role. Find the first:
                    layer_index = used_for_this_role.index(False)
                else:
                    # There are no unused slots for this role. Add a new layer:
                    cfg.project_data.append_layer(scale_key=scale)
                    layer_index = len(cfg.project_data['data']['scales'][scale]['alignment_stack']) - 1
                cfg.project_data.add_img(
                    scale_key=scale,
                    layer_index=layer_index,
                    role=role_name,
                    filename=image_file_name
                )
    
    def add_empty_to_role(self, role_name):
        logger.debug('MainWindow.add_empty_to_role:')
        local_cur_scale = get_cur_scale_key()
        used_for_this_role = [role_name in l['images'].keys() for l in
                              cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']]
        layer_index = -1
        if False in used_for_this_role:
            # There is an unused slot for this role. Find the first.
            layer_index = used_for_this_role.index(False)
        else:
            # There are no unused slots for this role. Add a new layer
            logger.debug("Adding Empty Layer For Role %s at layer %d" % (role_name, layer_index))
            cfg.project_data.append_layer(scale_key=local_cur_scale)
            layer_index_for_new_role = len(cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        cfg.project_data.add_img(
            scale_key=local_cur_scale,
            layer_index=layer_index,
            role=role_name,
            filename=None
        )
    
    def import_images(self, clear_role=False):
        ''' Import images into project '''
        logger.info('import_images | Importing images..')
        self.set_status('Importing...')
        role_to_import = 'base'
        file_name_list = sorted(self.import_images_dialog())
        local_cur_scale = get_cur_scale_key()
        if clear_role:
            # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            for layer in cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']:
                if role_to_import in layer['images'].keys():
                    layer['images'].pop(role_to_import)
        
        if file_name_list != None:
            if len(file_name_list) > 0:
                logger.debug("Selected Files: " + str(file_name_list))
                for i, f in enumerate(file_name_list):
                    if i == 0:
                        self.center_all_images() # Center first imported image for better user experience
                    # Find next layer with an empty role matching the requested role_to_import
                    logger.debug("Role " + str(role_to_import) + ", Importing file: " + str(f))
                    if f is None:
                        self.add_empty_to_role(role_to_import)
                    else:
                        self.add_image_to_role(f, role_to_import)
                # Draw the panel's ("windows") #0808- #0816+s
                for p in self.panel_list:
                    p.force_center = True
                    p.update_zpa_self()

        if are_images_imported():
            self.generate_scales_button.setEnabled(True)
            img_size = get_image_size(
                cfg.project_data['data']['scales']['scale_1']['alignment_stack'][0]['images'][str(role_to_import)]['filename'])
            n_images = get_num_imported_images()
            self.hud.post('%d Images Were Imported' % n_images)
            self.hud.post('Image dimensions: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')
            cfg.project_data.link_all_stacks()
            self.center_all_images()
            self.update_panels()
            self.save_project()
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)
        
        self.set_idle()

    # 0527
    def load_images_in_role(self, role, file_names):
        logger.info('MainWindow.load_images_in_role:')
        '''Not clear if this has any effect. Needs refactoring.'''
        self.import_images(role, file_names, clear_role=True)
        self.center_all_images()
    
    def define_roles(self, roles_list):
        logger.info('MainWindow.define_roles: Roles List: %s' % str(roles_list))
        self.image_panel.set_roles(roles_list)  # Set the image panels according to the roles

    @Slot()
    def empty_into_role(self, checked):
        logger.info("MainWindow.empty_into_role:")
        # preexisting note: This function is now much closer to add_image_to_role and should be merged"
        local_cur_scale = get_cur_scale_key()
        role_to_import = str(self.sender().text())
        used_for_this_role = [role_to_import in l['images'].keys() for l in
                              cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']]
        layer_index_for_new_role = -1
        if False in used_for_this_role:
            # This means that there is an unused slot for this role. Find the first:
            layer_index_for_new_role = used_for_this_role.index(False)
        else:
            # This means that there are no unused slots for this role. Add a new layer
            cfg.project_data.append_layer(scale_key=local_cur_scale)
            layer_index_for_new_role = len(cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        cfg.project_data.add_img(scale_key=local_cur_scale, layer_index=layer_index_for_new_role,
                                      role=role_to_import, filename='')
        for p in self.panel_list:
            p.force_center = True
            p.update_zpa_self()
        self.update_win_self()
    
    @Slot()
    def remove_all_layers(self):
        logger.info("MainWindow.remove_all_layers:")
        # global cfg.project_data
        local_cur_scale = get_cur_scale_key()
        cfg.project_data['data']['current_layer'] = 0
        while len(cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) > 0:
            cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'].pop(0)
        self.update_win_self()
    
    @Slot()
    def remove_all_panels(self):
        logger.info("Removing all panels")
        logger.debug("Removing all panels")
        if 'image_panel' in dir(self):
            logger.debug("image_panel exists")
            self.image_panel.remove_all_panels()
        else:
            logger.debug("image_panel does not exit!!")
        # self.define_roles([])  # 0601  #0809-
        # self.image_panel.set_roles(cfg.roles_list) #0809+
        self.update_win_self()
    
    @Slot()
    def actual_size_callback(self):
        logger.info('MainWindow.actual_size_callback:')
        self.all_images_actual_size()
    
    @Slot()
    def center_all_images(self, all_images_in_stack=True):
        '''NOTE: CALLS COULD BE REDUCED BY CENTERING ALL STACKS OF IMAGES NOT JUST CURRENT SCALE
        self.image_panel is a MultiImagePanel object'''
        logger.info("Called by " + inspect.stack()[1].function)
        self.image_panel.center_all_images(all_images_in_stack=all_images_in_stack)
        self.image_panel.update_multi_self()
    
    @Slot()
    def all_images_actual_size(self):
        logger.info("Actual-sizing all images.")
        self.image_panel.all_images_actual_size()


    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent:")
        self.set_status('Exiting...')
        app = QApplication.instance()
        if not are_images_imported():
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
        self.hud.post('Confirm Exit AlignEM-SWiFT')
        message = "Save before exiting?"
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
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
        if reply == QMessageBox.Discard:
            logger.info('reply=Discard Exiting without saving')
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
    
    @Slot()
    def exit_app(self):
        logger.info("MainWindow.exit_app:")
        self.set_status('Exiting...')
        app = QApplication.instance()
        if not are_images_imported():
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
        self.hud.post('Confirm Exit AlignEM-SWiFT')
        message = "Save before exiting?"
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
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
        if reply == QMessageBox.Discard:
            logger.info('reply=Discard Exiting without saving')
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()

    def documentation_view(self):  # documentationview
        logger.info("Launching documentation view | MainWindow.documentation_view...")

        self.hud.post("Switching to AlignEM_SWiFT Documentation")
        # don't force the reload, add home button instead
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
        self.main_widget.setCurrentIndex(2)

    def documentation_view_home(self):
        logger.info("Launching documentation view home | MainWindow.documentation_view_home...")
        self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
        # self.set_status("AlignEM_SWiFT Documentation")

    def remote_view(self):
        logger.info("Launching remote viewer | MainWindow.remote_view...")
        self.hud.post("Switching to Remote Neuroglancer Viewer (https://neuroglancer-demo.appspot.com/)")
        self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.main_widget.setCurrentIndex(4)

    def reload_ng(self):
        logger.info("Reloading Neuroglancer...")
        self.view_neuroglancer()

    def reload_remote(self):
        logger.info("Reloading remote viewer...")
        self.remote_view()

    def exit_ng(self):
        logger.info("Exiting Neuroglancer...")
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def exit_docs(self):
        logger.info("Exiting docs...")
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def exit_remote(self):
        logger.info("Exiting remote viewer...")
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def exit_demos(self):
        logger.info("Exiting demos...")
        self.main_widget.setCurrentIndex(0)
        self.set_idle()

    def webgl2_test(self):
        '''https://www.khronos.org/files/webgl20-reference-guide.pdf'''
        logger.info("Running WebGL 2.0 Test In Web Browser...")
        self.browser_docs.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.main_widget.setCurrentIndex(2)


    def google(self):
        logger.info("Running Google in Web Browser...")
        self.browser_docs.setUrl(QUrl('https://www.google.com'))
        self.main_widget.setCurrentIndex(2)

    def about_config(self):
        logger.info("Running about:config in Web Browser...")
        self.browser_docs.setUrl(QUrl('about:config'))
        self.main_widget.setCurrentIndex(2)

    def gpu_config(self):
        logger.info("Running chrome://gpu in Web Browser...")
        self.browser_docs.setUrl(QUrl('chrome://gpu'))
        self.main_widget.setCurrentIndex(2)


    def print_state_ng(self):
        # viewer_state = json.loads(str(self.ng_viewer.state))
        logger.info(self.ng_viewer.state)
        # logger.info("Viewer.url : ", self.ng_viewer.get_viewer_url)
        # logger.info("Viewer.screenshot : ", self.ng_viewer.screenshot)
        # logger.info("Viewer.txn : ", self.ng_viewer.txn)
        # logger.info("Viewer.actions : ", self.ng_viewer.actions)
        # time.sleep(1)
        # self.set_status("Viewing aligned images in Neuroglancer.")

    def print_url_ng(self):
        print(ng.to_url(self.ng_viewer.state))
        # logger.info("\nURL : " + self.ng_viewer.get_viewer_url() + "\n")
        # logger.info("Viewer.url : ", self.ng_viewer.get_viewer_url)
        # logger.info("Viewer.screenshot : ", self.ng_viewer.screenshot)
        # logger.info("Viewer.txn : ", self.ng_viewer.txn)
        # logger.info("Viewer.actions : ", self.ng_viewer.actions)

    # def screenshot_ng():
    #     self.set_status("Taking screenshot...")
    #     ScreenshotSaver.capture(self)

    def blend_ng(self):
        logger.info("blend_ng():")

    def view_neuroglancer(self):  #view_3dem #ngview #neuroglancer
        logger.info("view_neuroglancer >>>>")
        logger.info("# of aligned images                  : %d" % get_num_aligned())
        if not are_aligned_images_generated():
            self.hud.post('This scale must be aligned and exported before viewing in Neuroglancer')

            self.show_warning("No Alignment Found",
                         "This scale must be aligned and exported before viewing in Neuroglancer.\n\n"
                         "Typical workflow:\n"
                         "(1) Open a project or import images and save.\n"
                         "(2) Generate a set of scaled images and save.\n"
                         "--> (3) Align each scale starting with the coarsest.\n"
                         "--> (4) Export alignment to Zarr format.\n"
                         "(5) View data in Neuroglancer client")
            logger.info(
                "Warning | This scale must be aligned and exported before viewing in Neuroglancer - Returning")
            self.set_idle()
            return
        else:
            logger.info('Alignment at this scale exists - Continuing')

        if not is_cur_scale_exported():
            self.hud.post('Alignment must be exported before it can be viewed in Neuroglancer')

            self.show_warning("No Export Found",
                         "Alignment must be exported before it can be viewed in Neuroglancer.\n\n"
                         "Typical workflow:\n"
                         "(1) Open a project or import images and save.\n"
                         "(2) Generate a set of scaled images and save.\n"
                         "(3) Align each scale starting with the coarsest.\n"
                         "--> (4) Export alignment to Zarr format.\n"
                         "(5) View data in Neuroglancer client")
            logger.info(
                "WARNING | Alignment must be exported before it can be viewed in Neuroglancer - Returning")
            self.set_idle()
            return
        else:
            logger.info('Exported alignment at this scale exists - Continuing')

        proj_path = os.path.abspath(cfg.project_data['data']['destination_path'])
        zarr_path = os.path.join(proj_path, '3dem.zarr')

        if 'server' in locals():
            logger.info('server is already running')
        else:
            # self.browser.setUrl(QUrl()) #empty page
            logger.info('no server found in local namespace -> starting RunnableServer() worker')

            ng_worker = View3DEM(source=zarr_path)
            self.threadpool.start(ng_worker)

        logger.info('Initializing Neuroglancer viewer...')
        logger.info("  Source: '%s'" % zarr_path)

        Image.MAX_IMAGE_PIXELS = None
        res_x, res_y, res_z = 2, 2, 50

        logger.info('defining Neuroglancer coordinate space')

        # def add_example_layers(state, image, offset):
        #     a[0, :, :, :] = np.abs(np.sin(4 * (ix + iy))) * 255
        #     a[1, :, :, :] = np.abs(np.sin(4 * (iy + iz))) * 255
        #     a[2, :, :, :] = np.abs(np.sin(4 * (ix + iz))) * 255
        #     dimensions = ng.CoordinateSpace(names=['x', 'y', 'z'], units='nm', scales=[2, 2, 50])
        #     state.dimensions = dimensions
        #     state.layers.append(
        #         name=image,
        #         layer=ng.LocalVolume(
        #             data='a',
        #             dimensions=ng.CoordinateSpace(
        #                 names=['x', 'y', 'z'],
        #                 units=['nm', 'nm', 'nm'],
        #                 scales=[2, 2, 50],
        #                 coordinate_arrays=[
        #                     ng.CoordinateArray(labels=['red', 'green', 'blue']), None, None, None
        #                 ]),
        #             voxel_offset=(0, 0, offset),
        #         ),
        #     return a, b

        self.ng_viewer = ng.Viewer()
        logger.info('Adding Neuroglancer Image Layers...')
        with self.ng_viewer.txn() as s:
            s.cross_section_background_color = "#ffffff"
            # s.cross_section_background_color = "#000000"
            # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]
            # s.perspective_zoom = 300
            # s.position = [0, 0, 0]

            '''Set Dimensions'''
            s.dimensions = ng.CoordinateSpace(
                names=["z", "y", "x"],
                units=["nm", "nm", "nm"],
                scales=[res_z, res_y, res_x]
            )

            '''generate_zarr_contig.py ONLY'''
            # layers = []
            # for scale in get_scales_list():
            #     scale_val = get_scale_val(scale)
            #     layer_name = 's' + str(scale_val)
            #     layers.append(layer_name)
            #     # s.layers[scale] = ng.ImageLayer(source="zarr://http://localhost:9000/" + str(scale_val))
            #     s.layers[layer_name] = ng.ImageLayer(source="zarr://http://localhost:9000/")
            #     # s.layers['multiscale_img'] = ng.ImageLayer(source="zarr://http://localhost:9000/")
            s.layers['multiscale_img'] = ng.ImageLayer(source="zarr://http://localhost:9000/")
            # s.layers['s1'] = ng.ImageLayer(source="zarr://http://localhost:9000/s1")
            # s.layers['s2'] = ng.ImageLayer(source="zarr://http://localhost:9000/s2")
            # s.layers['s4'] = ng.ImageLayer(source="zarr://http://localhost:9000/s4")

            '''generate_zarr.py ONLY'''
            # layers = ['layer_' + str(x) for x in range(get_num_aligned())]
            # for i, layer in enumerate(layers):
            #     s.layers[layer] = ng.ImageLayer(source="zarr://http://localhost:9000/" + str(i))

            # s.layers.append( name="one_layer", ...)
            # s.layers['layer_0'].visible = True
            # layout types: frozenset(['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'])
            s.layout = ng.column_layout(
                [
                    ng.LayerGroupViewer(
                        layout='4panel',
                        # layers=layers
                        # layers=['s1','s2','s4']
                        layers=['multiscale_img']
                    )
                ]
            )

        # logger.info('Loading Neuroglancer Callbacks...')
        # # self.ng_viewer.actions.add('unchunk_', unchunk)
        # # self.ng_viewer.actions.add('blend_', blend)
        with self.ng_viewer.config_state.txn() as s:
            # s.input_event_bindings.viewer['keyu'] = 'unchunk_'
            # s.input_event_bindings.viewer['keyb'] = 'blend_'
            # s.status_messages['message'] = 'Welcome to AlignEM_SWiFT'
            s.show_ui_controls = True
            s.show_panel_borders = True
            s.viewer_size = None

        viewer_url = str(self.ng_viewer)
        logger.info('viewer_url: %s' % viewer_url)
        self.ng_url = QUrl(viewer_url)
        self.browser.setUrl(self.ng_url)
        self.main_widget.setCurrentIndex(1)

        # To modify the state, use the viewer.txn() function, or viewer.set_state
        logger.info('Viewer.config_state                  : %s' % str(self.ng_viewer.config_state))
        # logger.info('viewer URL                           :', self.ng_viewer.get_viewer_url())
        # logger.info('Neuroglancer view (remote viewer)                :', ng.to_url(viewer.state))
        self.hud.post('Viewing Aligned Images In Neuroglancer')
        logger.info("<<<< view_neuroglancer")

    def set_main_view(self):
        self.main_widget.setCurrentIndex(0)

    def show_splash(self):
        print('Initializing funky UI...')
        # # self.main_widget.setCurrentIndex(6)
        # pixmap = QPixmap('fusiform-alignem-guy.png')
        # # splash = QSplashScreen(pixmap)
        # splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
        # splash.setMask(splash_pix.mask())
        # splash.show()
        # # app.processEvents()
        splash_pix = QPixmap('resources/em_guy.png')
        splash = QSplashScreen(self, splash_pix, Qt.WindowStaysOnTopHint)
        splash.setMask(splash_pix.mask())
        splash.show()

    def splash(self):
        self.funky_panel = QWidget()
        self.funky_layout = QVBoxLayout()
        pixmap = QPixmap('resources/fusiform-alignem-guy.png')
        label = QLabel(self)
        label.setPixmap(pixmap)
        # self.resize(pixmap.width(), pixmap.height())
        self.funky_layout.addWidget(label)
        self.funky_panel.setLayout(self.funky_layout)

    def cycle_user_progress(self):
        print('self.up = ' + str(self.up))
        self.up += 1
        up_ = self.up % 4
        print('up_ = ' + str(up_))
        if up_ == 0:    self.set_progress_stage_1()
        elif up_ == 1:  self.set_progress_stage_2()
        elif up_ == 2:  self.set_progress_stage_3()
        elif up_ == 3:  self.set_progress_stage_0()

    def settings(self):
        cfg.defaults_form.show()

    def view_k_img(self):
        logger.info('view_k_img:')
        self.w = KImageWindow(parent=self)
        self.w.show()

    def bounding_rect_changed_callback(self, state):
        # logger.info('  Bounding Rect project_file value was:', cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'])
        caller = inspect.stack()[1].function
        logger.info('Called By %s' % caller)
        if state:
            cfg.main_window.hud.post(
                'Bounding box will be used. Warning: x and y dimensions may grow larger than the source images.')
            cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            cfg.main_window.hud.post(
                'Bounding box will not be used (faster). x and y dimensions of generated images will equal the source images.')
            cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'] = False
            # logger.info('  Bounding Rect project_file value saved as:',cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'])
        # else:
        #     pass



    def skip_changed_callback(self, state):  # 'state' is connected to skip toggle
        logger.info("skip_changed_callback(state=%s):" % str(state))
        '''Toggle callback for skip image function. Note: a signal is emitted regardless of whether a user or another part
        of the program flips the toggle state. Caller is 'run_app' when a user flips the switch. Caller is change_layer
        or other user-defined function when the program flips the switch'''
        # called by:  change_layer <-- when ZoomPanWidget.change_layer toggles
        # called by:  run_app <-- when user toggles
        # skip_list = []
        # for layer_index in range(len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])):
        #     if cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][layer_index]['skip'] == True:
        #         skip_list.append(layer_index)
        if are_images_imported():
            skip_list = get_skips_list()
            # if inspect.stack()[1].function == 'run_app':
            toggle_state = state
            new_skip = not state
            logger.info('toggle_state: ' + str(toggle_state) + '  skip_list: ' + str(
                skip_list) + 'new_skip: ' + str(new_skip))
            scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]
            layer = scale['alignment_stack'][cfg.project_data['data']['current_layer']]
            layer['skip'] = new_skip  # skip # this is where skip list is appended to
            copy_skips_to_all_scales()
            cfg.project_data.link_all_stacks()  # 0525
            cfg.main_window.center_all_images()


    def toggle_match_point_align(self):
        self.match_point_mode = not self.match_point_mode
        if self.match_point_mode:
            self.hud.post('Match Point Mode is now ON (Ctrl+M or ⌘+M to Toggle Match Point Mode)')
        else:
            self.hud.post('Match Point Mode is now OFF (Ctrl+M or ⌘+M to Toggle Match Point Mode)')

    def clear_match_points(self):
        logger.info('Clearing Match Points...')
        cfg.project_data.clear_match_points()



    def initUI(self):

        '''-------- PANEL 1: PROJECT --------'''

        self.hud = HeadUpDisplay(self.app)
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.hud.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hud.post('You are aligning with AlignEM-SWiFT, please report any newlybugs to joel@salk.edu :)',
                      logging.INFO)

        self.new_project_button = QPushButton(" New")
        self.new_project_button.clicked.connect(self.new_project)
        self.new_project_button.setFixedSize(self.square_button_size)
        self.new_project_button.setIcon(qta.icon("msc.add", color=cfg.ICON_COLOR))

        self.open_project_button = QPushButton(" Open")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_project_button.setFixedSize(self.square_button_size)
        self.open_project_button.setIcon(qta.icon("fa.folder-open", color=cfg.ICON_COLOR))

        self.save_project_button = QPushButton(" Save")
        self.save_project_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setFixedSize(self.square_button_size)
        self.save_project_button.setIcon(qta.icon("mdi.content-save", color=cfg.ICON_COLOR))

        self.documentation_button = QPushButton(" Help")
        self.documentation_button.clicked.connect(self.documentation_view)
        self.documentation_button.setFixedSize(self.square_button_size)
        self.documentation_button.setIcon(qta.icon("mdi.help", color=cfg.ICON_COLOR))

        self.exit_app_button = QPushButton(" Exit")
        self.exit_app_button.clicked.connect(self.exit_app)
        self.exit_app_button.setFixedSize(self.square_button_size)
        self.exit_app_button.setIcon(qta.icon("mdi6.close", color=cfg.ICON_COLOR))

        self.remote_viewer_button = QPushButton("Neuroglancer\nServer")
        self.remote_viewer_button.clicked.connect(self.remote_view)
        self.remote_viewer_button.setFixedSize(self.square_button_size)
        self.remote_viewer_button.setStyleSheet("font-size: 9px;")

        self.project_functions_layout = QGridLayout()
        self.project_functions_layout.setContentsMargins(10, 25, 10, 5)
        self.project_functions_layout.addWidget(self.new_project_button, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.open_project_button, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.save_project_button, 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.exit_app_button, 1, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.documentation_button, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.remote_viewer_button, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        '''-------- PANEL 2: DATA SELECTION & SCALING --------'''

        self.import_images_button = QPushButton(" Import\n Images")
        self.import_images_button.setToolTip('Import TIFF images.')
        self.import_images_button.clicked.connect(self.import_images)
        self.import_images_button.setFixedSize(self.square_button_size)
        self.import_images_button.setIcon(qta.icon("fa5s.file-import", color=cfg.ICON_COLOR))
        self.import_images_button.setStyleSheet("font-size: 10px;")

        self.center_button = QPushButton('Center')
        self.center_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.center_button.setToolTip('Center all images.')
        self.center_button.clicked.connect(self.center_all_images)
        self.center_button.setFixedSize(self.square_button_width, self.std_height)
        self.center_button.setStyleSheet("font-size: 10px;")

        self.project_view_button = QPushButton('Inspect\nJSON')
        self.project_view_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.project_view_button.setToolTip('Inspect the project dictionary in memory.')
        self.project_view_button.clicked.connect(self.project_view_callback)
        self.project_view_button.setFixedSize(self.square_button_size)
        self.project_view_button.setStyleSheet("font-size: 10px;")

        self.print_sanity_check_button = QPushButton("Print\nSanity Check")
        self.print_sanity_check_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.print_sanity_check_button.clicked.connect(print_sanity_check)
        self.print_sanity_check_button.setFixedSize(self.square_button_size)
        self.print_sanity_check_button.setStyleSheet("font-size: 9px;")

        self.plot_snr_button = QPushButton("Plot SNR")
        self.plot_snr_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_snr_button.clicked.connect(self.show_snr_plot)
        self.plot_snr_button.setFixedSize(self.square_button_size)

        self.set_defaults_button = QPushButton("Options")
        self.set_defaults_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_defaults_button.clicked.connect(self.settings)
        self.set_defaults_button.setFixedSize(self.square_button_size)
        self.set_defaults_button.setStyleSheet("font-size: 10px;")

        # self.k_img_button = QPushButton("K Image")
        # self.k_img_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.k_img_button.clicked.connect(self.view_k_img)
        # self.k_img_button.setFixedSize(self.square_button_size)
        # # self.plot_snr_button.setStyleSheet("font-size: 9px;")

        self.actual_size_button = QPushButton('Actual Size')
        self.actual_size_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.actual_size_button.setToolTip('Actual-size all images.')
        self.actual_size_button.clicked.connect(self.actual_size_callback)
        self.actual_size_button.setFixedSize(self.square_button_width, self.std_height)
        self.actual_size_button.setStyleSheet("font-size: 10px;")

        self.size_buttons_vlayout = QVBoxLayout()
        self.size_buttons_vlayout.addWidget(self.center_button)
        self.size_buttons_vlayout.addWidget(self.actual_size_button)

        self.generate_scales_button = QPushButton('Generate\nScales')
        self.generate_scales_button.setToolTip('Generate scale pyramid with chosen # of levels.')
        self.generate_scales_button.clicked.connect(self.run_scaling)
        # self.generate_scales_button.clicked.connect(self.startProgressBar)

        self.generate_scales_button.setFixedSize(self.square_button_size)
        self.generate_scales_button.setStyleSheet("font-size: 10px;")
        self.generate_scales_button.setIcon(qta.icon("mdi.image-size-select-small", color=cfg.ICON_COLOR))
        self.generate_scales_button.setEnabled(False)

        self.clear_all_skips_button = QPushButton()
        self.clear_all_skips_button.setToolTip('Reset skips (keep all)')
        self.clear_all_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_all_skips_button.clicked.connect(self.clear_all_skips_callback)
        self.clear_all_skips_button.setFixedSize(self.std_height, self.std_height)
        self.clear_all_skips_button.setIcon(qta.icon("mdi.undo", color=cfg.ICON_COLOR))

        self.toggle_skip = ToggleSwitch()
        self.toggle_skip.setToolTip('Skip current image (do not align)')
        self.toggle_skip.setChecked(False)  # 0816 #observed #sus
        self.toggle_skip.toggled.connect(self.skip_changed_callback)
        self.skip_label = QLabel("Include:")
        self.skip_label.setToolTip('Skip current image (do not align)')
        self.skip_layout = QHBoxLayout()
        self.skip_layout.setAlignment(Qt.AlignCenter)
        self.skip_layout.addStretch()
        self.skip_layout.addWidget(self.skip_label)
        self.skip_layout.addWidget(self.toggle_skip)
        self.skip_layout.addStretch(4)

        self.jump_label = QLabel("Go to:")
        self.jump_input = QLineEdit(self)
        self.jump_input.setToolTip('Jump to image #')
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.jump_input.setFixedSize(self.std_input_size, self.std_height)
        self.jump_validator = QIntValidator()
        self.jump_input.setValidator(self.jump_validator)
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer())

        self.toggle_reset_hlayout = QHBoxLayout()
        self.toggle_reset_hlayout.addWidget(self.clear_all_skips_button)
        self.toggle_reset_hlayout.addLayout(self.skip_layout)
        self.toggle_reset_hlayout.addWidget(self.jump_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toggle_reset_hlayout.addWidget(self.jump_input, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.scale_layout = QGridLayout()
        self.scale_layout.setContentsMargins(10, 25, 10, 5)  # tag23
        self.scale_layout.addWidget(self.import_images_button, 0, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addLayout(self.size_buttons_vlayout, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addWidget(self.generate_scales_button, 0, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.scale_layout.addLayout(self.toggle_reset_hlayout, 1, 0, 1, 3)
        self.scale_layout.addWidget(self.set_defaults_button, 2, 0)
        self.scale_layout.addWidget(self.project_view_button, 2, 1)
        self.scale_layout.addWidget(self.print_sanity_check_button, 2, 2)

        '''-------- PANEL 3: ALIGNMENT --------'''

        self.scales_combobox = QComboBox(self)
        # self.scales_combobox.addItems([skip_list])
        # self.scales_combobox.addItems(['--'])
        self.scales_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scales_combobox.setFixedSize(self.std_button_size)
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

        self.affine_combobox = QComboBox(self)
        self.affine_combobox.addItems(['Init Affine', 'Refine Affine', 'Apply Affine'])
        self.affine_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.affine_combobox.setFixedSize(self.std_button_size)

        self.whitening_label = QLabel("Whitening:")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(self.std_input_size)
        self.whitening_input.setFixedHeight(self.std_height)
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
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(self.std_input_size)
        self.swim_input.setFixedHeight(self.std_height)
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
        self.apply_all_button.setToolTip('Apply these settings to the entire project.')
        self.apply_all_button.clicked.connect(self.apply_all_callback)
        self.apply_all_button.setFixedSize(self.std_height, self.std_height)
        self.apply_all_button.setIcon(qta.icon("mdi6.transfer", color=cfg.ICON_COLOR))

        self.apply_all_layout = QGridLayout()
        self.apply_all_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_all_layout.addWidget(self.apply_all_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.apply_all_layout.addWidget(self.apply_all_button, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.next_scale_button = QPushButton('Next Scale ')
        self.next_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_scale_button.setToolTip('Go forward to the next scale.')
        self.next_scale_button.clicked.connect(self.next_scale_button_callback)
        self.next_scale_button.setFixedSize(self.std_button_size)
        self.next_scale_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.next_scale_button.setIcon(qta.icon("ri.arrow-right-line", color=cfg.ICON_COLOR))

        self.prev_scale_button = QPushButton(' Prev Scale')
        self.prev_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_scale_button.setToolTip('Go back to the previous scale.')
        self.prev_scale_button.clicked.connect(self.prev_scale_button_callback)
        self.prev_scale_button.setFixedSize(self.std_button_size)
        self.prev_scale_button.setIcon(qta.icon("ri.arrow-left-line", color=cfg.ICON_COLOR))

        self.align_all_button = QPushButton('Align')
        self.align_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_all_button.setToolTip('Align This Scale')
        self.align_all_button.clicked.connect(self.run_alignment)
        self.align_all_button.setFixedSize(self.std_button_size)
        self.align_all_button.setIcon(qta.icon("ph.stack-fill", color=cfg.ICON_COLOR))

        self.alignment_status_label = QLabel()
        self.alignment_status_label.setText("Is Aligned: ")
        self.alignment_status_label.setStyleSheet("""color: #F3F6FB;""")

        self.align_label_resolution = QLabel()
        self.align_label_resolution.setText('[img size]')
        self.align_label_resolution.setStyleSheet("""color: #F3F6FB;""")

        self.align_label_affine = QLabel()
        self.align_label_affine.setText('Initialize Affine')
        self.align_label_affine.setStyleSheet("""color: #F3F6FB;""")

        self.align_label_scales_remaining = QLabel()
        self.align_label_scales_remaining.setText('# Scales Unaligned: n/a')
        self.align_label_scales_remaining.setStyleSheet("""color: #F3F6FB;""")

        self.alignment_status_label.setToolTip('Alignment status')
        self.alignment_status_checkbox = QRadioButton()
        self.alignment_status_checkbox.setEnabled(False)
        self.alignment_status_checkbox.setToolTip('Alignment status')

        self.alignment_status_layout = QHBoxLayout()
        self.alignment_status_layout.addWidget(self.alignment_status_label)
        self.alignment_status_layout.addWidget(self.alignment_status_checkbox)

        self.align_txt_layout = QGridLayout()
        self.align_txt_layout.addWidget(self.align_label_resolution, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_txt_layout.addWidget(self.align_label_affine, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_txt_layout.addLayout(self.alignment_status_layout, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_txt_layout.addWidget(self.align_label_scales_remaining, 1, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_txt_layout.setContentsMargins(5, 5, 15, 5)

        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.auto_generate_label.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate = ToggleSwitch()  # toggleboundingrect
        self.toggle_auto_generate.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate.setChecked(True)
        self.toggle_auto_generate.toggled.connect(self.toggle_auto_generate_callback)
        self.toggle_auto_generate_hlayout = QHBoxLayout()
        self.toggle_auto_generate_hlayout.addWidget(self.auto_generate_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_auto_generate_hlayout.addWidget(self.toggle_auto_generate, alignment=Qt.AlignmentFlag.AlignRight)

        self.alignment_layout = QGridLayout()
        self.alignment_layout.setContentsMargins(10, 25, 10, 0)  # tag23
        self.alignment_layout.addLayout(self.swim_grid, 0, 0, 1, 2)
        self.alignment_layout.addLayout(self.whitening_grid, 1, 0, 1, 2)
        self.alignment_layout.addWidget(self.prev_scale_button, 0, 2)
        self.alignment_layout.addWidget(self.next_scale_button, 1, 2)
        self.alignment_layout.addLayout(self.apply_all_layout, 2, 0, 1, 2)
        self.alignment_layout.addWidget(self.align_all_button, 2, 2)
        self.align_txt_layout_tweak = QVBoxLayout()
        self.align_txt_layout_tweak.setAlignment(Qt.AlignCenter)
        self.align_line = QFrame()
        self.align_line.setGeometry(QRect(60, 110, 751, 20))
        self.align_line.setFrameShape(QFrame.HLine)
        self.align_line.setFrameShadow(QFrame.Sunken)
        self.align_line.setStyleSheet("""background-color: #455364;""")

        self.align_txt_layout_tweak.addWidget(self.align_line)
        self.align_txt_layout_tweak.addLayout(self.align_txt_layout)
        self.align_txt_layout_tweak.setContentsMargins(0, 10, 0, 0)
        self.alignment_layout.addLayout(self.align_txt_layout_tweak, 3, 0, 1, 3)

        '''-------- PANEL 3.5: Post-alignment --------'''

        self.null_bias_label = QLabel("Bias:")
        tip = 'Polynomial bias (default=None). Affects aligned images including their pixel dimension.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.null_bias_label.setToolTip(wrapped)
        self.null_bias_combobox = QComboBox(self)
        self.null_bias_combobox.setToolTip(wrapped)
        self.null_bias_combobox.setToolTip('Polynomial bias (default=None)')
        self.null_bias_combobox.addItems(['None', '0', '1', '2', '3', '4'])
        self.null_bias_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.null_bias_combobox.setFixedSize(72, self.std_height)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.poly_order_hlayout.addWidget(self.null_bias_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        self.bounding_label = QLabel("Bounding Box:")
        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that ' \
              'are the same size as the source images but may have missing data, while turning this ON will ' \
              'result in no missing data but may significantly increase the size of the generated images.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.bounding_label.setToolTip(wrapped)
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setToolTip(wrapped)
        self.toggle_bounding_rect.toggled.connect(self.bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignRight)

        self.regenerate_label = QLabel('(Re)generate:')
        self.regenerate_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.regenerate_label.setToolTip('Regenerate aligned with adjusted settings')
        self.regenerate_button = QPushButton()
        self.regenerate_button.setToolTip('Regenerate aligned with adjusted settings')
        self.regenerate_button.setIcon(qta.icon("ri.refresh-line", color=cfg.ICON_COLOR))
        self.regenerate_button.clicked.connect(self.run_regenerate_alignment)
        self.regenerate_button.setFixedSize(self.std_height, self.std_height)

        self.regenerate_hlayout = QHBoxLayout()
        self.regenerate_hlayout.addWidget(self.regenerate_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.regenerate_hlayout.addWidget(self.regenerate_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.postalignment_note = QLabel("Note: These settings adjust,\nbut do not alter the initial\nalignment.")
        self.postalignment_note.setFont(QFont('Arial', 11, QFont.Light))
        self.postalignment_note.setContentsMargins(0, 0, 0, 0)
        self.postalignment_layout = QGridLayout()
        self.postalignment_layout.setContentsMargins(10, 25, 10, 5)

        self.postalignment_layout.addLayout(self.poly_order_hlayout, 0, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addLayout(self.toggle_bounding_hlayout, 1, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addLayout(self.regenerate_hlayout, 2, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addWidget(self.postalignment_note, 23, 0, alignment=Qt.AlignmentFlag.AlignBottom)

        '''-------- PANEL 4: EXPORT & VIEW --------'''

        clevel_label = QLabel("clevel (1-9):")
        clevel_label.setToolTip("Zarr Compression Level (default=5)")
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clevel_input.setText("5")
        self.clevel_input.setFixedWidth(self.std_input_size_small)
        self.clevel_input.setFixedHeight(self.std_height)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)
        cname_label = QLabel("cname:")
        cname_label.setToolTip("Zarr Compression Type (default=zstd) ")
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setFixedSize(72, self.std_height)
        self.export_and_view_hbox = QHBoxLayout()
        self.export_zarr_button = QPushButton(" Export\n Zarr")
        tip = "To view data in Neuroglancer, it is necessary to export to a compatible format such " \
              "as Zarr. This function exports all aligned .TIF images for current scale to the chunked " \
              "and compressed Zarr (.zarr) format with scale pyramid. Uses parallel processing."
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.export_zarr_button.setToolTip(wrapped)
        self.export_zarr_button.clicked.connect(self.export_zarr)
        self.export_zarr_button.setFixedSize(self.square_button_size)
        self.export_zarr_button.setStyleSheet("font-size: 10px;")
        # self.export_zarr_button.setIcon(qta.icon("fa5s.file-export", color=cfg.ICON_COLOR))
        self.export_zarr_button.setIcon(qta.icon("fa5s.cubes", color=cfg.ICON_COLOR))

        self.ng_button = QPushButton("3DEM")
        self.ng_button.setToolTip('View Zarr export in Neuroglancer.')
        self.ng_button.clicked.connect(self.view_neuroglancer)
        self.ng_button.setFixedSize(self.square_button_size)
        self.ng_button.setIcon(qta.icon("ph.cube-light", color=cfg.ICON_COLOR))

        self.export_hlayout = QVBoxLayout()
        self.export_hlayout.addWidget(self.export_zarr_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.export_hlayout.addWidget(self.ng_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clevel_layout = QHBoxLayout()
        self.clevel_layout.setContentsMargins(0, 0, 0, 0)
        self.clevel_layout.addWidget(clevel_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignmentFlag.AlignRight)

        self.cname_layout = QHBoxLayout()
        self.cname_layout.addWidget(cname_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        self.export_settings_layout = QGridLayout()
        self.export_settings_layout.addLayout(self.clevel_layout, 1, 0)
        self.export_settings_layout.addLayout(self.cname_layout, 0, 0)
        self.export_settings_layout.addLayout(self.export_hlayout, 0, 1, 2, 1)
        self.export_settings_layout.setContentsMargins(10, 25, 10, 5)  # tag23

        '''-------- INTEGRATED CONTROL PANEL --------'''

        # controlpanel
        cpanel_height = 200
        cpanel_1_width = 260
        cpanel_2_width = 260
        cpanel_3_width = 320
        cpanel_4_width = 170
        cpanel_5_width = 240

        # PROJECT CONTROLS
        self.project_functions_groupbox = QGroupBox("Project")
        self.project_functions_groupbox_ = QGroupBox("Project")
        self.project_functions_groupbox.setLayout(self.project_functions_layout)
        self.project_functions_stack = QStackedWidget()
        self.project_functions_stack.setFixedSize(cpanel_1_width, cpanel_height)
        self.project_functions_stack.addWidget(self.project_functions_groupbox_)
        self.project_functions_stack.addWidget(self.project_functions_groupbox)
        self.project_functions_stack.setCurrentIndex(1)

        # SCALING & DATA SELECTION CONTROLS
        self.images_and_scaling_groupbox = QGroupBox("Data Selection && Scaling")
        self.images_and_scaling_groupbox_ = QGroupBox("Scaling && Data Selection")
        self.images_and_scaling_groupbox.setLayout(self.scale_layout)
        self.images_and_scaling_stack = QStackedWidget()
        self.images_and_scaling_stack.setFixedSize(cpanel_2_width, cpanel_height)
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
        self.alignment_stack.setFixedSize(cpanel_3_width, cpanel_height)
        self.alignment_stack.addWidget(self.alignment_groupbox_)
        self.alignment_stack.addWidget(self.alignment_groupbox)
        self.alignment_stack.setCurrentIndex(0)

        # POST-ALIGNMENT CONTROLS
        self.postalignment_groupbox = QGroupBox("Adjust Output")
        self.postalignment_groupbox_ = QGroupBox("Adjust Output")
        self.postalignment_groupbox.setLayout(self.postalignment_layout)
        self.postalignment_stack = QStackedWidget()
        self.postalignment_stack.setFixedSize(cpanel_4_width, cpanel_height)
        self.postalignment_stack.addWidget(self.postalignment_groupbox_)
        self.postalignment_stack.addWidget(self.postalignment_groupbox)
        self.postalignment_stack.setCurrentIndex(0)

        # EXPORT & VIEW CONTROLS
        self.export_and_view_groupbox = QGroupBox("Export && View")
        self.export_and_view_groupbox_ = QGroupBox("Export && View")
        self.export_and_view_groupbox.setLayout(self.export_settings_layout)
        self.export_and_view_stack = QStackedWidget()
        self.export_and_view_stack.setFixedSize(cpanel_5_width, cpanel_height)
        self.export_and_view_stack.addWidget(self.export_and_view_groupbox_)
        self.export_and_view_stack.addWidget(self.export_and_view_groupbox)
        self.export_and_view_stack.setCurrentIndex(0)

        self.images_and_scaling_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")
        self.alignment_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")
        self.postalignment_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")
        self.export_and_view_stack.setStyleSheet("""QGroupBox {border: 2px dotted #455364;}""")

        self.lower_panel_groups_ = QGridLayout()
        self.lower_panel_groups_.addWidget(self.project_functions_stack, 0, 0, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.images_and_scaling_stack, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.alignment_stack, 0, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.postalignment_stack, 0, 3, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.lower_panel_groups_.addWidget(self.export_and_view_stack, 0, 4, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.lower_panel_groups_.setHorizontalSpacing(15)
        self.lower_panel_groups = QWidget()
        self.lower_panel_groups.setLayout(self.lower_panel_groups_)

        '''-------- MAIN LAYOUT --------'''

        self.image_panel = MultiImagePanel()
        self.image_panel.setFocusPolicy(Qt.StrongFocus)
        self.image_panel.setFocus()
        self.image_panel.draw_annotations = self.draw_annotations
        # self.image_panel.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding) #0610
        self.image_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_panel.setMinimumHeight(400)

        self.main_panel_bottom_widget = QStackedWidget()
        self.main_panel_bottom_widget.addWidget(self.hud)

        self.snr_plot = SnrPlot()
        # self.scatter_widget = pg.ScatterPlotWidget()
        # self.snr_plot = pg.plot()

        self.plot_widget_clear_button = QPushButton('Clear Plot')
        self.plot_widget_clear_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_widget_clear_button.clicked.connect(self.clear_snr_plot)
        self.plot_widget_clear_button.setFixedSize(self.square_button_size)

        self.plot_widget_back_button = QPushButton('Back')
        self.plot_widget_back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.plot_widget_back_button.clicked.connect(self.back_callback)
        self.plot_widget_back_button.setFixedSize(self.square_button_size)
        self.plot_widget_back_button.setAutoDefault(True)

        self.plot_controls_layout = QVBoxLayout()
        self.plot_controls_layout.addWidget(self.plot_widget_clear_button)
        self.plot_controls_layout.addWidget(self.plot_widget_back_button)
        self.plot_controls_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.plot_widget_layout = QHBoxLayout()
        # self.plot_widget_layout.addWidget(self.plot_widget)
        self.plot_widget_layout.addWidget(self.snr_plot)
        self.plot_widget_layout.addLayout(self.plot_controls_layout)
        self.plot_widget_container = QWidget()
        self.plot_widget_container.setLayout(self.plot_widget_layout)

        self.python_console_back_button = QPushButton('Back')
        self.python_console_back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.python_console_back_button.clicked.connect(self.back_callback)
        self.python_console_back_button.setFixedSize(self.square_button_size)
        self.python_console_back_button.setAutoDefault(True)

        self.python_console_layout = QHBoxLayout()
        self.python_console_layout.addWidget(self.jupyter_console)

        self.python_console_widget_container = QWidget()
        self.python_console_widget_container.setLayout(self.python_console_layout)

        self.main_panel_bottom_widget.addWidget(self.plot_widget_container)
        self.main_panel_bottom_widget.addWidget(self.python_console_widget_container)
        self.main_panel_bottom_widget.setCurrentIndex(0)

        '''MAIN SECONDARY CONTROL PANEL'''
        self.show_hud_button = QPushButton("Head-up\nDisplay")
        self.show_hud_button.setStyleSheet("font-size: 10px;")
        self.show_hud_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_hud_button.clicked.connect(self.show_hud)
        self.show_hud_button.setFixedSize(self.square_button_size)
        self.show_hud_button.setIcon(qta.icon("mdi.monitor", color=cfg.ICON_COLOR))

        self.show_jupyter_console_button = QPushButton("Python\nConsole")
        self.show_jupyter_console_button.setStyleSheet("font-size: 10px;")
        self.show_jupyter_console_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_jupyter_console_button.clicked.connect(self.show_jupyter_console)
        self.show_jupyter_console_button.setFixedSize(self.square_button_size)
        self.show_jupyter_console_button.setIcon(qta.icon("fa.terminal", color=cfg.ICON_COLOR))

        self.show_snr_plot_button = QPushButton("SNR\nPlot")
        self.show_snr_plot_button.setStyleSheet("font-size: 10px;")
        self.show_snr_plot_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_snr_plot_button.clicked.connect(self.show_snr_plot)
        self.show_snr_plot_button.setFixedSize(self.square_button_size)
        self.show_snr_plot_button.setIcon(qta.icon("mdi.scatter-plot", color=cfg.ICON_COLOR))

        self.main_secondary_controls_layout = QVBoxLayout()
        self.main_secondary_controls_layout.setContentsMargins(0, 8, 0, 0)
        self.main_secondary_controls_layout.addWidget(self.show_hud_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.main_secondary_controls_layout.addWidget(self.show_jupyter_console_button,
                                                      alignment=Qt.AlignmentFlag.AlignTop)
        self.main_secondary_controls_layout.addWidget(self.show_snr_plot_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.spacer_item_main_secondary = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.main_secondary_controls_layout.addSpacerItem(self.spacer_item_main_secondary)

        self.bottom_display_area_hlayout = QHBoxLayout()
        self.bottom_display_area_hlayout.setContentsMargins(0, 0, 0, 0)
        self.bottom_display_area_hlayout.addWidget(self.main_panel_bottom_widget)
        self.bottom_display_area_hlayout.addLayout(self.main_secondary_controls_layout)
        self.bottom_display_area_widget = QWidget()
        self.bottom_display_area_widget.setLayout(self.bottom_display_area_hlayout)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.image_panel)
        self.splitter.addWidget(self.lower_panel_groups)
        self.splitter.addWidget(self.bottom_display_area_widget)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, True)

        self.main_panel = QWidget()
        self.main_panel_layout = QGridLayout()
        self.main_panel_layout.setSpacing(2) # this inherits downward
        self.main_panel_layout.addWidget(self.splitter, 1, 0)
        self.main_panel.setLayout(self.main_panel_layout)

        '''-------- AUXILIARY PANELS --------'''

        # PROJECT VIEW PANEL
        self.project_view = QTreeView()
        self.project_model = JsonModel()
        self.project_view.setModel(self.project_model)
        self.project_view.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.project_view.setAlternatingRowColors(True)
        self.exit_project_view_button = QPushButton("Back")
        self.exit_project_view_button.setFixedSize(self.std_button_size)
        self.exit_project_view_button.clicked.connect(self.back_callback)
        self.refresh_project_view_button = QPushButton("Refresh")
        self.refresh_project_view_button.setFixedSize(self.std_button_size)
        self.refresh_project_view_button.clicked.connect(self.project_view_callback)
        self.save_project_project_view_button = QPushButton("Save")
        self.save_project_project_view_button.setFixedSize(self.std_button_size)
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
        self.browser = QWebEngineView()
        self.browser_docs = QWebEngineView()
        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(self.std_button_size)
        self.exit_docs_button.clicked.connect(self.exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(self.std_button_size)
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

        # REMOTE VIEWER PANEL
        self.browser_remote = QWebEngineView()
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))  # tacctacc
        # self.browser_remote.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.exit_remote_button = QPushButton("Back")
        self.exit_remote_button.setFixedSize(self.std_button_size)
        self.exit_remote_button.clicked.connect(self.exit_remote)
        self.reload_remote_button = QPushButton("Reload")
        self.reload_remote_button.setFixedSize(self.std_button_size)
        self.reload_remote_button.clicked.connect(self.reload_remote)
        self.remote_viewer_panel = QWidget()
        self.remote_viewer_panel_layout = QVBoxLayout()
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
        self.exit_demos_button.setFixedSize(self.std_button_size)
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
        self.exit_ng_button.setFixedSize(self.std_button_size)
        self.exit_ng_button.clicked.connect(self.exit_ng)
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(self.std_button_size)
        self.reload_ng_button.clicked.connect(self.reload_ng)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(self.std_button_size)
        self.print_state_ng_button.clicked.connect(self.print_state_ng)
        self.print_url_ng_button = QPushButton("Print URL")
        self.print_url_ng_button.setFixedSize(self.std_button_size)
        self.print_url_ng_button.clicked.connect(self.print_url_ng)
        # self.screenshot_ng_button = QPushButton("Screenshot")
        # self.screenshot_ng_button.setFixedSize(QSize(100, 28))
        # self.screenshot_ng_button.clicked.connect(screenshot_ng)
        # self.blend_ng_button = QPushButton("Blend (b)")
        # self.blend_ng_button.setFixedSize(QSize(100, 28))
        # self.blend_ng_button.clicked.connect(blend_ng)
        self.ng_panel = QWidget()  # create QWidget()
        self.ng_panel_layout = QVBoxLayout()  # create QVBoxLayout()
        self.ng_panel_layout.addWidget(self.browser)  # add widgets
        self.ng_panel_controls_layout = QHBoxLayout()
        self.ng_panel_controls_layout.addWidget(self.exit_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.reload_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_state_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.ng_panel_controls_layout.addWidget(self.print_url_ng_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)
        self.ng_panel.setLayout(self.ng_panel_layout)

        self.splash() #0816 Refactor!

        self.main_widget = QStackedWidget(self)
        self.main_widget.addWidget(self.main_panel)                 # (0) main_panel
        self.main_widget.addWidget(self.ng_panel)                   # (1) ng_panel
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

        self.setCentralWidget(self.main_widget)



