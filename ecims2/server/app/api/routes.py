from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

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
from app.models.user import UserRole
from app.schemas.admin import (
    AgentRevokeRequest,
    AuditExportRequest,
    BaselineApproveRequest,
    EvidenceCustodyEventCreateRequest,
    EvidenceExportRequest,
    EvidenceObjectCreateRequest,
    EnrollmentTokenIssueRequest,
    EnrollmentTokenRevokeRequest,
    DeviceAllowTokenIssueRequest,
    DeviceAllowTokenRevokeRequest,
    DeviceKillSwitchRequest,
    DeviceSetAgentModeRequest,
    FeatureFlagCreateRequest,
    FeatureFlagSetStateRequest,
    MaintenanceScheduleCreateRequest,
    MaintenanceSchedulePreviewRequest,
    MaintenanceScheduleStateUpdateRequest,
    OfflineEnrollmentKitImportRequest,
    RemoteActionTaskCreateRequest,
    DeviceUnblockApproveRequest,
    DeviceUnblockRequestCreate,
)
from app.schemas.ai import AIScoreRunRequest, AITrainRequest
from app.schemas.agent import (
    AgentCommandAckRequest,
    AgentEnrollRequest,
    AgentCommandOut,
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentSummary,
)
from app.schemas.alert import AlertOut
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.event import EventBatchRequest, EventBatchResponse
from app.schemas.user import (
    AdminUserActiveUpdateRequest,
    AdminUserCreateRequest,
    AdminUserResetPasswordRequest,
    AdminUserRoleUpdateRequest,
    SelfPasswordResetRequest,
    UserOut,
)
from app.security.auth import create_access_token
from app.security.mtls import require_mtls_client_identity
from app.services.agent_command_service import AgentCommandService
from app.services.agent_service import AgentService
from app.services.alert_service import AlertService
from app.services.audit_service import AuditService
from app.services.device_allow_token_service import DeviceAllowTokenService
from app.services.device_control_state_service import DeviceControlStateService
from app.services.device_policy_service import DevicePolicyService
from app.services.enrollment_service import EnrollmentService
from app.services.evidence_vault_service import EvidenceVaultService
from app.services.event_service import EventService
from app.services.feature_flag_service import FeatureFlagService
from app.services.maintenance_schedule_service import MaintenanceScheduleService
from app.services.remote_action_task_service import RemoteActionTaskService
from app.services.retention_service import RetentionService
from app.services.user_service import UserService
from app.utils.time import utcnow
from app.utils.request_context import REQUEST_ID

router = APIRouter()


def _to_user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"],
        username=user["username"],
        role=user["role"],
        is_active=user["is_active"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
        last_login_at=user["last_login_at"],
        must_reset_password=bool(user["must_reset_password"]),
    )


def _raise_feature_flag_error(exc: ValueError) -> None:
    code = str(exc)
    if code == "INVALID_SCOPE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid scope") from exc
    if code == "INVALID_SCOPE_TARGET":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scope target is required") from exc
    if code == "INVALID_RISK_LEVEL":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid risk level") from exc
    if code == "INVALID_REASON_CODE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reason code") from exc
    if code == "FLAG_KEY_RESERVED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flag key is reserved") from exc
    if code == "FLAG_ALREADY_EXISTS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Flag already exists for scope") from exc
    if code == "RISK_CONFIRMATION_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Risky toggle requires explicit confirmation",
        ) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc


def _raise_remote_action_error(exc: ValueError) -> None:
    code = str(exc)
    if code == "INVALID_ACTION":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action") from exc
    if code == "INVALID_STATUS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status") from exc
    if code == "INVALID_REASON_CODE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reason code") from exc
    if code == "HIGH_RISK_CONFIRMATION_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="High-risk action requires explicit confirmation",
        ) from exc
    if code == "BATCH_TOO_LARGE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch size exceeds safe limit (100)") from exc
    if code == "INVALID_AGENT_IDS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one valid agent ID is required") from exc
    if code == "INVALID_IDEMPOTENCY_KEY":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid idempotency key") from exc
    if code == "METADATA_TOO_LARGE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Metadata payload too large") from exc
    if code == "IDEMPOTENCY_KEY_CONFLICT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used with a different payload",
        ) from exc
    if code.startswith("MISSING_AGENTS:"):
        missing = code.split(":", 1)[1]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent not found: {missing}") from exc
    if code.startswith("REVOKED_AGENTS:"):
        revoked = code.split(":", 1)[1]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Agent revoked: {revoked}") from exc
    if code == "TASK_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found") from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc


