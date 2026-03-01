"""Offline-safe workspace diagnostics export."""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from la_gui.core.storage_paths import StoragePaths


class DiagnosticsService:
    """Exports selected non-secret files for diagnostics."""

    @staticmethod
    def export_workspace_snapshot(storage_paths: StoragePaths, app_root: Path) -> tuple[Path, list[str]]:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        zip_path = storage_paths.exports_dir / f"diagnostics_{stamp}.zip"

        candidates = [
            storage_paths.config_dir / "app_settings.json",
            storage_paths.config_dir / "offline_ack.json",
            storage_paths.config_dir / "latest_data_key_bundle.json",
            storage_paths.logs_dir / "audit_log.jsonl",
            app_root / "README.md",
        ]

        included: list[str] = []
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in candidates:
                if not file_path.exists() or not file_path.is_file():
                    continue
                if storage_paths.keys_dir in file_path.parents:
                    continue
                arc_name = str(file_path.relative_to(app_root)).replace("\\", "/")
                archive.write(file_path, arc_name)
                included.append(arc_name)

        return zip_path, included
