from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class StateBackupService:
    VALID_SCOPES = {"CONFIG_ONLY", "FULL"}
    MAX_ROWS_PER_TABLE = 10000
    IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

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
    PROTECTED_DELETE_TABLES = {"users", "state_backups", "state_restore_jobs", "audit_log", "schema_version"}

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
    def preview_restore(*, backup_id: str, tables: list[str] | None, allow_deletes: bool) -> dict[str, Any]:
        with get_db() as conn:
            backup, bundle, selected_tables = StateBackupService._resolve_backup_bundle_with_conn(
                conn,
                backup_id=backup_id,
                tables=tables,
            )
            preview = StateBackupService._build_restore_preview_with_conn(
                conn,
                bundle_tables=bundle["tables"],
                selected_tables=selected_tables,
                allow_deletes=allow_deletes,
            )
            return {
                "backup_id": backup["backup_id"],
                "scope": backup["scope"],
                "allow_deletes": bool(allow_deletes),
                "selected_tables": selected_tables,
                "summary": preview["summary"],
                "table_diffs": preview["table_diffs"],
            }

    @staticmethod
    def apply_restore(
        *,
        backup_id: str,
        tables: list[str] | None,
        allow_deletes: bool,
        reason: str,
        idempotency_key: str,
        confirm_apply: bool,
        actor_id: int,
    ) -> tuple[dict[str, Any], bool]:
        if not confirm_apply:
            raise ValueError("INVALID_CONFIRMATION")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")
        normalized_idem = idempotency_key.strip()
        if len(normalized_idem) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        now_iso = utcnow().isoformat()
        restore_id = f"rst_{secrets.token_hex(8)}"
        with get_db() as conn:
            backup, bundle, selected_tables = StateBackupService._resolve_backup_bundle_with_conn(
                conn,
                backup_id=backup_id,
                tables=tables,
            )
            preview = StateBackupService._build_restore_preview_with_conn(
                conn,
                bundle_tables=bundle["tables"],
                selected_tables=selected_tables,
                allow_deletes=allow_deletes,
            )
            request_hash = StateBackupService._build_restore_request_hash(
                backup_id=backup["backup_id"],
                selected_tables=selected_tables,
                allow_deletes=allow_deletes,
                reason=normalized_reason,
            )

            existing = conn.execute(
                "SELECT id, request_hash FROM state_restore_jobs WHERE idempotency_key = ?",
                (normalized_idem,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                result = StateBackupService._get_restore_job_by_id_with_conn(conn, int(existing["id"]))
                if not result:
                    raise ValueError("RESTORE_NOT_FOUND")
                return result, False

            apply_result = StateBackupService._apply_restore_with_conn(
                conn,
                bundle_tables=bundle["tables"],
                preview=preview,
                allow_deletes=allow_deletes,
            )
            result_payload = {
                "backup_id": backup["backup_id"],
                "scope": backup["scope"],
                "allow_deletes": bool(allow_deletes),
                "summary": apply_result["summary"],
                "table_results": apply_result["table_results"],
            }
            conn.execute(
                """
                INSERT INTO state_restore_jobs(
                    restore_id, backup_id, status, reason, allow_deletes, idempotency_key, request_hash,
                    selected_tables_json, result_json, created_by_user_id, created_at, applied_at
                )
                VALUES(?, ?, 'APPLIED', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    restore_id,
                    backup["backup_id"],
                    normalized_reason,
                    1 if allow_deletes else 0,
                    normalized_idem,
                    request_hash,
                    json.dumps(selected_tables, sort_keys=True),
                    json.dumps(result_payload, sort_keys=True),
                    actor_id,
                    now_iso,
                    now_iso,
                ),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="STATE_BACKUP_RESTORE_APPLIED",
                target_type="STATE_RESTORE",
                target_id=restore_id,
                message="State backup restore applied",
                metadata={
                    "backup_id": backup["backup_id"],
                    "allow_deletes": bool(allow_deletes),
                    "changed_rows": apply_result["summary"]["changed_rows"],
                    "selected_tables": selected_tables,
                },
            )
            restore = StateBackupService._get_restore_job_by_restore_id_with_conn(conn, restore_id)
            if not restore:
                raise ValueError("RESTORE_NOT_FOUND")
            return restore, True

    @staticmethod
    def _resolve_backup_bundle_with_conn(conn, *, backup_id: str, tables: list[str] | None) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        backup = StateBackupService._get_backup_by_backup_id_with_conn(conn, backup_id.strip())
        if not backup:
            raise ValueError("BACKUP_NOT_FOUND")
        bundle = backup.get("bundle")
        if not isinstance(bundle, dict):
            raise ValueError("INVALID_BUNDLE")
        bundle_tables = bundle.get("tables")
        if not isinstance(bundle_tables, dict):
            raise ValueError("INVALID_BUNDLE")

        allowed_table_names = set(StateBackupService.CONFIG_TABLES + StateBackupService.FULL_EXTRA_TABLES)
        available_tables: list[str] = []
        for table_name in bundle_tables.keys():
            if not isinstance(table_name, str):
                continue
            normalized = table_name.strip()
            if not StateBackupService._is_safe_ident(normalized):
                continue
            if normalized not in allowed_table_names:
                continue
            available_tables.append(normalized)

        if tables is None:
            selected_tables = available_tables
        else:
            selected_tables = []
            seen: set[str] = set()
            for raw_table in tables:
                normalized = raw_table.strip()
                if not StateBackupService._is_safe_ident(normalized):
                    raise ValueError("INVALID_TABLE_NAME")
                if normalized not in available_tables:
                    raise ValueError("TABLE_NOT_IN_BACKUP")
                if normalized in seen:
                    continue
                seen.add(normalized)
                selected_tables.append(normalized)

        if not selected_tables:
            raise ValueError("NO_TABLES_SELECTED")
        return backup, bundle, selected_tables

    @staticmethod
    def _build_restore_preview_with_conn(conn, *, bundle_tables: dict[str, Any], selected_tables: list[str], allow_deletes: bool) -> dict[str, Any]:
        table_diffs: list[dict[str, Any]] = []
        total_inserts = 0
        total_updates = 0
        total_deletes = 0
        total_changed = 0

        for table_name in selected_tables:
            backup_rows_raw = bundle_tables.get(table_name)
            if not isinstance(backup_rows_raw, list):
                raise ValueError("INVALID_BUNDLE")

            schema_columns = StateBackupService._table_columns(conn, table_name)
            if not schema_columns:
                table_diffs.append({
                    "table": table_name,
                    "mode": "missing_table",
                    "key_columns": [],
                    "current_rows": 0,
                    "backup_rows": len(backup_rows_raw),
                    "to_insert": 0,
                    "to_update": 0,
                    "to_delete": 0,
                    "potential_delete_skipped": 0,
                    "unchanged": 0,
                    "warnings": ["target table does not exist in current database"],
                })
                continue

            key_columns = StateBackupService._table_key_columns(conn, table_name)
            backup_rows = StateBackupService._sanitize_bundle_rows(backup_rows_raw, allowed_columns=schema_columns)
            current_rows = StateBackupService._read_table_rows(conn, table_name=table_name, include_sensitive=True)
            current_count = StateBackupService._table_row_count(conn, table_name)

            to_insert = 0
            to_update = 0
            to_delete = 0
            unchanged = 0
            potential_delete_skipped = 0
            warnings: list[str] = []
            mode = "upsert_by_key"

            if not key_columns:
                mode = "replace_only"
                if allow_deletes and table_name not in StateBackupService.PROTECTED_DELETE_TABLES:
                    to_delete = current_count
                    to_insert = len(backup_rows)
                else:
                    potential_delete_skipped = current_count
                    warnings.append("no key columns; allow_deletes required to restore this table")
            else:
                current_map = StateBackupService._rows_to_keyed_map(current_rows, key_columns)
                backup_map = StateBackupService._rows_to_keyed_map(backup_rows, key_columns)
                comparable_columns = [col for col in schema_columns if col not in key_columns]

                for key in backup_map:
                    if key not in current_map:
                        to_insert += 1
                    else:
                        if StateBackupService._rows_equal(current_map[key], backup_map[key], comparable_columns):
                            unchanged += 1
                        else:
                            to_update += 1

                if allow_deletes and table_name not in StateBackupService.PROTECTED_DELETE_TABLES:
                    to_delete = len([key for key in current_map.keys() if key not in backup_map])
                else:
                    potential_delete_skipped = len([key for key in current_map.keys() if key not in backup_map])
                    if potential_delete_skipped > 0:
                        warnings.append("delete phase skipped (allow_deletes=false or table protected)")

            changed_rows = to_insert + to_update + to_delete
            total_inserts += to_insert
            total_updates += to_update
            total_deletes += to_delete
            total_changed += changed_rows

            table_diffs.append({
                "table": table_name,
                "mode": mode,
                "key_columns": key_columns,
                "current_rows": current_count,
                "backup_rows": len(backup_rows),
                "to_insert": to_insert,
                "to_update": to_update,
                "to_delete": to_delete,
                "potential_delete_skipped": potential_delete_skipped,
                "unchanged": unchanged,
                "warnings": warnings,
            })

        return {
            "summary": {
                "table_count": len(selected_tables),
                "inserts": total_inserts,
                "updates": total_updates,
                "deletes": total_deletes,
                "changed_rows": total_changed,
            },
            "table_diffs": table_diffs,
        }

    @staticmethod
    def _apply_restore_with_conn(conn, *, bundle_tables: dict[str, Any], preview: dict[str, Any], allow_deletes: bool) -> dict[str, Any]:
        table_results: list[dict[str, Any]] = []
        total_inserted = 0
        total_updated = 0
        total_deleted = 0

        for table_diff in preview["table_diffs"]:
            table_name = str(table_diff["table"])
            mode = str(table_diff["mode"])
            if mode == "missing_table":
                table_results.append({"table": table_name, "status": "skipped", "inserted": 0, "updated": 0, "deleted": 0, "warnings": table_diff.get("warnings", [])})
                continue

            schema_columns = StateBackupService._table_columns(conn, table_name)
            backup_rows_raw = bundle_tables.get(table_name)
            backup_rows = StateBackupService._sanitize_bundle_rows(backup_rows_raw if isinstance(backup_rows_raw, list) else [], allowed_columns=schema_columns)
            key_columns = [str(item) for item in table_diff.get("key_columns", []) if isinstance(item, str)]

            inserted = 0
            updated = 0
            deleted = 0
            warnings: list[str] = []

            if mode == "replace_only":
                if allow_deletes and table_name not in StateBackupService.PROTECTED_DELETE_TABLES:
                    conn.execute(f"DELETE FROM {StateBackupService._quote_ident(table_name)}")
                    deleted = int(table_diff.get("current_rows") or 0)
                    for row in backup_rows:
                        if row:
                            StateBackupService._insert_row(conn, table_name=table_name, row=row)
                            inserted += 1
                else:
                    warnings.append("restore skipped for table without key columns")
            else:
                current_rows = StateBackupService._read_table_rows(conn, table_name=table_name, include_sensitive=True)
                current_map = StateBackupService._rows_to_keyed_map(current_rows, key_columns)
                backup_map = StateBackupService._rows_to_keyed_map(backup_rows, key_columns)

                for key, backup_row in backup_map.items():
                    if key not in current_map:
                        StateBackupService._insert_row(conn, table_name=table_name, row=backup_row)
                        inserted += 1
                    else:
                        update_cols = [col for col in backup_row.keys() if col not in key_columns]
                        if update_cols and StateBackupService._update_row(conn, table_name=table_name, key_columns=key_columns, key=key, row=backup_row):
                            updated += 1

                if allow_deletes and table_name not in StateBackupService.PROTECTED_DELETE_TABLES:
                    delete_keys = [key for key in current_map.keys() if key not in backup_map]
                    for key in delete_keys:
                        if StateBackupService._delete_row(conn, table_name=table_name, key_columns=key_columns, key=key):
                            deleted += 1
                else:
                    potential = int(table_diff.get("potential_delete_skipped") or 0)
                    if potential > 0:
                        warnings.append("deletes skipped")

            total_inserted += inserted
            total_updated += updated
            total_deleted += deleted
            table_results.append({"table": table_name, "status": "applied", "inserted": inserted, "updated": updated, "deleted": deleted, "warnings": warnings})

        return {
            "summary": {
                "inserted": total_inserted,
                "updated": total_updated,
                "deleted": total_deleted,
                "changed_rows": total_inserted + total_updated + total_deleted,
            },
            "table_results": table_results,
        }

    @staticmethod
    def _read_table_rows(conn, *, table_name: str, include_sensitive: bool) -> list[dict[str, Any]]:
        if not StateBackupService._is_safe_ident(table_name):
            raise ValueError("INVALID_TABLE_NAME")
        table_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)).fetchone()
        if not table_exists:
            return []
        columns = StateBackupService._table_columns(conn, table_name)
        blocked = StateBackupService.SENSITIVE_COLUMNS.get(table_name, set()) if not include_sensitive else set()
        selected = [col for col in columns if col not in blocked]
        if not selected:
            return []
        select_sql = ", ".join(StateBackupService._quote_ident(col) for col in selected)
        rows = conn.execute(
            f"SELECT {select_sql} FROM {StateBackupService._quote_ident(table_name)} ORDER BY rowid ASC LIMIT ?",
            (StateBackupService.MAX_ROWS_PER_TABLE,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _table_row_count(conn, table_name: str) -> int:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM {StateBackupService._quote_ident(table_name)}").fetchone()
        return int(row["c"] if row else 0)

    @staticmethod
    def _table_columns(conn, table_name: str) -> list[str]:
        rows = conn.execute(f"PRAGMA table_info({StateBackupService._quote_ident(table_name)})").fetchall()
        return [str(row["name"]) for row in rows]

    @staticmethod
    def _table_key_columns(conn, table_name: str) -> list[str]:
        rows = conn.execute(f"PRAGMA table_info({StateBackupService._quote_ident(table_name)})").fetchall()
        keyed = [row for row in rows if int(row["pk"] or 0) > 0]
        keyed.sort(key=lambda row: int(row["pk"]))
        if keyed:
            return [str(row["name"]) for row in keyed]
        for row in rows:
            if str(row["name"]) == "id":
                return ["id"]
        return []

    @staticmethod
    def _sanitize_bundle_rows(rows: list[Any], *, allowed_columns: list[str]) -> list[dict[str, Any]]:
        allowed = set(allowed_columns)
        normalized: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            clean: dict[str, Any] = {}
            for key, value in row.items():
                if isinstance(key, str) and key in allowed:
                    clean[key] = value
            if clean:
                normalized.append(clean)
        return normalized

    @staticmethod
    def _rows_to_keyed_map(rows: list[dict[str, Any]], key_columns: list[str]) -> dict[tuple[Any, ...], dict[str, Any]]:
        out: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            key = tuple(row.get(col) for col in key_columns)
            if any(item is None for item in key):
                continue
            out[key] = row
        return out

    @staticmethod
    def _rows_equal(current_row: dict[str, Any], backup_row: dict[str, Any], compare_columns: list[str]) -> bool:
        return all(current_row.get(col) == backup_row.get(col) for col in compare_columns)

    @staticmethod
    def _insert_row(conn, *, table_name: str, row: dict[str, Any]) -> None:
        columns = [col for col in row.keys() if StateBackupService._is_safe_ident(col)]
        if not columns:
            return
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {StateBackupService._quote_ident(table_name)} "
            f"({', '.join(StateBackupService._quote_ident(col) for col in columns)}) VALUES ({placeholders})"
        )
        conn.execute(sql, tuple(row[col] for col in columns))

    @staticmethod
    def _update_row(conn, *, table_name: str, key_columns: list[str], key: tuple[Any, ...], row: dict[str, Any]) -> bool:
        update_cols = [col for col in row.keys() if col not in key_columns and StateBackupService._is_safe_ident(col)]
        if not update_cols:
            return False
        set_sql = ", ".join(f"{StateBackupService._quote_ident(col)} = ?" for col in update_cols)
        where_sql = " AND ".join(f"{StateBackupService._quote_ident(col)} = ?" for col in key_columns)
        sql = f"UPDATE {StateBackupService._quote_ident(table_name)} SET {set_sql} WHERE {where_sql}"
        params = tuple(row[col] for col in update_cols) + tuple(key)
        conn.execute(sql, params)
        return True

    @staticmethod
    def _delete_row(conn, *, table_name: str, key_columns: list[str], key: tuple[Any, ...]) -> bool:
        where_sql = " AND ".join(f"{StateBackupService._quote_ident(col)} = ?" for col in key_columns)
        sql = f"DELETE FROM {StateBackupService._quote_ident(table_name)} WHERE {where_sql}"
        conn.execute(sql, tuple(key))
        return True

    @staticmethod
    def _build_restore_request_hash(*, backup_id: str, selected_tables: list[str], allow_deletes: bool, reason: str) -> str:
        payload = {
            "backup_id": backup_id,
            "selected_tables": selected_tables,
            "allow_deletes": bool(allow_deletes),
            "reason": reason,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

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
    def _get_restore_job_by_id_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                r.*,
                u.username AS created_by_username
            FROM state_restore_jobs r
            LEFT JOIN users u ON u.id = r.created_by_user_id
            WHERE r.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return StateBackupService._row_to_restore_job(row)

    @staticmethod
    def _get_restore_job_by_restore_id_with_conn(conn, restore_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                r.*,
                u.username AS created_by_username
            FROM state_restore_jobs r
            LEFT JOIN users u ON u.id = r.created_by_user_id
            WHERE r.restore_id = ?
            """,
            (restore_id,),
        ).fetchone()
        if not row:
            return None
        return StateBackupService._row_to_restore_job(row)

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

    @staticmethod
    def _row_to_restore_job(row) -> dict[str, Any]:
        row_map = dict(row)
        try:
            selected_tables = json.loads(str(row_map.get("selected_tables_json") or "[]"))
            if not isinstance(selected_tables, list):
                selected_tables = []
        except Exception:
            selected_tables = []
        try:
            result = json.loads(str(row_map.get("result_json") or "{}"))
            if not isinstance(result, dict):
                result = {}
        except Exception:
            result = {}
        return {
            "id": int(row_map["id"]),
            "restore_id": str(row_map["restore_id"]),
            "backup_id": str(row_map["backup_id"]),
            "status": str(row_map["status"]),
            "reason": str(row_map["reason"]),
            "allow_deletes": bool(row_map["allow_deletes"]),
            "selected_tables": selected_tables,
            "result": result,
            "created_by_user_id": int(row_map["created_by_user_id"]),
            "created_by_username": row_map.get("created_by_username"),
            "created_at": row_map["created_at"],
            "applied_at": row_map.get("applied_at"),
        }

    @staticmethod
    def _is_safe_ident(value: str) -> bool:
        return bool(StateBackupService.IDENT_RE.fullmatch(value or ""))

    @staticmethod
    def _quote_ident(value: str) -> str:
        if not StateBackupService._is_safe_ident(value):
            raise ValueError("INVALID_TABLE_NAME")
        return f'"{value}"'
