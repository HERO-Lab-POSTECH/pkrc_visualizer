"""MainWindow: 햄버거 토글 + 메뉴 클릭 → 페이지 전환 smoke."""
from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import Qt

from pkrc_visualizer.main_window import MainWindow, PAGE_TITLES


@pytest.fixture
def fake_ros_client():
    client = MagicMock()
    client.message_received = MagicMock()
    client.message_received.connect = MagicMock()
    return client


def test_main_window_starts_on_first_page(qtbot, fake_ros_client):
    window = MainWindow(fake_ros_client)
    qtbot.addWidget(window)
    assert window._stack.currentIndex() == 0


def test_menu_click_changes_page(qtbot, fake_ros_client):
    window = MainWindow(fake_ros_client)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    for i in range(len(PAGE_TITLES)):
        window._on_menu_clicked(i)
        assert window._stack.currentIndex() == i


def test_hamburger_toggle_shows_drawer(qtbot, fake_ros_client):
    window = MainWindow(fake_ros_client)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert not window._drawer.isVisible()
    qtbot.mouseClick(window._hamburger, Qt.LeftButton)
    qtbot.wait(250)  # animation
    assert window._drawer.isVisible()
