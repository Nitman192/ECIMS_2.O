from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.db.database import get_db
from app.licensing_core.state import get_license_state
from app.models.user import UserRole
from app.security.auth import decode_access_token
from app.services.agent_service import AgentService
from app.services.audit_service import AuditService
from app.services.user_service import UserService

bearer_scheme = HTTPBearer(auto_error=False)


def validate_token(agent_id: int, x_ecims_token: str = Header(default="")) -> None:
    if not x_ecims_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-ECIMS-TOKEN")
    if not AgentService.validate_agent_token(agent_id, x_ecims_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")


def _audit_block(action: str, reason: str) -> None:
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="SYSTEM",
            action=action,
            target_type="LICENSE",
            target_id="phase4",
            message="License gate blocked operation",
            metadata={"reason": reason},
        )


def require_valid_license() -> None:
    state = get_license_state()
    if not state.valid:
        _audit_block("LICENSE_AI_BLOCK", state.reason)
        raise HTTPException(status_code=403, detail=f"Blocked by license: {state.reason}")


def require_ai_enabled() -> None:
    state = get_license_state()
    if not state.valid:
        _audit_block("LICENSE_AI_BLOCK", state.reason)
        raise HTTPException(status_code=403, detail=f"AI blocked by license: {state.reason}")
    if state.payload is None or not state.payload.ai_enabled:
        reason = "AI_DISABLED"
        _audit_block("LICENSE_AI_BLOCK", reason)
        raise HTTPException(status_code=403, detail=f"AI blocked by license: {reason}")


def require_registration_allowed() -> None:
    state = get_license_state()
    if not state.valid:
        _audit_block("LICENSE_REGISTRATION_BLOCK", state.reason)
        raise HTTPException(status_code=403, detail=f"Registration blocked by license: {state.reason}")
    if state.payload is None:
        reason = "INVALID_LICENSE_PAYLOAD"
        _audit_block("LICENSE_REGISTRATION_BLOCK", reason)
        raise HTTPException(status_code=403, detail=f"Registration blocked by license: {reason}")

    current = AgentService.count_agents()
    if current >= state.payload.max_agents:
        reason = "MAX_AGENTS_REACHED"
        _audit_block("LICENSE_REGISTRATION_BLOCK", reason)
        raise HTTPException(status_code=403, detail=f"Registration blocked by license: {reason}")


def require_admin_auth(x_ecims_admin_token: str = Header(default="")) -> None:
    settings = get_settings()
    expected = settings.admin_api_token.strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin API disabled")
    if x_ecims_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload.get("sub", ""))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = UserService.get_by_id(user_id)
    if not user or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    request_path = request.url.path.rstrip("/")
    if user["must_reset_password"] and not (
        request_path.endswith("/auth/me") or request_path.endswith("/auth/password/reset")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password reset required")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def require_analyst_or_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in {UserRole.ADMIN.value, UserRole.ANALYST.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Analyst or Admin role required")
    return user
