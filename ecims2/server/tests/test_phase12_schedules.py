from __future__ import annotations

import base64
import importlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.utils.time import utcnow


class TestPhase12Schedules(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [k for k in os.environ.keys() if k.startswith("ECIMS_")]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def _make_license(self, td: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_path = td / "public.pem"
        public_path.write_bytes(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-P12-001",
            "max_agents": 100,
            "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
            "ai_enabled": True,
        }
        sig = private_key.sign(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        lic = td / "license.ecims"
        lic.write_text(
            json.dumps({"payload": payload, "signature_b64": base64.b64encode(sig).decode("ascii")}),
            encoding="utf-8",
        )
        return lic, public_path

    def _load_client(self) -> TestClient:
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _auth_header(self, client: TestClient, username: str, password: str) -> dict[str, str]:
        login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        self.assertEqual(login.status_code, 200, login.text)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _insert_agent(self, name: str, hostname: str, token: str) -> int:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agents(name, hostname, token, registered_at, last_seen, status, agent_revoked, revoked_at, revocation_reason)
                VALUES(?, ?, ?, ?, ?, 'ONLINE', 0, NULL, NULL)
                """,
                (name, hostname, token, utcnow().isoformat(), utcnow().isoformat()),
            )
            return int(cursor.lastrowid)

    def test_schedule_create_preview_conflict_and_runner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                a1 = self._insert_agent("a1", "h1", "tok-a1")
                a2 = self._insert_agent("a2", "h2", "tok-a2")

                create_payload = {
                    "window_name": "Nightly Patch Window",
                    "timezone": "UTC",
                    "start_time_local": "01:00",
                    "duration_minutes": 120,
                    "recurrence": "DAILY",
                    "weekly_days": [],
                    "target_agent_ids": [a1, a2],
                    "orchestration_mode": "SAFE_SHUTDOWN_START",
                    "status": "ACTIVE",
                    "reason_code": "MAINTENANCE",
                    "reason": "Routine patching and reboot",
                    "allow_conflicts": False,
                    "idempotency_key": "sched-idem-001",
                    "metadata": {"source": "tests"},
                }
                created = client.post("/api/v1/admin/ops/schedules", headers=admin, json=create_payload)
                self.assertEqual(created.status_code, 201, created.text)
                self.assertTrue(created.json()["created"])
                schedule_id = int(created.json()["item"]["id"])
                self.assertEqual(created.json()["item"]["status"], "ACTIVE")

                replay = client.post("/api/v1/admin/ops/schedules", headers=admin, json=create_payload)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertFalse(replay.json()["created"])
                self.assertEqual(int(replay.json()["item"]["id"]), schedule_id)

                preview = client.post(
                    "/api/v1/admin/ops/schedules/preview",
                    headers=admin,
                    json={
                        "window_name": "Overlap Window",
                        "timezone": "UTC",
                        "start_time_local": "01:30",
                        "duration_minutes": 90,
                        "recurrence": "DAILY",
                        "weekly_days": [],
                        "target_agent_ids": [a1],
                        "orchestration_mode": "RESTART_ONLY",
                        "metadata": {},
                    },
                )
                self.assertEqual(preview.status_code, 200, preview.text)
                self.assertGreaterEqual(int(preview.json()["conflict_count"]), 1)

                conflict_create = client.post(
                    "/api/v1/admin/ops/schedules",
                    headers=admin,
                    json={
                        "window_name": "Overlap Window",
                        "timezone": "UTC",
                        "start_time_local": "01:30",
                        "duration_minutes": 90,
                        "recurrence": "DAILY",
                        "weekly_days": [],
                        "target_agent_ids": [a1],
                        "orchestration_mode": "RESTART_ONLY",
                        "status": "ACTIVE",
                        "reason_code": "MAINTENANCE",
                        "reason": "Conflicting test schedule",
                        "allow_conflicts": False,
                        "idempotency_key": "sched-idem-002",
                    },
                )
                self.assertEqual(conflict_create.status_code, 409, conflict_create.text)

                with get_db() as conn:
                    conn.execute(
                        "UPDATE maintenance_schedules SET next_run_at = ? WHERE id = ?",
                        ((utcnow() - timedelta(minutes=5)).isoformat(), schedule_id),
                    )

                run_due = client.post("/api/v1/admin/ops/schedules/run-due", headers=admin)
                self.assertEqual(run_due.status_code, 200, run_due.text)
                self.assertGreaterEqual(int(run_due.json()["due_count"]), 1)
                self.assertGreaterEqual(int(run_due.json()["tasks_dispatched"]), 1)

                listed = client.get("/api/v1/admin/ops/schedules", headers=admin, params={"q": str(schedule_id)})
                self.assertEqual(listed.status_code, 200, listed.text)
                row = listed.json()["items"][0]
                self.assertIsNotNone(row["last_run_at"])
                self.assertIsNotNone(row["next_run_at"])

                conflicts = client.get(f"/api/v1/admin/ops/schedules/{schedule_id}/conflicts", headers=admin)
                self.assertEqual(conflicts.status_code, 200, conflicts.text)
                self.assertIn("total", conflicts.json())

    def test_schedule_state_update_and_admin_guard(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                a1 = self._insert_agent("a1", "h1", "tok-a1")

                create_user = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "analyst_sched",
                        "password": "AnalystPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_user.status_code, 201, create_user.text)
                analyst = self._auth_header(client, "analyst_sched", "AnalystPass12345!")
                denied = client.get("/api/v1/admin/ops/schedules", headers=analyst)
                self.assertEqual(denied.status_code, 403, denied.text)

                created = client.post(
                    "/api/v1/admin/ops/schedules",
                    headers=admin,
                    json={
                        "window_name": "Draft Window",
                        "timezone": "UTC",
                        "start_time_local": "03:00",
                        "duration_minutes": 60,
                        "recurrence": "WEEKLY",
                        "weekly_days": [0, 2, 4],
                        "target_agent_ids": [a1],
                        "orchestration_mode": "RESTART_ONLY",
                        "status": "DRAFT",
                        "reason_code": "TESTING",
                        "reason": "Draft schedule for state transitions",
                        "allow_conflicts": True,
                        "idempotency_key": "sched-idem-003",
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)
                schedule_id = int(created.json()["item"]["id"])
                self.assertEqual(created.json()["item"]["status"], "DRAFT")

                activate = client.post(
                    f"/api/v1/admin/ops/schedules/{schedule_id}/state",
                    headers=admin,
                    json={"status": "ACTIVE", "reason": "Activate schedule"},
                )
                self.assertEqual(activate.status_code, 200, activate.text)
                self.assertEqual(activate.json()["status"], "ACTIVE")
                self.assertIsNotNone(activate.json()["next_run_at"])

                pause = client.post(
                    f"/api/v1/admin/ops/schedules/{schedule_id}/state",
                    headers=admin,
                    json={"status": "PAUSED", "reason": "Pause schedule"},
                )
                self.assertEqual(pause.status_code, 200, pause.text)
                self.assertEqual(pause.json()["status"], "PAUSED")


if __name__ == "__main__":
    unittest.main()
