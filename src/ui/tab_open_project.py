#!/usr/bin/env python3

import os
import sys
import json
import time
import uuid
import shutil
import inspect
import logging
from pathlib import Path
import platform
import textwrap
from datetime import datetime
import copy
from pprint import pformat
from glob import glob
from pathlib import Path
import subprocess as sp
import numpy as np
from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWebEngineWidgets import *
import qtawesome as qta
from src.ui.file_browser import FileBrowser
from src.funcs_image import ImageSize
from src.helpers import list_paths_absolute, get_bytes, absFilePaths, getOpt, setOpt, \
    print_exception, natural_sort, is_tacc, is_joel, hotkey, initLogFiles, sanitizeSavedPaths
from src.data_model import DataModel
from src.ui.tab_zarr import ZarrTab
from src.ui.dialogs import ImportImagesDialog
from src.ui.layouts import HBL, VBL, GL, HW, VW, HSplitter, VSplitter
from src.ui.tab_project import VerticalLabel
from src.viewer_em import PMViewer
from src.thumbnailer import Thumbnailer

import src.config as cfg

__all__ = ['OpenProject']

logger = logging.getLogger(__name__)


class OpenProject(QWidget):

    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent
        self.setMinimumHeight(100)
        self.filebrowser = FileBrowser(parent=self)
        self.filebrowser.setContentsMargins(2,2,2,2)
        self._watchImages = FileWatcher(extension='.images', preferences=cfg.preferences, key='images_search_paths')
        self._watchImages.fsChanged.connect(self.updateCombos)
        self._watchAlignments = FileWatcher(extension='.alignment', preferences=cfg.preferences, key='alignments_search_paths')
        self._watchAlignments.fsChanged.connect(self.loadAlignmentCombo)
        # self._fsWatcher = FsWatcher(extension='.alignment')
        self.filebrowser.navigateTo(os.path.expanduser('~'))
        self._updateWatchPaths()
        self.initUI()
        self.selected_file = ''
        self._NEW_IMAGES_PATHS = []

        logger.debug("\n\n\nTESTTTTTT\n\n")

        # clipboard = QGuiApplication.clipboard()
        # clipboard = QApplication.clipboard()
        # clipboard.dataChanged.connect(self.onClipboardChanged)
        #Note: when clipboard changes during app out-of-focus, clipboard changed signal gets emitted
        #once focus is returned. This is the ideal behavior.

        # self.setStyleSheet("font-size: 10px; color: #161c20;") #0919-

        # sanitizeSavedPaths()

        # configure_project_paths()

        # self.installEventFilter(self)

        self.filebrowser.setRootLastKnownRoot()

        self.resetView()
        self.refresh()



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
        self.bPlusImages.setToolTip("Create Images (.images)")
        # self.bPlusImages.setIcon(qta.icon('fa5s.images', color='#ede9e8'))
        # self.bPlusImages.setIcon(qta.icon('fa5s.images'))
        self.bPlusImages.setIcon(qta.icon('fa.plus'))
        self.bPlusImages.clicked.connect(self.showImportSeriesDialog)

        # self.bMinusAlignment = HoverButton('Delete')
        self.bMinusImages = QPushButton()
        self.bMinusImages.setFixedSize(QSize(18, 18))
        self.bMinusImages.setIconSize(QSize(13, 13))
        self.bMinusImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.bMinusImages.setToolTip("Delete Images (.images)")
        self.bMinusImages.setToolTipDuration(-1)
        # self.bMinusImages.setIcon(qta.icon('fa.minus', color='#ede9e8'))
        self.bMinusImages.setIcon(qta.icon('fa.minus'))
        self.bMinusImages.clicked.connect(self.onMinusImages)

        self.cmbLevel = QComboBox()
        self.cmbLevel.setToolTip("Scale Level")
        self.cmbLevel.setFixedSize(QSize(44, 18))
        self.cmbLevel.setCursor(QCursor(Qt.PointingHandCursor))
        self.cmbLevel.setFocusPolicy(Qt.NoFocus)
        self.cmbLevel.currentIndexChanged.connect(self.onComboLevel)

        self.cmbSelectAlignment = QComboBox()
        self.cmbSelectAlignment.setStyleSheet("""QComboBox QAbstractItemView {
    border: 2px solid darkgray;
    selection-background-color: lightgray;
}""")
        self.cmbSelectAlignment.setToolTip("Select Alignment (.alignment)")
        # self.cmbSelectAlignment.setPlaceholderText("Select Alignment...")
        self.cmbSelectAlignment.setPlaceholderText("")
        self.cmbSelectAlignment.setFocusPolicy(Qt.NoFocus)
        self.cmbSelectAlignment.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.cmbSelectAlignment.setEditable(True)
        # self.cmbSelectAlignment.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.cmbSelectAlignment.setCursor(QCursor(Qt.PointingHandCursor))
        self.cmbSelectAlignment.textActivated.connect(self.initPMviewer)
        # self.cmbSelectAlignment.addItems(["None"])

        self.cmbSelectImages = QComboBox()
        self.cmbSelectImages.setToolTip("Select Images (.images)")
        self.cmbSelectImages.setPlaceholderText("Select Images...")
        self.cmbSelectImages.setFocusPolicy(Qt.NoFocus)
        self.cmbSelectImages.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.cmbSelectImages.setEditable(True)
        # self.cmbSelectImages.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.cmbSelectImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.updateCombos()
        self.cmbSelectImages.textActivated.connect(self.onSelectImagesCombo)

        tip = f"Create Alignment (.alignment)"
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

        # self.bOpenAlignment = HoverButton('Open')
        self.bOpenAlignment = QPushButton()
        self.bOpenAlignment.setFixedSize(QSize(18, 18))
        self.bOpenAlignment.setIconSize(QSize(13, 13))
        self.bOpenAlignment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bOpenAlignment.setToolTip("Open alignment")
        self.bOpenAlignment.setToolTipDuration(-1)
        # self.bOpenAlignment.setIcon(qta.icon('fa.folder-open', color='#ede9e8'))
        self.bOpenAlignment.setIcon(qta.icon('fa.folder-open'))
        self.bOpenAlignment.clicked.connect(self.onOpenAlignment)

        self.wSelectImageSeries = HW(self.cmbSelectImages, self.cmbLevel, self.bPlusImages, self.bMinusImages)
        self.wSelectAlignment = HW(self.cmbSelectAlignment, self.bOpenAlignment, self.bPlusAlignment, self.bMinusAlignment)

        self.toolbar = QToolBar()
        self.toolbar.addWidget(VW(self.wSelectImageSeries, self.wSelectAlignment))

        self.webengine = WebEngine(ID='pmViewer')
        self.webengine.setFocusPolicy(Qt.StrongFocus)
        setWebengineProperties(self.webengine)

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
            # self.leNameAlignment.setStyleSheet(("border-color: #339933; border-width: 2px;", "border-color: #f3f6fb;")[
            #                                        bool(self.leNameAlignment.text())])
            # self.bConfirmNewAlignment.setStyleSheet(("background-color: #222222;", "background-color: #339933; border-color: #f3f6fb;")[
            #                                             bool(self.leNameAlignment.text())])
            f = QFont()
            f.setItalic(not len(self.leNameAlignment.text()))
            self.leNameAlignment.setFont(f)
        self.leNameAlignment.textEdited.connect(onTextChanged)

        self.bConfirmNewAlignment = QPushButton('Create')
        self.bConfirmNewAlignment.setFixedSize(QSize(44, 18))
        self.bConfirmNewAlignment.setAutoFillBackground(False)
        # self.bConfirmNewAlignment.setStyleSheet("font-size: 10px; background-color: rgba(0,0,0,.5); color: #f3f6fb; border-color: #f3f6fb;")
        self.bConfirmNewAlignment.setFocusPolicy(Qt.NoFocus)
        self.bConfirmNewAlignment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bConfirmNewAlignment.clicked.connect(self.createAlignment)

        self.bCancelNewAligment = QPushButton()
        self.bCancelNewAligment.setAutoFillBackground(False)
        # self.bCancelNewAligment.setStyleSheet("font-size: 10px; background-color: rgba(0,0,0,.5); color: #f3f6fb; border-color: #f3f6fb;")
        self.bCancelNewAligment.setIcon(qta.icon('fa.close'))
        self.bCancelNewAligment.setFixedSize(QSize(18, 18))
        self.bCancelNewAligment.setIconSize(QSize(12,12))
        self.bCancelNewAligment.setFocusPolicy(Qt.NoFocus)
        self.bCancelNewAligment.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCancelNewAligment.clicked.connect(lambda: self.wNameAlignment.hide())
        self.bCancelNewAligment.clicked.connect(lambda: self.webengine.setFocus())

        newAlignmentLab = QLabel("Alignment Name:")
        # newAlignmentLab.setStyleSheet("font-size: 10px; background-color: rgba(0,0,0,.5); color: #f3f6fb; border-color: #f3f6fb;")
        self.wNameAlignment = HW(self.leNameAlignment, self.bConfirmNewAlignment, self.bCancelNewAligment)
        self.wNameAlignment.setFixedHeight(18)
        self.wNameAlignment.layout.setSpacing(0)
        newAlignmentLab.setAutoFillBackground(True)
        # self.wNameAlignment.setStyleSheet("font-size: 10px; background-color: rgba(0,0,0,.5); color: #f3f6fb; border-color: #f3f6fb;")
        self.wNameAlignment.hide()

        '''Step 1/3'''
        logger.info('Creating name_dialog...')
        self.name_dialog = QFileDialog()
        # self.name_dialog.setContentsMargins(2,2,2,2)
        self.name_dialog.setWindowFlags(Qt.FramelessWindowHint)
        self.name_dialog.setOption(QFileDialog.DontUseNativeDialog)
        self.name_dialog.layout().setContentsMargins(2,2,2,2)
        self.name_dialog.layout().setHorizontalSpacing(2)
        self.name_dialog.layout().setVerticalSpacing(2)

        logger.info('Setting name filter...')
        self.name_dialog.setNameFilter("Text Files (*.swiftir)")
        self.name_dialog.setLabelText(QFileDialog.Accept, "Create")
        self.name_dialog.setViewMode(QFileDialog.Detail)
        self.name_dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.name_dialog.setModal(True)
        # self.name_dialog.setFilter(QDir.AllEntries | QDir.Hidden)

        logger.info('Getting sidebar URLs...')
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

        logger.info('Settings sidebar URLs...')
        self.name_dialog.setSidebarUrls(urls)

        places = getSideBarPlacesProjectName()
        # print(str(places))

        sidebar = self.name_dialog.findChild(QListView, "sidebar")
        delegate = StyledItemDelegate(sidebar)
        delegate.mapping = places
        sidebar.setItemDelegate(delegate)

        self.iid_dialog = ImportImagesDialog()
        self.iid_dialog.filesSelected.connect(self.updateImportImagesUI)
        self.iid_dialog.setAutoFillBackground(True)
        self.iid_dialog.hide()

        self.leNameImages = QLineEdit()
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
        self.bSelect.setCursor(QCursor(Qt.PointingHandCursor))
        self.bSelect.clicked.connect(self.selectImages)

        self.bCancel = QPushButton()
        self.bCancel.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCancel.setFixedSize(QSize(18, 18))
        self.bCancel.setIcon(qta.icon('fa.close', color='#161c20'))
        def fn():
            self.gbCreateImages.hide()
            self.iid_dialog.hide()
            # self.showMainUI()
            self._NEW_IMAGES_PATHS = []
        self.bCancel.clicked.connect(fn)

        self.bCreateImages = QPushButton("Create")
        self.bCreateImages.setCursor(QCursor(Qt.PointingHandCursor))
        self.bCreateImages.clicked.connect(self.createImages)
        self.bCreateImages.setEnabled(False)
        self.wNameImages = HW(QLabel('Images Name:'), self.leNameImages, self.bSelect, self.bCreateImages, self.bCancel)
        # self.wNameImages.setStyleSheet("QLabel {color: #f3f6fb;} ")
        self.wNameImages.layout.setSpacing(2)
        self.wNameImages.layout.setContentsMargins(0, 0, 0, 0)

        bs = [self.bSelect, self.bCreateImages]
        for b in bs:
            b.setFixedSize(QSize(78,18))

        self.wImagesConfig = ImagesConfig(parent=self)
        self.wImagesConfig.layout().setSpacing(4)

        self.labImgCount = QLabel()
        self.labImgCount.setStyleSheet("color: #339933;")
        self.labImgCount.hide()
        self.cbCalGrid = QCheckBox('Image 0 is calibration grid')
        self.cbCalGrid.setChecked(False)
        self.wMiddle = HW(ExpandingHWidget(self), self.labImgCount, QLabel('  '),self.cbCalGrid)
        vbl = VBL(self.wNameImages, self.wMiddle, self.wImagesConfig)
        vbl.setSpacing(4)
        self.gbCreateImages = QGroupBox()
        self.gbCreateImages.setLayout(vbl)
        self.gbCreateImages.hide()

        self.wOverlay = VW(self.iid_dialog)
        self.wOverlay.layout.setContentsMargins(18, 12, 18, 18)
        self.wOverlay.layout.setSpacing(4)
        self.wOverlay.layout.setAlignment(Qt.AlignTop)
        self.wOverlay.adjustSize()

        self.wOverlay.layout.setAlignment(Qt.AlignTop)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.glMain = QGridLayout()
        self.glMain.setContentsMargins(0,0,0,0)
        self.glMain.addWidget(self.webengine, 0, 0, 4, 3)
        self.glMain.addWidget(self.wOverlay, 0, 0, 1, 3)
        self.glMain.setRowStretch(1,9)

        self._wProjects = QWidget()
        self._wProjects.setContentsMargins(0,0,0,0)
        self._wProjects.setLayout(self.glMain)

        self.vlPM = VerticalLabel('Alignment Manager')
        self.wProjects = HW(self.vlPM, VW(self.toolbar, self.gbCreateImages, self.wNameAlignment, self._wProjects))

        self._hsplitter = HSplitter()
        self._hsplitter.addWidget(self.wProjects)
        self._hsplitter.addWidget(self.filebrowser)
        self._hsplitter.setSizes([int(cfg.WIDTH * (8/10)), int(cfg.WIDTH * (2/10))])
        self._hsplitter.setStretchFactor(0,1)
        self._hsplitter.setStretchFactor(1,1)
        self._hsplitter.setCollapsible(0, False)
        self._hsplitter.setCollapsible(1, False)

        self.vbl_main = VBL()
        self.vbl_main.setSpacing(0)
        self._vw = VW()

        self.vbl_main.addWidget(self._hsplitter)

        self.setLayout(self.vbl_main)

        # if self.cmbSelectImages.currentText():
        #     self.wSelectAlignment.setVisible(True)


    def resetView(self):
        logger.info('')
        # self.leNameImages.setText('')
        # self.leNameAlignment.setText('')
        self.leNameImages.setStyleSheet("border-color: #339933; border-width: 2px;")
        self.bSelect.setStyleSheet("background-color: #339933; color: #f3f6fb; border-color: #f3f6fb;")
        self.bCreateImages.setStyleSheet("")
        # self.leNameAlignment.setStyleSheet("border-color: #339933; color: #f3f6fb; border-width: 2px;")
        self.gbCreateImages.hide()
        self.labImgCount.hide()
        self.iid_dialog.hide()
        self.wNameAlignment.hide()
        self.bPlusAlignment.setEnabled(True)


    def getDict(self, path):
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    data=json.load(f)
                return data
            except json.decoder.JSONDecodeError:
                logger.warning(f'JSON decoder error: {path}')
        return None


    def getScaleKeys(self, x):
        logger.info('')
        basename,_ = os.path.splitext(os.path.basename(x))
        info_path = os.path.join(x, 'info.json')
        if os.path.isfile(info_path):
            info = self.getDict(info_path)
            return natural_sort(info['levels'])
        else:
            return []


    def _getUUID(self, p):
        name,_ = os.path.splitext(os.path.basename(p))
        path = os.path.join(p, name + '.swiftir')
        uuid = None
        if os.path.exists(path):
            try:
                data = self.getDict(path)
                assert isinstance(data,dict)
            except AssertionError:
                logger.warning(f'Unable to access project data model at {p}')
                return None
            try:
                uuid = data['info']['series_uuid']
            except json.decoder.JSONDecodeError:
                logger.warning('JSON decoder error!')
        else:
            logger.warning(f"path does not exist: {path}")
        return uuid


    def _getImagesName(self):
        return os.path.basename(self.cmbSelectImages.currentText())


    def _getImagesUUID(self, p):
        # logger.info('')
        path = os.path.join(p, 'info.json')
        if os.path.exists(path):
            try:
                uuid = self.getDict(path)['uuid']
                return uuid
            except json.decoder.JSONDecodeError:
                logger.warning('JSON decoder error!')


    #importseries
    def createImages(self):
        logger.info("")
        self.resetView()
        self.bCreateImages.setEnabled(False)
        self.bCreateImages.setStyleSheet("")
        self.bSelect.setStyleSheet("")

        name = self.leNameImages.text()
        name.replace(' ', '_')
        if not name.endswith('.images'):
            name += '.images'

        out = os.path.join(cfg.preferences['images_root'], name)

        zarr_settings = self.wImagesConfig.getSettings()
        # logger.info(f"Scale levels & Zarr preferences:\n{zarr_settings}")
        try:
            logger.info(f"Scale levels & Zarr preferences:\n{json.dumps(zarr_settings, indent=4)}")
        except:
            print_exception()

        logpath = os.path.join(out, 'logs')
        os.makedirs(logpath, exist_ok=True)
        # open(os.path.join(logpath, 'exceptions.log'), 'a').close()

        cal_grid_path = None
        has_cal_grid = self.cbCalGrid.isChecked()
        if has_cal_grid:
            logger.info('Linking to calibration grid image...')
            cal_grid_path = self._NEW_IMAGES_PATHS[0]
            cal_grid_name = os.path.basename(cal_grid_path)
            self._NEW_IMAGES_PATHS = self._NEW_IMAGES_PATHS[1:]
            logger.info('Copying calibration grid image...')
            shutil.copyfile(cal_grid_path, os.path.join(out, cal_grid_name))

        src = os.path.dirname(self._NEW_IMAGES_PATHS[0])
        cfg.mw.tell(f'Importing {len(self._NEW_IMAGES_PATHS)} Images...')
        scales_str = self.wImagesConfig.scales_input.text().strip()
        scale_vals = list(map(int,scales_str.split(' ')))
        # makedirs_exist_ok(dirname, exist_ok=True)
        tiff_path = os.path.join(out, 'tiff')
        zarr_path = os.path.join(out, 'zarr')
        thumbs_path = os.path.join(out, 'thumbs')

        for sv in scale_vals:
            cfg.mw.tell('Making directory structure for level %d...' % sv)
            os.makedirs(os.path.join(tiff_path,   's%d' % sv), exist_ok=True)
            os.makedirs(os.path.join(zarr_path,   's%d' % sv), exist_ok=True)
            os.makedirs(os.path.join(thumbs_path, 's%d' % sv), exist_ok=True)

        logger.info(f"# Imported: {len(self._NEW_IMAGES_PATHS)}")

        t0 = time.time()
        logger.info('Symbolically linking full scale images...')
        self.parent.tell('Symbolically linking full scale images...')
        for img in self._NEW_IMAGES_PATHS:
            fn = img
            ofn = os.path.join(out, 'tiff', 's1', os.path.split(fn)[1])
            # normalize path for different OSs
            if os.path.abspath(os.path.normpath(fn)) != os.path.abspath(os.path.normpath(ofn)):
                try:
                    os.unlink(ofn)
                except:
                    pass
                try:
                    os.symlink(fn, ofn)
                except FileNotFoundError:
                    # print_exception()
                    logger.warning(f"File not found: {fn}. Unable to link, copying instead." )
                    try:
                        shutil.copy(fn, ofn)
                    except:
                        logger.warning("Unable to link or copy from " + fn + " to " + ofn)
        dt = time.time() - t0
        logger.info(f'Elapsed Time (linking): {dt:.3g} seconds')

        count = len(self._NEW_IMAGES_PATHS)
        # level_keys = natural_sort(['s%d' % v for v in scale_vals])[::-1]
        level_keys = natural_sort(['s%d' % v for v in scale_vals])
        series_name = os.path.basename(out)
        logger.critical(f"Resolution levels: {level_keys}")

        opts = {
            'name': series_name,
            'uuid': str(uuid.uuid4()),
            # 'images_location': out,
            'created': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
            'scale_factors': scale_vals,
            'levels': level_keys,
            'count': count,
            'cal_grid': {
                'has': has_cal_grid,
                'path': cal_grid_path,
            },
            'paths': self._NEW_IMAGES_PATHS,
        }
        opts.update(self.wImagesConfig.getSettings())
        logger.info(pformat(opts))

        full_scale_size = ImageSize(self._NEW_IMAGES_PATHS[0])
        opts['size_zyx'] = {}
        opts['size_xy'] = {}
        for sv in scale_vals:
            key = 's%d' % sv
            siz = tuple((np.array(full_scale_size) / sv).astype(int).tolist())
            opts['size_zyx'][key] = (count, siz[1], siz[0])
            opts['size_xy'][key] = siz

        siz_x, siz_y = ImageSize(opts['paths'][1])
        # siz_x, siz_y = ImageIOSize(next(absFilePaths(src)))
        sf = int(max(siz_x, siz_y) / cfg.TARGET_THUMBNAIL_SIZE)
        opts['thumbnail_scale_factor'] = sf
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        with open(os.path.join(out, 'info.json'), 'w') as f:
            f.write(jde.encode(copy.deepcopy(opts)))
        cfg.mw.autoscaleImages(src, out, opts)
        cfg.preferences['images_combo_text'] = out
        logger.info('done')


    # importalignment
    def createAlignment(self):
        logger.info('')
        self.bPlusAlignment.setEnabled(False)
        self.resetView()
        # name         = self.leNameAlignment.text()
        name         = self.leNameAlignment.text()
        if not name.endswith('.alignment'):
            name += '.alignment'

        out = os.path.join(cfg.preferences['alignments_root'], name)

        images_path = self.cmbSelectImages.currentText()
        series_name,_ = os.path.splitext(os.path.basename(images_path))
        series_info_path = os.path.join(images_path, 'info.json')

        if not os.path.isfile(series_info_path):
            cfg.mw.warn(f"Series data file not found: {series_info_path}. Was it moved?")
            print(series_info_path)
            self.resetView()
            return
        if not os.path.isdir(images_path):
            cfg.mw.warn(f"Series not found: {images_path}. Was this images moved?")
            self.resetView()
            return
        if os.path.exists(out):
            cfg.mw.warn(f"An alignment data file with this name already exists in the content root!")
            self.resetView()
            return

        with open(series_info_path) as f:
            info = json.load(f)

        logger.info(f"Initializing Data Model...\n"
                        f"  alignment name : {name}\n"
                        f"       of images : {series_name}\n"
                        f"           count : {info['count']}")

        t0 = time.time()
        #Todo also need to pass in the images location, which may have moved
        dm = DataModel(data_location=out, images_location=images_path, initialize=True, images_info=info)
        dt = time.time() - t0
        logger.info(f'Time Elapsed (initialize data model): {dt:.3g}s')

        initLogFiles(out)
        # makedirs_exist_ok(out, exist_ok=True)
        # os.makedirs(out, exist_ok=True)
        os.makedirs(os.path.join(out, 'data'), exist_ok=True)
        logger.info(f"Out:\n{out}")
        logger.info(f"Levels: {info['levels']}")
        n = info['count']

        cfg.mw.hud('Generating directory structure for alignment data...')
        for k in info['levels']:
            os.makedirs(os.path.join(out, 'zarr',        k), exist_ok=True)
        for i in range(n):
            # logger.info(f"creating {os.path.join(out, 'zarr', k)}")
            for k in info['levels']:
                os.makedirs(os.path.join(out, 'data', str(i), k), exist_ok=True)

        cfg.mw._saveProjectToFile()
        self.bPlusAlignment.setEnabled(True)
        cfg.mw.onStartProject(dm, switch_to=True)



    def refresh(self):
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Refreshing...")
        self.resetView() #0830+
        self.updateCombos()
        self.initPMviewer()


    def initPMviewer(self):
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        self.viewer = cfg.pmViewer = PMViewer(webengine=self.webengine)
        if self.cmbSelectImages.currentText():
            self.path_l, self.path_r = self.get_pmviewer_paths()
            self.viewer.initViewer(path_l=self.path_l, path_r=self.path_r)
            # self.viewer.initZoom(w=w, h=h)
        else:
            self.viewer.initViewer(path_l=None, path_r=None)
            # self.viewer.initZoom(w=w, h=h)


    def onPlusAlignment(self):
        logger.info('')
        if self.wNameAlignment.isVisible():
            self.wNameAlignment.hide()
            return
        if not os.path.isdir(self.cmbSelectImages.currentText()):
            cfg.mw.warn(f"'{self.cmbSelectImages.currentText()}' is not a valid images.")
            return
        self.wNameAlignment.show()
        self.leNameAlignment.setFocus()


    def onMinusAlignment(self):
        logger.info('')
        path = self.cmbSelectAlignment.currentText()
        if path:
            if os.path.isdir(path):
                logger.warning(f"Removing alignment at: {path}...")
                reply = QMessageBox.question(self, "Quit", f"Delete this alignment?\n\n'{path}'",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    cfg.mw.tell(f'Starting subprocess: removing {path}...')
                    try:
                        if path.endswith('.alignment'):
                            run_subprocess(["rm", "-rf", path])
                        else:
                            logger.warning(f"\n\nCANNOT REMOVE THIS PATH: {path}\n")
                    except:
                        print_exception()
                    self.updateCombos()
                    # if cfg.preferences['images_combo_text']:
                    #     logger.critical(f"cfg.preferences['images_combo_text'] = {cfg.preferences['images_combo_text']}")
                    #     if os.path.exists(cfg.preferences['images_combo_text']):
                    #         self.cmbSelectImages.setCurrentText(cfg.preferences['images_combo_text'])
                    self.resetView()
                    self.initPMviewer()
            else:
                cfg.mw.warn('Path not found.')
        else:
            cfg.mw.warn('No alignment selected.')


    def onOpenAlignment(self):
        logger.info('')
        alignment_dir = self.cmbSelectAlignment.currentText()
        images_location = self.cmbSelectImages.currentText()
        if alignment_dir:
            name,_ = os.path.splitext(os.path.basename(alignment_dir))
            swiftir_file = os.path.join(alignment_dir, name + '.swiftir')
            if not os.path.exists(swiftir_file):
                cfg.mw.warn(f"Alignment data file not found: {swiftir_file}")
                self.resetView()
                return
            if not os.path.exists(alignment_dir):
                cfg.mw.warn(f"Alignment data not found: {alignment_dir}")
                self.resetView()
                return
            cfg.mw.tell(f"Opening: {swiftir_file}...")
            self.openAlignment(path=swiftir_file, data_location=alignment_dir, images_location=images_location)
        else:
            cfg.mw.warn("No alignment selected.")

    def onMinusImages(self):
        path = self.cmbSelectImages.currentText()
        if os.path.isdir(path):
            cfg.mw.tell(f'Starting subprocess: removing {path}...')
            logger.warning(f"Removing images at: {path}...")
            reply = QMessageBox.question(self, "Quit", f"Delete this images?\n\n'{path}'",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    if path.endswith('.images'):
                        cfg.mw.tell(f'Deleting images {path}...')
                        run_subprocess(["rm", "-rf", path])
                    else:
                        logger.warning(f"\n\nCANNOT REMOVE THIS PATH: {path}\n")
                except:
                    print_exception()

        else:
            cfg.mw.warn(f"Images not found: {path}")
        logger.info('Sleeping for 3 seconds...')
        time.sleep(3)
        self.refresh()

    def _updateWatchPaths(self):
        logger.info('')
        [self._watchImages.watch(sp) for sp in cfg.preferences['images_search_paths']]
        [self._watchAlignments.watch(sp) for sp in cfg.preferences['alignments_search_paths']]



    def updateCombos(self):
        '''Loading this combobox triggers the loading of the alignment and scales comboboxes'''
        caller = inspect.stack()[1].function
        logger.info(f'[{caller}]')
        shown = [self.cmbSelectImages.itemText(i) for i in range(self.cmbSelectImages.count())]
        known = self._watchImages.known
        if sorted(shown) == sorted(known):
            logger.info(".images combobox is current!"); return
        self.cmbSelectImages.clear()
        self.cmbSelectImages.addItems(known)
        mem = cfg.preferences['images_combo_text']
        if mem in known:
            self.cmbSelectImages.setCurrentText(mem)
        _im_path = self.cmbSelectImages.currentText()
        _im_name = os.path.basename(_im_path)
        al_known = self._watchAlignments.known
        if os.path.exists(str(_im_path)):
            logger.critical(f"alignments known: {al_known}")
            if len(al_known) == 0:
                self.cmbSelectAlignment.setPlaceholderText(f"No Alignments (.alignment) Found for '{_im_name}'")
            else:
                self.cmbSelectAlignment.setPlaceholderText(f"{len(al_known)} Alignments (.alignment) of '{_im_name}' Found")
        else:
            self.cmbSelectAlignment.setPlaceholderText("")

        self.loadLevelsCombo()
        self.loadAlignmentCombo()
        self.update()

    def loadAlignmentCombo(self):
        logger.info('')
        cur_items = [self.cmbSelectAlignment.itemText(i) for i in range(self.cmbSelectAlignment.count())]
        if sorted(cur_items) == sorted(self._watchAlignments.known):
            logger.info(".alignments combobox is current!"); return
        _im_path = self.cmbSelectImages.currentText()
        _im_name = os.path.basename(_im_path)
        _uuid = self._getImagesUUID(_im_path)
        known = self._watchAlignments.known
        valid = [p for p in known if self._getUUID(p) == _uuid]
        self.cmbSelectAlignment.clear()
        self.cmbSelectAlignment.addItems(valid)
        mem = cfg.preferences['alignment_combo_text']
        if mem in valid:
            self.cmbSelectAlignment.setCurrentText(mem)
        logger.critical(f"valid: {valid} (?)")
        if os.path.exists(str(_im_path)):
            if len(valid):
                self.cmbSelectAlignment.setPlaceholderText(f"{len(valid)} Alignments (.alignment) of '{_im_name}' Found")
            else:
                self.cmbSelectAlignment.setPlaceholderText(f"No Alignments (.alignment) of '{_im_name}' Found")
        else:
            self.cmbSelectAlignment.setPlaceholderText("")


    def loadLevelsCombo(self):
        logger.info('')
        self.cmbLevel.clear()
        cur_series = self.cmbSelectImages.currentText()
        if cur_series:
            scales = self.getScaleKeys(x=cur_series)
            if scales:
                self.cmbLevel.addItems(scales)
                self.cmbLevel.setCurrentIndex(self.cmbLevel.count() - 1)

    # def setCurrentImages(self):
    #     logger.info('')
    #     self._fsWatcher = FsWatcher(extension='.alignments')


    def onSelectImagesCombo(self):
        logger.info('')
        caller = inspect.stack()[1].function
        if caller == 'main':
            if self.cmbSelectImages.currentText():
                self.resetView()
                cfg.preferences['images_combo_text'] = self.cmbSelectImages.currentText()
                try:
                    self.loadLevelsCombo() #Important load the scale levels combo before initializing viewers
                except:
                    print_exception()
                self.loadAlignmentCombo()

                w, h = int(self.webengine.width() / 2), self.webengine.height()
                if self.cmbSelectImages.currentText():
                    self.viewer = cfg.pmViewer = PMViewer(webengine=self.webengine)
                    self.path_l, self.path_r = self.get_pmviewer_paths()
                    self.viewer.initViewer(path_l=self.path_l, path_r=self.path_r)
                    # self.viewer.initZoom(w=w, h=h)
                #     self.wSelectAlignment.setVisible(True)
                # else:
                #     self.wSelectAlignment.setVisible(False)
                self.webengine.setFocus()

    def onComboLevel(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            self.initPMviewer()

    def onSelectAlignmentCombo(self):
        caller = inspect.stack()[1].function
        if caller == 'main':
            logger.info(f"[{caller}]")
            cfg.preferences['alignment_combo_text'] = self.cmbSelectAlignment.currentText()
            self.gbCreateImages.hide()
            # self.loadAlignmentCombo()
            self.webengine.setFocus()

    def get_pmviewer_paths(self):
        self.path_l, self.path_r = None, None
        try:
            images = self.cmbSelectImages.currentText()
            alignment = self.cmbSelectAlignment.currentText()
            scale = self.cmbLevel.currentText()
            keys = self.getScaleKeys(x=images)
            if scale:
                scale = keys[-1]
                logger.info(f"scale to set: {scale}")
                if self.cmbSelectImages.count() > 0:
                    self.path_l = os.path.join(images, 'zarr', scale)
                    # if self.cmbSelectAlignment.currentText() != 'None':
                    if self.cmbSelectAlignment.currentText():
                        # coarsest_aligned = self.getCoarsestAlignedScale(alignment_file)
                        self.path_r = os.path.join(alignment, 'zarr', scale)
        except:
            print_exception()
        return self.path_l, self.path_r


    # def onComboLevel(self):
    #     pass

    def openAlignment(self, path=None, data_location=None, images_location=None):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        logger.info(f"Loading: {path}")
        if path == None:
            path = self.selectionReadout.text()
        if validate_zarr_selection(path):
            logger.info('Opening Zarr...')
            self.open_zarr_selected()
            return
        elif validate_project_selection(path):

            if cfg.mw.isProjectOpen(path):
                cfg.mw.globTabs.setCurrentIndex(cfg.mw.getProjectIndex(path))
                cfg.mw.warn(f'Project {os.path.basename(path)} is already open.')
                return

            fn, ext = os.path.splitext(path)
            if ext == '.json':
                logger.info('Opening OLD alignEM project')
                new_name = fn + '.swiftir'
                print(f"new name: {new_name}")
                with open(path, 'r') as f:
                    data = json.load(f)
                    al_stack = data['data']['scales']['scale_1']['alignment_stack']
                    imgs = []
                    for l in al_stack:
                        imgs.append(os.path.dirname(new_name) + '/' + l['images']['base']['path'])
                    print(imgs)
                    self.NEW_PROJECT_IMAGES = imgs
                    self.NEW_PROJECT_PATH = new_name
                    self.new_project(skip_to_config=True)
                    # print(json.dumps(data, indent=4))
                return
            logger.info(f'Opening {path}...')

            if not os.path.exists(path):
                logger.warning("File not found!");
                return
            if os.path.getsize(path) == 0:
                logger.warning("File is empty!");
                return

            try:
                with open(path, 'r') as f:
                    dm = cfg.data = DataModel(data=json.load(f), data_location=data_location, images_location=images_location)
                # dm.set_defaults()
                cfg.mw._autosave()
            except:
                cfg.mw.warn(f'No Such File Found: {path}')
                print_exception()
                return
            else:
                logger.info(f'Project Opened!')

            initLogFiles(dm.data_location)  # 0805+
            cfg.mw.saveUserPreferences(silent=True)
            cfg.mw.onStartProject(dm, switch_to=True)

        else:
            cfg.mw.warn("Invalid Path")


    def showMainUI(self):
        logger.info('')
        self.gbCreateImages.hide()
        self.update()

    def validate_path(self):
        # logger.info(f'caller:{inspect.stack()[1].function}')
        path = self.selectionReadout.text()
        # logger.info(f'Validating path : {path}')
        if validate_project_selection(path):
            self._buttonOpen.setText(f"Open Project {hotkey('O')}")
            logger.info(f'path is a valid AlignEM project')
            self.validity_label.hide()
            self._buttonOpen.setEnabled(True)

        elif validate_zarr_selection(path):
            self._buttonOpen.setText(f"Open Zarr {hotkey('O')}")
            self.validity_label.hide()

        elif validate_tiff_folder(path):
            self._buttonProjectFromTiffFolder1.setEnabled(True)
            self.cbCalGrid.show()
            self.validity_label.hide()

        elif path == '':
            self.validity_label.hide()

        else:
            self.validity_label.show()
            self._buttonProjectFromTiffFolder1.setEnabled(False)
            self.cbCalGrid.hide()
            self._buttonOpen.setEnabled(False)
            self._buttonDelete.setEnabled(False)
            # self._buttonOpen.hide()
            # self._buttonDelete.hide()



    def showImportSeriesDialog(self):
        self.setUpdatesEnabled(False)
        isShown = self.gbCreateImages.isVisible()
        self.resetView()
        self.leNameImages.setStyleSheet(("border-color: #339933; border-width: 2px;", "border-color: #f3f6fb;")[bool(
            self.leNameImages.text(
        ))])
        self.gbCreateImages.setVisible(not isShown)
        if self.gbCreateImages.isVisible():
            self.wImagesConfig.leResX.setText(str(cfg.DEFAULT_RESX))
            self.wImagesConfig.leResY.setText(str(cfg.DEFAULT_RESY))
            self.wImagesConfig.leResZ.setText(str(cfg.DEFAULT_RESZ))
            self.wImagesConfig.leChunkX.setText(str(cfg.CHUNK_X))
            self.wImagesConfig.leChunkY.setText(str(cfg.CHUNK_Y))
            self.wImagesConfig.leChunkZ.setText(str(cfg.CHUNK_Z))
            self.wImagesConfig.cname_combobox.setCurrentText(str(cfg.CNAME))
        self.leNameImages.setFocus(True)
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


    def selectImages(self):
        # self.iid_dialog = ImportImagesDialog()
        # self.iid_dialog.resize(QSize(820,480))
        # self.bSelect.setStyleSheet("background-color: #339933; color: #f3f6fb; border-color: #f3f6fb;")
        self.bCreateImages.setStyleSheet("")

        if self.iid_dialog.isVisible():
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
            if len(filenames) > 0:
                # self.labImgCount.setText(f"{len(filenames)} images selected from {os.path.dirname(filenames[0])}")
                self.labImgCount.setText(f"{len(filenames)} images selected  ")
                self.labImgCount.show()
                self.bSelect.setStyleSheet("")
                if self.leNameImages.text():
                    self.bCreateImages.setStyleSheet("background-color: #339933; color: #f3f6fb; border-color: #f3f6fb;")

            self.iid_dialog.pixmap = None
        else:
            cfg.mw.warn('Import images dialog did not return a valid file list')
            self.showMainUI()
            self.iid_dialog.pixmap = None
            return 1

        if filenames == 1:
            cfg.mw.warn('No Project Canceled')
            self.showMainUI()
            return 1

        self._NEW_IMAGES_PATHS = natural_sort(filenames)
        self.updateImportImagesUI()
        logger.info(f"<<<< selectImages <<<<")


    def setSelectionPathText(self, path):
        # logger.info('')
        self.selectionReadout.setText(path)
        self._buttonProjectFromTiffFolder1.setEnabled(validate_tiff_folder(path))
        self.cbCalGrid.setVisible(validate_tiff_folder(path))

        if validate_project_selection(path) | validate_zarr_selection(path):
            self.validity_label.hide()
            self._buttonOpen.setEnabled(True)
            self._buttonDelete.setEnabled(True)
        else:
            self.validity_label.show()
            self._buttonOpen.setEnabled(False)
            self._buttonDelete.setEnabled(False)


    def open_zarr_selected(self):
        # path = self.selected_file
        path = self.selectionReadout.text()
        logger.info("Opening Zarr '%s'..." % path)
        try:
            with open(os.path.join(path, '.zarray')) as j:
                self.zarray = json.load(j)
        except:
            print_exception()
            return
        tab = ZarrTab(self, path=path)
        cfg.mw.addGlobTab(tab, os.path.basename(path))
        cfg.mw._setLastTab()


    def deleteContextMethod(self):
        logger.info('')
        selected_projects = self.getSelectedProjects()
        self.delete_projects(project_files=selected_projects)

    def openContextMethod(self):
        logger.info('')
        self.openAlignment()


    def delete_projects(self, project_files=None):
        logger.info('')
        if project_files == None:
            project_files = [self.selectionReadout.text()]

        for project_file in project_files:
            if project_file != '':
                if validate_project_selection(project_file):

                    project = os.path.splitext(project_file)[0]

                    cfg.mw.tell("Delete this project? %s" % project_file)
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
                        cfg.mw.tell('Canceling Delete Project Permanently Instruction...')
                        return
                    if reply == QMessageBox.Ok:
                        logger.info('Deleting file %s...' % project_file)
                        cfg.mw.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)

                    cfg.mw.tell(f'Deleting project file {project_file}...')

                    try:
                        os.remove(project_file)
                    except:
                        print_exception()
                    # else:
                    #     cfg.mw.hud.done()

                    # configure_project_paths()
                    # self.user_projects.set_data()

                    cfg.mw.tell(f'Deleting alignment at {project}...')
                    try:
                        run_subprocess(["rm","-rf", project])
                        # delete_recursive(dir=project)
                        # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
                        # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
                    except:
                        cfg.mw.warn('An Error Was Encountered During Deletion of the Project Directory')
                        print_exception()
                    else:
                        cfg.mw.hud.done()

                    # cfg.mw.tell('Wrapping up...')
                    # configure_project_paths()
                    # if cfg.mw.globTabs.currentWidget().__class__.__name__ == 'OpenProject':
                    #     try:
                    #         self.user_projects.set_data()
                    #     except:
                    #         logger.warning('There was a problem updating the project list')
                    #         print_exception()

                    self.selectionReadout.setText('')

                    cfg.mw.tell('Deletion Complete!')
                    logger.info('Deletion tasks finished')
                else:
                    logger.warning('(!) Invalid target for deletion: %s' % project_file)


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
    #         #     # path = self.getSelectedProjects()[0]
    #         #     path = self.getSelectedProjects()[0]
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


# class TableWidget(QTableWidget):
#     def __init__(self, parent=None):
#         # super(TableWidget, self).__init__(parent)
#         super().__init__()
#         self.parent = parent
#
#     def keyPressEvent(self, event):
#         print(event.key())
#         if event.key() == Qt.Key_Delete:
#             # self.parent.parent.delete_projects()
#             cfg.mw._getTabObject().delete_projects()
#         else:
#             super().keyPressEvent(event)


#
# class UserProjects(QWidget):
#     def __init__(self, parent, **kwargs):
#         super().__init__(**kwargs)
#         self.parent = parent
#
#         # self.initial_row_height = 64
#         # self.ROW_HEIGHT = 64
#         self.ROW_HEIGHT = 64
#
#         self.counter1 = 0
#         self.counter2 = 0
#         # self.counter3 = 0
#         # self.setFocusPolicy(Qt.StrongFocus)
#
#         self.data = QTableWidget()
#         self.data.setFocusPolicy(Qt.NoFocus)
#         self.data.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         # self.data.setAlternatingRowColors(True)
#         # self.data = TableWidget(self)
#
#         # self.data.setShowGrid(False)
#         self.data.setSortingEnabled(True)
#         self.data.setWordWrap(True)
#         self.data.horizontalHeader().setHighlightSections(False)
#         self.data.horizontalHeader().setStretchLastSection(True)
#         self.data.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self.data.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self.data.verticalHeader().setVisible(False)
#         # self.data.horizontalHeader().setDefaultAlignment(Qt.Alignment(Qt.TextWordWrap))
#         self.data.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
#         def countCurrentItemChangedCalls(): self.counter2 += 1
#         self.data.currentItemChanged.connect(countCurrentItemChangedCalls)
#         self.data.currentItemChanged.connect(self.parent.userSelectionChanged)
#         def countItemClickedCalls(): self.counter1 += 1
#         self.data.itemClicked.connect(countItemClickedCalls)
#         self.data.itemClicked.connect(self.parent.userSelectionChanged)
#         # def onDoubleClick(): self.parent.openAlignment()
#         # self.data.itemDoubleClicked.connect(self.parent.openAlignment)
#         self.data.doubleClicked.connect(self.parent.openAlignment) #Critical this always emits
#         self.data.itemSelectionChanged.connect(self.parent.userSelectionChanged)  # Works!
#         # self.data.itemSelectionChanged.connect(lambda: print('itemselectionChanged was emitted!'))  # Works!
#         # self.data.itemPressed.connect(lambda: print('itemPressed was emitted!'))
#         # self.data.cellActivated.connect(lambda: print('cellActivated was emitted!'))
#         # self.data.currentItemChanged.connect(lambda: print('currentItemChanged was emitted!'))
#         # self.data.itemDoubleClicked.connect(lambda: print('itemDoubleClicked was emitted!'))
#         # self.data.cellChanged.connect(lambda: print('cellChanged was emitted!'))
#         # self.data.cellClicked.connect(lambda: print('cellClicked was emitted!'))
#         # self.data.itemChanged.connect(lambda: print('itemChanged was emitted!'))
#
#         self.data.setColumnCount(11)
#         self.set_headers()
#
#         self.layout = QVBoxLayout()
#         self.layout.setContentsMargins(0, 0, 0, 0)
#         self.layout.addWidget(self.data)
#         # self.layout.addWidget(controls)
#         self.setLayout(self.layout)
#         self.set_data()
#
#         self.data.setMouseTracking(True)
#
#         self.current_hover = [0, 0]
#         self.data.cellEntered.connect(self.cellHover)
#
#     def cellHover(self, row, column):
#         self.current_hover = [row, column]
#
#     # btn.clicked.connect(lambda state, x=zpos: self.jump_to_manual(x))
#
#     # def setNotes(self, index, txt):
#     #     caller = inspect.stack()[1].function
#     #     if caller != 'updateNotes':
#     #         self.statusBar.showMessage('Note Saved!', 3000)
#     #
#     #         # cfg.data.save_notes(text=txt, z=index)
#     #     else:
#     #         cfg.preferences['notes']['global_notes'] = self.notes.toPlainText()
#     #     self.notes.update()
#
#
#
#
#     def updateRowHeight(self, h):
#         for section in range(self.data.verticalHeader().count()):
#             self.data.verticalHeader().resizeSection(section, h)
#         self.data.setColumnWidth(1, h)
#         self.data.setColumnWidth(2, h)
#         self.data.setColumnWidth(3, h)
#         # self.data.setColumnWidth(10, h)
#
#
#     # def userSelectionChanged(self):
#     #     caller = inspect.stack()[1].function
#     #     # if caller == 'initTableData':
#     #     #     return
#     #     row = self.data.currentIndex().row()
#     #     try:
#     #         path = self.data.item(row,9).text()
#     #     except:
#     #         cfg.selected_file = ''
#     #         logger.warning(f'No file path at project_table.currentIndex().row()! '
#     #                        f'caller: {caller} - Returning...')
#     #         return
#     #     logger.info(f'path: {path}')
#     #     cfg.selected_file = path
#     #     cfg.mw.setSelectionPathText(path)
#     #     # logger.info(f'counter1={self.counter1}, counter2={self.counter2}')
#
#
#     def set_headers(self):
#         self.data.setHorizontalHeaderLabels([
#             "Location",
#             "First\nSection",
#             "Last\nSection",
#             "Calibration\nGrid",
#             "Created",
#             "Last\nOpened",
#             "#\nImgs",
#             "Image\nSize (px)",
#             "Disk Space\n(Bytes)",
#             "Disk Space\n(Gigabytes)",
#             "Tags"
#         ])
#
#         header = self.data.horizontalHeader()
#         header.setFrameStyle(QFrame.Box | QFrame.Plain)
#         header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
#         self.data.setHorizontalHeader(header)
#
#
#     def set_data(self):
#         logger.info('')
#
#         configure_project_paths()
#         # logger.info(">>>> set_data >>>>")
#         # caller = inspect.stack()[1].function
#         # logger.info(f'[{caller}]')
#         self.data.clear()
#         self.data.clearContents()
#         font0 = QFont()
#         # font0.setBold(True)
#         font0.setPointSize(9)
#
#         font1 = QFont()
#         # font1.setBold(True)
#         font1.setPointSize(9)
#         self.data.setRowCount(0)
#         for i, row in enumerate(self.get_data()):
#             # logger.info(f'>>>> row #{i} >>>>')
#             self.data.insertRow(i)
#             for j, item in enumerate(row):
#                 if j == 0:
#                     twi = QTableWidgetItem(str(item))
#                     twi.setFont(font1)
#                     self.data.setItem(i, j, twi)
#                 elif j in (1,2,3):
#                     # logger.info(f"j={j}, path={item}")
#                     if item == 'No Thumbnail':
#                         thumbnail = ThumbnailFast(self)
#                         self.data.setCellWidget(i, j, thumbnail)
#                     else:
#                         thumbnail = ThumbnailFast(self, path=item)
#                         self.data.setCellWidget(i, j, thumbnail)
#                 elif j in (4,5):
#                     item.replace("_", " ")
#                     item.replace('-', ':')
#                     # item = item[9:].replace('-', ':')
#                     twi = QTableWidgetItem(item)
#                     twi.setFont(font0)
#                     self.data.setItem(i, j, twi)
#                 elif j in (6,7):
#                     twi = QTableWidgetItem(str(item))
#                     twi.setFont(font0)
#                     # twi.setTextAlignment(Qt.AlignCenter)
#                     self.data.setItem(i, j, twi)
#                 else:
#                     twi = QTableWidgetItem(str(item))
#                     twi.setFont(font0)
#                     self.data.setItem(i, j, twi)
#         self.data.setColumnWidth(0, 220)
#         self.data.setColumnWidth(1, self.ROW_HEIGHT) # <first thumbnail>
#         self.data.setColumnWidth(2, self.ROW_HEIGHT) # <last thumbnail>
#         self.data.setColumnWidth(3, self.ROW_HEIGHT) # <last thumbnail>
#         self.data.setColumnWidth(4, 100)
#         self.data.setColumnWidth(5, 100)
#         self.data.setColumnWidth(6, 36)
#         self.data.setColumnWidth(7, 70)
#         self.data.setColumnWidth(8, 70)
#         self.data.setColumnWidth(9, 70)
#         # self.data.setColumnWidth(10, self.ROW_HEIGHT) # <extra thumbnail>
#         # self.data.setColumnWidth(10, 70) # <extra thumbnail>
#         # self.data.setColumnWidth(10, 100)
#         # self.updateRowHeight(self.ROW_HEIGHT) #0508-
#
#         self.set_headers()
#
#         # logger.info("<<<< set_data <<<<")
#         for section in range(self.data.verticalHeader().count()):
#             self.data.verticalHeader().resizeSection(section, self.ROW_HEIGHT)
#
#         self.data.sortByColumn(4, Qt.DescendingOrder)
#
#         logger.info('----Table Data Set----')
#
#
#
#     def get_data(self):
#         caller = inspect.stack()[1].function
#         logger.info(f'[{caller}]')
#         # logger.info('>>>> get_data >>>>')
#         # logger.info(f'caller: {caller}')
#         self.project_paths = cfg.preferences['projects']
#         # self.project_paths = []
#         projects, thumbnail_first, thumbnail_last, created, modified, \
#         n_sections, images_location, img_dimensions, bytes, gigabytes, extra = \
#             [], [], [], [], [], [], [], [], [], [], []
#
#         logger.info(f'# saved projects: {len(self.project_paths)}')
#         for p in self.project_paths:
#             logger.info(f'Collecting {p}...')
#
#             try:
#                 with open(p, 'r') as f:
#                     dm = DataModel(data=json.load(f), quietly=True)
#             except:
#                 # print_exception()
#                 logger.error('Unable to locate or load data model: %level' % p)
#
#             try:    created.append(dm.created)
#             except: created.append('Unknown')
#             try:    modified.append(dm.modified)
#             except: modified.append('Unknown')
#             try:    n_sections.append(len(dm))
#             except: n_sections.append('Unknown')
#             try:    img_dimensions.append(dm.image_size('scale_1'))
#             except: img_dimensions.append('Unknown')
#             try:    projects.append(os.path.basename(p))
#             except: projects.append('Unknown')
#             project_dir = os.path.splitext(p)[0]
#             try:
#                 if getOpt(lookup='ui,FETCH_PROJECT_SIZES'):
#                     logger.info('Getting project size...')
#                     _bytes = get_bytes(project_dir)
#                     bytes.append(_bytes)
#                     gigabytes.append('%.4f' % float(_bytes / 1073741824))
#                 else:
#                     bytes.append('N/A')
#                     gigabytes.append('N/A')
#             except:
#                 bytes.append('Unknown')
#                 gigabytes.append('Unknown')
#             thumb_path = os.path.join(project_dir, 'thumbnails')
#             absolute_content_paths = list_paths_absolute(thumb_path)
#             try:    thumbnail_first.append(absolute_content_paths[0])
#             except: thumbnail_first.append('No Thumbnail')
#             try:    thumbnail_last.append(absolute_content_paths[-1])
#             except: thumbnail_last.append('No Thumbnail')
#             try:    images_location.append(p)
#             except: images_location.append('Unknown')
#             extra_toplevel_paths = glob(f'{project_dir}/*.tif')
#             # logger.critical(f"extra_toplevel_paths = {extra_toplevel_paths}")
#             #Todo refactor this
#             # if extra_toplevel_paths != []:
#             if dm['data']['has_cal_grid']:
#                 extra.append(dm['data']['cal_grid_path'])
#             else:
#                 extra.append('No Thumbnail')
#
#         # logger.info('<<<< get_data <<<<')
#         # return zip(projects, images_location, thumbnail_first, thumbnail_last, created, modified,
#         #            n_sections, img_dimensions, bytes, gigabytes, extra)
#         return zip(images_location, thumbnail_first, thumbnail_last, extra, created, modified,
#                    n_sections, img_dimensions, bytes, gigabytes)
#
#             # logger.info('Getting project images_location...')
#         logger.info('<<<<')



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
    # path, extension = os.path.splitext(path)
    # contents = glob(os.path.join(path, '*'))
    # n_files = len(contents)
    # tif_files = glob(os.path.join(path, '*.tif'))
    # tiff_files = glob(os.path.join(path, '*.tiff'))
    # n_valid_files = len(tif_files) + len(tiff_files)
    # n_invalid_files = n_files - n_valid_files
    # # print(f'n_files: {n_files}')
    # # print(f'# valid files: {n_valid_files}')
    # # print(f'# invalid files: {n_invalid_files}')
    # return (n_valid_files > 0) and (n_invalid_files == 0)

    return (len(glob(os.path.join(path, '*.tiff'))) > 0) or (len(glob(os.path.join(path, '*.tif'))) > 0)


def validate_project_selection(path) -> bool:
    logger.info(f'caller:{inspect.stack()[1].function}')
    logger.info('Validating selection %s...' % path)
    # called by setSelectionPathText
    path, extension = os.path.splitext(path)
    # if extension != '.swiftir':
    if extension not in ('.swiftir','.json'):
        logger.info('Returning False')
        return False
    else:
        logger.info('Returning True')
        return True


def validate_zarr_selection(path) -> bool:
    # logger.info(f'caller:{inspect.stack()[1].function}')
    # logger.info('Validating selection %level...' % cfg.selected_file)
    # called by setSelectionPathText
    if os.path.isdir(path):
        if '.zarray' in os.listdir(path):
            # logger.info('Directory contains .zarray -> selection is a valid Zarr')
            return True
    return False


def makedirs_exist_ok(path_to_build, exist_ok=False):
    # Needed for old python which doesn't have the exist_ok option!!!
    logger.info("Making directories for path %s" % path_to_build)
    parts = path_to_build.split(
        os.sep)  # Variable "parts" should be a list of subpath sections. The first will be empty ('') if it was absolute.
    full = ""
    if len(parts[0]) == 0:
        # This happens with an absolute PosixPath
        full = os.sep
    else:
        # This may be a Windows drive or the start of a non-absolute path
        if ":" in parts[0]:
            # Assume a Windows drive
            full = parts[0] + os.sep
        else:
            # This is a non-absolute path which will be handled naturally with full=""
            pass
    for p in parts:
        full = os.path.join(full, p)
        if not os.path.exists(full):
            os.makedirs(full)
        elif not exist_ok:
            pass
            # logger.info("Warning: Attempt to create existing directory: " + full)

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
        # self.setStyleSheet("""font-size: 10px; color: #f3f6fb;""")

    def getSettings(self):

        cfg.main_window.hud('Setting images configuration...')
        logger.info('Setting images configuration...')
        self._settings['scale_factors'] = sorted(list(map(int, self.scales_input.text().strip().split(' '))))
        self._settings['clevel'] = int(self.leClevel.text())
        self._settings['cname'] = self.cname_combobox.currentText()
        chunkshape = (int(self.leChunkZ.text()),
                      int(self.leChunkY.text()),
                      int(self.leChunkX.text()))
        self._settings['chunkshape'] = {}
        self._settings['resolution'] = {}
        # if cfg.data['data']['has_cal_grid']:
        for sv in self._settings['scale_factors']:
            res_x = int(self.leResX.text()) * sv
            res_y = int(self.leResY.text()) * sv
            res_z = int(self.leResZ.text())
            self._settings['resolution']['s%d' % sv] = (res_z, res_y, res_x)
            self._settings['chunkshape']['s%d' % sv] = chunkshape

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

        # wScaling = HW(QLabel('Scale Levels: '), self.scales_input, ExpandingHWidget(self))
        wScaling = HW(QLabel('Scale Levels: '), self.scales_input)
        wScaling.layout.setAlignment(Qt.AlignHCenter)
        # wScaling.layout.setAlignment(Qt.AlignLeft)

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

        labType = QLabel('Compress: ')
        labLevel = QLabel('Level (1-9): ')
        wCompression = HW(labType, self.cname_combobox, QLabel(' '), labLevel, self.leClevel)
        wCompression.layout.setSpacing(4)
        # wCompression.layout.setAlignment(Qt.AlignCenter)

        '''Chunk Shape'''
        self.leChunkX = QLineEdit(self)
        self.leChunkY = QLineEdit(self)
        self.leChunkZ = QLineEdit(self)

        self.leChunkX.setFixedSize(QSize(40, 18))
        self.leChunkY.setFixedSize(QSize(40, 18))
        self.leChunkZ.setFixedSize(QSize(40, 18))
        self.leChunkX.setValidator(QIntValidator())
        self.leChunkY.setValidator(QIntValidator())
        self.leChunkZ.setValidator(QIntValidator())

        l1 = QLabel("x:")
        l1.setAlignment(Qt.AlignRight)
        l2 = QLabel("y:")
        l2.setAlignment(Qt.AlignRight)
        l3 = QLabel("z:")
        l3.setAlignment(Qt.AlignRight)
        few = [HW(l1, self.leChunkX), HW(l2, self.leChunkY), HW(l3, self.leChunkZ)]
        for one in few:
            one.layout.setAlignment(Qt.AlignHCenter)
            one.setStyleSheet("font-size: 9px;")
        self.wChunk = HW(*few)
        self.wChunk.layout.setSpacing(4)
        # self.wChunk.layout.setSpacing(4)
        txt = "The way volumetric data will be stored. Zarr is an open-source " \
              "format for the storage of chunked, compressed, N-dimensional " \
              "arrays with an interface similar to NumPy."
        txt = '\n'.join(textwrap.wrap(txt, width=60))
        wChunk = HW(QLabel('Chunk: '), self.wChunk)
        wChunk.setToolTip(txt)
        wChunk.layout.setAlignment(Qt.AlignCenter)

        hbl = HBL(wScaling, wVoxelSize, wCompression, wChunk, )

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
    def __init__(self, ID='webengine'):
        QWebEngineView.__init__(self)
        self.ID = ID
        self.grabGesture(Qt.PinchGesture, Qt.DontStartGestureOnChildren)


class FileWatcher(QObject):
    fsChanged = Signal(str)

    def __init__(self, extension, preferences, key):
        super().__init__()
        self._extension = extension
        self._preferences = preferences
        self._key = key
        self._searchPaths = preferences[key]
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.onDirChanged)
        self._watcher.directoryChanged.connect(lambda path: print(f"Directory '{path}' changed!"))
        self._watcher.fileChanged.connect(self.onFileChanged)
        self._watcher.fileChanged.connect(lambda path: print(f"File '{path}' changed!"))

        self._known = []

        self._events = {}
        self._updateKnown()

    def _loadSearchPaths(self):
        for path in self._searchPaths:
            self.watch(path)


    def _updateKnown(self):
        # logger.info(f"_updateKnown:")
        self._loadSearchPaths()
        self._known = []
        for path in self.watched:
            found = list(Path(path).glob('*%s' % self._extension))
            self._known.extend(map(str,found))


    @property
    def watched(self):
        return self._watcher.directories() + self._watcher.files()

    @property
    def known(self):
        self._updateKnown()
        return self._known

    def watch(self, path):
        self._watcher.addPath(path)

    def clearWatches(self):
        print('Clearing watch paths...')
        self._watcher.removePaths(self.watched)


    def onDirChanged(self, path):
        self._updateKnown()
        print(f'onDirChanged: {path}')
        self.fsChanged.emit(path)

    def onFileChanged(self, path):
        print(f'onFileChanged: {path}')
        self.fsChanged.emit(path)


class FsWatcher(QObject):
    fsChanged = Signal(str)

    def __init__(self, extension):
        super().__init__()
        self._extension = extension

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.onDirChanged)
        self._watcher.directoryChanged.connect(lambda path: print(f"Directory '{path}' changed!"))
        self._watcher.fileChanged.connect(self.onFileChanged)
        self._watcher.fileChanged.connect(lambda path: print(f"File '{path}' changed!"))

        self._known = []

        self._events = {}
        self._updateKnown()

    def _loadSearchPaths(self):
        logger.info('')
        for path in self._searchPaths:
            self.watch(path)

    def _updateKnown(self):
        logger.critical(f"_updateKnown:")
        self._loadSearchPaths()

        self._known = []
        for path in self.watched:
            print(f"Searching path {path}...")
            found = list(Path(path).glob('*%s' % self._extension))
            print(f"Found: {found}")
            self._known.extend(map(str, found))

    @property
    def watched(self):
        return self._watcher.directories() + self._watcher.files()

    @property
    def known(self):
        return self._known

    def watch(self, path):
        self._watcher.addPath(path)

    def clearWatches(self):
        print('Clearing watch paths...')
        self._watcher.removePaths(self.watched)

    def onDirChanged(self, path):
        self._updateKnown()
        print(f'onDirChanged: {path}')
        self.fsChanged.emit(path)

    def onFileChanged(self, path):
        print(f'onFileChanged: {path}')
        self.fsChanged.emit(path)


def setWebengineProperties(webengine):
    # webengine.preferences().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    # webengine.preferences().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    # webengine.preferences().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
    # webengine.preferences().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    # webengine.preferences().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    pass


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