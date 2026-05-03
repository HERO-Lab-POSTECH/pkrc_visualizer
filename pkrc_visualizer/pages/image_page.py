"""Sonar Image 페이지 — Oculus / Ping360 / Sonoptix 탭."""
from PyQt5.QtWidgets import QTabWidget, QVBoxLayout

from pkrc_visualizer.pages.base_page import BasePage
from pkrc_visualizer.widgets.image_view import ImageView


# (탭 라벨, topic_id)
TABS = [
    ("Oculus M750D", "oculus_m750d_fan"),
    ("Oculus M3000D", "oculus_m3000d_fan"),
    ("Ping360", "ping360_image"),
    ("Sonoptix", "sonoptix_image"),
]


class ImagePage(BasePage):
    def __init__(self, ros_client, parent=None):
        super().__init__(ros_client, parent)
        self._views: dict[str, ImageView] = {}

        tabs = QTabWidget()
        for label, topic_id in TABS:
            view = ImageView()
            self._views[topic_id] = view
            tabs.addTab(view, label)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def _is_my_topic(self, topic_id: str) -> bool:
        return topic_id in self._views

    def refresh(self) -> None:
        for topic_id, view in self._views.items():
            msg = self._latest.get(topic_id)
            if msg is not None:
                view.set_image_msg(msg)
