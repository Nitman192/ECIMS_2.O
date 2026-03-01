"""GUI application bootstrap for License Authority desktop tool."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from la_gui.core.activity_log_service import ActivityLogService
from la_gui.core.audit_log import AuditLogger
from la_gui.core.settings_service import SettingsService
from la_gui.core.storage_paths import StoragePaths
from la_gui.ui.hardening.idle_lock import IdleLockManager
from la_gui.ui.hardening.offline_ack_dialog import OfflineAckDialog
from la_gui.ui.main_window import MainWindow
from la_gui.ui.state import SessionState
from la_gui.ui.theme import apply_theme


def build_state() -> SessionState:
    """Construct state/services for the running desktop session."""
    app_root = Path(__file__).resolve().parents[1]
    storage_paths = StoragePaths(root=app_root)
    storage_paths.ensure_directories()
    settings = SettingsService.load_settings(storage_paths)
    offline_ack = SettingsService.has_offline_ack(storage_paths)
    current_role = SettingsService.load_current_role(storage_paths)
    return SessionState(
        storage_paths=storage_paths,
        audit_logger=AuditLogger(storage_paths.audit_log_path),
        settings=settings,
        activity_log=ActivityLogService(storage_paths.activity_log_path),
        app_root=app_root,
        offline_acknowledged=offline_ack,
        current_role=current_role,
    )


def main() -> int:
    """Run the PySide6 desktop GUI."""
    app = QApplication(sys.argv)
    apply_theme(app)
    state = build_state()

    if state.settings.require_offline_ack and not state.offline_acknowledged:
        dialog = OfflineAckDialog()
        if dialog.exec() != 1:
            return 1
        SettingsService.write_offline_ack(state.storage_paths)
        state.offline_acknowledged = True

    window = MainWindow(state)

    idle = IdleLockManager(
        idle_seconds=state.settings.lock_on_idle_seconds,
        lock_callback=window.force_lock,
        status_callback=window.show_status,
    )
    app.installEventFilter(idle)
    idle.start()

    window.show()
    return app.exec()
