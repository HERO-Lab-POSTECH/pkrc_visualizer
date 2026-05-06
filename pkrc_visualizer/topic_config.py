"""Topic-to-page mapping kept in one place. Tweak per deployment."""
from dataclasses import dataclass
from typing import Type

from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry, Path
from std_msgs.msg import Float32
from visualization_msgs.msg import MarkerArray


@dataclass(frozen=True)
class TopicSpec:
    topic_id: str       # Routing key inside a page (e.g. "slam_cloud")
    topic_name: str     # ROS2 topic name
    msg_type: Type      # Message class
    qos_best_effort: bool = False  # If True, subscribe with BEST_EFFORT QoS


# Page key → list of topics
TOPICS = {
    "slam": [
        TopicSpec("slam_cloud", "/fast_lio/debug/points_world", PointCloud2, qos_best_effort=True),
        TopicSpec("slam_path", "/fast_lio/debug/path", Path, qos_best_effort=True),
    ],
    "pose": [
        TopicSpec("pose_odom", "/localization/fast_lio/odometry", Odometry),
        TopicSpec("pose_loc_odom", "/localization/fast_lio_loc/odometry", Odometry),
        TopicSpec("pose_confidence", "/localization/fast_lio_loc/confidence", Float32),
        TopicSpec("pose_path", "/fast_lio/debug/path", Path, qos_best_effort=True),
    ],
    "mapping": [
        TopicSpec("map_cloud", "/perception/sonar_3d/points", PointCloud2, qos_best_effort=True),
        TopicSpec("map_markers", "/perception/sonar_3d_visualizer/markers", MarkerArray, qos_best_effort=True),
    ],
}


def all_topics() -> list[TopicSpec]:
    """Flat list of every page's topics."""
    return [t for topics in TOPICS.values() for t in topics]
