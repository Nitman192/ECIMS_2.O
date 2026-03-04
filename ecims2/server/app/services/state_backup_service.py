from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class StateBackupService:
    VALID_SCOPES = {"CONFIG_ONLY", "FULL"}
    MAX_ROWS_PER_TABLE = 10000

    CONFIG_TABLES = [
        "users",
        "feature_flags",
        "maintenance_schedules",
        "playbooks",
        "change_requests",
        "device_control_state",
    ]
    FULL_EXTRA_TABLES = [
        "agents",
        "agent_device_status",
        "enrollment_tokens",
        "offline_enrollment_kits",
        "break_glass_sessions",
        "playbook_runs",
        "evidence_objects",
        "evidence_custody_events",
        "agent_tasks",
        "agent_task_targets",
    ]

    SENSITIVE_COLUMNS = {
        "users": {"password_hash"},
        "agents": {"token"},
        "enrollment_tokens": {"token_secret_hash"},
        "break_glass_sessions": {"session_secret_hash"},
    }

    @staticmethod
    def list_backups(*, page: int, page_size: int, scope_filter: str | None, query: str | None) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if scope_filter and scope_filter.strip().upper() != "ALL":
            normalized_scope = scope_filter.strip().upper()
            if normalized_scope not in StateBackupService.VALID_SCOPES:
                raise ValueError("INVALID_SCOPE")
            where.append("b.scope = ?")
            params.append(normalized_scope)

        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            where.append("(lower(b.backup_id) LIKE ? OR lower(b.bundle_hash) LIKE ? OR lower(u.username) LIKE ?)")
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size
        with get_db() as conn:
            total_row = conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM state_backups b
                LEFT JOIN users u ON u.id = b.created_by_user_id
                {where_sql}
                """,
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT
                    b.*,
                    u.username AS created_by_username
                FROM state_backups b
                LEFT JOIN users u ON u.id = b.created_by_user_id
                {where_sql}
                ORDER BY b.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [StateBackupService._row_to_backup_meta(row) for row in rows]
        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def create_backup(*, scope: str, include_sensitive: bool, actor_id: int) -> dict[str, Any]:
        normalized_scope = scope.strip().upper()
        if normalized_scope not in StateBackupService.VALID_SCOPES:
            raise ValueError("INVALID_SCOPE")

        table_names = list(StateBackupService.CONFIG_TABLES)
        if normalized_scope == "FULL":
            table_names.extend(StateBackupService.FULL_EXTRA_TABLES)

        with get_db() as conn:
            tables_payload: dict[str, list[dict[str, Any]]] = {}
            per_table_counts: dict[str, int] = {}
            total_rows = 0
            for table_name in table_names:
                table_rows = StateBackupService._read_table_rows(
                    conn,
                    table_name=table_name,
                    include_sensitive=include_sensitive,
                )
                tables_payload[table_name] = table_rows
                per_table_counts[table_name] = len(table_rows)
                total_rows += len(table_rows)

            now_iso = utcnow().isoformat()
            bundle = {
                "bundle_version": "1",
                "scope": normalized_scope,
                "include_sensitive": bool(include_sensitive),
                "created_at": now_iso,
                "table_counts": per_table_counts,
                "tables": tables_payload,
            }
            bundle_json = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
            bundle_hash = hashlib.sha256(bundle_json.encode("utf-8")).hexdigest()
            backup_id = f"bkp_{secrets.token_hex(8)}"

            conn.execute(
                """
                INSERT INTO state_backups(
                    backup_id, scope, include_sensitive, row_count, bundle_hash, bundle_json, created_by_user_id, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backup_id,
                    normalized_scope,
                    1 if include_sensitive else 0,
                    total_rows,
                    bundle_hash,
                    bundle_json,
                    actor_id,
                    now_iso,
                ),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="STATE_BACKUP_CREATED",
                target_type="STATE_BACKUP",
                target_id=backup_id,
                message="State backup snapshot created",
                metadata={"scope": normalized_scope, "include_sensitive": bool(include_sensitive), "row_count": total_rows},
            )
            created = StateBackupService._get_backup_by_backup_id_with_conn(conn, backup_id)
            if not created:
                raise ValueError("BACKUP_NOT_FOUND")
            return created

    @staticmethod
    def get_backup(backup_id: str) -> dict[str, Any] | None:
        with get_db() as conn:
            return StateBackupService._get_backup_by_backup_id_with_conn(conn, backup_id)

    @staticmethod
    def _read_table_rows(conn, *, table_name: str, include_sensitive: bool) -> list[dict[str, Any]]:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if not table_exists:
            return []

        columns = [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
        if not columns:
            return []
        blocked = set()
        if not include_sensitive:
            blocked = StateBackupService.SENSITIVE_COLUMNS.get(table_name, set())
        selected_columns = [col for col in columns if col not in blocked]
        if not selected_columns:
            return []
        select_sql = ", ".join(selected_columns)
        rows = conn.execute(
            f"SELECT {select_sql} FROM {table_name} ORDER BY rowid ASC LIMIT ?",
            (StateBackupService.MAX_ROWS_PER_TABLE,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _get_backup_by_backup_id_with_conn(conn, backup_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                b.*,
                u.username AS created_by_username
            FROM state_backups b
            LEFT JOIN users u ON u.id = b.created_by_user_id
            WHERE b.backup_id = ?
            """,
            (backup_id,),
        ).fetchone()
        if not row:
            return None
        return StateBackupService._row_to_backup(row)

    @staticmethod
    def _row_to_backup_meta(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "backup_id": str(row_map["backup_id"]),
            "scope": str(row_map["scope"]),
            "include_sensitive": bool(row_map["include_sensitive"]),
            "row_count": int(row_map["row_count"] or 0),
            "bundle_hash": str(row_map["bundle_hash"]),
            "created_by_user_id": int(row_map["created_by_user_id"]),
            "created_by_username": row_map.get("created_by_username"),
            "created_at": row_map["created_at"],
        }

    @staticmethod
    def _row_to_backup(row) -> dict[str, Any]:
        row_map = dict(row)
        item = StateBackupService._row_to_backup_meta(row_map)
        try:
            bundle = json.loads(str(row_map.get("bundle_json") or "{}"))
            if not isinstance(bundle, dict):
                bundle = {}
        except Exception:
            bundle = {}
        item["bundle"] = bundle
        return item
