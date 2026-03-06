from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    environment: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "ECIMS 2.0 Server"
    api_prefix: str = "/api/v1"
    db_path: str = "ecims2.db"
    offline_threshold_sec: int = 120
    request_size_limit_bytes: int = 1024 * 1024
    patch_update_max_file_bytes: int = 256 * 1024 * 1024
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
    security_policy_public_key_path: str = "configs/security.policy.public.pem"

    mtls_enabled: bool = True
    mtls_required: bool = True
    server_cert_path: str = "configs/tls/server.crt"
    server_key_path: str = "configs/tls/server.key"
    client_ca_cert_path: str = "configs/tls/client_ca.crt"
    tls_min_version: Literal["1.2", "1.3"] = "1.3"

    admin_api_token: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_expiry_minutes: int = Field(default=30, ge=1)
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    bootstrap_admin_token: str = ""
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""

    login_rate_limit_count: int = Field(default=100, ge=1)
    login_rate_limit_window_sec: int = Field(default=60, ge=1)
    agent_rate_limit_count: int = Field(default=1000, ge=1)
    agent_rate_limit_window_sec: int = Field(default=60, ge=1)

    device_allow_token_private_key_path: str = "configs/device_allow_token_private.pem"
    device_allow_token_public_key_path: str = "configs/device_allow_token_public.pem"
    allow_token_max_duration_minutes: int = Field(default=240, ge=1)

    data_encryption_enabled: bool = False
    data_key_path: str = "configs/data_keys.json"
    data_key_env: str = "ECIMS_DATA_KEY_B64"

    maintenance_scheduler_enabled: bool = False
    maintenance_scheduler_interval_sec: int = Field(default=60, ge=1, le=3600)
    maintenance_scheduler_batch_limit: int = Field(default=20, ge=1, le=100)

    discovery_enabled: bool = False
    discovery_udp_port: int = Field(default=40110, ge=1, le=65535)
    discovery_server_url: str = ""
    discovery_http_port: int = Field(default=8010, ge=1, le=65535)
    discovery_mdns_enabled: bool = False
    discovery_mdns_service_name: str = "ecims-server"
    discovery_mdns_service_type: str = "_ecims._tcp.local."
    admin_console_enabled: bool = True
    admin_console_dist_path: str = "../ecims_admin/dist"


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
    _apply_env_override(raw, "security_policy_public_key_path", "ECIMS_SECURITY_POLICY_PUBLIC_KEY_PATH")
    _apply_env_override(raw, "server_cert_path", "ECIMS_SERVER_CERT_PATH")
    _apply_env_override(raw, "server_key_path", "ECIMS_SERVER_KEY_PATH")
    _apply_env_override(raw, "client_ca_cert_path", "ECIMS_CLIENT_CA_CERT_PATH")
    _apply_env_override(raw, "tls_min_version", "ECIMS_TLS_MIN_VERSION")
    _apply_env_override(raw, "admin_api_token", "ECIMS_ADMIN_API_TOKEN")
    _apply_env_override(raw, "jwt_secret", "ECIMS_JWT_SECRET")
    _apply_env_override(raw, "jwt_expiry_minutes", "ECIMS_JWT_EXPIRY_MINUTES")
    _apply_env_override(raw, "bcrypt_rounds", "ECIMS_BCRYPT_ROUNDS")
    _apply_env_override(raw, "environment", "ECIMS_ENVIRONMENT")
    _apply_env_override(raw, "bootstrap_admin_token", "ECIMS_BOOTSTRAP_ADMIN_TOKEN")
    _apply_env_override(raw, "bootstrap_admin_username", "ECIMS_BOOTSTRAP_ADMIN_USERNAME")
    _apply_env_override(raw, "bootstrap_admin_password", "ECIMS_BOOTSTRAP_ADMIN_PASSWORD")
    _apply_env_override(raw, "login_rate_limit_count", "ECIMS_LOGIN_RATE_LIMIT_COUNT")
    _apply_env_override(raw, "login_rate_limit_window_sec", "ECIMS_LOGIN_RATE_LIMIT_WINDOW_SEC")
    _apply_env_override(raw, "agent_rate_limit_count", "ECIMS_AGENT_RATE_LIMIT_COUNT")
    _apply_env_override(raw, "agent_rate_limit_window_sec", "ECIMS_AGENT_RATE_LIMIT_WINDOW_SEC")
    _apply_env_override(raw, "patch_update_max_file_bytes", "ECIMS_PATCH_UPDATE_MAX_FILE_BYTES")
    _apply_env_override(raw, "allow_token_max_duration_minutes", "ECIMS_ALLOW_TOKEN_MAX_DURATION_MINUTES")
    _apply_env_override(raw, "device_allow_token_public_key_path", "ECIMS_DEVICE_ALLOW_TOKEN_PUBLIC_KEY_PATH")
    _apply_env_override(raw, "device_allow_token_private_key_path", "ECIMS_DEVICE_ALLOW_TOKEN_PRIVATE_KEY_PATH")
    _apply_env_override(raw, "data_key_path", "ECIMS_DATA_KEY_PATH")
    _apply_env_override(raw, "data_key_env", "ECIMS_DATA_KEY_ENV")
    _apply_env_override(raw, "maintenance_scheduler_interval_sec", "ECIMS_MAINTENANCE_SCHEDULER_INTERVAL_SEC")
    _apply_env_override(raw, "maintenance_scheduler_batch_limit", "ECIMS_MAINTENANCE_SCHEDULER_BATCH_LIMIT")
    _apply_env_override(raw, "discovery_udp_port", "ECIMS_DISCOVERY_UDP_PORT")
    _apply_env_override(raw, "discovery_server_url", "ECIMS_DISCOVERY_SERVER_URL")
    _apply_env_override(raw, "discovery_http_port", "ECIMS_DISCOVERY_HTTP_PORT")
    _apply_env_override(raw, "discovery_mdns_service_name", "ECIMS_DISCOVERY_MDNS_SERVICE_NAME")
    _apply_env_override(raw, "discovery_mdns_service_type", "ECIMS_DISCOVERY_MDNS_SERVICE_TYPE")
    _apply_env_override(raw, "admin_console_dist_path", "ECIMS_ADMIN_CONSOLE_DIST_PATH")

    env_data_encryption_enabled = os.getenv("ECIMS_DATA_ENCRYPTION_ENABLED")
    if env_data_encryption_enabled:
        raw["data_encryption_enabled"] = env_data_encryption_enabled.strip().lower() in {"1", "true", "yes"}

    env_mtls_enabled = os.getenv("ECIMS_MTLS_ENABLED")
    if env_mtls_enabled:
        raw["mtls_enabled"] = env_mtls_enabled.strip().lower() in {"1", "true", "yes"}

    env_mtls_required = os.getenv("ECIMS_MTLS_REQUIRED")
    if env_mtls_required:
        raw["mtls_required"] = env_mtls_required.strip().lower() in {"1", "true", "yes"}

    env_maintenance_scheduler_enabled = os.getenv("ECIMS_MAINTENANCE_SCHEDULER_ENABLED")
    if env_maintenance_scheduler_enabled:
        raw["maintenance_scheduler_enabled"] = env_maintenance_scheduler_enabled.strip().lower() in {"1", "true", "yes"}

    env_discovery_enabled = os.getenv("ECIMS_DISCOVERY_ENABLED")
    if env_discovery_enabled:
        raw["discovery_enabled"] = env_discovery_enabled.strip().lower() in {"1", "true", "yes"}

    env_discovery_mdns_enabled = os.getenv("ECIMS_DISCOVERY_MDNS_ENABLED")
    if env_discovery_mdns_enabled:
        raw["discovery_mdns_enabled"] = env_discovery_mdns_enabled.strip().lower() in {"1", "true", "yes"}

    env_admin_console_enabled = os.getenv("ECIMS_ADMIN_CONSOLE_ENABLED")
    if env_admin_console_enabled:
        raw["admin_console_enabled"] = env_admin_console_enabled.strip().lower() in {"1", "true", "yes"}

    return Settings(**raw)
