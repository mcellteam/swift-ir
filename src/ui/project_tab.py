#!/usr/bin/env python3

import sys, logging, inspect
import neuroglancer as ng
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QGroupBox, QFormLayout, QLabel, QScrollArea, \
    QVBoxLayout, QSizePolicy, QHBoxLayout, QPushButton, QComboBox, QSpinBox, QStyleOption, QStyle, QTabBar, \
    QTabWidget, QGridLayout, QHeaderView, QTreeView, QGraphicsOpacityEffect, QSplitter
from qtpy.QtCore import Qt, QSize, QRect, QUrl
from qtpy.QtGui import QPainter, QFont, QPixmap
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
        # self.initUI_mini_view()
        self.initUI_tab_widget()
        self._tabs.currentChanged.connect(self._onTabChange)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ng_browser.setFocusPolicy(Qt.StrongFocus)
        self.arrangement = 0



    def _onTabChange(self, index=None):
        if index == None: index = self._tabs.currentIndex()
        if index == 0:
            self.updateNeuroglancer()
        if index == 1:
            self.layer_view_widget.set_data()
        if index == 2:
            self.updateJsonWidget()
        if index == 3:
            self.snr_plot.data = self.datamodel
            # self.snr_plot.plotData()
            self.snr_plot.initSnrPlot()
            self.snr_plot.updateSpecialLayerLines()
            self.updatePlotThumbnail()


        QApplication.processEvents()
        self.repaint()

    def initNeuroglancer(self, layout=None, matchpoint=None):
        caller = inspect.stack()[1].function
        logger.info(f'caller: {caller}')
        if cfg.data:
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
        # self._overlayNotification = QLabel('')
        # self._overlayNotification.setStyleSheet('background-color: rgba(0,0,0,0);'
        #                                         'color: #ffe135;')
        # self._overlayNotification.setFixedWidth(160)
        # self._overlayNotification.setFixedHeight(120)

        self.lab_name = QLabel('Name :')
        self.lab_name.setStyleSheet('font-weight: 650;')
        # self.lab_name.setFont(f)
        self.lab_snr = QLabel('SNR: :')
        self.lab_skipped = QLabel('Skipped Layers : []')
        self.lab_match_point = QLabel('Match Point Layers : []')

        self._layer_details = (
            QLabel('Name :'),
            QLabel('SNR :'),
            QLabel('Skipped Layers : []'),
            QLabel('Match Point Layers : []'),
        )
        for layer in self._layer_details:
            layer.setStyleSheet(
                'color: #ffe135;'
                'background-color: rgba(0,0,0,.3);'
                'margin: 0px;'
                'border-width: 1px;'
                'border-style: solid;'
                'border-color: #141414;'
            )
            layer.setWordWrap(True)
            layer.setContentsMargins(0,0,0,0)
        self._widgetArea_details = WidgetArea(parent=self, title='Details', labels=self._layer_details)
        # self._widgetArea_details.setStyleSheet('background-color: rgba(0,0,0,.1);'
        #                                        'color: #f3f6fb;'
        #                                        'margin: 0px;')
        self._widgetArea_details.hideTitle()
        self._widgetArea_details.setTitleStyle(
            'font-size: 10px; '
            'color: #f3f6fb;'
            'font-weight: 500;'
        )
        # self._widgetArea_details._title.setStylesheet(
        #     'font-size: 10px; '
        #     'font-weight: 500;'
        #     'color: #f3f6fb;')

        # font = QFont()
        # font.setFamily("Courier New")
        # self._overlayNotification.setFont(font)
        # self._overlayNotification.setObjectName('_overlayNotification')
        # self._scrollNotification = QScrollArea()
        self._widgetArea_details.setFixedWidth(224)
        self._widgetArea_details.setFixedHeight(80)
        self._widgetArea_details.setStyleSheet('font-size: 10px;'
                                               'background-color: rgba(0,0,0,0);'
                                               'border-radius: 2px;'
                                               'margin: 5px;')
        self._widgetArea_details.setContentsMargins(0, 0, 0, 0)
        # self._scrollNotification.setWidget(self._overlayNotification)
        # self._scrollNotification.setWidget(self._widgetArea_details)
        # self._scrollNotification.setWidgetResizable(True)
        self._widgetArea_details.hide()

        '''
           # 'border-width: 1px;'
           # 'border-style: solid;'
           # 'border-color: #141414;'
        
        
        QLabel#_overlayNotification {
        /*color: #141414;*/
        /*color: #f3f6fb;*/
        color: #ffe135;
        font-size: 12px;
        font-weight: 600;
        /*background-color: #1b1e23;*/
        background-color: rgba(0, 0, 0, 100);
        border-width: 1px;
        border-style: solid;
        border-color: #141414;
}
        
        '''


        self._overlayBottomLeft = QLabel()
        self._overlayBottomLeft.setObjectName('_overlayBottomLeft')
        self._overlayBottomLeft.hide()

        # op = QGraphicsOpacityEffect(self)
        # op.setOpacity(0.3)  # 0 to 1 will cause the fade effect to kick in
        # self._overlayNotification.setGraphicsEffect(op)
        # self._overlayNotification.setAutoFillBackground(True)

        gl.addWidget(self._overlayLab, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._overlayBottomLeft, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        # gl.addWidget(self._overlayNotification, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        gl.addWidget(self._widgetArea_details, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.ng_browser_container.setLayout(gl)
        gl.setContentsMargins(0, 0, 0, 0)
        lab = VerticalLabel('Neuroglancer 3DEM View')
        # lab.setStyleSheet('background-color: #ffe135;')
        lab.setObjectName('label_ng')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(0,0,0,0)
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

    def updatePlotThumbnail(self):
        pixmap = QPixmap(cfg.data.thumbnail())
        # size = pixmap.size()
        # pixmap = pixmap.scaled(128, 128, Qt.KeepAspectRatio)
        # pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pixmap = pixmap.scaled(128, 128, aspectRatioMode=Qt.KeepAspectRatio)
        self._thumbnail_src.setPixmap(pixmap)
        self.source_thumb_and_label.show()
        if cfg.data.is_aligned():
            # pixmap = QPixmap(cfg.data.thumbnail_aligned()).scaled(150, 150, Qt.KeepAspectRatio)
            pixmap = QPixmap(cfg.data.thumbnail_aligned())
            # size = pixmap.size()
            # pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = pixmap.scaled(128, 128, aspectRatioMode=Qt.KeepAspectRatio)
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
        # gl.setContentsMargins(4, 4, 4, 4)
        gl.setContentsMargins(4, 4, 4, 4)
        gl.setRowStretch(0, 1)
        gl.setRowStretch(1, 1)
        gl.setColumnStretch(0, 1)

        # vbl.addWidget(self._lab_source_thumb, alignment=Qt.AlignmentFlag.AlignBottom)
        # vbl.addWidget(self._thumbnail_src, alignment=Qt.AlignmentFlag.AlignTop)
        # vbl.addWidget(self._lab_aligned_thumb, alignment=Qt.AlignmentFlag.AlignBottom)
        # vbl.addWidget(self._thumbnail_aligned, alignment=Qt.AlignmentFlag.AlignTop)

        gl.addWidget(self.source_thumb_and_label, 0, 0)
        gl.addWidget(self.aligned_thumb_and_label, 1, 0)
        w2 = QWidget()
        w2.setLayout(gl)


        self.snr_plot_widget = QSplitter(Qt.Orientation.Horizontal)
        self.snr_plot_widget.setObjectName('snr_plot_widget')
        self.snr_plot_widget.addWidget(w1)
        self.snr_plot_widget.addWidget(w2)
        # self.snr_plot_widget.setSizes([1000, 150])

        # self.snr_plot_widget.setLayout(vbl)
        try:
            self.snr_plot.initSnrPlot() #To set up some basic plot characteristics
        except:
            pass


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
        self._addTab(widget=self.ng_browser_container_outer, name=' 3DEM ')
        self._addTab(widget=self.layer_view_container, name=' Table ')
        self._addTab(widget=self._wdg_treeview, name=' Tree ')
        self._addTab(widget=self.snr_plot_widget, name=' SNR Plot ')
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