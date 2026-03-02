from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class USBDetectionEventDetails(BaseModel):
    device_id: str = Field(min_length=1, max_length=255)
    vid: str = Field(min_length=1, max_length=32)
    pid: str = Field(min_length=1, max_length=32)
    serial: str | None = Field(default=None, max_length=255)
    bus: str | None = Field(default=None, max_length=128)
    vendor_name: str | None = Field(default=None, max_length=255)
    product_name: str | None = Field(default=None, max_length=255)
    first_seen_ts: datetime | None = None


class USBControlDecision(BaseModel):
    action: str = Field(pattern=r"^(BLOCK|ALLOW|TEMP_ALLOW)$")
    reason: str = Field(min_length=1, max_length=255)
    temporary_allow_minutes: int | None = Field(default=None, ge=1)
    policy_source: str = Field(min_length=1, max_length=64)
