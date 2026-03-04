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


class TestPhase10FeatureFlags(unittest.TestCase):
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
            "license_id": "LIC-P10-001",
            "max_agents": 20,
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
            json.dumps(
                {
                    "payload": payload,
                    "signature_b64": base64.b64encode(sig).decode("ascii"),
                }
            ),
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

    def test_admin_feature_flags_scope_risk_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")

                listed = client.get("/api/v1/admin/features", headers=admin)
                self.assertEqual(listed.status_code, 200, listed.text)
                items = listed.json()["items"]
                self.assertTrue(any(item["key"] == "device_kill_switch" for item in items))

                created = client.post(
                    "/api/v1/admin/features",
                    headers=admin,
                    json={
                        "key": "threat_hunt_assist",
                        "description": "Enable guided threat hunting helper flows",
                        "scope": "GLOBAL",
                        "scope_target": None,
                        "is_enabled": False,
                        "risk_level": "LOW",
                        "reason_code": "POLICY_CHANGE",
                        "reason": "Create feature flag for rollout",
                        "confirm_risky": False,
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)
                created_flag = created.json()
                self.assertFalse(created_flag["enabled"])

                toggle_on = client.put(
                    f"/api/v1/admin/features/{created_flag['id']}/state",
                    headers=admin,
                    json={
                        "enabled": True,
                        "reason_code": "TESTING",
                        "reason": "Enable for controlled test rollout",
                        "confirm_risky": False,
                    },
                )
                self.assertEqual(toggle_on.status_code, 200, toggle_on.text)
                self.assertTrue(toggle_on.json()["enabled"])

                toggle_noop = client.put(
                    f"/api/v1/admin/features/{created_flag['id']}/state",
                    headers=admin,
                    json={
                        "enabled": True,
                        "reason_code": "TESTING",
                        "reason": "Repeat same state to verify idempotency",
                        "confirm_risky": False,
                    },
                )
                self.assertEqual(toggle_noop.status_code, 200, toggle_noop.text)
                self.assertTrue(toggle_noop.json()["enabled"])

                risky_created = client.post(
                    "/api/v1/admin/features",
                    headers=admin,
                    json={
                        "key": "remote_lockdown_mode",
                        "description": "Agent level containment mode override",
                        "scope": "AGENT",
                        "scope_target": "42",
                        "is_enabled": False,
                        "risk_level": "HIGH",
                        "reason_code": "SECURITY_INCIDENT",
                        "reason": "Prepare high-risk emergency control",
                        "confirm_risky": False,
                    },
                )
                self.assertEqual(risky_created.status_code, 201, risky_created.text)
                risky_flag = risky_created.json()

                risky_denied = client.put(
                    f"/api/v1/admin/features/{risky_flag['id']}/state",
                    headers=admin,
                    json={
                        "enabled": True,
                        "reason_code": "EMERGENCY_MITIGATION",
                        "reason": "Enable immediate mitigation",
                        "confirm_risky": False,
                    },
                )
                self.assertEqual(risky_denied.status_code, 400, risky_denied.text)
                self.assertIn("Risky toggle requires explicit confirmation", risky_denied.text)

                risky_allowed = client.put(
                    f"/api/v1/admin/features/{risky_flag['id']}/state",
                    headers=admin,
                    json={
                        "enabled": True,
                        "reason_code": "EMERGENCY_MITIGATION",
                        "reason": "Enable immediate mitigation",
                        "confirm_risky": True,
                    },
                )
                self.assertEqual(risky_allowed.status_code, 200, risky_allowed.text)
                self.assertTrue(risky_allowed.json()["enabled"])

                audit = client.get("/api/v1/admin/audit?page=1&page_size=500", headers=admin)
                self.assertEqual(audit.status_code, 200, audit.text)
                actions = {item["action"] for item in audit.json()["items"]}
                self.assertIn("FEATURE_FLAG_CREATED", actions)
                self.assertIn("FEATURE_FLAG_ENABLED", actions)
                self.assertIn("FEATURE_FLAG_STATE_NOOP", actions)

    def test_feature_flags_admin_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                created = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "analyst_flags",
                        "password": "AnalystPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)

                analyst = self._auth_header(client, "analyst_flags", "AnalystPass12345!")
                denied = client.get("/api/v1/admin/features", headers=analyst)
                self.assertEqual(denied.status_code, 403, denied.text)

    def test_legacy_kill_switch_syncs_feature_flag_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")

                enable = client.post(
                    "/api/v1/admin/device/kill-switch",
                    headers=admin,
                    json={"enabled": True, "reason": "Recovery drill enable"},
                )
                self.assertEqual(enable.status_code, 200, enable.text)

                listed = client.get(
                    "/api/v1/admin/features",
                    headers=admin,
                    params={"q": "device_kill_switch"},
                )
                self.assertEqual(listed.status_code, 200, listed.text)
                rows = listed.json()["items"]
                self.assertEqual(len(rows), 1)
                self.assertTrue(rows[0]["is_kill_switch"])
                self.assertTrue(rows[0]["enabled"])

                disable = client.put(
                    f"/api/v1/admin/features/{rows[0]['id']}/state",
                    headers=admin,
                    json={
                        "enabled": False,
                        "reason_code": "ROLLBACK",
                        "reason": "Disable after recovery drill",
                        "confirm_risky": True,
                    },
                )
                self.assertEqual(disable.status_code, 200, disable.text)
                self.assertFalse(disable.json()["enabled"])

                rollout = client.get("/api/v1/admin/device/rollout/status", headers=admin)
                self.assertEqual(rollout.status_code, 200, rollout.text)
                self.assertFalse(rollout.json()["kill_switch"])


if __name__ == "__main__":
    unittest.main()
