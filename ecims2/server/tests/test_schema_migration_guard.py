from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.db.database import get_db, init_db


def _create_old_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            hostname TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            registered_at TEXT NOT NULL,
            last_seen TEXT,
            status TEXT NOT NULL DEFAULT 'UNKNOWN'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE agent_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE device_allow_tokens (
            token_id TEXT PRIMARY KEY,
            agent_id INTEGER NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            scope_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
        )
        """
    )
    conn.execute("CREATE TABLE device_control_state (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
    conn.execute("CREATE TABLE agent_device_status (agent_id INTEGER PRIMARY KEY, updated_at TEXT NOT NULL)")
    conn.execute("INSERT INTO agents(name, hostname, token, registered_at, status) VALUES('a1','h1','t1','2026-01-01T00:00:00+00:00','ONLINE')")
    conn.execute("INSERT INTO agent_commands(agent_id,type,payload_json,status,created_at) VALUES(1,'DEVICE_SET_MODE','{}','PENDING','2026-01-01T00:00:00+00:00')")
    conn.execute("INSERT INTO device_allow_tokens(token_id,agent_id,issued_at,expires_at,scope_json,status) VALUES('tok1',1,'2026-01-01T00:00:00+00:00','2026-01-02T00:00:00+00:00','{}','ACTIVE')")
    conn.execute("INSERT INTO device_control_state(key,value_json) VALUES('kill_switch','{\"enabled\":false}')")
    conn.execute("INSERT INTO agent_device_status(agent_id,updated_at) VALUES(1,'2026-01-01T00:00:00+00:00')")
    conn.commit()
    conn.close()


def test_schema_migration_guard_preserves_existing_data() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "upgrade.db"
        _create_old_schema(db_path)

        os.environ["ECIMS_DB_PATH"] = str(db_path)
        get_settings.cache_clear()
        migration = init_db()

        assert migration["to_version"] >= migration["from_version"]
        with get_db() as conn:
            schema_row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            assert schema_row is not None
            assert int(schema_row[0]) == migration["to_version"]
            assert conn.execute("SELECT COUNT(*) FROM agent_commands").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM device_allow_tokens").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM device_control_state").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM agent_device_status").fetchone()[0] == 1


def test_restore_db_backup_remains_consistent_after_init() -> None:
    with tempfile.TemporaryDirectory() as td:
        primary = Path(td) / "primary.db"
        backup = Path(td) / "backup.db"
        _create_old_schema(primary)
        shutil.copy2(primary, backup)

        os.environ["ECIMS_DB_PATH"] = str(backup)
        get_settings.cache_clear()
        init_db()

        with get_db() as conn:
            assert conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM agent_commands").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM device_allow_tokens").fetchone()[0] == 1
