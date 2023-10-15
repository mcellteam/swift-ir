#!/usr/bin/env python3
"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.
"""
import os
import sys
import copy
import json
import time
import datetime
import threading
import inspect
import logging
import textwrap
import getpass
from pathlib import Path
import psutil
from math import floor
import multiprocessing
import subprocess
from collections import OrderedDict
# from guppy import hpy; h=hpy()
import neuroglancer as ng

import qtawesome as qta
# from rechunker import rechunk
from qtpy.QtWebEngineWidgets import *

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

# from qtpy.QtCore import Qt, QThread, QThreadPool, QEvent, Slot, Signal, QSize, QUrl,  QTimer, QPoint, QRectF, \
#     QSettings, QObject, QFileInfo, QMutex
# from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
#     QKeySequence, QMovie, QStandardItemModel, QColor, QCursor, QImage, QPainterPath, QRegion, QPainter
# from qtpy.QtWidgets import QApplication, qApp, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
#     QStackedWidget, QGridLayout, QInputDialog, QLineEdit, QPushButton, QMessageBox, \
#     QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
#     QShortcut, QGraphicsOpacityEffect, QCheckBox, QSpinBox, QDoubleSpinBox, QRadioButton, QSlider, \
#     QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QMenuBar, QTableView, QTabWidget, QStatusBar, QTextBrowser, \
#     QFormLayout, QGroupBox, QScrollArea, QToolButton, QWidgetAction, QSpacerItem, QButtonGroup, QAbstractButton, \
#     QApplication, QPlainTextEdit, QTableWidget, QTableWidgetItem, QDockWidget, QMdiArea, QMdiSubWindow
# import pyqtgraph.examples
# print('mainwindow:Importing local modules...')
import src.config as cfg
import src.resources.icons_rc
import src.shaders
# from src.data_model import DataModel
# from src.generate_scales import GenerateScales
from src.helpers import getData, setData, print_exception, get_scale_val, \
    tracemalloc_start, tracemalloc_stop, tracemalloc_compare, tracemalloc_clear, \
    exist_aligned_zarr, isNeuroglancerRunning, \
    update_preferences_model, is_mac, hotkey, make_affine_widget_HTML, \
    is_joel, is_tacc, run_command, check_macos_isdark_theme
from src.ui.dialogs import export_affines_dialog, ExitAppDialog
from src.ui.process_monitor import HeadupDisplay
from src.align import AlignWorker
from src.scale import ScaleWorker
from src.generate_zarr import ZarrWorker
from src.ui.models.json_tree import JsonModel
from src.ui.toggle_switch import ToggleSwitch
from src.ui.tab_browser import WebBrowser
from src.ui.tab_project import ProjectTab
from src.ui.tab_open_project import OpenProject
from src.ui.layouts import HBL, VBL, HW, VW, QVLine
from src.funcs_image import SetStackCafm
from src.ui.python_console import PythonConsoleWidget
from src.ui.webpage import QuickWebPage

__all__ = ['MainWindow']

# logger = logging.getLogger(__name__)
# logger = logging.getLogger()
logger = logging.getLogger('root')
# addLoggingLevel('TRACE', logging.INFO)

DEV = is_joel()

# logger.critical('_Directory of this script: %level' % os.path.dirname(__file__))

class HudOutputFormat(logging.Formatter):
    # ANSI color codess
    grey = "\x1b[38;20m"
    warn = "\x1b[31m"
    error = "\x1b[41m"
    bold_red = "\x1b[31;1m"
    # blue = "\x1b[1;34m"
    info = "\x1b[47m"
    reset = "\x1b[0m"
    # format = '%(asctime)s %(message)s'
    format = '%(message)s'
    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: info + format + reset,
        logging.WARNING: warn + format + reset,
        logging.ERROR: error + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        # formatter = logging.Formatter(log_fmt, datefmt=None)
        return formatter.format(record)

# create logger with 'spam_application'
hudlogger = logging.getLogger("HUD")
hudlogger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(HudOutputFormat())
hudlogger.addHandler(ch)
hudlogger.propagate = False


class MainWindow(QMainWindow):
    resized = Signal()
    # keyPressed = Signal(int)
    keyPressed = Signal(QEvent)
    # finished = Signal()
    updateTable = Signal()
    tabChanged = Signal()
    cancelMultiprocessing = Signal()

    def __init__(self, data=None):
        QMainWindow.__init__(self)
        self.app = QApplication.instance()
        font = QFont("Tahoma")
        self.app.setFont(font)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName('mainwindow')
        try:
            self.branch = run_command('git', arg_list=['rev-parse', '--abbrev-ref', 'HEAD'])['out'].rstrip()
        except:
            print_exception()
            self.branch = ''
        tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        self.window_title = 'AlignEM branch: %s - %s' % (self.branch, tstamp)
        self.setWindowTitle(self.window_title)
        self.setAutoFillBackground(False)

        self.settings = QSettings("cnl", "alignem")
        if self.settings.value("windowState") == None:
            self.initSizeAndPos(cfg.WIDTH, cfg.HEIGHT)
        else:
            self.restoreState(self.settings.value("windowState"))
            self.restoreGeometry(self.settings.value("geometry"))

        # self.initThreadpool(timeout=250)
        self.menu = QMenu()
        self.pythonConsole = PythonConsoleWidget()
        # f = QFont()
        # f.setFamily('Ubuntu')
        # f.setPointSize(9)
        # self.pythonConsole.setFont(f)
        # self.menu.setFixedWidth(700)
        self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.initImageAllocations()
        self.initPrivateMembers()
        self.initOpenGlContext()
        self.initStyle()
        self.initStatusBar()
        self.initPbar()
        self.initControlPanel()
        self.initMenu()
        self.initAdvancedMenu() #self.wAdvanced
        self.initLowest8Widget()
        self.initEditorStats()
        self.initToolbar()


        self.initUI()

        QThreadPool.globalInstance().setMaxThreadCount(1)

        # self.initMenu()
        self.initWidgetSpacing()
        # self.initShortcuts()



        # self.finished.connect(self.updateProjectTable)
        self.cancelMultiprocessing.connect(self.cleanupAfterCancel)

        self.activateWindow()

        self.tell('To Relaunch on Lonestar6:\n\n  source $WORK/swift-ir/tacc_boostrap\n')

        logger.debug('\n\nIf this message is seen then the logging level is set to logging.DEBUG\n')

        if not cfg.NO_SPLASH:
            self.show_splash()

        self.bStopPbar.setEnabled(cfg.DAEMON_THREADS)

        # self.preferences = QSettings("cnl", "alignem")
        # # if not self.preferences.value("geometry") == None:
        # #     self.restoreGeometry(self.preferences.value("geometry"))
        # if not self.preferences.value("windowState") == None:
        #     self.restoreState(self.preferences.value("windowState"))

        # QApplication.setFont(QFont("Calibri"))
        # self.font = QFont("Tahoma")
        # self.app.setFont(self.font)

        self.setFocusPolicy(Qt.StrongFocus)

        # QApplication.processEvents()
        # self.resizeThings()

        # self.setWindowFlags(Qt.FramelessWindowHint)

        # self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea )
        # self.setCorner(Qt.BottomLeftCorner, Qt.LeftToolBarArea )
        # self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea )
        # self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea )
        self.setCorner(Qt.BottomRightCorner, Qt.BottomDockWidgetArea )
        # self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea )
        self.setDockNestingEnabled(True)


        self._layer_left_action = QAction()
        self._layer_left_action.triggered.connect(self.layer_left)

        self._layer_right_action = QAction()
        self._layer_right_action.triggered.connect(self.layer_right)


        self._shortcutArrowLeft = QShortcut(QKeySequence(Qt.Key_Left), self)
        self._shortcutArrowLeft.activated.connect(self.layer_left)
        self._shortcutArrowLeft.activated.connect(lambda: print("Left arrow pressed!"))
        # self._shortcutArrowLeft.setKey(QKeySequence(Qt.Key_Left))
        self._shortcutArrowLeft.setContext(Qt.WidgetShortcut)
        self._shortcutArrowRight = QShortcut(QKeySequence(Qt.Key_Right), self)
        self._shortcutArrowRight.activated.connect(self.layer_right)
        self._shortcutArrowRight.activated.connect(lambda: print("Right arrow pressed!"))
        # self._shortcutArrowRight.setKey(QKeySequence(Qt.Key_Right))
        self._shortcutArrowRight.setContext(Qt.WidgetShortcut)

        # def fn_main_window_lost_focus():
        #     logger.warning(f"\n\nMain Window lost its focus to: {self.focusWidget()}!\n")
        # 
        # self.focusOutEvent.(fn_main_window_lost_focus)
        self.focusreasons = {0: 'MouseFocusReason',
                             1: 'TabFocusReason',
                             2: 'BacktabFocusReason',
                             3: 'ActiveWindowFocusReason',
                             4: 'PopupFocusReason',
                             5: 'ShortcutFocusReason',
                             6: 'MenuBarFocusReason',
                             7: 'OtherFocusReason'}

        self._mutex = QMutex()
        self._initProjectManager()
        self.setdw_hud(True)

    # def focusInEvent(self, event):
    #     logger.warning(f"\nFocus GAINED - reason : ({event.reason()}) {self.focusreasons[event.reason()]}"
    #                    f"\nFocus belongs to      : {self.focusWidget()}")
    #
    # def focusOutEvent(self, event):
    #     logger.warning(f"\nFocus LOST - reason : ({event.reason()}) {self.focusreasons[event.reason()]}"
    #                    f"\nFocus belongs to    : {self.focusWidget()}")
    #     # if type(self.focusWidget()) != QTextEdit:
    #     #     self.focusW = self.focusWidget()
    #     # self.setFocus()

    # def pyqtgraph_examples(self):
    #     pyqtgraph.examples.run()


    def TO(self):
        return self._getTabObject()

    def runUiChecks(self):
        if not getData('state,manual_mode'):
            assert (cfg.emViewer.state.layout.type == self.comboboxNgLayout.currentText())


    def memory(self):
        if self._isProjectTab():
            mem = psutil.Process(os.getpid()).memory_info().rss
            MB = f'{mem / 1024 ** 2:.0f} MB'
            GB = f'{mem / 1024 ** 3:.0f} GB'
            s = f'Main Memory Usage: {MB}, {GB}'
            self.tell(f'<span style="color: #FFFF66;"><b>{s}</b></span>')
            logger.critical(s)

    def mem(self):
        if self._isProjectTab():
            s1 = f'Memory Usage / Task (MB): '
            # s2 = f'Memory Usage / Task (GB): '
            try:
                if self.dm.is_aligned():
                    for l in self.dm.get_iter():
                        try:
                            mb = l['levels'][self.dm.scale]['results']['memory_mb']
                            # gb = ['levels'][self.dm.scale]['method_results']['memory_gb']
                            MB = f'{mb:.0f}, '
                            # GB = f'{gb:.0f}, '
                            s1 += MB
                            # s2 += GB
                        except:
                            pass

                    self.tell(f'<span style="color: #FFFF66;"><b>{s1}</b></span>')
                    # self.tell(f'<span style="color: #FFFF66;"><b>{s2}</b></span>')
                    logger.critical(s1)
                    # logger.critical(s2)
                else:
                    self.tell(f'No memory data to report.')
                    logger.critical(f'No memory data to report.')
            except:
                print_exception()


    # def resizeThings(self):
    #     logger.critical('Resizing things...')

        # if self._isProjectTab():
        #     self.pt.fn_hwidgetChanged()
        #     logger.critical('Resizing things, isProjectTab...')
        #     h = self.pt.wEditAlignment.height()
        #     # self.pt.sideTabs.setFixedWidth(int(.26 * self.width()))
        #     ms_w = int(h/4 + 0.5)
        #     tn_w = int((h - self.pt.tn_ref_lab.height() - self.pt.tn_ref_lab.height()) / 2 + 0.5)
        #     self.pt.ms_widget.setFixedWidth(ms_w)
        #     self.pt.match_widget.setFixedWidth(ms_w)
        #     self.pt.tn_widget.setFixedWidth(tn_w)


    def restore_tabs(self, settings):
        '''self.restore_tabs(self.preferences)'''
        finfo = QFileInfo(settings.fileName())
        if finfo.exists() and finfo.isFile():
            for w in qApp.allWidgets():
                mo = w.metaObject()
                if w.objectName() != "":
                    for i in range(mo.propertyCount()):
                        name = mo.property(i).name()
                        val = settings.value("{}/{}".format(w.objectName(), name), w.property(name))
                        w.setProperty(name, val)


    def save_tabs(self, settings):
        '''self.save_tabs(self.preferences)'''
        for w in qApp.allWidgets():
            mo = w.metaObject()
            if w.objectName() != "":
                for i in range(mo.propertyCount()):
                    name = mo.property(i).name()
                    settings.setValue("{}/{}".format(w.objectName(), name), w.property(name))



    def initSizeAndPos(self, width, height):
        self.resize(width, height)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()  # cp PyQt5.QtCore.QPoint
        # cp.setX(cp.x() - 200)
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        # self.showMaximized(

    def cleanupAfterCancel(self):
        logger.critical('Cleaning Up After Multiprocessing Tasks Were Canceled...')
        # self.pt.snr_plot.initSnrPlot()
        self.wPbar.hide()
        # self.pt.updateTreeWidget()
        self.dataUpdateWidgets()
        self.updateEnabledButtons()
        if self.dwSnr.isVisible():
            self.pt.dSnr_plot.initSnrPlot()

    def hardRestartNg(self):
        caller = inspect.stack()[1].function
        logger.critical('\n\n**HARD** Restarting Neuroglancer (caller: %s)...\n' % caller)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if self._isProjectTab() or self._isZarrTab():
            if ng.is_server_running():
                logger.info('Stopping Neuroglancer...')
                ng.server.stop()
            elif self.pt:
                self.pt.initNeuroglancer()
            elif cfg.zarr_tab:
                cfg.zarr_tab.load()
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)


    def _refresh(self, silently=False):
        caller = inspect.stack()[1].function
        logger.info(f'')
        self.setUpdatesEnabled(True)
        if not self._working:
            if not silently:
                self.tell('Refreshing...')
            if self._isProjectTab():
                self.pt.refreshTab()
            elif self._isOpenProjTab():
                self.pm.refresh()
            elif self._getTabType() == 'WebBrowser':
                self._getTabObject().browser.page().triggerAction(QWebEnginePage.Reload)
            elif self._getTabType() == 'QWebEngineView':
                self.globTabs.currentWidget().reload()
            self.updateEnabledButtons()
            self.initStyle()
            self.hud.done()
        else:
            self.warn('The application is busy')


    def shutdownNeuroglancer(self):
        if ng.is_server_running():
            if DEV:
                logger.info('[DEV] Stopping Neuroglancer...')
            # self.tell('Stopping Neuroglancer...')
            ng.server.stop()
            time.sleep(.1)

    def tell(self, message):
        hudlogger.info(f"[HUD] {message}")
        self.hud.post(message, level=logging.INFO)
        self.update()

    def warn(self, message):
        hudlogger.warning(f"[HUD WARNING] {message}")
        self.hud.post(message, level=logging.WARNING)
        self.statusBar.showMessage(message, msecs=3000)
        self.update()

    def err(self, message):
        hudlogger.error(f"[HUD ERROR] {message}")
        self.hud.post(message, level=logging.ERROR)
        self.update()

    def bug(self, message):
        self.hud.post(message, level=logging.DEBUG)
        self.update()

    # def initThreadpool(self, timeout=1000):

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

        self.pm = None
        self.pt = None

        self.uiUpdateTimer = QTimer()
        self.uiUpdateTimer.setSingleShot(True)
        self.uiUpdateTimer.timeout.connect(self.dataUpdateWidgets)
        self.uiUpdateTimer.setInterval(cfg.UI_UPDATE_TIMEOUT)

        self._unsaved_changes = False
        self._working = False
        self._scales_combobox_switch = 0  # 1125
        self._isProfiling = 0
        self.detachedNg = None
        self.count_calls = {}
        self._exiting = 0
        self._old_pos = None
        self.curTabID = None
        self._lastTab = None

        self._dock_snr = None
        self._dock_matches = None
        self._dock_thumbs = None

        self._snr_before = None

    def initStyle(self):
        logger.info('')
        if is_mac() and check_macos_isdark_theme():
            self._icon_color = '#39ff14'
            qta.set_defaults(color='#daebfe')
            rel_path = 'src/style/newstyle_dark.qss'
            logger.info("applying theme: src/style/newstyle_dark.qss...")
            # self.pythonConsole.setStyleSheet("""
            # font-size: 10px;
            # font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
            # """)
        else:
            self._icon_color = '#161c20'
            qta.set_defaults(color='#161c20')
            rel_path = 'src/style/newstyle.qss'
            logger.info("applying theme: src/style/newstyle.qss...")
            # self.pythonConsole.setStyleSheet("""
            # font-size: 10px;
            # font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
            # """)

        self.main_stylesheet = os.path.abspath(rel_path)
        with open(self.main_stylesheet, 'r') as f:
            style = f.read()
        self.setStyleSheet(style)


    def test(self):
        if self._isProjectTab():
            logger.critical(f'id(self.pt)   = {id(self.pt)}')
            # logger.critical(f'cfg.dataById = {str(cfg.dataById)}')
            logger.critical(f'self.dm == cfg.dataById[{id(self.pt)}]? {self.dm == cfg.dataById[id(self.pt)]}')


    def initEditorStats(self):

        self.flStats = QFormLayout()
        self.flStats.setVerticalSpacing(2)
        self.flStats.setContentsMargins(0, 0, 0, 0)
        self.results0 = QLabel()  # Image dimensions
        self.results1 = QLabel()  # # of images
        self.results2 = QLabel()  # SNR average
        self.results3 = QWidget()
        self.results3_fl = QFormLayout()
        self.results3_fl.setContentsMargins(0, 0, 0, 0)
        self.results3_fl.setVerticalSpacing(2)
        self.results3.setLayout(self.results3_fl)
        self.flStats.addRow('Image Dimensions', self.results0)
        self.flStats.addRow('# Images', self.results1)
        self.flStats.addRow('SNR (average)', self.results2)
        self.secDetails_fl = QFormLayout()
        self.secDetails_fl.setVerticalSpacing(2)
        self.secDetails_fl.setHorizontalSpacing(4)
        self.secDetails_fl.setContentsMargins(0, 0, 0, 0)
        secStyle = """ font-weight: 300; background-color: #dedede; """
        self.secName = QLabel()
        self.secReference = QLabel()
        self.secExcluded = QLabel()
        self.secHasBB = QLabel()
        self.secUseBB = QLabel()
        self.secAlignmentMethod = QLabel()
        self.secSrcImageSize = QLabel()
        self.secAlignedImageSize = QLabel()
        self.secSNR = QLabel()
        self.secDefaults = QLabel()
        self.secName.setStyleSheet(secStyle)
        self.secReference.setStyleSheet(secStyle)
        self.secExcluded.setStyleSheet(secStyle)
        self.secHasBB.setStyleSheet(secStyle)
        self.secUseBB.setStyleSheet(secStyle)
        self.secAlignmentMethod.setStyleSheet(secStyle)
        self.secSrcImageSize.setStyleSheet(secStyle)
        self.secAlignedImageSize.setStyleSheet(secStyle)
        self.secSNR.setStyleSheet(secStyle)
        self.secDefaults.setStyleSheet(secStyle)
        self.secAffine = QLabel()
        self.gb_affine = QGroupBox("Affine")
        self.gb_affine.setLayout(VBL(self.secAffine))
        wids = [self.secName, self.secReference, self.secSNR, self.secAlignmentMethod, self.secSrcImageSize,
                self.secAlignedImageSize, self.secExcluded, self.secHasBB, self.secUseBB, self.gb_affine]
        for w in wids:
            w.setStyleSheet("""background-color: #161c20; color: #f3f6fb;""")

        self.secDetails = OrderedDict({
            'Name': self.secName,
            'Reference': self.secReference,
            'SNR': self.secSNR,
            'Alignment Method': self.secAlignmentMethod,
            'Source Image Size': self.secSrcImageSize,
            'Aligned Image Size': self.secAlignedImageSize,
            'Excluded Sections': self.secExcluded,
            'Has Bounding Box': self.secHasBB,
            'Use Bounding Box': self.secUseBB,
            'Affine': self.gb_affine,
            # 'Changes': self.secDefaults,
        })
        for i in range(len(self.secDetails)):
            self.secDetails_fl.addRow(list(self.secDetails.items())[i][0], list(self.secDetails.items())[i][1])

        self.wStats = QWidget()
        self.wStats.setStyleSheet("""background-color: #161c20; color: #f3f6fb; font-size: 10px; font-weight: 600;""")
        self.wStats.setContentsMargins(0, 0, 0, 0)
        # self.secDetails_fl.addWidget(self.gb_affine)
        self.wStats.setLayout(self.secDetails_fl)
        self.wStats.setFixedSize(QSize(300,240))
        self.wStats.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.saStats.setWidget(VW(self.wStats, self.gb_affine))
        # self.saStats = QScrollArea()
        # self.saStats.setStyleSheet("QScrollArea {border: none;}")
        # self.saStats.setWidgetResizable(True)
        # self.saStats.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.saStats.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.saStats.setWidget(self.wStats)
        # self.saStats.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # self.saStats.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)



    def updateStats(self):
        logger.info('')
        if self._isProjectTab():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}] Updating stats widget...')
            self.secName.setText(self.dm.name())
            ref = self.dm.name_ref()
            if ref == '':
                ref = 'None'
            self.secReference.setText(ref)
            self.secAlignmentMethod.setText(self.dm.method_pretty())
            # self.secSNR.setText(self.dm.snr_report()[5:])
            # self.secSNR.setText('<span style="font-color: red;"><b>%.2f</b></span>' % self.dm.snr())
            # self.secDetails[2][1].setText(str(self.dm.skips_list()))
            skips = self.dm.skips_list()
            if skips == []:
                self.secExcluded.setText('None')
            else:
                self.secExcluded.setText('\n'.join([f'z-index: {a}, name: {b}' for a, b in skips]))
            self.secHasBB.setText(str(self.dm.has_bb()))
            self.secUseBB.setText(str(self.dm.use_bb()))
            siz = self.dm.image_size()
            self.secSrcImageSize.setText('%dx%d pixels' % (siz[0], siz[1]))
            if self.dm.is_aligned():
                #Todo come back and upgrade this
                # try:
                #     self.secAlignedImageSize.setText('%dx%d pixels' % self.dm.image_size_aligned())
                # except:
                #     print_exception()
                if self.dm.zpos <= self.dm.first_unskipped():
                    self.secSNR.setText('--')
                else:
                    try:
                        self.secSNR.setText(
                            '<span style="color: #a30000;"><b>%.2f</b></span><span>&nbsp;&nbsp;(%s)</span>' % (
                                self.dm.snr(), ",  ".join(["%.2f" % x for x in self.dm.snr_components()])))
                    except:
                        print_exception()
            else:
                self.secAlignedImageSize.setText('--')
                self.secSNR.setText('--')
            # self.secDefaults.setText(self.dm.defaults_pretty)
            # self.secDefaults.setText(str([list(map(str,a)) for a in self.dm.data_comports()[1]]))
            self.secAffine.setText(make_affine_widget_HTML(self.dm.afm(), self.dm.cafm()))
        else:
            self.secName.setText('')
            self.secReference.setText('')
            self.secAlignmentMethod.setText('')
            self.secExcluded.setText('')
            self.secHasBB.setText('')
            self.secUseBB.setText('')
            self.secSrcImageSize.setText('')
            self.secAlignedImageSize.setText('')
            self.secSNR.setText('')


    def updateDwMatches(self):
        if self.dwMatches.isVisible():
            self.setSignalsPixmaps()
            self.setTargKargPixmaps()

    def setSignalsPixmaps(self, z=None):

        if self.dwMatches.isVisible():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if not hasattr(cfg, 'data'):
                return

            if z == None: z = self.dm.zpos
            if not self._isProjectTab():
                logger.warning('Not a project tab')
                return



            thumbs = self.dm.get_signals_filenames(l=z)
            snr_vals = copy.deepcopy(self.dm.snr_components(l=z))
            # logger.info(f'snr_vals = {snr_vals}')
            count = 0
            for i in range(4):
                if not self.pt.msList[i]._noImage:
                    self.pt.msList[i].set_no_image()

            method = self.dm.method(l=z)
            # if method == 'grid_custom':
            if method == 'grid':
                regions = self.dm.quadrants
                names = self.dm.get_grid_filenames(l=z)
                # logger.critical(f'# names: {len(names)}')
                # logger.critical(f'snr vals: {snr_vals}')
                # logger.critical(f'name:\n{names}')
                for i in range(4):
                    if regions[i]:
                        try:
                            try:
                                snr = snr_vals[count]
                                assert snr > 0.0
                            except:
                                self.pt.msList[i].set_no_image()
                                continue
                            # logger.info(f'Setting data for {names[i]}, snr={float(snr)}')
                            self.pt.msList[i].set_data(path=names[i], snr=float(snr))
                            self.pt.msList[i].update()
                            count += 1
                        except:
                            print_exception()
                            logger.warning('There was a problem with index %d...' % i)
                            logger.warning('%s' % (names[i]))
                    else:
                        self.pt.msList[i].set_no_image()
                        # self.pt.msList[i].update()

            # elif self.dm.current_method == 'manual-hint':
            #     self.dm.snr_components()
            elif method == 'manual_strict':
                for i in range(4):
                    if not self.pt.msList[i]._noImage:
                        self.pt.msList[i].set_no_image()
                        # self.pt.msList[i].update()

            elif method == 'manual':
                #Todo #mode check mode for hint vs strict
                indexes = []
                for n in thumbs:
                    fn, _ = os.path.splitext(n)
                    indexes.append(int(fn[-1]))

                for i in range(0,4):

                    if i in indexes:
                        try:
                            try:
                                snr = snr_vals.pop(0)
                                assert snr > 0.0
                            except:
                                # logger.info(f'no SNR data for corr signal index {i}')
                                self.pt.msList[i].set_no_image()
                                print_exception()
                                continue

                            # self.pt.msList[i].set_data(path=thumbs[i], snr=float(snr))
                            self.pt.msList[i].set_data(path=thumbs.pop(0), snr=float(snr))
                        except:
                            print_exception()
                            self.pt.msList[i].set_no_image()
                            logger.warning(f'There was a problem with index {i}, {thumbs[i]}')
                        # finally:
                        #     self.pt.msList[i].update()
                    else:
                        self.pt.msList[i].set_no_image()
                        # self.pt.msList[i].update()
            self.dwMatches.update()
                        
        


    def setTargKargPixmaps(self, z=None):

        if self.dwMatches.isVisible():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')

            if not hasattr(cfg, 'data'):
                return

            if z == None:
                z = self.dm.zpos

            # logger.info('')
            # caller = inspect.stack()[1].function
            # logger.critical(f'setTargKargPixmaps [{caller}] >>>>')

            # basename = self.dm.name()
            # path, extension = os.path.splitext(basename)
            basename = self.dm.name(l=z)
            filename, extension = os.path.splitext(basename)

            for i in range(4):
                self.pt.match_thumbnails[i].set_no_image()

            if self.dm.skipped(l=z):
                return

            # for i in range(4):
            #     if not self.pt.match_thumbnails[i]._noImage:
            #         self.pt.match_thumbnails[i].set_no_image()

            if getData('state,targ_karg_toggle'):
                tkarg = 'k'
            else:
                tkarg = 't'

            method = self.dm.current_method
            files = []
            dir_matches = self.dm.dir_matches()
            for i in range(0, 4):
                name = '%s_%s_%s_%d%s' % (filename, method, tkarg, i, extension)
                files.append((i, os.path.join(dir_matches, name)))

            # logger.info(f'Files:\n{files}')

            if method == 'grid':
                # for i in range(n_cutouts):
                for i in range(0, 4):
                    use = self.dm.quadrants[i]

                    # logger.info(f'file  : {files[i]}  exists? : {os.path.exists(files[i])}  use? : {use}')
                    path = os.path.join(self.dm.data_location, 'matches', self.dm.scale, files[i][1])
                    if use and os.path.exists(path):
                        self.pt.match_thumbnails[i].path = path
                        try:
                            # self.pt.match_thumbnails[i].showPixmap()
                            self.pt.match_thumbnails[i].set_data(path)
                        except:
                            self.pt.match_thumbnails[i].set_no_image()
                    else:
                        self.pt.match_thumbnails[i].set_no_image()
                    self.pt.match_thumbnails[i].show()

            if self.dm.current_method == 'manual':
                # self.pt.match_thumbnails[3].hide()
                for i in range(0, 3):
                    path = os.path.join(self.dm.data_location, 'matches', self.dm.scale, files[i][1])
                    if os.path.exists(path):
                        self.pt.match_thumbnails[i].path = path
                        self.pt.match_thumbnails[i].set_data(path)
                    else:
                        self.pt.match_thumbnails[i].set_no_image()

                    # try:
                    #     # if DEV:
                    #     #     logger.info(f'path: {path}')
                    #     assert os.path.exists(path)
                    # except:
                    #     # print_exception(extra=f"path = {path}")
                    #     # logger.critical('Handling Exception...')
                    #     self.pt.match_thumbnails[i].set_no_image()
                    #     continue
                    # try:
                    #     self.pt.match_thumbnails[i].path = path
                    #     # self.pt.match_thumbnails[i].showPixmap()
                    #     self.pt.match_thumbnails[i].set_data(path)
                    # except:
                    #     self.pt.match_thumbnails[i].set_no_image()
                    #     print_exception()

            self.dwMatches.update()

    def callbackDwVisibilityChanged(self):
        logger.debug('')
        # caller = inspect.stack()[1].function
        # logger.info(f'[{caller}] [{caller_name()}] {self.dwPython.isVisible()} {self.dw_hud.isVisible()} {self.dwNotes.isVisible()}')
        self.tbbPython.setChecked(self.dwPython.isVisible())
        self.tbbHud.setChecked(self.dw_hud.isVisible())
        self.tbbNotes.setChecked(self.dwNotes.isVisible())
        self.tbbThumbs.setChecked(self.dwThumbs.isVisible())
        self.tbbMatches.setChecked(self.dwMatches.isVisible())
        self.tbbSnr.setChecked(self.dwSnr.isVisible())

        self.setUpdatesEnabled(False)
        w = self.globTabs.width()
        half_w = int(w / 2)
        third_w = int(w / 3)
        fourth_w = int(w / 4)

        self.resizeDocks((self.dw_hud, self.dwSnr), (half_w, half_w), Qt.Horizontal)
        self.resizeDocks((self.dw_hud, self.dwPython), (half_w, half_w), Qt.Horizontal)
        self.resizeDocks((self.dwSnr, self.dwPython), (half_w, half_w), Qt.Horizontal)

        self.resizeDocks((self.dwPython, self.dwNotes), (half_w, half_w), Qt.Horizontal)
        self.resizeDocks((self.dw_hud, self.dwNotes), (half_w, half_w), Qt.Horizontal)
        self.resizeDocks((self.dwSnr, self.dwNotes), (half_w, half_w), Qt.Horizontal)

        self.resizeDocks((self.dw_hud, self.dwSnr, self.dwPython), (third_w, third_w, third_w), Qt.Horizontal)
        self.resizeDocks((self.dw_hud, self.dwSnr, self.dwPython, self.dwNotes), (fourth_w, fourth_w, fourth_w,
                                                                                  fourth_w), Qt.Horizontal)
        self.setUpdatesEnabled(True)


    def setdw_python(self, state):
        logger.info('')
        # caller = inspect.stack()[1].function
        # logger.info(f'[{caller}], state={state}')
        self.setUpdatesEnabled(False)

        self.dwPython.setVisible(state)
        self.aPython.setText(('Show Python console', 'Hide Python console')[state])
        self.tbbPython.setToolTip((f"Show Python console {hotkey('P')}",
                                  f"Hide Python console {hotkey('P')}")[state])

        self.setUpdatesEnabled(True)


    def setdw_hud(self, state):
        logger.info('')
        self.tbbHud.setChecked(state)
        self.setUpdatesEnabled(False)
        self.dw_hud.setVisible(state)
        tip1 = '\n'.join(f"Show Head-up-display/process monitor {hotkey('H')}")
        tip2 = '\n'.join(f"Show Head-up-display/process monitor {hotkey('H')}")
        tip = (tip1, tip2)[state]
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.aHud.setText(tip)
        self.tbbHud.setToolTip(tip)
        self.setUpdatesEnabled(True)


    def setdw_thumbs(self, state):
        logger.info('')
        # caller = inspect.stack()[1].function
        # logger.info(f"[{caller}]")
        if not self._isProjectTab():
            state = False

        self.tbbThumbs.setChecked(state)
        self.dwThumbs.setVisible(state)
        tip1 = '\n'.join(f"Show Source Thumbnails ({hotkey('T')})")
        tip2 = '\n'.join(f"Hide Source Thumbnails ({hotkey('T')})")
        tip = (tip1, tip2)[state]
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.aThumbs.setText(tip)
        self.tbbThumbs.setToolTip(tip)

        if state:
            self.setSignalsPixmaps()
            self.setTargKargPixmaps()
            # QApplication.processEvents() #1015-
            h = self.dwThumbs.height() - self.pt.tn_ref_lab.height() - self.pt.tn_tra_lab.height()
            w = int(h / 2 + .5) - 10
            self.pt.tn_widget.setMaximumWidth(w)


    def setdw_matches(self, state):
        logger.info('')
        if not self._isProjectTab():
            state = False
        self.tbbMatches.setChecked(state)
        self.dwMatches.setVisible(state)
        tip1 = '\n'.join(f"Show Matches and Signals ({hotkey('M')})")
        tip2 = '\n'.join(f"Hide Macthes and Signals ({hotkey('M')})")
        tip = (tip1, tip2)[state]
        self.aMatches.setText(tip)
        self.tbbMatches.setToolTip(tip)

        if state:
            self.setSignalsPixmaps()
            self.setTargKargPixmaps()
            # QApplication.processEvents() #1015-
            h = self.dwMatches.height() - self.pt.mwTitle.height()
            self.pt.match_widget.setMaximumWidth(int(h /2 + .5) - 4)


    def setdw_notes(self, state):
        logger.info('')
        # self.setUpdatesEnabled(False)
        self.dwNotes.setVisible(state)
        tip1 = f"Show Notepad {hotkey('Z')}"
        tip2 = f"Hide Notepad {hotkey('Z')}"
        tip = (tip1, tip2)[state]
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.aNotes.setText(tip)
        self.tbbNotes.setToolTip(tip)
        self.updateNotes()
        # self.setUpdatesEnabled(True)


    def setdw_snr(self, state):
        logger.info('')
        if not self._isProjectTab():
            state = False

        self.tbbSnr.setChecked(state)
        self.dwSnr.setVisible(state)
        if self._isProjectTab():
            if state:
                self.pt.dSnr_plot.initSnrPlot()

        tip1 = f"Show SNR plot {hotkey('L')}"
        tip2 = f"Hide SNR plot {hotkey('L')}"
        tip = (tip1, tip2)[state]
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.aSnr.setText(tip)
        self.tbbSnr.setToolTip(tip)


    def _showSNRcheck(self, s=None):
        # logger.info('')
        # caller = inspect.stack()[1].function
        if s == None: s = self.dm.level
        if self.dm.is_aligned():
            # logger.info('Checking SNR data for %level...' % self.dm.level_pretty(level=level))
            failed = self.dm.check_snr_status()
            if len(failed) == len(self.dm):
                self.warn('No SNR Data Available for %s' % self.dm.level_pretty(s=s))
            elif failed:
                indexes, names = zip(*failed)
                lst_names = ''
                for name in names:
                    lst_names += f'\n  Section: {name}'
                self.warn(f'No SNR Data For Sections: {", ".join(map(str, indexes))}')

    # def regenerateOne(self):
    #     self.regenerateAll(scale=self.dm.level, indexes=[self.dm.zpos])


    def regenerateAll(self, scale=None, indexes=None, ignore_bb=True) -> None:
        '''Note: For now this will always reallocate Zarr, i.e. expects arguments for full stack'''
        logger.info(f'scale: {scale}')
        logger.info(f'self.dm.scale: {self.dm.scale}')
        if scale == None:
            scale = self.dm.scale
        if indexes == None: indexes = list(range(0,len(self.dm)))
        # self.align(scale=scale, indexes=indexes, align=False, regenerate=True, ignore_bb=ignore_bb)
        self.align(dm=self.dm, indexes=indexes)


    def verify_alignment_readiness(self) -> bool:
        # logger.critical('')
        ans = False
        if not self.dm:
            self.warn('No project yet!')
        elif self._working == True:
            self.warn('Another Process is Running')
        elif not self.dm.is_alignable():
            warning_msg = "Another scale must be aligned first!"
            self.warn(warning_msg)
        else:
            ans = True
        # logger.info(f'Returning: {ans}')
        return ans

    def present_snr_results(self, indexes):
        snr_before = self._snr_before
        snr_after = self.dm.snr_list()
        try:
            import statistics
            if self.dm.is_aligned():
                logger.info('Alignment seems successful')
            else:
                self.warn('Something Went Wrong')
            logger.info('Calculating SNR Diff Values...')
            mean_before = statistics.fmean(snr_before)
            mean_after = statistics.fmean(snr_after)
            diff_avg = mean_after - mean_before
            delta_snr_list = self.dm.delta_snr_list(snr_before, snr_after)
            delta_list = [delta_snr_list[i] for i in indexes]
            no_chg = [i for i, x in enumerate(delta_list) if x == 0]
            pos = [i for i, x in enumerate(delta_list) if x > 0]
            neg = [i for i, x in enumerate(delta_list) if x < 0]
            self.tell('Re-alignment Results:')
            self.tell('  # Better     (SNR ↑) : %s' % ' '.join(map(str, pos)))
            self.tell('  # Worse      (SNR ↓) : %s' % ' '.join(map(str, neg)))
            self.tell('  # No Change  (SNR =) : %s' % ' '.join(map(str, no_chg)))
            self.tell('  Total Avg. SNR       : %.3f' % (self.dm.snr_average()))
            if abs(diff_avg) < .001:
                self.tell('  Δ AVG. SNR           : <span style="color: #66FF00;"><b>%.4g (NO CHANGE)</b></span>' %
                          diff_avg)
            elif diff_avg < 0:
                self.tell('  Δ AVG. SNR           : <span style="color: #a30000;"><b>%.4g (WORSE)</b></span>' %
                          diff_avg)
            else:
                self.tell('  Δ AVG. SNR           : <span style="color: #66FF00;"><b>%.4g (BETTER)</b></span>' %
                          diff_avg)

        except:
            logger.warning('Unable To Present SNR Results')


    def onAlignmentEnd(self):
        #Todo make this atomic for scale that was just aligned. Cant be current scale.
        caller = inspect.stack()[1].function
        self.tell(f'Running post-alignment tasks...')
        t0 = time.time()
        self._working = False
        self.updateDwMatches()
        logger.info(f"SNR: {self.dm.snr()}")

        self.updateEnabledButtons()
        self.updateLowest8widget()
        self.dataUpdateWidgets() #1015+

        if self._isProjectTab():
            # self._showSNRcheck()
            if self.dm.is_aligned():
                setData('state,neuroglancer,layout', '4panel')
                if not self.dm['level_data'][self.dm.level]['aligned']:
                    self.dm['level_data'][self.dm.level]['initial_snr'] = self.dm.snr_list()
                    self.dm['level_data'][self.dm.level]['aligned'] = True
                if self.pt.wTabs.currentIndex() == 1:
                    self.pt.gifPlayer.set()
                self.setdw_snr(True)  # Also initializes
                self.setdw_matches(True)
                if self.pt.wTabs.currentIndex() == 2:
                    self.pt.snr_plot.initSnrPlot()
            else:
                setData('state,neuroglancer,layout', 'xy')

        self.pt.initNeuroglancer()

        dt = time.time() - t0
        logger.info(f'  Elapsed Time         : {dt:.2f}s')
        logger.info(f"Alignment Complete")


    def onFixAll(self):
        pass


    def alignAllScales(self):
        if self._isProjectTab():
            scales = self.dm.scales
            scales.reverse()
            alignThese = []
            for s in scales:
                if not self.dm.is_aligned(s=s):
                    alignThese.append(s)
                #     alignThese.app

            self.tell(f'# Scales Unaligned: {len(alignThese)}. Aligning now...')
            ntasks = 4 * len(alignThese)
            for s in alignThese:
                self.dm.level = s
                # self.pt.initNeuroglancer()
                self.pt.refreshTab()
                self.dataUpdateWidgets()
                self.alignAll()


    def alignOne(self, dm=None, index=None, regenerate=False, align=True):
    # def alignOne(self, dm=None, index=None, regenerate=False, align=True):
        self.tell('Aligning Section #%d (%s)...' % (self.dm.zpos, self.dm.level_pretty()))
        if dm == None:
            dm = self.dm
        if index == None:
            index = self.dm.zpos
        self.align(
            dm=dm,
            indexes=[index],
        )


    @Slot()
    def alignAll(self):

        if self._isProjectTab():
            if self.dm.is_alignable():
                logger.info('\n\nAligning All...\n')
                indexes = list(range(0,len(self.dm)))
                self.align(dm=self.dm, indexes=indexes)
            else:
                logger.warning("This scale is not alignable!")

    @Slot()
    def regenZarr(self):

        renew = not self.dm['level_data'][cfg.data.level]['zarr_made']

        if self._isProjectTab():
            if self.dm.is_aligned():
                logger.info('Regenerating Zarr...')
                self.bRegenZarr.setEnabled(False)
                self._zarrThread = QThread()
                self._zarrworker = ZarrWorker(dm=self.dm, renew=renew)
                self._zarrThread.started.connect(self._zarrworker.run)  # Step 5: Connect signals and slots
                self._zarrThread.finished.connect(self._zarrThread.deleteLater)
                self._zarrworker.moveToThread(self._zarrThread)  # Step 4: Move worker to the thread
                self._zarrworker.progress.connect(self.setPbar)
                self._zarrworker.initPbar.connect(self.resetPbar)
                self._zarrworker.hudMessage.connect(self.tell)
                self._zarrworker.hudWarning.connect(self.warn)
                self._zarrworker.finished.connect(self._zarrThread.quit)
                self._zarrworker.finished.connect(self._autosave)
                self._zarrworker.finished.connect(lambda: self.wPbar.hide())
                self._zarrworker.finished.connect(lambda: self.dm.setZarrMade(True))
                self._zarrworker.finished.connect(lambda: self.bRegenZarr.setEnabled(True))
                self._zarrworker.finished.connect(self.dataUpdateWidgets)
                self._zarrworker.finished.connect(lambda: self.pt.initNeuroglancer(init_all=True))
                self._zarrworker.finished.connect(lambda: print('Finished'))
                self._zarrThread.start()  # Step 6: Start the thread


    @Slot()
    def align(self, dm, indexes=()):
    # def align(self, dm, align_indexes=(), regen_indexes=(), scale=None, renew_od=False, reallocate_zarr=False,
    #           align=True, regenerate=True, ignore_bb=False):
        ready = self.dm['level_data'][self.dm.scale]['alignment_ready']
        if not ready:
            logger.warning("Not ready to align yet!")
            self.warn("Please pull settings before aligning (Edit Alignment > Pull Settings)")
            return

        if self.dm.level != self.dm.coarsest_scale_key():
            if not self.dm.is_aligned():
                self.tell("Pulling settings from reduced scale level automatically...")
                self.dm.pullSettings()

        logger.critical('')
        scale = dm.scale

        if self._working == True:
            self.warn('Another Process is Already Running')
            return

        if hasattr(self, '_scaleworker'):
            try:
                self._scaleworker.stop()
            except:
                print_exception()
            # logger.warning('\n\nSleeping for 2 seconds (hasattr: _scaleworker)...\n')
            # time.sleep(2)
            del self._scaleworker
        if hasattr(self, '_alignworker'):
            try:
                self._alignworker.stop()
            except:
                print_exception()
            # logger.warning('\n\nSleeping for 2 seconds (hasattr: _alignworker)...\n')
            # time.sleep(2)
            del self._alignworker

        self.shutdownNeuroglancer() #1013-

        self.tell("%s Affines (%s)..." % (('Initializing', 'Refining')[dm.isRefinement()], dm.level_pretty(s=scale)))
        # logger.info(f'Aligning indexes:{indexes}, {self.dm.level_pretty(scale)}...')
        self._snr_before = self.dm.snr_list()

        # self.shutdownNeuroglancer()
        logger.info("Setting mp debugging...")
        if cfg.DEBUG_MP:
            # if 1:
            logger.warning('Multiprocessing Module Debugging is Enabled!')
            mpl = multiprocessing.log_to_stderr()
            mpl.setLevel(logging.DEBUG)

        logger.info("Instantiating Thread...")
        self._alignThread = QThread()  # Step 2: Create a QThread object
        logger.info("Starting background worker...")
        self._alignworker = AlignWorker(
            dm=dm,
            path=None,
            scale=scale,
            indexes=indexes,
        )  # Step 3: Create a worker object
        logger.info("Connecting worker signals...")
        self._alignThread.started.connect(self._alignworker.run)  # Step 5: Connect signals and slots
        self._alignThread.finished.connect(self._alignThread.deleteLater)
        self._alignworker.moveToThread(self._alignThread)  # Step 4: Move worker to the thread

        self._alignworker.progress.connect(self.setPbar)
        self._alignworker.initPbar.connect(self.resetPbar)
        self._alignworker.hudMessage.connect(self.tell)
        self._alignworker.hudWarning.connect(self.warn)
        self._alignworker.finished.connect(self._alignThread.quit)
        self._alignworker.finished.connect(self._autosave)
        self._alignworker.finished.connect(lambda: self.wPbar.hide())
        self._alignworker.finished.connect(self.onAlignmentEnd)
        self._alignworker.finished.connect(lambda: self.bAlign.setEnabled(True))

        if dm.is_aligned():
            self._alignworker.finished.connect(lambda: self.present_snr_results(indexes))
        self._alignworker.finished.connect(lambda: print(self._alignworker.dm))
        self._alignThread.start()  # Step 6: Start the thread


    @Slot()
    def autoscaleImages(self, src, out, opts):
        if self._working == True:
            self.warn('Another Process is Already Running')
            return
        logger.info('\n\nAutoscaling...\n')
        self.tell("Creating a new .images bundle...")
        self._scaleThread = QThread()  # Step 2: Create a QThread object
        scale_keys = opts['levels']
        scales = zip(scale_keys[::-1], [opts['size_xy'][s] for s in scale_keys[::-1]])
        if hasattr(self, '_scaleworker'):
            try:
                self._scaleworker.stop()
            except:
                print_exception()
            logger.info('\n\nSleeping for 2 seconds...\n')
            time.sleep(2)
        if hasattr(self, '_alignworker'):
            try:
                self._alignworker.stop()
            except:
                print_exception()
            logger.info('\n\nSleeping for 2 seconds...\n')
            time.sleep(2)

        self.shutdownNeuroglancer()

        self._scaleworker = ScaleWorker(src=src, out=out, scales=scales, opts=opts)
        self._scaleThread.started.connect(self._scaleworker.run)  # Step 5: Connect signals and slots
        self._scaleThread.finished.connect(self._scaleThread.deleteLater)
        self._scaleworker.finished.connect(self._scaleThread.quit)
        self._scaleworker.moveToThread(self._scaleThread)  # Step 4: Move worker to the thread
        self._scaleworker.finished.connect(self._scaleworker.deleteLater)
        self._scaleworker.finished.connect(lambda: self.wPbar.hide())
        self._scaleworker.finished.connect(self._refresh)
        self._scaleworker.finished.connect(lambda: self.pm.bCreateImages.setEnabled(True))
        def fn():
            self.saveUserPreferences()
            self.pm.refresh()
        self._scaleworker.finished.connect(fn)
        self._scaleworker.progress.connect(self.setPbar)
        self._scaleworker.initPbar.connect(self.resetPbar)
        self._scaleworker.hudMessage.connect(self.tell)
        self._scaleworker.hudWarning.connect(self.warn)

        self._scaleThread.start()  # Step 6: Start the thread


    def enableAllButtons(self):
        self.bAlign.setEnabled(True)
        self.bArrowDown.setEnabled(True)
        self.bArrowUp.setEnabled(True)
        self.cbSkip.setEnabled(True)
        self.cbBB.setEnabled(True)
        self.boxBias.setEnabled(True)
        self.startRangeInput.setEnabled(True)
        self.endRangeInput.setEnabled(True)
        

    
    def updateEnabledButtons(self) -> None:
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        self.wCpanel.hide()

        if self._isProjectTab():
            self.bRegenZarr.setEnabled(self.dm.is_aligned())
            self.wCpanel.show()
            try:
                self.pt.bSWIM.setEnabled(True)
                self.pt.bTransform.setEnabled(True)
            except:
                print_exception()
            self.cbSkip.setEnabled(True)
            self.boxScale.setEnabled(True)
            self.bLeftArrow.setEnabled(True)
            self.bRightArrow.setEnabled(True)
            self.sldrZpos.setEnabled(True)
            self.bPlayback.setEnabled(True)
            self.sbFPS.setEnabled(True)
            self.wToggleExclude.setEnabled(True)
            self.leJump.setEnabled(True)
            self.boxScale.setEnabled(True)
            self.cbBB.setChecked(self.dm.has_bb())

            # self.bAlign.setEnabled(self.dm.is_alignable() and self.dm['level_data'][self.dm.scale]['alignment_ready'])
            self.bAlign.setEnabled(True)
            # self.bAlign.setVisible(not self.dm.is_aligned())

            if len(self.dm.scales) == 1:
                self.bArrowUp.setEnabled(False)
                self.bArrowDown.setEnabled(False)
            else:
                cur_index = self.boxScale.currentIndex()
                if cur_index == 0:
                    self.bArrowDown.setEnabled(True)
                    self.bArrowUp.setEnabled(False)
                elif len(self.dm['images']['levels']) == cur_index + 1:
                    self.bArrowDown.setEnabled(False)
                    self.bArrowUp.setEnabled(True)
                else:
                    self.bArrowDown.setEnabled(True)
                    self.bArrowUp.setEnabled(True)
        else:
            self.bArrowUp.setEnabled(False)
            self.bArrowDown.setEnabled(False)
            self.bLeftArrow.setEnabled(False)
            self.bRightArrow.setEnabled(False)
            self.cbSkip.setEnabled(False)
            self.sldrZpos.setRange(0, 1)
            self.sldrZpos.setValue(0)
            self.sldrZpos.setEnabled(False)
            self.bPlayback.setEnabled(False)
            self.sbFPS.setEnabled(False)
            self.wToggleExclude.setEnabled(False)
            self.leJump.setEnabled(False)
            self.boxScale.setEnabled(False)



    def layer_left(self):
        if self._isProjectTab():
            if self.pt.wTabs.currentIndex() == 1:
                if self.dm['state']['tra_ref_toggle'] == 'ref':
                    self.pt.set_transforming()
            requested = self.dm.zpos - 1
            logger.info(f'requested: {requested}')
            if requested >= 0:
                self.dm.zpos = requested

    def layer_right(self):
        if self._isProjectTab():
            if self.pt.wTabs.currentIndex() == 1:
                if self.dm['state']['tra_ref_toggle'] == 'ref':
                    self.pt.set_transforming()
            requested = self.dm.zpos + 1
            if requested < len(self.dm):
                self.dm.zpos = requested


    def scale_down(self) -> None:
        logger.info('')
        if not self._working:
            if self.bArrowDown.isEnabled():
                self.boxScale.setCurrentIndex(self.boxScale.currentIndex() + 1)  # Changes Scale

    def scale_up(self) -> None:
        logger.info('')
        if not self._working:
            if self.bArrowUp.isEnabled():
                self.boxScale.setCurrentIndex(self.boxScale.currentIndex() - 1)  # Changes Scale
                if not self.dm.is_alignable():
                    self.warn('Lower scales have not been aligned yet')

    @Slot()
    def set_status(self, msg: str, *args, **kwargs) -> None:
        self.statusBar.showMessage(msg, *args, **kwargs)

    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')

    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')


    @staticmethod
    async def dataUpdateAsync(self):
        await self._dataUpdateWidgets()


    @Slot()
    def updateSlidrZpos(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'[{caller}]')
        if self._isProjectTab():
            cur = self.dm.zpos
            self.leJump.setText(str(cur))
            self.sldrZpos.setValue(cur)
            self.cbSkip.setChecked(not self.dm.skipped())
            self.bLeftArrow.setEnabled(cur > 0)
            self.bRightArrow.setEnabled(cur < len(self.dm) - 1)
            if self.dwSnr.isVisible():
                self.pt.dSnr_plot.updateLayerLinePos()
            if cfg.emViewer:
                cfg.emViewer.set_layer(self.dm.zpos)
            self.dataUpdateWidgets()
            if self.pt.wTabs.currentIndex() == 1:
                self.pt.gifPlayer.set()





    # def dataUpdateWidgets(self, ng_layer=None, silently=False) -> None:
    @Slot(name='dataUpdateWidgets-slot-name')
    def dataUpdateWidgets(self) -> None:
        '''Reads Project Data to Update MainWindow.'''
        # self.dataUpdateAsync(self)
        # await self._dataUpdateWidgets()

        # if DEV:
        #     caller = inspect.stack()[1].function
        #     logger.info(f'caller: {caller} sender: {self.sender()}')

        if self._working:
            logger.warning("Busy working! Not going to update the entire interface rn.")
            return

        logger.info('')

        # _needsAlignIndexes = self.dm.needsAlignIndexes()
        # _needsGenerateIndexes = self.dm.needsGenerateIndexes()
        # _hasUnsavedChangesIndexes = self.dm.hasUnsavedChangesIndexes()
        # n1 = len(_needsAlignIndexes)
        # n2 = len(_needsGenerateIndexes)
        # n3 = len(_hasUnsavedChangesIndexes)
        # s1 = (', '.join(map(str, _needsAlignIndexes)), '%d (total)' % n1)[n1 > 5]
        # s2 = (', '.join(map(str, _needsGenerateIndexes)), '%d (total)' % n2)[n2 > 5]
        # s3 = (', '.join(map(str, _hasUnsavedChangesIndexes)), '%d (total)' % n3)[n3 > 5]
        # if sum([n1, n2, n3]):
        #     msg = []
        #     if n1:
        #         msg.append(f"Alignment not in sync: {s1}")
        #     if n2:
        #         msg.append(f"Zarr not in sync: {s2}")
        #     if n3:
        #         msg.append(f"Unsaved changes: {s3}")
        #     self.statusBar.showMessage(" // ".join(msg))
        # else:
        #     self.statusBar.clearMessage()



        if self._isProjectTab():

            #CriticalMechanism
            if 'src.data_model.Signals' in str(self.sender()):
                # <src.data_model.Signals object at 0x13b8b3e20>
                # timerActive = self.uiUpdateTimer.isActive()
                # logger.critical(f"uiUpdateTimer active? {timerActive}")
                if self.uiUpdateTimer.isActive():
                    # logger.warning('Delaying UI Update [viewer_em.WorkerSignals]...')
                    return
                else:
                    self.uiUpdateTimer.start()
                    logger.info('Updating UI on timeout...')

            if self.dwThumbs.isVisible():
                self.pt.tn_tra.set_data(path=self.dm.path_thumb())
                self.pt.tn_tra_lab.setText(f'Transforming Section (Thumbnail)\n'
                                          f'[{self.dm.zpos}] {self.dm.name()}')

                if self.dm.skipped():
                    self.pt.tn_ref_lab.setText(f'--')
                    if not self.pt.tn_tra_overlay.isVisible():
                        self.pt.tn_tra_overlay.show()
                    self.pt.tn_ref.hide()
                    self.pt.tn_ref_lab.hide()
                else:
                    self.pt.tn_ref_lab.setText(f'Reference Section (Thumbnail)\n'
                          f'[{self.dm.zpos}] {self.dm.name_ref()}')
                    if self.pt.tn_tra_overlay.isVisible():
                        self.pt.tn_tra_overlay.hide()
                    self.pt.tn_ref.set_data(path=self.dm.path_thumb_ref())
                    self.pt.tn_ref.show()
                    self.pt.tn_ref_lab.show()


            if self.dwNotes.isVisible():
                self.updateNotes()


            self.updateDwMatches()

            if self.pt.wTabs.currentIndex() == 0:
                self.pt._overlayLab.setVisible(self.dm.skipped()) #Todo find/fix
                if hasattr(cfg, 'emViewer'):
                    try:
                        if floor(cfg.emViewer.state.position[0]) != self.dm.zpos:
                            cfg.emViewer.set_layer(self.dm.zpos)
                    except:
                        print_exception()
                else:
                    logger.warning("no attribute: 'emViewer'!")

            elif self.pt.wTabs.currentIndex() == 1:
                self.pt.dataUpdateMA()

                self.pt.editorViewer.set_layer()

                self.pt.lab_filename.setText(f"[{self.dm.zpos}] Name: {self.dm.name()} - {self.dm.level_pretty()}")
                self.pt.cl_tra.setText(f'[{self.dm.zpos}] {self.dm.name()} (Transforming)')
                if self.dm.skipped():
                    self.pt.cl_tra.setText(f'[{self.dm.zpos}] {self.dm.name()} (Transforming)')
                    self.pt.cl_ref.setText(f'--')
                else:
                    try:
                        self.pt.cl_ref.setText(f'[{self.dm.get_ref_index()}] {self.dm.name_ref()} (Reference)')
                    except:
                        self.pt.cl_ref.setText(f'Null (Reference)')


            elif self.pt.wTabs.currentIndex() == 2:
                self.pt.snr_plot.updateLayerLinePos()

            elif self.pt.wTabs.currentIndex() == 4:
                self.pt.treeview_model.jumpToLayer()
            self.setFocus()



            #Todo come back to how to make this work without it getting stuck in a loop
            # if self.pt.wTabs.currentIndex() == 2:
            #     self.pt.project_table.data.selectRow(cur)


    def updateNotes(self):
        # caller = inspect.stack()[1].function
        # logger.info('')
        if self.notes.isVisible():
            self.notes.clear()
            if self._isProjectTab():
                self.notes.setPlaceholderText('Enter notes about %s here...'
                                              % self.dm.base_image_name(s=self.dm.level, l=self.dm.zpos))
                if self.dm.notes(s=self.dm.level, l=self.dm.zpos):
                    self.notes.setPlainText(self.dm.notes(s=self.dm.level, l=self.dm.zpos))
            else:
                self.notes.clear()
                self.notes.setPlaceholderText('Notes are stored automatically...')
            self.notes.update()

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
        if s == None: s = self.dm.level
        self.history_label = QLabel('<b>Saved Alignments (Scale %d)</b>' % get_scale_val(s))
        self._hstry_listWidget.clear()
        dir = os.path.join(self.dm.data_location, s, 'history')
        try:
            self._hstry_listWidget.addItems(os.listdir(dir))
        except:
            logger.warning(f"History Directory '{dir}' Not Found")

    def view_historical_alignment(self):
        logger.info('view_historical_alignment:')
        name = self._hstry_listWidget.currentItem().text()
        if self.pt:
            if name:
                path = os.path.join(self.dm.data_location, self.dm.level, 'history', name)
                with open(path, 'r') as f:
                    project = json.load(f)
                self.projecthistory_model.load(project)
                self.globTabs.addTab(self.historyview_widget, self.dm.level_pretty())
        self._setLastTab()

    def rename_historical_alignment(self):
        new_name, ok = QInputDialog.getText(self, 'Rename', 'New Name:')
        if not ok: return
        old_name = self._hstry_listWidget.currentItem().text()
        dir = os.path.join(self.dm.data_location, self.dm.level, 'history')
        old_path = os.path.join(dir, old_name)
        new_path = os.path.join(dir, new_name)
        try:
            os.rename(old_path, new_path)
        except:
            logger.warning('There was a problem renaming the file')
        # self.updateHistoryListWidget()

    def remove_historical_alignment(self):
        logger.info('Loading History File...')
        name = self._hstry_listWidget.currentItem().text()
        if name is None: return
        path = os.path.join(self.dm.data_location, self.dm.level, 'history', name)
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
        path = os.path.join(self.dm.data_location, self.dm.level, 'history', item.text())
        with open(path, 'r') as f:
            scale = json.load(f)

    def ng_layer(self):
        '''The idea behind this was to cache the current layer. Not Being Used Currently'''
        try:
            index = cfg.emViewer.cur_index
            assert isinstance(index, int)
            return index
        except:
            print_exception()

    def reload_zpos_slider_and_lineedit(self):
        '''Requires Neuroglancer '''
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if self._isProjectTab() or self._isZarrTab():
                logger.info('')
                self.leJump.setValidator(QIntValidator(0, len(self.dm) - 1))
                self.sldrZpos.setRange(0, len(self.dm) - 1)
                self.sldrZpos.setValue(self.dm.zpos)
                self.updateSlidrZpos()
                self.update()
            else:
                self.leJump.clear()
                self.sldrZpos.setValue(0)
                self.sldrZpos.setRange(0, 0)
        except:
            print_exception()

    def printActiveThreads(self):
        threads = '\n'.join([thread.name for thread in threading.enumerate()])
        logger.info(f'# Active Threads : {threading.active_count()}')
        logger.info(f'Current Thread   : {threading.current_thread()}')
        logger.info(f'All Threads      : \n{threads}')
        self.tell(f'# Active Threads : {threading.active_count()}')
        self.tell(f'Current Thread   : {threading.current_thread()}')
        self.tell(f'All Threads      : \n{threads}')


    @Slot()
    def jump_to_index(self, requested) -> None:
        '''Connected to leJump. Calls jump_to_slider directly.'''
        if self._isProjectTab():
            logger.info('')
            self.dm.zpos = requested


    @Slot()
    def jump_to_layer(self) -> None:
        '''Connected to leJump. Calls jump_to_slider directly.'''
        if self._isProjectTab():
            logger.info('')
            requested = int(self.leJump.text())
            self.dm.zpos = requested


    def jump_to_slider(self):
        if self._isProjectTab():
            if inspect.stack()[1].function == 'main':
                logger.info('')
                self.dm.zpos = self.sldrZpos.value()

    @Slot()
    def reloadComboScale(self) -> None:
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        self.boxScale.clear()
        if self._isProjectTab():
            if hasattr(cfg, 'data'):
                # logger.info('Reloading Scale Combobox (caller: %level)' % caller)
                self._scales_combobox_switch = 0
                # lvl = self.dm.lvl(s=self.dm.level)
                lst = []
                for level in self.dm.levels:
                    lvl = self.dm.lvl(s=level)
                    siz = self.dm.image_size(s=level)
                    lst.append('%d / %d x %dpx' % (lvl, siz[0], siz[1]))

                self.boxScale.addItems(lst)
                self.boxScale.setCurrentIndex(self.dm.scales.index(self.dm.level))
                self._scales_combobox_switch = 1

    def onScaleChange(self) -> None:
        caller = inspect.stack()[1].function
        if self._scales_combobox_switch == 0:
            # logger.warning(f"[{caller}] level change blocked by _scales_combobox_switch switch")
            return
        if not self._working:
            if caller in ('main', 'scale_down', 'scale_up'):
                if self._isProjectTab():
                    # logger.info(f'[{caller}]')
                    requested = self.dm.scales[self.boxScale.currentIndex()]
                    self.dm.scale = requested
                    if self.dm.is_aligned():
                        setData('state,neuroglancer,layout', '4panel')
                    else:
                        setData('state,neuroglancer,layout', 'xy')

                    # self.pt.cmbViewerScale.setCurrentIndex(self.dm.levels.index(self.dm.level))
                    if self.pt.wTabs.currentIndex() == 3:
                        self.pt.project_table.initTableData()
                    # self.pt.project_table.veil()
                    self.alignAllAction.setText(f"Align + Generate All: Level {self.dm.scale}")
                    self.updateEnabledButtons()
                    self.dataUpdateWidgets()
                    self.pt.dataUpdateMA()
                    self.pt.refreshTab()
                    if self.dwSnr.isVisible():
                        self.pt.dSnr_plot.initSnrPlot()
            else:
                logger.warning(f"[{caller}] scale change disallowed")


    def export_afms(self):
        if self.pt:
            if self.dm.is_aligned():
                file = export_affines_dialog()
                if file == None:
                    self.warn('No Filename - Canceling Export')
                    return
                afm_lst = self.dm.afm_list()
                with open(file, 'w') as f:
                    for sublist in afm_lst:
                        for item in sublist:
                            f.write(str(item) + ',')
                        f.write('\n')
                self.tell('Exported: %s' % file)
                self.tell(f"AFMs exported successfully to '{file}'")
            else:
                self.warn('Current level is not aligned. Nothing to export.')
        else:
            self.warn('No open projects. Nothing to export.')

    def export_cafms(self):
        file = export_affines_dialog()
        if file == None:
            logger.warning('No Filename - Canceling Export')
            return
        logger.info('Export Filename: %s' % file)
        cafm_lst = self.dm.cafm_list()
        with open(file, 'w') as f:
            for sublist in cafm_lst:
                for item in sublist:
                    f.write(str(item) + ',')
                f.write('\n')
        self.tell('Exported: %s' % file)
        self.tell('Cumulative AFMs exported successfully.')

    def show_warning(self, title, text):
        QMessageBox.warning(None, title, text)

    def open_project_new(self):

        for i in range(self.globTabs.count()):
            if self.globTabs.widget(i).__class__.__name__ == 'OpenProject':
                self.globTabs.setCurrentIndex(i)
                return
        self.globTabs.addTab(self.pm, 'Alignment Manager')

    def detachNeuroglancer(self):
        logger.info('')
        if self._isProjectTab() or self._isZarrTab():
            try:
                self.detachedNg = QuickWebPage(url=cfg.emViewer.url())
            except:
                logger.info('Cannot open detached neuroglancer view')


    def onStartProject(self, dm, switch_to=False):
        '''Functions that only need to be run once per project
                Do not automatically save, there is nothing to save yet'''
        logger.info('')
        self.setUpdatesEnabled(False)
        self.dm = cfg.data = dm
        cfg.preferences['last_alignment_opened'] = dm.data_location
        # dm.scale = dm.coarsest_scale_key() #1015-
        name,_ = os.path.splitext(os.path.basename(dm.data_location))
        setData('state,neuroglancer,layout', ('xy','4panel')[self.dm.is_aligned()])
        self.pt = self.pt = cfg.pt = ProjectTab(self, path=dm.data_location, datamodel=dm)
        cfg.dataById[id(self.pt)] = dm
        self.addGlobTab(self.pt, name, switch_to=switch_to)
        logger.info(f'\n\nLoading project:\n%s\n' % os.path.basename(self.dm.data_location))
        self.tell("Loading Project '%s'..." % self.dm.data_location)
        self.alignAllAction.setText(f"Align + Generate All: Level {self.dm.scale}")
        # if switch_to:
        #     if self.dm.is_aligned():
                # self.setdw_snr(True)
                # self.setdw_matches(True)
            # self.setdw_thumbs(True)
            # self.setdw_matches(False)
        self.hud.done()
        self.setUpdatesEnabled(True)
        self.setFocus()

    def saveUserPreferences(self, silent=False):
        if not silent:
            logger.info('Saving User Preferences...')
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        # if self._isProjectTab():
        #     self.preferences.setValue("hsplitter_tn_ngSizes", self.pt.splitter_ngPlusSideControls.saveState())
        userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
        if not os.path.exists(userpreferencespath):
            open(userpreferencespath, 'a').close()
        try:
            f = open(userpreferencespath, 'w')
            json.dump(cfg.preferences, f, indent=2)
            f.close()
        except:
            self.warn(f'Unable to save current user preferences. Using defaults instead.')

    def resetUserPreferences(self):
        logger.info('')
        userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
        if os.path.exists(userpreferencespath):
            os.remove(userpreferencespath)
        cfg.preferences = {}
        update_preferences_model()
        self.saveUserPreferences()

    def rename_project(self):
        new_name, ok = QInputDialog.getText(self, 'Input Dialog', 'Project Name:')
        if ok:
            dest_orig = Path(self.dm.data_location)
            print(dest_orig)
            parent = dest_orig.parents[0]
            new_dest = os.path.join(parent, new_name)
            new_dest_no_ext = os.path.splitext(new_dest)[0]
            os.rename(dest_orig, new_dest_no_ext)
            self.dm.data_location = new_dest
            # if not new_dest.endswith('.json'):  # 0818-
            #     new_dest += ".json"
            # logger.info('new_dest = %level' % new_dest)
            self._autosave()

    def save(self):
        #Todo move this to DataModel or project_tab
        caller = inspect.stack()[1].function
        logger.info(f'/*======== Saving Automatically [{caller}] ========*/')
        if self._isProjectTab():
            try:
                self._saveProjectToFile()
                # self.tell('Project Saved!')
                self._unsaved_changes = False
            except:
                self.warn('Failed To Save')
                print_exception()

            else:
                self.hud.done()

    def _autosave(self, silently=False):

        caller = inspect.stack()[1].function
        if hasattr(cfg,'data'):
            if cfg.AUTOSAVE:
                logger.info(f'/*---- Autosaving [{caller}] ----*/')
                try:
                    self._saveProjectToFile(silently=silently)
                except:
                    self._unsaved_changes = True
                    print_exception()

    def _saveProjectToFile(self, saveas=None, silently=False):
        #Todo move this to DataModel or project_tab
        if hasattr(self, 'dm'):
            caller = inspect.stack()[1].function
            try:
                if saveas is not None:
                    self.dm.data_location = saveas
                # data_cp = copy.deepcopy(self.dm._data) #0828-

                # data_cp.make_paths_relative(start=self.dm.images_location)
                # data_cp_json = data_cp.to_dict()
                name,_ = os.path.splitext(os.path.basename(self.dm.data_location))
                path = os.path.join(self.dm.data_location, name + '.swiftir')
                if not silently:
                    logger.info(f'Saving:\n{path}')

                logger.critical(f"[{caller}] Writing {path} to file...")
                with open(path, 'w') as f:
                    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                    # f.write(jde.encode(data_cp)) #0828-
                    f.write(jde.encode(self.dm._data))

                # if is_tacc():
                #     node = platform.node()
                #     user = getpass.getuser()
                #     tstamp = datetime.datetime.now().strftime('%Y%m%d')
                #     fn = f"pf_{tstamp}_{node}_{user}_" + os.path.basename(name)
                #     images_location = "/work/08507/joely/ls6/log_db"
                #     of = os.path.join(images_location, fn)
                #     with open(of, 'w') as f:
                #         f.write(jde.encode(data_cp))

                self.saveUserPreferences()
                logger.info('Pickling alignment data...')
                self.dm.ht.pickle()
                if not silently:
                    self.tell('Alignment Saved!')

            except:
                print_exception()
            else:
                self._unsaved_changes = False
            finally:
                logger.info("<<<<")

    def _callbk_unsavedChanges(self):
        if self._isProjectTab():
            # logger.info('')
            caller = inspect.stack()[1].function
            if caller == 'main':
                # self.tell('You have unsaved changes.')
                # logger.critical("caller: " + inspect.stack()[1].function)
                self._unsaved_changes = True
                name = os.path.basename(self.dm.data_location)
                self.globTabs.setTabText(self.globTabs.currentIndex(), name + '.swiftir' + ' *')


    @Slot()
    def closeEvent(self, event):
        logger.info("closeEvent called by %s..." % inspect.stack()[1].function)
        self.shutdownInstructions()

        self.exit_app()
        # QMainWindow.closeEvent(self, event)


    def cancelExitProcedure(self):
        logger.info('')
        self._exiting = 0
        self.exit_dlg.hide()

    def saveExitProcedure(self):
        logger.info('')
        self.save()
        self.shutdownInstructions()

    def exitProcedure(self):
        logger.info('')
        self.shutdownInstructions()

    def exitResponse(self, response):
        logger.info(f'User Response: {response}')

    def restart_app(self):
        self.tell('Attempting to restart AlignEM...')
        path = os.path.join(os.getenv('WORK'), 'swift-ir', 'tacc_bootstrap')
        logger.info(f'Attempting to restart AlignEM with {path}...')
        # run_command('source', arg_list=[path])
        # run_command('/usr/src/ofa_kernel-5.6/source', arg_list=[path])
        subprocess.run(["source", path])
        self.shutdownInstructions()


    def exit_app(self):

        if self._exiting:
            self._exiting = 0
            if self.exit_dlg.isVisible():
                self.globTabsAndCpanel.children()[-1].hide()
            return
        self._exiting = 1

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.exit_dlg = ExitAppDialog(unsaved_changes=self._unsaved_changes)
        self.exit_dlg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.exit_dlg.signals.cancelExit.connect(self.cancelExitProcedure)
        self.exit_dlg.signals.saveExit.connect(self.saveExitProcedure)
        self.exit_dlg.signals.exit.connect(self.exitProcedure)
        # self.exit_dlg.signals.response.connect(self.exitResponse)
        self.exit_dlg.signals.response.connect(lambda val: self.exitResponse(val))
        self.exit_dlg.setFixedHeight(22)
        p = self.exit_dlg.palette()
        # p.setColor(self.exit_dlg.backgroundRole(), QColor('#222222'))
        p.setColor(self.exit_dlg.backgroundRole(), QColor('#222222'))
        self.exit_dlg.setPalette(p)
        self.globTabsAndCpanel.layout.addWidget(self.exit_dlg)

    def shutdownInstructions(self):
        logger.info('Performing Shutdown Instructions...')

        self._autosave(silently=True)
        self._timerWorker._running = False

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        if ng.server.is_server_running():
            try:
                self.tell('Stopping Neuroglancer Client...')
                self.shutdownNeuroglancer()
            except:
                self.warn('Having trouble shutting down neuroglancer')

        # if cfg.USE_EXTRA_THREADING:
        #     try:
        #         self.tell('Waiting For Threadpool...')
        #         result = QThreadPool.globalInstance().waitForDone(msecs=500)
        #     except:
        #         print_exception()
        #         self.warn(f'Having trouble shutting down threadpool')

        # if cfg.DEV_MODE:
        self.tell('Shutting Down Python Console Kernel...')
        try:

            self.pythonConsole.pyconsole.kernel_client.stop_channels()
            self.pythonConsole.pyconsole.kernel_manager.shutdown_kernel()
        except:
            print_exception()
            self.warn('Having trouble shutting down Python console kernel')

        self.tell('Graceful, Goodbye!')
        # time.sleep(1)
        QApplication.quit()


    def html_resource(self, resource='features.html', title='Features', ID=''):

        html_f = os.path.join(self.get_application_root(), 'src/resources/html', resource)
        with open(html_f, 'r') as f:
            html = f.read()

        # webengine = QWebEngineView()
        webengine = WebEngine(ID=ID)
        webengine.setHtml(html, baseUrl=QUrl.fromLocalFile(os.getcwd() + os.path.sep))
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.addGlobTab(webengine, title)

    def url_resource(self, url, title):
        webengine = QWebEngineView()
        webengine.setUrl(QUrl(url))
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.addGlobTab(webengine, title)

    def remote_view(self):
        self.tell('Opening Neuroglancer Remote Viewer...')
        webbrowser = WebBrowser()
        webbrowser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.addGlobTab(webbrowser, 'Neuroglancer')
        self.setCpanelVisibility(False)

    def open_url(self, text: str) -> None:
        self.browser_web.setUrl(QUrl(text))
        self.main_stack_widget.setCurrentIndex(1)

    # def view_swiftir_examples(self):
    #     self.browser_web.setUrl(
    #         QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/examples/README.md'))
    #     self.main_stack_widget.setCurrentIndex(1)

    def view_zarr_drawing(self):
        path = 'https://github.com/zarr-developers/zarr-specs/blob/main/docs/v3/core/terminology-read.excalidraw.png'

    def view_swiftir_commands(self):
        self.browser_web.setUrl(
            QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/commands/README.md'))
        self.main_stack_widget.setCurrentIndex(1)

    def browser_3dem_community(self):
        self.browser_web.setUrl(QUrl(
            'https://3dem.org/workbench/data/tapis/community/data-3dem-community/'))


    def startStopTimer(self):
        logger.info('')
        if self.timerPlayback.isActive():
            self.timerPlayback.stop()
            self.bPlayback.setIcon(qta.icon('fa.play'))
        elif self._isProjectTab() or self._isZarrTab():
            self.timerPlayback.start()
            self.bPlayback.setIcon(qta.icon('fa.pause'))

    def stopPlaybackTimer(self):
        if self.timerPlayback.isActive():
            logger.warning('Timer was active!')
            self.timerPlayback.stop()
            self.bPlayback.setIcon(qta.icon('fa.play'))
            # self.bPlayback.setIcon(QIcon('src/resources/play-bBlink.png'))

    def incrementZoomOut(self):
        if ('QTextEdit' or 'QLineEdit') in str(self.focusWidget()):
            return

        # logger.info('')
        if self._isProjectTab():
            cur = self.pt.wTabs.currentIndex()
            if cur == 1:
                new_cs_scale = cfg.editorViewer.zoom() * 1.1
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.editorViewer.set_zoom(new_cs_scale)
                self.pt.zoomSlider.setValue(1 / new_cs_scale)
            elif cur == 0:
                new_cs_scale = cfg.emViewer.zoom() * 1.1
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.emViewer.set_zoom(new_cs_scale)
                self.pt.zoomSlider.setValue(1 / new_cs_scale)

    def incrementZoomIn(self):
        # logger.info('')
        if ('QTextEdit' or 'QLineEdit') in str(self.focusWidget()):
            return

        if self._isProjectTab():
            cur = self.pt.wTabs.currentIndex()
            if cur == 1:
                new_cs_scale = cfg.editorViewer.zoom() * 0.9
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.editorViewer.set_zoom(new_cs_scale)
                self.pt.zoomSlider.setValue(1 / new_cs_scale)
            elif cur == 0:
                new_cs_scale = cfg.emViewer.zoom() * 0.9
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.emViewer.set_zoom(new_cs_scale)
                self.pt.zoomSlider.setValue(1 / new_cs_scale)

    # def initShortcuts(self):
    #     logger.info('')
    #     events = (
    #         # (QKeySequence.MoveToPreviousChar, self.layer_left),
    #         # (QKeySequence.MoveToNextChar, self.layer_right),
    #         # (QKeySequence.MoveToPreviousLine, self.incrementZoomIn),
    #         # (QKeySequence.MoveToNextLine, self.incrementZoomOut),
    #         # (QKeySequence("Ctrl+M"), self.enterExitManAlignMode),
    #         # (QKeySequence.MoveToPreviousChar, self.scale_down),
    #         # (QKeySequence.MoveToNextChar, self.scale_up),
    #         # (Qt.Key_K, self._callbk_skipChanged),
    #         # (Qt.Key_N, self._callbk_showHideNotes)
    #     )
    #     for event, action in events:
    #         QShortcut(event, self, action)

    def display_shortcuts(self):
        for action in self.findChildren(QAction) :
            print(type(action), action.toolTip(), [x.toString() for x in action.shortcuts()])

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
        logger.info('Opening WebGL Test...')
        browser = WebBrowser(self)
        browser.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.addGlobTab(browser, 'WebGL Test')
        self.setCpanelVisibility(False)

    def tab_google(self):
        logger.info('Opening Google tab...')
        browser = WebBrowser(self)
        browser.setObjectName('web_browser')
        browser.setUrl(QUrl('https://www.google.com'))
        self.addGlobTab(browser, 'Google')

    def tab_report_bug(self):
        logger.info('Opening GitHub issue tracker tab...')
        cfg.bugreport = browser = WebBrowser(self)
        browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/issues'))
        self.addGlobTab(browser, 'Issue Tracker')

    def tab_3dem_community_data(self):
        path = 'https://3dem.org/workbench/data/tapis/community/data-3dem-community/'
        browser = WebBrowser(self)
        browser.setUrl(QUrl(path))
        self.addGlobTab(browser, 'Community Data (TACC)')

    def tab_workbench(self):
        logger.info('Opening 3DEM Workbench tab...')
        browser = WebBrowser(self)
        browser.setUrl(QUrl('https://3dem.org/workbench/'))
        self.addGlobTab(browser, '3DEM Workbench')

    def gpu_config(self):
        logger.info('Opening GPU Config...')
        browser = WebBrowser()
        browser.setUrl(QUrl('chrome://gpu'))
        self.addGlobTab(browser, 'GPU Configuration')


    def chromium_debug(self):
        logger.info('Opening Chromium Debugger...')
        browser = WebBrowser()
        browser.setUrl(QUrl('http://127.0.0.1:9000'))
        self.addGlobTab(browser, 'Debug Chromium')

    def get_ng_state(self):
        if self.pt:
            try:
                if ng.is_server_running():
                    txt = json.dumps(cfg.emViewer.state.to_json(), indent=2)
                    return f"Viewer State:\n{txt}"
                else:
                    return f"Neuroglancer Is Not Running."
            except:
                return f"N/A"
                print_exception()

    def get_ng_state_raw(self):
        if self.pt:
            try:
                if ng.is_server_running():
                    return f"Raw Viewer State:\n{cfg.emViewer.config_state.raw_state}"
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
        if self.pt:
            if not ng.is_server_running():
                logger.warning('Neuroglancer is not running')
                return
            v = cfg.emViewer
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

    def _callbk_skipChanged(self, state: int):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        #Todo refactor
        caller = inspect.stack()[1].function
        # if caller == 'main':
        if self._isProjectTab():
            if caller != 'updateSlidrZpos':
                logger.info(f'[{caller}]')
                skip_state = not self.cbSkip.isChecked()
                layer = self.dm.zpos
                # for s in self.dm.finer_scales():
                if layer < len(self.dm):
                    self.dm.set_skip(skip_state, s=self.dm.level, l=layer)
                else:
                    logger.warning(f'Request layer is out of range ({layer}) - Returning')
                    return

                if skip_state:
                    self.tell("Exclude: %s" % self.dm.name())
                else:
                    self.tell("Include: %s" % self.dm.name())

                self.dm.linkReference(level=self.dm.level)

                # if getData('state,blink'):

                SetStackCafm( #Critical0802+
                    self.dm,
                    scale=self.dm.scale,
                    poly_order=self.dm.poly_order
                )

                self.pt.project_table.set_row_data(row=layer)

                #Todo Fix this. This is just a kluge to make the data reflect correct data for now.
                for x in range(0,5):
                    if layer + x in range(0,len(self.dm)):
                        self.pt.project_table.set_row_data(row=layer + x)

                if self.pt.wTabs.currentIndex() == 4:
                    self.pt.snr_plot.initSnrPlot()

                if self.dwSnr.isVisible():
                    self.pt.dSnr_plot.initSnrPlot()

                self.dataUpdateWidgets()


    def skip_change_shortcut(self):
        logger.info('')
        if self.dm:
            self.cbSkip.setChecked(not self.cbSkip.isChecked())


    def print_all_matchpoints(self):
        if self.pt:
            self.dm.print_all_manpoints()

    def show_all_matchpoints(self):
        if self.pt:
            no_mps = True
            for i, l in enumerate(self.dm.stack()):
                r = l['images']['ref']['metadata']['man_points']
                b = l['images']['base']['metadata']['man_points']
                if r != []:
                    no_mps = False
                    self.tell(f'Layer: {i}, Ref, Match Points: {str(r)}')
                if b != []:
                    no_mps = False
                    self.tell(f'Layer: {i}, Base, Match Points: {str(b)}')
            if no_mps:
                self.tell('This project has no match points.')

    def show_run_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.tell('\n\nWorking Directory     : %s\n'
                  'Running In (__file__) : %s' % (os.getcwd(), os.path.dirname(os.path.realpath(__file__))))

    def show_module_search_path(self) -> None:
        '''Prints the current working directory (os.getcwd), the 'running in' path, and sys.path.'''
        self.tell('\n\n' + '\n'.join(sys.path))

    def show_snr_list(self) -> None:
        if self.pt:
            s = self.dm.curScale_val()
            lst = ' | '.join(map(str, self.dm.snr_list()))
            self.tell('\n\nSNR List for Scale %d:\n%s\n' % (s, lst.split(' | ')))

    # def show_zarr_info(self) -> None:
    #     if self.pt:
    #         z = zarr.open(os.path.join(self.dm.images_location, 'img_aligned.zarr'))
    #         self.tell('\n' + str(z.tree()) + '\n' + str(z.info))
    #
    # def show_zarr_info_aligned(self) -> None:
    #     if self.pt:
    #         z = zarr.open(os.path.join(self.dm.images_location, 'img_aligned.zarr'))
    #         self.tell('\n' + str(z.info) + '\n' + str(z.tree()))
    #
    # def show_zarr_info_source(self) -> None:
    #     if self.pt:
    #         z = zarr.open(os.path.join(self.dm.images_location, 'img_src.zarr'))
    #         self.tell('\n' + str(z.info) + '\n' + str(z.tree()))

    def show_hide_developer_console(self):
        if self.dwPython.isHidden():
            self.dwPython.show()
        else:
            self.dwPython.hide()

    def set_opacity(self, obj, val):
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(val)  # 0 to 1 -> fade effect
        obj.setGraphicsEffect(op)
        obj.setAutoFillBackground(True)

    # def set_shader_none(self):
    #     cfg.SHADER = '''void main () {
    #       emitGrayscale(toNormalized(getDataValue()));
    #     }'''
    #     self.pt.initNeuroglancer()

    def set_shader_default(self):
        self.dm['rendering']['shader'] = src.shaders.shader_default_
        self.pt.initNeuroglancer()

    def set_shader_colormapJet(self):
        self.dm['rendering']['shader'] = src.shaders.colormapJet
        self.pt.initNeuroglancer()

    def set_shader_test1(self):
        self.dm['rendering']['shader'] = src.shaders.shader_test1
        self.pt.initNeuroglancer()

    def set_shader_test2(self):
        self.dm['rendering']['shader'] = src.shaders.shader_test2
        self.pt.initNeuroglancer()

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



    def initAdvancedMenu(self):

        self.le_tacc_num_cores = QLineEdit()
        self.le_tacc_num_cores.setFixedHeight(18)
        self.le_tacc_num_cores.setFixedWidth(30)
        self.le_tacc_num_cores.setValidator(QIntValidator(1,128))
        def update_tacc_max_cores():
            logger.info('')
            n = int(self.le_tacc_num_cores.text())
            cfg.TACC_MAX_CPUS = int(n)
            self.tell(f"Maximum # of cores is now set to: {n}")
        self.le_tacc_num_cores.setText(str(cfg.TACC_MAX_CPUS))
        self.le_tacc_num_cores.textEdited.connect(update_tacc_max_cores)
        self.le_tacc_num_cores.returnPressed.connect(update_tacc_max_cores)

        self.le_max_downsampling = QLineEdit()
        self.le_max_downsampling.setFixedHeight(18)
        self.le_max_downsampling.setFixedWidth(30)
        self.le_max_downsampling.setValidator(QIntValidator())
        def update_le_max_downsampling():
            logger.info('')
            n = int(self.le_max_downsampling.text())
            cfg.max_downsampling = int(n)
        self.le_max_downsampling.setText(str(cfg.max_downsampling))
        self.le_max_downsampling.textEdited.connect(update_le_max_downsampling)
        self.le_max_downsampling.returnPressed.connect(update_le_max_downsampling)

        self.le_max_downsampled_size = QLineEdit()
        self.le_max_downsampled_size.setFixedHeight(18)
        self.le_max_downsampled_size.setFixedWidth(30)
        self.le_max_downsampled_size.setValidator(QIntValidator())
        def update_le_max_downsampled_size():
            logger.info('')
            n = int(self.le_max_downsampled_size.text())
            cfg.max_downsampled_size = int(n)
        self.le_max_downsampled_size.setText(str(cfg.max_downsampled_size))
        self.le_max_downsampled_size.textEdited.connect(update_le_max_downsampled_size)
        self.le_max_downsampled_size.returnPressed.connect(update_le_max_downsampled_size)

        # self.le_max_downsampling_scales = QLineEdit()
        # self.le_max_downsampling_scales.setFixedHeight(18)
        # self.le_max_downsampling_scales.setFixedWidth(30)
        # self.le_max_downsampling_scales.setValidator(QIntValidator())
        # def update_le_max_downsampling_scales():
        #     logger.info('')
        #     n = int(self.le_max_downsampling_scales.text())
        #     cfg.max_downsampling_scales = int(n)
        # self.le_max_downsampling_scales.setText(str(cfg.max_downsampling_scales))
        # self.le_max_downsampling_scales.textEdited.connect(update_le_max_downsampling_scales)
        # self.le_max_downsampling_scales.returnPressed.connect(update_le_max_downsampling_scales)

        self.le_tacc_num_scale1_cores = QLineEdit()
        self.le_tacc_num_scale1_cores.setFixedSize(QSize(30,18))
        self.le_tacc_num_scale1_cores.setValidator(QIntValidator(1,128))
        def update_tacc_max_scale1_cores():
            logger.info('')
            n = int(self.le_tacc_num_scale1_cores.text())
            cfg.SCALE_1_CORES_LIMIT = int(n)
            self.tell(f"Maximum # of cores is now set to: {n}")
        self.le_tacc_num_scale1_cores.setText(str(cfg.SCALE_1_CORES_LIMIT))
        self.le_tacc_num_scale1_cores.textEdited.connect(update_tacc_max_scale1_cores)
        self.le_tacc_num_scale1_cores.returnPressed.connect(update_tacc_max_scale1_cores)

        self.le_qtwebengine_raster_threads = QLineEdit()
        self.le_qtwebengine_raster_threads.setFixedHeight(18)
        self.le_qtwebengine_raster_threads.setFixedWidth(30)
        self.le_qtwebengine_raster_threads.setValidator(QIntValidator())
        def update_raster_threads():
            logger.info('')
            n = int(self.le_qtwebengine_raster_threads.text())
            cfg.QTWEBENGINE_RASTER_THREADS = n
            self.tell(f"# QtWebengine raster threads is now set to: {n}")
        self.le_qtwebengine_raster_threads.setText(str(cfg.QTWEBENGINE_RASTER_THREADS))
        self.le_qtwebengine_raster_threads.textEdited.connect(update_raster_threads)
        self.le_qtwebengine_raster_threads.returnPressed.connect(update_raster_threads)

        self.cb_recipe_logging = QCheckBox()
        self.cb_recipe_logging.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_recipe_logging():
            logger.info('')
            b = self.cb_recipe_logging.isChecked()
            cfg.LOG_RECIPE_TO_FILE = int(b)
            self.tell(f"Recipe logging is now set to: {b}")
        self.cb_recipe_logging.setChecked(cfg.LOG_RECIPE_TO_FILE)
        self.cb_recipe_logging.toggled.connect(update_recipe_logging)

        self.cb_verbose_swim = QCheckBox()
        self.cb_verbose_swim.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_swim_verbosity():
            logger.info('')
            b = self.cb_verbose_swim.isChecked()
            cfg.VERBOSE_SWIM = int(b)
            self.tell(f"Recipe logging is now set to: {b}")
        self.cb_verbose_swim.setChecked(cfg.VERBOSE_SWIM)
        self.cb_verbose_swim.toggled.connect(update_swim_verbosity)

        self.cb_dev_mode = QCheckBox()
        self.cb_dev_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_dev_mode():
            logger.info('')
            b = self.cb_dev_mode.isChecked()
            cfg.DEV_MODE = int(b)
            self.tell(f"Dev mode is now set to: {b}")
        self.cb_dev_mode.setChecked(cfg.DEV_MODE)
        self.cb_dev_mode.toggled.connect(update_dev_mode)

        self.cb_use_pool = QCheckBox()
        self.cb_use_pool.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def update_mp_mode():
            logger.info('')
            b = self.cb_use_pool.isChecked()
            cfg.USE_POOL_FOR_SWIM = int(b)
            self.tell(f"Multiprocessing mode is now set to: "
                                 f"{('task queue', 'pool')[b]}")
        self.cb_use_pool.setChecked(cfg.USE_POOL_FOR_SWIM)
        self.cb_use_pool.toggled.connect(update_mp_mode)

        self.le_thumb_size = QLineEdit()
        self.le_thumb_size.setFixedSize(QSize(30, 18))
        self.le_thumb_size.setValidator(QIntValidator(1, 1024))
        def update_thumb_size():
            logger.info('')
            n = int(self.le_thumb_size.text())
            cfg.TARGET_THUMBNAIL_SIZE = n
            self.tell(f"Target thumbnail size is now set to: {n}")
        self.le_thumb_size.setText(str(cfg.TARGET_THUMBNAIL_SIZE))
        self.le_thumb_size.textEdited.connect(update_thumb_size)
        self.le_thumb_size.returnPressed.connect(update_thumb_size)

        self.w_tacc = QWidget()
        self.w_tacc.setContentsMargins(2,2,2,2)
        self.fl_tacc = QFormLayout()
        self.fl_tacc.setContentsMargins(0,0,0,0)
        self.fl_tacc.setSpacing(0)
        self.w_tacc.setLayout(self.fl_tacc)
        self.fl_tacc.addRow(f"Local Vol., max_downsampling", self.le_max_downsampling)
        self.fl_tacc.addRow(f"Local Vol., max_downsampled_size", self.le_max_downsampled_size)
        # self.fl_tacc.addRow(f"Local Vol., max_downsampling_scales", self.le_max_downsampling_scales)
        self.fl_tacc.addRow(f"Max # cores (downsampled scales)", self.le_tacc_num_cores)
        self.fl_tacc.addRow(f"Max # cores (scale 1)", self.le_tacc_num_scale1_cores)
        self.fl_tacc.addRow(f"Use mp.Pool (vs task queue)", self.cb_use_pool)
        self.fl_tacc.addRow(f"QtWebengine # raster threads", self.le_qtwebengine_raster_threads)
        self.fl_tacc.addRow(f"Log recipe to file", self.cb_recipe_logging)
        self.fl_tacc.addRow(f"Verbose SWIM (-v)", self.cb_verbose_swim)
        self.fl_tacc.addRow(f"DEV_MODE", self.cb_dev_mode)
        self.fl_tacc.addRow(f"Target Thumbnail Size", self.le_thumb_size)

        self.wAdvanced = QScrollArea()
        self.wAdvanced.setStyleSheet("background-color: #161c20; color: #f3f6fb;")
        self.wAdvanced.setWidget(self.w_tacc)
        self.wAdvanced.setWidgetResizable(True)
        self.wAdvanced.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.wAdvanced.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)


    def initToolbar(self):
        logger.info('')

        # self.exitButton = QPushButton()
        # self.exitButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # # self.exitButton.setFixedSize(QSize(15,15))
        # # self.exitButton.setIconSize(QSize(12,12))
        # self.exitButton.setFixedSize(QSize(16, 16))
        # self.exitButton.setIconSize(QSize(14, 14))
        # # self.exitButton.setIcon(qta.icon('fa.close'))
        # self.exitButton.setIcon(qta.icon('mdi.close'))
        # self.exitButton.clicked.connect(self.exit_app)
        # # self.exitButton.setStyleSheet(button_gradient_style)
        # # self.exitButton.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif; border: none;')
        #
        # self.minimizeButton = QPushButton()
        # self.minimizeButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.minimizeButton.setFixedSize(QSize(16, 16))
        # self.minimizeButton.setIconSize(QSize(14, 14))
        # # self.minimizeButton.setIcon(qta.icon('fa.window-minimize'))
        # self.minimizeButton.setIcon(qta.icon('mdi.minus-thick'))
        # self.minimizeButton.clicked.connect(self.showMinimized)
        # # self.minimizeButton.setStyleSheet(button_gradient_style)

        self.tbbRefresh = QToolButton()
        self.tbbRefresh.setToolTip(f"Refresh View {hotkey('R')}")
        self.tbbRefresh.clicked.connect(self._refresh)
        self.tbbRefresh.setIcon(qta.icon("fa.refresh"))

        def fn_view_faq():
            search = self.lookForTabID(search='faq')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("FAQ is already open!", msecs=3000)
            else:
                logger.info('Showing FAQ...')
                self.html_resource(resource='faq.html', title='FAQ', ID='faq')

        self.tbbFAQ = QToolButton()
        self.tbbFAQ.setToolTip(f"Read AlignEM FAQ")
        self.tbbFAQ.clicked.connect(fn_view_faq)
        self.tbbFAQ.setIcon(qta.icon("fa.question"))


        def fn_view_getting_started():
            search = self.lookForTabID(search='getting-started')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("Getting started document is already open!", msecs=3000)
            else:
                logger.info('Showing Getting Started Tips...')
                self.html_resource(resource='getting-started.html', title='Getting Started', ID='getting-started')

        self.tbbGettingStarted = QToolButton()
        self.tbbGettingStarted.setToolTip(f"Read AlignEM Tips for Getting Started")
        self.tbbGettingStarted.clicked.connect(fn_view_getting_started)
        self.tbbGettingStarted.setIcon(qta.icon("fa.map-signs"))


        def fn_glossary():
            search = self.lookForTabID(search='glossary')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("Glossary is already open!", msecs=3000)
            else:
                logger.info('Showing Glossary...')
                self.html_resource(resource='glossary.html', title='Glossary', ID='glossary')

        self.tbbGlossary = QToolButton()
        self.tbbGlossary.setToolTip(f"Read AlignEM Glossary")
        self.tbbGlossary.clicked.connect(fn_glossary)
        self.tbbGlossary.setIcon(qta.icon("fa.book"))

        self.tbbReportBug = QToolButton()
        self.tbbReportBug.setToolTip("Report a bug, suggest changes, or request features for AlignEM")
        self.tbbReportBug.clicked.connect(self.tab_report_bug)
        self.tbbReportBug.setIcon(qta.icon("fa.bug"))

        self.tbb3demdata = QToolButton()
        self.tbb3demdata.setToolTip("Access 3DEM Workbench Data")
        self.tbb3demdata.clicked.connect(self.tab_3dem_community_data)
        # self.tbb3demdata.setIcon(qta.icon("fa.database"))
        # icon = QIcon(":/icons/3DEM-WB.png")
        # icon = QIcon(":/icons/3dem-icon.png")
        icon = QIcon(":/icons/tacc-logo2.png")
        # self.tbb3demdata.setIcon(qta.icon("fa.database"))
        self.tbb3demdata.setIcon(icon)

        # self.workbenchButton = QPushButton('3DEM Workbench')
        # self.workbenchButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.workbenchButton.setFont(f)
        # self.workbenchButton.setFixedHeight(18)
        # self.workbenchButton.setIconSize(QSize(16, 16))
        # self.workbenchButton.clicked.connect(self.tab_workbench)

        # self.navWidget = HW(QLabel(' '), self.refreshButton, self.faqButton, self.gettingStartedButton, self.glossaryButton, self.bugreportButton, ExpandingWidget(self))
        # self.navWidget.setFixedHeight(18)
        # self.navWidget.setC

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(18,18))
        self.toolbar.setMovable(True)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbar.setObjectName('main-toolbar')
        # self.addToolBar(self.toolbar)

        tip = f"Show Notepad {hotkey('Z')}"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.tbbNotes = QToolButton()
        self.tbbNotes.setCheckable(True)
        self.tbbNotes.setToolTip(tip)
        self.tbbNotes.setIcon(QIcon(':/icons/notepad.png'))
        self.tbbNotes.clicked.connect(lambda: self.setdw_notes(self.tbbNotes.isChecked()))

        tip = f"Show Python console {hotkey('P')}"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.tbbPython = QCheckBox(f"Python Console {hotkey('P')}")
        self.tbbPython = QToolButton()
        self.tbbPython.setCheckable(True)
        self.tbbPython.setToolTip(tip)
        self.tbbPython.setIcon(QIcon(':/icons/python.png'))
        self.tbbPython.clicked.connect(lambda: self.setdw_python(self.tbbPython.isChecked()))

        tip = f"Show Head-up-display/process monitor {hotkey('H')}"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.tbbHud = QToolButton()
        self.tbbHud.setCheckable(True)
        self.tbbHud.setToolTip(tip)
        # self.tbbHud.setIcon(qta.icon("mdi.monitor"))
        self.tbbHud.setIcon(qta.icon("fa.terminal"))
        self.tbbHud.clicked.connect(lambda: self.setdw_hud(self.tbbHud.isChecked()))

        tip = f"Show Source Thumbnails {hotkey('T')}"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.tbbThumbs = QToolButton()
        self.tbbThumbs.setCheckable(True)
        self.tbbThumbs.setToolTip(tip)
        self.tbbThumbs.setIcon(qta.icon("mdi.relative-scale"))
        self.tbbThumbs.clicked.connect(lambda: self.setdw_thumbs(self.tbbThumbs.isChecked()))

        tip = f"Show Match Signals {hotkey('I')}"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.tbbMatches = QToolButton()
        self.tbbMatches.setCheckable(True)
        # self.tbbMatches.setChecked(False)
        self.tbbMatches.setToolTip(tip)
        self.tbbMatches.setIcon(qta.icon("mdi.image-filter-center-focus"))
        self.tbbMatches.clicked.connect(lambda: self.setdw_matches(self.tbbMatches.isChecked()))

        tip = f"Show SNR Plot {hotkey('L')}"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.tbbSnr = QToolButton()
        self.tbbSnr.setCheckable(True)
        self.tbbSnr.setToolTip(tip)
        self.tbbSnr.setIcon(qta.icon("mdi.chart-scatter-plot"))
        self.tbbSnr.clicked.connect(lambda: self.setdw_snr(self.tbbSnr.isChecked()))

        self.tbbDetachNgButton = QToolButton()
        # self.tbbDetachNgButton.setCheckable(True)
        self.tbbDetachNgButton.setIcon(qta.icon("fa.external-link-square"))
        def fn_detach_ng():
            if self._isProjectTab():
                if not self.tbbDetachNgButton.isChecked():
                    self.detachNeuroglancer()
                else:
                    try:
                        self.detachedNg.hide()
                    except:
                        print_exception()
            else:
                self.warn('No Neuroglancer to detach!')

        self.tbbDetachNgButton.pressed.connect(fn_detach_ng)
        self.tbbDetachNgButton.setToolTip('Detach Neuroglancer (open in a separate window)')


        # https://codeloop.org/pyqt5-make-multi-document-interface-mdi-application/

        # self.mdi = QMdiArea()
        # self.mdi.setMaximumHeight(500)
        # self.mdi.setBackground(QBrush(Qt.transparent))
        #
        # def WindowTrig():
        #     sub = QMdiSubWindow()
        #     sub.setWidget(QTextEdit())
        #     sub.setWindowTitle("Sub Window")
        #     self.mdi.addSubWindow(sub)
        #     sub.show()
        #
        # testmenu = QMenu()
        # testmenu.addAction("New")
        # testmenu.addAction("cascade")
        # testmenu.addAction("Tiled")
        # testmenu.triggered[QAction].connect(WindowTrig)

        self.tbbProjects = QToolButton()
        def fn_projectmanager():
            logger.info('')
            for i in range(self.globTabs.count()):
                if self.globTabs.widget(i).__class__.__name__ == 'OpenProject':
                    self.globTabs.setCurrentIndex(i)
                    return

            self._dock_thumbs = self.dwThumbs.isVisible()
            self._dock_matches = self.dwMatches.isVisible()
            self._dock_snr = self.dwSnr.isVisible()
            self.setdw_thumbs(False)
            self.setdw_matches(False)
            self.setdw_snr(False)
            # self.globTabs.addTab(OpenProject(), 'Project Manager')
            self.globTabs.insertTab(0, self.pm, 'Alignment Manager')
            self._switchtoOpenProjectTab()


        self.tbbProjects.setToolTip("Alignment Manager")
        # menu = QMenu()
        # projectsMenu = menu.addMenu("New Project")
        # action = QAction('From Folder', self)
        # action.triggered.connect()
        # projectsMenu.addAction(action)
        # action = QAction('From Selected Images', self)
        # action.triggered.connect()
        # projectsMenu.addAction(action)
        # self.tbbProjects.setMenu(projectsMenu)
        # self.tbbProjects.setPopupMode(QToolButton.InstantPopup)
        self.tbbProjects.pressed.connect(fn_projectmanager)
        self.tbbProjects.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.tbbProjects.setIcon(qta.icon("fa.folder"))
        # self.tbbProjects.setIcon(qta.icon("fa.database"))
        self.tbbProjects.setIcon(qta.icon("mdi.folder-upload-outline"))

        self.tbbMenu = QToolButton()
        self.tbbMenu.setMenu(self.menu)
        self.tbbMenu.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbbMenu.setPopupMode(QToolButton.InstantPopup)
        # self.tbbMenu.setToolTip(f"Menu")
        # self.tbbMenu.clicked.connect(fn_glossary)
        self.tbbMenu.setIcon(qta.icon("mdi.menu"))

        # self.tbbTestThread = QToolButton()
        # self.tbbTestThread.pressed.connect(self.runLongTask)
        # self.tbbTestThread.setFocusPolicy(Qt.FocusPolicy.NoFocus)


        self.tbbStats = QToolButton()
        menu = QMenu()
        menu.aboutToShow.connect(self.updateStats)
        menu.setFocusPolicy(Qt.NoFocus)
        self.tbbStats.setMenu(menu)
        self.tbbStats.setFocusPolicy(Qt.NoFocus)
        self.tbbStats.setPopupMode(QToolButton.InstantPopup)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.wStats)
        menu.addAction(action)


        self.tbbLow8 = QToolButton()
        menu = QMenu()
        menu.aboutToShow.connect(self.updateLowest8widget)
        menu.setFocusPolicy(Qt.NoFocus)
        self.tbbLow8.setMenu(menu)
        self.tbbLow8.setFocusPolicy(Qt.NoFocus)
        self.tbbLow8.setPopupMode(QToolButton.InstantPopup)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.sa8)
        menu.addAction(action)

        self.tbbAdvanced = QToolButton()
        menu = QMenu()
        menu.setFocusPolicy(Qt.NoFocus)
        self.tbbAdvanced.setMenu(menu)
        self.tbbAdvanced.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbbAdvanced.setPopupMode(QToolButton.InstantPopup)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.wAdvanced)
        menu.addAction(action)

        # menu = debugMenu.addMenu('Active Threads')
        # self.menuTextActiveThreads = QTextEdit(self)
        # self.menuTextActiveThreads.setReadOnly(True)
        # action = QWidgetAction(self)
        # action.setDefaultWidget(self.menuTextActiveThreads)
        # menu.hovered.connect(fn)
        # debugMenu.hovered.connect(fn)
        # menu.addAction(action)



        toolbuttons = [
            self.tbbMenu,
            self.tbbProjects,
            self.tbbRefresh,
            self.tbbGettingStarted,
            self.tbbFAQ,
            self.tbbGlossary,
            self.tbbReportBug,
            self.tbb3demdata,
            self.tbbThumbs,
            self.tbbMatches,
            self.tbbSnr,
            self.tbbHud,
            self.tbbNotes,
            self.tbbPython,
            self.tbbDetachNgButton,
            self.tbbStats,
            self.tbbLow8,
            self.tbbAdvanced
            # self.tbbTestThread,
        ]


        # self._lower_tb_buttons = [self.tbbStats, self.tbbLow8, self.tbbAdvanced]
        self._lower_tb_buttons = [self.tbbStats, self.tbbLow8, self.tbbAdvanced,
                                  self.tbbThumbs, self.tbbMatches, self.tbbSnr, self.tbbDetachNgButton]
        [b.setEnabled(False) for b in self._lower_tb_buttons]

        names = ['Menu', 'Projects', '&Refresh','Getting\nStarted','FAQ','Glossary','Issue\nTracker','3DEM\nData',
                 'SWIM\nRegions', ' &Matches', 'SNR P&lot', '&HUD', '&Notes', '&Python\nConsole', '&Detach\nNG',
                 'Quick Stats','Lowest 8\nSNR', 'Advanced\nOptions']
        for b,n in zip(toolbuttons,names):
            b.setText(n)
            # b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            # b.setFixedSize(QSize(64,24))
            b.setIconSize(QSize(16,16))
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            # b.setLayoutDirection(Qt.RightToLeft)
            b.setStyleSheet("QToolButton { text-align: right; margin-left: 4px;}")

        self.bExport = QPushButton('Export ')
        tip = """Export images to Zarr & TIFF"""
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bExport.setToolTip(tip)
        self.bExport.setIconSize(QSize(15,15))
        self.bExport.setIcon(qta.icon('mdi.export', color='#141414', color_disabled='#f3f6fb'),)
        self.bExport.setLayoutDirection(Qt.RightToLeft)
        # self.bExport.setStyleSheet("QPushButton{color: #141414; font-size: 11px; font-weight: 600; background-color: #b3e6b3; "
        #                            "border: 1px solid #141414; border-radius: 2px; padding: 2px;} QPushButton:disabled{color: #f3f6fb; background-color: #a3a3a3; border: none;}")
        self.bExport.setVisible(False)

        self.wExport = HW(ExpandingHWidget(self), self.bExport)

        # self.tbb3demdata.setIconSize(QSize(40,20))

        self._timerWorker = TimerWorker()
        self._timerThread = QThread()
        self._timerWorker.everySecond.connect(self.onSecondPassed)
        self._timerWorker.moveToThread(self._timerThread)
        self._timerWorker.finished.connect(self._timerThread.quit)
        self._timerThread.started.connect(self._timerWorker.secondCounter)
        self._timerThread.start()

        self.lcdTimer = QLCDNumber()
        self.lcdTimer.setFixedSize(QSize(80, 20))
        self.lcdTimer.setDigitCount(8)
        self.lcdTimer.display("00:00:00")
        self.lcdTimer.setStyleSheet("""QLCDNumber
                                                   { border: none;
                                                   background: none;
                                                   }""")
        palette = self.lcdTimer.palette()

        # foreground color
        # palette.setColor(palette.WindowText, QColor(85, 85, 255))
        palette.setColor(palette.WindowText, QColor('#161c20'))
        # background color
        palette.setColor(palette.Background, QColor('#f3f6fb'))
        # "light" border
        palette.setColor(palette.Light, QColor('#141414'))
        # "dark" border
        palette.setColor(palette.Dark, QColor('#141414'))

        # set the palette
        self.lcdTimer.setPalette(palette)



        self.wLcdTimer = HW(ExpandingHWidget(self), self.lcdTimer)

        # https://stackoverflow.com/questions/6783194/background-thread-with-qthread-in-pyqt


        self.toolbar.addWidget(self.tbbMenu)
        self.toolbar.addWidget(self.tbbProjects)
        self.toolbar.addWidget(self.tbbRefresh)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.tbbHud)
        self.toolbar.addWidget(self.tbbPython)
        self.toolbar.addWidget(self.tbbNotes)
        self.toolbar.addWidget(self.tbbThumbs)
        self.toolbar.addWidget(self.tbbMatches)
        self.toolbar.addWidget(self.tbbSnr)
        self.toolbar.addWidget(self.tbbDetachNgButton)
        self.toolbar.addWidget(self.tbbStats)
        self.toolbar.addWidget(self.tbbLow8)
        self.toolbar.addWidget(self.tbbAdvanced)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.tbbGettingStarted)
        self.toolbar.addWidget(self.tbbFAQ)
        self.toolbar.addWidget(self.tbbGlossary)
        self.toolbar.addWidget(self.tbbReportBug)
        self.toolbar.addWidget(self.tbb3demdata)
        self.toolbar.addWidget(self.wLcdTimer)

        # self.toolbar.addWidget(self.tbbTestThread)

    def onSecondPassed(self, val):
        # logger.critical('')
        def secs_to_hrsminsec(secs: int):
            mins = secs // 60
            secs %= 60
            hrs = mins // 60
            mins %= 60
            hrsminsec = f'{hrs:02}:{mins:02}:{secs:02}'
            return hrsminsec
        # logger.info(f'time: {val}')
        self.lcdTimer.display(secs_to_hrsminsec(val))
        self.lcdTimer.update()
        # QApplication.processEvents()

    def updateOutputSettings(self):
        if self.wOutputSettings.isVisible():
            poly = self.dm['defaults'][self.dm.scale]['polynomial_bias']
            if (poly == None) or (poly == 'None'):
                self.boxBias.setCurrentIndex(0)
            else:
                self.boxBias.setCurrentIndex(int(poly) + 1)
            self.cbBB.setChecked(self.dm.has_bb())


    def resizeEvent(self, e):
        logger.info('')
        self.setUpdatesEnabled(False)

        # self.dwMatches.setMaximumWidth(999)
        # self.dwThumbs.setMaximumWidth(999)

        if self.dwThumbs.isVisible():
            h = self.dwThumbs.height() - self.pt.tn_ref_lab.height() - self.pt.tn_tra_lab.height()
            # self.dwThumbs.setMaximumWidth(int(h / 2 + .5) - 10)
            self.pt.tn_widget.setMaximumWidth(int(h / 2 + .5) - 10)
            # self.pt.tn_widget.resize(int(h / 2 + .5) - 10, h) #Bad!

        if self.dwMatches.isVisible():
            h = self.dwMatches.height() - self.pt.mwTitle.height()
            # self.dwMatches.setMaximumWidth(int(h / 2 + .5) - 4)
            self.pt.match_widget.setMaximumWidth(int(h / 2 + .5) - 4)

        self.setUpdatesEnabled(True)




    def changeEvent(self, event):
        # logger.info('')

        # Allows catching of window maximized/unmaximized events
        if event.type() == QEvent.WindowStateChange:
            print("(!) Window State Change!")
            if event.oldState() and Qt.WindowMinimized:
                logger.info("(!) window un-maximized")
                self.fullScreenAction.setIcon(qta.icon('mdi.fullscreen', color='#ede9e8'))
            elif event.oldState() == Qt.WindowNoState or self.windowState() == Qt.WindowMaximized:
                logger.info("(!) window maximized")
                self.fullScreenAction.setIcon(qta.icon('mdi.fullscreen-exit', color='#ede9e8'))
            if self._isProjectTab():
                if self.pt.wTabs.currentIndex() in (0, 1):
                    self.pt.initNeuroglancer()


    def set_elapsed(self, t, desc=""):
        txt = f"Elapsed Time : %.3gs / %.3gm" % (t, t / 60)
        if desc:
            txt += " (%s)" % desc
        self.tell(txt)
        self.set_status(txt)


    def _disableGlobTabs(self):
        clr = inspect.stack()[1].function
        logger.info(f"[{clr}]")
        indexes = list(range(0, self.globTabs.count()))
        if indexes:
            indexes.remove(self.globTabs.currentIndex())
            for i in indexes:
                self.globTabs.setTabEnabled(i, False)
            # self._btn_refreshTab.setEnabled(False)

    def enableAllTabs(self):
        logger.info('')
        indexes = list(range(0, self.globTabs.count()))
        for i in indexes:
            self.globTabs.setTabEnabled(i, True)
        if self.pt:
            for i in range(0, 5):
                self.pt.wTabs.setTabEnabled(i, True)
        # self._btn_refreshTab.setEnabled(True)

    def lookForTabID(self, search):
        for i in range(self.globTabs.count()):
            w = self.globTabs.widget(i)
            if hasattr(w, 'ID'):
                if w.ID == search:
                    return i
        return None

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


    def _switchtoOpenProjectTab(self):
        for i in range(self.globTabs.count()):
            if self.globTabs.widget(i).__class__.__name__ == 'OpenProject':
                self.globTabs.setCurrentIndex(i)
                return

    def _getTabType(self, index=None):
        try:
            return self.globTabs.currentWidget().__class__.__name__
        except:
            return None

    def getOpenProjects(self):
        '''Returns a list of currently open projects.'''
        projects = []
        for i in range(self.globTabs.count()):
            if 'ProjectTab' in str(self.globTabs.widget(i)):
                projects.append(self.globTabs.widget(i).datamodel.data_location)
        return projects

    def getOpenProjectNames(self):
        '''Returns a list of currently open projects.'''
        projects = self.getOpenProjects()
        return [os.path.basename(p) for p in projects]

    def isProjectOpen(self, name):
        '''Checks whether an alignment is already open.'''
        return os.path.splitext(name)[0] in [os.path.splitext(x)[0] for x in self.getOpenProjects()]

    def getProjectIndex(self, search):
        for i in range(self.globTabs.count()):
            if 'ProjectTab' in str(self.globTabs.widget(i)):
                if self.globTabs.widget(i).datamodel.data_location == os.path.splitext(search)[0]:
                    return i

    def closeAlignment(self, dest):
        pass


    def getCurrentTabWidget(self):
        return self.globTabs.currentWidget()

    def _getTabObject(self):
        return self.globTabs.currentWidget()


    def addGlobTab(self, tab_widget, name, switch_to=True):
        logger.info(f'Adding Tab, type: {type(tab_widget)}\nName: {name}')
        cfg.tabsById[id(tab_widget)] = {}
        cfg.tabsById[id(tab_widget)]['name'] = name
        cfg.tabsById[id(tab_widget)]['type'] = type(tab_widget)
        cfg.tabsById[id(tab_widget)]['widget'] = tab_widget
        # tab_widget.setAttribute(Qt.WA_DeleteOnClose)
        if switch_to:
            self.globTabs.setCurrentIndex(self.globTabs.addTab(tab_widget, name))
        else:
            self.globTabs.addTab(tab_widget, name)


    def getTabIndexById(self, ID):
        for i in range(self.globTabs.count()):
            if ID == id(self.globTabs.widget(i)):
                return i
        logger.warning(f'Tab {ID} not found.')
        return 0



    def _onGlobTabChange(self):

        self.tabChanged.emit()
        self.setUpdatesEnabled(False)
        caller = inspect.stack()[1].function
        logger.info(f'changing tab to tab of type {self._getTabType()}')

        # self.pt = None
        # cfg.zarr_tab = None
        self.stopPlaybackTimer()
        self.reloadComboScale()
        [b.setEnabled(False) for b in self._lower_tb_buttons]
        # QApplication.restoreOverrideCursor()


        if not self._isProjectTab():
            self.statusBar.clearMessage()
            self.dwThumbs.setWidget(NullWidget())
            self.dwMatches.setWidget(NullWidget())
            self.dwSnr.setWidget(NullWidget())
            self.dwMatches.setWidget(NullWidget())
            self.dwSnr.setWidget(NullWidget())
            if self.dwSnr.isVisible():
                self.setdw_snr(False)
            if self.dwMatches.isVisible():
                self.setdw_matches(False)
            if self.dwThumbs.isVisible():
                self.setdw_thumbs(False)
            self.bExport.setVisible(False)

        elif self._isProjectTab():
            self.dm = self.dm = self.globTabs.currentWidget().datamodel
            # self.dm.signals.zposChanged.connect(self.updateSlidrZpos)
            self.pt = self.pt = self.globTabs.currentWidget()
            self.pt.initNeuroglancer() #0815-
            self.updateLowest8widget()
            [b.setEnabled(True) for b in self._lower_tb_buttons]
            try:
                if cfg.emViewer:
                    cfg.emViewer = self.pt.viewer
                if hasattr(self.pt, 'editorViewer'):
                    cfg.editorViewer = self.pt.editorViewer
            except:
                print_exception()

            # self.pt.dataUpdateMA()
            self.dwThumbs.setWidget(self.pt.tn_widget)
            self.dwMatches.setWidget(self.pt.match_widget)
            self.dwSnr.setWidget(self.pt.dSnr_plot)
            if self.dwSnr.isVisible():
                self.pt.dSnr_plot.initSnrPlot()
            self.bExport.setVisible(self.dm.is_zarr_generated())

        elif self._getTabType() == 'ZarrTab':
            logger.info('Loading Zarr Tab...')
            cfg.zarr_tab = self.globTabs.currentWidget()
            cfg.emViewer = cfg.zarr_tab.viewer
            cfg.zarr_tab.viewer.bootstrap()

        elif self._getTabType() == 'OpenProject':
            self.pm.refresh()
        
        logger.info('Wrapping up...')
        # self.updateMenus()
        self.reload_zpos_slider_and_lineedit()  # future changes to image importing will require refactor
        self.reloadComboScale()
        self.updateEnabledButtons()
        self.updateNotes()
        self._lastTab = self._getTabObject()
        self.setFocus()
        self.setUpdatesEnabled(True)

    def _onGlobTabClose(self, index):
        if not self._working:
            logger.info(f'Closing Tab: {index}')
            self.globTabs.removeTab(index)

    def _setLastTab(self):
        self.globTabs.setCurrentIndex(self.globTabs.count() - 1)

    def showActiveThreads(self, action):
        logger.info('')
        threads = '\n'.join([thread.name for thread in threading.enumerate()])
        text = f'# Active Threads : {threading.active_count()}' \
               f'Current Thread   : {threading.current_thread()}' \
               f'All Threads      : \n{threads}'
        self.menuTextActiveThreads.setText(text)

    # def updateMenus(self):
    #     '''NOTE: This should always be run AFTER initializing Neuroglancer!'''
    #     caller = inspect.stack()[1].function
    #     logger.info('')
    #     self.tensorMenu.clear()
    #     if self._isProjectTab() or self._isZarrTab():
    #         # logger.info('Clearing menus...')
    #
    #         def addTensorMenuInfo(label, body):
    #             menu = self.tensorMenu.addMenu(label)
    #             textedit = QTextEdit(self)
    #             textedit.setFixedSize(QSize(600, 600))
    #             textedit.setReadOnly(True)
    #             textedit.setText(body)
    #             action = QWidgetAction(self)
    #             action.setDefaultWidget(textedit)
    #             menu.addAction(action)
    #
    #         if self._isProjectTab():
    #             try:
    #                 addTensorMenuInfo(label='Tensor Metadata', body=json.dumps(cfg.tensor.spec().to_json(), indent=2))
    #             except:
    #                 print_exception()
    #             # if cfg.unal_tensor:
    #             #     # logger.info('Adding Raw Series tensor to menu...')
    #             #     txt = json.dumps(cfg.unal_tensor.spec().to_json(), indent=2)
    #             #     addTensorMenuInfo(label='Raw Series', body=txt)
    #             # if self.dm.is_aligned():
    #             #     if cfg.al_tensor:
    #             #         # logger.info('Adding Aligned Series tensor to menu...')
    #             #         txt = json.dumps(cfg.al_tensor.spec().to_json(), indent=2)
    #             #         addTensorMenuInfo(label='Aligned Series', body=txt)
    #         if self._isZarrTab():
    #             try:
    #                 addTensorMenuInfo(label='Zarr Series', body=json.dumps(cfg.tensor.spec().to_json(), indent=2))
    #             except:
    #                 print_exception()
    #         try:
    #             self.updateNgMenuStateWidgets()
    #         except:
    #             print_exception()
    #     else:
    #         self.clearNgStateMenus()

    def clearTensorMenu(self):
        self.tensorMenu.clear()
        textedit = QTextEdit(self)
        textedit.setFixedSize(QSize(50, 28))
        textedit.setReadOnly(True)
        textedit.setText('N/A')
        action = QWidgetAction(self)
        action.setDefaultWidget(textedit)
        self.tensorMenu.addAction(action)

    def updateNgMenuStateWidgets(self):
        if not self.dm:
            self.clearMenu(menu=self.ngStateMenu)
            return
        textedit = QTextEdit(self)
        textedit.setFixedSize(QSize(600, 600))
        textedit.setReadOnly(True)
        textedit.setText(self.get_ng_state())
        action = QWidgetAction(self)
        action.setDefaultWidget(textedit)
        self.ngStateMenu.clear()
        self.ngStateMenu.addAction(action)

    # def clearNgStateMenus(self):
    #     self.clearMenu(menu=self.ngStateMenu)

    # def clearMenu(self, menu):
    #     menu.clear()
    #     textedit = QTextEdit(self)
    #     textedit.setFixedSize(QSize(50, 28))
    #     textedit.setReadOnly(True)
    #     textedit.setText('N/A')
    #     action = QWidgetAction(self)
    #     action.setDefaultWidget(textedit)
    #     menu.addAction(action)



    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')

        self.action_groups = {}

        # self.menu = self.menuBar()
        self.menu.setFocusPolicy(Qt.NoFocus)
        # Fix for non-native menu on macOS
        # self.menu.setNativeMenuBar(False)
        # self.menu.setNativeMenuBar(True)

        self.exitAction = QAction()
        self.exitAction.setToolTip("Exit AlignEM")
        self.exitAction.setIcon(qta.icon('mdi.close', color='#ede9e8'))
        self.exitAction.triggered.connect(self.exit_app)

        self.minimizeAction = QAction()
        self.minimizeAction.setToolTip("Minimize")
        self.minimizeAction.setIcon(qta.icon('mdi.minus-thick', color='#ede9e8'))
        self.minimizeAction.triggered.connect(self.showMinimized)

        def fullscreen_callback():
            logger.info('')
            (self.showMaximized, self.showNormal)[self.isMaximized() or self.isFullScreen()]()
        self.fullScreenAction = QAction()
        self.fullScreenAction.setToolTip("Full Screen")
        self.fullScreenAction.setIcon(qta.icon('mdi.fullscreen', color='#ede9e8'))
        self.fullScreenAction.triggered.connect(fullscreen_callback)

        self.menu.addAction(self.exitAction)
        self.menu.addAction(self.minimizeAction)
        self.menu.addAction(self.fullScreenAction)

        fileMenu = self.menu.addMenu('File')

        self.openAction = QAction('&Open...', self)
        # self.openAction.triggered.connect(self.open_project)
        self.openAction.triggered.connect(self.open_project_new)
        # self.openAction.setShortcut('Ctrl+O')
        self.addAction(self.openAction)
        fileMenu.addAction(self.openAction)

        # self.openArbitraryZarrAction = QAction('Open &Zarr...', self)
        # self.openArbitraryZarrAction.triggered.connect(self.open_zarr_selected)
        # self.openArbitraryZarrAction.setShortcut('Ctrl+Z')
        # fileMenu.addAction(self.openArbitraryZarrAction)

        exportMenu = fileMenu.addMenu('Export')

        self.exportAfmAction = QAction('Affines...', self)
        self.exportAfmAction.triggered.connect(self.export_afms)
        exportMenu.addAction(self.exportAfmAction)

        self.exportCafmAction = QAction('Cumulative Affines...', self)
        self.exportCafmAction.triggered.connect(self.export_cafms)
        exportMenu.addAction(self.exportCafmAction)

        self.saveAction = QAction('&Save Project', self)
        self.saveAction.triggered.connect(self.save)
        # self.saveAction.setShortcut('Ctrl+S')
        # self.saveAction.setShortcutContext(Qt.ApplicationShortcut)
        # self.addAction(self.saveAction)
        fileMenu.addAction(self.saveAction)

        self.savePreferencesAction = QAction('Save User Preferences', self)
        self.savePreferencesAction.triggered.connect(self.saveUserPreferences)
        fileMenu.addAction(self.savePreferencesAction)

        self.resetPreferencesAction = QAction('Set Default Preferences', self)
        self.resetPreferencesAction.triggered.connect(self.resetUserPreferences)
        fileMenu.addAction(self.resetPreferencesAction)

        self.refreshAction = QAction('&Refresh', self)
        self.refreshAction.triggered.connect(self._refresh)
        self.refreshAction.setShortcut('Ctrl+R')
        self.refreshAction.setShortcutContext(Qt.ApplicationShortcut)
        # self.addAction(self.refreshAction)
        fileMenu.addAction(self.refreshAction)


        action = QAction('3DEM Community Data', self)
        action.triggered.connect(self.tab_3dem_community_data)
        fileMenu.addAction(action)



        def fn():
            logger.info('')
            if self.globTabs.count() > 0:
                # if self._getTabType() != 'OpenProject':
                self.globTabs.removeTab(self.globTabs.currentIndex())
            else:
                self.exit_app()

        self.closeTabAction = QAction(f"Close Tab {hotkey('W')}", self)
        self.closeTabAction.triggered.connect(fn)
        self.closeTabAction.setShortcut('Ctrl+W')
        self.closeTabAction.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.closeTabAction)
        fileMenu.addAction(self.closeTabAction)

        self.exitAppAction = QAction(f"&Quit {hotkey('Q')}", self)
        self.exitAppAction.triggered.connect(self.exit_app)
        self.exitAppAction.setShortcut('Ctrl+Q')
        self.exitAppAction.setShortcutContext(Qt.ApplicationShortcut)
        self.addAction(self.exitAppAction)
        fileMenu.addAction(self.exitAppAction)

        if is_tacc():
            self.restartAppAction = QAction(f"Restart Application (Experimental!)", self)
            self.restartAppAction.triggered.connect(self.restart_app)
            self.addAction(self.restartAppAction)
            fileMenu.addAction(self.restartAppAction)

        viewMenu = self.menu.addMenu("View")


        self.aPython = QAction('Show &Python', self)
        self.aPython.triggered.connect(lambda: self.setdw_python(not self.tbbPython.isChecked()))
        # self.aPython.setShortcut('Ctrl+P')
        # self.aPython.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.aPython)


        self.aHud = QAction('Show Head-up-display/process monitor', self)
        # self.aHud.triggered.connect(lambda: self.tbbHud.setChecked(not self.tbbHud.isChecked()))
        self.aHud.triggered.connect(lambda: self.setdw_hud(not self.tbbHud.isChecked()))
        # self.aHud.setShortcut('Ctrl+H')
        # self.aHud.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.aHud)

        self.aThumbs = QAction('Show SWIM Region &Thumbnails', self)
        self.aThumbs.triggered.connect(lambda: self.setdw_thumbs(not self.tbbThumbs.isChecked()))
        # self.aThumbs.setShortcut('Ctrl+T')
        # self.aThumbs.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.aThumbs)

        self.aMatches = QAction('Show &Match Signals', self)
        self.aMatches.triggered.connect(lambda: self.setdw_matches(not self.tbbMatches.isChecked()))
        viewMenu.addAction(self.aMatches)

        self.aSnr = QAction('Show SNR P&lot', self)
        self.aSnr.triggered.connect(lambda: self.setdw_snr(not self.tbbSnr.isChecked()))
        viewMenu.addAction(self.aSnr)


        # self.aNotes = QAction('Show &Notes', self)
        self.aNotes = QAction('Show &Notes', self)
        self.aNotes.triggered.connect(lambda: self.setdw_notes(not self.tbbNotes.isChecked()))
        # self.aNotes.setShortcut('Ctrl+Z')
        # self.aNotes.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.aNotes)


        self.layerLeftAction = QAction('Decrement Z-index', self)
        self.layerLeftAction.triggered.connect(self.layer_left)
        # self.layerLeftAction.setShortcut(QKeySequence('left'))
        # self.layerLeftAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.layerLeftAction)

        self.layerRightAction = QAction('Increment Z-index', self)
        self.layerRightAction.triggered.connect(self.layer_right)
        # self.layerRightAction.setShortcut(QKeySequence('right'))
        # self.layerRightAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.layerRightAction)

        self.zoomInAction = QAction('Zoom In', self)
        self.zoomInAction.triggered.connect(self.incrementZoomIn)
        # self.zoomInAction.setShortcut(QKeySequence('up'))
        # self.zoomInAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.zoomInAction)

        self.zoomOutAction = QAction('Zoom Out', self)
        self.zoomOutAction.triggered.connect(self.incrementZoomOut)
        # self.zoomOutAction.setShortcut(QKeySequence('down'))
        # self.zoomOutAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.zoomOutAction)

        alignMenu = self.menu.addMenu('Align')

        self.alignAllAction = QAction('Align + Generate All: Current Level', self)
        self.alignAllAction.triggered.connect(self.alignAll)
        alignMenu.addAction(self.alignAllAction)

        self.alignAllScalesAction = QAction('Align + Generate All Scale Levels', self)
        self.alignAllScalesAction.triggered.connect(self.alignAllScales)
        alignMenu.addAction(self.alignAllScalesAction)

        self.alignOneAction = QAction('Align + Generate Current Only', self)
        self.alignOneAction.triggered.connect(self.alignOne)
        alignMenu.addAction(self.alignOneAction)

        self.skipChangeAction = QAction('Toggle Include', self)
        # self.skipChangeAction.triggered.connect(self.skip_change_shortcut)
        # self.skipChangeAction.setShortcut('Ctrl+K')
        self.addAction(self.skipChangeAction)
        alignMenu.addAction(self.skipChangeAction)

        ngMenu = self.menu.addMenu("Neuroglancer")

        self.ngStateMenu = ngMenu.addMenu('JSON State')  # get_ng_state
        self.ngStateMenuText = QTextEdit(self)
        self.ngStateMenuText.setReadOnly(False)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.ngStateMenuText)
        # self.ngStateMenu.hovered.connect(self.updateNgMenuStateWidgets)
        ngMenu.hovered.connect(self.updateNgMenuStateWidgets)
        self.ngStateMenu.addAction(action)
        # self.clearMenu(menu=self.ngStateMenu)

        self.tensorMenu = ngMenu.addMenu('Tensors')
        self.clearTensorMenu()

        # ngPerspectiveMenu = ngMenu.addMenu("Perspective")
        self.ngLayout1Action = QAction('xy', self)
        self.ngLayout2Action = QAction('yz', self)
        self.ngLayout3Action = QAction('xz', self)
        self.ngLayout4Action = QAction('xy-3d', self)
        self.ngLayout5Action = QAction('yz-3d', self)
        self.ngLayout6Action = QAction('xz-3d', self)
        self.ngLayout7Action = QAction('3d', self)
        self.ngLayout8Action = QAction('4panel', self)
        ####
        # ngPerspectiveMenu.addAction(self.ngLayout1Action)
        # ngPerspectiveMenu.addAction(self.ngLayout2Action)
        # ngPerspectiveMenu.addAction(self.ngLayout3Action)
        # ngPerspectiveMenu.addAction(self.ngLayout4Action)
        # ngPerspectiveMenu.addAction(self.ngLayout5Action)
        # ngPerspectiveMenu.addAction(self.ngLayout6Action)
        # # ngPerspectiveMenu.addAction(self.ngLayout7Action)
        # ngPerspectiveMenu.addAction(self.ngLayout8Action)
        ####
        # self.ngLayout1Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('xy'))
        # self.ngLayout2Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('xz'))
        # self.ngLayout3Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('yz'))
        # self.ngLayout4Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('yz-3d'))
        # self.ngLayout5Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('xy-3d'))
        # self.ngLayout6Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('xz-3d'))
        # self.ngLayout7Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('3d'))
        # self.ngLayout8Action.triggered.connect(lambda: self.comboboxNgLayout.setCurrentText('4panel'))
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
        self.ngLayout2Action.setCheckable(True)
        self.ngLayout3Action.setCheckable(True)
        self.ngLayout4Action.setCheckable(True)
        self.ngLayout5Action.setCheckable(True)
        self.ngLayout6Action.setCheckable(True)
        self.ngLayout7Action.setCheckable(True)
        self.ngLayout8Action.setCheckable(True)

        ngShaderMenu = ngMenu.addMenu("Experimental Shaders")

        self.shaderDefaultAction = QAction('default', self)
        self.shaderDefaultAction.triggered.connect(self.set_shader_default)
        ngShaderMenu.addAction(self.shaderDefaultAction)
        self.shaderDefaultAction.setChecked(True)

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
        shaderActionGroup.addAction(self.shaderDefaultAction)
        shaderActionGroup.addAction(self.shader2Action)
        shaderActionGroup.addAction(self.shader3Action)
        shaderActionGroup.addAction(self.shader4Action)
        self.shader2Action.setCheckable(True)
        self.shader3Action.setCheckable(True)
        self.shader4Action.setCheckable(True)

        self.detachNgAction = QAction('Detach Neuroglancer...', self)
        self.detachNgAction.triggered.connect(self.detachNeuroglancer)
        ngMenu.addAction(self.detachNgAction)

        self.hardRestartNgNgAction = QAction('Hard Restart Neuroglancer', self)
        self.hardRestartNgNgAction.triggered.connect(self.hardRestartNg)
        ngMenu.addAction(self.hardRestartNgNgAction)

        action = QAction('Remote NG Client', self)
        action.triggered.connect(
            lambda: self.url_resource(url='https://neuroglancer-demo.appspot.com/',
                                      title='Remote NG Client'))
        ngMenu.addAction(action)

        actionsMenu = self.menu.addMenu('Actions')

        # self.rescaleAction = QAction('Rescale...', self)
        # self.rescaleAction.triggered.connect(self.rescale)
        # actionsMenu.addAction(self.rescaleAction)

        # self.rechunkAction = QAction('Rechunk...', self)
        # self.rechunkAction.triggered.connect(self.rechunk)
        # actionsMenu.addAction(self.rechunkAction)

        configMenu = self.menu.addMenu('Configure')

        self.setPlaybackSpeedAction = QAction('Configure Playback...', self)
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

        self.printfocusAction = QAction('Print Focus Widget', self)
        self.printfocusAction.triggered.connect(lambda: print(self.focusWidget()))
        debugMenu.addAction(self.printfocusAction)

        self.chromiumDebugAction = QAction('Troubleshoot Chromium', self)
        self.chromiumDebugAction.triggered.connect(self.chromium_debug)
        debugMenu.addAction(self.chromiumDebugAction)

        # def fn():
        #     try:
        #         log = json.dumps(cfg.webdriver.get_log(), indent=2)
        #     except:
        #         print_exception()
        #         log = 'Webdriver is offline.'
        #     self.menuTextWebdriverLog.setText(log)

        # menu = debugMenu.addMenu('Webdriver Log')
        # self.menuTextWebdriverLog = QTextEdit(self)
        # self.menuTextWebdriverLog.setReadOnly(True)
        # self.menuTextWebdriverLog.setText('Webdriver is offline.')
        # action = QWidgetAction(self)
        # action.setDefaultWidget(self.menuTextWebdriverLog)
        # menu.hovered.connect(fn)
        # debugMenu.hovered.connect(fn)
        # menu.addAction(action)
        #
        # def fn():
        #     try:
        #         log = json.dumps(cfg.webdriver.get_log(), indent=2)
        #     except:
        #         print_exception()
        #         log = 'Webdriver is offline.'
        #     self.menuTextWebdriverLog.setText(log)

        # menu = debugMenu.addMenu('Debug Dump')
        # self.menuTextWebdriverLog = QTextEdit(self)
        # self.menuTextWebdriverLog.setReadOnly(True)
        # action = QWidgetAction(self)
        # action.setDefaultWidget(self.menuTextWebdriverLog)

        # menu.hovered.connect(fn)
        # debugMenu.hovered.connect(fn)
        # menu.addAction(action)

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

        self.enableAllControlsAction = QAction('Enable All Controls', self)
        self.enableAllControlsAction.triggered.connect(self.enableAllButtons)
        overrideMenu.addAction(self.enableAllControlsAction)

        if cfg.DEV_MODE:
            # developerMenu = debugMenu.addMenu('Developer')
            self.developerConsoleAction = QAction('Developer Console', self)
            self.developerConsoleAction.triggered.connect(self.show_hide_developer_console)
            debugMenu.addAction(self.developerConsoleAction)



        '''Help Menu'''
        helpMenu = self.menu.addMenu('Help')


        helpPrintExportInstructions = helpMenu.addMenu('Print Export Instructions')

        # action = QAction('Export Zarr Command', self)
        # action.triggered.connect(self.printExportInstructionsTIFF)
        # helpPrintExportInstructions.addAction(action)
        #
        # action = QAction('Export TIFFs Command', self)
        # action.triggered.connect(self.printExportInstructionsZarr)
        # helpPrintExportInstructions.addAction(action)



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
        action.triggered.connect(
            lambda: self.url_resource(
                url="https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/examples/README.md",
                title='CLI Examples'))
        helpMenu.addAction(action)

        self.featuresAction = QAction('AlignEM Features', self)
        self.featuresAction.triggered.connect(
            lambda: self.html_resource(resource='features.html', title='Help: Features'))
        helpMenu.addAction(self.featuresAction)

        # self.reloadBrowserAction = QAction('Reload QtWebEngine', self)
        # self.reloadBrowserAction.triggered.connect(self.browser_reload)
        # helpMenu.addAction(self.reloadBrowserAction)

        zarrHelpMenu = helpMenu.addMenu('Zarr Help')

        action = QAction('Zarr Debrief', self)
        action.triggered.connect(lambda: self.html_resource(resource='zarr-drawing.html', title='Help: Zarr'))
        zarrHelpMenu.addAction(action)

        action = QAction('Zarr/NGFF (Nature Methods, 2021)', self)
        action.triggered.connect(lambda: self.html_resource(resource='zarr-nature-2021.html', title="Help: NGFF"))
        zarrHelpMenu.addAction(action)

        action = QAction('Lonestar6', self)
        action.triggered.connect(lambda: self.html_resource(resource='ls6.html', title='Lonestar6', ID='ls6'))
        helpMenu.addAction(action)

        action = QAction('GitHub', self)
        action.triggered.connect(
            lambda: self.url_resource(url='https://github.com/mcellteam/swift-ir/blob/development_ng/docs/README.md',
                                      title='Source Code (GitHub)'))
        helpMenu.addAction(action)

        researchGroupMenu = helpMenu.addMenu('Our Research Groups')

        action = QAction('CNL @ Salk', self)
        action.triggered.connect(lambda: self.url_resource(url='https://cnl.salk.edu/', title='Web: CNL'))
        researchGroupMenu.addAction(action)

        action = QAction('Texas Advanced Computing Center', self)
        action.triggered.connect(lambda: self.url_resource(url='https://3dem.org/workbench', title='Web: TACC'))
        researchGroupMenu.addAction(action)

        action = QAction('UTexas @ Austin', self)
        action.triggered.connect(
            lambda: self.url_resource(url='https://synapseweb.clm.utexas.edu/harrislab', title='Web: UTexas'))
        researchGroupMenu.addAction(action)

        action = QAction('MMBIoS (UPitt)', self)
        action.triggered.connect(lambda: self.url_resource(url='https://mmbios.pitt.edu/', title='Web: MMBioS'))
        researchGroupMenu.addAction(action)

        action = QAction('MCell4 Pre-print', self)
        action.triggered.connect(
            lambda: self.html_resource(resource="mcell4-preprint.html", title='MCell4 Pre-print (2023)'))
        researchGroupMenu.addAction(action)

        # self.googleAction = QAction('Google', self)
        # self.googleAction.triggered.connect(self.tab_google)
        # helpMenu.addAction(self.googleAction)

        # action = QAction('PyQtGraph Examples', self)
        # action.triggered.connect(self.pyqtgraph_examples)
        # helpMenu.addAction(action)

        action = QAction('Google', self)
        action.triggered.connect(self.tab_google)
        helpMenu.addAction(action)




    # @Slot()
    # def widgetsUpdateData(self) -> None:
    #     '''Reads MainWindow to Update Project Data.'''
    #     logger.debug('widgetsUpdateData:')

    # def _valueChangedSwimWindow(self):
    #     # logger.info('')
    #     caller = inspect.stack()[1].function
    #     if caller == 'main':
    #         logger.info(f'caller: {caller}')
    #         # self.dm.set_swim_window_global(float(self.pt.leSwimWindow.value()) / 100.)
    #         self.dm.set_size1x1(self.pt.leSwimWindow.value())

    # def printExportInstructionsTIFF(self):
    #     work = os.getenv('WORK')
    #     user = os.getenv('USER')
    #     tiffs = os.path.join(self.dm.images_location, 'scale_1', 'img_src')
    #     self.hud.post(f'Use the follow command to copy-export full resolution TIFFs to another images_location on the filesystem:\n\n'
    #                   f'    rsync -atvr {tiffs} {user}@ls6.tacc.utexas.edu:{work}/data')
    #
    #
    # def printExportInstructionsZarr(self):
    #     work = os.getenv('WORK')
    #     user = os.getenv('USER')
    #     zarr = os.path.join(self.dm.images_location, 'img_aligned.zarr', 's1')
    #     self.hud.post(
    #         f'Use the follow command to copy-export full resolution Zarr to another images_location on the filesystem:\n\n'
    #         f'    rsync -atvr {zarr} {user}@ls6.tacc.utexas.edu:{work}/data\n\n'
    #         f'Note: AlignEM supports the opening and re-opening of arbitrary Zarr files in Neuroglancer')



    def _valueChangedPolyOrder(self):
        #Todo move to ProjectTab
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            try:
                self.dm.set_stack_cafm()
            except:
                print_exception()
            if self.boxBias.currentText() == 'None':
                self.dm.poly_order = None
                self.tell('Corrective Polynomial Order is set to None')
            else:
                txt = self.boxBias.currentText()
                index = self.boxBias.findText(txt)
                val = index - 1
                self.dm.poly_order = val
                self.tell('Corrective Polynomial Order is set to %d' % val)
            if self.dwSnr.isVisible():
                self.pt.dSnr_plot.initSnrPlot()


    def rechunk(self):
        # if self._isProjectTab():
        #     if self.dm.is_aligned_and_generated():
        #         target = os.path.join(self.dm.images_location, 'img_aligned.zarr', 's%d' % self.dm.lvl())
        #         _src = os.path.join(self.dm.images_location, 'img_aligned.zarr', '_s%d' % self.dm.lvl())
        #     else:
        #         target = os.path.join(self.dm.images_location, 'img_src.zarr', 's%d' % self.dm.lvl())
        #         _src = os.path.join(self.dm.images_location, 'img_src.zarr', '_s%d' % self.dm.lvl())
        #
        #     dlg = RechunkDialog(self, target=target)
        #     if dlg.exec():
        #
        #         t_start = time.time()
        #
        #         logger.info('Rechunking...')
        #         chunkshape = self.dm['data']['chunkshape']
        #         intermediate = "intermediate.zarr"
        #
        #         os.rename(target, _src)
        #         try:
        #             source = zarr.open(store=_src)
        #             self.tell('Configuring rechunking (target: %level). New chunk shape: %level...' % (target, str(chunkshape)))
        #             logger.info('Configuring rechunk operation (target: %level)...' % target)
        #             rechunked = rechunk(
        #                 source=source,
        #                 target_chunks=chunkshape,
        #                 target_store=target,
        #                 max_mem=100_000_000_000,
        #                 temp_store=intermediate
        #             )
        #             self.tell('Rechunk plan:\n%level' % str(rechunked))
        #         except:
        #             self.warn('Unable to rechunk the array')
        #             print_exception()
        #             os.rename(_src, target) # set name back to original name
        #             return
        #
        #         self.tell('Rechunking...')
        #         logger.info('Rechunking...')
        #         rechunked.execute()
        #         self.hud.done()
        #
        #         logger.info('Removing %level...' %intermediate)
        #         self.tell('Removing %level...' %intermediate)
        #         shutil.rmtree(intermediate, ignore_errors=True)
        #         shutil.rmtree(intermediate, ignore_errors=True)
        #
        #         logger.info('Removing %level...' %_src)
        #         self.tell('Removing %level...' %_src)
        #         shutil.rmtree(_src, ignore_errors=True)
        #         shutil.rmtree(_src, ignore_errors=True)
        #         self.hud.done()
        #
        #         t_end = time.time()
        #         dt = t_end - t_start
        #         z = zarr.open(store=target)
        #         info = str(z.info)
        #         self.tell('\n%level' %info)
        #
        #         self.tell('Rechunking Time: %.2f' % dt)
        #         logger.info('Rechunking Time: %.2f' % dt)
        #
        #         self.pt.initNeuroglancer()
        #
        #     else:
        #         logger.info('Rechunking Canceled')
        pass

    def initControlPanel(self):

        tip = """Sections marked for exclusion will not be aligned or used by SWIM in any way (like a dropped frame)."""
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.cbSkip = ToggleSwitch()
        self.cbSkip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cbSkip.setToolTip(tip)
        self.cbSkip.setEnabled(False)
        self.cbSkip.stateChanged.connect(self._callbk_skipChanged)
        labSkip = QLabel('Include:')
        labSkip.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.wToggleExclude = VW(QVLine(), labSkip, self.cbSkip)
        self.wToggleExclude.layout.setSpacing(0)
        self.wToggleExclude.layout.setAlignment(Qt.AlignCenter)

        tip = 'Go To Previous Section.'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bLeftArrow = QPushButton()
        self.bLeftArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bLeftArrow.setToolTip(tip)
        self.bLeftArrow.clicked.connect(self.layer_left)
        self.bLeftArrow.setFixedSize(QSize(18, 18))
        self.bLeftArrow.setIcon(qta.icon("fa.arrow-left"))
        self.bLeftArrow.setEnabled(False)

        tip = 'Go To Next Section.'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bRightArrow = QPushButton()
        self.bRightArrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bRightArrow.setToolTip(tip)
        self.bRightArrow.clicked.connect(self.layer_right)
        self.bRightArrow.setFixedSize(QSize(18, 18))
        self.bRightArrow.setIcon(qta.icon("fa.arrow-right"))
        self.bRightArrow.setEnabled(False)

        tip = 'Go To Previous Scale.'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bArrowDown = QPushButton()
        self.bArrowDown.setEnabled(False)
        self.bArrowDown.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bArrowDown.setToolTip(tip)
        self.bArrowDown.clicked.connect(self.scale_down)
        self.bArrowDown.setFixedSize(QSize(18, 18))
        self.bArrowDown.setIcon(qta.icon("fa.arrow-down"))

        tip = 'Go To Next Scale.'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bArrowUp = QPushButton()
        self.bArrowUp.setEnabled(False)
        self.bArrowUp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bArrowUp.setToolTip(tip)
        self.bArrowUp.clicked.connect(self.scale_up)
        self.bArrowUp.setFixedSize(QSize(18, 18))
        self.bArrowUp.setIcon(qta.icon("fa.arrow-up"))

        self.wUpDownArrows = HW(self.bArrowDown, self.bArrowUp)
        self.wUpDownArrows.layout.setAlignment(Qt.AlignCenter)

        self.sldrZpos = QSlider(Qt.Orientation.Horizontal, self)
        self.sldrZpos.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sldrZpos.setFocusPolicy(Qt.StrongFocus)
        self.sldrZpos.valueChanged.connect(self.jump_to_slider)

        tip = 'Jumpt to section #'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.leJump = QLineEdit(self)
        self.leJump.setAlignment(Qt.AlignCenter)
        self.leJump.setFocusPolicy(Qt.ClickFocus)
        self.leJump.setToolTip(tip)
        self.leJump.setFixedSize(QSize(32, 16))
        self.leJump.returnPressed.connect(self.jump_to_layer)
        # self.leJump.returnPressed.connect(lambda: self.jump_to(int(self.leJump.text())))

        self.bPlayback = QPushButton()
        self.bPlayback.setFixedSize(18, 18)
        self.bPlayback.setIcon(qta.icon('fa.play'))

        self.timerPlayback = QTimer(self)
        self.bPlayback.clicked.connect(self.startStopTimer)

        def onTimer():
            logger.info('')
            self.timerPlayback.setInterval(int(1000 / self.sbFPS.value()))
            if hasattr(cfg,'data'):
                if self.pt:
                    if self.sldrZpos.value() < len(self.dm) - 1:
                        self.dm.zpos += 1
                    else:
                        self.dm.zpos = 0
                        self.timerPlayback.stop()
                        self.bPlayback.setIcon(qta.icon('fa.play'))

        self.timerPlayback.timeout.connect(onTimer)

        self.sbFPS = QDoubleSpinBox()
        self.sbFPS.setFixedSize(QSize(50, 18))
        self.sbFPS.setMinimum(.1)
        self.sbFPS.setMaximum(20)
        self.sbFPS.setSingleStep(.2)
        self.sbFPS.setDecimals(1)
        self.sbFPS.setSuffix('fps')
        self.sbFPS.setValue(float(cfg.DEFAULT_PLAYBACK_SPEED))
        self.sbFPS.setToolTip('Autoplay Speed (frames/second)')

        self.boxScale = QComboBox(self)
        self.boxScale.setFixedSize(QSize(132, 16))
        self.boxScale.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.boxScale.currentTextChanged.connect(self.onScaleChange)

        labs = [QLabel('Resolution Level'), QLabel('Z-position')]
        [lab.setAlignment(Qt.AlignLeft) for lab in labs]

        self.wwScaleLevel = HW(self.boxScale, self.wUpDownArrows)
        self.wwScaleLevel.layout.setSpacing(4)
        self.wScaleLevel = VW(labs[0], self.wwScaleLevel)
        self.wScaleLevel = VW(labs[0], self.wwScaleLevel)

        self.wLeftRightArrows = HW(self.bLeftArrow, self.bRightArrow)
        self.wLeftRightArrows.layout.setAlignment(Qt.AlignCenter)
        # self.wLeftRightArrows.layout.setAlignment(Qt.AlignCenter)

        self.wwwZpos = HW(self.leJump, self.wLeftRightArrows)
        self.wwwZpos.layout.setAlignment(Qt.AlignCenter)

        self.wwZpos = VW(labs[1], self.wwwZpos)
        self.wwZpos.setFixedWidth(80)
        self.wZpos = HW(self.bPlayback, self.sldrZpos, self.sbFPS)
        self.wZpos.layout.setSpacing(4)

        tip = """Align and generate new images for the current resolution level"""
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bAlign = QPushButton(f"Apply")
        self.bAlign = QPushButton('Align All')
        self.bAlign.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.bAlign.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bAlign.clicked.connect(self.alignAll)
        p = self.bAlign.palette()
        p.setColor(self.bAlign.backgroundRole(), QColor('#f3f6fb'))
        p.setColor(QPalette.Text, QColor("#141414"))
        self.bAlign.setPalette(p)

        self.bRegenZarr = QPushButton('Transform 3D')
        self.bRegenZarr.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bRegenZarr.clicked.connect(self.regenZarr)
        p = self.bRegenZarr.palette()
        p.setColor(self.bRegenZarr.backgroundRole(), QColor('#f3f6fb'))
        p.setColor(QPalette.Text, QColor("#141414"))
        self.bRegenZarr.setPalette(p)


        self.wAlign = HW(QVLine(), self.bAlign, self.bRegenZarr)
        self.wAlign.layout.setSpacing(4)


        '''
        OUTPUT SETTINGS
        '''

        tip = """Bounding box is only applied upon "Align All" and "Regenerate". Caution: Turning this ON may 
        significantly increase the size of generated images."""
        self.cbBB = QCheckBox()
        self.cbBB.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cbBB.toggled.connect(lambda state: self.dm.set_use_bounding_rect(state))
        # self.cbBB.toggled.connect(lambda: self.dm.set_use_bounding_rect(self.cbBB.isChecked()))

        tip = 'Polynomial bias correction (defaults to None), alters the generated images including their width and height.'
        self.boxBias = QComboBox(self)
        self.boxBias.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.boxBias.addItems(['None', 'poly 0°', 'poly 1°', 'poly 2°', 'poly 3°', 'poly 4°'])
        # self.boxBias.setCurrentText(str(cfg.DEFAULT_CORRECTIVE_POLYNOMIAL))
        self.boxBias.currentIndexChanged.connect(self._valueChangedPolyOrder)
        self.boxBias.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.boxBias.setFixedSize(QSize(74, 12))
        self.boxBias.lineEdit()

        self.bRegenerateAll = QPushButton('Regenerate All Output')
        self.bRegenerateAll.clicked.connect(lambda: self.regenerateAll())
        # self.bRegenerateAll.setFixedSize(QSize(120, 16))
        self.bRegenerateAll.setFixedHeight(15)

        hw0 = HW(QLabel('Bounding Box: '), self.cbBB, ExpandingHWidget(self), QLabel('Corrective Bias: '),
                 self.boxBias)
        hw0.layout.setAlignment(Qt.AlignBottom)
        hw1 = HW(self.bRegenerateAll)
        # hw1.layout.setAlignment(Qt.AlignRight)

        # vbl = VBL(hw0, hw1)

        self.wPopoutOutputSettings = VW(hw0, hw1)
        self.bOutputSettings = QToolButton()
        self.bOutputSettings.setText('Output\nSettings')
        self.bOutputSettings.setCheckable(True)
        self.bOutputSettings.toggled.connect(lambda state: self.wOutputSettings.setVisible(state))
        self.wOutputSettings = HW(QVLine(), self.wPopoutOutputSettings)
        self.wOutputSettings.setContentsMargins(2,0,2,0)
        self.wOutputSettings.setFixedWidth(220)
        self.wOutputSettings.hide()

        self.wCpanel = HW(self.wScaleLevel, QVLine(),
                          self.wwZpos, QVLine(),
                          self.wZpos,
                          self.wToggleExclude,
                          self.wAlign,
                          self.bOutputSettings,
                          self.wOutputSettings
                          )

        self.setAutoFillBackground(True)
        f = QFont()
        f.setPixelSize(9)
        self.wCpanel.setFont(f)
        self.wCpanel.setFixedHeight(36)
        self.wCpanel.layout.setContentsMargins(6,2,6,2)
        self.wCpanel.layout.setSpacing(4)

    def initUI(self):
        '''Initialize Main UI'''
        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)

        '''Headup Display'''
        self.hud = HeadupDisplay(self.app)
        self.hud.set_theme_dark()

        self.dwThumbs = DockWidget('Tra./Ref. Thumbnails', self)
        self.dwThumbs.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        self.dwThumbs.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        self.dwThumbs.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.dwThumbs.setObjectName('Dock Widget Thumbnails')
        self.dwThumbs.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #161c20;
                    font-weight: 600;
                    text-align: left;
                    padding: 0px;
                    margin: 0px;
                    border-width: 0px;
                }""")
        self.dwThumbs.setWidget(NullWidget())
        self.addDockWidget(Qt.RightDockWidgetArea, self.dwThumbs)
        self.dwThumbs.hide()

        self.dwMatches = DockWidget('Matches & Match Signals', self)
        self.dwMatches.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        self.dwMatches.visibilityChanged.connect(lambda: self.pt.matchPlayTimer.stop())
        self.dwMatches.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        self.dwMatches.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.dwMatches.setObjectName('Dock Widget Thumbnails')
        self.dwMatches.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #161c20;
                    font-weight: 600;
                    text-align: left;
                    padding: 0px;
                    margin: 0px;
                    border-width: 0px;
                }""")
        self.dwMatches.setWidget(NullWidget())
        self.addDockWidget(Qt.RightDockWidgetArea, self.dwMatches)
        self.dwMatches.hide()


        self.splitDockWidget(self.dwThumbs, self.dwMatches, Qt.Horizontal)



        self.dw_hud = DockWidget('HUD', self)
        def fn_dw_monitor_visChanged():
            if self.dw_hud.isVisible():
                self.setUpdatesEnabled(False)
                loc_hud = self.dockWidgetArea(self.dw_hud)
                # logger.info(f'dw_monitor images_location: {loc_hud}')
                if loc_hud in (1,2):
                    self.dw_hud.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dw_hud.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)

                loc_py = self.dockWidgetArea(self.dwPython)
                if loc_hud == loc_py:
                    if loc_hud in (4, 8):
                        # self.splitDockWidget(self.dw_hud, self.dwPython, Qt.Horizontal)
                        w = int(self.width() / 2)
                        self.resizeDocks((self.dw_hud, self.dwPython), (w, w), Qt.Horizontal)
                        # self.resizeDocks((self.dw_hud, self.dwPython),
                        #                  (self.dw_hud.sizeHint().height(), self.dw_hud.sizeHint().height()), Qt.Vertical)
                    elif loc_hud in (1, 2):
                        # self.splitDockWidget(self.dw_hud, self.dwPython, Qt.Vertical)
                        h = int(self.height() / 2)
                        self.resizeDocks((self.dw_hud, self.dwPython), (h, h), Qt.Vertical)
                self.setUpdatesEnabled(True)

        self.dw_hud.dockLocationChanged.connect(fn_dw_monitor_visChanged)
        self.dw_hud.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        # self.dw_hud.setFeatures(self.dw_hud.DockWidgetClosable | self.dw_hud.DockWidgetVerticalTitleBar)
        self.dw_hud.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
        self.dw_hud.setObjectName('Dock Widget HUD')
        self.dw_hud.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #161c20;
                    font-weight: 600;
                    text-align: left;
                    padding: 0px;
                    margin: 0px;
                    border-width: 0px;
                }""")
        self.dw_hud.setWidget(self.hud)
        self.dw_hud.hide()
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_hud)

        self.user = getpass.getuser()
        self.tell(f'Hello {self.user}. Please report any issues or bugs to joel@salk.edu.')

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

        baseline = Qt.AlignmentFlag.AlignBaseline
        vcenter = Qt.AlignmentFlag.AlignVCenter
        hcenter = Qt.AlignmentFlag.AlignHCenter
        center = Qt.AlignmentFlag.AlignCenter
        left = Qt.AlignmentFlag.AlignLeft
        right = Qt.AlignmentFlag.AlignRight

        self._processMonitorWidget = QWidget()
        lab = QLabel('Process Monitor')
        # self._processMonitorWidget.setStyleSheet('background-color: #1b2328; color: #f3f6fb; border-radius: 5px;')
        # lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 4px; margin-top: 4px;')
        vbl = QVBoxLayout()
        vbl.setSpacing(1)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lab, alignment=baseline)
        self._processMonitorWidget.setLayout(vbl)

        lab = QLabel('Details')
        self._tool_textInfo = QWidget()
        vbl = VBL()
        vbl.setSpacing(1)
        # vbl.addWidget(lab, alignment=baseline)
        self._tool_textInfo.setLayout(vbl)

        self._tool_hstry = QWidget()
        # self._tool_hstry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._hstry_listWidget = QListWidget()
        # self._hstry_listWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        self.projecthistory_model = JsonModel(parent=self)
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
        vbl = VBL()

        self.splash_widget = QWidget()  # Todo refactor this it is not in use
        self.splash_widget.setObjectName('splash_widget')
        self.splashmovie = QMovie('src/resources/alignem_animation.gif')
        self.splashlabel = QLabel()
        self.splashlabel.setMovie(self.splashmovie)
        self.splashlabel.setMinimumSize(QSize(64, 64))
        gl = QGridLayout()
        gl.addWidget(self.splashlabel, 1, 1, 1, 1)
        self.splash_widget.setLayout(gl)
        self.splash_widget.setGraphicsEffect(QGraphicsOpacityEffect().setOpacity(0.7))
        self.splashmovie.finished.connect(self.runaftersplash)

        # self.permFileBrowser = FileBrowser()

        self.viewer_stack_widget = QStackedWidget()
        self.viewer_stack_widget.setObjectName('viewer_stack_widget')
        self.viewer_stack_widget.addWidget(self.ng_widget)
        self.viewer_stack_widget.addWidget(self.splash_widget)
        # self.viewer_stack_widget.addWidget(self.permFileBrowser)


        '''Show/Hide Primary Tools Buttons'''

        def fn():
            caller = inspect.stack()[1].function
            if caller != 'updateNotes':
                if self._isProjectTab():
                    if hasattr(cfg,'data'):
                        self.dm.save_notes(text=self.notes.toPlainText())
                        self.statusBar.showMessage('Note Saved!', 3000)
                else:
                    cfg.preferences['notes']['global_notes'] = self.notes.toPlainText()
                self.notes.update()

        self.notes = QTextEdit()
        self.notes.setMinimumWidth(64)
        self.notes.setObjectName('Notes')
        self.notes.setStyleSheet("""
            background-color: #ede9e8;
            color: #161c20;
            font-size: 11px;
        """)
        self.notes.setPlaceholderText('Type any notes here...')
        self.notes.textChanged.connect(fn)
        self.dwNotes = DockWidget('Notes', self)


        def fn():
            logger.info('')
            if self. dwNotes.isVisible():
                self.setUpdatesEnabled(False)
                if self.dockWidgetArea(self.dwNotes) in (1, 2):
                    self.dwNotes.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dwNotes.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
                self.setUpdatesEnabled(True)

        self.dwNotes.dockLocationChanged.connect(fn)
        self.dwNotes.visibilityChanged.connect(lambda: self.tbbNotes.setToolTip(
            (f"Hide Notepad {hotkey('Z')}", f"Show Notepad {hotkey('Z')}")[self.dwNotes.isHidden()]))
        self.dwNotes.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        def fn():
            self.setUpdatesEnabled(False)
            if self.dwThumbs.isVisible():
                h = self.dwThumbs.height() - self.pt.tn_ref_lab.height() - self.pt.tn_tra_lab.height()
                # self.dwThumbs.setMaximumWidth(int(h / 2 + .5) - 10)
                self.pt.tn_widget.setMaximumWidth(int(h / 2 + .5) - 10)
                # self.pt.tn_widget.resize(int(h / 2 + .5) - 10, h) #Bad!
            if self.dwMatches.isVisible():
                h = self.dwMatches.height() - self.pt.mwTitle.height()
                # self.dwMatches.setMaximumWidth(int(h / 2 + .5) - 4)
                self.pt.match_widget.setMaximumWidth(int(h / 2 + .5) - 4)
            self.setUpdatesEnabled(True)
        self.dwNotes.visibilityChanged.connect(fn)
        self.dwNotes.setStyleSheet("""
                        QDockWidget {color: #161c20;}
                        QDockWidget::title {
                                    background-color: #FFE873;
                                    color: #161c20;
                                    font-weight: 600;
                                    text-align: left;
                                    padding: 0px;
                                    margin: 0px;
                                    border-width: 0px;
                                }""")
        self.dwNotes.setWidget(self.notes)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dwNotes)
        self.dwNotes.hide()

        tip = 'Show/Hide Contrast and Brightness Shaders'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self._btn_show_hide_shader = QPushButton(' Shader')
        self._btn_show_hide_shader.setFixedHeight(18)
        # self._btn_show_hide_shader.setStyleSheet(lower_controls_style)
        self._btn_show_hide_shader.setToolTip(tip)
        # self._btn_show_hide_shader.clicked.connect(self._callbk_showHideShader)
        # self._btn_show_hide_shader.setIcon(qta.icon('mdi.format-paint', color='#f3f6fb'))
        self._btn_show_hide_shader.setIcon(qta.icon('mdi.format-paint', color='#380282'))
        self._btn_show_hide_shader.setIconSize(QSize(12, 12))
        self._btn_show_hide_shader.setStyleSheet('color: #380282; font-size: 11px;')

        self.detailsTitle = QLabel('Correlation Signals')
        self.detailsTitle.setFixedHeight(13)
        self.detailsTitle.setStyleSheet(
            'color: #f3f6fb; font-size: 10px; font-weight: 600; margin-left: 2px; margin-top: 2px;')


        '''Tabs Global Widget'''
        self.globTabs = QTabWidget(self)

        # self.globTabs.setStyleSheet("""
        #
        # QTabBar::close-button {
        #     image: url(:/icons/close-tab-dark.png);
        #     subcontrol-origin: padding;
        #     subcontrol-position: right;
        #     padding-left: 6px;
        #     padding-top: 6px;
        #     padding-bottom: 6px;
        # }
        # QTabBar::close-button:!selected {
        #     image: url(:/icons/close-tab-light.png);
        #     subcontrol-origin: padding;
        #     subcontrol-position: right;
        #     padding-left: 6px;
        #     padding-top: 6px;
        #     padding-bottom: 6px;
        # """)
        self.globTabs.setTabBarAutoHide(True)
        self.globTabs.setTabShape(QTabWidget.Triangular)
        self.globTabs.tabBar().setExpanding(True)
        self.globTabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.globTabs.setUsesScrollButtons(True)
        self.globTabs.setContentsMargins(0, 0, 0, 0)
        self.globTabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.globTabs.tabBar().setStyleSheet("""
        # QTabBar::close {
        #     image: url(src/resources/close-tab-light.png);
        #     subcontrol-origin: padding;
        #     subcontrol-position: right;
        #     padding: 6px;
        # }
        # QTabBar::close:!selected {
        #
        #     image: url(src/resources/close-tab-dark.png);
        #     subcontrol-origin: padding;
        #     subcontrol-position: right;
        #     padding: 6px;
        # }
        #
        # QTabBar::tab {
        #     background-color: qlineargradient(x1:0, y1:0, x2:.5, y2:1, stop:0 #141414, stop:1 #222222);
        #     color: #f3f6fb;
        #     min-width: 120px;
        #     height: 16px;
        #     padding-left:4px;
        #     margin-left:4px;
        #     font-size: 10px;
        #     border-width: 0px;
        # }
        # QTabBar::tab:selected
        # {
        #     font-weight: 600;
        # }
        # QTabBar::tab:!selected
        # {
        #     color: #161c20;
        #     font-weight: 600;
        # }
        # """)

        self.globTabs.tabBar().setElideMode(Qt.ElideMiddle)
        self.globTabs.setElideMode(Qt.ElideMiddle)
        self.globTabs.setMovable(True)
        self.globTabs.setDocumentMode(True)
        self.globTabs.setTabsClosable(True)
        self.globTabs.setObjectName('globTabs')
        self.globTabs.tabCloseRequested[int].connect(self._onGlobTabClose)
        self.globTabs.currentChanged.connect(self._onGlobTabChange)

        # self.pythonConsole = PythonConsole()
        # self.pythonConsole.pyconsole.set_color_linux()
        self.pythonConsole.pyconsole.set_color_none()
        self.pythonConsole.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # self.pythonConsole.resize(QSize(600,600))

        self.dwPython = DockWidget('Python', self)
        self.dwPython.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        def fn_dw_python_visChanged():
            caller = inspect.stack()[1].function

            # logger.critical(f'caller: {caller}')
            if self. dwPython.isVisible():
                logger.info('>>>>')
                # self.setUpdatesEnabled(False)
                loc_py = self.dockWidgetArea(self.dwPython)
                if loc_py in (1,2):
                    self.dwPython.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dwPython.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)

                loc_hud = self.dockWidgetArea(self.dw_hud)
                # logger.critical(f"loc_py = {loc_py}, loc_hud = {loc_hud}")
                if loc_py == loc_hud:
                    if loc_py in (4, 8):
                        self.splitDockWidget(self.dw_hud, self.dwPython, Qt.Horizontal)
                        w = int(self.width() / 2)
                        self.resizeDocks((self.dw_hud, self.dwPython), (w, w), Qt.Horizontal)
                        # self.resizeDocks((self.dw_hud, self.dwPython), (self.dwPython.sizeHint().height(), self.dwPython.sizeHint().height()), Qt.Vertical)
                    elif loc_py in (1, 2):
                        self.splitDockWidget(self.dw_hud, self.dwPython, Qt.Vertical)
                        h = int(self.height() / 2)
                        self.resizeDocks((self.dw_hud, self.dwPython), (h, h), Qt.Vertical)
                # self.setUpdatesEnabled(True)
                logger.info('<<<<')

        self.dwPython.dockLocationChanged.connect(fn_dw_python_visChanged)
        self.dwPython.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
        self.dwPython.setStyleSheet("""
                QDockWidget {color: #161c20;}
                QDockWidget::title {
                            background-color: #daebfe;
                            font-weight: 600;
                            text-align: left;
                            padding: 0px;
                            margin: 0px;
                            border-width: 0px;
                        }""")
        self.dwPython.setWidget(self.pythonConsole)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dwPython)
        self.dwPython.hide()

        self.dwSnr = DockWidget('SNR', self)
        self.dwSnr.visibilityChanged.connect(self.callbackDwVisibilityChanged)


        def fn_dw_snr_visChanged():
            self.setUpdatesEnabled(False)
            caller = inspect.stack()[1].function
            if self. dwSnr.isVisible():
                loc_py = self.dockWidgetArea(self.dwSnr)
                if loc_py in (1,2):
                    self.dwSnr.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dwSnr.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)

                # self.splitDockWidget(self.dw_hud, self.dwSnr, Qt.Vertical)
                # self.splitDockWidget(self.dwPython, self.dwSnr, Qt.Vertical)
            self.setUpdatesEnabled(True)

        self.dwSnr.dockLocationChanged.connect(fn_dw_snr_visChanged)
        self.dwSnr.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
        self.dwSnr.setStyleSheet("""
                QDockWidget {color: #161c20;}
                QDockWidget::title {
                            background-color: #ffcccb;
                            font-weight: 600;
                            text-align: left;
                            padding: 0px;
                            margin: 0px;
                            border-width: 0px;
                        }""")

        self.addDockWidget(Qt.BottomDockWidgetArea, self.dwSnr)
        self.dwSnr.hide()

        # def fn_vert_dock_locations_changed():
        #     logger.info('')
        #     # if self.dw_hud.isVisible():
        #     self.setUpdatesEnabled(False)
        #     w = self.globTabs.width()
        #     half_w = int(w/2)
        #     third_w = int(w/3)
        #     self.resizeDocks((self.dw_hud, self.dwSnr), (half_w, half_w), Qt.Horizontal)
        #     self.resizeDocks((self.dw_hud, self.dwPython), (half_w, half_w), Qt.Horizontal)
        #     self.resizeDocks((self.dwSnr, self.dwPython), (half_w, half_w), Qt.Horizontal)
        #     self.resizeDocks((self.dw_hud, self.dwSnr, self.dwPython), (third_w, third_w, third_w), Qt.Horizontal)
        #     self.setUpdatesEnabled(True)

        # self.dwMatches.dockLocationChanged.connect(fn_vert_dock_locations_changed)
        # self.dwThumbs.dockLocationChanged.connect(fn_vert_dock_locations_changed)
        # self.dw_hud.dockLocationChanged.connect(fn_vert_dock_locations_changed)
        # self.dwSnr.dockLocationChanged.connect(fn_vert_dock_locations_changed)
        # self.dwPython.dockLocationChanged.connect(fn_vert_dock_locations_changed)

        # self.splitDockWidget(self.dwMatches, self.dwThumbs, Qt.Horizontal)

        '''Documentation Panel'''
        self.browser_web = QWebEngineView()
        self._buttonExitBrowserWeb = QPushButton()
        self._buttonExitBrowserWeb.setFixedSize(18, 18)
        self._buttonExitBrowserWeb.setIcon(qta.icon('fa.arrow-left'))
        self._buttonExitBrowserWeb.setFixedSize(std_button_size)
        self._buttonExitBrowserWeb.clicked.connect(self.exit_docs)
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
        buttonBrowserBack.setToolTip('Go Back')
        buttonBrowserBack.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserBack.clicked.connect(browser_backward)
        buttonBrowserBack.setFixedSize(QSize(20, 20))
        buttonBrowserBack.setIcon(qta.icon('fa.arrow-left'))

        buttonBrowserForward = QPushButton()
        buttonBrowserForward.setToolTip('Go Forward')
        buttonBrowserForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserForward.clicked.connect(browser_forward)
        buttonBrowserForward.setFixedSize(QSize(20, 20))
        buttonBrowserForward.setIcon(qta.icon('fa.arrow-right'))

        buttonBrowserRefresh = QPushButton()
        buttonBrowserRefresh.setToolTip('Refresh')
        buttonBrowserRefresh.setIcon(qta.icon("fa.refresh"))
        buttonBrowserRefresh.setFixedSize(QSize(22, 22))
        buttonBrowserRefresh.clicked.connect(browser_reload)

        buttonBrowserCopy = QPushButton('Copy')
        buttonBrowserCopy.setToolTip('Copy Text')
        buttonBrowserCopy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserCopy.clicked.connect(browser_copy)
        buttonBrowserCopy.setFixedSize(QSize(50, 20))

        buttonBrowserPaste = QPushButton('Paste')
        buttonBrowserPaste.setToolTip('Paste Text')
        buttonBrowserPaste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserPaste.clicked.connect(browser_paste)
        buttonBrowserPaste.setFixedSize(QSize(50, 20))

        button3demCommunity = QPushButton('3DEM Community Data')
        button3demCommunity.setToolTip('Vist the 3DEM Community Workbench')
        button3demCommunity.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button3demCommunity.clicked.connect(self.browser_3dem_community)
        button3demCommunity.setFixedSize(QSize(120, 20))

        # webpage
        browser_controls_widget = QWidget()
        browser_controls_widget.setFixedHeight(24)
        hbl = HBL()
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserBack, alignment=right)
        hbl.addWidget(buttonBrowserForward, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserRefresh, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserCopy, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserPaste, alignment=left)
        hbl.addWidget(QLabel('   |   '))
        hbl.addWidget(button3demCommunity, alignment=left)
        browser_controls_widget.setLayout(hbl)

        vbl = VBL()
        vbl.addWidget(browser_controls_widget, alignment=Qt.AlignmentFlag.AlignLeft)
        vbl.addWidget(self.browser_web)
        hbl = HBL()
        hbl.addWidget(self._buttonExitBrowserWeb, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(w)
        browser_bottom_controls = QWidget()
        browser_bottom_controls.setFixedHeight(20)
        browser_bottom_controls.setLayout(hbl)
        vbl.addWidget(browser_bottom_controls)
        self.browser_widget.setLayout(vbl)

        self.globTabsAndCpanel = VW(self.globTabs, self.wCpanel)
        self.globTabsAndCpanel.layout.setStretch(0,9)
        self.globTabsAndCpanel.layout.setStretch(1,0)
        # self.addToolBar(Qt.LeftToolBarArea, self.toolbar)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        # self.addToolBar(Qt.BottomToolBarArea, self.wCpanel)
        self.globTabsAndCpanel.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setCentralWidget(self.globTabsAndCpanel)
        # self.setCentralWidget(VW(self.globTabsAndCpanel, self.test_widget))
        # self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks)
        self.setDockOptions(QMainWindow.AnimatedDocks)


    def updateLowest8widget(self):
        logger.info('')
        if self.dm:
            if self.dm.is_aligned():
                logger.info('')
                n_lowest = min(8, len(self.dm) - 1)
                lowest_X_i = [x[0] for x in list(self.dm.snr_lowest(n_lowest))]
                lowest_X = list(self.dm.snr_lowest(n_lowest))
                self.lowestX_btns = []
                self.lowestX_txt = []

                for i in range(n_lowest):
                    try:
                        # logger.info(f'i = {i}, lowest_X_i[i] = {lowest_X_i[i]}')
                        s1 = ('z-index <u><b>%d</b></u>' % lowest_X[i][0]).ljust(15)
                        s2 = ("<span style='color: #a30000;'>%.2f</span>" % lowest_X[i][1]).ljust(15)
                        combined = s1 + ' ' + s2
                        self.lowestX_txt.append(combined)
                        zpos = copy.deepcopy(lowest_X_i[i])
                        btn = QPushButton(f'Jump To {zpos}')
                        self.lowestX_btns.append(btn)
                        btn.setLayoutDirection(Qt.RightToLeft)
                        btn.setFixedSize(QSize(78, 16))
                        btn.setStyleSheet("font-size: 9px;")
                        btn.setIconSize(QSize(12, 12))
                        btn.setIcon(qta.icon('fa.arrow-right', color='#ede9e8'))
                        # self.lowestX_btns[i].clicked.connect(funcs[i])
                        btn.clicked.connect(lambda state, x=zpos: self.jump_to_index(x))
                    except:
                        print_exception()

                self.lowX_left_fl = QFormLayout()
                self.lowX_left_fl.setContentsMargins(4,18,4,4)
                self.lowX_left_fl.setVerticalSpacing(1)
                if n_lowest >= 1:
                    self.lowX_left_fl.addRow(self.lowestX_txt[0], self.lowestX_btns[0])
                if n_lowest >= 2:
                    self.lowX_left_fl.addRow(self.lowestX_txt[1], self.lowestX_btns[1])
                if n_lowest >= 3:
                    self.lowX_left_fl.addRow(self.lowestX_txt[2], self.lowestX_btns[2])
                if n_lowest >= 4:
                    self.lowX_left_fl.addRow(self.lowestX_txt[3], self.lowestX_btns[3])
                if n_lowest >= 5:
                    self.lowX_left_fl.addRow(self.lowestX_txt[4], self.lowestX_btns[4])
                if n_lowest >= 6:
                    self.lowX_left_fl.addRow(self.lowestX_txt[5], self.lowestX_btns[5])
                if n_lowest >= 7:
                    self.lowX_left_fl.addRow(self.lowestX_txt[6], self.lowestX_btns[6])
                if n_lowest >= 8:
                    self.lowX_left_fl.addRow(self.lowestX_txt[7], self.lowestX_btns[7])
                self.lowX_left = QWidget()
                self.lowX_left.setStyleSheet("QScrollArea{border-radius: 8px; border-width: 2px; "
                                             "border-color: #161c20; font-size:10px;}")
                self.lowX_left.setWindowFlags(Qt.FramelessWindowHint)
                self.lowX_left.setAutoFillBackground(False)
                self.lowX_left.setContentsMargins(4,4,4,4)
                # self.lowX_left.setLayout(self.lowX_left_fl)
                self.lowX_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                self.gb8 = QGroupBox('Your 8 Most Unfavorable Alignments')
                self.gb8.setWindowFlags(Qt.FramelessWindowHint)
                self.gb8.setAutoFillBackground(False)
                self.gb8.setAlignment(Qt.AlignBottom)
                self.gb8.setStyleSheet("QGroupBox{border-radius: 8px; border-width: 2px; border-color: #161c20; font-size:10px;}")
                self.gb8.setLayout(self.lowX_left_fl)
                self.sa8.setWidget(self.gb8)

            else:
                label = QLabel('Not Yet Aligned.')
                label.setStyleSheet("font-size: 11px; color: #161c20; font-weight: 600;")
                label.setAlignment(Qt.AlignCenter)
                self.sa8.setWidget(label)

        else:
            self.sa8.setWidget(NullWidget())


    def initLowest8Widget(self):
        self.sa8 = QScrollArea()
        self.sa8.setAutoFillBackground(True)
        self.sa8.setStyleSheet("background-color: #161c20; color: #f3f6fb;")
        # self.sa8.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.sa8.setWidgetResizable(True)
        self.sa8.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa8.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa8.setFixedSize(QSize(200,164))


    def _initProjectManager(self):
        self.pm = cfg.pm = OpenProject(parent=self)
        self.globTabs.addTab(self.pm, 'Alignment Manager')
        # self.globTabs.tabBar().setTabButton(0, QTabBar.RightSide,None)
        # self._setLastTab()

    def get_application_root(self):
        return Path(__file__).parents[2]


    def initWidgetSpacing(self):
        logger.info('')
        self.hud.setContentsMargins(0, 0, 0, 0)
        self._tool_hstry.setMinimumWidth(128)
        # self.pt._transformationWidget.setFixedWidth(248)
        # self.pt._transformationWidget.setFixedSize(248,100)

    def initStatusBar(self):
        logger.info('')
        self.statusBar = QStatusBar()
        self.statusBar.setFixedHeight(17)
        self.setStatusBar(self.statusBar)

    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setFixedWidth(320)
        self.pbar.setFixedHeight(13)
        self.pbar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pbar.setTextVisible(True)
        self.bStopPbar = QPushButton('Stop')
        self.bStopPbar.setStyleSheet("font-size: 8px;")
        self.bStopPbar.setFixedSize(36, 12)
        self.bStopPbar.setIconSize(QSize(11, 11))
        self.bStopPbar.setToolTip('Cancel running tasks')
        self.bStopPbar.setIcon(qta.icon('mdi.cancel'))
        self.bStopPbar.clicked.connect(self.cancelTasks)
        # self.wPbar = HW(ExpandingHWidget(self), self.pbar, self.bStopPbar)
        self.wPbar = HW(self.pbar, self.bStopPbar)
        self.wPbar.layout.setAlignment(Qt.AlignRight)
        # self.wPbar.layout.setAlignment(Qt.AlignCenter)
        self.wPbar.layout.setContentsMargins(4, 0, 4, 0)
        self.wPbar.layout.setSpacing(1)
        self.statusLabel = QLabel()
        self.statusBar.addPermanentWidget(ExpandingHWidget(self))
        self.statusBar.addPermanentWidget(self.statusLabel)
        self.statusBar.addPermanentWidget(self.wPbar)
        self.wPbar.hide()

    def cancelTasks(self):
        logger.critical("STOP TASKS requested!")
        self._working = False
        if hasattr(self, '_alignworker'):
            try:
                self._alignworker.stop()
            except:
                logger.warning('Unable to stop _alignworker or no _alignworker to stop')
        if hasattr(self, '_scaleworker'):
            try:
                self._scaleworker.stop()
            except:
                logger.warning('Unable to stop _scaleworker or no _scaleworker to stop')

        self.cleanupAfterCancel()

    def setPbarMax(self, x):
        self.pbar.setMaximum(x)

    def setPbar(self, n:int):
        '''New method to replace historical pbar functionality 2023-08-09'''
        self.pbar.setValue(n)
        # QApplication.processEvents() #1007-
        self.pbar.update()

    def resetPbar(self, data:tuple):
        '''New method to replace historical pbar functionality 2023-08-09'''
        # self.sw_pbar.show()
        self.wPbar.show()
        self.pbar.setMaximum(data[0])
        self.pbar.setValue(0)
        self.pbar.setFormat('  (%p%) ' + data[1])
        # logger.info(f"Progress bar reset with maximum {data[0]}, descript: {data[1]}")
        # QApplication.processEvents() #1007-


    def updatePbar(self, x=None):
        if x == None: x = 1
        self.pbar.setValue(x)
        self.pbar.update() #1015+
        sys.stdout.flush() #1015+

    def hidePbar(self):
        logger.info('')
        self.wPbar.hide()

    def back_callback(self):
        logger.info("Returning Home...")
        self.viewer_stack_widget.setCurrentIndex(0)

    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self._hstry_listWidget:
            menu = QMenu()
            self.history_view_action = QAction('View')
            self.history_view_action.setToolTip('View this alignment as a tree view')
            self.history_view_action.triggered.connect(self.view_historical_alignment)
            self.history_rename_action = QAction('Rename')
            self.history_rename_action.setToolTip('Rename this file')
            self.history_rename_action.triggered.connect(self.rename_historical_alignment)
            self.history_delete_action = QAction('Delete')
            self.history_delete_action.setToolTip('Delete this file')
            self.history_delete_action.triggered.connect(self.remove_historical_alignment)
            menu.addAction(self.history_view_action)
            menu.addAction(self.history_rename_action)
            menu.addAction(self.history_delete_action)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
                logger.info(f'Item Text: {item.text()}')
            return True
        return super().eventFilter(source, event)

    def store_var(self, name, var):
        setattr(cfg, name, var)


    def get_dw_monitor(self):
        for i, dock in enumerate(self.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Head-up Display':
                return self.children()[i]

    def get_dw_notes(self):
        for i, dock in enumerate(self.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Notes':
                return self.children()[i]

    # def mousePressEvent(self, event):
    #     if event.bBlink() == Qt.LeftButton:
    #         self._old_pos = event.pos()
    #
    # def mouseReleaseEvent(self, event):
    #     if event.bBlink() == Qt.LeftButton:
    #         self._old_pos = None
    #
    # def mouseMoveEvent(self, event):
    #     if not self._old_pos:
    #         return
    #     delta = event.pos() - self._old_pos
    #     self.move(self.pos() + delta)


    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)
        key = event.key()

        if cfg.DEV_MODE:
            t0 = time.time()
            logger.info(f'{key} ({event.text()} / {event.nativeVirtualKey()} / modifiers: {event.nativeModifiers()}) was pressed!')

        if key == Qt.Key_Slash:
            if self._isProjectTab():
                # self.setUpdatesEnabled(False)
                if self.pt.wTabs.currentIndex() == 1:
                    logger.info(f"Slash pressed! toggle:[{self.dm['state']['tra_ref_toggle']}]")
                    if self.dm['state']['tra_ref_toggle'] == 'tra':
                        self.pt.set_reference()
                    else:
                        self.pt.set_transforming()
                # self.setUpdatesEnabled(True)

        # left arrow key = 16777234
        elif key == 16777234:
            self.layer_left()

        # right arrow key = 16777236
        elif key == 16777236:
            self.layer_right()

        elif key == 35 and event.nativeVirtualKey() == 20:
            logger.info("Shift + 3 was pressed")

        elif key == Qt.Key_Escape:
            if self.isMaximized():
                self.showNormal()
            elif self._isOpenProjTab():
                self.pm.resetView()

        # elif key == Qt.Key_B:
        #     if self._isProjectTab():
        #         if self.pt.wTabs.currentIndex() == 1:
        #             self.pt.gifPlayer.bBlink.click()

        # Shift key workaround
        # elif key == 16777248:
        #     logger.info('16777248 was pressed!')
        #     if self._isProjectTab():
        #         cur = self.pt.wTabs.currentIndex()
        #         self.pt.wTabs.setCurrentIndex((cur + 1) % 5)
        # elif key == Qt.Key_Shift:
        #     logger.info(f"{Qt.Key_Shift} was pressed")
        #     if self._isProjectTab():
        #         cur = self.pt.wTabs.currentIndex()
        #         self.pt.wTabs.setCurrentIndex((cur + 1) % 5)

        elif key == Qt.Key_F11:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        # elif key == Qt.Key_R:
        #     self._refresh()

        elif key == Qt.Key_Space:
            if self._isProjectTab():
                self.pt.wTabs.setCurrentIndex(0)


        # elif key == Qt.Key_M:
        #     self.enterExitManAlignMode()
        # r = 82
        # m = 77
        # k = 75
        # p = 80
        elif key == Qt.Key_K:
            if self._isProjectTab():
                self.skip_change_shortcut()

        elif key == Qt.Key_P:
            self.aPython.trigger()
            # self.setdw_python(not self.tbbPython.isChecked())

        elif key == Qt.Key_H:
            self.aHud.trigger()
            # self.setdw_hud(not self.tbbHud.isChecked())

        elif key == Qt.Key_N:
            self.aNotes.trigger()
            # self.setdw_notes(not self.tbbNotes.isChecked())

        elif key == Qt.Key_T:
            self.aThumbs.trigger()
            # self.setdw_thumbs(not self.tbbThumbs.isChecked())

        elif key == Qt.Key_M:
            self.aMatches.trigger()
            # self.setdw_matches(not self.tbbMatches.isChecked())

        elif key == Qt.Key_S:
            # self.save()
            self._autosave()

        elif key == Qt.Key_D:
            if self._isProjectTab():
                self.detachNeuroglancer()

        # elif key == Qt.Key_A:
        #     self.alignAll()

        elif key == Qt.Key_B:
            if self._isProjectTab():
                self.pt.blink_main_fn()


        # elif key == Qt.Key_V:
        #     self.enterExitManAlignMode()

        elif key == Qt.Key_Up:
            if self._isProjectTab():
                if self.pt.wTabs.currentIndex() in (0, 1):
                    self.incrementZoomIn()

        elif key == Qt.Key_Down:
            if self._isProjectTab():
                if self.pt.wTabs.currentIndex() in (0, 1):
                    self.incrementZoomOut()

        # elif key == Qt.Key_Tab:
        #     logger.info('')
        #     if self._isProjectTab():
        #         new_index = (self.pt.wTabs.currentIndex()+1)%4
        #         logger.info(f'new index: {new_index}')
        #         self.pt.wTabs.setCurrentIndex(new_index)

        elif key == Qt.Key_Delete:
            if self._isOpenProjTab():
                self._getTabObject().delete_projects()
        else:
            super().keyPressEvent(event) # re-raise the event if it doesn't match!

        if cfg.DEV_MODE:
            dt = time.time() - t0
            logger.info(f"keyPressEvent time elapsed = {dt:.4g}") # time elapsed = 0.20649194717407227


        # # left arrow key = 16777234
        # elif key == 16777234:
        #     self.layer_left()
        #
        # # right arrow key = 16777236
        # elif key == 16777236:
        #     self.layer_right()

        # self.keyPressed.emit(event)


class DockWidget(QDockWidget):
    hasFocus = Signal([QDockWidget])

    def __init__(self, text, parent=None):
        super().__init__(text)
        self.setObjectName(text)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)

    # def event(self, event):
    #     if event.type() == QEvent.MouseButtonPress and event.button() == 1:
    #         self.hasFocus.emit(self)
    #         logger.info(f'Emission from {self.objectName()}')
    #     return super().event(event)


class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

class ExpandingVWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)


