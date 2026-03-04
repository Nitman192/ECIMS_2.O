from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.core.config import get_settings
from app.core.version import SCHEMA_VERSION
from app.utils.time import utcnow


def _get_db_path() -> Path:
    settings = get_settings()
    configured = Path(settings.db_path)
    if configured.is_absolute():
        return configured
    root = Path(__file__).resolve().parents[3]
    return root / configured


def _ensure_user_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN', 'ANALYST', 'VIEWER')),
            is_active INTEGER NOT NULL DEFAULT 1,
            must_reset_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            last_login_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, is_active)")


def _ensure_user_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "must_reset_password" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN must_reset_password INTEGER NOT NULL DEFAULT 0")
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT")
        conn.execute("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL")
    if "last_login_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")


def _ensure_agent_revocation_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
    if "agent_revoked" not in columns:
        conn.execute("ALTER TABLE agents ADD COLUMN agent_revoked INTEGER NOT NULL DEFAULT 0")
    if "revoked_at" not in columns:
        conn.execute("ALTER TABLE agents ADD COLUMN revoked_at TEXT")
    if "revocation_reason" not in columns:
        conn.execute("ALTER TABLE agents ADD COLUMN revocation_reason TEXT")






def _ensure_agent_device_status_columns(conn: sqlite3.Connection) -> None:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "agent_device_status" not in tables:
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_device_status)").fetchall()}
    if "agent_version" not in columns:
        conn.execute("ALTER TABLE agent_device_status ADD COLUMN agent_version TEXT")

def _ensure_agent_device_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
    if "device_mode_override" not in columns:
        conn.execute("ALTER TABLE agents ADD COLUMN device_mode_override TEXT")
    if "device_tags" not in columns:
        conn.execute("ALTER TABLE agents ADD COLUMN device_tags TEXT")


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_version ORDER BY rowid DESC LIMIT 1").fetchone()
    if not row:
        return 0
    return int(row[0])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("DELETE FROM schema_version")
    conn.execute(
        "INSERT INTO schema_version(version, updated_at) VALUES(?, ?)",
        (version, utcnow().isoformat()),
    )


