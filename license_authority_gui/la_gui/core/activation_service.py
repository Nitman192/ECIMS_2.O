"""Offline server activation request/verification helper service."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from la_gui.core.canonical_json import canonicalize_json
from la_gui.core.crypto_service import CryptoService
from la_gui.core.storage_paths import StoragePaths

REQUEST_TOKEN_TYPE = "ECIMS_ACTIVATION_REQUEST_V1"
VERIFY_TOKEN_TYPE = "ECIMS_SERVER_ACTIVATION_V1"


def _b64u_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64u_decode(payload: str) -> bytes:
    pad = "=" * ((4 - len(payload) % 4) % 4)
    return base64.urlsafe_b64decode(payload + pad)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ActivationService:
    @staticmethod
    def parse_request_code(raw_input: str) -> dict[str, Any]:
        token = raw_input.strip()
        if not token:
            raise ValueError("Activation request code is required.")
        try:
            payload = json.loads(_b64u_decode(token).decode("utf-8"))
        except Exception as exc:
            raise ValueError("Activation request code is invalid.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Activation request payload is invalid.")
        if str(payload.get("token_type", "")) != REQUEST_TOKEN_TYPE:
            raise ValueError("Unsupported activation request token type.")

        required = ["installation_id", "challenge", "license_id", "machine_fingerprint", "expires_at"]
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Activation request missing fields: {', '.join(missing)}")

        expires_at = _parse_iso(str(payload["expires_at"]))
        if _utcnow() > expires_at:
            raise ValueError("Activation request has already expired.")
        return payload

    @staticmethod
    def create_verification_id(
        *,
        request_payload: dict[str, Any],
        private_key: RSAPrivateKey,
        validity_days: int = 30,
    ) -> tuple[str, dict[str, Any]]:
        if validity_days < 1:
            validity_days = 1
        now = _utcnow()
        expires_at = now + timedelta(days=validity_days)
        claims = {
            "token_type": VERIFY_TOKEN_TYPE,
            "installation_id": str(request_payload["installation_id"]),
            "challenge": str(request_payload["challenge"]),
            "license_id": str(request_payload["license_id"]),
            "machine_fingerprint": str(request_payload["machine_fingerprint"]).lower(),
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "verification_id": f"VER-{uuid.uuid4().hex[:16].upper()}",
        }
        payload_raw = canonicalize_json(claims)
        signature_b64 = CryptoService.sign_bytes(private_key=private_key, payload=payload_raw)
        signature_raw = base64.b64decode(signature_b64.encode("ascii"))
        token = f"{_b64u_encode(payload_raw)}.{_b64u_encode(signature_raw)}"
        return token, claims

    @staticmethod
    def load_registry(storage_paths: StoragePaths) -> dict[str, Any]:
        path = storage_paths.activation_registry_path
        if not path.exists():
            return {"clients": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"clients": []}
            clients = data.get("clients", [])
            if not isinstance(clients, list):
                clients = []
            return {"clients": clients}
        except Exception:
            return {"clients": []}

    @staticmethod
    def save_registry(storage_paths: StoragePaths, payload: dict[str, Any]) -> None:
        path = storage_paths.activation_registry_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def upsert_registry_entry(
        *,
        storage_paths: StoragePaths,
        request_payload: dict[str, Any],
        verification_claims: dict[str, Any],
    ) -> dict[str, Any]:
        registry = ActivationService.load_registry(storage_paths)
        clients = registry.get("clients", [])
        if not isinstance(clients, list):
            clients = []

        installation_id = str(request_payload.get("installation_id", "")).strip()
        now_iso = _utcnow().isoformat()
        entry = {
            "installation_id": installation_id,
            "license_id": str(request_payload.get("license_id", "")).strip(),
            "customer_name": str(request_payload.get("customer_name", "")).strip(),
            "license_expiry_date": str(request_payload.get("license_expiry_date", "")).strip(),
            "machine_fingerprint_short": str(request_payload.get("machine_fingerprint", "")).strip().lower()[:8],
            "verification_id": str(verification_claims.get("verification_id", "")).strip(),
            "verification_issued_at": str(verification_claims.get("issued_at", "")).strip(),
            "verification_expires_at": str(verification_claims.get("expires_at", "")).strip(),
            "last_updated_at": now_iso,
        }

        updated = False
        for idx, item in enumerate(clients):
            if not isinstance(item, dict):
                continue
            if str(item.get("installation_id", "")).strip() == installation_id:
                clients[idx] = entry
                updated = True
                break
        if not updated:
            clients.append(entry)
        registry["clients"] = clients
        ActivationService.save_registry(storage_paths, registry)
        return entry

    @staticmethod
    def expiring_entries(storage_paths: StoragePaths, *, within_days: int = 7) -> list[dict[str, Any]]:
        now_date = _utcnow().date()
        threshold = now_date + timedelta(days=max(1, within_days))
        registry = ActivationService.load_registry(storage_paths)
        expiring: list[dict[str, Any]] = []
        for item in registry.get("clients", []):
            if not isinstance(item, dict):
                continue
            raw = str(item.get("license_expiry_date", "")).strip()
            if not raw:
                continue
            try:
                expiry_date = datetime.fromisoformat(f"{raw}T00:00:00+00:00").date()
            except Exception:
                continue
            if now_date <= expiry_date <= threshold:
                row = dict(item)
                row["days_left"] = (expiry_date - now_date).days
                expiring.append(row)
        return sorted(expiring, key=lambda item: int(item.get("days_left", 9999)))
