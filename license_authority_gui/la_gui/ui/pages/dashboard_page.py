"""Dashboard page for runtime status and recent actions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from la_gui.core.export_bundle import ExportBundleService
from la_gui.ui.helpers import confirm_action, open_json_file, show_error, show_info
from la_gui.ui.preview_dialog import confirm_export_preview
from la_gui.ui.state import SessionState
from la_gui.ui.style_helpers import card_frame, section_header, set_primary


class DashboardPage(QWidget):
    """Shows key status, storage paths, recent audit activity, and bundle export action."""

    def __init__(self, state: SessionState, status_callback):
        super().__init__()
        self.state = state
        self.status_callback = status_callback

        self._status_label = QLabel()
        self._paths_label = QLabel()
        self._recent_actions = QTextEdit()
        self._recent_actions.setReadOnly(True)

        export_bundle_btn = QPushButton("Export Activation Bundle")
        export_bundle_btn.setProperty("action_id", "activation.export")
        set_primary(export_bundle_btn)
        export_bundle_btn.clicked.connect(self.export_activation_bundle)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        card = card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(10)
        card_layout.addWidget(section_header("Dashboard"))
        card_layout.addWidget(self._status_label)
        card_layout.addWidget(self._paths_label)
        card_layout.addWidget(export_bundle_btn)
        card_layout.addWidget(QLabel("Recent Audit Actions (last 5)"))
        card_layout.addWidget(self._recent_actions)
        layout.addWidget(card)

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

    def export_activation_bundle(self) -> None:
        """Create activation bundle zip from exported artifacts and verify manifest."""
        try:
            license_path = self._pick_or_find_license()
            if license_path is None:
                raise ValueError("No license file selected or found in exports.")

            include: list[Path] = [license_path]
            root_pub = self.state.storage_paths.root_public_key_path
            if root_pub.exists():
                include.append(root_pub)

            optional_candidates = [
                self.state.storage_paths.exports_dir / "mtls_ca_cert.pem",
                self.state.storage_paths.exports_dir / "mtls_chain.pem",
                self.state.storage_paths.exports_dir / "data_key_bundle.json",
                self._latest_file("revocation_*.json"),
            ]
            for item in optional_candidates:
                if item is not None and item.exists():
                    include.append(item)

            if self.state.settings.confirm_sensitive_actions and not confirm_action(self, "Confirm Activation Bundle Export", "Create activation bundle ZIP in exports/ and run manifest verification?"):
                return
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            zip_path = self.state.storage_paths.exports_dir / f"activation_bundle_{stamp}.zip"
            preview_items = [p.name for p in include]
            if not confirm_export_preview(self, self.state, export_type="activation_bundle", destination=zip_path, items=preview_items):
                return
            ExportBundleService.create_activation_bundle(zip_path, include)
            self.state.audit_logger.append(
                "activation_bundle_exported",
                {"zip_path": str(zip_path), "file_count": len(include)},
            )

            ok, details = ExportBundleService.verify_manifest(zip_path)
            self.state.audit_logger.append(
                "activation_bundle_verified",
                {"zip_path": str(zip_path), "ok": ok, "details": details},
            )
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type="activation.export",
                outcome="success" if ok else "fail",
                safe_metadata={"filename": zip_path.name, "verify": ok},
            )
            self.status_callback(f"Activation bundle created: {zip_path.name} | verify={ok}")
            show_info(self, "Activation Bundle", f"Bundle exported to:\n{zip_path}\n\nManifest verified: {ok}")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self.state.activity_log.append(
                actor_role=self.state.current_role,
                mode="Advanced" if self.state.settings.show_advanced_mode else "Standard",
                action_type="activation.export",
                outcome="fail",
                safe_metadata={"error": str(exc)},
            )
            show_error(self, "Bundle Export Error", str(exc))

    def _pick_or_find_license(self) -> Path | None:
        selected = open_json_file(self)
        if selected is not None:
            return selected
        return self._latest_file("license_*.json")

    def _latest_file(self, pattern: str) -> Path | None:
        candidates = sorted(self.state.storage_paths.exports_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return None
        return candidates[-1]
