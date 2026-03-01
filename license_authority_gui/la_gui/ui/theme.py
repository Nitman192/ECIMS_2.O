"""Application theme (QSS) for consistent professional styling."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


def get_stylesheet() -> str:
    return """
    QWidget { background: #1b1f24; color: #e6e9ef; font-size: 12px; }
    QMainWindow { background: #1b1f24; }
    QListWidget, QTextEdit, QLineEdit, QSpinBox { background: #232a31; border: 1px solid #3a4653; border-radius: 6px; padding: 6px; }
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus { border: 1px solid #4f8cff; }
    QPushButton { background: #2d3742; border: 1px solid #455466; border-radius: 6px; padding: 8px 10px; }
    QPushButton:hover { background: #364353; }
    QPushButton:pressed { background: #263140; }
    QPushButton:disabled { background: #252b33; color: #7f8895; border-color: #323c48; }
    QListWidget::item:selected { background: #2f6de1; color: white; border-radius: 4px; }
    QProgressBar { border: 1px solid #3a4653; border-radius: 6px; background: #232a31; text-align: center; }
    QProgressBar::chunk { background: #2f6de1; border-radius: 6px; }
    QLabel[role="header"] { font-size: 16px; font-weight: 600; }
    """


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(get_stylesheet())
