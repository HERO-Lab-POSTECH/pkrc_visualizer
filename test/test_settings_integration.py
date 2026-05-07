"""End-to-end: store ↔ panel ↔ view round-trip on a SLAM-like page."""
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from pkrc_visualizer.display_settings import DisplaySettingsStore
from pkrc_visualizer.widgets.pyvista_view import PyVistaView
from pkrc_visualizer.widgets.settings_button import SettingsButton
from pkrc_visualizer.widgets.settings_panel import SettingsPanel
from pkrc_visualizer.widgets.settings_schema import panel_tabs


def test_panel_change_propagates_to_view(qtbot, tmp_path):
    page = QWidget()
    page.resize(800, 600)
    qtbot.addWidget(page)
    view = PyVistaView()
    QVBoxLayout(page).addWidget(view)

    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    panel = SettingsPanel(panel_tabs(True, size_unit="pixels"), parent=view)
    button = SettingsButton(view)
    button.clicked.connect(lambda: panel.toggle(button.geometry()))
    panel.field_changed.connect(
        lambda path, value: store.update("slam", path, value))
    store.changed.connect(
        lambda k, settings: view.apply_display_settings(settings))

    # Force pixels mode so GetPointSize remains the source of truth (in
    # meters mode the actor uses vtkPointGaussianMapper.GetScaleFactor).
    store.update("slam", "cloud.size_unit", "pixels")
    snapshot = store.get("slam")
    view.apply_display_settings(snapshot)
    panel.apply_values(snapshot)

    assert view._cloud_actor.GetProperty().GetPointSize() == 1.0

    # User drags the slider
    panel._widgets["cloud.size_pixels"].setValue(8.0)
    qtbot.wait(260)        # panel debounce 200 + buffer
    qtbot.wait(120)        # store debounce 50 + buffer

    assert view._cloud_actor.GetProperty().GetPointSize() == 8.0
    # Persisted on disk
    assert (tmp_path / "s.yaml").exists()


def test_reset_propagates_to_view(qtbot, tmp_path):
    view = PyVistaView()
    qtbot.addWidget(view)
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    panel = SettingsPanel(panel_tabs(True, size_unit="pixels"), parent=view)
    panel.field_changed.connect(
        lambda path, value: store.update("slam", path, value))
    panel.reset_requested.connect(
        lambda section: store.reset("slam", section=section))
    store.changed.connect(
        lambda k, s: (view.apply_display_settings(s), panel.apply_values(s)))

    # Pin pixels mode so GetPointSize stays meaningful through reset.
    store.update("slam", "cloud.size_unit", "pixels")
    panel.apply_values(store.get("slam"))
    panel._widgets["cloud.size_pixels"].setValue(15.0)
    qtbot.wait(260)
    qtbot.wait(120)
    assert view._cloud_actor.GetProperty().GetPointSize() == 15.0

    panel._tabs_widget.setCurrentIndex(1)   # cloud tab
    # store.reset emits changed synchronously (no debounce on the signal —
    # only the disk write is debounced), so the property updates inside
    # the click() call. No qtbot.wait needed; the assertion guards future
    # regressions where reset accidentally becomes async.
    panel._reset_button.click()
    # Default is now size_unit=meters / size_meters=0.01, so the actor flips
    # to vtkPointGaussianMapper; verify ScaleFactor instead of GetPointSize.
    mapper = view._cloud_actor.GetMapper()
    assert mapper.GetScaleFactor() == 0.01


def test_cloud_size_unit_combobox_toggle_reaches_store(qtbot, tmp_path):
    """Regression: clicking pixels<->meters in the combobox must update the
    store (and via store.changed, the view + persisted YAML). Previously a
    bug where rebuild_cloud_tab killed the debounce timer before
    field_changed fired meant the toggle never reached the store.
    """
    view = PyVistaView()
    qtbot.addWidget(view)
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    panel = SettingsPanel(panel_tabs(True, size_unit="meters"), parent=view)
    panel.field_changed.connect(
        lambda path, value: store.update("slam", path, value))

    # Sync widgets with the store snapshot (defaults to size_unit="meters")
    # so the combobox starts on "meters" — matching the real install path.
    panel.apply_values(store.get("slam"))
    assert store.get("slam").cloud.size_unit == "meters"

    # User toggles the combobox to pixels.
    combo = panel._widgets["cloud.size_unit"]
    combo.setCurrentText("pixels")

    # Wait for panel debounce (200ms) + store debounce (50ms) + buffer.
    qtbot.wait(260)
    qtbot.wait(120)

    assert store.get("slam").cloud.size_unit == "pixels"
