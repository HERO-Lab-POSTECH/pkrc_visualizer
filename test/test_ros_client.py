"""RosClient: rclpy를 별도 스레드에서 spin하면서 토픽 구독 → cache + signal."""
import threading
import time

import pytest
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node

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
