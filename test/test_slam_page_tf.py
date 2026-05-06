"""SlamPage applies map←odom transform when the lookup returns a matrix."""
import math
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def fake_ros_client():
    """A stub RosClient that exposes lookup_map_from_odom + a no-op subscribe API."""
    client = MagicMock()
    client.lookup_map_from_odom.return_value = None  # default: mapping mode
    return client


@pytest.fixture
def slam_page(qtbot, fake_ros_client, tmp_path, monkeypatch):
    """Build a real SlamPage backed by the stub client."""
    # Isolate display-settings persistence so the test never touches the real config.
    monkeypatch.setenv("HOME", str(tmp_path))
    from pkrc_visualizer.display_settings import DisplaySettingsStore
    from pkrc_visualizer.pages.slam_page import SlamPage
    store = DisplaySettingsStore()
    page = SlamPage(fake_ros_client, store)
    qtbot.addWidget(page)
    return page


def _odometry(x, y, z=0.0, qz=0.0, qw=1.0):
    from nav_msgs.msg import Odometry
    msg = Odometry()
    msg.pose.pose.position.x = x
    msg.pose.pose.position.y = y
    msg.pose.pose.position.z = z
    msg.pose.pose.orientation.z = qz
    msg.pose.pose.orientation.w = qw
    return msg


def _pointcloud_xyz(points):
    """Build a tiny PointCloud2 carrying the given (N, 3) numpy array."""
    from sensor_msgs.msg import PointCloud2
    from sensor_msgs_py import point_cloud2
    from std_msgs.msg import Header
    pts = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
    return point_cloud2.create_cloud_xyz32(Header(frame_id="odom"), pts)


def test_identity_when_lookup_returns_none(slam_page, fake_ros_client):
    """No TF available → forward odom-frame data unchanged (today's behaviour)."""
    fake_ros_client.lookup_map_from_odom.return_value = None
    slam_page._latest["slam_cloud"] = _pointcloud_xyz([[1.0, 0.0, 0.0]])
    slam_page._latest["pose_odom"] = _odometry(1.0, 0.0)

    captured_pts = []
    captured_pose = []
    slam_page._view.append_cloud = lambda pts, color="#4fc3f7": captured_pts.append(pts.copy())
    slam_page._view.update_robot_pose = lambda p, q: captured_pose.append((p, q))

    slam_page.refresh()

    assert len(captured_pts) == 1
    assert np.allclose(captured_pts[0][0], [1.0, 0.0, 0.0])
    assert len(captured_pose) == 1
    assert captured_pose[0][0] == (1.0, 0.0, 0.0)


def test_identity_tf_falls_back_to_odom_frame(slam_page, fake_ros_client):
    """fast-lio publishes identity `map ← odom` during global grid search
    (before /initialpose). Treat identity as no-TF so cloud stays visible in
    odom frame — otherwise the user has nothing to aim at when picking pose."""
    fake_ros_client.lookup_map_from_odom.return_value = np.eye(4)
    slam_page._latest["slam_cloud"] = _pointcloud_xyz([[1.0, 0.0, 0.0]])
    slam_page._latest["pose_odom"] = _odometry(1.0, 0.0)

    captured_pts = []
    captured_pose = []
    slam_page._view.append_cloud = lambda pts, color="#4fc3f7": captured_pts.append(pts.copy())
    slam_page._view.update_robot_pose = lambda p, q: captured_pose.append((p, q))

    slam_page.refresh()

    assert len(captured_pts) == 1
    assert np.allclose(captured_pts[0][0], [1.0, 0.0, 0.0])
    assert captured_pose[0][0] == (1.0, 0.0, 0.0)


def test_transform_applied_when_lookup_returns_matrix(slam_page, fake_ros_client):
    """`map ← odom` = +y by 5m. Cloud at odom (1, 0, 0) lands at map (1, 5, 0)."""
    m = np.eye(4)
    m[1, 3] = 5.0
    fake_ros_client.lookup_map_from_odom.return_value = m
    slam_page._latest["slam_cloud"] = _pointcloud_xyz([[1.0, 0.0, 0.0]])
    slam_page._latest["pose_odom"] = _odometry(1.0, 0.0)

    captured_pts = []
    captured_pose = []
    slam_page._view.append_cloud = lambda pts, color="#4fc3f7": captured_pts.append(pts.copy())
    slam_page._view.update_robot_pose = lambda p, q: captured_pose.append((p, q))

    slam_page.refresh()

    assert len(captured_pts) == 1
    assert np.allclose(captured_pts[0][0], [1.0, 5.0, 0.0])
    assert len(captured_pose) == 1
    p, _ = captured_pose[0]
    assert abs(p[0] - 1.0) < 1e-6
    assert abs(p[1] - 5.0) < 1e-6
