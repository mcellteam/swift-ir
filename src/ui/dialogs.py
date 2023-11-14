#!/usr/bin/env python3

import faulthandler
import logging
import os
import platform
import sys
from os.path import expanduser

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

import neuroglancer as ng
import src.config as cfg
from src.utils.funcs_image import ImageSize
from src.utils.helpers import hotkey
from src.ui.layouts import HBL

logger = logging.getLogger(__name__)


class ExitSignals(QObject):
    cancelExit = Signal()
    saveExit = Signal()
    exit = Signal()
    response = Signal(int)

class ExitAppDialog(QDialog):

    def __init__(self, unsaved_changes=False):
        super().__init__()
        self.signals = ExitSignals()
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Confirm Exit")
        self.setStyleSheet("""
        QLabel{
            color: #f3f6fb;
            font-weight: 600;
        }
        /*
        QPushButton {
            color: #161c20;
            background-color: #f3f6fb;
            font-size: 9px;
            border-radius: 3px;
        }
        */
        QDialog {
                background-color: #339933;
                color: #ede9e8;
                font-size: 11px;
                font-weight: 600;
        }""")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.buttonGroup = QButtonGroup()
        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setStyleSheet("QPushButton{font-size: 9pt; font-weight: 500;}")
        self.cancelButton.setFixedSize(QSize(80,20))
        self.saveExitButton = QPushButton('Save && Quit')
        self.saveExitButton.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 500;}")
        self.saveExitButton.setFixedSize(QSize(80,20))
        self.exitExitButton = QPushButton()
        self.exitExitButton.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 500;}")
        self.buttonGroup.addButton(self.cancelButton)
        self.buttonGroup.addButton(self.saveExitButton)
        self.buttonGroup.addButton(self.exitExitButton)
        self.saveExitButton.setVisible(unsaved_changes)
        self.cancelButton.clicked.connect(self.cancelPressed)
        self.saveExitButton.clicked.connect(self.savePressed)
        self.exitExitButton.clicked.connect(self.exitPressed)

        if unsaved_changes:
            self.message = 'There are unsaved changes. Save before exiting?'
            self.exitExitButton.setText('Quit Without Saving')
            self.exitExitButton.setFixedSize(QSize(130,20))
        else:
            self.message = 'Exit Align-EM-SWiFT?'
            self.exitExitButton.setText(f"Quit {hotkey('Q')}")
            self.exitExitButton.setText(f"Quit {hotkey('Q')}")
            self.exitExitButton.setFixedSize(QSize(80,20))

        self.layout = HBL(ExpandingWidget(self), QLabel(self.message), self.cancelButton, self.saveExitButton, self.exitExitButton)
        self.layout.setSpacing(4)
        self.setContentsMargins(8,0,8,0)
        self.setLayout(self.layout)

    def cancelPressed(self):
        logger.info('')
        self.signals.response.emit(2)
        self.signals.cancelExit.emit()
        self.close()

    def savePressed(self):
        logger.info('')
        self.signals.response.emit(4)
        self.signals.saveExit.emit()
        self.close()

    def exitPressed(self):
        logger.info('')
        self.signals.response.emit(6)
        self.signals.exit.emit()
        self.close()

class SaveExitAppDialog(QDialog):
    def __init__(self):
        super().__init__()
        # self.setFixedSize(240, 100)

        # self.setWindowFlags(Qt.FramelessWindowHint)
        # self.setAutoFillBackground(False)

        self.setWindowTitle("Confirm Exit")
        self.setStyleSheet("""
            background-color: #141414;
            color: #ede9e8;
            font-size: 11px;
            font-weight: 600;
            border-color: #339933;
        """)

        btns = QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel

        self.buttonBox = QDialogButtonBox(btns)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        message = QLabel('There are unsaved changed. Save before exiting Align-EM-SWiFT?')
        self.layout.addWidget(message, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.buttonBox, alignment=Qt.AlignCenter)
        self.setLayout(self.layout)


