"""Placeholder for sonar visualization — TBD in a future round."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from pkrc_visualizer.pages.monitoring.common import (PANEL_BG_INNER, PANEL_QSS,
                                                       TEXT_DIM, TEXT_LABEL,
                                                       TITLE_QSS)


class SonarPlaceholderWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)
        title = QLabel("🌊 소나")
        title.setStyleSheet(TITLE_QSS)
        layout.addWidget(title)
        body = QLabel("sonar view\nTBD")
        body.setAlignment(Qt.AlignCenter)
        body.setStyleSheet(
            f"color: {TEXT_LABEL}; background: {PANEL_BG_INNER}; "
            f"border-radius: 6px; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(body, 1)
