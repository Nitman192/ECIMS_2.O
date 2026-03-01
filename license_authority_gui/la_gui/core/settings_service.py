"""Application settings and offline acknowledgement persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from la_gui.core.storage_paths import StoragePaths


@dataclass(slots=True)
class AppSettings:
    """Operator safety settings persisted in config/app_settings.json."""

    require_offline_ack: bool = True
    show_advanced_mode: bool = True
    confirm_sensitive_actions: bool = True
    lock_on_idle_seconds: int = 300


class SettingsService:
    """Load/store app safety settings and offline acknowledgement."""

    @staticmethod
    def settings_path(storage_paths: StoragePaths) -> Path:
        return storage_paths.config_dir / "app_settings.json"

    @staticmethod
    def offline_ack_path(storage_paths: StoragePaths) -> Path:
        return storage_paths.config_dir / "offline_ack.json"

    @staticmethod
    def load_settings(storage_paths: StoragePaths) -> AppSettings:
        path = SettingsService.settings_path(storage_paths)
        if not path.exists():
            settings = AppSettings()
            path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True), encoding="utf-8")
            return settings

        raw = json.loads(path.read_text(encoding="utf-8"))
        return AppSettings(
            require_offline_ack=bool(raw.get("require_offline_ack", True)),
            show_advanced_mode=bool(raw.get("show_advanced_mode", True)),
            confirm_sensitive_actions=bool(raw.get("confirm_sensitive_actions", True)),
            lock_on_idle_seconds=max(0, int(raw.get("lock_on_idle_seconds", 300))),
        )

    @staticmethod
    def has_offline_ack(storage_paths: StoragePaths) -> bool:
        path = SettingsService.offline_ack_path(storage_paths)
        if not path.exists():
            return False
        raw = json.loads(path.read_text(encoding="utf-8"))
        return bool(raw.get("acknowledged", False))

    @staticmethod
    def write_offline_ack(storage_paths: StoragePaths) -> None:
        path = SettingsService.offline_ack_path(storage_paths)
        path.write_text(json.dumps({"acknowledged": True}, indent=2, sort_keys=True), encoding="utf-8")
