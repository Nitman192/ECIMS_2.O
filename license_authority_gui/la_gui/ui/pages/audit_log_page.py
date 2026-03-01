"""Audit log viewer and integrity verification page."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.state import SessionState


class AuditLogPage(QWidget):
    """Read-only audit log list, verification, and export actions."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)

        verify_btn = QPushButton("Verify Audit Hash Chain")
        verify_btn.clicked.connect(self.verify_chain)

        export_btn = QPushButton("Export Audit Log Copy")
        export_btn.clicked.connect(self.export_copy)

        actions = QHBoxLayout()
        actions.addWidget(refresh_btn)
        actions.addWidget(verify_btn)
        actions.addWidget(export_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Audit Log</h2>"))
        layout.addLayout(actions)
        layout.addWidget(self.log_view)

    def refresh(self) -> None:
        """Refresh audit entries list."""
        entries = self.state.audit_logger.read_entries()
        if not entries:
            self.log_view.setPlainText("No audit entries yet.")
            return
        lines = [f"{entry.timestamp} | {entry.actor} | {entry.action} | {entry.details}" for entry in entries]
        self.log_view.setPlainText("\n".join(lines))

    def verify_chain(self) -> None:
        """Verify hash chain integrity and write a verification audit event."""
        ok, message = self.state.audit_logger.verify_chain()
        self.state.audit_logger.append("audit_verified", {"ok": ok, "message": message})
        self.status_callback(f"Audit verify: {message}")
        if ok:
            show_info(self, "Audit Verification", "Audit hash chain verification succeeded.")
        else:
            show_error(self, "Audit Verification", f"Audit verification failed: {message}")
        self.refresh()

    def export_copy(self) -> None:
        """Export audit log to exports directory."""
        try:
            if not self.state.storage_paths.audit_log_path.exists():
                show_error(self, "Missing Log", "Audit log file does not exist yet.")
                return
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            destination = self.state.storage_paths.exports_dir / f"audit_log_{stamp}.jsonl"
            destination.write_text(self.state.storage_paths.audit_log_path.read_text(encoding="utf-8"), encoding="utf-8")
            self.status_callback(f"Audit log exported: {destination.name}")
            show_info(self, "Exported", f"Audit log exported to:\n{destination}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Export Error", str(exc))
