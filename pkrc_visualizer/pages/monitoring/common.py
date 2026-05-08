"""Shared style + helpers for monitoring widgets.

Palette derived from the legacy HERO Robot 4WD web dashboard so the Qt
panel feels familiar to operators who switch from the browser UI.
"""
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

# Page-level
PAGE_BG = "#0d1929"        # deepest navy (page background)

# Panel (card) — slightly lighter navy so cards "float" above the page
PANEL_BG = "#152238"
PANEL_BG_INNER = "#1a2942"  # for inset elements (bars, lamps, image bg)
PANEL_BORDER = "#1e3a5f"

# Text
TEXT_PRIMARY = "#e2e8f0"
TEXT_DIM = "#64748b"
TEXT_LABEL = "#94a3b8"

# Accents (web GUI matched)
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_ORANGE = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_CYAN = "#06b6d4"

PANEL_QSS = (
    f"QFrame#StatusPanel {{ "
    f"background: {PANEL_BG}; "
    f"border: 1px solid {PANEL_BORDER}; "
    f"border-radius: 10px; "
    f"}}"
)

TITLE_QSS = (
    f"color: {TEXT_LABEL}; "
    f"font-size: 10px; "
    f"font-weight: bold; "
    f"letter-spacing: 0.5px; "
    f"background: transparent; "
    f"border: none;"
)


class StatusPanel(QFrame):
    """Card-style framed panel: small header (icon + title) + value area.

    Subclasses set value content via self._value (a QLabel that supports
    rich text) or replace it entirely.
    """

    def __init__(self, title: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPanel")
        self.setStyleSheet(PANEL_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(4)
        header.setContentsMargins(0, 0, 0, 0)
        if icon:
            icon_label = QLabel(icon)
            icon_label.setStyleSheet(
                f"color: {ACCENT_BLUE}; font-size: 11px; background: transparent; border: none;"
            )
            header.addWidget(icon_label)
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(TITLE_QSS)
        header.addWidget(title_label)
        header.addStretch(1)
        layout.addLayout(header)

        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 13px; background: transparent; border: none;"
        )
        self._value.setWordWrap(True)
        layout.addWidget(self._value, 1)
