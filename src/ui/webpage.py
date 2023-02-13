
import logging
from qtpy.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout
from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from qtpy.QtCore import QUrl, QSize

__all__ = ['WebPage']

logger = logging.getLogger(__name__)

# class WebEnginePage(QWebEnginePage):
#     def __init__(self, *args, **kwargs):
#         QWebEnginePage.__init__(self, *args, **kwargs)
#
# class WebPage(QWidget):
#
#     def __init__(self, parent=None, url=None):
#         super(WebPage, self).__init__()
#         logger.info('')
#
#
#         self.initUI()
#
#         if url:
#             # self.open(url=url)
#             self.loadUrl(url=url)
#             self.show()
#
#
#
#     def initUI(self):
#         logger.info('')
#         self.page = WebEnginePage()
#         self.page.windowCloseRequested.connect(lambda: print('(!) windowCloseRequested'))
#         # self.view.loadFinished.connect(lambda: print('QWebengineView Load Finished!'))
#         # self.view.loadProgress.connect(lambda progress: print(f'QWebengineView Load Progress: {progress}'))
#         # self.view.urlChanged.connect(lambda terminationStatus:
#         #                              print(f'QWebengineView Render Process Terminated!'
#         #                                    f' terminationStatus:{terminationStatus}'))
#
#         self.webengineview = QWebEngineView()
#         self.webengineview.urlChanged.connect(lambda: print('QWebengineView URL Changed!'))
#         self.vbl = QVBoxLayout()
#         self.vbl.setContentsMargins(0, 0, 0, 0)
#         self.vbl.addWidget(self.webengineview)
#         self.setLayout(self.vbl)
#         self.show()
#
#
#
#
#     def open(self, url='https://www.google.com/'):
#         self.page.profile().clearHttpCache()
#         self.webengineview.setPage(self.page)
#         self.webengineview.load(QUrl(url))
#         self.webengineview.show()
#
#     def setUrl(self, url):
#         self.webengineview.setUrl(url)
#
#     def show(self):
#         self.webengineview.show()
#
#     def loadUrl(self, url:str):
#
#         url = QUrl(url)
#
#         if url.isValid():
#             self.webengineview.load(url)


class WebEnginePage(QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation """
    # Store external windows.
    external_window = None

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        print(url, _type, isMainFrame)
        if _type == QWebEnginePage.NavigationTypeLinkClicked:
            if not self.external_window:
                self.external_window = QWebEngineView()

            self.external_window.setUrl(url)
            self.external_window.show()
            return False

        return super().acceptNavigationRequest(url, _type, isMainFrame)


class WebPage(QMainWindow):
    def __init__(self, url=None, *args, **kwargs):
        super(WebPage, self).__init__(*args, **kwargs)

        self.webengineview = QWebEngineView()
        self.webengineview.setPage(WebEnginePage())
        self.setCentralWidget(self.webengineview)

        if url:
            self.setUrl(url)
            self.show()

    def setUrl(self, url):
        self.webengineview.setUrl(QUrl(url))
        self.show()

    def sizeHint(self):
        return QSize(1024, 768)


if __name__ == '__main__':
    app = QApplication([])
    # view = QWebEngineView()
    # page = WebEnginePage()
    # page.profile().clearHttpCache()
    # view.setPage(page)
    # view.load(QUrl('https://www.google.com/'))

    webpage = WebPage()
    webpage.open()
    webpage.show()

    # view.show()
    app.exec_()