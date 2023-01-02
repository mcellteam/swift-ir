#!/usr/bin/env python3

import sys, logging
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QGroupBox, QFormLayout, QLabel, QScrollArea, \
    QVBoxLayout, QSizePolicy
from qtpy.QtCore import Qt, QSize, QRect

logger = logging.getLogger(__name__)

class WidgetArea(QWidget):

    def __init__(self,
                 parent=None,
                 name=None,
                 title=None,
                 labels=(),
                 *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        self.parent=parent
        self.name = name
        self.setObjectName(('defaultWidgetArea', name)[isinstance(name, str)])
        self._title = QLabel(('Widget Area', title)[isinstance(title, str)])
        self._title.setObjectName('cp_title')
        self._title.setStyleSheet('font-size: 10px; font-weight: 750;')

        self._labels = list(labels)
        self._style = ''
        self.addStyle(f'QLabel#title{{font-size: 10px; font-weight: 750;}}')
        self.updateLayout()
        self.updateStyle()

        self.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.MinimumExpanding
        )

    def addLabels(self, items):
        for item in items:
            self._appendLabel(item)
        self.updateLayout()

    def setLabels(self, items, names=None):
        self._labels = []
        self.addLabels(items)

    def _appendLabel(self, item):
        self._labels.append(item)

    def updateLayout(self):
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)
        self._form = QFormLayout()
        # self._gb = QGroupBox('AlignEM-SWiFT')
        self._gb = QGroupBox()
        self._gb.setLayout(self._form)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._gb)
        self._scroll.setWidgetResizable(True)
        self._layout.addWidget(self._title)
        self._layout.addWidget(self._scroll)
        for lb in self._labels:
            self._form.addRow(lb)
        self.setLayout(self._layout)

    def addStyle(self, style:str):
        self._style += style

    def updateStyle(self):
        self.setStyleSheet(self._style)

    def sizeHint(self):
        return QSize(80,50)


if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    w = WidgetArea()
    main_window.setCentralWidget(w)
    main_window.show()
    sys.exit(app.exec_())
