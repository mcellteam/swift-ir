# !/usr/bin/env python3

import os, sys, logging
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QFileSystemModel, \
    QPushButton, QSizePolicy, QAbstractItemView, QLineEdit, QAction, QMenu, QComboBox, QTextEdit, QFormLayout, \
    QButtonGroup, QLabel, QCompleter
from qtpy.QtCore import Slot, Qt, QSize, QDir
from qtpy.QtGui import QCursor
import qtawesome as qta
from src.helpers import is_joel, is_tacc, sanitizeSavedPaths
from src.ui.layouts import HWidget, VWidget, VBL, HBL
import src.config as cfg

__all__ = ['FileBrowser']

logger = logging.getLogger(__name__)


class FileBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.treeview = cfg.treeview = QTreeView()
        # self.treeview.customContextMenuRequested.connect(self._show_context_menu)
        self.treeview.setStyleSheet('border-width: 0px; color: #161c20;')
        self.treeview.expandsOnDoubleClick()
        self.treeview.setAnimated(True)
        self.treeview.setAlternatingRowColors(True)
        self.treeview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fileSystemModel = QFileSystemModel(self.treeview)
        self.fileSystemModel.setReadOnly(False)
        self.fileSystemModel.setFilter(QDir.AllEntries | QDir.Hidden)
        # self.fileSystemModel.setFilter(QDir.Files)
        # self.fileSystemModel.setFilter(QDir.NoDotAndDotDot)
        self.treeview.setModel(self.fileSystemModel)
        root = self.fileSystemModel.setRootPath(os.path.expanduser('~'))
        # root = self.fileSystemModel.setRootPath('/')

        self.treeview.setRootIndex(root)


        self.path_scratch = os.getenv('SCRATCH', "SCRATCH not found")
        self.path_work = os.getenv('WORK', "WORK not found")
        self.path_special = '/Volumes/3dem_data'

        self.treeview.setColumnWidth(0, 400)
        self.initUI()
        self.treeview.selectionModel().selectionChanged.connect(self.selectionChanged)

        self.treeview.setColumnWidth(0,150)
        self.treeview.setColumnWidth(1,50)
        self.treeview.setColumnWidth(2,50)

        sanitizeSavedPaths()
        self.loadPathCombo()

    # def _show_context_menu(self, position):
    #     display_action1 = QAction("Display Selection")
    #     display_action1.triggered.connect(self.display_selection)
    #     menu = QMenu(self.tree_widget)
    #     menu.addAction(display_action1)
    #
    #     menu.exec_(self.tree_widget.mapToGlobal(position))

    def setRootHome(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(os.path.expanduser('~')))
        except: logger.warning('Directory cannot be accessed')

    def setRootRoot(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index('/'))
        except: logger.warning('Directory cannot be accessed')

    def setRootTmp(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index('/tmp'))
        except: logger.warning('Directory cannot be accessed')

    def setRootWork(self):
        try:   self.treeview.setRootIndex(self.fileSystemModel.index(self.path_work))
        except: logger.warning('Directory cannot be accessed')

    def setRootScratch(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(self.path_scratch))
        except: logger.warning('Directory cannot be accessed')

    def setRootSpecial(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(self.path_special))
        except: logger.warning('Directory cannot be accessed')

    def setRootCR(self):
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(cfg.settings['content_root']))
        except: logger.warning('Directory cannot be accessed')

    def setRoot_corral_projects(self):
        corral_projects_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(corral_projects_dir))
        except: logger.warning('Directory cannot be accessed')

    def setRoot_corral_images(self):
        corral_images_dir = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/EM_Series'
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(corral_images_dir))
        except: logger.warning('Directory cannot be accessed')

    def set_corral_root(self):
        dir = '/corral-repl'
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(dir))
        except: logger.warning('Directory cannot be accessed')





    def initUI(self):
        # with open('src/style/controls.qss', 'r') as f:
        #     style = f.read()

        self.bSetRootRoot = QPushButton('/ (Root)')
        self.bSetRootRoot.setStyleSheet('font-size: 9px;')
        self.bSetRootRoot.setFixedHeight(16)
        self.bSetRootRoot.clicked.connect(self.setRootRoot)

        self.bSetRootTmp = QPushButton('/tmp')
        self.bSetRootTmp.setStyleSheet('font-size: 9px;')
        self.bSetRootTmp.setFixedHeight(16)
        self.bSetRootTmp.clicked.connect(self.setRootTmp)

        self.bSetRootHome = QPushButton('~ (Home)')
        self.bSetRootHome.setStyleSheet('font-size: 9px;')
        self.bSetRootHome.setFixedHeight(16)
        self.bSetRootHome.clicked.connect(self.setRootHome)

        self.bSetRootWork = QPushButton('Work')
        self.bSetRootWork.setStyleSheet('font-size: 9px;')
        self.bSetRootWork.setFixedHeight(16)
        self.bSetRootWork.clicked.connect(self.setRootWork)

        self.bSetRootScratch = QPushButton('Scratch')
        self.bSetRootScratch.setStyleSheet('font-size: 9px;')
        self.bSetRootScratch.setFixedHeight(16)
        self.bSetRootScratch.clicked.connect(self.setRootScratch)

        self.bSetRootSpecial = QPushButton('SanDisk')
        self.bSetRootSpecial.setStyleSheet('font-size: 9px;')
        self.bSetRootSpecial.setFixedHeight(16)
        self.bSetRootSpecial.clicked.connect(self.setRootSpecial)

        self.bSetRootCR = QPushButton('Content Root')
        self.bSetRootCR.setStyleSheet('font-size: 9px;')
        self.bSetRootCR.setFixedHeight(16)
        self.bSetRootCR.clicked.connect(self.setRootCR)

        if is_tacc():
            self.buttonSetRoot_corral_projects = QPushButton('Projects_AlignEM')
            self.buttonSetRoot_corral_projects.setStyleSheet('font-size: 9px;')
            # self.buttonSetRoot_corral_projects.setFixedSize(QSize(90,16))
            self.buttonSetRoot_corral_projects.setFixedHeight(16)
            self.buttonSetRoot_corral_projects.clicked.connect(self.setRoot_corral_projects)

            self.buttonSetRoot_corral_images = QPushButton('EM_Series')
            self.buttonSetRoot_corral_images.setStyleSheet('font-size: 9px;')
            # self.buttonSetRoot_corral_images.setFixedSize(QSize(90,16))
            self.buttonSetRoot_corral_images.setFixedHeight(16)
            self.buttonSetRoot_corral_images.clicked.connect(self.setRoot_corral_images)

            self.buttonSetRoot_corral_root = QPushButton('Corral')
            self.buttonSetRoot_corral_root.setStyleSheet('font-size: 9px;')
            # self.buttonSetRoot_corral_root.setFixedSize(QSize(90,16))
            self.buttonSetRoot_corral_root.setFixedHeight(16)
            self.buttonSetRoot_corral_root.clicked.connect(self.set_corral_root)

        hw1 = HWidget()
        hw1.layout.setSpacing(2)
        hw1.addWidget(self.bSetRootTmp)
        hw1.addWidget(self.bSetRootRoot)
        hw1.addWidget(self.bSetRootHome)
        if is_joel():
            if os.path.exists(self.path_special):
                hw1.addWidget(self.bSetRootSpecial)

        hw2 = HWidget()
        hw2.layout.setSpacing(2)
        if is_tacc():
            hw2.addWidget(self.bSetRootScratch)
            hw2.addWidget(self.bSetRootWork)
            # hw2.addWidget(self.buttonSetRoot_corral_images)
            # hw2.addWidget(self.buttonSetRoot_corral_projects)
            hw2.addWidget(self.buttonSetRoot_corral_root)

        self.wTreeviewButtons = VWidget(hw1, hw2)

        self.combobox = QComboBox()
        self.combobox.setEditable(True)
        self.combobox.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.combobox.setCursor(QCursor(Qt.PointingHandCursor))
        self.combobox.setStyleSheet('font-size: 9px;')
        self.combobox.setFixedHeight(16)
        # self.combobox.currentTextChanged.connect(self.onComboChanged)
        self.combobox.activated.connect(self.onComboChanged)

        self.lePath = QLineEdit()
        self.lePath.setFixedHeight(18)
        self.lePath.setReadOnly(False)
        self.lePath.setStyleSheet('font-size: 9px;')
        self.lePath.setPlaceholderText('<path>')
        self.lePath.returnPressed.connect(lambda: self.navigateTo(self.lePath.text()))
        self.lePath.textChanged.connect(self.onPathChanged)
        self.bGo = QPushButton('Go')
        self.bGo.setStyleSheet('font-size: 9px;')
        self.bGo.setFixedSize(QSize(24, 16))
        def fn_bGo():
            logger.info('')
            cur = self.lePath.text()
            if os.path.exists(cur):
                self.navigateTo(cur)
            else:
                logger.warning(f"path not found: {cur}")
        self.bGo.clicked.connect(fn_bGo)
        self.bGo.setEnabled(False)

        self.bPlus = QPushButton()
        self.bPlus.setFixedSize(QSize(16, 16))
        self.bPlus.setIconSize(QSize(12, 12))
        self.bPlus.clicked.connect(self.onPlus)
        self.bPlus.setIcon(qta.icon('fa.plus', color='#161c20'))

        self.bMinus = QPushButton()
        self.bMinus.setFixedSize(QSize(16, 16))
        self.bMinus.setIconSize(QSize(12, 12))
        self.bMinus.clicked.connect(self.onMinus)
        self.bMinus.setIcon(qta.icon('fa.minus', color='#161c20'))

        self.bSetContentSources = QPushButton('Set Content Sources')
        self.bSetContentSources.setFixedHeight(16)
        def fn():
            self.w_teContentSources.setVisible(not self.w_teContentSources.isVisible())
            if self.w_teContentSources.isVisible():
                self.leContentRoot.setText(cfg.settings['content_root'])
                self.teSearchPaths.setText('\n'.join(cfg.settings['search_paths']))
        self.bSetContentSources.clicked.connect(fn)

        self.leContentRoot = QLineEdit()
        self.leContentRoot.setFixedHeight(18)
        self.leContentRoot.setReadOnly(False)

        self.teSearchPaths = QTextEdit()
        # self.teSearchPaths.setMaximumHeight(100)
        self.teSearchPaths.setReadOnly(False)
        # self.teSearchPaths.setMaximumHeight(140)
        # self.teSearchPaths.setMinimumHeight(40)

        self.bSaveCancelSources = QPushButton('Cancel')
        self.bSaveCancelSources.setFixedSize(QSize(60,18))
        self.bSaveCancelSources.setIconSize(QSize(12,12))
        self.bSaveCancelSources.clicked.connect(lambda: self.w_teContentSources.hide())

        self.bSaveContentSources = QPushButton('Save')
        self.bSaveContentSources.setFixedSize(QSize(60,18))
        def fn():
            logger.info(f'Saving search paths and content roots...')
            cfg.settings['search_paths'] = self.teSearchPaths.toPlainText().split('\n')
            cfg.settings['content_root'] = self.leContentRoot.text()
            p = cfg.settings['content_root']
            if not os.path.exists(p):
                cfg.mw.tell(f"Creating directory content root {p}"); os.makedirs(p, exist_ok=True)
            p = os.path.join(cfg.settings['content_root'], 'series')
            if not os.path.exists(p):
                cfg.mw.tell(f"Creating series directory {p}"); os.makedirs(p, exist_ok=True)
            p = os.path.join(cfg.settings['content_root'], 'alignments')
            if not os.path.exists(p):
                cfg.mw.tell(f"Creating alignments directory {p}"); os.makedirs(p, exist_ok=True)
            cfg.mw.saveUserPreferences(silent=True)
            self.w_teContentSources.hide()
            cfg.mw.statusBar.showMessage('Content roots saved!', 3000)
        self.bSaveContentSources.clicked.connect(fn)

        self.bgSources = QButtonGroup()
        self.bgSources.addButton(self.bSaveCancelSources)
        self.bgSources.addButton(self.bSaveContentSources)

        self.w_teContentSources = QWidget()
        self.w_teContentSources.setAutoFillBackground(True)
        self.flContentAndSearch = QFormLayout()
        self.flContentAndSearch.setContentsMargins(2,2,2,2)
        self.flContentAndSearch.setSpacing(2)
        self.flContentAndSearch.addRow('Content Root', self.leContentRoot)
        self.flContentAndSearch.addRow('Search Paths', self.teSearchPaths)
        self.flContentAndSearch.addWidget(HWidget(self.bSaveContentSources, self.bSaveCancelSources,
                                                  ExpandingHWidget(self)))
        # self.w_teContentSources.setMaximumHeight(140)
        self.w_teContentSources.setLayout(self.flContentAndSearch)
        self.w_teContentSources.setMinimumHeight(50)
        self.w_teContentSources.setMaximumHeight(150)
        self.w_teContentSources.hide()

        self.labSavedLocations = QLabel('Saved Locations:')
        self.labSavedLocations.setAlignment(Qt.AlignLeft)
        self.labSavedLocations.setStyleSheet("""color: #161c20; font-size: 8px; font-weight: 600;""")

        self.labJumpTo = QLabel('Jump To:')
        self.labJumpTo.setAlignment(Qt.AlignLeft)
        self.labJumpTo.setStyleSheet("""color: #161c20; font-size: 8px; font-weight: 600;""")

        self.comboWidget = HWidget(self.combobox, self.bMinus)
        self.leWidget = HWidget(self.lePath, self.bGo, self.bPlus)

        self.wCS = HWidget(self.bSetRootCR, self.bSetContentSources)

        vbl = VBL(self.treeview, self.labSavedLocations, self.comboWidget, self.labJumpTo, self.leWidget,
                  self.w_teContentSources,
                  self.wCS, self.wTreeviewButtons)
        vbl.setSpacing(0)
        self.setLayout(vbl)


    def onComboChanged(self):
        logger.info('')
        cur = self.combobox.currentText()
        if os.path.exists(cur):
            self.navigateTo(cur)
        else:
            logger.warning(f"path not found: {cur}")

    def onPathChanged(self):
        # requested = self.lePath.text()
        # self.bGo.setEnabled((self.combobox.count() > 0) and
        #                     (self.getSelectionPath() != self.combobox.currentText()))
        cur = self.lePath.text()
        self.bGo.setEnabled(os.path.exists(cur))
        self.bPlus.setEnabled(os.path.exists(cur) and cur not in cfg.settings['saved_paths'])



    def selectionChanged(self):
        requested = self.getSelectionPath()
        logger.info(f'Selection changed! {requested}')
        self.lePath.setText(requested)
        # self.bPlus.setEnabled((self.getSelectionPath() not in cfg.settings['saved_paths']) and os.path.isdir(requested))



    def onPathCombo(self):
        requested = self.combobox.currentText()
        self.lePath.setText(requested)
        self.navigateTo(requested)
        self.bPlus.setEnabled((self.getSelectionPath() not in cfg.settings['saved_paths']) and os.path.isdir(requested))


    def loadPathCombo(self):
        paths = cfg.settings['saved_paths']
        self.combobox.clear()

        # for path in paths:
        #     aslist = os.path.normpath(path).split(os.sep)
        # self.combobox.addItems([])

        self.combobox.addItems(paths)
        self.bMinus.setEnabled(self.combobox.count() > 0)
        self.bGo.setEnabled((self.combobox.count() > 0) and
                            (self.getSelectionPath() != self.combobox.currentText()))



    def onMinus(self):
        requested = self.combobox.currentText()
        if requested:
            logger.info(f"Removing path: {self.getSelectionPath()}")
            try:
                cfg.settings['saved_paths'].remove(requested)
            except:
                logger.warning(f"Nothing to remove!")
            cfg.mw.saveUserPreferences(silent=True)
            self.loadPathCombo()

    def onPlus(self):
        requested = self.lePath.text()
        if requested:
            if os.path.exists(requested) and os.path.isdir(requested):
                if requested not in cfg.settings['saved_paths']:
                    cfg.mw.tell(f"Adding path: {requested}")
                    cfg.settings['saved_paths'].append(requested)
                else:
                    cfg.mw.warn(f"Path is already saved! {requested}")
            else:
                cfg.mw.warn(f"Path is not a directory! {requested}")
            cfg.mw.saveUserPreferences(silent=True)
            self.loadPathCombo()
        else:
            cfg.mw.warn(f"Nothing selected.")


    def navigateTo(self, path):
        logger.info(f'Navigating to: {path}')
        try:    self.treeview.setRootIndex(self.fileSystemModel.index(path))
        except: cfg.main_window.warn('Directory cannot be accessed')

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


    # def sizeHint(self):
    #     return QSize(400,200)


class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = FileBrowser()
    main.show()
    sys.exit(app.exec_())
