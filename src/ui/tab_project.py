#!/usr/bin/env python3

'''TODO This needs to have columns for indexing and section name (for sorting!)'''

import os, sys, logging, inspect, copy, time, warnings
# from math import log10
from math import log2, sqrt
import neuroglancer as ng
import numpy as np
from qtpy.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QStyleOption, \
    QStyle, QTabBar, QTabWidget, QGridLayout, QTreeView, QSplitter, QTextEdit, QSlider
from qtpy.QtCore import Qt, QSize, QRect, QUrl
from qtpy.QtGui import QPainter, QFont, QPixmap
from qtpy.QtWebEngineWidgets import *
import src.config as cfg
from src.helpers import getOpt
from src.ng_host import EMViewer
from src.ng_host_slim import NgHostSlim
from src.helpers import print_exception
from src.ui.snr_plot import SnrPlot
from src.ui.mini_view import MiniView
from src.ui.widget_area import WidgetArea
from src.ui.project_table import ProjectTable
from src.ui.models.json_tree import JsonModel
from src.ui.doubleslider import DoubleSlider



logger = logging.getLogger(__name__)

class ProjectTab(QWidget):

    def __init__(self,
                 parent,
                 path=None,
                 datamodel=None):
        super().__init__(parent)
        logger.info(f'Initializing Project Tab...\nID(datamodel): {id(datamodel)}, Path: {path}')
        self.parent = parent
        self.path = path
        self.datamodel = datamodel
        self.ng_layout = '4panel'
        self.setUpdatesEnabled(True)
        self.ng_browser = QWebEngineView()
        self.initUI_Neuroglancer()
        self.initUI_table()
        self.initUI_JSON()
        self.initUI_plot()
        # self.initUI_mini_view()
        self.initUI_tab_widget()
        self._tabs.currentChanged.connect(self._onTabChange)
        self.ng_browser.setFocusPolicy(Qt.StrongFocus)
        self.bookmark_tab = 0


    def _onTabChange(self, index=None):
        logger.info(f'index = {str(index)}')
        if index == None:
            index = self._tabs.currentIndex()
        logger.info(f'index = {index}')
        # if index == 0:
        #     self.updateNeuroglancer() # Don't update neuroglancer -> maintain emViewer state
        if index == 1:
            # self.project_table.setScaleData()
            # self.project_table.setScaleData() #not sure why this is needed twice
            pass
        if index == 2:
            self.updateJsonWidget()
        if index == 3:
            self.snr_plot.data = cfg.data
            self.snr_plot.initSnrPlot()
            self.updatePlotThumbnail()
        # QApplication.processEvents()
        # self.repaint()


    def shutdownNeuroglancer(self):
        logger.critical('')
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_BEFORE)
        if ng.is_server_running():
            ng.server.stop()
            # time.sleep(.5)
        if cfg.USE_DELAY:
            time.sleep(cfg.DELAY_AFTER)


    def initNeuroglancer(self, matchpoint=False):
        caller = inspect.stack()[1].function
        # self.shutdownNeuroglancer()
        if caller != '_onGlobTabChange':
            logger.critical(f'Initializing Neuroglancer (caller: {inspect.stack()[1].function})...')
            if cfg.data:
                cfg.emViewer = EMViewer()
                self.updateNeuroglancer(matchpoint=matchpoint)



    def updateNeuroglancer(self, matchpoint=False):
        caller = inspect.stack()[1].function
        if caller != 'initNeuroglancer':
            logger.critical(f'Updating Neuroglancer Viewer (caller: {caller})')
        if cfg.main_window.rb0.isChecked():
            cfg.main_window.comboboxNgLayout.setCurrentText('4panel')
            cfg.emViewer.initViewerSlim()
        elif cfg.main_window.rb1.isChecked():
            cfg.main_window.comboboxNgLayout.setCurrentText('xy')
            cfg.emViewer.initViewer(matchpoint=matchpoint)
        url = cfg.emViewer.get_viewer_url()
        logger.info(f'URL:\n{url}')
        self.ng_browser.setUrl(QUrl(url))
        self._transformationWidget.setVisible(cfg.data.is_aligned_and_generated())
        self._widgetArea_details.setVisible(getOpt('neuroglancer,SHOW_ALIGNMENT_DETAILS'))
        cfg.emViewer.signals.stateChanged.connect(lambda l: cfg.main_window.dataUpdateWidgets(ng_layer=l))
        cfg.emViewer.signals.zoomChanged.connect(self.resetCrossSectionScaleSlider)
        # self.resetCrossSectionScaleSlider()
        self.resetSliderZmag()
        self.ng_browser.setFocus()

    # def addToState(self):
    #     state = copy.deepcopy(cfg.emViewer.state)
    #     state.relative_display_scales = {"z": 10}
    #     cfg.emViewer.set_state(state)
    #     cfg.LV.invalidate()

    def setNeuroglancerUrl(self):
        self.ng_browser.setUrl(QUrl(cfg.emViewer.get_viewer_url()))


    def updateNgLayer(self):
        state = copy.deepcopy(cfg.emViewer.state)
        state.position[0] = cfg.data.layer()
        cfg.emViewer.set_state(state)


    def getBrowserSize(self):
        return self.ng_browser.geometry().getRect()



    def initUI_Neuroglancer(self):
        '''NG Browser'''
        logger.info('')

        self.ng_browser.loadFinished.connect(lambda: print('QWebengineView Load Finished!'))
        self.ng_browser.loadFinished.connect(self.resetCrossSectionScaleSlider)
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
                'background-color: rgba(0,0,0,.36);'
                'margin: 1px 1px 1px 1px;'
                'border-width: 0px;'
                'border-style: solid;'
                'border-color: #141414;'
                'border-radius: 1px;'
                'margin-right: 10px;'
            )
            layer.setFixedWidth(170)
            layer.setWordWrap(True)
            layer.setContentsMargins(0,0,0,0)

        '''AFM/CAFM Widget'''
        self.afm_widget_ = QTextEdit()
        self.afm_widget_.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.afm_widget_.setObjectName('_tool_afmCafm')
        self.afm_widget_.setReadOnly(True)
        self._transformationWidget = QWidget()
        # self._transformationWidget.setFixedSize(180,80)
        self._transformationWidget.setFixedWidth(170)
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

        self._widgetArea_details.setVisible(getOpt('neuroglancer,SHOW_ALIGNMENT_DETAILS'))
        self._overlayBottomLeft = QLabel()
        self._overlayBottomLeft.setObjectName('_overlayBottomLeft')
        self._overlayBottomLeft.hide()
        gl.addWidget(self._overlayLab, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._overlayBottomLeft, 0, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)
        gl.addWidget(self._widgetArea_details, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        # gl.addWidget(cfg.main_window._tool_afmCafm, 0, 0, alignment=Qt.AlignRight | Qt.AlignBottom)
        self.ng_browser_container.setLayout(gl)
        gl.setContentsMargins(0, 0, 0, 0)
        self.ngVertLab = VerticalLabel('Neuroglancer 3DEM View')
        self.ngVertLab.setObjectName('label_ng')


        # self.crossSectionScaleSlider = QSlider(Qt.Orientation.Vertical, self)
        self.crossSectionScaleSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        # self.crossSectionScaleSlider.set
        # self.crossSectionScaleSlider.setMaximum(8.0)
        # self.crossSectionScaleSlider.setMaximum(100)
        self.crossSectionScaleSlider.setMaximum(5)
        self.crossSectionScaleSlider.setMinimum(0.0)
        # self.crossSectionScaleSlider.valueChanged.connect(self.onSliderCrossSectionScale)
        self.crossSectionScaleSlider.sliderMoved.connect(self.onSliderCrossSectionScale)
        self.crossSectionScaleSlider.setValue(4.0)

        # self.crossSectionOrientationSlider = DoubleSlider(Qt.Orientation.Vertical, self)
        # # self.crossSectionScaleSlider.setMaximum(8.0)
        # # self.crossSectionScaleSlider.setMaximum(100)
        # self.crossSectionOrientationSlider.setMaximum(5.0)
        # self.crossSectionOrientationSlider.setMinimum(-5.0)
        # self.crossSectionOrientationSlider.valueChanged.connect(self.onSliderCrossSectionOrientation)

        # self.crossSectionOrientationSliderAndLabel = QWidget()
        # self.crossSectionOrientationSliderAndLabel.setFixedWidth(24)
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # vbl.addWidget(self.crossSectionOrientationSlider)
        # vbl.addWidget(VerticalLabel('Rotation:'))
        # self.crossSectionOrientationSliderAndLabel.setLayout(vbl)

        self.crossSectionScaleSliderAndLabel = QWidget()
        self.crossSectionScaleSliderAndLabel.setFixedWidth(20)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.crossSectionScaleSlider)
        vbl.addWidget(VerticalLabel('Zoom:'))
        self.crossSectionScaleSliderAndLabel.setLayout(vbl)

        # self.crossSectionScaleSlider = QSlider(Qt.Orientation.Vertical, self)
        self.ZdisplaySlider = DoubleSlider(Qt.Orientation.Vertical, self)
        # self.crossSectionScaleSlider.set
        # self.crossSectionScaleSlider.setMaximum(8.0)
        # self.crossSectionScaleSlider.setMaximum(100)
        self.ZdisplaySlider.setMaximum(100.)
        self.ZdisplaySlider.setMinimum(1.0)
        # self.crossSectionScaleSlider.valueChanged.connect(self.onSliderCrossSectionScale)
        self.ZdisplaySlider.sliderMoved.connect(self.onSliderZmag)
        self.ZdisplaySlider.setValue(1.0)

        self.ZdisplaySliderAndLabel = QWidget()
        self.ZdisplaySliderAndLabel.setFixedWidth(20)
        vbl = QVBoxLayout()
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.ZdisplaySlider)
        vbl.addWidget(VerticalLabel('Z-Mag:'))
        self.ZdisplaySliderAndLabel.setLayout(vbl)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 0, 0, 0)
        hbl.addWidget(self.ngVertLab)
        hbl.addWidget(self.ng_browser_container)
        # hbl.addWidget(self.crossSectionScaleSlider)
        # hbl.addWidget(self.crossSectionOrientationSliderAndLabel)
        hbl.addWidget(self.ZdisplaySliderAndLabel)
        hbl.addWidget(self.crossSectionScaleSliderAndLabel)
        self.ng_browser_container_outer = QWidget()
        self.ng_browser_container_outer.setObjectName('ng_browser_container_outer')
        self.ng_browser_container_outer.setLayout(hbl)


    def resetCrossSectionScaleSlider(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            val = cfg.emViewer.state.cross_section_scale

            if val:
                if val != 0:
                    new_val = float(sqrt(val))
                    # logger.info(f'val = {val}, new_val = {new_val}')
                    self.crossSectionScaleSlider.setValue(new_val)
        except:
            print_exception()


    def onSliderCrossSectionScale(self):
        caller = inspect.stack()[1].function
        if caller not in  ('resetCrossSectionScaleSlider', 'setValue'):
            # logger.info(f'caller: {caller}')
            try:
                val = self.crossSectionScaleSlider.value()
                state = copy.deepcopy(cfg.emViewer.state)
                # new_val = log2(1 + val)
                # new_val = val * val
                # logger.info(f'val = {val}, new_val = {new_val}')
                state.cross_section_scale = val * val
                cfg.emViewer.set_state(state)
            except:
                print_exception()


    def onSliderZmag(self):
        # caller = inspect.stack()[1].function
        try:
            val = self.ZdisplaySlider.value()
            state = copy.deepcopy(cfg.emViewer.state)
            state.relative_display_scales = {'z': val}
            cfg.emViewer.set_state(state)
        except:
            print_exception()


    def resetSliderZmag(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        try:
            if cfg.main_window.rb1.isChecked():
                self.ZdisplaySlider.setValue(10)
            else:
                self.ZdisplaySlider.setValue(1)
        except:
            print_exception()

    # def onSliderCrossSectionOrientation(self):
    #     caller = inspect.stack()[1].function
    #     # if caller not in ('resetCrossSectionScaleSlider', 'setValue'):
    #     #     # logger.info(f'caller: {caller}')
    #     if cfg.emViewer.state.cross_section_scale:
    #         state = copy.deepcopy(cfg.emViewer.state)
    #         val = self.crossSectionOrientationSlider.value()
    #         logger.info(f'val={val}')
    #         # cur_val = state.cross_section_orientation
    #         state.cross_section_orientation = [0,0,0,val]
    #         cfg.emViewer.set_state(state)
    #     else:
    #         logger.warning('cfg.emViewer.state.cross_section_scale does not exist!')




    def initUI_table(self):
        '''Layer View Widget'''
        logger.info('')
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
        self.table_container = QWidget()
        self.table_container.setObjectName('table_container')
        self.table_container.setLayout(hbl)


    def updateJsonWidget(self):
        logger.info('')
        self.treeview_model.load(cfg.data.to_dict())
        self.treeview.header().resizeSection(0, 300)


    def initUI_JSON(self):
        '''JSON Project View'''
        logger.info('')
        self.treeview = QTreeView()
        self.treeview.setIndentation(20)
        self.treeview.header().resizeSection(0, 300)
        self.treeview_model = JsonModel()
        self.treeview.setModel(self.treeview_model)
        self.treeview.setAlternatingRowColors(True)
        self._wdg_treeview = QWidget()
        self._wdg_treeview.setObjectName('_wdg_treeview')
        hbl = QHBoxLayout()
        hbl.setContentsMargins(2, 0, 2, 0)
        lab = VerticalLabel('Project Dictionary/JSON Tree View')
        lab.setObjectName('label_treeview')
        hbl.addWidget(lab)
        hbl.addWidget(self.treeview)
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


        # self.snr_plot_browser = QWebEngineView()
        # w3 = QWidget()
        # vbl = QVBoxLayout()
        # vbl.setContentsMargins(0, 0, 0, 0)
        # vbl.addWidget(self.snr_plot_browser)
        # w3.setLayout(vbl)


        self.snr_plot_widget.addWidget(w1)
        self.snr_plot_widget.addWidget(w2)
        # self.snr_plot_widget.addWidget(w3)


    # def upateSnrPlotBrowser(self):
    #     cfg.emViewer = EMViewer(parent=self)
    #     cfg.emViewer.initViewerSlim()
    #     url = cfg.emViewer.get_viewer_url()
    #     self.snr_plot_browser.setUrl(QUrl(url))




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


class Thumbnail(QWidget):

    def __init__(self, parent, path):
        super().__init__(parent)
        thumbnail = ScaledPixmapLabel(self)
        pixmap = QPixmap(path)
        thumbnail.setPixmap(pixmap)
        thumbnail.setScaledContents(True)
        layout = QGridLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(thumbnail, 0, 0)
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
                pass
                # logger.warning('Cannot divide by zero')
                # print_exception()
        super().paintEvent(event)



class VerticalLabel(QLabel):

    def __init__(self, text, bg_color=None, font_color=None, font_size=None, *args):
        QLabel.__init__(self, text, *args)

        self.text = text
        self.setStyleSheet("font-size: 12px;")
        font = QFont()
        font.setBold(True)
        self.setFont(font)
        style = ''
        if bg_color:
            style += f'background-color: {bg_color};'
        if font_color:
            style += f'color: {font_color};'
        if font_size:
            style += f'font-size: {str(font_size)};'
        if style != '':
            self.setStyleSheet(style)

    def setText(self, p_str):
        self.text = p_str

    def paintEvent(self, event):
        p = QPainter(self)
        p.rotate(-90)
        rgn = QRect(-self.height(), 0, self.height(), self.width())
        align  = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter
        # align  = Qt.AlignmentFlag.AlignCenter
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.hint = p.drawText(rgn, align, self.text)
        p.end()
        self.setMaximumWidth(self.hint.height())
        self.setMinimumHeight(self.hint.width())


    def sizeHint(self):
        if hasattr(self, 'hint'):
            return QSize(self.hint.height(), self.hint.width() + 10)
        else:
            return QSize(16, 48)


    def minimumSizeHint(self):
        size = QLabel.minimumSizeHint(self)
        return QSize(size.height(), size.width())



if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    pt = ProjectTab()
    main_window.setCentralWidget(pt)
    main_window.show()
    sys.exit(app.exec_())