"""Tests for the schema declarations driving SettingsPanel."""
from pkrc_visualizer.widgets.settings_schema import (
    background_schema, cloud_schema, frames_schema, panel_tabs,
)


def test_frames_schema_covers_all_dataclass_fields():
    paths = {f.path for f in frames_schema()}
    expected = {
        "frames.map_axes_length_m", "frames.map_axes_line_width",
        "frames.robot_axes_length_m", "frames.robot_axes_line_width",
        "frames.label_font_size",
        "frames.map_label_color", "frames.robot_label_color",
        "frames.show_map_frame", "frames.show_robot_frame",
    }
    assert paths == expected


def test_cloud_schema_with_decay():
    paths = {f.path for f in cloud_schema(include_decay=True)}
    assert "cloud.decay_seconds" in paths
    assert "cloud.style" in paths
    assert "cloud.size_unit" in paths
    assert "cloud.color_transformer" in paths


def test_cloud_schema_without_decay():
    paths = {f.path for f in cloud_schema(include_decay=False)}
    assert "cloud.decay_seconds" not in paths
    # size_unit stays in even when decay is disabled.
    assert "cloud.size_unit" in paths


def test_background_schema():
    fields = background_schema()
    assert len(fields) == 1
    assert fields[0].path == "background"
    assert fields[0].widget == "color"


def test_panel_tabs_returns_three_groups():
    tabs = panel_tabs(include_decay=True)
    ids = [t[0] for t in tabs]
    assert ids == ["frames", "cloud", "background"]


from PyQt5.QtCore import QRect
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QWidget

from pkrc_visualizer.widgets.settings_panel import SettingsPanel
from pkrc_visualizer.display_settings import PageDisplaySettings


def _make_panel(qtbot, include_decay=True):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    panel = SettingsPanel(panel_tabs(include_decay), parent=parent)
    return parent, panel


def test_panel_builds_widget_per_field(qtbot):
    _, panel = _make_panel(qtbot, include_decay=True)
    # frames(9) + cloud(9 with decay+size_unit) + background(1)
    assert len(panel._widgets) == 19
    assert "cloud.size_unit" in panel._widgets


def test_panel_omits_decay_when_disabled(qtbot):
    _, panel = _make_panel(qtbot, include_decay=False)
    assert "cloud.decay_seconds" not in panel._widgets
    assert "cloud.size_unit" in panel._widgets
    assert len(panel._widgets) == 18


def test_apply_values_syncs_widget_state(qtbot):
    _, panel = _make_panel(qtbot)
    page = PageDisplaySettings()
    page.cloud.size = 7.0
    page.frames.show_map_frame = False
    panel.apply_values(page)
    assert panel._widgets["cloud.size"].value() == 7.0
    assert panel._widgets["frames.show_map_frame"].isChecked() is False


def test_slider_change_emits_debounced_signal(qtbot):
    _, panel = _make_panel(qtbot)
    spy = QSignalSpy(panel.field_changed)
    panel._widgets["cloud.size"].setValue(10.0)
    panel._widgets["cloud.size"].setValue(11.0)
    panel._widgets["cloud.size"].setValue(12.0)
    qtbot.wait(260)  # > DEBOUNCE_MS (200)
    assert len(spy) == 1            # PyQt5 5.15: use len(spy), not spy.count()
    path, value = spy[0]
    assert path == "cloud.size"
    assert value == 12.0


def test_reset_button_emits_current_tab(qtbot):
    parent, panel = _make_panel(qtbot)
    panel._tabs_widget.setCurrentIndex(1)  # cloud
    spy = QSignalSpy(panel.reset_requested)
    panel._reset_button.click()
    assert len(spy) == 1
    assert spy[0][0] == "cloud"


def test_toggle_shows_and_hides(qtbot):
    parent, panel = _make_panel(qtbot)
    parent.show()
    qtbot.waitExposed(parent)
    assert not panel.isVisible()
    panel.toggle(QRect(8, 560, 32, 32))
    qtbot.waitUntil(lambda: panel.isVisible(), timeout=500)
    panel.toggle(QRect(8, 560, 32, 32))
    qtbot.waitUntil(lambda: not panel.isVisible(), timeout=500)


from pkrc_visualizer.widgets.settings_button import SettingsButton


def test_settings_button_anchors_bottom_right(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    btn = SettingsButton(parent)
    parent.show()
    qtbot.waitExposed(parent)
    assert btn.x() == 800 - 32 - 8      # width - BUTTON_SIZE - MARGIN_RIGHT
    assert btn.y() == 600 - 32 - 8      # height - BUTTON_SIZE - MARGIN_BOTTOM


def test_settings_button_repositions_on_parent_resize(qtbot):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    btn = SettingsButton(parent)
    parent.show()
    qtbot.waitExposed(parent)
    parent.resize(1000, 400)
    qtbot.wait(50)
    assert btn.y() == 400 - 32 - 8


def test_settings_button_emits_clicked(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    btn = SettingsButton(parent)
    spy = QSignalSpy(btn.clicked)
    btn.click()
    assert len(spy) == 1
