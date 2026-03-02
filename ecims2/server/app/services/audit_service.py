from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.utils.time import utcnow
from app.utils.request_context import REQUEST_ID


class AuditService:
    @staticmethod
    def log(
        conn,
        actor_type: str,
        action: str,
        target_type: str,
        message: str,
        *,
        actor_id: int | None = None,
        target_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log(ts, actor_type, actor_id, action, target_type, target_id, message, metadata_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utcnow().isoformat(),
                actor_type,
                actor_id,
                action,
                target_type,
                str(target_id) if target_id is not None else None,
                message,
                json.dumps({**(metadata or {}), "request_id": REQUEST_ID.get()}),
            ),
        )

    @staticmethod
    def list_logs(
        conn,
        *,
        page: int,
        page_size: int,
        start_ts: str | None,
        end_ts: str | None,
        action_type: str | None,
        outcome: str | None,
        role: str | None,
        user: str | None,
    ) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if start_ts:
            where.append("a.ts >= ?")
            params.append(start_ts)
        if end_ts:
            where.append("a.ts <= ?")
            params.append(end_ts)
        if action_type:
            where.append("a.action = ?")
            params.append(action_type)
        if user:
            where.append("u.username = ?")
            params.append(user)
        if role:
            where.append("u.role = ?")
            params.append(role)
        if outcome:
            if outcome.upper() == "SUCCESS":
                where.append("a.action NOT LIKE '%FAILED%'")
            elif outcome.upper() == "FAILED":
                where.append("a.action LIKE '%FAILED%'")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        total_row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.actor_id
            {where_sql}
            """,
            tuple(params),
        ).fetchone()
        total = int(total_row["c"] if total_row else 0)

        rows = conn.execute(
            f"""
            SELECT a.id, a.ts, a.actor_type, a.actor_id, a.action, a.target_type, a.target_id, a.message, a.metadata_json,
                   u.username AS actor_username, u.role AS actor_role
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.actor_id
            {where_sql}
            ORDER BY a.id DESC
            LIMIT ? OFFSET ?
            """,
            tuple([*params, page_size, offset]),
        ).fetchall()

        items = []
        for row in rows:
            items.append(
                {
                    "id": int(row["id"]),
                    "ts": row["ts"],
                    "actor_type": row["actor_type"],
                    "actor_id": row["actor_id"],
                    "actor_username": row["actor_username"],
                    "actor_role": row["actor_role"],
                    "action": row["action"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "message": row["message"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                }
            )

        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def export_logs(conn, rows: list[dict[str, Any]], *, redaction_profile: str = "standard", max_rows: int = 5000) -> str:
        settings = get_settings()
        root = Path(__file__).resolve().parents[3]
        export_dir = root / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        out = export_dir / f"audit_export_{utcnow().strftime('%Y%m%dT%H%M%S')}.csv"

        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "id",
                    "ts",
                    "actor_type",
                    "actor_id",
                    "actor_username",
                    "actor_role",
                    "action",
                    "target_type",
                    "target_id",
                    "message",
                    "metadata",
                ],
            )
            writer.writeheader()
            for row in rows[:max_rows]:
                safe_metadata = dict(row.get("metadata") or {})
                profiles = {"standard": ["password", "jwt", "token", "private_key", "secret"], "strict": ["password", "jwt", "token", "private_key", "secret", "username", "host_ip"]}
                for sensitive_key in profiles.get(redaction_profile, profiles["standard"]):
                    safe_metadata.pop(sensitive_key, None)
                writer.writerow({**row, "metadata": json.dumps(safe_metadata, sort_keys=True)})

        AuditService.log(
            conn,
            actor_type="ADMIN",
            action="audit.export",
            target_type="AUDIT",
            target_id=out.name,
            message="Audit export generated",
            metadata={"path": str(out.relative_to(root)), "row_count": min(len(rows), max_rows), "env": settings.environment, "redaction_profile": redaction_profile},
        )
        return str(out.relative_to(root))
