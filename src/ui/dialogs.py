#!/usr/bin/env python3

import os, sys, logging, textwrap, platform
from os.path import expanduser
from pathlib import Path
import faulthandler
import neuroglancer as ng

from qtpy.QtWidgets import QWidget, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, \
    QLineEdit, QVBoxLayout, QCheckBox, QTabWidget, QMessageBox, QFileDialog, QInputDialog, QPushButton, QToolButton
from qtpy.QtCore import Qt, Slot, QAbstractListModel, QModelIndex, QUrl, QDir, QFileInfo
from qtpy.QtGui import QDoubleValidator, QFont, QIntValidator, QPixmap
import src.config as cfg
from src.helpers import get_scale_val, do_scales_exist

logger = logging.getLogger(__name__)

#
# class TestMend(QWidget):
#     def __init__(self):
#         super().__init__()
#         layout = QHBoxLayout(self)
#         self.pathEdit = QLineEdit(placeholderText='Select path...')
#         self.button = QToolButton(text='...')
#         layout.addWidget(self.pathEdit)
#         layout.addWidget(self.button)
#         self.button.clicked.connect(self.selectTarget)
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
#                 button.setEnabled(True)
#                 return True
#
#         # get the "Open" button in the dialog
#         button = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Open)
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
            cfg.main_window.set_idle()
            return
        else:
            try:
                os.mkdir(path)
            except:
                logger.warning(f"Unable to create path '{path}'")
                cfg.main_window.hud.post(f"Unable to create path '{path}'")
            else:
                logger.info(f"Directory Created: {path}")
                cfg.main_window.hud.post(f"Directory Created: {path}")
                cfg.main_window.set_idle()
                return path


def export_affines_dialog() -> str:
    '''Dialog for saving a data. Returns 'filename'.'''
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('Export Affine Data as .csv')
    dialog.setNameFilter("Text Files (*.csv)")
    dialog.setViewMode(QFileDialog.Detail)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec() == QFileDialog.Accepted:
        cfg.main_window.hud.post('Exported: %s' % dialog.selectedFiles()[0])
        cfg.main_window.set_idle()
        return dialog.selectedFiles()[0]


def open_project_dialog() -> str:
    '''Dialog for opening a data. Returns 'filename'.'''
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('* Open Project *')
    dialog.setNameFilter("Text Files (*.proj *.json)")
    dialog.setViewMode(QFileDialog.Detail)
    urls = dialog.sidebarUrls()
    if '.tacc.utexas.edu' in platform.node():
        urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
        urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
    dialog.setSidebarUrls(urls)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec() == QFileDialog.Accepted:
        # self.hud.post("Loading Project '%s'" % os.path.basename(dialog.selectedFiles()[0]))
        cfg.main_window.set_idle()
        return dialog.selectedFiles()[0]


def import_images_dialog():
    '''Dialog for importing images. Returns list of filenames.'''
    dialog = QFileDialogPreview()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('Import Images - %s' % cfg.data.name())
    dialog.setNameFilter('Images (*.tif *.tiff)')
    dialog.setFileMode(QFileDialog.ExistingFiles)
    urls = dialog.sidebarUrls()
    urls.append(QUrl.fromLocalFile(QDir.homePath()))
    if '.tacc.utexas.edu' in platform.node():
        urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
        urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabData'))
    dialog.setSidebarUrls(urls)
    logger.debug('Selected Files:\n%s' % str(dialog.selectedFiles()))
    logger.info('Dialog Return Code: %s' % dialog.Accepted)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec_() == QDialog.Accepted:
        # self.set_mainwindow_project_view()
        cfg.main_window.set_idle()
        return dialog.selectedFiles()
    else:
        logger.warning('Import Images dialog did not return an image list')
        cfg.main_window.set_idle()
        return


