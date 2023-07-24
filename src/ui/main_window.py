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
from math import sqrt
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
import time
import psutil
import resource
import platform
import datetime
import multiprocessing
import subprocess
from collections import OrderedDict
import numpy as np
# from guppy import hpy; h=hpy()
import neuroglancer as ng
import qtawesome as qta
# from rechunker import rechunk
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QTimer, QPoint, QRectF, \
    QPropertyAnimation, QSettings, QObject, QThread, QFileInfo
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QKeySequence, QMovie, QStandardItemModel, QColor, QCursor, QImage, QPainterPath, QRegion
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import QApplication, qApp, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QInputDialog, QLineEdit, QPushButton, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QCheckBox, QSpinBox, QDoubleSpinBox, QRadioButton, QSlider, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QMenuBar, QTableView, QTabWidget, QStatusBar, QTextBrowser, \
    QFormLayout, QGroupBox, QScrollArea, QToolButton, QWidgetAction, QSpacerItem, QButtonGroup, QAbstractButton, \
    QApplication, QPlainTextEdit, QTableWidget, QTableWidgetItem, QDockWidget, QDialog, QDialogButtonBox, QFrame, \
    QSizeGrip, QTabBar, QAbstractItemView, QStyledItemDelegate, QMdiArea, QMdiSubWindow

import src.config as cfg
import src.shaders
from src.thumbnailer import Thumbnailer
from src.background_worker import BackgroundWorker
from src.compute_affines import ComputeAffines
from src.config import ICON_COLOR
from src.data_model import DataModel
from src.funcs_zarr import tiffs2MultiTiff
from src.generate_aligned import GenerateAligned
# from src.generate_scales import GenerateScales
from src.generate_scales_zarr import GenerateScalesZarr
from src.helpers import run_checks, setOpt, getOpt, getData, setData, print_exception, get_scale_val, \
    natural_sort, tracemalloc_start, tracemalloc_stop, tracemalloc_compare, tracemalloc_clear, \
    exist_aligned_zarr, configure_project_paths, isNeuroglancerRunning, \
    update_preferences_model, delete_recursive, initLogFiles, is_mac, hotkey, make_affine_widget_HTML, \
    check_project_status, caller_name, is_joel, is_tacc, run_command
from src.ui.dialogs import AskContinueDialog, ConfigProjectDialog, ConfigAppDialog, NewConfigureProjectDialog, \
    open_project_dialog, export_affines_dialog, mendenhall_dialog, RechunkDialog, ExitAppDialog, SaveExitAppDialog
from src.ui.process_monitor import HeadupDisplay
from src.ui.models.json_tree import JsonModel
from src.ui.toggle_switch import ToggleSwitch
from src.ui.sliders import DoubleSlider, RangeSlider
from src.ui.widget_area import WidgetArea
from src.funcs_image import ImageSize
from src.ui.webpage import WebPage
from src.ui.tab_browser import WebBrowser
from src.ui.tab_open_project import OpenProject
from src.ui.thumbnail import CorrSignalThumbnail, ThumbnailFast, SnrThumbnail
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel, Button
from src.ui.timer import Timer
from src.autoscale import autoscale
# from src.ui.flicker import Flicker

# from src.ui.components import AutoResizingTextEdit
from src.mendenhall_protocol import Mendenhall
import src.pairwise
# if cfg.DEV_MODE:
#     from src.ui.python_console import PythonConsole
from src.ui.python_console import PythonConsole, PythonConsoleWidget

__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

DEV = is_joel()

# logger.critical('_Directory of this script: %s' % os.path.dirname(__file__))

