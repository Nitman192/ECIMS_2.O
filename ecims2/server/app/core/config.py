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
    license_path: str = "configs/license.ecims"
    license_public_key_path: str = "server/app/license/public_key.pem"

    security_policy_path: str = "configs/security.policy.json"
    security_policy_sig_path: str = "configs/security.policy.sig"

    mtls_enabled: bool = True
    mtls_required: bool = True
    server_cert_path: str = "configs/tls/server.crt"
    server_key_path: str = "configs/tls/server.key"
    client_ca_cert_path: str = "configs/tls/client_ca.crt"
    tls_min_version: Literal["1.2", "1.3"] = "1.3"

    admin_api_token: str = ""

    data_encryption_enabled: bool = True
    data_key_path: str = "server/.ecims_state/data_keyring.json"
    data_key_env: str = "ECIMS_DATA_KEY_B64"
    key_rotation_grace_days: int = 0


def _apply_env_override(raw: dict[str, Any], field: str, env_var: str) -> None:
    value = os.getenv(env_var)
    if value:
        raw[field] = value


@lru_cache
def get_settings() -> Settings:
    config_path = Path(__file__).resolve().parents[3] / "configs" / "server.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    _apply_env_override(raw, "db_path", "ECIMS_DB_PATH")
    _apply_env_override(raw, "ai_artifact_dir", "ECIMS_AI_ARTIFACT_DIR")
    _apply_env_override(raw, "license_path", "ECIMS_LICENSE_PATH")
    _apply_env_override(raw, "license_public_key_path", "ECIMS_LICENSE_PUBLIC_KEY_PATH")
    _apply_env_override(raw, "security_policy_path", "ECIMS_SECURITY_POLICY_PATH")
    _apply_env_override(raw, "security_policy_sig_path", "ECIMS_SECURITY_POLICY_SIG_PATH")
    _apply_env_override(raw, "server_cert_path", "ECIMS_SERVER_CERT_PATH")
    _apply_env_override(raw, "server_key_path", "ECIMS_SERVER_KEY_PATH")
    _apply_env_override(raw, "client_ca_cert_path", "ECIMS_CLIENT_CA_CERT_PATH")
    _apply_env_override(raw, "tls_min_version", "ECIMS_TLS_MIN_VERSION")
    _apply_env_override(raw, "admin_api_token", "ECIMS_ADMIN_API_TOKEN")
    _apply_env_override(raw, "data_key_path", "ECIMS_DATA_KEY_PATH")
    _apply_env_override(raw, "data_key_env", "ECIMS_DATA_KEY_ENV")

    env_mtls_enabled = os.getenv("ECIMS_MTLS_ENABLED")
    if env_mtls_enabled:
        raw["mtls_enabled"] = env_mtls_enabled.strip().lower() in {"1", "true", "yes"}

    env_mtls_required = os.getenv("ECIMS_MTLS_REQUIRED")

    env_data_encryption_enabled = os.getenv("ECIMS_DATA_ENCRYPTION_ENABLED")
    if env_data_encryption_enabled:
        raw["data_encryption_enabled"] = env_data_encryption_enabled.strip().lower() in {"1", "true", "yes"}

    env_key_rotation_grace_days = os.getenv("ECIMS_KEY_ROTATION_GRACE_DAYS")
    if env_key_rotation_grace_days:
        raw["key_rotation_grace_days"] = int(env_key_rotation_grace_days)

    if env_mtls_required:
        raw["mtls_required"] = env_mtls_required.strip().lower() in {"1", "true", "yes"}

    return Settings(**raw)
