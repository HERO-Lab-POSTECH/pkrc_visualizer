"""PyVistaView prior-map API + camera push/pop (headless)."""
import pytest
from nav_msgs.msg import OccupancyGrid


@pytest.fixture
def view(qtbot):
    from pkrc_visualizer.widgets.pyvista_view import PyVistaView
    v = PyVistaView()
    qtbot.addWidget(v)
    return v


def _make_grid(w=4, h=3):
    g = OccupancyGrid()
    g.header.frame_id = "map"
    g.info.resolution = 0.5
    g.info.width = w
    g.info.height = h
    g.info.origin.position.x = -1.0
    g.info.origin.position.y = -1.0
    g.data = [0] * (w * h)
    return g


def test_set_occupancy_grid_creates_actor(view):
    assert not view._prior_map.has_actor
    view.set_occupancy_grid(_make_grid())
    assert view._prior_map.has_actor


def test_clear_occupancy_grid_removes_actor(view):
    view.set_occupancy_grid(_make_grid())
    view.clear_occupancy_grid()
    assert not view._prior_map.has_actor


def test_set_prior_grid_alpha_changes_alpha(view):
    view.set_occupancy_grid(_make_grid())
    view.set_prior_grid_alpha(0.3)
    assert view._prior_map._alpha == 0.3


def test_push_pop_camera_restores_position(view):
    cam = view._plotter.camera
    cam.position = (1.0, 2.0, 3.0)
    cam.focal_point = (0.0, 0.0, 0.0)
    view.push_camera()
    cam.position = (10.0, 0.0, 0.0)
    view.pop_camera()
    assert tuple(round(x, 3) for x in cam.position) == (1.0, 2.0, 3.0)


def test_force_top_down_aligns_camera_with_z_axis(view):
    view.force_top_down()
    cam = view._plotter.camera
    fx, fy, fz = cam.focal_point
    px, py, pz = cam.position
    # Camera should be straight above focal point: x/y match, pz > fz
    assert abs(px - fx) < 1e-3
    assert abs(py - fy) < 1e-3
    assert pz > fz
