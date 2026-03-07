from __future__ import annotations

import base64
import importlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _b64u(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64u_decode(payload: str) -> bytes:
    pad = "=" * ((4 - len(payload) % 4) % 4)
    return base64.urlsafe_b64decode(payload + pad)


class TestPhase18ActivationFlow(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [k for k in os.environ.keys() if k.startswith("ECIMS_")]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def _make_license(self, td: Path) -> tuple[dict, Path, Path]:
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
            "org_name": "Activation Test Org",
            "customer_name": "Activation Test Org",
            "license_id": "LIC-ACT-001",
            "max_agents": 20,
            "expiry_date": (date.today() + timedelta(days=60)).isoformat(),
            "ai_enabled": True,
        }
        signature = private_key.sign(
            _canonical(payload),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return {"payload": payload, "signature_b64": base64.b64encode(signature).decode("ascii")}, private_path, public_path

    def _load_client(self) -> TestClient:
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _build_verification_id(self, *, request_code: str, private_key_path: Path) -> str:
        req = json.loads(_b64u_decode(request_code).decode("utf-8"))
        private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
        claims = {
            "token_type": "ECIMS_SERVER_ACTIVATION_V1",
            "installation_id": str(req["installation_id"]),
            "challenge": str(req["challenge"]),
            "license_id": str(req["license_id"]),
            "machine_fingerprint": str(req["machine_fingerprint"]),
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "verification_id": "VER-TEST-001",
        }
        payload_raw = _canonical(claims)
        signature = private_key.sign(
            payload_raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return f"{_b64u(payload_raw)}.{_b64u(signature)}"

    def test_activation_required_flow_unlocks_after_verification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            license_doc, private_path, public_path = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(tmp / "license.ecims")
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(public_path)
            os.environ["ECIMS_ACTIVATION_STATE_PATH"] = str(tmp / "activation_state.json")
            os.environ["ECIMS_STATE_DIR"] = str(tmp / "state")
            os.environ["ECIMS_ACTIVATION_REQUIRED"] = "true"
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"

            with self._load_client() as client:
                health = client.get("/health")
                self.assertEqual(health.status_code, 200, health.text)

                blocked = client.get("/api/v1/agents")
                self.assertEqual(blocked.status_code, 423, blocked.text)

                status_before = client.get("/api/v1/license/activation/status")
                self.assertEqual(status_before.status_code, 200, status_before.text)
                self.assertFalse(status_before.json()["is_activated"])

                imported = client.post(
                    "/api/v1/license/activation/license-key",
                    json={"license_key": json.dumps(license_doc)},
                )
                self.assertEqual(imported.status_code, 200, imported.text)
                request_code = imported.json()["request_code"]
                self.assertTrue(request_code)

                verification_id = self._build_verification_id(request_code=request_code, private_key_path=private_path)
                verified = client.post(
                    "/api/v1/license/activation/verify",
                    json={"verification_id": verification_id},
                )
                self.assertEqual(verified.status_code, 200, verified.text)
                self.assertTrue(verified.json()["license_state"]["is_valid"])

                login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
                self.assertEqual(login.status_code, 200, login.text)


if __name__ == "__main__":
    unittest.main()
