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

from app.models.user import UserRole
from app.services.user_service import UserService


class TestPhase7HardeningOperability(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [k for k in os.environ.keys() if k.startswith("ECIMS_")]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def _make_license(self, td: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_path = td / "public.pem"
        public_path.write_bytes(
            private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        )
        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-P7-001",
            "max_agents": 50,
            "expiry_date": (date.today() + timedelta(days=90)).isoformat(),
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

    def _admin_headers(self, client: TestClient) -> dict[str, str]:
        res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200, res.text)
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    def test_prod_fails_on_weak_jwt_secret(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_ENVIRONMENT"] = "prod"
            os.environ["ECIMS_JWT_SECRET"] = "change-me-in-production"
            with self.assertRaises(RuntimeError):
                with self._load_client() as client:
                    client.get("/health")

    def test_prod_requires_explicit_bootstrap_admin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_ENVIRONMENT"] = "prod"
            os.environ["ECIMS_JWT_SECRET"] = "this-is-a-secure-jwt-secret-for-prod"
            with self.assertRaises(RuntimeError):
                with self._load_client() as client:
                    client.get("/health")

    def test_security_status_policy_source_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"
            with self._load_client() as client:
                headers = self._admin_headers(client)
                resp = client.get("/api/v1/security/status", headers=headers)
                self.assertEqual(resp.status_code, 200, resp.text)
                body = resp.json()
                self.assertIn(body["source"], {"signed", "default"})
                self.assertIsInstance(body["reason"], str)

    def test_rate_limit_login_and_agent_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"
            os.environ["ECIMS_LOGIN_RATE_LIMIT_COUNT"] = "1"
            os.environ["ECIMS_LOGIN_RATE_LIMIT_WINDOW_SEC"] = "60"
            os.environ["ECIMS_AGENT_RATE_LIMIT_COUNT"] = "1"
            os.environ["ECIMS_AGENT_RATE_LIMIT_WINDOW_SEC"] = "60"

            with self._load_client() as client:
                first = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
                self.assertEqual(first.status_code, 200, first.text)
                second = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
                self.assertEqual(second.status_code, 429, second.text)

                headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
                reg = client.post("/api/v1/agents/register", json={"name": "a1", "hostname": "h1"}, headers=headers)
                self.assertEqual(reg.status_code, 200, reg.text)
                a = reg.json()

                first_evt = client.post(
                    "/api/v1/agents/events",
                    headers={"X-ECIMS-TOKEN": a["token"]},
                    json={"agent_id": a["agent_id"], "events": [{"schema_version":"1.0","ts":"2026-01-01T00:00:00Z","event_type":"FILE_PRESENT","file_path":"/tmp/x","sha256":"a"*64,"file_size_bytes":1,"mtime_epoch":1.0,"user":"u","process_name":None,"host_ip":None,"details_json":{}}]},
                )
                self.assertEqual(first_evt.status_code, 200, first_evt.text)
                second_evt = client.post(
                    "/api/v1/agents/events",
                    headers={"X-ECIMS-TOKEN": a["token"]},
                    json={"agent_id": a["agent_id"], "events": [{"schema_version":"1.0","ts":"2026-01-01T00:00:00Z","event_type":"FILE_PRESENT","file_path":"/tmp/x","sha256":"a"*64,"file_size_bytes":1,"mtime_epoch":1.0,"user":"u","process_name":None,"host_ip":None,"details_json":{}}]},
                )
                self.assertEqual(second_evt.status_code, 429, second_evt.text)

    def test_mtls_integration_allow_mismatch_revoke(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "true"
            os.environ["ECIMS_MTLS_ENABLED"] = "true"

            with self._load_client() as client:
                headers = self._admin_headers(client)
                reg = client.post(
                    "/api/v1/agents/register",
                    json={"name": "agent1", "hostname": "host1"},
                    headers={**headers, "x-ecims-client-cert-b64": "not-a-cert"},
                )
                self.assertEqual(reg.status_code, 401)

                # use cert that matches known id for heartbeat path checks
                reg2 = client.post(
                    "/api/v1/agents/register",
                    json={"name": "agent2", "hostname": "host2"},
                    headers={**headers, "x-ecims-client-cert-b64": self._mk_client_cert("2")},
                )
                self.assertEqual(reg2.status_code, 200, reg2.text)
                data = reg2.json()

                mismatch = client.post(
                    "/api/v1/agents/heartbeat",
                    json={"agent_id": data["agent_id"]},
                    headers={"X-ECIMS-TOKEN": data["token"], "x-ecims-client-cert-b64": self._mk_client_cert("999")},
                )
                self.assertEqual(mismatch.status_code, 403)

                revoke = client.post(f"/api/v1/admin/agents/{data['agent_id']}/revoke", json={"reason": "test"}, headers=headers)
                self.assertEqual(revoke.status_code, 200, revoke.text)
                revoked = client.post(
                    "/api/v1/agents/heartbeat",
                    json={"agent_id": data["agent_id"]},
                    headers={"X-ECIMS-TOKEN": data["token"], "x-ecims-client-cert-b64": self._mk_client_cert(str(data['agent_id']))},
                )
                self.assertEqual(revoked.status_code, 403)

    def test_audit_list_export_rbac_and_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"
            with self._load_client() as client:
                admin_headers = self._admin_headers(client)
                UserService.create_user("analyst1", "analyst-pass-123", UserRole.ANALYST)
                analyst_login = client.post("/api/v1/auth/login", json={"username": "analyst1", "password": "analyst-pass-123"})
                analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['access_token']}"}

                forbidden = client.get("/api/v1/admin/audit", headers=analyst_headers)
                self.assertEqual(forbidden.status_code, 403)

                listed = client.get("/api/v1/admin/audit?page=1&page_size=2", headers=admin_headers)
                self.assertEqual(listed.status_code, 200, listed.text)
                payload = listed.json()
                self.assertEqual(payload["page"], 1)
                self.assertLessEqual(len(payload["items"]), 2)

                exported = client.post("/api/v1/admin/audit/export", headers=admin_headers, json={})
                self.assertEqual(exported.status_code, 200, exported.text)
                self.assertEqual(exported.json()["status"], "ok")

                listed2 = client.get("/api/v1/admin/audit?action_type=audit.export", headers=admin_headers)
                self.assertEqual(listed2.status_code, 200)
                self.assertGreaterEqual(listed2.json()["total"], 1)

    def test_policy_artifacts_present(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.assertTrue((root / "configs" / "security.policy.json").exists())
        self.assertTrue((root / "configs" / "security.policy.sig").exists())
        self.assertTrue((root / "configs" / "security.policy.public.pem").exists())


if __name__ == "__main__":
    unittest.main()
