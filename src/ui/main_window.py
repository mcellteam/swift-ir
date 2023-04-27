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
import numpy as np
# from guppy import hpy; h=hpy()
import neuroglancer as ng
import pyqtgraph.console
import pyqtgraph as pg
import qtawesome as qta
from rechunker import rechunk
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QTimer, QEventLoop, QRect, QPoint, \
    QPropertyAnimation
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QKeySequence, QMovie, QStandardItemModel, QColor, QCursor
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QStackedWidget, QGridLayout, QInputDialog, QLineEdit, QPushButton, QMessageBox, \
    QComboBox, QSplitter, QTreeView, QHeaderView, QAction, QActionGroup, QProgressBar, \
    QShortcut, QGraphicsOpacityEffect, QCheckBox, QSpinBox, QDoubleSpinBox, QRadioButton, QSlider, \
    QDesktopWidget, QTextEdit, QToolBar, QListWidget, QMenu, QTableView, QTabWidget, QStatusBar, QTextBrowser, \
    QFormLayout, QGroupBox, QScrollArea, QToolButton, QWidgetAction, QSpacerItem, QButtonGroup, QAbstractButton, \
    QApplication, QPlainTextEdit, QTableWidget, QTableWidgetItem, QDockWidget, QDialog, QDialogButtonBox, QFrame

import src.config as cfg
import src.shaders
from src.background_worker import BackgroundWorker
from src.compute_affines import compute_affines
from src.config import ICON_COLOR
from src.data_model import DataModel
from src.funcs_zarr import tiffs2MultiTiff
from src.generate_aligned import generate_aligned
from src.generate_scales import generate_scales
from src.thumbnailer import Thumbnailer
from src.generate_scales_zarr import generate_zarr_scales
from src.helpers import run_checks, setOpt, getOpt, getData, setData,  print_exception, get_scale_val, \
    natural_sort, tracemalloc_start, tracemalloc_stop, tracemalloc_compare, tracemalloc_clear, \
    exist_aligned_zarr_cur_scale, exist_aligned_zarr, configure_project_paths, isNeuroglancerRunning, \
    update_preferences_model, delete_recursive, initLogFiles, is_mac
from src.ui.dialogs import AskContinueDialog, ConfigProjectDialog, ConfigAppDialog, NewConfigureProjectDialog, \
    open_project_dialog, export_affines_dialog, mendenhall_dialog, RechunkDialog, ExitAppDialog, SaveExitAppDialog
from src.ui.process_monitor import HeadupDisplay
from src.ui.models.json_tree import JsonModel
from src.ui.toggle_switch import ToggleSwitch
from src.ui.sliders import DoubleSlider, RangeSlider
from src.ui.widget_area import WidgetArea
from src.ui.control_panel import ControlPanel
from src.ui.file_browser import FileBrowser
from src.ui.tab_project import ProjectTab
from src.ui.tab_zarr import ZarrTab
from src.ui.webpage import WebPage
from src.ui.tab_browser import WebBrowser
from src.ui.tab_open_project import OpenProject
from src.ui.thumbnail import CorrSignalThumbnail
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel, Button

# from src.ui.components import AutoResizingTextEdit
from src.mendenhall_protocol import Mendenhall
import src.pairwise
# if cfg.DEV_MODE:
#     from src.ui.python_console import PythonConsole
from src.ui.python_console import PythonConsole


__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

logger.critical('_Directory of this script: %s' % os.path.dirname(__file__))

