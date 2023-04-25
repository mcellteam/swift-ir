#!/usr/bin/env python3
import math
from qtpy.QtCore import QAbstractTableModel, Qt, QSize
from qtpy.QtWidgets import QStyledItemDelegate

NUMBER_OF_COLUMNS = 1
CELL_PADDING = 2 # all sides


class PreviewModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        # .datamodel holds our datamodel for display, as a list of Preview objects.
        self.previews = []

    def data(self, index, role):
        try:
            # datamodel = self.previews[index.row() * 4 + index.column() ] #orig
            data = self.previews[index.row() * NUMBER_OF_COLUMNS + index.column() ]
        except IndexError:
            # Incomplete last row.
            return
        if role == Qt.DisplayRole:
            return data   # Pass the datamodel to our delegate to draw.
        if role == Qt.ToolTipRole:
            return data.title

    def columnCount(self, index):
        return NUMBER_OF_COLUMNS

    def rowCount(self, index):
        n_items = len(self.previews)
        return math.ceil(n_items / NUMBER_OF_COLUMNS)


class PreviewDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        # datamodel is our preview object
        # option: <class 'PyQt5.QtWidgets.QStyleOptionViewItem'>
        # index: <class 'PyQt5.QtCore.QModelIndex'>

        data = index.model().data(index, Qt.DisplayRole)

        print('col = %s, cur_method(datamodel) = %s' % (str(index.column()), type(data)))

        if data is None:
            return

        # print(cur_method(datamodel))
        # print(str(datamodel))
        # print(datamodel.title)
        width = option.rect.width() - CELL_PADDING * 2
        height = option.rect.height() - CELL_PADDING * 2

        # option.rect holds the area we are painting on the widget (our project_table cell)
        # s our pixmap to fit
        scaled = data.image.scaled(
            width,
            height,
            aspectRatioMode=Qt.KeepAspectRatio,
        )
        # Position in the middle of the area.
        x = CELL_PADDING + (width - scaled.width()) / 2
        y = CELL_PADDING + (height - scaled.height()) / 2

        # painter.drawImage(option.rect.x() + x, option.rect.y() + y, scaled)
        # painter.drawText(option.rect.x() + x, option.rect.y() + y - 5, datamodel.title)

        painter.drawImage(option.rect.x(), option.rect.y(), scaled)
        painter.drawText(option.rect.x(), option.rect.y() - 5, data.title)


    def sizeHint(self, option, index):
        # All items the same size.
        # return QSize(300, 200) #orig
        return QSize(60, 60)



