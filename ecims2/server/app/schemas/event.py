from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"


class EventType(str, Enum):
    FILE_PRESENT = "FILE_PRESENT"
    FILE_DELETED = "FILE_DELETED"


class LegacyFileEvent(BaseModel):
    ts: datetime
    event_type: EventType
    file_path: str = Field(min_length=1, max_length=1024)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    details_json: dict[str, Any] | None = None

    @field_validator("file_path")
    @classmethod
    def sanitize_file_path(cls, value: str) -> str:
        cleaned = value.replace("\\", "/").strip()
        if ".." in cleaned:
            raise ValueError("file_path traversal is not allowed")
        return cleaned

    @field_validator("sha256")
    @classmethod
    def validate_sha(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("sha256 must be hex")
        return value.lower()


class FileEventV1(BaseModel):
    schema_version: Literal[SCHEMA_VERSION]
    ts: datetime
    event_type: EventType
    file_path: str = Field(min_length=1, max_length=1024)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    file_size_bytes: int | None = Field(default=None, ge=0)
    mtime_epoch: float | None = None
    user: str | None = Field(default=None, max_length=255)
    process_name: str | None = Field(default=None, max_length=255)
    host_ip: str | None = Field(default=None, max_length=64)
    details_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("file_path")
    @classmethod
    def sanitize_file_path(cls, value: str) -> str:
        cleaned = value.replace("\\", "/").strip()
        if ".." in cleaned:
            raise ValueError("file_path traversal is not allowed")
        return cleaned

    @field_validator("sha256")
    @classmethod
    def validate_sha(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("sha256 must be hex")
        return value.lower()

    @field_validator("details_json")
    @classmethod
    def validate_details_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(str(value)) > 4096:
            raise ValueError("details_json too large")
        return value

    @model_validator(mode="after")
    def validate_by_event_type(self) -> "FileEventV1":
        if self.event_type == EventType.FILE_PRESENT and not self.sha256:
            raise ValueError("sha256 is required for FILE_PRESENT")
        return self

    def normalized_ts(self) -> str:
        ts = self.ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        return ts.isoformat()


class EventBatchRequest(BaseModel):
    agent_id: int = Field(gt=0)
    events: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


class EventBatchResponse(BaseModel):
    processed: int
    alerts_created: int
