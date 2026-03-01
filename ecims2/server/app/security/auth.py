from __future__ import annotations

import base64
import crypt
import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.utils.time import utcnow


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + pad).encode("ascii"))


def hash_password(password: str) -> str:
    settings = get_settings()
    if hasattr(crypt, "METHOD_BLOWFISH"):
        salt = crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=max(16, settings.bcrypt_rounds))
        hashed = crypt.crypt(password, salt)
        if hashed:
            return hashed
    raise RuntimeError("bcrypt hashing is unavailable in this runtime")


def verify_password(password: str, password_hash: str) -> bool:
    computed = crypt.crypt(password, password_hash)
    return secrets.compare_digest(computed or "", password_hash)


def create_access_token(*, user_id: int, username: str, role: str) -> str:
    settings = get_settings()
    now = utcnow()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expiry_minutes)).timestamp()),
    }
    signing_input = f"{_b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))}.{_b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
    sig = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    signing_input = f"{parts[0]}.{parts[1]}"
    expected_sig = hmac.new(settings.jwt_secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    token_sig = _b64url_decode(parts[2])
    if not secrets.compare_digest(expected_sig, token_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(utcnow().timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload
