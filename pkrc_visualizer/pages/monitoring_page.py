"""Monitoring page — top status bar (20%) + main visualization (80%).

All subscribed topics are tagged with the "mon_" prefix in topic_config.py;
this page filters by that prefix and dispatches each message to the right
widget.
"""
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.pages.monitoring.common import PAGE_BG
from pkrc_visualizer.pages.monitoring.battery_widget import BatteryWidget
from pkrc_visualizer.pages.monitoring.camera_widget import CameraWidget
from pkrc_visualizer.pages.monitoring.joystick_widget import JoystickWidget
from pkrc_visualizer.pages.monitoring.motor_currents_widget import \
    MotorCurrentsWidget
from pkrc_visualizer.pages.monitoring.relay_lamps_widget import \
    RelayLampsWidget
from pkrc_visualizer.pages.monitoring.sonar_image_widget import \
    SonarImageWidget
from pkrc_visualizer.pages.monitoring.sonar_tilt_widget import SonarTiltWidget
from pkrc_visualizer.pages.monitoring.system_led_widget import SystemLedWidget
from pkrc_visualizer.pages.monitoring.topdown_map_widget import \
    TopdownMapWidget

TOPIC_PREFIX = "mon_"


class MonitoringPage(BasePage):
    def __init__(self, ros_client, parent=None):
        super().__init__(ros_client, parent)
        self.setStyleSheet(
            f"MonitoringPage {{ background: {PAGE_BG}; }}"
        )
        self.setAutoFillBackground(True)

        # Top status bar (20%)
        self._joy = JoystickWidget()
        self._motors = MotorCurrentsWidget()
        self._battery = BatteryWidget()
        self._relays = RelayLampsWidget()
        self._tilt = SonarTiltWidget()
        self._sys_led = SystemLedWidget()

        top = QWidget()
        top.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(8)
        for w in (self._joy, self._motors, self._battery,
                  self._relays, self._tilt, self._sys_led):
            top_layout.addWidget(w, 1)

        # Main visualization (80%)
        self._map = TopdownMapWidget()
        self._sonar = SonarImageWidget()
        self._camera = CameraWidget()

        bottom = QWidget()
        bottom.setStyleSheet("background: transparent;")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(8, 4, 8, 8)
        bottom_layout.setSpacing(8)
        for w in (self._map, self._sonar, self._camera):
            bottom_layout.addWidget(w, 1)

        # Compose 20%/80% vertical split
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(top, 1)
        outer.addWidget(bottom, 4)

        self._dispatch = {
            "mon_camera":       self._camera.update_from_msg,
            "mon_odom":         self._map.update_from_msg,
            "mon_joy":          self._joy.update_from_msg,
            "mon_motors":       self._motors.update_from_msg,
            "mon_relays":       self._relays.update_from_msg,
            "mon_battery":      self._battery.update_from_msg,
            "mon_system":       self._sys_led.update_system,
            "mon_led":          self._sys_led.update_led,
            "mon_tilt_cur":     self._tilt.update_current,
            "mon_tilt_goal":    self._tilt.update_goal,
            "mon_sonar_m750d":  self._sonar.set_image_msg,
            "mon_sonar_m3000d": self._sonar.set_image_msg,
        }

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id.startswith(TOPIC_PREFIX)

    def refresh(self) -> None:
        # 10Hz tick — fan out the latest cached message of every topic.
        # Widgets are idempotent: rendering the same message twice is a no-op
        # for QLabel/setText, and the trail/canvas widgets only append on
        # update_pose which is called from update_from_msg directly. To avoid
        # re-appending the same odom sample, we drain self._latest each tick.
        if not self._latest:
            return
        snapshot = self._latest
        self._latest = {}
        for tid, msg in snapshot.items():
            handler = self._dispatch.get(tid)
            if handler is not None:
                try:
                    handler(msg)
                except Exception:
                    # A bad single message must not kill the whole tick.
                    pass
