from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.database import get_db, init_db


def _load_client(tmp_db: Path) -> TestClient:
    os.environ["ECIMS_DB_PATH"] = str(tmp_db)
    get_settings.cache_clear()
    from app import main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_db_init_creates_required_device_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        os.environ["ECIMS_DB_PATH"] = str(Path(td) / "schema.db")
        get_settings.cache_clear()
        init_db()

        with get_db() as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tables = {row[0] for row in rows}

        expected = {
            "agent_commands",
            "device_allow_tokens",
            "device_control_state",
            "agent_device_status",
            "device_unblock_requests",
        }
        assert expected.issubset(tables)


def test_request_id_echoed_and_written_to_audit_metadata() -> None:
    with tempfile.TemporaryDirectory() as td:
        with _load_client(Path(td) / "obs.db") as client:
            resp = client.get("/health", headers={"x-request-id": "req-123"})
            assert resp.status_code == 200
            assert resp.headers.get("x-request-id") == "req-123"
            assert "server_version" in resp.json()
            assert "schema_version" in resp.json()

            login = client.post(
                "/api/v1/auth/login",
                headers={"x-request-id": "req-123"},
                json={"username": "admin", "password": "admin123"},
            )
            assert login.status_code == 200

            with get_db() as conn:
                row = conn.execute(
                    "SELECT metadata_json FROM audit_log WHERE action='LOGIN_SUCCESS' ORDER BY id DESC LIMIT 1"
                ).fetchone()
            assert row is not None
            assert '"request_id": "req-123"' in row[0]


def test_health_reports_degraded_when_db_unavailable() -> None:
    with tempfile.TemporaryDirectory() as td:
        with _load_client(Path(td) / "health.db") as client:
            with mock.patch("app.main.get_db", side_effect=sqlite3.OperationalError("db down")):
                resp = client.get("/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "degraded"
            assert body["db_ok"] is False
