"""Overlay button anchored to the bottom-left of its parent widget.

Repositions itself on parent resize via an event filter. When parented
to a widget that hosts a native VTK canvas (PyVistaView), the WA_NativeWindow
attribute is set so the button z-orders above the native sibling.
"""
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QPushButton


BUTTON_SIZE = 32
MARGIN_LEFT = 8
MARGIN_BOTTOM = 8


class SettingsButton(QPushButton):
    def __init__(self, parent):
        super().__init__("⚙", parent)
        self.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        self.setStyleSheet(
            "QPushButton { background:#2d2d30; color:#f0f0f0; border:none; "
            "border-radius:4px; font-size:18px; } "
            "QPushButton:hover { background:#3e3e42; }"
        )
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_NativeWindow)   # z-order over native VTK canvas
        parent.installEventFilter(self)
        self._reposition()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize and obj is self.parent():
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self):
        p = self.parent()
        self.move(MARGIN_LEFT, p.height() - BUTTON_SIZE - MARGIN_BOTTOM)
        self.raise_()
