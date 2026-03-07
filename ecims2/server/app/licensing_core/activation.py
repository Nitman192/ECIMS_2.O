from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from app.licensing_core.fingerprint import compute_machine_fingerprint
from app.licensing_core.models import LicensePayload
from app.licensing_core.verifier import load_public_key

ACTIVATION_REQUEST_TOKEN_TYPE = "ECIMS_ACTIVATION_REQUEST_V1"
ACTIVATION_VERIFY_TOKEN_TYPE = "ECIMS_SERVER_ACTIVATION_V1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _b64u_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64u_decode(payload: str) -> bytes:
    pad = "=" * ((4 - len(payload) % 4) % 4)
    return base64.urlsafe_b64decode(payload + pad)


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "activation_required": True,
        "activated": None,
        "activation_request": None,
    }


def resolve_activation_state_path(path_str: str) -> Path:
    candidate = Path(path_str)
    if not candidate.is_absolute():
        root = Path(__file__).resolve().parents[3]
        candidate = root / candidate
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def load_activation_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _default_state()
        merged = _default_state()
        merged.update(raw)
        return merged
    except Exception:
        return _default_state()


def save_activation_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def build_activation_request(
    *,
    payload: LicensePayload,
    state_path: Path,
    ttl_hours: int,
) -> dict[str, Any]:
    if ttl_hours < 1:
        ttl_hours = 1
    now = _utcnow()
    machine_fp = compute_machine_fingerprint().lower()
    license_id = str(payload.license_id or "").strip()
    if not license_id:
        raise ValueError("ACTIVATION_LICENSE_ID_MISSING")

    installation_id = f"INS-{uuid.uuid4().hex[:20].upper()}"
    challenge = secrets.token_urlsafe(24)
    expires_at = (now + timedelta(hours=ttl_hours)).isoformat()
    request_obj = {
        "installation_id": installation_id,
        "challenge": challenge,
        "license_id": license_id,
        "machine_fingerprint": machine_fp,
        "license_expiry_date": payload.expiry_date,
        "customer_name": payload.customer_name or payload.org_name,
        "issued_at": now.isoformat(),
        "expires_at": expires_at,
    }
    request_code = _b64u_encode(
        json.dumps(
            {
                "token_type": ACTIVATION_REQUEST_TOKEN_TYPE,
                **request_obj,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    state = load_activation_state(state_path)
    state["activation_required"] = True
    state["activation_request"] = request_obj
    state["activated"] = None
    save_activation_state(state_path, state)
    return {
        **request_obj,
        "request_code": request_code,
        "machine_fingerprint_short": machine_fp[:8],
    }


def parse_activation_verification_token(token: str, public_key_path: str | None) -> dict[str, Any]:
    pieces = token.strip().split(".", 1)
    if len(pieces) != 2:
        raise ValueError("ACTIVATION_TOKEN_FORMAT_INVALID")
    payload_b64, sig_b64 = pieces
    try:
        payload_raw = _b64u_decode(payload_b64)
        signature = _b64u_decode(sig_b64)
    except Exception as exc:
        raise ValueError("ACTIVATION_TOKEN_ENCODING_INVALID") from exc

    public_key = load_public_key(public_key_path)
    try:
        public_key.verify(
            signature,
            payload_raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except InvalidSignature:
        try:
            public_key.verify(signature, payload_raw, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature as exc:
            raise ValueError("ACTIVATION_TOKEN_SIGNATURE_INVALID") from exc
    except Exception as exc:
        raise ValueError("ACTIVATION_TOKEN_SIGNATURE_INVALID") from exc

    try:
        claims = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("ACTIVATION_TOKEN_PAYLOAD_INVALID") from exc
    if not isinstance(claims, dict):
        raise ValueError("ACTIVATION_TOKEN_PAYLOAD_INVALID")

    if str(claims.get("token_type", "")) != ACTIVATION_VERIFY_TOKEN_TYPE:
        raise ValueError("ACTIVATION_TOKEN_TYPE_INVALID")
    expires_at_raw = str(claims.get("expires_at", "")).strip()
    if not expires_at_raw:
        raise ValueError("ACTIVATION_TOKEN_EXPIRES_MISSING")
    try:
        expires_at = _parse_iso(expires_at_raw)
    except Exception as exc:
        raise ValueError("ACTIVATION_TOKEN_EXPIRES_INVALID") from exc
    if _utcnow() > expires_at:
        raise ValueError("ACTIVATION_TOKEN_EXPIRED")
    return claims


def apply_activation_verification(
    *,
    token: str,
    state_path: Path,
    public_key_path: str | None,
) -> dict[str, Any]:
    state = load_activation_state(state_path)
    request_obj = state.get("activation_request")
    if not isinstance(request_obj, dict):
        raise ValueError("ACTIVATION_REQUEST_MISSING")

    expires_at = _parse_iso(str(request_obj.get("expires_at", "")))
    if _utcnow() > expires_at:
        raise ValueError("ACTIVATION_REQUEST_EXPIRED")

    claims = parse_activation_verification_token(token, public_key_path)
    request_installation_id = str(request_obj.get("installation_id", "")).strip()
    request_license_id = str(request_obj.get("license_id", "")).strip()
    request_machine = str(request_obj.get("machine_fingerprint", "")).strip().lower()
    request_challenge = str(request_obj.get("challenge", "")).strip()

    if str(claims.get("installation_id", "")).strip() != request_installation_id:
        raise ValueError("ACTIVATION_INSTALLATION_ID_MISMATCH")
    if str(claims.get("license_id", "")).strip() != request_license_id:
        raise ValueError("ACTIVATION_LICENSE_ID_MISMATCH")
    if str(claims.get("machine_fingerprint", "")).strip().lower() != request_machine:
        raise ValueError("ACTIVATION_MACHINE_FINGERPRINT_MISMATCH")
    if str(claims.get("challenge", "")).strip() != request_challenge:
        raise ValueError("ACTIVATION_CHALLENGE_MISMATCH")

    verified_at = _utcnow().isoformat()
    activated = {
        "installation_id": request_installation_id,
        "license_id": request_license_id,
        "machine_fingerprint": request_machine,
        "verified_at": verified_at,
        "verification_id": str(claims.get("verification_id", "")).strip(),
        "verification_token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
    }
    state["activated"] = activated
    state["activation_request"] = None
    save_activation_state(state_path, state)
    return activated


def get_activation_gate_result(*, payload: LicensePayload, state_path: Path) -> tuple[bool, str]:
    state = load_activation_state(state_path)
    activated = state.get("activated")
    if not isinstance(activated, dict):
        request_obj = state.get("activation_request")
        if isinstance(request_obj, dict):
            try:
                if _utcnow() <= _parse_iso(str(request_obj.get("expires_at", ""))):
                    return False, "ACTIVATION_PENDING"
            except Exception:
                pass
        return False, "ACTIVATION_REQUIRED"

    license_id = str(payload.license_id or "").strip()
    machine_fp = compute_machine_fingerprint().lower()
    if str(activated.get("license_id", "")).strip() != license_id:
        return False, "ACTIVATION_LICENSE_MISMATCH"
    if str(activated.get("machine_fingerprint", "")).strip().lower() != machine_fp:
        return False, "ACTIVATION_MACHINE_MISMATCH"
    return True, "OK"


def get_activation_status(*, state_path: Path, activation_required: bool) -> dict[str, Any]:
    state = load_activation_state(state_path)
    activated = state.get("activated")
    request_obj = state.get("activation_request")
    return {
        "activation_required": bool(activation_required),
        "is_activated": bool(isinstance(activated, dict)),
        "activated": activated if isinstance(activated, dict) else None,
        "pending_request": request_obj if isinstance(request_obj, dict) else None,
    }
