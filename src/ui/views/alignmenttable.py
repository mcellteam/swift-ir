#!/usr/bin/env python3

import copy
import inspect
import logging
import os
import time

import qtawesome as qta
from qtpy.QtCore import Qt, QRect, Signal, QEvent
from qtpy.QtGui import QPainter, QPixmap, QImage
from qtpy.QtWidgets import QWidget, QHBoxLayout, QAbstractItemView, QApplication, \
    QTableWidget, QTableWidgetItem, QSlider, QLabel, QPushButton, QFrame, QAction, QMenu, \
    QTextEdit

import src.config as cfg
from src.utils.helpers import print_exception
from src.ui.layouts.layouts import VBL, VW, HW
from src.ui.views.thumbnail import ThumbnailFast, CorrSignalThumbnail

logger = logging.getLogger(__name__)


class ProjectTable(QWidget):
    onTableFinishedLoading = Signal()
    updatePbar = Signal(int)

    def __init__(self, parent, dm):
        super().__init__(parent)
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        self.parent = parent
        self.dm = dm
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
        # self.data.horizontalHeader().setHighlightSections(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.data.itemClicked.connect(self.userSelectionChanged)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        # self.data.itemPressed.connect(self.selection_changed)
        # self.data.itemPressed.connect(lambda: print('itemPressed was emitted!'))
        # self.data.cellActivated.connect(lambda: print('cellActivated was emitted!'))
        # self.data.currentItemChanged.connect(lambda: print('currentItemChanged was emitted!'))
        # self.data.itemDoubleClicked.connect(lambda: print('itemDoubleClicked was emitted!'))
        # self.data.itemSelectionChanged.connect(lambda: print('itemselectionChanged was emitted!')) #Works!
        # self.data.cellChanged.connect(lambda: print('cellChanged was emitted!'))
        # self.data.cellClicked.connect(lambda: print('cellClicked was emitted!'))
        # self.data.itemChanged.connect(lambda: print('itemChanged was emitted!'))
        # self.data.setSelectionMode(QAbstractItemView.ContiguousSelection)
        # self.data.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Fails on TACC for some reason
        # self.tableFinishedLoading.connect(self.onTableFinishedLoading)
        # self.onTableFinishedLoading.connect(lambda: logger.critical("\n\n\nTable finished loading!\n\n"))
        # self.onTableFinishedLoading.connect(lambda:self.parent.parent.set_status("Table finished loading."))
        header = self.table.horizontalHeader()
        header.setFrameStyle(QFrame.Box | QFrame.Plain)
        header.setStyleSheet("QHeaderView::section { border-bottom: 1px solid gray; }");
        self.table.setHorizontalHeader(header)

        self.m = {'grid_default': 'Grid Align',
                  'grid_custom': 'Custom Grid',
                  'manual_hint': 'Match Region',
                  'manual_strict': 'Match Point',
                  'grid': 'Grid Align',
                  'manual': 'Match'}

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

        # self.initTableData()
        self.veil()


    def veil(self):
        self.wTable.hide()
        self.btn_splash_load_table.show()


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
    #     # cfg.main_window.openAlignment()

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
            if self.parent.wTabs.currentIndex() == 2:
                self.dm.zpos = self.table.currentIndex().row()


    def set_column_headers(self):
        labels = ['Z-index', 'Section vs.\nReference', 'SNR/\nMethod', 'Last\nAligned', 'Reference', 'Transforming', 'Aligned\nResult',
                  'Match\nSignal 1', 'Match\nSignal 2', 'Match\nSignal 3', 'Match\nSignal 4', 'Notes']
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setColumnCount(len(labels))


    def initTableData(self):
        self.btn_splash_load_table.setText("Loading...")
        t0 = time.time()

        self.setUpdatesEnabled(False)
        self.table.blockSignals(True)

        # self.wTable.hide()

        self.btn_splash_load_table.setText("Load Table")
        siz = self.dm.image_size()
        self.scaleLabel.setText(f"{self.dm.level_pretty()} | {siz[0]}x{siz[1]}px")
        self.btn_splash_load_table.hide()
        # self.data.update()
        # self.wTable.show()
        self.set_column_headers()
        self.setColumnWidths()
        self.updateTableDimensions(self.INITIAL_ROW_HEIGHT)
        self.updateTableDimensions(self.row_height_slider.value())

        self._ms0 = [None] * len(self.dm)
        self._ms1 = [None] * len(self.dm)
        self._ms2 = [None] * len(self.dm)
        self._ms3 = [None] * len(self.dm)

        t = time.time()
        caller = inspect.stack()[1].function

        # self.data.setUpdatesEnabled(False)

        self.table.clearContents()
        self.table.clear()
        self.table.setRowCount(len(self.dm))
        self.set_column_headers() #Critical
        cnt = 0
        # self.parent.parent.resetPbar((self.dm.count, 'Loading Table'))
        try:
            for row in range(0, len(self.dm)):
                if cfg.CancelProcesses:
                    logger.warning("Canceling data load!")
                    return
                cnt += 1
                # cfg.main_window.updatePbar(cnt)
                self.updatePbar.emit(cnt)
                # self.data.insertRow(row)
                self.set_row_data(row=row)

        except:
            print_exception()
        finally:
            logger.critical(f"\n\nTIME ELAPSED: {time.time() - t0:.1f}s\n")
            # self.btn_splash_load_table.setText("Load Table")
            # siz = self.dm.image_size()
            # self.scaleLabel.setText(f"{self.dm.level_pretty()} | {siz[0]}x{siz[1]}px")
            # self.btn_splash_load_table.hide()
            self.wTable.show()
            self.table.blockSignals(False)
            # self.set_column_headers()
            self.setColumnWidths()
            self.updateTableDimensions(self.row_height_slider.value())

            # self.data.setUpdatesEnabled(True)

            self.setUpdatesEnabled(True)


            # if cur_selection != -1:
            #     self.data.selectRow(cur_selection)
            # self.data.verticalScrollBar().setValue(cur_scroll_pos)
            # logger.info(f'cur_selection={cur_selection}, cur_scroll_pos={cur_scroll_pos}')
            # cur_selection = self.data.currentIndex().row()


            logger.info('Data data finished loading.')

        logger.info(f'<<<< initTableData [{caller}]')


    def updateTableData(self):
        logger.info('')
        # self.parent.parent.resetPbar((self.dm.count, 'Updating Table'))

        if self.btn_splash_load_table.isVisible():
            self.initTableData()
            return

        cur_selection = self.table.currentIndex().row()
        cur_scroll_pos = self.table.verticalScrollBar().value()

        # self.data.setUpdatesEnabled(False)

        try:
            self.table.clear()
            self.table.clearContents()
            self.set_column_headers()  # Critical
            for row in range(0,len(self.dm)):
                cfg.nProcessDone += 1
                # cfg.main_window.updatePbar(cfg.nProcessDone)
                self.updatePbar.emit(cfg.nProcessDone)
                self.set_row_data(row=row)

        except:
            print_exception()
        finally:
            siz = self.dm.image_size()
            self.scaleLabel.setText(f"{self.dm.level_pretty()} | {siz[0]}x{siz[1]}px")
            self.parent.parent.hidePbar()
            if cur_selection != -1:
                self.table.selectRow(cur_selection)
            self.table.verticalScrollBar().setValue(cur_scroll_pos)
            cfg.nProcessDone += 1
            self.parent.parent.updatePbar(cfg.nProcessDone)

            # self.data.setUpdatesEnabled(True)


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

        # header = self.data.horizontalHeader()
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
        # self.data.setStyleSheet(f'font-size: {size}px;')


    def jump_to_edit(self, requested) -> None:
        self.dm.zpos = requested
        self.parent.wTabs.setCurrentIndex(1)


    def jump_to_view(self, requested) -> None:
        self.dm.zpos = requested
        self.parent.wTabs.setCurrentIndex(0)

    def request_refresh(self, requested) -> None:
        self.set_row_data(row=requested)


    def get_row_data(self, s=None, l=None):
        if s == None: s = self.dm.level
        if l == None: l = self.dm.zpos
        method = self.dm.method(s=s, l=l)
        index = ('%d'%l).zfill(5)
        basename = self.dm.name(s=s, l=l)
        snr_avg = self.dm.snr(s=s, l=l, method=method)
        tn_tra = self.dm.path_thumb(s=s, l=l)
        tn_ref = self.dm.path_thumb_ref(s=s, l=l)
        tn_aligned = self.dm.path_aligned(s=s, l=l)

        # fn, extension = os.file_path.splitext(basename)
        # dir_signals = self.dm.dir_signals()

        # sigs = self.dm.get_signals_filenames()
        # sigs_lst = ['']*4
        # for i, p in enumerate(sigs):
        #     sigs_lst[i] = sigs[i]

        # sig0 = os.file_path.join(dir_signals, '%s_%s_0%s' % (fn, method, extension))
        # sig1 = os.file_path.join(dir_signals, '%s_%s_1%s' % (fn, method, extension))
        # sig2 = os.file_path.join(dir_signals, '%s_%s_2%s' % (fn, method, extension))
        # sig3 = os.file_path.join(dir_signals, '%s_%s_3%s' % (fn, method, extension))
        sigs = self.dm.get_enum_signals_filenames(s=s, l=l)
        notes = self.dm.notes(s=s,l=l)
        try:
            last_aligned = self.dm['stack'][l]['levels'][s]['results']['datetime']
        except:
            last_aligned = 'N/A'
        return [index, basename, snr_avg, last_aligned, tn_ref, tn_tra, tn_aligned, *sigs, notes]


    def set_row_data(self, row):
        # print(f"row: {row}")
        snr_4x = copy.deepcopy(self.dm.snr_components(s=self.dm.level, l=row))
        # logger.critical(f"SNR: {snr_4x}")
        row_data = self.get_row_data(s=self.dm.level, l=row)
        # pprint.pprint("\n\nrow_data:\n")
        # pprint.pprint(row_data)
        method = self.dm.method(s=self.dm.level, l=row)
        if 'grid' in method:
            regions = copy.deepcopy(self.dm.get_grid_regions(l=row))
        # for j, item in enumerate(row):

        self.all_notes = []

        self._ms = []

        # if row in (0,1,2,3):
        #     logger.critical(f"\n\n==== ROW {row} ====\nsnr: {snr_4x}\nrow data: {row_data}")

        for col in range(0, len(row_data)):

            if col == 0:
                # self.data.setItem(row, col, QTableWidgetItem('\n'.join(textwrap.wrap(str(row_data[0]), 20))))
                # self.data.setCellWidget(row, col, tn)

                b0 = QPushButton('View')
                b0.setMaximumHeight(14)
                b0.clicked.connect(lambda state, x=row: self.jump_to_view(x))
                # b0.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20; padding:1px; width: 22px; height: 14px; ")
                b0.setStyleSheet("font-size: 8px; background-color: #ede9e8; color: #161c20; padding:1px; ")
                b1 = QPushButton('Edit')
                b1.setMaximumHeight(14)
                b1.clicked.connect(lambda state, x=row: self.jump_to_edit(x))
                # b1.setStyleSheet("font-size: 10px; background-color: #ede9e8; color: #161c20;  padding:1px; width: 22px; height: 14px; ")
                b1.setStyleSheet("font-size: 8px; background-color: #ede9e8; color: #161c20;  padding:1px; ")
                b2 = QPushButton('Refresh Row')
                b2.setMaximumHeight(14)
                b2.clicked.connect(lambda state, x=row: self.request_refresh(x))
                b2.setStyleSheet("font-size: 8px; background-color: #ede9e8; color: #161c20;  padding:1px; ")
                btns = VW(HW(b0, b1), b2)
                # btns.setStyleSheet("font-size: 12px; background-color: #161c20;")

                lab = QLabel(str(row_data[0]))
                lab.setAlignment(Qt.AlignCenter)
                # lab.setStyleSheet("font-size: 12px; background-color: #ede9e8; color: #161c20;")
                lab.setStyleSheet("font-size: 10px; color: #161c20; font-weight: 600; padding: 0px; margin: 0px;")

                w = QWidget()
                vbl = VBL(lab, btns)
                vbl.setSpacing(4)
                vbl.setAlignment(Qt.AlignVCenter)
                w.setLayout(vbl)
                w.setStyleSheet("background:transparent;")
                # w.setStyleSheet("QWidget {border-radius: 6px; border: 1px solid #ede9e8;}")

                self.table.setCellWidget(row, col, w)
            elif col == 1:
                lab1 = QLabel(self.dm.name(l=row))
                lab1.setStyleSheet("font-weight: 600; font-size: 11px; background: transparent;")
                if self.dm.skipped(l=row):
                    lab2 = QLabel('* Exclude')
                    lab2.setStyleSheet("font-size: 10px; color: #d0342c; padding:2px; background: transparent;")
                    vw = VW(lab1, lab2)
                    vw.layout.setAlignment(Qt.AlignVCenter)
                else:
                    lab2 = QLabel("Reference:")
                    lab2.setStyleSheet("font-size: 9px; background: transparent;")
                    lab3_str = self.dm.name_ref(l=row)
                    ref_offset = self.dm.get_ref_index_offset(l=row)
                    if ref_offset > 1:
                        lab3_str += f' <span style="color: #d0342c;"><b>[{-ref_offset + 1}]</b></span>'
                    lab3 = QLabel(lab3_str)
                    lab3.setStyleSheet("font-size: 9px; font-weight: 600; background: transparent;")
                    vw = VW(lab1, lab2, lab3)
                    vw.setStyleSheet("background: transparent;")
                    vw.layout.setAlignment(Qt.AlignVCenter)
                self.table.setCellWidget(row, col, vw)
            elif col == 2:
                lab1 = QLabel('%.3g' % float(row_data[2]))
                lab1.setStyleSheet("font-weight: 600; font-size: 11px;")
                m = self.m[method]
                # m = self.m
                lab2 = QLabel(m)
                if m == 'Default Grid':
                    lab2.setStyleSheet("font-size: 10px; color: #00BF00;")
                elif method == 'Custom Grid':
                    lab2.setStyleSheet("font-size: 10px; color: #8f99fb;")
                else:
                    lab2.setStyleSheet("font-size: 10px; color: #010fcc;")

                vw = VW(lab1, lab2)
                vw.layout.setAlignment(Qt.AlignCenter)
                vw.setStyleSheet("background:transparent;")
                self.table.setCellWidget(row, col, vw)
                # self.data.setItem(row, col, QTableWidgetItem(str(row_data[col])))
            elif col == 3:
                self.table.setItem(row, col, QTableWidgetItem(str(row_data[col])))
            elif col == 4:
                if os.path.exists(row_data[col]):
                    # tn = ThumbnailFast(self, file_path=row_data[col], name='reference-data', level=scale, z=row)
                    tn = ThumbnailFast(self, path=row_data[col], name='reference-data', s=self.dm.level, l=row)
                    if self.dm.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                else:
                    logger.warning(f"Path DNE: {row_data[col]}")
            elif col == 5:
                if os.path.exists(row_data[col]):
                    tn = ThumbnailFast(self, path=row_data[col], name='transforming-data', s=self.dm.level, l=row)
                    if self.dm.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                else:
                    logger.warning(f"Path DNE: {row_data[col]}")
            elif col == 6:
                if os.path.exists(row_data[col]):
                    tn = ThumbnailFast(self, path=row_data[col])
                    if self.dm.skipped(l=row):
                        tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
                else:
                    logger.warning(f"Path DNE: {row_data[col]}")
            elif col == 7:
                try:
                    # if method == 'grid_custom':
                    if 'grid' in method:
                        assert regions[0] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    if len(snr_4x):
                        tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms0', annotations=False)
                        self._ms0[row] = tn
                        if self.dm.skipped(l=row):
                            tn.set_no_image()
                        self.table.setCellWidget(row, col, tn)
                except:
                    print_exception()
                    tn = CorrSignalThumbnail(self, name='ms0')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 8:

                try:
                    # if method == 'grid_custom':
                    if 'grid' in method:
                        assert regions[1] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    if len(snr_4x):
                        tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms1', annotations=False)
                        self._ms1[row] = tn
                        if self.dm.skipped(l=row):
                            tn.set_no_image()
                        self.table.setCellWidget(row, col, tn)
                except:
                    print_exception()
                    tn = CorrSignalThumbnail(self, name='ms1')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 9:
                try:
                    # if method == 'grid_custom':
                    if 'grid' in method:
                        assert regions[2] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    if len(snr_4x):
                        tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms2', annotations=False)
                        self._ms2[row] = tn
                        if self.dm.skipped(l=row):
                            tn.set_no_image()
                        self.table.setCellWidget(row, col, tn)
                except:
                    print_exception()
                    tn = CorrSignalThumbnail(self, name='ms2')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 10:
                try:
                    # if method == 'grid_custom':
                    if 'grid' in method:
                        assert regions[3] == 1
                    else:
                        assert snr_4x[0] > 0.0
                    if len(snr_4x):
                        tn = CorrSignalThumbnail(self, path=row_data[col], snr=snr_4x.pop(0), name='ms3', annotations=False)
                        self._ms3[row] = tn
                        if self.dm.skipped(l=row):
                            tn.set_no_image()
                        self.table.setCellWidget(row, col, tn)
                except:
                    print_exception()
                    tn = CorrSignalThumbnail(self, name='ms3')
                    # tn.set_no_image()
                    self.table.setCellWidget(row, col, tn)
            elif col == 11:
                notes = QTextEdit()
                notes.setObjectName('Notes')
                notes.setPlaceholderText('Notes...')
                if self.dm.notes(l=row):
                    notes.setText(self.dm.notes(l=row))
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
            self.dm.zpos = r
            self.parent.parent.alignOne(dm=self.dm)
            QApplication.processEvents()
            # if self.parent.wTabs.currentIndex() == 0:
            #     self.parent.viewer.set_layer()
            # elif self.parent.wTabs.currentIndex() == 1:
            #     self.parent.viewer1.set_layer()

    # btn.clicked.connect(lambda state, x=zpos: self.jump_to_manual(x))

    def setNotes(self, index, txt):
        caller = inspect.stack()[1].function
        logger.info(f"\ncaller = {caller}\n"
                    f"index  = {index}\n"
                    f"txt    = {txt}")
        self.dm.save_notes(text=txt, l=index)
        self.all_notes[index].update()



    def eventFilter(self, source, event):
        if event.type() == QEvent.ContextMenu:
            logger.info('')
            menu = QMenu()

            if self.getNumRowsSelected() == 1:
                # file_path = self.getSelectedProjects()[0]

                pass

            # if self.getNumRowsSelected() > 1:
            if self.dm.is_aligned():
                # self._min = min(self.getSelectedRows())
                # self._max = max(self.getSelectedRows())
                txt = f'Align Selected ({self.getSelectedRows()})'
                alignedSelectedRangeAction = QAction(txt)
                # alignedSelectedRangeAction = QAction(f'Align Selected ({self.getSelectedRows()})')
                # logger.info(f'Multiple rows are selected! _min={self._min}, _max={self._max}')
                # file_path = self.getSelectedProjects()[0]
                # copyPathAction = QAction(f"Copy Path '{self.getSelectedProjects()[0]}'")
                # logger.info(f"Added to Clipboard: {QApplication.clipboard().text()}")
                alignedSelectedRangeAction.triggered.connect(self.alignHighlighted)
                menu.addAction(alignedSelectedRangeAction)

            menu.exec_(event.globalPos())
            return True
        return super().eventFilter(source, event)



    def initUI(self):
        logger.info('')

        # self.data.setStyleSheet('font-size: 10px;')
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # self.data.setSelectionMode(QAbstractItemView.SingleSelection)
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
        self.btn_splash_load_table.setFixedSize(160,64)


        self.scaleLabel = QLabel()
        self.scaleLabel.setStyleSheet("""font-size: 12px; color: #f3f6fb;""")
        self.scaleLabel.setAlignment(Qt.AlignLeft)
        self.scaleLabel.setFixedHeight(22)

        layout = VBL()
        layout.addWidget(self.btn_splash_load_table, alignment=Qt.AlignCenter)
        self.wTable = VW(self.scaleLabel, self.table)
        layout.addWidget(self.wTable)
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


class ImageWidget(QWidget):

    def __init__(self, imagePath, parent):
        super(ImageWidget, self).__init__(parent)
        #             pixmap = QPixmap(file_path)
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


# self.parent.project_table.setImage(2,3,'/Users/joelyancey/glanceem_swift/test_projects/test2/scale_4/thumbnails_aligned/funky4.tif')