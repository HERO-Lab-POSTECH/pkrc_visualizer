"""2D top-down map — robot pose + 30s trail.

Lightweight QWidget with custom paintEvent. No OpenGL, no PyVista.

Coordinate convention (matches RViz top-down view):
  +x_world (forward) → screen up
  +y_world (left)    → screen left
"""
import math
import time
from collections import deque
from typing import Optional

import numpy as np
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from pkrc_visualizer.pages.monitoring.common import (ACCENT_BLUE, ACCENT_CYAN,
                                                       PANEL_BG_INNER,
                                                       PANEL_BORDER, PANEL_QSS,
                                                       TEXT_DIM, TEXT_LABEL,
                                                       TEXT_PRIMARY, TITLE_QSS)

VIEW_HALF_M = 5.0    # 5m radius visible
GRID_STEP_M = 1.0
TRAIL_SECONDS = 30.0
ROBOT_LEN_M = 0.4


def _quat_to_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    """Yaw from quaternion (ZYX convention)."""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def _occupancy_grid_to_qimage(msg) -> QImage:
    """nav_msgs/OccupancyGrid → QImage (Format_Grayscale8).

    Greyscale mapping:
      -1 (unknown) → 127 (mid grey)
       0 (free)    → 255 (white)
     100 (occupied) → 0 (black)
      others       → linearly interpolated.

    OccupancyGrid data is row-major with row 0 at the LOWER-LEFT cell
    (origin pose). QImage uses TOP-LEFT origin, so we flip vertically
    so that drawImage(rect, img) renders north-up.
    """
    w = msg.info.width
    h = msg.info.height
    data = np.asarray(msg.data, dtype=np.int16).reshape(h, w)
    out = np.where(data < 0, 127, 255 - (data * 255) // 100)
    out = np.clip(out, 0, 255).astype(np.uint8)
    out = np.flipud(out)
    flat = bytes(out.tobytes())
    return QImage(flat, w, h, w, QImage.Format_Grayscale8).copy()


class _MapCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self._x = None
        self._y = None
        self._yaw = 0.0
        # Trail entries: (timestamp, x, y) in world coords
        self._trail: deque[tuple[float, float, float]] = deque(maxlen=600)
        # Occupancy-grid layer (drawn behind grid lines / trail / robot).
        self._grid_image: Optional[QImage] = None
        self._grid_origin_xy: tuple[float, float] = (0.0, 0.0)
        self._grid_resolution: float = 0.0
        self._grid_size: tuple[int, int] = (0, 0)

    def update_pose(self, x: float, y: float, yaw: float) -> None:
        self._x = x
        self._y = y
        self._yaw = yaw
        now = time.monotonic()
        self._trail.append((now, x, y))
        # Drop entries older than TRAIL_SECONDS
        cutoff = now - TRAIL_SECONDS
        while self._trail and self._trail[0][0] < cutoff:
            self._trail.popleft()
        self.update()

    def set_occupancy_grid(self, msg) -> None:
        """Cache grid as QImage + metadata; trigger repaint."""
        self._grid_image = _occupancy_grid_to_qimage(msg)
        self._grid_origin_xy = (
            float(msg.info.origin.position.x),
            float(msg.info.origin.position.y),
        )
        self._grid_resolution = float(msg.info.resolution)
        self._grid_size = (int(msg.info.width), int(msg.info.height))
        self.update()

    def set_pose_in_map_frame(self, x: float, y: float, yaw: float) -> None:
        """Equivalent to update_pose; explicit name documents the frame
        contract: callers must provide map-frame coords."""
        self.update_pose(x, y, yaw)

    def _world_to_screen(self, wx: float, wy: float) -> QPointF:
        # Center of widget = robot center (follow camera).
        # Scale so VIEW_HALF_M fills half of the smaller dimension.
        cx_pix = self.width() / 2.0
        cy_pix = self.height() / 2.0
        side = min(self.width(), self.height())
        scale = (side / 2.0) / VIEW_HALF_M
        # Shift world point into robot-centered frame.
        rx = wx - (self._x or 0.0)
        ry = wy - (self._y or 0.0)
        # +x world → screen up; +y world → screen left.
        sx = cx_pix - ry * scale
        sy = cy_pix - rx * scale
        return QPointF(sx, sy)

    def _paint_grid(self, p: QPainter) -> None:
        if self._grid_image is None:
            return
        W, H = self._grid_size
        res = self._grid_resolution
        if W == 0 or H == 0 or res <= 0.0:
            return
        ox, oy = self._grid_origin_xy
        tl = self._world_to_screen(ox, oy + H * res)
        br = self._world_to_screen(ox + W * res, oy)
        rect = QRectF(tl.x(), tl.y(), br.x() - tl.x(), br.y() - tl.y())
        p.drawImage(rect, self._grid_image)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Background — deep navy with rounded corners
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PANEL_BG_INNER))
        p.drawRoundedRect(self.rect(), 6, 6)
        # Occupancy grid (behind everything else)
        self._paint_grid(p)
        # Grid
        p.setPen(QPen(QColor(PANEL_BORDER), 1))
        side = min(self.width(), self.height())
        scale = (side / 2.0) / VIEW_HALF_M
        if self._x is not None:
            # Snap grid lines to world meters.
            x_min = math.floor((self._x - VIEW_HALF_M) / GRID_STEP_M) * GRID_STEP_M
            x_max = self._x + VIEW_HALF_M
            x = x_min
            while x <= x_max:
                a = self._world_to_screen(x, self._y - VIEW_HALF_M)
                b = self._world_to_screen(x, self._y + VIEW_HALF_M)
                p.drawLine(a, b)
                x += GRID_STEP_M
            y_min = math.floor((self._y - VIEW_HALF_M) / GRID_STEP_M) * GRID_STEP_M
            y_max = self._y + VIEW_HALF_M
            y = y_min
            while y <= y_max:
                a = self._world_to_screen(self._x - VIEW_HALF_M, y)
                b = self._world_to_screen(self._x + VIEW_HALF_M, y)
                p.drawLine(a, b)
                y += GRID_STEP_M
        # Trail
        if len(self._trail) >= 2:
            p.setPen(QPen(QColor(6, 182, 212, 180), 2))  # cyan-ish trail
            prev = None
            for _ts, tx, ty in self._trail:
                pt = self._world_to_screen(tx, ty)
                if prev is not None:
                    p.drawLine(prev, pt)
                prev = pt
        # Robot arrow
        if self._x is not None:
            cx, cy = self.width() / 2.0, self.height() / 2.0
            arrow_pix = ROBOT_LEN_M * scale
            tip_dx = math.cos(self._yaw) * arrow_pix
            tip_dy = math.sin(self._yaw) * arrow_pix
            # World +x → up, world +y → left → so tip on screen:
            # (screen +y is down, screen +x is right)
            tip_sx = cx - tip_dy
            tip_sy = cy - tip_dx
            base_left_dx = -tip_dy * 0.5 + tip_dx * 0.0
            # Build a triangle: tip + two base points perpendicular to heading.
            # Perpendicular in world = (-sin(yaw), cos(yaw)).
            perp_dx = -math.sin(self._yaw) * arrow_pix * 0.4
            perp_dy = math.cos(self._yaw) * arrow_pix * 0.4
            base_x = -tip_dx * 0.4  # half a length behind center
            base_y = -tip_dy * 0.4
            base_l_sx = cx - (base_y + perp_dy)
            base_l_sy = cy - (base_x + perp_dx)
            base_r_sx = cx - (base_y - perp_dy)
            base_r_sy = cy - (base_x - perp_dx)
            tri = QPolygonF([
                QPointF(tip_sx, tip_sy),
                QPointF(base_l_sx, base_l_sy),
                QPointF(base_r_sx, base_r_sy),
            ])
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.setBrush(QColor(ACCENT_BLUE))
            p.drawPolygon(tri)
        else:
            # No data yet — match web GUI's "2D Map" empty state
            p.setPen(QColor(TEXT_LABEL))
            big = QFont(); big.setPointSize(20); big.setBold(True); p.setFont(big)
            r = self.rect()
            p.drawText(r.adjusted(0, -10, 0, -10), Qt.AlignCenter, "2D Map")
            small = QFont(); small.setPointSize(9); p.setFont(small)
            p.setPen(QColor(TEXT_DIM))
            p.drawText(r.adjusted(0, 24, 0, 24), Qt.AlignCenter,
                       "/slam/fast_lio/odometry 대기 중")


class TopdownMapWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)
        title = QLabel("🗺 2D 맵 (탑뷰)")
        title.setStyleSheet(TITLE_QSS)
        layout.addWidget(title)
        self._canvas = _MapCanvas()
        layout.addWidget(self._canvas, 1)

    def set_occupancy_grid(self, msg) -> None:
        """nav_msgs/OccupancyGrid pass-through to canvas."""
        self._canvas.set_occupancy_grid(msg)

    def set_pose_in_map_frame(self, x: float, y: float, yaw: float) -> None:
        self._canvas.set_pose_in_map_frame(x, y, yaw)
