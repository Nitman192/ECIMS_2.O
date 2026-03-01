"""Application settings, UI state, and offline acknowledgement persistence."""

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
    """Load/store app safety settings and runtime UI state."""

    # ---------- Paths ----------

    @staticmethod
    def settings_path(storage_paths: StoragePaths) -> Path:
        return storage_paths.config_dir / "app_settings.json"

    @staticmethod
    def offline_ack_path(storage_paths: StoragePaths) -> Path:
        return storage_paths.config_dir / "offline_ack.json"

    @staticmethod
    def ui_state_path(storage_paths: StoragePaths) -> Path:
        return storage_paths.config_dir / "ui_state.json"

    # ---------- Internal helpers ----------

    @staticmethod
    def _load_ui_state(storage_paths: StoragePaths) -> dict[str, object]:
        path = SettingsService.ui_state_path(storage_paths)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt or partial file -> start fresh (UI-only state)
            return {}

    @staticmethod
    def _save_ui_state(storage_paths: StoragePaths, payload: dict[str, object]) -> None:
        storage_paths.config_dir.mkdir(parents=True, exist_ok=True)
        path = SettingsService.ui_state_path(storage_paths)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    # ---------- App settings ----------

    @staticmethod
    def load_settings(storage_paths: StoragePaths) -> AppSettings:
        path = SettingsService.settings_path(storage_paths)
        if not path.exists():
            settings = AppSettings()
            storage_paths.config_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True), encoding="utf-8")
            return settings

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

        return AppSettings(
            require_offline_ack=bool(raw.get("require_offline_ack", True)),
            show_advanced_mode=bool(raw.get("show_advanced_mode", True)),
            confirm_sensitive_actions=bool(raw.get("confirm_sensitive_actions", True)),
            lock_on_idle_seconds=max(0, int(raw.get("lock_on_idle_seconds", 300))),
        )

    @staticmethod
    def save_settings(storage_paths: StoragePaths, settings: AppSettings) -> None:
        storage_paths.config_dir.mkdir(parents=True, exist_ok=True)
        path = SettingsService.settings_path(storage_paths)
        path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True), encoding="utf-8")

    # ---------- Offline acknowledgement ----------

    @staticmethod
    def has_offline_ack(storage_paths: StoragePaths) -> bool:
        path = SettingsService.offline_ack_path(storage_paths)
        if not path.exists():
            return False
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return bool(raw.get("acknowledged", False))

    @staticmethod
    def write_offline_ack(storage_paths: StoragePaths) -> None:
        storage_paths.config_dir.mkdir(parents=True, exist_ok=True)
        path = SettingsService.offline_ack_path(storage_paths)
        path.write_text(json.dumps({"acknowledged": True}, indent=2, sort_keys=True), encoding="utf-8")

    # ---------- UI state: navigation ----------

    @staticmethod
    def load_last_opened_page(storage_paths: StoragePaths) -> str | None:
        raw = SettingsService._load_ui_state(storage_paths)
        value = raw.get("last_opened_page")
        return value if isinstance(value, str) and value else None

    @staticmethod
    def save_last_opened_page(storage_paths: StoragePaths, page_name: str) -> None:
        raw = SettingsService._load_ui_state(storage_paths)
        raw["last_opened_page"] = page_name
        SettingsService._save_ui_state(storage_paths, raw)

    # ---------- UI state: roles ----------

    @staticmethod
    def load_current_role(storage_paths: StoragePaths) -> str:
        raw = SettingsService._load_ui_state(storage_paths)
        value = raw.get("current_role")
        return value if isinstance(value, str) and value else "Admin"

    @staticmethod
    def save_current_role(storage_paths: StoragePaths, role: str) -> None:
        raw = SettingsService._load_ui_state(storage_paths)
        raw["current_role"] = role
        SettingsService._save_ui_state(storage_paths, raw)

    # ---------- UI state: export preview preferences ----------

    @staticmethod
    def is_preview_disabled(storage_paths: StoragePaths, role: str, export_type: str) -> bool:
        raw = SettingsService._load_ui_state(storage_paths)
        prefs = raw.get("preview_preferences", {})
        if not isinstance(prefs, dict):
            return False
        role_map = prefs.get(role, {})
        if not isinstance(role_map, dict):
            return False
        return bool(role_map.get(export_type, False))

    @staticmethod
    def set_preview_disabled(
        storage_paths: StoragePaths, role: str, export_type: str, disabled: bool
    ) -> None:
        raw = SettingsService._load_ui_state(storage_paths)
        prefs = raw.get("preview_preferences", {})
        if not isinstance(prefs, dict):
            prefs = {}
        role_map = prefs.get(role, {})
        if not isinstance(role_map, dict):
            role_map = {}
        role_map[export_type] = bool(disabled)
        prefs[role] = role_map
        raw["preview_preferences"] = prefs
        SettingsService._save_ui_state(storage_paths, raw)