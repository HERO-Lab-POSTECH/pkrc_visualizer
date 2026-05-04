"""Mapper swap (vtkPolyDataMapper <-> vtkPointGaussianMapper) for size_unit toggle."""
import vtk

from pkrc_visualizer.display_settings import PageDisplaySettings
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


def _apply(view, *, size_unit, size=2.0):
    s = PageDisplaySettings()
    s.cloud.size_unit = size_unit
    s.cloud.size = size
    view.apply_display_settings(s)


def test_pixel_mode_uses_polydata_mapper(qtbot):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply(view, size_unit="pixels", size=5.0)
    for actor in (view._cloud_actor, view._accum_actor):
        mapper = actor.GetMapper()
        assert isinstance(mapper, vtk.vtkPolyDataMapper)
        assert not isinstance(mapper, vtk.vtkPointGaussianMapper)
        assert actor.GetProperty().GetPointSize() == 5.0


def test_meter_mode_swaps_to_gaussian_mapper(qtbot):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply(view, size_unit="meters", size=0.5)
    for actor in (view._cloud_actor, view._accum_actor):
        mapper = actor.GetMapper()
        assert isinstance(mapper, vtk.vtkPointGaussianMapper)
        assert mapper.GetScaleFactor() == 0.5
        # EmissiveOff so alpha behaves naturally.
        assert mapper.GetEmissive() == 0


def test_swap_back_to_pixels_restores_polydata_mapper(qtbot):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply(view, size_unit="meters")
    _apply(view, size_unit="pixels")
    assert isinstance(view._cloud_actor.GetMapper(), vtk.vtkPolyDataMapper)
    assert not isinstance(
        view._cloud_actor.GetMapper(), vtk.vtkPointGaussianMapper)


def test_pixel_mode_idempotent(qtbot):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply(view, size_unit="pixels", size=5.0)
    m1 = view._cloud_actor.GetMapper()
    _apply(view, size_unit="pixels", size=8.0)
    m2 = view._cloud_actor.GetMapper()
    assert m1 is m2  # same mapper instance — no recreation


def test_meter_mode_idempotent(qtbot):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply(view, size_unit="meters", size=0.5)
    m1 = view._cloud_actor.GetMapper()
    _apply(view, size_unit="meters", size=0.8)
    m2 = view._cloud_actor.GetMapper()
    assert m1 is m2
    assert m2.GetScaleFactor() == 0.8  # parameter updated in place
