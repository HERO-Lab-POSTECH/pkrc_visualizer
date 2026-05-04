"""RosClient: spin rclpy on a separate thread, subscribe to topics -> cache + signal."""
import threading
import time

import pytest
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image as ImageMsg

from pkrc_visualizer.ros_client import RosClient
from pkrc_visualizer.topic_config import TopicSpec


@pytest.fixture(scope="function")
def rclpy_init():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_ros_client_caches_message_and_emits_signal(qtbot, rclpy_init):
    spec = TopicSpec("test_odom", "/test/odometry", Odometry)
    client = RosClient([spec])
    client.start()

    # Fake publisher.
    pub_node = Node("fake_pub")
    pub = pub_node.create_publisher(Odometry, "/test/odometry", 10)
    pub_thread = threading.Thread(target=lambda: rclpy.spin_once(pub_node, timeout_sec=0.1))

    received = []
    client.message_received.connect(lambda tid, msg: received.append((tid, msg)))

    # Publish a message.
    msg = Odometry()
    msg.pose.pose.position.x = 1.0
    pub.publish(msg)
    pub_thread.start()
    pub_thread.join()

    # Wait for signal delivery (spin the Qt event loop).
    deadline = time.time() + 2.0
    while time.time() < deadline and not received:
        qtbot.wait(50)

    assert received, "RosClient did not emit a signal"
    topic_id, payload = received[0]
    assert topic_id == "test_odom"
    assert payload.pose.pose.position.x == 1.0
    assert client.latest("test_odom").pose.pose.position.x == 1.0

    pub_node.destroy_node()
    client.stop()


def test_discover_topics_filters_by_type():
    """Filter get_topic_names_and_types() results by message type."""
    client = RosClient([])
    fake_topics = [
        ("/cam/raw", ["sensor_msgs/msg/Image"]),
        ("/cam/compressed", ["sensor_msgs/msg/CompressedImage"]),
        ("/scan", ["sensor_msgs/msg/LaserScan"]),
        ("/tf", ["tf2_msgs/msg/TFMessage"]),
    ]
    found = client._filter_topics(fake_topics, [ImageMsg, CompressedImage])
    assert found == {
        "/cam/raw": "sensor_msgs/msg/Image",
        "/cam/compressed": "sensor_msgs/msg/CompressedImage",
    }


def test_discover_diff_emits_only_on_change(qtbot):
    client = RosClient([])
    client._known_topics = {"/a": "sensor_msgs/msg/Image"}
    spy = []
    client.topics_changed.connect(lambda d: spy.append(dict(d)))
    # No change - must not emit.
    client._publish_if_changed({"/a": "sensor_msgs/msg/Image"})
    assert spy == []
    # Added - emit.
    client._publish_if_changed({
        "/a": "sensor_msgs/msg/Image",
        "/b": "sensor_msgs/msg/CompressedImage",
    })
    assert len(spy) == 1
    assert spy[0]["/b"] == "sensor_msgs/msg/CompressedImage"


def test_subscribe_dynamic_returns_unique_topic_id():
    client = RosClient([])
    # ID issuance must work even when _node is None (registration happens after start).
    tid1 = client._make_topic_id("/cam/raw")
    tid2 = client._make_topic_id("/cam/raw")
    assert tid1 != tid2
    assert tid1.startswith("dyn_")


def test_subscribe_dynamic_ref_counts(monkeypatch):
    """Subscribing twice to the same topic must call create_subscription only once."""
    client = RosClient([])

    class FakeNode:
        def __init__(self):
            self.created = []

        def create_subscription(self, msg_type, name, cb, qos):
            sub = ("sub", name, msg_type, cb, qos)
            self.created.append(sub)
            return sub

        def destroy_subscription(self, sub):
            self.created.remove(sub)

    fake = FakeNode()
    client._node = fake  # type: ignore
    tid1 = client.subscribe_dynamic("/cam/raw", ImageMsg)
    tid2 = client.subscribe_dynamic("/cam/raw", ImageMsg)
    assert len(fake.created) == 1   # Only one real subscription.
    client.unsubscribe(tid1)
    assert len(fake.created) == 1   # Still ref > 0.
    client.unsubscribe(tid2)
    assert len(fake.created) == 0   # Final release destroys.