class MainWindow(QMainWindow):
    resized = Signal()
    keyPressed = Signal(int)
    # alignmentFinished = Signal()
    updateTable = Signal()
    cancelMultiprocessing = Signal()
    sectionChanged = Signal()

    def __init__(self, data=None):
        QMainWindow.__init__(self)
        self.app = QApplication.instance()
        self.setObjectName('mainwindow')
        self.window_title = 'AlignEM-SWiFT'
        self.setWindowTitle(self.window_title)
        cfg.thumb = Thumbnailer()
        # self.installEventFilter(self)
        # self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.initImageAllocations()
        self.initPrivateMembers()
        self.initThreadpool(timeout=250)
        self.initOpenGlContext()
        # self.initPythonConsole()
        self.initStatusBar()
        self.initPbar()
        self.initControlPanel()
        self.initUI()
        self.initMenu()
        self.initWidgetSpacing()
        self.initStyle()
        self.initShortcuts()
        self.initToolbar()
        # self.initData()
        # self.initView()
        self.initLaunchTab()

        cfg.event = multiprocessing.Event()

        # self.alignmentFinished.connect(self.updateProjectTable)
        self.cancelMultiprocessing.connect(self.cleanupAfterCancel)

        self.activateWindow()

        self.tell('To Relaunch on Lonestar6:\n\n  cd $WORK/swift-ir\n  source tacc_boostrap\n')

        if not cfg.NO_SPLASH:
            self.show_splash()

        self.pbar_cancel_button.setEnabled(cfg.DAEMON_THREADS)
        self.initSizeAndPos(cfg.WIDTH, cfg.HEIGHT)


    def initSizeAndPos(self, width, height):
        self.resize(width, height)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center() # cp PyQt5.QtCore.QPoint
        # cp.setX(cp.x() - 200)
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def resizeEvent(self, event):
        if self._working:
            return
        # if self.detailsWidget.isVisible():
        #     h = self.detailsWidget.geometry().height()
        #     self.corrSignalsWidget.setFixedSize(max(10,h-44), max(10,h-44))
        # if not self._working:
        #     self.resized.emit()
        #     if cfg.project_tab:
        #         cfg.project_tab.initNeuroglancer()
        #     return super(MainWindow, self).resizeEvent(event)
        if self._isProjectTab():

            # if cfg.project_tab._tabs.currentIndex() == 0:
            if getData('state,mode') == 'comparison':
                # # cfg.project_tab.initNeuroglancer()
                # w = cfg.project_tab.webengine.width() / ((2, 3)[cfg.data.is_aligned_and_generated()])
                # h = cfg.project_tab.webengine.height()
                # cfg.emViewer.cs_scale = None
                #
                # # cfg.project_tab.disableZoomSlider()
                # cfg.emViewer.diableZoom()
                # # time.sleep(2)
                # cfg.emViewer.initZoom(w=w,h=h)
                # # cfg.project_tab.enableZoomSlider()
                # # time.sleep(2)
                # cfg.emViewer.enableZoom()
                cfg.project_tab.initNeuroglancer()


    # def neuroglancer_configuration_0(self):
    #
    #     # logger.info('')
    #
    # def neuroglancer_configuration_1(self):
    #     logger.critical(f'caller:{inspect.stack()[1].function}')
    #     # logger.info('')
    #
    # def neuroglancer_configuration_2(self):
    #     logger.info('')
    #     if cfg.data:
    #         if cfg.project_tab:
    #             self.comboboxNgLayout.setCurrentText('xy')
    #             cfg.project_tab._widgetArea_details.show()
    #             # cfg.project_tab._tabs.setCurrentIndex(0) #0124-
    #             # cfg.project_tab.updateNeuroglancer()
    #             cfg.project_tab.initNeuroglancer()


    def cleanupAfterCancel(self):
        logger.critical('Cleaning Up After Multiprocessing Tasks Were Canceled...')
        cfg.project_tab.snr_plot.initSnrPlot()
        cfg.project_tab.project_table.setScaleData()
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
        if not self._working:
            logger.critical('Refreshing...')
            if self._isProjectTab():
                # if cfg.project_tab._tabs.currentIndex() == 0:
                    # delay = time.time() - self._lastRefresh
                    # logger.info('delay: %s' % str(delay))
                    # if self._lastRefresh and (delay < 2):
                    #     self.hardRestartNg()
                    # else:
                    #     cfg.project_tab.refreshTab()
                    # self._lastRefresh = time.time()
                cfg.project_tab.refreshTab()

                for v in cfg.project_tab.get_viewers():
                    v.set_zmag()
                self.hud.done()
                self.updateEnabledButtons()    #0301+
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
        self._unsaved_changes = False
        self._working = False
        self._scales_combobox_switch = 0 #1125
        self._isPlayingBack = 0
        self._isProfiling = 0
        self.detachedNg = WebPage()
        self._lastRefresh = 0
        # self._corrSpotDrawerSize = 140
        self._corrSpotDrawerSize = 160
        self.count_calls = {}

        self._dontReinit = False

    def initStyle(self):
        logger.info('')
        self.apply_default_style()


    def initPythonConsole(self):
        # logger.info('')
        #
        # namespace = {
        #     'pg': pg,
        #     'np': np,
        #     'cfg': src.config,
        #     'mw': src.config.main_window,
        #     'emViewer': cfg.emViewer,
        #     'ng': ng,
        # }
        # text = """
        # Caution - anything executed here is injected into the main event loop of AlignEM-SWiFT!
        # """
        #
        # cfg.py_console = pyqtgraph.console.ConsoleWidget(namespace=namespace, text=text)
        # self._py_console = QWidget()
        # self._py_console.setStyleSheet('background: #222222; color: #f3f6fb; border-radius: 5px;')
        # lab = QLabel('Python Console')
        # # lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        # # lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 4px; margin-top: 4px;')
        # lab.setStyleSheet(
        #     """
        #     color: #f3f6fb;
        #     font-size: 10px;
        #     font-weight: 600;
        #     padding-left: 2px;
        #     padding-top: 2px;
        #     """)
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0,0,0,0)
        # vbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignBaseline)
        # vbl.addWidget(cfg.py_console)
        # self._py_console.setLayout(vbl)
        # self._py_console.hide()
        pass


    def _callbk_showHideCorrSpots(self):
        logger.info('')
        # self.correlation_signals.setVisible(self.correlation_signals.isHidden())
        self.correlation_signals.setVisible(cfg.project_tab.signalsAction.isChecked())
        self._splitter.setHidden(self.correlation_signals.isHidden() and self.notes.isHidden() and self._dev_console.isHidden())
        # if self.correlation_signals.isVisible():
        if cfg.project_tab.signalsAction.isChecked():
        #     sizes = self._splitter.sizes()
        #     sizes[1] = self._corrSpotDrawerSize
        #     self._splitter.setSizes(sizes)
            QApplication.processEvents()
            self.updateCorrSignalsDrawer()

        # self.correlation_signals.setVisible(self.correlation_signals.isHidden())
        # logger.critical(f'_splitter sizes: {self._splitter.sizes()}, corr spot height = {self.correlation_signals.height()}')
        # logger.critical('is visible? %r' % self.correlation_signals.isVisible())


    def forceShowCorrSignalDrawer(self):
        logger.critical(f'forceShowCorrSignalDrawer [sizes: {self._splitter.sizes()}]>>>>')
        if self._isProjectTab():
            self.correlation_signals.setVisible(True)
            cfg.project_tab.signalsAction.setChecked(True)
            # sizes = self._splitter.sizes()
            # sizes[1] = 160
            # self._splitter.setSizes(sizes)
            QApplication.processEvents()
            self.updateCorrSignalsDrawer()
        logger.critical(f'<<<< forceShowCorrSignalDrawer [sizes: {self._splitter.sizes()}]')



    def updateCorrSignalsDrawer(self):
        caller = inspect.stack()[1].function
        logger.info('caller: %s >>>>' % caller)
        if self._isProjectTab():
            if self.correlation_signals.isVisible():
                logger.info(f'updateCorrSignalsDrawer [sizes: {self._splitter.sizes()}] >>>>')
                colors = cfg.glob_colors

                thumbs = cfg.data.get_signals_filenames()
                n = len(thumbs)
                splitterSizes = self._splitter.sizes()

                logger.info(f'n             = {n}')
                logger.info(f'thumbs        = {thumbs}')
                logger.info(f'splitterSizes = {splitterSizes}')
                if n == 0:
                    self.corrSignalsWidget.hide()
                    self.lab_corr_signals.show()
                    splitterSizes[1] = 24
                    self._splitter.setSizes(splitterSizes)
                    QApplication.processEvents()
                    return
                else:
                    self.corrSignalsWidget.show()
                    self.lab_corr_signals.hide()

                snr_vals = cfg.data.snr_components()
                logger.info(f'snr_vals      = {snr_vals}')
                # splitterSizes[1] = 110

                if splitterSizes[1] == 0:
                    splitterSizes[1] = self._corrSpotDrawerSize

                logger.info(f'Setting _splitter sizes to {splitterSizes}')
                self._splitter.setSizes(splitterSizes)
                
                QApplication.processEvents()
                logger.info(f'_splitter sizes: {self._splitter.sizes()}')
                logger.info(f'snr vals: {snr_vals}')

                h = max(self._splitter.sizes()[1] - 30, 40)

                logger.info(f'h = {h}')

                # logger.info('thumbs: %s' % str(thumbs))
                for i in range(7):

                    self.corrSignalsList[i].setFixedSize(h, h)
                    if i < n:
                        # logger.info('i = %d ; name = %s' %(i, str(thumbs[i])))
                        try:
                            self.corrSignalsList[i].set_data(path=thumbs[i], snr=snr_vals[i])
                            self.corrSignalsList[i].setStyleSheet(f"""border: 4px solid {colors[i]}; padding: 3px;""")
                        except:
                            print_exception()
                            self.corrSignalsList[i].set_no_image()
                        finally:
                            self.corrSignalsList[i].show()
                    else:
                        self.corrSignalsList[i].hide()

        logger.info(f'<<<< updateCorrSignalsDrawer [actual sizes: {self._splitter.sizes()}]')


    def clearCorrSpotsDrawer(self):
        logger.info('')
        if self._isProjectTab():
            snr_vals = cfg.data.snr_components()
            thumbs = cfg.data.get_signals_filenames()
            n = len(thumbs)
            # logger.info('thumbs: %s' % str(thumbs))
            for i in range(7):
                self.corrSignalsList[i].hide()
                # h = max(self.correlation_signals.height() - 38, 64)
                # self.corrSignalsList[i].setFixedSize(h, h)
                # if i < n:
                #     # logger.info('i = %d, name = %s' %(i, str(thumbs[i])))
                #     try:
                #         if snr_vals:
                #             self.corrSignalsList[i].set_data(path=thumbs[i], snr=snr_vals[i])
                #         else:
                #             self.corrSignalsList[i].set_data(path=thumbs[i], snr=0.0)
                #     except:
                #         # print_exception()
                #         self.corrSignalsList[i].set_no_image()
                #     self.corrSignalsList[i].show()
                # else:
                #     self.corrSignalsList[i].hide()


    # def get_viewers(self):
    #     logger.info('')
    #     viewers = []
    #     if self._isProjectTab():
    #         if getData('state,manual_mode'):
    #             viewers.extend([cfg.baseViewer, cfg.refViewer, cfg.project_tab.MA_viewer_stage])
    #             # return [cfg.baseViewer, cfg.refViewer]
    #         tab = cfg.project_tab._tabs.currentIndex()
    #         if tab == 0:
    #             viewers.extend([cfg.emViewer])
    #         elif tab == 3:
    #             viewers.extend([cfg.project_tab.snrViewer])
    #     return viewers


    def _callbk_showHidePython(self):
        logger.info(f'QApplication.focusWidget = {QApplication.focusWidget()}')
        self._dev_console.setVisible(self._dev_console.isHidden())
        self._splitter.setHidden(self.correlation_signals.isHidden() and self.notes.isHidden() and self._dev_console.isHidden())
        logger.info(f'QApplication.focusWidget = {QApplication.focusWidget()}')
        self.pythonConsole.setFocus()
        logger.info(f'QApplication.focusWidget = {QApplication.focusWidget()}')
        self.pythonButton.setText(('Python','Hide')[self._dev_console.isVisible()])
        self.pythonButton.setStatusTip(('Show Python Console','Hide Python Console')[self._dev_console.isVisible()])


    def _callbk_showHideControls(self):
        # self.cpanelFrame.setVisible(self.cpanelFrame.isHidden())

        if self.cpanelFrame.isHidden():
            self.cpanelFrame.show()
        else:
            self.cpanelFrame.hide()

        self.controlsButton.setText(('Controls','Hide')[self.cpanelFrame.isVisible()])
        self.controlsButton.setStatusTip(('Show Control Panel','Hide Control Panel')[self.cpanelFrame.isVisible()])
        self._splitter.setHidden(
            self.correlation_signals.isHidden() and self.notes.isHidden() and self._dev_console.isHidden())


    def _callbk_showHideNotes(self):
        self.notes.setVisible(self.notes.isHidden())
        self.notesButton.setText(('Notepad', 'Hide')[self.notes.isVisible()])
        self.notesButton.setStatusTip(('Show Notepad','Hide Notepad')[self.notes.isVisible()])
        self.updateNotes()
        self._splitter.setHidden(
            self.correlation_signals.isHidden() and self.notes.isHidden() and self._dev_console.isHidden())


    def _forceHidePython(self):

        # con = (self._py_console, self._dev_console)[cfg.DEV_MODE]
        con = self._dev_console
        label = ' Python'
        icon = 'mdi.language-python'
        # color = '#f3f6fb'
        color = '#380282'
        con.hide()
        self._btn_show_hide_console.setIcon(qta.icon(icon, color=color))
        self._btn_show_hide_console.setText(label)
        self._splitter.setHidden(
            self.correlation_signals.isHidden() and self.notes.isHidden() and self._dev_console.isHidden())


    def autoscale(self, make_thumbnails=True):

        logger.critical('>>>> autoscale >>>>')

        #Todo This should check for existence of original source files before doing anything
        self.stopNgServer() #0202-
        self.tell('Generating TIFF Scale Image Hierarchy...')
        cfg.nTasks = 3
        cfg.nCompleted = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.pbarLabel.setText('Task (0/%d)...' % cfg.nTasks)
        self.showZeroedPbar()
        self.set_status('Autoscaling...')
        self._disableGlobTabs()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_scales(dm=cfg.data))
                self.threadpool.start(self.worker)
            else:
                generate_scales(dm=cfg.data)
        except:
            print_exception()
            self.warn('Something Unexpected Happened While Generating TIFF Scale Hierarchy')

        # show_status_report(results=cfg.results, dt=cfg.dt)

        cfg.data.link_reference_sections() #Todo: check if this is necessary
        cfg.data.scale = cfg.data.scales()[-1]

        logger.info('Autoscaler is setting image sizes per scale...')
        for s in cfg.data.scales():
            cfg.data.set_image_size(s=s)

        self.tell('Copy-converting TIFFs to NGFF-Compliant Zarr...')
        self.showZeroedPbar()
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_zarr_scales(cfg.data))
                self.threadpool.start(self.worker)
            else:
                generate_zarr_scales(cfg.data)
        except:
            print_exception()
            self.warn('Something Unexpected Happened While Converting The Scale Hierarchy To Zarr')

        if make_thumbnails:
            self.tell('Generating Thumbnails...')
            self.showZeroedPbar()
            try:
                if cfg.USE_EXTRA_THREADING:
                    self.worker = BackgroundWorker(fn=cfg.thumb.reduce_main())
                    self.threadpool.start(self.worker)
                else:
                    cfg.thumb.reduce_main()

            except:
                print_exception()
                self.warn('Something Unexpected Happened While Generating Thumbnails')

            finally:
                cfg.data.scale = cfg.data.scales()[-1]
                self.hidePbar()
                logger.info('Thumbnail Generation Complete')

        self.enableAllTabs()
        # cfg.project_tab.initNeuroglancer()
        # cfg.data.set_manual_swim_windows_to_default()
        self.pbarLabel.setText('')
        self.tell('**** Processes Complete ****')
        logger.info('<<<< autoscale <<<<')


    def _showSNRcheck(self, s=None):
        caller = inspect.stack()[1].function
        if s == None: s = cfg.data.scale
        if cfg.data.is_aligned():
            logger.info(f'Checking SNR data for {s}...')
            failed = cfg.data.check_snr_status()
            if len(failed) == len(cfg.data):
                self.warn(f'No SNR Data Available for %s' % cfg.data.scale_pretty(s=s))
            elif failed:
                indexes, names = zip(*failed)
                lst_names = ''
                for name in names:
                    lst_names += f'\n  Section: {name}'
                self.warn(f'No SNR Data For Layer(s): {", ".join(map(str, indexes))}')


    # def regenerateOne(self):
    #     start = cfg.data.zpos
    #     end = cfg.data.zpos + 1
    #     self.regenerate(scale=cfg.data.scale, start=start, end=end)


    def regenerate(self, scale, start=0, end=None) -> None:
        '''Note: For now this will always reallocate Zarr, i.e. expects arguments for full stack'''
        if self._working == True:
            self.warn('Another Process is Already Running'); return
        if not cfg.data.is_aligned(s=scale):
            self.warn('Scale Must Be Aligned First'); return
        cfg.nTasks = 3
        cfg.nCompleted = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.pbarLabel.setText('Task (0/%d)...' % cfg.nTasks)
        self.showZeroedPbar()
        logger.info('Regenerate Aligned Images...')
        cfg.data.set_has_bb(cfg.data.use_bb())  #Critical, also see regenerate
        self.tell('Regenerating Aligned Images,  Scale %d...' % get_scale_val(scale))
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=generate_aligned(
                    scale, start, end, stageit=True, reallocate_zarr=True))
                self.threadpool.start(self.worker)
            else:
                generate_aligned(scale, start, end, stageit=True, reallocate_zarr=True)
        except:
            print_exception()
        finally:
            logger.info('Generate Alignment Finished')

        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(start=start, end=end))
                self.threadpool.start(self.worker)
            else:
                cfg.thumb.reduce_aligned(start=start, end=end)
        except:
            print_exception()
        finally:
            self.pbarLabel.setText('')
            self.hidePbar()
            self.updateDtWidget()
            cfg.project_tab.updateTreeWidget()
            cfg.nCompleted = 0
            cfg.nTasks = 0
            cfg.project_tab.initNeuroglancer()
            logger.info('Generate Aligned Thumbnails Finished')
            self.tell('**** Processes Complete ****')




    def verify_alignment_readiness(self) -> bool:
        logger.info('')
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
        logger.info(f'Returning: {ans}')
        return ans


    @Slot()
    def updateProjectTable(self):
        caller = inspect.stack()[1].function
        logger.info(f'SLOT: Updating Project Table [caller: {caller}]...')
        cfg.project_tab.project_table.setScaleData()


    # @Slot()
    # def restore_interactivity(self):
    #     self._working = False
    #     self.enableAllButtons()
    #     self.updateEnabledButtons()
    #     self.pbar_widget.hide()


    def present_snr_results(self, start=0, end=None):
        try:
            if exist_aligned_zarr_cur_scale():
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
            if abs(diff_avg) < .001: self.tell('  Δ AVG. SNR : 0.000 (NO CHANGE)')
            elif diff_avg < 0:       self.tell('  Δ AVG. SNR : %.3f (WORSE)' % diff_avg)
            else:                    self.tell('  Δ AVG. SNR : %.3f (BETTER)' % diff_avg)
        except:
            logger.warning('Unable To Present SNR Results')


    def updateDtWidget(self):
        logger.info('')
        # if self._isProjectTab():
        if cfg.data:
            s = cfg.data.scale
            try:
                cfg.project_tab.detailsRuntime.setText(
                    'Gen. Scales      :' + ('%.2fs\n' % cfg.data['data']['t_scaling']).rjust(9) +
                    'Convert Zarr     :' + ('%.2fs\n' % cfg.data['data']['t_scaling_convert_zarr']).rjust(9) +
                    'Source Thumbs    :' + ('%.2fs\n' % cfg.data['data']['t_thumbs']).rjust(9) +
                    'Compute Affines  :' + ('%.2fs\n' % cfg.data['data']['scales'][s]['t_align']).rjust(9) +
                    'Gen. Alignment   :' + ('%.2fs\n' % cfg.data['data']['scales'][s]['t_generate']).rjust(9) +
                    'Aligned Thumbs   :' + ('%.2fs\n' % cfg.data['data']['scales'][s]['t_thumbs_aligned']).rjust(9) +
                    'Corr Spot Thumbs :' + ('%.2fs\n' % cfg.data['data']['scales'][s]['t_thumbs_spot']).rjust(9)
                )
            except:
                logger.warning('detailsTiming cant update')


    def onAlignmentStart(self, scale):
        logger.info('')
        t0 = time.time()

        dt = datetime.datetime.now()

        logger_log = os.path.join(cfg.data.dest(), 'logs', 'logger.log')
        mp_log = os.path.join(cfg.data.dest(), 'logs', 'multiprocessing.log')
        manual_log = os.path.join(cfg.data.dest(), 'logs', 'manual_align.log')
        swim_log = os.path.join(cfg.data.dest(), 'logs', 'swim.log')
        open(logger_log, 'a+').close()
        open(manual_log, 'a+').close()
        open(mp_log, 'a+').close()
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
        self.pbarLabel.setText('Task (0/%d)...' % cfg.nTasks)
        if not cfg.ignore_pbar:
            self.showZeroedPbar()
        cfg.data.set_use_bounding_rect(self._bbToggle.isChecked(), s=cfg.data.scale)
        if cfg.data.is_aligned(s=scale):
            cfg.data.set_previous_results()

        self._autosave()

        t6 = time.time()
        dt = t6 - t0
        # time point 6: = 0.2953681945800781

        self.stopNgServer()  # 0202-

        t9 = time.time()
        dt = t9 - t0
        logger.critical(f'onAlignmentStart, time: = {dt}')


    def onAlignmentEnd(self, start, end):
        logger.info('Running Post-Alignment Tasks...')
        # self.alignmentFinished.emit()
        t0 = time.time()
        try:
            self.pbarLabel.setText('')
            cfg.project_tab.snr_plot.initSnrPlot()
            self.updateEnabledButtons()
            self.updateProjectTable() #+
            self.updateMenus()
            self.present_snr_results(start=start, end=end)
            prev_snr_average = cfg.data.snr_prev_average()
            snr_average = cfg.data.snr_average()
            self.tell('New Avg. SNR: %.3f, Previous Avg. SNR: %.3f' % (snr_average, prev_snr_average))
            self.updateDtWidget()
            cfg.project_tab.updateTreeWidget()
            cfg.project_tab.updateProjectLabels()
            self._bbToggle.setChecked(cfg.data.has_bb())
            self.dataUpdateWidgets()
            self._showSNRcheck()
        except:
            print_exception()
        finally:
            self._working = False
            self.hidePbar()
            self.enableAllTabs()
            self._autosave()

            t9 = time.time()
            dt = t9 - t0
            logger.critical(f'onAlignmentEnd, time: {dt}')


    def alignAll(self):
        cfg.ignore_pbar = False
        '''MUST handle bounding box for partial-stack alignments.'''
        self.tell('Aligning All Sections (%s)...' % cfg.data.scale_pretty())
        scale = cfg.data.scale
        # is_realign = cfg.data.is_aligned(s=scale)
        # This SHOULD always work. Only set bounding box here. Then, during a single or partial alignment,
        # reduce_aligned will use the correct value that is consistent with the other images
        # at the same scale
        if self._toggleAutogenerate.isChecked():
            cfg.nTasks = 5
        else:
            cfg.nTasks = 3
        cfg.nCompleted = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        cfg.data.set_has_bb(cfg.data.use_bb()) #Critical, also see regenerate
        cfg.data['data']['scales'][scale]['use_bounding_rect'] = self._bbToggle.isChecked()
        self.align(
            scale=cfg.data.scale,
            start=0,
            end=None,
            renew_od=True,
            reallocate_zarr=True,
            # stageit=stageit,
            stageit=True,
        )
        # if not cfg.CancelProcesses:
        #     self.present_snr_results()

        self.onAlignmentEnd(start=0, end=None)
        cfg.project_tab.initNeuroglancer()
        self.tell('**** Processes Complete ****')


    def alignRange(self):
        cfg.ignore_pbar = False
        start = int(self.startRangeInput.text())
        end = int(self.endRangeInput.text()) + 1
        if self._toggleAutogenerate.isChecked():
            cfg.nTasks = 5
        else:
            cfg.nTasks = 3
        cfg.nCompleted = 0
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
        self.tell('**** Processes Complete ****')


    # def alignOne(self, stageit=False):
    def alignOne(self):
        logger.critical('Aligning One...')
        self.tell('Re-aligning Section #%d (%s)...' %
                  (cfg.data.zpos, cfg.data.scale_pretty()))
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        cfg.nCompleted = 0
        cfg.nTasks = 2
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
        # self.onAlignmentEnd(start=start, end=end)
        self._working = False
        self.enableAllTabs()
        self.updateCorrSignalsDrawer()
        cfg.project_tab.initNeuroglancer()
        self.tell('Section #%d Alignment Complete' % start)
        self.tell('SNR Before: %.3f  SNR After: %.3f' %
                  (cfg.data.snr_prev(l=start), cfg.data.snr(l=start)))
        self.tell('**** Processes Complete ****')


    def alignGenerateOne(self):
        cfg.ignore_pbar = True
        logger.critical('Realigning Manually...')
        self.tell('Re-aligning Section #%d (%s)...' %
                  (cfg.data.zpos, cfg.data.scale_pretty()))
        start = cfg.data.zpos
        end = cfg.data.zpos + 1
        cfg.nCompleted = 0
        cfg.nTasks = 5
        self.setPbarMax(5)
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
        self.tell('**** Processes Complete ****')
        cfg.ignore_pbar = False


    def align(self, scale, start, end, renew_od, reallocate_zarr, stageit, align_one=False, swim_only=False):
        #Todo change printout based upon alignment scope, i.e. for single layer
        # caller = inspect.stack()[1].function
        # if caller in ('alignGenerateOne','alignOne'):
        #     ALIGN_ONE = True
        logger.info(f'Aligning start:{start}, end: {end}, scale: {scale}...')
        if not self.verify_alignment_readiness(): return


        self.onAlignmentStart(scale=scale)
        m = {'init_affine': 'Initializing', 'refine_affine': 'Refining'}
        self.tell("%s Affines (%s)..." %(m[cfg.data.al_option(s=scale)], cfg.data.scale_pretty(s=scale)))

        if cfg.ignore_pbar:
            self.showZeroedPbar()
            self.setPbarText('Computing Affine...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=compute_affines(scale, start, end))
                self.threadpool.start(self.worker)
            else: compute_affines(scale, start, end)
        except:   print_exception(); self.err('An Exception Was Raised During Alignment.')
        # else:     logger.info('Affine Computation Finished')

        if cfg.ignore_pbar:
            cfg.nCompleted +=1
            self.updatePbar()
            self.setPbarText('Scaling Correlation Signal Thumbnails...')
        try:
            if cfg.USE_EXTRA_THREADING:
                self.worker = BackgroundWorker(fn=cfg.thumb.reduce_signals(start=start, end=end))
                self.threadpool.start(self.worker)
            else: cfg.thumb.reduce_signals(start=start, end=end)
        except: print_exception(); self.warn('There Was a Problem Generating Corr Spot Thumbnails')
        # else:   logger.info('Correlation Signal Thumbnail Generation Finished')


        # if cfg.project_tab._tabs.currentIndex() == 1:
        #     cfg.project_tab.project_table.setScaleData()

        if not swim_only:
            if self._toggleAutogenerate.isChecked():

                if cfg.ignore_pbar:
                    cfg.nCompleted += 1
                    self.updatePbar()
                    self.setPbarText('Generating Alignment...')

                try:
                    if cfg.USE_EXTRA_THREADING:
                        self.worker = BackgroundWorker(fn=generate_aligned(
                            scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit))
                        self.threadpool.start(self.worker)
                    else: generate_aligned(scale, start, end, renew_od=renew_od, reallocate_zarr=reallocate_zarr, stageit=stageit)
                except:
                    print_exception()
                finally:
                    logger.info('Generate Alignment Finished')

                if cfg.ignore_pbar:
                    cfg.nCompleted += 1
                    self.updatePbar()
                    self.setPbarText('Generating Aligned Thumbnail...')

                try:
                    if cfg.USE_EXTRA_THREADING:
                        self.worker = BackgroundWorker(fn=cfg.thumb.reduce_aligned(start=start, end=end))
                        self.threadpool.start(self.worker)
                    else: cfg.thumb.reduce_aligned(start=start, end=end)
                except:
                    print_exception()
                finally:
                    logger.info('Generate Aligned Thumbnails Finished')

                if cfg.ignore_pbar:
                    cfg.nCompleted += 1
                    self.updatePbar()
                    self.setPbarText('Aligning')

        self.pbarLabel.setText('')
        self.hidePbar()
        cfg.nCompleted = 0
        cfg.nTasks = 0


    def rescale(self):
        if self._isProjectTab():

            msg ='Warning: Rescaling clears project data.\nProgress will be lost. Continue?'
            dlg = AskContinueDialog(title='Confirm Rescale', msg=msg)
            if dlg.exec():
                recipe_dialog = NewConfigureProjectDialog(parent=self)
                if recipe_dialog.exec():

                    self.stopNgServer()  # 0202-
                    self._disableGlobTabs()

                    self.tell('Clobbering the Project Directory %s...')
                    try:
                        delete_recursive(dir=cfg.data.dest(), keep_core_dirs=True)
                    except:
                        print_exception()
                        self.err('The Above Error Was Encountered During Clobber of the Project Directory')
                    else:
                        self.hud.done()

                    cfg.nTasks = 3
                    cfg.nCompleted = 0
                    cfg.CancelProcesses = False
                    self.showZeroedPbar()
                    self.pbarLabel.setText('Task (0/%d)...' % cfg.nTasks)
                    # makedirs_exist_ok(cfg.data.dest(), exist_ok=True)
                    self.hud.post("Re-scaling...")
                    try:
                        self.autoscale(make_thumbnails=False)
                    except:
                        print_exception()
                    else:
                        self._autosave()
                        self.tell('Rescaling Successful')
                    finally:
                        self.onStartProject()
                        self.hidePbar()

                    self.tell('**** Processes Complete ****')


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
                self.worker = BackgroundWorker(fn=generate_zarr_scales())
                self.threadpool.start(self.worker)
            else:
                generate_zarr_scales()
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
                cfg.main_window.tell('Resetting Skips...')
                cfg.data.clear_all_skips()
        else:
            self.warn('No Skips To Clear.')


    def apply_all(self) -> None:
        '''Apply alignment settings to all images for all scales'''
        if cfg.data:
            swim_val = self._swimWindowControl.value() / 100.
            whitening_val = self._whiteningControl.value()
            self.tell('Applying Settings To All Scales + Layers...\n'
                      '  SWIM Window : %dpx\n'
                      '  Whitening   : %.3f' % (self._swimWindowControl.value(), whitening_val))
            for s in cfg.data.scales():
                cfg.data.set_use_bounding_rect(self._bbToggle.isChecked())
                if self._polyBiasCombo.currentText() == 'None':
                    cfg.data.set_use_poly_order(False)
                else:
                    cfg.data.set_use_poly_order(True)
                    cfg.data.set_poly_order(int(self._polyBiasCombo.currentText()), s=s)
                for layer in cfg.data.stack(s=s):
                    layer['alignment']['method_data']['win_scale_factor'] = swim_val
                    layer['alignment']['method_data']['whitening_factor'] = whitening_val


    def enableAllButtons(self):
        self._btn_alignAll.setEnabled(True)
        self._btn_alignOne.setEnabled(True)
        self._btn_alignRange.setEnabled(True)
        self._btn_regenerate.setEnabled(True)
        self._scaleDownButton.setEnabled(True)
        self._scaleUpButton.setEnabled(True)
        # self._ctlpanel_applyAllButton.setEnabled(True)
        self._skipCheckbox.setEnabled(True)
        self._whiteningControl.setEnabled(True)
        self._swimWindowControl.setEnabled(True)
        self._toggleAutogenerate.setEnabled(True)
        self._bbToggle.setEnabled(True)
        self._polyBiasCombo.setEnabled(True)
        self._btn_clear_skips.setEnabled(True)
        self._toggleAutogenerate.setEnabled(True)
        self.startRangeInput.setEnabled(True)
        self.endRangeInput.setEnabled(True)


    def updateEnabledButtons(self) -> None:
        '''This method does three things:
        (1) Update the visibility of next/prev s buttons depending on current s.
        (2) Set the enabled/disabled state of the align_all-all button
        (3) Sets the input validator on the jump-to lineedit widget'''
        logger.info('')
        if cfg.data:
            # self._btn_alignAll.setText('Align All\n%s' % cfg.data.scale_pretty())
            self._skipCheckbox.setEnabled(True)
            self._toggleAutogenerate.setEnabled(True)
            self._bbToggle.setEnabled(True)
            self._polyBiasCombo.setEnabled(True)
            self._btn_clear_skips.setEnabled(True)
            self._swimWindowControl.setEnabled(True)
            self._whiteningControl.setEnabled(True)
            # self._ctlpanel_applyAllButton.setEnabled(True)
        else:
            self._skipCheckbox.setEnabled(False)
            self._whiteningControl.setEnabled(False)
            self._swimWindowControl.setEnabled(False)
            self._toggleAutogenerate.setEnabled(False)
            self._bbToggle.setEnabled(False)
            self._polyBiasCombo.setEnabled(False)
            self._btn_clear_skips.setEnabled(False)
            # self._ctlpanel_applyAllButton.setEnabled(False)

        if cfg.data:
            # if cfg.data.is_aligned_and_generated(): #0202-
            if cfg.data.is_aligned():
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(True)
                self._btn_alignRange.setEnabled(True)
                self._btn_regenerate.setEnabled(True)
                self.startRangeInput.setEnabled(True)
                self.endRangeInput.setEnabled(True)
            elif cfg.data.is_alignable():
                self._btn_alignAll.setEnabled(True)
                self._btn_alignOne.setEnabled(False)
                self._btn_alignRange.setEnabled(False)
                self._btn_regenerate.setEnabled(False)
                self.startRangeInput.setEnabled(False)
                self.endRangeInput.setEnabled(False)
            else:
                self._btn_alignAll.setEnabled(False)
                self._btn_alignOne.setEnabled(False)
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
                    self._btn_alignRange.setEnabled(True)
                    self._btn_regenerate.setEnabled(True)
                    self.startRangeInput.setEnabled(True)
                    self.endRangeInput.setEnabled(True)
                else:
                    self._btn_alignAll.setEnabled(True)
                    self._btn_alignOne.setEnabled(False)
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
            self._btn_alignRange.setEnabled(False)
            self._btn_regenerate.setEnabled(False)
            self.startRangeInput.setEnabled(False)
            self.endRangeInput.setEnabled(False)

        # self._highContrastNgAction.setEnabled(self._isProjectTab())
        # self._detachNgButton.setEnabled(self._isProjectTab())
        # self._highContrastNgAction.setChecked(getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'))


    def layer_left(self):
        logger.info('')
        if self._isProjectTab():
            requested = cfg.data.zpos - 1
            if requested >= 0:
                cfg.data.zpos = requested
            if getData('state,manual_mode'):
                # cfg.project_tab.MA_layer_left()
                # self.initAllViewers()
                cfg.project_tab.initNeuroglancer()
            else:
                cfg.emViewer.set_layer(requested)
            self.dataUpdateWidgets()


    def layer_right(self):
        logger.info('')
        if self._isProjectTab():
            requested = cfg.data.zpos + 1
            if requested < len(cfg.data):
                cfg.data.zpos = requested
            if getData('state,manual_mode'):
                # cfg.project_tab.MA_layer_right()
                # self.initAllViewers()
                cfg.project_tab.initNeuroglancer()
            else:
                cfg.emViewer.set_layer(requested)
            self.dataUpdateWidgets()


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
        # self.statusBar.showMessage(msg)
        pass


    def minimal_stylesheet(self):
        self.setStyleSheet('')
        logger.info('Changing stylesheet to minimal')


    def apply_default_style(self):
        cfg.THEME = 0
        # self.tell('Setting Default Theme')
        self.main_stylesheet = os.path.abspath('src/style/default.qss')
        with open(self.main_stylesheet, 'r') as f:
            style = f.read()
        self.setStyleSheet(style)
        # self.cpanel.setStyleSheet(style)
        # self.hud.set_theme_default()
        self.hud.set_theme_overlay()


    def reset_groupbox_styles(self):
        logger.info('reset_groupbox_styles:')


    # def updateToolbar(self):
    #     caller = inspect.stack()[1].function
    #     logger.info(f'caller: {caller}')
    #     if self._isProjectTab():
    #
    #         if cfg.data['state']['mode'] == 'stack':
    #             setData('state,ng_layout', '4panel')
    #             self.combo_mode.setCurrentIndex(0)
    #         elif cfg.data['state']['mode'] == 'comparison':
    #             setData('state,ng_layout', 'xy')
    #             self.combo_mode.setCurrentIndex(1)
    #
    #         # self.comboboxNgLayout.setCurrentText(cfg.data['ui']['ng_layout'])
    #         if cfg.data.is_aligned_and_generated():
    #             cfg.project_tab.aligned_label.show()
    #             cfg.project_tab.generated_label.show()
    #             cfg.project_tab.unaligned_label.hide()
    #         elif cfg.data.is_aligned():
    #             cfg.project_tab.aligned_label.show()
    #             cfg.project_tab.generated_label.hide()
    #             cfg.project_tab.unaligned_label.hide()
    #         else:
    #             cfg.project_tab.aligned_label.hide()
    #             cfg.project_tab.generated_label.hide()
    #             cfg.project_tab.unaligned_label.show()
    #
    #     else:
    #         cfg.project_tab.aligned_label.hide()
    #         cfg.project_tab.unaligned_label.hide()
    #         cfg.project_tab.generated_label.hide()
    #         cfg.project_tab.generated_label.hide()

    # @Slot()
    def dataUpdateWidgets(self, ng_layer=None) -> None:
        '''Reads Project Data to Update MainWindow.'''
        caller = inspect.stack()[1].function
        self.count_calls.setdefault('dataUpdateWidgets', {})
        self.count_calls['dataUpdateWidgets'].setdefault(caller, 0)
        self.count_calls['dataUpdateWidgets'][caller] += 1

        logger.info(f'Updating widgets (caller: {caller}, zpos={cfg.data.zpos})...')
        if ng_layer:
            logger.info(f'ng_layer (requested): {ng_layer}')

        if self._isProjectTab():

            if self._working == True:
                logger.warning(f"Can't update GUI now - working (caller: {caller})...")
                self.warn("Can't update GUI now - working...")
                return
            if isinstance(ng_layer, int):
                if type(ng_layer) != bool:
                    try:
                        if 0 <= ng_layer < len(cfg.data):
                            logger.critical(f'Setting Layer: {ng_layer}')
                            cfg.data.zpos = ng_layer
                            # self._sectionSlider.setValue(ng_layer)
                    except:
                        print_exception()

            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.snrViewer.set_layer(cfg.data.zpos)

            # logger.critical(f'cfg.data.zpos = {cfg.data.zpos}')
            # self.statusBar.showMessage(cfg.data.name_base(), 1000)

            img_siz = cfg.data.image_size()
            self.statusBar.showMessage(cfg.data.scale_pretty() + ' - ' +
                                       'x'.join(map(str,img_siz)) + ' | ' +
                                       cfg.data.name_base(), msecs=3000)

            cfg.project_tab._overlayRect.hide()
            cfg.project_tab._overlayLab.hide()
            if cfg.data.skipped():
                cfg.project_tab._overlayRect.setStyleSheet('background-color: rgba(0, 0, 0, 0.5);')
                cfg.project_tab._overlayLab.setText('X REJECTED - %s' % cfg.data.name_base())
                cfg.project_tab._overlayLab.show()
                cfg.project_tab._overlayRect.show()
            elif ng_layer == 0:
                cfg.project_tab._overlayLab.setText('No Reference')
                cfg.project_tab._overlayLab.show()
            # else:
            #     cfg.project_tab._overlayRect.hide()
            #     cfg.project_tab._overlayLab.hide()

            if self.correlation_signals.isVisible():
                self.updateCorrSignalsDrawer()

            cur = cfg.data.zpos
            if self.notes.isVisible():
                self.updateNotes()


            self._btn_prevSection.setEnabled(cur > 0)
            self._btn_nextSection.setEnabled(cur < len(cfg.data) - 1)

            if getData('state,manual_mode'):
                cfg.project_tab.dataUpdateMA()
                # if prev_loc != cfg.data.zpos:
                # cfg.project_tab.tgl_alignMethod.setChecked(cfg.data.method() != 'Auto-SWIM')
                # cfg.project_tab.set_method_label_text()

            if cfg.project_tab._tabs.currentIndex() == 2:
                cfg.project_tab.treeview_model.jumpToLayer()

            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.snr_plot.updateLayerLinePos()

            cfg.project_tab.project_table.table.selectRow(cur)
            self._sectionSlider.setValue(cur)
            self._jumpToLineedit.setText(str(cur)) #0131+

            if cfg.project_tab.corrSignalsWidget.isVisible():
                if cfg.data.method() in ('grid-default','grid-custom'):
                    snr_vals = cfg.data.snr_components()
                    n = len(snr_vals)
                    if (n >= 1) and (snr_vals[0] > .001):
                        cfg.project_tab.cs0.set_data(path=cfg.data.signal_q0_path(), snr=snr_vals[0])
                    else:
                        cfg.project_tab.cs0.set_no_image()
                    if (n >= 2):
                        cfg.project_tab.cs1.set_data(path=cfg.data.signal_q1_path(), snr=snr_vals[1])
                    else:
                        cfg.project_tab.cs1.set_no_image()
                    if (n >= 3):
                        cfg.project_tab.cs2.set_data(path=cfg.data.signal_q2_path(), snr=snr_vals[2])
                    else:
                        cfg.project_tab.cs2.set_no_image()
                    if (n >= 4):
                        cfg.project_tab.cs3.set_data(path=cfg.data.signal_q3_path(), snr=snr_vals[3])
                    else:
                        cfg.project_tab.cs3.set_no_image()
                elif cfg.data.method() == 'manual-hint':
                    files = cfg.data.get_signals_filenames()
                    snr_vals = cfg.data.snr_components()
                    n = len(files)
                    if n >= 1:
                        cfg.project_tab.cs0.show()
                        cfg.project_tab.cs0.set_data(path=files[0], snr=snr_vals[0])
                    else:       cfg.project_tab.cs0.set_no_image()
                    if n >= 2:  cfg.project_tab.cs1.set_data(path=files[1], snr=snr_vals[1])
                    else:       cfg.project_tab.cs1.set_no_image()
                    if n >= 3:  cfg.project_tab.cs2.set_data(path=files[2], snr=snr_vals[2])
                    else:       cfg.project_tab.cs2.set_no_image()
                    if n >= 4:
                        cfg.project_tab.cs3.set_data(path=files[3], snr=snr_vals[3])
                    else:
                        cfg.project_tab.cs3.set_no_image()

            br = '&nbsp;'
            a = """<span style='color: #ffe135;'>"""
            b = """</span>"""
            nl = '<br>'

            if cfg.project_tab.detailsSection.isVisible():
                txt = f"""
                Filename{br}:{br}{a}{cfg.data.filename_basename()}{b}{nl}
                Reference:{br}{a}{cfg.data.reference_basename()}{b}{nl}
                Modified{br}:{br}{a}{cfg.data.modified}{b}{nl}"""
                method = cfg.data.method()
                if method == 'Auto-SWIM':       txt += f"Method{br*3}:{br}{a}Automatic{br}SWIM{b}"
                elif method == 'Manual-Hint':   txt += f"Method{br*3}:{br}{a}Manual,{br}Hint{b}"
                elif method == 'Manual-Strict': txt += f"Method{br*3}:{br}{a}Manual,{br}Strict{b}"
                # txt += f"""Reject{br*7}:{br}[{(' ', 'X')[cfg.data.skipped()]}]"""
                cfg.project_tab.detailsSection.setText(txt)

            if cfg.project_tab.detailsAFM.isVisible():
                afm, cafm = cfg.data.afm(), cfg.data.cafm()
                afm_txt, cafm_txt = [], []
                for x in range(2):
                    for y in range(3):
                        if y == 0:
                            afm_txt.append(('%.2f' % afm[x][y]).ljust(8))
                            cafm_txt.append(('%.2f' % cafm[x][y]).ljust(8))
                        elif y == 1:
                            afm_txt.append(('%.2f' % afm[x][y]).rjust(8))
                            cafm_txt.append(('%.2f' % afm[x][y]).rjust(8))
                        else:
                            afm_txt.append(('%.2f' % afm[x][y]).rjust(11))
                            cafm_txt.append(('%.2f' % cafm[x][y]).rjust(11))
                        if (x == 0) and (y == 2):
                            afm_txt.append(f'{nl}')
                            cafm_txt.append(f'{nl}')
                cfg.project_tab.detailsAFM.setText(
                    f"{a}Affine:{b}{nl}" + "".join(afm_txt) +
                    f"{nl}{a}Cumulative Affine:{b}{nl}" + "".join(cafm_txt))

            if cfg.project_tab.detailsSNR.isVisible():
                if cfg.data.zpos == 0:
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
                    components = cfg.data.snr_components()
                    str0 = ('%.3f' % cfg.data.snr()).rjust(9)
                    str1 = ('%.3f' % cfg.data.snr_prev()).rjust(9)
                    if cfg.data.method() in ('grid-default','grid-custom'):
                        q0 = ('%.3f' % components[0]).rjust(9)
                        q1 = ('%.3f' % components[1]).rjust(9)
                        q2 = ('%.3f' % components[2]).rjust(9)
                        q3 = ('%.3f' % components[3]).rjust(9)
                        cfg.project_tab.detailsSNR.setText(
                            f"Avg. SNR{br*2}:{a}{str0}{b}{nl}"
                            f"Prev.{br}SNR{br}:{str1}{nl}"
                            f"Components{nl}"
                            f"Top,Left{br*2}:{q0}{nl}"
                            f"Top,Right{br}:{q1}{nl}"
                            f"Btm,Left{br*2}:{q2}{nl}"
                            f"Btm,Right{br}:{q3}"
                        )
                    elif cfg.data.method() in ('manual-hint', 'manual-strict'):
                        txt = f"Avg. SNR{br*2}:{a}{str0}{b}{nl}" \
                              f"Prev. SNR{br}:{str1}{nl}" \
                              f"Components"
                        for i in range(len(components)):
                            txt += f'{nl}%d:{br*10}%.3f' % (i, components[i])

                        cfg.project_tab.detailsSNR.setText(txt)

            try:     self._jumpToLineedit.setText(str(cur))
            except:  logger.warning('Current Layer Widget Failed to Update')
            try:     self._skipCheckbox.setChecked(not cfg.data.skipped())
            except:  logger.warning('Skip Toggle Widget Failed to Update')

            # try:     self._whiteningControl.setValue(cfg.data.whitening())
            # except:  logger.warning('Whitening Input Widget Failed to Update')
            # try:
            #     self._swimWindowControl.setMaximum(min(cfg.data.image_size()))
            #     self._swimWindowControl.setValue(cfg.data.swim_window_px()[0])
            # except:
            #     logger.warning('Swim Input Widget Failed to Update')
            #
            # try:
            #     if cfg.data.null_cafm():
            #         self._polyBiasCombo.setCurrentText(str(cfg.data.poly_order()))
            #     else:
            #         self._polyBiasCombo.setCurrentText('None')
            # except:  logger.warning('Polynomial Order Combobox Widget Failed to Update')
            try:     self._bbToggle.setChecked(cfg.data.use_bb())
            except:  logger.warning('Bounding Box Toggle Failed to Update')

            # cfg.project_tab.slotUpdateZoomSlider()

        logger.info(f'<<<< dataUpdateWidgets [zpos={cfg.data.zpos}]')




    def updateNotes(self):
        # caller = inspect.stack()[1].function
        # logger.info('')
        self.notesTextEdit.clear()
        if self._isProjectTab():
            self.notesTextEdit.setPlaceholderText('Enter notes about %s here...'
                                                  % cfg.data.base_image_name(s=cfg.data.scale, l=cfg.data.zpos))
            if cfg.data.notes(s=cfg.data.scale, l=cfg.data.zpos):
                self.notesTextEdit.setPlainText(cfg.data.notes(s=cfg.data.scale, l=cfg.data.zpos))
        else:
            self.notesTextEdit.clear()
            self.notesTextEdit.setPlaceholderText('Enter notes about anything here...')
        self.notes.update()

    # def updateShaderText(self):
    #     # caller = inspect.stack()[1].function
    #     logger.info('')
    #     self.shaderText.clear()
    #     if self._isProjectTab():
    #         self.shaderText.setPlainText(cfg.data['rendering']['shader'])

    # def onShaderApply(self):
    #     # caller = inspect.stack()[1].function
    #     logger.info('')
    #     if self._isProjectTab():
    #         # cfg.data.set_brightness(float(self.brightnessLE.text()))
    #         cfg.data.brightness = float(self.brightnessLE.text())
    #         # cfg.data.set_contrast(float(self.contrastLE.text()))
    #         cfg.data.contrast = float(self.contrastLE.text())
    #         # cfg.data['rendering']['shader'] = self.shaderText.toPlainText()
    #         cfg.project_tab.initNeuroglancer()
    #         self._callbk_unsavedChanges()


    # def clearAffineWidget(self):
    #     afm = cafm = [[0] * 3, [0] * 3]
    #     cfg.project_tab.afm_widget_.setText(make_affine_widget_HTML(afm, cafm))


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
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if self._isProjectTab() or self._isZarrTab():
                logger.info('Setting section slider and jump input validators...')
                if cfg.project_tab:
                    self._jumpToLineedit.setValidator(QIntValidator(0, len(cfg.data) - 1))
                    self._sectionSlider.setRange(0, len(cfg.data) - 1)
                    self._sectionSlider.setValue(cfg.data.zpos)
                    self.sectionRangeSlider.setMin(0)
                    self.sectionRangeSlider.setStart(0)
                    self.sectionRangeSlider.setMax(len(cfg.data) - 1)
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


    # @Slot()
    # def jump_to(self, requested) -> None:
    #     logger.info('')
    #     if self._isProjectTab():
    #         if requested not in range(len(cfg.data)):
    #             logger.warning('Requested layer is not a valid layer')
    #             return
    #         cfg.data.zpos = requested
    #
    #         cfg.project_tab.updateNeuroglancer() #0214+ intentionally putting this before dataUpdateWidgets (!)
    #         self.dataUpdateWidgets()


    @Slot()
    def jump_to_layer(self) -> None:
        '''Connected to _jumpToLineedit. Calls jump_to_slider directly.'''
        logger.info('')
        if self._isProjectTab():
            requested = int(self._jumpToLineedit.text())
            if requested in range(len(cfg.data)):
                cfg.data.zpos = requested
                if cfg.project_tab._tabs.currentIndex() == 1:
                    cfg.project_tab.project_table.table.selectRow(requested)
                self._sectionSlider.setValue(requested)



    def jump_to_slider(self):
        # if cfg.data:
        caller = inspect.stack()[1].function
        logger.info(f'jump_to_slider [caller: {caller}] >>>>')
        # if caller in ('dataUpdateWidgets', '_resetSlidersAndJumpInput'): #0323-
        if caller in ('dataUpdateWidgets'):
            return
        if caller in ('main', 'onTimer'):
            requested = self._sectionSlider.value()
            if self._isProjectTab():
                logger.info('Jumping To Section #%d' % requested)
                cfg.data.zpos = requested
                # if not getData('state,manual_mode'):
                #     cfg.emViewer._layer = requested

                for viewer in cfg.project_tab.get_viewers():
                    viewer.set_layer(cfg.data.zpos)

                self.dataUpdateWidgets()

        try:     self._jumpToLineedit.setText(str(requested))
        except:  logger.warning('Current Section Widget Failed to Update')

        logger.info('<<<< jump_to_slider')


    @Slot()
    def reload_scales_combobox(self) -> None:
        if self._isProjectTab():
            logger.info('Reloading Scale Combobox (caller: %s)' % inspect.stack()[1].function)
            self._changeScaleCombo.show()
            self._scales_combobox_switch = 0
            self._changeScaleCombo.clear()
            def pretty_scales():
                lst = []
                for s in cfg.data.scales():
                    siz = cfg.data.image_size(s=s)
                    lst.append('%s %dx%d' % (cfg.data.scale_pretty(s=s), siz[0], siz[1]))
                return lst
            self._changeScaleCombo.addItems(pretty_scales())
            self._changeScaleCombo.setCurrentIndex(cfg.data.scales().index(cfg.data.scale))
            self._scales_combobox_switch = 1
        else:
            self._changeScaleCombo.hide()


    def fn_scales_combobox(self) -> None:
        caller = inspect.stack()[1].function
        logger.info('caller: %s' % caller)
        if caller == 'main':

            if getData('state,manual_mode'):
                self.reload_scales_combobox()
                logger.warning('Exit manual alignment mode before changing scales')
                self.warn('Exit manual alignment mode before changing scales!')
                return

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
                            try:
                                cfg.project_tab.updateProjectLabels()
                            except:
                                pass
                            self.updateEnabledButtons()
                            self.dataUpdateWidgets()
                            self._showSNRcheck()
                            cfg.project_tab.refreshTab()



    def export_afms(self):
        if cfg.project_tab:
            if cfg.data.is_aligned_and_generated():
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
                self.tell('Exported: %s' % file)
                self.tell('AFMs exported successfully.')
            else:
                self.warn('The current scale is not aligned. Nothing to export.')
        else:
            self.warn('There is no project open. Nothing to export.')


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
        if self._isProjectTab():
            if getData('state,manual_mode') == True:
                return
            if self._isProjectTab() or self._isZarrTab():
                logger.info('Creating QWebEngineView...')
                if cfg.emViewer:
                    self.detachedNg = WebPage(url=cfg.emViewer.url())


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

        t0 = time.time()

        initLogFiles()

        # dt = 0.000392913818359375

        self._dontReinit = True
        caller = inspect.stack()[1].function
        # logger.critical('caller: %s' % caller)
        self.tell('Loading project...')
        logger.critical('\n\nLoading project...\n')

        setData('state,manual_mode', False)
        setData('state,mode', 'comparison')
        setData('state,ng_layout', 'xy')

        # dt = 0.0009050369262695312

        # self.combo_mode.setCurrentIndex(1)
        logger.info(f"Setting mode combobox to {self.modeKeyToPretty(getData('state,mode'))}")
        self.combo_mode.setCurrentText(self.modeKeyToPretty(getData('state,mode')))

        # dt = 0.001238107681274414

        self.updateDtWidget() # <.001s

        cfg.data.set_defaults() # 0.5357 -> 0.5438, ~.0081s

        t_ng = time.time()
        cfg.project_tab.initNeuroglancer() # dt = 0.543 -> dt = 0.587 = 0.044 ~ 1/20 second
        logger.info(f't(initialize neuroglancer): {time.time() - t_ng}')
        self.update()

        # cfg.project_tab.updateTreeWidget()  # TimeConsuming dt = 0.001 -> dt = 0.535 ~1/2 second

        self.tell('Updating UI...')
        self.dataUpdateWidgets() # 0.5878 -> 0.5887 ~.001s


        self._changeScaleCombo.setCurrentText(cfg.data.scale)

        self.setControlPanelData() #Added 2023-04-23

        logger.critical('Setting FPS spinbox value...')
        self._fps_spinbox.setValue(cfg.DEFAULT_PLAYBACK_SPEED)
        # cfg.project_tab.updateTreeWidget() #TimeConsuming!! dt = 0.58 - > dt = 1.10

        # dt = 1.1032602787017822
        self.updateEnabledButtons()
        self.updateMenus()
        # dt = 1.1051950454711914
        self._resetSlidersAndJumpInput()
        self.reload_scales_combobox()
        self.enableAllTabs()
        # dt = 1.105268955230713

        cfg.data.zpos = int(len(cfg.data)/2)


        self.updateNotes()
        self._autosave() #0412+
        self.hud.done()
        # cfg.project_tab.project_table.setScaleData()
        self._sectionSlider.setValue(int(len(cfg.data) / 2))
        # self._forceShowControls() #Todo make a decision on this
        self.update()
        self._dontReinit = False

        # dt = 1.1060302257537842





    def saveUserPreferences(self):
        logger.info('')
        userpreferencespath = os.path.join(os.path.expanduser('~'), '.swiftrc')
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
        if cfg.data:
            self.set_status('Saving...')
            self.tell('Saving Project...')
            try:
                self._saveProjectToFile()
                self._unsaved_changes = False
            except:
                self.warn('Unable To Save')
            else:
                self.hud.done()


    def _autosave(self, silently=False):
        if cfg.data:
            if cfg.AUTOSAVE:
                logger.info('Autosaving...')
                try:
                    self._saveProjectToFile(silently=silently)
                except:
                    self._unsaved_changes = True
                    print_exception()


    def _saveProjectToFile(self, saveas=None, silently=False):
        if cfg.data:
            if self._isProjectTab():
                try:
                    cfg.data.basefilenames()
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
                    with open(name, 'w') as f: f.write(proj_json)
                    self.globTabs.setTabText(self.globTabs.currentIndex(), os.path.basename(name))
                    self.statusBar.showMessage('Project Saved!', 3000)
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

    # def import_multiple_images(self):
    #     ''' Import images into data '''
    #     logger.info('>>>> import_multiple_images >>>>')
    #     self.tell('Import Images:')
    #     filenames = natural_sort(import_images_dialog())
    #
    #     if not filenames:
    #         logger.warning('No Images Were Selected')
    #         self.warn('No Images Were Selected')
    #         return 1
    #
    #     cfg.data.set_source_path(os.path.dirname(filenames[0])) #Critical!
    #     self.tell(f'Importing {len(filenames)} Images...')
    #     logger.info(f'Selected Images: \n{filenames}')
    #
    #     try:
    #         for f in filenames:
    #             if f:
    #                 cfg.data.append_image(f)
    #             else:
    #                 cfg.data.append_empty()
    #     except:
    #         print_exception()
    #         self.err('There Was A Problem Importing Selected Files')
    #     else:
    #         self.hud.done()
    #
    #     if len(cfg.data) > 0:
    #         img_size = cfg.data.image_size(s='scale_1')
    #         self.tell(f'Dimensions: {img_size[0]}✕{img_size[1]}')
    #         cfg.data.link_reference_sections()
    #     else:
    #         self.warn('No Images Were Imported')
    #
    #     logger.info('<<<< import_multiple_images <<<<')


    @Slot()
    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent (called by %s):" % inspect.stack()[1].function)
        self.shutdownInstructions()





    def exit_app(self):
        logger.info("Asking user to confirm exit application...")
        style = """
                background-color: #141414;
                color: #ede9e8;
                font-size: 11px;
                font-weight: 600;
                font-family: Tahoma, sans-serif;
                border-color: #339933;
                border-width: 2px;
            """

        dlg = ExitAppDialog()
        dlg.show()

        # fg = self.frameGeometry()
        # logger.critical(f'dlg.width() = {dlg.width()}')
        # logger.critical(f'dlg.height() = {dlg.height()}')
        # # x = (fg.width() / 2) - (dlg.width() / 2)
        # # y = (fg.height() / 2) + (dlg.height() / 2)
        # x = (fg.width()/2)
        # y = (fg.height()/2)
        # dlg.move(x, y)

        if dlg.exec():
            logger.info('User Choice: Exit')
        else:
            logger.info('User Choice: Cancel')
            return

        self.hud('Exiting...')
        if self._unsaved_changes:
            self.tell('Exit AlignEM-SWiFT?')
            message = "There are unsaved changes.\n\nSave before exiting?"
            msg = QMessageBox(QMessageBox.Warning, "Save Changes", message)
            msg.setParent(self)
            msg.show() #Critical - reveals window size

            logger.critical(f'msg.width() = {msg.width()}')
            logger.critical(f'msg.height() = {msg.height()}')
            # msg_width = 640
            # msg_height = 480

            fg = self.frameGeometry()
            # fg = self.geometry()
            # x = (fg.width()/2) #- (msg.width() / 2)
            # x = (fg.width()/3) #- (msg.width() / 2)
            x = (fg.width() - msg.width()) / 2
            y = (fg.height() - msg.height()) / 2
            # # x = (fg.width()/2)
            # # y = (fg.height()/2)
            msg.move(x, y)

            msg.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowCloseButtonHint)
            msg.setStyleSheet(style)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            buttonSave = msg.button(QMessageBox.Save)
            buttonSave.setText('Save && Exit')
            buttonDiscard = msg.button(QMessageBox.Discard)
            buttonDiscard.setText('Exit Without Saving')
            msg.setDefaultButton(QMessageBox.Save)
            # msg.setIcon(QMessageBox.Question)
            # msg.setWindowIcon(qta.icon('fa.question', color='#ede9e8'))
            reply = msg.exec_()
            if reply == QMessageBox.Cancel:
                logger.info('User Choice: Cancel')
                self.tell('Canceling Exit')
                return
            if reply == QMessageBox.Save:
                logger.info('User Choice: Save and Exit')
                self.save()
                self.set_status('Wrapping up...')
                logger.info('Project saved. Exiting')
            if reply == QMessageBox.Discard:
                logger.info('User Choice: Discard Saved Changes')
        else:
            logger.info('No Unsaved Changes - Exiting')

        self.shutdownInstructions()


    def shutdownInstructions(self):
        logger.info('Performing Shutdown Instructions...')

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
                time.sleep(.4)

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
            time.sleep(.4)

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

    def html_resource(self, resource='features.html', title='Features'):

        html_f = os.path.join(self.get_application_root(), 'src', 'resources', resource)
        with open(html_f, 'r') as f:
            html = f.read()

        webengine = QWebEngineView()
        webengine.setFocusPolicy(Qt.StrongFocus)
        webengine.setHtml(html, baseUrl=QUrl.fromLocalFile(os.getcwd()+os.path.sep))
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.globTabs.addTab(webengine, title)
        self._setLastTab()
        self.cpanelFrame.hide()

    def url_resource(self, url, title):
        webengine = QWebEngineView()
        webengine.setFocusPolicy(Qt.StrongFocus)
        webengine.setUrl(QUrl(url))
        webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.globTabs.addTab(webengine, title)
        self._setLastTab()
        self.cpanelFrame.hide()



    def remote_view(self):
        self.tell('Opening Neuroglancer Remote Viewer...')
        browser = WebBrowser()
        browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.globTabs.addTab(browser, 'Neuroglancer')
        self._setLastTab()
        self.cpanelFrame.hide()


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


    def stopNgServer(self):
        # caller = inspect.stack()[1].function
        # logger.critical(caller)
        if ng.is_server_running():
            logger.info('Stopping Neuroglancer...')
            try:    ng.stop()
            except: print_exception()
        else:
            logger.info('Neuroglancer Is Not Running')

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
        if self._isPlayingBack:
            self.automaticPlayTimer.stop()
            self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        elif cfg.project_tab or cfg.zarr_tab:
            # self.automaticPlayTimer.setInterval(1000 / cfg.DEFAULT_PLAYBACK_SPEED)
            self.automaticPlayTimer.start()
            self._btn_automaticPlayTimer.setIcon(qta.icon('fa.pause', color=cfg.ICON_COLOR))
        self._isPlayingBack = not self._isPlayingBack


    def stopPlaybackTimer(self):
        self.automaticPlayTimer.stop()
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        self._isPlayingBack = 0

    def incrementZoomOut(self):
        # logger.info('')
        if getData('state,manual_mode'):
            new_cs_scale = cfg.refViewer.zoom() * 1.1
            logger.info(f'new_cs_scale: {new_cs_scale}')
            cfg.baseViewer.set_zoom(new_cs_scale)
        else:
            new_cs_scale = cfg.emViewer.zoom() * 1.1
            logger.info(f'new_cs_scale: {new_cs_scale}')
            cfg.emViewer.set_zoom(new_cs_scale)

        cfg.project_tab.zoomSlider.setValue( 1 / new_cs_scale )


    def incrementZoomIn(self):
        # logger.info('')
        if getData('state,manual_mode'):
            new_cs_scale = cfg.refViewer.zoom() * 0.9
            logger.info(f'new_cs_scale: {new_cs_scale}')
            cfg.baseViewer.set_zoom(new_cs_scale)
        else:
            new_cs_scale = cfg.emViewer.zoom() * 0.9
            logger.info(f'new_cs_scale: {new_cs_scale}')
            cfg.emViewer.set_zoom(new_cs_scale)
        cfg.project_tab.zoomSlider.setValue( 1 / new_cs_scale )


    def initShortcuts(self):
        logger.info('')
        events = (
            (QKeySequence.MoveToPreviousChar, self.layer_left),
            (QKeySequence.MoveToNextChar, self.layer_right),
            (QKeySequence.MoveToPreviousLine, self.incrementZoomIn),
            (QKeySequence.MoveToNextLine, self.incrementZoomOut),
            # (QKeySequence.MoveToPreviousChar, self.scale_down),
            # (QKeySequence.MoveToNextChar, self.scale_up),
            (Qt.Key_K, self._callbk_skipChanged),
            (Qt.Key_P, self.startStopTimer)
        )
        for event, action in events:
            QShortcut(event, self, action)


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
        self.browser = WebBrowser(self)
        self.browser.setUrl(QUrl('https://get.webgl.org/webgl2/'))
        self.globTabs.addTab(self.browser, 'WebGL Test')
        self._setLastTab()
        self.cpanelFrame.hide()

    def google(self):
        logger.info('Opening Google Tab...')
        self.browser = WebBrowser(self)
        self.browser.setObjectName('web_browser')
        self.browser.setUrl(QUrl('https://www.google.com'))
        self.globTabs.addTab(self.browser, 'Google')
        self._setLastTab()
        self.cpanelFrame.hide()

    def gpu_config(self):
        logger.info('Opening GPU Config...')
        browser = WebBrowser()
        browser.setUrl(QUrl('chrome://gpu'))
        self.globTabs.addTab(browser, 'GPU Configuration')
        self._setLastTab()
        self.cpanelFrame.hide()

    def chromium_debug(self):
        logger.info('Opening Chromium Debugger...')
        browser = WebBrowser()
        browser.setUrl(QUrl('http://127.0.0.1:9000'))
        self.globTabs.addTab(browser, 'Debug Chromium')
        self._setLastTab()
        self.cpanelFrame.hide()

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
        if caller != 'dataUpdateWidgets':
            # self._bbToggle.setEnabled(state)
            if cfg.project_tab:
                if state:
                    self.tell('Bounding Box is ON. Warning: Output dimensions may grow larger than source.')
                    cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = True
                else:
                    self.tell('Bounding Box is OFF. Output dimensions will match source.')
                    cfg.data['data']['scales'][cfg.data['data']['current_scale']]['use_bounding_rect'] = False


    def _callbk_skipChanged(self, state:int):  # 'state' is connected to skipped toggle
        '''Callback Function for Skip Image Toggle'''
        caller = inspect.stack()[1].function
        if self._isProjectTab():
            if caller != 'dataUpdateWidgets':
                skip_state = not self._skipCheckbox.isChecked()
                for s in cfg.data.scales():
                    layer = cfg.data.zpos
                    if layer < len(cfg.data):
                        cfg.data.set_skip(skip_state, s=s, l=layer)
                    else:
                        logger.warning(f'Request layer is out of range ({layer}) - Returning')
                        return
                if skip_state:
                    self.tell("Include: %s" % cfg.data.name_base())
                else:
                    self.tell("Exclude: %s" % cfg.data.name_base())
                cfg.data.link_reference_sections()
                self.dataUpdateWidgets()
                if cfg.project_tab._tabs.currentIndex() == 1:
                    cfg.project_tab.project_table.setScaleData()
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
                if not getData('state,manual_mode'):
                    if not cfg.data.is_aligned_and_generated():
                        logger.warning('Cannot enter manual alignment mode until the series is aligned.')
                        self.warn('Align the series first and then use Manual Alignment.')
                        return
                    self.enter_man_mode()
                else:
                    self.exit_man_mode()

    def enter_man_mode(self):
        if self._isProjectTab():
            if cfg.data.is_aligned_and_generated():
                logger.info('\n\nEnter Manual Alignment Mode >>>>\n')
                self.tell('Entering Manual Align Mode...')
                # for v in cfg.project_tab.get_viewers():
                #     try:
                #         v = None
                #     except:
                #         logger.warning(f'Unable to delete viewer: {str(v)}')

                # self.combo_mode.setCurrentIndex(2)
                setData('state,previous_mode', getData('state,mode'))
                setData('state,mode', 'manual_align')
                setData('state,manual_mode', True)
                # cfg.project_tab.cpanelFrame.hide()

                self.combo_mode.setCurrentText(self.modeKeyToPretty(getData('state,mode')))
                self.stopPlaybackTimer()
                self.setWindowTitle(self.window_title + ' - Manual Alignment Mode')
                self.alignMatchPointAction.setText('Exit Manual Align Mode')
                self.matchpoint_text_snr.setText(cfg.data.snr_report())
                self.mp_marker_lineweight_spinbox.setValue(getOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT'))
                self.mp_marker_size_spinbox.setValue(getOpt('neuroglancer,MATCHPOINT_MARKER_SIZE'))

                self._changeScaleCombo.setEnabled(False)

                cfg.project_tab.onEnterManualMode()

            else:
                self.warn('Alignment must be generated before using Manual Point Alignment method.')

    def exit_man_mode(self):

        if self._isProjectTab():
            logger.critical('exit_man_mode >>>>')
            self.tell('Exiting Manual Align Mode...')

            # try:
            #     cfg.refViewer = None
            #     cfg.baseViewer = None
            #     cfg.stageViewer = None
            # except:
            #     print_exception()

            self.setWindowTitle(self.window_title)
            prev_mode = getData('state,previous_mode')

            if prev_mode == 'stack-xy':
                setData('state,mode', 'stack-xy')
                setData('state,ng_layout', 'xy')

                self.combo_mode.setCurrentIndex(0)
            elif prev_mode == 'stack-4panel':
                setData('state,mode', 'stack-4panel')
                setData('state,ng_layout', '4panel')

            else:
                setData('state,mode', 'comparison')
                setData('state,ng_layout', 'xy')

            self.combo_mode.setCurrentText(self.modeKeyToPretty(getData('state,mode')))

            # cfg.project_tab.cpanelFrame.show()

            setData('state,manual_mode', False)
            self.alignMatchPointAction.setText('Align Manually')
            self._changeScaleCombo.setEnabled(True)
            self.dataUpdateWidgets()
            self.updateCorrSignalsDrawer() #Caution - Likely Redundant!
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
            QApplication.processEvents() #Critical! - enables viewer to acquire appropriate zoom

            # self._changeScaleCombo.setEnabled(True)

            cfg.project_tab.initNeuroglancer()
            cfg.emViewer.set_layer(cfg.data.zpos)
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
        if self._dev_console.isHidden():
            self._dev_console.show()
        else:
            self._dev_console.hide()


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
        elif key == 'comparison':
            return 'Comparison View'
        elif key == 'manual_align':
            return 'Manual Align Mode'

    def prettyToModeKey(self, key):
        if key == 'Stack View (xy plane)':
            return 'stack-xy'
        elif key == 'Stack View (4 panel)':
            return 'stack-4panel'
        elif key == 'Comparison View':
            return 'comparison'
        elif key == 'Manual Align Mode':
            return 'manual_align'


    def onComboModeChange(self):
        caller = inspect.stack()[1].function

        if self._isProjectTab():
            # if cfg.project_tab._tabs.currentIndex() == 0:
            if caller == 'main':
                logger.info('')
                # index = self.combo_mode.currentIndex()
                curText = self.combo_mode.currentText()
                if curText == 'Manual Align Mode':
                    if not cfg.data.is_aligned():
                        self.warn('Align the series first and then use Manual Alignment.')
                        self.combo_mode.setCurrentText(self.modeKeyToPretty(getData('state,mode')))
                        return
                requested_key = self.prettyToModeKey(curText)
                logger.info(f'Requested key: {requested_key}')
                if getData('state,mode') == 'manual_align':
                    if requested_key != 'manual_align':
                        self.exit_man_mode()
                setData('state,previous_mode', getData('state,mode'))
                setData('state,mode', requested_key)
                if requested_key == 'stack-4panel':
                    setData('state,ng_layout', '4panel')
                elif requested_key == 'stack-xy':
                    setData('state,ng_layout', 'xy')
                elif requested_key == 'comparison':
                    setData('state,ng_layout', 'xy')
                elif requested_key == 'manual_align':
                    setData('state,ng_layout', 'xy')
                    self.enter_man_mode()
                self.dataUpdateWidgets()
                cfg.project_tab.comboNgLayout.setCurrentText(getData('state,ng_layout'))
                cfg.project_tab.initNeuroglancer()

            # cfg.project_tab.updateCursor()
        else:
            self.combo_mode.setCurrentText(self.modeKeyToPretty('comparison'))




    def initToolbar(self):
        logger.info('')

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(18,18))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # self.toolbar.setFixedHeight(32)
        self.toolbar.setFixedHeight(20)
        self.toolbar.setObjectName('toolbar')
        self.addToolBar(self.toolbar)

        # self._btn_refreshTab = QPushButton(' Refresh')
        self._btn_refreshTab = QPushButton()
        self._btn_refreshTab.setToolTip("Refresh View (" + ('^','⌘')[is_mac()] + "R)")
        self._btn_refreshTab.setStyleSheet('font-size: 12px;')
        # self._btn_refreshTab.setFixedSize(68,18)
        self._btn_refreshTab.setFixedSize(18,18)
        self._btn_refreshTab.setIcon(qta.icon('ei.refresh', color=cfg.ICON_COLOR))
        self._btn_refreshTab.setIconSize(QSize(14, 14))
        self._btn_refreshTab.clicked.connect(self.refreshTab)
        self._btn_refreshTab.setStatusTip('Refresh')

        self.combo_mode = QComboBox(self)
        self.combo_mode.setStyleSheet('font-size: 11px; font-weight: 600;')
        self.combo_mode.setFixedSize(150, 18)
        self.combo_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        items = ['Stack View (4 panel)', 'Stack View (xy plane)', 'Comparison View', 'Manual Align Mode']
        self.combo_mode.addItems(items)
        self.combo_mode.currentTextChanged.connect(self.onComboModeChange)

        self._sectionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self._sectionSlider.setMinimumWidth(140)
        self._sectionSlider.setFocusPolicy(Qt.StrongFocus)
        self._sectionSlider.valueChanged.connect(self.jump_to_slider)

        tip = 'Show Neuroglancer key bindings'
        self.info_button_buffer_label = QLabel(' ')

        '''section # / jump-to lineedit'''
        self._jumpToLineedit = QLineEdit(self)
        self._jumpToLineedit.setStyleSheet('font-size: 11px; border-width: 0px;')
        self._jumpToLineedit.setFocusPolicy(Qt.ClickFocus)
        self._jumpToLineedit.setStatusTip(tip)
        self._jumpToLineedit.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._jumpToLineedit.setFixedSize(QSize(36, 16))
        self._jumpToLineedit.returnPressed.connect(self.jump_to_layer)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        sec_label = QLabel('Section: ')
        hbl.addWidget(sec_label, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._jumpToLineedit)
        self._jumpToSectionWidget = QWidget()
        self._jumpToSectionWidget.setStyleSheet('border-radius: 4px;')
        self._jumpToSectionWidget.setLayout(hbl)
        # self.toolbar.addWidget(self._sectionSlider)

        self._btn_automaticPlayTimer = QPushButton()
        self._btn_automaticPlayTimer.setIconSize(QSize(14,14))
        self._btn_automaticPlayTimer.setFixedSize(18,18)
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        self.automaticPlayTimer = QTimer(self)
        self._btn_automaticPlayTimer.clicked.connect(self.startStopTimer)

        def onTimer():
            logger.info('')
            self.automaticPlayTimer.setInterval(1000 / self._fps_spinbox.value())
            if cfg.data:
                if cfg.project_tab:
                    if self._sectionSlider.value() < len(cfg.data) - 1:
                        self._sectionSlider.setValue(self._sectionSlider.value() + 1)
                    else:
                        self._sectionSlider.setValue(0)
                        self.automaticPlayTimer.stop()
                        self._isPlayingBack = 0
                        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))

        self.automaticPlayTimer.timeout.connect(onTimer)
        self._sectionSliderWidget = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4,0,4,0)
        hbl.addWidget(self._btn_automaticPlayTimer, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._sectionSlider, alignment=Qt.AlignmentFlag.AlignLeft)
        self._sectionSliderWidget.setLayout(hbl)

        lab = QLabel('Speed:')
        self._fps_spinbox = QDoubleSpinBox()
        self._fps_spinbox.setStyleSheet('font-size: 11px')
        # self._fps_spinbox.setStyleSheet('font-size: 11px')
        self._fps_spinbox.setFixedHeight(18)
        self._fps_spinbox.setMinimum(.5)
        self._fps_spinbox.setMaximum(10)
        self._fps_spinbox.setSingleStep(.2)
        self._fps_spinbox.setDecimals(1)
        self._fps_spinbox.setSuffix('fps')
        self._fps_spinbox.setStatusTip('Playback Speed (frames/second)')
        self._fps_spinbox.clear()

        '''scale combobox'''
        self._changeScaleCombo = QComboBox(self)
        self._changeScaleCombo.setMinimumWidth(134)
        self._changeScaleCombo.setFixedHeight(16)
        self._changeScaleCombo.setStyleSheet('font-size: 11px; font-weight: 600;')
        self._changeScaleCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self._changeScaleCombo.setFixedSize(QSize(160, 20))

        self._changeScaleCombo.currentTextChanged.connect(self.fn_scales_combobox)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self._changeScaleCombo, alignment=Qt.AlignmentFlag.AlignRight)
        self._changeScaleWidget = QWidget()
        self._changeScaleWidget.setLayout(hbl)

        self.controlsButton = QPushButton()
        # self.controlsButton.setText(('Controls', 'Hide')[self.cpanelFrame.isVisible()])
        self.controlsButton.setText('Controls')
        self.controlsButton.setStatusTip('Show Controls')
        self.controlsButton.setFixedHeight(18)
        self.controlsButton.setFixedWidth(70)
        self.controlsButton.setIcon(qta.icon('ei.adjust-alt', color=ICON_COLOR))
        self.controlsButton.clicked.connect(self._callbk_showHideControls)


        self.notesButton = QPushButton('Notes')
        self.notesButton.setStatusTip('Show Notepad')
        self.notesButton.setFixedHeight(18)
        self.notesButton.setFixedWidth(70)
        self.notesButton.setIcon(qta.icon('mdi.notebook-edit', color=ICON_COLOR))
        self.notesButton.clicked.connect(self._callbk_showHideNotes)


        self.pythonButton = QPushButton('Python')
        self.pythonButton.setStatusTip('Show Python Console')
        self.pythonButton.setFixedHeight(18)
        self.pythonButton.setFixedWidth(70)
        self.pythonButton.setIcon(qta.icon('mdi.language-python', color=ICON_COLOR))
        self.pythonButton.clicked.connect(self._callbk_showHidePython)

        self._detachNgButton = QPushButton()
        self._detachNgButton.setFixedSize(18,18)
        self._detachNgButton.setIcon(qta.icon("fa.external-link-square", color=ICON_COLOR))
        self._detachNgButton.clicked.connect(self.update_ng)
        self._detachNgButton.setStatusTip('Detach Neuroglancer (pop-out into a separate window)')


        def fn():
            if self._isProjectTab():
                for v in cfg.project_tab.get_viewers():
                    v.set_zmag()
        self._fixAllZmag = QPushButton()
        self._fixAllZmag.setStatusTip('Fix Z-mag')
        self._fixAllZmag.setFixedSize(18, 18)
        self._fixAllZmag.setIcon(qta.icon("mdi.auto-fix", color=ICON_COLOR))
        self._fixAllZmag.clicked.connect(fn)


        # self.toolbar.addWidget(QLabel(' '))
        self.toolbar.addWidget(self._btn_refreshTab)
        self.toolbar.addWidget(QLabel(' '))
        self.toolbar.addWidget(self.combo_mode)
        # self.toolbar.addWidget(self._al_unal_label_widget)
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(w)
        # self.toolbar.addWidget(self._btn_refreshTab)
        self.toolbar.addWidget(self._jumpToSectionWidget)
        self.toolbar.addWidget(self._sectionSliderWidget)
        self.toolbar.addWidget(self._fps_spinbox)
        self.toolbar.addWidget(self._changeScaleWidget)

        # if cfg.DEV_MODE:
        #     self.toolbar.addWidget(self.profilingTimerButton)
        # self.toolbar.addWidget(self.controlsButton)
        self.toolbar.addWidget(self.notesButton)
        self.toolbar.addWidget(self.pythonButton)
        # self.toolbar.addWidget(self._highContrastNgAction)
        self.toolbar.addWidget(self._fixAllZmag)
        self.toolbar.addWidget(self._detachNgButton)
        self.toolbar.addWidget(self.info_button_buffer_label)


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
            for i in range(0,4):
                cfg.project_tab._tabs.setTabEnabled(i, True)
        # self._btn_refreshTab.setEnabled(True)


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
                projects.append(cfg.main_window.globTabs.widget(i).datamodel.dest())
        return projects


    def isProjectOpen(self, name):
        return os.path.splitext(name)[0] in [os.path.splitext(x)[0] for x in self.getOpenProjects()]


    def getProjectIndex(self, search):
        for i in range(self.globTabs.count()):
            if 'ProjectTab' in str(self.globTabs.widget(i)):
                if cfg.main_window.globTabs.widget(i).datamodel.dest() == os.path.splitext(search)[0]:
                    return i


    def getCurrentTabWidget(self):
        return self.globTabs.currentWidget()


    def _getTabObject(self):
        return self.globTabs.currentWidget()


    def _onGlobTabChange(self):


        # if self._dontReinit == True:
        #     logger.critical('\n\n\n<<<<< DONT REINIT! >>>>>\n\n\n')
        #     return

        caller = inspect.stack()[1].function
        logger.info('caller: %s' %caller)
        if caller not in ('onStartProject', '_setLastTab'):
            self.shutdownNeuroglancer() #0329+

        tabtype = self._getTabType()
        if tabtype == 'ProjectTab':
            logger.critical('Loading Project Tab...')
            self.cpanelFrame.show()
            self.statusBar.setStyleSheet("""
                    font-size: 10px; font-weight: 600;
                    color: #ede9e8; background-color: #222222;
                    margin: 0px; padding: 0px;
                    """)
        else:
            self.statusBar.setStyleSheet("""
                    font-size: 10px; font-weight: 600;
                    color: #141414; background-color: #ede9e8;
                    margin: 0px; padding: 0px;
                    """)

        # if caller  == '_setLastTab':
        #     logger.critical('\n\n<<<<< DONT REINIT (caller = _setLastTab)! >>>>>\n')
        #     return

        cfg.project_tab = None
        cfg.zarr_tab = None
        self.globTabs.show() #nec?
        self.enableAllTabs()  #Critical - Necessary for case of glob tab closure during disabled state for MA Mode
        self.stopPlaybackTimer()
        self._changeScaleCombo.clear()
        self._changeScaleCombo.setEnabled(True) #needed for disable on MA
        # self.clearCorrSpotsDrawer()
        QApplication.restoreOverrideCursor()

        self._splitter.hide() #0424-


        # self.newMainSplitter.setStyleSheet("""QSplitter::handle { background: none; }""")

        if tabtype == 'OpenProject':
            configure_project_paths()
            self._getTabObject().user_projects.set_data()
            self.cpanelFrame.hide()
            self.correlation_signals.hide()


        elif tabtype == 'ProjectTab':
            logger.critical('Loading Project Tab...')
            self.cpanelFrame.show()
            cfg.data = self.globTabs.currentWidget().datamodel
            cfg.project_tab = cfg.pt = self.globTabs.currentWidget()
            cfg.zarr_tab = None
            self._lastRefresh = 0
            self.statusBar.setStyleSheet("""
                    font-size: 10px;
                    font-weight: 600;
                    color: #f3f6fb;
                    background-color: #222222;
                    margin: 0px;
                    padding: 0px;
                    """)
            logger.info(f"Setting mode combobox to {self.modeKeyToPretty(getData('state,mode'))}")
            self.combo_mode.setCurrentText(self.modeKeyToPretty(getData('state,mode')))
            # self.set_nglayout_combo_text(layout=cfg.data['state']['mode'])  # must be before initNeuroglancer
            self.dataUpdateWidgets()
            self._bbToggle.setChecked(cfg.data.use_bb()) #0309+
            # cfg.project_tab.refreshTab() #Todo - Refactor!!!!! may init neuroglancer twice.

            self.setControlPanelData()

            if not getData('state,manual_mode'):
                cfg.project_tab.showSecondaryNgTools()
            elif getData('state,manual_mode'):
                cfg.project_tab.hideSecondaryNgTools()

            logger.info('Setting global viewer reference...')
            cfg.emViewer = cfg.project_tab.viewer
            # cfg.project_tab.initNeuroglancer()

            try:
                cfg.project_tab.signalsAction.setChecked(False)
            except:
                logger.warning('Cant deactivate signalsAction QAction')

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
        cfg.data.set_paths_absolute(filename=filename) #+
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
        self._saveProjectToFile()

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
                textedit.setFixedSize(QSize(600,600))
                textedit.setReadOnly(True)
                textedit.setText(body)
                action = QWidgetAction(self)
                action.setDefaultWidget(textedit)
                menu.addAction(action)

            if self._isProjectTab():
                if cfg.unal_tensor:
                    # logger.info('Adding Raw Series tensor to menu...')
                    txt = json.dumps(cfg.unal_tensor.spec().to_json(), indent=2)
                    addTensorMenuInfo(label='Raw Series', body=txt)
                if cfg.data.is_aligned():
                    if cfg.al_tensor:
                        # logger.info('Adding Aligned Series tensor to menu...')
                        txt = json.dumps(cfg.al_tensor.spec().to_json(), indent=2)
                        addTensorMenuInfo(label='Aligned Series', body=txt)
            if self._isZarrTab():
                txt = json.dumps(cfg.tensor.spec().to_json(), indent=2)
                addTensorMenuInfo(label='Zarr Series', body=txt)

            self.updateNgMenuStateWidgets()
        else:
            self.clearNgStateMenus()


    def clearTensorMenu(self):
        self.tensorMenu.clear()
        textedit = QTextEdit(self)
        textedit.setFixedSize(QSize(50,28))
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


    # def fn_ngShowHideUiControls(self):
    #     logger.info('')
    #     if self._isProjectTab():
    #         setOpt('neuroglancer,SHOW_UI_CONTROLS', self.ngShowUiControlsAction.isChecked())
    #         cfg.project_tab.spreadW.setVisible(getOpt('neuroglancer,SHOW_UI_CONTROLS'))
    #         cfg.project_tab.updateUISpacing()
    #         self.ngShowUiControlsAction.setText(
    #             ('Show NG UI Controls', 'Hide NG UI Controls')[self.ngShowUiControlsAction.isChecked()])
    #         self.initAllViewers()


    def initAllViewers(self):
        if self._isProjectTab():
            for v in cfg.project_tab.get_viewers():
                v.initViewer()


    def initMenu(self):
        '''Initialize Menu'''
        logger.info('')
        #
        # self.scManualAlign = QShortcut(QKeySequence('Ctrl+M'), self)
        # self.scManualAlign.activated.connect(self.enterExitManAlignMode)

        self.action_groups = {}
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(True)  # Fix for non-native menubar on macOS

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
        self.openAction.setShortcut('Ctrl+O')
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
        self.addAction(self.saveAction)
        fileMenu.addAction(self.saveAction)

        self.savePreferencesAction = QAction('Save User Preferences', self)
        self.savePreferencesAction.triggered.connect(self.saveUserPreferences)
        fileMenu.addAction(self.savePreferencesAction)

        self.resetPreferencesAction = QAction('Set Default Preferences', self)
        self.resetPreferencesAction.triggered.connect(self.resetUserPreferences)
        fileMenu.addAction(self.resetPreferencesAction)

        self.refreshAction = QAction('&Refresh', self)
        self.refreshAction.triggered.connect(self.refreshTab)
        self.refreshAction.setShortcut('Ctrl+R')
        self.addAction(self.refreshAction)
        fileMenu.addAction(self.refreshAction)

        self.showPythonAction = QAction('Show &Python', self)
        self.showPythonAction.triggered.connect(self._callbk_showHidePython)
        self.showPythonAction.setShortcut('Ctrl+P')
        fileMenu.addAction(self.showPythonAction)


        def fn():
            self.globTabs.removeTab(self.globTabs.currentIndex())
        self.closeTabAction = QAction('Close Tab', self)
        self.closeTabAction.triggered.connect(fn)
        self.closeTabAction.setShortcut('Ctrl+W')
        self.addAction(self.closeTabAction)
        fileMenu.addAction(self.closeTabAction)

        self.exitAppAction = QAction('&Quit', self)
        self.exitAppAction.triggered.connect(self.exit_app)
        self.exitAppAction.setShortcut('Ctrl+Q')
        self.addAction(self.exitAppAction)
        fileMenu.addAction(self.exitAppAction)


        viewMenu = self.menu.addMenu("View")



        self.ngShowAxisLinesAction = QAction(self)
        def fn():
            if self._isProjectTab():
                opt = self.ngShowAxisLinesAction.isChecked()
                setOpt('neuroglancer,SHOW_AXIS_LINES', opt)
                # self.ngShowAxisLinesAction.setText(('Show Axis Lines', 'Hide Axis Lines')[opt])
                # for v in self.get_viewers():
                #     v.updateAxisLines()
                if cfg.emViewer:
                    cfg.emViewer.updateAxisLines()
        self.ngShowAxisLinesAction.triggered.connect(fn)
        self.ngShowAxisLinesAction.setCheckable(True)
        self.ngShowAxisLinesAction.setChecked(getOpt('neuroglancer,SHOW_AXIS_LINES'))
        # self.ngShowAxisLinesAction.setText(('Show Axis Lines', 'Hide Axis Lines')[getOpt('neuroglancer,SHOW_AXIS_LINES')])
        self.ngShowAxisLinesAction.setText('Axis Lines')
        viewMenu.addAction(self.ngShowAxisLinesAction)

        self.ngShowScaleBarAction = QAction(self)
        def fn():
            if self._isProjectTab():
                opt = self.ngShowScaleBarAction.isChecked()
                setOpt('neuroglancer,SHOW_SCALE_BAR', opt)
                # self.ngShowScaleBarAction.setText(('Show Scale Bar', 'Hide Scale Bar')[opt])
                # for v in self.get_viewers():
                #     v.updateScaleBar()
                if cfg.emViewer:
                    cfg.emViewer.updateScaleBar()
        self.ngShowScaleBarAction.setCheckable(True)
        self.ngShowScaleBarAction.setChecked(getOpt('neuroglancer,SHOW_SCALE_BAR'))
        # self.ngShowScaleBarAction.setText(('Show Scale Bar', 'Hide Scale Bar')[getOpt('neuroglancer,SHOW_SCALE_BAR')])
        self.ngShowScaleBarAction.setText('Scale Bar')
        self.ngShowScaleBarAction.triggered.connect(fn)
        viewMenu.addAction(self.ngShowScaleBarAction)


        self.ngShowUiControlsAction = QAction(self)
        def fn():
            if self._isProjectTab():
                opt = self.ngShowUiControlsAction.isChecked()
                setOpt('neuroglancer,SHOW_UI_CONTROLS', opt)
                cfg.project_tab.spreadW.setVisible(getOpt('neuroglancer,SHOW_UI_CONTROLS'))
                cfg.project_tab.updateUISpacing()
                # self.ngShowUiControlsAction.setText(('Show NG UI Controls', 'Hide NG UI Controls')[opt])
                # self.initAllViewers()
                if cfg.emViewer:
                    cfg.emViewer.updateUIControls()
        self.ngShowUiControlsAction.triggered.connect(fn)
        self.ngShowUiControlsAction.setCheckable(True)
        self.ngShowUiControlsAction.setChecked(getOpt('neuroglancer,SHOW_UI_CONTROLS'))
        # self.ngShowUiControlsAction.setText(('Show NG UI Controls', 'Hide NG UI Controls')[getOpt('neuroglancer,SHOW_UI_CONTROLS')])
        self.ngShowUiControlsAction.setText('NG UI Controls')
        viewMenu.addAction(self.ngShowUiControlsAction)

        self.ngShowYellowFrameAction = QAction(self)
        def fn():
            if self._isProjectTab():
                opt = self.ngShowYellowFrameAction.isChecked()
                setOpt('neuroglancer,SHOW_YELLOW_FRAME', opt)
                # self.ngShowYellowFrameAction.setText(('Show Boundary', 'Hide Boundary')[opt])
                if cfg.emViewer:
                    cfg.emViewer.updateDefaultAnnotations()
        self.ngShowYellowFrameAction.setCheckable(True)
        self.ngShowYellowFrameAction.setChecked(getOpt('neuroglancer,SHOW_YELLOW_FRAME'))
        # self.ngShowYellowFrameAction.setText(('Show Boundary', 'Hide Boundary')[getOpt('neuroglancer,SHOW_YELLOW_FRAME')])
        self.ngShowYellowFrameAction.setText('Boundary')
        self.ngShowYellowFrameAction.triggered.connect(fn)
        viewMenu.addAction(self.ngShowYellowFrameAction)
        
        
        
        self.toggleCorrSigsAction = QAction(self)
        def fn():
            if self._isProjectTab():
                cfg.project_tab.signalsAction.toggle()
                self._callbk_showHideCorrSpots()
        # self.toggleCorrSpotsAction.setCheckable(True)
        # self.toggleCorrSpotsAction.setChecked(getOpt('neuroglancer,SHOW_YELLOW_FRAME'))
        # self.ngShowYellowFrameAction.setText(('Show Boundary', 'Hide Boundary')[getOpt('neuroglancer,SHOW_YELLOW_FRAME')])
        self.toggleCorrSigsAction.setText('Toggle Correlation Signals')
        # self.toggleCorrSigsAction.triggered.connect(fn)
        self.toggleCorrSigsAction.triggered.connect(fn)
        viewMenu.addAction(self.toggleCorrSigsAction)

        maViewMenu = viewMenu.addMenu('Manual Align Mode')

        self.maShowSwimWindowAction = QAction('Show SWIM Window', self)
        self.maShowSwimWindowAction.setCheckable(True)
        self.maShowSwimWindowAction.setChecked(getOpt('neuroglancer,SHOW_SWIM_WINDOW'))
        # self.maShowSwimWindowAction.setText(('Show Boundary', 'Hide Boundary')[getOpt('neuroglancer,SHOW_SWIM_WINDOW')])
        self.maShowSwimWindowAction.triggered.connect(lambda val: setOpt('neuroglancer,SHOW_SWIM_WINDOW', val))
        def fn():
            if self._isProjectTab():
                if getData('state,manual_mode'):
                    if not getOpt('neuroglancer,SHOW_SWIM_WINDOW'):
                        cfg.refViewer.undrawSWIMwindows()
                        cfg.baseViewer.undrawSWIMwindows()
                    else:
                        cfg.refViewer.drawSWIMwindow()
                        cfg.baseViewer.drawSWIMwindow()
        self.maShowSwimWindowAction.triggered.connect(fn)
        maViewMenu.addAction(self.maShowSwimWindowAction)

        # self.showCorrSpotsAction = QAction('Show Correlation Signals', self)
        # self.showCorrSpotsAction.setCheckable(True)
        # self.showCorrSpotsAction.setChecked(getOpt('ui,SHOW_CORR_SPOTS'))
        # self.showCorrSpotsAction.triggered.connect(lambda val: setOpt('ui,SHOW_CORR_SPOTS', val))
        # self.showCorrSpotsAction.triggered.connect(self.update_displayed_controls)
        # viewMenu.addAction(self.showCorrSpotsAction)

        # self.ngShowPanelBordersAction = QAction('Show Ng Panel Borders', self)
        # self.ngShowPanelBordersAction.setCheckable(True)
        # self.ngShowPanelBordersAction.setChecked(getOpt('neuroglancer,SHOW_PANEL_BORDERS'))
        # self.ngShowPanelBordersAction.triggered.connect(lambda val: setOpt('neuroglancer,SHOW_PANEL_BORDERS', val))
        # self.ngShowPanelBordersAction.triggered.connect(self.update_ng)
        # ngMenu.addAction(self.ngShowPanelBordersAction)

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

        self.alignAllAction = QAction('Align All', self)
        self.alignAllAction.triggered.connect(self.alignAll)
        self.alignAllAction.setShortcut('Ctrl+A')
        alignMenu.addAction(self.alignAllAction)

        self.alignOneAction = QAction('Align + Generate One', self)
        self.alignOneAction.triggered.connect(self.alignGenerateOne)
        alignMenu.addAction(self.alignOneAction)

        self.alignMatchPointAction = QAction('Align Manually', self)
        self.alignMatchPointAction.triggered.connect(self.enterExitManAlignMode)
        self.alignMatchPointAction.setShortcut('Ctrl+M')
        alignMenu.addAction(self.alignMatchPointAction)
        # self.addAction(self.alignMatchPointAction)

        self.skipChangeAction = QAction('Toggle Skip', self)
        self.skipChangeAction.triggered.connect(self.skip_change_shortcut)
        self.skipChangeAction.setShortcut('Ctrl+K')
        self.addAction(self.skipChangeAction)
        alignMenu.addAction(self.skipChangeAction)

        self.showMatchpointsAction = QAction('Show Matchpoints', self)
        self.showMatchpointsAction.triggered.connect(self.show_all_matchpoints)
        alignMenu.addAction(self.showMatchpointsAction)

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

        self.ngStateMenu = ngMenu.addMenu('JSON State') #get_ng_state
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
        ngPerspectiveMenu.addAction(self.ngLayout1Action)
        ngPerspectiveMenu.addAction(self.ngLayout2Action)
        ngPerspectiveMenu.addAction(self.ngLayout3Action)
        ngPerspectiveMenu.addAction(self.ngLayout4Action)
        ngPerspectiveMenu.addAction(self.ngLayout5Action)
        ngPerspectiveMenu.addAction(self.ngLayout6Action)
        # ngPerspectiveMenu.addAction(self.ngLayout7Action)
        ngPerspectiveMenu.addAction(self.ngLayout8Action)
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

        self.rechunkAction = QAction('Rechunk...', self)
        self.rechunkAction.triggered.connect(self.rechunk)
        actionsMenu.addAction(self.rechunkAction)


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

        # self.initViewAction = QAction('Fix View', self)
        # self.initViewAction.triggered.connect(self.initView)
        # debugMenu.addAction(self.initViewAction)

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

        helpMenu = self.menu.addMenu('Help')

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
            lambda: self.url_resource(url="https://github.com/mcellteam/swift-ir/blob/development_ng/docs/user/command_line/examples/README.md", title='CLI Examples'))
        helpMenu.addAction(action)

        self.featuresAction = QAction('AlignEM-SWiFT Features', self)
        self.featuresAction.triggered.connect(lambda: self.html_resource(resource='features.html', title='Help: Features'))
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

        action = QAction('Remod Help', self)
        action.triggered.connect(lambda: self.html_resource(resource='remod.html', title='Help: Remod (beta)'))
        helpMenu.addAction(action)

        self.documentationAction = QAction('GitHub', self)
        action.triggered.connect(lambda: self.url_resource(url='https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md', title='Source Code (GitHub)'))
        helpMenu.addAction(self.documentationAction)


        researchGroupMenu = helpMenu.addMenu('Our Research Groups')

        action = QAction('CNL @ Salk', self)
        action.triggered.connect(lambda: self.url_resource(url='https://cnl.salk.edu/', title='Web: CNL'))
        researchGroupMenu.addAction(action)

        action = QAction('Texas Advanced Computing Center', self)
        action.triggered.connect(lambda: self.url_resource(url='https://3dem.org/workbench', title='Web: TACC'))
        researchGroupMenu.addAction(action)

        action = QAction('UTexas @ Austin', self)
        action.triggered.connect(lambda: self.url_resource(url='https://synapseweb.clm.utexas.edu/harrislab', title='Web: UTexas'))
        researchGroupMenu.addAction(action)

        action = QAction('MMBIoS (UPitt)', self)
        action.triggered.connect(lambda: self.url_resource(url='https://mmbios.pitt.edu/', title='Web: MMBioS'))
        researchGroupMenu.addAction(action)

        action = QAction('MCell4 Pre-print', self)
        action.triggered.connect(
            lambda: self.html_resource(resource="mcell4-preprint.html", title='MCell4 Pre-print (2023)'))
        researchGroupMenu.addAction(action)

        # self.googleAction = QAction('Google', self)
        # self.googleAction.triggered.connect(self.google)
        # helpMenu.addAction(self.googleAction)

        action = QAction('Google', self)
        action.triggered.connect(lambda: self.url_resource(url='https://www.google.com', title='Google'))
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
    #         cfg.data.set_swim_window_px(self._swimWindowControl.value())

    def _valueChangedWhitening(self):
        # logger.info('')
        caller = inspect.stack()[1].function
        # if caller != 'initControlPanel':
        if caller == 'main':
            cfg.data.set_whitening(float(self._whiteningControl.value()))


    def _valueChangedPolyOrder(self):
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if self._polyBiasCombo.currentText() == 'None':
                cfg.data.set_use_poly_order(False)
            else:
                cfg.data.set_use_poly_order(True)
                cfg.data.set_poly_order(self._polyBiasCombo.currentText())


    def _toggledAutogenerate(self) -> None:
        # logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if self._toggleAutogenerate.isChecked():
                self.tell('Images will be generated automatically after alignment')
            else:
                self.tell('Images will not be generated automatically after alignment')


    def rechunk(self):
        if self._isProjectTab():
            if cfg.data.is_aligned_and_generated():
                target = os.path.join(cfg.data.dest(), 'img_aligned.zarr', 's%d' % cfg.data.scale_val())
                _src = os.path.join(cfg.data.dest(), 'img_aligned.zarr', '_s%d' % cfg.data.scale_val())
            else:
                target = os.path.join(cfg.data.dest(), 'img_src.zarr', 's%d' % cfg.data.scale_val())
                _src = os.path.join(cfg.data.dest(), 'img_src.zarr', '_s%d' % cfg.data.scale_val())

            dlg = RechunkDialog(self, target=target)
            if dlg.exec():

                t_start = time.time()

                logger.info('Rechunking...')
                chunkshape = cfg.data['data']['chunkshape']
                intermediate = "intermediate.zarr"

                os.rename(target, _src)
                try:
                    source = zarr.open(store=_src)
                    self.tell('Configuring rechunking (target: %s). New chunk shape: %s...' % (target, str(chunkshape)))
                    logger.info('Configuring rechunk operation (target: %s)...' % target)
                    rechunked = rechunk(
                        source=source,
                        target_chunks=chunkshape,
                        target_store=target,
                        max_mem=100_000_000_000,
                        temp_store=intermediate
                    )
                    self.tell('Rechunk plan:\n%s' % str(rechunked))
                except:
                    self.warn('Unable to rechunk the array')
                    print_exception()
                    os.rename(_src, target) # set name back to original name
                    return

                self.tell('Rechunking...')
                logger.info('Rechunking...')
                rechunked.execute()
                self.hud.done()

                logger.info('Removing %s...' %intermediate)
                self.tell('Removing %s...' %intermediate)
                shutil.rmtree(intermediate, ignore_errors=True)
                shutil.rmtree(intermediate, ignore_errors=True)

                logger.info('Removing %s...' %_src)
                self.tell('Removing %s...' %_src)
                shutil.rmtree(_src, ignore_errors=True)
                shutil.rmtree(_src, ignore_errors=True)
                self.hud.done()

                t_end = time.time()
                dt = t_end - t_start
                z = zarr.open(store=target)
                info = str(z.info)
                self.tell('\n%s' %info)

                self.tell('Rechunking Time: %.2f' % dt)
                logger.info('Rechunking Time: %.2f' % dt)

                cfg.project_tab.initNeuroglancer()

            else:
                logger.info('Rechunking Canceled')


    def initControlPanel(self):

        button_size = QSize(58, 20)
        std_input_size = QSize(64, 20)
        normal_button_size = QSize(68, 28)
        baseline = Qt.AlignmentFlag.AlignBaseline
        vcenter  = Qt.AlignmentFlag.AlignVCenter
        hcenter  = Qt.AlignmentFlag.AlignHCenter
        center   = Qt.AlignmentFlag.AlignCenter
        left     = Qt.AlignmentFlag.AlignLeft
        right    = Qt.AlignmentFlag.AlignRight

        tip = 'Keep or Reject the Current Section'
        self._lab_keep_reject = QLabel('Include:')
        self._lab_keep_reject.setStatusTip(tip)
        # self._skipCheckbox = QCheckBox()
        self._skipCheckbox = ToggleSwitch()
        self._skipCheckbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._skipCheckbox.setObjectName('_skipCheckbox')
        self._skipCheckbox.stateChanged.connect(self._callbk_skipChanged)
        self._skipCheckbox.stateChanged.connect(self._callbk_unsavedChanges)
        self._skipCheckbox.setStatusTip(tip)
        self._skipCheckbox.setEnabled(False)
        self._skipCheckbox.setFixedHeight(28)
        vbl = VBL()
        vbl.setContentsMargins(2, 0, 2, 0)
        vbl.setSpacing(0)
        vbl.addWidget(self._lab_keep_reject, alignment=center)
        vbl.addWidget(self._skipCheckbox, alignment=right)
        # vbl.setAlignment(vcenter)
        self._ctlpanel_skip = QWidget()
        self._ctlpanel_skip.setMaximumHeight(34)
        self._ctlpanel_skip.setLayout(vbl)

        tip = 'Use All Images (Reset)'
        self._btn_clear_skips = QPushButton('Reset')
        self._btn_clear_skips.setEnabled(False)
        self._btn_clear_skips.setStyleSheet("font-size: 10px;")
        self._btn_clear_skips.setStatusTip(tip)
        self._btn_clear_skips.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_clear_skips.clicked.connect(self.clear_skips)
        self._btn_clear_skips.setFixedSize(button_size)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        lab = QLabel("Whitening Factor:")
        lab.setAlignment(center)
        self._whiteningControl = QDoubleSpinBox(self)
        self._whiteningControl.setFixedHeight(14)
        self._whiteningControl.valueChanged.connect(self._callbk_unsavedChanges)
        self._whiteningControl.valueChanged.connect(self._valueChangedWhitening)
        self._whiteningControl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self._whiteningControl.setValue(cfg.DEFAULT_WHITENING)
        self._whiteningControl.setFixedSize(std_input_size)
        self._whiteningControl.setDecimals(2)
        self._whiteningControl.setSingleStep(.01)
        self._whiteningControl.setMinimum(-2)
        self._whiteningControl.setMaximum(2)
        # self._whiteningControl.setEnabled(False)
        lab.setStatusTip(tip)
        self._whiteningControl.setStatusTip(tip)
        lay = QHBoxLayout()
        # lay.addWidget(lab, alignment=right)
        lay.addWidget(self._whiteningControl, alignment=center)
        lay.setContentsMargins(0, 0, 0, 0)
        w = QWidget()
        w.setLayout(lay)
        self._ctlpanel_whitening = VWidget(lab, w)


        tip = "The region size SWIM uses for computing alignment, specified as pixels" \
              "width. (default=12.5% of image width)"
        lab = QLabel("SWIM Window:")
        lab.setAlignment(center)
        self._swimWindowControl = QSpinBox(self)
        self._swimWindowControl.setSuffix('px')
        self._swimWindowControl.setMaximum(9999)
        self._swimWindowControl.setFixedHeight(14)
        def fn():
            # logger.info('')
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info(f'caller: {caller}')
                # cfg.data.set_swim_window_global(float(self._swimWindowControl.value()) / 100.)
                cfg.data.set_swim_window_px(self._swimWindowControl.value())
                # setData(f'data,scales,{cfg.data.scale},')



        self._swimWindowControl.valueChanged.connect(fn)
        self._swimWindowControl.valueChanged.connect(self._callbk_unsavedChanges)
        self._swimWindowControl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self._swimWindowControl.setValue(cfg.DEFAULT_SWIM_WINDOW)
        self._swimWindowControl.setFixedSize(std_input_size)
        lab.setStatusTip(tip)
        self._swimWindowControl.setStatusTip(tip)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        # lay.addWidget(lab, alignment=right)
        lay.addWidget(self._swimWindowControl, alignment=center)
        w = QWidget()
        w.setLayout(lay)
        self._ctlpanel_inp_swimWindow = VWidget(lab, w)



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

        # hbl = QHBoxLayout()
        # hbl.setContentsMargins(0, 0, 0, 0)
        # hbl.addWidget(self._ctlpanel_inp_swimWindow)
        # hbl.addWidget(self._ctlpanel_whitening)
        # hbl.addWidget(self._ctlpanel_applyAllButton)

        tip = 'Go To Previous Section.'
        self._btn_prevSection = QPushButton()
        self._btn_prevSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_prevSection.setStatusTip(tip)
        self._btn_prevSection.clicked.connect(self.layer_left)
        self._btn_prevSection.setFixedSize(QSize(20, 20))
        self._btn_prevSection.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))
        self._btn_prevSection.setEnabled(False)

        tip = 'Go To Next Section.'
        self._btn_nextSection = QPushButton()
        self._btn_nextSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_nextSection.setStatusTip(tip)
        self._btn_nextSection.clicked.connect(self.layer_right)
        self._btn_nextSection.setFixedSize(QSize(20, 20))
        self._btn_nextSection.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))
        self._btn_nextSection.setEnabled(False)

        w = QWidget()
        lab = QLabel('Section:')
        lab.setAlignment(left)
        hbl = HBL()
        hbl.addWidget(self._btn_prevSection, alignment=right)
        hbl.addWidget(self._btn_nextSection, alignment=left)
        w.setLayout(hbl)
        self._sectionChangeWidget = VWidget(lab,w)
        self._sectionChangeWidget.layout.setAlignment(Qt.AlignVCenter)
        self._sectionChangeWidget.layout.setSpacing(0)
        self._sectionChangeWidget.setFixedWidth(48)
        self._sectionChangeWidget.setAutoFillBackground(True)


        tip = 'Go To Previous Scale.'
        self._scaleDownButton = QPushButton()
        self._scaleDownButton.setEnabled(False)
        self._scaleDownButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleDownButton.setStatusTip(tip)
        self._scaleDownButton.clicked.connect(self.scale_down)
        self._scaleDownButton.setFixedSize(QSize(20, 20))
        self._scaleDownButton.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        tip = 'Go To Next Scale.'
        self._scaleUpButton = QPushButton()
        self._scaleUpButton.setEnabled(False)
        self._scaleUpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleUpButton.setStatusTip(tip)
        self._scaleUpButton.clicked.connect(self.scale_up)
        self._scaleUpButton.setFixedSize(QSize(20, 20))
        self._scaleUpButton.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        w = QWidget()
        lab = QLabel('Scale:')
        lab.setAlignment(left)
        hbl = HBL()
        hbl.addWidget(self._scaleDownButton, alignment=right)
        hbl.addWidget(self._scaleUpButton, alignment=left)
        w.setLayout(hbl)
        self._scaleSetWidget = VWidget(lab, w)
        self._scaleSetWidget.layout.setSpacing(0)
        self._scaleSetWidget.setFixedWidth(48)

        # lab = QLabel('Scale:')
        # lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        # self._ctlpanel_changeScale = QWidget()
        # lay = QHBoxLayout()
        # lay.setContentsMargins(0, 0, 0, 0)
        # lay.addWidget(lab, alignment=right)
        # lay.addWidget(self._scaleSetWidget, alignment=left)
        # self._ctlpanel_changeScale.setLayout(lay)

        tip = 'Align and Generate All Sections'
        self._btn_alignAll = QPushButton('Align All')
        self._btn_alignAll.setEnabled(False)
        self._btn_alignAll.setStyleSheet("font-size: 10px;")
        self._btn_alignAll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignAll.setStatusTip(tip)
        self._btn_alignAll.clicked.connect(self.alignAll)
        self._btn_alignAll.setFixedSize(normal_button_size)

        tip = 'Align and Generate the Current Section Only'
        self._btn_alignOne = QPushButton('Align One')
        self._btn_alignOne.setEnabled(False)
        self._btn_alignOne.setStyleSheet("font-size: 10px;")
        self._btn_alignOne.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignOne.setStatusTip(tip)
        self._btn_alignOne.clicked.connect(self.alignOne)
        self._btn_alignOne.setFixedSize(normal_button_size)

        self.sectionRangeSlider = RangeSlider()
        self.sectionRangeSlider.setStyleSheet('border-radius: 2px;')
        self.sectionRangeSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sectionRangeSlider.setFixedWidth(100)
        self.sectionRangeSlider.setMin(0)
        self.sectionRangeSlider.setStart(0)

        self.startRangeInput = QLineEdit()
        self.startRangeInput.setFixedSize(34,22)
        self.startRangeInput.setEnabled(False)

        self.endRangeInput = QLineEdit()
        self.endRangeInput.setFixedSize(34,22)
        self.endRangeInput.setEnabled(False)

        self.rangeInputWidget = QWidget()
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 0, 2, 0)
        hbl.setSpacing(0)
        hbl.addWidget(self.startRangeInput)
        hbl.addWidget(QLabel(':'))
        hbl.addWidget(self.endRangeInput)
        self.rangeInputWidget.setLayout(hbl)

        self.sectionRangeSlider.startValueChanged.connect(lambda val: self.startRangeInput.setText(str(val)))
        self.sectionRangeSlider.endValueChanged.connect(lambda val: self.endRangeInput.setText(str(val)))
        self.startRangeInput.textChanged.connect(lambda val: self.sectionRangeSlider.setStart(int(val)))
        self.endRangeInput.textChanged.connect(lambda val: self.sectionRangeSlider.setEnd(int(val)))


        tip = 'Align and Generate a Range of Sections'
        self._btn_alignRange = QPushButton('Align Range')
        self._btn_alignRange.setEnabled(False)
        self._btn_alignRange.setStyleSheet("font-size: 10px;")
        self._btn_alignRange.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignRange.setStatusTip(tip)
        self._btn_alignRange.clicked.connect(self.alignRange)
        self._btn_alignRange.setFixedSize(normal_button_size)

        tip = 'Auto-generate aligned images.'
        lab = QLabel("Auto-generate:")
        lab.setAlignment(center)
        lab.setStatusTip(tip)
        self._toggleAutogenerate = ToggleSwitch()
        self._toggleAutogenerate.stateChanged.connect(self._toggledAutogenerate)
        self._toggleAutogenerate.stateChanged.connect(self._callbk_unsavedChanges)
        self._toggleAutogenerate.setStatusTip(tip)
        self._toggleAutogenerate.setChecked(True)
        self._toggleAutogenerate.setEnabled(False)
        self._toggleAutogenerate.setFixedHeight(28)
        vbl = VBL()
        vbl.setSpacing(0)
        # hbl.addWidget(lab, alignment=right | vcenter)
        # hbl.addWidget(self._toggleAutogenerate, alignment=right | vcenter)
        vbl.addWidget(lab, alignment=center)
        vbl.addWidget(self._toggleAutogenerate, alignment=right)
        vbl.setAlignment(vcenter)
        self._ctlpanel_toggleAutogenerate = QWidget()
        self._ctlpanel_toggleAutogenerate.setMaximumHeight(34)
        self._ctlpanel_toggleAutogenerate.setLayout(vbl)

        tip = 'Polynomial bias correction (default=None), alters the generated images including their width and height.'
        lab = QLabel("Corrective Polynomial:")
        lab.setAlignment(right)
        lab.setStatusTip(tip)
        self._polyBiasCombo = QComboBox(self)
        self._polyBiasCombo.setStyleSheet("font-size: 10px; padding-left: 6px;")
        self._polyBiasCombo.currentIndexChanged.connect(self._valueChangedPolyOrder)
        self._polyBiasCombo.currentIndexChanged.connect(self._callbk_unsavedChanges)
        self._polyBiasCombo.setStatusTip(tip)
        self._polyBiasCombo.addItems(['None', '0', '1', '2', '3', '4'])
        self._polyBiasCombo.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self._polyBiasCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._polyBiasCombo.setFixedSize(QSize(54, 18))
        self._polyBiasCombo.setEnabled(False)
        self._polyBiasCombo.lineEdit()
        vbl = VBL()
        vbl.setSpacing(0)
        vbl.addWidget(lab, alignment=center)
        vbl.addWidget(self._polyBiasCombo, alignment=right)
        self._ctlpanel_polyOrder = QWidget()
        self._ctlpanel_polyOrder.setLayout(vbl)


        tip = 'Bounding box is only applied upon "Align All" and "Regenerate". Caution: Turning this ON may ' \
              'significantly increase the size of generated images.'
        lab = QLabel("Bounding Box:")
        lab.setAlignment(center)
        lab.setStatusTip(tip)
        self._bbToggle = ToggleSwitch()
        # self._bbToggle.setChecked(True)
        self._bbToggle.setStatusTip(tip)
        self._bbToggle.toggled.connect(self._callbk_bnding_box)
        self._bbToggle.setEnabled(False)
        self._bbToggle.setFixedHeight(28)
        vbl = VBL()
        vbl.setSpacing(0)
        # hbl.addWidget(lab, alignment=baseline | Qt.AlignmentFlag.AlignRight)
        vbl.addWidget(lab, alignment=center)
        vbl.addWidget(self._bbToggle, alignment=right)
        vbl.setAlignment(vcenter)
        self._ctlpanel_bb = QWidget()
        self._ctlpanel_bb.setMaximumHeight(34)
        self._ctlpanel_bb.setLayout(vbl)
        # self._ctlpanel_bb = VWidget(lab, self._bbToggle)
        # self._ctlpanel_bb.setStyleSheet('background-color: #222222;')
        # self._bbToggle.setAutoFillBackground(True)
        # self._ctlpanel_bb.setAutoFillBackground(True)
        # self._ctlpanel_bb.layout.setSpacing(0)


        tip = "Recompute cumulative affine and generate new images" \
              "based on the current Null Bias and Bounding Box presets."
        self._btn_regenerate = QPushButton('Regenerate')
        # self._btn_regenerate.setStyleSheet('font-size: 10px;')
        self._btn_regenerate.setEnabled(False)
        self._btn_regenerate.setStatusTip(tip)
        self._btn_regenerate.clicked.connect(lambda: self.regenerate(scale=cfg.data.scale))
        self._btn_regenerate.setFixedSize(normal_button_size)

        self._wdg_alignButtons = QWidget()
        hbl = HBL()
        # hbl.addWidget(self._ctlpanel_applyAllButton)
        hbl.addWidget(self._btn_regenerate)
        hbl.addWidget(self._btn_alignOne)
        hbl.addWidget(self.sectionRangeSlider)
        hbl.addWidget(self.rangeInputWidget)
        hbl.addWidget(self._btn_alignRange)
        hbl.addWidget(self._btn_alignAll)
        self._wdg_alignButtons.setLayout(hbl)
        # lab = QLabel('Actions\n(Highly Parallel):')

        # lab.setAlignment(right | vcenter)
        lay = QHBoxLayout()
        # vbl.setSpacing(1)
        lay.setContentsMargins(0, 0, 0, 0)
        # lay.addWidget(lab, alignment=right)
        lay.addWidget(self._wdg_alignButtons, alignment=left)
        self._ctlpanel_alignRegenButtons = QWidget()
        self._ctlpanel_alignRegenButtons.setLayout(lay)

        style = """
            QWidget {background-color: #222222;}

            QDoubleSpinBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 2px;
            }
            QSpinBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 2px;
            }
            QLineEdit {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 2px;
            }
            QComboBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 2px;
            }
            QAbstractItemView {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
            }
            QCheckBox::indicator {
                background: none;
            }
        """
        # border: 1px solid #f3f6fb;

        stretch1 = QWidget()
        stretch1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        stretch2 = QWidget()
        stretch2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.cpanel_hwidget1 = HWidget(
            QLabel('  '),
            self._sectionChangeWidget,
            # self._scaleSetWidget,
            self._ctlpanel_skip,
            self._ctlpanel_bb,
            self._ctlpanel_toggleAutogenerate,
            self._ctlpanel_polyOrder,
            self._ctlpanel_inp_swimWindow,
            self._ctlpanel_whitening,
            self._ctlpanel_alignRegenButtons,
            QLabel('  '),
        )

        self.cpanel_hwidget1.setStyleSheet('background-color: #222222;')
        self.cpanel_hwidget1.setAutoFillBackground(True)
        self.cpanel_hwidget1.layout.setSpacing(10)
        self.cpanel_hwidget1.setStyleSheet(style)

        # cpanel_hwidget2.setStyleSheet('background-color: #222222; color: #f3f6fb; font-size: 10px;')
        # cpanel_hwidget2.setAutoFillBackground(True)
        # cpanel_hwidget2.layout.setSpacing(0)
        # cpanel_hwidget2.setStyleSheet(style)

        lab = QLabel('Global Default Settings')
        lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        lab.setStyleSheet(
            """
            color: #f3f6fb; 
            font-size: 10px; 
            font-weight: 600; 
            padding-left: 2px; 
            padding-top: 2px;
            """)

        self.cpanel = VWidget(lab, self.cpanel_hwidget1)

        self.cpanel.setStyleSheet('QWidget {'
                                  'background-color: #222222; '
                                  'color: #f3f6fb; '
                                  'font-size: 10px; '
                                  'padding-left: 2px;'
                                  'padding-right: 2px;'
                                  '}')
        self.cpanel.setAutoFillBackground(True)
        # self.cpanel.setStyleSheet('color: #f3f6fb; font-size: 9px;')
        # with open('src/style/cpanel.qss', 'r') as f:
        #     self.cpanel.setStyleSheet(f.read())

        # self.cpanel.setFixedHeight(60)
        # self.cpanel.hide()



    def splittersHaveMoved(self, pos, index):
        logger.critical('')
        # self.correlation_signals.setMinimumHeight(16)  # reverse this on splitter moved (hacky)MinimumHeight(10)  # reverse this on splitter moved (hacky)

        # if not self._dev_console.isVisible():
        #     self._forceHidePython()
        #
        # if not self.cpanelFrame.isVisible():
        #     self._forceHideControls()
        #
        # if not self.notes.isVisible():
        #     self._forceHideNotes()

        if self.correlation_signals.isVisible():
            cur_size = self._splitter.sizes()[1]
            if cur_size != 0:
                self._corrSpotDrawerSize = cur_size
            self.updateCorrSignalsDrawer()
            # h = self.correlation_signals.geometry().height()
            # # self.corrSignalsDrawer.setFixedHeight(max(10,h-44))
            # for w in self.corrSignalsList:
            #     w.setFixedSize(max(10,h-44))
    #
    #     logger.info('pos: %s index: %s' % (str(pos),str(index)) )
    #     if self.detailsWidget.isHidden():
    #         label = ' Details'
    #         icon = 'fa.info-circle'
    #         self._btn_show_hide_corr_spots.setIcon(qta.icon(icon, color='#f3f6fb'))
    #         self._btn_show_hide_corr_spots.setText(label)
    #
    #     if self.shaderWidget.isHidden():
    #         label = ' Shader'
    #         icon = 'mdi.format-paint'
    #         self.shaderWidget.hide()
    #         self._btn_show_hide_shader.setIcon(qta.icon(icon, color='#f3f6fb'))
    #         self._btn_show_hide_shader.setText(label)
    #
    #     if self.notes.isHidden():
    #         label  = ' Notes'
    #         icon   = 'mdi.notebook-edit'
    #         self.notes.hide()
    #         self._btn_show_hide_notes.setIcon(qta.icon(icon, color='#f3f6fb'))
    #         self._btn_show_hide_notes.setText(label)
    #
    #     if self._dev_console.isHidden():
    #         self._forceHidePython()
    #
    #     if self.cpanelMainWidgets.isHidden():
    #         self._forceHideControls()


    def initUI(self):
        '''Initialize Main UI'''
        logger.info(f'Current Directory: {os.getcwd()}')

        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)

        with open('src/style/controls.qss', 'r') as f:
            lower_controls_style = f.read()

        '''Headup Display'''
        self.hud = HeadupDisplay(self.app)
        self.hud.resize(QSize(400,120))
        # self.hud.setMinimumWidth(256)
        self.hud.setMinimumWidth(180)
        self.hud.setObjectName('hud')
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
        vcenter  = Qt.AlignmentFlag.AlignVCenter
        hcenter  = Qt.AlignmentFlag.AlignHCenter
        center   = Qt.AlignmentFlag.AlignCenter
        left     = Qt.AlignmentFlag.AlignLeft
        right    = Qt.AlignmentFlag.AlignRight

        self._processMonitorWidget = QWidget()
        self._processMonitorWidget.setStyleSheet('background-color: #1b2328; color: #f3f6fb; border-radius: 5px;')
        lab = QLabel('Process Monitor')
        lab.setStyleSheet('font-size: 9px; font-weight: 500; color: #141414;')
        lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 4px; margin-top: 4px;')
        vbl = QVBoxLayout()
        vbl.setSpacing(1)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(lab, alignment=baseline)
        vbl.addWidget(self.hud)
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
            QLabel('Rejected Layer :'),
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
        self._tool_hstry.setObjectName('_tool_hstry')
        self._hstry_listWidget = QListWidget()
        # self._hstry_listWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._hstry_listWidget.setObjectName('_hstry_listWidget')
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

        # self.matchpointControls = QWidget()
        # with open('src/style/cpanel.qss', 'r') as f:
        #     self.matchpointControls.setStyleSheet(f.read())
        #
        # self.matchpointControls.setFixedSize(QSize(560,120))
        # self.matchpointControls.hide()

        mp_marker_lineweight_label = QLabel('Lineweight')
        self.mp_marker_lineweight_spinbox = QSpinBox()
        self.mp_marker_lineweight_spinbox.setMinimum(1)
        self.mp_marker_lineweight_spinbox.setMaximum(32)
        self.mp_marker_lineweight_spinbox.setSuffix('pt')
        # self.mp_marker_lineweight_spinbox.valueChanged.connect(self.set_mp_marker_lineweight)
        self.mp_marker_lineweight_spinbox.valueChanged.connect(
            lambda val: setOpt('neuroglancer,MATCHPOINT_MARKER_LINEWEIGHT', val))

        mp_marker_size_label = QLabel('Size')
        self.mp_marker_size_spinbox = QSpinBox()
        self.mp_marker_size_spinbox.setMinimum(1)
        self.mp_marker_size_spinbox.setMaximum(32)
        self.mp_marker_size_spinbox.setSuffix('pt')
        self.mp_marker_size_spinbox.valueChanged.connect(
            lambda val: setOpt('neuroglancer,MATCHPOINT_MARKER_SIZE', val))

        self.exit_matchpoint_button = QPushButton('Exit')
        self.exit_matchpoint_button.setStatusTip('Exit Manual Alignment Mode')
        self.exit_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_matchpoint_button.clicked.connect(self.enterExitManAlignMode)
        self.exit_matchpoint_button.setFixedSize(normal_button_size)

        # self.realign_matchpoint_button = QPushButton('Realign\nSection')
        # self.realign_matchpoint_button.setStatusTip('Realign The Current Layer')
        # self.realign_matchpoint_button.setStyleSheet("font-size: 9px;")
        # self.realign_matchpoint_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.realign_matchpoint_button.clicked.connect(self.alignGenerateOne)
        # self.realign_matchpoint_button.setFixedSize(normal_button_size)

        self.matchpoint_text_snr = QLabel()
        self.matchpoint_text_snr.setFixedHeight(26)
        self.matchpoint_text_snr.setWordWrap(True)
        self.matchpoint_text_snr.setStyleSheet('border-width: 0px;font-size: 12px;')
        self.matchpoint_text_snr.setMaximumWidth(300)
        # self.matchpoint_text_snr.setFixedHeight(24)
        self.matchpoint_text_snr.setObjectName('matchpoint_text_snr')

        hbl = HBL()
        hbl.addWidget(self.exit_matchpoint_button)
        # hbl.addWidget(self.realign_matchpoint_button)
        hbl.addWidget(mp_marker_lineweight_label)
        hbl.addWidget(self.mp_marker_lineweight_spinbox)
        hbl.addWidget(mp_marker_size_label)
        hbl.addWidget(self.mp_marker_size_spinbox)
        hbl.addWidget(self.matchpoint_text_snr)
        hbl.addStretch()

        # self.matchpoint_text_prompt = QTextEdit()
        # # self.matchpoint_text_prompt.setMaximumWidth(600)
        # self.matchpoint_text_prompt.setFixedHeight(74)
        # self.matchpoint_text_prompt.setReadOnly(True)
        # self.matchpoint_text_prompt.setObjectName('matchpoint_text_prompt')
        # self.matchpoint_text_prompt.setStyleSheet('border: 0px;')
        # self.matchpoint_text_prompt.setHtml("Select 3-5 corresponding match points on the reference and base images. Key Bindings:<br>"
        #                                     "<b>Enter/return</b> - Add match points (Left, Right, Left, Right...)<br>"
        #                                     "<b>s</b>            - Save match points<br>"
        #                                     "<b>c</b>            - Clear match points for this layer")

        lab = QLabel('Control Panel - Manual Point Selection')
        lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 4px; margin-top: 4px;')

        vbl = QVBoxLayout()
        vbl.setContentsMargins(4, 0, 4, 0)
        vbl.addWidget(lab)
        vbl.addLayout(hbl)
        # vbl.addWidget(self.matchpoint_text_prompt)
        # vbl.addStretch()

        gb = QGroupBox()
        gb.setLayout(vbl)

        vbl = VBL()
        vbl.addWidget(gb)

        # self.corrSignalsDrawer = QWidget()
        # self.corrSignalsDrawer.setMinimumHeight(30)
        # self.corrSignalsDrawer.setStyleSheet('background-color: #1b1e23; color: #f3f6fb; border-radius: 5px; ')
        hbl = QHBoxLayout()
        hbl.setSpacing(1)
        # hbl.setContentsMargins(4,4,4,8)

        self.cs0 = CorrSignalThumbnail(self)
        self.cs1 = CorrSignalThumbnail(self)
        self.cs2 = CorrSignalThumbnail(self)
        self.cs3 = CorrSignalThumbnail(self)
        self.cs4 = CorrSignalThumbnail(self)
        self.cs5 = CorrSignalThumbnail(self)
        self.cs6 = CorrSignalThumbnail(self)
        self.corrSignalsList = [
            self.cs0,
            self.cs1,
            self.cs2,
            self.cs3,
            self.cs4,
            self.cs5,
            self.cs6
        ]
        hbl.setContentsMargins(2, 2, 2, 2)
        hbl.addWidget(self.cs0)
        hbl.addWidget(self.cs1)
        hbl.addWidget(self.cs2)
        hbl.addWidget(self.cs3)
        hbl.addWidget(self.cs4)
        hbl.addWidget(self.cs5)
        hbl.addWidget(self.cs6)
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        hbl.addWidget(w)
        self.corrSignalsWidget = QWidget()
        self.corrSignalsWidget.setLayout(hbl)

        self.lab_corr_signals = QLabel('No Signals Found for Current Alignment Method.')
        self.lab_corr_signals.setMaximumHeight(18)
        self.lab_corr_signals.setStyleSheet('color: #ede9e8;')
        self.lab_corr_signals.setContentsMargins(8,0,0,0)

        # self.corrSignalsDrawer.setLayout(hbl)
        self.corrSignalsDrawer = VWidget(self.corrSignalsWidget, self.lab_corr_signals)
        # self.corrSignalsDrawer.setStyleSheet('background-color: #ffe135; color: #f3f6fb; border-radius: 5px; ')
        # self.corrSignalsDrawer.setVisible(getOpt(lookup='ui,SHOW_CORR_SPOTS'))

        '''Show/Hide Primary Tools Buttons'''

        tip = 'Show/Hide Alignment Controls'
        self._btn_show_hide_ctls = QPushButton('Hide Controls')
        self._btn_show_hide_ctls.setFixedHeight(18)
        self._btn_show_hide_ctls.setStyleSheet(lower_controls_style)
        self._btn_show_hide_ctls.setStatusTip(tip)
        self._btn_show_hide_ctls.clicked.connect(self._callbk_showHideControls)
        # self._btn_show_hide_ctls.setIcon(qta.icon('fa.caret-down', color='#f3f6fb'))
        self._btn_show_hide_ctls.setIcon(qta.icon('fa.caret-down', color='#380282'))
        self._btn_show_hide_ctls.setIconSize(QSize(12, 12))
        self._btn_show_hide_ctls.setStyleSheet(
                'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif;')

        tip = 'Show/Hide Python Console'
        self._btn_show_hide_console = QPushButton(' Python')
        self._btn_show_hide_console.setFixedHeight(18)
        self._btn_show_hide_console.setStyleSheet(lower_controls_style)
        self._btn_show_hide_console.setStatusTip(tip)
        self._btn_show_hide_console.clicked.connect(self._callbk_showHidePython)
        # self._btn_show_hide_console.setIcon(qta.icon("mdi.language-python", color='#f3f6fb'))
        self._btn_show_hide_console.setIcon(qta.icon("mdi.language-python", color='#380282'))
        self._btn_show_hide_console.setIconSize(QSize(12, 12))
        self._btn_show_hide_console.setStyleSheet(
                'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif;')

        def fn():
            caller = inspect.stack()[1].function
            if caller != 'updateNotes':
                if self._isProjectTab():
                    if cfg.data:
                        self.statusBar.showMessage('Note Saved!', 3000)
                        cfg.data.save_notes(text=self.notesTextEdit.toPlainText())
                else:
                    cfg.settings['notes']['global_notes'] = self.notesTextEdit.toPlainText()
                self.notes.update()

        self.notes = QWidget()
        self.notes.setStyleSheet("""
        color: #f3f6fb; 
        """)
        # self.notesTextEdit = QPlainTextEdit()
        self.notesTextEdit = QTextEdit()
        self.notesTextEdit.setStyleSheet("""
        background-color: #f3f6fb; 
        color: #141414;
        font-size: 11px; 
        border-width: 0px; 
        border-radius: 5px;
        """)
        self.notesTextEdit.setPlaceholderText('Type any notes here...')
        self.notesTextEdit.textChanged.connect(fn)
        lab = QLabel('Notes')
        # lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin-left: 2px; margin-top: 2px;')
        # lab.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 500; margin: 2px;')
        lab.setStyleSheet(
            """
            color: #f3f6fb; 
            font-size: 10px; 
            font-weight: 600; 
            padding-left: 2px; 
            padding-top: 2px;
            """)
        vbl = QVBoxLayout()
        vbl.setSpacing(0)
        # vbl.setContentsMargins(4, 0, 4, 0)
        vbl.setContentsMargins(1, 1, 1, 1)
        vbl.addWidget(lab)
        vbl.addWidget(self.notesTextEdit)
        self.notes.setLayout(vbl)
        self.notes.hide()


        tip = 'Show/Hide Project Notes'
        self._btn_show_hide_notes = QPushButton(' Notes')
        self._btn_show_hide_notes.setFixedHeight(18)
        self._btn_show_hide_notes.setStyleSheet(lower_controls_style)
        self._btn_show_hide_notes.setStatusTip(tip)
        self._btn_show_hide_notes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_show_hide_notes.clicked.connect(self._callbk_showHideNotes)
        # self._btn_show_hide_notes.setIcon(qta.icon('mdi.notebook-edit', color='#f3f6fb'))
        self._btn_show_hide_notes.setIcon(qta.icon('mdi.notebook-edit', color='#380282'))
        self._btn_show_hide_notes.setStyleSheet(
                'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif;')

        tip = 'Show/Hide Shader Code'
        self._btn_show_hide_shader = QPushButton(' Shader')
        self._btn_show_hide_shader.setFixedHeight(18)
        self._btn_show_hide_shader.setStyleSheet(lower_controls_style)
        self._btn_show_hide_shader.setStatusTip(tip)
        # self._btn_show_hide_shader.clicked.connect(self._callbk_showHideShader)
        # self._btn_show_hide_shader.setIcon(qta.icon('mdi.format-paint', color='#f3f6fb'))
        self._btn_show_hide_shader.setIcon(qta.icon('mdi.format-paint', color='#380282'))
        self._btn_show_hide_shader.setIconSize(QSize(12, 12))
        self._btn_show_hide_shader.setStyleSheet(
                'color: #380282; font-size: 11px; font-family: Tahoma, sans-serif;')



        dSize = 166

        self.detailsTitle = QLabel('Correlation Signals')
        self.detailsTitle.setFixedHeight(13)
        self.detailsTitle.setStyleSheet('color: #f3f6fb; font-size: 10px; font-weight: 600; margin-left: 2px; margin-top: 2px;')


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


        # self.correlation_signals = QWidget()
        self.correlation_signals = QScrollArea()
        # self.correlation_signals.setMinimumHeight(136) #Important
        # self.correlation_signals.setStyleSheet('background-color: #222222; color: #f3f6fb; border-radius: 5px; QScrollBar {width:0px;}")')
        self.correlation_signals.setWidgetResizable(True)
        w = QWidget()
        vbl = VBL()
        vbl.setSpacing(0)
        vbl.addWidget(self.detailsTitle)
        vbl.addWidget(self.corrSignalsDrawer)
        w.setLayout(vbl)
        # w.setMinimumHeight(80)
        # self.correlation_signals.setLayout(vbl)
        # self.correlation_signals.hide()
        self.correlation_signals.setWidget(w)
        self.correlation_signals.hide()


        # self.detailsWidget = QScrollArea()
        # self.detailsWidget.setWidgetResizable(True)


        '''Tabs Global Widget'''
        self.globTabs = QTabWidget(self)
        # self.globTabs.setStyleSheet('background-color: #222222;')
        self.globTabs.tabBar().setStyleSheet("""
        QTabBar::tab {
          width: 128px;
        }
        """)

        # self.globTabs.setTabShape(QTabWidget.TabShape.Triangular)

        # self.globTabs.setTabBarAutoHide(True)
        self.globTabs.setElideMode(Qt.ElideMiddle)
        self.globTabs.setMovable(True)
        self.globTabs.hide()

        self.globTabs.setDocumentMode(True)
        self.globTabs.setTabsClosable(True)
        self.globTabs.setObjectName('globTabs')
        self.globTabs.tabCloseRequested[int].connect(self._onGlobTabClose)
        self.globTabs.currentChanged.connect(self._onGlobTabChange)


        self.pythonConsole = PythonConsole()
        self.__dev_console = QWidget()
        vbl = VBL()
        vbl.addWidget(self.pythonConsole)
        self.__dev_console.setLayout(vbl)

        self._dev_console = QWidget()
        self._dev_console.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # self._dev_console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self._dev_console.resize(QSize(600,600))

        self.__dev_console.setStyleSheet("""
        font-size: 10px; 
        background-color: #222222;
        color: #f3f6fb;
        font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
        border-radius: 5px;
        """)
        lab = QLabel('Python Console')
        lab.setStyleSheet(
            """
            color: #f3f6fb; 
            font-size: 10px; 
            font-weight: 600; 
            padding-left: 2px; 
            padding-top: 2px;
            """)
        vbl = QVBoxLayout()
        # vbl.setSpacing(1)
        vbl.setSpacing(0)
        vbl.setContentsMargins(1, 1, 1, 1) # this provides for thin contrasting margin
        vbl.addWidget(lab, alignment=Qt.AlignBaseline)
        vbl.addWidget(self.__dev_console)
        self._dev_console.setLayout(vbl)
        self._dev_console.hide()
        self.notes.setContentsMargins(0, 0, 0, 0)
        self._dev_console.setContentsMargins(0, 0, 0, 0)

        '''Main Vertical Splitter'''
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        # self._splitter.setStyleSheet("""
        # QWidget {background: #222222;}
        # QSplitter::handle { background: #339933; margin-left:400px; margin-right:400px;}""")
        self._splitter.setStyleSheet("""
        QWidget {background: #222222;}
        QSplitter::handle:horizontal {width: 1px;} QSplitter::handle:vertical {height: 1px;}""")
        # self._splitter.setAutoFillBackground(True)
        self._splitter.splitterMoved.connect(self.splittersHaveMoved)
        self._splitter.addWidget(self.notes)                # (0)
        self._splitter.addWidget(self.correlation_signals)  # (1)
        self._splitter.addWidget(self._dev_console)         # (2)
        self._splitter.setContentsMargins(0, 0, 0, 0)
        self._splitter.setHandleWidth(1)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, False)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.hide()

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
        buttonBrowserBack.setStatusTip('Go Back')
        buttonBrowserBack.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserBack.clicked.connect(browser_backward)
        buttonBrowserBack.setFixedSize(QSize(20, 20))
        buttonBrowserBack.setIcon(qta.icon('fa.arrow-left', color=ICON_COLOR))

        buttonBrowserForward = QPushButton()
        buttonBrowserForward.setStatusTip('Go Forward')
        buttonBrowserForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserForward.clicked.connect(browser_forward)
        buttonBrowserForward.setFixedSize(QSize(20, 20))
        buttonBrowserForward.setIcon(qta.icon('fa.arrow-right', color=ICON_COLOR))

        buttonBrowserRefresh = QPushButton()
        buttonBrowserRefresh.setStatusTip('Refresh')
        buttonBrowserRefresh.setIcon(qta.icon("ei.refresh", color=cfg.ICON_COLOR))
        buttonBrowserRefresh.setFixedSize(QSize(22,22))
        buttonBrowserRefresh.clicked.connect(browser_reload)

        # buttonBrowserViewSource = QPushButton()
        # buttonBrowserViewSource.setStatusTip('View Source')
        # buttonBrowserViewSource.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # buttonBrowserViewSource.clicked.connect(browser_view_source)
        # buttonBrowserViewSource.setFixedSize(QSize(20, 20))
        # buttonBrowserViewSource.setIcon(qta.icon('ri.code-view', color=ICON_COLOR))

        buttonBrowserCopy = QPushButton('Copy')
        buttonBrowserCopy.setStatusTip('Copy Text')
        buttonBrowserCopy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserCopy.clicked.connect(browser_copy)
        buttonBrowserCopy.setFixedSize(QSize(50, 20))

        buttonBrowserPaste = QPushButton('Paste')
        buttonBrowserPaste.setStatusTip('Paste Text')
        buttonBrowserPaste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserPaste.clicked.connect(browser_paste)
        buttonBrowserPaste.setFixedSize(QSize(50, 20))

        button3demCommunity = QPushButton('3DEM Community Data')
        button3demCommunity.setStyleSheet('font-size: 10px;')
        button3demCommunity.setStatusTip('Vist the 3DEM Community Workbench')
        button3demCommunity.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button3demCommunity.clicked.connect(self.browser_3dem_community)
        button3demCommunity.setFixedSize(QSize(120, 20))

        #webpage
        browser_controls_widget = QWidget()
        browser_controls_widget.setFixedHeight(24)
        hbl = HBL()
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserBack, alignment=right)
        hbl.addWidget(buttonBrowserForward, alignment=left)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserRefresh, alignment=left)
        # hbl.addWidget(QLabel(' '))
        # hbl.addWidget(buttonBrowserViewSource, alignment=left)
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
        # hbl.addWidget(self._readmeButton, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(w)
        browser_bottom_controls = QWidget()
        browser_bottom_controls.setFixedHeight(20)
        browser_bottom_controls.setLayout(hbl)
        vbl.addWidget(browser_bottom_controls)
        self.browser_widget.setLayout(vbl)

        self.cpanelFrame = QFrame()
        self.cpanelFrame.setContentsMargins(4,4,4,4)
        self.cpanelFrame.setStyleSheet('background-color: #222222;')
        self.setAutoFillBackground(True)
        vbl = VBL()
        vbl.addWidget(self.cpanel)
        self.cpanelFrame.setLayout(vbl)

        self.globTabsAndCpanel = VWidget(self.globTabs, self.cpanelFrame)
        self.globTabsAndCpanel.setAutoFillBackground(True)

        # self.newMainWidget = VWidget(self.globTabs, self._splitter)
        self.newMainSplitter = QSplitter(Qt.Orientation.Vertical)
        # self.newMainSplitter.setStyleSheet("""QSplitter::handle { background: #339933; }""")
        self.newMainSplitter.setHandleWidth(1)
        self.newMainSplitter.addWidget(self.globTabsAndCpanel)
        self.newMainSplitter.addWidget(self._splitter)
        self.newMainSplitter.splitterMoved.connect(self.splittersHaveMoved)
        self.newMainSplitter.setCollapsible(0, False)
        self.newMainSplitter.setCollapsible(1, False)

        self.setCentralWidget(self.newMainSplitter)



    def initLaunchTab(self):
        self._launchScreen = OpenProject()
        self.globTabs.addTab(self._launchScreen, 'Open...')
        self._setLastTab()


    def get_application_root(self):
        return Path(__file__).parents[2]


    def initWidgetSpacing(self):
        logger.info('')
        # self._py_console.setContentsMargins(0, 0, 0, 0)
        self.hud.setContentsMargins(0, 0, 0, 0)
        self.layer_details.setContentsMargins(0, 0, 0, 0)
        self.matchpoint_text_snr.setMaximumHeight(20)
        self._tool_hstry.setMinimumWidth(248)
        # cfg.project_tab._transformationWidget.setFixedWidth(248)
        # cfg.project_tab._transformationWidget.setFixedSize(248,100)
        self.layer_details.setMinimumWidth(248)


    def initStatusBar(self):
        logger.info('')
        # self.statusBar = self.statusBar()
        self.statusBar = QStatusBar()
        self.statusBar.setFixedHeight(21)
        self.statusBar.setStyleSheet("""
        font-size: 10px;
        font-weight: 600;
        color: #141414;
        background-color: #ede9e8;
        margin: 0px;
        padding: 0px;
        """)
        self.setStatusBar(self.statusBar)


    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setStyleSheet("font-size: 10px;")
        self.pbar.setTextVisible(True)
        # font = QFont('Arial', 12)
        # font.setBold(True)
        # self.pbar.setFont(font)
        # self.pbar.setFixedHeight(16)
        # self.pbar.setFixedWidth(400)
        self.pbar_widget = QWidget(self)
        self.status_bar_layout = QHBoxLayout()
        self.status_bar_layout.setContentsMargins(0, 0, 0, 0)

        # self.pbar_cancel_button = QPushButton('Stop')
        self.pbar_cancel_button = QPushButton('Stop')
        self.pbar_cancel_button.setFixedSize(48,16)
        self.pbar_cancel_button.setStatusTip('Terminate Pending Multiprocessing Tasks')
        self.pbar_cancel_button.setIcon(qta.icon('mdi.cancel', color=cfg.ICON_COLOR))
        self.pbar_cancel_button.setStyleSheet("font-size: 10px;")
        self.pbar_cancel_button.clicked.connect(self.forceStopMultiprocessing)

        self.pbar_widget.setLayout(self.status_bar_layout)
        self.pbarLabel = QLabel('Task... ')
        self.status_bar_layout.addWidget(self.pbarLabel, alignment=Qt.AlignmentFlag.AlignRight)
        self.status_bar_layout.addWidget(self.pbar)
        self.status_bar_layout.addWidget(self.pbar_cancel_button)
        self.statusBar.addPermanentWidget(self.pbar_widget)
        self.hidePbar()

    def forceStopMultiprocessing(self):
        cfg.CancelProcesses = True
        cfg.event.set()

    def setPbarMax(self, x):
        self.pbar.setMaximum(x)


    def updatePbar(self, x=None):
        if x == None: x = cfg.nCompleted
        caller = inspect.stack()[1].function
        # logger.info(f'[caller: {caller}] Updating pbar, x={x}')
        self.pbar.setValue(x)
        # self.repaint()
        QApplication.processEvents()


    def setPbarText(self, text: str):
        # logger.critical('')
        self.pbar.setFormat('(%p%) ' + text)
        self.pbarLabel.setText('Processing (%d/%d)...' % (cfg.nCompleted, cfg.nTasks))
        # logger.info('Processing (%d/%d)...' % (cfg.nCompleted, cfg.nTasks))
        # self.repaint()
        QApplication.processEvents()


    def showZeroedPbar(self):
        logger.info('')
        self.pbar.setValue(0)
        self.setPbarText('Preparing Tasks...')
        self.pbar_widget.show()
        QApplication.processEvents()


    def hidePbar(self):
        logger.info('')
        self.pbar_widget.hide()
        self.statusBar.clearMessage() #Shoehorn
        QApplication.processEvents()



    def back_callback(self):
        logger.info("Returning Home...")
        self.viewer_stack_widget.setCurrentIndex(0)


    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self._hstry_listWidget:
            menu = QMenu()
            self.history_view_action = QAction('View')
            self.history_view_action.setStatusTip('View this alignment as a tree view')
            self.history_view_action.triggered.connect(self.view_historical_alignment)
            self.history_swap_action = QAction('Swap')
            self.history_swap_action.setStatusTip('Swap the settings of this historical alignment '
                                                  'with your current s settings')
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


    def store_var(self, name, var):
        setattr(cfg, name, var)

    def setControlPanelData(self):

        whitening = getData('data,defaults,whitening-factor')
        self._whiteningControl.setValue(float(whitening))

        poly = getData('data,defaults,corrective-polynomial')
        if (poly == None) or (poly == 'None'):
            self._polyBiasCombo.setCurrentText('None')
        else:
            self._polyBiasCombo.setCurrentText(str(poly))

        ww = getData(f'data,defaults,{cfg.data.scale},swim-window-px')
        self._swimWindowControl.setValue(int(ww[0]))








