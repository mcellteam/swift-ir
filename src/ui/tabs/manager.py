#!/usr/bin/env python3

import copy
import inspect
import json
import logging
import os
import shutil
import subprocess as sp
import textwrap
import time
import uuid
from math import floor
from datetime import datetime
from glob import glob
from pathlib import Path
from pprint import pformat

import numpy as np
import qtawesome as qta
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import *

import src.config as cfg
from src.models.data import DataModel
from src.utils.funcs_image import ImageSize
from src.utils.helpers import print_exception, natural_sort, is_tacc, is_joel, hotkey
from src.ui.dialogs.importimages import ImportImagesDialog
from src.ui.views.filebrowser import FileBrowser
from src.ui.layouts.layouts import HBL, VBL, HW, VW, HSplitter
from src.ui.widgets.vertlabel import VerticalLabel
from src.ui.tabs.zarr import ZarrTab
from src.ui.tabs.project import AlignmentTab
from src.viewers.viewerfactory import PMViewer
from src.utils.readers import read
from src.utils.writers import write
from src.core.files import DirectoryStructure, DirectoryWatcher


__all__ = ['ManagerTab']

logger = logging.getLogger(__name__)

DEV = is_joel()

class ManagerTab(QWidget):

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        self.setMinimumHeight(100)
        self.filebrowser = FileBrowser(parent=self)
        self.filebrowser.setContentsMargins(2,2,2,2)
        self.dm = None
        self._level = None
        self._watchImages = DirectoryWatcher(suffixes=['.emstack', '.images'], preferences=cfg.preferences,
                                             key='images_search_paths')
        self._watchImages.fsChanged.connect(self.updateCombos)
        self._watchAlignments = DirectoryWatcher(suffixes=['.alignment', '.align'], preferences=cfg.preferences, key='alignments_search_paths')
        self._watchAlignments.fsChanged.connect(self.loadAlignmentCombo)
        # self._fsWatcher = FsWatcher(extension='.align')
        self.filebrowser.navigateTo(os.path.expanduser('~'))
        self._images_info = {}
        # self._selected_series = None #Todo
        # self._selected_alignment = None #Todo
        self.setAttribute(Qt.WA_TranslucentBackground)


        self._updateWatchPaths()
        self.initUI()
        self._NEW_IMAGES_PATHS = []
        # self.installEventFilter(self)

        self.filebrowser.setRootLastKnownRoot()

        self.resetView()
        # self.refresh()

        self._selecting_emstack = False

        self.updateCombos()

        self.webengine0.setFocus()



    # def onClipboardChanged(self):
    #     # print('Clipboard changed!')
    #     buffer = QApplication.clipboard().text()
    #     tip = 'Your Clipboard:\n' + '\n'.join(textwrap.wrap(buffer[0:512], width=35)) #set limit on length of tooltip string
    #     # print('\n' + tip)
    #     self._buttonBrowserPaste.setToolTip(tip)

    def onChanged(self, path):
        self.pathChanged.emit(path)


    def initUI(self):

        # User Files Widget

        # self.bPlusImages = HoverButton('Import')
        self.bPlusImages = QPushButton()
        self.bPlusImages.setFixedSize(QSize(18, 18))
        self.bPlusImages.setIconSize(QSize(13, 13))
        self.bPlusImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.bPlusImages.setToolTip("Create Images (.emstack)")
        # self.bPlusImages.setIcon(qta.icon('fa5s.images', color='#ede9e8'))
        # self.bPlusImages.setIcon(qta.icon('fa5s.images'))
        self.bPlusImages.setIcon(qta.icon('fa.plus'))
        self.bPlusImages.clicked.connect(self.onPlusEmstack)

        # self.bMinusAlignment = HoverButton('Delete')
        self.bMinusImages = QPushButton()
        self.bMinusImages.setFixedSize(QSize(18, 18))
        self.bMinusImages.setIconSize(QSize(13, 13))
        self.bMinusImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.bMinusImages.setToolTip("Delete Images (.emstack)")
        self.bMinusImages.setToolTipDuration(-1)
        # self.bMinusImages.setIcon(qta.icon('fa.minus', color='#ede9e8'))
        self.bMinusImages.setIcon(qta.icon('fa.minus'))
        self.bMinusImages.clicked.connect(self.onMinusImages)

        self.comboLevel = QComboBox()
        self.comboLevel.setToolTip("Scale Level")
        self.comboLevel.setFixedSize(QSize(44, 18))
        self.comboLevel.setCursor(QCursor(Qt.PointingHandCursor))
        self.comboLevel.setFocusPolicy(Qt.NoFocus)
        self.comboLevel.currentIndexChanged.connect(self.onComboLevel)

        self.comboTransformed = QComboBox()
        self.comboTransformed.setFixedHeight(16)
        # self.comboTransformed.setStyleSheet("""QComboBox QAbstractItemView {
        #     border: 2px solid darkgray;
        #     selection-background-color: lightgray;
        # }""")
        tip = 'Create a new alignment of the selected EM stack in your alignments content root'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.comboTransformed.setToolTip(tip)
        # self.comboTransformed.setPlaceholderText("Select Alignment...")
        self.comboTransformed.setPlaceholderText("")
        self.comboTransformed.setFocusPolicy(Qt.NoFocus)
        # self.comboTransformed.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.comboTransformed.setEditable(True)
        # self.comboTransformed.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.comboTransformed.setCursor(QCursor(Qt.PointingHandCursor))
        self.comboTransformed.textActivated.connect(self.onComboTransformed)
        # self.comboTransformed.addItems(["None"])

        self.comboImages = QComboBox()
        self.comboImages.setFixedHeight(16)
        tip = 'Select files to create a new EM stack (.emstack) in your images content root'
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.comboImages.setToolTip(tip)
        self.comboImages.setPlaceholderText("Select EM Stack (.emstack)...")
        self.comboImages.setFocusPolicy(Qt.NoFocus)
        self.comboImages.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.comboImages.setEditable(True)
        # self.comboImages.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.comboImages.setCursor(QCursor(Qt.PointingHandCursor))
        # self.updateCombos()
        self.comboImages.textActivated.connect(self.onComboSelectEmstack)

        tip = f"Create Alignment (.align)"
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        # self.bPlusAlignment = HoverButton('New')
        self.bPlusAlignment = QPushButton()
        self.bPlusAlignment.setFixedSize(QSize(18, 18))
        self.bPlusAlignment.setIconSize(QSize(13, 13))
        self.bPlusAlignment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bPlusAlignment.setToolTip(tip)
        self.bPlusAlignment.setToolTipDuration(-1)
        # self.bPlusAlignment.setIcon(qta.icon('fa.plus', color='#ede9e8'))
        self.bPlusAlignment.setIcon(qta.icon('fa.plus'))
        self.bPlusAlignment.clicked.connect(self.onPlusAlignment)

        # self.bMinusAlignment = HoverButton('Delete')
        tip = "Delete alignment"
        self.bMinusAlignment = QPushButton()
        self.bMinusAlignment.setFixedSize(QSize(18, 18))
        self.bMinusAlignment.setIconSize(QSize(13, 13))
        self.bMinusAlignment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bMinusAlignment.setToolTip(tip)
        self.bMinusAlignment.setToolTipDuration(-1)
        # self.bMinusAlignment.setIcon(qta.icon('fa.minus', color='#ede9e8'))
        self.bMinusAlignment.setIcon(qta.icon('fa.minus'))
        self.bMinusAlignment.clicked.connect(self.onMinusAlignment)

        # self.bOpen = HoverButton('Open')
        self.bOpen = QPushButton()
        self.bOpen.setFixedSize(QSize(18, 18))
        self.bOpen.setIconSize(QSize(13, 13))
        self.bOpen.setCursor(QCursor(Qt.PointingHandCursor))
        self.bOpen.setToolTip("Open alignment")
        self.bOpen.setToolTipDuration(-1)
        self.bOpen.setIcon(qta.icon('fa.folder-open'))
        self.bOpen.clicked.connect(self.onOpenAlignment)

        self.wSelectEmstack = HW(self.comboImages, self.comboLevel, self.bPlusImages, self.bMinusImages)
        self.wSelectEmstack.setFixedHeight(20)
        self.wSelectAlignment = HW(self.comboTransformed, self.bOpen, self.bPlusAlignment, self.bMinusAlignment)
        self.wSelectAlignment.setFixedHeight(20)

        # self.toolbar = QToolBar()
        # self.toolbar.addWidget(VW(self.wSelectEmstack, self.wSelectAlignment))



        self.webengine0 = WebEngine(ID='emstack-viewer')
        self.wrapper0 = VW(self.webengine0)
        # self.wrapper0.setStyleSheet("border-radius: 4px; background-color: #222222;")

        self.webengine1 = WebEngine(ID='align-viewer')
        # self.webengine1._load()
        self.wrapper1 = VW(self.webengine1)
        # self.wrapper1.setStyleSheet("border-radius: 4px; background-color: #222222; padding: 20px;")

        self.leNameAlignment = QLineEdit()
        self.leNameAlignment.setFixedHeight(18)
        self.leNameAlignment.returnPressed.connect(self.createAlignment)

        self.leNameAlignment.setReadOnly(False)
        self.leNameAlignment.setPlaceholderText("<New alignment name>")
        f = QFont()
        f.setItalic(True)
        self.leNameAlignment.setFont(f)
        def onTextChanged():
            self.bConfirmNewAlignment.setEnabled(bool(self.leNameAlignment.text()))
            f = QFont()
            f.setItalic(not len(self.leNameAlignment.text()))
            self.leNameAlignment.setFont(f)
        self.leNameAlignment.textEdited.connect(onTextChanged)

        self.bConfirmNewAlignment = QPushButton('Create')
        self.bConfirmNewAlignment.setFixedSize(QSize(44, 18))
        self.bConfirmNewAlignment.setAutoFillBackground(False)
        self.bConfirmNewAlignment.setFocusPolicy(Qt.NoFocus)
        self.bConfirmNewAlignment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bConfirmNewAlignment.clicked.connect(self.createAlignment)

        self.bCancelNewAligment = QPushButton()
        self.bCancelNewAligment.setAutoFillBackground(False)
        self.bCancelNewAligment.setIcon(qta.icon('fa.close'))
        self.bCancelNewAligment.setFixedSize(QSize(18, 18))
        self.bCancelNewAligment.setIconSize(QSize(12,12))
        self.bCancelNewAligment.setFocusPolicy(Qt.NoFocus)
        self.bCancelNewAligment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCancelNewAligment.clicked.connect(lambda: self.wNameAlignment.hide())
        self.bCancelNewAligment.clicked.connect(lambda: self.wSelectAlignment.show())
        self.bCancelNewAligment.clicked.connect(lambda: self.webengine0.setFocus())
        self.bCancelNewAligment.clicked.connect(lambda: self.leNameAlignment.clear())

        newAlignmentLab = QLabel("Alignment Name:")
        self.wNameAlignment = HW(self.leNameAlignment, self.bConfirmNewAlignment, self.bCancelNewAligment)
        self.wNameAlignment.setFixedHeight(18)
        self.wNameAlignment.layout.setSpacing(0)
        newAlignmentLab.setAutoFillBackground(True)
        self.wNameAlignment.hide()

        '''Step 1/3'''
        self.name_dialog = QFileDialog()
        # self.name_dialog.setContentsMargins(2,2,2,2)
        self.name_dialog.setWindowFlags(Qt.FramelessWindowHint)
        self.name_dialog.setOption(QFileDialog.DontUseNativeDialog)
        self.name_dialog.layout().setContentsMargins(2,2,2,2)
        self.name_dialog.layout().setHorizontalSpacing(2)
        self.name_dialog.layout().setVerticalSpacing(2)
        self.name_dialog.setNameFilter("Text Files (*.swiftir)")
        self.name_dialog.setLabelText(QFileDialog.Accept, "Create")
        self.name_dialog.setViewMode(QFileDialog.Detail)
        self.name_dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.name_dialog.setModal(True)
        # self.name_dialog.setFilter(QDir.AllEntries | QDir.Hidden)

        urls = self.name_dialog.sidebarUrls()

        corral_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'

        if is_tacc():
            urls.append(QUrl.fromLocalFile(os.getenv('SCRATCH')))
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile(os.getenv('HOME')))
            urls.append(QUrl.fromLocalFile(corral_dir))

        else:
            urls.append(QUrl.fromLocalFile(QDir.homePath()))
            urls.append(QUrl.fromLocalFile('/tmp'))
            if os.path.exists('/Volumes'):
                urls.append(QUrl.fromLocalFile('/Volumes'))
            if is_joel():
                if os.path.exists('/Volumes/3dem_data'):
                    urls.append(QUrl.fromLocalFile('/Volumes/3dem_data'))

        self.name_dialog.setSidebarUrls(urls)

        places = getSideBarPlacesProjectName()
        # print(str(places))

        sidebar = self.name_dialog.findChild(QListView, "sidebar")
        delegate = StyledItemDelegate(sidebar)
        delegate.mapping = places
        sidebar.setItemDelegate(delegate)

        self.iid_dialog = ImportImagesDialog()
        # self.iid_dialog.filesSelected.connect(self.updateImportImagesUI)
        self.iid_dialog.setAutoFillBackground(True)
        self.iid_dialog.hide()

        self.leNameImages = QLineEdit()
        # def fn():
        #     cur = Path(self.leNameImages.text())
        #     # od = Path(cfg.preferences['images_root'])
        #     # if (Path(od) / self.leNameImages.text()).exists()
        #     if cur.suffix != '.emstack':
        #         self.leNameImages.setText(str(cur.w))
        # self.leNameImages.textChanged.connect(fn)
        f = QFont()
        f.setItalic(True)
        self.leNameImages.setFont(f)
        self.placeholderText = '<short, descriptive name>'
        self.leNameImages.setPlaceholderText(self.placeholderText)
        self.leNameImages.setFixedHeight(18)
        self.leNameImages.setReadOnly(False)
        pal = self.leNameImages.palette()
        pal.setColor(QPalette.PlaceholderText, QColor("#dadada"))
        self.leNameImages.setPalette(pal)
        self.leNameImages.textEdited.connect(self.updateImportImagesUI)

        # self.bSelect = QPushButton("Select Images (TIFF)")
        self.bSelect = QPushButton("Select Images")
        # self.bSelect.setCheckable(True)
        self.bSelect.setCursor(QCursor(Qt.PointingHandCursor))
        self.bSelect.clicked.connect(self.selectImages)

        self.bCancel = QPushButton()
        self.bCancel.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCancel.setFixedSize(QSize(18, 18))
        self.bCancel.setIcon(qta.icon('fa.close', color='#161c20'))
        self.bCancel.clicked.connect(lambda: setattr(self, '_NEW_IMAGES_PATHS', []))
        self.bCancel.clicked.connect(lambda: self.leNameImages.clear())
        self.bCancel.clicked.connect(lambda: self.gbCreateImages.hide())
        self.bCancel.clicked.connect(lambda: self.iid_dialog.hide())
        self.bCancel.clicked.connect(lambda: self.vwEmStackProperties.hide())
        self.bCancel.clicked.connect(lambda: self.wSelectEmstack.show())


        self.bCreateImages = QPushButton("Create")
        self.bCreateImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCreateImages.clicked.connect(self.confirmCreateImages)
        self.bCreateImages.setEnabled(False)

        # self.wNameEmStack = HW(QLabel('Images Name:'), self.leNameImages, self.bSelect, self.bCreateImages, self.bCancel)
        self.wNameEmStack = VW(BoldLabel('Step 1:'), HW(QLabel('Images Name:'), self.leNameImages, self.bSelect, self.bCancel))
        # self.wNameEmStack.setStyleSheet("QLabel {color: #f3f6fb;} ")
        self.wNameEmStack.layout.setSpacing(2)
        self.wNameEmStack.layout.setContentsMargins(0, 0, 0, 0)

        bs = [self.bSelect, self.bCreateImages]
        for b in bs:
            b.setFixedSize(QSize(78,18))

        self.wEmStackProperties = ImagesConfig(parent=self)
        self.wEmStackProperties.cbCalGrid.toggled.connect(self.updateConfirmAlignmentLabels)
        # self.wEmStackProperties.hide()
        self.wEmStackProperties.layout().setSpacing(16)

        self.labConfirmReady = QLabel()
        # self.labConfirmReady.setStyleSheet("color: #339933;")
        # self.labConfirmReady.hide()
        self.labImgCount = QLabel()
        self.labImgCount.setStyleSheet("font-weight: 600; color: #339933;")
        # self.labImgCount.hide()

        hw = HW(ExpandingHWidget(self), self.labConfirmReady, self.labImgCount, self.bCreateImages)
        hw.layout.setSpacing(6)
        self.vwEmStackProperties = VW(BoldLabel('Step 2:'), self.wEmStackProperties, hw)
        self.vwEmStackProperties.hide()


        # self.wMiddle = HW(ExpandingHWidget(self), self.labImgCount)
        # vbl = VBL(self.wNameEmStack, self.wMiddle, self.wEmStackProperties)
        # vbl = VBL(self.wNameEmStack, self.wMiddle, self.vwEmStackProperties)
        vbl = VBL(self.wNameEmStack, self.vwEmStackProperties)
        # vbl.setSpacing(4)
        self.gbCreateImages = QGroupBox()
        self.gbCreateImages.setLayout(vbl)
        self.gbCreateImages.hide()

        self.wOverlay = VW(self.iid_dialog)
        self.wOverlay.layout.setContentsMargins(18, 12, 18, 18)
        self.wOverlay.layout.setSpacing(4)
        self.wOverlay.layout.setAlignment(Qt.AlignTop)
        self.wOverlay.adjustSize()
        self.wOverlay.layout.setAlignment(Qt.AlignTop)

        self.labFound0 = BoldLabel('0 Found')
        self.labFound0.setAlignment(Qt.AlignRight)
        self.labFound0.setFixedHeight(10)
        self.gl0 = QGridLayout()
        self.gl0.setContentsMargins(0, 0, 0, 0)
        self.gl0.addWidget(self.wrapper0, 0, 0, 4, 3)
        self.gl0.addWidget(self.wOverlay, 0, 0, 1, 3)
        self.gl0.setRowStretch(1, 1)
        w = QWidget()
        w.setContentsMargins(0, 0, 0, 0)
        w.setLayout(self.gl0)
        self.gbWebengine0 = GroupBox('EM Image Stacks (.emstack)')
        vl = VBL(self.labFound0, self.wSelectEmstack, self.gbCreateImages, w)
        self.gbWebengine0.setLayout(vl)
        self.gbWebengine0.setContentsMargins(0, 0, 0, 0)

        self.labFound1 = BoldLabel('0 Found')
        self.labFound1.setAlignment(Qt.AlignRight)
        self.labFound1.setFixedHeight(10)
        self.gl1 = QGridLayout()
        self.gl1.setContentsMargins(0, 0, 0, 0)
        self.gl1.addWidget(self.wrapper1, 0, 0, 4, 3)
        self.gl1.setRowStretch(1, 1)
        w = QWidget()
        w.setContentsMargins(0, 0, 0, 0)
        w.setLayout(self.gl1)
        self.gbWebengine1 = GroupBox('Alignments (.align)')
        vl = VBL(self.labFound1, self.wSelectAlignment, self.wNameAlignment, w)
        self.gbWebengine1.setLayout(vl)
        self.gbWebengine1.setContentsMargins(0, 0, 0, 0)


        self.vsplitter = QSplitter(Qt.Orientation.Vertical)
        self.vsplitter.setOpaqueResize(False)
        self.vsplitter.addWidget(self.gbWebengine0)
        self.vsplitter.addWidget(self.gbWebengine1)
        self.vsplitter.setStretchFactor(0, 1)
        self.vsplitter.setStretchFactor(1, 1)
        self.vsplitter.setCollapsible(0, False)
        self.vsplitter.setCollapsible(1, False)

        # self.vlPM = VerticalLabel('Alignment Manager')
        # self.wManager = HW(self.vlPM, self.vsplitter)

        self.hsplitter = HSplitter()
        self.hsplitter.setOpaqueResize(False)
        self.hsplitter.addWidget(self.vsplitter)
        self.hsplitter.addWidget(self.filebrowser)
        self.hsplitter.setSizes([int(cfg.WIDTH * (8 / 10)), int(cfg.WIDTH * (2 / 10))])
        self.hsplitter.setStretchFactor(0, 1)
        self.hsplitter.setStretchFactor(1, 1)
        self.hsplitter.setCollapsible(0, False)
        self.hsplitter.setCollapsible(1, False)

        self.vbl_main = VBL()
        self.vbl_main.setSpacing(0)
        self._vw = VW()

        self.vbl_main.addWidget(self.hsplitter)

        self.setLayout(self.vbl_main)

        # if self.comboImages.currentText():
        #     self.wSelectAlignment.setVisible(True)


    def resetView(self, init_viewer=False):
        logger.info('')
        self.setUpdatesEnabled(False)
        self.leNameImages.setStyleSheet("border-color: #339933; border-width: 2px;")
        self.bSelect.setStyleSheet("background-color: #339933; color: #f3f6fb; border-color: #f3f6fb;")
        self.bCreateImages.setStyleSheet("")
        self.gbCreateImages.hide()
        self.labImgCount.hide()
        self.iid_dialog.hide()
        self.wNameAlignment.hide()
        self.wSelectAlignment.show()
        self.wSelectEmstack.show()
        self.bPlusAlignment.setEnabled(True)
        self.leNameAlignment.clear()
        self.leNameImages.clear()
        setattr(self, '_NEW_IMAGES_PATHS', [])
        self.webengine1.setnull() #1130

        if init_viewer:
            # self.updateCombos()
            self.initPMviewer()

        self.setUpdatesEnabled(True)


    def _getUUID(self, path):
        # uuid = ''
        if os.path.exists(path):
            data = read('json')(path) # returns None if not valid JSON
            if isinstance(data, dict):
                try:
                    uuid = data['info']['images_uuid']
                except KeyError:
                    uuid = data['info']['series_uuid']
                except json.decoder.JSONDecodeError:
                    self.parent.warn('JSON decoder error')
                else:
                    return uuid
            # return uuid


    def _getImagesName(self):
        return os.path.basename(self.comboImages.currentText())


    def _getImagesUUID(self, p):
        path = Path(p) / 'info.json'

        if path.exists():
            try:
                return read('json')(path)['uuid']
            except:
                logger.warning(f'Unable to read UUID from {path}')
                return None



    #importseries
    def confirmCreateImages(self):
        logger.info("")
        self.bCreateImages.setEnabled(False)
        self.bCreateImages.setStyleSheet("")
        self.bSelect.setStyleSheet("")

        name = self.leNameImages.text()
        name.replace(' ', '_')
        if not name.endswith('.emstack'):
            name += '.emstack'

        out = os.path.join(cfg.preferences['images_root'], name)
        im_siz = ImageSize(self._NEW_IMAGES_PATHS[0])
        im_config_opts = self.wEmStackProperties.getSettings(im_siz=im_siz)
        logpath = os.path.join(out, 'logs')
        os.makedirs(logpath, exist_ok=True)
        # open(os.file_path.join(logpath, 'exceptions.log'), 'a').close()

        cal_grid_path = None
        if im_config_opts['has_cal_grid']:
            cal_grid_path = self._NEW_IMAGES_PATHS[0]
            cal_grid_name = os.path.basename(cal_grid_path)
            self._NEW_IMAGES_PATHS = self._NEW_IMAGES_PATHS[1:]
            self.parent.tell(f"Copying calibration grid image '{cal_grid_name}'")
            shutil.copyfile(cal_grid_path, os.path.join(out, cal_grid_name))
            #Todo create multiscale Zarr

        src = os.path.dirname(self._NEW_IMAGES_PATHS[0])
        self.parent.tell(f'Importing {len(self._NEW_IMAGES_PATHS)} Images...')
        scales_str = self.wEmStackProperties.scales_input.text().strip()
        scale_vals = list(map(int,scales_str.split(' ')))
        tiff_path = os.path.join(out, 'tiff')
        zarr_path = os.path.join(out, 'zarr')
        thumbs_path = os.path.join(out, 'thumbs')

        for sv in scale_vals:
            self.parent.tell('Making directory structure for level %d...' % sv)
            os.makedirs(os.path.join(tiff_path,   's%d' % sv), exist_ok=True)
            os.makedirs(os.path.join(zarr_path,   's%d' % sv), exist_ok=True)
            os.makedirs(os.path.join(thumbs_path, 's%d' % sv), exist_ok=True)

        logger.info(f"# Imported: {len(self._NEW_IMAGES_PATHS)}")

        count = len(self._NEW_IMAGES_PATHS)
        level_keys = natural_sort(['s%d' % v for v in scale_vals])
        series_name = os.path.basename(out)
        logger.critical(f"Resolution levels: {level_keys}")

        im_sample = self._NEW_IMAGES_PATHS[0]
        try:
            tiffinfo = read('tiffinfo')(im_sample)
            write('txt')(Path(out) / 'tiffinfo.txt', tiffinfo)
        except:
            logger.warning('Unable to read or write tiffinfo to file.')
        try:
            tifftags = read('tifftags')(im_sample)
            write('json')(Path(out) / 'tifftags.json', tifftags)
        except:
            logger.warning('Unable to read or write TIFF tags to file')

        opts = {}
        opts.update(
            name=series_name,
            uuid=str(uuid.uuid4()),
            created=datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
            scale_factors=scale_vals,
            levels=level_keys,
            count=count,
            cal_grid={
                'has': im_config_opts['has_cal_grid'],
                'file_path': cal_grid_path,
            },
            paths=self._NEW_IMAGES_PATHS,
            size_zyx={},
            size_xy={},
        )
        opts.update(im_config_opts)
        logger.info(pformat(opts))

        full_scale_size = ImageSize(self._NEW_IMAGES_PATHS[0])
        for sv in scale_vals:
            key = 's%d' % sv
            siz = tuple((np.array(full_scale_size) / sv).astype(int).tolist())
            opts['size_zyx'][key] = (count, siz[1], siz[0])
            opts['size_xy'][key] = siz

        siz_x, siz_y = ImageSize(opts['paths'][1])
        sf = int(max(siz_x, siz_y) / cfg.TARGET_THUMBNAIL_SIZE)
        opts['thumbnail_scale_factor'] = sf
        p = os.path.join(out, 'info.json')
        write('json')(p, opts)
        self.update()
        # QApplication.processEvents()
        self.parent.autoscaleImages(src, out, opts)
        cfg.preferences['images_combo_text'] = out
        self.resetView(init_viewer=True)

    def createAlignment(self):
        logger.info('')
        self.bPlusAlignment.setEnabled(False)
        root = Path(cfg.preferences['alignments_root'])
        seriespath = Path(self.comboImages.currentText())
        usertext = self.leNameAlignment.text()
        newproject = (root / usertext).with_suffix('.align')
        newdir = (root / usertext).with_suffix('')
        info = seriespath / 'info.json'
        _err = 0
        _msg = None
        if not os.path.isdir(seriespath):
            _err = 1
            _msg = f"Image Series Not Found: {seriespath}.\nWere the images moved?"
        elif not info.exists():
            _err = 1
            _msg = f"Image Stack 'info.json' File Is Missing:\n{info}\nWas it moved?"
        elif os.path.exists(newproject):
            _err = 1
            _msg = f"A file with this name already exists: {newproject}"
        elif os.path.exists(newdir):
            _err = 1
            _msg = f"A directory with this name already exists: {newdir}"
        if _err:
            self.parent.warn(_msg)
            self.resetView()
        else:
            info = read('json')(info)
            self.dm = dm = DataModel(file_path=newproject, images_path=seriespath, init=True, images_info=info)
            DirectoryStructure(dm).initDirectory()
            AlignmentTab(self.parent, dm)
            dm.save(silently=True)
        self.bPlusAlignment.setEnabled(True)
        self.resetView()
        logger.info(f"<-- createAlignment")



    def initPMviewer(self, path=None):
        self.setUpdatesEnabled(False)
        self.loadLevelsCombo()
        level = self.comboLevel.currentText()

        path = Path(self.comboImages.currentText()) / 'zarr' / level

        try:
            resolution = self._images_info['resolution'][level]
        except:
            logger.warning(f'(hotfix) resolution could not be determined. Using default instead.')
            resolution = [8, 8, 50]

        try:
            self.viewer0 = PMViewer(
                parent=self,
                webengine=self.webengine0,
                path=path,
                res=resolution,
                extra_data={'name': 'viewer0', 'dm': None})
            self.viewer0.signals.arrowLeft.connect(self.parent.layer_left)
            self.viewer0.signals.arrowRight.connect(self.parent.layer_right)
            self.viewer0.signals.arrowUp.connect(self.parent.incrementZoomIn)
            self.viewer0.signals.arrowDown.connect(self.parent.incrementZoomOut)
        except:
            print_exception()

        try:
            # REQUIRES having dm
            self.viewer1 = PMViewer(
                parent=self,
                webengine=self.webengine1,
                path=path,
                res=resolution,
                extra_data={'name': 'viewer1', 'dm': None})
            self.viewer1.signals.arrowLeft.connect(self.parent.layer_left)
            self.viewer1.signals.arrowRight.connect(self.parent.layer_right)
            self.viewer1.signals.arrowUp.connect(self.parent.incrementZoomIn)
            self.viewer1.signals.arrowDown.connect(self.parent.incrementZoomOut)
        except:
            print_exception()

        self.updatePMViewers()
        self.setUpdatesEnabled(True)

    def updatePMViewers(self):
        logger.info('')
        try:
            self.setUpdatesEnabled(False)
            level = self.comboLevel.currentText()
            if self.comboImages.currentText():
                path = Path(self.comboImages.currentText()) / 'zarr' / level
                if path.exists():
                    self.viewer0.initViewer()
                    if self.comboTransformed.currentText():
                        self.viewer1.initViewer()
            self.setUpdatesEnabled(True)
        except:
            print_exception()



    def onPlusAlignment(self):
        logger.info('')
        if self.wNameAlignment.isVisible():
            self.wNameAlignment.hide()
            return
        if not os.path.isdir(self.comboImages.currentText()):
            self.parent.warn(f"'{self.comboImages.currentText()}' is not valid.")
            return
        self.wSelectAlignment.hide()
        self.wNameAlignment.show()
        self.leNameAlignment.setFocus()

    def onMinusAlignment(self):
        logger.info('')
        path = Path(self.comboTransformed.currentText())
        if path.suffix == '.align':
            del_path = path.with_suffix('')

            # if del_path.is_dir():
            logger.warning(f"Removing alignment dir '{del_path}'")
            reply = QMessageBox.question(self, "Quit", f"Delete this alignment?\n\n'{del_path}'",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.parent.tell(f'Running background process: removing {del_path}...')
                if path.exists():
                    try:
                        os.remove(path) #todo make this more robust/safe, check dir before deleting
                    except:
                        print_exception()
                if path.with_suffix('').exists():
                    try:
                        run_subprocess(["rm", "-rf", str(del_path)])
                        time.sleep(2)
                    except:
                        print_exception()

                # self.updateCombos()
                # self.initPMviewer()  #1118-
                self.resetView()
                # self.webengine1.setnull()

                self.parent.hud.done()
                self.parent.tell('The deletion process will continue running in the background.')
                self.resetView(init_viewer=True)
            else:
                self.parent.warn(f'Path not found: {del_path}')


    def onMinusImages(self):
        path = self.comboImages.currentText()
        if os.path.isdir(path):
            self.parent.tell(f'Running background process: removing {path}...')
            reply = QMessageBox.question(self, "Quit", f"Delete this images?\n\n'{path}'",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    if path.endswith('.emstack') or path.endswith('.images'):
                        self.parent.tell(f'Deleting EM stack {path}...')
                        run_subprocess(["rm", "-rf", path])
                        run_subprocess(["rm", "-rf", path])
                    else:
                        logger.warning(f"\n\nCANNOT REMOVE THIS PATH: {path}\n")
                except:
                    print_exception()
                else:
                    logger.info('Sleeping for 2 seconds...')
                    time.sleep(2)
                    self.parent.hud.done()
                    self.parent.tell('The deletion process will continue running in the background.')

                self.resetView(init_viewer=True)
        else:
            self.parent.warn(f"Images not found: {path}")

        self.resetView()


    def _updateWatchPaths(self):
        [self._watchImages.watch(sp) for sp in cfg.preferences['images_search_paths']]
        [self._watchAlignments.watch(sp) for sp in cfg.preferences['alignments_search_paths']]


    def updateCombos(self):
        '''Loading this combobox triggers the loading of the alignment and scales comboboxes'''
        caller = inspect.stack()[1].function
        # logger.critical(f"{caller}")
        shown = [self.comboImages.itemText(i) for i in range(self.comboImages.count())]
        known = self._watchImages.known
        if sorted(shown) == sorted(known):
            logger.info("null return")
            return
        self.comboImages.clear()
        self.comboImages.addItems(known)
        self.labFound0.setText(f"{len(known)} Found")
        mem = cfg.preferences['images_combo_text']
        if mem in known:
            self.comboImages.setCurrentText(mem)
            info_path = os.path.join(mem,'info.json')
            self._images_info = read('json')(info_path)
        _im_path = self.comboImages.currentText()
        _im_name = os.path.basename(_im_path)
        al_known = self._watchAlignments.known
        if os.path.exists(str(_im_path)):
            if len(al_known) == 0:
                self.comboTransformed.setPlaceholderText(f"No Alignments (.align) Found for '{_im_name}'")
            else:
                self.comboTransformed.setPlaceholderText(f"{len(al_known)} Alignments (.align) of '{_im_name}' Found")
        else:
            self.comboTransformed.setPlaceholderText("")

        self.loadLevelsCombo()
        self.loadAlignmentCombo()


    def loadAlignmentCombo(self):
        # logger.info('')
        self.comboTransformed.clear()
        if self.comboImages.currentText():
            cur_items = [self.comboTransformed.itemText(i) for i in range(self.comboTransformed.count())]
            if sorted(cur_items) != sorted(self._watchAlignments.known):
                _im_path = self.comboImages.currentText()
                _im_name = os.path.basename(_im_path)
                _uuid = self._getImagesUUID(_im_path)
                known = self._watchAlignments.known

                # valid = [p for p in known if self._getUUID(p) == _uuid]
                valid = []
                for p in known:
                    if self._getUUID(p) == _uuid:
                        valid.append(p)

                # self.comboTransformed.clear()
                self.comboTransformed.addItems(valid)
                self.labFound1.setText(f"{len(valid)} Found")
                mem = cfg.preferences['alignment_combo_text']
                if mem in valid:
                    self.comboTransformed.setCurrentText(mem)
                if os.path.exists(str(_im_path)):
                    if len(valid):
                        self.comboTransformed.setPlaceholderText(f"{len(valid)} Alignments (.align) of '{_im_name}' "
                                                                   f"Found")
                    else:
                        self.comboTransformed.setPlaceholderText(f"No Alignments (.align) of '{_im_name}' Found")
                else:
                    self.comboTransformed.setPlaceholderText("")


    def loadLevelsCombo(self):
        # logger.info('')
        self.comboLevel.clear()
        if self._images_info:
            if type(self._images_info) == dict:
                if 'levels' in self._images_info:
                    self.comboLevel.addItems(self._images_info['levels'])
                    self.comboLevel.setCurrentIndex(self.comboLevel.count() - 1)


    def onComboSelectEmstack(self):
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            self.webengine0.setnull()
            self.webengine1.setnull()
            if self.comboImages.currentText():
                path = self.comboImages.currentText()
                info_path = os.path.join(path, 'info.json')
                self._images_info = read('json')(info_path)
                self.resetView()
                cfg.preferences['images_combo_text'] = path
                try:
                    self.loadLevelsCombo() #Important load the scale levels combo before initializing viewers
                except:
                    print_exception()
                self.loadAlignmentCombo()
                self.updatePMViewers()

    def onComboTransformed(self):
        caller = inspect.stack()[1].function
        logger.critical(f"[{caller}]")
        if caller == 'main':
            try:
                self.dm = DataModel(data=read('json')(self.comboTransformed.currentText()), readonly=True)
            except:
                self.dm = None
                print_exception()

            self.wNameAlignment.hide()
            self.leNameAlignment.clear()
            if self.comboTransformed.currentText():
                self.viewer1.initViewer()


    def onComboLevel(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            self._level = self.comboLevel.currentText()
            self.updatePMViewers()

    # def onSelectAlignmentCombo(self):
    #     caller = inspect.stack()[1].function
    #     if caller == 'main':
    #         cfg.preferences['alignment_combo_text'] = self.comboTransformed.currentText()
    #         self.gbCreateImages.hide()
    #         self.webengine0.py.setFocus()

    def onOpenAlignment(self):
        logger.info('')
        p = Path(self.comboTransformed.currentText())
        if p.suffix == '.align':
            impath = Path(self.comboImages.currentText())
            self.openAlignment(file_path=p, images_path=impath)


    def openAlignment(self, file_path, images_path=None):
        if not file_path:
            file_path = Path(self.selectionReadout.text())
        if validate_zarr_selection(file_path):
            logger.info('Opening Zarr...')
            self.open_zarr_selected()
            return
        elif validate_project_selection(file_path):

            logger.info(f"\nfile_path       : {file_path}"
                        f"\nimages_location : {images_path}")

            if self.parent.isProjectOpen(file_path):
                logger.info(f"Project {file_path} is already open...")
                try:
                    self.parent.globTabs.setCurrentIndex(self.parent.getProjectIndex(file_path))
                except Exception as e:
                    logger.warning(f"Error. Reason: {e.__class__.__name__}")

                self.parent.warn(f'Project {file_path.name} is already open.')
                return

            self.parent.tell(f"Opening: {file_path}...")
            data = read('json')(file_path)
            dm = DataModel(
                data=data,
                file_path=file_path,
                images_path=images_path,
            )
            cfg.preferences['last_alignment_opened'] = dm.data_file_path
            self.parent.saveUserPreferences(silent=True)
            dm.save(silently=True)
            AlignmentTab(self.parent, dm)
        else:
            self.parent.warn("Invalid Path")


    def showMainUI(self):
        logger.info('')
        self.gbCreateImages.hide()
        self.vwEmStackProperties.hide()
        self.update()

    def onPlusEmstack(self):
        self.setUpdatesEnabled(False)
        isShown = self.gbCreateImages.isVisible()
        self.resetView()
        self.leNameImages.setStyleSheet(("border-color: #339933; border-width: 2px;", "border-color: #f3f6fb;")[bool(
            self.leNameImages.text(
        ))])
        self.gbCreateImages.setVisible(not isShown)
        self.wSelectEmstack.hide()
        if self.gbCreateImages.isVisible():
            self.wEmStackProperties.leResX.setText(str(cfg.DEFAULT_RESX))
            self.wEmStackProperties.leResY.setText(str(cfg.DEFAULT_RESY))
            self.wEmStackProperties.leResZ.setText(str(cfg.DEFAULT_RESZ))
            self.wEmStackProperties.leNewChunk.setText(str(cfg.CHUNK_FACTOR))
            # self.wEmStackProperties.leChunkX.setText(str(cfg.CHUNK_X))
            # self.wEmStackProperties.leChunkY.setText(str(cfg.CHUNK_Y))
            # self.wEmStackProperties.leChunkZ.setText(str(cfg.CHUNK_Z))
            self.wEmStackProperties.cname_combobox.setCurrentText(str(cfg.CNAME))
        self.leNameImages.setFocus()
        self.setUpdatesEnabled(True)


    def updateImportImagesUI(self):
        logger.info('')
        # self.leNameImages.setText(self.leNameImages.text().strip())
        f = QFont()
        f.setItalic(not len(self.leNameImages.text()))
        self.leNameImages.setFont(f)
        isAllowedImport = bool(self.leNameImages.text() and bool(len(self._NEW_IMAGES_PATHS)))
        self.bCreateImages.setStyleSheet(("", "background-color: #339933; color: #f3f6fb;")[isAllowedImport])
        self.bCreateImages.setEnabled(isAllowedImport)
        self.leNameImages.setStyleSheet(("border-color: #339933; border-width: 2px;", "border-color: #f3f6fb;")[bool(self.leNameImages.text())])
        # QApplication.processEvents()
        self.labImgCount.setVisible(len(self.iid_dialog.selectedFiles()))
        # self.update()

    def updateConfirmAlignmentLabels(self):
        n = len(self._NEW_IMAGES_PATHS)
        if n > 0:
            im0 = Path(self._NEW_IMAGES_PATHS[0])
            im1 = Path(self._NEW_IMAGES_PATHS[1])
            self.labImgCount.setText(f"{n} images selected  ")
            if self.wEmStackProperties.cbCalGrid.isChecked():
                self.labConfirmReady.setText(f"Calibration Grid: {im0.name}  |  First Section: {im1.name}")
            else:
                self.labConfirmReady.setText(f"No Calibration Grid  |  First Section: {im0.name}")



    def selectImages(self):
        # self.iid_dialog = ImportImagesDialog()
        # self.iid_dialog.resize(QSize(820,480))
        # self.bSelect.setStyleSheet("background-color: #339933; color: #f3f6fb; border-color: #f3f6fb;")
        self.bCreateImages.setStyleSheet("")
        # self.vwEmStackProperties.hide()

        if self.iid_dialog.isVisible():
            self.iid_dialog.hide()
            return

        self.gbCreateImages.setAutoFillBackground(True)
        # if not self.iid_dialog.isVisible():
        self.iid_dialog.show()

        sidebar = self.findChild(QListView, "sidebar")
        delegate = StyledItemDelegate(sidebar)
        delegate.mapping = getSideBarPlacesImportImages()
        sidebar.setItemDelegate(delegate)

        if self.iid_dialog.exec_() == QDialog.Accepted:
            QApplication.processEvents()
            filenames = self.iid_dialog.selectedFiles()
            self._NEW_IMAGES_PATHS = natural_sort(filenames)
            n = len(self._NEW_IMAGES_PATHS)
            if n > 0:
                self.vwEmStackProperties.show()
                self.updateConfirmAlignmentLabels()

                if self.leNameImages.text():
                    self.bSelect.setStyleSheet("")
                    self.bCreateImages.setStyleSheet("background-color: #339933; color: #f3f6fb; border-color: #f3f6fb;")

            self.iid_dialog.pixmap = None
        else:
            self.iid_dialog.hide()
            # self.iid_dialog.pixmap = None
            self.parent.warn('Import images dialog did not return a valid file list')
            # self.showMainUI()
            return 1

        if filenames == 1:
            self.parent.warn('No Project Canceled')
            self.showMainUI()
            return 1

        # self._NEW_IMAGES_PATHS = natural_sort(filenames)
        self.updateImportImagesUI()
        logger.info(f"<<<< selectImages <<<<")



    def open_zarr_selected(self):
        path = Path(self.filebrowser.selection)
        logger.info(f"Opening Zarr {path}...")
        try:
            with open(path / '.zarray') as j:
                self.zarray = json.load(j)
        except:
            print_exception()
            return
        tab = ZarrTab(self, path=path)
        self.parent.addGlobTab(tab, path.name)
        self.parent._setLastTab()


    def deleteContextMethod(self):
        logger.info('')
        selected_projects = self.getSelectedProjects()
        self.delete_projects(project_files=selected_projects)

    # def openContextMethod(self):
    #     logger.info('')
    #     self.openAlignment()


    def delete_projects(self, project_files=None):
        logger.info('')
        if project_files == None:
            project_files = [self.selectionReadout.text()]

        for project_file in project_files:
            if project_file:
                if validate_project_selection(project_file):
                    project = Path(project_file).with_suffix('')
                    self.parent.tell("Delete this project? %s" % project_file)
                    txt = "Are you sure you want to PERMANENTLY DELETE " \
                          "the following project?\n\n" \
                          "Project: %s" % project_file
                    msgbox = QMessageBox(QMessageBox.Warning,
                                         'Confirm Delete Project',
                                         txt,
                                         buttons=QMessageBox.Cancel | QMessageBox.Yes
                                         )
                    msgbox.setIcon(QMessageBox.Critical)
                    msgbox.setMaximumWidth(350)
                    msgbox.setDefaultButton(QMessageBox.Cancel)
                    reply = msgbox.exec_()
                    if reply == QMessageBox.Cancel:
                        self.parent.tell('Canceling Delete Project Permanently Instruction...')
                        return
                    if reply == QMessageBox.Ok:
                        logger.info('Deleting file %s...' % project_file)
                        self.parent.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)

                    self.parent.tell(f'Deleting project file {project_file}...')

                    try:
                        os.remove(project_file)
                    except:
                        print_exception()
                    # else:
                    #     self.parent.hud.done()

                    # configure_project_paths()
                    # self.user_projects.set_data()

                    self.parent.tell(f'Deleting: {project}...')
                    try:
                        run_subprocess(["rm","-rf", project])
                    except:
                        self.parent.warn('An Error Was Encountered During Deletion of the Project Directory')
                        print_exception()
                    else:
                        self.parent.hud.done()

                    # self.parent.tell('Wrapping up...')
                    # configure_project_paths()
                    # if self.parent.globTabs.currentWidget().__class__.__name__ == 'ManagerTab':
                    #     try:
                    #         self.user_projects.set_data()
                    #     except:
                    #         logger.warning('There was a problem updating the project list')
                    #         print_exception()

                    self.parent.tell('Deletion Complete!')
                    logger.info('Deletion tasks finished')
                else:
                    logger.warning('(!) Invalid target for deletion: %s' % project_file)

    # def keyPressEvent(self, event):
    #     key = event.key()
    #     print(key)
    #
    #     if key == Qt.Key_Enter:
    #         print("Enter pressed!")

    # def eventFilter(self, source, event):
    #     if event.type() == QEvent.ContextMenu:
    #         logger.info('')
    #         menu = QMenu()
    #
    #         openContextAction = QAction('Open')
    #         openContextAction.triggered.connect(self.openContextMethod)
    #         menu.addAction(openContextAction)
    #
    #         deleteContextAction = QAction('Delete')
    #         deleteContextAction.triggered.connect(self.deleteContextMethod)
    #         menu.addAction(deleteContextAction)
    #
    #         # if self.getNumRowsSelected() == 1:
    #         #     # copyPathAction = QAction('Copy Path')
    #         #     # file_path = self.getSelectedProjects()[0]
    #         #     file_path = self.getSelectedProjects()[0]
    #         #     copyPathAction = QAction(f"Copy Path '{self.getSelectedProjects()[0]}'")
    #         #     logger.info(f"Added to Clipboard: {QApplication.clipboard().text()}")
    #         #     menu.addAction(copyPathAction)
    #
    #
    #
    #         menu.exec_(event.globalPos())
    #         return True
    #     return super().eventFilter(source, event)


    def keyPressEvent(self, event):
        print(event)
        self.keyevent = event

        if event.matches(QKeySequence.Open):
            logger.info("QKeySequence: Open")
            self.onOpenAlignment()
        elif event.matches(QKeySequence.Delete):
            self.onMinusAlignment()
        else:
            super().keyPressEvent(event) # re-raise the event if it doesn't match!


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))