class ImportImagesDialog(QFileDialog):
    def __init__(self, *args, **kwargs):
        QFileDialog.__init__(self, *args, **kwargs)
        logger.info('')
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setNameFilter('Images (*.tif *.tiff)')
        self.setFileMode(QFileDialog.ExistingFiles)
        self.setModal(True)
        urls = self.sidebarUrls()
        self.setSidebarUrls(urls)
        self.mpPreview = QLabel("Preview", self)
        self.mpPreview.setMinimumSize(256, 256)
        self.mpPreview.setAlignment(Qt.AlignCenter)
        self.mpPreview.setObjectName("labelPreview")
        self.mpPreview.setText('Preview')
        self.mpPreview.setAutoFillBackground(True)
        self.mpPreview.setStyleSheet("background-color: #dadada;")
        self.imageDimensionsLabel = QLabel('')
        self.imageDimensionsLabel.setMaximumHeight(16)
        self.imageDimensionsLabel.setStyleSheet("""
            font-size: 12px; 
            color: #141414; 
            padding: 2px;
        """)
        # self.cb_cal_grid = QCheckBox('Image 0 is calibration grid')
        # self.cb_cal_grid.setChecked(False)

        self.cb_display_thumbs = QCheckBox('Display Thumbnails')
        self.cb_display_thumbs.setChecked(True)
        self.cb_display_thumbs.toggled.connect(self.onToggle)

        # self.cb_overwrite = QCheckBox('Overwrite')
        # self.cb_overwrite.setChecked(False)

        self.box = QVBoxLayout()
        self.box.addWidget(self.mpPreview)
        self.box.addStretch()
        # box.addWidget(self.imageDimensionsLabel)
        self.extra_layout = QVBoxLayout()
        self.extra_layout.addWidget(self.imageDimensionsLabel, alignment=Qt.AlignRight)
        self.extra_layout.addWidget(self.cb_display_thumbs, alignment=Qt.AlignRight)
        # self.extra_layout.addWidget(self.cbCalGrid, alignment=Qt.AlignRight)
        self.layout().addLayout(self.box, 1, 3, 1, 1)
        self.layout().addLayout(self.extra_layout, 3, 3, 1, 1)
        # self.layout().addLayout(HBL(self.cb_cal_grid), 4, 0, 1, 3)
        self.layout().setContentsMargins(2,2,2,2)
        self.layout().setHorizontalSpacing(2)
        self.layout().setVerticalSpacing(0)
        self.currentChanged.connect(self.onChange)
        # self.fileSelected.connect(self.onFileSelected)
        # self.filesSelected.connect(self.onFilesSelected)
        # self._fileSelected = None
        # self._filesSelected = None
        # self.pixmap = None
        self.pixmap = QPixmap()
        # self.pixmap = ThumbnailFast(self).pixmap()
        self.setStyleSheet("font-size: 10px;")



    def onToggle(self):
        if self.cb_display_thumbs.isChecked():
            self.imageDimensionsLabel.show()
            self.mpPreview.show()
        else:
            self.imageDimensionsLabel.hide()
            self.mpPreview.hide()


    def onChange(self, path):
        # logger.info('')
        self.pixmap = QPixmap(path)
        if(self.pixmap.isNull()):
            self.imageDimensionsLabel.setText('')
        elif self.cb_display_thumbs.isChecked():
            self.mpPreview.setPixmap(self.pixmap.scaled(self.mpPreview.width(),
                                                   self.mpPreview.height(),
                                                   Qt.KeepAspectRatio,
                                                   Qt.SmoothTransformation))
            logger.info(f'Selected: {path}')
            # siz = ImageSize(path)
            # self.imageDimensionsLabel.setText('Size: %dx%dpx' %(siz[0], siz[1]))
            self.imageDimensionsLabel.setText('Size: %dx%dpx' % ImageSize(path))
            self.imageDimensionsLabel.show()


    # def onFileSelected(self, file):
    #     self._fileSelected = file
    #
    #
    # def onFilesSelected(self, files):
    #     self._filesSelected = files
    #
    #
    # def getFileSelected(self):
    #     return self._fileSelected
    #
    #
    # def getFilesSelected(self):
    #     return self._filesSelected

