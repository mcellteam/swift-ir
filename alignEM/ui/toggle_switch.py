#!/usr/bin/env python3
from qtpy.QtWidgets import QCheckBox
from qtpy.QtCore import Qt, Slot, QSize, QPointF, QPoint, QRectF
from qtpy.QtGui import QBrush, QColor, QFont, QPen, QPaintEvent, QPainter, QIcon
import qtawesome as qta

__all__ = ['ToggleSwitch']

class ToggleSwitch(QCheckBox):
    #0610 after switching to PyQt6... AttributeError: type object 'alignEM' has no attribute 'transparent'
    _transparent_pen = QPen(QColor('transparent'))
    _light_grey_pen = QPen(QColor('lightgrey'))
    _black_pen = QPen(QColor('black'))
    _almost_black_color = QColor('#070D0D')
    _almost_black_pen = QPen(_almost_black_color)
    _grey_pen = QPen(QColor('grey'))
    _snow_color = QColor('#F3F6FB')
    _snow_pen = QPen(_snow_color)
    _green_pen = QPen(QColor('#00ff00'))
    _green_color = '#00ff00'
    _black_charcoal_color = QColor('#212121')
    _black_color = QColor('#000000')

    _red_pen = QPen(QColor('red'))
    def __init__(self,
                 parent=None,
                 # bar_color=QColor('grey'),
                 # bar_color=QColor('white'),
                 # bar_color=QColor('lightgrey'), # circle around image
                 # bar_color=QColor('#ffffff'),
                 bar_color=QColor('red'),
                 # checked_color="#00B0FF",
                 # checked_color="#607cff",
                 # checked_color="# d3dae3",  # monjaromix stylesheet
                 # checked_color="#00ff00",
                 # checked_color=QColor('white'),
                 checked_color=_green_color,
                 # checked_color=_snow_color,
                 # checked_color='#ffffff', # toggle background; on

                 # handle_color=QColor('blue'),
                 # handle_color=QColor('black'), # handle; off
                 handle_color=_almost_black_color, # handle; off
                 # handle_color=QColor('#000000'), # handle; off
                 # handle_color=QColor('red'), # handle; off
                 h_scale=1,
                 # v_scale=.5, #0824-
                 v_scale=1,
                 fontSize=12):

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # focus don't steal focus from zoompanwidget
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())
        self._handle_brush = QBrush(handle_color)
        # self._handle_checked_brush = QBrush(QColor(checked_color))
        # self._handle_checked_brush = QBrush(QColor('#151a1e'))
        # self._handle_checked_brush = QBrush(QColor("#00ff00"))
        # self._handle_checked_brush = QBrush(QColor("#F3F6FB"))
        self._handle_checked_brush = QBrush(QColor("white")) # handle, off
        # self._handle_checked_brush = QBrush(QColor("red"))
        # self.light_brush = QBrush(QColor(0, 0, 0))]
        # this setContentMargins can cause issues with painted region, might need to stick to 8,0,8,0
        self.setContentsMargins(0, 0, 4, 0) #left,top,right,bottom
        # self.setContentsMargins(0, 0, 0, 0) #left,top,right,bottom
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize
        self.stateChanged.connect(self.handle_state_change)
        # self.setFixedWidth(36) #0824-
        # self.setFixedHeight(30) #0824-

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        # return QSize(76, 30)
        # return QSize(80, 35)
        return QSize(39, 30)

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
            # p.setPen(self._grey_pen)
            p.setPen(self._snow_pen)
            # p.setPen(self._almost_black_pen)
            # p.setPen(self._black_pen)
            # p.setBrush(self._handle_checked_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.drawText(xLeft + handleRadius / 2, contRect.center().y() + handleRadius / 2, "✓")
            # self.setIcon(qta.icon("mdi.help"))
            # self.documentation_button.setIcon(qta.icon("mdi.help"))

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            # p.setPen(self._grey_pen)
            # p.setPen(self._black_pen)
            # p.setPen(self._red_pen)
            # p.setPen(self._snow_pen)
            # p.setPen(self._red_pen)
            p.setPen(self._almost_black_pen)
            p.setBrush(self._handle_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.drawText(contRect.center().x(), contRect.center().y() + handleRadius / 2, " ×")


        # p.setPen(self._light_grey_pen)
        p.setPen(self._snow_pen)
        # p.setPen(self._transparent_pen)
        # p.setPen(self._black_pen) # CIRCLE AROUND HANDLE, ALL
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
