"""Session lock overlay dialog that blocks interaction until dismissed."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from la_gui.ui.style_helpers import set_primary


class LockOverlayDialog(QDialog):
    """Full-window modal lock overlay with simple unlock confirmation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Session Locked")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        self.info_label = QLabel("Session Locked")
        self.details_label = QLabel("Idle timeout reached.")

        self.unlock_button = QPushButton("Unlock Session UI")
        set_primary(self.unlock_button)
        self.unlock_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)
        layout.addWidget(self.info_label)
        layout.addWidget(self.details_label)
        layout.addWidget(self.unlock_button)

        self.setStyleSheet(
            "QDialog { background: rgba(15, 23, 42, 210); }"
            "QLabel { color: #ffffff; font-size: 15px; }"
            "QPushButton { min-width: 220px; }"
        )

    def open_for_reason(self, reason: str) -> int:
        parent = self.parentWidget()
        if parent:
            self.resize(parent.size())
            self.move(parent.pos())
        self.details_label.setText(reason)
        return self.exec()
