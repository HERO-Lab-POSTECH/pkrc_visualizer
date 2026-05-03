"""rclpy를 별도 스레드에서 spin하면서 토픽을 구독하고 Qt signal로 전달."""
import threading
from typing import Any, Iterable, Optional

import rclpy
from PyQt5.QtCore import QObject, pyqtSignal
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from pkrc_visualizer.topic_config import TopicSpec


class RosClient(QObject):
    """모든 토픽을 항상 구독하면서 최신 메시지를 cache + pyqtSignal로 푸시."""

    message_received = pyqtSignal(str, object)  # (topic_id, msg)

    def __init__(self, topic_specs: Iterable[TopicSpec], node_name: str = "pkrc_visualizer"):
        super().__init__()
        self._specs = list(topic_specs)
        self._node_name = node_name
        self._node: Optional[Node] = None
        self._executor_thread: Optional[threading.Thread] = None
        self._cache: dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self) -> None:
        if not rclpy.ok():
            raise RuntimeError("rclpy.init()이 먼저 호출되어야 합니다.")
        self._node = rclpy.create_node(self._node_name)
        for spec in self._specs:
            self._subscribe(spec)
        self._executor_thread = threading.Thread(target=self._spin_loop, daemon=True)
        self._executor_thread.start()

    def _subscribe(self, spec: TopicSpec) -> None:
        assert self._node is not None, "RosClient.start()가 먼저 호출되어야 합니다."
        qos = QoSProfile(depth=10)
        if spec.qos_best_effort:
            qos.reliability = ReliabilityPolicy.BEST_EFFORT
        self._node.create_subscription(
            spec.msg_type, spec.topic_name,
            lambda msg, tid=spec.topic_id: self._on_msg(tid, msg),
            qos,
        )

    def _on_msg(self, topic_id: str, msg: Any) -> None:
        with self._cache_lock:
            self._cache[topic_id] = msg
        self.message_received.emit(topic_id, msg)

    def _spin_loop(self) -> None:
        assert self._node is not None
        while not self._stop_event.is_set():
            try:
                rclpy.spin_once(self._node, timeout_sec=0.1)
            except Exception as exc:  # noqa: BLE001 — Qt UI는 계속 살리기 위함
                self._node.get_logger().error(f"spin loop exception: {exc}")

    def latest(self, topic_id: str) -> Optional[Any]:
        with self._cache_lock:
            return self._cache.get(topic_id)

    def stop(self) -> None:
        self._stop_event.set()
        if self._executor_thread is not None:
            self._executor_thread.join(timeout=1.0)
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
