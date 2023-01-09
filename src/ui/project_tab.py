#!/usr/bin/env python3

import sys, logging, inspect
import neuroglancer as ng
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QGroupBox, QFormLayout, QLabel, QScrollArea, \
    QVBoxLayout, QSizePolicy, QHBoxLayout, QPushButton, QComboBox, QSpinBox, QStyleOption, QStyle, QTabBar, \
    QTabWidget, QGridLayout, QHeaderView, QTreeView, QGraphicsOpacityEffect
from qtpy.QtCore import Qt, QSize, QRect, QUrl
from qtpy.QtGui import QPainter, QFont
from qtpy.QtWebEngineWidgets import *
from src.ui.ui_custom import VerticalLabel
from src.ui.layer_view_widget import LayerViewWidget
from src.ui.models.json_tree import JsonModel
from src.ui.snr_plot import SnrPlot
import src.config as cfg
from src.ng_host import NgHost
from src.ng_host_slim import NgHostSlim
from src.helpers import print_exception

logger = logging.getLogger(__name__)

class ProjectTab(QWidget):

    def __init__(self,
                 key,
                 parent=None,
                 path=None,
                 datamodel=None,
                 *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        logger.info(f'Unique Key: {key}, ID(datamodel): {id(datamodel)}, Path: {path}')
        self.key = key
        self.parent = parent
        self.path = path
        self.datamodel = datamodel
        # self.ng_layout = 'xy'
        self.ng_layout = '4panel'
        cfg.main_window._ng_layout_switch = 0
        cfg.main_window._cmbo_ngLayout.setCurrentText(self.ng_layout)
        cfg.main_window._ng_layout_switch = 1

        self.initUI_Neuroglancer()
        self.initUI_details()
        self.initUI_JSON()
        self.initUI_plot()
        self.initUI_tab_widget()
        self._tabs.currentChanged.connect(self._onTabChange)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ng_browser.setFocusPolicy(Qt.StrongFocus)
        self.arrangement = 0

    def _onTabChange(self, index=None):
        if index == None: index = self._tabs.currentIndex()
        if index == 0:  pass
        if index == 1:
            if not cfg.main_window._working:
                self.layer_view_widget.set_data()
        if index == 2:
            self.updateJsonWidget()
        if index == 3:
            self.snr_plot.data = self.datamodel
            # self.snr_plot.plotData()
            self.snr_plot.initSnrPlot()
        QApplication.processEvents()
        self.repaint()

    def initNeuroglancer(self, layout=None, matchpoint=None):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')

        if layout:
            cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
        # cfg.main_window.reload_ng_layout_combobox(initial_layout=self.ng_layout)

        if self.arrangement == 0:
            cfg.ng_worker = NgHostSlim(parent=self, project=True)
        else:
            cfg.ng_worker = NgHost(parent=self)
            if self.arrangement == 1:
                cfg.ng_worker.arrangement = 1
            elif self.arrangement == 2:
                cfg.ng_worker.arrangement = 2
        cfg.ng_worker.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
        self.updateNeuroglancer(matchpoint=matchpoint)


    def updateNeuroglancer(self, matchpoint=None, layout=None):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        if layout:
            cfg.main_window._cmbo_ngLayout.setCurrentText(layout)
        if matchpoint != None:
            cfg.ng_worker.initViewer(matchpoint=matchpoint)
        else:
            cfg.ng_worker.initViewer()
        self.ng_browser.setUrl(QUrl(cfg.ng_worker.url()))
        self.ng_browser.setFocus()



    def getBrowserSize(self):
        return self.ng_browser.geometry().getRect()


    def _addTab(self, widget, name):
        self._tabs.addTab(widget, name)


    def updateJsonWidget(self):
        self._treeview_model.load(self.datamodel.to_dict())


    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')

        self.ng_browser = QWebEngineView()
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
        # self._overlayNotification = QLabel('No datamodel. ')
        self._overlayNotification = QLabel('')
        font = QFont()
        font.setFamily("Courier New")
        self._overlayNotification.setFont(font)
        self._overlayNotification.setObjectName('_overlayNotification')
        self._overlayBottomLeft = QLabel()
        self._overlayBottomLeft.setObjectName('_overlayBottomLeft')
        self._overlayBottomLeft.hide()

        # op = QGraphicsOpacityEffect(self)
        # op.setOpacity(0.3)  # 0 to 1 will cause the fade effect to kick in
        # self._overlayNotification.setGraphicsEffect(op)
        self._overlayNotification.setAutoFillBackground(True)

        gl.addWidget(self._overlayLab, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._overlayBottomLeft, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._overlayNotification, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.ng_browser_container.setLayout(gl)
        gl.setContentsMargins(0, 0, 0, 0)
        lab = VerticalLabel('Neuroglancer 3DEM View')
        # lab.setStyleSheet('background-color: #ffe135;')
        lab.setObjectName('label_ng')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0,0,0,0)
        hbl.addWidget(lab)
        hbl.addWidget(self.ng_browser_container)
        self.ng_browser_container_outer = QWidget()
        self.ng_browser_container_outer.setObjectName('ng_browser_container_outer')
        self.ng_browser_container_outer.setLayout(hbl)


    def initUI_details(self):
        '''Layer View Widget'''
        logger.info('')
        self.layer_view_widget = LayerViewWidget()
        self.layer_view_widget.setObjectName('layer_view_widget')
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.layer_view_widget)
        self.label_overview = VerticalLabel('Project Data Table View')
        self.label_overview.setObjectName('label_overview')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.label_overview)
        hbl.addLayout(vbl)
        self.layer_view_container = QWidget(parent=self)
        self.layer_view_container.setObjectName('layer_view_container')
        self.layer_view_container.setLayout(hbl)


    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self._treeview = QTreeView()
        # self._treeview.setStyleSheet('background-color: #ffffff;')
        self._treeview_model = JsonModel()
        self._treeview.setModel(self._treeview_model)
        self._treeview.header().setSectionResizeMode(0, QHeaderView.Stretch)
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
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        self.snr_plot_widget = QWidget()
        self.snr_plot_widget.setObjectName('snr_plot_widget')
        self._plot_Xaxis = QLabel('Serial Section #')
        self._plot_Xaxis.setStyleSheet('color: #f3f6fb; font-size: 14px;')
        self._plot_Xaxis.setContentsMargins(0, 0, 0, 8)
        self._plot_Xaxis.setFont(font)
        vbl.addLayout(hbl)
        vbl.addWidget(self._plot_Xaxis, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.snr_plot_widget.setLayout(vbl)
        try:
            self.snr_plot.initSnrPlot() #To set up some basic plot characteristics
        except:
            pass


    def initUI_tab_widget(self):
        '''Tab Widget'''
        logger.info('')
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet('QTabBar::tab { height: 22px; width: 84px; }')
        self._tabs.setDocumentMode(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setObjectName('project_tabs')
        self._addTab(widget=self.ng_browser_container_outer, name=' 3DEM ')
        self._addTab(widget=self.layer_view_container, name=' Table ')
        self._addTab(widget=self._wdg_treeview, name=' Tree ')
        self._addTab(widget=self.snr_plot_widget, name=' SNR Plot ')
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