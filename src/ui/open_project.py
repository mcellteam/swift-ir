#!/usr/bin/env python3

import os
import json
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QAbstractItemView, \
    QStyledItemDelegate, QPushButton, QSplitter, QTableWidget, QTableWidgetItem
from qtpy.QtCore import Qt
from qtpy.QtGui import QImage

from src.ui.file_browser import FileBrowser
from src.helpers import get_project_list, list_paths_absolute, get_bytes
from src.data_model import DataModel

import src.config as cfg

logger = logging.getLogger(__name__)



class OpenProject(QWidget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setMinimumHeight(200)
        self.filebrowser = FileBrowser(parent=self)
        self.user_projects = UserProjects()
        self.initUI()
        self.selected_project = None

    def initUI(self):
        # User Projects Widget
        self.userProjectsWidget = QWidget()
        lab = QLabel('<h3>User Projects:</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(6, 0, 6, 0)
        vbl.addWidget(lab)
        vbl.addWidget(self.user_projects)
        self.userProjectsWidget.setLayout(vbl)

        # User Files Widget
        self.userFilesWidget = QWidget()
        lab = QLabel('<h3>File Browser:</h3>')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(6, 0, 6, 0)
        vbl.addWidget(lab)
        vbl.addWidget(self.filebrowser)
        self.userFilesWidget.setLayout(vbl)

        self._splitter = QSplitter()
        self._splitter.addWidget(self.userProjectsWidget)
        self._splitter.addWidget(self.userFilesWidget)
        self._splitter.setSizes([650, 350])

        self.layout = QVBoxLayout()
        self.layout.addWidget(self._splitter)
        self.setLayout(self.layout)


class UserProjects(QWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        self.table.itemClicked.connect(self.selectionChanged)
        # self.table.setStyleSheet("selection-background-color: #353535; border-radius: 10px")
        # self.table.setStyleSheet("border-radius: 10px")
        self.table.setColumnCount(10)
        self.set_headers()
        self.set_data()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)

    def set_headers(self):
        self.table.setHorizontalHeaderLabels([
            "Name",
            "Created",
            "Last\nOpened",
            "#\nImgs",
            "Image\nSize",
            "First\nThumbnail",
            "Last\nThumbnail",
            "Disk Space\n(Bytes)",
            "Disk Space\n(Gigabytes)",
            "Location"])

    def set_data(self):
        caller = inspect.stack()[1].function
        logger.critical(f'caller: {caller}')
        self.table.clearContents()
        self.set_headers()
        data = self.get_data()
        # n_rows_needed = len(list(data))
        self.table.setRowCount(0)
        for i, row in enumerate(data):
            self.table.insertRow(i)
            for j, item in enumerate(row):
                logger.info(f'item: {item}')
                if j == 0:
                    # lab = QLabel('<h3>' + '\n'.join(textwrap.wrap(item, 12)) + '</h3>')
                    lab = QLabel('<h3>' + '\n'.join(textwrap.wrap(item, 12)) + '</h3>')
                    lab.setWordWrap(True)
                    self.table.setCellWidget(i, j, lab)
                else:
                    self.table.setItem(i, j, QTableWidgetItem(str(item)))
        self.set_row_height(80)
        self.thumb_delegate = ThumbnailDelegate()
        self.table.setItemDelegateForColumn(5, self.thumb_delegate)
        self.table.setItemDelegateForColumn(6, self.thumb_delegate)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 30)
        self.table.setColumnWidth(4, 60)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 80)
        # self.table.setColumnWidth(8, 120)
        self.table.resizeColumnToContents(0)
        self.table.setWordWrap(True)


    def get_data(self):

        self.project_paths = get_project_list()
        # logger.info(project_paths)
        # if not self.project_paths:
        #     return
        projects, created, last_opened, n_sections, img_dimensions, thumbnail_first, thumbnail_last,  \
        bytes, gigabytes, location = \
            [], [], [], [], [], [], [], [], [], []
        for p in self.project_paths:
            with open(p, 'r') as f:
                dm = DataModel(data=json.load(f), quitely=True)
            try:    created.append(dm.created())
            except: created.append('Unknown')
            try:    last_opened.append(dm.last_opened())
            except: last_opened.append('Unknown')
            try:    n_sections.append(dm.n_sections())
            except: n_sections.append('Unknown')
            try:    img_dimensions.append(dm.full_scale_size())
            except: img_dimensions.append('Unknown')
            projects.append(os.path.splitext(os.path.basename(p))[0])
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
            location.append(p)
        return zip(projects, created, last_opened, n_sections, img_dimensions, thumbnail_first, thumbnail_last,
                   bytes, gigabytes, location)

    def selectionChanged(self):
        logger.info('')
        row = self.table.currentIndex().row()
        self.selected_project = self.project_paths[row]
        cfg.selected_file = self.selected_project
        # logger.info(f'Project Selection Changed! {cfg.selected_file}')
        cfg.main_window.setSelectionPathText(cfg.selected_file)

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





class ThumbnailDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        data = index.model().data(index, Qt.DisplayRole)
        if data is None:
            return
        thumbnail = QImage(data)
        width = option.rect.width()
        height = option.rect.height()
        scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
        painter.drawImage(option.rect.x(), option.rect.y(), scaled)




