#!/usr/bin/env python3
'''
Adapted from Qt Documentation:
https://doc.qt.io/qtforpython/examples/example_widgets_itemviews_jsonmodel.html

item = self.parent.mdlTreeview.itemData(self.parent.mdlTreeview.index(2,0)); print(item)

a = self.parent.treeview.model().index(1, 0)
b = a.child(0,0) # a is QModelIndex
self.parent.mdlTreeview.itemData(b) #b is QModelIndex
self.parent.treeview.setCurrentIndex(b) # select the item programmatically

# returns the item count (8 here)
self.parent.mdlTreeview._rootItem.childCount()

cur_method(self.parent.mdlTreeview._rootItem):
Out[10]: src.ui.models.json_tree.TreeItem


# return the item data for all items
# get QModelIndex of 'data' key


lst = []
for i in range(self.parent.mdlTreeview._rootItem.childCount()):
    # lst.append(self.parent.mdlTreeview.index(i,0).data())
    lst.append(self.parent.mdlTreeview._rootItem.child(i).key)


tree_data = self.parent.mdlTreeview._rootItem.child(1).childCount()
index_data = lst.index('data')
modelindex_data = self.parent.mdlTreeview.index(index_data,0) #  QModelIndex of 'data' key

def get_index(findkeys, treeitem=self.parent.mdlTreeview._rootItem):
    print('\nRecursing...')
    # start w/ self.parent.mdlTreeview._rootItem
    print('findkeys = %level' % str(findkeys))
    print('childCount = %level' % str(treeitem.childCount()))

    print('Finding key %level...' % str(findkeys[0]))
    lst = []
        for i in range(treeitem.childCount()):
            # lst.append(self.parent.mdlTreeview.index(i,0).data())
            lst.append(treeitem.child(i).key)

    index = lst.index(findkeys[0])
    findkeys.pop(0)
    if findkeys == []:
        print('Returning %level' % treeitem)
        return self.parent.mdlTreeview.index(index,0).data()
        # return treeitem
    else:
        get_index(findkeys, treeitem=treeitem.child(index))

# get QModelIndex of 'data key'


'''
import json
import logging
import sys
from typing import Any, List, Dict, Union
import qtpy
from qtpy.QtWidgets import QTreeView, QApplication, QHeaderView, QAbstractItemView
from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, QFileInfo
from qtpy.QtCore import Qt, QAbstractItemModel, QAbstractTableModel, QModelIndex, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy, QHeaderView, QTableView

import src.config as cfg

__all__ = ['JsonModel']

logger = logging.getLogger(__name__)

class TreeItem:
    """A Json item corresponding to a line in QTreeView"""

    def __init__(self, parent: "TreeItem" = None):
        self._parent = parent
        self._key = ""
        self._value = ""
        self._value_type = None
        self._children = []

    def appendChild(self, item: "TreeItem"):
        """Add item as a child"""
        self._children.append(item)

    def child(self, row: int) -> "TreeItem":
        """Return the child of the current item from the given row"""
        return self._children[row]

    def parent(self) -> "TreeItem":
        """Return the parent of the current item"""
        return self._parent

    def childCount(self) -> int:
        """Return the number of children of the current item"""
        return len(self._children)

    def row(self) -> int:
        """Return the row where the current item occupies in the parent"""
        return self._parent._children.index(self) if self._parent else 0

    @property
    def key(self) -> str:
        """Return the key name"""
        return self._key

    @key.setter
    def key(self, key: str):
        """Set key name of the current item"""
        self._key = key

    @property
    def value(self) -> str:
        """Return the value name of the current item"""
        return self._value

    @value.setter
    def value(self, value: str):
        """Set value name of the current item"""
        self._value = value

    @property
    def value_type(self):
        """Return the python cur_method of the item'level value."""
        return self._value_type

    @value_type.setter
    def value_type(self, value):
        """Set the python cur_method of the item'level value."""
        self._value_type = value

    @classmethod
    def load(
        cls, value: Union[List, Dict], parent: "TreeItem" = None, sort=False
    ) -> "TreeItem":
        """Create a 'root' TreeItem from a nested list or a nested dictonary

        Examples:
            with open("file.json") as file:
                datamodel = json.dump(file)
                root = TreeItem.load(datamodel)

        This method is a recursive function that calls itself.

        Returns:
            TreeItem: TreeItem
        """
        rootItem = TreeItem(parent)
        rootItem.key = "root"

        if isinstance(value, dict):
            items = sorted(value.items()) if sort else value.items()

            for key, value in items:
                child = cls.load(value, rootItem)
                child.key = key
                child.value_type = type(value)
                rootItem.appendChild(child)

        elif isinstance(value, list):
            for index, value in enumerate(value):
                child = cls.load(value, rootItem)
                child.key = index
                child.value_type = type(value)
                rootItem.appendChild(child)

        else:
            rootItem.value = value
            rootItem.value_type = type(value)

        return rootItem

