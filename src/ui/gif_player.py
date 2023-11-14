import os, sys, logging, inspect
import qtawesome as qta
import libtiff
libtiff.libtiff_ctypes.suppress_warnings()
from qtpy.QtWidgets import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from src.ui.layouts import HBL, VBL, GL, HW, VW, HSplitter, VSplitter
import src.config as cfg


__all__ = ['GifPlayer']

logger = logging.getLogger(__name__)


class GifPlayer(QWidget):
    def __init__(self, dm, parent=None):
        QWidget.__init__(self, parent)
        self.color = QColor(0, 0, 0)
        self.dm = dm
        self.min = 1
        self.max = 100
        # sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # sizePolicy.setHeightForWidth(True)
        # self.setSizePolicy(sizePolicy)
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 1007-
        self.path = self.dm.path_gif()
        # self.movie = QMovie(self.path, QByteArray(), self)
        # self.movie = QMovie(path)
        # self.setMinimumSize(QSize(128,128))
        self.label = QLabel()
        # self.label.setSizePolicy(sizePolicy)
        # self.label.setAutoFillBackground(True)
        # self.label.setScaledContents(True)
        # self.label.setMinimumSize(QSize(64,64)) #1007-
        # self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("border: 2px inset #141414; border-radius: 4px;")

        # self.label.setMovie(self.movie)
        # self.movie.setCacheMode(QMovie.CacheAll)
        # self.movie.loopCount()
        # self.movie.frameChanged.connect(lambda: print(f"getFrameScale changed! {self.movie.currentFrameNumber()}"))
        # self.movie.start()

        self.bPlay = QPushButton()
        self.bPlay.setStyleSheet("""color: #f3f6fb; background-color:  rgba(255, 255, 255, 200);""")
        # self.bPlay.setAutoFillBackground(False)
        self.bPlay.setCheckable(True)
        self.bPlay.setChecked(True)
        self.bPlay.setFixedSize(QSize(22, 22))
        self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))
        self.bPlay.clicked.connect(self.onPlayButton)

        self.bBlink = QPushButton()
        # self.bBlink.setStyleSheet("""color: #f3f6fb; background: none;""")
        # self.bBlink.setAutoFillBackground(False)
        self.bBlink.setStyleSheet("""color: #f3f6fb; background-color:  rgba(255, 255, 255, 10);""")
        self.bBlink.setFixedSize(QSize(22, 22))
        self.bBlink.setToolTip(self.path)
        self.bBlink.setIcon(qta.icon('fa.eye', color='#161c20'))
        self.bBlink.clicked.connect(self.on_click)
        self.bBlink.setEnabled(False)


        self.rb0 = QRadioButton('Pairwise Alignment')
        self.rb0.setStyleSheet("font-size: 10px; color: #ffe135; font-weight: 600; "
                               "padding: 2px; background-color: rgba(0, 0, 0, 0.5);"
                               "border-radius: 4px;")
        self.rb0.clicked.connect(self.set)
        # self.rbZarrRaw.setStyleSheet(style)

        self.rb1 = QRadioButton('Cumulative Alignment')
        self.rb1.setStyleSheet("font-size: 10px; color: #ffe135; font-weight: 600; "
                               "padding: 2px; background-color: rgba(0, 0, 0, 0.5);"
                               "border-radius: 4px;")
        self.rb1.clicked.connect(self.set)
        # self.rbZarrTransformed.setStyleSheet(style)

        self.bg = QButtonGroup()
        self.bg.addButton(self.rb0)
        self.bg.addButton(self.rb1)
        self.bg.setExclusive(True)
        self.rb0.setChecked(True)

        self.radiobuttons = HW(self.rb0, self.rb1)
        self.radiobuttons.layout.setAlignment(Qt.AlignBottom)
        # self.radiobuttons.setStyleSheet("font-size: 10px; color: #339933; font-weight: 600;")


        self.labNull = QLabel('No Data.')
        self.labNull.setAlignment(Qt.AlignCenter)

        self.labSlr = QLabel('Blink Speed: ')

        self.slrGif = QSlider(Qt.Horizontal, self)
        # self.slrGif.setStyleSheet("""
        # QSlider::handle:horizontal {
        # background-color: #ede9e8;
        # height: 10px;
        # width:4px;
        # margin-top: -2px;
        # margin-bottom: -2px;
        # border-radius: 4px;
        # }
        # QSlider::groove:horizontal {
        # border: 1px solid #bbb;```
        #
        # height: 10px;
        # border-radius: 4px;
        # }
        # """)
        # self.slrGif.setMaximumWidth(100)
        self.slrGif.setRange(self.min, self.max)
        def fn_slrGif(val):
            caller = inspect.stack()[1].function
            if caller == 'main':
                self.set_speed(val)

        self.slrGif.valueChanged[int].connect(fn_slrGif)

        self.labMs = QLabel('ms')
        self.labMs.setStyleSheet("color: #f3f6fb;")

        self.leSlr = QLineEdit()
        def fn():
            val = int(self.leSlr.text())
            logger.info(f'[{val}]')
            self.set_speed(val)
        # self.leSlr.textEdited.connect(fn)
        self.leSlr.textEdited[str].connect(fn)
        self.leSlr.setAlignment(Qt.AlignCenter)
        self.leSlr.setValidator(QIntValidator(self.min, self.max))
        self.leSlr.setMaximumWidth(34)
        # self.leSlr.setStyleSheet("color: #f3f6fb; border: 1px solid #f3f6fb;")
        # self.leSlr.setStyleSheet("border: 1px solid #f3f6fb;")
        # self.leW = HW(self.leSlr, self.labMs)
        self.wSlrGif = HW(self.labSlr, self.slrGif, self.leSlr)
        self.wSlrGif.layout.setContentsMargins(4,4,4,4)
        self.wSlrGif.setMaximumWidth(150)

        # self.controls = HW(self.bBlink, self.bPlay)
        self.controls = HW(self.bBlink, self.bPlay)
        # self.controls = HW(self.bBlink, self.bPlay, self.radiobuttons)
        self.controls.layout.setContentsMargins(4,4,4,4)
        self.controls.layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # self.controls.move(2, 2)
        self.gl = GL()
        self.vl = QVBoxLayout()
        self.vl.setContentsMargins(0,0,0,0)
        self.vl.setSpacing(2)
        self.gl.setContentsMargins(0,0,0,0)
        self.gl.addWidget(self.labNull, 0, 0, 3, 3)
        self.gl.addWidget(self.label, 0, 0, 3, 3)
        self.gl.addWidget(self.controls, 0, 0, 0, 0)
        self.gl.addWidget(self.radiobuttons, 2, 1, 1, 1)
        self.gl.addWidget(self.wSlrGif, 2, 2, 1, 1)
        self.gl.setRowStretch(0, 0)
        self.gl.setRowStretch(1, 9)
        self.gl.setColumnStretch(0, 0)
        self.gl.setColumnStretch(1, 9)
        self.w = QWidget()
        self.w.setLayout(self.gl)
        # self.setStyleSheet("""color: #f3f6fb; background-color: rgba(255, 255, 255, 160);""")
        # self.setStyleSheet("""color: #f3f6fb; background-color: #000000;""")

        # self.timerGif = QTimer(self)
        # self.timerGif.setInterval(750)
        # self.timerGif.setSingleShot(False)
        # self.timerGif.timeout.connect(self.on_click)

        self.vl.addWidget(self.w)
        # self.vl.addWidget(self.wSlrGif)

        self.setLayout(self.vl)
        # self.setStyleSheet(f"background-color: #000000;")

    # @Slot()
    # def _onRadiobutton(self):
    #     logger.info('')
    #     pass

    @Slot()
    def set_speed(self, val):
        # self.movie.stop()
        # self.movie.start()
        # logger.info(f'Setting animation speed: {val}')
        self.movie.stop()
        cfg.preferences['gif_speed'] = val
        self.movie.setSpeed(val)
        self.leSlr.setText('%d' % val)
        self.slrGif.setValue(val)
        self.label.setMovie(self.movie)
        # self.label.update()
        self.movie.start()
        # cfg.mw.saveUserPreferences(silent=True) #1015-


    def start(self):
        logger.info('')
        # self.timerGif.start()
        self.movie.start()
        self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))

    def stop(self):
        logger.info('')
        # self.timerGif.stop()

        self.movie.stop()
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

    def set(self):
        # self.movie = QMovie(self.path, QByteArray(), self)
        path_cafm_gif = self.dm.path_cafm_gif()
        self.path = path_gif = self.dm.path_gif()
        if self.radiobuttons.isVisible():
            if self.rb1.isChecked():
                self.path = path_cafm_gif
            else:
                self.path = path_gif
        self.movie = QMovie(self.path)
        self.movie.setCacheMode(QMovie.CacheAll)
        # self.movie.setSpeed(5)
        # self.movie.loopCount()
        # self.movie.frameChanged.connect(lambda: print(f"getFrameScale changed! {self.movie.currentFrameNumber()}"))
        self.movie.setFileName(self.path)
        self.label.setMovie(self.movie)
        speed = max(5, cfg.preferences['gif_speed'])
        # cfg.preferences['gif_speed'] = speed
        self.set_speed(speed)
        # self.leSlr.setText('%d' % speed)
        # self.movie.setSpeed(speed)
        # self.slrGif.setValue(speed)
        self.movie.start()
        self.update()

    @Slot()
    def on_click(self):
        # logger.info('')
        # self.movie = QMovie(self.path, QByteArray(), self)
        # self.label.setMovie(self.movie)
        self.movie.start()
        # pass

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        # qp.fillRect(event.rect(), QBrush(self.color))

        # self.r = QRect(0, 0, self.width(), self.height())

        # font = QFont()
        # font.setFamily('Ubuntu')
        # fsize = 20
        # font.setPointSize(fsize)
        # font.setWeight(10)
        # qp.setFont(font)
        # qp.setPen(QColor('#fd411e'))
        #
        # textFill = QColor('#ffffff')
        # textFill.setAlpha(128)
        # qp.fillRect(QRect(QPoint(0, 0), QSize(100, 200)), QBrush(textFill))
        # pixmap = QPixmap(100, 100)
        # pixmap.fill(Qt.transparent)

        # qp.setPen(QPen(Qt.green, 4, Qt.SolidLine))
        # qp.drawEllipse(pixmap.rect().adjusted(4, 4, -4, -4))
        # qp.drawText(QPointF(100, 100), 'TEEEST')

        qp.end()

    def sizeHint(self):
        if self.isVisible():
            return QSize(256,256)
        else:
            return QSize(0, 0)

    # def resizeEvent(self, event):
    #     rect = self.geometry()
    #     size = QSize(min(rect.width(), rect.height()), min(rect.width(), rect.height()))
    #     self.movie.setScaledSize(size)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    path = '/Users/joelyancey/alignem_data/alignments/r34_full_series/new_alignment3/gif/s4/R34CA1-BS12.122.gif'
    player = GifPlayer(path)
    # player = GifPlayer2("bla bla", path)
    player.show()
    sys.exit(app.exec_())
