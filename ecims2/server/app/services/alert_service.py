from __future__ import annotations

from app.db.database import get_db


class AlertService:
    @staticmethod
    def list_alerts(limit: int = 200) -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
