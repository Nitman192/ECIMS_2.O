from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.services.user_service import UserService
from app.utils.time import utcnow


class BreakGlassService:
    VALID_SCOPES = {"INCIDENT_RESPONSE", "SYSTEM_RECOVERY", "FORENSICS", "OTHER"}
    VALID_STATUSES = {"ACTIVE", "EXPIRED", "REVOKED"}
    MIN_DURATION_MINUTES = 5
    MAX_DURATION_MINUTES = 240

    @staticmethod
    def list_sessions(
        *,
        page: int,
        page_size: int,
        status_filter: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        with get_db() as conn:
            BreakGlassService._touch_expired_with_conn(conn)

            where: list[str] = []
            params: list[Any] = []
            if status_filter and status_filter.strip().upper() != "ALL":
                normalized_status = status_filter.strip().upper()
                if normalized_status not in BreakGlassService.VALID_STATUSES:
                    raise ValueError("INVALID_STATUS")
                where.append("b.status = ?")
                params.append(normalized_status)

            if query and query.strip():
                term = f"%{query.strip().lower()}%"
                where.append("(lower(b.session_id) LIKE ? OR lower(b.reason) LIKE ? OR lower(ru.username) LIKE ?)")
                params.extend([term, term, term])

            where_sql = f"WHERE {' AND '.join(where)}" if where else ""
            offset = (page - 1) * page_size

            total_row = conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM break_glass_sessions b
                LEFT JOIN users ru ON ru.id = b.requested_by_user_id
                {where_sql}
                """,
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT
                    b.*,
                    ru.username AS requested_by_username,
                    vu.username AS revoked_by_username
                FROM break_glass_sessions b
                LEFT JOIN users ru ON ru.id = b.requested_by_user_id
                LEFT JOIN users vu ON vu.id = b.revoked_by_user_id
                {where_sql}
                ORDER BY b.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [BreakGlassService._row_to_session(row) for row in rows]
        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def create_session(
        *,
        actor_id: int,
        actor_username: str,
        current_password: str,
        reason: str,
        scope: str,
        duration_minutes: int,
        idempotency_key: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], bool, str | None]:
        normalized_scope = scope.strip().upper()
        if normalized_scope not in BreakGlassService.VALID_SCOPES:
            raise ValueError("INVALID_SCOPE")

        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")

        duration = int(duration_minutes)
        if duration < BreakGlassService.MIN_DURATION_MINUTES or duration > BreakGlassService.MAX_DURATION_MINUTES:
            raise ValueError("INVALID_DURATION")

        normalized_idem = idempotency_key.strip()
        if len(normalized_idem) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        metadata_obj = metadata or {}
        if not isinstance(metadata_obj, dict):
            raise ValueError("INVALID_METADATA")
        metadata_json = json.dumps(metadata_obj, sort_keys=True)

        verified = UserService.verify_credentials(actor_username, current_password)
        if not verified or int(verified["id"]) != actor_id:
            raise ValueError("INVALID_REAUTH")

        request_hash = BreakGlassService._build_request_hash(
            actor_id=actor_id,
            reason=normalized_reason,
            scope=normalized_scope,
            duration_minutes=duration,
            metadata_json=metadata_json,
        )
        now = utcnow()
        now_iso = now.isoformat()
        expires_at = (now + timedelta(minutes=duration)).isoformat()

        with get_db() as conn:
            BreakGlassService._touch_expired_with_conn(conn)
            existing = conn.execute(
                "SELECT id, request_hash FROM break_glass_sessions WHERE idempotency_key = ?",
                (normalized_idem,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                item = BreakGlassService._get_session_by_id_with_conn(conn, int(existing["id"]))
                if not item:
                    raise ValueError("SESSION_NOT_FOUND")
                return item, False, None

            session_id = f"bgs_{secrets.token_hex(8)}"
            secret = secrets.token_urlsafe(24)
            token_value = f"bgtk_{session_id}.{secret}"
            secret_hash = BreakGlassService._secret_hash(secret)
            cursor = conn.execute(
                """
                INSERT INTO break_glass_sessions(
                    session_id, requested_by_user_id, revoked_by_user_id, reason, scope, status, duration_minutes,
                    started_at, expires_at, ended_at, reauth_method, idempotency_key, request_hash, session_secret_hash,
                    metadata_json, created_at, updated_at
                )
                VALUES(?, ?, NULL, ?, ?, 'ACTIVE', ?, ?, ?, NULL, 'PASSWORD', ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    actor_id,
                    normalized_reason,
                    normalized_scope,
                    duration,
                    now_iso,
                    expires_at,
                    normalized_idem,
                    request_hash,
                    secret_hash,
                    metadata_json,
                    now_iso,
                    now_iso,
                ),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="BREAK_GLASS_SESSION_STARTED",
                target_type="BREAK_GLASS_SESSION",
                target_id=session_id,
                message="Break-glass emergency session opened",
                metadata={"scope": normalized_scope, "duration_minutes": duration, "expires_at": expires_at},
            )
            item = BreakGlassService._get_session_by_id_with_conn(conn, int(cursor.lastrowid))
            if not item:
                raise ValueError("SESSION_NOT_FOUND")
            return item, True, token_value

    @staticmethod
    def revoke_session(*, session_id: str, reason: str, actor_id: int) -> dict[str, Any] | None:
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")

        now_iso = utcnow().isoformat()
        with get_db() as conn:
            BreakGlassService._touch_expired_with_conn(conn)
            row = conn.execute(
                "SELECT id, status FROM break_glass_sessions WHERE session_id = ?",
                (session_id.strip(),),
            ).fetchone()
            if not row:
                return None
            status_value = str(row["status"])
            if status_value == "ACTIVE":
                conn.execute(
                    """
                    UPDATE break_glass_sessions
                    SET status = 'REVOKED',
                        revoked_by_user_id = ?,
                        ended_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (actor_id, now_iso, now_iso, int(row["id"])),
                )
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="BREAK_GLASS_SESSION_REVOKED",
                    target_type="BREAK_GLASS_SESSION",
                    target_id=session_id,
                    message="Break-glass session revoked",
                    metadata={"reason": normalized_reason},
                )
            return BreakGlassService._get_session_by_id_with_conn(conn, int(row["id"]))

    @staticmethod
    def _touch_expired_with_conn(conn) -> None:
        now_iso = utcnow().isoformat()
        conn.execute(
            """
            UPDATE break_glass_sessions
            SET status = 'EXPIRED',
                ended_at = COALESCE(ended_at, ?),
                updated_at = ?
            WHERE status = 'ACTIVE' AND expires_at <= ?
            """,
            (now_iso, now_iso, now_iso),
        )

    @staticmethod
    def _get_session_by_id_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                b.*,
                ru.username AS requested_by_username,
                vu.username AS revoked_by_username
            FROM break_glass_sessions b
            LEFT JOIN users ru ON ru.id = b.requested_by_user_id
            LEFT JOIN users vu ON vu.id = b.revoked_by_user_id
            WHERE b.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return BreakGlassService._row_to_session(row)

    @staticmethod
    def _build_request_hash(
        *,
        actor_id: int,
        reason: str,
        scope: str,
        duration_minutes: int,
        metadata_json: str,
    ) -> str:
        payload = {
            "actor_id": actor_id,
            "reason": reason,
            "scope": scope,
            "duration_minutes": duration_minutes,
            "metadata_json": metadata_json,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _secret_hash(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_session(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "session_id": str(row_map["session_id"]),
            "requested_by_user_id": int(row_map["requested_by_user_id"]),
            "requested_by_username": row_map.get("requested_by_username"),
            "revoked_by_user_id": int(row_map["revoked_by_user_id"]) if row_map["revoked_by_user_id"] is not None else None,
            "revoked_by_username": row_map.get("revoked_by_username"),
            "reason": str(row_map["reason"]),
            "scope": str(row_map["scope"]),
            "status": str(row_map["status"]),
            "duration_minutes": int(row_map["duration_minutes"]),
            "started_at": row_map["started_at"],
            "expires_at": row_map["expires_at"],
            "ended_at": row_map.get("ended_at"),
            "reauth_method": str(row_map["reauth_method"]),
            "metadata": BreakGlassService._safe_json_dict(row_map.get("metadata_json")),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
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
