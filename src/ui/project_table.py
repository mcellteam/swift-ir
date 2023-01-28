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
from qtpy.QtGui import QImage, QFont, QColor, QPixmap, QPainter, QStandardItemModel

from src.ui.file_browser import FileBrowser
from src.helpers import absFilePaths, get_project_list, list_paths_absolute, get_bytes
from src.data_model import DataModel
from src.helpers import print_exception
from src.funcs_image import ImageSize

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
        self.table = QTableWidget()
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)
        self.table.setUpdatesEnabled(True)
        self.table.itemClicked.connect(self.userSelectionChanged)
        self.table.currentItemChanged.connect(self.userSelectionChanged)
        self.row_height_slider = Slider(self)
        # self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Fails on TACC for some reason
        self.INITIAL_ROW_HEIGHT = 100
        # self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
        self.initUI()

    # def onDoubleClick(self, item=None):
    #     print(type(item))
        # userSelectionChanged
        # cfg.main_window.open_project_selected()


    def set_column_headers(self):
        if cfg.data.is_aligned():
            labels = [ 'Img\nName','Index', 'Img', 'Reference', 'Aligned', 'Q0', 'Q1', 'Q2', 'Q3',
                       'Scale', 'Skip?', 'Method']
        else:
            labels = [ 'Img\nName','Index','Img', 'Reference', 'Scale', 'Skip?', 'Method' ]
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setColumnCount(len(labels))


    def setScaleData(self):

        self.setUpdatesEnabled(False)
        caller = inspect.stack()[1].function
        logger.info('Setting Table Data (caller: %s)...' % caller)
        self.table.clearContents()
        self.table.clear()
        self.table.setRowCount(0)
        self.updateSliderMaxVal()

        try:
            data = self.get_data()
        except:
            print_exception()
        try:
            if cfg.data.is_aligned():
                for i, row in enumerate(data):
                    self.table.insertRow(i)
                    snr_4x = cfg.data.snr_components(l=i)
                    for j, item in enumerate(row):
                        if j == (0, 1):
                            # lab = QLabel('<h3>' + '\n'.join(textwrap.wrap(item, 12)) + '</h3>')
                            lab = QLabel('\n'.join(textwrap.wrap(item, 22)))
                            lab.setWordWrap(True)
                            font = QFont()
                            font.setBold(True)
                            font.setPointSize(9)
                            lab.setFont(font)
                            self.table.setCellWidget(i, j, lab)
                        elif j in (2, 3, 4):
                            thumbnail = Thumbnail(self, path=item)
                            self.table.setCellWidget(i, j, thumbnail)
                        elif j in (5, 6, 7, 8):
                            logger.info(f'j={j}, item={str(item)}')
                            thumbnail = SnrThumbnail(self, path=item, label='%.3f' % snr_4x[j - 5])
                            self.table.setCellWidget(i, j, thumbnail)
                        else:
                            self.table.setItem(i, j, QTableWidgetItem(str(item)))
            else:
                for i, row in enumerate(data):
                    self.table.insertRow(i)
                    for j, item in enumerate(row):
                        if j in (2, 3):
                            thumbnail = Thumbnail(self, path=item)
                            self.table.setCellWidget(i, j, thumbnail)
                        else:
                            self.table.setItem(i, j, QTableWidgetItem(str(item)))
        except:
            print_exception()
        finally:
            self.setUpdatesEnabled(True)
            self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
            self.set_column_headers()
            self.table.update()



    def get_data(self):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:     is_aligned = cfg.data.is_aligned_and_generated()
        except:  is_aligned = False;  print_exception()
        try:     scale = [cfg.data.scale_pretty()] * cfg.data.nSections
        except:  scale = ['Unknown'] * cfg.data.nSections; print_exception()
        try:     ref = cfg.data.thumbnails_ref()
        except:  ref = ['Unknown'] * cfg.data.nSections; print_exception()
        indexes, skips, base, method, snr_report, test = [], [], [], [], [], []
        for i, l in enumerate(cfg.data.alstack()):
            indexes.append(i)
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
            zipped = list(zip(cfg.data.basefilenames(), indexes, cfg.data.thumbnails(), ref,
                              cfg.data.thumbnails_aligned(),
                              cfg.data.corr_spots_q0(), cfg.data.corr_spots_q1(),
                              cfg.data.corr_spots_q2(), cfg.data.corr_spots_q3(),
                              scale, skips, method, cfg.data.snr_list(), snr_report))
            self.table.setColumnWidth(0, 128)  # 0 index
            self.table.setColumnWidth(1, 40)  # 1 Filename
            self.table.setColumnWidth(2, 100) # 2 Current
            self.table.setColumnWidth(3, 100) # 1 Reference
            self.table.setColumnWidth(4, 100) # 2 Aligned
            self.table.setColumnWidth(5, 100) # 3 Q0
            self.table.setColumnWidth(6, 100) # 4 Q1
            self.table.setColumnWidth(7, 100) # 5 Q2
            self.table.setColumnWidth(8, 100) # 6 Q3
            self.table.setColumnWidth(9, 100) # 7 Scale
            self.table.setColumnWidth(0, 50)  # 8 Skip
            self.table.setColumnWidth(11, 50) # 9 Method
            self.table.setColumnWidth(12, 50) # 10 SNR
            self.table.setColumnWidth(13, 50) # 11 SNR_report
            # self.table.setColumnWidth(14, 80) # 12
            # self.table.resizeColumnToContents(9)

        else:
            zipped = list(zip(cfg.data.basefilenames(), indexes, cfg.data.thumbnails(),  ref, scale, skips, method))


            self.table.setColumnWidth(0, 128)
            self.table.setColumnWidth(1, 40)
            self.table.setColumnWidth(2, 100)
            self.table.setColumnWidth(3, 100)
            self.table.setColumnWidth(4, 50)
            self.table.setColumnWidth(5, 50)
            self.table.setColumnWidth(6, 80)
            # self.table.setColumnWidth(6, 80)

        return zipped


    def userSelectionChanged(self):
        caller = inspect.stack()[1].function
        row = self.table.currentIndex().row()
        cfg.data.set_layer(row)
        cfg.main_window.tell('Section #%d' % row)


    def updateTableDimensions(self, h):
        # logger.info(f'Updating table dimensions...')
        logger.info('')
        if h < 64:
            return
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table.setColumnWidth(2, h)
        self.table.setColumnWidth(3, h)
        if cfg.data.is_aligned_and_generated():
            self.table.setColumnWidth(2, h)
            self.table.setColumnWidth(3, h)
            self.table.setColumnWidth(4, h)
            self.table.setColumnWidth(5, h)
            self.table.setColumnWidth(6, h)
            self.table.setColumnWidth(7, h)
            self.table.setColumnWidth(8, h)
        # self.table.resizeColumnToContents()
        # self.table.resizeColumnToContents(9)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            logger.info('Click detected!')

    def eventFilter(self, obj, event):
        if event.type() == event.MouseMove:
            print('mouse moving')
        return super().eventFilter(obj, event)

    def updateSliderMaxVal(self):
        if cfg.data.is_aligned():
            thumb_path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'thumbnails_aligned')
        else:
            thumb_path = os.path.join(cfg.data.dest(), 'thumbnails')
        max_val = max(ImageSize(next(absFilePaths(thumb_path))))
        # self.row_height_slider.setMaximum(max_val)


    def initUI(self):
        logger.info('Initializing Table UI...')

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

        self.updateSliderMaxVal()
        self.row_height_slider.setValue(self.INITIAL_ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.updateTableDimensions)
        self.row_height_slider.setMaximumWidth(128)

        # self.row_height_slider.valueChanged.connect(self.updateFontSize)
        # self.row_height_widget = QWidget()
        # self.thumbnailPixelsLabel = QLabel()
        # self.row_height_hlayout = QHBoxLayout()
        # self.row_height_hlayout.setContentsMargins(2, 2, 2, 2)
        # self.row_height_hlayout.addWidget(QLabel('Thumbnail Size:'))
        # self.row_height_hlayout.addWidget(self.row_height_slider, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.row_height_hlayout.addWidget(self.thumbnailPixelsLabel, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.row_height_widget.setLayout(self.row_height_hlayout)

        logger.info('Initializing Table Controls...')

        self.controls = QWidget()
        self.controls.setObjectName('controls')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.row_height_slider, alignment=Qt.AlignLeft)
        # self.controls_hlayout.addWidget(self.font_size_widget)
        hbl.addStretch()
        self.controls.setLayout(hbl)

        logger.info('Initializing Table Layout...')

        layout =QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addWidget(self.controls)

        self.setLayout(layout)


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
    def __init__(self, parent):
        super().__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(16)
        self.setMaximum(512)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)

    def setMaximum(self, a0: int) -> None:
        self.setMaximum(a0)




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

