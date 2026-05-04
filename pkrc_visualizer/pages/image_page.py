"""Image page: dynamic panel grid with nested QSplitter support. v0.4.0."""
from typing import Optional

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import QGridLayout, QSplitter, QVBoxLayout, QWidget
from sensor_msgs.msg import CompressedImage, Image

from pkrc_visualizer.display_settings import (
    DisplaySettingsStore, ImageLayoutSettings, ImagePanelSettings,
)
from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.image_panel import ImagePanel
from pkrc_visualizer.widgets.image_toolbar import ImageToolbar


PAGE_KEY = "image"
LAYOUT_GRID = {
    "1x1": (1, 1), "2x1": (1, 2),
    "2x2": (2, 2), "3x2": (2, 3),
    "free": (2, 2),  # In free mode the grid still falls back to a 2x2 layout.
}
MSG_TYPE_MAP = {"Image": Image, "CompressedImage": CompressedImage}


class ImagePage(BasePage):
    def __init__(self, ros_client, display_store: DisplaySettingsStore, parent=None) -> None:
        super().__init__(ros_client, parent)
        self._store = display_store
        self._panels: list[ImagePanel] = []
        self._panel_topic_ids: dict[ImagePanel, Optional[str]] = {}
        self._topic_pool: list[str] = []

        self._build_ui()
        self._wire_signals()
        ros_client.enable_discovery([Image, CompressedImage])
        self._restore_from_store(display_store.get(PAGE_KEY).image)

    def _build_ui(self) -> None:
        self._toolbar = ImageToolbar()
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter: Optional[QSplitter] = None
        # Free-mode and 1x1 keep a grid widget around as a fallback.
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._toolbar)
        outer.addWidget(self._container, 1)

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        # Restore splitter positions after layout has been finalized.
        # setSizes() must run after the splitter is visible so the container
        # has assigned a real size to it; doing it here is reliable.
        self._restore_splitter_state()

    def _wire_signals(self) -> None:
        self._toolbar.add_viewer_clicked.connect(self._add_panel)
        self._toolbar.layout_changed.connect(self._on_layout_changed)
        self._ros_client.topics_changed.connect(self._on_topics_changed)

    def _restore_from_store(self, layout: ImageLayoutSettings) -> None:
        # Disconnect layout_changed while restoring to avoid a spurious reflow.
        self._toolbar.layout_changed.disconnect(self._on_layout_changed)
        self._toolbar.set_layout_value(layout.layout)
        self._toolbar.layout_changed.connect(self._on_layout_changed)
        for ps in layout.panels:
            panel = self._add_panel()
            if ps.topic_name:
                msg_type = MSG_TYPE_MAP.get(ps.msg_type, Image)
                tid = self._ros_client.subscribe_dynamic(ps.topic_name, msg_type)
                self._panel_topic_ids[panel] = tid
                panel._combo.blockSignals(True)
                panel._combo.set_candidates(
                    sorted(set(self._topic_pool + [ps.topic_name])))
                panel._combo.setCurrentText(ps.topic_name)
                panel._combo.blockSignals(False)
        self._reflow()

    def _is_my_topic(self, topic_id: str) -> bool:
        return any(tid == topic_id for tid in self._panel_topic_ids.values())

    def refresh(self) -> None:
        for panel, tid in self._panel_topic_ids.items():
            if tid is None:
                continue
            msg = self._latest.pop(tid, None)
            if msg is not None:
                panel.set_image_msg(msg)

    def _add_panel(self) -> ImagePanel:
        panel = ImagePanel()
        panel.set_topic_candidates(self._topic_pool)
        panel.topic_changed.connect(
            lambda name, p=panel: self._on_panel_topic_changed(p, name))
        panel.closed.connect(lambda p=panel: self._remove_panel(p))
        self._panels.append(panel)
        self._panel_topic_ids[panel] = None
        self._reflow()
        self._persist()
        return panel

    def _remove_panel(self, panel: ImagePanel) -> None:
        tid = self._panel_topic_ids.pop(panel, None)
        if tid is not None:
            self._ros_client.unsubscribe(tid)
        self._panels.remove(panel)
        panel.deleteLater()
        self._reflow()
        self._persist()

    def _on_panel_topic_changed(self, panel: ImagePanel, name: str) -> None:
        if name not in self._topic_pool:
            return
        # Drop the previous subscription, then subscribe to the new topic.
        old_tid = self._panel_topic_ids.get(panel)
        if old_tid is not None:
            self._ros_client.unsubscribe(old_tid)
        msg_type = self._infer_msg_type(name)
        tid = self._ros_client.subscribe_dynamic(name, msg_type)
        self._panel_topic_ids[panel] = tid
        self._persist()

    def _on_topics_changed(self, found: dict[str, str]) -> None:
        self._topic_pool = sorted(found.keys())
        for panel in self._panels:
            panel.set_topic_candidates(self._topic_pool)
        self._known_topic_types = found

    def _infer_msg_type(self, topic_name: str) -> type:
        type_str = getattr(self, "_known_topic_types", {}).get(topic_name, "")
        if "CompressedImage" in type_str:
            return CompressedImage
        return Image

    def _on_layout_changed(self, _value: str) -> None:
        self._reflow()
        self._persist()

    def _reflow(self) -> None:
        layout_id = self._toolbar._layout_combo.currentText()
        # Detach all panels from any current parent before re-parenting.
        for panel in self._panels:
            panel.setParent(None)
        self._teardown_container()
        if layout_id == "free" or layout_id == "1x1":
            self._reflow_into_grid(layout_id)
        else:
            self._reflow_into_splitter(layout_id)

    def _teardown_container(self) -> None:
        # Remove all children from container_layout so the next layout
        # builds fresh widgets without leaking.
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            w = item.widget()
            if w is not None and w is not self._grid_widget:
                w.setParent(None)
                w.deleteLater()
        self._splitter = None

    def _reflow_into_grid(self, layout_id: str) -> None:
        for i in reversed(range(self._grid.count())):
            self._grid.takeAt(i)
        _, cols = LAYOUT_GRID.get(layout_id, (2, 2))
        for idx, panel in enumerate(self._panels):
            r, c = divmod(idx, cols)
            self._grid.addWidget(panel, r, c)
        self._container_layout.addWidget(self._grid_widget)

    def _reflow_into_splitter(self, layout_id: str) -> None:
        rows, cols = LAYOUT_GRID.get(layout_id, (2, 2))
        if rows == 1:
            self._splitter = QSplitter(Qt.Horizontal)
            for panel in self._panels[:cols]:
                self._splitter.addWidget(panel)
        else:
            self._splitter = QSplitter(Qt.Vertical)
            for r in range(rows):
                row = QSplitter(Qt.Horizontal)
                start = r * cols
                for panel in self._panels[start:start + cols]:
                    row.addWidget(panel)
                self._splitter.addWidget(row)
        self._container_layout.addWidget(self._splitter)
        self._wire_splitter_signals(self._splitter)
        self._restore_splitter_state()

    def _wire_splitter_signals(self, splitter: QSplitter) -> None:
        splitter.splitterMoved.connect(
            lambda _pos, _idx: self._capture_splitter_state())
        for i in range(splitter.count()):
            child = splitter.widget(i)
            if isinstance(child, QSplitter):
                self._wire_splitter_signals(child)

    def _capture_splitter_state(self) -> None:
        if self._splitter is None:
            return
        # Store sizes as a comma-joined string so that _restore_splitter_state
        # can call setSizes() which is reliable across show/resize cycles.
        # We also keep a base64 saveState() copy for future use, but the
        # primary restore path reads the sizes list.
        sizes = self._splitter.sizes()
        state = ",".join(str(s) for s in sizes)
        layout = self._store.get(PAGE_KEY).image
        new_layout = ImageLayoutSettings(
            layout=layout.layout,
            panels=list(layout.panels),
            splitter_state=state,
        )
        self._store.update(PAGE_KEY, "image", new_layout)

    def _restore_splitter_state(self) -> None:
        if self._splitter is None:
            return
        state_str = self._store.get(PAGE_KEY).image.splitter_state
        if not state_str:
            return
        try:
            sizes = [int(s) for s in state_str.split(",")]
        except (ValueError, AttributeError):
            return
        if len(sizes) != self._splitter.count():
            return
        self._splitter.setSizes(sizes)

    def _persist(self) -> None:
        panels = []
        for panel in self._panels:
            tid = self._panel_topic_ids.get(panel)
            topic_name = ""
            msg_type = "Image"
            if tid is not None:
                topic_name = self._ros_client._tid_to_topic.get(tid, "")
                type_str = getattr(self, "_known_topic_types", {}).get(topic_name, "")
                msg_type = "CompressedImage" if "CompressedImage" in type_str else "Image"
            panels.append(ImagePanelSettings(
                topic_name=topic_name, msg_type=msg_type))
        new_layout_id = self._toolbar._layout_combo.currentText()
        old = self._store.get(PAGE_KEY).image
        # Layout id changed -> drop incompatible splitter state.
        keep_state = old.splitter_state if new_layout_id == old.layout else ""
        self._store.update(
            PAGE_KEY, "image",
            ImageLayoutSettings(
                layout=new_layout_id,
                panels=panels,
                splitter_state=keep_state,
            ))
