#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path


def rotate_keyring(path: Path, kid: str | None = None) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Keyring not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    keys = data.setdefault("keys", {})
    kid = kid or datetime.now(timezone.utc).strftime("k%Y%m%d%H%M%S")
    keys[kid] = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    data["active_kid"] = kid
    data["rotated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main() -> None:
    target = Path(os.getenv("ECIMS_KEYRING_PATH", "configs/data_keyring.json"))
    data = rotate_keyring(target)
    print(f"rotated keyring={target} active_kid={data['active_kid']}")


if __name__ == "__main__":
    main()
