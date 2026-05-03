"""좌측에서 슬라이드되는 메뉴 패널. itemClicked(int) signal로 페이지 인덱스 발신."""
from PyQt5.QtCore import QPropertyAnimation, QRect, pyqtSignal
from PyQt5.QtWidgets import QFrame, QListWidget, QVBoxLayout


class DrawerMenu(QFrame):
    itemClicked = pyqtSignal(int)  # 선택된 페이지 인덱스

    DRAWER_WIDTH = 220

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("DrawerMenu")
        self.setStyleSheet(
            "#DrawerMenu { background-color: #2d2d30; border-right: 1px solid #444; } "
            "QListWidget { background: transparent; color: #f0f0f0; "
            "font-size: 14px; padding: 8px; border: none; } "
            "QListWidget::item { padding: 10px 12px; } "
            "QListWidget::item:selected { background-color: #094771; }"
        )
        self._list = QListWidget(self)
        self._list.addItems(items)
        self._list.currentRowChanged.connect(self.itemClicked.emit)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 0)  # 햄버거 버튼 공간
        layout.addWidget(self._list)

        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setDuration(180)
        self._open = False
        self.hide()

    def toggle(self, parent_height: int) -> None:
        if self._open:
            self.close_drawer(parent_height)
        else:
            self.open_drawer(parent_height)

    def open_drawer(self, parent_height: int) -> None:
        self.show()
        self._animation.stop()
        self._animation.setStartValue(QRect(-self.DRAWER_WIDTH, 0, self.DRAWER_WIDTH, parent_height))
        self._animation.setEndValue(QRect(0, 0, self.DRAWER_WIDTH, parent_height))
        self._animation.start()
        self._open = True

    def close_drawer(self, parent_height: int) -> None:
        self._animation.stop()
        self._animation.setStartValue(QRect(0, 0, self.DRAWER_WIDTH, parent_height))
        self._animation.setEndValue(QRect(-self.DRAWER_WIDTH, 0, self.DRAWER_WIDTH, parent_height))
        self._animation.start()
        self._animation.finished.connect(self._on_close_done)
        self._open = False

    def _on_close_done(self) -> None:
        try:
            self._animation.finished.disconnect(self._on_close_done)
        except TypeError:
            pass
        self.hide()

    def select(self, index: int) -> None:
        self._list.setCurrentRow(index)
