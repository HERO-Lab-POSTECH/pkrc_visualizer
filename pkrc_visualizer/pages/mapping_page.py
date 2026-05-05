"""Sonar Mapping page: combined view of /sonar_3d_mapper/point_cloud + marker_array."""
import numpy as np
from PyQt5.QtWidgets import QVBoxLayout
from sensor_msgs_py import point_cloud2

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


class MappingPage(BasePage):
    def __init__(self, ros_client, display_store, parent=None):
        super().__init__(ros_client, parent)
        self._view = PyVistaView()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        self._has_set_camera = False
        self._install_settings_panel(
            self._view, page_key="mapping", store=display_store, include_decay=False)

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"map_cloud", "map_markers", "pose_odom"}

    def refresh(self) -> None:
        cloud_msg = self._latest.pop("map_cloud", None)
        if cloud_msg is not None:
            pts = self._cloud_to_array(cloud_msg)
            self._view.update_cloud(pts, color="#81c784")
            if not self._has_set_camera and pts.size:
                self._view.reset_camera()
                self._has_set_camera = True

        marker_msg = self._latest.pop("map_markers", None)
        if marker_msg is not None:
            pts = self._markers_to_array(marker_msg)
            self._view.update_markers(pts, color="#ffb74d")

        odom_msg = self._latest.get("pose_odom")
        if odom_msg is not None:
            p = odom_msg.pose.pose.position
            q = odom_msg.pose.pose.orientation
            self._view.update_robot_pose((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))

    @staticmethod
    def _cloud_to_array(msg) -> np.ndarray:
        try:
            structured = point_cloud2.read_points(
                msg, field_names=("x", "y", "z"), skip_nans=True)
            return np.array([[p[0], p[1], p[2]] for p in structured], dtype=np.float32)
        except Exception:
            return np.zeros((0, 3), dtype=np.float32)

    @staticmethod
    def _markers_to_array(msg) -> np.ndarray:
        coords: list[tuple[float, float, float]] = []
        for marker in msg.markers:
            # POINTS / LINE_STRIP / SPHERE_LIST / CUBE_LIST etc. carry marker.points.
            if marker.points:
                coords.extend((p.x, p.y, p.z) for p in marker.points)
            else:
                # CUBE/SPHERE single markers expose only pose.position.
                p = marker.pose.position
                coords.append((p.x, p.y, p.z))
        return np.array(coords, dtype=np.float32) if coords else np.zeros((0, 3), dtype=np.float32)
