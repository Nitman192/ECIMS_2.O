from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.licensing_core.fingerprint import compute_machine_fingerprint
from app.licensing_core.integrity import check_licensing_integrity
from app.licensing_core.models import LicensePayload, LicenseReason, LicenseState
from app.licensing_core.verifier import EMBEDDED_PUBLIC_KEY_PEM, verify_signature

SMALL_SKEW = timedelta(minutes=5)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _parse_payload(payload_obj: dict) -> LicensePayload | None:
    try:
        payload = LicensePayload(
            org_name=str(payload_obj["org_name"]),
            max_agents=int(payload_obj["max_agents"]),
            expiry_date=str(payload_obj["expiry_date"]),
            ai_enabled=bool(payload_obj["ai_enabled"]),
            machine_fingerprint=str(payload_obj["machine_fingerprint"]).lower() if payload_obj.get("machine_fingerprint") else None,
            license_id=str(payload_obj["license_id"]) if payload_obj.get("license_id") else None,
            customer_name=str(payload_obj["customer_name"]) if payload_obj.get("customer_name") else None,
        )
    except Exception:
        return None
    return payload if payload.max_agents >= 1 else None


def _derive_hmac_key() -> bytes:
    return hashlib.sha256(EMBEDDED_PUBLIC_KEY_PEM.encode("utf-8")).digest()


def _state_file_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    state_dir = root / "server" / ".ecims_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "last_run.json"


def _read_last_run() -> datetime | None:
    path = _state_file_path()
    if not path.exists():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        ts = str(body["last_seen_utc"])
        sig = str(body["hmac_hex"])
        expected = hmac.new(_derive_hmac_key(), ts.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return datetime.max.replace(tzinfo=timezone.utc)
        return _parse_iso(ts)
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def _write_last_run(now_iso: str) -> None:
    sig = hmac.new(_derive_hmac_key(), now_iso.encode("utf-8"), hashlib.sha256).hexdigest()
    _state_file_path().write_text(json.dumps({"last_seen_utc": now_iso, "hmac_hex": sig}), encoding="utf-8")


def load_license(license_path: str, public_key_path: str | None = None) -> LicenseState:
    now = _utc_now()
    loaded_at = now.isoformat()
    local_fp = compute_machine_fingerprint()
    local_short = local_fp[:8]

    integrity_ok, integrity_reason = check_licensing_integrity()
    if not integrity_ok:
        return LicenseState(False, integrity_reason, None, loaded_at, None, local_short)

    env = os.getenv("ECIMS_ENVIRONMENT", "dev").strip().lower() or "dev"
    enforce_tamper = env == "prod"

    last_run = _read_last_run()
    if enforce_tamper and last_run is not None and (last_run == datetime.max.replace(tzinfo=timezone.utc) or now < (last_run - SMALL_SKEW)):
        return LicenseState(False, LicenseReason.TAMPER_DETECTED.value, None, loaded_at, None, local_short)

    license_file = Path(license_path)
    if not license_file.exists():
        return LicenseState(False, LicenseReason.NO_LICENSE_FILE.value, None, loaded_at, None, local_short)

    try:
        body = json.loads(license_file.read_text(encoding="utf-8"))
    except Exception:
        return LicenseState(False, LicenseReason.INVALID_JSON.value, None, loaded_at, None, local_short)

    if not isinstance(body, dict) or "payload" not in body or "signature_b64" not in body:
        return LicenseState(False, LicenseReason.INVALID_JSON.value, None, loaded_at, None, local_short)

    payload_obj = body["payload"]
    signature_b64 = body["signature_b64"]
    if not isinstance(payload_obj, dict) or not isinstance(signature_b64, str):
        return LicenseState(False, LicenseReason.INVALID_JSON.value, None, loaded_at, None, local_short)

    payload = _parse_payload(payload_obj)
    if payload is None:
        return LicenseState(False, LicenseReason.INVALID_JSON.value, None, loaded_at, None, local_short)

    ok, verify_reason = verify_signature(_canonical_payload_bytes(payload_obj), signature_b64, public_key_path)
    if not ok:
        return LicenseState(False, verify_reason, None, loaded_at, None, local_short)

    try:
        exp = date.fromisoformat(payload.expiry_date)
    except ValueError:
        return LicenseState(False, LicenseReason.INVALID_JSON.value, None, loaded_at, None, local_short)

    if exp < now.date():
        return LicenseState(False, LicenseReason.EXPIRED.value, payload, loaded_at, None, local_short)

    machine_match = None
    if payload.machine_fingerprint:
        machine_match = payload.machine_fingerprint.lower() == local_fp.lower()
        if not machine_match:
            return LicenseState(False, LicenseReason.MACHINE_MISMATCH.value, payload, loaded_at, False, local_short)

    _write_last_run(loaded_at)
    return LicenseState(True, LicenseReason.OK.value, payload, loaded_at, machine_match, local_short)
