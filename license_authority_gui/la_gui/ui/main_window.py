"""Main window with sidebar navigation, hardening tools, and wizard mode."""

from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStyle,
    QWidget,
)

from la_gui.core.diagnostics_service import DiagnosticsService
from la_gui.ui.helpers import show_error, show_info
from la_gui.ui.pages.audit_log_page import AuditLogPage
from la_gui.ui.pages.dashboard_page import DashboardPage
from la_gui.ui.pages.data_keys_page import DataKeysPage
from la_gui.ui.pages.license_signing_page import LicenseSigningPage
from la_gui.ui.pages.mtls_ca_page import MTLSCAPage
from la_gui.ui.pages.revocation_page import RevocationPage
from la_gui.ui.pages.root_key_page import RootKeyPage
from la_gui.ui.pages.wizard_page import WizardPage
from la_gui.ui.state import SessionState


class MainWindow(QMainWindow):
    """Desktop shell for the License Authority tool."""

    def __init__(self, state: SessionState):
        super().__init__()
        self.state = state
        self.page_index_by_name: dict[str, int] = {}

        self.setWindowTitle("ECIMS 2.0 License Authority")
        self.resize(1280, 800)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(280)

        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage(state, self.show_status)
        self.root_key_page = RootKeyPage(state, self.show_status)
        self.license_page = LicenseSigningPage(state, self.show_status)
        self.mtls_page = MTLSCAPage(state, self.show_status)
        self.data_key_page = DataKeysPage(state, self.show_status)
        self.revocation_page = RevocationPage(state, self.show_status)
        self.audit_page = AuditLogPage(state, self.show_status)
        self.wizard_page = WizardPage(
            state,
            self.show_status,
            self.open_page_by_name,
            self.audit_page.verify_chain,
            self.dashboard_page.export_activation_bundle,
        )

        self._add_page("Quick Start (Wizard)", self.wizard_page)

        if self.state.settings.show_advanced_mode:
            self._add_page("Dashboard", self.dashboard_page)
            self._add_page("Root Key Management", self.root_key_page)
            self._add_page("License Signing", self.license_page)
            self._add_page("mTLS CA Management", self.mtls_page)
            self._add_page("Data Key Bundles", self.data_key_page)
            self._add_page("Revocation", self.revocation_page)

        self._add_page("Audit Log", self.audit_page)

        self.sidebar.currentRowChanged.connect(self._on_page_changed)
        self.sidebar.setCurrentRow(0)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)
        self.setCentralWidget(central)

        self._setup_menu()
        self._setup_status_widgets()
        self.update_security_status()

    def _setup_menu(self) -> None:
        tools = self.menuBar().addMenu("Tools")
        export_diag = QAction("Export Diagnostics", self)
        export_diag.triggered.connect(self.export_diagnostics)
        tools.addAction(export_diag)

    def _setup_status_widgets(self) -> None:
        self.security_status_label = QLabel()
        self.last_action_label = QLabel("Last action: Ready")

        lock_button = QPushButton("LOCK")
        lock_button.clicked.connect(self.force_lock)

        self.statusBar().addPermanentWidget(self.security_status_label)
        self.statusBar().addPermanentWidget(self.last_action_label)
        self.statusBar().addPermanentWidget(lock_button)

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
        item = QListWidgetItem(icon, title)
        self.sidebar.addItem(item)
        idx = self.stack.addWidget(page)
        self.page_index_by_name[title] = idx

    def _on_page_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        refresh: Callable[[], None] | None = getattr(page, "refresh", None)
        if refresh:
            refresh()

    def open_page_by_name(self, name: str) -> None:
        idx = self.page_index_by_name.get(name)
        if idx is None:
            return
        self.sidebar.setCurrentRow(idx)

    def show_status(self, message: str) -> None:
        """Show transient status message in status bar."""
        self.state.last_action = message
        self.last_action_label.setText(f"Last action: {message}")
        self.statusBar().showMessage(message, 6000)
        self.update_security_status()

    def update_security_status(self) -> None:
        root = "present" if self.state.root_private_key_path.exists() else "missing"
        ca = "present" if self.state.storage_paths.mtls_ca_cert_path.exists() else "missing"
        lock = "UNLOCKED" if self.state.is_unlocked else "LOCKED"
        self.security_status_label.setText(f"State: {lock} | Root: {root} | CA: {ca}")

    def force_lock(self) -> None:
        self.state.lock()
        self.update_security_status()
        self.show_status("Manual lock executed.")

    def export_diagnostics(self) -> None:
        """Create offline-safe diagnostics zip excluding keys directory."""
        try:
            zip_path, included = DiagnosticsService.export_workspace_snapshot(self.state.storage_paths, self.state.app_root)
            self.state.audit_logger.append(
                "diagnostics_exported",
                {"zip_path": str(zip_path), "included": included},
            )
            self.show_status(f"Diagnostics exported: {zip_path.name}")
            show_info(self, "Diagnostics Export", f"Diagnostics exported to:\n{zip_path}")
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Diagnostics Error", str(exc))
