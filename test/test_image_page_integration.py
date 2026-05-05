"""End-to-end: topics_changed -> panel candidate refresh + add panel -> store persist."""
from PyQt5.QtCore import pyqtSignal, QObject

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
        tid = f"dyn_{self._tid_seq}_{name.strip('/').replace('/', '_')}"
        self._tid_to_topic[tid] = name
        return tid

    def unsubscribe(self, tid):
        self._tid_to_topic.pop(tid, None)

    def latest(self, tid):
        return self._cache.get(tid)


def test_topics_changed_propagates_to_panels(qtbot, tmp_path):
    ros = FakeRosClient()
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    page = ImagePage(ros, store)
    qtbot.addWidget(page)

    # Add one panel.
    page._add_panel()
    qtbot.wait(20)
    assert len(page._panels) == 1
    assert page._panels[0]._combo.count() == 0  # Pool is empty.

    # Simulate topic discovery.
    ros.topics_changed.emit({
        "/cam/raw": "sensor_msgs/msg/Image",
        "/cam/jpg": "sensor_msgs/msg/CompressedImage",
    })
    qtbot.wait(20)
    items = [page._panels[0]._combo.itemText(i)
             for i in range(page._panels[0]._combo.count())]
    assert sorted(items) == ["/cam/jpg", "/cam/raw"]


def test_add_panel_persists_to_store(qtbot, tmp_path):
    ros = FakeRosClient()
    store = DisplaySettingsStore(path=tmp_path / "s.yaml", debounce_ms=50)
    page = ImagePage(ros, store)
    qtbot.addWidget(page)
    page._add_panel()
    qtbot.wait(120)   # store debounce flush
    assert (tmp_path / "s.yaml").exists()
    snap = store.get("image")
    assert len(snap.image.panels) == 1
