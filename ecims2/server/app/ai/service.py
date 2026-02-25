from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.ai.explain import build_explanation
from app.ai.features import (
    FEATURE_NAMES,
    FEATURE_SPEC_VERSION,
    FeatureRow,
    build_feature_dataset,
    feature_vector,
    iso_utc,
    json_dumps_compact,
    parse_iso,
)
from app.ai.model import load_bundle, save_bundle, score_to_risk, train_bundle
from app.core.config import get_settings
from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


def _artifact_dir() -> Path:
    settings = get_settings()
    root = Path(__file__).resolve().parents[3]
    dir_path = root / getattr(settings, "ai_artifact_dir", "ai_artifacts")
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _resolve_start_end(window_minutes: int, start_ts: str | None, end_ts: str | None) -> tuple[str | None, str | None]:
    if start_ts or end_ts:
        return start_ts, end_ts

    end = utcnow()
    start = end - timedelta(days=7)
    return iso_utc(start), iso_utc(end)


class AIService:
    @staticmethod
    def build_feature_dataset(window_minutes: int, start_ts: str | None, end_ts: str | None) -> list[FeatureRow]:
        return build_feature_dataset(window_minutes, start_ts, end_ts)

    @staticmethod
    def train_model(
        model_name: str = "isolation_forest",
        model_version: str = "1.0",
        window_minutes: int = 60,
        start_ts: str | None = None,
        end_ts: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        start_ts, end_ts = _resolve_start_end(window_minutes, start_ts, end_ts)
        rows = AIService.build_feature_dataset(window_minutes, start_ts, end_ts)
        if not rows:
            raise ValueError("No feature dataset rows available for training")

        X = [feature_vector(r.features) for r in rows]
        bundle = train_bundle(model_name, model_version, X, params)

        trained_at = utcnow().isoformat()
        artifact_name = f"{model_name}_{model_version}_{trained_at.replace(':', '-').replace('+', '_')}.joblib"
        artifact_path = _artifact_dir() / artifact_name
        save_bundle(str(artifact_path), bundle)

        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_models(
                    trained_at, model_name, model_version, window_minutes,
                    params_json, feature_spec_json, artifact_path, training_summary_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trained_at,
                    model_name,
                    model_version,
                    window_minutes,
                    json_dumps_compact(bundle.params),
                    json_dumps_compact({"version": FEATURE_SPEC_VERSION, "features": FEATURE_NAMES}),
                    str(artifact_path),
                    json_dumps_compact(
                        {
                            "rows_used": len(rows),
                            "start_ts": start_ts,
                            "end_ts": end_ts,
                            "score_min": bundle.score_min,
                            "score_max": bundle.score_max,
                            "anomaly_cutoff": bundle.anomaly_cutoff,
                        }
                    ),
                ),
            )
            model_id = int(cursor.lastrowid)

            AuditService.log(
                conn,
                actor_type="ADMIN",
                action="TRAIN_MODEL",
                target_type="AI_MODEL",
                target_id=model_id,
                message="AI model trained",
                metadata={"model_name": model_name, "window_minutes": window_minutes, "rows_used": len(rows)},
            )

        return {
            "model_id": model_id,
            "trained_at": trained_at,
            "rows_used": len(rows),
            "artifact_path": str(artifact_path),
        }

    @staticmethod
    def _load_model_record(model_id: int) -> dict[str, Any]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM ai_models WHERE id = ?", (model_id,)).fetchone()
            if not row:
                raise ValueError(f"Model not found: {model_id}")
            return dict(row)

    @staticmethod
    def score_agents(model_id: int, end_ts: str | None = None, lookback_windows: int = 1) -> dict[str, int]:
        if lookback_windows < 1:
            raise ValueError("lookback_windows must be >= 1")

        model_record = AIService._load_model_record(model_id)
        bundle = load_bundle(model_record["artifact_path"])
        model = bundle["model"]
        score_min = float(bundle["score_min"])
        score_max = float(bundle["score_max"])
        anomaly_cutoff = float(bundle["anomaly_cutoff"])
        feature_means = bundle["feature_means"]
        feature_stds = bundle["feature_stds"]

        window_minutes = int(model_record["window_minutes"])
        end = parse_iso(end_ts) if end_ts else utcnow()

        scored_agents: set[int] = set()
        inserted = 0

        with get_db() as conn:
            agents = conn.execute("SELECT id FROM agents ORDER BY id ASC").fetchall()
            for row in agents:
                agent_id = int(row["id"])
                scored_agents.add(agent_id)
                for idx in range(lookback_windows):
                    window_end = end - timedelta(minutes=window_minutes * idx)
                    window_start = window_end - timedelta(minutes=window_minutes)
                    window_rows = build_feature_dataset(window_minutes, iso_utc(window_start), iso_utc(window_end))
                    target = next((r for r in window_rows if r.agent_id == agent_id), None)
                    if target is None:
                        continue

                    vector = np.array([feature_vector(target.features)], dtype=float)
                    raw_score = float(model.score_samples(vector)[0])
                    risk_score = score_to_risk(raw_score, score_min, score_max)
                    is_anomaly = 1 if raw_score <= anomaly_cutoff else 0
                    explanation = build_explanation(target.features, feature_means, feature_stds)

                    conn.execute(
                        """
                        INSERT INTO ai_scores(
                            ts, agent_id, window_start_ts, window_end_ts,
                            risk_score, is_anomaly, model_name, model_version,
                            explanation_json, status
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                        """,
                        (
                            utcnow().isoformat(),
                            agent_id,
                            target.window_start_ts,
                            target.window_end_ts,
                            risk_score,
                            is_anomaly,
                            model_record["model_name"],
                            model_record["model_version"],
                            json.dumps(explanation),
                        ),
                    )
                    inserted += 1

            AuditService.log(
                conn,
                actor_type="ADMIN",
                action="SCORE_RUN",
                target_type="AI_MODEL",
                target_id=model_id,
                message="AI scoring run completed",
                metadata={"scored_agents": len(scored_agents), "inserted_scores": inserted},
            )

        return {"scored_agents": len(scored_agents), "inserted_scores": inserted}

    @staticmethod
    def get_scores(agent_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with get_db() as conn:
            if agent_id is None:
                rows = conn.execute(
                    "SELECT * FROM ai_scores ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ai_scores WHERE agent_id = ? ORDER BY ts DESC LIMIT ?",
                    (agent_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_models() -> list[dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM ai_models ORDER BY trained_at DESC").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_latest_score(agent_id: int) -> dict[str, Any] | None:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM ai_scores WHERE agent_id = ? ORDER BY ts DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            return dict(row) if row else None
