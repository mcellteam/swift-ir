#!/usr/bin/env python3

import copy
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
import tensorstore as ts
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWebEngineWidgets import *
from qtpy.QtWidgets import *

import src.config as cfg
from src.models.data import DataModel
from src.utils.funcs_image import ImageSize
from src.utils.helpers import print_exception, natural_sort, is_tacc, is_joel, hotkey, derive_search_paths
from src.ui.dialogs.importimages import ImportImagesDialog
from src.ui.layouts.layouts import HBL, VBL, HW, VW
from src.ui.widgets.vertlabel import VerticalLabel
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
        self.dm = None
        self._level = None
        self._watchImages = DirectoryWatcher(suffixes=['.emstack', '.images'], preferences=cfg.preferences,
                                             key='images_search_paths')
        self._watchImages.fsChanged.connect(self.updateCombos)
        self._watchAlignments = DirectoryWatcher(suffixes=['.alignment', '.align'], preferences=cfg.preferences, key='alignments_search_paths')
        self._watchAlignments.fsChanged.connect(self.loadAlignmentCombo)
        self._images_info = {}
        self._updating_viewers = False  # Re-entrancy guard for updatePMViewers
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._updateWatchPaths()
        self.initUI()
        self._NEW_IMAGES_PATHS = []

        self.resetView()

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
            for var in ('SCRATCH', 'WORK', 'HOME'):
                if os.getenv(var):
                    urls.append(QUrl.fromLocalFile(os.getenv(var)))
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
        self.bCancel.clicked.connect(self._onCancelCreate)


        self.bCreateImages = QPushButton("Create")
        self.bCreateImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCreateImages.clicked.connect(self.confirmCreateImages)
        self.bCreateImages.setEnabled(False)

        # self.wNameEmStack = HW(QLabel('Images Name:'), self.leNameImages, self.bSelect, self.bCreateImages, self.bCancel)
        self.wNameEmStack = VW(BoldLabel('Step 1:'), HW(QLabel('Images Name:'), self.leNameImages, self.bSelect, self.bCancel))
        # self.wNameEmStack.setStyleSheet("QLabel {color: #f3f6fb;} ")
        self.wNameEmStack.layout.setSpacing(2)
        self.wNameEmStack.layout.setContentsMargins(0, 0, 0, 0)

        # Content root selector (where the emstack will be created)
        self.comboContentRoot = QComboBox()
        self.comboContentRoot.setFixedHeight(18)
        self.comboContentRoot.setToolTip("Select content root (alignem_data directory)")
        self._populateContentRootCombo()

        self.bBrowseContentRoot = QPushButton("Browse...")
        self.bBrowseContentRoot.setFixedSize(QSize(60, 18))
        self.bBrowseContentRoot.setCursor(QCursor(Qt.PointingHandCursor))
        self.bBrowseContentRoot.setToolTip("Choose a new content root directory")
        self.bBrowseContentRoot.clicked.connect(self._onBrowseContentRoot)

        self.wContentRoot = HW(QLabel('Content Root:'), self.comboContentRoot, self.bBrowseContentRoot)
        self.wContentRoot.layout.setSpacing(4)
        self.wContentRoot.layout.setContentsMargins(0, 0, 0, 0)

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
        vbl = VBL(self.wContentRoot, self.wNameEmStack, self.vwEmStackProperties)
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

        self.vbl_main = VBL()
        self.vbl_main.setSpacing(0)

        self.vbl_main.addWidget(self.vsplitter)

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

        # Use the selected content root
        selected_root = self.comboContentRoot.currentText()
        images_dir = os.path.join(selected_root, 'images')
        os.makedirs(images_dir, exist_ok=True)
        out = os.path.join(images_dir, name)

        # Add this root to content_roots if it's new
        self._addContentRoot(selected_root)
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
            siz = (np.array(full_scale_size) / sv).astype(int).tolist()
            opts['size_zyx'][key] = (count, siz[1], siz[0])
            opts['size_xy'][key] = siz

        siz_x, siz_y = ImageSize(opts['paths'][1])
        sf = int(max(siz_x, siz_y) / cfg.TARGET_THUMBNAIL_SIZE)
        opts['thumbnail_scale_factor'] = sf
        p = os.path.join(out, 'info.json')
        write('json')(p, opts)
        self.update()
        # QApplication.processEvents()
        cfg.preferences['images_combo_text'] = out
        # Blank the viewer before starting the background worker —
        # _syncContentRoots / updateCombos may have reloaded old data
        self.webengine0.setnull()
        self.parent.autoscaleImages(src, out, opts)
        # Don't resetView here — keep viewer blank while the background
        # worker creates the emstack.  _onScaleComplete calls
        # resetView(init_viewer=True) when finished.

    def createAlignment(self):
        '''Create a new alignment for the selected EM stack.'''
        logger.info('')
        self.bPlusAlignment.setEnabled(False)
        # Find the content root that contains the selected emstack
        root = Path(self._getAlignmentsRootForEmstack(self.comboImages.currentText()))
        seriespath = Path(self.comboImages.currentText())
        usertext = self.leNameAlignment.text()
        newproject = (root / usertext).with_suffix('.align')
        newdir = (root / usertext).with_suffix('')
        info = seriespath / 'info.json'
        _err = 0
        _msg = ''
        if not os.path.isdir(seriespath):
            _err = 1
            _msg += f"Image Series Not Found: {seriespath}.\nWere the images moved?\n"
        if not info.exists():
            _err = 1
            _msg += f"Image Stack 'info.json' File Is Missing:\n{info}\nWas it moved?\n"
        if os.path.exists(newproject):
            _err = 1
            _msg += f"A file with this name already exists: {newproject}\n"
        if os.path.exists(newdir):
            _err = 1
            _msg += f"A directory with this name already exists: {newdir}\n"

        if _err:
            self.parent.warn(_msg)
            self.resetView()
        else:
            info = read('json')(info)
            self.dm = dm = DataModel(file_path=newproject, images_path=seriespath, init=True, images_info=info)
            # DirectoryStructure(dm).initDirectory()
            self.dm.ds.initDirectory()
            AlignmentTab(self.parent, self.dm)
            self.dm.save(silently=True)
        self.bPlusAlignment.setEnabled(True)
        self.resetView()
        logger.info(f"<-- createAlignment")



    def _connectViewerSignals(self, viewer):
        viewer.signals.arrowLeft.connect(self.parent.layer_left)
        viewer.signals.arrowRight.connect(self.parent.layer_right)
        viewer.signals.arrowUp.connect(self.parent.incrementZoomIn)
        viewer.signals.arrowDown.connect(self.parent.incrementZoomOut)

    def initPMviewer(self, path=None):
        '''Initialize the PMViewer instances for the current images and alignment paths.'''
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
            self._connectViewerSignals(self.viewer0)
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
            self._connectViewerSignals(self.viewer1)
        except:
            print_exception()

        self.updatePMViewers()
        self.setUpdatesEnabled(True)

    def updatePMViewers(self):
        logger.info('')
        # Re-entrancy guard: prevent processEvents() from triggering nested viewer updates
        if self._updating_viewers:
            logger.warning("updatePMViewers already in progress, skipping re-entrant call")
            return
        self._updating_viewers = True
        try:
            self.setUpdatesEnabled(False)
            level = self.comboLevel.currentText()
            if self.comboImages.currentText():
                path = Path(self.comboImages.currentText()) / 'zarr' / level
                if path.exists():
                    if hasattr(self, 'viewer0'):
                        self.viewer0.path = str(path)  # Update path before reinit
                        # Use delayed layer creation to avoid GL texture errors
                        # that occur when layers are created before WebSocket is ready
                        def create_viewer0_layers():
                            if hasattr(self, 'viewer0') and self.viewer0.tensor is not None:
                                self.viewer0.add_im_layer('source', self.viewer0.tensor[:,:,:], clear_first=True)
                                # Validate layer was created
                                if len(self.viewer0.state.layers) != 1:
                                    raise RuntimeError(f"Expected 1 layer, got {len(self.viewer0.state.layers)}")
                                # Force browser to reload with updated state containing layers
                                self.webengine0.setUrl(QUrl(self.viewer0.get_viewer_url()))
                        self.webengine0.setOnLoadCallback(create_viewer0_layers)
                        self.viewer0.initViewer(skip_layers=True)
                        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

                    if self.comboTransformed.currentText() and hasattr(self, 'viewer1'):
                        # Recreate viewer1 fresh to avoid neuroglancer state conflicts
                        try:
                            resolution = self._images_info['resolution'][level]
                        except:
                            resolution = [8, 8, 50]

                        # Clear webengine BEFORE deleting old viewer to prevent JS errors
                        self.webengine1.setnull()
                        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

                        # Follow EMViewer pattern: load page first with NO layers,
                        # then add transformation layers AFTER page is loaded
                        old_viewer = self.viewer1
                        self.viewer1 = PMViewer(
                            parent=self,
                            webengine=self.webengine1,
                            path=str(path),
                            res=resolution,
                            extra_data={'name': 'viewer1', 'dm': self.dm})
                        self.viewer1.dm = self.dm  # Set dm before initViewer
                        self._connectViewerSignals(self.viewer1)
                        # Clean up old viewer after webengine is cleared
                        del old_viewer

                        # Use different approach based on dataset size:
                        # - Small datasets (<50 slices): pre-transform in Python, single LocalVolume
                        # - Large datasets: use transformation layers (works reliably)
                        self.viewer1.initViewer(skip_layers=True, use_transformation_layers=False)

                        def add_layers():
                            if hasattr(self, 'viewer1') and self.viewer1.tensor is not None:
                                self.viewer1.add_transformation_layers(affine=True, clear_first=True)
                                # Refresh URL to load with new state
                                self.webengine1.setUrl(QUrl(self.viewer1.get_viewer_url()))
                        self.webengine1.setOnLoadCallback(add_layers)

                        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            self.setUpdatesEnabled(True)
        except:
            print_exception()
        finally:
            self._updating_viewers = False



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
        # Clear old watches before adding current ones to avoid stale paths
        self._watchImages.clearWatches()
        self._watchAlignments.clearWatches()
        for sp in cfg.preferences['images_search_paths']:
            if os.path.isdir(sp):
                self._watchImages.watch(sp)
        for sp in cfg.preferences['alignments_search_paths']:
            if os.path.isdir(sp):
                self._watchAlignments.watch(sp)

    def _populateContentRootCombo(self):
        '''Populate the content root combo from preferences.'''
        if hasattr(self, 'comboContentRoot'):
            self.comboContentRoot.clear()
            for root in cfg.preferences.get('content_roots', []):
                self.comboContentRoot.addItem(root)

    def _onBrowseContentRoot(self):
        '''Browse for a new content root directory.'''
        start_dir = self.comboContentRoot.currentText() or os.path.expanduser('~')
        chosen = QFileDialog.getExistingDirectory(self, "Select Content Root Directory", start_dir)
        if not chosen:
            return
        # Ensure it ends with alignem_data
        if not chosen.endswith('alignem_data'):
            chosen = os.path.join(chosen, 'alignem_data')
        self._addContentRoot(chosen)
        self.comboContentRoot.setCurrentText(chosen)

    def _addContentRoot(self, root):
        '''Add a content root to preferences and sync watchers.'''
        if root not in cfg.preferences['content_roots']:
            cfg.preferences['content_roots'].append(root)
            os.makedirs(os.path.join(root, 'images'), exist_ok=True)
            os.makedirs(os.path.join(root, 'alignments'), exist_ok=True)
            self._syncContentRoots()
            self._populateContentRootCombo()

    def _syncContentRoots(self):
        '''Derive search paths from content_roots, update watchers.'''
        cfg.preferences['images_search_paths'] = derive_search_paths(cfg.preferences['content_roots'], 'images')
        cfg.preferences['alignments_search_paths'] = derive_search_paths(cfg.preferences['content_roots'], 'alignments')
        self._updateWatchPaths()
        self.parent.saveUserPreferences(silent=True)

    def _getAlignmentsRootForEmstack(self, emstack_path):
        '''Find the alignments directory in the same content root as the given emstack.'''
        emstack_path = str(emstack_path)
        for root in cfg.preferences.get('content_roots', []):
            images_dir = os.path.join(root, 'images')
            if emstack_path.startswith(images_dir):
                return os.path.join(root, 'alignments')
        # Fallback to default
        return cfg.preferences['alignments_root']

    def updateCombos(self):
        '''Loading this combobox triggers the loading of the alignment and scales comboboxes'''
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
        # Load alignment data model if a remembered alignment is selected
        if self.comboTransformed.currentText():
            try:
                self.dm = DataModel(data=read('json')(self.comboTransformed.currentText()), readonly=True)
            except:
                self.dm = None
                print_exception()
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        # Don't try to load viewers while the scale worker is building the emstack —
        # the zarr doesn't exist yet and tensorstore will raise ValueError.
        if not self.parent._working:
            self.updatePMViewers()


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
        self.comboLevel.blockSignals(True)
        self.comboLevel.clear()
        if self._images_info:
            if type(self._images_info) == dict:
                if 'levels' in self._images_info:
                    self.comboLevel.addItems(self._images_info['levels'])
                    self.comboLevel.setCurrentIndex(self.comboLevel.count() - 1)
        self.comboLevel.blockSignals(False)


    def onComboSelectEmstack(self):
        logger.info('')
        self.webengine0.setnull()
        self.webengine1.setnull()
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)  # Allow webengines to clear
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
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)  # Process pending events before viewer update
            self.updatePMViewers()

    def onComboTransformed(self):
        logger.info('')
        cfg.preferences['alignment_combo_text'] = self.comboTransformed.currentText()
        try:
            self.dm = DataModel(data=read('json')(self.comboTransformed.currentText()), readonly=True)
        except:
            self.dm = None
            print_exception()

        self.wNameAlignment.hide()
        self.leNameAlignment.clear()
        if self.comboTransformed.currentText() and hasattr(self, 'viewer1'):
            # Don't call setnull() - it disrupts WebSocket connection
            # Update path in case level changed
            level = self.comboLevel.currentText()
            path = Path(self.comboImages.currentText()) / 'zarr' / level
            self.viewer1.path = str(path)

            # Recreate viewer1 fresh to avoid neuroglancer state conflicts
            try:
                resolution = self._images_info['resolution'][level]
            except:
                resolution = [8, 8, 50]

            # Clear webengine BEFORE deleting old viewer to prevent JS errors
            # when accessing deleted SharedObjects
            self.webengine1.setnull()
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

            # Follow EMViewer pattern: load page first with NO layers,
            # then add transformation layers AFTER page is loaded
            old_viewer = self.viewer1
            self.viewer1 = PMViewer(
                parent=self,
                webengine=self.webengine1,
                path=str(path),
                res=resolution,
                extra_data={'name': 'viewer1', 'dm': self.dm})
            self.viewer1.dm = self.dm  # Set dm before initViewer
            self._connectViewerSignals(self.viewer1)
            # Clean up old viewer after webengine is cleared
            del old_viewer

            # Use different approach based on dataset size:
            # - Small datasets (<50 slices): pre-transform in Python, single LocalVolume
            # - Large datasets: use transformation layers (works reliably)
            self.viewer1.initViewer(skip_layers=True, use_transformation_layers=False)

            def add_layers():
                if hasattr(self, 'viewer1') and self.viewer1.tensor is not None:
                    self.viewer1.add_transformation_layers(affine=True, clear_first=True)
                    # Refresh URL to load with new state
                    self.webengine1.setUrl(QUrl(self.viewer1.get_viewer_url()))
            self.webengine1.setOnLoadCallback(add_layers)

            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)


    def onComboLevel(self):
        self._level = self.comboLevel.currentText()
        self.webengine0.setnull()
        self.webengine1.setnull()
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)  # Allow webengines to clear
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
            return
        if validate_project_selection(file_path):

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

    def _onCancelCreate(self):
        self._NEW_IMAGES_PATHS = []
        self.leNameImages.clear()
        self.gbCreateImages.hide()
        self.iid_dialog.hide()
        self.vwEmStackProperties.hide()
        self.wSelectEmstack.show()
        # Clear combo selections and blank both viewers
        self.comboImages.setCurrentIndex(-1)
        cfg.preferences['images_combo_text'] = None
        self.webengine0.setnull()
        self.comboTransformed.clear()
        self.comboTransformed.setPlaceholderText("")
        cfg.preferences['alignment_combo_text'] = None
        self.webengine1.setnull()

    def onPlusEmstack(self):
        self.setUpdatesEnabled(False)
        isShown = self.gbCreateImages.isVisible()
        self.resetView()
        self.leNameImages.setStyleSheet(("border-color: #339933; border-width: 2px;", "border-color: #f3f6fb;")[bool(
            self.leNameImages.text(
        ))])
        self.gbCreateImages.setVisible(not isShown)
        self.wSelectEmstack.hide()
        if not isShown:
            self.webengine0.setnull()
            # Clear alignments panel — no emstack selected during creation
            self.comboTransformed.clear()
            self.comboTransformed.setPlaceholderText("")
            self.webengine1.setnull()
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

        if self.iid_dialog.exec() == QDialog.Accepted:
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
    }
    if os.getenv('WORK'):
        places[QUrl.fromLocalFile(os.getenv('WORK'))] = 'Work (' + os.getenv('WORK') + ')'
    if os.getenv('SCRATCH'):
        places[QUrl.fromLocalFile(os.getenv('SCRATCH'))] = 'Scratch (' + os.getenv('SCRATCH') + ')'
    places[QUrl.fromLocalFile(corral_projects_dir)] = 'Projects_AlignEM'
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
    }
    if os.getenv('WORK'):
        places[QUrl.fromLocalFile(os.getenv('WORK'))] = 'Work (' + os.getenv('WORK') + ')'
    if os.getenv('SCRATCH'):
        places[QUrl.fromLocalFile(os.getenv('SCRATCH'))] = 'Scratch (' + os.getenv('SCRATCH') + ')'
    places[QUrl.fromLocalFile(corral_images_dir)] = 'EM_Series'
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
    logger.info(f'Validating selection {path}...')
    if Path(path).suffix in ('.align'):
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
        l1 = QLabel("x:")
        l1.setAlignment(Qt.AlignRight)
        l2 = QLabel("y:")
        l2.setAlignment(Qt.AlignRight)
        l3 = QLabel("z:")
        l3.setAlignment(Qt.AlignRight)
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
        if self.pixmap() and not self.pixmap().isNull():
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
                    qp.end()
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
        self.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        self.settings().setAttribute(QWebEngineSettings.AutoLoadImages, True)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)

        # Callback to run when page finishes loading
        self._on_load_callback = None
        self._callback_generation = 0  # Generation counter to invalidate stale timer callbacks
        self.setnull()
        self.loadFinished.connect(self._on_load_finished)

    def _on_load_finished(self, ok):
        """Called when webengine finishes loading a page."""
        current_url = self.url().toString()
        has_callback = self._on_load_callback is not None
        logger.info(f"[{self.ID}] loadFinished: ok={ok}, hasCallback={has_callback}, gen={self._callback_generation}, url={current_url[:60]}...")
        if ok and has_callback:
            # Only trigger callback for neuroglancer URLs, not HTML content from setnull()
            if current_url.startswith('http://127.0.0.1') or current_url.startswith('http://localhost'):
                logger.info(f"[{self.ID}] Scheduling layer creation callback (gen={self._callback_generation})")
                callback = self._on_load_callback
                generation = self._callback_generation  # Capture current generation
                self._on_load_callback = None  # Clear callback so it only runs once
                # Schedule callback with retry logic, passing generation to detect stale timers
                self._scheduleCallbackWithRetry(callback, generation, attempt=1)
            else:
                logger.info(f"[{self.ID}] URL is not neuroglancer, not triggering callback")

    def _scheduleCallbackWithRetry(self, callback, generation, attempt=1, max_attempts=3):
        """Schedule a callback with retry logic for robustness.

        Both viewers need delayed layer creation to avoid GL texture errors and
        referencedGeneration errors. The neuroglancer WebSocket must be fully
        connected before layers can be added safely.

        Args:
            callback: The function to call (typically adds layers to the viewer)
            generation: The callback generation when this was scheduled
            attempt: Current attempt number (1-based)
            max_attempts: Maximum retry attempts before giving up
        """
        # Progressive delays: 500ms, 1000ms, 2000ms
        # Start with 500ms which is typically enough for WebSocket connection
        delay = 500 * attempt
        logger.info(f"[{self.ID}] Scheduling callback attempt {attempt} gen={generation} with {delay}ms delay")

        def try_callback():
            # Check if this callback is stale (a newer viewer setup has occurred)
            if generation != self._callback_generation:
                logger.warning(f"[{self.ID}] Skipping stale callback (gen={generation}, current={self._callback_generation})")
                return
            logger.info(f"[{self.ID}] Executing callback attempt {attempt} gen={generation}")
            try:
                callback()
                logger.info(f"[{self.ID}] Layer creation succeeded on attempt {attempt}")
            except Exception as e:
                if attempt < max_attempts:
                    logger.warning(f"[{self.ID}] Layer creation failed on attempt {attempt}, retrying: {e}")
                    self._scheduleCallbackWithRetry(callback, generation, attempt + 1, max_attempts)
                else:
                    logger.error(f"[{self.ID}] Layer creation failed after {max_attempts} attempts: {e}")

        QTimer.singleShot(delay, try_callback)

    def setOnLoadCallback(self, callback):
        """Register a callback to run after the next page load completes.

        The callback will be executed after the page loads with retry logic
        to handle cases where the neuroglancer WebSocket isn't immediately ready.
        Increments the generation counter so any previously scheduled timer
        callbacks are invalidated (they check generation before executing).
        """
        self._callback_generation += 1
        self._on_load_callback = callback

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
        # Clear any pending callback so the HTML load doesn't trigger it
        self._callback_generation += 1  # Invalidate any pending timer callbacks
        self._on_load_callback = None
        self.setText('Neuroglancer: No Data.')
        logger.info(f"[{self.ID}] Null view set (gen={self._callback_generation})")

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