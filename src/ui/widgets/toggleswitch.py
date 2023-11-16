#!/usr/bin/env python3
'''Toggle Switch UI Widget Class'''

import sys
import logging
from qtpy.QtWidgets import QCheckBox, QApplication, QMainWindow
from qtpy.QtCore import Qt, Slot, QSize, QPointF, QPoint, QRectF
from qtpy.QtGui import QBrush, QColor, QFont, QPen, QPaintEvent, QPainter

__all__ = ['ToggleSwitch']

logger = logging.getLogger(__name__)

class ToggleSwitch(QCheckBox):
    _transparent_pen = QPen(QColor('transparent'))
    _light_grey_pen = QPen(QColor('lightgrey'))
    _black_pen = QPen(QColor('black'))
    _almost_black_color = QColor('#070D0D')
    _almost_black_pen = QPen(_almost_black_color)
    _grey_pen = QPen(QColor('grey'))
    _snow_color = QColor('#F3F6FB')
    _snow_pen = QPen(_snow_color)
    _green_pen = QPen(QColor('#00ff00'))
    _green_color = '#588A0E' #darker green
    _black_charcoal_color = QColor('#212121')
    _black_color = QColor('#000000')
    _border_color_pen = QPen(QColor('#171d22;'))
    _red_color = QColor('#D61529') # deeper red
    _red_pen = QPen(_red_color) # deeper red
    def __init__(self,
                 parent=None,
                 bar_color=QColor(_red_color),
                 checked_color=_green_color,
                 handle_color=_snow_color, # handle; off
                 # h_scale=.7,
                 # v_scale=1,
                 h_scale=.75,
                 v_scale=1.35,
                 fontSize=11):

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # focus don't steal focus from zoompanwidget
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())
        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor("white")) # handle, off
        # self.setContentsMargins(0, 0, 4, 0)
        # self.setContentsMargins(0, 0, 0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize
        self.stateChanged.connect(self.handle_state_change)
        # self._fixed_width = 52 #horizontal
        # self._fixed_height = 26 #vertical
        self._fixed_width = 42 #horizontal
        self._fixed_height = 20 #vertical
        self.setFixedWidth(self._fixed_width)
        self.setFixedHeight(self._fixed_height)

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        return QSize(self._fixed_height, self._fixed_width)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect() #0610 #TypeError: moveCenter(self, QPointF): argument 1 has unexpected cur_method 'QPoint'
        # contRect = QPointF(self.contentsRect()) #0613
        self.width = contRect.width() * self._h_scale
        self.height = contRect.height() * self._v_scale
        # self.handle_radius = round(0.16 * self.height)
        self.handle_radius = round(0.13 * self.height)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing) #0610 #0628 re-uncommenting
        p.setPen(self._snow_pen) # Border around background area
        barRect = QRectF(0, 0, self.width - self.handle_radius, 0.42 * self.height)
        barRect.moveCenter(QPointF(contRect.center())) #pyqt6 fix
        rounding = barRect.height() / 2
        # the handle will move along this line !
        adjust_trail = -4
        self.trailLength = contRect.width() * self._h_scale - 2 * self.handle_radius + adjust_trail
        self.xLeft = int(contRect.center().x() - (self.trailLength + self.handle_radius) / 2)
        self.xPos = self.xLeft + self.handle_radius + self.trailLength * self._handle_position

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            '''TEXT, ON'''
            p.setPen(self._snow_pen)
            p.setBrush(self._handle_checked_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            p.setFont(QFont('Helvetica', self._fontSize, 95))
            # position for the check # lower number is more left
            adjust_x = -1
            adjust_y = 4 # higher adjust is lower text
            p.drawText(int(self.xLeft + self.handle_radius / 2 + adjust_x), int(contRect.center().y() + adjust_y), "✓")

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._snow_pen)
            p.setBrush(self._handle_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            p.setFont(QFont('Helvetica', self._fontSize, 95))
            # position for the 'x'
            adjust_x = 0
            adjust_y = 3
            p.drawText(int(contRect.center().x() + adjust_x), int(contRect.center().y() + adjust_y), " ×")

        p.setPen(self._transparent_pen)
        p.drawEllipse(QPointF(self.xPos, barRect.center().y()), self.handle_radius, self.handle_radius)
        p.end()

    @Slot(int)
    def handle_state_change(self, value):
        '''Position of Handle; orig= 1 or 0'''
        self._handle_position = .8 if value else 0

    def setH_scale(self, value):
        self._h_scale = value
        self.update()

    def setV_scale(self, value):
        self._v_scale = value
        self.update()

    def setFontSize(self, value):
        self._fontSize = value
        self.update()




'''
Source   : https://www.pythonguis.com/tutorials/qpropertyanimation/
Accessed : 2023-03-11

Because we're inheriting from QCheckBox it is essential that we override hitButton(). This defines the clickable area of our widget, and by a QCheckBox is only clickable in the area of the checkable box. Here we expand the clickable region to the entire widget, using self.contentsRect() so a click anywhere on the widget will toggle the state.
Similarly it'level essential we override sizeHint() so when we add our widget to layouts, they know an acceptable default size to use.
You must set p.setRenderHint(QPainter.Antialiasing) to smooth the edges of things you draw, otherwise the outline will be jagged.
In this example we trigger the animation using the self.stateChanged signal, which is provided by QCheckBox. This fires whenever the state (checked or unchecked) of the widget changes. It is important to choose the right trigger to start the animation in order for the widget to feel intuitive.
Since we're using stateChanged to start the animation, if you check the state of the toggle as soon as it'level been clicked it will give the correct value -- even if the animation is not yet complete.
'''

import logging
from qtpy.QtCore import (Qt, QSize, QPoint, QPointF, QRectF,
    QEasingCurve, QPropertyAnimation, QSequentialAnimationGroup,
    Slot, Property)
from qtpy.QtWidgets import QCheckBox
from qtpy.QtGui import QColor, QBrush, QPaintEvent, QPen, QPainter

__all__ = ['AnimatedToggle']

logger = logging.getLogger(__name__)

class AnimatedToggle(QCheckBox):

    _transparent_pen = QPen(Qt.transparent)
    _light_grey_pen = QPen(Qt.lightGray)

    def __init__(self,
        parent=None,
        bar_color=Qt.gray,
        checked_color="#00B0FF",
        handle_color=Qt.white,
        pulse_unchecked_color="#44999999",
        pulse_checked_color="#4400B0EE"
        ):
        super().__init__(parent)

        # Save our properties on the object via self, so we can access them later
        # in the paintEvent.
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())

        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor(checked_color))

        self._pulse_unchecked_animation = QBrush(QColor(pulse_unchecked_color))
        self._pulse_checked_animation = QBrush(QColor(pulse_checked_color))

        # Setup the rest of the widget.
        self.setContentsMargins(8, 0, 8, 0)
        self._handle_position = 0

        self._pulse_radius = 0

        self.animation = QPropertyAnimation(self, b"handle_position", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(200)  # time in ms

        self.pulse_anim = QPropertyAnimation(self, b"pulse_radius", self)
        # self.pulse_anim.setDuration(350)  # time in ms
        self.pulse_anim.setDuration(200)  # time in ms
        self.pulse_anim.setStartValue(8)
        # self.pulse_anim.setEndValue(20)
        self.pulse_anim.setEndValue(10)

        self.animations_group = QSequentialAnimationGroup()
        self.animations_group.addAnimation(self.animation)
        self.animations_group.addAnimation(self.pulse_anim)

        self.stateChanged.connect(self.setup_animation)


    def sizeHint(self):
        return QSize(58, 45)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    @Slot(int)
    def setup_animation(self, value):
        self.animations_group.stop()
        if value:
            self.animation.setEndValue(1)
        else:
            self.animation.setEndValue(0)
        self.animations_group.start()

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect()
        handleRadius = round(0.24 * contRect.height())

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(self._transparent_pen)
        barRect = QRectF(
            0, 0,
            contRect.width() - handleRadius, 0.40 * contRect.height()
        )
        barRect.moveCenter(contRect.center())
        rounding = barRect.height() / 2

        # the handle will move along this line
        trailLength = contRect.width() - 2 * handleRadius

        xPos = contRect.x() + handleRadius + trailLength * self._handle_position

        if self.pulse_anim.state() == QPropertyAnimation.Running:
            p.setBrush(
                self._pulse_checked_animation if
                self.isChecked() else self._pulse_unchecked_animation)
            p.drawEllipse(QPointF(xPos, barRect.center().y()),
                          self._pulse_radius, self._pulse_radius)

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setBrush(self._handle_checked_brush)

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._light_grey_pen)
            p.setBrush(self._handle_brush)

        p.drawEllipse(
            QPointF(xPos, barRect.center().y()),
            handleRadius, handleRadius)

        p.end()

    @Property(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
        """change the property
        we need to trigger QWidget.update() method, either by:
            1- calling it here [ what we doing ].
            2- connecting the QPropertyAnimation.valueChanged() signal to it.
        """
        self._handle_position = pos
        self.update()

    @Property(float)
    def pulse_radius(self):
        return self._pulse_radius

    @pulse_radius.setter
    def pulse_radius(self, pos):
        self._pulse_radius = pos
        self.update()




if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    ts = ToggleSwitch()
    main_window.setCentralWidget(ts)
    main_window.show()
    sys.exit(app.exec_())
