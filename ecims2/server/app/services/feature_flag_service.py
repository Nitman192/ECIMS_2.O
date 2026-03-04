from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.database import get_db
from app.services.agent_command_service import AgentCommandService
from app.services.audit_service import AuditService
from app.services.device_control_state_service import DeviceControlStateService
from app.utils.time import utcnow


class FeatureFlagService:
    BUILTIN_KILL_SWITCH_KEY = "device_kill_switch"
    _VALID_SCOPES = {"GLOBAL", "USER", "AGENT"}
    _VALID_RISK_LEVELS = {"LOW", "HIGH"}
    _VALID_REASON_CODES = {
        "SECURITY_INCIDENT",
        "EMERGENCY_MITIGATION",
        "POLICY_CHANGE",
        "ROLLBACK",
        "MAINTENANCE",
        "COMPLIANCE",
        "TESTING",
        "LEGACY_API",
    }
    _RESERVED_KEYS = {BUILTIN_KILL_SWITCH_KEY}

    @staticmethod
    def ensure_builtin_flags() -> None:
        kill_switch_enabled = DeviceControlStateService.get_kill_switch()
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, is_enabled
                FROM feature_flags
                WHERE key = ? AND scope = 'GLOBAL' AND scope_target = ''
                LIMIT 1
                """,
                (FeatureFlagService.BUILTIN_KILL_SWITCH_KEY,),
            ).fetchone()

            if not row:
                conn.execute(
                    """
                    INSERT INTO feature_flags(
                        key, description, scope, scope_target, is_enabled, risk_level, is_kill_switch,
                        created_by_user_id, updated_by_user_id, created_at, updated_at
                    )
                    VALUES(?, ?, 'GLOBAL', '', ?, 'HIGH', 1, NULL, NULL, ?, ?)
                    """,
                    (
                        FeatureFlagService.BUILTIN_KILL_SWITCH_KEY,
                        "Emergency endpoint containment kill switch",
                        1 if kill_switch_enabled else 0,
                        now_iso,
                        now_iso,
                    ),
                )
                return

            if bool(row["is_enabled"]) != bool(kill_switch_enabled):
                conn.execute(
                    """
                    UPDATE feature_flags
                    SET is_enabled = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (1 if kill_switch_enabled else 0, now_iso, int(row["id"])),
                )

    @staticmethod
    def list_flags(
        *,
        query: str | None = None,
        scope: str | None = None,
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        FeatureFlagService.ensure_builtin_flags()

        where = ["1 = 1"]
        params: list[Any] = []

        if scope:
            normalized_scope = scope.strip().upper()
            if normalized_scope != "ALL":
                if normalized_scope not in FeatureFlagService._VALID_SCOPES:
                    raise ValueError("INVALID_SCOPE")
                where.append("scope = ?")
                params.append(normalized_scope)

        if state:
            normalized_state = state.strip().lower()
            if normalized_state == "on":
                where.append("is_enabled = 1")
            elif normalized_state == "off":
                where.append("is_enabled = 0")
            elif normalized_state != "all":
                raise ValueError("INVALID_STATE")

        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            where.append("(lower(key) LIKE ? OR lower(description) LIKE ? OR lower(scope_target) LIKE ?)")
            params.extend([term, term, term])

        where_sql = " AND ".join(where)
        with get_db() as conn:
            rows = conn.execute(
                f"""
                SELECT id, key, description, scope, scope_target, is_enabled, risk_level, is_kill_switch,
                       created_by_user_id, updated_by_user_id, created_at, updated_at
                FROM feature_flags
                WHERE {where_sql}
                ORDER BY is_kill_switch DESC, key ASC, scope ASC, scope_target ASC
                """,
                tuple(params),
            ).fetchall()
        return [FeatureFlagService._row_to_flag(row) for row in rows]

    @staticmethod
    def get_flag(flag_id: int) -> dict[str, Any] | None:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, key, description, scope, scope_target, is_enabled, risk_level, is_kill_switch,
                       created_by_user_id, updated_by_user_id, created_at, updated_at
                FROM feature_flags
                WHERE id = ?
                """,
                (flag_id,),
            ).fetchone()
            if not row:
                return None
            return FeatureFlagService._row_to_flag(row)

    @staticmethod
    def create_flag(
        *,
        key: str,
        description: str,
        scope: str,
        scope_target: str | None,
        is_enabled: bool,
        risk_level: str,
        reason_code: str,
        reason: str,
        confirm_risky: bool,
        actor_id: int,
    ) -> dict[str, Any]:
        FeatureFlagService.ensure_builtin_flags()

        normalized_scope = FeatureFlagService._normalize_scope(scope)
        normalized_risk = FeatureFlagService._normalize_risk_level(risk_level)
        normalized_scope_target = FeatureFlagService._normalize_scope_target(normalized_scope, scope_target)
        normalized_reason_code = FeatureFlagService._normalize_reason_code(reason_code)
        normalized_key = key.strip().lower()

        if normalized_key in FeatureFlagService._RESERVED_KEYS:
            raise ValueError("FLAG_KEY_RESERVED")

        if normalized_risk == "HIGH" and bool(is_enabled) and not bool(confirm_risky):
            raise ValueError("RISK_CONFIRMATION_REQUIRED")

        now_iso = utcnow().isoformat()
        try:
            with get_db() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO feature_flags(
                        key, description, scope, scope_target, is_enabled, risk_level, is_kill_switch,
                        created_by_user_id, updated_by_user_id, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                    """,
                    (
                        normalized_key,
                        description.strip(),
                        normalized_scope,
                        normalized_scope_target,
                        1 if is_enabled else 0,
                        normalized_risk,
                        actor_id,
                        actor_id,
                        now_iso,
                        now_iso,
                    ),
                )
                flag_id = int(cursor.lastrowid)
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="FEATURE_FLAG_CREATED",
                    target_type="FEATURE_FLAG",
                    target_id=flag_id,
                    message="Feature flag created",
                    metadata={
                        "key": normalized_key,
                        "scope": normalized_scope,
                        "scope_target": normalized_scope_target or None,
                        "is_enabled": bool(is_enabled),
                        "risk_level": normalized_risk,
                        "reason_code": normalized_reason_code,
                        "reason": reason.strip(),
                    },
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("FLAG_ALREADY_EXISTS") from exc

        created = FeatureFlagService.get_flag(flag_id)
        if not created:
            raise ValueError("FLAG_CREATE_FAILED")
        return created

    @staticmethod
    def set_flag_state(
        *,
        flag_id: int,
        enabled: bool,
        reason_code: str,
        reason: str,
        confirm_risky: bool,
        actor_id: int,
        source: str = "ADMIN_FEATURES",
    ) -> dict[str, Any] | None:
        FeatureFlagService.ensure_builtin_flags()
        normalized_reason_code = FeatureFlagService._normalize_reason_code(reason_code)
        next_enabled = bool(enabled)
        should_broadcast_enforce = False

        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, key, scope, scope_target, is_enabled, risk_level, is_kill_switch
                FROM feature_flags
                WHERE id = ?
                """,
                (flag_id,),
            ).fetchone()
            if not row:
                return None

            current_enabled = bool(row["is_enabled"])
            is_kill_switch = bool(row["is_kill_switch"])
            if str(row["risk_level"]) == "HIGH" and current_enabled != next_enabled and not bool(confirm_risky):
                raise ValueError("RISK_CONFIRMATION_REQUIRED")

            changed = current_enabled != next_enabled
            now_iso = utcnow().isoformat()
            if changed:
                conn.execute(
                    """
                    UPDATE feature_flags
                    SET is_enabled = ?, updated_at = ?, updated_by_user_id = ?
                    WHERE id = ?
                    """,
                    (1 if next_enabled else 0, now_iso, actor_id, flag_id),
                )

            if is_kill_switch:
                conn.execute(
                    """
                    INSERT INTO device_control_state(key, value_json)
                    VALUES('device_kill_switch', ?)
                    ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                    """,
                    (json.dumps({"enabled": next_enabled}),),
                )

            action = (
                "FEATURE_FLAG_ENABLED"
                if changed and next_enabled
                else "FEATURE_FLAG_DISABLED"
                if changed and not next_enabled
                else "FEATURE_FLAG_STATE_NOOP"
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action=action,
                target_type="FEATURE_FLAG",
                target_id=flag_id,
                message="Feature flag state updated",
                metadata={
                    "key": row["key"],
                    "scope": row["scope"],
                    "scope_target": row["scope_target"] or None,
                    "previous_enabled": current_enabled,
                    "new_enabled": next_enabled,
                    "changed": changed,
                    "reason_code": normalized_reason_code,
                    "reason": reason.strip(),
                    "source": source,
                },
            )
            if is_kill_switch:
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="DEVICE_KILL_SWITCH_SET",
                    target_type="DEVICE_CONTROL",
                    target_id="kill-switch",
                    message="Device kill-switch updated",
                    metadata={
                        "enabled": next_enabled,
                        "changed": changed,
                        "reason_code": normalized_reason_code,
                        "reason": reason.strip(),
                        "source": source,
                    },
                )

            should_broadcast_enforce = is_kill_switch and changed and next_enabled

        if should_broadcast_enforce:
            with get_db() as conn:
                agents = conn.execute("SELECT id FROM agents").fetchall()
            for agent in agents:
                AgentCommandService.enqueue(
                    int(agent["id"]),
                    "DEVICE_FORCE_OBSERVE",
                    {"reason": reason.strip(), "reason_code": normalized_reason_code, "source": source},
                )

        return FeatureFlagService.get_flag(flag_id)

    @staticmethod
    def set_builtin_kill_switch(
        *,
        enabled: bool,
        reason: str,
        actor_id: int,
        reason_code: str = "LEGACY_API",
        confirm_risky: bool = True,
        source: str = "LEGACY_DEVICE_API",
    ) -> dict[str, Any]:
        FeatureFlagService.ensure_builtin_flags()
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM feature_flags
                WHERE key = ? AND scope = 'GLOBAL' AND scope_target = ''
                LIMIT 1
                """,
                (FeatureFlagService.BUILTIN_KILL_SWITCH_KEY,),
            ).fetchone()
            if not row:
                raise ValueError("KILL_SWITCH_FLAG_MISSING")
            flag_id = int(row["id"])

        result = FeatureFlagService.set_flag_state(
            flag_id=flag_id,
            enabled=enabled,
            reason_code=reason_code,
            reason=reason,
            confirm_risky=confirm_risky,
            actor_id=actor_id,
            source=source,
        )
        if not result:
            raise ValueError("KILL_SWITCH_FLAG_MISSING")
        return result

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        normalized = scope.strip().upper()
        if normalized not in FeatureFlagService._VALID_SCOPES:
            raise ValueError("INVALID_SCOPE")
        return normalized

    @staticmethod
    def _normalize_scope_target(scope: str, scope_target: str | None) -> str:
        if scope == "GLOBAL":
            return ""
        normalized_target = (scope_target or "").strip()
        if not normalized_target:
            raise ValueError("INVALID_SCOPE_TARGET")
        return normalized_target

    @staticmethod
    def _normalize_risk_level(risk_level: str) -> str:
        normalized = risk_level.strip().upper()
        if normalized not in FeatureFlagService._VALID_RISK_LEVELS:
            raise ValueError("INVALID_RISK_LEVEL")
        return normalized

    @staticmethod
    def _normalize_reason_code(reason_code: str) -> str:
        normalized = reason_code.strip().upper()
        if normalized not in FeatureFlagService._VALID_REASON_CODES:
            raise ValueError("INVALID_REASON_CODE")
        return normalized

    @staticmethod
    def _row_to_flag(row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "key": str(row["key"]),
            "description": str(row["description"] or ""),
            "scope": str(row["scope"]),
            "scope_target": str(row["scope_target"]) if row["scope_target"] else None,
            "enabled": bool(row["is_enabled"]),
            "risk_level": str(row["risk_level"]),
            "is_kill_switch": bool(row["is_kill_switch"]),
            "created_by_user_id": int(row["created_by_user_id"]) if row["created_by_user_id"] is not None else None,
            "updated_by_user_id": int(row["updated_by_user_id"]) if row["updated_by_user_id"] is not None else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
