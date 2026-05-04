"""ImageView가 Image / CompressedImage 둘 다 처리하는지 검증."""
import numpy as np
import pytest

from sensor_msgs.msg import CompressedImage, Image

from pkrc_visualizer.widgets.image_view import ImageView


@pytest.fixture
def image_msg():
    arr = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
    msg = Image()
    msg.height, msg.width = 64, 64
    msg.encoding = "rgb8"
    msg.step = 64 * 3
    msg.data = arr.tobytes()
    return msg


@pytest.fixture
def compressed_msg():
    import cv2  # cv2.imencode for jpeg
    arr = (np.random.rand(64, 64, 3) * 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", arr)
    assert ok
    msg = CompressedImage()
    msg.format = "jpeg"
    msg.data = buf.tobytes()
    return msg


def test_image_view_accepts_image(qtbot, image_msg):
    view = ImageView()
    qtbot.addWidget(view)
    view.set_image_msg(image_msg)
    assert view.pixmap() is not None
    assert not view.pixmap().isNull()


def test_image_view_accepts_compressed_image(qtbot, compressed_msg):
    view = ImageView()
    qtbot.addWidget(view)
    view.set_image_msg(compressed_msg)
    assert view.pixmap() is not None
    assert not view.pixmap().isNull()
