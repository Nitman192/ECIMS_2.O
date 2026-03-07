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

        self.step_indicator = QLabel("Progress: 0/0")
        self.step_indicator.setProperty("role", "muted")

        self.guide_label = QLabel("Follow steps from top to bottom. Use the action button in each row.")
        self.guide_label.setProperty("role", "muted")
        self.guide_label.setWordWrap(True)

        self.progress = QProgressBar()
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(8)

        self.next_btn = QPushButton("Open Next Pending Step")
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
        card_layout.addWidget(section_header("Quick Start Wizard"))
        card_layout.addWidget(self.guide_label)
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
        total_count = len(self.steps)
        self.progress.setMaximum(total_count if total_count else 1)
        self.progress.setValue(ok_count)
        self.progress.setFormat(f"{ok_count}/{total_count} steps completed")

        headers = ["Step", "Status", "Details", "Action"]
        for col, text in enumerate(headers):
            label = QLabel(text)
            label.setProperty("role", "tableHeader")
            self.grid.addWidget(label, 0, col)

        for row, step in enumerate(self.steps, start=1):
            self.grid.addWidget(QLabel(f"{row}. {step.label}"), row, 0)

            status_label = QLabel(self._display_status(step.status))
            status_label.setProperty("status", self._status_variant(step.status))
            self.grid.addWidget(status_label, row, 1)

            details_label = QLabel(self._friendly_details(step))
            details_label.setWordWrap(True)
            details_label.setProperty("role", "muted")
            self.grid.addWidget(details_label, row, 2)

            action_id = self._action_id(step.key)
            button = QPushButton(self._action_text(step.key))
            button.setProperty("action_id", action_id)
            set_primary(button)
            if step.key in {"offline", "audit", "mtls_ca", "mtls_sign", "data_key"}:
                set_secondary(button)

            allowed, reason = self.permission_callback(action_id)
            enabled = step.enabled and allowed
            button.setEnabled(enabled)
            if not allowed and reason:
                button.setToolTip(reason)
            button.clicked.connect(lambda _=False, key=step.key: self._run_action(key))
            self.grid.addWidget(button, row, 3)

        self.current_step_index = self._next_actionable_index()
        if not self.steps:
            self.step_indicator.setText("Progress: no setup steps available")
            self.next_btn.setEnabled(False)
            return

        current_step = self.steps[self.current_step_index]
        self.step_indicator.setText(
            f"Progress: {ok_count}/{total_count} completed. Next: Step {self.current_step_index + 1} - {current_step.label}"
        )

        action_id = self._action_id(current_step.key)
        allowed, reason = self.permission_callback(action_id)
        can_next = current_step.status != "OK" and current_step.enabled and allowed
        self.next_btn.setEnabled(can_next)
        self.next_btn.setToolTip(reason if not allowed and reason else "")

    def _next_actionable_index(self) -> int:
        if not self.steps:
            return 0

        for idx, step in enumerate(self.steps):
            if step.status != "OK" and step.enabled:
                return idx

        for idx, step in enumerate(self.steps):
            if step.status != "OK":
                return idx

        return len(self.steps) - 1

    def _display_status(self, status: str) -> str:
        return {
            "OK": "Done",
            "Missing": "Required",
            "Locked": "Unlock Needed",
            "Needs Input": "Pending",
        }.get(status, status)

    def _status_variant(self, status: str) -> str:
        return {
            "OK": "ok",
            "Missing": "warn",
            "Locked": "warn",
            "Needs Input": "pending",
        }.get(status, "pending")

    def _friendly_details(self, step: StepStatus) -> str:
        return {
            "offline": "Save offline acknowledgment once per environment.",
            "root": "Generate or unlock your root signing key.",
            "license": "Create the signed license file for the target server.",
            "mtls_ca": "Optional: create local mTLS CA certificate.",
            "mtls_sign": "Optional: sign agent CSR using mTLS CA.",
            "data_key": "Optional: generate data key bundle for encryption.",
            "bundle": "Export activation package to share with server.",
            "audit": "Run audit chain verification for compliance.",
        }.get(step.key, step.details)

    def _next_incomplete_step(self) -> None:
        if not self.steps:
            return
        self.current_step_index = self._next_actionable_index()
        step = self.steps[self.current_step_index]
        if step.status == "OK" or not step.enabled:
            show_info(self, "Quick Start", "All required actionable steps are complete.")
            return
        self._run_action(step.key)

    def _action_text(self, key: str) -> str:
        return {
            "offline": "Acknowledge",
            "root": "Open Root Keys",
            "license": "Open License",
            "mtls_ca": "Open mTLS",
            "mtls_sign": "Open mTLS",
            "data_key": "Open Data Keys",
            "bundle": "Export Bundle",
            "audit": "Verify Audit",
        }.get(key, "Open")

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
