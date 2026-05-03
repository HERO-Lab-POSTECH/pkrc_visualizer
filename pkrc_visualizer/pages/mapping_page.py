"""Sonar Mapping 페이지 — placeholder (Task 9)."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class MappingPage(QWidget):
    def __init__(self, ros_client=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Sonar Mapping (Task 9)")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
