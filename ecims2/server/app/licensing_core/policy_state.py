from __future__ import annotations

from app.licensing_core.policy import DEFAULT_POLICY, PolicyLoadResult

_POLICY_STATE = PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_MISSING")


def set_policy_state(state: PolicyLoadResult) -> None:
    global _POLICY_STATE
    _POLICY_STATE = state


def get_policy_state() -> PolicyLoadResult:
    return _POLICY_STATE
