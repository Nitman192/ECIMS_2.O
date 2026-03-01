"""Quick Start wizard page for simplified operator workflow."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.settings_service import SettingsService
from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.state import SessionState
from la_gui.ui.wizard_state import build_snapshot, evaluate_steps


class WizardPage(QWidget):
    """Simple mode wizard with step statuses and primary actions."""

    def __init__(self, state: SessionState, status_callback, open_page_callback, verify_audit_callback, bundle_export_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback
        self.open_page_callback = open_page_callback
        self.verify_audit_callback = verify_audit_callback
        self.bundle_export_callback = bundle_export_callback

        self.progress = QProgressBar()
        self.grid = QGridLayout()

        panel = QGroupBox("Quick Start (Wizard)")
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(self.progress)
        panel_layout.addLayout(self.grid)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(panel)

    def refresh(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        snapshot = build_snapshot(self.state.storage_paths, self.state.is_unlocked, self.state.offline_acknowledged)
        steps = evaluate_steps(snapshot, self.state.settings)

        ok_count = sum(1 for s in steps if s.status == "OK")
        self.progress.setMaximum(len(steps))
        self.progress.setValue(ok_count)
        self.progress.setFormat(f"{ok_count}/{len(steps)} steps OK")

        for row, step in enumerate(steps):
            self.grid.addWidget(QLabel(f"{row + 1}. {step.label}"), row, 0)
            status_label = QLabel(step.status)
            status_label.setObjectName("statusBadge")
            self.grid.addWidget(status_label, row, 1)
            self.grid.addWidget(QLabel(step.details), row, 2)

            button = QPushButton("Action")
            button.setEnabled(step.enabled)
            button.clicked.connect(lambda _=False, key=step.key: self._run_action(key))
            self.grid.addWidget(button, row, 3)

    def _run_action(self, key: str) -> None:
        try:
            if key == "offline":
                SettingsService.write_offline_ack(self.state.storage_paths)
                self.state.offline_acknowledged = True
                show_info(self, "Acknowledged", "Offline acknowledgement saved.")
            elif key == "root":
                self.open_page_callback("Root Key Management")
            elif key == "license":
                self.open_page_callback("License Signing")
            elif key == "mtls_ca":
                self.open_page_callback("mTLS CA Management")
            elif key == "mtls_sign":
                self.open_page_callback("mTLS CA Management")
            elif key == "data_key":
                self.open_page_callback("Data Key Bundles")
            elif key == "bundle":
                self.bundle_export_callback()
            elif key == "audit":
                self.verify_audit_callback()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Wizard Action Error", str(exc))
