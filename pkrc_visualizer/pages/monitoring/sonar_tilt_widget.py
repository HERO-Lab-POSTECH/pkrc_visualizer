"""Sonar tilt — discrete goal angle (0/30/45/60/90°) with side-view diagram.

Top row carries the readouts so they're never hidden by the diagram:
  ┌─ 목표 각도            Oculus Vertical Aperture ─┐
  │     0.0°                       20°            │
  └────────────────────────────────────────────────┘

The diagram below shows the sonar pointing direction relative to a water
surface. The sonar fan (±10°) is drawn as a translucent wedge around the
arrow so the operator sees what the sonar actually covers.
"""
import math

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pkrc_visualizer.pages.monitoring.common import (ACCENT_BLUE, ACCENT_CYAN,
                                                       PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_DIM, TEXT_LABEL,
                                                       TEXT_PRIMARY, TITLE_QSS)

ALLOWED_STEPS_DEG = (0, 30, 45, 60, 90)
VERTICAL_APERTURE_DEG = 20.0  # Oculus M1200d vertical aperture (±10°)
WATER_BLUE = "#1e3a8a"
WATER_BLUE_LIGHT = "#3b82f6"


def _snap_to_step(deg: float) -> int:
    return min(ALLOWED_STEPS_DEG, key=lambda s: abs(s - deg))


