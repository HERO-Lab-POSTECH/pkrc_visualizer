"""RosClient: rclpy를 별도 스레드에서 spin하면서 토픽 구독 → cache + signal."""
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

    # 페이크 publisher
    pub_node = Node("fake_pub")
    pub = pub_node.create_publisher(Odometry, "/test/odometry", 10)
    pub_thread = threading.Thread(target=lambda: rclpy.spin_once(pub_node, timeout_sec=0.1))

    received = []
    client.message_received.connect(lambda tid, msg: received.append((tid, msg)))

    # 메시지 발행
    msg = Odometry()
    msg.pose.pose.position.x = 1.0
    pub.publish(msg)
    pub_thread.start()
    pub_thread.join()

    # 시그널 처리 대기 (Qt 이벤트 루프 spin)
    deadline = time.time() + 2.0
    while time.time() < deadline and not received:
        qtbot.wait(50)

    assert received, "RosClient가 시그널을 발신하지 않음"
    topic_id, payload = received[0]
    assert topic_id == "test_odom"
    assert payload.pose.pose.position.x == 1.0
    assert client.latest("test_odom").pose.pose.position.x == 1.0

    pub_node.destroy_node()
    client.stop()


def test_discover_topics_filters_by_type():
    """get_topic_names_and_types() 결과를 메시지 타입으로 필터링."""
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
    # 변경 없음 — emit 금지
    client._publish_if_changed({"/a": "sensor_msgs/msg/Image"})
    assert spy == []
    # 추가됨 — emit
    client._publish_if_changed({
        "/a": "sensor_msgs/msg/Image",
        "/b": "sensor_msgs/msg/CompressedImage",
    })
    assert len(spy) == 1
    assert spy[0]["/b"] == "sensor_msgs/msg/CompressedImage"
