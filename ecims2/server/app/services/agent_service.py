from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.security import generate_agent_token
from app.utils.time import utcnow


class AgentService:
    @staticmethod
    def register_agent(name: str, hostname: str) -> tuple[int, str]:
        token = generate_agent_token()
        now = utcnow().isoformat()
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agents(name, hostname, token, registered_at, last_seen, status, agent_revoked, revoked_at, revocation_reason)
                VALUES(?, ?, ?, ?, ?, ?, 0, NULL, NULL)
                """,
                (name.strip(), hostname.strip(), token, now, now, "ONLINE"),
            )
            agent_id = int(cursor.lastrowid)
            AuditService.log(
                conn,
                actor_type="AGENT",
                actor_id=agent_id,
                action="AGENT_REGISTERED",
                target_type="AGENT",
                target_id=agent_id,
                message="Agent registered",
                metadata={"name": name.strip(), "hostname": hostname.strip()},
            )
            return agent_id, token

    @staticmethod
    def get_agent(agent_id: int) -> dict | None:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, hostname, agent_revoked, revoked_at, revocation_reason FROM agents WHERE id = ?",
                (agent_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": int(row["id"]),
                "name": row["name"],
                "hostname": row["hostname"],
                "agent_revoked": bool(row["agent_revoked"]),
                "revoked_at": row["revoked_at"],
                "revocation_reason": row["revocation_reason"],
            }

    @staticmethod
    def revoke_agent(agent_id: int, reason: str, actor_id: int | None = None) -> bool:
        now_iso = utcnow().isoformat()
        with get_db() as conn:
            exists = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not exists:
                return False
            conn.execute(
                "UPDATE agents SET agent_revoked = 1, revoked_at = ?, revocation_reason = ? WHERE id = ?",
                (now_iso, reason.strip(), agent_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="AGENT_REVOKED",
                target_type="AGENT",
                target_id=agent_id,
                message="Agent certificate access revoked",
                metadata={"reason": reason.strip()},
            )
            return True

    @staticmethod
    def restore_agent(agent_id: int, actor_id: int | None = None) -> bool:
        with get_db() as conn:
            exists = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not exists:
                return False
            conn.execute(
                "UPDATE agents SET agent_revoked = 0, revoked_at = NULL, revocation_reason = NULL WHERE id = ?",
                (agent_id,),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="AGENT_UNREVOKED",
                target_type="AGENT",
                target_id=agent_id,
                message="Agent certificate access restored",
                metadata={},
            )
            return True

    @staticmethod
    def count_agents() -> int:
        with get_db() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM agents").fetchone()
            return int(row["c"] if row else 0)

    @staticmethod
    def count_revoked_agents() -> int:
        with get_db() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM agents WHERE agent_revoked = 1").fetchone()
            return int(row["c"] if row else 0)

    @staticmethod
    def validate_agent_token(agent_id: int, token: str) -> bool:
        with get_db() as conn:
            row = conn.execute("SELECT token FROM agents WHERE id = ?", (agent_id,)).fetchone()
            return bool(row and row["token"] == token)

    @staticmethod
    def heartbeat(agent_id: int) -> None:
        with get_db() as conn:
            conn.execute(
                "UPDATE agents SET last_seen = ?, status = 'ONLINE' WHERE id = ?",
                (utcnow().isoformat(), agent_id),
            )

    @staticmethod
    def list_agents(offline_threshold_sec: int) -> list[dict]:
        now = utcnow()
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM agents ORDER BY id ASC").fetchall()
            result: list[dict] = []
            for row in rows:
                last_seen = datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None
                status = "ONLINE"
                if not last_seen or (now - last_seen) > timedelta(seconds=offline_threshold_sec):
                    status = "OFFLINE"
                result.append(
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "hostname": row["hostname"],
                        "registered_at": datetime.fromisoformat(row["registered_at"]),
                        "last_seen": last_seen,
                        "status": status,
                        "agent_revoked": bool(row["agent_revoked"]),
                    }
                )
            return result

    @staticmethod
    def get_agent_self_status(agent_id: int) -> dict | None:
        with get_db() as conn:
            agent = conn.execute(
                """
                SELECT
                    id, name, hostname, registered_at, last_seen, status,
                    agent_revoked, revoked_at, revocation_reason, device_mode_override, device_tags
                FROM agents
                WHERE id = ?
                """,
                (agent_id,),
            ).fetchone()
            if not agent:
                return None

            device_status = conn.execute(
                """
                SELECT
                    policy_hash_applied, enforcement_mode, adapter_status, last_reconcile_time,
                    agent_version, runtime_id, state_root, updated_at
                FROM agent_device_status
                WHERE agent_id = ?
                """,
                (agent_id,),
            ).fetchone()

            command_rows = conn.execute(
                """
                SELECT status, COUNT(*) AS c
                FROM agent_commands
                WHERE agent_id = ?
                GROUP BY status
                """,
                (agent_id,),
            ).fetchall()
            command_counts = {str(row["status"]).lower(): int(row["c"]) for row in command_rows}

            pending_rows = conn.execute(
                """
                SELECT id, type, created_at, payload_json
                FROM agent_commands
                WHERE agent_id = ? AND status = 'PENDING'
                ORDER BY id ASC
                LIMIT 10
                """,
                (agent_id,),
            ).fetchall()

            pending_preview = [
                {
                    "id": int(row["id"]),
                    "type": row["type"],
                    "created_at": row["created_at"],
                    "payload": json.loads(row["payload_json"] or "{}"),
                }
                for row in pending_rows
            ]

        return {
            "agent": {
                "id": int(agent["id"]),
                "name": agent["name"],
                "hostname": agent["hostname"],
                "registered_at": agent["registered_at"],
                "last_seen": agent["last_seen"],
                "status": agent["status"],
                "agent_revoked": bool(agent["agent_revoked"]),
                "revoked_at": agent["revoked_at"],
                "revocation_reason": agent["revocation_reason"],
                "device_mode_override": agent["device_mode_override"],
                "device_tags": agent["device_tags"],
            },
            "device_status": (
                {
                    "policy_hash_applied": device_status["policy_hash_applied"],
                    "enforcement_mode": device_status["enforcement_mode"],
                    "adapter_status": device_status["adapter_status"],
                    "last_reconcile_time": device_status["last_reconcile_time"],
                    "agent_version": device_status["agent_version"],
                    "runtime_id": device_status["runtime_id"],
                    "state_root": device_status["state_root"],
                    "updated_at": device_status["updated_at"],
                }
                if device_status
                else None
            ),
            "command_counts": {
                "pending": int(command_counts.get("pending", 0)),
                "applied": int(command_counts.get("applied", 0)),
                "failed": int(command_counts.get("failed", 0)),
            },
            "pending_commands": pending_preview,
            "server_time_utc": utcnow().isoformat(),
        }

    @staticmethod
    def set_device_mode_override(agent_id: int, mode: str | None) -> bool:
        with get_db() as conn:
            row = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE agents SET device_mode_override = ? WHERE id = ?", (mode, agent_id))
            return True

    @staticmethod
    def run_offline_check(offline_threshold_sec: int) -> int:
        now = utcnow()
        cutoff = now - timedelta(seconds=offline_threshold_sec)
        created = 0
        with get_db() as conn:
            rows = conn.execute("SELECT id, name, last_seen FROM agents").fetchall()
            for row in rows:
                last_seen = datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None
                if not last_seen or last_seen < cutoff:
                    conn.execute("UPDATE agents SET status = 'OFFLINE' WHERE id = ?", (row["id"],))
                    existing = conn.execute(
                        """
                        SELECT id FROM alerts
                        WHERE agent_id = ? AND alert_type = 'AGENT_OFFLINE' AND status = 'OPEN'
                        LIMIT 1
                        """,
                        (row["id"],),
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            """
                            INSERT INTO alerts(agent_id, ts, alert_type, severity, file_path,
                                previous_sha256, new_sha256, message, status)
                            VALUES(?, ?, 'AGENT_OFFLINE', 'AMBER', NULL, NULL, NULL, ?, 'OPEN')
                            """,
                            (row["id"], now.isoformat(), f"Agent {row['name']} is offline"),
                        )
                        AuditService.log(
                            conn,
                            actor_type="SYSTEM",
                            action="ALERT_CREATED",
                            target_type="ALERT",
                            target_id=f"AGENT_OFFLINE:{row['id']}",
                            message="Offline alert created",
                            metadata={"agent_id": row["id"]},
                        )
                        created += 1
                else:
                    conn.execute("UPDATE agents SET status = 'ONLINE' WHERE id = ?", (row["id"],))

            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="OFFLINE_CHECK_RUN",
                target_type="SYSTEM",
                target_id="offline-check",
                message="Offline check completed",
                metadata={"created_alerts": created},
            )

        return created
