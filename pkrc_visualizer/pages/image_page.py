"""ImagePage v0.5.0: rqt-style QDockWidget layout.

ImagePage hosts an inner QMainWindow inside a QWidget so we can use
QDockWidget's drag/dock/tabify/float behavior without making the whole
visualizer page a QMainWindow.
"""
from __future__ import annotations
import base64
import uuid
from typing import Optional

from PyQt5.QtCore import QByteArray, QEvent, QObject, Qt, QTimer
from PyQt5.QtWidgets import QDockWidget, QMainWindow, QVBoxLayout, QWidget
from sensor_msgs.msg import CompressedImage, Image

from pkrc_visualizer.display_settings import (
    DisplaySettingsStore, ImageLayoutSettings, ImagePanelSettings,
)
from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.image_panel import ImagePanel
from pkrc_visualizer.widgets.image_toolbar import ImageToolbar


PAGE_KEY = "image"
MSG_TYPE_MAP = {"Image": Image, "CompressedImage": CompressedImage}
DOCK_FEATURES = (
    QDockWidget.DockWidgetMovable
    | QDockWidget.DockWidgetFloatable
    | QDockWidget.DockWidgetClosable
)


class _DockCloseFilter(QObject):
    """Event filter installed on QDockWidget to intercept close events."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def eventFilter(self, obj, event: QEvent) -> bool:
        if event.type() == QEvent.Close:
            self._callback()
            return True  # consume the event
        return False


def _new_object_name() -> str:
    return "panel_" + uuid.uuid4().hex


def _encode_state(state: QByteArray) -> str:
    return base64.b64encode(bytes(state)).decode("ascii")


def _decode_state(s: str) -> Optional[QByteArray]:
    if not s:
        return None
    try:
        return QByteArray(base64.b64decode(s.encode("ascii")))
    except (ValueError, UnicodeError):
        return None


class ImagePage(BasePage):
    def __init__(self, ros_client, display_store: DisplaySettingsStore,
                 parent=None) -> None:
        super().__init__(ros_client, parent)
        self._store = display_store
        self._panels: list[tuple[QDockWidget, ImagePanel]] = []
        self._panel_topic_ids: dict[ImagePanel, Optional[str]] = {}
        self._topic_pool: list[str] = []
        self._restored: bool = False
        self._restoring: bool = False

        self._build_ui()
        self._wire_signals()
        ros_client.enable_discovery([Image, CompressedImage])

    def _build_ui(self) -> None:
        self._toolbar = ImageToolbar()
        self._inner_mw = QMainWindow()
        self._inner_mw.setCentralWidget(QWidget())
        self._inner_mw.centralWidget().hide()
        self._inner_mw.setDockNestingEnabled(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._toolbar)
        outer.addWidget(self._inner_mw, 1)

    def _wire_signals(self) -> None:
        self._toolbar.add_viewer_clicked.connect(self._on_add_viewer)
        self._ros_client.topics_changed.connect(self._on_topics_changed)

    # ---- showEvent: restore on first visibility ---------------------------
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        if not self._restored:
            self._restore_from_store(self._store.get(PAGE_KEY).image)
            self._restored = True

    # ---- restore ----------------------------------------------------------
    def _restore_from_store(self, settings: ImageLayoutSettings) -> None:
        # Recreate panels first so QMainWindow.restoreState can match them
        # by objectName. Guard _restoring to prevent any _persist calls.
        self._restoring = True
        for ps in settings.panels:
            self._spawn_panel(ps, persist=False)
        state = _decode_state(settings.dock_state)
        if state is not None:
            self._inner_mw.restoreState(state)
        self._restoring = False

    # ---- add / spawn ------------------------------------------------------
    def _on_add_viewer(self) -> None:
        ps = ImagePanelSettings()
        self._spawn_panel(ps, persist=True)

    def _spawn_panel(self, ps: ImagePanelSettings, persist: bool) -> None:
        panel = ImagePanel()
        panel.set_topic_candidates(self._topic_pool)
        panel.topic_changed.connect(
            lambda topic, p=panel: self._on_panel_topic(p, topic))

        dock = QDockWidget()
        dock.setObjectName(_new_object_name())
        dock.setFeatures(DOCK_FEATURES)
        dock.setWidget(panel)
        close_cb = lambda d=dock, p=panel: self._remove_dock(d, p)
        dock.setTitleBarWidget(panel.make_titlebar(close_cb=close_cb))
        # Install event filter to catch dock.close() in addition to titlebar ✕.
        _filter = _DockCloseFilter(close_cb, parent=dock)
        dock.installEventFilter(_filter)
        dock.dockLocationChanged.connect(self._persist)

        if self._panels:
            prev_dock = self._panels[-1][0]
            self._inner_mw.splitDockWidget(prev_dock, dock, Qt.Horizontal)
        else:
            self._inner_mw.addDockWidget(Qt.RightDockWidgetArea, dock)

        self._panels.append((dock, panel))
        self._panel_topic_ids[panel] = None
        if ps.topic_name:
            panel._combo.setCurrentText(ps.topic_name)
        if persist:
            self._persist()

    # ---- close ------------------------------------------------------------
    def _remove_dock(self, dock: QDockWidget, panel: ImagePanel) -> None:
        """Called by titlebar ✕ button. Removes the dock unconditionally."""
        if dock not in [d for d, _ in self._panels]:
            return
        sub_id = self._panel_topic_ids.pop(panel, None)
        if sub_id:
            self._ros_client.unsubscribe(sub_id)
        self._panels = [(d, p) for d, p in self._panels if d is not dock]
        self._inner_mw.removeDockWidget(dock)
        dock.setParent(None)
        dock.deleteLater()
        self._persist()

    def _schedule_close_check(self, dock: QDockWidget, panel: ImagePanel,
                              visible: bool) -> None:
        """Handle visibilityChanged for floating-dock close fallback."""
        if visible:
            return
        QTimer.singleShot(0, lambda: self._on_dock_visibility(dock, panel))

    def _on_dock_visibility(self, dock: QDockWidget, panel: ImagePanel) -> None:
        """Fallback close handler for when the dock window (floating) is dismissed."""
        if dock.isVisible() or not dock.isFloating():
            return
        self._remove_dock(dock, panel)

    # ---- topic pool / subscription ----------------------------------------
    def _on_topics_changed(self, names) -> None:
        if isinstance(names, dict):
            self._topic_pool = sorted(names.keys())
        else:
            self._topic_pool = list(names)
        for _, p in self._panels:
            p.set_topic_candidates(self._topic_pool)

    def _on_panel_topic(self, panel: ImagePanel, topic: str) -> None:
        sub_id = self._panel_topic_ids.get(panel)
        if sub_id:
            self._ros_client.unsubscribe(sub_id)
        new_id = self._ros_client.subscribe_dynamic(
            topic, MSG_TYPE_MAP.get("Image", Image))
        self._panel_topic_ids[panel] = new_id
        self._persist()

    # ---- persist ----------------------------------------------------------
    def _persist(self, *_args) -> None:
        if self._restoring:
            return
        snapshot = ImageLayoutSettings(
            panels=[
                ImagePanelSettings(topic_name=p.current_topic(), msg_type="Image")
                for _, p in self._panels
            ],
            dock_state=_encode_state(self._inner_mw.saveState()),
        )
        self._store.update(PAGE_KEY, "image", snapshot)

    # ---- message handling -------------------------------------------------
    def _is_my_topic(self, topic_id: str) -> bool:
        return any(tid == topic_id for tid in self._panel_topic_ids.values())

    def refresh(self) -> None:
        for panel, tid in self._panel_topic_ids.items():
            if tid is None:
                continue
            msg = self._latest.pop(tid, None)
            if msg is not None:
                panel.set_image_msg(msg)
