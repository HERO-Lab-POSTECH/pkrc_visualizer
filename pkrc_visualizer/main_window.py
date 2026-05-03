"""햄버거 메뉴 + DrawerMenu + QStackedWidget을 담는 메인 윈도우."""
from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import (QMainWindow, QPushButton, QStackedWidget,
                             QVBoxLayout, QWidget)

from pkrc_visualizer.pages.image_page import ImagePage
from pkrc_visualizer.pages.mapping_page import MappingPage
from pkrc_visualizer.pages.pose_page import PosePage
from pkrc_visualizer.pages.slam_page import SlamPage
from pkrc_visualizer.widgets.drawer_menu import DrawerMenu
from pkrc_visualizer.widgets.status_bar import TopicHzStatusBar


PAGE_TITLES = ["SLAM", "위치/경로", "Sonar Mapping", "Sonar Image"]


class MainWindow(QMainWindow):
    def __init__(self, ros_client):
        super().__init__()
        self.setWindowTitle("PKRC Visualizer")
        self.resize(1280, 800)

        self._ros_client = ros_client

        # 햄버거 버튼 (좌상단)
        self._hamburger = QPushButton("☰", self)
        self._hamburger.setFixedSize(QSize(36, 36))
        self._hamburger.setStyleSheet(
            "QPushButton { background: #2d2d30; color: #f0f0f0; "
            "border: none; font-size: 18px; } "
            "QPushButton:hover { background: #3e3e42; }"
        )
        self._hamburger.move(8, 8)
        self._hamburger.raise_()
        self._hamburger.clicked.connect(self._toggle_drawer)

        # Stacked 페이지 컨테이너
        self._stack = QStackedWidget(self)
        self._stack.addWidget(SlamPage(ros_client))
        self._stack.addWidget(PosePage(ros_client))
        self._stack.addWidget(MappingPage(ros_client))
        self._stack.addWidget(ImagePage(ros_client))

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)
        self.setCentralWidget(container)

        # Status bar (토픽 Hz 표시) — drawer.select 이전에 설치 필요
        status_bar = TopicHzStatusBar(self._ros_client, self)
        status_bar.set_page_text(f"페이지: {PAGE_TITLES[0]}")
        self.setStatusBar(status_bar)

        # Drawer (overlay)
        self._drawer = DrawerMenu(PAGE_TITLES, self)
        self._drawer.itemClicked.connect(self._on_menu_clicked)
        self._drawer.select(0)
        self._stack.setCurrentIndex(0)

    def _toggle_drawer(self) -> None:
        self._drawer.toggle(self.height())

    def _on_menu_clicked(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self.statusBar().set_page_text(f"페이지: {PAGE_TITLES[index]}")
        self._drawer.close_drawer(self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Drawer가 열려 있으면 height 따라 갱신
        if self._drawer.isVisible():
            self._drawer.setGeometry(0, 0, self._drawer.DRAWER_WIDTH, self.height())
