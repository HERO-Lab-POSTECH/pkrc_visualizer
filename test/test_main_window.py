"""MainWindow: hamburger toggle + menu click -> page switch smoke."""
from unittest.mock import MagicMock

import pytest

from pkrc_visualizer.display_settings import DisplaySettingsStore
from pkrc_visualizer.main_window import MainWindow, PAGE_TITLES


@pytest.fixture
def fake_ros_client():
    client = MagicMock()
    client.message_received = MagicMock()
    client.message_received.connect = MagicMock()
    return client


@pytest.fixture
def display_store(tmp_path):
    return DisplaySettingsStore(path=tmp_path / "s.yaml")


def test_main_window_starts_on_first_page(qtbot, fake_ros_client, display_store):
    window = MainWindow(fake_ros_client, display_store)
    qtbot.addWidget(window)
    assert window._stack.currentIndex() == 0


def test_menu_click_changes_page(qtbot, fake_ros_client, display_store):
    window = MainWindow(fake_ros_client, display_store)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    for i in range(len(PAGE_TITLES)):
        window._on_menu_clicked(i)
        assert window._stack.currentIndex() == i


def test_hamburger_toggle_shows_drawer(qtbot, fake_ros_client, display_store):
    window = MainWindow(fake_ros_client, display_store)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert not window._drawer.isVisible()
    window._menu_action.trigger()
    qtbot.wait(250)  # animation
    assert window._drawer.isVisible()
