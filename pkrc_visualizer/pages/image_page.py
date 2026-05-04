"""Image page: dynamic panel grid. v0.3.0."""
from typing import Optional

from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QWidget
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
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._toolbar)
        outer.addWidget(self._grid_widget, 1)

    def _wire_signals(self) -> None:
        self._toolbar.add_viewer_clicked.connect(self._add_panel)
        self._toolbar.layout_changed.connect(self._on_layout_changed)
        self._ros_client.topics_changed.connect(self._on_topics_changed)

    def _restore_from_store(self, layout: ImageLayoutSettings) -> None:
        self._toolbar.set_layout_value(layout.layout)
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
        for i in reversed(range(self._grid.count())):
            self._grid.takeAt(i)
        _rows, cols = LAYOUT_GRID.get(self._toolbar._layout_combo.currentText(), (2, 2))
        for idx, panel in enumerate(self._panels):
            r, c = divmod(idx, cols)
            self._grid.addWidget(panel, r, c)

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
        self._store.update(
            PAGE_KEY, "image",
            ImageLayoutSettings(
                layout=self._toolbar._layout_combo.currentText(),
                panels=panels,
            ))
