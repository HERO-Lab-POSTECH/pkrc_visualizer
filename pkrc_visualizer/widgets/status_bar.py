"""Estimate per-topic Hz over a 1-second sliding window and show it in the status bar."""
import time
from collections import defaultdict, deque

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QLabel, QStatusBar


class TopicHzStatusBar(QStatusBar):
    WINDOW_SEC = 1.0
    UPDATE_MS = 500

    def __init__(self, ros_client, parent=None):
        super().__init__(parent)
        self._ros_client = ros_client
        self._timestamps: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))
        self._labels: dict[str, QLabel] = {}
        self._page_label = QLabel("Page: -")
        self.addWidget(self._page_label)

        ros_client.message_received.connect(self._on_msg, type=Qt.QueuedConnection)

        self._timer = QTimer(self)
        self._timer.setInterval(self.UPDATE_MS)
        self._timer.timeout.connect(self._refresh_labels)
        self._timer.start()

    def _on_msg(self, topic_id: str, _msg) -> None:
        self._timestamps[topic_id].append(time.monotonic())

    def set_page_text(self, text: str) -> None:
        self._page_label.setText(text)

    def _refresh_labels(self) -> None:
        now = time.monotonic()
        for topic_id, stamps in self._timestamps.items():
            while stamps and now - stamps[0] > self.WINDOW_SEC:
                stamps.popleft()
            hz = len(stamps) / self.WINDOW_SEC
            label = self._labels.get(topic_id)
            if label is None:
                label = QLabel()
                # Cap label width so the status bar can't grow past the
                # window's normal minimum. Without this, every newly-seen
                # topic permanently widens the bar (the WM then refuses to
                # maximize the window because its minimum has outgrown the
                # screen).
                label.setMaximumWidth(140)
                self._labels[topic_id] = label
                self.addPermanentWidget(label)
            color = "#81c784" if hz > 0 else "#888"
            label.setText(f"{topic_id}: {hz:.1f} Hz")
            label.setStyleSheet(f"color: {color}; padding: 0 6px;")
