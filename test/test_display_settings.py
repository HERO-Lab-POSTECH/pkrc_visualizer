"""Pure-Python tests for the display-settings dataclasses + YAML codec."""
from pathlib import Path

import pytest

from pkrc_visualizer.display_settings import (
    CloudSettings, FramesSettings, PageDisplaySettings,
    load_yaml, save_yaml,
)


def test_dataclass_defaults():
    s = PageDisplaySettings()
    assert s.background == "#1e1e1e"
    assert s.frames.map_axes_length_m == 1.0
    assert s.cloud.color_transformer == "flat"
    assert s.cloud.decay_max_points == 300_000


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


import pytest
from PyQt5.QtTest import QSignalSpy

from pkrc_visualizer.display_settings import DisplaySettingsStore, load_yaml


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


from pkrc_visualizer.display_settings import (
    ImageLayoutSettings, ImagePanelSettings,
)


def test_image_layout_defaults():
    s = ImageLayoutSettings()
    assert s.layout == "2x2"
    assert s.panels == []


def test_image_layout_yaml_roundtrip(tmp_path: Path):
    path = tmp_path / "settings.yaml"
    pages = {
        "image": PageDisplaySettings(
            image=ImageLayoutSettings(
                layout="3x2",
                panels=[
                    ImagePanelSettings(
                        topic_name="/cam/raw", msg_type="Image"),
                    ImagePanelSettings(
                        topic_name="/cam/compressed", msg_type="CompressedImage"),
                ],
            ),
        ),
    }
    save_yaml(path, pages)
    loaded = load_yaml(path)
    assert loaded["image"].image.layout == "3x2"
    assert len(loaded["image"].image.panels) == 2
    assert loaded["image"].image.panels[0].topic_name == "/cam/raw"
    assert loaded["image"].image.panels[1].msg_type == "CompressedImage"
