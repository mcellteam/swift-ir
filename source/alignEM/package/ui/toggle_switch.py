#!/usr/bin/env python3

from qtpy.QtCore import Slot, QSize, QPointF, QPoint, QRectF
from qtpy.QtWidgets import QCheckBox
from qtpy.QtGui import Qt, QBrush, QColor, QFont, QPen, QPaintEvent, QPainter

__all__ = ['ToggleSwitch']

class ToggleSwitch(QCheckBox):
    #0610 after switching to PyQt6... AttributeError: type object 'alignEM' has no attribute 'transparent'
    _transparent_pen = QPen(QColor('transparent'))
    _light_grey_pen = QPen(QColor('lightgrey'))
    _black_pen = QPen(QColor('black'))

    def __init__(self,
                 parent=None,
                 bar_color=QColor('grey'),
                 # checked_color="#00B0FF",
                 # checked_color="#607cff",
                 # checked_color="# d3dae3",  # monjaromix stylesheet
                 checked_color="#00ff00",

                 handle_color=QColor('white'),
                 h_scale=.7,
                 v_scale=.5,
                 fontSize=10):

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # focus don't steal focus from zoompanwidget

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())
        self._handle_brush = QBrush(handle_color)
        # self._handle_checked_brush = QBrush(QColor(checked_color))
        self._handle_checked_brush = QBrush(QColor('#151a1e'))
        # self.light_brush = QBrush(QColor(0, 0, 0))]
        # this setContentMargins can cause issues with painted region, might need to stick to 8,0,8,0
        self.setContentsMargins(0, 0, 2, 0) #left,top,right,bottom
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize

        self.stateChanged.connect(self.handle_state_change)

        self.setFixedWidth(36)
        self.setFixedHeight(30)

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        # return QSize(76, 30)
        # return QSize(80, 35)
        return QSize(36, 30)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect() #0610 #TypeError: moveCenter(self, QPointF): argument 1 has unexpected type 'QPoint'
        # contRect = QPointF(self.contentsRect()) #0613
        width = contRect.width() * self._h_scale
        height = contRect.height() * self._v_scale
        handleRadius = round(0.24 * height)


        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing) #0610 #0628 re-uncommenting

        p.setPen(self._transparent_pen)
        barRect = QRectF(0, 0, width - handleRadius, 0.40 * height)
        # barRect.moveCenter(contRect.center())
        barRect.moveCenter(QPointF(contRect.center())) #pyqt6 fix
        rounding = barRect.height() / 2

        # the handle will move along this line
        trailLength = contRect.width() * self._h_scale - 2 * handleRadius
        xLeft = int(contRect.center().x() - (trailLength + handleRadius) / 2)
        # xLeft = contRect.center().x() - (trailLength + handleRadius) / 2
        # DeprecationWarning: an integer is required (got type float).
        xPos = xLeft + handleRadius + trailLength * self._handle_position

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._black_pen)
            p.setBrush(self._handle_checked_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._black_pen)
            p.setBrush(self._handle_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))


        p.setPen(self._light_grey_pen)
        p.drawEllipse(QPointF(xPos, barRect.center().y()), handleRadius, handleRadius)
        p.end()

    @Slot(int)
    def handle_state_change(self, value):
        self._handle_position = 1 if value else 0

    # @Property(float)
    # def handle_position(self):
    #     return self._handle_position

    # @handle_position.setter
    # def handle_position(self, pos):
    #     """change the property
    #        we need to trigger QWidget.update() method, either by:
    #        1- calling it here [ what we're doing ].
    #        2- connecting the QPropertyAnimation.valueChanged() signal to it.
    #     """
    #     self._handle_position = pos
    #     self.update()

    def setH_scale(self, value):
        self._h_scale = value
        self.update()

    def setV_scale(self, value):
        self._v_scale = value
        self.update()

    def setFontSize(self, value):
        self._fontSize = value
        self.update()
