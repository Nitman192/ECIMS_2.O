"""UI helper utilities."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


def show_error(parent: QWidget, title: str, message: str) -> None:
    """Show a critical error dialog."""
    QMessageBox.critical(parent, title, message)


def show_info(parent: QWidget, title: str, message: str) -> None:
    """Show an informational dialog."""
    QMessageBox.information(parent, title, message)


def open_json_file(parent: QWidget) -> Path | None:
    """Open a JSON file dialog and return selected path."""
    file_name, _ = QFileDialog.getOpenFileName(parent, "Select JSON file", str(Path.home()), "JSON Files (*.json)")
    if not file_name:
        return None
    return Path(file_name)
