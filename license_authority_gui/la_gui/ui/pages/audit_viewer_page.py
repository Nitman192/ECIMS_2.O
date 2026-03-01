"""Advanced activity audit viewer page."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.preview_dialog import confirm_export_preview
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_primary, set_secondary


class AuditViewerPage(QWidget):
    """Browse, filter, and export safe activity log entries."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback
        self._current_entries = []

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")

        self.role_filter = QComboBox()
        self.role_filter.addItems(["All", "Admin", "Operator", "Auditor"])

        self.outcome_filter = QComboBox()
        self.outcome_filter.addItems(["All", "success", "fail"])

        self.action_filter = QComboBox()
        self.action_filter.addItems(["All"])

        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(datetime.utcnow().date().replace(day=1))

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(datetime.utcnow().date())

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("action_id", "activity.refresh")
        set_secondary(refresh_btn)
        refresh_btn.clicked.connect(self.refresh)

        export_btn = QPushButton("Export Activity Log")
        export_btn.setProperty("action_id", "activity.export")
        set_primary(export_btn)
        export_btn.clicked.connect(self.export_log)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Role", "Mode", "Action", "Outcome"])
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._load_selected_details)

        self.details = QTextEdit()
        self.details.setReadOnly(True)

        filter_form = QFormLayout()
        filter_form.addRow("Search:", self.search_input)
        filter_form.addRow("Role:", self.role_filter)
        filter_form.addRow("Outcome:", self.outcome_filter)
        filter_form.addRow("Action Type:", self.action_filter)
        filter_form.addRow("From:", self.from_date)
        filter_form.addRow("To:", self.to_date)

        top_actions = QHBoxLayout()
        top_actions.addWidget(refresh_btn)
        top_actions.addWidget(export_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Details (safe metadata)"))
        right_layout.addWidget(self.details)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([700, 300])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Audit Viewer"))
        card_layout.addLayout(filter_form)
        card_layout.addLayout(top_actions)
        card_layout.addWidget(splitter)
        layout.addWidget(card)

    def refresh(self) -> None:
        entries = self.state.activity_log.query(
            search=self.search_input.text(),
            role=self.role_filter.currentText(),
            outcome=self.outcome_filter.currentText(),
            action_type=self.action_filter.currentText(),
            date_from=self.from_date.date().toPython(),
            date_to=self.to_date.date().toPython(),
        )
        self._current_entries = entries

        # refresh action types list
        action_types = ["All"] + self.state.activity_log.known_action_types()
        current = self.action_filter.currentText()
        self.action_filter.blockSignals(True)
        self.action_filter.clear()
        self.action_filter.addItems(action_types)
        idx = max(0, self.action_filter.findText(current))
        self.action_filter.setCurrentIndex(idx)
        self.action_filter.blockSignals(False)

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.timestamp))
            self.table.setItem(row, 1, QTableWidgetItem(entry.actor_role))
            self.table.setItem(row, 2, QTableWidgetItem(entry.mode))
            self.table.setItem(row, 3, QTableWidgetItem(entry.action_type))
            self.table.setItem(row, 4, QTableWidgetItem(entry.outcome))

        self.details.setPlainText("")
        self.status_callback(f"Audit viewer loaded {len(entries)} entries.")

    def _load_selected_details(self) -> None:
        selected = self.table.currentRow()
        if selected < 0 or selected >= len(self._current_entries):
            self.details.setPlainText("")
            return
        entry = self._current_entries[selected]
        self.details.setPlainText(json.dumps(entry.safe_metadata, indent=2, sort_keys=True))

    def export_log(self) -> None:
        try:
            default = self.state.storage_paths.exports_dir / "activity_log_export.jsonl"
            file_name, _ = QFileDialog.getSaveFileName(self, "Export Activity Log", str(default), "JSONL Files (*.jsonl)")
            if not file_name:
                return
            path = Path(file_name)
            if not confirm_export_preview(self, self.state, export_type="activity_log_export", destination=path, items=[path.name]):
                return
            self.state.activity_log.export(path)
            self.status_callback(f"Activity log exported: {path.name}")
            show_info(self, "Exported", f"Activity log exported to:\n{path}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Activity Export Error", str(exc))
