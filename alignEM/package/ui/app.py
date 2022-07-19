#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os, sys, copy, json, inspect, collections, multiprocessing, logging, textwrap
from random import randint
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QFileDialog, QInputDialog, QLineEdit, QPushButton, QCheckBox, \
    QSpacerItem, QMenu, QMessageBox, QComboBox, QGroupBox, QScrollArea, QToolButton, QSplitter, \
    QRadioButton,  QErrorMessage, QFrame, QTreeView, QHeaderView, QDockWidget
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QPainter, \
    QBrush, QPen, QColor, QFont
from qtpy.QtCore import Qt, QSize, QUrl, QRunnable, QObject, QAbstractAnimation, QPropertyAnimation, \
    QParallelAnimationGroup, QThreadPool, QThread, Signal, Slot, QRect, QFileInfo
from qtpy.QtWidgets import QAction, QActionGroup
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWebEngineCore import *
import qtawesome as qta
import pyqtgraph as pg
import daisy
import neuroglancer as ng
from glob import glob
from PIL import Image
import numpy as np
import psutil
import platform
import config as cfg
# from package.em_utils import get_cur_scale_key, is_destination_set, is_dataset_scaled, \
#     is_cur_scale_aligned, get_num_aligned, get_skips_list, are_aligned_images_generated,
#     is_any_scale_aligned_and_generated, get_num_scales, print_path, copy_skips_to_all_scales, are_images_imported, \
#     print_sanity_check, debug_project, is_cur_scale_exported, get_num_imported_images, print_exception, get_scale_val, \
#     set_scales_from_string, makedirs_exist_ok, make_relative, make_absolute, is_scale_aligned, \
#     clear_all_skips, verify_image_file, get_cur_layer, get_cur_scale_key, is_dataset_scaled, print_debug, \
#     get_aligned_scales_list, is_cur_scale_ready_for_alignment, get_next_coarsest_scale_key, \
#     ensure_proper_data_structure, set_default_settings, is_cur_scale_ready_for_alignment, get_aligned_scales_list, \
#     get_scales_list
from package.em_utils import *
from package.scale_pyramid import add_layer
from data_model import new_project_template, new_layer_template, new_image_template, upgrade_data_model
from package.get_image_size import get_image_size
from package.compute_affines import compute_affines
from package.generate_aligned_images import generate_aligned_images
from package.generate_scales import generate_scales
from .heads_up_display import HeadsUpDisplay
from .image_library import ImageLibrary, SmartImageLibrary
from .runnable_server import RunnableServer
from .multi_image_panel import MultiImagePanel
from .toggle_switch import ToggleSwitch
from .json_treeview import JsonModel

__all__ = ['MainWindow']

#
# logger = logging.getLogger(__name__)
# logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s [%(levelname)s] %(message)s",
#         datefmt='%H:%M:%S',
#         handlers=[ logging.StreamHandler() ]
# )

# from caveclient import CAVEclient


center_switch = 0
print_switch = 0

# cfg.project_data = None #jy turning back on #0404 #<-- #0618 this could be the problem
app = None
use_c_version = True
use_file_io = cfg.USE_FILE_IO
show_skipped_images = True

code_mode = 'c'
global_parallel_mode = True
# global_use_file_io = True #0629
# global_use_file_io = False #0629


# max_image_file_size = 1000000000 #orig
max_image_file_size = 50000000000


def open_ds(path, ds_name):
    """ wrapper for daisy.open_ds """
    print("Running daisy.open_ds with path:" + path + ", ds_name:" + ds_name)
    try:
        return daisy.open_ds(path, ds_name)
    except KeyError:
        print("\n  ERROR: dataset " + ds_name + " could not be loaded. Must be Daisy-like array.\n")
        return None



def decode_json(x):
    return json.loads(x, object_pairs_hook=collections.OrderedDict)


def get_json(path):
    with open(path) as f:
        return json.load(f)
        # example: keys = get_json("project.zarr/img_aligned_zarr/s0/.zarray")


def show_warning(title, text):
    QMessageBox.warning(None, title, text)


def request_confirmation(title, text):
    button = QMessageBox.question(None, title, text)
    print_debug(50, "You clicked " + str(button))
    print_debug(50, "Returning " + str(button == QMessageBox.StandardButton.Yes))
    return (button == QMessageBox.StandardButton.Yes)


def link_stack():
    print('Linking stack | link_stack...')
    cfg.main_window.hud.post('Linking the image stack...')

    skip_list = []
    for layer_index in range(len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])):
        if cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][layer_index][
            'skip'] == True:
            skip_list.append(layer_index)

    # print('\nlink_stack(): Skip List = \n' + str(skip_list) + '\n')

    for layer_index in range(len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])):
        base_layer = cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][layer_index]

        if layer_index == 0:
            # No ref for layer 0
            if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(new_image_template)
            base_layer['images']['ref']['filename'] = ''
        elif layer_index in skip_list:
            # No ref for skipped layer
            if 'ref' not in base_layer['images'].keys():
                base_layer['images']['ref'] = copy.deepcopy(new_image_template)
            base_layer['images']['ref']['filename'] = ''
        else:
            # Find nearest previous non-skipped layer
            j = layer_index - 1
            while (j in skip_list) and (j >= 0):
                j -= 1

            # Use the nearest previous non-skipped layer as ref for this layer
            if (j not in skip_list) and (j >= 0):
                ref_layer = cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][j]
                ref_fn = ''
                if 'base' in ref_layer['images'].keys():
                    ref_fn = ref_layer['images']['base']['filename']
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(new_image_template)
                base_layer['images']['ref']['filename'] = ref_fn

    # main_win.update_panels() #0526
    cfg.main_window.update_win_self()
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    # print('skip_list =', str(skip_list))
    print('Exiting link_stack')
    cfg.main_window.hud.post('Complete')


# NOTE: this is called right after importing base images (through update_linking_callback)
def link_all_stacks():
    '''Called by the functions 'skip_changed_callback' and 'import_images'  '''
    print('link_all_stacks >>>>>>>>')
    # global cfg.project_data #0619 this was NOT in 0613 commit
    ensure_proper_data_structure() #0712
    for scale_key in cfg.project_data['data']['scales'].keys():
        skip_list = []
        for layer_index in range(len(cfg.project_data['data']['scales'][scale_key]['alignment_stack'])):
            if cfg.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip'] == True:
                print('  appending layer ' + str(layer_index) + ' to skip_list')       #0714 <-- issue w/ scope
                skip_list.append(layer_index)  # skip

        for layer_index in range(len(cfg.project_data['data']['scales'][scale_key]['alignment_stack'])):
            base_layer = cfg.project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]

            if layer_index == 0:
                # No ref for layer 0 # <-- ******
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(new_image_template)
                base_layer['images']['ref']['filename'] = ''
            elif layer_index in skip_list:
                # No ref for skipped layer
                if 'ref' not in base_layer['images'].keys():
                    base_layer['images']['ref'] = copy.deepcopy(new_image_template)
                base_layer['images']['ref']['filename'] = ''
            else:
                # Find nearest previous non-skipped layer
                j = layer_index - 1
                while (j in skip_list) and (j >= 0):
                    j -= 1

                # Use the nearest previous non-skipped layer as ref for this layer
                if (j not in skip_list) and (j >= 0):
                    ref_layer = cfg.project_data['data']['scales'][scale_key]['alignment_stack'][j]
                    ref_fn = ''
                    if 'base' in ref_layer['images'].keys():
                        ref_fn = ref_layer['images']['base']['filename']
                    if 'ref' not in base_layer['images'].keys():
                        base_layer['images']['ref'] = copy.deepcopy(new_image_template)
                    base_layer['images']['ref']['filename'] = ref_fn

    cfg.main_window.update_win_self()
    cfg.main_window.center_all_images()  # 0702 necessary call
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    print('<<<<<<<< link_all_stacks')


def null_bias_changed_callback(state):
    print('\nnull_bias_changed_callback(state):' % str(state))
    print('  Null Bias project_file value was:',
          cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['null_cafm_trends'])
    if state:
        cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['null_cafm_trends'] = True
    else:
        cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['null_cafm_trends'] = False
    print('  Null Bias project_file value saved as: ',
          cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['null_cafm_trends'])


# 0606
def bounding_rect_changed_callback(state):
    # print('  Bounding Rect project_file value was:', cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'])

    caller = inspect.stack()[1].function
    # print('bounding_rect_changed_callback | called by %s ' % caller)
    if cfg.main_window.toggle_bounding_rect_switch == 1:
        if state:
            cfg.main_window.hud.post(
                'Bounding box will be used. Warning: x and y dimensions may grow larger than the source images.')
            cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'] = True
        else:
            cfg.main_window.hud.post(
                'Bounding box will not be used (faster). x and y dimensions of generated images will equal the source images.')
            cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'] = False
        # print('  Bounding Rect project_file value saved as:',cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['use_bounding_rect'])
    else:
        pass


def skip_changed_callback(state):  # 'state' is connected to skip toggle
    print("\nskip_changed_callback(state=%s):" % str(state))
    '''Toggle callback for skip image function. Note: a signal is emitted regardless of whether a user or another part 
    of the program flips the toggle state. Caller is 'run_app' when a user flips the switch. Caller is change_layer 
    or other user-defined function when the program flips the switch'''
    # !!!
    # global ignore_changes #0528
    # called by:  change_layer <-- when ZoomPanWidget.change_layer toggles
    # called by:  run_app <-- when user toggles
    # skip_list = []
    # for layer_index in range(len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])):
    #     if cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][layer_index]['skip'] == True:
    #         skip_list.append(layer_index)
    print('skip_changed_callback | inspect.stack()[1].function = ', inspect.stack()[1].function)
    if are_images_imported():
        skip_list = get_skips_list()
        # if inspect.stack()[1].function == 'run_app':
        toggle_state = state
        new_skip = not state
        print('skip_changed_callback | toggle_state: ' + str(toggle_state) + '  skip_list: ' + str(
            skip_list) + 'new_skip: ' + str(new_skip))
        scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]
        layer = scale['alignment_stack'][cfg.project_data['data']['current_layer']]
        layer['skip'] = new_skip  # skip # this is where skip list is appended to
        copy_skips_to_all_scales()

        link_all_stacks()  # 0525
        # cfg.main_window.update_panels() #0701 removed
        # cfg.main_window.refresh_all_images() #0701 removed
        # update_linking_callback()
        # 0503 possible non-centering bug that occurs when runtime skips change is followed by scale change
        cfg.main_window.center_all_images()



class ScreenshotSaver(object):
    def __init__(self, viewer, directory):
        self.viewer = viewer
        self.directory = directory

        if not os.path.exists(directory):
            os.makedirs(directory)

        self.index = 0

    def get_path(self, index):
        return os.path.join(self.directory, '%07d.png' % index)

    def get_next_path(self, index=None):
        if index is None:
            index = self.index
        return index, self.get_path(index)

    def capture(self, index=None):
        s = self.viewer.screenshot()
        increment_index = index is None
        index, path = self.get_next_path(index)
        with open(path, 'wb') as f:
            f.write(s.screenshot.image)
        if increment_index:
            self.index += 1
        return index, path


# example keypress callback
def get_mouse_coords(s):
    print('  Mouse position: %s' % (s.mouse_voxel_coordinates,))
    print('  Layer selected values: %s' % (s.selected_values,))


class CollapsibleBox(QWidget):
    '''Forms a part of the project inspector class. Adapted from:
    https://github.com/fzls/djc_helper/blob/master/qt_collapsible_box.py'''

    def __init__(self, title="", title_backgroup_color="", tool_tip="Project Inspector :)",
                 animation_duration_millseconds=250, parent=None):
        super(CollapsibleBox, self).__init__(parent)

        self.title = title
        self.setToolTip(tool_tip)
        self.animation_duration_millseconds = animation_duration_millseconds
        self.collapsed_height = 19
        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(title)

        # sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) #0610
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self.toggle_button.setSizePolicy(sizePolicy)

        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet(
            f"QToolButton {{ border: none; font-weight: bold; background-color: #7c7c7c; }}")
        # self.toggle_button.setToolButtonStyle(alignEM.ToolButtonTextBesideIcon) #0610
        # self.toggle_button.setArrowType(alignEM.RightArrow) #0610
        self.toggle_button.pressed.connect(self.on_pressed)

        self.toggle_animation = QParallelAnimationGroup(self)

        self.content_area = QScrollArea(self)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        # self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # self.content_area.setFrameShape(QFrame.NoFrame) #0610 AttributeError: type object 'QFrame' has no attribute 'NoFrame'

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(QPropertyAnimation(self, b"minimumHeight"))
        self.toggle_animation.addAnimation(QPropertyAnimation(self, b"maximumHeight"))
        self.toggle_animation.addAnimation(QPropertyAnimation(self.content_area, b"maximumHeight"))

    @Slot()
    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.DownArrow if not checked else Qt.RightArrow)
        self.toggle_animation.setDirection(
                QAbstractAnimation.Forward
                if not checked
                else QAbstractAnimation.Backward
        )
        self.toggle_animation.start()

    def setContentLayout(self, layout):
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = (self.sizeHint().height() - self.content_area.maximumHeight())
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            # animation.setDuration(500)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
        # content_animation.setDuration(500)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)


