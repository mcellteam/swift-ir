# !/usr/bin/env python3

import os, sys, logging
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QFileSystemModel, \
    QPushButton, QSizePolicy, QAbstractItemView, QLineEdit
from qtpy.QtCore import Slot, Qt, QSize, QDir
from src.helpers import is_joel, is_tacc
from src.ui.layouts import HWidget, VWidget
import src.config as cfg

__all__ = ['FileBrowser']

logger = logging.getLogger(__name__)


class FileBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.treeview = cfg.treeview = QTreeView()
        self.treeview.setStyleSheet('border-width: 0px;')
        self.treeview.expandsOnDoubleClick()
        self.treeview.setAnimated(True)
        self.treeview.setAlternatingRowColors(True)
        self.treeview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fileSystemModel = QFileSystemModel(self.treeview)
        self.fileSystemModel.setReadOnly(False)
        self.fileSystemModel.setFilter(QDir.AllEntries | QDir.Hidden)
        self.treeview.setModel(self.fileSystemModel)
        root = self.fileSystemModel.setRootPath(os.path.expanduser('~'))
        # root = self.fileSystemModel.setRootPath('/Users/joelyancey/glanceem_swift/test_images')
        # root = self.fileSystemModel.setRootPath('/')
        self.treeview.setRootIndex(root)

        self.path_scratch = os.getenv('SCRATCH')
        self.path_work = os.getenv('WORK')
        self.path_special = '/Volumes/3dem_data'

        self.treeview.setColumnWidth(0, 600)
        self.initUI()
        # self.treeview.selectionModel().selectionChanged.connect(self.selectionChanged)

    def setRootHome(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(os.path.expanduser('~')))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def setRootRoot(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index('/'))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def setRootWork(self):
        try:   self.treeview.setRootIndex(self.fileSystemModel.index(self.path_work))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def setRootScratch(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(self.path_scratch))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def setRootSpecial(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(self.path_special))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def setRoot_corral_projects(self):
        corral_projects_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(corral_projects_dir))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def setRoot_corral_images(self):
        corral_images_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/EM_Series'
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(corral_images_dir))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def set_corral_root(self):
        dir = '/corral-repl'
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(dir))
        except: cfg.main_window.warn('Directory cannot be accessed')


    def initUI(self):
        with open('src/style/controls.qss', 'r') as f:
            style = f.read()

        self._btn_showFileBrowser = QPushButton('Hide Files')
        self._btn_showFileBrowser.setFixedSize(86, 18)
        self._btn_showFileBrowser.setStyleSheet(style)
        self._btn_showFileBrowser.hide()
        self._btn_showFileBrowser.clicked.connect(self._showHideFb)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(2,2,2,2)
        hbl.addWidget(self._btn_showFileBrowser, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addStretch()
        self.controls = QWidget()
        self.controls.setFixedHeight(18)
        self.controls.setLayout(hbl)
        self.controls.hide()

        button_size = QSize(54, 16)

        # with open('src/style/buttonstyle.qss', 'r') as f:
        #     button_gradient_style = f.read()

        self.buttonSetRootRoot = QPushButton('Root')
        # self.buttonSetRootRoot.setStyleSheet(button_gradient_style)
        self.buttonSetRootRoot.setStyleSheet('font-size: 9px;')
        self.buttonSetRootRoot.setFixedSize(button_size)
        self.buttonSetRootRoot.clicked.connect(self.setRootRoot)

        self.buttonSetRootHome = QPushButton('Home')
        # self.buttonSetRootHome.setStyleSheet(button_gradient_style)
        self.buttonSetRootHome.setStyleSheet('font-size: 9px;')
        self.buttonSetRootHome.setFixedSize(button_size)
        self.buttonSetRootHome.clicked.connect(self.setRootHome)

        self.buttonSetRootWork = QPushButton('Work')
        # self.buttonSetRootWork.setStyleSheet(button_gradient_style)
        self.buttonSetRootWork.setStyleSheet('font-size: 9px;')
        self.buttonSetRootWork.setFixedSize(button_size)
        self.buttonSetRootWork.clicked.connect(self.setRootWork)

        self.buttonSetRootScratch = QPushButton('Scratch')
        # self.buttonSetRootScratch.setStyleSheet(button_gradient_style)
        self.buttonSetRootScratch.setStyleSheet('font-size: 9px;')
        self.buttonSetRootScratch.setFixedSize(button_size)
        self.buttonSetRootScratch.clicked.connect(self.setRootScratch)

        self.buttonSetRootSpecial = QPushButton('SanDisk')
        # self.buttonSetRootSpecial.setStyleSheet(button_gradient_style)
        self.buttonSetRootSpecial.setStyleSheet('font-size: 9px;')
        self.buttonSetRootSpecial.setFixedSize(button_size)
        self.buttonSetRootSpecial.clicked.connect(self.setRootSpecial)


        if is_tacc():
            self.buttonSetRoot_corral_projects = QPushButton('Projects_AlignEM')
            self.buttonSetRoot_corral_projects.setStyleSheet('font-size: 9px;')
            self.buttonSetRoot_corral_projects.setFixedSize(QSize(90,16))
            self.buttonSetRoot_corral_projects.clicked.connect(self.setRoot_corral_projects)

            self.buttonSetRoot_corral_images = QPushButton('EM_Series')
            self.buttonSetRoot_corral_images.setStyleSheet('font-size: 9px;')
            self.buttonSetRoot_corral_images.setFixedSize(QSize(90,16))
            self.buttonSetRoot_corral_images.clicked.connect(self.setRoot_corral_images)

            self.buttonSetRoot_corral_root = QPushButton('Corral')
            self.buttonSetRoot_corral_root.setStyleSheet('font-size: 9px;')
            self.buttonSetRoot_corral_root.setFixedSize(QSize(90,16))
            self.buttonSetRoot_corral_root.clicked.connect(self.set_corral_root)

        self.buttonCreateProject = QPushButton('Create Project')
        self.buttonCreateProject.setStyleSheet('font-size: 9px;')
        self.buttonCreateProject.setFixedSize(QSize(100, 16))
        self.buttonCreateProject.clicked.connect(self.createProjectFromFolder)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(2,2,2,2)
        if not is_tacc():
            hbl.addWidget(self.buttonSetRootRoot)
        if not is_tacc():
            hbl.addWidget(self.buttonSetRootHome)
        if self.path_scratch:
            hbl.addWidget(self.buttonSetRootScratch)
        if self.path_work:
            hbl.addWidget(self.buttonSetRootWork)
        if is_tacc():
            hbl.addWidget(self.buttonSetRoot_corral_images)
            hbl.addWidget(self.buttonSetRoot_corral_projects)
            hbl.addWidget(self.buttonSetRoot_corral_root)



        if is_joel():
            if os.path.exists(self.path_special):
                hbl.addWidget(self.buttonSetRootSpecial)

        self.controlsNavigation = QWidget()
        self.controlsNavigation.setFixedHeight(18)
        self.controlsNavigation.setLayout(hbl)
        self.controlsNavigation.hide()

        self.le_navigate_to = QLineEdit()
        self.le_navigate_to.setStyleSheet('font-size: 8px;')
        self.le_navigate_to.setFixedHeight(20)
        self.le_navigate_to.setReadOnly(False)
        # if is_tacc():
        #     self.le_navigate_to.setPlaceholderText('/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/EM_Series')
        # else:
        #     self.le_navigate_to.setPlaceholderText(os.path.expanduser('~'))
        self.le_navigate_to.setPlaceholderText('<enter path>')

        self.btn_go = QPushButton('Go')
        self.btn_go.setStyleSheet('font-size: 9px;')
        self.btn_go.setFixedSize(QSize(36,16))
        self.btn_go.clicked.connect(lambda: self.navigateTo(self.le_navigate_to.text()))

        self.nav_widget = HWidget(self.le_navigate_to, self.btn_go)
        self.nav_widget.layout.setContentsMargins(2,2,2,2)
        self.nav_widget.layout.setSpacing(4)
        self.nav_widget.setFixedHeight(22)

        vbl = QVBoxLayout(self)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.treeview)
        vbl.addWidget(self.nav_widget)
        vbl.addWidget(self.controlsNavigation, alignment=Qt.AlignmentFlag.AlignLeft)
        vbl.addWidget(self.controls, alignment=Qt.AlignmentFlag.AlignLeft)
        self.setLayout(vbl)

    # def selectionChanged(self):
    #     cfg.selected_file = self.getSelectionPath()
    #     logger.info(f'Project Selection Changed! {cfg.selected_file}')
    #     # cfg.tab.setSelectionPathText(cfg.selected_file)


    def navigateTo(self, path):
        logger.info(f'Navigating to: {path}')
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(path))
        except: cfg.main_window.warn('Directory cannot be accessed')
        pass


    def createProjectFromFolder(self):
        pass

    def showSelection(self):
        logger.info('showSelection:')
        try:
            selection = self.fileSystemModel.itemData(self.treeview.selectedIndexes()[0])
            logger.info(selection)
        except:
            logger.warning('Is Any File Selected?')

    def getSelection(self):
        try:
            selection = self.fileSystemModel.itemData(self.treeview.selectedIndexes()[0])
            return selection
        except:
            logger.warning('Is Any File Selected?')

    def getSelectionPath(self):
        try:
            index = self.treeview.selectedIndexes()[0]
            info = self.treeview.model().fileInfo(index)
            path = info.absoluteFilePath()
            print(f'getSelectionPath: {path}')
            return path
        except:
            logger.warning('No Path Selected.')



    def _showHideFb(self):
        if self.treeview.isHidden():
            self.treeview.show()
            self._btn_showFileBrowser.setText('Hide Files')
        else:
            self.treeview.hide()
            self._btn_showFileBrowser.setText('File Browser')

    # def sizeHint(self):
    #     return QSize(400,200)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = FileBrowser()
    main.show()
    sys.exit(app.exec_())