class MarqueeLabel(QLabel):
    def __init__(self, parent=None):
        QLabel.__init__(self, parent)
        self.px = 0
        self.py = 15
        self._direction = Qt.LeftToRight
        self.setWordWrap(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(40)
        self._speed = 2
        self.textLength = 0
        self.fontPointSize = 0
        self.setAlignment(Qt.AlignVCenter)
        self.setFixedHeight(self.fontMetrics().height())

    def setFont(self, font):
        QLabel.setFont(self, font)
        self.setFixedHeight(self.fontMetrics().height())

    def updateCoordinates(self):
        align = self.alignment()
        if align == Qt.AlignTop:
            self.py = 10
        elif align == Qt.AlignBottom:
            self.py = self.height() - 10
        elif align == Qt.AlignVCenter:
            self.py = self.height() / 2
        self.fontPointSize = self.font().pointSize() / 2
        self.textLength = self.fontMetrics().width(self.text())

    def setAlignment(self, alignment):
        self.updateCoordinates()
        QLabel.setAlignment(self, alignment)

    def resizeEvent(self, event):
        self.updateCoordinates()
        QLabel.resizeEvent(self, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._direction == Qt.RightToLeft:
            self.px -= self.speed()
            if self.px <= -self.textLength:
                self.px = self.width()
        else:
            self.px += self.speed()
            if self.px >= self.width():
                self.px = -self.textLength
        painter.drawText(int(self.px), int(self.py + self.fontPointSize), self.text())
        painter.translate(self.px, 0)

    def speed(self):
        return self._speed

    def setSpeed(self, speed):
        self._speed = speed

    def setDirection(self, direction):
        self._direction = direction
        if self._direction == Qt.RightToLeft:
            self.px = self.width() - self.textLength
        else:
            self.px = 0
        self.update()

    def pause(self):
        self.timer.stop()

    def unpause(self):
        self.timer.start()


class NullWidget(QLabel):
    def __init__(self, *args):
        QLabel.__init__(self, *args)
        self.setText('Nothing To Show :)')
        self.setMinimumSize(QSize(100,100))
        self.setStyleSheet("""font-size: 11px; background-color: #222222; color: #ede9e8;""")
        self.setAlignment(Qt.AlignCenter)

class WebEngine(QWebEngineView):

    def __init__(self, ID='webengine'):
        QWebEngineView.__init__(self)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)
        # self.inFocus = Signal(str)
        # self.installEventFilter(self)


class AspectWidget(QWidget):
    '''
    A widget that maintains its aspect ratio.
    '''
    def __init__(self, *args, ratio=4/1, **kwargs):
        super().__init__(*args, **kwargs)
        self.ratio = ratio
        self.adjusted_to_size = (-1, -1)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored))

    def resizeEvent(self, event):
        size = event.size()
        if size == self.adjusted_to_size:
            # Avoid infinite recursion. I suspect Qt does this for you,
            # but it'level best to be safe.
            return
        self.adjusted_to_size = size

        full_width = size.width()
        full_height = size.height()
        width = min(full_width, full_height * self.ratio)
        height = min(full_height, full_width / self.ratio)

        h_margin = round((full_width - width) / 2)
        v_margin = round((full_height - height) / 2)

        self.setContentsMargins(h_margin, v_margin, h_margin, v_margin)


