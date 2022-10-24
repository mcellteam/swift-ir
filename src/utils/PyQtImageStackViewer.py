

""" PyQtImageStackViewer.py: PyQt image stack viewer similar to that in ImageJ.
"""


import os.path
import logging
import numpy as np
# from PIL import Image
# import dask
# import dask.array
from src.config import USE_TENSORSTORE

if USE_TENSORSTORE:
    import tensorstore as ts

try:
    from qtpy.QtCore import Qt, QSize
    from qtpy.QtGui import QImage, QPixmap, QCursor, QColor
    from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QSizePolicy, QScrollBar, QToolBar, QLabel, \
        QFileDialog, QStyle, QGraphicsDropShadowEffect
except ImportError:
    try:
        from PySide6.QtCore import Qt, QSize, QSpacerItem
        from PySide6.QtGui import QImage, QPixmap, QCursor
        from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSizePolicy, QScrollBar, QToolBar, QLabel, QFileDialog, QStyle
    except ImportError:
        raise ImportError("Requires PyQt (version 5 or 6)")


from src.utils.PyQtImageViewer import QtImageViewer
import src.config as cfg
from src.helpers import are_images_imported
from src.helpers import are_aligned_images_generated
from src.helpers import get_scale_val
from src.ui.clickable import ClickablePicButton

__author__ = "Marcel Goldschen-Ohm <marcel.goldschen@gmail.com>"
__version__ = '0.1.0'


logger = logging.getLogger(__name__)



def isDarkColor(qcolor):
    darkness = 1 - (0.299 * qcolor.red() + 0.587 * qcolor.green() + 0.114 * qcolor.blue()) / 255
    return darkness >= 0.5


def invertIconColors(qicon, w, h):
    qimage = QImage(qicon.pixmap(w, h))
    qimage.invertPixels()
    pixmap = QPixmap.fromImage(qimage)
    qicon.addPixmap(pixmap)


