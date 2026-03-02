from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOKENS = ROOT / ".agent_tokens.json"
EVENTQ = ROOT / ".agent_event_queue.json"


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def load_tokens() -> list[str]:
    return _read(TOKENS, [])


def save_tokens(tokens: list[str]) -> None:
    _write(TOKENS, tokens)


def load_event_queue() -> list[dict[str, Any]]:
    return _read(EVENTQ, [])


def save_event_queue(items: list[dict[str, Any]]) -> None:
    _write(EVENTQ, items)
