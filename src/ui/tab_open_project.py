#!/usr/bin/env python3

import os
import sys
import json
import shutil
import inspect
import logging
import platform
import textwrap
from glob import glob
from pathlib import Path
import multiprocessing as mp

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QAbstractItemView, \
    QSplitter, QTableWidget, QTableWidgetItem, QSlider, QGridLayout, QFrame, QPushButton, \
    QSizePolicy, QSpacerItem, QLineEdit, QMessageBox, QDialog, QFileDialog, QStyle, QStyledItemDelegate, \
    QListView, QApplication, QScrollArea
from qtpy.QtCore import Qt, QRect, QUrl, QDir, QSize, QPoint
from qtpy.QtGui import QGuiApplication, QFont, QPixmap, QPainter, QKeySequence, QColor

from src.ui.file_browser import FileBrowser
from src.ui.file_browser_tacc import FileBrowserTacc
from src.funcs_image import ImageSize
from src.autoscale import autoscale
from src.helpers import get_project_list, list_paths_absolute, get_bytes, absFilePaths, getOpt, setOpt, \
    print_exception, append_project_path, configure_project_paths, delete_recursive, \
    create_project_structure_directories, makedirs_exist_ok, natural_sort, initLogFiles, is_tacc, is_joel, hotkey, \
    get_appdir, caller_name
