"""UI-only operator role definitions and action permissions."""

from __future__ import annotations

from dataclasses import dataclass

ROLE_ADMIN = "Admin"
ROLE_OPERATOR = "Operator"
ROLE_AUDITOR = "Auditor"
ALL_ROLES = [ROLE_ADMIN, ROLE_OPERATOR, ROLE_AUDITOR]


@dataclass(frozen=True, slots=True)
class RoleDecision:
    allowed: bool
    reason: str = ""


_OPERATOR_DENY = {
    "root.generate",
    "mtls.ca.generate",
    "data.rotate",
    "activity.export",
}

_AUDITOR_ALLOW = {
    "audit.refresh",
    "audit.verify",
    "license.verify",
    "revocation.verify",
    "activity.refresh",
    "activity.export",
    "wizard.open_root",
    "wizard.open_license",
    "wizard.open_mtls",
    "wizard.open_data",
    "wizard.audit",
}


def can_perform(role: str, action_id: str | None) -> RoleDecision:
    """Check whether role can execute a UI action id."""
    if not action_id:
        return RoleDecision(True)

    if role == ROLE_ADMIN:
        return RoleDecision(True)

    if role == ROLE_OPERATOR:
        if action_id in _OPERATOR_DENY:
            return RoleDecision(False, "Disabled for Operator role")
        return RoleDecision(True)

    if role == ROLE_AUDITOR:
        if action_id in _AUDITOR_ALLOW:
            return RoleDecision(True)
        return RoleDecision(False, "Read-only in Auditor role")

    return RoleDecision(False, "Unknown role")
