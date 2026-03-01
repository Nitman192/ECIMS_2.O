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

from app.models.user import UserRole
from app.services.user_service import UserService


class TestPhase6AuthRBAC(unittest.TestCase):
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
            private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        )
        public_path.write_bytes(
            private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        )
        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-AUTH-001",
            "max_agents": 10,
            "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
            "ai_enabled": True,
        }
        sig = private_key.sign(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        lic = td / "license.ecims"
        lic.write_text(json.dumps({"payload": payload, "signature_b64": base64.b64encode(sig).decode("ascii")}), encoding="utf-8")
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

    def test_login_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
                self.assertEqual(login.status_code, 200, login.text)
                self.assertIn("access_token", login.json())

    def test_login_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
                self.assertEqual(login.status_code, 401, login.text)

    def test_protected_endpoint_unauthorized(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)

            with self._load_client() as client:
                resp = client.get("/api/v1/license/status")
                self.assertEqual(resp.status_code, 401, resp.text)

    def test_role_restriction_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"

            with self._load_client() as client:
                UserService.create_user("analyst1", "pass123", UserRole.ANALYST)
                headers = self._auth_header(client, "analyst1", "pass123")
                reg = client.post("/api/v1/agents/register", json={"name": "a1", "hostname": "h1"}, headers=headers)
                self.assertEqual(reg.status_code, 403, reg.text)

    def test_expired_token_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_JWT_SECRET"] = "test-secret"

            with self._load_client() as client:
                import base64
                import hashlib
                import hmac
                import json

                header = {"alg": "HS256", "typ": "JWT"}
                payload = {"sub": "1", "username": "admin", "role": "ADMIN", "iat": 1, "exp": 2}

                def _b64url(data: bytes) -> str:
                    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

                header_part = _b64url(json.dumps(header, separators=(",", ":")).encode())
                payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode())
                signing_input = f"{header_part}.{payload_part}"
                sig = hmac.new(b"test-secret", signing_input.encode("ascii"), hashlib.sha256).digest()
                expired = f"{signing_input}.{_b64url(sig)}"
                resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
                self.assertEqual(resp.status_code, 401, resp.text)


if __name__ == "__main__":
    unittest.main()
