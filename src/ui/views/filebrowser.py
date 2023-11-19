# !/usr/bin/env python3

import logging
import os
import pprint
import subprocess as sp
import sys
import textwrap

import qtawesome as qta
from qtpy.QtCore import Qt, QSize, QDir
from qtpy.QtWidgets import QApplication, QWidget, QTreeView, QFileSystemModel, \
    QPushButton, QSizePolicy, QAbstractItemView, QLineEdit, QAction, QMenu, QComboBox, QTextEdit, QButtonGroup, QLabel, \
    QMessageBox

import src.config as cfg
from src.utils.helpers import is_tacc, print_exception
from src.ui.layouts.layouts import HW, VW, VBL

__all__ = ['FileBrowser']

logger = logging.getLogger(__name__)


class FileBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.selection = None
        self.treeview = QTreeView()
        self.treeview.expanded.connect(self.onExpanded)
        self.treeview.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeview.customContextMenuRequested.connect(self.openMenu)
        # self.treeview.customContextMenuRequested.connect(self._show_context_menu)
        self.treeview.expandsOnDoubleClick()
        self.treeview.setAnimated(True)
        self.treeview.setAlternatingRowColors(True)
        self.treeview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.treeview.setSortingEnabled(True)
        self.treeview.header().setSortIndicator(0, Qt.AscendingOrder)
        self.model = QFileSystemModel(self.treeview)
        self.model.directoryLoaded.connect(lambda path: print(f"directoryLoaded: {path}!"))
        self.model.rootPathChanged.connect(lambda newpath: print(f"rootPathChanged: {newpath}!"))
        self.model.setReadOnly(False)
        self.model.setFilter(QDir.AllEntries | QDir.Hidden)
        self.model.sort(0, Qt.SortOrder.AscendingOrder)
        # self.model.setFilter(QDir.Files)
        # self.model.setFilter(QDir.NoDotAndDotDot)
        self.treeview.setModel(self.model)
        # self._root = os.file_path.expanduser('~')
        # self.model.setRootPath(self._root)
        root = self.model.setRootPath('/')
        self.treeview.setRootIndex(root)

        self.path_scratch = os.getenv('SCRATCH', "SCRATCH not found")
        self.path_work = os.getenv('WORK', "WORK not found")
        self.path_special = '/Volumes/3dem_data'

        self.initUI()
        self.treeview.selectionModel().selectionChanged.connect(self.selectionChanged)
        self.treeview.setColumnWidth(0,110)
        self.treeview.setColumnWidth(1,50)
        self.treeview.setColumnWidth(2,50)
        self.treeview.setColumnWidth(3,70)

        # sanitizeSavedPaths()
        self.loadCombobox()

        # self.setRootLastKnownRoot()

    def navigateUp(self):
        logger.info('')
        if hasattr(self, '_root'):
            logger.debug(f'current root: {self._root}')
            # selection = self.getSelectionPath()
            self._root = os.path.dirname(self._root)
            logger.debug(f"Setting root: {self._root}")
            self.treeview.setRootIndex(self.model.index(self._root))
            cfg.mw.tell(f'Root directory set to {self._root}')

    def navigateDown(self):
        logger.info('')
        if hasattr(self, '_root'):
            selection = self.getSelectionPath()
            if selection:
                self._root = selection
                logger.debug(f"Setting root: {self._root}")
                self.treeview.setRootIndex(self.model.index(self._root))
                cfg.mw.tell(f'Root directory set to {self._root}')
            else:
                logger.warning("No directory selected!")



    def onExpanded(self, index):
        logger.debug(f'Expanded! {index}')

    # def _show_context_menu(self, position):
    #     display_action1 = QAction("Display Selection")
    #     display_action1.triggered.connect(self.display_selection)
    #     menu = QMenu(self.tree_widget)
    #     menu.addAction(display_action1)
    #
    #     menu.exec_(self.tree_widget.mapToGlobal(position))

    def openMenu(self, position):
        logger.debug('')
        indexes = self.treeview.selectedIndexes()
        if len(indexes) > 0:
            level = 0
            index = indexes[0]
            while index.parent().isValid():
                index = index.parent()
                level += 1

        selected = self.getSelectionPath()

        menu = QMenu()

        action = QAction()
        action.setText(f"Save {selected} to My Locations")
        def fn():
            if selected not in cfg.preferences['saved_paths']:
                cfg.preferences['saved_paths'].append(selected)

        action.triggered.connect(fn)
        menu.addAction(action)

        fn,ext = os.path.splitext(selected)
        if ext == '.align':
            action = QAction()
            action.setText(f"Open Alignment {selected}")
            action.triggered.connect(lambda: cfg.pm.openAlignment(selected))
            menu.addAction(action)

        if ext in ('.alignment', '.images', '.align', '.emstack'):
            action = QAction()
            action.setText(f"Delete {selected}")
            action.triggered.connect(self.onDelete)
            menu.addAction(action)


        # if level == 0:
        #     menu.addAction(self.tr("Edit person"))
        # elif level == 1:
        #     menu.addAction(self.tr("Edit object/container"))
        # elif level == 2:
        #     menu.addAction(self.tr("Edit object"))
        menu.exec_(self.treeview.viewport().mapToGlobal(position))

    def setRootLastKnownRoot(self):
        self._root = cfg.preferences['current_filebrowser_root']
        logger.critical(f'Setting filebrowser root to {self._root}')
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:
            if hasattr(cfg, 'mw') and cfg.mw:
                cfg.mw.tell(f'Root directory set to {self._root}')
            else:
                logger.info(f'Root directory set to {self._root}')

    def setRootHome(self):
        self._root = os.path.expanduser('~')
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootRoot(self):
        self._root = '/'
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootTmp(self):
        self._root = '/tmp'
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootWork(self):
        self._root = self.path_work
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootScratch(self):
        self._root = self.path_scratch
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootSpecial(self):
        self._root = self.path_special
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootSeries(self):
        self._root = cfg.preferences['images_root']
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRootAlignments(self):
        self._root = cfg.preferences['alignments_root']
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def setRoot_corral_projects(self):
        self._root = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/Projects_AlignEM'
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')


    def setRoot_corral_images(self):
        self._root = '/corral-repl/projects/NeuroNex-3DEM/projects/3dem-1076/EM_Series'
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')

    def set_corral_root(self):
        self._root = '/corral-repl'
        try:    self.treeview.setRootIndex(self.model.index(self._root))
        except: logger.warning('Directory cannot be accessed')
        else:   cfg.mw.tell(f'Root directory set to {self._root}')


    def initUI(self):

        self.bNavigateUp = QPushButton()
        self.bNavigateUp.setToolTip("Go up one level")
        # self.bNavigateUp.setIcon(qta.icon('fa.arrow-up'))
        self.bNavigateUp.setIcon(qta.icon('fa5s.angle-up'))
        self.bNavigateUp.clicked.connect(self.navigateUp)

        self.bNavigateDown = QPushButton()
        self.bNavigateDown.setToolTip("Go down one level")
        # self.bNavigateDown.setIcon(qta.icon('fa.arrow-down'))
        self.bNavigateDown.setIcon(qta.icon('fa5s.angle-down'))
        self.bNavigateDown.clicked.connect(self.navigateDown)

        self.bSlash = QPushButton()
        self.bSlash.setToolTip("Go to system root")
        self.bSlash.setIcon(qta.icon('mdi.slash-forward'))
        self.bSlash.clicked.connect(self.setRootRoot)

        self.bHome = QPushButton()
        self.bHome.setToolTip("Go to home directory")
        self.bHome.setIcon(qta.icon('fa.home'))
        self.bHome.clicked.connect(self.setRootHome)

        self.bPlus = QPushButton()
        self.bPlus.setToolTip("Add file_path to saved locations")
        self.bPlus.clicked.connect(self.onPlus)
        self.bPlus.setIcon(qta.icon('fa.plus'))

        self.bMinus = QPushButton()
        self.bMinus.setToolTip("Remove file_path from saved locations")
        self.bMinus.clicked.connect(self.onMinus)
        self.bMinus.setIcon(qta.icon('fa.minus'))

        # self.bSetRootTmp = QPushButton('/tmp')
        # self.bSetRootTmp.clicked.connect(self.setRootTmp)
        # self.bSetRootTmp.setToolTip("Go to /tmp directory")

        navbuttons = [self.bNavigateUp, self.bNavigateDown, self.bSlash, self.bHome, self.bPlus, self.bMinus]
        for b in navbuttons:
            # b.setFixedSize(QSize(16, 16))
            b.setFixedHeight(14)
            b.setIconSize(QSize(14, 14))

        self.bSetRootSpecial = QPushButton('SanDisk')
        self.bSetRootSpecial.setFixedHeight(12)
        self.bSetRootSpecial.clicked.connect(self.setRootSpecial)

        # self.bSetRootSeries = QPushButton('Images Root')
        # self.bSetRootSeries.setFixedHeight(16)
        # self.bSetRootSeries.clicked.connect(self.setRootSeries)
        #
        # self.bSetRootAlignments = QPushButton('Alignments Root')
        # self.bSetRootAlignments.setFixedHeight(16)
        # self.bSetRootAlignments.clicked.connect(self.setRootAlignments)

        if is_tacc():
            self.buttonSetRoot_corral_projects = QPushButton('Projects_AlignEM')
            self.buttonSetRoot_corral_projects.setFixedHeight(14)
            self.buttonSetRoot_corral_projects.clicked.connect(self.setRoot_corral_projects)

            # self.buttonSetRoot_corral_images = QPushButton('EM_Series')
            # self.buttonSetRoot_corral_images.setFixedHeight(14)
            # self.buttonSetRoot_corral_images.clicked.connect(self.setRoot_corral_images)

            self.buttonSetRoot_corral_root = QPushButton('Corral')
            self.buttonSetRoot_corral_root.setFixedHeight(14)
            self.buttonSetRoot_corral_root.clicked.connect(self.set_corral_root)

        self.bSetContentSources = QPushButton('Set Content Sources')
        self.bSetContentSources.setFixedHeight(16)
        def fn():
            self.setVisibilityContentSourcesCpanel(not self.wContentRoot.isVisible())

            if self.wContentRoot.isVisible():
                self.leNewSeries.setText(cfg.preferences['images_root'])
                self.leNewAlignments.setText(cfg.preferences['alignments_root'])
                self.teSeriesSearchPaths.setText('\n'.join(cfg.preferences['images_search_paths']))
                self.teAlignmentsSearchPaths.setText('\n'.join(cfg.preferences['alignments_search_paths']))
        self.bSetContentSources.clicked.connect(fn)

        self.combobox = QComboBox()
        # self.combobox.setPlaceholderText("Select images_path...")
        self.combobox.setToolTip("Saved Locations")
        # self.combobox.setEditable(True)
        # self.combobox.completer().setCompletionMode(QCompleter.PopupCompletion)
        # self.combobox.setCursor(QCursor(Qt.PointingHandCursor))
        # self.combobox.currentTextChanged.connect(self.onComboChanged)
        self.combobox.activated.connect(self.onComboChanged)

        self.lePath = QLineEdit()
        self.lePath.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lePath.setFixedHeight(16)
        self.lePath.setReadOnly(False)
        self.lePath.setPlaceholderText('Go to...')
        self.lePath.returnPressed.connect(lambda: self.navigateTo(self.lePath.text()))
        self.lePath.textEdited.connect(self.onPathChanged)

        self.bGo = QPushButton()
        self.bGo.setIcon(qta.icon('mdi.arrow-right'))
        self.bGo.setFixedSize(QSize(16, 16))
        self.bGo.setIconSize(QSize(13, 13))
        def fn_bGo():
            logger.info('')
            cur = self.lePath.text()
            if os.path.exists(cur):
                self.navigateTo(cur)
            else:
                logger.warning(f"file_path not found: {cur}")
        self.bGo.clicked.connect(fn_bGo)
        self.bGo.setEnabled(False)

        self.wPath = HW(self.lePath, self.bGo)
        self.wPath.setFixedHeight(16)

        tip = "Location where new images will be created."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.leNewSeries = QLineEdit()
        self.leNewSeries.setFixedHeight(16)
        self.leNewSeries.setReadOnly(False)
        lab = BoldLabel('Images Root:')
        lab.setAlignment(Qt.AlignBottom)
        self.wNewSeries = VW(lab, self.leNewSeries)
        self.wNewSeries.layout.setAlignment(Qt.AlignVCenter)
        self.wNewSeries.setToolTip(tip)

        tip = "Location where new alignments will be created."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.leNewAlignments = QLineEdit()
        self.leNewAlignments.setFixedHeight(16)
        self.leNewAlignments.setReadOnly(False)
        lab = BoldLabel('Alignments Root:')
        lab.setAlignment(Qt.AlignBottom)
        self.wNewAlignments = VW(lab, self.leNewAlignments)
        self.wNewAlignments.layout.setAlignment(Qt.AlignVCenter)
        self.wNewAlignments.setToolTip(tip)

        tip = "List of filesystem locations to search for images."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.teSeriesSearchPaths = QTextEdit()
        self.teSeriesSearchPaths.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.teSeriesSearchPaths.setMinimumHeight(40)
        # self.teSeriesSearchPaths.setMaximumHeight(80)
        self.teSeriesSearchPaths.setReadOnly(False)
        lab = BoldLabel('Images (.emstack) Search Paths:')
        lab.setAlignment(Qt.AlignBottom)
        self.wSeriesSearchPaths = VW(lab, self.teSeriesSearchPaths)
        self.wSeriesSearchPaths.setToolTip(tip)

        tip = "List of filesystem locations to search for alignments."
        tip = '\n'.join(textwrap.wrap(tip, width=35))
        self.teAlignmentsSearchPaths = QTextEdit()
        self.teAlignmentsSearchPaths.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.teAlignmentsSearchPaths.setMinimumHeight(40)
        # self.teAlignmentsSearchPaths.setMaximumHeight(80)
        self.teAlignmentsSearchPaths.setReadOnly(False)
        # lab = BoldLabel('Alignments Search Paths (Recursive):')
        lab = BoldLabel('Alignments (.align) Search Paths:')
        lab.setAlignment(Qt.AlignBottom)
        self.wAlignmentsSearchPaths = VW(lab, self.teAlignmentsSearchPaths)
        self.wAlignmentsSearchPaths.setToolTip(tip)

        self.bCancel = QPushButton()
        self.bCancel.setFixedHeight(16)
        self.bCancel.setIconSize(QSize(14, 14))
        self.bCancel.setIcon(qta.icon('ri.close-fill'))
        self.bCancel.clicked.connect(lambda: self.setVisibilityContentSourcesCpanel(False))

        self.bSave = QPushButton()
        self.bSave.setFixedHeight(16)
        self.bSave.setIconSize(QSize(14, 14))
        self.bSave.setIcon(qta.icon('fa.check'))
        self.bSave.clicked.connect(self.onSaveContentSources)

        self.bgSources = QButtonGroup()
        self.bgSources.addButton(self.bCancel)
        self.bgSources.addButton(self.bSave)
        self.wCloseSaveButtons = HW(self.bSave, self.bCancel)
        self.wCloseSaveButtons.setFixedHeight(20)

        self.wContentRoot = VW(self.wNewSeries, self.wSeriesSearchPaths, self.wNewAlignments, self.wAlignmentsSearchPaths, self.wCloseSaveButtons)
        self.wContentRoot.layout.setSpacing(6)
        self.wContentRoot.hide()

        self.wNavButtons = HW(self.bNavigateUp, self.bNavigateDown, self.bSlash, self.bHome, self.bPlus, self.bMinus, ExpandingHWidget(self))
        self.wNavButtons.setStyleSheet("""border: none;""")
        self.wNavButtons.setFixedHeight(16)
        self.wNavButtons.layout.setSpacing(0)

        # self.treetop = VW(self.combobox, self.vwButtons, self.wNavButtons)
        self.treetop = VW(self.combobox, self.wNavButtons)
        # self.treetop.setStyleSheet("""font-size: 9px;""")

        vbl = VBL(self.treetop, self.treeview, self.wPath, self.bSetContentSources, self.wContentRoot)
        vbl.setSpacing(1)
        # vbl.setSpacing(2)
        self.setLayout(vbl)

        # f = QFont()
        # f.setPixelSize(9)
        # self.setFont(f)

    def onSaveContentSources(self):
        logger.info(f'Saving search paths and content roots...')
        try:
            d = {
                'images_root': self.leNewSeries.text(),
                'images_search_paths': self.teSeriesSearchPaths.toPlainText().split('\n'),
                'alignments_root': self.leNewAlignments.text(),
                'alignments_search_paths': self.teAlignmentsSearchPaths.toPlainText().split('\n'),
            }
            cfg.preferences.update(d)
            pprint.pprint(d)
            p = cfg.preferences['images_root']
            if not os.path.exists(p):
                cfg.mw.tell(f"Creating images directory {p}")
                os.makedirs(p, exist_ok=True)

            p = cfg.preferences['alignments_root']
            if not os.path.exists(p):
                cfg.mw.tell(f"Creating alignments directory {p}")
                os.makedirs(p, exist_ok=True)

            for path in cfg.preferences['images_search_paths']:
                if not os.path.isdir(path):
                    cfg.mw.warn(f"'{path}' is not a directory and will be ignored. ")

            for path in cfg.preferences['alignments_search_paths']:
                if not os.path.isdir(path):
                    cfg.mw.warn(f"'{path}' is not a directory and will be ignored. ")

            cfg.mw.saveUserPreferences(silent=True)
            self.parent._updateWatchPaths()
            self.wContentRoot.hide()
            cfg.mw.statusBar.showMessage('Preferences saved!', 3000)
        except:
            print_exception()
        finally:
            self.setVisibilityContentSourcesCpanel(False)

    def onComboChanged(self):
        logger.info('')
        cur = self.combobox.currentText()
        try:
            if cur == 'Saved locations...':
                return
            elif cur == 'New Images Root':
                self.setRootSeries()
            elif cur == 'New Alignments Root':
                self.setRootAlignments()
            elif cur == '$SCRATCH':
                self.setRootScratch()
            elif cur == '$WORK':
                self.setRootWork()
            elif cur == 'Corral':
                self.setRoot_corral_projects()
            elif os.path.exists(cur):
                self.navigateTo(cur)
            else:
                logger.warning(f"file_path not found: {cur}")
        except:
            print_exception()


    def onPathChanged(self):
        logger.info('')
        self.selection = cur = self.lePath.text()
        self.bGo.setEnabled(os.path.exists(cur) and (cur != self._root))
        self.bPlus.setEnabled(os.path.exists(cur) and cur not in cfg.preferences['saved_paths'])


    def selectionChanged(self):
        requested = self.getSelectionPath()
        logger.info(f'Selection changed! {requested}')
        self.lePath.setText(requested)
        # self.bPlus.setEnabled((self.getSelectionPath() not in cfg.preferences['saved_paths']) and os.file_path.isdir(requested))


    def onPathCombo(self):
        requested = self.combobox.currentText()
        self.lePath.setText(requested)
        self.navigateTo(requested)
        self.bPlus.setEnabled((self.getSelectionPath() not in cfg.preferences['saved_paths']) and os.path.isdir(requested))


    def loadCombobox(self):

        self.combobox.clear()

        # for file_path in paths:
        #     aslist = os.file_path.normpath(file_path).split(os.sep)
        # self.combobox.addItems([])

        items = ['Saved locations...', 'Images Root', 'Alignments Root']

        #Critical
        if hasattr(cfg,'preferences'):
            if cfg.preferences['saved_paths']:
                items.extend(cfg.preferences['saved_paths'])

        if is_tacc():
            items.extend(['$SCRATCH', '$WORK', 'Corral'])

        self.combobox.addItems(items)
        self.bMinus.setEnabled(self.combobox.count() > 0)
        # self.bGo.setEnabled((self.combobox.count() > 0) and
        #                     (self.getSelectionPath() != self.combobox.currentText()))
        cur = self.lePath.text()
        self.bGo.setEnabled(os.path.exists(cur) and (cur != self._root))


    def onMinus(self):
        requested = self.combobox.currentText()
        if requested:
            logger.info(f"Removing file_path: {self.getSelectionPath()}")
            try:
                cfg.preferences['saved_paths'].remove(requested)
            except:
                logger.warning(f"Nothing to remove!")
            cfg.mw.saveUserPreferences(silent=True)
            self.loadCombobox()

    def onPlus(self):
        requested = self.lePath.text()
        if requested:
            if os.path.exists(requested) and os.path.isdir(requested):
                if requested not in cfg.preferences['saved_paths']:
                    cfg.mw.tell(f"Adding file_path: {requested}")
                    cfg.preferences['saved_paths'].append(requested)
                else:
                    cfg.mw.warn(f"Path is already saved! {requested}")
            else:
                cfg.mw.warn(f"Path is not a directory! {requested}")
            cfg.mw.saveUserPreferences(silent=True)
            self.loadCombobox()
        else:
            cfg.mw.warn(f"Select a valid location.")

    def onDelete(self):
        selection = self.getSelectionPath()

        cfg.mw.tell("Delete %s?" % selection)
        txt = "Are you sure you want to PERMANENTLY DELETE %s?" % selection
        msgbox = QMessageBox(QMessageBox.Warning,'Confirm Delete Project',
                             txt,
                             buttons=QMessageBox.Cancel | QMessageBox.Yes
                             )
        msgbox.setIcon(QMessageBox.Critical)
        msgbox.setMaximumWidth(350)
        msgbox.setDefaultButton(QMessageBox.Cancel)
        reply = msgbox.exec_()
        if reply == QMessageBox.Cancel:
            cfg.mw.tell('Canceling delete...')
            return
        if reply == QMessageBox.Ok:
            logger.info('Attempting to delete %s...' % selection)

        try:
            run_subprocess(["rm", "-rf", selection])
            # delete_recursive(dir=project)
            # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
            # shutil.rmtree(project, ignore_errors=True, onerror=handleError)
        except:
            cfg.mw.warn('An Error Was Encountered During Deletion of the Project Directory')
            print_exception()
        else:
            cfg.mw.hud.done()


    def navigateTo(self, path):
        logger.info(f'Navigating to: {path}')
        try:    self.treeview.setRootIndex(self.model.index(path))
        except: cfg.main_window.warn('Directory cannot be accessed')

    def createProjectFromFolder(self):
        pass

    def showSelection(self):
        logger.info('showSelection:')
        try:
            selection = self.model.itemData(self.treeview.selectedIndexes()[0])
            logger.info(selection)
        except:
            logger.warning('Is Any File Selected?')

    def getSelection(self):
        try:
            selection = self.model.itemData(self.treeview.selectedIndexes()[0])
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

    def setVisibilityContentSourcesCpanel(self, state):
        self.wContentRoot.setVisible(state)
        self.treetop.setVisible(not state)
        self.treeview.setVisible(not state)
        self.wPath.setVisible(not state)
        self.bSetContentSources.setVisible(not state)


    # def sizeHint(self):
    #     return QSize(400,200)


class BoldLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("font-size: 8px; font-weight: 600;")
        self.setAlignment(Qt.AlignLeft)
        # self.setFixedHeight(8)


class ExpandingHWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


def run_subprocess(task):
    """Call run(), catch exceptions."""
    try:
        sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
    except Exception as e:
        print("error: %s run(*%r)" % (e, task))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main = FileBrowser()
    main.show()
    sys.exit(app.exec_())