#
# class TestMend(QWidget):
#     def __init__(self):
#         super().__init__()
#         layout = QHBoxLayout(self)
#         self.pathEdit = QLineEdit(placeholderText='Select path...')
#         self.bBlink = QToolButton(text='...')
#         layout.addWidget(self.pathEdit)
#         layout.addWidget(self.bBlink)
#         self.bBlink.clicked.connect(self.selectTarget)
#
#     def selectTarget(self):
#         dialog = QFileDialog(self)
#
#         if self.pathEdit.text():
#             dialog.setDirectory(self.pathEdit.text())
#
#         dialog.setFileMode(dialog.Directory)
#
#         # we cannot use the native dialog, because we need control over the UI
#         options = dialog.Options(dialog.DontUseNativeDialog | dialog.ShowDirsOnly)
#         dialog.setOptions(options)
#
#         def checkLineEdit(path):
#             if not path:
#                 return
#             if path.endswith(QDir.separator()):
#                 return checkLineEdit(path.rstrip(QDir.separator()))
#             path = QFileInfo(path)
#             if path.exists() or QFileInfo(path.absolutePath()).exists():
#                 bBlink.setEnabled(True)
#                 return True
#
#         # get the "Open" bBlink in the dialog
#         bBlink = dialog.findChild(QDialogButtonBox).bBlink(QDialogButtonBox.Open)
#
#         # get the line edit used for the path
#         lineEdit = dialog.findChild(QLineEdit)
#         lineEdit.textChanged.connect(checkLineEdit)
#
#         # override the existing accept() method, otherwise selectedFiles() will
#         # complain about selecting a non existing path
#         def accept():
#             if checkLineEdit(lineEdit.text()):
#                 # if the path is acceptable, call the base accept() implementation
#                 QDialog.accept(dialog)
#         dialog.accept = accept
#
#         if dialog.exec_() and dialog.selectedFiles():
#             path = QFileInfo(dialog.selectedFiles()[0]).absoluteFilePath()
#             self.pathEdit.setText(path)

def mendenhall_dialog() -> str:
    home = expanduser("~")
    dialog = QInputDialog()
    dialog.resize(200,500)
    dialog.setInputMode(QInputDialog.TextInput)
    dialog.setWindowTitle('Create Directory')
    dialog.setLabelText('Set Microscope Sink')
    lineEdit = dialog.findChild(QLineEdit)
    lineEdit.setPlaceholderText(home)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec_():
        path = dialog.textValue()
        logger.info(f'Selected Path: {path}')
        if os.path.exists(path):
            cfg.main_window.hud.post('Path Already Exists', logging.WARNING)
            return
        else:
            try:
                os.makedirs(path, exist_ok=True)
            except:
                logger.warning(f"Unable to create path '{path}'")
                cfg.main_window.hud.post(f"Unable to create path '{path}'")
            else:
                logger.info(f"Directory Created: {path}")
                cfg.main_window.hud.post(f"Directory Created: {path}")
                return path


def export_affines_dialog() -> str:
    '''Dialog for saving a datamodel. Returns 'path'.'''
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('Export Affine Data as .csv')
    dialog.setNameFilter("Text Files (*.csv)")
    dialog.setViewMode(QFileDialog.Detail)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec() == QFileDialog.Accepted:
        cfg.main_window.hud.post('Exported: %s' % dialog.selectedFiles()[0])
        return dialog.selectedFiles()[0]


def open_project_dialog() -> str:
    '''Dialog for opening a datamodel. Returns 'path'.'''
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('* Open Project *')
    dialog.setNameFilter("Text Files (*.swiftir)")
    dialog.setViewMode(QFileDialog.Detail)
    urls = dialog.sidebarUrls()
    if '.tacc.utexas.edu' in platform.node():
        urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
        urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
    dialog.setSidebarUrls(urls)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec() == QFileDialog.Accepted:
        # self.hud.post("Loading Project '%level'" % os.path.basename(dialog.selectedFiles()[0]))
        return dialog.selectedFiles()[0]


