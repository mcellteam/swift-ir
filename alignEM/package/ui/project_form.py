#!/usr/bin/env python3

import os, sys, copy, json, inspect, logging, textwrap

from qtpy.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox, \
    QHBoxLayout, QLabel, QLineEdit, QMenu, QMenuBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QFormLayout, \
    QCheckBox, QToolButton, QDataWidgetMapper
from qtpy.QtCore import Qt, Signal, Slot, QAbstractTableModel, QAbstractListModel, QModelIndex
from qtpy.QtGui import QDoubleValidator, QFont

import package.config as cfg

__all__ = ['ProjectForm']

logger = logging.getLogger(__name__)

'''
Python-Qt Documentation - Using Adapters between Forms and Models
https://doc.qt.io/qtforpython/overviews/modelview.html#using-adapters-between-forms-and-models
***QDataWidgetMapper***

***QAbstractListModel*** <-- May need to subclass 
'''

class ProjectForm(QDialog):

    def __init__(self, parent=None): # parent=None allows passing in MainWindow if needed
        self.parent = parent
        super(ProjectForm, self).__init__()
        self.setWindowTitle("ToolButton")
        self.setGeometry(400,400,300,260)
        g = self.geometry()
        g.moveCenter(self.parent.geometry().center())
        self.setGeometry(g)
        self.defaults_file = cfg.project_data['data']['destination_path'] + '/defaults.json'
        print('self.defaults_file = ', str(self.defaults_file))
        self.defaults = None

        self.createFormGroupBox()

        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.on_cancel)
        self.button_cancel.setAutoDefault(False)

        self.button_create_project = QPushButton("Create Project")
        self.button_create_project.clicked.connect(self.on_create_button_clicked)
        self.button_create_project.setAutoDefault(True)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_cancel)
        button_layout.addWidget(self.button_create_project)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.formGroupBox)
        main_layout.addLayout(button_layout)
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

        self.show()


    @Slot()
    def load(self):
        try:
            with open(self.defaults_file, "r") as f:
                self.defaults = list(json.load(f))
                print("self.defaults=", self.defaults)
                # self.defaults = f.read()
        except Exception:
            pass

    @Slot()
    def save(self):
        print('ProjectForm.save was called')
        with open(self.defaults_file, "w") as f:
            data = json.dump(self.defaults, f)
            # f.write(self.defaults)



    def on_cancel(self):
        self.close()

    def on_create_button_clicked(self):
        # emit custom signal and pass some parameters back in self.config
        self.write_config()
        # self.emit(Signal("dialog closed"), self.config)
        self.close()

    def write_config(self):
        logger.debug('Writing config defaults...')
        cfg.DEFAULT_SWIM_WINDOW = float(self.swim_input.text())
        cfg.DEFAULT_WHITENING = float(self.whitening_input.text())
        cfg.DEFAULT_INITIAL_ROTATION = float(self.initial_rotation_input.text())
        cfg.DEFAULT_INITIAL_SCALE = float(self.initial_rotation_input.text())
        cfg.DEFAULT_BOUNDING_BOX = bool(self.bounding_rectangle_checkbox.isChecked())
        pass

    def createFormGroupBox(self):

        # DEFAULT_SWIM_WINDOW = float(0.8125)
        # DEFAULT_WHITENING = float(-0.6800)
        # DEFAULT_POLY_ORDER = int(0)
        # DEFAULT_NULL_BIAS = bool(False)
        # DEFAULT_BOUNDING_BOX = bool(True)

        '''Whitening Factor Field'''
        self.whitening_label = QLabel("Whitening:")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.setText(str(cfg.DEFAULT_WHITENING))
        self.whitening_input.setValidator(QDoubleValidator(-5.0000, 5.0000, 4, self))
        # what should validator be might be in docs
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        '''SWIM Window Field'''
        self.swim_label = QLabel("SWIM Window:")
        self.swim_input = QLineEdit(self)
        self.swim_input.setText(str(cfg.DEFAULT_SWIM_WINDOW))
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        '''Initial Rotation Field'''
        self.initial_rotation_label = QLabel("Initial Rotation:")
        self.initial_rotation_input = QLineEdit(self)
        self.initial_rotation_input.setText(str(cfg.DEFAULT_INITIAL_ROTATION))
        self.initial_rotation_input.setValidator(QDoubleValidator(0.0000, 5.0000, 4, self))
        self.initial_rotation_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        '''Initial Scale Field'''
        self.initial_scale_label = QLabel("Initial Rotation:")
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
        layout.addRow(self.whitening_label, self.whitening_input)
        layout.addRow(self.swim_label, self.swim_input)
        layout.addRow(self.initial_rotation_label, self.initial_rotation_input)
        layout.addRow(self.initial_scale_label, self.initial_scale_input)
        layout.addRow(self.bounding_rectangle_label, self.bounding_rectangle_checkbox)
        self.formGroupBox = QGroupBox('Configure Recipe')
        self.formGroupBox.setLayout(layout)

        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        self.whitening_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.whitening_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        self.swim_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.swim_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
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
