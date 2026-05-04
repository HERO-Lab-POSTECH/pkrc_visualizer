"""Schema-driven settings panel that overlays a parent QWidget bottom-left."""
from typing import Any

from PyQt5.QtCore import (
    QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from pkrc_visualizer.widgets.settings_schema import FieldSpec


PANEL_WIDTH = 320
PANEL_MAX_HEIGHT = 520
ANIMATION_MS = 240
DEBOUNCE_MS = 200


class _ColorButton(QPushButton):
    color_picked = pyqtSignal(str)

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self._color = color_hex
        self.setFixedHeight(24)
        self.clicked.connect(self._open_dialog)
        self._refresh()

    def value(self) -> str:
        return self._color

    def setValue(self, color_hex: str) -> None:
        self._color = color_hex
        self._refresh()

    def _refresh(self) -> None:
        self.setStyleSheet(
            f"background:{self._color};color:#000;"
            "border:1px solid #555;border-radius:3px;"
        )
        self.setText(self._color)

    def _open_dialog(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Pick color")
        if c.isValid():
            self.setValue(c.name())
            self.color_picked.emit(c.name())


class SettingsPanel(QFrame):
    """Bottom-left overlay panel rendered from a schema.

    Emits `field_changed(path, value)` (debounced) when a widget value
    changes. Emits `reset_requested(tab_id)` when the Reset button is
    clicked on the currently visible tab.
    """

    field_changed = pyqtSignal(str, object)
    reset_requested = pyqtSignal(str)

    def __init__(self, tabs: list[tuple[str, str, list[FieldSpec]]], parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self.setStyleSheet(
            "#SettingsPanel { background:#2d2d30; border:1px solid #3e3e42; "
            "border-radius:6px; } "
            "QLabel { color:#f0f0f0; } "
            "QTabBar::tab { color:#f0f0f0; padding:6px 12px; } "
            "QTabBar::tab:selected { background:#094771; }"
        )
        self.hide()
        self._widgets: dict[str, QWidget] = {}
        self._latest_value: dict[str, Any] = {}
        self._debounce_timers: dict[str, QTimer] = {}
        self._tab_id_list: list[str] = [tid for tid, _, _ in tabs]
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(ANIMATION_MS)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._build_ui(tabs)

    # ---- public API -------------------------------------------------
    def apply_values(self, page) -> None:
        for path, widget in self._widgets.items():
            value = self._read_page_path(page, path)
            self._set_widget_value(widget, value)

    def toggle(self, anchor_rect: QRect) -> None:
        if self.isVisible():
            self.hide()
        else:
            self._show_at(anchor_rect)

    # ---- UI building ------------------------------------------------
    def _build_ui(self, tabs):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Display Properties</b>"))
        header.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        outer.addLayout(header)

        self._tabs_widget = QTabWidget()
        for tab_id, label, fields_ in tabs:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            inner = QWidget()
            form = QFormLayout(inner)
            for spec in fields_:
                w = self._make_widget(spec)
                self._widgets[spec.path] = w
                form.addRow(QLabel(spec.label), w)
            scroll.setWidget(inner)
            self._tabs_widget.addTab(scroll, label)
        outer.addWidget(self._tabs_widget)

        self._reset_button = QPushButton("Reset this tab to defaults")
        self._reset_button.clicked.connect(self._on_reset_clicked)
        outer.addWidget(self._reset_button)

    def _on_reset_clicked(self):
        idx = self._tabs_widget.currentIndex()
        self.reset_requested.emit(self._tab_id_list[idx])

    def _make_widget(self, spec: FieldSpec) -> QWidget:
        if spec.widget in ("slider", "spinbox_float"):
            w = QDoubleSpinBox()
            w.setRange(spec.options["min"], spec.options["max"])
            w.setSingleStep(spec.options.get("step", 0.1))
            w.valueChanged.connect(
                lambda v, p=spec.path: self._emit(p, float(v)))
            return w
        if spec.widget == "spinbox_int":
            w = QSpinBox()
            w.setRange(int(spec.options["min"]), int(spec.options["max"]))
            w.setSingleStep(int(spec.options.get("step", 1)))
            w.valueChanged.connect(
                lambda v, p=spec.path: self._emit(p, int(v)))
            return w
        if spec.widget == "color":
            w = _ColorButton("#000000")
            w.color_picked.connect(
                lambda c, p=spec.path: self._emit(p, c))
            return w
        if spec.widget == "checkbox":
            w = QCheckBox()
            w.toggled.connect(
                lambda v, p=spec.path: self._emit(p, bool(v)))
            return w
        if spec.widget == "combobox":
            w = QComboBox()
            for choice in spec.options["choices"]:
                w.addItem(choice)
            w.currentTextChanged.connect(
                lambda v, p=spec.path: self._emit(p, v))
            return w
        raise ValueError(f"unknown widget kind: {spec.widget}")

    # ---- value sync -------------------------------------------------
    @staticmethod
    def _read_page_path(page, path: str):
        obj = page
        for part in path.split("."):
            obj = getattr(obj, part)
        return obj

    @staticmethod
    def _set_widget_value(widget, value):
        widget.blockSignals(True)
        try:
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, _ColorButton):
                widget.setValue(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
        finally:
            widget.blockSignals(False)

    # ---- debounced emit --------------------------------------------
    def _emit(self, path: str, value):
        self._latest_value[path] = value
        timer = self._debounce_timers.get(path)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(DEBOUNCE_MS)
            timer.timeout.connect(
                lambda p=path: self.field_changed.emit(p, self._latest_value[p]))
            self._debounce_timers[path] = timer
        timer.start()

    # ---- show/hide animation --------------------------------------
    def _show_at(self, anchor_rect: QRect) -> None:
        parent_rect = self.parent().rect()
        target_w = PANEL_WIDTH
        target_h = max(0, min(PANEL_MAX_HEIGHT, parent_rect.height() - 16))
        if target_h == 0:
            return
        x = anchor_rect.x()
        y = max(8, anchor_rect.y() - target_h - 4)
        self.setGeometry(x, anchor_rect.y(), target_w, 0)
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(QRect(x, y, target_w, target_h))
        self._anim.start()
