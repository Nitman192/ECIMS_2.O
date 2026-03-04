from __future__ import annotations

import hashlib
import json
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class RemoteActionTaskService:
    ACTION_COMMAND_MAP: dict[str, str] = {
        "shutdown": "REMOTE_SHUTDOWN",
        "restart": "REMOTE_RESTART",
        "lockdown": "REMOTE_LOCKDOWN",
        "policy_push": "REMOTE_POLICY_PUSH",
    }
    VALID_STATUSES = {"PENDING", "SENT", "ACK", "DONE", "FAILED"}
    HIGH_RISK_ACTIONS = {"shutdown", "lockdown"}
    VALID_REASON_CODES = {
        "SECURITY_INCIDENT",
        "EMERGENCY_MITIGATION",
        "POLICY_CHANGE",
        "ROLLBACK",
        "MAINTENANCE",
        "COMPLIANCE",
        "TESTING",
        "POLICY_SYNC",
        "INCIDENT_RESPONSE",
    }
    MAX_BATCH_SIZE = 100
    MAX_METADATA_BYTES = 4096

    @staticmethod
    def create_task(
        *,
        action: str,
        agent_ids: list[int],
        idempotency_key: str,
        reason_code: str,
        reason: str,
        confirm_high_risk: bool,
        metadata: dict[str, Any] | None,
        actor_id: int,
    ) -> tuple[dict[str, Any], bool]:
        normalized_action = action.strip().lower()
        if normalized_action not in RemoteActionTaskService.ACTION_COMMAND_MAP:
            raise ValueError("INVALID_ACTION")
        if len(agent_ids) > RemoteActionTaskService.MAX_BATCH_SIZE:
            raise ValueError("BATCH_TOO_LARGE")

        normalized_reason_code = reason_code.strip().upper()
        if normalized_reason_code not in RemoteActionTaskService.VALID_REASON_CODES:
            raise ValueError("INVALID_REASON_CODE")
        if normalized_action in RemoteActionTaskService.HIGH_RISK_ACTIONS and not bool(confirm_high_risk):
            raise ValueError("HIGH_RISK_CONFIRMATION_REQUIRED")

        deduped_agent_ids = sorted({int(agent_id) for agent_id in agent_ids if int(agent_id) > 0})
        if not deduped_agent_ids:
            raise ValueError("INVALID_AGENT_IDS")

        normalized_idempotency_key = idempotency_key.strip()
        if not normalized_idempotency_key:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        metadata_json = json.dumps(metadata or {}, sort_keys=True)
        if len(metadata_json.encode("utf-8")) > RemoteActionTaskService.MAX_METADATA_BYTES:
            raise ValueError("METADATA_TOO_LARGE")

        request_hash = RemoteActionTaskService._build_request_hash(
            action=normalized_action,
            agent_ids=deduped_agent_ids,
            reason_code=normalized_reason_code,
            reason=reason.strip(),
            metadata_json=metadata_json,
        )
        now_iso = utcnow().isoformat()
        command_type = RemoteActionTaskService.ACTION_COMMAND_MAP[normalized_action]

        with get_db() as conn:
            existing = conn.execute(
                """
                SELECT id, request_hash
                FROM agent_tasks
                WHERE idempotency_key = ?
                """,
                (normalized_idempotency_key,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                task = RemoteActionTaskService._get_task_by_id_with_conn(conn, int(existing["id"]))
                if not task:
                    raise ValueError("TASK_NOT_FOUND")
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="REMOTE_ACTION_TASK_IDEMPOTENT_REPLAY",
                    target_type="AGENT_TASK",
                    target_id=task["id"],
                    message="Idempotent replay returned existing task",
                    metadata={"idempotency_key": normalized_idempotency_key},
                )
                return task, False

            existing_agents = conn.execute(
                f"""
                SELECT id, agent_revoked
                FROM agents
                WHERE id IN ({','.join('?' for _ in deduped_agent_ids)})
                """,
                tuple(deduped_agent_ids),
            ).fetchall()
            found_ids = {int(row["id"]) for row in existing_agents}
            missing_ids = sorted(set(deduped_agent_ids) - found_ids)
            if missing_ids:
                raise ValueError(f"MISSING_AGENTS:{','.join(str(item) for item in missing_ids)}")
            revoked_ids = sorted(int(row["id"]) for row in existing_agents if bool(row["agent_revoked"]))
            if revoked_ids:
                raise ValueError(f"REVOKED_AGENTS:{','.join(str(item) for item in revoked_ids)}")

            task_cursor = conn.execute(
                """
                INSERT INTO agent_tasks(
                    idempotency_key, request_hash, action, reason_code, reason, requested_by_user_id,
                    status, target_count, sent_count, ack_count, done_count, failed_count,
                    created_at, updated_at, sent_at, completed_at, metadata_json
                )
                VALUES(?, ?, ?, ?, ?, ?, 'PENDING', ?, 0, 0, 0, 0, ?, ?, NULL, NULL, ?)
                """,
                (
                    normalized_idempotency_key,
                    request_hash,
                    normalized_action,
                    normalized_reason_code,
                    reason.strip(),
                    actor_id,
                    len(deduped_agent_ids),
                    now_iso,
                    now_iso,
                    metadata_json,
                ),
            )
            task_id = int(task_cursor.lastrowid)

            for agent_id in deduped_agent_ids:
                target_cursor = conn.execute(
                    """
                    INSERT INTO agent_task_targets(
                        task_id, agent_id, command_id, status, ack_applied, error,
                        created_at, updated_at, sent_at, ack_at, completed_at
                    )
                    VALUES(?, ?, NULL, 'PENDING', NULL, NULL, ?, ?, NULL, NULL, NULL)
                    """,
                    (task_id, agent_id, now_iso, now_iso),
                )
                target_id = int(target_cursor.lastrowid)
                command_payload = {
                    "task_id": task_id,
                    "action": normalized_action,
                    "reason_code": normalized_reason_code,
                    "reason": reason.strip(),
                    "metadata": metadata or {},
                }
                command_cursor = conn.execute(
                    """
                    INSERT INTO agent_commands(agent_id, type, payload_json, status, created_at, applied_at, error)
                    VALUES(?, ?, ?, 'PENDING', ?, NULL, NULL)
                    """,
                    (agent_id, command_type, json.dumps(command_payload), now_iso),
                )
                command_id = int(command_cursor.lastrowid)
                conn.execute(
                    """
                    UPDATE agent_task_targets
                    SET command_id = ?, status = 'SENT', sent_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (command_id, now_iso, now_iso, target_id),
                )
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="AGENT_COMMAND_ISSUED",
                    target_type="AGENT_COMMAND",
                    target_id=command_id,
                    message="Agent command issued from remote action task",
                    metadata={"task_id": task_id, "agent_id": agent_id, "type": command_type},
                )

            conn.execute(
                """
                UPDATE agent_tasks
                SET status = 'SENT',
                    sent_count = target_count,
                    updated_at = ?,
                    sent_at = ?
                WHERE id = ?
                """,
                (now_iso, now_iso, task_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="REMOTE_ACTION_TASK_CREATED",
                target_type="AGENT_TASK",
                target_id=task_id,
                message="Remote action task created",
                metadata={
                    "action": normalized_action,
                    "target_count": len(deduped_agent_ids),
                    "idempotency_key": normalized_idempotency_key,
                    "reason_code": normalized_reason_code,
                },
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="REMOTE_ACTION_TASK_DISPATCHED",
                target_type="AGENT_TASK",
                target_id=task_id,
                message="Remote action task dispatched",
                metadata={"command_type": command_type, "sent_count": len(deduped_agent_ids)},
            )
            task = RemoteActionTaskService._get_task_by_id_with_conn(conn, task_id)
            if not task:
                raise ValueError("TASK_NOT_FOUND")
            return task, True

    @staticmethod
    def list_tasks(
        *,
        page: int,
        page_size: int,
        action: str | None,
        status: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if action and action.strip().lower() != "all":
            normalized_action = action.strip().lower()
            if normalized_action not in RemoteActionTaskService.ACTION_COMMAND_MAP:
                raise ValueError("INVALID_ACTION")
            where.append("t.action = ?")
            params.append(normalized_action)

        if status and status.strip().upper() != "ALL":
            normalized_status = status.strip().upper()
            if normalized_status not in RemoteActionTaskService.VALID_STATUSES:
                raise ValueError("INVALID_STATUS")
            where.append("t.status = ?")
            params.append(normalized_status)

        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            if query.strip().isdigit():
                where.append(
                    "(lower(t.idempotency_key) LIKE ? OR lower(t.action) LIKE ? OR lower(t.reason) LIKE ? OR t.id = ?)"
                )
                params.extend([term, term, term, int(query.strip())])
            else:
                where.append("(lower(t.idempotency_key) LIKE ? OR lower(t.action) LIKE ? OR lower(t.reason) LIKE ?)")
                params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        with get_db() as conn:
            total_row = conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM agent_tasks t
                {where_sql}
                """,
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT
                    t.id,
                    t.idempotency_key,
                    t.action,
                    t.reason_code,
                    t.reason,
                    t.requested_by_user_id,
                    t.status,
                    t.target_count,
                    t.sent_count,
                    t.ack_count,
                    t.done_count,
                    t.failed_count,
                    t.created_at,
                    t.updated_at,
                    t.sent_at,
                    t.completed_at,
                    t.metadata_json,
                    u.username AS requested_by_username
                FROM agent_tasks t
                LEFT JOIN users u ON u.id = t.requested_by_user_id
                {where_sql}
                ORDER BY t.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [RemoteActionTaskService._row_to_task(row) for row in rows]
            return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def list_task_targets(task_id: int) -> list[dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.task_id,
                    t.agent_id,
                    a.name AS agent_name,
                    a.hostname AS agent_hostname,
                    t.command_id,
                    t.status,
                    t.ack_applied,
                    t.error,
                    t.created_at,
                    t.updated_at,
                    t.sent_at,
                    t.ack_at,
                    t.completed_at
                FROM agent_task_targets t
                LEFT JOIN agents a ON a.id = t.agent_id
                WHERE t.task_id = ?
                ORDER BY t.id ASC
                """,
                (task_id,),
            ).fetchall()
        return [RemoteActionTaskService._row_to_target(row) for row in rows]

    @staticmethod
    def get_task(task_id: int) -> dict[str, Any] | None:
        with get_db() as conn:
            return RemoteActionTaskService._get_task_by_id_with_conn(conn, task_id)

    @staticmethod
    def sync_after_command_ack(command_id: int, *, applied: bool, error: str | None) -> None:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            target = conn.execute(
                """
                SELECT id, task_id, status
                FROM agent_task_targets
                WHERE command_id = ?
                """,
                (command_id,),
            ).fetchone()
            if not target:
                return

            current_status = str(target["status"])
            if current_status in {"DONE", "FAILED"}:
                return

            new_status = "DONE" if applied else "FAILED"
            conn.execute(
                """
                UPDATE agent_task_targets
                SET status = ?, ack_applied = ?, error = ?, ack_at = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    1 if applied else 0,
                    error,
                    now_iso,
                    now_iso,
                    now_iso,
                    int(target["id"]),
                ),
            )
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="REMOTE_ACTION_TARGET_ACK",
                target_type="AGENT_TASK_TARGET",
                target_id=int(target["id"]),
                message="Remote action target acknowledged",
                metadata={"command_id": command_id, "applied": bool(applied), "error": error},
            )
            RemoteActionTaskService._refresh_task_status_with_conn(conn, int(target["task_id"]), now_iso=now_iso)

    @staticmethod
    def _refresh_task_status_with_conn(conn, task_id: int, *, now_iso: str) -> None:
        previous = conn.execute("SELECT status, completed_at FROM agent_tasks WHERE id = ?", (task_id,)).fetchone()
        if not previous:
            return
        counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) AS sent_count,
                SUM(CASE WHEN status IN ('DONE', 'FAILED') THEN 1 ELSE 0 END) AS ack_count,
                SUM(CASE WHEN status = 'DONE' THEN 1 ELSE 0 END) AS done_count,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_count
            FROM agent_task_targets
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        target_count = int(counts["total_count"] or 0)
        sent_count = int(counts["sent_count"] or 0)
        ack_count = int(counts["ack_count"] or 0)
        done_count = int(counts["done_count"] or 0)
        failed_count = int(counts["failed_count"] or 0)

        if failed_count > 0:
            next_status = "FAILED"
        elif target_count > 0 and done_count == target_count:
            next_status = "DONE"
        elif ack_count > 0:
            next_status = "ACK"
        elif sent_count > 0:
            next_status = "SENT"
        else:
            next_status = "PENDING"

        completed_at = now_iso if next_status in {"DONE", "FAILED"} else None
        conn.execute(
            """
            UPDATE agent_tasks
            SET status = ?,
                target_count = ?,
                sent_count = ?,
                ack_count = ?,
                done_count = ?,
                failed_count = ?,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                target_count,
                sent_count,
                ack_count,
                done_count,
                failed_count,
                now_iso,
                completed_at if completed_at else previous["completed_at"],
                task_id,
            ),
        )

        prev_status = str(previous["status"])
        if prev_status != next_status:
            event_action = {
                "SENT": "REMOTE_ACTION_TASK_SENT",
                "ACK": "REMOTE_ACTION_TASK_ACKED",
                "DONE": "REMOTE_ACTION_TASK_DONE",
                "FAILED": "REMOTE_ACTION_TASK_FAILED",
                "PENDING": "REMOTE_ACTION_TASK_PENDING",
            }[next_status]
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action=event_action,
                target_type="AGENT_TASK",
                target_id=task_id,
                message="Remote action task status changed",
                metadata={
                    "previous_status": prev_status,
                    "new_status": next_status,
                    "target_count": target_count,
                    "done_count": done_count,
                    "failed_count": failed_count,
                },
            )

    @staticmethod
    def _get_task_by_id_with_conn(conn, task_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                t.id,
                t.idempotency_key,
                t.action,
                t.reason_code,
                t.reason,
                t.requested_by_user_id,
                t.status,
                t.target_count,
                t.sent_count,
                t.ack_count,
                t.done_count,
                t.failed_count,
                t.created_at,
                t.updated_at,
                t.sent_at,
                t.completed_at,
                t.metadata_json,
                u.username AS requested_by_username
            FROM agent_tasks t
            LEFT JOIN users u ON u.id = t.requested_by_user_id
            WHERE t.id = ?
            """,
            (task_id,),
        ).fetchone()
        if not row:
            return None
        return RemoteActionTaskService._row_to_task(row)

    @staticmethod
    def _build_request_hash(
        *,
        action: str,
        agent_ids: list[int],
        reason_code: str,
        reason: str,
        metadata_json: str,
    ) -> str:
        payload = {
            "action": action,
            "agent_ids": agent_ids,
            "reason_code": reason_code,
            "reason": reason,
            "metadata_json": metadata_json,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_task(row) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        return {
            "id": int(row["id"]),
            "idempotency_key": str(row["idempotency_key"]),
            "action": str(row["action"]),
            "reason_code": str(row["reason_code"]),
            "reason": str(row["reason"]),
            "requested_by_user_id": int(row["requested_by_user_id"]),
            "requested_by_username": row["requested_by_username"],
            "status": str(row["status"]),
            "target_count": int(row["target_count"] or 0),
            "sent_count": int(row["sent_count"] or 0),
            "ack_count": int(row["ack_count"] or 0),
            "done_count": int(row["done_count"] or 0),
            "failed_count": int(row["failed_count"] or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "sent_at": row["sent_at"],
            "completed_at": row["completed_at"],
            "metadata": metadata,
        }

    @staticmethod
    def _row_to_target(row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "task_id": int(row["task_id"]),
            "agent_id": int(row["agent_id"]),
            "agent_name": row["agent_name"],
            "agent_hostname": row["agent_hostname"],
            "command_id": int(row["command_id"]) if row["command_id"] is not None else None,
            "status": str(row["status"]),
            "ack_applied": bool(row["ack_applied"]) if row["ack_applied"] is not None else None,
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "sent_at": row["sent_at"],
            "ack_at": row["ack_at"],
            "completed_at": row["completed_at"],
        }
