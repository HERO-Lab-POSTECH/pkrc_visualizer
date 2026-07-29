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
    # GetPointSize is a vtkPolyDataMapper property; force pixels so the
    # mapper-swap helper does not replace it with vtkPointGaussianMapper.
    s = PageDisplaySettings(cloud=CloudSettings(
        size_pixels=7.0, alpha=0.5, size_unit="pixels"))
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


def test_meters_mode_attaches_style_specific_splat_shader(view):
    """vtkPointGaussianMapper must carry a per-style fragment shader.

    Without an explicit SetSplatShaderCode, the default leaves the quad
    sprite outline visible (the "white square around a gaussian disc"
    artefact). Each style now ships its own GLSL with a discard outside
    the unit disc/box so the quad never bleeds.
    """
    import vtk
    cases = [
        ("points",  "exp("),
        ("square",  "max(abs"),
        ("spheres", "diffuse"),
    ]
    for style, signature in cases:
        s = PageDisplaySettings(cloud=CloudSettings(
            size_unit="meters", style=style, size_meters=0.05))
        view.apply_display_settings(s)
        mapper = view._cloud_actor.GetMapper()
        assert isinstance(mapper, vtk.vtkPointGaussianMapper)
        code = mapper.GetSplatShaderCode()
        assert "discard" in code, f"{style} shader must discard outside sprite"
        assert signature in code, f"{style} shader missing distinguishing token"
        # Some VTK builds omit Set/GetTriangleScale; the shader's discard
        # already enforces a clean splat, so just assert when available.
        if hasattr(mapper, "GetTriangleScale"):
            assert mapper.GetTriangleScale() == 1.0


def test_apply_cloud_decay_seconds_takes_effect(view, monkeypatch):
    # Apply a 1-second decay window.
    s = PageDisplaySettings(cloud=CloudSettings(decay_seconds=1.0))
    view.apply_display_settings(s)

    monkeypatch.setattr(
        "pkrc_visualizer.widgets.pyvista_view.monotonic", lambda: 0.0)
    view.append_cloud(np.ones((10, 3), dtype=np.float32))

    monkeypatch.setattr(
        "pkrc_visualizer.widgets.pyvista_view.monotonic", lambda: 2.0)
    view.append_cloud(np.zeros((5, 3), dtype=np.float32))

    # The first chunk is 2 s old — older than the 1 s window — so it must be dropped.
    assert len(view._accum_chunks) == 1
    assert view._accum_chunks[0][1].shape[0] == 5


def test_apply_background_updates_renderer(view):
    s = PageDisplaySettings(background="#abcdef")
    view.apply_display_settings(s)
    rgb = view._plotter.renderer.GetBackground()
    assert pytest.approx(rgb[0], abs=0.01) == 0xab / 255.0


def test_active_size_routes_per_unit_to_mapper(qtbot):
    """meters: SetScaleFactor=size_meters, pixels: SetPointSize=size_pixels."""
    import vtk
    from pkrc_visualizer.display_settings import PageDisplaySettings
    from pkrc_visualizer.widgets.pyvista_view import PyVistaView
    view = PyVistaView()
    qtbot.addWidget(view)

    s = PageDisplaySettings()
    s.cloud.size_unit = "meters"
    s.cloud.size_meters = 0.07
    s.cloud.size_pixels = 9.0
    view.apply_display_settings(s)
    assert isinstance(view._cloud_actor.GetMapper(), vtk.vtkPointGaussianMapper)
    assert view._cloud_actor.GetMapper().GetScaleFactor() == 0.07

    s.cloud.size_unit = "pixels"
    view.apply_display_settings(s)
    assert view._cloud_actor.GetProperty().GetPointSize() == 9.0
