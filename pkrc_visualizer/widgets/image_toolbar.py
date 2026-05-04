"""Top toolbar for the Image page: Add Viewer + Layout selector."""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget


LAYOUT_OPTIONS = ["1x1", "2x1", "2x2", "3x2", "free"]


class ImageToolbar(QWidget):
    add_viewer_clicked = pyqtSignal()
    layout_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._add_btn = QPushButton("+ Add Viewer")
        self._add_btn.clicked.connect(self.add_viewer_clicked.emit)

        self._layout_combo = QComboBox()
        self._layout_combo.addItems(LAYOUT_OPTIONS)
        self._layout_combo.setCurrentText("2x2")
        self._layout_combo.currentTextChanged.connect(self.layout_changed.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._add_btn)
        layout.addStretch(1)
        layout.addWidget(QLabel("Layout:"))
        layout.addWidget(self._layout_combo)

    def set_layout_value(self, value: str) -> None:
        if value in LAYOUT_OPTIONS:
            self._layout_combo.setCurrentText(value)
