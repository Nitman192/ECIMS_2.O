"""Server activation page for installation-id to verification-id workflow."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.activation_service import ActivationService
from la_gui.ui.feature_flags import ENABLE_SERVER_ACTIVATION
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
        self._last_parsed_token = ""

        self.request_input = QPlainTextEdit()
        self.request_input.setPlaceholderText("Step 1: Paste request code from ECIMS server activation screen.")
        self.request_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.request_input.textChanged.connect(self._on_request_changed)

        self.parsed_output = QPlainTextEdit()
        self.parsed_output.setReadOnly(True)
        self.parsed_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.parsed_output.setPlaceholderText("Step 2: Parsed request details will appear here.")

        self.verification_output = QPlainTextEdit()
        self.verification_output.setReadOnly(True)
        self.verification_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.verification_output.setPlaceholderText("Step 3: Generated verification ID token appears here.")

        self.expiry_notice = QLabel("No upcoming license expiry alerts.")
        self.expiry_notice.setWordWrap(True)
        self.registry_output = QPlainTextEdit()
        self.registry_output.setReadOnly(True)
        self.registry_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.registry_output.setPlaceholderText("Activated client records will appear here.")

        paste_btn = QPushButton("Paste from Clipboard")
        set_secondary(paste_btn)
        paste_btn.clicked.connect(self.paste_from_clipboard)

        clear_btn = QPushButton("Clear")
        set_secondary(clear_btn)
        clear_btn.clicked.connect(self.clear_inputs)

        self.parse_btn = QPushButton("Parse Request")
        self.parse_btn.setProperty("action_id", "activation.parse")
        set_secondary(self.parse_btn)
        self.parse_btn.clicked.connect(self.parse_request_code)

        self.generate_btn = QPushButton("Generate Verification ID")
        self.generate_btn.setProperty("action_id", "activation.verify.generate")
        set_primary(self.generate_btn)
        self.generate_btn.clicked.connect(self.generate_verification_id)

        copy_btn = QPushButton("Copy Verification ID")
        set_secondary(copy_btn)
        copy_btn.clicked.connect(self.copy_verification_id)

        if not ENABLE_SERVER_ACTIVATION:
            disabled_msg = "Temporarily disabled: Server activation key generation is turned off."
            self.request_input.setPlainText(disabled_msg)
            self.request_input.setReadOnly(True)
            self.parsed_output.setReadOnly(True)
            self.verification_output.setReadOnly(True)
            self.expiry_notice.setText(disabled_msg)
            for btn in [paste_btn, clear_btn, self.parse_btn, self.generate_btn, copy_btn]:
                btn.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Server Activation"))
        flow_label = QLabel(
            "Simple flow: 1) Paste request code, 2) Parse request, 3) Generate verification ID, 4) Copy it back to server."
        )
        flow_label.setProperty("role", "muted")
        flow_label.setWordWrap(True)
        card_layout.addWidget(flow_label)
        card_layout.addWidget(QLabel("Request Code"))
        card_layout.addWidget(self.request_input)

        request_actions = QHBoxLayout()
        request_actions.addWidget(paste_btn)
        request_actions.addWidget(clear_btn)
        request_actions.addStretch(1)
        request_actions.addWidget(self.parse_btn)
        request_actions.addWidget(self.generate_btn)
        card_layout.addLayout(request_actions)

        card_layout.addWidget(QLabel("Request Details"))
        card_layout.addWidget(self.parsed_output)
        card_layout.addWidget(QLabel("Verification ID"))
        card_layout.addWidget(self.verification_output)
        verification_actions = QHBoxLayout()
        verification_actions.addStretch(1)
        verification_actions.addWidget(copy_btn)
        card_layout.addLayout(verification_actions)
        card_layout.addWidget(self.expiry_notice)
        card_layout.addWidget(QLabel("Activated Client Registry"))
        card_layout.addWidget(self.registry_output)
        layout.addWidget(card)

    def refresh(self) -> None:
        if not ENABLE_SERVER_ACTIVATION:
            return
        self._refresh_registry_view()

    def _on_request_changed(self) -> None:
        current = self.request_input.toPlainText().strip()
        if current == self._last_parsed_token:
            return
        self._parsed_request = None

    def paste_from_clipboard(self) -> None:
        if not ENABLE_SERVER_ACTIVATION:
            return
        text = QApplication.clipboard().text().strip()
        if not text:
            show_error(self, "Clipboard Empty", "Clipboard does not contain request code text.")
            return
        self.request_input.setPlainText(text)
        self.status_callback("Request code pasted from clipboard.")

    def clear_inputs(self) -> None:
        self.request_input.clear()
        self.parsed_output.clear()
        self.verification_output.clear()
        self._parsed_request = None
        self._last_parsed_token = ""
        self.status_callback("Activation inputs cleared.")

    def copy_verification_id(self) -> None:
        verification_id = self.verification_output.toPlainText().strip()
        if not verification_id:
            show_error(self, "Missing Verification ID", "Generate verification ID first.")
            return
        QApplication.clipboard().setText(verification_id)
        self.status_callback("Verification ID copied to clipboard.")

    def _render_request_details(self, payload: dict) -> str:
        return "\n".join(
            [
                f"Installation ID : {payload.get('installation_id', '-')}",
                f"License ID      : {payload.get('license_id', '-')}",
                f"Customer        : {payload.get('customer_name') or '-'}",
                f"Machine Finger  : {str(payload.get('machine_fingerprint') or '')[:12]}...",
                f"License Expiry  : {payload.get('license_expiry_date') or '-'}",
                f"Request Expires : {payload.get('expires_at', '-')}",
            ]
        )

    def parse_request_code(self) -> None:
        if not ENABLE_SERVER_ACTIVATION:
            return
        try:
            token = self.request_input.toPlainText().strip()
            payload = ActivationService.parse_request_code(token)
            self._parsed_request = payload
            self._last_parsed_token = token
            self.parsed_output.setPlainText(self._render_request_details(payload))
            self.status_callback("Request parsed. Review details then generate verification ID.")
        except Exception as exc:  # noqa: BLE001
            self._parsed_request = None
            self.parsed_output.clear()
            show_error(self, "Parse Error", str(exc))

    def generate_verification_id(self) -> None:
        if not ENABLE_SERVER_ACTIVATION:
            return
        if not self.state.is_unlocked or self.state.private_key is None:
            show_error(self, "Locked", "Unlock root key before generating verification ID.")
            return
        raw_token = self.request_input.toPlainText().strip()
        if not raw_token:
            show_error(self, "Missing Request Code", "Paste request code before generating verification ID.")
            return
        if self._parsed_request is None or raw_token != self._last_parsed_token:
            try:
                self._parsed_request = ActivationService.parse_request_code(raw_token)
                self._last_parsed_token = raw_token
                self.parsed_output.setPlainText(self._render_request_details(self._parsed_request))
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
                    "Verification ID is ready. Copy it and paste into server activation screen.\n\n"
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

        summary = ", ".join(
            [f"{item.get('installation_id', '-')} ({item.get('days_left', '?')}d)" for item in expiring[:10]]
        )
        self.expiry_notice.setText(
            f"Attention: {len(expiring)} client license(s) expiring within 7 days: {summary}"
        )
