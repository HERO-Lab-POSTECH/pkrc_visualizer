"""Topic-to-page mapping kept in one place. Tweak per deployment."""
from dataclasses import dataclass
from typing import Type

from sensor_msgs.msg import BatteryState, CompressedImage, Joy, PointCloud2
from nav_msgs.msg import Odometry, OccupancyGrid, Path
from std_msgs.msg import Float32, Float32MultiArray, String, UInt8
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
        # SlamPage + PosePage share these. Two odometry sources subscribed in
        # parallel (last-arrival wins) so the robot pose renders whether SLAM
        # is fast_lio or cartographer.
        TopicSpec("pose_odom", "/slam/fast_lio/odometry", Odometry),
        TopicSpec("pose_odom_carto", "/slam/cartographer/odometry", Odometry),
        TopicSpec("pose_loc_odom", "/slam/fast_lio_loc/odometry", Odometry),
        TopicSpec("pose_confidence", "/slam/fast_lio_loc/confidence", Float32),
        # PosePlot accumulates trajectory from pose_odom directly (30s window),
        # so /slam/fast_lio/debug/path is no longer needed.
    ],
    "mapping": [
        # Two cloud sources subscribed in parallel: 3d_mapper publishes
        # /perception/sonar_3d/points only in in-memory mode, map_visualizer
        # publishes /perception/sonar_3d_visualizer/points only in out-of-core
        # mode. Operationally only one mode runs at a time, so MappingPage
        # routes whichever message arrives most recently into the same cloud
        # actor — last-arrival-wins.
        TopicSpec("map_cloud_inmem",   "/perception/sonar_3d/points",
                  PointCloud2, qos_best_effort=True),
        TopicSpec("map_cloud_outcore", "/perception/sonar_3d_visualizer/points",
                  PointCloud2, qos_best_effort=True),
        # Robot pose: same parallel pattern as pose section so the arrow
        # renders under either SLAM stack.
        TopicSpec("map_pose_odom",       "/slam/fast_lio/odometry",   Odometry),
        TopicSpec("map_pose_odom_carto", "/slam/cartographer/odometry", Odometry),
    ],
    "monitoring": [
        TopicSpec("mon_camera",    "/camera/image/compressed",  CompressedImage,    qos_best_effort=True),
        # Two odometry sources subscribed in parallel (last-arrival wins) so
        # the robot pose renders whether SLAM is fast_lio or cartographer.
        TopicSpec("mon_odom",        "/slam/fast_lio/odometry",   Odometry,         qos_best_effort=True),
        TopicSpec("mon_odom_carto",  "/slam/cartographer/odometry", Odometry,       qos_best_effort=True),
        TopicSpec("mon_joy",       "/joy",                      Joy,                qos_best_effort=True),
        TopicSpec("mon_motors",    "/pkrc/motors/cmd_current",  Float32MultiArray,  qos_best_effort=True),
        TopicSpec("mon_relays",    "/pkrc/relays/state",        UInt8,              qos_best_effort=True),
        TopicSpec("mon_battery",   "/pkrc/battery/state",       BatteryState,       qos_best_effort=True),
        TopicSpec("mon_system",    "/pkrc/system/state",        Float32MultiArray,  qos_best_effort=True),
        TopicSpec("mon_led",       "/pkrc/led/color",           String,             qos_best_effort=True),
        TopicSpec("mon_tilt_cur",  "/sonar/tilt/current_angle", Float32,            qos_best_effort=True),
        TopicSpec("mon_tilt_goal", "/sonar/tilt/goal_angle",    Float32,            qos_best_effort=True),
        # 2D map sources — both engines subscribed in parallel; whichever
        # SLAM stack is running publishes. transient_local so a Monitoring
        # page opened *after* SLAM started still receives the latest map.
        TopicSpec("mon_map_carto",   "/slam/cartographer/map",
                  OccupancyGrid, qos_transient_local=True),
        TopicSpec("mon_map_fastlio", "/slam/fast_lio_loc/occupancy_grid",
                  OccupancyGrid, qos_transient_local=True),
        # Sonar polar image — auto-detect by message arrival.
        TopicSpec("mon_sonar_m750d",  "/sensor/sonar/oculus/m750d/image/compressed",
                  CompressedImage, qos_best_effort=True),
        TopicSpec("mon_sonar_m3000d", "/sensor/sonar/oculus/m3000d/image/compressed",
                  CompressedImage, qos_best_effort=True),
    ],
}


def all_topics() -> list[TopicSpec]:
    """Flat list of every page's topics."""
    return [t for topics in TOPICS.values() for t in topics]
