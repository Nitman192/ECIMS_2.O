from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from app.ai.service import AIService
from app.api.deps import validate_token
from app.core.config import get_settings
from app.schemas.admin import BaselineApproveRequest
from app.schemas.ai import AIScoreRunRequest, AITrainRequest
from app.schemas.agent import (
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentSummary,
)
from app.schemas.alert import AlertOut
from app.schemas.event import EventBatchRequest, EventBatchResponse
from app.services.agent_service import AgentService
from app.services.alert_service import AlertService
from app.services.event_service import EventService
from app.services.retention_service import RetentionService

router = APIRouter()


@router.post("/agents/register", response_model=AgentRegisterResponse)
def register_agent(payload: AgentRegisterRequest) -> AgentRegisterResponse:
    agent_id, token = AgentService.register_agent(payload.name, payload.hostname)
    return AgentRegisterResponse(agent_id=agent_id, token=token)


@router.post("/agents/heartbeat")
def agent_heartbeat(payload: AgentHeartbeatRequest, x_ecims_token: str = Header(default="")):
    validate_token(payload.agent_id, x_ecims_token)
    AgentService.heartbeat(payload.agent_id)
    return {"status": "ok"}


@router.post("/agents/events", response_model=EventBatchResponse)
def agent_events(payload: EventBatchRequest, x_ecims_token: str = Header(default="")):
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


@router.post("/admin/run_offline_check")
def run_offline_check():
    settings = get_settings()
    created = AgentService.run_offline_check(settings.offline_threshold_sec)
    return {"offline_alerts_created": created}


@router.post("/admin/baseline/approve")
def approve_baseline(payload: BaselineApproveRequest):
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
def run_retention():
    settings = get_settings()
    return RetentionService.run(
        settings.retention_days_events,
        settings.retention_days_alerts,
        settings.retention_days_audit,
    )


@router.post("/ai/train")
def ai_train(payload: AITrainRequest):
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
def ai_score_run(payload: AIScoreRunRequest):
    try:
        return AIService.score_agents(
            model_id=payload.model_id,
            end_ts=payload.end_ts.isoformat() if payload.end_ts else None,
            lookback_windows=payload.lookback_windows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ai/scores")
def ai_scores(agent_id: int | None = Query(default=None), limit: int = Query(default=50, ge=1, le=1000)):
    return AIService.get_scores(agent_id=agent_id, limit=limit)


@router.get("/ai/models")
def ai_models():
    return AIService.get_models()
