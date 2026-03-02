from __future__ import annotations

from datetime import timedelta

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
from app.schemas.admin import (
    AgentRevokeRequest,
    AuditExportRequest,
    BaselineApproveRequest,
    DeviceAllowTokenIssueRequest,
    DeviceAllowTokenRevokeRequest,
    DeviceKillSwitchRequest,
    DeviceSetAgentModeRequest,
    DeviceUnblockApproveRequest,
    DeviceUnblockRequestCreate,
)
from app.schemas.ai import AIScoreRunRequest, AITrainRequest
from app.schemas.agent import (
    AgentCommandAckRequest,
    AgentCommandOut,
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
from app.services.agent_command_service import AgentCommandService
from app.services.agent_service import AgentService
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.device_allow_token_service import DeviceAllowTokenService
from app.services.device_control_state_service import DeviceControlStateService
from app.services.device_policy_service import DevicePolicyService
from app.services.event_service import EventService
from app.services.retention_service import RetentionService
from app.services.user_service import UserService
from app.utils.time import utcnow
from app.utils.request_context import REQUEST_ID

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




@router.get("/agents/{agent_id}/commands", response_model=list[AgentCommandOut])
def get_agent_commands(agent_id: int, request: Request, x_ecims_token: str = Header(default="")):
    require_mtls_client_identity(request, claimed_agent_id=agent_id)
    validate_token(agent_id, x_ecims_token)
    return AgentCommandService.list_pending(agent_id)


@router.post("/agents/{agent_id}/commands/{command_id}/ack")
def ack_agent_command(
    agent_id: int,
    command_id: int,
    payload: AgentCommandAckRequest,
    request: Request,
    x_ecims_token: str = Header(default=""),
):
    require_mtls_client_identity(request, claimed_agent_id=agent_id)
    validate_token(agent_id, x_ecims_token)
    if not AgentCommandService.ack(agent_id, command_id, applied=payload.applied, error=payload.error):
        raise HTTPException(status_code=404, detail="Command not found or already acknowledged")
    return {"status": "ok"}



@router.post("/agents/{agent_id}/device/status")
def agent_device_status(agent_id: int, payload: dict, request: Request, x_ecims_token: str = Header(default="")):
    require_mtls_client_identity(request, claimed_agent_id=agent_id)
    validate_token(agent_id, x_ecims_token)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO agent_device_status(agent_id, policy_hash_applied, enforcement_mode, adapter_status, last_reconcile_time, agent_version, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                policy_hash_applied=excluded.policy_hash_applied,
                enforcement_mode=excluded.enforcement_mode,
                adapter_status=excluded.adapter_status,
                last_reconcile_time=excluded.last_reconcile_time,
                agent_version=excluded.agent_version,
                updated_at=excluded.updated_at
            """,
            (
                agent_id,
                str(payload.get("policy_hash_applied", "")),
                str(payload.get("enforcement_mode", "")),
                str(payload.get("adapter_status", "")),
                str(payload.get("last_reconcile_time", "")),
                str(payload.get("agent_version", "")),
                utcnow().isoformat(),
            ),
        )
    return {"status": "ok"}

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
    backlog = AgentCommandService.backlog_counts()
    rollout = DevicePolicyService.rollout_counters()
    return {
        "policy_mode": state.policy.mode,
        "mtls_required": state.policy.mtls_required,
        "allow_unsigned_dev": state.policy.allow_unsigned_dev,
        "allow_key_override": state.policy.allow_key_override,
        "mass_storage_default_action": state.policy.mass_storage_default_action,
        "temporary_allow_duration_minutes": state.policy.temporary_allow_duration_minutes,
        "escalation_threshold": state.policy.escalation_threshold,
        "usb_allowlist_entries": len(state.policy.usb_allowlist),
        "device_enforcement_mode": state.policy.device_enforcement_mode,
        "mass_storage_offline_behavior": state.policy.mass_storage_offline_behavior,
        "allow_token_required_for_unblock": state.policy.allow_token_required_for_unblock,
        "allow_token_max_duration_minutes": state.policy.allow_token_max_duration_minutes,
        "local_event_queue_retention_hours": state.policy.local_event_queue_retention_hours,
        "command_backlog": backlog,
        "rollout_counters": rollout,
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




@router.post("/admin/device/unblock-request")
def create_device_unblock_request(payload: DeviceUnblockRequestCreate, admin: dict = Depends(require_admin)):
    decision = DevicePolicyService.evaluate_usb_mass_storage(
        vid=payload.vid,
        pid=payload.pid,
        serial=payload.serial,
        agent_id=payload.agent_id,
    )
    policy_state = get_policy_state()
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO device_unblock_requests(
                agent_id, device_id, vid, pid, serial, justification, requested_by_user_id, status, requested_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, 'PENDING', datetime('now'))
            """,
            (
                payload.agent_id,
                payload.device_id,
                payload.vid.strip().lower(),
                payload.pid.strip().lower(),
                payload.serial,
                payload.justification,
                admin["id"],
            ),
        )
        request_id = int(cursor.lastrowid)
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="device.usb.unblock_requested",
            target_type="DEVICE",
            target_id=payload.device_id,
            message="USB unblock requested",
            metadata={
                "request_id": request_id,
                "agent_id": payload.agent_id,
                "vid": payload.vid,
                "pid": payload.pid,
                "decision_action": decision.action,
                "decision_reason": decision.reason,
            },
        )
    return {
        "request_id": request_id,
        "status": "PENDING",
        "device_id": payload.device_id,
        "decision": {
            "action": decision.action,
            "reason": decision.reason,
            "temporary_allow_minutes": decision.temporary_allow_minutes,
            "policy_source": policy_state.source,
        },
    }


