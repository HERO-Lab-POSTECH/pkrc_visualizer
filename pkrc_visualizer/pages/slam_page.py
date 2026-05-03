"""SLAM 페이지 — /fast_lio/cloud_registered_body 점군 + path 오버레이."""
import numpy as np
from PyQt5.QtWidgets import QVBoxLayout
from sensor_msgs_py import point_cloud2

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


class SlamPage(BasePage):
    def __init__(self, ros_client, parent=None):
        super().__init__(ros_client, parent)
        self._view = PyVistaView()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._has_set_camera = False

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"slam_cloud", "slam_path"}

    def refresh(self) -> None:
        cloud_msg = self._latest.pop("slam_cloud", None)
        if cloud_msg is not None:
            pts = self._cloud_to_array(cloud_msg)
            self._view.update_cloud(pts, color="#4fc3f7")
            if not self._has_set_camera and pts.size:
                self._view.reset_camera()
                self._has_set_camera = True

    @staticmethod
    def _cloud_to_array(msg) -> np.ndarray:
        try:
            structured = point_cloud2.read_points(
                msg, field_names=("x", "y", "z"), skip_nans=True)
            arr = np.array([[p[0], p[1], p[2]] for p in structured], dtype=np.float32)
            return arr
        except Exception:
            return np.zeros((0, 3), dtype=np.float32)
