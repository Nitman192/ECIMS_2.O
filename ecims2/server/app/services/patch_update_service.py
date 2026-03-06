from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Any

from app.db.database import get_db
from app.utils.time import utcnow

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class PatchUpdateService:
    @staticmethod
    def upload_patch(
        *,
        version: str,
        original_filename: str,
        payload: bytes,
        notes: str,
        actor_id: int,
    ) -> dict[str, Any]:
        safe_version = version.strip()
        if not safe_version:
            raise ValueError("INVALID_VERSION")
        if not payload:
            raise ValueError("EMPTY_FILE")

        patch_id = f"ptu_{uuid.uuid4().hex[:16]}"
        safe_filename = PatchUpdateService._sanitize_filename(original_filename)
        storage_root = PatchUpdateService._storage_root()
        file_path = storage_root / f"{patch_id}_{safe_filename}"
        file_path.write_bytes(payload)

        now_iso = utcnow().isoformat()
        digest = hashlib.sha256(payload).hexdigest()
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO patch_updates(
                    patch_id, version, filename, file_path, sha256, file_size_bytes, status,
                    notes, apply_notes, backup_id, created_by_user_id, applied_by_user_id, created_at, applied_at
                )
                VALUES(?, ?, ?, ?, ?, ?, 'UPLOADED', ?, NULL, NULL, ?, NULL, ?, NULL)
                """,
                (
                    patch_id,
                    safe_version,
                    safe_filename,
                    str(file_path),
                    digest,
                    len(payload),
                    notes.strip(),
                    actor_id,
                    now_iso,
                ),
            )
        item = PatchUpdateService.get_patch(patch_id)
        if not item:
            raise ValueError("PATCH_SAVE_FAILED")
        return item

    @staticmethod
    def list_patches(*, page: int, page_size: int, status_filter: str | None = None, query: str | None = None) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if status_filter:
            normalized = status_filter.strip().upper()
            allowed = {"UPLOADED", "APPLIED", "FAILED", "ROLLED_BACK"}
            if normalized not in allowed:
                raise ValueError("INVALID_STATUS")
            where.append("status = ?")
            params.append(normalized)

        if query:
            q = f"%{query.strip().lower()}%"
            if q != "%%":
                where.append("(lower(patch_id) LIKE ? OR lower(version) LIKE ? OR lower(filename) LIKE ? OR lower(notes) LIKE ?)")
                params.extend([q, q, q, q])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size
        with get_db() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM patch_updates {where_sql}",
                tuple(params),
            ).fetchone()
            rows = conn.execute(
                f"""
                SELECT *
                FROM patch_updates
                {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params + [page_size, offset]),
            ).fetchall()
        total = int((total_row["c"] if total_row else 0) or 0)
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [PatchUpdateService._row_to_item(row) for row in rows],
        }

    @staticmethod
    def get_patch(patch_id: str) -> dict[str, Any] | None:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM patch_updates WHERE patch_id = ?",
                (patch_id,),
            ).fetchone()
        if not row:
            return None
        return PatchUpdateService._row_to_item(row)

    @staticmethod
    def mark_applied(
        *,
        patch_id: str,
        actor_id: int,
        apply_notes: str,
        backup_id: str | None,
    ) -> dict[str, Any] | None:
        with get_db() as conn:
            row = conn.execute("SELECT status FROM patch_updates WHERE patch_id = ?", (patch_id,)).fetchone()
            if not row:
                return None
            now_iso = utcnow().isoformat()
            if str(row["status"]).upper() != "APPLIED":
                conn.execute(
                    """
                    UPDATE patch_updates
                    SET status = 'APPLIED',
                        apply_notes = ?,
                        backup_id = ?,
                        applied_by_user_id = ?,
                        applied_at = ?
                    WHERE patch_id = ?
                    """,
                    (apply_notes.strip(), backup_id, actor_id, now_iso, patch_id),
                )
        return PatchUpdateService.get_patch(patch_id)

    @staticmethod
    def resolve_file_path(patch_id: str) -> tuple[Path, str] | None:
        item = PatchUpdateService.get_patch(patch_id)
        if not item:
            return None
        candidate = Path(str(item["file_path"])).resolve()
        root = PatchUpdateService._storage_root().resolve()
        if root not in candidate.parents:
            raise ValueError("PATCH_PATH_INVALID")
        if not candidate.exists():
            raise ValueError("PATCH_FILE_MISSING")
        return candidate, str(item["filename"])

    @staticmethod
    def _storage_root() -> Path:
        root = Path(__file__).resolve().parents[3]
        path = root / "patch_updates"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        value = Path(filename or "").name.strip()
        if not value:
            value = "patch_update.bin"
        value = _SAFE_FILENAME.sub("_", value)
        return value[:180] or "patch_update.bin"

    @staticmethod
    def _row_to_item(row) -> dict[str, Any]:
        return {
            "patch_id": str(row["patch_id"]),
            "version": str(row["version"]),
            "filename": str(row["filename"]),
            "file_path": str(row["file_path"]),
            "sha256": str(row["sha256"]),
            "file_size_bytes": int(row["file_size_bytes"] or 0),
            "status": str(row["status"]),
            "notes": str(row["notes"] or ""),
            "apply_notes": str(row["apply_notes"] or ""),
            "backup_id": row["backup_id"],
            "created_by_user_id": int(row["created_by_user_id"]),
            "applied_by_user_id": int(row["applied_by_user_id"]) if row["applied_by_user_id"] is not None else None,
            "created_at": str(row["created_at"]),
            "applied_at": str(row["applied_at"]) if row["applied_at"] is not None else None,
        }
