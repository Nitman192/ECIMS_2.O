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


class TestPhase15OpsControlPlane(unittest.TestCase):
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
            "license_id": "LIC-P15-001",
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

    def _configure_env(self, tmp: Path) -> None:
        lic, pub = self._make_license(tmp)
        os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
        os.environ["ECIMS_LICENSE_PATH"] = str(lic)
        os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
        os.environ["ECIMS_MTLS_REQUIRED"] = "false"
        os.environ["ECIMS_MTLS_ENABLED"] = "false"

    def test_playbook_execution_two_person_flow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)
            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                agent_id = self._insert_agent("agent-1", "host-1", "tok-agent-1")

                create_admin_2 = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "admin_phase15_2",
                        "password": "AdminPass12345!",
                        "role": "ADMIN",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_admin_2.status_code, 201, create_admin_2.text)
                admin_2 = self._auth_header(client, "admin_phase15_2", "AdminPass12345!")

                create_admin_3 = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "admin_phase15_3",
                        "password": "AdminPass12345!",
                        "role": "ADMIN",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_admin_3.status_code, 201, create_admin_3.text)
                admin_3 = self._auth_header(client, "admin_phase15_3", "AdminPass12345!")

                payload = {
                    "name": "Containment Shutdown",
                    "description": "Two-person emergency shutdown playbook",
                    "trigger_type": "MANUAL",
                    "action": "shutdown",
                    "target_agent_ids": [agent_id],
                    "approval_mode": "TWO_PERSON",
                    "risk_level": "HIGH",
                    "reason_code": "EMERGENCY_MITIGATION",
                    "status": "ACTIVE",
                    "idempotency_key": "playbook-idem-001",
                    "metadata": {"source": "phase15-test"},
                }
                created = client.post("/api/v1/admin/ops/playbooks", headers=admin, json=payload)
                self.assertEqual(created.status_code, 201, created.text)
                playbook_id = created.json()["item"]["playbook_id"]

                run_resp = client.post(
                    f"/api/v1/admin/ops/playbooks/{playbook_id}/execute",
                    headers=admin,
                    json={"reason": "Containment triggered during test incident"},
                )
                self.assertEqual(run_resp.status_code, 200, run_resp.text)
                run_id = run_resp.json()["run_id"]
                self.assertEqual(run_resp.json()["status"], "PENDING_APPROVAL")

                requester_approve = client.post(
                    f"/api/v1/admin/ops/playbooks/runs/{run_id}/decision",
                    headers=admin,
                    json={"decision": "APPROVE", "reason": "Requester approval must fail"},
                )
                self.assertEqual(requester_approve.status_code, 409, requester_approve.text)

                first_approve = client.post(
                    f"/api/v1/admin/ops/playbooks/runs/{run_id}/decision",
                    headers=admin_2,
                    json={"decision": "APPROVE", "reason": "First approver accepted"},
                )
                self.assertEqual(first_approve.status_code, 200, first_approve.text)
                self.assertEqual(first_approve.json()["status"], "PARTIALLY_APPROVED")

                duplicate_approve = client.post(
                    f"/api/v1/admin/ops/playbooks/runs/{run_id}/decision",
                    headers=admin_2,
                    json={"decision": "APPROVE", "reason": "Duplicate approver should fail"},
                )
                self.assertEqual(duplicate_approve.status_code, 409, duplicate_approve.text)

                second_approve = client.post(
                    f"/api/v1/admin/ops/playbooks/runs/{run_id}/decision",
                    headers=admin_3,
                    json={"decision": "APPROVE", "reason": "Second approver accepted"},
                )
                self.assertEqual(second_approve.status_code, 200, second_approve.text)
                self.assertEqual(second_approve.json()["status"], "DISPATCHED")
                self.assertIsNotNone(second_approve.json()["task_id"])

                runs = client.get("/api/v1/admin/ops/playbooks/runs", headers=admin, params={"q": run_id})
                self.assertEqual(runs.status_code, 200, runs.text)
                self.assertGreaterEqual(int(runs.json()["total"]), 1)

    def test_change_control_break_glass_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)
            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                create_admin_2 = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "admin_phase15_cc_2",
                        "password": "AdminPass12345!",
                        "role": "ADMIN",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_admin_2.status_code, 201, create_admin_2.text)
                admin_2 = self._auth_header(client, "admin_phase15_cc_2", "AdminPass12345!")

                create_admin_3 = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "admin_phase15_cc_3",
                        "password": "AdminPass12345!",
                        "role": "ADMIN",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_admin_3.status_code, 201, create_admin_3.text)
                admin_3 = self._auth_header(client, "admin_phase15_cc_3", "AdminPass12345!")

                change_payload = {
                    "change_type": "POLICY",
                    "target_ref": "policy/device-usb",
                    "summary": "Update USB device policy to enforce stricter controls",
                    "proposed_changes": {"mode": "enforce"},
                    "risk_level": "HIGH",
                    "reason": "Emergency hardening rollout",
                    "two_person_rule": False,
                    "idempotency_key": "change-idem-001",
                    "metadata": {"ticket": "CC-100"},
                }
                created_change = client.post("/api/v1/admin/ops/change-control/requests", headers=admin, json=change_payload)
                self.assertEqual(created_change.status_code, 201, created_change.text)
                request_id = created_change.json()["item"]["request_id"]
                self.assertEqual(int(created_change.json()["item"]["approvals_required"]), 2)

                requester_decide = client.post(
                    f"/api/v1/admin/ops/change-control/requests/{request_id}/decision",
                    headers=admin,
                    json={"decision": "APPROVE", "reason": "Requester cannot approve own request"},
                )
                self.assertEqual(requester_decide.status_code, 409, requester_decide.text)

                first_decision = client.post(
                    f"/api/v1/admin/ops/change-control/requests/{request_id}/decision",
                    headers=admin_2,
                    json={"decision": "APPROVE", "reason": "First approval"},
                )
                self.assertEqual(first_decision.status_code, 200, first_decision.text)
                self.assertEqual(first_decision.json()["status"], "PARTIALLY_APPROVED")

                second_decision = client.post(
                    f"/api/v1/admin/ops/change-control/requests/{request_id}/decision",
                    headers=admin_3,
                    json={"decision": "APPROVE", "reason": "Second approval"},
                )
                self.assertEqual(second_decision.status_code, 200, second_decision.text)
                self.assertEqual(second_decision.json()["status"], "APPROVED")

                invalid_reauth = client.post(
                    "/api/v1/admin/ops/break-glass/sessions",
                    headers=admin,
                    json={
                        "current_password": "wrong-password",
                        "reason": "Emergency maintenance required",
                        "scope": "INCIDENT_RESPONSE",
                        "duration_minutes": 30,
                        "idempotency_key": "bg-idem-001",
                        "metadata": {"ticket": "IR-100"},
                    },
                )
                self.assertEqual(invalid_reauth.status_code, 401, invalid_reauth.text)

                created_session = client.post(
                    "/api/v1/admin/ops/break-glass/sessions",
                    headers=admin,
                    json={
                        "current_password": "admin123",
                        "reason": "Emergency maintenance required",
                        "scope": "INCIDENT_RESPONSE",
                        "duration_minutes": 30,
                        "idempotency_key": "bg-idem-001",
                        "metadata": {"ticket": "IR-100"},
                    },
                )
                self.assertEqual(created_session.status_code, 201, created_session.text)
                self.assertTrue(created_session.json()["created"])
                self.assertIsNotNone(created_session.json().get("break_glass_token"))
                session_id = created_session.json()["item"]["session_id"]

                session_replay = client.post(
                    "/api/v1/admin/ops/break-glass/sessions",
                    headers=admin,
                    json={
                        "current_password": "admin123",
                        "reason": "Emergency maintenance required",
                        "scope": "INCIDENT_RESPONSE",
                        "duration_minutes": 30,
                        "idempotency_key": "bg-idem-001",
                        "metadata": {"ticket": "IR-100"},
                    },
                )
                self.assertEqual(session_replay.status_code, 200, session_replay.text)
                self.assertFalse(session_replay.json()["created"])

                revoked_session = client.post(
                    f"/api/v1/admin/ops/break-glass/sessions/{session_id}/revoke",
                    headers=admin,
                    json={"reason": "Emergency completed and access closed"},
                )
                self.assertEqual(revoked_session.status_code, 200, revoked_session.text)
                self.assertEqual(revoked_session.json()["item"]["status"], "REVOKED")

                backup_created = client.post(
                    "/api/v1/admin/ops/state-backups",
                    headers=admin,
                    json={"scope": "CONFIG_ONLY", "include_sensitive": False},
                )
                self.assertEqual(backup_created.status_code, 201, backup_created.text)
                backup_id = backup_created.json()["backup_id"]
                self.assertEqual(backup_created.json()["scope"], "CONFIG_ONLY")
                self.assertIn("bundle", backup_created.json())

                users_rows = backup_created.json()["bundle"]["tables"]["users"]
                self.assertIsInstance(users_rows, list)
                if users_rows:
                    self.assertNotIn("password_hash", users_rows[0])

                fetched_backup = client.get(f"/api/v1/admin/ops/state-backups/{backup_id}", headers=admin)
                self.assertEqual(fetched_backup.status_code, 200, fetched_backup.text)
                self.assertEqual(fetched_backup.json()["backup_id"], backup_id)

                listed_backups = client.get("/api/v1/admin/ops/state-backups", headers=admin)
                self.assertEqual(listed_backups.status_code, 200, listed_backups.text)
                self.assertGreaterEqual(int(listed_backups.json()["total"]), 1)

    def test_phase15_endpoints_admin_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)
            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                create_user = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "analyst_phase15",
                        "password": "AnalystPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_user.status_code, 201, create_user.text)
                analyst = self._auth_header(client, "analyst_phase15", "AnalystPass12345!")

                denied_playbooks = client.get("/api/v1/admin/ops/playbooks", headers=analyst)
                self.assertEqual(denied_playbooks.status_code, 403, denied_playbooks.text)

                denied_change = client.get("/api/v1/admin/ops/change-control/requests", headers=analyst)
                self.assertEqual(denied_change.status_code, 403, denied_change.text)

                denied_break_glass = client.get("/api/v1/admin/ops/break-glass/sessions", headers=analyst)
                self.assertEqual(denied_break_glass.status_code, 403, denied_break_glass.text)

                denied_backup = client.get("/api/v1/admin/ops/state-backups", headers=analyst)
                self.assertEqual(denied_backup.status_code, 403, denied_backup.text)


if __name__ == "__main__":
    unittest.main()
