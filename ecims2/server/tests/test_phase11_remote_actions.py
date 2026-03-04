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


class TestPhase11RemoteActions(unittest.TestCase):
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
            "license_id": "LIC-P11-001",
            "max_agents": 50,
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

    def _insert_agent(self, *, name: str, hostname: str, token: str) -> int:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agents(name, hostname, token, registered_at, last_seen, status, agent_revoked, revoked_at, revocation_reason)
                VALUES(?, ?, ?, ?, ?, 'ONLINE', 0, NULL, NULL)
                """,
                (name, hostname, token, utcnow().isoformat(), utcnow().isoformat()),
            )
            return int(cursor.lastrowid)

    def test_remote_action_task_lifecycle_and_idempotency(self) -> None:
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
                agent_1 = self._insert_agent(name="a1", hostname="h1", token="tok-a1")
                agent_2 = self._insert_agent(name="a2", hostname="h2", token="tok-a2")

                payload = {
                    "action": "restart",
                    "agent_ids": [agent_1, agent_2],
                    "idempotency_key": "idem-remote-001",
                    "reason_code": "MAINTENANCE",
                    "reason": "Planned restart for patch validation",
                    "confirm_high_risk": False,
                    "metadata": {"scope": "test"},
                }
                created = client.post("/api/v1/admin/ops/remote-actions/tasks", headers=admin, json=payload)
                self.assertEqual(created.status_code, 201, created.text)
                self.assertTrue(created.json()["created"])
                task = created.json()["item"]
                task_id = int(task["id"])
                self.assertEqual(task["status"], "SENT")
                self.assertEqual(int(task["target_count"]), 2)

                replay = client.post("/api/v1/admin/ops/remote-actions/tasks", headers=admin, json=payload)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertFalse(replay.json()["created"])
                self.assertEqual(int(replay.json()["item"]["id"]), task_id)

                conflict_payload = dict(payload)
                conflict_payload["reason"] = "Different reason must conflict"
                conflict = client.post("/api/v1/admin/ops/remote-actions/tasks", headers=admin, json=conflict_payload)
                self.assertEqual(conflict.status_code, 409, conflict.text)

                c1 = client.get(f"/api/v1/agents/{agent_1}/commands", headers={"X-ECIMS-TOKEN": "tok-a1"})
                c2 = client.get(f"/api/v1/agents/{agent_2}/commands", headers={"X-ECIMS-TOKEN": "tok-a2"})
                self.assertEqual(c1.status_code, 200, c1.text)
                self.assertEqual(c2.status_code, 200, c2.text)
                self.assertGreaterEqual(len(c1.json()), 1)
                self.assertGreaterEqual(len(c2.json()), 1)
                command_1 = int(c1.json()[0]["id"])
                command_2 = int(c2.json()[0]["id"])

                ack_1 = client.post(
                    f"/api/v1/agents/{agent_1}/commands/{command_1}/ack",
                    headers={"X-ECIMS-TOKEN": "tok-a1"},
                    json={"applied": True, "error": None},
                )
                self.assertEqual(ack_1.status_code, 200, ack_1.text)

                listed_ack = client.get(
                    "/api/v1/admin/ops/remote-actions/tasks",
                    headers=admin,
                    params={"q": str(task_id)},
                )
                self.assertEqual(listed_ack.status_code, 200, listed_ack.text)
                ack_task = listed_ack.json()["items"][0]
                self.assertEqual(ack_task["status"], "ACK")
                self.assertEqual(int(ack_task["done_count"]), 1)

                ack_2 = client.post(
                    f"/api/v1/agents/{agent_2}/commands/{command_2}/ack",
                    headers={"X-ECIMS-TOKEN": "tok-a2"},
                    json={"applied": True, "error": None},
                )
                self.assertEqual(ack_2.status_code, 200, ack_2.text)

                listed_done = client.get(
                    "/api/v1/admin/ops/remote-actions/tasks",
                    headers=admin,
                    params={"q": str(task_id)},
                )
                self.assertEqual(listed_done.status_code, 200, listed_done.text)
                done_task = listed_done.json()["items"][0]
                self.assertEqual(done_task["status"], "DONE")
                self.assertEqual(int(done_task["done_count"]), 2)

                targets = client.get(f"/api/v1/admin/ops/remote-actions/tasks/{task_id}/targets", headers=admin)
                self.assertEqual(targets.status_code, 200, targets.text)
                self.assertEqual(int(targets.json()["total"]), 2)

    def test_remote_action_validations(self) -> None:
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
                agent_1 = self._insert_agent(name="a1", hostname="h1", token="tok-a1")

                high_risk_without_confirm = client.post(
                    "/api/v1/admin/ops/remote-actions/tasks",
                    headers=admin,
                    json={
                        "action": "shutdown",
                        "agent_ids": [agent_1],
                        "idempotency_key": "idem-high-risk-001",
                        "reason_code": "EMERGENCY_MITIGATION",
                        "reason": "Emergency host shutdown required",
                        "confirm_high_risk": False,
                    },
                )
                self.assertEqual(high_risk_without_confirm.status_code, 400, high_risk_without_confirm.text)

                high_risk_confirmed = client.post(
                    "/api/v1/admin/ops/remote-actions/tasks",
                    headers=admin,
                    json={
                        "action": "shutdown",
                        "agent_ids": [agent_1],
                        "idempotency_key": "idem-high-risk-002",
                        "reason_code": "EMERGENCY_MITIGATION",
                        "reason": "Emergency host shutdown required",
                        "confirm_high_risk": True,
                    },
                )
                self.assertEqual(high_risk_confirmed.status_code, 201, high_risk_confirmed.text)

                large_batch = client.post(
                    "/api/v1/admin/ops/remote-actions/tasks",
                    headers=admin,
                    json={
                        "action": "restart",
                        "agent_ids": [agent_1 for _ in range(101)],
                        "idempotency_key": "idem-batch-001",
                        "reason_code": "MAINTENANCE",
                        "reason": "Batch restart test",
                        "confirm_high_risk": False,
                    },
                )
                self.assertEqual(large_batch.status_code, 422, large_batch.text)

    def test_remote_action_admin_only_access(self) -> None:
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
                create_user = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "analyst_remote",
                        "password": "AnalystPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_user.status_code, 201, create_user.text)

                analyst = self._auth_header(client, "analyst_remote", "AnalystPass12345!")
                denied = client.get("/api/v1/admin/ops/remote-actions/tasks", headers=analyst)
                self.assertEqual(denied.status_code, 403, denied.text)


if __name__ == "__main__":
    unittest.main()
