#!/usr/bin/env python3

import os, sys, copy, json, inspect, logging, textwrap

from PyQt5.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox, \
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QFormLayout, \
    QCheckBox, QToolButton, QDataWidgetMapper
from PyQt5.QtCore import Qt, QAbstractTableModel, QAbstractListModel, QModelIndex
from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtGui import QDoubleValidator, QFont

import src.config as cfg
from src.helpers import get_scale_key, get_scale_val, do_scales_exist

__all__ = ['DefaultsForm','DefaultsModel']

logger = logging.getLogger(__name__)

'''
Python-Qt Documentation - Using Adapters between Forms and Models
https://doc.qt.io/qtforpython/overviews/modelview.html#using-adapters-between-forms-and-models
***QDataWidgetMapper***

***QAbstractListModel*** <-- May need to subclass 
'''

class DefaultsForm(QDialog):

    def __init__(self, parent=None): # parent=None allows passing in MainWindow if needed
        self.parent = parent
        super(DefaultsForm, self).__init__()
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

        self.initUI()

        # self.button_cancel = QPushButton("Cancel")
        # self.button_cancel.clicked.connect(self.on_cancel)
        # self.button_cancel.setAutoDefault(False)

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.clicked.connect(self.on_create_button_clicked)



        # self.button_apply_settings = QPushButton("Generate Scales")
        # self.button_apply_settings.clicked.connect(self.on_create_button_clicked)
        # self.button_apply_settings.setAutoDefault(True)
        # button_layout = QHBoxLayout()
        # button_layout.addWidget(self.button_cancel)
        # button_layout.addWidget(self.button_apply_settings)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.formGroupBox)
        # main_layout.addLayout(button_layout)
        main_layout.addWidget(self.buttonBox)
        self.setLayout(main_layout)

        self.setWindowTitle("Project Form")


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
    #     print('DefaultsForm.save was called')
    #     with open(self.defaults_file, "w") as f:
    #         data = json.dump(self.defaults, f)
    #         # f.write(self.defaults)

    def update_project_dict(self):
        # logger.critical('Running update_init_scale:')
        logger.critical('Running update_project_dict:')
        cfg.data.set_scales_from_string(self.scales_input.text())
        cfg.DEFAULT_INITIAL_ROTATION = float(self.initial_rotation_input.text())
        cfg.DEFAULT_INITIAL_SCALE = float(self.initial_scale_input.text())
        cfg.DEFAULT_BOUNDING_BOX = float(self.bounding_rectangle_checkbox.isChecked())
        for scale in cfg.data.get_scales():
            cfg.data['data']['scales'][scale]['use_bounding_rect'] = cfg.DEFAULT_BOUNDING_BOX
            for layer in cfg.data['data']['scales'][scale]['alignment_stack']:
                layer['align_to_ref_method']['method_options'].update({'initial_scale': cfg.DEFAULT_INITIAL_SCALE})
                layer['align_to_ref_method']['method_options'].update({'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION})
        cfg.main_window.save_project_to_file()

    def on_cancel(self):
        self.close()

    @Slot()
    def on_create_button_clicked(self):
        logger.critical('on_create_button_clicked:')
        self.update_project_dict()
        self.close()

    def initUI(self):

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
            scales_lst = ['1']
        scales_str = ' '.join(scales_lst)


        self.scales_label = QLabel("Scale Factors:")
        self.scales_input = QLineEdit(self)
        self.scales_input.setText(scales_str)
        self.scales_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip = "Enter scale factors separated by spaces.\nFor example, to generate 1x 2x and 4x scales: 1 2 4"
        self.scales_label.setToolTip(tip)
        self.scales_input.setToolTip(tip)

        '''Initial Rotation Field'''
        self.initial_rotation_label = QLabel("Initial Rotation:")
        self.initial_rotation_input = QLineEdit(self)
        self.initial_rotation_input.setText(str(cfg.DEFAULT_INITIAL_ROTATION))
        self.initial_rotation_input.setValidator(QDoubleValidator(0.0000, 5.0000, 4, self))
        self.initial_rotation_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        '''Initial Scale Field'''
        self.initial_scale_label = QLabel("Initial Scale:")
        self.initial_scale_input = QLineEdit(self)
        self.initial_scale_input.setText(str(cfg.DEFAULT_INITIAL_SCALE))
        self.initial_scale_input.setValidator(QDoubleValidator(0.0000, 5.0000, 4, self))
        self.initial_scale_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        '''Bounding Box Field'''
        self.bounding_rectangle_label = QLabel("Bounding Box:")
        self.bounding_rectangle_checkbox = QCheckBox()
        self.bounding_rectangle_checkbox.setChecked(cfg.DEFAULT_BOUNDING_BOX)

        '''Groupbox QFormLayout'''
        layout = QFormLayout()
        # layout.addRow(self.whitening_label, self.whitening_input)
        # layout.addRow(self.swim_label, self.swim_input)
        layout.addRow(self.scales_label, self.scales_input)
        layout.addRow(self.initial_rotation_label, self.initial_rotation_input)
        layout.addRow(self.initial_scale_label, self.initial_scale_input)
        layout.addRow(self.bounding_rectangle_label, self.bounding_rectangle_checkbox)
        self.formGroupBox = QGroupBox('Configure Recipe')
        self.formGroupBox.setLayout(layout)

        # tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        # self.whitening_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # self.whitening_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        # self.swim_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # self.swim_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        tip = "Initial rotation is sometimes needed to prevent alignment from aligning to unseen artifacts (default=0.0000)"
        self.initial_rotation_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.initial_rotation_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))

        self.formGroupBox.setLayout(layout)





class DefaultsModel(QAbstractListModel):
    def __init__(self, data, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.lst = data

    # def columnCount(self, parent=QModelIndex()):
    #     return len(self.lst[0])

    def rowCount(self, parent=QModelIndex()):
        return len(self.lst)

    def data(self, index, role=Qt.DisplayRole):
        # row = index.row()
        # col = index.column()
        row = index.column()

        if role == Qt.EditRole:
            # return self.lst[row][col]
            return self.lst[row]
        elif role == Qt.DisplayRole:
            # return self.lst[row][col]
            return self.lst[row]

    def flags(self, index):
        flags = super(DefaultsModel, self).flags(index)

        if index.isValid():
            flags |= Qt.ItemIsEditable
            flags |= Qt.ItemIsDragEnabled
        else:
            flags = Qt.ItemIsDropEnabled

        return flags

    def setData(self, index, value, role=Qt.EditRole):

        if not index.isValid() or role != Qt.EditRole:
            return False

        # self.lst[index.row()][index.column()] = value
        self.lst[index.row()] = value
        # self.dataChanged.emit(index, index) # <-- list()/[] is necessary since Qt5
        self.dataChanged.emit(index, index, list()) # <-- list()/[] is necessary since Qt5
        return True


