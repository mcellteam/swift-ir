import sys, logging, inspect
import qtawesome as qta
# import libtiff
# libtiff.libtiff_ctypes.suppress_warnings()
from qtpy.QtWidgets import *
from qtpy.QtGui import *
from qtpy.QtCore import *
from src.ui.layouts.layouts import GL, HW, VW
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
        self.path = self.dm.path_gif()

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("border: 2px inset #141414; border-radius: 4px;")

        self.bPlay = QPushButton()
        self.bPlay.setStyleSheet("""color: #f3f6fb; background-color:  rgba(255, 255, 255, 200);""")
        self.bPlay.setCheckable(True)
        self.bPlay.setChecked(True)
        self.bPlay.setFixedSize(QSize(22, 22))
        # self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))
        self._paused = True
        self.bPlay.setIcon(qta.icon('fa.play', color='#161c20'))
        self.bPlay.clicked.connect(self.onPlayButton)

        self.bBlink = QPushButton()
        # self.bBlink.setStyleSheet("""color: #f3f6fb; background-color:  rgba(255, 255, 255, 10);""")
        self.bBlink.setFixedSize(QSize(22, 22))
        self.bBlink.setToolTip(self.path)
        # self.bBlink.setIcon(qta.icon('fa.eye', color='#161c20'))
        self.bBlink.setIcon(qta.icon('ri.eye-line', color='#161c20'))
        self.bBlink.clicked.connect(self.blink)
        # self.bBlink.setEnabled(False)

        self.labSlr = QLabel('Blink Speed: ')

        self.slrGif = QSlider(Qt.Horizontal, self)
        self.rb0 = QRadioButton('Pairwise')
        self.rb0.clicked.connect(self.set)
        self.rb1 = QRadioButton('Cumulative')
        self.rb1.clicked.connect(self.set)

        self.bg = QButtonGroup()
        self.bg.addButton(self.rb0)
        self.bg.addButton(self.rb1)
        self.bg.setExclusive(True)
        self.rb0.setChecked(True)


        self.labNull = QLabel('No Data.')
        self.labNull.setAlignment(Qt.AlignCenter)

        self.slrGif.setRange(self.min, self.max)
        def fn_slrGif(val):
            caller = inspect.stack()[1].function
            if caller == 'main':
                self.set_speed(val)

        self.slrGif.valueChanged[int].connect(fn_slrGif)

        self.labMs = QLabel('ms')
        self.labMs.setStyleSheet("color: #f3f6fb;")

        self.leSlr = QLineEdit()
        self.leSlr.setAlignment(Qt.AlignCenter)
        def fn():
            val = int(self.leSlr.text())
            logger.info(f'[{val}]')
            self.set_speed(val)
        # self.leSlr.textEdited.connect(fn)
        self.leSlr.textEdited[str].connect(fn)
        self.leSlr.setAlignment(Qt.AlignCenter)
        self.leSlr.setValidator(QIntValidator(self.min, self.max))
        self.leSlr.setFixedWidth(40)
        self.wSlrGif = HW(self.labSlr, self.slrGif, self.leSlr)
        self.wSlrGif.layout.setContentsMargins(4,4,4,4)
        self.wSlrGif.setMaximumWidth(150)

        self.controls2 = VW(self.rb0, self.rb1, self.wSlrGif)
        self.controls2.setStyleSheet("font-size: 10px; color: #ffe135; "
                                        "padding: 2px; background-color: rgba(0, 0, 0, 0.5);"
                                        "border-radius: 2px;")
        self.controls2.layout.setAlignment(Qt.AlignTop | Qt.AlignRight)

        self.controls = HW(self.bBlink, self.bPlay)
        self.controls.layout.setContentsMargins(4,4,4,4)
        self.controls.layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.gl = GL()
        self.vl = QVBoxLayout()
        self.vl.setContentsMargins(0,0,0,0)
        self.vl.setSpacing(2)
        self.gl.setContentsMargins(0,0,0,0)
        self.gl.addWidget(self.labNull, 0, 0, 3, 3)
        self.gl.addWidget(self.label, 0, 0, 3, 3)
        self.gl.addWidget(self.controls, 0, 0, 1, 1)
        self.gl.addWidget(self.controls2, 0, 2, 1, 1)
        self.gl.setRowStretch(0, 0)
        self.gl.setRowStretch(1, 9)
        self.gl.setColumnStretch(0, 0)
        self.gl.setColumnStretch(1, 9)
        self.w = QWidget()
        self.w.setLayout(self.gl)

        self.vl.addWidget(self.w)

        self.setLayout(self.vl)

    # @Slot()
    # def _onRadiobutton(self):
    #     logger.info('')
    #     pass

    @Slot()
    def start(self):
        logger.info('')
        self.bBlink.setIcon(qta.icon('ri.eye-line', color='#161c20'))
        # self.timerGif.start()
        self.movie.start()
        self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))

    @Slot()
    def stop(self):
        logger.info('')
        self.bBlink.setIcon(qta.icon('ri.eye-close-line', color='#161c20'))
        # self.timerGif.stop()
        self.movie.stop()
        self.bPlay.setIcon(qta.icon('fa.play', color='#161c20'))

    def onPlayButton(self):
        logger.info('')
        if self._paused:
            self.resume()
        else:
            self.pause()

    @Slot()
    def set_speed(self, val):
        # self.movie.stop()
        # self.movie.start()
        # logger.info(f'Setting animation speed: {val}')
        # self.stop() #1122-
        cfg.preferences['gif_speed'] = val # not data-driven
        self.movie.setSpeed(val)
        self.leSlr.setText('%d' % val)
        self.slrGif.setValue(val)
        self.label.setMovie(self.movie)
        # self.label.update()
        # self.start() #1122-
        # cfg.mw.saveUserPreferences(silent=True) #1015-

    def set(self, start=True):
        self.bBlink.setIcon(qta.icon('ri.eye-line', color='#161c20'))
        # self.movie = QMovie(self.file_path, QByteArray(), self)
        path_cafm_gif = self.dm.path_cafm_gif()
        self.path = path_gif = self.dm.path_gif()
        if self.controls2.isVisible():
            if self.rb1.isChecked():
                self.path = path_cafm_gif
            else:
                self.path = path_gif
        self.movie = QMovie(self.path)
        self.movie.setCacheMode(QMovie.CacheAll)
        # self.movie.frameChanged.connect(lambda: print(f"getFrameScale changed! {self.movie.currentFrameNumber()}"))
        self.movie.setFileName(self.path)
        self.label.setMovie(self.movie)

        # self.leSlr.setText('%d' % speed)
        self.movie.start()
        if start:
            self.resume()
        else:
            self.resume()
            self.pause()

        self.update()


    @Slot()
    def pause(self):
        logger.info('')
        self._paused = True
        self.bBlink.setIcon(qta.icon('ri.eye-close-line', color='#161c20'))
        self.bPlay.setIcon(qta.icon('fa.play', color='#161c20'))
        self.movie.setPaused(True)

    @Slot()
    def resume(self):
        logger.info('')
        self._paused = False
        self.bBlink.setIcon(qta.icon('ri.eye-line', color='#161c20'))
        self.bPlay.setIcon(qta.icon('fa.pause', color='#161c20'))
        self.set_speed(max(5, cfg.preferences['gif_speed']))  # calls start
        self.movie.setPaused(False)
        # self.start()


    @Slot()
    def blink(self):
        logger.info('')
        self.pause()
        frame = self.movie.currentFrameNumber()
        if frame == 1:
            self.bBlink.setIcon(qta.icon('ri.eye-line', color='#161c20'))
            self.movie.jumpToFrame(2)
        elif frame in (0,2):
            self.bBlink.setIcon(qta.icon('ri.eye-close-line', color='#161c20'))
            self.movie.jumpToFrame(1)


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
    # player = GifPlayer2("bla bla", file_path)
    player.show()
    sys.exit(app.exec_())
