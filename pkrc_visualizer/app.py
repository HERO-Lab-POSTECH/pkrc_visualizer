"""Entry point: QApplication + RosClient + MainWindow."""
import signal
import sys

import rclpy
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QMessageBox

from pkrc_visualizer.display_settings import DisplaySettingsStore
from pkrc_visualizer.main_window import MainWindow
from pkrc_visualizer.ros_client import RosClient
from pkrc_visualizer.topic_config import all_topics


def _apply_dark_theme(app: QApplication) -> None:
    """Force a dark Fusion theme so widgets without an explicit stylesheet
    still get readable contrast (light text on dark backgrounds)."""
    app.setStyle("Fusion")
    palette = QPalette()
    bg = QColor(45, 45, 48)
    base = QColor(30, 30, 30)
    text = QColor(240, 240, 240)
    button = QColor(62, 62, 66)
    highlight = QColor(9, 71, 113)
    disabled = QColor(127, 127, 127)
    palette.setColor(QPalette.Window, bg)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, base)
    palette.setColor(QPalette.AlternateBase, bg)
    palette.setColor(QPalette.ToolTipBase, bg)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, button)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, text)
    palette.setColor(QPalette.Link, QColor(79, 195, 247))
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled)
    app.setPalette(palette)


def main(args=None) -> int:
    rclpy.init(args=args)
    app = QApplication(sys.argv)
    _apply_dark_theme(app)

    # Show a startup error if pyvistaqt cannot be imported.
    try:
        import pyvistaqt  # noqa: F401
    except ImportError:
        QMessageBox.critical(
            None, "Missing dependency",
            "pyvistaqt is not installed. Run:\n\npip install --user pyvistaqt pyvista",
        )
        rclpy.shutdown()
        return 1

    ros_client = RosClient(all_topics())
    ros_client.start()

    display_store = DisplaySettingsStore()
    window = MainWindow(ros_client, display_store)
    window.show()

    # Allow Ctrl+C to terminate.
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
