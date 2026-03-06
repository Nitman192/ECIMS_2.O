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
    if "runtime_id" not in columns:
        conn.execute("ALTER TABLE agent_device_status ADD COLUMN runtime_id TEXT")
    if "state_root" not in columns:
        conn.execute("ALTER TABLE agent_device_status ADD COLUMN state_root TEXT")

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
                runtime_id TEXT,
                state_root TEXT,
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
            CREATE TABLE IF NOT EXISTS enrollment_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT NOT NULL UNIQUE,
                token_secret_hash TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('ONLINE', 'OFFLINE')),
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'REVOKED', 'EXPIRED', 'CONSUMED')),
                expires_at TEXT NOT NULL,
                max_uses INTEGER NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                reason_code TEXT NOT NULL,
                reason TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                revoked_at TEXT,
                revoked_by_user_id INTEGER,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (revoked_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_status_expiry ON enrollment_tokens(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_mode_status ON enrollment_tokens(mode, status);
            CREATE TABLE IF NOT EXISTS enrollment_token_uses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT NOT NULL,
                agent_id INTEGER,
                source TEXT NOT NULL,
                hostname TEXT,
                agent_name TEXT,
                used_at TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (token_id) REFERENCES enrollment_tokens(token_id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_enrollment_token_uses_token_time ON enrollment_token_uses(token_id, used_at);
            CREATE TABLE IF NOT EXISTS offline_enrollment_kits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kit_id TEXT NOT NULL UNIQUE,
                token_id TEXT NOT NULL,
                bundle_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('EXPORTED', 'IMPORTED')),
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                imported_at TEXT,
                created_by_user_id INTEGER,
                imported_by_user_id INTEGER,
                FOREIGN KEY (token_id) REFERENCES enrollment_tokens(token_id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (imported_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_offline_kits_token_status ON offline_enrollment_kits(token_id, status);
            CREATE TABLE IF NOT EXISTS evidence_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL UNIQUE,
                object_hash TEXT NOT NULL,
                hash_algorithm TEXT NOT NULL CHECK(hash_algorithm IN ('SHA256')),
                origin_type TEXT NOT NULL CHECK(origin_type IN ('ALERT', 'EVENT', 'AGENT', 'MANUAL', 'FORENSICS_IMPORT')),
                origin_ref TEXT,
                classification TEXT NOT NULL CHECK(classification IN ('INTERNAL', 'CONFIDENTIAL', 'RESTRICTED')),
                status TEXT NOT NULL CHECK(status IN ('SEALED', 'IN_REVIEW', 'RELEASED', 'ARCHIVED')),
                manifest_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                create_idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                chain_version TEXT NOT NULL DEFAULT '1',
                immutability_chain_head TEXT,
                sealed_at TEXT,
                released_at TEXT,
                archived_at TEXT,
                created_by_user_id INTEGER NOT NULL,
                updated_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_objects_status_created ON evidence_objects(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_evidence_objects_origin_status ON evidence_objects(origin_type, status);
            CREATE INDEX IF NOT EXISTS idx_evidence_objects_hash ON evidence_objects(object_hash);
            CREATE TABLE IF NOT EXISTS evidence_custody_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                sequence_no INTEGER NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN (
                    'CREATED',
                    'REVIEW_STARTED',
                    'RESEALED',
                    'RELEASED',
                    'ARCHIVED',
                    'NOTE_ADDED',
                    'TRANSFERRED',
                    'EXPORT_COMPLETED'
                )),
                actor_user_id INTEGER,
                actor_role TEXT NOT NULL,
                reason TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                prev_event_hash TEXT,
                event_hash TEXT NOT NULL UNIQUE,
                event_ts TEXT NOT NULL,
                FOREIGN KEY (evidence_id) REFERENCES evidence_objects(evidence_id) ON DELETE CASCADE,
                FOREIGN KEY (actor_user_id) REFERENCES users(id),
                UNIQUE(evidence_id, sequence_no)
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_custody_events_evidence_seq ON evidence_custody_events(evidence_id, sequence_no);
            CREATE INDEX IF NOT EXISTS idx_evidence_custody_events_ts ON evidence_custody_events(event_ts);
            CREATE TABLE IF NOT EXISTS playbooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playbook_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                trigger_type TEXT NOT NULL CHECK(trigger_type IN ('MANUAL', 'ALERT_MATCH', 'AGENT_HEALTH', 'SCHEDULED')),
                action TEXT NOT NULL CHECK(action IN ('shutdown', 'restart', 'lockdown', 'policy_push')),
                target_agent_ids_json TEXT NOT NULL,
                approval_mode TEXT NOT NULL CHECK(approval_mode IN ('AUTO', 'MANUAL', 'TWO_PERSON')),
                risk_level TEXT NOT NULL CHECK(risk_level IN ('LOW', 'HIGH')),
                reason_code TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'DISABLED')),
                idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_by_user_id INTEGER NOT NULL,
                updated_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_run_at TEXT,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_playbooks_status_updated ON playbooks(status, updated_at);
            CREATE INDEX IF NOT EXISTS idx_playbooks_approval_status ON playbooks(approval_mode, status);
            CREATE TABLE IF NOT EXISTS playbook_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                playbook_id INTEGER NOT NULL,
                requested_by_user_id INTEGER NOT NULL,
                request_reason TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING_APPROVAL', 'PARTIALLY_APPROVED', 'REJECTED', 'DISPATCHED', 'FAILED')),
                first_approver_user_id INTEGER,
                second_approver_user_id INTEGER,
                decision_reason TEXT,
                task_id INTEGER,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                decided_at TEXT,
                dispatched_at TEXT,
                FOREIGN KEY (playbook_id) REFERENCES playbooks(id) ON DELETE CASCADE,
                FOREIGN KEY (requested_by_user_id) REFERENCES users(id),
                FOREIGN KEY (first_approver_user_id) REFERENCES users(id),
                FOREIGN KEY (second_approver_user_id) REFERENCES users(id),
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
            );

            CREATE INDEX IF NOT EXISTS idx_playbook_runs_playbook_created ON playbook_runs(playbook_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_playbook_runs_status_created ON playbook_runs(status, created_at);
            CREATE TABLE IF NOT EXISTS change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE,
                change_type TEXT NOT NULL CHECK(change_type IN ('POLICY', 'FEATURE_FLAG', 'PLAYBOOK', 'SCHEDULE', 'ENROLLMENT_POLICY', 'BREAK_GLASS_POLICY')),
                target_ref TEXT NOT NULL,
                summary TEXT NOT NULL,
                proposed_changes_json TEXT NOT NULL DEFAULT '{}',
                risk_level TEXT NOT NULL CHECK(risk_level IN ('LOW', 'HIGH', 'CRITICAL')),
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'PARTIALLY_APPROVED', 'APPROVED', 'REJECTED', 'CANCELLED')),
                approvals_required INTEGER NOT NULL CHECK(approvals_required IN (1, 2)),
                reason TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                requested_by_user_id INTEGER NOT NULL,
                first_approver_user_id INTEGER,
                second_approver_user_id INTEGER,
                decision_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                decided_at TEXT,
                FOREIGN KEY (requested_by_user_id) REFERENCES users(id),
                FOREIGN KEY (first_approver_user_id) REFERENCES users(id),
                FOREIGN KEY (second_approver_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_change_requests_status_created ON change_requests(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_change_requests_risk_status ON change_requests(risk_level, status);
            CREATE TABLE IF NOT EXISTS break_glass_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                requested_by_user_id INTEGER NOT NULL,
                revoked_by_user_id INTEGER,
                reason TEXT NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('INCIDENT_RESPONSE', 'SYSTEM_RECOVERY', 'FORENSICS', 'OTHER')),
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'EXPIRED', 'REVOKED')),
                duration_minutes INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                ended_at TEXT,
                reauth_method TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                session_secret_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (requested_by_user_id) REFERENCES users(id),
                FOREIGN KEY (revoked_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_break_glass_sessions_status_expires ON break_glass_sessions(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_break_glass_sessions_user_created ON break_glass_sessions(requested_by_user_id, created_at);
            CREATE TABLE IF NOT EXISTS state_backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_id TEXT NOT NULL UNIQUE,
                scope TEXT NOT NULL CHECK(scope IN ('CONFIG_ONLY', 'FULL')),
                include_sensitive INTEGER NOT NULL DEFAULT 0,
                row_count INTEGER NOT NULL DEFAULT 0,
                bundle_hash TEXT NOT NULL,
                bundle_json TEXT NOT NULL,
                created_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_state_backups_scope_created ON state_backups(scope, created_at);
            CREATE TABLE IF NOT EXISTS state_restore_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restore_id TEXT NOT NULL UNIQUE,
                backup_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('APPLIED', 'FAILED')),
                reason TEXT NOT NULL,
                allow_deletes INTEGER NOT NULL DEFAULT 0,
                idempotency_key TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL,
                selected_tables_json TEXT NOT NULL DEFAULT '[]',
                result_json TEXT NOT NULL DEFAULT '{}',
                created_by_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                applied_at TEXT,
                FOREIGN KEY (backup_id) REFERENCES state_backups(backup_id) ON DELETE CASCADE,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_state_restore_jobs_backup_created ON state_restore_jobs(backup_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_state_restore_jobs_status_created ON state_restore_jobs(status, created_at);
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
