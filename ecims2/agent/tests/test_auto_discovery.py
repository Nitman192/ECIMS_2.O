from __future__ import annotations

import json
import socket
import threading
import unittest

from ecims_agent.config import AgentConfig
from ecims_agent.discovery import (
    DISCOVERY_REQUEST_TYPE,
    DISCOVERY_RESPONSE_TYPE,
    _candidate_from_payload,
    _discover_via_udp_broadcast,
    resolve_server_url,
)


def _build_config(**overrides) -> AgentConfig:
    payload = {
        "server_url": "http://127.0.0.1:8010",
        "agent_name": "agent-a",
        "hostname": "host-a",
        "monitored_paths": [],
        "scan_interval_sec": 30,
        "runtime_id": "agent-a",
        "state_dir": ".ecims_agent_runtime",
        "enrollment_token": None,
        "auto_discovery_enabled": False,
        "discovery_timeout_sec": 2,
        "discovery_lan_broadcast_enabled": True,
        "discovery_udp_port": 40110,
        "discovery_broadcast_targets": ["255.255.255.255"],
        "discovery_mdns_enabled": False,
        "discovery_mdns_service_type": "_ecims._tcp.local.",
        "agent_client_cert_path": None,
        "agent_client_key_path": None,
        "agent_pfx_path": None,
        "agent_pfx_password": None,
        "server_ca_bundle_path": None,
        "server_cert_pin_sha256": None,
        "pinning_required": False,
        "allow_plain_https": True,
        "device_enforcement_mode": "observe",
        "command_poll_interval_sec": 15,
        "failsafe_offline_minutes": 5,
        "token_public_key_path": "configs/device_allow_token_public.pem",
        "local_event_queue_retention_hours": 72,
        "enforcement_grace_seconds": 0,
    }
    payload.update(overrides)
    return AgentConfig(**payload)


class TestAutoDiscovery(unittest.TestCase):
    def test_resolve_server_url_uses_configured_when_discovery_disabled(self) -> None:
        config = _build_config(auto_discovery_enabled=False, server_url="http://10.10.10.10:8010")
        self.assertEqual(resolve_server_url(config), "http://10.10.10.10:8010")

    def test_candidate_from_payload_uses_sender_ip_fallback(self) -> None:
        payload = {
            "type": DISCOVERY_RESPONSE_TYPE,
            "nonce": "n1",
            "scheme": "http",
            "port": 8010,
        }
        url = _candidate_from_payload(payload, sender_ip="192.168.1.44")
        self.assertEqual(url, "http://192.168.1.44:8010")

    def test_udp_broadcast_discovery_roundtrip(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            udp_port = probe.getsockname()[1]

        stop_event = threading.Event()
        server_ready = threading.Event()

        def responder() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(("127.0.0.1", udp_port))
                sock.settimeout(0.5)
                server_ready.set()
                while not stop_event.is_set():
                    try:
                        raw, addr = sock.recvfrom(4096)
                    except socket.timeout:
                        continue
                    payload = json.loads(raw.decode("utf-8"))
                    if str(payload.get("type", "")) != DISCOVERY_REQUEST_TYPE:
                        continue
                    nonce = str(payload.get("nonce", ""))
                    response = {
                        "type": DISCOVERY_RESPONSE_TYPE,
                        "version": 1,
                        "nonce": nonce,
                        "server_url": "http://127.0.0.1:8010",
                    }
                    sock.sendto(json.dumps(response, ensure_ascii=True).encode("utf-8"), addr)
                    return

        thread = threading.Thread(target=responder, daemon=True)
        thread.start()
        self.assertTrue(server_ready.wait(timeout=1.0))
        discovered = _discover_via_udp_broadcast(
            timeout_sec=2,
            udp_port=udp_port,
            targets=["127.0.0.1"],
        )
        stop_event.set()
        thread.join(timeout=1.0)
        self.assertIn("http://127.0.0.1:8010", discovered)


if __name__ == "__main__":
    unittest.main()

