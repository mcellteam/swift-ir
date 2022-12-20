#!/usr/bin/env python3

import warnings
from qtpy.QtWidgets import QLabel
from qtpy.QtGui import QPainter, QFont
from qtpy.QtCore import Qt, QSize, QRect

class VerticalLabel(QLabel):

    def __init__(self, text, *args):
        QLabel.__init__(self, text, *args)

        self.text = text
        # self.setStyleSheet("font-size: 10px;")
        self.setStyleSheet("font-size: 10px; color: #1B1E23")
        font = QFont()
        font.setBold(True)
        self.setFont(font)

    def paintEvent(self, event):
        # QLabel.paintEvent(self, event)
        # p = QPainter(self)
        # p.rotate(-90)
        # p.translate(0, self.height()-1)
        # self.setGeometry(self.x(), self.y(), self.height(), self.width())
        # QLabel.render(self, p)

        p = QPainter(self)
        p.rotate(-90)
        rgn = QRect(-self.height(), 0, self.height(), self.width())
        # align = self.alignment()
        # align  = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter
        align  = Qt.AlignmentFlag.AlignHCenter
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.hint = p.drawText(rgn, align, self.text)
        p.end()

        self.setMaximumWidth(self.hint.height())
        self.setMinimumHeight(self.hint.width())


    def sizeHint(self):
        if hasattr(self, 'hint'):
            return QSize(self.hint.height(), self.hint.width())
        else:
            return QSize(16, 48)


    def minimumSizeHint(self):
        size = QLabel.minimumSizeHint(self)
        return QSize(size.height(), size.width())



