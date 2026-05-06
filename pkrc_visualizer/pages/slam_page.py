"""SLAM page — accumulate /fast_lio/debug/points_world (world frame) +
overlay map-origin/robot-frame axes + optional OccupancyGrid prior map."""
import numpy as np
from PyQt5.QtWidgets import QVBoxLayout
from sensor_msgs_py import point_cloud2

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


class SlamPage(BasePage):
    def __init__(self, ros_client, display_store, parent=None):
        super().__init__(ros_client, parent)
        self._view = PyVistaView()
        self._store = display_store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._has_set_camera = False
        self._install_settings_panel(
            self._view, page_key="slam", store=display_store,
            include_decay=True, include_prior_map=True)

        display_store.changed.connect(self._on_settings_changed)
        self._apply_prior_map_settings(display_store.get("slam"))

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"slam_cloud", "slam_path", "pose_odom", "slam_prior_grid"}

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

        grid_msg = self._latest.pop("slam_prior_grid", None)
        if grid_msg is not None:
            settings = self._store.get("slam")
            if settings.prior_map.show:
                self._view.set_occupancy_grid(grid_msg)

    def _on_settings_changed(self, page_key, settings) -> None:
        if page_key == "slam":
            self._apply_prior_map_settings(settings)

    def _apply_prior_map_settings(self, settings) -> None:
        pm = settings.prior_map
        if pm.show:
            self._view.set_prior_grid_alpha(pm.alpha)
        else:
            self._view.clear_occupancy_grid()

    @staticmethod
    def _cloud_to_array(msg) -> np.ndarray:
        try:
            structured = point_cloud2.read_points(
                msg, field_names=("x", "y", "z"), skip_nans=True)
            arr = np.array([[p[0], p[1], p[2]] for p in structured], dtype=np.float32)
            return arr
        except Exception:
            return np.zeros((0, 3), dtype=np.float32)
