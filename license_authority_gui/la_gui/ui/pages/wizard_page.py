"""Quick Start wizard page for simplified operator workflow."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout, QWidget

from la_gui.core.settings_service import SettingsService
from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_primary, set_secondary
from la_gui.ui.wizard_state import StepStatus, build_snapshot, evaluate_steps


class WizardPage(QWidget):
    """Simple mode wizard with step statuses and primary actions."""

    def __init__(
        self,
        state: SessionState,
        status_callback,
        open_page_callback,
        verify_audit_callback,
        bundle_export_callback,
        permission_callback,
    ):
        super().__init__()
        self.state = state
        self.status_callback = status_callback
        self.open_page_callback = open_page_callback
        self.verify_audit_callback = verify_audit_callback
        self.bundle_export_callback = bundle_export_callback
        self.permission_callback = permission_callback
        self.current_step_index = 0
        self.steps: list[StepStatus] = []

        self.step_indicator = QLabel("Step 1")
        self.progress = QProgressBar()
        self.grid = QGridLayout()

        self.next_btn = QPushButton("Next Incomplete Step")
        self.next_btn.setProperty("action_id", "wizard.next")
        set_primary(self.next_btn)
        self.next_btn.clicked.connect(self._next_incomplete_step)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Quick Start (Wizard)"))
        card_layout.addWidget(self.step_indicator)
        card_layout.addWidget(self.progress)
        card_layout.addLayout(self.grid)
        card_layout.addWidget(self.next_btn)
        layout.addWidget(card)

    def refresh(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        snapshot = build_snapshot(self.state.storage_paths, self.state.is_unlocked, self.state.offline_acknowledged)
        self.steps = evaluate_steps(snapshot, self.state.settings)

        ok_count = sum(1 for s in self.steps if s.status == "OK")
        self.progress.setMaximum(len(self.steps))
        self.progress.setValue(ok_count)
        self.progress.setFormat(f"{ok_count}/{len(self.steps)} steps OK")

        for row, step in enumerate(self.steps):
            self.grid.addWidget(QLabel(f"{row + 1}. {step.label}"), row, 0)
            self.grid.addWidget(QLabel(step.status), row, 1)
            self.grid.addWidget(QLabel(step.details), row, 2)

            action_id = self._action_id(step.key)
            button = QPushButton(self._action_text(step.key))
            button.setProperty("action_id", action_id)
            set_primary(button)
            if step.key in {"offline", "audit"}:
                set_secondary(button)

            allowed, reason = self.permission_callback(action_id)
            enabled = step.enabled and allowed
            button.setEnabled(enabled)
            if not allowed and reason:
                button.setToolTip(reason)
            button.clicked.connect(lambda _=False, key=step.key: self._run_action(key))
            self.grid.addWidget(button, row, 3)

        self.current_step_index = next((i for i, step in enumerate(self.steps) if step.status != "OK"), len(self.steps) - 1)
        self.step_indicator.setText(f"Current step: {self.current_step_index + 1}/{len(self.steps)}")

        action_id = self._action_id(self.steps[self.current_step_index].key) if self.steps else "wizard.next"
        allowed, reason = self.permission_callback(action_id)
        can_next = bool(self.steps) and self.current_step_index < len(self.steps) and self.steps[self.current_step_index].enabled and allowed
        self.next_btn.setEnabled(can_next)
        if not allowed and reason:
            self.next_btn.setToolTip(reason)

    def _next_incomplete_step(self) -> None:
        if not self.steps:
            return
        step = self.steps[self.current_step_index]
        if step.status == "OK" or not step.enabled:
            return
        self._run_action(step.key)

    def _action_text(self, key: str) -> str:
        return {
            "offline": "Acknowledge",
            "root": "Open Root Key",
            "license": "Open License",
            "mtls_ca": "Open mTLS",
            "mtls_sign": "Open CSR Sign",
            "data_key": "Open Data Keys",
            "bundle": "Export Bundle",
            "audit": "Verify Audit",
        }.get(key, "Action")

    def _action_id(self, key: str) -> str:
        return {
            "offline": "wizard.offline",
            "root": "wizard.open_root",
            "license": "wizard.open_license",
            "mtls_ca": "wizard.open_mtls",
            "mtls_sign": "wizard.open_mtls",
            "data_key": "wizard.open_data",
            "bundle": "activation.export",
            "audit": "wizard.audit",
        }.get(key, "wizard.action")

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
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type=f"wizard.{key}",
                outcome="success",
                safe_metadata={"step": key},
            )
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type=f"wizard.{key}",
                outcome="fail",
                safe_metadata={"error": str(exc)},
            )
            show_error(self, "Wizard Action Error", str(exc))
