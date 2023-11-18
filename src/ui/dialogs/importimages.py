#!/usr/bin/env python3

import logging

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from src.utils.funcs_image import ImageSize

__all__ = ['ImportImagesDialog']

logger = logging.getLogger(__name__)


class ImportImagesDialog(QFileDialog):
    def __init__(self, *args, **kwargs):
        QFileDialog.__init__(self, *args, **kwargs)
        logger.info('')
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setNameFilter('Images (*.tif *.tiff)')
        self.setFileMode(QFileDialog.ExistingFiles)
        self.setModal(True)
        urls = self.sidebarUrls()
        self.setSidebarUrls(urls)
        self.mpPreview = QLabel("Preview", self)
        self.mpPreview.setMinimumSize(256, 256)
        self.mpPreview.setAlignment(Qt.AlignCenter)
        self.mpPreview.setObjectName("labelPreview")
        self.mpPreview.setText('Preview')
        self.mpPreview.setAutoFillBackground(True)
        self.mpPreview.setStyleSheet("background-color: #dadada;")
        self.imageDimensionsLabel = QLabel('')
        self.imageDimensionsLabel.setMaximumHeight(16)
        self.imageDimensionsLabel.setStyleSheet("""
            font-size: 12px; 
            color: #141414; 
            padding: 2px;
        """)
        # self.cb_cal_grid = QCheckBox('Image 0 is calibration grid')
        # self.cb_cal_grid.setChecked(False)

        self.cb_display_thumbs = QCheckBox('Display Thumbnails')
        self.cb_display_thumbs.setChecked(True)
        self.cb_display_thumbs.toggled.connect(self.onToggle)

        # self.cb_overwrite = QCheckBox('Overwrite')
        # self.cb_overwrite.setChecked(False)

        self.box = QVBoxLayout()
        self.box.addWidget(self.mpPreview)
        self.box.addStretch()
        # box.addWidget(self.imageDimensionsLabel)
        self.extra_layout = QVBoxLayout()
        self.extra_layout.addWidget(self.imageDimensionsLabel, alignment=Qt.AlignRight)
        self.extra_layout.addWidget(self.cb_display_thumbs, alignment=Qt.AlignRight)
        # self.extra_layout.addWidget(self.cbCalGrid, alignment=Qt.AlignRight)
        self.layout().addLayout(self.box, 1, 3, 1, 1)
        self.layout().addLayout(self.extra_layout, 3, 3, 1, 1)
        # self.layout().addLayout(HBL(self.cb_cal_grid), 4, 0, 1, 3)
        self.layout().setContentsMargins(2, 2, 2, 2)
        self.layout().setHorizontalSpacing(2)
        self.layout().setVerticalSpacing(0)
        self.currentChanged.connect(self.onChange)
        # self.fileSelected.connect(self.onFileSelected)
        # self.filesSelected.connect(self.onFilesSelected)
        # self._fileSelected = None
        # self._filesSelected = None
        # self.pixmap = None
        self.pixmap = QPixmap()
        # self.pixmap = ThumbnailFast(self).pixmap()
        self.setStyleSheet("font-size: 10px;")

    def onToggle(self):
        if self.cb_display_thumbs.isChecked():
            self.imageDimensionsLabel.show()
            self.mpPreview.show()
        else:
            self.imageDimensionsLabel.hide()
            self.mpPreview.hide()

    def onChange(self, path):
        # logger.info('')
        self.pixmap = QPixmap(path)
        if (self.pixmap.isNull()):
            self.imageDimensionsLabel.setText('')
        elif self.cb_display_thumbs.isChecked():
            self.mpPreview.setPixmap(self.pixmap.scaled(self.mpPreview.width(),
                                                        self.mpPreview.height(),
                                                        Qt.KeepAspectRatio,
                                                        Qt.SmoothTransformation))
            logger.info(f'Selected: {path}')
            # siz = ImageSize(file_path)
            # self.imageDimensionsLabel.setText('Size: %dx%dpx' %(siz[0], siz[1]))
            self.imageDimensionsLabel.setText('Size: %dx%dpx' % ImageSize(path))
            self.imageDimensionsLabel.show()

    # def onFileSelected(self, file):
    #     self._fileSelected = file
    #
    #
    # def onFilesSelected(self, files):
    #     self._filesSelected = files
    #
    #
    # def getFileSelected(self):
    #     return self._fileSelected
    #
    #
    # def getFilesSelected(self):
    #     return self._filesSelected



