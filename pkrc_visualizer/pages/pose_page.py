"""Pose / Path page: XY trajectory (built from pose_odom over a 30s window)
+ confidence label. The trajectory replaces the old /slam/fast_lio/debug/path
subscription — odometry already streams every pose, and PosePlot now
expires older entries by time so memory stays bounded."""
from time import monotonic

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.pose_plot import PosePlot


class PosePage(BasePage):
    def __init__(self, ros_client, parent=None):
        super().__init__(ros_client, parent)
        self._plot = PosePlot()
        self._confidence_label = QLabel("Confidence: -")
        self._odom_label = QLabel("Odometry: -")
        self._loc_label = QLabel("Localization: -")

        info_row = QHBoxLayout()
        info_row.addWidget(self._odom_label)
        info_row.addWidget(self._loc_label)
        info_row.addWidget(self._confidence_label)
        info_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(info_row)
        layout.addWidget(self._plot, stretch=1)

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in {"pose_odom", "pose_loc_odom", "pose_confidence"}

    def _on_message(self, topic_id: str, msg) -> None:
        super()._on_message(topic_id, msg)
        if topic_id == "pose_odom":
            p = msg.pose.pose.position
            # monotonic() matches the cloud accumulator's clock so the path
            # window and cloud decay age together.
            self._plot.append_pose(monotonic(), p.x, p.y)

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

        self._plot.draw()
