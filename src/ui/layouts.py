#!/usr/bin/env python3

import inspect
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter, QLabel, QPushButton
from qtpy.QtCore import Qt, Signal

__all__ = ['HBL', 'VBL', 'GL', 'HWidget', 'VWidget', 'HSplitter', 'VSplitter', 'YellowTextLabel']

class HBL(QHBoxLayout):
    def __init__(self, *args):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(2)
        for w in args:
            self.addWidget(w)


class VBL(QVBoxLayout):
    def __init__(self, *args):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(2)
        for w in args:
            self.addWidget(w)


class GL(QGridLayout):
    def __init__(self):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)


class HWidget(QWidget):
    def __init__(self, *args):
        super().__init__()
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)
        for w in args:
            self.layout.addWidget(w)

    def addWidget(self, w):
        self.layout.addWidget(w)


class VWidget(QWidget):
    def __init__(self, *args):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        # self.layout.setSpacing(2)
        self.layout.setSpacing(0)
        self.setLayout(self.layout)
        for w in args:
            self.layout.addWidget(w)

    def addWidget(self, w):
        self.layout.addWidget(w)


class HSplitter(QSplitter):
    def __init__(self, *args):
        super().__init__(Qt.Orientation.Horizontal)
        self.setHandleWidth(2)
        for w in args:
            self.addWidget(w)


class VSplitter(QSplitter):
    def __init__(self, *args):
        super().__init__(Qt.Orientation.Vertical)
        self.setHandleWidth(2)
        for w in args:
            self.addWidget(w)


class YellowTextLabel(QLabel):
    clicked = Signal()
    def __init__(self, *args):
        super().__init__(*args)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""color: #ffe135; background-color: rgba(0,0,0,.35); 
            font-weight: 600; text-align: center; padding: 3px;""")

    def mousePressEvent(self, ev):
        self.clicked.emit()

class Button(QPushButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setFixedHeight(18)

class SmallButton(QPushButton):
    def __init__(self, *args):
        super().__init__(*args)
        self.setFixedHeight(18)
        self.setFixedWidth(48)

