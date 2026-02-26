from __future__ import annotations

import json
from typing import Any

from app.utils.time import utcnow


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
                json.dumps(metadata or {}),
            ),
        )
