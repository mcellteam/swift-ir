#!/usr/bin/env python3

import os
import json
import copy
import time
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QAbstractItemView, \
    QTableWidget, QTableWidgetItem, QSlider, QLabel, QPushButton, QSizePolicy
from qtpy.QtCore import Qt, QRect, QAbstractTableModel, Signal
from qtpy.QtGui import QPainter, QPixmap, QImage
from src.ui.thumbnail import ThumbnailFast, CorrSignalThumbnail
from src.ui.layouts import VBL, HBL, VWidget, HWidget
from src.ui.timer import Timer
from src.helpers import print_exception
import qtawesome as qta

import src.config as cfg

logger = logging.getLogger(__name__)


class ProjectTable(QWidget):
    onTableFinishedLoading = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        # self.INITIAL_ROW_HEIGHT = 128
        self.INITIAL_ROW_HEIGHT = 80
        self.image_col_width = self.INITIAL_ROW_HEIGHT
        self.data = None
        self.table = QTableWidget()
        self.table.hide()
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.row_height_slider = Slider(self)
        self.row_height_slider.setMinimum(28)
        self.row_height_slider.setMaximum(256)
        self.initUI()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.table.itemClicked.connect(self.userSelectionChanged)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        # self.table.itemPressed.connect(lambda: print('itemPressed was emitted!'))
        # self.table.cellActivated.connect(lambda: print('cellActivated was emitted!'))
        # self.table.currentItemChanged.connect(lambda: print('currentItemChanged was emitted!'))
        # self.table.itemDoubleClicked.connect(lambda: print('itemDoubleClicked was emitted!'))
        # self.table.itemSelectionChanged.connect(lambda: print('itemselectionChanged was emitted!')) #Works!
        # self.table.cellChanged.connect(lambda: print('cellChanged was emitted!'))
        # self.table.cellClicked.connect(lambda: print('cellClicked was emitted!'))
        # self.table.itemChanged.connect(lambda: print('itemChanged was emitted!'))
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        # self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Fails on TACC for some reason
        # self.tableFinishedLoading.connect(self.onTableFinishedLoading)
        self.table.hide()

        self.table.setStyleSheet("font-size: 10px;")



    # def onDoubleClick(self, item=None):
    #     logger.critical('')
    #     # print(cur_method(item))
    #     # userSelectionChanged
    #     # cfg.main_window.open_project_selected()

    def setImage(self, row, col, imagePath):
        image = ImageWidget(imagePath, self)
        self.table.setCellWidget(row, col, image)


    def get_selection(self):
        selected = []
        for index in sorted(self.table.selectionModel().selectedRows()):
            selected.append(index.row())
        return selected

    def selection_changed(self):
        caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}')
        if caller not in ('initTableData', 'updateTableData'):
            if cfg.project_tab._tabs.currentIndex() == 2:
                row = self.table.currentIndex().row()
                # cfg.main_window.tell('Section #%d' % row)
                # cfg.data.zpos = row
                cfg.mw.setZpos(row)
        selection = self.get_selection()
        if selection:
            r_min = min(selection)
            r_max = max(selection)
            # cfg.main_window.sectionRangeSlider.setStart(r_min)
            # cfg.main_window.sectionRangeSlider.setEnd(r_max)


    def set_column_headers(self):
        labels = ['Z-index', 'Img\nName', 'SNR', 'Img', 'Reference', 'Aligned',
                  'Match\nSignal 1', 'Match\nSignal 2', 'Match\nSignal 3', 'Match\nSignal 4', 'Last\nAligned',
                  'Scale', 'Skip?', 'Method', 'SNR Report']
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setColumnCount(len(labels))


    def initTableData(self):
        self.table.hide()
        t = time.time()
        timer = Timer()
        timer.start()
        caller = inspect.stack()[1].function
        logger.info(f'')
        # cfg.main_window.tell('Updating Table Data...')
        self.table.setUpdatesEnabled(False)
        # cfg.mw.showZeroedPbar(set_n_processes=1, pbar_max=len(cfg.data))
        cfg.mw.showZeroedPbar(set_n_processes=False, pbar_max=len(cfg.data))
        # self.table.clearContents()
        # self.table.clear()
        # self.table.setRowCount(0)
        self.set_column_headers() #Critical
        cnt = 0
        cfg.mw.showZeroedPbar(set_n_processes=1, pbar_max=cfg.data.count)
        try:
            for row in range(0, len(cfg.data)):
                if cfg.CancelProcesses:
                    logger.warning("Canceling table load!")
                    return
                cfg.main_window.setPbarText('Loading %s...' % cfg.data.base_image_name(l=row))
                cnt += 1
                cfg.main_window.updatePbar(cnt)
                self.table.insertRow(row)
                self.set_row_data(row=row)

        except:
            print_exception()
        finally:
            timer.report()
            self.btn_splash_load_table.hide()
            self.table.setUpdatesEnabled(True)
            cfg.mw.hidePbar()
            self.setColumnWidths()
            # self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
            self.updateTableDimensions(self.row_height_slider.value())
            self.set_column_headers()
            # if cur_selection != -1:
            #     self.table.selectRow(cur_selection)
            # self.table.verticalScrollBar().setValue(cur_scroll_pos)
            # logger.info(f'cur_selection={cur_selection}, cur_scroll_pos={cur_scroll_pos}')
            # cur_selection = self.table.currentIndex().row()


            self.table.update()
            timer.report()
            self.table.show()
            logger.info('Data table finished loading.')

        logger.info(f'<<<< initTableData [{caller}]')

    def updateTableData(self):
        cfg.mw.showZeroedPbar(set_n_processes=1, pbar_max=len(cfg.data))

        if self.btn_splash_load_table.isVisible():
            self.initTableData()
            return

        cur_selection = self.table.currentIndex().row()
        cur_scroll_pos = self.table.verticalScrollBar().value()
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clear()
            self.table.clearContents()
            self.set_column_headers()  # Critical
            for row in range(0,len(cfg.data)):
                cfg.main_window.setPbarText('Loading %s...' % cfg.data.base_image_name(l=row))
                cfg.nProcessDone += 1
                cfg.main_window.updatePbar(cfg.nProcessDone)
                self.set_row_data(row=row)

        except:
            print_exception()
        finally:
            cfg.mw.hidePbar()
            if cur_selection != -1:
                self.table.selectRow(cur_selection)
            self.table.verticalScrollBar().setValue(cur_scroll_pos)
            cfg.nProcessDone += 1
            cfg.main_window.updatePbar(cfg.nProcessDone)
            self.table.setUpdatesEnabled(True)


    def setColumnWidths(self):
        self.table.setColumnWidth(0, 64)  # 0 index
        self.table.setColumnWidth(1, 128)   # 1 Filename
        self.table.setColumnWidth(2, 60)   # 2 SNR
        self.table.setColumnWidth(3, 100)  # 3 Current
        self.table.setColumnWidth(4, 100)  # 4 Reference
        self.table.setColumnWidth(5, 100)  # 5 Aligned
        self.table.setColumnWidth(6, 100)  # 6 Q0
        self.table.setColumnWidth(7, 100)  # 7 Q1
        self.table.setColumnWidth(8, 100)  # 8 Q2
        self.table.setColumnWidth(9, 100) # 9 Q3
        self.table.setColumnWidth(10, 80) # 10 Last Aligned datetime
        self.table.setColumnWidth(11, 50) # 11 Scale
        self.table.setColumnWidth(12, 50)  # 12 Skip
        self.table.setColumnWidth(13, 120)  # 13 Method
        self.table.setColumnWidth(14, 120) # 14 SNR_report


    def updateTableDimensions(self, h):
        # caller = inspect.stack()[1].function
        self.image_col_width = h
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table.setColumnWidth(3, h)
        self.table.setColumnWidth(4, h)
        self.table.setColumnWidth(5, h)
        self.table.setColumnWidth(6, h)
        self.table.setColumnWidth(7, h)
        self.table.setColumnWidth(8, h)
        self.table.setColumnWidth(9, h)
        size = max(min(int(11 * (max(h, 1) / 80)), 14), 8)
        # self.table.setStyleSheet(f'font-size: {size}px;')


    def get_row_data(self, s=None, l=None):
        if s == None: s = cfg.data.scale
        if l == None: l = cfg.data.zpos

        rowData = []
        dest = cfg.data.dest()
        method = cfg.data['data']['scales'][s]['stack'][l]['current_method']
        index = ('%d'%l).zfill(5)
        basename = cfg.data.filename_basename(s=s, l=l)
        snr_avg = cfg.data.snr(s=s, l=l, method=method)
        tn_tra = cfg.data.thumbnail_tra(s=s, l=l)
        tn_ref = cfg.data.thumbnail_ref(s=s, l=l)
        tn_aligned = cfg.data.thumbnail_aligned(s=s, l=l)
        fn, extension = os.path.splitext(basename)
        sig0 = os.path.join(dest, s, 'signals', '%s_%s_0%s' % (fn, method, extension))
        sig1 = os.path.join(dest, s, 'signals', '%s_%s_1%s' % (fn, method, extension))
        sig2 = os.path.join(dest, s, 'signals', '%s_%s_2%s' % (fn, method, extension))
        sig3 = os.path.join(dest, s, 'signals', '%s_%s_3%s' % (fn, method, extension))
        try:
            last_aligned = cfg.data['data']['scales'][s]['stack'][l]['alignment']['method_results']['datetime']
        except:
            last_aligned = 'N/A'
        scale = cfg.data.scale_pretty(s=s)
        skip = cfg.data.skipped(s=s, l=l)
        method = method
        snr_report = cfg.data.snr_report(s=s, l=l)

        return [index, basename, snr_avg, tn_tra, tn_ref, tn_aligned, sig0, sig1, sig2, sig3, last_aligned, scale, skip, method, snr_report]


    def set_row_data(self, row):
        scale = cfg.data.scale

        snr_4x = copy.deepcopy(cfg.data.snr_components(s=scale, l=row))
        row_data = self.get_row_data(s=scale, l=row)
        method = cfg.data.method(s=scale, l=row)
        if method == 'grid-custom':
            regions = copy.deepcopy(cfg.data.get_grid_custom_regions(l=row))
        # for j, item in enumerate(row):
        for col in range(0, len(row_data)):
            if col == 0:
                self.table.setItem(row, col, QTableWidgetItem('\n'.join(textwrap.wrap(str(row_data[0]), 20))))
            elif col == 1:
                self.table.setItem(row, col, QTableWidgetItem('\n'.join(textwrap.wrap(str(row_data[1]), 20))))
            elif col == 2:
                self.table.setItem(row, col, QTableWidgetItem('\n'.join(textwrap.wrap(str(row_data[2]), 20))))
            elif col == 3:
                tn = ThumbnailFast(self, path=row_data[3], name='reference-table', s=scale, l=row)
                self.table.setCellWidget(row, col, tn)
            elif col == 4:
                tn = ThumbnailFast(self, path=row_data[4], name='transforming-table', s=scale, l=row)
                self.table.setCellWidget(row, col, tn)
            elif col == 5:
                tn = ThumbnailFast(self, path=row_data[5])
                self.table.setCellWidget(row, col, tn)
            elif col == 6:
                try:
                    if method == 'grid-custom':
                        assert regions[0] == 1
                    else:
                        assert snr_4x[0] > 0.0

                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms0')
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms0')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 7:

                try:
                    if method == 'grid-custom':
                        assert regions[1] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms1')
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms1')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 8:
                try:
                    if method == 'grid-custom':
                        assert regions[2] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms2')
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms2')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 9:
                try:
                    if method == 'grid-custom':
                        assert regions[3] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms3')
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms3')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            else:
                self.table.setItem(row, col, QTableWidgetItem(str(row_data[col])))

    def initUI(self):
        logger.info('')

        # self.table.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setTextElideMode(Qt.ElideMiddle)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.row_height_slider.setValue(self.INITIAL_ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.updateTableDimensions)
        self.row_height_slider.setMaximumWidth(128)
        self.btnReloadTable = QPushButton('Reload')
        # self.btnReloadTable.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.btnReloadTable.setFixedHeight(18)
        self.btnReloadTable.setFixedWidth(70)
        self.btnReloadTable.clicked.connect(self.updateTableData)


        # self.loadedLabel = QLabel()

        self.controls = QWidget()
        self.controls.setObjectName('controls')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 2, 0, 2)
        lab = QLabel('Table Size:')
        lab.setStyleSheet("font-size: 10px;")
        hbl.addWidget(lab, alignment=Qt.AlignLeft)
        hbl.addWidget(self.row_height_slider, alignment=Qt.AlignLeft)
        hbl.addWidget(self.btnReloadTable, alignment=Qt.AlignLeft)
        # self.controls_hlayout.addWidget(self.font_size_widget)
        hbl.addStretch()
        self.controls.setMaximumHeight(24)
        self.controls.setLayout(hbl)

        # self.btn_splash_load_table = QPushButton('Load Table')
        self.btn_splash_load_table = QPushButton(' Load Table')
        self.btn_splash_load_table.setIcon(qta.icon("fa.download", color='#f3f6fb'))
        self.btn_splash_load_table.clicked.connect(self.initTableData)
        self.btn_splash_load_table.setStyleSheet("""font-size: 18px; font-weight: 600; color: #f3f6fb;""")
        self.btn_splash_load_table.setFixedSize(160,80)

        layout = VBL()
        layout.addWidget(self.btn_splash_load_table, alignment=Qt.AlignCenter)
        layout.addWidget(self.table)
        layout.addWidget(self.controls, alignment=Qt.AlignBottom)
        self.setLayout(layout)


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
                # print_exception()
                pass
        super().paintEvent(event)


