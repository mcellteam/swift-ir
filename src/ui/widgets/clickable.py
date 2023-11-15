#!/usr/bin/env python3

'''https://stackoverflow.com/questions/2711033/how-code-a-image-button-in-pyqt'''

import logging
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPainter, QPixmap
from qtpy.QtWidgets import QLabel, QAbstractButton

logger = logging.getLogger(__name__)

class ClickablePicButton(QAbstractButton):
    # clicked = Signal()
    def __init__(self, pixmap, parent=None):
        super(ClickablePicButton, self).__init__(parent)
        self.pixmap = pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(event.rect(), self.pixmap)

    def sizeHint(self):
        return self.pixmap.size()

class ClickableLabel(QLabel):
    clicked = Signal()
    def mouseReleaseEvent(self, event):
        super(ClickableLabel, self).mouseReleaseEvent(self, event)
        if event.button() == Qt.LeftButton and event.pos() in self.rect():
            self.clicked.emit()

    def paintEvent(self, e):
        super().paintEvent(e)
        qp = QPainter(self)
        qp.drawPixmap(100, 100, QPixmap("resources/button_ng.png"))

