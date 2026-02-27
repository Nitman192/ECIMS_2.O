from __future__ import annotations

from pydantic import BaseModel, Field


class BaselineApproveRequest(BaseModel):
    agent_id: int = Field(gt=0)
    file_path: str = Field(min_length=1, max_length=4096)
    approve_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    reason: str = Field(min_length=1, max_length=512)


class AgentRevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)
