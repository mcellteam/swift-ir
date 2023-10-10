#!/usr/bin/env python3

import os, sys, logging, textwrap, platform
from os.path import expanduser
from pathlib import Path
import faulthandler
import neuroglancer as ng
import qtawesome as qta

from qtpy.QtWidgets import QWidget, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, \
    QLineEdit, QVBoxLayout, QCheckBox, QTabWidget, QMessageBox, QFileDialog, QInputDialog, QPushButton, QToolButton, \
    QColorDialog, QWidgetAction, QMenu, QToolButton, QSizePolicy, QDial, QFormLayout, QGroupBox, QButtonGroup, \
    QStyle, QSpinBox, QListView, QStyledItemDelegate
from qtpy.QtCore import Qt, Slot, QAbstractListModel, QModelIndex, QUrl, QDir, QFileInfo, Signal, QSize, QObject, \
    QUrl
from qtpy.QtGui import QDoubleValidator, QFont, QIntValidator, QPixmap, QColor, QIcon
import src.config as cfg
from src.helpers import get_scale_val, do_scales_exist, is_joel, is_tacc, hotkey
from src.funcs_image import ImageSize
from src.ui.layouts import VBL, HBL, VW, HW
from src.ui.thumbnail import ThumbnailFast

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
        self.cb_cal_grid = QCheckBox('Image 0 is calibration grid')
        self.cb_cal_grid.setChecked(False)

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
        # self.extra_layout.addWidget(self.cb_cal_grid, alignment=Qt.AlignRight)
        self.layout().addLayout(self.box, 1, 3, 1, 1)
        self.layout().addLayout(self.extra_layout, 3, 3, 1, 1)
        self.layout().addLayout(HBL(self.cb_cal_grid), 4, 0, 1, 3)
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

        # tsWidget = QWidget()
        # tsLayout = QHBoxLayout()
        # tsLayout.setContentsMargins(4, 2, 4, 2)
        # tsWidget.setLayout(tsLayout)
        # self.tsCheckbox = QCheckBox()
        # self.tsCheckbox.setChecked(cfg.USE_TENSORSTORE)
        # tsLayout.addWidget(QLabel('Enable Tensorstore Backend: '))
        # tsLayout.addWidget(self.tsCheckbox, alignment=Qt.AlignRight)

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