class Slider(QSlider):
    def __init__(self, parent):
        super().__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(16)
        self.setMaximum(150)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)


class ClickLabel(QLabel):
    clicked=Signal()
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

    def mousePressEvent(self, ev):
        self.clicked.emit()


# class ThumbnailDelegate(QStyledItemDelegate):
#
#     def paint(self, painter, option, index):
#         data = index.model().data(index, Qt.DisplayRole)
#         if data is None:
#             return
#         thumbnail = QImage(data)
#         width = option.rect.width()
#         height = option.rect.height()
#         scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
#         painter.drawImage(option.rect.x(), option.rect.y(), scaled)

# class CorrSpotDelegate(QStyledItemDelegate):
#
#     def paint(self, painter, option, index):
#
#         data = index.model().data(index, Qt.DisplayRole)
#         if data is None:
#             return
#
#         cfg.a = index.model().data
#         cfg.b = index.model().itemData
#         cfg.i = index
#         # cfg.i.data()  # !!! This gives the path
#         cfg.d = data
#         thumbnail = QImage(data)
#         width = option.rect.width()
#         height = option.rect.height()
#         scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
#         painter.drawImage(option.rect.x(), option.rect.y(), scaled)
#         painter.setPen(QColor('#FF0000'))
#         if cfg.data.is_aligned_and_generated():
#             painter.drawText(option.rect.x(), option.rect.y() - 5, '<SNR>')



class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data[0])


class ImageWidget(QWidget):

    def __init__(self, imagePath, parent):
        super(ImageWidget, self).__init__(parent)
        #             pixmap = QPixmap(path)
        #             thumbnail.setPixmap(pixmap)
        #             thumbnail.setScaledContents(True)
        self.picture = QPixmap(imagePath)

    # def paintEvent(self, event):
    #     painter = QPainter(self)
    #     painter.drawPixmap(0, 0, self.picture)

    def paint(self, painter, option, index):
        data = index.model().data(index, Qt.DisplayRole)
        if data is None:
            return
        thumbnail = QImage(data)
        width = option.rect.width()
        height = option.rect.height()
        scaled = thumbnail.scaled(width, height, aspectRatioMode=Qt.KeepAspectRatio)
        painter.drawImage(option.rect.x(), option.rect.y(), scaled)


# cfg.pt.project_table.setImage(2,3,'/Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/thumbnails_aligned/funky4.tif')