def getSideBarPlacesProjectName():
    corral_projects_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'
    corral_images_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/EM_Series'

    places = {
        QUrl.fromLocalFile(os.getenv('HOME')): 'Home (' + str(os.getenv('HOME')) + ')',
        QUrl.fromLocalFile(os.getenv('WORK')): 'Work (' + str(os.getenv('WORK')) + ')',
        QUrl.fromLocalFile(os.getenv('SCRATCH')): 'Scratch (' + str(os.getenv('SCRATCH')) + ')',
        QUrl.fromLocalFile(corral_projects_dir): 'Projects_AlignEM',
    }
    if os.path.exists('/Volumes'):
        places[QUrl.fromLocalFile('/Volumes')] = '/Volumes'
    if is_joel():
        if os.path.exists('/Volumes/3dem_data'):
            places[QUrl.fromLocalFile('/Volumes/3dem_data')] = '/Volumes/3dem_data'

    return places

def getSideBarPlacesImportImages():
    corral_projects_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'
    corral_images_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/EM_Series'

    places = {
        QUrl.fromLocalFile(os.getenv('HOME')): 'Home (' + str(os.getenv('HOME')) + ')',
        QUrl.fromLocalFile(os.getenv('WORK')): 'Work (' + str(os.getenv('WORK')) + ')',
        QUrl.fromLocalFile(os.getenv('SCRATCH')): 'Scratch (' + str(os.getenv('SCRATCH')) + ')',
        QUrl.fromLocalFile(corral_images_dir): 'EM_Series',
    }
    if os.path.exists('/Volumes'):
        places[QUrl.fromLocalFile('/Volumes')] = '/Volumes'
    if is_joel():
        if os.path.exists('/Volumes/3dem_data'):
            places[QUrl.fromLocalFile('/Volumes/3dem_data')] = '/Volumes/3dem_data'

    return places


