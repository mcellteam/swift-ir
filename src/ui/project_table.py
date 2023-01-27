#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QStyledItemDelegate, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QSlider, QAbstractScrollArea, \
    QHeaderView
from qtpy.QtCore import Qt, QAbstractTableModel, QRect
from qtpy.QtGui import QImage, QFont, QColor, QPixmap, QPainter

from src.ui.file_browser import FileBrowser
from src.helpers import get_project_list, list_paths_absolute, get_bytes
from src.data_model import DataModel
from src.helpers import print_exception

import src.config as cfg

logger = logging.getLogger(__name__)

'''
cfg.project_tab.project_table.updateTableDimensions(100)
'''


class ProjectTable(QWidget):
    def __init__(self, parent=None):
        # super().__init__(parent)
        super().__init__(parent)
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        # self.table = QTableWidget() #0126-
        self.table = QTableWidget()
        self.table.setUpdatesEnabled(True)
        self.table.itemClicked.connect(self.userSelectionChanged)
        self.table.currentItemChanged.connect(self.userSelectionChanged)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.INITIAL_ROW_HEIGHT = 100
        self.row_height_slider = Slider(self, min=30, max=256)
        self.row_height_slider.setValue(self.INITIAL_ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.updateTableDimensions)
        self.row_height_slider.setMaximumWidth(128)
        # self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
        self.initUI()

    def set_column_headers(self):
        if cfg.data.is_aligned():
            labels = [ 'Img', 'Reference', 'Aligned', 'Q0', 'Q1', 'Q2', 'Q3',
                       'Scale', 'Skip?', 'Method', 'SNR Report' ]
        else:
            labels = [ 'Img', 'Reference', 'Scale', 'Skip?', 'Method' ]
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setColumnCount(len(labels))


    def setScaleData(self):
        logger.info('Setting Table Data...')
        self.setUpdatesEnabled(False)
        caller = inspect.stack()[1].function
        self.table.clearContents()
        # self.table.clear()
        self.table.setRowCount(0)

        data = self.get_data()
        if cfg.data.is_aligned():
            for i, row in enumerate(data):
                self.table.insertRow(i)
                snr_4x = cfg.data.all_snr(l=i)
                for j, item in enumerate(row):
                    if (j <= 2):
                        thumbnail = Thumbnail(self, path=item)
                        self.table.setCellWidget(i, j, thumbnail)
                    elif (2 < j < 7):
                        thumbnail = SnrThumbnail(self, path=item, label='%.3f' % snr_4x[j - 3])
                        self.table.setCellWidget(i, j, thumbnail)
                    else:
                        self.table.setItem(i, j, QTableWidgetItem(str(item)))
        else:
            for i, row in enumerate(data):
                self.table.insertRow(i)
                for j, item in enumerate(row):
                    if (j < 2):
                        thumbnail = Thumbnail(self, path=item)
                        self.table.setCellWidget(i, j, thumbnail)
                    else:
                        self.table.setItem(i, j, QTableWidgetItem(str(item)))

        self.set_column_headers()
        self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
        self.setUpdatesEnabled(True)
        self.table.repaint()


    def get_data(self):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:     is_aligned = cfg.data.is_aligned_and_generated()
        except:  is_aligned = False;  print_exception()
        try:     scale = [cfg.data.scale_pretty()] * cfg.data.nSections
        except:  scale = ['Unknown'] * cfg.data.nSections; print_exception()
        try:     ref = cfg.data.thumbnails_ref()
        except:  ref = ['Unknown'] * cfg.data.nSections; print_exception()
        skips, base, method, snr_report, test = [], [], [], [], []
        for l in cfg.data.alstack():
            try:     skips.append(l['skipped'])
            except:  skips.append('?'); print_exception()
            try:
                m = l['align_to_ref_method']['selected_method']
                if m == 'Auto Swim Align': m = 'Automatic SWIM Alignment'
                method.append(m)
            except:
                method.append('Unknown')
            if is_aligned:
                try:     snr_report.append(l['align_to_ref_method']['method_results']['snr_report'])
                except:  snr_report.append('<No SNR Report>')

        if is_aligned:
            zipped = list(zip(cfg.data.thumbnails(), ref,
                              cfg.data.thumbnails_aligned(),
                              cfg.data.corr_spots_q0(), cfg.data.corr_spots_q1(),
                              cfg.data.corr_spots_q2(), cfg.data.corr_spots_q3(),
                              scale, skips, method, snr_report))
            self.table.setColumnWidth(1, 100)
            self.table.setColumnWidth(2, 100) # 0 Current
            self.table.setColumnWidth(3, 100) # 1 Reference
            self.table.setColumnWidth(4, 100) # 2 Aligned
            self.table.setColumnWidth(5, 100) # 3 Q0
            self.table.setColumnWidth(6, 100) # 4 Q1
            self.table.setColumnWidth(7, 100) # 5 Q2
            self.table.setColumnWidth(8, 100) # 6 Q3
            self.table.setColumnWidth(9, 60)  # 7 Scale
            self.table.setColumnWidth(10, 60) # 8 Skip
            self.table.setColumnWidth(11, 80) # 9 Method
            # self.table.resizeColumnToContents(9)

        else:
            zipped = list(zip(cfg.data.thumbnails(),  ref, scale, skips, method))
            self.table.setColumnWidth(0, 100)
            self.table.setColumnWidth(1, 100) # 0
            self.table.setColumnWidth(2, 60) # 1
            self.table.setColumnWidth(3, 60)  # 2 Scale
            self.table.setColumnWidth(4, 80)  # 3 Skip
            # self.table.setColumnWidth(6, 80)  # 4 Method
            self.table.resizeColumnToContents(4)

        return zipped


    def userSelectionChanged(self):
        caller = inspect.stack()[1].function
        row = self.table.currentIndex().row()
        cfg.data.set_layer(row)
        cfg.main_window.tell('Section #%d' % row)


    def updateTableDimensions(self, h):
        # logger.info(f'Updating table dimensions...')
        if h < 64:
            return
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table.setColumnWidth(0, h)
        self.table.setColumnWidth(1, h)
        if cfg.data.is_aligned_and_generated():
            self.table.setColumnWidth(2, h)
            self.table.setColumnWidth(3, h)
            self.table.setColumnWidth(4, h)
            self.table.setColumnWidth(5, h)
            self.table.setColumnWidth(6, h)
        self.table.resizeColumnToContents(7)
        self.table.resizeColumnToContents(8)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            logger.info('Click detected!')

    def eventFilter(self, obj, event):
        if event.type() == event.MouseMove:
            print('mouse moving')
        return super().eventFilter(obj, event)

    def initUI(self):

        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # self.project_table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setTextElideMode(Qt.ElideMiddle)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)

        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        # self.row_height_slider.valueChanged.connect(self.updateFontSize)
        self.row_height_widget = QWidget()
        self.thumbnailPixelsLabel = QLabel()
        self.row_height_hlayout = QHBoxLayout()
        self.row_height_hlayout.setContentsMargins(2, 2, 2, 2)
        self.row_height_widget.setLayout(self.row_height_hlayout)
        self.row_height_hlayout.addWidget(QLabel('Thumbnail Size:'))
        self.row_height_hlayout.addWidget(self.row_height_slider, alignment=Qt.AlignmentFlag.AlignLeft)
        self.row_height_hlayout.addWidget(self.thumbnailPixelsLabel, alignment=Qt.AlignmentFlag.AlignLeft)

        self.controls = QWidget()
        self.controls.setObjectName('controls')
        self.controls_hlayout = QHBoxLayout()
        self.controls_hlayout.setContentsMargins(0, 0, 0, 0)
        self.controls_hlayout.addWidget(self.row_height_widget)
        # self.controls_hlayout.addWidget(self.font_size_widget)
        self.controls_hlayout.addStretch()
        self.controls.setLayout(self.controls_hlayout)
        self.layout.addWidget(self.table, 0, 0)
        self.layout.addWidget(self.controls, 1, 0)