class AskContinueDialog(QDialog):
    '''Simple dialog to ask user if they wish to proceed. Usage:
        dlg = AskContinueDialog(self)
        if dlg.exec():
            # Do if accepted
        else:
            # Do if Rejected'''
    def __init__(self, title:str, msg:str, parent=None):
        self.parent = parent
        super(AskContinueDialog, self).__init__()

        self.setWindowTitle(title)
        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout = QVBoxLayout()
        message = QLabel(msg)
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


# class RenameProject(QWidget):
#
#     def __init__(self):
#         super().__init__()
#         self.initUI()
#
#     def initUI(self):
#         self.btn = QPushButton('Dialog', self)
#         self.btn.move(20, 20)
#         self.btn.clicked.connect(self.showDialog)
#
#         self.le = QLineEdit(self)
#         self.le.move(130, 22)
#
#         self.setGeometry(300, 150, 450, 350)
#         self.setWindowTitle('Rename ProjectTab')
#         self.show()


class ConfigAppDialog(QDialog):
    def __init__(self, parent=None):  # parent=None allows passing in MainWindow if needed
        super().__init__()
        self.parent = parent
        logger.info('Showing Application Configuration Dialog:')
        self.initUI()
        cfg.main_window.set_status('Awaiting User Input...')

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        headlessWidget = QWidget()
        headlessLayout = QHBoxLayout()
        headlessLayout.setContentsMargins(4, 2, 4, 2)
        headlessWidget.setLayout(headlessLayout)
        self.headlessCheckbox = QCheckBox()
        self.headlessCheckbox.setChecked(cfg.HEADLESS)
        headlessLayout.addWidget(QLabel('Enable Neuroglancer Headless Mode: '))
        headlessLayout.addWidget(self.headlessCheckbox, alignment=Qt.AlignRight)

        ngdebugWidget = QWidget()
        ngdebugLayout = QHBoxLayout()
        ngdebugLayout.setContentsMargins(4, 2, 4, 2)
        ngdebugWidget.setLayout(ngdebugLayout)
        self.ngdebugCheckbox = QCheckBox()
        self.ngdebugCheckbox.setChecked(cfg.DEBUG_NEUROGLANCER)
        ngdebugLayout.addWidget(QLabel('Enable Neuroglancer Server Debugging: '))
        ngdebugLayout.addWidget(self.ngdebugCheckbox, alignment=Qt.AlignRight)

        mpdebugWidget = QWidget()
        mpdebugLayout = QHBoxLayout()
        mpdebugLayout.setContentsMargins(4, 2, 4, 2)
        mpdebugWidget.setLayout(mpdebugLayout)
        self.mpdebugCheckbox = QCheckBox()
        self.mpdebugCheckbox.setChecked(cfg.DEBUG_MP)
        mpdebugLayout.addWidget(QLabel('Enable Python Multiprocessing Debugging: '))
        mpdebugLayout.addWidget(self.mpdebugCheckbox, alignment=Qt.AlignRight)

        # useprofilerWidget = QWidget()
        # useprofilerLayout = QHBoxLayout()
        # useprofilerLayout.setContentsMargins(4, 2, 4, 2)
        # useprofilerWidget.setLayout(useprofilerLayout)
        # self.useprofilerCheckbox = QCheckBox()
        # self.useprofilerCheckbox.setChecked(cfg.PROFILER)
        # useprofilerLayout.addWidget(QLabel('Enable Scalene Profiler: '))
        # useprofilerLayout.addWidget(self.useprofilerCheckbox, alignment=Qt.AlignRight)

        faultWidget = QWidget()
        faultLayout = QHBoxLayout()
        faultLayout.setContentsMargins(4, 2, 4, 2)
        faultWidget.setLayout(faultLayout)
        self.faultCheckbox = QCheckBox()
        self.faultCheckbox.setChecked(cfg.FAULT_HANDLER)
        faultLayout.addWidget(QLabel('Enable Fault Handler: '))
        faultLayout.addWidget(self.faultCheckbox, alignment=Qt.AlignRight)

        cancelButton = QPushButton('Cancel')
        cancelButton.setDefault(False)
        cancelButton.setAutoDefault(False)
        cancelButton.clicked.connect(self.on_cancel)
        applyButton = QPushButton('Apply')
        applyButton.setDefault(True)
        applyButton.clicked.connect(self.on_apply)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(cancelButton)
        buttonLayout.addWidget(applyButton)
        buttonWidget = QWidget()
        buttonWidget.setLayout(buttonLayout)

        if 'CONDA_DEFAULT_ENV' in os.environ:
            environLabel = QLabel(f"Conda Environment:  {os.environ['CONDA_DEFAULT_ENV']}\n")
            layout.addWidget(environLabel)


        # layout.addWidget(tsWidget)
        layout.addWidget(headlessWidget)
        layout.addWidget(ngdebugWidget)
        layout.addWidget(mpdebugWidget)
        # layout.addWidget(useprofilerWidget)
        layout.addWidget(faultWidget)
        layout.addWidget(buttonWidget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)


    @Slot()
    def on_apply(self):
        try:
            cfg.main_window.hud('Applying Application Settings...')
            # cfg.USE_TENSORSTORE = self.tsCheckbox.isChecked()
            cfg.HEADLESS = self.headlessCheckbox.isChecked()
            cfg.DEBUG_NEUROGLANCER = int(self.ngdebugCheckbox.isChecked())
            if ng.is_server_running():
                logger.info(f'Setting Neuroglancer Server Debugging: {cfg.DEBUG_NEUROGLANCER}')
                ng.server.debug = cfg.DEBUG_NEUROGLANCER

            cfg.DEBUG_MP = int(self.mpdebugCheckbox.isChecked())
            cfg.FAULT_HANDLER = self.faultCheckbox.isChecked()
            if cfg.FAULT_HANDLER:
                if not faulthandler.is_enabled():
                    file=sys.stderr
                    all_threads=True
                    logger.info(f'Enabling faulthandler (file={file}, all_threads={all_threads})...')
                    faulthandler.enable(file=sys.stderr, all_threads=True)
            else:
                if faulthandler.is_enabled():
                    logger.info('Disabling faulthandler...')
                    faulthandler.disable()

        except Exception as e:
            logger.warning(e)
        finally:
            self.accept()

    @Slot()
    def on_cancel(self):
        logger.warning("ConfigAppDialog Exiting On 'Cancel'...")
        self.close()



