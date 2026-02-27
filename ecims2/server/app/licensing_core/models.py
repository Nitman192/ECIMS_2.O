from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LicenseReason(str, Enum):
    OK = "OK"
    NO_LICENSE_FILE = "NO_LICENSE_FILE"
    INVALID_JSON = "INVALID_JSON"
    NO_PUBLIC_KEY = "NO_PUBLIC_KEY"
    INVALID_SIGNATURE_ENCODING = "INVALID_SIGNATURE_ENCODING"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    EXPIRED = "EXPIRED"
    MACHINE_MISMATCH = "MACHINE_MISMATCH"
    TAMPER_DETECTED = "TAMPER_DETECTED"
    NO_LICENSE_LOADED = "NO_LICENSE_LOADED"


@dataclass
class LicensePayload:
    org_name: str
    max_agents: int
    expiry_date: str
    ai_enabled: bool
    machine_fingerprint: str | None = None
    license_id: str | None = None
    customer_name: str | None = None


@dataclass
class LicenseState:
    valid: bool
    reason: str
    payload: LicensePayload | None
    loaded_at_utc: str | None
    machine_match: bool | None = None
    local_fingerprint_short: str | None = None
