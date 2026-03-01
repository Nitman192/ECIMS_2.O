"""Application style loader for central QSS."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication


def get_stylesheet() -> str:
    """Load stylesheet from central style.qss file."""
    qss_path = Path(__file__).resolve().with_name("style.qss")
    return qss_path.read_text(encoding="utf-8")


def apply_theme(app: QApplication) -> None:
    """Apply stylesheet to the whole application."""
    app.setProperty("theme", "default")
    app.setStyleSheet(get_stylesheet())
