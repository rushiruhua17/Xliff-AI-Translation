from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QScrollArea, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                font-weight: bold;
                color: #60CDFF; /* Accent color */
                padding: 5px;
            }
            QToolButton:hover {
                background-color: #2D2F31;
                border-radius: 4px;
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.clicked.connect(self.on_pressed)

        self.content_area = QScrollArea()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setFrameShape(QFrame.Shape.NoFrame)
        self.content_area.setStyleSheet("background-color: transparent;")

        # Animation
        self.anim = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        
        # Calculate height
        content_height = self.content_area.widget().sizeHint().height() if self.content_area.widget() else 0
        
        self.anim.setStartValue(0 if checked else content_height)
        self.anim.setEndValue(content_height if checked else 0)
        self.anim.start()

    def set_content_layout(self, layout):
        w = QWidget()
        w.setLayout(layout)
        self.content_area.setWidget(w)
        self.content_area.setWidgetResizable(True)
