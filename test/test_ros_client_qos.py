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
