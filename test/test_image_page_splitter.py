"""ImagePage nested QSplitter layout building."""
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QSplitter

from pkrc_visualizer.display_settings import (
    DisplaySettingsStore, ImageLayoutSettings, ImagePanelSettings, PageDisplaySettings,
)
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


def test_splitter_state_persists_to_store_on_resize(qtbot, tmp_path):
    page = _make_page(qtbot, tmp_path)
    page._toolbar.set_layout_value("2x1")
    page._add_panel()
    page._add_panel()
    qtbot.wait(60)  # debounce flush

    # Simulate user-driven splitter movement by writing sizes directly.
    page._splitter.setSizes([200, 600])
    page._capture_splitter_state()
    qtbot.wait(120)
    snap = page._store.get("image")
    assert snap.image.splitter_state != ""


def test_splitter_state_restored_on_page_rebuild(qtbot, tmp_path):
    # Pre-seed the store with a strongly asymmetric splitter state.
    # The state string format is "size0,size1,..." matching _capture_splitter_state.
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    # Make the page wide enough so both panels can satisfy their minimumSizeHint
    # (330 px each) while still leaving room for a clear asymmetry.
    # 400 vs 1200 → ratio ≈ 0.25; both are well above the 330-px minimum.
    state_str = "400,1200"

    store._pages["image"] = PageDisplaySettings(
        image=ImageLayoutSettings(
            layout="2x1",
            panels=[ImagePanelSettings(), ImagePanelSettings()],
            splitter_state=state_str,
        ),
    )

    ros = FakeRosClient()
    page = ImagePage(ros, store)
    # Make the page wide enough for the stored sizes to be respected.
    page.resize(1800, 600)
    qtbot.addWidget(page)
    page.show()
    qtbot.wait(60)
    assert page._splitter is not None
    sizes = page._splitter.sizes()
    total = sum(sizes) or 1
    ratio = sizes[0] / total
    # The first panel must be clearly smaller than the second (ratio < 0.4).
    assert ratio < 0.4, (
        f"Expected asymmetric split (ratio<0.4), got {ratio:.2f} from sizes {sizes}"
    )


def test_splitter_state_dropped_on_layout_change(qtbot, tmp_path):
    page = _make_page(qtbot, tmp_path)
    page._toolbar.set_layout_value("2x1")
    page._add_panel()
    page._add_panel()
    page._splitter.setSizes([100, 700])
    page._capture_splitter_state()
    qtbot.wait(120)
    assert page._store.get("image").image.splitter_state != ""

    # Change layout — old state must be cleared (its byte shape is
    # incompatible with the new splitter tree).
    page._toolbar.set_layout_value("2x2")
    qtbot.wait(120)
    assert page._store.get("image").image.splitter_state == ""
