from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AgentConfig:
    server_url: str
    agent_name: str
    hostname: str
    monitored_paths: list[str]
    scan_interval_sec: int
    agent_client_cert_path: str | None = None
    agent_client_key_path: str | None = None
    agent_pfx_path: str | None = None
    agent_pfx_password: str | None = None
    server_ca_bundle_path: str | None = None
    server_cert_pin_sha256: str | None = None


def load_config(path: str) -> AgentConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return AgentConfig(
        server_url=raw["server_url"].rstrip("/"),
        agent_name=raw["agent_name"],
        hostname=raw.get("hostname", "unknown-host"),
        monitored_paths=raw.get("monitored_paths", []),
        scan_interval_sec=int(raw.get("scan_interval_sec", 30)),
        agent_client_cert_path=raw.get("agent_client_cert_path"),
        agent_client_key_path=raw.get("agent_client_key_path"),
        agent_pfx_path=raw.get("agent_pfx_path"),
        agent_pfx_password=raw.get("agent_pfx_password"),
        server_ca_bundle_path=raw.get("server_ca_bundle_path"),
        server_cert_pin_sha256=raw.get("server_cert_pin_sha256"),
    )
