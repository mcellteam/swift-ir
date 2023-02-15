#!/usr/bin/env python3

import sys, logging
from math import floor
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QGroupBox, QFormLayout, QLabel, QScrollArea, \
    QVBoxLayout, QSizePolicy, QHBoxLayout, QGridLayout, QPushButton, QComboBox, QSpinBox, QStyleOption, QStyle
from qtpy.QtCore import Qt, QSize, QRect
from qtpy.QtGui import QPainter

__all__ = ['ControlPanel']

logger = logging.getLogger(__name__)

def makerows(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

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
        # self._controls = QWidget()

        self._items = list(items)
        if bg_color:
            self.addStyle(f' background-color: {bg_color};')
        # self.setLayoutGrid()
        self.updateStyle()

    def addWidgets(self, items):
        for item in items:
            self._appendWidget(item)
        # self.updateLayout()
        self.setLayoutGrid()

    def setWidgets(self, items):
        self._items = []
        self.addWidgets(items)

    def _appendWidget(self, item):
        self._items.append(item)

    def setLayoutRow(self, height=40):
        logger.info(f'Setting Row Layout for Control Panel ({len(self._items)} items)')
        # self._layout = QVBoxLayout()
        # self._layout.setContentsMargins(4, 0, 4, 0)
        # self._layout.setSpacing(2)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        self.setFixedHeight(height)
        for item in self._items:
            hbl.addWidget(item)
            hbl.addStretch(1)
        hbl.addStretch(5)
        # self._controls.setLayout(hbl)
        # self._layout.addWidget(self._title)
        # self._layout.addWidget(self._controls)
        # self.setLayout(self._layout)
        self.setLayout(hbl)

    def setLayoutGrid(self, columns, height=100):
        logger.info(f'Setting Grid Layout for Control Panel ({len(self._items)} items)')
        # self._layout = QVBoxLayout()
        # self._layout.setContentsMargins(4, 0, 4, 0)
        # self._layout.setSpacing(2)
        gl = QGridLayout()
        gl.setContentsMargins(4, 0, 4, 0)
        self.setFixedHeight(height)
        for i, item in enumerate(self._items):
            row = floor(i / columns)
            col = i % columns
            gl.addWidget(item, row, col, alignment=Qt.AlignmentFlag.AlignCenter)
        #     gl.addStretch(1)
        # gl.addStretch(5)
        # self._controls.setLayout(gl)
        # self._layout.addWidget(self._title)
        # self._layout.addWidget(self._controls)
        self.setLayout(gl)

    def setCustomLayout(self, layout):
        self.setLayout(layout)

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