"""Verify apply_display_settings pushes values into VTK property setters."""
import numpy as np
import pytest

from pkrc_visualizer.display_settings import (
    CloudSettings, FramesSettings, PageDisplaySettings,
)
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


@pytest.fixture
def view(qtbot):
    v = PyVistaView()
    qtbot.addWidget(v)
    return v


def test_apply_frames_updates_axes_lengths(view):
    s = PageDisplaySettings(frames=FramesSettings(
        map_axes_length_m=2.5, robot_axes_length_m=1.5,
    ))
    view.apply_display_settings(s)
    assert view._origin_axes.GetTotalLength() == (2.5, 2.5, 2.5)
    assert view._robot_axes.GetTotalLength() == (1.5, 1.5, 1.5)


def test_apply_frames_hides_when_disabled(view):
    s = PageDisplaySettings(frames=FramesSettings(
        show_map_frame=False, show_robot_frame=False,
    ))
    view.apply_display_settings(s)
    assert view._origin_axes.GetVisibility() == 0
    assert view._robot_axes.GetVisibility() == 0
    assert view._origin_label.GetVisibility() == 0
    assert view._robot_label.GetVisibility() == 0


def test_apply_cloud_updates_point_size_and_alpha(view):
    s = PageDisplaySettings(cloud=CloudSettings(size=7.0, alpha=0.5))
    view.apply_display_settings(s)
    assert view._cloud_actor.GetProperty().GetPointSize() == 7.0
    assert view._accum_actor.GetProperty().GetPointSize() == 7.0
    assert view._cloud_actor.GetProperty().GetOpacity() == 0.5


def test_apply_cloud_flat_color(view):
    s = PageDisplaySettings(cloud=CloudSettings(
        color_transformer="flat", flat_color="#ff0000",
    ))
    view.apply_display_settings(s)
    rgb = view._cloud_actor.GetProperty().GetColor()
    assert rgb == (1.0, 0.0, 0.0)
    assert view._cloud_actor.GetMapper().GetScalarVisibility() == 0


def test_apply_cloud_z_transformer_attaches_scalar(view):
    s = PageDisplaySettings(cloud=CloudSettings(
        color_transformer="z", color_min=-2.0, color_max=2.0,
    ))
    view.apply_display_settings(s)
    pts = np.array([[0, 0, -1], [0, 0, 0], [0, 0, 1]], dtype=np.float32)
    view.update_cloud(pts)
    polydata = view._polydata_keepalive[id(view._cloud_actor)]
    assert "scalar" in polydata.point_data
    assert view._cloud_actor.GetMapper().GetScalarVisibility() == 1
    rng = view._cloud_actor.GetMapper().GetScalarRange()
    assert rng == (-2.0, 2.0)


def test_apply_cloud_decay_max_points_takes_effect(view):
    s = PageDisplaySettings(cloud=CloudSettings(decay_max_points=50))
    view.apply_display_settings(s)
    pts = np.random.rand(200, 3).astype(np.float32)
    view.append_cloud(pts)
    assert view._accum_points.shape[0] == 50


def test_apply_background_updates_renderer(view):
    s = PageDisplaySettings(background="#abcdef")
    view.apply_display_settings(s)
    rgb = view._plotter.renderer.GetBackground()
    assert pytest.approx(rgb[0], abs=0.01) == 0xab / 255.0
