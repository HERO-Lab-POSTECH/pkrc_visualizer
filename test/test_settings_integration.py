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
    panel = SettingsPanel(panel_tabs(True), parent=view)
    button = SettingsButton(view)
    button.clicked.connect(lambda: panel.toggle(button.geometry()))
    panel.field_changed.connect(
        lambda path, value: store.update("slam", path, value))
    store.changed.connect(
        lambda k, settings: view.apply_display_settings(settings))

    snapshot = store.get("slam")
    view.apply_display_settings(snapshot)
    panel.apply_values(snapshot)

    assert view._cloud_actor.GetProperty().GetPointSize() == 2.0

    # User drags the slider
    panel._widgets["cloud.size"].setValue(8.0)
    qtbot.wait(260)        # panel debounce 200 + buffer
    qtbot.wait(120)        # store debounce 50 + buffer

    assert view._cloud_actor.GetProperty().GetPointSize() == 8.0
    # Persisted on disk
    assert (tmp_path / "s.yaml").exists()


def test_reset_propagates_to_view(qtbot, tmp_path):
    view = PyVistaView()
    qtbot.addWidget(view)
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    panel = SettingsPanel(panel_tabs(True), parent=view)
    panel.field_changed.connect(
        lambda path, value: store.update("slam", path, value))
    panel.reset_requested.connect(
        lambda section: store.reset("slam", section=section))
    store.changed.connect(
        lambda k, s: (view.apply_display_settings(s), panel.apply_values(s)))

    panel.apply_values(store.get("slam"))
    panel._widgets["cloud.size"].setValue(15.0)
    qtbot.wait(260)
    qtbot.wait(120)
    assert view._cloud_actor.GetProperty().GetPointSize() == 15.0

    panel._tabs_widget.setCurrentIndex(1)   # cloud tab
    panel._reset_button.click()
    qtbot.wait(120)
    assert view._cloud_actor.GetProperty().GetPointSize() == 2.0
