#!/usr/bin/env python3

from qtpy.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QScrollArea, QToolButton
from qtpy.QtCore import Qt, QAbstractAnimation, QPropertyAnimation, QParallelAnimationGroup
from qtpy.QtCore import Slot


class CollapsibleBox(QWidget):
    '''Forms a part of the data inspector class. Adapted from:
    https://github.com/fzls/djc_helper/blob/master/qt_collapsible_box.py'''

    def __init__(self, title="", title_backgroup_color="", tool_tip="Project Inspector :)",
                 animation_duration_millseconds=250, parent=None):
        super(CollapsibleBox, self).__init__(parent)

        self.title = title
        self.setToolTip(tool_tip)
        self.animation_duration_millseconds = animation_duration_millseconds
        self.collapsed_height = 19

        # sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) #0610
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)

        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(title)
        self.toggle_button.setSizePolicy(sizePolicy)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet(
            f"QToolButton {{ border: none; font-weight: bold; background-color: #7c7c7c; }}")
        self.toggle_button.pressed.connect(self.on_pressed)

        self.toggle_animation = QParallelAnimationGroup(self)

        self.content_area = QScrollArea(self)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        # self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # self.content_area.setFrameShape(QFrame.NoFrame) #0610 AttributeError: type object 'QFrame' has no attribute 'NoFrame'

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(QPropertyAnimation(self, b"minimumHeight"))
        self.toggle_animation.addAnimation(QPropertyAnimation(self, b"maximumHeight"))
        self.toggle_animation.addAnimation(QPropertyAnimation(self.content_area, b"maximumHeight"))

    @Slot()
    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.DownArrow if not checked else Qt.RightArrow)
        self.toggle_animation.setDirection(
            QAbstractAnimation.Forward
            if not checked
            else QAbstractAnimation.Backward
        )
        self.toggle_animation.start()

    def setContentLayout(self, layout):
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = (self.sizeHint().height() - self.content_area.maximumHeight())
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            # animation.setDuration(500)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
        # content_animation.setDuration(500)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)