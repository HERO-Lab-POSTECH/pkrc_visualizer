"""End-to-end migration: a real v0.4.0 yaml on disk loads cleanly into v0.5.0."""
from pathlib import Path

from pkrc_visualizer.display_settings import DisplaySettingsStore, load_yaml


V04_YAML = """\
image:
  background: '#1e1e1e'
  cloud:
    style: 'points'
    size: 2.0
    size_unit: 'meters'
  image:
    layout: '2x2'
    splitter_state: 'a,b;c,d;e,f'
    panels:
      - topic_name: '/cam/raw'
        msg_type: 'Image'
      - topic_name: '/cam/compressed'
        msg_type: 'CompressedImage'
"""


def test_v04_yaml_migrates(tmp_path: Path):
    p = tmp_path / "settings.yaml"
    p.write_text(V04_YAML)
    pages = load_yaml(p)
    img = pages["image"].image
    assert img.dock_state == ""                  # legacy state ignored
    assert len(img.panels) == 2
    assert img.panels[0].topic_name == "/cam/raw"
    assert img.panels[1].msg_type == "CompressedImage"
    # Legacy keys must not have leaked through:
    assert not hasattr(img, "layout")
    assert not hasattr(img, "splitter_state")


def test_store_migration_writes_back_clean_yaml(qtbot, tmp_path: Path):
    p = tmp_path / "settings.yaml"
    p.write_text(V04_YAML)
    store = DisplaySettingsStore(path=p, debounce_ms=10)
    img = store.get("image").image
    assert img.dock_state == ""
    # Force a write: update an unrelated field. qtbot.wait() drives the Qt
    # event loop so the debounced QTimer.timeout fires _flush -> save_yaml.
    store.update("image", "background", "#202020")
    qtbot.wait(60)
    fresh = p.read_text()
    assert "layout:" not in fresh
    assert "splitter_state:" not in fresh
    assert "dock_state:" in fresh
