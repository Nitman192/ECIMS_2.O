from __future__ import annotations

import base64
import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID
    from fastapi.testclient import TestClient
except Exception as _dep_exc:  # noqa: BLE001
    _DEPS_ERR = _dep_exc
else:
    _DEPS_ERR = None


class TestPhase61Revocation(unittest.TestCase):
    def setUp(self) -> None:
        if _DEPS_ERR is not None:
            raise unittest.SkipTest(f"phase6.1 deps unavailable: {_DEPS_ERR}")

    def tearDown(self) -> None:
        for key in [
            "ECIMS_DB_PATH",
            "ECIMS_LICENSE_PATH",
            "ECIMS_LICENSE_PUBLIC_KEY_PATH",
            "ECIMS_MTLS_REQUIRED",
            "ECIMS_MTLS_ENABLED",
            "ECIMS_ADMIN_API_TOKEN",
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
            "license_id": "LIC-REV-001",
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

    def _mk_client_cert_b64(self, agent_id: str) -> str:
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

    def _load_client(self):
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def test_revoke_blocks_and_restore_allows_with_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            db_path = tmp / "db.sqlite"
            lic, pub = self._make_license(tmp)

            os.environ["ECIMS_DB_PATH"] = str(db_path)
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "true"
            os.environ["ECIMS_MTLS_ENABLED"] = "true"
            os.environ["ECIMS_ADMIN_API_TOKEN"] = "admin-secret"

            with self._load_client() as client:
                reg_headers = {"X-ECIMS-CLIENT-CERT-B64": self._mk_client_cert_b64("bootstrap")}
                register = client.post("/api/v1/agents/register", json={"name": "r1", "hostname": "h1"}, headers=reg_headers)
                self.assertEqual(register.status_code, 200, register.text)
                data = register.json()
                agent_id = data["agent_id"]
                token = data["token"]

                live_headers = {
                    "X-ECIMS-TOKEN": token,
                    "X-ECIMS-CLIENT-CERT-B64": self._mk_client_cert_b64(str(agent_id)),
                }
                ok_hb = client.post("/api/v1/agents/heartbeat", json={"agent_id": agent_id}, headers=live_headers)
                self.assertEqual(ok_hb.status_code, 200, ok_hb.text)

                revoke = client.post(
                    f"/api/v1/admin/agents/{agent_id}/revoke",
                    json={"reason": "compromised endpoint"},
                    headers={"X-ECIMS-ADMIN-TOKEN": "admin-secret"},
                )
                self.assertEqual(revoke.status_code, 200, revoke.text)

                blocked_hb = client.post("/api/v1/agents/heartbeat", json={"agent_id": agent_id}, headers=live_headers)
                self.assertEqual(blocked_hb.status_code, 403, blocked_hb.text)
                self.assertIn("revoked", blocked_hb.text.lower())

                agents = client.get("/api/v1/agents")
                self.assertEqual(agents.status_code, 200)
                self.assertTrue(any(a["id"] == agent_id and a["agent_revoked"] for a in agents.json()))

                restore = client.post(
                    f"/api/v1/admin/agents/{agent_id}/restore",
                    headers={"X-ECIMS-ADMIN-TOKEN": "admin-secret"},
                )
                self.assertEqual(restore.status_code, 200, restore.text)

                ok_after_restore = client.post("/api/v1/agents/heartbeat", json={"agent_id": agent_id}, headers=live_headers)
                self.assertEqual(ok_after_restore.status_code, 200, ok_after_restore.text)

            with sqlite3.connect(db_path) as conn:
                actions = [r[0] for r in conn.execute("SELECT action FROM audit_log ORDER BY id ASC").fetchall()]
                self.assertIn("AGENT_REVOKED", actions)
                self.assertIn("AGENT_UNREVOKED", actions)
                self.assertIn("MTLS_AGENT_REVOKED", actions)


if __name__ == "__main__":
    unittest.main()
