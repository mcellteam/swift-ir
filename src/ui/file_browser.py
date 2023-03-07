# !/usr/bin/env python3

import os, sys, logging
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QFileSystemModel, \
    QPushButton, QSizePolicy, QAbstractItemView
from qtpy.QtCore import Slot, Qt, QSize, QDir
from src.helpers import is_joel, is_tacc
import src.config as cfg

__all__ = ['FileBrowser']

logger = logging.getLogger(__name__)


class FileBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.treeview = QTreeView()
        self.treeview.setStyleSheet('border-width: 0px;')
        self.treeview.expandsOnDoubleClick()
        self.treeview.setAnimated(True)
        self.treeview.setAlternatingRowColors(True)
        self.treeview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fileSystemModel = QFileSystemModel(self.treeview)
        self.fileSystemModel.setReadOnly(False)
        self.fileSystemModel.setFilter(QDir.AllEntries | QDir.Hidden)
        self.treeview.setModel(self.fileSystemModel)
        # root = self.fileSystemModel.setRootPath(os.path.expanduser('~'))
        root = self.fileSystemModel.setRootPath('/')
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


    def initUI(self):
        with open('src/style/controls.qss', 'r') as f:
            style = f.read()

        self._btn_showFileBrowser = QPushButton('Hide Files')
        self._btn_showFileBrowser.setFixedSize(86, 18)
        self._btn_showFileBrowser.setStyleSheet(style)
        self._btn_showFileBrowser.hide()
        self._btn_showFileBrowser.clicked.connect(self._showHideFb)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 2, 4, 2)
        hbl.addWidget(self._btn_showFileBrowser, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addStretch()
        self.controls = QWidget()
        self.controls.setFixedHeight(24)
        self.controls.setLayout(hbl)
        self.controls.hide()

        self.buttonSetRootRoot = QPushButton('Root')
        self.buttonSetRootRoot.setFixedSize(64, 20)
        self.buttonSetRootRoot.clicked.connect(self.setRootRoot)

        self.buttonSetRootHome = QPushButton('Home')
        self.buttonSetRootHome.setFixedSize(64, 20)
        self.buttonSetRootHome.clicked.connect(self.setRootHome)

        self.buttonSetRootWork = QPushButton('Work')
        self.buttonSetRootWork.setFixedSize(64, 20)
        self.buttonSetRootWork.clicked.connect(self.setRootWork)

        self.buttonSetRootScratch = QPushButton('Scratch')
        self.buttonSetRootScratch.setFixedSize(64, 20)
        self.buttonSetRootScratch.clicked.connect(self.setRootScratch)

        self.buttonSetRootSpecial = QPushButton('SanDisk')
        self.buttonSetRootSpecial.setFixedSize(64, 20)
        self.buttonSetRootSpecial.clicked.connect(self.setRootSpecial)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        if not is_tacc(): hbl.addWidget(self.buttonSetRootRoot)
        hbl.addWidget(self.buttonSetRootHome)

        if self.path_work: hbl.addWidget(self.buttonSetRootWork)
        if self.path_scratch: hbl.addWidget(self.buttonSetRootScratch)
        if is_joel():
            if os.path.exists(self.path_special):
                hbl.addWidget(self.buttonSetRootSpecial)

        self.controlsNavigation = QWidget()
        self.controlsNavigation.setFixedHeight(24)
        self.controlsNavigation.setLayout(hbl)
        self.controlsNavigation.hide()

        vbl = QVBoxLayout(self)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.treeview)
        vbl.addWidget(self.controls, alignment=Qt.AlignmentFlag.AlignLeft)
        vbl.addWidget(self.controlsNavigation, alignment=Qt.AlignmentFlag.AlignLeft)
        # vbl.setStretch(1,0)
        self.setLayout(vbl)

    # def selectionChanged(self):
    #     cfg.selected_file = self.getSelectionPath()
    #     logger.info(f'Project Selection Changed! {cfg.selected_file}')
    #     # cfg.tab.setSelectionPathText(cfg.selected_file)

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
