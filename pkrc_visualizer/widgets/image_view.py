"""sensor_msgs/Image + sensor_msgs/CompressedImage → QPixmap."""
from typing import Optional, Union

import cv2
import numpy as np
from cv_bridge import CvBridge, CvBridgeError
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel
from sensor_msgs.msg import CompressedImage, Image


ImageLike = Union[Image, CompressedImage]


class ImageView(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #1e1e1e; color: #888;")
        self.setText("(no image)")
        self._bridge = CvBridge()

    def set_image_msg(self, msg: Optional[ImageLike]) -> None:
        if msg is None:
            return
        try:
            qimg = self._convert(msg)
        except (CvBridgeError, ValueError, cv2.error) as exc:
            self.setText(f"convert failed: {exc}")
            return
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pixmap)

    def _convert(self, msg: ImageLike) -> QImage:
        if isinstance(msg, CompressedImage):
            return self._compressed_to_qimage(msg)
        return self._raw_image_to_qimage(msg)

    def _raw_image_to_qimage(self, msg: Image) -> QImage:
        encoding = msg.encoding.lower()
        if "mono" in encoding or encoding in ("8uc1", "16uc1"):
            cv = self._bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")
            return self._mono_to_qimage(cv)
        cv = self._bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8")
        return self._rgb_to_qimage(cv)

    def _compressed_to_qimage(self, msg: CompressedImage) -> QImage:
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError(f"cv2.imdecode failed (format={msg.format})")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return self._rgb_to_qimage(rgb)

    @staticmethod
    def _rgb_to_qimage(cv: np.ndarray) -> QImage:
        h, w, _ = cv.shape
        return QImage(cv.tobytes(), w, h, w * 3, QImage.Format_RGB888).copy()

    @staticmethod
    def _mono_to_qimage(cv: np.ndarray) -> QImage:
        h, w = cv.shape
        return QImage(cv.tobytes(), w, h, w, QImage.Format_Grayscale8).copy()
