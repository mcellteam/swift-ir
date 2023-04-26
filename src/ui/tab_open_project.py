#!/usr/bin/env python3

import os
import json
import shutil
import inspect
import logging
import platform
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QAbstractItemView, \
    QSplitter, QTableWidget, QTableWidgetItem, QSlider, QGridLayout, QFrame, QPushButton, \
    QSizePolicy, QSpacerItem, QLineEdit, QMessageBox, QDialog, QFileDialog
from qtpy.QtCore import Qt, QRect, QUrl, QDir
from qtpy.QtGui import QFont, QPixmap, QPainter, QKeySequence

from src.ui.file_browser import FileBrowser
from src.funcs_image import ImageSize
from src.helpers import get_project_list, list_paths_absolute, get_bytes, absFilePaths, getOpt, setOpt, \
    print_exception, append_project_path, configure_project_paths, delete_recursive, \
    create_project_structure_directories, makedirs_exist_ok, natural_sort, initLogFiles, is_tacc, is_joel
from src.data_model import DataModel
from src.ui.tab_project import ProjectTab
from src.ui.tab_zarr import ZarrTab
from src.ui.dialogs import QFileDialogPreview, NewConfigureProjectDialog
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter, YellowTextLabel, Button, SmallButton

import src.config as cfg

__all__ = ['OpenProject']

logger = logging.getLogger(__name__)


