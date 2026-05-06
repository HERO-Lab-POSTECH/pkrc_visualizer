"""Common base for every page. Manages show/hide timers + RosClient signal wiring."""

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
        # Qt picks queued connection automatically (emit comes from another thread).
        self._ros_client.message_received.connect(
            self._on_message, type=Qt.QueuedConnection)

    def _on_message(self, topic_id: str, msg) -> None:
        if self._is_my_topic(topic_id):
            self._latest[topic_id] = msg

    # Subclasses override.
    def _is_my_topic(self, topic_id: str) -> bool:
        return False

    def refresh(self) -> None:
        """Subclasses override to refresh widgets."""

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
        include_prior_map: bool = False,
    ) -> None:
        """Hook a SettingsButton + SettingsPanel onto a 3D view.

        Applies the store's current values immediately. Wires field
        changes back into the store. Re-applies the snapshot to the view
        whenever the store emits. Rebuilds the cloud tab when the
        size_unit changes so the slider's path/range/label match the
        active unit.
        """
        snapshot = store.get(page_key)
        last_size_unit = snapshot.cloud.size_unit
        panel = SettingsPanel(
            panel_tabs(include_decay, last_size_unit,
                       include_prior_map=include_prior_map),
            parent=view,
        )
        button = SettingsButton(view)

        def _on_button_clicked():
            panel.toggle(button.geometry())
            # Spec §5: hide orientation widget while panel is visible
            view._orient_widget.SetEnabled(0 if panel.isVisible() else 1)

        def _on_store_changed(emitted_key, settings):
            if emitted_key != page_key:
                return
            view.apply_display_settings(settings)
            nonlocal last_size_unit
            new_unit = settings.cloud.size_unit
            if new_unit != last_size_unit:
                panel.rebuild_cloud_tab(new_unit)
                last_size_unit = new_unit
            panel.apply_values(settings)

        button.clicked.connect(_on_button_clicked)
        panel.field_changed.connect(
            lambda path, value: store.update(page_key, path, value))
        panel.reset_requested.connect(
            lambda section: store.reset(page_key, section=section))
        store.changed.connect(_on_store_changed)

        view.apply_display_settings(snapshot)
        panel.apply_values(snapshot)
