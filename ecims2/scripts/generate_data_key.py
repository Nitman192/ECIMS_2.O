#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path


def generate_keyring(path: Path, kid: str | None = None) -> dict:
    kid = kid or datetime.now(timezone.utc).strftime("k%Y%m%d%H%M%S")
    key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    data = {
        "active_kid": kid,
        "keys": {kid: key},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main() -> None:
    output = Path(os.getenv("ECIMS_KEYRING_PATH", "configs/data_keyring.json"))
    data = generate_keyring(output)
    print(f"created keyring={output} active_kid={data['active_kid']}")


if __name__ == "__main__":
    main()