from src.data_model import DataModel
from src.ui.tab_project import ProjectTab
from src.ui.timer import Timer
from src.ui.tab_zarr import ZarrTab
from src.ui.dialogs import QFileDialogPreview, NewConfigureProjectDialog
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel, Button, SmallButton
from src.ui.tab_project import VerticalLabel
from src.ui.thumbnail import ThumbnailFast
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
        self.user_projects = UserProjects(parent=self)
        self.initUI()
        self.row_height_slider.setValue(self.user_projects.ROW_HEIGHT)
        # self.row_height_slider.setValue(getOpt('state,open_project_tab,row_height'))
        # p = self.palette()
        # p.setColor(self.backgroundRole(), QColor('#ede9e8'))
        # self.USE_CAL_GRID = False
        self.selected_file = ''

        clipboard = QGuiApplication.clipboard()
        clipboard.dataChanged.connect(self.onClipboardChanged)
        #Note: when clipboard changes during app out-of-focus, clipboard changed signal gets emitted
        #once focus is returned. This is the ideal behavior.

        # self.setStyleSheet("font-size: 10px; color: #f3f6fb;")
        self.setStyleSheet("font-size: 10px; color: #161c20;")

    def onClipboardChanged(self):
        print('Clipboard changed!')
        buffer = QApplication.clipboard().text()
        tip = 'Your Clipboard:\n' + '\n'.join(textwrap.wrap(buffer[0:512], width=35)) #set limit on length of tooltip string
        print('\n' + tip)
        self._buttonBrowserPaste.setToolTip(tip)


    def initUI(self):

        # User Projects Widget
        self.userProjectsWidget = QWidget()
        # lab = QLabel('Saved AlignEM-SWiFT Projects:')
        # lab = QLabel('Project Management')
        # lab.setStyleSheet('font-size: 13px; font-weight: 600; color: #161c20;')


        self.row_height_slider = Slider(self)
        self.row_height_slider.setMinimum(16)
        self.row_height_slider.setMaximum(180)
        self.row_height_slider.setMaximumWidth(120)
        self.row_height_slider.valueChanged.connect(self.user_projects.updateRowHeight)
        self.row_height_slider.valueChanged.connect(
            lambda: setOpt('state,open_project_tab,row_height', self.row_height_slider.value()))
        # self.row_height_slider.setValue(self.initial_row_height)
        # self.updateRowHeight(self.initial_row_height)

        self.fetchSizesCheckbox = QCheckBox()
        self.fetchSizesCheckbox.setStyleSheet("font-size: 10px;")
        # self.fetchSizesCheckbox.setChecked(getOpt(lookup='ui,FETCH_PROJECT_SIZES'))
        self.fetchSizesCheckbox.setChecked(getOpt(lookup='ui,FETCH_PROJECT_SIZES'))
        self.fetchSizesCheckbox.toggled.connect(
            lambda: setOpt('ui,FETCH_PROJECT_SIZES', self.fetchSizesCheckbox.isChecked()))

        self.fetchSizesCheckbox.toggled.connect(self.user_projects.set_data)


        self.controls = QWidget()
        self.controls.setFixedHeight(18)
        hbl = HBL()
        # hbl.setContentsMargins(2, 0, 2, 0)
        hbl.addWidget(QLabel('  '))
        # hbl.addStretch(1)
        hbl.addWidget(HWidget(QLabel(' Row Height '), self.row_height_slider), alignment=Qt.AlignLeft)
        hbl.addWidget(QLabel('  '))
        # hbl.addStretch(1)
        hbl.addWidget(HWidget(QLabel(' Fetch Sizes '), self.fetchSizesCheckbox), alignment=Qt.AlignLeft)
        hbl.addStretch(10)
        # hbl.addWidget(ExpandingHWidget(self))
        self.controls.setLayout(hbl)
        self.controls.setStyleSheet('font-size: 10px;')

        self.new_project_lab1 = QLabel()
        self.new_project_lab1.setStyleSheet('font-size: 13px; font-weight: 600; padding: 4px; color: #f3f6fb; background-color: #222222;')
        self.new_project_lab2 = QLabel()
        self.new_project_lab2.setStyleSheet('font-size: 11px; font-weight: 600; padding: 4px; color: #f3f6fb; background-color: #222222;')
        # self.new_project_lab2.setStyleSheet('font-size: 11px; font-weight: 600; padding: 4px; color: #9fdf9f; background-color: #222222;')
        self.new_project_lab2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.new_project_lab_gap = QLabel('      ')
        self.new_project_lab_gap.setStyleSheet('color: #f3f6fb; background-color: #222222; padding: 0px;')
        self.new_project_header = HWidget(self.new_project_lab1, self.new_project_lab_gap, self.new_project_lab2)
        self.new_project_header.setFixedHeight(28)
        self.new_project_header.layout.setSpacing(0)
        self.new_project_header.setAutoFillBackground(True)
        self.new_project_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.new_project_header.setStyleSheet('background-color: #222222;')
        self.new_project_header.hide()

        self.vbl_projects = QVBoxLayout()
        self.vbl_projects.setSpacing(1)
        self.vbl_projects.setContentsMargins(2, 2, 2, 2)
        self.vbl_projects.addWidget(self.user_projects)
        self.vbl_projects.addWidget(self.controls)
        # self.vbl_projects.addWidget(self.new_project_header)
        self.userProjectsWidget.setLayout(self.vbl_projects)


        # User Files Widget
        self.userFilesWidget = QWidget()
        lab = QLabel('Open AlignEM-SWIFT Project or...\nOpen OME-NGFF Zarr in Neuroglancer or...\nSelect folder of images for new project...')
        lab.setStyleSheet('font-size: 10px; font-weight: 600; color: #161c20;')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(4, 4, 4, 4)
        vbl.addWidget(HWidget(lab))
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


        # self._buttonNew = QPushButton('New Project')
        tip = "Create a new project by selecting which images to import."
        self._buttonNew = QPushButton(f"Select Images {hotkey('I')}")
        self._buttonNew.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self._buttonNew.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonNew.setShortcut('Ctrl+I')
        self._buttonNew.clicked.connect(self.new_project)
        self._buttonNew.setFixedSize(button_size)
        self._buttonNew.setStyleSheet('font-size: 9px;')

        self._buttonCancelProjectFromTiffFolder = QPushButton(f"Cancel")
        # self._buttonProjectFromTiffFolder1.setShortcut()
        self._buttonCancelProjectFromTiffFolder.setStyleSheet('font-size: 9px;')
        def fn():
            self.le_project_name_w.hide()
        self._buttonCancelProjectFromTiffFolder.clicked.connect(fn)
        self._buttonCancelProjectFromTiffFolder.setFixedSize(button_size)

        self.cbCalGrid = QCheckBox('Image 0 is calibration grid')
        # def setCalGridData():
        #     try:
        #         cfg.data['data']['has_cal_grid'] = self.cbCalGrid.isChecked()
        #     except:
        #         print_exception()
        # self.cbCalGrid.stateChanged.connect(fn)
        self.cbCalGrid.setChecked(False)
        self.cbCalGrid.hide()

        # self._buttonDelete = QPushButton(f"Delete Project")
        self._buttonDelete = QPushButton(f"Delete Project {hotkey('D')}")
        self._buttonDelete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonDelete.setShortcut('Ctrl+D')
        self._buttonDelete.setStyleSheet('font-size: 9px;')
        self._buttonDelete.setEnabled(False)
        self._buttonDelete.clicked.connect(self.delete_project)
        self._buttonDelete.setFixedSize(button_size)
        # self._buttonDelete.hide()



        # self._buttonNew = QPushButton('Remember')
        # self._buttonNew.setStyleSheet("font-size: 9px;")
        # self._buttonNew.clicked.connect(self.new_project)
        # self._buttonNew.setFixedSize(64, 20)
        # # self._buttonNew.setStyleSheet(w)

        def paste_from_buffer():
            buffer = QApplication.clipboard().text()
            # path_exists = os.path.exists(buffer)
            # if path_exists:
            #     logger.info('Paste buffer text is a valid path.')
            #     cfg.mw.tell('Paste buffer text is a valid path')
            #     self.selectionReadout.setText(os.path.abspath(buffer))
            #     self.validate_path()
            # else:
            #     cfg.mw.warn('Paste buffer text is not a valid path')
            #     logger.warn('Paste buffer text is not a valid path')
            self.selectionReadout.setText(os.path.abspath(buffer))
            self.validate_path()

        self._buttonBrowserPaste = QPushButton(f"Paste {hotkey('V')}")
        self._buttonBrowserPaste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttonBrowserPaste.setToolTip('Paste path from clipboard')
        self._buttonBrowserPaste.clicked.connect(paste_from_buffer)
        self._buttonBrowserPaste.setFixedSize(QSize(64,18))
        self._buttonBrowserPaste.setStyleSheet('font-size: 9px;')
        # self._buttonBrowserPaste.setEnabled(os.path.exists(QApplication.clipboard().text()))


        self.lab_path_exists = cfg.lab_path_exists = QLabel('Path Exists')
        self.lab_path_exists.setFixedWidth(80)
        self.lab_path_exists.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lab_path_exists.setAlignment(Qt.AlignRight)
        self.lab_path_exists.setObjectName('validity_label')
        self.lab_path_exists.setFixedHeight(16)
        self.lab_path_exists.setAlignment(Qt.AlignRight)
        self.lab_path_exists.hide()

        self.lab_project_name = QLabel(' New Project Path: ')
        self.lab_project_name.setStyleSheet("font-size: 10px; font-weight: 600; color: #ede9e8; background-color: #339933; border-radius: 4px;")
        self.lab_project_name.setFixedHeight(18)
        self.le_project_name = QLineEdit()
        self.le_project_name = cfg.le_project_name = QLineEdit()
        self.le_project_name.setReadOnly(False)
        def fn():
            logger.info('')
            self._buttonProjectFromTiffFolder2.setEnabled(not os.path.exists(self.le_project_name.text()))
            self.lab_path_exists.setVisible(os.path.exists(self.le_project_name.text()))

        self.le_project_name.textChanged.connect(fn)
        # self.le_project_name.textEdited.connect(fn)
        self.le_project_name.setFixedHeight(20)
        self.le_project_name.setMinimumWidth(400)

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
        hbl.setContentsMargins(6, 2, 6, 2)
        hbl.addWidget(self.labNewProject)
        hbl.addWidget(self._buttonNew)
        hbl.addWidget(self._buttonProjectFromTiffFolder1)
        # hbl.addWidget(self.selectionReadout)
        hbl.addWidget(self.selectionReadout_w_overlay)
        # hbl.addWidget(self.validity_label)
        hbl.addWidget(self._buttonOpen)
        hbl.addWidget(self._buttonDelete)
        hbl.addWidget(self._buttonBrowserPaste)
        hbl.addWidget(self.cbCalGrid)
        hbl.setStretch(3,5)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hbl.addSpacerItem(self.spacer_item_docs)

        self._actions_widget = QWidget()
        self._actions_widget.setFixedHeight(26)
        self._actions_widget.setLayout(hbl)


        # self._actions_widget.setStyleSheet("""
        # QPushButton {
        #     font-size: 12px;
        #     font-weight: 600;
        #     font-family: Tahoma, sans-serif;
        #     color: #339933;
        #     background-color: #ede9e8;
        #     border-width: 1px;
        #     border-color: #339933;
        #     border-style: solid;
        #     padding: 1px;
        #     border-radius: 4px;
        #     outline: none;w
        # }
        #
        # QPushButton:disabled {
        #     border-width: 1px;
        #     border-color: #dadada;
        #     border-style: solid;
        #     background-color: #ede9e8;
        #     padding: 1px;
        #     border-radius: 4px;
        #     color: #dadada;
        # }
        # """)

        # self._actions_widget.setStyleSheet(style)

        # with open('src/style/buttonstyle.qss', 'r') as f:
        #     button_gradient_style = f.read()
        # self._actions_widget.setStyleSheet(button_gradient_style)


        self._splitter = QSplitter()

        self._splitter.addWidget(self.userProjectsWidget)
        self._splitter.addWidget(self.userFilesWidget)
        self._splitter.setSizes([700, 300])

        self.vbl_main = VBL()
        self.vbl_main.addWidget(self._splitter)
        self.vbl_main.addWidget(self._actions_widget)
        self.vbl_main.addWidget(self.le_project_name_w)
        self.vbl_main.addWidget(self.new_project_header)
        # self.vbl_main.addWidget(<temp widgets>)

        # self.layout = QVBoxLayout()
        # self.layout.setContentsMargins(4, 0, 4, 0)
        # self.layout.addWidget(self._splitter)
        # # self.layout.addWidget(self.embed)
        # self.layout.addWidget(self._actions_widget)
        # # self.layout.addWidget(self.new_project_header)
        # self.setLayout(self.layout)

        self.setLayout(self.vbl_main)



    def hideMainUI(self):
        self._splitter.hide()
        self._actions_widget.hide()
        self.new_project_header.show()
        # pass


    def showMainUI(self):
        self._splitter.show()
        self._actions_widget.show()
        self.new_project_header.hide()

    def validate_path(self):
        logger.info(f'caller:{inspect.stack()[1].function}')
        path = self.selectionReadout.text()
        # logger.info(f'Validating path : {path}')
        if validate_project_selection(path):
            self._buttonOpen.setText(f"Open Project {hotkey('O')}")
            logger.info(f'The path selected is a valid AlignEM-SWIFT project')
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
        logger.info(f'>>>> userSelectionChanged >>>>')
        caller = inspect.stack()[1].function
        # if caller == 'initTableData':
        #     return
        row = self.user_projects.table.currentIndex().row()
        try:
            try:
                self.selected_file = self.user_projects.table.item(row, 0).text()
            except:
                pass
            logger.info(f'row: {str(row)}, selected:\n{self.selected_file}')
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
        logger.critical('')
        self.NEW_PROJECT_PATH = self.le_project_name.text()
        # self.USE_CAL_GRID = self.cbCalGrid.isChecked()
        self.new_project(skip_to_config=True)
        self.le_project_name_w.hide()
        self.le_project_name.setText('')


    def new_project(self, mendenhall=False, skip_to_config=False):
        logger.info('\n\nStarting A New Project...\n')
        cfg.mw.tell('Starting A New Project...')
        cfg.mw._is_initialized = 0

        if not skip_to_config:
            self.hideMainUI()
            cfg.mw.stopPlaybackTimer()
            cfg.mw.tell('New Project Path:')
            self.new_project_lab1.setText('New Project (Step: 1/3) - Name & Location')
            cfg.mw.set_status('New Project (Step: 1/3) - Name & Location')

            '''Step 1/3'''
            logger.info('Creating name_dialog...')
            self.name_dialog = QFileDialog()
            self.vbl_main.addWidget(self.name_dialog)
            self.name_dialog.setContentsMargins(0,0,0,0)
            self.name_dialog.setWindowFlags(Qt.FramelessWindowHint)
            self.name_dialog.setOption(QFileDialog.DontUseNativeDialog)

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
            cfg.mw.set_status('New Project (Step: 2/3) - Import TIFF Images')
            if self.name_dialog.exec() == QFileDialog.Accepted:
                logger.info('Save File Path: %s' % self.name_dialog.selectedFiles()[0])
                filename = self.name_dialog.selectedFiles()[0]
                self.new_project_lab2.setText(filename)
                self.name_dialog.close()
            else:
                self.showMainUI()
                self.name_dialog.close()
                return 1

            if filename in ['', None]:
                logger.info('New Project Canceled.')
                cfg.mw.warn("New Project Canceled.")
                self.showMainUI()
                return
            cfg.mw.set_status('')

            filename.replace(' ','_')
            if not filename.endswith('.swiftir'):
                filename += ".swiftir"
            if os.path.exists(filename):
                logger.warning("The file '%s' already exists." % filename)
                cfg.mw.warn("The file '%s' already exists." % filename)
                path_proj = os.path.splitext(filename)[0]
                cfg.mw.tell(f"Removing Extant Project Directory '{path_proj}'...")
                logger.info(f"Removing Extant Project Directory '{path_proj}'...")
                shutil.rmtree(path_proj, ignore_errors=True)
                cfg.mw.tell(f"Removing Extant Project File '{path_proj}'...")
                logger.info(f"Removing Extant Project File '{path_proj}'...")
                os.remove(filename)

            self.NEW_PROJECT_PATH = filename

        path,_ = os.path.splitext(self.NEW_PROJECT_PATH)
        # self.NEW_PROJECT_PATH = path + '.swiftir'
        self.NEW_PROJECT_PATH = path

        makedirs_exist_ok(path, exist_ok=True)

        # cfg.data = DataModel(name=path, mendenhall=mendenhall)
        cfg.data = dm = DataModel(name=self.NEW_PROJECT_PATH)
        # cfg.data.set_defaults()

        if skip_to_config:
            cfg.data['data']['has_cal_grid'] = self.cbCalGrid.isChecked()


        # cfg.project_tab = ProjectTab(self, path=path, datamodel=cfg.data)
        # cfg.dataById[id(cfg.project_tab)] = cfg.data
        self.new_project_lab2.setText(path)

        if mendenhall:
            create_project_structure_directories(cfg.data.dest(), ['scale_1'])
        else:

            if not skip_to_config:
                '''Step 2/3...'''
                result = self.import_multiple_images(path)
                if result == 1:
                    cfg.mw.warn('No images were imported - canceling new project')
                    self.showMainUI()
                    return


            self.NEW_PROJECT_IMAGES = natural_sort(self.NEW_PROJECT_IMAGES)

            if cfg.data['data']['has_cal_grid']:
                self.NEW_PROJECT_IMAGES = self.NEW_PROJECT_IMAGES[1:]
                cfg.data['data']['cal_grid_path'] = self.NEW_PROJECT_IMAGES[0]
                try:
                    shutil.copy(cfg.data['data']['cal_grid_path'], cfg.data.dest())
                except:
                    print_exception()


            cfg.data.set_source_path(os.path.dirname(self.NEW_PROJECT_IMAGES[0]))  # Critical!
            cfg.mw.tell(f'Importing {len(self.NEW_PROJECT_IMAGES)} Images...')
            logger.info(f'Selected Images: \n{self.NEW_PROJECT_IMAGES}')
            cfg.data.append_images(self.NEW_PROJECT_IMAGES)

            cfg.mw.tell(f'Dimensions: %dx%d' % cfg.data.image_size(s='scale_1'))

            cfg.data.set_defaults()

            self.le_project_name_w.hide()

            '''Step 3/3'''
            self.new_project_lab1.setText('New Project (Step: 3/3) - Global Configuration')
            cfg.mw.set_status('New Project (Step: 3/3) - Global Configuration')
            logger.info('Showing new configure project dialog')
            dialog = NewConfigureProjectDialog(parent=self)
            dialog.setWindowFlags(Qt.FramelessWindowHint)
            self.vbl_main.addWidget(dialog)
            # cfg.data = dm
            result = dialog.exec()
            self.showMainUI()
            # logger.info(f'result = {result}, type = {type(result)}')
            cfg.mw.set_status('')
            if result:
                logger.info('Save File Path: %s' % path)
            else:
                # self.showMainUI()
                dialog.close()
                return 1

            # cfg.project_tab = ProjectTab(self, path=path, datamodel=dm)
            ID = id(cfg.project_tab)
            logger.critical(f'New Tab ID: {ID}')
            cfg.dataById[id(cfg.project_tab)] = dm

            # self.showMainUI()
            dm.set_defaults()

            cfg.project_tab = ProjectTab(self, path=path, datamodel=dm)

            initLogFiles(dm)
            # cfg.mw._disableGlobTabs()

            # self.user_projects.table.rowCount()

            font = QFont()
            font.setPointSize(11)
            font.setBold(True)

            # self.table.setItem(i, j, item)
            rc = self.user_projects.table.rowCount()
            self.user_projects.table.insertRow(rc)
            self.user_projects.table.setRowHeight(rc, self.row_height_slider.value())

            twi = QTableWidgetItem('Initializing\nProject...')
            twi.setFont(font)
            self.user_projects.table.setItem(rc, 0, twi)

            font0 = QFont()
            font0.setPointSize(10)
            twi = QTableWidgetItem(cfg.data.dest())
            twi.setFont(font0)
            self.user_projects.table.setItem(rc, 1, twi)
            try:
                if dm['data']['autoalign_flag']:
                    cfg.mw.tell(
                        f'Auto-align flag is set. Aligning {dm.scale_pretty(dm.coarsest_scale_key())}...')
                    cfg.ignore_pbar = False
                    cfg.mw.showZeroedPbar(set_n_processes=7)
                    autoscale(dm=dm, make_thumbnails=True, set_pbar=False)
                    # cfg.mw.setdw_matches(True)
                    cfg.mw.alignAll(set_pbar=False, force=True, ignore_bb=True)
                else:
                    autoscale(dm=dm, make_thumbnails=True, set_pbar=True)
            except:
                print_exception()
            finally:
                # cfg.mw.enableAllTabs()
                # QApplication.processEvents()
                cfg.mw._autosave(silently=True)
                cfg.data = dm
                cfg.mw.addGlobTab(cfg.project_tab, os.path.basename(path))
                cfg.mw.setUpdatesEnabled(False)
                try:
                    cfg.mw.onStartProject()
                except:
                    print_exception()
                finally:
                    cfg.mw.setUpdatesEnabled(True)


        QApplication.processEvents()

        logger.critical(f'Appending {filename} to .swift_cache...')
        userprojectspath = os.path.join(os.path.expanduser('~'), '.swift_cache')
        with open(userprojectspath, 'a') as f:
            f.write(filename + '\n')
        cfg.mw._autosave()
        self.user_projects.set_data()
        QApplication.processEvents()
        cfg.mw._is_initialized = 1
        cfg.pt.initNeuroglancer()

        logger.critical('<<<< new_project <<<<')



    def import_multiple_images(self, path):
        ''' Import images into data '''
        cfg.mw.tell('Import Images:')

        '''Step 2/3'''
        '''Dialog for importing images. Returns list of filenames.'''
        dialog = QFileDialogPreview()
        dialog.setWindowFlags(Qt.FramelessWindowHint)

        self.vbl_main.addWidget(dialog)
        # dialog.setOption(QFileDialog.DontUseNativeDialog)
        self.new_project_lab1.setText('New Project (Step: 2/3) - Import TIFF Images')
        cfg.mw.set_status('New Project (Step: 2/3) - Import TIFF Images')
        # dialog.setWindowTitle('New Project (Step: 2/3) - Import TIFF Images')
        dialog.setNameFilter('Images (*.tif *.tiff)')
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.setModal(True)
        urls = dialog.sidebarUrls()
        dialog.setSidebarUrls(urls)



        # urls = self.name_dialog.sidebarUrls()
        #
        # corral_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'
        #
        # if '.tacc.utexas.edu' in platform.node():
        #     urls.append(QUrl.fromLocalFile(os.getenv('SCRATCH')))
        #     urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
        #     urls.append(QUrl.fromLocalFile(os.getenv('HOME')))
        #     urls.append(QUrl.fromLocalFile(corral_dir))
        #
        # else:
        #     urls.append(QUrl.fromLocalFile(QDir.homePath()))
        #     urls.append(QUrl.fromLocalFile('/tmp'))
        #     if os.path.exists('/Volumes'):
        #         urls.append(QUrl.fromLocalFile('/Volumes'))
        #     if is_joel():
        #         if os.path.exists('/Volumes/3dem_data'):
        #             urls.append(QUrl.fromLocalFile('/Volumes/3dem_data'))
        # self.name_dialog.setSidebarUrls(urls)

        places = getSideBarPlacesImportImages()

        sidebar = self.findChild(QListView, "sidebar")
        delegate = StyledItemDelegate(sidebar)
        delegate.mapping = places
        sidebar.setItemDelegate(delegate)


        if dialog.exec_() == QDialog.Accepted:
            filenames = dialog.selectedFiles()
        else:
            logger.warning('Import images dialog did not return a valid file list')
            cfg.mw.warn('Import images dialog did not return a valid file list')
            self.showMainUI()
            return 1

        if filenames == 1:
            logger.warning('New Project Canceled')
            cfg.mw.warn('No Project Canceled')
            self.showMainUI()
            return 1

        self.NEW_PROJECT_IMAGES = natural_sort(filenames)

        # files_sorted = natural_sort(filenames)
        # cfg.data.set_source_path(os.path.dirname(files_sorted[0])) #Critical!
        # cfg.mw.tell(f'Importing {len(files_sorted)} Images...')
        # logger.info(f'Selected Images: \n{files_sorted}')
        # cfg.data.append_images(files_sorted)
        # cfg.data.link_reference_sections()

        logger.critical(f'destination: {cfg.data.dest()}')



    def setSelectionPathText(self, path):
        logger.info('')
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
            logger.info(f'Opening Project {filename}...')
            try:
                with open(filename, 'r') as f:
                    cfg.data = DataModel(data=json.load(f))
                cfg.data.set_defaults()
                cfg.mw._autosave()
            except:
                cfg.mw.warn(f'No Such File Found: {filename}')
                logger.warning(f'No Such File Found: {filename}')
                print_exception()
                return
            else:
                logger.info(f'Project Opened!')
            append_project_path(filename)
            cfg.data.set_paths_absolute(filename=filename)
            cfg.project_tab = ProjectTab(self, path=cfg.data.dest() + '.swiftir', datamodel=cfg.data)
            cfg.dataById[id(cfg.project_tab)] = cfg.data
            cfg.mw.setUpdatesEnabled(False)
            try:
                cfg.mw.onStartProject()
            except:
                print_exception()
            finally:
                cfg.mw.setUpdatesEnabled(True)
            cfg.mw.addGlobTab(cfg.project_tab, os.path.basename(cfg.data.dest()) + '.swiftir')
            cfg.mw._setLastTab()
            # cfg.mw.hud.done()
            cfg.mw._is_initialized = 1
            cfg.pt.initNeuroglancer()
        else:
            cfg.mw.warn("Invalid Path")


    def delete_project(self):
        logger.info('')
        # project_file = self.selected_file
        project_file = self.selectionReadout.text()
        project = os.path.splitext(project_file)[0]
        if not validate_project_selection(project_file):
            logger.warning('Invalid Project For Deletion (!)\n%s' % project)
            return
        cfg.mw.warn("Delete this project? %s" % project)
        txt = "Are you sure you want to PERMANENTLY DELETE " \
              "the following project?\n\n" \
              "Project: %s" % project
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
            logger.info('Deleting Project File %s...' % project_file)
            cfg.mw.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)
            logger.warning('Executing Delete Project Permanently Instruction...')

        logger.info(f'Deleting Project File: {project_file}...')
        cfg.mw.warn(f'Deleting Project File: {project_file}...')
        try:
            os.remove(project_file)
        except:
            print_exception()
        # else:
        #     cfg.mw.hud.done()

        logger.info('Deleting Project Data: %s...' % project)
        cfg.mw.warn('Deleting Project Data: %s...' % project)
        try:

            delete_recursive(dir=project)
            # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
            # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
        except:
            cfg.mw.warn('An Error Was Encountered During Deletion of the Project Directory')
            print_exception()
        else:
            cfg.mw.hud.done()

        cfg.mw.tell('Wrapping up...')
        configure_project_paths()
        if cfg.mw.globTabs.currentWidget().__class__.__name__ == 'OpenProject':
            try:
                cfg.mw.globTabs.currentWidget().user_projects.set_data()
            except:
                logger.warning('There was a problem updating the project list')
                print_exception()

        self.selectionReadout.setText('')

        cfg.mw.tell('Deletion Complete!')
        logger.info('Deletion Complete')

    # def keyPressEvent(self, event):
    #     print(event)
    #     self.keyevent = event
    #
    #     if event.matches(QKeySequence.Delete):
    #         self.delete_project()


        # if event.key() == Qt.Key_Delete:
        #     # self.parent.parent.delete_project()
        #     self.delete_project()
        # else:
        #     super().keyPressEvent(event)

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
#             # self.parent.parent.delete_project()
#             cfg.mw._getTabObject().delete_project()
#         else:
#             super().keyPressEvent(event)

