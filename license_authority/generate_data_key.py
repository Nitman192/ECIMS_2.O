from __future__ import annotations

import argparse
import base64
import json
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ECIMS data encryption keyring")
    parser.add_argument("--out", default="data_keyring.json")
    parser.add_argument("--key-id", default="key-001")
    args = parser.parse_args()

    key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    body = {"active_key_id": args.key_id, "keys": {args.key_id: key}}
    Path(args.out).write_text(json.dumps(body, indent=2), encoding="utf-8")
    print(f"Wrote keyring to {args.out}")


if __name__ == "__main__":
    main()
