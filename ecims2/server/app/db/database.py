from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.core.config import get_settings


def _get_db_path() -> Path:
    settings = get_settings()
    configured = Path(settings.db_path)
    if configured.is_absolute():
        return configured
    root = Path(__file__).resolve().parents[3]
    return root / configured


def init_db() -> None:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hostname TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                registered_at TEXT NOT NULL,
                last_seen TEXT,
                status TEXT NOT NULL DEFAULT 'UNKNOWN'
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


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
