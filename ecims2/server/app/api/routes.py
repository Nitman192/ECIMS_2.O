from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.ai.service import AIService
from app.api.deps import (
    get_current_user,
    require_admin,
    require_ai_enabled,
    require_analyst_or_admin,
    require_registration_allowed,
    require_valid_license,
    validate_token,
)
from app.core.config import get_settings
from app.db.database import get_db
from app.licensing_core.policy_state import get_policy_state
from app.licensing_core.state import get_license_state
from app.schemas.admin import AgentRevokeRequest, BaselineApproveRequest
from app.schemas.ai import AIScoreRunRequest, AITrainRequest
from app.schemas.agent import (
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentSummary,
)
from app.schemas.alert import AlertOut
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.event import EventBatchRequest, EventBatchResponse
from app.schemas.user import UserOut
from app.security.auth import create_access_token
from app.security.mtls import require_mtls_client_identity
from app.services.agent_service import AgentService
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.event_service import EventService
from app.services.retention_service import RetentionService
from app.services.user_service import UserService

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def auth_login(payload: LoginRequest) -> TokenResponse:
    user = UserService.verify_credentials(payload.username, payload.password)
    if not user:
        with get_db() as conn:
            AuditService.log(
                conn,
                actor_type="USER",
                action="LOGIN_FAILED",
                target_type="AUTH",
                target_id=payload.username,
                message="Login failed",
                metadata={"username": payload.username},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user_id=user["id"], username=user["username"], role=user["role"])
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="USER",
            actor_id=user["id"],
            action="LOGIN_SUCCESS",
            target_type="AUTH",
            target_id=user["id"],
            message="Login successful",
            metadata={"username": user["username"], "role": user["role"]},
        )
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=UserOut)
def auth_me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current_user["id"],
        username=current_user["username"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
    )


@router.post("/agents/register", response_model=AgentRegisterResponse)
def register_agent(
    payload: AgentRegisterRequest,
    request: Request,
    _: None = Depends(require_registration_allowed),
    __: dict = Depends(require_admin),
) -> AgentRegisterResponse:
    require_mtls_client_identity(request, claimed_agent_id=None)
    agent_id, token = AgentService.register_agent(payload.name, payload.hostname)
    return AgentRegisterResponse(agent_id=agent_id, token=token)


@router.post("/agents/heartbeat")
def agent_heartbeat(payload: AgentHeartbeatRequest, request: Request, x_ecims_token: str = Header(default="")):
    require_mtls_client_identity(request, claimed_agent_id=payload.agent_id)
    validate_token(payload.agent_id, x_ecims_token)
    AgentService.heartbeat(payload.agent_id)
    return {"status": "ok"}


