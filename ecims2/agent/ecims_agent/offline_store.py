from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TOKENS = ROOT / ".agent_tokens.json"
EVENTQ = ROOT / ".agent_event_queue.json"
USED_ALLOW_TOKENS = ROOT / ".agent_used_allow_tokens.json"


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def configure_store_paths(*, tokens_path: str | Path, eventq_path: str | Path, used_tokens_path: str | Path | None = None) -> None:
    global TOKENS, EVENTQ, USED_ALLOW_TOKENS
    TOKENS = Path(tokens_path)
    EVENTQ = Path(eventq_path)
    if used_tokens_path is not None:
        USED_ALLOW_TOKENS = Path(used_tokens_path)
    TOKENS.parent.mkdir(parents=True, exist_ok=True)
    EVENTQ.parent.mkdir(parents=True, exist_ok=True)
    USED_ALLOW_TOKENS.parent.mkdir(parents=True, exist_ok=True)


def load_tokens() -> list[str]:
    return _read(TOKENS, [])


def save_tokens(tokens: list[str]) -> None:
    _write(TOKENS, tokens)


def load_event_queue() -> list[dict[str, Any]]:
    return _read(EVENTQ, [])


def save_event_queue(items: list[dict[str, Any]]) -> None:
    _write(EVENTQ, items)


def load_used_allow_tokens() -> dict[str, str]:
    data = _read(USED_ALLOW_TOKENS, {})
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in data.items():
        token_id = str(key or "").strip()
        if not token_id:
            continue
        normalized[token_id] = str(value or "")
    return normalized


def save_used_allow_tokens(items: dict[str, str]) -> None:
    _write(USED_ALLOW_TOKENS, items)
