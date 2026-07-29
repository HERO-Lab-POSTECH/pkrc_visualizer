"""Monitoring page sonar panel — wraps ImageView with title chrome.

Subscribed via the page's dispatch table for two topics in parallel:
m750d and m3000d. Whichever message arrives is rendered.
"""
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from pkrc_visualizer.pages.monitoring.common import PANEL_QSS, TITLE_QSS
from pkrc_visualizer.widgets.image_view import ImageView


class SonarImageWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        title = QLabel("🌊 소나 이미지")
        title.setStyleSheet(TITLE_QSS)
        layout.addWidget(title)

        self._view = ImageView()
        self._view.setText("소나 이미지 대기 중\n(m750d / m3000d)")
        layout.addWidget(self._view, 1)

    def set_image_msg(self, msg) -> None:
        """sensor_msgs/Image or CompressedImage."""
        self._view.set_image_msg(msg)
