"""모든 페이지의 공통 상위. show/hide 시 timer 제어 + RosClient 시그널 연결."""
from typing import Callable

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QWidget


REFRESH_INTERVAL_MS = 100  # 10 Hz


class BasePage(QWidget):
    def __init__(self, ros_client, parent=None):
        super().__init__(parent)
        self._ros_client = ros_client
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._latest: dict[str, object] = {}
        self._connect_signals()

    def _connect_signals(self) -> None:
        # Qt가 자동으로 queued connection 사용 (다른 스레드 emit)
        self._ros_client.message_received.connect(
            self._on_message, type=Qt.QueuedConnection)

    def _on_message(self, topic_id: str, msg) -> None:
        if self._is_my_topic(topic_id):
            self._latest[topic_id] = msg

    # 서브클래스가 override
    def _is_my_topic(self, topic_id: str) -> bool:
        return False

    def refresh(self) -> None:
        """서브클래스가 override — 위젯 갱신."""

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()
