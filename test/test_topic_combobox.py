"""TopicComboBox: 후보 갱신 + 선택 시그널 검증."""
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
    cb.set_candidates(["/a", "/b", "/c"])  # /b 여전히 존재
    assert cb.currentText() == "/b"


def test_topic_selected_signal(qtbot):
    cb = TopicComboBox()
    qtbot.addWidget(cb)
    cb.set_candidates(["/a", "/b"])
    spy = []
    cb.topic_selected.connect(lambda name: spy.append(name))
    cb.setCurrentText("/b")
    assert spy == ["/b"]
