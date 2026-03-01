"""License signing and verification page."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.canonical_json import canonicalize_json
from la_gui.core.crypto_service import CryptoService
from la_gui.core.models import LicensePayload, SignedLicense
from la_gui.core.license_service import LicenseService
from la_gui.ui.helpers import confirm_action, open_json_file, show_error, show_info
from la_gui.ui.state import SessionState


class LicenseSigningPage(QWidget):
    """Collects license fields and executes preview/sign/verify flows."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback
        self._pending_payload: LicensePayload | None = None

        self.customer_input = QLineEdit()
        self.max_agents_input = QLineEdit()
        self.max_agents_input.setPlaceholderText("e.g. 25")
        self.expires_at_input = QLineEdit()
        self.expires_at_input.setPlaceholderText("ISO 8601 UTC, e.g. 2030-01-01T00:00:00+00:00")
        self.server_id_input = QLineEdit()
        self.features_input = QTextEdit()
        self.features_input.setPlaceholderText('{"feature_a": true}')

        self.preview_output = QTextEdit()
        self.preview_output.setReadOnly(True)

        preview_btn = QPushButton("Preview Payload")
        preview_btn.clicked.connect(self.preview_payload)

        sign_btn = QPushButton("Confirm + Sign")
        sign_btn.clicked.connect(self.confirm_and_sign)

        verify_btn = QPushButton("Verify License File")
        verify_btn.clicked.connect(self.verify_license_file)

        form = QFormLayout()
        form.addRow("Customer:", self.customer_input)
        form.addRow("Max Agents:", self.max_agents_input)
        form.addRow("Expires At:", self.expires_at_input)
        form.addRow("Server ID (optional):", self.server_id_input)
        form.addRow("Features JSON (optional):", self.features_input)

        actions = QHBoxLayout()
        actions.addWidget(preview_btn)
        actions.addWidget(sign_btn)
        actions.addWidget(verify_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>License Signing</h2>"))
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(QLabel("Preview (Canonical Payload)"))
        layout.addWidget(self.preview_output)

    def _build_payload(self) -> LicensePayload:
        if not self.state.is_unlocked or self.state.private_key is None:
            raise ValueError("Root key must be unlocked before signing.")
        if not self.state.public_key_fingerprint:
            raise ValueError("Public key fingerprint unavailable. Unlock root key first.")

        features_text = self.features_input.toPlainText().strip()
        features = {} if not features_text else json.loads(features_text)
        if not isinstance(features, dict):
            raise ValueError("Features must be a JSON object.")

        issued_at = datetime.now(timezone.utc).isoformat()
        expires_at = self.expires_at_input.text().strip()
        if not expires_at:
            raise ValueError("expires_at is required.")

        return LicensePayload(
            serial=str(uuid.uuid4()),
            customer=self.customer_input.text().strip(),
            issued_at=issued_at,
            expires_at=expires_at,
            max_agents=int(self.max_agents_input.text().strip()),
            server_id=self.server_id_input.text().strip() or None,
            features=features,
            public_key_fingerprint=self.state.public_key_fingerprint,
        )

    def preview_payload(self) -> None:
        """Validate input and render canonical payload preview."""
        try:
            payload = self._build_payload()
            LicenseService.validate_payload(payload)
            payload_dict = LicenseService.payload_to_sign_dict(payload)
            self._pending_payload = payload
            self.preview_output.setPlainText(canonicalize_json(payload_dict).decode("utf-8"))
            self.status_callback("Preview generated. Confirm to sign.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Preview Error", str(exc))

    def confirm_and_sign(self) -> None:
        """Display final confirmation then sign and export license.json."""
        if self._pending_payload is None:
            show_error(self, "Missing Preview", "Run Preview Payload before signing.")
            return
        if self.state.private_key is None:
            show_error(self, "Locked", "Root key is not unlocked.")
            return

        if self.state.settings.confirm_sensitive_actions:
            ok = confirm_action(self, "Confirm Signing", "Proceed with signing and exporting license artifact to exports/?")
            if not ok:
                return

        try:
            signed = LicenseService.sign_license(self._pending_payload, self.state.private_key)
            destination = self.state.storage_paths.exports_dir / f"license_{signed.serial}.json"
            destination.write_text(json.dumps(asdict(signed), indent=2, sort_keys=True), encoding="utf-8")
            self.state.audit_logger.append("license_signed", {"serial": signed.serial, "path": str(destination)})
            self.status_callback(f"License signed: {destination.name}")
            show_info(self, "Signed", f"License saved to:\n{destination}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Signing Error", str(exc))

    def verify_license_file(self) -> None:
        """Verify a selected signed license JSON file."""
        path = open_json_file(self)
        if path is None:
            return

        try:
            if not self.state.root_public_key_path.exists():
                raise ValueError("Root public key file not found.")
            public_key = self.state.public_key or self._load_public_key_from_disk()
            raw = json.loads(path.read_text(encoding="utf-8"))
            signed = SignedLicense(**raw)
            valid = LicenseService.verify_license_signature(signed, public_key)
            self.status_callback(f"License verification: {'valid' if valid else 'invalid'}")
            if valid:
                show_info(self, "Verification Result", "License signature is valid.")
            else:
                show_error(self, "Verification Result", "License signature is INVALID.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Verification Error", str(exc))

    def _load_public_key_from_disk(self):
        public_pem = self.state.root_public_key_path.read_bytes()
        return CryptoService.load_public_key(public_pem)