class _SonarDiagram(QWidget):
    """Side-view: water surface bar, robot silhouette, sonar fan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._goal: int | None = None
        self.setMinimumHeight(110)

    def set_goal(self, deg: int | None) -> None:
        self._goal = deg
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        # Water surface band along the top
        water_h = 14
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(WATER_BLUE))
        p.drawRoundedRect(2, 2, w - 4, water_h, 4, 4)
        p.setPen(QColor(WATER_BLUE_LIGHT))
        f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f)
        p.drawText(8, 2, 60, water_h, Qt.AlignVCenter | Qt.AlignLeft, "Water")

        # Pivot — where the sonar attaches to the robot. Placed near top
        # so the fan extends downward into the available space.
        cx = w / 2
        cy = water_h + 14
        r = min(w / 2 - 14, h - cy - 18)
        if r < 14:
            return

        # Quarter-circle guide arc 0° (right) → 90° (down)
        p.setPen(QPen(QColor(PANEL_BORDER), 1, Qt.DashLine))
        p.drawArc(int(cx - r), int(cy - r), int(2 * r), int(2 * r),
                  -90 * 16, 90 * 16)

        # Tick marks for each allowed step
        for step in ALLOWED_STEPS_DEG:
            rad = math.radians(step)
            tx = cx + r * math.cos(rad)
            ty = cy + r * math.sin(rad)
            inner_x = cx + (r - 5) * math.cos(rad)
            inner_y = cy + (r - 5) * math.sin(rad)
            is_active = (self._goal == step)
            color = QColor(ACCENT_BLUE) if is_active else QColor(TEXT_DIM)
            p.setPen(QPen(color, 2 if is_active else 1))
            p.drawLine(int(inner_x), int(inner_y), int(tx), int(ty))
            label_x = cx + (r + 12) * math.cos(rad)
            label_y = cy + (r + 12) * math.sin(rad)
            p.setPen(QColor(TEXT_PRIMARY) if is_active else QColor(TEXT_DIM))
            f = p.font(); f.setPointSize(8); f.setBold(is_active); p.setFont(f)
            txt = f"{step}°"
            tw = p.fontMetrics().horizontalAdvance(txt)
            p.drawText(int(label_x - tw / 2), int(label_y + 4), txt)

        # Robot silhouette — a small sub at the pivot, riding the surface.
        body_w = int(r * 0.5)
        body_h = 10
        body_x = int(cx - body_w / 2)
        body_y = int(cy - body_h / 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#475569"))
        p.drawRoundedRect(body_x, body_y, body_w, body_h, 5, 5)
        # Front fin pointing right (= 0° forward)
        p.setBrush(QColor(TEXT_DIM))
        front = QPolygonF([
            QPointF(body_x + body_w, body_y - 1),
            QPointF(body_x + body_w + 5, cy),
            QPointF(body_x + body_w, body_y + body_h + 1),
        ])
        p.drawPolygon(front)

        # Sonar fan + arrow at goal angle
        if self._goal is not None:
            rad = math.radians(self._goal)
            half_aperture = math.radians(VERTICAL_APERTURE_DEG / 2.0)

            # Fan polygon: pivot + edge points across ±half_aperture.
            steps = 16
            pts = [QPointF(cx, cy)]
            for i in range(steps + 1):
                a = rad - half_aperture + (2 * half_aperture) * i / steps
                pts.append(QPointF(cx + r * 0.95 * math.cos(a),
                                   cy + r * 0.95 * math.sin(a)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(6, 182, 212, 60))  # cyan, translucent
            p.drawPolygon(QPolygonF(pts))
            # Edge lines
            p.setPen(QPen(QColor(ACCENT_CYAN), 1, Qt.DashLine))
            for sign in (-1, +1):
                a = rad + sign * half_aperture
                ex = cx + r * 0.95 * math.cos(a)
                ey = cy + r * 0.95 * math.sin(a)
                p.drawLine(int(cx), int(cy), int(ex), int(ey))

            # Center arrow
            tip_x = cx + r * 0.92 * math.cos(rad)
            tip_y = cy + r * 0.92 * math.sin(rad)
            p.setPen(QPen(QColor(ACCENT_BLUE), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(int(cx), int(cy), int(tip_x), int(tip_y))
            head_len = 8
            perp = rad + math.pi / 2
            hx1 = tip_x - head_len * math.cos(rad) + 4 * math.cos(perp)
            hy1 = tip_y - head_len * math.sin(rad) + 4 * math.sin(perp)
            hx2 = tip_x - head_len * math.cos(rad) - 4 * math.cos(perp)
            hy2 = tip_y - head_len * math.sin(rad) - 4 * math.sin(perp)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ACCENT_BLUE))
            head = QPolygonF([
                QPointF(tip_x, tip_y),
                QPointF(hx1, hy1),
                QPointF(hx2, hy2),
            ])
            p.drawPolygon(head)


class SonarTiltWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 8)
        outer.setSpacing(4)

        title = QLabel("⌖ 소나 틸트")
        title.setStyleSheet(TITLE_QSS)
        outer.addWidget(title, 0, Qt.AlignTop)

        # Top readout row — goal angle + vertical aperture
        readout = QHBoxLayout()
        readout.setSpacing(4)

        goal_box = QVBoxLayout()
        goal_box.setSpacing(0)
        goal_caption = QLabel("목표 각도")
        goal_caption.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 10px; "
            f"background: transparent; border: none;"
        )
        self._goal_label = QLabel("—°")
        self._goal_label.setStyleSheet(
            f"color: {ACCENT_BLUE}; font-size: 22px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        goal_box.addWidget(goal_caption)
        goal_box.addWidget(self._goal_label)

        ap_box = QVBoxLayout()
        ap_box.setSpacing(0)
        ap_caption = QLabel("Oculus Vertical Aperture")
        ap_caption.setAlignment(Qt.AlignRight)
        ap_caption.setStyleSheet(
            f"color: {TEXT_LABEL}; font-size: 10px; "
            f"background: transparent; border: none;"
        )
        ap_value = QLabel(f"{int(VERTICAL_APERTURE_DEG)}°")
        ap_value.setAlignment(Qt.AlignRight)
        ap_value.setStyleSheet(
            f"color: {ACCENT_CYAN}; font-size: 22px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        ap_box.addWidget(ap_caption)
        ap_box.addWidget(ap_value)

        readout.addLayout(goal_box, 1)
        readout.addStretch(1)
        readout.addLayout(ap_box, 1)
        outer.addLayout(readout)

        # Diagram below
        self._diagram = _SonarDiagram()
        outer.addWidget(self._diagram, 1)

    def update_current(self, _msg) -> None:
        # Per design: only goal angle is shown.
        pass

    def update_goal(self, msg) -> None:
        snapped = _snap_to_step(float(msg.data))
        self._goal_label.setText(f"{snapped}°")
        self._diagram.set_goal(snapped)
