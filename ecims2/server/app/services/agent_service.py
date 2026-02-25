from __future__ import annotations

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
                INSERT INTO agents(name, hostname, token, registered_at, last_seen, status)
                VALUES(?, ?, ?, ?, ?, ?)
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
                    }
                )
            return result

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
