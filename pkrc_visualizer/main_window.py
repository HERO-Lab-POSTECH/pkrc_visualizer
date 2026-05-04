"""Top toolbar (hamburger) + DrawerMenu + QStackedWidget container."""
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import (QAction, QMainWindow, QStackedWidget, QToolBar,
                             QVBoxLayout, QWidget)

from pkrc_visualizer.pages.image_page import ImagePage
from pkrc_visualizer.pages.mapping_page import MappingPage
from pkrc_visualizer.pages.pose_page import PosePage
from pkrc_visualizer.pages.slam_page import SlamPage
from pkrc_visualizer.widgets.drawer_menu import DrawerMenu
from pkrc_visualizer.widgets.status_bar import TopicHzStatusBar


PAGE_TITLES = ["SLAM", "Pose / Path", "Sonar Mapping", "Sonar Image"]


class MainWindow(QMainWindow):
    def __init__(self, ros_client, display_store):
        super().__init__()
        self.setWindowTitle("PKRC Visualizer")
        self.resize(1280, 800)

        self._ros_client = ros_client
        self._display_store = display_store

        # Stacked page container
        self._stack = QStackedWidget()
        self._stack.addWidget(SlamPage(ros_client, display_store))
        self._stack.addWidget(PosePage(ros_client))
        self._stack.addWidget(MappingPage(ros_client, display_store))
        self._stack.addWidget(ImagePage(ros_client, display_store))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)
        self.setCentralWidget(container)

        # Top toolbar with hamburger — Qt-managed reserved area, always visible
        # above PyVista's native OpenGL canvas.
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet(
            "QToolBar { background: #2d2d30; border: none; padding: 4px; } "
            "QToolButton { color: #ffffff; background: #094771; border: 1px solid #4fc3f7; "
            "border-radius: 4px; padding: 6px 12px; font-size: 14px; font-weight: bold; } "
            "QToolButton:hover { background: #1177bb; border-color: #ffffff; }"
        )
        self._menu_action = QAction("☰  Menu", self)
        self._menu_action.triggered.connect(self._toggle_drawer)
        toolbar.addAction(self._menu_action)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # Status bar (topic Hz) — install before drawer.select(0) so set_page_text works
        status_bar = TopicHzStatusBar(self._ros_client, self)
        status_bar.set_page_text(f"Page: {PAGE_TITLES[0]}")
        self.setStatusBar(status_bar)

        # Drawer (overlay over the central widget area)
        self._drawer = DrawerMenu(PAGE_TITLES, container)
        self._drawer.itemClicked.connect(self._on_menu_clicked)
        self._drawer.select(0)
        self._stack.setCurrentIndex(0)

    def _toggle_drawer(self) -> None:
        self._drawer.toggle(self.centralWidget().height())
        self._drawer.raise_()

    def _on_menu_clicked(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self.statusBar().set_page_text(f"Page: {PAGE_TITLES[index]}")
        self._drawer.close_drawer(self.centralWidget().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._drawer.isVisible():
            h = self.centralWidget().height()
            self._drawer.setGeometry(0, 0, self._drawer.DRAWER_WIDTH, h)
