from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)


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
