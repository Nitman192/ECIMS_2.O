"""Offline acknowledgement modal dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class OfflineAckDialog(QDialog):
    """Dialog requiring operator offline acknowledgement."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Offline Safety Acknowledgement")
        self.setModal(True)

        self.checkbox = QCheckBox("I understand")
        self.checkbox.stateChanged.connect(self._update_buttons)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("This workstation must remain offline. Proceed?"))
        layout.addWidget(self.checkbox)
        layout.addWidget(self.buttons)
        self._update_buttons()

    def _update_buttons(self) -> None:
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(self.checkbox.isChecked())
