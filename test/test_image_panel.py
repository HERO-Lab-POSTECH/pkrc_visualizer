"""ImagePanel: combo + view + close + Hz."""
import pytest
from PyQt5.QtWidgets import QLabel, QPushButton, QWidget
from sensor_msgs.msg import Image

from pkrc_visualizer.widgets.image_panel import ImagePanel


def test_panel_set_candidates(qtbot):
    panel = ImagePanel()
    qtbot.addWidget(panel)
    panel.set_topic_candidates(["/a", "/b"])
    items = [panel._combo.itemText(i) for i in range(panel._combo.count())]
    assert items == ["/a", "/b"]


def test_panel_topic_changed_signal(qtbot):
    panel = ImagePanel()
    qtbot.addWidget(panel)
    panel.set_topic_candidates(["/a"])
    spy = []
    panel.topic_changed.connect(lambda name: spy.append(name))
    panel._combo.setCurrentText("/a")
    assert spy == ["/a"]


def test_make_titlebar_contains_combo_hz_close(qtbot):
    from pkrc_visualizer.widgets.image_panel import ImagePanel
    from pkrc_visualizer.widgets.topic_combobox import TopicComboBox

    panel = ImagePanel()
    qtbot.addWidget(panel)

    closed = []
    titlebar = panel.make_titlebar(close_cb=lambda: closed.append(True))
    assert isinstance(titlebar, QWidget)

    # Combobox + Hz label + close button live in the titlebar.
    combos = titlebar.findChildren(TopicComboBox)
    labels = titlebar.findChildren(QLabel)
    buttons = titlebar.findChildren(QPushButton)
    assert len(combos) == 1
    assert any("Hz" in lab.text() for lab in labels)
    assert len(buttons) == 1

    # Clicking the titlebar close button invokes the callback.
    buttons[0].click()
    assert closed == [True]


def test_make_titlebar_topic_changed_still_propagates(qtbot):
    from pkrc_visualizer.widgets.image_panel import ImagePanel

    panel = ImagePanel()
    qtbot.addWidget(panel)
    received = []
    panel.topic_changed.connect(received.append)

    titlebar = panel.make_titlebar(close_cb=lambda: None)
    qtbot.addWidget(titlebar)
    panel.set_topic_candidates(["/cam/image"])
    panel._combo.setCurrentText("/cam/image")
    assert received == ["/cam/image"]


def test_image_panel_no_inline_header(qtbot):
    # v0.5.0: header lives only in the titlebar; the panel body is just
    # the ImageView (Hz label moves into the titlebar).
    from pkrc_visualizer.widgets.image_panel import ImagePanel
    panel = ImagePanel()
    qtbot.addWidget(panel)
    # No close button or combobox should be parented inline on the panel
    # itself — they only exist after make_titlebar() is called.
    assert not panel.findChildren(QPushButton)
