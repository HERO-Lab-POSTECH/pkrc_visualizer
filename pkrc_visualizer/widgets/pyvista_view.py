"""pyvistaqt.QtInteractor 임베드. 점군 + Marker 갱신 인터페이스."""
from typing import Optional

import numpy as np
import pyvista as pv
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from pyvistaqt import QtInteractor


class PyVistaView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter = QtInteractor(self)
        self._plotter.set_background("#1e1e1e")
        self._plotter.add_axes()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plotter.interactor)

        self._cloud_actor = None
        self._marker_actor = None

    def update_cloud(self, points: np.ndarray, color: str = "#4fc3f7") -> None:
        """points: (N, 3) ndarray. N=0이면 클리어."""
        if self._cloud_actor is not None:
            self._plotter.remove_actor(self._cloud_actor)
            self._cloud_actor = None
        if points.size == 0:
            return
        cloud = pv.PolyData(points.astype(np.float32))
        self._cloud_actor = self._plotter.add_mesh(
            cloud, color=color, point_size=2, render_points_as_spheres=False)

    def update_markers(self, points: np.ndarray, color: str = "#ffb74d") -> None:
        """MarkerArray의 모든 marker.points를 평탄화한 (N,3) ndarray."""
        if self._marker_actor is not None:
            self._plotter.remove_actor(self._marker_actor)
            self._marker_actor = None
        if points.size == 0:
            return
        cloud = pv.PolyData(points.astype(np.float32))
        self._marker_actor = self._plotter.add_mesh(
            cloud, color=color, point_size=4, render_points_as_spheres=True)

    def reset_camera(self) -> None:
        self._plotter.reset_camera()

    def closeEvent(self, event):
        self._plotter.close()
        super().closeEvent(event)
