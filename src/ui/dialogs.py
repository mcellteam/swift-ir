#!/usr/bin/env python3

import os, logging, textwrap

from qtpy.QtWidgets import QWidget, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, \
    QLineEdit, QVBoxLayout, QCheckBox, QTabWidget, QMessageBox, QFileDialog, QInputDialog, QPushButton
from qtpy.QtCore import Qt, Slot, QAbstractListModel, QModelIndex
from qtpy.QtGui import QDoubleValidator, QFont, QIntValidator, QPixmap
import src.config as cfg
from src.helpers import get_scale_val, do_scales_exist

logger = logging.getLogger(__name__)


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
#
#



'''
Python-Qt Documentation - Using Adapters between Forms and Models
https://doc.qt.io/qtforpython/overviews/modelview.html#using-adapters-between-forms-and-models
***QDataWidgetMapper***

***QAbstractListModel*** <-- May need to subclass 
'''

class ConfigDialog(QDialog):

    def __init__(self, parent=None): # parent=None allows passing in MainWindow if needed
        self.parent = parent
        super(ConfigDialog, self).__init__()
        logger.info('>>>> Config Dialog Start >>>>')
        cfg.main_window.hud.post('Configuring Project Settings Based On User Responses')
        # self.setGeometry(400,400,300,260)
        # g = self.geometry()
        # g.moveCenter(self.parent.geometry().center())
        # self.setGeometry(g)

        # self.setWindowFlags(
        #     Qt.CustomizeWindowHint |
        #     Qt.FramelessWindowHint)

        # self.defaults_file = cfg.data['data']['destination_path'] + '/defaults.json'
        # print('self.defaults_file = ', str(self.defaults_file))
        # self.defaults = None


        # self.button_cancel = QPushButton("Cancel")
        # self.button_cancel.clicked.connect(self.on_cancel)
        # self.button_cancel.setAutoDefault(False)

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.clicked.connect(self.set_project_configuration)

        self.tab_widget = QTabWidget()

        self.tab1 = QWidget()
        self.tab2 = QWidget()
        # self.tab3 = QWidget()

        self.tab_widget.addTab(self.tab1, "Main")
        self.tab_widget.addTab(self.tab2, "Storage")
        # self.tab_widget.addTab(self.tab3, "Tab 3")

        self.initUI_tab1()
        self.initUI_tab2()
        # self.initUI_tab3()

        # self.button_apply_settings = QPushButton("Generate Scales")
        # self.button_apply_settings.clicked.connect(self.on_create_button_clicked)
        # self.button_apply_settings.setAutoDefault(True)
        # button_layout = QHBoxLayout()
        # button_layout.addWidget(self.button_cancel)
        # button_layout.addWidget(self.button_apply_settings)

        self.main_layout = QVBoxLayout()
        # main_layout.addWidget(self.formGroupBox)
        self.main_layout.addWidget(self.tab_widget)
        # main_layout.addLayout(button_layout)
        self.main_layout.addWidget(self.buttonBox)
        self.setLayout(self.main_layout)

        self.setWindowTitle("Project Configuration")

        self.show()


        # self.load()
        # print('self.defaults = ', str(self.defaults))
        # self.defaults_model = DefaultsModel(data=self.defaults)
        #
        # # self.mapper = None
        # self.mapper = QDataWidgetMapper(self)
        # # self.mapper.setModel(self.defaults_model)
        # self.mapper.setModel(self.defaults_model)
        # self.mapper.addMapping(self.whitening_input, 0)
        # self.mapper.addMapping(self.swim_input, 1)
        # self.mapper.addMapping(self.initial_rotation_input, 2)
        # self.mapper.addMapping(self.bounding_rectangle_checkbox, 3)
        # self.mapper.toFirst()
        # self.defaults_model.dataChanged.connect(lambda value: print(value.row(), value.data()))
        # self.defaults_model.dataChanged.connect(self.save)

    #
    # @Slot()
    # def load(self):
    #     try:
    #         with open(self.defaults_file, "r") as f:
    #             self.defaults = list(json.load(f))
    #             print("self.defaults=", self.defaults)
    #             # self.defaults = f.read()
    #     except Exception:
    #         pass
    #
    # @Slot()
    # def save(self):
    #     print('ConfigDialog.save was called')
    #     with open(self.defaults_file, "w") as f:
    #         data = json.dump(self.defaults, f)
    #         # f.write(self.defaults)

    @Slot()
    def set_project_configuration(self):
        cfg.main_window.hud('Initializing Project Data...')
        cfg.data.set_scales_from_string(self.scales_input.text())
        cfg.data.set_use_bounding_rect(self.bounding_rectangle_checkbox.isChecked())
        cfg.data['data']['initial_scale'] = float(self.initial_scale_input.text())
        cfg.data['data']['initial_rotation'] = float(self.initial_rotation_input.text())
        cfg.data['data']['clevel'] = int(self.clevel_input.text())
        cfg.data['data']['cname'] = self.cname_combobox.currentText()
        cfg.data['data']['chunkshape'] = [int(self.chunk_z_lineedit.text()),
                                          int(self.chunk_y_lineedit.text()),
                                          int(self.chunk_x_lineedit.text())]
        for scale in cfg.data.scales():
            scale_val = get_scale_val(scale)
            cfg.data['data']['scales'][scale]['resolution_x'] = int(self.res_x_lineedit.text()) * scale_val
            cfg.data['data']['scales'][scale]['resolution_y'] = int(self.res_y_lineedit.text()) * scale_val
            cfg.data['data']['scales'][scale]['resolution_z'] = int(self.res_z_lineedit.text())
        self.close()

    def on_cancel(self):
        self.close()


    def initUI_tab2(self):

        tip = 'Zarr Compression Level\n(default=5)'
        self.clevel_label = QLabel('Compression Level (1-9):')
        self.clevel_label.setToolTip('\n'.join(textwrap.wrap(tip, width=35)))
        self.clevel_input = QLineEdit(self)
        self.clevel_input.setAlignment(Qt.AlignCenter)
        self.clevel_input.setText(str(cfg.CLEVEL))
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
        self.cname_combobox.addItems(["zstd", "zlib", "gzip", "none"])
        self.cname_combobox.setCurrentText(cfg.CNAME)
        self.cname_combobox.setFixedWidth(78)

        self.cname_layout = QHBoxLayout()
        self.cname_layout.addWidget(self.cname_label, alignment=Qt.AlignLeft)
        self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignRight)


        # '''Compression Level (clevel)'''
        # self.clevel_layout = QHBoxLayout()
        # self.clevel_layout.setContentsMargins(0, 0, 0, 0)
        # self.clevel_layout.addWidget(self.clevel_label, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.clevel_layout.addWidget(self.clevel_input, alignment=Qt.AlignmentFlag.AlignRight)
        #
        # '''Compression Type (cname)'''
        # self.cname_layout = QHBoxLayout()
        # self.cname_layout.addWidget(self.cname_label, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.cname_layout.addWidget(self.cname_combobox, alignment=Qt.AlignmentFlag.AlignRight)


        '''Chunk Shape'''
        self.chunk_shape_label = QLabel("Chunk Shape:")
        self.chunk_x_label = QLabel("x:")
        self.chunk_y_label = QLabel("y:")
        self.chunk_z_label = QLabel("z:")
        self.chunk_x_lineedit = QLineEdit(self)
        self.chunk_y_lineedit = QLineEdit(self)
        self.chunk_z_lineedit = QLineEdit(self)
        self.chunk_z_lineedit.setEnabled(False)
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

        # DEFAULT_SWIM_WINDOW = float(0.8125)
        # DEFAULT_WHITENING = float(-0.6800)
        # DEFAULT_POLY_ORDER = int(0)
        # DEFAULT_NULL_BIAS = bool(False)
        # DEFAULT_BOUNDING_BOX = bool(True)

        # '''Whitening Factor Field'''
        # self.whitening_label = QLabel("Whitening:")
        # self.whitening_input = QLineEdit(self)
        # self.whitening_input.setText(str(cfg.DEFAULT_WHITENING))
        # self.whitening_input.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        # self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #
        # '''SWIM Window Field'''
        # self.swim_label = QLabel("SWIM Window:")
        # self.swim_input = QLineEdit(self)
        # self.swim_input.setText(str(cfg.DEFAULT_SWIM_WINDOW))
        # self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        # self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)


        '''Scales Field'''
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
        self.res_x_lineedit.setText(str(cfg.RES_X))
        self.res_y_lineedit.setText(str(cfg.RES_Y))
        self.res_z_lineedit.setText(str(cfg.RES_Z))
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


        '''Initial Rotation Field'''
        self.initial_rotation_label = QLabel("Initial Rotation:")
        self.initial_rotation_input = QLineEdit(self)
        self.initial_rotation_input.setFixedWidth(70)
        self.initial_rotation_input.setText(str(cfg.DEFAULT_INITIAL_ROTATION))
        self.initial_rotation_input.setValidator(QDoubleValidator(0.0000, 5.0000, 4, self))
        self.initial_rotation_input.setAlignment(Qt.AlignCenter)
        self.initial_rotation_layout = QHBoxLayout()
        self.initial_rotation_layout.addWidget(self.initial_rotation_label, alignment=Qt.AlignLeft)
        self.initial_rotation_layout.addWidget(self.initial_rotation_input, alignment=Qt.AlignRight)

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
        layout.addLayout(self.scales_layout , 0, 0)
        layout.addWidget(self.scale_instructions_label , 1, 0)
        layout.addLayout(self.resolution_layout, 2, 0)
        layout.addLayout(self.initial_rotation_layout, 3, 0)
        layout.addLayout(self.initial_scale_layout, 4, 0)
        layout.addLayout(self.bounding_rectangle_layout, 5, 0)
        # self.formGroupBox = QGroupBox('Recipe Maker')
        # self.formGroupBox.setLayout(layout)

        self.tab1.setLayout(layout)

        # tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        # self.whitening_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # self.whitening_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        # self.swim_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # self.swim_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        tip = "Initial rotation is sometimes needed to prevent alignment from aligning to unseen artifacts (default=0.0000)"
        self.initial_rotation_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # self.initial_rotation_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))


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
