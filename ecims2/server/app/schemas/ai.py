from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AITrainRequest(BaseModel):
    model_name: Literal["isolation_forest", "one_class_svm"] = "isolation_forest"
    model_version: str = "1.0"
    window_minutes: int = Field(default=60, ge=1, le=1440)
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class AIScoreRunRequest(BaseModel):
    model_id: int = Field(gt=0)
    end_ts: datetime | None = None
    lookback_windows: int = Field(default=1, ge=1, le=168)
