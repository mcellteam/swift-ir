#!/usr/bin/env python3

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter, QLabel, QPushButton, QFrame

__all__ = ['HBL', 'VBL', 'GL', 'HW', 'VW', 'HSplitter', 'VSplitter', 'YellowTextLabel', 'QVLine', 'QHLine']


# class L(QLabel):
#     def __init__(self):
#         super().__init__()
#         self.layout = QHBoxLayout()
#         self.setLayout(self.layout)


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


class HW(QWidget):
    def __init__(self, *args, spacing=0):
        super().__init__()
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        # self.layout.setSpacing(2)
        self.layout.setSpacing(spacing)
        self.setLayout(self.layout)
        for w in args:
            self.layout.addWidget(w)

    def addWidget(self, w):
        self.layout.addWidget(w)


class VW(QWidget):
    def __init__(self, *args, spacing=0):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        # self.layout.setSpacing(2)
        self.layout.setSpacing(spacing)
        self.setLayout(self.layout)
        for w in args:
            self.layout.addWidget(w)

    def addWidget(self, w):
        self.layout.addWidget(w)

    def addLayout(self, l):
        self.layout.addLayout(l)


class HSplitter(QSplitter):
    def __init__(self, *args):
        super().__init__(Qt.Orientation.Horizontal)
        self.setHandleWidth(4)
        for w in args:
            self.addWidget(w)


class VSplitter(QSplitter):
    def __init__(self, *args):
        super().__init__(Qt.Orientation.Vertical)
        self.setHandleWidth(4)
        for w in args:
            self.addWidget(w)

class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class QVLine(QFrame):
    def __init__(self):
        super(QVLine, self).__init__()
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)


class YellowTextLabel(QLabel):
    clicked = Signal()
    def __init__(self, *args):
        super().__init__(*args)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""color: #ffe135; background-color: rgba(0,0,0,.35); 
            font-weight: 600; text-align: center; padding: 3px; font-size: 12px;""")

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

