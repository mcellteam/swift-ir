#!/usr/bin/env python3

import os
import sys
import json
import time
import shutil
import inspect
import logging
import platform
import textwrap
import copy
from glob import glob
from pathlib import Path
import subprocess as sp
import numpy as np
import multiprocessing as mp
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()

from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
# from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QAbstractItemView, \
#     QSplitter, QTableWidget, QTableWidgetItem, QSlider, QGridLayout, QFrame, QPushButton, \
#     QSizePolicy, QSpacerItem, QLineEdit, QMessageBox, QDialog, QFileDialog, QStyle, QStyledItemDelegate, \
#     QListView, QApplication, QScrollArea, QMenu, QAction, QTextEdit, QFormLayout, QGroupBox, QComboBox
# from qtpy.QtCore import Qt, QRect, QUrl, QDir, QSize, QPoint, QEvent
# from qtpy.QtGui import QGuiApplication, QFont, QPixmap, QPainter, QKeySequence, QColor, QBrush, QIntValidator, \
#     QPalette
from qtpy.QtWebEngineWidgets import *
# from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
import qtawesome as qta
from src.ui.file_browser import FileBrowser
from src.ui.file_browser_tacc import FileBrowserTacc
from src.thumbnailer import Thumbnailer
from src.helpers import list_paths_absolute, get_bytes, absFilePaths, getOpt, setOpt, \
    print_exception, configure_project_paths, delete_recursive, natural_sort, is_tacc, \
    is_joel, hotkey, get_appdir, caller_name, initLogFiles, create_project_directories, get_appdir, example_zarr
from src.data_model import DataModel
from src.ui.tab_project import ProjectTab
from src.ui.timer import Timer
from src.ui.tab_zarr import ZarrTab
from src.ui.dialogs import ImportImagesDialog, NewConfigureProjectDialog
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter
from src.ui.tab_project import VerticalLabel
from src.ui.thumbnail import ThumbnailFast
from src.viewer_em import PMViewer

import src.config as cfg

__all__ = ['OpenProject']

logger = logging.getLogger(__name__)


