#!/usr/bin/env python3
from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex
from qtpy.QtGui import QColor



class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # See below for the nested-list datamodel structure.
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

class GeneralTableModel(QAbstractTableModel):

    def __init__(self, data):
        super(GeneralTableModel, self).__init__()
        self._data = data
        self.previews = []

    # def datamodel(self, index, role):
    #     if role == Qt.DisplayRole:
    #         # See below for the nested-list datamodel structure.
    #         # .row() indexes into the outer list,
    #         # .column() indexes into the sub-list
    #         return self._data[index.row()][index.column()]

    def data(self, index, role):
        try:
            # datamodel = self.previews[index.row() * 4 + index.column() ]
            data = self.previews[index.row()]
        except IndexError:
            # Incomplete last row.
            return
        if role == Qt.DisplayRole:
            return data   # Pass the datamodel to our delegate to draw.
        if role == Qt.ToolTipRole:
            return data.title

    def rowCount(self, index):
        # The length of the outer list.
        # return len(self._data)
        return len(self.previews)

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        # return len(self._data[0])
        return len(self.previews[0])


# # EXAMPLE FROM QT DOCUMENTATION
class CustomTableModel(QAbstractTableModel):
    '''https://doc.qt.io/qtforpython/tutorials/datavisualize/add_tableview.html'''
    def __init__(self, data=None):
        QAbstractTableModel.__init__(self)
        self.load_data(data)

    def load_data(self, data):
        self.input_dates = data[0].values
        self.input_magnitudes = data[1].values
        self.column_count = 2
        self.row_count = len(self.input_magnitudes)

    def rowCount(self, parent=QModelIndex()):
        return self.row_count

    def columnCount(self, parent=QModelIndex()):
        return self.column_count

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return ("Date", "Magnitude")[section]
        else:
            return f"{section}"

    def data(self, index, role=Qt.DisplayRole):
        column = index.column()
        row = index.row()

        if role == Qt.DisplayRole:

            if column == 0:
                date = self.input_dates[row].toPython()
                return str(date)[:-3]
            elif column == 1:
                magnitude = self.input_magnitudes[row]
                return f"{magnitude:.2f}"

        elif role == Qt.BackgroundRole:
            return QColor(Qt.white)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignRight

        return None


# # EXAMPLE FROM QT DOCUMENTATION
# class Widget(QWidget):
#
#     def __init__(self, datamodel):
#
#         QWidget.__init__(self)
#         self.model = CustomTableModel(datamodel)   # <-- get the model
#         self.project_table = QTableView()        # <-- create QTableView()
#         self.project_table.setModel(self.model)
#         self.horizontal_header = self.project_table.horizontalHeader()
#         self.vertical_header = self.project_table.verticalHeader()
#         self.horizontal_header.setSectionResizeMode(QHeaderView.ResizeToContents)
#         self.vertical_header.setSectionResizeMode(QHeaderView.ResizeToContents)
#         self.horizontal_header.setStretchLastSection(True)
#         self.main_layout = QHBoxLayout()
#         size = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
#         size.setHorizontalStretch(1)
#         self.project_table.setSizePolicy(size)
#         self.main_layout.addWidget(self.project_table)
#         self.setLayout(self.main_layout)