from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "ECIMS 2.0 Server"
    api_prefix: str = "/api/v1"
    db_path: str = "ecims2.db"
    offline_threshold_sec: int = 120
    request_size_limit_bytes: int = 1024 * 1024
    event_batch_limit: int = 1000

    baseline_update_mode: Literal["AUTO", "MANUAL"] = "AUTO"
    allow_legacy_phase1_events: bool = True

    retention_days_events: int = Field(default=30, ge=1)
    retention_days_alerts: int = Field(default=90, ge=1)
    retention_days_audit: int = Field(default=365, ge=1)
    ai_artifact_dir: str = "ai_artifacts"


@lru_cache
def get_settings() -> Settings:
    config_path = Path(__file__).resolve().parents[3] / "configs" / "server.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    env_db_path = os.getenv("ECIMS_DB_PATH")
    if env_db_path:
        raw["db_path"] = env_db_path

    env_ai_artifact_dir = os.getenv("ECIMS_AI_ARTIFACT_DIR")
    if env_ai_artifact_dir:
        raw["ai_artifact_dir"] = env_ai_artifact_dir

    return Settings(**raw)
