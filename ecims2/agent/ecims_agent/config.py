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


def load_config(path: str) -> AgentConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return AgentConfig(
        server_url=raw["server_url"].rstrip("/"),
        agent_name=raw["agent_name"],
        hostname=raw.get("hostname", "unknown-host"),
        monitored_paths=raw.get("monitored_paths", []),
        scan_interval_sec=int(raw.get("scan_interval_sec", 30)),
    )