class SnrThumbnail(QWidget):

    def __init__(self, parent, path, label='<SNR>'):
        super().__init__(parent)
        # thumbnail = QLabel(self)
        thumbnail = ScaledPixmapLabel(self)
        try:
            pixmap = QPixmap(path)
            thumbnail.setPixmap(pixmap)
            thumbnail.setScaledContents(True)
            label = QLabel(label)
            label.setStyleSheet('color: #ff0000')
        except:
            label = QLabel(label)
            label.setStyleSheet('background-color: #141414')
            print_exception()
            logger.warning(f'WARNING path={path}, label={label}')
        layout = QGridLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(thumbnail, 0, 0)
        layout.addWidget(label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.setLayout(layout)


class Thumbnail(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        self.thumbnail = ScaledPixmapLabel(self)
        self.pixmap = QPixmap(path)
        self.thumbnail.setPixmap(self.pixmap)
        self.thumbnail.setScaledContents(True)
        self.layout = QGridLayout()
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.addWidget(self.thumbnail, 0, 0)
        self.setLayout(self.layout)


class ScaledPixmapLabel(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setScaledContents(True)

    def paintEvent(self, event):
        if self.pixmap():
            pm = self.pixmap()
            try:
                originalRatio = pm.width() / pm.height()
                currentRatio = self.width() / self.height()
                if originalRatio != currentRatio:
                    qp = QPainter(self)
                    pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    rect = QRect(0, 0, pm.width(), pm.height())
                    rect.moveCenter(self.rect().center())
                    qp.drawPixmap(rect, pm)
                    return
            except ZeroDivisionError:
                # logger.warning('Cannot divide by zero')
                # print_exception()
                pass
        super().paintEvent(event)


class Slider(QSlider):
    def __init__(self, parent, min, max):
        super().__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(min)
        self.setMaximum(max)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)



# class ThumbnailDelegate(QStyledItemDelegate):
#
#     def paint(self, painter, option, index):
#         data = index.model().data(index, Qt.DisplayRole)
#         if data is None:
#             return
#         thumbnail = QImage(data)
#         width = option.rect.width()
#         height = option.rect.height()
#         scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
#         painter.drawImage(option.rect.x(), option.rect.y(), scaled)

# class CorrSpotDelegate(QStyledItemDelegate):
#
#     def paint(self, painter, option, index):
#
#         data = index.model().data(index, Qt.DisplayRole)
#         if data is None:
#             return
#
#         cfg.a = index.model().data
#         cfg.b = index.model().itemData
#         cfg.i = index
#         # cfg.i.data()  # !!! This gives the path
#         cfg.d = data
#         thumbnail = QImage(data)
#         width = option.rect.width()
#         height = option.rect.height()
#         scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
#         painter.drawImage(option.rect.x(), option.rect.y(), scaled)
#         painter.setPen(QColor('#FF0000'))
#         if cfg.data.is_aligned_and_generated():
#             painter.drawText(option.rect.x(), option.rect.y() - 5, '<SNR>')


# class TableModel(QAbstractTableModel):
#     def __init__(self, data):
#         super().__init__()
#         self._data = data
#
#     def data(self, index, role):
#         if role == Qt.DisplayRole:
#             return self._data[index.row()][index.column()]
#
#     def rowCount(self, parent=None):
#         return len(self._data)
#
#     def columnCount(self, parent=None):
#         return len(self._data[0])

