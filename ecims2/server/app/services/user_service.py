from __future__ import annotations

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
    def get_by_username(username: str) -> dict | None:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active, created_at
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
                SELECT id, username, password_hash, role, is_active, created_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return UserService._row_to_user(row)

    @staticmethod
    def create_user(username: str, password: str, role: UserRole, *, actor_id: int | None = None) -> int:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users(username, password_hash, role, is_active, created_at)
                VALUES(?, ?, ?, 1, ?)
                """,
                (username.strip(), hash_password(password), role.value, now_iso),
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
                metadata={"username": username.strip(), "role": role.value},
            )
            return user_id

    @staticmethod
    def verify_credentials(username: str, password: str) -> dict | None:
        user = UserService.get_by_username(username)
        if not user or not user["is_active"]:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        return user

    @staticmethod
    def update_role(user_id: int, role: UserRole, *, actor_id: int | None = None) -> bool:
        with get_db() as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role.value, user_id))
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="ROLE_CHANGE",
                target_type="USER",
                target_id=user_id,
                message="User role updated",
                metadata={"role": role.value},
            )
            return True

    @staticmethod
    def ensure_bootstrap_admin() -> bool:
        if UserService.count_users() > 0:
            return False
        UserService.create_user("admin", "admin123", UserRole.ADMIN)
        return True

    @staticmethod
    def _row_to_user(row) -> dict:
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }
