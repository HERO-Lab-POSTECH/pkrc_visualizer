"""Pure-Python tests for the display-settings dataclasses + YAML codec."""
from pathlib import Path

import pytest
from PyQt5.QtTest import QSignalSpy

from pkrc_visualizer.display_settings import (
    CloudSettings, DisplaySettingsStore, FramesSettings,
    ImageLayoutSettings, ImagePanelSettings, PageDisplaySettings,
    load_yaml, save_yaml, settings_from_dict,
)


def test_dataclass_defaults():
    s = PageDisplaySettings()
    assert s.background == "#1e1e1e"
    assert s.frames.map_axes_length_m == 1.0
    assert s.cloud.color_transformer == "flat"
    assert s.cloud.decay_seconds == 30.0
    assert s.cloud.size_unit == "meters"


def test_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "slam": PageDisplaySettings(
            background="#000000",
            frames=FramesSettings(map_axes_length_m=2.5, label_font_size=24),
            cloud=CloudSettings(size=5.0, color_transformer="z", color_max=20.0),
        ),
        "mapping": PageDisplaySettings(),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["slam"].background == "#000000"
    assert loaded["slam"].frames.map_axes_length_m == 2.5
    assert loaded["slam"].frames.label_font_size == 24
    assert loaded["slam"].cloud.size == 5.0
    assert loaded["slam"].cloud.color_transformer == "z"
    assert loaded["slam"].cloud.color_max == 20.0
    assert loaded["mapping"] == PageDisplaySettings()


