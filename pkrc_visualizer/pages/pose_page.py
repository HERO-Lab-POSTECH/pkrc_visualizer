"""위치/경로 페이지 — placeholder (Task 7에서 matplotlib XY plot)."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class PosePage(QWidget):
    def __init__(self, ros_client=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("위치/경로 (Task 7)")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