class OpenProject(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setMinimumHeight(100)
        self.filebrowser = FileBrowser(parent=self)
        # self.filebrowsertacc = FileBrowserTacc(parent=self)
        def fn():
            self.selectionReadout.setText(self.filebrowser.getSelectionPath())
        self.filebrowser.treeview.selectionModel().selectionChanged.connect(fn)
        self.filebrowser.controlsNavigation.show()
        # self.user_projects = UserProjects(parent=self)
        self.initUI()
        # self.row_height_slider.setValue(self.user_projects.ROW_HEIGHT)
        self.selected_file = ''
        self._series = None

        clipboard = QGuiApplication.clipboard()
        clipboard.dataChanged.connect(self.onClipboardChanged)
        #Note: when clipboard changes during app out-of-focus, clipboard changed signal gets emitted
        #once focus is returned. This is the ideal behavior.

        # self.setStyleSheet("font-size: 10px; color: #f3f6fb;")
        self.setStyleSheet("font-size: 10px; color: #161c20;")

        self.installEventFilter(self)

        # configure_project_paths()

    def onClipboardChanged(self):
        # print('Clipboard changed!')
        buffer = QApplication.clipboard().text()
        tip = 'Your Clipboard:\n' + '\n'.join(textwrap.wrap(buffer[0:512], width=35)) #set limit on length of tooltip string
        # print('\n' + tip)
        self._buttonBrowserPaste.setToolTip(tip)


    def initUI(self):

        # self.vbl_projects = QVBoxLayout()
        # self.vbl_projects.setSpacing(1)
        # self.vbl_projects.setContentsMargins(2, 2, 2, 2)
        # self.vbl_projects.addWidget(self.user_projects)
        # self.vbl_projects.addWidget(self.controls)
        # # self.userProjectsWidget.setLayout(self.vbl_projects)

        # User Files Widget
        self.userFilesWidget = QWidget()
        lab = QLabel('Open AlignEM-SWIFT Project or...\nOpen OME-NGFF Zarr in Neuroglancer or...\nSelect folder of images for new project...')
        lab.setStyleSheet('font-size: 10px; color: #161c20;')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(4, 4, 4, 4)
        # vbl.addWidget(HWidget(lab))
        vbl.addWidget(self.filebrowser)
        self.userFilesWidget.setLayout(vbl)

        button_size = QSize(94,18)

        self._buttonOpen = QPushButton(f"Open Project {hotkey('O')}")
        self._buttonOpen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonOpen.setShortcut('Ctrl+O')
        self._buttonOpen.setStyleSheet('font-size: 9px;')
        self._buttonOpen.setEnabled(False)
        self._buttonOpen.clicked.connect(self.open_project_selected)
        self._buttonOpen.setFixedSize(button_size)

        self.labNewProject = QLabel(f"New\nAlignment:")
        self.labNewProject.setStyleSheet('font-size: 9px; font-weight: 600; color: #161c20;')
        self.labNewProject.setAlignment(Qt.AlignRight)

        tip = "Create a new project from an existing folder of images. " \
              "Some users find this more convenient than selecting images."
        self._buttonProjectFromTiffFolder1 = QPushButton(f"Select Folder {hotkey('F')}")
        self._buttonProjectFromTiffFolder1.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._buttonProjectFromTiffFolder1.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonProjectFromTiffFolder1.setShortcut('Ctrl+F')
        # self._buttonProjectFromTiffFolder1.setShortcut()
        self._buttonProjectFromTiffFolder1.setStyleSheet('font-size: 9px;')
        self._buttonProjectFromTiffFolder1.setEnabled(False)
        self._buttonProjectFromTiffFolder1.clicked.connect(self.createProjectFromTiffFolder)
        self._buttonProjectFromTiffFolder1.setFixedSize(button_size)

        self._buttonCancelProjectFromTiffFolder = QPushButton(f"Cancel")
        self._buttonCancelProjectFromTiffFolder.setStyleSheet('font-size: 9px;')
        def fn():
            self.le_project_name_w.hide()
        self._buttonCancelProjectFromTiffFolder.clicked.connect(fn)
        self._buttonCancelProjectFromTiffFolder.setFixedSize(button_size)

        self.cbCalGrid = QCheckBox('Image 0 is calibration grid')
        self.cbCalGrid.setChecked(False)
        self.cbCalGrid.hide()

        # self._buttonDelete = QPushButton(f"Delete Project")
        self._buttonDelete = QPushButton(f"Delete Project {hotkey('D')}")
        self._buttonDelete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonDelete.setShortcut('Ctrl+D')
        self._buttonDelete.setStyleSheet('font-size: 9px;')
        self._buttonDelete.setEnabled(False)
        self._buttonDelete.clicked.connect(lambda: self.delete_projects())
        self._buttonDelete.setFixedSize(button_size)
        # self._buttonDelete.hide()

        def paste_from_buffer():
            buffer = QApplication.clipboard().text()
            self.selectionReadout.setText(os.path.abspath(buffer))
            self.validate_path()

        self._buttonBrowserPaste = QPushButton(f"Paste {hotkey('V')}")
        self._buttonBrowserPaste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonBrowserPaste.setToolTip('Paste path from clipboard')
        self._buttonBrowserPaste.clicked.connect(paste_from_buffer)
        self._buttonBrowserPaste.setFixedSize(QSize(64,18))
        self._buttonBrowserPaste.setStyleSheet('font-size: 9px;')
        # self._buttonBrowserPaste.setEnabled(os.path.exists(QApplication.clipboard().text()))

        self.bSetContentSources = QPushButton('Set Content Sources')
        self.bSetContentSources.setFixedSize(QSize(100,18))
        self.bSetContentSources.setStyleSheet('font-size: 9px;')
        def fn():
            self.w_teContentSources.setVisible(not self.w_teContentSources.isVisible())
            if self.w_teContentSources.isVisible():
                self.leContentRoot.setText(cfg.settings['content_root'])
                self.teSearchPaths.setText('\n'.join(cfg.settings['search_paths']))
            self.bSetContentSources.setText(('Set Content Sources', 'Hide')[
                                                self.w_teContentSources.isVisible()])
        self.bSetContentSources.clicked.connect(fn)
        self.lab_path_exists = cfg.lab_path_exists = QLabel('Path Exists')
        self.lab_path_exists.setFixedWidth(80)
        self.lab_path_exists.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lab_path_exists.setAlignment(Qt.AlignRight)
        self.lab_path_exists.setObjectName('validity_label')
        self.lab_path_exists.setFixedHeight(16)
        self.lab_path_exists.setAlignment(Qt.AlignRight)
        self.lab_path_exists.hide()

        self.bImportSeries = QPushButton('Import Series')
        self.bImportSeries.setFixedSize(QSize(100,18))
        self.bImportSeries.setStyleSheet('font-size: 9px;')
        self.bImportSeries.clicked.connect(self.showImportSeriesDialog)

        self.lab_project_name = QLabel(' New Project Path: ')
        self.lab_project_name.setStyleSheet("font-size: 10px; font-weight: 600; color: #ede9e8; background-color: #339933; border-radius: 4px;")
        self.lab_project_name.setFixedHeight(18)
        self.le_project_name = QLineEdit()
        self.le_project_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.le_project_name = cfg.le_project_name = QLineEdit()
        self.le_project_name.setReadOnly(False)
        def fn():
            logger.info('')
            self._buttonProjectFromTiffFolder2.setEnabled(not os.path.exists(self.le_project_name.text()))
            self.lab_path_exists.setVisible(os.path.exists(self.le_project_name.text()))

        self.le_project_name.textChanged.connect(fn)
        # self.le_project_name.textEdited.connect(fn)
        self.le_project_name.setFixedHeight(20)
        self.le_project_name.setMinimumWidth(40)

        self.le_project_name_w_overlay = QWidget()
        ew = ExpandingWidget(self)
        ew.setAttribute(Qt.WA_TransparentForMouseEvents)
        hw = HWidget(ew, self.lab_project_name, QLabel(' '))
        hw.setAttribute(Qt.WA_TransparentForMouseEvents)
        # self.le_project_name_w_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        gl = QGridLayout()
        gl.setContentsMargins(0,0,0,0)
        gl.addWidget(self.le_project_name,0,0)
        gl.addWidget(self.lab_path_exists,0,0)
        self.le_project_name_w_overlay.setLayout(gl)

        # def fn_le_textChanged(path):
        #     logger.info('')
        #     self._buttonProjectFromTiffFolder2.setEnabled(not os.path.exists(path))
        # self.le_project_name.textChanged.connect(lambda: fn_le_textChanged(self.le_project_name.text()))

        def enter_pressed():
            logger.info('')
            if self._buttonProjectFromTiffFolder2.isEnabled():
                self.skipToConfig()

        self.le_project_name.returnPressed.connect(enter_pressed)
        self._buttonProjectFromTiffFolder2 = QPushButton('Create')
        self._buttonProjectFromTiffFolder2.setFixedSize(button_size)
        self._buttonProjectFromTiffFolder2.setStyleSheet("font-size: 10px;")
        self.le_project_name_w = HWidget(QLabel('  '),self.lab_project_name, QLabel('  '), self.le_project_name_w_overlay, QLabel('    '),
                                         self._buttonProjectFromTiffFolder2, QLabel('    '),
                                         self._buttonCancelProjectFromTiffFolder, QLabel('    '))
        self.le_project_name_w.setFixedHeight(20)
        self.le_project_name_w.hide()

        self._buttonProjectFromTiffFolder2.clicked.connect(self.skipToConfig)

        self.validity_label = QLabel('Invalid')
        self.validity_label.setAlignment(Qt.AlignRight)
        self.validity_label.setObjectName('validity_label')
        self.validity_label.setFixedHeight(16)
        self.validity_label.hide()
        tip = '<span>Several different file types can be opened in alignEM-SWiFT: <br>' \
              '&nbsp;&nbsp;- AlignEM-SWiFT project files (.swiftir)<br><br>' \
              '&nbsp;&nbsp;- Zarr files (any directory containing .zarray)' \
              '<br><br><i>Zarr is a format for the storage of chunked, compressed, ' \
              'N-dimensional arrays</i></span>'
        self.validity_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))


        self.selectionReadout = QLineEdit()
        self.selectionReadout.setReadOnly(False)
        self.selectionReadout.textChanged.connect(self.validate_path)
        self.selectionReadout.returnPressed.connect(self.open_project_selected)
        # self.selectionReadout.textEdited.connect(self.validateUserEnteredPath)

        self.selectionReadout.setFixedHeight(22)
        # self.selectionReadout.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.selectionReadout_w_overlay = QWidget()
        # self.selectionReadout_w_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        gl = QGridLayout()
        gl.setContentsMargins(0,0,0,0)
        gl.addWidget(self.selectionReadout,0,0)
        hw = HWidget(ExpandingWidget(self), self.validity_label, QLabel(' '))
        hw.setAttribute(Qt.WA_TransparentForMouseEvents)
        gl.addWidget(hw,0,0)
        self.selectionReadout_w_overlay.setLayout(gl)


        hbl = QHBoxLayout()
        hbl.setContentsMargins(0,0,0,0)
        # hbl.addWidget(self.labNewProject)
        # hbl.addWidget(self._buttonProjectFromTiffFolder1)
        # hbl.addWidget(self.selectionReadout_w_overlay)
        # hbl.addWidget(self._buttonOpen)
        # hbl.addWidget(self._buttonDelete)
        # hbl.addWidget(self._buttonBrowserPaste)
        hbl.addWidget(self.bSetContentSources)
        hbl.addWidget(self.bImportSeries)
        hbl.addWidget(self.cbCalGrid)
        hbl.setStretch(3,5)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hbl.addSpacerItem(self.spacer_item_docs)

        self._actions_widget = QWidget()
        self._actions_widget.setAutoFillBackground(True)
        self._actions_widget.setFixedHeight(26)
        self._actions_widget.setLayout(hbl)


        self.comboSelectSeries = QComboBox()
        self.comboSelectSeries.setAutoFillBackground(True)
        self.comboSelectSeries.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # self.comboSelectSeries.setCurrentText()
        self.updateSeriesCombo()


        self.comboSelectAlignment = QComboBox()
        self.comboSelectAlignment.addItems(["Null"])
        self.comboSelectAlignment.setAutoFillBackground(True)

        self.bPlusAlignment = QPushButton()
        self.bPlusAlignment.setIcon(qta.icon('fa.plus', color=cfg.ICON_COLOR))
        self.bPlusAlignment.setToolTip("New Alignment")
        self.bPlusAlignment.setFixedSize(QSize(18,18))
        self.bPlusAlignment.setIconSize(QSize(12,12))
        self.bMinusAlignment = QPushButton()
        self.bMinusAlignment.setIcon(qta.icon('fa.minus', color=cfg.ICON_COLOR))
        self.bMinusAlignment.setToolTip("Delete Alignment")
        self.bMinusAlignment.setFixedSize(QSize(18,18))
        self.bMinusAlignment.setIconSize(QSize(12,12))
        self.bOpenAlignment = QPushButton()
        self.bOpenAlignment.setIcon(qta.icon('fa.folder-open', color=cfg.ICON_COLOR))
        self.bOpenAlignment.setToolTip("Open Alignment")
        self.bOpenAlignment.setFixedSize(QSize(18,18))
        self.bOpenAlignment.setIconSize(QSize(12,12))

        self.alignButtons = HWidget(self.bOpenAlignment, self.bPlusAlignment, self.bMinusAlignment)

        self.l0 = QLabel('Series: ')
        self.l0.setFixedWidth(58)
        self.l1 = QLabel('Alignment: ')
        self.l1.setFixedWidth(58)
        self.combos = HWidget(self.l0, self.comboSelectSeries, QLabel(' '), self.l1, self.comboSelectAlignment, self.alignButtons)
        self.combos.setAutoFillBackground(True)
        self.combos.setStyleSheet("background-color: #222222; color: #f3f6fb; font-size: 11px;")
        # self.combos.layout.setSpacing(0)
        self.combos.layout.setStretch(1,9)
        self.combos.layout.setStretch(4,9)
        # self.combos.layout.setAlignment(Qt.AlignLeft)

        self.webengine = WebEngine(ID='pmViewer')
        setWebengineProperties(self.webengine)
        self.webengine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.webengine.setMinimumWidth(400)
        self.webengine.setMinimumHeight(400)
        self.viewer = cfg.pmViewer = PMViewer(webengine=self.webengine)
        self.updateSeriesCombo()
        logger.critical(self.comboSelectSeries.currentText())
        if self.comboSelectSeries.currentText() != "null":
            path = os.path.join(self.comboSelectSeries.currentText(), 'zarr', 's2')
            # try:
            self.viewer.initViewer(path=path)
            # self.viewer.initZoom(self.webengine.width(), self.webengine.height())
            # except:
            #     self.viewer.initExample()
            #     self.viewer.initZoom(self.webengine.width(), self.webengine.height())

        else:
            self.viewer.initExample()
            # self.viewer.initZoom(self.webengine.width(), self.webengine.height())

        self.labTitle = QLabel("Series Manager")
        self.labTitle.setContentsMargins(1,1,0,4)
        self.labTitle.setStyleSheet("font-size: 11px; font-weight: 600;")

        self.wProjects = VWidget(self.labTitle, self.combos, self.webengine)
        self.wProjects.layout.setContentsMargins(2,2,2,2)
        self.wProjects.setStyleSheet("""
        QWidget {
            background-color: #222222; 
            color: #f3f6fb;
        }
        QComboBox {
            background-color: #222222;
            color: #f3f6fb;
        }    
            
        """)

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

        if '.tacc.utexas.edu' in platform.node():
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
        # urls = self.name_dialog.sidebarUrls()
        # logger.info(f'urls: {urls}')

        # cfg.cp_dialog = NewConfigureProjectDialog(parent=self)
        # cfg.cp_dialog.layout().setContentsMargins(2,2,2,2)
        # cfg.cp_dialog.setWindowFlags(Qt.FramelessWindowHint)
        # self.vbl_main.addWidget(cfg.cp_dialog)

        cfg.iid_dialog = ImportImagesDialog()

        self.leProjName = QLineEdit()
        self.leProjName.setReadOnly(False)

        self.w_name_dialog = HWidget(QLabel("Project Name:"), self.leProjName)
        self.w_name_dialog.hide()

        self.leContentRoot = QLineEdit()
        self.leContentRoot.setFixedHeight(18)
        self.leContentRoot.setReadOnly(False)

        self.teSearchPaths = QTextEdit()
        self.teSearchPaths.setMaximumHeight(100)
        self.teSearchPaths.setReadOnly(False)
        # self.teSearchPaths.setMaximumHeight(140)
        # self.teSearchPaths.setMinimumHeight(40)

        self.bSaveContentSources = QPushButton('Save')
        self.bSaveContentSources.setFixedSize(QSize(60,18))
        def fn():
            logger.info(f'Saving search paths and content roots...')
            cfg.settings['search_paths'] = self.teSearchPaths.toPlainText().split('\n')
            cfg.settings['content_root'] = self.leContentRoot.text()

            makedirs_exist_ok(cfg.settings['content_root'], exist_ok=True)
            p = os.path.join(cfg.settings['content_root'], 'series')
            if not os.path.exists(p):
                logger.critical(f'Creating directory! {p}')
                os.mkdir(p)
            p = os.path.join(cfg.settings['content_root'], 'projects')
            if not os.path.exists(p):
                logger.critical(f'Creating directory! {p}')
                os.mkdir(p)
            cfg.mw._autosave()
            self.w_teContentSources.hide()
            self.bSetContentSources.setText('Set Content Sources')
            cfg.mw.statusBar.showMessage('Content roots saved!', 3000)
        self.bSaveContentSources.clicked.connect(fn)


        self.w_teContentSources = QWidget()
        self.flContentAndSearch = QFormLayout()
        self.flContentAndSearch.setContentsMargins(0,0,0,0)
        self.flContentAndSearch.setSpacing(2)
        self.flContentAndSearch.addRow('Content Root', self.leContentRoot)
        self.flContentAndSearch.addRow('Search Paths', self.teSearchPaths)
        self.flContentAndSearch.addWidget(self.bSaveContentSources)
        # self.w_teContentSources.setMaximumHeight(140)
        self.w_teContentSources.setLayout(self.flContentAndSearch)
        self.w_teContentSources.setMinimumHeight(50)
        self.w_teContentSources.setMaximumHeight(150)
        self.w_teContentSources.hide()


        self.leNameSeries = QLineEdit()
        self.placeholderText = '<short, descriptive name>'
        self.leNameSeries.setPlaceholderText(self.placeholderText)
        self.leNameSeries.setFixedHeight(18)
        self.leNameSeries.setReadOnly(False)
        pal = self.leNameSeries.palette()
        pal.setColor(QPalette.PlaceholderText, QColor("#dadada"))
        self.leNameSeries.setPalette(pal)
        self.leNameSeries.textChanged.connect(self.updateImportSeriesUI)


        lab = QLabel('Series Name:')
        lab.setStyleSheet("font-size: 10px;")
        self.bSelect = QPushButton("Select Images")
        self.bSelect.clicked.connect(self.selectImages)

        self.bCancel = QPushButton("Cancel")
        def fn():
            self.showMainUI()
            self._NEW_SERIES_PATHS = []
        self.bCancel.clicked.connect(fn)

        self.bConfirmImport = QPushButton("Import")
        self.bConfirmImport.clicked.connect(self.importSeries)
        self.bConfirmImport.setEnabled(False)
        # self.wNameSeries = HWidget(lab, self.leNameSeries, self.bSelect, self.bConfirmImport, self.bCancel)
        self.wNameSeries = HWidget(lab, self.leNameSeries, self.bSelect, self.bConfirmImport)
        self.wNameSeries.layout.setSpacing(4)
        self.wNameSeries.layout.setContentsMargins(0,0,0,0)

        bs = [self.bSelect, self.bConfirmImport, self.bCancel]
        for b in bs:
            # b.setStyleSheet("font-size: 10px; ")
            b.setFixedSize(QSize(78,18))

        self.wSeriesConfig = SeriesConfig(parent=self)

        vbl = VBL(self.wNameSeries, self.wSeriesConfig)
        vbl.setContentsMargins(4,10,4,4)
        self.gbImportSeries = QGroupBox("Import Series")
        self.gbImportSeries.setLayout(vbl)
        self.gbImportSeries.setFixedHeight(70)
        # self.gbImportSeries.layout.setContentsMargins(4,4,4,4)
        self.gbImportSeries.hide()

        self._splitter = QSplitter()
        # self._splitter.addWidget(self.userProjectsWidget)
        self._splitter.addWidget(VSplitter(self.wProjects,self.gbImportSeries, self.w_teContentSources))
        self._splitter.addWidget(self.userFilesWidget)
        self._splitter.setSizes([700, 300])

        self.vbl_main = VBL()
        self._vw = VWidget(self._splitter, self._actions_widget, self.le_project_name_w)
        self._vsplitter = QSplitter(Qt.Orientation.Vertical)
        self._vsplitter.addWidget(self._vw)
        # self._vsplitter.addWidget(self.w_teContentSources)
        # self._vsplitter.addWidget(self.w_name_dialog)
        self.vbl_main.addWidget(self._vsplitter)
        # self.vbl_main.addWidget(self.gbImportSeries)
        self.setLayout(self.vbl_main)

        self._NEW_SERIES_PATHS = []


    def onNewAlignment(self):
        series = self._series
        dm = cfg.data = DataModel(name=self.NEW_PROJECT_PATH)

        logger.critical(f"series: {series}")


    def onSelectSeriesCombo(self):
        self._series = self.comboSelectSeries.currentText()
        logger.critical(f'Selected series: {self._series}')
        if self.comboSelectSeries.currentText() != "null":
            self.viewer = cfg.pmViewer = PMViewer(webengine=self.webengine)
            path = os.path.join(self.comboSelectSeries.currentText(), 'zarr', 's2')
            self.viewer.initViewer(path=path)
            # self.viewer.initZoom(self.webengine.width(), self.webengine.height())
        else:
            self.viewer.initExample()
            # self.viewer.initZoom(self.webengine.width(), self.webengine.height())


    def updateSeriesCombo(self):
        self.comboSelectSeries.disconnect()
        self.comboSelectSeries.clear()
        cr = cfg.settings['content_root'] # content root full path
        crn = os.path.basename(cfg.settings['content_root']) # content root name
        d = os.path.join(cr, 'series')
        # dirs = ['./' + crn + '/series/' + name for name in os.listdir(d) if os.path.isdir(os.path.join(d, name)) ]
        dirs = [d + '/' + name for name in os.listdir(d) if os.path.isdir(os.path.join(d, name)) ]
        if dirs:
            self.comboSelectSeries.addItems(dirs)
        else:
            self.comboSelectSeries.addItems(["null"])
        self.comboSelectSeries.currentIndexChanged.connect(self.onSelectSeriesCombo)


    def showMainUI(self):
        logger.info('')
        self._actions_widget.show()
        # self.w_name_dialog.hide()
        self.gbImportSeries.hide()
        # self.bImportSeries.setText("Set Content Source")
        # self.bSetContentSources.setText("Import Series")
        self.update()
        # self.new_project_header.hide()

    def validate_path(self):
        # logger.info(f'caller:{inspect.stack()[1].function}')
        path = self.selectionReadout.text()
        # logger.info(f'Validating path : {path}')
        if validate_project_selection(path):
            self._buttonOpen.setText(f"Open Project {hotkey('O')}")
            logger.info(f'path is a valid AlignEM-SWIFT project')
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


    def userSelectionChanged(self):
        logger.info('')
        # logger.info(f'>>>> userSelectionChanged >>>>')
        # caller = inspect.stack()[1].function
        # if caller == 'initTableData':
        #     return
        row = self.user_projects.table.currentIndex().row()
        try:
            try:
                self.selected_file = self.user_projects.table.item(row, 0).text()
            except:
                pass
            logger.info(f'row {str(row)}, {self.selected_file}')
            self.setSelectionPathText(self.selected_file)
            self._buttonProjectFromTiffFolder1.setEnabled(validate_tiff_folder(self.selected_file))
            self.cbCalGrid.setVisible(validate_tiff_folder(self.selected_file))
            self.validity_label.setVisible(validate_tiff_folder(self.selected_file))
            self.validate_path()
        except:
            # path = ''
            # logger.warning(f'No file path at project_table.currentIndex().row()! '
            #                f'caller: {caller} - Returning...')
            print_exception()


    '''New Project From TIFFs (1/3)'''
    def createProjectFromTiffFolder(self):
        logger.info(f'caller:{inspect.stack()[1].function}')
        cur_path = self.selectionReadout.text()
        if validate_tiff_folder(cur_path):
            # if cfg.data['data']['has_cal_grid']:
            self.le_project_name_w.show()
            self.le_project_name.setFocus()
            pathlib = Path(cur_path)
            path_par = str(pathlib.parent.absolute())
            self.le_project_name.setText(os.path.join(path_par,'myproject.swiftir'))
            self.NEW_PROJECT_IMAGES = natural_sort(glob(os.path.join(cur_path, '*.tif')) + glob(os.path.join(cur_path, '*.tiff')))


    '''New Project From TIFFs (2/3)'''
    def skipToConfig(self):
        logger.info('')
        self.NEW_PROJECT_PATH = self.le_project_name.text()
        self.new_project(skip_to_config=True)
        self.le_project_name_w.hide()
        self.le_project_name.setText('')


    def showImportSeriesDialog(self):
        self.gbImportSeries.setVisible(not self.gbImportSeries.isVisible())
        self._NEW_SERIES_PATHS = []
        if self.gbImportSeries.isVisible():
            self.wSeriesConfig.le_res_x.setText(str(cfg.DEFAULT_RESX))
            self.wSeriesConfig.le_res_y.setText(str(cfg.DEFAULT_RESY))
            self.wSeriesConfig.le_res_z.setText(str(cfg.DEFAULT_RESZ))
            self.wSeriesConfig.le_chunk_x.setText(str(cfg.CHUNK_X))
            self.wSeriesConfig.le_chunk_y.setText(str(cfg.CHUNK_Y))
            self.wSeriesConfig.le_chunk_z.setText(str(cfg.CHUNK_Z))
            self.wSeriesConfig.cname_combobox.setCurrentText(str(cfg.CNAME))
            # self.leContentRoot.setText(cfg.settings['content_root'])
            # self.teSearchPaths.setText('\n'.join(cfg.settings['search_paths']))
        self.bImportSeries.setText(('Import Series', 'Hide')[self.gbImportSeries.isVisible()])
        # self._actions_widget.hide()


        # response = cfg.iid_dialog.exec()
        # self.showMainUI()
        # cfg.mw.set_status('')
        # if response == QDialog.Rejected:
        #     logger.warning("Dialog was rejected")
        #     return


    def updateImportSeriesUI(self):
        logger.info('')
        self.bConfirmImport.setEnabled(False)
        if len(self.leNameSeries.text()) > 1:
            if len(self._NEW_SERIES_PATHS) > 1:
                self.bConfirmImport.setEnabled(True)
        # self.bConfirmImport.setStyleSheet(("color: #dadada;","color: #161c20;")[self.bConfirmImport.isEnabled()])


    def selectImages(self):
        cfg.new_iid_dialog = ImportImagesDialog()
        cfg.new_iid_dialog.resize(QSize(820,480))
        cfg.new_iid_dialog.show()
        # sidebar = self.findChild(QListView, "sidebar")
        # delegate = StyledItemDelegate(sidebar)
        # delegate.mapping = getSideBarPlacesImportImages()
        # sidebar.setItemDelegate(delegate)

        if cfg.new_iid_dialog.exec_() == QDialog.Accepted:
            filenames = cfg.new_iid_dialog.selectedFiles()
            cfg.new_iid_dialog.pixmap = None
        else:
            logger.warning('Import images dialog did not return a valid file list')
            cfg.mw.warn('Import images dialog did not return a valid file list')
            self.showMainUI()
            cfg.new_iid_dialog.pixmap = None
            return 1

        if filenames == 1:
            logger.warning('New Project Canceled')
            cfg.mw.warn('No Project Canceled')
            self.showMainUI()
            return 1

        self._NEW_SERIES_PATHS = natural_sort(filenames)
        self.updateImportSeriesUI()
        logger.critical(f"{filenames}")



    def importSeries(self):
        logger.critical("")
        self.bConfirmImport.setEnabled(False)

        name = self.leNameSeries.text()
        name.replace(' ','_')
        name, _ = os.path.splitext(name)
        filename = os.path.join(cfg.settings['content_root'], 'series', name + ".series")
        dirname = os.path.join(cfg.settings['content_root'], 'series', name)


        logger.critical(f"has cal grid? {cfg.new_iid_dialog.cb_cal_grid.isChecked()}")
        logger.critical(f"paths: {self._NEW_SERIES_PATHS}")
        logger.critical(f"name: {name}")
        logger.critical(f"dirname: {dirname}")

        dm = cfg.data = DataModel(series_path=dirname)
        dm['data']['autoalign_flag'] = False
        logger.critical(f"0, dm.location = {dm.location}")
        initLogFiles(dm)


        dm['data']['has_cal_grid'] = cfg.new_iid_dialog.cb_cal_grid.isChecked()
        if dm['data']['has_cal_grid']:
            logger.info('Linking to calibration grid image...')
            dm['data']['cal_grid_path'] = self._NEW_SERIES_PATHS[0]
            self._NEW_SERIES_PATHS = self._NEW_SERIES_PATHS[1:]

        dm.set_source_path(os.path.dirname(self._NEW_SERIES_PATHS[0]))  # Critical!
        cfg.mw.tell(f'Importing {len(self._NEW_SERIES_PATHS)} Images...')
        dm.append_images(self._NEW_SERIES_PATHS)

        cfg.mw.tell(f'Dimensions: %dx%d' % dm.image_size(s='scale_1'))
        logger.critical(f"1, dm.location = {dm.location}")


        dm.set_scales_from_string(self.wSeriesConfig.scales_input.text())


        dm.set_defaults()

        makedirs_exist_ok(dirname, exist_ok=True)
        logger.critical(f"dirname = {dirname}")
        logger.critical(f"dm.scales() = {dm.scales()}")
        # create_project_directories(dirname, dm.scales())

        tiff_path = os.path.join(dirname, 'tiff')
        zarr_path = os.path.join(dirname, 'zarr')
        os.makedirs(tiff_path, exist_ok=True)
        os.makedirs(zarr_path, exist_ok=True)

        for sv in dm.scale_vals():
            cfg.mw.hud('Creating new series directories for scale %s...' % sv)
            logger.info('Creating new series directories for scale %s...' % sv)
            os.makedirs(os.path.join(tiff_path, 's%d' % sv), exist_ok=True)
            os.makedirs(os.path.join(zarr_path, 's%d' % sv), exist_ok=True)


        t0 = time.time()
        logger.info('>>>> Symbolically linking full scale images >>>>')
        for img in self._NEW_SERIES_PATHS:
            fn = os.path.join(dm['data']['source_path'], img)
            ofn = os.path.join(dm.location, 'tiff', 's1', os.path.split(fn)[1])
            # normalize path for different OSs
            if os.path.abspath(os.path.normpath(fn)) != os.path.abspath(os.path.normpath(ofn)):
                try:
                    os.unlink(ofn)
                except:
                    pass
                try:
                    os.symlink(fn, ofn)
                except:
                    logger.warning("Unable to link %s to %s. Copying instead." % (fn, ofn))
                    try:
                        shutil.copy(fn, ofn)
                    except:
                        logger.warning("Unable to link or copy from " + fn + " to " + ofn)
        dt = time.time() - t0
        logger.info(f'<<<< linking took {dt:.3g}s <<<<')

        # cfg.project_tab = ProjectTab(self, path=path, datamodel=dm)
        ID = id(cfg.project_tab)
        logger.info(f'New Tab ID: {ID}')
        cfg.dataById[id(cfg.project_tab)] = dm
        dm.set_defaults()
        set_image_sizes(dm)




        # settings = self.gbImportSeries.getSettings()

        # data_cp = copy.deepcopy(dm.to_json())
        jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
        with open(filename, 'w') as f:
            f.write(jde.encode(copy.deepcopy(dm._data)))

        cfg.mw.autoscaleSeries(dm)

        cfg.mw._is_initialized = 1
        # cfg.data = dm
        logger.critical('<<<< new_project <<<<')





    def new_project(self, mendenhall=False, skip_to_config=False):
        logger.info('\n\nStarting A New Project...\n')
        cfg.mw.tell('Starting A New Project...')
        cfg.mw._is_initialized = 0

        cfg.mw.stopPlaybackTimer()
        cfg.mw.tell('New Project Path:')
        # self.new_project_lab1.setText('New Project (Step: 1/3) - Name & Location')
        cfg.mw.set_status('New Project (Step: 1/3) - Name & Location')

        self._actions_widget.hide()
        if self.name_dialog.exec() == QFileDialog.Accepted:
            logger.info('Save File Path: %s' % self.name_dialog.selectedFiles()[0])
            filename = self.name_dialog.selectedFiles()[0]
            self.new_project_lab2.setText(filename)
            self.name_dialog.close()
        else:
            self.showMainUI()
            self.name_dialog.close()
            cfg.mw.set_status('')
            return 1

        if filename in ['', None]:
            logger.info('New Project Canceled.')
            cfg.mw.warn("New Project Canceled.")
            self.showMainUI()
            cfg.mw.set_status('')
            return


        self.NEW_PROJECT_PATH = filename

        path,_ = os.path.splitext(self.NEW_PROJECT_PATH)
        self.NEW_PROJECT_PATH = os.path.join(cfg.settings['content_root'], 'alignment', os.path.basename(path))

        dm = cfg.data = DataModel(name=self.NEW_PROJECT_PATH)
        initLogFiles(dm)

        if skip_to_config:
            dm['data']['has_cal_grid'] = self.cbCalGrid.isChecked()

        self.new_project_lab2.setText(path)

        if not skip_to_config:
            '''Step 2/3...'''

            cfg.mw.tell('Import Images:')

            '''Step 2/3'''
            '''Dialog for importing images. Returns list of filenames.'''
            # cfg.iid_dialog = ImportImagesDialog()
            # self.vbl_main.addWidget(cfg.iid_dialog)
            cfg.iid_dialog.show()
            # self.new_project_lab1.setText('New Project (Step: 2/3) - Import TIFF Images')
            cfg.mw.set_status('New Project (Step: 2/3) - Import TIFF Images')
            sidebar = self.findChild(QListView, "sidebar")
            delegate = StyledItemDelegate(sidebar)
            delegate.mapping = getSideBarPlacesImportImages()
            sidebar.setItemDelegate(delegate)

            if cfg.iid_dialog.exec_() == QDialog.Accepted:
                filenames = cfg.iid_dialog.selectedFiles()
                cfg.iid_dialog.pixmap = None
            else:
                logger.warning('Import images dialog did not return a valid file list')
                cfg.mw.warn('Import images dialog did not return a valid file list')
                self.showMainUI()
                cfg.iid_dialog.pixmap = None
                return 1

            if filenames == 1:
                logger.warning('New Project Canceled')
                cfg.mw.warn('No Project Canceled')
                self.showMainUI()
                return 1

            self.NEW_PROJECT_IMAGES = natural_sort(filenames)
            logger.info(f'destination: {dm.dest()}')


        self.NEW_PROJECT_IMAGES = natural_sort(self.NEW_PROJECT_IMAGES)

        if dm['data']['has_cal_grid']:
            logger.info('Linking to calibration grid image...')
            dm['data']['cal_grid_path'] = self.NEW_PROJECT_IMAGES[0]
            self.NEW_PROJECT_IMAGES = self.NEW_PROJECT_IMAGES[1:]

        dm.set_source_path(os.path.dirname(self.NEW_PROJECT_IMAGES[0]))  # Critical!
        cfg.mw.tell(f'Importing {len(self.NEW_PROJECT_IMAGES)} Images...')
        # logger.info(f'Selected Images: \n{self.NEW_PROJECT_IMAGES}')
        dm.append_images(self.NEW_PROJECT_IMAGES)

        cfg.mw.tell(f'Dimensions: %dx%d' % dm.image_size(s='scale_1'))

        dm.set_defaults()

        self.le_project_name_w.hide()

        '''Step 3/3'''
        # self.new_project_lab1.setText('New Project (Step: 3/3) - Configure')
        cfg.mw.set_status('New Project (Step: 3/3) - Configure')

        cfg.cp_dialog = NewConfigureProjectDialog(parent=self)
        cfg.cp_dialog.layout().setContentsMargins(2,2,2,2)
        cfg.cp_dialog.setWindowFlags(Qt.FramelessWindowHint)
        self.vbl_main.addWidget(cfg.cp_dialog)
        response = cfg.cp_dialog.exec()
        self.showMainUI()
        cfg.mw.set_status('')
        if response == QDialog.Rejected:
            logger.warning("Dialog was rejected")
            return
        QApplication.processEvents()
        makedirs_exist_ok(path, exist_ok=True)
        create_project_directories(dm.location, dm.scales())
        logger.critical(os.listdir(path))

        # cfg.project_tab = ProjectTab(self, path=path, datamodel=dm)
        ID = id(cfg.project_tab)
        logger.info(f'New Tab ID: {ID}')
        cfg.dataById[id(cfg.project_tab)] = dm
        dm.set_defaults()
        set_image_sizes(dm)

        cfg.project_tab = cfg.pt = ProjectTab(self, path=path, datamodel=dm)
        cfg.mw._autosave()
        cfg.mw.tell(f"Creating project {os.path.basename(path)}...")
        logger.info(f'Appending project {filename} to .swift_cache...')

        # append_project_path(filename)
        cfg.settings['projects'].append(filename)
        cfg.mw.saveUserPreferences()


        # cfg.mw._autosave()
        self.user_projects.set_data()
        cfg.mw._is_initialized = 1
        cfg.mw.autoscale(dm, new_tab=True)
        # cfg.data = dm
        logger.info('<<<< new_project <<<<')





    def setSelectionPathText(self, path):
        # logger.info('')
        self.selectionReadout.setText(path)
        # logger.info('Evaluating whether path is AlignEM-SWiFT Project...')

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

    def open_project_selected(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        logger.info('')

        cfg.mw.set_status("Loading Project...")
        cfg.mw._is_initialized = 0
        path = self.selectionReadout.text()
        if validate_zarr_selection(path):
            self.open_zarr_selected()
            return
        elif validate_project_selection(path):

            if cfg.mw.isProjectOpen(path):
                cfg.mw.globTabs.setCurrentIndex(cfg.mw.getProjectIndex(path))
                cfg.mw.warn(f'Project {os.path.basename(path)} is already open.')
                return

            # filename = self.selected_file
            filename = self.selectionReadout.text()
            fn, ext = os.path.splitext(filename)
            if ext == '.json':
                logger.info('Opening OLD alignem-swift project')
                new_name = fn + '.swiftir'
                print(f"new name: {new_name}")
                with open(filename, 'r') as f:
                    data = json.load(f)
                    al_stack = data['data']['scales']['scale_1']['alignment_stack']
                    imgs = []
                    for l in al_stack:
                        imgs.append(os.path.dirname(new_name) + '/' + l['images']['base']['filename'])
                    print(imgs)
                    self.NEW_PROJECT_IMAGES = imgs
                    self.NEW_PROJECT_PATH = new_name
                    self.new_project(skip_to_config=True)
                    # print(json.dumps(data, indent=4))
                return


            logger.info(f'Opening {filename}...')

            try:
                with open(filename, 'r') as f:
                    dm = cfg.data = DataModel(data=json.load(f))
                dm.set_defaults()
                cfg.mw._autosave()
            except:
                cfg.mw.warn(f'No Such File Found: {filename}')
                logger.warning(f'No Such File Found: {filename}')
                print_exception()
                return
            else:
                logger.info(f'Project Opened!')

            initLogFiles(dm) #0805+
            # append_project_path(filename)
            cfg.settings['projects'].append(filename)
            cfg.mw.saveUserPreferences()
            dm.set_paths_absolute(filename=filename)
            # cfg.project_tab = ProjectTab(self, path=cfg.data.dest() + '.swiftir', datamodel=cfg.data)
            cfg.project_tab = cfg.pt = ProjectTab(self, path=dm.name, datamodel=dm)
            cfg.dataById[id(cfg.project_tab)] = dm

            # cfg.mw.addGlobTab(cfg.project_tab, os.path.basename(cfg.data.dest()) + '.swiftir')
            # cfg.mw._closeOpenProjectTab()
            # cfg.mw._setLastTab()
            cfg.mw._is_initialized = 1
            QApplication.processEvents()
            cfg.pt.initNeuroglancer()
            cfg.mw.onStartProject(dm)

        else:
            cfg.mw.warn("Invalid Path")

    def getSelectedRows(self):
        logger.info(f"{[x.row() for x in self.user_projects.table.selectionModel().selectedRows()]}")
        return [x.row() for x in self.user_projects.table.selectionModel().selectedRows()]

    def getSelectedProjects(self):
        logger.info(f"{[self.user_projects.table.item(r, 0).text() for r in self.getSelectedRows()]}")
        return [self.user_projects.table.item(r, 0).text() for r in self.getSelectedRows()]

    def getNumRowsSelected(self):
        return len(self.getSelectedProjects())

    def deleteContextMethod(self):
        logger.info('')
        selected_projects = self.getSelectedProjects()
        self.delete_projects(project_files=selected_projects)

    def openContextMethod(self):
        logger.info('')
        self.open_project_selected()


    def delete_projects(self, project_files=None):
        logger.info('')
        if project_files == None:
            project_files = [self.selectionReadout.text()]


        for project_file in project_files:
            if project_file != '':
                if validate_project_selection(project_file):

                    project = os.path.splitext(project_file)[0]

                    cfg.mw.set_status(f'Delete {project}')

                    cfg.mw.warn("Delete this project? %s" % project_file)
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
                        logger.warning('Canceling Delete Project Permanently Instruction...')
                        return
                    if reply == QMessageBox.Ok:
                        logger.info('Deleting file %s...' % project_file)
                        cfg.mw.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)
                        logger.warning('Executing Delete Project Permanently Instruction...')



                    logger.info(f'Deleting project file {project_file}...')
                    cfg.mw.warn(f'Deleting project file {project_file}...')
                    cfg.mw.set_status(f'Deleting {project_file}...')

                    try:
                        os.remove(project_file)
                    except:
                        print_exception()
                    # else:
                    #     cfg.mw.hud.done()

                    # configure_project_paths()
                    # self.user_projects.set_data()

                    logger.info(f'Deleting project directory {project}...')
                    cfg.mw.warn(f'Deleting project directory {project}...')
                    cfg.mw.set_status(f'Deleting {project_file}...')
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

                    cfg.mw.tell('Wrapping up...')
                    # configure_project_paths()
                    # if cfg.mw.globTabs.currentWidget().__class__.__name__ == 'OpenProject':
                    #     try:
                    #         self.user_projects.set_data()
                    #     except:
                    #         logger.warning('There was a problem updating the project list')
                    #         print_exception()

                    self.selectionReadout.setText('')

                    cfg.mw.tell('Deletion Complete!')
                    cfg.mw.set_status('Deletion Complete')
                    logger.info('Deletion tasks finished')
                else:
                    logger.warning('(!) Invalid target for deletion: %s' % project_file)


    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu:
            logger.info('')
            menu = QMenu()

            openContextAction = QAction('Open')
            openContextAction.triggered.connect(self.openContextMethod)
            menu.addAction(openContextAction)

            if self.getNumRowsSelected() == 1:
                # copyPathAction = QAction('Copy Path')
                # path = self.getSelectedProjects()[0]
                path = self.getSelectedProjects()[0]
                copyPathAction = QAction(f"Copy Path '{self.getSelectedProjects()[0]}'")
                logger.info(f"Added to Clipboard: {QApplication.clipboard().text()}")
                menu.addAction(copyPathAction)

            deleteContextAction = QAction('Delete')
            deleteContextAction.triggered.connect(self.deleteContextMethod)
            menu.addAction(deleteContextAction)

            menu.exec_(event.globalPos())
            return True
        return super().eventFilter(source, event)


    # def keyPressEvent(self, event):
    #     print(event)
    #     self.keyevent = event
    #
    #     if event.matches(QKeySequence.Delete):
    #         self.delete_projects()


        # if event.key() == Qt.Key_Delete:
        #     # self.parent.parent.delete_projects()
        #     self.delete_projects()
        # else:
        #     super().keyPressEvent(event)


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        # sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
        # sp.Popen(task, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
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
#         self.table = QTableWidget()
#         self.table.setFocusPolicy(Qt.NoFocus)
#         self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         # self.table.setAlternatingRowColors(True)
#         # self.table = TableWidget(self)
#
#         # self.table.setShowGrid(False)
#         self.table.setSortingEnabled(True)
#         self.table.setWordWrap(True)
#         self.table.horizontalHeader().setHighlightSections(False)
#         self.table.horizontalHeader().setStretchLastSection(True)
#         self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
#         self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
#         self.table.verticalHeader().setVisible(False)
#         # self.table.horizontalHeader().setDefaultAlignment(Qt.Alignment(Qt.TextWordWrap))
#         self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
#         def countCurrentItemChangedCalls(): self.counter2 += 1
#         self.table.currentItemChanged.connect(countCurrentItemChangedCalls)
#         self.table.currentItemChanged.connect(self.parent.userSelectionChanged)
#         def countItemClickedCalls(): self.counter1 += 1
#         self.table.itemClicked.connect(countItemClickedCalls)
#         self.table.itemClicked.connect(self.parent.userSelectionChanged)
#         # def onDoubleClick(): self.parent.open_project_selected()
#         # self.table.itemDoubleClicked.connect(self.parent.open_project_selected)
#         self.table.doubleClicked.connect(self.parent.open_project_selected) #Critical this always emits
#         self.table.itemSelectionChanged.connect(self.parent.userSelectionChanged)  # Works!
#         # self.table.itemSelectionChanged.connect(lambda: print('itemselectionChanged was emitted!'))  # Works!
#         # self.table.itemPressed.connect(lambda: print('itemPressed was emitted!'))
#         # self.table.cellActivated.connect(lambda: print('cellActivated was emitted!'))
#         # self.table.currentItemChanged.connect(lambda: print('currentItemChanged was emitted!'))
#         # self.table.itemDoubleClicked.connect(lambda: print('itemDoubleClicked was emitted!'))
#         # self.table.cellChanged.connect(lambda: print('cellChanged was emitted!'))
#         # self.table.cellClicked.connect(lambda: print('cellClicked was emitted!'))
#         # self.table.itemChanged.connect(lambda: print('itemChanged was emitted!'))
#
#         self.table.setColumnCount(11)
#         self.set_headers()
#
#         self.layout = QVBoxLayout()
#         self.layout.setContentsMargins(0, 0, 0, 0)
#         self.layout.addWidget(self.table)
#         # self.layout.addWidget(controls)
#         self.setLayout(self.layout)
#         self.set_data()
#
#         self.table.setMouseTracking(True)
#
#         self.current_hover = [0, 0]
#         self.table.cellEntered.connect(self.cellHover)
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
#     #         # cfg.data.save_notes(text=txt, l=index)
#     #     else:
#     #         cfg.settings['notes']['global_notes'] = self.notes.toPlainText()
#     #     self.notes.update()
#
#
#
#
#     def updateRowHeight(self, h):
#         for section in range(self.table.verticalHeader().count()):
#             self.table.verticalHeader().resizeSection(section, h)
#         self.table.setColumnWidth(1, h)
#         self.table.setColumnWidth(2, h)
#         self.table.setColumnWidth(3, h)
#         # self.table.setColumnWidth(10, h)
#
#
#     # def userSelectionChanged(self):
#     #     caller = inspect.stack()[1].function
#     #     # if caller == 'initTableData':
#     #     #     return
#     #     row = self.table.currentIndex().row()
#     #     try:
#     #         path = self.table.item(row,9).text()
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
#         self.table.setHorizontalHeaderLabels([
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
#         header = self.table.horizontalHeader()
#         header.setFrameStyle(QFrame.Box | QFrame.Plain)
#         header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
#         self.table.setHorizontalHeader(header)
#
#
#     def set_data(self):
#         logger.info('')
#
#         configure_project_paths()
#         # logger.info(">>>> set_data >>>>")
#         # caller = inspect.stack()[1].function
#         # logger.info(f'[{caller}]')
#         self.table.clear()
#         self.table.clearContents()
#         font0 = QFont()
#         # font0.setBold(True)
#         font0.setPointSize(9)
#
#         font1 = QFont()
#         # font1.setBold(True)
#         font1.setPointSize(9)
#         self.table.setRowCount(0)
#         for i, row in enumerate(self.get_data()):
#             # logger.info(f'>>>> row #{i} >>>>')
#             self.table.insertRow(i)
#             for j, item in enumerate(row):
#                 if j == 0:
#                     twi = QTableWidgetItem(str(item))
#                     twi.setFont(font1)
#                     self.table.setItem(i, j, twi)
#                 elif j in (1,2,3):
#                     # logger.info(f"j={j}, path={item}")
#                     if item == 'No Thumbnail':
#                         thumbnail = ThumbnailFast(self)
#                         self.table.setCellWidget(i, j, thumbnail)
#                     else:
#                         thumbnail = ThumbnailFast(self, path=item)
#                         self.table.setCellWidget(i, j, thumbnail)
#                 elif j in (4,5):
#                     item.replace("_", " ")
#                     item.replace('-', ':')
#                     # item = item[9:].replace('-', ':')
#                     twi = QTableWidgetItem(item)
#                     twi.setFont(font0)
#                     self.table.setItem(i, j, twi)
#                 elif j in (6,7):
#                     twi = QTableWidgetItem(str(item))
#                     twi.setFont(font0)
#                     # twi.setTextAlignment(Qt.AlignCenter)
#                     self.table.setItem(i, j, twi)
#                 else:
#                     twi = QTableWidgetItem(str(item))
#                     twi.setFont(font0)
#                     self.table.setItem(i, j, twi)
#         self.table.setColumnWidth(0, 220)
#         self.table.setColumnWidth(1, self.ROW_HEIGHT) # <first thumbnail>
#         self.table.setColumnWidth(2, self.ROW_HEIGHT) # <last thumbnail>
#         self.table.setColumnWidth(3, self.ROW_HEIGHT) # <last thumbnail>
#         self.table.setColumnWidth(4, 100)
#         self.table.setColumnWidth(5, 100)
#         self.table.setColumnWidth(6, 36)
#         self.table.setColumnWidth(7, 70)
#         self.table.setColumnWidth(8, 70)
#         self.table.setColumnWidth(9, 70)
#         # self.table.setColumnWidth(10, self.ROW_HEIGHT) # <extra thumbnail>
#         # self.table.setColumnWidth(10, 70) # <extra thumbnail>
#         # self.table.setColumnWidth(10, 100)
#         # self.updateRowHeight(self.ROW_HEIGHT) #0508-
#
#         self.set_headers()
#
#         # logger.info("<<<< set_data <<<<")
#         for section in range(self.table.verticalHeader().count()):
#             self.table.verticalHeader().resizeSection(section, self.ROW_HEIGHT)
#
#         self.table.sortByColumn(4, Qt.DescendingOrder)
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
#         self.project_paths = cfg.settings['projects']
#         # self.project_paths = []
#         projects, thumbnail_first, thumbnail_last, created, modified, \
#         n_sections, location, img_dimensions, bytes, gigabytes, extra = \
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
#                 logger.error('Unable to locate or load data model: %s' % p)
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
#             try:    location.append(p)
#             except: location.append('Unknown')
#             extra_toplevel_paths = glob(f'{project_dir}/*.tif')
#             # logger.critical(f"extra_toplevel_paths = {extra_toplevel_paths}")
#             #Todo refactor this
#             # if extra_toplevel_paths != []:
#             if dm['data']['has_cal_grid']:
#                 extra.append(dm['data']['cal_grid_path'])
#             else:
#                 extra.append('No Thumbnail')
#             # extra.append(os.path.join(get_appdir(), 'resources', 'no-image.png'))
#
#         # logger.info('<<<< get_data <<<<')
#         # return zip(projects, location, thumbnail_first, thumbnail_last, created, modified,
#         #            n_sections, img_dimensions, bytes, gigabytes, extra)
#         return zip(location, thumbnail_first, thumbnail_last, extra, created, modified,
#                    n_sections, img_dimensions, bytes, gigabytes)
#
#             # logger.info('Getting project location...')
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
    # logger.info(f'caller:{inspect.stack()[1].function}')
    # logger.info('Validating selection %s...' % cfg.selected_file)
    # called by setSelectionPathText
    path, extension = os.path.splitext(path)
    # if extension != '.swiftir':
    if extension not in ('.swiftir','.json'):
        return False
    else:
        # logger.info('Directory contains .zarray -> selection is a valid project')
        return True