def test_corrupt_yaml_backed_up(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    path.write_text("not: valid: yaml: [\n")
    result = load_yaml(path)
    assert result == {}
    assert path.with_suffix(".yaml.bak").exists()
    assert not path.exists()


def test_missing_file_returns_empty(tmp_path: Path):
    result = load_yaml(tmp_path / "nope.yaml")
    assert result == {}


def test_unknown_yaml_keys_dropped(tmp_path: Path):
    # Forward-compat: a YAML written by a future version with extra fields
    # must not crash older readers — unknown fields fall back to defaults.
    path = tmp_path / "settings.yaml"
    path.write_text(
        "slam:\n"
        "  background: '#222222'\n"
        "  unknown_top_level: 42\n"
        "  frames:\n"
        "    map_axes_length_m: 3.0\n"
        "    future_field: 99\n"
        "  cloud:\n"
        "    size: 7.0\n"
        "    intensity_field_name: 'foo'\n"
    )
    loaded = load_yaml(path)
    assert loaded["slam"].background == "#222222"
    assert loaded["slam"].frames.map_axes_length_m == 3.0
    assert loaded["slam"].cloud.size == 7.0


def test_store_get_returns_default(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    s = store.get("slam")
    assert s == PageDisplaySettings()


def test_store_update_emits_changed(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    spy = QSignalSpy(store.changed)
    store.update("slam", "cloud.size", 7.0)
    assert len(spy) == 1
    assert store.get("slam").cloud.size == 7.0


def test_store_update_top_level_field(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    store.update("slam", "background", "#000000")
    assert store.get("slam").background == "#000000"


def test_store_debounces_yaml_write(tmp_path, qtbot):
    path = tmp_path / "s.yaml"
    store = DisplaySettingsStore(path=path, debounce_ms=100)
    store.update("slam", "cloud.size", 5.0)
    store.update("slam", "cloud.size", 6.0)
    store.update("slam", "cloud.size", 7.0)
    assert not path.exists()  # not flushed yet
    qtbot.wait(220)
    assert path.exists()
    assert load_yaml(path)["slam"].cloud.size == 7.0


def test_store_reset_section(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    store.update("slam", "cloud.size", 9.0)
    store.update("slam", "frames.label_font_size", 24)
    store.reset("slam", section="cloud")
    assert store.get("slam").cloud.size == 2.0  # default
    assert store.get("slam").frames.label_font_size == 24  # untouched


def test_store_unknown_path_raises(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml")
    with pytest.raises(KeyError):
        store.update("slam", "cloud.nope", 1)


def test_image_layout_panels_default():
    s = ImageLayoutSettings()
    assert s.panels == []


def test_image_dict_non_dict_falls_back_to_defaults():
    # YAML written as `image: bad_string` (or any non-dict) must not crash.
    s = settings_from_dict({"image": "bad_string"})
    assert s.image == ImageLayoutSettings()


def test_image_panels_non_dict_entries_skipped():
    # Forward-compat: future versions may emit non-dict entries — drop them.
    s = settings_from_dict({
        "image": {
            "panels": [
                {"topic_name": "/a", "msg_type": "Image"},
                "not_a_dict",
                42,
                {"topic_name": "/b", "msg_type": "CompressedImage"},
            ],
        },
    })
    assert [p.topic_name for p in s.image.panels] == ["/a", "/b"]


def test_image_key_absent_returns_default_image_layout():
    s = settings_from_dict({"frames": {"map_axes_length_m": 2.0}})
    assert s.image == ImageLayoutSettings()
    assert s.frames.map_axes_length_m == 2.0  # Other fields parse normally.


def test_cloud_decay_seconds_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "slam": PageDisplaySettings(
            cloud=CloudSettings(decay_seconds=12.5),
        ),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["slam"].cloud.decay_seconds == 12.5


def test_cloud_decay_max_points_legacy_key_silently_dropped(tmp_path: Path):
    # YAML written by v0.3.x had `decay_max_points`; v0.4.0 must silently
    # drop the unknown key and fall back to the new default.
    path = tmp_path / "settings.yaml"
    path.write_text(
        "slam:\n"
        "  cloud:\n"
        "    decay_max_points: 999999\n"
        "    size: 4.0\n"
    )
    loaded = load_yaml(path)
    assert loaded["slam"].cloud.decay_seconds == 30.0   # default, not 999999
    assert loaded["slam"].cloud.size == 4.0             # other fields parse fine


def test_cloud_size_unit_default():
    s = CloudSettings()
    assert s.size_unit == "meters"


def test_cloud_size_unit_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "slam": PageDisplaySettings(
            cloud=CloudSettings(size_unit="meters", size=0.5),
        ),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["slam"].cloud.size_unit == "meters"
    assert loaded["slam"].cloud.size == 0.5


def test_cloud_size_unit_unknown_value_passes_through():
    # The dataclass holds the string verbatim; PyVistaView treats anything
    # other than "meters" as "pixels" (Task 6). Codec must not coerce.
    s = settings_from_dict({"cloud": {"size_unit": "weird"}})
    assert s.cloud.size_unit == "weird"


def test_image_layout_settings_default_dock_state():
    s = PageDisplaySettings()
    assert s.image.dock_state == ""
    assert s.image.panels == []
    # Removed in v0.5.0:
    assert not hasattr(s.image, "layout")
    assert not hasattr(s.image, "splitter_state")


def test_image_dock_state_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "image": PageDisplaySettings(
            image=ImageLayoutSettings(
                dock_state="aGVsbG8=",  # arbitrary base64 ASCII
                panels=[ImagePanelSettings(topic_name="/foo", msg_type="Image")],
            ),
        ),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["image"].image.dock_state == "aGVsbG8="
    assert loaded["image"].image.panels[0].topic_name == "/foo"


def test_store_clamps_size_on_unit_toggle_pixels_to_meters(tmp_path, qtbot):
    """A 10 px size must become a sane 0.05 m the moment unit flips.

    The previous panel-side guard depended on two debounced widget
    signals delivered in the right order. This test pins the contract
    at the store layer: the moment size_unit changes to meters, the
    stored size must be unit-safe — atomically, before changed emits.
    """
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=10)
    store.update("slam", "cloud.size", 10.0)
    store.update("slam", "cloud.size_unit", "meters")
    cloud = store.get("slam").cloud
    assert cloud.size_unit == "meters"
    assert cloud.size == 0.05


def test_store_clamps_size_on_unit_toggle_meters_to_pixels(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=10)
    store.update("slam", "cloud.size", 0.05)
    store.update("slam", "cloud.size_unit", "pixels")
    cloud = store.get("slam").cloud
    assert cloud.size_unit == "pixels"
    assert cloud.size == 2.0


def test_store_keeps_safe_size_on_unit_toggle(tmp_path, qtbot):
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=10)
    store.update("slam", "cloud.size", 0.5)
    store.update("slam", "cloud.size_unit", "meters")
    cloud = store.get("slam").cloud
    assert cloud.size == 0.5         # already <= threshold


def test_image_legacy_keys_drop_silently(tmp_path: Path):
    # v0.4.0 yaml had layout + splitter_state. v0.5.0 must not crash.
    path = tmp_path / "settings.yaml"
    path.write_text(
        "image:\n"
        "  image:\n"
        "    layout: '2x2'\n"
        "    splitter_state: 'foo;bar'\n"
        "    panels:\n"
        "      - topic_name: '/legacy'\n"
        "        msg_type: 'Image'\n"
    )
    loaded = load_yaml(path)
    assert loaded["image"].image.dock_state == ""
    assert loaded["image"].image.panels[0].topic_name == "/legacy"
    # legacy keys must not have leaked through:
    assert not hasattr(loaded["image"].image, "layout")
    assert not hasattr(loaded["image"].image, "splitter_state")