@router.post("/admin/device/unblock-approve")
def approve_device_unblock_request(payload: DeviceUnblockApproveRequest, admin: dict = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, agent_id, device_id, status FROM device_unblock_requests WHERE id = ?",
            (payload.request_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Unblock request not found")
        if row["status"] != "PENDING":
            raise HTTPException(status_code=400, detail="Unblock request already resolved")

        new_status = "APPROVED" if payload.approved else "DENIED"
        policy_state = get_policy_state()
        duration = policy_state.policy.temporary_allow_duration_minutes
        expires_at = (utcnow() + timedelta(minutes=duration)).isoformat() if payload.approved else None
        conn.execute(
            """
            UPDATE device_unblock_requests
            SET status = ?, approved_by_user_id = ?, approved_at = ?, expires_at = ?
            WHERE id = ?
            """,
            (new_status, admin["id"], utcnow().isoformat(), expires_at, payload.request_id),
        )
        action = "device.usb.unblock_approved" if payload.approved else "device.usb.unblock_denied"
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action=action,
            target_type="DEVICE",
            target_id=row["device_id"],
            message="USB unblock request reviewed",
            metadata={"request_id": payload.request_id, "status": new_status, "reason": payload.reason},
        )

    if payload.approved:
        allow_token, claims = DeviceAllowTokenService.issue_token(
            agent_id=row["agent_id"],
            duration_minutes=duration,
            scope={"device_id": row["device_id"]},
            justification=payload.reason,
            policy_version=get_policy_state().reason,
        )
        AgentCommandService.enqueue(int(row["agent_id"]), "DEVICE_APPLY_POLICY_HASH", {"policy_hash": get_policy_state().reason})
        command_id = AgentCommandService.enqueue(
            agent_id=row["agent_id"],
            command_type="DEVICE_UNBLOCK",
            payload={
                "request_id": payload.request_id,
                "duration_minutes": duration,
                "justification": payload.reason,
                "allow_token": allow_token,
                "token_id": claims["token_id"],
            },
        )
        with get_db() as conn:
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=admin["id"],
                action="DEVICE_UNBLOCK_COMMAND_ISSUED",
                target_type="AGENT_COMMAND",
                target_id=command_id,
                message="Unblock command issued to agent",
                metadata={"agent_id": row["agent_id"], "request_id": payload.request_id},
            )
    return {"request_id": payload.request_id, "status": new_status}



@router.post("/admin/device/allow-token")
def issue_device_allow_token(payload: DeviceAllowTokenIssueRequest, admin: dict = Depends(require_admin)):
    scope = {"vid": payload.vid, "pid": payload.pid, "serial": payload.serial}
    policy_state = get_policy_state()
    token, claims = DeviceAllowTokenService.issue_token(
        agent_id=payload.agent_id,
        duration_minutes=payload.duration_minutes,
        scope=scope,
        justification=payload.justification,
        policy_version=policy_state.reason,
    )
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="device.allow_token.issued",
            target_type="DEVICE_ALLOW_TOKEN",
            target_id=claims["token_id"],
            message="Device allow token issued",
            metadata={"agent_id": payload.agent_id, "expires_at": claims["expires_at"]},
        )
    return {"token": token, "claims": claims}


@router.post("/admin/device/allow-token/revoke")
def revoke_device_allow_token(payload: DeviceAllowTokenRevokeRequest, admin: dict = Depends(require_admin)):
    if not DeviceAllowTokenService.revoke_token(payload.token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="device.allow_token.revoked",
            target_type="DEVICE_ALLOW_TOKEN",
            target_id=payload.token_id,
            message="Device allow token revoked",
            metadata={},
        )
    return {"status": "revoked", "token_id": payload.token_id}



@router.post("/admin/device/kill-switch")
def set_device_kill_switch(payload: DeviceKillSwitchRequest, admin: dict = Depends(require_admin)):
    DeviceControlStateService.set_kill_switch(payload.enabled)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="DEVICE_KILL_SWITCH_SET",
            target_type="DEVICE_CONTROL",
            target_id="kill-switch",
            message="Device kill-switch updated",
            metadata={"enabled": payload.enabled, "reason": payload.reason},
        )
    if payload.enabled:
        with get_db() as conn:
            agents = conn.execute("SELECT id FROM agents").fetchall()
        for a in agents:
            AgentCommandService.enqueue(int(a["id"]), "DEVICE_FORCE_OBSERVE", {"reason": payload.reason})
    return {"status": "ok", "enabled": payload.enabled}


