"""Relay states (UInt8 bitmask, bit0=CH1 .. bit2=CH3) — three labeled lamps.

Layout per channel (matches web GUI):
   [ ROUND LAMP ]
       label
       ON/OFF       (large)
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pkrc_visualizer.pages.monitoring.common import (ACCENT_GREEN, PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_DIM, TEXT_LABEL,
                                                       TEXT_PRIMARY, TITLE_QSS)

CHANNEL_NAMES = ("Relay 1", "Oculus", "MID360")


class _Lamp(QWidget):
    """Round lamp — green when ON, dark when OFF."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False
        self.setMinimumSize(28, 28)

    def set_on(self, on: bool) -> None:
        self._on = bool(on)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        d = min(w, h) - 4
        cx, cy = w / 2, h / 2
        # Lamp body — darker base ring so it stands out inside the slot card.
        p.setPen(QColor("#0a1525"))
        if self._on:
            p.setBrush(QColor(ACCENT_GREEN))
        else:
            p.setBrush(QColor("#0f1729"))
        p.drawEllipse(int(cx - d / 2), int(cy - d / 2), d, d)
        if self._on:
            # Inner highlight to suggest light
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 50))
            inner = int(d * 0.45)
            p.drawEllipse(int(cx - inner / 2), int(cy - inner / 2 - 2),
                          inner, inner)


class _RelaySlot(QFrame):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("RelaySlot")
        self.setStyleSheet(
            f"QFrame#RelaySlot {{ "
            f"background: {PANEL_BG_INNER}; "
            f"border: 1px solid {PANEL_BORDER}; "
            f"border-radius: 8px; "
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        self._lamp = _Lamp()
        layout.addWidget(self._lamp, 1, Qt.AlignHCenter)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 10px; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._label)

        self._state = QLabel("OFF")
        self._state.setAlignment(Qt.AlignCenter)
        self._state.setStyleSheet(self._state_qss(False))
        layout.addWidget(self._state)

    @staticmethod
    def _state_qss(on: bool) -> str:
        color = ACCENT_GREEN if on else TEXT_DIM
        return (
            f"color: {color}; font-size: 13px; font-weight: bold; "
            f"background: transparent; border: none; letter-spacing: 1px;"
        )

    def set_on(self, on: bool) -> None:
        self._lamp.set_on(on)
        self._state.setText("ON" if on else "OFF")
        self._state.setStyleSheet(self._state_qss(on))


class RelayLampsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(4)

        title = QLabel("⚡ 릴레이")
        title.setStyleSheet(TITLE_QSS)
        outer.addWidget(title, 0, Qt.AlignTop)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._slots = [_RelaySlot(name) for name in CHANNEL_NAMES]
        for slot in self._slots:
            row.addWidget(slot, 1)
        outer.addLayout(row, 1)

    def update_from_msg(self, msg) -> None:
        bitmask = int(msg.data) & 0xFF
        for i, slot in enumerate(self._slots):
            slot.set_on(bool(bitmask & (1 << i)))
