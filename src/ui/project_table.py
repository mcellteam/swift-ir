#!/usr/bin/env python3

import os
import json
import time
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QAbstractItemView, \
    QTableWidget, QTableWidgetItem, QSlider
from qtpy.QtCore import Qt, QRect, QAbstractTableModel
from src.ui.thumbnail import ThumbnailFast, CorrSignalThumbnail
from src.helpers import print_exception

import src.config as cfg

logger = logging.getLogger(__name__)

'''
cfg.project_tab.project_table.updateTableDimensions(100)
'''


class ProjectTable(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        # self.INITIAL_ROW_HEIGHT = 128
        self.INITIAL_ROW_HEIGHT = 100
        self.data = None
        self.table = QTableWidget()
        # self.model = TableModel(data='')
        # self.table.setModel(self.model)
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.row_height_slider = Slider(self)
        self.initUI()
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.table.itemClicked.connect(self.userSelectionChanged)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        # self.table.itemClicked.connect(lambda: print('itemClicked was CALLED!'))
        # self.table.itemSelectionChanged.connect(lambda: print('itemselectionChange was CALLED!')) #Works!
        # self.table.cellChanged.connect(lambda: print('cellChanged was CALLED!'))
        # self.table.itemChanged.connect(lambda: print('itemChanged was CALLED!'))

        # self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Fails on TACC for some reason

        # self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
        # self.initUI()

    # def onDoubleClick(self, item=None):
    #     print(type(item))
        # userSelectionChanged
        # cfg.main_window.open_project_selected()

    def selection_changed(self):
        caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        if caller != 'setScaleData':
            if cfg.project_tab._tabs.currentIndex() == 1:
                row = self.table.currentIndex().row()
                # cfg.main_window.tell('Section #%d' % row)
                cfg.data.loc = row
                cfg.main_window.dataUpdateWidgets()


    def set_column_headers(self):
        if cfg.data.is_aligned():
            labels = [ 'Img\nName','Index', 'SNR', 'Img', 'Reference', 'Aligned',
                       # 'Q0', 'Q1', 'Q2', 'Q3',
                       'Top,\nLeft', 'Top,\nRight', 'Bottom,\nLeft', 'Bottom,\nRight', 'Last\nAligned',
                       'Scale', 'Skip?', 'Method', 'SNR Report']
        else:
            labels = [ 'Img\nName','Index','Img', 'Reference', 'Scale', 'Skip?', 'Method' ]
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setColumnCount(len(labels))

    def setScaleRowData(self):
        pass


    def setScaleData(self):
        t = time.time()
        caller = inspect.stack()[1].function
        logger.info('Setting Table Data (caller: %s)...' % caller)
        cur_selection = self.table.currentIndex().row()
        cur_scroll_pos = self.table.verticalScrollBar().value()
        self.setUpdatesEnabled(False)
        self.table.clearContents()
        self.table.clear()
        self.table.setRowCount(0)
        self.set_column_headers() #Critical
        try:
            self.get_data()
        except:
            print_exception()
        try:
            if cfg.data.is_aligned_and_generated():
                for i, row in enumerate(self.data):
                    # logger.info('Inserting row %d' % i)
                    self.table.insertRow(i)
                    snr_4x = cfg.data.snr_components(l=i)
                    for j, item in enumerate(row):
                        if j == 0:
                            # item = '<h4>' + item + '</h4>'
                            # lab = QLabel('\n'.join(textwrap.wrap(item, 20)))
                            # lab.setWordWrap(True)
                            # self.table.setCellWidget(i, j, lab)
                            self.table.setItem(i, j, QTableWidgetItem('\n'.join(textwrap.wrap(str(item), 20))))
                        elif j == 1:
                            # item = '<h3>' + str(item).zfill(5) + '</h3>'
                            # lab = QLabel('\n'.join(textwrap.wrap(item, 20)))
                            # self.table.setCellWidget(i, j, lab)
                            self.table.setItem(i, j, QTableWidgetItem('\n'.join(textwrap.wrap(str(item), 20))))
                        elif j == 2:
                            # item = '<h3>' + ('%.3f' % item).zfill(5) + '</h3>'
                            # lab = QLabel('\n'.join(textwrap.wrap(item, 20)))
                            # self.table.setCellWidget(i, j, lab)
                            self.table.setItem(i, j, QTableWidgetItem('\n'.join(textwrap.wrap(str(item), 20))))
                        elif j in (3, 4):
                            # tn = Thumbnail(self, path=item)
                            tn = ThumbnailFast(self, path=item)
                            self.table.setCellWidget(i, j, tn)
                        elif j == 5:
                            # tn = Thumbnail(self, path=item)
                            # tn = ThumbnailFast(self, path=item, extra=cfg.data.datetime(l=i))
                            tn = ThumbnailFast(self, path=item)
                            self.table.setCellWidget(i, j, tn)
                        elif j in (6, 7, 8, 9):
                            # logger.info(f'j={j}, item={str(item)}')
                            try:
                                # tn = SnrThumbnail(self, path=item, snr=snr_4x[j - 6])
                                tn = CorrSignalThumbnail(self, path=item, snr=snr_4x[j - 6])
                                self.table.setCellWidget(i, j, tn)
                            except:
                                tn = CorrSignalThumbnail(self)
                                tn.set_no_image()
                                self.table.setCellWidget(i, j, tn)
                        else:
                            self.table.setItem(i, j, QTableWidgetItem(str(item)))
            else:
                for i, row in enumerate(self.data):
                    self.table.insertRow(i)
                    for j, item in enumerate(row):
                        if j == 0:
                            # item = '<h4>' + item + '</h4>'
                            # lab = QLabel('\n'.join(textwrap.wrap(item, 20)))
                            # lab.setWordWrap(True)
                            # self.table.setCellWidget(i, j, lab)
                            self.table.setItem(i, j, QTableWidgetItem('\n'.join(textwrap.wrap(str(item), 20))))
                        elif j == 1:
                            # item = '<h3>' + str(item).zfill(5) + '</h3>'
                            # lab = QLabel('\n'.join(textwrap.wrap(item, 20)))
                            # self.table.setCellWidget(i, j, lab)
                            self.table.setItem(i, j, QTableWidgetItem('\n'.join(textwrap.wrap(str(item), 20))))
                        elif j in (2, 3):
                            # thumbnail = Thumbnail(self, path=item)
                            thumbnail = ThumbnailFast(self, path=item)
                            self.table.setCellWidget(i, j, thumbnail)
                        else:
                            self.table.setItem(i, j, QTableWidgetItem(str(item)))
        except:
            print_exception()
        finally:
            self.setUpdatesEnabled(True)
            self.setColumnWidths()
            self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
            self.set_column_headers()

            if cur_selection != -1:
                self.table.selectRow(cur_selection)
            self.table.verticalScrollBar().setValue(cur_scroll_pos)
            # logger.info(f'cur_selection={cur_selection}, cur_scroll_pos={cur_scroll_pos}')
            # cur_selection = self.table.currentIndex().row()
            self.table.update()

            dt = time.time() - t
            logger.info('Table Load Time %s' %str(dt))


    def setColumnWidths(self):
        if cfg.data.is_aligned_and_generated():
            self.table.setColumnWidth(0, 128)  # 0 index
            self.table.setColumnWidth(1, 60)   # 1 Filename
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
        else:
            self.table.setColumnWidth(0, 128)
            self.table.setColumnWidth(1, 60)
            self.table.setColumnWidth(2, 100)
            self.table.setColumnWidth(3, 100)
            self.table.setColumnWidth(4, 50)
            self.table.setColumnWidth(5, 50)
            self.table.setColumnWidth(6, 80)

    def updateTableDimensions(self, h):
        # logger.info(f'Updating table dimensions...')
        # logger.info('')
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)

        if cfg.data.is_aligned_and_generated():
            self.table.setColumnWidth(3, h)
            self.table.setColumnWidth(4, h)
            self.table.setColumnWidth(5, h)
            self.table.setColumnWidth(6, h)
            self.table.setColumnWidth(7, h)
            self.table.setColumnWidth(8, h)
            self.table.setColumnWidth(9, h)
        else:
            self.table.setColumnWidth(2, h)
            self.table.setColumnWidth(3, h)


    def get_data(self):
        # logger.info('')
        is_aligned = cfg.data.is_aligned_and_generated()
        # logger.critical('is aligned? %r' % is_aligned)
        try:
            try:     scale = [cfg.data.scale_pretty()] * cfg.data.nSections
            except:  scale = ['Unknown'] * cfg.data.nSections; print_exception()
            try:     ref = cfg.data.thumbnails_ref()
            except:  ref = ['Unknown'] * len(cfg.data); print_exception()
            indexes, skips, base, method, snr_report, test, datetime = [], [], [], [], [], [], []
            for i, l in enumerate(cfg.data.stack()):
                indexes.append(i)
                try:     skips.append(l['skipped'])
                except:  skips.append('?'); print_exception()
                try:
                    m = l['alignment']['selected_method']
                    if m == 'Auto-SWIM': m = 'Automatic SWIM Alignment'
                    method.append(m)
                except:
                    method.append('Unknown')
                if is_aligned:
                    try:     snr_report.append(l['alignment']['method_results']['snr_report'])
                    except:  snr_report.append('<No SNR Report>')
                    try:     datetime.append(l['alignment']['method_results']['datetime'])
                    except:  datetime.append('N/A')


            if is_aligned:
                self.data = list(zip(cfg.data.basefilenames(), indexes, cfg.data.snr_list(),
                                  cfg.data.thumbnails(), ref, cfg.data.thumbnails_aligned(),
                                  cfg.data.corr_spots_q0(), cfg.data.corr_spots_q1(),
                                  cfg.data.corr_spots_q2(), cfg.data.corr_spots_q3(), datetime,
                                  scale, skips, method, snr_report))
            else:
                self.data = list(zip(cfg.data.basefilenames(), indexes, cfg.data.thumbnails(),
                                  ref, scale, skips, method))
            # print(str(list(zipped)))
            # return self.data
        except:
            print_exception()


    # def updateSliderMaxVal(self):
    #     if cfg.data.is_aligned():
    #         thumb_path = os.path.join(cfg.data.dest(), cfg.data.scale(), 'thumbnails_aligned')
    #     else:
    #         thumb_path = os.path.join(cfg.data.dest(), 'thumbnails')
    #     max_val = max(ImageSize(next(absFilePaths(thumb_path))))
    #     # self.row_height_slider.setMaximum(max_val)


    def initUI(self):
        logger.info('Initializing Table UI...')

        self.table.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # self.project_table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setTextElideMode(Qt.ElideMiddle)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.row_height_slider.setValue(self.INITIAL_ROW_HEIGHT)
        self.row_height_slider.valueChanged.connect(self.updateTableDimensions)
        self.row_height_slider.setMaximumWidth(128)

        # self.row_height_slider.valueChanged.connect(self.updateFontSize)
        # self.row_height_widget = QWidget()
        # self.thumbnailPixelsLabel = QLabel()
        # self.row_height_hlayout = QHBoxLayout()
        # self.row_height_hlayout.setContentsMargins(2, 2, 2, 2)
        # self.row_height_hlayout.addWidget(QLabel('Thumbnail Size:'))
        # self.row_height_hlayout.addWidget(self.row_height_slider, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.row_height_hlayout.addWidget(self.thumbnailPixelsLabel, alignment=Qt.AlignmentFlag.AlignLeft)
        # self.row_height_widget.setLayout(self.row_height_hlayout)

        logger.info('Initializing Table Controls...')

        self.controls = QWidget()
        self.controls.setObjectName('controls')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.row_height_slider, alignment=Qt.AlignLeft)
        # self.controls_hlayout.addWidget(self.font_size_widget)
        hbl.addStretch()
        self.controls.setLayout(hbl)

        logger.info('Initializing Table Layout...')

        layout =QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addWidget(self.controls)

        self.setLayout(layout)
