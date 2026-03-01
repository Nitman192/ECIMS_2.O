"""Data models for license authority core workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class LicensePayload:
    """Unsigned license payload fields."""

    serial: str
    customer: str
    issued_at: str
    expires_at: str
    max_agents: int
    public_key_fingerprint: str
    server_id: str | None = None
    features: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SignedLicense:
    """Signed license artifact."""

    serial: str
    customer: str
    issued_at: str
    expires_at: str
    max_agents: int
    public_key_fingerprint: str
    signed_payload_hash: str
    signature: str
    server_id: str | None = None
    features: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RevocationBundle:
    """Signed revocation list bundle."""

    issued_at: str
    revoked_serials: list[str]
    signature: str