def validate_zarr_selection(path) -> bool:
    # logger.info(f'caller:{inspect.stack()[1].function}')
    # logger.info('Validating selection %s...' % cfg.selected_file)
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
    for s in dm.scales():
        if s != 'scale_1':
            siz = (np.array(dm.image_size(s='scale_1')) / dm.scale_val(s)).astype(int).tolist()
            logger.info(f"Setting size for {s} to {siz}...")
            dm['data']['scales'][s]['image_src_size'] = siz




class SeriesConfig(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        logger.info('')
        self.parent = parent
        self._settings = {}
        self.initUI()
        # self.setStyleSheet("""font-size: 10px;""")


    def getSettings(self):

        cfg.main_window.hud('Setting series configuration...')
        self._settings['scale_factors'] = list(map(int, self.scales_input.text().split(' ')))
        self._settings['clevel'] = int(self.clevel_input.text())
        self._settings['cname'] = self.cname_combobox.currentText()
        self._settings['chunkshape'] = (int(self.le_chunk_z.text()),
                                          int(self.le_chunk_y.text()),
                                          int(self.le_chunk_x.text()))
        self._settings['scales'] = {}
        # if cfg.data['data']['has_cal_grid']:
        for sv in self._settings['scale_factors']:
            res_x = int(self.le_res_x.text()) * sv
            res_y = int(self.le_res_y.text()) * sv
            res_z = int(self.le_res_z.text())
            self._settings['scales'][sv]['resolution'] = [res_x, res_y, res_z]

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
        tip = "Scale factors, space-delimited.\nThis would generate a 4x 2x and 1x scale_key hierarchy:\n\n4 2 1"
        # self.scale_instructions_label = QLabel(tip)
        # self.scale_instructions_label.setStyleSheet("font-size: 11px;")
        self.scales_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))

        wScaling = HWidget(QLabel('Scale Factors: '), self.scales_input)
        # wScaling.layout.setAlignment(Qt.AlignLeft)

        '''Voxel Size (Resolution) Fields'''
        tip = "Resolution or size of each voxel (nm)"
        self.le_res_x = QLineEdit(self)
        self.le_res_y = QLineEdit(self)
        self.le_res_z = QLineEdit(self)
        self.le_res_x.setFixedSize(QSize(24, 18))
        self.le_res_y.setFixedSize(QSize(24, 18))
        self.le_res_z.setFixedSize(QSize(24, 18))
        self.le_res_x.setValidator(QIntValidator())
        self.le_res_y.setValidator(QIntValidator())
        self.le_res_z.setValidator(QIntValidator())
        self.resolution_widget = HWidget(QLabel("x:"), self.le_res_x,
                                         QLabel("y:"), self.le_res_y,
                                         QLabel("z:"), self.le_res_z)
        self.resolution_widget.layout.setSpacing(4)
        self.resolution_widget.setToolTip(tip)

        wVoxelSize = HWidget(QLabel('Voxel Size (nm): '), self.resolution_widget)
        wVoxelSize.layout.setAlignment(Qt.AlignCenter)

        tip = 'Zarr Compression Level\n(default=5)'
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clevel_input.setAlignment(Qt.AlignCenter)
        self.clevel_input.setText(str(cfg.CLEVEL))
        self.clevel_input.setFixedSize(QSize(24,18))
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)

        tip = f'Compression Type (default={cfg.CNAME})'
        self.cname_label = QLabel('Compression Option:')
        self.cname_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["none", "zstd", "zlib"])
        self.cname_combobox.setFixedSize(QSize(64,18))

        labType = QLabel('Compress: ')
        labLevel = QLabel('Level (1-9): ')
        wCompression = HWidget(labType, self.cname_combobox, QLabel(' '), labLevel, self.clevel_input)
        wCompression.layout.setAlignment(Qt.AlignCenter)

        '''Chunk Shape'''
        self.chunk_shape_label = QLabel("Chunk Shape:")
        self.le_chunk_x = QLineEdit(self)
        self.le_chunk_y = QLineEdit(self)
        self.le_chunk_z = QLineEdit(self)
        self.le_chunk_x.setFixedSize(QSize(40, 18))
        self.le_chunk_y.setFixedSize(QSize(40, 18))
        self.le_chunk_z.setFixedSize(QSize(20, 18))
        self.le_chunk_x.setValidator(QIntValidator())
        self.le_chunk_y.setValidator(QIntValidator())
        self.le_chunk_z.setValidator(QIntValidator())
        self.chunk_shape_widget = HWidget(QLabel("x:"), self.le_chunk_x,
                                          QLabel("y:"), self.le_chunk_y,
                                          QLabel("z:"), self.le_chunk_z)
        self.chunk_shape_widget.layout.setSpacing(4)
        txt = "The way volumetric data will be stored. Zarr is an open-source " \
              "format for the storage of chunked, compressed, N-dimensional " \
              "arrays with an interface similar to NumPy."
        txt = '\n'.join(textwrap.wrap(txt, width=60))
        wChunk = HWidget(QLabel('Chunk Shape: '), self.chunk_shape_widget)
        wChunk.setToolTip(txt)
        wChunk.layout.setAlignment(Qt.AlignCenter)



        hbl = HBL(wScaling,
                  QLabel(' '),
                  wVoxelSize,
                  QLabel(' '),
                  wCompression,
                  QLabel(' '),
                  wChunk,
                  ExpandingHWidget(self))

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

def setWebengineProperties(webengine):
    webengine.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    webengine.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    webengine.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)