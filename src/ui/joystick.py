'''

Adapted from:
https://stackoverflow.com/questions/55876713/how-to-create-a-joystick-controller-widget-in-pyqt

'''

import sys
import math
from enum import Enum
from qtpy.QtWidgets import *
from qtpy.QtGui import *
from qtpy.QtCore import *

import src.config as cfg

class Direction(Enum):
    Left = 0
    Right = 1
    Up = 2
    Down = 3

class Joystick(QWidget):
    def __init__(self, parent=None):
        super(Joystick, self).__init__(parent)
        # self.setMinimumSize(100, 100)
        self.setFixedSize(32, 32)
        self.setMinimumSize(32, 32)
        self.movingOffset = QPointF(0, 0)
        self.grabCenter = False
        self.__maxDistance = 30 #Original, movement of actual joystick painted object
        # self.__maxDistance = 1
        # self.__maxDistance = 20

        self.timer = QTimer()
        # self.timer.timeout.connect(lambda: print('joystick is active!'))
        self.timer.timeout.connect(self.joystickDirection)

    def paintEvent(self, event):
        painter = QPainter(self)
        bounds = QRectF(-self.__maxDistance, -self.__maxDistance, self.__maxDistance * 2, self.__maxDistance * 2).translated(self._center())
        painter.drawEllipse(bounds)
        painter.setBrush(Qt.black)
        painter.drawEllipse(self._centerEllipse())

    def _centerEllipse(self):
        # if self.grabCenter:
        #     return QRectF(-20, -20, 40, 40).translated(self.movingOffset)
        # return QRectF(-20, -20, 40, 40).translated(self._center())
        if self.grabCenter:
            return QRectF(-5, -5, 10, 10).translated(self.movingOffset)
        return QRectF(-5, -5, 10, 10).translated(self._center())

    def _center(self):
        return QPointF(self.width()/2, self.height()/2)


    def _boundJoystick(self, point):
        limitLine = QLineF(self._center(), point)
        if (limitLine.length() > self.__maxDistance):
            limitLine.setLength(self.__maxDistance)
        return limitLine.p2()

    def joystickDirection(self):
        if not self.grabCenter:
            return 0
        normVector = QLineF(self._center(), self.movingOffset)
        currentDistance = normVector.length()
        angle = normVector.angle()

        distance = min(currentDistance / self.__maxDistance, 1.0)
        print(f'Distance: {distance}, Angle: {angle}')

        px_to_travel = 30
        x_travel = px_to_travel * math.cos(angle) * distance
        y_travel = px_to_travel * math.cos(90 - angle) * distance

        # distance_scaled_up = distance_up * distance
        # distance_scaled_right = distance_right * distance

        # distance_up = math.tan((angle*math.pi)/180)
        # distance_right = 1 / math.tan((angle*math.pi)/180)

        # if distance_up > 100:
        #     distance_up = 0
        #
        # if distance_right > 100:
        #     distance_right = 0

        # cfg.emViewer.moveDownBy(y_travel)
        # cfg.emViewer.moveRightBy(x_travel)
        print(f'Down by: {y_travel:.2f}, right by: {x_travel:.2f}')


        if 0 <= angle < 180:
            cfg.emViewer.moveUpBy(y_travel)
            cfg.emViewer.moveRightBy(x_travel)
            # cfg.emViewer.moveUpBy(distance_scaled_up)
            # cfg.emViewer.moveRightBy(distance_scaled_right)
            print(f'up by: {y_travel:.2f}, right by: {x_travel:.2f}')
            # print(f'distance scaled up: {distance_scaled_up:.2f}, distance scaled right: {distance_scaled_right:.2f}')
        else:
            cfg.emViewer.moveDownBy(y_travel)
            cfg.emViewer.moveRightBy(x_travel)
            # cfg.emViewer.moveDownBy(distance_scaled_up / 10)
            # cfg.emViewer.moveLeftBy(distance_scaled_right / 10)
            print(f'down by: {y_travel:.2f}, right by: {x_travel:.2f}')
            # print(f'distance scaled down: {distance_scaled_up:.2f}, distance scaled left: {distance_scaled_right:.2f}')

        # if 45 <= angle < 135:
        #     cfg.emViewer.moveUpBy(distance)
        #     return (Direction.Up, distance)
        # elif 135 <= angle < 225:
        #     cfg.emViewer.moveLeftBy(distance)
        #     return (Direction.Left, distance)
        # elif 225 <= angle < 315:
        #     cfg.emViewer.moveDownBy(distance)
        #     return (Direction.Down, distance)
        # else:
        #     cfg.emViewer.moveRightBy(distance)
        #     return (Direction.Right, distance)


    def mousePressEvent(self, ev):
        self.timer.start(100)
        self.grabCenter = self._centerEllipse().contains(ev.pos())
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, event):
        self.grabCenter = False
        self.movingOffset = QPointF(0, 0)
        self.update()
        print('\n\nMouse Released!\n')
        self.timer.stop()

    def mouseMoveEvent(self, event):
        if self.grabCenter:
            print("Moving")
            self.movingOffset = self._boundJoystick(event.pos())
            self.update()
        # print(self.joystickDirection())