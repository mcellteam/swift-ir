from qtpy.QtWidgets import QApplication
from qtpy.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from qtpy.QtCore import QUrl

class WebEnginePage(QWebEnginePage):
    def __init__(self, *args, **kwargs):
        QWebEnginePage.__init__(self, *args, **kwargs)
        self.featurePermissionRequested.connect(self.onFeaturePermissionRequested)

    def onFeaturePermissionRequested(self, url, feature):
        if feature in (QWebEnginePage.MediaAudioCapture,
            QWebEnginePage.MediaVideoCapture,
            QWebEnginePage.MediaAudioVideoCapture):
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)
        else:
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionDeniedByUser)

class WebPage:
    def __init__(self, url=None):
        self.page = WebEnginePage()
        self.page.windowCloseRequested.connect(lambda: print('(!) windowCloseRequested'))
        self.view = QWebEngineView()
        # self.view.loadFinished.connect(lambda: print('QWebengineView Load Finished!'))
        # self.view.loadProgress.connect(lambda progress: print(f'QWebengineView Load Progress: {progress}'))
        # self.view.urlChanged.connect(lambda: print('QWebengineView URL Changed!'))
        # self.view.urlChanged.connect(lambda terminationStatus:
        #                              print(f'QWebengineView Render Process Terminated!'
        #                                    f' terminationStatus:{terminationStatus}'))
        if url:
            self.open(url=url)
            self.show()

    def open(self, url='https://www.google.com/'):
        self.page.profile().clearHttpCache()
        self.view.setPage(self.page)
        self.view.load(QUrl(url))
        self.view.show()

    def show(self):
        self.view.show()






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