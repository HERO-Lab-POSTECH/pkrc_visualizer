"""Spin rclpy on a separate thread and forward subscribed topics as Qt signals."""
import threading
from typing import Any, Iterable, Optional

import numpy as np
import rclpy
import tf2_ros
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time

from pkrc_visualizer.qos import RELIABLE_QOS, SENSOR_QOS
from pkrc_visualizer.tf_transform import transform_to_matrix
from pkrc_visualizer.topic_config import TopicSpec


class RosClient(QObject):
    """Subscribe to every topic, cache the latest message, and emit it via pyqtSignal."""

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
        self._dynamic_subs: dict[str, tuple[Any, int]] = {}
        # topic_name → (subscription_handle, ref_count)
        self._tid_to_topic: dict[str, str] = {}
        self._tid_seq = 0
        self._initialpose_pub: Optional[Any] = None
        self._tf_buffer: Optional[tf2_ros.Buffer] = None
        self._tf_listener: Optional[tf2_ros.TransformListener] = None

    def start(self) -> None:
        if not rclpy.ok():
            raise RuntimeError("rclpy.init() must be called first.")
        # automatically_declare_parameters_from_overrides honors CLI/launch
        # `use_sim_time` so /initialpose and any time-stamped publication
        # align with the bag clock during replay.
        self._node = rclpy.create_node(
            self._node_name,
            automatically_declare_parameters_from_overrides=True,
        )
        for spec in self._specs:
            self._subscribe(spec)
        self._tf_buffer = tf2_ros.Buffer()
        self._tf_listener = tf2_ros.TransformListener(self._tf_buffer, self._node)
        self._executor_thread = threading.Thread(target=self._spin_loop, daemon=True)
        self._executor_thread.start()

    def _subscribe(self, spec: TopicSpec) -> None:
        assert self._node is not None, "RosClient.start() must be called first."
        # Workspace-standard QoS profiles (spec §2.4). transient_local is a
        # separate axis (latched publishers like OccupancyGrid prior maps),
        # so build a custom profile when the spec asks for it.
        if spec.qos_transient_local:
            qos = QoSProfile(depth=10)
            qos.reliability = (ReliabilityPolicy.BEST_EFFORT if spec.qos_best_effort
                               else ReliabilityPolicy.RELIABLE)
            qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        else:
            qos = SENSOR_QOS if spec.qos_best_effort else RELIABLE_QOS
        self._node.create_subscription(
            spec.msg_type, spec.topic_name,
            lambda msg, tid=spec.topic_id: self._on_msg(tid, msg),
            qos,
        )

    def enable_discovery(self, msg_types: list[type]) -> None:
        """Begin periodic topic discovery. Emit topics_changed when the matching set changes."""
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
        """raw = [(name, [type_str, ...]), ...] -> {name: first_matching_type_str}.

        A topic can carry multiple types (rare); only the first match is used.
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
            except Exception as exc:  # noqa: BLE001 - keep the Qt UI alive on errors
                self._node.get_logger().error(f"spin loop exception: {exc}")

    def latest(self, topic_id: str) -> Optional[Any]:
        with self._cache_lock:
            return self._cache.get(topic_id)

    def _make_topic_id(self, topic_name: str) -> str:
        self._tid_seq += 1
        sanitized = topic_name.strip("/").replace("/", "_") or "root"
        return f"dyn_{self._tid_seq}_{sanitized}"

    def subscribe_dynamic(self, topic_name: str, msg_type: type) -> str:
        """Dynamic subscribe. Repeated calls for the same topic_name only bump the ref count."""
        topic_id = self._make_topic_id(topic_name)
        if topic_name in self._dynamic_subs:
            sub, count = self._dynamic_subs[topic_name]
            self._dynamic_subs[topic_name] = (sub, count + 1)
        else:
            assert self._node is not None, "RosClient.start() must precede subscribe_dynamic()"
            qos = SENSOR_QOS
            sub = self._node.create_subscription(
                msg_type, topic_name,
                lambda msg, name=topic_name: self._on_dynamic_msg(name, msg),
                qos,
            )
            self._dynamic_subs[topic_name] = (sub, 1)
        self._tid_to_topic[topic_id] = topic_name
        return topic_id

    def unsubscribe(self, topic_id: str) -> None:
        topic_name = self._tid_to_topic.pop(topic_id, None)
        if topic_name is None:
            return
        sub, count = self._dynamic_subs.get(topic_name, (None, 0))
        if sub is None:
            return
        if count <= 1:
            self._node.destroy_subscription(sub)  # type: ignore
            self._dynamic_subs.pop(topic_name, None)
        else:
            self._dynamic_subs[topic_name] = (sub, count - 1)

    def _on_dynamic_msg(self, topic_name: str, msg: Any) -> None:
        """Fan out a dynamic-subscription message to every active topic_id."""
        for tid, name in self._tid_to_topic.items():
            if name == topic_name:
                with self._cache_lock:
                    self._cache[tid] = msg
                self.message_received.emit(tid, msg)

    def publish_initialpose(self, x: float, y: float, yaw: float) -> None:
        """Publish a 2D pose estimate to /initialpose (RViz-compatible).

        frame_id = "map", z = 0, covariance uses RViz defaults
        (xx=0.25, yy=0.25, yaw=0.06853891945200942).
        """
        import math
        from geometry_msgs.msg import PoseWithCovarianceStamped
        if self._node is None:
            return
        if self._initialpose_pub is None:
            self._initialpose_pub = self._node.create_publisher(
                PoseWithCovarianceStamped, "/initialpose", 10)
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.x = 0.0
        msg.pose.pose.orientation.y = 0.0
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        cov = [0.0] * 36
        cov[0] = 0.25                  # xx
        cov[7] = 0.25                  # yy
        cov[35] = 0.06853891945200942  # yaw-yaw (RViz default)
        msg.pose.covariance = cov
        self._initialpose_pub.publish(msg)

    def lookup_map_from_odom(self) -> Optional[np.ndarray]:
        """Return the latest `map ← odom` transform as a 4×4 numpy matrix.

        Returns None if the buffer has not yet seen a `map → odom` TF
        (e.g. mapping mode, or localization mode before the first
        `mat_odom2map_` rebroadcast). Callers should treat that as
        "render in odom frame" (identity fallback).
        """
        if self._tf_buffer is None:
            return None
        try:
            ts = self._tf_buffer.lookup_transform(
                "map", "odom", Time(), timeout=Duration(seconds=0.0))
        except (tf2_ros.LookupException, tf2_ros.ExtrapolationException,
                tf2_ros.ConnectivityException, tf2_ros.TransformException):
            return None
        t = ts.transform.translation
        r = ts.transform.rotation
        return transform_to_matrix(
            translation=(t.x, t.y, t.z),
            quaternion=(r.x, r.y, r.z, r.w),
        )

    def lookup_odom_from_base(self, stamp) -> Optional[np.ndarray]:
        """Return `odom ← base_link` at message timestamp as 4×4 numpy matrix.

        Used to lift base_link-frame point clouds (e.g. /localization/fast_lio/points_body)
        into odom frame. Returns None if TF for that timestamp is unavailable —
        caller should drop the frame; the next sample retries.
        """
        if self._tf_buffer is None:
            return None
        try:
            ts = self._tf_buffer.lookup_transform(
                "odom", "base_link", Time.from_msg(stamp),
                timeout=Duration(seconds=0.0))
        except (tf2_ros.LookupException, tf2_ros.ExtrapolationException,
                tf2_ros.ConnectivityException, tf2_ros.TransformException):
            return None
        t = ts.transform.translation
        r = ts.transform.rotation
        return transform_to_matrix(
            translation=(t.x, t.y, t.z),
            quaternion=(r.x, r.y, r.z, r.w),
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._executor_thread is not None:
            self._executor_thread.join(timeout=1.0)
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
