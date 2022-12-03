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
    #0610 after switching to PyQt6... AttributeError: type object 'src' has no attribute 'transparent'
    _transparent_pen = QPen(QColor('transparent'))
    _light_grey_pen = QPen(QColor('lightgrey'))
    _black_pen = QPen(QColor('black'))
    _almost_black_color = QColor('#070D0D')
    _almost_black_pen = QPen(_almost_black_color)
    _grey_pen = QPen(QColor('grey'))
    _snow_color = QColor('#F3F6FB')
    _snow_pen = QPen(_snow_color)
    _green_pen = QPen(QColor('#00ff00'))
    # _green_color = '#00ff00'
    _green_color = '#588A0E' #darker green
    _black_charcoal_color = QColor('#212121')
    _black_color = QColor('#000000')

    _border_color_pen = QPen(QColor('#171d22;'))

    # _red_pen = QPen(QColor('red'))
    _red_color = QColor('#D61529') # deeper red
    _red_pen = QPen(_red_color) # deeper red
    def __init__(self,
                 parent=None,
                 # bar_color=QColor('grey'),
                 # bar_color=QColor('white'),
                 # bar_color=QColor('lightgrey'), # circle around image
                 # bar_color=QColor('#ffffff'),
                 bar_color=QColor(_red_color),
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
                 # handle_color=_almost_black_color, # handle; off
                 handle_color=_snow_color, # handle; off
                 # handle_color=QColor('#000000'), # handle; off
                 # handle_color=QColor('red'), # handle; off
                 # h_scale=1,
                 h_scale=.7,
                 # v_scale=.5, #0824-
                 v_scale=1,
                 fontSize=13):

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # focus don't steal focus from zoompanwidget
        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())
        # self._bar_checked_brush = QBrush(self._snow_color)
        self._handle_brush = QBrush(handle_color)
        # self._handle_checked_brush = QBrush(QColor(checked_color))
        # self._handle_checked_brush = QBrush(QColor('#151a1e'))
        # self._handle_checked_brush = QBrush(QColor("#00ff00"))
        # self._handle_checked_brush = QBrush(QColor("#F3F6FB"))
        self._handle_checked_brush = QBrush(QColor("white")) # handle, off
        # self._handle_checked_brush = QBrush(QColor("red"))
        # self.light_brush = QBrush(QColor(0, 0, 0))]
        # this setContentMargins can cause issues with painted region, might need to stick to 8,0,8,0
        # self.setContentsMargins(0, 0, 4, 0) #left,top,right,bottom
        self.setContentsMargins(0, 0, 4, 0) #left,top,right,bottom
        self._handle_position = 0
        self._h_scale = h_scale
        self._v_scale = v_scale
        self._fontSize = fontSize
        self.stateChanged.connect(self.handle_state_change)
        self._fixed_height = 52 #horizontal
        self._fixed_width = 32 #vertical
        self.setFixedWidth(self._fixed_height) #0824-
        self.setFixedHeight(self._fixed_width) #0824-

    def __str__(self):
        return str(self.__class__) + '\n' + '\n'.join(
            ('{} = {}'.format(item, self.__dict__[item]) for item in self.__dict__))

    def sizeHint(self):
        return QSize(self._fixed_height, self._fixed_width)
        # return QSize(80, 35)
        # return QSize(39, 30)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect() #0610 #TypeError: moveCenter(self, QPointF): argument 1 has unexpected type 'QPoint'
        # contRect = QPointF(self.contentsRect()) #0613
        self.width = contRect.width() * self._h_scale
        self.height = contRect.height() * self._v_scale
        self.handle_radius = round(0.16 * self.height)
        # self.handle_radius = round(0.18 * self.height)


        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing) #0610 #0628 re-uncommenting

        '''Layout of Main Background Area'''
        # p.setPen(self._transparent_pen) # Border around background area
        p.setPen(self._snow_pen) # Border around background area
        # p.setPen(self._border_color_pen) # Border around background area
        # p.setPen(self._almost_black_pen) # Border around background area
        # p.setPen(self._black_pen)
        # barRect = QRectF(0, 0, self.width - self.handle_radius, 0.40 * self.height)
        barRect = QRectF(0, 0, self.width - self.handle_radius, 0.42 * self.height)
        # barRect.moveCenter(contRect.center())
        barRect.moveCenter(QPointF(contRect.center())) #pyqt6 fix
        rounding = barRect.height() / 2

        # the handle will move along this line
        adjust_trail = -6
        self.trailLength = contRect.width() * self._h_scale - 2 * self.handle_radius + adjust_trail
        self.xLeft = int(contRect.center().x() - (self.trailLength + self.handle_radius) / 2)
        # xLeft = contRect.center().x() - (self.trailLength + self.handle_radius) / 2
        # DeprecationWarning: an integer is required (got type float).
        self.xPos = self.xLeft + self.handle_radius + self.trailLength * self._handle_position
        # logger.critical('self.trailLength=%s' % str(self.trailLength))
        # logger.critical('xLeft=%s' % str(xLeft))
        # logger.critical('xPos=%s' % str(xPos))

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            '''TEXT, ON'''
            # p.setPen(self._grey_pen)
            p.setPen(self._snow_pen)
            # p.setPen(self._green_pen)
            # p.setPen(self._almost_black_pen)
            # p.setPen(self._black_pen)
            p.setBrush(self._handle_checked_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.setFont(QFont('Helvetica', self._fontSize, 95))
            # p.drawText(xLeft + self.handle_radius / 2, contRect.center().y() + self.handle_radius / 2, "✓") #orig
            # p.drawText(xLeft + self.handle_radius / 2, contRect.center().y() + self.handle_radius / 2, "✓")
            adjust_x = -1
            adjust_y = 4 # higher adjust is lower text
            p.drawText(int(self.xLeft + self.handle_radius / 2 + adjust_x), int(contRect.center().y() + adjust_y), "✓") # higher
            # p.drawText(contRect.center().x(), contRect.center().y() + self.handle_radius / 2, " ×")
            # p.drawText(xLeft + self.handle_radius / 3, contRect.center().y() + self.handle_radius / 3, "✓")
            # self.setIcon(qta.icon("mdi.help"))
            # self.documentation_button.setIcon(qta.icon("mdi.help"))
            # logger.critical('contRect.center().y() = %s' % str(contRect.center().y()))
            # logger.critical('self.handle_radius = %s' % str(self.handle_radius))


        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            # p.setPen(self._grey_pen)
            # p.setPen(self._black_pen)
            # p.setPen(self._red_pen)
            p.setPen(self._snow_pen)
            p.setBrush(self._handle_brush)
            font = QFont("PT Sans", self._fontSize)
            p.setFont(font)
            # p.setFont(QFont('Helvetica', self._fontSize, 75))
            p.setFont(QFont('Helvetica', self._fontSize, 95))
            #contRect.center().y() = 14
            # self.handle_radius = 7
            adjust_y = 4
            adjust_x = -2
            p.drawText(int(contRect.center().x() + adjust_x), int(contRect.center().y() + adjust_y), " ×") #orig

            # p.drawText(contRect.center().x(), contRect.center().y() + self.handle_radius / 3, " ×")
            # p.drawText(xLeft + self.handle_radius / 3, contRect.center().y() + self.handle_radius / 3, "✓")

        # Circle around handle, ON & OFF; looks good transparent
        # p.setPen(self._light_grey_pen)
        # p.setPen(self._snow_pen)
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

if __name__ == '__main__':
    app = QApplication([])
    main_window = QMainWindow()
    ts = ToggleSwitch()
    main_window.setCentralWidget(ts)
    main_window.show()
    sys.exit(app.exec_())
