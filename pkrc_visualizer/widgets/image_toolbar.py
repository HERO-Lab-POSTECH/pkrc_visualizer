"""Top toolbar for the ImagePage (v0.5.0): Add Viewer button only.

Layout presets were removed; users arrange panels by dragging dock headers
inside the page (rqt-style).
"""
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ImageToolbar(QWidget):
    add_viewer_clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._add_btn = QPushButton("+ Add Viewer")
        self._add_btn.clicked.connect(self.add_viewer_clicked.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._add_btn)
        layout.addStretch(1)
