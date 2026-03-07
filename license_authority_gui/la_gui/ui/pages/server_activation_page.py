"""Server activation page for installation-id to verification-id workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.activation_service import ActivationService
from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_primary, set_secondary


class ServerActivationPage(QWidget):
    """Generates signed verification IDs from server activation request codes."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback
        self._parsed_request: dict | None = None

        self.request_input = QTextEdit()
        self.request_input.setPlaceholderText("Paste request_code from ECIMS server activation screen")

        self.parsed_output = QTextEdit()
        self.parsed_output.setReadOnly(True)
        self.parsed_output.setPlaceholderText("Parsed installation request details will appear here")

        self.verification_output = QTextEdit()
        self.verification_output.setReadOnly(True)
        self.verification_output.setPlaceholderText("Generated verification ID token appears here")

        self.expiry_notice = QLabel("No upcoming license expiry alerts.")
        self.registry_output = QTextEdit()
        self.registry_output.setReadOnly(True)

        parse_btn = QPushButton("Parse Request Code")
        parse_btn.setProperty("action_id", "activation.parse")
        set_secondary(parse_btn)
        parse_btn.clicked.connect(self.parse_request_code)

        generate_btn = QPushButton("Generate Verification ID")
        generate_btn.setProperty("action_id", "activation.verify.generate")
        set_primary(generate_btn)
        generate_btn.clicked.connect(self.generate_verification_id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Server Activation"))
        card_layout.addWidget(
            QLabel(
                "Flow: import license on server -> copy request_code -> generate verification ID here -> paste back on server."
            )
        )
        card_layout.addWidget(self.request_input)

        actions = QHBoxLayout()
        actions.addWidget(parse_btn)
        actions.addWidget(generate_btn)
        card_layout.addLayout(actions)

        card_layout.addWidget(QLabel("Request Details"))
        card_layout.addWidget(self.parsed_output)
        card_layout.addWidget(QLabel("Verification ID"))
        card_layout.addWidget(self.verification_output)
        card_layout.addWidget(self.expiry_notice)
        card_layout.addWidget(QLabel("Activated Client Registry"))
        card_layout.addWidget(self.registry_output)
        layout.addWidget(card)

    def refresh(self) -> None:
        self._refresh_registry_view()

    def parse_request_code(self) -> None:
        try:
            payload = ActivationService.parse_request_code(self.request_input.toPlainText())
            self._parsed_request = payload
            self.parsed_output.setPlainText(
                "\n".join(
                    [
                        f"Installation ID: {payload.get('installation_id')}",
                        f"License ID: {payload.get('license_id')}",
                        f"Customer: {payload.get('customer_name') or '-'}",
                        f"Machine FP: {str(payload.get('machine_fingerprint') or '')[:8]}...",
                        f"License Expiry: {payload.get('license_expiry_date') or '-'}",
                        f"Request Expires: {payload.get('expires_at')}",
                    ]
                )
            )
            self.status_callback("Activation request parsed successfully.")
        except Exception as exc:  # noqa: BLE001
            self._parsed_request = None
            self.parsed_output.clear()
            show_error(self, "Parse Error", str(exc))

    def generate_verification_id(self) -> None:
        if not self.state.is_unlocked or self.state.private_key is None:
            show_error(self, "Locked", "Unlock root key before generating verification ID.")
            return
        if self._parsed_request is None:
            try:
                self._parsed_request = ActivationService.parse_request_code(self.request_input.toPlainText())
            except Exception as exc:  # noqa: BLE001
                show_error(self, "Invalid Request", str(exc))
                return
        try:
            verification_id, claims = ActivationService.create_verification_id(
                request_payload=self._parsed_request,
                private_key=self.state.private_key,
                validity_days=30,
            )
            self.verification_output.setPlainText(verification_id)
            registry_entry = ActivationService.upsert_registry_entry(
                storage_paths=self.state.storage_paths,
                request_payload=self._parsed_request,
                verification_claims=claims,
            )
            self.state.audit_logger.append(
                "server_activation_verification_issued",
                {
                    "installation_id": registry_entry["installation_id"],
                    "license_id": registry_entry["license_id"],
                    "verification_id": registry_entry["verification_id"],
                },
            )
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type="activation.verify.generate",
                outcome="success",
                safe_metadata={
                    "installation_id": registry_entry["installation_id"],
                    "license_id": registry_entry["license_id"],
                },
            )
            self._refresh_registry_view()
            self.status_callback("Verification ID generated.")
            show_info(
                self,
                "Verification ID Generated",
                (
                    "Paste this verification ID into server activation screen.\n\n"
                    f"Installation ID: {registry_entry['installation_id']}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type="activation.verify.generate",
                outcome="fail",
                safe_metadata={"error": str(exc)},
            )
            show_error(self, "Generation Error", str(exc))

    def _refresh_registry_view(self) -> None:
        registry = ActivationService.load_registry(self.state.storage_paths)
        clients = registry.get("clients", [])
        if not isinstance(clients, list) or not clients:
            self.registry_output.setPlainText("No activated client records yet.")
        else:
            lines = []
            for item in clients[-200:]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    (
                        f"{item.get('installation_id', '-')}"
                        f" | {item.get('license_id', '-')}"
                        f" | expiry={item.get('license_expiry_date', '-')}"
                        f" | updated={item.get('last_updated_at', '-')}"
                    )
                )
            self.registry_output.setPlainText("\n".join(lines) if lines else "No activated client records yet.")

        expiring = ActivationService.expiring_entries(self.state.storage_paths, within_days=7)
        if not expiring:
            self.expiry_notice.setText("No client licenses expiring in next 7 days.")
            return

        now = datetime.now(timezone.utc).isoformat()
        summary = ", ".join(
            [f"{item.get('installation_id', '-')} ({item.get('days_left', '?')}d)" for item in expiring[:10]]
        )
        self.expiry_notice.setText(
            f"Expiry alert ({now}): {len(expiring)} client license(s) expiring within 7 days -> {summary}"
        )
