"""Camera preview — decode JPEG from CompressedImage and render via QPixmap.

Lightweight: PyQt5 decodes JPEG natively (no OpenCV). We only decode when a
new message arrives; rescale on every paintEvent to fit the current widget
size.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from pkrc_visualizer.pages.monitoring.common import (PANEL_BG_INNER,
                                                       PANEL_QSS, TEXT_DIM,
                                                       TITLE_QSS)


class CameraWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)
        title = QLabel("📷 카메라")
        title.setStyleSheet(TITLE_QSS)
        layout.addWidget(title)
        self._image_label = QLabel("/camera/image/compressed 대기 중…")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet(
            f"color: {TEXT_DIM}; background: #000000; "
            f"border-radius: 6px; font-size: 11px;"
        )
        self._image_label.setMinimumSize(160, 120)
        layout.addWidget(self._image_label, 1)
        self._pixmap: QPixmap | None = None

    def update_from_msg(self, msg) -> None:
        # CompressedImage.data: bytes-like JPEG stream.
        # Sometimes 'format' is "jpeg" or "rgb8; jpeg compressed"; QPixmap
        # auto-detects the format from the byte signature so the hint is
        # only a fallback.
        fmt_hint = "JPEG" if "jpeg" in str(msg.format).lower() else None
        pix = QPixmap()
        loaded = pix.loadFromData(bytes(msg.data), fmt_hint)
        if not loaded:
            return
        self._pixmap = pix
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        target = self._image_label.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._pixmap.scaled(
            target, Qt.KeepAspectRatio, Qt.FastTransformation)
        self._image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()
