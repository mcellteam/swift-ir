#!/usr/bin/env python3

from qtpy.QtCore import Qt, QAbstractTableModel

class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            return self._data[index.row()][index.column()]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._data[0])



#############################
# Below classes are from from:
# https://www.pythonguis.com/faq/file-image-browser-app-with-thumbnails/
#############################

import math
from collections import namedtuple

from qtpy.QtCore import QAbstractTableModel, Qt, QSize
from qtpy.QtWidgets import QStyledItemDelegate

NUMBER_OF_COLUMNS = 4
CELL_PADDING = 20 # all sides

class PreviewDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        # data is our preview object
        data = index.model().data(index, Qt.DisplayRole)
        if data is None:
            return

        width = option.rect.width() - CELL_PADDING * 2
        height = option.rect.height() - CELL_PADDING * 2

        # option.rect holds the area we are painting on the widget (our table cell)
        # scale our pixmap to fit
        scaled = data.image.scaled(
            width,
            height,
            aspectRatioMode=Qt.KeepAspectRatio,
        )
        # Position in the middle of the area.
        x = CELL_PADDING + (width - scaled.width()) / 2
        y = CELL_PADDING + (height - scaled.height()) / 2

        painter.drawImage(option.rect.x() + x, option.rect.y() + y, scaled)

    def sizeHint(self, option, index):
        # All items the same size.
        return QSize(300, 200)


class PreviewModel(QAbstractTableModel):
    def __init__(self, todos=None):
        super().__init__()
        # .data holds our data for display, as a list of Preview objects.
        self.previews = []

    def data(self, index, role):
        try:
            data = self.previews[index.row() * 4 + index.column() ]
        except IndexError:
            # Incomplete last row.
            return

        if role == Qt.DisplayRole:
            return data   # Pass the data to our delegate to draw.

        if role == Qt.ToolTipRole:
            return data.title

    def columnCount(self, index):
        return NUMBER_OF_COLUMNS

    def rowCount(self, index):
        n_items = len(self.previews)
        return math.ceil(n_items / NUMBER_OF_COLUMNS)