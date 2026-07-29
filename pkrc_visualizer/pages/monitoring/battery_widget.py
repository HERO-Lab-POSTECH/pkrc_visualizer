"""Battery panel — large percentage + gradient bar + voltage + status pill.

Color thresholds are voltage-based per Jetson reference (2026-05-07):
  v ≤ 12.5 V         → critical (red)
  12.5 < v ≤ 13.0 V  → low      (yellow)
  v > 13.0 V         → good     (green)

`power_supply_health=GOOD` alone cannot distinguish "low but not critical"
from "good", because the publisher only flips to DEAD at the critical
threshold. Use voltage as the primary signal; fall back to NaN handling
when CAN frames have not arrived yet.
"""
import math

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from sensor_msgs.msg import BatteryState

from pkrc_visualizer.pages.monitoring.common import (ACCENT_GREEN,
                                                       ACCENT_ORANGE,
                                                       ACCENT_RED, PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_DIM, TEXT_LABEL,
                                                       TEXT_PRIMARY, TITLE_QSS)

V_CRITICAL = 12.5
V_LOW = 13.0


def _color_for_voltage(v: float) -> QColor:
    if math.isnan(v):
        return QColor(TEXT_DIM)
    if v <= V_CRITICAL:
        return QColor(ACCENT_RED)
    if v <= V_LOW:
        return QColor(ACCENT_ORANGE)
    return QColor(ACCENT_GREEN)


def _status_for_voltage(v: float) -> tuple[str, str]:
    """(label, color) — for the status pill."""
    if math.isnan(v):
        return ("데이터 없음", TEXT_DIM)
    if v <= V_CRITICAL:
        return ("위험", ACCENT_RED)
    if v <= V_LOW:
        return ("낮음", ACCENT_ORANGE)
    return ("정상", ACCENT_GREEN)


class _GradientBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self._color = QColor(ACCENT_GREEN)
        self._enabled = True
        self.setMinimumHeight(8)
        self.setMaximumHeight(8)

    def set_state(self, pct: float, color: QColor, enabled: bool) -> None:
        self._pct = max(0.0, min(1.0, float(pct)))
        self._color = color
        self._enabled = enabled
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PANEL_BG_INNER))
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        if self._enabled and self._pct > 0:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, self._color.darker(110))
            grad.setColorAt(1.0, self._color.lighter(120))
            p.setBrush(grad)
            fill_w = max(int(w * self._pct), h)
            p.drawRoundedRect(0, 0, fill_w, h, h / 2, h / 2)


class BatteryWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(4)

        title = QLabel("🔋 배터리")
        title.setStyleSheet(TITLE_QSS)
        outer.addWidget(title, 0, Qt.AlignTop)

        self._pct_label = QLabel("—")
        self._pct_label.setAlignment(Qt.AlignCenter)
        self._pct_label.setStyleSheet(self._big_qss(TEXT_DIM))
        outer.addWidget(self._pct_label, 1)

        self._bar = _GradientBar()
        outer.addWidget(self._bar)

        bottom_row = QHBoxLayout()
        self._voltage_label = QLabel("— V")
        self._voltage_label.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 12px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        self._status_pill = QLabel("—")
        self._status_pill.setAlignment(Qt.AlignCenter)
        self._status_pill.setStyleSheet(self._pill_qss(TEXT_DIM))
        self._status_pill.setFixedHeight(20)
        bottom_row.addWidget(self._voltage_label, 1)
        bottom_row.addWidget(self._status_pill)
        outer.addLayout(bottom_row)

    @staticmethod
    def _pill_qss(color: str) -> str:
        return (
            f"color: white; background: {color}; border: none; "
            f"border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: bold;"
        )

    @staticmethod
    def _big_qss(color: str) -> str:
        return (
            f"color: {color}; font-size: 34px; font-weight: bold; "
            f"background: transparent; border: none;"
        )

    def update_from_msg(self, msg) -> None:
        v = msg.voltage
        pct = msg.percentage  # 0~1 fraction
        v_known = not math.isnan(v)
        pct_known = not math.isnan(pct)

        # Color is voltage-driven; if voltage missing, fall back to dim.
        color = _color_for_voltage(v)

        if pct_known:
            self._pct_label.setText(f"{pct * 100:.0f}%")
        else:
            self._pct_label.setText("—")
        self._pct_label.setStyleSheet(self._big_qss(color.name()))
        self._bar.set_state(pct if pct_known else 0.0, color, pct_known)

        self._voltage_label.setText(f"{v:.2f} V" if v_known else "— V")

        # Status pill follows voltage thresholds. Critical override: if the
        # health field is DEAD, force critical color even with stale voltage.
        if msg.power_supply_health == BatteryState.POWER_SUPPLY_HEALTH_DEAD:
            label, pill_color = ("위험", ACCENT_RED)
        else:
            label, pill_color = _status_for_voltage(v)
        self._status_pill.setText(label)
        self._status_pill.setStyleSheet(self._pill_qss(pill_color))
