from __future__ import annotations

import base64
import importlib
import json
import os
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



class TestPhase6MTLS(unittest.TestCase):
    def setUp(self) -> None:
        if _DEPS_ERR is not None:
            raise unittest.SkipTest(f"phase6 test deps unavailable: {_DEPS_ERR}")

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
            "license_id": "LIC-MTLS-001",
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

    def _load_client(self):
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def tearDown(self) -> None:
        for key in ["ECIMS_DB_PATH", "ECIMS_LICENSE_PATH", "ECIMS_LICENSE_PUBLIC_KEY_PATH", "ECIMS_MTLS_REQUIRED", "ECIMS_MTLS_ENABLED"]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_strict_blocks_missing_client_cert(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "true"
            os.environ["ECIMS_MTLS_ENABLED"] = "true"

            with self._load_client() as client:
                reg = client.post("/api/v1/agents/register", json={"name": "a", "hostname": "h"})
                self.assertEqual(reg.status_code, 401)

    def test_parse_identity_from_cn(self) -> None:
        from app.security.mtls import parse_mtls_identity

        cert_b64 = self._mk_client_cert("77")
        identity = parse_mtls_identity(cert_b64)
        self.assertEqual(identity.agent_id, "77")


if __name__ == "__main__":
    unittest.main()
