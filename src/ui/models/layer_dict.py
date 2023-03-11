#!/usr/bin/env python3

import os, sys, json
from qtpy.QtCore import QAbstractTableModel, QAbstractItemModel, QModelIndex, QObject, Qt, QFileInfo
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QTableView, QHBoxLayout, QVBoxLayout, QSizePolicy, \
    QHeaderView
from qtpy.QtGui import QColor

# from qtpy import QtCore, QtGui, QtWidgets

class DictionaryTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super(DictionaryTableModel, self).__init__()
        self._data = data
        self._headers = headers

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # Look up the key by header index.
            column = index.column()
            column_key = self._headers[column]
            return self._data[index.row()][column_key]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The length of our headers.
        return len(self._headers)

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._headers[section])

            if orientation == Qt.Vertical:
                return str(section)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.table = QTableView()

        data = [
          {'a':4, 'b':9, 'c':2},
          {'a':1, 'b':0, 'c':0},
          {'a':3, 'b':5, 'c':0},
          {'a':3, 'b':3, 'c':2},
          {'a':7, 'b':8, 'c':9},
        ]

        headers = ['a', 'b', 'c']

        self.model = DictionaryTableModel(data, headers)
        self.table.setModel(self.model)

        self.setCentralWidget(self.table)



from qtpy.QtWidgets import  QApplication, QTreeWidget, QTreeWidgetItem

class ViewTree(QTreeWidget):
    def __init__(self, value) -> None:
        super().__init__()
        self.fill_item(self.invisibleRootItem(), value)

    @staticmethod
    def fill_item(item: QTreeWidgetItem, value) -> None:
        if value is None:
            return
        elif isinstance(value, dict):
            for key, val in sorted(value.items()):
                ViewTree.new_item(item, str(key), val)
        elif isinstance(value, (list, tuple)):
            for val in value:
                if isinstance(val, (str, int, float)):
                    ViewTree.new_item(item, str(val))
                else:
                    ViewTree.new_item(item, f"[{type(val).__name__}]", val)
        else:
            ViewTree.new_item(item, str(value))

    @staticmethod
    def new_item(parent: QTreeWidgetItem, text:str, val=None) -> None:
        child = QTreeWidgetItem([text])
        ViewTree.fill_item(child, val)
        parent.addChild(child)
        child.setExpanded(True)


if __name__ == '__main__':
    app = QApplication([])

    with open('src/ui/models/r34_alignment.swiftir', 'r') as f:
        data = json.load(f)

    s4_layers = data['data']['scales']['scale_4']['stack']
    print(s4_layers)



    # window = ViewTree({
    #     'key1': 'value1',
    #     'key2': [1, 2, 3, {1: 3, 7: 9}]})
    window = ViewTree(s4_layers)

    window.show()
    app.exec_()


    # app = QApplication(sys.argv)
    # window = MainWindow()
    # window.show()
    # app.exec_()
