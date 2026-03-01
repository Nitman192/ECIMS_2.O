"""Tests for settings and offline acknowledgement persistence."""

from __future__ import annotations

from la_gui.core.settings_service import SettingsService
from la_gui.core.storage_paths import StoragePaths


def test_settings_default_and_offline_ack(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    settings = SettingsService.load_settings(paths)
    assert settings.require_offline_ack is True
    assert settings.lock_on_idle_seconds == 300

    assert not SettingsService.has_offline_ack(paths)
    SettingsService.write_offline_ack(paths)
    assert SettingsService.has_offline_ack(paths)