UrlRole = Qt.UserRole + 1
EnabledRole = Qt.UserRole + 2
class StyledItemDelegate(QStyledItemDelegate):
    mapping = dict()

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        url = index.data(UrlRole)
        text = self.mapping.get(url)
        if isinstance(text, str):
            option.text = text
        is_enabled = index.data(EnabledRole)
        if is_enabled is not None and not is_enabled:
            option.state &= ~QStyle.State_Enabled



class Thumbnail(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        self.thumbnail = ScaledPixmapLabel(self)
        self.pixmap = QPixmap(path)
        self.thumbnail.setPixmap(self.pixmap)
        self.thumbnail.setScaledContents(True)
        self.layout = QGridLayout()
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.addWidget(self.thumbnail, 0, 0)
        self.setLayout(self.layout)


def validate_tiff_folder(path) -> bool:
    # logger.info(f'caller:{inspect.stack()[1].function}')
    # file_path, extension = os.file_path.splitext(file_path)
    # contents = glob(os.file_path.join(file_path, '*'))
    # n_files = len(contents)
    # tif_files = glob(os.file_path.join(file_path, '*.tif'))
    # tiff_files = glob(os.file_path.join(file_path, '*.tiff'))
    # n_valid_files = len(tif_files) + len(tiff_files)
    # n_invalid_files = n_files - n_valid_files
    # # print(f'n_files: {n_files}')
    # # print(f'# valid files: {n_valid_files}')
    # # print(f'# invalid files: {n_invalid_files}')
    # return (n_valid_files > 0) and (n_invalid_files == 0)

    return (len(glob(os.path.join(path, '*.tiff'))) > 0) or (len(glob(os.path.join(path, '*.tif'))) > 0)


def validate_project_selection(path) -> bool:
    clr = inspect.stack()[1].function
    logger.info(f'[{clr}] Validating selection {path}...')
    if Path(path).suffix in ('.align'):
        return True
    return False


def validate_zarr_selection(path) -> bool:
    # logger.info(f'caller:{inspect.stack()[1].function}')
    # logger.info('Validating selection %level...' % cfg.selected_file)
    # called by setSelectionPathText
    if Path(path).is_dir():
        if '.zarray' in Path(path).glob('**/*'):
            return True
    return False


def set_image_sizes(dm):
    for s in dm.scales:
        if s != 's1':
            siz = (np.array(dm.image_size(s='s1')) / dm.lvl(s)).astype(int).tolist()
            logger.info(f"Setting size for {s} to {siz}...")
            dm['data']['scales'][s]['image_src_size'] = siz


class ImagesConfig(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        logger.info('')
        self.parent = parent
        self._settings = {}
        self.initUI()

    def getSettings(self, im_siz):

        cfg.main_window.hud('Setting images configuration...')
        logger.info('Setting images configuration...')
        self._settings['scale_factors'] = sorted(list(map(int, self.scales_input.text().strip().split(' '))))
        self._settings['clevel'] = int(self.leClevel.text())
        self._settings['cname'] = self.cname_combobox.currentText()
        self._settings['has_cal_grid'] = self.cbCalGrid.isChecked()
        # chunkshape = (int(self.leChunkZ.text()),
        #               int(self.leChunkY.text()),
        #               int(self.leChunkX.text()))
        self._settings['chunkshape'] = {}
        self._settings['resolution'] = {}
        for sv in self._settings['scale_factors']:
            res_z = int(self.leResZ.text())
            res_y = int(self.leResY.text()) * sv
            res_x = int(self.leResX.text()) * sv
            chunk_fac = int(self.leNewChunk.text())
            chunk_z = 1
            chunk_y = floor(im_siz[1] / (sv * chunk_fac))
            chunk_x = floor(im_siz[0] / (sv * chunk_fac))
            if min(chunk_y, chunk_x) < 512:
                chunk_y = 512
                chunk_x = 512
            # self._settings['resolution']['s%d' % sv] = (res_z, res_y, res_x)
            # self._settings['chunkshape']['s%d' % sv] = (chunk_z, chunk_y, chunk_x)
            self._settings['resolution']['s%d' % sv] = (res_x, res_y, res_z)
            self._settings['chunkshape']['s%d' % sv] = (chunk_x, chunk_y, chunk_z)

        return self._settings


    def initUI(self):
        logger.info('')

        '''Scales Input Field'''
        self.scales_input = QLineEdit(self)
        self.scales_input.setMaximumWidth(80)
        self.scales_input.setMinimumWidth(50)
        self.scales_input.setFixedHeight(18)
        self.scales_input.setText('24 6 2 1')
        self.scales_input.setAlignment(Qt.AlignCenter)
        tip = "Scale levels, space-delimited.\nThis would generate a 4x 2x and 1x level hierarchy:\n\n4 2 1"
        # self.scale_instructions_label = QLabel(tip)
        # self.scale_instructions_label.setStyleSheet("font-size: 11px;")
        self.scales_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))

        wScaling = HW(QLabel('Scale Levels: '), self.scales_input)
        wScaling.layout.setAlignment(Qt.AlignHCenter)

        '''Voxel Size (Resolution) Fields'''
        tip = "Resolution or size of each voxel (nm)"
        self.leResX = QLineEdit(self)
        self.leResY = QLineEdit(self)
        self.leResZ = QLineEdit(self)
        self.leResX.setFixedSize(QSize(24, 18))
        self.leResY.setFixedSize(QSize(24, 18))
        self.leResZ.setFixedSize(QSize(24, 18))
        self.leResX.setValidator(QIntValidator())
        self.leResY.setValidator(QIntValidator())
        self.leResZ.setValidator(QIntValidator())
        l1 = QLabel("x:").setAlignment(Qt.AlignRight)
        # l1.setAlignment(Qt.AlignRight)
        l2 = QLabel("y:").setAlignment(Qt.AlignRight)
        # l2.setAlignment(Qt.AlignRight)
        l3 = QLabel("z:").setAlignment(Qt.AlignRight)
        # l3.setAlignment(Qt.AlignRight)
        few = [HW(l1, self.leResX), HW(l2, self.leResY), HW(l3, self.leResZ)]
        for one in few:
            one.layout.setAlignment(Qt.AlignHCenter)
            one.setStyleSheet("font-size: 9px;")
        self.wResolution = HW(*few)
        # self.wResolution.layout.setAlignment(Qt.AlignCenter)
        # self.wResolution.layout.setSpacing(4)
        self.wResolution.setToolTip(tip)

        wVoxelSize = HW(QLabel('Voxel Size (nm): '), self.wResolution)
        wVoxelSize.layout.setAlignment(Qt.AlignCenter)

        tip = 'Zarr Compression Level\n(default=5)'
        self.leClevel = QLineEdit(self)
        self.leClevel.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.leClevel.setAlignment(Qt.AlignCenter)
        self.leClevel.setText(str(cfg.CLEVEL))
        self.leClevel.setFixedSize(QSize(24, 18))
        self.leClevel.setValidator(QIntValidator(1, 9, self))

        tip = f'Compression Type (default={cfg.CNAME})'
        self.cname_label = QLabel('Compression Option:')
        self.cname_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["none", "zstd", "zlib"])
        self.cname_combobox.setFixedSize(QSize(58,18))

        labType = QLabel('Compression Type: ')
        labLevel = QLabel('Compression Level (1-9): ')
        wCompression = HW(labType, self.cname_combobox, QLabel(' '), labLevel, self.leClevel)
        wCompression.layout.setSpacing(4)
        # wCompression.layout.setAlignment(Qt.AlignCenter)

        '''Chunk Shape'''
        self.leNewChunk = QLineEdit(self)
        self.leNewChunk.setFixedSize(QSize(24, 18))
        self.leNewChunk.setValidator(QIntValidator())


        # self.leChunkX = QLineEdit(self)
        # self.leChunkY = QLineEdit(self)
        # self.leChunkZ = QLineEdit(self)
        #
        # self.leChunkX.setFixedSize(QSize(40, 18))
        # self.leChunkY.setFixedSize(QSize(40, 18))
        # self.leChunkZ.setFixedSize(QSize(40, 18))
        #
        # self.leChunkX.setValidator(QIntValidator())
        # self.leChunkY.setValidator(QIntValidator())
        # self.leChunkZ.setValidator(QIntValidator())
        # l1 = QLabel("x:")
        # l1.setAlignment(Qt.AlignRight)
        # l2 = QLabel("y:")
        # l2.setAlignment(Qt.AlignRight)
        # l3 = QLabel("z:")
        # l3.setAlignment(Qt.AlignRight)


        # few = [HW(l1, self.leChunkX), HW(l2, self.leChunkY), HW(l3, self.leChunkZ)]
        # for one in few:
        #     one.layout.setAlignment(Qt.AlignHCenter)
        #     one.setStyleSheet("font-size: 9px;")
        # self.wChunk = HW(*few)
        # self.wChunk.layout.setSpacing(4)
        txt = "The way volumetric data will be stored. Zarr is an open-source " \
              "format for the storage of chunked, compressed, N-dimensional " \
              "arrays with an interface similar to NumPy."
        txt = '\n'.join(textwrap.wrap(txt, width=60))
        # wChunk = HW(QLabel('Chunk: '), self.wChunk)
        wChunk = HW(QLabel('Chunk Factor: '), self.leNewChunk)
        wChunk.setMaximumWidth(90)
        wChunk.setToolTip(txt)
        # wChunk.layout.setAlignment(Qt.AlignCenter)

        self.cbCalGrid = QCheckBox('Image 0 is calibration grid')
        # self.cbCalGrid.setChecked(False)
        self.cbCalGrid.setChecked(True) # Kristen's request

        hbl = HBL(wScaling, wVoxelSize, wCompression, wChunk, self.cbCalGrid)
        hbl.setContentsMargins(4,4,4,4)

        # hbl.setSpacing(12)
        self.setLayout(hbl)



