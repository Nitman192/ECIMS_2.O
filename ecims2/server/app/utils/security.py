from __future__ import annotations

import secrets


def generate_agent_token() -> str:
    return secrets.token_hex(32)