class UserProjects(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent

        # self.initial_row_height = 64
        # self.ROW_HEIGHT = 64
        self.ROW_HEIGHT = 80

        self.counter1 = 0
        self.counter2 = 0
        # self.counter3 = 0
        # self.setFocusPolicy(Qt.StrongFocus)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # self.table.setAlternatingRowColors(True)
        # self.table = TableWidget(self)

        # self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection) #0507-  !!!!!!!!!!!!
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.Alignment(Qt.TextWordWrap))
        def countCurrentItemChangedCalls(): self.counter2 += 1
        self.table.currentItemChanged.connect(countCurrentItemChangedCalls)
        self.table.currentItemChanged.connect(self.parent.userSelectionChanged)
        def countItemClickedCalls(): self.counter1 += 1
        self.table.itemClicked.connect(countItemClickedCalls)
        self.table.itemClicked.connect(self.parent.userSelectionChanged)
        # def onDoubleClick(): self.parent.open_project_selected()
        # self.table.itemDoubleClicked.connect(self.parent.open_project_selected)
        self.table.doubleClicked.connect(self.parent.open_project_selected) #Critical this always emits
        self.table.itemSelectionChanged.connect(self.parent.userSelectionChanged)  # Works!
        # self.table.itemSelectionChanged.connect(lambda: print('itemselectionChanged was emitted!'))  # Works!
        # self.table.itemPressed.connect(lambda: print('itemPressed was emitted!'))
        # self.table.cellActivated.connect(lambda: print('cellActivated was emitted!'))
        # self.table.currentItemChanged.connect(lambda: print('currentItemChanged was emitted!'))
        # self.table.itemDoubleClicked.connect(lambda: print('itemDoubleClicked was emitted!'))
        # self.table.cellChanged.connect(lambda: print('cellChanged was emitted!'))
        # self.table.cellClicked.connect(lambda: print('cellClicked was emitted!'))
        # self.table.itemChanged.connect(lambda: print('itemChanged was emitted!'))

        self.table.setColumnCount(12)
        self.set_headers()

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.table)
        # self.layout.addWidget(controls)
        self.setLayout(self.layout)
        self.set_data()
        # self.updateRowHeight(self.ROW_HEIGHT)
        # self.updateRowHeight(getOpt('state,open_project_tab,row_height'))

        # self.setStyleSheet("color: #161c20;")
        # self.setStyleSheet("font-size: 10px; color: #f3f6fb;")


    def updateRowHeight(self, h):
        for section in range(self.table.verticalHeader().count()):
            self.table.verticalHeader().resizeSection(section, h)
        self.table.setColumnWidth(1, h)
        self.table.setColumnWidth(2, h)
        self.table.setColumnWidth(3, h)
        # self.table.setColumnWidth(10, h)


    # def userSelectionChanged(self):
    #     caller = inspect.stack()[1].function
    #     # if caller == 'initTableData':
    #     #     return
    #     row = self.table.currentIndex().row()
    #     try:
    #         path = self.table.item(row,9).text()
    #     except:
    #         cfg.selected_file = ''
    #         logger.warning(f'No file path at project_table.currentIndex().row()! '
    #                        f'caller: {caller} - Returning...')
    #         return
    #     logger.info(f'path: {path}')
    #     cfg.selected_file = path
    #     cfg.mw.setSelectionPathText(path)
    #     # logger.info(f'counter1={self.counter1}, counter2={self.counter2}')


    def set_headers(self):
        self.table.setHorizontalHeaderLabels([
            "Location",
            "First\nSection",
            "Last\nSection",
            "Calibration\nGrid",
            "Created",
            "Last\nOpened",
            "#\nImgs",
            "Image\nSize (px)",
            "Disk Space\n(Bytes)",
            "Disk Space\n(Gigabytes)",
            "Tags"
        ])

        header = self.table.horizontalHeader()
        header.setFrameStyle(QFrame.Box | QFrame.Plain)
        header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
        self.table.setHorizontalHeader(header)


    def set_data(self):
        logger.info('')
        # logger.info(">>>> set_data >>>>")
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        self.table.clearContents()
        font0 = QFont()
        font0.setPointSize(10)
        self.table.setRowCount(0)
        for i, row in enumerate(self.get_data()):
            # logger.info(f'>>>> row #{i} >>>>')
            self.table.insertRow(i)
            for j, item in enumerate(row):
                if j == 0:
                    twi = QTableWidgetItem(str(item))
                    twi.setFont(font0)
                    self.table.setItem(i, j, twi)
                elif j in (1,2,3):
                    if item == 'No Thumbnail':
                        thumbnail = ThumbnailFast(self)
                        self.table.setCellWidget(i, j, thumbnail)
                    else:
                        thumbnail = ThumbnailFast(self, path=item)
                        self.table.setCellWidget(i, j, thumbnail)
                elif j in (4,5):
                    twi = QTableWidgetItem(item.replace("_", " "))
                    twi.setTextAlignment(Qt.AlignCenter)
                    twi.setFont(font0)
                    self.table.setItem(i, j, twi)
                elif j == 6:
                    twi = QTableWidgetItem(str(item))
                    twi.setFont(font0)
                    twi.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(i, j, twi)
                else:
                    twi = QTableWidgetItem(str(item))
                    twi.setFont(font0)
                    self.table.setItem(i, j, twi)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, self.ROW_HEIGHT) # <first thumbnail>
        self.table.setColumnWidth(2, self.ROW_HEIGHT) # <last thumbnail>
        self.table.setColumnWidth(3, self.ROW_HEIGHT) # <last thumbnail>
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(6, 40)
        self.table.setColumnWidth(7, 70)
        self.table.setColumnWidth(8, 70)
        self.table.setColumnWidth(9, 70)
        # self.table.setColumnWidth(10, self.ROW_HEIGHT) # <extra thumbnail>
        self.table.setColumnWidth(10, 70) # <extra thumbnail>
        # self.table.setColumnWidth(10, 100)
        # self.updateRowHeight(self.ROW_HEIGHT) #0508-

        # logger.info("<<<< set_data <<<<")
        for section in range(self.table.verticalHeader().count()):
            self.table.verticalHeader().resizeSection(section, self.ROW_HEIGHT)



    def get_data(self):
        logger.info('')
        # timer = Timer()
        # logger.info('>>>> get_data >>>>')
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        self.project_paths = get_project_list()
        projects, thumbnail_first, thumbnail_last, created, modified, \
        n_sections, location, img_dimensions, bytes, gigabytes, extra = \
            [], [], [], [], [], [], [], [], [], [], []

        logger.info(f'# saved projects: {len(self.project_paths)}')
        for p in self.project_paths:
            logger.info(f'Getting table entry data for {p}...')

            try:
                with open(p, 'r') as f:
                    dm = DataModel(data=json.load(f), quietly=True)
            except:
                # print_exception()
                logger.error('Unable to locate or load data model: %s' % p)

            logger.info(f'  DataModel Loaded')
            # timer.report()
            try:    created.append(dm.created)
            except: created.append('Unknown')
            # timer.report(extra='modified...')
            try:    modified.append(dm.modified)
            except: modified.append('Unknown')
            # timer.report(extra='n_sections...')
            try:    n_sections.append(len(dm))
            except: n_sections.append('Unknown')
            # timer.report(extra='img_dimensions...')
            try:    img_dimensions.append(dm.full_scale_size())
            except: img_dimensions.append('Unknown')
            # timer.report(extra='basename...')
            try:    projects.append(os.path.basename(p))
            except: projects.append('Unknown')
            # timer.report(extra='sizes...')
            project_dir = os.path.splitext(p)[0]
            try:
                if getOpt(lookup='ui,FETCH_PROJECT_SIZES'):
                    logger.info('Getting project size...')
                    _bytes = get_bytes(project_dir)
                    bytes.append(_bytes)
                    gigabytes.append('%.4f' % float(_bytes / 1073741824))
                else:
                    bytes.append('N/A')
                    gigabytes.append('N/A')
            except:
                bytes.append('Unknown')
                gigabytes.append('Unknown')
            # timer.report(extra='thumbnail first...')
            thumb_path = os.path.join(project_dir, 'thumbnails')
            absolute_content_paths = list_paths_absolute(thumb_path)
            try:    thumbnail_first.append(absolute_content_paths[0])
            except: thumbnail_first.append('No Thumbnail')
            # timer.report(extra='thumbnail last...')
            try:    thumbnail_last.append(absolute_content_paths[-1])
            except: thumbnail_last.append('No Thumbnail')
            # timer.report(extra='location...')
            try:    location.append(p)
            except: location.append('Unknown')
            # timer.report(extra='extra (cal grid)...')
            extra_toplevel_paths = glob(f'{project_dir}/*.tif')
            if extra_toplevel_paths:
                extra.append(extra_toplevel_paths[0])
            else:
                extra.append('No Thumbnail')
            # extra.append(os.path.join(get_appdir(), 'resources', 'no-image.png'))
            # timer.report()

        # logger.info('<<<< get_data <<<<')
        # return zip(projects, location, thumbnail_first, thumbnail_last, created, modified,
        #            n_sections, img_dimensions, bytes, gigabytes, extra)
        return zip(location, thumbnail_first, thumbnail_last, extra, created, modified,
                   n_sections, img_dimensions, bytes, gigabytes)

            # logger.info('Getting project location...')



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
    # logger.info('Validating selection %s...' % cfg.selected_file)
    # called by setSelectionPathText
    path, extension = os.path.splitext(path)
    if extension != '.swiftir':
        return False
    else:
        # logger.info('Directory contains .zarray -> selection is a valid project')
        return True

