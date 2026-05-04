"""모든 페이지의 공통 상위. show/hide 시 timer 제어 + RosClient 시그널 연결."""

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QWidget

from pkrc_visualizer.display_settings import DisplaySettingsStore
from pkrc_visualizer.widgets.pyvista_view import PyVistaView
from pkrc_visualizer.widgets.settings_button import SettingsButton
from pkrc_visualizer.widgets.settings_panel import SettingsPanel
from pkrc_visualizer.widgets.settings_schema import panel_tabs


REFRESH_INTERVAL_MS = 100  # 10 Hz


class BasePage(QWidget):
    def __init__(self, ros_client, parent=None):
        super().__init__(parent)
        self._ros_client = ros_client
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh)
        self._latest: dict[str, object] = {}
        self._connect_signals()

    def _connect_signals(self) -> None:
        # Qt가 자동으로 queued connection 사용 (다른 스레드 emit)
        self._ros_client.message_received.connect(
            self._on_message, type=Qt.QueuedConnection)

    def _on_message(self, topic_id: str, msg) -> None:
        if self._is_my_topic(topic_id):
            self._latest[topic_id] = msg

    # 서브클래스가 override
    def _is_my_topic(self, topic_id: str) -> bool:
        return False

    def refresh(self) -> None:
        """서브클래스가 override — 위젯 갱신."""

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _install_settings_panel(
        self,
        view: PyVistaView,
        page_key: str,
        store: DisplaySettingsStore,
        include_decay: bool,
    ) -> None:
        """Hook a SettingsButton + SettingsPanel onto a 3D view.

        Applies the store's current values immediately. Wires field
        changes back into the store. Re-applies the snapshot to the view
        whenever the store emits.
        """
        panel = SettingsPanel(panel_tabs(include_decay), parent=view)
        button = SettingsButton(view)

        def _on_button_clicked():
            panel.toggle(button.geometry())
            # Spec §5: hide orientation widget while panel is visible
            view._orient_widget.SetEnabled(0 if panel.isVisible() else 1)

        def _on_store_changed(emitted_key, settings):
            if emitted_key != page_key:
                return
            view.apply_display_settings(settings)
            panel.apply_values(settings)

        button.clicked.connect(_on_button_clicked)
        panel.field_changed.connect(
            lambda path, value: store.update(page_key, path, value))
        panel.reset_requested.connect(
            lambda section: store.reset(page_key, section=section))
        store.changed.connect(_on_store_changed)

        snapshot = store.get(page_key)
        view.apply_display_settings(snapshot)
        panel.apply_values(snapshot)