class WorkerSignals(QObject):
    dataModelChanged = Signal()

class JsonModel(QAbstractItemModel):
    """ An editable previewmodel of Json datamodel """

    def __init__(self, parent, dm=None):
        super().__init__(parent)
        self.parent = parent
        self.dm = dm
        self._rootItem = TreeItem()
        self._headers = ("key", "value")
        self.signals = WorkerSignals()

    def clear(self):
        """ Clear datamodel from the previewmodel """
        self.load({})

    def load(self, document: dict):
        """Load previewmodel from a nested dictionary returned by json.loads()"""

        assert isinstance(
            document, (dict, list, tuple)
        ), "`document` must be of dict, list or tuple, " f"not {type(document)}"

        self.beginResetModel()
        self._rootItem = TreeItem.load(document)
        self._rootItem.value_type = type(document)
        self.endResetModel()
        return True

    # def datamodel(self, index: QModelIndex, role: Qt.ItemDataRole) -> Any:
    def data(self, index: QModelIndex, role: Qt.ItemDataRole) -> Any:
        """Override from QAbstractItemModel
        Return datamodel from a json item according index and role
        """

        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.DisplayRole:
            if index.column() == 0:
                return item.key

            if index.column() == 1:
                return item.value

        elif role == Qt.EditRole:
            if index.column() == 1:
                return item.value

    def setData(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole):

        """Override from QAbstractItemModel

        Set json item according index and role

        Args:
            index (QModelIndex)
            value (Any)
            role (Qt.ItemDataRole)

        """
        #Critical - Uncomment this line to prevent editing
        if not cfg.DEV_MODE:
            role = Qt.DisplayRole #0718+
        if role == Qt.EditRole:
            # print('Role was EDIT role')
            if index.column() == 1:
                item = index.internalPointer()
                item.value = str(value)
                self.signals.dataModelChanged.emit()
                return True



        return False

    # def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole):
    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole):
        """Override from QAbstractItemModel
        For the JsonModel, it returns only datamodel for columns (orientation = Horizontal)
        """

        # role = Qt.DisplayRole  # 0718+

        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self._headers[section]

    def index(self, row: int, column: int, parent=QModelIndex()) -> QModelIndex:
        """Override from QAbstractItemModel
        Return index according row, column and parent
        """
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Override from QAbstractItemModel
        Return parent index of index
        """

        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self._rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent=QModelIndex()):
        """Override from QAbstractItemModel
        Return row count from parent index
        """
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self._rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def columnCount(self, parent=QModelIndex()):
        """Override from QAbstractItemModel
        Return column number. For the previewmodel, it always return 2 columns
        """
        return 2

    #Critical Uncomment these flags to make data non-editable
    # if qtpy.PYSIDE6:
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Override from QAbstractItemModel

        Return flags of index
        """
        flags = super(JsonModel, self).flags(index)

        if index.column() == 1:
            return Qt.ItemIsEditable | flags
        else:
            return flags

    def to_json(self, item=None):

        if item is None:
            item = self._rootItem

        nchild = item.childCount()

        if item.value_type is dict:
            document = {}
            for i in range(nchild):
                ch = item.child(i)
                document[ch.key] = self.to_json(ch)
            return document

        elif item.value_type == list:
            document = []
            for i in range(nchild):
                ch = item.child(i)
                document.append(self.to_json(ch))
            return document

        else:
            return item.value

    def collapseIndex(self, s=None, l=None):
        if s == None: s = self.dm.level
        if l == None: l = self.dm.zpos
        # self.parent.treeview.collapseAll()
        self.collapseAll()
        keys = ['data', 'scales', s, 'stack', l]
        self.getIndex(findkeys=keys, jump=False, collapse=True)


    def getIndex(self, findkeys, treeitem=None, jump=True, expand=False, collapse=False):
        # start w/ self.parent.mdlTreeview._rootItem
        print(f"Recursing... next key: {findkeys}")
        isRoot = 0
        if treeitem == None:
            isRoot = 1
            treeitem = self._rootItem
            self.count = treeitem.childCount()
            self.lst = [self.index(i, 0).data() for i in range(self.count)]
        else:
            self.count = self.rowCount(treeitem)
            self.lst = [treeitem.child(i,0).data() for i in range(self.count)]

        self.idx = self.lst.index(findkeys[0])
        # print('found key %level in %level at images_path %d...' % (str(findkeys), str(self.lst), self.idx))

        findkeys.pop(0)

        if isRoot:
            next_treeitem = self.index(self.idx, 0)  # b is QModelIndex
        else:
            next_treeitem = treeitem.child(self.idx, 0)

        self.next_treeitem = next_treeitem

        if findkeys == []:
            # print('Returning: %level' % str(next_treeitem))
            if jump:
                self.parent.treeview.setCurrentIndex(next_treeitem)
            if expand:
                self.parent.treeview.expandRecursively(next_treeitem)
            # if collapse:
            #     # self.parent.treeview.collapse(next_treeitem)
            #     previous_index = self.parent.treeview.pr
            #     self.parent.treeview.collapse(next_treeitem)

            return next_treeitem

        else:
            # print('next treeitem: %level, cur_method: %level' % (next_treeitem, cur_method(next_treeitem)))
            self.getIndex(findkeys, treeitem=next_treeitem)

    def jumpToLayer(self, s=None, l=None):
        if s == None: s = self.dm.level
        if l == None: l = self.dm.zpos
        # self.parent.treeview.collapseAll()
        keys = ['stack', l, 'levels', s]
        # if z !=0:
        #     self.collapseIndex(z=z - 1)
        # self.getIndex(findkeys=keys, expand=True)
        self.getIndex(findkeys=keys, expand=False)
        # self.parent.treeview.scrollTo(self.next_treeitem, QAbstractItemView.PositionAtCenter)

    # def jumpToScale(self, level=None):
    #     if level == None: level = self.dm.level
    #     keys = ['data', 'scales', level]
    #     self.getIndex(findkeys=keys, expand=True)
    #     self.parent.treeview.scrollTo(self.next_treeitem, QAbstractItemView.PositionAtTop)


    # def jumpToSection(self, sec, s=None):
    #     if s == None: s = self.dm.level
    #     keys = ['data', 'scales', s, 'stack', sec]
    #     self.getIndex(findkeys=keys, expand=True)
    #     self.parent.treeview.scrollTo(self.next_treeitem, QAbstractItemView.PositionAtTop)

    def jumpToKey(self, keys):
        self.getIndex(findkeys=keys, expand=True)
        self.parent.treeview.scrollTo(self.next_treeitem, QAbstractItemView.PositionAtTop)




if __name__ == "__main__":

    app = QApplication(sys.argv)
    view = QTreeView()
    model = JsonModel()

    view.setModel(model)

    json_path = QFileInfo(__file__).absoluteDir().filePath("r34_alignment.swiftir")

    with open(json_path) as file:
        document = json.load(file)
        model.load(document)

    view.show()
    view.header().setSectionResizeMode(0, QHeaderView.Stretch)
    view.setAlternatingRowColors(True)
    view.resize(500, 300)
    app.exec()