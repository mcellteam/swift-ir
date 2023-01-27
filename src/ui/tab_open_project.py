#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QAbstractItemView, \
    QStyledItemDelegate, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QSlider, QGridLayout, QHeaderView, \
    QFrame
from qtpy.QtCore import Qt, QAbstractTableModel, QPoint, QRect
from qtpy.QtGui import QImage, QFont, QPixmap, QPainter

from src.ui.file_browser import FileBrowser
from src.helpers import get_project_list, list_paths_absolute, get_bytes
from src.data_model import DataModel

import src.config as cfg

logger = logging.getLogger(__name__)

ROW_HEIGHT = 60


class OpenProject(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setMinimumHeight(200)
        self.filebrowser = FileBrowser(parent=self)
        self.filebrowser.controlsNavigation.show()
        self.user_projects = UserProjects()
        self.row_height_slider = Slider(min=30, max=256)
        self.row_height_slider.setValue(ROW_HEIGHT)
        self.row_height_slider.setMaximumWidth(128)
        self.row_height_slider.valueChanged.connect(self.user_projects.updateRowHeight)
        self.initUI()

    def initUI(self):
        # User Projects Widget
        self.userProjectsWidget = QWidget()
        lab = QLabel('<h3>User Projects:</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(2, 2, 2, 2)
        vbl.addWidget(lab)
        vbl.addWidget(self.user_projects)
        self.userProjectsWidget.setLayout(vbl)

        # User Files Widget
        self.userFilesWidget = QWidget()
        lab = QLabel('<h3>Import Project:</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(2, 2, 2, 2)
        vbl.addWidget(lab)
        vbl.addWidget(self.filebrowser)
        self.userFilesWidget.setLayout(vbl)

        self._splitter = QSplitter()
        self._splitter.addWidget(self.userProjectsWidget)
        self._splitter.addWidget(self.userFilesWidget)
        self._splitter.setSizes([650, 350])

        controls = QWidget()
        controls.setFixedHeight(18)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 0, 4, 0)
        hbl.addWidget(self.row_height_slider,alignment=Qt.AlignmentFlag.AlignLeft)
        controls.setLayout(hbl)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self._splitter)
        self.layout.addWidget(controls)
        self.setLayout(self.layout)

        self.user_projects.set_data()


class UserProjects(QWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.counter1 = 0
        self.counter2 = 0
        # self.counter3 = 0
        self.setFocusPolicy(Qt.StrongFocus)

        self.table = QTableWidget()
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setTextElideMode(Qt.ElideMiddle)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)

        self.table.itemClicked.connect(self.userSelectionChanged)
        self.table.itemClicked.connect(self.countItemClickedCalls)
        self.table.currentItemChanged.connect(self.userSelectionChanged)
        self.table.currentItemChanged.connect(self.countCurrentItemChangedCalls)
        # self.table.itemChanged.connect(self.userSelectionChanged)
        # self.table.itemChanged.connect(self.countItemChangedCalls)s
        # self.table.itemChanged.connect(lambda: print('itemChanged!'))

        # self.project_table.setStyleSheet("border-radius: 12px")
        self.table.setColumnCount(10)
        self.set_headers()
        # self.set_data() # This is now called from _onGlobTabChange
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)

    def countItemClickedCalls(self):
        logger.info('')
        self.counter1 += 1

    def countCurrentItemChangedCalls(self):
        logger.info('')
        self.counter2 += 1

    # def countItemChangedCalls(self):
    #     logger.info('')
    #     self.counter3 += 1

    def updateRowHeight(self, h):
        logger.info(f'h = {h}')
        # if h < 64:
        #     return
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table.setColumnWidth(5, h)
        self.table.setColumnWidth(6, h)

        # header = self.table.horizontalHeader()
        # header.setSectionResizeMode(5, QHeaderView.Stretch)
        # header.setSectionResizeMode(6, QHeaderView.ResizeToContents)


    def set_headers(self):
        self.table.setHorizontalHeaderLabels([
            "Name",
            "Created",
            "Last\nOpened",
            "#\nImgs",
            "Image\nSize (px)",
            "First\nThumbnail",
            "Last\nThumbnail",
            "Disk Space\n(Bytes)",
            "Disk Space\n(Gigabytes)",
            "Location"])

        header = self.table.horizontalHeader()
        # self.header.setFrameStyle(QFrame.Box | QFrame.Plain)
        header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
        self.table.setHorizontalHeader(header)

    def set_data(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        self.table.clearContents()
        # self.set_column_headers()
        data = self.get_data()
        self.table.setRowCount(0)
        for i, row in enumerate(data):
            self.table.insertRow(i)
            for j, item in enumerate(row):
                # logger.info(f'item: {item}')
                if j == 0:
                    # lab = QLabel('<h3>' + '\n'.join(textwrap.wrap(item, 12)) + '</h3>')
                    lab = QLabel('\n'.join(textwrap.wrap(item, 18)))
                    lab.setWordWrap(True)
                    font = QFont()
                    font.setBold(True)
                    font.setPointSize(11)
                    lab.setFont(font)
                    self.table.setCellWidget(i, j, lab)
                elif j in (5, 6):
                    thumbnail = Thumbnail(path=item)
                    self.table.setCellWidget(i, j, thumbnail)
                else:
                    table_item = QTableWidgetItem(str(item))
                    font = QFont()
                    font.setPointSize(10)
                    table_item.setFont(font)
                    self.table.setItem(i, j, table_item)
        self.set_row_height(ROW_HEIGHT)
        # self.thumb_delegate = ThumbnailDelegate()
        # self.table.setItemDelegateForColumn(5, self.thumb_delegate)
        # self.table.setItemDelegateForColumn(6, self.thumb_delegate)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 56)
        self.table.setColumnWidth(2, 56)
        self.table.setColumnWidth(3, 30)
        self.table.setColumnWidth(4, 56)
        self.table.setColumnWidth(5, 64)
        self.table.setColumnWidth(6, 64)
        self.table.setColumnWidth(7, 74)
        self.table.setColumnWidth(8, 74)
        self.table.setColumnWidth(9, 120)
        # self.project_table.setColumnWidth(8, 120)
        self.table.setWordWrap(True)


    def get_data(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        self.project_paths = get_project_list()
        # logger.info(project_paths)
        # if not self.project_paths:
        #     return
        projects, created, last_opened, n_sections, img_dimensions, thumbnail_first, thumbnail_last,  \
        bytes, gigabytes, location = \
            [], [], [], [], [], [], [], [], [], []
        logger.info('Project Path List:\n %s' % str(self.project_paths))
        for p in self.project_paths:
            try:
                with open(p, 'r') as f:
                    dm = DataModel(data=json.load(f), quitely=True)
            except:
                logger.error('Table view failed to load data model: %s' % p)
                # cfg.main_window.err('Table view failed to load data model')
            try:    created.append(dm.created())
            except: created.append('Unknown')
            try:    last_opened.append(dm.last_opened())
            except: last_opened.append('Unknown')
            try:    n_sections.append(dm.n_sections())
            except: n_sections.append('Unknown')
            try:    img_dimensions.append(dm.full_scale_size())
            except: img_dimensions.append('Unknown')
            # projects.append(os.path.splitext(os.path.basename(p))[0])
            projects.append(os.path.basename(p))
            project_dir = os.path.splitext(p)[0]
            try:
                _bytes = get_bytes(project_dir)
                bytes.append(_bytes)
                _gigabytes = _bytes / (1024 * 1024 * 1024)
                gigabytes.append('%.4f' % _gigabytes)
            except:
                bytes.append('Unknown')
                gigabytes.append('Unknown')
            thumb_path = os.path.join(project_dir, 'thumbnails')
            try:    thumbnail_first.append(list_paths_absolute(thumb_path)[0])
            except: thumbnail_first.append('No Thumbnail')
            try:    thumbnail_last.append(list_paths_absolute(thumb_path)[-1])
            except: thumbnail_last.append('No Thumbnail')
            try:    location.append(p)
            except: location.append('Unknown')
        return zip(projects, created, last_opened, n_sections, img_dimensions, thumbnail_first, thumbnail_last,
                   bytes, gigabytes, location)

    def userSelectionChanged(self):
        caller = inspect.stack()[1].function
        # if caller == 'set_data':
        #     return
        row = self.table.currentIndex().row()
        try:
            path = self.table.item(row,9).text()
        except:
            cfg.selected_file = ''
            logger.warning(f'No file path at project_table.currentIndex().row()! '
                           f'caller: {caller} - Returning...')
            return
        logger.info(f'path: {path}')
        cfg.selected_file = path
        cfg.main_window.setSelectionPathText(path)
        logger.info(f'counter1={self.counter1}, counter2={self.counter2}')

    def set_row_height(self, h):
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            logger.info('Click detected!')

    def eventFilter(self, obj, event):
        if event.type() == event.MouseMove:
            print('mouse moving')
        return super().eventFilter(obj, event)


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


class ThumbnailDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        data = index.model().data(index, Qt.DisplayRole)
        if data is None:
            return
        thumbnail = QImage(data)
        width = option.rect.width() - 2
        height = option.rect.height() - 2
        scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
        painter.drawImage(option.rect.x(), option.rect.y() + 4, scaled)


class Thumbnail(QWidget):

    def __init__(self, path):
        super(Thumbnail, self).__init__()
        # thumbnail = QLabel(self)
        # thumbnail = Label(self)
        thumbnail = ScaledPixmapLabel()
        pixmap = QPixmap(path)
        pixmap = pixmap.scaledToHeight(ROW_HEIGHT)
        pixmap.scaled(ROW_HEIGHT, ROW_HEIGHT, Qt.KeepAspectRatio)
        thumbnail.setPixmap(pixmap)
        # thumbnail.setScaledContents(True)
        layout = QGridLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(thumbnail, 0, 0)
        self.setLayout(layout)

class Slider(QSlider):
    def __init__(self, min, max, parent=None):
        #QSlider.__init__(self, parent)
        super(Slider, self).__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(min)
        self.setMaximum(max)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)


# class Label(QLabel):
#     def __init__(self, img):
#         super(Label, self).__init__()
#         self.setFrameStyle(QFrame.StyledPanel)
#         self.pixmap = QPixmap(img)
#
#     def paintEvent(self, event):
#         size = self.size()
#         painter = QPainter(self)
#         point = QPoint(0,0)
#         scaledPix = self.pixmap.scaled(size, Qt.KeepAspectRatio, transformMode = Qt.SmoothTransformation)
#         # start painting the label from left upper corner
#         point.setX((size.width() - scaledPix.width())/2)
#         point.setY((size.height() - scaledPix.height())/2)
#         print(point.x(), ' ', point.y())
#         painter.drawPixmap(point, scaledPix)

class ScaledPixmapLabel(QLabel):
    def __init__(self):
        super().__init__()
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
                logger.warning('Cannot divide by zero')
        super().paintEvent(event)


class ImageWidget(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)

    def hasHeightForWidth(self):
        return self.pixmap() is not None

    def heightForWidth(self, w):
        if self.pixmap():
            return int(w * (self.pixmap().height() / self.pixmap().width()))
