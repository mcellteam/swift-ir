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
import qtawesome as qta
# from rechunker import rechunk
from qtpy.QtCore import Qt, QSize, QUrl, QThreadPool, Slot, Signal, QEvent, QTimer
from qtpy.QtGui import QPixmap, QIntValidator, QDoubleValidator, QIcon, QSurfaceFormat, QOpenGLContext, QFont, \
    QKeySequence, QMovie, QStandardItemModel, QColor, QCursor, QImage
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
    exist_aligned_zarr, configure_project_paths, isNeuroglancerRunning, \
    update_preferences_model, delete_recursive, initLogFiles, is_mac
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
from src.ui.flicker import Flicker

# from src.ui.components import AutoResizingTextEdit
from src.mendenhall_protocol import Mendenhall
import src.pairwise
# if cfg.DEV_MODE:
#     from src.ui.python_console import PythonConsole
from src.ui.python_console import PythonConsole


__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

# logger.critical('_Directory of this script: %s' % os.path.dirname(__file__))

class MainWindow(QMainWindow):
    resized = Signal()
    keyPressed = Signal(int)
    # alignmentFinished = Signal()
    updateTable = Signal()
    cancelMultiprocessing = Signal()
    sectionChanged = Signal()
    swimWindowChanged = Signal()

    def __init__(self, data=None):
        QMainWindow.__init__(self)
        self.app = QApplication.instance()
        self.setObjectName('mainwindow')
        self.window_title = 'AlignEM-SWiFT'
        self.setWindowTitle(self.window_title)
        self.setAutoFillBackground(True)
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

        font = QFont("Tahoma")
        QApplication.setFont(font)


    def initSizeAndPos(self, width, height):
        self.resize(width, height)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center() # cp PyQt5.QtCore.QPoint
        # cp.setX(cp.x() - 200)
        qr.moveCenter(cp)
        self.move(qr.topLeft())


    def resizeEvent(self, event):
        logger.info('')
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


    def _callbk_showHideCorrSpots(self):
        logger.info('')
        self.dw_corrspots.setVisible(cfg.project_tab.signalsAction.isChecked())
        if cfg.project_tab.signalsAction.isChecked():
            # w = self.csWidget.width()
            # self.csWidget.resize(QSize(w,200))
            self.updateCorrSignalsDrawer()




    def updateCorrSignalsDrawer(self):
        #             siz = cfg.data.image_size()
        #             ar = siz[0] / siz[1]  # aspect ratio
        #             self.corrSignalsList[i].setFixedSize(QSize(int(h*ar), h))

        # caller = inspect.stack()[1].function

        thumbs = cfg.data.get_signals_filenames()
        # logger.info('thumbs: %s' % str(thumbs))
        n = len(thumbs)
        snr_vals = cfg.data.snr_components()
        colors = cfg.glob_colors
        count = 0
        if cfg.data.current_method == 'grid-custom':
            for i in range(7):
                self.corrSignalsList[i].hide()
            regions = cfg.data.grid_custom_regions
            names = cfg.data.get_grid_custom_filenames()
            logger.info('names: %s' % str(names))
            for i in range(4):
                if regions[i]:
                    self.corrSignalsList[i].set_data(path=names[i], snr=snr_vals[count])
                    self.corrSignalsList[i].setStyleSheet(f"""border: 4px solid {colors[i]}; padding: 3px;""")
                    self.corrSignalsList[i].show()
                    count += 1
        else:
            for i in range(7):
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

        # logger.info("<<<< updateCorrSignalsDrawer")


    def _callbk_showHidePython(self):
        self.dw_console.setHidden(not self.dw_console.isHidden())
        self.pythonButton.setToolTip(("Hide Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)", "Show Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)")[self.dw_console.isHidden()])


    def _callbk_showHideNotes(self):
        self.dw_notes.setHidden(not self.dw_notes.isHidden())
        self.updateNotes()


    def _callbk_showHideHud(self):
        self.dw_monitor.setHidden(not self.dw_monitor.isHidden())
        self.hudButton.setToolTip(('Hide Head-up Display Tool Window', 'Show Head-up Display Tool Window')[self.dw_monitor.isHidden()])

    def _callbk_showHideSignals(self):
        logger.info('')
        if not self._isProjectTab():
            self.dw_corrspots.hide()
            return
        self.dw_corrspots.setHidden(not self.dw_corrspots.isHidden())
        if self.dw_corrspots.isVisible():
            self.updateCorrSignalsDrawer()

    def _callbk_showHideFlicker(self):
        logger.info('')
        if not self._isProjectTab():
            self.dw_flicker.hide()
            return
        self.dw_flicker.setHidden(not self.dw_flicker.isHidden())
        if self.dw_flicker.isHidden():
            self.flicker.stop()
        else:
            self.flicker.set_position(cfg.data.zpos)
            self.flicker.start()

    def autoscale(self, make_thumbnails=True):

        logger.critical('>>>> autoscale >>>>')

        #Todo This should check for existence of original source files before doing anything

        self.tell('Generating TIFF Scale Image Hierarchy...')
        cfg.nTasks = 3
        cfg.nCompleted = 0
        cfg.CancelProcesses = False
        # cfg.event = multiprocessing.Event()
        self.pbarLabel.setText('Task (0/%d)...' % cfg.nTasks)
        self.showZeroedPbar()
        self.set_status('Autoscaling...')
        # self.stopNgServer()  # 0202-
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
        if not self._isProjectTab():
            return
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
                a = """<span style='color: #ffe135;'>"""
                b = """</span>"""
                nl = '<br>'
                br = '&nbsp;'
                cfg.project_tab.detailsRuntime.setText(
                    f"Gen. Scales{br}{br}{br}{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['t_scaling']).rjust(9) +
                    f"Convert Zarr{br}{br}{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['t_scaling_convert_zarr']).rjust(9) +
                    f"Source Thumbs{br}{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['t_thumbs']).rjust(9) +
                    f"Compute Affines{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['scales'][s]['t_align']).rjust(9) +
                    f"Gen. Alignment{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['scales'][s]['t_generate']).rjust(9) +
                    f"Aligned Thumbs{br}{br}{br}:{a}" + (f"%.2fs{b}{nl}" % cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_aligned']).rjust(9) +
                    f"Corr Spot Thumbs{br}:{a}" + (f"%.2fs{b}" % cfg.data['data']['benchmarks']['scales'][s]['t_thumbs_spot']).rjust(9)
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

        # self.stopNgServer()  # 0202-

        t9 = time.time()
        dt = t9 - t0
        logger.critical(f'onAlignmentStart, time: = {dt}')


    def onAlignmentEnd(self, start, end):
        logger.info('Running Post-Alignment Tasks...')
        # self.alignmentFinished.emit()
        t0 = time.time()
        try:
            if self._isProjectTab():
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
            if self._isProjectTab():
                self.enableAllTabs()
                self._autosave()
                try:
                    if cfg.project_tab._tabs.currentIndex() == 3:
                        cfg.project_tab.snr_plot.initSnrPlot()
                except:
                    print_exception()

            t9 = time.time()
            dt = t9 - t0
            logger.critical(f'onAlignmentEnd, time: {dt}')


    def alignAll(self):
        if not self._isProjectTab():
            return

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
                self.tell('Resetting Skips...')
                cfg.data.clear_all_skips()
        else:
            self.warn('No Skips To Clear.')


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
        logger.info('updateEnabledButtons >>>>')
        if cfg.data:
            # self._btn_alignAll.setText('Align All Sections - %s' % cfg.data.scale_pretty())
            # self._btn_regenerate.setText('Regenerate All Sections - %s' % cfg.data.scale_pretty())
            self.gb_ctlActions.setTitle('%s Multiprocessing Commands' % cfg.data.scale_pretty())
            # self._btn_alignRange.setText('Regenerate\nAll %s' % cfg.data.scale_pretty())
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
                # self._btn_alignAll.setText('Re-Align All Sections (%s)' % cfg.data.scale_pretty())
                self._btn_alignAll.setText('Align All Sections')
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


    def layer_left(self):
        if self._isProjectTab():
            requested = cfg.data.zpos - 1
            logger.info(f'requested: {requested}')
            if requested >= 0:
                cfg.data.zpos = requested
                if getData('state,manual_mode'):
                    # cfg.project_tab.MA_layer_left()
                    # self.initAllViewers()
                    cfg.project_tab.initNeuroglancer()
                else:
                    cfg.emViewer.set_layer(requested)
                self.dataUpdateWidgets()
            else:
                self.warn(f'Invalid Index Request: {requested}')


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
            else:
                self.warn(f'Invalid Index Request: {requested}')


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

            if self.dw_corrspots.isVisible():
                self.updateCorrSignalsDrawer()

            cur = cfg.data.zpos
            if self.notes.isVisible():
                self.updateNotes()

            if self.dw_flicker.isVisible():
                self.flicker.set_position(cfg.data.zpos)

            self._btn_prevSection.setEnabled(cur > 0)
            self._btn_nextSection.setEnabled(cur < len(cfg.data) - 1)

            try:     self._sectionSlider.setValue(cur)
            except:  logger.warning('Section Slider Widget Failed to Update')
            try:     self._jumpToLineedit.setText(str(cur))
            except:  logger.warning('Current Layer Widget Failed to Update')
            try:     self._skipCheckbox.setChecked(not cfg.data.skipped())
            except:  logger.warning('Skip Toggle Widget Failed to Update')
            try:     self._bbToggle.setChecked(cfg.data.use_bb())
            except:  logger.warning('Bounding Box Toggle Failed to Update')

            if getData('state,manual_mode'):
                cfg.project_tab.dataUpdateMA()

            if cfg.project_tab._tabs.currentIndex() == 1:
                cfg.project_tab.project_table.table.selectRow(cur)

            if cfg.project_tab._tabs.currentIndex() == 2:
                cfg.project_tab.treeview_model.jumpToLayer()

            if cfg.project_tab._tabs.currentIndex() == 3:
                cfg.project_tab.snr_plot.updateLayerLinePos()

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
                if method == 'grid-default':       txt += f"Method{br*3}:{br}{a}Default{br}Grid{b}"
                elif method == 'grid-custom':       txt += f"Method{br*3}:{br}{a}Custom{br}Grid{b}"
                elif method == 'manual-hint':   txt += f"Method{br*3}:{br}{a}Manual,{br}Hint{b}"
                elif method == 'manual-strict': txt += f"Method{br*3}:{br}{a}Manual,{br}Strict{b}"
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
                if (cfg.data.zpos == 0) or cfg.data.skipped():
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

            self._btn_alignOne.setText('Re-Align Section #%d' %cfg.data.zpos)

        logger.info(f'<<<< dataUpdateWidgets [zpos={cfg.data.zpos}]')




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
            self.notes.setPlaceholderText('Enter notes about anything here...')
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

            try:
                self._jumpToLineedit.setText(str(requested))
            except:
                logger.warning('Current Section Widget Failed to Update')
                print_exception()

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
        logger.info('fn_scales_combobox [caller: %s] >>>>' % caller)
        if caller in ('main', 'scale_down', 'scale_up'):

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
        # self.tell("Loading project '%s'..." %cfg.data.dest())
        logger.critical("\n\nLoading project '%s'...\n" %cfg.data.dest())

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

        # self.tell('Updating UI...')
        self.dataUpdateWidgets() # 0.5878 -> 0.5887 ~.001s


        self._changeScaleCombo.setCurrentText(cfg.data.scale)

        self.setControlPanelData() #Added 2023-04-23

        logger.critical('Setting FPS spinbox value...')
        self._fps_spinbox.setValue(cfg.DEFAULT_PLAYBACK_SPEED)
        # cfg.project_tab.updateTreeWidget() #TimeConsuming!! dt = 0.58 - > dt = 1.10

        # dt = 1.1032602787017822
        self.updateEnabledButtons()
        self.updateMenus()
        self._resetSlidersAndJumpInput() #fast
        self.reload_scales_combobox() #fast
        self.enableAllTabs() #fast

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
        logger.critical(f'User Response: {response}')

    def exit_app(self):
        if self._exiting:
            self._exiting = 0
            if self.exit_dlg.isVisible():
                self.globTabsAndCpanel.children()[-1].hide()
            return

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
                font-family: Tahoma, sans-serif;
                border-color: #339933;
                border-width: 2px;
        }
            """
        self._exiting = 1
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
        # try:
        #
        #     self.pythonConsole.kernel_client.stop_channels()
        #     self.pythonConsole.kernel_manager.shutdown_kernel()
        # except:
        #     print_exception()
        #     self.warn('Having trouble shutting down Python console kernel')
        # finally:
        #     time.sleep(.4)

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
        self.cpanel.hide()

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
        self.cpanel.hide()



    def remote_view(self):
        self.tell('Opening Neuroglancer Remote Viewer...')
        browser = WebBrowser()
        browser.setUrl(QUrl('https://neuroglancer-demo.appspot.com/'))
        self.globTabs.addTab(browser, 'Neuroglancer')
        self._setLastTab()
        self.cpanel.hide()


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

            cfg.project_tab.zoomSlider.setValue( 1 / new_cs_scale )


    def incrementZoomIn(self):
        # logger.info('')
        if self._isProjectTab():
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
            # (Qt.Key_K, self._callbk_skipChanged),
            # (Qt.Key_N, self._callbk_showHideNotes)
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
        self.cpanel.hide()

    def google(self):
        logger.info('Opening Google Tab...')
        self.browser = WebBrowser(self)
        self.browser.setObjectName('web_browser')
        self.browser.setUrl(QUrl('https://www.google.com'))
        self.globTabs.addTab(self.browser, 'Google')
        self._setLastTab()
        self.cpanel.hide()

    def gpu_config(self):
        logger.info('Opening GPU Config...')
        browser = WebBrowser()
        browser.setUrl(QUrl('chrome://gpu'))
        self.globTabs.addTab(browser, 'GPU Configuration')
        self._setLastTab()
        self.cpanel.hide()

    def chromium_debug(self):
        logger.info('Opening Chromium Debugger...')
        browser = WebBrowser()
        browser.setUrl(QUrl('http://127.0.0.1:9000'))
        self.globTabs.addTab(browser, 'Debug Chromium')
        self._setLastTab()
        self.cpanel.hide()

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
                # cfg.project_tab.cpanel.hide()

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

            # cfg.project_tab.cpanel.show()

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
        if self.dw_console.isHidden():
            self.dw_console.show()
        else:
            self.dw_console.hide()


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

        self.combo_mode = QComboBox(self)
        # self.combo_mode.setStyleSheet('font-size: 11px; font-weight: 600; color: #1b1e23;')
        self.combo_mode.setFixedSize(130, 18)
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
        # self._jumpToLineedit.setStyleSheet('font-size: 11px; border-width: 0px;')
        self._jumpToLineedit.setFocusPolicy(Qt.ClickFocus)
        self._jumpToLineedit.setStatusTip(tip)
        self._jumpToLineedit.setFixedSize(QSize(36, 16))
        self._jumpToLineedit.returnPressed.connect(self.jump_to_layer)


        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(HWidget(QLabel('Section:'), self._jumpToLineedit))
        self._jumpToSectionWidget = QWidget()
        self._jumpToSectionWidget.setLayout(hbl)
        # self.toolbar.addWidget(self._sectionSlider)

        self._btn_automaticPlayTimer = QPushButton()
        self._btn_automaticPlayTimer.setIconSize(QSize(14,14))
        self._btn_automaticPlayTimer.setFixedSize(18,18)
        self._btn_automaticPlayTimer.setIcon(qta.icon('fa.play', color=cfg.ICON_COLOR))
        # self._btn_automaticPlayTimer.setIcon(QIcon('src/resources/play-button.png'))
        #0505
        self.automaticPlayTimer = QTimer(self)
        self._btn_automaticPlayTimer.clicked.connect(self.startStopTimer)

        def onTimer():
            logger.info('')
            # self.automaticPlayTimer.setInterval(1000 / self._fps_spinbox.value())
            self.automaticPlayTimer.setInterval(int(1000 / self._fps_spinbox.value()))
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
        hbl.setContentsMargins(4,0,4,0)
        hbl.addWidget(self._btn_automaticPlayTimer, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(self._sectionSlider, alignment=Qt.AlignmentFlag.AlignLeft)
        self._sectionSliderWidget.setLayout(hbl)

        lab = QLabel('Speed:')
        self._fps_spinbox = QDoubleSpinBox()
        self._fps_spinbox.setFixedHeight(18)
        self._fps_spinbox.setMinimum(.5)
        self._fps_spinbox.setMaximum(10)
        self._fps_spinbox.setSingleStep(.2)
        self._fps_spinbox.setDecimals(1)
        self._fps_spinbox.setSuffix('fps')
        self._fps_spinbox.setStatusTip('Playback Speed (frames/second)')
        self._fps_spinbox.setToolTip('Playback Speed (frames/second)')
        self._fps_spinbox.clear()

        '''scale combobox'''
        self._changeScaleCombo = QComboBox(self)
        self._changeScaleCombo.setMinimumWidth(134)
        self._changeScaleCombo.setFixedHeight(18)
        self._changeScaleCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._changeScaleCombo.currentTextChanged.connect(self.fn_scales_combobox)
        hbl.addWidget(self._changeScaleCombo, alignment=Qt.AlignmentFlag.AlignRight)


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

        self._btn_refreshTab = QPushButton()
        # self._btn_refreshTab.setStyleSheet("background-color: #161c20;")
        self._btn_refreshTab.setStyleSheet(button_gradient_style)
        self._btn_refreshTab.setToolTip("Refresh View (" + ('^','⌘')[is_mac()] + "R)")
        self._btn_refreshTab.setFixedSize(18,18)
        self._btn_refreshTab.setIconSize(QSize(16,16))
        self._btn_refreshTab.setIcon(qta.icon('fa.refresh', color='#161c20'))
        self._btn_refreshTab.clicked.connect(self.refreshTab)

        tb_button_size = QSize(64,18)

        tip = 'Show Notepad Tool Window'
        self.notesButton = QPushButton(' Notes')
        self.notesButton.setStyleSheet(button_gradient_style)
        self.notesButton.setStatusTip(tip)
        self.notesButton.setToolTip(tip)
        self.notesButton.setFixedSize(tb_button_size)
        self.notesButton.setIconSize(QSize(14,14))
        self.notesButton.setIcon(QIcon('src/resources/notepad-icon.png'))
        self.notesButton.clicked.connect(self._callbk_showHideNotes)

        tip = "Show Python Console Tool Window (" + ('^', '⌘')[is_mac()] + "P)"
        self.pythonButton = QPushButton('Python')
        self.pythonButton.setStyleSheet(button_gradient_style)
        self.pythonButton.setToolTip(tip)
        self.pythonButton.setStatusTip(tip)
        self.pythonButton.setFixedSize(tb_button_size)
        self.pythonButton.setIconSize(QSize(14,14))
        self.pythonButton.setIcon(QIcon('src/resources/python-icon.png'))
        self.pythonButton.clicked.connect(self._callbk_showHidePython)

        tip = 'Show Head-up Display Tool Window'
        self.hudButton = QPushButton(' HUD')
        self.hudButton.setStyleSheet(button_gradient_style)
        self.hudButton.setToolTip(tip)
        self.hudButton.setStatusTip(tip)
        self.hudButton.setFixedSize(tb_button_size)
        self.hudButton.setIconSize(QSize(14,14))
        # self.hudButton.setIcon(QIcon('src/resources/python-icon.png'))
        self.hudButton.setIcon(qta.icon("mdi.monitor", color='#161c20'))
        self.hudButton.clicked.connect(self._callbk_showHideHud)


        tip = 'Show Flicker Tool Window'
        self.flickerButton = QPushButton(' Flicker')
        self.flickerButton.setStyleSheet(button_gradient_style)
        self.flickerButton.setToolTip(tip)
        self.flickerButton.setStatusTip(tip)
        self.flickerButton.setFixedSize(tb_button_size)
        self.flickerButton.setIconSize(QSize(14,14))
        # self.flickerButton.setIcon(QIcon('src/resources/python-icon.png'))
        self.flickerButton.setIcon(qta.icon("mdi.reiterate", color='#161c20'))
        self.flickerButton.clicked.connect(self._callbk_showHideFlicker)

        tip = 'Show Correlation Signals Tool Window'
        self.csButton = QPushButton('Signals')
        self.csButton.setStyleSheet(button_gradient_style)
        self.csButton.setToolTip(tip)
        self.csButton.setStatusTip(tip)
        self.csButton.setFixedSize(tb_button_size)
        self.csButton.setIconSize(QSize(14,14))
        self.csButton.setIcon(qta.icon("fa.signal", color='#161c20'))
        self.csButton.clicked.connect(self._callbk_showHideSignals)

        self._detachNgButton = QPushButton()
        # self._detachNgButton.setStyleSheet("background-color: #161c20;")
        self._detachNgButton.setStyleSheet(button_gradient_style)
        self._detachNgButton.setFixedSize(18,18)
        self._detachNgButton.setIconSize(QSize(16,16))
        self._detachNgButton.setIcon(qta.icon("fa.external-link-square", color='#161c20'))
        # self._detachNgButton.setIcon(QIcon('src/resources/popout-icon.png'))
        # self._detachNgButton.setIconSize(QSize(13, 13))
        self._detachNgButton.clicked.connect(self.detachNeuroglancer)
        self._detachNgButton.setToolTip('Detach Neuroglancer (open in a separate window)')

        # self.toolbar.addWidget(QLabel(' '))
        self.toolbar.addWidget(self._btn_refreshTab)
        self.toolbar.addWidget(QLabel(' '))
        self.toolbar.addWidget(self.combo_mode)
        self.toolbar.addWidget(self._changeScaleCombo)
        self.toolbar.addWidget(ExpandingWidget(self))
        self.toolbar.addWidget(self._jumpToLineedit)
        self.toolbar.addWidget(self._sectionSliderWidget)
        self.toolbar.addWidget(self._fps_spinbox)
        self.toolbar.addWidget(ExpandingWidget(self))
        self.toolbar.addWidget(self.notesButton)
        self.toolbar.addWidget(self.pythonButton)
        self.toolbar.addWidget(self.hudButton)
        self.toolbar.addWidget(self.flickerButton)
        self.toolbar.addWidget(self.csButton)
        self.toolbar.addWidget(self._detachNgButton)
        self.toolbar.addWidget(self.info_button_buffer_label)
        self.toolbar.layout().setSpacing(4)


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
            self.cpanel.show()
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

        if tabtype == 'OpenProject':
            configure_project_paths()
            self._getTabObject().user_projects.set_data()
            self.cpanel.hide()
            # self.dw_corrspots_layout.hide()
            self.dw_corrspots.hide()
            self.dw_flicker.hide()


        elif tabtype == 'ProjectTab':
            self.cpanel.show()
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

            if getData('state,manual_mode'):
                self._changeScaleCombo.setEnabled(False)

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
        self.ngShowAxisLinesAction.setText('Axes')
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
        self.ngShowUiControlsAction.setText('NG Controls')
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
        self.ngShowYellowFrameAction.setText('Bounds')
        self.ngShowYellowFrameAction.triggered.connect(fn)
        viewMenu.addAction(self.ngShowYellowFrameAction)

        self.ngShowSnrAction = QAction(self)
        def fn():
            if self._isProjectTab():
                cfg.project_tab.detailsSNR.setVisible(self.ngShowSnrAction.isChecked())
                self.dataUpdateWidgets()

        self.ngShowSnrAction.triggered.connect(fn)
        self.ngShowSnrAction.setCheckable(True)
        self.ngShowSnrAction.setText('SNR')
        viewMenu.addAction(self.ngShowSnrAction)

        self.ngShowAffineAction = QAction(self)
        def fn():
            if self._isProjectTab():
                cfg.project_tab.detailsAFM.setVisible(self.ngShowAffineAction.isChecked())
                self.dataUpdateWidgets()

        self.ngShowAffineAction.triggered.connect(fn)
        self.ngShowAffineAction.setCheckable(True)
        self.ngShowAffineAction.setText('Affine')
        viewMenu.addAction(self.ngShowAffineAction)

        self.ngShowSectionDetailsAction = QAction(self)
        def fn():
            if self._isProjectTab():
                cfg.project_tab.detailsSection.setVisible(self.ngShowSectionDetailsAction.isChecked())
                self.dataUpdateWidgets()
        self.ngShowSectionDetailsAction.triggered.connect(fn)
        self.ngShowSectionDetailsAction.setCheckable(True)
        self.ngShowSectionDetailsAction.setText('Section')
        viewMenu.addAction(self.ngShowSectionDetailsAction)


        self.ngShowRuntimesAction = QAction(self)
        def fn():
            if self._isProjectTab():
                cfg.project_tab.detailsRuntime.setVisible(self.ngShowRuntimesAction.isChecked())
                self.dataUpdateWidgets()
        self.ngShowRuntimesAction.triggered.connect(fn)
        self.ngShowRuntimesAction.setCheckable(True)
        self.ngShowRuntimesAction.setText('Runtimes')
        viewMenu.addAction(self.ngShowRuntimesAction)
        
        self.toggleCorrSigsAction = QAction(self)
        def fn():
            if self._isProjectTab():
                cfg.project_tab.signalsAction.toggle()
                self._callbk_showHideCorrSpots()
        # self.toggleCorrSpotsAction.setCheckable(True)
        # self.toggleCorrSpotsAction.setChecked(getOpt('neuroglancer,SHOW_YELLOW_FRAME'))
        # self.ngShowYellowFrameAction.setText(('Show Boundary', 'Hide Boundary')[getOpt('neuroglancer,SHOW_YELLOW_FRAME')])
        self.toggleCorrSigsAction.setText('Toggle Correlation Signals')
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
            val = float(self._whiteningControl.value())
            cfg.data.default_whitening = val
            self.tell('Whitening Factor is set to %d' % val)


    def _valueChangedPolyOrder(self):
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if self._polyBiasCombo.currentText() == 'None':
                cfg.data.default_poly_order = None
                self.tell('Corrective Polynomial Order is set to None')
            else:
                val = int(self._polyBiasCombo.currentText()[-1])
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
        # long_button_size = QSize(132, 14)
        long_button_size = QSize(128, 14)
        left     = Qt.AlignmentFlag.AlignLeft
        right    = Qt.AlignmentFlag.AlignRight

        ctl_lab_style = 'color: #ede9e8;'

        tip = 'Whether to include the current section'
        self._lab_keep_reject = QLabel('Include:')
        self._lab_keep_reject.setStyleSheet(ctl_lab_style)
        self._lab_keep_reject.setStatusTip(tip)
        self._skipCheckbox = ToggleSwitch()
        self._skipCheckbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._skipCheckbox.stateChanged.connect(self._callbk_skipChanged)
        self._skipCheckbox.stateChanged.connect(self._callbk_unsavedChanges)
        self._skipCheckbox.setStatusTip(tip)
        self._skipCheckbox.setEnabled(False)


        tip = 'Use all the images (include all)'
        self._btn_clear_skips = QPushButton('Reset')
        self._btn_clear_skips.setEnabled(False)
        self._btn_clear_skips.setStyleSheet("font-size: 10px;")
        self._btn_clear_skips.setStatusTip(tip)
        self._btn_clear_skips.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_clear_skips.clicked.connect(self.clear_skips)
        self._btn_clear_skips.setFixedSize(button_size)

        tip = "Whitening factor parameter used by SWIM (defaults to -0.68)"
        lab = QLabel("Whitening\nFactor:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(left)
        self._whiteningControl = QDoubleSpinBox(self)
        self._whiteningControl.setStyleSheet("font-size: 10px;")
        self._whiteningControl.setFixedHeight(12)
        self._whiteningControl.valueChanged.connect(self._callbk_unsavedChanges)
        self._whiteningControl.valueChanged.connect(self._valueChangedWhitening)
        # self._whiteningControl.setValue(cfg.DEFAULT_WHITENING)
        self._whiteningControl.setFixedSize(std_input_size)
        self._whiteningControl.setDecimals(2)
        self._whiteningControl.setSingleStep(.01)
        self._whiteningControl.setMinimum(-2)
        self._whiteningControl.setMaximum(2)


        tip = f"The region size SWIM uses for computing alignment, specified as pixels " \
              f"width. (defaults to {cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC * 100}% of image width)"
        lab = QLabel("SWIM\nWindow:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(left)
        self._swimWindowControl = QSpinBox(self)
        self._swimWindowControl.setStyleSheet("font-size: 10px;")
        self._swimWindowControl.setSuffix('px')
        self._swimWindowControl.setMaximum(9999)
        self._swimWindowControl.setFixedHeight(12)

        def fn():
            # logger.info('')
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info(f'caller: {caller}')
                # cfg.data.set_swim_window_global(float(self._swimWindowControl.value()) / 100.)
                # cfg.data.set_swim_window_px(self._swimWindowControl.value())
                # setData(f'data,scales,{cfg.data.scale},')
                cfg.data.set_auto_swim_windows_to_default(factor=float(self._swimWindowControl.value()/cfg.data.image_size()[0]))
                self.swimWindowChanged.emit()

        self._swimWindowControl.valueChanged.connect(fn)
        self._swimWindowControl.valueChanged.connect(self._callbk_unsavedChanges)
        self._swimWindowControl.setFixedSize(std_input_size)

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
        self._btn_prevSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_prevSection.setStatusTip(tip)
        self._btn_prevSection.clicked.connect(self.layer_left)
        self._btn_prevSection.setFixedSize(QSize(16, 16))
        self._btn_prevSection.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))
        self._btn_prevSection.setEnabled(False)

        tip = 'Go To Next Section.'
        self._btn_nextSection = QPushButton()
        self._btn_nextSection.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_nextSection.setStatusTip(tip)
        self._btn_nextSection.clicked.connect(self.layer_right)
        self._btn_nextSection.setFixedSize(QSize(16, 16))
        self._btn_nextSection.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))
        self._btn_nextSection.setEnabled(False)

        self._sectionChangeWidget = QWidget()
        self._sectionChangeWidget.setLayout(HBL(self._btn_prevSection, self._btn_nextSection))
        self._sectionChangeWidget.setAutoFillBackground(True)

        tip = 'Go To Previous Scale.'
        self._scaleDownButton = QPushButton()
        self._scaleDownButton.setEnabled(False)
        self._scaleDownButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleDownButton.setStatusTip(tip)
        self._scaleDownButton.clicked.connect(self.scale_down)
        self._scaleDownButton.setFixedSize(QSize(16, 16))
        self._scaleDownButton.setIcon(qta.icon("fa.arrow-left", color=ICON_COLOR))

        tip = 'Go To Next Scale.'
        self._scaleUpButton = QPushButton()
        self._scaleUpButton.setEnabled(False)
        self._scaleUpButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scaleUpButton.setStatusTip(tip)
        self._scaleUpButton.clicked.connect(self.scale_up)
        self._scaleUpButton.setFixedSize(QSize(16, 16))
        self._scaleUpButton.setIcon(qta.icon("fa.arrow-right", color=ICON_COLOR))

        self._scaleSetWidget = QWidget()
        self._scaleSetWidget.setLayout(HBL(self._scaleDownButton, self._scaleUpButton))

        # self.navControls = QWidget()

        fl = QFormLayout()
        fl.setContentsMargins(2,2,2,2)
        fl.setSpacing(4)
        fl.addRow('Include: ', self._skipCheckbox)
        fl.addRow('Section:', self._sectionChangeWidget)
        fl.addRow('Scale:', self._scaleSetWidget)
        # self.navControls.setAutoFillBackground(True)
        # self.navControls.setLayout(fl)
        self.navControls = QGroupBox()
        self.navControls.setContentsMargins(0, 0, 0, 0)
        self.navControls.setObjectName('gb_cpanel')
        self.navControls.setLayout(fl)

        # lab = QLabel('Scale:')
        # lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #141414;')
        # self._ctlpanel_changeScale = QWidget()
        # lay = QHBoxLayout()
        # lay.setContentsMargins(0, 0, 0, 0)
        # lay.addWidget(lab, alignment=right)
        # lay.addWidget(self._scaleSetWidget, alignment=left)

        # self._ctlpanel_changeScale.setLayout(lay)

        tip = 'Align and generate all sections.'
        self._btn_alignAll = QPushButton('Align All')
        self._btn_alignAll.setEnabled(False)
        # self._btn_alignAll.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #141414;")
        self._btn_alignAll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignAll.setStatusTip(tip)
        self._btn_alignAll.clicked.connect(self.alignAll)
        self._btn_alignAll.setFixedSize(long_button_size)

        tip = 'Align and regenerate the current section only'
        self._btn_alignOne = QPushButton('Align One')
        self._btn_alignOne.setStatusTip(tip)
        self._btn_alignOne.setEnabled(False)
        # self._btn_alignOne.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #141414;")
        self._btn_alignOne.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignOne.clicked.connect(self.alignOne)
        self._btn_alignOne.setFixedSize(long_button_size)

        tip = 'The range of sections to align for the align range button.'
        self.sectionRangeSlider = RangeSlider()
        self.sectionRangeSlider.setMinimumWidth(120)
        self.sectionRangeSlider.setStatusTip(tip)
        self.sectionRangeSlider.setStyleSheet('border-radius: 2px;')
        self.sectionRangeSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.sectionRangeSlider.setFixedWidth(100)
        self.sectionRangeSlider.setMinimumWidth(40)
        self.sectionRangeSlider.setMaximumWidth(150)
        self.sectionRangeSlider.setFixedHeight(16)
        # self.sectionRangeSlider.setMaximumWidth(long_button_size.width() * 2)
        # self.sectionRangeSlider.setMaximumHeight(30)
        self.sectionRangeSlider.setMin(0)
        self.sectionRangeSlider.setStart(0)

        self.startRangeInput = QLineEdit()
        # self.startRangeInput.setStyleSheet("background-color: #f3f6fb;")
        self.startRangeInput.setAlignment(Qt.AlignCenter)
        self.startRangeInput.setFixedSize(30,16)
        self.startRangeInput.setEnabled(False)

        self.endRangeInput = QLineEdit()
        # self.endRangeInput.setStyleSheet("background-color: #f3f6fb;")
        self.endRangeInput.setAlignment(Qt.AlignCenter)
        self.endRangeInput.setFixedSize(30,16)
        self.endRangeInput.setEnabled(False)

        self.rangeInputWidget = HWidget(self.startRangeInput, QLabel(':'), self.endRangeInput)
        self.rangeInputWidget.setMaximumWidth(140)
        self.rangeInputWidget.setStatusTip(tip)

        def updateRangeButton():
            a = self.sectionRangeSlider.start()
            b = self.sectionRangeSlider.end()
            self._btn_alignRange.setText('Re-Align Sections #%d to #%d' % (a,b))

        self.sectionRangeSlider.startValueChanged.connect(lambda val: self.startRangeInput.setText(str(val)))
        self.sectionRangeSlider.startValueChanged.connect(updateRangeButton)
        self.sectionRangeSlider.endValueChanged.connect(lambda val: self.endRangeInput.setText(str(val)))
        self.sectionRangeSlider.endValueChanged.connect(updateRangeButton)
        self.startRangeInput.textChanged.connect(lambda val: self.sectionRangeSlider.setStart(int(val)))
        self.endRangeInput.textChanged.connect(lambda val: self.sectionRangeSlider.setEnd(int(val)))

        self._btn_alignRange = QPushButton('Realign Range')
        self._btn_alignRange.setEnabled(False)
        # self._btn_alignRange.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #141414;")
        self._btn_alignRange.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_alignRange.setStatusTip(tip)
        self._btn_alignRange.clicked.connect(self.alignRange)
        self._btn_alignRange.setFixedSize(long_button_size)

        tip = 'Whether to auto-generate aligned images following alignment.'
        self._toggleAutogenerate = ToggleSwitch()
        self._toggleAutogenerate.stateChanged.connect(self._toggledAutogenerate)
        self._toggleAutogenerate.stateChanged.connect(self._callbk_unsavedChanges)
        self._toggleAutogenerate.setStatusTip(tip)
        self._toggleAutogenerate.setChecked(True)
        self._toggleAutogenerate.setEnabled(False)

        tip = 'Polynomial bias correction (defaults to None), alters the generated images including their width and height.'
        self._polyBiasCombo = QComboBox(self)
        # self._polyBiasCombo.setStyleSheet("font-size: 10px; padding-left: 6px;")
        self._polyBiasCombo.currentIndexChanged.connect(self._valueChangedPolyOrder)
        self._polyBiasCombo.currentIndexChanged.connect(self._callbk_unsavedChanges)
        self._polyBiasCombo.setStatusTip(tip)
        self._polyBiasCombo.addItems(['None', 'poly 0°', 'poly 1°', 'poly 2°', 'poly 3°', 'poly 4°'])
        self._polyBiasCombo.setCurrentText(str(cfg.DEFAULT_POLY_ORDER))
        self._polyBiasCombo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._polyBiasCombo.setFixedSize(QSize(60, 16))
        self._polyBiasCombo.setEnabled(False)
        self._polyBiasCombo.lineEdit()


        tip = 'Bounding box is only applied upon "Align All" and "Regenerate". Caution: Turning this ON may ' \
              'significantly increase the size of generated images.'
        self._bbToggle = ToggleSwitch()
        self._bbToggle.setStatusTip(tip)
        self._bbToggle.toggled.connect(self._callbk_bnding_box)
        self._bbToggle.setEnabled(False)


        tip = "Recompute cumulative affine and generate new images" \
              "based on the current Null Bias and Bounding Box presets."
        self._btn_regenerate = QPushButton('Regenerate All Images')
        # self._btn_regenerate.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #141414; ")
        self._btn_regenerate.setEnabled(False)
        self._btn_regenerate.setStatusTip(tip)
        self._btn_regenerate.clicked.connect(lambda: self.regenerate(scale=cfg.data.scale))
        self._btn_regenerate.setFixedSize(long_button_size)

        '''_wdg_alignButtons'''

        # hbl.addWidget(self._ctlpanel_applyAllButton)

        # self._btn_regenerate.setAutoFillBackground(True)
        # self._btn_alignOne.setAutoFillBackground(True)
        # # self.sectionRangeSlider.setAutoFillBackground(True)
        # self.rangeInputWidget.setAutoFillBackground(True)
        # self._btn_alignRange.setAutoFillBackground(True)
        # self._btn_alignAll.setAutoFillBackground(True)
        fl = QFormLayout()
        # fl.setAlignment(Qt.AlignTop)
        fl.setContentsMargins(2,0,2,0)
        fl.setSpacing(2)
        fl.addWidget(self._btn_regenerate)
        fl.addWidget(self._btn_alignOne)
        fl.addWidget(self._btn_alignAll)
        self.cpButtonsLeft = QWidget()
        self.cpButtonsLeft.setContentsMargins(0,0,0,0)
        self.cpButtonsLeft.setAutoFillBackground(True)
        self.cpButtonsLeft.setLayout(fl)

        self.cpButtonsRight = QWidget()
        self.cpButtonsRight.setContentsMargins(0,0,0,0)
        fl.setContentsMargins(2,0,2,0)
        fl = QFormLayout()
        fl.setSpacing(4)
        range_widget = HWidget(QLabel('Range:'), ExpandingWidget(self), self.rangeInputWidget, ExpandingWidget(self))
        range_widget.setMaximumWidth(400)
        fl.addWidget(range_widget)
        # fl.addWidget(self.sectionRangeSlider)
        fl.addWidget(HWidget(self._btn_alignRange))
        self.cpButtonsRight.setLayout(fl)

        self.gb_ctlActions = QGroupBox("Scale Actions")
        self.gb_ctlActions.setObjectName("gb_cpanel")
        # self.gb_ctlActions.setFixedWidth(500)
        # vw_l = VWidget(ExpandingWidget(self), self.cpButtonsLeft)
        # vw_r = VWidget(ExpandingWidget(self), self.cpButtonsRight)
        # self.gb_ctlActions_layout = HBL(vw_l, vw_r)

        self.gb_ctlActions_layout = HBL()
        self.gb_ctlActions_layout.setContentsMargins(0,0,0,0)
        self.gb_ctlActions_layout.addWidget(self.cpButtonsLeft, alignment=Qt.AlignBaseline)
        self.gb_ctlActions_layout.addWidget(self.cpButtonsRight, alignment=Qt.AlignVCenter)
        self.gb_ctlActions.setLayout(self.gb_ctlActions_layout)

        style = """
            QWidget{
                background-color: #222222;
            }
            QPushButton {
                color: #161c20;
                background-color: #f3f6fb;
                font-size: 9px;
                border-radius: 3px;
            }
            QPushButton:enabled {
                font-weight: 400;
                border-color: #f3f6fb;
            }
            QPushButton:enabled:hover {
                border-color: #339933;
            }
            QPushButton:disabled {
                color: #555555;
                background-color: #222222;
                font-weight: 200;
                border-color: #555555;
            }
            QLabel {
                font-size: 10px;
                font-family: Tahoma, sans-serif;
                color: #ede9e8;
                /*font-weight: 600;*/
            }
            QDoubleSpinBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 3px;
            }
            QSpinBox {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 3px;
            }
            QLineEdit {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 11px;
                border-radius: 3px;
            }
            QComboBox {
                background-color: #f3f6fb;
                color: #161c20;
                font-size: 10px;
            }
            
            QComboBox QAbstractItemView 
            {
                min-width: 50px;
            }
            
            QAbstractItemView {
                background-color: #f3f6fb;
                color: #141414;
                font-size: 10px;
            }
            QGroupBox#gb_cpanel {
                border: 1px solid #ede9e8;
                border-radius: 4px;
                padding: 2px;
                padding-bottom: 0px;
                margin-top: 0px;
                margin-bottom: 0px;
                font-size: 9px;
            }
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
        """

        fl = QFormLayout()
        fl.setContentsMargins(2,10,2,2)
        fl.setSpacing(1)
        # fl.addRow('Include: ', self._skipCheckbox)
        fl.addRow('Generate TIFFs: ', self._toggleAutogenerate)
        fl.addRow('Bounding Box: ', self._bbToggle)
        fl.addRow('Corrective Bias: ', self._polyBiasCombo)
        # fl.setAlignment(Qt.AlignBaseline)
        fl.setAlignment(Qt.AlignBottom)

        self.outputSettings = QGroupBox("Output Settings")
        self.outputSettings.setObjectName('gb_cpanel')
        self.outputSettings.setLayout(fl)

        # self.combos = QWidget()
        # self.combos.setFixedHeight(72)
        fl = QFormLayout()
        fl.setFormAlignment(Qt.AlignCenter)
        # fl.setAlignment(Qt.AlignTop)
        fl.setContentsMargins(2,2,8,2)
        fl.setSpacing(8)
        fl.addRow('Grid Width (px): ', self._swimWindowControl)
        fl.addRow('Whitening Factor: ', self._whiteningControl)
        # self.combos.setLayout(fl)

        self.swimSettings = QGroupBox("SWIM Alignment Settings")
        self.swimSettings.setObjectName('gb_cpanel')
        self.swimSettings.setLayout(fl)

        '''self._wdg_alignBut
        tons <- self.cpButtonsLeft <- self.cpanel_hwidget1'''
        w = QWidget()
        w.setContentsMargins(0,0,0,0)
        hbl = HBL()
        # hbl.setSpacing(8)
        w.setLayout(hbl)
        # hbl.addWidget(QLabel('  '))
        # hbl.addWidget(ExpandingWidget(self))
        hbl.addStretch(3)
        hbl.addWidget(self.navControls)
        hbl.addStretch(1)
        hbl.addWidget(self.swimSettings)
        hbl.addStretch(1)
        hbl.addWidget(self.gb_ctlActions)
        hbl.addStretch(1)
        hbl.addWidget(self.outputSettings)
        hbl.addStretch(3)

        lab = QLabel('Control Panel')
        lab.setStyleSheet('font-size: 10px; font-weight: 600; color: #f3f6fb; padding-left: 1px; padding-top: 1px;')

        self.cpanelVertLabel = VerticalLabel('Control Panel', font_color='#ede9e8', font_size=14)

        # self.cpanel = VWidget(lab, w)
        # self.cpanel = HWidget(self.cpanelVertLabel,ExpandingWidget(self), w)
        self.cpanel = w
        self.cpanel.setContentsMargins(8,6,8,4)
        self.cpanel.setFixedHeight(86)
        # self.cpanel.layout.setAlignment(Qt.AlignHCenter)
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
        self.cpanel.setStyleSheet(style)


    def initUI(self):
        '''Initialize Main UI'''
        logger.info(f'Current Directory: {os.getcwd()}')

        std_button_size = QSize(96, 20)
        normal_button_size = QSize(64, 24)

        with open('src/style/controls.qss', 'r') as f:
            lower_controls_style = f.read()

        logger.info('Creating HUD...')
        '''Headup Display'''
        # self.hud = HeadupDisplay(self.app)
        self.hud = HeadupDisplay(self.app)
        self.hud.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # self.hud.setObjectName('HUD')
        self.hud.set_theme_default()
        self.dw_monitor = QDockWidget('Head-up Display (Process Monitor)', self)
        self.dw_monitor.visibilityChanged.connect(lambda: self.hudButton.setText((' Hide', ' HUD')[self.dw_monitor.isHidden()]))

        self.dw_monitor.setObjectName('Dock Widget HUD')
        self.dw_monitor.setStyleSheet("""
        QDockWidget {color: #161c20;}
        QDockWidget::title {
                    background-color: #daebfe;
                    color: #161c20;
                    font-weight: 600;
                    padding-left: 5px;
                    text-align: left;
                }""")
        self.dw_monitor.setWidget(self.hud)
        self.dw_monitor.hide()
        # self.dw_hud.setLayout(HBL(self.hud))
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

        logger.info('HUD created.')

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


        self.cs0 = CorrSignalThumbnail(self)
        self.cs1 = CorrSignalThumbnail(self)
        self.cs2 = CorrSignalThumbnail(self)
        self.cs3 = CorrSignalThumbnail(self)
        self.cs4 = CorrSignalThumbnail(self)
        self.cs5 = CorrSignalThumbnail(self)
        self.cs6 = CorrSignalThumbnail(self)
        self.corrSignalsList = [self.cs0, self.cs1, self.cs2, self.cs3,
                                self.cs4, self.cs5, self.cs6 ]
        self.cs_layout = HBL()
        self.cs_layout.setContentsMargins(2, 2, 2, 2)
        self.cs_layout.addWidget(self.cs0)
        self.cs_layout.addWidget(self.cs1)
        self.cs_layout.addWidget(self.cs2)
        self.cs_layout.addWidget(self.cs3)
        self.cs_layout.addWidget(self.cs4)
        self.cs_layout.addWidget(self.cs5)
        self.cs_layout.addWidget(self.cs6)
        self.cs_layout.addWidget(ExpandingWidget(self))

        self.lab_corr_signals = QLabel('No Signals Found for Current Alignment Method.')
        self.lab_corr_signals.setMaximumHeight(18)
        self.lab_corr_signals.setStyleSheet('color: #ede9e8;')
        self.lab_corr_signals.setContentsMargins(8,0,0,0)

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
        self.notes.setMinimumWidth(120)
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

        self.dw_notes = QDockWidget('Notes', self)
        self.dw_notes.visibilityChanged.connect(
            lambda: self.notesButton.setText((' Hide', ' Notes')[self.dw_notes.isHidden()]))
        # self.dw_notes.visibilityChanged.connect(lambda: )
        self.dw_notes.visibilityChanged.connect(lambda: self.notesButton.setToolTip(('Hide Notepad Tool Window', 'Show Notepad Tool Window')[self.dw_notes.isHidden()]))


        self.dw_notes.setStyleSheet("""
        QDockWidget {color: #161c20;}
        
        QDockWidget::title {
            background-color: #FFE873;
            font-weight: 600;
            padding-left: 5px;
            text-align: left;
        }""")
        self.dw_notes.setWidget(self.notes)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dw_notes)
        self.dw_notes.hide()


        tip = 'Show/Hide Contrast and Brightness Shaders'
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


        '''Tabs Global Widget'''
        self.globTabs = QTabWidget(self)
        # self.globTabs.setContentsMargins(4,4,4,4)
        self.globTabs.setContentsMargins(0,0,0,0)
        # self.globTabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        # self.pythonConsole.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # self.pythonConsole.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pythonConsole.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # self.pythonConsole.resize(QSize(600,600))

        self.pythonConsole.setStyleSheet("""
        font-size: 10px;
        background-color: #f3f6fb;
        color: #161c20;
        font-family: 'Andale Mono', 'Ubuntu Mono', monospace;
        border-radius: 5px;
        """)

        self.dw_console = QDockWidget('Python Console', self)
        self.dw_console.visibilityChanged.connect(
            lambda: self.pythonButton.setText((' Hide', 'Python')[self.dw_console.isHidden()]))
        self.dw_console.visibilityChanged.connect(lambda: self.pythonButton.setToolTip(('Hide Python Console Tool Window', 'Show Python Console Tool Window')[self.dw_console.isHidden()]))
        self.dw_console.setStyleSheet("""QDockWidget::title {
            text-align: left; /* align the text to the left */
            background: #4B8BBE;
            padding-left: 5px;
            font-weight: 600;
        }""")
        self.dw_console.setWidget(self.pythonConsole)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_console)
        self.dw_console.hide()

        self.flicker = Flicker(self)
        self.flicker.setMaximumSize(QSize(256,256))

        self.dw_flicker = QDockWidget('Flicker', self)

        self.dw_flicker.visibilityChanged.connect(lambda: self.flickerButton.setText((' Hide', ' Flicker')[self.dw_flicker.isHidden()]))
        self.dw_flicker.visibilityChanged.connect(lambda: self.flickerButton.setToolTip(('Hide Flicker Tool Window', 'Show Flicker Tool Window')[self.dw_flicker.isHidden()]))

        self.dw_flicker.setStyleSheet("""QDockWidget::title {
            text-align: left; /* align the text to the left */
            background: #380282;
            padding-left: 5px;
            font-weight: 600;
        }""")
        self.dw_flicker.setWidget(self.flicker)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_flicker)
        self.dw_flicker.hide()

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
        buttonBrowserRefresh.setIcon(qta.icon("fa.refresh", color=cfg.ICON_COLOR))
        buttonBrowserRefresh.setFixedSize(QSize(22,22))
        buttonBrowserRefresh.clicked.connect(browser_reload)

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

        self.dw_corrspots = QDockWidget('Correlation Signals', self)
        self.dw_corrspots.setStyleSheet("""
        QDockWidget {color: #ede9e8;}
        QDockWidget::title {
                    background-color: #306998;
                    color: #161c20;
                    font-weight: 600;
                    padding-left: 5px;
                    text-align: left;
                }""")
        self.dw_corrspots.visibilityChanged.connect(lambda: self.csButton.setText((' Hide', 'Signals')[self.dw_corrspots.isHidden()]))
        self.dw_corrspots.visibilityChanged.connect(lambda: self.csButton.setToolTip(('Hide Correlation Signals Tool Window', 'Show Correlation Signals Tool Window')[self.dw_corrspots.isHidden()]))

        def fn():
            caller = inspect.stack()[1].function
            logger.info(f'caller: {caller}')
            if caller == 'main':
                for i, dock in enumerate(self.findChildren(QDockWidget)):
                    title = dock.windowTitle()
                    area = self.dockWidgetArea(dock)
                    if title == 'Correlation Signals':

                        if area in (Qt.LeftDockWidgetArea, Qt.RightDockWidgetArea):
                            self.cs_layout = VBL()
                            logger.info('Stacking correlation signals vertically...')
                        else:
                            # self.cs_layout = HBL()
                            self.cs_layout = QGridLayout()
                            logger.info('Stacking correlation signals horizontally...')
                        self.cs0 = CorrSignalThumbnail(self)
                        self.cs1 = CorrSignalThumbnail(self)
                        self.cs2 = CorrSignalThumbnail(self)
                        self.cs3 = CorrSignalThumbnail(self)
                        # self.cs4 = CorrSignalThumbnail(self)
                        # self.cs5 = CorrSignalThumbnail(self)
                        # self.cs6 = CorrSignalThumbnail(self)
                        self.corrSignalsList = [self.cs0, self.cs1, self.cs2, self.cs3,
                                                self.cs4, self.cs5, self.cs6]
                        self.cs_layout.setContentsMargins(2, 2, 2, 2)
                        self.cs_layout.addWidget(self.cs0,0,0)
                        self.cs_layout.addWidget(self.cs1,1,0)
                        self.cs_layout.addWidget(self.cs2,2,0)
                        self.cs_layout.addWidget(self.cs3,3,0)
                        # self.cs_layout.addWidget(self.cs4,0,0)
                        # self.cs_layout.addWidget(self.cs5,0,0)
                        # self.cs_layout.addWidget(self.cs6,0,0)
                        # self.cs_layout.addWidget(ExpandingWidget(self))
                        self.csWidget.setLayout(self.cs_layout)
                        # self.dw_corrspots.setWidget(self.csWidget)
            self.csWidget = QWidget()
            self.csWidget.setObjectName('Correlation Signals')
            self.csWidget.setLayout(self.cs_layout)
            self.dw_corrspots.setWidget(self.csWidget)
            # self.updateCorrSignalsDrawer()
            # QApplication.processEvents()
        self.dw_corrspots.dockLocationChanged.connect(fn)
        self.dw_corrspots.featuresChanged.connect(lambda area: print(f'featuresChanged: {area}'))
        self.dw_corrspots.topLevelChanged.connect(lambda area: print(f'topLevelChanged: {area}'))
        self.dw_corrspots.visibilityChanged.connect(lambda area: print(f'visibilityChanged: {area}'))
        self.dw_corrspots.visibilityChanged.connect(fn)
        self.csWidget = QWidget()
        # self.csWidget.setMinimumHeight(64)
        self.csWidget.setStyleSheet("background-color: #161c20;")
        # self.csWidget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.csWidget.setLayout(self.cs_layout)
        self.dw_corrspots.setWidget(self.csWidget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dw_corrspots)
        self.dw_corrspots.hide()


        self.globTabsAndCpanel = VWidget(self.globTabs, self.cpanel, self.pbar_widget)
        # self.globTabsAndCpanel.setAutoFillBackground(True)
        # self.globTabsAndCpanel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.globTabsAndCpanel.show()

        self.setCentralWidget(self.globTabsAndCpanel)





    def initLaunchTab(self):
        self._launchScreen = OpenProject()
        self.globTabs.addTab(self._launchScreen, 'Open...')
        self._setLastTab()


    def get_application_root(self):
        return Path(__file__).parents[2]


    def initWidgetSpacing(self):
        logger.info('')
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
        self.statusBar.setFixedHeight(16)
        # self.statusBar.setStyleSheet("""
        # font-size: 10px;
        # font-weight: 600;
        # color: #141414;
        # background-color: #ede9e8;
        # margin: 0px;
        # padding: 0px;
        # """)
        self.setStatusBar(self.statusBar)


    def initPbar(self):
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(16)
        # self.pbar.setStyleSheet("font-size: 10px;")
        self.pbar.setTextVisible(True)
        # font = QFont('Arial', 12)
        # font.setBold(True)
        # self.pbar.setFont(font)
        # self.pbar.setFixedHeight(16)
        # self.pbar.setFixedWidth(400)
        self.pbar_widget = QWidget(self)
        self.pbar_widget.setAutoFillBackground(True)
        # self.pbar_widget.setStyleSheet("background-color: #222222;")
        self.status_bar_layout = QHBoxLayout()
        self.status_bar_layout.setContentsMargins(4, 0, 4, 0)
        self.status_bar_layout.setSpacing(4)

        # self.pbar_cancel_button = QPushButton('Stop')
        self.pbar_cancel_button = QPushButton('Stop')
        self.pbar_cancel_button.setFixedSize(42,14)
        self.pbar_cancel_button.setIconSize(QSize(14,14))
        self.pbar_cancel_button.setStatusTip('Terminate Pending Multiprocessing Tasks')
        self.pbar_cancel_button.setIcon(qta.icon('mdi.cancel', color=cfg.ICON_COLOR))
        self.pbar_cancel_button.setStyleSheet("""
        QPushButton{
            font-size: 9px;
            border-style: solid;
            border-color: #c7c7c7;
            border-width: 1px;
            border-radius: 2px;
            background-color: #ede9e8;
        }""")
        self.pbar_cancel_button.clicked.connect(self.forceStopMultiprocessing)

        self.pbar_widget.setLayout(self.status_bar_layout)
        self.pbarLabel = QLabel('Task... ')
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

        self._whiteningControl.setValue(float(getData('data,defaults,whitening-factor')))
        poly = getData('data,defaults,corrective-polynomial')
        if (poly == None) or (poly == 'None'):
            self._polyBiasCombo.setCurrentText('None')
        else:
            self._polyBiasCombo.setCurrentText(str(poly))
        self._swimWindowControl.setValue(int(getData(f'data,defaults,{cfg.data.scale},swim-window-px')[0]))


    def get_dw_hud(self):
        for i, dock in enumerate(cfg.mw.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Head-up Display':
                return self.children()[i]

    def get_dw_notes(self):
        for i, dock in enumerate(cfg.mw.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Notes':
                return self.children()[i]

    def get_dw_signals(self):
        for i, dock in enumerate(cfg.mw.findChildren(QDockWidget)):
            if dock.windowTitle() == 'Correlation Signals':
                return self.children()[i]







class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


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



'''


