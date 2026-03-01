"""Pre-export preview dialog and role-aware preference checks."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QListWidget, QVBoxLayout, QWidget

from la_gui.core.settings_service import SettingsService
from la_gui.ui.state import SessionState


class ExportPreviewDialog(QDialog):
    """Shows safe export summary before writing files."""

    def __init__(self, export_type: str, destination: Path, items: list[str], role: str):
        super().__init__()
        self.setWindowTitle("Export Preview")
        self.setModal(True)

        title = QLabel(f"Export Type: {export_type}")
        dest = QLabel(f"Destination: {destination}")
        note = QLabel("Keys/Secrets are excluded")

        listing = QListWidget()
        listing.addItems(items)

        self.skip_checkbox = QCheckBox("Do not show again for this export type")
        self.skip_checkbox.setEnabled(role != "Auditor")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(dest)
        layout.addWidget(note)
        layout.addWidget(listing)
        layout.addWidget(self.skip_checkbox)
        layout.addWidget(buttons)


def confirm_export_preview(
    parent: QWidget,
    state: SessionState,
    *,
    export_type: str,
    destination: Path,
    items: list[str],
) -> bool:
    """Show role-aware preview unless disabled in UI state preferences."""
    role = state.current_role
    if role != "Auditor" and SettingsService.is_preview_disabled(state.storage_paths, role, export_type):
        return True

    dlg = ExportPreviewDialog(export_type=export_type, destination=destination, items=items, role=role)
    if dlg.exec() != 1:
        return False

    if role != "Auditor" and dlg.skip_checkbox.isChecked():
        SettingsService.set_preview_disabled(state.storage_paths, role, export_type, True)

    return True
