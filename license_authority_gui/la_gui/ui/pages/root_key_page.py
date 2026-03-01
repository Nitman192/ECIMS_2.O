"""Root key management page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.crypto_service import CryptoService
from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.state import SessionState


class RootKeyPage(QWidget):
    """Handles generate/unlock/lock and public key export actions."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self.passphrase_input = QLineEdit()
        self.passphrase_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase_input.setPlaceholderText("Passphrase")

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Confirm passphrase")

        self.fingerprint_label = QLabel("Fingerprint: <none>")

        generate_btn = QPushButton("Generate Root Key")
        generate_btn.clicked.connect(self.generate_root_key)

        unlock_btn = QPushButton("Load/Unlock Root Key")
        unlock_btn.clicked.connect(self.unlock_root_key)

        lock_btn = QPushButton("Lock (Purge In-Memory Key)")
        lock_btn.clicked.connect(self.lock_root_key)

        export_public_btn = QPushButton("Export Public Key PEM")
        export_public_btn.clicked.connect(self.export_public_key)

        form = QFormLayout()
        form.addRow("Passphrase:", self.passphrase_input)
        form.addRow("Confirm:", self.confirm_input)

        actions = QHBoxLayout()
        actions.addWidget(generate_btn)
        actions.addWidget(unlock_btn)
        actions.addWidget(lock_btn)
        actions.addWidget(export_public_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Root Key Management</h2>"))
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addWidget(self.fingerprint_label)

    def generate_root_key(self) -> None:
        """Generate and persist encrypted root key and public key."""
        passphrase = self.passphrase_input.text()
        confirm = self.confirm_input.text()
        if not passphrase:
            show_error(self, "Invalid Input", "Passphrase is required.")
            return
        if passphrase != confirm:
            show_error(self, "Invalid Input", "Passphrase confirmation does not match.")
            return

        try:
            artifacts = CryptoService.generate_root_keypair(passphrase)
            self.state.root_private_key_path.write_bytes(artifacts.encrypted_private_pem)
            self.state.root_public_key_path.write_bytes(artifacts.public_pem)
            self.state.public_key_fingerprint = artifacts.public_key_fingerprint
            self.fingerprint_label.setText(f"Fingerprint: {artifacts.public_key_fingerprint}")
            self.state.audit_logger.append(
                "root_key_generated",
                {"fingerprint": artifacts.public_key_fingerprint},
            )
            self.status_callback("Root key generated successfully.")
            show_info(self, "Success", "Root key generated and stored encrypted.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Key Generation Error", str(exc))

    def unlock_root_key(self) -> None:
        """Load encrypted private key and public key into runtime memory."""
        passphrase = self.passphrase_input.text()
        if not self.state.root_private_key_path.exists():
            show_error(self, "Missing Key", "No root key found. Generate key first.")
            return

        try:
            private_pem = self.state.root_private_key_path.read_bytes()
            public_pem = self.state.root_public_key_path.read_bytes()
            private_key = CryptoService.load_encrypted_private_key(private_pem, passphrase)
            public_key = CryptoService.load_public_key(public_pem)
            self.state.private_key = private_key
            self.state.public_key = public_key
            self.state.public_key_fingerprint = CryptoService.public_key_fingerprint(public_pem)
            self.fingerprint_label.setText(f"Fingerprint: {self.state.public_key_fingerprint}")
            self.status_callback("Root key unlocked in memory.")
            show_info(self, "Unlocked", "Root key loaded into memory for signing.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Unlock Error", str(exc))

    def lock_root_key(self) -> None:
        """Purge in-memory key state."""
        self.state.lock()
        self.status_callback("Root key locked and purged from memory.")
        show_info(self, "Locked", "Root key removed from memory.")

    def export_public_key(self) -> None:
        """Export the root public key into exports directory."""
        try:
            if not self.state.root_public_key_path.exists():
                show_error(self, "Missing Key", "Public key file not found.")
                return
            destination = self.state.storage_paths.exports_dir / "la_public_key.pem"
            destination.write_bytes(self.state.root_public_key_path.read_bytes())
            self.state.audit_logger.append("public_key_exported", {"path": str(destination)})
            self.status_callback(f"Public key exported to {destination}")
            show_info(self, "Exported", f"Public key exported to:\n{destination}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Export Error", str(exc))
