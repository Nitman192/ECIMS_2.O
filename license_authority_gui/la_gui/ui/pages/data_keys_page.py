"""Data key bundle management page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from la_gui.core.data_key_service import DataKeyService
from la_gui.ui.helpers import confirm_action, show_error, show_info
from la_gui.ui.preview_dialog import confirm_export_preview
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_primary, set_secondary


class DataKeysPage(QWidget):
    """Generate, rotate, and export data key bundles."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self.bundle_id_label = QLabel("-")
        self.key_id_label = QLabel("-")
        self.algorithm_label = QLabel("-")
        self.created_at_label = QLabel("-")
        self.previous_key_id_label = QLabel("-")

        self.copy_key_id_btn = QPushButton("Copy Key ID")
        self.copy_key_id_btn.setProperty("action_id", "data.copy_key_id")
        set_secondary(self.copy_key_id_btn)
        self.copy_key_id_btn.clicked.connect(lambda: self._copy_text(self.key_id_label.text(), "Key ID copied."))

        self.show_advanced = QCheckBox("Show advanced details")
        self.show_advanced.stateChanged.connect(self._toggle_advanced)

        self.advanced_details = QTextEdit()
        self.advanced_details.setReadOnly(True)
        self.advanced_details.setVisible(False)

        generate_btn = QPushButton("Generate Data Key Bundle")
        generate_btn.setProperty("action_id", "data.generate")
        set_primary(generate_btn)
        generate_btn.clicked.connect(self.generate_bundle)

        rotate_btn = QPushButton("Rotate Data Key Bundle")
        rotate_btn.setProperty("action_id", "data.rotate")
        set_primary(rotate_btn)
        rotate_btn.clicked.connect(self.rotate_bundle)

        export_btn = QPushButton("Export Latest Bundle")
        export_btn.setProperty("action_id", "data.export")
        set_secondary(export_btn)
        export_btn.clicked.connect(self.export_latest)

        actions = QHBoxLayout()
        actions.addWidget(generate_btn)
        actions.addWidget(rotate_btn)
        actions.addWidget(export_btn)

        fields = QFormLayout()
        fields.addRow("Bundle ID:", self.bundle_id_label)
        row = QHBoxLayout()
        row.addWidget(self.key_id_label)
        row.addWidget(self.copy_key_id_btn)
        fields.addRow("Key ID:", row)
        fields.addRow("Algorithm:", self.algorithm_label)
        fields.addRow("Created At:", self.created_at_label)
        fields.addRow("Previous Key ID:", self.previous_key_id_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Data Key Bundles"))
        card_layout.addLayout(actions)
        card_layout.addLayout(fields)
        card_layout.addWidget(self.show_advanced)
        card_layout.addWidget(self.advanced_details)
        layout.addWidget(card)

    def refresh(self) -> None:
        latest = DataKeyService.load_latest_bundle(self.state.storage_paths)
        if not latest:
            self.bundle_id_label.setText("-")
            self.key_id_label.setText("-")
            self.algorithm_label.setText("-")
            self.created_at_label.setText("-")
            self.previous_key_id_label.setText("-")
            self.advanced_details.setPlainText("No data key bundle generated yet.")
            return

        self.bundle_id_label.setText(latest.bundle_id)
        self.key_id_label.setText(latest.key_id)
        self.algorithm_label.setText(latest.algorithm)
        self.created_at_label.setText(latest.created_at)
        self.previous_key_id_label.setText(latest.previous_key_id or "-")

        masked = "***hidden***"
        self.advanced_details.setPlainText(
            "\n".join(
                [
                    f"key_material_b64: {masked}",
                    f"key_material_sha256: {latest.key_material_sha256}",
                ]
            )
        )

    def _toggle_advanced(self, state: int) -> None:
        self.advanced_details.setVisible(state == int(Qt.CheckState.Checked))

    def _copy_text(self, value: str, success_message: str) -> None:
        if not value or value == "-":
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(value)
        self.status_callback(success_message)

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
            path = self.state.storage_paths.exports_dir / "data_key_bundle.json"
            if not confirm_export_preview(self, self.state, export_type="data_key_export", destination=path, items=["data_key_bundle.json"]):
                return
            path = DataKeyService.export_bundle(self.state.storage_paths, bundle)
            self.status_callback(f"Data key bundle exported: {path.name}")
            show_info(self, "Exported", f"Latest data key bundle exported to:\n{path}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Export Error", str(exc))