#
#
# class SnrThumbnail(QWidget):
#
#     def __init__(self, parent, path, snr='<SNR>'):
#         super().__init__(parent)
#         # thumbnail = QLabel(self)
#         thumbnail = ScaledPixmapLabel(self)
#         try:
#             pixmap = QPixmap(path)
#             thumbnail.setPixmap(pixmap)
#             thumbnail.setScaledContents(True)
#             snr = QLabel(snr)
#             snr.setStyleSheet('color: #ff0000')
#         except:
#             snr = QLabel('<h5>' + str(snr) + '</h5>')
#             snr.setStyleSheet('background-color: #141414')
#             print_exception()
#             logger.warning(f'WARNING path={path}, snr={snr}')
#         layout = QGridLayout()
#         layout.setContentsMargins(1, 1, 1, 1)
#         layout.addWidget(thumbnail, 0, 0)
#         layout.addWidget(snr, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
#         self.setLayout(layout)
#
#
# class Thumbnail(QWidget):
#
#     def __init__(self, parent, path):
#         super().__init__(parent)
#         self.thumbnail = ScaledPixmapLabel(self)
#         self.pixmap = QPixmap(path)
#         self.thumbnail.setPixmap(self.pixmap)
#         self.thumbnail.setScaledContents(True)
#         self.layout = QGridLayout()
#         self.layout.setContentsMargins(1, 1, 1, 1)
#         self.layout.addWidget(self.thumbnail, 0, 0)
#         self.setLayout(self.layout)
#
#
# class ScaledPixmapLabel(QLabel):
#     def __init__(self, parent):
#         super().__init__(parent)
#         self.setScaledContents(True)
#
#     def paintEvent(self, event):
#         if self.pixmap():
#             pm = self.pixmap()
#             try:
#                 originalRatio = pm.width() / pm.height()
#                 currentRatio = self.width() / self.height()
#                 if originalRatio != currentRatio:
#                     qp = QPainter(self)
#                     pm = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
#                     rect = QRect(0, 0, pm.width(), pm.height())
#                     rect.moveCenter(self.rect().center())
#                     qp.drawPixmap(rect, pm)
#                     return
#             except ZeroDivisionError:
#                 # logger.warning('Cannot divide by zero')
#                 # print_exception()
#                 pass
#         super().paintEvent(event)


class Slider(QSlider):
    def __init__(self, parent):
        super().__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.setMinimum(16)
        self.setMaximum(512)
        self.setSingleStep(1)
        self.setPageStep(2)
        self.setTickInterval(1)





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

