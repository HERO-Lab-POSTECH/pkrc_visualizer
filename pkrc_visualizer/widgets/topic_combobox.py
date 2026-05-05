"""rqt_image_view-style topic combo: prefix autocomplete + topic_selected signal."""
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QComboBox, QCompleter


class TopicComboBox(QComboBox):
    topic_selected = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText("Topic name")
        completer = QCompleter([], self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchStartsWith)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)
        self.currentTextChanged.connect(self._on_text_changed)

    def set_candidates(self, names: list[str]) -> None:
        current = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItems(names)
        self.setCompleter(QCompleter(names, self))
        self.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.completer().setFilterMode(Qt.MatchStartsWith)
        if current and current in names:
            self.setCurrentText(current)
        else:
            self.setCurrentText("")
        self.blockSignals(False)

    def _on_text_changed(self, text: str) -> None:
        # Popup click or user-typed Enter; emit only if the value matches a candidate.
        if text and self.findText(text) >= 0:
            self.topic_selected.emit(text)
