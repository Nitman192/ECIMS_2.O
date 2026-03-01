"""Data key bundle management page."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from la_gui.core.data_key_service import DataKeyService
from la_gui.ui.helpers import confirm_action, show_error, show_info
from la_gui.ui.state import SessionState


class DataKeysPage(QWidget):
    """Generate, rotate, and export data key bundles."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        generate_btn = QPushButton("Generate Data Key Bundle")
        generate_btn.clicked.connect(self.generate_bundle)

        rotate_btn = QPushButton("Rotate Data Key Bundle")
        rotate_btn.clicked.connect(self.rotate_bundle)

        export_btn = QPushButton("Export Latest Bundle")
        export_btn.clicked.connect(self.export_latest)

        actions = QHBoxLayout()
        actions.addWidget(generate_btn)
        actions.addWidget(rotate_btn)
        actions.addWidget(export_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Data Key Bundles</h2>"))
        layout.addLayout(actions)
        layout.addWidget(self.output)

    def refresh(self) -> None:
        latest = DataKeyService.load_latest_bundle(self.state.storage_paths)
        if not latest:
            self.output.setPlainText("No data key bundle generated yet.")
            return
        self.output.setPlainText(str(latest.to_dict()))

    def generate_bundle(self) -> None:
        """Generate new data key bundle."""
        try:
            if self.state.settings.confirm_sensitive_actions and not confirm_action(self, "Confirm Data Key Generation", "Generate new data key bundle and persist in config/ and exports/?"):
                return
            bundle = DataKeyService.generate_data_key_bundle(self.state.storage_paths)
            self.state.audit_logger.append("data_key_bundle_generated", {"bundle_id": bundle.bundle_id, "key_id": bundle.key_id})
            self.status_callback("Data key bundle generated.")
            self.refresh()
            show_info(self, "Generated", "Data key bundle generated and exported.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Data Key Error", str(exc))

    def rotate_bundle(self) -> None:
        """Rotate data key bundle with previous key linkage."""
        try:
            if self.state.settings.confirm_sensitive_actions and not confirm_action(self, "Confirm Data Key Rotation", "Rotate data key bundle and export updated bundle?"):
                return
            bundle = DataKeyService.rotate_data_key_bundle(self.state.storage_paths)
            self.state.audit_logger.append(
                "data_key_bundle_rotated",
                {"bundle_id": bundle.bundle_id, "key_id": bundle.key_id, "previous_key_id": bundle.previous_key_id},
            )
            self.status_callback("Data key bundle rotated.")
            self.refresh()
            show_info(self, "Rotated", "Data key bundle rotated and exported.")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Data Key Error", str(exc))

    def export_latest(self) -> None:
        """Re-export latest bundle to exports directory."""
        try:
            bundle = DataKeyService.load_latest_bundle(self.state.storage_paths)
            if bundle is None:
                raise ValueError("No latest bundle found. Generate one first.")
            path = DataKeyService.export_bundle(self.state.storage_paths, bundle)
            self.status_callback(f"Data key bundle exported: {path.name}")
            show_info(self, "Exported", f"Latest data key bundle exported to:\n{path}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Export Error", str(exc))