@router.post("/agents/events", response_model=EventBatchResponse)
def agent_events(payload: EventBatchRequest, request: Request, x_ecims_token: str = Header(default="")):
    require_mtls_client_identity(request, claimed_agent_id=payload.agent_id)
    validate_token(payload.agent_id, x_ecims_token)
    settings = get_settings()
    if len(payload.events) > settings.event_batch_limit:
        raise HTTPException(status_code=400, detail="Event batch too large")

    try:
        processed, alerts_created = EventService.process_events(
            payload.agent_id,
            payload.events,
            allow_legacy=settings.allow_legacy_phase1_events,
            baseline_update_mode=settings.baseline_update_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EventBatchResponse(processed=processed, alerts_created=alerts_created)


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(limit: int = Query(default=200, ge=1, le=1000)):
    return AlertService.list_alerts(limit)


@router.get("/agents", response_model=list[AgentSummary])
def get_agents():
    settings = get_settings()
    return AgentService.list_agents(settings.offline_threshold_sec)


@router.get("/license/status")
def license_status(_: dict = Depends(require_admin)):
    state = get_license_state()
    payload = state.payload
    return {
        "is_valid": state.valid,
        "reason": state.reason,
        "loaded_at_utc": state.loaded_at_utc,
        "license_id": payload.license_id if payload else None,
        "customer_name": payload.customer_name if payload else (payload.org_name if payload else None),
        "org_name": payload.org_name if payload else None,
        "max_agents": payload.max_agents if payload else None,
        "agents_registered": AgentService.count_agents(),
        "agents_revoked": AgentService.count_revoked_agents(),
        "expiry_date": payload.expiry_date if payload else None,
        "ai_enabled": payload.ai_enabled if payload else None,
        "machine_match": state.machine_match,
        "local_fingerprint_short": state.local_fingerprint_short,
        "valid": state.valid,
    }


@router.get("/security/status")
def security_status(_: dict = Depends(require_admin)):
    state = get_policy_state()
    return {
        "policy_mode": state.policy.mode,
        "mtls_required": state.policy.mtls_required,
        "allow_unsigned_dev": state.policy.allow_unsigned_dev,
        "allow_key_override": state.policy.allow_key_override,
        "source": state.source,
        "reason": state.reason,
    }


@router.post("/admin/agents/{agent_id}/revoke")
def revoke_agent(agent_id: int, payload: AgentRevokeRequest, _: None = Depends(require_valid_license), user: dict = Depends(require_admin)):
    if not AgentService.revoke_agent(agent_id, payload.reason, actor_id=user["id"]):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "revoked", "agent_id": agent_id}


@router.post("/admin/agents/{agent_id}/restore")
def restore_agent(agent_id: int, _: None = Depends(require_valid_license), user: dict = Depends(require_admin)):
    if not AgentService.restore_agent(agent_id, actor_id=user["id"]):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "restored", "agent_id": agent_id}


@router.post("/admin/run_offline_check")
def run_offline_check(_: None = Depends(require_valid_license), __: dict = Depends(require_admin)):
    settings = get_settings()
    created = AgentService.run_offline_check(settings.offline_threshold_sec)
    return {"offline_alerts_created": created}


@router.post("/admin/baseline/approve")
def approve_baseline(payload: BaselineApproveRequest, _: None = Depends(require_valid_license), __: dict = Depends(require_admin)):
    settings = get_settings()
    if settings.baseline_update_mode != "MANUAL":
        raise HTTPException(status_code=400, detail="Baseline approval is only needed in MANUAL mode")

    updated = EventService.approve_baseline(
        payload.agent_id,
        payload.file_path,
        payload.approve_sha256,
        payload.reason,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Baseline entry not found")
    return {"status": "approved"}


@router.post("/admin/retention/run")
def run_retention(_: None = Depends(require_valid_license), __: dict = Depends(require_admin)):
    settings = get_settings()
    return RetentionService.run(
        settings.retention_days_events,
        settings.retention_days_alerts,
        settings.retention_days_audit,
    )


@router.post("/ai/train")
def ai_train(payload: AITrainRequest, _: None = Depends(require_ai_enabled), __: dict = Depends(require_analyst_or_admin)):
    try:
        return AIService.train_model(
            model_name=payload.model_name,
            model_version=payload.model_version,
            window_minutes=payload.window_minutes,
            start_ts=payload.start_ts.isoformat() if payload.start_ts else None,
            end_ts=payload.end_ts.isoformat() if payload.end_ts else None,
            params=payload.params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ai/score/run")
def ai_score_run(payload: AIScoreRunRequest, _: None = Depends(require_ai_enabled), __: dict = Depends(require_analyst_or_admin)):
    try:
        return AIService.score_agents(
            model_id=payload.model_id,
            end_ts=payload.end_ts.isoformat() if payload.end_ts else None,
            lookback_windows=payload.lookback_windows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ai/scores")
def ai_scores(
    agent_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    _: None = Depends(require_ai_enabled),
    __: dict = Depends(require_analyst_or_admin),
):
    return AIService.get_scores(agent_id=agent_id, limit=limit)


@router.get("/ai/models")
def ai_models(_: None = Depends(require_ai_enabled), __: dict = Depends(require_analyst_or_admin)):
    return AIService.get_models()
