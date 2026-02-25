from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings


class TestPhase1Smoke(unittest.TestCase):
    def test_phase1_core_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "phase1_smoke.db"
            os.environ["ECIMS_DB_PATH"] = str(db_path)
            get_settings.cache_clear()

            from app import main as main_module

            importlib.reload(main_module)

            with TestClient(main_module.app) as client:
                register_resp = client.post(
                    "/api/v1/agents/register",
                    json={"name": "smoke-agent", "hostname": "smoke-host"},
                )
                self.assertEqual(register_resp.status_code, 200, register_resp.text)
                register_data = register_resp.json()
                agent_id = register_data["agent_id"]
                token = register_data["token"]
                headers = {"X-ECIMS-TOKEN": token}

                heartbeat_resp = client.post(
                    "/api/v1/agents/heartbeat",
                    headers=headers,
                    json={"agent_id": agent_id},
                )
                self.assertEqual(heartbeat_resp.status_code, 200, heartbeat_resp.text)

                file_path = "/tmp/smoke-file.txt"
                hash_old = "a" * 64
                hash_new = "b" * 64

                new_file_resp = client.post(
                    "/api/v1/agents/events",
                    headers=headers,
                    json={
                        "agent_id": agent_id,
                        "events": [
                            {
                                "schema_version": "1.0",
                                "ts": "2026-01-01T00:00:00Z",
                                "event_type": "FILE_PRESENT",
                                "file_path": file_path,
                                "sha256": hash_old,
                                "file_size_bytes": 100,
                                "mtime_epoch": 1735689600.0,
                                "user": "smoke",
                                "process_name": None,
                                "host_ip": None,
                                "details_json": {"source": "smoke"},
                            }
                        ],
                    },
                )
                self.assertEqual(new_file_resp.status_code, 200, new_file_resp.text)

                modified_resp = client.post(
                    "/api/v1/agents/events",
                    headers=headers,
                    json={
                        "agent_id": agent_id,
                        "events": [
                            {
                                "schema_version": "1.0",
                                "ts": "2026-01-01T00:01:00Z",
                                "event_type": "FILE_PRESENT",
                                "file_path": file_path,
                                "sha256": hash_new,
                                "file_size_bytes": 110,
                                "mtime_epoch": 1735689700.0,
                                "user": "smoke",
                                "process_name": None,
                                "host_ip": None,
                                "details_json": {"source": "smoke"},
                            }
                        ],
                    },
                )
                self.assertEqual(modified_resp.status_code, 200, modified_resp.text)

                deleted_resp = client.post(
                    "/api/v1/agents/events",
                    headers=headers,
                    json={
                        "agent_id": agent_id,
                        "events": [
                            {
                                "schema_version": "1.0",
                                "ts": "2026-01-01T00:02:00Z",
                                "event_type": "FILE_DELETED",
                                "file_path": file_path,
                                "sha256": None,
                                "file_size_bytes": None,
                                "mtime_epoch": None,
                                "user": "smoke",
                                "process_name": None,
                                "host_ip": None,
                                "details_json": {"source": "smoke"},
                            }
                        ],
                    },
                )
                self.assertEqual(deleted_resp.status_code, 200, deleted_resp.text)

                alerts_resp = client.get("/api/v1/alerts")
                self.assertEqual(alerts_resp.status_code, 200, alerts_resp.text)
                alerts = alerts_resp.json()

                new_file_alert = any(
                    a["agent_id"] == agent_id and a["alert_type"] == "NEW_FILE" and a["file_path"] == file_path
                    for a in alerts
                )
                modified_alert = any(
                    a["agent_id"] == agent_id and a["alert_type"] == "FILE_MODIFIED" and a["file_path"] == file_path
                    for a in alerts
                )
                deleted_alert = any(
                    a["agent_id"] == agent_id and a["alert_type"] == "FILE_DELETED" and a["file_path"] == file_path
                    for a in alerts
                )

                self.assertTrue(new_file_alert, "Expected NEW_FILE alert not found")
                self.assertTrue(modified_alert, "Expected FILE_MODIFIED alert not found")
                self.assertTrue(deleted_alert, "Expected FILE_DELETED alert not found")

            get_settings.cache_clear()
            os.environ.pop("ECIMS_DB_PATH", None)


if __name__ == "__main__":
    unittest.main()
