"""MonitoringPage: dispatch table includes new sonar entries."""
from unittest.mock import MagicMock

from pkrc_visualizer.pages.monitoring.sonar_image_widget import \
    SonarImageWidget
from pkrc_visualizer.pages.monitoring_page import MonitoringPage


def _stub_ros_client():
    rc = MagicMock()
    rc.lookup_map_from_odom.return_value = None
    return rc


def test_page_uses_sonar_image_widget(qtbot):
    page = MonitoringPage(_stub_ros_client())
    qtbot.addWidget(page)
    assert isinstance(page._sonar, SonarImageWidget)


def test_dispatch_has_sonar_entries(qtbot):
    page = MonitoringPage(_stub_ros_client())
    qtbot.addWidget(page)
    assert "mon_sonar_m750d" in page._dispatch
    assert "mon_sonar_m3000d" in page._dispatch
    assert page._dispatch["mon_sonar_m750d"] == page._sonar.set_image_msg
    assert page._dispatch["mon_sonar_m3000d"] == page._sonar.set_image_msg