class TimerWorker(QObject):
    finished = Signal()
    everySecond = Signal(int)

    @Slot()
    def secondCounter(self):
        self._countup = 0
        self._running = True
        while self._running:
            time.sleep(1)
            if self._running:
                self._countup += 1
                self.everySecond.emit(self._countup)

        self.finished.emit()

'''
#indicators css

QGroupBox::indicator:unchecked {
    image: url(:/images/checkbox_unchecked.png);
}

https://stackoverflow.com/questions/47206667/collect-all-docked-widgets-and-their-locations
for dock in self.findChildren(QDockWidget):
    print(dock.windowTitle())


area = self.dockWidgetArea(dock)
if area == QtCore.Qt.LeftDockWidgetArea:
    print(dock.windowTitle(), '(Left)')
elif area == QtCore.Qt.RightDockWidgetArea:
    print(dock.windowTitle(), '(Right)')



for i,dock in enumerate(self.findChildren(QDockWidget)):
    title = dock.windowTitle()
    area = self.dockWidgetArea(dock)
    # if title == 'Correlation Signals':
    if title == 'Head-up Display':
        if area in (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea):
            print(True)



"Z-stack position"

d = dict()
def checkbox_changed(self, state):
    self.ILCheck = (state == Qt.Checked)
    print(self.ILCheck)
    d[self.sender()] = self.ILCheck
    print(d)


'''

