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
import datetime
import multiprocessing
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
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QInputDialog, QLineEdit, QPushButton, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QCheckBox, QSpinBox, QDoubleSpinBox, QRadioButton, QSlider, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView, QTabWidget, QStatusBar, QTextBrowser, \
    QFormLayout, QGroupBox, QScrollArea, QToolButton, QWidgetAction, QSpacerItem, QButtonGroup, QAbstractButton, \
    QApplication, QPlainTextEdit, QTableWidget, QTableWidgetItem, QDockWidget, QDialog, QDialogButtonBox, QFrame, \
    QSizeGrip, QTabBar, QAbstractItemView, QStyledItemDelegate, qApp

import src.config as cfg
import src.shaders
from src.background_worker import BackgroundWorker
from src.compute_affines import ComputeAffines
from src.config import ICON_COLOR
from src.data_model import DataModel
from src.funcs_zarr import tiffs2MultiTiff
from src.generate_aligned import GenerateAligned
from src.generate_scales import GenerateScales
from src.thumbnailer import Thumbnailer
from src.generate_scales_zarr import GenerateScalesZarr
from src.autoscale import autoscale
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
# from src.ui.flicker import Flicker

# from src.ui.components import AutoResizingTextEdit
from src.mendenhall_protocol import Mendenhall
import src.pairwise
# if cfg.DEV_MODE:
#     from src.ui.python_console import PythonConsole
from src.ui.python_console import PythonConsole

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
        self.setObjectName('mainwindow')
        self.window_title = 'AlignEM-SWIFT NG'
        self.setWindowTitle(self.window_title)
        self.setAutoFillBackground(False)

        self.settings = QSettings("cnl", "alignem")
        if self.settings.value("windowState") == None:
            self.initSizeAndPos(cfg.WIDTH, cfg.HEIGHT)
        else:
            self.restoreState(self.settings.value("windowState"))
            self.restoreGeometry(self.settings.value("geometry"))

        self.menu = self.menuBar()
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
        self.initToolbar()

        self.initUI()
        self.initMenu()
        # self.initMenu()
        self.initWidgetSpacing()
        self.initStyle()
        # self.initShortcuts()

        self.initLaunchTab()

        cfg.event = multiprocessing.Event()

        # self.alignmentFinished.connect(self.updateProjectTable)
        self.cancelMultiprocessing.connect(self.cleanupAfterCancel)

        self.activateWindow()

        # self.setWindowFlag(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground)
        # self.showFullScreen()

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
        font = QFont("Calibri")
        QApplication.setFont(font)

        self.setFocusPolicy(Qt.StrongFocus)

        # self.zposChanged.connect(lambda: logger.critical(f'Z-index changed! New zpos is {cfg.data.zpos}'))
        # self.zposChanged.connect(self.dataUpdateWidgets)

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

        if z == None:
            z = cfg.data.zpos
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        # if cfg.data.zpos != z:
        cfg.data.zpos = z

        if not cfg.pt.rb_transforming.isChecked():
            cfg.pt.setRbTransforming()

        if getData('state,manual_mode'):
            cfg.baseViewer.set_layer(cfg.data.zpos)
            cfg.refViewer.set_layer(cfg.data.get_ref_index()) #0611+
            cfg.stageViewer.set_layer(cfg.data.zpos)
        else:
            cfg.emViewer.set_layer(cfg.data.zpos)

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
        # self.showMaximized()

    def cleanupAfterCancel(self):
        logger.critical('Cleaning Up After Multiprocessing Tasks Were Canceled...')
        cfg.project_tab.snr_plot.initSnrPlot()
        # cfg.project_tab.project_table.updateTableData() #0611-
        cfg.project_tab.updateTreeWidget()
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
        caller = inspect.stack()[1].function
        logger.critical(f'caller: {caller}')

        if not self._working:
            logger.critical('Refreshing...')
            if cfg.pt.ms_widget.isVisible():
                self.updateCorrSignalsDrawer()
            if self._isProjectTab():
                cfg.project_tab.refreshTab()
                # for v in cfg.project_tab.get_viewers():
                #     v.set_zmag() #0524-
                self.hud.done()
                self.updateEnabledButtons()  # 0301+
                # self.updateAllCpanelDetails()
                self.updateCpanelDetails()
            elif self._getTabType() == 'WebBrowser':
                self._getTabObject().browser.page().triggerAction(QWebEnginePage.Reload)
            elif self._getTabType() == 'QWebEngineView':
                self.globTabs.currentWidget().reload()
            elif self._getTabType() == 'OpenProject':
                configure_project_paths()
                self._getTabObject().user_projects.set_data()
        else:
            self.warn('The application is busy')
            logger.warning('The application is busy')

    def shutdownNeuroglancer(self):
        if ng.is_server_running():
            logger.critical('Stopping Neuroglancer...')
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
        logger.info('')
        self.threadpool = QThreadPool.globalInstance()
        self.threadpool.setExpiryTimeout(timeout)  # ms

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
            if DEV:
                print(f'focus widget  : {self.focusWidget()}')
                print(f'object name   : {self.focusWidget().objectName()}')
                print(f'object type   : {type(self.focusWidget())}')
                print(f'object id     : {id(self.focusWidget())}')
                print(f'object parent : {self.focusWidget().parent()}')
            if 'tab_project.WebEngine' in str(self.focusWidget().parent()):
                self.setFocus()
        self.printFocusTimer.timeout.connect(fn)
        self.printFocusTimer.start()

        self.uiUpdateTimer = QTimer()
        self.uiUpdateTimer.setSingleShot(True)
        # self.uiUpdateTimer.timeout.connect(lambda: self.dataUpdateWidgets(silently=True))
        self.uiUpdateTimer.timeout.connect(self.dataUpdateWidgets)
        # self.uiUpdateTimer.setInterval(250)
        # self.uiUpdateTimer.setInterval(450)
        self.uiUpdateTimer.setInterval(350)

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

        self._dontReinit = False

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
        if z == None: z = cfg.data.zpos

        # caller = inspect.stack()[1].function
        if not self._isProjectTab():
            return

        # logger.info('')

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

        #Critical0601-
        if not cfg.data.is_aligned_and_generated():
            for i in range(4):
                if not cfg.pt.msList[i]._noImage:
                    cfg.pt.msList[i].set_no_image()

            return #0610+


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
                        except:
                            snr = 0.0
                            # logger.info(f'no SNR data for corr signal index {i}')
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
                        except:
                            snr = 0.0
                            # logger.info(f'no SNR data for corr signal index {i}')
                            cfg.pt.msList[i].set_no_image()
                            # print_exception()
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

    def callbackDwVisibilityChanged(self):
        if self._isProjectTab():
            # caller = inspect.stack()[1].function
            # logger.info(f'caller: {caller}')
            # QApplication.processEvents()
            cfg.data['state']['tool_windows']['python'] = self.dw_python.isVisible()
            cfg.data['state']['tool_windows']['hud'] = self.dw_monitor.isVisible()
            cfg.data['state']['tool_windows']['notes'] = self.dw_notes.isVisible()
            self.cbPython.setChecked(cfg.data['state']['tool_windows']['python'])
            self.cbMonitor.setChecked(cfg.data['state']['tool_windows']['hud'])
            self.cbNotes.setChecked(cfg.data['state']['tool_windows']['notes'])

            # self.pythonConsole.resize(QSize(int(self.width()/2), 90))
            # self.pythonConsole.update()
            # self.hud.resize(QSize(int(self.width()/2), 90))
            # self.hud.update()


    def callbackToolwindows(self):
        QApplication.processEvents()
        self.dw_python.setVisible(self.cbPython.isChecked())
        self.dw_notes.setVisible(self.cbNotes.isChecked())
        self.dw_monitor.setVisible(self.cbMonitor.isChecked())

    def setdw_python(self, state):
        self.dw_python.setVisible(state)
        self.showPythonAction.setText(('Show Python Console', 'Hide Python Console')[state])
        self.cbPython.setToolTip(("Show Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)",
                                  "Hide Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)")[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['python'] = state

    def setdw_monitor(self, state):
        self.dw_monitor.setVisible(state)
        self.showMonitorAction.setText(('Show Process Monitor', 'Hide Process Monitor')[state])
        self.dw_monitor.setVisible(self.cbMonitor.isChecked())
        tip1 = '\n'.join("Show Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "M)")
        tip2 = '\n'.join("Hide Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "M)")
        self.cbMonitor.setToolTip((tip1, tip2)[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['hud'] = state

    # def setdw_thumbnails(self, state):
    #     self.dw_thumbnails.setVisible(state)
    #     self.showThumbnailsAction.setText(('Show Raw Thumbnails', 'Hide Raw Thumbnails')[state])
    #     self.dw_thumbnails.setVisible(self.cbThumbnails.isChecked())
    #     tip1 = '\n'.join(f"Show Raw Thumbnails Tool Window ({hotkey('T')})")
    #     tip2 = '\n'.join(f"Hide Raw Thumbnails Tool Window ({hotkey('T')})")
    #     self.cbThumbnails.setToolTip((tip1, tip2)[state])
    #     if self._isProjectTab():
    #         cfg.data['state']['tool_windows']['raw_thumbnails'] = state


    def setdw_notes(self, state):
        self.dw_notes.setVisible(state)
        self.showNotesAction.setText(('Show Notes', 'Hide Notes')[state])
        self.cbNotes.setToolTip(("Show Notes Tool Window (" + ('^', '⌘')[is_mac()] + "N)",
                                 "Hide Notes Tool Window (" + ('^', '⌘')[is_mac()] + "N)")[state])
        if self._isProjectTab():
            cfg.data['state']['tool_windows']['notes'] = state
        self.updateNotes()

    # def _callbk_showHidePython(self):
    #     # self.dw_python.setHidden(not self.dw_python.isHidden())
    #     self.dw_python.setVisible(self.cbPython.isChecked())
    #     self.cbPython.setToolTip(("Hide Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)",
    #                               "Show Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)")[
    #                                  self.dw_python.isHidden()])

    # def _callbk_showHideNotes(self):
    #     # self.dw_notes.setHidden(not self.dw_notes.isHidden())
    #     self.dw_notes.setVisible(self.cbNotes.isChecked())
    #     self.updateNotes()

    # def _callbk_showHideHud(self):
    #     # self.dw_monitor.setHidden(not self.dw_monitor.isHidden())
    #     self.dw_monitor.setVisible(self.cbMonitor.isChecked())
    #     tip1 = '\n'.join(textwrap.wrap('Hide Head-up Display (Process Monitor) Tool Window', width=35))
    #     tip2 = '\n'.join(textwrap.wrap('Show Head-up Display (Process Monitor) Tool Window', width=35))
    #     self.cbMonitor.setToolTip((tip1, tip2)[self.dw_monitor.isHidden()])

    def _showSNRcheck(self, s=None):
        logger.info('')
        caller = inspect.stack()[1].function
        if s == None: s = cfg.data.scale
        if cfg.data.is_aligned():
            logger.info('Checking SNR data for %s...' % cfg.data.scale_pretty(s=s))
            failed = cfg.data.check_snr_status()
            if len(failed) == len(cfg.data):
                self.warn('No SNR Data Available for %s' % cfg.data.scale_pretty(s=s))
            elif failed:
                indexes, names = zip(*failed)
                lst_names = ''
                for name in names:
                    lst_names += f'\n  Section: {name}'
                self.warn(f'No SNR Data For Sections: {", ".join(map(str, indexes))}')

    def regenerateOne(self):
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        self.regenerate(scale=cfg.data.scale, start=start, end=end)

    def regenerate(self, scale, start=0, end=None) -> None:
        '''Note: For now this will always reallocate Zarr, i.e. expects arguments for full stack'''
        logger.info('regenerate >>>>')
        if cfg.event.is_set():
            cfg.event.clear()
        if not self._isProjectTab():
            return
        if self._working == True:
            self.warn('Another Process is Already Running');
            return
        if not cfg.data.is_aligned(s=scale):
            self.warn('Scale Must Be Aligned First');
            return
        cfg.nProcessSteps = 3
        cfg.nProcessDone = 0
        cfg.CancelProcesses = False
        self.pbarLabel.setText('Task (0/%d)...' % cfg.nProcessSteps)
        self.showZeroedPbar(set_n_processes=3)
        cfg.data.set_has_bb(cfg.data.use_bb())  # Critical, also see regenerate
        self.tell('Regenerating Aligned Images,  Scale %d...' % get_scale_val(scale))
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=GenerateAligned(
                    cfg.data, scale, start, end, stageit=True, reallocate_zarr=True, use_gui=True))
                self.threadpool.start(self.worker)
            else:
                GenerateAligned(cfg.data, scale, start, end, stageit=True, reallocate_zarr=True, use_gui=True)
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
            # self.updateAllCpanelDetails()
            self.updateCpanelDetails()
            self.pbarLabel.setText('')
            self.hidePbar()
            self.updateDtWidget()
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
    #     self.pbar_widget.hide()

    def present_snr_results(self, start=0, end=None):
        try:
            if cfg.data.is_aligned():
                self.tell('The Stack is Aligned!')
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
            self.tell('  # Better (SNR ↑) : %s' % ' '.join(map(str, pos)))
            self.tell('  # Worse  (SNR ↓) : %s' % ' '.join(map(str, neg)))
            self.tell('  # Equal  (SNR =) : %s' % ' '.join(map(str, no_chg)))
            if abs(diff_avg) < .001:
                self.tell('  Δ AVG. SNR : 0.000 (NO CHANGE)')
            elif diff_avg < 0:
                self.tell('  Δ AVG. SNR : %.3f (WORSE)' % diff_avg)
            else:
                self.tell('  Δ AVG. SNR : %.3f (BETTER)' % diff_avg)
        except:
            logger.warning('Unable To Present SNR Results')

    def updateDtWidget(self):
        logger.info('')
        # if self._isProjectTab():
        if cfg.data:
            s = cfg.data.scale
            try:
                # a = """<span style='color: #ffe135;'>"""
                # b = """</span>"""
                # nl = '<br>'
                # br = '&nbsp;'
                # cfg.project_tab.detailsRuntime.setText(
                #     f"Gen. Scales{br}{br}{br}{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['t_scaling']).rjust(9) +
                #     f"Convert Zarr{br}{br}{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['t_scaling_convert_zarr']).rjust(9) +
                #     f"Source Thumbs{br}{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['t_thumbs']).rjust(9) +
                #     f"Compute Affines{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['scales'][s]['t_align']).rjust(9) +
                #     f"Gen. Alignment{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['scales'][s]['t_generate']).rjust(9) +
                #     f"Aligned Thumbs{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_aligned']).rjust(9) +
                #     f"Corr Spot Thumbs{br}:{a}" + (f"%.2fs{b}" % cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_spot']).rjust(9)
                # )

                t0 = (f"%.1fs" % cfg.data['data']['benchmarks']['t_scaling']).rjust(12)
                t1 = (f"%.1fs" % cfg.data['data']['benchmarks']['t_scaling_convert_zarr']).rjust(12)
                t2 = (f"%.1fs" % cfg.data['data']['benchmarks']['t_thumbs']).rjust(12)
                
                t0m = (f"%.3fm" % (cfg.data['data']['benchmarks']['t_scaling'] / 60))
                t1m = (f"%.3fm" % (cfg.data['data']['benchmarks']['t_scaling_convert_zarr'] / 60))
                t2m = (f"%.3fm" % (cfg.data['data']['benchmarks']['t_thumbs'] / 60))

                t3, t4, t5, t6, t7 = {}, {}, {}, {}, {}
                for s in cfg.data.scales():
                    t3[s] = (f"%.1fs" % cfg.data['data']['benchmarks']['scales'][s]['t_align']).rjust(12)
                    t4[s] = (f"%.1fs" % cfg.data['data']['benchmarks']['scales'][s]['t_convert_zarr']).rjust(12)
                    t5[s] = (f"%.1fs" % cfg.data['data']['benchmarks']['scales'][s]['t_generate']).rjust(12)
                    t6[s] = (f"%.1fs" % cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_aligned']).rjust(12)
                    t7[s] = (f"%.1fs" % cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_spot']).rjust(12)



                t3m, t4m, t5m, t6m, t7m = {}, {}, {}, {}, {}
                for s in cfg.data.scales():
                    t3m[s] = (f"%.3fm" % (cfg.data['data']['benchmarks']['scales'][s]['t_align'] / 60))
                    t4m[s] = (f"%.3fm" % (cfg.data['data']['benchmarks']['scales'][s]['t_convert_zarr'] / 60))
                    t5m[s] = (f"%.3fm" % (cfg.data['data']['benchmarks']['scales'][s]['t_generate'] / 60))
                    t6m[s] = (f"%.3fm" % (cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_aligned'] / 60))
                    t7m[s] = (f"%.3fm" % (cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_spot'] / 60))

                fl_l = QFormLayout()
                fl_l.setContentsMargins(0, 0, 0, 0)
                fl_l.setVerticalSpacing(1)
                fl_l.addRow('Generate Scale Hierarchy', QLabel(t0 + ' / ' + t0m))
                fl_l.addRow('Convert All Scales to Zarr', QLabel(t1 + ' / ' + t1m))
                fl_l.addRow('Generate Source Image Thumbnails', QLabel(t2 + ' / ' + t2m))
                # fl_l.addRow('Compute Affines', QLabel('\n'.join(['  %s: %s / %s' % (s, t3[s],t3m[s]) for s in cfg.data.scales()])))
                fl_l.addRow('Compute Affines', QLabel(''))
                for s in cfg.data.scales():
                    fl_l.addRow('  ' + cfg.data.scale_pretty(s), QLabel('%s / %s' % (t3[s], t3m[s])))
                fl_l.addRow('Generate Aligned TIFFs', QLabel(''))
                for s in cfg.data.scales():
                    fl_l.addRow('  ' + cfg.data.scale_pretty(s), QLabel('%s / %s' % (t4[s], t4m[s])))
                fl_l.addRow('Convert Aligned TIFFs to Zarr', QLabel(''))
                for s in cfg.data.scales():
                    fl_l.addRow('  ' + cfg.data.scale_pretty(s), QLabel('%s / %s' % (t5[s], t5m[s])))
                fl_l.addRow('Generate Aligned TIFF Thumbnails', QLabel(''))
                for s in cfg.data.scales():
                    fl_l.addRow('  ' + cfg.data.scale_pretty(s), QLabel('%s / %s' % (t6[s], t6m[s])))
                fl_l.addRow('Generate Correlation Signal Thumbnails', QLabel(''))
                for s in cfg.data.scales():
                    fl_l.addRow('  ' + cfg.data.scale_pretty(s), QLabel('%s / %s' % (t7[s], t7m[s])))

                # fl_l.addRow('Compute Affines', QLabel('\n'.join(['  %s: %s / %s' % (s, t3[s], t3m[s]) for s in cfg.data.scales()])))
                # fl_l.addRow('Generate Aligned TIFFs', QLabel('\n'.join(['  %s: %s / %s' % (s, t4[s],t4m[s]) for s in cfg.data.scales()])))
                # fl_l.addRow('Convert Aligned TIFFs to Zarr', QLabel('\n'.join(['  %s: %s / %s' % (s, t5[s],t5m[s]) for s in cfg.data.scales()])))
                # fl_l.addRow('Generate Aligned TIFF Thumbnails', QLabel('\n'.join(['  %s: %s / %s' % (s, t6[s],t6m[s]) for s in cfg.data.scales()])))
                # fl_l.addRow('Generate Correlation Signal Thumbnails', QLabel('\n'.join(['  %s: %s / %s' % (s, t7[s],t7m[s]) for s in cfg.data.scales()])))

                # self.runtimeWidget.setText(
                #     f"Gen. Scales{br}{br}{br}{br}{br}{br}:{br}{a}{t0}{br}{br}"
                #     f"Convert Zarr{br}{br}{br}{br}{br}:{br}{a}{t1}{nl}"
                #     f"Source Thumbs{br}{br}{br}{br}:{br}{a}{t2}{br}{br}"
                #     f"Compute Affines{br}{br}:{br}{a}{t3}{nl}"
                #     f"Gen. Alignment{br}{br}{br}:{br}{a}{t4}{br}{br}"
                #     f"Aligned Thumbs{br}{br}{br}:{br}{a}{t5}{nl}"
                #     f"Corr Spot Thumbs{br}:{br}{a}{t6}"
                # )
                w = QWidget()
                w.setContentsMargins(0, 0, 0, 0)
                w.setStyleSheet("""
                QLabel{
                    color: #161c20;
                    font-size: 8px;
                }
                """)
                w.setLayout(fl_l)

                self.sa_tab3.setWidget(w)


            except:
                logger.warning('detailsTiming cant update')

    def onAlignmentStart(self, scale):
        logger.info('')
        if cfg.event.is_set():
            cfg.event.clear()
        t0 = time.time()
        dt = datetime.datetime.now()
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
        self._autosave()
        self._changeScaleCombo.setEnabled(False)
        check_project_status()

    def onAlignmentEnd(self, start, end):
        logger.critical('Running Post-Alignment Tasks...')
        # self.alignmentFinished.emit()
        t0 = time.time()
        try:
            if self._isProjectTab():
                self.enableAllTabs() #0603+ #Critical
                self.updateEnabledButtons()
                self.updateCorrSignalsDrawer()
                # self.pbarLabel.setText('')
                if cfg.project_tab._tabs.currentIndex() == 3:
                    cfg.project_tab.snr_plot.initSnrPlot()
                # self.updateProjectTable()  # +
                try:
                    self.updateMenus()
                except:
                    print_exception()
                self.present_snr_results(start=start, end=end)
                self.tell('New Avg. SNR: %.3f, Previous Avg. SNR: %.3f' % (cfg.data.snr_average(), cfg.data.snr_prev_average()))
                self.updateDtWidget()
                cfg.project_tab.updateTreeWidget() #0603-
                self._bbToggle.setChecked(cfg.data.has_bb())
                self.dataUpdateWidgets()
                self._showSNRcheck()
                # self.updateAllCpanelDetails()
                self.updateCpanelDetails()

                # self.flicker.start()

        except:
            print_exception()
        finally:
            if cfg.event.is_set():
                cfg.event.clear()
            self._autosave()
            self._working = False
            self._changeScaleCombo.setEnabled(True)
            self.hidePbar()
            if self._isProjectTab():
                self.enableAllTabs()
                try:
                    if cfg.project_tab._tabs.currentIndex() == 3:
                        cfg.project_tab.snr_plot.initSnrPlot()
                except:
                    print_exception()

            t9 = time.time()
            dt = t9 - t0
            logger.critical(f'Time Elapsed: {dt}s')
            self.tell(f'Time Elapsed: {dt}s')

    def alignAll(self, set_pbar=True, force=False, ignore_bb=False):
        caller = inspect.stack()[1].function
        if caller == 'main':
            set_pbar = True

        if (not force) and (not self._isProjectTab()):
            return
        scale = cfg.data.scale
        if not self.verify_alignment_readiness():
            self.warn('%s is not a valid target for alignment!' % cfg.data.scale_pretty(scale))
            return
        self.tell('Aligning All Sections (%s)...' % cfg.data.scale_pretty())
        logger.critical(f'alignAll caller={caller}, set_pbar={set_pbar} >>>>')
        if set_pbar:
            logger.critical('set_pbar >>>>')
            cfg.ignore_pbar = False
            if self._toggleAutogenerate.isChecked():
                # cfg.nProcessSteps = 5
                self.showZeroedPbar(set_n_processes=4)
            else:
                # cfg.nProcessSteps = 3
                self.showZeroedPbar(set_n_processes=2)


        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        cfg.data.set_has_bb(cfg.data.use_bb())  # Critical, also see regenerate
        self.align(
            scale=cfg.data.scale,
            start=0,
            end=None,
            renew_od=True,
            reallocate_zarr=True,
            # stageit=stageit,
            stageit=True,
            ignore_bb=ignore_bb
        )
        # if not cfg.CancelProcesses:
        #     self.present_snr_results()

        self.onAlignmentEnd(start=0, end=None)
        cfg.project_tab.initNeuroglancer()
        self.tell('<span style="color: #FFFF66;"><b>**** Processes Complete ****</b></span>')

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
                cfg.data.scale = s
                # cfg.project_tab.initNeuroglancer()
                cfg.project_tab.refreshTab()
                self.dataUpdateWidgets()
                # if getData('state,manual_mode'):
                #     cfg.pt.dataUpdateMA()
                self.alignAll(set_pbar=False)

            self.onAlignmentEnd()

    def alignRange(self):
        cfg.ignore_pbar = False
        start = int(self.startRangeInput.text())
        end = int(self.endRangeInput.text()) + 1
        if self._toggleAutogenerate.isChecked():
            self.showZeroedPbar(set_n_processes=4)
        else:
            self.showZeroedPbar(set_n_processes=2)
        cfg.nProcessDone = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.tell('Re-aligning Sections #%d through #%d (%s)...' %
                  (start, end, cfg.data.scale_pretty()))
        self.align(
            scale=cfg.data.scale,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            # stageit=False,
            stageit=True,
        )
        self.onAlignmentEnd(start=start, end=end)
        cfg.project_tab.initNeuroglancer()
        self.tell('<span style="color: #FFFF66;"><b>**** Processes Complete ****</b></span>')

    def alignForward(self):
        cfg.ignore_pbar = False
        start = cfg.data.zpos
        end = cfg.data.count
        if self._toggleAutogenerate.isChecked():
            self.showZeroedPbar(set_n_processes=4)
        else:
            self.showZeroedPbar(set_n_processes=2)
        cfg.nProcessDone = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.tell('Re-aligning Sections #%d through #%d (%s)...' %
                  (start, end, cfg.data.scale_pretty()))
        self.align(
            scale=cfg.data.scale,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            # stageit=False,
            stageit=True,
        )
        self.onAlignmentEnd(start=start, end=end)
        cfg.project_tab.initNeuroglancer()
        self.tell('<span style="color: #FFFF66;"><b>**** Processes Complete ****</b></span>')

    # def alignOne(self, stageit=False):
    def alignOne(self, quick_swim=False):
        logger.critical('Aligning One...')
        self.tell('Re-aligning Section #%d (%s)...' %
                  (cfg.data.zpos, cfg.data.scale_pretty()))
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        cfg.nProcessDone = 0
        cfg.nProcessSteps = 1
        self.align(
            scale=cfg.data.scale,
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

        # self.updateCorrSignalsDrawer()
        if quick_swim:
            self.updateCorrSignalsDrawer()
            self.updateEnabledButtons()
            self.enableAllTabs()
            self.updateCpanelDetails()
        else:
            self.onAlignmentEnd(start=start, end=end)  # 0601+ why was this uncommented?
            cfg.project_tab.initNeuroglancer()

        self.tell('Section #%d Alignment Complete' % start)
        self.tell('SNR Before: %.3f  SNR After: %.3f' %
                  (cfg.data.snr_prev(l=start), cfg.data.snr(l=start)))
        self.tell('<span style="color: #FFFF66;"><b>**** Processes Complete ****</b></span>')

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
            scale=cfg.data.scale,
            start=start,
            end=end,
            renew_od=False,
            reallocate_zarr=False,
            stageit=True,
            align_one=True,
            swim_only=False
        )
        self.onAlignmentEnd(start=start, end=end)
        cfg.project_tab.initNeuroglancer()
        self.tell('Section #%d Alignment Complete' % start)
        self.tell('SNR Before: %.3f  SNR After: %.3f' %
                  (cfg.data.snr_prev(l=start), cfg.data.snr(l=start)))
        self.tell('<span style="color: #FFFF66;"><b>**** Processes Complete ****</b></span>')
        cfg.ignore_pbar = False

    def align(self, scale, start, end, renew_od, reallocate_zarr, stageit, align_one=False, swim_only=False, ignore_bb=False):
        # Todo change printout based upon alignment scope, i.e. for single layer
        # caller = inspect.stack()[1].function
        # if caller in ('alignGenerateOne','alignOne'):
        #     ALIGN_ONE = True
        logger.info(f'Aligning start:{start}, end: {end}, scale: {scale}...')

        self.onAlignmentStart(scale=scale)
        self.tell("%s Affines (%s)..." % (('Initializing', 'Refining')[cfg.data.isRefinement()], cfg.data.scale_pretty(s=scale)))

        if not ignore_bb:
            cfg.data.set_use_bounding_rect(self._bbToggle.isChecked())
        
        if cfg.ignore_pbar:
            self.showZeroedPbar(set_n_processes=False)
            self.setPbarText('Computing Affine...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(
                    fn=ComputeAffines(scale, path=None, start=start, end=end, swim_only=swim_only, renew_od=renew_od,
                                      reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=True, dm=cfg.data))
                self.threadpool.start(self.worker)
            else:
                ComputeAffines(scale, path=None, start=start, end=end, swim_only=swim_only, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit, use_gui=True, dm=cfg.data)
        except:
            print_exception();
            self.err('An Exception Was Raised During Alignment.')
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
        #     if self._toggleAutogenerate.isChecked():
        #
        #         if cfg.ignore_pbar:
        #             cfg.nProcessDone += 1
        #             self.updatePbar()
        #             self.setPbarText('Generating Alignment...')
        #
        #         try:
        #             if cfg.USE_EXTRA_THREADING:
        #                 self.worker = BackgroundWorker(fn=GenerateAligned(
        #                     scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit))
        #                 self.threadpool.start(self.worker)
        #             else: GenerateAligned(scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit)
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

    def generate_multiscale_zarr(self):
        pass

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
        self.sb_whiteningControl.setEnabled(True)
        self._swimWindowControl.setEnabled(True)
        self._toggleAutogenerate.setEnabled(True)
        self._bbToggle.setEnabled(True)
        self._polyBiasCombo.setEnabled(True)
        self._btn_clear_skips.setEnabled(True)
        self._toggleAutogenerate.setEnabled(True)
        self.startRangeInput.setEnabled(True)
        self.endRangeInput.setEnabled(True)
        
    
    def updateManualAlignModeButton(self):
        if getData('state,manual_mode'):
            tip = 'Exit Manual Align Mode'
            self._btn_manualAlign.setText(f" Exit Manual Mode {hotkey('M')}")
            self.alignMatchPointAction.setText(f"Exit Manual Align Mode {hotkey('M')} ")
            self._btn_manualAlign.setLayoutDirection(Qt.LeftToRight)
            self._btn_manualAlign.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
            self._btn_manualAlign.setIcon(qta.icon('fa.arrow-left', color='#ede9e8'))
            self._btn_manualAlign.setStyleSheet("""background-color: #222222; color: #ede9e8;""")

        else:
            tip = 'Enter Manual Align Mode'
            self._btn_manualAlign.setText(f"Manual Align {hotkey('M')} ")
            self.alignMatchPointAction.setText(f"Align Manually {hotkey('M')} ")
            self._btn_manualAlign.setLayoutDirection(Qt.RightToLeft)
            self._btn_manualAlign.setIcon(qta.icon('fa.arrow-right', color='#161c20'))
            self._btn_manualAlign.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
            self._btn_manualAlign.setStyleSheet("""""")
            
    
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
            self._toggleAutogenerate.setEnabled(True)
            self._bbToggle.setEnabled(True)
            self._polyBiasCombo.setEnabled(True)
            self._btn_clear_skips.setEnabled(True)
            self._swimWindowControl.setEnabled(True)
            self.sb_whiteningControl.setEnabled(True)
            # self._ctlpanel_applyAllButton.setEnabled(True)
            self._swimWindowControl.setValidator(QIntValidator(0, cfg.data.image_size()[0]))
            self._changeScaleCombo.setEnabled(True)

            self.cbThumbnails.setChecked(getData('state,tool_windows,raw_thumbnails'))
            self.cbSignals.setChecked(getData('state,tool_windows,signals'))
            self.cbMonitor.setChecked(getData('state,tool_windows,hud'))
            self.cbNotes.setChecked(getData('state,tool_windows,notes'))
            self.cbPython.setChecked(getData('state,tool_windows,python'))

        else:
            self._skipCheckbox.setEnabled(False)
            self.sb_whiteningControl.setEnabled(False)
            self._swimWindowControl.setEnabled(False)
            self._toggleAutogenerate.setEnabled(False)
            self._bbToggle.setEnabled(False)
            self._polyBiasCombo.setEnabled(False)
            self._btn_clear_skips.setEnabled(False)

            # self._ctlpanel_applyAllButton.setEnabled(False)

        if self._isProjectTab():
            # if cfg.data.is_aligned_and_generated(): #0202-

            self.updateManualAlignModeButton()

            if cfg.data.is_aligned():
                # self._btn_alignAll.setText('Re-Align All Sections (%s)' % cfg.data.scale_pretty())
                # self._btn_alignAll.setText('Align All')
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(True)
                self._btn_alignForward.setEnabled(True)
                self._btn_alignRange.setEnabled(True)
                self._btn_regenerate.setEnabled(True)
                self._btn_manualAlign.setEnabled(True)
                self.startRangeInput.setEnabled(True)
                self.endRangeInput.setEnabled(True)

            elif cfg.data.is_alignable():
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(False)
                self._btn_alignForward.setEnabled(False)
                self._btn_alignRange.setEnabled(False)
                self._btn_regenerate.setEnabled(False)
                self._btn_manualAlign.setEnabled(False)
                self.startRangeInput.setEnabled(False)
                self.endRangeInput.setEnabled(False)
            else:
                self._btn_alignAll.setEnabled(False)
                self._btn_alignOne.setEnabled(False)
                self._btn_alignForward.setEnabled(False)
                self._btn_alignRange.setEnabled(False)
                self._btn_regenerate.setEnabled(False)
                self._btn_manualAlign.setEnabled(False)
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
                    self._btn_manualAlign.setEnabled(True)
                    self.startRangeInput.setEnabled(True)
                    self.endRangeInput.setEnabled(True)
                else:
                    self._btn_alignAll.setEnabled(True)
                    self._btn_alignOne.setEnabled(False)
                    self._btn_alignForward.setEnabled(False)
                    self._btn_alignRange.setEnabled(False)
                    self._btn_regenerate.setEnabled(False)
                    self._btn_manualAlign.setEnabled(False)
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
            self._btn_manualAlign.setEnabled(False)
            self.startRangeInput.setEnabled(False)
            self.endRangeInput.setEnabled(False)


    def layer_left(self):

        if self._isProjectTab():
            requested = cfg.data.zpos - 1
            logger.info(f'requested: {requested}')
            if requested >= 0:
                cfg.mw.setZpos(requested)
                # cfg.data.zpos = requested
                # if getData('state,manual_mode'):
                #     setData('state,stackwidget_ng_toggle', 1)
                #     cfg.pt.sw_neuroglancer.setCurrentIndex(cfg.data['state']['stackwidget_ng_toggle'])
                #     cfg.baseViewer.set_layer(cfg.data.zpos)
                #     cfg.stageViewer.set_layer(cfg.data.zpos)
                # else:
                #     cfg.emViewer.set_layer(cfg.data.zpos)

            else:
                # self.warn(f'Invalid Index Request: {requested}')
               pass

    def layer_right(self):

        if self._isProjectTab():
            requested = cfg.data.zpos + 1
            if requested < len(cfg.data):
                cfg.mw.setZpos(requested)
                # cfg.data.zpos = requested
                # if getData('state,manual_mode'):
                #     setData('state,stackwidget_ng_toggle', 1)
                #     cfg.pt.sw_neuroglancer.setCurrentIndex(cfg.data['state']['stackwidget_ng_toggle'])
                #     cfg.baseViewer.set_layer(cfg.data.zpos)
                #     cfg.stageViewer.set_layer(cfg.data.zpos)
                # else:
                #     cfg.emViewer.set_layer(cfg.data.zpos)
            else:
                # self.warn(f'Invalid Index Request: {requested}')
                pass

    def scale_down(self) -> None:
        '''Callback function for the Previous Scale button.'''
        logger.info('')
        if not self._working:
            if self._scaleDownButton.isEnabled():
                self._changeScaleCombo.setCurrentIndex(self._changeScaleCombo.currentIndex() + 1)  # Changes Scale

    def scale_up(self) -> None:
        '''Callback function for the Next Scale button.'''
        logger.info('scale_up >>>>')
        if not self._working:
            if self._scaleUpButton.isEnabled():
                self._changeScaleCombo.setCurrentIndex(self._changeScaleCombo.currentIndex() - 1)  # Changes Scale
                if not cfg.data.is_alignable():
                    self.warn('Lower scales have not been aligned yet')

    @Slot()
    def set_status(self, msg: str) -> None:
        # self.statusBar.showMessage(msg)
        pass

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
    #         # self.sa_tab1.setWidget(w)

    def everySecond(self):
        if self._isProjectTab():
            if cfg.pt._tabs.currentIndex() == 0:
                logger.info('')
                if not self._working:
                    self.dataUpdateWidgets()



    # def dataUpdateWidgets(self, ng_layer=None, silently=False) -> None:
    @Slot(name='dataUpdateWidgets-slot-name')
    def dataUpdateWidgets(self) -> None:
        '''Reads Project Data to Update MainWindow.'''

        # caller = inspect.stack()[1].function
        if DEV:
            logger.info(f'{caller_name()}')
        # logger.critical(f'dataUpdateWidgets [caller: {caller}] [sender: {self.sender()}]...')
        # if getData('state,blink'):
        #     return

        # if cfg.emViewer:
        #     cfg.emViewer.

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
                    logger.warning('Delaying UI Update [viewer_em.WorkerSignals]...')
                    return
                else:
                    self.uiUpdateTimer.start()
                    logger.critical('Updating UI on Timeout [viewer_em.WorkerSignals]...')

            # cfg.project_tab._overlayRect.hide()
            cfg.project_tab._overlayLab.hide()

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

            if cfg.data.skipped():
                # cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
                cfg.project_tab._overlayLab.setText('X EXCLUDED - %s' % cfg.data.name_base())
                cfg.project_tab._overlayLab.show()
                # cfg.project_tab._overlayRect.show()


            if cfg.pt.ms_widget.isVisible():
                self.updateCorrSignalsDrawer()


            if cfg.pt.tn_widget.isVisible():
                os.path.isdir(cfg.data.thumbnail_ref())
                cfg.pt.tn_ref.selectPixmap(path=cfg.data.thumbnail_ref())
                cfg.pt.tn_tra.selectPixmap(path=cfg.data.thumbnail_tra())
                cfg.pt.labMethod2.setText(cfg.data.method_pretty())

            cfg.pt.lab_filename.setText(f"[{cfg.data.zpos}] Name: {cfg.data.filename_basename()}")
            cfg.pt.tn_tra_lab.setText(f'Transforming Section\n'
                                      f'[{cfg.data.zpos}] {cfg.data.filename_basename()}')
            try:
                cfg.pt.tn_ref_lab.setText(f'Reference Section\n'
                                          f'[{cfg.data.get_ref_index()}] {cfg.data.reference_basename()}')
            except:
                cfg.pt.tn_ref_lab.setText(f'Reference Section')


            img_siz = cfg.data.image_size()
            self.statusBar.showMessage(cfg.data.scale_pretty() + ', ' +
                                       'x'.join(map(str, img_siz)) + ', ' +
                                       cfg.data.name_base())

            if self.notes.isVisible():
                self.updateNotes()

            if getData('state,manual_mode'):
                cfg.project_tab.dataUpdateMA()
            #     # setData('state,stackwidget_ng_toggle', 1)
            #     # cfg.pt.rb_transforming.setChecked(getData('state,stackwidget_ng_toggle'))
            #     cfg.baseViewer.set_layer()
            #     cfg.stageViewer.set_layer(cfg.data.zpos)
            #     # if cfg.pt.MA_webengine_ref.isVisible():
            #     #     cfg.refViewer.drawSWIMwindow()
            #     # elif cfg.pt.MA_webengine_base.isVisible():
            #     cfg.baseViewer.drawSWIMwindow()
            #     # cfg.refViewer.drawSWIMwindow()
            #     # cfg.baseViewer.drawSWIMwindow()
            #
            #     # cfg.refViewer.set_layer()
            #     # cfg.baseViewer.set_layer()

            if cfg.project_tab._tabs.currentIndex() == 1:
                cfg.project_tab.project_table.table.selectRow(cur)

            if cfg.project_tab._tabs.currentIndex() == 2:
                cfg.project_tab.treeview_model.jumpToLayer()

            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.snr_plot.updateLayerLinePos()

            # if cfg.project_tab._tabs.currentIndex() == 3:
            #     cfg.snrViewer.set_layer(cfg.data.zpos)

            # timer.report() #6

            br = '&nbsp;'
            a = """<span style='color: #ffe135;'>"""
            b = """</span>"""
            nl = '<br>'

            if self.cpanelTabWidget.currentIndex() == 0:
                self.secName.setText(cfg.data.filename_basename())
                ref = cfg.data.reference_basename()
                if ref == '':
                    ref = 'None'
                self.secReference.setText(ref)
                self.secAlignmentMethod.setText(cfg.data.method_pretty())
                if cfg.data.snr() == 0:
                    self.secSNR.setText('--')
                else:
                    self.secSNR.setText(
                        '<span style="color: #a30000;"><b>%.2f</b></span><span>&nbsp;&nbsp;(%s)</span>' % (
                        cfg.data.snr(), ",  ".join(["%.2f" % x for x in cfg.data.snr_components()])))

            if self.cpanelTabWidget.currentIndex() == 3:
                self.secAffine.setText(make_affine_widget_HTML(cfg.data.afm(), cfg.data.cafm()))

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
            self._btn_alignOne.setText('Re-Align #%d' % cfg.data.zpos)
            self._btn_alignForward.setText('Align Forward (#%d - #%d)' % (cfg.data.zpos, cfg.data.count))
        # timer.stop() #7
        # logger.info(f'<<<< dataUpdateWidgets [{caller}] zpos={cfg.data.zpos} <<<<')

        self.setFocus()


    def updateNotes(self):
        # caller = inspect.stack()[1].function
        # logger.info('')
        self.notes.clear()
        if self._isProjectTab():
            self.notes.setPlaceholderText('Enter notes about %s here...'
                                          % cfg.data.base_image_name(s=cfg.data.scale, l=cfg.data.zpos))
            if cfg.data.notes(s=cfg.data.scale, l=cfg.data.zpos):
                self.notes.setPlainText(cfg.data.notes(s=cfg.data.scale, l=cfg.data.zpos))
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
        if s == None: s = cfg.data.scale
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
                path = os.path.join(cfg.data.dest(), cfg.data.scale, 'history', name)
                with open(path, 'r') as f:
                    project = json.load(f)
                self.projecthistory_model.load(project)
                self.globTabs.addTab(self.historyview_widget, cfg.data.scale_pretty())
        self._setLastTab()

    def rename_historical_alignment(self):
        new_name, ok = QInputDialog.getText(self, 'Rename', 'New Name:')
        if not ok: return
        old_name = self._hstry_listWidget.currentItem().text()
        dir = os.path.join(cfg.data.dest(), cfg.data.scale, 'history')
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
        path = os.path.join(cfg.data.dest(), cfg.data.scale, 'history', name)
        with open(path, 'r') as f:
            scale = json.load(f)
        self.tell('Swapping Current Scale %d Dictionary with %s' % (scale_val, name))
        cfg.data.set_al_dict(aldict=scale)
        # self.regenerate() #Todo test this under a range of possible scenarios

    def remove_historical_alignment(self):
        logger.info('Loading History File...')
        name = self._hstry_listWidget.currentItem().text()
        if name is None: return
        path = os.path.join(cfg.data.dest(), cfg.data.scale, 'history', name)
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
        path = os.path.join(cfg.data.dest(), cfg.data.scale, 'history', item.text())
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

    def _resetSlidersAndJumpInput(self):
        '''Requires Neuroglancer '''
        logger.info('')
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if self._isProjectTab() or self._isZarrTab():
                self._jumpToLineedit.setValidator(QIntValidator(0, len(cfg.data) - 1))
                self._sectionSlider.setRange(0, len(cfg.data) - 1)
                self._sectionSlider.setValue(cfg.data.zpos)
                self.sectionRangeSlider.setMin(0)
                self.sectionRangeSlider.setMax(len(cfg.data) - 1)
                self.sectionRangeSlider.setStart(0)
                self.sectionRangeSlider.setEnd(len(cfg.data) - 1)

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
    def jump_to_manual(self, requested) -> None:
        logger.info('')
        if self._isProjectTab():
            if requested not in range(len(cfg.data)):
                logger.warning('Requested layer is not a valid layer')
                return
            self.setZpos(requested)
            # cfg.project_tab.updateNeuroglancer() #0214+ intentionally putting this before dataUpdateWidgets (!)
            self.enter_man_mode()

    @Slot()
    def jump_to_layer(self) -> None:
        '''Connected to _jumpToLineedit. Calls jump_to_slider directly.'''
        # logger.info('')
        if self._isProjectTab():
            requested = int(self._jumpToLineedit.text())
            if requested in range(len(cfg.data)):
                self.setZpos(requested)
                if cfg.project_tab._tabs.currentIndex() == 1:
                    cfg.project_tab.project_table.table.selectRow(requested)
                self._sectionSlider.setValue(requested)
                # if cfg.pt.ms_widget.isVisible():     #0601+ untried
                #     self.updateCorrSignalsDrawer()
                # self.dataUpdateWidgets() #0601+

    def jump_to_slider(self):
        caller = inspect.stack()[1].function

        #0601 this seems to work as intended with no time lag
        if caller in ('dataUpdateWidgets'):
            return
        logger.info('')
        # if caller in ('main', 'onTimer','jump'):
        requested = self._sectionSlider.value()
        if self._isProjectTab():
            logger.info('Jumping To Section #%d' % requested)
            self.setZpos(requested)



            # if getData('state,manual_mode'):
            #     cfg.pt.rb_transforming.setChecked(True)
            #     cfg.baseViewer.set_layer()
            # else:
            #     cfg.emViewer.set_layer()
            # self.dataUpdateWidgets()


        try:
            self._jumpToLineedit.setText(str(requested))
        except:
            logger.warning('Current Section Widget Failed to Update')
            print_exception()

        # logger.critical('<<<< jump_to_slider <<<<')

    @Slot()
    def reload_scales_combobox(self) -> None:
        # caller = inspect.stack()[1].function
        # logger.info(f'reload_scales_combobox [{caller}] >>>>')
        if self._isProjectTab():
            # logger.info('Reloading Scale Combobox (caller: %s)' % caller)
            self._changeScaleCombo.show()
            self._scales_combobox_switch = 0
            self._changeScaleCombo.clear()

            def pretty_scales():
                lst = []
                for s in cfg.data.scales():
                    siz = cfg.data.image_size(s=s)
                    # lst.append('%s / %dx%dpx' % (cfg.data.scale_pretty(s=s), siz[0], siz[1]))
                    # if s =
                    lst.append('%d / %d x %dpx' % (cfg.data.scale_val(s=s), siz[0], siz[1]))
                return lst

            self._changeScaleCombo.addItems(pretty_scales())
            self._changeScaleCombo.setCurrentIndex(cfg.data.scales().index(cfg.data.scale))
            self._scales_combobox_switch = 1
        else:
            self._changeScaleCombo.hide()
        # logger.info(f'<<<< reload_scales_combobox [{caller}]')

    def fn_scales_combobox(self) -> None:
        caller = inspect.stack()[1].function
        logger.info('>>>> fn_scales_combobox [caller: %s] >>>>' % caller)
        if caller in ('main', 'scale_down', 'scale_up'):

            if getData('state,manual_mode'):
                # self.reload_scales_combobox()
                # logger.warning('Exit manual alignment mode before changing scales')
                # self.warn('Exit manual alignment mode before changing scales!')
                self.exit_man_mode()

                # return

            if not self._working:
                if self._scales_combobox_switch:
                    if self._isProjectTab():
                        caller = inspect.stack()[1].function
                        logger.info('caller: %s' % caller)
                        if caller in ('main', 'scale_up', 'scale_down'):
                            # if getData('state,manual_mode'):
                            #     self.exit_man_mode()
                            # 0414-
                            index = self._changeScaleCombo.currentIndex()
                            cfg.data.scale = cfg.data.scales()[index]
                            # try:
                            #     cfg.project_tab.updateProjectLabels()
                            # except:
                            #     pass
                            self.updateEnabledButtons()
                            self.dataUpdateWidgets()
                            self.updateCpanelDetails_i1()
                            self._showSNRcheck()
                            # cfg.project_tab.project_table.initTableData()
                            # cfg.project_tab.project_table.updateTableData()
                            # cfg.project_tab.updateLabelsHeader()
                            cfg.project_tab.refreshTab()
        logger.info('<<<< fn_scales_combobox [caller: %s] <<<<' % caller)

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
                self.warn('Current scale is not aligned. Nothing to export.')
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

    # def delete_project(self):
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
        self.globTabs.addTab(OpenProject(), 'Open...')
        self._setLastTab()

    def detachNeuroglancer(self):
        logger.info('')
        if self._isProjectTab():
            if getData('state,manual_mode') == True:
                return
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
        logger.info(f'\n\n################ Loading Project - %s ################\n' % os.path.basename(cfg.data.dest()))
        self.cbMonitor.setChecked(True) #Why?

        self.tell("Loading Project '%s'..." % cfg.data.dest())

        initLogFiles(cfg.data)
        self._dontReinit = True
        caller = inspect.stack()[1].function
        # self.tell("Loading project '%s'..." %cfg.data.dest())

        setData('state,manual_mode', False)
        # setData('state,mode', 'comparison')
        # setData('state,ng_layout', 'xy')

        setData('state,mode', 'stack-xy')
        setData('state,ng_layout', 'xy')

        cfg.data['data']['current_scale'] = cfg.data.coarsest_scale_key()



        QApplication.processEvents()

        self.updateDtWidget()  # <.001s

        # cfg.data.set_defaults()  # 0.5357 -> 0.5438, ~.0081s

        t_ng = time.time()
        # cfg.project_tab.initNeuroglancer()  # dt = 0.543 -> dt = 0.587 = 0.044 ~ 1/20 second
        self.update()

        # cfg.project_tab.updateTreeWidget()  # TimeConsuming dt = 0.001 -> dt = 0.535 ~1/2 second

        # self.tell('Updating UI...')
        self.dataUpdateWidgets()  # 0.5878 -> 0.5887 ~.001s

        # self._changeScaleCombo.setCurrentText(cfg.data.scale)
        # self.spinbox_fps.setValue(czfg.DEFAULT_PLAYBACK_SPEED)
        self.spinbox_fps.setValue(float(cfg.DEFAULT_PLAYBACK_SPEED))
        # cfg.project_tab.updateTreeWidget() #TimeConsuming!! dt = 0.58 - > dt = 1.10
        try:    self._bbToggle.setChecked(cfg.data.use_bb())
        except: logger.warning('Bounding Box Toggle Failed to Update')

        # dt = 1.1032602787017822
        self.reload_scales_combobox()  # fast
        self.updateEnabledButtons()
        self.updateMenus()
        self._resetSlidersAndJumpInput()  # fast
        self.setControlPanelData()  # Added 2023-04-23

        self.enableAllTabs()  # fast
        # cfg.data.zpos = int(len(cfg.data)/2)
        self.updateNotes()
        # self._autosave()  # 0412+
        # self._sectionSlider.setValue(int(len(cfg.data) / 2))
        self._dontReinit = False

        self.cpanel.show()
        self.sa_cpanel.show()
        cfg.project_tab.showSecondaryNgTools()

        self.updateCorrSignalsDrawer()
        # self.updateAllCpanelDetails()
        self.updateCpanelDetails()
        # QApplication.processEvents()
        # self.refreshTab()


        QApplication.processEvents()
        cfg.project_tab.initNeuroglancer()
        # QApplication.processEvents()
        # cfg.project_tab.initNeuroglancer()
        check_project_status()
        # self.dw_monitor.show()
        self.hud.done()
        self.cbMonitor.setChecked(True)
        # dt = 1.1060302257537842

    def saveUserPreferences(self):
        logger.info('Saving User Preferences...')
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        # if self._isProjectTab():
        #     self.settings.setValue("hsplitter_tn_ngSizes", cfg.pt.hsplitter_tn_ng.saveState())
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
                    self.globTabs.setTabText(self.globTabs.currentIndex(), os.path.basename(name))
                    # self.statusBar.showMessage('Project Saved!', 3000)

                    # self.saveUserPreferences()

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
        logger.critical("closeEvent called by %s..." % inspect.stack()[1].function)
        # self.shutdownInstructions()

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        self.exit_app()
        QMainWindow.closeEvent(self, event)




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
        run_command('source', arg_list='tacc_bootstrap')
        self.shutdownInstructions()


    def exit_app(self):

        logger.info('sender : ' + str(self.sender()))
        if self._exiting:
            self._exiting = 0
            if self.exit_dlg.isVisible():
                self.globTabsAndCpanel.children()[-1].hide()
            return
        self._exiting = 1

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

            self.pythonConsole.kernel_client.stop_channels()
            self.pythonConsole.kernel_manager.shutdown_kernel()
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
        # self.cpanel.hide()
        self.sa_cpanel.hide()

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
        # self.cpanel.hide()
        self.sa_cpanel.hide()

    def remote_view(self):
        self.tell('Opening Neuroglancer Remote Viewer...')
        browser = WebBrowser()
        browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.globTabs.addTab(browser, 'Neuroglancer')
        self._setLastTab()
        # self.cpanel.hide()
        self.sa_cpanel.hide()

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
            if s == None: s = cfg.data.scale
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

    # def startStopProfiler(self):
    #     logger.info('')
    #     if self._isProfiling:
    #         self.profilingTimer.stop()
    #     else:
    #         self.profilingTimer.setInterval(cfg.PROFILING_TIMER_SPEED)
    #         self.profilingTimer.start()
    #     self._isProfiling = not self._isProfiling

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
            if getData('state,manual_mode'):
                new_cs_scale = cfg.refViewer.zoom() * 1.1
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.baseViewer.set_zoom(new_cs_scale)
            else:
                new_cs_scale = cfg.emViewer.zoom() * 1.1
                logger.info(f'new_cs_scale: {new_cs_scale}')
                cfg.emViewer.set_zoom(new_cs_scale)

            cfg.project_tab.zoomSlider.setValue(1 / new_cs_scale)

    def incrementZoomIn(self):
        # logger.info('')
        if ('QTextEdit' or 'QLineEdit') in str(cfg.mw.focusWidget()):
            return

        if self._isProjectTab():
            if getData('state,manual_mode'):
                if cfg.data['state']['stackwidget_ng_toggle']:
                    new_cs_scale = cfg.baseViewer.zoom() * 0.9
                    logger.info(f'new_cs_scale: {new_cs_scale}')
                    cfg.baseViewer.set_zoom(new_cs_scale)
                else:
                    new_cs_scale = cfg.refViewer.zoom() * 0.9
                    logger.info(f'new_cs_scale: {new_cs_scale}')
                    cfg.refViewer.set_zoom(new_cs_scale)

            else:
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
        self.cpanel.hide()
        self.sa_cpanel.hide()

    def tab_google(self):
        logger.info('Opening Google tab...')
        browser = WebBrowser(self)
        browser.setObjectName('web_browser')
        browser.setUrl(QUrl('https://www.google.com'))
        self.addGlobTab(browser, 'Google')
        self.cpanel.hide()
        self.sa_cpanel.hide()

    def tab_report_bug(self):
        logger.info('Opening GitHub issue tracker tab...')
        cfg.bugreport = browser = WebBrowser(self)
        browser.setUrl(QUrl('https://github.com/mcellteam/swift-ir/issues'))
        self.addGlobTab(browser, 'Issue Tracker')
        self.cpanel.hide()
        self.sa_cpanel.hide()


    def tab_workbench(self):
        logger.info('Opening 3DEM Workbench tab...')
        browser = WebBrowser(self)
        browser.setUrl(QUrl('https://3dem.org/workbench/'))
        self.addGlobTab(browser, '3DEM Workbench')
        self.cpanel.hide()
        self.sa_cpanel.hide()

    def gpu_config(self):
        logger.info('Opening GPU Config...')
        browser = WebBrowser()
        browser.setUrl(QUrl('chrome://gpu'))
        self.globTabs.addTab(browser, 'GPU Configuration')
        self._setLastTab()
        self.cpanel.hide()
        self.sa_cpanel.hide()


    def chromium_debug(self):
        logger.info('Opening Chromium Debugger...')
        browser = WebBrowser()
        browser.setUrl(QUrl('http://127.0.0.1:9000'))
        self.globTabs.addTab(browser, 'Debug Chromium')
        self._setLastTab()
        self.cpanel.hide()
        self.sa_cpanel.hide()


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
            state = self._bbToggle.isChecked()
            # self._bbToggle.setEnabled(state)
            if state:
                self.warn('Bounding Box is ON. Warning: Output dimensions may grow larger than source.')
                cfg.data['data']['defaults']['bounding-box'] = True
            else:
                self.tell('Bounding Box is OFF. Output dimensions will match source.')
                cfg.data['data']['defaults']['bounding-box'] = False

    def _callbk_skipChanged(self, state: int):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        caller = inspect.stack()[1].function
        # if caller == 'main':
        if self._isProjectTab():
            if caller != 'dataUpdateWidgets':
                # logger.critical('')
                skip_state = not self._skipCheckbox.isChecked()
                layer = cfg.data.zpos
                for s in cfg.data.scales():
                    if layer < len(cfg.data):
                        cfg.data.set_skip(skip_state, s=s, l=layer)
                    else:
                        logger.warning(f'Request layer is out of range ({layer}) - Returning')
                        return
                if skip_state:
                    self.tell("Exclude: %s" % cfg.data.name_base())
                else:
                    self.tell("Include: %s" % cfg.data.name_base())
                cfg.data.link_reference_sections()
                # if getData('state,blink'):
                self.dataUpdateWidgets()
                # if cfg.project_tab._tabs.currentIndex() == 1:
                    # cfg.project_tab.project_table.initTableData()
                cfg.pt.project_table.set_row_data(row=layer)

            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.snr_plot.initSnrPlot()

    def skip_change_shortcut(self):
        logger.info('')
        if cfg.data:
            self._skipCheckbox.setChecked(not self._skipCheckbox.isChecked())

    def runchecks(self):
        run_checks()

    def enterExitManAlignMode(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        if cfg.data:
            if self._isProjectTab():
                if not cfg.data.is_aligned_and_generated():
                    logger.warning('Cannot enter manual alignment mode until the series is aligned.')
                    self.warn('Align the series first and then use Manual Alignment.')
                    return
                if not getData('state,manual_mode'):
                    self.enter_man_mode()
                else:
                    self.exit_man_mode()

                self.setFocus()

    def onMAsyncTimer(self):
        logger.critical("")
        logger.critical(f"cfg.data.zpos         = {cfg.data.zpos}")
        logger.critical(f"cfg.refViewer.index   = {cfg.refViewer.index}")
        logger.critical(f"cfg.baseViewer.index  = {cfg.baseViewer.index}")


    def enter_man_mode(self):
        if self._isProjectTab():
            if cfg.data.is_aligned_and_generated():

                del cfg.emViewer

                logger.info('\n\nEnter Manual Alignment Mode >>>>\n')
                self.tell('Entering manual align mode')

                # cfg.project_tab.w_section_label_header.show()
                cfg.project_tab.w_ng_extended_toolbar.hide()
                cfg.pt.ma_radioboxes.show()

                setData('state,previous_mode', getData('state,mode'))
                setData('state,mode', 'manual_align')
                setData('state,manual_mode', True)

                self.updateManualAlignModeButton()
                self.updateCorrSignalsDrawer()
                # cfg.project_tab.ngVertLab.setStyleSheet("""background-color: #222222 ; color: #FFFF66;""")
                self.stopPlaybackTimer()
                self.setWindowTitle(self.window_title + ' - Manual Alignment Mode')
                # self._changeScaleCombo.setEnabled(False)
                setData('state,stackwidget_ng_toggle', 1)
                # cfg.pt.rb_transforming.setChecked(getData('state,stackwidget_ng_toggle'))
                cfg.pt.setRbTransforming()

                # self.MAsyncTimer = QTimer()
                # self.MAsyncTimer.setInterval(500)
                # self.MAsyncTimer.timeout.connect(self.onMAsyncTimer)
                # self.MAsyncTimer.start()
                # self.uiUpdateTimer.setInterval(250)

                cfg.project_tab.onEnterManualMode()
                self.hud.done()

            else:
                self.warn('Alignment must be generated before using Manual Point Alignment method.')

    def exit_man_mode(self):

        if self._isProjectTab():
            logger.critical('Exiting manual alignment mode...')
            self.tell('Exiting manual align mode')

            # try:
            #     cfg.refViewer = None
            #     cfg.baseViewer = None
            #     cfg.stageViewer = None
            # except:
            #     print_exception()

            # self.MAsyncTimer.stop()

            # cfg.project_tab.w_section_label_header.hide()
            cfg.project_tab.w_ng_extended_toolbar.show()
            cfg.pt.tn_ref.update()
            cfg.pt.tn_tra.update()
            cfg.pt.ma_radioboxes.hide()
            cfg.project_tab.ngVertLab.setStyleSheet("""background-color: #222222 ; color: #ede9e8;""")
            self.setWindowTitle(self.window_title)
            prev_mode = getData('state,previous_mode')

            if prev_mode == 'stack-xy':
                setData('state,mode', 'stack-xy')
                setData('state,ng_layout', 'xy')

            elif prev_mode == 'stack-4panel':
                setData('state,mode', 'stack-4panel')
                setData('state,ng_layout', '4panel')

            else:
                setData('state,mode', 'comparison')
                setData('state,ng_layout', 'xy')


            # cfg.project_tab.cpanel.show()

            setData('state,manual_mode', False)
            self.updateManualAlignModeButton()
            self.alignMatchPointAction.setText(f"Align Manually {hotkey('M')} ")
            # self._changeScaleCombo.setEnabled(True)
            self.dataUpdateWidgets()
            self.updateCorrSignalsDrawer()  # Caution - Likely Redundant!
            QApplication.restoreOverrideCursor()
            # cfg.project_tab.onExitManualMode()
            cfg.project_tab.showSecondaryNgTools()
            cfg.project_tab.MA_ptsListWidget_ref.clear()
            cfg.project_tab.MA_ptsListWidget_base.clear()
            cfg.project_tab._tabs.setCurrentIndex(cfg.project_tab.bookmark_tab)
            cfg.project_tab.MA_splitter.hide()
            # cfg.project_tab.w_ng_display_ext.show()
            cfg.project_tab.w_ng_display.show()
            cfg.project_tab.ngVertLab.setText('Neuroglancer 3DEM View')
            QApplication.processEvents()  # Critical! - enables viewer to acquire appropriate zoom

            # self._changeScaleCombo.setEnabled(True)

            cfg.project_tab.initNeuroglancer()
            cfg.emViewer.set_layer(cfg.data.zpos)

            check_project_status()
            self.hud.done()
            logger.info('\n\n<<<< Exit Manual Alignment Mode\n')

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
    #                     self.exit_man_mode()
    #             setData('state,previous_mode', getData('state,mode'))
    #             setData('state,mode', requested_key)
    #             if requested_key == 'stack-4panel':
    #                 setData('state,ng_layout', '4panel')
    #             elif requested_key == 'stack-xy':
    #                 setData('state,ng_layout', 'xy')
    #             elif requested_key == 'comparison':
    #                 setData('state,ng_layout', 'xy')
    #             elif requested_key == 'manual_align':
    #                 setData('state,ng_layout', 'xy')
    #                 self.enter_man_mode()
    #             self.dataUpdateWidgets()
    #             cfg.project_tab.comboNgLayout.setCurrentText(getData('state,ng_layout'))
    #             cfg.project_tab.initNeuroglancer()
    #
    #         # cfg.project_tab.updateCursor()
    #     else:
    #         self.combo_mode.setCurrentText(self.modeKeyToPretty('comparison'))

    def initToolbar(self):
        logger.info('')

        with open('src/style/buttonstyle.qss', 'r') as f:
            button_gradient_style = f.read()

        self.exitButton = QPushButton()
        self.exitButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.exitButton.setFixedSize(QSize(15,15))
        # self.exitButton.setIconSize(QSize(12,12))
        self.exitButton.setFixedSize(QSize(16, 16))
        self.exitButton.setIconSize(QSize(14, 14))
        # self.exitButton.setIcon(qta.icon('fa.close', color='#161c20'))
        self.exitButton.setIcon(qta.icon('mdi.close', color='#161c20'))
        self.exitButton.clicked.connect(self.exit_app)
        # self.exitButton.setStyleSheet(button_gradient_style)
        # self.exitButton.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif; border: none;')

        self.minimizeButton = QPushButton()
        self.minimizeButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.minimizeButton.setFixedSize(QSize(15,15))
        # self.minimizeButton.setIconSize(QSize(12,12))
        self.minimizeButton.setFixedSize(QSize(16, 16))
        self.minimizeButton.setIconSize(QSize(14, 14))
        # self.minimizeButton.setIcon(qta.icon('fa.window-minimize', color='#161c20'))
        self.minimizeButton.setIcon(qta.icon('mdi.minus-thick', color='#161c20'))
        self.minimizeButton.clicked.connect(self.showMinimized)
        # self.minimizeButton.setStyleSheet(button_gradient_style)

        self.fullScreenButton = QPushButton('Full Screen')
        self.fullScreenButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        f = QFont()
        f.setBold(True)
        f.setPixelSize(10)
        self.fullScreenButton.setFont(f)
        self.fullScreenButton.setFixedHeight(16)
        self.fullScreenButton.setIconSize(QSize(16, 16))
        # self.fullScreenButton.setIcon(qta.icon('mdi.fullscreen', color='#161c20'))
        self.fullScreenButton.setIcon(qta.icon('mdi.fullscreen', color='#161c20'))

        # def fn():
        #     # (cfg.mw.showMaximized, cfg.mw.showNormal)[cfg.mw.isMaximized()]()
        #     # self.fullScreenButton.setIcon(
        #     #     qta.icon(('mdi.fullscreen', 'mdi.fullscreen-exit')[self.isMaximized()], color='#161c20'))
        #     # self.fullScreenButton.setText(('Full Screen', 'Exit Full Screen')[self.isMaximized()])
        #
        #
        #     (cfg.mw.showFullScreen(), cfg.mw.showNormal)[cfg.mw.isFullScreen()]()
        #     self.fullScreenButton.setIcon(
        #         qta.icon(('mdi.fullscreen', 'mdi.fullscreen-exit')[self.isFullScreen()], color='#161c20'))
        #     self.fullScreenButton.setText(('Full Screen', 'Exit Full Screen')[self.isFullScreen()])
        #
        #     if self._isProjectTab():
        #         cfg.project_tab.initNeuroglancer()
        #         QApplication.processEvents()
        #         self.refreshTab()

        # self.fullScreenButton.clicked.connect(fn)
        self.fullScreenButton.clicked.connect(self.fullScreenCallback)
        # self.fullScreenButton.setStyleSheet(button_gradient_style)

        self.refreshButton = QPushButton(' Refresh')
        self.refreshButton .setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refreshButton.setFont(f)
        # self.refreshButton.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.refreshButton.setToolTip(f"Refresh View {hotkey('R')}")
        self.refreshButton.setFixedHeight(16)
        self.refreshButton.setIconSize(QSize(16, 16))
        self.refreshButton.setIcon(qta.icon('mdi.refresh', color='#161c20'))
        self.refreshButton.clicked.connect(self.refreshTab)

        self.faqButton = QPushButton(' FAQ')
        self.faqButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        def fn_view_faq():
            search = self.lookForTabID(search='faq')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("FAQ is already open!", msecs=3000)
            else:
                logger.info('Showing FAQ...')
                self.html_resource(resource='faq.html', title='FAQ', ID='faq')

        self.faqButton.setFont(f)
        # self.faqButton.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.faqButton.setToolTip(f"Read AlignEM-SWiFT FAQ")
        self.faqButton.setFixedHeight(16)
        self.faqButton.setFixedWidth(40)
        self.faqButton.setIconSize(QSize(16, 16))
        # self.faqButton.setIcon(qta.icon('fa.info-circle', color='#161c20'))
        self.faqButton.clicked.connect(fn_view_faq)

        self.gettingStartedButton = QPushButton('Getting Started')
        self.gettingStartedButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # def fn_view_faq():
        #     logger.info('Showing FAQ...')
        #     search = self.lookForTabID(search='FAQ')
        #     if search:
        #         self.globTabs.setCurrentIndex(search)
        #         self.statusBar.showMessage("FAQ is already open!", msecs=3000)
        #     else:
        #         self.html_resource(resource='faq.html', title='FAQ', ID='FAQ')
        def fn_view_getting_started():
            search = self.lookForTabID(search='getting-started')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("Getting started document is already open!", msecs=3000)
            else:
                logger.info('Showing Getting Started Tips...')
                self.html_resource(resource='getting-started.html', title='Getting Started', ID='getting-started')
        self.gettingStartedButton.setFont(f)
        # self.gettingStartedButton.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.gettingStartedButton.setToolTip(f"Read AlignEM-SWiFT Tips for Getting Started")
        self.gettingStartedButton.setFixedHeight(16)
        self.gettingStartedButton.setIconSize(QSize(16, 16))
        # self.gettingStartedButton.setIcon(qta.icon('fa.info-circle', color='#161c20'))
        self.gettingStartedButton.clicked.connect(fn_view_getting_started)

        self.glossaryButton = QPushButton('Glossary')
        def fn_glossary():
            search = self.lookForTabID(search='glossary')
            if search:
                self.globTabs.setCurrentIndex(search)
                self.statusBar.showMessage("Glossary is already open!", msecs=3000)
            else:
                logger.info('Showing Glossary...')
                self.html_resource(resource='glossary.html', title='Glossary', ID='glossary')
        self.glossaryButton.setFont(f)
        # self.glossaryButton.setStyleSheet('font-size: 10px; font-family: Tahoma, sans-serif;')
        self.glossaryButton.setToolTip(f"Read AlignEM-SWiFT Glossary")
        self.glossaryButton.setFixedHeight(16)
        self.glossaryButton.setIconSize(QSize(16, 16))
        # self.glossaryButton.setIcon(qta.icon('fa.info-circle', color='#161c20'))
        self.glossaryButton.clicked.connect(fn_glossary)


        self.bugreportButton = QPushButton('Report Bug')
        self.bugreportButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bugreportButton.setFont(f)
        self.bugreportButton.setFixedHeight(16)
        self.bugreportButton.setIconSize(QSize(16, 16))
        self.bugreportButton.clicked.connect(self.tab_report_bug)

        self.workbenchButton = QPushButton('3DEM Workbench')
        self.workbenchButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.workbenchButton.setFont(f)
        self.workbenchButton.setFixedHeight(16)
        self.workbenchButton.setIconSize(QSize(16, 16))
        self.workbenchButton.clicked.connect(self.tab_workbench)


        self.navWidget = HWidget(QLabel(' '), self.exitButton, self.minimizeButton, self.fullScreenButton,
                                 self.refreshButton, self.faqButton, self.gettingStartedButton, self.glossaryButton, self.bugreportButton, ExpandingWidget(self))
        self.navWidget.setFixedHeight(18)
        # self.navWidget.setC

        self.toolbar = QToolBar()
        # self.toolbar.setIconSize(QSize(18,18))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.toolbar.setFixedHeight(32)
        self.toolbar.setFixedHeight(20)
        self.toolbar.setObjectName('toolbar')
        # self.addToolBar(self.toolbar)

        style = """
        QPushButton {
            color: #161c20;
            background-color: #dadada;
            border-width: 1px;
            border-color: #c7c7c7;
            border-style: solid;
            margin: 1px;
            border-radius: 4px;
            font-size: 10px;
        }
        QPushButton:pressed { 
            border-color: #ede9e8;
            border-width: 2px;
            border-style: inset;
        }
        """
        with open('src/style/buttonstyle.qss', 'r') as f:
            button_gradient_style = f.read()

        # tb_button_size = QSize(64,18)
        tb_button_size = QSize(90, 16)

        tip = f"Show Notepad Tool Window {hotkey('Z')}"
        # self.cbNotes = QPushButton(' Notes')
        # self.cbNotes = QCheckBox(f"Notes {hotkey('N')}")
        # self.cbNotes = QCheckBox(f"Notes {hotkey('N')}")
        self.cbNotes = QCheckBox(f"Notes {hotkey('Z')}")
        # self.cbNotes.setStyleSheet(button_gradient_style)
        # self.cbNotes.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.cbNotes.setToolTip(tip)
        self.cbNotes.setIconSize(QSize(14, 14))
        # self.cbNotes.setIcon(QIcon('src/resources/notepad-icon.png'))
        self.cbNotes.stateChanged.connect(lambda: self.setdw_notes(self.cbNotes.isChecked()))

        tip = f"Show Python Console Tool Window {hotkey('P')}"
        # self.cbPython = QPushButton('Python')
        self.cbPython = QCheckBox(f"Python Console {hotkey('P')}")
        # self.cbPython.setStyleSheet(button_gradient_style)
        # self.cbPython.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.cbPython.setToolTip(tip)
        self.cbPython.setIconSize(QSize(14, 14))
        # self.cbPython.setIcon(QIcon('src/resources/python-icon.png'))
        # self.cbPython.stateChanged.connect(self._callbk_showHidePython)
        self.cbPython.stateChanged.connect(lambda: self.setdw_python(self.cbPython.isChecked()))

        tip = f"Show Process Monitor Tool Window {hotkey('H')}"
        # self.cbMonitor = QPushButton(' HUD')
        self.cbMonitor = QCheckBox(f"Process Monitor {hotkey('H')}")
        # self.cbMonitor.setStyleSheet(button_gradient_style)
        # self.cbMonitor.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        self.cbMonitor.setToolTip(tip)
        self.cbMonitor.setIconSize(QSize(14, 14))
        # self.cbMonitor.setIcon(QIcon('src/resources/python-icon.png'))
        # self.cbMonitor.setIcon(qta.icon("mdi.monitor", color='#161c20'))
        self.cbMonitor.stateChanged.connect(lambda: self.setdw_monitor(self.cbMonitor.isChecked()))


        def toggleThumbnailsVisibility():
            if self._isProjectTab():
                state = self.cbThumbnails.isChecked()
                setData('state,tool_windows,signals', state)
                new_size = (0, 200)[state]
                cfg.pt.tn_widget.setVisible(state)
                sizes = cfg.pt.hsplitter_tn_ng.sizes()
                sizes[0] = new_size
                cfg.pt.hsplitter_tn_ng.setSizes(sizes)
                self.showRawThumbnailsAction.setText(('Show Match Signals', 'Hide Match Signals')[state])
                tip1 = '\n'.join(f"Show Match Signals {hotkey('I')}")
                tip2 = '\n'.join(f"Hide Match Signals {hotkey('I')}")
                self.cbThumbnails.setToolTip((tip1, tip2)[state])

        tip = f"Show Raw Thumbnails {hotkey('T')}"
        self.cbThumbnails = QCheckBox(f"Raw Thumbnails {hotkey('T')}")
        self.cbThumbnails.stateChanged.connect(toggleThumbnailsVisibility)
        self.cbThumbnails.setToolTip(tip)
        self.cbThumbnails.setIconSize(QSize(14, 14))
        self.cbThumbnails.stateChanged.connect(toggleThumbnailsVisibility)

        def toggleSignalVisibility():
            if self._isProjectTab():
                state = self.cbSignals.isChecked()
                setData('state,tool_windows,signals', state)
                new_size = (0,400)[state]
                cfg.pt.ms_widget.setVisible(state)
                sizes = cfg.pt.hsplitter_tn_ng.sizes()
                sizes[2] = new_size
                cfg.pt.hsplitter_tn_ng.setSizes(sizes)
                self.showMatchSignalsAction.setText(('Show Match Signals', 'Hide Match Signals')[state])
                tip1 = '\n'.join(f"Show Match Signals {hotkey('I')}")
                tip2 = '\n'.join(f"Hide Match Signals {hotkey('I')}")
                self.cbSignals.setToolTip((tip1, tip2)[state])


        tip = f"Show Match Signals {hotkey('I')}"
        self.cbSignals = QCheckBox(f"Match Signals {hotkey('I')}")
        self.cbSignals.setToolTip(tip)
        self.cbSignals.setIconSize(QSize(14, 14))
        self.cbSignals.stateChanged.connect(toggleSignalVisibility)

        self._detachNgButton = QPushButton()
        self._detachNgButton.setFixedSize(QSize(18, 18))
        self._detachNgButton.setIconSize(QSize(14, 14))
        self._detachNgButton.setIcon(qta.icon("fa.external-link-square", color='#161c20'))
        self._detachNgButton.clicked.connect(self.detachNeuroglancer)
        self._detachNgButton.setToolTip('Detach Neuroglancer (open in a separate window)')

        self.toolbar.addWidget(ExpandingWidget(self))
        self.toolbar.addWidget(self.cbThumbnails)
        self.toolbar.addWidget(self.cbSignals)
        self.toolbar.addWidget(self.cbMonitor)
        self.toolbar.addWidget(self.cbPython)
        self.toolbar.addWidget(self.cbNotes)


        # self.cbSignals.setFixedSize(QSize(146, 16))  # tacc
        # self.cbThumbnails.setFixedSize(QSize(130, 16))
        # self.cbMonitor.setFixedSize(QSize(148, 16))  # tacc
        # self.cbPython.setFixedSize(QSize(148, 16))  # tacc
        # self.cbNotes.setFixedSize(QSize(96, 16))




        self.toolbar.layout().setSpacing(4)
        self.toolbar.layout().setAlignment(Qt.AlignRight)
        self.toolbar.setStyleSheet('font-size: 10px; font-weight: 600; color: #161c20;')

    # def resizeEvent(self, e):
    #     logger.info('')

    def fullScreenCallback(self):
        logger.info('')
        (self.showMaximized, self.showNormal)[self.isMaximized()]()
        self.fullScreenButton.setIcon(
            qta.icon(('mdi.fullscreen', 'mdi.fullscreen-exit')[self.isMaximized()], color='#161c20'))
        self.fullScreenButton.setText(('Full Screen', 'Exit Full Screen')[self.isMaximized()])

        # (cfg.mw.showFullScreen(), cfg.mw.showNormal)[cfg.mw.isFullScreen()]()
        # self.fullScreenButton.setIcon(
        #     qta.icon(('mdi.fullscreen', 'mdi.fullscreen-exit')[self.isFullScreen()], color='#161c20'))
        # self.fullScreenButton.setText(('Full Screen', 'Exit Full Screen')[self.isFullScreen()])

        if self._isProjectTab():
            QApplication.processEvents()
            cfg.project_tab.initNeuroglancer()


    def _disableGlobTabs(self):
        indexes = list(range(0, self.globTabs.count()))
        indexes.remove(self.globTabs.currentIndex())
        for i in indexes:
            self.globTabs.setTabEnabled(i, False)
        # self._btn_refreshTab.setEnabled(False)

    def enableAllTabs(self):
        indexes = list(range(0, self.globTabs.count()))
        for i in indexes:
            self.globTabs.setTabEnabled(i, True)
        if cfg.project_tab:
            for i in range(0, 4):
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

    def isManual(self):
        return getData('state,manual_mode')


    def addGlobTab(self, tab_widget, name):
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

        caller = inspect.stack()[1].function
        logger.info(f'_onGlobTabChange [{caller}]')
        # if caller not in ('onStartProject', '_setLastTab'): #0524-
        #     self.shutdownNeuroglancer()  # 0329+

        tabtype = self._getTabType()
        # if tabtype == 'ProjectTab':
        #     logger.critical('Loading Project Tab...')
        #     self.cpanel.show()
        #     self.statusBar.setStyleSheet("""
        #             font-size: 10px; font-weight: 600;
        #             color: #ede9e8; background-color: #222222;
        #             margin: 0px; padding: 0px;
        #             """)
        # else:
        #     self.statusBar.setStyleSheet("""
        #             font-size: 10px; font-weight: 600;
        #             color: #141414; background-color: #ede9e8;
        #             margin: 0px; padding: 0px;
        #             """)

        # if caller  == '_setLastTab':
        #     logger.critical('\n\n<<<<< DONT REINIT (caller = _setLastTab)! >>>>>\n')
        #     return

        cfg.project_tab = None
        cfg.zarr_tab = None
        self.globTabs.show()  # nec?
        self.enableAllTabs()  # Critical - Necessary for case of glob tab closure during disabled state for MA Mode
        self.stopPlaybackTimer()
        self._changeScaleCombo.clear()
        # self.combo_mode.clear()
        self._jumpToLineedit.clear()
        self._sectionSlider.setValue(0)
        self._sectionSlider.setRange(0, 0)
        # self._changeScaleCombo.setEnabled(True)  # needed for disable on MA
        # self.clearCorrSpotsDrawer()
        QApplication.restoreOverrideCursor()

        self.secName.setText('N/A')
        self.secReference.setText('N/A')
        self.secExcluded.setText('N/A')
        self.secHasBB.setText('N/A')
        self.secUseBB.setText('N/A')
        self.secAlignmentMethod.setText('N/A')
        self.secSrcImageSize.setText('N/A')
        self.secAlignedImageSize.setText('N/A')
        self.secAffine.setText('N/A')
        self.secDefaults.setText('N/A')

        if tabtype == 'OpenProject':
            configure_project_paths()
            self._getTabObject().user_projects.set_data()
            self.cpanel.hide()
            self.sa_cpanel.hide()
            self.statusBar.clearMessage()

        elif tabtype == 'ProjectTab':

            cfg.data = self.globTabs.currentWidget().datamodel
            cfg.project_tab = cfg.pt = self.globTabs.currentWidget()
            # self.statusBar.setStyleSheet("""
            #         font-size: 10px;
            #         font-weight: 600;
            #         color: #f3f6fb;
            #         background-color: #222222;
            #         margin: 0px;
            #         padding: 0px;
            #         """)
            # self.set_nglayout_combo_text(layout=cfg.data['state']['mode'])  # must be before initNeuroglancer
            self.dataUpdateWidgets()

            self.updateManualAlignModeButton()

            # cfg.project_tab.refreshTab() #Todo - Refactor! may init ng twice.

            try:
                self.setControlPanelData()
            except:
                print_exception()

            # self.updateAllCpanelDetails()
            try:
                self.updateCpanelDetails()
            except:
                print_exception()
            # self.dataUpdateResults()
            # cfg.project_tab.updateLabelsHeader()

            try:
                if not getData('state,manual_mode'):
                    cfg.project_tab.showSecondaryNgTools()
                else:
                    cfg.project_tab.hideSecondaryNgTools()
            except:
                print_exception()

            cfg.emViewer = cfg.project_tab.viewer
            # cfg.project_tab.initNeuroglancer()

            # try:
            #     cfg.project_tab.signalsAction.setChecked(False)
            # except:
            #     print_exception()
            #     logger.warning('Cant deactivate signalsAction QAction')

            # if getData('state,manual_mode'):
            #     self._changeScaleCombo.setEnabled(False)

            self.cpanel.show()
            self.sa_cpanel.show()

        elif tabtype == 'ZarrTab':
            logger.critical('Loading Zarr Tab...')
            cfg.zarr_tab = self.globTabs.currentWidget()
            cfg.emViewer = cfg.zarr_tab.viewer
            # self.set_nglayout_combo_text(layout='4panel')
            cfg.zarr_tab.viewer.bootstrap()

        self.updateMenus()
        self._resetSlidersAndJumpInput()  # future changes to image importing will require refactor
        self.reload_scales_combobox()
        self.updateEnabledButtons()
        self.updateNotes()
        self.setFocus()

    def _onGlobTabClose(self, index):
        if not self._working:
            logger.info(f'Closing Tab: {index}')
            self.globTabs.removeTab(index)

    def _setLastTab(self):
        self.globTabs.setCurrentIndex(self.globTabs.count() - 1)

    def new_mendenhall_protocol(self):
        # self.new_project(mendenhall=True)
        # scale = cfg.data.scale
        # cfg.data['data']['cname'] = 'none'
        # cfg.data['data']['clevel'] = 5
        # cfg.data['data']['chunkshape'] = (1, 512, 512)
        # cfg.data['data']['scales'][scale]['resolution_x'] = 2
        # cfg.data['data']['scales'][scale]['resolution_y'] = 2
        # cfg.data['data']['scales'][scale]['resolution_z'] = 50
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

    def updateMenus(self):
        '''NOTE: This should always be run AFTER initializing Neuroglancer!'''
        caller = inspect.stack()[1].function
        logger.info('')
        self.tensorMenu.clear()
        if self._isProjectTab() or self._isZarrTab():
            # logger.info('Clearing menus...')

            def addTensorMenuInfo(label, body):
                menu = self.tensorMenu.addMenu(label)
                textedit = QTextEdit(self)
                textedit.setFixedSize(QSize(600, 600))
                textedit.setReadOnly(True)
                textedit.setText(body)
                action = QWidgetAction(self)
                action.setDefaultWidget(textedit)
                menu.addAction(action)

            if self._isProjectTab():
                try:
                    addTensorMenuInfo(label='Tensor Metadata', body=json.dumps(cfg.tensor.spec().to_json(), indent=2))
                except:
                    print_exception()
                # if cfg.unal_tensor:
                #     # logger.info('Adding Raw Series tensor to menu...')
                #     txt = json.dumps(cfg.unal_tensor.spec().to_json(), indent=2)
                #     addTensorMenuInfo(label='Raw Series', body=txt)
                # if cfg.data.is_aligned():
                #     if cfg.al_tensor:
                #         # logger.info('Adding Aligned Series tensor to menu...')
                #         txt = json.dumps(cfg.al_tensor.spec().to_json(), indent=2)
                #         addTensorMenuInfo(label='Aligned Series', body=txt)
            if self._isZarrTab():
                try:
                    addTensorMenuInfo(label='Zarr Series', body=json.dumps(cfg.tensor.spec().to_json(), indent=2))
                except:
                    print_exception()
            try:
                self.updateNgMenuStateWidgets()
            except:
                print_exception()
        else:
            self.clearNgStateMenus()

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


    def turnBlinkOnOff(self):
        if self._isProjectTab():
            setData('state,blink', not getData('state,blink'))
            logger.info(f"blink toggle: {getData('state,blink')}")
            # self.tell(f"Blink : {('OFF','ON')[getData('state,blink')]}")
            cfg.pt.blinkToggle.setChecked(getData('state,blink'))
            if getData('state,blink'):
                cfg.pt.blinkTimer.start()
            else:
                cfg.pt.blinkTimer.stop()


    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')

        # self.scManualAlign = QShortcut(QKeySequence('Ctrl+M'), self)
        # self.scManualAlign.activated.connect(self.enterExitManAlignMode)

        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setStyleSheet("font-size: 10px;")

        # Fix for non-native menubar on macOS
        self.menu.setNativeMenuBar(False)
        # self.menu.setNativeMenuBar(True)


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
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.setShortcutContext(Qt.ApplicationShortcut)
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
        self.addAction(self.refreshAction)
        fileMenu.addAction(self.refreshAction)

        # self.showNotesAction = QAction('Show &Notes', self)
        self.showNotesAction = QAction('Show &Notes', self)
        self.showNotesAction.triggered.connect(lambda: self.cbNotes.setChecked(not self.cbNotes.isChecked()))
        # self.showNotesAction.setShortcut('Ctrl+Z')
        # self.showNotesAction.setShortcutContext(Qt.ApplicationShortcut)
        fileMenu.addAction(self.showNotesAction)

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

        self.showPythonAction = QAction('Show &Python', self)
        self.showPythonAction.triggered.connect(lambda: self.cbPython.setChecked(not self.cbPython.isChecked()))
        self.showPythonAction.setShortcut('Ctrl+P')
        self.showPythonAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.showPythonAction)

        self.showMonitorAction = QAction('Show Process &Monitor', self)
        self.showMonitorAction.triggered.connect(lambda: self.cbMonitor.setChecked(not self.cbMonitor.isChecked()))
        # self.showMonitorAction.setShortcut('Ctrl+H')
        # self.showMonitorAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.showMonitorAction)

        self.showRawThumbnailsAction = QAction('Show Raw &Thumbnails', self)
        self.showRawThumbnailsAction.triggered.connect(lambda: self.cbThumbnails.setChecked(not self.cbThumbnails.isChecked()))
        # self.showRawThumbnailsAction.setShortcut('Ctrl+T')
        # self.showRawThumbnailsAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.showRawThumbnailsAction)

        self.showMatchSignalsAction = QAction('Show Match S&ignals', self)
        self.showMatchSignalsAction.triggered.connect(lambda: self.cbSignals.setChecked(not self.cbSignals.isChecked()))
        # self.showMatchSignalsAction.setShortcut('Ctrl+I')
        # self.showMatchSignalsAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.showMatchSignalsAction)


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
        self.zoomInAction.setShortcut(QKeySequence('up'))
        self.zoomInAction.setShortcutContext(Qt.ApplicationShortcut)
        viewMenu.addAction(self.zoomInAction)

        self.zoomOutAction = QAction('Zoom Out', self)
        self.zoomOutAction.triggered.connect(self.incrementZoomOut)
        self.zoomOutAction.setShortcut(QKeySequence('down'))
        self.zoomOutAction.setShortcutContext(Qt.ApplicationShortcut)
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

        menu = alignMenu.addMenu('History')
        action = QWidgetAction(self)
        action.setDefaultWidget(self._tool_hstry)
        menu.addAction(action)

        self.alignAllAction = QAction('Align All Current Scale', self)
        self.alignAllAction.triggered.connect(self.alignAll)
        self.alignAllAction.setShortcut('Ctrl+A')
        alignMenu.addAction(self.alignAllAction)

        self.alignAllScalesAction = QAction('Align Scales to Full Res', self)
        self.alignAllScalesAction.triggered.connect(self.alignAllScales)
        alignMenu.addAction(self.alignAllScalesAction)

        self.alignOneAction = QAction('Align Current Section', self)
        self.alignOneAction.triggered.connect(self.alignGenerateOne)
        alignMenu.addAction(self.alignOneAction)

        self.alignMatchPointAction = QAction(f"Align Manually {hotkey('M')}", self)
        self.alignMatchPointAction.triggered.connect(self.enterExitManAlignMode)
        # self.alignMatchPointAction.setShortcut('Ctrl+M')
        # self.alignMatchPointAction.setShortcutContext(Qt.ApplicationShortcut)
        alignMenu.addAction(self.alignMatchPointAction)
        # self.addAction(self.alignMatchPointAction)

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
        self.blinkAction.triggered.connect(self.turnBlinkOnOff)
        self.blinkAction.setShortcut('Ctrl+B')
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

        from src.ui.snr_plot import SnrPlot
        tw = SnrPlot()

        testMenu = debugMenu.addMenu('Test Menu Widgets')
        action = QWidgetAction(self)
        action.setDefaultWidget(tw)
        testMenu.addAction(action)


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
    #         # cfg.data.set_swim_window_global(float(self._swimWindowControl.value()) / 100.)
    #         cfg.data.set_swim_1x1_custom_px(self._swimWindowControl.value())

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
            val = float(self.sb_whiteningControl.value())
            cfg.data.default_whitening = val
            self.tell('Signal Whitening is set to %.3f' % val)
            self.updateCpanelDetails_i1()

    def _valueChangedPolyOrder(self):
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if self._polyBiasCombo.currentText() == 'None':
                cfg.data.default_poly_order = None
                self.tell('Corrective Polynomial Order is set to None')
            else:
                txt = self._polyBiasCombo.currentText()
                index = cfg.mw._polyBiasCombo.findText(txt)
                val = index - 1
                cfg.data.default_poly_order = val
                self.tell('Corrective Polynomial Order is set to %d' % val)



    def _toggledAutogenerate(self) -> None:
        # logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if self._toggleAutogenerate.isChecked():
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

        button_size = QSize(58, 16)
        std_input_size = QSize(64, 16)
        # normal_button_size = QSize(68, 28)
        normal_button_size = QSize(76, 30)
        # long_button_size = QSize(138, 13)
        long_button_size = QSize(146, 16)
        left = Qt.AlignmentFlag.AlignLeft
        right = Qt.AlignmentFlag.AlignRight

        ctl_lab_style = 'color: #ede9e8; font-size: 10px;'

        tip = """Sections marked for exclusion will not be aligned or used by SWIM in any way (like a dropped frame)."""
        self._lab_keep_reject = QLabel('Include:')
        self._lab_keep_reject.setStyleSheet(ctl_lab_style)
        self._lab_keep_reject.setToolTip(tip)
        self._skipCheckbox = ToggleSwitch()
        self._skipCheckbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._skipCheckbox.stateChanged.connect(self._callbk_skipChanged)
        self._skipCheckbox.stateChanged.connect(self._callbk_unsavedChanges)
        self._skipCheckbox.stateChanged.connect(self.updateCpanelDetails_i1)
        self._skipCheckbox.setToolTip(tip)
        self._skipCheckbox.setEnabled(False)

        self.labInclude = QLabel('Include Section:')
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

        tip = """A SWIM parameter which takes values in the range of -1.00 and 0.00 (default=-0.68)."""
        lab = QLabel("Whitening\nFactor:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(left)
        self.sb_whiteningControl = QDoubleSpinBox(self)
        self.sb_whiteningControl.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.sb_whiteningControl.setFixedSize(QSize(50, 18))
        self.sb_whiteningControl.valueChanged.connect(self._callbk_unsavedChanges)
        self.sb_whiteningControl.valueChanged.connect(self._valueChangedWhitening)
        self.sb_whiteningControl.setDecimals(2)
        self.sb_whiteningControl.setSingleStep(.01)
        self.sb_whiteningControl.setMinimum(-2)
        self.sb_whiteningControl.setMaximum(2)

        tip = """The number of sequential SWIM refinements to alignment. In general, greater iterations results in a more refined alignment up to some limit, except for in cases of local maxima or complete misalignment (default=3)."""
        self.sb_SWIMiterations = QSpinBox(self)
        self.sb_SWIMiterations.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.sb_SWIMiterations.setFixedSize(QSize(50, 18))
        self.sb_SWIMiterations.valueChanged.connect(self._callbk_unsavedChanges)

        def fn_swim_iters():
            caller = inspect.stack()[1].function
            if caller == 'main':
                setData('data,defaults,swim-iterations', self.sb_SWIMiterations.value())
                self.updateCpanelDetails_i1()

        self.sb_SWIMiterations.valueChanged.connect(fn_swim_iters)
        self.sb_SWIMiterations.setMinimum(1)
        self.sb_SWIMiterations.setMaximum(9)

        tip = f"""The full width in pixels of an imaginary, centered grid which SWIM 
        aligns against (default={cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC * 100}% of image width)."""
        lab = QLabel("SWIM\nWindow:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(left)
        # self._swimWindowControl = QSpinBox(self)
        self._swimWindowControl = QLineEdit(self)
        self._swimWindowControl.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._swimWindowControl.setFixedSize(QSize(50, 18))
        def fn():
            # logger.info('')
            caller = inspect.stack()[1].function
            if self._isProjectTab():
                if caller == 'main':
                    logger.info(f'caller: {caller}')
                    try:
                        val = int(self._swimWindowControl.text())
                    except:
                        self._swimWindowControl.setText(str(cfg.data['data']['defaults'][cfg.data.scale]['swim-window-px'][0]))
                        return
                    logger.critical(f"val = {val}")
                    if (val % 2) == 1:
                        new_val = val - 1
                        self.tell(f'SWIM requires even values as input. Setting value to {new_val}')
                        self._swimWindowControl.setText(str(new_val))
                        return
                    logger.critical(f"val = {val}...........")
                    # cfg.data.set_auto_swim_windows_to_default(factor=float(self._swimWindowControl.text()) / cfg.data.image_size()[0])
                    cfg.data.set_auto_swim_windows_to_default(factor=val / cfg.data.image_size()[0])
                    # self.swimWindowChanged.emit()

                    if getData('state,manual_mode'):
                        cfg.baseViewer.drawSWIMwindow()
                        cfg.refViewer.drawSWIMwindow()

                cfg.pt.tn_ref.update()
                cfg.pt.tn_tra.update()
                self.tell(f'SWIM Window set to: {str(val)}')
        self._swimWindowControl.selectionChanged.connect(fn)
        self._swimWindowControl.returnPressed.connect(fn)
        self._swimWindowControl.returnPressed.connect(fn)
        self._swimWindowControl.selectionChanged.connect(self._callbk_unsavedChanges)
        self._swimWindowControl.returnPressed.connect(self._callbk_unsavedChanges)
        self._swimWindowControl.setValidator(QIntValidator())
        # self._swimWindowControl.setFixedSize(std_input_size)

        # # tip = 'Apply SWIM Window and Whitening Factor settings to entire dataset.'
        # self._ctlpanel_applyAllButton = QPushButton("Apply Settings\nEverywhere")
        # self._ctlpanel_applyAllButton.setStyleSheet('font-size: 8px;')
        # # self._ctlpanel_applyAllButton = QPushButton("Apply To All")
        # self._ctlpanel_applyAllButton.setEnabled(False)
        # self._ctlpanel_applyAllButton.setStatusTip('Apply These Settings To The Entire Image Stack')
        # self._ctlpanel_applyAllButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self._ctlpanel_applyAllButton.clicked.connect(self.apply_all)
        # # self._ctlpanel_applyAllButton.setFixedSize(QSize(54, 20))
        # self._ctlpanel_applyAllButton.setFixedSize(normal_button_size)

        tip = 'Go To Previous Section.'
        self._btn_prevSection = QPushButton()
        self._btn_prevSection.setObjectName('z-index-left-button')
        self._btn_prevSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_prevSection.setToolTip(tip)
        self._btn_prevSection.clicked.connect(self.layer_left)
        self._btn_prevSection.setFixedSize(QSize(16, 16))
        self._btn_prevSection.setIconSize(QSize(14, 14))
        self._btn_prevSection.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))
        self._btn_prevSection.setEnabled(False)

        tip = 'Go To Next Section.'
        self._btn_nextSection = QPushButton()
        self._btn_nextSection.setObjectName('z-index-right-button')
        self._btn_nextSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_nextSection.setToolTip(tip)
        self._btn_nextSection.clicked.connect(self.layer_right)
        self._btn_nextSection.setFixedSize(QSize(16, 16))
        self._btn_nextSection.setIconSize(QSize(14, 14))
        self._btn_nextSection.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))
        self._btn_nextSection.setEnabled(False)

        # self.labSectionChange = QLabel('   Section: ')
        # self.labSectionChange.setStyleSheet('font-size: 10px;')

        self._sectionChangeWidget = HWidget(self._btn_prevSection, self._btn_nextSection)
        # self._sectionChangeWidget.setLayout(HBL(self.labSectionChange, self._btn_prevSection, self._btn_nextSection))
        # self._sectionChangeWidget.setLayout(HBL(self._btn_prevSection, self._btn_nextSection))
        self._sectionChangeWidget.layout.setAlignment(Qt.AlignCenter)
        # self._sectionChangeWidget.setAutoFillBackground(True)

        tip = 'Go To Previous Scale.'
        self._scaleDownButton = QPushButton()
        self._scaleDownButton.setEnabled(False)
        self._scaleDownButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleDownButton.setToolTip(tip)
        self._scaleDownButton.clicked.connect(self.scale_down)
        # self._scaleDownButton.setFixedSize(QSize(12, 12))
        self._scaleDownButton.setFixedSize(QSize(16, 16))
        self._scaleDownButton.setIconSize(QSize(14, 14))
        self._scaleDownButton.setIcon(qta.icon("fa.arrow-down", color=ICON_COLOR))

        tip = 'Go To Next Scale.'
        self._scaleUpButton = QPushButton()
        self._scaleUpButton.setEnabled(False)
        self._scaleUpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleUpButton.setToolTip(tip)
        self._scaleUpButton.clicked.connect(self.scale_up)
        # self._scaleUpButton.setFixedSize(QSize(12, 12))
        self._scaleUpButton.setFixedSize(QSize(16, 16))
        self._scaleUpButton.setIconSize(QSize(14, 14))
        self._scaleUpButton.setIcon(qta.icon("fa.arrow-up", color=ICON_COLOR))

        self._scaleSetWidget = HWidget(self._scaleDownButton, self._scaleUpButton)
        self._scaleSetWidget.layout.setAlignment(Qt.AlignCenter)

        self._sectionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self._sectionSlider.setObjectName('z-index-slider')
        # self._sectionSlider.setFixedWidth(76)
        self._sectionSlider.setFocusPolicy(Qt.StrongFocus)
        self._sectionSlider.valueChanged.connect(self.jump_to_slider)



        '''section # / jump-to lineedit'''
        tip = 'Jumpt to section #'
        self._jumpToLineedit = QLineEdit(self)
        self._jumpToLineedit.setFocusPolicy(Qt.ClickFocus)
        self._jumpToLineedit.setToolTip(tip)
        self._jumpToLineedit.setFixedSize(QSize(32, 16))
        self._jumpToLineedit.returnPressed.connect(self.jump_to_layer)
        # self._jumpToLineedit.returnPressed.connect(lambda: self.jump_to(int(self._jumpToLineedit.text())))

        # hbl = QHBoxLayout()
        # hbl.setContentsMargins(4, 0, 4, 0)
        # hbl.addWidget(HWidget(QLabel('Section:'), self._jumpToLineedit))
        # self._jumpToSectionWidget = QWidget()
        # self._jumpToSectionWidget.setLayout(hbl)
        # self.toolbar.addWidget(self._sectionSlider)

        self._btn_automaticPlayTimer = QPushButton()
        self._btn_automaticPlayTimer.setIconSize(QSize(11, 11))
        self._btn_automaticPlayTimer.setFixedSize(14, 14)
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        # self._btn_automaticPlayTimer.setIcon(QIcon('src/resources/play-button.png'))
        # 0505
        self.automaticPlayTimer = QTimer(self)
        self._btn_automaticPlayTimer.clicked.connect(self.startStopTimer)

        def onTimer():
            logger.info('')
            # self.automaticPlayTimer.setInterval(1000 / self.spinbox_fps.value())
            self.automaticPlayTimer.setInterval(int(1000 / self.spinbox_fps.value()))
            if cfg.data:
                if cfg.project_tab:
                    if self._sectionSlider.value() < len(cfg.data) - 1:
                        self._sectionSlider.setValue(self._sectionSlider.value() + 1)
                    else:
                        self._sectionSlider.setValue(0)
                        self.automaticPlayTimer.stop()
                        self._isPlayingBack = 0
                        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
                        # self._btn_automaticPlayTimer.setIcon(QIcon('src/resources/play-button.png'))

        self.automaticPlayTimer.timeout.connect(onTimer)
        self._sectionSliderWidget = QWidget()

        hbl = QHBoxLayout()
        hbl.setSpacing(0)
        hbl.setContentsMargins(2, 0, 2, 0)
        # hbl.addWidget(self._btn_automaticPlayTimer, alignment=Qt.AlignmentFlag.AlignRight)
        # hbl.addWidget(self._sectionSlider, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(self._btn_automaticPlayTimer)
        hbl.addWidget(self._sectionSlider)
        self._sectionSliderWidget.setLayout(hbl)

        lab = QLabel('Speed (fps):')
        # self.spinbox_fps = QLineEdit()
        self.spinbox_fps = QDoubleSpinBox()
        # self.spinbox_fps.setValidator(QDoubleValidator())
        # self.spinbox_fps.setFixedHeight(18)
        self.spinbox_fps.setFixedSize(QSize(50, 18))
        self.spinbox_fps.setMinimum(.1)
        self.spinbox_fps.setMaximum(20)
        self.spinbox_fps.setSingleStep(.2)
        self.spinbox_fps.setDecimals(1)
        self.spinbox_fps.setSuffix('fps')
        # self.spinbox_fps.setStatusTip('Playback Speed (frames/second)')
        self.spinbox_fps.setToolTip('Scroll Speed (frames/second)')
        self.spinbox_fps.clear()

        """scale combobox"""
        self._changeScaleCombo = QComboBox(self)
        self._changeScaleCombo.setFixedSize(QSize(148, 16))
        self._changeScaleCombo.setStyleSheet('font-size: 10px;')
        self._changeScaleCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._changeScaleCombo.currentTextChanged.connect(self.fn_scales_combobox)
        # hbl.addWidget(self._changeScaleCombo, alignment=Qt.AlignmentFlag.AlignRight)

        # self.navControls = QWidget()
        self.fl_nav = QFormLayout()
        self.fl_nav.setVerticalSpacing(2)
        self.fl_nav.setHorizontalSpacing(2)
        self.fl_nav.setContentsMargins(2, 0, 2, 0)
        # self.fl_nav.addRow('Scale: ', HWidget(self._changeScaleCombo, self._scaleSetWidget, ExpandingWidget(self)))
        # self.fl_nav.addRow('Section:', HWidget(self._jumpToLineedit, self._sectionSliderWidget, self.spinbox_fps))
        # # self.fl_nav.addRow('Include:', HWidget(self._skipCheckbox, self._sectionChangeWidget))
        # self.fl_nav.addRow('', HWidget(self._sectionChangeWidget, self._skipCheckbox, self._sectionChangeWidget))

        self.fl_nav.addRow('Scale: ', HWidget(self._changeScaleCombo, ExpandingHWidget(self), self._scaleSetWidget))
        self.resLab = QLabel('Level / Downsampled Image Resolution')
        self.resLab.setStyleSheet('font-size: 8px; font-weight: 600;')
        self.fl_nav.addRow('', HWidget(self.resLab, ExpandingHWidget(self)))
        self.fl_nav.addRow('Section:', HWidget(self._jumpToLineedit, self._sectionSliderWidget, self.spinbox_fps))
        # self.fl_nav.addRow('', HWidget(self.spinbox_fps, self._sectionSliderWidget, self._sectionChangeWidget))
        self.fl_nav.addRow('', HWidget(self._w_skipCheckbox, ExpandingHWidget(self), self._sectionChangeWidget))
        # self.fl_nav.addRow('Include:', HWidget(self._skipCheckbox, self._sectionChangeWidget))
        # self.fl_nav.addRow('', HWidget(self._sectionChangeWidget, self._skipCheckbox))

        self.navControls = QGroupBox()
        self.navControls.setContentsMargins(0, 0, 0, 0)
        self.navControls.setObjectName('gb_cpanel')
        self.navControls.setLayout(self.fl_nav)

        tip = """Align and generate all sections for the current scale"""
        self._btn_alignAll = QPushButton(f"Align All {hotkey('A')}")
        # self._btn_alignAll.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 600;}")
        self._btn_alignAll.setEnabled(False)
        self._btn_alignAll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignAll.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignAll.clicked.connect(self.alignAll)
        self._btn_alignAll.setFixedSize(long_button_size)

        tip = """Align and generate the current section only"""
        self._btn_alignOne = QPushButton('Align One')
        # self._btn_alignOne.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 600;}")
        self._btn_alignOne.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignOne.setEnabled(False)
        self._btn_alignOne.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignOne.clicked.connect(self.alignOne)
        self._btn_alignOne.setFixedSize(long_button_size)


        tip = """Align and generate current sections from the current through the end of the image stack"""
        self._btn_alignForward = QPushButton('Align Forward')
        self._btn_alignOne.setStyleSheet("font-size: 9px;")
        self._btn_alignForward.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignForward.setEnabled(False)
        self._btn_alignForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignForward.clicked.connect(self.alignForward)
        self._btn_alignForward.setFixedSize(long_button_size)

        tip = """The range of sections to align for the align range button"""
        self.sectionRangeSlider = RangeSlider()
        self.sectionRangeSlider.setMinimumWidth(100)
        self.sectionRangeSlider.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.sectionRangeSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sectionRangeSlider.setMinimumWidth(40)
        self.sectionRangeSlider.setMaximumWidth(150)
        self.sectionRangeSlider.setFixedHeight(16)
        self.sectionRangeSlider.setMin(0)
        self.sectionRangeSlider.setStart(0)

        self.startRangeInput = QLineEdit()
        self.startRangeInput.setAlignment(Qt.AlignCenter)
        self.startRangeInput.setFixedSize(30, 16)
        self.startRangeInput.setEnabled(False)

        self.endRangeInput = QLineEdit()
        # self.endRangeInput.setStyleSheet("background-color: #f3f6fb;")
        self.endRangeInput.setAlignment(Qt.AlignCenter)
        self.endRangeInput.setFixedSize(30, 16)
        self.endRangeInput.setEnabled(False)

        tip = """The range of sections to align."""
        self.rangeInputWidget = HWidget(self.startRangeInput, QLabel(':'), self.endRangeInput)
        self.rangeInputWidget.setMaximumWidth(140)
        self.rangeInputWidget.setToolTip(tip)

        def updateRangeButton():
            a = self.sectionRangeSlider.start()
            b = self.sectionRangeSlider.end()
            # self._btn_alignRange.setText("Re-Align Sections #%d to #%d" % (a,b))
            self._btn_alignRange.setText("Re-Align #%d to #%d" % (a, b))

        self.sectionRangeSlider.startValueChanged.connect(lambda val: self.startRangeInput.setText(str(val)))
        self.sectionRangeSlider.startValueChanged.connect(updateRangeButton)
        self.sectionRangeSlider.endValueChanged.connect(lambda val: self.endRangeInput.setText(str(val)))
        self.sectionRangeSlider.endValueChanged.connect(updateRangeButton)
        self.startRangeInput.textChanged.connect(lambda val: self.sectionRangeSlider.setStart(int(val)))
        self.endRangeInput.textChanged.connect(lambda val: self.sectionRangeSlider.setEnd(int(val)))

        tip = """Align and generate the selected range of sections"""
        self._btn_alignRange = QPushButton('Realign Range')
        # self._btn_alignRange.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 600;}")
        self._btn_alignRange.setEnabled(False)
        # self._btn_alignRange.setStyleSheet("font-size: 10px; color: #161c20;")
        self._btn_alignRange.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignRange.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_alignRange.clicked.connect(self.alignRange)
        self._btn_alignRange.setFixedSize(long_button_size)

        tip = 'Enter Manual Align Mode'
        # self._btn_manualAlign = QPushButton('Manual Align Mode →')
        self._btn_manualAlign = QPushButton(f"Manual Align {hotkey('M')} ")
        self._btn_manualAlign.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_manualAlign.setIconSize(QSize(12, 12))
        # self._btn_manualAlign.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 600;}")
        self._btn_manualAlign.setStyleSheet("""""")
        self._btn_manualAlign.setLayoutDirection(Qt.RightToLeft)
        self._btn_manualAlign.setIcon(qta.icon('fa.arrow-right', color='#161c20'))
        self._btn_manualAlign.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_manualAlign.clicked.connect(self.enterExitManAlignMode)
        self._btn_manualAlign.setFixedSize(long_button_size)

        tip = """Whether to auto-generate aligned images following alignment."""
        self._toggleAutogenerate = ToggleSwitch()
        self._toggleAutogenerate.stateChanged.connect(self._toggledAutogenerate)
        self._toggleAutogenerate.stateChanged.connect(self._callbk_unsavedChanges)
        self._toggleAutogenerate.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._toggleAutogenerate.setChecked(True)
        self._toggleAutogenerate.setEnabled(False)

        tip = 'Polynomial bias correction (defaults to None), alters the generated images including their width and height.'
        self._polyBiasCombo = QComboBox(self)
        # self._polyBiasCombo.setStyleSheet("font-size: 10px; padding-left: 6px;")
        self._polyBiasCombo.currentIndexChanged.connect(self._valueChangedPolyOrder)
        self._polyBiasCombo.currentIndexChanged.connect(self._callbk_unsavedChanges)
        self._polyBiasCombo.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._polyBiasCombo.addItems(['None', 'poly 0°', 'poly 1°', 'poly 2°', 'poly 3°', 'poly 4°'])
        self._polyBiasCombo.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self._polyBiasCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._polyBiasCombo.setFixedSize(QSize(70, 16))
        self._polyBiasCombo.setEnabled(False)
        self._polyBiasCombo.lineEdit()

        tip = """Bounding box is only applied upon "Align All" and "Regenerate". Caution: Turning this ON may 
        significantly increase the size of generated images."""
        self._bbToggle = ToggleSwitch()
        self._bbToggle.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._bbToggle.toggled.connect(self._callbk_bnding_box)
        self._bbToggle.setEnabled(False)

        tip = """Regenerate output based on the current Corrective Bias and Bounding Box presets."""
        self._btn_regenerate = QPushButton('Regenerate All Output')
        # self._btn_regenerate.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 600;}")
        self._btn_regenerate.setEnabled(False)
        self._btn_regenerate.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._btn_regenerate.clicked.connect(lambda: self.regenerate(scale=cfg.data.scale))
        self._btn_regenerate.setFixedSize(long_button_size)
        self._btn_regenerate.setEnabled(False)

        '''_wdg_alignButtons'''

        # hbl.addWidget(self._ctlpanel_applyAllButton)

        # self._btn_regenerate.setAutoFillBackground(True)
        # self._btn_alignOne.setAutoFillBackground(True)
        # # self.sectionRangeSlider.setAutoFillBackground(True)
        # self.rangeInputWidget.setAutoFillBackground(True)
        # self._btn_alignRange.setAutoFillBackground(True)
        # self._btn_alignAll.setAutoFillBackground(True)
        self.fl_cpButtonsLeft = QFormLayout()
        # self.fl_cpButtonsLeft.setFormAlignment(Qt.AlignJustify)
        self.fl_cpButtonsLeft.setVerticalSpacing(2)
        self.fl_cpButtonsLeft.setContentsMargins(2, 2, 2, 2)
        self.fl_cpButtonsLeft.addWidget(self._btn_alignAll)
        # self.fl_cpButtonsLeft.addWidget(self._btn_alignOne)
        self.fl_cpButtonsLeft.addWidget(self._btn_alignForward)
        self.fl_cpButtonsLeft.addWidget(HWidget(self._btn_manualAlign))
        self.cpButtonsLeft = QWidget()
        self.cpButtonsLeft.setAutoFillBackground(True)
        self.cpButtonsLeft.setLayout(self.fl_cpButtonsLeft)

        self.cpButtonsRight = QWidget()
        fl = QFormLayout()
        # fl.setFormAlignment(Qt.AlignJustify)
        fl.setVerticalSpacing(2)
        # fl.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        fl.setContentsMargins(2, 2, 2, 2)
        # range_widget = HWidget(QLabel('Range:'), ExpandingWidget(self), self.rangeInputWidget, ExpandingWidget(self))
        range_widget = HWidget(QLabel('Range:'), self.rangeInputWidget, ExpandingWidget(self))
        # range_widget = HWidget(QLabel('Range:'), self.rangeInputWidget)
        range_widget.setMaximumWidth(400)
        fl.addWidget(range_widget)
        # fl.addWidget(self.sectionRangeSlider)
        fl.addWidget(HWidget(self._btn_alignRange))
        fl.addWidget(self._btn_regenerate)
        self.cpButtonsRight.setLayout(fl)

        self.gb_ctlActions = QGroupBox("Scale Actions")
        # self.gb_ctlActions.setContentsMargins(2,2,2,2)
        self.gb_ctlActions.setObjectName("gb_cpanel")
        # self.gb_ctlActions.setFixedWidth(500)
        # vw_l = VWidget(ExpandingWidget(self), self.cpButtonsLeft)
        # vw_r = VWidget(ExpandingWidget(self), self.cpButtonsRight)
        # self.gb_ctlActions_layout = HBL(vw_l, vw_r)

        self.gb_ctlActions_layout = HBL()
        self.gb_ctlActions_layout.setSpacing(2)
        self.gb_ctlActions_layout.addWidget(self.cpButtonsLeft, alignment=Qt.AlignCenter)
        self.gb_ctlActions_layout.addWidget(self.cpButtonsRight, alignment=Qt.AlignCenter)
        self.gb_ctlActions.setLayout(self.gb_ctlActions_layout)

        style = """
            QWidget{
                /*background-color: #222222;*/
                color: #f3f6fb;
                margin:0px;
                padding:0px;
            }

            QPushButton {
                background-color: #f3f6fb;
                font-size: 9px;
                border-radius: 2px;
                border-color: #161c20;
                border-width: 1px;
            }
            QPushButton:enabled {
                font-weight: 500;
                border-width: 1px;
                border-color: #161c20;
            }
            QPushButton:enabled:hover {
                border-color: #339933;
            }
            QPushButton:disabled {
                color: #f3f6fb;
                background-color: #dadada;
                font-weight: 200;
                border-color: #555555;
                border-width: 0px;
            }
            QLabel {
                font-size: 10px;
                color: #161c20;
                /*font-weight: 600;*/
            }
            QDoubleSpinBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 10px;
                border-radius: 2px;
                height:19px;
                margin:0px;
                padding:0px;
            }
            QSpinBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 10px;
                border-radius: 2px;
                height:19px;
                margin:0px;
                padding:0px;
            }
            QLineEdit {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 10px;
                border-radius: 2px;
                margin:0px;
                padding:0px;
            }
            QLineEdit:disabled {
                color: #f3f6fb;
                background-color: #dadada;
                font-weight: 200;
                border-color: #555555;
                border-width: 0px;
            }
            QComboBox {
                background-color: #f3f6fb;
                color: #161c20;
                font-size: 10px;
                height:19px;
                                margin:0px;
                padding:0px;
            }

            QComboBox QAbstractItemView 
            {
                min-width: 50px;
                height:19px;
                margin:0px;
                padding:0px;
            }

            QAbstractItemView {
                background-color: #f3f6fb;
                color: #161c20;
                font-size: 10px;
            }


            QGroupBox#gb_cpanel {
                color: #161c20;
                border: 1px solid #ede9e8;
                font-size: 9px;
                font-weight:600;
                border-radius: 2px;
                padding-top: 0px;
                margin: 2px;
            }

            QGroupBox:title#gb_cpanel {
                color: #161c20;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                margin-left: 2px;
                margin-right: 2px;
            }



            /*
            QGroupBox:disabled#gb_cpanel {
                background-color: #ffe135;
            }
            QGroupBox::title#gb_cpanel {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                color: #222222;
                background-color: #ede9e8;
                border: 1px solid #ede9e8;
                border-top-left-radius: 4px;
                border-bottom-right-radius: 2px;
                padding: 1px;
                border-width: 0px;
            }
            */
        """

        self.flSettings = QFormLayout()
        # self.flSettings.setFormAlignment(Qt.AlignCenter)
        self.flSettings.setFormAlignment(Qt.AlignVCenter)
        # self.flSettings.setContentsMargins(6,14,2,2)
        self.flSettings.setContentsMargins(2, 2, 2, 2)
        self.flSettings.setVerticalSpacing(2)
        self.flSettings.setHorizontalSpacing(0)
        # self.flSettings.setContentsMargins(8,10,2,2)
        # self.flSettings.addRow('Generate TIFFs: ', self._toggleAutogenerate))
        self.flSettings.addRow('Generate TIFFs: ', HWidget(ExpandingWidget(self), self._toggleAutogenerate))
        # self.flSettings.addRow('Bounding Box: ', self._bbToggle)
        self.flSettings.addRow('Bounding Box: ', HWidget(ExpandingWidget(self), self._bbToggle))
        self.flSettings.addRow('Corrective Bias: ', HWidget(ExpandingWidget(self), self._polyBiasCombo))
        # self.flSettings.setAlignment(Qt.AlignBaseline)
        # self.flSettings.setAlignment(Qt.AlignBottom)

        self.outputSettings = QGroupBox("Output Settings")
        self.outputSettings.setObjectName('gb_cpanel')
        self.outputSettings.setLayout(self.flSettings)
        self.fl_swimSettings = QFormLayout()
        self.fl_swimSettings.setContentsMargins(2, 2, 2, 2)
        self.fl_swimSettings.setFormAlignment(Qt.AlignVCenter)
        self.fl_swimSettings.setVerticalSpacing(4)
        self.fl_swimSettings.addRow('Window Width (px):', self._swimWindowControl)
        self.fl_swimSettings.addRow('Signal Whitening:', self.sb_whiteningControl)
        self.fl_swimSettings.addRow('Iterations:', self.sb_SWIMiterations)

        self.swimSettings = QGroupBox("Default SWIM Settings")
        # self.swimSettings.setStyleSheet('font-size: 10px;')
        self.swimSettings.setObjectName('gb_cpanel')
        self.swimSettings.setLayout(self.fl_swimSettings)
        self.swimSettings.setAlignment(Qt.AlignCenter)

        self.fl_results = QFormLayout()
        # self.fl_results.setFormAlignment(Qt.AlignCenter)
        self.fl_results.setVerticalSpacing(2)
        # self.fl_results.setHorizontalSpacing(8)
        self.fl_results.setContentsMargins(0, 0, 0, 0)

        self.results0 = QLabel()  # Image dimensions
        self.results1 = QLabel()  # # of images
        self.results2 = QLabel()  # SNR average
        self.results3 = QWidget()
        self.results3_fl = QFormLayout()
        self.results3_fl.setContentsMargins(0, 0, 0, 0)
        self.results3_fl.setVerticalSpacing(2)
        self.results3.setLayout(self.results3_fl)
        self.fl_results.addRow('Image Dimensions', self.results0)
        self.fl_results.addRow('# Images', self.results1)
        self.fl_results.addRow('SNR (average)', self.results2)
        # self.fl_results.addRow('Lowest 5 SNR', self.results3)
        # self.fl_results.addRow('Another item', self.results4)
        # self.fl_results.addRow('Another item', self.results5)
        # self.fl_results.addRow('Another item', self.results6)
        # self.fl_results.addRow('Another item', self.results7)
        # self.fl_results.setAlignment(Qt.AlignBaseline)

        results_style = """
        QFormLayout{
                font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
                font-size: 9px;
                color: #f3f6fb;
                margin: 5px;
                padding: 5px;
                border-radius: 2px;
        }
        """
        tab_width = 360
        self.sa_tab1 = QScrollArea()
        # self.sa_tab1.setStyleSheet('background-color: #f3f6fb;')
        # self.sa_tab1.setMinimumHeight(60)
        # self.sa_tab1.setFixedWidth(tab_width)
        self.sa_tab1.setWidgetResizable(True)
        self.sa_tab1.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab1.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.resultsWidget = QWidget()
        # self.resultsWidget.setStyleSheet("font-size: 10px;")
        # self.resultsWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.resultsWidget.setLayout(self.fl_results)
        # self.sa_tab1.setWidget(self.resultsWidget)
        # self.sa_tab1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.secDetails_w = QWidget()
        # self.secDetails_w.setFixedWidth(tab_width-10)
        self.secDetails_w.setStyleSheet("""
            color: #161c20;
            font-size: 9px;
            font-weight: 600;
        """)
        self.secDetails_w.setContentsMargins(0, 0, 0, 0)
        self.secDetails_fl = QFormLayout()
        self.secDetails_fl.setVerticalSpacing(2)
        self.secDetails_fl.setHorizontalSpacing(4)
        self.secDetails_fl.setContentsMargins(0, 0, 0, 0)

        # self.secDetails = [
        #     ('Name', QLabel()),
        #     ('Reference', QLabel()),
        #     ('Excluded Sections', QLabel()),
        #     ('Has Bounding Box', QLabel()),
        #     ('Use Bounding Box', QLabel())
        # ]

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

        # make_affine_widget_HTML(cfg.data.afm(), cfg.data.cafm())

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
            'Defaults': self.secDefaults,
        })
        # self.secDetails['Excluded Sections'].setWordWrap(True)

        for i in range(len(self.secDetails)):
            self.secDetails_fl.addRow(list(self.secDetails.items())[i][0], list(self.secDetails.items())[i][1])

        self.secDetails_w.setLayout(self.secDetails_fl)
        self.sa_tab1.setWidget(self.secDetails_w)

        self._bbToggle.stateChanged.connect(self.updateCpanelDetails_i1)

        # See: updateCpanelDetails
        # See: updateCpanelDetails_i1

        self.sa_tab1.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab1.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.sa_tab2 = QScrollArea()
        # self.sa_tab2.setStyleSheet("""
        #     border: none;
        # """)
        # self.sa_tab2.setMinimumHeight(60)
        # self.sa_tab2.setMinimumWidth(220)
        self.sa_tab2.setWidgetResizable(True)
        self.sa_tab2.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab2.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.runtimeWidget = QWidget()
        self.runtimeWidget.setStyleSheet("""
                font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
                font-size: 9px;
                color: #161c20;
        """)
        # self.runtimeWidget.setReadOnly(True)
        self.sa_tab3 = QScrollArea()
        self.sa_tab3.setWidgetResizable(True)
        self.sa_tab3.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab3.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab3.setWidget(self.runtimeWidget)

        self.secAffine = QLabel()
        self.secAffine.setStyleSheet("""
        QWidget{
            color: #161c20;
            font-weight: 600;
            border: none;
            }
        """)

        self.sa_tab4 = QScrollArea()
        self.sa_tab4.setStyleSheet("""
        QLabel {font-weight: 300;}
        """)
        self.sa_tab4.setWidgetResizable(True)
        self.sa_tab4.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab4.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa_tab4.setWidget(self.secAffine)

        self.cpanelTabWidget = QTabWidget()
        self.cpanelTabWidget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cpanelTabWidget.setFixedWidth(tab_width)
        self.cpanelTabWidget.currentChanged.connect(self.updateCpanelDetails)

        self.cpanelTabWidget.setStyleSheet("""


        QScrollArea {border: none; font-size: 8px;}

        QTabWidget{
            font-size: 8px;
        }

        QTabBar::tab {
            height: 14px;
            width: 64px;
            padding-left: 0px;
            padding-right: 0px;
            font-size: 8px;
        }

        QTabBar::tab:selected
        {
            color: #339933;
            font-weight: 600;
        }

        """)

        # self.cpanelTabWidget.setStyleSheet("""
        #
        # QWidget{
        #     font-size: 10px;
        #     color: #161c20;
        #     background-color: #f3f6fb;
        #     border-width: 0px;
        #     border-color: #161c20;
        # }
        #
        # QScrollArea{
        #     color: #161c20;
        #     font-size: 8px;
        #     padding: 2px;
        #     border-width: 0px;
        #     border-style: solid;
        #     border-color: #161c20;
        # }
        #
        # QLabel {
        #     font-size: 10px;
        # }
        # QTabWidget{
        #     padding: 0px;
        #     border-width: 0px;
        #     border-radius: 2px;
        #     font-size: 9px;
        #
        # }
        #
        # QTabBar::tab {
        #     margin 0px;
        #     height: 14px;
        #     max-width: 100px;
        #     font-size: 8px;
        # }
        #
        # QTabBar::tab:selected
        # {
        #     color: #339933;
        #     font-weight: 600;
        # }
        # """)
        self.cpanelTabWidget.setContentsMargins(0, 0, 0, 0)
        self.cpanelTabWidget.setFixedHeight(80)
        self.cpanelTabWidget.addTab(self.sa_tab1, 'Details')
        self.cpanelTabWidget.addTab(self.sa_tab2, 'Lowest 8 SNR')
        self.cpanelTabWidget.addTab(self.sa_tab3, 'Runtimes')
        self.cpanelTabWidget.addTab(self.sa_tab4, 'Affine')
        # self.cpanelTabWidget.addTab(self.sa_tab4, 'Affine')

        # self.alignmentResults = QGroupBox("Data && Results")
        # # self.alignmentResults.setContentsMargins(2,12,0,0)
        # self.alignmentResults.setContentsMargins(2,2,2,2)
        # # self.alignmentResults.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # # self.alignmentResults.setFixedWidth(284)
        # self.alignmentResults.setObjectName('gb_cpanel')
        # self.alignmentResults.setLayout(HBL(self.sa_tab1))
        # # self.alignmentResults.setStyleSheet(style)
        # # self.alignmentResults.setStyleSheet(results_style)

        '''self._wdg_alignBut
        tons <- self.cpButtonsLeft <- self.cpanel_hwidget1'''
        self.cpanel = QWidget()
        hbl = HBL()
        # hbl.setSpacing(1)
        # hbl.setSpacing(8)

        # hbl.addWidget(QLabel('  '))
        # hbl.addWidget(ExpandingWidget(self))
        hbl.addWidget(ExpandingWidget(self))
        hbl.addWidget(self.navControls)
        hbl.addStretch(1)
        hbl.addWidget(self.swimSettings)
        hbl.addStretch(1)
        hbl.addWidget(self.gb_ctlActions)
        hbl.addStretch(1)
        hbl.addWidget(self.outputSettings)
        hbl.addStretch(1)
        # hbl.addWidget(self.alignmentResults)
        # hbl.addWidget(self.sa_tab1)
        hbl.addWidget(self.cpanelTabWidget)
        # hbl.addStretch(1)
        hbl.addWidget(ExpandingWidget(self))

        self.cpanel.setLayout(hbl)
        self.cpanel.setContentsMargins(2, 2, 2, 2)
        self.cpanel.setFixedHeight(92)
        # self.cpanel.layout.setAlignment(Qt.AlignHCenter)s
        self.cpanel.setAutoFillBackground(True)
        # p = self.cpanel.palette()
        # p.setColor(self.cpanel.backgroundRole(), QColor('#222222'))
        # self.cpanel.setPalette(p)
        # self.cpanel.setStyleSheet("""QWidget {
        #                           background-color: #222222;
        #                           color: #ede9e8;
        #                           }""")
        # self.cpanel.setStyleSheet("""
        # QWidget {
        #     background-color: #222222;
        #     color: #ede9e8;
        #     font-size: 10px;
        # }""")

        cpanel_style2 = """
        QLabel {font-size: 10px;}

        QPushButton {
            font-size: 10px;
        }


        QComboBox {
            background-color: #f3f6fb;
            color: #161c20;
            font-size: 10px;
            margin:0px;
            padding:0px;
        }

        QGroupBox#gb_cpanel {
                color: #161c20;
                border: 1px solid #161c20;
                font-size: 10px;
                /*font-weight: 600;*/
                border-radius: 2px;
                margin: 2px;
                padding: 2px;

        }

        QGroupBox:title#gb_cpanel {
            color: #161c20;
            /*font-weight:600;*/
            font-size: 9px;
            subcontrol-origin: margin;
            subcontrol-position: top center;
            margin-bottom: 16px;

        }
        """

        # self.cpanel.setStyleSheet(style)
        self.cpanel.setStyleSheet(cpanel_style2)

    def initUI(self):
        '''Initialize Main UI'''
        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)

        with open('src/style/controls.qss', 'r') as f:
            lower_controls_style = f.read()

        '''Headup Display'''
        # self.hud = HeadupDisplay(self.app)
        self.hud = HeadupDisplay(self.app)
        self.hud.set_theme_dark()
        # self.hud.set_theme_overlay()
        # self.hud.setObjectName('HUD')
        # self.hud.set_theme_default()
        # self.dw_monitor = QDockWidget('Head-up Display (Process Monitor)', self)
        # self.dw_monitor = QDockWidget('Head-up Display (Process Monitor)', self)
        self.dw_monitor = DockWidget('HUD', self)
        self.dw_monitor.visibilityChanged.connect(self.callbackDwVisibilityChanged)
        self.dw_monitor.setFeatures(self.dw_monitor.DockWidgetClosable | self.dw_monitor.DockWidgetVerticalTitleBar)
        self.dw_monitor.setFeatures(self.dw_monitor.DockWidgetVerticalTitleBar)
        self.dw_monitor.setObjectName('Dock Widget HUD')
        self.dw_monitor.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #161c20;
                    color: #ede9e8;
                    font-weight: 600;
                    text-align: left;
                }""")
        self.dw_monitor.setWidget(self.hud)
        self.dw_monitor.hide()
        # self.dw_monitor.setLayout(HBL(self.hud))
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_monitor)

        # self.hud.resize(QSize(400,120))
        # self.hud.setMinimumWidth(256)
        # self.hud.setMinimumHeight(100)
        # self.hud.setMinimumWidth(180)
        # path = 'src/resources/KeyboardCommands1.html'
        # with open(path) as f:
        #     contents = f.read()
        # self.hud.textedit.appendHtml(contents)
        self.user = getpass.getuser()
        self.tell(f'Hello User, please report any issues or bugs to joel@salk.edu.')

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

        # self._btn_refresh = QPushButton('Refresh')
        # self._btn_refresh.clicked.connect(cfg.emViewer.ini)

        # self.initControlPanel()

        '''
                    self.layer_details.setText(f"{name}{skip}"
                                                 f"{bb_dims}"
                                                 f"{snr}"
                                                 f"{completed}"
                                                 f"<b>Skipped Layers:</b> [{skips}]<br>"
                                                 f"<b>Match Point Layers:</b> [{matchpoints}]"
        '''

        self._layer_details = (
            QLabel('Name :'),
            QLabel('Bounds :'),
            QLabel('SNR :'),
            QLabel('Progress :'),
            QLabel('Excluded Layer :'),
            QLabel('Matchpoints :'),
        )
        self._tool_textInfo_NEW = WidgetArea(parent=self, title='Details', labels=self._layer_details)

        lab = QLabel('Details')
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        self.layer_details = QTextEdit()
        self.layer_details.setObjectName('layer_details')
        self.layer_details.setReadOnly(True)
        self._tool_textInfo = QWidget()
        vbl = VBL()
        vbl.setSpacing(1)
        # vbl.addWidget(lab, alignment=baseline)
        # vbl.addWidget(self.layer_details)
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
        self.splashlabel.setMinimumSize(QSize(100, 100))
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

        # self.dw_notes = DockWidget('Notes', self)
        self.dw_notes = DockWidget('Notes', self)
        # self.dw_notes.visibilityChanged.connect(
        #     lambda: self.cbNotes.setText((' Hide', ' Notes')[self.dw_notes.isHidden()]))
        # self.dw_notes.visibilityChanged.connect(lambda: )
        self.dw_notes.visibilityChanged.connect(lambda: self.cbNotes.setToolTip(
            ('Hide Notes Tool Window', 'Show Notes Tool Window')[self.dw_notes.isHidden()]))
        # self.dw_notes.visibilityChanged.connect(self.dataUpdateResults()) #???
        self.dw_notes.visibilityChanged.connect(self.callbackDwVisibilityChanged)

        self.dw_notes.setStyleSheet("""
        QDockWidget {color: #161c20;}

        QDockWidget::title {
            background-color: #FFE873;
            font-weight: 600;
            text-align: left;
        }""")
        self.dw_notes.setWidget(self.notes)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dw_notes)
        self.dw_notes.hide()

        tip = 'Show/Hide Contrast and Brightness Shaders'
        self._btn_show_hide_shader = QPushButton(' Shader')
        self._btn_show_hide_shader.setFixedHeight(18)
        self._btn_show_hide_shader.setStyleSheet(lower_controls_style)
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
        self.globTabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.globTabs.setStyleSheet("""background-color: #ede9e8""")
        # self.globTabs.setContentsMargins(4,4,4,4)
        self.globTabs.setContentsMargins(0, 0, 0, 0)
        # self.globTabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.globTabs.tabBar().setStyleSheet("""
        # QTabBar::tab {
        #     min-width: 100px;
        #     max-width: 260px;
        #     height: 16px;
        #     padding-left:0px;
        #     padding-right:0px;
        #     padding: 1px;
        #     font-size: 11px;
        # }
        # QTabBar::tab:selected
        # {
        #     font-weight: 600;
        # }
        # """)

        self.globTabs.setStyleSheet("""
                 QTabBar::close-button {
                     image: url(src/resources/close-tab.png)
                 }
                
                QTabBar::tab {
                    height: 13px;
                    min-width: 100px;
                    max-width: 240px;
                    font-size: 9px;
                    font-weight: 600;
                    border-top-left-radius: 1px;
                    border-bottom-right-radius: 1px;
                    border-bottom-left-radius: 8px;
                    border-top-right-radius: 8px;
                    border: 1px solid #ede9e8;
                    background-color: #b3e6b3;

                }
                QTabBar::tab:selected
                {   
                    font-weight: 600;
                    color: #f3f6fb;
                    background-color: #339933;
                }
                """)

        # self.globTabs.setTabShape(QTabWidget.TabShape.Triangular)

        # self.globTabs.setTabBarAutoHide(True)
        self.globTabs.tabBar().setElideMode(Qt.ElideMiddle)
        self.globTabs.setElideMode(Qt.ElideMiddle)
        self.globTabs.setMovable(True)
        self.globTabs.hide()

        self.globTabs.setDocumentMode(True)
        self.globTabs.setTabsClosable(True)
        self.globTabs.setObjectName('globTabs')
        self.globTabs.tabCloseRequested[int].connect(self._onGlobTabClose)
        self.globTabs.currentChanged.connect(self._onGlobTabChange)

        self.pythonConsole = PythonConsole()
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
        self.dw_python.setFeatures(self.dw_python.DockWidgetClosable | self.dw_python.DockWidgetVerticalTitleBar)
        # self.dw_python.visibilityChanged.connect(lambda: self.cbPython.setToolTip(('Hide Python Console Tool Window', 'Show Python Console Tool Window')[self.dw_python.isHidden()]))
        self.dw_python.setStyleSheet("""QDockWidget::title {
            text-align: left; /* align the text to the left */
            background: #4B8BBE;
            font-weight: 600;
        }""")
        self.dw_python.setWidget(self.pythonConsole)
        # def fn():
        #     width = int(cfg.main_window.width() / 2)
        #     self.pythonConsole.resize(QSize(width, 90))
        #     self.pythonConsole.update()
        # self.dw_python.visibilityChanged.connect(fn)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_python)
        self.dw_python.hide()



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

        self.tb = HWidget(self.navWidget, self.toolbar)
        self.tb.setFixedHeight(18)

        self.sa_cpanel = QScrollArea()
        self.sa_cpanel.setContentsMargins(0, 0, 0, 0)
        self.sa_cpanel.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # self.sa_cpanel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sa_cpanel.setStyleSheet("""
        /* ---- QScrollBar  ---- */
        QScrollBar:vertical {
            border: none;
            width: 6px;
        }
        QScrollBar:horizontal {
            border: none;
            height: 6px;
        }
        """)
        self.sa_cpanel.setFixedHeight(104)
        self.sa_cpanel.setWidget(self.cpanel)

        self.tb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.globTabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sa_cpanel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pbar_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.globTabsAndCpanel = VWidget(self.tb, self.globTabs, self.sa_cpanel, self.pbar_widget)
        self.globTabsAndCpanel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.globTabsAndCpanel.layout.setSpacing(0)
        # self.globTabsAndCpanel.setAutoFillBackground(True)
        # self.globTabsAndCpanel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.globTabsAndCpanel.show()

        # self.setMenuWidget(self.menu)
        # self.globTabsAndCpanel.setStyleSheet("""background-color: #f3f6fb;""")
        self.setCentralWidget(self.globTabsAndCpanel)

        # self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks)
        self.setDockOptions(QMainWindow.AnimatedDocks)



    def setControlPanelData(self):

        self._swimWindowControl.setText(str(getData(f'data,defaults,{cfg.data.scale},swim-window-px')[0]))
        self.sb_whiteningControl.setValue(float(getData('data,defaults,signal-whitening')))
        self.sb_SWIMiterations.setValue(int(getData('data,defaults,swim-iterations')))

        poly = getData('data,defaults,corrective-polynomial')
        if (poly == None) or (poly == 'None'):
            self._polyBiasCombo.setCurrentText('None')
        else:
            self._polyBiasCombo.setCurrentText(str(poly))

        self._bbToggle.setChecked(bool(getData(f'data,defaults,bounding-box')))

    # def updateAllCpanelDetails(self):
    #     '''
    #     _onGlobTabChange  (1 usage found)
    #         3392 self.updateAllCpanelDetails()
    #     onAlignmentEnd  (1 usage found)
    #         876 self.updateAllCpanelDetails()
    #     onStartProject  (1 usage found)
    #         2155 self.updateAllCpanelDetails()
    #     refreshTab  (1 usage found)
    #         235 self.updateAllCpanelDetails()
    #     regenerate  (1 usage found)
    #         646 self.updateAllCpanelDetails()
    #     '''
    #     self.updateCpanelDetails_i1()
    #     self.secAffine.setText(make_affine_widget_HTML(cfg.data.afm(), cfg.data.cafm()))
    #     self.updateLowest8widget()
    #
    #     try:    self._bbToggle.setChecked(cfg.data.use_bb())
    #     except: logger.warning('Bounding Box Toggle Failed to Update')

    def updateCpanelDetails(self):
        '''
        usages:
        cpanelTabWidget tab change
        '''
        # logger.info('')
        if self.cpanelTabWidget.currentIndex() == 0:
            self.updateCpanelDetails_i1()
        if self.cpanelTabWidget.currentIndex() == 1:
            self.updateLowest8widget()
        if self.cpanelTabWidget.currentIndex() == 2:
            self.updateDtWidget()
        #Cancel- tab 2 - runtimes are updated when runtimes change
        if self.cpanelTabWidget.currentIndex() == 3:
            self.secAffine.setText(make_affine_widget_HTML(cfg.data.afm(), cfg.data.cafm()))

    def updateCpanelDetails_i1(self):
        """
        _valueChangedWhitening  (1 usage found)
            4223 self.updateCpanelDetails_i1()
        fn_scales_combobox  (1 usage found)
            1948 self.updateCpanelDetails_i1()
        fn_swim_iters  (1 usage found)
            4374 self.updateCpanelDetails_i1()
        initControlPanel  (2 usages found)
            4337 self._skipCheckbox.stateChanged.connect(self.updateCpanelDetails_i1)
            5032 self._bbToggle.stateChanged.connect(self.updateCpanelDetails_i1)
        updateAllCpanelDetails  (1 usage found)
            5940 self.updateCpanelDetails_i1()
        updateCpanelDetails  (1 usage found)
            5954 self.updateCpanelDetails_i1()

        """


        logger.info('')
        if self._isProjectTab():
            caller = inspect.stack()[1].function
            # logger.critical(f'caller: {caller}')
            # if self.cpanelTabWidget.currentIndex() == 0:
            self.secName.setText(cfg.data.filename_basename())
            ref = cfg.data.reference_basename()
            if ref == '':
                ref = 'None'
            self.secReference.setText(ref)

            self.secAlignmentMethod.setText(cfg.data.method_pretty())
            # self.secSNR.setText(cfg.data.snr_report()[5:])
            # self.secSNR.setText('<span style="font-color: red;"><b>%.2f</b></span>' % cfg.data.snr())

            # self.secDetails[2][1].setText(str(cfg.data.skips_list()))
            skips = cfg.data.skips_list()
            if skips == []:
                self.secExcluded.setText('None')
            else:
                self.secExcluded.setText('\n'.join([f'z-index: {a}, name: {b}' for a, b in skips]))
            self.secHasBB.setText(str(cfg.data.has_bb()))
            self.secUseBB.setText(str(cfg.data.use_bb()))
            self.secSrcImageSize.setText('%dx%d pixels' % cfg.data.image_size())
            if cfg.data.is_aligned():
                self.secAlignedImageSize.setText('%dx%d pixels' % cfg.data.image_size_aligned())
                if cfg.data.zpos <= cfg.data.first_unskipped():
                    self.secSNR.setText('--')
                else:
                    try:
                        self.secSNR.setText(
                            '<span style="color: #a30000;"><b>%.2f</b></span><span>&nbsp;&nbsp;(%s)</span>' % (
                                cfg.data.snr(), ",  ".join(["%.2f" % x for x in cfg.data.snr_components()])))
                    except:
                        print_exception()
            else:
                self.secAlignedImageSize.setText('--')
                self.secSNR.setText('--')
            self.secDefaults.setText(cfg.data.defaults_pretty)


    def updateLowest8widget(self):

        if cfg.data.is_aligned():
            n_lowest = min(8, len(cfg.data) - 1)
            lowest_X_i = [x[0] for x in list(cfg.data.snr_lowest(n_lowest))]
            lowest_X = list(cfg.data.snr_lowest(n_lowest))
            logger.info(f'lowest_X_i : {lowest_X_i}')
            logger.info(f'lowest_X : {lowest_X}')
            logger.info(f'n_lowest : {n_lowest}')

            funcs = []
            for i in range(n_lowest):
                funcs.append(lambda: self.jump_to_manual(lowest_X_i[i]))

            self.lowestX_btns = []
            self.lowestX_txt = []

            for i in range(n_lowest):
                logger.info(f'i = {i}')

                try:
                    # logger.info(f'i = {i}, lowest_X_i[i] = {lowest_X_i[i]}')
                    s1 = ('z-index <u><b>%d</b></u>' % lowest_X[i][0]).ljust(15)
                    s2 = ("<span style='color: #a30000;'>%.2f</span>" % lowest_X[i][1]).ljust(15)
                    combined = s1 + ' ' + s2
                    # btn = QPushButton('Jump')
                    # self.lowestX_btns.append(QPushButton('Align Manually →'))
                    self.lowestX_btns.append(QPushButton('Manual Align'))
                    f = QFont()
                    f.setPointSizeF(7)
                    self.lowestX_btns[i].setFont(f)
                    self.lowestX_btns[i].setLayoutDirection(Qt.RightToLeft)
                    self.lowestX_btns[i].setFixedSize(QSize(80, 14))
                    self.lowestX_btns[i].setStyleSheet("font-size: 9px;")
                    self.lowestX_btns[i].setIconSize(QSize(10, 10))
                    self.lowestX_btns[i].setIcon(qta.icon('fa.arrow-right', color='#161c20'))
                    self.lowestX_btns[i].clicked.connect(funcs[i])
                    self.lowestX_txt.append(combined)

                # try:    self.results3.setText("\n".join(["z-index %d: %.2f" % (x[0], x[1]) for x in list(cfg.data.snr_lowest(5))]))
                except:
                    print_exception()
                # self.results3 = QLabel('...Worst 5 SNR')
        else:
            label = QLabel('Not Aligned.')
            label.setAlignment(Qt.AlignTop)
            self.sa_tab2.setWidget(label)
            return

        self.lowX_left_fl = QFormLayout()
        self.lowX_left_fl.setContentsMargins(0, 0, 0, 0)
        self.lowX_left_fl.setVerticalSpacing(1)
        if n_lowest >= 1:
            self.lowX_left_fl.addRow(self.lowestX_txt[0], self.lowestX_btns[0])
        if n_lowest >= 2:
            self.lowX_left_fl.addRow(self.lowestX_txt[1], self.lowestX_btns[1])
        if n_lowest >= 3:
            self.lowX_left_fl.addRow(self.lowestX_txt[2], self.lowestX_btns[2])
        if n_lowest >= 4:
            self.lowX_left_fl.addRow(self.lowestX_txt[3], self.lowestX_btns[3])
        # self.lowX_left_fl.addRow(self.lowestX_txt[4], self.lowestX_btns[4])
        self.lowX_left = QWidget()
        self.lowX_left.setContentsMargins(0, 0, 0, 0)
        self.lowX_left.setLayout(self.lowX_left_fl)

        self.lowX_right_fl = QFormLayout()
        self.lowX_right_fl.setContentsMargins(0, 0, 0, 0)
        self.lowX_right_fl.setVerticalSpacing(1)
        if n_lowest >= 5:
            self.lowX_right_fl.addRow(self.lowestX_txt[4], self.lowestX_btns[4])
        if n_lowest >= 6:
            self.lowX_right_fl.addRow(self.lowestX_txt[5], self.lowestX_btns[5])
        if n_lowest >= 7:
            self.lowX_right_fl.addRow(self.lowestX_txt[6], self.lowestX_btns[6])
        if n_lowest >= 8:
            self.lowX_right_fl.addRow(self.lowestX_txt[7], self.lowestX_btns[7])
        # self.lowX_right_fl.addRow(self.lowestX_txt[9], self.lowestX_btns[9])
        self.lowX_right = QWidget()
        self.lowX_right.setContentsMargins(0, 0, 0, 0)
        self.lowX_right.setLayout(self.lowX_right_fl)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 2, 2, 2)
        hbl.addWidget(self.lowX_left)
        hbl.addWidget(self.lowX_right)
        w = QWidget()
        w.setLayout(hbl)

        logger.critical('Setting sa_tab2 Layout...')
        # self.sa_tab2.setLayout(HBL(self.lowX_left, self.lowX_right))
        self.sa_tab2.setWidget(w)

    def initLaunchTab(self):
        self._launchScreen = OpenProject()
        self.globTabs.addTab(self._launchScreen, 'Open...')
        self.globTabs.tabBar().setTabButton(0, QTabBar.RightSide,None)
        self._setLastTab()

    def get_application_root(self):
        return Path(__file__).parents[2]

    def initWidgetSpacing(self):
        logger.info('')
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.layer_details.setContentsMargins(0, 0, 0, 0)
        self._tool_hstry.setMinimumWidth(248)
        # cfg.project_tab._transformationWidget.setFixedWidth(248)
        # cfg.project_tab._transformationWidget.setFixedSize(248,100)
        self.layer_details.setMinimumWidth(248)

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
        # self.pbar.setFixedHeight(16)
        # self.pbar.setFixedWidth(400)
        self.pbar_widget = QWidget(self)
        self.pbar_widget.setAutoFillBackground(True)
        self.status_bar_layout = QHBoxLayout()
        self.status_bar_layout.setContentsMargins(4, 0, 4, 0)
        self.status_bar_layout.setSpacing(4)
        self.pbar_cancel_button = QPushButton('Stop')
        self.pbar_cancel_button.setFixedSize(42, 16)
        self.pbar_cancel_button.setIconSize(QSize(14, 14))
        self.pbar_cancel_button.setToolTip('Terminate Pending Multiprocessing Tasks')
        self.pbar_cancel_button.setIcon(qta.icon('mdi.cancel', color=cfg.ICON_COLOR))
        self.pbar_cancel_button.setStyleSheet("""
        QPushButton{
            font-size: 9px;
            font-weight: 600;
        }""")
        self.pbar_cancel_button.clicked.connect(self.forceStopMultiprocessing)

        self.pbar_widget.setLayout(self.status_bar_layout)
        self.pbarLabel = QLabel('Task... ')
        self.pbarLabel.setStyleSheet("""
        font-size: 9px;
        font-weight: 600;""")
        self.status_bar_layout.addWidget(self.pbarLabel, alignment=Qt.AlignmentFlag.AlignRight)
        self.status_bar_layout.addWidget(self.pbar)
        self.status_bar_layout.addWidget(self.pbar_cancel_button)
        # self.statusBar.addPermanentWidget(self.pbar_widget)
        self.hidePbar()

    def forceStopMultiprocessing(self):
        cfg.CancelProcesses = True
        cfg.event.set()

    def setPbarMax(self, x):
        self.pbar.setMaximum(x)

    def updatePbar(self, x=None):
        caller = inspect.stack()[1].function
        # logger.critical(f"caller: {caller}")
        if x == None: x = cfg.nProcessDone
        self.pbar.setValue(x)
        try:
            if self._isProjectTab():
                if caller == "collect_results":
                    if "Transforms" in self.pbar.text():
                        if cfg.pt.ms_widget.isVisible():
                            # if (x == len(cfg.data)) or (x == len(cfg.data) - 1):
                            #     logger.critical(f"\n\nx = {x}\n")
                            #     # self.updateCorrSignalsDrawer(z=cfg.data.zpos)
                            #     cfg.pt.tn_ms0.set_no_image()
                            #     cfg.pt.tn_ms1.set_no_image()
                            #     cfg.pt.tn_ms2.set_no_image()
                            #     cfg.pt.tn_ms3.set_no_image()
                            # else:
                            self.updateCorrSignalsDrawer(z=x - 1)
                    # elif "Copy-converting" in self.pbar.text():
                    #     # if cfg.pt._tabs.currentIndex() == 0:
                    #     if x%10 == 10:
                    #         logger.info(f'Displaying NG alignment at z={x}')
                    #         cfg.emViewer.initViewerAligned(z=x)
                    #         # cfg.emViewer.

        except:
            print_exception()

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
        '''
        Note:
        pbar_max is set by mp queue for all multiprocessing functions
        '''
        caller = inspect.stack()[1].function
        # logger.critical(f'caller = {caller}, set_n_processes = {set_n_processes}')
        cfg.CancelProcesses = False #0602+
        if set_n_processes and (set_n_processes > 1):
            # logger.critical('Resetting # tasks...')
            cfg.nProcessSteps = set_n_processes
            cfg.nProcessDone = 0
            self.pbarLabel.show()
        else:
            self.pbarLabel.hide()
        # if cancel_processes:
        #     cfg.CancelProcesses = True
        #     self.pbar_cancel_button.hide()
        # else:
        #     self.pbar_cancel_button.show()
        # logger.critical(f'cfg.nProcessSteps = {cfg.nProcessSteps}, cfg.nProcessDone = {cfg.nProcessDone}')
        if pbar_max:
            self.pbar.setMaximum(pbar_max)
        self.pbar.setValue(0)
        self.setPbarText('Preparing Tasks...')
        self.pbar_widget.show()
        QApplication.processEvents()

    def hidePbar(self):
        # logger.info('')
        self.pbar_widget.hide()
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




    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)

        if DEV:
            logger.info(f'caller: {caller_name()}')
            logger.info(f'{event.key()} ({event.text()} / {event.nativeVirtualKey()} / modifiers: {event.nativeModifiers()}) was pressed!')
        # if ((event.key() == 77) and (event.nativeModifiers() == 1048840)) \
        #         or ((event.key() == 16777249) and (event.nativeModifiers() == 264)):
        #     self.enterExitManAlignMode()
        #     return
        if (event.key() == 77) and (event.nativeModifiers() == 1048840):
            self.enterExitManAlignMode()
            return
        # if (event.key() == 16777249) and (event.nativeModifiers() == 264):
        #     self.enterExitManAlignMode()
        #     return
        # M Key: event.key(): 77 <class 'int'>
        # Command key modifier: event.nativeModifiers(): 1048840 <class 'int'>



        if event.key() == Qt.Key_Escape:
            if self.isMaximized():
                self.showNormal()
        if event.key() == Qt.Key_F11:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        if event.key() == Qt.Key_Slash:
            logger.info('Qt.Key_Slash was pressed')
            if self._isProjectTab():
                if getData('state,manual_mode'):
                    # newcur = 1 - cfg.data['state']['stackwidget_ng_toggle']
                    # cfg.data['state']['stackwidget_ng_toggle'] = newcur
                    # if newcur == 1:
                    #     cfg.pt.rb_transforming.setChecked(True)f
                    # else:
                    #     cfg.pt.rb_reference.setChecked(True)
                    cfg.data['state']['stackwidget_ng_toggle'] = (1, 0)[cfg.data['state']['stackwidget_ng_toggle'] == 1]
                    if cfg.data['state']['stackwidget_ng_toggle']:
                        cfg.pt.setRbTransforming()
                    else:
                        cfg.pt.setRbReference()

        self.keyPressed.emit(event)

        if event.key() == Qt.Key_R:
            self.refreshTab()

        elif event.key() == Qt.Key_M:
            self.enterExitManAlignMode()
        # r = 82
        # m = 77
        # k = 75
        # p = 80
        elif event.key() == Qt.Key_K:
            self.skip_change_shortcut()

        elif event.key() == Qt.Key_P:
            self.cbPython.setChecked(not self.cbPython.isChecked())

        elif event.key() == Qt.Key_H:
            self.cbMonitor.setChecked(not self.cbMonitor.isChecked())

        elif event.key() == Qt.Key_Z:
            self.cbNotes.setChecked(not self.cbNotes.isChecked())

        elif event.key() == Qt.Key_T:
            self.cbThumbnails.setChecked(not self.cbThumbnails.isChecked())

        elif event.key() == Qt.Key_I:
            self.cbSignals.setChecked(not self.cbSignals.isChecked())

        # left arrow key = 16777234
        elif event.key() == 16777234:
            self.layer_left()

        # right arrow key = 16777236
        elif event.key() == 16777236:
            self.layer_right()







    def on_key(self, event):
        print('event received @ MainWindow')
        if event.key() == Qt.Key_Space:
            logger.info('Space key was pressed')

        # if event.key() == Qt.Key_M:
        #     logger.info('M key was pressed')

class DockWidget(QDockWidget):
    hasFocus = Signal([QDockWidget])

    def __init__(self, text, parent=None):
        super().__init__(text)
        self.setObjectName(text)
        self.setAllowedAreas(
            Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
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
   able to generate scale image hierarchies, compute affine transforms, and generate aligned
   images using multi-image rendering.

Q: Can AlignEM-SWiFT be used to register or "align" non-EM images?
A: Yes, but its forte is aligning EM images which tend to be large, and greyscale. AlignEM-SWIFT
   provides functionality for downscaling and the ability to pass alignment results (affines)
   from lower scale levels to higher ones.

Q: What are scales?
A: In AlignEM-SWiFT a "scale" means a downsampled (or decreased resolution) series of images.

Q: Why should data be scaled? Is it okay to align the full resolution series with brute force?
A: You could, but EM images tend to run large. A more efficient workflow is to:
   1) generate a hierarchy of downsampled images from the full resolution images
   2) align the lowest resolution images first
   3) pass the computed affines to the scale of next-highest resolution, and repeat
      until the full resolution images are in alignment. In these FAQs this is referred to
      as "climbing the scale hierarchy""

Q: Why do SNR values not necessarily increase as we "climb the scale hierarchy"?
A: SNR values returned by SWIM are a relative metric which depend on image resolution. It is
   therefore most useful when comparing the relative alignment quality of aligned image
   pairs at the same scale.

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

