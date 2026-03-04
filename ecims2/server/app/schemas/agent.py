from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)


class AgentEnrollRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    enrollment_token: str = Field(min_length=12, max_length=512)


class AgentRegisterResponse(BaseModel):
    agent_id: int
    token: str


class AgentHeartbeatRequest(BaseModel):
    agent_id: int = Field(gt=0)


class AgentSummary(BaseModel):
    id: int
    name: str
    hostname: str
    registered_at: datetime
    last_seen: datetime | None
    status: str
    agent_revoked: bool


class AgentCommandOut(BaseModel):
    id: int
    agent_id: int
    type: str
    payload: dict[str, Any]
    status: str
    created_at: str


class AgentCommandAckRequest(BaseModel):
    applied: bool
    error: str | None = Field(default=None, max_length=1024)
