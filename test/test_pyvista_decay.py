"""Time-decay accumulator behaviour for PyVistaView."""
import numpy as np

from pkrc_visualizer.display_settings import PageDisplaySettings
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


def _apply_decay(view, seconds):
    s = PageDisplaySettings()
    s.cloud.decay_seconds = seconds
    view.apply_display_settings(s)


def test_decay_drops_chunks_older_than_window(qtbot, monkeypatch):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply_decay(view, 0.3)

    monkeypatch.setattr(
        "pkrc_visualizer.widgets.pyvista_view.monotonic", lambda: 10.0)
    view.append_cloud(np.array([[1, 2, 3]], dtype=np.float32))

    monkeypatch.setattr(
        "pkrc_visualizer.widgets.pyvista_view.monotonic", lambda: 10.5)
    view.append_cloud(np.array([[4, 5, 6]], dtype=np.float32))

    # First chunk is now 0.5 s old, > 0.3 s window — dropped.
    assert len(view._accum_chunks) == 1
    assert view._accum_chunks[0][1].tolist() == [[4.0, 5.0, 6.0]]


def test_decay_zero_disables_drop(qtbot, monkeypatch):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply_decay(view, 0.0)

    times = iter([10.0, 20.0, 30.0, 40.0, 50.0])
    monkeypatch.setattr(
        "pkrc_visualizer.widgets.pyvista_view.monotonic", lambda: next(times))
    for i in range(5):
        view.append_cloud(np.array([[i, i, i]], dtype=np.float32))
    assert len(view._accum_chunks) == 5


def test_safety_cap_drops_oldest_when_exceeded(qtbot, monkeypatch):
    view = PyVistaView()
    qtbot.addWidget(view)
    _apply_decay(view, 0.0)
    view.HARD_MAX_ACCUM_POINTS = 5  # tighten for the test

    monkeypatch.setattr(
        "pkrc_visualizer.widgets.pyvista_view.monotonic", lambda: 10.0)
    view.append_cloud(np.array([[1, 1, 1], [2, 2, 2]], dtype=np.float32))
    view.append_cloud(np.array([[3, 3, 3], [4, 4, 4]], dtype=np.float32))
    view.append_cloud(np.array([[5, 5, 5], [6, 6, 6]], dtype=np.float32))

    total = sum(arr.shape[0] for _, arr in view._accum_chunks)
    assert total <= 5
    last_arr = view._accum_chunks[-1][1]
    assert last_arr.tolist() == [[5.0, 5.0, 5.0], [6.0, 6.0, 6.0]]