#mainwindow
class MainWindow(QMainWindow):
    def __init__(self, fname=None, panel_roles=None, title="AlignEM-SWiFT"):
        app = QApplication.instance()
        if app is None:
            print("Warning | 'app' was None. Creating new instance.")
            app = QApplication([])

        logging.info('MainWindow | app.__str__() = ' + app.__str__())
        self.pyside_path = os.path.dirname(os.path.realpath(__file__))

        logging.info('MainWindow | initializing QMainWindow.__init__(self)')
        QMainWindow.__init__(self)

        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(QPixmap('sims.png')))
        self.project_filename = None
        self.mouse_down_callback = None
        self.mouse_move_callback = None
        self.init_dir = os.getcwd()

        logging.info("MainWindow | Initializing Thread Pool")
        self.threadpool = QThreadPool(self)  # important consideration is this 'self' reference
        QThread.currentThread().setObjectName('MainThread')
        logging.getLogger().setLevel(logging.DEBUG)  # <- critical instruction else logger will break.
        self.hud = HeadsUpDisplay(app)
        self.hud.post('Welcome to AlignEM-SWiFT (Development Branch). Please report bugs to joel@salk.edu.')

        logging.info("MainWindow | Copying new project template")
        cfg.project_data = copy.deepcopy(new_project_template)  # <-- TODO: get rid of this

        cfg.image_library = ImageLibrary()
        # cfg.image_library = SmartImageLibrary()

        logging.info('MainWindow | cfg.USES_PYSIDE=%s' % str(cfg.USES_PYSIDE))

        '''This will require moving the image_panel = ImageLibrary() to MainWindow constructor where it should be anyway'''
        # self.define_roles(['ref', 'base', 'aligned'])
        '''
        objc[53148]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was
        called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint
        on objc_initializeAfterForkError to debug.
        https://stackoverflow.com/questions/50168647/multiprocessing-causes-python-to-crash-and-gives-an-error-may-have-been-in-progr'''
        # print('alignem_swift.py | Setting OBJC_DISABLE_INITIALIZE_FORK_SAFETY=yes')
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

        # if cfg.QT_API == 'pyside6':
        #     print("alignem_swift.py | QImageReader.allocationLimit() WAS " + str(QImageReader.allocationLimit()) + "MB")
        #     QImageReader.setAllocationLimit(4000) #pyside6 #0610setAllocationLimit
        #     print("alignem_swift.py | New QImageReader.allocationLimit() NOW IS " + str(QImageReader.allocationLimit()) + "MB")

        # self.setWindowFlags(self.windowFlags() | alignEM.FramelessWindowHint)
        # self.setWindowFlag(alignEM.FramelessWindowHint)

        # stylesheet must be after QMainWindow.__init__(self)
        # self.setStyleSheet(open('stylesheet.qss').read())
        logging.info("MainWindow | applying stylesheet")
        # self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet1.qss')
        self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet1.qss')
        # self.main_stylesheet = os.path.join(self.pyside_path, 'styles/stylesheet4.qss')
        self.setStyleSheet(open(self.main_stylesheet).read())

        self.context = QOpenGLContext(self)
        self.context.setFormat(QSurfaceFormat())

        logging.info("MainWindow | Setting multiprocessing.set_start_method('fork', force=True)...")
        multiprocessing.set_start_method('fork', force=True)

        self.project_progress = 0
        # self.project_scales = [] #0702
        self.project_aligned_scales = []

        self.scales_combobox_switch = 0

        self.always_generate_images = True

        # std_height = int(22)
        std_height = 24
        std_width = int(96)
        std_button_size = QSize(std_width, std_height)
        square_button_height = int(30)
        square_button_width = int(72)
        square_button_size = QSize(square_button_width, square_button_height)
        std_input_size = int(56)
        std_input_size_small = int(36)

        # titlebar resource
        # https://stackoverflow.com/questions/44241612/custom-titlebar-with-frame-in-pyqt5

        # pyside6 port needed to replace deprecated the 'defaultSettings()' attribute of QWebEngineSettings. These two lines were uncommented.
        # self.web_settings = QWebEngineSettings.defaultSettings()
        # self.web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # pyside6
        logging.info("MainWindow | instantiating QWebEngineView()")
        if cfg.USES_PYSIDE:
            self.view = QWebEngineView()
        if cfg.QT_API == 'pyqt6':
            self.view = QWebEngineView()
        # PySide6 available options
        # self.view.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.view.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        logging.info("MainWindow | Setting QWebEngineSettings.LocalContentCanAccessRemoteUrls to True")
        # print('---------------------\n')
        if cfg.USES_QT6:
            self.view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # print('---------------------\n')

        def closeEvent(self, event):

            quit_msg = "Are you sure you want to exit the program?"
            reply = QMessageBox.question(self, 'Message',
                                         quit_msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()

        # !!!
        # def changeEvent(self, event):
        #     if event.type() == event.WindowStateChange:
        #         self.titleBar.windowStateChanged(self.windowState())
        #
        # def resizeEvent(self, event):
        #     self.titleBar.resize(self.width(), self.titleBar.height())

        # # set stylesheet
        # file = QFile(":/dark/stylesheet.qss")
        # file.open(QFile.ReadOnly | QFile.Text)
        # stream = QTextStream(file)
        # app.setStyleSheet(stream.readAll())

        # create RunnableServer class to start background CORS web server
        def start_server():
            logging.info("MainWindow | creating RunnableServer() instance and setting up thread pool")
            worker = RunnableServer()
            self.threadpool.start(worker)

        # self.browser.setPage(CustomWebEnginePage(self)) # This is necessary. Clicked links will never open new window.
        # self.browser.setPage(CustomWebEnginePage(self))

        # homepage #browserview #webview
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!%7B%22dimensions%22:%7B%22x%22:%5B8e-9%2C%22m%22%5D%2C%22y%22:%5B8e-9%2C%22m%22%5D%2C%22z%22:%5B8e-9%2C%22m%22%5D%7D%2C%22position%22:%5B2914.500732421875%2C3088.243408203125%2C4045%5D%2C%22crossSectionScale%22:3.762185354999915%2C%22projectionOrientation%22:%5B0.31435418128967285%2C0.8142172694206238%2C0.4843378961086273%2C-0.06040274351835251%5D%2C%22projectionScale%22:4593.980956070108%2C%22layers%22:%5B%7B%22type%22:%22image%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/image%22%2C%22tab%22:%22source%22%2C%22name%22:%22image%22%7D%2C%7B%22type%22:%22segmentation%22%2C%22source%22:%22precomputed://gs://neuroglancer-public-data/flyem_fib-25/ground_truth%22%2C%22tab%22:%22source%22%2C%22segments%22:%5B%22158571%22%2C%2221894%22%2C%2222060%22%2C%2224436%22%2C%222515%22%5D%2C%22name%22:%22ground-truth%22%7D%5D%2C%22showSlices%22:false%2C%22layout%22:%224panel%22%7D"))
        # self.browser.load(QUrl("https://github.com/google/neuroglancer"))
        # self.browser.load(QUrl("https://neuroglancer-demo.appspot.com/#!{'layers':{'original-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image'_'visible':false}_'corrected-image':{'type':'image'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/image_color_corrected'}_'ground_truth':{'type':'segmentation'_'source':'precomputed://gs://neuroglancer-public-data/kasthuri2011/ground_truth'_'selectedAlpha':0.63_'notSelectedAlpha':0.14_'segments':['3208'_'4901'_'13'_'4965'_'4651'_'2282'_'3189'_'3758'_'15'_'4027'_'3228'_'444'_'3207'_'3224'_'3710']}}_'navigation':{'pose':{'position':{'voxelSize':[6_6_30]_'voxelCoordinates':[5523.99072265625_8538.9384765625_1198.0423583984375]}}_'zoomFactor':22.573112129999547}_'perspectiveOrientation':[-0.004047565162181854_-0.9566211104393005_-0.2268827110528946_-0.1827099621295929]_'perspectiveZoom':340.35867907175077}"))
        # self.browser.setUrl(QUrl()) # empty/blank URL (white screen)
        # self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        # self.browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/development/docs/user/README.md'))

        def documentation_view():  # documentationview
            logging.info("Launching documentation view | MainWindow.documentation_view...")
            self.stacked_widget.setCurrentIndex(2)
            self.hud.post("Switching to AlignEM_SWiFT Documentation")
            # don't force the reload, add home button instead
            self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))

        def documentation_view_home():
            logging.info("Launching documentation view home | MainWindow.documentation_view_home...")
            self.browser_docs.setUrl(QUrl('https://github.com/mcellteam/swift-ir/blob/joel-dev/README.md'))
            # self.set_status("AlignEM_SWiFT Documentation")

        def remote_view():
            logging.info("Launching remote viewer | MainWindow.remote_view...")
            self.stacked_widget.setCurrentIndex(4)
            self.hud.post("Switching to Remote Neuroglancer Viewer (https://neuroglancer-demo.appspot.com/)")
            self.browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))

        # webgl2
        def microns_view():
            logging.info("Launching microns viewer | MainWindow.microns_view...")
            self.stacked_widget.setCurrentIndex(5)
            self.browser_microns.setUrl(QUrl(
                    'https://neuromancer-seung-import.appspot.com/#!%7B%22layers%22:%5B%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v0/son_of_alignment_v15_rechunked%22%2C%22type%22:%22image%22%2C%22blend%22:%22default%22%2C%22shaderControls%22:%7B%7D%2C%22name%22:%22EM%22%7D%2C%7B%22source%22:%22precomputed://gs://microns_public_datasets/pinky100_v185/seg%22%2C%22type%22:%22segmentation%22%2C%22selectedAlpha%22:0.51%2C%22segments%22:%5B%22648518346349538235%22%2C%22648518346349539462%22%2C%22648518346349539853%22%5D%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22cell_segmentation_v185%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-clefts/mip1_d2_1175k%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22synapses%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-mito/seg_191220%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22mitochondria%22%7D%2C%7B%22source%22:%22precomputed://matrix://sseung-archive/pinky100-nuclei/seg%22%2C%22type%22:%22segmentation%22%2C%22skeletonRendering%22:%7B%22mode2d%22:%22lines_and_points%22%2C%22mode3d%22:%22lines%22%7D%2C%22name%22:%22nuclei%22%7D%5D%2C%22navigation%22:%7B%22pose%22:%7B%22position%22:%7B%22voxelSize%22:%5B4%2C4%2C40%5D%2C%22voxelCoordinates%22:%5B83222.921875%2C52981.34765625%2C834.9962768554688%5D%7D%7D%2C%22zoomFactor%22:383.0066650796121%7D%2C%22perspectiveOrientation%22:%5B-0.00825042650103569%2C0.06130112707614899%2C-0.0012821174459531903%2C0.9980843663215637%5D%2C%22perspectiveZoom%22:3618.7659948513424%2C%22showSlices%22:false%2C%22selectedLayer%22:%7B%22layer%22:%22cell_segmentation_v185%22%7D%2C%22layout%22:%7B%22type%22:%22xy-3d%22%2C%22orthographicProjection%22:true%7D%7D'))
            # self.set_status("MICrONS (http://layer23.microns-explorer.org)")
            # self.browser_microns.setUrl(QUrl('https://get.webgl.org/webgl2/'))
            # self.set_status("Checking WebGL2.0 support.")

        def reload_ng():
            logging.info("Reloading Neuroglancer...")
            ng_view()

        def reload_remote():
            logging.info("Reloading remote viewer...")
            remote_view()

        def exit_ng():
            logging.info("Exiting Neuroglancer...")
            self.stacked_widget.setCurrentIndex(0)
            self.set_idle()

        def exit_docs():
            logging.info("Exiting docs...")
            self.stacked_widget.setCurrentIndex(0)
            self.set_idle()

        def exit_remote():
            logging.info("Exiting remote viewer...")
            self.stacked_widget.setCurrentIndex(0)
            self.set_idle()

        def exit_demos():
            logging.info("Exiting demos...")
            self.stacked_widget.setCurrentIndex(0)
            self.set_idle()

        def print_state_ng():
            # viewer_state = json.loads(str(self.viewer.state))
            print(self.viewer.state)

            # print("Viewer.url : ", self.viewer.get_viewer_url)
            # print("Viewer.screenshot : ", self.viewer.screenshot)
            # print("Viewer.txn : ", self.viewer.txn)
            # print("Viewer.actions : ", self.viewer.actions)
            # time.sleep(1)
            # self.set_status("Viewing aligned images in Neuroglancer.")

        def print_url_ng():
            print(ng.to_url(self.viewer.state))
            # print("\nURL : " + self.viewer.get_viewer_url() + "\n")

            # print("Viewer.url : ", self.viewer.get_viewer_url)
            # print("Viewer.screenshot : ", self.viewer.screenshot)
            # print("Viewer.txn : ", self.viewer.txn)
            # print("Viewer.actions : ", self.viewer.actions)
            # time.sleep(1)
            # self.set_status("Viewing aligned images in Neuroglancer.")
            print("\n")

        # def screenshot_ng():
        #     self.set_status("Taking screenshot...")
        #     ScreenshotSaver.capture(self)

        def blend_ng():
            print("blend_ng():")
            # self.set_status("Making blended image...")

        def ng_view_2():
            print()

        # ngview
        def ng_view():  # ng_view #ngview #neuroglancer
            print("\n>>>>>>>>>>>>>>>> RUNNING ng_view()\n")
            print("ng_view() | # of aligned images                  : ", get_num_aligned())
            if not are_aligned_images_generated():
                self.hud.post('This scale must be aligned and exported before viewing in Neuroglancer')

                show_warning("No Alignment Found",
                             "This scale must be aligned and exported before viewing in Neuroglancer.\n\n"
                             "Typical workflow:\n"
                             "(1) Open a project or import images and save.\n"
                             "(2) Generate a set of scaled images and save.\n"
                             "--> (3) Align each scale starting with the coarsest.\n"
                             "--> (4) Export alignment to Zarr format.\n"
                             "(5) View data in Neuroglancer client")
                print(
                    "ng_view() | Warning | This scale must be aligned and exported before viewing in Neuroglancer - Returning")
                self.set_idle()
                return
            else:
                print('ng_view() | Alignment at this scale exists - Continuing')

            if not is_cur_scale_exported():
                self.hud.post('Alignment must be exported before it can be viewed in Neuroglancer')

                show_warning("No Export Found",
                             "Alignment must be exported before it can be viewed in Neuroglancer.\n\n"
                             "Typical workflow:\n"
                             "(1) Open a project or import images and save.\n"
                             "(2) Generate a set of scaled images and save.\n"
                             "(3) Align each scale starting with the coarsest.\n"
                             "--> (4) Export alignment to Zarr format.\n"
                             "(5) View data in Neuroglancer client")
                print(
                    "ng_view() | WARNING | Alignment must be exported before it can be viewed in Neuroglancer - Returning")
                self.set_idle()
                return
            else:
                print('ng_view() | Exported alignment at this scale exists - Continuing')

            ds_name = "aligned_" + get_cur_scale_key()
            destination_path = os.path.abspath(cfg.project_data['data']['destination_path'])
            zarr_project_path = os.path.join(destination_path, "project.zarr")
            zarr_ds_path = os.path.join(destination_path, "project.zarr", ds_name)

            print('ng_view() | zarr_project_path                    :', zarr_project_path)
            print('ng_view() | zarr_ds_path                         :', zarr_ds_path)
            print('ng_view() | zarr_ds_path exists?                 :', bool(os.path.isdir(zarr_ds_path)))

            self.hud.post('Loading Neuroglancer viewer...')
            self.hud.post("  source: '%s'" % zarr_ds_path)

            if 'server' in locals():
                print('ng_view() | server is already running')
            else:
                # self.browser.setUrl(QUrl()) #empty page
                print('ng_view() | no server found in local namespace -> starting RunnableServer() worker')
                worker = RunnableServer()
                self.threadpool.start(worker)

            os.chdir(zarr_project_path)  # refactor

            Image.MAX_IMAGE_PIXELS = None
            view = 'single'
            bind = '127.0.0.1'
            port = 9000
            res_x = 2
            res_y = 2
            res_z = 50

            src = zarr_project_path

            # LOAD METADATA - .zarray
            print('ng_view() | loading metadata from .zarray (array details) file')
            zarray_path = os.path.join(src, ds_name, "s0", ".zarray")
            print("zarray_path : ", zarray_path)
            with open(zarray_path) as f:
                zarray_keys = json.load(f)
            chunks = zarray_keys["chunks"]

            # cname = zarray_keys["compressor"]["cname"] #jy
            # clevel = zarray_keys["compressor"]["clevel"] #jy
            shape = zarray_keys["shape"]
            print("shape : ", shape)

            # LOAD META DATA - .zattrs
            print('ng_view() | loading metadata from .zattrs (attributes) file')
            zattrs_path = os.path.join(src, ds_name, "s0", ".zattrs")
            with open(zattrs_path) as f:
                zattrs_keys = json.load(f)
            print("zattrs_path : ", zattrs_path)
            resolution = zattrs_keys["resolution"]
            # scales = zattrs_keys["scales"]  #0405 #0406 #remove
            # print("scales : ", scales)  #0405 #0406 #remove

            ds_ref = "img_ref_zarr"
            ds_base = "img_base_zarr"
            ds_aligned = ds_name
            ds_blended = "img_blended_zarr"

            print('ng_view() | initializing neuroglancer.Viewer()')
            # viewer = ng.Viewer()
            self.viewer = ng.Viewer()

            print('ng_view() | looking for aligned data')
            data_aligned = []
            aligned_scale_paths = glob(os.path.join(src, ds_aligned) + "/s*")
            for s in aligned_scale_paths:
                scale = os.path.join(ds_aligned, os.path.basename(s))
                print("ng_view() | 'daisy' is opening scale '%s' and appending aligned data" % s)
                data_aligned.append(open_ds(src, scale))

            if view == 'row':
                print("Looking for REF scale directories...")
                data_ref = []
                ref_scale_paths = glob(os.path.join(src, ds_ref) + "/s*")
                for s in ref_scale_paths:
                    scale = os.path.join(ds_ref, os.path.basename(s))
                    print("ng_view() | 'daisy' is opening scale '%s' and appending aligned data" % s)
                    data_ref.append(open_ds(src, scale))

                print('Looking for BASE scale directories...')
                data_base = []
                base_scale_paths = glob(os.path.join(src, ds_base) + "/s*")
                for s in base_scale_paths:
                    scale = os.path.join(ds_base, os.path.basename(s))
                    print("ng_view() | 'daisy' is opening scale '%s' and appending aligned data" % s)
                    data_base.append(open_ds(src, scale))

            print('ng_view() | defining Neuroglancer coordinate space')
            dimensions = ng.CoordinateSpace(
                    names=['x', 'y', 'z'],
                    units='nm',
                    scales=[res_x, res_y, res_z],
            )

            # https://github.com/google/neuroglancer/blob/master/src/neuroglancer/viewer.ts
            print('ng_view() | updating viewer.txn()')
            with self.viewer.txn() as s:

                # s.cross_section_background_color = "#ffffff"
                s.cross_section_background_color = "#000000"
                s.dimensions = dimensions
                # s.perspective_zoom = 300
                # s.position = [0.24, 0.095, 0.14]
                # s.projection_orientation = [-0.205, 0.053, -0.0044, 0.97]

                # temp = np.zeros_like(data_ref)
                # layer = ng.Layer(temp)

                # print("type(data_aligned) = ", type(data_aligned))  # <class 'list'>
                # print("type(data_aligned[0]) = ", type(data_aligned[0]))  # <class 'daisy.array.Array'>
                # print("len(data_aligned) = ", len(data_aligned))  # 2

                array = np.asarray(data_aligned)
                # print("type(array) = ", type(array))                       # <class 'numpy.ndarray'>
                # print("array.shape = ", array.shape)                       # (2,)
                # print("array.size = ", array.size)                         # 2
                # print("array.ndim = ", array.ndim)                         # 1

                print('ng_view() | type(np.asarray(data_aligned))       :', type(np.asarray(data_aligned)))
                print('ng_view() | np.asarray(data_aligned).shape       :', np.asarray(data_aligned).shape)
                print('ng_view() | np.asarray(data_aligned).size        :', np.asarray(data_aligned).size)
                print('ng_view() | np.asarray(data_aligned).ndim        :', np.asarray(data_aligned).ndim)

                print("ng_view() | 'view' is set to                     :", view)
                # only for 3 pane view
                if view == 'row':
                    add_layer(s, data_ref, 'ref')
                    add_layer(s, data_base, 'base')

                add_layer(s, data_aligned, 'aligned')

                ###data_panel_layout_types: frozenset(['xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d', '4panel', '3d'])

                # s.selectedLayer.visible = False
                # s.layers['focus'].visible = False

                # view = "single"
                if view == "row":
                    print("ng_view() | view is 'row'")

                    s.layers['focus'].visible = True

                    # [
                    #     ng.LayerGroupViewer(layers=["focus"], layout='xy'),

                    # temp = np.zeros_like(data_ref)
                    # #layer = ng.Layer()
                    # #layer = ng.ManagedLayer
                    # s.layers['focus'] = ng.LocalVolume(temp)
                    # s.layers['focus'] = ng.ManagedLayer(source="zarr://http://localhost:9000/img_blended_zarr",voxel_size=[i * .00000001 for i in resolution])
                    s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
                    s.layout = ng.column_layout(
                            [
                                    ng.row_layout(
                                            [
                                                    ng.LayerGroupViewer(layers=["focus"], layout='xy'),
                                            ]
                                    ),

                                    ng.row_layout(
                                            [
                                                    ng.LayerGroupViewer(layers=['ref'], layout='xy'),
                                                    ng.LayerGroupViewer(layers=['base'], layout='xy'),
                                                    ng.LayerGroupViewer(layers=['aligned'], layout='xy'),
                                            ]
                                    ),
                            ]
                    )

                    # s.layout = ng.column_layout(
                    #
                    #     [
                    #         ng.LayerGroupViewer(layers=["focus"], layout='xy'),
                    #
                    # s.layers['focus'] = ng.ImageLayer(source="zarr://http://localhost:9000/img_blended_zarr/")
                    #
                    # ng.row_layout(
                    #     [
                    #         ng.LayerGroupViewer(layers=["ref"], layout='xy'),
                    #         ng.LayerGroupViewer(layers=["base"], layout='xy'),
                    #         ng.LayerGroupViewer(layers=["aligned"], layout='xy'),
                    #     ]
                    # )
                    #
                    #
                    #
                    #
                    #     ]
                    #
                    # ]
                    # # )

                # single image view
                if view == "single":
                    s.layout = ng.column_layout(
                            [
                                    ng.LayerGroupViewer(
                                            layout='xy',
                                            layers=["aligned"]),
                            ]
                    )

            print('ng_view() | loading Neuroglancer callbacks       :', self.viewer.config_state)
            self.viewer.actions.add('get_mouse_coords_', get_mouse_coords)
            # self.viewer.actions.add('unchunk_', unchunk)
            # self.viewer.actions.add('blend_', blend)
            with self.viewer.config_state.txn() as s:
                s.input_event_bindings.viewer['keyt'] = 'get_mouse_coords_'
                # s.input_event_bindings.viewer['keyu'] = 'unchunk_'
                # s.input_event_bindings.viewer['keyb'] = 'blend_'
                # s.status_messages['message'] = 'Welcome to AlignEM_SWiFT!'

                s.show_ui_controls = True
                s.show_panel_borders = True
                s.viewer_size = None

            viewer_url = str(self.viewer)
            # viewer_url = self.viewer
            self.browser.setUrl(QUrl(viewer_url))
            self.stacked_widget.setCurrentIndex(1)

            # To modify the state, use the viewer.txn() function, or viewer.set_state
            print('ng_view() | Viewer.config_state                  :', self.viewer.config_state)
            # print('ng_view() | viewer URL                           :', self.viewer.get_viewer_url())
            # print('Neuroglancer view (remote viewer)                :', ng.to_url(viewer.state))

            cur_scale = get_cur_scale_key()
            self.hud.post('Viewing aligned images at scale ' + cur_scale[-1] + ' in Neuroglancer.')

            print("\n<<<<<<<<<<<<<<<< EXITING ng_view()\n")

        if panel_roles != None:
            cfg.project_data['data']['panel_roles'] = panel_roles

        self.draw_border = False
        self.draw_annotations = True
        self.panel_list = []

        def pretty(d, indent=0):
            for key, value in d.items():
                print('\t' * indent + str(key))
                if isinstance(value, dict):
                    pretty(value, indent + 1)
                else:
                    print('\t' * (indent + 1) + str(value))

        def show_memory_usage():
            os.system('python3 memoryusage.py')

        '''------------------------------------------
        PROJECT INSPECTOR #projectinspector
        ------------------------------------------'''
        # self.inspector_label_skips = QLabel('')
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

        # Project Status

        # Skips List
        self.inspector_scales = CollapsibleBox('Skip List')

        dock_vlayout.addWidget(self.inspector_scales)
        lay = QVBoxLayout()

        self.inspector_label_skips.setStyleSheet(
                "color: #d3dae3;"
                "border-radius: 12px;"
            )
        lay.addWidget(self.inspector_label_skips, alignment=Qt.AlignTop)
        self.inspector_scales.setContentLayout(lay)

        # CPU Specs
        self.inspector_cpu = CollapsibleBox('CPU Specs')
        dock_vlayout.addWidget(self.inspector_cpu)
        lay = QVBoxLayout()
        label = QLabel("CPU #: %s\nSystem : %s" % ( psutil.cpu_count(logical=False), platform.system() ))
        label.setStyleSheet(
                "color: #d3dae3;"
                "border-radius: 12px;"
            )
        # lay.addWidget(label, alignment=alignEM.AlignTop)    #0610
        lay.addWidget(label, alignment=Qt.AlignTop)
        self.inspector_cpu.setContentLayout(lay)

        dock_vlayout.addStretch()

        '''------------------------------------------
        PANEL 1: PROJECT #projectpanel
        ------------------------------------------'''

        self.new_project_button = QPushButton(" New")
        self.new_project_button.clicked.connect(self.new_project)
        self.new_project_button.setFixedSize(square_button_size)
        # self.new_project_button.setIcon(qta.icon("ei.stackoverflow", color=cfg.ICON_COLOR))
        # self.new_project_button.setIcon(qta.icon("ph.stack-fill", color=cfg.ICON_COLOR))
        self.new_project_button.setIcon(qta.icon("msc.add", color=cfg.ICON_COLOR))
        # self.new_project_button.setIconSize(QSize(20, 20))

        self.open_project_button = QPushButton(" Open")
        self.open_project_button.clicked.connect(self.open_project)
        self.open_project_button.setFixedSize(square_button_size)
        self.open_project_button.setIcon(qta.icon("fa.folder-open", color=cfg.ICON_COLOR))

        self.save_project_button = QPushButton(" Save")
        self.save_project_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_project_button.clicked.connect(self.save_project)
        self.save_project_button.setFixedSize(square_button_size)
        self.save_project_button.setIcon(qta.icon("mdi.content-save", color=cfg.ICON_COLOR))

        # self.documentation_button = QPushButton("Docs")
        self.documentation_button = QPushButton(" Help")
        self.documentation_button.clicked.connect(documentation_view)
        self.documentation_button.setFixedSize(square_button_size)
        # self.documentation_button.setIcon(qta.icon("fa.github", color=cfg.ICON_COLOR))
        self.documentation_button.setIcon(qta.icon("mdi.help", color=cfg.ICON_COLOR))

        self.exit_app_button = QPushButton(" Exit")
        self.exit_app_button.clicked.connect(self.exit_app)
        self.exit_app_button.setFixedSize(square_button_size)
        # self.exit_app_button.setIcon(qta.icon("mdi.exit-to-app", color=cfg.ICON_COLOR))
        self.exit_app_button.setIcon(qta.icon("mdi6.close", color=cfg.ICON_COLOR))

        self.remote_viewer_button = QPushButton("Neuroglancer\nServer")
        self.remote_viewer_button.clicked.connect(remote_view)
        self.remote_viewer_button.setFixedSize(square_button_size)
        self.remote_viewer_button.setStyleSheet("font-size: 9px;")

        self.project_functions_layout = QGridLayout()
        self.project_functions_layout.setContentsMargins(10, 25, 10, 5)
        # self.project_functions_layout.setSpacing(10)  # ***
        self.project_functions_layout.addWidget(self.new_project_button, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.open_project_button, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.save_project_button, 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.exit_app_button, 1, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.documentation_button, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        self.project_functions_layout.addWidget(self.remote_viewer_button, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        '''------------------------------------------
        PANEL 2: DATA SELECTION & SCALING
        ------------------------------------------'''
        # datapanel #scalingpanel #importpanel

        self.import_images_button = QPushButton(" Import\n Images")
        self.import_images_button.setToolTip('Import TIFF images.')
        self.import_images_button.clicked.connect(self.import_images)
        self.import_images_button.setFixedSize(square_button_size)
        # self.import_images_button.setIcon(qta.icon("ph.stack-fill", color=cfg.ICON_COLOR))
        self.import_images_button.setIcon(qta.icon("fa5s.file-import", color=cfg.ICON_COLOR))
        self.import_images_button.setStyleSheet("font-size: 10px;")
        # self.import_images_button.setFixedSize(square_button_width, std_height)

        self.center_button = QPushButton('Center')
        self.center_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.center_button.setToolTip('Center all images.')
        self.center_button.clicked.connect(self.center_all_images)
        self.center_button.setFixedSize(square_button_width, std_height)
        self.center_button.setStyleSheet("font-size: 10px;")

        self.project_view_button = QPushButton('Inspect\nJSON')
        self.project_view_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.project_view_button.setToolTip('Inspect the project dictionary in memory.')
        self.project_view_button.clicked.connect(self.project_view_callback)
        self.project_view_button.setFixedSize(square_button_size)
        self.project_view_button.setStyleSheet("font-size: 10px;")

        self.print_sanity_check_button = QPushButton("Print\nSanity Check")
        self.print_sanity_check_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.print_sanity_check_button.clicked.connect(print_sanity_check)
        self.print_sanity_check_button.setFixedSize(square_button_size)
        self.print_sanity_check_button.setStyleSheet("font-size: 9px;")

        self.print_bias_data_button = QPushButton("Print\nBias Data")
        self.print_bias_data_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.print_bias_data_button.clicked.connect(print_dat_files)
        self.print_bias_data_button.setFixedSize(square_button_size)
        self.print_bias_data_button.setStyleSheet("font-size: 9px;")

        self.actual_size_button = QPushButton('Actual Size')
        self.actual_size_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.actual_size_button.setToolTip('Actual-size all images.')
        self.actual_size_button.clicked.connect(self.actual_size_callback)
        self.actual_size_button.setFixedSize(square_button_width, std_height)
        self.actual_size_button.setStyleSheet("font-size: 10px;")

        self.size_buttons_vlayout = QVBoxLayout()
        self.size_buttons_vlayout.addWidget(self.center_button)
        self.size_buttons_vlayout.addWidget(self.actual_size_button)

        self.generate_scales_button = QPushButton('Generate\nScales')
        self.generate_scales_button.setToolTip('Generate scale pyramid with chosen # of levels.')
        # self.generate_scales_button.clicked.connect(generate_scales_queue)
        self.generate_scales_button.clicked.connect(self.run_scaling)
        # self.generate_scales_button.clicked.connect(self.startProgressBar)

        # popupprogressbar


        self.generate_scales_button.setFixedSize(square_button_size)
        self.generate_scales_button.setStyleSheet("font-size: 10px;")
        self.generate_scales_button.setIcon(qta.icon("mdi.image-size-select-small", color=cfg.ICON_COLOR))
        self.generate_scales_button.setEnabled(False)

        # self.clear_all_skips_button = QPushButton('Reset')
        self.clear_all_skips_button = QPushButton()
        self.clear_all_skips_button.setToolTip('Reset skips (keep all)')
        self.clear_all_skips_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_all_skips_button.clicked.connect(self.clear_all_skips_callback)
        self.clear_all_skips_button.setFixedSize(std_height, std_height)
        self.clear_all_skips_button.setIcon(qta.icon("mdi.undo", color=cfg.ICON_COLOR))

        self.toggle_skip = ToggleSwitch()
        self.skip_label = QLabel("Include:")
        # self.skip_label.setPointSize(9)
        # self.skip_label.setFixedSize(80, 30)

        self.skip_layout = QHBoxLayout()
        self.skip_layout.setAlignment(Qt.AlignCenter)
        self.skip_layout.addStretch()
        self.skip_layout.addWidget(self.skip_label)
        self.skip_layout.addWidget(self.toggle_skip)
        self.skip_layout.addStretch(4)
        self.toggle_skip.setToolTip('Skip current image (do not align)')
        self.skip_label.setToolTip('Skip current image (do not align)')
        # self.toggle_skip.setChecked(True)
        self.toggle_skip.setChecked(False)
        # self.toggle_skip.setH_scale(.9)
        # self.toggle_skip.setV_scale(1.0)
        self.toggle_skip.toggled.connect(skip_changed_callback)

        self.jump_label = QLabel("Go to:")
        self.jump_input = QLineEdit(self)
        self.jump_input.setToolTip('Jump to image #')
        self.jump_input.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        # self.jump_input.setText("--")
        self.jump_input.setFixedSize(std_input_size, std_height)
        self.jump_validator = QIntValidator()
        self.jump_input.setValidator(self.jump_validator)
        # self.jump_input.returnPressed.connect(self.jump_to_layer())
        self.jump_input.returnPressed.connect(lambda: self.jump_to_layer())  # must be lambda for some reason
        # self.jump_input.editingFinished.connect(self.jump_to_layer())
        # self.jump_hlayout = QHBoxLayout()
        # self.jump_hlayout.addWidget(jump_label, alignment=alignEM.AlignmentFlag.AlignLeft)
        # self.jump_hlayout.addWidget(self.jump_input, alignment=alignEM.AlignmentFlag.AlignRight)

        self.images_and_scaling_layout = QGridLayout()
        self.images_and_scaling_layout.setContentsMargins(10, 25, 10, 5)  # tag23
        # self.images_and_scaling_layout.setSpacing(10) # ***
        self.images_and_scaling_layout.addWidget(self.import_images_button, 0, 0,
                                                 alignment=Qt.AlignmentFlag.AlignHCenter)
        # self.images_and_scaling_layout.addWidget(self.center_button, 0, 1, alignment=alignEM.AlignmentFlag.AlignHCenter)
        self.images_and_scaling_layout.addLayout(self.size_buttons_vlayout, 0, 1,
                                                 alignment=Qt.AlignmentFlag.AlignHCenter)
        self.images_and_scaling_layout.addWidget(self.generate_scales_button, 0, 2,
                                                 alignment=Qt.AlignmentFlag.AlignHCenter)
        self.toggle_reset_hlayout = QHBoxLayout()
        self.toggle_reset_hlayout.addWidget(self.clear_all_skips_button)
        # self.toggle_reset_hlayout.addWidget(self.toggle_skip, alignment=alignEM.AlignmentFlag.AlignLeft)
        # self.toggle_reset_hlayout.addWidget(self.toggle_skip, alignment=alignEM.AlignmentFlag.AlignLeft)
        self.toggle_reset_hlayout.addLayout(self.skip_layout)
        self.toggle_reset_hlayout.addWidget(self.jump_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.toggle_reset_hlayout.addWidget(self.jump_input, alignment=Qt.AlignmentFlag.AlignHCenter)
        # self.toggle_reset_hlayout.addLayout(self.jump_hlayout, alignment=alignEM.AlignmentFlag.AlignHCenter)
        # self.images_and_scaling_layout.addWidget(self.toggle_skip, 1, 0, alignment=alignEM.AlignmentFlag.AlignHCenter)
        # self.images_and_scaling_layout.addWidget(self.clear_all_skips_button, 1, 1, alignment=alignEM.AlignmentFlag.AlignHCenter)
        self.images_and_scaling_layout.addLayout(self.toggle_reset_hlayout, 1, 0, 1, 3)
        self.images_and_scaling_layout.addWidget(self.print_sanity_check_button, 2, 0)
        self.images_and_scaling_layout.addWidget(self.print_bias_data_button, 2, 1)
        self.images_and_scaling_layout.addWidget(self.project_view_button, 2, 2)
        # self.images_and_scaling_layout.addLayout(self.jump_hlayout, 1, 1, 1, 2, alignment=alignEM.AlignmentFlag.AlignRight)

        '''------------------------------------------
        PANEL 3: ALIGNMENT
        ------------------------------------------'''
        # alignmentpanel

        self.scales_combobox = QComboBox(self)
        # self.scales_combobox.addItems([skip_list])
        # self.scales_combobox.addItems(['--'])
        self.scales_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scales_combobox.setFixedSize(std_button_size)
        self.scales_combobox.currentTextChanged.connect(self.fn_scales_combobox)

        self.affine_combobox = QComboBox(self)
        self.affine_combobox.addItems(['Init Affine', 'Refine Affine', 'Apply Affine'])
        self.affine_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.affine_combobox.setFixedSize(std_button_size)

        # ^^ this should perhaps be connected to a function that updates python_swiftir in project file (immediately).. not sure yet
        # on second thought, the selected option here ONLY matters at alignment time
        # in the meantime, best temporary functionality is to just make sure that whatever item is selected when the
        #   alignment button is pressed will always be the python_swiftir used for alignment
        # saving python_swiftir data to project file might ultimately be needed, but this is good for now.

        # Whitening LineEdit
        self.whitening_label = QLabel("Whitening:")
        # self.whitening_label.setFont(QFont('Terminus', 12, QFont.Bold))
        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.whitening_label.setToolTip(wrapped)
        self.whitening_input = QLineEdit(self)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setFixedWidth(std_input_size)
        self.whitening_input.setFixedHeight(std_height)
        self.whitening_input.setValidator(QDoubleValidator(-5.0, 5.0, 2, self))

        # Swim Window LineEdit
        self.swim_label = QLabel("SWIM Window:")
        # self.swim_label.setFont(QFont('Terminus', 12, QFont.Bold))
        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.swim_label.setToolTip(wrapped)
        self.swim_input = QLineEdit(self)
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setFixedWidth(std_input_size)
        self.swim_input.setFixedHeight(std_height)
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))

        self.whitening_grid = QGridLayout()
        self.whitening_grid.setContentsMargins(0, 0, 0, 0)
        self.whitening_grid.addWidget(self.whitening_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.whitening_grid.addWidget(self.whitening_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.swim_grid = QGridLayout()
        self.swim_grid.setContentsMargins(0, 0, 0, 0)
        self.swim_grid.addWidget(self.swim_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.swim_grid.addWidget(self.swim_input, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        # Apply All Button
        # self.apply_all_label = QLabel("Apply Settings All:")
        self.apply_all_label = QLabel("Apply All:")
        # self.apply_all_label.setFont(QFont('Terminus', 12, QFont.Bold))
        # self.apply_all_button = QPushButton('Apply To All')
        self.apply_all_button = QPushButton()
        self.apply_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.apply_all_button.setToolTip('Apply these settings to the entire project.')
        self.apply_all_button.clicked.connect(self.apply_all_callback)
        # self.apply_all_button.setFixedSize(std_button_size)
        self.apply_all_button.setFixedSize(std_height, std_height)
        # self.apply_all_button.setIcon(qta.icon("fa.mail-forward", color=cfg.ICON_COLOR))
        self.apply_all_button.setIcon(qta.icon("mdi6.transfer", color=cfg.ICON_COLOR))

        self.apply_all_layout = QGridLayout()
        self.apply_all_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_all_layout.addWidget(self.apply_all_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.apply_all_layout.addWidget(self.apply_all_button, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)

        # Next Scale Button
        self.next_scale_button = QPushButton('Next Scale ')
        self.next_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_scale_button.setToolTip('Go forward to the next scale.')
        self.next_scale_button.clicked.connect(self.next_scale_button_callback)
        self.next_scale_button.setFixedSize(std_button_size)
        self.next_scale_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.next_scale_button.setIcon(qta.icon("ri.arrow-right-line", color=cfg.ICON_COLOR))
        # self.next_scale_button.setStyleSheet("font-size: 10px;")

        # Previous Scale Button
        self.prev_scale_button = QPushButton(' Prev Scale')
        self.prev_scale_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_scale_button.setToolTip('Go back to the previous scale.')
        self.prev_scale_button.clicked.connect(self.prev_scale_button_callback)
        self.prev_scale_button.setFixedSize(std_button_size)
        # self.prev_scale_button.setFixedSize(square_button_width, std_height)
        self.prev_scale_button.setIcon(qta.icon("ri.arrow-left-line", color=cfg.ICON_COLOR))
        # self.prev_scale_button.setStyleSheet("font-size: 10px;")

        # Align All Button
        self.align_all_button = QPushButton('Align Stack')
        self.align_all_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.align_all_button.setToolTip('Align This Scale')
        # self.align_all_button.clicked.connect(align_all_or_some) #orig
        # self.align_all_button.clicked.connect(self.run_alignment)
        self.align_all_button.clicked.connect(self.run_alignment)
        # self.align_all_button.clicked.connect(self.startProgressBar)

        # self.align_all_button.setFixedSize(square_button_width, std_height)
        self.align_all_button.setFixedSize(std_button_size)
        # self.align_all_button.setIcon(qta.icon("mdi.format-align-middle", color=cfg.ICON_COLOR))
        self.align_all_button.setIcon(qta.icon("ph.stack-fill", color=cfg.ICON_COLOR))
        # self.align_all_button.setStyleSheet("font-size: 10px;")

        # pixmap = getattr(QStyle, 'SP_MediaPlay')
        # icon = self.style().standardIcon(pixmap)
        # self.align_all_button.setIcon(icon)
        # self.align_all_button.setLayoutDirection(alignEM.RightToLeft)

        self.alignment_status_label = QLabel("Is Aligned: ")
        self.alignment_status_label.setFont(QFont('Terminus', 12, QFont.Bold))
        self.alignment_status_label.setToolTip('Alignment status')
        # self.alignment_status_checkbox = QCheckBox()
        self.alignment_status_checkbox = QRadioButton()
        self.alignment_status_checkbox.setEnabled(False)
        self.alignment_status_checkbox.setToolTip('Alignment status')
        self.alignment_status_layout = QHBoxLayout()
        self.alignment_status_layout.addWidget(self.alignment_status_label)
        self.alignment_status_layout.addWidget(self.alignment_status_checkbox)

        self.align_label_resolution = QLabel()
        self.align_label_resolution.setFont(QFont('Terminus', 12, QFont.Bold))
        self.align_label_affine = QLabel()
        self.align_label_affine.setFont(QFont('Terminus', 12, QFont.Bold))
        self.align_label_scales_remaining = QLabel()
        self.align_label_scales_remaining.setFont(QFont('Terminus', 12, QFont.Bold))
        self.align_details_layout = QGridLayout()
        self.align_details_layout.addWidget(self.align_label_resolution, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_details_layout.addWidget(self.align_label_affine, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_details_layout.addLayout(self.alignment_status_layout, 0, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_details_layout.addWidget(self.align_label_scales_remaining, 1, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self.align_details_layout.setContentsMargins(5, 5, 15, 5)

        # Auto-generate Toggle
        # Current implementation is not data-driven.
        self.auto_generate_label = QLabel("Auto-generate Images:")
        self.auto_generate_label.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate = ToggleSwitch()  # toggleboundingrect
        self.toggle_auto_generate.setToolTip('Automatically generate aligned images.')
        self.toggle_auto_generate.setChecked(True)
        # self.toggle_auto_generate.setV_scale(.6)
        # self.toggle_auto_generate.setH_scale(.8)
        self.toggle_auto_generate.toggled.connect(self.toggle_auto_generate_callback)
        self.toggle_auto_generate_hlayout = QHBoxLayout()
        self.toggle_auto_generate_hlayout.addWidget(self.auto_generate_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_auto_generate_hlayout.addWidget(self.toggle_auto_generate, alignment=Qt.AlignmentFlag.AlignRight)

        # self.scale_tabs = QTabWidget()
        self.alignment_layout = QGridLayout()
        self.alignment_layout.setContentsMargins(10, 25, 10, 0)  # tag23
        self.alignment_layout.addLayout(self.swim_grid, 0, 0, 1, 2)
        self.alignment_layout.addLayout(self.whitening_grid, 1, 0, 1, 2)
        self.alignment_layout.addWidget(self.prev_scale_button, 0, 2)
        self.alignment_layout.addWidget(self.next_scale_button, 1, 2)
        self.alignment_layout.addLayout(self.apply_all_layout, 2, 0, 1, 2)
        self.alignment_layout.addWidget(self.align_all_button, 2, 2)
        # self.alignment_layout.addLayout(self.toggle_auto_generate_hlayout, 3, 0)
        self.align_details_layout_tweak = QVBoxLayout()
        self.align_details_layout_tweak.setAlignment(Qt.AlignCenter)
        # layout.addStretch()
        self.align_line = QFrame()
        self.align_line.setGeometry(QRect(60, 110, 751, 20))
        self.align_line.setFrameShape(QFrame.HLine)
        self.align_line.setFrameShadow(QFrame.Sunken)
        self.align_line.setStyleSheet("""background-color: #455364;""")
        # self.align_line.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        # self.align_line.setLineWidth(3)
        # self.align_details_gb = QGroupBox()
        # self.align_details_gb.setLayout(self.align_details_layout_tweak)


        self.align_details_layout_tweak.addWidget(self.align_line)
        self.align_details_layout_tweak.addLayout(self.align_details_layout)
        self.align_details_layout_tweak.setContentsMargins(0,10,0,0)
        # self.alignment_layout.addLayout(self.align_details_layout_tweak, 3, 0, 1, 3)
        self.alignment_layout.addLayout(self.align_details_layout_tweak, 3, 0, 1, 3)


        '''------------------------------------------
        PANEL 3.5: Post-alignment
        ------------------------------------------'''
        # postalignmentpanel

        # Null Bias combobox
        self.null_bias_label = QLabel("Bias:")
        tip = 'Polynomial bias (default=None). Note: This affects the alignment and the pixel dimensions of the generated images.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.null_bias_label.setToolTip(wrapped)
        self.null_bias_combobox = QComboBox(self)
        self.null_bias_combobox.setToolTip(wrapped)
        self.null_bias_combobox.setToolTip('Polynomial bias (default=None)')
        self.null_bias_combobox.addItems(['None', '0', '1', '2', '3', '4'])
        self.null_bias_combobox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.null_bias_combobox.setFixedSize(std_button_size)
        self.null_bias_combobox.setFixedSize(72, std_height)

        self.poly_order_hlayout = QHBoxLayout()
        self.poly_order_hlayout.addWidget(self.null_bias_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.poly_order_hlayout.addWidget(self.null_bias_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        # Bounding Box toggle
        self.bounding_label = QLabel("Bounding Box:")
        tip = 'Bounding rectangle (default=ON). Caution: Turning this OFF will result in images that are the same size as the source images but may have missing data, while turning this ON will result in no missing data but may significantly increase the size of the generated images.'
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.bounding_label.setToolTip(wrapped)
        self.toggle_bounding_rect_switch = 1
        self.toggle_bounding_rect = ToggleSwitch()
        self.toggle_bounding_rect.setToolTip(wrapped)
        # self.toggle_bounding_rect.setChecked(True)
        # self.toggle_bounding_rect.setV_scale(.6)
        # self.toggle_bounding_rect.setH_scale(.8)
        self.toggle_bounding_rect.toggled.connect(bounding_rect_changed_callback)
        self.toggle_bounding_hlayout = QHBoxLayout()
        self.toggle_bounding_hlayout.addWidget(self.bounding_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.toggle_bounding_hlayout.addWidget(self.toggle_bounding_rect, alignment=Qt.AlignmentFlag.AlignRight)

        # Regenerate Button
        # mdi6.reload
        self.regenerate_label = QLabel('(Re)generate:')
        self.regenerate_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.regenerate_label.setToolTip('Regenerate aligned with adjusted settings')
        # self.regenerate_button = QPushButton('(Re-)Generate')
        self.regenerate_button = QPushButton()
        self.regenerate_button.setToolTip('Regenerate aligned with adjusted settings')
        # self.regenerate_button.setIcon(qta.icon("fa.refresh", color=cfg.ICON_COLOR))
        self.regenerate_button.setIcon(qta.icon("ri.refresh-line", color=cfg.ICON_COLOR))
        # self.regenerate_load_image_workerbutton.clicked.connect(regenerate_aligns)
        self.regenerate_button.clicked.connect(self.run_regenerate_alignment)
        self.regenerate_button.setFixedSize(std_height, std_height)

        self.regenerate_hlayout = QHBoxLayout()
        self.regenerate_hlayout.addWidget(self.regenerate_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.regenerate_hlayout.addWidget(self.regenerate_button, alignment=Qt.AlignmentFlag.AlignRight)

        # pixmap = getattr(QStyle, 'SP_BrowserReload')
        # icon = self.style().standardIcon(pixmap)
        # self.regenerate_button.setIcon(icon)
        # # self.regenerate_button.setLayoutDirection(alignEM.RightToLeft)
        self.postalignment_note = QLabel("Note: These settings adjust,\nbut do not alter the initial\nalignment.")
        self.postalignment_note.setFont(QFont('Terminus', 11, QFont.Light))
        self.postalignment_note.setContentsMargins(0, 0, 0, 0)
        self.postalignment_layout = QGridLayout()
        self.postalignment_layout.setContentsMargins(10, 25, 10, 5)

        self.postalignment_layout.addLayout(self.poly_order_hlayout, 0, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addLayout(self.toggle_bounding_hlayout, 1, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        # self.postalignment_layout.addWidget(self.regenerate_button, 2, 0, alignment=alignEM.AlignmentFlag.AlignCenter)
        self.postalignment_layout.addLayout(self.regenerate_hlayout, 2, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.postalignment_layout.addWidget(self.postalignment_note, 23, 0, alignment=Qt.AlignmentFlag.AlignBottom)

        '''------------------------------------------
        PANEL 4: EXPORT & VIEW
        ------------------------------------------'''
        n_scales_label = QLabel("# of scales:")
        n_scales_label.setToolTip("Number of scale pyramid layers (default=4)")
        self.n_scales_input = QLineEdit(self)
        self.n_scales_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.n_scales_input.setText("4")
        self.n_scales_input.setFixedWidth(std_input_size_small)
        self.n_scales_input.setFixedHeight(std_height)
        self.n_scales_valid = QIntValidator(1, 20, self)
        self.n_scales_input.setValidator(self.n_scales_valid)

        clevel_label = QLabel("clevel (1-9):")
        clevel_label.setToolTip("Zarr Compression Level (default=5)")
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clevel_input.setText("5")
        self.clevel_input.setFixedWidth(std_input_size_small)
        self.clevel_input.setFixedHeight(std_height)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)
        cname_label = QLabel("cname:")
        cname_label.setToolTip("Zarr Compression Type (default=zstd) ")
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setFixedSize(72, std_height)
        self.export_and_view_hbox = QHBoxLayout()
        self.export_zarr_button = QPushButton(" Export\n Zarr")
        tip = "To view data in Neuroglancer, it is necessary to export to a compatible " \
              "format such as Zarr. This function exports all aligned .TIF images for " \
              "current scale to the chunked and compressed Zarr (.zarr) format with " \
              "scale pyramid. Uses parallel processing."
        wrapped = "\n".join(textwrap.wrap(tip, width=35))
        self.export_zarr_button.setToolTip(wrapped)
        self.export_zarr_button.clicked.connect(self.export_zarr)
        self.export_zarr_button.setFixedSize(square_button_size)
        self.export_zarr_button.setStyleSheet("font-size: 10px;")
        # self.export_zarr_button.setIcon(qta.icon("fa5s.file-export", color=cfg.ICON_COLOR))
        self.export_zarr_button.setIcon(qta.icon("fa5s.cubes", color=cfg.ICON_COLOR))

        # self.ng_button = QPushButton("View In\nNeuroglancer")
        self.ng_button = QPushButton("3DEM")
        self.ng_button.setToolTip('View Zarr export in Neuroglancer.')
        self.ng_button.clicked.connect(ng_view)  # parenthesis were causing the member function to be evaluated early
        self.ng_button.setFixedSize(square_button_size)
        self.ng_button.setIcon(qta.icon("ph.cube-light", color=cfg.ICON_COLOR))
        # self.ng_button.setStyleSheet("font-size: 9px;")

        self.export_and_view_hlayout = QVBoxLayout()
        self.export_and_view_hlayout.addWidget(self.export_zarr_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.export_and_view_hlayout.addWidget(self.ng_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.n_scales_layout = QHBoxLayout()
        self.n_scales_layout.setContentsMargins(0, 0, 0, 0)
        self.n_scales_layout.addWidget(n_scales_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.n_scales_layout.addWidget(self.n_scales_input, alignment=Qt.AlignmentFlag.AlignRight)

        self.clevel_layout = QHBoxLayout()
        self.clevel_layout.setContentsMargins(0, 0, 0, 0)
        self.clevel_layout.addWidget(clevel_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignmentFlag.AlignRight)

        self.cname_layout = QHBoxLayout()
        # self.cname_layout.setContentsMargins(0,0,0,0)
        self.cname_layout.addWidget(cname_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignmentFlag.AlignRight)

        self.export_settings_grid_layout = QGridLayout()
        self.export_settings_grid_layout.addLayout(self.clevel_layout, 1, 0)
        self.export_settings_grid_layout.addLayout(self.cname_layout, 0, 0)
        self.export_settings_grid_layout.addLayout(self.n_scales_layout, 2, 0)
        self.export_settings_grid_layout.addLayout(self.export_and_view_hlayout, 0, 1, 3, 1)
        # self.export_settings_grid_layout.addWidget(self.export_zarr_button, 1, 1, alignment=alignEM.AlignmentFlag.AlignRight)
        # self.export_settings_grid_layout.addWidget(self.ng_button, 2, 1, alignment=alignEM.AlignmentFlag.AlignRight)
        self.export_settings_grid_layout.setContentsMargins(10, 25, 10, 5)  # tag23

        '''------------------------------------------
        INTEGRATED CONTROL PANEL
        ------------------------------------------'''
        # controlpanel
        # cpanel_height = 138
        # cpanel_height = 150
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
        self.images_and_scaling_groupbox.setLayout(self.images_and_scaling_layout)
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
        self.export_and_view_groupbox.setLayout(self.export_settings_grid_layout)
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
        # self.lower_panel_groups.setFixedHeight(cpanel_height + 10)
        # self.main_panel_layout.addLayout(self.lower_panel_groups) #**
        # self.main_panel_layout.setAlignment(alignEM.AlignmentFlag.AlignHCenter)

        '''------------------------------------------
        MAIN LAYOUT
        ------------------------------------------'''

        self.image_panel = MultiImagePanel()
        self.image_panel.setFocusPolicy(Qt.StrongFocus)
        self.image_panel.setFocus()
        self.image_panel.draw_annotations = self.draw_annotations
        # self.image_panel.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding) #0610
        self.image_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_panel.setMinimumHeight(400)

        self.bottom_panel_stacked_widget = QStackedWidget()
        self.bottom_panel_stacked_widget.addWidget(self.hud)
        # self.bottom_panel_plot_widget = QWidget()
        # self.bottom_panel_plot_layout = QVBoxLayout()
        # self.bottom_panel_plot_widget.
        self.plot_widget = pg.PlotWidget()
        self.bottom_panel_stacked_widget.addWidget(self.plot_widget)
        self.bottom_panel_stacked_widget.setCurrentIndex(0)


        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.image_panel)
        self.splitter.addWidget(self.lower_panel_groups)
        # self.splitter.addWidget(self.hud)
        self.splitter.addWidget(self.bottom_panel_stacked_widget)

        # self.splitter.addWidget(self.progress_bar)
        # self.progress_bar.setGeometry(200, 80, 250, 20)
        # https://stackoverflow.com/questions/14397653/qsplitter-with-one-fixed-size-widget-and-one-variable-size-widget
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, True)

        self.main_panel = QWidget()
        # self.main_panel_layout = QVBoxLayout()
        self.main_panel_layout = QGridLayout()
        self.main_panel_layout.setSpacing(4)  # this will inherit downward

        self.main_panel_layout.addWidget(self.splitter, 1, 0)
        self.main_panel.setLayout(self.main_panel_layout)

        '''------------------------------------------
        AUXILIARY PANELS
        ------------------------------------------'''
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
        self.project_view_panel_controls_layout.addWidget(self.exit_project_view_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_view_panel_controls_layout.addWidget(self.refresh_project_view_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_view_panel_controls_layout.addWidget(self.save_project_project_view_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.project_view_panel_controls_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.project_view_panel_layout.addLayout(self.project_view_panel_controls_layout)
        self.project_view_panel.setLayout(self.project_view_panel_layout)

        # DOCUMENTATION PANEL
        self.browser = QWebEngineView()
        self.browser_docs = QWebEngineView()
        self.exit_docs_button = QPushButton("Back")
        self.exit_docs_button.setFixedSize(std_button_size)
        self.exit_docs_button.clicked.connect(exit_docs)
        self.readme_button = QPushButton("README.md")
        self.readme_button.setFixedSize(std_button_size)
        self.readme_button.clicked.connect(documentation_view_home)
        self.docs_panel = QWidget()
        self.docs_panel_layout = QVBoxLayout()
        self.docs_panel_layout.addWidget(self.browser_docs)
        self.docs_panel_controls_layout = QHBoxLayout()
        self.docs_panel_controls_layout.addWidget(self.exit_docs_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.docs_panel_controls_layout.addWidget(self.readme_button, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) #0610
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.docs_panel_controls_layout.addSpacerItem(self.spacer_item_docs)
        self.docs_panel_layout.addLayout(self.docs_panel_controls_layout)
        self.docs_panel.setLayout(self.docs_panel_layout)

        # REMOTE VIEWER PANEL
        self.browser_remote = QWebEngineView()
        self.browser_remote.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))  # tacctacc
        # self.browser_remote.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.exit_remote_button = QPushButton("Back")
        self.exit_remote_button.setFixedSize(std_button_size)
        self.exit_remote_button.clicked.connect(exit_remote)
        self.reload_remote_button = QPushButton("Reload")
        self.reload_remote_button.setFixedSize(std_button_size)
        self.reload_remote_button.clicked.connect(reload_remote)
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
        self.exit_demos_button.setFixedSize(std_button_size)
        self.exit_demos_button.clicked.connect(exit_demos)
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
        self.exit_ng_button.clicked.connect(exit_ng)
        self.reload_ng_button = QPushButton("Reload")
        self.reload_ng_button.setFixedSize(std_button_size)
        self.reload_ng_button.clicked.connect(reload_ng)
        self.print_state_ng_button = QPushButton("Print State")
        self.print_state_ng_button.setFixedSize(std_button_size)
        self.print_state_ng_button.clicked.connect(print_state_ng)
        self.print_url_ng_button = QPushButton("Print URL")
        self.print_url_ng_button.setFixedSize(std_button_size)
        self.print_url_ng_button.clicked.connect(print_url_ng)
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
        # self.ng_panel_controls_layout.addWidget(self.screenshot_ng_button, alignment=alignEM.AlignmentFlag.AlignLeft)
        # self.ng_panel_controls_layout.addWidget(self.blend_ng_button, alignment=alignEM.AlignmentFlag.AlignLeft)
        # self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) #0610
        self.spacer_item_ng_panel = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.ng_panel_controls_layout.addSpacerItem(self.spacer_item_ng_panel)
        self.ng_panel_layout.addLayout(self.ng_panel_controls_layout)  # add horizontal layout
        self.ng_panel.setLayout(self.ng_panel_layout)  # set layout

        # self.spacerItem = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum) # not working

        # stack of windows views
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(self.main_panel)  # (0) main_panel
        self.stacked_widget.addWidget(self.ng_panel)  # (1) ng_panel
        self.stacked_widget.addWidget(self.docs_panel)  # (2) docs_panel
        self.stacked_widget.addWidget(self.demos_panel)  # (3) demos_panel
        self.stacked_widget.addWidget(self.remote_viewer_panel)  # (4) remote_viewer_panel
        # self.stacked_widget.addWidget(self.project_view)  # (5) self.project_view
        self.stacked_widget.addWidget(self.project_view_panel)  # (5) self.project_view
        self.stacked_widget.setCurrentIndex(0)

        # This can be invisible, will still use to organize QStackedWidget
        self.pageComboBox = QComboBox()
        self.pageComboBox.addItem("Main")
        self.pageComboBox.addItem("Neuroglancer Local")
        self.pageComboBox.addItem("Documentation")
        self.pageComboBox.addItem("Demos")
        self.pageComboBox.addItem("Remote Viewer")
        self.pageComboBox.addItem("Project View")
        self.pageComboBox.activated[int].connect(self.stacked_widget.setCurrentIndex)
        # self.pageComboBox.activated.connect(self.stackedLayout.s_etCurrentIndex)

        self.stacked_layout = QVBoxLayout()
        self.stacked_layout.addWidget(self.stacked_widget)
        self.setCentralWidget(self.stacked_widget)  # setCentralWidget to QStackedWidget

        #status bar
        self.status = self.statusBar()
        self.set_idle()

        #menu bar
        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)  # fix to set non-native menubar in macOS


        ####   0:MenuName, 1:Shortcut-or-None, 2:Action-Function, 3:Checkbox (None,False,True), 4:Checkbox-Group-Name (None,string), 5:User-Data
        ml = [
                ['&File',
                    [
                         ['&New Project', 'Ctrl+N', self.new_project, None, None, None],
                         ['&Open Project', 'Ctrl+O', self.open_project, None, None, None],
                         ['&Save Project', 'Ctrl+S', self.save_project, None, None, None],
                         ['Save Project &As...', 'Ctrl+A', self.save_project_as, None, None, None],
                         ['View Project JSON', 'Ctrl+J', self.project_view_callback, None, None, None],
                         ['Show/Hide Project Inspector', None, self.show_hide_project_inspector, None, None, None],
                         ['Go Back', None, self.back_callback, None, None, None],
                         ['Exit', 'Ctrl+Q', self.exit_app, None, None, None]
                    ]
                 ],
                ['&Tools',
                    [
                        ['Go Back', None, self.back_callback, None, None, None],
                        ['Plot SNRs', None, self.plot_snr, None, None, None],
                        ['Apply Project Defaults', None, set_default_settings, None, None, None],
                        ['Print Sanity Check', None, print_sanity_check, None, None, None],
                        ['Print Structures', None, self.print_structures, None, None, None],
                        ['Print Image Library', None, self.print_image_library, None, None, None],
                        ['Print Affine Grep', None, debug_project, None, None, None],
                        ['Print Aligned Scales List', None, get_aligned_scales_list, None, None, None],
                        ['Print Single Alignment Layer', None, print_alignment_layer, None, None, None],
                        ['Print SNR List', None, print_snr_list, None, None, None],
                        ['Print .dat Files', None, print_dat_files, None, None, None],
                        ['Print Working Directory', None, print_path, None, None, None],
                        ['&Stylesheets',
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

                    ]
                 ],
                ['&Debug',
                    [
                         ['Update Panels', None, self.update_panels, None, None, None],
                         ['Refresh All Images', None, self.refresh_all_images, None, None, None],
                         ['Read project_data Update GUI', None, self.read_project_data_update_gui, None, None, None],
                         ['Read GUI Update project_data', None, self.read_gui_update_project_data, None, None, None],
                         ['Link Images Stacks', None, link_all_stacks, None, None, None],
                         ['Reload Scales Combobox', None, self.reload_scales_combobox, None, None, None],
                         ['Update Project Inspector', None, self.update_project_inspector, None, None, None],
                    ]
                ],
            ]
        self.build_menu_from_list(self.menu, ml)

    @Slot()
    def project_view_callback(self):
        # json_path = QFileInfo(__file__).absoluteDir().filePath(self.project_filename)
        # with open(json_path) as f:
        #     document = json.load(f)
        #     self.project_model.load(document)
        self.project_model.load(cfg.project_data)
        self.project_view.show()
        self.stacked_widget.setCurrentIndex(5)
        # 0718

    @Slot()
    def run_scaling(self) -> None:
        print("run_scaling >>>>>>>>")
        self.set_status("Scaling...")
        self.hud.post('Requesting scale factors from user')
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
            print("run_scaling | User did not select OK - Canceling")
            self.hud.post('User did not select OK - Canceling')
            self.set_idle()
            print('<<<<<<<< run_scaling')
            return

        if input_val == '':
            self.hud.post('Input was empty, please provide scaling factors')
            self.set_idle()
            print('<<<<<<<< run_scaling')
            return
        set_scales_from_string(str(input_val))
        self.hud.post('Scale image hierarchy will have these scale levels: %s' % input_val)
        # worker = RunnableWorker(self.execute_this_fn) # Any other args, kwargs are passed to the run function

        try:
            generate_scales()
        except:
            cfg.main_window.hud.post('Generating Scales Triggered an Exception',logging.WARNING)
        else:
            link_all_stacks()
            set_default_settings()

        if is_dataset_scaled():
            try:
                path_of_img_aligned = os.path.join(cfg.project_data['data']['destination_path'], get_cur_scale_key(),
                                                   'img_aligned')
                print('path_of_img_aligned = ' % path_of_img_aligned)
                path_of_first_image = os.listdir(path_of_img_aligned)[:1]
                print('path_of_first_image = ' % path_of_first_image)
                imghdr_type = verify_image_file(path_of_first_image)
                print('imghdr_type = %s' % imghdr_type)
                self.hud.post('Output Format: %s' % imghdr_type)
            except:
                self.hud.post('(Unable to verify image type for generated images.)')

            cfg.project_data['data']['current_scale'] = get_scales_list()[-1]
            self.set_progress_stage_2()
            self.read_project_data_update_gui()
            self.reload_scales_combobox() #0529 #0713+
            self.scales_combobox.setCurrentIndex(self.scales_combobox.count() - 1)
            AllItems = [self.scales_combobox.itemText(i) for i in range(self.scales_combobox.count())]
            print('str(AllItems) = %s' % str(AllItems))
            self.update_scale_controls()
            self.center_all_images()
            self.hud.post('Scaling Completed Successfully.')
            print('\nScaling Completed Successfully.\n')
        else:
            self.hud.post('Scaling Was Not Successful.', logging.ERROR)
            print('\nScaling Was Not Successful.\n')
        self.set_idle()


    @Slot()
    def run_alignment(self) -> None:
        print('run_alignment >>>>>>>>')
        self.read_gui_update_project_data()
        # This should be impossible to trigger due to disabling/enabling of buttons.
        if not is_cur_scale_ready_for_alignment():
            error_msg = "Scale %s must be aligned first!" % get_next_coarsest_scale_key()[-1]
            cfg.main_window.hud.post(error_msg, logging.WARNING)
            # error_dialog = QErrorMessage()
            # error_dialog.showMessage(error_msg)
            return
        self.status.showMessage('Aligning...')
        try:
            compute_affines(use_scale=get_cur_scale_key(), start_layer=0, num_layers=-1)
        except:
            self.hud.post('An Exception Was Raised During Alignment.', logging.ERROR)
            print_exception()

        if not is_cur_scale_aligned():
            self.hud.post('Something Went Wrong During Alignment.', logging.ERROR)
            self.set_idle()
            return
        self.update_alignment_status_indicator()

        if self.always_generate_images:
            try:
                generate_aligned_images(
                        use_scale=get_cur_scale_key(),
                        start_layer=0,
                        num_layers=-1
                )
            except:
                self.hud.post('Something Went Wrong During Image Generation.', logging.ERROR)
                self.set_idle()
                print_exception()
                return

            if are_aligned_images_generated():
                self.set_progress_stage_3()
                self.center_all_images()
                self.hud.post('Image Generation Complete')
                print('\nImage Generation Complete\n')
            else:
                self.hud.post('Alignment Succeeded, but Image Generation Failed. Try Re-generating the Images.', logging.WARNING)
            self.update_win_self()
            self.set_idle()

    @Slot()
    def run_regenerate_alignment(self) -> None:
        print('run_regenerate_alignment >>>>>>>>')
        self.read_gui_update_project_data()
        if not is_cur_scale_aligned():
            self.hud.post('Scale Must Be Aligned Before Images Can Be Generated.', logging.WARNING)
            self.set_idle()
            return
        self.status.showMessage('Busy...')
        try:
            generate_aligned_images(
                    use_scale=get_cur_scale_key(),
                    start_layer=0,
                    num_layers=-1
            )
        except:
            self.hud.post('Something Went Wrong During ImageGeneration.', logging.ERROR)
            self.set_idle()
            print_exception()
            return

        if are_aligned_images_generated():
            self.set_progress_stage_3()
            self.center_all_images()
            self.hud.post("Regenerate Complete")
            print('\nRegenerate Complete\n')
        else:
            self.hud.post('Image Generation Failed Unexpectedly. Try Re-aligning First.', logging.ERROR)
        self.update_win_self()
        self.set_idle()

    def make_zarr_multithreaded(self, aligned_path, n_scales, cname, clevel, destination_path, ds_name):
        os.system("python3 ../convert_zarr.py %s -c '64,64,64' -nS %s -cN %s -cL %s -d %s -n %s" % (
        aligned_path, str(n_scales), str(cname), str(clevel), destination_path, ds_name))

    def export_zarr(self):
        print('\nexport_zarr():')

        # if get_num_aligned() < 1:
        if is_any_scale_aligned_and_generated():
            print('  export_zarr() | there is an alignment stack at this scale - continuing.')
            pass
        else:
            print('  export_zarr() | (!) There is no alignment at this scale to export. Returning from export_zarr().')
            show_warning('No Alignment', 'There is no alignment to export.\n\n'
                                         'Typical workflow:\n'
                                         '(1) Open a project or import images and save.\n'
                                         '(2) Generate a set of scaled images and save.\n'
                                         '--> (3) Align each scale starting with the coarsest.\n'
                                         '(4) Export alignment to Zarr format.\n'
                                         '(5) View data in Neuroglancer client')
            return

        self.set_status('Exporting...')
        self.hud.post('Exporting scale %s to Neuroglancer-ready Zarr format...' % get_cur_scale_key()[-1])

        # allow any scale export...
        self.aligned_path = os.path.join(cfg.project_data['data']['destination_path'], get_cur_scale_key(),
                                         'img_aligned')
        self.ds_name = 'aligned_' + get_cur_scale_key()
        print('  export_zarr() | aligned_path_cur_scale =', self.aligned_path)

        destination_path = os.path.abspath(cfg.project_data['data']['destination_path'])
        print('  export_zarr() | path of aligned images              :', self.aligned_path)
        print('  export_zarr() | path of Zarr export                 :', destination_path)
        print('  export_zarr() | dataset name                        :', self.ds_name)
        os.chdir(self.pyside_path)
        print('  export_zarr() | working directory                   :', os.getcwd())

        self.clevel = str(self.clevel_input.text())
        self.cname = str(self.cname_combobox.currentText())
        self.n_scales = str(self.n_scales_input.text())
        print("  export_zarr() | export options                      : clevel='%s'  cname='%s'  n_scales='%s'".format(
                self.clevel, self.cname, self.n_scales))

        # if self.cname == "none":
        #     os.system(
        #         "python3 convert_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(
        #             self.n_scales) + " -nC 1 -d " + destination_path)
        # else:
        #     # os.system("./convert_zarr.py volume_josef_small --chunks '1,5332,5332' --no_compression True")
        #     os.system(
        #         "python3 convert_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(self.n_scales) + " -cN " + str(
        #             self.cname) + " -cL " + str(self.clevel) + " -d " + destination_path)

        # zarr
        # https://stackoverflow.com/questions/6783194/background-thread-with-qthread-in-pyqt
        # https://stackoverflow.com/questions/47560399/run-function-in-the-background-and-update-ui
        # https://stackoverflow.com/questions/58327821/how-to-pass-parameters-to-pyqt-qthreadpool-running-function
        self.dest_path = destination_path
        if self.cname == "none":
            # os.system("python3 convert_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(n_scales) + " -nC 1 -d " + destination_path + " -n " + ds_name)
            os.system("python3 ../convert_zarr.py %s -c '64,64,64' -nS %s -nC 1 -d %s -n %s" % (
            self.aligned_path, self.n_scales, self.dest_path, self.ds_name))
            # self.set_status('Idle')
            self.set_idle()
            self.hud.post('Export of scale %s to Zarr complete' % get_cur_scale_key()[-1])

        else:
            # print('\n\n---------ATTEMPTING BACKGROUND ZARR-----------\n\n')
            # worker = RunnableWorker(self.make_zarr_multithreaded, self.aligned_path, self.n_scales, self.cname, self.clevel, self.dest_path, self.ds_name) # Any other args, kwargs are passed to the run function
            # self.threadpool.start(worker)

            # worker.signals.result.connect(self.print_output)
            # worker.signals.finished.connect(self.thread_complete)
            # worker.signals.progress.connect(self.progress_fn)

            # make_zarr_multithreaded(aligned_path, n_scales, cname, clevel, destination_path, ds_name) # THIS WORKS

            os.system("python3 ../convert_zarr.py %s -c '64,64,64' -nS %s -cN %s -cL %s -d %s -n %s" % (
            self.aligned_path, str(self.n_scales), str(self.cname), str(self.clevel), destination_path, self.ds_name))
            # os.system("python3 convert_zarr.py " + aligned_path + " -c '64,64,64' -nS " + str(n_scales) + " -cN " + str(cname) + " -cL " + str(clevel) + " -d " + destination_path + " -n " + ds_name)
            # self.set_status('Idle')
            self.set_idle()
            # self.hud.post('Export of scale %s to Zarr complete' % get_cur_scale_key()[-1])
            self.hud.post('Complete')

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
                self.hud.post('Something Went Wrong',logging.WARNING)
                print_exception()
        self.hud.post('Done')
        self.set_idle()



    def update_win_self(self):
        print("update_win_self (called by %s):" % inspect.stack()[1].function)
        # self.center_all_images()  # uncommenting causes centering issues to re-emerge
        self.update()  # repaint

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
                # This is a submenu
                sub = parent.addMenu(item[0])
                self.build_menu_from_list(sub, item[1])
            else:
                # This is a menu item (action) or a separator
                if item[0] == '-':
                    # This is a separator
                    parent.addSeparator()
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
                print('update_scale_controls | WARNING | Something went wrong updating visibility state of controls')
                print_exception()
            try:
                self.align_all_button.setEnabled(is_cur_scale_ready_for_alignment())
            except:
                print('update_scale_controls | WARNING | Something went wrong enabling/disabling align all button')
            try:
                self.jump_validator = QIntValidator(0,get_num_imported_images())
            except:
                print('update_scale_controls | WARNING | Something went wrong setting validator on jump_input')


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


    def update_alignment_details(self):
        dm_name_to_combo_name = {'init_affine' : 'Initialize Affine',
                                 'refine_affine': 'Refine Affine',
                                 'apply_affine': 'Apply Affine'}
        img_size = get_image_size(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][0][
                                      'images']['base']['filename'])
        alignment_method_string = dm_name_to_combo_name[cfg.project_data['data']['scales'][get_cur_scale_key()][
            'method_data']['alignment_option']]

        self.align_label_resolution.setText('%sx%spx' % (img_size[0], img_size[1]))
        self.align_label_affine.setText(alignment_method_string)
        self.align_label_scales_remaining.setText('# Scales Unaligned: %d' % len(get_not_aligned_scales_list()))

    @Slot()
    def update_alignment_status_indicator(self) -> None:
        '''Simple function to update alignment status indicator'''
        # print("update_alignment_status_indicator | called by " + inspect.stack()[1].function)
        self.alignment_status_checkbox.setChecked(is_cur_scale_aligned())
        self.update_alignment_details()


    @Slot()
    def next_scale_button_callback(self) -> None:
        '''Callback function for the Next Scale button (scales combobox may not be visible but controls the current scale).'''
        try:
            self.scales_combobox_switch = 1
            self.read_gui_update_project_data()
            cur_index = self.scales_combobox.currentIndex()
            requested_index = cur_index - 1
            # cur_scale_key = self.scales_combobox.itemText(cur_index)
            # requested_scale_key = self.scales_combobox.itemText(requested_index)
            # is_current_scale_aligned = is_scale_aligned(cur_scale_key)
            # is_requested_scale_aligned = is_scale_aligned(requested_scale_key)
            # if not is_current_scale_aligned and not is_requested_scale_aligned:
            #     cfg.main_window.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)

            self.scales_combobox.setCurrentIndex(requested_index)
            self.read_project_data_update_gui()
            self.update_scale_controls()
            if not is_cur_scale_ready_for_alignment():
                cfg.main_window.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
        except:
            print_exception()
            print('next_scale_button_callback | EXCEPTION')
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

            cur_scale_key = self.scales_combobox.itemText(cur_index)
            requested_scale_key = self.scales_combobox.itemText(requested_index)
            is_current_scale_aligned = is_scale_aligned(cur_scale_key)
            is_requested_scale_aligned = is_scale_aligned(requested_scale_key)


            new_cur_index = self.scales_combobox.currentIndex()
            # print('self.scales_combobox.Items.Count - 1 = ',self.scales_combobox.Items.Count - 1)
            # before_new_cur_index = cur_index + 1
            # if new_cur_index == 1:
            #     self.next_scale_button.setEnabled(True)
            #
            # print('self.scales_combobox.itemText(cur_index) = ', self.scales_combobox.itemText(cur_index))
            # print('self.scales_combobox.itemText(new_index-1) = ', self.scales_combobox.itemText(requested_index-1))
            #
            # print('cur_index = ', cur_index)
            # print('cur_scale_key = ', cur_scale_key)
            # print('new_index = ', requested_index)
            # is_cur_scale_aligned = is_scale_aligned(cur_scale_key)
            # is_requested_scale_aligned = is_scale_aligned(requested_scale_key)
            # print('is_cur_scale_aligned = ', is_cur_scale_aligned)
            # print('is_requested_scale_aligned = ', is_requested_scale_aligned)
            self.scales_combobox.setCurrentIndex(requested_index)  # <-- this is what actually does the scale change
            self.read_project_data_update_gui()
            self.update_scale_controls()
            if not is_cur_scale_ready_for_alignment():
                cfg.main_window.hud.post('Scale(s) of lower resolution have not been aligned yet', logging.WARNING)
        except:
                print_exception()
                print('next_scale_button_callback | EXCEPTION')
        finally:
            self.scales_combobox_switch = 0

    # def set_run_alignment_enabled_or_disabled(self) -> None:
    #     return
    #     # current_scale = get_cur_scale_key()
    #     # if is_scale_aligned(current_scale):
    #     #     self.next_scale_button.setEnabled()

    @Slot()
    def plot_snr(self):

        snr_list = get_snr_list()
        x_axis = [x for x in range(0,len(snr_list))]
        # pen = pg.mkPen(color=(255, 0, 0), width=5, style=Qt.SolidLine)
        pen = pg.mkPen(color=(0, 0, 0), width=5, style=Qt.SolidLine)
        styles = {'color': '#000000', 'font-size': '13px'}
        self.plot_widget.setLabel('left', 'SNR', **styles)
        self.plot_widget.setLabel('bottom', 'Layer', **styles)
        # self.plot_widget.setXRange(0, get_num_imported_images())
        # self.plot_widget.setBackground(QColor(100, 50, 254, 25))
        self.plot_widget.plot(x_axis, snr_list, name = "SNR", pen=pen, symbol='+')
        # self.plot_widget.setXRange(0,len(snr_list))
        # x_ax = self.plot_widget.getAxis("bottom")
        self.bottom_panel_stacked_widget.setCurrentIndex(1)

    @Slot()
    def back_callback(self):
        logging.info("Returning Home...")
        self.stacked_widget.setCurrentIndex(0)
        self.bottom_panel_stacked_widget.setCurrentIndex(0)
        self.set_idle()

    @Slot()
    def show_hide_project_inspector(self):
        print('show_hide_project_inspector:')
        if self.project_inspector.isHidden():
            print('show_hide_project_inspector | Showing project inspector...')
            self.update_project_inspector()
            self.project_inspector.show()
        elif self.project_inspector.isVisible():
            print('show_hide_project_inspector | Hiding project inspector...')
            self.project_inspector.hide()


    @Slot()
    def update_project_inspector(self):
        try:
            skips_list = str(get_skips_list())
            skips_list_wrapped = "\n".join(textwrap.wrap(skips_list, width=10))
            self.inspector_label_skips.setText(skips_list_wrapped)
        except:
            print('update_project_inspector | EXCEPTION | Failed to update_skips_list')
            print_exception()

    @Slot()
    def set_status(self, msg: str) -> None:
        self.status.showMessage(msg)

    @Slot()  # 0503 #skiptoggle #toggleskip #skipswitch forgot to define this
    def update_skip_toggle(self):
        print('update_skip_toggle:')
        scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]
        print("scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'] = ",
              scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'])
        self.toggle_skip.setChecked(not scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'])

    # stylesheet
    def minimal_stylesheet(self):
        self.setStyleSheet('')
        print('Changing stylesheet to minimal')

    def apply_stylesheet_1(self):
        self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet1.qss')
        self.hud.post('Applying stylesheet 1')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    # def apply_stylesheet_2(self):
    #     self.setStyleSheet('')
    #     self.setStyleSheet(open(os.path.join(self.pyside_path, 'styles/stylesheet2.qss')).read())

    def apply_stylesheet_3(self):
        '''Light stylesheet'''
        self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet3.qss')
        self.hud.post('Applying stylesheet 3')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def apply_stylesheet_4(self):
        '''Grey stylesheet'''
        self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet4.qss')
        self.hud.post('Applying stylesheet 4')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def apply_stylesheet_11(self):
        '''Screamin' Green stylesheet'''
        self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet11.qss')
        self.hud.post('Applying stylesheet 11')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def apply_stylesheet_12(self):
        self.main_stylesheet = os.path.join(self.pyside_path, '../styles/stylesheet12.qss')
        self.hud.post('Applying stylesheet 12')
        self.setStyleSheet('')
        self.setStyleSheet(open(self.main_stylesheet).read())
        self.reset_groupbox_styles()

    def reset_groupbox_styles(self):
        print('reset_groupbox_styles | Resetting groupbox styles')
        self.project_functions_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.images_and_scaling_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.alignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.postalignment_stack.setStyleSheet(open(self.main_stylesheet).read())
        self.export_and_view_stack.setStyleSheet(open(self.main_stylesheet).read())
        # self.auto_set_user_progress() #0713-


    def auto_set_user_progress(self):
        '''Set user progress (0 to 3). This is only called when user opens a project.'''
        print("auto_set_user_progress:")
        if is_any_scale_aligned_and_generated(): self.set_progress_stage_3()
        elif is_dataset_scaled():                self.set_progress_stage_2()
        elif is_destination_set():               self.set_progress_stage_1()
        else:                                    self.set_progress_stage_0()


    def set_user_progress(self, gb1:bool, gb2:bool, gb3:bool, gb4:bool) -> None:
        self.images_and_scaling_stack.setCurrentIndex((0,1)[gb1])
        self.images_and_scaling_stack.setStyleSheet(
                ("""QGroupBox {border: 2px dotted #455364;}""",
                 open(self.main_stylesheet).read())[gb1])
        self.alignment_stack.setCurrentIndex((0, 1)[gb2])
        self.alignment_stack.setStyleSheet(
                ("""QGroupBox {border: 2px dotted #455364;}""",
                 open(self.main_stylesheet).read())[gb2])
        self.postalignment_stack.setCurrentIndex((0, 1)[gb3])
        self.postalignment_stack.setStyleSheet(
                ("""QGroupBox {border: 2px dotted #455364;}""",
                 open(self.main_stylesheet).read())[gb3])
        self.export_and_view_stack.setCurrentIndex((0, 1)[gb4])
        self.export_and_view_stack.setStyleSheet(
                ("""QGroupBox {border: 2px dotted #455364;}""",
                 open(self.main_stylesheet).read())[gb4])

    @Slot()
    def set_progress_stage_0(self):
        if self.get_user_progress() != 0: self.hud.post('Reverting user progress to Project')
        self.set_user_progress(False, False, False, False)
        # self.scales_combobox_switch = 0 #0718-
        self.project_progress = 0

    @Slot()
    def set_progress_stage_1(self):
        if self.get_user_progress() > 1:   self.hud.post('Reverting user progress to Data Selection & Scaling')
        elif self.get_user_progress() < 1: self.hud.post('Setting user progress to Data Selection & Scaling')
        self.set_user_progress(True, False, False, False)
        # self.scales_combobox_switch = 0 #0718-
        self.project_progress = 1

    def set_progress_stage_2(self):
        if self.get_user_progress() > 2:   self.hud.post('Reverting user progress to Alignment')
        elif self.get_user_progress() < 2: self.hud.post('Setting user progress to Alignment')
        self.set_user_progress(True, True, True, False)
        # self.scales_combobox_switch = 1 #0718-
        self.project_progress = 2

    def set_progress_stage_3(self):
        if self.get_user_progress() < 2: self.hud.post('Setting user progress to Export & View')
        self.set_user_progress(True, True, True, True)
        # self.scales_combobox_switch = 1 #0718-
        self.project_progress = 3

    def get_user_progress(self) -> int:
        '''Get user progress (0 to 3)'''
        if is_any_scale_aligned_and_generated(): return int(3)
        elif is_dataset_scaled():                return int(2)
        elif is_destination_set():               return int(1)
        else:                                    return int(0)

    @Slot()
    def read_gui_update_project_data(self) -> None:
        '''
        Reads UI data from MainWindow and writes everything to 'cfg.project_data'.
        '''
        # print('read_gui_update_project_data:')
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
            print('read_gui_update_project_data | EXCEPTION | Failed to update project_data')
        return

    @Slot()
    def read_project_data_update_gui(self) -> None:
        '''Reads 'cfg.project_data' values and writes everything to MainWindow.'''
        try:
            scale = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]  # we only want the current scale
        except:
            print('read_project_data_update_gui | WARNING | Failed to get current scale')
        try:
            self.toggle_skip.setChecked(not scale['alignment_stack'][cfg.project_data['data']['current_layer']]['skip'])
        except:
            print('read_project_data_update_gui | WARNING | toggle_skip UI element failed to update its state')

        try:
            self.jump_input.setText(str(get_cur_layer()))
        except:
            pass


        if is_dataset_scaled():
            try:
                cur_whitening_factor = \
                scale['alignment_stack'][cfg.project_data['data']['current_layer']]['align_to_ref_method']['method_data'][
                    'whitening_factor']
                self.whitening_input.setText(str(cur_whitening_factor))
            except:
                print('read_project_data_update_gui | WARNING | Whitening Input UI element failed to update its state')

            try:
                layer = scale['alignment_stack'][
                    cfg.project_data['data']['current_layer']]  # we only want the current layer
                cur_swim_window = layer['align_to_ref_method']['method_data']['win_scale_factor']
                self.swim_input.setText(str(cur_swim_window))
            except:
                print('read_project_data_update_gui | WARNING | Swim Input UI element failed to update its state')

            try:
                use_bounding_rect = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']][
                    'use_bounding_rect']
                self.toggle_bounding_rect.setChecked(bool(use_bounding_rect))
            except:
                print('read_project_data_update_gui | WARNING | Bounding Rect UI element failed to update its state')

        # self.reload_scales_combobox() #0713-
        # self.update_scale_controls() #<-- this does not need to be called on every change of layer
        try:
            self.update_alignment_status_indicator()
        except:
            print('read_project_data_update_gui | WARNING | Unable to update alignment status indicator')
            pass

        caller = inspect.stack()[1].function
        if caller != 'change_layer': print(
            'read_project_data_update_gui | GUI is in sync with cfg.project_data for current scale + layer.')

    @Slot()
    def set_idle(self) -> None:
        self.status.showMessage('Idle')
        QThread.currentThread().setObjectName('MainThread')

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
    def jump_to_layer(self) -> None:
        if self.jump_input.text() == '':
            pass
        else:
            requested_layer = int(self.jump_input.text())
            print("Jumping to layer " + str(requested_layer))
            self.hud.post("Jumping to layer " + str(requested_layer))
            num_layers = len(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'])
            if requested_layer >= num_layers:  # Limit to largest
                requested_layer = num_layers - 1

            cfg.project_data['data']['current_layer'] = requested_layer
            self.image_panel.update_multi_self()

    @Slot()
    def reload_scales_combobox(self) -> None:
        # print("reload_scales_combobox:")
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
        print('\nfn_scales_combobox | called by %s' % inspect.stack()[1].function)
        if self.scales_combobox_switch == 0:
            # print('fn_scales_combobox | Change scales switch is disabled | Called by %s' % inspect.stack()[1].function)
            return None
        print('fn_scales_combobox | Switch is live...')
        # print('fn_scales_combobox | self.scales_combobox.currentText() = %s' % self.scales_combobox.currentText())
        # print("fn_scales_combobox | Change scales switch is Enabled, changing to %s"%self.scales_combobox.currentText())
        # self.reload_scales_combobox() #bug fix
        try:
            print(
                'fn_scales_combobox | self.scales_combobox.currentText() = new_curr_scale = ' % self.scales_combobox.currentText())
        except:
            print('fn_scales_combobox | something is wrong')
        new_curr_scale = self.scales_combobox.currentText()  # <class 'str'>

        cfg.project_data['data']['current_scale'] = new_curr_scale
        # self.hud.post('Switching to Scale %s' % new_curr_scale[-1]) #0718 #BUG
        self.read_project_data_update_gui()
        # self.update_panels()  # 0523 #0528
        self.center_all_images()  # 0528
        return None

    @Slot()
    def not_yet(self):
        print_debug(30, "Function is not implemented yet")

    @Slot()
    def toggle_annotations(self, checked):
        print_debug(30, "Toggling Annotations")

    @Slot()
    def toggle_full_paths(self, checked):
        print_debug(30, "Toggling Full Paths")

    @Slot()
    def toggle_show_skipped(self, checked):
        print_debug(30, "Toggling Show Skipped with checked = " + str(checked))
        global show_skipped_images
        show_skipped_images = checked

    def print_structures(self):
        # global DEBUG_LEVEL #0613
        print("\n:::DATA STRUCTURES:::")
        print_debug(2, "  cfg.project_data['version'] = " + str(cfg.project_data['version']))
        print_debug(2, "  cfg.project_data.keys() = " + str(cfg.project_data.keys()))
        print_debug(2, "  cfg.project_data['data'].keys() = " + str(cfg.project_data['data'].keys()))
        print_debug(2, "  cfg.project_data['data']['panel_roles'] = " + str(cfg.project_data['data']['panel_roles']))
        scale_keys = list(cfg.project_data['data']['scales'].keys())
        print_debug(2, "  list(cfg.project_data['data']['scales'].keys()) = " + str(scale_keys))
        print_debug(2, "Scales, Layers, and Images:")
        for k in sorted(scale_keys):
            print_debug(2, "  Scale key: " + str(k) +
                        ", NullBias: " + str(cfg.project_data['data']['scales'][k]['null_cafm_trends']) +
                        ", Bounding Rect: " + str(cfg.project_data['data']['scales'][k]['use_bounding_rect']))
            scale = cfg.project_data['data']['scales'][k]
            for layer in scale['alignment_stack']:
                print_debug(2, "    Layer: " + str([k for k in layer['images'].keys()]))
                for role in layer['images'].keys():
                    im = layer['images'][role]
                    print_debug(2, "      " + str(role) + ": " + str(layer['images'][role]['filename']))

    @Slot()
    def print_image_library(self):
        print(str(cfg.image_library))

    def new_project(self):
        print('\nnew_project:')
        self.hud.post('Creating new project...')
        self.set_status("Project...")
        if is_destination_set():
            print('new_project | Asking user to confirm new project')
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
                print("new_project | Response was 'OK'")
                pass
            else:
                print("new_project | Response was not 'OK' - Returning")
                self.hud.post('New project was canceled')
                self.set_idle()
                return
        # self.scales_combobox_switch = 0 #0718-
        self.set_progress_stage_0()
        filename = self.save_project_dialog()
        if filename == '':
            self.hud.post("You did not enter a valid name for the project file.")
            self.set_idle()
            return
        print("new_project | Overwriting project data in memory with project template")
        cfg.project_data = copy.deepcopy(new_project_template)
        print("new_project | Creating new project %s" % filename)
        self.project_filename = filename
        self.setWindowTitle("Project: " + os.path.split(self.project_filename)[-1])
        self.set_def_proj_dest()
        self.save_project_to_file()
        self.set_progress_stage_1()
        self.scales_combobox.clear()  # why? #0528
        self.set_idle()

    def import_into_role(self):
        print("import_into_role:")
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
            logging.info('Something went wrong during import', logging.WARNING)
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

    def open_project(self):
        logging.info('open_project >>>>>>>>')
        self.set_status("Project...")
        # self.scales_combobox_switch = 0 #0718-
        filename = self.open_project_dialog()
        if filename != '':
            with open(filename, 'r') as f:
                proj_copy = json.load(f)
            proj_copy = upgrade_data_model(proj_copy)  # Upgrade the "Data Model"
            if type(proj_copy) == type('abc'):  # abc = abstract base class
                # There was a known error loading the data model
                self.hud.post('There was a problem loading the project file.', logging.ERROR)
                print("open_project | type=abc | Project %s has abstract base class" % proj_copy)
                self.set_idle()
                return
            self.hud.post("Loading project '%s'" % filename)
            self.project_filename = filename
            self.setWindowTitle("Project: " + os.path.split(self.project_filename)[-1])
            print('open_project | Modifying the copy to use absolute paths internally')

            # Modify the copy to use absolute paths internally
            if 'destination_path' in proj_copy['data']:
                if proj_copy['data']['destination_path'] != None:
                    if len(proj_copy['data']['destination_path']) > 0:
                        proj_copy['data']['destination_path'] = make_absolute(
                                proj_copy['data']['destination_path'], self.project_filename)
            for scale_key in proj_copy['data']['scales'].keys():
                scale_dict = proj_copy['data']['scales'][scale_key]
                for layer in scale_dict['alignment_stack']:
                    for role in layer['images'].keys():
                        if layer['images'][role]['filename'] != None:
                            if len(layer['images'][role]['filename']) > 0:
                                layer['images'][role]['filename'] = make_absolute(
                                        layer['images'][role]['filename'], self.project_filename)

            cfg.project_data = copy.deepcopy(proj_copy)  # Replace the current version with the copy
            logging.info('open_project | Ensuring proper data structure...')
            ensure_proper_data_structure()
            link_all_stacks()
            self.read_project_data_update_gui()
            self.reload_scales_combobox()
            self.auto_set_user_progress()
            self.update_scale_controls()
            if are_images_imported():
                self.generate_scales_button.setEnabled(True)
            self.center_all_images()
            self.hud.post("Project '%s'" % self.project_filename)
        else:
            self.hud.post("No project file (.json) was selected")
        self.image_panel.setFocus()
        self.set_idle()
        logging.info('<<<<<<<< open_project')

    def save_project(self):
        logging.info('save_project:')
        self.set_status("Saving...")
        try:
            self.save_project_to_file()
            self.hud.post("Project saved as '%s'" % self.project_filename)
        except:
            self.hud.post('Save Project Failed', logging.ERROR)
            self.set_idle()
            print_exception()
        self.set_idle()

    def save_project_as(self):
        logging.info("save_project_as:")
        self.set_status("Saving...")
        filename = self.save_project_dialog()
        if filename != '':
            try:
                self.save_project_to_file()
                self.hud.post("Project saved as '%s'" % self.project_filename)
            except:
                self.hud.post('Save Project Failed', logging.ERROR)
                self.set_idle()
                print_exception()
        self.set_idle()

    def save_project_to_file(self):
        # self.hud.post('Saving project')
        # Save to current file and make known file paths relative to the project file name
        if is_destination_set():
            self.read_gui_update_project_data()
            if not self.project_filename.endswith('.json'):
                self.project_filename += ".json"
            proj_copy = copy.deepcopy(cfg.project_data)
            if cfg.project_data['data']['destination_path'] != None:
                if len(proj_copy['data']['destination_path']) > 0:
                    proj_copy['data']['destination_path'] = make_relative(
                            proj_copy['data']['destination_path'], self.project_filename)
            for scale_key in proj_copy['data']['scales'].keys():
                scale_dict = proj_copy['data']['scales'][scale_key]
                for layer in scale_dict['alignment_stack']:
                    for role in layer['images'].keys():
                        if layer['images'][role]['filename'] != None:
                            if len(layer['images'][role]['filename']) > 0:
                                layer['images'][role]['filename'] = make_relative(
                                        layer['images'][role]['filename'], self.project_filename)
            logging.info("save_project_to_file | Writing cfg.project_data to '%s'" % self.project_filename)
            logging.info('------- WRITING TO PROJECT FILE -------')
            jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
            proj_json = jde.encode(proj_copy)
            with open(self.project_filename, 'w') as f:
                f.write(proj_json)

    @Slot()
    def actual_size(self):
        logging.info("MainWindow.actual_size:")
        print_debug(90, "Setting images to actual size")
        for p in self.panel_list:
            p.dx = p.mdx = p.ldx = 0
            p.dy = p.mdy = p.ldy = 0
            p.wheel_index = 0
            p.zoom_scale = 1.0
            p.update_zpa_self()

    @Slot()
    def toggle_arrow_direction(self, checked):
        print('MainWindow.toggle_arrow_direction:')
        self.image_panel.arrow_direction = -self.image_panel.arrow_direction

    @Slot()
    def toggle_threaded_loading(self, checked):
        print('MainWindow.toggle_threaded_loading:')
        cfg.image_library.threaded_loading_enabled = checked

    @Slot()
    def toggle_annotations(self, checked):
        print('MainWindow.toggle_annotations:')
        self.draw_annotations = checked
        self.image_panel.draw_annotations = self.draw_annotations
        self.image_panel.update_multi_self()
        for p in self.panel_list:
            p.draw_annotations = self.draw_annotations
            p.update_zpa_self()

    @Slot()
    def opt_n(self, option_name, option_action):
        if 'num' in dir(option_action):
            print_debug(50, "Dynamic Option[" + str(option_action.num) + "]: \"" + option_name + "\"")
        else:
            print_debug(50, "Dynamic Option: \"" + option_name + "\"")
        print_debug(50, "  Action: " + str(option_action))

    def add_image_to_role(self, image_file_name, role_name):
        # print('add_image_to_role:')

        #### NOTE: TODO: This function is now much closer to empty_into_role and should be merged
        local_cur_scale = get_cur_scale_key()

        # print("add_image_to_role | Placing file " + str(image_file_name) + " in role " + str(role_name))
        if image_file_name != None:
            if len(image_file_name) > 0:
                used_for_this_role = [role_name in l['images'].keys() for l in
                                      cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']]
                # print("Layers using this role: " + str(used_for_this_role))
                layer_index_for_new_role = -1
                if False in used_for_this_role:
                    # This means that there is an unused slot for this role. Find the first:
                    layer_index_for_new_role = used_for_this_role.index(False)
                    # print("add_image_to_role | Inserting file " + str(image_file_name) + " in role " + str(role_name) + " into existing layer " + str(layer_index_for_new_role))
                else:
                    # This means that there are no unused slots for this role. Add a new layer
                    # print("add_image_to_role | Making a new layer for file " + str(image_file_name) + " in role " + str(role_name) + " at layer " + str(layer_index_for_new_role))
                    cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'].append(
                            copy.deepcopy(new_layer_template))
                    layer_index_for_new_role = len(
                            cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
                image_dict = \
                    cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role][
                        'images']
                image_dict[role_name] = copy.deepcopy(new_image_template)
                image_dict[role_name]['filename'] = image_file_name

    def add_empty_to_role(self, role_name):
        logging.info('MainWindow.add_empty_to_role:')
        local_cur_scale = get_cur_scale_key()
        used_for_this_role = [role_name in l['images'].keys() for l in
                              cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']]
        layer_index_for_new_role = -1
        if False in used_for_this_role:
            # There is an unused slot for this role. Find the first.
            layer_index_for_new_role = used_for_this_role.index(False)
        else:
            # There are no unused slots for this role. Add a new layer
            print(
                "Making a new layer for empty in role " + str(role_name) + " at layer " + str(layer_index_for_new_role))
            cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'].append(
                copy.deepcopy(new_layer_template))
            layer_index_for_new_role = len(cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        image_dict = cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role][
            'images']
        image_dict[role_name] = copy.deepcopy(new_image_template)
        image_dict[role_name]['filename'] = None

    def import_images(self, clear_role=False):
        ''' Import images into project '''
        logging.info('import_images | Importing images..')
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
                print_debug(40, "Selected Files: " + str(file_name_list))
                for f in file_name_list:
                    # Find next layer with an empty role matching the requested role_to_import
                    print_debug(50, "Role " + str(role_to_import) + ", Importing file: " + str(f))
                    if f is None:
                        self.add_empty_to_role(role_to_import)
                    else:
                        self.add_image_to_role(f, role_to_import)
                # Draw the panel's ("windows")
                for p in self.panel_list:
                    p.force_center = True
                    p.update_zpa_self()

        if are_images_imported():
            self.generate_scales_button.setEnabled(True)
            # img_size = get_image_size(cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][0]['images']['base']['filename'])
            img_size = get_image_size(
                    cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack'][0]['images'][
                        str(role_to_import)]['filename'])
            n_images = get_num_imported_images()
            self.hud.post('%d images imported' % n_images)
            self.hud.post('Image dimensions: ' + str(img_size[0]) + 'x' + str(img_size[1]) + ' pixels')
            link_all_stacks() #0714+
            self.center_all_images()
            self.update_panels()
        else:
            self.hud.post('No Images Were Imported', logging.WARNING)

        self.set_idle()

    def update_panels(self):
        '''Repaint the viewing port.'''
        logging.info("MainWindow.update_panels:")
        for p in self.panel_list:
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def set_def_proj_dest(self):
        '''TODO Refactor this into trash funcs'''
        print("MainWindow is setting default project destination (MainWindow.set_def_proj_dest was called by " +
              inspect.stack()[1].function + ")...")
        if self.project_filename == None:
            # self.set_status("Unable to set a project destination without a project file.\nPlease save the project file first.")
            pass
        elif len(self.project_filename) == 0:
            # self.set_status("Unable to set a project destination without a project file.\nPlease save the project file first.")
            pass
        else:
            p, e = os.path.splitext(self.project_filename)
            cfg.project_data['data']['destination_path'] = p
            # os.makedirs(cfg.project_data['data']['destination_path'])
            makedirs_exist_ok(cfg.project_data['data']['destination_path'], exist_ok=True)
            logging.info("Destination path is : " + str(cfg.project_data['data']['destination_path']))

            proj_path = self.project_filename
            dest_path = str(cfg.project_data['data']['destination_path'])
            # self.set_status("Project File: " + proj_path)

    # 0527
    def load_images_in_role(self, role, file_names):
        logging.info('MainWindow | MainWindow.load_images_in_role:')
        '''Not clear if this has any effect. Needs refactoring.'''
        self.import_images(role, file_names, clear_role=True)
        self.center_all_images()

    def define_roles(self, roles_list):
        logging.info("MainWindow | MainWindow.define_roles:")

        # Set the image panels according to the roles
        self.image_panel.set_roles(roles_list)

        # Set the Roles menu from this roles_list
        mb = self.menuBar()
        if not (mb is None):
            for m in mb.children():
                if type(m) == QMenu:
                    text_label = ''.join(m.title().split('&'))
                    if 'Images' in text_label:
                        print_debug(30, "Found Images Menu")
                        for mm in m.children():
                            if type(mm) == QMenu:
                                text_label = ''.join(mm.title().split('&'))
                                if 'Import into' in text_label:
                                    print_debug(30, "Found Import Into Menu")
                                    # Remove all the old actions:
                                    while len(mm.actions()) > 0:
                                        mm.removeAction(mm.actions()[-1])
                                    # Add the new actions
                                    for role in roles_list:
                                        item = QAction(role, self)
                                        item.triggered.connect(self.import_into_role)
                                        mm.addAction(item)
                                if 'Empty into' in text_label:
                                    print_debug(30, "Found Empty Into Menu")
                                    # Remove all the old actions:
                                    while len(mm.actions()) > 0:
                                        mm.removeAction(mm.actions()[-1])
                                    # Add the new actions
                                    for role in roles_list:
                                        item = QAction(role, self)
                                        item.triggered.connect(self.empty_into_role)
                                        mm.addAction(item)
                                if 'Clear Role' in text_label:
                                    print_debug(30, "Found Clear Role Menu")
                                    # Remove all the old actions:
                                    while len(mm.actions()) > 0:
                                        mm.removeAction(mm.actions()[-1])
                                    # Add the new actions
                                    for role in roles_list:
                                        item = QAction(role, self)
                                        item.triggered.connect(self.remove_all_from_role)
                                        mm.addAction(item)

    @Slot()
    def empty_into_role(self, checked):
        logging.info("MainWindow | MainWindow.empty_into_role:")
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
            # print("Making a new layer for <empty> in role " + str(role_to_import) + " at layer " + str(layer_index_for_new_role))
            cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'].append(
                copy.deepcopy(new_layer_template))
            layer_index_for_new_role = len(cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) - 1
        image_dict = cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'][layer_index_for_new_role][
            'images']
        image_dict[role_to_import] = copy.deepcopy(new_image_template)
        # Draw the panels ("windows")
        for p in self.panel_list:
            p.force_center = True
            p.update_zpa_self()
        self.update_win_self()

    @Slot()
    def remove_all_from_role(self, checked):
        logging.info("MainWindow.remove_all_from_role:")
        role_to_remove = str(self.sender().text())
        print_debug(10, "Remove role: " + str(role_to_remove))
        self.remove_from_role(role_to_remove)

    def remove_from_role(self, role, starting_layer=0, prompt=True):
        print("MainWindow.remove_from_role:")
        print_debug(5, "Removing " + role + " from scale " + str(get_cur_scale_key()) + " forward from layer " + str(
                starting_layer) + "  (remove_from_role)")
        actually_remove = True
        if prompt:
            actually_remove = request_confirmation("Note", "Do you want to remove all " + role + " images?")
        if actually_remove:
            print_debug(5, "Removing " + role + " images ...")
            delete_list = []
            layer_index = 0
            for layer in cfg.project_data['data']['scales'][get_cur_scale_key()]['alignment_stack']:
                if layer_index >= starting_layer:
                    print_debug(5, "Removing " + role + " from Layer " + str(layer_index))
                    if role in layer['images'].keys():
                        delete_list.append(layer['images'][role]['filename'])
                        print_debug(5, "  Removing " + str(layer['images'][role]['filename']))
                        layer['images'].pop(role)
                        # Remove the method results since they are no longer applicable
                        if role == 'aligned':
                            if 'align_to_ref_method' in layer.keys():
                                if 'method_results' in layer['align_to_ref_method']:
                                    # Set the "method_results" to an empty dictionary to signify no results:
                                    layer['align_to_ref_method']['method_results'] = {}
                layer_index += 1
            # cfg.image_library.remove_all_images()
            for fname in delete_list:
                if fname != None:
                    if os.path.exists(fname):
                        os.remove(fname)
                        cfg.image_library.remove_image_reference(fname)
            self.update_panels()  # 0503
            self.refresh_all()  # 0503

    @Slot()
    def remove_all_layers(self):
        logging.info("MainWindow.remove_all_layers:")
        # global cfg.project_data
        local_cur_scale = get_cur_scale_key()
        cfg.project_data['data']['current_layer'] = 0
        while len(cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack']) > 0:
            cfg.project_data['data']['scales'][local_cur_scale]['alignment_stack'].pop(0)
        self.update_win_self()

    @Slot()
    def remove_all_panels(self):
        logging.info("MainWindow.remove_all_panels |  Removing all panels")
        print_debug(30, "Removing all panels")
        if 'image_panel' in dir(self):
            print_debug(30, "image_panel exists")
            self.image_panel.remove_all_panels()
        else:
            print_debug(30, "image_panel does not exit!!")
        self.define_roles([])  # 0601
        self.update_win_self()

    @Slot()
    def set_max_image_size(self):
        global max_image_file_size
        input_val, ok = QInputDialog().getInt(None, "Enter Max Image File Size", "Max Image Size:", max_image_file_size)
        if ok:
            max_image_file_size = input_val

    @Slot()
    def actual_size_callback(self):
        logging.info('MainWindow.actual_size_callback:')
        # self.hud.post('Actual-sizing images...')

        self.all_images_actual_size()

    # MainWindow.center_all_images -> calls MultiImagePanel.center_all_images
    @Slot()
    def center_all_images(self, all_images_in_stack=True):
        '''NOTE: CALLS COULD BE REDUCED BY CENTERING ALL STACKS OF IMAGES NOT JUST CURRENT SCALE
        self.image_panel is a MultiImagePanel object'''
        logging.info("center_all_images | called by " + inspect.stack()[1].function)
        self.image_panel.center_all_images(all_images_in_stack=all_images_in_stack)

    @Slot()
    def refresh_all_images(self):
        # print("  MainWindow is refreshing all images (called by " + inspect.stack()[1].function + ")...")
        self.image_panel.refresh_all_images()

    @Slot()
    def all_images_actual_size(self):
        logging.info("all_images_actual_size | Actual-sizing all images.")
        self.image_panel.all_images_actual_size()

    # inspect.stack()[1].function

    def closeEvent(self, event):
        self.set_status('Exiting...')
        self.hud.post('Confirm exit AlignEM-SWiFT?')
        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
        else:
            self.hud.post('Canceling Exit Application')
            self.set_idle()
            event.ignore()

    @Slot()
    def exit_app(self):
        logging.info("MainWindow.exit_app:")
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
            logging.info('exit_app | reply=Cancel. Returning control to the app.')
            self.hud.post('Canceling exit application')
            self.set_idle()
            return
        if reply == QMessageBox.Save:
            logging.info('exit_app | reply=Save')
            self.save_project()
            self.set_status('Wrapping up...')
            logging.info('Project saved. Exiting')
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()
        if reply == QMessageBox.Discard:
            print('exit_app | reply=Discard Exiting without saving')
            self.threadpool.waitForDone(msecs=200)
            QApplication.quit()
            sys.exit()