def show_ng_commands():
    msgBox = QMessageBox()
    msgBox.setIcon(QMessageBox.Information)
    msgBox.setText('pop up text')
    # msgBox.setWindowTitle('title')
    # msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    msgBox.setStandardButtons(QMessageBox.Ok)
    # msgBox.buttonClicked.connect(msgButtonClick)
    # returnValue = msgBox.exec()
    # if returnValue == QMessageBox.Ok:
    #     print('OK clicked')


class DefaultsModel(QAbstractListModel):
    def __init__(self, data, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.lst = data

    # def columnCount(self, parent=QModelIndex()):
    #     return len(self.lst[0])

    def rowCount(self, parent=QModelIndex()):
        return len(self.lst)

    def data(self, index, role=Qt.DisplayRole):
        row = index.column()
        if role == Qt.EditRole:       return self.lst[row]
        elif role == Qt.DisplayRole:  return self.lst[row]

    def flags(self, index):
        flags = super(DefaultsModel, self).flags(index)

        if index.isValid():
            flags |= Qt.ItemIsEditable
            flags |= Qt.ItemIsDragEnabled
        else:
            flags = Qt.ItemIsDropEnabled

        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:  return False
        self.lst[index.row()] = value
        self.dataChanged.emit(index, index, list())
        return True


class ExpandingWidget(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
