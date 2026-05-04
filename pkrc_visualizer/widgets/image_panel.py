"""단일 이미지 패널: 토픽 콤보 + 닫기 + ImageView + Hz 라벨."""
from typing import Optional, Union

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout)
from sensor_msgs.msg import CompressedImage, Image

from pkrc_visualizer.widgets.image_view import ImageView
from pkrc_visualizer.widgets.topic_combobox import TopicComboBox


ImageLike = Union[Image, CompressedImage]
HZ_WINDOW_MS = 1000
HZ_TICK_MS = 200


class ImagePanel(QFrame):
    topic_changed = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._build_ui()
        self._timestamps: list[float] = []
        self._hz_timer = QTimer(self)
        self._hz_timer.setInterval(HZ_TICK_MS)
        self._hz_timer.timeout.connect(self._refresh_hz)
        self._hz_timer.start()

    def _build_ui(self) -> None:
        self._combo = TopicComboBox()
        self._combo.topic_selected.connect(self.topic_changed.emit)
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedWidth(28)
        self._close_btn.clicked.connect(self.closed.emit)
        header = QHBoxLayout()
        header.addWidget(self._combo, 1)
        header.addWidget(self._close_btn)

        self._view = ImageView()
        self._hz_label = QLabel("Hz: —")
        self._hz_label.setStyleSheet("color: #888; font-size: 11px;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addLayout(header)
        outer.addWidget(self._view, 1)
        outer.addWidget(self._hz_label)

    def set_topic_candidates(self, names: list[str]) -> None:
        self._combo.set_candidates(names)

    def set_image_msg(self, msg: Optional[ImageLike]) -> None:
        from time import monotonic
        if msg is not None:
            self._view.set_image_msg(msg)
            self._timestamps.append(monotonic())

    def current_topic(self) -> str:
        return self._combo.currentText()

    def _refresh_hz(self) -> None:
        from time import monotonic
        cutoff = monotonic() - HZ_WINDOW_MS / 1000.0
        self._timestamps = [t for t in self._timestamps if t >= cutoff]
        n = len(self._timestamps)
        self._hz_label.setText(f"Hz: {n:.1f}" if n else "Hz: —")
