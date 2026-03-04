from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.version import SERVER_VERSION, SCHEMA_VERSION
from app.db.database import get_db, init_db
from app.licensing_core.loader import load_license
from app.licensing_core.policy import load_security_policy
from app.licensing_core.policy_state import set_policy_state
from app.licensing_core.state import set_license_state
from app.services.audit_service import AuditService
from app.security.storage_crypto import get_crypto_status
from app.services.maintenance_schedule_service import MaintenanceScheduleService
from app.services.user_service import UserService
from app.utils.request_context import REQUEST_ID

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartupValidationError(RuntimeError):
    pass


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float, limit: int, window_sec: int) -> bool:
        bucket = self._buckets[key]
        cutoff = now - window_sec
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_rate_limiter = SlidingWindowRateLimiter()
_maintenance_scheduler_stop = threading.Event()
_maintenance_scheduler_thread: threading.Thread | None = None


def _resolve_path(path_str: str) -> str:
    candidate = Path(path_str)
    if candidate.is_absolute():
        return str(candidate)
    root = Path(__file__).resolve().parents[2]
    return str(root / candidate)


def _resolve_scheduler_actor_id() -> int | None:
    with get_db() as conn:
        admin_row = conn.execute(
            "SELECT id FROM users WHERE role = 'ADMIN' AND is_active = 1 ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if admin_row:
            return int(admin_row["id"])

        fallback = conn.execute(
            "SELECT id FROM users WHERE is_active = 1 ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if fallback:
            return int(fallback["id"])
    return None


def _maintenance_scheduler_loop(*, interval_sec: int, batch_limit: int) -> None:
    logger.info(
        "Maintenance background scheduler started interval_sec=%s batch_limit=%s",
        interval_sec,
        batch_limit,
    )
    while not _maintenance_scheduler_stop.is_set():
        started = time.monotonic()
        try:
            actor_id = _resolve_scheduler_actor_id()
            if actor_id is None:
                logger.warning("Maintenance background scheduler skipped tick: no active user available for actor_id")
            else:
                result = MaintenanceScheduleService.run_due_schedules(actor_id=actor_id, limit=batch_limit)
                if result["due_count"] > 0 or result["failed_count"] > 0:
                    logger.info(
                        "Maintenance background scheduler tick due=%s executed=%s failed=%s tasks_dispatched=%s",
                        result["due_count"],
                        result["executed_count"],
                        result["failed_count"],
                        result["tasks_dispatched"],
                    )
        except Exception:
            logger.exception("Maintenance background scheduler tick failed")

        elapsed = time.monotonic() - started
        wait_seconds = max(1.0, float(interval_sec) - elapsed)
        if _maintenance_scheduler_stop.wait(wait_seconds):
            break

    logger.info("Maintenance background scheduler stopped")


def _start_maintenance_scheduler() -> None:
    global _maintenance_scheduler_thread
    if not settings.maintenance_scheduler_enabled:
        logger.info("Maintenance background scheduler disabled by configuration")
        return
    if _maintenance_scheduler_thread and _maintenance_scheduler_thread.is_alive():
        return

    _maintenance_scheduler_stop.clear()
    _maintenance_scheduler_thread = threading.Thread(
        target=_maintenance_scheduler_loop,
        kwargs={
            "interval_sec": int(settings.maintenance_scheduler_interval_sec),
            "batch_limit": int(settings.maintenance_scheduler_batch_limit),
        },
        name="maintenance-scheduler-loop",
        daemon=True,
    )
    _maintenance_scheduler_thread.start()


def _stop_maintenance_scheduler(*, timeout_sec: float = 5.0) -> None:
    global _maintenance_scheduler_thread
    if not _maintenance_scheduler_thread:
        return
    _maintenance_scheduler_stop.set()
    _maintenance_scheduler_thread.join(timeout=timeout_sec)
    if _maintenance_scheduler_thread.is_alive():
        logger.warning("Maintenance background scheduler did not stop cleanly before timeout")
    _maintenance_scheduler_thread = None


def _is_weak_jwt_secret(secret: str) -> bool:
    if not secret:
        return True
    lowered = secret.strip().lower()
    weak_values = {"change-me-in-production", "changeme", "default", "secret", "password"}
    return lowered in weak_values or len(secret.strip()) < 24


def _validate_startup_guardrails(policy_reason: str) -> None:
    env = settings.environment
    if env not in {"dev", "test", "prod"}:
        raise StartupValidationError("STARTUP_ENVIRONMENT_INVALID")

    if env != "dev" and _is_weak_jwt_secret(settings.jwt_secret):
        raise StartupValidationError("STARTUP_JWT_SECRET_WEAK")

    if env != "dev" and policy_reason in {"POLICY_MISSING", "POLICY_INVALID_SIGNATURE", "POLICY_INVALID_JSON"}:
        raise StartupValidationError(f"STARTUP_POLICY_INVALID:{policy_reason}")

    if env == "prod":
        allow_token_private_key = Path(_resolve_path(settings.device_allow_token_private_key_path))
        if not allow_token_private_key.exists():
            raise StartupValidationError("STARTUP_ALLOW_TOKEN_PRIVATE_KEY_MISSING")


def _handle_bootstrap_admin() -> None:
    if UserService.count_users() > 0:
        return

    if settings.environment == "dev":
        if UserService.ensure_bootstrap_admin_dev():
            logger.warning(
                "Default admin bootstrap account created in dev mode (username=admin). Rotate password immediately."
            )
        return

    token = settings.bootstrap_admin_token.strip()
    username = settings.bootstrap_admin_username.strip()
    password = settings.bootstrap_admin_password
    if not (token and username and password):
        raise StartupValidationError("STARTUP_ADMIN_BOOTSTRAP_REQUIRED")

    try:
        created = UserService.bootstrap_admin_with_token(
            expected_token=token,
            provided_token=token,
            username=username,
            password=password,
        )
    except ValueError as exc:
        raise StartupValidationError(f"STARTUP_ADMIN_BOOTSTRAP_INVALID:{exc}") from exc

    if created:
        logger.info("Bootstrap admin created from explicit bootstrap token flow")




@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id", "").strip() or str(uuid.uuid4())
    request.state.request_id = rid
    token = REQUEST_ID.set(rid)
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
    finally:
        REQUEST_ID.reset(token)

@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")

    if content_length:
        try:
            parsed_length = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid Content-Length header"
            )

        if parsed_length > settings.request_size_limit_bytes:
            raise HTTPException(
                status_code=413,
                detail="Payload too large"
            )

    body = await request.body()

    if len(body) > settings.request_size_limit_bytes:
        raise HTTPException(
            status_code=413,
            detail="Payload too large"
        )

    request._body = body
    return await call_next(request)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    endpoint_key = None
    key = None
    path = request.url.path

    if path.endswith("/auth/login") and request.method.upper() == "POST":
        endpoint_key = "login"
        key = f"ip:{request.client.host if request.client else 'unknown'}"
        limit = settings.login_rate_limit_count
        window = settings.login_rate_limit_window_sec
    elif path.endswith("/agents/heartbeat") or path.endswith("/agents/events"):
        endpoint_key = "agent"
        token = request.headers.get("x-ecims-token", "").strip()
        if token:
            key = f"token:{token[:16]}"
        else:
            key = f"ip:{request.client.host if request.client else 'unknown'}"
        limit = settings.agent_rate_limit_count
        window = settings.agent_rate_limit_window_sec
    else:
        return await call_next(request)

    if not _rate_limiter.allow(f"{endpoint_key}:{key}", time.time(), limit, window):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    migration = init_db()
    _rate_limiter._buckets.clear()

    policy_state = load_security_policy(
        policy_path=_resolve_path(settings.security_policy_path),
        policy_sig_path=_resolve_path(settings.security_policy_sig_path),
        public_key_override=_resolve_path(settings.security_policy_public_key_path),
    )
    set_policy_state(policy_state)

    _validate_startup_guardrails(policy_state.reason)

    crypto_status = get_crypto_status()
    if settings.data_encryption_enabled and not crypto_status.encryption_enabled:
        raise StartupValidationError(f"STARTUP_DATA_ENCRYPTION_INVALID:{crypto_status.reason}")

    configured_public_key_path = _resolve_path(settings.license_public_key_path)
    override_pub = os.getenv("ECIMS_LICENSE_PUBLIC_KEY_PATH")
    allow_override = policy_state.policy.allow_key_override or settings.environment in {"dev", "test"}
    if override_pub and allow_override:
        public_key_path = _resolve_path(override_pub)
    else:
        public_key_path = configured_public_key_path
    license_state = load_license(
        license_path=_resolve_path(settings.license_path),
        public_key_path=public_key_path,
    )
    set_license_state(license_state)

    _handle_bootstrap_admin()

    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="SYSTEM",
            action="SCHEMA_MIGRATION_APPLIED",
            target_type="DATABASE",
            target_id="schema_version",
            message="Schema migration check completed",
            metadata=migration,
        )
        AuditService.log(
            conn,
            actor_type="SYSTEM",
            action="SECURITY_POLICY_LOADED",
            target_type="POLICY",
            target_id="security-policy",
            message="Security policy evaluated",
            metadata={"source": policy_state.source, "reason": policy_state.reason, "mode": policy_state.policy.mode},
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
    logger.info("Storage encryption enabled=%s key_id=%s reason=%s", crypto_status.encryption_enabled, crypto_status.active_key_id, crypto_status.reason)
    _start_maintenance_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    _stop_maintenance_scheduler()


@app.get("/health")
def health() -> dict[str, object]:
    db_ok = True
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db_ok": db_ok,
        "server_version": SERVER_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


app.include_router(api_router, prefix=settings.api_prefix)
