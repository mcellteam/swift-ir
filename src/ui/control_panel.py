#!/usr/bin/env python3

import sys, logging
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QGroupBox, QFormLayout, QLabel, QScrollArea, \
    QVBoxLayout, QSizePolicy, QHBoxLayout, QPushButton, QComboBox, QSpinBox, QStyleOption, QStyle
from qtpy.QtCore import Qt, QSize, QRect
from qtpy.QtGui import QPainter

logger = logging.getLogger(__name__)

class ControlPanel(QWidget):

    def __init__(self,
                 parent=None,
                 name=None,
                 title=None,
                 items=(),
                 color=None,
                 bg_color=None,
                 *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        logger.info('')
        self.parent=parent
        self._style = ''
        self.name = name
        self.setObjectName(('defaultControlPanel', name)[isinstance(name, str)])
        self._title = QLabel(('Control Panel', title)[isinstance(title, str)])
        self._title.setObjectName('cp_title')
        self._title.setStyleSheet('font-size: 10px; font-weight: 550;')

        self._items = list(items)
        if bg_color:
            self.addStyle(f' background-color: {bg_color};')
        self.updateLayout()
        self.updateStyle()

    def addWidgets(self, items):
        for item in items:
            self._appendWidget(item)
        self.updateLayout()

    def setWidgets(self, items):
        self._items = []
        self.addWidgets(items)

    def _appendWidget(self, item):
        self._items.append(item)

    def updateLayout(self):
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(4, 0, 4, 0)
        # self._layout.setSpacing(2)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        self.setFixedHeight(40)
        hbl.addStretch()
        for item in self._items:
            hbl.addWidget(item)
        hbl.addStretch()
        self._controls = QWidget()
        self._controls.setLayout(hbl)
        # self._layout.addWidget(self._title)
        self._layout.addWidget(self._controls)
        self.setLayout(self._layout)

    def addStyle(self, style:str):
        self._style += style

    def updateStyle(self):
        self.setStyleSheet(self._style)

    def paintEvent(self, pe):
        '''Enables widget to be style-ized'''
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        s = self.style()
        s.drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def sizeHint(self):
        return QSize(1000,20)


if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    w = [
        QPushButton("Demo 1"),
        QComboBox(),
        QSpinBox()
    ]
    w = ControlPanel(items=w)
    main_window.setCentralWidget(w)
    main_window.show()
    sys.exit(app.exec_())