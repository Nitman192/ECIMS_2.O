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

from app.licensing_core.fingerprint import compute_machine_fingerprint


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class TestPhase4License(unittest.TestCase):
    def _make_keys(self, tmp_dir: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_path = tmp_dir / "private_key.pem"
        public_path = tmp_dir / "public_key.pem"
        private_path.write_bytes(private_bytes)
        public_path.write_bytes(public_bytes)
        return private_path, public_path

    def _write_license(self, private_key_path: Path, license_path: Path, *, ai_enabled: bool, expiry_date: str,
                       machine_fingerprint: str | None = None, scheme: str = "pss") -> None:
        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-TST-001",
            "max_agents": 5,
            "expiry_date": expiry_date,
            "ai_enabled": ai_enabled,
        }
        if machine_fingerprint:
            payload["machine_fingerprint"] = machine_fingerprint

        private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
        if scheme == "pss":
            pad = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
        else:
            pad = padding.PKCS1v15()
        signature = private_key.sign(_canonical_payload_bytes(payload), pad, hashes.SHA256())

        license_obj = {"payload": payload, "signature_b64": base64.b64encode(signature).decode("ascii")}
        license_path.write_text(json.dumps(license_obj), encoding="utf-8")

    def _load_client(self):
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _set_env(self, **kwargs: str) -> None:
        for k, v in kwargs.items():
            os.environ[k] = v

    def _clear_env(self) -> None:
        for k in [
            "ECIMS_DB_PATH",
            "ECIMS_LICENSE_PATH",
            "ECIMS_LICENSE_PUBLIC_KEY_PATH",
            "ECIMS_AI_ARTIFACT_DIR",
        ]:
            os.environ.pop(k, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def test_no_license_blocks_registration_and_ai(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _, public_key = self._make_keys(tmp)
            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db1.sqlite"),
                ECIMS_LICENSE_PATH=str(tmp / "missing.ecims"),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
            )
            with self._load_client() as client:
                self.assertEqual(client.post("/api/v1/agents/register", json={"name": "a1", "hostname": "h1"}).status_code, 403)
                self.assertEqual(client.get("/api/v1/ai/models").status_code, 403)
            self._clear_env()

    def test_pss_license_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            private_key, public_key = self._make_keys(tmp)
            license_path = tmp / "valid_pss.ecims"
            self._write_license(private_key, license_path, ai_enabled=True, expiry_date=(date.today() + timedelta(days=30)).isoformat(), scheme="pss")

            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db2.sqlite"),
                ECIMS_LICENSE_PATH=str(license_path),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
                ECIMS_AI_ARTIFACT_DIR=str(tmp / "artifacts2"),
            )
            with self._load_client() as client:
                self.assertEqual(client.post("/api/v1/agents/register", json={"name": "a2", "hostname": "h2"}).status_code, 200)
                self.assertEqual(client.get("/api/v1/ai/models").status_code, 200)
            self._clear_env()

    def test_pkcs1v15_license_still_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            private_key, public_key = self._make_keys(tmp)
            license_path = tmp / "valid_pkcs.ecims"
            self._write_license(private_key, license_path, ai_enabled=True, expiry_date=(date.today() + timedelta(days=30)).isoformat(), scheme="pkcs1v15")
            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db3.sqlite"),
                ECIMS_LICENSE_PATH=str(license_path),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
            )
            with self._load_client() as client:
                self.assertEqual(client.post("/api/v1/agents/register", json={"name": "a3", "hostname": "h3"}).status_code, 200)
            self._clear_env()

    def test_machine_binding_match_and_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            private_key, public_key = self._make_keys(tmp)
            local_fp = compute_machine_fingerprint()

            match_license = tmp / "match.ecims"
            self._write_license(private_key, match_license, ai_enabled=True, expiry_date=(date.today() + timedelta(days=30)).isoformat(), machine_fingerprint=local_fp)
            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db4.sqlite"),
                ECIMS_LICENSE_PATH=str(match_license),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
            )
            with self._load_client() as client:
                st = client.get("/api/v1/license/status").json()
                self.assertTrue(st["is_valid"])
                self.assertTrue(st["machine_match"])
            self._clear_env()

            mismatch_license = tmp / "mismatch.ecims"
            self._write_license(private_key, mismatch_license, ai_enabled=True, expiry_date=(date.today() + timedelta(days=30)).isoformat(), machine_fingerprint="0" * 64)
            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db5.sqlite"),
                ECIMS_LICENSE_PATH=str(mismatch_license),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
            )
            with self._load_client() as client:
                st = client.get("/api/v1/license/status").json()
                self.assertFalse(st["is_valid"])
                self.assertEqual(st["reason"], "MACHINE_MISMATCH")
                self.assertEqual(client.post("/api/v1/agents/register", json={"name": "a5", "hostname": "h5"}).status_code, 403)
            self._clear_env()

    def test_expired_license_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            private_key, public_key = self._make_keys(tmp)
            license_path = tmp / "expired.ecims"
            self._write_license(private_key, license_path, ai_enabled=True, expiry_date=(date.today() - timedelta(days=1)).isoformat())
            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db6.sqlite"),
                ECIMS_LICENSE_PATH=str(license_path),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
            )
            with self._load_client() as client:
                self.assertEqual(client.post("/api/v1/agents/register", json={"name": "a6", "hostname": "h6"}).status_code, 403)
                self.assertEqual(client.get("/api/v1/license/status").json()["reason"], "EXPIRED")
            self._clear_env()

    def test_rollback_tamper_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            private_key, public_key = self._make_keys(tmp)
            license_path = tmp / "valid.ecims"
            self._write_license(private_key, license_path, ai_enabled=True, expiry_date=(date.today() + timedelta(days=30)).isoformat())

            # first startup writes last_run
            self._set_env(
                ECIMS_DB_PATH=str(tmp / "db7.sqlite"),
                ECIMS_LICENSE_PATH=str(license_path),
                ECIMS_LICENSE_PUBLIC_KEY_PATH=str(public_key),
            )
            with self._load_client() as client:
                self.assertTrue(client.get("/api/v1/license/status").json()["is_valid"])

            # tamper with future timestamp signed correctly to simulate rollback scenario.
            state_dir = Path(__file__).resolve().parents[3] / "server" / ".ecims_state"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / "last_run.json"
            future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            import hashlib, hmac

            key = hashlib.sha256(public_key.read_bytes()).digest()
            sig = hmac.new(key, future.encode("utf-8"), hashlib.sha256).hexdigest()
            state_file.write_text(json.dumps({"last_seen_utc": future, "hmac_hex": sig}), encoding="utf-8")

            with self._load_client() as client:
                st = client.get("/api/v1/license/status").json()
                self.assertFalse(st["is_valid"])
                self.assertEqual(st["reason"], "TAMPER_DETECTED")
                self.assertEqual(client.post("/api/v1/agents/register", json={"name": "a7", "hostname": "h7"}).status_code, 403)

            self._clear_env()


if __name__ == "__main__":
    unittest.main()
