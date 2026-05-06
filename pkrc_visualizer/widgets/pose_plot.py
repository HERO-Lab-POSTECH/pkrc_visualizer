"""Embed matplotlib FigureCanvasQTAgg: XY trajectory built from pose_odom
over a sliding time window. Window matches the cloud accumulator's
decay_seconds so path and cloud age together."""
from collections import deque

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QVBoxLayout, QWidget


class PosePlot(QWidget):
    WINDOW_SECONDS = 30.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = Figure(figsize=(6, 6))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._ax.set_xlabel("X [m]")
        self._ax.set_ylabel("Y [m]")
        self._ax.set_aspect("equal", adjustable="datalim")
        self._ax.grid(True, alpha=0.3)
        self._traj: deque[tuple[float, float, float]] = deque()  # (t, x, y)

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas)

    def append_pose(self, t: float, x: float, y: float) -> None:
        self._traj.append((t, x, y))
        cutoff = t - self.WINDOW_SECONDS
        while self._traj and self._traj[0][0] < cutoff:
            self._traj.popleft()

    def draw(self) -> None:
        self._ax.clear()
        self._ax.set_xlabel("X [m]")
        self._ax.set_ylabel("Y [m]")
        self._ax.set_aspect("equal", adjustable="datalim")
        self._ax.grid(True, alpha=0.3)
        if self._traj:
            xs = [x for _, x, _ in self._traj]
            ys = [y for _, _, y in self._traj]
            self._ax.plot(xs, ys, color="#1976d2", linewidth=2, label="path")
            self._ax.scatter([xs[-1]], [ys[-1]], color="#d32f2f", s=40, zorder=3)
            self._ax.legend(loc="upper right", fontsize=8)
        self._canvas.draw_idle()