def new_project_dialog() -> str:
    '''Dialog for saving a data. Returns 'filename'.'''
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.DontUseNativeDialog)
    dialog.setWindowTitle('* New Project *')
    dialog.setNameFilter("Text Files (*.proj *.json)")
    dialog.setLabelText(QFileDialog.Accept, "Create")
    dialog.setViewMode(QFileDialog.Detail)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    urls = dialog.sidebarUrls()
    if '.tacc.utexas.edu' in platform.node():
        urls.append(QUrl.fromLocalFile(os.getenv('WORK')))
        urls.append(QUrl.fromLocalFile('/work/08507/joely/ls6/HarrisLabShared'))
    dialog.setSidebarUrls(urls)
    cfg.main_window.set_status('Awaiting User Input...')
    if dialog.exec() == QFileDialog.Accepted:
        logger.info('Save File Path: %s' % dialog.selectedFiles()[0])
        cfg.main_window.set_idle()
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
#         self.setWindowTitle('Rename Project')
#         self.show()


class ConfigAppDialog(QDialog):
    def __init__(self, parent=None):  # parent=None allows passing in MainWindow if needed
        super(ConfigAppDialog, self).__init__()
        self.parent = parent
        logger.info('Showing Application Configuration Dialog:')
        self.initUI()
        cfg.main_window.set_status('Awaiting User Input...')

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        tsWidget = QWidget()
        tsLayout = QHBoxLayout()
        tsLayout.setContentsMargins(4, 2, 4, 2)
        tsWidget.setLayout(tsLayout)
        self.tsCheckbox = QCheckBox()
        self.tsCheckbox.setChecked(cfg.USE_TENSORSTORE)
        tsLayout.addWidget(QLabel('Enable Tensorstore Backend: '))
        tsLayout.addWidget(self.tsCheckbox, alignment=Qt.AlignRight)

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

        useprofilerWidget = QWidget()
        useprofilerLayout = QHBoxLayout()
        useprofilerLayout.setContentsMargins(4, 2, 4, 2)
        useprofilerWidget.setLayout(useprofilerLayout)
        self.useprofilerCheckbox = QCheckBox()
        self.useprofilerCheckbox.setChecked(cfg.PROFILER)
        useprofilerLayout.addWidget(QLabel('Enable Scalene Profiler: '))
        useprofilerLayout.addWidget(self.useprofilerCheckbox, alignment=Qt.AlignRight)

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


        layout.addWidget(tsWidget)
        layout.addWidget(headlessWidget)
        layout.addWidget(ngdebugWidget)
        layout.addWidget(mpdebugWidget)
        layout.addWidget(useprofilerWidget)
        layout.addWidget(faultWidget)
        layout.addWidget(buttonWidget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)


    @Slot()
    def on_apply(self):
        try:
            cfg.main_window.hud('Applying Application Settings...')
            cfg.USE_TENCSORSTORE = self.tsCheckbox.isChecked()
            cfg.HEADLESS = self.headlessCheckbox.isChecked()
            if cfg.HEADLESS:
                cfg.main_window.tabs_main.setTabVisible(0, False)
                cfg.main_window.external_hyperlink.show()
            else:
                cfg.main_window.tabs_main.setTabVisible(0, True)
                cfg.main_window.external_hyperlink.hide()
            cfg.DEBUG_NEUROGLANCER = self.ngdebugCheckbox.isChecked()
            if ng.is_server_running():
                logger.info(f'Setting Neuroglancer Server Debugging: {cfg.DEBUG_NEUROGLANCER}')
                ng.server.debug = cfg.DEBUG_NEUROGLANCER

            cfg.DEBUG_MP = self.mpdebugCheckbox.isChecked()
            cfg.PROFILER = self.useprofilerCheckbox.isChecked()
            if cfg.PROFILER:
                pass
                # from scalene import scalene_profiler
                # scalene_profiler.start()
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
            cfg.main_window.set_idle()

    @Slot()
    def on_cancel(self):
        logger.warning("ConfigProjectDialog Exiting On 'Cancel'...")
        self.close()



