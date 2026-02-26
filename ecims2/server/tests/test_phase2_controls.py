from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.database import get_db


class TestPhase2Controls(unittest.TestCase):
    def test_schema_version_rejected_when_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "phase2_schema.db"
            os.environ["ECIMS_DB_PATH"] = str(db_path)
            get_settings.cache_clear()

            from app import main as main_module

            importlib.reload(main_module)

            with TestClient(main_module.app) as client:
                reg = client.post(
                    "/api/v1/agents/register",
                    json={"name": "phase2-agent", "hostname": "phase2-host"},
                )
                self.assertEqual(reg.status_code, 200)
                data = reg.json()
                headers = {"X-ECIMS-TOKEN": data["token"]}

                bad = client.post(
                    "/api/v1/agents/events",
                    headers=headers,
                    json={
                        "agent_id": data["agent_id"],
                        "events": [
                            {
                                "schema_version": "2.0",
                                "ts": "2026-01-01T00:00:00Z",
                                "event_type": "FILE_PRESENT",
                                "file_path": "/tmp/bad.txt",
                                "sha256": "a" * 64,
                                "details_json": {"source": "test"},
                            }
                        ],
                    },
                )
                self.assertEqual(bad.status_code, 400, bad.text)
                self.assertIn("Unsupported schema_version", bad.text)

            get_settings.cache_clear()
            os.environ.pop("ECIMS_DB_PATH", None)

    def test_retention_endpoint_deletes_old_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "phase2_retention.db"
            os.environ["ECIMS_DB_PATH"] = str(db_path)
            get_settings.cache_clear()

            from app import main as main_module

            importlib.reload(main_module)

            with TestClient(main_module.app) as client:
                reg = client.post(
                    "/api/v1/agents/register",
                    json={"name": "phase2-agent-2", "hostname": "phase2-host-2"},
                )
                self.assertEqual(reg.status_code, 200)
                agent_id = reg.json()["agent_id"]

                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO events(agent_id, ts, event_type, file_path, sha256, details_json) VALUES(?, ?, ?, ?, ?, ?)",
                        (agent_id, "2000-01-01T00:00:00+00:00", "FILE_PRESENT", "/tmp/old", "a" * 64, json.dumps({})),
                    )
                    conn.execute(
                        "INSERT INTO alerts(agent_id, ts, alert_type, severity, file_path, previous_sha256, new_sha256, message, status) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (agent_id, "2000-01-01T00:00:00+00:00", "NEW_FILE", "AMBER", "/tmp/old", None, "a" * 64, "old", "OPEN"),
                    )
                    conn.execute(
                        "INSERT INTO audit_log(ts, actor_type, actor_id, action, target_type, target_id, message, metadata_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                        ("2000-01-01T00:00:00+00:00", "SYSTEM", None, "OLD", "SYSTEM", "old", "old", json.dumps({})),
                    )

                retention = client.post("/api/v1/admin/retention/run")
                self.assertEqual(retention.status_code, 200, retention.text)
                data = retention.json()
                self.assertGreaterEqual(data["deleted_events"], 1)
                self.assertGreaterEqual(data["deleted_alerts"], 1)
                self.assertGreaterEqual(data["deleted_audit"], 1)

            get_settings.cache_clear()
            os.environ.pop("ECIMS_DB_PATH", None)


if __name__ == "__main__":
    unittest.main()
