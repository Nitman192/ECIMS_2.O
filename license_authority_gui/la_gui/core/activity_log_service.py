"""Safe append-only activity log service for UI events."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Any


_SENSITIVE_TOKENS = {"key", "passphrase", "secret", "private", "material", "pem", "signature"}


@dataclass(slots=True)
class ActivityEntry:
    timestamp: str
    actor_role: str
    mode: str
    action_type: str
    outcome: str
    safe_metadata: dict[str, Any]


class ActivityLogService:
    """Append/query/filter/export activity entries with safe metadata enforcement."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        actor_role: str,
        mode: str,
        action_type: str,
        outcome: str,
        safe_metadata: dict[str, Any] | None = None,
    ) -> ActivityEntry:
        entry = ActivityEntry(
            timestamp=datetime.utcnow().isoformat(),
            actor_role=actor_role,
            mode=mode,
            action_type=action_type,
            outcome=outcome,
            safe_metadata=self._sanitize_metadata(safe_metadata or {}),
        )
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def read_entries(self) -> list[ActivityEntry]:
        if not self.log_path.exists():
            return []
        entries: list[ActivityEntry] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw = json.loads(line)
                entries.append(ActivityEntry(**raw))
        return entries

    def query(
        self,
        *,
        search: str = "",
        role: str = "All",
        outcome: str = "All",
        action_type: str = "All",
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ActivityEntry]:
        items = self.read_entries()
        text = search.strip().lower()
        results: list[ActivityEntry] = []
        for item in items:
            item_date = datetime.fromisoformat(item.timestamp).date()
            if role != "All" and item.actor_role != role:
                continue
            if outcome != "All" and item.outcome != outcome:
                continue
            if action_type != "All" and item.action_type != action_type:
                continue
            if date_from and item_date < date_from:
                continue
            if date_to and item_date > date_to:
                continue
            if text:
                hay = json.dumps(asdict(item), sort_keys=True).lower()
                if text not in hay:
                    continue
            results.append(item)
        return results

    def export(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.log_path.read_text(encoding="utf-8") if self.log_path.exists() else "", encoding="utf-8")
        return destination

    def known_action_types(self) -> list[str]:
        return sorted({entry.action_type for entry in self.read_entries()})

    def _sanitize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in metadata.items():
            lowered = key.lower()
            if any(token in lowered for token in _SENSITIVE_TOKENS):
                continue
            safe_value = self._sanitize_value(value)
            if safe_value is None:
                continue
            safe[key] = safe_value
        return safe

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, str):
            if any(token in value.lower() for token in _SENSITIVE_TOKENS):
                return None
            return value[:256]
        if isinstance(value, list):
            out = []
            for item in value[:25]:
                sv = self._sanitize_value(item)
                if sv is not None:
                    out.append(sv)
            return out
        if isinstance(value, dict):
            nested: dict[str, Any] = {}
            for k, v in value.items():
                lk = str(k).lower()
                if any(token in lk for token in _SENSITIVE_TOKENS):
                    continue
                sv = self._sanitize_value(v)
                if sv is not None:
                    nested[str(k)] = sv
            return nested
        return str(value)[:256]
