from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.licensing_core.verifier import verify_signature


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
    data_encryption_required: bool
    allow_plaintext_exports: bool
    allow_key_rotation_grace: bool


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
    data_encryption_required=True,
    allow_plaintext_exports=False,
    allow_key_rotation_grace=False,
)


def _canonical_policy_bytes(policy_dict: dict) -> bytes:
    return json.dumps(policy_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
        data_encryption_required = bool(raw.get("data_encryption_required", mode == "STRICT"))
        allow_plaintext_exports = bool(raw.get("allow_plaintext_exports", False))
        allow_key_rotation_grace = bool(raw.get("allow_key_rotation_grace", False))

        if mode == "STRICT" and (allow_tls12 or allow_plain_https or allow_plaintext_exports or allow_key_rotation_grace):
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
            data_encryption_required=data_encryption_required,
            allow_plaintext_exports=allow_plaintext_exports,
            allow_key_rotation_grace=allow_key_rotation_grace,
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
        # No unsigned policy downgrades here. Must be signed to influence security posture.
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_SIGNATURE")

    parsed = _parse_policy(policy_obj)
    if parsed is None:
        return PolicyLoadResult(policy=DEFAULT_POLICY, source="default", reason="POLICY_INVALID_JSON")

    # Environment may enable additional development convenience only when signed policy permits.
    dev_flag = os.getenv("ECIMS_DEV_MODE", "").strip().lower() in {"1", "true", "yes"}
    if dev_flag and parsed.allow_unsigned_dev:
        return PolicyLoadResult(policy=parsed, source="signed", reason="OK_DEV")

    return PolicyLoadResult(policy=parsed, source="signed", reason="OK")
