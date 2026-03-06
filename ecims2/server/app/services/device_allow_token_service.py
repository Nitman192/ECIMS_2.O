from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config import get_settings
from app.db.database import get_db
from app.utils.time import utcnow


def _resolve_path(path_value: str) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    root = Path(__file__).resolve().parents[3]
    return root / candidate


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


class DeviceAllowTokenService:
    @staticmethod
    def issue_token(
        *,
        agent_id: int,
        duration_minutes: int,
        scope: dict[str, Any],
        justification: str,
        policy_version: str,
    ) -> tuple[str, dict[str, Any]]:
        settings = get_settings()
        max_dur = settings.allow_token_max_duration_minutes
        duration = min(max(1, duration_minutes), max_dur)

        now = utcnow()
        claims = {
            "token_id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=duration)).isoformat(),
            "single_use": True,
            "scope": scope,
            "reason": justification,
            "policy_version": policy_version,
        }
        claims_bytes = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")

        priv_path = _resolve_path(settings.device_allow_token_private_key_path)
        private_key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
        signature = private_key.sign(
            claims_bytes,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        token = f"{_b64(claims_bytes)}.{_b64(signature)}"

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO device_allow_tokens(token_id, agent_id, issued_at, expires_at, scope_json, status)
                VALUES(?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (
                    claims["token_id"],
                    agent_id,
                    claims["issued_at"],
                    claims["expires_at"],
                    json.dumps(scope),
                ),
            )
        return token, claims

    @staticmethod
    def revoke_token(token_id: str) -> bool:
        with get_db() as conn:
            row = conn.execute("SELECT token_id FROM device_allow_tokens WHERE token_id = ?", (token_id,)).fetchone()
            if not row:
                return False
            conn.execute("UPDATE device_allow_tokens SET status = 'REVOKED' WHERE token_id = ?", (token_id,))
            return True

    @staticmethod
    def consume_token(*, token: str, agent_id: int, public_key_path: str) -> tuple[bool, str, dict[str, Any] | None]:
        claims = DeviceAllowTokenService.verify_token_offline(token, public_key_path)
        if not claims:
            return False, "TOKEN_INVALID_OR_EXPIRED", None

        token_id = str(claims.get("token_id") or "").strip()
        if not token_id:
            return False, "TOKEN_INVALID_OR_EXPIRED", None
        if int(claims.get("agent_id", -1)) != agent_id:
            return False, "TOKEN_AGENT_MISMATCH", None

        now = utcnow()
        with get_db() as conn:
            row = conn.execute(
                "SELECT token_id, agent_id, expires_at, status FROM device_allow_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if not row:
                return False, "TOKEN_NOT_FOUND", claims
            if int(row["agent_id"]) != agent_id:
                return False, "TOKEN_AGENT_MISMATCH", claims

            status = str(row["status"] or "").upper()
            expires_at = DeviceAllowTokenService._parse_iso(str(row["expires_at"] or ""))
            if expires_at and now > expires_at:
                if status == "ACTIVE":
                    conn.execute("UPDATE device_allow_tokens SET status = 'EXPIRED' WHERE token_id = ?", (token_id,))
                return False, "TOKEN_EXPIRED", claims
            if status == "REVOKED":
                return False, "TOKEN_REVOKED", claims
            if status == "CONSUMED":
                return False, "TOKEN_ALREADY_USED", claims
            if status != "ACTIVE":
                return False, f"TOKEN_STATUS_{status or 'UNKNOWN'}", claims

            conn.execute("UPDATE device_allow_tokens SET status = 'CONSUMED' WHERE token_id = ?", (token_id,))
            return True, "CONSUMED", claims

    @staticmethod
    def verify_token_offline(token: str, public_key_path: str) -> dict[str, Any] | None:
        try:
            payload_b64, sig_b64 = token.split(".", 1)
            payload = _b64d(payload_b64)
            sig = _b64d(sig_b64)
            public_key = serialization.load_pem_public_key(_resolve_path(public_key_path).read_bytes())
            public_key.verify(
                sig,
                payload,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            claims = json.loads(payload.decode("utf-8"))
            expires_at = DeviceAllowTokenService._parse_iso(str(claims.get("expires_at", "")))
            if not expires_at or utcnow() > expires_at:
                return None
            return claims
        except Exception:
            return None

    @staticmethod
    def _parse_iso(value: str) -> datetime | None:
        try:
            dt = datetime.fromisoformat(value)
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
