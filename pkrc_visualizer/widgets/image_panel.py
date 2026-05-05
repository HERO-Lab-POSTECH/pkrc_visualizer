"""Single image panel: ImageView body + a make_titlebar() factory.

Inline header (combobox + close) was removed in v0.5.0. The page wraps each
ImagePanel in a QDockWidget and uses make_titlebar() as the dock's custom
titleBarWidget.
"""
from typing import Callable, Optional, Union

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)
from sensor_msgs.msg import CompressedImage, Image

from pkrc_visualizer.widgets.image_view import ImageView
from pkrc_visualizer.widgets.topic_combobox import TopicComboBox


ImageLike = Union[Image, CompressedImage]
HZ_WINDOW_MS = 1000
HZ_TICK_MS = 200


class ImagePanel(QFrame):
    topic_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._combo = TopicComboBox()
        self._combo.topic_selected.connect(self.topic_changed.emit)
        self._hz_label = QLabel("Hz: -")
        self._hz_label.setStyleSheet("color: #888; font-size: 11px;")

        self._view = ImageView()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._view, 1)

        self._timestamps: list[float] = []
        self._hz_timer = QTimer(self)
        self._hz_timer.setInterval(HZ_TICK_MS)
        self._hz_timer.timeout.connect(self._refresh_hz)
        self._hz_timer.start()

    def make_titlebar(self, close_cb: Callable[[], None]) -> QWidget:
        """Build the dock's custom title bar: combo + Hz + close.

        Reparents the existing combo and Hz label so they live inside the
        returned widget. Adding an explicit close button is necessary because
        QDockWidget.setTitleBarWidget hides the default close icon.
        """
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._combo, 1)
        layout.addWidget(self._hz_label)
        close_btn = QPushButton("✕")
        close_btn.setFixedWidth(24)
        close_btn.setFlat(True)
        close_btn.clicked.connect(close_cb)
        layout.addWidget(close_btn)
        return bar

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
        self._hz_label.setText(f"Hz: {n:.1f}" if n else "Hz: -")
