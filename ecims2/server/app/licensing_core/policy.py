from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.licensing_core.verifier import verify_signature


@dataclass
class USBAllowlistEntry:
    vid: str
    pid: str
    serial: str | None = None


@dataclass
class DeviceEnforcementRollout:
    strategy: Literal["all", "percent", "allowlist_agents", "tags"] = "all"
    percent: int = 100
    allowlist_agents: list[int] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class SecurityPolicy:
    mode: Literal["STRICT", "STANDARD"]
    allow_key_override: bool
    grace_days: int
    status_redaction_level: int
    allow_unsigned_dev: bool
    mtls_required: bool
    pinning_required: bool
    allow_tls12: bool
    allow_plain_https: bool
    mass_storage_default_action: Literal["block_on_insert", "allow"] = "block_on_insert"
    usb_allowlist: list[USBAllowlistEntry] = field(default_factory=list)
    temporary_allow_duration_minutes: int = 60
    escalation_threshold: int = 3
    device_enforcement_mode: Literal["observe", "enforce"] = "observe"
    mass_storage_offline_behavior: Literal["block"] = "block"
    allow_token_required_for_unblock: bool = True
    allow_token_max_duration_minutes: int = 240
    local_event_queue_retention_hours: int = 72
    token_public_key_path: str = "configs/device_allow_token_public.pem"
    device_enforcement_rollout: DeviceEnforcementRollout = field(default_factory=DeviceEnforcementRollout)
    device_kill_switch: bool = False
    per_agent_override_allowed: bool = True
    enforcement_grace_seconds: int = 0


@dataclass
class PolicyLoadResult:
    policy: SecurityPolicy
    source: str
    reason: str


DEFAULT_POLICY = SecurityPolicy(
    mode="STRICT",
    allow_key_override=False,
    grace_days=0,
    status_redaction_level=1,
    allow_unsigned_dev=False,
    mtls_required=True,
    pinning_required=True,
    allow_tls12=False,
    allow_plain_https=False,
    mass_storage_default_action="block_on_insert",
    usb_allowlist=[],
    temporary_allow_duration_minutes=60,
    escalation_threshold=3,
    device_enforcement_mode="observe",
    mass_storage_offline_behavior="block",
    allow_token_required_for_unblock=True,
    allow_token_max_duration_minutes=240,
    local_event_queue_retention_hours=72,
    token_public_key_path="configs/device_allow_token_public.pem",
    device_enforcement_rollout=DeviceEnforcementRollout(),
    device_kill_switch=False,
    per_agent_override_allowed=True,
    enforcement_grace_seconds=0,
)