class ConfigProjectDialog(QDialog):
    def __init__(self, parent=None): # parent=None allows passing in MainWindow if needed
        super(ConfigProjectDialog, self).__init__()
        self.parent = parent
        logger.info('Showing Project Configuration Dialog:')
        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setDefault(False)
        self.cancelButton.setAutoDefault(False)
        self.cancelButton.clicked.connect(self.on_cancel)
        # self.applyButton = QPushButton('Apply')
        self.applyButton = QPushButton('Scale && Configure')
        self.applyButton.setDefault(True)
        self.applyButton.clicked.connect(self.on_apply)
        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.addWidget(self.cancelButton)
        self.buttonLayout.addWidget(self.applyButton)
        self.buttonWidget = QWidget()
        self.buttonWidget.setLayout(self.buttonLayout)
        self.tab_widget = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab_widget.addTab(self.tab1, "Main")
        self.tab_widget.addTab(self.tab2, "Storage")
        self.initUI_tab1()
        self.initUI_tab2()
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.tab_widget)
        self.main_layout.addWidget(self.buttonWidget)
        self.setLayout(self.main_layout)
        self.setWindowTitle("Project Configuration")
        cfg.main_window.hud('Set Scales and Configure:')
        self.show()
        cfg.main_window.set_status('Awaiting User Input...')

    @Slot()
    def on_apply(self):
        try:
            cfg.main_window.hud('Applying Project Settings...')
            cfg.data.set_scales_from_string(self.scales_input.text())
            cfg.data.set_use_bounding_rect(self.bounding_rectangle_checkbox.isChecked())
            cfg.data['data']['initial_scale'] = float(self.initial_scale_input.text())
            cfg.data['data']['initial_rotation'] = float(self.initial_rotation_input.text())
            cfg.data['data']['clevel'] = int(self.clevel_input.text())
            cfg.data['data']['cname'] = self.cname_combobox.currentText()
            cfg.data['data']['chunkshape'] = (int(self.chunk_z_lineedit.text()),
                                              int(self.chunk_y_lineedit.text()),
                                              int(self.chunk_x_lineedit.text()))
            for scale in cfg.data.scales():
                scale_val = get_scale_val(scale)
                res_x = int(self.res_x_lineedit.text()) * scale_val
                res_y = int(self.res_y_lineedit.text()) * scale_val
                res_z = int(self.res_z_lineedit.text())
                cfg.data.set_resolutions(scale=scale, res_x=res_x, res_y=res_y, res_z=res_z)
        except Exception as e:
            logger.warning(e)
        finally:
            cfg.main_window.hud.done()
            self.accept()
            cfg.main_window.set_idle()


    @Slot()
    def on_cancel(self):
        logger.warning("ConfigProjectDialog Exiting On 'Cancel'...")
        self.close()

    def initUI_tab2(self):
        tip = 'Zarr Compression Level\n(default=5)'
        self.clevel_label = QLabel('Compression Level (1-9):')
        self.clevel_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setAlignment(Qt.AlignCenter)
        self.clevel_input.setText(str(cfg.data.clevel()))
        self.clevel_input.setFixedWidth(70)
        self.clevel_valid = QIntValidator(1, 9, self)
        self.clevel_input.setValidator(self.clevel_valid)
        self.clevel_layout = QHBoxLayout()
        self.clevel_layout.addWidget(self.clevel_label, alignment=Qt.AlignLeft)
        self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignRight)

        tip = 'Zarr Compression Type\n(default=zstd)'
        self.cname_label = QLabel('Compression Option:')
        self.cname_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.cname_combobox = QComboBox(self)
        # self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.addItems(["zstd", "zlib", "none"])
        self.cname_combobox.setCurrentText(cfg.data.cname())
        self.cname_combobox.setFixedWidth(78)
        self.cname_layout = QHBoxLayout()
        self.cname_layout.addWidget(self.cname_label, alignment=Qt.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignRight)

        '''Chunk Shape'''
        self.chunk_shape_label = QLabel("Chunk Shape:")
        self.chunk_x_label = QLabel("x:")
        self.chunk_y_label = QLabel("y:")
        self.chunk_z_label = QLabel("z:")
        self.chunk_x_lineedit = QLineEdit(self)
        self.chunk_y_lineedit = QLineEdit(self)
        self.chunk_z_lineedit = QLineEdit(self)
        # self.chunk_z_lineedit.setEnabled(False)
        self.chunk_x_lineedit.setFixedWidth(40)
        self.chunk_y_lineedit.setFixedWidth(40)
        self.chunk_z_lineedit.setFixedWidth(40)
        chunkshape = cfg.data.chunkshape()
        self.chunk_x_lineedit.setText(str(chunkshape[2]))
        self.chunk_y_lineedit.setText(str(chunkshape[1]))
        self.chunk_z_lineedit.setText(str(chunkshape[0]))
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
        self.chunk_layout = QHBoxLayout()
        self.chunk_layout.addWidget(self.chunk_shape_label, alignment=Qt.AlignLeft)
        self.chunk_layout.addWidget(self.chunk_shape_widget, alignment=Qt.AlignRight)

        txt = "AlignEM-SWiFT uses a chunked and compressed N-dimensional file format called Zarr for rapid viewing of " \
              "volumetric data in Neuroglancer. These settings determine the way volumetric data is " \
              "stored and retrieved from disk storage."
        txt = '\n'.join(textwrap.wrap(txt, width=55))
        self.storage_info_label = QLabel(txt)

        self.export_settings_layout = QGridLayout()
        self.export_settings_layout.addLayout(self.cname_layout, 0, 0)
        self.export_settings_layout.addLayout(self.clevel_layout, 1, 0)
        self.export_settings_layout.addLayout(self.chunk_layout, 2, 0)
        self.export_settings_layout.addWidget(self.storage_info_label, 3, 0)

        self.tab2.setLayout(self.export_settings_layout)


    def initUI_tab1(self):
        '''Scales Field'''
        if not cfg.data.is_mendenhall():

            if do_scales_exist():
                scales_lst = [str(v) for v in
                                  sorted([get_scale_val(s) for s in cfg.data['data']['scales'].keys()])]
            else:
                width, height = cfg.data.image_size(s='scale_1')
                if (width*height) > 400_000_000:
                    scales_lst = ['24 6 2 1']
                elif (width*height) > 200_000_000:
                    scales_lst = ['16 6 2 1']
                elif (width * height) > 100_000_000:
                    scales_lst = ['8 2 1']
                elif (width * height) > 10_000_000:
                    scales_lst = ['4 2 1']
                else:
                    scales_lst = ['4 1']

            scales_str = ' '.join(scales_lst)
            self.scales_label = QLabel("Scale Factors:")
            self.scales_input = QLineEdit(self)
            self.scales_input.setFixedWidth(130)
            self.scales_input.setText(scales_str)
            self.scales_input.setAlignment(Qt.AlignCenter)
            tip = "Scale factors, separated by spaces.\n(example) To generate 4x 2x and 1x/full scales, type: 4 2 1"
            self.scale_instructions_label = QLabel(tip)
            self.scale_instructions_label.setStyleSheet("font-size: 11px;")
            self.scales_label.setToolTip(tip)
            self.scales_input.setToolTip(tip)
            self.scales_layout = QHBoxLayout()
            self.scales_layout.addWidget(self.scales_label, alignment=Qt.AlignLeft)
            self.scales_layout.addWidget(self.scales_input, alignment=Qt.AlignRight)

        '''Resolution Fields'''
        tip = "Resolution or size of each voxel (nm)"
        self.resolution_label = QLabel("Voxel Size (nm):")
        self.resolution_label.setToolTip(tip)
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
        # self.res_x_lineedit.setText(str(cfg.data['data']['resolution_x']))
        # self.res_y_lineedit.setText(str(cfg.data['data']['resolution_y']))
        # self.res_z_lineedit.setText(str(cfg.data['data']['resolution_z']))
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
        self.resolution_layout = QHBoxLayout()
        self.resolution_layout.addWidget(self.resolution_label, Qt.AlignLeft)
        self.resolution_layout.addWidget(self.resolution_widget, Qt.AlignRight)

        if not cfg.data.is_mendenhall():
            '''Initial Rotation Field'''
            tip = "Initial rotation is sometimes needed to prevent alignment from " \
                  "aligning to unseen artifacts (default=0.0000)"
            self.initial_rotation_label = QLabel("Initial Rotation:")
            self.initial_rotation_input = QLineEdit(self)
            self.initial_rotation_input.setFixedWidth(70)
            self.initial_rotation_input.setText(str(cfg.DEFAULT_INITIAL_ROTATION))
            self.initial_rotation_input.setValidator(QDoubleValidator(0.0000, 5.0000, 4, self))
            self.initial_rotation_input.setAlignment(Qt.AlignCenter)
            self.initial_rotation_layout = QHBoxLayout()
            self.initial_rotation_layout.addWidget(self.initial_rotation_label, alignment=Qt.AlignLeft)
            self.initial_rotation_layout.addWidget(self.initial_rotation_input, alignment=Qt.AlignRight)
            self.initial_rotation_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))

            '''Initial Scale Field'''
            self.initial_scale_label = QLabel("Initial Scale:")
            self.initial_scale_input = QLineEdit(self)
            self.initial_scale_input.setFixedWidth(70)
            self.initial_scale_input.setText(str(cfg.DEFAULT_INITIAL_SCALE))
            self.initial_scale_input.setValidator(QDoubleValidator(0.0000, 5.0000, 4, self))
            self.initial_scale_input.setAlignment(Qt.AlignCenter)
            self.initial_scale_layout = QHBoxLayout()
            self.initial_scale_layout.addWidget(self.initial_scale_label, alignment=Qt.AlignLeft)
            self.initial_scale_layout.addWidget(self.initial_scale_input, alignment=Qt.AlignRight)

        '''Bounding Box Field'''
        self.bounding_rectangle_label = QLabel("Bounding Box:")
        self.bounding_rectangle_checkbox = QCheckBox()
        self.bounding_rectangle_checkbox.setChecked(cfg.DEFAULT_BOUNDING_BOX)
        self.bounding_rectangle_layout = QHBoxLayout()
        self.bounding_rectangle_layout.addWidget(self.bounding_rectangle_label, alignment=Qt.AlignLeft)
        self.bounding_rectangle_layout.addWidget(self.bounding_rectangle_checkbox, alignment=Qt.AlignRight)

        '''Groupbox QFormLayout'''
        layout = QGridLayout()
        if not cfg.data.is_mendenhall():
            layout.addLayout(self.scales_layout , 0, 0)
            layout.addWidget(self.scale_instructions_label , 1, 0)
        layout.addLayout(self.resolution_layout, 2, 0)
        if not cfg.data.is_mendenhall():
            layout.addLayout(self.initial_rotation_layout, 3, 0)
            layout.addLayout(self.initial_scale_layout, 4, 0)
        layout.addLayout(self.bounding_rectangle_layout, 5, 0)
        self.tab1.setLayout(layout)


