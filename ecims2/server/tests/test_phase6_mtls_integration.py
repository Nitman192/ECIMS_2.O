from __future__ import annotations

import base64
import importlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient


class TestPhase6MTLSIntegration(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [k for k in os.environ.keys() if k.startswith("ECIMS_")]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def _load_client(self):
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _make_license(self, td: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_path = td / "public.pem"
        public_path.write_bytes(
            private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        )
        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-MTLS-I-001",
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

    def _mk_client_cert(self, agent_id: str) -> str:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, agent_id)]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")]))
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")

    def test_valid_mismatch_and_revoked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "true"
            os.environ["ECIMS_MTLS_ENABLED"] = "true"

            with self._load_client() as client:
                login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
                token = login.json()["access_token"]
                authz = {"Authorization": f"Bearer {token}"}

                reg = client.post(
                    "/api/v1/agents/register",
                    json={"name": "agent1", "hostname": "h1"},
                    headers={**authz, "x-ecims-client-cert-b64": self._mk_client_cert("1")},
                )
                self.assertEqual(reg.status_code, 200, reg.text)
                payload = reg.json()

                good = client.post(
                    "/api/v1/agents/heartbeat",
                    json={"agent_id": payload["agent_id"]},
                    headers={"X-ECIMS-TOKEN": payload["token"], "x-ecims-client-cert-b64": self._mk_client_cert(str(payload["agent_id"]))},
                )
                self.assertEqual(good.status_code, 200)

                bad_mismatch = client.post(
                    "/api/v1/agents/heartbeat",
                    json={"agent_id": payload["agent_id"]},
                    headers={"X-ECIMS-TOKEN": payload["token"], "x-ecims-client-cert-b64": self._mk_client_cert("999")},
                )
                self.assertEqual(bad_mismatch.status_code, 403)

                revoke = client.post(f"/api/v1/admin/agents/{payload['agent_id']}/revoke", json={"reason": "rotated"}, headers=authz)
                self.assertEqual(revoke.status_code, 200)

                bad_revoked = client.post(
                    "/api/v1/agents/heartbeat",
                    json={"agent_id": payload["agent_id"]},
                    headers={"X-ECIMS-TOKEN": payload["token"], "x-ecims-client-cert-b64": self._mk_client_cert(str(payload["agent_id"]))},
                )
                self.assertEqual(bad_revoked.status_code, 403)


if __name__ == "__main__":
    unittest.main()
