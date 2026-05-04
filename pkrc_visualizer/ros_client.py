"""rclpy를 별도 스레드에서 spin하면서 토픽을 구독하고 Qt signal로 전달."""
import threading
from typing import Any, Iterable, Optional

import rclpy
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from pkrc_visualizer.topic_config import TopicSpec


class RosClient(QObject):
    """모든 토픽을 항상 구독하면서 최신 메시지를 cache + pyqtSignal로 푸시."""

    message_received = pyqtSignal(str, object)  # (topic_id, msg)
    topics_changed = pyqtSignal(dict)            # {topic_name: type_str}

    DISCOVER_INTERVAL_MS = 1000

    def __init__(self, topic_specs: Iterable[TopicSpec], node_name: str = "pkrc_visualizer"):
        super().__init__()
        self._specs = list(topic_specs)
        self._node_name = node_name
        self._node: Optional[Node] = None
        self._executor_thread: Optional[threading.Thread] = None
        self._cache: dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._known_topics: dict[str, str] = {}
        self._discover_msg_types: list[type] = []
        self._discover_timer: Optional[QTimer] = None

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

    def enable_discovery(self, msg_types: list[type]) -> None:
        """주기적 토픽 발견 시작. 발견된 토픽 타입이 변경되면 topics_changed emit."""
        self._discover_msg_types = list(msg_types)
        if self._discover_timer is None:
            self._discover_timer = QTimer(self)
            self._discover_timer.setInterval(self.DISCOVER_INTERVAL_MS)
            self._discover_timer.timeout.connect(self._poll_topics)
            self._discover_timer.start()

    def disable_discovery(self) -> None:
        if self._discover_timer is not None:
            self._discover_timer.stop()
            self._discover_timer = None
        self._known_topics = {}

    def _poll_topics(self) -> None:
        if self._node is None:
            return
        raw = self._node.get_topic_names_and_types()
        found = self._filter_topics(raw, self._discover_msg_types)
        self._publish_if_changed(found)

    @staticmethod
    def _filter_topics(
        raw: list[tuple[str, list[str]]],
        msg_types: list[type],
    ) -> dict[str, str]:
        """raw = [(name, [type_str, ...]), ...] → {name: first_matching_type_str}.

        한 토픽이 여러 type을 가질 수 있으나 (rare) 첫 매칭만 사용.
        """
        wanted = {f"{cls.__module__.split('.')[0]}/msg/{cls.__name__}"
                  for cls in msg_types}
        result: dict[str, str] = {}
        for name, types in raw:
            for t in types:
                if t in wanted:
                    result[name] = t
                    break
        return result

    def _publish_if_changed(self, found: dict[str, str]) -> None:
        if found == self._known_topics:
            return
        self._known_topics = dict(found)
        self.topics_changed.emit(self._known_topics)

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