def show_ng_commands():
    msgBox = QMessageBox()
    msgBox.setIcon(QMessageBox.Information)
    msgBox.setText('pop up text')
    msgBox.setWindowTitle('title')
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


class QFileDialogPreview(QFileDialog):
    def __init__(self, *args, **kwargs):
        QFileDialog.__init__(self, *args, **kwargs)
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFixedSize(self.width() + 360, self.height())
        self.mpPreview = QLabel("Preview", self)
        self.mpPreview.setFixedSize(360, 360)
        self.mpPreview.setAlignment(Qt.AlignCenter)
        self.mpPreview.setObjectName("labelPreview")
        box = QVBoxLayout()
        box.addWidget(self.mpPreview)
        box.addStretch()
        self.layout().addLayout(box, 1, 3, 1, 1)
        self.currentChanged.connect(self.onChange)
        self.fileSelected.connect(self.onFileSelected)
        self.filesSelected.connect(self.onFilesSelected)
        self._fileSelected = None
        self._filesSelected = None

    def onChange(self, path):
        pixmap = QPixmap(path)
        if(pixmap.isNull()):
            self.mpPreview.setText('Preview')
        else:
            self.mpPreview.setPixmap(pixmap.scaled(self.mpPreview.width(),
                                                   self.mpPreview.height(),
                                                   Qt.KeepAspectRatio,
                                                   Qt.SmoothTransformation))

    def onFileSelected(self, file):    self._fileSelected = file
    def onFilesSelected(self, files):  self._filesSelected = files
    def getFileSelected(self):         return self._fileSelected
    def getFilesSelected(self):        return self._filesSelected
