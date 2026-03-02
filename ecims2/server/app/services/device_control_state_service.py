from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.database import get_db


class DeviceControlStateService:
    @staticmethod
    def set_kill_switch(enabled: bool) -> None:
        DeviceControlStateService._set_state("device_kill_switch", {"enabled": bool(enabled)})

    @staticmethod
    def get_kill_switch() -> bool:
        state = DeviceControlStateService._get_state("device_kill_switch")
        return bool((state or {}).get("enabled", False))

    @staticmethod
    def _set_state(key: str, value: dict[str, Any]) -> None:
        with get_db() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO device_control_state(key, value_json)
                    VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json
                    """,
                    (key, json.dumps(value)),
                )
            except sqlite3.OperationalError:
                conn.execute("CREATE TABLE IF NOT EXISTS device_control_state (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
                conn.execute(
                    """
                    INSERT INTO device_control_state(key, value_json)
                    VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json
                    """,
                    (key, json.dumps(value)),
                )

    @staticmethod
    def _get_state(key: str) -> dict[str, Any] | None:
        with get_db() as conn:
            try:
                row = conn.execute("SELECT value_json FROM device_control_state WHERE key = ?", (key,)).fetchone()
            except sqlite3.OperationalError:
                return None
            if not row:
                return None
            try:
                return json.loads(row["value_json"] or "{}")
            except Exception:
                return None
