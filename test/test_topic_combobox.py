"""TopicComboBox: candidate refresh + selection signal verification."""
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from pkrc_visualizer.widgets.topic_combobox import TopicComboBox


def test_set_candidates_populates_items(qtbot):
    cb = TopicComboBox()
    qtbot.addWidget(cb)
    cb.set_candidates(["/a", "/b", "/cam/raw"])
    items = [cb.itemText(i) for i in range(cb.count())]
    assert items == ["/a", "/b", "/cam/raw"]


def test_set_candidates_preserves_current_selection(qtbot):
    cb = TopicComboBox()
    qtbot.addWidget(cb)
    cb.set_candidates(["/a", "/b"])
    cb.setCurrentText("/b")
    cb.set_candidates(["/a", "/b", "/c"])  # /b is still present
    assert cb.currentText() == "/b"


def test_topic_selected_signal(qtbot):
    cb = TopicComboBox()
    qtbot.addWidget(cb)
    cb.set_candidates(["/a", "/b"])
    spy = []
    cb.topic_selected.connect(lambda name: spy.append(name))
    cb.setCurrentText("/b")
    assert spy == ["/b"]
