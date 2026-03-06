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


class TestPhase17PatchUpdates(unittest.TestCase):
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
            "org_name": "Patch Test Org",
            "customer_name": "Patch Test Org",
            "license_id": "LIC-P17-001",
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

    def _admin_headers(self, client: TestClient) -> dict[str, str]:
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(login.status_code, 200, login.text)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_patch_update_upload_apply_and_download(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ["ECIMS_DB_PATH"] = str(tmp / "db.sqlite")
            os.environ["ECIMS_LICENSE_PATH"] = str(lic)
            os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
            os.environ["ECIMS_MTLS_REQUIRED"] = "false"
            os.environ["ECIMS_MTLS_ENABLED"] = "false"

            with self._load_client() as client:
                admin = self._admin_headers(client)
                upload = client.post(
                    "/api/v1/admin/ops/patch-updates/upload",
                    headers=admin,
                    data={"version": "2.0.1-hotfix1", "notes": "offline LAN hotfix"},
                    files={"bundle": ("hotfix.zip", b"dummy patch bytes", "application/zip")},
                )
                self.assertEqual(upload.status_code, 201, upload.text)
                item = upload.json()["item"]
                patch_id = item["patch_id"]
                self.assertEqual(item["status"], "UPLOADED")

                listed = client.get("/api/v1/admin/ops/patch-updates", headers=admin)
                self.assertEqual(listed.status_code, 200, listed.text)
                self.assertTrue(any(row["patch_id"] == patch_id for row in listed.json()["items"]))

                apply_resp = client.post(
                    f"/api/v1/admin/ops/patch-updates/{patch_id}/apply",
                    headers=admin,
                    json={"reason": "validated and approved", "backup_scope": "CONFIG_ONLY", "include_sensitive": False},
                )
                self.assertEqual(apply_resp.status_code, 200, apply_resp.text)
                self.assertEqual(apply_resp.json()["item"]["status"], "APPLIED")
                self.assertIn("backup", apply_resp.json())

                download = client.get(f"/api/v1/admin/ops/patch-updates/{patch_id}/download", headers=admin)
                self.assertEqual(download.status_code, 200, download.text)
                self.assertEqual(download.content, b"dummy patch bytes")


if __name__ == "__main__":
    unittest.main()
