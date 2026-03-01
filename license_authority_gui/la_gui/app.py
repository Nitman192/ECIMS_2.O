"""GUI application bootstrap for License Authority desktop tool."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from la_gui.core.audit_log import AuditLogger
from la_gui.core.storage_paths import StoragePaths
from la_gui.ui.main_window import MainWindow
from la_gui.ui.state import SessionState


def build_state() -> SessionState:
    """Construct state/services for the running desktop session."""
    app_root = Path(__file__).resolve().parents[1]
    storage_paths = StoragePaths(root=app_root)
    storage_paths.ensure_directories()
    return SessionState(storage_paths=storage_paths, audit_logger=AuditLogger(storage_paths.audit_log_path))


def main() -> int:
    """Run the PySide6 desktop GUI."""
    app = QApplication(sys.argv)
    state = build_state()
    window = MainWindow(state)
    window.show()
    return app.exec()
