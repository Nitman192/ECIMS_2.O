from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class ChangeControlService:
    VALID_CHANGE_TYPES = {"POLICY", "FEATURE_FLAG", "PLAYBOOK", "SCHEDULE", "ENROLLMENT_POLICY", "BREAK_GLASS_POLICY"}
    VALID_RISK_LEVELS = {"LOW", "HIGH", "CRITICAL"}
    VALID_STATUSES = {"PENDING", "PARTIALLY_APPROVED", "APPROVED", "REJECTED", "CANCELLED"}
    PENDING_STATUSES = {"PENDING", "PARTIALLY_APPROVED"}

    @staticmethod
    def list_requests(
        *,
        page: int,
        page_size: int,
        status_filter: str | None,
        risk_filter: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if status_filter and status_filter.strip().upper() != "ALL":
            normalized_status = status_filter.strip().upper()
            if normalized_status not in ChangeControlService.VALID_STATUSES:
                raise ValueError("INVALID_STATUS")
            where.append("c.status = ?")
            params.append(normalized_status)

        if risk_filter and risk_filter.strip().upper() != "ALL":
            normalized_risk = risk_filter.strip().upper()
            if normalized_risk not in ChangeControlService.VALID_RISK_LEVELS:
                raise ValueError("INVALID_RISK_LEVEL")
            where.append("c.risk_level = ?")
            params.append(normalized_risk)

        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            where.append("(lower(c.request_id) LIKE ? OR lower(c.target_ref) LIKE ? OR lower(c.summary) LIKE ?)")
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        with get_db() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM change_requests c {where_sql}",
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT
                    c.*,
                    ru.username AS requested_by_username,
                    fu.username AS first_approver_username,
                    su.username AS second_approver_username
                FROM change_requests c
                LEFT JOIN users ru ON ru.id = c.requested_by_user_id
                LEFT JOIN users fu ON fu.id = c.first_approver_user_id
                LEFT JOIN users su ON su.id = c.second_approver_user_id
                {where_sql}
                ORDER BY c.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [ChangeControlService._row_to_request(row) for row in rows]
        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def create_request(
        *,
        change_type: str,
        target_ref: str,
        summary: str,
        proposed_changes: dict[str, Any] | None,
        risk_level: str,
        reason: str,
        two_person_rule: bool,
        idempotency_key: str,
        metadata: dict[str, Any] | None,
        actor_id: int,
    ) -> tuple[dict[str, Any], bool]:
        normalized_change_type = change_type.strip().upper()
        if normalized_change_type not in ChangeControlService.VALID_CHANGE_TYPES:
            raise ValueError("INVALID_CHANGE_TYPE")

        normalized_target_ref = target_ref.strip()
        if len(normalized_target_ref) < 2:
            raise ValueError("INVALID_TARGET_REF")

        normalized_summary = summary.strip()
        if len(normalized_summary) < 5:
            raise ValueError("INVALID_SUMMARY")

        normalized_risk = risk_level.strip().upper()
        if normalized_risk not in ChangeControlService.VALID_RISK_LEVELS:
            raise ValueError("INVALID_RISK_LEVEL")

        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")

        normalized_idem = idempotency_key.strip()
        if len(normalized_idem) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        proposed_obj = proposed_changes or {}
        if not isinstance(proposed_obj, dict):
            raise ValueError("INVALID_PROPOSED_CHANGES")
        metadata_obj = metadata or {}
        if not isinstance(metadata_obj, dict):
            raise ValueError("INVALID_METADATA")

        approvals_required = 2 if bool(two_person_rule) or normalized_risk in {"HIGH", "CRITICAL"} else 1
        proposed_json = json.dumps(proposed_obj, sort_keys=True)
        metadata_json = json.dumps(metadata_obj, sort_keys=True)
        request_hash = ChangeControlService._build_request_hash(
            change_type=normalized_change_type,
            target_ref=normalized_target_ref,
            summary=normalized_summary,
            proposed_json=proposed_json,
            risk_level=normalized_risk,
            reason=normalized_reason,
            approvals_required=approvals_required,
            metadata_json=metadata_json,
        )
        now_iso = utcnow().isoformat()

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id, request_hash FROM change_requests WHERE idempotency_key = ?",
                (normalized_idem,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                item = ChangeControlService._get_request_by_id_with_conn(conn, int(existing["id"]))
                if not item:
                    raise ValueError("REQUEST_NOT_FOUND")
                return item, False

            request_id = f"ccr_{secrets.token_hex(8)}"
            cursor = conn.execute(
                """
                INSERT INTO change_requests(
                    request_id, change_type, target_ref, summary, proposed_changes_json, risk_level, status,
                    approvals_required, reason, metadata_json, idempotency_key, request_hash, requested_by_user_id,
                    first_approver_user_id, second_approver_user_id, decision_reason, created_at, updated_at, decided_at
                )
                VALUES(?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL)
                """,
                (
                    request_id,
                    normalized_change_type,
                    normalized_target_ref,
                    normalized_summary,
                    proposed_json,
                    normalized_risk,
                    approvals_required,
                    normalized_reason,
                    metadata_json,
                    normalized_idem,
                    request_hash,
                    actor_id,
                    now_iso,
                    now_iso,
                ),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="CHANGE_REQUEST_CREATED",
                target_type="CHANGE_REQUEST",
                target_id=request_id,
                message="Change control request created",
                metadata={"change_type": normalized_change_type, "risk_level": normalized_risk, "approvals_required": approvals_required},
            )
            item = ChangeControlService._get_request_by_id_with_conn(conn, int(cursor.lastrowid))
            if not item:
                raise ValueError("REQUEST_NOT_FOUND")
            return item, True

    @staticmethod
    def decide_request(*, request_id: str, decision: str, reason: str, actor_id: int) -> dict[str, Any]:
        normalized_decision = decision.strip().upper()
        if normalized_decision not in {"APPROVE", "REJECT"}:
            raise ValueError("INVALID_DECISION")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")

        with get_db() as conn:
            row = conn.execute("SELECT * FROM change_requests WHERE request_id = ?", (request_id.strip(),)).fetchone()
            if not row:
                raise ValueError("REQUEST_NOT_FOUND")

        record = dict(row)
        current_status = str(record["status"])
        if current_status not in ChangeControlService.PENDING_STATUSES:
            raise ValueError("REQUEST_NOT_PENDING")

        requested_by_user_id = int(record["requested_by_user_id"])
        if actor_id == requested_by_user_id:
            raise ValueError("APPROVER_MUST_BE_DISTINCT")

        now_iso = utcnow().isoformat()
        if normalized_decision == "REJECT":
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE change_requests
                    SET status = 'REJECTED',
                        decision_reason = ?,
                        updated_at = ?,
                        decided_at = ?
                    WHERE request_id = ?
                    """,
                    (normalized_reason, now_iso, now_iso, request_id),
                )
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="CHANGE_REQUEST_REJECTED",
                    target_type="CHANGE_REQUEST",
                    target_id=request_id,
                    message="Change request rejected",
                    metadata={"reason": normalized_reason},
                )
                item = ChangeControlService._get_request_by_request_id_with_conn(conn, request_id)
                if not item:
                    raise ValueError("REQUEST_NOT_FOUND")
                return item

        approvals_required = int(record["approvals_required"])
        first_approver = int(record["first_approver_user_id"]) if record["first_approver_user_id"] is not None else None
        second_approver = int(record["second_approver_user_id"]) if record["second_approver_user_id"] is not None else None
        if first_approver is not None and actor_id == first_approver:
            raise ValueError("APPROVER_MUST_BE_DISTINCT")
        if second_approver is not None:
            raise ValueError("REQUEST_NOT_PENDING")

        next_status = "APPROVED"
        set_first = first_approver
        set_second = second_approver
        decided_at = now_iso
        action = "CHANGE_REQUEST_APPROVED"

        if approvals_required == 2 and first_approver is None:
            next_status = "PARTIALLY_APPROVED"
            set_first = actor_id
            set_second = None
            decided_at = None
            action = "CHANGE_REQUEST_FIRST_APPROVAL"
        elif approvals_required == 2:
            set_second = actor_id
            action = "CHANGE_REQUEST_SECOND_APPROVAL"
        else:
            set_first = actor_id

        with get_db() as conn:
            conn.execute(
                """
                UPDATE change_requests
                SET status = ?,
                    first_approver_user_id = ?,
                    second_approver_user_id = ?,
                    decision_reason = ?,
                    updated_at = ?,
                    decided_at = ?
                WHERE request_id = ?
                """,
                (next_status, set_first, set_second, normalized_reason, now_iso, decided_at, request_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action=action,
                target_type="CHANGE_REQUEST",
                target_id=request_id,
                message="Change request decision recorded",
                metadata={"status": next_status, "approvals_required": approvals_required},
            )
            item = ChangeControlService._get_request_by_request_id_with_conn(conn, request_id)
            if not item:
                raise ValueError("REQUEST_NOT_FOUND")
            return item

    @staticmethod
    def _build_request_hash(
        *,
        change_type: str,
        target_ref: str,
        summary: str,
        proposed_json: str,
        risk_level: str,
        reason: str,
        approvals_required: int,
        metadata_json: str,
    ) -> str:
        payload = {
            "change_type": change_type,
            "target_ref": target_ref,
            "summary": summary,
            "proposed_json": proposed_json,
            "risk_level": risk_level,
            "reason": reason,
            "approvals_required": approvals_required,
            "metadata_json": metadata_json,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _get_request_by_id_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                c.*,
                ru.username AS requested_by_username,
                fu.username AS first_approver_username,
                su.username AS second_approver_username
            FROM change_requests c
            LEFT JOIN users ru ON ru.id = c.requested_by_user_id
            LEFT JOIN users fu ON fu.id = c.first_approver_user_id
            LEFT JOIN users su ON su.id = c.second_approver_user_id
            WHERE c.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return ChangeControlService._row_to_request(row)

    @staticmethod
    def _get_request_by_request_id_with_conn(conn, request_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                c.*,
                ru.username AS requested_by_username,
                fu.username AS first_approver_username,
                su.username AS second_approver_username
            FROM change_requests c
            LEFT JOIN users ru ON ru.id = c.requested_by_user_id
            LEFT JOIN users fu ON fu.id = c.first_approver_user_id
            LEFT JOIN users su ON su.id = c.second_approver_user_id
            WHERE c.request_id = ?
            """,
            (request_id,),
        ).fetchone()
        if not row:
            return None
        return ChangeControlService._row_to_request(row)

    @staticmethod
    def _row_to_request(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "request_id": str(row_map["request_id"]),
            "change_type": str(row_map["change_type"]),
            "target_ref": str(row_map["target_ref"]),
            "summary": str(row_map["summary"]),
            "proposed_changes": ChangeControlService._safe_json_dict(row_map.get("proposed_changes_json")),
            "risk_level": str(row_map["risk_level"]),
            "status": str(row_map["status"]),
            "approvals_required": int(row_map["approvals_required"]),
            "reason": str(row_map["reason"]),
            "metadata": ChangeControlService._safe_json_dict(row_map.get("metadata_json")),
            "requested_by_user_id": int(row_map["requested_by_user_id"]),
            "requested_by_username": row_map.get("requested_by_username"),
            "first_approver_user_id": int(row_map["first_approver_user_id"]) if row_map["first_approver_user_id"] is not None else None,
            "first_approver_username": row_map.get("first_approver_username"),
            "second_approver_user_id": int(row_map["second_approver_user_id"]) if row_map["second_approver_user_id"] is not None else None,
            "second_approver_username": row_map.get("second_approver_username"),
            "decision_reason": row_map.get("decision_reason"),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
            "decided_at": row_map.get("decided_at"),
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
