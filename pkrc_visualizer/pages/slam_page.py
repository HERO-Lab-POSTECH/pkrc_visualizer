"""SLAM 페이지 — placeholder (Task 8에서 PyVista 임베드)."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class SlamPage(QWidget):
    def __init__(self, ros_client=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("SLAM (Task 8에서 점군 viewer 임베드)")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
