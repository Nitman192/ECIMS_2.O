from __future__ import annotations

import hashlib
import sqlite3

from app.db.database import get_db
from app.models.user import UserRole
from app.security.auth import hash_password, verify_password
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class UserService:
    @staticmethod
    def count_users() -> int:
        with get_db() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
            return int(row["c"] if row else 0)

    @staticmethod
    def count_active_admins(*, exclude_user_id: int | None = None) -> int:
        with get_db() as conn:
            if exclude_user_id is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM users WHERE role = ? AND is_active = 1",
                    (UserRole.ADMIN.value,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM users WHERE role = ? AND is_active = 1 AND id != ?",
                    (UserRole.ADMIN.value, exclude_user_id),
                ).fetchone()
            return int(row["c"] if row else 0)

    @staticmethod
    def list_users(*, include_inactive: bool = True) -> list[dict]:
        with get_db() as conn:
            where_sql = "" if include_inactive else "WHERE is_active = 1"
            rows = conn.execute(
                f"""
                SELECT id, username, password_hash, role, is_active, must_reset_password, created_at, updated_at, last_login_at
                FROM users
                {where_sql}
                ORDER BY id ASC
                """
            ).fetchall()
            return [UserService._row_to_user(row) for row in rows]

    @staticmethod
    def get_by_username(username: str) -> dict | None:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active, must_reset_password, created_at, updated_at, last_login_at
                FROM users
                WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()
            if not row:
                return None
            return UserService._row_to_user(row)

    @staticmethod
    def get_by_id(user_id: int) -> dict | None:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active, must_reset_password, created_at, updated_at, last_login_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return UserService._row_to_user(row)

    @staticmethod
    def create_user(
        username: str,
        password: str,
        role: UserRole,
        *,
        actor_id: int | None = None,
        must_reset_password: bool = False,
        is_active: bool = True,
    ) -> int:
        now_iso = utcnow().isoformat()
        normalized_username = username.strip()
        try:
            with get_db() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users(username, password_hash, role, is_active, must_reset_password, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_username,
                        hash_password(password),
                        role.value,
                        1 if is_active else 0,
                        1 if must_reset_password else 0,
                        now_iso,
                        now_iso,
                    ),
                )
                user_id = int(cursor.lastrowid)
                AuditService.log(
                    conn,
                    actor_type="ADMIN" if actor_id else "SYSTEM",
                    actor_id=actor_id,
                    action="USER_CREATED",
                    target_type="USER",
                    target_id=user_id,
                    message="User account created",
                    metadata={
                        "username": normalized_username,
                        "role": role.value,
                        "is_active": bool(is_active),
                        "must_reset_password": bool(must_reset_password),
                    },
                )
                return user_id
        except sqlite3.IntegrityError as exc:
            raise ValueError("USERNAME_ALREADY_EXISTS") from exc

    @staticmethod
    def verify_credentials(username: str, password: str) -> dict | None:
        user = UserService.get_by_username(username)
        if not user or not user["is_active"]:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    @staticmethod
    def mark_login_success(user_id: int) -> None:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now_iso, now_iso, user_id),
            )

    @staticmethod
    def update_role(user_id: int, role: UserRole, *, actor_id: int | None = None, reason: str = "") -> bool:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            row = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            old_role = str(row["role"])
            conn.execute(
                "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                (role.value, now_iso, user_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="USER_ROLE_UPDATED",
                target_type="USER",
                target_id=user_id,
                message="User role updated",
                metadata={"old_role": old_role, "new_role": role.value, "reason": reason},
            )
            return True

    @staticmethod
    def set_active(user_id: int, *, is_active: bool, actor_id: int | None = None, reason: str = "") -> bool:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            row = conn.execute("SELECT id, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            prev = bool(row["is_active"])
            conn.execute(
                "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if is_active else 0, now_iso, user_id),
            )
            action = "USER_ENABLED" if is_active else "USER_DISABLED"
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action=action,
                target_type="USER",
                target_id=user_id,
                message="User active state changed",
                metadata={"previous_is_active": prev, "new_is_active": bool(is_active), "reason": reason},
            )
            return True

    @staticmethod
    def reset_password(
        user_id: int,
        *,
        new_password: str,
        must_reset_password: bool,
        actor_id: int | None = None,
        reason: str = "",
    ) -> bool:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, must_reset_password = ?, updated_at = ?
                WHERE id = ?
                """,
                (hash_password(new_password), 1 if must_reset_password else 0, now_iso, user_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="USER_PASSWORD_RESET_BY_ADMIN",
                target_type="USER",
                target_id=user_id,
                message="User password reset by admin",
                metadata={"must_reset_password": bool(must_reset_password), "reason": reason},
            )
            return True

    @staticmethod
    def delete_user(user_id: int, *, actor_id: int | None = None, reason: str = "") -> bool:
        try:
            with get_db() as conn:
                row = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
                if not row:
                    return False
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                AuditService.log(
                    conn,
                    actor_type="ADMIN",
                    actor_id=actor_id,
                    action="USER_DELETED",
                    target_type="USER",
                    target_id=user_id,
                    message="User deleted",
                    metadata={"username": row["username"], "role": row["role"], "reason": reason},
                )
                return True
        except sqlite3.IntegrityError as exc:
            raise ValueError("USER_DELETE_CONFLICT") from exc

    @staticmethod
    def change_own_password(user_id: int, *, current_password: str, new_password: str) -> None:
        user = UserService.get_by_id(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        if not verify_password(current_password, user["password_hash"]):
            raise ValueError("INVALID_CURRENT_PASSWORD")

        now_iso = utcnow().isoformat()
        with get_db() as conn:
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, must_reset_password = 0, updated_at = ?
                WHERE id = ?
                """,
                (hash_password(new_password), now_iso, user_id),
            )
            AuditService.log(
                conn,
                actor_type="USER",
                actor_id=user_id,
                action="USER_PASSWORD_CHANGED",
                target_type="USER",
                target_id=user_id,
                message="User changed own password",
                metadata={},
            )

    @staticmethod
    def ensure_bootstrap_admin_dev() -> bool:
        if UserService.count_users() > 0:
            return False
        UserService.create_user("admin", "admin123", UserRole.ADMIN)
        return True

    @staticmethod
    def bootstrap_admin_with_token(*, expected_token: str, provided_token: str, username: str, password: str) -> bool:
        if UserService.count_users() > 0:
            return False
        if not expected_token or provided_token != expected_token:
            raise ValueError("BOOTSTRAP_TOKEN_INVALID")
        if not username.strip() or len(password) < 12:
            raise ValueError("BOOTSTRAP_CREDENTIALS_INVALID")

        now_iso = utcnow().isoformat()
        token_sha256 = hashlib.sha256(provided_token.encode("utf-8")).hexdigest()
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users(username, password_hash, role, is_active, must_reset_password, created_at, updated_at)
                VALUES(?, ?, ?, 1, 0, ?, ?)
                """,
                (username.strip(), hash_password(password), UserRole.ADMIN.value, now_iso, now_iso),
            )
            user_id = int(cursor.lastrowid)
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="BOOTSTRAP_ADMIN_CREATED",
                target_type="USER",
                target_id=user_id,
                message="Bootstrap admin account created",
                metadata={"username": username.strip(), "token_sha256_prefix": token_sha256[:12]},
            )
        return True

    @staticmethod
    def _row_to_user(row) -> dict:
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "must_reset_password": bool(row["must_reset_password"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_login_at": row["last_login_at"],
        }
