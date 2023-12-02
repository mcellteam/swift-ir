#!/usr/bin/env python3
import copy
import inspect
import logging
import os
import shutil
import sys
import textwrap
import time
import warnings
from pprint import pformat
from pathlib import Path
from math import floor

import qtawesome as qta
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import *

import neuroglancer as ng
import src.config as cfg
from src.models.data import DataModel
from src.utils.helpers import print_exception, getOpt, setOpt, getData, setData, is_joel, \
    ensure_even
from src.ui.views.gif import GifPlayer
from src.ui.layouts.layouts import HBL, VBL, GL, HW, VW, QHLine
from src.models.jsontree import JsonModel
from src.ui.views.alignmenttable import ProjectTable
from src.ui.widgets.sliders import DoubleSlider
from src.ui.widgets.vertlabel import VerticalLabel
from src.ui.tools.snrplot import SnrPlot
from src.ui.views.thumbnail import CorrSignalThumbnail, ThumbnailFast
from src.viewers.viewerfactory import EMViewer, TransformViewer, MAViewer
from src.utils.readers import read
from src.utils.writers import write


__all__ = ['AlignmentTab']

logger = logging.getLogger(__name__)
# logger.propagate = False

DEV = is_joel()

class AlignmentTab(QWidget):

    def __init__(self, parent, dm=None):
        super().__init__(parent)
        logger.info('Initializing AlignmentTab...')
        cfg.preferences['last_alignment_opened'] = dm.data_file_path
        # self.signals = Signals()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.mw = parent
        self.viewer= None
        # self.viewer0 = None
        self.dm = self.mw.dm = cfg.dm = dm
        self.mw.pt = cfg.pt = self
        self.setUpdatesEnabled(True)
        self.we0 = WebEngine(self, ID='viewer')
        self.we0.setStyleSheet("background-color: #000000;")
        self.we0.setFocusPolicy(Qt.NoFocus)
        self.we0.loadFinished.connect(lambda: print('Web engine load finished!'))
        setWebengineProperties(self.we0)
        # self.webengine0.setStyleSheet('background-color: #222222;')
        self.we0.setMouseTracking(True)
        self._initNG_calls = 0
        self.wTable = QWidget()
        self.wTreeview = QWidget()
        self.initShader()
        self.gifPlayer = GifPlayer(dm=self.dm)
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        self.initTabs()
        # self.updateZarrUI()
        self.updateTab0UI()
        self.dataUpdateMA()
        # self.glWebengine0.addWidget(self.mw.wCpanel, 0, 1, 1, 1)


        self.wTabs.currentChanged.connect(self._onTabChange)
        self._allow_zoom_change = True
        self.dm.signals.positionChanged.connect(self.onPositionChange)
        self.dm.signals.positionChanged.connect(self.mw.setSignalsPixmaps)
        self.dm.signals.positionChanged.connect(self.mw.setTargKargPixmaps)
        self.dm.signals.swimArgsChanged.connect(self.onSwimArgsChanged)

        self.mw.cbInclude.setChecked(self.dm.include(l=self.dm.zpos))
        self.mw.cbInclude.stateChanged.connect(self.onIncludeExcludeToggle)

        # self.dm.loadHashTable()

        # self.installEventFilter(self)
        self.mw.addGlobTab(self, self.dm.title, switch_to=True)
        msg =      f"\n  {'Project'.rjust(15)}: {self.dm.title}"
        for k,v in self.dm['info'].items():
            msg += f"\n  {k.rjust(15)}: {v}"
        self.mw.tell(msg)

    def onSwimArgsChanged(self):
        print("swimArgsChanged signal received...", flush=True)
        _tab = self.wTabs.currentIndex()
        if _tab == 1:
            self.mw.updateAlignAllButtonText()
            self.updateAaButtons()
            self.cbDefaults.setChecked(self.dm.isDefaults())
            self.dataUpdateMA()
        if _tab == 2:
            self.snr_plot.plotData()
        self.mw.cbInclude.setChecked(self.dm.include())


    def onPositionChange(self):
        print("positionChanged!", flush=True)

        self.mw.sldrZpos.setValue(self.dm.zpos)
        self.mw.cbInclude.setChecked(self.dm.include(l=self.dm.zpos))

        _tab = self.wTabs.currentIndex()
        if _tab == 0:
            self.viewer0.set_layer()
            # self.viewer0.defer_callback(self.viewer0.set_layer)
        elif _tab == 1:
            self.bApplyOne.setText(f"Align Layer {self.dm.zpos}")
            self.viewer1.initViewer()
            self.transformViewer.initViewer()
            self.labCornerViewer.setText(self.transformViewer.title)
            if self.dm['state']['tra_ref_toggle'] == 'ref':
                self.set_transforming()
            self.dataUpdateMA()
        elif _tab == 2:
            self.snr_plot.updateLayerLinePos()

        if self.dSnr_plot.isVisible():
            self.dSnr_plot.updateLayerLinePos()




    #1111+
    # def forceFocus(self):
    #     logger.info('')
    #     logger.debug('Forcing focus...')
    #     if self.wTabs.currentIndex() == 1:
    #         # self.webengine1.setFocus()
    #         self.mw.setFocus()
    #         self.viewer.set_layer()

    def updateAaButtons(self):
        # logger.info('')
        # if self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['method'] == 'grid':
        alignment_ready = self.dm['level_data'][self.dm.scale]['alignment_ready']
        if alignment_ready:
            if self.twMethod.currentIndex() == 0:
                def_dl = self.dm['level_data'][self.dm.level]['defaults']
                def_mo = self.dm['level_data'][self.dm.level]['defaults']['method_opts']
                dl = self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]
                try:
                    mo = dl['swim_settings']['method_opts']
                except:
                    print_exception(extra=f"Level: {self.dm.level} | Section #: {self.dm.zpos}")
                try:
                    self.aaButtons[0].setEnabled(def_mo['size_1x1'] != mo['size_1x1'])
                    self.aaButtons[1].setEnabled(def_mo['size_2x2'] != mo['size_2x2'])
                    self.aaButtons[2].setEnabled(def_dl['iterations'] != dl['swim_settings']['iterations'])
                    self.aaButtons[3].setEnabled(def_dl['whitening'] != dl['swim_settings']['whitening'])
                    self.aaButtons[4].setEnabled((def_dl['clobber'] != dl['swim_settings']['clobber']) or
                                                 (def_dl['clobber_size'] != dl['swim_settings']['clobber_size']))
                    self.aaButtons[5].setEnabled(def_mo['quadrants'] != mo['quadrants'])
                except:
                    print_exception()
        print('<<', flush=True)

    def load_data_from_treeview(self):
        self.dm = DataModel(self.mdlTreeview.to_json())

    def updateTab0UI(self):
        logger.info('')
        self.bZarrRegen.setEnabled(self.dm.is_aligned())
        m = self.cbxNgExtras.model()
        if self.dm['state']['neuroglancer']['show_controls']: m.item(1).setCheckState(2)
        else: m.item(1).setCheckState(0)
        if self.dm['state']['neuroglancer']['show_bounds']: m.item(2).setCheckState(2)
        else: m.item(2).setCheckState(0)
        if self.dm['state']['neuroglancer']['show_axes']: m.item(3).setCheckState(2)
        else: m.item(3).setCheckState(0)
        if self.dm['state']['neuroglancer']['show_scalebar']: m.item(4).setCheckState(2)
        else: m.item(4).setCheckState(0)
        isAligned = self.dm.is_aligned()
        self.cbBB.setChecked(self.dm.output_settings()['bounding_box']['has'])



    def _onTabChange(self):
        clr = inspect.stack()[1].function
        logger.critical(f"[{clr}]")
        # QApplication.restoreOverrideCursor()
        self.dm['state']['blink'] = False
        index = self.wTabs.currentIndex()
        self.dm['state']['current_tab'] = index
        # self.gifPlayer.stop()

        index = self.wTabs.currentIndex()
        if index == 1:
            self.mw.bPlayback.hide()
            self.mw.sldrZpos.show()
            self.mw.sbFPS.hide()
            self.mw.ehw.hide()
        else:
            self.mw.bPlayback.hide()
            self.mw.sldrZpos.hide()
            self.mw.sbFPS.hide()
            self.mw.ehw.show()

        # if index != 0:
        #     self.mw.globTabsAndCpanel.layout.addWidget(self.mw.wCpanel)

        if index == 0:
            self.updateTab0UI()
            # self.updateZarrUI()
            self.initNeuroglancer()
            # self.glWebengine0.addWidget(self.mw.wCpanel, 0, 1, 1, 1)

        elif index == 1:
            # self.mw.setdw_thumbs(False) #BEFORE init neuroglancer
            # self.mw.setdw_matches(True) #BEFORE init neuroglancer
            self.dataUpdateMA()
            self.cbxViewerScale.setCurrentIndex(self.dm.levels.index(self.dm.level))
            self.initNeuroglancer() #Todo necessary for now
            self.set_transforming() #0802+
            self._updatePointLists() #0726+Failed to compose
            if self.twCornerViewer.currentIndex() == 0:
                # res = self.dm.resolution(s=self.dm.level)
                # self.transformViewer = TransformViewer(parent=self, webengine0=self.we2, path=None, dm=self.dm, res=res, )
                # w = self.we2.width()
                # h = self.we2.height()
                # self.transformViewer.initZoom(w=w, h=h, adjust=1.15)
                # self.transformViewer.set_layer()

                # self.transformViewer.webengine0.reload()
                pass
            elif self.twCornerViewer.currentIndex() == 1:
                self.gifPlayer.set()
        elif index == 2:
            self.snr_plot.initSnrPlot()
        elif index == 3:
            # self.project_table.data.selectRow(self.dm.zpos)
            self.project_table.initTableData()
        elif index == 4:
            self.updateTreeWidget()
            self.mdlTreeview.jumpToLayer()
        logger.info(f"<<<< _onTabChange")


    # def _refresh(self, index=None):
    def refreshTab(self):
        logger.info(f'[{inspect.stack()[1].function}]')
        logger.critical(f"\n\n[{inspect.stack()[1].function}] Refreshing Tab...\n")
        index = self.wTabs.currentIndex()
        self.dm['state']['blink'] = False
        # self.matchPlayTimer.stop()
        # self.initNeuroglancer(init_all=True)
        self.initNeuroglancer(force=True)
        if index == 0:
            self.updateTab0UI()
            # self.updateZarrUI()
            # self.initNeuroglancer()
            pass

        elif index == 1:
            logger.critical('Refreshing editor tab...')
            # self.initNeuroglancer()
            self.set_transforming()  # 0802+
            if self.mw.dwSnr.isVisible():
                if self.dm.is_aligned():
                    self.dSnr_plot.initSnrPlot()
                else:
                    self.dSnr_plot.wipePlot()

            # elif self.twCornerViewer.currentIndex() == 0:
            #     res = copy.deepcopy(self.dm.resolution(s=self.dm.level))
            #     self.transformViewer = TransformViewer(parent=self, webengine0=self.we2, path=None, dm=self.dm, res=res, )
            #     w = self.we2.width()
            #     h = self.we2.height()
            #     self.transformViewer.initZoom(w=w, h=h, adjust=1.15)
            if self.twCornerViewer.currentIndex() == 1:
                self.gifPlayer.set()

            self.viewer = self.viewer1
        elif index == 2:
            self.snr_plot.initSnrPlot()
        elif index == 3:
            self.project_table.initTableData()
        elif index == 4:
            self.treeview.collapseAll()
            self.updateTreeWidget()
            self.mdlTreeview.jumpToLayer()


    def initVolumeTab0(self):
        path = self.dm.path_zarr_raw()
        res = copy.deepcopy(self.dm.resolution(s=self.dm.level))
        self.viewer0 = EMViewer(parent=self, webengine=self.we0, path=path, dm=self.dm, res=res)
        self.viewer0.signals.layoutChanged.connect(lambda: setData('state,neuroglancer,layout', self.viewer0.state.layout.type))
        self.viewer0.signals.layoutChanged.connect(lambda: self.cbxNgLayout.setCurrentText(self.viewer0.state.layout.type))
        self.viewer0.signals.arrowLeft.connect(self.layer_left)
        self.viewer0.signals.arrowRight.connect(self.layer_right)
        self.viewer0.signals.arrowLeft.connect(lambda: print(f"arrow left!"))
        self.viewer0.signals.arrowRight.connect(lambda: print(f"arrow right!"))
        self.viewer0.signals.arrowUp.connect(lambda: self.viewer0.set_zoom(self.viewer0.zoom() * 0.9))
        self.viewer0.signals.arrowDown.connect(lambda: self.viewer0.set_zoom(self.viewer0.zoom() * 1.1))
        self.viewer0.signals.zoomChanged.connect(lambda x: self.slot_zoom_changed(x))  # Critical updates the lineedit
        # self.viewer0.signals.zoomChanged.connect(self.slotUpdateZoomSlider)  # 0314
        # self.viewer0.signals.zoomChanged.connect(lambda x: self.sldrZoomTab0.setValue(x)) #debug #1129 was on

        self.sldrZoomTab1.setValue(self.viewer0.state.cross_section_scale)

    def initVolumeTab1(self):
        path = os.path.join(self.dm['info']['images_path'], 'zarr', self.dm.level)
        res = self.dm.resolution(s=self.dm.level)
        self.viewer = self.viewer1 = MAViewer(parent=self, webengine=self.we1, path=path, dm=self.dm, res=res, )
        self.viewer1.signals.badStateChange.connect(self.set_transforming)
        self.viewer1.signals.ptsChanged.connect(self._updatePointLists)
        self.viewer1.signals.toggleView.connect(self.toggle_ref_tra)
        self.viewer1.signals.arrowLeft.connect(self.layer_left)
        self.viewer1.signals.arrowRight.connect(self.layer_right)
        self.viewer1.signals.arrowUp.connect(lambda: self.viewer1.set_zoom(self.viewer1.zoom() * 0.9))
        self.viewer1.signals.arrowDown.connect(lambda: self.viewer1.set_zoom(self.viewer1.zoom() * 1.1))
        # self.viewer1.signals.zoomChanged.connect(self.slotUpdateZoomSlider)  # 0314
        self.viewer1.signals.zoomChanged.connect(lambda x: self.sldrZoomTab1.setValue(x))

        def fn(x):
            logger.info(f'signal received. requested: {x}')
            self.dm.zpos = x
            # self.viewer1.webengine0.reload()

        self.viewer1.signals.zChanged.connect(lambda x: fn(x))
        self.viewer1.signals.zChanged.connect(self.viewer1.drawSWIMwindow)
        if hasattr(self,'transformViewer'):
            del self.transformViewer
        self.transformViewer = TransformViewer(parent=self, webengine=self.we2, path='', dm=self.dm, res=res, )

        self.sldrZoomTab1.setValue(self.viewer1.state.cross_section_scale)



    def initNeuroglancer(self, force=False):
        clr = inspect.stack()[1].function

        self._initNG_calls += 1
        logger.critical(f"[call # {self._initNG_calls}, {clr}] Initializing Neuroglancer...")

        if self.mw._working:
            logger.warning(f"[{clr}] Unable to initialize Neuroglancer at this time, busy working!")
            return

        if force:
            if hasattr(self, 'viewer0'):
                del self.viewer0
            if hasattr(self, 'viewer1'):
                del self.viewer1
            if hasattr(self, 'transformViewer'):
                del self.transformViewer
            if ng.is_server_running():
                ng.server.stop()

        QApplication.processEvents() #Critical for viewer1 to take correct size

        _tab = self.wTabs.currentIndex()
        if _tab == 0:
            # self.cbxNgLayout.setCurrentText(getData('state,neuroglancer,layout'))
            if force or not hasattr(self, 'viewer0'):
                self.initVolumeTab0()
            else:
                self.viewer0.initViewer()
        elif _tab == 1:
            self.gifPlayer.set(start=False)
            # self.webengine1.setUrl(QUrl("http://localhost:8888/"))
            if force or not hasattr(self,'viewer1'):
                self.initVolumeTab1()
            else:
                self.viewer1.initViewer()
                self.transformViewer.initViewer()

        self.mw.hud.done()
        logger.info(f"<<<< initNeuroglancer")

    @Slot()
    def layer_left(self):
        logger.info('')
        requested = self.dm.zpos - 1
        if requested >= 0:
            self.dm.zpos = requested
            # if self.wTabs.currentIndex() == 1:
            #     self.pt.set_transforming()

    @Slot()
    def layer_right(self):
        logger.info('')
        requested = self.dm.zpos + 1
        if requested < len(self.dm):
            self.dm.zpos = requested


    def slot_zoom_changed(self, val):
        if val > 1000:
            val *= 250000000
        self.leZoom.setText(f'{val:.2f}')


    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')

        self._overlayLab = QLabel()
        # self._overlayLab.setMaximumHeight(20)
        self._overlayLab.setFocusPolicy(Qt.NoFocus)
        self._overlayLab.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayLab.setAlignment(Qt.AlignCenter)
        self._overlayLab.setStyleSheet("""color: #FF0000; font-size: 16px; font-weight: 600; background-color: rgba(0, 0, 0, 0.5); """)
        self._overlayLab.hide()

        # self.hud_overlay = HeadupDisplay(self.mw.app, overlay=True)
        # self.hud_overlay.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        # self.hud_overlay.set_theme_overlay()


        self.detailsSNR = QLabel()
        self.detailsSNR.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSNR.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSNR.setMaximumHeight(100)
        self.detailsSNR.setWordWrap(True)
        self.detailsSNR.hide()

        self.sldrZoomTab1 = DoubleSlider(Qt.Orientation.Vertical, self)
        self.sldrZoomTab1.setFocusPolicy(Qt.NoFocus)
        self.sldrZoomTab1.setMouseTracking(True)
        # self.sldrZoomTab1.setInvertedAppearance(True)
        self.sldrZoomTab1.setMaximum(4)
        self.sldrZoomTab1.setMinimum(1)

        # self.sldrZoomTab1.sliderMoved.connect(self.onZoomSlider) #Original #0314
        self.sldrZoomTab1.sliderReleased.connect(self.onZoomSlider)
        self.sldrZoomTab1.setValue(4.0)

        vlab = VerticalLabel('Zoom:')

        self.wSldrZoomTab1 = VW()
        self.wSldrZoomTab1.layout.setSpacing(0)
        self.wSldrZoomTab1.setFocusPolicy(Qt.NoFocus)
        self.wSldrZoomTab1.setFixedWidth(16)
        self.wSldrZoomTab1.addWidget(self.sldrZoomTab1)
        self.wSldrZoomTab1.addWidget(vlab)

        # self.sliderZdisplay = DoubleSlider(Qt.Orientation.Vertical, self)
        # self.sliderZdisplay.setFocusPolicy(Qt.NoFocus)
        # self.sliderZdisplay.setMaximum(20)
        # self.sliderZdisplay.setMinimum(1)
        # self.sliderZdisplay.setValue(1.0)
        # self.sliderZdisplay.valueChanged.connect(self.onSliderZmag)

        '''Mouse move events will occur only when a mouse bBlink is pressed down, 
        unless mouse tracking has been enabled with setMouseTracking() .'''


        # self.bRevertSettings = QPushButton('Revert Settings')
        # self.bRevertSettings.setFocusPolicy(Qt.NoFocus)
        # # self.bRevertSettings.setFixedHeight(14)
        # self.bRevertSettings.setEnabled(False)
        # def fn_bRevertSettings():
        #     pass
        # self.bRevertSettings.clicked.connect(fn_bRevertSettings)
        # tip = "Todo: add tool tip"
        # tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bRevertSettings.setToolTip(tip)

        # self.bPush = QPushButton('Export as default preferences')
        # self.bPush.setFocusPolicy(Qt.NoFocus)
        # # self.bPush.setFixedHeight(16)
        # self.bPush.clicked.connect(self.onPushSettings)
        # msg = "Use these as default preferences for the current and finer scale levels."
        # tip = "Push (forward-propagate) these SWIM preferences as defaults for this and finer resolution levels."
        # tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bPush.setToolTip(tip)

        # self.bPull = QPushButton('Pull All Settings From Coarser Resolution')
        # self.bPull.setFocusPolicy(Qt.NoFocus)
        # self.bPull.setFixedHeight(16)
        # self.bPull.clicked.connect(self.dm.pullSettings)
        # self.bPull.clicked.connect(self.refreshTab)
        # # msg = "Re-pull (propagate) preferences from previous scale level."
        # tip = "Propagate all saved SWIM settings from next lowest level."
        # tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bPull.setToolTip(tip)

        # tip = "Perform a quick SWIM alignment to show match signals and SNR values, " \
        #       "but do not generate any new images"
        tip = "Perform a SWIM alignment + generate the resulting aligned image"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bApplyOne = QPushButton('Align (Affine, Match Signals, SNR)')
        # self.bApplyOne = QPushButton('Align')
        self.bApplyOne = QPushButton('Align Layer')
        self.bApplyOne.setToolTip(tip)
        self.bApplyOne.setFixedHeight(16)
        self.bApplyOne.setFocusPolicy(Qt.NoFocus)
        self.bApplyOne.clicked.connect(lambda: self.bApplyOne.setEnabled(False))
        self.bApplyOne.clicked.connect(lambda: self.bTransform.setEnabled(False))
        self.bApplyOne.clicked.connect(lambda: self.mw.alignOne(dm=self.dm, regenerate=True))
        # self.bApplyOne.clicked.connect(lambda: self.mw.setdw_matches(True))

        tip = "Apply the affine transformation from SWIM to the images."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bTransform = QPushButton('Transform (Generates Images)')
        # self.bTransform.setStyleSheet("font-size: 10px; background-color: #9fdf9f;")
        self.bTransform.setToolTip(tip)
        self.bTransform.setFixedHeight(16)
        self.bTransform.setFocusPolicy(Qt.NoFocus)
        self.bTransform.clicked.connect(lambda: self.bApplyOne.setEnabled(False))
        self.bTransform.clicked.connect(lambda: self.bTransform.setEnabled(False))
        self.bTransform.clicked.connect(lambda: self.mw.alignOne(dm=self.dm, regenerate=True, align=False))
        self.bTransform.hide()

        # self.bMove = QPushButton('Move')
        # self.bMove.setFixedSize(QSize(36, 16))
        # self.bMove.setFocusPolicy(Qt.NoFocus)
        # self.bMove.clicked.connect(self.onTranslate)
        #
        # self.leMoveRight = QLineEdit()
        # self.leMoveRight.returnPressed.connect(self.onTranslate_x)
        # self.leMoveRight.setFixedSize(QSize(36, 16))
        # self.leMoveRight.setValidator(QIntValidator())
        # self.leMoveRight.setText('0')
        # self.leMoveRight.setAlignment(Qt.AlignCenter)
        #
        # self.leMoveUp = QLineEdit()
        # self.leMoveUp.returnPressed.connect(self.onTranslate_y)
        # self.leMoveUp.setFixedSize(QSize(36, 16))
        # self.leMoveUp.setValidator(QIntValidator())
        # self.leMoveUp.setText('0')
        # self.leMoveUp.setAlignment(Qt.AlignCenter)
        #
        # self.wMovePoints = HW(
        #     HW(QLabel('up:'), self.leMoveUp),
        #     HW(QLabel('right:'), self.leMoveRight),
        #     self.bMove
        # )
        # self.wMovePoints.layout.setSpacing(6)
        # self.wMovePoints.layout.setAlignment(Qt.AlignRight)

        """  MA Settings Tab  """

        tip = "Window width for manual alignment (px)"
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_sliderMatch():
            clr = inspect.stack()[1].function
            if clr == 'main':
                logger.info('')
                val = ensure_even(int(self.sliderMatch.value()))
                if val != self.sliderMatch.value():
                    self.sliderMatch.setValue(val)

                dec = float(val / self.dm.image_size()[0])
                # self.dm.set_manual_swim_window_px(dec)
                self.dm.set_manual_swim_window_dec(dec)
                self.leMatch.setText(str(val))
                self.viewer1.drawSWIMwindow()

                if self.tableThumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()

        # self.sliderMatch = DoubleSlider(Qt.Orientation.Horizontal, self)
        self.sliderMatch = QSlider(Qt.Orientation.Horizontal, self)
        self.sliderMatch.setFocusPolicy(Qt.NoFocus)
        self.sliderMatch.setMinimum(64)
        self.sliderMatch.setToolTip(tip)
        self.sliderMatch.valueChanged.connect(fn_sliderMatch)
        self.sliderMatch.setFixedWidth(80)
        self.leMatch = QLineEdit()
        self.leMatch.setAlignment(Qt.AlignCenter)
        self.leMatch.setFixedSize(QSize(48, 16))

        def fn_leMatch():
            clr = inspect.stack()[1].function
            logger.info('clr: %s' % clr)
            # logger.info(f'manua lswim window value {int(self.leMatch.text())}')
            val = ensure_even(int(self.leMatch.text()))
            if val != self.sliderMatch.value():
                self.sliderMatch.setValue(val)

            dec = float(val / self.dm.image_size()[0])
            # self.dm.set_manual_swim_window_px(val)
            self.dm.set_manual_swim_window_dec(dec)
            self.dataUpdateMA()
            self.viewer1.drawSWIMwindow()
            if self.tableThumbs.isVisible():
                self.tn_ref.update()
                self.tn_tra.update()
        self.leMatch.returnPressed.connect(fn_leMatch)

        tip = "Full window width for automatic alignment (px)"
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_slider1x1():
            clr = inspect.stack()[1].function
            if clr in ('main','fn_le1x1'):
                logger.info('')
                val = int(self.slider1x1.value())
                if (val % 2) == 1:
                    self.slider1x1.setValue(val - 1)
                    return
                self.dm.set_size1x1(val)
                self.le1x1.setText(str(self.dm.size1x1()[0]))
                self.le2x2.setText(str(self.dm.size2x2()[0]))
                # self.slider2x2.setMaximum(int(val / 2 + 0.5))2
                self.slider2x2.setValue(int(self.dm.size2x2()[0]))
                self.viewer1.drawSWIMwindow()
                if self.tableThumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()

        self.slider1x1 = QSlider(Qt.Orientation.Horizontal, self)
        self.slider1x1.setFocusPolicy(Qt.NoFocus)
        self.slider1x1.setMinimum(64)
        self.slider1x1.setToolTip(tip)
        self.slider1x1.valueChanged.connect(fn_slider1x1)
        # self.slider1x1.setMaximumWidth(100)

        def fn_le1x1():
            logger.info('')
            # self.dm.set_size1x1(int(self.le1x1.text()))
            txt = self.le1x1.text()
            if txt:
                self.slider1x1.setValue(int(txt))
            # self.dataUpdateMA()

        self.le1x1 = QLineEdit()
        self.le1x1.setAlignment(Qt.AlignCenter)
        self.le1x1.returnPressed.connect(fn_le1x1)
        self.le1x1.setFixedSize(QSize(48, 16))

        tip = "2x2 window width for automatic alignment (px)"
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_slider2x2():
            clr = inspect.stack()[1].function
            if clr in ('main','fn_le2x2'):
                logger.info('')
                val = int(self.slider2x2.value())
                self.dm.set_size2x2(val)
                self.le2x2.setText(str(self.dm.size2x2()[0]))
                self.slider2x2.setValue(int(self.dm.size2x2()[0]))
                self.viewer1.drawSWIMwindow()
                if self.tableThumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()

        self.slider2x2 = QSlider(Qt.Orientation.Horizontal, self)
        self.slider2x2.setFocusPolicy(Qt.NoFocus)
        self.slider2x2.setToolTip(tip)
        self.slider2x2.valueChanged.connect(fn_slider2x2)
        # self.slider2x2.setMaximumWidth(100)

        def fn_le2x2():
            logger.info('')
            # self.dm.set_size2x2(int(self.le2x2.text()))
            txt = self.le2x2.text()
            if txt:
                self.slider2x2.setValue(int(txt))
            # self.dataUpdateMA()

        self.le2x2 = QLineEdit()
        self.le2x2.setAlignment(Qt.AlignCenter)
        self.le2x2.returnPressed.connect(fn_le2x2)
        self.le2x2.setFixedSize(QSize(48, 16))

        def fn():
            clr = inspect.stack()[1].function
            if clr == 'main':
                # if self.rbHint.isChecked():
                #     self.dm.current_method = 'manual_hint'
                # elif self.rbStrict.isChecked():
                #     self.dm.current_method = 'manual_strict'
                self.viewer1.drawSWIMwindow()
                if self.tableThumbs.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                self.mw.setSignalsPixmaps()
                self.mw.setTargKargPixmaps()
                if self.mw.dwSnr.isVisible():
                    self.dSnr_plot.initSnrPlot()

        self.rbHint = QRadioButton('Match Regions')
        self.rbHint.setChecked(True)
        self.rbHint.setEnabled(False)
        self.rbStrict = QRadioButton('Match Points')
        self.rbStrict.setEnabled(False)
        self.bgManualRBs = QButtonGroup(self)
        self.bgManualRBs.setExclusive(True)
        self.bgManualRBs.addButton(self.rbHint)
        self.bgManualRBs.addButton(self.rbStrict)
        self.bgManualRBs.buttonClicked.connect(fn)

        self.pxLab = QLabel('px')

        self.wwWidget = HW(self.sliderMatch, self.leMatch, self.pxLab)
        self.wwWidget.layout.setSpacing(4)

        self.w1x1 = HW(self.le1x1, self.slider1x1)
        self.w1x1.layout.setSpacing(4)
        self.w2x2 = HW(self.le2x2, self.slider2x2)
        self.w2x2.layout.setSpacing(4)

        self.Q1 = ClickRegion(self, color=cfg.glob_colors[0], name='Q1')
        self.Q2 = ClickRegion(self, color=cfg.glob_colors[1], name='Q2')
        self.Q3 = ClickRegion(self, color=cfg.glob_colors[2], name='Q3')  # correct
        self.Q4 = ClickRegion(self, color=cfg.glob_colors[3], name='Q4')  # correct

        self.Q1.clicked.connect(self.updateAutoSwimRegions)
        self.Q2.clicked.connect(self.updateAutoSwimRegions)
        self.Q3.clicked.connect(self.updateAutoSwimRegions)
        self.Q4.clicked.connect(self.updateAutoSwimRegions)

        self.Q_widget = QWidget()
        self.Q_widget.setFixedSize(QSize(50, 50))
        self.gl_Q = QGridLayout()
        self.gl_Q.setContentsMargins(0,0,0,0)
        self.gl_Q.setSpacing(1)
        self.gl_Q.addWidget(self.Q1, 0, 0, 1, 1)
        self.gl_Q.addWidget(self.Q2, 0, 1, 1, 1)
        self.gl_Q.addWidget(self.Q3, 1, 0, 1, 1)
        self.gl_Q.addWidget(self.Q4, 1, 1, 1, 1)
        self.Q_widget.setLayout(self.gl_Q)

        ctl_lab_style = 'color: #ede9e8; font-size: 10px;'
        tip = """A SWIM parameter which takes values in the range of -1.00 and 0.00 (default=-0.68)."""
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        lab = QLabel("Whitening\nFactor:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(Qt.AlignLeft)
        self.leWhitening = QLineEdit(self)
        self.leWhitening.setAlignment(Qt.AlignCenter)
        self.leWhitening.setValidator(QDoubleValidator(bottom=-1.0, top=0.0, decimals=2))
        self.leWhitening.setToolTip(tip)
        self.leWhitening.setFixedSize(QSize(48, 16))
        def fnWhitening():
            logger.info('')
            # clr = inspect.stack()[1].function
            # if clr == 'main':
            txt = self.leWhitening.text()
            if txt:
                val = float(txt)
                self.dm.whitening = val
        self.leWhitening.textEdited.connect(fnWhitening)

        tip = """The number of sequential SWIM refinements to alignment. In general, greater iterations results in a more refined alignment up to some limit, except for in cases of local maxima or complete misalignment (default=3)."""
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.leIterations = QLineEdit(self)
        self.leIterations.setAlignment(Qt.AlignCenter)
        self.leIterations.setValidator(QIntValidator(1,9))
        self.leIterations.setToolTip(tip)
        self.leIterations.setFixedSize(QSize(24, 16))
        def fnIters():
            logger.info('')
            txt = self.leIterations.text()
            if txt:
                self.dm.set_swim_iterations(int(self.leIterations.text()))
        self.leIterations.textEdited.connect(fnIters)

        tip = f"""The full width in pixels of an imaginary, centered grid which SWIM 
        aligns against (default={cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC * 100}% of image width)."""
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        lab = QLabel("SWIM\nWindow:")
        lab.setStyleSheet(ctl_lab_style)
        lab.setAlignment(Qt.AlignLeft)
        # self.leSwimWindow = QSpinBox(self)
        self.leSwimWindow = QLineEdit(self)
        self.leSwimWindow.setAlignment(Qt.AlignCenter)
        self.leSwimWindow.setToolTip(tip)
        self.leSwimWindow.setFixedSize(QSize(48, 16))
        self.leSwimWindow.setValidator(QIntValidator())
        def fn():
            clr = inspect.stack()[1].function
            if clr == 'main':
                logger.info(f'clr: {clr}')
                if self.leSwimWindow.text():
                    val = int(self.leSwimWindow.text())
                    logger.info(f"val = {val}")
                    if (val % 2) == 1:
                        new_val = val - 1
                        self.mw.tell(f'SWIM requires even values as input. Setting value to {new_val}')
                        self.leSwimWindow.setText(str(new_val))
                        return

                    if self.wTabs.currentIndex() == 1:
                        self.viewer1.drawSWIMwindow()
                    if self.tableThumbs.isVisible():
                        self.tn_ref.update()
                        self.tn_tra.update()
                    self.mw.tell(f'SWIM Window set to: {str(val)}')
        self.leSwimWindow.selectionChanged.connect(fn)
        self.leSwimWindow.returnPressed.connect(fn)

        self.cbClobber = QCheckBox()
        self.cbClobber.toggled.connect(lambda: self.dm.set_clobber(b=self.cbClobber.isChecked()))
        self.cbClobber.toggled.connect(lambda: self.leClobber.setEnabled(self.cbClobber.isChecked()))
        self.leClobber = QLineEdit()
        self.leClobber.setAlignment(Qt.AlignCenter)
        self.leClobber.setValidator(QIntValidator(1,16))
        self.leClobber.setFixedSize(QSize(24,16))
        self.leClobber.textEdited.connect(lambda: self.dm.set_clobber_px(x=self.leClobber.text()))
        self.wClobber = HW(self.cbClobber, QLabel('size (pixels): '), self.leClobber)
        self.wClobber.layout.setAlignment(Qt.AlignLeft)
        self.wClobber.setMaximumWidth(104)

        self.cbDefaults = QCheckBox('Defaults for this resolution level.')
        self.cbDefaults.setFocusPolicy(Qt.NoFocus)
        self.cbDefaults.toggled.connect(self.onDefaultsCheckbox)
        self.cbDefaults.setFixedHeight(14)

        self.cbIgnoreCache = QCheckBox('Ignore cache')
        self.cbIgnoreCache.setFocusPolicy(Qt.NoFocus)
        self.cbIgnoreCache.toggled.connect(self.onDefaultsCheckbox)
        self.cbIgnoreCache.setFixedHeight(14)

        self.flGrid = QFormLayout()
        self.flGrid.setHorizontalSpacing(4)
        self.flGrid.setLabelAlignment(Qt.AlignRight)
        self.flGrid.setFormAlignment(Qt.AlignCenter)
        self.flGrid.setContentsMargins(2, 2, 2, 2)
        self.flGrid.setSpacing(2)

        self.aaWidgets = []
        self.aaButtons = []
        for w in range(6):
            b = QPushButton('Apply To All')
            b.setFixedSize(62, 15)
            # b.clicked.connect(lambda: print('Applying all!'))
            self.aaButtons.append(b)
            hw = HW(b)
            hw.layout.setAlignment(Qt.AlignRight)
            self.aaWidgets.append(hw)

        self.aaButtons[0].clicked.connect(lambda: self.dm.aa1x1(int(self.le1x1.text())))
        self.aaButtons[1].clicked.connect(lambda: self.dm.aa2x2(int(self.le2x2.text())))
        self.aaButtons[2].clicked.connect(lambda: self.dm.aaIters(int(self.leIterations.text())))
        self.aaButtons[3].clicked.connect(lambda: self.dm.aaWhitening(float(self.leWhitening.text())))
        self.aaButtons[4].clicked.connect(lambda: self.dm.aaClobber((self.cbClobber.isChecked(), int(self.leClobber.text()))))
        self.aaButtons[5].clicked.connect(lambda: self.dm.aaQuadrants([self.Q1.isClicked, self.Q2.isClicked,self.Q3.isClicked, self.Q4.isClicked]))


        for b in self.aaButtons:
            # b.clicked.connect(self.dataUpdateMA)
            b.clicked.connect(lambda: self.mw.bAlign.setEnabled(False))
            b.clicked.connect(self.mw.alignAll)

        hw1x1 = HW(self.w1x1, self.aaWidgets[0])
        hw1x1.layout.setSpacing(4)
        hw2x2 = HW(self.w2x2, self.aaWidgets[1])
        hw2x2.layout.setSpacing(4)
        self.flGrid.addRow("SWIM 1x1 Window: ", hw1x1)
        self.flGrid.addRow("SWIM 2x2 Window: ", hw2x2)
        self.flGrid.addRow('SWIM Iterations: ', HW(self.leIterations, self.aaWidgets[2]))
        self.flGrid.addRow('Signal Whitening: ', HW(self.leWhitening, self.aaWidgets[3]))
        self.flGrid.addRow('Clobber Fixed Noise: ', HW(self.wClobber, self.aaWidgets[4]))
        self.flGrid.addRow("Use Quadrants\n(minimum=3): ", HW(self.Q_widget, self.aaWidgets[5]))
        wids = [self.cbDefaults, self.leSwimWindow, self.leWhitening, self.leIterations, self.cbClobber, self.leClobber]
        for w in wids:
            w.setFixedHeight(16)
        # self.flGrid.addWidget(self.bPush)
        # self.flGrid.addWidget(self.bPull)

        self.bLock = QPushButton()
        self.bLock.setFixedSize(QSize(16, 16))
        self.bLock.setIconSize(QSize(12, 12))
        self.bLock.setIcon(qta.icon('fa.unlock'))
        self.bLock.setCheckable(True)
        self.bLock.setChecked(self.dm.padlock)
        icon = ('fa.unlock', 'fa.lock')[self.dm.padlock]
        self.bLock.setIcon(qta.icon(icon))
        def fn_bLock():
            logger.info('')
            self.dm.padlock = self.bLock.isChecked()
            icon = ('fa.unlock', 'fa.lock')[self.dm.padlock]
            self.bLock.setIcon(qta.icon(icon))
            self.saManual.setDisabled(self.dm.padlock)
            self.saGrid.setDisabled(self.dm.padlock)
        self.bLock.toggled.connect(fn_bLock)

        tip = """User provides an alignment hint for SWIM by selecting 3 matching regions (manual correspondence). 
           Note: An affine transformation requires at least 3 correspondence regions."""
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_method_select():
            clr = inspect.stack()[1].function
            if clr == 'main':
                logger.info('')
                l = self.dm.zpos
                s = self.dm.scale
                if self.twMethod.currentIndex() == 0:
                    mo = self.dm['level_data'][s]['defaults']['method_opts'] #Todo why is this
                    self.dm['stack'][l]['levels'][s]['swim_settings']['method_opts'] = copy.deepcopy(mo)
                elif self.twMethod.currentIndex() == 1:
                    mo = self.dm['level_data'][s]['method_presets']['manual']  # Todo ...not similar to this
                    self.dm['stack'][l]['levels'][s]['swim_settings']['method_opts'] = copy.deepcopy(mo)
                self.dataUpdateMA() #1019+ #Critical
                self.viewer1.drawSWIMwindow()  # 1019+
                self.we1.setFocus()


        class ItemDelegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                option.decorationPosition = QStyleOptionViewItem.Right
                super(ItemDelegate, self).paint(painter, option, index)

        self.lwR = ListWidget()
        self.lwR.setItemDelegate(ItemDelegate())
        self.lwR.clicked.connect(lambda: print("lwR clicked!"))
        self.lwR.setFocusPolicy(Qt.NoFocus)
        # self.lwR.setFocusPolicy(Qt.NoFocus)
        delegate = ListItemDelegate()
        self.lwR.setItemDelegate(ItemDelegate())
        self.lwR.setItemDelegate(delegate)
        # self.lwR.setFixedHeight(52)
        self.lwR.setIconSize(QSize(12, 12))
        self.lwR.setSelectionMode(QListWidget.NoSelection)
        self.lwR.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lwR.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lwR.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # self.lwR.installEventFilter(self)
        def fn_point_selected(item):
            # self.item = item
            requested = self.lwR.indexFromItem(item).row()
            print(f"[transforming] row selected: {requested}")
            self._updatePointLists()

        self.lwR.itemClicked.connect(fn_point_selected)

        self.lwL = ListWidget()
        self.lwL.clicked.connect(lambda: print("lwL clicked!"))
        self.lwL.setFocusPolicy(Qt.NoFocus)
        # self.lwL.setFocusPolicy(Qt.NoFocus)
        delegate = ListItemDelegate()
        self.lwL.setItemDelegate(delegate)
        # self.lwL.setFixedHeight(52)
        self.lwL.setIconSize(QSize(12, 12))
        self.lwL.setSelectionMode(QListWidget.NoSelection)
        self.lwL.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lwL.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lwL.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lwL.installEventFilter(self)

        def fn_point_selected(item):
            logger.info('')
            self._updatePointLists()

        self.lwL.itemClicked.connect(fn_point_selected)

        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        font.setStyleHint(QFont.TypeWriter)

        nums = {0: 'ri.number-1', 1: 'ri.number-2', 2: 'ri.number-3'}
        for i in list(range(0, 3)):
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 16))
            item.setBackground(QColor(cfg.glob_colors[i]))
            item.setForeground(QColor('#141414'))
            item.setFont(font)
            self.lwL.addItem(item)
            self.lwL.item(i).setIcon(qta.icon(nums[i]))
            self.lwL.item(i).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 16))
            item.setBackground(QColor(cfg.glob_colors[i]))
            item.setForeground(QColor('#141414'))
            item.setFont(font)
            self.lwR.addItem(item)
            self.lwR.item(i).setIcon(qta.icon(nums[i]))
            self.lwR.item(i).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.lwR.itemSelectionChanged.connect(self.lwL.selectionModel().clear)
        self.lwL.itemSelectionChanged.connect(self.lwR.selectionModel().clear)

        self.bClearR = QPushButton('Clear')
        self.bClearR.setFocusPolicy(Qt.NoFocus)
        self.bClearR.setToolTip('Clear Selections')
        self.bClearR.setFixedHeight(14)
        self.bClearR.clicked.connect(self.deleteAllMpRef)

        self.bClearL = QPushButton('Clear')
        self.bClearL.setFocusPolicy(Qt.NoFocus)
        self.bClearL.setToolTip('Clear Selections')
        self.bClearL.setFixedHeight(14)
        self.bClearL.clicked.connect(self.deleteAllMpBase)

        self.gbGrid = QGroupBox("Grid Alignment Settings")
        self.gbGrid.setMaximumHeight(258)
        self.gbGrid.setLayout(self.flGrid)
        # self.gbGrid.setAlignment(Qt.AlignBottom)
        self.gbGrid.setAlignment(Qt.AlignCenter)

        self.lInstructions = BoldLabel("Use 1, 2, 3 keys to select 3 corresponding "
                                       "regions. Use Spacebar or / to toggle "
                                       "transforming and reference sections")
        self.lInstructions.setMaximumHeight(24)
        self.lInstructions.setWordWrap(True)

        style = """
                QWidget[current=true]{border-width: 3px; border-color: #339933;} 
                QWidget[current=false]{border-width:1px;} 
                QGroupBox {font-weight:600; border-radius: 2px;}
                """

        self.gbR = GroupBox()
        self.gbR.setProperty('current', False)
        self.gbR.clicked.connect(lambda: print("gbL clicked!"))
        self.gbR.setStyleSheet(style)

        def fn():
            if self.dm['state']['tra_ref_toggle'] == 'ref':
                self.set_transforming()

        # self.gbL.clicked.connect(fn)
        # self.gbL.setLayout(VBL(BoldLabel('Transforming'), self.lwL, self.bClearL))
        self.gbR.clicked.connect(fn)
        self.gbR.setLayout(VBL(BoldLabel('Reference'), self.lwR, self.bClearR))

        self.gbL = GroupBox()
        self.gbL.setProperty('current', True)
        self.gbL.clicked.connect(lambda: print("gbR clicked!"))
        self.gbL.setStyleSheet(style)

        def fn():
            if self.dm['state']['tra_ref_toggle'] == 'tra':
                self.set_reference()

        # self.gbR.clicked.connect(fn)
        # self.gbR.setLayout(VBL(BoldLabel('Reference'), self.lwR, self.bClearR))
        self.gbL.clicked.connect(fn)
        self.gbL.setLayout(VBL(BoldLabel('Transforming'), self.lwL, self.bClearL))

        self.labSlash = QLabel('←/→')
        self.labSlash.setStyleSheet("""font-size: 10px; font-weight: 600;""")
        self.hwPointsLists = HW(self.gbR, self.labSlash, self.gbL)
        self.hwPointsLists.setMaximumHeight(106)

        self.flManual = QFormLayout()
        self.flManual.setLabelAlignment(Qt.AlignRight)
        self.flManual.addRow("Window Width:", self.wwWidget)
        self.hwMethod = HW(self.rbHint, self.rbStrict)
        self.flManual.addRow("Method:", self.hwMethod)

        self.wMatch = QWidget()
        self.wMatch.setLayout(self.flManual)

        self.wMethodMatch = VW(self.lInstructions, self.hwPointsLists, self.wMatch)
        self.wMethodMatch.layout.setContentsMargins(4, 4, 4, 4)

        self.logs_top_btn = QPushButton('Top')
        self.logs_top_btn.setFixedSize(QSize(40, 18))
        self.logs_top_btn.clicked.connect(lambda: self.teLogs.verticalScrollBar().setValue(0))

        self.logs_bottom_btn = QPushButton('Bottom')
        self.logs_bottom_btn.setFixedSize(QSize(40, 18))
        self.logs_bottom_btn.clicked.connect(lambda: self.teLogs.verticalScrollBar().setValue(
            self.teLogs.verticalScrollBar().maximum()))

        def fn():
            logger.info('')
            logs_path = os.path.join(self.dm.dest(), 'logs')
            for filename in os.listdir(logs_path):
                file_path = os.path.join(logs_path, filename)
                logger.info(f'Removing: {file_path}...')
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print_exception()
                    print('Failed to delete %s. Reason: %s' % (file_path, e))

            self.teLogs.setText('No Log To Show.')

        self.bLogsRefresh = QPushButton('Refresh')
        self.bLogsRefresh.setFixedSize(QSize(64, 18))
        self.bLogsRefresh.clicked.connect(self.refreshLogs)

        self.bLogsDeleteAll = QPushButton('Delete Logs')
        self.bLogsDeleteAll.setFixedSize(QSize(64, 18))
        self.bLogsDeleteAll.clicked.connect(fn)

        self.teLogs = QTextEdit()
        self.teLogs.setReadOnly(True)
        self.teLogs.setText('Logs...')

        self.lab_logs = BoldLabel('Logs:')

        self.rbLogs1 = QRadioButton('SWIM Args')
        self.rbLogs1.setChecked(True)
        self.rbLogs2 = QRadioButton('SWIM Out')
        self.rbLogs3 = QRadioButton('MIR')
        self.bgRbLogs = QButtonGroup(self)
        self.bgRbLogs.addButton(self.rbLogs1)
        self.bgRbLogs.addButton(self.rbLogs2)
        self.bgRbLogs.addButton(self.rbLogs3)
        self.bgRbLogs.setExclusive(True)

        # self.btns_logs = QWidget()

        self.lIng = QLabel('Ingredients:')

        self.bIng0 = QPushButton('1')

        def fn():
            key = 'swim_args'
            if self.rbLogs1.isChecked():
                key = 'swim_args'
            elif self.rbLogs2.isChecked():
                key = 'swim_out'
            elif self.rbLogs3.isChecked():
                key = 'mir_args'
            args = '\n'.join(self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['results'][key][
                                 'ingredient_0']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.teLogs.setText(' '.join(args))

        self.bIng0.clicked.connect(fn)

        self.bIng1 = QPushButton('2')

        def fn():
            key = 'swim_args'
            if self.rbLogs1.isChecked():
                key = 'swim_args'
            elif self.rbLogs2.isChecked():
                key = 'swim_out'
            elif self.rbLogs3.isChecked():
                key = 'mir_args'
            args = '\n'.join(self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['results'][key][
                                 'ingredient_1']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.teLogs.setText(' '.join(args))

        self.bIng1.clicked.connect(fn)

        self.bIng2 = QPushButton('3')

        def fn():
            key = 'swim_args'
            if self.rbLogs1.isChecked():
                key = 'swim_args'
            elif self.rbLogs2.isChecked():
                key = 'swim_out'
            elif self.rbLogs3.isChecked():
                key = 'mir_args'
            args = '\n'.join(self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['results'][key][
'ingredient_2']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.teLogs.setText(' '.join(args))

        self.bIng2.clicked.connect(fn)
        self.bIng0.setFixedSize(QSize(40, 18))
        self.bIng1.setFixedSize(QSize(40, 18))
        self.bIng2.setFixedSize(QSize(40, 18))
        self.wIngredients = HW(self.lIng, ExpandingWidget(self), self.bIng0, self.bIng1, self.bIng2)

        self.logs_widget = VW(
            HW(self.lab_logs, ExpandingWidget(self), self.rbLogs1, self.rbLogs2),
            self.teLogs,
            self.wIngredients,
            HW(ExpandingWidget(self),
               self.bLogsRefresh,
               self.bLogsDeleteAll,
               self.logs_top_btn,
               self.logs_bottom_btn
               ),
        )
        self.logs_widget.layout.setContentsMargins(2,2,2,2)
        self.logs_widget.layout.setSpacing(2)

        self.saGrid = QScrollArea()
        self.saGrid.setFocusPolicy(Qt.NoFocus)
        self.saGrid.setWidgetResizable(True)
        self.saGrid.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.saGrid.setWidget(self.gbGrid)

        self.saManual = QScrollArea()
        self.saManual.setFocusPolicy(Qt.NoFocus)
        self.saManual.setWidgetResizable(True)
        self.saManual.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.saManual.setWidget(self.wMethodMatch)

        # self.sa_runtimes.setWidgetResizable(True)
        # self.sa_runtimes.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.sa_runtimes.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.labPlaceholder = QLabel("This resolution level must be aligned first ('Align All').")
        self.labPlaceholder.setAlignment(Qt.AlignCenter)
        self.labPlaceholder.setStyleSheet("font-size: 12px;")
        self.wPlaceholder = VW(self.labPlaceholder)

        self.twMethod = QTabWidget()
        self.twMethod.setCornerWidget(self.bLock)
        self.twMethod.setStyleSheet("""
        QTabBar::tab {
            padding-top: 1px;
            padding-bottom: 1px;
            height: 12px;  
            min-width: 100px;          
            font-size: 9px;
        }
        """)
        # self.twMethod.setTabShape(QTabWidget.Triangular)
        # self.twMethod.tabBar().setElideMode(Qt.ElideMiddle)
        # self.twMethod.tabBar().setExpanding(True)
        self.twMethod.setDocumentMode(True)
        self.twMethod.setTabsClosable(False)
        self.twMethod.setFocusPolicy(Qt.NoFocus)
        # self.twMethod.setStyleSheet("QTabBar::tab { height: 16px; width: 100px;}")
        self.twMethod.currentChanged.connect(fn_method_select)
        self.twMethod.addTab(self.saGrid, 'Grid Align')
        self.twMethod.addTab(self.saManual, 'Manual Align')


        self.swMethod = QStackedWidget()
        self.swMethod.layout().setContentsMargins(2,2,2,2)
        self.swMethod.addWidget(self.twMethod)
        self.swMethod.addWidget(self.wPlaceholder)

        # self.bFrameZoom = QPushButton()
        # self.bFrameZoom.setCursor(QCursor(Qt.PointingHandCursor))
        # self.bFrameZoom.setFixedSize(QSize(18, 18))
        # self.bFrameZoom.setIcon(qta.icon('msc.zoom-out', color='#161c20'))
        # def fn():
        #     try:
        #         self.viewer1.initZoom()
        #     except:
        #         print_exception()
        # self.bFrameZoom.clicked.connect(fn)

        # self.labViewerScale = QLabel('Viewer Resolution:')
        self.cbxViewerScale = QComboBox()
        lst = []
        lst.append('Full Quality %d x %dpx' % (self.dm.image_size(s=self.dm.levels[0])))
        for level in self.dm.levels[1:]:
            siz = self.dm.image_size(s=level)
            lst.append('1/%d Quality %d x %dpx' % (self.dm.lvl(level), siz[0], siz[1]))
        self.cbxViewerScale.addItems(lst)

        self.cbxViewerScale.setCurrentIndex(self.dm.levels.index(self.dm['state']['viewer_quality']))

        def fn_cmbViewerScale():
            clr = inspect.stack()[1].function
            logger.info(f"[{clr}]")
            if clr == 'main':
                level = self.dm.levels[self.cbxViewerScale.currentIndex()]
                siz = self.dm.image_size(s=level)
                self.dm['state']['viewer_quality'] = level
                self.mw.tell('Viewing quality set to 1/%d (%d x %dpx)' % (self.dm.lvl(level), siz[0], siz[1]))
                self.initNeuroglancer()

        # self.cbxViewerScale.currentIndexChanged.connect(fn_cmbViewerScale)

        # https://codeloop.org/pyqt5-make-multi-document-interface-mdi-application/

        # '''THIS WORKS'''
        # self.mdi = QMdiArea()
        # self.sub_webengine = QMdiSubWindow()
        # self.sub_webengine.setWidget(self.webengine0)
        # self.sub_webengine.showMaximized()
        # self.sub_webengine.setWindowFlags(Qt.FramelessWindowHint)
        # self.mdi.addSubWindow(self.sub_webengine)

        # self.mdi.setBackground(QBrush(Qt.transparent))
        # self.w_mdi = QWidget()
        # self.w_mdi.setLayout(self.mdi)
        # def WindowTrig(p):
        #     print(f"Menu Selection: {p.text()}")
        #     if p.text() == "New":
        #         self.sub = QMdiSubWindow()
        #         te = QTextEdit()
        #         te.setFixedSize(QSize(400,300))
        #         self.sub.setWidget()
        #         self.sub.setWindowTitle("Sub Window")
        #         self.mdi.addSubWindow(self.sub)
        #         self.sub.show()

        # testmenu = QMenu()
        # testmenu.addAction("New")
        # testmenu.addAction("cascade")
        # testmenu.addAction("Tiled")

        ngFont = QFont('Tahoma')
        ngFont.setBold(True)
        pal = QPalette()
        pal.setColor(QPalette.Text, QColor("#FFFF66"))

        self.cbxNgLayout = QComboBox(self)
        self.cbxNgLayout.setFixedWidth(60)
        self.cbxNgLayout.setFixedHeight(16)
        self.cbxNgLayout.setFocusPolicy(Qt.NoFocus)
        items = ['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d']
        self.cbxNgLayout.addItems(items)
        self.cbxNgLayout.activated.connect(self.onNgLayoutCombobox)
        self.cbxNgLayout.setCurrentText(getData('state,neuroglancer,layout'))

        self.wNgLayout = HW(BoldLabel('  Layout  '), self.cbxNgLayout)

        self.tbbColorPicker = QToolButton()
        self.tbbColorPicker.setFixedSize(QSize(74, 16))
        # self.tbbColorPicker.setStyleSheet("color: #f3f6fb; font-size: 10px; background-color: rgba(0, 0, 0, 0.5); border-radius: 2px;")
        self.tbbColorPicker.setText('Background   ')

        def openColorDialog():
            logger.info('')
            color = QColorDialog.getColor()
            if color.isValid():
                logger.info(f"Selected color: {color.name()}")
                setOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR', color.name())
                setOpt('neuroglancer,USE_CUSTOM_BACKGROUND', True)
                self.colorAction0.setChecked(False)
                self.colorAction1.setChecked(False)
                self.colorAction3.setChecked(True)
                self.colorAction3.setVisible(True)
                self.colorAction3.setText(f'Custom ({color.name()})')
                if self.wTabs.currentIndex() == 0:
                    self.viewer0.setBackground()
                elif self.wTabs.currentIndex() == 1:
                    self.viewer1.setBackground()
                # self.initNeuroglancer()
            else:
                self.colorAction3.setChecked(False)

        self.colorAction0 = QAction('Neutral', self)
        def fn():
            # setData('state,neutral_contrast', True)
            setOpt('neuroglancer,USE_CUSTOM_BACKGROUND', False)
            setOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND', False)
            # self.colorAction0.setChecked(True)
            self.colorAction0.setChecked(True)
            self.colorAction1.setChecked(False)
            self.colorAction3.setChecked(False)
            # self.colorAction2.setChecked(False)
            if self.wTabs.currentIndex() == 0:
                self.viewer0.setBackground()
            elif self.wTabs.currentIndex() == 1:
                self.viewer1.setBackground()
            # self.initNeuroglancer()
        self.colorAction0.triggered.connect(fn)

        self.colorAction1 = QAction('Dark', self)
        def fn():
            # setData('state,neutral_contrast', False)
            setOpt('neuroglancer,USE_CUSTOM_BACKGROUND', False)
            setOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND', True)
            self.colorAction0.setChecked(False)
            self.colorAction1.setChecked(True)
            self.colorAction3.setChecked(False)
            # self.colorAction2.setChecked(False)
            if self.wTabs.currentIndex() == 0:
                self.viewer0.setBackground()
            elif self.wTabs.currentIndex() == 1:
                self.viewer1.setBackground()
            # self.initNeuroglancer()
        self.colorAction1.triggered.connect(fn)

        self.colorAction2 = QAction('Pick...', self)
        self.colorAction2.triggered.connect(openColorDialog)

        self.colorAction3 = QAction('Custom', self)
        def fn():
            self.colorAction0.setChecked(False)
            self.colorAction1.setChecked(False)
            self.colorAction3.setChecked(True)
            setOpt('neuroglancer,USE_CUSTOM_BACKGROUND', True)
            if self.wTabs.currentIndex() == 0:
                self.viewer0.setBackground()
            elif self.wTabs.currentIndex() == 1:
                self.viewer1.setBackground()

        self.colorAction3.triggered.connect(fn)
        self.colorAction3.setObjectName('customColor')
        if getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR'):
            self.colorAction3.setVisible(True)
            self.colorAction3.setText(f"Custom ({getOpt('neuroglancer,CUSTOM_BACKGROUND_COLOR')})")
        else:
            self.colorAction3.setVisible(False)
        self.colorAction3.setChecked(getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'))

        self.colorAction0.setCheckable(True)
        self.colorAction1.setCheckable(True)
        # self.colorAction2.setCheckable(True)
        self.colorAction3.setCheckable(True)
        self.colorAction0.setChecked(not getOpt('neuroglancer,USE_CUSTOM_BACKGROUND') and not getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'))
        self.colorAction1.setChecked(not getOpt('neuroglancer,USE_CUSTOM_BACKGROUND') and getOpt('neuroglancer,USE_DEFAULT_DARK_BACKGROUND'))
        # self.colorAction2.setChecked(getOpt('neuroglancer,USE_CUSTOM_BACKGROUND'))

        self.colorMenu = QMenu()
        self.colorMenu.addAction(self.colorAction1)
        self.colorMenu.addAction(self.colorAction0)
        self.colorMenu.addAction(self.colorAction3)
        self.colorMenu.addAction(self.colorAction2)
        self.tbbColorPicker.setMenu(self.colorMenu)
        self.tbbColorPicker.setPopupMode(QToolButton.InstantPopup)
        self.tbbColorPicker.clicked.connect(openColorDialog)

        self.leZoom = QLineEdit()
        self.leZoom.setAlignment(Qt.AlignCenter)
        self.leZoom.setFixedWidth(38)
        self.leZoom.setFixedHeight(15)
        self.leZoom.setValidator(QDoubleValidator())
        self.leZoom.returnPressed.connect(lambda: setData('state,neuroglancer,zoom', float(self.leZoom.text())))
        self.leZoom.returnPressed.connect(lambda: self.viewer0.set_zoom(float(self.leZoom.text())))
        try:
            self.leZoom.setText('%.3f' % self.dm['state']['neuroglancer']['zoom'])
        except:
            print_exception()

        self.zoomLab = BoldLabel('  Zoom  ')
        self.zoomLab.setFixedWidth(34)
        # self.zoomLab.setAlignment(Qt.AlignCenter)
        # self.zoomLab.setStyleSheet("font-weight: 600;")
        self.wZoom = HW(self.zoomLab, self.leZoom)
        self.wZoom.layout.setAlignment(Qt.AlignCenter)
        self.wZoom.layout.setSpacing(4)
        self.wZoom.setMaximumWidth(80)

        self.tbbNgHelp = QToolButton()
        def fn_ng_help():
            logger.info('')
            self.viewer0.setHelpMenu(not self.tbbNgHelp.isChecked())
            # if self.tbbNgHelp.isChecked():
            #     self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#161c20'))
            # else:
            #     self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#f3f6fb'))

        self.tbbNgHelp.setToolTip("Neuroglancer Help")
        self.tbbNgHelp.setCheckable(True)
        self.tbbNgHelp.pressed.connect(fn_ng_help)
        self.tbbNgHelp.setFocusPolicy(Qt.NoFocus)
        # self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#f3f6fb'))
        self.tbbNgHelp.setIcon(qta.icon('fa.question'))


        self.cbxNgExtras = CheckableComboBox()
        self.cbxNgExtras.setFixedWidth(86)
        self.cbxNgExtras.setFixedHeight(16)
        self.cbxNgExtras.addItem("Show/Hide...")
        self.cbxNgExtras.addItem("NG Controls", state=self.dm['state']['neuroglancer']['show_controls'])
        self.cbxNgExtras.addItem("Bounds", state=self.dm['state']['neuroglancer']['show_bounds'])
        self.cbxNgExtras.addItem("Axes", state=self.dm['state']['neuroglancer']['show_axes'])
        self.cbxNgExtras.addItem("Scale Bar", state=self.dm['state']['neuroglancer']['show_scalebar'])

        def cb_itemChanged():
            clr = inspect.stack()[1].function
            logger.info(f'clr: {clr}')
            if clr == 'main':
                self.dm['state']['neuroglancer']['show_controls'] = self.cbxNgExtras.itemChecked(1)
                self.dm['state']['neuroglancer']['show_bounds'] = self.cbxNgExtras.itemChecked(2)
                self.dm['state']['neuroglancer']['show_axes'] = self.cbxNgExtras.itemChecked(3)
                self.dm['state']['neuroglancer']['show_scalebar'] = self.cbxNgExtras.itemChecked(4)
                self.viewer0.updateDisplayExtras()
                self.mw.saveUserPreferences(silent=True)

        self.cbxNgExtras.model().itemChanged.connect(cb_itemChanged)

        self.labZarrSource = BoldLabel(' View ')
        self.wNgAccessories = HW(BoldLabel("  Neuroglancer  "), self.cbxNgExtras)

        self.cbTransformed = QCheckBox('Transformed')
        # self.cbTransformed.setStyleSheet("")
        def fn_cb_transformed():
            clr = inspect.stack()[1].function
            if clr == 'main':
                if self.cbTransformed.isChecked():
                    self.viewer0.set_transformed()
                else:
                    self.viewer0.set_untransformed()
        self.cbTransformed.toggled.connect(fn_cb_transformed)

        tip = 'Generate permanent Zarr of cumulative alignment from TIFFs'
        self.bZarrRegen = QPushButton('Generate')
        self.bZarrRegen.setFixedSize(QSize(42,15))
        self.bZarrRegen.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.bZarrRegen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bZarrRegen.clicked.connect(lambda: self.bZarrRegen.setEnabled(False))
        self.bZarrRegen.clicked.connect(lambda: self.mw.regenZarr(self.dm))

        self.wZarrSelect = HW(self.labZarrSource, self.cbTransformed, spacing=6)

        self.toolbar0 = QToolBar()
        self.toolbar0.setFixedHeight(20)
        self.toolbar0.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbar0.addSeparator()
        self.toolbar0.addWidget(self.wZarrSelect)
        self.toolbar0.addSeparator()
        self.toolbar0.addWidget(self.wNgLayout)
        self.toolbar0.addWidget(self.wNgAccessories)
        self.toolbar0.addWidget(self.wZoom)
        self.toolbar0.addWidget(self.wBC)
        self.toolbar0.addWidget(self.tbbColorPicker)
        self.toolbar0.addWidget(self.tbbNgHelp)

        '''REFERENCE AND TRANSFORMING THUMBNAILS WITH PAINTED SWIM REGION ANNOTATIONS'''
        # self.tn_tra_overlay = QLabel('Excluded')
        self.tn_tra_overlay = QLabel('X')
        self.tn_tra_overlay.setFocusPolicy(Qt.NoFocus)
        self.tn_tra_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.tn_tra_overlay.setAlignment(Qt.AlignCenter)
        self.tn_tra_overlay.setStyleSheet("""color: #FF0000; font-size: 20px; font-weight: 600; background-color: rgba(0, 0, 0, 0.5); """)
        self.tn_tra_overlay.hide()

        self.tn_ref = ThumbnailFast(self, name='reference')
        self.tn_tra = ThumbnailFast(self, name='transforming')
        self.tn_ref.setMinimumSize(QSize(64,64))
        self.tn_tra.setMinimumSize(QSize(64,64))

        self.wTbThumbs = QWidget()
        self.glTbThumbs = QGridLayout()
        self.glTbThumbs.setContentsMargins(0, 0, 0, 0)
        self.glTbThumbs.addWidget(self.tn_tra, 0, 0, 1, 1)
        self.glTbThumbs.addWidget(self.tn_tra_overlay, 0, 0, 1, 1)

        self.wTbThumbs.setLayout(self.glTbThumbs)

        self.tn_ref_lab = QLabel('Reference Section')
        self.tn_ref_lab.setFixedHeight(26)
        self.tn_ref_lab.setStyleSheet("""font-size: 10px; background-color: #ede9e8; color: #161c20;""")

        self.tn_tra_lab = QLabel('Transforming Section')
        self.tn_tra_lab.setFixedHeight(26)
        self.tn_tra_lab.setStyleSheet("""font-size: 10px; background-color: #ede9e8; color: #161c20;""")

        self.tableThumbs = QTableWidget()
        self.tableThumbs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tableThumbs.setAutoFillBackground(True)
        self.tableThumbs.setMinimumWidth(64)
        self.tableThumbs.setContentsMargins(0, 0, 0, 0)
        self.tableThumbs.setStyleSheet("""background-color: #222222;""")
        self.tableThumbs.horizontalHeader().setHighlightSections(False)
        self.tableThumbs.verticalHeader().setHighlightSections(False)
        self.tableThumbs.setFocusPolicy(Qt.NoFocus)
        self.tableThumbs.setSelectionMode(QAbstractItemView.NoSelection)
        self.tableThumbs.setRowCount(2)
        self.tableThumbs.setColumnCount(1)
        self.vw1 = VW(self.tn_tra_lab, self.wTbThumbs)
        self.vw1.setStyleSheet("background-color: #222222;")
        self.vw2 = VW(self.tn_ref_lab, self.tn_ref)
        self.vw2.setStyleSheet("background-color: #222222;")
        self.tableThumbs.setCellWidget(0, 0, self.vw1)
        self.tableThumbs.setCellWidget(1, 0, self.vw2)
        self.tableThumbs.setItem(0, 0, QTableWidgetItem())
        self.tableThumbs.setItem(1, 0, QTableWidgetItem())
        self.tableThumbs.verticalHeader().setVisible(False)
        self.tableThumbs.horizontalHeader().setVisible(False)
        self.tableThumbs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableThumbs.setShowGrid(False)
        v_header = self.tableThumbs.verticalHeader()
        h_header = self.tableThumbs.horizontalHeader()
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        # h_header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.tableSigs = QTableWidget()
        self.tableSigs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.sig0 = CorrSignalThumbnail(self, name='ms0')
        self.sig1 = CorrSignalThumbnail(self, name='ms1')
        self.sig2 = CorrSignalThumbnail(self, name='ms2')
        self.sig3 = CorrSignalThumbnail(self, name='ms3')
        self.sigList = [self.sig0, self.sig1, self.sig2, self.sig3]
        self.sig0.set_no_image()
        self.sig1.set_no_image()
        self.sig2.set_no_image()
        self.sig3.set_no_image()

        self.tableSigs.setAutoFillBackground(True)
        self.tableSigs.setContentsMargins(0, 0, 0, 0)
        self.tableSigs.setStyleSheet(
            """QLabel{ color: #ede9e8; background-color: #222222; font-weight: 600; font-size: 9px; } QTableWidget{background-color: #222222;}""")
        self.tableSigs.horizontalHeader().setHighlightSections(False)
        self.tableSigs.verticalHeader().setHighlightSections(False)
        self.tableSigs.setFocusPolicy(Qt.NoFocus)
        self.tableSigs.setSelectionMode(QAbstractItemView.NoSelection)
        self.tableSigs.setRowCount(4)
        self.tableSigs.setColumnCount(1)
        self.tableSigs.setCellWidget(0, 0, self.sig0)
        self.tableSigs.setCellWidget(1, 0, self.sig1)
        self.tableSigs.setCellWidget(2, 0, self.sig2)
        self.tableSigs.setCellWidget(3, 0, self.sig3)
        self.tableSigs.setItem(0, 0, QTableWidgetItem())
        self.tableSigs.setItem(1, 0, QTableWidgetItem())
        self.tableSigs.setItem(2, 0, QTableWidgetItem())
        self.tableSigs.setItem(3, 0, QTableWidgetItem())
        self.tableSigs.verticalHeader().setVisible(False)
        self.tableSigs.horizontalHeader().setVisible(False)
        self.tableSigs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableSigs.setShowGrid(True)
        v_header = self.tableSigs.verticalHeader()
        h_header = self.tableSigs.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        v_header.setSectionResizeMode(2, QHeaderView.Stretch)
        v_header.setSectionResizeMode(3, QHeaderView.Stretch)

        self.toggleMatches = QPushButton()
        self.toggleMatches.setIcon(qta.icon('mdi.toggle-switch-off'))
        self.toggleMatches.setFixedSize(20, 14)
        self.toggleMatches.setIconSize(QSize(20, 20))

        def fn_stop_playing():
            self.matchPlayTimer.stop()
            self.bPlayMatchTimer.setIcon(qta.icon('fa.play'))

        self.toggleMatches.clicked.connect(fn_stop_playing)
        self.toggleMatches.clicked.connect(self.fn_toggleTargKarg)

        self.match0 = ThumbnailFast(self, name='match0')
        self.match1 = ThumbnailFast(self, name='match1')
        self.match2 = ThumbnailFast(self, name='match2')
        self.match3 = ThumbnailFast(self, name='match3')
        self.matchesList = [self.match0, self.match1, self.match2, self.match3]

        self.tableMatches = QTableWidget()
        self.tableMatches.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.tableMatches.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.tableMatches.setAutoFillBackground(True)
        self.tableMatches.setContentsMargins(0, 0, 0, 0)
        self.tableMatches.setStyleSheet(
            """QLabel{ color: #ede9e8; background-color: #222222; font-weight: 600; font-size: 9px; } QTableWidget{background-color: #222222;}""")
        self.tableMatches.horizontalHeader().setHighlightSections(False)
        self.tableMatches.verticalHeader().setHighlightSections(False)
        self.tableMatches.setFocusPolicy(Qt.NoFocus)
        self.tableMatches.setSelectionMode(QAbstractItemView.NoSelection)
        self.tableMatches.setRowCount(4)
        self.tableMatches.setColumnCount(1)
        # self.tableMatches.setColumnCount(2)
        self.tableMatches.setCellWidget(0, 0, self.match0)
        self.tableMatches.setCellWidget(1, 0, self.match1)
        self.tableMatches.setCellWidget(2, 0, self.match2)
        self.tableMatches.setCellWidget(3, 0, self.match3)
        self.tableMatches.setItem(0, 0, QTableWidgetItem())
        self.tableMatches.setItem(1, 0, QTableWidgetItem())
        self.tableMatches.setItem(2, 0, QTableWidgetItem())
        self.tableMatches.setItem(3, 0, QTableWidgetItem())
        self.tableMatches.verticalHeader().setVisible(False)
        self.tableMatches.horizontalHeader().setVisible(False)
        self.tableMatches.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableMatches.setShowGrid(True)
        h_header = self.tableMatches.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header = self.tableMatches.verticalHeader()
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        v_header.setSectionResizeMode(2, QHeaderView.Stretch)
        v_header.setSectionResizeMode(3, QHeaderView.Stretch)

        # Playback Widget

        self.bPlayMatchTimer = QPushButton()
        self.bPlayMatchTimer.setIconSize(QSize(11, 11))
        self.bPlayMatchTimer.setFixedSize(14, 14)
        self.bPlayMatchTimer.setIcon(qta.icon('fa.play'))

        def startStopMatchTimer():
            logger.info('')
            if self.mw._isProjectTab():
                self.dm['state']['blink'] = not self.dm['state']['blink']
                if self.dm['state']['blink']:
                    self.matchPlayTimer.start()
                    self.bPlayMatchTimer.setIcon(qta.icon('fa.pause'))
                else:
                    self.matchPlayTimer.stop()
                    self.bPlayMatchTimer.setIcon(qta.icon('fa.play'))
        self.bPlayMatchTimer.clicked.connect(startStopMatchTimer)

        self.matchPlayTimer = QTimer(self)
        self.matchPlayTimer.setInterval(500)
        self.matchPlayTimer.timeout.connect(self.fn_toggleTargKarg)


        self.cbAnnotateSignals = QCheckBox('Annotations')
        self.cbAnnotateSignals.setIconSize(QSize(11, 11))
        self.cbAnnotateSignals.setFixedHeight(14)
        self.cbAnnotateSignals.setChecked(self.dm['state']['annotate_match_signals'])
        self.cbAnnotateSignals.toggled.connect(lambda: setData('state,annotate_match_signals',
                                                               self.cbAnnotateSignals.isChecked()))
        self.cbAnnotateSignals.toggled.connect(lambda: self.match_widget.update())

        self.lAutotoggle = QLabel('Auto-toggle:')
        self.lAutotoggle.setFocusPolicy(Qt.NoFocus)
        self.lAutotoggle.setAlignment(Qt.AlignRight)
        self.lAutotoggle.setFixedHeight(14)

        self.lToggle = QLabel('Toggle:')
        self.lToggle.setFocusPolicy(Qt.NoFocus)
        self.lToggle.setAlignment(Qt.AlignRight)
        self.lToggle.setFixedHeight(14)

        self.mwTitle = HW(self.cbAnnotateSignals, self.lAutotoggle, self.bPlayMatchTimer, self.lToggle,
                          self.toggleMatches)
        self.mwTitle.layout.setAlignment(Qt.AlignRight)
        self.mwTitle.layout.setSpacing(4)

        hw = HW(self.tableMatches, self.tableSigs)
        hw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.match_widget = VW(self.mwTitle, hw)
        self.match_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.we1 = WebEngine(self, ID='tra')
        setWebengineProperties(self.we1)
        self.we1.setMouseTracking(True)

        w = QWidget()
        gl = GL()
        gl.addWidget(self.we1, 0, 0, 3, 3)
        gl.addWidget(self._overlayLab, 0, 0, 3, 3)
        w.setLayout(gl)

        self.clTra = ClickLabel(' Transforming ')
        self.clTra.setFocusPolicy(Qt.NoFocus)
        self.clTra.setAlignment(Qt.AlignCenter)
        self.clTra.clicked.connect(self.set_transforming)

        self.clRef = ClickLabel(' Reference ')
        self.clRef.setFocusPolicy(Qt.NoFocus)
        self.clRef.setAlignment(Qt.AlignCenter)
        self.clRef.clicked.connect(self.set_reference)

        self.wClickHeader = HW(self.clRef, self.clTra)
        self.wClickHeader.setFixedHeight(16)

        self.vlabTab1 = VerticalLabel('Alignment Editor')
        self.wWebengine1 = HW(self.vlabTab1, VW(self.wClickHeader, w), self.wSldrZoomTab1)
        self.wWebengine1.layout.setSpacing(0)

        self.labCornerViewer = QLabel(f'i={self.dm.zpos} | Transformed')
        # self.labCornerViewer.setStyleSheet("color: #FFFF66; font-weight: 600; font-size: 12px;")
        self.labCornerViewer.setStyleSheet("""color: #FFFF66; 
        background-color: rgba(0, 0, 0, 0.40); border-radius: 2px; font-size: 11px; 
        padding: 2px;""")

        self.we2 = WebEngine(self, ID='we2')
        self.we2.setFocusPolicy(Qt.NoFocus)
        self.we2.setMinimumSize(QSize(200, 200))
        setWebengineProperties(self.we2)
        self.we2.setMouseTracking(True)

        self.bToggleResult = QPushButton('Toggle Result')
        self.bToggleResult.setFocusPolicy(Qt.NoFocus)
        self.bToggleResult.setFixedSize(QSize(68, 14))

        self.bToggleResult.clicked.connect(lambda: self.transformViewer.toggle())
        self.bToggleResult.clicked.connect(lambda: self.labCornerViewer.setText(self.transformViewer.title))

        self.hwCornerViewer = HW(self.bToggleResult, self.labCornerViewer)
        self.hwCornerViewer.setFocusPolicy(Qt.NoFocus)
        self.hwCornerViewer.layout.setSpacing(4)
        self.hwCornerViewer.layout.setAlignment(Qt.AlignTop)
        self.hwCornerViewer.setFixedHeight(16)
        self.hwCornerViewer.setMaximumWidth(240)

        self.wWebengine2 = QWidget()
        self.wWebengine2.setFocusPolicy(Qt.NoFocus)
        self.glWebengine2 = GL()
        self.wWebengine2.setLayout(self.glWebengine2)
        self.glWebengine2.addWidget(self.we2, 0, 0, 3, 3)
        self.glWebengine2.addWidget(self.hwCornerViewer, 0, 1, 1, 1)

        self.twCornerViewer = QTabWidget()
        self.twCornerViewer.setFocusPolicy(Qt.NoFocus)
        self.twCornerViewer.setMinimumHeight(280)
        self.twCornerViewer.setStyleSheet("""
        QTabBar::tab {
            padding-top: 1px;
            padding-bottom: 1px;
            height: 12px;  
            min-width: 100px;          
            font-size: 9px;
        }
        """)

        self.twCornerViewer.addTab(self.wWebengine2, 'Blink Neuroglancer (Experimental)')
        # self.twCornerViewer.addTab(self.wGifPlayer, 'Blink GIF')
        self.twCornerViewer.addTab(self.gifPlayer, 'Blink GIF')

        def tab_changed():
            if self.twCornerViewer.currentIndex() == 0:
                # res = self.dm.resolution(s=self.dm.level)
                # self.transformViewer = TransformViewer(parent=self, webengine0=self.we2, path=None, dm=self.dm, res=res, )
                # w = self.we2.width()
                # h = self.we2.height()
                # self.transformViewer.initZoom(w=w, h=h, adjust=1.15)
                pass
            if self.twCornerViewer.currentIndex() == 1:
                self.gifPlayer.set(start=False)

        self.twCornerViewer.currentChanged.connect(tab_changed)

        self.checkboxes = HW( self.cbDefaults , self.cbIgnoreCache )
        self.checkboxes.layout.setSpacing(4)

        # self.btnsSWIM = HW(self.bApplyOne)
        # self.btnsSWIM.layout.setContentsMargins(2,2,2,2)
        # self.btnsSWIM.layout.setSpacing(2)
        # self.vwRightPanel = VW( self.swMethod , self.checkboxes , self.btnsSWIM )
        self.vwRightPanel = VW(self.checkboxes, self.swMethod)
        self.vwRightPanel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.columnSplitter = QSplitter(Qt.Orientation.Vertical)
        self.columnSplitter.addWidget(self.vwRightPanel)
        self.columnSplitter.addWidget(self.twCornerViewer)
        self.columnSplitter.setCollapsible(0, False)
        self.columnSplitter.setCollapsible(1, False)
        self.columnSplitter.setStretchFactor(0, 1)
        self.columnSplitter.setStretchFactor(1, 2)

        self.wTab1 = QSplitter(Qt.Orientation.Horizontal)
        self.wTab1.addWidget(self.wWebengine1)
        self.wTab1.addWidget(self.columnSplitter)
        self.wTab1.setCollapsible(0, False)
        self.wTab1.setCollapsible(1, False)
        self.wTab1.setStretchFactor(0, 2) #1020-
        self.wTab1.setStretchFactor(1, 1) #1020-
        self.wTab1.setSizes([int(cfg.WIDTH * (3 / 4)), int(cfg.WIDTH * (1 / 4))]) #1020-

        
    def onZarrRadiobutton(self):
        # # self.rbZarrRaw, self.rbZarrExperimental, self.rbZarrTransformed
        # if self.rbZarrRaw.isChecked():
        #     self.viewer0 = self.viewer = self.mw.viewer = cfg.viewer = self.viewerRaw
        # elif self.rbZarrExperimental.isChecked():
        #     self.viewer0 = self.viewer = self.mw.viewer = cfg.viewer = self.viewerExperimental
        # elif self.rbZarrTransformed.isChecked():
        #     self.viewer0 = self.viewer = self.mw.viewer = cfg.viewer = self.viewerTransformed
        # self.viewer.set_layer()
        pass


    @Slot()
    def onPushSettings(self):
        logger.info('')
        self.dm.pushDefaultSettings()
        self.dataUpdateMA()


    # def fixAll(self):
    #     logger.info('')
    #     to_align = self.dm.needsAlignIndexes()
    #     # to_regenerate = self.dm.needsGenerateIndexes()
    #     logger.info(f'\nAlign indexes: {pprint.pformat(to_align)}')
    #     self.mw.align(dm=self.dm, indexes=to_align)
    #     self.mw.regenZarr()

    @Slot()
    def onIncludeExcludeToggle(self):
        '''Callback to set include/exclude section'''
        clr = inspect.stack()[1].function
        logger.critical(f'<<{clr}')
        if clr == 'main':
            _bool = self.mw.cbInclude.isChecked()
            self.dm.set_include(_bool, l=self.dm.zpos)
            self.dm.linkReference()
            if self.dm.is_aligned():
                self.dm.set_stack_cafm()
            self.mw.tell(f"Include -> {('No', 'Yes')[_bool]}")


    @Slot()
    def onDefaultsCheckbox(self):
        clr = inspect.stack()[1].function
        if clr == 'main':
            logger.info('')
            if self.cbDefaults.isChecked():
                if not self.dm.isDefaults():
                    self.dm.applyDefaults()
            else:
                self.cbDefaults.setChecked(self.dm.isDefaults())
            self.dataUpdateMA()


    def toggle_ref_tra(self):
        logger.info('')
        if self.wTabs.currentIndex() == 1:
            if self.dm['state']['tra_ref_toggle'] == 'tra':
                self.set_reference()
            else:
                self.set_transforming()


    @Slot()
    def set_reference(self):
        # logger.critical('')
        logger.info('')
        self.dm['state']['tra_ref_toggle'] = 'ref'
        if self.dm.skipped():
            self.mw.warn('This section does not have a reference because it is excluded.')
            return
        # self._tra_pt_selected = None
        self.viewer1.set_layer()
        self.transformViewer.setReference()
        self.labCornerViewer.setText(self.transformViewer.title)
        # self._updatePointLists()
        self.clRef.setChecked(True)
        self.clTra.setChecked(False)
        self.mw.leJump.setText(str(self.dm.get_ref_index()))
        if self.twMethod.currentIndex() == 1:
            self.lwR.setEnabled(True)
            self.lwL.setEnabled(False)
            self.gbR.setProperty("current", True)
            self.gbR.style().unpolish(self.gbR)
            self.gbL.setProperty("current", False)
            self.gbL.style().unpolish(self.gbL)
            for i in list(range(0,3)):
                self.lwL.item(i).setForeground(QColor('#666666'))
                self.lwR.item(i).setForeground(QColor('#141414'))
        self.we1.setFocus()

    @Slot()
    def set_transforming(self):
        clr = inspect.stack()[1].function
        logger.info(f'[{clr}]')
        self.dm['state']['tra_ref_toggle'] = 'tra'
        self.viewer1.set_layer()
        self.transformViewer.setTransforming()
        self.labCornerViewer.setText(self.transformViewer.title)
        # self._updatePointLists()
        self.clTra.setChecked(True)
        self.clRef.setChecked(False)
        self.mw.leJump.setText(str(self.dm.zpos))
        if self.twMethod.currentIndex() == 1:
            self.lwL.setEnabled(True)
            self.lwR.setEnabled(False)
            self.gbR.setProperty("current", False)
            self.gbR.style().unpolish(self.gbR)
            self.gbL.setProperty("current", True)
            self.gbL.style().unpolish(self.gbL)
            for i in list(range(0,3)):
                self.lwL.item(i).setForeground(QColor('#141414'))
                self.lwR.item(i).setForeground(QColor('#666666'))
        self.we1.setFocus()


    def onSideTabChange(self):
        logger.info('')
        if self.teLogs.isVisible():
            self.refreshLogs()


    def fn_toggleTargKarg(self):
        logger.info('')
        setData('state,targ_karg_toggle', 1 - getData('state,targ_karg_toggle'))
        self.toggleMatches.setIcon(qta.icon(
            ('mdi.toggle-switch', 'mdi.toggle-switch-off')[getData('state,targ_karg_toggle')]))
        # (self.rb_targ.setChecked, self.rb_karg.setChecked)[getData('state,targ_karg_toggle')](True)
        self.mw.setTargKargPixmaps()


    def refreshLogs(self):
        logger.info('')
        logs_path = os.path.join(self.dm.dest(), 'logs', 'recipemaker.log')
        if os.path.exists(logs_path):
            with open(logs_path, 'r') as f:
                text = f.read()
        else:
            text = 'No Log To Show.'
        self.teLogs.setText(text)
        self.teLogs.verticalScrollBar().setValue(self.teLogs.verticalScrollBar().maximum())

    def updateAutoSwimRegions(self):
        logger.info('')
        if 'grid' in self.dm.method():
            self.dm.quadrants = [self.Q1.isClicked, self.Q2.isClicked, self.Q3.isClicked, self.Q4.isClicked]
        self.viewer1.drawSWIMwindow()


    # def onTranslate(self):
    #     if (self.lwL.selectedIndexes() == []) and (self.lwR.selectedIndexes() == []):
    #         self.mw.warn('No points are selected in the list')
    #         return
    #
    #     selections = []
    #     if len(self.lwR.selectedIndexes()) > 0:
    #         role = 'ref'
    #         for sel in self.lwR.selectedIndexes():
    #             selections.append(int(sel.data()[0]))
    #     else:
    #         role = 'tra'
    #         for sel in self.lwL.selectedIndexes():
    #             selections.append(int(sel.data()[0]))
    #
    #     pts_old = self.dm.manpoints()[role]
    #     pts_new = pts_old
    #
    #     for sel in selections:
    #         new_x = pts_old[sel][1] - int(self.leMoveRight.text())
    #         new_y = pts_old[sel][0] - int(self.leMoveUp.text())
    #         pts_new[sel] = (new_y, new_x)
    #
    #     self.dm.set_manpoints(role=role, matchpoints=pts_new)
    #     # self.viewer1.restoreManAlignPts()
    #     self.viewer1.drawSWIMwindow()
    #
    # def onTranslate_x(self):
    #     if (self.lwL.selectedIndexes() == []) and (self.lwR.selectedIndexes() == []):
    #         self.mw.warn('No points are selected in the list')
    #         return
    #
    #     selections = []
    #     if len(self.lwR.selectedIndexes()) > 0:
    #         role = 'ref'
    #         for sel in self.lwR.selectedIndexes():
    #             selections.append(int(sel.data()[0]))
    #     else:
    #         role = 'tra'
    #         for sel in self.lwL.selectedIndexes():
    #             selections.append(int(sel.data()[0]))
    #
    #     pts_old = self.dm.manpoints()[role]
    #     pts_new = pts_old
    #
    #     for sel in selections:
    #         new_x = pts_old[sel][1] - int(self.leMoveRight.text())
    #         new_y = pts_old[sel][0]
    #         pts_new[sel] = (new_y, new_x)
    #
    #     self.dm.set_manpoints(role=role, matchpoints=pts_new)
    #     # self.viewer1.restoreManAlignPts()
    #     self.viewer1.drawSWIMwindow()
    #
    # def onTranslate_y(self):
    #     if (self.lwL.selectedIndexes() == []) and (self.lwR.selectedIndexes() == []):
    #         self.mw.warn('No points are selected in the list')
    #         return
    #
    #     selections = []
    #     if len(self.lwR.selectedIndexes()) > 0:
    #         role = 'ref'
    #         for sel in self.lwR.selectedIndexes():
    #             selections.append(int(sel.data()[0]))
    #     else:
    #         role = 'tra'
    #         for sel in self.lwL.selectedIndexes():
    #             selections.append(int(sel.data()[0]))
    #
    #     pts_old = self.dm.manpoints()[role]
    #     pts_new = pts_old
    #
    #     for sel in selections:
    #         new_x = pts_old[sel][1]
    #         new_y = pts_old[sel][0] - int(self.leMoveUp.text())
    #         pts_new[sel] = (new_y, new_x)
    #
    #     self.dm.set_manpoints(role=role, matchpoints=pts_new)
    #     # self.viewer1.restoreManAlignPts()
    #     self.viewer1.drawSWIMwindow()

    @Slot()
    def onNgLayoutCombobox(self) -> None:
        clr = inspect.stack()[1].function
        if clr in ('main', '<lambda>'):
            choice = self.cbxNgLayout.currentText()
            setData('state,neuroglancer,layout', choice)
            self.mw.tell(f'Neuroglancer Layout Set To: {choice}')
            try:
                layout_actions = {
                    'xy': self.mw.ngLayout1Action,
                    'yz': self.mw.ngLayout2Action,
                    'xz': self.mw.ngLayout3Action,
                    'xy-3d': self.mw.ngLayout4Action,
                    'yz-3d': self.mw.ngLayout5Action,
                    'xz-3d': self.mw.ngLayout6Action,
                    # '3d': self.mw.ngLayout7Action,
                    '4panel': self.mw.ngLayout8Action
                }
                layout_actions[choice].setChecked(True)
                with self.viewer0.txn() as s:
                    s.layout.type = choice
            except:
                print_exception()
                logger.error('Unable To Change Neuroglancer Layout')


    def updateCursor(self):
        QApplication.restoreOverrideCursor()
        if self.dm['state']['current_tab'] == 1:
            # if self.tgl_alignMethod.isChecked():
            if self.dm.method() in ('manual_hint', 'manual_strict'):
                pixmap = QPixmap('src/resources/match-point.png')
                cursor = QCursor(pixmap.scaled(QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                QApplication.setOverrideCursor(cursor)


    # def updateZarrUI(self):
    #     clr = inspect.stack()[1].function
    #     logger.critical(f'{clr}')
    #     # self.updateZarrButtonsEnabled()
    #     isGenerated = self.dm.is_zarr_generated()
    #     isAligned = self.dm.is_aligned()
    #     self.rbZarrTransformed.setEnabled(isGenerated)
    #     self.rbZarrTransformed.setText(f"Transformed ({('Not ','')[isGenerated]}Generated)")
    #     self.rbZarrExperimental.setEnabled(isAligned)
    #     settings = self.dm.output_settings()
    #     bias = settings['polynomial_bias']
    #     if type(bias) == int:
    #         self.cbxBias.setCurrentIndex(bias + 1)
    #     else:
    #         self.cbxBias.setCurrentIndex(0)
    #     # self.cbBB.setChecked(settings['bounding_box']['has'])
    #     selected = self.bgZarrSelect.checkedButton()
    #     if not selected:
    #         if self.dm.is_aligned():
    #             self.rbZarrExperimental.setChecked(True)
    #         else:
    #             self.rbZarrRaw.setChecked(True)
    #     else:
    #         if self.dm.is_aligned():
    #             if selected.objectName() == 'raw':
    #                 setData('state,neuroglancer,layout', '4panel')
    #                 self.rbZarrExperimental.setChecked(True)
    #         else:
    #             setData('state,neuroglancer,layout', 'xy')
    #             self.rbZarrRaw.setChecked(True)


    # def updateZarrButtonsEnabled(self):
    #     # isGenerated = self.dm.is_zarr_generated()
    #     # isAligned = self.dm.is_aligned()
    #     # self.rbZarrTransformed.setEnabled(isGenerated)
    #     # self.rbZarrExperimental.setEnabled(isAligned)
    #     # # self.rbZarrExperimental.setEnabled(isAligned and (Path(self.dm.images_path) / 'zarr_slices').exists())


    @Slot()
    def dataUpdateMA(self):
        # clr = inspect.stack()[1].function
        # logger.info(f"[{clr}]")

        # self.mw.bZarrRegen.setEnabled(self.dm.is_aligned())

        # self.bPull.setVisible((self.dm.scale != self.dm.coarsest_scale_key()) and self.dm.is_alignable())
        if self.wTabs.currentIndex() == 1: #1111 This should make a huge difference
            self.gifPlayer.controls2.setVisible(os.path.exists(self.dm.path_cafm_gif()))
            self.gbGrid.setTitle(f'Level {self.dm.lvl()} Grid Alignment Settings')
            self.hwCornerViewer.setVisible(self.dm.is_aligned())
            ready = self.dm['level_data'][self.dm.scale]['alignment_ready']
            if self.dm.is_alignable() and ready:
                self.swMethod.setCurrentIndex(0)
                if hasattr(self.viewer, 'drawSWIMwindow'): #1111+
                    try:
                        self.viewer1.drawSWIMwindow()
                    except AttributeError:
                        print_exception()

                # self.bPull.setVisible((self.dm.scale != self.dm.coarsest_scale_key()) and self.dm.is_alignable())
                # self.bApplyOne.show()
                self.checkboxes.show()
                ss = self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['swim_settings']
                if self.dm.current_method == 'grid':
                    # self.swMethod.setCurrentIndex(0)
                    self.twMethod.setCurrentIndex(0)

                    siz1x1 = ss['method_opts']['size_1x1']
                    min_dim = self.dm.image_size()[0]
                    self.le1x1.setValidator(QIntValidator(128, min_dim))
                    self.le1x1.setText(str(siz1x1[0]))
                    self.slider1x1.setMaximum(int(min_dim))
                    self.slider1x1.setValue(int(siz1x1[0]))

                    siz2x2 = ss['method_opts']['size_2x2']
                    self.le2x2.setValidator(QIntValidator(64, int(min_dim / 2)))
                    self.le2x2.setText(str(siz2x2[0]))
                    self.slider2x2.setMaximum(int(min_dim / 2))
                    self.slider2x2.setValue(siz2x2[0])

                    use = ss['method_opts']['quadrants']
                    self.Q1.setActivated(use[0])
                    self.Q2.setActivated(use[1])
                    self.Q3.setActivated(use[2])
                    self.Q4.setActivated(use[3])

                elif self.dm.current_method == 'manual':
                    # self.swMethod.setCurrentIndex(1)
                    self.twMethod.setCurrentIndex(1)
                    self.swMethod.setCurrentIndex(0)
                    # Todo update with either 'point' or 'region' selection mode
                    # self.rbHint.setChecked(self.dm.current_method == 'manual_hint')
                    self._updatePointLists()
                    img_w, _ = self.dm.image_size()
                    val = self.dm.manual_swim_window_px()
                    self.leMatch.setValidator(QIntValidator(64, img_w))
                    self.leMatch.setText(str(val))  # Todo
                    self.sliderMatch.setMaximum(img_w)
                    self.sliderMatch.setValue(val)  # Todo

                self.updateAaButtons()

                self.cbDefaults.setChecked(self.dm.isDefaults())

                self.bTransform.setEnabled(self.dm.is_aligned())
                # self.bApplyOne.setEnabled(self.dm.is_aligned() and not os.file_path.exists(self.dm.path_aligned()))

                self.clTra.setText(f' [{self.dm.zpos}] {self.dm.name()} (Transforming)')

                _skipped = self.dm.skipped()
                self.cbBB.setChecked(_skipped)
                if _skipped:
                    self.clTra.setText(f' [{self.dm.zpos}] {self.dm.name()} (Transforming)')
                    self.clRef.setText(f' --')
                else:
                    try:
                        self.clRef.setText(f' [{self.dm.get_ref_index()}] {self.dm.name_ref()} (Reference)')
                    except:
                        self.clRef.setText(f' Null (Reference)')

                self.leWhitening.setText(str(ss['whitening']))
                self.leIterations.setText(str(ss['iterations']))
                self.cbClobber.setChecked(bool(ss['clobber']))
                self.leClobber.setText(str(ss['clobber_size']))
                self.leClobber.setEnabled(self.cbClobber.isChecked())
                if self.teLogs.isVisible():
                    self.refreshLogs()
            else:
                self.swMethod.setCurrentIndex(1)
                self.bApplyOne.hide()
                self.checkboxes.hide()
            # if hasattr(self, 'viewer1'):
            #     self.viewer1.drawSWIMwindow() #1009+


    def _updatePointLists(self):
        clr = inspect.stack()[1].function
        logger.info(f'[{clr}]')
        if self.wTabs.currentIndex() == 1:
            if self.twMethod.currentIndex() == 1:
                siz = self.dm.image_size()
                # for i, p in enumerate(self.dm.manpoints_mir('tra')):
                for i, p in enumerate(self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords']['tra']):
                    if p:
                        msg = 'x=%.1f, y=%.1f' % (p[0] * siz[0], p[1] * siz[1])
                        self.lwL.item(i).setText(msg)
                    else:
                        self.lwL.item(i).setText('')
                for i, p in enumerate(self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts'][
                            'points']['coords']['ref']):
                    if p:
                        msg = 'x=%.1f, y=%.1f' % (p[0] * siz[0], p[1] * siz[1])
                        self.lwR.item(i).setText(msg)
                    else:
                        self.lwR.item(i).setText('')
                self.lwL.update()
                self.lwR.update()



    def deleteAllMpRef(self):
        self.mw.tell('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords']['ref'] = [None]*3
        # delete_matches(self.dm) #1025-
        # delete_correlation_signals(self.dm) #1025-
        self._updatePointLists()
        self.viewer1.drawSWIMwindow()



    def deleteAllMpBase(self):
        self.mw.tell('Deleting All Base Image Manual Correspondence Points from Buffer...')
        # self.dm.set_manpoints('tra', [None, None, None])
        self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords']['tra'] = [None] * 3
        # delete_matches(self.dm)
        # delete_correlation_signals(self.dm) #1025-
        self._updatePointLists()
        self.viewer1.drawSWIMwindow()


    def deleteAllMp(self):
        self.mw.tell('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][
            'ref'] = [None] * 3
        self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['points']['coords'][
            'tra'] = [None] * 3
        # delete_matches(self.dm)
        # delete_correlation_signals(self.dm)
        self._updatePointLists()
        self.viewer1.drawSWIMwindow()



    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self.lwR:
            menu = QMenu()
            # self.deleteMpRefAction = QAction('Delete')
            # self.deleteMpRefAction.triggered.connect(self.deleteMpRef)
            # menu.addAction(self.deleteMpRefAction)
            self.deleteAllMpRefAction = QAction('Clear All Reference Regions')
            self.deleteAllMpRefAction.triggered.connect(self.deleteAllMpRef)
            menu.addAction(self.deleteAllMpRefAction)
            self.deleteAllPtsAction0 = QAction('Clear All Regions')
            self.deleteAllPtsAction0.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction0)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        elif event.type() == QEvent.ContextMenu and source is self.lwL:
            menu = QMenu()
            # self.deleteMpBaseAction = QAction('Delete')
            # self.deleteMpBaseAction.triggered.connect(self.deleteMpBase)
            # menu.addAction(self.deleteMpBaseAction)
            self.deleteAllMpBaseAction = QAction('Clear All Transforming Regions')
            self.deleteAllMpBaseAction.triggered.connect(self.deleteAllMpBase)
            menu.addAction(self.deleteAllMpBaseAction)
            self.deleteAllPtsAction1 = QAction('Clear All Regions')
            self.deleteAllPtsAction1.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction1)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        return super().eventFilter(source, event)


    def disableZoomSlider(self):
        self._allow_zoom_change = False

    def enableZoomSlider(self):
        self._allow_zoom_change = True

    def setZoomSlider(self):
        clr = inspect.stack()[1].function
        if clr == 'main':
            logger.info(f'[{clr}]')
            if self._allow_zoom_change:
                # clr = inspect.stack()[1].function
                if self.dm['state']['current_tab'] == 1:
                    zoom = self.viewer1.zoom()
                else:
                    zoom = self.viewer0.zoom()
                if zoom == 0:
                    return
                # val =
                # if val in range(-2147483648, 2147483647):
                try:
                    self.sldrZoomTab1.setValue(1 / zoom)
                except:
                    print_exception()
                    logger.warning(f"zoom = {zoom}")
                # self.sldrZoomTab1.setValue(zoom)
                self._allow_zoom_change = True

    def onZoomSlider(self):
        clr = inspect.stack()[1].function
        logger.info(f'clr: {clr}')
        if clr not in ('slotUpdateZoomSlider', 'setValue'):  # Original #0314
            _tab = self.wTabs.currentIndex()
            # if _tab == 0:
            #     val = 1 / self.sldrZoomTab0.value()
            #     if abs(self.viewer0.state.cross_section_scale - val) > .0001:
            #         self.viewer0.set_zoom(val)
            if _tab == 1:
                val = 1 / self.sldrZoomTab1.value()
                if abs(self.viewer1.state.cross_section_scale - val) > .0001:
                    self.viewer1.set_zoom(val)



    def slotUpdateZoomSlider(self):
        # Lets only care about REF <--> wSlider
        clr = inspect.stack()[1].function
        logger.info(f'[{clr}]')
        _tab = self.wTabs.currentIndex()
        # if _tab == 0:
        #     val = self.viewer0.state.cross_section_scale
        #     if val:
        #         if val != 0:
        #             self.sldrZoomTab0.setValue(float(val * val))
        if _tab == 1:
            val = self.viewer1.state.cross_section_scale
            if val:
                if val != 0:
                    self.sldrZoomTab1.setValue(float(val * val))


    def initUI_table(self):
        '''Layer View Widget'''
        logger.info('')
        self.project_table = ProjectTable(parent=self, dm=self.dm)
        self.project_table.updatePbar.connect(self.mw.pbar.setValue)
        # self.project_table.setStyleSheet("color: #f3f6fb;")
        vbl = VBL()
        vbl.addWidget(self.project_table)
        self.label_overview = VerticalLabel('Project Data Table View')
        self.label_overview.setStyleSheet("""
        background-color: #161c20;
        color: #ede9e8;""")
        hbl = HBL()
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.wTable.setLayout(hbl)
        self.wTable.setStyleSheet("background-color: #222222; color: #f3f6fb;")


    def updateTreeWidget(self):
        # self.mw.statusBar.showMessage('Loading data into tree view...')
        # time consuming - refactor?
        self.mw.tell('Loading data into tree view...')
        self.mdlTreeview.load(self.dm.to_dict())
        # self.treeview.setModel(self.mdlTreeview)
        self.treeview.header().resizeSection(0, 340)


    #0731
    def get_treeview_data(self, index=None):
        # logger.info(f'arg passed {index}')
        if index == None:
            index = self.treeview.selectedIndexes()[0]
        # logger.info(f'index is {index}')
        cur_key = index.data()
        par_key = index.parent().data()
        # print(f"cur_key = {cur_key}")
        # print(f"par_key = {par_key}")
        if par_key == 'stack':
            self.dm.zpos = int(cur_key)


    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self.mdlTreeview = JsonModel(parent=self, dm=self.dm)
        self.treeview = QTreeView()
        self.treeview.expanded.connect(lambda index: self.get_treeview_data(index))
        # self.treeview.setStyleSheet("color: #161c20;")
        self.treeview.setAnimated(True)
        self.treeview.header().resizeSection(0, 340)
        self.treeview.setIndentation(14)
        self.treeview.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.treeview.header().resizeSection(0, 380)
        # self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        # self.mdlTreeview.signals.dataModelChanged.connect(self.load_data_from_treeview) #0716-
        self.treeview.setModel(self.mdlTreeview)
        self.treeview.setAlternatingRowColors(True)
        self.wTreeview.setContentsMargins(0, 0, 0, 0)
        self.bCollapseTree = QPushButton('Collapse All')
        self.bCollapseTree.setToolTip('Collapse all tree nodes')
        self.bCollapseTree.setFixedSize(80, 18)
        self.bCollapseTree.clicked.connect(self.treeview.collapseAll)
        self.bExpandTree = QPushButton('Expand All')
        self.bExpandTree.setToolTip('Expand all tree nodes')
        self.bExpandTree.setFixedSize(80, 18)
        self.bExpandTree.clicked.connect(self.treeview.expandAll)
        self.bCurTree = QPushButton('Current Section')

        def fn():
            self.updateTreeWidget()
            self.mdlTreeview.jumpToLayer()

        self.bCurTree.setToolTip('Jump to the data for current section and level')
        self.bCurTree.setFixedSize(80, 18)
        self.bCurTree.clicked.connect(fn)

        def fn():
            self.updateTreeWidget()
            self.treeview.collapseAll()

        self.bReloadTree = QPushButton('Reload')
        self.bReloadTree.setToolTip('Jump to the data for current section and level')
        self.bReloadTree.setFixedSize(80, 18)
        self.bReloadTree.clicked.connect(fn)

        def goToData():
            logger.info('')
            if self.leJumpTree.text():
                section = int(self.leJumpTree.text())
            else:
                section = self.dm.zpos
            # if (len(self.le_tree_jumpToScale.text()) > 0) and \
            #         (int(self.le_tree_jumpToScale.text()) in self.dm.lvls()):
            #     scale = get_scale_key(int(self.le_tree_jumpToScale.text()))
            # else:
            scale = self.dm.level
            self.updateTreeWidget()

            keys = ['stack', section, 'levels', scale]

            opt = self.cbxTree.currentText()
            logger.info(f'opt = {opt}')
            if opt:
                try:
                    if opt == 'Section':
                        pass
                    elif opt == 'Results':
                        keys.extend(['results'])
                    # elif opt == 'Alignment History':
                    #     keys.extend(['alignment_history'])
                    elif opt == 'SWIM Settings':
                        keys.extend(['swim_settings'])

                    logger.info(f'keys = {keys}')
                except:
                    print_exception()
                else:
                    self.mdlTreeview.jumpToKey(keys=keys)

        # self.le_tree_jumpToScale = QLineEdit()
        # self.le_tree_jumpToScale.setFixedHeight(18)
        # self.le_tree_jumpToScale.setFixedWidth(30)
        # def fn():
        #     requested = int(self.le_tree_jumpToScale.text())
        #     if requested in self.dm.lvls():
        #         self.updateTreeWidget()
        #         self.mdlTreeview.jumpToScale(level=get_scale_key(requested))
        # self.le_tree_jumpToScale.returnPressed.connect(goToData)

        self.leJumpTree = QLineEdit()
        self.leJumpTree.setFixedHeight(18)
        self.leJumpTree.setFixedWidth(30)
        self.leJumpTree.returnPressed.connect(goToData)

        self.cbxTree = QComboBox()
        self.cbxTree.setFixedWidth(120)
        items = ['--', 'SWIM Settings', 'Method Results', 'Alignment History']
        self.cbxTree.addItems(items)

        self.bGoTree = QPushButton('Go')
        self.bGoTree.clicked.connect(goToData)
        self.bGoTree.setFixedSize(28, 18)

        self.lJumpTree = QLabel('Jump To: ')
        self.lJumpTree.setAlignment(Qt.AlignRight)
        self.lJumpTree.setFixedHeight(18)

        hbl = HBL()
        hbl.setSpacing(4)
        hbl.addWidget(self.bReloadTree)
        hbl.addWidget(self.bCollapseTree)
        hbl.addWidget(self.bExpandTree)
        hbl.addWidget(ExpandingWidget(self))
        hbl.addWidget(self.lJumpTree)
        # hbl.addWidget(QLabel(' Level:'))
        # hbl.addWidget(self.le_tree_jumpToScale)
        hbl.addWidget(QLabel(' Section:'))
        hbl.addWidget(self.leJumpTree)
        hbl.addWidget(self.cbxTree)
        hbl.addWidget(self.bGoTree)
        hbl.addWidget(self.bCurTree)
        btns = QWidget()
        btns.setContentsMargins(2, 2, 2, 2)
        btns.setFixedHeight(24)
        btns.setLayout(hbl)

        self.treeHbl = HBL()
        self.treeHbl.setSpacing(0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setStyleSheet("""background-color: #161c20; color: #ede9e8;""")
        self.wTreeview = HW(lab, VW(self.treeview, btns))

    def initUI_plot(self):
        '''SNR Plot Widget'''
        logger.info('')
        self.snr_plot = SnrPlot(dm=self.dm)
        lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#ede9e8', font_size=13)
        lab_Xaxis = QLabel('Serial Section #')
        lab_Xaxis.setStyleSheet("font-size: 13px;")
        lab_Xaxis.setAlignment(Qt.AlignHCenter)
        self.wSNR = VW(HW(lab_yaxis, self.snr_plot), lab_Xaxis)
        self.wSNR.setStyleSheet('background-color: #222222; font-weight: 600; font-size: 14px; color: #ede9e8;')
        self.dSnr_plot = SnrPlot(dm=self.dm, dock=True)
        self.dSnr_plot.setStyleSheet('background-color: #222222; font-weight: 600; font-size: 12px; color: #ede9e8;')
        self.mw.dwSnr.setWidget(self.dSnr_plot)


    def initTabs(self):
        '''Tab Widget'''
        logger.info('')
        self.wTabs = QTabWidget()
        self.wTabs.setStyleSheet("""
        QTabBar::tab {
            color: #141414;
            padding-top: 1px;
            padding-bottom: 1px;
            height: 15px;
            font-size: 10px;
            border: 1px solid #ede9e8;
            background-color: #dadada;
        }
        QTabBar::tab:selected
        {
            font-weight: 600;
            font-size: 10px;
            color: #f3f6fb;
            background-color: #222222;
        }
        """)
        self.wTabs.setDocumentMode(True) #When this property is set the tab widget getFrameScale is not rendered.
        # self.wTabs.setTabPosition(QTabWidget.South)
        self.wTabs.setFocusPolicy(Qt.NoFocus)
        self.wTabs.tabBar().setExpanding(True)
        self.wTabs.setTabsClosable(False)

        self.leMaxDownsampling = QLineEdit()

        self.leMaxDownsampling.setFixedHeight(18)
        self.leMaxDownsampling.setFixedWidth(30)
        self.leMaxDownsampling.setValidator(QIntValidator())

        def update_le_max_downsampling():
            logger.info('')
            n = int(self.leMaxDownsampling.text())
            cfg.max_downsampling = int(n)

        self.leMaxDownsampling.setText(str(cfg.max_downsampling))
        self.leMaxDownsampling.textEdited.connect(update_le_max_downsampling)
        self.leMaxDownsampling.returnPressed.connect(update_le_max_downsampling)

        self.leMaxDownsampledSize = QLineEdit()
        self.leMaxDownsampledSize.setFixedHeight(18)
        self.leMaxDownsampledSize.setFixedWidth(30)
        self.leMaxDownsampledSize.setValidator(QIntValidator())

        def update_le_max_downsampled_size():
            logger.info('')
            n = int(self.leMaxDownsampledSize.text())
            cfg.max_downsampled_size = int(n)

        self.leMaxDownsampledSize.setText(str(cfg.max_downsampled_size))
        self.leMaxDownsampledSize.textEdited.connect(update_le_max_downsampled_size)
        self.leMaxDownsampledSize.returnPressed.connect(update_le_max_downsampled_size)

        self.bZarrRefresh = QPushButton('Refresh')
        self.bZarrRefresh.setIcon(qta.icon("fa.refresh"))
        self.bZarrRefresh.clicked.connect(self.refreshTab)

        tip = """Bounding Box is a parameter associated with the cumulative alignment. Caution: Turning bounding box ON may 
        significantly increase the size of generated images (default=False)."""
        self.cbBB = QCheckBox()
        self.cbBB.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cbBB.toggled.connect(lambda state: self.dm.set_use_bounding_rect(state))

        tip = 'Bias/Polynomial Correction is a parameter associated with the cumulative affine. It can counteract ' \
              'distortions caused by cumulative drift (default=0)'
        self.cbxBias = QComboBox()
        self.cbxBias.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cbxBias.addItems(['None', 'poly 0°', 'poly 1°', 'poly 2°', 'poly 3°', 'poly 4°'])
        self.cbxBias.currentIndexChanged.connect(self.onBiasChanged)
        self.cbxBias.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cbxBias.setFixedWidth(58)
        self.cbxBias.lineEdit()

        self.bRegenerateAll = QPushButton('Regenerate All Output')
        self.bRegenerateAll.clicked.connect(lambda: self.regenerateAll())
        self.bRegenerateAll.setFixedHeight(15)


        self.bShowHideOverlay = QPushButton('Hide')
        # self.bShowHideOverlay.setAutoFillBackground(False)
        # self.bShowHideOverlay.setStyleSheet("background: transparent;")
        # self.bShowHideOverlay.setAttribute(Qt.WA_TranslucentBackground)
        self.bShowHideOverlay.setIcon(qta.icon('mdi.close'))
        def fn():
            self.setUpdatesEnabled(False)
            self.wOverlayControls.setVisible(not self.wOverlayControls.isVisible())
            self.bShowHideOverlay.setText(('Show','Hide')[self.wOverlayControls.isVisible()])
            self.bShowHideOverlay.setIcon(qta.icon(('mdi.arrow-top-left', 'mdi.close')[self.wOverlayControls.isVisible()]))
            if not self.wOverlayControls.isVisible():
                if self.twInfoOverlay.isVisible():
                    self.twInfoOverlay.hide()
                    self.bInfo.setText('Show TIFF Info')
            self.setUpdatesEnabled(True)
        self.bShowHideOverlay.clicked.connect(fn)
        self.bShowHideOverlay.setFixedSize(40,14)

        self.bInfo = QPushButton("Show TIFF Info")
        # self.bInfo.setFixedHeight(15)
        def fn():
            self.twInfoOverlay.setVisible(not self.twInfoOverlay.isVisible())
            self.bInfo.setText(('Show TIFF Info', 'Hide TIFF Info')[self.twInfoOverlay.isVisible()])
            if self.twInfoOverlay.isVisible():
                p = Path(self.dm.images_path) / 'tiffinfo.txt'
                tiffinfo = read('txt')(p)
                try:
                    self.teInfoOverlay.setText(tiffinfo)
                except:
                    print_exception(f"type(tiffinfo) = {type(tiffinfo)}")
        self.bInfo.clicked.connect(fn)

        self.wOverlayControls = QWidget()
        self.wOverlayControls.setObjectName('wOverlayControls')
        self.wOverlayControls.setStyleSheet("QLabel{color: #FFFF66;} "
                                            "QWidget#wOverlayControls{padding: 2px; color: #FFFF66; background-color: rgba(0, 0, 0, 0.25); border-radius: 2px;}")
        self.flOverlaycontrols = QFormLayout()
        self.flOverlaycontrols.setContentsMargins(2,2,2,2)
        self.wOverlayControls.setLayout(self.flOverlaycontrols)
        self.flOverlaycontrols.setVerticalSpacing(2)
        self.flOverlaycontrols.setHorizontalSpacing(4)
        self.flOverlaycontrols.setLabelAlignment(Qt.AlignRight)
        self.flOverlaycontrols.setFormAlignment(Qt.AlignCenter)

        self.HL1 = QHLine()
        self.HL1.setStyleSheet("background-color: #FFFF66;")
        # self.flOverlaycontrols.addWidget(self.bZarrRefresh)
        # self.flOverlaycontrols.addWidget(QLabel('3D Alignment Options'))
        # self.flOverlaycontrols.addRow("Bounding Box:", self.cbBB)
        # self.flOverlaycontrols.addWidget(QLabel('Corrective Bias'))
        # self.flOverlaycontrols.addWidget(self.cbxBias)
        self.flOverlaycontrols.addWidget(HW(self.cbxBias, QLabel('Corrective Bias'), spacing=4))
        # self.flOverlaycontrols.addRow("Corrective Bias:", self.cbxBias)


        self.bInfo.setFixedHeight(16)
        self.bZarrRefresh.setFixedHeight(16)

        self.HL0 = QHLine()
        self.HL0.setStyleSheet("background-color: #FFFF66;")
        # self.flOverlaycontrols.addWidget(QLabel('Neuroglancer Volume\nRendering Preferences'))
        # self.flOverlaycontrols.addWidget()
        self.flOverlaycontrols.addWidget(HW(self.leMaxDownsampling, QLabel('Max Downsampling\n(NG default=64)'), spacing=4))
        # self.flOverlaycontrols.addWidget()
        self.flOverlaycontrols.addWidget(HW(self.leMaxDownsampledSize, QLabel('Max Downsamp. Size\n(sdefault=128)'), spacing=4))
        # self.flOverlaycontrols.addRow("Max Downsampling\n(NG default=64):", self.leMaxDownsampling)
        # self.flOverlaycontrols.addRow("Max Downsampled Size\n(NG default=128):", self.leMaxDownsampledSize)
        # self.flOverlaycontrols.addWidget(self.bInfo)

        self.wOverlay = VW(self.bShowHideOverlay, self.wOverlayControls)
        self.wOverlay.layout.setAlignment(Qt.AlignRight)
        self.wOverlay.setFixedWidth(140)

        self.teInfoOverlay = QTextEdit()
        self.teInfoOverlay.setReadOnly(True)

        self.twInfoOverlay = QTabWidget()
        self.twInfoOverlay.addTab(self.teInfoOverlay, 'TIFF Info')
        # self.twInfoOverlay.setMaximumSize(QSize(700, 700))
        self.twInfoOverlay.setFixedSize(QSize(380, 300))
        self.twInfoOverlay.hide()

        self.sldrZoomTab0 = DoubleSlider(Qt.Orientation.Vertical, self)
        self.sldrZoomTab0.setFocusPolicy(Qt.NoFocus)
        self.sldrZoomTab0.setMouseTracking(True)
        # self.sldrZoomTab1.setInvertedAppearance(True)
        self.sldrZoomTab0.setMaximum(4)
        self.sldrZoomTab0.setMinimum(1)
        # self.sldrZoomTab0.valueChanged.connect(self.onZoomSlider)
        self.sldrZoomTab0.setValue(4.0)

        vlab = VerticalLabel('Zoom:')

        self.wSldrZoomTab0 = VW()
        self.wSldrZoomTab0.layout.setSpacing(0)
        self.wSldrZoomTab0.setFocusPolicy(Qt.NoFocus)
        self.wSldrZoomTab0.setFixedWidth(16)
        self.wSldrZoomTab0.addWidget(self.sldrZoomTab0)
        self.wSldrZoomTab0.addWidget(vlab)

        self.vlabTab0 = VerticalLabel('Neuroglancer 3DEM View')

        self.glWebengine0 = GL()
        self.glWebengine0.addWidget(self.we0, 0, 0, 3, 3)
        self.glWebengine0.addWidget(self.wOverlay, 2, 2, 1, 1, Qt.AlignBottom | Qt.AlignRight)
        self.glWebengine0.addWidget(self.twInfoOverlay, 0, 0, 3, 3, Qt.AlignCenter)
        self.wWebengine0 = QWidget()
        self.wWebengine0.setLayout(self.glWebengine0)

        # self.wTab0 = HW(self.vlabTab0, VW(self.toolbar0, self.wWebengine0), self.wSldrZoomTab0)
        self.vwTab0 = VW(self.toolbar0, self.wWebengine0)
        self.wTab0 = HW(self.vlabTab0, self.vwTab0)

        tabs = [(self.wTab0, '3D Alignment'),
                (self.wTab1, 'Edit Alignment'),
                (self.wSNR, ' All SNR Plots '),
                (self.wTable, ' Table '),
                (self.wTreeview, ' JSON ')
                ]
        for tab in tabs:
            self.wTabs.addTab(tab[0], tab[1])

        self.setLayout(VBL(self.wTabs))

    def onBiasChanged(self):
        logger.info('')
        clr = inspect.stack()[1].function
        if clr == 'main':
            if self.cbxBias.currentText() == 'None':
                val = None
            else:
                val = self.cbxBias.currentIndex() - 1
            self.mw.tell(f'Corrective bias is set to {val}')
            self.dm.poly_order = val
            self.dm.set_stack_cafm()
            # self.initNeuroglancer()
            if self.dm.is_aligned():
                self.viewer0.set_transformed()

    def initShader(self):

        def resetBrightessAndContrast():
            reset_val = 0.0
            self.dm.brightness = reset_val
            self.dm.contrast = reset_val
            self.sldBrightness.setValue(int(self.dm.brightness))
            self.sldContrast.setValue(int(self.dm.contrast))
            if self.wTabs.currentIndex() == 0:
                self.viewer0.set_brightness()
                self.viewer0.set_contrast()
            elif self.wTabs.currentIndex() == 1:
                self.viewer1.set_brightness()
                self.viewer1.set_contrast()

        self.bResetShaders = QPushButton('Reset')
        self.bResetShaders.setFixedSize(QSize(34, 15))
        self.bResetShaders.clicked.connect(resetBrightessAndContrast)

        self.bVolumeRendering = QPushButton('Volume')
        self.bVolumeRendering.setFixedSize(QSize(40, 15))
        self.bVolumeRendering.clicked.connect(self.fn_volume_rendering)

        self.leBrightness = QLineEdit()
        self.leBrightness.setAlignment(Qt.AlignCenter)
        self.leBrightness.setText('%d' % self.dm.brightness)
        self.leBrightness.setValidator(QIntValidator(-100, 100))
        self.leBrightness.setFixedSize(QSize(38, 15))
        self.leBrightness.textEdited.connect(
            lambda: self.sldBrightness.setValue(int(self.leBrightness.text())))
        self.leBrightness.textEdited.connect(self.fn_brightness_control)
        self.sldBrightness = QSlider(Qt.Orientation.Horizontal, self)
        # self.sldBrightness.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.sldBrightness.setFixedWidth(150)
        self.sldBrightness.setMouseTracking(False)
        self.sldBrightness.setFocusPolicy(Qt.NoFocus)
        self.sldBrightness.setRange(-100, 100)
        self.sldBrightness.sliderReleased.connect(self.fn_brightness_control)
        self.sldBrightness.valueChanged.connect(lambda: self.leBrightness.setText('%d' % self.sldBrightness.value()))
        self.lBrightness = BoldLabel('  Brightness  ')
        self.wBrightness = HW(self.lBrightness, self.sldBrightness, self.leBrightness)
        # self.wBrightness.layout.setSpacing(4)
        self.wBrightness.setMaximumWidth(180)

        self.leContrast = QLineEdit()
        self.leContrast.setAlignment(Qt.AlignCenter)
        self.leContrast.setText('%d' % self.dm.contrast)
        self.leContrast.setValidator(QIntValidator(-100, 100))
        self.leContrast.setFixedSize(QSize(38, 15))
        self.leContrast.textEdited.connect(
            lambda: self.sldContrast.setValue(int(self.leContrast.text())))
        self.leContrast.textEdited.connect(self.fn_contrast_control)
        self.sldContrast = QSlider(Qt.Orientation.Horizontal, self)
        # self.sldContrast.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.sldContrast.setFixedWidth(150)
        self.sldContrast.setMouseTracking(False)
        self.sldContrast.setFocusPolicy(Qt.NoFocus)
        self.sldContrast.setRange(-100, 100)
        self.sldContrast.sliderReleased.connect(self.fn_contrast_control)
        self.sldContrast.valueChanged.connect(
            lambda: self.leContrast.setText('%d' % self.sldContrast.value()))
        self.lContrast = BoldLabel('  Contrast  ')

        self.wContrast = HW(self.lContrast, self.sldContrast, self.leContrast)
        # self.wContrast.layout.setSpacing(4)
        self.wContrast.setMaximumWidth(180)

        # self.wBC = HW(self.wBrightness, self.wContrast, self.bResetShaders, self.bVolumeRendering)
        self.wBC = HW(self.wBrightness, self.wContrast, self.bResetShaders)
        self.wBC.setMaximumWidth(400)


    def fn_brightness_control(self):
        clr = inspect.stack()[1].function
        if clr == 'main':
            self.dm.brightness = self.sldBrightness.value() / 100
            if self.wTabs.currentIndex() == 0:
                self.viewer0.set_brightness()
            elif self.wTabs.currentIndex() == 1:
                self.viewer1.set_brightness()
                self.transformViewer.set_brightness()

    def fn_contrast_control(self):
        clr = inspect.stack()[1].function
        if clr == 'main':
            self.dm.contrast = self.sldContrast.value() / 100
            if self.wTabs.currentIndex() == 0:
                self.viewer0.set_contrast()
            elif self.wTabs.currentIndex() == 1:
                self.viewer1.set_contrast()
                self.transformViewer.set_contrast()


    def fn_volume_rendering(self):
        logger.info('')
        state = copy.deepcopy(self.viewer0.state)
        state.showSlices = False
        self.viewer0.set_state(state)


    def jump_to_manual(self, requested) -> None:
        logger.info(f'requested: {requested}')
        if requested in range(len(self.dm)):
            self.dm.zpos = requested
        else:
            logger.warning('Requested index is not valid.')


class ScaledPixmapLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setScaledContents(True)

    def paintEvent(self, event):
        if self.pixmap():
            pm = self.pixmap()
            try:
                originalRatio = pm.width() / pm.height()
                currentRatio = self.width() / self.height()
                if originalRatio != currentRatio:
                    qp = QPainter(self)
                    pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    rect = QRect(0, 0, pm.width(), pm.height())
                    rect.moveCenter(self.rect().center())
                    qp.drawPixmap(rect, pm)
                    return
            except ZeroDivisionError:
                print_exception()
        super().paintEvent(event)


class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

'''
Forward key strokes to QWebEngineView:
new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_R, Qt.KeyboardModifiers(),"r",)
new_event.artificial = True
QCoreApplication.postEvent(cfg.pt.viewer0.webengine0.focusProxy(), new_event)

            MB = Qt.MouseButton
            KM = Qt.KeyboardModifier
            pos = QPointF(5.,5.)
            pixdel = QPoint()
            angdel = QPoint(int(10), int(10))
            btns = MB.NoButton
            mods = KM.NoModifier
            phase = Qt.ScrollPhase.NoScrollPhase
            inverted = False
            scroll_event = QWheelEvent(pos, pos, pixdel, angdel, btns, mods, phase, inverted)
            
            
https://github.com/vispy/jupyter_rfb/issues/48
'''
class ForwardKeyEvent(QObject):
    def __init__(self, sender, receiver, parent=None):
        super(ForwardKeyEvent, self).__init__(parent)
        self.m_sender = sender
        self.m_receiver = receiver
        self.m_sender.installEventFilter(self)

    def eventFilter(self, obj, event):
        if self.m_sender is obj and event.type() == QEvent.KeyPress:
            new_event = QKeyEvent(
                QEvent.KeyPress, 65, Qt.KeyboardModifiers(),"r",)
            new_event.artificial = True
            QCoreApplication.postEvent(self.m_receiver.focusProxy(), new_event)
            return True
        return False




class WebEngine(QWebEngineView):

    
    def __init__(self, parent, ID='webengine0'):
        super().__init__(parent)
        self.ID = ID
        # self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)
        # self.focusProxy().installEventFilter(self)
        # self.installEventFilter(self)

    # def injectEvent(self, new_event):
    #     new_event.artificial = True
    #     QCoreApplication.postEvent(self.focusProxy(), new_event)
    # 
    # def rotate(self):
    #     new_event = QKeyEvent(QEvent.KeyPress, Qt.Key_R, Qt.KeyboardModifiers(), "r", )
    #     new_event.artificial = True
    #     QCoreApplication.postEvent(self.focusProxy(), new_event)

        # self.widget_id = id(self.children()[2])
        # self.inFocus = Signal(str)
        # self.installEventFilter(self)
        # self.focusProxy().installEventFilter(self)
        # self.installEventFilter(self)



    # def eventFilter(self, obj, event):
    #     # print(event.type())
    #     _type = event.type()
    #     print(_type)
    #     if _type == QEvent.Wheel:
    #         print(event.angleDelta())
    #         print(f"[{_type}] SCROLL event!")
    #         self.se = event
    #         return False
    #     elif _type == QEvent.KeyPress and hasattr(event, "artificial"):
    #         print("event:", event.key(), event.text())
    #         return False
    #     return super().eventFilter(obj, event)



    # def eventFilter(self, object, event):
    #     if event.type() == QEvent.Enter:
    #         # self.inFocus.emit(self.ID)
    #         logger.info(f"Entering Focus of ({self.ID})")
    #         # self.stop = True
    #         # print('program stop is', self.stop)
    #         # return True
    #     elif event.type() == QEvent.Leave:
    #         logger.info(f"Leaving Focus of ({self.ID})")
    #         # self.stop = False
    #         # print('program stop is', self.stop)
    #     return True


class Rect(QWidget):
    clicked = Signal()

    def __init__(self, ID):
        super().__init__()
        self.ID = ID
        # self.setGeometry(30,30,600,400)
        self.begin = QPoint()
        self.end = QPoint()
        self.show()

    def paintEvent(self, event):
        qp = QPainter(self)
        br = QBrush(QColor(100, 10, 10, 40))
        qp.setBrush(br)
        qp.drawRect(QRect(self.begin, self.end))

    def mousePressEvent(self, event):
        self.clicked.emit()
        logger.critical(f'Rect {self.ID} clicked!')
        self.begin = event.pos()
        self.end = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.begin = event.pos()
        self.end = event.pos()
        self.update()


class ClickRegion(QLabel):
    clicked = Signal()

    def __init__(self, parent, color, name, **kwargs):
        # super().__init__(parent, **kwargs)
        super().__init__(parent)
        self.name = name
        self.color = color
        if name:
            self.setObjectName(name)
        # self.setStyleSheet('color: #f3f6fb;')
        self.setStyleSheet(f'background-color: {self.color}; border: 2px solid #f3f6fb;')
        self.isClicked = 1

    def mousePressEvent(self, ev):
        self.isClicked = 1 - self.isClicked
        if self.isClicked:
            self.activate()
        else:
            self.inactivate()
        self.clicked.emit()

    def activate(self):
        self.isClicked = 1
        self.setStyleSheet(f'background-color: {self.color}; border: 2px solid #f3f6fb;')

    def inactivate(self):
        self.isClicked = 0
        self.setStyleSheet(f'background-color: #dadada; border: 2px dotted #141414;')

    def setActivated(self, val):
        if val:
            self.activate()
        else:
            self.inactivate()

    # def onClick(self):
    #     logger.info(f'{self.name} was clicked!')
    #     if self.isClicked:
    #         self.setStyleSheet(f'background-color: {self.color};')
    #     else:
    #         self.setStyleSheet(f'background-color: #dadada;')

class CheckableComboBox(QComboBox):
    # cfg.pt.checkableCombobox.model().item(0).checkState()
    # 0 = unchecked, 2 = checked
    # cfg.pt.checkableCombobox.model().item(0).setCheckState(0) <-- set unchecked
    # cfg.pt.checkableCombobox.model().item(0).setCheckState(2) <-- set checked

    def addItem(self, item, state=0):
        super(CheckableComboBox, self).addItem(item)
        item = self.model().item(self.count()-1,0)
        if self.count() > 1:
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            # item.setCheckState(Qt.Unchecked)
            item.setCheckState(0)

    def itemChecked(self, index):
        item = self.model().item(index,0)
        return item.checkState() == Qt.Checked


class WarningNotice(QWidget):

    def __init__(self, parent, msg, fixbutton=False, symbol=None, **kwargs):
        super().__init__(parent)
        self.msg = msg
        self.label = QLabel(self.msg)
        self.label.setStyleSheet("QLabel { background: none; font-size: 9px; color: #a30000; font-weight: 600;"
                                 "padding: 0px; } ")
        self.label.setWordWrap(True)
        self.layout = HBL()
        self.layout.setSpacing(4)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor('#ffcccb'))
        p.setColor(QPalette.Text, QColor("#d0342c"))
        # # self.gbWarnings.setStyleSheet("font-weight: 600; color: #d0342c; background-color: #ffcccb;")

        # font = QFont()
        # font.setBold(True)
        # self.setFont(font)

        # if symbol:
        #     self.symbol = QLabel(symbol)
        #     self.symbol.setStyleSheet("""color: #f3f6fb; font-size: 16px; background-color: #ff0000; border-radius:
        #     6px; font-weight: 600; padding: 2px;""")
        #     self.symbol.setFixedSize(QSize(16,16))
        #     self.symbol.setAlignment(Qt.AlignCenter)
        #     self.layout.addWidget(self.symbol)

        if fixbutton:
            self.fixbutton = QPushButton('Fix All')
            # self.fixbutton.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            self.fixbutton.setFixedSize(QSize(36, 16))
            self.layout.addWidget(self.fixbutton)

        self.layout.addWidget(self.label)
        self.layout.setContentsMargins(6,2,6,2)

        self.setLayout(self.layout)


class ClickLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent, **kwargs):
        # super().__init__(parent, **kwargs)
        super().__init__(parent)
        self.isChecked = 0

    def mousePressEvent(self, ev):
        self.isChecked = 1 - self.isChecked
        self.clicked.emit()

    def setChecked(self, b):
        self.isClicked = b
        if self.isClicked:
            # self.setStyleSheet(
            #     """background-color: #dadada;
            #     color: #222222;
            #     font-size: 10px;
            #     font-weight: 600;""")
            self.setStyleSheet(
                """background-color: #339933; 
                color: #f3f6fb; 
                font-size: 10px; 
                font-weight: 600;""")
        else:
            # self.setStyleSheet(
            #     """background-color: #222222;
            #     color: #ede9e8;
            #     font-size: 10px;
            #     font-weight: 600;""")
            self.setStyleSheet(
                """ color: #141414;
                    padding-top: 1px;
                    padding-bottom: 1px;
                    height: 15px;
                    font-size: 10px;
                    border: 1px solid #ede9e8;
                    background-color: #dadada;
                """)

    def isChecked(self):
        return self.isChecked


class ListWidget(QListWidget):
    def __init__(self,):
        super(QListWidget, self).__init__()
        self.setFocusPolicy(Qt.NoFocus)

    def sizeHint(self):
        s = QSize()
        s.setHeight(super(ListWidget,self).sizeHint().height())
        s.setWidth(self.sizeHintForColumn(0))
        return s


class GroupBox(QGroupBox):
    clicked = Signal(str, object)

    def __init__(self, title=''):
        super(GroupBox, self).__init__()
        self.title = title
        self.setTitle(self.title)

    def mousePressEvent(self, event):
        child = self.childAt(event.pos())
        if not child:
            child = self
        self.clicked.emit(self.title, child)


class ListItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.decorationPosition = QStyleOptionViewItem.Right
        super(ListItemDelegate, self).paint(painter, option, index)


class BoldLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet('font-weight: 600; font-size: 10px;')


def setWebengineProperties(webengine):
    webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True) #Turning this off block neuroglancer, expectedly
    webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    # webengine0.settings().setAttribute(QWebEngineSettings.ErrorPageEnabled, True)


def delete_correlation_signals(dm):
    logger.info('')
    files = dm.get_signals_filenames(s=dm.scale, l=dm.zpos)
    # logger.info(f'Deleting:\n{sigs}')
    for f in files:
        if os.path.isfile(f):  # this makes the code more robust
            os.remove(f)


def delete_matches(dm):
    logger.info('')
    files = dm.get_matches_filenames(s=dm.scale, l=dm.zpos)
    # logger.info(f'Deleting:\n{sigs}')
    for f in files:
        if os.path.isfile(f):  # this makes the code more robust
            # logger.info(f"Removing {f}...")
            os.remove(f)



if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    pt = AlignmentTab()
    main_window.setCentralWidget(pt)
    main_window.show()
    sys.exit(app.exec_())