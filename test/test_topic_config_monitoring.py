"""topic_config: Monitoring page exposes 2D-map + sonar topic specs."""
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import CompressedImage

from pkrc_visualizer.topic_config import TOPICS


def _by_id(specs, topic_id):
    for s in specs:
        if s.topic_id == topic_id:
            return s
    raise KeyError(topic_id)


def test_monitoring_has_map_carto():
    spec = _by_id(TOPICS["monitoring"], "mon_map_carto")
    assert spec.topic_name == "/slam/cartographer/map"
    assert spec.msg_type is OccupancyGrid
    assert spec.qos_transient_local is True
    assert spec.qos_best_effort is False


def test_monitoring_has_map_fastlio():
    spec = _by_id(TOPICS["monitoring"], "mon_map_fastlio")
    assert spec.topic_name == "/slam/fast_lio_loc/occupancy_grid"
    assert spec.msg_type is OccupancyGrid
    assert spec.qos_transient_local is True


def test_monitoring_has_sonar_m750d():
    spec = _by_id(TOPICS["monitoring"], "mon_sonar_m750d")
    assert spec.topic_name == "/sensor/sonar/oculus/m750d/image/compressed"
    assert spec.msg_type is CompressedImage
    assert spec.qos_best_effort is True


def test_monitoring_has_sonar_m3000d():
    spec = _by_id(TOPICS["monitoring"], "mon_sonar_m3000d")
    assert spec.topic_name == "/sensor/sonar/oculus/m3000d/image/compressed"
    assert spec.msg_type is CompressedImage
    assert spec.qos_best_effort is True
