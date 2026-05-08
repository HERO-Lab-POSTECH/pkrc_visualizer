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
                                                       ACCENT_GREEN, ACCENT_RED,
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
        """Map (wx, wy) world coords → panel pixel coords.

        Two modes:
        - Auto-fit on grid bounds (north-up). Used when an occupancy grid
          has been loaded. +x_world → screen right, +y_world → screen up.
          Aspect preserved (letterbox).
        - Robot-centered fallback. Used until the first grid arrives. +x
          forward → screen up, +y left → screen left, fixed 5m radius.
        """
        if self._grid_image is not None and self._grid_size[0] > 0 \
                and self._grid_size[1] > 0 and self._grid_resolution > 0.0:
            Pw = float(self.width())
            Ph = float(self.height())
            W, H = self._grid_size
            res = self._grid_resolution
            ox, oy = self._grid_origin_xy
            gw_m = W * res
            gh_m = H * res
            scale = min(Pw / gw_m, Ph / gh_m)
            cx = (Pw - gw_m * scale) / 2.0
            cy = (Ph - gh_m * scale) / 2.0
            sx = cx + (wx - ox) * scale
            sy = cy + gh_m * scale - (wy - oy) * scale
            return QPointF(sx, sy)

        cx_pix = self.width() / 2.0
        cy_pix = self.height() / 2.0
        side = min(self.width(), self.height())
        scale = (side / 2.0) / VIEW_HALF_M
        rx = wx - (self._x or 0.0)
        ry = wy - (self._y or 0.0)
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

    def _paint_axes(self, p: QPainter) -> None:
        """Draw a small RViz-style coordinate triad at the robot pose.

        X axis red, Y axis green. Length = 0.5 m world (constant in metric
        units, so visual size scales with zoom). No labels — keep it terse.
        """
        if self._x is None:
            return
        AXIS_LEN_M = 0.5
        origin = self._world_to_screen(self._x, self._y)
        x_tip = self._world_to_screen(
            self._x + AXIS_LEN_M * math.cos(self._yaw),
            self._y + AXIS_LEN_M * math.sin(self._yaw))
        y_tip = self._world_to_screen(
            self._x + AXIS_LEN_M * math.cos(self._yaw + math.pi / 2),
            self._y + AXIS_LEN_M * math.sin(self._yaw + math.pi / 2))
        p.setPen(QPen(QColor(ACCENT_RED), 2))
        p.drawLine(origin, x_tip)
        p.setPen(QPen(QColor(ACCENT_GREEN), 2))
        p.drawLine(origin, y_tip)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Background — deep navy with rounded corners
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PANEL_BG_INNER))
        p.drawRoundedRect(self.rect(), 6, 6)
        # Occupancy grid (behind everything else)
        self._paint_grid(p)
        # 1m grid lines
        p.setPen(QPen(QColor(PANEL_BORDER), 1))
        if self._grid_image is not None and self._grid_size[0] > 0:
            ox, oy = self._grid_origin_xy
            W, H = self._grid_size
            gw_m = W * self._grid_resolution
            gh_m = H * self._grid_resolution
            x_min = math.floor(ox / GRID_STEP_M) * GRID_STEP_M
            x_max = ox + gw_m
            x = x_min
            while x <= x_max:
                a = self._world_to_screen(x, oy)
                b = self._world_to_screen(x, oy + gh_m)
                p.drawLine(a, b)
                x += GRID_STEP_M
            y_min = math.floor(oy / GRID_STEP_M) * GRID_STEP_M
            y_max = oy + gh_m
            y = y_min
            while y <= y_max:
                a = self._world_to_screen(ox, y)
                b = self._world_to_screen(ox + gw_m, y)
                p.drawLine(a, b)
                y += GRID_STEP_M
        elif self._x is not None:
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
        # TF axes triad at robot pose (X red, Y green)
        self._paint_axes(p)
        # Robot arrow — direction = heading (yaw), length ROBOT_LEN_M in world.
        # All vertices go through _world_to_screen so this is correct in
        # both auto-fit and robot-centered-fallback modes.
        if self._x is not None:
            tip_w = (self._x + ROBOT_LEN_M * math.cos(self._yaw),
                     self._y + ROBOT_LEN_M * math.sin(self._yaw))
            back = ROBOT_LEN_M * 0.4
            base_c_w = (self._x - back * math.cos(self._yaw),
                        self._y - back * math.sin(self._yaw))
            perp_yaw = self._yaw + math.pi / 2
            half_w = ROBOT_LEN_M * 0.4
            base_l_w = (base_c_w[0] + half_w * math.cos(perp_yaw),
                        base_c_w[1] + half_w * math.sin(perp_yaw))
            base_r_w = (base_c_w[0] - half_w * math.cos(perp_yaw),
                        base_c_w[1] - half_w * math.sin(perp_yaw))
            tri = QPolygonF([
                self._world_to_screen(*tip_w),
                self._world_to_screen(*base_l_w),
                self._world_to_screen(*base_r_w),
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
                       "맵 대기 중\n(cartographer / fast_lio_loc)")


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
