#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QAbstractItemView, \
    QSplitter, QTableWidget, QTableWidgetItem, QSlider, QGridLayout
from qtpy.QtCore import Qt, QRect
from qtpy.QtGui import QFont, QPixmap, QPainter

from src.ui.file_browser import FileBrowser
from src.funcs_image import ImageSize
from src.helpers import get_project_list, list_paths_absolute, get_bytes, absFilePaths
from src.data_model import DataModel

import src.config as cfg

logger = logging.getLogger(__name__)

ROW_HEIGHT = 40


class OpenProject(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.initial_row_height = 50

        self.setMinimumHeight(256)
        self.filebrowser = FileBrowser(parent=self)
        self.filebrowser.controlsNavigation.show()
        self.user_projects = UserProjects()
        self.row_height_slider = Slider(self)
        self.row_height_slider.setValue(ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.user_projects.updateRowHeight)
        self.initUI()

    def initUI(self):
        # User Projects Widget
        self.userProjectsWidget = QWidget()
        lab = QLabel('<h3>User Projects:</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(4, 4, 4, 4)
        vbl.addWidget(lab)
        vbl.addWidget(self.user_projects)
        self.userProjectsWidget.setLayout(vbl)

        # User Files Widget
        self.userFilesWidget = QWidget()
        lab = QLabel('<h3>Import Project:</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(4, 4, 4, 4)
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
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.addWidget(self._splitter)
        self.layout.addWidget(controls)
        self.setLayout(self.layout)

        self.user_projects.set_data()
        self.row_height_slider.setValue(self.initial_row_height)



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
        self.table.itemDoubleClicked.connect(self.onDoubleClick)

        self.table.setStyleSheet("border-radius: 12px; border-width: 3px;")
        self.table.setColumnCount(10)
        self.set_headers()
        # self.setScaleData() # This is now called from _onGlobTabChange
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)

    def onDoubleClick(self, item=None):
        print(type(item))
        # userSelectionChanged
        cfg.main_window.open_project_selected()

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
        self.table.setColumnWidth(1, h)
        self.table.setColumnWidth(2, h)

        # header = self.table.horizontalHeader()
        # header.setSectionResizeMode(5, QHeaderView.Stretch)
        # header.setSectionResizeMode(6, QHeaderView.ResizeToContents)


    def set_headers(self):
        self.table.setHorizontalHeaderLabels([
            "Name",
            "First\nThumbnail",
            "Last\nThumbnail",
            "Created",
            "Last\nOpened",
            "#\nImgs",
            "Image\nSize (px)",
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
        self.table.setRowCount(0)
        for i, row in enumerate(self.get_data()):
            self.table.insertRow(i)
            for j, item in enumerate(row):
                if j == 0:
                    lab = QLabel('\n'.join(textwrap.wrap(item, 22)))
                    lab.setWordWrap(True)
                    font = QFont()
                    font.setBold(True)
                    font.setPointSize(9)
                    lab.setFont(font)
                    self.table.setCellWidget(i, j, lab)
                elif j in (1, 2):
                    thumbnail = Thumbnail(self, path=item)
                    self.table.setCellWidget(i, j, thumbnail)
                else:
                    table_item = QTableWidgetItem(str(item))
                    font = QFont()
                    font.setPointSize(10)
                    table_item.setFont(font)
                    self.table.setItem(i, j, table_item)
        self.table.setColumnWidth(0, 128)
        self.table.setColumnWidth(1, 64)
        self.table.setColumnWidth(2, 64)
        self.table.setColumnWidth(3, 56)
        self.table.setColumnWidth(4, 56)
        self.table.setColumnWidth(5, 30)
        self.table.setColumnWidth(6, 56)
        self.table.setColumnWidth(7, 74)
        self.table.setColumnWidth(8, 74)
        self.table.setColumnWidth(9, 120)


    def get_data(self):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        self.project_paths = get_project_list()
        projects, thumbnail_first, thumbnail_last, created, last_opened, \
        n_sections, img_dimensions, bytes, gigabytes, location = \
            [], [], [], [], [], [], [], [], [], []
        for p in self.project_paths:
            try:
                with open(p, 'r') as f:
                    dm = DataModel(data=json.load(f), quitely=True)
            except:
                logger.error('Table view failed to load data model: %s' % p)
            try:    created.append(dm.created())
            except: created.append('Unknown')
            try:    last_opened.append(dm.last_opened())
            except: last_opened.append('Unknown')
            try:    n_sections.append(dm.n_sections())
            except: n_sections.append('Unknown')
            try:    img_dimensions.append(dm.full_scale_size())
            except: img_dimensions.append('Unknown')
            try:    projects.append(os.path.basename(p))
            except: projects.append('Unknown')
            project_dir = os.path.splitext(p)[0]
            try:
                _bytes = get_bytes(project_dir)
                bytes.append(_bytes)
                gigabytes.append('%.4f' % _bytes / 1073741824)
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
        return zip(projects, thumbnail_first, thumbnail_last, created, last_opened,
                   n_sections, img_dimensions, bytes, gigabytes, location)

    def userSelectionChanged(self):
        caller = inspect.stack()[1].function
        # if caller == 'setScaleData':
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
        # logger.info(f'counter1={self.counter1}, counter2={self.counter2}')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            logger.info('Click detected!')

    def eventFilter(self, obj, event):
        if event.type() == event.MouseMove:
            print('mouse moving')
        return super().eventFilter(obj, event)


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


class Slider(QSlider):
    def __init__(self, parent):
        super().__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(16)
        self.setMaximum(512)
        self.setValue(128)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)


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
                pass
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
