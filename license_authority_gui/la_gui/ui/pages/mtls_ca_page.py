"""mTLS CA management page."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from la_gui.core.mtls_service import MTLSService
from la_gui.ui.helpers import open_pem_file, show_error, show_info
from la_gui.ui.state import SessionState


class MTLSCAPage(QWidget):
    """Generate CA, sign agent CSRs, and export chain."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self.passphrase_input = QLineEdit()
        self.passphrase_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase_input.setPlaceholderText("CA passphrase")

        self.validity_days_input = QSpinBox()
        self.validity_days_input.setMinimum(1)
        self.validity_days_input.setMaximum(3650)
        self.validity_days_input.setValue(365)

        generate_btn = QPushButton("Generate mTLS CA")
        generate_btn.clicked.connect(self.generate_ca)

        sign_csr_btn = QPushButton("Sign Agent CSR")
        sign_csr_btn.clicked.connect(self.sign_csr)

        export_chain_btn = QPushButton("Export mTLS Chain")
        export_chain_btn.clicked.connect(self.export_chain)

        form = QFormLayout()
        form.addRow("CA Passphrase:", self.passphrase_input)
        form.addRow("CSR Validity Days:", self.validity_days_input)

        actions = QHBoxLayout()
        actions.addWidget(generate_btn)
        actions.addWidget(sign_csr_btn)
        actions.addWidget(export_chain_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>mTLS CA Management</h2>"))
        layout.addLayout(form)
        layout.addLayout(actions)

    def generate_ca(self) -> None:
        """Generate encrypted CA key/cert pair."""
        try:
            passphrase = self.passphrase_input.text()
            MTLSService.generate_ca(self.state.storage_paths, passphrase)
            self.state.audit_logger.append("mtls_ca_generated", {"cert_path": str(self.state.storage_paths.mtls_ca_cert_path)})
            self.status_callback("mTLS CA generated.")
            show_info(self, "Success", "mTLS CA key/certificate generated.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "mTLS Error", str(exc))

    def sign_csr(self) -> None:
        """Sign selected CSR with offline mTLS CA."""
        csr_path = open_pem_file(self, "Select Agent CSR PEM")
        if csr_path is None:
            return
        try:
            passphrase = self.passphrase_input.text()
            result = MTLSService.sign_agent_csr(
                storage_paths=self.state.storage_paths,
                ca_passphrase=passphrase,
                csr_pem_path=csr_path,
                validity_days=int(self.validity_days_input.value()),
            )
            self.state.audit_logger.append(
                "agent_csr_signed",
                {"csr": str(csr_path), "cert_path": str(result.output_path)},
            )
            self.status_callback(f"CSR signed: {result.output_path.name}")
            show_info(self, "Signed", f"Agent certificate exported to:\n{result.output_path}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "CSR Signing Error", str(exc))

    def export_chain(self) -> None:
        """Export mTLS certificate chain to exports."""
        try:
            chain_path = MTLSService.export_chain(self.state.storage_paths)
            self.state.audit_logger.append("mtls_chain_exported", {"chain_path": str(chain_path)})
            self.status_callback(f"mTLS chain exported: {chain_path.name}")
            show_info(self, "Exported", f"mTLS chain exported to:\n{chain_path}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Chain Export Error", str(exc))
