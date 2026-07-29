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
# Pixel-space sizes for the robot arrow and TF triad. Decoupled from world
# zoom so the robot stays readable as the auto-fit map grows.
ROBOT_LEN_PX = 30.0
AXIS_LEN_PX = 22.0


def _quat_to_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    """Yaw from quaternion (ZYX convention)."""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def _occupancy_grid_to_qimage(msg) -> QImage:
    """nav_msgs/OccupancyGrid → ARGB QImage with deliberately light tone.

    The previous greyscale mapping (unknown = mid grey, free = white,
    occupied = black) was too heavy — the grid dominated the panel and
    the actual walls (occupied cells, sparse) blended in. New mapping:
      -1 (unknown) → near-transparent (subtle background tint)
       0 (free)    → very light (almost background)
     100 (occupied) → opaque dark blue (high contrast against panel)
    """
    w = msg.info.width
    h = msg.info.height
    data = np.asarray(msg.data, dtype=np.int16).reshape(h, w)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    occupied = data >= 50
    free = (data >= 0) & (data < 50)
    # Walls — saturated cyan/blue, fully opaque so they pop.
    rgba[occupied] = (96, 165, 250, 255)
    # Free cells — barely-visible grey wash so the grid frame still reads.
    rgba[free] = (255, 255, 255, 60)
    # Unknown cells stay (0,0,0,0) — fully transparent.
    rgba = np.flipud(rgba)
    flat = bytes(rgba.tobytes())
    return QImage(flat, w, h, w * 4, QImage.Format_RGBA8888).copy()