class OpenProject(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setMinimumHeight(200)
        self.filebrowser = FileBrowser(parent=self)
        def fn():
            self.selectionReadout.setText(self.filebrowser.getSelectionPath())
        self.filebrowser.treeview.selectionModel().selectionChanged.connect(fn)
        self.filebrowser.setStyleSheet('border-width: 0px;')
        self.filebrowser.controlsNavigation.show()
        self.user_projects = UserProjects(parent=self)
        # self.embed = QFileDialogPreview()
        # self.embed.setStyleSheet("background-color: #f3f6fb;")
        self.initUI()
        self.row_height_slider.setValue(self.user_projects.ROW_HEIGHT)

        self.setStyleSheet("""
        QLineEdit {
            background-color: #f3f6fb;
            border-width: 1px;
            border-style: solid;
            border-color: #141414;
            /*selection-background-color: #ffcccb;*/
            /*background:#daebfe;*/
            font-size: 11px;
            font-family: Tahoma, sans-serif;
        }
        """)

    def initUI(self):
        # User Projects Widget
        self.userProjectsWidget = QWidget()
        # lab = QLabel('Saved AlignEM-SWiFT Projects:')
        lab = QLabel('Project Management')
        lab.setStyleSheet('font-size: 13px; font-weight: 600;')

        self.row_height_slider = Slider(self)
        self.row_height_slider.valueChanged.connect(self.user_projects.updateRowHeight)
        # self.row_height_slider.setValue(self.initial_row_height)
        # self.updateRowHeight(self.initial_row_height)

        self.fetchSizesCheckbox = QCheckBox('Fetch Sizes')
        # self.fetchSizesCheckbox.setStyleSheet('font-size: 11px; font-family: Tahoma, sans-serif;')
        # self.fetchSizesCheckbox.setChecked(getOpt(lookup='ui,FETCH_PROJECT_SIZES'))
        self.fetchSizesCheckbox.setChecked(getOpt(lookup='ui,FETCH_PROJECT_SIZES'))
        self.fetchSizesCheckbox.toggled.connect(
            lambda: setOpt('ui,FETCH_PROJECT_SIZES', self.fetchSizesCheckbox.isChecked()))

        self.fetchSizesCheckbox.toggled.connect(self.user_projects.set_data)

        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        controls = QWidget()
        controls.setFixedHeight(18)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 0, 2, 0)
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(w)
        hbl.addWidget(self.row_height_slider, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(QLabel('Row Height'))
        hbl.addWidget(self.fetchSizesCheckbox, alignment=Qt.AlignmentFlag.AlignRight)
        controls.setLayout(hbl)

        self.new_project_header = QLabel()
        self.new_project_header.setAlignment(Qt.AlignTop)
        self.new_project_header.setMinimumHeight(28)
        self.new_project_header.setStyleSheet('font-size: 13px; font-weight: 600; padding: 4px;')
        self.new_project_header.hide()

        self.vbl_projects = QVBoxLayout()
        self.vbl_projects.setSpacing(1)
        self.vbl_projects.setContentsMargins(2, 2, 2, 2)
        self.vbl_projects.addWidget(controls)
        self.vbl_projects.addWidget(self.user_projects)
        # self.vbl_projects.addWidget(self.new_project_header)
        self.userProjectsWidget.setLayout(self.vbl_projects)

        # User Files Widget
        self.userFilesWidget = QWidget()
        lab = QLabel('<h3>Open (Project or Zarr):</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(4, 4, 4, 4)

        w = QWidget()
        w.setContentsMargins(0, 0, 0, 0)
        hbl = QHBoxLayout()
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignRight)

        vbl.addWidget(self.filebrowser)
        self.userFilesWidget.setLayout(vbl)

        self._buttonOpen = QPushButton('Open Project')
        self._buttonOpen.setStyleSheet("font-size: 10px;")
        self._buttonOpen.clicked.connect(self.open_project_selected)
        self._buttonOpen.setFixedSize(70, 20)

        self._buttonDelete = QPushButton('Delete Project')
        self._buttonDelete.setStyleSheet("font-size: 10px;")
        self._buttonDelete.clicked.connect(self.delete_project)
        self._buttonDelete.setFixedSize(70, 20)

        self._buttonNew = QPushButton('New Project')
        self._buttonNew.setStyleSheet("font-size: 10px;")
        self._buttonNew.clicked.connect(self.new_project)
        self._buttonNew.setFixedSize(70, 20)

        # self._buttonNew = QPushButton('Remember')
        # self._buttonNew.setStyleSheet("font-size: 9px;")
        # self._buttonNew.clicked.connect(self.new_project)
        # self._buttonNew.setFixedSize(64, 20)
        # # self._buttonNew.setStyleSheet(style)

        self.selectionReadout = QLineEdit()

        self.selectionReadout.textChanged.connect(self.validate_path)
        self.selectionReadout.returnPressed.connect(self.open_project_selected)
        # self.selectionReadout.textEdited.connect(self.validateUserEnteredPath)

        self.selectionReadout.setFixedHeight(22)
        self.selectionReadout.setMinimumWidth(700)

        self.validity_label = QLabel('Invalid')
        self.validity_label.setObjectName('validity_label')
        self.validity_label.setFixedHeight(20)
        self.validity_label.hide()

        hbl = QHBoxLayout()
        hbl.setContentsMargins(6, 2, 6, 2)
        hbl.addWidget(self._buttonNew)
        hbl.addWidget(self.selectionReadout)
        hbl.addWidget(self.validity_label)
        hbl.addWidget(self._buttonOpen)
        hbl.addWidget(self._buttonDelete)
        self.spacer_item_docs = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        hbl.addSpacerItem(self.spacer_item_docs)

        self._buttonOpen.setEnabled(False)
        self._buttonDelete.setEnabled(False)

        self._actions_widget = QWidget()
        self._actions_widget.setFixedHeight(26)
        self._actions_widget.setLayout(hbl)

        self._splitter = QSplitter()
        self._splitter.setStyleSheet("""QSplitter::handle { background: none; }""")

        self._splitter.addWidget(self.userProjectsWidget)
        self._splitter.addWidget(self.userFilesWidget)
        self._splitter.setSizes([650, 350])

        self.vbl_main = VBL()
        self.vbl_main.addWidget(self._splitter)
        self.vbl_main.addWidget(self._actions_widget)
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
        # logger.info(f'caller:{inspect.stack()[1].function}')
        path = self.selectionReadout.text()
        if validate_project_selection(path) or validate_zarr_selection(path):
            self.validity_label.hide()
            self._buttonOpen.setEnabled(True)
            self._buttonDelete.setEnabled(True)
        else:
            self.validity_label.show()
            self._buttonOpen.setEnabled(False)
            self._buttonDelete.setEnabled(False)

    def userSelectionChanged(self):
        caller = inspect.stack()[1].function
        # if caller == 'setScaleData':
        #     return
        row = self.user_projects.table.currentIndex().row()
        try:
            path = self.user_projects.table.item(row, 9).text()
        except:
            path = ''
            logger.warning(f'No file path at project_table.currentIndex().row()! '
                           f'caller: {caller} - Returning...')
            return
        logger.info(f'path: {path}')
        self.selected_file = path
        self.setSelectionPathText(path)


    def new_project(self, mendenhall=False):
        logger.info('\n\nStarting A New Project...\n')
        cfg.main_window.tell('Starting A New Project...')
        self.hideMainUI()
        cfg.main_window.stopPlaybackTimer()
        cfg.main_window.tell('New Project Path:')
        self.name_dialog = QFileDialog()
        self.name_dialog.setStyleSheet("""background-color: #ede9e8; color: #141414; """)
        # self.vbl_projects.addWidget(self.name_dialog)
        self.vbl_main.addWidget(self.name_dialog)
        # self.layout.addWidget(self.name_dialog)
        self.name_dialog.setOption(QFileDialog.DontUseNativeDialog)
        self.new_project_header.setText('New Project (1/3) - Name & Location')
        self.name_dialog.setWindowTitle('New Project (1/3) - Name & Location')
        cfg.main_window.set_status('New Project (1/3) - Name & Location')
        self.name_dialog.setNameFilter("Text Files (*.swiftir)")
        self.name_dialog.setLabelText(QFileDialog.Accept, "Create")
        self.name_dialog.setViewMode(QFileDialog.Detail)
        self.name_dialog.setAcceptMode(QFileDialog.AcceptSave)
        self.name_dialog.setModal(True)
        # dialog.setOptions(dialog.DontUseNativeDialog)
        self.name_dialog.setFilter(QDir.AllEntries | QDir.Hidden)
        urls = self.name_dialog.sidebarUrls()
        if '.tacc.utexas.edu' in platform.node():
            urls.append(QUrl.fromLocalFile(os.getenv('HOME')))
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile(os.getenv('SCRATCH')))
            # urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
        else:
            urls.append(QUrl.fromLocalFile('/tmp'))
            if os.path.exists('/Volumes'):
                urls.append(QUrl.fromLocalFile('/Volumes'))
            if is_joel():
                if os.path.exists('/Volumes/3dem_data'):
                    urls.append(QUrl.fromLocalFile('/Volumes/3dem_data'))
        self.name_dialog.setSidebarUrls(urls)
        cfg.main_window.set_status('Awaiting User Input...')
        if self.name_dialog.exec() == QFileDialog.Accepted:
            logger.info('Save File Path: %s' % self.name_dialog.selectedFiles()[0])
            filename = self.name_dialog.selectedFiles()[0]
            self.name_dialog.close()
        else:
            self.showMainUI()
            self.name_dialog.close()
            return 1

        if filename in ['', None]:
            logger.info('New Project Canceled.')
            cfg.main_window.warn("New Project Canceled.")
            self.showMainUI()
            return
        if not filename.endswith('.swiftir'):
            filename += ".swiftir"
        if os.path.exists(filename):
            logger.warning("The file '%s' already exists." % filename)
            cfg.main_window.warn("The file '%s' already exists." % filename)
            path_proj = os.path.splitext(filename)[0]
            cfg.main_window.tell(f"Removing Extant Project Directory '{path_proj}'...")
            logger.info(f"Removing Extant Project Directory '{path_proj}'...")
            shutil.rmtree(path_proj, ignore_errors=True)
            cfg.main_window.tell(f"Removing Extant Project File '{path_proj}'...")
            logger.info(f"Removing Extant Project File '{path_proj}'...")
            os.remove(filename)


        path, extension = os.path.splitext(filename)
        cfg.data = DataModel(name=path, mendenhall=mendenhall)

        cfg.project_tab = ProjectTab(self, path=path, datamodel=cfg.data)
        cfg.dataById[id(cfg.project_tab)] = cfg.data

        # makedirs_exist_ok(path, exist_ok=True)

        if mendenhall:
            create_project_structure_directories(cfg.data.dest(), ['scale_1'])
        else:
            result = self.import_multiple_images()
            if result == 1:
                cfg.main_window.warn('No images were imported - canceling new project')
                self.showMainUI()
                return

            # configure_project_paths()
            # self.user_projects.set_data()

            # cfg.data.set_defaults()
            # recipe_dialog = ScaleProjectDialog(parent=self)
            self.new_project_header.setText('New Project (3/3) - Global Configuration')
            cfg.main_window.set_status('New Project (3/3) - Global Configuration')
            self.recipe_widget = NewConfigureProjectDialog(parent=self)

            self.recipe_widget.setStyleSheet("""background-color: #ede9e8; color: #141414;""")
            # self.vbl_projects.addWidget(self.recipe_widget)
            self.vbl_main.addWidget(self.recipe_widget)
            # self.layout.addWidget(self.recipe_widget)

            result = self.recipe_widget.exec()
            logger.info(f'result = {result}, type = {type(result)}')

            if result:
                logger.info('Save File Path: %s' % path)
            else:
                self.showMainUI()
                self.recipe_widget.close()
                return 1

            self.showMainUI()

            # logger.info('Showing ScaleProjectDialog...')
            # # result = recipe_dialog.exec()
            # if recipe_dialog.exec():
            #     logger.info('Continuing...')
            # else:
            #     logger.info('Returning...')
            #     return 1
            # return


            # logger.critical(f'result = {result}')
            # logger.critical(f'result = {type(result)}')
            #
            # logger.critical(f'Result: {result}; type: {type(result)}')
            # makedirs_exist_ok(path, exist_ok=True)
            initLogFiles()
            cfg.main_window._autosave(silently=True)
            cfg.main_window.autoscale()
            cfg.main_window.globTabs.addTab(cfg.project_tab, os.path.basename(path) + '.swiftir')
            cfg.main_window._setLastTab()
            cfg.main_window.onStartProject()

            # self.onStartProject(mendenhall=True)
            # turn OFF onStartProject for Mendenhall

        logger.info(f'Appending {filename} to .swift_cache...')
        userprojectspath = os.path.join(os.path.expanduser('~'), '.swift_cache')
        with open(userprojectspath, 'a') as f:
            f.write(filename + '\n')
        cfg.main_window._autosave()


    def import_multiple_images(self):
        ''' Import images into data '''
        cfg.main_window.tell('Import Images:')

        '''Dialog for importing images. Returns list of filenames.'''
        dialog = QFileDialogPreview()
        dialog.setStyleSheet("""background-color: #ede9e8; color: #141414;""")

        # self.layout.addWidget(dialog)
        # self.vbl_projects.addWidget(dialog)
        self.vbl_main.addWidget(dialog)
        # dialog.setOption(QFileDialog.DontUseNativeDialog)
        self.new_project_header.setText('New Project (2/3) - Import TIFF Images')
        cfg.main_window.set_status('New Project (2/3) - Import TIFF Images')
        dialog.setWindowTitle('New Project (2/3) - Import TIFF Images')
        dialog.setNameFilter('Images (*.tif *.tiff)')
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.setModal(True)
        urls = dialog.sidebarUrls()
        urls.append(QUrl.fromLocalFile(QDir.homePath()))
        if is_tacc():
            urls.append(QUrl.fromLocalFile(os.getenv('HOME')))
            urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
            urls.append(QUrl.fromLocalFile(os.getenv('SCRATCH')))
            # urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
        else:
            if os.path.exists('/Volumes'):
                urls.append(QUrl.fromLocalFile('/Volumes'))
            if is_joel():
                if os.path.exists('/Volumes/3dem_data'):
                    urls.append(QUrl.fromLocalFile('/Volumes/3dem_data'))

        dialog.setSidebarUrls(urls)
        cfg.main_window.set_status('Awaiting User Input...')
        logger.info('Awaiting user input...')
        if dialog.exec_() == QDialog.Accepted:
            filenames = dialog.selectedFiles()
        else:
            logger.warning('Import images dialog did not return a valid file list')
            cfg.main_window.warn('Import images dialog did not return a valid file list')
            self.showMainUI()
            return 1

        if filenames == 1:
            logger.warning('New Project Canceled')
            cfg.main_window.warn('No Project Canceled')
            self.showMainUI()
            return 1

        files_sorted = natural_sort(filenames)

        cfg.data.set_source_path(os.path.dirname(files_sorted[0])) #Critical!
        cfg.main_window.tell(f'Importing {len(files_sorted)} Images...')
        logger.info(f'Selected Images: \n{files_sorted}')

        for f in files_sorted:
            cfg.data.append_image(f)

        cfg.main_window.tell(f'Dimensions: %dx%d' % cfg.data.image_size(s='scale_1'))
        cfg.data.link_reference_sections()



    def setSelectionPathText(self, path):
        # logger.info(f'caller:{inspect.stack()[1].function}')
        self.selectionReadout.setText(path)
        logger.info('Evaluating whether path is AlignEM-SWiFT Project...')

        if validate_project_selection(path) or validate_zarr_selection(path):
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
        cfg.main_window.globTabs.addTab(tab, os.path.basename(path))
        cfg.main_window._setLastTab()

    def open_project_selected(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        cfg.main_window.stopPlaybackTimer()
        path = self.selectionReadout.text()
        if validate_zarr_selection(path):
            self.open_zarr_selected()
            return
        elif validate_project_selection(path):

            isOpen = cfg.main_window.isProjectOpen(path)
            # logger.info(f'isOpen = {isOpen}')
            # logger.info('path = %s' % path)
            if isOpen:
                cfg.main_window.globTabs.setCurrentIndex(cfg.main_window.getProjectIndex(path))
                return

            # filename = self.selected_file
            filename = self.selectionReadout.text()
            logger.info(f'Opening Project {filename}...')
            cfg.main_window.tell('Loading Project "%s"' % filename)
            try:
                with open(filename, 'r') as f:
                    cfg.data = DataModel(data=json.load(f))
                cfg.main_window._autosave()
            except:
                cfg.main_window.warn(f'No Such File Found: {filename}')
                logger.warning(f'No Such File Found: {filename}')
                print_exception()
                return
            else:
                logger.info(f'Project Opened!')
            append_project_path(filename)
            cfg.data.set_paths_absolute(filename=filename)
            cfg.project_tab = ProjectTab(self, path=cfg.data.dest() + '.swiftir', datamodel=cfg.data)
            cfg.dataById[id(cfg.project_tab)] = cfg.data
            cfg.main_window.onStartProject()
            cfg.main_window.globTabs.addTab(cfg.project_tab, os.path.basename(cfg.data.dest()) + '.swiftir')
            cfg.main_window._setLastTab()
        else:
            cfg.main_window.warn("Invalid Path")


    def delete_project(self):
        logger.info('')
        # project_file = self.selected_file
        project_file = self.selectionReadout.text()
        project = os.path.splitext(project_file)[0]
        if not validate_project_selection(project_file):
            logger.warning('Invalid Project For Deletion (!)\n%s' % project)
            return
        cfg.main_window.warn("Delete the following project?\nProject: %s" % project)
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
            cfg.main_window.tell('Canceling Delete Project Permanently Instruction...')
            logger.warning('Canceling Delete Project Permanently Instruction...')
            return
        if reply == QMessageBox.Ok:
            logger.info('Deleting Project File %s...' % project_file)
            cfg.main_window.tell('Reclaiming Disk Space. Deleting Project File %s...' % project_file)
            logger.warning('Executing Delete Project Permanently Instruction...')

        logger.info(f'Deleting Project File: {project_file}...')
        cfg.main_window.warn(f'Deleting Project File: {project_file}...')
        try:
            os.remove(project_file)
        except:
            print_exception()
        else:
            cfg.main_window.hud.done()

        logger.info('Deleting Project Directory %s...' % project)
        cfg.main_window.warn('Deleting Project Directory %s...' % project)
        try:

            delete_recursive(dir=project)
            # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
            # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
        except:
            cfg.main_window.warn('An Error Was Encountered During Deletion of the Project Directory')
            print_exception()
        else:
            cfg.main_window.hud.done()

        cfg.main_window.tell('Wrapping up...')
        configure_project_paths()
        if cfg.main_window.globTabs.currentWidget().__class__.__name__ == 'OpenProject':
            try:
                cfg.main_window.globTabs.currentWidget().user_projects.set_data()
            except:
                logger.warning('There was a problem updating the project list')
                print_exception()

        self.selectionReadout.setText('')

        cfg.main_window.tell('Deletion Complete!')
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
#             cfg.main_window._getTabObject().delete_project()
#         else:
#             super().keyPressEvent(event)

class UserProjects(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(**kwargs)
        self.parent = parent

        # self.initial_row_height = 64
        self.ROW_HEIGHT = 64

        self.counter1 = 0
        self.counter2 = 0
        # self.counter3 = 0
        self.setFocusPolicy(Qt.StrongFocus)

        self.table = QTableWidget()
        # self.table = TableWidget(self)

        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        # self.table.horizontalHeader().setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setTextElideMode(Qt.ElideMiddle)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
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

        self.table.setStyleSheet("border-radius: 12px; border-width: 3px;"
                                 "QPushButton{background-color: #ffe135;}")
        self.table.setColumnCount(10)
        self.set_headers()

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.table)
        # self.layout.addWidget(controls)
        self.setLayout(self.layout)
        self.set_data()
        self.updateRowHeight(self.ROW_HEIGHT)


    def updateRowHeight(self, h):
        for section in range(self.table.verticalHeader().count()):
            self.table.verticalHeader().resizeSection(section, h)
        self.table.setColumnWidth(1, h)
        self.table.setColumnWidth(2, h)


    # def userSelectionChanged(self):
    #     caller = inspect.stack()[1].function
    #     # if caller == 'setScaleData':
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
    #     cfg.main_window.setSelectionPathText(path)
    #     # logger.info(f'counter1={self.counter1}, counter2={self.counter2}')


    def set_headers(self):
        self.table.setHorizontalHeaderLabels([
            "Name",
            "First\nThumbnail",
            "Last\nThumbnail",
            "Created",
            "Last\nOpened",
            "#\nImgs",
            "Image\nSize (px)",
            "Disk Space\n(Bytes)",
            "Disk Space\n(Gigabytes)",
            "Location"])

        header = self.table.horizontalHeader()
        header.setFrameStyle(QFrame.Box | QFrame.Plain)
        header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
        self.table.setHorizontalHeader(header)

    def set_data(self):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        self.table.clearContents()
        # self.set_column_headers()
        self.table.setRowCount(0)
        for i, row in enumerate(self.get_data()):
            self.table.insertRow(i)
            for j, item in enumerate(row):
                if j == 0:
                    item = '<h5>' + item + '</h5>'
                    lab = QLabel('\n'.join(textwrap.wrap(item, 20)))
                    lab.setWordWrap(True)
                    self.table.setCellWidget(i, j, lab)
                elif j in (1, 2):
                    thumbnail = Thumbnail(self, path=item)
                    self.table.setCellWidget(i, j, thumbnail)
                else:
                    table_item = QTableWidgetItem(str(item))
                    font = QFont()
                    font.setPointSize(10)
                    table_item.setFont(font)
                    self.table.setItem(i, j, table_item)
        self.table.setColumnWidth(0, 128)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 40)
        self.table.setColumnWidth(6, 60)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 80)
        self.table.setColumnWidth(9, 120)
        # self.row_height_slider.setValue(self.initial_row_height)
        self.updateRowHeight(self.ROW_HEIGHT)


    def get_data(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        self.project_paths = get_project_list()
        logger.info('Getting project data...')

        projects, thumbnail_first, thumbnail_last, created, modified, \
        n_sections, img_dimensions, bytes, gigabytes, location = \
            [], [], [], [], [], [], [], [], [], []
        for p in self.project_paths:
            try:
                with open(p, 'r') as f:
                    dm = DataModel(data=json.load(f), quietly=True)
            except:
                logger.error('Table view failed to load data model: %s' % p)
            try:    created.append(dm.created)
            except: created.append('Unknown')
            try:    modified.append(dm.modified)
            except: modified.append('Unknown')
            try:    n_sections.append(len(dm))
            except: n_sections.append('Unknown')
            try:    img_dimensions.append(dm.full_scale_size())
            except: img_dimensions.append('Unknown')
            try:    projects.append(os.path.basename(p))
            except: projects.append('Unknown')
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
            thumb_path = os.path.join(project_dir, 'thumbnails')
            try:    thumbnail_first.append(list_paths_absolute(thumb_path)[0])
            except: thumbnail_first.append('No Thumbnail')
            try:    thumbnail_last.append(list_paths_absolute(thumb_path)[-1])
            except: thumbnail_last.append('No Thumbnail')
            # logger.info('Getting project location...')
            try:    location.append(p)
            except: location.append('Unknown')
        logger.info('<<<< get_data <<<<')
        return zip(projects, thumbnail_first, thumbnail_last, created, modified,
                   n_sections, img_dimensions, bytes, gigabytes, location)



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


def validate_project_selection(path) -> bool:
    # logger.info('Validating selection %s...' % cfg.selected_file)
    # called by setSelectionPathText
    path, extension = os.path.splitext(path)
    if extension != '.swiftir':
        return False
    else:
        return True

def validate_zarr_selection(path) -> bool:
    logger.info('Validating selection %s...' % cfg.selected_file)
    # called by setSelectionPathText
    if os.path.isdir(path):
        logger.info('Path IS a directory')
        if '.zarray' in os.listdir(path):
            logger.info('Directory DOES contain .zarray -> Returning True...')
            return True
    logger.info('Returning False...')
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
