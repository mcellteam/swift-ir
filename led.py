
from qtpy.QtWidgets import *
from qtpy.QtCore import *

class LEDs(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        self.animation = QVariantAnimation()
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setDuration(1500)
        self.animation.valueChanged.connect(self.updateOpacity)
        self.animation.finished.connect(self.checkAnimation)

        self.buttons = []
        for i in range(3):
            button = QPushButton()
            self.buttons.append(button)
            layout.addWidget(button)
            effect = QGraphicsOpacityEffect(opacity=1.0)
            button.setGraphicsEffect(effect)
            button.clicked.connect(self.startAnimation)

    # ... as above ...

    def updateOpacity(self, opacity):
        for button in self.buttons:
            button.graphicsEffect().setOpacity(opacity)
