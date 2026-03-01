"""Application theme (QSS) loader for consistent professional styling."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication


def get_stylesheet() -> str:
    """Load stylesheet from central style.qss file if present."""
    qss_path = Path(__file__).resolve().with_name("style.qss")
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")

    # Fallback minimal theme if style.qss missing
    return """
    QWidget { background: #1b1f24; color: #e6e9ef; font-size: 12px; }
    QMainWindow { background: #1b1f24; }
    QPushButton { border-radius: 6px; padding: 6px 8px; }
    """


def apply_theme(app: QApplication) -> None:
    app.setProperty("theme", "default")
    app.setStyleSheet(get_stylesheet())