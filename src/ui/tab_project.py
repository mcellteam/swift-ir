#!/usr/bin/env python3
import os, sys, logging, inspect, copy, time, warnings
from datetime import datetime
import textwrap, pprint
import neuroglancer as ng
import numpy as np
import shutil
import qtawesome as qta
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWebEngineWidgets import *
import src.config as cfg
from src.helpers import print_exception, getOpt, setOpt, getData, setData, caller_name, is_tacc, is_joel
from src.viewer_em import EMViewer, PMViewer
from src.viewer_ma import MAViewer
from src.ui.snr_plot import SnrPlot
from src.ui.project_table import ProjectTable
from src.ui.models.json_tree import JsonModel
from src.ui.sliders import DoubleSlider
from src.ui.thumbnail import CorrSignalThumbnail, ThumbnailFast
from src.ui.gif_player import GifPlayer
from src.ui.layouts import HBL, VBL, GL, HW, VW, HSplitter, VSplitter
from src.ui.joystick import Joystick
from src.funcs_image import SetStackCafm
# from src import DataModel
from src.data_model import DataModel
from src.hash_table import HashTable

__all__ = ['ProjectTab']

logger = logging.getLogger(__name__)

DEV = is_joel()

class ProjectTab(QWidget):

    def __init__(self,
                 parent,
                 path=None,
                 datamodel=None):
        super().__init__(parent)
        logger.info(f'Initializing Project Tab...\nID(datamodel): {id(datamodel)}, Path: {path}')
        # self.signals = Signals()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.parent = parent
        self.path = path
        self.viewer = None
        self.datamodel = self.dm = datamodel
        self.setUpdatesEnabled(True)
        # self.webengine = QWebEngineView()
        self.webengine = WebEngine(ID='emViewer')
        self.webengine.setStyleSheet("background-color: #000000;")
        self.webengine.setFocusPolicy(Qt.NoFocus)
        self.webengine.loadFinished.connect(lambda: print('Web engine load finished!'))
        # setWebengineProperties(self.webengine)
        # self.webengine.setStyleSheet('background-color: #222222;')
        self.webengine.setMouseTracking(True)
        self.focusedViewer = None
        # self.setAutoFillBackground(True)
        self.indexConfigure = 0
        self.wTable = QWidget()
        self.wTreeview = QWidget()
        self.initShader()
        self.initGif()
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        self.initTabs()
        self.wTabs.currentChanged.connect(self._onTabChange)
        self.manAlignBufferRef = []
        self.manAlignBufferBase = []
        self.mp_colors = cfg.glob_colors
        self._allow_zoom_change = True
        self.oldPos = None
        self.blinkCur = 0
        # self.initNeuroglancer(init_all=True)
        self.dm.signals.zposChanged.connect(self.parent.updateSlidrZpos)
        self.dm.signals.zposChanged.connect(self.parent.setSignalsPixmaps)
        self.dm.signals.zposChanged.connect(self.parent.setTargKargPixmaps)

        self.dm.signals.dataChanged.connect(self.updateAaButtons)
        self.dm.signals.dataChanged.connect(lambda: self.cbDefaults.setChecked(self.dm.isDefaults()))
        self.dm.signals.dataChanged.connect(lambda: self.cbSaved.setChecked(self.dm.ssSavedComports()))
        # self.dm.signals.dataChanged.connect(lambda: self.bSaveSettings.setEnabled(not self.dm.ssSavedComports()))
        self.dm.signals.dataChanged.connect(lambda: self.bSaveSettings.setEnabled(not self.dm.ssSavedComports() and self.dm.ht.haskey(self.dm.swim_settings())))
        # self.dm.signals.dataChanged.connect(lambda: self.cbSaved.setText(('Saved preferences (revert)', 'Saved preferences')[self.dm.ssSavedComports()]))

        self.dm.loadHashTable()

        self.dataUpdateMA()
        self.updateZarrRadiobuttons()

    # def _updateSaveButton(self):
    #     # Todo this would be faster as a dictionary lookup
    #     # self.bSaveSettings.setEnabled((not self.dm.ssSavedComports()) and os.path.exists(self.dm.dir_matches()))
    #     self.bSaveSettings.setEnabled(not self.dm.ssSavedComports())


    def updateAaButtons(self):
        logger.info('')
        # if self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['method_opts']['method'] == 'grid':
        alignment_ready = self.dm['level_data'][self.dm.scale]['alignment_ready']

        if alignment_ready:
            if self.twMethod.currentIndex() == 0:
                try:
                    # self.aaButtons[0].setEnabled(self.dm['defaults'][self.dm.level]['method_opts']['size_1x1'] !=
                    #                              self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings'][
                    #                                  'method_opts']['size_1x1'])
                    # self.aaButtons[1].setEnabled(self.dm['defaults'][self.dm.level]['method_opts']['size_2x2'] !=
                    #                              self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings'][
                    #                                  'method_opts']['size_2x2'])
                    # self.aaButtons[2].setEnabled(self.dm['defaults'][self.dm.level]['iterations'] !=
                    #                              self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings']['iterations'])
                    # self.aaButtons[3].setEnabled(self.dm['defaults'][self.dm.level]['whitening'] !=
                    #                              self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings'][
                    #                                  'whitening'])
                    # self.aaButtons[4].setEnabled((self.dm['defaults'][self.dm.level]['clobber'] !=
                    #                              self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings'][
                    #                                  'clobber']) or (self.dm['defaults'][self.dm.level]['clobber_size'] !=
                    #                                                  self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                    #                                                      'swim_settings']['clobber_size']))
                    # self.aaButtons[5].setEnabled(self.dm['defaults'][self.dm.level]['method_opts']['quadrants'] !=
                    #                              self.dm['stack'][self.dm.zpos]['levels'][self.dm.level]['swim_settings'][
                    #                                  'method_opts']['quadrants'])
                    self.aaButtons[0].setEnabled(self.dm['defaults'][self.dm.level]['method_opts']['size_1x1'] !=
                                                 self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                     'swim_settings'][
                                                     'method_opts']['size_1x1'])
                    self.aaButtons[1].setEnabled(self.dm['defaults'][self.dm.level]['method_opts']['size_2x2'] !=
                                                 self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                     'swim_settings'][
                                                     'method_opts']['size_2x2'])
                    self.aaButtons[2].setEnabled(self.dm['defaults'][self.dm.level]['iterations'] !=
                                                 self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                     'swim_settings']['iterations'])
                    self.aaButtons[3].setEnabled(self.dm['defaults'][self.dm.level]['whitening'] !=
                                                 self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                     'swim_settings'][
                                                     'whitening'])
                    self.aaButtons[4].setEnabled((self.dm['defaults'][self.dm.level]['clobber'] !=
                                                  self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                      'swim_settings'][
                                                      'clobber']) or (
                                                             self.dm['defaults'][self.dm.level]['clobber_size'] !=
                                                             self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                                 'swim_settings']['clobber_size']))
                    self.aaButtons[5].setEnabled(self.dm['defaults'][self.dm.level]['method_opts']['quadrants'] !=
                                                 self.dm['stack'][self.dm.zpos]['levels'][self.dm.level][
                                                     'swim_settings'][
                                                     'method_opts']['quadrants'])
                except:
                    print_exception()

    def load_data_from_treeview(self):
        self.datamodel = DataModel(self.treeview_model.to_json())
        self.dm = self.datamodel

    def initGif(self):
        self.gifPlayer = GifPlayer(dm=self.dm)
        # self.timerGif = QTimer(self)
        # self.timerGif.setInterval(500)
        # self.timerGif.setSingleShot(False)
        # self.timerGif.timeout.connect(self.gifPlayer.bBlink.click)


    def _onTabChange(self):
        logger.info('')
        # QApplication.restoreOverrideCursor()
        self.datamodel['state']['blink'] = False
        index = self.wTabs.currentIndex()
        self.dm['state']['current_tab'] = index
        # self.gifPlayer.stop()
        if index == 0:
            # self.parent.setdw_thumbs(True)
            # self.parent.setdw_matches(False)
            pass
        elif index == 1:
            # self.parent.setdw_thumbs(False) #BEFORE init neuroglancer
            # self.parent.setdw_matches(True) #BEFORE init neuroglancer
            self.cmbViewerScale.setCurrentIndex(self.dm.levels.index(self.dm.level))
            self.initNeuroglancer() #Todo necessary for now
            self.editorViewer.set_layer()
            self.set_transforming() #0802+
            self.update_match_list_widgets() #0726+
            self.gifPlayer.set()
            # if self.dm.is_aligned():
            #     self.gifPlayer.start()
        elif index == 2:
            self.snr_plot.initSnrPlot()
        elif index == 3:
            # self.project_table.data.selectRow(self.dm.zpos)
            self.project_table.initTableData()
        elif index == 4:
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()
        # self.parent.dataUpdateWidgets() #0805-


    # def _refresh(self, index=None):
    def refreshTab(self):
        logger.critical('\n\nRefreshing...\n')
        index = self.wTabs.currentIndex()
        self.datamodel['state']['blink'] = False
        # self.matchPlayTimer.stop()
        if index == 0:
            self.shutdownNeuroglancer()
            self.initNeuroglancer()
        elif index == 1:
            logger.critical('Refreshing editor tab...')
            self.shutdownNeuroglancer()
            self.initNeuroglancer()
            self.set_transforming()  # 0802+
            if self.parent.dwSnr.isVisible():
                if self.dm.is_aligned():
                    self.dSnr_plot.initSnrPlot()
                else:
                    self.dSnr_plot.wipePlot()

            self.gifPlayer.set()
            # if self.dm.is_aligned():
            #     self.gifPlayer.start()
        elif index == 2:
            self.snr_plot.initSnrPlot()
        elif index == 3:
            self.project_table.initTableData()
        elif index == 4:
            self.treeview.collapseAll()
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()
        self.parent.dataUpdateWidgets() #Todo might be redundant thumbail redraws
        # QApplication.processEvents() #1015-


    def shutdownNeuroglancer(self):
        logger.info('')
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if ng.is_server_running():
            ng.server.stop()
            # time.sleep(.5)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)

    def initNeuroglancer(self, init_all=False):
        caller = inspect.stack()[1].function

        if self.parent._working:
            logger.warning(f"[{caller}] UNABLE TO INITIALIZE NEUROGLANCER AT THIS TIME... BUSY WORKING!")
            return

        self.parent.set_status('Initializing Neuroglancer...')
        if DEV:
            logger.critical(f"[DEV][{caller_name()}] Initializing Neuroglancer...")

        if self.parent._isOpenProjTab():
            # self.parent.pm.updateCombos()
            self.parent.pm.viewer = cfg.pmViewer = PMViewer(webengine=self.parent.pm.webengine)
            if self.parent.pm.cmbSelectImages.count() > 0:
                self.parent.pm.viewer.initViewer()
        else:

            self.lNotAligned.setVisible(self.dm.is_aligned())

            if self.wTabs.currentIndex() == 1 or init_all:
                # self.MA_webengine_ref.setUrl(QUrl("http://localhost:8888/"))
                # self.editorWebengine.setUrl(QUrl("http://localhost:8888/"))
                # level = self.dm.levels[self.cmbViewerScale.currentIndex()]
                level = self.dm['state']['viewer_quality']
                self.editorViewer = cfg.editorViewer = MAViewer(parent=self, dm=self.dm, role='tra', quality=level, webengine=self.editorWebengine)
                self.editorViewer.signals.badStateChange.connect(self.set_transforming)
                self.editorViewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)  # 0314
                self.editorViewer.signals.ptsChanged.connect(self.update_match_list_widgets)
                # self.editorViewer.signals.ptsChanged.connect(self.updateWarnings)
                self.editorViewer.signals.zVoxelCoordChanged.connect(lambda zpos: setattr(self.dm, 'zpos', zpos))
                # self.editorViewer.signals.swimAction.connect(self.parent.alignOne)
                try:
                    self.dataUpdateMA()
                except:
                    print_exception()
                # logger.info(f"Local Volume:\n{self.editorViewer.LV.info()}")

            if self.wTabs.currentIndex() == 0 or init_all:
                # self.updateZarrRadiobuttons()
                self.updateNgLayoutCombox()

                path = (self.dm.path_zarr_transformed(), self.dm.path_zarr_raw())[self.rbZarrRaw.isChecked()]

                self.viewer = cfg.emViewer = EMViewer(parent=self, dm=self.dm, webengine=self.webengine, path=path)
                self.viewer.initZoom(self.webengine.width(), self.webengine.height())
                # self.viewer.signals.zoomChanged.connect(self.slotUpdateZoomSlider)  # 0314 #Todo
                self.viewer.signals.layoutChanged.connect(self.slot_layout_changed)
                self.viewer.signals.zoomChanged.connect(self.slot_zoom_changed)
                # logger.info(f"Local Volume:\n{cfg.LV.info()}")

        self.parent.hud.done()
        # self.setZmag(10)
        # QApplication.processEvents() #1009-

    def updateNgLayoutCombox(self):
        logger.info('')
        try:
            self.comboNgLayout.setCurrentText(getData('state,neuroglancer,layout'))
        except:
            print_exception()



    def slot_layout_changed(self):
        rev_mapping = {'yz':'xy', 'xy':'yz', 'xz':'xz', 'yz-3d':'xy-3d','xy-3d':'yz-3d',
                   'xz-3d':'xz-3d', '4panel': '4panel', '3d': '3d'}
        requested = rev_mapping[self.viewer.state.layout.type]
        if DEV:
            logger.info(f"Layout changed! requested: {requested}")
        setData('state,neuroglancer,layout', requested)
        self.comboNgLayout.setCurrentText(requested)
        # self.parent.tell(f'Neuroglancer Layout (set from native NG controls): {requested}')

    def slot_zoom_changed(self, val):
        caller = inspect.stack()[1].function
        # logger.info(f'[{caller}]')
        if val > 1000:
            val *= 250000000
        logger.info(f"Zoom changed! passed value: {val:.3f}")
        self.leZoom.setText("%.2f" % val)
        # setData('state,ng_zoom', self.viewer.state.cross_section_scale)
        # self.leZoom.setText(str(self.viewer.state.cross_section_scale))


    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')

        self._overlayLab = QLabel('<label>')
        # self._overlayLab.setMaximumHeight(20)
        self._overlayLab.setFocusPolicy(Qt.NoFocus)
        self._overlayLab.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayLab.setAlignment(Qt.AlignCenter)
        self._overlayLab.setStyleSheet("""color: #FF0000; font-size: 16px; font-weight: 600; background-color: rgba(0, 0, 0, 0.5); """)
        self._overlayLab.hide()

        # self.hud_overlay = HeadupDisplay(self.parent.app, overlay=True)
        # self.hud_overlay.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        # self.hud_overlay.set_theme_overlay()

        # self.joystick = Joystick()

        self.ngVertLab = VerticalLabel('Neuroglancer 3DEM View')
        self.detailsSNR = QLabel()
        self.detailsSNR.setWindowFlags(Qt.FramelessWindowHint)
        self.detailsSNR.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.detailsSNR.setMaximumHeight(100)
        self.detailsSNR.setWordWrap(True)
        self.detailsSNR.hide()

        self.zoomSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        self.zoomSlider.setFocusPolicy(Qt.NoFocus)
        self.zoomSlider.setMouseTracking(True)
        # self.zoomSlider.setInvertedAppearance(True)
        self.zoomSlider.setMaximum(4)
        self.zoomSlider.setMinimum(1)

        # self.zoomSlider.sliderMoved.connect(self.onZoomSlider) #Original #0314
        self.zoomSlider.valueChanged.connect(self.onZoomSlider)
        self.zoomSlider.setValue(4.0)

        vlab = VerticalLabel('Zoom:')

        self.zoomSliderAndLabel = VW()
        self.zoomSliderAndLabel.layout.setSpacing(0)
        self.zoomSliderAndLabel.setFocusPolicy(Qt.NoFocus)
        self.zoomSliderAndLabel.setFixedWidth(16)
        self.zoomSliderAndLabel.addWidget(self.zoomSlider)
        self.zoomSliderAndLabel.addWidget(vlab)

        # self.sliderZdisplay = DoubleSlider(Qt.Orientation.Vertical, self)
        # self.sliderZdisplay.setFocusPolicy(Qt.NoFocus)
        # self.sliderZdisplay.setMaximum(20)
        # self.sliderZdisplay.setMinimum(1)
        # self.sliderZdisplay.setValue(1.0)
        # self.sliderZdisplay.valueChanged.connect(self.onSliderZmag)
        #
        # self.wSliderZdisplay = VW()
        # self.wSliderZdisplay.layout.setSpacing(0)
        # self.wSliderZdisplay.setFixedWidth(16)
        # self.wSliderZdisplay.setMaximumHeight(100)
        # self.wSliderZdisplay.addWidget(self.sliderZdisplay)
        # self.wSliderZdisplay.addWidget(vlab)

        self.editorWebengine = WebEngine(ID='tra')
        # self.editorWebengine.setFocusPolicy(Qt.NoFocus) #1011-
        self.editorWebengine.setStyleSheet("background-color: #000000;")
        self.editorWebengine.page().setBackgroundColor(Qt.transparent) #0726+
        self.editorWebengine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # setWebengineProperties(self.editorWebengine)
        self.editorWebengine.setMouseTracking(True)
        # self.editorWebengine.setFocusPolicy(Qt.NoFocus) #0726-


        '''Mouse move events will occur only when a mouse bBlink is pressed down, 
        unless mouse tracking has been enabled with setMouseTracking() .'''

        # NO CHANGE----------------------
        # cfg.editorViewer.signals.ptsChanged.connect(self.update_MA_list_base)
        # cfg.editorViewer.shared_state.add_changed_callback(self.update_MA_ref_state)
        # NO CHANGE----------------------

        # MA Stage Buffer Widget

        self.lw_ref = ListWidget()
        # self.lw_ref.setFocusPolicy(Qt.NoFocus)
        delegate = ListItemDelegate()
        self.lw_ref.setItemDelegate(delegate)
        self.lw_ref.setFixedHeight(52)
        self.lw_ref.setIconSize(QSize(12,12))
        self.lw_ref.setStyleSheet("""
        QListWidget {
            font-size: 8px; 
            background-color: #ede9e8; 
            color: #161c20; 
            border: none;
        }
        QListView::item:selected {
            border: 1px solid #ffe135;
        }""")
        # palette = QPalette()
        # palette.setColor(QPalette.Highlight, self.lw_ref.palette().color(QPalette.Base))
        # palette.setColor(QPalette.HighlightedText, self.lw_ref.palette().color(QPalette.Text))
        # self.lw_ref.setPalette(palette)
        self.lw_ref.setSelectionMode(QListWidget.NoSelection)
        self.lw_ref.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lw_ref.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lw_ref.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lw_ref.installEventFilter(self)
        def fn_point_selected(item):
            # self.item = item
            requested = self.lw_ref.indexFromItem(item).row()
            self.editorViewer._selected_index['tra'] = requested
            self.editorViewer._selected_index['ref'] = requested
            print(f"[transforming] row selected: {requested}")
            self.update_match_list_widgets()
        self.lw_ref.itemClicked.connect(fn_point_selected)
        self.lab_ref = QLabel('Next Color:   ')
        self.lab_ref.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.lab_nextcolor1 = QLabel()
        self.lab_nextcolor1.setFixedSize(14, 14)


        self.lw_tra = ListWidget()
        # self.lw_tra.setFocusPolicy(Qt.NoFocus)
        delegate = ListItemDelegate()
        self.lw_tra.setItemDelegate(delegate)
        self.lw_tra.setFixedHeight(52)
        self.lw_tra.setIconSize(QSize(12, 12))
        self.lw_tra.setStyleSheet("""
        QListWidget {
            font-size: 8px; 
            background-color: #ede9e8; 
            color: #161c20; 
            border: none;
        }
        QListView::item:selected {
            border: 1px solid #6a6ea9;
        }""")
        # palette = QPalette()
        # palette.setColor(QPalette.Highlight, self.lw_ref.palette().color(QPalette.Base))
        # palette.setColor(QPalette.HighlightedText, self.lw_ref.palette().color(QPalette.Text))
        self.lw_tra.setSelectionMode(QListWidget.NoSelection)
        # self.lw_tra.setSelectionMode(QListWidget.ExtendedSelection)
        self.lw_tra.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lw_tra.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.lw_tra.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lw_tra.installEventFilter(self)
        def fn_point_selected(item):
            # self.item = item
            requested = self.lw_tra.indexFromItem(item).row()
            self.editorViewer._selected_index['tra'] = requested
            self.editorViewer._selected_index['ref'] = requested
            print(f"[transforming] row selected: {requested}")
            self.update_match_list_widgets()
        self.lw_tra.itemClicked.connect(fn_point_selected)
        self.lab_tra = QLabel('Next Color:   ')
        self.lab_tra.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #161c20;')
        self.lab_nextcolor0 = QLabel()
        self.lab_nextcolor0.setFixedSize(14, 14)




        font = QFont()
        font.setBold(True)


        for i in list(range(0,3)):
            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 16))
            item.setBackground(QColor(cfg.glob_colors[i]))
            item.setForeground(QColor('#141414'))
            item.setFont(font)
            # item.setCheckState(2)
            self.lw_tra.addItem(item)

            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 16))
            item.setBackground(QColor(cfg.glob_colors[i]))
            item.setForeground(QColor('#141414'))
            item.setFont(font)
            # item.setCheckState(2)
            self.lw_ref.addItem(item)


        self.lw_ref.itemSelectionChanged.connect(self.lw_tra.selectionModel().clear)
        self.lw_tra.itemSelectionChanged.connect(self.lw_ref.selectionModel().clear)

        self.btn_undoRefPts = QPushButton()
        self.btn_undoRefPts.setFixedSize(QSize(14, 14))
        self.btn_undoRefPts.setIconSize(QSize(13, 13))
        self.btn_undoRefPts.setToolTip('Undo Last Selection')
        self.btn_undoRefPts.setIcon(qta.icon('fa.undo', color='#161c20'))
        def fn():
            self.editorViewer.pts['ref'][self.editorViewer._selected_index['ref']] = None
            self.editorViewer._selected_index['ref'] = self.editorViewer.getNextPoint('ref')
            # self.editorViewer.restoreManAlignPts()
            # self.editorViewer.setMpData()
            self.editorViewer.drawSWIMwindow()
            self.update_match_list_widgets()
        self.btn_undoRefPts.clicked.connect(fn)

        self.btn_clrRefPts = QPushButton('Clear')
        self.btn_clrRefPts.setToolTip('Clear All Selections')
        self.btn_clrRefPts.setStyleSheet("""font-size: 9px;""")
        self.btn_clrRefPts.setFixedSize(QSize(36, 14))
        self.btn_clrRefPts.clicked.connect(self.deleteAllMpRef)

        self.btn_undoBasePts = QPushButton()
        self.btn_undoBasePts.setFixedSize(QSize(14, 14))
        self.btn_undoBasePts.setIconSize(QSize(13, 13))
        self.btn_undoBasePts.setToolTip('Undo Last Selection')
        self.btn_undoBasePts.setIcon(qta.icon('fa.undo', color='#161c20'))
        def fn():
            self.editorViewer.pts['tra'][self.editorViewer._selected_index['tra']] = None
            self.editorViewer._selected_index['tra'] = self.editorViewer.getNextPoint('tra')
            # self.editorViewer.restoreManAlignPts()
            # self.editorViewer.setMpData()
            self.editorViewer.drawSWIMwindow()
            self.update_match_list_widgets()
        self.btn_undoBasePts.clicked.connect(fn)

        self.btn_clrBasePts = QPushButton('Clear')
        self.btn_clrBasePts.setToolTip('Clear All Selections')
        self.btn_clrBasePts.setStyleSheet("""font-size: 9px;""")
        self.btn_clrBasePts.setFixedSize(QSize(36, 14))
        self.btn_clrBasePts.clicked.connect(self.deleteAllMpBase)

        self.btn_clrAllPts = QPushButton('Clear All')
        self.btn_clrAllPts.setToolTip('Clear All Selections')
        self.btn_clrAllPts.setStyleSheet("""font-size: 9px; margin-right: 2px;""")
        self.btn_clrAllPts.setFixedSize(QSize(48, 14))
        self.btn_clrAllPts.clicked.connect(self.deleteAllMp)

        self.baseNextColorWidget = HW(self.lab_tra, self.lab_nextcolor0,
                                      ExpandingWidget(self), self.btn_clrBasePts)
        self.baseNextColorWidget.setFixedHeight(16)
        self.refNextColorWidget = HW(self.lab_ref, self.lab_nextcolor1,
                                     ExpandingWidget(self), self.btn_clrRefPts)
        self.refNextColorWidget.setFixedHeight(16)

        self.automatic_label = QLabel()
        self.automatic_label.setStyleSheet('color: #06470c; font-size: 11px; font-weight: 600;')

        lab = QLabel('Saved Method:')
        lab.setStyleSheet('font-size: 8px;')
        vw = VW(lab, self.automatic_label)
        vw.layout.setSpacing(0)

        self.bSaveSettings = QPushButton('Save')
        self.bSaveSettings.setFocusPolicy(Qt.NoFocus)
        self.bSaveSettings.setFixedHeight(16)
        def fn_bSaveSettings():
            logger.info('')
            self.dm.saveSettings()
            self.parent._autosave(silently=True)  # Critical, as the key will be assumed to exist
            # self.dataUpdateMA()
            if self.parent.dwSnr.isVisible():
                self.dSnr_plot.initSnrPlot()
            self.parent.dataUpdateWidgets()

        self.bSaveSettings.clicked.connect(fn_bSaveSettings)
        tip = "Todo: add tool tip"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bSaveSettings.setToolTip(tip)

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

        self.bPull = QPushButton('Pull Settings From Coarser Resolution')
        self.bPull.setFocusPolicy(Qt.NoFocus)
        self.bPull.setFixedHeight(16)
        self.bPull.clicked.connect(self.dm.pullSettings)
        self.bPull.clicked.connect(self.dataUpdateMA)
        # msg = "Re-pull (propagate) preferences from previous scale level."
        tip = "Pull (re-propagate) all SWIM preferences from the next coarsest resolution level."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bPull.setToolTip(tip)

        # self.combo_MA_actions = QComboBox(self)
        # self.combo_MA_actions.setStyleSheet('font-size: 10px')
        # self.combo_MA_actions.setFixedHeight(20)
        # self.combo_MA_actions.setFocusPolicy(Qt.NoFocus)
        # items = ['Set All Auto-SWIM']
        # self.combo_MA_actions.addItems(items)
        # self.combo_MA_actions.currentTextChanged.connect(fn)
        # btn_go = QPushButton()
        # btn_go.clicked.connect(self.onMAaction)
        #
        # self.MA_actions = HW(self.combo_MA_actions, btn_go)


        # tip = "Perform a quick SWIM alignment to show match signals and SNR values, " \
        #       "but do not generate any new images"
        tip = "Perform a SWIM alignment + generate the resulting aligned image"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bSWIM = QPushButton('Align (Affine, Match Signals, SNR)')
        self.bSWIM = QPushButton('Align')
        # self.bSWIM.setStyleSheet("font-size: 10px; background-color: #9fdf9f;")
        self.bSWIM.setToolTip(tip)
        self.bSWIM.setFixedHeight(16)
        self.bSWIM.setFocusPolicy(Qt.NoFocus)
        self.bSWIM.clicked.connect(lambda: self.bSWIM.setEnabled(False))
        self.bSWIM.clicked.connect(lambda: self.bTransform.setEnabled(False))
        # self.bSWIM.clicked.connect(lambda: self.parent.alignOne(dm=self.dm, regenerate=False))
        self.bSWIM.clicked.connect(lambda: self.parent.alignOne(dm=self.dm, regenerate=True))
        # self.bSWIM.clicked.connect(lambda: self.parent.setdw_matches(True))

        tip = "Apply the affine transformation from SWIM to the images."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.bTransform = QPushButton('Transform (Generates Images)')
        # self.bTransform.setStyleSheet("font-size: 10px; background-color: #9fdf9f;")
        self.bTransform.setToolTip(tip)
        self.bTransform.setFixedHeight(16)
        self.bTransform.setFocusPolicy(Qt.NoFocus)
        self.bTransform.clicked.connect(lambda: self.bSWIM.setEnabled(False))
        self.bTransform.clicked.connect(lambda: self.bTransform.setEnabled(False))
        self.bTransform.clicked.connect(lambda: self.parent.alignOne(dm=self.dm, regenerate=True, align=False))
        self.bTransform.hide()

        self.lw_gb_l = GroupBox("Transforming")
        def fn():
            logger.info('')
            if self.dm['state']['tra_ref_toggle'] == 'ref':
                self.set_transforming()
        self.lw_gb_l.clicked.connect(fn)
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.lw_tra)
        vbl.addWidget(self.baseNextColorWidget)
        self.lw_gb_l.setLayout(vbl)

        # self.lw_gb_r = GroupBox("Reference")
        self.lw_gb_r = GroupBox("Reference")
        def fn():
            logger.info('')
            if self.dm['state']['tra_ref_toggle'] == 'tra':
                self.set_reference()
        self.lw_gb_r.clicked.connect(fn)
        vbl = VBL()
        vbl.setSpacing(1)
        vbl.addWidget(self.lw_ref)
        vbl.addWidget(self.refNextColorWidget)
        self.lw_gb_r.setLayout(vbl)
        self.labSlash = QLabel('←/→')
        self.labSlash.setStyleSheet("""font-size: 10px; font-weight: 600;""")
        self.MA_sbw = HW(self.lw_gb_l, self.labSlash, self.lw_gb_r)
        self.MA_sbw.layout.setSpacing(0)
        # self.msg_MAinstruct = YellowTextLabel("⇧ + Click - Select 3 corresponding points")
        # self.msg_MAinstruct.setFixedSize(266, 20)

        self.gb_stageInfoText = QGroupBox()
        vbl = VBL()
        vbl.setSpacing(0)
        self.gb_stageInfoText.setLayout(vbl)

        self.bMove = QPushButton('Move')
        self.bMove.setStyleSheet("""font-size: 10px;""")
        self.bMove.setFixedSize(QSize(38, 18))
        self.bMove.setFocusPolicy(Qt.NoFocus)
        self.bMove.clicked.connect(self.onTranslate)

        self.leTranslateX = QLineEdit()
        self.leTranslateX.returnPressed.connect(self.onTranslate_x)
        # self.leTranslateX.setFixedSize(QSize(36, 16))
        self.leTranslateX.setFixedSize(QSize(36,16))
        self.leTranslateX.setValidator(QIntValidator())
        self.leTranslateX.setText('0')
        self.leTranslateX.setAlignment(Qt.AlignCenter)

        self.leTranslateY = QLineEdit()
        self.leTranslateY.returnPressed.connect(self.onTranslate_y)
        # self.leTranslateY.setFixedSize(QSize(36, 16))
        self.leTranslateY.setFixedSize(QSize(36, 16))
        self.leTranslateY.setValidator(QIntValidator())
        self.leTranslateY.setText('0')
        self.leTranslateY.setAlignment(Qt.AlignCenter)

        self.translatePointsWidget = HW(
            # QLabel('Translation:'),
            ExpandingWidget(self),
            QLabel('up:'),
            self.leTranslateY,
            ExpandingWidget(self),
            QLabel('right:'),
            self.leTranslateX,
            self.bMove
        )
        self.translatePointsWidget.layout.setSpacing(6)
        self.translatePointsWidget.layout.setAlignment(Qt.AlignRight)

        """  MA Settings Tab  """

        tip = "Window width for manual alignment (px)"
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_sliderMatch():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info('')
                val = int(self.sliderMatch.value())
                if (val % 2) == 1:
                    self.sliderMatch.setValue(val - 1)
                    return

                self.dm.set_manual_swim_window_px(val)
                self.leMatch.setText(str(self.dm.manual_swim_window_px()))
                self.editorViewer.drawSWIMwindow()

                if self.tn_widget.isVisible():
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
            caller = inspect.stack()[1].function
            logger.info('caller: %s' % caller)
            # logger.info(f'manua lswim window value {int(self.leMatch.text())}')
            val = int(self.leMatch.text())
            if (val % 2) == 1:
                self.sliderMatch.setValue(val - 1)
                return
            self.dm.set_manual_swim_window_px(val)
            self.dataUpdateMA()
            self.editorViewer.drawSWIMwindow()
            if self.tn_widget.isVisible():
                self.tn_ref.update()
                self.tn_tra.update()
            self.sliderMatch.setValue(int(self.leMatch.text()))
        self.leMatch.returnPressed.connect(fn_leMatch)

        tip = "Full window width for automatic alignment (px)"
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_slider1x1():
            caller = inspect.stack()[1].function
            if caller in ('main','fn_le1x1'):
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
                self.editorViewer.drawSWIMwindow()
                if self.tn_widget.isVisible():
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
            caller = inspect.stack()[1].function
            if caller in ('main','fn_le2x2'):
                logger.info('')
                val = int(self.slider2x2.value())
                self.dm.set_size2x2(val)
                self.le2x2.setText(str(self.dm.size2x2()[0]))
                self.slider2x2.setValue(int(self.dm.size2x2()[0]))
                self.editorViewer.drawSWIMwindow()
                if self.tn_widget.isVisible():
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
            caller = inspect.stack()[1].function
            if caller == 'main':
                # if self.rb_MA_hint.isChecked():
                #     self.dm.current_method = 'manual_hint'
                # elif self.rb_MA_strict.isChecked():
                #     self.dm.current_method = 'manual_strict'
                self.editorViewer.drawSWIMwindow()
                if self.tn_widget.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                self.parent.setSignalsPixmaps()
                self.parent.setTargKargPixmaps()
                if self.parent.dwSnr.isVisible():
                    self.dSnr_plot.initSnrPlot()
                self.parent.statusBar.showMessage(f'Manual alignment option now set to: {self.dm.current_method}')

        # self.rb_MA_hint = QRadioButton('Hint')
        # self.rb_MA_strict = QRadioButton('Strict')
        self.rb_MA_hint = QRadioButton('Match Regions')
        self.rb_MA_strict = QRadioButton('Match Points')
        self.rb_MA_strict.setEnabled(False)
        self.MA_bg = QButtonGroup(self)
        self.MA_bg.setExclusive(True)
        self.MA_bg.addButton(self.rb_MA_hint)
        self.MA_bg.addButton(self.rb_MA_strict)
        self.MA_bg.buttonClicked.connect(fn)
        self.radioboxes_MA = HW(self.rb_MA_hint, self.rb_MA_strict)

        self.pxLab = QLabel('px')

        self.wwWidget = HW(self.sliderMatch, self.leMatch, self.pxLab)
        self.wwWidget.layout.setSpacing(4)

        self.flManualAlign = QFormLayout()
        self.flManualAlign.setContentsMargins(0,0,0,0)
        self.flManualAlign.addRow("Method:", self.radioboxes_MA)
        self.flManualAlign.addRow("Move Selection:", self.translatePointsWidget)
        self.flManualAlign.addRow("Window Width:", self.wwWidget)

        self.gbMatch = QGroupBox()
        # self.gbMatch.setFixedHeight(76)
        self.gbMatch.setLayout(self.flManualAlign)

        ##############

        self.w1x1 = HW(self.le1x1, self.slider1x1)
        self.w1x1.layout.setSpacing(4)
        # self.w1x1.layout.setAlignment(Qt.AlignLeft)
        self.w2x2 = HW(self.le2x2, self.slider2x2)
        self.w2x2.layout.setSpacing(4)
        # self.w2x2.layout.setAlignment(Qt.AlignLeft)

        self.Q1 = ClickRegion(self, color=cfg.glob_colors[0], name='Q1')
        self.Q2 = ClickRegion(self, color=cfg.glob_colors[1], name='Q2')
        self.Q3 = ClickRegion(self, color=cfg.glob_colors[2], name='Q3')  # correct
        self.Q4 = ClickRegion(self, color=cfg.glob_colors[3], name='Q4')  # correct

        self.Q1.clicked.connect(self.updateAutoSwimRegions)
        self.Q2.clicked.connect(self.updateAutoSwimRegions)
        self.Q3.clicked.connect(self.updateAutoSwimRegions)
        self.Q4.clicked.connect(self.updateAutoSwimRegions)

        self.gl_Q = QGridLayout()
        self.gl_Q.setContentsMargins(0,0,0,0)
        self.gl_Q.setSpacing(1)
        self.gl_Q.addWidget(self.Q1, 0, 0, 1, 1)
        self.gl_Q.addWidget(self.Q2, 0, 1, 1, 1)
        # self.gl_Q.addWidget(self.Q3, 0, 2, 1, 1)
        # self.gl_Q.addWidget(self.Q4, 0, 3, 1, 1)
        self.gl_Q.addWidget(self.Q3, 1, 0, 1, 1)
        self.gl_Q.addWidget(self.Q4, 1, 1, 1, 1)
        # self.Q_widget = HW(self.Q1, self.Q2, self.Q3, self.Q4)
        self.Q_widget = QWidget()
        self.Q_widget.setFixedSize(QSize(50,50))
        self.Q_widget.setLayout(self.gl_Q)

        '''
        DEFAULT GRID SWIM SETTINGS
        '''

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
            # caller = inspect.stack()[1].function
            # if caller == 'main':
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
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info(f'caller: {caller}')
                val = int(self.leSwimWindow.text())
                logger.info(f"val = {val}")
                if (val % 2) == 1:
                    new_val = val - 1
                    self.parent.tell(f'SWIM requires even values as input. Setting value to {new_val}')
                    self.leSwimWindow.setText(str(new_val))
                    return
                # self.dm.set_auto_swim_windows_to_default(factor=float(self.leSwimWindow.text()) / self.dm.image_size()[0])
                # self.dm.set_auto_swim_windows_to_default(factor=val / self.dm.image_size()[0]) #0907-
                # self.swimWindowChanged.emit()

                if self.wTabs.currentIndex() == 1:
                    self.editorViewer.drawSWIMwindow()
                if self.tn_widget.isVisible():
                    self.tn_ref.update()
                    self.tn_tra.update()
                self.parent.tell(f'SWIM Window set to: {str(val)}')
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
        self.cbDefaults.toggled.connect(self.onDefaultsCheckbox)
        self.cbDefaults.setFixedHeight(14)

        self.cbSaved = QCheckBox('Saved preferences')
        self.cbSaved.setFixedHeight(14)
        def fn_cbSaved():
            logger.info('')
            caller = inspect.stack()[1].function
            if caller == 'main':
                if self.cbSaved.isChecked():
                    logger.info('Updating displayed data to match saved SWIM preferences...')
                    # ss = self.dm.swim_settings()
                    self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['swim_settings'].update(
                        copy.deepcopy(self.dm.saved_swim_settings()))
                else:
                    self.cbSaved.setChecked(self.dm.ssHash() == self.dm.ssSavedHash())
                self.dataUpdateMA()

        self.cbSaved.toggled.connect(fn_cbSaved)



        self.flGrid = QFormLayout()
        self.flGrid.setHorizontalSpacing(4)
        self.flGrid.setLabelAlignment(Qt.AlignRight)
        self.flGrid.setFormAlignment(Qt.AlignCenter)
        self.flGrid.setContentsMargins(2, 2, 2, 2)
        self.flGrid.setSpacing(2)

        self.aaWidgets = []
        self.aaButtons = []
        for w in range(6):
            b = QPushButton('Apply All')
            b.setFixedSize(42, 15)
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
            b.clicked.connect(self.dataUpdateMA)

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

        # tip = """Similar to the Default Grid method, but the user is able to avoid image defects
        # by adjusting the grid shape and images_location and adding or removing quadrants of the grid.
        # An affine transformation requires at least 3 regions (quadrants)."""

        tip = """User provides an alignment hint for SWIM by selecting 3 matching regions (manual correspondence). 
           Note: An affine transformation requires at least 3 correspondence regions."""
        tip = '\n'.join(textwrap.wrap(tip, width=35))

        def fn_method_select():
            caller = inspect.stack()[1].function
            if caller == 'main':
                logger.info('')
                l = self.dm.zpos
                s = self.dm.scale
                cur_tab = self.twMethod.currentIndex()
                if cur_tab == 0:
                    # self.swMethod.setCurrentIndex(0)
                    # mo = self.dm['level_data'][s]['method_presets']['grid']
                    mo = self.dm['defaults'][s]['method_opts']
                    self.dm['stack'][l]['levels'][s]['swim_settings']['method_opts'] = copy.deepcopy(mo)
                elif cur_tab == 1:
                    # self.swMethod.setCurrentIndex(1)
                    mo = self.dm['level_data'][s]['method_presets']['manual']
                    self.dm['stack'][l]['levels'][s]['swim_settings']['method_opts'] = copy.deepcopy(mo)
                    #Todo
                    if self.dm.current_method == 'manual_strict':
                        self.rb_MA_strict.setChecked(True)
                    else:
                        self.rb_MA_hint.setChecked(True)
                self.parent.dataUpdateWidgets()

        self.gbGrid = QGroupBox("Grid Alignment Settings")
        self.gbGrid.setMaximumHeight(258)
        self.gbGrid.setLayout(self.flGrid)
        # self.gbGrid.setAlignment(Qt.AlignBottom)
        self.gbGrid.setAlignment(Qt.AlignCenter)

        self.MA_use_global_defaults_lab = QLabel('Global defaults will be used.')
        self.MA_use_global_defaults_lab.setStyleSheet('font-size: 13px; font-weight: 600;')
        self.MA_use_global_defaults_lab.setAlignment(Qt.AlignCenter)

        self.lab_region_selection = QLabel("Alt + click to select 3 matching regions")
        # self.lab_region_selection = QLabel("")
        self.lab_region_selection.setStyleSheet("font-size: 10px; font-weight: 600; color: #161c20; padding: 1px;")

        self.rbCycle = QRadioButton('cycle')
        self.rbCycle.setObjectName('cycle')
        self.rbCycle.setFocusPolicy(Qt.NoFocus)

        self.rbZigzag = QRadioButton('zigzag')
        self.rbZigzag.setObjectName('zigzag')
        self.rbZigzag.setFocusPolicy(Qt.NoFocus)

        self.rbSticky = QRadioButton('sticky')
        self.rbSticky.setObjectName('sticky')
        self.rbSticky.setFocusPolicy(Qt.NoFocus)

        d = {'cycle': self.rbCycle,
             'zigzag': self.rbZigzag,
             'sticky': self.rbSticky}

        bg = QButtonGroup(self)
        bg.setExclusive(True)
        def fn():
            for b in bg.buttons():
                if b.isChecked():
                    self.dm['state']['neuroglancer']['region_selection']['select_by'] = b.objectName()
                    return
        bg.buttonClicked.connect(fn)
        bg.addButton(self.rbCycle)
        bg.addButton(self.rbZigzag)
        bg.addButton(self.rbSticky)
        self.rbCycle.setChecked(True) #Todo

        self.w_rbs_selection = HW(ExpandingWidget(self), self.rbCycle, self.rbZigzag, self.rbSticky,
                                  self.btn_clrAllPts)

        # self.lab_region_selection2 = QLabel("Note: At least 3 are necessary to for affine.")
        # self.lab_region_selection2 = QLabel("")
        # self.lab_region_selection2.setStyleSheet("font-size: 9px; color: #161c20; padding: 1px;")
        self.gbMethodMatch = VW(
            self.lab_region_selection,
            self.MA_sbw,
            self.w_rbs_selection,
            # self.lab_region_selection2,
            self.gbMatch,
        )
        # self.gbMethodMatch.setMaximumHeight(210)
        # self.gbMethodMatch.setMinimumHeight(180)


        def bottom():
            self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())

        def top():
            self.te_logs.verticalScrollBar().setValue(0)

        self.logs_top_btn = QPushButton('Top')
        self.logs_top_btn.setFixedSize(QSize(40, 18))
        self.logs_top_btn.clicked.connect(top)

        self.logs_bottom_btn = QPushButton('Bottom')
        self.logs_bottom_btn.setFixedSize(QSize(40, 18))
        self.logs_bottom_btn.clicked.connect(bottom)

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

            self.te_logs.setText('No Log To Show.')

        self.logs_refresh_btn = QPushButton('Refresh')
        self.logs_refresh_btn.setFixedSize(QSize(64, 18))
        self.logs_refresh_btn.clicked.connect(self.refreshLogs)

        self.logs_delete_all_btn = QPushButton('Delete Logs')
        self.logs_delete_all_btn.setFixedSize(QSize(64, 18))
        self.logs_delete_all_btn.clicked.connect(fn)

        self.te_logs = QTextEdit()
        self.te_logs.setReadOnly(True)
        self.te_logs.setText('Logs...')

        self.lab_logs = BoldLabel('Logs:')

        self.rb_logs_swim_args = QRadioButton('SWIM Args')
        self.rb_logs_swim_args.setChecked(True)
        self.rb_logs_swim_out = QRadioButton('SWIM Out')
        self.rb_logs_mir_args = QRadioButton('MIR')
        self.rb_logs = QButtonGroup(self)
        self.rb_logs.setExclusive(True)
        self.rb_logs.addButton(self.rb_logs_swim_args)
        self.rb_logs.addButton(self.rb_logs_swim_out)
        self.rb_logs.addButton(self.rb_logs_mir_args)

        # self.btns_logs = QWidget()

        self.lab_ing = QLabel('Ingredients:')

        self.btn_ing0 = QPushButton('1')

        def fn():
            key = 'swim_args'
            if self.rb_logs_swim_args.isChecked():
                key = 'swim_args'
            elif self.rb_logs_swim_out.isChecked():
                key = 'swim_out'
            elif self.rb_logs_mir_args.isChecked():
                key = 'mir_args'
            args = '\n'.join(self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['results'][key][
                                 'ingredient_0']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.te_logs.setText(' '.join(args))

        self.btn_ing0.clicked.connect(fn)

        self.btn_ing1 = QPushButton('2')

        def fn():
            key = 'swim_args'
            if self.rb_logs_swim_args.isChecked():
                key = 'swim_args'
            elif self.rb_logs_swim_out.isChecked():
                key = 'swim_out'
            elif self.rb_logs_mir_args.isChecked():
                key = 'mir_args'
            args = '\n'.join(self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['results'][key][
                                 'ingredient_1']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.te_logs.setText(' '.join(args))

        self.btn_ing1.clicked.connect(fn)

        self.btn_ing2 = QPushButton('3')

        def fn():
            key = 'swim_args'
            if self.rb_logs_swim_args.isChecked():
                key = 'swim_args'
            elif self.rb_logs_swim_out.isChecked():
                key = 'swim_out'
            elif self.rb_logs_mir_args.isChecked():
                key = 'mir_args'
            args = '\n'.join(self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['results'][key][
'ingredient_2']).split(' ')
            for i, x in enumerate(args):
                if x and x[0] == '/':
                    args[i] = os.path.basename(x)
            self.te_logs.setText(' '.join(args))

        self.btn_ing2.clicked.connect(fn)
        self.btn_ing0.setFixedSize(QSize(40, 18))
        self.btn_ing1.setFixedSize(QSize(40, 18))
        self.btn_ing2.setFixedSize(QSize(40, 18))
        self.w_ingredients = HW(self.lab_ing, ExpandingWidget(self), self.btn_ing0, self.btn_ing1, self.btn_ing2)

        self.logs_widget = VW(
            HW(self.lab_logs, ExpandingWidget(self), self.rb_logs_swim_args, self.rb_logs_swim_out),
            self.te_logs,
            self.w_ingredients,
            HW(ExpandingWidget(self),
               self.logs_refresh_btn,
               self.logs_delete_all_btn,
               self.logs_top_btn,
               self.logs_bottom_btn
               ),
        )
        self.logs_widget.layout.setContentsMargins(2,2,2,2)
        self.logs_widget.layout.setSpacing(2)

        self.saGrid = QScrollArea()
        self.saGrid.setWidgetResizable(True)
        self.saGrid.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.saGrid.setWidget(self.gbGrid)

        self.saManual = QScrollArea()
        self.saManual.setWidgetResizable(True)
        self.saManual.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.saManual.setWidget(self.gbMethodMatch)

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
        self.twMethod.setTabShape(QTabWidget.Triangular)
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
        self.swMethod.addWidget(self.twMethod)
        self.swMethod.addWidget(self.wPlaceholder)

        # self.labViewerScale = QLabel('Viewer Resolution:')
        self.cmbViewerScale = QComboBox()
        lst = []
        lst.append('Full Quality %d x %dpx' % (self.dm.image_size(s=self.dm.levels[0])))
        for level in self.dm.levels[1:]:
            # lvl = self.dm.lvl(s=level)
            # siz = self.dm.image_size(s=level)
            # lst.append('%d / %d x %dpx' % (lvl, siz[0], siz[1]))
            # lst.append('%d x %dpx' % (siz[0], siz[1]))
            siz = self.dm.image_size(s=level)
            lst.append('1/%d Quality %d x %dpx' % (self.dm.lvl(level), siz[0], siz[1]))
        self.cmbViewerScale.addItems(lst)

        self.cmbViewerScale.setCurrentIndex(self.dm.levels.index(self.dm['state']['viewer_quality']))

        def fn_cmbViewerScale():
            caller = inspect.stack()[1].function
            logger.info(f"[{caller}]")
            if caller == 'main':
                level = self.dm.levels[self.cmbViewerScale.currentIndex()]
                siz = self.dm.image_size(s=level)
                self.dm['state']['viewer_quality'] = level
                self.parent.tell('Viewing quality set to 1/%d (%d x %dpx)' % (self.dm.lvl(level), siz[0], siz[1]))
                self.initNeuroglancer()

        self.cmbViewerScale.currentIndexChanged.connect(fn_cmbViewerScale)

        # self.wCmbViewerScale = HW(self.cmbViewerScale)
        # self.wCmbViewerScale.layout.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        self.cl_tra = ClickLabel(' Transforming ')
        self.cl_tra.setFocusPolicy(Qt.NoFocus)
        self.cl_tra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cl_tra.setMinimumWidth(128)
        self.cl_tra.setAlignment(Qt.AlignLeft)
        self.cl_tra.setFixedHeight(16)
        self.cl_tra.clicked.connect(self.set_transforming)

        self.cl_ref = ClickLabel(' Reference ')
        self.cl_ref.setFocusPolicy(Qt.NoFocus)
        self.cl_ref.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cl_ref.setMinimumWidth(128)
        self.cl_ref.setAlignment(Qt.AlignRight)
        self.cl_ref.setFixedHeight(16)
        self.cl_ref.clicked.connect(self.set_reference)

        self.cl_tra.setStyleSheet('background-color: #339933; color: #f3f6fb; font-size: 10px; font-weight: 600; border: none;')
        self.cl_ref.setStyleSheet('background-color: #222222; color: #f3f6fb; font-size: 10px; font-weight: 600; border-width: 4px;')

        self.wSwitchRefTra = QWidget()
        self.wSwitchRefTra.setFixedHeight(16)
        # self.wSwitchRefTra.setStyleSheet("background-color: #222222;")
        self.wSwitchRefTra.setFocusPolicy(Qt.NoFocus)
        self.labAlignTo = QLabel(f"Aligns To ⇒")
        self.labAlignTo.setToolTip("'/' (slash) key to toggle")
        self.labAlignTo.setFixedWidth(80)
        self.labAlignTo.setAlignment(Qt.AlignHCenter)
        self.labAlignTo.setStyleSheet('background-color: #ede9e8; color: #161c20; font-size: 11px; font-weight: 600; '
                                      'border-radius: 2px; padding-left: 1px; padding-right: 1px;')

        # self.wSwitchRefTra = HW(self.cl_tra, self.labAlignTo, self.cl_ref)
        self.wSwitchRefTra = HW(self.cl_tra, self.cmbViewerScale, self.cl_ref)
        self.wSwitchRefTra.setFixedHeight(15)

        # https://codeloop.org/pyqt5-make-multi-document-interface-mdi-application/


        # '''THIS WORKS'''
        # self.mdi = QMdiArea()
        # self.sub_webengine = QMdiSubWindow()
        # self.sub_webengine.setWidget(self.webengine)
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

        # self.gl_sw_main = QGridLayout()
        # self.gl_sw_main.setSpacing(0)
        # self.gl_sw_main.setContentsMargins(0, 0, 0, 0)
        # self.gl_sw_main.addWidget(self.editorWebengine, 0, 0, 3, 3)
        # self.gl_sw_main.addWidget(self._overlayLab, 0, 0, 3, 3)


        self.wNeuroglancer = QWidget()
        self.glNeuroglancer = GL()
        self.glNeuroglancer.addWidget(self.editorWebengine, 0, 0, 3, 3)
        # self.glNeuroglancer.addWidget(self.wCmbViewerScale, 0, 1, 1, 1)
        # self.glNeuroglancer.addWidget(self.cmbViewerScale, 0, 1, 1, 1)

        self.wNeuroglancer.setLayout(self.glNeuroglancer)

        # self.ng_widget = VW(self.wSwitchRefTra, self.editorWebengine)
        self.ng_widget = VW(self.wSwitchRefTra, self.wNeuroglancer)

        ngFont = QFont('Tahoma')
        ngFont.setBold(True)
        pal = QPalette()
        pal.setColor(QPalette.Text, QColor("#FFFF66"))

        self.comboNgLayout = QComboBox(self)
        self.comboNgLayout.setFixedWidth(84)
        self.comboNgLayout.setFixedHeight(15)
        self.comboNgLayout.setFocusPolicy(Qt.NoFocus)
        items = ['4panel', 'xy', 'yz', 'xz', 'xy-3d', 'yz-3d', 'xz-3d']
        self.comboNgLayout.addItems(items)
        self.comboNgLayout.activated.connect(self.onNgLayoutCombobox)
        self.comboNgLayout.setCurrentText(getData('state,neuroglancer,layout'))

        self.lab_filename = QLabel('Filename')
        self.lab_filename.setStyleSheet("""background-color: #222222; color: #ede9e8; font-weight: 600; font-size: 10px;""")

        self.hwEditorTitle = HW(self.lab_filename)
        self.hwEditorTitle.setFixedHeight(16)
        # self.hwEditorTitle.setStyleSheet("""background-color: #222222; color: #ede9e8; font-weight: 600; font-size: 10px;""")

        logger.info("Setting NG extended toolbar...")

        self.labNgLayout = QLabel('Layout: ')
        self.labNgLayout.setStyleSheet("""color: #ede9e8; font-weight: 600; font-size: 10px;""")

        def fn():
            self.setUpdatesEnabled(False)
            if not self.bShader.isChecked():
                self.bShader.setToolTip('Show Brightness & Contrast Shaders')
            else:
                self.contrastSlider.setValue(int(self.dm.contrast))
                self.contrastLE.setText('%d' % self.dm.contrast)
                self.brightnessSlider.setValue(int(self.dm.brightness))
                self.brightnessLE.setText('%d' % self.dm.brightness)
                # self.initNeuroglancer() #Critical #Cringe #guarantees sliders will work
                self.bShader.setToolTip('Hide Brightness & Contrast Shaders')
            self.setUpdatesEnabled(True)

        # self.bShader = QToolButton()
        self.bShader = QPushButton()
        self.bShader.setFixedWidth(46)
        self.bShader.setFixedSize(QSize())
        self.bShader.setCheckable(True)
        self.bShader.setText('Shader')
        self.bShader.clicked.connect(fn)

        self.tbbColorPicker = QToolButton()
        self.tbbColorPicker.setFixedSize(QSize(74, 16))
        self.tbbColorPicker.setStyleSheet("color: #f3f6fb; font-size: 10px; background-color: rgba(0, 0, 0, 0.5); border-radius: 2px;")
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
                    cfg.emViewer.setBackground()
                elif self.wTabs.currentIndex() == 1:
                    self.editorViewer.setBackground()
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
                cfg.emViewer.setBackground()
            elif self.wTabs.currentIndex() == 1:
                self.editorViewer.setBackground()
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
                cfg.emViewer.setBackground()
            elif self.wTabs.currentIndex() == 1:
                self.editorViewer.setBackground()
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
                cfg.emViewer.setBackground()
            elif self.wTabs.currentIndex() == 1:
                self.editorViewer.setBackground()

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
        self.leZoom.returnPressed.connect(lambda: self.viewer.set_zoom(float(self.leZoom.text())))
        try:
            self.leZoom.setText('%.3f' % self.dm['state']['neuroglancer']['zoom'])
        except:
            print_exception()

        self.zoomLab = QLabel('  Zoom  ')
        self.zoomLab.setFixedWidth(40)
        self.zoomLab.setAlignment(Qt.AlignCenter)
        self.zoomLab.setStyleSheet("color: #f3f6fb; font-size: 10px; background-color: rgba(0, 0, 0, 0.5); border-radius: 4px;")
        self.wZoom = HW(self.zoomLab, self.leZoom)
        self.wZoom.layout.setAlignment(Qt.AlignCenter)
        self.wZoom.layout.setSpacing(4)
        self.wZoom.setMaximumWidth(100)

        # self.tbbNgHelp = QToolButton()
        # def fn_ng_help():
        #     logger.info('')
        #     cfg.emViewer.setHelpMenu(not self.tbbNgHelp.isChecked())
        #     # if self.tbbNgHelp.isChecked():
        #     #     self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#161c20'))
        #     # else:
        #     #     self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#f3f6fb'))
        #
        # self.tbbNgHelp.setToolTip("Neuroglancer Help")
        # self.tbbNgHelp.setCheckable(True)
        # self.tbbNgHelp.pressed.connect(fn_ng_help)
        # self.tbbNgHelp.setFocusPolicy(Qt.NoFocus)
        # self.tbbNgHelp.setIcon(qta.icon("fa.question", color='#f3f6fb'))

        self.cmbNgAccessories = CheckableComboBox()
        self.cmbNgAccessories.setFixedWidth(84)
        self.cmbNgAccessories.setFixedHeight(15)
        self.cmbNgAccessories.addItem("Show/Hide...")
        self.cmbNgAccessories.addItem("NG Controls", state=self.dm['state']['neuroglancer']['show_controls'])
        self.cmbNgAccessories.addItem("Bounds", state=self.dm['state']['neuroglancer']['show_bounds'])
        self.cmbNgAccessories.addItem("Axes", state=self.dm['state']['neuroglancer']['show_axes'])
        self.cmbNgAccessories.addItem("Scale Bar", state=self.dm['state']['neuroglancer']['show_scalebar'])
        self.cmbNgAccessories.addItem("Shader", state=False)

        def cb_itemChanged():
            logger.info('')
            self.dm['state']['neuroglancer']['show_controls'] = self.cmbNgAccessories.itemChecked(1)
            self.dm['state']['neuroglancer']['show_bounds'] = self.cmbNgAccessories.itemChecked(2)
            self.dm['state']['neuroglancer']['show_axes'] = self.cmbNgAccessories.itemChecked(3)
            self.dm['state']['neuroglancer']['show_scalebar'] = self.cmbNgAccessories.itemChecked(4)
            cfg.emViewer.updateDisplayAccessories()
            if self.cmbNgAccessories.itemChecked(5):
                self.contrastSlider.setValue(int(self.dm.contrast))
                self.contrastLE.setText('%d' % self.dm.contrast)
                self.brightnessSlider.setValue(int(self.dm.brightness))
                self.brightnessLE.setText('%d' % self.dm.brightness)
                # self.initNeuroglancer() #Critical #Cringe #guarantees sliders will work
            self._vgap2.setVisible(self.dm['state']['neuroglancer']['show_controls'])
            self.parent.saveUserPreferences(silent=True)

        self.cmbNgAccessories.model().itemChanged.connect(cb_itemChanged)


        # ----------------
        self.ew0 = ExpandingHWidget(self)
        self.ew1 = ExpandingHWidget(self)
        # self.ew0.setFixedSize(QSize(80, 1))
        # self.ew0.setMaximumWidth(80)

        self._gap1 = QWidget()
        # self._gap1.setFixedSize(QSize(50, 1))
        self._gap1.setFixedWidth(50)

        self._vgap2 = QWidget()
        self._vgap2.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._vgap2.setFixedSize(QSize(1,24))
        self._vgap2.setVisible(self.dm['state']['neuroglancer']['show_controls'])

        self.lNotAligned = QLabel("Not Aligned")
        self.lNotAligned.hide()
        self.lNotAligned.setStyleSheet("QLabel { background-color: rgba(0, 0, 0, 0.5); font-size: 12px; color: #a30000; font-weight: 600;"
                                 "border-radius: 4px; font-family: Tahoma, sans-serif; padding: 4px; } ")


        self.labZarrSource = QLabel(' Series: ')
        self.labZarrSource.setStyleSheet("font-size: 11px; font-weight: 600; padding: 4px;")

        # .setStyleSheet("color: #f3f6fb; font-size: 10px; background-color: rgba(0, 0, 0, 0.5); border-radius: 4px;")
        # style = "QRadioButton{font-size: 11px; font-weight: 600; border: 1px solid #339933; " \
        #         "border-radius: 2px; background-color: #161c20; color: #f3f6fb;} " \
        #         "QRadioButton:disabled{background-color: grey;} QRadioButton::indicator{width: 12px; height: 12px; color: #339933;}"


        self.rbZarrRaw = QRadioButton('Raw')
        self.rbZarrRaw.clicked.connect(self.initNeuroglancer)
        # self.rbZarrRaw.setStyleSheet(style)

        self.rbZarrTransformed = QRadioButton('Transformed')
        self.rbZarrTransformed.clicked.connect(self.initNeuroglancer)
        # self.rbZarrTransformed.setStyleSheet(style)

        self.bgZarrSelect = QButtonGroup()
        self.bgZarrSelect.addButton(self.rbZarrRaw)
        self.bgZarrSelect.addButton(self.rbZarrTransformed)
        self.bgZarrSelect.setExclusive(True)

        # self.rbwZarr = HW(self.rbZarrRaw, self.rbZarrTransformed)
        # self.rbwZarr.layout.setSpacing(6)
        # self.rbwZarr.setStyleSheet("font-size: 11px;")

        self.toolbarNg = QToolBar()
        self.toolbarNg.setStyleSheet("")
        self.toolbarNg.setFixedHeight(23)
        # self.toolbarNg.layout().setAlignment(Qt.AlignCenter)
        self.toolbarNg.layout().setSpacing(6)
        self.toolbarNg.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbarNg.setAutoFillBackground(False)
        self.toolbarNg.addWidget(self.comboNgLayout)
        self.toolbarNg.addWidget(self.cmbNgAccessories)
        self.toolbarNg.addWidget(self.wZoom)
        self.toolbarNg.addWidget(self.ew0)
        # self.toolbarNg.addWidget(self.rbwZarr)
        self.toolbarNg.addSeparator()
        self.toolbarNg.addWidget(self.labZarrSource)
        self.toolbarNg.addWidget(self.rbZarrRaw)
        self.toolbarNg.addSeparator()
        self.toolbarNg.addWidget(self.rbZarrTransformed)
        self.toolbarNg.addSeparator()

        self.toolbarNg.addWidget(self.lNotAligned)
        self.toolbarNg.addWidget(self.ew1)
        self.toolbarNg.addWidget(self.bcWidget)
        # self.toolbarNg.addWidget(ExpandingWidget(self))
        self.toolbarNg.addWidget(self.bShader)
        self.toolbarNg.addWidget(self.tbbColorPicker)
        # self.toolbarNg.addWidget(self._gap1)

        # self.sideSliders = VW(self.wSliderZdisplay, self.zoomSliderAndLabel)
        # self.sideSliders = VW(self.wSliderZdisplay, self.zoomSliderAndLabel)
        # self.sideSliders.setFixedWidth(16)
        # self.sideSliders.layout.setSpacing(0)
        # self.sideSliders.setStyleSheet("""background-color: #222222; color: #ede9e8;""")

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

        self.w_tn_tra = QWidget()
        self.gl_tn_tra = QGridLayout()
        self.gl_tn_tra.setContentsMargins(0, 0, 0, 0)
        self.gl_tn_tra.addWidget(self.tn_tra, 0, 0, 1, 1)
        self.gl_tn_tra.addWidget(self.tn_tra_overlay, 0, 0, 1, 1)
        self.w_tn_tra.setLayout(self.gl_tn_tra)

        self.tn_ref_lab = QLabel('Reference Section')
        self.tn_ref_lab.setFixedHeight(26)
        self.tn_ref_lab.setStyleSheet("""font-size: 10px; background-color: #ede9e8; color: #161c20;""")

        self.tn_tra_lab = QLabel('Transforming Section')
        self.tn_tra_lab.setFixedHeight(26)
        self.tn_tra_lab.setStyleSheet("""font-size: 10px; background-color: #ede9e8; color: #161c20;""")

        self.tn_widget = QTableWidget()
        self.tn_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tn_widget.setAutoFillBackground(True)
        self.tn_widget.setMinimumWidth(64)
        self.tn_widget.setContentsMargins(0,0,0,0)
        self.tn_widget.setStyleSheet("""background-color: #222222;""")
        self.tn_widget.horizontalHeader().setHighlightSections(False)
        self.tn_widget.verticalHeader().setHighlightSections(False)
        self.tn_widget.setFocusPolicy(Qt.NoFocus)
        self.tn_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self.tn_widget.setRowCount(2)
        self.tn_widget.setColumnCount(1)
        self.vw1 = VW(self.tn_tra_lab, self.w_tn_tra)
        self.vw1.setStyleSheet("background-color: #222222;")
        self.vw2 = VW(self.tn_ref_lab, self.tn_ref)
        self.vw2.setStyleSheet("background-color: #222222;")
        self.tn_widget.setCellWidget(0, 0, self.vw1)
        self.tn_widget.setCellWidget(1, 0, self.vw2)
        self.tn_widget.setItem(0, 0, QTableWidgetItem())
        self.tn_widget.setItem(1, 0, QTableWidgetItem())
        self.tn_widget.verticalHeader().setVisible(False)
        self.tn_widget.horizontalHeader().setVisible(False)
        self.tn_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tn_widget.setShowGrid(False)
        v_header = self.tn_widget.verticalHeader()
        h_header = self.tn_widget.horizontalHeader()
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        # h_header.setSectionResizeMode(1, QHeaderView.Stretch)

        # vbl = VBL(self.tn_table, hw)
        # vbl.setSpacing(0)
        # self.tn_widget.setLayout(vbl)

        ####

        # path = os.path.join(get_appdir(), 'resources', 'x_reticle.png')
        #
        # self.tn_reticle1 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle1.setLayout(layout)
        # self.reticle1 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle1.layout().addWidget(self.tn_ms0,0,0)
        # self.tn_reticle1.layout().addWidget(self.reticle1,0,0)
        #
        # self.tn_reticle2 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle2.setLayout(layout)
        # self.reticle2 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle2.layout().addWidget(self.tn_ms1,0,0)
        # self.tn_reticle2.layout().addWidget(self.reticle2,0,0)
        #
        # self.tn_reticle3 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle3.setLayout(layout)
        # self.reticle3 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle3.layout().addWidget(self.tn_ms2,0,0)
        # self.tn_reticle3.layout().addWidget(self.reticle3,0,0)
        #
        # self.tn_reticle4 = QWidget()
        # layout = QGridLayout()
        # layout.setContentsMargins(0,0,0,0)
        # self.tn_reticle4.setLayout(layout)
        # self.reticle4 = CorrSignalThumbnail(self, path=path, extra='reticle')
        # self.tn_reticle4.layout().addWidget(self.tn_ms3,0,0)
        # self.tn_reticle4.layout().addWidget(self.reticle4,0,0)

        self.ms_table = QTableWidget()
        self.ms_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.tn_ms0 = CorrSignalThumbnail(self, name='ms0')
        self.tn_ms1 = CorrSignalThumbnail(self, name='ms1')
        self.tn_ms2 = CorrSignalThumbnail(self, name='ms2')
        self.tn_ms3 = CorrSignalThumbnail(self, name='ms3')
        self.msList = [self.tn_ms0, self.tn_ms1, self.tn_ms2, self.tn_ms3]
        self.tn_ms0.set_no_image()
        self.tn_ms1.set_no_image()
        self.tn_ms2.set_no_image()
        self.tn_ms3.set_no_image()

        self.ms_table.setAutoFillBackground(True)
        self.ms_table.setContentsMargins(0,0,0,0)
        self.ms_table.setStyleSheet(
            """QLabel{ color: #ede9e8; background-color: #222222; font-weight: 600; font-size: 9px; } QTableWidget{background-color: #222222;}""")
        self.ms_table.horizontalHeader().setHighlightSections(False)
        self.ms_table.verticalHeader().setHighlightSections(False)
        self.ms_table.setFocusPolicy(Qt.NoFocus)
        self.ms_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.ms_table.setRowCount(4)
        self.ms_table.setColumnCount(1)
        self.ms_table.setCellWidget(0,0, self.tn_ms0)
        self.ms_table.setCellWidget(1,0, self.tn_ms1)
        self.ms_table.setCellWidget(2,0, self.tn_ms2)
        self.ms_table.setCellWidget(3,0, self.tn_ms3)
        self.ms_table.setItem(0, 0, QTableWidgetItem())
        self.ms_table.setItem(1, 0, QTableWidgetItem())
        self.ms_table.setItem(2, 0, QTableWidgetItem())
        self.ms_table.setItem(3, 0, QTableWidgetItem())
        self.ms_table.verticalHeader().setVisible(False)
        self.ms_table.horizontalHeader().setVisible(False)
        self.ms_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ms_table.setShowGrid(True)
        v_header = self.ms_table.verticalHeader()
        h_header = self.ms_table.horizontalHeader()
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
            self._btn_playMatchTimer.setIcon(qta.icon('fa.play'))

        self.toggleMatches.clicked.connect(fn_stop_playing)
        self.toggleMatches.clicked.connect(self.fn_toggleTargKarg)

        self.matches_tn0 = ThumbnailFast(self, name='match0')
        self.matches_tn1 = ThumbnailFast(self, name='match1')
        self.matches_tn2 = ThumbnailFast(self, name='match2')
        self.matches_tn3 = ThumbnailFast(self, name='match3')
        self.match_thumbnails = [self.matches_tn0, self.matches_tn1, self.matches_tn2, self.matches_tn3]

        self.ktarg_table = QTableWidget()
        self.ktarg_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.ktarg_table.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        # self.ktarg_table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.ktarg_table.setAutoFillBackground(True)
        # self.ktarg_table.setMinimumWidth(64)
        # self.ktarg_table.setMaximumWidth(200)
        self.ktarg_table.setContentsMargins(0,0,0,0)
        self.ktarg_table.setStyleSheet(
            """QLabel{ color: #ede9e8; background-color: #222222; font-weight: 600; font-size: 9px; } QTableWidget{background-color: #222222;}""")
        self.ktarg_table.horizontalHeader().setHighlightSections(False)
        self.ktarg_table.verticalHeader().setHighlightSections(False)
        self.ktarg_table.setFocusPolicy(Qt.NoFocus)
        self.ktarg_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.ktarg_table.setRowCount(4)
        self.ktarg_table.setColumnCount(1)
        # self.ktarg_table.setColumnCount(2)
        self.ktarg_table.setCellWidget(0, 0, self.matches_tn0)
        self.ktarg_table.setCellWidget(1, 0, self.matches_tn1)
        self.ktarg_table.setCellWidget(2, 0, self.matches_tn2)
        self.ktarg_table.setCellWidget(3, 0, self.matches_tn3)
        self.ktarg_table.setItem(0, 0, QTableWidgetItem())
        self.ktarg_table.setItem(1, 0, QTableWidgetItem())
        self.ktarg_table.setItem(2, 0, QTableWidgetItem())
        self.ktarg_table.setItem(3, 0, QTableWidgetItem())
        self.ktarg_table.verticalHeader().setVisible(False)
        self.ktarg_table.horizontalHeader().setVisible(False)
        self.ktarg_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ktarg_table.setShowGrid(True)
        v_header = self.ktarg_table.verticalHeader()
        h_header = self.ktarg_table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(0, QHeaderView.Stretch)
        v_header.setSectionResizeMode(1, QHeaderView.Stretch)
        v_header.setSectionResizeMode(2, QHeaderView.Stretch)
        v_header.setSectionResizeMode(3, QHeaderView.Stretch)

        # Playback Widget

        self._btn_playMatchTimer = QPushButton()
        self._btn_playMatchTimer.setIconSize(QSize(11, 11))
        self._btn_playMatchTimer.setFixedSize(14, 14)
        self._btn_playMatchTimer.setIcon(qta.icon('fa.play'))

        def startStopMatchTimer():
            logger.info('')
            if self.parent._isProjectTab():
                self.dm['state']['blink'] = not self.dm['state']['blink']
                if self.dm['state']['blink']:
                    self.matchPlayTimer.start()
                    self._btn_playMatchTimer.setIcon(qta.icon('fa.pause'))
                else:
                    self.matchPlayTimer.stop()
                    self._btn_playMatchTimer.setIcon(qta.icon('fa.play'))
        self._btn_playMatchTimer.clicked.connect(startStopMatchTimer)

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

        self.labMatches = QLabel('Auto-toggle:')
        self.labMatches.setFocusPolicy(Qt.NoFocus)
        self.labMatches.setAlignment(Qt.AlignRight)
        self.labMatches.setFixedHeight(14)
        self.labMatches.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #222222;')

        self.labMatchesTog = QLabel('Toggle:')
        self.labMatchesTog.setFocusPolicy(Qt.NoFocus)
        self.labMatchesTog.setAlignment(Qt.AlignRight)
        self.labMatchesTog.setFixedHeight(14)
        self.labMatchesTog.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #222222;')

        self.mwTitle = HW(self.cbAnnotateSignals, self.labMatches, self._btn_playMatchTimer, self.labMatchesTog,
                          self.toggleMatches)
        self.mwTitle.layout.setAlignment(Qt.AlignRight)
        self.mwTitle.layout.setSpacing(4)
        self.mwTitle.setStyleSheet('font-size: 10px; background-color: #ede9e8; color: #222222;')


        hw = HW(self.ktarg_table, self.ms_table)
        hw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.match_widget = VW(self.mwTitle, hw)
        self.match_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Warnings
        self.wWebengineEditor = HW(self.ngVertLab, self.ng_widget, self.zoomSliderAndLabel)
        # self.wWebengineEditor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.warning_data = WarningNotice(self, '<b>Warning:</b> Some data is out of sync.', fixbutton=True, symbol='×')

        self.warning_data.fixbutton.clicked.connect(self.fixAll)
        self.warning_data.fixbutton.setText('Fix All')
        self.warning_data.hide()

        self.glGifPlayer = QGridLayout()
        self.glGifPlayer.addWidget(self.gifPlayer, 0, 0)
        # self.glGifPlayer.addWidget(self.gifPlayer, 0, 0, 2, 2)
        # self.glGifPlayer.addWidget(self.slrGif, 1, 1, 1, 1)
        # self.glGifPlayer.setContentsMargins(10,10,10,10)
        self.glGifPlayer.setContentsMargins(2,2,2,2)

        self.wGifPlayer = QWidget()
        self.wGifPlayer.setMinimumSize(QSize(128,128))
        # self.wGifPlayer.setStyleSheet("background-color: #000000;")
        self.wGifPlayer.setLayout(self.glGifPlayer)

        self.checkboxes = HW(self.cbDefaults, self.cbSaved)

        # self.cpanelEditor = HW(self.bTransform, self.bSWIM, self.bSaveSettings)
        self.btnsSWIM = VW(HW(self.bSWIM, self.bSaveSettings), self.bPull)
        self.btnsSWIM.layout.setContentsMargins(2,2,2,2)
        self.btnsSWIM.layout.setSpacing(2)

        self.vblRightPanel = VBL(
            # self.warning_data,
            # self.wRadiobuttons,
            self.swMethod,
            self.checkboxes,
            self.btnsSWIM,
            # self.bRevertSettings,
            self.wGifPlayer,
            # self.gbOutputSettings,
            )
        self.gbRightPanel = QGroupBox()
        self.gbRightPanel.setLayout(self.vblRightPanel)

        self.gbRightPanel.setMaximumWidth(380)
        # self.wRightPanel.setFocusPolicy(Qt.NoFocus)
        # self.wRightPanel.setStyleSheet("""
        # QWidget{
        #     font-size: 10px;
        # }
        # QTabBar::tab {
        #     font-size: 9px;
        #     height: 12px;
        #     width: 64px;
        #     min-width: 64px;
        #     max-width: 64px;
        #     margin-bottom: 0px;
        #     padding-bottom: 0px;
        # }
        # QGroupBox {
        #     color: #161c20;
        #     border: 1px solid #161c20;
        #     font-size: 10px;
        #     /*font-weight: 600;*/
        #     border-radius: 2px;
        #     margin: 2px;
        #     padding: 2px;
        #     padding-top: 8px;
        # }
        # QGroupBox:title {
        #     color: #161c20;
        #     /*font-weight:600;*/
        #     font-size: 9px;
        #     subcontrol-origin: margin;
        #     subcontrol-position: top center;
        #     margin-bottom: 12px;
        # }
        # """)

        self.wEditAlignment = QSplitter(Qt.Orientation.Horizontal)
        self.wEditAlignment.addWidget(self.wWebengineEditor)
        self.wEditAlignment.addWidget(self.gbRightPanel)
        self.wEditAlignment.setCollapsible(0, False)
        self.wEditAlignment.setCollapsible(1, False)
        self.wEditAlignment.setStretchFactor(0, 99)
        # self.wEditAlignment.setStretchFactor(1, 1)

        logger.info("<<")

    def onPushSettings(self):
        logger.info('')
        self.dm.pushDefaultSettings()
        self.dataUpdateMA()
        pass

    def fixAll(self):
        logger.info('')
        to_align = self.dm.needsAlignIndexes()
        # to_regenerate = self.dm.needsGenerateIndexes()
        logger.info(f'\nAlign indexes: {pprint.pformat(to_align)}')
        self.parent.align(dm=self.dm, indexes=to_align)


        self.parent.regenZarr()


    def set_viewer_role(self, role):
        if role == 'ref':
            self.set_reference()
        elif role == 'tra':
            self.set_transforming()

    def set_reference(self):
        # logger.critical('')
        logger.info('')
        self.dm['state']['tra_ref_toggle'] = 'ref'
        if self.dm.skipped():
            self.parent.warn('This section does not have a reference because it is excluded.')
            return
        # self._tra_pt_selected = None
        self.editorViewer.role = 'ref'
        self.editorViewer.set_layer()
        # self.editorViewer._selected_index['ref'] = self.editorViewer.getNextPoint('ref')
        # self.editorViewer.restoreManAlignPts()
        self.update_match_list_widgets()
        self.cl_ref.setChecked(True)
        self.cl_tra.setChecked(False)
        self.lw_ref.setEnabled(True)
        self.lw_tra.setEnabled(False)
        self.btn_clrBasePts.setEnabled(False)
        self.btn_undoBasePts.setEnabled(False)
        self.btn_clrRefPts.setEnabled(True)
        self.btn_undoRefPts.setEnabled(True)
        self.lw_gb_r.setAutoFillBackground(True)
        self.lab_tra.setStyleSheet("color: #4d4d4d;")
        self.lab_ref.setStyleSheet("color: #161c20;")
        # self.lw_gb_r.setStyleSheet("""border-width: 3px; border-color: #339933; font-weight: 600;""")
        # self.lw_gb_l.setStyleSheet("""border-color: #666666; font-weight: 300;""")
        self.lw_gb_r.setStyleSheet("""QWidget{border-width: 3px; border-color: #339933;} QGroupBox {font-weight: 
        600;}""")
        self.lw_gb_l.setStyleSheet("""border-color: #666666; """)
        self.editorViewer.drawSWIMwindow() #redundant
        for i in list(range(0,3)):
            self.lw_tra.item(i).setForeground(QColor('#666666'))
            self.lw_ref.item(i).setForeground(QColor('#141414'))
        logger.info(f"<<<< set_reference <<<<")


    def onDefaultsCheckbox(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            logger.info('')
            if self.cbDefaults.isChecked():
                if not self.dm.isDefaults():
                    self.dm.applyDefaults()
            else:
                self.cbDefaults.setChecked(self.dm.isDefaults())
            self.dataUpdateMA()




    def set_transforming(self):
        logger.info('')
        self.dm['state']['tra_ref_toggle'] = 'tra'
        self.editorViewer.role = 'tra'
        self.editorViewer.set_layer()
        # self.editorViewer._selected_index['tra'] = self.editorViewer.getNextPoint('tra')
        # self.editorViewer.restoreManAlignPts()
        self.update_match_list_widgets()
        self.cl_tra.setChecked(True)
        self.cl_ref.setChecked(False)
        self.lw_tra.setEnabled(True)
        self.lw_ref.setEnabled(False)
        self.btn_clrBasePts.setEnabled(True)
        self.btn_undoBasePts.setEnabled(True)
        self.btn_clrRefPts.setEnabled(False)
        self.btn_undoRefPts.setEnabled(False)
        self.lw_gb_l.setAutoFillBackground(True)
        self.lab_ref.setStyleSheet("color: #4d4d4d;")
        self.lab_tra.setStyleSheet("color: #161c20;")
        # self.lw_gb_l.setStyleSheet("""border-width: 3px; border-color: #339933; font-weight: 600;""")
        # self.lw_gb_r.setStyleSheet("""border-color: #666666; font-weight: 300;""")

        self.lw_gb_l.setStyleSheet("""QWidget{border-width: 3px; border-color: #339933;} QGroupBox {font-weight: 
        600;}""")
        self.lw_gb_r.setStyleSheet("""border-color: #666666;""")
        self.editorViewer.drawSWIMwindow() #redundant
        for i in list(range(0,3)):
            self.lw_tra.item(i).setForeground(QColor('#141414'))
            self.lw_ref.item(i).setForeground(QColor('#666666'))


    def onSideTabChange(self):
        logger.info('')
        if self.te_logs.isVisible():
            self.refreshLogs()


    def fn_toggleTargKarg(self):
        logger.info('')
        setData('state,targ_karg_toggle', 1 - getData('state,targ_karg_toggle'))
        self.toggleMatches.setIcon(qta.icon(
            ('mdi.toggle-switch', 'mdi.toggle-switch-off')[getData('state,targ_karg_toggle')]))
        # (self.rb_targ.setChecked, self.rb_karg.setChecked)[getData('state,targ_karg_toggle')](True)
        self.parent.setTargKargPixmaps()


    def setRbStackView(self):
        if DEV:
            logger.critical(caller_name())
        self.cl_ref.setChecked(True)
        self.cl_ref.setStyleSheet('background-color: #339933; color: #f3f6fb; font-size: 10px; font-weight: 600;')
        self.cl_tra.setStyleSheet('background-color: #222222; color: #f3f6fb; font-size: 10px; font-weight: 600;')


    def setRbRegionsView(self):
        if DEV:
            logger.critical(caller_name())
        self.cl_tra.setChecked(True)
        self.cl_tra.setStyleSheet('background-color: #339933; color: #f3f6fb; font-size: 10px; font-weight: 600;')
        self.cl_ref.setStyleSheet('background-color: #222222; color: #f3f6fb; font-size: 10px; font-weight: 600;')


    def refreshLogs(self):
        logger.info('')
        logs_path = os.path.join(self.dm.dest(), 'logs', 'recipemaker.log')
        if os.path.exists(logs_path):
            with open(logs_path, 'r') as f:
                text = f.read()
        else:
            text = 'No Log To Show.'
        self.te_logs.setText(text)
        self.te_logs.verticalScrollBar().setValue(self.te_logs.verticalScrollBar().maximum())

    def updateAutoSwimRegions(self):
        logger.info('')
        if 'grid' in self.dm.method():
            self.dm.quadrants = [self.Q1.isClicked, self.Q2.isClicked, self.Q3.isClicked, self.Q4.isClicked]
        self.editorViewer.drawSWIMwindow()

    def updateAnnotations(self):
        if DEV:
            logger.info(f'[DEV] [{caller_name()}] [{self.dm.zpos}] Updating annotations...')
        self.editorViewer.drawSWIMwindow()


    def onTranslate(self):
        if (self.lw_tra.selectedIndexes() == []) and (self.lw_ref.selectedIndexes() == []):
            self.parent.warn('No points are selected in the list')
            return

        selections = []
        if len(self.lw_ref.selectedIndexes()) > 0:
            role = 'ref'
            for sel in self.lw_ref.selectedIndexes():
                selections.append(int(sel.data()[0]))
        else:
            role = 'tra'
            for sel in self.lw_tra.selectedIndexes():
                selections.append(int(sel.data()[0]))

        pts_old = self.dm.manpoints()[role]
        pts_new = pts_old

        for sel in selections:
            new_x = pts_old[sel][1] - int(self.leTranslateX.text())
            new_y = pts_old[sel][0] - int(self.leTranslateY.text())
            pts_new[sel] = (new_y, new_x)

        self.dm.set_manpoints(role=role, matchpoints=pts_new)
        # self.editorViewer.restoreManAlignPts()
        self.editorViewer.drawSWIMwindow()

    def onTranslate_x(self):
        if (self.lw_tra.selectedIndexes() == []) and (self.lw_ref.selectedIndexes() == []):
            self.parent.warn('No points are selected in the list')
            return

        selections = []
        if len(self.lw_ref.selectedIndexes()) > 0:
            role = 'ref'
            for sel in self.lw_ref.selectedIndexes():
                selections.append(int(sel.data()[0]))
        else:
            role = 'tra'
            for sel in self.lw_tra.selectedIndexes():
                selections.append(int(sel.data()[0]))

        pts_old = self.dm.manpoints()[role]
        pts_new = pts_old


        for sel in selections:
            new_x = pts_old[sel][1] - int(self.leTranslateX.text())
            new_y = pts_old[sel][0]
            pts_new[sel] = (new_y, new_x)

        self.dm.set_manpoints(role=role, matchpoints=pts_new)
        # self.editorViewer.restoreManAlignPts()
        self.editorViewer.drawSWIMwindow()

    def onTranslate_y(self):
        if (self.lw_tra.selectedIndexes() == []) and (self.lw_ref.selectedIndexes() == []):
            self.parent.warn('No points are selected in the list')
            return

        selections = []
        if len(self.lw_ref.selectedIndexes()) > 0:
            role = 'ref'
            for sel in self.lw_ref.selectedIndexes():
                selections.append(int(sel.data()[0]))
        else:
            role = 'tra'
            for sel in self.lw_tra.selectedIndexes():
                selections.append(int(sel.data()[0]))

        pts_old = self.dm.manpoints()[role]
        pts_new = pts_old

        for sel in selections:
            new_x = pts_old[sel][1]
            new_y = pts_old[sel][0] - int(self.leTranslateY.text())
            pts_new[sel] = (new_y, new_x)

        self.dm.set_manpoints(role=role, matchpoints=pts_new)
        # self.editorViewer.restoreManAlignPts()
        self.editorViewer.drawSWIMwindow()


    def onNgLayoutCombobox(self) -> None:
        caller = inspect.stack()[1].function
        if caller in ('main', '<lambda>'):
            choice = self.comboNgLayout.currentText()
            logger.info('Setting neuroglancer layout to %s' % choice)
            setData('state,neuroglancer,layout', choice)
            self.parent.tell(f'Neuroglancer Layout: {choice}')
            try:
                self.parent.hud("Setting Neuroglancer Layout to '%s'... " % choice)
                layout_actions = {
                    'xy': self.parent.ngLayout1Action,
                    'yz': self.parent.ngLayout2Action,
                    'xz': self.parent.ngLayout3Action,
                    'xy-3d': self.parent.ngLayout4Action,
                    'yz-3d': self.parent.ngLayout5Action,
                    'xz-3d': self.parent.ngLayout6Action,
                    # '3d': self.parent.ngLayout7Action,
                    '4panel': self.parent.ngLayout8Action
                }
                layout_actions[choice].setChecked(True)
                self.viewer.initViewer()
            except:
                print_exception()
                logger.error('Unable To Change Neuroglancer Layout')


    def updateCursor(self):
        QApplication.restoreOverrideCursor()
        # self.msg_MAinstruct.setText("Toggle 'Mode' to select manual correspondence points")

        if self.dm['state']['current_tab'] == 1:
            # if self.tgl_alignMethod.isChecked():
            if self.dm.method() in ('manual_hint', 'manual_strict'):
                pixmap = QPixmap('src/resources/match-point.png')
                cursor = QCursor(pixmap.scaled(QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                QApplication.setOverrideCursor(cursor)

    # def isManualReady(self):
    #     return self.tgl_alignMethod.isChecked()

    # def fade(self):
    #     self.MA_ng_widget.setWindowOpacity(0.5)
    #     QTimer.singleShot(1000, self.unfade)
    #
    #
    # def unfade(self):
    #     self.setWindowOpacity(1)


    # def onMAaction(self):
    #     if self.combo_MA_actions.currentIndex() == 0:
    #         self.dm.set_all_methods_automatic()


    def validate_MA_points(self):
        # if len(cfg.refViewer.pts.keys()) >= 3:
        if len(self.editorViewer.pts['ref']) == len(self.editorViewer.pts['tra']):
            if len(self.editorViewer.pts['tra']) == 3:
                return True
        return False


    def updateZarrRadiobuttons(self):
        logger.info('')
        isGenerated = self.dm.is_zarr_generated()
        self.parent.bExport.setVisible(self.dm.is_zarr_generated())
        self.gbGrid.setTitle(f'Level {self.dm.lvl()} Grid Alignment Settings')
        # self.cbDefaults.setText(f'Uses defaults')
        self.cbDefaults.setText(f'Default preferences')
        # ready = self.dm.is_alignable()
        if isGenerated:
            self.rbZarrTransformed.setEnabled(True)
            self.rbZarrTransformed.setChecked(True)
        else:
            self.rbZarrTransformed.setEnabled(False)
            self.rbZarrRaw.setChecked(True)

    @Slot()
    def dataUpdateMA(self):
        caller = inspect.stack()[1].function
        logger.critical(f"[{caller}]")
        # if DEV:
        #     logger.critical(f"[DEV] called by {caller_name()}")

        # self.msg_MAinstruct.setVisible(self.dm.current_method not in ('grid-default', 'grid-custom'))
        # self.gbOutputSettings.setTitle(f'Level {self.dm.lvl()} Output Settings')
        # self.gbGrid.setTitle(f'Level {self.dm.lvl()} SWIM Settings')

        self.parent.bRegenZarr.setEnabled(self.dm.is_aligned())
        # self.gifPlayer.labNull.setText(('Not Aligned.','No Data.')[self.dm.is_aligned()])
        self.bPull.setVisible((self.dm.scale != self.dm.coarsest_scale_key()) and self.dm.is_alignable())

        self.gifPlayer.radiobuttons.setVisible(os.path.exists(self.dm.path_cafm_gif()))

        ready = self.dm['level_data'][self.dm.scale]['alignment_ready']
        if self.dm.is_alignable() and ready:
            self.swMethod.setCurrentIndex(0)
            # self.btnsSWIM.show()
            # self.bPull.setVisible((self.dm.scale != self.dm.coarsest_scale_key()) and self.dm.is_alignable())
            self.bSWIM.show()
            self.bSaveSettings.show()
            ss = self.dm['stack'][self.dm.zpos]['levels'][self.dm.scale]['swim_settings']
            if self.dm.current_method == 'grid':
                # self.swMethod.setCurrentIndex(0)
                self.twMethod.setCurrentIndex(0)

                siz1x1 = ss['method_opts']['size_1x1']
                # min_dim = min(self.dm.image_size())
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
                # Todo check swim preferences for manual mode, either 'point' or 'region'
                if self.dm.current_method == 'manual_strict':
                    self.rb_MA_strict.setChecked(True)
                else:
                    self.rb_MA_hint.setChecked(True)
                self.update_match_list_widgets()

                img_w, _ = self.dm.image_size()
                self.leMatch.setValidator(QIntValidator(64, img_w))
                self.leMatch.setText(str(ss['method_opts']['size']))  # Todo
                self.sliderMatch.setMaximum(img_w)
                self.sliderMatch.setValue(int(ss['method_opts']['size']))  # Todo

            self.updateAaButtons()

            self.cbDefaults.setChecked(self.dm.isDefaults())
            self.cbSaved.setChecked(self.dm.ssHash() == self.dm.ssSavedHash())

            self.bTransform.setEnabled(self.dm.is_aligned())
            # self.bSWIM.setEnabled(self.dm.is_aligned() and not os.path.exists(self.dm.path_aligned()))
            self.bSaveSettings.setEnabled(not self.dm.ssSavedComports() and self.dm.ht.haskey(self.dm.swim_settings())) #Critical

            self.leWhitening.setText(str(ss['whitening']))
            self.leIterations.setText(str(ss['iterations']))
            self.cbClobber.setChecked(bool(ss['clobber']))
            self.leClobber.setText(str(ss['clobber_size']))
            self.leClobber.setEnabled(self.cbClobber.isChecked())

            if self.te_logs.isVisible():
                self.refreshLogs()

        else:
            self.swMethod.setCurrentIndex(1)
            self.swMethod.setCurrentIndex(1)
            self.bSWIM.hide()
            self.bSaveSettings.hide()
            self.checkboxes.hide()
        if hasattr(self, 'editorViewer'):
            self.editorViewer.drawSWIMwindow() #1009+


    # def updateEnabledButtonsMA(self):
    #     method = self.dm.current_method
    #     sec = self.dm.zpos
    #     realign_tip = 'SWIM align section #%d and generate an image' % sec
    #     if method == 'grid-custom':
    #         self.parent._btn_alignOne.setEnabled(True)
    #         if sum(self.dm.grid_custom_regions) >= 3:
    #             self.parent._btn_alignOne.setEnabled(True)
    #             realign_tip = 'SWIM align section #%d using custom grid method' % sec
    #         else:
    #             self.parent._btn_alignOne.setEnabled(False)
    #             realign_tip = 'SWIM alignment requires at least three regions to form an affine'
    #     elif method == 'grid-default':
    #         self.parent._btn_alignOne.setEnabled(True)
    #         realign_tip = 'SWIM align section #%d using default grid regions' % sec
    #     elif method in ('manual-hint', 'manual-strict'):
    #         if (len(self.dm.manpoints()['ref']) >= 3) and (len(self.dm.manpoints()['tra']) >= 3):
    #             self.parent._btn_alignOne.setEnabled(True)
    #             realign_tip = 'SWIM align section #%d using manual correspondence regions method ' \
    #                           'and generate an image' % sec
    #         else:
    #             self.parent._btn_alignOne.setEnabled(False)
    #             realign_tip = 'SWIM alignment requires at least three regions to form an affine'
    #
    #     self.parent._btn_alignOne.setToolTip('\n'.join(textwrap.wrap(realign_tip, width=35)))

    def update_match_list_widgets(self):
        #Innocent
        if self.wTabs.currentIndex() == 1:
            # if self.dm.current_method in ('manual-hint', 'manual-strict'):
            if self.twMethod.currentIndex() == 1:
                # self.setUpdatesEnabled(False)

                # font = QFont()
                # font.setBold(True)
                #
                # self.lw_tra.clear()
                # self.lw_tra.update()
                # # for i, p in enumerate(self.editorViewer.tra_pts):

                for i in range(0,3):
                    self.lw_tra.item(i).setText('')
                    self.lw_tra.item(i).setIcon(QIcon())
                    self.lw_ref.item(i).setText('')
                    self.lw_ref.item(i).setIcon(QIcon())

                for i, p in enumerate(self.dm.manpoints_mir('tra')):
                    # if p[0]:
                    if p and p[0]:
                        x, y = p[0], p[1]
                        msg = '%d: x=%.1f, y=%.1f' % (i, x, y)
                        self.lw_tra.item(i).setText(msg)
                    else:
                        self.lw_tra.item(i).setText('')

                self.lw_tra.update()

                # self.lw_ref.clear()
                # self.lw_ref.update()
                # # for i, p in enumerate(self.editorViewer.ref_pts):
                for i, p in enumerate(self.dm.manpoints_mir('ref')):
                    # if p[0]:
                    if p and p[0]:
                        x, y = p[0], p[1]
                        msg = '%d: x=%.1f, y=%.1f' % (i, x, y)
                        self.lw_ref.item(i).setText(msg)
                    else:
                        self.lw_ref.item(i).setText('')

                self.lw_ref.update()

                # if self.dm['state']['tra_ref_toggle'] == 'tra':
                color = cfg.glob_colors[self.editorViewer._selected_index['tra']]
                index = self.editorViewer._selected_index['tra']

                if self.editorViewer.numPts('tra') < 3:
                    self.lab_tra.setText('Next Color:   ')
                    self.lab_nextcolor0.setStyleSheet(f'''background-color: {color};''')
                    self.lab_nextcolor0.show()
                else:
                    self.lab_tra.setText('Complete!')
                    self.lab_nextcolor0.hide()
                self.lw_tra.item(index).setSelected(True)
                self.lw_tra.item(index).setIcon(qta.icon('fa.arrow-left', color='#161c20'))

                # elif self.dm['state']['tra_ref_toggle'] == 'ref':
                color = cfg.glob_colors[self.editorViewer._selected_index['ref']]
                index = self.editorViewer._selected_index['ref']
                if self.editorViewer.numPts('ref') < 3:
                    self.lab_ref.setText('Next Color:   ')
                    self.lab_nextcolor1.setStyleSheet(f'''background-color: {color};''')
                    self.lab_nextcolor1.show()

                else:
                    self.lab_ref.setText('Complete!')
                    self.lab_nextcolor1.hide()
                self.lw_ref.item(index).setSelected(True)
                self.lw_ref.item(index).setIcon(qta.icon('fa.arrow-left', color='#161c20'))


    def deleteAllMpRef(self):
        logger.info('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        self.parent.hud.post('Deleting All Reference Image Manual Correspondence Points from Buffer...')
        self.dm.set_manpoints('ref', [None, None, None])
        self.editorViewer._selected_index['ref'] = 0
        # self.editorViewer.restoreManAlignPts()
        self.editorViewer.drawSWIMwindow()
        delete_matches(self.dm)
        delete_correlation_signals(self.dm)
        self.parent.dataUpdateWidgets()
        self.update_match_list_widgets()
        if self.parent.dwSnr.isVisible():
            self.dSnr_plot.initSnrPlot()



    def deleteAllMpBase(self):
        logger.info('Deleting All Base Image Manual Correspondence Points from Buffer...')
        self.parent.hud.post('Deleting All Base Image Manual Correspondence Points from Buffer...')
        self.dm.set_manpoints('tra', [None, None, None])
        self.editorViewer._selected_index['tra'] = 0
        # self.editorViewer.restoreManAlignPts()
        self.editorViewer.drawSWIMwindow()
        # delete_matches(self.dm)
        # delete_correlation_signals(self.dm)
        self.parent.dataUpdateWidgets()
        self.update_match_list_widgets()
        if self.parent.dwSnr.isVisible():
            self.dSnr_plot.initSnrPlot()


    def deleteAllMp(self):
        logger.info('deleteAllMp >>>>')
        logger.info('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        self.parent.hud.post('Deleting All Base + Reference Image Manual Correspondence Points from Buffer...')
        self.dm.set_manpoints('ref', [None, None, None])
        self.dm.set_manpoints('tra', [None, None, None])
        self.editorViewer._selected_index['ref'] = 0
        self.editorViewer._selected_index['tra'] = 0
        # self.editorViewer.restoreManAlignPts()
        self.editorViewer.drawSWIMwindow()
        # delete_matches(self.dm)
        # delete_correlation_signals(self.dm)
        self.parent.dataUpdateWidgets()
        self.update_match_list_widgets()
        if self.parent.dwSnr.isVisible():
            self.dSnr_plot.initSnrPlot()
        logger.info('<<<< deleteAllMp')


    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu and source is self.lw_ref:
            menu = QMenu()
            # self.deleteMpRefAction = QAction('Delete')
            # # self.deleteMpRefAction.setStatusTip('Delete this manual correspondence point')
            # self.deleteMpRefAction.triggered.connect(self.deleteMpRef)
            # menu.addAction(self.deleteMpRefAction)
            self.deleteAllMpRefAction = QAction('Clear All Reference Regions')
            # self.deleteAllMpRefAction.setStatusTip('Delete all fn_reference manual correspondence points')
            self.deleteAllMpRefAction.triggered.connect(self.deleteAllMpRef)
            menu.addAction(self.deleteAllMpRefAction)
            self.deleteAllPtsAction0 = QAction('Clear All Regions')
            # self.deleteAllPtsAction0.setStatusTip('Delete all manual correspondence points')
            self.deleteAllPtsAction0.triggered.connect(self.deleteAllMp)
            menu.addAction(self.deleteAllPtsAction0)
            if menu.exec_(event.globalPos()):
                item = source.itemAt(event.pos())
            return True
        elif event.type() == QEvent.ContextMenu and source is self.lw_tra:
            menu = QMenu()
            # self.deleteMpBaseAction = QAction('Delete')
            # # self.deleteMpBaseAction.setStatusTip('Delete this manual correspondence point')
            # self.deleteMpBaseAction.triggered.connect(self.deleteMpBase)
            # menu.addAction(self.deleteMpBaseAction)
            self.deleteAllMpBaseAction = QAction('Clear All Transforming Regions')
            # self.deleteAllMpBaseAction.setStatusTip('Delete all base manual correspondence points')
            self.deleteAllMpBaseAction.triggered.connect(self.deleteAllMpBase)
            menu.addAction(self.deleteAllMpBaseAction)
            self.deleteAllPtsAction1 = QAction('Clear All Regions')
            # self.deleteAllPtsAction1.setStatusTip('Delete all manual correspondence points')
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
        caller = inspect.stack()[1].function
        if caller == 'main':
            logger.info(f'[{caller}]')
            if self._allow_zoom_change:
                # caller = inspect.stack()[1].function
                if self.dm['state']['current_tab'] == 1:
                    zoom = self.editorViewer.zoom()
                else:
                    zoom = cfg.emViewer.zoom()
                if zoom == 0:
                    return
                # val =
                # if val in range(-2147483648, 2147483647):
                try:
                    self.zoomSlider.setValue(1/zoom)
                except:
                    print_exception()
                    logger.warning(f"zoom = {zoom}")
                # self.zoomSlider.setValue(zoom)
                self._allow_zoom_change = True

    def onZoomSlider(self):
        caller = inspect.stack()[1].function
        if caller not in ('slotUpdateZoomSlider', 'setValue'):  # Original #0314
            val = 1 / self.zoomSlider.value()
            if self.dm['state']['current_tab'] == 1:
                if abs(self.editorViewer.state.cross_section_scale - val) > .0001:
                    self.editorViewer.set_zoom(val)
            elif self.dm['state']['current_tab'] == 0:
                try:
                    if abs(cfg.emViewer.state.cross_section_scale - val) > .0001:
                        cfg.emViewer.set_zoom(val)
                except:
                    print_exception()


    def slotUpdateZoomSlider(self):
        # Lets only care about REF <--> wSlider
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if self.dm['state']['current_tab'] == 1:
                val = self.editorViewer.state.cross_section_scale
            else:
                val = cfg.emViewer.state.cross_section_scale
            if val:
                if val != 0:
                    # new_val = float(sqrt(val))
                    new_val = float(val * val)
                    logger.info('new_val = %s' % str(new_val))
                    self.zoomSlider.setValue(new_val)
        except:
            print_exception()


    def onSliderZmag(self):

        caller = inspect.stack()[1].function
        logger.info('caller: %s' % caller)
        try:
            val = self.sliderZdisplay.value()
            if self.dm['state']['current_tab'] == 1:
                state = copy.deepcopy(self.editorViewer.state)
                state.relative_display_scales = {'z': val}
                self.editorViewer.set_state(state)
                # state = copy.deepcopy(cfg.stageViewer.state)
                # state.relative_display_scales = {'z': val}
                # cfg.editorViewer.set_state(state)

            else:
                # logger.info('val = %d' % val)
                state = copy.deepcopy(cfg.emViewer.state)
                state.relative_display_scales = {'z': val}
                cfg.emViewer.set_state(state)
            self.parent.update()
        except:
            print_exception()


    @Slot()
    def async_table_load(self):
        self.loadTable.emit()


    def initUI_table(self):
        '''Layer View Widget'''
        logger.info('')
        self.project_table = ProjectTable(parent=self, dm=self.dm)
        self.project_table.updatePbar.connect(self.parent.pbar.setValue)
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
        # self.parent.statusBar.showMessage('Loading data into tree view...')
        # time consuming - refactor?
        self.parent.tell('Loading data into tree view...')
        self.treeview_model.load(self.dm.to_dict())
        # self.treeview.setModel(self.treeview_model)
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
        self.treeview_model = JsonModel(parent=self)
        self.treeview = QTreeView()
        self.treeview.expanded.connect(lambda index: self.get_treeview_data(index))

        # self.treeview.setStyleSheet("color: #161c20;")
        self.treeview.setAnimated(True)
        self.treeview.header().resizeSection(0, 340)
        self.treeview.setIndentation(14)
        self.treeview.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.treeview.header().resizeSection(0, 380)
        # self.treeview.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        # self.treeview_model.signals.dataModelChanged.connect(self.load_data_from_treeview) #0716-
        self.treeview.setModel(self.treeview_model)
        self.treeview.setAlternatingRowColors(True)
        self.wTreeview.setContentsMargins(0, 0, 0, 0)
        self.btnCollapseAll = QPushButton('Collapse All')
        self.btnCollapseAll.setToolTip('Collapse all tree nodes')
        self.btnCollapseAll.setFixedSize(80, 18)
        self.btnCollapseAll.clicked.connect(self.treeview.collapseAll)
        self.btnExpandAll = QPushButton('Expand All')
        self.btnExpandAll.setToolTip('Expand all tree nodes')
        self.btnExpandAll.setFixedSize(80, 18)
        self.btnExpandAll.clicked.connect(self.treeview.expandAll)
        self.btnCurSection = QPushButton('Current Section')

        def fn():
            self.updateTreeWidget()
            self.treeview_model.jumpToLayer()

        self.btnCurSection.setToolTip('Jump to the data for current section and level')
        self.btnCurSection.setFixedSize(80, 18)
        self.btnCurSection.clicked.connect(fn)

        def fn():
            self.updateTreeWidget()
            self.treeview.collapseAll()

        self.btnReloadDataTree = QPushButton('Reload')
        self.btnReloadDataTree.setToolTip('Jump to the data for current section and level')
        self.btnReloadDataTree.setFixedSize(80, 18)
        self.btnReloadDataTree.clicked.connect(fn)

        def goToData():
            logger.info('')
            if self.le_tree_jumpToSec.text():
                section = int(self.le_tree_jumpToSec.text())
            else:
                section = self.dm.zpos
            # if (len(self.le_tree_jumpToScale.text()) > 0) and \
            #         (int(self.le_tree_jumpToScale.text()) in self.dm.lvls()):
            #     scale = get_scale_key(int(self.le_tree_jumpToScale.text()))
            # else:
            scale = self.dm.level
            self.updateTreeWidget()

            keys = ['stack', section, 'levels', scale]

            opt = self.combo_data_tree.currentText()
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
                    self.treeview_model.jumpToKey(keys=keys)

        # self.le_tree_jumpToScale = QLineEdit()
        # self.le_tree_jumpToScale.setFixedHeight(18)
        # self.le_tree_jumpToScale.setFixedWidth(30)
        # def fn():
        #     requested = int(self.le_tree_jumpToScale.text())
        #     if requested in self.dm.lvls():
        #         self.updateTreeWidget()
        #         self.treeview_model.jumpToScale(level=get_scale_key(requested))
        # self.le_tree_jumpToScale.returnPressed.connect(goToData)

        self.le_tree_jumpToSec = QLineEdit()
        self.le_tree_jumpToSec.setFixedHeight(18)
        self.le_tree_jumpToSec.setFixedWidth(30)
        self.le_tree_jumpToSec.returnPressed.connect(goToData)

        self.combo_data_tree = QComboBox()
        self.combo_data_tree.setFixedWidth(120)
        items = ['--', 'SWIM Settings', 'Method Results', 'Alignment History']
        self.combo_data_tree.addItems(items)

        self.btn_tree_go = QPushButton('Go')
        self.btn_tree_go.clicked.connect(goToData)
        self.btn_tree_go.setFixedSize(28, 18)

        self.jumpToTreeLab = QLabel('Jump To: ')
        self.jumpToTreeLab.setAlignment(Qt.AlignRight)
        self.jumpToTreeLab.setFixedHeight(18)

        hbl = HBL()
        hbl.setSpacing(4)
        hbl.addWidget(self.btnReloadDataTree)
        hbl.addWidget(self.btnCollapseAll)
        hbl.addWidget(self.btnExpandAll)
        hbl.addWidget(ExpandingWidget(self))
        hbl.addWidget(self.jumpToTreeLab)
        # hbl.addWidget(QLabel(' Level:'))
        # hbl.addWidget(self.le_tree_jumpToScale)
        hbl.addWidget(QLabel(' Section:'))
        hbl.addWidget(self.le_tree_jumpToSec)
        hbl.addWidget(self.combo_data_tree)
        hbl.addWidget(self.btn_tree_go)
        hbl.addWidget(self.btnCurSection)
        btns = QWidget()
        btns.setContentsMargins(2, 2, 2, 2)
        btns.setFixedHeight(24)
        btns.setLayout(hbl)

        self.treeHbl = HBL()
        self.treeHbl.setSpacing(0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setStyleSheet("""background-color: #161c20; color: #ede9e8;""")
        self.treeHbl.addWidget(lab)
        self.treeHbl.addWidget(VW(self.treeview, btns))
        self.wTreeview.setLayout(self.treeHbl)

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
        def update_dSnr_zpos():
            if self.dSnr_plot.isVisible():
                logger.critical('')
                self.dSnr_plot.updateLayerLinePos()
        # self.datamodel.signals.zposChanged.connect(update_dSnr_zpos)

        #Todo this results in far too many calls for certain widgets. Figure out something better.
        # def reinit_dSnr():
        #     if self.dSnr_plot.isVisible():
        #         logger.info('Signal received! Reinitializing SNR plot dock widget...')
        #         self.dSnr_plot.initSnrPlot()
        # self.datamodel.signals.dataChanged.connect(reinit_dSnr)
        self.dSnr_plot.setStyleSheet('background-color: #222222; font-weight: 600; font-size: 12px; color: #ede9e8;')
        self.parent.dwSnr.setWidget(self.dSnr_plot)



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
            font-size: 11px;
            border: 1px solid #ede9e8;
            background-color: #dadada;
        }
        QTabBar::tab:selected
        {
            font-weight: 600;
            color: #f3f6fb;
            background-color: #222222;
        }
        """)
        self.wTabs.setDocumentMode(True) #When this property is set the tab widget frame is not rendered.
        self.wTabs.setTabPosition(QTabWidget.South)
        self.wTabs.setFocusPolicy(Qt.NoFocus)
        self.wTabs.tabBar().setExpanding(True)
        self.wTabs.setTabsClosable(False)
        self.wTabs.setObjectName('project_tabs')

        # self.glNG = GL()
        # self.glNG.addWidget(self.webengine, 0, 0, 2, 2)
        # # self.glNG.addWidget(self.wNG, 0, 0, 1, 2)
        # self.glNG.addWidget(VW(self._vgap2, self.toolbarNg), 0, 0, 1, 2)
        # self.glNG.setRowStretch(0,0)
        # self.glNG.setRowStretch(1,9)

        self.vblNG = VBL()
        self.vblNG.addWidget(self.toolbarNg)
        self.vblNG.addWidget(self.webengine)

        self.wNG = QWidget()
        self.wNG.setLayout(self.vblNG)

        self.wTabs.addTab(self.wNG, 'View Alignment')
        self.wTabs.addTab(self.wEditAlignment, 'Edit Alignment')
        self.wTabs.addTab(self.wSNR, ' All SNR Plots ')
        self.wTabs.addTab(self.wTable, ' Table ')
        self.wTabs.addTab(self.wTreeview, ' JSON ')

        vbl = VBL()
        vbl.setSpacing(0)
        vbl.addWidget(self.wTabs)
        # self.wTabs.setCornerWidget(self.warning_data)
        # vbl.addWidget(self.warning_data)
        self.setLayout(vbl)

    def initShader(self):

        def resetBrightessAndContrast():
            reset_val = 0.0
            self.dm.brightness = reset_val
            self.dm.contrast = reset_val
            self.brightnessSlider.setValue(int(self.dm.brightness))
            self.contrastSlider.setValue(int(self.dm.contrast))
            if self.wTabs.currentIndex() == 0:
                cfg.emViewer.set_brightness()
                cfg.emViewer.set_contrast()
            elif self.wTabs.currentIndex() == 1:
                self.editorViewer.set_brightness()
                self.editorViewer.set_contrast()

        self.bResetShaders = QPushButton('Reset')
        self.bResetShaders.setFixedSize(QSize(40, 15))
        self.bResetShaders.clicked.connect(resetBrightessAndContrast)

        # self._btn_volumeRendering = QPushButton('Volume')
        # self._btn_volumeRendering.setFixedSize(QSize(58,20))
        # self._btn_volumeRendering.clicked.connect(self.fn_volume_rendering)
        # self.shaderSideButtons = HW(self.bResetShaders, self._btn_volumeRendering)
        self.shaderSideButtons = HW(self.bResetShaders)

        self.brightnessLE = QLineEdit()
        self.brightnessLE.setAlignment(Qt.AlignCenter)
        self.brightnessLE.setText('%d' % self.dm.brightness)
        self.brightnessLE.setValidator(QIntValidator(-100, 100))
        self.brightnessLE.setFixedSize(QSize(38,15))
        self.brightnessLE.textEdited.connect(
            lambda: self.brightnessSlider.setValue(int(self.brightnessLE.text())))
        self.brightnessLE.textEdited.connect(self.fn_brightness_control)
        self.brightnessSlider = QSlider(Qt.Orientation.Horizontal, self)
        # self.brightnessSlider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.brightnessSlider.setFixedWidth(150)
        self.brightnessSlider.setMouseTracking(False)
        self.brightnessSlider.setFocusPolicy(Qt.NoFocus)
        self.brightnessSlider.setRange(-100, 100)
        self.brightnessSlider.valueChanged.connect(self.fn_brightness_control)
        self.brightnessSlider.valueChanged.connect(
            lambda: self.brightnessLE.setText('%d' % self.brightnessSlider.value()))
        lab = QLabel('  Brightness  ')
        lab.setStyleSheet("color: #f3f6fb; font-size: 10px; background-color: rgba(0, 0, 0, 0.5); border-radius: 4px;")
        # lab.setStyleSheet("color: #FFFF66; font-size: 9px;")
        self.brightnessWidget = HW(lab, self.brightnessSlider, self.brightnessLE)
        # self.brightnessWidget.layout.setAlignment(Qt.AlignCenter)
        self.brightnessWidget.layout.setSpacing(4)

        self.contrastLE = QLineEdit()
        self.contrastLE.setAlignment(Qt.AlignCenter)
        self.contrastLE.setText('%d' % self.dm.contrast)
        self.contrastLE.setValidator(QIntValidator(-100, 100))
        self.contrastLE.setFixedSize(QSize(38, 15))
        self.contrastLE.textEdited.connect(
            lambda: self.contrastSlider.setValue(int(self.contrastLE.text())))
        self.contrastLE.textEdited.connect(self.fn_contrast_control)
        self.contrastSlider = QSlider(Qt.Orientation.Horizontal, self)
        # self.contrastSlider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.contrastSlider.setFixedWidth(150)
        self.contrastSlider.setMouseTracking(False)
        self.contrastSlider.setFocusPolicy(Qt.NoFocus)
        self.contrastSlider.setRange(-100, 100)
        self.contrastSlider.valueChanged.connect(self.fn_contrast_control)
        self.contrastSlider.valueChanged.connect(
            lambda: self.contrastLE.setText('%d' % self.contrastSlider.value()))
        lab = QLabel('  Contrast  ')
        lab.setStyleSheet("color: #f3f6fb; font-size: 10px; background-color: rgba(0, 0, 0, 0.5); border-radius: 4px;")
        # lab.setStyleSheet("color: #FFFF66; font-size: 9px;")
        self.contrastWidget = HW(lab, self.contrastSlider, self.contrastLE)
        # self.contrastWidget.layout.setAlignment(Qt.AlignCenter)
        self.contrastWidget.layout.setSpacing(4)

        self.bcWidget = HW(self.brightnessWidget, self.contrastWidget, self.shaderSideButtons)
        self.bcWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.bcWidget.layout.setSpacing(4)


    def fn_brightness_control(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            self.dm.brightness = self.brightnessSlider.value() / 100
            if self.wTabs.currentIndex() == 0:
                cfg.emViewer.set_brightness()
            elif self.wTabs.currentIndex() == 1:
                self.editorViewer.set_brightness()

    def fn_contrast_control(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            self.dm.contrast = self.contrastSlider.value() / 100
            if self.wTabs.currentIndex() == 0:
                cfg.emViewer.set_contrast()
            elif self.wTabs.currentIndex() == 1:
                self.editorViewer.set_contrast()

    # def fn_shader_control(self):
    #     logger.info('')
    #     logger.info(f'range: {self.normalizedSlider.getRange()}')
    #     self.dm.set_normalize(self.normalizedSlider.getRange())
    #     state = copy.deepcopy(cfg.emViewer.state)
    #     for layer in state.layers:
    #         layer.shaderControls['normalized'].range = np.array(self.dm.normalize())
    #     # state.layers[0].shader_controls['normalized'] = {'range': np.array([20,50])}
    #     cfg.emViewer.set_state(state)

    def fn_volume_rendering(self):
        logger.info('')
        state = copy.deepcopy(cfg.emViewer.state)
        state.showSlices = False
        cfg.emViewer.set_state(state)


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


class VerticalLabel(QLabel):

    def __init__(self, text, bg_color=None, font_color=None, font_size=None, *args):
        QLabel.__init__(self, text, *args)

        self.text = text
        font = QFont()
        font.setBold(True)
        font.setPixelSize(11)
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

    def setText(self, p_str):
        self.text = p_str

    def paintEvent(self, event):
        p = QPainter(self)
        p.rotate(-90)
        rgn = QRect(-self.height(), 0, self.height(), self.width())
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter
        # align  = Qt.AlignmentFlag.AlignCenter
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.hint = p.drawText(rgn, align, self.text)
        p.end()
        self.setMaximumWidth(self.hint.height())
        self.setMinimumHeight(self.hint.width())

    def sizeHint(self):
        if hasattr(self, 'hint'):
            return QSize(self.hint.height(), self.hint.width() + 10)
        else:
            return QSize(10, 48)

    def minimumSizeHint(self):
        size = QLabel.minimumSizeHint(self)
        return QSize(size.height(), size.width())


class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


class WebEngine(QWebEngineView):

    def __init__(self, ID='webengine'):
        QWebEngineView.__init__(self)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)

        # self.widget_id = id(self.children()[2])
        # self.inFocus = Signal(str)
        # self.installEventFilter(self)

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
        # self.label.setStyleSheet("QLabel { background: none; font-size: 9px; color: #a30000; font-weight: 600;"
        #                          "border-radius: 4px; font-family: Tahoma, sans-serif; padding: 4px; } ")
        self.label.setStyleSheet("QLabel { background: none; font-size: 9px; color: #a30000; font-weight: 600;"
                                 "padding: 0px; } ")
        self.label.setWordWrap(True)
        # self.setFixedHeight(16)
        self.layout = HBL()
        self.layout.setSpacing(4)
        # self.layout.setAlignment(Qt.AlignBottom)
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
            self.setStyleSheet(
                """background-color: #339933; 
                color: #ede9e8; 
                font-size: 10px; 
                border: 1px solid #ede9e8; 
                font-weight: 600;""")
        else:
            self.setStyleSheet(
                """background-color: #222222; 
                color: #ede9e8; 
                font-size: 10px; 
                border: 1px solid #ede9e8; 
                font-weight: 600;""")

    def isChecked(self):
        return self.isChecked


# class NgClickLabel(QLabel):
#     clicked = Signal()
#
#     def __init__(self, parent, **kwargs):
#         super().__init__(parent, **kwargs)
#         # super().__init__(parent)
#         self.setStyleSheet('color: #f3f6fb;')
#         # self.isClicked = False
#         self.isClicked = False
#
#     def mousePressEvent(self, ev):
#         self.isClicked = not self.isClicked
#         self.clicked.emit()


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
        self.setStyleSheet('font-weight: 600;')


def setWebengineProperties(webengine):
    webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)


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
    pt = ProjectTab()
    main_window.setCentralWidget(pt)
    main_window.show()
    sys.exit(app.exec_())