class MainWindow(QMainWindow):
    resized = Signal()
    # keyPressed = Signal(int)
    keyPressed = Signal(QEvent)
    # alignmentFinished = Signal()
    updateTable = Signal()
    cancelMultiprocessing = Signal()
    zposChanged = Signal()
    # swimWindowChanged = Signal()



    def __init__(self, data=None):
        QMainWindow.__init__(self)
        self.app = QApplication.instance()
        self.app.setStyleSheet("border-radius: 12px; ")
        self.setObjectName('mainwindow')
        try:
            self.branch = run_command('git', arg_list=['rev-parse', '--abbrev-ref', 'HEAD'])['out'].rstrip()
        except:
            print_exception()
            self.branch = ''
        tstamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        self.window_title = 'AlignEM-SWIFT - branch: %s - %s' % (self.branch, tstamp)
        self.setWindowTitle(self.window_title)
        # self.setWindowTitle('AlignEM-SWIFT (%s)' % tstamp)
        self.setAutoFillBackground(False)

        self.settings = QSettings("cnl", "alignem")
        if self.settings.value("windowState") == None:
            self.initSizeAndPos(cfg.WIDTH, cfg.HEIGHT)
        else:
            self.restoreState(self.settings.value("windowState"))
            self.restoreGeometry(self.settings.value("geometry"))

        # self.menu = self.menuBar()
        self.menu = QMenu()
        # self.menu = QMenuBar()
        # self.menu.setFixedWidth(700)
        # self.setMenuBar(self.menu)
        # self.menu = QMenu()
        cfg.thumb = Thumbnailer()
        self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.initImageAllocations()
        self.initPrivateMembers()
        self.initThreadpool(timeout=250)
        self.initOpenGlContext()
        # self.initPythonConsole()
        self.initStatusBar()
        self.initPbar()
        self.initControlPanel()
        self.initMenu()
        self.initToolbar()

        self.initUI()

        # self.initMenu()
        self.initWidgetSpacing()
        self.initStyle()
        # self.initShortcuts()

        self.initLaunchTab()

        cfg.event = multiprocessing.Event()

        # self.alignmentFinished.connect(self.updateProjectTable)
        self.cancelMultiprocessing.connect(self.cleanupAfterCancel)

        self.activateWindow()

        self.tell('To Relaunch on Lonestar6:\n\n  source $WORK/swift-ir/tacc_boostrap\n')

        if not cfg.NO_SPLASH:
            self.show_splash()

        self.pbar_cancel_button.setEnabled(cfg.DAEMON_THREADS)

        # self.settings = QSettings("cnl", "alignem")
        # # if not self.settings.value("geometry") == None:
        # #     self.restoreGeometry(self.settings.value("geometry"))
        # if not self.settings.value("windowState") == None:
        #     self.restoreState(self.settings.value("windowState"))

        # font = QFont("Tahoma")
        # font = QFont("Calibri")
        font = QFont("Tahoma")
        QApplication.setFont(font)

        # self.setFocusPolicy(Qt.StrongFocus)

        # QApplication.processEvents()
        # self.resizeThings()

        # QTimer.singleShot(1000, self.resizeThings)
        # self.zposChanged.connect(lambda: logger.critical(f'Z-index changed! New zpos is {cfg.data.zpos}'))
        # self.zposChanged.connect(self.dataUpdateWidgets)

        # self.setWindowFlags(Qt.FramelessWindowHint)

        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea )
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea )
        self.setDockNestingEnabled(True)




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
                if cfg.data.is_aligned():
                    for l in cfg.data.get_iter():
                        try:
                            mb = l['alignment']['method_results']['memory_mb']
                            # gb = l['alignment']['method_results']['memory_gb']
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

    def eventFilter(self, object, event):
        if DEV:
            if event.type() == QEvent.WindowActivate:
                logger.critical("widget window has gained focus")
            elif event.type() == QEvent.WindowDeactivate:
                logger.critical("widget window has lost focus")
            elif event.type() == QEvent.FocusIn:
                logger.critical("widget has gained keyboard focus")
            elif event.type() == QEvent.FocusOut:
                logger.critical("widget has lost keyboard focus")


    # def resizeThings(self):
    #     logger.critical('Resizing things...')

        # if self._isProjectTab():
        #     cfg.pt.fn_hwidgetChanged()
        #     logger.critical('Resizing things, isProjectTab...')
        #     h = cfg.project_tab.wEditAlignment.height()
        #     # cfg.pt.sideTabs.setFixedWidth(int(.26 * self.width()))
        #     ms_w = int(h/4 + 0.5)
        #     tn_w = int((h - cfg.project_tab.tn_ref_lab.height() - cfg.project_tab.tn_ref_lab.height()) / 2 + 0.5)
        #     cfg.pt.ms_widget.setFixedWidth(ms_w)
        #     cfg.pt.match_widget.setFixedWidth(ms_w)
        #     cfg.pt.tn_widget.setFixedWidth(tn_w)


    def restore_tabs(self, settings):
        '''self.restore_tabs(self.settings)'''
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
        '''self.save_tabs(self.settings)'''
        for w in qApp.allWidgets():
            mo = w.metaObject()
            if w.objectName() != "":
                for i in range(mo.propertyCount()):
                    name = mo.property(i).name()
                    settings.setValue("{}/{}".format(w.objectName(), name), w.property(name))


    @Slot(name='my-zpos-signal-name')
    def setZpos(self, z=None, on_state_change=False):

        if self._isProjectTab():


            if z == None:
                z = cfg.data.zpos

            caller = inspect.stack()[1].function
            logger.info(f'[{caller}] requested z-index: {z}')
            # if cfg.data.zpos != z:
            cfg.data.zpos = z

            if not cfg.data['state']['tra_ref_toggle']:
                cfg.pt.set_transforming()

            # if cfg.data['state']['current_tab'] == 1:
            #     cfg.baseViewer.set_layer(cfg.data.zpos)
            #     cfg.refViewer.set_layer(cfg.data.get_ref_index()) #0611+
            #     # cfg.stageViewer.set_layer(cfg.data.zpos) #stageViewer
            # else:
            #     cfg.emViewer.set_layer(cfg.data.zpos)

            if cfg.pt._tabs.currentIndex() == 0:
                cfg.emViewer.set_layer(cfg.data.zpos)
            elif cfg.pt._tabs.currentIndex() == 1:
                cfg.baseViewer.set_layer(cfg.data.zpos)
                cfg.refViewer.set_layer(cfg.data.get_ref_index())  # 0611+


            # if on_state_change:
            #     if getData('state,manual_mode'):
            #         if not cfg.pt.rb_transforming.isChecked():
            #             cfg.pt.setRbTransforming()
            #         cfg.baseViewer.set_layer(cfg.data.zpos)
            #         cfg.stageViewer.set_layer(cfg.data.zpos)
            # else:
            #     if getData('state,manual_mode'):
            #         cfg.baseViewer.set_layer(cfg.data.zpos)
            #         cfg.stageViewer.set_layer(cfg.data.zpos)
            #     else:
            #         cfg.emViewer.set_layer(cfg.data.zpos)
            self.dataUpdateWidgets()
            self.zposChanged.emit()
            # else:
            #     logger.info(f'Zpos is the same! sender: {self.sender()}. Canceling...')


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
        # cfg.project_tab.snr_plot.initSnrPlot()
        if self.dw_snr.isVisible():
            cfg.project_tab.dSnr_plot.initSnrPlot()
        # cfg.project_tab.updateTreeWidget()
        self.dataUpdateWidgets()
        self.updateEnabledButtons()

    def hardRestartNg(self):
        caller = inspect.stack()[1].function
        logger.critical('\n\n**HARD** Restarting Neuroglancer (caller: %s)...\n' % caller)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if self._isProjectTab() or self._isZarrTab():
            if ng.is_server_running():
                logger.info('Stopping Neuroglancer...')
                ng.server.stop()
            elif cfg.project_tab:
                cfg.project_tab.initNeuroglancer()
            elif cfg.zarr_tab:
                cfg.zarr_tab.load()
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)

    def refreshTab(self):
        # caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}')

        if cfg.CancelProcesses:
            cfg.CancelProcesses = False
            logger.warning('\n\ncfg.CancelProcesses was TRUE. Resetting its value.\n')
        if not self._working:
            self.tell('Refreshing...')
            logger.critical('Refreshing...')
            self.dataUpdateWidgets()
            if self._isProjectTab():
                cfg.project_tab.refreshTab()
                self.updateEnabledButtons()  # 0301+
                # self.updateAllCpanelDetails()
                self.setControlPanelData()
            elif self._isOpenProjTab():
                configure_project_paths()
                self._getTabObject().user_projects.set_data()
            elif self._getTabType() == 'WebBrowser':
                self._getTabObject().browser.page().triggerAction(QWebEnginePage.Reload)
            elif self._getTabType() == 'QWebEngineView':
                self.globTabs.currentWidget().reload()
            self.hud.done()
        else:
            self.warn('The application is busy')
            logger.warning('The application is busy')


    def shutdownNeuroglancer(self):
        if ng.is_server_running():
            if DEV:
                logger.critical('[DEV] Stopping Neuroglancer...')
            # self.tell('Stopping Neuroglancer...')
            ng.server.stop()
            time.sleep(.1)

    def tell(self, message):
        self.hud.post(message, level=logging.INFO)
        self.update()

    def warn(self, message):
        self.hud.post(message, level=logging.WARNING)
        self.statusBar.showMessage(message, msecs=3000)
        # self.statusBar.showMessage(message)
        # self.statusBar.showMessage("<p style='color:red;'>" + message + "</p>")
        self.update()

    def err(self, message):
        self.hud.post(message, level=logging.ERROR)
        self.update()

    def bug(self, message):
        self.hud.post(message, level=logging.DEBUG)
        self.update()

    def initThreadpool(self, timeout=1000):
        if cfg.USE_EXTRA_THREADING:
            logger.info('')
            self.threadpool = QThreadPool.globalInstance()
            self.threadpool.setExpiryTimeout(timeout)  # ms
        else:
            self.threadpool = None

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

        # if DEV:
        self.printFocusTimer = QTimer()
        self.printFocusTimer.setSingleShot(False)
        self.printFocusTimer.setInterval(500)
        def fn():
            if self._isProjectTab():
                # if DEV:
                #     print(f'focus widget  : {self.focusWidget()}')
                #     print(f'object name   : {self.focusWidget().objectName()}')
                #     print(f'object type   : {type(self.focusWidget())}')
                #     print(f'object id     : {id(self.focusWidget())}')
                #     print(f'object parent : {self.focusWidget().parent()}')

                #CriticalMechanism
                try:
                    if 'tab_project.WebEngine' in str(self.focusWidget().parent()):
                        self.setFocus()
                except:
                    pass
        self.printFocusTimer.timeout.connect(fn)
        self.printFocusTimer.start()

        self.uiUpdateTimer = QTimer()
        self.uiUpdateTimer.setSingleShot(True)
        # self.uiUpdateTimer.timeout.connect(lambda: self.dataUpdateWidgets(silently=True))
        self.uiUpdateTimer.timeout.connect(self.dataUpdateWidgets)
        # self.uiUpdateTimer.setInterval(250)
        # self.uiUpdateTimer.setInterval(450)
        self.uiUpdateTimer.setInterval(cfg.UI_UPDATE_DELAY)

        # self.uiUpdateRegularTimer = QTimer()
        # # self.uiUpdateRegularTimer.setInterval(1000)
        # self.uiUpdateRegularTimer.setInterval(5000)
        # self.uiUpdateRegularTimer.timeout.connect(lambda: self.dataUpdateWidgets(silently=True))
        # self.uiUpdateRegularTimer.start()

        self._unsaved_changes = False
        self._working = False
        self._scales_combobox_switch = 0  # 1125
        self._isPlayingBack = 0
        self._isProfiling = 0
        self.detachedNg = WebPage()
        self.count_calls = {}
        self._exiting = 0
        self._is_initialized = 0
        self._old_pos = None

    def initStyle(self):
        logger.info('')
        self.apply_default_style()

    # def initPythonConsole(self):
    #     logger.info('')
    #
    #     namespace = {
    #         'pg': pg,
    #         'np': np,
    #         'cfg': src.config,
    #         'mw': src.config.main_window,
    #         'emViewer': cfg.emViewer,
    #         'ng': ng,
    #     }
    #     text = """
    #     Caution - any code executed here is injected into the main event loop of AlignEM-SWiFT!
    #     """
    #     cfg.py_console = pyqtgraph.console.ConsoleWidget(namespace=namespace, text=text)
    #     self.pythonConsole = QWidget()
    #     self.pythonConsole.setAutoFillBackground(False)
    #     # self.pythonConsole.setStyleSheet('background: #222222; color: #f3f6fb; border-radius: 5px;')
    #     # self.pythonConsole.setStyleSheet('background: #ede9e8; color: #141414; border-radius: 5px;')
    #     self.pythonConsole.setStyleSheet("""
    #                                     QWidget {background-color: #ede9e8; color: #141414;}
    #                                     QLineEdit {background-color: #ede9e8; }
    #                                     QPlainTextEdit {background-color: #ede9e8; }
    #                                     QPushButton""")
    #     lab = QLabel('Python Console')
    #     # lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
    #     # lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 4px; margin-top: 4px;')
    #     lab.setStyleSheet("""
    #         color: #141414;
    #         font-size: 10px;
    #         font-weight: 600;
    #         padding-left: 2px;
    #         padding-top: 2px;
    #         """)
    #     vbl = QVBoxLayout()
    #     vbl.setContentsMargins(0,0,0,0)
    #     vbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignBaseline)
    #     vbl.addWidget(cfg.py_console)
    #     self.pythonConsole.setLayout(vbl)
    #     self.pythonConsole.hide()
    #     # pass

    def test(self):
        if self._isProjectTab():
            logger.critical(f'id(cfg.pt)   = {id(cfg.pt)}')
            # logger.critical(f'cfg.dataById = {str(cfg.dataById)}')
            logger.critical(f'cfg.data == cfg.dataById[{id(cfg.pt)}]? {cfg.data == cfg.dataById[id(cfg.pt)]}')

    def updateCorrSignalsDrawer(self, z=None):

        if self.dw_matches.isVisible():

            if z == None: z = cfg.data.zpos

            # caller = inspect.stack()[1].function
            if not self._isProjectTab():
                return

            logger.info('')

            # if not cfg.data.is_aligned():
            #     cfg.pt.ms_widget.hide()
            #     return
            # else:
            #     cfg.pt.ms_widget.show()

            thumbs = cfg.data.get_signals_filenames(l=z)
            n = len(thumbs)
            snr_vals = cfg.data.snr_components(l=z)
            # logger.info(f'snr_vals = {snr_vals}')
            colors = cfg.glob_colors
            count = 0
            # for i in range(7):

            for i in range(4):
                if not cfg.pt.msList[i]._noImage:
                    cfg.pt.msList[i].set_no_image()

            # #Critical0601-
            # if not cfg.data.is_aligned_and_generated():
            #     for i in range(4):
            #         if not cfg.pt.msList[i]._noImage:
            #             cfg.pt.msList[i].set_no_image()
            #
            #     return #0610+


            # logger.critical('thumbs: %s' % str(thumbs))
            # logger.critical('snr_vals: %s' % str(snr_vals))
            method = cfg.data.get_current_method(l=z)
            if method == 'grid-custom':
                regions = cfg.data.grid_custom_regions
                names = cfg.data.get_grid_custom_filenames(l=z)
                # logger.info('names: %s' % str(names))
                for i in range(4):
                    if regions[i]:
                        try:
                            try:
                                snr = snr_vals[count]
                                assert snr > 0.0
                            except:
                                print_exception()
                                cfg.pt.msList[i].set_no_image()
                                continue

                            cfg.pt.msList[i].set_data(path=names[i], snr=snr)
                            # cfg.pt.msList[i].update()

                            count += 1
                        except:
                            print_exception()
                            logger.warning(f'There was a problem with index {i}, {names[i]}\ns')
                    else:
                        cfg.pt.msList[i].set_no_image()
                        # cfg.pt.msList[i].update()

            # elif cfg.data.current_method == 'manual-hint':
            #     cfg.data.snr_components()
            elif method == 'manual-strict':
                for i in range(4):
                    if not cfg.pt.msList[i]._noImage:
                        cfg.pt.msList[i].set_no_image()
                        # cfg.pt.msList[i].update()
            else:
                for i in range(4):
                    if i < n:
                        # logger.info('i = %d ; name = %s' %(i, str(thumbs[i])))
                        try:
                            try:
                                snr = snr_vals[i]
                                assert snr > 0.0
                                if method == 'manual-hint':
                                    n_ref = len(cfg.data.manpoints()['ref'])
                                    n_base = len(cfg.data.manpoints()['base'])
                                    assert n_ref > i
                                    assert n_base > i
                            except:
                                # logger.info(f'no SNR data for corr signal index {i}')
                                cfg.pt.msList[i].set_no_image()
                                print_exception()
                                continue

                            cfg.pt.msList[i].set_data(path=thumbs[i], snr=snr)
                        except:
                            print_exception()
                            cfg.pt.msList[i].set_no_image()
                            logger.warning(f'There was a problem with index {i}, {thumbs[i]}')
                        # finally:
                        #     cfg.pt.msList[i].update()
                    else:
                        cfg.pt.msList[i].set_no_image()
                        # cfg.pt.msList[i].update()

            # logger.info('<<<< updateCorrSignalsDrawer <<<<')


    def setTargKargPixmaps(self, z=None):

        if self.dw_matches.isVisible():
            if z == None:
                z = cfg.data.zpos





            logger.info('')
            # caller = inspect.stack()[1].function
            # logger.critical(f'setTargKargPixmaps [{caller}] >>>>')

            # basename = cfg.data.filename_basename()
            # filename, extension = os.path.splitext(basename)
            basename = cfg.data.filename_basename(l=z)
            filename, extension = os.path.splitext(basename)

            for i in range(4):
                cfg.pt.match_thumbnails[i].set_no_image()

            if cfg.data.skipped(l=z):
                return

            # for i in range(4):
            #     if not cfg.pt.match_thumbnails[i]._noImage:
            #         cfg.pt.match_thumbnails[i].set_no_image()

            if getData('state,targ_karg_toggle'):
                tkarg = 'k'
            else:
                tkarg = 't'
            files = []
            for i in range(0, 4):
                name = '%s_%s_%s_%d%s' % (filename, cfg.data.current_method, tkarg, i, extension)
                files.append(os.path.join(cfg.data.dest(), cfg.data.scale_key, 'tmp', name))

            method = cfg.data.current_method

            # logger.info(f'Files:\n{files}')

            if method in ('grid-custom', 'grid-default'):
                # for i in range(n_cutouts):
                for i in range(0, 4):
                    use = True
                    if method == 'grid-custom':
                        use = cfg.data.grid_custom_regions[i]
                    elif method == 'grid-default':
                        use = cfg.data.grid_default_regions[i]

                    # logger.info(f'file  : {files[i]}  exists? : {os.path.exists(files[i])}  use? : {use}')
                    path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'tmp', files[i])
                    if use and os.path.exists(path):
                        cfg.pt.match_thumbnails[i].path = path
                        try:
                            # cfg.pt.match_thumbnails[i].showPixmap()
                            cfg.pt.match_thumbnails[i].set_data(path)
                        except:
                            cfg.pt.match_thumbnails[i].set_no_image()
                    else:
                        cfg.pt.match_thumbnails[i].set_no_image()

            if cfg.data.current_method == 'manual-hint':
                n_ref = len(cfg.data.manpoints()['ref'])
                n_base = len(cfg.data.manpoints()['base'])
                for i in range(0, 4):
                    path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'tmp', files[i])
                    # if DEV:
                    #     logger.info(f'path: {path}')
                    #     logger.info(f'i = {i}, n_ref = {n_ref}, n_base = {n_base}')

                    try:
                        # if DEV:
                        #     logger.info(f'path: {path}')
                        assert os.path.exists(path)
                        #Todo add handler... generate a warning or something...
                        assert n_ref > i
                        assert n_base > i
                    except:
                        # print_exception(extra=f"path = {path}")
                        # logger.critical('Handling Exception...')
                        cfg.pt.match_thumbnails[i].set_no_image()

                        continue
                    try:
                        cfg.pt.match_thumbnails[i].path = path
                        # cfg.pt.match_thumbnails[i].showPixmap()
                        cfg.pt.match_thumbnails[i].set_data(path)
                    except:
                        cfg.pt.match_thumbnails[i].set_no_image()
                        print_exception()

            # logger.info('<<<< setTargKargPixmaps')

    def callbackDwVisibilityChanged(self):
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}] [{caller_name()}] {self.dw_python.isVisible()} {self.dw_hud.isVisible()} {self.dw_notes.isVisible()}')
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['python'] = self.dw_python.isVisible()
            cfg.data['state']['tool_windows']['hud'] = self.dw_hud.isVisible()
            cfg.data['state']['tool_windows']['notes'] = self.dw_notes.isVisible()
            cfg.data['state']['tool_windows']['raw_thumbnails'] = self.dw_thumbs.isVisible()
            cfg.data['state']['tool_windows']['signals'] = self.dw_matches.isVisible()
            cfg.data['state']['tool_windows']['snr_plot'] = self.dw_snr.isVisible()
        self.tbbPython.setChecked(self.dw_python.isVisible())
        self.tbbHud.setChecked(self.dw_hud.isVisible())
        self.tbbNotes.setChecked(self.dw_notes.isVisible())
        self.tbbThumbnails.setChecked(self.dw_thumbs.isVisible())
        self.tbbMatches.setChecked(self.dw_matches.isVisible())
        self.tbbSnr.setChecked(self.dw_snr.isVisible())


    def setdw_python(self, state):
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}], state={state}')
        self.setUpdatesEnabled(False)

        self.dw_python.setVisible(state)
        self.a_python.setText(('Show Python Console', 'Hide Python Console')[state])
        self.tbbPython.setToolTip((f"Show Python Console Tool Window ({hotkey('P')})",
                                  f"Hide Python Console Tool Window ({hotkey('P')})")[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['python'] = state

        # if self.dw_python.isVisible():
        #     if self.dw_hud.isVisible():
        #         # self.splitDockWidget(self.dw_hud,self.dw_python,Qt.Horizontal)
        #         w = int(self.width() / 2)
        #         self.resizeDocks((self.dw_hud, self.dw_python), (w, w), Qt.Horizontal)

        self.setUpdatesEnabled(True)


    def setdw_hud(self, state):
        self.setUpdatesEnabled(False)
        self.dw_hud.setVisible(state)
        self.a_monitor.setText(('Show Process Monitor', 'Hide Process Monitor')[state])
        tip1 = '\n'.join(f"Show Python Console Tool Window ({hotkey('H')})")
        tip2 = '\n'.join(f"Hide Python Console Tool Window ({hotkey('H')})")
        self.tbbHud.setToolTip((tip1, tip2)[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['hud'] = state
        self.setUpdatesEnabled(True)


    def setdw_thumbs(self, state):
        logger.critical('')
        self.dw_thumbs.setVisible(state)
        self.dw_thumbs.setVisible(self.tbbThumbnails.isChecked())
        tip1 = '\n'.join(f"Show Raw Thumbnails Tool Window ({hotkey('T')})")
        tip2 = '\n'.join(f"Hide Raw Thumbnails Tool Window ({hotkey('T')})")
        self.tbbThumbnails.setToolTip((tip1, tip2)[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['raw_thumbnails'] = state


        # if state:
        #     QApplication.processEvents()
        #     cfg.mw.dataUpdateWidgets()
        #     h = self.dw_thumbs.height() - cfg.pt.tn_ref_lab.height() - cfg.pt.tn_tra_lab.height()
        #     self.dw_thumbs.setMaximumWidth(int(h / 2 + .5))
        #     # cfg.pt.tn_widget.resize(QSize(int(h / 2 + .5), cfg.pt.tn_widget.height()))



    def setdw_matches(self, state):
        self.dw_matches.setVisible(state)
        self.dw_matches.setVisible(self.tbbMatches.isChecked())
        tip1 = '\n'.join(f"Show Matches and Signals Tool Window ({hotkey('M')})")
        tip2 = '\n'.join(f"Hide Matches and Signals Tool Window ({hotkey('M')})")
        self.tbbMatches.setToolTip((tip1, tip2)[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['signals'] = state

        # if state:
        #     # cfg.pt.match_widget.adjustSize() #MUCH BETTER OFF
        #     self.setUpdatesEnabled(True)
        #     QApplication.processEvents()
        #     self.updateCorrSignalsDrawer()
        #     self.setTargKargPixmaps()
        #
        #     if cfg.data.is_aligned():
        #         h = self.dw_matches.height() - cfg.pt.mwTitle.height()
        #         self.dw_matches.setMaximumWidth(int(h /2 + .5))
        #         # cfg.pt.match_widget.resize(int(h / 2 + .5), h)




    def setdw_notes(self, state):
        logger.info(f'state={state}')
        self.setUpdatesEnabled(False)
        self.dw_notes.setVisible(state)
        self.a_notes.setText(('Show Notes', 'Hide Notes')[state])
        self.tbbNotes.setToolTip(("Show Notes Tool Window (" + ('^', '⌘')[is_mac()] + "N)",
                                 "Hide Notes Tool Window (" + ('^', '⌘')[is_mac()] + "N)")[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['notes'] = state
        self.updateNotes()
        self.setUpdatesEnabled(True)

    def setdw_snr(self, state):
        logger.info(f'state={state}')
        self.setUpdatesEnabled(False)
        self.dw_snr.setVisible(state)
        self.a_snr.setText(('Show SNR Plot', 'Hide SNR Plot')[state])
        self.tbbSnr.setToolTip((f"Show SNR Plot Tool Window ({hotkey('L')})",
                                 f"Hide SNR Plot Tool Window ({hotkey('L')})")[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['snr_plot'] = state
            cfg.pt.dSnr_plot.initSnrPlot()
        self.setUpdatesEnabled(True)

    # def _callbk_showHidePython(self):
    #     # self.dw_python.setHidden(not self.dw_python.isHidden())
    #     self.dw_python.setVisible(self.tbbPython.isChecked())
    #     self.tbbPython.setToolTip(("Hide Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)",
    #                               "Show Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)")[
    #                                  self.dw_python.isHidden()])

    # def _callbk_showHideNotes(self):
    #     # self.dw_notes.setHidden(not self.dw_notes.isHidden())
    #     self.dw_notes.setVisible(self.tbbNotes.isChecked())
    #     self.updateNotes()

    # def _callbk_showHideHud(self):
    #     # self.dw_hud.setHidden(not self.dw_hud.isHidden())
    #     self.dw_hud.setVisible(self.tbbHud.isChecked())
    #     tip1 = '\n'.join(textwrap.wrap('Hide Head-up Display (Process Monitor) Tool Window', width=35))
    #     tip2 = '\n'.join(textwrap.wrap('Show Head-up Display (Process Monitor) Tool Window', width=35))
    #     self.tbbHud.setToolTip((tip1, tip2)[self.dw_hud.isHidden()])

    def _showSNRcheck(self, s=None):
        # logger.info('')
        # caller = inspect.stack()[1].function
        if s == None: s = cfg.data.scale_key
        if cfg.data.is_aligned():
            # logger.info('Checking SNR data for %s...' % cfg.data.scale_pretty(s=s))
            failed = cfg.data.check_snr_status()
            if len(failed) == len(cfg.data):
                self.warn('No SNR Data Available for %s' % cfg.data.scale_pretty(s=s))
            elif failed:
                indexes, names = zip(*failed)
                lst_names = ''
                for name in names:
                    lst_names += f'\n  Section: {name}'
                self.warn(f'No SNR Data For Sections: {", ".join(map(str, indexes))}')



        # range(10, 0, -1)

    def fix_cafm(self):
        first_cafm_false = cfg.data.first_cafm_false()
        self.regenerate(scale=cfg.data.scale_key, start=first_cafm_false, end=len(cfg.data), reallocate_zarr=False)

        self.dataUpdateWidgets()


    def regenerateOne(self):
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        self.regenerate(scale=cfg.data.scale_key, start=start, end=end)


    def regenerate(self, scale, start=0, end=None, reallocate_zarr=True) -> None:
        '''Note: For now this will always reallocate Zarr, i.e. expects arguments for full stack'''
        logger.info('regenerate >>>>')
        self.setNoPbarMessage(True)

        STAGEIT = False

        if cfg.event.is_set():
            cfg.event.clear()
        if not self._isProjectTab():
            return
        if self._working == True:
            self.warn('Another Process is Already Running')
            return
        if not cfg.data.is_aligned(s=scale):
            self.warn('Scale Must Be Aligned First')
            return
        cfg.nProcessSteps = 3
        cfg.nProcessDone = 0
        cfg.CancelProcesses = False
        self.pbarLabel.setText('Task (0/%d)...' % cfg.nProcessSteps)
        self.showZeroedPbar(set_n_processes=3)
        if end == None:
            end = len(cfg.data)
        cfg.data.set_has_bb(cfg.data.use_bb())  # Critical, also see regenerate
        self.tell('Regenerating %s aligned images for sections #%d to #%d...' % (cfg.data.scale_pretty(s=scale), start, end))
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=GenerateAligned(
                    cfg.data, scale, start, end, stageit=STAGEIT, reallocate_zarr=reallocate_zarr, use_gui=True))
                self.threadpool.start(self.worker)
            else:
                GenerateAligned(cfg.data, scale, start, end, stageit=STAGEIT, reallocate_zarr=reallocate_zarr, use_gui=True)
        except:
            print_exception()


        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=cfg.thumb.reduce_aligned(start=start, end=end, dest=cfg.data.dest(), scale=scale))
                self.threadpool.start(self.worker)
            else:
                cfg.thumb.reduce_aligned(start=start, end=end, dest=cfg.data.dest(), scale=scale)

        except:
            print_exception()
        finally:
            self.setNoPbarMessage(False)
            # self.updateAllCpanelDetails()
            cfg.pt.updateDetailsPanel()
            self.hidePbar()
            cfg.project_tab.updateTimingsWidget()
            cfg.project_tab.updateTreeWidget()
            cfg.nProcessDone = 0
            cfg.nProcessSteps = 0
            cfg.project_tab.initNeuroglancer()
            logger.info('<<<< regenerate')
            self.tell('<span style="color: #FFFF66;"><b>**** Processes Complete ****</b></span>')

        logger.info('<<<< regenerate')

    def verify_alignment_readiness(self) -> bool:
        # logger.critical('')
        ans = False
        if not cfg.data:
            self.warn('No project yet!')
        elif self._working == True:
            self.warn('Another Process is Running')
        elif not cfg.data.is_alignable():
            warning_msg = "Scale %s must be aligned first!" % get_scale_val(cfg.data.next_coarsest_scale_key())
            self.warn(warning_msg)
        else:
            ans = True
        # logger.info(f'Returning: {ans}')
        return ans

    # @Slot()
    # def restore_interactivity(self):
    #     self._working = False
    #     self.enableAllButtons()
    #     self.updateEnabledButtons()
    #     self.sw_pbar.hide()

    def present_snr_results(self, start=0, end=None):
        try:
            if cfg.data.is_aligned():
                logger.info('Alignment seems successful')
            else:
                self.warn('Something Went Wrong')
            logger.info('Calculating SNR Diff Values...')
            diff_avg = cfg.data.snr_average() - cfg.data.snr_prev_average()
            delta_list = cfg.data.delta_snr_list()[start:end]
            no_chg = [i for i, x in enumerate(delta_list) if x == 0]
            pos = [i for i, x in enumerate(delta_list) if x > 0]
            neg = [i for i, x in enumerate(delta_list) if x < 0]
            self.tell('Re-alignment Results:')
            self.tell('  # Better     (SNR ↑) : %s' % ' '.join(map(str, pos)))
            self.tell('  # Worse      (SNR ↓) : %s' % ' '.join(map(str, neg)))
            self.tell('  # No Change  (SNR =) : %s' % ' '.join(map(str, no_chg)))
            self.tell('  Total Avg. SNR       : %.3f (Prev.: %.3f)' % (cfg.data.snr_average(), cfg.data.snr_prev_average()))
            if abs(diff_avg) < .001:
                self.tell('  Δ AVG. SNR           : <span style="color: #66FF00;"><b>0.000 (NO CHANGE)</b></span>')
            elif diff_avg < 0:
                self.tell('  Δ AVG. SNR           : <span style="color: #a30000;"><b>%.3f (WORSE)</b></span>' % diff_avg)
            else:
                self.tell('  Δ AVG. SNR           : <span style="color: #66FF00;"><b>%.3f (BETTER)</b></span>' % diff_avg)

        except:
            logger.warning('Unable To Present SNR Results')


    def onAlignmentStart(self, scale):
        logger.info('')
        if cfg.event.is_set():
            cfg.event.clear()
        t0 = time.time()
        dt = datetime.datetime.now()

        cfg.project_tab.tn_ms0.set_no_image()
        cfg.project_tab.tn_ms1.set_no_image()
        cfg.project_tab.tn_ms2.set_no_image()
        cfg.project_tab.tn_ms3.set_no_image()

        cfg.project_tab.matches_tn0.set_no_image()
        cfg.project_tab.matches_tn1.set_no_image()
        cfg.project_tab.matches_tn2.set_no_image()
        cfg.project_tab.matches_tn3.set_no_image()

        logger_log = os.path.join(cfg.data.dest(), 'logs', 'logger.log')
        mp_log = os.path.join(cfg.data.dest(), 'logs', 'multiprocessing.log')
        manual_log = os.path.join(cfg.data.dest(), 'logs', 'manual_align.log')
        swim_log = os.path.join(cfg.data.dest(), 'logs', 'swim.log')
        thumbs_log = os.path.join(cfg.data.dest(), 'logs', 'thumbnails.log')
        # open(logger_log, 'a+').close()
        # open(mp_log, 'a+').close()
        # open(manual_log, 'a+').close()
        # open(thumbs_log, 'a+').close()
        with open(logger_log, 'a+') as f:
            f.write('\n\n====================== NEW RUN ' + str(dt) + ' ======================\n\n')
        with open(manual_log, 'a+') as f:
            f.write('\n\n====================== NEW RUN ' + str(dt) + ' ======================\n\n')
        with open(mp_log, 'a+') as f:
            f.write('\n\n====================== NEW RUN ' + str(dt) + ' ======================\n\n')
        with open(swim_log, 'a+') as f:
            f.write('\n\n====================== NEW RUN ' + str(dt) + ' ======================\n\n')
        # time point 5: = 0.0032761096954345703
        self.stopPlaybackTimer()
        self._disableGlobTabs()
        # self.pbarLabel.setText('Task (0/%d)...' % cfg.nProcessSteps)
        # if not cfg.ignore_pbar:
        #     self.showZeroedPbar()
        if cfg.data.is_aligned(s=scale):
            cfg.data.set_previous_results()
        self._autosave(silently=True)
        self._changeScaleCombo.setEnabled(False)
        check_project_status()
        self.setNoPbarMessage(True)



    def onAlignmentEnd(self, start, end):
        logger.info('Running Post-Alignment Tasks...')
        # self.alignmentFinished.emit()
        t0 = time.time()
        try:
            if self._isProjectTab():
                self.setNoPbarMessage(False)
                self.updateEnabledButtons()
                self.updateCorrSignalsDrawer()
                self.setTargKargPixmaps()
                self.present_snr_results(start=start, end=end)
                self.dataUpdateWidgets()
                self._showSNRcheck()
                cfg.project_tab.updateTimingsWidget()
                cfg.project_tab.updateTreeWidget() #0603-
                cfg.pt._bbToggle.setChecked(cfg.data.has_bb())
                cfg.pt.updateDetailsPanel()

        except:
            print_exception()
        finally:
            self._autosave()
            if cfg.event.is_set():
                cfg.event.clear()
            self._working = False
            self._changeScaleCombo.setEnabled(True)
            self.hidePbar()
            self.enableAllTabs()
            if self._isProjectTab():
                if cfg.project_tab._tabs.currentIndex() == 4:
                    cfg.project_tab.snr_plot.initSnrPlot()
                if self.dw_snr.isVisible():
                    cfg.project_tab.dSnr_plot.initSnrPlot()

            t9 = time.time()
            dt = t9 - t0
            logger.info(f'  Elapsed Time         : {dt:.2f}s')
            self.tell(f'  Elapsed Time         : {dt:.2f}s')


    def alignAllScales(self):
        if self._isProjectTab():
            scales = cfg.data.scales()
            scales.reverse()
            alignThese = []
            for s in scales:
                if not cfg.data.is_aligned(s=s):
                    alignThese.append(s)
                #     alignThese.app

            self.tell(f'# Scales Unaligned: {len(alignThese)}. Aligning now...')
            ntasks = 4 * len(alignThese)
            self.showZeroedPbar(set_n_processes=ntasks)
            for s in alignThese:
                cfg.data.scale_key = s
                # cfg.project_tab.initNeuroglancer()
                cfg.project_tab.refreshTab()
                self.dataUpdateWidgets()
                self.alignAll(set_pbar=False)

            self.onAlignmentEnd()

    def alignRange(self):
        cfg.ignore_pbar = False
        start = int(self.startRangeInput.text())
        end = int(self.endRangeInput.text()) + 1
        if cfg.pt._toggleAutogenerate.isChecked():
            self.showZeroedPbar(set_n_processes=4)
        else:
            self.showZeroedPbar(set_n_processes=2)
        self.hidePbar()
        cfg.nProcessDone = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.tell('Re-aligning Sections #%d through #%d (%s)...' %
                  (start, end, cfg.data.scale_pretty()))
        self.align(
            scale=cfg.data.scale_key,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            # stageit=False,
            stageit=False,
        )

        self.onAlignmentEnd(start=start, end=end)
        cfg.project_tab.initNeuroglancer()

    def alignForward(self):
        cfg.ignore_pbar = False
        start = cfg.data.zpos
        end = cfg.data.count
        if cfg.pt._toggleAutogenerate.isChecked():
            self.showZeroedPbar(set_n_processes=4)
        else:
            self.showZeroedPbar(set_n_processes=2)
        self.hidePbar()
        cfg.nProcessDone = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.tell('Re-aligning Sections #%d through #%d (%s)...' %
                  (start, end, cfg.data.scale_pretty()))
        self.align(
            scale=cfg.data.scale_key,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            # stageit=False,
            stageit=False,
        )
        self.onAlignmentEnd(start=start, end=end)
        cfg.project_tab.initNeuroglancer()

    # def alignOne(self, stageit=False):
    def alignOne(self, quick_swim=False):
        logger.critical('Aligning One...')
        self.tell('Re-aligning Section #%d (%s)...' %
                  (cfg.data.zpos, cfg.data.scale_pretty()))
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        cfg.nProcessDone = 0
        cfg.nProcessSteps = 1
        if quick_swim:
            cfg.ignore_pbar = True
        self.align(
            scale=cfg.data.scale_key,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            # stageit=stageit,
            stageit=False,
            align_one=True,
            swim_only=True,
        )
        self._working = False


        # 0614-
        if quick_swim:
            cfg.ignore_pbar = False
            self.updateCorrSignalsDrawer()
            self.setTargKargPixmaps()
            self.updateEnabledButtons()
            self.enableAllTabs()
        else:
            self.onAlignmentEnd(start=start, end=end)  # 0601+ why was this uncommented?
            cfg.project_tab.initNeuroglancer()

        self.tell('Section #%d Alignment Complete' % start)
        self.tell('SNR Before: %.3f  SNR After: %.3f' %
                  (cfg.data.snr_prev(l=start), cfg.data.snr(l=start)))

    def alignGenerateOne(self):
        cfg.ignore_pbar = True
        logger.critical('Realigning Manually...')
        self.tell('Re-aligning Section #%d (%s)...' %
                  (cfg.data.zpos, cfg.data.scale_pretty()))
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        cfg.nProcessDone = 0
        cfg.nProcessSteps = 4
        self.setPbarMax(4)
        self.align(
            scale=cfg.data.scale_key,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            stageit=False,
            align_one=True,
            swim_only=False
        )
        self.onAlignmentEnd(start=start, end=end)
        cfg.project_tab.initNeuroglancer()
        self.tell('Section #%d Alignment Complete' % start)
        self.tell('SNR Before: %.3f  SNR After: %.3f' %
                  (cfg.data.snr_prev(l=start), cfg.data.snr(l=start)))
        cfg.ignore_pbar = False


    def alignAll(self, set_pbar=True, force=False, ignore_bb=False, use_gui=True):
        caller = inspect.stack()[1].function
        if caller == 'main':
            set_pbar = True


        if (not force) and (not self._isProjectTab()):
            return
        scale = cfg.data.scale_key
        if not self.verify_alignment_readiness():
            self.warn('%s is not a valid target for alignment!' % cfg.data.scale_pretty(scale))
            return
        self.tell('Aligning All Sections (%s)...' % cfg.data.scale_pretty())
        # if set_pbar:
        #     logger.critical('set_pbar >>>>')
        #     cfg.ignore_pbar = False
        #     if cfg.pt._toggleAutogenerate.isChecked():
        #         # cfg.nProcessSteps = 5
        #         self.showZeroedPbar(set_n_processes=4)
        #     else:
        #         # cfg.nProcessSteps = 3
        #         self.showZeroedPbar(set_n_processes=2)
        #     self.hidePbar()

        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        cfg.data.set_has_bb(cfg.data.use_bb())  # Critical, also see regenerate
        self.align(
            scale=cfg.data.scale_key,
            start=0,
            end=None,
            renew_od=True,
            reallocate_zarr=True,
            # stageit=stageit,
            stageit=False,
            ignore_bb=ignore_bb,
            use_gui=use_gui
        )
        # if not cfg.CancelProcesses:
        #     self.present_snr_results()

        self.onAlignmentEnd(start=0, end=None)
        cfg.project_tab.initNeuroglancer()



    def align(self, scale, start, end, renew_od, reallocate_zarr, stageit, align_one=False, swim_only=False, ignore_bb=False, show_pbar=True, use_gui=True):
        # Todo change printout based upon alignment scope, i.e. for single layer
        # caller = inspect.stack()[1].function
        # if caller in ('alignGenerateOne','alignOne'):
        #     ALIGN_ONE = True
        logger.info(f'Aligning start:{start} -> end: {end}, {cfg.data.scale_pretty(scale)}...')
        self.tell(f'Alignment start:{start} -> end: {end}, {cfg.data.scale_pretty(scale)}...')

        self.shutdownNeuroglancer()

        # cafms_before = cfg.data.cafm_list()

        if end == None:
            end = len(cfg.data)

        self.onAlignmentStart(scale=scale)
        self.tell("%s Affines (%s)..." % (('Initializing', 'Refining')[cfg.data.isRefinement()], cfg.data.scale_pretty(s=scale)))

        if not ignore_bb:
            cfg.data.set_use_bounding_rect(cfg.pt._bbToggle.isChecked())

        # if cfg.ignore_pbar:
        #     self.showZeroedPbar(set_n_processes=False)
        #     self.setPbarText('Computing Affine...')
        #     self.hidePbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=ComputeAffines(scale, path=None, start=start, end=end, swim_only=swim_only, renew_od=renew_od,
                                      reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui, dm=cfg.data))
                self.threadpool.start(self.worker)
            else:
                ComputeAffines(scale, path=None, start=start, end=end, swim_only=swim_only, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=use_gui, dm=cfg.data)
        except:
            print_exception();
            self.err('An Exception Was Raised During Alignment.')



        # cfg.data.get_iter()



        # cafms_after = cfg.data.cafm_list()
        # indexes = []
        # for i,(b,a) in enumerate(zip(cafms_before, cafms_after)):
        #     if b != a :
        #         indexes.append(i)
        # if len(indexes) > 0:
        #     # self.tell(f"<span style='color: #FFFF66;'><b>New Cumulative for Sections: {', '.join(map(str, indexes))}</b></span>")
        #     self.tell(f"New Cumulative for Sections: {', '.join(map(str, indexes))}")

        self.tell('<span style="color: #FFFF66;"><b>**** Process Group Complete ****</b></span><br>')

        # else:     logger.info('Affine Computation Finished')

        # if cfg.ignore_pbar:
        #     cfg.nProcessDone +=1
        #     self.updatePbar()
        #     self.setPbarText('Scaling Correlation Signal Thumbnails...')
        # try:
        #     if cfg.USE_EXTRA_THREADING:
        #         self.worker = BackgroundWorker(fn=cfg.thumb.reduce_signals(start=start, end=end))
        #         self.threadpool.start(self.worker)
        #     else: cfg.thumb.reduce_signals(start=start, end=end)
        # except: print_exception(); self.warn('There Was a Problem Generating Corr Spot Thumbnails')
        # # else:   logger.info('Correlation Signal Thumbnail Generation Finished')

        # if cfg.project_tab._tabs.currentIndex() == 1:
        #     cfg.project_tab.project_table.initTableData()
        #
        # if not swim_only:
        #     if cfg.pt._toggleAutogenerate.isChecked():
        #
        #         if cfg.ignore_pbar:
        #             cfg.nProcessDone += 1
        #             self.updatePbar()
        #             self.setPbarText('Generating Alignment...')
        #
        #         try:
        #             if cfg.USE_EXTRA_THREADING:
        #                 self.worker = BackgroundWorker(fn=GenerateAligned(
        #                     scale_key, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit))
        #                 self.threadpool.start(self.worker)
        #             else: GenerateAligned(scale_key, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit)
        #         except:
        #             print_exception()
        #         finally:
        #             logger.info('Generate Alignment Finished')
        #
        #         if cfg.ignore_pbar:
        #             cfg.nProcessDone += 1
        #             self.updatePbar()
        #             self.setPbarText('Generating Aligned Thumbnail...')
        #
        #         try:
        #             if cfg.USE_EXTRA_THREADING:
        #                 self.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(start=start, end=end))
        #                 self.threadpool.start(self.worker)
        #             else: cfg.thumb.reduce_aligned(start=start, end=end)
        #         except:
        #             print_exception()
        #         finally:
        #             logger.info('Generate Aligned Thumbnails Finished')
        #
        #         if cfg.ignore_pbar:
        #             cfg.nProcessDone += 1
        #             self.updatePbar()
        #             self.setPbarText('Aligning')

        self.pbarLabel.setText('')
        self.hidePbar()
        cfg.nProcessDone = 0
        cfg.nProcessSteps = 0

    def rescale(self):
        if self._isProjectTab():

            msg = 'Warning: Rescaling clears project data.\nProgress will be lost. Continue?'
            dlg = AskContinueDialog(title='Confirm Rescale', msg=msg)
            if dlg.exec():
                recipe_dialog = NewConfigureProjectDialog(parent=self)
                if recipe_dialog.exec():

                    # self.stopNgServer()  # 0202-
                    self._disableGlobTabs()

                    self.tell('Clobbering the Project Directory %s...')
                    try:
                        delete_recursive(dir=cfg.data.dest(), keep_core_dirs=True)
                    except:
                        print_exception()
                        self.err('The Above Error Was Encountered During Clobber of the Project Directory')
                    else:
                        self.hud.done()

                    try:
                        # self.pbarLabel.setText('')
                        # self.autoscale_(make_thumbnails=False)
                        autoscale(dm=cfg.data, make_thumbnails=False)
                    except:
                        print_exception()
                    else:
                        self._autosave()
                        self.tell('Rescaling Successful')
                    finally:
                        self.onStartProject()

    # def generate_multiscale_zarr(self):
    #     pass

    def export(self):
        if self._working == True:
            self.warn('Another Process is Already Running')
            return
        logger.critical('Exporting To Zarr...')
        self.tell('Exporting...')
        self.tell('Generating Neuroglancer-Compatible Zarr...')
        src = os.path.abspath(cfg.data['data']['destination_path'])
        out = os.path.abspath(os.path.join(src, 'img_aligned.zarr'))
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=GenerateScalesZarr())
                self.threadpool.start(self.worker)
            else:
                GenerateScalesZarr()
        except:
            print_exception()
            logger.error('Zarr Export Encountered an Exception')

        self._callbk_unsavedChanges()
        self.tell('Process Finished')

    @Slot()
    def clear_skips(self):
        if cfg.data.anySkips():
            msg = 'Verify reset the reject list.'
            reply = QMessageBox.question(self, 'Verify Reset Reject List', msg, QMessageBox.Cancel | QMessageBox.Ok)
            if reply == QMessageBox.Ok:
                self.tell('Resetting Skips...')
                cfg.data.clear_all_skips()
        else:
            self.warn('No Skips To Clear.')

    def enableAllButtons(self):
        self._btn_alignAll.setEnabled(True)
        self._btn_alignOne.setEnabled(True)
        self._btn_alignForward.setEnabled(True)
        self._btn_alignRange.setEnabled(True)
        self._btn_regenerate.setEnabled(True)
        self._scaleDownButton.setEnabled(True)
        self._scaleUpButton.setEnabled(True)
        # self._ctlpanel_applyAllButton.setEnabled(True)
        self._skipCheckbox.setEnabled(True)
        # cfg.pt.sb_whiteningControl.setEnabled(True)
        # cfg.pt._swimWindowControl.setEnabled(True)
        cfg.pt._toggleAutogenerate.setEnabled(True)
        cfg.pt._bbToggle.setEnabled(True)
        cfg.pt._polyBiasCombo.setEnabled(True)
        self._btn_clear_skips.setEnabled(True)
        self.startRangeInput.setEnabled(True)
        self.endRangeInput.setEnabled(True)
        

    
    def updateEnabledButtons(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev s buttons depending on current s.
        (2) Set the enabled/disabled state of the align_all-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        # logger.critical('')
        # self.dataUpdateResults()

        if self._isProjectTab():
            # self._btn_alignAll.setText('Align All Sections - %s' % cfg.data.scale_pretty())
            # self._btn_regenerate.setText('Regenerate All Sections - %s' % cfg.data.scale_pretty())
            self.gb_ctlActions.setTitle('%s Multiprocessing Functions' % cfg.data.scale_pretty())
            # self.alignmentResults.setTitle('%s Data && Results' % cfg.data.scale_pretty())
            # self._btn_alignRange.setText('Regenerate\nAll %s' % cfg.data.scale_pretty())
            self._skipCheckbox.setEnabled(True)
            self._btn_clear_skips.setEnabled(True)

            self._changeScaleCombo.setEnabled(True)

        else:
            self._skipCheckbox.setEnabled(False)
            self._btn_clear_skips.setEnabled(False)

            # self._ctlpanel_applyAllButton.setEnabled(False)

        if self._isProjectTab():
            # if cfg.data.is_aligned_and_generated(): #0202-

            if cfg.data.is_aligned():
                # self._btn_alignAll.setText('Re-Align All Sections (%s)' % cfg.data.scale_pretty())
                # self._btn_alignAll.setText('Align All')
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(True)
                self._btn_alignForward.setEnabled(True)
                self._btn_alignRange.setEnabled(True)
                self._btn_regenerate.setEnabled(True)
                self.startRangeInput.setEnabled(True)
                self.endRangeInput.setEnabled(True)

            elif cfg.data.is_alignable():
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(False)
                self._btn_alignForward.setEnabled(False)
                self._btn_alignRange.setEnabled(False)
                self._btn_regenerate.setEnabled(False)
                self.startRangeInput.setEnabled(False)
                self.endRangeInput.setEnabled(False)
            else:
                self._btn_alignAll.setEnabled(False)
                self._btn_alignOne.setEnabled(False)
                self._btn_alignForward.setEnabled(False)
                self._btn_alignRange.setEnabled(False)
                self._btn_regenerate.setEnabled(False)
                self.startRangeInput.setEnabled(False)
                self.endRangeInput.setEnabled(False)
            if len(cfg.data.scales()) == 1:
                self._scaleUpButton.setEnabled(False)
                self._scaleDownButton.setEnabled(False)
                if cfg.data.is_aligned():
                    self._btn_alignAll.setEnabled(True)
                    self._btn_alignOne.setEnabled(True)
                    self._btn_alignForward.setEnabled(True)
                    self._btn_alignRange.setEnabled(True)
                    self._btn_regenerate.setEnabled(True)
                    self.startRangeInput.setEnabled(True)
                    self.endRangeInput.setEnabled(True)
                else:
                    self._btn_alignAll.setEnabled(True)
                    self._btn_alignOne.setEnabled(False)
                    self._btn_alignForward.setEnabled(False)
                    self._btn_alignRange.setEnabled(False)
                    self._btn_regenerate.setEnabled(False)
                    self.startRangeInput.setEnabled(False)
                    self.endRangeInput.setEnabled(False)
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
            self._btn_alignRange.setEnabled(False)
            self._btn_regenerate.setEnabled(False)
            self.startRangeInput.setEnabled(False)
            self.endRangeInput.setEnabled(False)


    def layer_left(self):
        if self._isProjectTab():
            requested = cfg.data.zpos - 1
            logger.info(f'requested: {requested}')
            if requested >= 0:
                cfg.mw.setZpos(requested)

    def layer_right(self):
        if self._isProjectTab():
            requested = cfg.data.zpos + 1
            if requested < len(cfg.data):
                cfg.mw.setZpos(requested)

    def scale_down(self) -> None:
        '''Callback function for the Previous Scale button.'''
        logger.info('')
        if not self._working:
            if self._scaleDownButton.isEnabled():
                self._changeScaleCombo.setCurrentIndex(self._changeScaleCombo.currentIndex() + 1)  # Changes Scale

    def scale_up(self) -> None:
        '''Callback function for the Next Scale button.'''
        logger.info('')
        if not self._working:
            if self._scaleUpButton.isEnabled():
                self._changeScaleCombo.setCurrentIndex(self._changeScaleCombo.currentIndex() - 1)  # Changes Scale
                if not cfg.data.is_alignable():
                    self.warn('Lower scales have not been aligned yet')

    @Slot()
    def set_status(self, msg: str) -> None:
        self.statusBar.showMessage(msg)
        # QApplication.processEvents()
        # pass

    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')

    def apply_default_style(self):
        # self.main_stylesheet = os.path.abspath('src/style/default.qss')
        self.main_stylesheet = os.path.abspath('src/style/newstyle.qss')
        with open(self.main_stylesheet, 'r') as f:
            style = f.read()
        self.setStyleSheet(style)

    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')

    # def dataUpdateResults(self):
    #     caller = inspect.stack()[1].function
    #     logger.critical(f'>>>> dataUpdateResults [{caller}] >>>>')
    #
    #     if cfg.data:
    #         # self.results0 = QLabel('...Image Dimensions')
    #         # self.results1 = QLabel('...# Images')
    #         # self.results2 = QLabel('...SNR (average)')
    #         # self.results3 = QLabel('...Worst 5 SNR')
    #
    #         self.results0 = QLabel()  # Image dimensions
    #         self.results1 = QLabel()  # # of images
    #         self.results2 = QLabel()  # SNR average
    #
    #         # self.fl_main_results = QFormLayout()
    #         # self.fl_main_results.setContentsMargins(2,2,2,2)
    #         # self.fl_main_results.setVerticalSpacing(2)
    #         # self.fl_main_results.addRow('Source Dimensions', self.results0)
    #         # self.fl_main_results.addRow('# Images', self.results1)
    #         # self.fl_main_results.addRow('SNR (average)', self.results2)
    #         # # self.fl_main_results.addRow('Lowest 10 SNR', self.results3)
    #
    #         siz = cfg.data.image_size()
    #         try:
    #             self.results0.setText("%dx%dpx" % (siz[0], siz[1]))
    #         except:
    #             self.results0.setText("N/A")
    #         try:
    #             self.results1.setText("%d" % len(cfg.data))
    #         except:
    #             self.results1.setText("N/A")
    #         try:
    #             self.results2.setText("%.2f" % cfg.data.snr_average())
    #         except:
    #             self.results2.setText("N/A")
    #
    #         # w = QWidget()
    #         # w.setLayout(self.fl_main_results)
    #         # self.sa_details.setWidget(w)

    def everySecond(self):
        if self._isProjectTab():
            if cfg.pt._tabs.currentIndex() in (0,1):
                logger.info('')
                if not self._working:
                    self.dataUpdateWidgets()



    # def dataUpdateWidgets(self, ng_layer=None, silently=False) -> None:
    @Slot(name='dataUpdateWidgets-slot-name')
    def dataUpdateWidgets(self) -> None:
        '''Reads Project Data to Update MainWindow.'''
        # logger.info('')

        # caller = inspect.stack()[1].function
        # if DEV:
        #     logger.info(f'{caller_name()}')
        # logger.critical(f'dataUpdateWidgets [caller: {caller}] [sender: {self.sender()}]...')
        # if getData('state,blink'):
        #     return

        if self._working:
            logger.warning("Busy working! Not going to update the interface rn.")

        if not self._isProjectTab():
            logger.warning('No Current Project Tab!')
            return

        # cfg.project_tab._overlayLab.hide()
        # logger.info('')

        # logger.info(f">>>> dataUpdateWidgets [{caller}] zpos={cfg.data.zpos} requested={ng_layer} >>>>")
        # self.count_calls.setdefault('dupw', {})
        # self.count_calls[].setdefault(caller, {})
        # self.count_calls['dupw'][caller].setdefault('total_count',0)
        # self.count_calls['dupw'][caller].setdefault('same_count',0)
        # self.count_calls['dupw'][caller].setdefault('diff_count',0)
        # self.count_calls['dupw'][caller].setdefault('none_count',0)
        # self.count_calls['dupw'][caller]['total_count'] += 1
        # if ng_layer == None:
        #     self.count_calls['dupw'][caller]['none_count'] += 1
        # elif cfg.data.zpos == ng_layer:
        #     self.count_calls['dupw'][caller]['same_count'] += 1
        # elif cfg.data.zpos != ng_layer:
        #     self.count_calls['dupw'][caller]['diff_count'] += 1


        # timer.report() #0

        if self._isProjectTab():
            cfg.CancelProcesses = False #0720+ probably a necessary precaution until something better


            # if 'viewer_em' in str(self.sender()):
            #     if not silently:
            #         # if cfg.pt.ms_widget.isVisible():
            #         #     self.updateCorrSignalsDrawer()
            #         if self.uiUpdateTimer.isActive():
            #             logger.info('Delaying UI Update...')
            #             return
            #         else:
            #             logger.critical('Updating UI...')
            #             self.uiUpdateTimer.start()
            #             # QTimer.singleShot(300, lambda: logger.critical('\n\nsingleShot dataUpdateWidget...\n'))
            #             # QTimer.singleShot(300, self.dataUpdateWidgets)

            #CriticalMechanism
            if 'viewer_em.WorkerSignals' in str(self.sender()):
                timerActive = self.uiUpdateTimer.isActive()
                # logger.critical(f"uiUpdateTimer active? {timerActive}")
                if self.uiUpdateTimer.isActive():
                    # logger.info('Delaying UI Update [viewer_em.WorkerSignals]...')
                    return
                else:
                    self.uiUpdateTimer.start()
                    logger.info('Updating UI on timeout...')

            # cfg.project_tab._overlayRect.hide()
            cfg.project_tab._overlayLab.hide()
            cfg.project_tab.tn_tra_overlay.hide()

            cur = cfg.data.zpos

            try:    self._jumpToLineedit.setText(str(cur))
            except: logger.warning('Current Layer Widget Failed to Update')
            try:    self._sectionSlider.setValue(cur)
            except: logger.warning('Section Slider Widget Failed to Update')
            try:    self._skipCheckbox.setChecked(not cfg.data.skipped())
            except: logger.warning('Skip Toggle Widget Failed to Update')
            self._btn_prevSection.setEnabled(cur > 0)
            self._btn_nextSection.setEnabled(cur < len(cfg.data) - 1)

            # try:
            #     delay_list = ('z-index-left-button', 'z-index-right-button', 'z-index-slider')
            #     # if ('viewer_em' in str(self.sender()) or (self.sender().objectName() in delay_list)):
            #     if ('viewer_em' in str(self.sender()) or (self.sender().objectName() in delay_list)):
            #         if self.uiUpdateTimer.isActive():
            #             logger.info('Delaying UI Update...')
            #             self.uiUpdateTimer.start()
            #             return
            #         else:
            #             logger.critical('Updating UI...')
            #             self.uiUpdateTimer.start()
            # except:
            #     print_exception()


            # if self._working == True:
            #     logger.warning(f"Can't update GUI now - working (caller: {caller})...")
            #     self.warn("Can't update GUI now - working...")
            #     return

            # if isinstance(ng_layer, int):
            #     if type(ng_layer) != bool:
            #         try:
            #             if 0 <= ng_layer < len(cfg.data):
            #                 logger.info(f'  Setting Z-index: {ng_layer} current Z-index:{cfg.data.zpos} [{caller}]')
            #                 cfg.data.zpos = ng_layer
            #                 # self._sectionSlider.setValue(ng_layer)
            #         except:
            #             print_exception()

            if self.dw_thumbs.isVisible():
                if cfg.data.skipped():
                    # cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
                    txt = '\n'.join(textwrap.wrap('EXCLUDED: %s' % cfg.data.name_base(), width=35))
                    cfg.project_tab._overlayLab.setText(txt)
                    cfg.project_tab._overlayLab.show()
                    cfg.project_tab.tn_tra_overlay.show()
                    cfg.project_tab.tn_ref.hide()
                    # cfg.project_tab._overlayRect.show()
                else:
                    cfg.project_tab.tn_ref.show()


            if self.dw_matches.isVisible():
                self.updateCorrSignalsDrawer()
                self.setTargKargPixmaps()


            if self.dw_thumbs.isVisible():
                try:
                    assert os.path.exists(cfg.data.thumbnail_ref())
                    # cfg.pt.tn_ref.selectPixmap(path=cfg.data.thumbnail_ref())
                    cfg.pt.tn_ref.set_data(path=cfg.data.thumbnail_ref())
                    assert os.path.exists(cfg.data.thumbnail_tra())
                    # cfg.pt.tn_tra.selectPixmap(path=cfg.data.thumbnail_tra())
                    cfg.pt.tn_tra.set_data(path=cfg.data.thumbnail_tra())

                except:
                    cfg.pt.tn_ref.set_no_image()
                    cfg.pt.tn_tra.set_no_image()
                    print_exception()

            cfg.pt.lab_filename.setText(f"[{cfg.data.zpos}] Name: {cfg.data.filename_basename()} - {cfg.data.scale_pretty()}")

            if self.dw_thumbs.isVisible():
                cfg.pt.tn_tra_lab.setText(f'Transforming Section (Thumbnail)\n'
                                          f'[{cfg.data.zpos}] {cfg.data.filename_basename()}')
                try:
                    cfg.pt.tn_ref_lab.setText(f'Reference Section (Thumbnail)\n'
                                              f'[{cfg.data.get_ref_index()}] {cfg.data.reference_basename()}')
                except:
                    cfg.pt.tn_ref_lab.setText(f'Reference Section (Thumbnail)')

            if cfg.pt._tabs.currentIndex() == 1:
                # cl_tra
                cfg.pt.cl_tra.setText(f'[{cfg.data.zpos}] {cfg.data.filename_basename()} (Transforming)')
                if cfg.data.skipped():
                    cfg.pt.cl_tra.setText(f'[{cfg.data.zpos}] {cfg.data.filename_basename()} (Transforming)')
                    cfg.pt.cl_ref.setText(f'--')
                else:
                    try:
                        cfg.pt.cl_ref.setText(f'[{cfg.data.get_ref_index()}] {cfg.data.reference_basename()} (Reference)')
                    except:
                        cfg.pt.cl_ref.setText(f'Null (Reference)')




            img_siz = cfg.data.image_size()
            self.statusBar.showMessage(cfg.data.scale_pretty() + ', ' +
                                       'x'.join(map(str, img_siz)) + ', ' +
                                       cfg.data.name_base())

            if cfg.data['state']['current_tab'] == 1:
                cfg.project_tab.dataUpdateMA()
                if not cfg.data.cafm_hash_comports() and cfg.data.is_aligned_and_generated():
                    cfg.pt.warning_cafm.show()
                else:
                    cfg.pt.warning_cafm.hide()

            if self.notes.isVisible():
                self.updateNotes()

            #Todo come back to how to make this work without it getting stuck in a loop
            # if cfg.project_tab._tabs.currentIndex() == 2:
            #     cfg.project_tab.project_table.table.selectRow(cur)

            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.treeview_model.jumpToLayer()

            if cfg.project_tab._tabs.currentIndex() == 4:
                cfg.project_tab.snr_plot.updateLayerLinePos()

            if self.dw_snr.isVisible():
                cfg.project_tab.dSnr_plot.updateLayerLinePos()


            br = '&nbsp;'
            a = """<span style='color: #ffe135;'>"""
            b = """</span>"""
            nl = '<br>'

            if cfg.pt.secDetails_w.isVisible():
                cfg.pt.secName.setText(cfg.data.filename_basename())
                ref = cfg.data.reference_basename()
                if ref == '':
                    ref = 'None'
                cfg.pt.secReference.setText(ref)
                cfg.pt.secAlignmentMethod.setText(cfg.data.method_pretty())
                if cfg.data.snr() == 0:
                    cfg.pt.secSNR.setText('--')
                else:
                    cfg.pt.secSNR.setText(
                        '<span style="color: #a30000;"><b>%.2f</b></span><span>&nbsp;&nbsp;(%s)</span>' % (
                        cfg.data.snr(), ",  ".join(["%.2f" % x for x in cfg.data.snr_components()])))

            if cfg.pt._tabs.currentIndex() == 1:
                cfg.pt.secAffine.setText(make_affine_widget_HTML(cfg.data.afm(), cfg.data.cafm()))

            if cfg.project_tab.detailsSNR.isVisible():
                if (cfg.data.zpos == 0) or cfg.data.skipped() or cfg.data.snr() == 0:
                    cfg.project_tab.detailsSNR.setText(
                        f"Avg. SNR{br * 2}: N/A{nl}"
                        f"Prev.{br}SNR{br}: N/A{nl}"
                        f"Components{nl}"
                        f"Top,Left{br * 2}: N/A{nl}"
                        f"Top,Right{br}: N/A{nl}"
                        f"Btm,Left{br * 2}: N/A{nl}"
                        f"Btm,Right{br}: N/A"
                    )
                else:
                    try:
                        components = cfg.data.snr_components()
                        str0 = ('%.3f' % cfg.data.snr()).rjust(9)
                        str1 = ('%.3f' % cfg.data.snr_prev()).rjust(9)
                        if cfg.data.method() in ('grid-default', 'grid-custom'):
                            q0 = ('%.3f' % components[0]).rjust(9)
                            q1 = ('%.3f' % components[1]).rjust(9)
                            q2 = ('%.3f' % components[2]).rjust(9)
                            q3 = ('%.3f' % components[3]).rjust(9)
                            cfg.project_tab.detailsSNR.setText(
                                f"Avg. SNR{br * 2}:{a}{str0}{b}{nl}"
                                f"Prev.{br}SNR{br}:{str1}{nl}"
                                f"Components{nl}"
                                f"Top,Left{br * 2}:{q0}{nl}"
                                f"Top,Right{br}:{q1}{nl}"
                                f"Btm,Left{br * 2}:{q2}{nl}"
                                f"Btm,Right{br}:{q3}"
                            )
                        elif cfg.data.method() in ('manual-hint', 'manual-strict'):
                            txt = f"Avg. SNR{br * 2}:{a}{str0}{b}{nl}" \
                                  f"Prev. SNR{br}:{str1}{nl}" \
                                  f"Components"
                            for i in range(len(components)):
                                txt += f'{nl}%d:{br * 10}%.3f' % (i, components[i])

                            cfg.project_tab.detailsSNR.setText(txt)
                    except:
                        print_exception()

            # self._btn_alignOne.setText('Re-Align Section #%d' %cfg.data.zpos)
            tip = f"""Compute alignment and generate new image for section #{cfg.data.zpos} only"""
            self._btn_alignOne.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
            tip = f"""Compute alignment and generate new images for sections in range #{cfg.data.zpos} to #{cfg.data.count}"""
            self._btn_alignForward.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        # timer.stop() #7
        # logger.info(f'<<<< dataUpdateWidgets [{caller}] zpos={cfg.data.zpos} <<<<')

        self.setFocus()


    def updateNotes(self):
        # caller = inspect.stack()[1].function
        # logger.info('')
        if self.notes.isVisible():
            self.notes.clear()
            if self._isProjectTab():
                self.notes.setPlaceholderText('Enter notes about %s here...'
                                              % cfg.data.base_image_name(s=cfg.data.scale_key, l=cfg.data.zpos))
                if cfg.data.notes(s=cfg.data.scale_key, l=cfg.data.zpos):
                    self.notes.setPlainText(cfg.data.notes(s=cfg.data.scale_key, l=cfg.data.zpos))
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
        if s == None: s = cfg.data.scale_key
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
                path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'history', name)
                with open(path, 'r') as f:
                    project = json.load(f)
                self.projecthistory_model.load(project)
                self.globTabs.addTab(self.historyview_widget, cfg.data.scale_pretty())
        self._setLastTab()

    def rename_historical_alignment(self):
        new_name, ok = QInputDialog.getText(self, 'Rename', 'New Name:')
        if not ok: return
        old_name = self._hstry_listWidget.currentItem().text()
        dir = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'history')
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
        scale_val = cfg.data.scale_val()
        msg = "Are you sure you want to swap your alignment data for Scale %d with '%s'?\n" \
              "Note: You must realign after swapping it in." % (scale_val, name)
        reply = QMessageBox.question(self, 'Message', msg, QMessageBox.Yes, QMessageBox.No)
        if reply != QMessageBox.Yes:
            logger.info("Returning without changing anything.")
            return
        self.tell('Loading %s')
        path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'history', name)
        with open(path, 'r') as f:
            scale = json.load(f)
        self.tell('Swapping Current Scale %d Dictionary with %s' % (scale_val, name))
        cfg.data.set_al_dict(aldict=scale)
        # self.regenerate() #Todo test this under a range of possible scenarios

    def remove_historical_alignment(self):
        logger.info('Loading History File...')
        name = self._hstry_listWidget.currentItem().text()
        if name is None: return
        path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'history', name)
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
        path = os.path.join(cfg.data.dest(), cfg.data.scale_key, 'history', item.text())
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
                self._jumpToLineedit.setValidator(QIntValidator(0, len(cfg.data) - 1))
                self._sectionSlider.setRange(0, len(cfg.data) - 1)
                self._sectionSlider.setValue(cfg.data.zpos)
                self.startRangeInput.setValidator(QIntValidator(0, len(cfg.data) - 1))
                self.endRangeInput.setValidator(QIntValidator(0, len(cfg.data) - 1))
                # if cfg.zarr_tab:
                #     if not cfg.tensor:
                #         logger.warning('No tensor!')
                #         return
                #     self._jumpToLineedit.setValidator(QIntValidator(0, cfg.tensor.shape[0] - 1))
                #     self._jumpToLineedit.setText(str(0))
                #     self._sectionSlider.setRange(0, cfg.tensor.shape[0] - 1)
                #     self._sectionSlider.setValue(0)
                self.update()
            else:
                self._jumpToLineedit.clear()
                self._sectionSlider.setValue(0)
                self._sectionSlider.setRange(0, 0)
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

    # @Slot()
    # def jump_to_manual(self, requested) -> None:
    #     logger.info(f'requested: {requested}')
    #     if self._isProjectTab():
    #         if requested in range(len(cfg.data)):
    #             self.setZpos(requested)
    #             cfg.pt._tabs.setCurrentIndex(1)
    #         else:
    #             logger.warning('Requested layer is not a valid layer')

    @Slot()
    def jump_to_layer(self) -> None:
        '''Connected to _jumpToLineedit. Calls jump_to_slider directly.'''
        # logger.info('')
        if self._isProjectTab():
            requested = int(self._jumpToLineedit.text())
            if requested in range(len(cfg.data)):
                self.setZpos(requested)
                cfg.project_tab.project_table.table.selectRow(requested)
                self._sectionSlider.setValue(requested)
                # if cfg.pt.ms_widget.isVisible():     #0601+ untried
                #     self.updateCorrSignalsDrawer()
                # self.dataUpdateWidgets() #0601+

    def jump_to_slider(self):
        if self._isProjectTab():
            caller = inspect.stack()[1].function
            if caller == 'main':
                #0601 this seems to work as intended with no time lag
                # if caller in ('dataUpdateWidgets'):
                #     return
                logger.info('')
                # if caller in ('main', 'onTimer','jump'):
                requested = self._sectionSlider.value()
                if self._isProjectTab():
                    logger.info('Jumping To Section #%d' % requested)
                    self.setZpos(requested)
                try:
                    self._jumpToLineedit.setText(str(requested))
                except:
                    logger.warning('Current Section Widget Failed to Update')
                    print_exception()

                # logger.critical('<<<< jump_to_slider <<<<')

    @Slot()
    def reload_scales_combobox(self) -> None:
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        if self._isProjectTab():
            # logger.info('Reloading Scale Combobox (caller: %s)' % caller)
            self._scales_combobox_switch = 0
            self._changeScaleCombo.clear()
            # def pretty_scales():
                # lst = []
                # for s in cfg.data.scales():
                #     # siz = cfg.data.image_size(s=s)
                #     lst.append('%d / %d x %dpx' % (cfg.data.scale_val(s=s), *cfg.data.image_size(s=s)))
                # return lst
            lst = ['%d / %d x %dpx' % (cfg.data.scale_val(s=s), *cfg.data.image_size(s=s)) for s in cfg.data.scales()]
            self._changeScaleCombo.addItems(lst)
            self._changeScaleCombo.setCurrentIndex(cfg.data.scales().index(cfg.data.scale_key))
            self._scales_combobox_switch = 1
        else:
            self._changeScaleCombo.clear()

    def fn_scales_combobox(self) -> None:
        caller = inspect.stack()[1].function
        if self._scales_combobox_switch == 0:
            # logger.warning(f"[{caller}] scale_key change blocked by _scales_combobox_switch switch")
            return
        if not self._working:
            if caller in ('main', 'scale_down', 'scale_up'):
                if self._isProjectTab():
                    # logger.info(f'[{caller}]')
                    requested_scale = cfg.data.scales()[self._changeScaleCombo.currentIndex()]
                    cfg.pt.warning_cafm.hide()
                    cfg.pt.project_table.wTable.hide()
                    cfg.pt.project_table.btn_splash_load_table.show()
                    cfg.data.scale_key = requested_scale
                    self.updateEnabledButtons()
                    self.dataUpdateWidgets()
                    self.setControlPanelData()
                    if self.globTabs.currentIndex() == 1:
                        if cfg.pt.secDetails_w.isVisible():
                            cfg.pt.updateDetailsPanel()
                    self._showSNRcheck()
                    cfg.project_tab.refreshTab()
            else:
                logger.warning(f"[{caller}] scale change disallowed")


    def export_afms(self):
        if cfg.project_tab:
            if cfg.data.is_aligned_and_generated():
                file = export_affines_dialog()
                if file == None:
                    self.warn('No Filename - Canceling Export')
                    return
                afm_lst = cfg.data.afm_list()
                with open(file, 'w') as f:
                    for sublist in afm_lst:
                        for item in sublist:
                            f.write(str(item) + ',')
                        f.write('\n')
                self.tell('Exported: %s' % file)
                self.tell(f"AFMs exported successfully to '{file}'")
            else:
                self.warn('Current scale_key is not aligned. Nothing to export.')
        else:
            self.warn('No open projects. Nothing to export.')

    def export_cafms(self):
        file = export_affines_dialog()
        if file == None:
            logger.warning('No Filename - Canceling Export')
            return
        logger.info('Export Filename: %s' % file)
        cafm_lst = cfg.data.cafm_list()
        with open(file, 'w') as f:
            for sublist in cafm_lst:
                for item in sublist:
                    f.write(str(item) + ',')
                f.write('\n')
        self.tell('Exported: %s' % file)
        self.tell('Cumulative AFMs exported successfully.')

    def show_warning(self, title, text):
        QMessageBox.warning(None, title, text)

    # def delete_projects(self):
    #     logger.critical('')
    #     project_file = cfg.selected_file
    #     project = os.path.splitext(project_file)[0]
    #     if not validate_project_selection():
    #         logger.warning('Invalid Project For Deletion (!)\n%s' % project)
    #         return
    #     self.warn("Delete the following project?\nProject: %s" % project)
    #     txt = "Are you sure you want to PERMANENTLY DELETE " \
    #           "the following project?\n\n" \
    #           "Project: %s" % project
    #     msgbox = QMessageBox(QMessageBox.Warning, 'Confirm Delete Project', txt,
    #                       buttons=QMessageBox.Abort | QMessageBox.Yes)
    #     msgbox.setIcon(QMessageBox.Critical)
    #     msgbox.setMaximumWidth(350)
    #     msgbox.setDefaultButton(QMessageBox.Cancel)
    #     reply = msgbox.exec_()
    #     if reply == QMessageBox.Abort:
    #         self.tell('Aborting Delete Project Permanently Instruction...')
    #         logger.warning('Aborting Delete Project Permanently Instruction...')
    #         return
    #     if reply == QMessageBox.Ok:
    #         logger.info('Deleting Project File %s...' % project_file)
    #         self.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)
    #         logger.warning('Executing Delete Project Permanently Instruction...')
    #
    #     logger.critical(f'Deleting Project File: {project_file}...')
    #     self.warn(f'Deleting Project File: {project_file}...')
    #     try:
    #         os.remove(project_file)
    #     except:
    #         print_exception()
    #     else:
    #         self.hud.done()
    #
    #     logger.info('Deleting Project Directory %s...' % project)
    #     self.warn('Deleting Project Directory %s...' % project)
    #     try:
    #
    #         delete_recursive(dir=project)
    #         # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
    #         # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
    #     except:
    #         self.warn('An Error Was Encountered During Deletion of the Project Directory')
    #         print_exception()
    #     else:
    #         self.hud.done()
    #
    #     self.tell('Wrapping up...')
    #     configure_project_paths()
    #     if self.globTabs.currentWidget().__class__.__name__ == 'OpenProject':
    #         logger.critical('Reloading table of projects data...')
    #         try:
    #             self.globTabs.currentWidget().user_projects.set_data()
    #         except:
    #             logger.warning('There was a problem updating the project list')
    #             print_exception()
    #
    #     self.clearSelectionPathText()
    #
    #     self.tell('Deletion Complete!')
    #     logger.info('Deletion Complete')

    def open_project_new(self):

        for i in range(self.globTabs.count()):
            if self.globTabs.widget(i).__class__.__name__ == 'OpenProject':
                self.globTabs.setCurrentIndex(i)
                return
        self.globTabs.addTab(OpenProject(), 'Project Manager')
        self._setLastTab()

    def detachNeuroglancer(self):
        logger.info('')
        if self._isProjectTab() or self._isZarrTab():
            try:
                self.detachedNg = WebPage(url=cfg.emViewer.url())
            except:
                logger.info('Cannot open detached neuroglancer view')

    def openDetatchedZarr(self):
        logger.info('')
        if self._isProjectTab() or self._isZarrTab():
            self.detachedNg = WebPage()
            self.detachedNg.open(url=str(cfg.emViewer.url()))
            self.detachedNg.show()
        else:
            if not ng.server.is_server_running():
                self.warn('Neuroglancer is not running.')

    # def set_nglayout_combo_text(self, layout:str):
    #     self.comboboxNgLayout.setCurrentText(layout)

    def onStartProject(self, mendenhall=False):
        '''Functions that only need to be run once per project
                Do not automatically save, there is nothing to save yet'''
        print(f'\n\n################ Loading Project - %s ################\n' % os.path.basename(cfg.data.dest()))
        self.tell("Loading Project '%s'..." % cfg.data.dest())
        initLogFiles(cfg.data)

        #Critical this might be critical for now
        # cfg.data['data']['current_scale'] = cfg.data.coarsest_scale_key() #0720-
        # if not cfg.data.is_aligned(s=cfg.data['data']['current_scale']):
        #     cfg.data['data']['current_scale'] = cfg.data.coarsest_scale_key()
        # cfg.data.set_defaults()  # 0.5357 -> 0.5438, ~.0081s

        # cfg.project_tab.updateTreeWidget()  #TimeConsuming dt = 0.001 -> dt = 0.535 ~1/2 second
        # cfg.project_tab.updateTreeWidget() #TimeConsuming!! dt = 0.58 - > dt = 1.10
        self.dataUpdateWidgets()  # 0.5878 -> 0.5887 ~.001s
        self.spinbox_fps.setValue(float(cfg.DEFAULT_PLAYBACK_SPEED))
        self.reload_scales_combobox()  # fast
        self.updateEnabledButtons()
        # self.updateMenus()
        self.reload_zpos_slider_and_lineedit()  # fast
        self.setControlPanelData()  # Added 2023-04-23
        self.enableAllTabs()  # fast
        self.setCpanelVisibility(True)
        # cfg.project_tab.initNeuroglancer(init_all=True)
        cfg.project_tab.updateDetailsPanel()
        cfg.project_tab.updateTimingsWidget()
        cfg.project_tab.updateMethodSelectWidget()
        cfg.project_tab.dataUpdateMA() #Important must come after initNeuroglancer
        check_project_status()
        if cfg.mw.dw_snr.isVisible():
            self.dw_snr.setWidget(cfg.pt.dSnr_plot)
            self.dSnr_plot.initSnrPlot()
        QApplication.processEvents()

        # QTimer.singleShot(1000, lambda: self.initNeuroglancer(init_all=True))

        self.hud.done()


    # def delayInitNeuroglancer(self, ms=1000):
    #     QTimer.singleShot(ms, self.initNeuroglancer)

    def saveUserPreferences(self):
        logger.info('Saving User Preferences...')
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        # if self._isProjectTab():
        #     self.settings.setValue("hsplitter_tn_ngSizes", cfg.pt.splitter_ngPlusSideControls.saveState())
        userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
        if not os.path.exists(userpreferencespath):
            open(userpreferencespath, 'a').close()
        try:
            f = open(userpreferencespath, 'w')
            json.dump(cfg.settings, f, indent=2)
            f.close()
        except:
            logger.warning(f'Unable to save current user preferences. Using defaults')

    def resetUserPreferences(self):
        logger.info('')
        userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
        if os.path.exists(userpreferencespath):
            os.remove(userpreferencespath)
        cfg.settings = {}
        update_preferences_model()
        self.saveUserPreferences()

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
        caller = inspect.stack()[1].function
        logger.info(f'/*======== Saving Automatically [{caller}] ========*/')
        if self._isProjectTab():
            self.tell('Saving Project...')
            try:
                self._saveProjectToFile()
                self._unsaved_changes = False
            except:
                self.warn('Unable To Save')
            else:
                self.hud.done()

    def _autosave(self, silently=False):
        caller = inspect.stack()[1].function
        if cfg.data:
            if cfg.AUTOSAVE:
                logger.info(f'/*---- Autosaving [{caller}] ----*/')
                try:
                    self._saveProjectToFile(silently=silently)
                except:
                    self._unsaved_changes = True
                    print_exception()

    def _saveProjectToFile(self, saveas=None, silently=False):
        if cfg.data:
            if self._isProjectTab():
                try:
                    # 0514-
                    # hud_text = self.hud.textedit.toPlainText()
                    # cfg.data['hud'] = hud_text

                    # cfg.data.basefilenames()
                    if saveas is not None:
                        cfg.data.set_destination(saveas)
                    data_cp = copy.deepcopy(cfg.data)
                    # data_cp.make_paths_relative(start=cfg.data.dest())
                    data_cp_json = data_cp.to_dict()
                    if not silently:
                        logger.info('---- SAVING DATA TO PROJECT FILE ----')
                    jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
                    proj_json = jde.encode(data_cp_json)
                    name = cfg.data.dest()
                    if not name.endswith('.swiftir'):
                        name += ".swiftir"
                    logger.info('Save Name: %s' % name)
                    with open(name, 'w') as f:
                        f.write(proj_json)

                    if is_tacc():
                        node = platform.node()
                        user = getpass.getuser()
                        tstamp = datetime.datetime.now().strftime('%Y%m%d')
                        fn = f"pf_{tstamp}_{node}_{user}_" + os.path.basename(name)
                        location = "/work/08507/joely/ls6/log_db"
                        of = os.path.join(location, fn)
                        with open(of, 'w') as f:
                            f.write(proj_json)


                    self.globTabs.setTabText(self.globTabs.currentIndex(), os.path.basename(name))
                    # self.statusBar.showMessage('Project Saved!', 3000)

                    # self.saveUserPreferences()
                    if not silently:
                        self.statusBar.showMessage('Project Saved!')



                except:
                    print_exception()
                else:
                    self._unsaved_changes = False

    def _callbk_unsavedChanges(self):
        if self._isProjectTab():
            # logger.info('')
            caller = inspect.stack()[1].function
            if caller == 'main':
                # self.tell('You have unsaved changes.')
                # logger.critical("caller: " + inspect.stack()[1].function)
                self._unsaved_changes = True
                name = os.path.basename(cfg.data.dest())
                self.globTabs.setTabText(self.globTabs.currentIndex(), name + '.swiftir' + ' *')

    def update_ng(self):
        if cfg.project_tab:
            cfg.project_tab.initNeuroglancer()
        if cfg.zarr_tab:
            cfg.zarr_tab.load()

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
        self.tell('Attempting to restart AlignEM-SWIFT...')
        path = os.path.join(os.getenv('WORK'), 'swift-ir', 'tacc_bootstrap')
        logger.info(f'Attempting to restart AlignEM-SWIFT with {path}...')
        # run_command('source', arg_list=[path])
        # run_command('/usr/src/ofa_kernel-5.6/source', arg_list=[path])
        subprocess.run(["source", path])
        self.shutdownInstructions()


    def exit_app(self):

        logger.info('sender : ' + str(self.sender()))
        if self._exiting:
            self._exiting = 0
            if self.exit_dlg.isVisible():
                self.globTabsAndCpanel.children()[-1].hide()
            return
        self._exiting = 1

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        logger.info("Asking user to confirm exit application...")

        style = """
        QPushButton {
            color: #161c20;
            background-color: #f3f6fb;
            font-size: 9px;
            border-radius: 3px;
        }
        QDialog{
                /*background-color: #161c20;*/
                color: #ede9e8;
                font-size: 11px;
                font-weight: 600;
                border-color: #339933;
                border-width: 2px;
        }
            """

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
        # self.statusBar.addPermanentWidget(self.exit_dlg)

    def shutdownInstructions(self):
        logger.info('Performing Shutdown Instructions...')

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

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

        self._autosave(silently=True)

        if cfg.USE_EXTRA_THREADING:
            try:
                self.tell('Waiting For Threadpool...')
                logger.info('Waiting For Threadpool...')
                result = self.threadpool.waitForDone(msecs=500)
            except:
                print_exception()
                self.warn(f'Having trouble shutting down threadpool')
            finally:
                time.sleep(.3)

        # if cfg.DEV_MODE:
        self.tell('Shutting Down Python Console Kernel...')
        logger.info('Shutting Down Python Console Kernel...')
        try:

            self.pythonConsole.pyconsole.kernel_client.stop_channels()
            self.pythonConsole.pyconsole.kernel_manager.shutdown_kernel()
        except:
            print_exception()
            self.warn('Having trouble shutting down Python console kernel')
        finally:
            time.sleep(.3)

        self.tell('Graceful, Goodbye!')
        logger.info('Exiting...')
        time.sleep(1)
        QApplication.quit()

    # def html_view(self):
    #     app_root = self.get_application_root()
    #     html_f = os.path.join(app_root, 'src', 'resources', 'remod.html')
    #     with open(html_f, 'r') as f:
    #         html = f.read()
    #     self.browser_web.setHtml(html)
    #     self.main_stack_widget.setCurrentIndex(1)

    def html_resource(self, resource='features.html', title='Features', ID=''):

        html_f = os.path.join(self.get_application_root(), 'src', 'resources', resource)
        with open(html_f, 'r') as f:
            html = f.read()

        # webengine = QWebEngineView()
        webengine = WebEngine(ID=ID)
        webengine.setFocusPolicy(Qt.StrongFocus)
        webengine.setHtml(html, baseUrl=QUrl.fromLocalFile(os.getcwd() + os.path.sep))
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.globTabs.addTab(webengine, title)
        self._setLastTab()
        self.setCpanelVisibility(False)

    def url_resource(self, url, title):
        webengine = QWebEngineView()
        # webengine.setFocusPolicy(Qt.StrongFocus)
        webengine.setUrl(QUrl(url))
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.globTabs.addTab(webengine, title)
        self._setLastTab()
        self.setCpanelVisibility(False)

    def remote_view(self):
        self.tell('Opening Neuroglancer Remote Viewer...')
        browser = WebBrowser()
        browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.globTabs.addTab(browser, 'Neuroglancer')
        self._setLastTab()
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

    def invalidate_all(self, s=None):
        if ng.is_server_running():
            if s == None: s = cfg.data.scale_key
            if cfg.data.is_mendenhall():
                cfg.emViewer.menLV.invalidate()
            else:
                cfg.refLV.invalidate()
                cfg.baseLV.invalidate()
                if exist_aligned_zarr(s):
                    cfg.alLV.invalidate()

    #
    # def stopNgServer(self):
    #     # caller = inspect.stack()[1].function
    #     # logger.critical(caller)
    #     if ng.is_server_running():
    #         logger.info('Stopping Neuroglancer...')
    #         try:    ng.stop()
    #         except: print_exception()
    #     else:
    #         logger.info('Neuroglancer Is Not Running')

    def startStopTimer(self):
        logger.info('')
        if self._isProjectTab():
            if self._isPlayingBack:
                self.automaticPlayTimer.stop()
                self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
                # self._btn_automaticPlayTimer.setIcon(QIcon('src/resources/play-button.png'))
            elif cfg.project_tab or cfg.zarr_tab:
                # self.automaticPlayTimer.setInterval(1000 / cfg.DEFAULT_PLAYBACK_SPEED)
                self.automaticPlayTimer.start()
                self._btn_automaticPlayTimer.setIcon(qta.icon('fa.pause', color=cfg.ICON_COLOR))
                # self._btn_automaticPlayTimer.setIcon(QIcon('src/resources/pause-button.png'))
            self._isPlayingBack = not self._isPlayingBack

    def stopPlaybackTimer(self):
        self.automaticPlayTimer.stop()
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        # self._btn_automaticPlayTimer.setIcon(QIcon('src/resources/play-button.png'))
        self._isPlayingBack = 0

    def incrementZoomOut(self):
        if ('QTextEdit' or 'QLineEdit') in str(cfg.mw.focusWidget()):
            return

        # logger.info('')
        if self._isProjectTab():
            if cfg.data['state']['current_tab'] == 1:
                if cfg.data['state']['tra_ref_toggle']:
                    new_cs_scale = cfg.baseViewer.zoom() * 1.1
                    logger.info(f'new_cs_scale: {new_cs_scale}')
                    cfg.baseViewer.set_zoom(new_cs_scale)
                    cfg.refViewer.set_zoom(new_cs_scale)
                else:
                    new_cs_scale = cfg.refViewer.zoom() * 1.1
                    logger.info(f'new_cs_scale: {new_cs_scale}')
                    cfg.refViewer.set_zoom(new_cs_scale)
                    cfg.baseViewer.set_zoom(new_cs_scale)
                cfg.project_tab.zoomSlider.setValue(1 / new_cs_scale)
            elif cfg.data['state']['current_tab'] == 0:
                new_cs_scale = cfg.emViewer.zoom() * 1.1
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.emViewer.set_zoom(new_cs_scale)
                cfg.project_tab.zoomSlider.setValue(1 / new_cs_scale)

    def incrementZoomIn(self):
        # logger.info('')
        if ('QTextEdit' or 'QLineEdit') in str(cfg.mw.focusWidget()):
            return

        if self._isProjectTab():
            if cfg.data['state']['current_tab'] == 1:
                if cfg.data['state']['tra_ref_toggle']:
                    new_cs_scale = cfg.baseViewer.zoom() * 0.9
                    logger.info(f'new_cs_scale: {new_cs_scale}')
                    cfg.baseViewer.set_zoom(new_cs_scale)
                else:
                    new_cs_scale = cfg.refViewer.zoom() * 0.9
                    logger.info(f'new_cs_scale: {new_cs_scale}')
                    cfg.refViewer.set_zoom(new_cs_scale)
                cfg.project_tab.zoomSlider.setValue(1 / new_cs_scale)
            elif cfg.data['state']['current_tab'] == 0:
                new_cs_scale = cfg.emViewer.zoom() * 0.9
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.emViewer.set_zoom(new_cs_scale)
                cfg.project_tab.zoomSlider.setValue(1 / new_cs_scale)

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
        self.setCpanelVisibility(False)


    def tab_report_bug(self):
        logger.info('Opening GitHub issue tracker tab...')
        cfg.bugreport = browser = WebBrowser(self)
        browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/issues'))
        self.addGlobTab(browser, 'Issue Tracker')
        self.setCpanelVisibility(False)


    def tab_3dem_community_data(self):
        path = 'https://3dem.org/workbench/data/tapis/community/data-3dem-community/'
        browser = WebBrowser(self)
        browser.setUrl(QUrl(path))
        self.addGlobTab(browser, '3DEM Community Data (TACC)')
        self.setCpanelVisibility(False)


    def tab_workbench(self):
        logger.info('Opening 3DEM Workbench tab...')
        browser = WebBrowser(self)
        browser.setUrl(QUrl('https://3dem.org/workbench/'))
        self.addGlobTab(browser, '3DEM Workbench')
        self.setCpanelVisibility(False)

    def gpu_config(self):
        logger.info('Opening GPU Config...')
        browser = WebBrowser()
        browser.setUrl(QUrl('chrome://gpu'))
        self.globTabs.addTab(browser, 'GPU Configuration')
        self._setLastTab()
        self.setCpanelVisibility(False)


    def chromium_debug(self):
        logger.info('Opening Chromium Debugger...')
        browser = WebBrowser()
        browser.setUrl(QUrl('http://127.0.0.1:9000'))
        self.globTabs.addTab(browser, 'Debug Chromium')
        self._setLastTab()
        self.setCpanelVisibility(False)


    def get_ng_state(self):
        if cfg.project_tab:
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
        if cfg.project_tab:
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
        if cfg.project_tab:
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

    def _callbk_bnding_box(self, state):
        caller = inspect.stack()[1].function
        logger.info(f'Bounding Box Toggle Callback (caller: {caller})')
        # if caller != 'dataUpdateWidgets':


        if caller == 'main':
            state = cfg.pt._bbToggle.isChecked()
            # cfg.pt._bbToggle.setEnabled(state)
            if state:
                self.warn('Bounding Box is ON. Warning: Output dimensions may grow larger than source.')
                cfg.data['data']['defaults']['bounding-box'] = True
            else:
                self.tell('Bounding Box is OFF. Output dimensions will match source.')
                cfg.data['data']['defaults']['bounding-box'] = False

    def _callbk_skipChanged(self, state: int):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        #Todo refactor
        caller = inspect.stack()[1].function
        # if caller == 'main':
        if self._isProjectTab():
            if caller != 'dataUpdateWidgets':
                # logger.critical('')
                skip_state = not self._skipCheckbox.isChecked()
                layer = cfg.data.zpos
                for s in cfg.data.finer_scales():
                    if layer < len(cfg.data):
                        cfg.data.set_skip(skip_state, s=s, l=layer)
                    else:
                        logger.warning(f'Request layer is out of range ({layer}) - Returning')
                        return


                if skip_state:
                    self.tell("Exclude: %s" % cfg.data.name_base())
                    if self.dw_thumbs.isVisible():
                        cfg.project_tab.tn_ref.hide()
                        cfg.project_tab.tn_ref_lab.hide()
                        cfg.project_tab.tn_tra_overlay.show()
                else:
                    self.tell("Include: %s" % cfg.data.name_base())
                    if self.dw_thumbs.isVisible():
                        cfg.project_tab.tn_ref.show()
                        cfg.project_tab.tn_ref_lab.show()
                        cfg.project_tab.tn_tra_overlay.hide()
                cfg.data.link_reference_sections()
                # if getData('state,blink'):
                self.dataUpdateWidgets()
                # if cfg.project_tab._tabs.currentIndex() == 1:
                    # cfg.project_tab.project_table.initTableData()
                cfg.pt.project_table.set_row_data(row=layer)

                #Todo Fix this. This is just a kluge to make the table reflect correct data for now.
                for x in range(0,5):
                    if layer + x in range(0,len(cfg.data)):
                        cfg.pt.project_table.set_row_data(row=layer + x)

            if cfg.project_tab._tabs.currentIndex() == 4:
                cfg.project_tab.snr_plot.initSnrPlot()

            if self.dw_snr.isVisible():
                cfg.project_tab.dSnr_plot.initSnrPlot()


    def skip_change_shortcut(self):
        logger.info('')
        if cfg.data:
            self._skipCheckbox.setChecked(not self._skipCheckbox.isChecked())

    def runchecks(self):
        run_checks()

    def onMAsyncTimer(self):
        logger.critical("")
        logger.critical(f"cfg.data.zpos         = {cfg.data.zpos}")
        logger.critical(f"cfg.refViewer.index   = {cfg.refViewer.index}")
        logger.critical(f"cfg.baseViewer.index  = {cfg.baseViewer.index}")

    def clear_match_points(self):
        if cfg.project_tab:
            logger.info('Clearing Match Points...')
            cfg.data.clearMps()
            self.dataUpdateWidgets()

    def print_all_matchpoints(self):
        if cfg.project_tab:
            cfg.data.print_all_manpoints()

    def show_all_matchpoints(self):
        if cfg.project_tab:
            no_mps = True
            for i, l in enumerate(cfg.data.stack()):
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
        if self.dw_python.isHidden():
            self.dw_python.show()
        else:
            self.dw_python.hide()

    def set_opacity(self, obj, val):
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(val)  # 0 to 1 -> fade effect
        obj.setGraphicsEffect(op)
        obj.setAutoFillBackground(True)

    # def set_shader_none(self):
    #     cfg.SHADER = '''void main () {
    #       emitGrayscale(toNormalized(getDataValue()));
    #     }'''
    #     cfg.project_tab.initNeuroglancer()

    def set_shader_default(self):
        cfg.data['rendering']['shader'] = src.shaders.shader_default_
        cfg.project_tab.initNeuroglancer()

    def set_shader_colormapJet(self):
        cfg.data['rendering']['shader'] = src.shaders.colormapJet
        cfg.project_tab.initNeuroglancer()

    def set_shader_test1(self):
        cfg.data['rendering']['shader'] = src.shaders.shader_test1
        cfg.project_tab.initNeuroglancer()

    def set_shader_test2(self):
        cfg.data['rendering']['shader'] = src.shaders.shader_test2
        cfg.project_tab.initNeuroglancer()

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

    def modeKeyToPretty(self, key):
        if key == 'stack-xy':
            return 'Stack View (xy plane)'
        elif key == 'stack-4panel':
            return 'Stack View (4 panel)'
        # elif key == 'comparison':
        #     return 'Comparison View'
        elif key == 'manual_align':
            return 'Manual Align Mode'

    # def prettyToModeKey(self, key):
    #     if key == 'Stack View (xy plane)':
    #         return 'stack-xy'
    #     elif key == 'Stack View (4 panel)':
    #         return 'stack-4panel'
    #     # elif key == 'Comparison View':
    #     #     return 'comparison'
    #     elif key == 'Manual Align Mode':
    #         return 'manual_align'

    # def onComboModeChange(self):
    #     caller = inspect.stack()[1].function
    #
    #     if self._isProjectTab():
    #         # if cfg.project_tab._tabs.currentIndex() == 0:
    #         if caller == 'main':
    #             logger.info('')
    #             curText = self.combo_mode.currentText()
    #             if curText == 'Manual Align Mode':
    #                 if not cfg.data.is_aligned():
    #                     self.warn('Align the series first and then use Manual Alignment.')
    #                     self.combo_mode.setCurrentText(self.modeKeyToPretty(getData('state,mode')))
    #                     return
    #             requested_key = self.prettyToModeKey(curText)
    #             logger.info(f'Requested key: {requested_key}')
    #             if getData('state,mode') == 'manual_align':
    #                 if requested_key != 'manual_align':
    #                     self.go_to_series_viewer()
    #             setData('state,mode', requested_key)
    #             if requested_key == 'stack-4panel':
    #                 setData('state,ng_layout', '4panel')
    #             elif requested_key == 'stack-xy':
    #                 setData('state,ng_layout', 'xy')
    #             elif requested_key == 'comparison':
    #                 setData('state,ng_layout', 'xy')
    #             elif requested_key == 'manual_align':
    #                 setData('state,ng_layout', 'xy')
    #                 self.go_to_alignment_editor()
    #             self.dataUpdateWidgets()
    #             cfg.project_tab.comboNgLayout.setCurrentText(getData('state,ng_layout'))
    #             cfg.project_tab.initNeuroglancer()
    #
    #         # cfg.project_tab.updateCursor()
    #     else:
    #         self.combo_mode.setCurrentText(self.modeKeyToPretty('comparison'))

    def initToolbar(self):
        logger.info('')

        # with open('src/style/buttonstyle.qss', 'r') as f:
        #     button_gradient_style = f.read()

        f = QFont()
        f.setBold(True)
        f.setPixelSize(10)

        # self.exitButton = QPushButton()
        # self.exitButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # # self.exitButton.setFixedSize(QSize(15,15))
        # # self.exitButton.setIconSize(QSize(12,12))
        # self.exitButton.setFixedSize(QSize(16, 16))
        # self.exitButton.setIconSize(QSize(14, 14))
        # # self.exitButton.setIcon(qta.icon('fa.close', color='#161c20'))
        # self.exitButton.setIcon(qta.icon('mdi.close', color='#161c20'))
        # self.exitButton.clicked.connect(self.exit_app)
        # # self.exitButton.setStyleSheet(button_gradient_style)
        # # self.exitButton.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif; border: none;')
        #
        # self.minimizeButton = QPushButton()
        # self.minimizeButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.minimizeButton.setFixedSize(QSize(16, 16))
        # self.minimizeButton.setIconSize(QSize(14, 14))
        # # self.minimizeButton.setIcon(qta.icon('fa.window-minimize', color='#161c20'))
        # self.minimizeButton.setIcon(qta.icon('mdi.minus-thick', color='#161c20'))
        # self.minimizeButton.clicked.connect(self.showMinimized)
        # # self.minimizeButton.setStyleSheet(button_gradient_style)

        self.tbbRefresh = QToolButton()
        self.tbbRefresh.setToolTip(f"Refresh View {hotkey('R')}")
        self.tbbRefresh.clicked.connect(self.refreshTab)
        self.tbbRefresh.setIcon(qta.icon("fa.refresh", color='#161c20'))

        def fn_view_faq():
            search = self.lookForTabID(search='faq')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("FAQ is already open!", msecs=3000)
            else:
                logger.info('Showing FAQ...')
                self.html_resource(resource='faq.html', title='FAQ', ID='faq')

        self.tbbFAQ = QToolButton()
        self.tbbFAQ.setToolTip(f"Read AlignEM-SWiFT FAQ")
        self.tbbFAQ.clicked.connect(fn_view_faq)
        self.tbbFAQ.setIcon(qta.icon("fa.question", color='#161c20'))


        def fn_view_getting_started():
            search = self.lookForTabID(search='getting-started')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("Getting started document is already open!", msecs=3000)
            else:
                logger.info('Showing Getting Started Tips...')
                self.html_resource(resource='getting-started.html', title='Getting Started', ID='getting-started')

        self.tbbGettingStarted = QToolButton()
        self.tbbGettingStarted.setToolTip(f"Read AlignEM-SWiFT Tips for Getting Started")
        self.tbbGettingStarted.clicked.connect(fn_view_getting_started)
        self.tbbGettingStarted.setIcon(qta.icon("fa.map-signs", color='#161c20'))


        def fn_glossary():
            search = self.lookForTabID(search='glossary')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("Glossary is already open!", msecs=3000)
            else:
                logger.info('Showing Glossary...')
                self.html_resource(resource='glossary.html', title='Glossary', ID='glossary')

        self.tbbGlossary = QToolButton()
        self.tbbGlossary.setToolTip(f"Read AlignEM-SWiFT Glossary")
        self.tbbGlossary.clicked.connect(fn_glossary)
        self.tbbGlossary.setIcon(qta.icon("fa.book", color='#161c20'))

        self.tbbReportBug = QToolButton()
        self.tbbReportBug.setStyleSheet("Report a bug, suggest changes, or request features for AlignEM-SWiFT")
        self.tbbReportBug.clicked.connect(self.tab_report_bug)
        self.tbbReportBug.setIcon(qta.icon("fa.bug", color='#161c20'))

        self.tbb3demdata = QToolButton()
        self.tbb3demdata.setStyleSheet("Access 3DEM Workbench Data")
        self.tbb3demdata.clicked.connect(self.tab_3dem_community_data)
        self.tbb3demdata.setIcon(qta.icon("fa.database", color='#161c20'))

        # self.workbenchButton = QPushButton('3DEM Workbench')
        # self.workbenchButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.workbenchButton.setFont(f)
        # self.workbenchButton.setFixedHeight(18)
        # self.workbenchButton.setIconSize(QSize(16, 16))
        # self.workbenchButton.clicked.connect(self.tab_workbench)

        # self.navWidget = HWidget(QLabel(' '), self.refreshButton, self.faqButton, self.gettingStartedButton, self.glossaryButton, self.bugreportButton, ExpandingWidget(self))
        # self.navWidget.setFixedHeight(18)
        # self.navWidget.setC

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(18,18))
        self.toolbar.setMovable(True)
        # self.toolbar.setIconSize(QSize(18,18))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.toolbar.setFixedHeight(32)
        # self.toolbar.setFixedHeight(24)
        self.toolbar.setObjectName('toolbar')
        # self.addToolBar(self.toolbar)


        tip = f"Show Notepad Tool Window {hotkey('Z')}"
        # self.tbbNotes = QCheckBox(f"Notes {hotkey('N')}")
        # self.tbbNotes = QCheckBox(f"Notes {hotkey('Z')}")
        self.tbbNotes = QToolButton()
        self.tbbNotes.setCheckable(True)
        self.tbbNotes.setToolTip(tip)
        self.tbbNotes.setIcon(QIcon('src/resources/notepad-icon.png'))
        # self.tbbNotes.setIcon(qta.icon("fa.sticky-note", color='#161c20'))
        # self.tbbNotes.setIcon(qta.icon("mdi.notebook-edit", color='#161c20'))
        # self.tbbNotes.stateChanged.connect(lambda: self.setdw_notes(self.tbbNotes.isChecked()))
        # self.tbbNotes.pressed.connect(lambda: self.setdw_notes(not self.tbbNotes.isChecked()))

        def fn_tb_press():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if caller == 'main':
                self.setdw_notes(self.tbbNotes.isChecked())
        self.tbbNotes.clicked.connect(fn_tb_press)
        # self.tbbNotes.setDefaultAction(self.a_notes)


        tip = f"Show Python Console Tool Window {hotkey('P')}"
        # self.tbbPython = QCheckBox(f"Python Console {hotkey('P')}")
        self.tbbPython = QToolButton()
        self.tbbPython.setCheckable(True)
        self.tbbPython.setToolTip(tip)

        self.tbbPython.setIcon(QIcon('src/resources/python-icon.png'))
        # self.tbbPython.stateChanged.connect(self._callbk_showHidePython)
        # self.tbbPython.stateChanged.connect(lambda: self.setdw_python(self.tbbPython.isChecked()))
        def fn_tb_press():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if caller == 'main':
                self.setdw_python(self.tbbPython.isChecked())
        # self.tbbPython.pressed.connect(fn_tb_press)
        self.tbbPython.clicked.connect(fn_tb_press)
        # self.tbbPython.pressed.connect(lambda: self.setdw_python(self.tbbPython.isChecked()))

        tip = f"Show Process Monitor Tool Window {hotkey('H')}"
        self.tbbHud = QToolButton()
        def fn_tb_press():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if caller == 'main':
                self.setdw_hud(self.tbbHud.isChecked())
        self.tbbHud.setCheckable(True)
        self.tbbHud.setToolTip(tip)
        self.tbbHud.setIcon(qta.icon("mdi.monitor", color='#161c20'))
        self.tbbHud.clicked.connect(fn_tb_press)


        tip = f"Show Raw Thumbnails {hotkey('T')}"
        self.tbbThumbnails = QToolButton()
        def fn_tb_press():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if caller == 'main':
                self.setdw_thumbs(self.tbbThumbnails.isChecked())
        self.tbbThumbnails.setCheckable(True)
        self.tbbThumbnails.setToolTip(tip)
        self.tbbThumbnails.setIcon(qta.icon("mdi.relative-scale", color='#161c20'))
        self.tbbThumbnails.clicked.connect(fn_tb_press)

        tip = f"Show Match Signals {hotkey('I')}"
        self.tbbMatches = QToolButton()
        def fn_tb_press():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if caller == 'main':
                self.setdw_matches(self.tbbMatches.isChecked())
        self.tbbMatches.setCheckable(True)
        # self.tbbMatches.setChecked(False)
        self.tbbMatches.setToolTip(tip)
        self.tbbMatches.setIcon(qta.icon("mdi.image-filter-center-focus", color='#161c20'))
        self.tbbMatches.clicked.connect(fn_tb_press)


        tip = f"Show SNR Plot {hotkey('L')}"
        self.tbbSnr = QToolButton()
        def fn_tb_press():
            caller = inspect.stack()[1].function
            logger.info(f'[{caller}]')
            if caller == 'main':
                self.setdw_snr(self.tbbSnr.isChecked())
        self.tbbSnr.setCheckable(True)
        self.tbbSnr.setToolTip(tip)
        self.tbbSnr.setIcon(qta.icon("mdi.chart-scatter-plot", color='#161c20'))
        self.tbbSnr.clicked.connect(fn_tb_press)

        self.tbbDetachNgButton = QToolButton()
        # self.tbbDetachNgButton.setCheckable(True)
        self.tbbDetachNgButton.setIcon(qta.icon("fa.external-link-square", color='#161c20'))
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
        #
        # self.testButton = QPushButton()
        # self.testButton.setMenu(testmenu)
        # def testFn():
        #     print('Test Function Called...')
        # self.testButton.clicked.connect(testFn)




        toolbuttons = [
            self.tbbRefresh,
            self.tbbGettingStarted,
            self.tbbFAQ,
            self.tbbGlossary,
            self.tbbReportBug,
            self.tbb3demdata,
            self.tbbMatches,
            self.tbbSnr,
            self.tbbThumbnails,
            self.tbbHud,
            self.tbbNotes,
            self.tbbPython,
            self.tbbDetachNgButton
        ]

        names = [' &Refresh','Getting\nStarted',' FAQ','Glossary','Issue\nTracker','3DEM\nData',' &Matches', 'SNR P&lot', 'Ref/Tra\n&Thumbs', '   &HUD', '  &Notes', '&Python\nConsole', '&Detach\nNG']
        for b,n in zip(toolbuttons,names):
            b.setText(n)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setFixedSize(QSize(80,28))
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setStyleSheet("""
            font-size: 10px; 
            font-weight: 600; 
            color: #161c20;
            padding: 1px;
            margin: 1px;
            """)

            # b.setLayoutDirection(Qt.RightToLeft)


        self.tbbMenu = QToolButton()
        self.tbbMenu.setMenu(self.menu)
        self.tbbMenu.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbbMenu.setPopupMode(QToolButton.InstantPopup)
        # self.tbbMenu.setToolTip(f"Menu")
        # self.tbbMenu.clicked.connect(fn_glossary)
        self.tbbMenu.setIcon(qta.icon("mdi.menu", color='#161c20'))

        self.newLabel = QLabel(' ← New! ')
        self.newLabel.setFixedHeight(16)
        self.newLabel.setStyleSheet("background-color: #AAFF00; color: #161c20; font-size: 10px; border-radius: 4px;")

        self.toolbar.addWidget(self.tbbMenu)
        self.toolbar.addWidget(self.tbbRefresh)
        self.toolbar.addWidget(self.tbbGettingStarted)
        self.toolbar.addWidget(self.tbbFAQ)
        self.toolbar.addWidget(self.tbbGlossary)
        self.toolbar.addWidget(self.tbbReportBug)
        self.toolbar.addWidget(self.tbb3demdata)
        self.toolbar.addWidget(self.newLabel)
        self.toolbar.addWidget(ExpandingWidget(self))
        # self.toolbar.addWidget(self.testButton)
        self.toolbar.addWidget(self.tbbThumbnails)
        self.toolbar.addWidget(self.tbbMatches)
        self.toolbar.addWidget(self.tbbSnr)
        self.toolbar.addWidget(self.tbbHud)
        self.toolbar.addWidget(self.tbbPython)
        self.toolbar.addWidget(self.tbbNotes)
        self.toolbar.addWidget(self.tbbDetachNgButton)
        # self.toolbar.addWidget(self.tbbMenu)


        # self.toolbar.layout().setSpacing(2)
        # self.toolbar.layout().setAlignment(Qt.AlignRight)
        self.toolbar.setStyleSheet('font-size: 10px; font-weight: 600; color: #161c20;')

    def resizeEvent(self, e):
        logger.info('')

        # self.dw_matches.setMaximumWidth(999)
        # self.dw_thumbs.setMaximumWidth(999)
        # if self._isProjectTab():
        #
        #     if self.dw_matches.isVisible():
        #         if cfg.data.is_aligned():
        #             h = self.dw_matches.height() - cfg.pt.mwTitle.height()
        #             # self.dw_matches.setMaximumWidth(int(h / 2 + .5))
        #             cfg.pt.match_widget.resize(int(h / 2 + .5), h)
        #
        #     if self.dw_thumbs.isVisible():
        #         h = cfg.pt.tn_widget.height() - cfg.pt.tn_ref_lab.height() - cfg.pt.tn_tra_lab.height()
        #         # self.dw_thumbs.setMaximumWidth(int(h / 2 + .5))
        #         cfg.pt.tn_widget.resize(QSize(int(h / 2 + .5), cfg.pt.tn_widget.height()))

        # if self.dw_thumbs.isVisible():
        #     QApplication.processEvents()
        #     h = self.dw_thumbs.height() - cfg.pt.tn_ref_lab.height() - cfg.pt.tn_tra_lab.height()
        #     self.dw_thumbs.setMaximumWidth(int(h / 2 + .5))
        #     # cfg.pt.tn_widget.resize(QSize(int(h / 2 + .5), cfg.pt.tn_widget.height()))
        # #
        # if self.dw_matches.isVisible():
        #     self.setUpdatesEnabled(True)
        #     QApplication.processEvents()
        #
        #     if cfg.data.is_aligned():
        #         h = self.dw_matches.height() - cfg.pt.mwTitle.height()
        #         self.dw_matches.setMaximumWidth(int(h /2 + .5))
        #         # cfg.pt.match_widget.resize(int(h / 2 + .5), h)





    def changeEvent(self, event):

        # self.dw_matches.setMaximumWidth(999)
        # self.dw_thumbs.setMaximumWidth(999)


        # Allows catching of window maximized/unmaximized events
        if event.type() == QEvent.WindowStateChange:
            if event.oldState() and Qt.WindowMinimized:
                logger.info("(!) window un-maximized")
                self.fullScreenAction.setIcon(qta.icon('mdi.fullscreen', color='#ede9e8'))
            elif event.oldState() == Qt.WindowNoState or self.windowState() == Qt.WindowMaximized:
                logger.info("(!) window maximized")
                self.fullScreenAction.setIcon(qta.icon('mdi.fullscreen-exit', color='#ede9e8'))
            if self._isProjectTab():
                if cfg.pt._tabs.currentIndex() == 1:
                    cfg.pt.fn_hwidgetChanged()
                if cfg.pt._tabs.currentIndex() in (0, 1):
                    # QApplication.processEvents()
                    cfg.project_tab.initNeuroglancer()

            # if self.dw_matches.isVisible():
            #     if cfg.data.is_aligned():
            #         h = cfg.pt.ktarg_table.height() - cfg.pt.mwTitle.height()
            #         # self.dw_matches.setMaximumWidth(int(h / 2 + .5))
            #         cfg.pt.match_widget.resize(int(h / 2 + .5), h)
            #
            # if self.dw_thumbs.isVisible():
            #     h = cfg.pt.tn_widget.height() - cfg.pt.tn_ref_lab.height() - cfg.pt.tn_tra_lab.height()
            #     # self.dw_thumbs.setMaximumWidth(int(h / 2 + .5))
            #     cfg.pt.tn_widget.resize(QSize(int(h / 2 + .5), cfg.pt.tn_widget.height()))

            # cfg.pt.match_widget.adjustSize()
            # cfg.pt.tn_widget.adjustSize()

    def set_elapsed(self, t, desc=""):
        txt = f"Elapsed Time : %.3gs / %.3gm" % (t, t / 60)
        if desc:
            txt += " (%s)" % desc
        self.set_status(txt)


    def _disableGlobTabs(self):
        logger.info('')
        indexes = list(range(0, self.globTabs.count()))
        indexes.remove(self.globTabs.currentIndex())
        for i in indexes:
            self.globTabs.setTabEnabled(i, False)
        # self._btn_refreshTab.setEnabled(False)

    def enableAllTabs(self):
        logger.info('')
        indexes = list(range(0, self.globTabs.count()))
        for i in indexes:
            self.globTabs.setTabEnabled(i, True)
        if cfg.project_tab:
            for i in range(0, 5):
                cfg.project_tab._tabs.setTabEnabled(i, True)
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

    def _getTabType(self, index=None):
        try:
            return self.globTabs.currentWidget().__class__.__name__
        except:
            return None

    def getOpenProjects(self):
        projects = []
        for i in range(self.globTabs.count()):
            if 'ProjectTab' in str(self.globTabs.widget(i)):
                projects.append(self.globTabs.widget(i).datamodel.dest())
        return projects

    def isProjectOpen(self, name):
        return os.path.splitext(name)[0] in [os.path.splitext(x)[0] for x in self.getOpenProjects()]

    def getProjectIndex(self, search):
        for i in range(self.globTabs.count()):
            if 'ProjectTab' in str(self.globTabs.widget(i)):
                if self.globTabs.widget(i).datamodel.dest() == os.path.splitext(search)[0]:
                    return i

    def getCurrentTabWidget(self):
        return self.globTabs.currentWidget()

    def _getTabObject(self):
        return self.globTabs.currentWidget()


    def addGlobTab(self, tab_widget, name):
        logger.info(f'Adding Tab, type: {type(tab_widget)}\nName: {name}')
        cfg.tabsById[id(tab_widget)] = {}
        cfg.tabsById[id(tab_widget)]['name'] = name
        cfg.tabsById[id(tab_widget)]['type'] = type(tab_widget)
        cfg.tabsById[id(tab_widget)]['widget'] = tab_widget
        self.globTabs.setCurrentIndex(self.globTabs.addTab(tab_widget, name))


    def getTabIndexById(self, ID):
        for i in range(self.globTabs.count()):
            if ID == id(self.globTabs.widget(i)):
                return i
        logger.warning(f'Tab {ID} not found.')
        return 0



    def _onGlobTabChange(self):

        # if self._dontReinit == True:
        #     logger.critical('\n\n\n<<<<< DONT REINIT! >>>>>\n\n\n')
        #     return

        self.setUpdatesEnabled(False)

        caller = inspect.stack()[1].function
        logger.info(f'_onGlobTabChange [{caller}]')
        # if caller not in ('onStartProject', '_setLastTab'): #0524-
        #     self.shutdownNeuroglancer()  # 0329+

        cfg.project_tab = None
        cfg.zarr_tab = None
        self.enableAllTabs()  # Critical - Necessary for case of glob tab closure during disabled state for MA Mode
        self.stopPlaybackTimer()
        self._changeScaleCombo.clear()
        # self.combo_mode.clear()
        # self._changeScaleCombo.setEnabled(True)  # needed for disable on MA
        # self.clearCorrSpotsDrawer()
        QApplication.restoreOverrideCursor()

        if self._getTabType() != 'ProjectTab':
            self.setCpanelVisibility(False)
            self.statusBar.clearMessage()
            self.statusBar.setStyleSheet("""
                font-size: 10px;
                color: #161c20;
                background-color: #ede9e8;
                margin: 0px;
                padding: 0px;
            """)

            self.dw_thumbs.setWidget(NullWidget())

            self.dw_matches.setWidget(NullWidget())

            self.dw_snr.setWidget(NullWidget())

        elif self._getTabType() == 'OpenProject':
            configure_project_paths()
            self._getTabObject().user_projects.set_data()

        elif self._getTabType() == 'ProjectTab':
            cfg.data = self.globTabs.currentWidget().datamodel
            cfg.project_tab = cfg.pt = self.globTabs.currentWidget()
            cfg.pt.initNeuroglancer(init_all=True)
            # if self._is_initialized:
            try:
                cfg.emViewer = cfg.project_tab.viewer
                cfg.refViewer = cfg.project_tab.refViewer
                cfg.baseViewer = cfg.project_tab.baseViewer
            except:
                pass
            self.dw_thumbs.setWidget(cfg.pt.tn_widget)
            self.dw_matches.setWidget(cfg.pt.match_widget)
            self.dw_snr.setWidget(cfg.pt.dSnr_plot)
            self.setCpanelVisibility(True)

            self.dataUpdateWidgets()
            try:
                self.setControlPanelData()
            except:
                print_exception()

            # self.updateAllCpanelDetails()

        elif self._getTabType() == 'ZarrTab':
            logger.critical('Loading Zarr Tab...')
            cfg.zarr_tab = self.globTabs.currentWidget()
            cfg.emViewer = cfg.zarr_tab.viewer
            # self.set_nglayout_combo_text(layout='4panel')
            cfg.zarr_tab.viewer.bootstrap()

        # self.updateMenus()
        self.reload_zpos_slider_and_lineedit()  # future changes to image importing will require refactor
        self.reload_scales_combobox()
        self.updateEnabledButtons()
        self.updateNotes()
        self.setFocus()
        self.setUpdatesEnabled(True)

    def _onGlobTabClose(self, index):
        if not self._working:
            logger.info(f'Closing Tab: {index}')
            self.globTabs.removeTab(index)

    def _setLastTab(self):
        self.globTabs.setCurrentIndex(self.globTabs.count() - 1)

    def new_mendenhall_protocol(self):
        # self.new_project(mendenhall=True)
        # scale_key = cfg.data.scale_key
        # cfg.data['data']['cname'] = 'none'
        # cfg.data['data']['clevel'] = 5
        # cfg.data['data']['chunkshape'] = (1, 512, 512)
        # cfg.data['data']['scales'][scale_key]['resolution_x'] = 2
        # cfg.data['data']['scales'][scale_key]['resolution_y'] = 2
        # cfg.data['data']['scales'][scale_key]['resolution_z'] = 50
        # self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        # self.mendenhall.set_directory()
        # self.mendenhall.start_watching()
        # cfg.data.set_source_path(self.mendenhall.sink)
        # self._saveProjectToFile()
        pass

    def open_mendenhall_protocol(self):
        filename = open_project_dialog()
        with open(filename, 'r') as f:
            project = DataModel(json.load(f), mendenhall=True)
        cfg.data = copy.deepcopy(project)
        cfg.data.set_paths_absolute(filename=filename)  # +
        self.mendenhall = Mendenhall(parent=self, data=cfg.data)
        self.mendenhall.start_watching()
        cfg.project_tab.initNeuroglancer()

    def stop_mendenhall_protocol(self):
        self.mendenhall.stop_watching()

    def aligned_mendenhall_protocol(self):
        # cfg.MV = not cfg.MV
        cfg.project_tab.initNeuroglancer()

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
        self.save()

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
    #             # if cfg.data.is_aligned():
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

    def initAllViewers(self):
        if self._isProjectTab():
            for v in cfg.project_tab.get_viewers():
                v.initViewer()




    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')

        # self.scManualAlign = QShortcut(QKeySequence('Ctrl+M'), self)
        # self.scManualAlign.activated.connect(self.enterExitManAlignMode)

        self.action_groups = {}

        # self.menu = self.menuBar()
        self.menu.setStyleSheet("""font-size: 11px; font-weight: 600;""")

        # Fix for non-native menu on macOS
        # self.menu.setNativeMenuBar(False)
        # self.menu.setNativeMenuBar(True)

        # self.exitAction = QAction()
        # self.exitAction.setToolTip("Exit AlignEM-SWiFT")
        # self.exitAction.setIcon(qta.icon('mdi.close', color='#ede9e8'))
        # self.exitAction.triggered.connect(self.exit_app)
        # 
        # self.minimizeAction = QAction()
        # self.minimizeAction.setToolTip("Minimize")
        # self.minimizeAction.setIcon(qta.icon('mdi.minus-thick', color='#ede9e8'))
        # self.minimizeAction.triggered.connect(self.showMinimized)
        # 
        # def fullscreen_callback():
        #     logger.info('')
        #     (self.showMaximized, self.showNormal)[self.isMaximized() or self.isFullScreen()]()
        # self.fullScreenAction = QAction()
        # self.fullScreenAction.setToolTip("Full Screen")
        # self.fullScreenAction.setIcon(qta.icon('mdi.fullscreen', color='#ede9e8'))
        # self.fullScreenAction.triggered.connect(fullscreen_callback)
        # 
        # self.menu.addAction(self.exitAction)
        # self.menu.addAction(self.minimizeAction)
        # self.menu.addAction(self.fullScreenAction)

        fileMenu = self.menu.addMenu('File')

        # self.newAction = QAction('&New Project...', self)
        # def fn():
        #     if self._isOpenProjTab():
        #
        #         self.getCurrentTabWidget()
        # self.newAction.triggered.connect(self.new_project)
        # self.newAction.setShortcut('Ctrl+N')
        # self.addAction(self.newAction)
        # fileMenu.addAction(self.newAction)

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
        self.refreshAction.triggered.connect(self.refreshTab)
        # self.refreshAction.setShortcut('Ctrl+R')
        # self.refreshAction.setShortcutContext(Qt.ApplicationShortcut)
        # self.addAction(self.refreshAction)
        fileMenu.addAction(self.refreshAction)


        action = QAction('3DEM Community Data', self)
        action.triggered.connect(self.tab_3dem_community_data)
        fileMenu.addAction(action)



        def fn():
            if self.globTabs.count() > 0:
                if cfg.mw._getTabType() != 'OpenProject':
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


        # elif event.key() == Qt.Key_P:
        #     self.setdw_python(not self.tbbPython.isChecked())
        #
        # elif event.key() == Qt.Key_H:
        #     self.setdw_hud(not self.tbbHud.isChecked())
        #
        # elif event.key() == Qt.Key_Z:
        #     self.setdw_notes(not self.tbbNotes.isChecked())
        #
        # elif event.key() == Qt.Key_T:
        #     self.setdw_thumbs(not self.tbbThumbnails.isChecked())
        #
        # elif event.key() == Qt.Key_M:
        #     self.setdw_matches(not self.tbbMatches.isChecked())


        self.a_python = QAction('Show &Python', self)
        self.a_python.triggered.connect(lambda: self.setdw_python(not self.tbbPython.isChecked()))
        # self.a_python.setShortcut('Ctrl+P')
        # self.a_python.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.a_python)


        self.a_monitor = QAction('Show Process &Monitor', self)
        # self.a_monitor.triggered.connect(lambda: self.tbbHud.setChecked(not self.tbbHud.isChecked()))
        self.a_monitor.triggered.connect(lambda: self.setdw_hud(not self.tbbHud.isChecked()))
        # self.a_monitor.setShortcut('Ctrl+H')
        # self.a_monitor.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.a_monitor)

        self.a_thumbs = QAction('Show Raw &Thumbnails', self)
        self.a_thumbs.triggered.connect(lambda: self.setdw_thumbs(not self.tbbThumbnails.isChecked()))
        # self.a_thumbs.setShortcut('Ctrl+T')
        # self.a_thumbs.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.a_thumbs)

        self.a_matches = QAction('Show Match S&ignals', self)
        self.a_matches.triggered.connect(lambda: self.setdw_matches(not self.tbbMatches.isChecked()))
        viewMenu.addAction(self.a_matches)

        self.a_snr = QAction('Show SNR P&lot', self)
        self.a_snr.triggered.connect(lambda: self.setdw_snr(not self.tbbSnr.isChecked()))
        viewMenu.addAction(self.a_snr)


        # self.a_notes = QAction('Show &Notes', self)
        self.a_notes = QAction('Show &Notes', self)
        self.a_notes.triggered.connect(lambda: self.setdw_notes(not self.tbbNotes.isChecked()))
        # self.a_notes.setShortcut('Ctrl+Z')
        # self.a_notes.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.a_notes)


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


        # self.ngShowAxisLinesAction = QAction(self)



        # self.ngShowScaleBarAction = QAction(self)
        # def fn():
        #     if self._isProjectTab():
        #         opt = self.ngShowScaleBarAction.isChecked()
        #         setOpt('neuroglancer,SHOW_SCALE_BAR', opt)
        #         # self.ngShowScaleBarAction.setText(('Show Scale Bar', 'Hide Scale Bar')[opt])
        #         # for v in self.get_viewers():
        #         #     v.updateScaleBar()
        #         if cfg.emViewer:
        #             cfg.emViewer.updateScaleBar()
        # self.ngShowScaleBarAction.setCheckable(True)
        # self.ngShowScaleBarAction.setChecked(getOpt('neuroglancer,SHOW_SCALE_BAR'))
        # # self.ngShowScaleBarAction.setText(('Show Scale Bar', 'Hide Scale Bar')[getOpt('neuroglancer,SHOW_SCALE_BAR')])
        # self.ngShowScaleBarAction.setText('Scale Bar')
        # self.ngShowScaleBarAction.triggered.connect(fn)
        # viewMenu.addAction(self.ngShowScaleBarAction)



        # self.colorMenu = ngMenu.addMenu('Select Background Color')
        # from qtpy.QtWidgets import QColorDialog
        # self.ngColorMenu= QColorDialog(self)
        # action = QWidgetAction(self)
        # action.setDefaultWidget(self.ngColorMenu)
        # # self.ngStateMenu.hovered.connect(self.updateNgMenuStateWidgets)
        # self.colorMenu.addAction(action)

        alignMenu = self.menu.addMenu('Align')

        # menu = alignMenu.addMenu('History')
        # action = QWidgetAction(self)
        # action.setDefaultWidget(self._tool_hstry)
        # menu.addAction(action)

        self.alignAllAction = QAction('Align All Current Scale', self)
        self.alignAllAction.triggered.connect(self.alignAll)
        # self.alignAllAction.setShortcut('Ctrl+A')
        # self.alignAllAction.setShortcutContext(Qt.ApplicationShortcut)
        alignMenu.addAction(self.alignAllAction)

        self.alignAllScalesAction = QAction('Align Scales to Full Res', self)
        self.alignAllScalesAction.triggered.connect(self.alignAllScales)
        alignMenu.addAction(self.alignAllScalesAction)

        self.alignOneAction = QAction('Align Current Section', self)
        self.alignOneAction.triggered.connect(self.alignGenerateOne)
        alignMenu.addAction(self.alignOneAction)

        self.skipChangeAction = QAction('Toggle Include', self)
        # self.skipChangeAction.triggered.connect(self.skip_change_shortcut)
        # self.skipChangeAction.setShortcut('Ctrl+K')
        self.addAction(self.skipChangeAction)
        alignMenu.addAction(self.skipChangeAction)

        # self.showMatchpointsAction = QAction('Show Matchpoints', self)
        # self.showMatchpointsAction.triggered.connect(self.show_all_matchpoints)
        # alignMenu.addAction(self.showMatchpointsAction)

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


        self.blinkAction = QAction('Turn Blink On/Off', self)
        # self.blinkAction.triggered.connect(self.turnBlinkOnOff)
        def blink_fn():
            if self._isProjectTab():
                cfg.project_tab.blinkToggle.setChecked(not cfg.project_tab.blinkToggle.isChecked())

        self.blinkAction.triggered.connect(blink_fn)
        # self.blinkAction.setShortcut('Ctrl+B')
        ngMenu.addAction(self.blinkAction)


        self.ngStateMenu = ngMenu.addMenu('JSON State')  # get_ng_state
        self.ngStateMenuText = QTextEdit(self)
        self.ngStateMenuText.setReadOnly(False)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.ngStateMenuText)
        # self.ngStateMenu.hovered.connect(self.updateNgMenuStateWidgets)
        ngMenu.hovered.connect(self.updateNgMenuStateWidgets)
        self.ngStateMenu.addAction(action)
        self.clearNgStateMenus()

        self.tensorMenu = ngMenu.addMenu('Tensors')
        self.clearTensorMenu()

        ngPerspectiveMenu = ngMenu.addMenu("Perspective")

        self.ngLayout1Action = QAction('xy', self)
        self.ngLayout2Action = QAction('yz', self)
        self.ngLayout3Action = QAction('xz', self)
        self.ngLayout4Action = QAction('xy-3d', self)
        self.ngLayout5Action = QAction('yz-3d', self)
        self.ngLayout6Action = QAction('xz-3d', self)
        self.ngLayout7Action = QAction('3d', self)
        self.ngLayout8Action = QAction('4panel', self)
        #############
        # ngPerspectiveMenu.addAction(self.ngLayout1Action)
        # ngPerspectiveMenu.addAction(self.ngLayout2Action)
        # ngPerspectiveMenu.addAction(self.ngLayout3Action)
        # ngPerspectiveMenu.addAction(self.ngLayout4Action)
        # ngPerspectiveMenu.addAction(self.ngLayout5Action)
        # ngPerspectiveMenu.addAction(self.ngLayout6Action)
        # # ngPerspectiveMenu.addAction(self.ngLayout7Action)
        # ngPerspectiveMenu.addAction(self.ngLayout8Action)
        #############
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

        # self.shader1Action = QAction('None', self)
        # self.shader1Action.triggered.connect(self.set_shader_none)
        # ngShaderMenu.addAction(self.shader1Action)

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
        # shaderActionGroup.addAction(self.shader1Action)
        shaderActionGroup.addAction(self.shaderDefaultAction)
        shaderActionGroup.addAction(self.shader2Action)
        shaderActionGroup.addAction(self.shader3Action)
        shaderActionGroup.addAction(self.shader4Action)
        # self.shader1Action.setCheckable(True)
        # self.shader1Action.setChecked(True)
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

        self.rescaleAction = QAction('Rescale...', self)
        self.rescaleAction.triggered.connect(self.rescale)
        actionsMenu.addAction(self.rescaleAction)

        # self.rechunkAction = QAction('Rechunk...', self)
        # self.rechunkAction.triggered.connect(self.rechunk)
        # actionsMenu.addAction(self.rechunkAction)

        configMenu = self.menu.addMenu('Configure')

        self.projectConfigAction = QAction('Configure Project...', self)
        self.projectConfigAction.triggered.connect(self._dlg_cfg_project)
        configMenu.addAction(self.projectConfigAction)

        self.appConfigAction = QAction('Configure Debugging...', self)
        self.appConfigAction.triggered.connect(self._dlg_cfg_application)
        configMenu.addAction(self.appConfigAction)

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
            try:
                log = json.dumps(cfg.webdriver.get_log(), indent=2)
            except:
                log = 'Webdriver is offline.'
            self.menuTextWebdriverLog.setText(log)

        menu = debugMenu.addMenu('Debug Dump')
        self.menuTextWebdriverLog = QTextEdit(self)
        self.menuTextWebdriverLog.setReadOnly(True)
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

        action = QAction('Export Zarr Command', self)
        action.triggered.connect(self.printExportInstructionsTIFF)
        helpPrintExportInstructions.addAction(action)

        action = QAction('Export TIFFs Command', self)
        action.triggered.connect(self.printExportInstructionsZarr)
        helpPrintExportInstructions.addAction(action)



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

        self.featuresAction = QAction('AlignEM-SWiFT Features', self)
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

        # action = QAction('Remod Help', self)
        # action.triggered.connect(lambda: self.html_resource(resource='remod.html', title='Help: Remod (beta)'))
        # helpMenu.addAction(action)

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
    #         # cfg.data.set_swim_window_global(float(cfg.pt._swimWindowControl.value()) / 100.)
    #         cfg.data.set_swim_1x1_custom_px(cfg.pt._swimWindowControl.value())

    def printExportInstructionsTIFF(self):
        work = os.getenv('WORK')
        user = os.getenv('USER')
        tiffs = os.path.join(cfg.data.dest(),'scale_1','img_src')
        self.hud.post(f'Use the follow command to copy-export full resolution TIFFs to another location on the filesystem:\n\n'
                      f'    rsync -atvr {tiffs} {user}@ls6.tacc.utexas.edu:{work}/data')


    def printExportInstructionsZarr(self):
        work = os.getenv('WORK')
        user = os.getenv('USER')
        zarr = os.path.join(cfg.data.dest(),'img_aligned.zarr','s1')
        self.hud.post(
            f'Use the follow command to copy-export full resolution Zarr to another location on the filesystem:\n\n'
            f'    rsync -atvr {zarr} {user}@ls6.tacc.utexas.edu:{work}/data\n\n'
            f'Note: AlignEM-SWIFT supports the opening and re-opening of arbitrary Zarr files in Neuroglancer')



    def _valueChangedWhitening(self):
        # logger.info('')
        caller = inspect.stack()[1].function
        # if caller != 'initControlPanel':
        if caller == 'main':
            val = float(cfg.pt.sb_whiteningControl.value())
            cfg.data.default_whitening = val
            self.tell('Signal Whitening is set to %.3f' % val)
            cfg.pt.updateDetailsPanel()

    def _valueChangedPolyOrder(self):
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if cfg.pt._polyBiasCombo.currentText() == 'None':
                cfg.data.default_poly_order = None
                self.tell('Corrective Polynomial Order is set to None')
            else:
                txt = cfg.pt._polyBiasCombo.currentText()
                index = cfg.pt._polyBiasCombo.findText(txt)
                val = index - 1
                cfg.data.default_poly_order = val
                self.tell('Corrective Polynomial Order is set to %d' % val)



    def _toggledAutogenerate(self) -> None:
        # logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if cfg.pt._toggleAutogenerate.isChecked():
                self.tell('Images will be generated automatically after alignment')
            else:
                self.tell('Images will not be generated automatically after alignment')

    def rechunk(self):
        # if self._isProjectTab():
        #     if cfg.data.is_aligned_and_generated():
        #         target = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's%d' % cfg.data.scale_val())
        #         _src = os.path.join(cfg.data.dest(), 'img_aligned.zarr', '_s%d' % cfg.data.scale_val())
        #     else:
        #         target = os.path.join(cfg.data.dest(), 'img_src.zarr', 's%d' % cfg.data.scale_val())
        #         _src = os.path.join(cfg.data.dest(), 'img_src.zarr', '_s%d' % cfg.data.scale_val())
        #
        #     dlg = RechunkDialog(self, target=target)
        #     if dlg.exec():
        #
        #         t_start = time.time()
        #
        #         logger.info('Rechunking...')
        #         chunkshape = cfg.data['data']['chunkshape']
        #         intermediate = "intermediate.zarr"
        #
        #         os.rename(target, _src)
        #         try:
        #             source = zarr.open(store=_src)
        #             self.tell('Configuring rechunking (target: %s). New chunk shape: %s...' % (target, str(chunkshape)))
        #             logger.info('Configuring rechunk operation (target: %s)...' % target)
        #             rechunked = rechunk(
        #                 source=source,
        #                 target_chunks=chunkshape,
        #                 target_store=target,
        #                 max_mem=100_000_000_000,
        #                 temp_store=intermediate
        #             )
        #             self.tell('Rechunk plan:\n%s' % str(rechunked))
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
        #         logger.info('Removing %s...' %intermediate)
        #         self.tell('Removing %s...' %intermediate)
        #         shutil.rmtree(intermediate, ignore_errors=True)
        #         shutil.rmtree(intermediate, ignore_errors=True)
        #
        #         logger.info('Removing %s...' %_src)
        #         self.tell('Removing %s...' %_src)
        #         shutil.rmtree(_src, ignore_errors=True)
        #         shutil.rmtree(_src, ignore_errors=True)
        #         self.hud.done()
        #
        #         t_end = time.time()
        #         dt = t_end - t_start
        #         z = zarr.open(store=target)
        #         info = str(z.info)
        #         self.tell('\n%s' %info)
        #
        #         self.tell('Rechunking Time: %.2f' % dt)
        #         logger.info('Rechunking Time: %.2f' % dt)
        #
        #         cfg.project_tab.initNeuroglancer()
        #
        #     else:
        #         logger.info('Rechunking Canceled')
        pass

    def initControlPanel(self):

        button_size = QSize(54, 16)

        ctl_lab_style = 'color: #ede9e8; font-size: 10px;'

        tip = """Sections marked for exclusion will not be aligned or used by SWIM in any way (like a dropped frame)."""
        self._lab_keep_reject = QLabel('Include:')
        self._lab_keep_reject.setStyleSheet(ctl_lab_style)
        self._lab_keep_reject.setToolTip(tip)
        self._skipCheckbox = ToggleSwitch()
        self._skipCheckbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._skipCheckbox.setToolTip(tip)
        self._skipCheckbox.setEnabled(False)
        self._skipCheckbox.stateChanged.connect(self._callbk_skipChanged)
        self._skipCheckbox.stateChanged.connect(lambda: cfg.pt.updateDetailsPanel())
        self._skipCheckbox.stateChanged.connect(self._callbk_unsavedChanges)

        self.labInclude = QLabel('Include\nSection:')
        self.labInclude.setStyleSheet('font-size: 8px; font-weight: 600;')

        self._w_skipCheckbox = HWidget(self.labInclude, self._skipCheckbox)
        self._w_skipCheckbox.layout.setAlignment(Qt.AlignCenter)

        self._btn_clear_skips = QPushButton('Reset')
        self._btn_clear_skips.setEnabled(False)
        self._btn_clear_skips.setStyleSheet("font-size: 10px;")
        self._btn_clear_skips.setToolTip(tip)
        self._btn_clear_skips.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_clear_skips.clicked.connect(self.clear_skips)
        self._btn_clear_skips.setFixedSize(button_size)

        tip = 'Go To Previous Section.'
        self._btn_prevSection = QPushButton()
        self._btn_prevSection.setObjectName('z-index-left-button')
        self._btn_prevSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_prevSection.setToolTip(tip)
        self._btn_prevSection.clicked.connect(self.layer_left)
        self._btn_prevSection.setFixedSize(QSize(18, 18))
        self._btn_prevSection.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))
        self._btn_prevSection.setEnabled(False)

        tip = 'Go To Next Section.'
        self._btn_nextSection = QPushButton()
        self._btn_nextSection.setObjectName('z-index-right-button')
        self._btn_nextSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_nextSection.setToolTip(tip)
        self._btn_nextSection.clicked.connect(self.layer_right)
        self._btn_nextSection.setFixedSize(QSize(18, 18))
        self._btn_nextSection.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))
        self._btn_nextSection.setEnabled(False)

        self._sectionChangeWidget = HWidget(self._btn_prevSection, self._btn_nextSection)
        self._sectionChangeWidget.layout.setAlignment(Qt.AlignCenter)

        tip = 'Go To Previous Scale.'
        self._scaleDownButton = QPushButton()
        self._scaleDownButton.setEnabled(False)
        self._scaleDownButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleDownButton.setToolTip(tip)
        self._scaleDownButton.clicked.connect(self.scale_down)
        self._scaleDownButton.setFixedSize(QSize(18, 18))
        self._scaleDownButton.setIcon(qta.icon("fa.arrow-down", color=ICON_COLOR))

        tip = 'Go To Next Scale.'
        self._scaleUpButton = QPushButton()
        self._scaleUpButton.setEnabled(False)
        self._scaleUpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleUpButton.setToolTip(tip)
        self._scaleUpButton.clicked.connect(self.scale_up)
        self._scaleUpButton.setFixedSize(QSize(18, 18))
        self._scaleUpButton.setIcon(qta.icon("fa.arrow-up", color=ICON_COLOR))

        self._scaleSetWidget = HWidget(self._scaleUpButton, self._scaleDownButton)
        self._scaleSetWidget.layout.setAlignment(Qt.AlignCenter)

        self._sectionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self._sectionSlider.setObjectName('z-index-slider')
        self._sectionSlider.setFocusPolicy(Qt.StrongFocus)
        self._sectionSlider.valueChanged.connect(self.jump_to_slider)

        tip = 'Jumpt to section #'
        self._jumpToLineedit = QLineEdit(self)
        self._jumpToLineedit.setFocusPolicy(Qt.ClickFocus)
        self._jumpToLineedit.setToolTip(tip)
        self._jumpToLineedit.setFixedSize(QSize(32, 16))
        self._jumpToLineedit.returnPressed.connect(self.jump_to_layer)
        # self._jumpToLineedit.returnPressed.connect(lambda: self.jump_to(int(self._jumpToLineedit.text())))

        self._btn_automaticPlayTimer = QPushButton()
        self._btn_automaticPlayTimer.setFixedSize(18, 18)
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        self.automaticPlayTimer = QTimer(self)
        self._btn_automaticPlayTimer.clicked.connect(self.startStopTimer)

        def onTimer():
            logger.info('')
            self.automaticPlayTimer.setInterval(int(1000 / self.spinbox_fps.value()))
            if cfg.data:
                if cfg.project_tab:
                    if self._sectionSlider.value() < len(cfg.data) - 1:
                        self.setZpos(cfg.data.zpos + 1)
                    else:
                        self.setZpos(0)
                        self.automaticPlayTimer.stop()
                        self._isPlayingBack = 0
                        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))

        self.automaticPlayTimer.timeout.connect(onTimer)
        self._sectionSliderWidget = QWidget()

        hbl = QHBoxLayout()
        hbl.setSpacing(0)
        hbl.setContentsMargins(2, 0, 2, 0)
        hbl.addWidget(self._btn_automaticPlayTimer)
        hbl.addWidget(self._sectionSlider)
        self._sectionSliderWidget.setLayout(hbl)

        # self.spinbox_fps = QLineEdit()
        self.spinbox_fps = QDoubleSpinBox()
        self.spinbox_fps.setFixedSize(QSize(50, 18))
        self.spinbox_fps.setMinimum(.1)
        self.spinbox_fps.setMaximum(20)
        self.spinbox_fps.setSingleStep(.2)
        self.spinbox_fps.setDecimals(1)
        self.spinbox_fps.setSuffix('fps')
        self.spinbox_fps.setValue(float(cfg.DEFAULT_PLAYBACK_SPEED))
        self.spinbox_fps.setToolTip('Paging Speed (frames/second)')
        self.spinbox_fps.clear()

        self._changeScaleCombo = QComboBox(self)
        self._changeScaleCombo.setFixedSize(QSize(132, 16))
        self._changeScaleCombo.setStyleSheet('font-size: 10px;')
        self._changeScaleCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._changeScaleCombo.currentTextChanged.connect(self.fn_scales_combobox)

        resLab = QLabel('Level / Downsampled Image Resolution')
        resLab.setStyleSheet('font-size: 8px; font-weight: 600;')
        scaleLabel = QLabel('Scale:')
        scaleLabel.setStyleSheet("font-size: 11px; font-weight: 600;")
        hw = HWidget(scaleLabel, self._changeScaleCombo, self._scaleSetWidget)
        hw.layout.setSpacing(8)
        self.scaleWidget = VWidget(hw)

        secLabel = QLabel('Section:')
        secLabel.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.sectionIndexWidget = HWidget(
            secLabel, self._jumpToLineedit,
            self._sectionChangeWidget,
            self._sectionSliderWidget,
            self.spinbox_fps,
            self._w_skipCheckbox
        )
        self.sectionIndexWidget.layout.setSpacing(8)

        self.navControls = HWidget(self.scaleWidget, self.sectionIndexWidget)
        self.navControls.layout.setSpacing(8)

        tip = """Align and generate all sections for the current scale_key"""
        # self._btn_alignAll = QPushButton(f"Align All {hotkey('A')}")
        self._btn_alignAll = QPushButton(f"Align All")
        self._btn_alignAll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._btn_alignAll.setEnabled(False)
        self._btn_alignAll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignAll.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignAll.clicked.connect(self.alignAll)

        tip = """Align and generate the current section only"""
        self._btn_alignOne = QPushButton('Align One')
        self._btn_alignOne.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._btn_alignOne.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignOne.setEnabled(False)
        self._btn_alignOne.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignOne.clicked.connect(self.alignGenerateOne)

        tip = """Align and generate current sections from the current through the end of the image stack"""
        self._btn_alignForward = QPushButton('Align Forward')
        self._btn_alignForward.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._btn_alignForward.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignForward.setEnabled(False)
        self._btn_alignForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignForward.clicked.connect(self.alignForward)

        self.startRangeInput = QLineEdit()
        self.startRangeInput.setAlignment(Qt.AlignCenter)
        self.startRangeInput.setFixedSize(30, 16)
        self.startRangeInput.setEnabled(False)

        self.endRangeInput = QLineEdit()
        self.endRangeInput.setAlignment(Qt.AlignCenter)
        self.endRangeInput.setFixedSize(30, 16)
        self.endRangeInput.setEnabled(False)

        tip = """The range of sections to align."""
        self.rangeInputWidget = HWidget(self.startRangeInput, QLabel(' : '), self.endRangeInput)
        self.rangeInputWidget.layout.setAlignment(Qt.AlignHCenter)
        self.rangeInputWidget.setMaximumWidth(140)
        self.rangeInputWidget.setToolTip(tip)

        tip = """Compute alignment and generate new images for range of sections"""
        self._btn_alignRange = QPushButton('Align Range')
        self._btn_alignRange.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._btn_alignRange.setEnabled(False)
        self._btn_alignRange.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignRange.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignRange.clicked.connect(self.alignRange)

        tip = """Do NOT align, only generate new output images for all sections based on the cumulative affine and output settings"""
        self._btn_regenerate = QPushButton('Regenerate All')
        self._btn_regenerate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._btn_regenerate.setEnabled(False)
        self._btn_regenerate.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_regenerate.clicked.connect(lambda: self.regenerate(scale=cfg.data.scale_key))
        self._btn_regenerate.setEnabled(False)

        self.gb_ctlActions = QGroupBox("Scale Actions")
        self.gb_ctlActions.setObjectName("gb_cpanel")
        self.gb_ctlActions.setStyleSheet("font-size: 9px;")

        self.w_range = HWidget(VWidget(QLabel('Range: '), HWidget(self.rangeInputWidget, self.rangeInputWidget)), self._btn_alignRange)
        self.w_range.layout.setAlignment(Qt.AlignHCenter)
        self.w_range.layout.setSpacing(2)

        self.newActionsWidget = HWidget(self._btn_alignAll,
                                        self._btn_alignForward,
                                        self._btn_alignOne,
                                        self.w_range,
                                        self._btn_regenerate
                                        )
        self.newActionsWidget.layout.setSpacing(4)
        self.newActionsWidget.setStyleSheet("font-size: 10px; font-weight: 600;")

        self.toolbar_cpanel = QToolBar()
        self.toolbar_cpanel.setFixedHeight(38)
        self.toolbar_cpanel.addWidget(self.navControls)
        self.toolbar_cpanel.addWidget(self.newActionsWidget)
        self.toolbar_cpanel.hide()

    def initUI(self):
        '''Initialize Main UI'''
        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)

        '''Headup Display'''
        self.hud = HeadupDisplay(self.app)
        self.hud.set_theme_dark()

        self.dw_thumbs = DockWidget('Tra./Ref. Thumbnails', self)
        self.dw_thumbs.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        # self.dw_thumbs.setFeatures(self.dw_hud.DockWidgetClosable | self.dw_hud.DockWidgetVerticalTitleBar)
        self.dw_thumbs.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        # self.dw_thumbs.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.dw_thumbs.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.dw_thumbs.setObjectName('Dock Widget Thumbnails')
        self.dw_thumbs.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #161c20;
                    font-weight: 600;
                    text-align: left;
                    padding: 0px;
                    margin: 0px;
                    border-width: 0px;
                }""")
        self.dw_thumbs.setWidget(QLabel('Null Widget'))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dw_thumbs)
        self.dw_thumbs.hide()

        self.dw_matches = DockWidget('Matches & Match Signals', self)
        self.dw_matches.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        # self.dw_thumbs.setFeatures(self.dw_hud.DockWidgetClosable | self.dw_hud.DockWidgetVerticalTitleBar)
        self.dw_matches.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        # self.dw_thumbs.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.dw_matches.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.dw_matches.setObjectName('Dock Widget Thumbnails')
        self.dw_matches.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #161c20;
                    font-weight: 600;
                    text-align: left;
                    padding: 0px;
                    margin: 0px;
                    border-width: 0px;
                }""")
        self.dw_matches.setWidget(QLabel('Null Widget'))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dw_matches)
        self.dw_matches.hide()


        def fn_vert_dock_locations_changed():
            logger.info('')
            if self.dw_hud.isVisible():
                self.setUpdatesEnabled(False)
                w = 180
                self.resizeDocks((self.dw_matches, self.dw_thumbs), (w, w), Qt.Horizontal)
                self.setUpdatesEnabled(True)

        self.dw_matches.dockLocationChanged.connect(fn_vert_dock_locations_changed)
        self.dw_thumbs.dockLocationChanged.connect(fn_vert_dock_locations_changed)



        self.dw_hud = DockWidget('HUD', self)
        def fn_dw_monitor_visChanged():
            if self.dw_hud.isVisible():
                self.setUpdatesEnabled(False)
                loc_hud = self.dockWidgetArea(self.dw_hud)
                # logger.info(f'dw_monitor location: {loc_hud}')
                if loc_hud in (1,2):
                    self.dw_hud.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dw_hud.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)

                loc_py = self.dockWidgetArea(self.dw_python)
                if loc_hud == loc_py:
                    if loc_hud in (4, 8):
                        # self.splitDockWidget(self.dw_hud, self.dw_python, Qt.Horizontal)
                        w = int(self.width() / 2)
                        self.resizeDocks((self.dw_hud, self.dw_python), (w, w), Qt.Horizontal)
                        # self.resizeDocks((self.dw_hud, self.dw_python),
                        #                  (self.dw_hud.sizeHint().height(), self.dw_hud.sizeHint().height()), Qt.Vertical)
                    elif loc_hud in (1, 2):
                        # self.splitDockWidget(self.dw_hud, self.dw_python, Qt.Vertical)
                        h = int(self.height() / 2)
                        self.resizeDocks((self.dw_hud, self.dw_python), (h, h), Qt.Vertical)
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
        vcenter = Qt.AlignmentFlag.AlignVCenter
        hcenter = Qt.AlignmentFlag.AlignHCenter
        center = Qt.AlignmentFlag.AlignCenter
        left = Qt.AlignmentFlag.AlignLeft
        right = Qt.AlignmentFlag.AlignRight

        self._processMonitorWidget = QWidget()
        self._processMonitorWidget.setStyleSheet('background-color: #1b2328; color: #f3f6fb; border-radius: 5px;')
        lab = QLabel('Process Monitor')
        lab.setStyleSheet('font-size: 9px; font-weight: 500; color: #141414;')
        lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 4px; margin-top: 4px;')
        vbl = QVBoxLayout()
        vbl.setSpacing(1)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lab, alignment=baseline)
        self._processMonitorWidget.setLayout(vbl)

        lab = QLabel('Details')
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #1418414;')
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
                    if cfg.data:
                        self.statusBar.showMessage('Note Saved!', 3000)
                        cfg.data.save_notes(text=self.notes.toPlainText())
                else:
                    cfg.settings['notes']['global_notes'] = self.notes.toPlainText()
                self.notes.update()

        self.notes = QTextEdit()
        self.notes.setMinimumWidth(64)
        self.notes.setObjectName('Notes')
        self.notes.setStyleSheet("""
            background-color: #ede9e8;
            color: #161c20;
            font-size: 11px;
            border-width: 0px;
            border-radius: 5px;
        """)
        self.notes.setPlaceholderText('Type any notes here...')
        self.notes.textChanged.connect(fn)
        self.dw_notes = DockWidget('Notes', self)


        def fn():
            logger.info('')
            if self. dw_notes.isVisible():
                self.setUpdatesEnabled(False)
                if self.dockWidgetArea(self.dw_notes) in (1,2):
                    self.dw_notes.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dw_notes.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
                self.setUpdatesEnabled(True)

        self.dw_notes.dockLocationChanged.connect(fn)


        # self.dw_notes.visibilityChanged.connect(
        #     lambda: self.tbbNotes.setText((' Hide', ' Notes')[self.dw_notes.isHidden()]))
        # self.dw_notes.visibilityChanged.connect(lambda: )
        self.dw_notes.visibilityChanged.connect(lambda: self.tbbNotes.setToolTip(
            ('Hide Notes Tool Window', 'Show Notes Tool Window')[self.dw_notes.isHidden()]))
        # self.dw_notes.visibilityChanged.connect(self.dataUpdateResults()) #???
        self.dw_notes.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        self.dw_notes.setStyleSheet("""
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
        self.dw_notes.setWidget(self.notes)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dw_notes)
        self.dw_notes.hide()

        tip = 'Show/Hide Contrast and Brightness Shaders'
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

        # #0210
        # self.detailsScales = QLabel()
        # self.btnDetailsScales = QPushButton('Hide Scales')
        # self.btnDetailsScales.setFixedWidth(dSize)
        # self.btnDetailsScales.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))
        # def fn():
        #     self.detailsScales.setVisible(not self.detailsScales.isVisible())
        #     if self.detailsScales.isHidden():
        #         label, icon = ' Scales', 'fa.caret-right'
        #     else:
        #         label, icon = 'Hide Scales', 'fa.caret-down'
        #     self.btnDetailsScales.setIcon(qta.icon(icon, color='#f3f6fb'))
        #     self.btnDetailsScales.setText(label)
        # self.btnDetailsScales.clicked.connect(fn)
        # self.detailsScales.setWordWrap(True)
        # self.detailsScales.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.detailsScales.setStyleSheet("""font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace; font-size: 11px;""")
        # # self.detailsScales.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum) #???
        # self.detailsScales.setFixedWidth(dSize)
        # # self.detailsScales.setReadOnly(True)
        #
        # self.detailsSkips = QLabel()
        # self.btndetailsSkips = QPushButton('Hide Rejects')
        # self.btndetailsSkips.setFixedWidth(dSize)
        # self.btndetailsSkips.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))
        # def fn():
        #     self.detailsSkips.setVisible(not self.detailsSkips.isVisible())
        #     if self.detailsSkips.isHidden(): label, icon = ' Rejects', 'fa.caret-right'
        #     else:                            label, icon = 'Hide Rejects', 'fa.caret-down'
        #     self.btndetailsSkips.setIcon(qta.icon(icon, color='#f3f6fb'))
        #     self.btndetailsSkips.setText(label)
        # self.btndetailsSkips.clicked.connect(fn)
        # self.detailsSkips.setWordWrap(True)
        # self.detailsSkips.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.detailsSkips.setStyleSheet("""font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;""")
        # self.detailsSkips.setFixedWidth(dSize)
        # # self.detailsSkips.setReadOnly(True)

        # self.detailsTensor = QWidget()
        # self.detailsTensor.setFixedWidth(dSize)
        # self.detailsTensorLab = QLabel()
        # self.detailsTensorLab.setWordWrap(True)
        # # self.detailsTensorLab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.detailsTensorLab.setStyleSheet("""
        # font-family: Consolas, 'Andale Mono', 'Ubuntu Mono', monospace;
        # color: #f3f6fb;
        # font-size: 10px;""")
        # self.detailsTensorLab.hide()
        # self.btnDetailsTensor = QPushButton('Tensor')
        # self.btnDetailsTensor.setIcon(qta.icon('fa.caret-right', color='#f3f6fb'))
        # def fn():
        #     logger.info('')
        #     self.detailsTensorLab.setVisible(not self.detailsTensorLab.isVisible())
        #     if self.detailsTensorLab.isHidden():
        #         label, icon = ' Tensor', 'fa.caret-right'
        #     else:
        #         label, icon  = 'Hide Tensor', 'fa.caret-down'
        #         self.detailsTensorLab.setText(json.dumps(cfg.tensor.spec().to_json(), indent=2))
        #     self.btnDetailsTensor.setIcon(qta.icon(icon, color='#f3f6fb'))
        #     self.btnDetailsTensor.setText(label)
        # self.btnDetailsTensor.setFixedWidth(dSize + 26)
        # self.btnDetailsTensor.clicked.connect(fn)
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # vbl.addWidget(self.btnDetailsTensor)
        # vbl.addWidget(self.detailsTensorLab)
        # self.detailsTensor.setLayout(vbl)

        '''Tabs Global Widget'''
        self.globTabs = QTabWidget(self)
        self.globTabs.setTabBarAutoHide(True)
        self.globTabs.setTabShape(QTabWidget.Triangular)
        self.globTabs.tabBar().setExpanding(True)
        self.globTabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.globTabs.setUsesScrollButtons(True)
        # self.globTabs.setStyleSheet("""background-color: #ede9e8""")
        # self.globTabs.setContentsMargins(4,4,4,4)
        self.globTabs.setContentsMargins(0, 0, 0, 0)
        # self.globTabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.globTabs.tabBar().setStyleSheet("""
        QTabBar::close-button {

            image: url(src/resources/close-tab-light.png);
            subcontrol-origin: padding;
            subcontrol-position: right;
            padding: 6px;
        }
        QTabBar::close-button:!selected {

            image: url(src/resources/close-tab-dark.png);
            subcontrol-origin: padding;
            subcontrol-position: right;
            padding: 6px;
        }

        QTabBar::tab {
            background-color: qlineargradient(x1:0, y1:0, x2:.5, y2:1, stop:0 #141414, stop:1 #222222);
            color: #f3f6fb;
            min-width: 120px;
            height: 18px;
            padding-left:0px;
            padding-right:0px;
            font-size: 10px;
            border-width: 0px;
        }
        QTabBar::tab:selected
        {
            font-weight: 600;
        }
        QTabBar::tab:!selected
        {
            color: #161c20;
            font-weight: 600;
        }
        """)

        # self.globTabs.tabBar().setStyleSheet("""
        #         QTabBar::close-button {
        #             image: url(src/resources/close-tab.png);
        #             subcontrol-origin: padding;
        #             subcontrol-position: right;
        #             width: 10px;
        #             height: 10px;
        #          }
        # 
        #         QTabBar::tab {
        #             height: 13px;
        #             min-width: 100px;
        #             max-width: 240px;
        #             font-size: 10px;
        #             font-weight: 600;
        #             
        #             /*border: 1px solid #ede9e8;*/
        #             
        #             border-bottom-left-radius: 1px;
        #             border-bottom-right-radius: 1px;
        #             border-top-left-radius: 2px;
        #             border-top-right-radius: 6px;
        #             border: 1px solid #ede9e8;
        #             background-color: #b3e6b3;
        #             
        #             
        #             padding-left: 3px;
        #             padding-right: 3x;
        #             padding-top: 1px;
        #             padding-bottom: 1px;
        #             
        #             border-bottom-width: 0px;
        #             border-left-width: 0px;
        # 
        #         }
        #         QTabBar::tab:selected
        #         {
        #             font-weight: 600;
        #             color: #f3f6fb;
        #             background-color: #339933;
        #         }
        #         """)

        self.globTabs.tabBar().setElideMode(Qt.ElideMiddle)
        self.globTabs.setElideMode(Qt.ElideMiddle)
        self.globTabs.setMovable(True)
        self.globTabs.setDocumentMode(True)
        self.globTabs.setTabsClosable(True)
        self.globTabs.setObjectName('globTabs')
        self.globTabs.tabCloseRequested[int].connect(self._onGlobTabClose)
        self.globTabs.currentChanged.connect(self._onGlobTabChange)

        # self.pythonConsole = PythonConsole()
        self.pythonConsole = PythonConsoleWidget()
        # self.pythonConsole.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pythonConsole.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # self.pythonConsole.resize(QSize(600,600))

        self.pythonConsole.setStyleSheet("""
        font-size: 10px;
        background-color: #f3f6fb;
        color: #161c20;
        font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
        border-radius: 5px;
        """)

        self.dw_python = DockWidget('Python', self)
        self.dw_python.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        def fn_dw_python_visChanged():
            caller = inspect.stack()[1].function

            # logger.critical(f'caller: {caller}')
            if self. dw_python.isVisible():
                self.setUpdatesEnabled(False)
                loc_py = self.dockWidgetArea(self.dw_python)
                if loc_py in (1,2):
                    self.dw_python.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dw_python.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)

                loc_hud = self.dockWidgetArea(self.dw_hud)
                # logger.critical(f"loc_py = {loc_py}, loc_hud = {loc_hud}")
                if loc_py == loc_hud:
                    if loc_py in (4, 8):
                        self.splitDockWidget(self.dw_hud, self.dw_python, Qt.Horizontal)
                        w = int(self.width() / 2)
                        # logger.critical(f"w = {w}")
                        self.resizeDocks((self.dw_hud, self.dw_python), (w, w), Qt.Horizontal)
                        # self.resizeDocks((self.dw_hud, self.dw_python), (self.dw_python.sizeHint().height(), self.dw_python.sizeHint().height()), Qt.Vertical)
                    elif loc_py in (1, 2):
                        self.splitDockWidget(self.dw_hud, self.dw_python, Qt.Vertical)
                        h = int(self.height() / 2)
                        self.resizeDocks((self.dw_hud, self.dw_python), (h, h), Qt.Vertical)
                self.setUpdatesEnabled(True)

        self.dw_python.dockLocationChanged.connect(fn_dw_python_visChanged)
        self.dw_python.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
        # self.dw_python.visibilityChanged.connect(lambda: self.tbbPython.setToolTip(('Hide Python Console Tool Window', 'Show Python Console Tool Window')[self.dw_python.isHidden()]))
        # self.dw_python.setStyleSheet("""QDockWidget::title {
        #     text-align: left; /* align the text to the left */
        #     background: #daebfe;
        #     color: #161c20;
        #     font-weight: 600;
        # }""")
        self.dw_python.setStyleSheet("""
                QDockWidget {color: #161c20;}
                QDockWidget::title {
                            background-color: #daebfe;
                            font-weight: 600;
                            text-align: left;
                            padding: 0px;
                            margin: 0px;
                            border-width: 0px;
                        }""")
        self.dw_python.setWidget(self.pythonConsole)
        # def fn():
        #     width = int(cfg.main_window.width() / 2)
        #     self.pythonConsole.resize(QSize(width, 90))
        #     self.pythonConsole.update()
        # self.dw_python.visibilityChanged.connect(fn)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_python)
        self.dw_python.hide()



        self.dw_snr = DockWidget('SNR', self)
        self.dw_snr.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        def fn_dw_snr_visChanged():
            self.setUpdatesEnabled(False)
            caller = inspect.stack()[1].function

            # logger.critical(f'caller: {caller}')
            if self. dw_snr.isVisible():
                loc_py = self.dockWidgetArea(self.dw_snr)
                if loc_py in (1,2):
                    self.dw_snr.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
                else:
                    self.dw_snr.setFeatures(
                        QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)

                # self.splitDockWidget(self.dw_hud, self.dw_snr, Qt.Vertical)
                # self.splitDockWidget(self.dw_python, self.dw_snr, Qt.Vertical)
            self.setUpdatesEnabled(True)

        self.dw_snr.dockLocationChanged.connect(fn_dw_snr_visChanged)
        self.dw_snr.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetVerticalTitleBar)
        self.dw_snr.setStyleSheet("""
                QDockWidget {color: #161c20;}
                QDockWidget::title {
                            background-color: #ffcccb;
                            font-weight: 600;
                            text-align: left;
                            padding: 0px;
                            margin: 0px;
                            border-width: 0px;
                        }""")

        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_snr)
        self.dw_snr.hide()



        '''Documentation Panel'''
        self.browser_web = QWebEngineView()
        self._buttonExitBrowserWeb = QPushButton()
        self._buttonExitBrowserWeb.setFixedSize(18, 18)
        self._buttonExitBrowserWeb.setIcon(qta.icon('fa.arrow-left', color=ICON_COLOR))
        self._buttonExitBrowserWeb.setStyleSheet('font-size: 9px;')
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
        buttonBrowserBack.setIcon(qta.icon('fa.arrow-left', color=ICON_COLOR))

        buttonBrowserForward = QPushButton()
        buttonBrowserForward.setToolTip('Go Forward')
        buttonBrowserForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserForward.clicked.connect(browser_forward)
        buttonBrowserForward.setFixedSize(QSize(20, 20))
        buttonBrowserForward.setIcon(qta.icon('fa.arrow-right', color=ICON_COLOR))

        buttonBrowserRefresh = QPushButton()
        buttonBrowserRefresh.setToolTip('Refresh')
        buttonBrowserRefresh.setIcon(qta.icon("fa.refresh", color=cfg.ICON_COLOR))
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
        button3demCommunity.setStyleSheet('font-size: 10px;')
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


        self.test_widget = QLabel()
        self.test_widget.setFixedSize(40,40)
        self.test_widget.setStyleSheet("background-color: #000000;")


        self.globTabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sw_pbar.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # self.addToolBar(self.toolbar)



        # self.globTabsAndCpanel = VWidget(self.toolbar, self.globTabs, self.cpanel, self.sw_pbar)
        self.addToolBar(self.toolbar)
        # self.globTabsAndCpanel = VWidget(self.globTabs, self.cpanel, self.sw_pbar)
        # self.globTabsAndCpanel = VWidget(self.globTabs, self.sa_cpanel, self.sw_pbar)
        self.globTabsAndCpanel = VWidget(self.globTabs, self.toolbar_cpanel, self.sw_pbar)
        self.globTabsAndCpanel.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setCentralWidget(self.globTabsAndCpanel)

        # self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks)
        self.setDockOptions(QMainWindow.AnimatedDocks)


    def setCpanelVisibility(self, b):
        # self.sa_cpanel.setVisible(b)
        self.toolbar_cpanel.setVisible(b)
        # pass




    def setControlPanelData(self):
        logger.info('')
        if self._isProjectTab():
            cfg.pt._swimWindowControl.setText(str(getData(f'data,defaults,{cfg.data.scale_key},swim-window-px')[0]))
            cfg.pt._swimWindowControl.setValidator(QIntValidator(0, cfg.data.image_size()[0]))
            cfg.pt.sb_whiteningControl.setValue(float(getData('data,defaults,signal-whitening')))
            cfg.pt.sb_SWIMiterations.setValue(int(getData('data,defaults,swim-iterations')))

            poly = getData('data,defaults,corrective-polynomial')
            if (poly == None) or (poly == 'None'):
                cfg.pt._polyBiasCombo.setCurrentText('None')
            else:
                # cfg.pt._polyBiasCombo.setCurrentText(str(poly))
                cfg.pt._polyBiasCombo.setCurrentIndex(int(poly) + 1)

            cfg.pt._bbToggle.setChecked(bool(getData(f'data,defaults,bounding-box')))

            try:    cfg.pt._bbToggle.setChecked(cfg.data.use_bb())
            except: logger.warning('Bounding Box Toggle Failed to Update')

            cfg.pt.updateDetailsPanel()



    def initLaunchTab(self):
        self._launchScreen = OpenProject()
        self.globTabs.addTab(self._launchScreen, 'Project Manager')
        self.globTabs.tabBar().setTabButton(0, QTabBar.RightSide,None)
        self._setLastTab()

    def get_application_root(self):
        return Path(__file__).parents[2]

    def initWidgetSpacing(self):
        logger.info('')
        self.hud.setContentsMargins(0, 0, 0, 0)
        self._tool_hstry.setMinimumWidth(128)
        # cfg.project_tab._transformationWidget.setFixedWidth(248)
        # cfg.project_tab._transformationWidget.setFixedSize(248,100)

    def initStatusBar(self):
        logger.info('')
        # self.statusBar = self.statusBar()
        self.statusBar = QStatusBar()
        self.statusBar.setFixedHeight(16)
        self.statusBar.setStyleSheet("""
            font-size: 10px;
            color: #161c20;
            background-color: #ede9e8;
            margin: 0px;
            padding: 0px;
        """)
        # self.statusBar.setStyleSheet("""
        #         font-size: 10px;
        #         font-weight: 600;
        #         background-color: #161c20;
        #         color: #f3f6fb;
        #         margin: 0px;
        #         padding: 0px;
        #         """)
        self.setStatusBar(self.statusBar)

    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(14)
        # self.pbar.setStyleSheet("font-size: 9px; font-weight: 600;")
        self.pbar.setStyleSheet("font-size: 9px;")
        self.pbar.setTextVisible(True)
        # font = QFont('Arial', 12)
        # font.setBold(True)
        # self.pbar.setFont(font)
        # self.pbar.setFixedWidth(400)
        # self.sw_pbar = QWidget(self)
        self.sw_pbar = QStackedWidget(self)
        self.sw_pbar.setMaximumHeight(16)
        self.sw_pbar.setAutoFillBackground(True)
        self.pbar_cancel_button = QPushButton('Stop')
        self.pbar_cancel_button.setFixedSize(42, 16)
        self.pbar_cancel_button.setIconSize(QSize(14, 14))
        self.pbar_cancel_button.setToolTip('Terminate Pending Multiprocessing Tasks')
        self.pbar_cancel_button.setIcon(qta.icon('mdi.cancel', color=cfg.ICON_COLOR))
        self.pbar_cancel_button.setStyleSheet("""font-size: 9px;""")
        self.pbar_cancel_button.clicked.connect(self.forceStopMultiprocessing)
        self.pbarLabel = QLabel('Task... ')
        self.pbarLabel.setStyleSheet("""font-size: 9px;font-weight: 600;""")

        self.widgetPbar = HWidget(self.pbarLabel, self.pbar, self.pbar_cancel_button)
        self.widgetPbar.layout.setContentsMargins(4, 0, 4, 0)
        self.widgetPbar.layout.setSpacing(4)

        self.w_pbarUnavailable = QLabel('GUI Progress Bar Unavailable. See Progress in Terminal.')
        self.w_pbarUnavailable.setFixedHeight(18)
        self.w_pbarUnavailable.setAlignment(Qt.AlignCenter)
        self.w_pbarUnavailable.setStyleSheet("""font-size: 12px; font-weight: 600; background-color: #161c20; color: #f3f6fb;""")

        self.sw_pbar.addWidget(self.widgetPbar)
        self.sw_pbar.addWidget(self.w_pbarUnavailable)
        self.sw_pbar.setCurrentIndex(0)

        # self.statusBar.addPermanentWidget(self.sw_pbar)
        self.hidePbar()

    def forceStopMultiprocessing(self):
        cfg.CancelProcesses = True
        cfg.event.set()

    def setPbarMax(self, x):
        self.pbar.setMaximum(x)

    def setNoPbarMessage(self, b):
        self.setUpdatesEnabled(False)
        if b:
            self.sw_pbar.setCurrentIndex(1)
            self.sw_pbar.show()
        else:
            self.sw_pbar.setCurrentIndex(0)
            self.sw_pbar.hide()
        self.setUpdatesEnabled(True)
        QApplication.processEvents()



    def updatePbar(self, x=None):
        caller = inspect.stack()[1].function
        # logger.critical(f"caller: {caller}")
        if x == None: x = cfg.nProcessDone
        self.pbar.setValue(x)
        try:
            if self._isProjectTab():
                if caller == "collect_results":
                    if "Transforms" in self.pbar.text():
                        if self.dw_matches:
                            # else:
                            self.updateCorrSignalsDrawer(z=x - 1)
                            self.setTargKargPixmaps(z=x - 1)
                    # elif "Copy-converting" in self.pbar.text():
                    #     # if cfg.pt._tabs.currentIndex() == 0:
                    #     if x%10 == 10:
                    #         logger.info(f'Displaying NG alignment at z={x}')
                    #         cfg.emViewer.initViewerAligned(z=x)
                    #         # cfg.emViewer.

        except:
            print_exception()
        finally:
            QApplication.processEvents()

    def setPbarText(self, text: str):
        # logger.critical('')
        # logger.critical(f'cfg.nTasks = {cfg.nProcessSteps}, cfg.nCompleted = {cfg.nProcessDone}')
        self.pbar.setFormat('(%p%) ' + text)
        # self.pbarLabel.setText('Processing (%d/%d)...' % (cfg.nProcessDone, cfg.nProcessSteps))
        self.pbarLabel.setText('(Task %d/%d)' % (cfg.nProcessDone, cfg.nProcessSteps))
        # logger.info('Processing (%d/%d)...' % (cfg.nProcessDone, cfg.nProcessSteps))
        # self.repaint()
        QApplication.processEvents()

    # def showZeroedPbar(self, set_n_processes=None, cancel_processes=None):
    def showZeroedPbar(self, set_n_processes=None, pbar_max=None):
        # '''
        # Note:
        # pbar_max is set by mp queue for all multiprocessing functions
        # '''
        # caller = inspect.stack()[1].function
        # # logger.critical(f'caller = {caller}, set_n_processes = {set_n_processes}')
        # cfg.CancelProcesses = False #0602+
        # if set_n_processes and (set_n_processes > 1):
        #     # logger.critical('Resetting # tasks...')
        #     cfg.nProcessSteps = set_n_processes
        #     cfg.nProcessDone = 0
        #     self.pbarLabel.show()
        # else:
        #     self.pbarLabel.hide()
        # # if cancel_processes:
        # #     cfg.CancelProcesses = True
        # #     self.pbar_cancel_button.hide()
        # # else:
        # #     self.pbar_cancel_button.show()
        # # logger.critical(f'cfg.nProcessSteps = {cfg.nProcessSteps}, cfg.nProcessDone = {cfg.nProcessDone}')
        # if pbar_max:
        #     self.pbar.setMaximum(pbar_max)
        # self.pbar.setValue(0)
        # self.setPbarText('Preparing Tasks...')
        # self.sw_pbar.show()
        # QApplication.processEvents()
        pass

    def hidePbar(self):
        # logger.info('')
        self.pbarLabel.setText('')
        self.sw_pbar.hide()
        self.sw_pbar.setCurrentIndex(0)
        self.statusBar.clearMessage()  # Shoehorn
        QApplication.processEvents()

    def back_callback(self):
        logger.info("Returning Home...")
        self.viewer_stack_widget.setCurrentIndex(0)

    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self._hstry_listWidget:
            menu = QMenu()
            self.history_view_action = QAction('View')
            self.history_view_action.setToolTip('View this alignment as a tree view')
            self.history_view_action.triggered.connect(self.view_historical_alignment)
            self.history_swap_action = QAction('Swap')
            self.history_swap_action.setToolTip('Swap the settings of this historical alignment '
                                                'with your current s settings')
            self.history_swap_action.triggered.connect(self.swap_historical_alignment)
            self.history_rename_action = QAction('Rename')
            self.history_rename_action.setToolTip('Rename this file')
            self.history_rename_action.triggered.connect(self.rename_historical_alignment)
            self.history_delete_action = QAction('Delete')
            self.history_delete_action.setToolTip('Delete this file')
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


    def get_dw_monitor(self):
        for i, dock in enumerate(cfg.mw.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Head-up Display':
                return self.children()[i]

    def get_dw_notes(self):
        for i, dock in enumerate(cfg.mw.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Notes':
                return self.children()[i]

    # def mousePressEvent(self, event):
    #     if event.button() == Qt.LeftButton:
    #         self._old_pos = event.pos()
    #
    # def mouseReleaseEvent(self, event):
    #     if event.button() == Qt.LeftButton:
    #         self._old_pos = None
    #
    # def mouseMoveEvent(self, event):
    #     if not self._old_pos:
    #         return
    #     delta = event.pos() - self._old_pos
    #     self.move(self.pos() + delta)


    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)
        # if DEV:
        #     logger.info(f'caller: {caller_name()}')
        logger.info(f'{event.key()} ({event.text()} / {event.nativeVirtualKey()} / modifiers: {event.nativeModifiers()}) was pressed!')
        # if ((event.key() == 77) and (event.nativeModifiers() == 1048840)) \
        #         or ((event.key() == 16777249) and (event.nativeModifiers() == 264)):
        #     self.enterExitManAlignMode()
        #     return
        #Prev...
        # if (event.key() == 77) and (event.nativeModifiers() == 1048840):
        #     self.enterExitManAlignMode()
        #     return
        # if (event.key() == 16777249) and (event.nativeModifiers() == 264):
        #     self.enterExitManAlignMode()
        #     return
        # M Key: event.key(): 77 <class 'int'>
        # Command key modifier: event.nativeModifiers(): 1048840 <class 'int'>



        if event.key() == Qt.Key_Escape:
            if self.isMaximized():
                self.showNormal()
        elif event.key() == Qt.Key_F11:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        elif event.key() == Qt.Key_R:
            self.refreshTab()

        elif event.key() == Qt.Key_Space:
            if self._isProjectTab():
                cfg.pt._tabs.setCurrentIndex(0)


        # elif event.key() == Qt.Key_M:
        #     self.enterExitManAlignMode()
        # r = 82
        # m = 77
        # k = 75
        # p = 80
        elif event.key() == Qt.Key_K:
            if self._isProjectTab():
                self.skip_change_shortcut()

        elif event.key() == Qt.Key_P:
            self.a_python.trigger()
            # self.setdw_python(not self.tbbPython.isChecked())

        elif event.key() == Qt.Key_H:
            self.a_monitor.trigger()
            # self.setdw_hud(not self.tbbHud.isChecked())

        elif event.key() == Qt.Key_N:
            self.a_notes.trigger()
            # self.setdw_notes(not self.tbbNotes.isChecked())

        elif event.key() == Qt.Key_T:
            self.a_thumbs.trigger()
            # self.setdw_thumbs(not self.tbbThumbnails.isChecked())

        elif event.key() == Qt.Key_M:
            self.a_matches.trigger()
            # self.setdw_matches(not self.tbbMatches.isChecked())

        elif event.key() == Qt.Key_S:
            self.save()

        elif event.key() == Qt.Key_D:
            if self._isProjectTab():
                self.detachNeuroglancer()

        # elif event.key() == Qt.Key_A:
        #     self.alignAll()

        elif event.key() == Qt.Key_B:
            if self._isProjectTab():
                cfg.pt.blink_main_fn()

            # cfg.project_tab.blinkToggle.setChecked(not cfg.project_tab.blinkToggle.isChecked())

        # elif event.key() == Qt.Key_V:
        #     self.enterExitManAlignMode()

        elif event.key() == Qt.Key_Up:
            if self._isProjectTab():
                if cfg.pt._tabs.currentIndex() in (0,1):
                    self.incrementZoomIn()

        elif event.key() == Qt.Key_Down:
            if self._isProjectTab():
                if cfg.pt._tabs.currentIndex() in (0, 1):
                    self.incrementZoomOut()

        elif event.key() == Qt.Key_Slash:
            if self._isProjectTab():      
                if cfg.pt._tabs.currentIndex() == 1:
                    logger.info(f"Qt.Key_Slash was pressed, tra_ref_toggle={cfg.data['state']['tra_ref_toggle']}")
                    if cfg.data['state']['tra_ref_toggle'] == 1:
                        cfg.pt.set_reference()
                    else:
                        cfg.pt.set_transforming()

        elif event.key() == Qt.Key_Delete:
            if self._isOpenProjTab():
                self._getTabObject().delete_projects()

        # elif event.key() == Qt.Key_Shift:
        #     if self._isProjectTab():
        #         cur = cfg.pt._tabs.currentIndex()
        #         cfg.pt._tabs.setCurrentIndex((cur + 1) % 5)

        # elif event.key() == Qt.Key_Shift:
        # elif event.key() == Qt.Key_M:
        #     # logger.info('Shift Key Pressed!')
        #     if self._isProjectTab():
        #         if getData('state,viewer_mode') == 'series_as_stack':
        #             cfg.pt.configure_or_stack(selection='configure')
        #
        #         elif getData('state,viewer_mode') == 'series_with_regions':
        #             cfg.pt.configure_or_stack(selection='stack')


                # if cfg.project_tab._tabs.currentIndex == 0:
                #     (cfg.project_tab.cl_tra.setChecked,
                #      cfg.project_tab.cl_ref.setChecked)[
                #         cfg.project_tab.cl_tra.isChecked](True)

        # elif event.key() == Qt.Key_Tab:
        #     logger.info('')
        #     if self._isProjectTab():
        #         new_index = (cfg.project_tab._tabs.currentIndex()+1)%4
        #         logger.info(f'new index: {new_index}')
        #         cfg.project_tab._tabs.setCurrentIndex(new_index)





        # # left arrow key = 16777234
        # elif event.key() == 16777234:
        #     self.layer_left()
        #
        # # right arrow key = 16777236
        # elif event.key() == 16777236:
        #     self.layer_right()


        # left arrow key = 16777234
        elif event.key() == 16777234:
            self.layer_left()

        # right arrow key = 16777236
        elif event.key() == 16777236:
            self.layer_right()

        # self.keyPressed.emit(event)




    #
    # def on_key(self, event):
    #     print('event received @ MainWindow')
    #     if event.key() == Qt.Key_Space:
    #         logger.info('Space key was pressed')

        # if event.key() == Qt.Key_M:
        #     logger.info('M key was pressed')

class DockWidget(QDockWidget):
    hasFocus = Signal([QDockWidget])

    def __init__(self, text, parent=None):
        super().__init__(text)
        self.setObjectName(text)
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)

    def event(self, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == 1:
            self.hasFocus.emit(self)
            logger.info(f'Emission from {self.objectName()}')
        return super().event(event)




class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # self.setStyleSheet("background-color: #000000;")
        # self.setAutoFillBackground(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

class ExpandingVWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # self.setStyleSheet("background-color: #000000;")
        # self.setAutoFillBackground(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


class VerticalLabel(QLabel):

    def __init__(self, text, bg_color=None, font_color=None, font_size=None, *args):
        QLabel.__init__(self, text, *args)

        self.text = text
        self.setStyleSheet("font-size: 12px;")
        font = QFont()
        font.setBold(True)
        self.setFont(font)
        style = ''
        if bg_color:
            style += f'background-color: {bg_color};'
        if font_color:
            style += f'color: {font_color};'
        if font_size:
            style += f'font-size: {str(font_size)};'
        if style != '':
            self.setStyleSheet(style)


class NullWidget(QLabel):
    def __init__(self, *args):
        QLabel.__init__(self, *args)
        self.setText('Null Widget')
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
            # but it's best to be safe.
            return
        self.adjusted_to_size = size

        full_width = size.width()
        full_height = size.height()
        width = min(full_width, full_height * self.ratio)
        height = min(full_height, full_width / self.ratio)

        h_margin = round((full_width - width) / 2)
        v_margin = round((full_height - height) / 2)

        self.setContentsMargins(h_margin, v_margin, h_margin, v_margin)

'''
#indicators css

QGroupBox::indicator:unchecked {
    image: url(:/images/checkbox_unchecked.png);
}

https://stackoverflow.com/questions/47206667/collect-all-docked-widgets-and-their-locations
for dock in cfg.mw.findChildren(QDockWidget):
    print(dock.windowTitle())


area = cfg.mw.dockWidgetArea(dock)
if area == QtCore.Qt.LeftDockWidgetArea:
    print(dock.windowTitle(), '(Left)')
elif area == QtCore.Qt.RightDockWidgetArea:
    print(dock.windowTitle(), '(Right)')



for i,dock in enumerate(cfg.mw.findChildren(QDockWidget)):
    title = dock.windowTitle()
    area = cfg.mw.dockWidgetArea(dock)
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

Q: What is AlignEM-SWiFT?
A: AlignEM-SWiFt is a software tool specialized for registering electron micrographs. It is
   able to generate scale_key image hierarchies, compute affine transforms, and generate aligned
   images using multi-image rendering.

Q: Can AlignEM-SWiFT be used to register or "align" non-EM images?
A: Yes, but its forte is aligning EM images which tend to be large, and greyscale. AlignEM-SWIFT
   provides functionality for downscaling and the ability to pass alignment results (affines)
   from lower scale_key levels to higher ones.

Q: What are scales?
A: In AlignEM-SWiFT a "scale_key" means a downsampled (or decreased resolution) series of images.

Q: Why should data be scaled? Is it okay to align the full resolution series with brute force?
A: You could, but EM images tend to run large. A more efficient workflow is to:
   1) generate a hierarchy of downsampled images from the full resolution images
   2) align the lowest resolution images first
   3) pass the computed affines to the scale_key of next-highest resolution, and repeat
      until the full resolution images are in alignment. In these FAQs this is referred to
      as "climbing the scale_key hierarchy""

Q: Why do SNR values not necessarily increase as we "climb the scale_key hierarchy"?
A: SNR values returned by SWIM are a relative metric which depend on image resolution. It is
   therefore most useful when comparing the relative alignment quality of aligned image
   pairs at the same scale_key.

Q: Why are the selected manual correlation regions not mutually independent? In other words,
   why does moving or removing an argument to SWIM affect the signal-to-noise ratio and
   resulting correlation signals of the other selected SWIM regions?
A:

Q: What is Neuroglancer?
A: Neuroglancer is an open-source WebGL and typescript-based web application for displaying
   volumetric data. AlignEM-SWiFT uses a Chromium-based API called QtWebEngine together
   with the Neuroglancer Python API to render large volumetric data efficiently and conveniently
   within the application window.

Q: What is Zarr?
A: Zarr is an open-source format for the storage of chunked, compressed, N-dimensional arrays
   with an interface similar to NumPy. It has a Nature Methods paper:
   https://www.nature.com/articles/s41592-021-01326-w

Q: Why is AlignEM-SWiFT so swift?
A: For several reasons:
   1) Time-intensive processes are executed in parallel.
   2) Data scaling, SWIM alignment, and affine processing functions are all implemented
      in highly efficient C code written by computer scientist Arthur Wetzel.
   3) Fast Fourier Transform is a fast algorithm.

Q: How many CPUs or "cores" does AlignEM-SWiFT use?
A: By default, as many cores as the system has available.

Q: What file types are supported?
A: Currently, only images formatted as TIFF.

Q: Where can I learn more about the principles of Signal Whitening Fourier Transform Image Matching?
A: https://mmbios.pitt.edu/images/ScientificMeetings/MMBIOS-Aug2014.pdf




"""

