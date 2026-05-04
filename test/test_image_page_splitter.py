"""ImagePage nested QSplitter layout building."""
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QSplitter

from pkrc_visualizer.display_settings import DisplaySettingsStore
from pkrc_visualizer.pages.image_page import ImagePage


class FakeRosClient(QObject):
    message_received = pyqtSignal(str, object)
    topics_changed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._cache: dict = {}
        self._tid_to_topic: dict[str, str] = {}
        self._tid_seq = 0

    def enable_discovery(self, msg_types):
        pass

    def subscribe_dynamic(self, name, msg_type):
        self._tid_seq += 1
        tid = f"dyn_{self._tid_seq}"
        self._tid_to_topic[tid] = name
        return tid

    def unsubscribe(self, tid):
        self._tid_to_topic.pop(tid, None)

    def latest(self, tid):
        return self._cache.get(tid)


def _make_page(qtbot, tmp_path):
    ros = FakeRosClient()
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    page = ImagePage(ros, store)
    qtbot.addWidget(page)
    return page


def test_2x2_layout_creates_nested_splitters(qtbot, tmp_path):
    page = _make_page(qtbot, tmp_path)
    page._toolbar.set_layout_value("2x2")
    for _ in range(4):
        page._add_panel()
    outer = page._splitter
    assert isinstance(outer, QSplitter)
    assert outer.orientation() == Qt.Vertical
    assert outer.count() == 2
    row0 = outer.widget(0)
    row1 = outer.widget(1)
    assert isinstance(row0, QSplitter)
    assert row0.orientation() == Qt.Horizontal
    assert row0.count() == 2
    assert row1.orientation() == Qt.Horizontal
    assert row1.count() == 2


def test_2x1_layout_creates_single_horizontal_splitter(qtbot, tmp_path):
    page = _make_page(qtbot, tmp_path)
    page._toolbar.set_layout_value("2x1")
    page._add_panel()
    page._add_panel()
    outer = page._splitter
    assert isinstance(outer, QSplitter)
    assert outer.orientation() == Qt.Horizontal
    assert outer.count() == 2


def test_1x1_layout_no_splitter(qtbot, tmp_path):
    page = _make_page(qtbot, tmp_path)
    page._toolbar.set_layout_value("1x1")
    page._add_panel()
    # 1x1 does not need a splitter — page._splitter is None.
    assert page._splitter is None


def test_3x2_layout_two_rows_three_columns(qtbot, tmp_path):
    page = _make_page(qtbot, tmp_path)
    page._toolbar.set_layout_value("3x2")
    for _ in range(6):
        page._add_panel()
    outer = page._splitter
    assert outer.orientation() == Qt.Vertical
    assert outer.count() == 2
    for i in range(2):
        row = outer.widget(i)
        assert isinstance(row, QSplitter)
        assert row.orientation() == Qt.Horizontal
        assert row.count() == 3
