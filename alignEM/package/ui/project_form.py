#!/usr/bin/env python3

import os, sys, copy, json, inspect, collections, multiprocessing, logging, textwrap, psutil, operator, platform, \
    code, readline
from qtpy.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QGroupBox, \
    QHBoxLayout, QLabel, QLineEdit, QMenu, QMenuBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QFormLayout, \
    QCheckBox
from qtpy.QtCore import Qt
from qtpy.QtGui import QDoubleValidator

__all__ = ['ProjectForm']


class ProjectForm(QDialog):
    NumGridRows = 3
    NumButtons = 4

    def __init__(self):
        super(ProjectForm, self).__init__()
        self.createFormGroupBox()

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.setWindowTitle("Project Form")

    def createFormGroupBox(self):
        self.whitening_label = QLabel("Whitening:")
        self.whitening_input = QLineEdit(self)
        self.whitening_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whitening_input.setText("-0.68")
        self.whitening_input.setValidator(QDoubleValidator(-5.0, 5.0, 2, self))

        self.swim_label = QLabel("SWIM Window:")
        self.swim_input = QLineEdit(self)
        self.swim_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swim_input.setText("0.8125")
        self.swim_input.setValidator(QDoubleValidator(0.0000, 1.0000, 4, self))

        self.formGroupBox = QGroupBox("Form Groupbox")
        layout = QFormLayout()
        layout.addRow(self.whitening_label, QLineEdit())
        layout.addRow(self.swim_label, QComboBox())
        layout.addRow(QLabel("Bounding Box"), QCheckBox())

        # Whitening LineEdit

        # self.whitening_label.setFont(QFont('Terminus', 12, QFont.Bold))
        tip = "Whitening factor used for Signal Whitening Fourier Transform Image Registration (default=-0.68)"
        self.whitening_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.whitening_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        # self.swim_label.setFont(QFont('Terminus', 12, QFont.Bold))
        tip = "SWIM window used for Signal Whitening Fourier Transform Image Registration (default=0.8125)"
        self.swim_label.setToolTip("\n".join(textwrap.wrap(tip, width=35)))
        self.swim_input.setToolTip("\n".join(textwrap.wrap(tip, width=35)))



        self.formGroupBox.setLayout(layout)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = ProjectForm()
    sys.exit(dialog.exec_())

