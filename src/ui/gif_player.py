import os, sys, logging
import qtawesome as qta
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()
from qtpy.QtWidgets import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from src.ui.layouts import HBL, VBL, GL, HWidget, VWidget, HSplitter, VSplitter


__all__ = ['GifPlayer']

logger = logging.getLogger(__name__)


class GifPlayer(QWidget):
    def __init__(self, path, parent=None):
        QWidget.__init__(self, parent)
        # self.color = QColor(0, 0, 0)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHeightForWidth(True)
        self.setSizePolicy(sizePolicy)

        self.path=path
        # self.movie = QMovie(path, QByteArray(), self)
        self.movie = QMovie(path)
        # self.setMinimumSize(QSize(128,128))
        self.label = QLabel()
        self.label.setSizePolicy(sizePolicy)
        self.label.setAutoFillBackground(False)
        # self.label.setScaledContents(True)
        self.label.setMinimumSize(QSize(64,64))
        # self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setAlignment(Qt.AlignCenter)
        self.movie.setCacheMode(QMovie.CacheAll)
        self.label.setMovie(self.movie)
        self.movie.start()
        self.movie.loopCount()

        self.bPlay = QPushButton()
        self.bPlay.setStyleSheet("""color: #f3f6fb; background: none;""")
        self.bPlay.setAutoFillBackground(False)
        self.bPlay.setCheckable(True)
        self.bPlay.setChecked(True)
        self.bPlay.setFixedSize(QSize(22,22))
        self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))
        self.bPlay.clicked.connect(self.onPlayButton)

        self.bBlink = QPushButton()
        self.bBlink.setStyleSheet("""color: #f3f6fb; background: none;""")
        self.bBlink.setAutoFillBackground(False)
        self.bBlink.setStyleSheet("font-size: 11px;")
        self.bBlink.setFixedSize(QSize(22, 22))
        self.bBlink.setToolTip(self.path)
        self.bBlink.setIcon(qta.icon('fa.eye', color='#161c20'))
        self.bBlink.clicked.connect(self.on_click)
        self.bBlink.setEnabled(False)

        self.controls = HWidget(self.bBlink, self.bPlay)
        self.controls.layout.setAlignment(Qt.AlignLeft | Qt. AlignTop)
        # self.controls.move(2, 2)
        self.gl = GL()
        self.gl.setContentsMargins(10,10,10,10)
        self.gl.addWidget(self.label, 0, 0, 2, 2)
        self.gl.addWidget(self.controls, 0, 0, 0, 0)
        self.gl.setRowStretch(0, 0)
        self.gl.setRowStretch(1, 9)
        self.gl.setColumnStretch(0, 0)
        self.gl.setColumnStretch(1, 9)
        # self.setStyleSheet("""color: #f3f6fb; background-color: rgba(255, 255, 255, 160);""")
        # self.setStyleSheet("""color: #f3f6fb; background-color: #000000;""")

        self.timerGif = QTimer(self)
        self.timerGif.setInterval(500)
        self.timerGif.setSingleShot(False)
        self.timerGif.timeout.connect(self.on_click)

        self.setLayout(self.gl)

    def start(self):
        logger.info('')
        self.timerGif.start()
        self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))

    def stop(self):
        logger.info('')
        self.timerGif.stop()
        self.bPlay.setIcon(qta.icon('fa.play', color='#161c20'))

    def onPlayButton(self):
        logger.info('')
        self.bPlay.setIcon(qta.icon(('fa.play','fa.pause')[self.bPlay.isChecked()], color='#161c20'))
        if self.bPlay.isChecked():
            self.start()
            self.bBlink.setEnabled(False)
        else:
            self.stop()
            self.bBlink.setEnabled(True)

    def set(self, path):
        self.path = path
        self.movie.start()
        self.update()

    @Slot()
    def on_click(self):
        # logger.info('')
        self.movie = QMovie(self.path, QByteArray(), self)
        self.label.setMovie(self.movie)
        self.movie.start()

    # def paintEvent(self, event):
    #     painter = QPainter()
    #     painter.begin(self)
    #     painter.fillRect(event.rect(), QBrush(self.color))
    #     painter.end()

    def resizeEvent(self, event):
        rect = self.geometry()
        size = QSize(min(rect.width(), rect.height()), min(rect.width(), rect.height()))
        self.movie.setScaledSize(size)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = '/Users/joelyancey/alignem_data/alignments/r34_full_series/new_alignment3/gif/s4/R34CA1-BS12.122.gif'
    player = GifPlayer(path)
    # player = GifPlayer2("bla bla", path)
    player.show()
    sys.exit(app.exec_())
