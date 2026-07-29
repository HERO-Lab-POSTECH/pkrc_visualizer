"""Joystick (sensor_msgs/Joy) — two circular gauges.

Visual: classic round joystick gauges with crosshair + dot.
Movement constraints:
  - Left stick:  fwd/back OR left/right only (no diagonals). Whichever
                 axis has the larger absolute value wins.
  - Right stick: horizontal (yaw) only. Y is forced to 0.
  - Both X axes inverted to match the operator's view.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pkrc_visualizer.pages.monitoring.common import (ACCENT_BLUE, ACCENT_CYAN,
                                                       PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_LABEL, TEXT_PRIMARY,
                                                       TITLE_QSS)


class _Stick(QWidget):
    """Round gauge — outline + crosshair + dot at (x, y) ∈ [-1, 1]²."""

    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self._x = 0.0
        self._y = 0.0
        self._label = label
        self._color = color
        self.setMinimumSize(60, 60)

    def set_xy(self, x: float, y: float) -> None:
        self._x = max(-1.0, min(1.0, float(x)))
        self._y = max(-1.0, min(1.0, float(y)))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        size = min(w, h) - 18  # leave room for label below
        cx = w / 2
        cy = (h - 12) / 2
        r = size / 2
        # Outer ring
        p.setBrush(QColor(PANEL_BG_INNER))
        p.setPen(QPen(QColor(PANEL_BORDER), 1))
        p.drawEllipse(int(cx - r), int(cy - r), int(size), int(size))
        # Crosshair
        p.setPen(QPen(QColor(PANEL_BORDER), 1))
        p.drawLine(int(cx - r * 0.7), int(cy), int(cx + r * 0.7), int(cy))
        p.drawLine(int(cx), int(cy - r * 0.7), int(cx), int(cy + r * 0.7))
        # Center reference
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TEXT_LABEL))
        p.drawEllipse(int(cx - 2), int(cy - 2), 4, 4)
        # Active dot — joystick convention: +x right, +y up. Screen y flips.
        dot_r = max(5, int(r * 0.20))
        dx = cx + self._x * (r - dot_r)
        dy = cy - self._y * (r - dot_r)
        p.setBrush(QColor(self._color))
        p.drawEllipse(int(dx - dot_r), int(dy - dot_r), dot_r * 2, dot_r * 2)
        # Label below
        p.setPen(QColor(TEXT_LABEL))
        f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f)
        p.drawText(0, int(cy + r) + 4, w, 14, Qt.AlignHCenter, self._label)


class JoystickWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 6)
        outer.setSpacing(4)

        title = QLabel("◉ 조이스틱")
        title.setStyleSheet(TITLE_QSS)
        outer.addWidget(title, 0, Qt.AlignTop)

        sticks_row = QHBoxLayout()
        sticks_row.setSpacing(6)
        self._left = _Stick("이동", ACCENT_BLUE)
        self._right = _Stick("회전", ACCENT_CYAN)
        sticks_row.addWidget(self._left, 1)
        sticks_row.addWidget(self._right, 1)
        outer.addLayout(sticks_row, 1)

    def update_from_msg(self, msg) -> None:
        axes = list(msg.axes) + [0.0] * 6
        # Common gamepad mapping: axes[0]=LX, axes[1]=LY, axes[3]=RX.
        # Both X axes inverted per operator feedback.
        lx = -axes[0]
        ly = axes[1]
        rx = -axes[3]
        # Left stick: 4-direction only — keep dominant axis, zero the other.
        if abs(lx) >= abs(ly):
            self._left.set_xy(lx, 0.0)
        else:
            self._left.set_xy(0.0, ly)
        # Right stick: horizontal only.
        self._right.set_xy(rx, 0.0)
