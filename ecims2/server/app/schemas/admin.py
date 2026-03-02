from __future__ import annotations

from pydantic import BaseModel, Field


class BaselineApproveRequest(BaseModel):
    agent_id: int = Field(gt=0)
    file_path: str = Field(min_length=1, max_length=4096)
    approve_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    reason: str = Field(min_length=1, max_length=512)


class AgentRevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)


class AuditExportRequest(BaseModel):
    start_ts: str | None = None
    end_ts: str | None = None
    action_type: str | None = None
    outcome: str | None = None
    role: str | None = None
    user: str | None = None
    redaction_profile: str = Field(default="standard", pattern=r"^(standard|strict)$")
    max_rows: int = Field(default=5000, ge=1, le=100000)


class DeviceUnblockRequestCreate(BaseModel):
    agent_id: int = Field(gt=0)
    device_id: str = Field(min_length=1, max_length=255)
    vid: str = Field(min_length=1, max_length=32)
    pid: str = Field(min_length=1, max_length=32)
    serial: str | None = Field(default=None, max_length=255)
    justification: str = Field(min_length=5, max_length=1024)


class DeviceUnblockApproveRequest(BaseModel):
    request_id: int = Field(gt=0)
    approved: bool = True
    reason: str = Field(min_length=1, max_length=1024)


class DeviceAllowTokenIssueRequest(BaseModel):
    agent_id: int = Field(gt=0)
    duration_minutes: int = Field(gt=0, le=1440)
    vid: str | None = None
    pid: str | None = None
    serial: str | None = None
    justification: str = Field(min_length=1, max_length=1024)


class DeviceAllowTokenRevokeRequest(BaseModel):
    token_id: str = Field(min_length=1, max_length=128)


class DeviceKillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = Field(min_length=1, max_length=1024)


class DeviceSetAgentModeRequest(BaseModel):
    agent_id: int = Field(gt=0)
    mode: str = Field(pattern=r"^(observe|enforce)$")
    reason: str = Field(min_length=1, max_length=1024)
