"""위치/경로 페이지 — XY 궤적 + confidence 라벨."""
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pose_plot import PosePlot


class PosePage(BasePage):
    def __init__(self, ros_client, parent=None):
        super().__init__(ros_client, parent)
        self._plot = PosePlot()
        self._confidence_label = QLabel("Confidence: —")
        self._odom_label = QLabel("Odometry: —")
        self._loc_label = QLabel("Localization: —")

        info_row = QHBoxLayout()
        info_row.addWidget(self._odom_label)
        info_row.addWidget(self._loc_label)
        info_row.addWidget(self._confidence_label)
        info_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(info_row)
        layout.addWidget(self._plot, stretch=1)

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"pose_odom", "pose_loc_odom", "pose_confidence", "pose_path"}

    def _on_message(self, topic_id: str, msg) -> None:
        super()._on_message(topic_id, msg)
        if topic_id == "pose_odom":
            p = msg.pose.pose.position
            self._plot.append_pose(p.x, p.y)

    def refresh(self) -> None:
        odom = self._latest.get("pose_odom")
        if odom is not None:
            p = odom.pose.pose.position
            self._odom_label.setText(f"Odometry: ({p.x:+.2f}, {p.y:+.2f}, {p.z:+.2f})")

        loc = self._latest.get("pose_loc_odom")
        if loc is not None:
            p = loc.pose.pose.position
            self._loc_label.setText(f"Localization: ({p.x:+.2f}, {p.y:+.2f}, {p.z:+.2f})")

        conf = self._latest.get("pose_confidence")
        if conf is not None:
            self._confidence_label.setText(f"Confidence: {conf.data:.3f}")

        path = self._latest.get("pose_path")
        if path is not None:
            xs = [pose.pose.position.x for pose in path.poses]
            ys = [pose.pose.position.y for pose in path.poses]
            self._plot.set_path(xs, ys)

        self._plot.draw()
