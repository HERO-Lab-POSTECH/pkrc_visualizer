"""System state + LED color combo card."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pkrc_visualizer.pages.monitoring.common import (ACCENT_BLUE, ACCENT_GREEN,
                                                       ACCENT_RED, PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_LABEL, TEXT_PRIMARY,
                                                       TITLE_QSS)

_LED_COLOR_HEX = {
    "green":  "#10b981",
    "orange": "#f59e0b",
    "blue":   "#3b82f6",
    "red":    "#ef4444",
    "off":    "#1a2942",
    "white":  "#e2e8f0",
}


class _LedSwatch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = "off"
        self.setMinimumSize(20, 20)
        self.setMaximumHeight(20)

    def set_color(self, name: str) -> None:
        self._color = name
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        hex_ = _LED_COLOR_HEX.get(self._color, "#475569")
        p.setBrush(QColor(hex_))
        p.setPen(QColor(PANEL_BORDER))
        p.drawRoundedRect(0, 0, w - 1, h - 1, 10, 10)


class SystemLedWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(4)

        title = QLabel("⚙ 시스템")
        title.setStyleSheet(TITLE_QSS)
        outer.addWidget(title, 0, Qt.AlignTop)

        # ARMED pill
        self._arm_label = QLabel("—")
        self._arm_label.setAlignment(Qt.AlignCenter)
        self._arm_label.setFixedHeight(28)
        self._arm_label.setStyleSheet(self._pill_qss(TEXT_LABEL))
        outer.addWidget(self._arm_label)

        # Sensitivity + Lumen
        self._sens_label = QLabel("감도 —")
        self._sens_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 12px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        outer.addWidget(self._sens_label)

        self._lumen_label = QLabel("Lumen —")
        self._lumen_label.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 12px; "
            f"background: transparent; border: none;"
        )
        outer.addWidget(self._lumen_label)

        # LED row
        led_row = QHBoxLayout()
        led_row.setSpacing(4)
        self._led_swatch = _LedSwatch()
        self._led_label = QLabel("LED off")
        self._led_label.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 9px; "
            f"background: transparent; border: none;"
        )
        led_row.addWidget(self._led_swatch)
        led_row.addWidget(self._led_label, 1)
        outer.addLayout(led_row)

        self._armed = None
        self._sensitivity = None
        self._lumen = None

    @staticmethod
    def _pill_qss(color: str) -> str:
        return (
            f"color: white; background: {color}; border: none; "
            f"border-radius: 8px; font-size: 14px; font-weight: bold; letter-spacing: 1px;"
        )

    def update_system(self, msg) -> None:
        # Per Jetson reference (2026-05-07):
        #   data[0] = 0.0/1.0 armed flag
        #   data[1] = 0.1..1.0 sensitivity fraction (display as int(v*100)%)
        #   data[2] = 0.0..1.0 lumen brightness fraction (display as int(v*100)%)
        data = list(msg.data)
        if len(data) >= 3:
            self._armed = bool(round(data[0]))
            self._sensitivity = float(data[1])
            self._lumen = float(data[2])
            self._render()

    def update_led(self, msg) -> None:
        color = str(msg.data).lower()
        self._led_swatch.set_color(color)
        self._led_label.setText(f"LED {color}")

    def _render(self) -> None:
        if self._armed is None:
            self._arm_label.setText("—")
            self._arm_label.setStyleSheet(self._pill_qss(TEXT_LABEL))
        elif self._armed:
            self._arm_label.setText("ARMED")
            self._arm_label.setStyleSheet(self._pill_qss(ACCENT_GREEN))
        else:
            self._arm_label.setText("DISARMED")
            self._arm_label.setStyleSheet(self._pill_qss(ACCENT_RED))

        # round() avoids float-binary truncation: 0.7*100 == 69.9999... so
        # int() would render "69%". round() gives the operator the step
        # they actually pressed.
        if self._sensitivity is not None:
            self._sens_label.setText(f"감도 {round(self._sensitivity * 100)}%")
        if self._lumen is not None:
            self._lumen_label.setText(f"Lumen {round(self._lumen * 100)}%")
