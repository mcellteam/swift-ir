#!/usr/bin/env python3

import logging

from qtpy.QtCore import *
from qtpy.QtWidgets import *
from src.ui.layouts.layouts import HBL
from src.utils.helpers import hotkey

__all__ = ['ExitAppDialog']

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
        self.cancelButton.setFixedSize(QSize(80, 20))
        self.saveExitButton = QPushButton('Save && Quit')
        self.saveExitButton.setStyleSheet("QPushButton{font-size: 10pt; font-weight: 500;}")
        self.saveExitButton.setFixedSize(QSize(80, 20))
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
            self.exitExitButton.setFixedSize(QSize(130, 20))
        else:
            self.message = 'Exit Align-EM-SWiFT?'
            self.exitExitButton.setText(f"Quit {hotkey('Q')}")
            self.exitExitButton.setText(f"Quit {hotkey('Q')}")
            self.exitExitButton.setFixedSize(QSize(80, 20))

        self.layout = HBL(_Expand(self), QLabel(self.message), self.cancelButton, self.saveExitButton, self.exitExitButton)
        self.layout.setSpacing(4)
        self.setContentsMargins(8, 0, 8, 0)
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


class _Expand(QWidget):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)