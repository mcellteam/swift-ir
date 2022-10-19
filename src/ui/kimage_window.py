#!/usr/bin/env python3

import os
from qtpy.QtWidgets import QWidget, QLabel, QVBoxLayout
from qtpy.QtGui import QPixmap
import src.config as cfg

class KImageWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        proj_dir = os.path.abspath(cfg.data['data']['destination_path'])
        path = os.path.join(proj_dir, cfg.data.scale(), 'k_img.tif')
        self.lb = QLabel(self)
        self.pixmap = QPixmap(path)
        # lb.resize(self.width(), 100)
        # lb.setPixmap(pixmap.scaled(lb.size(), Qt.IgnoreAspectRatio))
        self.lb.setPixmap(self.pixmap)
        self.lb.resize(self.pixmap.width(), self.pixmap.height())
        layout = QVBoxLayout()
        self.label = QLabel()
        layout.addWidget(self.label)
        self.setLayout(layout)