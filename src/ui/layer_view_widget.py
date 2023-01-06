#!/usr/bin/env python3

import os
import sys
import math
import inspect
import logging
import pandas as pd
from collections import namedtuple

from qtpy.QtCore import QSize, Qt, Slot, QCoreApplication, QAbstractTableModel, QModelIndex, Signal, QEvent
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QTabWidget, QGridLayout, \
    QHBoxLayout, QFileDialog, QTableView, QErrorMessage, QGroupBox, QTextEdit, QSplitter, QStatusBar, \
    QAbstractItemView, QStyledItemDelegate, QItemDelegate, QSlider, QLabel, QAbstractScrollArea
from qtpy.QtGui import QImage, QFont

from src.data_model import DataModel
from src.helpers import exist_aligned_zarr_cur_scale
import src.config as cfg

logger = logging.getLogger(__name__)


class LayerViewWidget(QWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.parent = parent
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self._dataframe = None # path to a file on disk
        self._selected_rows = []
        self.INITIAL_ROW_HEIGHT = 30 # was 50
        self.INITIAL_FONT_SIZE = 13
        self.table_view = QTableView()
        self.table_view.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.table_view.setFont(QFont('Arial', self.INITIAL_FONT_SIZE))

        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.hheader = self.table_view.horizontalHeader()
        self.vheader = self.table_view.verticalHeader()
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)

        self.row_height_slider = Slider(min=4, max=120)
        self.row_height_slider.setMaximumWidth(100)
        self.row_height_slider.setValue(self.INITIAL_ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.updateRowHeight)
        self.row_height_widget = QWidget()
        self.row_height_hlayout = QHBoxLayout()
        self.row_height_hlayout.setContentsMargins(2, 0, 2, 0)
        self.row_height_widget.setLayout(self.row_height_hlayout)
        self.row_height_hlayout.addWidget(QLabel('Row Height:'))
        self.row_height_hlayout.addWidget(self.row_height_slider, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.row_height_hlayout.addStretch()

        self.font_size_slider = Slider(min=4, max=26)
        self.font_size_slider.setMaximumWidth(100)
        self.font_size_slider.setValue(self.INITIAL_FONT_SIZE)
        self.font_size_slider.valueChanged.connect(self.updateFontSize)
        self.font_size_widget = QWidget()
        self.font_size_hlayout = QHBoxLayout()
        self.font_size_hlayout.setContentsMargins(2, 0, 2, 0)
        self.font_size_widget.setLayout(self.font_size_hlayout)
        self.font_size_hlayout.addWidget(QLabel('Font Size:'))
        self.font_size_hlayout.addWidget(self.font_size_slider, alignment=Qt.AlignmentFlag.AlignLeft)

        self.controls = QWidget()
        self.controls.setObjectName('controls')

        self.controls_hlayout = QHBoxLayout()
        # self.controls_hlayout.setContentsMargins(2, 2, 2, 2)
        self.controls_hlayout.setContentsMargins(0, 0, 0, 0)
        self.controls_hlayout.addWidget(self.row_height_widget)
        self.controls_hlayout.addWidget(self.font_size_widget)
        self.controls_hlayout.addStretch()
        self.controls.setLayout(self.controls_hlayout)

        self.layout.addWidget(self.table_view, 0, 0)
        self.layout.addWidget(self.controls, 1, 0)

        # self.table_view.resizeRowsToContents()
        # self.table_view.resizeColumnsToContents()
        # self.table_view.setColumnWidth(0, 68)
        # self.table_view.verticalHeader().setDefaultSectionSize(60)

        # self.table_view.setColumnWidth(0, self.INITIAL_ROW_HEIGHT)
        # self.table_view.setColumnWidth(2, 200)
        self.table_view.setColumnWidth(3, 380)
        self.table_view.setColumnWidth(4, 20)
        # self.table_view.setRowHeight()

        # cfg.main_window.layer_view_widget.table_view.setColumnWidth(0,
        #                                                             cfg.main_window.layer_view_widget.table_view.rowHeight(
        #                                                                 0))

        self.thumbnail_delegate = ThumbnailDelegate()
        self.table_view.setItemDelegateForColumn(0, self.thumbnail_delegate)


    def selection(self):
        '''Return Pandas Dataframe From Selection'''
        return self._dataframe.iloc[self._selected_rows]


    @Slot()
    def set_data(self):
        # logger.info('Setting Table Data..')
        selection = self._selected_rows
        # logger.info(f'selection: {selection}')
        is_aligned = exist_aligned_zarr_cur_scale()
        scale = [cfg.data.scale_pretty()] * cfg.data.nSections

        skips, ref, base, method, snr_report = [], [], [], [], []
        for l in cfg.data.alstack():
            ref.append(os.path.basename(l['images']['ref']['filename']))
            skips.append(l['skipped'])
            m = l['align_to_ref_method']['selected_method']
            if m == 'Auto Swim Align':
                m = 'Automatic SWIM Alignment'
            method.append(m)
            if is_aligned:
                snr_report.append(l['align_to_ref_method']['method_results']['snr_report'])

        # buttons = ['buttons'] * cfg.datamodel.nSections
        if is_aligned:
            zipped = list(zip(cfg.data.thumbnails(), ref, scale, skips, method, snr_report))
            self._dataframe = pd.DataFrame(zipped, columns=['Img', 'Reference', 'Scale',
                                                            'Skip?', 'Method', 'SNR Report'])
        else:
            zipped = list(zip(cfg.data.thumbnails(),  ref, scale, skips, method))
            self._dataframe = pd.DataFrame(zipped, columns=['Img', 'Reference', 'Scale',
                                                            'Skip?', 'Method'])

        self._dataframe.index = cfg.data.basefilenames()
        self.load_dataframe()
        # self.thumbnail_delegate = ThumbnailDelegate()
        # self.table_view.setItemDelegateForColumn(0, self.thumbnail_delegate)
        if selection:
            self.table_view.selectRow(selection[0])

        # self.skip_delegate = CheckBoxDelegate()
        # self.table_view.setItemDelegateForColumn(3, self.skip_delegate)
        # self.table_view.setItemDelegateForColumn(3, ButtonDelegate())
        # self.button_delegate = PushButtonDelegate(view=self.table_view)
        # self.table_view.setItemDelegateForColumn(3, self.button_delegate)

        self.table_view.setColumnWidth(1, 160)
        self.table_view.setColumnWidth(2, 80)
        self.table_view.setColumnWidth(3, 40)
        self.table_view.setColumnWidth(4, 176)
        QApplication.processEvents()

    def set_selected_row(self, row):
        self._selected_rows = [row]
        if self._selected_rows:
            self.table_view.selectRow(self._selected_rows[0])


    def load_dataframe(self):
        logger.info('Loading dataframe...')
        if isinstance(self._dataframe, pd.DataFrame):
            my_pandas_model = PandasModel(self._dataframe)
            self.table_view.setModel(my_pandas_model)
            self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.selection_model = self.table_view.selectionModel()
            self.selection_model.selectionChanged.connect(self.selectionChanged)
        else:
            error_dialog = QErrorMessage()
            error_dialog.showMessage('No datamodel loaded!')

        self.updateRowHeight(self.INITIAL_ROW_HEIGHT)


    def selectionChanged(self):
        logger.info('selection_changed:')
        caller = inspect.stack()[1].function
        if caller != 'clear_selection':
            selection = self.table_view.selectedIndexes()
            self._selected_rows = list(set([row.row() for row in selection]))
            # print(str(self._selected_rows))
            # logger.info(f'index.row: {index.row()}')
            index = self.table_view.currentIndex().row()
            cfg.data.set_layer(index)
            cfg.main_window.updateTextWidgetA()
            QApplication.processEvents()
        cfg.main_window.dataUpdateWidgets()


    def updateRowHeight(self, h):
        parentVerticalHeader = self.table_view.verticalHeader()
        # parentVerticalHeader.setMinimumSectionSize(rowHeight)
        # parentVerticalHeader.resizeSection(rowHeight, rowHeight)
        parentVerticalHeader.setMaximumSectionSize(h)
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table_view.setColumnWidth(0, h)


    def updateFontSize(self, s):
        # self.table_view.setFont(QFont('Arial', s))
        fnt = self.table_view.font()
        fnt.setPointSize(s)
        self.table_view.setFont(fnt)


    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable


class Slider(QSlider):
    def __init__(self, min, max, parent=None):
        #QSlider.__init__(self, parent)
        super(Slider, self).__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(min)
        self.setMaximum(max)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickPosition(QSlider.TicksAbove)
        self.setTickInterval(1)


class CheckBoxDelegate(QItemDelegate):
    """A delegate that places a fully functioning QCheckBox cell of the column to which it's applied."""
    def __init__(self, parent=None):
        QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        """Important, otherwise an editor is created if the user clicks in this cell."""
        return None

    def paint(self, painter, option, index):
        """Paint a checkbox without the label."""
        self.drawCheck(painter, option, option.rect, Qt.Unchecked if index.data() == False else Qt.Checked)

    def editorEvent(self, event, model, option, index):
        '''Change the datamodel in the model and the state of the checkbox if the user presses
        the left mousebutton and this cell is editable. Otherwise do nothing.'''
        logger.info(f'index.row()={index.row()}')
        # event  = <PyQt5.QtGui.QMouseEvent object at 0x1cd5eb310>
        # model  = <src.ui.layer_view_widget.PandasModel object at 0x1cd5c8040>
        # option = <PyQt5.QtWidgets.QStyleOptionViewItem object at 0x1d08da2e0
        # index  = <PyQt5.QtCore.QModelIndex object at 0x1d08da120>

        if not int(index.flags() & Qt.ItemIsEditable) > 0:
            return False
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            self.setModelData(None, model, index) # Change the checkbox-state
            return True
        return False

    def setModelData (self, editor, model, index):
        '''The user wanted to change the old state in the opposite.'''
        logger.info(f'setModelData | editor={editor} | model={model} | index={index}')
        model.setData(index, True if index.data() == False else False, Qt.EditRole)


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
        # print(f'ThumbnailDelegate, width: {width}')
        # print(f'ThumbnailDelegate, height: {height}')
        # ThumbnailDelegate, width: 99
        # ThumbnailDelegate, height: 29

        # option.rect holds the painting area (table cell)
        # scaled = datamodel.image.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio, )
        scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio, )
        # print(f'ThumbnailDelegate, scaled.width(): {scaled.width()}')
        # print(f'ThumbnailDelegate, scaled.height(): {scaled.height()}')
        # ThumbnailDelegate, scaled.width(): 29
        # ThumbnailDelegate, scaled.height(): 29

        # print(f'ThumbnailDelegate, option.rect.x(): {option.rect.x()}')
        # print(f'ThumbnailDelegate, option.rect.y(): {option.rect.y()}')
        # ThumbnailDelegate, option.rect.x(): 0
        # ThumbnailDelegate, option.rect.y(): 330

        # Position in the middle of the area.
        # x = padding + (width - scaled.width()) / 2
        # y = padding + (height - scaled.height()) / 2
        painter.drawImage(option.rect.x(), option.rect.y(), scaled)