"""
FAQs:

Q: What is alignEM?
A: alignEM is a software tool specialized for registering electron micrographs. It is
   able to generate level image hierarchies, compute affine transforms, and generate aligned
   images using multi-image rendering.

Q: Can alignEM be used to register or "align" non-EM images?
A: Yes, but its forte is aligning EM images which tend to be large, and greyscale. alignEM
   provides functionality for downscaling and the ability to pass alignment results (affines)
   from lower level levels to higher ones.

Q: What are scales?
A: In alignEM a "level" means a downsampled (or decreased resolution) images of images.

Q: Why should data be scaled? Is it okay to align the full resolution images with brute force?
A: You could, but EM images tend to run large. A more efficient workflow is to:
   1) generate a hierarchy of downsampled images from the full resolution images
   2) align the lowest resolution images first
   3) pass the computed affines to the level of next-highest resolution, and repeat
      until the full resolution images are in alignment. In these FAQs this is referred to
      as "climbing the level hierarchy""

Q: Why do SNR values not necessarily increase as we "climb the level hierarchy"?
A: SNR values returned by SWIM are a relative metric which depend on image resolution. It is
   therefore most useful when comparing the relative alignment quality of aligned image
   pairs at the same level.

Q: Why are the selected manual correlation regions not mutually independent? In other words,
   why does moving or removing an argument to SWIM affect the signal-to-noise ratio and
   resulting correlation signals of the other selected SWIM regions?
A:

Q: What is Neuroglancer?
A: Neuroglancer is an open-source WebGL and typescript-based web application for displaying
   volumetric data. alignEM uses a Chromium-based API called QtWebEngine together
   with the Neuroglancer Python API to render large volumetric data efficiently and conveniently
   within the application window.

Q: What is Zarr?
A: Zarr is an open-source format for the storage of chunked, compressed, N-dimensional arrays
   with an interface similar to NumPy. It has a Nature Methods paper:
   https://www.nature.com/articles/s41592-021-01326-w

Q: Why is alignEM so swift?
A: For several reasons:
   1) Time-intensive processes are executed in parallel.
   2) Data scaling, SWIM alignment, and affine processing functions are all implemented
      in highly efficient C code written by computer scientist Arthur Wetzel.
   3) Fast Fourier Transform is a fast algorithm.

Q: How many CPUs or "cores" does alignEM use?
A: By default, as many cores as the system has available.

Q: What file types are supported?
A: Currently, only images formatted as TIFF.

Q: Where can I learn more about the principles of Signal Whitening Fourier Transform Image Matching?
A: https://mmbios.pitt.edu/images/ScientificMeetings/MMBIOS-Aug2014.pdf




"""

