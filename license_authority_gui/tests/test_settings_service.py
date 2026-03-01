"""Tests for settings, offline acknowledgement, and UI state persistence."""

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


def test_last_opened_page_persistence(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    assert SettingsService.load_last_opened_page(paths) is None
    SettingsService.save_last_opened_page(paths, "License Signing")
    assert SettingsService.load_last_opened_page(paths) == "License Signing"


def test_role_persistence_in_ui_state(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    assert SettingsService.load_current_role(paths) == "Admin"
    SettingsService.save_current_role(paths, "Auditor")
    assert SettingsService.load_current_role(paths) == "Auditor"


def test_preview_preferences_persistence(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    assert not SettingsService.is_preview_disabled(paths, "Admin", "activation_bundle")
    SettingsService.set_preview_disabled(paths, "Admin", "activation_bundle", True)
    assert SettingsService.is_preview_disabled(paths, "Admin", "activation_bundle")