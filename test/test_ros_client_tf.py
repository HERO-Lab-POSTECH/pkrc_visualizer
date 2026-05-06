"""RosClient.lookup_map_from_odom() returns None until TF arrives, ndarray after."""
import numpy as np
import pytest
import rclpy

from pkrc_visualizer.ros_client import RosClient


@pytest.fixture
def ros_client():
    if not rclpy.ok():
        rclpy.init()
    client = RosClient(topic_specs=[], node_name="pkrc_visualizer_test_tf")
    client.start()
    yield client
    client.stop()
    if rclpy.ok():
        rclpy.shutdown()


def test_lookup_returns_none_when_no_tf(ros_client):
    """Right after start, no TF has been published yet."""
    assert ros_client.lookup_map_from_odom() is None


def test_lookup_returns_4x4_after_seeding_buffer(ros_client):
    """If we seed the internal buffer with a static map→odom transform, the
    lookup should produce a 4×4 matrix whose translation matches the seed."""
    from geometry_msgs.msg import TransformStamped
    msg = TransformStamped()
    msg.header.stamp = ros_client._node.get_clock().now().to_msg()
    msg.header.frame_id = "map"
    msg.child_frame_id = "odom"
    msg.transform.translation.x = 1.5
    msg.transform.translation.y = -2.0
    msg.transform.translation.z = 0.0
    msg.transform.rotation.w = 1.0  # identity rotation
    # set_transform is the public API for unit-testing tf2 buffers.
    ros_client._tf_buffer.set_transform(msg, "test_authority")

    m = ros_client.lookup_map_from_odom()
    assert m is not None
    assert m.shape == (4, 4)
    assert abs(m[0, 3] - 1.5) < 1e-6
    assert abs(m[1, 3] + 2.0) < 1e-6
