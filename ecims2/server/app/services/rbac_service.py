from __future__ import annotations

from app.db.database import get_db
from app.models.user import UserRole

_ROLE_MATRIX: dict[str, dict[str, object]] = {
    UserRole.ADMIN.value: {
        "scope": "CONTROL_PLANE",
        "permissions": [
            "users.manage",
            "roles.read_matrix",
            "feature_flags.manage",
            "audit.read_export",
            "device_control.manage",
            "ops.remote_actions.manage",
            "ops.schedules.manage",
            "ops.enrollment.manage",
            "ops.evidence.manage",
            "ops.playbooks.manage",
            "ops.change_control.manage",
            "ops.break_glass.manage",
            "ops.state_backups.manage",
            "ai.manage",
        ],
    },
    UserRole.ANALYST.value: {
        "scope": "OPERATIONS",
        "permissions": [
            "dashboard.read",
            "agents.read",
            "alerts.read",
            "security.read",
            "license.read",
            "audit.read",
            "ops.remote_actions.read",
            "ops.schedules.read",
            "ops.enrollment.read",
            "ops.health.read",
            "ops.quarantine.read",
            "ops.evidence.read",
            "ops.playbooks.read",
            "ops.change_control.read",
            "ops.break_glass.read",
            "ops.state_backups.read",
            "ai.read",
        ],
    },
    UserRole.VIEWER.value: {
        "scope": "READ_ONLY",
        "permissions": [
            "dashboard.read",
            "agents.read",
            "alerts.read",
            "security.read",
            "license.read",
            "audit.read",
        ],
    },
}


class RBACService:
    @staticmethod
    def get_role_matrix() -> list[dict]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT
                    role,
                    COUNT(*) AS total_users,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_users,
                    MAX(COALESCE(updated_at, created_at)) AS updated_at
                FROM users
                GROUP BY role
                """
            ).fetchall()

        usage = {
            str(row["role"]): {
                "total_users": int(row["total_users"] or 0),
                "active_users": int(row["active_users"] or 0),
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

        ordered_roles = [UserRole.ADMIN.value, UserRole.ANALYST.value, UserRole.VIEWER.value]
        payload: list[dict] = []
        for role in ordered_roles:
            role_cfg = _ROLE_MATRIX[role]
            permissions = list(role_cfg["permissions"])
            stats = usage.get(role, {})
            payload.append(
                {
                    "role": role,
                    "scope": str(role_cfg["scope"]),
                    "permissions": permissions,
                    "permission_count": len(permissions),
                    "active_users": int(stats.get("active_users", 0)),
                    "total_users": int(stats.get("total_users", 0)),
                    "updated_at": stats.get("updated_at"),
                }
            )
        return payload
