from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    agent_id: int
    ts: datetime
    alert_type: str
    severity: str
    file_path: str | None
    previous_sha256: str | None
    new_sha256: str | None
    message: str
    status: str
