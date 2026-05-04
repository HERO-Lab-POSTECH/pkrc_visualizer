"""토픽 → 페이지 매핑 한 곳 관리. 운용 환경마다 수정될 핫스팟."""
from dataclasses import dataclass
from typing import Type

from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry, Path
from std_msgs.msg import Float32
from visualization_msgs.msg import MarkerArray


@dataclass(frozen=True)
class TopicSpec:
    topic_id: str       # 페이지 내부에서 라우팅할 키 (예: "slam_cloud")
    topic_name: str     # ROS2 토픽 이름
    msg_type: Type      # 메시지 클래스
    qos_best_effort: bool = False  # True면 BEST_EFFORT QoS로 구독


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
    """모든 페이지의 토픽을 평탄화한 리스트."""
    return [t for topics in TOPICS.values() for t in topics]
