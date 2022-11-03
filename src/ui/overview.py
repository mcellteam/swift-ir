#!/usr/bin/env python3

import os
import sys
import glob
import math
import logging
from collections import namedtuple

from qtpy.QtGui import QImage, QPixmap
from qtpy.QtWidgets import QWidget, QTableView

import src.config as cfg
from src.helpers import get_scale_val, do_scales_exist
from src.ui.table_models import PreviewDelegate, PreviewModel

logger = logging.getLogger(__name__)

# Create a custom namedtuple class to hold our data.
preview = namedtuple("preview", "id title image")

class OverviewWidget(QWidget):
    def __init__(self, destination=None):
        super().__init__()
        if destination == None:
            self.destination = cfg.data.dest()
        else:
            self.destination = destination

        self.thumbsdir = os.path.join(self.destination, 'thumbnails')

        self.view = QTableView()
        # self.view.horizontalHeader().hide()
        # self.view.verticalHeader().hide()
        # self.view.setGridStyle(Qt.NoPen)

        delegate = PreviewDelegate()
        self.view.setItemDelegate(delegate)
        self.model = PreviewModel()
        self.view.setModel(self.model)

        # self.setCentralWidget(self.view)

        # Add a bunch of images.
        for n, fn in enumerate(glob.glob(self.thumbsdir + "/*.tif")):
            # NOTE: This assumes that only .tif files are supported
            image = QImage(fn)
            item = preview(n, fn, image)
            self.model.previews.append(item)
        self.model.layoutChanged.emit()

        self.view.resizeRowsToContents()
        self.view.resizeColumnsToContents()

