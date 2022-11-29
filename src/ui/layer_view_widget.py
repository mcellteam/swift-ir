#!/usr/bin/env python3

import os
import sys
import math
import inspect
import logging
import pandas as pd
from collections import namedtuple

from PyQt5.QtCore import QSize, Qt, pyqtSlot, QCoreApplication, QAbstractTableModel, QModelIndex, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QTabWidget, QGridLayout, \
    QHBoxLayout, QFileDialog, QTableView, QErrorMessage, QGroupBox, QTextEdit, QSplitter, QStatusBar, \
    QAbstractItemView, QStyledItemDelegate, QItemDelegate
from PyQt5.QtGui import QImage

from src.data_model import DataModel
from src.helpers import is_cur_scale_aligned
import src.config as cfg

logger = logging.getLogger(__name__)


class LayerViewWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super(LayerViewWidget, self).__init__(*args, **kwargs)
        # self.parent = parent
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self._dataframe = None # path to a file on disk

        self._selected_rows = []

        self.table_widget = QTableView()
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.hheader = self.table_widget.horizontalHeader()
        self.vheader = self.table_widget.verticalHeader()
        # delegate = ThumbnailDelegate()
        # self.table_widget.setItemDelegateForColumn(0, ThumbnailDelegate())
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSelectionBehavior(QTableView.SelectRows)
        self.layout.addWidget(self.table_widget, 0, 0)


    @pyqtSlot()
    def set_data(self):
        '''Get User File Selection Dialog
        Note: This function is a 'Slot' function. It is connected
        to the 'clicked' signal of the import_button'''
        n_layers = cfg.data.n_layers()
        thumbnails = cfg.data.thumbnail_paths()
        # names = cfg.data.basefilenames()
        is_aligned = is_cur_scale_aligned()
        scale = [cfg.data.scale()] * n_layers

        skips, ref, base, method, snr_report = [], [], [], [], []
        for l in cfg.data.alstack():
            # base.append(os.path.basename(l['images']['base']['filename']))
            ref.append(os.path.basename(l['images']['ref']['filename']))
            skips.append(l['skipped'])
            method.append(l['align_to_ref_method']['selected_method'])
            if is_aligned:
                snr_report.append(l['align_to_ref_method']['method_results']['snr_report'])

        buttons = ['buttons'] * n_layers
        if is_aligned:
            zipped = list(zip(thumbnails, ref, scale, skips, method, snr_report))
            self._dataframe = pd.DataFrame(zipped, columns=['Thumbnail', 'Reference', 'Scale', 'Skip?', 'Method', 'SNR Report'])
        else:
            zipped = list(zip(thumbnails,  ref, scale, skips, method))
            self._dataframe = pd.DataFrame(zipped, columns=['Thumbnail', 'Reference', 'Scale', 'Skip?', 'Method'])

        self._dataframe.index = cfg.data.basefilenames()
        self.load_dataframe()
        self.thumbnail_delegate = ThumbnailDelegate()
        self.table_widget.setItemDelegateForColumn(0, self.thumbnail_delegate)
        # self.table_widget.setItemDelegateForColumn(3, ButtonDelegate())
        # self.button_delegate = PushButtonDelegate(view=self.table_widget)
        # self.table_widget.setItemDelegateForColumn(3, self.button_delegate)
        self.table_widget.resizeRowsToContents()
        self.table_widget.resizeColumnsToContents()
        self.table_widget.setColumnWidth(0, 100)
        self.table_widget.verticalHeader().setDefaultSectionSize(100);


    def load_dataframe(self):
        if isinstance(self._dataframe, pd.DataFrame):
            my_pandas_model = PandasModel(self._dataframe)
            self.table_widget.setModel(my_pandas_model)
            self.table_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.selection_model = self.table_widget.selectionModel()
            self.selection_model.selectionChanged.connect(self.selected_rows_changed)
        else:
            error_dialog = QErrorMessage()
            error_dialog.showMessage('No data loaded!')


    def selection(self):
        '''Return Pandas Dataframe From Selection'''
        return self._dataframe.iloc[self._selection_indexes]


    def selected_rows_changed(self):
        caller = inspect.stack()[1].function
        if caller != 'clear_selection':
            # logger.info('Selection Changed!')
            index = self.table_widget.currentIndex().row()
            # logger.info(f'index.row: {index.row()}')
            cfg.main_window.updateAffineWidget(l=index)
            cfg.main_window.updateTextWidgetA(l=index)


class PushButtonDelegate(QStyledItemDelegate):
    """
    A delegate containing a clickable push button.  The button name will be
    taken from the Qt.DisplayRole data.  Then clicked, this delegate will emit
    a `clicked` signal with either:

    - If `role` is None, a `QtCore.QModelIndex` for the cell that was clicked.
    - Otherwise, the `role` data for the cell that was clicked.
    """

    clicked = pyqtSignal(object)

    def __init__(self, view, role=None):
        """
        :param view: The view that this delegate will be added to.  Note that
            mouse tracking will be enabled in the view.
        :type view: `QtWidgets.QTableView`

        :param role: The role to emit data for when a button is clicked.  If not
            given, the index that was clicked will be emitted instead.  This value
            may be specified after instantiation using `setRole`.
        :type role: int or NoneType
        """

        super().__init__(view)
        self._btn_down = None  # index of the button that is down
        self._mouse_over = None  # index of button that the mouse is over
        # We only need the palette from the button, but we keep a reference to
        # the button itself to prevent garbage collection of the button from
        # triggering destruction of the palette.
        self._button = QPushButton()
        self.setRole(role)


class ThumbnailDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        data = index.model().data(index, Qt.DisplayRole)
        if data is None:
            return

        thumbnail = QImage(data)
        # padding = 10
        # width = option.rect.width() - padding * 2
        # height = option.rect.height() - padding * 2
        # width = 120
        width = option.rect.width()
        height = option.rect.height()
        # print(f'width: {width} height: {height}')

        # option.rect holds the painting area (table cell)
        # scaled = data.image.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio, )
        scaled = thumbnail.scaled(width, 100, aspectRatioMode=Qt.KeepAspectRatio, )
        # Position in the middle of the area.
        # x = padding + (width - scaled.width()) / 2
        # y = padding + (height - scaled.height()) / 2
        painter.drawImage(option.rect.x(), option.rect.y(), scaled)



class PandasModel(QAbstractTableModel):
    """A model to interface a Qt table_widget with pandas dataframe.
    Adapted from Qt Documentation Example:
    https://doc.qt.io/qtforpython/examples/example_external__pandas.html"""
    def __init__(self, dataframe: pd.DataFrame, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self._dataframe = dataframe

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent == QModelIndex():
            return len(self._dataframe)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent == QModelIndex():
            return len(self._dataframe.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return str(self._dataframe.iloc[index.row(), index.column()])

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._dataframe.columns[section])
            if orientation == Qt.Vertical:
                return str(self._dataframe.index[section])