# !/usr/bin/env python3

import os, sys, logging, pprint, textwrap
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QFileSystemModel, \
    QPushButton, QSizePolicy, QAbstractItemView, QLineEdit, QAction, QMenu, QComboBox, QTextEdit, QFormLayout, \
    QButtonGroup, QLabel, QCompleter
from qtpy.QtCore import Slot, Qt, QSize, QDir
from qtpy.QtGui import QCursor
import qtawesome as qta
from src.helpers import is_joel, is_tacc, sanitizeSavedPaths
from src.ui.layouts import HWidget, VWidget, VBL, HBL, HSplitter, VSplitter
import src.config as cfg

__all__ = ['FileBrowser']

logger = logging.getLogger(__name__)


class FileBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.treeview = QTreeView()
        self.treeview.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeview.customContextMenuRequested.connect(self.openMenu)
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

        # sanitizeSavedPaths()
        self.loadPathCombo()

    # def _show_context_menu(self, position):
    #     display_action1 = QAction("Display Selection")
    #     display_action1.triggered.connect(self.display_selection)
    #     menu = QMenu(self.tree_widget)
    #     menu.addAction(display_action1)
    #
    #     menu.exec_(self.tree_widget.mapToGlobal(position))

    def openMenu(self, position):
        logger.info('')
        indexes = self.treeview.selectedIndexes()
        logger.info(f"len(indexes) = {len(indexes)}")
        if len(indexes) > 0:
            level = 0
            index = indexes[0]
            while index.parent().isValid():
                index = index.parent()
                level += 1

        logger.info(f"menu level = {level}")

        menu = QMenu()
        if level == 0:
            menu.addAction(self.tr("Edit person"))
        elif level == 1:
            menu.addAction(self.tr("Edit object/container"))
        elif level == 2:
            menu.addAction(self.tr("Edit object"))
        menu.exec_(self.treeview.viewport().mapToGlobal(position))

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

    def setRootSeries(self):
        try:
            self.treeview.setRootIndex(self.fileSystemModel.index(cfg.settings['series_root']))
        except:
            logger.warning('Directory cannot be accessed')

    def setRootAlignments(self):
        try:
            self.treeview.setRootIndex(self.fileSystemModel.index(cfg.settings['alignments_root']))
        except:
            logger.warning('Directory cannot be accessed')

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

        self.bSetRootSeries = QPushButton('Series Root')
        self.bSetRootSeries.setStyleSheet('font-size: 9px;')
        self.bSetRootSeries.setFixedHeight(16)
        self.bSetRootSeries.clicked.connect(self.setRootSeries)

        self.bSetRootAlignments = QPushButton('Alignments Root')
        self.bSetRootAlignments.setStyleSheet('font-size: 9px;')
        self.bSetRootAlignments.setFixedHeight(16)
        self.bSetRootAlignments.clicked.connect(self.setRootAlignments)

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

        self.bSetContentSources = QPushButton('Configure Content Sources')
        self.bSetContentSources.setFixedHeight(16)
        def fn():
            self.wContentRoot.setVisible(not self.wContentRoot.isVisible())
            if self.wContentRoot.isVisible():
                self.leNewSeries.setText(cfg.settings['series_root'])
                self.leNewAlignments.setText(cfg.settings['alignments_root'])
                self.teSeriesSearchPaths.setText('\n'.join(cfg.settings['series_search_paths']))
                self.teAlignmentsSearchPaths.setText('\n'.join(cfg.settings['alignments_search_paths']))
        self.bSetContentSources.clicked.connect(fn)

        self.btns0 = HWidget(self.bSetRootSeries, self.bSetRootAlignments)
        self.btns0.setFixedHeight(16)

        self.btns1 = HWidget(self.bSetRootTmp, self.bSetRootRoot, self.bSetRootHome)
        self.btns1.setFixedHeight(16)

        if is_joel():
            if os.path.exists(self.path_special):
                self.btns1.addWidget(self.bSetRootSpecial)

        self.vwButtons = VWidget()
        self.vwButtons.addWidget(self.btns1)
        self.vwButtons.addWidget(self.btns0)
        self.vwButtons.layout.setSpacing(2)

        if is_tacc():
            self.btns2 = HWidget()
            self.btns2.addWidget(self.bSetRootScratch)
            self.btns2.addWidget(self.bSetRootWork)
            self.btns2.addWidget(self.buttonSetRoot_corral_root)
            self.vwButtons.addWidget(self.btns2)

        self.vwButtons.addWidget(self.bSetContentSources)

        self.combobox = QComboBox()
        self.combobox.setFixedHeight(16)
        self.combobox.setEditable(True)
        self.combobox.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.combobox.setCursor(QCursor(Qt.PointingHandCursor))
        # self.combobox.currentTextChanged.connect(self.onComboChanged)
        self.combobox.activated.connect(self.onComboChanged)

        self.lePath = QLineEdit()
        self.lePath.setFixedHeight(16)
        self.lePath.setReadOnly(False)
        self.lePath.setPlaceholderText('<path>')
        self.lePath.returnPressed.connect(lambda: self.navigateTo(self.lePath.text()))
        self.lePath.textChanged.connect(self.onPathChanged)
        self.bGo = QPushButton('Go')
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

        tip = "Location where new series will be created."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.leNewSeries = QLineEdit()
        self.leNewSeries.setFixedHeight(16)
        self.leNewSeries.setReadOnly(False)
        lab = BoldLabel('Series Root:')
        self.wNewSeries = VWidget(lab, self.leNewSeries)
        self.wNewSeries.layout.setAlignment(Qt.AlignVCenter)
        self.wNewSeries.setToolTip(tip)

        tip = "Location where new alignments will be created."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.leNewAlignments = QLineEdit()
        self.leNewAlignments.setFixedHeight(16)
        self.leNewAlignments.setReadOnly(False)
        lab = BoldLabel('Alignments Root:')
        self.wNewAlignments = VWidget(lab, self.leNewAlignments)
        self.wNewAlignments.layout.setAlignment(Qt.AlignVCenter)
        self.wNewAlignments.setToolTip(tip)

        tip = "List of filesystem locations to search for series."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.teSeriesSearchPaths = QTextEdit()
        self.teSeriesSearchPaths.setMinimumHeight(80)
        self.teSeriesSearchPaths.setReadOnly(False)
        lab = BoldLabel('Series Search Paths (Recursive):')
        self.wSeriesSearchPaths = VWidget(lab, self.teSeriesSearchPaths)
        self.wSeriesSearchPaths.setMaximumHeight(80)
        self.wSeriesSearchPaths.layout.setAlignment(Qt.AlignVCenter)
        self.wSeriesSearchPaths.setToolTip(tip)

        tip = "List of filesystem locations to search for alignments."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.teAlignmentsSearchPaths = QTextEdit()
        self.teAlignmentsSearchPaths.setMinimumHeight(70)
        self.teAlignmentsSearchPaths.setReadOnly(False)
        lab = BoldLabel('Alignments Search Paths (Recursive):')
        self.wAlignmentsSearchPaths = VWidget(lab, self.teAlignmentsSearchPaths)
        self.wAlignmentsSearchPaths.setMaximumHeight(80)
        self.wAlignmentsSearchPaths.layout.setAlignment(Qt.AlignVCenter)
        self.wAlignmentsSearchPaths.setToolTip(tip)

        self.bCancel = QPushButton()
        # self.bCancel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.bCancel = QPushButton('Cancel')
        self.bCancel.setFixedHeight(16)
        self.bCancel.setIconSize(QSize(14, 14))
        self.bCancel.setIcon(qta.icon('ri.close-fill', color='#161c20'))
        self.bCancel.clicked.connect(lambda: self.wContentRoot.hide())
        self.bSave = QPushButton()
        # self.bSave.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.bSave = QPushButton('Save')
        self.bSave.setFixedHeight(16)
        self.bSave.setIconSize(QSize(14, 14))
        self.bSave.setIcon(qta.icon('fa.check', color='#161c20'))
        self.bSave.clicked.connect(self.onSaveContentSources)
        self.bgSources = QButtonGroup()
        self.bgSources.addButton(self.bCancel)
        self.bgSources.addButton(self.bSave)
        # self.wCloseSaveButtons = HWidget(self.bSave, self.bCancel, ExpandingHWidget(self))
        self.wCloseSaveButtons = HWidget(self.bSave, self.bCancel)
        self.wCloseSaveButtons.setFixedHeight(20)

        self.flContentRoot = QFormLayout()
        self.flContentRoot.setContentsMargins(0, 0, 0, 0)
        self.flContentRoot.setSpacing(2)
        # self.flContentRoot.addRow('New Series\nLocation', self.leNewSeries)
        # self.flContentRoot.addRow('Series\nSearch Paths', self.teSeriesSearchPaths)
        # self.flContentRoot.addRow('New Alignments\nLocation', self.leNewAlignments)
        # self.flContentRoot.addRow('Alignments\nSearch Paths', self.teAlignmentsSearchPaths)
        self.flContentRoot.addWidget(self.wNewSeries)
        self.flContentRoot.addWidget(self.wSeriesSearchPaths)
        self.flContentRoot.addWidget(self.wNewAlignments)
        self.flContentRoot.addWidget(self.wAlignmentsSearchPaths)
        self.flContentRoot.addWidget(self.wCloseSaveButtons)

        self.wContentRoot = QWidget()
        self.wContentRoot.setAutoFillBackground(True)
        self.wContentRoot.setLayout(self.flContentRoot)
        self.wContentRoot.hide()

        lab = BoldLabel('Saved Locations:')
        self.comboWidget = VWidget(lab, HWidget(self.combobox, self.bMinus))
        self.comboWidget.layout.setAlignment(Qt.AlignVCenter)

        self.leWidget = HWidget(self.lePath, self.bGo, self.bPlus)
        lab = BoldLabel('Folder...')
        self.wJumpTo = VWidget(lab, self.leWidget)
        # self.wJumpTo.setFixedHeight(18)

        self.vw1 = VWidget(self.treeview)

        # self.vsplitter = VSplitter(self.vw1, self.wContentRoot, self.vw2)
        # self.vsplitter = VSplitter()

        vbl = VBL(self.treeview, self.comboWidget, self.wJumpTo, self.vwButtons, self.wContentRoot)
        vbl.setSpacing(2)
        self.setLayout(vbl)
        self.setStyleSheet("font-size: 9px;")

        # self.setLayout(VBL(self.vsplitter))



        self.setStyleSheet('font-size: 9px;')

    def onSaveContentSources(self):
        logger.info(f'Saving search paths and content roots...')
        d = {
            'series_root': self.leNewSeries.text(),
            'series_search_paths': self.teSeriesSearchPaths.toPlainText().split('\n'),
            'alignments_root': self.leNewAlignments.text(),
            'alignments_search_paths': self.teAlignmentsSearchPaths.toPlainText().split('\n'),
        }
        cfg.settings.update(d)
        pprint.pprint(d)
        p = cfg.settings['series_root']
        if not os.path.exists(p):
            cfg.mw.tell(f"Creating series directory {p}")
            os.makedirs(p, exist_ok=True)

        p = cfg.settings['alignments_root']
        if not os.path.exists(p):
            cfg.mw.tell(f"Creating alignments directory {p}")
            os.makedirs(p, exist_ok=True)

        for path in cfg.settings['series_search_paths']:
            if not os.path.isdir(path):
                cfg.mw.warn(f"'{path}' is not a directory and will be ignored. ")

        for path in cfg.settings['alignments_search_paths']:
            if not os.path.isdir(path):
                cfg.mw.warn(f"'{path}' is not a directory and will be ignored. ")

        cfg.mw.saveUserPreferences(silent=True)
        self.wContentRoot.hide()
        cfg.mw.statusBar.showMessage('Preferences saved!', 3000)

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

        self.combobox.clear()

        # for path in paths:
        #     aslist = os.path.normpath(path).split(os.sep)
        # self.combobox.addItems([])

        self.combobox.addItems(cfg.settings['saved_paths'])
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


class BoldLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("font-size: 8px; font-weight: 600;")
        self.setAlignment(Qt.AlignLeft)


class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = FileBrowser()
    main.show()
    sys.exit(app.exec_())
