"""Visible operator settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from la_gui.core.settings_service import AppSettings
from la_gui.ui.role_service import ALL_ROLES


class SettingsDialog(QDialog):
    """UI dialog for app settings and role selection."""

    def __init__(self, settings: AppSettings, current_role: str):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setModal(True)

        self.advanced_mode = QCheckBox("Enable Advanced Mode")
        self.advanced_mode.setChecked(settings.show_advanced_mode)

        self.confirm_sensitive = QCheckBox("Confirm Sensitive Actions")
        self.confirm_sensitive.setChecked(settings.confirm_sensitive_actions)

        self.idle_minutes = QSpinBox()
        self.idle_minutes.setRange(0, 1440)
        self.idle_minutes.setValue(settings.lock_on_idle_seconds // 60)

        self.role_combo = QComboBox()
        self.role_combo.addItems(ALL_ROLES)
        idx = max(0, self.role_combo.findText(current_role))
        self.role_combo.setCurrentIndex(idx)

        form = QFormLayout()
        form.addRow("Role:", self.role_combo)
        form.addRow(self.advanced_mode)
        form.addRow(self.confirm_sensitive)
        form.addRow("Idle Lock Timeout (minutes):", self.idle_minutes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self._on_apply)

        self._apply_clicked = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_apply(self) -> None:
        self._apply_clicked = True

    def to_settings(self, base: AppSettings) -> AppSettings:
        return AppSettings(
            require_offline_ack=base.require_offline_ack,
            show_advanced_mode=self.advanced_mode.isChecked(),
            confirm_sensitive_actions=self.confirm_sensitive.isChecked(),
            lock_on_idle_seconds=int(self.idle_minutes.value()) * 60,
        )

    @property
    def selected_role(self) -> str:
        return self.role_combo.currentText()

    @property
    def apply_clicked(self) -> bool:
        return self._apply_clicked
