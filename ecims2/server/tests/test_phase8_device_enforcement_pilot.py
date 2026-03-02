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


class TestPhase8DeviceEnforcementPilot(unittest.TestCase):
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
            "license_id": "LIC-P8-001",
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

    def test_command_poll_ack_and_unblock_approve_wiring(self) -> None:
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
                reg = client.post("/api/v1/agents/register", json={"name": "a", "hostname": "h"}, headers=admin)
                self.assertEqual(reg.status_code, 200, reg.text)
                agent = reg.json()

                tok = client.post(
                    "/api/v1/admin/device/allow-token",
                    headers=admin,
                    json={
                        "agent_id": agent["agent_id"],
                        "duration_minutes": 30,
                        "vid": "abcd",
                        "pid": "1234",
                        "serial": "S1",
                        "justification": "offline permit",
                    },
                )
                self.assertEqual(tok.status_code, 200, tok.text)
                token_id = tok.json()["claims"]["token_id"]
                rev = client.post("/api/v1/admin/device/allow-token/revoke", headers=admin, json={"token_id": token_id})
                self.assertEqual(rev.status_code, 200, rev.text)

                ks = client.post("/api/v1/admin/device/kill-switch", headers=admin, json={"enabled": True, "reason": "emergency"})
                self.assertEqual(ks.status_code, 200, ks.text)
                mode = client.post(
                    "/api/v1/admin/device/set-agent-mode",
                    headers=admin,
                    json={"agent_id": agent["agent_id"], "mode": "enforce", "reason": "canary"},
                )
                self.assertEqual(mode.status_code, 200, mode.text)
                rollout = client.get("/api/v1/admin/device/rollout/status", headers=admin)
                self.assertEqual(rollout.status_code, 200, rollout.text)

                req = client.post(
                    "/api/v1/admin/device/unblock-request",
                    headers=admin,
                    json={
                        "agent_id": agent["agent_id"],
                        "device_id": "usb://1",
                        "vid": "abcd",
                        "pid": "1234",
                        "serial": "S1",
                        "justification": "pilot test",
                    },
                )
                self.assertEqual(req.status_code, 200, req.text)
                request_id = req.json()["request_id"]

                approved = client.post(
                    "/api/v1/admin/device/unblock-approve",
                    headers=admin,
                    json={"request_id": request_id, "approved": True, "reason": "approved for pilot"},
                )
                self.assertEqual(approved.status_code, 200, approved.text)

                h = {"X-ECIMS-TOKEN": agent["token"]}
                commands = client.get(f"/api/v1/agents/{agent['agent_id']}/commands", headers=h)
                self.assertEqual(commands.status_code, 200, commands.text)
                self.assertGreaterEqual(len(commands.json()), 1)
                cmd = next((c for c in commands.json() if c.get("type") == "DEVICE_UNBLOCK"), commands.json()[0])

                ack = client.post(
                    f"/api/v1/agents/{agent['agent_id']}/commands/{cmd['id']}/ack",
                    headers=h,
                    json={"applied": True, "error": None},
                )
                self.assertEqual(ack.status_code, 200, ack.text)

                sec = client.get("/api/v1/security/status", headers=admin)
                self.assertEqual(sec.status_code, 200)
                self.assertIn("command_backlog", sec.json())


if __name__ == "__main__":
    unittest.main()
