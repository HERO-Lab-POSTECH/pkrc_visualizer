"""SLAM page — accumulate /fast_lio/debug/points_world (world frame) +
overlay map-origin and robot-frame axes from odometry."""
import numpy as np
from PyQt5.QtWidgets import QVBoxLayout
from sensor_msgs_py import point_cloud2

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


class SlamPage(BasePage):
    def __init__(self, ros_client, display_store, parent=None):
        super().__init__(ros_client, parent)
        self._view = PyVistaView()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._has_set_camera = False
        self._install_settings_panel(
            self._view, page_key="slam", store=display_store, include_decay=True)

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"slam_cloud", "slam_path", "pose_odom"}

    def refresh(self) -> None:
        cloud_msg = self._latest.pop("slam_cloud", None)
        if cloud_msg is not None:
            pts = self._cloud_to_array(cloud_msg)
            if pts.size:
                self._view.append_cloud(pts, color="#4fc3f7")
                if not self._has_set_camera:
                    self._view.reset_camera()
                    self._has_set_camera = True

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
            arr = np.array([[p[0], p[1], p[2]] for p in structured], dtype=np.float32)
            return arr
        except Exception:
            return np.zeros((0, 3), dtype=np.float32)
