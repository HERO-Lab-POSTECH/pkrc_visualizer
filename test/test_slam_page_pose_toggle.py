"""SLAM page Pose Estimate toggle wiring."""
import math
import pytest


@pytest.fixture
def page(qtbot, tmp_path):
    import rclpy
    from pkrc_visualizer.display_settings import DisplaySettingsStore
    from pkrc_visualizer.ros_client import RosClient
    from pkrc_visualizer.pages.slam_page import SlamPage
    if not rclpy.ok():
        rclpy.init()
    store = DisplaySettingsStore(path=tmp_path / "settings.yaml")
    client = RosClient([], node_name="slam_page_test_node")
    client.start()
    p = SlamPage(client, store)
    qtbot.addWidget(p)
    yield p
    p.close()
    client.stop()
    rclpy.shutdown()


def test_pose_estimate_toggle_attaches_and_detaches(page):
    btn = page._pose_estimate_action
    assert not btn.isChecked()
    assert page._pose_tool is not None
    assert not page._pose_tool._observer_ids
    btn.toggle()           # ON
    assert btn.isChecked()
    assert page._pose_tool._observer_ids
    btn.toggle()           # OFF
    assert not btn.isChecked()
    assert not page._pose_tool._observer_ids


def test_pose_estimate_drag_calls_publish_initialpose(page, monkeypatch):
    calls = []
    monkeypatch.setattr(
        page._ros_client, "publish_initialpose",
        lambda x, y, yaw: calls.append((x, y, yaw)))
    page._pose_estimate_action.toggle()  # ON

    # Inject world-frame events (skip VTK pixel mapping).
    page._pose_tool._on_press_world(1.0, 0.0)
    page._pose_tool._on_release_world(1.0, 2.0)

    assert len(calls) == 1
    x, y, yaw = calls[0]
    assert abs(x - 1.0) < 1e-3
    assert abs(y - 0.0) < 1e-3
    assert abs(yaw - math.pi / 2) < 1e-3


def test_hideEvent_disables_pose_estimate(page):
    page._pose_estimate_action.toggle()  # ON
    assert page._pose_tool._observer_ids
    page.show()   # must be visible for hideEvent to fire
    page.hide()
    assert not page._pose_tool._observer_ids
    assert not page._pose_estimate_action.isChecked()