def _raise_schedule_error(exc: ValueError) -> None:
    code = str(exc)
    if code == "INVALID_STATUS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid schedule status") from exc
    if code == "INVALID_REASON_CODE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reason code") from exc
    if code == "INVALID_TIMEZONE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timezone") from exc
    if code == "INVALID_TIME_FORMAT":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid local start time format") from exc
    if code == "INVALID_RECURRENCE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recurrence") from exc
    if code == "INVALID_WEEKLY_DAYS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Weekly schedules require valid weekday list (0-6)") from exc
    if code == "INVALID_ORCHESTRATION_MODE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid orchestration mode") from exc
    if code == "INVALID_DURATION":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duration must be between 15 and 1440 minutes") from exc
    if code == "INVALID_AGENT_IDS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one valid agent ID is required") from exc
    if code == "BATCH_TOO_LARGE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target agent list exceeds safe limit (100)") from exc
    if code == "INVALID_IDEMPOTENCY_KEY":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid idempotency key") from exc
    if code == "IDEMPOTENCY_KEY_CONFLICT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key already used with different payload") from exc
    if code.startswith("MISSING_AGENTS:"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent not found: {code.split(':', 1)[1]}") from exc
    if code.startswith("REVOKED_AGENTS:"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Agent revoked: {code.split(':', 1)[1]}") from exc
    if code.startswith("CONFLICT_DETECTED:"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule conflict detected with schedule IDs: {code.split(':', 1)[1]}",
        ) from exc
    if code == "SCHEDULE_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found") from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc


def _raise_enrollment_error(exc: ValueError) -> None:
    code = str(exc)
    if code == "INVALID_MODE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid enrollment mode") from exc
    if code == "INVALID_STATUS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid enrollment status") from exc
    if code == "INVALID_REASON_CODE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reason code") from exc
    if code == "INVALID_MAX_USES":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Max uses must be between 1 and 1000") from exc
    if code == "INVALID_EXPIRY":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expiry must be between 1 and 720 hours") from exc
    if code == "INVALID_IDEMPOTENCY_KEY":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid idempotency key") from exc
    if code == "IDEMPOTENCY_KEY_CONFLICT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used with a different payload",
        ) from exc
    if code == "KIT_INVALID":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid offline enrollment kit bundle") from exc
    if code == "KIT_CONFLICT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Offline kit conflict detected") from exc
    if code == "TOKEN_CONFLICT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Enrollment token conflict detected") from exc
    if code == "TOKEN_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment token not found") from exc
    if code == "TOKEN_INVALID":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid enrollment token") from exc
    if code == "TOKEN_REVOKED":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enrollment token is revoked") from exc
    if code == "TOKEN_EXPIRED":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enrollment token is expired") from exc
    if code == "TOKEN_CONSUMED":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enrollment token is fully consumed") from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc


def _raise_evidence_error(exc: ValueError) -> None:
    code = str(exc)
    if code == "INVALID_HASH":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid object hash format") from exc
    if code == "INVALID_HASH_ALGORITHM":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hash algorithm") from exc
    if code == "INVALID_ORIGIN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid origin type") from exc
    if code == "INVALID_CLASSIFICATION":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid classification") from exc
    if code == "INVALID_STATUS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid evidence status") from exc
    if code == "INVALID_IDEMPOTENCY_KEY":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid idempotency key") from exc
    if code == "IDEMPOTENCY_KEY_CONFLICT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already used with a different payload",
        ) from exc
    if code == "EVIDENCE_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found") from exc
    if code == "INVALID_EVENT_TYPE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid custody event type") from exc
    if code == "INVALID_TRANSITION":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invalid evidence state transition") from exc
    if code == "INVALID_DETAILS":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event details payload") from exc
    if code == "INVALID_METADATA":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid evidence metadata payload") from exc
    if code == "INVALID_MANIFEST":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid manifest payload") from exc
    if code == "INVALID_REASON":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reason must be at least 5 characters") from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc


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

    UserService.mark_login_success(user["id"])
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
    return TokenResponse(access_token=token, must_reset_password=bool(user["must_reset_password"]))


