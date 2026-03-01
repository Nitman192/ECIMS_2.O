"""Main window with sidebar navigation and page stack."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from la_gui.ui.pages.audit_log_page import AuditLogPage
from la_gui.ui.pages.dashboard_page import DashboardPage
from la_gui.ui.pages.license_signing_page import LicenseSigningPage
from la_gui.ui.pages.placeholder_page import PlaceholderPage
from la_gui.ui.pages.revocation_page import RevocationPage
from la_gui.ui.pages.root_key_page import RootKeyPage
from la_gui.ui.state import SessionState


class MainWindow(QMainWindow):
    """Desktop shell for the License Authority tool."""

    def __init__(self, state: SessionState):
        super().__init__()
        self.state = state
        self.setWindowTitle("ECIMS 2.0 License Authority")
        self.resize(1200, 760)

        central = QWidget()
        layout = QHBoxLayout(central)

        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(260)

        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage(state)
        self.root_key_page = RootKeyPage(state, self.show_status)
        self.license_page = LicenseSigningPage(state, self.show_status)
        self.revocation_page = RevocationPage(state, self.show_status)
        self.audit_page = AuditLogPage(state, self.show_status)
        self.mtls_placeholder = PlaceholderPage("mTLS CA Management")
        self.data_key_placeholder = PlaceholderPage("Data Key Bundles")

        self._add_page("Dashboard", self.dashboard_page)
        self._add_page("Root Key Management", self.root_key_page)
        self._add_page("License Signing", self.license_page)
        self._add_page("mTLS CA Management", self.mtls_placeholder)
        self._add_page("Data Key Bundles", self.data_key_placeholder)
        self._add_page("Revocation", self.revocation_page)
        self._add_page("Audit Log", self.audit_page)

        self.sidebar.currentRowChanged.connect(self._on_page_changed)
        self.sidebar.setCurrentRow(0)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Ready")

    def _add_page(self, title: str, page: QWidget) -> None:
        self.sidebar.addItem(QListWidgetItem(title))
        self.stack.addWidget(page)

    def _on_page_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        refresh: Callable[[], None] | None = getattr(page, "refresh", None)
        if refresh:
            refresh()

    def show_status(self, message: str) -> None:
        """Show transient status message in status bar."""
        self.statusBar().showMessage(message, 6000)
