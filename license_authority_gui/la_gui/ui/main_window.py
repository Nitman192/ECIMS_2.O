"""Main window with polished navigation, settings, role permissions, and header bar."""

from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from la_gui import __version__
from la_gui.core.diagnostics_service import DiagnosticsService
from la_gui.core.settings_service import SettingsService
from la_gui.ui.feature_flags import ENABLE_SERVER_ACTIVATION
from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.lock_overlay import LockOverlayDialog
from la_gui.ui.pages.audit_log_page import AuditLogPage
from la_gui.ui.pages.audit_viewer_page import AuditViewerPage
from la_gui.ui.pages.dashboard_page import DashboardPage
from la_gui.ui.pages.data_keys_page import DataKeysPage
from la_gui.ui.pages.license_signing_page import LicenseSigningPage
from la_gui.ui.pages.mtls_ca_page import MTLSCAPage
from la_gui.ui.pages.revocation_page import RevocationPage
from la_gui.ui.pages.root_key_page import RootKeyPage
from la_gui.ui.pages.server_activation_page import ServerActivationPage
from la_gui.ui.pages.wizard_page import WizardPage
from la_gui.ui.preview_dialog import confirm_export_preview
from la_gui.ui.role_service import can_perform
from la_gui.ui.settings_dialog import SettingsDialog
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_danger


