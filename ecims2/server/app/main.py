from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.db.database import get_db, init_db
from app.licensing_core.loader import load_license
from app.licensing_core.policy import load_security_policy
from app.licensing_core.policy_state import set_policy_state
from app.licensing_core.state import set_license_state
from app.security.storage_crypto import get_crypto_status
from app.services.audit_service import AuditService

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name)




def _data_key_state_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    state_dir = root / "server" / ".ecims_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "data_key_state.json"


def _read_last_active_key_id() -> str | None:
    p = _data_key_state_path()
    if not p.exists():
        return None
    try:
        import json

        body = json.loads(p.read_text(encoding="utf-8"))
        value = body.get("active_key_id")
        return str(value) if value else None
    except Exception:
        return None


def _write_active_key_id(key_id: str | None) -> None:
    if not key_id:
        return
    import json

    _data_key_state_path().write_text(json.dumps({"active_key_id": key_id}), encoding="utf-8")

def _resolve_path(path_str: str) -> str:
    candidate = Path(path_str)
    if candidate.is_absolute():
        return str(candidate)
    root = Path(__file__).resolve().parents[3]
    return str(root / candidate)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.request_size_limit_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    body = await request.body()
    if len(body) > settings.request_size_limit_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    request._body = body
    return await call_next(request)


@app.middleware("http")
async def rate_limit_stub(request: Request, call_next):
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    init_db()

    policy_state = load_security_policy(
        policy_path=_resolve_path(settings.security_policy_path),
        policy_sig_path=_resolve_path(settings.security_policy_sig_path),
    )
    set_policy_state(policy_state)

    if settings.key_rotation_grace_days > 0 and not policy_state.policy.allow_key_rotation_grace:
        raise RuntimeError("Fail-closed startup: key rotation grace not permitted by signed policy")

    crypto_status = get_crypto_status()
    required_encryption = settings.data_encryption_enabled and policy_state.policy.data_encryption_required
    prev_active_key_id = _read_last_active_key_id()
    if required_encryption and not crypto_status.encryption_enabled:
        with get_db() as conn:
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="DATA_KEY_MISSING",
                target_type="SECURITY",
                target_id="storage-crypto",
                message="Data encryption required but key is missing/invalid",
                metadata={"reason": crypto_status.reason},
            )
        raise RuntimeError(f"Fail-closed startup: {crypto_status.reason}")

    override_pub = os.getenv("ECIMS_LICENSE_PUBLIC_KEY_PATH")
    pub_override = _resolve_path(override_pub) if (override_pub and policy_state.policy.allow_key_override) else None
    license_state = load_license(
        license_path=_resolve_path(settings.license_path),
        public_key_path=pub_override,
    )
    set_license_state(license_state)

    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="SYSTEM",
            action="SECURITY_POLICY_LOADED",
            target_type="POLICY",
            target_id="security-policy",
            message="Security policy evaluated",
            metadata={"source": policy_state.source, "reason": policy_state.reason, "mode": policy_state.policy.mode},
        )
        if crypto_status.encryption_enabled:
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="DATA_ENCRYPTION_ENABLED",
                target_type="SECURITY",
                target_id="storage-crypto",
                message="Data encryption keyring loaded",
                metadata={"active_key_id": crypto_status.active_key_id, "keyring_count": crypto_status.keyring_count},
            )
            if prev_active_key_id and prev_active_key_id != crypto_status.active_key_id:
                AuditService.log(
                    conn,
                    actor_type="SYSTEM",
                    action="DATA_KEY_ROTATED",
                    target_type="SECURITY",
                    target_id="storage-crypto",
                    message="Active data encryption key changed",
                    metadata={"previous_key_id": prev_active_key_id, "active_key_id": crypto_status.active_key_id},
                )
            _write_active_key_id(crypto_status.active_key_id)
        else:
            action = "DATA_KEY_MISSING" if "MISSING" in crypto_status.reason else "DATA_KEY_INVALID"
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action=action,
                target_type="SECURITY",
                target_id="storage-crypto",
                message="Data encryption unavailable",
                metadata={"reason": crypto_status.reason},
            )

        if license_state.valid:
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="LICENSE_LOADED",
                target_type="LICENSE",
                target_id="phase4",
                message="License loaded successfully",
                metadata={"valid": 1, "reason": license_state.reason},
            )
        else:
            action = "LICENSE_TAMPER_DETECTED" if license_state.reason == "TAMPER_DETECTED" else "LICENSE_INVALID"
            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action=action,
                target_type="LICENSE",
                target_id="phase4",
                message="License invalid",
                metadata={"valid": 0, "reason": license_state.reason},
            )

    logger.info("Database initialized and server started")
    logger.info("Policy mode=%s reason=%s", policy_state.policy.mode, policy_state.reason)
    logger.info("License status valid=%s reason=%s", license_state.valid, license_state.reason)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)
