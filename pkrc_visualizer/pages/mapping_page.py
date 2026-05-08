"""Sonar Mapping page: points-only view; subscribes to mapper (in-memory) and map_visualizer (out-of-core) clouds in parallel."""
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
        return topic_id in {"map_cloud_inmem", "map_cloud_outcore",
                            "map_pose_odom", "map_pose_odom_carto"}

    def refresh(self) -> None:
        # Last-arrival-wins: only one mapper mode is active at a time, so
        # whichever id holds a message this tick is the live source. Pop both
        # ids so the next tick starts clean.
        outcore_msg = self._latest.pop("map_cloud_outcore", None)
        inmem_msg = self._latest.pop("map_cloud_inmem", None)
        cloud_msg = outcore_msg if outcore_msg is not None else inmem_msg
        if cloud_msg is not None:
            pts = self._cloud_to_array(cloud_msg)
            self._view.update_cloud(pts, color="#81c784")
            if not self._has_set_camera and pts.size:
                self._view.reset_camera()
                self._has_set_camera = True

        # Two odometry sources (fast_lio, cartographer) — same last-arrival
        # pattern as the cloud sources above.
        odom_msg = (self._latest.get("map_pose_odom_carto")
                    or self._latest.get("map_pose_odom"))
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
