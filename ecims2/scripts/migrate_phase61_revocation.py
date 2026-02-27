from __future__ import annotations

import sqlite3
from pathlib import Path


def ensure_revocation_columns(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
        if "agent_revoked" not in cols:
            conn.execute("ALTER TABLE agents ADD COLUMN agent_revoked INTEGER NOT NULL DEFAULT 0")
        if "revoked_at" not in cols:
            conn.execute("ALTER TABLE agents ADD COLUMN revoked_at TEXT")
        if "revocation_reason" not in cols:
            conn.execute("ALTER TABLE agents ADD COLUMN revocation_reason TEXT")
        conn.commit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    db = root / "ecims2.db"
    ensure_revocation_columns(db)
    print(f"Phase 6.1 migration complete for {db}")
