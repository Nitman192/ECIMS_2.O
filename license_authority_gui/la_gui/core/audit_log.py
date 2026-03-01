"""Append-only tamper-evident audit logging with hash chaining."""

from __future__ import annotations

import getpass
import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from la_gui.core.canonical_json import canonicalize_json
from la_gui.core.crypto_service import CryptoService


@dataclass(slots=True)
class AuditEntry:
    """Single audit event entry stored in JSONL."""

    timestamp: str
    actor: str
    action: str
    details: dict[str, Any]
    prev_hash: str
    entry_hash: str


class AuditLogger:
    """Manages append-only audit entries with chained hashes."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, action: str, details: dict[str, Any], actor: str | None = None) -> AuditEntry:
        """Append a new audit entry and compute chained hash."""
        timestamp = datetime.now(timezone.utc).isoformat()
        resolved_actor = actor or getpass.getuser()
        prev_hash = self._get_last_hash()

        entry_core = {
            "timestamp": timestamp,
            "actor": resolved_actor,
            "action": action,
            "details": details,
            "prev_hash": prev_hash,
        }
        entry_hash = CryptoService.sha256_hex(canonicalize_json(entry_core))
        entry = AuditEntry(**entry_core, entry_hash=entry_hash)

        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")

        return entry

    def read_entries(self) -> list[AuditEntry]:
        """Read all audit entries from disk."""
        if not self.log_path.exists():
            return []

        entries: list[AuditEntry] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw = json.loads(line)
                entries.append(AuditEntry(**raw))
        return entries

    def verify_chain(self) -> tuple[bool, str]:
        """Verify prev_hash linkage and entry_hash values across the full log."""
        prev_hash = "GENESIS"
        for index, entry in enumerate(self.read_entries()):
            if entry.prev_hash != prev_hash:
                return False, f"Broken prev_hash at line {index + 1}"

            core = {
                "timestamp": entry.timestamp,
                "actor": entry.actor,
                "action": entry.action,
                "details": entry.details,
                "prev_hash": entry.prev_hash,
            }
            expected_hash = CryptoService.sha256_hex(canonicalize_json(core))
            if expected_hash != entry.entry_hash:
                return False, f"Invalid entry_hash at line {index + 1}"

            prev_hash = entry.entry_hash

        return True, "ok"

    def _get_last_hash(self) -> str:
        entries = self.read_entries()
        if not entries:
            return "GENESIS"
        return entries[-1].entry_hash
