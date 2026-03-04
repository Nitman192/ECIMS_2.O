from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class EnrollmentService:
    VALID_MODES = {"ONLINE", "OFFLINE"}
    VALID_STATUSES = {"ACTIVE", "REVOKED", "EXPIRED", "CONSUMED"}
    VALID_REASON_CODES = {
        "MAINTENANCE",
        "OFFLINE_AIRGAP",
        "BOOTSTRAP",
        "INCIDENT_RESPONSE",
        "TESTING",
        "COMPLIANCE",
    }

    @staticmethod
    def list_tokens(
        *,
        page: int,
        page_size: int,
        mode_filter: str | None,
        status_filter: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        with get_db() as conn:
            EnrollmentService._touch_expired_tokens_with_conn(conn)

            where: list[str] = []
            params: list[Any] = []

            if mode_filter and mode_filter.strip().upper() != "ALL":
                mode = mode_filter.strip().upper()
                if mode not in EnrollmentService.VALID_MODES:
                    raise ValueError("INVALID_MODE")
                where.append("mode = ?")
                params.append(mode)

            if status_filter and status_filter.strip().upper() != "ALL":
                token_status = status_filter.strip().upper()
                if token_status not in EnrollmentService.VALID_STATUSES:
                    raise ValueError("INVALID_STATUS")
                where.append("status = ?")
                params.append(token_status)

            if query and query.strip():
                q = query.strip().lower()
                term = f"%{q}%"
                where.append("(lower(token_id) LIKE ? OR lower(reason) LIKE ?)")
                params.extend([term, term])

            where_sql = f"WHERE {' AND '.join(where)}" if where else ""
            offset = (page - 1) * page_size

            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM enrollment_tokens {where_sql}",
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT e.*, u.username AS created_by_username, ru.username AS revoked_by_username
                FROM enrollment_tokens e
                LEFT JOIN users u ON u.id = e.created_by_user_id
                LEFT JOIN users ru ON ru.id = e.revoked_by_user_id
                {where_sql}
                ORDER BY e.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [EnrollmentService._row_to_token(row) for row in rows]

        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def issue_token(
        *,
        mode: str,
        expires_in_hours: int,
        max_uses: int,
        reason_code: str,
        reason: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None,
        actor_id: int,
    ) -> tuple[dict[str, Any], bool, str | None, dict[str, str] | None, dict[str, Any] | None]:
        normalized_mode = mode.strip().upper()
        if normalized_mode not in EnrollmentService.VALID_MODES:
            raise ValueError("INVALID_MODE")
        normalized_reason_code = reason_code.strip().upper()
        if normalized_reason_code not in EnrollmentService.VALID_REASON_CODES:
            raise ValueError("INVALID_REASON_CODE")
        if max_uses < 1 or max_uses > 1000:
            raise ValueError("INVALID_MAX_USES")
        if expires_in_hours < 1 or expires_in_hours > 720:
            raise ValueError("INVALID_EXPIRY")
        normalized_idempotency_key = idempotency_key.strip()
        if len(normalized_idempotency_key) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        metadata_obj = metadata or {}
        metadata_json = json.dumps(metadata_obj, sort_keys=True)
        req_hash = EnrollmentService._build_issue_request_hash(
            mode=normalized_mode,
            expires_in_hours=expires_in_hours,
            max_uses=max_uses,
            reason_code=normalized_reason_code,
            reason=reason.strip(),
            metadata_json=metadata_json,
        )

        now_iso = utcnow().isoformat()
        expires_at = (utcnow() + timedelta(hours=expires_in_hours)).isoformat()
        token_id = secrets.token_hex(8)
        secret = secrets.token_urlsafe(24)
        token_value = f"ectk_{token_id}.{secret}"
        secret_hash = EnrollmentService._secret_hash(secret)
        offline_kit_bundle: dict[str, Any] | None = None

        with get_db() as conn:
            EnrollmentService._touch_expired_tokens_with_conn(conn)
            existing = conn.execute(
                "SELECT id, request_hash FROM enrollment_tokens WHERE idempotency_key = ?",
                (normalized_idempotency_key,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != req_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                item = EnrollmentService._get_token_by_id_with_conn(conn, int(existing["id"]))
                if not item:
                    raise ValueError("TOKEN_NOT_FOUND")
                return item, False, None, None, None

            conn.execute(
                """
                INSERT INTO enrollment_tokens(
                    token_id, token_secret_hash, mode, status, expires_at, max_uses, used_count,
                    reason_code, reason, idempotency_key, request_hash, metadata_json,
                    created_by_user_id, created_at, updated_at, last_used_at, revoked_at, revoked_by_user_id
                )
                VALUES(?, ?, ?, 'ACTIVE', ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                """,
                (
                    token_id,
                    secret_hash,
                    normalized_mode,
                    expires_at,
                    max_uses,
                    normalized_reason_code,
                    reason.strip(),
                    normalized_idempotency_key,
                    req_hash,
                    metadata_json,
                    actor_id,
                    now_iso,
                    now_iso,
                ),
            )
            item = EnrollmentService._get_token_by_token_id_with_conn(conn, token_id)
            if not item:
                raise ValueError("TOKEN_NOT_FOUND")

            if normalized_mode == "OFFLINE":
                kit_id = f"kit_{secrets.token_hex(8)}"
                offline_kit_bundle = EnrollmentService._build_offline_kit_bundle(
                    kit_id=kit_id,
                    token_value=token_value,
                    mode=normalized_mode,
                    expires_at=expires_at,
                    max_uses=max_uses,
                    reason_code=normalized_reason_code,
                    reason=reason.strip(),
                    metadata=metadata_obj,
                )
                bundle_hash = hashlib.sha256(
                    json.dumps(offline_kit_bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                conn.execute(
                    """
                    INSERT INTO offline_enrollment_kits(
                        kit_id, token_id, bundle_hash, status, metadata_json, created_at, imported_at, created_by_user_id, imported_by_user_id
                    )
                    VALUES(?, ?, ?, 'EXPORTED', ?, ?, NULL, ?, NULL)
                    """,
                    (kit_id, token_id, bundle_hash, metadata_json, now_iso, actor_id),
                )

            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="ENROLLMENT_TOKEN_ISSUED",
                target_type="ENROLLMENT_TOKEN",
                target_id=token_id,
                message="Enrollment token issued",
                metadata={
                    "mode": normalized_mode,
                    "expires_at": expires_at,
                    "max_uses": max_uses,
                    "reason_code": normalized_reason_code,
                },
            )

        cli = EnrollmentService._build_cli_snippets(token_value=token_value)
        return item, True, token_value, cli, offline_kit_bundle

    @staticmethod
    def revoke_token(*, token_id: str, reason: str, actor_id: int) -> dict[str, Any] | None:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            EnrollmentService._touch_expired_tokens_with_conn(conn)
            row = conn.execute(
                "SELECT id, status FROM enrollment_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if not row:
                return None
            prev_status = str(row["status"])
            if prev_status == "REVOKED":
                return EnrollmentService._get_token_by_token_id_with_conn(conn, token_id)
            conn.execute(
                """
                UPDATE enrollment_tokens
                SET status = 'REVOKED', revoked_at = ?, revoked_by_user_id = ?, updated_at = ?
                WHERE token_id = ?
                """,
                (now_iso, actor_id, now_iso, token_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="ENROLLMENT_TOKEN_REVOKED",
                target_type="ENROLLMENT_TOKEN",
                target_id=token_id,
                message="Enrollment token revoked",
                metadata={"previous_status": prev_status, "reason": reason.strip()},
            )
            return EnrollmentService._get_token_by_token_id_with_conn(conn, token_id)

    @staticmethod
    def import_offline_kit(*, bundle: dict[str, Any], actor_id: int) -> tuple[dict[str, Any], bool, bool]:
        kit_id, token_value, mode, expires_at, max_uses, reason_code, reason, metadata_obj = EnrollmentService._validate_kit_bundle(bundle)
        token_id, secret = EnrollmentService._parse_token_value(token_value)
        secret_hash = EnrollmentService._secret_hash(secret)
        now_iso = utcnow().isoformat()

        metadata_json = json.dumps(metadata_obj, sort_keys=True)
        bundle_hash = hashlib.sha256(
            json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        req_hash = bundle_hash

        created_token = False
        created_kit = False
        with get_db() as conn:
            EnrollmentService._touch_expired_tokens_with_conn(conn)
            existing_token = conn.execute(
                "SELECT id, token_secret_hash FROM enrollment_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if existing_token:
                if str(existing_token["token_secret_hash"]) != secret_hash:
                    raise ValueError("TOKEN_CONFLICT")
            else:
                conn.execute(
                    """
                    INSERT INTO enrollment_tokens(
                        token_id, token_secret_hash, mode, status, expires_at, max_uses, used_count,
                        reason_code, reason, idempotency_key, request_hash, metadata_json,
                        created_by_user_id, created_at, updated_at, last_used_at, revoked_at, revoked_by_user_id
                    )
                    VALUES(?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                    """,
                    (
                        token_id,
                        secret_hash,
                        mode,
                        "ACTIVE" if datetime.fromisoformat(expires_at) > utcnow() else "EXPIRED",
                        expires_at,
                        max_uses,
                        reason_code,
                        reason,
                        f"import:{kit_id}",
                        req_hash,
                        metadata_json,
                        actor_id,
                        now_iso,
                        now_iso,
                    ),
                )
                created_token = True

            existing_kit = conn.execute(
                "SELECT id, bundle_hash FROM offline_enrollment_kits WHERE kit_id = ?",
                (kit_id,),
            ).fetchone()
            if existing_kit:
                if str(existing_kit["bundle_hash"]) != bundle_hash:
                    raise ValueError("KIT_CONFLICT")
            else:
                conn.execute(
                    """
                    INSERT INTO offline_enrollment_kits(
                        kit_id, token_id, bundle_hash, status, metadata_json, created_at, imported_at, created_by_user_id, imported_by_user_id
                    )
                    VALUES(?, ?, ?, 'IMPORTED', ?, ?, ?, NULL, ?)
                    """,
                    (kit_id, token_id, bundle_hash, metadata_json, now_iso, now_iso, actor_id),
                )
                created_kit = True

            item = EnrollmentService._get_token_by_token_id_with_conn(conn, token_id)
            if not item:
                raise ValueError("TOKEN_NOT_FOUND")
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="OFFLINE_ENROLLMENT_KIT_IMPORTED",
                target_type="ENROLLMENT_TOKEN",
                target_id=token_id,
                message="Offline enrollment kit imported",
                metadata={"kit_id": kit_id, "created_token": created_token, "created_kit": created_kit},
            )
            return item, created_token, created_kit

    @staticmethod
    def consume_token_for_enrollment(
        *,
        token_value: str,
        agent_name: str,
        hostname: str,
        source: str,
    ) -> dict[str, Any]:
        token_id, secret = EnrollmentService._parse_token_value(token_value)
        secret_hash = EnrollmentService._secret_hash(secret)
        now_iso = utcnow().isoformat()

        with get_db() as conn:
            EnrollmentService._touch_expired_tokens_with_conn(conn)
            row = conn.execute(
                "SELECT * FROM enrollment_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if not row:
                raise ValueError("TOKEN_INVALID")
            if str(row["token_secret_hash"]) != secret_hash:
                raise ValueError("TOKEN_INVALID")
            status = str(row["status"])
            if status == "REVOKED":
                raise ValueError("TOKEN_REVOKED")
            if status == "EXPIRED":
                raise ValueError("TOKEN_EXPIRED")
            if status == "CONSUMED":
                raise ValueError("TOKEN_CONSUMED")

            used_count = int(row["used_count"] or 0)
            max_uses = int(row["max_uses"] or 0)
            if used_count >= max_uses:
                conn.execute(
                    "UPDATE enrollment_tokens SET status = 'CONSUMED', updated_at = ? WHERE token_id = ?",
                    (now_iso, token_id),
                )
                raise ValueError("TOKEN_CONSUMED")

            next_used = used_count + 1
            next_status = "CONSUMED" if next_used >= max_uses else "ACTIVE"
            conn.execute(
                """
                UPDATE enrollment_tokens
                SET used_count = ?, status = ?, last_used_at = ?, updated_at = ?
                WHERE token_id = ?
                """,
                (next_used, next_status, now_iso, now_iso, token_id),
            )
            conn.execute(
                """
                INSERT INTO enrollment_token_uses(token_id, agent_id, source, hostname, agent_name, used_at, details_json)
                VALUES(?, NULL, ?, ?, ?, ?, ?)
                """,
                (token_id, source, hostname, agent_name, now_iso, json.dumps({"remaining_uses": max_uses - next_used})),
            )
            AuditService.log(
                conn,
                actor_type="AGENT",
                action="ENROLLMENT_TOKEN_CONSUMED",
                target_type="ENROLLMENT_TOKEN",
                target_id=token_id,
                message="Enrollment token consumed",
                metadata={"used_count": next_used, "max_uses": max_uses, "source": source},
            )
            return EnrollmentService._row_to_token(row, override={"used_count": next_used, "status": next_status, "last_used_at": now_iso})

    @staticmethod
    def _touch_expired_tokens_with_conn(conn) -> None:
        conn.execute(
            """
            UPDATE enrollment_tokens
            SET status = 'EXPIRED', updated_at = ?
            WHERE status = 'ACTIVE' AND expires_at <= ?
            """,
            (utcnow().isoformat(), utcnow().isoformat()),
        )

    @staticmethod
    def _get_token_by_id_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT e.*, u.username AS created_by_username, ru.username AS revoked_by_username
            FROM enrollment_tokens e
            LEFT JOIN users u ON u.id = e.created_by_user_id
            LEFT JOIN users ru ON ru.id = e.revoked_by_user_id
            WHERE e.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return EnrollmentService._row_to_token(row)

    @staticmethod
    def _get_token_by_token_id_with_conn(conn, token_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT e.*, u.username AS created_by_username, ru.username AS revoked_by_username
            FROM enrollment_tokens e
            LEFT JOIN users u ON u.id = e.created_by_user_id
            LEFT JOIN users ru ON ru.id = e.revoked_by_user_id
            WHERE e.token_id = ?
            """,
            (token_id,),
        ).fetchone()
        if not row:
            return None
        return EnrollmentService._row_to_token(row)

    @staticmethod
    def _row_to_token(row, override: dict[str, Any] | None = None) -> dict[str, Any]:
        row_map = dict(row)
        if override:
            row_map.update(override)
        max_uses = int(row_map["max_uses"] or 0)
        used_count = int(row_map["used_count"] or 0)
        return {
            "id": int(row_map["id"]),
            "token_id": str(row_map["token_id"]),
            "mode": str(row_map["mode"]),
            "status": str(row_map["status"]),
            "expires_at": row_map["expires_at"],
            "max_uses": max_uses,
            "used_count": used_count,
            "remaining_uses": max(0, max_uses - used_count),
            "reason_code": str(row_map["reason_code"]),
            "reason": str(row_map["reason"]),
            "metadata": json.loads(row_map["metadata_json"] or "{}"),
            "created_by_user_id": int(row_map["created_by_user_id"]),
            "created_by_username": row_map.get("created_by_username"),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
            "last_used_at": row_map["last_used_at"],
            "revoked_at": row_map["revoked_at"],
            "revoked_by_user_id": int(row_map["revoked_by_user_id"]) if row_map["revoked_by_user_id"] is not None else None,
            "revoked_by_username": row_map.get("revoked_by_username"),
        }

    @staticmethod
    def _parse_token_value(token_value: str) -> tuple[str, str]:
        value = token_value.strip()
        if "." not in value or not value.startswith("ectk_"):
            raise ValueError("TOKEN_INVALID")
        token_id_part, secret = value.split(".", 1)
        token_id = token_id_part.replace("ectk_", "", 1).strip()
        if not token_id or not secret:
            raise ValueError("TOKEN_INVALID")
        return token_id, secret

    @staticmethod
    def _secret_hash(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_issue_request_hash(
        *,
        mode: str,
        expires_in_hours: int,
        max_uses: int,
        reason_code: str,
        reason: str,
        metadata_json: str,
    ) -> str:
        payload = {
            "mode": mode,
            "expires_in_hours": expires_in_hours,
            "max_uses": max_uses,
            "reason_code": reason_code,
            "reason": reason,
            "metadata_json": metadata_json,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _build_cli_snippets(*, token_value: str) -> dict[str, str]:
        ps = (
            "$server='https://<SERVER_URL>'\n"
            "$body=@{name='<AGENT_NAME>';hostname=$env:COMPUTERNAME;enrollment_token='"
            + token_value
            + "'} | ConvertTo-Json\n"
            "Invoke-RestMethod -Method Post -Uri \"$server/api/v1/agents/enroll\" -ContentType 'application/json' -Body $body"
        )
        sh = (
            "SERVER_URL=\"https://<SERVER_URL>\"\n"
            "curl -X POST \"$SERVER_URL/api/v1/agents/enroll\" "
            "-H 'Content-Type: application/json' "
            "-d '{\"name\":\"<AGENT_NAME>\",\"hostname\":\"'\"$(hostname)\"'\",\"enrollment_token\":\""
            + token_value
            + "\"}'"
        )
        return {"powershell": ps, "linux": sh}

    @staticmethod
    def _build_offline_kit_bundle(
        *,
        kit_id: str,
        token_value: str,
        mode: str,
        expires_at: str,
        max_uses: int,
        reason_code: str,
        reason: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "kit_version": "1",
            "kit_id": kit_id,
            "exported_at": utcnow().isoformat(),
            "token": {
                "enrollment_token": token_value,
                "mode": mode,
                "expires_at": expires_at,
                "max_uses": max_uses,
                "reason_code": reason_code,
                "reason": reason,
                "metadata": metadata,
            },
        }

    @staticmethod
    def _validate_kit_bundle(bundle: dict[str, Any]) -> tuple[str, str, str, str, int, str, str, dict[str, Any]]:
        try:
            kit_id = str(bundle["kit_id"]).strip()
            token = bundle["token"]
            token_value = str(token["enrollment_token"]).strip()
            mode = str(token["mode"]).strip().upper()
            expires_at = str(token["expires_at"]).strip()
            max_uses = int(token["max_uses"])
            reason_code = str(token["reason_code"]).strip().upper()
            reason = str(token["reason"]).strip()
            metadata = token.get("metadata") or {}
        except Exception as exc:
            raise ValueError("KIT_INVALID") from exc

        if not kit_id:
            raise ValueError("KIT_INVALID")
        if mode not in EnrollmentService.VALID_MODES:
            raise ValueError("INVALID_MODE")
        if reason_code not in EnrollmentService.VALID_REASON_CODES:
            raise ValueError("INVALID_REASON_CODE")
        if max_uses < 1 or max_uses > 1000:
            raise ValueError("INVALID_MAX_USES")
        try:
            _ = datetime.fromisoformat(expires_at).astimezone(timezone.utc)
        except Exception as exc:
            raise ValueError("KIT_INVALID") from exc
        if not isinstance(metadata, dict):
            raise ValueError("KIT_INVALID")
        return kit_id, token_value, mode, expires_at, max_uses, reason_code, reason, metadata