@router.post("/admin/device/set-agent-mode")
def set_agent_mode(payload: DeviceSetAgentModeRequest, admin: dict = Depends(require_admin)):
    if not AgentService.set_device_mode_override(payload.agent_id, payload.mode):
        raise HTTPException(status_code=404, detail="Agent not found")
    cmd_id = AgentCommandService.enqueue(payload.agent_id, "DEVICE_SET_MODE", {"mode": payload.mode, "reason": payload.reason})
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="DEVICE_AGENT_MODE_SET",
            target_type="AGENT",
            target_id=payload.agent_id,
            message="Per-agent device mode override set",
            metadata={"mode": payload.mode, "command_id": cmd_id, "reason": payload.reason},
        )
    return {"status": "ok", "agent_id": payload.agent_id, "mode": payload.mode}


@router.get("/admin/device/rollout/status")
def device_rollout_status(_: dict = Depends(require_admin)):
    return {
        "kill_switch": DeviceControlStateService.get_kill_switch(),
        "rollout": DevicePolicyService.rollout_counters(),
        "command_backlog": AgentCommandService.backlog_counts(),
    }



@router.get("/admin/metrics")
def admin_metrics(_: dict = Depends(require_admin)):
    with get_db() as conn:
        cmd = conn.execute("SELECT status, COUNT(*) AS c FROM agent_commands GROUP BY status").fetchall()
        events = conn.execute("SELECT event_type, COUNT(*) AS c FROM events GROUP BY event_type").fetchall()
        toks = conn.execute("SELECT status, COUNT(*) AS c FROM device_allow_tokens GROUP BY status").fetchall()
    cmd_map = {r["status"]: int(r["c"]) for r in cmd}
    tok_map = {r["status"]: int(r["c"]) for r in toks}
    return {
        "request_id": REQUEST_ID.get(),
        "agent_commands_pending": cmd_map.get("PENDING", 0),
        "agent_commands_applied": cmd_map.get("APPLIED", 0),
        "agent_commands_failed": cmd_map.get("FAILED", 0),
        "device_events_ingested_total": {r["event_type"]: int(r["c"]) for r in events},
        "allow_tokens_issued": sum(tok_map.values()),
        "allow_tokens_revoked": tok_map.get("REVOKED", 0),
        "allow_tokens_expired": tok_map.get("EXPIRED", 0),
        "kill_switch_state": DeviceControlStateService.get_kill_switch(),
        "rollout": DevicePolicyService.rollout_counters(),
        "rate_limiter_rejections_total": 0,
    }


@router.get("/admin/device/fleet/drift")
def device_fleet_drift(_: dict = Depends(require_admin)):
    expected_hash = get_policy_state().reason
    expected_mode = get_policy_state().policy.device_enforcement_mode
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.name, s.policy_hash_applied, s.enforcement_mode, s.adapter_status, s.last_reconcile_time, s.agent_version
            FROM agents a
            LEFT JOIN agent_device_status s ON s.agent_id = a.id
            ORDER BY a.id ASC
            """
        ).fetchall()
    drift = []
    for r in rows:
        mismatch = (r["policy_hash_applied"] or "") != expected_hash or (r["enforcement_mode"] or "") != expected_mode
        if mismatch:
            drift.append(
                {
                    "agent_id": int(r["id"]),
                    "agent_name": r["name"],
                    "policy_hash_applied": r["policy_hash_applied"],
                    "expected_policy_hash": expected_hash,
                    "enforcement_mode": r["enforcement_mode"],
                    "expected_mode": expected_mode,
                    "adapter_status": r["adapter_status"],
                    "last_reconcile_time": r["last_reconcile_time"],
                    "agent_version": r["agent_version"],
                }
            )
    return {"count": len(drift), "items": drift}

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


@router.get("/admin/audit")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    start_ts: str | None = Query(default=None),
    end_ts: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    role: str | None = Query(default=None),
    user: str | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="audit.read",
            target_type="AUDIT",
            target_id="audit_log",
            message="Audit log queried",
            metadata={"page": page, "page_size": page_size},
        )
        return AuditService.list_logs(
            conn,
            page=page,
            page_size=page_size,
            start_ts=start_ts,
            end_ts=end_ts,
            action_type=action_type,
            outcome=outcome,
            role=role,
            user=user,
        )


@router.post("/admin/audit/export")
def export_audit_logs(payload: AuditExportRequest, admin: dict = Depends(require_admin)):
    with get_db() as conn:
        listed = AuditService.list_logs(
            conn,
            page=1,
            page_size=5000,
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            action_type=payload.action_type,
            outcome=payload.outcome,
            role=payload.role,
            user=payload.user,
        )
        path = AuditService.export_logs(
            conn,
            listed["items"],
            redaction_profile=payload.redaction_profile,
            max_rows=payload.max_rows,
        )
        return {"status": "ok", "path": path, "rows": min(len(listed["items"]), payload.max_rows)}
