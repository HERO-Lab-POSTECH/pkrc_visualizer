"""MonitoringPage: dispatch table includes new sonar entries."""
from unittest.mock import MagicMock

from pkrc_visualizer.pages.monitoring.sonar_image_widget import \
    SonarImageWidget
from pkrc_visualizer.pages.monitoring_page import MonitoringPage


def _stub_ros_client():
    rc = MagicMock()
    rc.lookup_map_from_odom.return_value = None
    return rc


def test_page_uses_sonar_image_widget(qtbot):
    page = MonitoringPage(_stub_ros_client())
    qtbot.addWidget(page)
    assert isinstance(page._sonar, SonarImageWidget)


def test_dispatch_has_sonar_entries(qtbot):
    page = MonitoringPage(_stub_ros_client())
    qtbot.addWidget(page)
    assert "mon_sonar_m750d" in page._dispatch
    assert "mon_sonar_m3000d" in page._dispatch
    assert page._dispatch["mon_sonar_m750d"] == page._sonar.set_image_msg
    assert page._dispatch["mon_sonar_m3000d"] == page._sonar.set_image_msg


import numpy as np
from nav_msgs.msg import Odometry


def _identity_4x4():
    return np.eye(4, dtype=np.float64)


def _odom_at(x, y, yaw=0.0):
    msg = Odometry()
    msg.pose.pose.position.x = x
    msg.pose.pose.position.y = y
    msg.pose.pose.orientation.z = float(np.sin(yaw / 2.0))
    msg.pose.pose.orientation.w = float(np.cos(yaw / 2.0))
    return msg


def test_handle_odom_uses_tf_when_available(qtbot):
    rc = MagicMock()
    tf = _identity_4x4()
    tf[0, 3] = 10.0
    tf[1, 3] = 20.0
    rc.lookup_map_from_odom.return_value = tf

    page = MonitoringPage(rc)
    qtbot.addWidget(page)

    page._handle_odom(_odom_at(1.0, 2.0))
    canvas = page._map._canvas
    assert canvas._x == 11.0
    assert canvas._y == 22.0


def test_handle_odom_falls_back_when_no_tf(qtbot):
    rc = MagicMock()
    rc.lookup_map_from_odom.return_value = None

    page = MonitoringPage(rc)
    qtbot.addWidget(page)

    page._handle_odom(_odom_at(3.0, 4.0))
    canvas = page._map._canvas
    assert canvas._x == 3.0
    assert canvas._y == 4.0


def test_dispatch_routes_mon_odom_to_handle_odom(qtbot):
    rc = MagicMock()
    rc.lookup_map_from_odom.return_value = None
    page = MonitoringPage(rc)
    qtbot.addWidget(page)
    assert page._dispatch["mon_odom"] == page._handle_odom


def test_dispatch_has_map_entries(qtbot):
    rc = MagicMock()
    rc.lookup_map_from_odom.return_value = None
    page = MonitoringPage(rc)
    qtbot.addWidget(page)
    assert page._dispatch["mon_map_carto"] == page._map.set_occupancy_grid
    assert page._dispatch["mon_map_fastlio"] == page._map.set_occupancy_grid
