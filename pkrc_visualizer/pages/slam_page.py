"""SLAM page — accumulate /fast_lio/debug/points_world (world frame) +
overlay map-origin/robot-frame axes + optional OccupancyGrid prior map +
2D Pose Estimate toggle (click+drag on ground plane)."""
import numpy as np
from PyQt5.QtWidgets import QAction, QToolBar, QVBoxLayout
from sensor_msgs_py import point_cloud2

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pose_estimate_tool import PoseEstimateTool
from pkrc_visualizer.widgets.pyvista_view import PyVistaView


class SlamPage(BasePage):
    def __init__(self, ros_client, display_store, parent=None):
        super().__init__(ros_client, parent)
        self._view = PyVistaView()
        self._store = display_store

        toolbar = QToolBar(self)
        self._pose_estimate_action = QAction("Pose Estimate", self)
        self._pose_estimate_action.setCheckable(True)
        self._pose_estimate_action.toggled.connect(self._on_pose_estimate_toggled)
        toolbar.addAction(self._pose_estimate_action)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        layout.addWidget(self._view)

        self._has_set_camera = False
        self._install_settings_panel(
            self._view, page_key="slam", store=display_store,
            include_decay=True, include_prior_map=True)

        self._pose_tool = PoseEstimateTool(
            self._view, on_pose_picked=self._on_pose_picked)

        display_store.changed.connect(self._on_settings_changed)
        self._apply_prior_map_settings(display_store.get("slam"))

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"slam_cloud", "slam_path", "pose_odom", "slam_prior_grid"}

    def refresh(self) -> None:
        tf_matrix = self._active_tf()  # None when no TF, or TF is still identity

        cloud_msg = self._latest.pop("slam_cloud", None)
        if cloud_msg is not None:
            pts = self._cloud_to_array(cloud_msg)
            if pts.size:
                if tf_matrix is not None:
                    from pkrc_visualizer.tf_transform import apply_to_points
                    pts = apply_to_points(tf_matrix, pts)
                self._view.append_cloud(pts, color="#4fc3f7")
                if not self._has_set_camera:
                    self._view.reset_camera()
                    self._has_set_camera = True

        odom_msg = self._latest.get("pose_odom")
        if odom_msg is not None:
            p = odom_msg.pose.pose.position
            q = odom_msg.pose.pose.orientation
            position = (p.x, p.y, p.z)
            quaternion = (q.x, q.y, q.z, q.w)
            if tf_matrix is not None:
                from pkrc_visualizer.tf_transform import apply_to_pose
                position, quaternion = apply_to_pose(tf_matrix, position, quaternion)
            self._view.update_robot_pose(position, quaternion)

        grid_msg = self._latest.pop("slam_prior_grid", None)
        if grid_msg is not None:
            settings = self._store.get("slam")
            if settings.prior_map.show:
                self._view.set_occupancy_grid(grid_msg)

    def _on_pose_estimate_toggled(self, checked: bool) -> None:
        if checked:
            self._view.push_camera()
            self._view.force_top_down()
            self._pose_tool.attach()
        else:
            self._pose_tool.detach()
            self._view.pop_camera()

    def _on_pose_picked(self, x: float, y: float, yaw: float) -> None:
        self._ros_client.publish_initialpose(x, y, yaw)

    def _on_settings_changed(self, page_key, settings) -> None:
        if page_key == "slam":
            self._apply_prior_map_settings(settings)

    def _apply_prior_map_settings(self, settings) -> None:
        pm = settings.prior_map
        if pm.show:
            # Re-create plane from cached message if previously cleared.
            # OccupancyGrid is transient_local — sent once, so we can't wait
            # for a fresh message to arrive on toggle-back-on.
            self._view.restore_prior_grid_if_cleared()
            self._view.set_prior_grid_alpha(pm.alpha)
        else:
            self._view.clear_occupancy_grid()

    def hideEvent(self, event) -> None:
        # Force OFF before parent hideEvent stops the timer.
        if self._pose_estimate_action.isChecked():
            self._pose_estimate_action.setChecked(False)
        super().hideEvent(event)

    def _active_tf(self):
        """Return the live `map ← odom` transform, or None for identity fallback.

        fast-lio publishes an identity TF during the global localization grid
        search (before the user provides /initialpose). Treating that case as
        identity-fallback keeps the cloud visible in odom frame so the user
        has something to aim at when clicking 2D Pose Estimate.
        """
        m = self._ros_client.lookup_map_from_odom()
        if m is None or getattr(m, "shape", None) != (4, 4):
            return None
        if np.allclose(m, np.eye(4), atol=1e-9):
            return None
        return m

    @staticmethod
    def _cloud_to_array(msg) -> np.ndarray:
        try:
            structured = point_cloud2.read_points(
                msg, field_names=("x", "y", "z"), skip_nans=True)
            arr = np.array([[p[0], p[1], p[2]] for p in structured], dtype=np.float32)
            return arr
        except Exception:
            return np.zeros((0, 3), dtype=np.float32)
