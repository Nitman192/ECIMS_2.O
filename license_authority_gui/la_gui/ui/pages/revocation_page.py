"""Revocation management page."""

from __future__ import annotations

import json
from dataclasses import asdict

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.crypto_service import CryptoService
from la_gui.core.models import RevocationBundle
from la_gui.core.revocation_service import RevocationService
from la_gui.ui.helpers import confirm_action, open_json_file, show_error, show_info
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_primary, set_secondary


class RevocationPage(QWidget):
    """Generate and verify signed revocation bundles."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self.serials_input = QTextEdit()
        self.serials_input.setPlaceholderText("Enter one serial per line")

        generate_btn = QPushButton("Generate Signed Revocation Bundle")
        generate_btn.setProperty("action_id", "revocation.sign")
        set_primary(generate_btn)
        generate_btn.clicked.connect(self.generate_bundle)

        verify_btn = QPushButton("Verify Revocation Bundle File")
        verify_btn.setProperty("action_id", "revocation.verify")
        set_secondary(verify_btn)
        verify_btn.clicked.connect(self.verify_bundle)

        actions = QHBoxLayout()
        actions.addWidget(generate_btn)
        actions.addWidget(verify_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Revocation"))
        card_layout.addWidget(QLabel("Revoked Serials"))
        card_layout.addWidget(self.serials_input)
        card_layout.addLayout(actions)
        layout.addWidget(card)

    def generate_bundle(self) -> None:
        """Generate signed revocation bundle and export JSON."""
        if self.state.private_key is None:
            show_error(self, "Locked", "Unlock root key before signing revocations.")
            return

        serials = [line.strip() for line in self.serials_input.toPlainText().splitlines() if line.strip()]
        if not serials:
            show_error(self, "Invalid Input", "Enter at least one serial to revoke.")
            return

        try:
            if self.state.settings.confirm_sensitive_actions and not confirm_action(self, "Confirm Revocation Signing", "Sign and export revocation bundle to exports/?"):
                return
            bundle = RevocationService.create_bundle(serials, self.state.private_key)
            destination = self.state.storage_paths.exports_dir / f"revocation_{bundle.issued_at.replace(':', '-')}.json"
            destination.write_text(json.dumps(asdict(bundle), indent=2, sort_keys=True), encoding="utf-8")
            self.state.audit_logger.append(
                "revocation_signed",
                {"count": len(bundle.revoked_serials), "path": str(destination)},
            )
            self.status_callback(f"Revocation bundle exported: {destination.name}")
            show_info(self, "Generated", f"Revocation bundle saved to:\n{destination}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Revocation Error", str(exc))

    def verify_bundle(self) -> None:
        """Verify a selected revocation bundle using root public key."""
        path = open_json_file(self)
        if path is None:
            return

        try:
            if not self.state.root_public_key_path.exists():
                raise ValueError("Root public key file not found.")
            public_key = self.state.public_key or CryptoService.load_public_key(self.state.root_public_key_path.read_bytes())
            raw = json.loads(path.read_text(encoding="utf-8"))
            bundle = RevocationBundle(**raw)
            valid = RevocationService.verify_bundle(bundle, public_key)
            self.status_callback(f"Revocation verification: {'valid' if valid else 'invalid'}")
            if valid:
                show_info(self, "Verification Result", "Revocation bundle signature is valid.")
            else:
                show_error(self, "Verification Result", "Revocation bundle signature is INVALID.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Verification Error", str(exc))
