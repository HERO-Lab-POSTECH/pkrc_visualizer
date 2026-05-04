"""Tests for the schema declarations driving SettingsPanel."""
from pkrc_visualizer.widgets.settings_schema import (
    FieldSpec, background_schema, cloud_schema, frames_schema, panel_tabs,
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
    assert "cloud.decay_max_points" in paths
    assert "cloud.style" in paths
    assert "cloud.color_transformer" in paths


def test_cloud_schema_without_decay():
    paths = {f.path for f in cloud_schema(include_decay=False)}
    assert "cloud.decay_max_points" not in paths


def test_background_schema():
    fields = background_schema()
    assert len(fields) == 1
    assert fields[0].path == "background"
    assert fields[0].widget == "color"


def test_panel_tabs_returns_three_groups():
    tabs = panel_tabs(include_decay=True)
    ids = [t[0] for t in tabs]
    assert ids == ["frames", "cloud", "background"]