def _canonical_policy_bytes(policy_dict: dict) -> bytes:
    return json.dumps(policy_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_allowlist(raw: object) -> list[USBAllowlistEntry] | None:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return None
    parsed: list[USBAllowlistEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        vid = str(item.get("vid", "")).strip().lower()
        pid = str(item.get("pid", "")).strip().lower()
        serial_raw = item.get("serial")
        serial = str(serial_raw).strip() if serial_raw is not None else None
        if not vid or not pid:
            return None
        parsed.append(USBAllowlistEntry(vid=vid, pid=pid, serial=serial or None))
    return parsed


def _parse_policy(raw: dict) -> SecurityPolicy | None:
    try:
        mode = str(raw.get("mode", "STRICT")).upper()
        if mode not in {"STRICT", "STANDARD"}:
            return None
        allow_key_override = bool(raw.get("allow_key_override", False))
        grace_days = max(0, int(raw.get("grace_days", 0)))
        status_redaction_level = max(0, int(raw.get("status_redaction_level", 1)))
        allow_unsigned_dev = bool(raw.get("allow_unsigned_dev", False))
        mtls_required = bool(raw.get("mtls_required", mode == "STRICT"))
        pinning_required = bool(raw.get("pinning_required", mode == "STRICT"))
        allow_tls12 = bool(raw.get("allow_tls12", False))
        allow_plain_https = bool(raw.get("allow_plain_https", False))

        mass_storage_default_action = str(raw.get("mass_storage_default_action", "block_on_insert")).strip().lower()
        if mass_storage_default_action not in {"block_on_insert", "allow"}:
            return None

        usb_allowlist = _parse_allowlist(raw.get("usb_allowlist"))
        if usb_allowlist is None:
            return None

        temporary_allow_duration_minutes = max(1, int(raw.get("temporary_allow_duration_minutes", 60)))
        escalation_threshold = max(1, int(raw.get("escalation_threshold", 3)))
        device_enforcement_mode = str(raw.get("device_enforcement_mode", "observe")).strip().lower()
        if device_enforcement_mode not in {"observe", "enforce"}:
            return None
        mass_storage_offline_behavior = str(raw.get("mass_storage_offline_behavior", "block")).strip().lower()
        if mass_storage_offline_behavior not in {"block"}:
            return None
        allow_token_required_for_unblock = bool(raw.get("allow_token_required_for_unblock", True))
        allow_token_max_duration_minutes = max(1, int(raw.get("allow_token_max_duration_minutes", 240)))
        local_event_queue_retention_hours = max(1, int(raw.get("local_event_queue_retention_hours", 72)))
        token_public_key_path = str(raw.get("token_public_key_path", "configs/device_allow_token_public.pem"))

        rollout_raw = raw.get("device_enforcement_rollout") or {}
        if not isinstance(rollout_raw, dict):
            return None
        strategy = str(rollout_raw.get("strategy", "all")).strip().lower()
        if strategy not in {"all", "percent", "allowlist_agents", "tags"}:
            return None
        percent = min(100, max(0, int(rollout_raw.get("percent", 100))))
        allowlist_agents = [int(a) for a in rollout_raw.get("allowlist_agents", []) if str(a).isdigit()]
        tags = [str(tag).strip() for tag in rollout_raw.get("tags", []) if str(tag).strip()]
        device_enforcement_rollout = DeviceEnforcementRollout(
            strategy=strategy,
            percent=percent,
            allowlist_agents=allowlist_agents,
            tags=tags,
        )
        device_kill_switch = bool(raw.get("device_kill_switch", False))
        per_agent_override_allowed = bool(raw.get("per_agent_override_allowed", True))
        enforcement_grace_seconds = max(0, int(raw.get("enforcement_grace_seconds", 0)))

        if mode == "STRICT" and (allow_tls12 or allow_plain_https):
            return None
        return SecurityPolicy(
            mode=mode,
            allow_key_override=allow_key_override,
            grace_days=grace_days,
            status_redaction_level=status_redaction_level,
            allow_unsigned_dev=allow_unsigned_dev,
            mtls_required=mtls_required,
            pinning_required=pinning_required,
            allow_tls12=allow_tls12,
            allow_plain_https=allow_plain_https,
            mass_storage_default_action=mass_storage_default_action,
            usb_allowlist=usb_allowlist,
            temporary_allow_duration_minutes=temporary_allow_duration_minutes,
            escalation_threshold=escalation_threshold,
            device_enforcement_mode=device_enforcement_mode,
            mass_storage_offline_behavior=mass_storage_offline_behavior,
            allow_token_required_for_unblock=allow_token_required_for_unblock,
            allow_token_max_duration_minutes=allow_token_max_duration_minutes,
            local_event_queue_retention_hours=local_event_queue_retention_hours,
            token_public_key_path=token_public_key_path,
            device_enforcement_rollout=device_enforcement_rollout,
            device_kill_switch=device_kill_switch,
            per_agent_override_allowed=per_agent_override_allowed,
            enforcement_grace_seconds=enforcement_grace_seconds,
        )
    except Exception:
        return None


def load_security_policy(policy_path: str, policy_sig_path: str, public_key_override: str | None = None) -> PolicyLoadResult:
    p_path = Path(policy_path)
    s_path = Path(policy_sig_path)

    if not p_path.exists() or not s_path.exists():
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_MISSING")

    try:
        policy_obj = json.loads(p_path.read_text(encoding="utf-8"))
    except Exception:
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_JSON")
    if not isinstance(policy_obj, dict):
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_JSON")

    sig_raw = s_path.read_text(encoding="utf-8").strip()
    if not sig_raw:
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_SIGNATURE")

    ok, reason = verify_signature(_canonical_policy_bytes(policy_obj), sig_raw, public_key_override)
    if not ok:
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_SIGNATURE")

    parsed = _parse_policy(policy_obj)
    if parsed is None:
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_JSON")

    dev_flag = os.getenv("ECIMS_DEV_MODE", "").strip().lower() in {"1", "true", "yes"}
    if dev_flag and parsed.allow_unsigned_dev:
        return PolicyLoadResult(policy=parsed, source="signed", reason="OK_DEV")

    return PolicyLoadResult(policy=parsed, source="signed", reason="OK")