@router.get("/auth/me", response_model=UserOut)
def auth_me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return _to_user_out(current_user)


@router.post("/auth/password/reset")
def auth_password_reset(payload: SelfPasswordResetRequest, current_user: dict = Depends(get_current_user)):
    try:
        UserService.change_own_password(
            current_user["id"],
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "INVALID_CURRENT_PASSWORD":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password") from exc
        if detail == "USER_NOT_FOUND":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return {"status": "ok"}


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


@router.post("/agents/enroll", response_model=AgentRegisterResponse)
def enroll_agent(
    payload: AgentEnrollRequest,
    request: Request,
    _: None = Depends(require_registration_allowed),
) -> AgentRegisterResponse:
    require_mtls_client_identity(request, claimed_agent_id=None)
    try:
        consumed = EnrollmentService.consume_token_for_enrollment(
            token_value=payload.enrollment_token,
            agent_name=payload.name,
            hostname=payload.hostname,
            source="AGENT_ENROLL",
        )
    except ValueError as exc:
        _raise_enrollment_error(exc)

    agent_id, token = AgentService.register_agent(payload.name, payload.hostname)

    with get_db() as conn:
        use_row = conn.execute(
            """
            SELECT id
            FROM enrollment_token_uses
            WHERE token_id = ? AND agent_id IS NULL AND source = 'AGENT_ENROLL'
              AND hostname = ? AND agent_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (consumed["token_id"], payload.hostname.strip(), payload.name.strip()),
        ).fetchone()
        if use_row:
            conn.execute(
                "UPDATE enrollment_token_uses SET agent_id = ? WHERE id = ?",
                (agent_id, int(use_row["id"])),
            )
        AuditService.log(
            conn,
            actor_type="AGENT",
            actor_id=agent_id,
            action="AGENT_ENROLLED_WITH_TOKEN",
            target_type="ENROLLMENT_TOKEN",
            target_id=consumed["token_id"],
            message="Agent enrolled using enrollment token",
            metadata={
                "token_status": consumed["status"],
                "used_count": consumed["used_count"],
                "max_uses": consumed["max_uses"],
                "hostname": payload.hostname.strip(),
            },
        )
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


@router.get("/admin/users", response_model=list[UserOut])
def admin_list_users(
    include_inactive: bool = Query(default=True),
    admin: dict = Depends(require_admin),
):
    users = UserService.list_users(include_inactive=include_inactive)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="USER_LIST_VIEWED",
            target_type="USER",
            target_id="all",
            message="Admin viewed users list",
            metadata={"include_inactive": include_inactive, "count": len(users)},
        )
    return [_to_user_out(user) for user in users]


@router.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user(payload: AdminUserCreateRequest, admin: dict = Depends(require_admin)):
    try:
        user_id = UserService.create_user(
            payload.username,
            payload.password,
            payload.role,
            actor_id=admin["id"],
            is_active=payload.is_active,
            must_reset_password=payload.must_reset_password,
        )
    except ValueError as exc:
        if str(exc) == "USERNAME_ALREADY_EXISTS":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc
        raise

    created = UserService.get_by_id(user_id)
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User creation failed")
    return _to_user_out(created)


@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def admin_update_user_role(user_id: int, payload: AdminUserRoleUpdateRequest, admin: dict = Depends(require_admin)):
    target = UserService.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_id == admin["id"] and payload.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove own admin role")

    if not UserService.update_role(
        user_id,
        payload.role,
        actor_id=admin["id"],
        reason="Updated from admin console",
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updated = UserService.get_by_id(user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_user_out(updated)


@router.patch("/admin/users/{user_id}/active", response_model=UserOut)
def admin_update_user_active_state(
    user_id: int,
    payload: AdminUserActiveUpdateRequest,
    admin: dict = Depends(require_admin),
):
    target = UserService.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_id == admin["id"] and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable own account")

    if (
        target["role"] == UserRole.ADMIN.value
        and target["is_active"]
        and not payload.is_active
        and UserService.count_active_admins(exclude_user_id=user_id) == 0
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable last active admin")

    if not UserService.set_active(
        user_id,
        is_active=payload.is_active,
        actor_id=admin["id"],
        reason=payload.reason,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updated = UserService.get_by_id(user_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_user_out(updated)


@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    payload: AdminUserResetPasswordRequest,
    admin: dict = Depends(require_admin),
):
    target = UserService.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not UserService.reset_password(
        user_id,
        new_password=payload.new_password,
        must_reset_password=payload.must_reset_password,
        actor_id=admin["id"],
        reason=payload.reason,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"status": "ok", "must_reset_password": payload.must_reset_password}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    reason: str = Query(default="Deleted from admin console", min_length=1, max_length=512),
    admin: dict = Depends(require_admin),
):
    target = UserService.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_id == admin["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete own account")

    if (
        target["role"] == UserRole.ADMIN.value
        and target["is_active"]
        and UserService.count_active_admins(exclude_user_id=user_id) == 0
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete last active admin")

    try:
        deleted = UserService.delete_user(user_id, actor_id=admin["id"], reason=reason)
    except ValueError as exc:
        if str(exc) == "USER_DELETE_CONFLICT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User cannot be deleted because related records exist",
            ) from exc
        raise
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"status": "deleted", "user_id": user_id}


@router.get("/admin/features")
def admin_list_feature_flags(
    q: str | None = Query(default=None, max_length=128),
    scope: str | None = Query(default=None),
    state: str | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    try:
        items = FeatureFlagService.list_flags(query=q, scope=scope, state=state)
    except ValueError as exc:
        _raise_feature_flag_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="FEATURE_FLAG_LIST_VIEWED",
            target_type="FEATURE_FLAG",
            target_id="all",
            message="Admin viewed feature flags",
            metadata={"count": len(items), "query": q, "scope": scope, "state": state},
        )
    return {"items": items, "total": len(items)}


@router.post("/admin/features", status_code=status.HTTP_201_CREATED)
def admin_create_feature_flag(payload: FeatureFlagCreateRequest, admin: dict = Depends(require_admin)):
    try:
        created = FeatureFlagService.create_flag(
            key=payload.key,
            description=payload.description,
            scope=payload.scope,
            scope_target=payload.scope_target,
            is_enabled=payload.is_enabled,
            risk_level=payload.risk_level,
            reason_code=payload.reason_code,
            reason=payload.reason,
            confirm_risky=payload.confirm_risky,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_feature_flag_error(exc)
    return created


@router.put("/admin/features/{flag_id}/state")
def admin_set_feature_flag_state(
    flag_id: int,
    payload: FeatureFlagSetStateRequest,
    admin: dict = Depends(require_admin),
):
    try:
        updated = FeatureFlagService.set_flag_state(
            flag_id=flag_id,
            enabled=payload.enabled,
            reason_code=payload.reason_code,
            reason=payload.reason,
            confirm_risky=payload.confirm_risky,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_feature_flag_error(exc)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return updated


@router.get("/admin/ops/remote-actions/tasks")
def admin_list_remote_action_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=128),
    admin: dict = Depends(require_admin),
):
    try:
        payload = RemoteActionTaskService.list_tasks(
            page=page,
            page_size=page_size,
            action=action,
            status=status_filter,
            query=q,
        )
    except ValueError as exc:
        _raise_remote_action_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="REMOTE_ACTION_TASK_LIST_VIEWED",
            target_type="AGENT_TASK",
            target_id="all",
            message="Admin viewed remote action tasks",
            metadata={
                "page": page,
                "page_size": page_size,
                "action": action,
                "status": status_filter,
                "query": q,
                "count": len(payload["items"]),
            },
        )
    return payload


@router.get("/admin/ops/remote-actions/tasks/{task_id}/targets")
def admin_list_remote_action_task_targets(task_id: int, admin: dict = Depends(require_admin)):
    task = RemoteActionTaskService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    items = RemoteActionTaskService.list_task_targets(task_id)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="REMOTE_ACTION_TASK_TARGETS_VIEWED",
            target_type="AGENT_TASK",
            target_id=task_id,
            message="Admin viewed remote action task targets",
            metadata={"count": len(items)},
        )
    return {"task": task, "items": items, "total": len(items)}


@router.post("/admin/ops/remote-actions/tasks", status_code=status.HTTP_201_CREATED)
def admin_create_remote_action_task(
    payload: RemoteActionTaskCreateRequest,
    response: Response,
    admin: dict = Depends(require_admin),
):
    try:
        task, created = RemoteActionTaskService.create_task(
            action=payload.action,
            agent_ids=payload.agent_ids,
            idempotency_key=payload.idempotency_key,
            reason_code=payload.reason_code,
            reason=payload.reason,
            confirm_high_risk=payload.confirm_high_risk,
            metadata=payload.metadata,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_remote_action_error(exc)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"item": task, "created": created}


@router.get("/admin/ops/schedules")
def admin_list_maintenance_schedules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    timezone_filter: str | None = Query(default=None, alias="timezone"),
    q: str | None = Query(default=None, max_length=128),
    admin: dict = Depends(require_admin),
):
    try:
        payload = MaintenanceScheduleService.list_schedules(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            timezone_filter=timezone_filter,
            query=q,
        )
    except ValueError as exc:
        _raise_schedule_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="MAINTENANCE_SCHEDULE_LIST_VIEWED",
            target_type="MAINTENANCE_SCHEDULE",
            target_id="all",
            message="Admin viewed maintenance schedule list",
            metadata={
                "page": page,
                "page_size": page_size,
                "status": status_filter,
                "timezone": timezone_filter,
                "query": q,
                "count": len(payload["items"]),
            },
        )
    return payload


@router.post("/admin/ops/schedules", status_code=status.HTTP_201_CREATED)
def admin_create_maintenance_schedule(
    payload: MaintenanceScheduleCreateRequest,
    response: Response,
    admin: dict = Depends(require_admin),
):
    try:
        item, created = MaintenanceScheduleService.create_schedule(
            window_name=payload.window_name,
            timezone_name=payload.timezone,
            start_time_local=payload.start_time_local,
            duration_minutes=payload.duration_minutes,
            recurrence=payload.recurrence,
            weekly_days=payload.weekly_days,
            target_agent_ids=payload.target_agent_ids,
            orchestration_mode=payload.orchestration_mode,
            status_value=payload.status,
            reason_code=payload.reason_code,
            reason=payload.reason,
            allow_conflicts=payload.allow_conflicts,
            idempotency_key=payload.idempotency_key,
            metadata=payload.metadata,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_schedule_error(exc)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"item": item, "created": created}


@router.post("/admin/ops/schedules/preview")
def admin_preview_maintenance_schedule(
    payload: MaintenanceSchedulePreviewRequest,
    admin: dict = Depends(require_admin),
):
    try:
        result = MaintenanceScheduleService.preview_schedule(
            window_name=payload.window_name,
            timezone_name=payload.timezone,
            start_time_local=payload.start_time_local,
            duration_minutes=payload.duration_minutes,
            recurrence=payload.recurrence,
            weekly_days=payload.weekly_days,
            target_agent_ids=payload.target_agent_ids,
            orchestration_mode=payload.orchestration_mode,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        _raise_schedule_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="MAINTENANCE_SCHEDULE_PREVIEWED",
            target_type="MAINTENANCE_SCHEDULE",
            target_id="preview",
            message="Maintenance schedule preview generated",
            metadata={"conflict_count": result["conflict_count"]},
        )
    return result


@router.post("/admin/ops/schedules/run-due")
def admin_run_due_maintenance_schedules(
    limit: int = Query(default=20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    result = MaintenanceScheduleService.run_due_schedules(actor_id=admin["id"], limit=limit)
    return result


@router.get("/admin/ops/schedules/{schedule_id}/conflicts")
def admin_get_maintenance_schedule_conflicts(schedule_id: int, admin: dict = Depends(require_admin)):
    try:
        conflicts = MaintenanceScheduleService.get_schedule_conflicts(schedule_id)
    except ValueError as exc:
        _raise_schedule_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="MAINTENANCE_SCHEDULE_CONFLICTS_VIEWED",
            target_type="MAINTENANCE_SCHEDULE",
            target_id=schedule_id,
            message="Maintenance schedule conflicts viewed",
            metadata={"count": len(conflicts)},
        )
    return {"schedule_id": schedule_id, "conflicts": conflicts, "total": len(conflicts)}


@router.post("/admin/ops/schedules/{schedule_id}/state")
def admin_update_maintenance_schedule_state(
    schedule_id: int,
    payload: MaintenanceScheduleStateUpdateRequest,
    admin: dict = Depends(require_admin),
):
    try:
        item = MaintenanceScheduleService.update_schedule_state(
            schedule_id=schedule_id,
            status_value=payload.status,
            reason=payload.reason,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_schedule_error(exc)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return item


@router.get("/admin/ops/enrollment/tokens")
def admin_list_enrollment_tokens(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    mode_filter: str | None = Query(default=None, alias="mode"),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=128),
    admin: dict = Depends(require_admin),
):
    try:
        payload = EnrollmentService.list_tokens(
            page=page,
            page_size=page_size,
            mode_filter=mode_filter,
            status_filter=status_filter,
            query=q,
        )
    except ValueError as exc:
        _raise_enrollment_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="ENROLLMENT_TOKEN_LIST_VIEWED",
            target_type="ENROLLMENT_TOKEN",
            target_id="all",
            message="Admin viewed enrollment token list",
            metadata={
                "page": page,
                "page_size": page_size,
                "mode": mode_filter,
                "status": status_filter,
                "query": q,
                "count": len(payload["items"]),
            },
        )
    return payload


@router.post("/admin/ops/enrollment/tokens", status_code=status.HTTP_201_CREATED)
def admin_issue_enrollment_token(
    payload: EnrollmentTokenIssueRequest,
    response: Response,
    admin: dict = Depends(require_admin),
):
    try:
        item, created, token_value, cli, offline_kit_bundle = EnrollmentService.issue_token(
            mode=payload.mode,
            expires_in_hours=payload.expires_in_hours,
            max_uses=payload.max_uses,
            reason_code=payload.reason_code,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            metadata=payload.metadata,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_enrollment_error(exc)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {
        "item": item,
        "created": created,
        "enrollment_token": token_value,
        "cli_snippets": cli,
        "offline_kit_bundle": offline_kit_bundle,
    }


@router.post("/admin/ops/enrollment/tokens/{token_id}/revoke")
def admin_revoke_enrollment_token(
    token_id: str,
    payload: EnrollmentTokenRevokeRequest,
    admin: dict = Depends(require_admin),
):
    item = EnrollmentService.revoke_token(token_id=token_id, reason=payload.reason, actor_id=admin["id"])
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment token not found")
    return {"status": "revoked", "item": item}


@router.post("/admin/ops/enrollment/offline-kit/import")
def admin_import_offline_enrollment_kit(
    payload: OfflineEnrollmentKitImportRequest,
    admin: dict = Depends(require_admin),
):
    try:
        item, created_token, created_kit = EnrollmentService.import_offline_kit(
            bundle=payload.bundle,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_enrollment_error(exc)
    return {"item": item, "created_token": created_token, "created_kit": created_kit}


@router.get("/admin/ops/evidence-vault")
def admin_list_evidence_vault_objects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    origin_filter: str | None = Query(default=None, alias="origin"),
    q: str | None = Query(default=None, max_length=128),
    admin: dict = Depends(require_admin),
):
    try:
        payload = EvidenceVaultService.list_evidence(
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            origin_filter=origin_filter,
            query=q,
        )
    except ValueError as exc:
        _raise_evidence_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="EVIDENCE_VAULT_LIST_VIEWED",
            target_type="EVIDENCE",
            target_id="all",
            message="Admin viewed evidence vault listing",
            metadata={
                "page": page,
                "page_size": page_size,
                "status": status_filter,
                "origin": origin_filter,
                "query": q,
                "count": len(payload["items"]),
            },
        )
    return payload


@router.post("/admin/ops/evidence-vault", status_code=status.HTTP_201_CREATED)
def admin_create_evidence_vault_object(
    payload: EvidenceObjectCreateRequest,
    response: Response,
    admin: dict = Depends(require_admin),
):
    try:
        item, created = EvidenceVaultService.create_evidence(
            object_hash=payload.object_hash,
            hash_algorithm=payload.hash_algorithm,
            origin_type=payload.origin_type,
            origin_ref=payload.origin_ref,
            classification=payload.classification,
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
            manifest=payload.manifest,
            metadata=payload.metadata,
            actor_id=admin["id"],
            actor_role=admin["role"],
        )
    except ValueError as exc:
        _raise_evidence_error(exc)
    if not created:
        response.status_code = status.HTTP_200_OK
    return {"item": item, "created": created}


@router.get("/admin/ops/evidence-vault/{evidence_id}")
def admin_get_evidence_vault_object(evidence_id: str, admin: dict = Depends(require_admin)):
    item = EvidenceVaultService.get_evidence(evidence_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="EVIDENCE_OBJECT_VIEWED",
            target_type="EVIDENCE",
            target_id=evidence_id,
            message="Admin viewed evidence object details",
            metadata={},
        )
    return item


@router.get("/admin/ops/evidence-vault/{evidence_id}/timeline")
def admin_get_evidence_vault_timeline(evidence_id: str, admin: dict = Depends(require_admin)):
    try:
        timeline = EvidenceVaultService.get_timeline(evidence_id)
    except ValueError as exc:
        _raise_evidence_error(exc)
    with get_db() as conn:
        AuditService.log(
            conn,
            actor_type="ADMIN",
            actor_id=admin["id"],
            action="EVIDENCE_TIMELINE_VIEWED",
            target_type="EVIDENCE",
            target_id=evidence_id,
            message="Admin viewed evidence custody timeline",
            metadata={"total": timeline["total"], "chain_valid": timeline["chain_valid"]},
        )
    return timeline


@router.post("/admin/ops/evidence-vault/{evidence_id}/custody")
def admin_append_evidence_vault_custody_event(
    evidence_id: str,
    payload: EvidenceCustodyEventCreateRequest,
    admin: dict = Depends(require_admin),
):
    try:
        item, event = EvidenceVaultService.append_custody_event(
            evidence_id=evidence_id,
            event_type=payload.event_type,
            reason=payload.reason,
            details=payload.details,
            actor_id=admin["id"],
            actor_role=admin["role"],
        )
    except ValueError as exc:
        _raise_evidence_error(exc)
    return {"item": item, "event": event}


@router.post("/admin/ops/evidence-vault/{evidence_id}/export")
def admin_export_evidence_vault_bundle(
    evidence_id: str,
    payload: EvidenceExportRequest,
    admin: dict = Depends(require_admin),
):
    try:
        result = EvidenceVaultService.export_evidence_bundle(
            evidence_id=evidence_id,
            reason=payload.reason,
            actor_id=admin["id"],
            actor_role=admin["role"],
        )
    except ValueError as exc:
        _raise_evidence_error(exc)
    return result




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
    try:
        FeatureFlagService.set_builtin_kill_switch(
            enabled=payload.enabled,
            reason=payload.reason,
            actor_id=admin["id"],
        )
    except ValueError as exc:
        _raise_feature_flag_error(exc)
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
