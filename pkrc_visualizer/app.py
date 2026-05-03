"""Entry point: QApplication + RosClient + MainWindow."""
import signal
import sys

import rclpy
from PyQt5.QtWidgets import QApplication, QMessageBox

from pkrc_visualizer.main_window import MainWindow
from pkrc_visualizer.ros_client import RosClient
from pkrc_visualizer.topic_config import all_topics


def main(args=None) -> int:
    rclpy.init(args=args)
    app = QApplication(sys.argv)

    # pyvistaqt가 import 안 되면 시작 시 안내
    try:
        import pyvistaqt  # noqa: F401
    except ImportError:
        QMessageBox.critical(
            None, "의존성 누락",
            "pyvistaqt 미설치. 다음을 실행:\n\npip install --user pyvistaqt pyvista",
        )
        rclpy.shutdown()
        return 1

    ros_client = RosClient(all_topics())
    ros_client.start()

    window = MainWindow(ros_client)
    window.show()

    # Ctrl+C로 종료 가능하게
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    try:
        exit_code = app.exec_()
    finally:
        ros_client.stop()
        if rclpy.ok():
            rclpy.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
