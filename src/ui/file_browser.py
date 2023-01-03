
#!/usr/bin/env python3

import os, sys, logging
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QFileSystemModel, \
    QPushButton, QSizePolicy
from qtpy.QtCore import Slot, Qt, QSize

try:
    import qtawesome as qta
except ImportError:
    pass
# try:
#     import src.config as cfg
# except ImportError:
#     pass


logger = logging.getLogger(__name__)

class FileBrowser(QWidget):
    def __init__(self):
        super(FileBrowser, self).__init__()
        self.treeview = QTreeView()
        self.treeview.expandsOnDoubleClick()
        self.treeview.setAnimated(True)
        self.treeview.setAlternatingRowColors(True)
        self.fileSystemModel = QFileSystemModel(self.treeview)
        self.fileSystemModel.setReadOnly(False)
        self.treeview.setModel(self.fileSystemModel)
        root = self.fileSystemModel.setRootPath(os.path.expanduser('~'))
        self.treeview.setRootIndex(root)
        # self.setSizePolicy(
        #     QSizePolicy.MinimumExpanding,
        #     QSizePolicy.MinimumExpanding
        # )
        self.treeview.setColumnWidth(0, 600)
        self.initUI()
        self.treeview.selectionModel().selectionChanged.connect(self.selectionChanged)

    def initUI(self):
        with open('src/styles/controls.qss', 'r') as f:
            style = f.read()
        self._btn_open = QPushButton('Open')
        self._btn_open.setFixedSize(86, 18)
        self._btn_open.setStyleSheet(style)

        self._btn_showFileBrowser = QPushButton('Hide Files')
        self._btn_showFileBrowser.setFixedSize(86, 18)
        self._btn_showFileBrowser.setStyleSheet(style)
        self._btn_showFileBrowser.hide()
        self._btn_showFileBrowser.clicked.connect(self._showHideFb)

        hbl = QHBoxLayout()
        hbl.setContentsMargins(4, 2, 4, 2)
        hbl.addStretch()
        hbl.addWidget(self._btn_showFileBrowser)
        hbl.addWidget(self._btn_open)
        controls = QWidget()
        controls.setFixedHeight(24)
        controls.setLayout(hbl)

        vbl = QVBoxLayout(self)
        vbl.setContentsMargins(0, 0, 0, 0)
        vbl.addWidget(self.treeview)
        vbl.addWidget(controls, alignment=Qt.AlignmentFlag.AlignLeft)
        self.setLayout(vbl)

    def selectionChanged(self):
        print('Selection Changed!')

    def showSelection(self):
        print('showSelection:')
        try:
            selection = self.fileSystemModel.itemData(self.treeview.selectedIndexes()[0])
            print(selection)
        except:
            logger.warning('Is Any File Selected?')

    def getSelection(self):
        try:
            selection = self.fileSystemModel.itemData(self.treeview.selectedIndexes()[0])
            return selection
        except:
            logger.warning('Is Any File Selected?')

    def getSelectionPath(self):
        try:
            index = self.treeview.selectedIndexes()[0]
            info  = self.treeview.model().fileInfo(index)
            path  = info.absoluteFilePath()
            print(f'getSelectionPath: {path}')
            return path
        except:
            logger.warning('No Path Selected.')

    def getOpenButton(self):
        return self._btn_open

    def showFb(self):
        self.treeview.show()

    def hideFb(self):
        self.treeview.hide()

    def showFbButton(self):
        self._btn_showFileBrowser.show()

    def hideFbButton(self):
        self._btn_showFileBrowser.hide()

    def _showHideFb(self):
        if self.treeview.isHidden():
            self.treeview.show()
            self._btn_showFileBrowser.setText('Hide Files')
        else:
            self.treeview.hide()
            self._btn_showFileBrowser.setText('File Browser')



    # def sizeHint(self):
    #     return QSize(400,200)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    main = FileBrowser()
    main.show()
    sys.exit(app.exec_())