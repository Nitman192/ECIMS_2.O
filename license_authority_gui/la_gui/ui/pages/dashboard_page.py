"""Dashboard page for runtime status and recent actions."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from la_gui.ui.state import SessionState


class DashboardPage(QWidget):
    """Shows key status, storage paths, and recent audit activity."""

    def __init__(self, state: SessionState):
        super().__init__()
        self.state = state

        self._status_label = QLabel()
        self._paths_label = QLabel()
        self._recent_actions = QTextEdit()
        self._recent_actions.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Dashboard</h2>"))
        layout.addWidget(self._status_label)
        layout.addWidget(self._paths_label)
        layout.addWidget(QLabel("Recent Audit Actions (last 5)"))
        layout.addWidget(self._recent_actions)

    def refresh(self) -> None:
        """Refresh status and recent event widgets."""
        root_exists = self.state.root_private_key_path.exists()
        self._status_label.setText(
            f"Root key file exists: {'Yes' if root_exists else 'No'} | "
            f"Session unlocked: {'Yes' if self.state.is_unlocked else 'No'}"
        )
        self._paths_label.setText(
            "\n".join(
                [
                    f"keys: {self.state.storage_paths.keys_dir}",
                    f"logs: {self.state.storage_paths.logs_dir}",
                    f"exports: {self.state.storage_paths.exports_dir}",
                    f"config: {self.state.storage_paths.config_dir}",
                ]
            )
        )

        entries = self.state.audit_logger.read_entries()[-5:]
        if not entries:
            self._recent_actions.setPlainText("No audit entries yet.")
            return

        formatted = []
        for entry in entries:
            formatted.append(f"{entry.timestamp} | {entry.actor} | {entry.action} | {entry.details}")
        self._recent_actions.setPlainText("\n".join(formatted))
