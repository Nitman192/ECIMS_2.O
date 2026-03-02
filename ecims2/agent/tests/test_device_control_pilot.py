from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ecims_agent.device_adapter import USBDevice
from ecims_agent.device_control import DeviceControlManager
from ecims_agent.offline_store import EVENTQ, TOKENS, save_tokens


class _Client:
    def __init__(self, online: bool = True):
        self.events = []
        self.acks = []
        self.commands = []
        self.online = online

    def post_events(self, agent_id, token, events):
        if not self.online:
            raise RuntimeError("offline")
        self.events.extend(events)
        return {"processed": len(events), "alerts_created": 0}

    def get_commands(self, agent_id, token):
        return list(self.commands)

    def ack_command(self, agent_id, token, command_id, *, applied, error=None):
        self.acks.append((command_id, applied, error))


class _Adapter:
    def __init__(self):
        self.block_calls = 0

    def detect_mass_storage(self):
        return []

    def block_device(self, device):
        self.block_calls += 1
        return True

    def unblock_device(self, device, duration_minutes=None):
        return True


class TestDeviceControlPilot(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.old_tok = TOKENS.exists()
        self.old_ev = EVENTQ.exists()
        if TOKENS.exists():
            TOKENS.unlink()
        if EVENTQ.exists():
            EVENTQ.unlink()

        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pub = Path(self.td.name) / "pub.pem"
        self.pub.write_bytes(priv.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        claims = {
            "token_id": "t1",
            "agent_id": 1,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "scope": {"vid": "abcd", "pid": "1234"},
            "reason": "test",
            "policy_version": "OK",
        }
        payload = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
        sig = priv.sign(payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
        import base64
        self.token = f"{base64.urlsafe_b64encode(payload).rstrip(b'=').decode()}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"

    def tearDown(self) -> None:
        self.td.cleanup()
        if TOKENS.exists():
            TOKENS.unlink()
        if EVENTQ.exists():
            EVENTQ.unlink()

    def _mgr(self, mode="observe"):
        return DeviceControlManager(
            enforcement_mode=mode,
            failsafe_offline_minutes=10,
            token_public_key_path=str(self.pub),
            local_event_queue_retention_hours=72,
        )

    def test_offline_enforce_blocks(self):
        mgr = self._mgr("enforce")
        client = _Client(online=False)
        adapter = _Adapter()
        device = USBDevice(device_id="usb://x", vid="aaaa", pid="bbbb")
        mgr.maybe_block_device(client, 1, "t", adapter, device)
        self.assertEqual(adapter.block_calls, 1)

    def test_valid_token_allows_then_expiry_blocks(self):
        save_tokens([self.token])
        mgr = self._mgr("enforce")
        client = _Client()
        adapter = _Adapter()
        device = USBDevice(device_id="usb://1", vid="abcd", pid="1234")
        mgr.maybe_block_device(client, 1, "t", adapter, device)
        self.assertEqual(adapter.block_calls, 0)

        # expired token
        save_tokens([])
        mgr.maybe_block_device(client, 1, "t", adapter, USBDevice(device_id="usb://2", vid="aaaa", pid="bbbb"))
        self.assertEqual(adapter.block_calls, 1)

    def test_token_scope_mismatch_blocks(self):
        save_tokens([self.token])
        mgr = self._mgr("enforce")
        adapter = _Adapter()
        mgr.maybe_block_device(_Client(), 1, "t", adapter, USBDevice(device_id="usb://3", vid="ffff", pid="eeee"))
        self.assertEqual(adapter.block_calls, 1)

    def test_event_queue_flush(self):
        mgr = self._mgr("observe")
        offline = _Client(online=False)
        online = _Client(online=True)
        adapter = _Adapter()
        mgr.maybe_block_device(offline, 1, "t", adapter, USBDevice(device_id="usb://4", vid="a", pid="b"))
        self.assertTrue(EVENTQ.exists())
        mgr.flush_event_queue(online, 1, "t")
        self.assertGreaterEqual(len(online.events), 1)

    def test_deleted_token_store_reverts_to_block(self):
        save_tokens([self.token])
        mgr = self._mgr("enforce")
        adapter = _Adapter()
        device = USBDevice(device_id="usb://del", vid="abcd", pid="1234")
        mgr.maybe_block_device(_Client(), 1, "t", adapter, device)
        self.assertEqual(adapter.block_calls, 0)
        if TOKENS.exists():
            TOKENS.unlink()
        mgr.maybe_block_device(_Client(), 1, "t", adapter, device)
        self.assertEqual(adapter.block_calls, 1)

    def test_force_observe_command_obeyed(self):
        mgr = self._mgr("enforce")
        c = _Client()
        c.commands = [{"id": 1, "type": "DEVICE_FORCE_OBSERVE", "payload": {}}]
        mgr.process_commands(c, 1, "t", _Adapter(), {})
        self.assertEqual(mgr.enforcement_mode, "observe")


if __name__ == "__main__":
    unittest.main()
