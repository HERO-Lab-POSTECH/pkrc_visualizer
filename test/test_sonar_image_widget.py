"""SonarImageWidget: title bar + ImageView wrapping."""
import numpy as np
from PyQt5.QtWidgets import QLabel
from sensor_msgs.msg import Image

from pkrc_visualizer.pages.monitoring.sonar_image_widget import \
    SonarImageWidget
from pkrc_visualizer.widgets.image_view import ImageView


def test_constructs_with_title_and_view(qtbot):
    w = SonarImageWidget()
    qtbot.addWidget(w)
    labels = w.findChildren(QLabel)
    titles = [lab.text() for lab in labels if "소나" in lab.text()]
    assert titles, "expected '소나' in some QLabel"
    views = w.findChildren(ImageView)
    assert len(views) == 1


def test_empty_state_text_is_korean(qtbot):
    w = SonarImageWidget()
    qtbot.addWidget(w)
    view = w.findChildren(ImageView)[0]
    assert "대기 중" in view.text()


def test_set_image_msg_forwards_to_view(qtbot):
    w = SonarImageWidget()
    qtbot.addWidget(w)
    msg = Image()
    msg.height = 4
    msg.width = 4
    msg.encoding = "rgb8"
    msg.step = 12
    msg.data = (np.zeros((4, 4, 3), dtype=np.uint8)).tobytes()
    w.set_image_msg(msg)
    view = w.findChildren(ImageView)[0]
    assert view.pixmap() is not None
