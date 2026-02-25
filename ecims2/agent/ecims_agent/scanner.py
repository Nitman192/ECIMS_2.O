from __future__ import annotations

import getpass
import socket
from datetime import datetime, timezone
from pathlib import Path

from ecims_agent.hashing import sha256_file

SCHEMA_VERSION = "1.0"


def _host_ip_or_none() -> str | None:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return None


def scan_paths(paths: list[str], previous_snapshot: dict[str, str]) -> tuple[list[dict], dict[str, str]]:
    now = datetime.now(timezone.utc).isoformat()
    host_ip = _host_ip_or_none()
    user = getpass.getuser() or None

    events: list[dict] = []
    current_snapshot: dict[str, str] = {}

    for root in paths:
        root_path = Path(root)
        if not root_path.exists():
            continue

        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue

            resolved = str(file_path.resolve())
            stat = file_path.stat()
            file_hash = sha256_file(file_path)
            current_snapshot[resolved] = file_hash
            events.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "ts": now,
                    "event_type": "FILE_PRESENT",
                    "file_path": resolved,
                    "sha256": file_hash,
                    "file_size_bytes": int(stat.st_size),
                    "mtime_epoch": float(stat.st_mtime),
                    "user": user,
                    "process_name": None,
                    "host_ip": host_ip,
                    "details_json": {"source": "scan"},
                }
            )

    for file_path in set(previous_snapshot) - set(current_snapshot):
        events.append(
            {
                "schema_version": SCHEMA_VERSION,
                "ts": now,
                "event_type": "FILE_DELETED",
                "file_path": file_path,
                "sha256": previous_snapshot.get(file_path),
                "file_size_bytes": None,
                "mtime_epoch": None,
                "user": user,
                "process_name": None,
                "host_ip": host_ip,
                "details_json": {"source": "scan"},
            }
        )

    return events, current_snapshot