class NewConfigureProjectDialog(QDialog):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        logger.info('')
        self.parent = parent
        self.setModal(True)
        # self.setWindowFlags(Qt.Widget)
        self.initUI()


    def on_cancel(self):
        self.reject()
        self.close()
        return 1


    def onScaleAndAlign(self):
        self.on_apply()

    def on_apply(self):

        try:
            cfg.main_window.hud('Applying Project Settings...')

            cfg.data.set_clobber(self.cb_clobber.isChecked(), glob=True)
            cfg.data.set_clobber_px(self.sb_clobber_pixels.value(), glob=True)

            # cfg.data.set_scales_from_string(self.scales_input.text()) #Deprecated
            cfg.data.set_use_bounding_rect(self.bounding_rectangle_checkbox.isChecked())
            cfg.data['defaults'][cfg.data.scale]['initial_rotation'] = float(self.initial_rotation_input.text())
            cfg.data['data']['clevel'] = int(self.clevel_input.text())
            cfg.data['data']['cname'] = self.cname_combobox.currentText()
            cfg.data['data']['chunkshape'] = (int(self.chunk_z_lineedit.text()),
                                              int(self.chunk_y_lineedit.text()),
                                              int(self.chunk_x_lineedit.text()))


            # if cfg.data['data']['has_cal_grid']:

            for scale in cfg.data.scales:
                scale_val = get_scale_val(scale)
                res_x = int(self.res_x_lineedit.text()) * scale_val
                res_y = int(self.res_y_lineedit.text()) * scale_val
                res_z = int(self.res_z_lineedit.text())
                cfg.data.set_resolution(s=scale, res_x=res_x, res_y=res_y, res_z=res_z)
        except Exception as e:
            logger.warning(e)
        finally:
            self.accept()
            return 0

    def scale_only(self):

        try:
            cfg.main_window.hud('Applying Project Settings...')

            cfg.data.set_clobber(self.cb_clobber.isChecked(), glob=True)
            cfg.data.set_clobber_px(self.sb_clobber_pixels.value(), glob=True)

            # cfg.data.set_scales_from_string(self.scales_input.text()) #Deprecated
            cfg.data.set_use_bounding_rect(self.bounding_rectangle_checkbox.isChecked())
            cfg.data['defaults'][cfg.data.scale]['initial_rotation'] = float(self.initial_rotation_input.text())
            cfg.data['data']['clevel'] = int(self.clevel_input.text())
            cfg.data['data']['cname'] = self.cname_combobox.currentText()
            cfg.data['data']['chunkshape'] = (int(self.chunk_z_lineedit.text()),
                                              int(self.chunk_y_lineedit.text()),
                                              int(self.chunk_x_lineedit.text()))
            for scale in cfg.data.scales:
                scale_val = get_scale_val(scale)
                res_x = int(self.res_x_lineedit.text()) * scale_val
                res_y = int(self.res_y_lineedit.text()) * scale_val
                res_z = int(self.res_z_lineedit.text())
                cfg.data.set_resolution(s=scale, res_x=res_x, res_y=res_y, res_z=res_z)
        except Exception as e:
            logger.warning(e)
        finally:
            self.accept()

    def initUI(self):
        logger.info('')

        self.createScalesButton = QPushButton('Create Scale Pyramid')
        # self.createScalesButton.setStyleSheet("font-size: 10px;")
        self.createScalesButton.setFixedSize(QSize(128, 28))
        self.createScalesButton.setDefault(True)
        # self.createScalesButton.clicked.connect(self.on_apply)
        self.createScalesButton.clicked.connect(self.scale_only)

        self.scaleAndAlignButton = QPushButton('Create Scales &&\nInitialize Alignment')
        self.scaleAndAlignButton.setStyleSheet("font-size: 9px;")
        self.scaleAndAlignButton.setFixedSize(QSize(128,28))
        self.scaleAndAlignButton.setDefault(True)
        self.scaleAndAlignButton.clicked.connect(self.onScaleAndAlign)

        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setFixedSize(QSize(128,28))
        self.cancelButton.clicked.connect(self.on_cancel)

        self.w_buttons = QWidget()
        self.w_buttons.setStyleSheet("font-size: 10px;")
        # self.w_buttons.setLayout(VBL(self.cb_alignLowestScale, HW(self.cancelButton, self.createScalesButton, ExpandingWidget(self)), ExpandingWidget(self)))
        self.w_buttons.setLayout(VBL(HW(self.cancelButton, self.createScalesButton, self.scaleAndAlignButton, ExpandingWidget(self)), ExpandingWidget(self)))

        '''Scales Input Field'''
        # if do_scales_exist():
        #     scales_lst = [str(v) for v in
        #                   sorted([get_scale_val(level) for level in cfg.data['data']['scales'].keys()])]
        # else:
        #     width, height = cfg.data.image_size(level='scale_1')
        #     if (width * height) > 400_000_000:
        #         scales_lst = ['24 6 2 1']
        #     elif (width * height) > 200_000_000:
        #         scales_lst = ['16 6 2 1']
        #     elif (width * height) > 100_000_000:
        #         scales_lst = ['8 2 1']
        #     elif (width * height) > 10_000_000:
        #         scales_lst = ['4 2 1']
        #     else:
        #         scales_lst = ['4 1']

        scales_lst = ['24 6 2 1']

        scales_str = ' '.join(scales_lst)
        self.scales_input = QLineEdit(self)
        self.scales_input.setFixedWidth(130)
        self.scales_input.setText(scales_str)
        self.scales_input.setAlignment(Qt.AlignCenter)
        tip = "Scale factors, space-delimited.\nExample: To generate a 4x 2x and 1x level hierarchy:\n\n4 2 1"
        self.scale_instructions_label = QLabel(tip)
        self.scale_instructions_label.setStyleSheet("font-size: 11px;")
        self.scales_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))


        '''Voxel Size (Resolution) Fields'''
        tip = "Resolution or size of each voxel (nm)"
        self.res_x_label = QLabel("x:")
        self.res_x_label.setToolTip('X-dimension of each pixel')
        self.res_y_label = QLabel("y:")
        self.res_x_label.setToolTip('Y-dimension of each pixel')
        self.res_z_label = QLabel("z:")
        self.res_x_label.setToolTip('Tissue thickness, usually')
        self.res_x_lineedit = QLineEdit(self)
        self.res_y_lineedit = QLineEdit(self)
        self.res_z_lineedit = QLineEdit(self)
        self.res_x_lineedit.setFixedWidth(40)
        self.res_y_lineedit.setFixedWidth(40)
        self.res_z_lineedit.setFixedWidth(40)
        self.res_x_lineedit.setText(str(cfg.DEFAULT_RESX))
        self.res_y_lineedit.setText(str(cfg.DEFAULT_RESY))
        self.res_z_lineedit.setText(str(cfg.DEFAULT_RESZ))
        self.res_x_lineedit.setValidator(QIntValidator())
        self.res_y_lineedit.setValidator(QIntValidator())
        self.res_z_lineedit.setValidator(QIntValidator())
        self.res_x_layout = QHBoxLayout()
        self.res_y_layout = QHBoxLayout()
        self.res_z_layout = QHBoxLayout()
        self.res_x_layout.addWidget(self.res_x_label, alignment=Qt.AlignRight)
        self.res_y_layout.addWidget(self.res_y_label, alignment=Qt.AlignRight)
        self.res_z_layout.addWidget(self.res_z_label, alignment=Qt.AlignRight)
        self.res_x_layout.addWidget(self.res_x_lineedit, alignment=Qt.AlignLeft)
        self.res_y_layout.addWidget(self.res_y_lineedit, alignment=Qt.AlignLeft)
        self.res_z_layout.addWidget(self.res_z_lineedit, alignment=Qt.AlignLeft)
        self.resolution_layout = QHBoxLayout()
        self.resolution_layout.addLayout(self.res_x_layout)
        self.resolution_layout.addLayout(self.res_y_layout)
        self.resolution_layout.addLayout(self.res_z_layout)
        self.resolution_widget = QWidget()
        self.resolution_widget.setToolTip(tip)
        self.resolution_widget.setLayout(self.resolution_layout)


        '''Initial Rotation Dial & Field'''
        self.initial_rotation_dial = QDial()
        self.initial_rotation_dial.setFixedSize(QSize(30, 30))
        self.initial_rotation_dial.setMinimum(-180)
        self.initial_rotation_dial.setMaximum(180)
        self.initial_rotation_dial.setValue(0)
        # self.initial_rotation_dial.move(100, 50)
        self.initial_rotation_dial.valueChanged.connect(
            lambda: self.initial_rotation_input.setText(str(self.initial_rotation_dial.value())))
        tip = "Initial rotation is sometimes needed to prevent alignment from " \
              "aligning to unseen artifacts (default=0.0000)"
        self.initial_rotation_label = QLabel("Initial Rotation:")
        self.initial_rotation_input = QLineEdit(self)
        self.initial_rotation_input.textChanged.connect(lambda: self.initial_rotation_dial.setValue(int(float(self.initial_rotation_input.text()))))
        self.initial_rotation_input.setFixedWidth(70)
        self.initial_rotation_input.setText(str(cfg.DEFAULT_INITIAL_ROTATION))
        self.initial_rotation_input.setValidator(QIntValidator(-180, 180))
        self.initial_rotation_input.setAlignment(Qt.AlignCenter)
        self.initial_rotation_layout = HBL(self.initial_rotation_dial, self.initial_rotation_input)
        self.initial_rotation_widget = QWidget()
        self.initial_rotation_widget.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.initial_rotation_widget.setLayout(self.initial_rotation_layout)


        self.cb_clobber = QCheckBox()
        self.sb_clobber_pixels = QSpinBox()
        self.sb_clobber_pixels.setFixedSize(QSize(38, 18))
        self.sb_clobber_pixels.setMinimum(1)
        self.sb_clobber_pixels.setMaximum(16)
        self.sb_clobber_pixels.setMaximum(16)
        self.cb_clobber.setChecked(cfg.data.clobber())
        self.sb_clobber_pixels.setValue(int(cfg.data.clobber_px()))

        '''Bounding Box Field'''
        self.bounding_rectangle_label = QLabel("Bounding Box:")
        self.bounding_rectangle_checkbox = QCheckBox()
        self.bounding_rectangle_checkbox.setChecked(cfg.DEFAULT_USE_BOUNDING_BOX)


        tip = 'Zarr Compression Level\n(default=5)'
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clevel_input.setAlignment(Qt.AlignCenter)
        self.clevel_input.setText(str(cfg.CLEVEL))
        self.clevel_input.setFixedWidth(70)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)

        tip = 'Zarr Compression Type\n(default=zstd)'
        self.cname_label = QLabel('Compression Option:')
        self.cname_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cname_combobox = QComboBox(self)
        self.cname_combobox.addItems(["none", "zstd", "zlib"])
        # self.cname_combobox.setCurrentText(cfg.data.cname())
        self.cname_combobox.setCurrentText(str(cfg.CLEVEL))
        self.cname_combobox.setFixedWidth(78)

        '''Chunk Shape'''
        self.chunk_shape_label = QLabel("Chunk Shape:")
        self.chunk_x_label = QLabel("x:")
        self.chunk_y_label = QLabel("y:")
        self.chunk_z_label = QLabel("z:")
        self.chunk_x_lineedit = QLineEdit(self)
        self.chunk_y_lineedit = QLineEdit(self)
        self.chunk_z_lineedit = QLineEdit(self)
        self.chunk_x_lineedit.setFixedWidth(40)
        self.chunk_y_lineedit.setFixedWidth(40)
        self.chunk_z_lineedit.setFixedWidth(40)
        self.chunk_x_lineedit.setText(str(cfg.CHUNK_X))
        self.chunk_y_lineedit.setText(str(cfg.CHUNK_Y))
        self.chunk_z_lineedit.setText(str(cfg.CHUNK_Z))
        self.chunk_x_lineedit.setValidator(QIntValidator())
        self.chunk_y_lineedit.setValidator(QIntValidator())
        self.chunk_z_lineedit.setValidator(QIntValidator())
        self.chunk_x_layout = QHBoxLayout()
        self.chunk_y_layout = QHBoxLayout()
        self.chunk_z_layout = QHBoxLayout()
        self.chunk_x_layout.addWidget(self.chunk_x_label, alignment=Qt.AlignRight)
        self.chunk_y_layout.addWidget(self.chunk_y_label, alignment=Qt.AlignRight)
        self.chunk_z_layout.addWidget(self.chunk_z_label, alignment=Qt.AlignRight)
        self.chunk_x_layout.addWidget(self.chunk_x_lineedit, alignment=Qt.AlignLeft)
        self.chunk_y_layout.addWidget(self.chunk_y_lineedit, alignment=Qt.AlignLeft)
        self.chunk_z_layout.addWidget(self.chunk_z_lineedit, alignment=Qt.AlignLeft)
        self.chunk_shape_layout = QHBoxLayout()
        self.chunk_shape_layout.addLayout(self.chunk_z_layout)
        self.chunk_shape_layout.addLayout(self.chunk_y_layout)
        self.chunk_shape_layout.addLayout(self.chunk_x_layout)
        self.chunk_shape_widget = QWidget()
        self.chunk_shape_widget.setLayout(self.chunk_shape_layout)

        cfg.mw.gb_storage_options = QGroupBox('Storage')
        cfg.mw.gb_storage_options.setFixedWidth(400)
        cfg.mw.gb_storage_options.setFixedHeight(320)
        self.fl_storage_options = QFormLayout()
        self.fl_storage_options.addRow('Compression Level (1-9):', self.clevel_input)
        self.fl_storage_options.addRow('Compression Option:', self.cname_combobox)
        self.fl_storage_options.addRow('Chunk Shape:', self.chunk_shape_widget)
        txt = "These presets control the way volumetric data is stored. Zarr is an open-source format for " \
              "the storage of chunked, compressed, N-dimensional arrays with an interface similar to NumPy."
        txt = '\n'.join(textwrap.wrap(txt, width=55))
        lab = QLabel(txt)
        lab.setStyleSheet("""font-size: 10px; color: #161c20;""")
        self.fl_storage_options.addWidget(lab)
        cfg.mw.gb_storage_options.setLayout(self.fl_storage_options)

        cfg.mw.gb_config = QGroupBox('Main')
        cfg.mw.gb_config.setFixedWidth(400)
        cfg.mw.gb_config.setFixedHeight(320)
        self.fl_config = QFormLayout()
        # self.fl_config.setVerticalSpacing(4)
        # self.fl_config.setHorizontalSpacing(6)
        # self.fl_config.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        # self.fl_config.setSpacing(2)
        # self.fl_config.setContentsMargins(0, 0, 0, 0)
        self.fl_config.addRow('Scale Factors:', self.scales_input)
        self.fl_config.addWidget(self.scale_instructions_label)
        self.fl_config.addRow('Voxel Size (nm):', self.resolution_widget)
        self.fl_config.addRow('Initial Rotation (°):', self.initial_rotation_widget)
        self.fl_config.addRow('Clobber Fixed Pattern', self.cb_clobber)
        self.fl_config.addRow('Clobber Amount (px)', self.sb_clobber_pixels)
        self.fl_config.addRow('Bounding Box:', self.bounding_rectangle_checkbox)
        cfg.mw.gb_config.setLayout(self.fl_config)


        hbl = QHBoxLayout()
        # hbl.addWidget(cfg.mw.gb_config, alignment=Qt.AlignHCenter | Qt.AlignTop)
        # hbl.addWidget(cfg.mw.gb_storage_options, alignment=Qt.AlignHCenter | Qt.AlignTop)
        hbl.addWidget(cfg.mw.gb_config, alignment=Qt.AlignLeft | Qt.AlignTop)
        hbl.addWidget(cfg.mw.gb_storage_options, alignment=Qt.AlignLeft | Qt.AlignTop)
        hbl.addWidget(ExpandingWidget(self))
        # if cfg.data['data']['has_cal_grid']:
        #     path = cfg.data['data']['cal_grid_path']
        #     tn = ThumbnailFast(self, path)
        #     hbl.addWidget(tn, alignment=Qt.AlignHCenter | Qt.AlignTop)


        w = QWidget()
        w.setLayout(hbl)
        # vbl = VBL(w, self.w_buttons, ExpandingWidget(self))
        vbl = VBL(w, self.w_buttons)
        vbl.setAlignment(Qt.AlignTop)
        self.setLayout(vbl)



