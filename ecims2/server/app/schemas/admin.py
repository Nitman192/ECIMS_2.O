from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class BaselineApproveRequest(BaseModel):
    agent_id: int = Field(gt=0)
    file_path: str = Field(min_length=1, max_length=1024)
    approve_sha256: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=1, max_length=512)

    @field_validator("file_path")
    @classmethod
    def sanitize_file_path(cls, value: str) -> str:
        cleaned = value.replace("\\", "/").strip()
        if ".." in cleaned:
            raise ValueError("file_path traversal is not allowed")
        return cleaned

    @field_validator("approve_sha256")
    @classmethod
    def validate_sha(cls, value: str) -> str:
        lowered = value.lower()
        if any(c not in "0123456789abcdef" for c in lowered):
            raise ValueError("approve_sha256 must be hex")
        return lowered
