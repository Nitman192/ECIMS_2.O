from __future__ import annotations

from app.licensing_core.models import LicenseReason, LicenseState

_LICENSE_STATE = LicenseState(
    valid=False,
    reason=LicenseReason.NO_LICENSE_LOADED.value,
    payload=None,
    loaded_at_utc=None,
    machine_match=None,
    local_fingerprint_short=None,
)


def set_license_state(state: LicenseState) -> None:
    global _LICENSE_STATE
    _LICENSE_STATE = state


def get_license_state() -> LicenseState:
    return _LICENSE_STATE
