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
        TopicSpec("slam_cloud", "/fast_lio/debug/cloud_registered", PointCloud2, qos_best_effort=True),
        TopicSpec("slam_path", "/fast_lio/path", Path),
    ],
    "pose": [
        TopicSpec("pose_odom", "/fast_lio/odometry", Odometry),
        TopicSpec("pose_loc_odom", "/fast_lio/localization/odometry", Odometry),
        TopicSpec("pose_confidence", "/fast_lio/localization/confidence", Float32),
        TopicSpec("pose_path", "/fast_lio/path", Path),
    ],
    "mapping": [
        TopicSpec("map_cloud", "/sonar_3d_mapper/point_cloud", PointCloud2, qos_best_effort=True),
        TopicSpec("map_markers", "/sonar_3d_mapper/marker_array", MarkerArray),
    ],
}


def all_topics() -> list[TopicSpec]:
    """Flat list of every page's topics."""
    return [t for topics in TOPICS.values() for t in topics]
