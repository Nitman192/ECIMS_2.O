"""Tests for offline-safe diagnostics snapshot export."""

from __future__ import annotations

import zipfile

from la_gui.core.diagnostics_service import DiagnosticsService
from la_gui.core.storage_paths import StoragePaths


def test_diagnostics_snapshot_excludes_keys(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    (paths.config_dir / "app_settings.json").write_text("{}", encoding="utf-8")
    (paths.logs_dir / "audit_log.jsonl").write_text("", encoding="utf-8")
    (paths.keys_dir / "secret.pem").write_text("secret", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")

    zip_path, included = DiagnosticsService.export_workspace_snapshot(paths, tmp_path)
    assert zip_path.exists()
    assert all(not item.startswith("keys/") for item in included)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "keys/secret.pem" not in names