def validate_zarr_selection(path) -> bool:
    logger.info(f'caller:{inspect.stack()[1].function}')
    # logger.info('Validating selection %s...' % cfg.selected_file)
    # called by setSelectionPathText
    if os.path.isdir(path):
        if '.zarray' in os.listdir(path):
            # logger.info('Directory contains .zarray -> selection is a valid Zarr')
            return True
    return False

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


# class Label(QLabel):
#     def __init__(self, img):
#         super(Label, self).__init__()
#         self.setFrameStyle(QFrame.StyledPanel)
#         self.pixmap = QPixmap(img)
#
#     def paintEvent(self, event):
#         size = self.size()
#         painter = QPainter(self)
#         point = QPoint(0,0)
#         scaledPix = self.pixmap.scaled(size, Qt.KeepAspectRatio, transformMode = Qt.SmoothTransformation)
#         # start painting the snr from left upper corner
#         point.setX((size.width() - scaledPix.width())/2)
#         point.setY((size.height() - scaledPix.height())/2)
#         print(point.x(), ' ', point.y())
#         painter.drawPixmap(point, scaledPix)


style = """
/* white pussh buttons */

/*-----QPushButton-----*/
QPushButton{
	border-style: solid;
    border-color: #161c20;
	border-width: 1px;
	border-radius: 5px;
	color: rgb(0,0,0);
	padding: 2px;
	background-color: #f3f6fb;
}
QPushButton::default{
	border-style: solid;
    border-color: #161c20;
	border-width: 1px;
	border-radius: 5px;
	color: rgb(0,0,0);
	padding: 2px;
	background-color: #f3f6fb;
}
QPushButton:hover{
	border-style: solid;
	border-color: #161c20;
	border-width: 2px;
	border-radius: 5px;
	color: rgb(0,0,0);
	padding: 2px;
	background-color: #f3f6fb;
}
QPushButton:pressed{
}
QPushButton:disabled{
    background-color: #dadada;

	border-style: solid;
	border-color: #161c20;
	border-width: 1px;
	border-radius: 5px;
	color: #ede9e8;
	padding: 2px;
	background-color: rgb(142,142,142);
}

"""
