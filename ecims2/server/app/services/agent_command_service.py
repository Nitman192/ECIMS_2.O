from __future__ import annotations

import json
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class AgentCommandService:
    @staticmethod
    def enqueue(agent_id: int, command_type: str, payload: dict[str, Any]) -> int:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agent_commands(agent_id, type, payload_json, status, created_at, applied_at, error)
                VALUES(?, ?, ?, 'PENDING', ?, NULL, NULL)
                """,
                (agent_id, command_type, json.dumps(payload), utcnow().isoformat()),
            )
            command_id = int(cursor.lastrowid)
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="AGENT_COMMAND_ISSUED",
                target_type="AGENT_COMMAND",
                target_id=command_id,
                message="Agent command issued",
                metadata={"agent_id": agent_id, "type": command_type},
            )
            return command_id

    @staticmethod
    def list_pending(agent_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, agent_id, type, payload_json, status, created_at
                FROM agent_commands
                WHERE agent_id = ? AND status = 'PENDING'
                ORDER BY id ASC
                LIMIT ?
                """,
                (agent_id, limit),
            ).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "agent_id": int(r["agent_id"]),
                    "type": r["type"],
                    "payload": json.loads(r["payload_json"] or "{}"),
                    "status": r["status"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    @staticmethod
    def ack(agent_id: int, command_id: int, *, applied: bool, error: str | None = None) -> bool:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, status FROM agent_commands WHERE id = ? AND agent_id = ?",
                (command_id, agent_id),
            ).fetchone()
            if not row or row["status"] != "PENDING":
                return False

            status = "APPLIED" if applied else "FAILED"
            conn.execute(
                """
                UPDATE agent_commands
                SET status = ?, applied_at = ?, error = ?
                WHERE id = ?
                """,
                (status, utcnow().isoformat(), error, command_id),
            )
            AuditService.log(
                conn,
                actor_type="AGENT",
                action="AGENT_COMMAND_APPLIED" if applied else "AGENT_COMMAND_FAILED",
                target_type="AGENT_COMMAND",
                target_id=command_id,
                message="Agent command acknowledged",
                metadata={"agent_id": agent_id, "status": status, "error": error},
            )
            return True

    @staticmethod
    def backlog_counts() -> dict[str, int]:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status = 'APPLIED' THEN 1 ELSE 0 END) AS applied
                FROM agent_commands
                """
            ).fetchone()
            return {
                "pending": int(row["pending"] or 0),
                "failed": int(row["failed"] or 0),
                "applied": int(row["applied"] or 0),
            }