def _run_schema_migrations(conn: sqlite3.Connection) -> dict[str, int | bool]:
    _ensure_schema_version_table(conn)
    from_version = _get_schema_version(conn)
    if from_version == 0:
        # existing DBs without version tracking are treated as v1 baseline
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        from_version = 1 if "agents" in tables else 0

    if from_version < 1:
        from_version = 1

    # v2 migration is additive and idempotent (handled by init DDL + ensure helpers)
    _set_schema_version(conn, SCHEMA_VERSION)
    return {"from_version": from_version, "to_version": SCHEMA_VERSION, "migrated": from_version != SCHEMA_VERSION}

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Always open/close a fresh sqlite connection.

    Notes:
    - check_same_thread=False improves compatibility with TestClient/threaded execution.
    - explicit close in finally avoids Windows file locking issues in temp dirs.
    """
    conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_db() -> dict[str, int | bool]:
    """
    Initialize DB schema using the same connection lifecycle as get_db()
    to avoid sqlite file locks on Windows during tests.
    """
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hostname TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                registered_at TEXT NOT NULL,
                last_seen TEXT,
                status TEXT NOT NULL DEFAULT 'UNKNOWN',
                agent_revoked INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT,
                revocation_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS baseline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                sha256 TEXT,
                first_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
                UNIQUE(agent_id, file_path)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                event_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                sha256 TEXT,
                details_json TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                file_path TEXT,
                previous_sha256 TEXT,
                new_sha256 TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id INTEGER,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                message TEXT NOT NULL,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS ai_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trained_at TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                window_minutes INTEGER NOT NULL,
                params_json TEXT NOT NULL,
                feature_spec_json TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                training_summary_json TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS device_unblock_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                device_id TEXT NOT NULL,
                vid TEXT NOT NULL,
                pid TEXT NOT NULL,
                serial TEXT,
                justification TEXT NOT NULL,
                requested_by_user_id INTEGER,
                status TEXT NOT NULL DEFAULT 'PENDING',
                approved_by_user_id INTEGER,
                requested_at TEXT NOT NULL,
                approved_at TEXT,
                expires_at TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
                FOREIGN KEY (requested_by_user_id) REFERENCES users(id),
                FOREIGN KEY (approved_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_device_unblock_status ON device_unblock_requests(status, requested_at);




            CREATE TABLE IF NOT EXISTS agent_device_status (
                agent_id INTEGER PRIMARY KEY,
                policy_hash_applied TEXT,
                enforcement_mode TEXT,
                adapter_status TEXT,
                last_reconcile_time TEXT,
                agent_version TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS device_control_state (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS device_allow_tokens (
                token_id TEXT PRIMARY KEY,
                agent_id INTEGER NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                scope_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_device_allow_tokens_agent_status ON device_allow_tokens(agent_id, status, expires_at);
            CREATE TABLE IF NOT EXISTS feature_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL CHECK(scope IN ('GLOBAL', 'USER', 'AGENT')),
                scope_target TEXT NOT NULL DEFAULT '',
                is_enabled INTEGER NOT NULL DEFAULT 0,
                risk_level TEXT NOT NULL DEFAULT 'LOW' CHECK(risk_level IN ('LOW', 'HIGH')),
                is_kill_switch INTEGER NOT NULL DEFAULT 0,
                created_by_user_id INTEGER,
                updated_by_user_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (updated_by_user_id) REFERENCES users(id),
                CHECK(
                    (scope = 'GLOBAL' AND scope_target = '')
                    OR (scope IN ('USER', 'AGENT') AND length(scope_target) > 0)
                ),
                UNIQUE(key, scope, scope_target)
            );

            CREATE INDEX IF NOT EXISTS idx_feature_flags_scope_enabled ON feature_flags(scope, is_enabled);
            CREATE INDEX IF NOT EXISTS idx_feature_flags_key ON feature_flags(key);
            CREATE TABLE IF NOT EXISTS agent_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL,
                applied_at TEXT,
                error TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_agent_commands_pending ON agent_commands(agent_id, status, created_at);
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('shutdown', 'restart', 'lockdown', 'policy_push')),
                reason_code TEXT NOT NULL,
                reason TEXT NOT NULL,
                requested_by_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'SENT', 'ACK', 'DONE', 'FAILED')),
                target_count INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                ack_count INTEGER NOT NULL DEFAULT 0,
                done_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sent_at TEXT,
                completed_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (requested_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_agent_tasks_status_created ON agent_tasks(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_agent_tasks_action_created ON agent_tasks(action, created_at);
            CREATE TABLE IF NOT EXISTS agent_task_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                agent_id INTEGER NOT NULL,
                command_id INTEGER,
                status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'SENT', 'ACK', 'DONE', 'FAILED')),
                ack_applied INTEGER,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sent_at TEXT,
                ack_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
                FOREIGN KEY (command_id) REFERENCES agent_commands(id) ON DELETE SET NULL,
                UNIQUE(task_id, agent_id),
                UNIQUE(command_id)
            );

            CREATE INDEX IF NOT EXISTS idx_agent_task_targets_task_status ON agent_task_targets(task_id, status);
            CREATE INDEX IF NOT EXISTS idx_agent_task_targets_agent_status ON agent_task_targets(agent_id, status);
            CREATE TABLE IF NOT EXISTS maintenance_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_name TEXT NOT NULL,
                timezone TEXT NOT NULL,
                start_time_local TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                recurrence TEXT NOT NULL CHECK(recurrence IN ('DAILY', 'WEEKLY')),
                weekly_days_json TEXT NOT NULL DEFAULT '[]',
                target_agent_ids_json TEXT NOT NULL,
                orchestration_mode TEXT NOT NULL CHECK(orchestration_mode IN ('SAFE_SHUTDOWN_START', 'SHUTDOWN_ONLY', 'RESTART_ONLY', 'POLICY_PUSH_ONLY')),
                status TEXT NOT NULL CHECK(status IN ('DRAFT', 'ACTIVE', 'PAUSED')),
                reason_code TEXT NOT NULL,
                reason TEXT NOT NULL,
                create_idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                next_run_at TEXT,
                last_run_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_by_user_id INTEGER NOT NULL,
                updated_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_status_next ON maintenance_schedules(status, next_run_at);
            CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_timezone_start ON maintenance_schedules(timezone, start_time_local);
            CREATE TABLE IF NOT EXISTS maintenance_schedule_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                run_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('RUNNING', 'DONE', 'FAILED')),
                started_at TEXT NOT NULL,
                finished_at TEXT,
                dispatched_task_ids_json TEXT NOT NULL DEFAULT '[]',
                details_json TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                FOREIGN KEY (schedule_id) REFERENCES maintenance_schedules(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_maintenance_schedule_runs_schedule_started ON maintenance_schedule_runs(schedule_id, started_at);
            CREATE TABLE IF NOT EXISTS ai_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                agent_id INTEGER NOT NULL,
                window_start_ts TEXT NOT NULL,
                window_end_ts TEXT NOT NULL,
                risk_score REAL NOT NULL,
                is_anomaly INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                explanation_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_agents_last_seen ON agents(last_seen);
            CREATE INDEX IF NOT EXISTS idx_baseline_agent_path ON baseline(agent_id, file_path);
            CREATE INDEX IF NOT EXISTS idx_events_agent_ts ON events(agent_id, ts);
            CREATE INDEX IF NOT EXISTS idx_alerts_agent_ts ON alerts(agent_id, ts);
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_type, actor_id);
            CREATE INDEX IF NOT EXISTS idx_ai_scores_agent_ts ON ai_scores(agent_id, ts);
            CREATE INDEX IF NOT EXISTS idx_ai_models_name_trained ON ai_models(model_name, trained_at);
            """
        )
        _ensure_agent_revocation_columns(conn)
        _ensure_agent_device_columns(conn)
        _ensure_user_table(conn)
        _ensure_user_columns(conn)
        _ensure_agent_device_status_columns(conn)
        migration = _run_schema_migrations(conn)
        return migration
