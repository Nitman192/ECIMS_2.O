from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.services.remote_action_task_service import RemoteActionTaskService
from app.utils.time import utcnow


class PlaybookService:
    VALID_TRIGGERS = {"MANUAL", "ALERT_MATCH", "AGENT_HEALTH", "SCHEDULED"}
    VALID_ACTIONS = {"shutdown", "restart", "lockdown", "policy_push"}
    VALID_APPROVAL_MODES = {"AUTO", "MANUAL", "TWO_PERSON"}
    VALID_STATUSES = {"ACTIVE", "DISABLED"}
    VALID_RISK_LEVELS = {"LOW", "HIGH"}
    VALID_RUN_STATUSES = {"PENDING_APPROVAL", "PARTIALLY_APPROVED", "REJECTED", "DISPATCHED", "FAILED"}
    PENDING_RUN_STATUSES = {"PENDING_APPROVAL", "PARTIALLY_APPROVED"}

    @staticmethod
    def list_playbooks(
        *,
        page: int,
        page_size: int,
        status_filter: str | None,
        approval_filter: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if status_filter and status_filter.strip().upper() != "ALL":
            normalized_status = status_filter.strip().upper()
            if normalized_status not in PlaybookService.VALID_STATUSES:
                raise ValueError("INVALID_STATUS")
            where.append("p.status = ?")
            params.append(normalized_status)

        if approval_filter and approval_filter.strip().upper() != "ALL":
            normalized_approval = approval_filter.strip().upper()
            if normalized_approval not in PlaybookService.VALID_APPROVAL_MODES:
                raise ValueError("INVALID_APPROVAL_MODE")
            where.append("p.approval_mode = ?")
            params.append(normalized_approval)

        if query and query.strip():
            q = query.strip().lower()
            term = f"%{q}%"
            where.append("(lower(p.playbook_id) LIKE ? OR lower(p.name) LIKE ? OR lower(p.trigger_type) LIKE ?)")
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        with get_db() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM playbooks p {where_sql}",
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)
            rows = conn.execute(
                f"""
                SELECT
                    p.*,
                    cu.username AS created_by_username,
                    uu.username AS updated_by_username
                FROM playbooks p
                LEFT JOIN users cu ON cu.id = p.created_by_user_id
                LEFT JOIN users uu ON uu.id = p.updated_by_user_id
                {where_sql}
                ORDER BY p.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [PlaybookService._row_to_playbook(row) for row in rows]
        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def create_playbook(
        *,
        name: str,
        description: str,
        trigger_type: str,
        action: str,
        target_agent_ids: list[int],
        approval_mode: str,
        risk_level: str,
        reason_code: str,
        status_value: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None,
        actor_id: int,
    ) -> tuple[dict[str, Any], bool]:
        normalized_name = name.strip()
        if len(normalized_name) < 3:
            raise ValueError("INVALID_NAME")

        normalized_trigger = trigger_type.strip().upper()
        if normalized_trigger not in PlaybookService.VALID_TRIGGERS:
            raise ValueError("INVALID_TRIGGER")

        normalized_action = action.strip().lower()
        if normalized_action not in PlaybookService.VALID_ACTIONS:
            raise ValueError("INVALID_ACTION")

        normalized_approval_mode = approval_mode.strip().upper()
        if normalized_approval_mode not in PlaybookService.VALID_APPROVAL_MODES:
            raise ValueError("INVALID_APPROVAL_MODE")

        normalized_risk_level = risk_level.strip().upper()
        if normalized_risk_level not in PlaybookService.VALID_RISK_LEVELS:
            raise ValueError("INVALID_RISK_LEVEL")

        normalized_reason_code = reason_code.strip().upper()
        if normalized_reason_code not in RemoteActionTaskService.VALID_REASON_CODES:
            raise ValueError("INVALID_REASON_CODE")

        normalized_status = status_value.strip().upper()
        if normalized_status not in PlaybookService.VALID_STATUSES:
            raise ValueError("INVALID_STATUS")

        normalized_idem = idempotency_key.strip()
        if len(normalized_idem) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        normalized_targets = PlaybookService._validate_target_agents(target_agent_ids)
        metadata_obj = metadata or {}
        if not isinstance(metadata_obj, dict):
            raise ValueError("INVALID_METADATA")

        normalized_description = description.strip()
        metadata_json = json.dumps(metadata_obj, sort_keys=True)
        request_hash = PlaybookService._build_request_hash(
            name=normalized_name,
            description=normalized_description,
            trigger_type=normalized_trigger,
            action=normalized_action,
            target_agent_ids=normalized_targets,
            approval_mode=normalized_approval_mode,
            risk_level=normalized_risk_level,
            reason_code=normalized_reason_code,
            status_value=normalized_status,
            metadata_json=metadata_json,
        )
        now_iso = utcnow().isoformat()

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id, request_hash FROM playbooks WHERE idempotency_key = ?",
                (normalized_idem,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                item = PlaybookService._get_playbook_by_id_with_conn(conn, int(existing["id"]))
                if not item:
                    raise ValueError("PLAYBOOK_NOT_FOUND")
                return item, False

            playbook_ref = f"pbk_{secrets.token_hex(8)}"
            cursor = conn.execute(
                """
                INSERT INTO playbooks(
                    playbook_id, name, description, trigger_type, action, target_agent_ids_json, approval_mode,
                    risk_level, reason_code, status, idempotency_key, request_hash, metadata_json,
                    created_by_user_id, updated_by_user_id, created_at, updated_at, last_run_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    playbook_ref,
                    normalized_name,
                    normalized_description,
                    normalized_trigger,
                    normalized_action,
                    json.dumps(normalized_targets),
                    normalized_approval_mode,
                    normalized_risk_level,
                    normalized_reason_code,
                    normalized_status,
                    normalized_idem,
                    request_hash,
                    metadata_json,
                    actor_id,
                    actor_id,
                    now_iso,
                    now_iso,
                ),
            )
            row_id = int(cursor.lastrowid)
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="PLAYBOOK_CREATED",
                target_type="PLAYBOOK",
                target_id=playbook_ref,
                message="Playbook created",
                metadata={
                    "action": normalized_action,
                    "approval_mode": normalized_approval_mode,
                    "target_count": len(normalized_targets),
                    "status": normalized_status,
                },
            )
            item = PlaybookService._get_playbook_by_id_with_conn(conn, row_id)
            if not item:
                raise ValueError("PLAYBOOK_NOT_FOUND")
            return item, True

    @staticmethod
    def list_runs(
        *,
        page: int,
        page_size: int,
        playbook_id: str | None,
        status_filter: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if playbook_id and playbook_id.strip():
            where.append("p.playbook_id = ?")
            params.append(playbook_id.strip())

        if status_filter and status_filter.strip().upper() != "ALL":
            normalized_status = status_filter.strip().upper()
            if normalized_status not in PlaybookService.VALID_RUN_STATUSES:
                raise ValueError("INVALID_RUN_STATUS")
            where.append("r.status = ?")
            params.append(normalized_status)

        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            where.append("(lower(r.run_id) LIKE ? OR lower(p.name) LIKE ? OR lower(r.request_reason) LIKE ?)")
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        with get_db() as conn:
            total_row = conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM playbook_runs r
                JOIN playbooks p ON p.id = r.playbook_id
                {where_sql}
                """,
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)
            rows = conn.execute(
                f"""
                SELECT
                    r.*,
                    p.playbook_id AS playbook_ref,
                    p.name AS playbook_name,
                    p.action AS playbook_action,
                    p.approval_mode AS playbook_approval_mode,
                    ru.username AS requested_by_username,
                    fu.username AS first_approver_username,
                    su.username AS second_approver_username
                FROM playbook_runs r
                JOIN playbooks p ON p.id = r.playbook_id
                LEFT JOIN users ru ON ru.id = r.requested_by_user_id
                LEFT JOIN users fu ON fu.id = r.first_approver_user_id
                LEFT JOIN users su ON su.id = r.second_approver_user_id
                {where_sql}
                ORDER BY r.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [PlaybookService._row_to_run(row) for row in rows]
        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def execute_playbook(*, playbook_id: str, reason: str, actor_id: int) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")

        with get_db() as conn:
            playbook_row = conn.execute(
                "SELECT * FROM playbooks WHERE playbook_id = ?",
                (playbook_id.strip(),),
            ).fetchone()
            if not playbook_row:
                raise ValueError("PLAYBOOK_NOT_FOUND")
            playbook = PlaybookService._row_to_playbook(playbook_row)
            if playbook["status"] != "ACTIVE":
                raise ValueError("PLAYBOOK_DISABLED")

        run_id = f"pbkr_{secrets.token_hex(8)}"
        now_iso = utcnow().isoformat()
        status_value = "PENDING_APPROVAL"
        task_id: int | None = None
        details: dict[str, Any] = {}

        if playbook["approval_mode"] == "AUTO":
            try:
                task_id = PlaybookService._dispatch_task(
                    playbook=playbook,
                    run_id=run_id,
                    reason=normalized_reason,
                    actor_id=actor_id,
                )
                status_value = "DISPATCHED"
            except ValueError as exc:
                status_value = "FAILED"
                details = {"dispatch_error": str(exc)}

        with get_db() as conn:
            playbook_row = conn.execute("SELECT id FROM playbooks WHERE playbook_id = ?", (playbook["playbook_id"],)).fetchone()
            if not playbook_row:
                raise ValueError("PLAYBOOK_NOT_FOUND")
            playbook_row_id = int(playbook_row["id"])
            cursor = conn.execute(
                """
                INSERT INTO playbook_runs(
                    run_id, playbook_id, requested_by_user_id, request_reason, status, first_approver_user_id,
                    second_approver_user_id, decision_reason, task_id, details_json, created_at, updated_at, decided_at, dispatched_at
                )
                VALUES(?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    playbook_row_id,
                    actor_id,
                    normalized_reason,
                    status_value,
                    task_id,
                    json.dumps(details, sort_keys=True),
                    now_iso,
                    now_iso,
                    now_iso if status_value in {"REJECTED", "FAILED", "DISPATCHED"} else None,
                    now_iso if status_value == "DISPATCHED" else None,
                ),
            )
            conn.execute(
                "UPDATE playbooks SET last_run_at = ?, updated_at = ? WHERE id = ?",
                (now_iso, now_iso, playbook_row_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="PLAYBOOK_RUN_CREATED",
                target_type="PLAYBOOK_RUN",
                target_id=run_id,
                message="Playbook run created",
                metadata={
                    "playbook_id": playbook["playbook_id"],
                    "approval_mode": playbook["approval_mode"],
                    "status": status_value,
                    "task_id": task_id,
                },
            )
            created_run = PlaybookService._get_run_by_id_with_conn(conn, int(cursor.lastrowid))
            if not created_run:
                raise ValueError("RUN_NOT_FOUND")
            return created_run

    @staticmethod
    def decide_run(*, run_id: str, decision: str, reason: str, actor_id: int) -> dict[str, Any]:
        normalized_decision = decision.strip().upper()
        if normalized_decision not in {"APPROVE", "REJECT"}:
            raise ValueError("INVALID_DECISION")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")

        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                    r.*,
                    p.playbook_id AS playbook_ref,
                    p.name AS playbook_name,
                    p.action AS playbook_action,
                    p.approval_mode AS playbook_approval_mode,
                    p.target_agent_ids_json AS playbook_target_agent_ids_json,
                    p.reason_code AS playbook_reason_code,
                    p.status AS playbook_status
                FROM playbook_runs r
                JOIN playbooks p ON p.id = r.playbook_id
                WHERE r.run_id = ?
                """,
                (run_id.strip(),),
            ).fetchone()
            if not row:
                raise ValueError("RUN_NOT_FOUND")

        run = dict(row)
        current_status = str(run["status"])
        if current_status not in PlaybookService.PENDING_RUN_STATUSES:
            raise ValueError("RUN_NOT_PENDING")

        requested_by_user_id = int(run["requested_by_user_id"])
        first_approver_user_id = int(run["first_approver_user_id"]) if run["first_approver_user_id"] is not None else None
        approval_mode = str(run["playbook_approval_mode"])
        if approval_mode == "AUTO":
            raise ValueError("INVALID_APPROVAL_MODE")
        if actor_id == requested_by_user_id:
            raise ValueError("APPROVER_MUST_BE_DISTINCT")

        now_iso = utcnow().isoformat()
        if normalized_decision == "REJECT":
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE playbook_runs
                    SET status = 'REJECTED',
                        decision_reason = ?,
                        updated_at = ?,
                        decided_at = ?
                    WHERE run_id = ?
                    """,
                    (normalized_reason, now_iso, now_iso, run_id),
                )
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="PLAYBOOK_RUN_REJECTED",
                    target_type="PLAYBOOK_RUN",
                    target_id=run_id,
                    message="Playbook run rejected",
                    metadata={"playbook_id": run["playbook_ref"], "reason": normalized_reason},
                )
                rejected = PlaybookService._get_run_by_run_id_with_conn(conn, run_id)
                if not rejected:
                    raise ValueError("RUN_NOT_FOUND")
                return rejected

        if approval_mode == "TWO_PERSON" and first_approver_user_id is None:
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE playbook_runs
                    SET status = 'PARTIALLY_APPROVED',
                        first_approver_user_id = ?,
                        decision_reason = ?,
                        updated_at = ?
                    WHERE run_id = ?
                    """,
                    (actor_id, normalized_reason, now_iso, run_id),
                )
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="PLAYBOOK_RUN_FIRST_APPROVAL",
                    target_type="PLAYBOOK_RUN",
                    target_id=run_id,
                    message="Playbook run first approval recorded",
                    metadata={"playbook_id": run["playbook_ref"]},
                )
                partial = PlaybookService._get_run_by_run_id_with_conn(conn, run_id)
                if not partial:
                    raise ValueError("RUN_NOT_FOUND")
                return partial

        if first_approver_user_id is not None and actor_id == first_approver_user_id:
            raise ValueError("APPROVER_MUST_BE_DISTINCT")

        playbook_view = {
            "playbook_id": str(run["playbook_ref"]),
            "action": str(run["playbook_action"]),
            "target_agent_ids": PlaybookService._safe_json_list(run["playbook_target_agent_ids_json"]),
            "reason_code": str(run["playbook_reason_code"]),
            "approval_mode": approval_mode,
            "status": str(run["playbook_status"]),
        }
        if playbook_view["status"] != "ACTIVE":
            raise ValueError("PLAYBOOK_DISABLED")

        next_status = "DISPATCHED"
        task_id: int | None = None
        details: dict[str, Any] = {}
        try:
            task_id = PlaybookService._dispatch_task(
                playbook=playbook_view,
                run_id=run_id,
                reason=normalized_reason,
                actor_id=actor_id,
            )
        except ValueError as exc:
            next_status = "FAILED"
            details = {"dispatch_error": str(exc)}

        with get_db() as conn:
            conn.execute(
                """
                UPDATE playbook_runs
                SET status = ?,
                    first_approver_user_id = COALESCE(first_approver_user_id, ?),
                    second_approver_user_id = CASE
                        WHEN ? = 'TWO_PERSON' THEN ?
                        ELSE second_approver_user_id
                    END,
                    decision_reason = ?,
                    task_id = ?,
                    details_json = ?,
                    updated_at = ?,
                    decided_at = ?,
                    dispatched_at = ?
                WHERE run_id = ?
                """,
                (
                    next_status,
                    actor_id,
                    approval_mode,
                    actor_id if approval_mode == "TWO_PERSON" else None,
                    normalized_reason,
                    task_id,
                    json.dumps(details, sort_keys=True),
                    now_iso,
                    now_iso,
                    now_iso if next_status == "DISPATCHED" else None,
                    run_id,
                ),
            )
            conn.execute(
                "UPDATE playbooks SET last_run_at = ?, updated_at = ? WHERE id = ?",
                (now_iso, now_iso, int(run["playbook_id"])),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="PLAYBOOK_RUN_APPROVED_AND_DISPATCHED" if next_status == "DISPATCHED" else "PLAYBOOK_RUN_DISPATCH_FAILED",
                target_type="PLAYBOOK_RUN",
                target_id=run_id,
                message="Playbook run decision applied",
                metadata={"status": next_status, "task_id": task_id, "playbook_id": run["playbook_ref"]},
            )
            decided = PlaybookService._get_run_by_run_id_with_conn(conn, run_id)
            if not decided:
                raise ValueError("RUN_NOT_FOUND")
            return decided

    @staticmethod
    def _dispatch_task(*, playbook: dict[str, Any], run_id: str, reason: str, actor_id: int) -> int:
        task, _created = RemoteActionTaskService.create_task(
            action=str(playbook["action"]),
            agent_ids=[int(agent_id) for agent_id in playbook["target_agent_ids"]],
            idempotency_key=f"playbook-run:{run_id}",
            reason_code=str(playbook["reason_code"]),
            reason=reason,
            confirm_high_risk=True,
            metadata={
                "source": "playbook",
                "playbook_id": playbook["playbook_id"],
                "run_id": run_id,
            },
            actor_id=actor_id,
        )
        return int(task["id"])

    @staticmethod
    def _validate_target_agents(agent_ids: list[int]) -> list[int]:
        deduped = sorted({int(agent_id) for agent_id in agent_ids if int(agent_id) > 0})
        if not deduped:
            raise ValueError("INVALID_AGENT_IDS")
        if len(deduped) > 100:
            raise ValueError("BATCH_TOO_LARGE")
        with get_db() as conn:
            rows = conn.execute(
                f"SELECT id, agent_revoked FROM agents WHERE id IN ({','.join('?' for _ in deduped)})",
                tuple(deduped),
            ).fetchall()
        found = {int(row["id"]) for row in rows}
        missing = sorted(set(deduped) - found)
        if missing:
            raise ValueError(f"MISSING_AGENTS:{','.join(str(item) for item in missing)}")
        revoked = sorted(int(row["id"]) for row in rows if bool(row["agent_revoked"]))
        if revoked:
            raise ValueError(f"REVOKED_AGENTS:{','.join(str(item) for item in revoked)}")
        return deduped

    @staticmethod
    def _build_request_hash(
        *,
        name: str,
        description: str,
        trigger_type: str,
        action: str,
        target_agent_ids: list[int],
        approval_mode: str,
        risk_level: str,
        reason_code: str,
        status_value: str,
        metadata_json: str,
    ) -> str:
        payload = {
            "name": name,
            "description": description,
            "trigger_type": trigger_type,
            "action": action,
            "target_agent_ids": target_agent_ids,
            "approval_mode": approval_mode,
            "risk_level": risk_level,
            "reason_code": reason_code,
            "status": status_value,
            "metadata_json": metadata_json,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _get_playbook_by_id_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                p.*,
                cu.username AS created_by_username,
                uu.username AS updated_by_username
            FROM playbooks p
            LEFT JOIN users cu ON cu.id = p.created_by_user_id
            LEFT JOIN users uu ON uu.id = p.updated_by_user_id
            WHERE p.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return PlaybookService._row_to_playbook(row)

    @staticmethod
    def _get_run_by_id_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                r.*,
                p.playbook_id AS playbook_ref,
                p.name AS playbook_name,
                p.action AS playbook_action,
                p.approval_mode AS playbook_approval_mode,
                ru.username AS requested_by_username,
                fu.username AS first_approver_username,
                su.username AS second_approver_username
            FROM playbook_runs r
            JOIN playbooks p ON p.id = r.playbook_id
            LEFT JOIN users ru ON ru.id = r.requested_by_user_id
            LEFT JOIN users fu ON fu.id = r.first_approver_user_id
            LEFT JOIN users su ON su.id = r.second_approver_user_id
            WHERE r.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return PlaybookService._row_to_run(row)

    @staticmethod
    def _get_run_by_run_id_with_conn(conn, run_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                r.*,
                p.playbook_id AS playbook_ref,
                p.name AS playbook_name,
                p.action AS playbook_action,
                p.approval_mode AS playbook_approval_mode,
                ru.username AS requested_by_username,
                fu.username AS first_approver_username,
                su.username AS second_approver_username
            FROM playbook_runs r
            JOIN playbooks p ON p.id = r.playbook_id
            LEFT JOIN users ru ON ru.id = r.requested_by_user_id
            LEFT JOIN users fu ON fu.id = r.first_approver_user_id
            LEFT JOIN users su ON su.id = r.second_approver_user_id
            WHERE r.run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return PlaybookService._row_to_run(row)

    @staticmethod
    def _row_to_playbook(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "playbook_id": str(row_map["playbook_id"]),
            "name": str(row_map["name"]),
            "description": str(row_map["description"] or ""),
            "trigger_type": str(row_map["trigger_type"]),
            "action": str(row_map["action"]),
            "target_agent_ids": PlaybookService._safe_json_list(row_map.get("target_agent_ids_json")),
            "approval_mode": str(row_map["approval_mode"]),
            "risk_level": str(row_map["risk_level"]),
            "reason_code": str(row_map["reason_code"]),
            "status": str(row_map["status"]),
            "metadata": PlaybookService._safe_json_dict(row_map.get("metadata_json")),
            "created_by_user_id": int(row_map["created_by_user_id"]),
            "updated_by_user_id": int(row_map["updated_by_user_id"]),
            "created_by_username": row_map.get("created_by_username"),
            "updated_by_username": row_map.get("updated_by_username"),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
            "last_run_at": row_map.get("last_run_at"),
        }

    @staticmethod
    def _row_to_run(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "run_id": str(row_map["run_id"]),
            "playbook_id": str(row_map["playbook_ref"]),
            "playbook_name": str(row_map["playbook_name"]),
            "playbook_action": str(row_map["playbook_action"]),
            "playbook_approval_mode": str(row_map["playbook_approval_mode"]),
            "requested_by_user_id": int(row_map["requested_by_user_id"]),
            "requested_by_username": row_map.get("requested_by_username"),
            "request_reason": str(row_map["request_reason"]),
            "status": str(row_map["status"]),
            "first_approver_user_id": int(row_map["first_approver_user_id"]) if row_map["first_approver_user_id"] is not None else None,
            "first_approver_username": row_map.get("first_approver_username"),
            "second_approver_user_id": int(row_map["second_approver_user_id"]) if row_map["second_approver_user_id"] is not None else None,
            "second_approver_username": row_map.get("second_approver_username"),
            "decision_reason": row_map.get("decision_reason"),
            "task_id": int(row_map["task_id"]) if row_map["task_id"] is not None else None,
            "details": PlaybookService._safe_json_dict(row_map.get("details_json")),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
            "decided_at": row_map.get("decided_at"),
            "dispatched_at": row_map.get("dispatched_at"),
        }

    @staticmethod
    def _safe_json_dict(value: object) -> dict[str, Any]:
        try:
            parsed = json.loads(str(value or "{}"))
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}

    @staticmethod
    def _safe_json_list(value: object) -> list[int]:
        try:
            parsed = json.loads(str(value or "[]"))
            if isinstance(parsed, list):
                return [int(item) for item in parsed]
            return []
        except Exception:
            return []
