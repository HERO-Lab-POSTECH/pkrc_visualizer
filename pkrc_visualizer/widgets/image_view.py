"""sensor_msgs/Image → QPixmap. RGB와 mono 인코딩 분기 처리."""
from typing import Optional

import numpy as np
from cv_bridge import CvBridge, CvBridgeError
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel
from sensor_msgs.msg import Image


class ImageView(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #1e1e1e; color: #888;")
        self.setText("대기 중…")
        self._bridge = CvBridge()

    def set_image_msg(self, msg: Optional[Image]) -> None:
        if msg is None:
            return
        try:
            qimg = self._convert(msg)
        except (CvBridgeError, ValueError) as exc:
            self.setText(f"변환 실패: {exc}")
            return
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pixmap)

    def _convert(self, msg: Image) -> QImage:
        encoding = msg.encoding.lower()
        if "mono" in encoding or encoding in ("8uc1", "16uc1"):
            cv = self._bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")
            return self._mono_to_qimage(cv)
        cv = self._bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8")
        return self._rgb_to_qimage(cv)

    @staticmethod
    def _rgb_to_qimage(cv: np.ndarray) -> QImage:
        h, w, _ = cv.shape
        return QImage(cv.tobytes(), w, h, w * 3, QImage.Format_RGB888).copy()

    @staticmethod
    def _mono_to_qimage(cv: np.ndarray) -> QImage:
        h, w = cv.shape
        return QImage(cv.tobytes(), w, h, w, QImage.Format_Grayscale8).copy()
