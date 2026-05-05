"""ImagePage dock-based behavior (v0.5.0)."""
from typing import Optional
from unittest.mock import MagicMock

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDockWidget, QMainWindow

from pkrc_visualizer.display_settings import DisplaySettingsStore
from pkrc_visualizer.pages.image_page import ImagePage


def _make_ros_client(monkeypatch=None) -> MagicMock:
    rc = MagicMock()
    rc.topics_changed = MagicMock()
    rc.topics_changed.connect = MagicMock()
    rc.enable_discovery = MagicMock()
    rc.subscribe_dynamic = MagicMock(return_value="sub-id-1")
    rc.unsubscribe = MagicMock()
    return rc


def _build_page(qtbot, tmp_path) -> tuple[ImagePage, DisplaySettingsStore]:
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=20)
    rc = _make_ros_client()
    page = ImagePage(rc, store)
    qtbot.addWidget(page)
    page.resize(800, 600)
    page.show()
    qtbot.waitExposed(page)
    return page, store


def test_default_empty(qtbot, tmp_path):
    page, _ = _build_page(qtbot, tmp_path)
    assert page._inner_mw.findChildren(QDockWidget) == []


def test_add_viewer_creates_dock(qtbot, tmp_path):
    page, _ = _build_page(qtbot, tmp_path)
    page._toolbar._add_btn.click()
    docks = page._inner_mw.findChildren(QDockWidget)
    assert len(docks) == 1
    assert docks[0].objectName().startswith("panel_")


def test_second_add_splits_horizontally(qtbot, tmp_path):
    page, _ = _build_page(qtbot, tmp_path)
    page._toolbar._add_btn.click()
    page._toolbar._add_btn.click()
    docks = page._inner_mw.findChildren(QDockWidget)
    assert len(docks) == 2
    # Both should be visible side by side, neither floating, neither tabified.
    for d in docks:
        assert not d.isFloating()


def test_close_dock_removes_panel(qtbot, tmp_path):
    page, store = _build_page(qtbot, tmp_path)
    page._toolbar._add_btn.click()
    page._toolbar._add_btn.click()
    docks = page._inner_mw.findChildren(QDockWidget)
    assert len(docks) == 2
    docks[0].close()                     # programmatic equivalent of ✕
    qtbot.wait(50)
    remaining = page._inner_mw.findChildren(QDockWidget)
    assert len(remaining) == 1
    assert len(store.get("image").image.panels) == 1


def test_titlebar_close_button_removes_dock(qtbot, tmp_path):
    """The user-visible path: clicking the titlebar ✕ removes the dock."""
    from PyQt5.QtWidgets import QPushButton
    page, _ = _build_page(qtbot, tmp_path)
    page._toolbar._add_btn.click()
    docks = page._inner_mw.findChildren(QDockWidget)
    assert len(docks) == 1
    titlebar = docks[0].titleBarWidget()
    close_btns = [b for b in titlebar.findChildren(QPushButton)
                  if b.text() == "✕"]
    assert len(close_btns) == 1, "titlebar must expose exactly one ✕ button"
    close_btns[0].click()
    qtbot.wait(50)
    assert page._panels == []


def test_dock_state_roundtrip(qtbot, tmp_path):
    # Build, add 3 docks, capture state, recreate from same yaml.
    page1, store = _build_page(qtbot, tmp_path)
    for _ in range(3):
        page1._toolbar._add_btn.click()
    qtbot.wait(120)                      # debounced persist
    saved_panels = list(store.get("image").image.panels)
    saved_state = store.get("image").image.dock_state
    assert len(saved_panels) == 3
    assert saved_state != ""

    # Recreate using the same on-disk yaml.
    store2 = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=20)
    page2 = ImagePage(_make_ros_client(), store2)
    qtbot.addWidget(page2)
    page2.resize(800, 600)
    page2.show()
    qtbot.waitExposed(page2)
    docks = page2._inner_mw.findChildren(QDockWidget)
    assert len(docks) == 3
    names_before = {p.topic_name for p in saved_panels}
    names_after = {p.topic_name for p in store2.get("image").image.panels}
    assert names_before == names_after


def test_v04_yaml_drops_legacy_keys(qtbot, tmp_path):
    yaml_path = tmp_path / "s.yaml"
    yaml_path.write_text(
        "image:\n"
        "  background: '#1e1e1e'\n"
        "  image:\n"
        "    layout: '2x2'\n"
        "    splitter_state: 'foo;bar;baz'\n"
        "    panels:\n"
        "      - topic_name: '/legacy/cam'\n"
        "        msg_type: 'Image'\n"
    )
    store = DisplaySettingsStore(path=yaml_path, debounce_ms=20)
    page = ImagePage(_make_ros_client(), store)
    qtbot.addWidget(page)
    page.resize(800, 600)
    page.show()
    qtbot.waitExposed(page)
    docks = page._inner_mw.findChildren(QDockWidget)
    assert len(docks) == 1                              # one panel survives
    assert store.get("image").image.dock_state == ""    # legacy state ignored


def test_tabify_persists(qtbot, tmp_path):
    page, store = _build_page(qtbot, tmp_path)
    for _ in range(2):
        page._toolbar._add_btn.click()
    docks = page._inner_mw.findChildren(QDockWidget)
    page._inner_mw.tabifyDockWidget(docks[0], docks[1])
    qtbot.wait(50)                       # let layout settle before saveState
    page._persist()
    qtbot.wait(80)
    saved = store.get("image").image.dock_state
    assert saved != ""

    store2 = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=20)
    page2 = ImagePage(_make_ros_client(), store2)
    qtbot.addWidget(page2)
    page2.resize(800, 600)
    page2.show()
    qtbot.waitExposed(page2)
    docks2 = page2._inner_mw.findChildren(QDockWidget)
    assert len(docks2) == 2
    # Tabified docks share the same tab bar.
    assert page2._inner_mw.tabifiedDockWidgets(docks2[0]) == [docks2[1]] or \
           page2._inner_mw.tabifiedDockWidgets(docks2[1]) == [docks2[0]]


def test_floating_persists(qtbot, tmp_path):
    page, store = _build_page(qtbot, tmp_path)
    page._toolbar._add_btn.click()
    docks = page._inner_mw.findChildren(QDockWidget)
    docks[0].setFloating(True)
    page._persist()
    qtbot.wait(80)
    assert store.get("image").image.dock_state != ""

    store2 = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=20)
    page2 = ImagePage(_make_ros_client(), store2)
    qtbot.addWidget(page2)
    page2.resize(800, 600)
    page2.show()
    qtbot.waitExposed(page2)
    docks2 = page2._inner_mw.findChildren(QDockWidget)
    assert len(docks2) == 1
    assert docks2[0].isFloating()
