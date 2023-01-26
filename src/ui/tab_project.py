#!/usr/bin/env python3

import os, sys, logging, inspect, copy
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStyleOption, \
    QStyle, QTabBar, QTabWidget, QGridLayout, QHeaderView, QTreeView, QSplitter, QTextEdit
from qtpy.QtCore import Qt, QSize, QRect, QUrl, QSortFilterProxyModel
from qtpy.QtGui import QPainter, QFont, QPixmap, QStandardItem, QStandardItemModel
from qtpy.QtWebEngineWidgets import *
from src.ui.ui_custom import VerticalLabel
from src.ui.layer_view_widget import LayerViewWidget
from src.ui.models.json_tree import JsonModel
from src.ui.snr_plot import SnrPlot
from src.ui.mini_view import MiniView
import src.config as cfg
from src.ng_host import NgHost
from src.ng_host_slim import NgHostSlim
from src.ui.widget_area import WidgetArea
from src.helpers import print_exception
from src.ui.project_table import ProjectTable

logger = logging.getLogger(__name__)

class ProjectTab(QWidget):

    def __init__(self,
                 parent=None,
                 path=None,
                 datamodel=None,
                 *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        logger.info(f'ID(datamodel): {id(datamodel)}, Path: {path}')
        self.parent = parent
        self.path = path
        self.datamodel = datamodel
        self.ng_layout = '4panel'
        # cfg.main_window._ng_layout_switch = 0
        # cfg.main_window._cmbo_ngLayout.setCurrentText(self.ng_layout)
        # cfg.main_window._ng_layout_switch = 1
        self.ng_browser = QWebEngineView()
        self.ng_browser.setFocusPolicy(Qt.StrongFocus)
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        # self.initUI_mini_view()
        self.initUI_tab_widget()
        self._tabs.currentChanged.connect(self._onTabChange)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ng_browser.setFocusPolicy(Qt.StrongFocus)


    def _onTabChange(self, index=None):
        if index == None: index = self._tabs.currentIndex()
        # if index == 0:
        #     self.updateNeuroglancer()
        if index == 1:
            self.project_table.set_data()
        if index == 2:
            self.updateJsonWidget()
        if index == 3:
            self.snr_plot.data = cfg.data
            self.snr_plot.initSnrPlot()
            # self.snr_plot.updateSpecialLayerLines()
            self.updatePlotThumbnail()


        QApplication.processEvents()
        self.repaint()


    def initNeuroglancer(self, layout=None, matchpoint=False):
        logger.critical(f'Initializing Neuroglancer Host (caller: {inspect.stack()[1].function})')
        if cfg.data:
            if layout:
                cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
            # cfg.main_window.reload_ng_layout_combobox(initial_layout=self.ng_layout)
            if cfg.main_window.rb0.isChecked():
                cfg.main_window._cmbo_ngLayout.setCurrentText('4panel')
                cfg.ng_worker = NgHostSlim(self, project=True)
            elif cfg.main_window.rb1.isChecked():
                cfg.main_window._cmbo_ngLayout.setCurrentText('xy')
                cfg.ng_worker = NgHost(self)
            cfg.ng_worker.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
            self.updateNeuroglancer(matchpoint=matchpoint)


    def updateNeuroglancer(self, matchpoint=False, layout=None):
        logger.critical(f'Updating Neuroglancer Viewer (caller: {inspect.stack()[1].function})')
        if layout: cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
        cfg.ng_worker.initViewer(matchpoint=matchpoint)
        self.ng_browser.setUrl(QUrl(cfg.ng_worker.url()))
        self.ng_browser.setFocus()
        self._transformationWidget.setVisible(cfg.data.is_aligned_and_generated())

    def setNeuroglancerUrl(self):
        self.ng_browser.setUrl(QUrl(cfg.ng_worker.url()))


    def updateNgLayer(self):
        state = copy.deepcopy(cfg.viewer.state)
        state.position[0] = cfg.data.layer()
        cfg.viewer.set_state(state)


    def getBrowserSize(self):
        return self.ng_browser.geometry().getRect()


    def updateJsonWidget(self):
        self._treeview_model.load(cfg.data.to_dict())


    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')


        self.ng_browser.loadFinished.connect(lambda: print('QWebengineView Load Finished!'))
        # self.ng_browser.loadProgress.connect(lambda progress: print(f'QWebengineView Load Progress: {progress}'))
        # self.ng_browser.urlChanged.connect(lambda terminationStatus:
        #                              print(f'QWebengineView Render Process Terminated!'
        #                                    f' terminationStatus:{terminationStatus}'))

        # self.ng_browser.settings().setAttribute(QWebEngineSettings.PluginsEnabled, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.AllowRunningInsecureContent, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        # self.ng_browser.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        self.ng_browser_container = QWidget()
        self.ng_browser_container.setObjectName('ng_browser_container')
        gl = QGridLayout()
        gl.addWidget(self.ng_browser, 0, 0)
        self._overlayRect = QWidget()
        self._overlayRect.setObjectName('_overlayRect')
        self._overlayRect.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._overlayRect.hide()
        gl.addWidget(self._overlayRect, 0, 0)
        self._overlayLab = QLabel()
        self._overlayLab.setObjectName('_overlayLab')
        self._overlayLab.hide()
        self.lab_name = QLabel('Name :')
        self.lab_name.setStyleSheet('font-weight: 650;')
        self.lab_snr = QLabel('SNR: :')
        self.lab_skipped = QLabel('Skipped Layers : []')
        self.lab_match_point = QLabel('Match Point Layers : []')

        self._layer_details = (
            self.lab_name,
            self.lab_snr,
            self.lab_skipped,
            self.lab_match_point,
        )
        for layer in self._layer_details:
            layer.setStyleSheet(
                'color: #ffe135;'
                'font-size: 9px;'
                'background-color: rgba(0,0,0,.5);'
                'margin: 1px 1px 1px 1px;'
                'border-width: 0px;'
                'border-style: solid;'
                'border-color: #141414;'
                'border-radius: 1px;'
                'margin-right: 10px;'
            )
            layer.setFixedWidth(160)
            layer.setWordWrap(True)
            layer.setContentsMargins(0,0,0,0)

        '''AFM/CAFM Widget'''
        # lab = QLabel('Transformation')
        # lab.setStyleSheet('font-size: 10px; font-weight: 500; color: #ffe135;')
        # lab.setObjectName('label_afm')
        self.afm_widget_ = QTextEdit()
        self.afm_widget_.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.afm_widget_.setObjectName('_tool_afmCafm')
        self.afm_widget_.setReadOnly(True)
        self._transformationWidget = QWidget()
        # self._transformationWidget.setFixedSize(180,80)
        self._transformationWidget.setFixedWidth(160)
        self._transformationWidget.setMaximumHeight(70)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.setSpacing(1)
        # vbl.addWidget(lab, alignment=Qt.AlignmentFlag.AlignBaseline)
        vbl.addWidget(self.afm_widget_)
        self._transformationWidget.setLayout(vbl)

        self.__widgetArea_details = WidgetArea(parent=self, title='Details', labels=self._layer_details)
        self.__widgetArea_details.hideTitle()
        self.__widgetArea_details.setFixedWidth(160)
        self.__widgetArea_details.setFixedHeight(80)
        self.__widgetArea_details.setStyleSheet('background-color: rgba(0,0,0,0);')
        self.__widgetArea_details.setContentsMargins(0, 0, 0, 0)

        self._widgetArea_details = QWidget()
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0,0,0,0)
        vbl.addWidget(self._transformationWidget)
        vbl.addWidget(self.__widgetArea_details)
        self._widgetArea_details.setLayout(vbl)

        self._widgetArea_details.hide()
        self._overlayBottomLeft = QLabel()
        self._overlayBottomLeft.setObjectName('_overlayBottomLeft')
        self._overlayBottomLeft.hide()
        gl.addWidget(self._overlayLab, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._overlayBottomLeft, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._widgetArea_details, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        # gl.addWidget(cfg.main_window._tool_afmCafm, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.ng_browser_container.setLayout(gl)
        gl.setContentsMargins(0, 0, 0, 0)
        lab = VerticalLabel('Neuroglancer 3DEM View')
        lab.setObjectName('label_ng')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0,0,0,0)
        hbl.addWidget(lab)
        hbl.addWidget(self.ng_browser_container)
        self.ng_browser_container_outer = QWidget()
        self.ng_browser_container_outer.setObjectName('ng_browser_container_outer')
        self.ng_browser_container_outer.setLayout(hbl)


    def initUI_table(self):
        '''Layer View Widget'''
        logger.info('')
        # self.project_table = LayerViewWidget()
        self.project_table = ProjectTable(self)
        self.project_table.setObjectName('project_table')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.project_table)
        self.label_overview = VerticalLabel('Project Data Table View')
        self.label_overview.setObjectName('label_overview')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.table_container = QWidget(parent=self)
        self.table_container.setObjectName('table_container')
        self.table_container.setLayout(hbl)


    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self._treeview = QTreeView()
        self._treeview.setIndentation(20)
        self._treeview_model = JsonModel()
        self._treeview.setModel(self._treeview_model)
        self._treeview.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self._treeview.setAlternatingRowColors(True)
        self._wdg_treeview = QWidget()
        self._wdg_treeview.setObjectName('_wdg_treeview')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 0, 2, 0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setObjectName('label_treeview')
        hbl.addWidget(lab)
        hbl.addWidget(self._treeview)
        self._wdg_treeview.setLayout(hbl)

    def updatePlotThumbnail(self):
        pixmap = QPixmap(cfg.data.thumbnail())
        pixmap = pixmap.scaledToHeight(160)
        self._thumbnail_src.setPixmap(pixmap)
        self.source_thumb_and_label.show()
        if cfg.data.is_aligned_and_generated():
            pixmap = QPixmap(cfg.data.thumbnail_aligned())
            pixmap = pixmap.scaledToHeight(160)
            self._thumbnail_aligned.setPixmap(pixmap)
            self.aligned_thumb_and_label.show()
        else:
            self.aligned_thumb_and_label.hide()

    def initUI_plot(self):
        '''SNR Plot Widget'''
        logger.info('')
        font = QFont()
        font.setBold(True)
        self.snr_plot = SnrPlot()
        lab_yaxis = VerticalLabel('Signal-to-Noise Ratio', font_color='#f3f6fb', font_size=14)
        lab_yaxis.setFixedWidth(18)
        hbl = QHBoxLayout()
        hbl.addWidget(lab_yaxis)
        self._plot_Yaxis = QWidget()
        self._plot_Yaxis.setLayout(hbl)
        self._plot_Yaxis.setContentsMargins(0, 0, 0, 0)
        self._plot_Yaxis.setFixedWidth(26)
        lab_yaxis.setFont(font)
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self._plot_Yaxis)
        hbl.addWidget(self.snr_plot)
        # self.snr_plot_widget = QWidget()
        # self.snr_plot_widget.setObjectName('snr_plot_widget')
        self._plot_Xaxis = QLabel('Serial Section #')
        self._plot_Xaxis.setStyleSheet('color: #f3f6fb; font-size: 14px;')
        self._plot_Xaxis.setContentsMargins(0, 0, 0, 8)
        self._plot_Xaxis.setFont(font)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addLayout(hbl)
        vbl.addWidget(self._plot_Xaxis, alignment=Qt.AlignmentFlag.AlignHCenter)

        w1 = QWidget()
        w1.setLayout(vbl)

        self._thumbnail_src = QLabel()
        self._thumbnail_aligned = QLabel()

        style = '''font-size: 14px; color: #f3f6fb; font-weight: 500;'''

        self._lab_source_thumb = QLabel('Source:')
        self._lab_source_thumb.setFixedHeight(16)
        self._lab_source_thumb.setStyleSheet(style)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._lab_source_thumb)
        vbl.addWidget(self._thumbnail_src, alignment=Qt.AlignmentFlag.AlignTop)
        self.source_thumb_and_label = QWidget()
        self.source_thumb_and_label.setLayout(vbl)

        self._lab_aligned_thumb = QLabel('Aligned:')
        self._lab_aligned_thumb.setFixedHeight(16)
        self._lab_aligned_thumb.setStyleSheet(style)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._lab_aligned_thumb)
        vbl.addWidget(self._thumbnail_aligned, alignment=Qt.AlignmentFlag.AlignTop)
        self.aligned_thumb_and_label = QWidget()
        self.aligned_thumb_and_label.setLayout(vbl)

        self.source_thumb_and_label.hide()
        self.aligned_thumb_and_label.hide()

        gl = QGridLayout()
        gl.setContentsMargins(4, 4, 4, 4)
        gl.setRowStretch(0, 1)
        gl.setRowStretch(1, 1)
        gl.setColumnStretch(0, 1)
        gl.addWidget(self.source_thumb_and_label, 0, 0)
        gl.addWidget(self.aligned_thumb_and_label, 1, 0)
        w2 = QWidget()
        w2.setLayout(gl)
        self.snr_plot_widget = QSplitter(Qt.Orientation.Horizontal)
        self.snr_plot_widget.setObjectName('snr_plot_widget')
        self.snr_plot_widget.addWidget(w1)
        self.snr_plot_widget.addWidget(w2)
        # self.snr_plot_widget.setSizes([1000, 150])
        # try:    self.snr_plot.initSnrPlot() # sets up some basic plot characteristics
        # except: logger.warning('exception while initializing Snr Plot')


    def initUI_mini_view(self):
        self._mv = MiniView()


    def initUI_tab_widget(self):
        '''Tab Widget'''
        logger.info('')
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet('QTabBar::tab { height: 22px; width: 84px; }')
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setObjectName('project_tabs')
        self._tabs.addTab(self.ng_browser_container_outer, ' 3DEM ')
        self._tabs.addTab(self.table_container, ' Table ')
        self._tabs.setTabToolTip(1, os.path.basename(cfg.data.dest()))
        self._tabs.addTab(self._wdg_treeview, ' Tree ')
        self._tabs.addTab(self.snr_plot_widget, ' SNR Plot ')
        # self._addTab(widget=self._mv, name=' Miniview ')
        self._tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(1, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(2, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(3, QTabBar.RightSide, None)
        self._tabs.tabBar().setTabButton(0, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(1, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(2, QTabBar.LeftSide, None)
        self._tabs.tabBar().setTabButton(3, QTabBar.LeftSide, None)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self._tabs)
        self.setLayout(vbl)


    def paintEvent(self, pe):
        '''Enables widget to be style-ized'''
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        s = self.style()
        s.drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def sizeHint(self):
        return QSize(1000,1000)




if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    pt = ProjectTab()
    main_window.setCentralWidget(pt)
    main_window.show()
    sys.exit(app.exec_())