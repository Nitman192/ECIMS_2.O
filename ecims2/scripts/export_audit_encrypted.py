from __future__ import annotations

import json
from pathlib import Path

from app.db.database import get_db
from app.security.storage_crypto import encrypt_bytes


def main() -> None:
    out = Path("audit_export.enc")
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY id ASC").fetchall()]
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    out.write_bytes(encrypt_bytes("audit_export", payload))
    print(f"Encrypted audit export written to {out}")


if __name__ == "__main__":
    main()
