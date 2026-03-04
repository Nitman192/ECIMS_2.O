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


class TestPhase9UsersAdmin(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [
            "ECIMS_DB_PATH",
            "ECIMS_LICENSE_PATH",
            "ECIMS_LICENSE_PUBLIC_KEY_PATH",
            "ECIMS_MTLS_REQUIRED",
            "ECIMS_MTLS_ENABLED",
            "ECIMS_JWT_SECRET",
            "ECIMS_JWT_EXPIRY_MINUTES",
        ]:
            os.environ.pop(key, None)

        from app.core.config import get_settings

        get_settings.cache_clear()

    def _make_license(self, td: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path = td / "private.pem"
        public_path = td / "public.pem"
        private_path.write_bytes(
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        public_path.write_bytes(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-USERS-001",
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

    def _load_client(self):
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _auth_header(self, client: TestClient, username: str, password: str) -> dict[str, str]:
        res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        self.assertEqual(res.status_code, 200, res.text)
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    def test_admin_user_crud_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                admin_headers = self._auth_header(client, "admin", "admin123")

                created = client.post(
                    "/api/v1/admin/users",
                    headers=admin_headers,
                    json={
                        "username": "ops_admin",
                        "password": "TempPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": True,
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)
                created_user = created.json()
                user_id = int(created_user["id"])
                self.assertTrue(created_user["must_reset_password"])
                self.assertIsNone(created_user["last_login_at"])

                listed = client.get("/api/v1/admin/users", headers=admin_headers)
                self.assertEqual(listed.status_code, 200, listed.text)
                self.assertTrue(any(u["username"] == "ops_admin" for u in listed.json()))

                role_update = client.patch(
                    f"/api/v1/admin/users/{user_id}/role",
                    headers=admin_headers,
                    json={"role": "VIEWER"},
                )
                self.assertEqual(role_update.status_code, 200, role_update.text)
                self.assertEqual(role_update.json()["role"], "VIEWER")

                disable = client.patch(
                    f"/api/v1/admin/users/{user_id}/active",
                    headers=admin_headers,
                    json={"is_active": False, "reason": "Temporary disable for testing"},
                )
                self.assertEqual(disable.status_code, 200, disable.text)
                self.assertFalse(disable.json()["is_active"])

                enable = client.patch(
                    f"/api/v1/admin/users/{user_id}/active",
                    headers=admin_headers,
                    json={"is_active": True, "reason": "Re-enable"},
                )
                self.assertEqual(enable.status_code, 200, enable.text)
                self.assertTrue(enable.json()["is_active"])

                reset = client.post(
                    f"/api/v1/admin/users/{user_id}/reset-password",
                    headers=admin_headers,
                    json={
                        "new_password": "NewTempPass12345!",
                        "must_reset_password": True,
                        "reason": "Reset for operator",
                    },
                )
                self.assertEqual(reset.status_code, 200, reset.text)

                deleted = client.delete(
                    f"/api/v1/admin/users/{user_id}",
                    headers=admin_headers,
                    params={"reason": "Cleanup after test"},
                )
                self.assertEqual(deleted.status_code, 200, deleted.text)

                audit_resp = client.get(
                    "/api/v1/admin/audit?page=1&page_size=500",
                    headers=admin_headers,
                )
                self.assertEqual(audit_resp.status_code, 200, audit_resp.text)
                actions = {item["action"] for item in audit_resp.json()["items"]}

                self.assertIn("USER_CREATED", actions)
                self.assertIn("USER_ROLE_UPDATED", actions)
                self.assertIn("USER_DISABLED", actions)
                self.assertIn("USER_ENABLED", actions)
                self.assertIn("USER_PASSWORD_RESET_BY_ADMIN", actions)
                self.assertIn("USER_DELETED", actions)

    def test_non_admin_cannot_access_admin_users(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                admin_headers = self._auth_header(client, "admin", "admin123")
                created = client.post(
                    "/api/v1/admin/users",
                    headers=admin_headers,
                    json={
                        "username": "analyst2",
                        "password": "AnalystPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)

                analyst_headers = self._auth_header(client, "analyst2", "AnalystPass12345!")
                denied = client.get("/api/v1/admin/users", headers=analyst_headers)
                self.assertEqual(denied.status_code, 403, denied.text)

    def test_forced_password_reset_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                admin_headers = self._auth_header(client, "admin", "admin123")
                created = client.post(
                    "/api/v1/admin/users",
                    headers=admin_headers,
                    json={
                        "username": "admin2",
                        "password": "AdminTempPass123!",
                        "role": "ADMIN",
                        "is_active": True,
                        "must_reset_password": True,
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)

                login = client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin2", "password": "AdminTempPass123!"},
                )
                self.assertEqual(login.status_code, 200, login.text)
                self.assertTrue(login.json()["must_reset_password"])
                temp_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

                blocked = client.get("/api/v1/admin/users", headers=temp_headers)
                self.assertEqual(blocked.status_code, 403, blocked.text)
                self.assertEqual(blocked.json().get("detail"), "Password reset required")

                me = client.get("/api/v1/auth/me", headers=temp_headers)
                self.assertEqual(me.status_code, 200, me.text)
                self.assertTrue(me.json()["must_reset_password"])

                reset = client.post(
                    "/api/v1/auth/password/reset",
                    headers=temp_headers,
                    json={
                        "current_password": "AdminTempPass123!",
                        "new_password": "AdminNewPass12345!",
                    },
                )
                self.assertEqual(reset.status_code, 200, reset.text)

                relogin = client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin2", "password": "AdminNewPass12345!"},
                )
                self.assertEqual(relogin.status_code, 200, relogin.text)
                self.assertFalse(relogin.json()["must_reset_password"])
                new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}

                allowed = client.get("/api/v1/admin/users", headers=new_headers)
                self.assertEqual(allowed.status_code, 200, allowed.text)


if __name__ == "__main__":
    unittest.main()
