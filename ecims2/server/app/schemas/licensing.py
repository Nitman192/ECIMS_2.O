from __future__ import annotations

from pydantic import BaseModel, Field


class ActivationLicenseKeyRequest(BaseModel):
    license_key: str = Field(min_length=10, max_length=262144)


class ActivationIssueRequest(BaseModel):
    force_new: bool = True


class ActivationVerificationRequest(BaseModel):
    verification_id: str = Field(min_length=16, max_length=8192)
