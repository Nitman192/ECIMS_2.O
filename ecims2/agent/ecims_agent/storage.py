from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path(".ecims_agent_state.json")


def set_state_file(path: str | Path) -> None:
    global STATE_FILE
    STATE_FILE = Path(path)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