class Slider(QSlider):
    def __init__(self, parent):
        super().__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(16)
        self.setMaximum(256)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)


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
                # logger.warning('Cannot divide by zero')
                pass
        super().paintEvent(event)


class ImageWidget(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)

    def hasHeightForWidth(self):
        return self.pixmap() is not None

    def heightForWidth(self, w):
        if self.pixmap():
            return int(w * (self.pixmap().height() / self.pixmap().width()))

class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)



class WebEngine(QWebEngineView):
    # use .settings() to access settings
    def __init__(self, ID):
        QWebEngineView.__init__(self)
        self.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        self.settings().setAttribute(QWebEngineSettings.AutoLoadImages, True)
        # self.loadFinished.connect(self.on_load_finish)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)
        # self.setnull()
        # self.setMinimumSize(QSize(200,200))
        self.setnull()


        # self.page().loadFinished.connect(lambda: self.page().runJavaScript(self.injectOnLoadFinish()))
        # self.urlChanged.connect(self._on_url_change)

    def injectOnLoadFinish(self):
        script = """
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.handler = channel.objects.handler;
            handler.test(function(retVal) {
                // console.error as console.log message don't show up in the python console
                console.error(JSON.stringify(retVal));
            });
        
        """
        return script

    def setText(self, text:str):
        self.setHtml(self.createHTML(text))

    def setnull(self):
        self.setText('Neuroglancer: No Data.')
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Null view set")

    def loadRandom(self):
        script = """
        alert(document.title);
        document.body.style.backgroundImage = "url('https://www.w3schools.com/jsref/img_tree.png')";"""
        self.page().runJavaScript(script)

    def _load(self, path='https://cnl.salk.edu/~jyancey/media/emguy.gif'):
        script = f"""
        alert(document.title);
        document.body.style.backgroundImage = "url('{path}')";
        document.body.style.backgroundSize = "360px 180px";
        """
        self.page().runJavaScript(script)

    def createHTML(self, text):
        doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
           <title>Null</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Tahoma, sans-serif; background-color: #000000; 
        color: #f3f6fb; font-size: 12px;">
            &nbsp;{text}&nbsp;
        </body>
        </html>
        """
        return doc

    # def _on_load_finished(self):
    #     self.current_url = self.url().toString()

    # def _on_url_change(self):
    #     self.page().runJavaScript("document.getElementsByName('email')[0].value", self.store_value)
    #
    # def store_value(self, param):
    #     self.value = param
    #     print("Param: " + str(param))


class BoldLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet('font-weight: 600; font-size: 9px; color: #141414;')


class Label(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet('font-size: 9px; color: #141414;')

class HoverButton(QPushButton):

   def __init__(self, text):
       super(HoverButton, self).__init__()
       self.text = text
       self.setCursor(QCursor(Qt.PointingHandCursor))
       self.installEventFilter(self)
       self.setFixedSize(QSize(18, 18))
       self.setIconSize(QSize(12,12))

   def eventFilter(self, source, event):
       if event.type() == QEvent.HoverEnter:
           self.setFixedSize(QSize(52,20))
           self.setText(self.text)
           self.update()

       elif event.type() == QEvent.HoverLeave:
           self.setText('')
           self.setFixedSize(QSize(18, 18))
           self.update()

       return super().eventFilter(source, event)


class GroupBox(QGroupBox):
    clicked = Signal(str, object)

    def __init__(self, title=None):
        super(GroupBox, self).__init__()
        if title:
            self.setTitle(title)

        self.setStyleSheet("""QGroupBox {
            font-weight: 600;
            font: 11px Tahoma;
            border: 1px solid silver;
            border-radius: 4px;
            margin-top: 6px;
        }

        QGroupBox::title {
            font-weight: 600;
            font: 11px Tahoma;
            subcontrol-origin: margin;
            left: 7px;
            padding: 0px 5px 0px 5px;
        }
        """)



# def createHTML(text='Nothing To Display'):
#     html = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#        <title>Null</title>
#         <meta charset="utf-8">
#     </head>
#     <body style="font-family: Consolas, sans-serif; background-color: #000000; color: #f3f6fb;">
#
#         <b>&nbsp;&nbsp;{text}&nbsp;&nbsp;</b>
#
#     </body>
#     </html>
#     """
#     return html