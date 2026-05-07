"""Topic-to-page mapping kept in one place. Tweak per deployment."""
from dataclasses import dataclass
from typing import Type

from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry, OccupancyGrid, Path
from std_msgs.msg import Float32
from visualization_msgs.msg import MarkerArray


@dataclass(frozen=True)
class TopicSpec:
    topic_id: str       # Routing key inside a page (e.g. "slam_cloud")
    topic_name: str     # ROS2 topic name
    msg_type: Type      # Message class
    qos_best_effort: bool = False        # If True, subscribe with BEST_EFFORT QoS
    qos_transient_local: bool = False    # If True, subscribe with TRANSIENT_LOCAL durability
                                         # (latched publishers like prior maps)


# Page key → list of topics
TOPICS = {
    "slam": [
        # Subscribe to body-frame scan and lift to odom→map in the page using TF.
        # Avoids dependence on /slam/fast_lio/debug/points_world (which is the same
        # scan pre-transformed to odom but lives in the debug namespace).
        TopicSpec("slam_cloud", "/slam/fast_lio/points_body", PointCloud2, qos_best_effort=True),
        # Two prior-grid sources are subscribed in parallel: fast_lio_loc and
        # cartographer. Operationally only one SLAM engine is active at a time
        # (Q1 confirmed), so the SlamPage routes whichever message arrives most
        # recently into the same PriorMapActor — last-arrival-wins.
        TopicSpec("slam_prior_grid", "/slam/fast_lio_loc/occupancy_grid",
                  OccupancyGrid, qos_transient_local=True),
        TopicSpec("slam_prior_grid_carto", "/slam/cartographer/map",
                  OccupancyGrid, qos_transient_local=True),
    ],
    "pose": [
        TopicSpec("pose_odom", "/slam/fast_lio/odometry", Odometry),
        TopicSpec("pose_loc_odom", "/slam/fast_lio_loc/odometry", Odometry),
        TopicSpec("pose_confidence", "/slam/fast_lio_loc/confidence", Float32),
        # PosePlot accumulates trajectory from pose_odom directly (30s window),
        # so /slam/fast_lio/debug/path is no longer needed.
    ],
    "mapping": [
        TopicSpec("map_cloud", "/perception/sonar_3d/points", PointCloud2, qos_best_effort=True),
        TopicSpec("map_markers", "/perception/sonar_3d_visualizer/markers", MarkerArray, qos_best_effort=True),
    ],
}


def all_topics() -> list[TopicSpec]:
    """Flat list of every page's topics."""
    return [t for topics in TOPICS.values() for t in topics]
