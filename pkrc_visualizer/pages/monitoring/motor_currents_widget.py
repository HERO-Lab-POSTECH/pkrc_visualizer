"""4-channel motor currents — 4 separate cards in cross/plus layout.

Each card shows a channel label, a big numeric readout, and a center-anchored
bidirectional bar:

    ┌─ 앞 (VESC 4) ───────────┐
    │       +2.50 A           │
    │   [────|████──────]     │   bar grows right for fwd, left for rev
    └─────────────────────────┘

Cross arrangement matches the physical motor placement (top down view):
       VESC4 (front)
              ▲
              │
   VESC3 ◀───■───▶ VESC1
              │
              ▼
       VESC2 (rear)

msg.data ordering = [VESC1, VESC2, VESC3, VESC4]. Display range ±8A.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (QFrame, QGridLayout, QLabel, QSizePolicy,
                              QVBoxLayout, QWidget)

from pkrc_visualizer.pages.monitoring.common import (ACCENT_BLUE, ACCENT_RED,
                                                       PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_LABEL, TEXT_PRIMARY,
                                                       TITLE_QSS)

MAX_DISPLAY_A = 8.0
WARN_THRESHOLD_A = 6.0


class _BidirBar(QWidget):
    """Center-anchored bar: positive → right, negative → left, scale ±MAX."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.setMinimumHeight(8)
        self.setMaximumHeight(8)

    def set_value(self, v: float) -> None:
        self._value = float(v)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        # Track
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0a1525"))
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        # Center tick
        cx = w / 2
        p.setBrush(QColor(PANEL_BORDER))
        p.drawRect(int(cx - 1), 0, 2, h)
        # Active fill
        ratio = max(-1.0, min(1.0, self._value / MAX_DISPLAY_A))
        warn = abs(self._value) > WARN_THRESHOLD_A
        color = QColor(ACCENT_RED) if warn else QColor(ACCENT_BLUE)
        p.setBrush(color)
        if ratio > 0:
            fill_w = int(ratio * (w / 2 - 2))
            p.drawRoundedRect(int(cx), 1, fill_w, h - 2, h / 2, h / 2)
        elif ratio < 0:
            fill_w = int(-ratio * (w / 2 - 2))
            p.drawRoundedRect(int(cx) - fill_w, 1, fill_w, h - 2, h / 2, h / 2)


class _MotorCard(QFrame):
    """One motor channel card."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MotorCard")
        self.setStyleSheet(
            f"QFrame#MotorCard {{ "
            f"background: {PANEL_BG_INNER}; "
            f"border: 1px solid {PANEL_BORDER}; "
            f"border-radius: 8px; "
            f"}}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self._label = QLabel(label)
        self._label.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 10px; font-weight: bold; "
            f"background: transparent; border: none; letter-spacing: 0.5px;"
        )
        layout.addWidget(self._label)

        self._value = QLabel("0.00 A")
        self._value.setAlignment(Qt.AlignCenter)
        self._value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 16px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._value, 1)

        self._bar = _BidirBar()
        layout.addWidget(self._bar)

    def set_value(self, v: float) -> None:
        warn = abs(v) > WARN_THRESHOLD_A
        color = ACCENT_RED if warn else ACCENT_BLUE
        # Avoid the cosmetic "+0.00" — render plain "0.00 A" at zero.
        self._value.setText(f"{v:+.2f} A".replace("+0.00", "0.00"))
        self._value.setStyleSheet(
            f"color: {color}; font-size: 16px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        self._bar.set_value(v)


class _CenterDot(QWidget):
    """Small center marker — visual anchor for the cross."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TEXT_LABEL))
        p.drawEllipse(int(cx - 3), int(cy - 3), 6, 6)


class MotorCurrentsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(4)

        title = QLabel("⚙ 모터 (4WD · ±8A)")
        title.setStyleSheet(TITLE_QSS)
        outer.addWidget(title, 0, Qt.AlignTop)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        self._top = _MotorCard("앞 (VESC 4)")
        self._left = _MotorCard("좌 (VESC 3)")
        self._right = _MotorCard("우 (VESC 1)")
        self._bottom = _MotorCard("뒤 (VESC 2)")

        grid.addWidget(self._top,    0, 1)
        grid.addWidget(self._left,   1, 0)
        grid.addWidget(_CenterDot(), 1, 1)
        grid.addWidget(self._right,  1, 2)
        grid.addWidget(self._bottom, 2, 1)

        for c in range(3):
            grid.setColumnStretch(c, 1)
        for r in range(3):
            grid.setRowStretch(r, 1)

        outer.addLayout(grid, 1)

    def update_from_msg(self, msg) -> None:
        d = list(msg.data) + [0.0] * 4
        # msg.data[0..3] = VESC1..VESC4
        self._right.set_value(d[0])
        self._bottom.set_value(d[1])
        self._left.set_value(d[2])
        self._top.set_value(d[3])
