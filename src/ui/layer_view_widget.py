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
from qtpy.QtGui import QImage, QFont, QColor

from src.data_model import DataModel
from src.helpers import exist_aligned_zarr_cur_scale
import src.config as cfg

logger = logging.getLogger(__name__)


class LayerViewWidget(QWidget):
    numberPopulated = Signal(int)

    def __init__(self, parent=None, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        self.fileCount = 0
        self.fileList = []

        self.parent = parent
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self._dataframe = None # path to a file on disk
        self._selected_rows = []
        self.INITIAL_ROW_HEIGHT = 100
        self.INITIAL_FONT_SIZE = 13
        self.table_view = QTableView()
        self.table_view.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.table_view.setFont(QFont('Arial', self.INITIAL_FONT_SIZE))


        self.hheader = self.table_view.horizontalHeader()
        self.vheader = self.table_view.verticalHeader()
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        # self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)

        self.row_height_slider = Slider(min=64, max=256)
        self.row_height_slider.setMaximumWidth(128)
        self.row_height_slider.setValue(self.INITIAL_ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.updateRowHeight)
        # self.row_height_slider.valueChanged.connect(self.updateFontSize)
        self.row_height_widget = QWidget()
        self.row_height_hlayout = QHBoxLayout()
        self.row_height_hlayout.setContentsMargins(2,2, 2, 2)
        self.row_height_widget.setLayout(self.row_height_hlayout)
        self.row_height_hlayout.addWidget(QLabel('Thumbnail Size:'))
        self.row_height_hlayout.addWidget(self.row_height_slider, alignment=Qt.AlignmentFlag.AlignLeft)

        # self.font_size_slider = Slider(min=4, max=26)
        # self.font_size_slider.setMaximumWidth(100)
        # self.font_size_slider.setValue(self.INITIAL_FONT_SIZE)
        # self.font_size_slider.valueChanged.connect(self.updateFontSize)
        # self.font_size_widget = QWidget()
        # self.font_size_hlayout = QHBoxLayout()
        # self.font_size_hlayout.setContentsMargins(2,2, 2, 2)
        # self.font_size_widget.setLayout(self.font_size_hlayout)
        # self.font_size_hlayout.addWidget(QLabel('Font Size:'))
        # self.font_size_hlayout.addWidget(self.font_size_slider, alignment=Qt.AlignmentFlag.AlignLeft)

        self.controls = QWidget()
        self.controls.setObjectName('controls')
        self.controls_hlayout = QHBoxLayout()
        self.controls_hlayout.setContentsMargins(0, 0, 0, 0)
        self.controls_hlayout.addWidget(self.row_height_widget)
        # self.controls_hlayout.addWidget(self.font_size_widget)
        self.controls_hlayout.addStretch()
        self.controls.setLayout(self.controls_hlayout)
        self.layout.addWidget(self.table_view, 0, 0)
        self.layout.addWidget(self.controls, 1, 0)

        self.setThumbnailDelegates()

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable

    def selection(self):
        '''Return Pandas Dataframe From Selection'''
        return self._dataframe.iloc[self._selected_rows]

    @Slot()
    def set_data(self):
        logger.info('Setting Table Data..')
        selection = self._selected_rows
        # logger.info(f'selection: {selection}')
        is_aligned = cfg.data.is_aligned_and_generated()
        scale = [cfg.data.scale_pretty()] * cfg.data.nSections

        ref = cfg.data.thumbnails_ref()

        skips, base, method, snr_report = [], [], [], []
        for l in cfg.data.alstack():
            ref.append(os.path.basename(l['images']['ref']['filename']))
            # ref.append(os.path.basename(l['reference']))
            skips.append(l['skipped'])
            m = l['align_to_ref_method']['selected_method']
            if m == 'Auto Swim Align':
                m = 'Automatic SWIM Alignment'
            method.append(m)
            if is_aligned:
                try:
                    snr_report.append(l['align_to_ref_method']['method_results']['snr_report'])
                except:
                    snr_report.append('<No SNR Report>')

        # buttons = ['buttons'] * cfg.datamodel.nSections

        if is_aligned:
            zipped = list(zip(cfg.data.thumbnails(), ref, cfg.data.thumbnails_aligned(),
                              cfg.data.corr_spots_q0(), cfg.data.corr_spots_q1(),
                              cfg.data.corr_spots_q2(), cfg.data.corr_spots_q3(),
                              scale, skips, method, snr_report))
            self._dataframe = pd.DataFrame(zipped, columns=['Img', 'Reference', 'Aligned',
                                                            'Q0', 'Q1', 'Q2', 'Q3',
                                                            'Scale','Skip?', 'Method', 'SNR Report'])

            self.table_view.setColumnWidth(1, 100)
            self.table_view.setColumnWidth(2, 100) # 0 Current
            self.table_view.setColumnWidth(3, 100) # 1 Reference
            self.table_view.setColumnWidth(4, 100) # 2 Aligned
            self.table_view.setColumnWidth(5, 100) # 3 Q0
            self.table_view.setColumnWidth(6, 100) # 4 Q1
            self.table_view.setColumnWidth(7, 100) # 5 Q2
            self.table_view.setColumnWidth(8, 100) # 6 Q3
            self.table_view.setColumnWidth(9, 30)  # 7 Scale
            self.table_view.setColumnWidth(10, 30) # 8 Skip
            self.table_view.setColumnWidth(11, 80) # 9 Method
            # self.table.setColumnWidth(7, 176) # 10 SNR Report
            # self.table.resizeColumnToContents(7)
            # self.table.resizeColumnToContents(8)
            self.table_view.resizeColumnToContents(9)

        else:
            zipped = list(zip(cfg.data.thumbnails(),  ref, scale, skips, method))
            self._dataframe = pd.DataFrame(zipped, columns=['Img', 'Reference', 'Scale',
                                                            'Skip?', 'Method'])
            self.table_view.setColumnWidth(1, 100)
            self.table_view.setColumnWidth(2, 100) # 0
            self.table_view.setColumnWidth(3, 100) # 1
            self.table_view.setColumnWidth(4, 30)  # 2 Scale
            self.table_view.setColumnWidth(5, 30)  # 3 Skip
            self.table_view.setColumnWidth(6, 80)  # 4 Method
            # self.table.setColumnWidth(6, 176)
            self.table_view.resizeColumnToContents(4)


        self.setThumbnailDelegates()
        self._dataframe.index = cfg.data.basefilenames() # set row header titles (!)
        self.load_dataframe()
        # if selection:
        #     self.table.selectRow(selection[0])
        self.table_view.selectRow(cfg.data.layer())

        QApplication.processEvents()

    def setThumbnailDelegates(self):
        logger.info('')
        self.thumb_delegate = ThumbnailDelegate()
        self.table_view.setItemDelegateForColumn(0, self.thumb_delegate)
        self.table_view.setItemDelegateForColumn(1, self.thumb_delegate)
        # if cfg.data.is_aligned_and_generated():
        self.cs_delegate = CorrSpotDelegate()
        self.table_view.setItemDelegateForColumn(2, self.thumb_delegate)
        self.table_view.setItemDelegateForColumn(3, self.cs_delegate)
        self.table_view.setItemDelegateForColumn(4, self.cs_delegate)
        self.table_view.setItemDelegateForColumn(5, self.cs_delegate)
        self.table_view.setItemDelegateForColumn(6, self.cs_delegate)


    def set_selected_row(self, row):
        self._selected_rows = [row]
        if self._selected_rows:
            self.table_view.selectRow(self._selected_rows[0])


    def load_dataframe(self):
        logger.info('Loading dataframe...')
        if isinstance(self._dataframe, pd.DataFrame):
            self.model = PandasModel(self._dataframe)
            self.table_view.setModel(self.model)
            # self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.selection_model = self.table_view.selectionModel()
            self.selection_model.selectionChanged.connect(self.selectionChanged)
        else:
            logger.warning('No datamodel loaded!')

        self.updateRowHeight(self.INITIAL_ROW_HEIGHT)


    def selectionChanged(self):
        logger.info('selection_changed:')
        caller = inspect.stack()[1].function
        if caller != 'clear_selection':
            selection = self.table_view.selectedIndexes()
            self._selected_rows = list(set([row.row() for row in selection]))
            index = self.table_view.currentIndex().row()
            cfg.data.set_layer(index)
            QApplication.processEvents()
        cfg.main_window.dataUpdateWidgets()


    def updateRowHeight(self, h):
        logger.info(f'h = {h}')
        if h < 64:
            return
        parentVerticalHeader = self.table_view.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table_view.setColumnWidth(0, h)
        self.table_view.setColumnWidth(1, h)
        if cfg.data.is_aligned_and_generated():
            self.table_view.setColumnWidth(2, h)
            self.table_view.setColumnWidth(3, h)
            self.table_view.setColumnWidth(4, h)
            self.table_view.setColumnWidth(5, h)
            self.table_view.setColumnWidth(6, h)
        self.table_view.resizeColumnToContents(7)
        self.table_view.resizeColumnToContents(8)

        # self.updateFontSize(h)

    # def updateFontSize(self, s):
    #     # self.table.setFont(QFont('Arial', s))
    #     size = s/4
    #     logger.info(f'size={size}')
    #     if size in range(5,18):
    #         fnt = self.table.font()
    #         fnt.setPointSize(size)
    #         self.table.setFont(fnt)


    # def canFetchMore(self, index):
    #     return self.fileCount < len(self.fileList)
    #
    # def fetchMore(self, index):
    #     remainder = len(self.fileList) - self.fileCount
    #     itemsToFetch = min(100, remainder)
    #
    #     self.beginInsertRows(QtCore.QModelIndex(), self.fileCount,
    #             self.fileCount + itemsToFetch)
    #
    #     self.fileCount += itemsToFetch
    #
    #     self.endInsertRows()
    #
    #     self.numberPopulated.emit(itemsToFetch)


    def canFetchMore(self, index):
        return self.fileCount < len(self.fileList)

    def fetchMore(self, index):
        remainder = len(self.fileList) - self.fileCount
        itemsToFetch = min(100, remainder)

        self.beginInsertRows(QModelIndex(), self.fileCount,
                self.fileCount + itemsToFetch)

        self.fileCount += itemsToFetch

        self.endInsertRows()

        self.numberPopulated.emit(itemsToFetch)


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

#
# class CheckBoxDelegate(QItemDelegate):
#     """A delegate that places a fully functioning QCheckBox cell of the column to which it's applied."""
#     def __init__(self, parent=None):
#         QItemDelegate.__init__(self, parent)
#
#     def createEditor(self, parent, option, index):
#         """Important, otherwise an editor is created if the user clicks in this cell."""
#         return None
#
#     def paint(self, painter, option, index):
#         """Paint a checkbox without the label."""
#         self.drawCheck(painter, option, option.rect, Qt.Unchecked if index.data() == False else Qt.Checked)
#
#     def editorEvent(self, event, model, option, index):
#         '''Change the datamodel in the model and the state of the checkbox if the user presses
#         the left mousebutton and this cell is editable. Otherwise do nothing.'''
#         logger.info(f'index.row()={index.row()}')
#         # event  = <PyQt5.QtGui.QMouseEvent object at 0x1cd5eb310>
#         # model  = <src.ui.layer_view_widget.PandasModel object at 0x1cd5c8040>
#         # option = <PyQt5.QtWidgets.QStyleOptionViewItem object at 0x1d08da2e0
#         # index  = <PyQt5.QtCore.QModelIndex object at 0x1d08da120>
#
#         if not int(index.flags() & Qt.ItemIsEditable) > 0:
#             return False
#         if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
#             self.setModelData(None, model, index) # Change the checkbox-state
#             return True
#         return False
#
#     def setModelData (self, editor, model, index):
#         '''The user wanted to change the old state in the opposite.'''
#         logger.info(f'setModelData | editor={editor} | model={model} | index={index}')
#         model.setData(index, True if index.data() == False else False, Qt.EditRole)


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
        scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
        # scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
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

        # type(index.model()) = <class 'src.ui.layer_view_widget.PandasModel'>
        # 19:21:52 INFO [layer_view_widget.paint:337] type(index.model().data) = <class 'method'>
        # 19:21:52 INFO [layer_view_widget.paint:338] index.model().data = <bound method PandasModel.data of <src.ui.layer_view_widget.PandasModel object at 0x1d4852b80>>
        # 19:21:52 INFO [layer_view_widget.paint:339] type(index.model().itemData) = <class 'builtin_function_or_method'>
        # 19:21:52 INFO [layer_view_widget.paint:340] index.model().itemData = <built-in method itemData of PandasModel object at 0x1d4852b80>

class CorrSpotDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):

        data = index.model().data(index, Qt.DisplayRole)
        if data is None:
            return

        cfg.a = index.model().data
        cfg.b = index.model().itemData
        cfg.i = index
        cfg.d = data
        thumbnail = QImage(data)
        width = option.rect.width()
        height = option.rect.height()
        scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
        painter.drawImage(option.rect.x(), option.rect.y(), scaled)
        painter.setPen(QColor('#FF0000'))
        if cfg.data.is_aligned_and_generated():
            painter.drawText(option.rect.x(), option.rect.y() - 5, '<SNR>')




class PandasModel(QAbstractTableModel):
    """A model to interface a Qt table with pandas dataframe.
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
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if cfg.data.is_aligned_and_generated():
                check_cols = [8]
            else:
                check_cols = [3]
            if index.column() in check_cols:
                return None
            else:
                return str(self._dataframe.iloc[index.row(), index.column()])
        if role == Qt.CheckStateRole:
            if cfg.data.is_aligned_and_generated():
                check_cols = [8]
            else:
                check_cols = [3]

            if index.column() in check_cols:
                # print(">>> datamodel() row,col = %d, %d" % (index.row(), index.column()))
                if self._dataframe.iloc[index.row(), index.column()] == True:
                    return Qt.Checked
                else:
                    return Qt.Unchecked
        # if role == Qt.EditRole:
        #     return self._df.values[index.row()][index.column()]

        # if role == Qt.CheckStateRole: # checked
        #     return 2
        # if role == Qt.CheckStateRole: # un-checked
        #     return 0

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            self._data.iloc[index.row(), index.column()] = value
            return True

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

