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
