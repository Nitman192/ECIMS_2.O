"""Placeholder page for deferred functionality."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    """Simple placeholder for future phases."""

    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h2>{title}</h2>"))
        layout.addWidget(QLabel("Coming in Phase 3"))
