"""matplotlib FigureCanvasQTAgg 임베드 — XY 궤적 + Path 오버레이."""
from collections import deque

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QVBoxLayout, QWidget


class PosePlot(QWidget):
    HISTORY = 10000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = Figure(figsize=(6, 6))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._ax.set_xlabel("X [m]")
        self._ax.set_ylabel("Y [m]")
        self._ax.set_aspect("equal", adjustable="datalim")
        self._ax.grid(True, alpha=0.3)
        self._traj_x: deque[float] = deque(maxlen=self.HISTORY)
        self._traj_y: deque[float] = deque(maxlen=self.HISTORY)
        self._path_x: list[float] = []
        self._path_y: list[float] = []

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas)

    def append_pose(self, x: float, y: float) -> None:
        self._traj_x.append(x)
        self._traj_y.append(y)

    def set_path(self, xs: list[float], ys: list[float]) -> None:
        self._path_x = xs
        self._path_y = ys

    def draw(self) -> None:
        self._ax.clear()
        self._ax.set_xlabel("X [m]")
        self._ax.set_ylabel("Y [m]")
        self._ax.set_aspect("equal", adjustable="datalim")
        self._ax.grid(True, alpha=0.3)
        if self._path_x:
            self._ax.plot(self._path_x, self._path_y, color="#888", linewidth=1, label="path")
        if self._traj_x:
            self._ax.plot(list(self._traj_x), list(self._traj_y), color="#1976d2", linewidth=2, label="odom")
            self._ax.scatter([self._traj_x[-1]], [self._traj_y[-1]], color="#d32f2f", s=40, zorder=3)
        if self._traj_x or self._path_x:
            self._ax.legend(loc="upper right", fontsize=8)
        self._canvas.draw_idle()