class PandasModel(QAbstractTableModel):
    """A model to interface a Qt table_view with pandas dataframe.
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
        '''The datamodel method works by receiving an index and role and responding with
        instructions for the view to perform. The index says where and the role says what.'''
        # logger.info(f'QModelIndex: {QModelIndex}, role: {role}')
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            if index.column() == 3:
                return None
            else:
                return str(self._dataframe.iloc[index.row(), index.column()])
        if role == Qt.CheckStateRole:
            if index.column() == 3:
                # print(">>> datamodel() row,col = %d, %d" % (index.row(), index.column()))
                if self._dataframe.iloc[index.row(), index.column()] == True:
                    return Qt.Checked
                else:
                    return Qt.Unchecked
        if role == Qt.EditRole:
            return self._df.values[index.row()][index.column()]

        # if role == Qt.CheckStateRole: # checked
        #     return 2
        # if role == Qt.CheckStateRole: # un-checked
        #     return 0

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._dataframe.columns[section])
            if orientation == Qt.Vertical:
                return str(self._dataframe.index[section])



class PushButtonDelegate(QStyledItemDelegate):
    """
    A delegate containing a clickable push button.  The button name will be
    taken from the Qt.DisplayRole datamodel.  Then clicked, this delegate will emit
    a `clicked` signal with either:

    - If `role` is None, a `QtCore.QModelIndex` for the cell that was clicked.
    - Otherwise, the `role` datamodel for the cell that was clicked.
    """

    clicked = Signal(object)

    def __init__(self, view, role=None):
        """
        :param view: The view that this delegate will be added to.  Note that
            mouse tracking will be enabled in the view.
        :type view: `QtWidgets.QTableView`

        :param role: The role to emit datamodel for when a button is clicked.  If not
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