class RechunkDialog(QDialog):
    def __init__(self, parent=None, target=None): # parent=None allows passing in MainWindow if needed
        super().__init__()
        self.parent = parent
        self.target=target
        self.setModal(True)
        self.setFixedSize(400, 240)
        logger.info('Showing Project Configuration Dialog:')

        self.initUI()
        self.setWindowTitle("Rechunk - Select Chunk Shape")
        cfg.main_window.hud('Select Chunk Shape:')
        self.show()
        cfg.main_window.set_status('Awaiting User Input...')

    @Slot()
    def on_apply(self):

        logger.info('Setting chunk shape for rechunking...')
        z = min(int(self.chunk_z_lineedit.text()), len(cfg.data))
        y = int(self.chunk_y_lineedit.text())
        x = int(self.chunk_x_lineedit.text())
        try:

            cfg.data['data']['chunkshape'] = (z, y, x)
            self.chunkshape = (z, y, x)

        except Exception as e:
            logger.warning(e)

        finally:
            self.accept()


    @Slot()
    def on_cancel(self):
        logger.warning("Exiting On 'Cancel'...")
        self.close()

    def initUI(self):
        '''Chunk Shape'''
        self.chunk_shape_label = QLabel("Chunk Shape:")
        self.chunk_x_label = QLabel("x:")
        self.chunk_y_label = QLabel("y:")
        self.chunk_z_label = QLabel("z:")
        self.chunk_x_lineedit = QLineEdit(self)
        self.chunk_y_lineedit = QLineEdit(self)
        self.chunk_z_lineedit = QLineEdit(self)
        # self.leChunkZ.setEnabled(False)
        self.chunk_x_lineedit.setFixedWidth(40)
        self.chunk_y_lineedit.setFixedWidth(40)
        self.chunk_z_lineedit.setFixedWidth(40)
        chunkshape = cfg.data.chunkshape()
        self.chunk_x_lineedit.setText(str(chunkshape[2]))
        self.chunk_y_lineedit.setText(str(chunkshape[1]))
        self.chunk_z_lineedit.setText(str(chunkshape[0]))
        # img_size = cfg.data.image_size()
        # self.leChunkX.setValidator(QIntValidator(0, img_size[0]))
        # self.leChunkY.setValidator(QIntValidator(0, img_size[1]))
        # self.leChunkZ.setValidator(QIntValidator(0, len(cfg.data)))
        # self.leChunkX.setValidator(QIntValidator(0, img_size[0]))
        # self.leChunkY.setValidator(QIntValidator(0, img_size[1]))
        self.chunk_z_lineedit.setValidator(QIntValidator(0, len(cfg.data)))
        self.chunk_x_layout = QHBoxLayout()
        self.chunk_x_layout.setContentsMargins(4,4,4,4)
        self.chunk_y_layout = QHBoxLayout()
        self.chunk_y_layout.setContentsMargins(4,4,4,4)
        self.chunk_z_layout = QHBoxLayout()
        self.chunk_z_layout.setContentsMargins(4,4,4,4)
        self.chunk_x_layout.addWidget(self.chunk_x_label, alignment=Qt.AlignRight)
        self.chunk_y_layout.addWidget(self.chunk_y_label, alignment=Qt.AlignRight)
        self.chunk_z_layout.addWidget(self.chunk_z_label, alignment=Qt.AlignRight)
        self.chunk_x_layout.addWidget(self.chunk_x_lineedit, alignment=Qt.AlignLeft)
        self.chunk_y_layout.addWidget(self.chunk_y_lineedit, alignment=Qt.AlignLeft)
        self.chunk_z_layout.addWidget(self.chunk_z_lineedit, alignment=Qt.AlignLeft)
        self.chunk_shape_layout = QHBoxLayout()
        self.chunk_shape_layout.setContentsMargins(4,4,4,4)
        self.chunk_shape_layout.addLayout(self.chunk_z_layout)
        self.chunk_shape_layout.addLayout(self.chunk_y_layout)
        self.chunk_shape_layout.addLayout(self.chunk_x_layout)
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.chunk_shape_layout.addWidget(w)
        self.chunk_shape_widget = QWidget()
        self.chunk_layout = QHBoxLayout()
        self.chunk_layout.addWidget(self.chunk_shape_label, alignment=Qt.AlignLeft)
        self.chunk_layout.addWidget(self.chunk_shape_widget, alignment=Qt.AlignRight)
        self.chunk_shape_widget.setLayout(self.chunk_shape_layout)

        txt = "These presets control the way volumetric data is stored. Zarr is an open-source format for " \
              "the storage of chunked, compressed, N-dimensional arrays with an interface similar to NumPy."
        txt = '\n'.join(textwrap.wrap(txt, width=55))
        self.storage_info_label = QLabel(txt)
        self.storage_info_label.setStyleSheet("""font-size: 10px; color: #161c20;""")

        txt = "Rechunk '%s'..." %self.target
        txt = '\n'.join(textwrap.wrap(txt, width=55))
        self.main_text = QLabel(txt)


        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setDefault(False)
        self.cancelButton.setAutoDefault(False)
        self.cancelButton.clicked.connect(self.on_cancel)
        self.applyButton = QPushButton('Apply')
        self.applyButton.setDefault(True)
        self.applyButton.clicked.connect(self.on_apply)


        hbl = QHBoxLayout()
        hbl.addWidget(self.cancelButton)
        hbl.addWidget(self.applyButton)
        self.buttonWidget = QWidget()
        self.buttonWidget.setLayout(hbl)

        vbl = QVBoxLayout()
        vbl.setContentsMargins(4,4,4,4)
        vbl.addWidget(self.main_text)
        vbl.addWidget(self.chunk_shape_widget)
        vbl.addWidget(self.buttonWidget)
        vbl.addWidget(self.storage_info_label)

        self.setLayout(vbl)






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
