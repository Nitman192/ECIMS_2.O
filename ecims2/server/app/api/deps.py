from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.services.agent_service import AgentService


def validate_token(agent_id: int, x_ecims_token: str = Header(default="")) -> None:
    if not x_ecims_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-ECIMS-TOKEN")
    if not AgentService.validate_agent_token(agent_id, x_ecims_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")
