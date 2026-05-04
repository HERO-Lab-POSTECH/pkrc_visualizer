"""ImagePanel: combo + view + close + Hz."""
import pytest
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


def test_panel_close_signal(qtbot):
    panel = ImagePanel()
    qtbot.addWidget(panel)
    spy = []
    panel.closed.connect(lambda: spy.append(1))
    panel._close_btn.click()
    assert spy == [1]