class MainWindow(QMainWindow):
    """Desktop shell for the License Authority tool."""

    def __init__(self, state: SessionState):
        super().__init__()
        self.state = state
        self.page_index_by_name: dict[str, int] = {}
        self.page_name_by_index: dict[int, str] = {}

        self.setWindowTitle("ECIMS 2.0 License Authority")
        self.resize(1280, 800)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("navigation")
        self.sidebar.setMinimumWidth(250)
        self.sidebar.setMaximumWidth(320)
        self.sidebar.setSpacing(4)
        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage(state, self.show_status)
        self.root_key_page = RootKeyPage(state, self.show_status)
        self.license_page = LicenseSigningPage(state, self.show_status)
        self.activation_page = ServerActivationPage(state, self.show_status)
        self.mtls_page = MTLSCAPage(state, self.show_status)
        self.data_key_page = DataKeysPage(state, self.show_status)
        self.revocation_page = RevocationPage(state, self.show_status)
        self.audit_page = AuditLogPage(state, self.show_status)
        self.activity_viewer_page = AuditViewerPage(state, self.show_status)
        self.wizard_page = WizardPage(
            state,
            self.show_status,
            self.open_page_by_name,
            self.audit_page.verify_chain,
            self.dashboard_page.export_activation_bundle,
            self.permission_for,
        )

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        header_card = card_frame()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title_layout.addWidget(section_header("ECIMS 2.0 License Authority"))
        subtitle = QLabel("Offline license activation and signing console")
        subtitle.setProperty("role", "muted")
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch(1)

        self.mode_label = QLabel()
        self.role_label = QLabel()
        self.lock_label = QLabel()
        self.version_label = QLabel(f"v{__version__}")
        self.environment_label = QLabel("Offline-ready")

        for label in [self.mode_label, self.role_label, self.lock_label, self.environment_label]:
            label.setProperty("role", "chip")
        self.version_label.setProperty("role", "muted")

        header_layout.addWidget(self.mode_label)
        header_layout.addWidget(self.role_label)
        header_layout.addWidget(self.lock_label)
        header_layout.addWidget(self.version_label)
        header_layout.addWidget(self.environment_label)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(10)
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.stack)

        root_layout.addWidget(header_card)
        root_layout.addLayout(body_layout)

        self.setCentralWidget(central)
        self.lock_overlay = LockOverlayDialog(self)

        self._setup_menu()
        self._setup_status_widgets()
        self._rebuild_navigation()
        self.sidebar.currentRowChanged.connect(self._on_page_changed)
        self._apply_startup_page_selection()
        self.update_security_status()
        self.apply_role_permissions()

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        settings_menu = self.menuBar().addMenu("Settings")
        settings_action = QAction("Preferences", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(settings_action)

        tools_menu = self.menuBar().addMenu("Tools")
        self.export_diag_action = QAction("Export Diagnostics", self)
        self.export_diag_action.setProperty("action_id", "diagnostics.export")
        self.export_diag_action.triggered.connect(self.export_diagnostics)
        tools_menu.addAction(self.export_diag_action)

        help_menu = self.menuBar().addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _setup_status_widgets(self) -> None:
        self.security_status_label = QLabel()
        self.last_action_label = QLabel("Last action: Ready")
        self.security_status_label.setProperty("role", "muted")
        self.last_action_label.setProperty("role", "muted")

        lock_button = QPushButton("Lock Session")
        lock_button.setProperty("action_id", "root.lock")
        set_danger(lock_button)
        lock_button.clicked.connect(self.force_lock)

        self.statusBar().addPermanentWidget(self.security_status_label)
        self.statusBar().addPermanentWidget(self.last_action_label)
        self.statusBar().addPermanentWidget(lock_button)

    def _clear_navigation(self) -> None:
        self.sidebar.clear()
        while self.stack.count():
            self.stack.removeWidget(self.stack.widget(0))
        self.page_index_by_name.clear()
        self.page_name_by_index.clear()

    def _rebuild_navigation(self) -> None:
        self._clear_navigation()

        self._add_page("Quick Start (Wizard)", self.wizard_page)
        if ENABLE_SERVER_ACTIVATION:
            self._add_page("Server Activation", self.activation_page)
        self._add_page("Root Key Management", self.root_key_page)
        self._add_page("License Signing", self.license_page)

        if self.state.settings.show_advanced_mode:
            self._add_page("Dashboard", self.dashboard_page)
            self._add_page("mTLS CA Management", self.mtls_page)
            self._add_page("Data Key Bundles", self.data_key_page)
            self._add_page("Revocation", self.revocation_page)

        self._add_page("Audit Log", self.audit_page)

        if self.state.settings.show_advanced_mode:
            self._add_page("Audit Viewer", self.activity_viewer_page)

        mode = "Advanced" if self.state.settings.show_advanced_mode else "Standard"
        self.mode_label.setText(f"Mode: {mode}")
        self.role_label.setText(f"Role: {self.state.current_role}")

    def _add_page(self, title: str, page: QWidget) -> None:
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        if "Wizard" in title:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight)
        elif "Audit" in title:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        elif "Root" in title:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        elif "License" in title:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        elif "Server Activation" in title:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)

        item = QListWidgetItem(icon, title)
        self.sidebar.addItem(item)
        idx = self.stack.addWidget(page)
        self.page_index_by_name[title] = idx
        self.page_name_by_index[idx] = title

    def _apply_startup_page_selection(self) -> None:
        if not self.state.settings.show_advanced_mode:
            self.open_page_by_name("Quick Start (Wizard)")
            return

        remembered = SettingsService.load_last_opened_page(self.state.storage_paths)
        if remembered and remembered in self.page_index_by_name:
            self.open_page_by_name(remembered)
        else:
            self.open_page_by_name("Quick Start (Wizard)")

    def _on_page_changed(self, index: int) -> None:
        if index < 0:
            return

        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        refresh: Callable[[], None] | None = getattr(page, "refresh", None)
        if refresh:
            refresh()

        page_name = self.page_name_by_index.get(index)
        if self.state.settings.show_advanced_mode and page_name:
            SettingsService.save_last_opened_page(self.state.storage_paths, page_name)

        self.apply_role_permissions()

    def open_page_by_name(self, name: str) -> None:
        idx = self.page_index_by_name.get(name)
        if idx is None:
            return
        self.sidebar.setCurrentRow(idx)

    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.state.settings, self.state.current_role)
        while True:
            result = dialog.exec()
            if dialog.apply_clicked:
                self._apply_settings_from_dialog(dialog)
                dialog._apply_clicked = False
                continue
            if result == int(dialog.DialogCode.Accepted):
                self._apply_settings_from_dialog(dialog)
            return

    def _apply_settings_from_dialog(self, dialog: SettingsDialog) -> None:
        self.state.settings = dialog.to_settings(self.state.settings)
        self.state.current_role = dialog.selected_role
        SettingsService.save_settings(self.state.storage_paths, self.state.settings)
        SettingsService.save_current_role(self.state.storage_paths, self.state.current_role)

        current = self.current_page_name()
        self._rebuild_navigation()

        if not self.state.settings.show_advanced_mode:
            self.open_page_by_name("Quick Start (Wizard)")
        elif current and current in self.page_index_by_name:
            self.open_page_by_name(current)
        else:
            self.open_page_by_name("Quick Start (Wizard)")

        self.apply_role_permissions()
        self.state.activity_log.append(
            actor_role=self.state.current_role,
            mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
            action_type="settings.updated",
            outcome="success",
            safe_metadata={"role": self.state.current_role},
        )
        self.show_status("Settings updated.")

    def current_page_name(self) -> str | None:
        return self.page_name_by_index.get(self.stack.currentIndex())

    def show_about(self) -> None:
        QMessageBox.information(self, "About", "ECIMS 2.0 License Authority\nOffline desktop tool.")

    def permission_for(self, action_id: str | None) -> tuple[bool, str]:
        decision = can_perform(self.state.current_role, action_id)
        return decision.allowed, decision.reason

    def apply_role_permissions(self) -> None:
        for button in self.findChildren(QPushButton):
            action_id = button.property("action_id")
            if not action_id:
                continue

            base_enabled = button.property("base_enabled")
            if base_enabled is None:
                base_enabled = button.isEnabled()
                button.setProperty("base_enabled", base_enabled)

            allowed, reason = self.permission_for(str(action_id))
            button.setEnabled(bool(base_enabled) and allowed)
            button.setToolTip(reason if not allowed and reason else "")

        action_base_enabled = self.export_diag_action.property("base_enabled")
        if action_base_enabled is None:
            action_base_enabled = self.export_diag_action.isEnabled()
            self.export_diag_action.setProperty("base_enabled", action_base_enabled)

        allowed, reason = self.permission_for(str(self.export_diag_action.property("action_id")))
        self.export_diag_action.setEnabled(bool(action_base_enabled) and allowed)
        self.export_diag_action.setToolTip(reason if not allowed and reason else "")

    def show_status(self, message: str) -> None:
        self.state.last_action = message
        self.last_action_label.setText(f"Last action: {message}")
        self.statusBar().showMessage(message, 6000)
        self.update_security_status()

    def update_security_status(self) -> None:
        root = "present" if self.state.root_private_key_path.exists() else "missing"
        ca = "present" if self.state.storage_paths.mtls_ca_cert_path.exists() else "missing"
        lock = "Unlocked" if self.state.is_unlocked else "Locked"
        self.lock_label.setText(f"Session: {lock}")
        self.security_status_label.setText(f"State: {lock} | Root key: {root} | mTLS CA: {ca}")
        self.role_label.setText(f"Role: {self.state.current_role}")

    def force_lock(self, reason: str = "Manual lock") -> None:
        self.state.lock()
        self.state.activity_log.append(
            actor_role=self.state.current_role,
            mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
            action_type="session.lock",
            outcome="success",
            safe_metadata={"reason": reason},
        )
        self.update_security_status()
        self.show_status("Session locked.")
        self.lock_overlay.open_for_reason(reason)

    def export_diagnostics(self) -> None:
        """Create offline-safe diagnostics zip excluding keys directory."""
        try:
            destination = self.state.storage_paths.exports_dir / "diagnostics_<timestamp>.zip"
            preview_items = [
                "config/app_settings.json",
                "config/offline_ack.json (if present)",
                "config/latest_data_key_bundle.json (if present)",
                "logs/audit_log.jsonl",
                "README.md",
            ]
            if not confirm_export_preview(self, self.state, export_type="diagnostics", destination=destination, items=preview_items):
                return

            zip_path, included = DiagnosticsService.export_workspace_snapshot(self.state.storage_paths, self.state.app_root)
            self.state.audit_logger.append(
                "diagnostics_exported",
                {"zip_path": str(zip_path), "included": included},
            )
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type="diagnostics.export",
                outcome="success",
                safe_metadata={"filename": zip_path.name, "count": len(included)},
            )
            self.show_status(f"Diagnostics exported: {zip_path.name}")
            show_info(self, "Diagnostics Export", f"Diagnostics exported to:\n{zip_path}")
        except Exception as exc:  # noqa: BLE001
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type="diagnostics.export",
                outcome="fail",
                safe_metadata={"error": str(exc)},
            )
            show_error(self, "Diagnostics Error", str(exc))
