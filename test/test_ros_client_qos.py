"""Subscribe-side QoS branching tests."""
import rclpy
import pytest
from nav_msgs.msg import OccupancyGrid

from pkrc_visualizer.ros_client import RosClient
from pkrc_visualizer.topic_config import TopicSpec


@pytest.fixture(autouse=True)
def _ros_init():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_transient_local_subscription_uses_transient_local_durability():
    spec = TopicSpec("grid", "/test/occupancy_grid", OccupancyGrid,
                     qos_transient_local=True)
    client = RosClient([spec], node_name="qos_test_node")
    client.start()
    try:
        node = client._node
        assert node is not None
        endpoints = node.get_subscriptions_info_by_topic("/test/occupancy_grid")
        assert endpoints, "subscription not registered"
        from rclpy.qos import DurabilityPolicy
        assert endpoints[0].qos_profile.durability == DurabilityPolicy.TRANSIENT_LOCAL
    finally:
        client.stop()


import math
import time
from geometry_msgs.msg import PoseWithCovarianceStamped


def test_publish_initialpose_emits_pose_with_yaw():
    client = RosClient([], node_name="initpose_test_node")
    client.start()
    received: list[PoseWithCovarianceStamped] = []
    try:
        node = client._node
        assert node is not None
        node.create_subscription(
            PoseWithCovarianceStamped, "/initialpose",
            lambda msg: received.append(msg), 10)
        time.sleep(0.1)
        client.publish_initialpose(1.5, -2.0, math.pi / 2)
        deadline = time.time() + 2.0
        while time.time() < deadline and not received:
            time.sleep(0.05)
        assert received, "initialpose not received"
        msg = received[0]
        assert msg.header.frame_id == "map"
        assert abs(msg.pose.pose.position.x - 1.5) < 1e-6
        assert abs(msg.pose.pose.position.y + 2.0) < 1e-6
        # yaw = pi/2 → quaternion (0, 0, sin(pi/4), cos(pi/4))
        assert abs(msg.pose.pose.orientation.z - math.sin(math.pi / 4)) < 1e-6
        assert abs(msg.pose.pose.orientation.w - math.cos(math.pi / 4)) < 1e-6
    finally:
        client.stop()
