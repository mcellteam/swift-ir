#!/usr/bin/env python3

import os
import logging
import qtawesome as qta
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout,QLabel, QPushButton, QLineEdit
from qtpy.QtCore import Qt, QSize, QUrl
from qtpy.QtGui import QPixmap
from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from src.helpers import print_exception
import src.config as cfg

logger = logging.getLogger(__name__)

__all__ = ['WebBrowser']

class WebEnginePage(QWebEnginePage):
    def __init__(self, *args, **kwargs):
        QWebEnginePage.__init__(self, *args, **kwargs)


class WebBrowser(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.browser = QWebEngineView()
        self.browser.loadFinished.connect(self.updateTabLabel)
        self.browser.urlChanged.connect(self.updateUrlBar)
        self.page = WebEnginePage()

        def browser_backward():
            self.browser.page().triggerAction(QWebEnginePage.Back)

        def browser_forward():
            self.browser.page().triggerAction(QWebEnginePage.Forward)

        def browser_reload():
            self.browser.page().triggerAction(QWebEnginePage.Reload)

        def browser_view_source():
            self.browser.page().triggerAction(QWebEnginePage.ViewSource)

        def browser_copy():
            self.browser.page().triggerAction(QWebEnginePage.Copy)

        def browser_paste():
            self.browser.page().triggerAction(QWebEnginePage.Paste)

        def browser_3dem_community():
            self.browser.setUrl(
                QUrl('https://3dem.org/workbench/data/tapis/community/data-3dem-community/'))

        def browser_documentation():
            self.browser.setUrl(
                QUrl('https://github.com/mcellteam/swift-ir/blob/development_ng/README_SWIFTIR.md'))

        def browser_wolframalpha():
            self.browser.setUrl(QUrl('https://www.wolframalpha.com/'))

        buttonBrowserBack = QPushButton()
        buttonBrowserBack.setStatusTip('Go Back')
        buttonBrowserBack.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserBack.clicked.connect(browser_backward)
        buttonBrowserBack.setFixedSize(QSize(20, 20))
        buttonBrowserBack.setIcon(qta.icon('fa.arrow-left', color=cfg.ICON_COLOR))

        buttonBrowserForward = QPushButton()
        buttonBrowserForward.setStatusTip('Go Forward')
        buttonBrowserForward.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserForward.clicked.connect(browser_forward)
        buttonBrowserForward.setFixedSize(QSize(20, 20))
        buttonBrowserForward.setIcon(qta.icon('fa.arrow-right', color=cfg.ICON_COLOR))

        buttonBrowserRefresh = QPushButton()
        buttonBrowserRefresh.setStatusTip('Refresh')
        buttonBrowserRefresh.setIcon(qta.icon("ei.refresh", color=cfg.ICON_COLOR))
        buttonBrowserRefresh.setFixedSize(QSize(20, 20))
        buttonBrowserRefresh.clicked.connect(browser_reload)

        # buttonBrowserViewSource = QPushButton()
        # buttonBrowserViewSource.setStatusTip('View Source')
        # buttonBrowserViewSource.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # buttonBrowserViewSource.clicked.connect(browser_view_source)
        # buttonBrowserViewSource.setFixedSize(QSize(20, 20))
        # buttonBrowserViewSource.setIcon(qta.icon('ri.code-view', color=cfg.ICON_COLOR))

        buttonBrowserCopy = QPushButton('Copy')
        buttonBrowserCopy.setStyleSheet('font-size: 10px;')
        buttonBrowserCopy.setStatusTip('Copy Text')
        buttonBrowserCopy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserCopy.clicked.connect(browser_copy)
        buttonBrowserCopy.setFixedSize(QSize(40, 20))

        buttonBrowserPaste = QPushButton('Paste')
        buttonBrowserPaste.setStyleSheet('font-size: 10px;')
        buttonBrowserPaste.setStatusTip('Paste Text')
        buttonBrowserPaste.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonBrowserPaste.clicked.connect(browser_paste)
        buttonBrowserPaste.setFixedSize(QSize(40, 20))

        button3demCommunity = QPushButton('3DEM Community Data')
        button3demCommunity.setStyleSheet('font-size: 9px;')
        button3demCommunity.setStatusTip('Vist the 3DEM Community Workbench')
        button3demCommunity.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button3demCommunity.clicked.connect(browser_3dem_community)
        button3demCommunity.setFixedSize(QSize(110, 20))

        buttonDocumentation = QPushButton('AlignEM-SWiFT Docs')
        buttonDocumentation.setStyleSheet('font-size: 9px;')
        buttonDocumentation.setStatusTip('View AlignEM-SWiFT Documentation')
        buttonDocumentation.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttonDocumentation.clicked.connect(browser_documentation)
        buttonDocumentation.setFixedSize(QSize(110, 20))

        # buttonWolframAlpha = QPushButton('WolframAlpha')
        # buttonWolframAlpha.setStyleSheet('font-size: 9px;')
        # buttonWolframAlpha.setStatusTip('Go to WolframAlpha')
        # buttonWolframAlpha.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # buttonWolframAlpha.clicked.connect(browser_wolframalpha)
        # buttonWolframAlpha.setFixedSize(QSize(90, 20))

        self.urlBar = QLineEdit()
        self.urlBar.setMinimumWidth(400)
        self.urlBar.returnPressed.connect(self.navigateToUrl)

        self.httpsicon = QLabel()  # Yes, really!
        self.httpsicon.setPixmap(QPixmap(os.path.join('icons', 'lock-nossl.png')))

        hbl = QHBoxLayout()
        hbl.setContentsMargins(0, 2, 0, 0)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserBack, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(buttonBrowserForward, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserRefresh, alignment=Qt.AlignmentFlag.AlignLeft)
        # hbl.addWidget(QLabel(' '))
        # hbl.addWidget(buttonBrowserViewSource, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserCopy, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonBrowserPaste, alignment=Qt.AlignmentFlag.AlignLeft)
        hbl.addWidget(QLabel('   |   '))
        hbl.addWidget(button3demCommunity, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(QLabel(' '))
        hbl.addWidget(buttonDocumentation, alignment=Qt.AlignmentFlag.AlignRight)
        hbl.addWidget(QLabel(' '))
        # hbl.addWidget(buttonWolframAlpha, alignment=Qt.AlignmentFlag.AlignRight)
        # hbl.addWidget(QLabel(' '))
        hbl.addWidget(self.urlBar, alignment=Qt.AlignmentFlag.AlignCenter)

        browser_controls_widget = QWidget()
        browser_controls_widget.setFixedHeight(22)
        browser_controls_widget.setLayout(hbl)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 2, 0, 0)
        self.layout.addWidget(browser_controls_widget, alignment=Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.browser)

        self.setLayout(self.layout)


    def urlChangeed(self):
        pass


    def open(self, url='https://www.google.com/'):
        self.page.profile().clearHttpCache()
        self.browser.setPage(self.page)
        self.browser.load(QUrl(url))
        self.browser.show()


    def setUrl(self, url):
        logger.info('Setting URL to %s' % url)
        self.browser.setUrl(QUrl(url))


    def navigateToUrl(self):
        try:
            q = QUrl(self.urlBar.text())
            if q.scheme() == "":
                q.setScheme("http")
            self.browser.setUrl(q)
        except:
            print_exception()
            logger.warning('Unable to navigate to the requested URL')


    def updateUrlBar(self, q):
        if q.scheme() == 'https':
            # Secure padlock icon
            self.httpsicon.setPixmap(QPixmap(os.path.join('icons', 'lock-ssl.png')))

        else:
            # Insecure padlock icon
            self.httpsicon.setPixmap(QPixmap(os.path.join('icons', 'lock-nossl.png')))

        self.urlBar.setText(q.toString())
        self.urlBar.setCursorPosition(0)


    def updateTabLabel(self):
        if cfg.main_window._getTabType() == 'WebBrowser':
            try:
                tab_index = cfg.main_window.globTabs.indexOf(cfg.main_window.browser)
                tab_text = cfg.main_window.globTabs.currentWidget().browser.title()
                if tab_text == 'https://www.google.com':
                    tab_text = 'Google'
                elif tab_text == 'https://www.wolframalpha.com/':
                    tab_text = 'WolframAlpha'
                logger.info('Setting tab text: %s' % tab_text)
                cfg.main_window.globTabs.setTabText(tab_index, tab_text)
            except:
                logger.warning('There was a problem updating the web browser tab text')

