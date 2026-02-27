from __future__ import annotations

import argparse
import base64
import json
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate ECIMS data encryption keyring")
    parser.add_argument("--keyring", required=True)
    parser.add_argument("--new-key-id", required=True)
    args = parser.parse_args()

    path = Path(args.keyring)
    body = json.loads(path.read_text(encoding="utf-8"))
    keys = body.get("keys", {})
    if not isinstance(keys, dict):
        raise ValueError("Invalid keyring: keys must be object")

    keys[args.new_key_id] = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    body["active_key_id"] = args.new_key_id
    body["keys"] = keys
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    print(f"Rotated keyring. Active key is now {args.new_key_id}")


if __name__ == "__main__":
    main()
