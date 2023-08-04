#!/usr/bin/env python3

import os
import json
import copy
import time
import inspect
import logging
import textwrap

from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QAbstractItemView, QApplication, \
    QTableWidget, QTableWidgetItem, QSlider, QLabel, QPushButton, QSizePolicy, QFrame, QHeaderView, QAction, QMenu, \
    QTextEdit
from qtpy.QtCore import Qt, QRect, QAbstractTableModel, Signal, QEvent, QRunnable
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
        self.INITIAL_ROW_HEIGHT = 70
        self.image_col_width = self.INITIAL_ROW_HEIGHT
        self.data = None
        self._ms0 = []
        self._ms1 = []
        self._ms2 = []
        self._ms3 = []
        self.installEventFilter(self)
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setSortingEnabled(False)
        self.table.setShowGrid(True)
        self.row_height_slider = Slider(self)
        self.row_height_slider.setMinimum(28)
        self.row_height_slider.setMaximum(256)
        self.initUI()
        # self.table.horizontalHeader().setHighlightSections(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.table.itemClicked.connect(self.userSelectionChanged)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        # self.table.itemPressed.connect(self.selection_changed)
        # self.table.itemPressed.connect(lambda: print('itemPressed was emitted!'))
        # self.table.cellActivated.connect(lambda: print('cellActivated was emitted!'))
        # self.table.currentItemChanged.connect(lambda: print('currentItemChanged was emitted!'))
        # self.table.itemDoubleClicked.connect(lambda: print('itemDoubleClicked was emitted!'))
        # self.table.itemSelectionChanged.connect(lambda: print('itemselectionChanged was emitted!')) #Works!
        # self.table.cellChanged.connect(lambda: print('cellChanged was emitted!'))
        # self.table.cellClicked.connect(lambda: print('cellClicked was emitted!'))
        # self.table.itemChanged.connect(lambda: print('itemChanged was emitted!'))
        # self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        # self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Fails on TACC for some reason
        # self.tableFinishedLoading.connect(self.onTableFinishedLoading)
        # self.onTableFinishedLoading.connect(lambda: logger.critical("\n\n\nTable finished loading!\n\n"))
        # self.onTableFinishedLoading.connect(lambda:cfg.mw.set_status("Table finished loading."))
        header = self.table.horizontalHeader()
        header.setFrameStyle(QFrame.Box | QFrame.Plain)
        header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
        self.table.setHorizontalHeader(header)

        self.m = {'grid-default': 'Default Grid',
             'grid-custom': 'Custom Grid',
             'manual-hint':'Match Region',
             'manual-strict':'Match Point'}

        self.table.setStyleSheet("""
        QWidget {
            background-color: #f3f6fb;
            color: #161c20;
            font-size: 9px;
        }

        QHeaderView::section {
            font-size: 9pt;
        }

        QTableWidget {
            gridline-color: #161c20;
            font-size: 9pt;
        }

        QTableWidget QTableCornerButton::section {
            background-color: #f3f6fb;
            border: 1px solid #161c20;
        }
        QTableWidget::item:selected{ background-color: #dadada;}

        QTableWidget::item {padding: 2px; color: #161c20;}
        """)



    def getSelectedRows(self):
        logger.info(f"{[x.row() for x in self.table.selectionModel().selectedRows()]}")
        return [x.row() for x in self.table.selectionModel().selectedRows()]

    def getSelectedProjects(self):
        selected_rows = self.getSelectedRows()
        logger.info(f'selected row: {selected_rows}')
        logger.info(f"{[self.table.item(r, 1).text() for r in selected_rows]}")
        return [self.table.item(r, 1).text() for r in self.getSelectedRows()]

    def getNumRowsSelected(self):
        return len(self.getSelectedRows())



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
        logger.info(f'[{caller}]')
        if caller not in ('initTableData', 'updateTableData'):
            if cfg.project_tab._tabs.currentIndex() == 2:
                row = self.table.currentIndex().row()
                # cfg.main_window.tell('Section #%d' % row)
                # cfg.data.zpos = row
                cfg.mw.setZpos(row)
        # selection = self.get_selection()
        # if selection:
        #     r_min = min(selection)
        #     r_max = max(selection)
        #     # cfg.main_window.sectionRangeSlider.setStart(r_min)
        #     # cfg.main_window.sectionRangeSlider.setEnd(r_max)


    def set_column_headers(self):
        labels = ['Z-index', 'Section vs.\nReference', 'SNR/\nMethod', 'Last\nAligned', 'Reference', 'Transforming', 'Aligned\nResult',
                  'Match\nSignal 1', 'Match\nSignal 2', 'Match\nSignal 3', 'Match\nSignal 4', 'Notes']
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setColumnCount(len(labels))


    def initTableData(self):
        self.btn_splash_load_table.setText("Loading...")

        self._ms0 = [None] * len(cfg.data)
        self._ms1 = [None] * len(cfg.data)
        self._ms2 = [None] * len(cfg.data)
        self._ms3 = [None] * len(cfg.data)


        self.wTable.hide()
        t = time.time()
        timer = Timer()
        timer.start()
        caller = inspect.stack()[1].function
        logger.info(f'')
        # cfg.main_window.tell('Updating Table Data...')
        self.table.setUpdatesEnabled(False)
        self.table.clearContents()
        self.table.clear()
        self.table.setRowCount(0)
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

            self.btn_splash_load_table.setText("Load Table")

            self.updateTableTitle()
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
            self.wTable.show()

            logger.info('Data table finished loading.')

        logger.info(f'<<<< initTableData [{caller}]')

    def updateTableTitle(self):
        siz = cfg.data.image_size()
        self.scaleLabel.setText(f"{cfg.data.scale_pretty()} | {siz[0]}x{siz[1]}px")

    def updateTableData(self):
        logger.info('')
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
            self.updateTableTitle()
            cfg.mw.hidePbar()
            if cur_selection != -1:
                self.table.selectRow(cur_selection)
            self.table.verticalScrollBar().setValue(cur_scroll_pos)
            cfg.nProcessDone += 1
            cfg.main_window.updatePbar(cfg.nProcessDone)
            self.table.setUpdatesEnabled(True)


    def setColumnWidths(self):
        self.table.setColumnWidth(0, 90)  # 0 index
        self.table.setColumnWidth(1, 170)   # 1 Filename
        self.table.setColumnWidth(2, 80)   # 2 SNR
        self.table.setColumnWidth(3, 80)  # 10 Last Aligned datetime
        self.table.setColumnWidth(4, 100)  # 3 Current
        self.table.setColumnWidth(5, 100)  # 4 Reference
        self.table.setColumnWidth(6, 100)  # 5 Aligned
        self.table.setColumnWidth(7, 100)  # 6 Q0
        self.table.setColumnWidth(8, 100)  # 7 Q1
        self.table.setColumnWidth(9, 100)  # 8 Q2
        self.table.setColumnWidth(10, 100) # 9 Q3
        self.table.setColumnWidth(11, 100) # 9 Q3




    def updateTableDimensions(self, h):
        # caller = inspect.stack()[1].function

        # header = self.table.horizontalHeader()
        # header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.image_col_width = h
        parentVerticalHeader = self.table.verticalHeader()
        for section in range(parentVerticalHeader.count()):
            parentVerticalHeader.resizeSection(section, h)
        self.table.setColumnWidth(1, h*2)
        self.table.setColumnWidth(2, h)
        self.table.setColumnWidth(3, h)
        self.table.setColumnWidth(4, h)
        self.table.setColumnWidth(5, h)
        self.table.setColumnWidth(6, h)
        self.table.setColumnWidth(7, h)
        self.table.setColumnWidth(8, h)
        self.table.setColumnWidth(9, h)
        self.table.setColumnWidth(10, h)
        # size = max(min(int(11 * (max(h, 1) / 80)), 14), 8)
        # self.table.setStyleSheet(f'font-size: {size}px;')


    def jump_to_edit(self, requested) -> None:
        cfg.mw.setZpos(requested)
        cfg.pt._tabs.setCurrentIndex(1)


    def jump_to_view(self, requested) -> None:
        cfg.mw.setZpos(requested)
        cfg.pt._tabs.setCurrentIndex(0)

    def request_refresh(self, requested) -> None:
        self.set_row_data(row=requested)


    def get_row_data(self, s=None, l=None):
        if s == None: s = cfg.data.scale_key
        if l == None: l = cfg.data.zpos

        rowData = []
        dest = cfg.data.dest()
        method = cfg.data['data']['scales'][s]['stack'][l]['alignment']['swim_settings']['method']
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
        notes = cfg.data.notes(s=s,l=l)
        try:
            last_aligned = cfg.data['data']['scales'][s]['stack'][l]['alignment']['method_results']['datetime']
        except:
            last_aligned = 'N/A'
        return [index, basename, snr_avg, last_aligned, tn_ref, tn_tra, tn_aligned, sig0, sig1, sig2, sig3, notes]


    def set_row_data(self, row):
        scale = cfg.data.scale_key

        snr_4x = copy.deepcopy(cfg.data.snr_components(s=scale, l=row))
        row_data = self.get_row_data(s=scale, l=row)
        method = cfg.data.method(s=scale, l=row)
        if method == 'grid-custom':
            regions = copy.deepcopy(cfg.data.get_grid_custom_regions(l=row))
        # for j, item in enumerate(row):

        self.all_notes = []

        self._ms = []

        for col in range(0, len(row_data)):

            if col == 0:
                # self.table.setItem(row, col, QTableWidgetItem('\n'.join(textwrap.wrap(str(row_data[0]), 20))))
                # self.table.setCellWidget(row, col, tn)

                b0 = QPushButton('View')
                b0.clicked.connect(lambda state, x=row: self.jump_to_view(x))
                # b0.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20; padding:1px; width: 22px; height: 14px; ")
                b0.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20; padding:1px; ")
                b1 = QPushButton('Edit')
                b1.clicked.connect(lambda state, x=row: self.jump_to_edit(x))
                # b1.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20;  padding:1px; width: 22px; height: 14px; ")
                b1.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20;  padding:1px; ")
                b2 = QPushButton('Refresh Row')
                b2.clicked.connect(lambda state, x=row: self.request_refresh(x))
                b2.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20;  padding:1px; ")
                btns = VWidget(HWidget(b0, b1),b2)
                # btns.setStyleSheet("font-size: 12px; background-color: #161c20;")

                lab = QLabel(str(row_data[0]))
                lab.setAlignment(Qt.AlignCenter)
                # lab.setStyleSheet("font-size: 12px; background-color: #ede9e8; color: #161c20;")
                lab.setStyleSheet("font-size: 11px; color: #161c20; font-weight: 600; padding: 0px; margin: 0px;")

                w = QWidget()
                vbl = VBL(lab, btns)
                vbl.setSpacing(4)
                vbl.setAlignment(Qt.AlignVCenter)
                w.setLayout(vbl)
                w.setStyleSheet("background:transparent;")
                # w.setStyleSheet("QWidget {border-radius: 6px; border: 1px solid #ede9e8;}")

                self.table.setCellWidget(row, col, w)
            elif col == 1:
                lab1 = QLabel(cfg.data.filename_basename(l=row))
                lab1.setStyleSheet("font-weight: 600; font-size: 12px; background: transparent;")
                if cfg.data.skipped(l=row):
                    lab2 = QLabel('* Exclude')
                    lab2.setStyleSheet("font-size: 10px; color: #d0342c; padding:2px; background: transparent;")
                    vw = VWidget(lab1,lab2)
                    vw.layout.setAlignment(Qt.AlignVCenter)
                else:
                    lab2 = QLabel("Reference:")
                    lab2.setStyleSheet("font-size: 9px; background: transparent;")
                    lab3_str = cfg.data.reference_basename(l=row)
                    ref_offset = cfg.data.get_ref_index_offset(l=row)
                    if ref_offset > 1:
                        lab3_str += f' <span style="color: #d0342c;"><b>[{-ref_offset + 1}]</b></span>'
                    lab3 = QLabel(lab3_str)
                    lab3.setStyleSheet("font-size: 9px; font-weight: 600; background: transparent;")
                    vw = VWidget(lab1,lab2,lab3)
                    vw.setStyleSheet("background: transparent;")
                    vw.layout.setAlignment(Qt.AlignVCenter)
                self.table.setCellWidget(row, col, vw)
            elif col == 2:
                lab1 = QLabel('%.3g' % float(row_data[2]))
                lab1.setStyleSheet("font-weight: 600; font-size: 11px;")
                m = self.m[method]
                lab2 = QLabel(m)
                if m == 'Default Grid':
                    lab2.setStyleSheet("font-size: 10px; color: #00BF00;")
                elif method == 'Custom Grid':
                    lab2.setStyleSheet("font-size: 10px; color: #8f99fb;")
                else:
                    lab2.setStyleSheet("font-size: 10px; color: #010fcc;")

                vw = VWidget(lab1,lab2)
                vw.layout.setAlignment(Qt.AlignCenter)
                vw.setStyleSheet("background:transparent;")
                self.table.setCellWidget(row, col, vw)
            elif col == 3:
                self.table.setItem(row, col, QTableWidgetItem(str(row_data[col])))
            elif col == 4:
                tn = ThumbnailFast(self, path=row_data[col], name='reference-table', s=scale, l=row)
                if cfg.data.skipped(l=row):
                    tn.set_no_image()
                self.table.setCellWidget(row, col, tn)
            elif col == 5:
                tn = ThumbnailFast(self, path=row_data[col], name='transforming-table', s=scale, l=row)
                if cfg.data.skipped(l=row):
                    tn.set_no_image()
                self.table.setCellWidget(row, col, tn)
            elif col == 6:
                tn = ThumbnailFast(self, path=row_data[col])
                if cfg.data.skipped(l=row):
                    tn.set_no_image()
                self.table.setCellWidget(row, col, tn)
            elif col == 7:
                try:
                    if method == 'grid-custom':
                        assert regions[0] == 1
                    else:
                        assert snr_4x[0] > 0.0

                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms0')
                    self._ms0[row] = tn
                    if cfg.data.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms0')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 8:

                try:
                    if method == 'grid-custom':
                        assert regions[1] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms1')
                    self._ms1[row] = tn
                    if cfg.data.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms1')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 9:
                try:
                    if method == 'grid-custom':
                        assert regions[2] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms2')
                    self._ms2[row] = tn
                    if cfg.data.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms2')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 10:
                try:
                    if method == 'grid-custom':
                        assert regions[3] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms3')
                    self._ms3[row] = tn
                    if cfg.data.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                except:
                    tn = CorrSignalThumbnail(self, name='ms3')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 11:

                notes = QTextEdit()
                notes.setObjectName('Notes')
                notes.setPlaceholderText('Notes...')
                if cfg.data.notes(l=row):
                    notes.setText(cfg.data.notes(l=row))
                notes.setStyleSheet("""
                    background-color: #ede9e8;
                    color: #161c20;
                    font-size: 11px;
                """)
                self.all_notes.append(notes)
                notes.textChanged.connect(lambda index=row, txt=notes.toPlainText(): self.setNotes(index, txt))
                self.table.setCellWidget(row, col, notes)
            else:
                self.table.setItem(row, col, QTableWidgetItem(str(row_data[col])))

    def alignHighlighted(self):
        logger.info('')
        for r in self.getSelectedRows():
            cfg.mw.setZpos(r)
            cfg.main_window.alignOne()
            QApplication.processEvents()
            if cfg.pt._tabs.currentIndex() == 0:
                cfg.emViewer.set_layer(cfg.data.zpos)
            elif cfg.pt._tabs.currentIndex() == 1:
                cfg.baseViewer.set_layer(cfg.data.zpos)
                cfg.refViewer.set_layer(cfg.data.get_ref_index(l=cfg.data.zpos))

    # btn.clicked.connect(lambda state, x=zpos: self.jump_to_manual(x))

    def setNotes(self, index, txt):
        caller = inspect.stack()[1].function
        logger.info(f"\ncaller = {caller}\n"
                    f"index  = {index}\n"
                    f"txt    = {txt}")
        cfg.data.save_notes(text=txt, l=index)
        cfg.main_window.statusBar.showMessage('Note Saved!', 3000)
        self.all_notes[index].update()



    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu:
            logger.info('')
            menu = QMenu()

            if self.getNumRowsSelected() == 1:
                # path = self.getSelectedProjects()[0]

                pass

            # if self.getNumRowsSelected() > 1:
            if cfg.data.is_aligned():
                # self._min = min(self.getSelectedRows())
                # self._max = max(self.getSelectedRows())
                txt = f'Align Selected ({self.getSelectedRows()})'
                alignedSelectedRangeAction = QAction(txt)
                # alignedSelectedRangeAction = QAction(f'Align Selected ({self.getSelectedRows()})')
                # logger.info(f'Multiple rows are selected! _min={self._min}, _max={self._max}')
                # path = self.getSelectedProjects()[0]
                # copyPathAction = QAction(f"Copy Path '{self.getSelectedProjects()[0]}'")
                # logger.info(f"Added to Clipboard: {QApplication.clipboard().text()}")
                alignedSelectedRangeAction.triggered.connect(self.alignHighlighted)
                menu.addAction(alignedSelectedRangeAction)

            menu.exec_(event.globalPos())
            return True
        return super().eventFilter(source, event)



    def initUI(self):
        logger.info('')

        # self.table.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.table.setSelectionMode(QAbstractItemView.SingleSelection)
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
        hbl.addStretch()
        self.controls.setMaximumHeight(24)
        self.controls.setLayout(hbl)

        self.btn_splash_load_table = QPushButton(' Load Table')
        self.btn_splash_load_table.setIcon(qta.icon("fa.download", color='#f3f6fb'))
        self.btn_splash_load_table.clicked.connect(self.initTableData)
        self.btn_splash_load_table.setStyleSheet("""font-size: 18px; font-weight: 600; color: #f3f6fb;""")
        self.btn_splash_load_table.setFixedSize(160,80)


        self.scaleLabel = QLabel()
        self.scaleLabel.setStyleSheet("""font-size: 14px; font-weight: 600; color: #f3f6fb;""")
        self.scaleLabel.setAlignment(Qt.AlignLeft)
        self.scaleLabel.setFixedHeight(22)

        layout = VBL()
        layout.addWidget(self.btn_splash_load_table, alignment=Qt.AlignCenter)
        self.wTable = VWidget(self.scaleLabel,self.table)
        layout.addWidget(self.wTable)
        layout.addWidget(self.controls, alignment=Qt.AlignBottom)
        self.setLayout(layout)

        self.wTable.hide()


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