class QtImageStackViewer(QWidget):
    """ PyQtImageStackViewer.py: PyQt image stack viewer similar to that in ImageJ.
    Uses a QtImageViewer with frame/channel sliders and a titlebar indicating current frame and mouse position
    similar to that in ImageJ.
    Display a multi-page image stack with a slider to traverse the frames in the stack.
    Can also optionally split color channels with a second slider.
    Image stack data can be loaded either directly as a NumPy 3D array [rows, columns, frames] or from file using PIL.
    If reading multi-page image data from file using PIL, only the currently displayed frame will be kept in memory,
    so loading and scrolling through even huge image stacks is very fast.
    """

    def __init__(self, image=None, role=None, parent=None):
        QWidget.__init__(self)

        self.role = role

        # Image data: NumPy array - OR - PIL image file object = PIL.Image.open(...)
        if type(image) is str:
            self._image = Image.open(image)
        else:
            self._image = image

        # Store data for current frame
        self._currentFrame = None

        # Display multiple channels individually in grayscale (choose selected channel with scrollbar).
        self._separateChannels = False

        # QtImageViewer
        self.imageViewer = QtImageViewer(role=role, parent=self)
        self.imageViewer.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))

        # Scrollbars for frames/channels/etc.
        self._scrollbars = []

        # Mouse wheel behavior
        self._wheelScrollsFrame = True
        self._wheelZoomFactor = 1.25

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignLeft)
        font = self.label.font()
        font.setPointSize(12)
        self.label.setFont(font)
        self.label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))

        self.toolbar = QToolBar()
        self.toolbar.autoFillBackground()

        self.toolbar.setOrientation(Qt.Orientation.Horizontal)
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(10, 10))
        self.toolbar.setContentsMargins(0, 0, 0, 0)
        self.toolbar.setStyleSheet("QToolBar { spacing: 2px; }")
        self.toolbar.addWidget(self.label)


        bgColor = self.palette().color(QWidget.backgroundRole(self))
        isDarkMode = isDarkColor(bgColor)

        qpixmapi = getattr(QStyle.StandardPixmap, "SP_MediaPlay")
        qicon = self.style().standardIcon(qpixmapi)
        if isDarkMode:
            invertIconColors(qicon, 10, 10)
        self.playAction = self.toolbar.addAction(qicon, "", self.play)

        qpixmapi = getattr(QStyle.StandardPixmap, "SP_MediaPause")
        qicon = self.style().standardIcon(qpixmapi)
        if isDarkMode:
            invertIconColors(qicon, 10, 10)
        self.pauseAction = self.toolbar.addAction(qicon, "", self.pause)

        vbox = QVBoxLayout(self)
        vbox.addWidget(self.toolbar)
        vbox.addWidget(self.imageViewer)
        self.toolbar.addSeparator()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(4)
        shadow.setOffset(2)
        self.toolbar.setGraphicsEffect(shadow)
        # vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setContentsMargins(0,0,0,0)
        # vbox.setSpacing(2)

        # Track mouse position on image.
        self.imageViewer.setMouseTracking(True)
        self.imageViewer.mousePositionOnImageChanged.connect(self.updateLabel)

        # For play/pause actions.
        self._isPlaying = False

        self.updateViewer()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # self.setContentsMargins(0, 0, 0, 0)

        if self.role == 'aligned':
            pixmap = QPixmap("src/resources/button_ng.png").scaled(120, 120, Qt.KeepAspectRatio,
                                                                   Qt.SmoothTransformation)
            self.ng_callback_button = ClickablePicButton(pixmap)
            self.ng_callback_button.clicked.connect(self.ng_callback)
            self.toolbar.addWidget(self.ng_callback_button)
            # self.ng_layout = QVBoxLayout()
            # self.ng_layout.addWidget(self.ng_callback_button, alignment=Qt.AlignRight | Qt.AlignBottom)
            # self.setLayout(self.ng_layout)
            # self.ng_callback_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.ng_callback_button.setCursor(QCursor(Qt.PointingHandCursor))
            self.ng_callback_button.hide()

    def image(self):
        return self._image

    def setImage(self, im):
        logger.info('Image Type is %s' % type(im))
        self._image = im
        self.updateViewer()

    def currentFrame(self):
        return self._currentFrame

    def open(self, filepath=None):
        if filepath is None:
            filepath, dummy = QFileDialog.getOpenFileName(self, "Select image file.")
        if len(filepath) and os.path.isfile(filepath):
            self.setImage(Image.open(filepath))

    def loadData(self):
        logger.warning('loadData:')
        if type(self._image) is np.ndarray:
            return self._image
        elif type(self._image) is dask.array.core.Array:
            return self._image
        else:
            # PIL Image file object = PIL.Image.open(...)
            channels = self._image.getbands()
            n_channels = len(channels)

            # n_frames = self._image.n_frames #orig
            n_frames = len(self._image[0, 0, :])
            logger.info('n_channels: %d' % n_channels)
            logger.info('n_frames: %s' % str(n_frames))
            if n_frames == 1:
                return np.array(self._image)
            if n_frames > 1:
                self._image.seek(0)
                firstFrame = np.array(self._image)
                if n_channels == 1:
                    data = np.zeros((self._image.height, self._image.width, n_frames),
                                    dtype=firstFrame.dtype)
                else:
                    data = np.zeros((self._image.height, self._image.width, n_channels, n_frames),
                                    dtype=firstFrame.dtype)
                data[:,:,:n_channels] = firstFrame
                for i in range(1, n_frames):
                    self._image.seek(i)
                    if n_channels == 1:
                        data[:,:,i] = np.array(self._image)
                    else:
                        data[:,:,i*n_channels:(i+1)*n_channels] = np.array(self._image)
                return data

    def separateChannels(self):
        return self._separateChannels

    def setSeparateChannels(self, tf):
        self._separateChannels = tf
        self.updateViewer()

    def currentIndexes(self):
        return [self._scrollbars[0].value()]
        # return [scrollbar.value() for scrollbar in self._scrollbars]
        #     type(self.currentIndexes()) = <class 'list'>
        #     str(self.currentIndexes() = [0]

    def currentIndex(self):
        return self._scrollbars[0].value()


    def setCurrentIndexes(self, indexes):
        self._scrollbars[0].setValue(indexes)
        # for i, index in enumerate(indexes):
        #     self._scrollbars[i].setValue(index)
        self.updateFrame()

    def setCurrentIndex(self, index):
        # logger.info('setCurrentIndex:')
        self._scrollbars[0].setValue(index)
        # for i, index in enumerate(indexes):
        #     self._scrollbars[i].setValue(index)
        self.updateFrame()

    def setCurrentIndexes_(self):
        self._scrollbars[0].setValue(0)
        self.updateFrame()

    def wheelScrollsFrame(self):
        return self._wheelScrollsFrame

    def setWheelScrollsFrame(self, tf):
        self._wheelScrollsFrame = tf
        if tf:
            self.imageViewer.wheelZoomFactor = 1
        else:
            self.imageViewer.wheelZoomFactor = self._wheelZoomFactor

    def wheelZoomFactor(self):
        return self._wheelZoomFactor

    def setWheelZoomFactor(self, zoomFactor):
        self._wheelZoomFactor = zoomFactor
        if not self._wheelScrollsFrame:
            self.imageViewer.wheelZoomFactor = zoomFactor

    def updateViewer(self):
        logger.info('updateViewer:')
        logger.info("Image Slice Has Type %s" % type(self._image))
        if self._image is None:
            self.imageViewer.clearImage()
            del self._scrollbars[:]
            return

        # if (type(self._image) is np.ndarray) or (type(self._image) is dask.array.core.Array):
        if (type(self._image) is np.ndarray) or (type(self._image) is ts.TensorStore):

            # type(self._image) = <class 'numpy.ndarray'>
            # self._image.shape = (1694, 1694, 80)
            # img = Image.fromarray(self._image[:,:,0])
            # img.show() #<-- this works, shows the first image

            # Treat numpy.ndarray as grayscale intensity image.
            # Add scrollbars for every dimension after the first two.
            n_scrollbars = max(0, self._image.ndim - 2)
            if len(self._scrollbars) > n_scrollbars:
                for sb in self._scrollbars[n_scrollbars:]:
                    sb.deleteLater()
                del self._scrollbars[n_scrollbars:]
            while len(self._scrollbars) < n_scrollbars:
                scrollbar = QScrollBar(Qt.Horizontal)
                scrollbar.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
                scrollbar.valueChanged.connect(self.updateFrame)
                self.layout().addWidget(scrollbar)
                self._scrollbars.append(scrollbar)
            # n_scrollbars = 1
            # for i in range(n_scrollbars):
            #     logger.info('(i=%d) Setting range of scrollbar to 0 -> %s' % (i, str(self._image.shape[i+2])))
            #     # (i=0) Setting range of scrollbar to 0 -> 80
            #     self._scrollbars[i].setRange(0, self._image.shape[i+2])
            #     self._scrollbars[i].setValue(0)

            n_frames = self._image.shape[0]
            logger.info('Configuring Scrollbar Range: 0 -> %d' % n_frames)
            self._scrollbars[0].setRange(0, n_frames)
            self._scrollbars[0].setValue(0)
        else:
            logger.info("Type of self._image is NOT 'np.ndarray' or 'dask.array.core.Array'...")
            # PIL Image file object = PIL.Image.open(...)
            # channels = self._image.getbands()
            # n_channels = len(channels)
            n_channels = 1
            # n_frames = self._image.n_frames #orig
            n_frames = len(self._image[0, 0, :]) #orig
            logger.warning('self._image.shape = %s' % str(self._image.shape))
            n_scrollbars = 0
            if n_channels > 1 and self._separateChannels:
                n_scrollbars += 1
            if n_frames > 1:
                n_scrollbars += 1
            if len(self._scrollbars) > n_scrollbars:
                for sb in self._scrollbars[n_scrollbars:]:
                    sb.deleteLater()
                del self._scrollbars[n_scrollbars:]
            while len(self._scrollbars) < n_scrollbars:
                scrollbar = QScrollBar(Qt.Orientation.Horizontal)
                scrollbar.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
                scrollbar.valueChanged.connect(self.updateFrame)
                self.layout().addWidget(scrollbar) #orig
                self._scrollbars.append(scrollbar)
            i = 0
            if n_channels > 1 and self._separateChannels:
                self._scrollbars[i].setRange(0, n_channels - 1)
                self._scrollbars[i].setValue(0)
                i += 1
            if n_frames > 1:
                self._scrollbars[i].setRange(0, n_frames)
                self._scrollbars[i].setValue(0)

        # mouse wheel scroll frames vs. zoom
        if len(self._scrollbars) > 0 and self._wheelScrollsFrame:
            self.imageViewer.wheelZoomFactor = None # wheel scrolls frame
        else:
            self.imageViewer.wheelZoomFactor = self._wheelZoomFactor # wheel zoom

        logger.info('str(self.currentIndexes() = %s' % str(self.currentIndexes()))
        self.updateFrame()

    def updateFrame(self):
        if self._image is None:
            return

        if type(self._image) is np.ndarray:
            # rows = np.arange(self._image.shape[0])
            # cols = np.arange(self._image.shape[1])
            '''
            rows Out[17]: array([   0,    1,    2, ..., 1691, 1692, 1693])
            cols Out[18]: array([   0,    1,    2, ..., 1691, 1692, 1693])'''
            # indexes = [rows, cols].extend([[i] for i in self.currentIndexes()]) #orig
            # indexes = [rows, cols].extend([np.array(self.currentIndexes())])
            # print(str(indexes))

            # indexes = [rows, cols, 0]
            # indexes = [rows, cols].extend(np.array([[i] for i in self.currentIndexes()])) #jy
            # ^^ indexes keeps getting set to NoneType
            # print('indexes: %s' % str(indexes))
            # print(*indexes)
            # self._currentFrame = self._image[np.ix_(*indexes)]
            # self._currentFrame = self._image[:, :, self.currentIndexes()] #orig
            # self.imageViewer.setImage(self._currentFrame.copy())                 #REMOVE COPY #0913
            # self.imageViewer.setImage(self._image[:, :, self.currentIndexes()])                 #REMOVE COPY #0913
        elif type(self._image) is ts.TensorStore:
            # self.imageViewer.setImage(np.asarray(self._image[self.currentIndex(), :, :])) # Uses No I/O

            x_al = self._image[self.currentIndex(), :, :]
            future_al = x_al.read()
            self.imageViewer.setImage(future_al.result())
            # self.imageViewer.setImage(np.asarray(self._image[cfg.data.l(), :, :])) # Uses No I/O

            # read_future = x.read() <-- This Returns a tensorstore.Future to read a slice asynchronously, if desired
        elif type(self._image) is dask.array.core.Array:
            # logger.critical('self._image is type dask.array.core.Array')
            # self._currentFrame = self._image[:, :, self.currentIndex()]
            # self._currentFrame = self._image[:, :, self.currentIndex()-1]
            # Out[10]: dask.array<getitem,
            # shape=(80, 6884, 1),
            # dtype=uint8,
            # chunksize=(1, 512, 1),
            # chunktype=numpy.ndarray>
            # self.imageViewer.setImage(self._currentFrame.copy()) # Is this copy really necessary?
            # self.imageViewer.setImage(self._image[:, :, self.currentIndex()-1])
            self.imageViewer.setImage(self._image[:, :, self.currentIndex()])

        else:
            # PIL Image file object = PIL.Image.open(...)
            # channels = self._image.getbands()
            # n_channels = len(channels)
            n_channels = 1
            # n_frames = self._image.n_frames #orig
            n_frames = len(self._image[0, 0, :])
            indexes = self.currentIndexes()
            if n_frames > 1:
                frameIndex = indexes[-1]
                self._image.seek(frameIndex)
            if n_channels > 1 and self._separateChannels:
                channelIndex = indexes[0]
                self._currentFrame = np.array(self._image)[:,:,channelIndex]
                self.imageViewer.setImage(self._currentFrame.copy())
            else:
                try:
                    self._currentFrame = QImage(self._image.toqimage())
                    self.imageViewer.setImage(self._currentFrame)
                except ValueError:
                    self._currentFrame = np.array(self._image)
                    self.imageViewer.setImage(self._currentFrame.copy())

        self.updateLabel()

    def updateLabel(self, imagePixelPosition=None):
        if self._image is None:
            return

        label = ""

        for sb in self._scrollbars:
            label += str(sb.value() + 1) + "/" + str(sb.maximum() + 1) + "; "
        if type(self._image) is np.ndarray:
            width = self._image.shape[1]
            height = self._image.shape[0]
        elif type(self._image) is ts.TensorStore:
            # logger.critical('self._image.shape = %s' % str(self._image.shape))
            width = self._image.shape[2]
            height = self._image.shape[1]
        elif type(self._image) is dask.array.core.Array:
            # logger.critical('self._image.shape = %s' % str(self._image.shape))
            width = self._image.shape[2]
            height = self._image.shape[1]
        else:
            # PIL Image file object = PIL.Image.open(...)
            width = self._image.width
            height = self._image.height
        label += str(width) + "x" + str(height)
        if imagePixelPosition is not None:
            x = imagePixelPosition.x()
            y = imagePixelPosition.y()
            if 0 <= x < width and 0 <= y < height:
                label += "; x=" + str(x) + ", y=" + str(y)
                if self._currentFrame is not None:
                    if type(self._currentFrame) is np.ndarray:
                        value = self._currentFrame[y, x]
                    elif type(self._currentFrame) is dask.array.core.Array:
                        value = self._currentFrame[y, x]
                    else:
                        # PIL Image file object = PIL.Image.open(...)
                        value = self._image.getpixel((x, y))
                    label += ", value=" + str(value)
        if type(self._image) is not np.ndarray:
            # PIL Image file object = PIL.Image.open(...)
            try:
                path, filename = os.path.split(self._image.filename)
                if len(filename) > 0:
                    label += "; " + filename
            except:
                pass
        self.label.setText(label)

    def wheelEvent(self, event):
        if len(self._scrollbars) == 0:
            return
        n_frames = self._scrollbars[-1].maximum() + 1
        if self._wheelScrollsFrame and n_frames > 1:
            i = self._scrollbars[-1].value()
            if event.angleDelta().y() < 0:
                # next frame
                if i < n_frames - 1:
                    self._scrollbars[-1].setValue(i + 1)
                    self.updateFrame()
            else:
                # prev frame
                if i > 0:
                    self._scrollbars[-1].setValue(i - 1)
                    self.updateFrame()
            return

        QWidget.wheelEvent(self, event)

    def leaveEvent(self, event):
        self.updateLabel()

    def play(self):
        if len(self._scrollbars) == 0:
            return
        self._isPlaying = True
        first = self._scrollbars[-1].value()
        last = self._scrollbars[-1].maximum()
        for i in range(first, last + 1):
            self._scrollbars[-1].setValue(i)
            self.updateFrame()
            QApplication.processEvents()
            if not self._isPlaying:
                break
        self._isPlaying = False

    def pause(self):
        self._isPlaying = False


    def ng_callback(self):
        cfg.main_window.init_neuroglancer_client()

    def show_ng_button(self):
        self.ng_callback_button.show()

    def hide_ng_button(self):
        self.ng_callback_button.hide()

    def set_tooltips(self):
        try:
            if are_images_imported():
                s = cfg.data['data']['current_scale']
                l = cfg.data['data']['current_layer']
                l_name = cfg.data['data']['scales'][s]['alignment_stack'][l]['images'][self.role]['filename']
                l_basename = os.path.basename(l_name)
                # n_images = get_num_imported_images()
                role_dict = {'ref': 'Reference Image', 'base': 'Current Image', 'aligned': 'SWiFT-IR Image'}
                role_str = role_dict[self.role]
                try:
                    dim_str = '%sx%spx' % (self.pixmap().width(), self.pixmap().height())
                except:
                    dim_str = ''
                scale_str = 'Scale %d' % get_scale_val(s)
                snr_str = str(cfg.data.snr())
                if self.role == 'aligned':
                    if are_aligned_images_generated():
                        self.setToolTip('%s\n%s\n%s [%s]\n%s' % (role_str, l_basename, scale_str, dim_str, snr_str))
                else:
                    self.setToolTip('%s\n%s\n%s [%s]' % (role_str, l_basename, scale_str, dim_str))
            else:
                self.setToolTip('No Image')
        except:
            pass


if __name__ == '__main__':
    import sys
    # try:
    #     from PyQt6.QtWidgets import QApplication
    # except ImportError:
    #     from PyQt5.QtWidgets import QApplication
    from qtpy import QApplication

    def handleLeftClick(x, y):
        row = int(y)
        column = int(x)
        print("Clicked on image pixel (row="+str(row)+", column="+str(column)+")")

    def handleViewChange():
        print("viewChanged")

    # Create the application.
    app = QApplication(sys.argv)

    # Create image viewer.
    viewer = QtImageViewer()

    # Open an image from file.
    viewer.open()

    # Handle left mouse clicks with custom slot.
    viewer.leftMouseButtonReleased.connect(handleLeftClick)

    # Show viewer and run application.
    viewer.show()
    sys.exit(app.exec())