class _MapCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self.setFocusPolicy(Qt.StrongFocus)  # accept key events for R-reset
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
        # User-controlled view rotation (radians, CCW positive).
        # Drag with the right mouse button to rotate; press R to reset.
        self._view_yaw: float = 0.0
        self._drag_anchor: Optional[QPointF] = None
        self._drag_start_yaw: float = 0.0

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

    def _rotate_about_center(self, pt: QPointF) -> QPointF:
        """Rotate a screen-space point around the panel centre by _view_yaw.

        +_view_yaw rotates the visible map counter-clockwise on screen
        (matches the conventional "drag right to spin world clockwise"
        intuition once we negate at the input layer)."""
        if self._view_yaw == 0.0:
            return pt
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        c = math.cos(self._view_yaw)
        s = math.sin(self._view_yaw)
        dx = pt.x() - cx
        dy = pt.y() - cy
        return QPointF(cx + c * dx - s * dy, cy + s * dx + c * dy)

    def _world_to_screen(self, wx: float, wy: float) -> QPointF:
        """Map (wx, wy) world coords → panel pixel coords.

        Two modes:
        - Auto-fit on grid bounds (north-up). Used when an occupancy grid
          has been loaded. +x_world → screen right, +y_world → screen up.
          Aspect preserved (letterbox).
        - Robot-centered fallback. Used until the first grid arrives. +x
          forward → screen up, +y left → screen left, fixed 5m radius.

        After the base mapping, the user's view rotation is applied as a
        rotation around the panel centre so every drawn element (grid,
        trail, robot) stays aligned.
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
            return self._rotate_about_center(QPointF(sx, sy))

        cx_pix = self.width() / 2.0
        cy_pix = self.height() / 2.0
        side = min(self.width(), self.height())
        scale = (side / 2.0) / VIEW_HALF_M
        rx = wx - (self._x or 0.0)
        ry = wy - (self._y or 0.0)
        sx = cx_pix - ry * scale
        sy = cy_pix - rx * scale
        return self._rotate_about_center(QPointF(sx, sy))

    def _paint_grid(self, p: QPainter) -> None:
        """Draw the grid image, rotated by the user's view angle.

        We can't just feed two rotated corners to drawImage(QRectF, ...)
        because that builds an axis-aligned rect — the image would shear.
        Instead apply a QPainter transform: translate to panel centre,
        rotate by the view yaw, translate back, then draw on the
        unrotated rect. The painter is restored to its prior state.
        """
        if self._grid_image is None:
            return
        W, H = self._grid_size
        res = self._grid_resolution
        if W == 0 or H == 0 or res <= 0.0:
            return
        # Compute the unrotated rectangle: temporarily disable view_yaw
        # so _world_to_screen gives the base mapping, then let the
        # painter do the rotation around the panel centre.
        prev_yaw = self._view_yaw
        self._view_yaw = 0.0
        try:
            ox, oy = self._grid_origin_xy
            tl = self._world_to_screen(ox, oy + H * res)
            br = self._world_to_screen(ox + W * res, oy)
            rect = QRectF(tl.x(), tl.y(), br.x() - tl.x(), br.y() - tl.y())
        finally:
            self._view_yaw = prev_yaw

        if prev_yaw == 0.0:
            p.drawImage(rect, self._grid_image)
            return
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        p.save()
        p.translate(cx, cy)
        p.rotate(math.degrees(prev_yaw))
        p.translate(-cx, -cy)
        p.drawImage(rect, self._grid_image)
        p.restore()

    def _paint_axes(self, p: QPainter) -> None:
        """Draw a small RViz-style triad at the robot pose, sized in pixels.

        Pixel-space length keeps the indicator readable regardless of how
        far the auto-fit map is zoomed out. View rotation is folded into
        the heading so the triad turns with the user-rotated map.
        """
        if self._x is None:
            return
        origin = self._world_to_screen(self._x, self._y)
        eff_yaw = self._yaw - self._view_yaw
        cos_y, sin_y = math.cos(eff_yaw), math.sin(eff_yaw)
        x_tip = QPointF(origin.x() + AXIS_LEN_PX * cos_y,
                        origin.y() - AXIS_LEN_PX * sin_y)
        y_tip = QPointF(origin.x() - AXIS_LEN_PX * sin_y,
                        origin.y() - AXIS_LEN_PX * cos_y)
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
        # Robot arrow — sized in PIXELS so it stays readable regardless of
        # zoom level. View rotation is folded into the heading so the
        # arrow turns together with the user-rotated map.
        if self._x is not None:
            origin = self._world_to_screen(self._x, self._y)
            eff_yaw = self._yaw - self._view_yaw
            cos_y, sin_y = math.cos(eff_yaw), math.sin(eff_yaw)
            tip = QPointF(origin.x() + ROBOT_LEN_PX * cos_y,
                          origin.y() - ROBOT_LEN_PX * sin_y)
            back = ROBOT_LEN_PX * 0.4
            base_c = QPointF(origin.x() - back * cos_y,
                             origin.y() + back * sin_y)
            half = ROBOT_LEN_PX * 0.4
            base_l = QPointF(base_c.x() - half * sin_y,
                             base_c.y() - half * cos_y)
            base_r = QPointF(base_c.x() + half * sin_y,
                             base_c.y() + half * cos_y)
            tri = QPolygonF([tip, base_l, base_r])
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.setBrush(QColor(ACCENT_BLUE))
            p.drawPolygon(tri)
        elif self._grid_image is None:
            # Truly empty (no grid AND no pose). Show the big "2D Map" hint.
            # Once a grid arrives, suppress the overlay text — the map alone
            # is the empty state for "no robot pose yet".
            p.setPen(QColor(TEXT_LABEL))
            big = QFont(); big.setPointSize(20); big.setBold(True); p.setFont(big)
            r = self.rect()
            p.drawText(r.adjusted(0, -10, 0, -10), Qt.AlignCenter, "2D Map")
            small = QFont(); small.setPointSize(9); p.setFont(small)
            p.setPen(QColor(TEXT_DIM))
            p.drawText(r.adjusted(0, 24, 0, 24), Qt.AlignCenter,
                       "맵 대기 중\n(cartographer / fast_lio_loc)")

    # ---- view rotation interaction --------------------------------
    # Right-mouse drag spins the map around the panel centre. R resets.
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self.setFocus(Qt.MouseFocusReason)
            self._drag_anchor = QPointF(event.pos())
            self._drag_start_yaw = self._view_yaw
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_anchor is not None:
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            a0 = math.atan2(self._drag_anchor.y() - cy,
                            self._drag_anchor.x() - cx)
            a1 = math.atan2(event.pos().y() - cy,
                            event.pos().x() - cx)
            self._view_yaw = self._drag_start_yaw + (a1 - a0)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.RightButton and self._drag_anchor is not None:
            self._drag_anchor = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_R:
            self._view_yaw = 0.0
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)


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
